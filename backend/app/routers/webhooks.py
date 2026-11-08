"""Webhooks router for receiving and handling voice telephony event callbacks."""

from datetime import datetime, timezone
import json
import logging
from typing import Any
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from app.core.config import settings
from app.core.db import get_db
from app.providers.twilio_webhook_mapper import can_transition_twilio, map_twilio_status_webhook

try:
    from twilio.request_validator import RequestValidator
except ImportError:
    RequestValidator = None  # type: ignore

logger = logging.getLogger("tara.webhooks")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/twilio/status")
async def handle_twilio_status_webhook(
    request: Request,
    x_twilio_signature: str | None = Header(None, alias="X-Twilio-Signature"),
) -> Response:
    """
    Public webhook receiver for Twilio call status callbacks.

    Normalizes call status (queued, ringing, in-progress, completed, busy, no-answer),
    validates monotonic state progression, and updates matching communication record.
    """
    # 1. Parse payload (Twilio posts application/x-www-form-urlencoded)
    content_type = request.headers.get("content-type", "")
    raw_payload: dict[str, Any] = {}
    if "application/x-www-form-urlencoded" in content_type:
        form_data = await request.form()
        raw_payload = dict(form_data)
    else:
        try:
            body_bytes = await request.body()
            if body_bytes:
                raw_payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            raw_payload = {}

    # 2. Twilio Signature Verification (when configured and not in permissive test mode)
    if settings.twilio_auth_token and RequestValidator and not settings.test_mode:
        validator = RequestValidator(settings.twilio_auth_token)
        url = str(request.url)
        if not x_twilio_signature or not validator.validate(url, raw_payload, x_twilio_signature):
            logger.warning("Twilio signature validation failed for URL: %s", url)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Twilio signature",
            )

    # 3. Map status data
    mapped_data, unmapped_keys = map_twilio_status_webhook(raw_payload)
    call_sid = mapped_data.get("provider_ref")

    now_utc = datetime.now(timezone.utc)
    db = get_db()

    # 4. Search matching communication record
    matching_comm = None
    if call_sid:
        matching_comm = await db.communications.find_one({"provider_ref": call_sid})

    matched_comm_id = str(matching_comm["_id"]) if matching_comm else None

    # 5. Persist raw event in webhook_events collection
    event_doc = {
        "received_at": now_utc,
        "provider": "twilio",
        "provider_ref": call_sid,
        "raw": raw_payload,
        "matched_communication_id": matched_comm_id,
    }
    await db.webhook_events.insert_one(event_doc)

    if not matching_comm:
        logger.info("Stored unmatched Twilio webhook event (CallSid: %s)", call_sid)
        return Response(content="<Response/>", media_type="text/xml")

    # 6. Apply updates respecting monotonic state transitions
    current_status = matching_comm.get("status")
    new_status = mapped_data.get("normalized_status")

    update_fields: dict[str, Any] = {"updated_at": now_utc}
    if new_status and can_transition_twilio(current_status, new_status):
        update_fields["status"] = new_status
        if new_status in ("COMPLETED", "FAILED", "BUSY", "NO_ANSWER", "CANCELED"):
            update_fields["completed_at"] = now_utc

    if mapped_data.get("provider_status"):
        update_fields["provider_status"] = mapped_data["provider_status"]

    duration = mapped_data.get("duration_seconds")
    if duration:
        existing_outcome = matching_comm.get("outcome") or {}
        existing_outcome["duration_seconds"] = duration
        update_fields["outcome"] = existing_outcome

    await db.communications.update_one({"_id": matching_comm["_id"]}, {"$set": update_fields})

    # 7. Write audit log
    await db.audit_log.insert_one({
        "tenant_id": matching_comm["tenant_id"],
        "actor_user_id": "twilio_webhook",
        "action": "webhook_applied",
        "entity_type": "communication",
        "entity_id": matched_comm_id,
        "detail": {
            "status_from": current_status,
            "status_to": update_fields.get("status", current_status),
            "unmapped_keys": unmapped_keys,
        },
        "at": now_utc,
    })

    # 8. Reconcile campaign recipient status if associated with an active campaign
    camp_id = matching_comm.get("campaign_id")
    if camp_id:
        try:
            from app.services.campaign_execution import refresh_recipient_statuses
            await refresh_recipient_statuses(db, camp_id, matching_comm["tenant_id"])
        except Exception as exc:
            logger.debug("Failed refreshing campaign recipients after webhook: %s", exc)

    return Response(content="<Response/>", media_type="text/xml")
