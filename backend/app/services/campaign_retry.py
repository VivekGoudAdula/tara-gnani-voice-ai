"""Retry policies and transient failure management for TARA 2.0 outbound voice campaigns.

Enforces strict compliance guarantees:
- Retries ONLY transient network, no-answer, or busy states.
- STRICTLY EXCLUDES customer opt-outs, DND, explicit rejections, or compliance blocks.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.campaigns import CampaignRetryQueueItem, CampaignRetriesResponse

logger = logging.getLogger("tara.services.campaign_retry")

# Outcomes eligible for automated or manual retry
RETRYABLE_STATUSES = {"NO_ANSWER", "BUSY", "FAILED"}

# Outcomes permanently terminal that must NEVER be retried
NON_RETRYABLE_STATUSES = {
    "INTERESTED",
    "QUALIFIED",
    "CALLBACK",
    "CALLBACK_SCHEDULED",
    "NOT_INTERESTED",
    "DO_NOT_CALL",
    "BLOCKED",
    "COMPLETED",
}

NON_RETRYABLE_BLOCKED_REASONS = {
    "dnd",
    "no_consent",
    "invalid_phone",
    "non_dialable_number",
    "test_mode_not_allowlisted",
}


def is_eligible_for_retry(
    recipient: Dict[str, Any],
    max_attempts: int = 2,
) -> bool:
    """
    Evaluate whether a recipient may be retried.

    Guarantees:
    - Never retries if attempts >= max_attempts.
    - Never retries if status is terminal/non-retryable.
    - Never retries if blocked by permanent compliance reason (DND, no consent, invalid phone).
    """
    attempts = int(recipient.get("attempts", 0))
    if attempts >= max_attempts:
        return False

    status = (recipient.get("status") or "").upper().strip()
    if status in NON_RETRYABLE_STATUSES:
        return False

    blocked_reason = recipient.get("blocked_reason")
    if blocked_reason and blocked_reason in NON_RETRYABLE_BLOCKED_REASONS:
        return False

    return status in RETRYABLE_STATUSES


def calculate_next_retry_at(
    attempt: int,
    base_interval_minutes: int = 60,
    last_contact_at: Optional[datetime] = None,
) -> datetime:
    """
    Calculate next scheduled retry timestamp using exponential backoff.

    Formula: last_contact + interval * (2 ** (attempt - 1))
    """
    ref_time = last_contact_at or datetime.now(timezone.utc)
    if ref_time.tzinfo is None:
        ref_time = ref_time.replace(tzinfo=timezone.utc)

    backoff_multiplier = 2 ** max(0, attempt - 1)
    delay_minutes = base_interval_minutes * backoff_multiplier
    return ref_time + timedelta(minutes=delay_minutes)


async def get_campaign_retry_queue(
    db: AsyncIOMotorDatabase,
    campaign_id: str,
    tenant_id: str,
    max_attempts: int = 2,
    base_interval_minutes: int = 60,
) -> CampaignRetriesResponse:
    """
    Fetch the list of campaign recipients in retryable state or currently queued for retries.
    """
    cursor = db.campaign_recipients.find({
        "campaign_id": campaign_id,
        "tenant_id": tenant_id,
        "status": {"$in": ["NO_ANSWER", "BUSY", "FAILED", "PENDING"]},
    })

    items: List[CampaignRetryQueueItem] = []
    async for r in cursor:
        attempts = int(r.get("attempts", 0))
        # Only list if it has been attempted at least once, or is currently pending retry
        if attempts == 0 and r.get("status") == "PENDING":
            continue

        eligible = is_eligible_for_retry(r, max_attempts)
        last_contact = r.get("last_contact_at")
        next_retry = None
        if eligible and last_contact:
            next_retry = calculate_next_retry_at(attempts, base_interval_minutes, last_contact)

        # Mask phone if available
        phone_masked = r.get("phone_masked", "+919*******00")

        items.append(CampaignRetryQueueItem(
            recipient_id=r.get("entity_id", ""),
            name=r.get("name", "Unknown"),
            phone_masked=phone_masked,
            attempts=attempts,
            max_attempts=max_attempts,
            last_attempt_at=last_contact,
            next_retry_at=next_retry,
            failure_reason=r.get("blocked_reason") or r.get("status"),
            eligible_for_retry=eligible,
        ))

    return CampaignRetriesResponse(
        campaign_id=campaign_id,
        total_in_queue=len(items),
        max_attempts_configured=max_attempts,
        items=items,
    )


async def queue_campaign_retries(
    db: AsyncIOMotorDatabase,
    campaign_id: str,
    tenant_id: str,
    max_attempts: int = 2,
) -> int:
    """
    Reset retry-eligible recipients back to PENDING status so they can be dispatched.
    Ensures that opt-out, DND, and max-attempt recipients are never touched.
    """
    now_utc = datetime.now(timezone.utc)
    res = await db.campaign_recipients.update_many(
        {
            "campaign_id": campaign_id,
            "tenant_id": tenant_id,
            "status": {"$in": ["NO_ANSWER", "BUSY", "FAILED"]},
            "attempts": {"$lt": max_attempts},
            "blocked_reason": {"$nin": list(NON_RETRYABLE_BLOCKED_REASONS)},
        },
        {"$set": {"status": "PENDING", "updated_at": now_utc}},
    )
    logger.info(
        "Queued %d recipients for retry in campaign %s (tenant %s)",
        res.modified_count,
        campaign_id,
        tenant_id,
    )
    return res.modified_count

