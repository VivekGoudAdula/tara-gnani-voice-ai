"""Schemas for communication dispatch, status tracking, and outcome reporting."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class RecipientRef(BaseModel):
    """Reference to a recipient stored in the tenant database."""

    type: Literal["lead", "customer"]
    id: str


class CommunicationContent(BaseModel):
    """Content definition including optional language override and template variables."""

    language: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)


class CommunicationSendRequest(BaseModel):
    """Request payload for dispatching an outbound communication."""

    channel: Literal["voice", "whatsapp", "sms", "email"]
    recipient_ref: RecipientRef
    content: CommunicationContent = Field(default_factory=CommunicationContent)
    campaign_id: str | None = None
    config_version: str | int | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommunicationSendResponse(BaseModel):
    """Response returned upon dispatch attempt or compliance block."""

    communication_id: str
    status: str
    blocked_reason: str | None = None
    provider_ref: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CommunicationOutcome(BaseModel):
    """Normalized communication outcome captured from provider webhooks."""

    interest_level: str | None = None
    preferred_amount: float | str | None = None
    preferred_callback_time: str | None = None
    language_used: str | None = None
    transcript: str | list[Any] | None = None
    duration_seconds: float | int | None = None
    duration_source: str | None = None
    duration_type: str | None = None
    hangup_reason: str | None = None
    cost: float | None = None
    latency: dict[str, Any] | float | None = None

    model_config = ConfigDict(from_attributes=True)


class CommunicationDetail(BaseModel):
    """Full detail model for a persisted communication record."""

    id: str
    tenant_id: str
    channel: str
    recipient_type: str
    recipient_id: str
    phone_masked: str
    campaign_id: str | None = None
    config_version: str | int | None = None
    idempotency_key: str | None = None
    status: str
    provider: str | None = None
    provider_ref: str | None = None
    provider_status: str | None = None
    blocked_reason: str | None = None
    error: str | None = None
    request_variables: dict[str, Any] = Field(default_factory=dict)
    provider_response_raw: dict[str, Any] | None = None
    outcome: CommunicationOutcome | None = None
    created_by: str
    created_at: datetime | str
    dispatched_at: datetime | str | None = None
    completed_at: datetime | str | None = None
    updated_at: datetime | str

    model_config = ConfigDict(from_attributes=True)
