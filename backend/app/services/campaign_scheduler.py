"""Lightweight, resilient Campaign Scheduler and worker restart recovery service for TARA 2.0.

Provides:
- Timezone-aware scheduled campaign execution.
- Safe worker restart recovery without duplicate dispatch.
- Periodic background check loop integrated with FastAPI app lifespan.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.db import get_db
from app.services.campaign_execution import execute_campaign_dispatch

try:
    from twilio.rest import Client as TwilioRestClient
except ImportError:
    TwilioRestClient = None  # type: ignore

logger = logging.getLogger("tara.services.campaign_scheduler")

_scheduler_task: Optional[asyncio.Task] = None
_is_running: bool = False


async def schedule_campaign(
    db: AsyncIOMotorDatabase,
    campaign_id: str,
    tenant_id: str,
    scheduled_start_time: datetime,
    timezone_str: str = "Asia/Kolkata",
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Set a campaign's status to SCHEDULED with a target future start time.
    """
    now_utc = datetime.now(timezone.utc)

    # Ensure start time has tzinfo
    if scheduled_start_time.tzinfo is None:
        tz = ZoneInfo(timezone_str)
        target_utc = scheduled_start_time.replace(tzinfo=tz).astimezone(timezone.utc)
    else:
        target_utc = scheduled_start_time.astimezone(timezone.utc)

    if target_utc <= now_utc:
        raise ValueError("Scheduled start time must be in the future")

    update_fields = {
        "status": "SCHEDULED",
        "scheduled_start_time": target_utc,
        "timezone": timezone_str,
        "updated_at": now_utc,
    }

    await db.campaigns.update_one(
        {"_id": ObjectId(campaign_id), "tenant_id": tenant_id},
        {"$set": update_fields},
    )

    if user:
        await db.audit_log.insert_one({
            "tenant_id": tenant_id,
            "actor_user_id": user.get("user_id", "system"),
            "action": "scheduled",
            "entity_type": "campaign",
            "entity_id": campaign_id,
            "detail": {"scheduled_start_time": target_utc.isoformat(), "timezone": timezone_str},
            "at": now_utc,
        })

    logger.info("Campaign %s scheduled for execution at %s (UTC)", campaign_id, target_utc.isoformat())
    return {
        "campaign_id": campaign_id,
        "status": "SCHEDULED",
        "scheduled_start_time": target_utc,
        "timezone": timezone_str,
    }


async def check_and_execute_scheduled_campaigns(db: AsyncIOMotorDatabase) -> int:
    """
    Scan for SCHEDULED campaigns whose start time has arrived, and trigger their dispatch.
    Returns the number of campaigns initiated.
    """
    now_utc = datetime.now(timezone.utc)

    cursor = db.campaigns.find({
        "status": "SCHEDULED",
        "scheduled_start_time": {"$lte": now_utc},
    })

    count = 0
    async for camp in cursor:
        cid = str(camp["_id"])
        tid = camp["tenant_id"]
        logger.info("Scheduled start time reached for campaign %s (%s). Starting execution.", cid, camp.get("name"))

        # Transition to RUNNING
        await db.campaigns.update_one(
            {"_id": camp["_id"]},
            {"$set": {"status": "RUNNING", "launched_at": now_utc, "updated_at": now_utc}},
        )

        sys_user = {
            "tenant_id": tid,
            "user_id": camp.get("created_by", "scheduler"),
            "tenant_name": camp.get("product_name", "Gnani Bank"),
        }
        asyncio.create_task(execute_campaign_dispatch(db, cid, tid, sys_user))
        count += 1

    return count


