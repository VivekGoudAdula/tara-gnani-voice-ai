"""Service for retrieving paginated call logs and detailed call timelines."""

from datetime import datetime
from typing import Any
from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.db import build_tenant_query, doc_to_dict
from app.core.security import mask_phone
from app.schemas.communication import CommunicationOutcome
from app.schemas.outcomes import OutcomesCallDetail, OutcomesCallItem, TimelineEvent
from app.services.outcomes import build_outcomes_filter


async def list_outcomes_calls(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    campaign_id: str | None = None,
    test_run_label: str | None = None,
    channel: str | None = None,
    status_filter: str | None = None,
    outcome: str | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[OutcomesCallItem], int]:
    """Retrieve filtered, paginated communication calls with resolved names."""
    query = build_outcomes_filter(
        tenant_id, campaign_id, test_run_label, channel,
        status=status_filter, outcome=outcome, date_from=date_from, date_to=date_to,
    )

    if search:
        s_clean = search.strip()
        query["$or"] = [
            {"phone_masked": {"$regex": s_clean, "$options": "i"}},
            {"request_variables.customer_name": {"$regex": s_clean, "$options": "i"}},
            {"test_run_label": {"$regex": s_clean, "$options": "i"}},
        ]

    total = await db.communications.count_documents(query)
    skip = (page - 1) * page_size
    cursor = db.communications.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    raw_comms = await cursor.to_list(length=page_size)

    # Batch resolve recipient names and campaign names
    lead_ids = [ObjectId(c["recipient_id"]) for c in raw_comms if c.get("recipient_type") == "lead" and ObjectId.is_valid(c.get("recipient_id"))]
    cust_ids = [ObjectId(c["recipient_id"]) for c in raw_comms if c.get("recipient_type") == "customer" and ObjectId.is_valid(c.get("recipient_id"))]
    camp_ids = [ObjectId(c["campaign_id"]) for c in raw_comms if c.get("campaign_id") and ObjectId.is_valid(c["campaign_id"])]

    lead_map = {str(d["_id"]): d.get("name") async for d in db.leads.find(build_tenant_query(tenant_id, {"_id": {"$in": lead_ids}}))}
    cust_map = {str(d["_id"]): d.get("name") async for d in db.customers.find(build_tenant_query(tenant_id, {"_id": {"$in": cust_ids}}))}
    camp_map = {str(d["_id"]): d.get("name") async for d in db.campaigns.find(build_tenant_query(tenant_id, {"_id": {"$in": camp_ids}}))}

    items: list[OutcomesCallItem] = []
    for c in raw_comms:
        rid = str(c.get("recipient_id", ""))
        rtype = c.get("recipient_type", "lead")
        rname = (lead_map.get(rid) if rtype == "lead" else cust_map.get(rid)) or c.get("request_variables", {}).get("customer_name") or "Recipient"
        camp_name = camp_map.get(str(c.get("campaign_id", "")))

        out = c.get("outcome") or {}
        outcome_obj = CommunicationOutcome(**out) if out else None
        dur = out.get("duration_seconds")
        lang = out.get("language_used") or c.get("request_variables", {}).get("language")

        items.append(OutcomesCallItem(
            id=str(c["_id"]), recipient_name=rname, phone_masked=c.get("phone_masked") or mask_phone(""),
            campaign_id=c.get("campaign_id"), campaign_name=camp_name,
            test_run_label=c.get("test_run_label") or c.get("metadata", {}).get("test_run_label"),
            status=c.get("status", "UNKNOWN"), outcome=outcome_obj, duration_seconds=float(dur) if dur is not None else None,
            language_used=lang, created_at=c.get("created_at"),
        ))

    return items, total


