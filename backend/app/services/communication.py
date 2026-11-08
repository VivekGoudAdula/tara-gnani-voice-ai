"""Communication orchestration service for dispatch, compliance, persistence, and reconciliation."""

from datetime import datetime, timezone
import logging
from typing import Any
from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.db import build_tenant_query, doc_to_dict
from app.core.security import mask_phone
from app.providers.base import CommunicationProvider, ProviderRequest
from app.providers.stubs import EmailProvider, SMSProvider, WhatsAppProvider
from app.providers.twilio_voice import TwilioVoiceProvider
from app.providers.twilio_webhook_mapper import can_transition_twilio, map_twilio_status_webhook
from app.schemas.communication import CommunicationSendRequest
from app.services.compliance import evaluate_compliance
from app.services.rendering import render_data_dict

logger = logging.getLogger("tara.services.communication")


def build_comm_doc(
    req: CommunicationSendRequest, tid: str, uid: str, masked: str, stat: str, now: datetime, **kw: Any,
) -> dict[str, Any]:
    """Helper to construct standardized communication document."""
    meta = req.metadata or {}
    test_run_label = meta.get("test_run_label")
    return {
        "tenant_id": tid, "channel": req.channel, "recipient_type": req.recipient_ref.type,
        "recipient_id": req.recipient_ref.id, "phone_masked": masked, "campaign_id": req.campaign_id,
        "config_version": req.config_version, "idempotency_key": req.idempotency_key, "status": stat,
        "provider": kw.get("provider"), "provider_ref": kw.get("provider_ref"), "provider_status": None,
        "blocked_reason": kw.get("blocked_reason"), "error": kw.get("error"),
        "request_variables": req.content.variables, "provider_response_raw": kw.get("provider_response_raw"),
        "outcome": None, "created_by": uid, "created_at": now, "dispatched_at": now if stat == "DISPATCHED" else None,
        "completed_at": None, "updated_at": now,
        "metadata": meta, "test_run_label": test_run_label,
    }


async def resolve_recipient(db: AsyncIOMotorDatabase, tid: str, rtype: str, rid: str) -> dict[str, Any]:
    """Fetch recipient strictly scoped to caller's tenant. Raise 404 if missing."""
    clean_id = rid.strip()
    target_id = ObjectId(clean_id) if ObjectId.is_valid(clean_id) else clean_id
    doc = await (db.leads if rtype == "lead" else db.customers).find_one(build_tenant_query(tid, {"_id": target_id}))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{rtype.capitalize()} '{rid}' not found")
    return doc_to_dict(doc)  # type: ignore[return-value]


