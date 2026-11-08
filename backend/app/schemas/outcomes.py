"""Pydantic schemas for Outcomes Dashboard, calls listing, and evidence reporting."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.communication import CommunicationOutcome


class LatencySummary(BaseModel):
    """Latency metrics derived honestly from provider data."""

    available: bool = False
    source: Literal["webhook", "telephony_stream", "none"] = "none"
    median_ms: float | None = None
    p95_ms: float | None = None
    n: int = 0


class CostSummary(BaseModel):
    """Cost metrics derived honestly from provider data."""

    available: bool = False
    total: float | None = None
    avg_per_call: float | None = None
    n: int = 0


class OutcomeCounts(BaseModel):
    """Distribution of call outcomes."""

    interested: int = 0
    callback: int = 0
    not_interested: int = 0
    other: int = 0
    unknown: int = 0


class ExtractionFillRate(BaseModel):
    """Percentage of completed calls with extracted fields populated (0.0 to 100.0)."""

    interest_level: float = 0.0
    preferred_amount: float = 0.0
    preferred_callback_time: float = 0.0
    language_used: float = 0.0


class WebhookDeliverySummary(BaseModel):
    """Delivery verification of webhooks against communication records."""

    events_received: int = 0
    communications_with_terminal_status: int = 0
    missing_terminal: int = 0


class OutcomesSummaryResponse(BaseModel):
    """Aggregate outcomes summary across filtered outreach communications."""

    attempted: int = 0
    blocked: int = 0
    blocked_by_reason: dict[str, int] = Field(default_factory=dict)
    dispatched: int = 0
    connected: int = 0
    completed: int = 0
    no_answer: int = 0
    failed: int = 0

    avg_duration_seconds: float | None = None
    median_duration_seconds: float | None = None
    p95_duration_seconds: float | None = None

    latency: LatencySummary = Field(default_factory=LatencySummary)
    outcome_counts: OutcomeCounts = Field(default_factory=OutcomeCounts)
    extraction_fill_rate: ExtractionFillRate = Field(default_factory=ExtractionFillRate)
    webhook_delivery: WebhookDeliverySummary = Field(default_factory=WebhookDeliverySummary)
    cost: CostSummary = Field(default_factory=CostSummary)
    language_breakdown: dict[str, int] = Field(default_factory=dict)
    definitions: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class OutcomesCallItem(BaseModel):
    """Summary item for paginated calls list."""

    id: str
    recipient_name: str
    phone_masked: str
    campaign_id: str | None = None
    campaign_name: str | None = None
    test_run_label: str | None = None
    status: str
    outcome: CommunicationOutcome | None = None
    duration_seconds: float | None = None
    language_used: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimelineEvent(BaseModel):
    """Status transition or webhook arrival event in communication lifecycle."""

    event: str
    timestamp: datetime | str
    source: str
    detail: dict[str, Any] = Field(default_factory=dict)


class OutcomesCallDetail(BaseModel):
    """Comprehensive detail view of a communication record and its history."""

    id: str
    tenant_id: str
    campaign_id: str | None = None
    campaign_name: str | None = None
    recipient_name: str
    phone_masked: str
    status: str
    timeline: list[TimelineEvent] = Field(default_factory=list)
    outcome: CommunicationOutcome | None = None
    transcript: str | list[Any] | None = None
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    provider_status: str | None = None
    hangup_reason: str | None = None
    config_version: str | int | None = None
    blocked_reason: str | None = None
    error: str | None = None
    test_run_label: str | None = None
    technical_details: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)
