"""Asynchronous Campaign Execution Engine for TARA 2.0.

Orchestrates paced, rate-limited outbound dispatch through the existing CommunicationProvider,
enforcing:
- Controlled concurrency limits via asyncio.Semaphore
- Pre-dispatch compliance checks immediately before each call
- Monotonic state tracking and auto-completion
- Pause, resume, and restart recovery guarantees
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

from app.core.config import settings
from app.core.db import build_tenant_query, doc_to_dict
from app.providers.base import CommunicationProvider
from app.schemas.communication import CommunicationContent, CommunicationSendRequest, RecipientRef
from app.services.campaign_retry import calculate_next_retry_at, is_eligible_for_retry
from app.services.campaign_variables import map_campaign_voice_variables
from app.services.communication import dispatch_communication
from app.services.compliance import is_fake_seeded_number

logger = logging.getLogger("tara.services.campaign_execution")

# Concurrency semaphore cache per campaign to prevent overlapping dispatch loops
_campaign_locks: Dict[str, asyncio.Lock] = {}


def get_campaign_lock(campaign_id: str) -> asyncio.Lock:
    """Retrieve or create async execution lock for a campaign."""
    if campaign_id not in _campaign_locks:
        _campaign_locks[campaign_id] = asyncio.Lock()
    return _campaign_locks[campaign_id]


async def refresh_recipient_statuses(
    db: AsyncIOMotorDatabase,
    campaign_id: str,
    tenant_id: str,
) -> None:
    """
    Reconcile campaign recipient records with their latest communication outcomes.
    Calculates and persists next_retry_at for retry-eligible recipients.
    Auto-completes the campaign only if all recipients are terminal and have no pending retries.
    """
    camp = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
    config_ver = camp.get("config_version", 1) if camp else 1
    cfg_doc = await db.campaign_configs.find_one({
        "campaign_id": campaign_id,
        "channel": "voice",
        "version": config_ver,
    })
    v_cfg = cfg_doc.get("config", {}) if cfg_doc else {}
    retry_policy = v_cfg.get("retry_policy", {})
    max_attempts = int(retry_policy.get("max_attempts", 2))
    interval_minutes = int(retry_policy.get("interval_minutes", 60))

    pipeline = [
        {"$match": {"campaign_id": campaign_id, "tenant_id": tenant_id}},
        {"$sort": {"created_at": -1}},
        {
            "$group": {
                "_id": "$recipient_id",
                "comm_id": {"$first": "$_id"},
                "status": {"$first": "$status"},
                "blocked_reason": {"$first": "$blocked_reason"},
                "outcome": {"$first": "$outcome"},
                "dispatched_at": {"$first": "$dispatched_at"},
                "completed_at": {"$first": "$completed_at"},
                "created_at": {"$first": "$created_at"},
            }
        },
    ]

    latest_comms = await db.communications.aggregate(pipeline).to_list(length=2000)
    if latest_comms:
        bulk_ops: List[UpdateOne] = []
        now_utc = datetime.now(timezone.utc)

        for comm in latest_comms:
            rid = comm["_id"]
            comm_stat = comm.get("status")
            blocked_r = comm.get("blocked_reason")
            outcome = comm.get("outcome") or {}
            last_contact = comm.get("completed_at") or comm.get("dispatched_at") or comm.get("created_at")

            if comm_stat == "BLOCKED":
                new_stat = "BLOCKED"
            elif comm_stat == "FAILED":
                new_stat = "FAILED"
            elif comm_stat in ("DISPATCHED", "IN_PROGRESS"):
                new_stat = "CALLING"
            elif comm_stat in ("NO_ANSWER", "BUSY"):
                new_stat = "NO_ANSWER"
            elif comm_stat == "COMPLETED":
                interest = str(outcome.get("interest_level", "")).lower().strip()
                if interest == "interested":
                    new_stat = "INTERESTED"
                elif interest == "callback":
                    new_stat = "CALLBACK"
                elif interest == "not_interested":
                    new_stat = "NOT_INTERESTED"
                else:
                    new_stat = "CONTACTED"
            else:
                new_stat = "PENDING"

            update_fields: Dict[str, Any] = {
                "status": new_stat,
                "blocked_reason": blocked_r,
                "last_communication_id": str(comm["comm_id"]),
                "last_contact_at": last_contact,
                "updated_at": now_utc,
            }

            if new_stat in ("NO_ANSWER", "FAILED"):
                rcpt_doc = await db.campaign_recipients.find_one({"campaign_id": campaign_id, "entity_id": rid})
                attempts = int(rcpt_doc.get("attempts", 1)) if rcpt_doc else 1
                if is_eligible_for_retry({"status": new_stat, "blocked_reason": blocked_r, "attempts": attempts}, max_attempts):
                    update_fields["next_retry_at"] = calculate_next_retry_at(attempts, interval_minutes, last_contact or now_utc)
                else:
                    update_fields["next_retry_at"] = None
            else:
                update_fields["next_retry_at"] = None

            bulk_ops.append(
                UpdateOne(
                    {"campaign_id": campaign_id, "entity_id": rid},
                    {"$set": update_fields},
                )
            )

        if bulk_ops:
            await db.campaign_recipients.bulk_write(bulk_ops, ordered=False)

    # Check auto-completion: are all recipients terminal and have no pending retries?
    non_terminal_count = await db.campaign_recipients.count_documents({
        "campaign_id": campaign_id,
        "status": {"$in": ["PENDING", "QUEUED", "CALLING"]},
    })
    pending_retries_count = await db.campaign_recipients.count_documents({
        "campaign_id": campaign_id,
        "next_retry_at": {"$ne": None},
    })
    total_count = await db.campaign_recipients.count_documents({"campaign_id": campaign_id})

    now_utc = datetime.now(timezone.utc)
    if total_count > 0 and non_terminal_count == 0 and pending_retries_count == 0:
        if camp and camp.get("status") in ("ACTIVE", "LAUNCHING", "RUNNING"):
            await db.campaigns.update_one(
                {"_id": ObjectId(campaign_id)},
                {"$set": {"status": "COMPLETED", "completed_at": now_utc, "updated_at": now_utc}},
            )
            logger.info("Campaign %s auto-completed (all %d recipients processed, 0 pending retries)", campaign_id, total_count)


async def execute_campaign_dispatch(
    db: AsyncIOMotorDatabase,
    campaign_id: str,
    tenant_id: str,
    current_user: Dict[str, Any],
    voice_provider: Optional[CommunicationProvider] = None,
    delay_seconds: Optional[float] = None,
    max_concurrency: Optional[int] = None,
) -> None:
    """
    Main asynchronous execution loop for a campaign.

    Ensures:
    - Single concurrent dispatch loop per campaign via lock.
    - Controlled concurrency limit via Semaphore.
    - Pre-dispatch compliance checks.
    - Respects pause/cancel state immediately.
    """
    lock = get_campaign_lock(campaign_id)
    if lock.locked():
        logger.warning("Campaign %s dispatch loop already running. Skipping duplicate invocation.", campaign_id)
        return

    async with lock:
        camp = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
        if not camp:
            logger.error("Campaign %s not found for execution", campaign_id)
            return

        # Mark RUNNING status
        now_utc = datetime.now(timezone.utc)
        await db.campaigns.update_one(
            {"_id": ObjectId(campaign_id)},
            {"$set": {"status": "RUNNING", "launched_at": camp.get("launched_at") or now_utc, "updated_at": now_utc}},
        )

        cfg_doc = await db.campaign_configs.find_one({
            "campaign_id": campaign_id,
            "channel": "voice",
            "version": camp.get("config_version", 1),
        })
        v_config = cfg_doc.get("config", {}) if cfg_doc else {}
        bank_name = current_user.get("tenant_name", "Gnani Bank")
        delay = delay_seconds if delay_seconds is not None else settings.campaign_dispatch_delay_seconds
        limit_concurrent = max_concurrency or settings.campaign_max_concurrent

        semaphore = asyncio.Semaphore(limit_concurrent)

        # 1. Fetch pending recipients
        cursor = db.campaign_recipients.find({
            "campaign_id": campaign_id,
            "tenant_id": tenant_id,
            "status": "PENDING",
        })
        recipients = await cursor.to_list(length=2000)

        # 2. Prioritize dialable unblocked leads first, then highest ML match score
        coll = db.leads if camp.get("entity_type") == "lead" else db.customers
        eids = [r.get("entity_id") or str(r.get("_id")) for r in recipients]
        id_objs = [ObjectId(e) if ObjectId.is_valid(e) else e for e in eids]
        ent_map = {str(e["_id"]): e async for e in coll.find(build_tenant_query(tenant_id, {"_id": {"$in": id_objs}}))}

        def get_prio(r: Dict[str, Any]) -> tuple[int, float]:
            eid = str(r.get("entity_id") or r.get("recipient_id") or r.get("_id"))
            ent = ent_map.get(eid, {})
            phone = (ent.get("phone") or "").strip()
            is_dialable = 0 if (phone and not is_fake_seeded_number(phone) and ent.get("consent") is True and not ent.get("dnd")) else 1
            return (is_dialable, -float(r.get("match_score", 0.0)))

        recipients.sort(key=get_prio)
        logger.info("Executing campaign %s: %d pending recipients sorted by priority", campaign_id, len(recipients))

        for rcpt in recipients:
            # Check if campaign was paused or cancelled before each call
            cur_camp = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
            if not cur_camp or cur_camp.get("status") not in ("RUNNING", "LAUNCHING", "ACTIVE"):
                logger.info(
                    "Campaign %s dispatch halted: status is %s",
                    campaign_id,
                    cur_camp.get("status") if cur_camp else "None",
                )
                break

            # Pacing delay
            if delay > 0:
                await asyncio.sleep(delay)

            # Acquire concurrency slot
            async with semaphore:
                attempt_num = int(rcpt.get("attempts", 0)) + 1
                eid = str(rcpt.get("entity_id") or rcpt.get("recipient_id") or rcpt.get("_id"))
                etype = str(rcpt.get("entity_type") or camp.get("entity_type") or "lead")
                try:
                    # Build mapped variables
                    vars_map = map_campaign_voice_variables(v_config, rcpt, camp.get("product_name", "Loan"), bank_name)
                    idempotency_key = f"{campaign_id}:{eid}:{attempt_num}"

                    send_req = CommunicationSendRequest(
                        channel="voice",
                        recipient_ref=RecipientRef(type=etype, id=eid),
                        content=CommunicationContent(language=rcpt.get("language") or "telugu", variables=vars_map),
                        campaign_id=campaign_id,
                        config_version=camp.get("config_version", 1),
                        idempotency_key=idempotency_key,
                        metadata={
                            "campaign_id": campaign_id,
                            "recipient_id": eid,
                            "attempt_number": str(attempt_num),
                            "test_run_label": camp.get("test_run_label"),
                        },
                    )

                    status_code, data = await dispatch_communication(
                        db, send_req, current_user, voice_provider=voice_provider,
                    )
                    now_call_utc = datetime.now(timezone.utc)
                    comm_stat = data.get("status", "DISPATCHED")
                    new_r_stat = "BLOCKED" if comm_stat == "BLOCKED" else ("CALLING" if comm_stat == "DISPATCHED" else "FAILED")

                    await db.campaign_recipients.update_one(
                        {"_id": rcpt["_id"]},
                        {"$set": {
                            "status": new_r_stat,
                            "blocked_reason": data.get("blocked_reason"),
                            "last_communication_id": data.get("communication_id"),
                            "attempts": attempt_num,
                            "last_contact_at": now_call_utc,
                            "updated_at": now_call_utc,
                        }},
                    )
                except Exception as exc:
                    logger.error("Error dispatching communication for recipient %s: %s", eid, exc)
                    await db.campaign_recipients.update_one(
                        {"_id": rcpt["_id"]},
                        {"$set": {
                            "status": "FAILED",
                            "blocked_reason": str(exc),
                            "attempts": attempt_num,
                            "updated_at": datetime.now(timezone.utc),
                        }},
                    )

        # Final reconciliation of statuses
        await refresh_recipient_statuses(db, campaign_id, tenant_id)

