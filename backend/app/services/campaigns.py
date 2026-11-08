"""Campaign lifecycle management, status derivation, and paced background dispatching."""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne
from app.core.config import settings
from app.core.db import build_tenant_query, doc_to_dict
from app.providers.base import CommunicationProvider
from app.schemas.communication import CommunicationContent, CommunicationSendRequest, RecipientRef
from app.services.campaign_variables import map_campaign_voice_variables
from app.services.communication import dispatch_communication
from app.services.compliance import is_fake_seeded_number

logger = logging.getLogger("tara.services.campaigns")

INTEREST_LEVEL_STATUS_MAP: dict[str, str] = {
    "interested": "INTERESTED",
    "callback": "CALLBACK",
    "not_interested": "NOT_INTERESTED",
}

TERMINAL_STATUSES = {
    "CONTACTED", "INTERESTED", "CALLBACK", "NOT_INTERESTED", "NO_ANSWER", "BLOCKED", "FAILED", "COMPLETED",
}


async def refresh_recipient_statuses(db: AsyncIOMotorDatabase, campaign_id: str, tenant_id: str) -> None:
    """Aggregate latest communications to update recipient statuses in a single batch."""
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

    latest_comms = await db.communications.aggregate(pipeline).to_list(length=1000)
    if not latest_comms:
        return

    bulk_ops: list[UpdateOne] = []
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
            new_stat = INTEREST_LEVEL_STATUS_MAP.get(interest, "CONTACTED")
        else:
            new_stat = "PENDING"

        bulk_ops.append(
            UpdateOne(
                {"campaign_id": campaign_id, "entity_id": rid},
                {"$set": {
                    "status": new_stat,
                    "blocked_reason": blocked_r,
                    "last_communication_id": str(comm["comm_id"]),
                    "last_contact_at": last_contact,
                    "updated_at": now_utc,
                }},
            )
        )

    if bulk_ops:
        await db.campaign_recipients.bulk_write(bulk_ops, ordered=False)

    # Check auto-completion of campaign
    non_terminal_count = await db.campaign_recipients.count_documents({
        "campaign_id": campaign_id,
        "status": {"$in": ["PENDING", "QUEUED", "CALLING"]},
    })
    total_count = await db.campaign_recipients.count_documents({"campaign_id": campaign_id})

    if total_count > 0 and non_terminal_count == 0:
        camp = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
        if camp and camp.get("status") in ("ACTIVE", "LAUNCHING"):
            await db.campaigns.update_one(
                {"_id": ObjectId(campaign_id)},
                {"$set": {"status": "COMPLETED", "completed_at": now_utc, "updated_at": now_utc}},
            )


async def get_campaign_progress(db: AsyncIOMotorDatabase, campaign_id: str, tenant_id: str) -> dict[str, Any]:
    """Retrieve progress metrics and blocked reason breakdown."""
    await refresh_recipient_statuses(db, campaign_id, tenant_id)

    counts_by_status: dict[str, int] = {}
    blocked_reasons: dict[str, int] = {}
    total = 0

    cursor = db.campaign_recipients.find({"campaign_id": campaign_id, "tenant_id": tenant_id})
    async for r in cursor:
        total += 1
        st = r.get("status", "PENDING")
        counts_by_status[st] = counts_by_status.get(st, 0) + 1
        br = r.get("blocked_reason")
        if br:
            blocked_reasons[br] = blocked_reasons.get(br, 0) + 1

    camp = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
    camp_status = camp.get("status", "DRAFT") if camp else "DRAFT"

    return {
        "campaign_id": campaign_id,
        "status": camp_status,
        "total_recipients": total,
        "counts_by_status": counts_by_status,
        "blocked_reasons_breakdown": blocked_reasons,
        "last_updated": datetime.now(timezone.utc),
    }


