"""Compliance gate enforcing regulatory and policy dispatch-time checks."""

from datetime import datetime, time, timedelta, timezone
import logging
import re
from typing import Any
from zoneinfo import ZoneInfo
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.security import mask_phone

logger = logging.getLogger("tara.compliance")

E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")
KOLKATA_TZ = ZoneInfo("Asia/Kolkata")


class ComplianceResult:
    """Outcome of compliance evaluation."""

    def __init__(self, allowed: bool, blocked_reason: str | None = None) -> None:
        self.allowed = allowed
        self.blocked_reason = blocked_reason

    def __repr__(self) -> str:
        return f"ComplianceResult(allowed={self.allowed}, blocked_reason={self.blocked_reason})"


def is_e164(phone: str | None) -> bool:
    """Validate E.164 phone number format (+ followed by 2 to 15 digits)."""
    if not phone or not isinstance(phone, str):
        return False
    return bool(E164_REGEX.match(phone.strip()))


def is_fake_seeded_number(phone: str | None) -> bool:
    """Check if phone number is a synthetic seeded number (+9190000...)."""
    if not phone or not isinstance(phone, str):
        return False
    clean = phone.strip()
    return clean.startswith("+9190000")


def parse_time_str(time_str: str) -> time:
    """Parse HH:MM string into datetime.time."""
    parts = time_str.strip().split(":")
    return time(int(parts[0]), int(parts[1]))


def is_within_calling_window(
    check_time: datetime,
    start_str: str = "09:00",
    end_str: str = "21:00",
) -> bool:
    """Check if given datetime in Asia/Kolkata timezone falls within allowed window."""
    kolkata_time = check_time.astimezone(KOLKATA_TZ) if check_time.tzinfo else check_time.replace(tzinfo=KOLKATA_TZ)
    current_time_val = kolkata_time.time()
    start = parse_time_str(start_str)
    end = parse_time_str(end_str)
    return start <= current_time_val < end


async def evaluate_compliance(
    recipient: dict[str, Any],
    tenant_id: str,
    db: AsyncIOMotorDatabase,
    current_time: datetime | None = None,
) -> ComplianceResult:
    """
    Execute 7-step compliance evaluation in strict priority order.

    Returns ComplianceResult indicating whether dispatch is permitted.
    """
    phone = (recipient.get("phone") or "").strip()
    masked = mask_phone(phone)

    # 1. TEST_MODE & Fake Seeded Numbers Check
    if is_fake_seeded_number(phone):
        logger.info("Compliance blocked %s: non_dialable_number", masked)
        return ComplianceResult(allowed=False, blocked_reason="non_dialable_number")

    if settings.test_mode:
        allowlist = {
            num.strip()
            for num in settings.test_allowlist.split(",")
            if num.strip()
        }
        if phone not in allowlist:
            logger.info("Compliance blocked %s: test_mode_not_allowlisted (phone: '%s', allowlist: %s)", masked, phone, list(allowlist))
            return ComplianceResult(allowed=False, blocked_reason="test_mode_not_allowlisted")

    # 2. E.164 Phone Validation
    if not is_e164(phone):
        logger.info("Compliance blocked %s: invalid_phone", masked)
        return ComplianceResult(allowed=False, blocked_reason="invalid_phone")

    # 3. Explicit Consent Check
    if recipient.get("consent") is not True:
        logger.info("Compliance blocked %s: no_consent", masked)
        return ComplianceResult(allowed=False, blocked_reason="no_consent")

    # 4. Do Not Disturb (DND) Check
    if recipient.get("dnd") is True:
        logger.info("Compliance blocked %s: dnd", masked)
        return ComplianceResult(allowed=False, blocked_reason="dnd")

    # Check exemption for developer test numbers (exempt from hours, frequency cap, and duplicate in-flight)
    exempt_raw = f"{settings.compliance_exempt_numbers},{settings.seed_test_phone_1}"
    exempt_numbers = {
        num.strip()
        for num in exempt_raw.split(",")
        if num.strip()
    }
    is_exempt = bool(settings.test_mode and (phone in exempt_numbers))
    if is_exempt:
        logger.info("Compliance: %s is an exempt test number (bypassing window, frequency cap, and in-flight checks)", masked)

    # 5. Calling Window (09:00 - 21:00 IST)
    ref_time = current_time or datetime.now(timezone.utc)
    if not is_exempt and not is_within_calling_window(ref_time, settings.call_window_start, settings.call_window_end):
        logger.info("Compliance blocked %s: outside_calling_hours", masked)
        return ComplianceResult(allowed=False, blocked_reason="outside_calling_hours")

    # Normalize reference time to UTC for database queries
    ref_time_utc = ref_time.astimezone(timezone.utc) if ref_time.tzinfo else ref_time.replace(tzinfo=timezone.utc)
    recipient_id = str(recipient.get("id") or recipient.get("_id"))

    # 6. Frequency Cap (Max count in N days across all channels)
    if settings.compliance_check_frequency_cap and not is_exempt:
        cap_cutoff = ref_time_utc - timedelta(days=settings.contact_cap_days)
        recent_comm_count = await db.communications.count_documents({
            "tenant_id": tenant_id,
            "recipient_id": recipient_id,
            "created_at": {"$gte": cap_cutoff},
            "status": {"$in": ["DISPATCHED", "IN_PROGRESS", "COMPLETED"]},
        })
        if recent_comm_count >= settings.contact_cap_count:
            logger.info(
                "Compliance blocked %s: frequency_cap (%d in %d days)",
                masked,
                recent_comm_count,
                settings.contact_cap_days,
            )
            return ComplianceResult(allowed=False, blocked_reason="frequency_cap")

    # 7. Duplicate In-Flight (Another in-progress communication in last 10 minutes)
    if settings.compliance_check_duplicate_in_flight and not is_exempt:
        inflight_cutoff = ref_time_utc - timedelta(minutes=10)
        inflight_count = await db.communications.count_documents({
            "tenant_id": tenant_id,
            "recipient_id": recipient_id,
            "created_at": {"$gte": inflight_cutoff},
            "status": {"$in": ["DISPATCHED", "IN_PROGRESS"]},
        })
        if inflight_count > 0:
            logger.info("Compliance blocked %s: duplicate_in_flight", masked)
            return ComplianceResult(allowed=False, blocked_reason="duplicate_in_flight")

    # All checks passed
    return ComplianceResult(allowed=True)
