"""Unit tests for Twilio webhook mapping and monotonic status transitions."""

from app.providers.twilio_webhook_mapper import (
    can_transition_twilio,
    map_twilio_status_webhook,
    TWILIO_STATUS_MAP,
)


def test_twilio_status_mappings():
    """Verify all Twilio CallStatus values map to canonical TARA statuses."""
    assert TWILIO_STATUS_MAP["queued"] == "DISPATCHED"
    assert TWILIO_STATUS_MAP["initiated"] == "DISPATCHED"
    assert TWILIO_STATUS_MAP["ringing"] == "DISPATCHED"
    assert TWILIO_STATUS_MAP["in-progress"] == "IN_PROGRESS"
    assert TWILIO_STATUS_MAP["completed"] == "COMPLETED"
    assert TWILIO_STATUS_MAP["busy"] == "BUSY"
    assert TWILIO_STATUS_MAP["no-answer"] == "NO_ANSWER"
    assert TWILIO_STATUS_MAP["failed"] == "FAILED"
    assert TWILIO_STATUS_MAP["canceled"] == "CANCELED"


def test_map_twilio_status_webhook():
    """Verify payload normalization extracts CallSid, duration, phone numbers, and status."""
    raw_payload = {
        "CallSid": "CA1234567890abcdef1234567890abcdef",
        "CallStatus": "completed",
        "CallDuration": "45",
        "To": "+919876543210",
        "From": "+19378064456",
        "RecordingUrl": "https://api.twilio.com/recordings/RE123",
        "CustomExtra": "some_extra_data",
    }
    mapped, unmapped = map_twilio_status_webhook(raw_payload)

    assert mapped["provider"] == "twilio"
    assert mapped["provider_ref"] == "CA1234567890abcdef1234567890abcdef"
    assert mapped["provider_status"] == "completed"
    assert mapped["normalized_status"] == "COMPLETED"
    assert mapped["duration_seconds"] == 45
    assert mapped["recipient_phone"] == "+919876543210"
    assert mapped["from_phone"] == "+19378064456"
    assert mapped["recording_url"] == "https://api.twilio.com/recordings/RE123"
    assert "CustomExtra" in unmapped


def test_monotonic_state_transitions():
    """Verify forward progression is allowed and terminal states cannot be overridden."""
    # Dispatched can advance
    assert can_transition_twilio("DISPATCHED", "IN_PROGRESS") is True
    assert can_transition_twilio("DISPATCHED", "COMPLETED") is True
    assert can_transition_twilio("DISPATCHED", "BUSY") is True
    assert can_transition_twilio("DISPATCHED", "FAILED") is True

    # In-progress can complete or fail
    assert can_transition_twilio("IN_PROGRESS", "COMPLETED") is True
    assert can_transition_twilio("IN_PROGRESS", "FAILED") is True

    # Same state is idempotent
    assert can_transition_twilio("IN_PROGRESS", "IN_PROGRESS") is True
    assert can_transition_twilio("COMPLETED", "COMPLETED") is True

    # Terminal states CANNOT regress
    assert can_transition_twilio("COMPLETED", "IN_PROGRESS") is False
    assert can_transition_twilio("COMPLETED", "DISPATCHED") is False
    assert can_transition_twilio("FAILED", "IN_PROGRESS") is False
    assert can_transition_twilio("BUSY", "IN_PROGRESS") is False
    assert can_transition_twilio("NO_ANSWER", "DISPATCHED") is False
    assert can_transition_twilio("CANCELED", "IN_PROGRESS") is False