async def reconcile_inflight_recipient(
    db: AsyncIOMotorDatabase,
    rcpt: Dict[str, Any],
    tenant_id: str,
) -> str:
    """
    Reconcile a recipient left in CALLING or QUEUED status with Twilio and communications record.
    Never blindly re-dials a potentially active call.
    Returns the resolved status ('CALLING', 'PENDING', or terminal status).
    """
    now_utc = datetime.now(timezone.utc)
    comm_id = rcpt.get("last_communication_id")

    comm = None
    if comm_id:
        comm_obj_id = ObjectId(comm_id) if ObjectId.is_valid(comm_id) else comm_id
        comm = await db.communications.find_one({"_id": comm_obj_id})

    if not comm:
        # Call was never successfully created or dispatched before crash.
        # Safely reset to PENDING so it can be cleanly dispatched.
        logger.info("Recovery: Recipient %s has no communication record. Resetting to PENDING.", rcpt.get("entity_id"))
        await db.campaign_recipients.update_one(
            {"_id": rcpt["_id"]},
            {"$set": {"status": "PENDING", "updated_at": now_utc}},
        )
        return "PENDING"

    provider_ref = comm.get("provider_ref")
    comm_status = comm.get("status")

    # If communication already reached a terminal state in MongoDB, align recipient
    if comm_status in ("COMPLETED", "FAILED", "BUSY", "NO_ANSWER", "BLOCKED", "CANCELED"):
        resolved_status = "FAILED" if comm_status == "FAILED" else ("NO_ANSWER" if comm_status in ("BUSY", "NO_ANSWER") else "CONTACTED")
        if comm_status == "COMPLETED":
            outcome = comm.get("outcome") or {}
            interest = str(outcome.get("interest_level", "")).lower().strip()
            if interest == "interested":
                resolved_status = "INTERESTED"
            elif interest == "callback":
                resolved_status = "CALLBACK"
            elif interest == "not_interested":
                resolved_status = "NOT_INTERESTED"

        await db.campaign_recipients.update_one(
            {"_id": rcpt["_id"]},
            {"$set": {"status": resolved_status, "updated_at": now_utc}},
        )
        logger.info("Recovery: Reconciled recipient %s to %s from communication status %s", rcpt.get("entity_id"), resolved_status, comm_status)
        return resolved_status

    # Communication is DISPATCHED or IN_PROGRESS. Check with Twilio REST API if live
    twilio_resolved_status = None
    if provider_ref and str(provider_ref).startswith("CA") and not settings.test_mode and settings.twilio_account_sid and settings.twilio_auth_token and TwilioRestClient:
        try:
            client = TwilioRestClient(settings.twilio_account_sid, settings.twilio_auth_token)
            call = client.calls(provider_ref).fetch()
            tw_stat = getattr(call, "status", None)
            logger.info("Recovery: Twilio REST API reports status '%s' for CallSid %s", tw_stat, provider_ref)

            if tw_stat in ("queued", "ringing", "in-progress"):
                # Call is genuinely still active on Twilio. DO NOT re-dial or fail it.
                return "CALLING"
            elif tw_stat == "completed":
                twilio_resolved_status = "COMPLETED"
            elif tw_stat in ("busy", "no-answer"):
                twilio_resolved_status = "NO_ANSWER"
            elif tw_stat in ("failed", "canceled"):
                twilio_resolved_status = "FAILED"
        except Exception as exc:
            logger.warning("Recovery: Failed to fetch Twilio status for %s: %s", provider_ref, exc)

    if twilio_resolved_status:
        await db.communications.update_one(
            {"_id": comm["_id"]},
            {"$set": {"status": twilio_resolved_status, "completed_at": now_utc, "updated_at": now_utc}},
        )
        await db.campaign_recipients.update_one(
            {"_id": rcpt["_id"]},
            {"$set": {"status": twilio_resolved_status, "updated_at": now_utc}},
        )
        return twilio_resolved_status

    # If mock mode or cannot reach Twilio: check how long it has been in flight
    comm_created = comm.get("created_at") or now_utc
    if comm_created.tzinfo is None:
        comm_created = comm_created.replace(tzinfo=timezone.utc)

    age_seconds = (now_utc - comm_created).total_seconds()
    if age_seconds > 600:  # In-flight for over 10 minutes without resolution
        logger.info("Recovery: In-flight communication %s timed out (>10m). Marking FAILED.", comm_id)
        await db.communications.update_one(
            {"_id": comm["_id"]},
            {"$set": {"status": "FAILED", "updated_at": now_utc}},
        )
        await db.campaign_recipients.update_one(
            {"_id": rcpt["_id"]},
            {"$set": {"status": "FAILED", "blocked_reason": "timeout_in_flight", "updated_at": now_utc}},
        )
        return "FAILED"

    # Otherwise still within active window; preserve CALLING
    return "CALLING"


