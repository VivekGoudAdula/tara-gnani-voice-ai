"""Service for outcomes aggregation, timeline reconstruction, and calls queries."""

from datetime import datetime, timezone
import math
import statistics
from typing import Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.db import build_tenant_query, doc_to_dict
from app.core.security import mask_phone
from app.schemas.communication import CommunicationOutcome
from app.schemas.outcomes import (
    CostSummary,
    ExtractionFillRate,
    LatencySummary,
    OutcomeCounts,
    OutcomesCallDetail,
    OutcomesCallItem,
    OutcomesSummaryResponse,
    TimelineEvent,
    WebhookDeliverySummary,
)

METRIC_DEFINITIONS: dict[str, str] = {
    "attempted": "Total outbound outreach calls scheduled or initiated.",
    "blocked": "Calls safeguarded by TRAI compliance gates (calling hours, consent, DND, allowlist).",
    "dispatched": "Calls successfully transmitted to the telephony voice provider.",
    "connected": "Calls reaching terminal status COMPLETED with duration_seconds > 0, verifying live audio pickup.",
    "completed": "Calls that successfully concluded their conversation session.",
    "no_answer": "Calls that were unanswered, busy, or timed out at the telephony layer.",
    "failed": "Calls encountering a telephony, network, or provider dispatch failure.",
    "avg_duration_seconds": "Arithmetic mean of conversation duration for connected calls in seconds.",
    "median_duration_seconds": "50th percentile conversation duration for connected calls in seconds.",
    "p95_duration_seconds": "95th percentile conversation duration for connected calls in seconds.",
    "latency": "Round-trip processing latency extracted from provider payloads. Reported unavailable if absent.",
    "cost": "Telephony and compute cost reported directly by provider. Reported unavailable if absent.",
    "extraction_fill_rate": "Percentage of completed calls with structured fields successfully extracted.",
    "webhook_delivery": "Integrity metric comparing received webhook events against terminal communications.",
}