async def get_outcomes_call_detail(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    comm_id: str,
    is_super_admin: bool = False,
) -> OutcomesCallDetail:
    """Retrieve complete communication details and reconstruct audit timeline."""
    if not ObjectId.is_valid(comm_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Communication record not found")

    comm = await db.communications.find_one(build_tenant_query(tenant_id, {"_id": ObjectId(comm_id)}))
    if not comm:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Communication record not found")

    # Resolve recipient name and campaign name
    rid, rtype = comm.get("recipient_id"), comm.get("recipient_type", "lead")
    rname = comm.get("request_variables", {}).get("customer_name") or "Recipient"
    if rid and ObjectId.is_valid(rid):
        coll = db.leads if rtype == "lead" else db.customers
        ent = await coll.find_one(build_tenant_query(tenant_id, {"_id": ObjectId(rid)}))
        if ent:
            rname = ent.get("name", rname)

    camp_name = None
    if comm.get("campaign_id") and ObjectId.is_valid(comm["campaign_id"]):
        camp = await db.campaigns.find_one(build_tenant_query(tenant_id, {"_id": ObjectId(comm["campaign_id"])}))
        if camp:
            camp_name = camp.get("name")

    # Reconstruct chronological timeline
    timeline: list[TimelineEvent] = []
    if comm.get("created_at"):
        timeline.append(TimelineEvent(event="initiated", timestamp=comm["created_at"], source="system", detail={"channel": comm.get("channel")}))
    if comm.get("status") == "BLOCKED":
        timeline.append(TimelineEvent(event="blocked", timestamp=comm.get("created_at"), source="compliance_gate", detail={"reason": comm.get("blocked_reason")}))
    elif comm.get("dispatched_at"):
        timeline.append(TimelineEvent(event="dispatched", timestamp=comm["dispatched_at"], source="provider_adapter", detail={"provider": comm.get("provider")}))

    # Webhook events matched to this communication
    wh_events: list[dict[str, Any]] = []
    cursor = db.webhook_events.find(build_tenant_query(tenant_id, {
        "$or": [{"matched_communication_id": comm_id}, {"provider_ref": comm.get("provider_ref")}],
    })).sort("received_at", 1)
    async for ev in cursor:
        wh_events.append(ev)
        raw_p = ev.get("raw", {})
        ev_type = str(raw_p.get("status") or raw_p.get("event") or "webhook_event").lower()
        timeline.append(TimelineEvent(event=ev_type, timestamp=ev.get("received_at"), source="webhook", detail={"provider_ref": ev.get("provider_ref")}))

    if comm.get("completed_at") and not any(t.event == "completed" for t in timeline):
        timeline.append(TimelineEvent(event="completed", timestamp=comm["completed_at"], source="system"))

    # Sort timeline by timestamp
    timeline.sort(key=lambda t: t.timestamp if isinstance(t.timestamp, datetime) else datetime.min)

    # Outcomes & Extractions
    out = comm.get("outcome") or {}
    outcome_obj = CommunicationOutcome(**out) if out else None
    extractions = {
        k: out.get(k) for k in ("interest_level", "preferred_amount", "preferred_callback_time", "language_used") if out.get(k) is not None
    }

    # Technical details restricted to SUPER_ADMIN
    tech_details = None
    if is_super_admin:
        tech_details = {
            "provider_response_raw": comm.get("provider_response_raw"),
            "webhook_payloads": [doc_to_dict(w.get("raw", {})) for w in wh_events],
            "request_variables": comm.get("request_variables"),
        }

    return OutcomesCallDetail(
        id=str(comm["_id"]), tenant_id=tenant_id, campaign_id=comm.get("campaign_id"),
        campaign_name=camp_name, recipient_name=rname, phone_masked=comm.get("phone_masked") or mask_phone(""),
        status=comm.get("status", "UNKNOWN"), timeline=timeline, outcome=outcome_obj,
        transcript=out.get("transcript"), extracted_data=extractions, provider_status=comm.get("provider_status"),
        hangup_reason=out.get("hangup_reason"), config_version=comm.get("config_version"),
        blocked_reason=comm.get("blocked_reason"), error=comm.get("error"),
        test_run_label=comm.get("test_run_label") or comm.get("metadata", {}).get("test_run_label"),
        technical_details=tech_details,
    )
