"""Pydantic schemas for Campaign Builder, audience previews, voice configs, and lifecycle."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ConversationStep(BaseModel):
    """Conversation step structure for dialogue guidance."""

    key: str
    text: str


class QuestionItem(BaseModel):
    """Question item specifying structured field to extract during call."""

    field: str
    question: str
    required: bool = True


class RetryPolicy(BaseModel):
    """Retry settings for unanswered or failed outreach calls."""

    max_attempts: int = Field(default=1, ge=1, le=3)
    interval_minutes: int = Field(default=60, ge=5)


class VoiceConfigInput(BaseModel):
    """Configuration model for outbound voice calls."""

    language_mode: Literal["recipient", "fixed"] = "recipient"
    language: str | None = "telugu"
    tone: Literal["Professional", "Friendly", "Formal"] = "Professional"
    opening_message: str
    objective: str
    system_prompt_addendum: str | None = ""
    conversation_steps: list[ConversationStep] = Field(default_factory=list)
    questions_to_collect: list[QuestionItem] = Field(default_factory=list)
    success_condition: str
    fallback_behaviour: str
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    call_termination: str | None = ""


class WhatsAppConfigInput(BaseModel):
    """Configuration model for WhatsApp outreach."""

    template_name: str = ""
    body: str = ""
    cta_label: str | None = None
    cta_url: str | None = None


class SMSConfigInput(BaseModel):
    """Configuration model for SMS outreach."""

    body: str = ""


class EmailConfigInput(BaseModel):
    """Configuration model for Email outreach."""

    sender_name: str = ""
    subject: str = ""
    body: str = ""
    cta_label: str | None = None
    cta_url: str | None = None


class CampaignCreate(BaseModel):
    """Payload to initiate a new draft campaign."""

    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    product_id: str
    entity_type: Literal["lead", "customer"]
    objective: str = Field(min_length=3)
    test_run_label: str | None = Field(None, max_length=60)


class CampaignUpdate(BaseModel):
    """Payload to update an existing draft/ready campaign."""

    name: str | None = Field(None, min_length=2, max_length=120)
    description: str | None = None
    product_id: str | None = None
    entity_type: Literal["lead", "customer"] | None = None
    objective: str | None = None
    test_run_label: str | None = Field(None, max_length=60)


class CampaignListItem(BaseModel):
    """Summary item for campaign index listing."""

    id: str
    name: str
    product_id: str
    product_name: str
    entity_type: str
    status: str
    test_run_label: str | None = None
    total_recipients: int
    contacted_count: int
    recipient_counts: dict[str, int] = Field(default_factory=dict)
    updated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignDetail(BaseModel):
    """Detailed view of campaign configuration, audience, and execution state."""

    id: str
    tenant_id: str
    name: str
    description: str | None
    product_id: str
    product_name: str
    entity_type: str
    objective: str
    status: str
    test_run_label: str | None = None
    channels: list[str]
    audience_filter: dict[str, Any] = Field(default_factory=dict)
    include_not_eligible: bool = False
    scoring_run_id: str | None = None
    config_version: int = 0
    created_by: str
    created_at: datetime
    updated_at: datetime
    launched_at: datetime | None = None
    completed_at: datetime | None = None
    scheduled_start_time: datetime | None = None
    timezone: str = "Asia/Kolkata"
    current_voice_config: dict[str, Any] | None = None
    recipient_counts: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class AudienceCandidateItem(BaseModel):
    """Scored candidate evaluated for potential campaign audience inclusion."""

    entity_id: str
    name: str
    phone_masked: str
    language: str
    band: str
    match_score: float
    eligibility: str
    consent: bool
    dnd: bool
    already_selected: bool
    will_be_blocked_reason: str | None = None
    match_id: str | None = None


class AudienceSummaryCounts(BaseModel):
    """Real-time aggregated counts across candidate audience filters."""

    total: int
    by_band: dict[str, int]
    by_eligibility: dict[str, int]
    selectable: int
    would_be_blocked: int


class AudiencePreviewResponse(BaseModel):
    """Response payload for campaign audience preview with pagination and breakdown."""

    candidates: list[AudienceCandidateItem]
    summary: AudienceSummaryCounts
    page: int
    page_size: int
    total: int
    total_pages: int


class AudienceSetRequest(BaseModel):
    """Payload to modify campaign recipient audience."""

    mode: Literal["filter", "manual", "add", "remove"]
    filter: dict[str, Any] | None = None
    entity_ids: list[str] | None = None
    include_not_eligible: bool = False
    confirm_override: bool = False


class CampaignRecipientItem(BaseModel):
    """Individual recipient record inside an active or completed campaign."""

    id: str
    campaign_id: str
    entity_type: str
    entity_id: str
    name: str
    language: str
    match_score: float
    band: str
    eligibility: str
    status: str
    blocked_reason: str | None = None
    tester_scenario: str | None = None
    last_communication_id: str | None = None
    attempts: int = 0
    last_contact_at: datetime | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecipientScenarioUpdate(BaseModel):
    """Payload to assign an expected testing scenario note to a campaign recipient."""

    tester_scenario: str | None = Field(None, max_length=200)


class CampaignLaunchRequest(BaseModel):
    """Strict confirmation payload required to trigger campaign dispatch."""

    confirm: bool
    expected_recipient_count: int


class CampaignLaunchResponse(BaseModel):
    """Response returned upon accepting campaign launch request."""

    message: str
    campaign_id: str
    status: str
    recipient_count: int
    test_mode: bool
    notice: str | None = None
    blocked_estimate: int = 0


class CampaignPreviewRequest(BaseModel):
    """Payload to request non-dispatch rendered voice preview for a recipient."""

    entity_id: str | None = None


class CampaignPreviewResponse(BaseModel):
    """Rendered voice preview showing exact user_data sent to provider."""

    rendered_opening_message: str
    user_data_variables: dict[str, str]
    config_version: int
    validation_report: dict[str, Any]


class CampaignProgress(BaseModel):
    """Live progress counts and blocked reasons breakdown for a campaign."""

    campaign_id: str
    status: str
    total_recipients: int
    counts_by_status: dict[str, int]
    blocked_reasons_breakdown: dict[str, int]
    last_updated: datetime


class CampaignScheduleRequest(BaseModel):
    """Payload to schedule campaign outreach for a future timestamp."""

    scheduled_start_time: datetime
    timezone: str = "Asia/Kolkata"


class CampaignValidationResponse(BaseModel):
    """Pre-flight campaign readiness validation report."""

    is_valid: bool
    status: str
    total_recipients: int
    eligible_recipients: int
    blocked_estimate: int
    voice_config_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CampaignDerivedMetrics(BaseModel):
    """Key conversion and delivery ratios for campaign analytics."""

    contact_rate: float = 0.0
    answer_rate: float = 0.0
    completion_rate: float = 0.0
    interest_rate: float = 0.0
    qualification_rate: float = 0.0
    unreachable_rate: float = 0.0
    retry_rate: float = 0.0
    dispatch_rate: float = 0.0
    drop_off_rate: float = 0.0


class CampaignDurationStats(BaseModel):
    """Call duration statistics in seconds."""

    avg_seconds: float = 0.0
    median_seconds: float = 0.0
    p95_seconds: float = 0.0
    total_seconds: float = 0.0


class CampaignAnalyticsResponse(BaseModel):
    """Comprehensive campaign performance analytics matching TARA 2.0 specs."""

    campaign_id: str
    campaign_name: str
    status: str
    total_audience: int = 0
    eligible_leads: int = 0
    excluded_leads: int = 0
    calls_dispatched: int = 0
    calls_ringing: int = 0
    calls_in_progress: int = 0
    calls_completed: int = 0
    calls_unanswered: int = 0
    calls_busy: int = 0
    calls_failed: int = 0
    retry_attempts: int = 0
    interested_customers: int = 0
    qualified_leads: int = 0
    follow_ups_required: int = 0
    callback_requests: int = 0
    escalations: int = 0
    do_not_call_requests: int = 0
    derived_metrics: CampaignDerivedMetrics = Field(default_factory=CampaignDerivedMetrics)
    duration_stats: CampaignDurationStats = Field(default_factory=CampaignDurationStats)
    blocked_reasons_breakdown: dict[str, int] = Field(default_factory=dict)
    counts_by_status: dict[str, int] = Field(default_factory=dict)
    last_updated: datetime


class CampaignRetryQueueItem(BaseModel):
    """Individual recipient queued or eligible for retry outreach."""

    recipient_id: str
    name: str
    phone_masked: str
    attempts: int
    max_attempts: int
    last_attempt_at: datetime | None = None
    next_retry_at: datetime | None = None
    failure_reason: str | None = None
    eligible_for_retry: bool


class CampaignRetriesResponse(BaseModel):
    """List of retried or retry-eligible recipients for a campaign."""

    campaign_id: str
    total_in_queue: int
    max_attempts_configured: int
    items: list[CampaignRetryQueueItem]