async def dispatch_communication(
    db: AsyncIOMotorDatabase,
    request: CommunicationSendRequest,
    current_user: dict[str, Any],
    voice_provider: CommunicationProvider | None = None,
    current_time: datetime | None = None,
) -> tuple[int, dict[str, Any]]:
    """Validate recipient, evaluate compliance, render variables, dispatch to provider, and persist."""
    tid, uid = current_user["tenant_id"], current_user["user_id"]

    # 1. Stub providers for unsupported channels (persist nothing, return 501)
    if request.channel in ("whatsapp", "sms", "email"):
        prov = {"whatsapp": WhatsAppProvider(), "sms": SMSProvider(), "email": EmailProvider()}[request.channel]
        res = await prov.send(ProviderRequest(recipient_phone=""))
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=res.error)

    # 2. Idempotency Check
    if request.idempotency_key:
        exist = await db.communications.find_one(build_tenant_query(tid, {"idempotency_key": request.idempotency_key}))
        if exist:
            return status.HTTP_200_OK, {
                "communication_id": str(exist["_id"]), "status": exist.get("status"),
                "blocked_reason": exist.get("blocked_reason"), "provider_ref": exist.get("provider_ref"),
            }

    # 3. Resolve recipient and evaluate compliance
    rcpt = await resolve_recipient(db, tid, request.recipient_ref.type, request.recipient_ref.id)
    comp = await evaluate_compliance(rcpt, tid, db, current_time)
    now_utc = current_time or datetime.now(timezone.utc)
    masked = mask_phone(rcpt.get("phone", ""))

    if not comp.allowed:
        doc = build_comm_doc(request, tid, uid, masked, "BLOCKED", now_utc, blocked_reason=comp.blocked_reason)
        cid = str((await db.communications.insert_one(doc)).inserted_id)
        await db.audit_log.insert_one({"tenant_id": tid, "actor_user_id": uid, "action": "blocked", "entity_type": "communication", "entity_id": cid, "detail": {"blocked_reason": comp.blocked_reason}, "at": now_utc})
        return status.HTTP_200_OK, {"communication_id": cid, "status": "BLOCKED", "blocked_reason": comp.blocked_reason, "provider_ref": None}

    # 4. Resolve and render variables
    rvars = dict(request.content.variables)
    rvars["customer_name"] = rcpt.get("name", "")
    rvars["language"] = request.content.language or rcpt.get("language", "telugu")
    rvars.setdefault("bank_name", current_user.get("tenant_name", "Test Bank"))
    rendered = render_data_dict(rvars, rvars)

    # 5. Provider Dispatch
    prov_inst: CommunicationProvider = voice_provider if voice_provider else TwilioVoiceProvider()

    # Pre-generate communication ObjectId so ID is attached to call stream metadata
    pre_comm_id = ObjectId()

    # Pass metadata with communication context for stream parameters
    dispatch_metadata = dict(request.metadata or {})
    dispatch_metadata["communication_id"] = str(pre_comm_id)
    dispatch_metadata["tenant_id"] = tid
    dispatch_metadata["campaign_id"] = request.campaign_id or ""

    pres = await prov_inst.send(ProviderRequest(
        recipient_phone=rcpt["phone"],
        variables={str(k): str(v) for k, v in rendered.items()},
        metadata=dispatch_metadata,
    ))

    if not pres.success:
        fdoc = build_comm_doc(request, tid, uid, masked, "FAILED", now_utc, provider=prov_inst.name, provider_ref=pres.provider_ref, error=pres.error, provider_response_raw=pres.raw_response)
        fdoc["_id"] = pre_comm_id
        cid = str((await db.communications.insert_one(fdoc)).inserted_id)
        await db.audit_log.insert_one({"tenant_id": tid, "actor_user_id": uid, "action": "failed", "entity_type": "communication", "entity_id": cid, "detail": {"error": pres.error}, "at": now_utc})
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"communication_id": cid, "status": "FAILED", "error": pres.error, "provider_ref": pres.provider_ref})

    # 6. Success Persistence & Webhook Reconciliation
    sdoc = build_comm_doc(request, tid, uid, masked, "DISPATCHED", now_utc, provider=prov_inst.name, provider_ref=pres.provider_ref, provider_response_raw=pres.raw_response)
    sdoc["_id"] = pre_comm_id
    cid = str((await db.communications.insert_one(sdoc)).inserted_id)

    await db.audit_log.insert_one({"tenant_id": tid, "actor_user_id": uid, "action": "send", "entity_type": "communication", "entity_id": cid, "detail": {"provider_ref": pres.provider_ref}, "at": now_utc})

    if pres.provider_ref:
        await reconcile_unmatched_webhook(db, cid, pres.provider_ref, tid)

    return status.HTTP_202_ACCEPTED, {"communication_id": cid, "status": "DISPATCHED", "blocked_reason": None, "provider_ref": pres.provider_ref}


async def reconcile_unmatched_webhook(db: AsyncIOMotorDatabase, cid: str, pref: str, tid: str) -> None:
    """Check if an unmatched webhook event arrived prior to provider_ref persistence."""
    event = await db.webhook_events.find_one({"provider_ref": pref, "matched_communication_id": None})
    if not event:
        return
    mapped, _ = map_twilio_status_webhook(event.get("raw", {}))
    up: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if mapped.get("normalized_status") and can_transition_twilio("DISPATCHED", mapped["normalized_status"]):
        up["status"] = mapped["normalized_status"]
    if mapped.get("provider_status"):
        up["provider_status"] = mapped["provider_status"]
    if mapped.get("outcome"):
        up["outcome"] = mapped["outcome"]

    await db.communications.update_one({"_id": ObjectId(cid)}, {"$set": up})
    await db.webhook_events.update_one({"_id": event["_id"]}, {"$set": {"matched_communication_id": cid}})
    await db.audit_log.insert_one({
        "tenant_id": tid, "actor_user_id": "system_webhook_reconciliation", "action": "webhook_applied",
        "entity_type": "communication", "entity_id": cid, "detail": {"provider_ref": pref, "reconciled": True}, "at": datetime.now(timezone.utc),
    })