async def run_campaign_dispatch(
    db: AsyncIOMotorDatabase,
    campaign_id: str,
    tenant_id: str,
    current_user: dict[str, Any],
    voice_provider: CommunicationProvider | None = None,
    delay_seconds: float | None = None,
) -> None:
    """Execute sequential paced outreach dispatch in background."""
    camp = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
    if not camp:
        return

    cfg_doc = await db.campaign_configs.find_one({
        "campaign_id": campaign_id,
        "channel": "voice",
        "version": camp.get("config_version", 1),
    })
    v_config = cfg_doc.get("config", {}) if cfg_doc else {}
    bank_name = current_user.get("tenant_name", "Test Bank")
    delay = delay_seconds if delay_seconds is not None else settings.campaign_dispatch_delay_seconds

    # Query recipients ready for dispatch
    cursor = db.campaign_recipients.find({
        "campaign_id": campaign_id,
        "tenant_id": tenant_id,
        "status": "PENDING",
    })

    recipients = await cursor.to_list(length=1000)

    # Prioritize dialable / unblocked recipients first so real calls happen immediately
    coll = db.leads if camp.get("entity_type") == "lead" else db.customers
    eids = [r.get("entity_id") or str(r.get("_id")) for r in recipients]
    id_objs = [ObjectId(e) if ObjectId.is_valid(e) else e for e in eids]
    ent_map = {str(e["_id"]): e async for e in coll.find(build_tenant_query(tenant_id, {"_id": {"$in": id_objs}}))}

    def get_dispatch_prio(r: dict[str, Any]) -> tuple[int, float]:
        eid = str(r.get("entity_id") or r.get("recipient_id") or r.get("_id"))
        ent = ent_map.get(eid, {})
        phone = (ent.get("phone") or "").strip()
        is_dialable = 0 if (phone and not is_fake_seeded_number(phone) and ent.get("consent") is True and not ent.get("dnd")) else 1
        return (is_dialable, -float(r.get("match_score", 0.0)))

    recipients.sort(key=get_dispatch_prio)

    for rcpt in recipients:
        # Check if campaign paused or cancelled before dispatch
        cur_camp = await db.campaigns.find_one({"_id": ObjectId(campaign_id)})
        if not cur_camp or cur_camp.get("status") not in ("LAUNCHING", "ACTIVE"):
            logger.info("Campaign %s stopped dispatching (status=%s)", campaign_id, cur_camp.get("status") if cur_camp else "None")
            break

        # Concurrency in-flight pacing
        while True:
            in_flight = await db.communications.count_documents({
                "campaign_id": campaign_id,
                "status": {"$in": ["DISPATCHED", "IN_PROGRESS"]},
            })
            if in_flight < settings.campaign_max_concurrent:
                break
            await asyncio.sleep(0.5)

        eid = str(rcpt.get("entity_id") or rcpt.get("recipient_id") or rcpt.get("_id"))
        etype = str(rcpt.get("entity_type") or camp.get("entity_type") or "lead")
        attempt_num = int(rcpt.get("attempts", 0)) + 1
        idempotency_key = f"{campaign_id}:{eid}:{attempt_num}"

        try:
            # Build mapped variables
            vars_map = map_campaign_voice_variables(v_config, rcpt, camp.get("product_name", "Loan"), bank_name)

            send_req = CommunicationSendRequest(
                channel="voice",
                recipient_ref=RecipientRef(type=etype, id=eid),
                content=CommunicationContent(language=rcpt.get("language") or "telugu", variables=vars_map),
                campaign_id=campaign_id,
                config_version=camp.get("config_version", 1),
                idempotency_key=idempotency_key,
                metadata={"test_run_label": camp.get("test_run_label")} if camp.get("test_run_label") else {},
            )

            status_code, data = await dispatch_communication(db, send_req, current_user, voice_provider=voice_provider)
            now_utc = datetime.now(timezone.utc)
            comm_stat = data.get("status", "DISPATCHED")
            new_r_stat = "BLOCKED" if comm_stat == "BLOCKED" else ("CALLING" if comm_stat == "DISPATCHED" else "FAILED")

            await db.campaign_recipients.update_one(
                {"_id": rcpt["_id"]},
                {"$set": {
                    "status": new_r_stat,
                    "blocked_reason": data.get("blocked_reason"),
                    "last_communication_id": data.get("communication_id"),
                    "attempts": attempt_num,
                    "last_contact_at": now_utc,
                    "updated_at": now_utc,
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

        # Respect pacing delay
        if delay > 0:
            await asyncio.sleep(delay)

    await refresh_recipient_statuses(db, campaign_id, tenant_id)
