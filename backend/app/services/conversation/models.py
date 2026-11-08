"""Data models, enums, and structured schemas for TARA 2.0 Intelligent Conversation Engine."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ConversationState(str, Enum):
    """Lifecycle states for conversational acquisition voice sessions."""

    INITIATED = "INITIATED"
    GREETING = "GREETING"
    DISCOVERY = "DISCOVERY"
    INFORMATION = "INFORMATION"
    OBJECTION_HANDLING = "OBJECTION_HANDLING"
    QUALIFICATION = "QUALIFICATION"
    FOLLOW_UP = "FOLLOW_UP"
    ESCALATION = "ESCALATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CustomerIntent(str, Enum):
    """Categorized customer intent inferred from spoken utterances."""

    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    ASKING_INFO = "asking_info"
    PRICING_INQUIRY = "pricing_inquiry"
    PRODUCT_INQUIRY = "product_inquiry"
    ELIGIBILITY_INQUIRY = "eligibility_inquiry"
    CALLBACK_REQUESTED = "callback_requested"
    BUSY_NOW = "busy_now"
    OBJECTION = "objection"
    ESCALATE_HUMAN = "escalate_human"
    WRONG_NUMBER = "wrong_number"
    DO_NOT_CALL = "do_not_call"
    UNCLEAR = "unclear"
    GOODBYE = "goodbye"
    GENERAL = "general"


class DialogueTurn(BaseModel):
    """Representation of an individual conversation turn."""

    speaker: Literal["agent", "customer", "system"]
    text: str
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    intent: Optional[str] = None
    state: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)


class QualificationState(BaseModel):
    """Structured lead qualification state updated across dialogue turns."""

    status: Literal["unqualified", "in_progress", "qualified", "disqualified"] = "unqualified"
    need_identified: bool = False
    stated_need: Optional[str] = None
    budget_or_amount: Optional[str] = None
    timeline: Optional[str] = None
    authority: Optional[str] = None
    existing_solution: Optional[str] = None
    captured_answers: Dict[str, Any] = Field(default_factory=dict)
    score_adjustment: float = 0.0
    notes: List[str] = Field(default_factory=list)


class ToolCallRequest(BaseModel):
    """Structured tool execution request from the reasoning model."""

    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    """Result returned from executing an approved tool."""

    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None


class ConversationContext(BaseModel):
    """Persistent and in-flight context for an active conversation session."""

    session_id: str
    tenant_id: str
    communication_id: Optional[str] = None
    campaign_id: Optional[str] = None
    entity_type: Literal["lead", "customer"] = "lead"
    entity_id: str = ""
    customer_name: str = "Customer"
    customer_phone: str = ""
    customer_profile: Dict[str, Any] = Field(default_factory=dict)
    product_id: Optional[str] = None
    product_name: str = "Personal Loan"
    product_details: Dict[str, Any] = Field(default_factory=dict)
    campaign_details: Dict[str, Any] = Field(default_factory=dict)
    bank_name: str = "Gnani Bank"
    loan_amount: str = "5,00,000"
    interest_rate: str = "10.49%"
    current_state: ConversationState = ConversationState.INITIATED
    detected_language: str = "te-IN"
    current_intent: CustomerIntent = CustomerIntent.GENERAL
    intent_confidence: float = 1.0
    objections: List[str] = Field(default_factory=list)
    qualification: QualificationState = Field(default_factory=QualificationState)
    callback_time: Optional[str] = None
    is_escalated: bool = False
    is_do_not_call: bool = False
    is_completed: bool = False
    turn_count: int = 0
    history: List[DialogueTurn] = Field(default_factory=list)
    summary: str = ""


class AgentTurnResponse(BaseModel):
    """Structured response produced by the Conversation Orchestrator for each turn."""

    spoken_text: str
    state: ConversationState
    intent: CustomerIntent
    confidence: float = 1.0
    tools_executed: List[ToolExecutionResult] = Field(default_factory=list)
    is_call_complete: bool = False
    recommended_action: str = "continue_conversation"
    qualification: QualificationState = Field(default_factory=QualificationState)