def build_outcomes_filter(
    tenant_id: str,
    campaign_id: str | None = None,
    test_run_label: str | None = None,
    channel: str | None = None,
    status: str | None = None,
    outcome: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    """Construct MongoDB query criteria strictly isolated to tenant with optional filters."""
    crit: dict[str, Any] = {}
    if campaign_id:
        crit["campaign_id"] = campaign_id
    if test_run_label:
        crit["$or"] = [{"test_run_label": test_run_label}, {"metadata.test_run_label": test_run_label}]
    if channel:
        crit["channel"] = channel
    if status:
        crit["status"] = status.upper().strip()
    if outcome:
        clean_out = outcome.lower().strip()
        crit["outcome.interest_level"] = {"$regex": f"^{clean_out}$", "$options": "i"}
    if date_from or date_to:
        date_q: dict[str, Any] = {}
        if date_from:
            date_q["$gte"] = date_from
        if date_to:
            date_q["$lte"] = date_to
        crit["created_at"] = date_q
    return build_tenant_query(tenant_id, crit)


def calculate_p95(vals: list[float]) -> float | None:
    """Compute 95th percentile from a list of numerical values."""
    if not vals:
        return None
    s = sorted(vals)
    idx = math.ceil(0.95 * len(s)) - 1
    return round(float(s[max(0, min(idx, len(s) - 1))]), 2)


async def get_outcomes_summary(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    campaign_id: str | None = None,
    test_run_label: str | None = None,
    channel: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> OutcomesSummaryResponse:
    """Compute exact outcomes metrics and distributions from communications data."""
    query = build_outcomes_filter(tenant_id, campaign_id, test_run_label, channel, date_from=date_from, date_to=date_to)
    cursor = db.communications.find(query)
    comms = await cursor.to_list(length=10000)

    attempted = len(comms)
    blocked, dispatched, completed, no_answer, failed = 0, 0, 0, 0, 0
    dispatched_terminal = 0
    blocked_by_reason: dict[str, int] = {}
    durations: list[float] = []
    latencies: list[float] = []
    costs: list[float] = []
    outcome_counts = OutcomeCounts()
    extractions_count = {"interest_level": 0, "preferred_amount": 0, "preferred_callback_time": 0, "language_used": 0}
    languages: dict[str, int] = {}

    for c in comms:
        st = c.get("status", "")
        if st == "BLOCKED":
            blocked += 1
            r = c.get("blocked_reason") or "unspecified"
            blocked_by_reason[r] = blocked_by_reason.get(r, 0) + 1
        elif st in ("DISPATCHED", "IN_PROGRESS", "COMPLETED", "NO_ANSWER", "BUSY", "FAILED", "CANCELLED"):
            dispatched += 1

        if st in ("COMPLETED", "NO_ANSWER", "BUSY", "FAILED", "CANCELLED"):
            dispatched_terminal += 1

        if st == "COMPLETED":
            completed += 1
        elif st in ("NO_ANSWER", "BUSY"):
            no_answer += 1
        elif st == "FAILED":
            failed += 1

        out = c.get("outcome") or {}
        dur = out.get("duration_seconds")
        if st == "COMPLETED" and dur is not None:
            try:
                fdur = float(dur)
                if fdur > 0:
                    durations.append(fdur)
            except (ValueError, TypeError):
                pass

        # Outcome classification
        ilevel = str(out.get("interest_level") or "").strip()
        ilevel_lower = ilevel.lower()
        if not ilevel or ilevel_lower in ("not detected", "unknown", "none"):
            if st == "COMPLETED":
                outcome_counts.unknown += 1
        elif ilevel_lower == "interested":
            outcome_counts.interested += 1
        elif ilevel_lower == "callback":
            outcome_counts.callback += 1
        elif ilevel_lower == "not_interested":
            outcome_counts.not_interested += 1
        else:
            # Unexpected / raw value -> count under Other / Ambiguous
            outcome_counts.other += 1

        # Extractions tracking (count only if value was actually extracted, not 'Not detected')
        if st == "COMPLETED":
            for field_name in extractions_count:
                val = out.get(field_name)
                if val is not None and str(val).strip() not in ("", "Not detected"):
                    extractions_count[field_name] += 1

        # Language tracking
        lang = out.get("language_used") or c.get("request_variables", {}).get("language")
        if lang:
            languages[str(lang).lower()] = languages.get(str(lang).lower(), 0) + 1

        # Latency & Cost checks
        lat = out.get("latency")
        if isinstance(lat, (int, float)):
            latencies.append(float(lat))
        elif isinstance(lat, dict) and "overall" in lat:
            latencies.append(float(lat["overall"]))

        cost_val = out.get("cost")
        if isinstance(cost_val, (int, float)):
            costs.append(float(cost_val))

    connected = len(durations)
    avg_dur = round(statistics.mean(durations), 2) if durations else None
    med_dur = round(statistics.median(durations), 2) if durations else None
    p95_dur = calculate_p95(durations)

    # Webhook delivery summary
    ev_count = await db.webhook_events.count_documents(build_tenant_query(tenant_id))
    terminal_comms = dispatched_terminal
    missing = max(0, dispatched - dispatched_terminal)

    # Fill rate calculation
    fill_rate = ExtractionFillRate(
        interest_level=round((extractions_count["interest_level"] / completed) * 100.0, 1) if completed else 0.0,
        preferred_amount=round((extractions_count["preferred_amount"] / completed) * 100.0, 1) if completed else 0.0,
        preferred_callback_time=round((extractions_count["preferred_callback_time"] / completed) * 100.0, 1) if completed else 0.0,
        language_used=round((extractions_count["language_used"] / completed) * 100.0, 1) if completed else 0.0,
    )

    latency_summary = LatencySummary(
        available=len(latencies) > 0,
        source="webhook" if len(latencies) > 0 else "none",
        median_ms=round(statistics.median(latencies), 1) if latencies else None,
        p95_ms=calculate_p95(latencies),
        n=len(latencies),
    )

    cost_summary = CostSummary(
        available=len(costs) > 0,
        total=round(sum(costs), 4) if costs else None,
        avg_per_call=round(statistics.mean(costs), 4) if costs else None,
        n=len(costs),
    )

    return OutcomesSummaryResponse(
        attempted=attempted, blocked=blocked, blocked_by_reason=blocked_by_reason,
        dispatched=dispatched, connected=connected, completed=completed, no_answer=no_answer, failed=failed,
        avg_duration_seconds=avg_dur, median_duration_seconds=med_dur, p95_duration_seconds=p95_dur,
        latency=latency_summary, outcome_counts=outcome_counts, extraction_fill_rate=fill_rate,
        webhook_delivery=WebhookDeliverySummary(events_received=ev_count, communications_with_terminal_status=terminal_comms, missing_terminal=missing),
        cost=cost_summary, language_breakdown=languages, definitions=METRIC_DEFINITIONS,
    )