async def recover_interrupted_campaigns(db: AsyncIOMotorDatabase) -> int:
    """
    Startup recovery: inspect campaigns left in RUNNING or LAUNCHING status,
    reconciles in-flight recipients with Twilio/communications, and resumes pending recipients safely.
    """
    cursor = db.campaigns.find({
        "status": {"$in": ["RUNNING", "LAUNCHING", "ACTIVE"]},
    })

    resumed_count = 0
    async for camp in cursor:
        cid = str(camp["_id"])
        tid = camp["tenant_id"]

        # 1. Reconcile any in-flight / CALLING recipients first
        calling_cursor = db.campaign_recipients.find({
            "campaign_id": cid,
            "status": {"$in": ["CALLING", "QUEUED"]},
        })
        async for r in calling_cursor:
            await reconcile_inflight_recipient(db, r, tid)

        # 2. Check pending recipients
        pending_recipients = await db.campaign_recipients.count_documents({
            "campaign_id": cid,
            "status": "PENDING",
        })

        still_active = await db.campaign_recipients.count_documents({
            "campaign_id": cid,
            "status": {"$in": ["CALLING", "QUEUED"]},
        })

        pending_retries = await db.campaign_recipients.count_documents({
            "campaign_id": cid,
            "next_retry_at": {"$ne": None},
        })

        if pending_recipients > 0:
            logger.info(
                "Worker restart recovery: Resuming campaign %s (%d pending recipients)",
                cid,
                pending_recipients,
            )
            sys_user = {
                "tenant_id": tid,
                "user_id": camp.get("created_by", "recovery_worker"),
                "tenant_name": camp.get("product_name", "Gnani Bank"),
            }
            asyncio.create_task(execute_campaign_dispatch(db, cid, tid, sys_user))
            resumed_count += 1
        elif still_active == 0 and pending_retries == 0:
            # Mark COMPLETED if all are already terminal and no pending retries
            logger.info("Worker restart recovery: Auto-completing finished campaign %s", cid)
            now_utc = datetime.now(timezone.utc)
            await db.campaigns.update_one(
                {"_id": camp["_id"]},
                {"$set": {"status": "COMPLETED", "completed_at": now_utc, "updated_at": now_utc}},
            )

    return resumed_count


async def check_and_execute_due_retries(db: AsyncIOMotorDatabase) -> int:
    """
    Scan for active campaigns with recipients due for automatic retry.
    Atomically moves eligible due recipients (next_retry_at <= now_utc) to PENDING
    and triggers campaign execution, respecting pause/cancel and pre-dispatch compliance.
    """
    now_utc = datetime.now(timezone.utc)

    active_campaigns = await db.campaigns.find({
        "status": {"$in": ["RUNNING", "ACTIVE"]},
    }).to_list(length=100)

    total_queued = 0
    for camp in active_campaigns:
        cid = str(camp["_id"])
        tid = camp["tenant_id"]

        cfg_doc = await db.campaign_configs.find_one({
            "campaign_id": cid,
            "channel": "voice",
            "version": camp.get("config_version", 1),
        })
        v_cfg = cfg_doc.get("config", {}) if cfg_doc else {}
        retry_policy = v_cfg.get("retry_policy", {})
        max_attempts = int(retry_policy.get("max_attempts", 2))

        due_cursor = db.campaign_recipients.find({
            "campaign_id": cid,
            "tenant_id": tid,
            "status": {"$in": ["NO_ANSWER", "BUSY", "FAILED"]},
            "next_retry_at": {"$lte": now_utc, "$ne": None},
            "attempts": {"$lt": max_attempts},
        })

        due_recipients = await due_cursor.to_list(length=500)
        if not due_recipients:
            continue

        due_ids = [r["_id"] for r in due_recipients]
        res = await db.campaign_recipients.update_many(
            {"_id": {"$in": due_ids}},
            {"$set": {"status": "PENDING", "updated_at": now_utc}, "$unset": {"next_retry_at": ""}},
        )

        if res.modified_count > 0:
            logger.info("Automatic retry: Queued %d due recipients for campaign %s", res.modified_count, cid)
            total_queued += res.modified_count
            sys_user = {
                "tenant_id": tid,
                "user_id": camp.get("created_by", "retry_worker"),
                "tenant_name": camp.get("product_name", "Gnani Bank"),
            }
            asyncio.create_task(execute_campaign_dispatch(db, cid, tid, sys_user))

    return total_queued


async def scheduler_background_loop(poll_interval_seconds: float = 15.0) -> None:
    """
    Background worker loop checking for scheduled campaigns and due retries.
    """
    global _is_running
    _is_running = True
    logger.info("Campaign scheduler background loop started (interval: %.1fs)", poll_interval_seconds)

    while _is_running:
        try:
            db = get_db()
            await check_and_execute_scheduled_campaigns(db)
            await check_and_execute_due_retries(db)
        except Exception as exc:
            logger.error("Error in campaign scheduler loop: %s", exc)

        try:
            await asyncio.sleep(poll_interval_seconds)
        except asyncio.CancelledError:
            break

    logger.info("Campaign scheduler background loop stopped")


def start_campaign_scheduler(poll_interval_seconds: float = 15.0) -> None:
    """Start background scheduler loop."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(scheduler_background_loop(poll_interval_seconds))


def stop_campaign_scheduler() -> None:
    """Cancel background scheduler loop."""
    global _scheduler_task, _is_running
    _is_running = False
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()

