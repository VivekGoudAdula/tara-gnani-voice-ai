"""Twilio status callback payload mapper and state transition validator."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("tara.providers.twilio_mapper")

# Canonical monotonic state transitions: terminal states cannot be overwritten
VALID_TRANSITIONS: Dict[str, set[str]] = {
    "DISPATCHED": {"DISPATCHED", "IN_PROGRESS", "COMPLETED", "FAILED", "BUSY", "NO_ANSWER", "CANCELED"},
    "IN_PROGRESS": {"IN_PROGRESS", "COMPLETED", "FAILED", "BUSY", "NO_ANSWER", "CANCELED"},
    "COMPLETED": set(),  # Terminal state
    "FAILED": set(),     # Terminal state
    "BUSY": set(),       # Terminal state
    "NO_ANSWER": set(),   # Terminal state
    "CANCELED": set(),    # Terminal state
}

# Twilio CallStatus mapping to TARA normalized status
TWILIO_STATUS_MAP: Dict[str, str] = {
    "queued": "DISPATCHED",
    "initiated": "DISPATCHED",
    "ringing": "DISPATCHED",
    "in-progress": "IN_PROGRESS",
    "completed": "COMPLETED",
    "busy": "BUSY",
    "no-answer": "NO_ANSWER",
    "failed": "FAILED",
    "canceled": "CANCELED",
}


def can_transition_twilio(current_status: Optional[str], target_status: Optional[str]) -> bool:
    """
    Check if state transition is allowed under monotonic progress rules.

    Args:
        current_status: Existing communication status.
        target_status: Candidate new status.

    Returns:
        Boolean indicating whether the transition is valid.
    """
    if not current_status or not target_status:
        return True
    if current_status == target_status:
        return True
    allowed = VALID_TRANSITIONS.get(current_status, set())
    return target_status in allowed


def map_twilio_status_webhook(raw_payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Normalize Twilio call status callback form/JSON data into standardized TARA fields.

    Args:
        raw_payload: Raw dictionary received from Twilio webhook.

    Returns:
        Tuple of (mapped_data_dict, unmapped_data_dict).
    """
    call_sid = raw_payload.get("CallSid") or raw_payload.get("call_sid")
    raw_status = (raw_payload.get("CallStatus") or raw_payload.get("call_status") or "").lower()
    normalized_status = TWILIO_STATUS_MAP.get(raw_status, "DISPATCHED")

    duration_raw = raw_payload.get("CallDuration") or raw_payload.get("Duration") or 0
    try:
        duration_seconds = int(duration_raw)
    except (ValueError, TypeError):
        duration_seconds = 0

    recipient_phone = raw_payload.get("To") or raw_payload.get("Called") or ""
    from_phone = raw_payload.get("From") or raw_payload.get("Caller") or ""
    recording_url = raw_payload.get("RecordingUrl")

    mapped = {
        "provider": "twilio",
        "provider_ref": call_sid,
        "provider_status": raw_status,
        "normalized_status": normalized_status,
        "duration_seconds": duration_seconds,
        "recipient_phone": recipient_phone,
        "from_phone": from_phone,
        "recording_url": recording_url,
        "timestamp": datetime.now(timezone.utc),
    }

    known_keys = {
        "CallSid", "call_sid", "CallStatus", "call_status", "CallDuration",
        "Duration", "To", "Called", "From", "Caller", "RecordingUrl",
        "AccountSid", "ApiVersion", "Direction",
    }
    unmapped = {k: v for k, v in raw_payload.items() if k not in known_keys}

    return mapped, unmapped

