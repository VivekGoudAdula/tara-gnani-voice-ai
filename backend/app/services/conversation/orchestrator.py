"""Central Conversation Orchestrator coordinating AI reasoning, tools, and voice lifecycle."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.services.speech.language import normalize_language_code
from app.services.conversation.models import (
    AgentTurnResponse,
    ConversationContext,
    ConversationState,
    CustomerIntent,
    DialogueTurn,
    ToolExecutionResult,
)
from app.services.conversation.customer_context_service import CustomerContextService
from app.services.conversation.prompt_builder import PromptBuilder
from app.services.conversation.llm_client import LLMReasoningService
from app.services.conversation.tool_registry import ToolRegistry
from app.services.conversation.lead_qualification import LeadQualificationEngine
from app.services.conversation.policy_engine import ConversationPolicyEngine
from app.services.conversation.outcome_extractor import ConversationOutcomeExtractor

logger = logging.getLogger("tara.conversation.orchestrator")


class ConversationOrchestrator:
    """
    Coordinates context retrieval, prompt generation, LLM reasoning, safe tool execution,
    qualification tracking, and outcome persistence for telephone conversations.
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        tenant_id: str = "default_tenant",
        mock_mode: bool = False,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.mock_mode = mock_mode

        self.context: Optional[ConversationContext] = None
        self.context_service = CustomerContextService(db, tenant_id)
        self.tool_registry = ToolRegistry(db, tenant_id)
        self.llm_service = LLMReasoningService(mock_mode=mock_mode)

    async def initialize(
        self,
        custom_params: Dict[str, str],
        session_id: str = "stream_session",
        call_sid: Optional[str] = None,
    ) -> None:
        """
        Initialize conversational context from call parameters and database lookups.

        Args:
            custom_params: Telephony stream parameters.
            session_id: Stream or session identifier.
            call_sid: Twilio Call SID.
        """
        comm_id = custom_params.get("communication_id")
        camp_id = custom_params.get("campaign_id")
        tid = custom_params.get("tenant_id") or self.tenant_id
        self.tenant_id = tid
        self.context_service.tenant_id = tid
        self.tool_registry.tenant_id = tid

        cust_name = custom_params.get("customer_name", "Customer")
        raw_lang = custom_params.get("language", "te-IN")
        norm_lang = normalize_language_code(raw_lang)
        bank_name = custom_params.get("bank_name", "Gnani Bank")
        prod_name = custom_params.get("product_name", "Personal Loan")
        loan_amount = custom_params.get("loan_amount", "5,00,000")
        interest_rate = custom_params.get("interest_rate", "10.49%")
        entity_id = custom_params.get("recipient_id") or custom_params.get("entity_id", "")
        entity_type = custom_params.get("recipient_type", "lead")

        # Create base context
        self.context = ConversationContext(
            session_id=session_id,
            tenant_id=tid,
            communication_id=comm_id,
            campaign_id=camp_id,
            entity_type=entity_type,  # type: ignore
            entity_id=entity_id,
            customer_name=cust_name,
            bank_name=bank_name,
            product_name=prod_name,
            loan_amount=loan_amount,
            interest_rate=interest_rate,
            detected_language=norm_lang,
            current_state=ConversationState.INITIATED,
        )

        # Retrieve factual database intelligence asynchronously
        try:
            if entity_id:
                cust_profile = await self.context_service.get_customer_context(entity_id, entity_type)
                if cust_profile:
                    self.context.customer_profile = cust_profile
                    if cust_profile.get("name") and cust_profile["name"] != "Customer":
                        self.context.customer_name = cust_profile["name"]
                    if cust_profile.get("phone"):
                        self.context.customer_phone = cust_profile["phone"]

            # Load product features and propensity matches
            prod_info = await self.context_service.get_product_context(custom_params.get("product_id"))
            self.context.product_details = prod_info
            if prod_info.get("name"):
                self.context.product_name = prod_info["name"]

        except Exception as exc:
            logger.warning("Context enrichment encountered error: %s", exc)

        logger.info(
            "ConversationOrchestrator initialized for customer '%s' (%s, lang: %s)",
            self.context.customer_name,
            self.context.product_name,
            self.context.detected_language,
        )

    def get_initial_greeting(self) -> str:
        """
        Generate warm, consultative opening that avoids scam-like initial pitch.

        Returns:
            Friendly spoken greeting in the customer's language.
        """
        if not self.context:
            return "నమస్కారం అండీ, నేను బ్యాంక్ నుండి తారా మాట్లాడుతున్నాను. మాట్లాడవచ్చా?"

        self.context.current_state = ConversationState.GREETING
        self.context.turn_count = 1
        name = self.context.customer_name
        bank = self.context.bank_name
        lang = self.context.detected_language.lower()

        if "te" in lang:
            greeting = (
                f"నమస్కారం {name} గారు, నేను {bank} నుండి తారా మాట్లాడుతున్నాను. "
                f"మన బ్యాంక్ నుండి కొత్త పర్సనల్ లోన్ సదుపాయాలు అందిస్తున్నాము. దీని గురించి ఒక నిమిషం మాట్లాడవచ్చా అండి?"
            )
        elif "hi" in lang:
            greeting = (
                f"नमस्ते {name} जी, मैं {bank} से तारा बात कर रही हूँ। "
                f"हमारे बैंक की ओर से आपके लिए नई लोन सुविधाएं उपलब्ध हैं। क्या इस बारे में एक मिनट बात हो सकती है?"
            )
        else:
            greeting = (
                f"Hello {name}, I am TARA calling from {bank}. "
                f"We have exciting new financial options available for our valued customers. Do you have a minute to speak?"
            )

        self.context.history.append(DialogueTurn(
            speaker="agent",
            text=greeting,
            state=ConversationState.GREETING.value,
        ))
        return greeting

    async def process_customer_speech(self, customer_speech: str) -> AgentTurnResponse:
        """
        Process customer spoken utterance through the complete intelligent pipeline:
        Intent detection -> Context -> LLM Reasoning -> Policy Guards -> Tools -> Qualification.

        Args:
            customer_speech: Transcript text recognized by Prisma STT.

        Returns:
            AgentTurnResponse containing speech output and updated state.
        """
        if not self.context:
            raise RuntimeError("ConversationOrchestrator must be initialized before processing turns.")

        clean_text = customer_speech.strip()
        if not clean_text:
            return AgentTurnResponse(
                spoken_text="",
                state=self.context.current_state,
                intent=self.context.current_intent,
                is_call_complete=self.context.is_completed,
            )

        self.context.turn_count += 1
        self.context.history.append(DialogueTurn(
            speaker="customer",
            text=clean_text,
            state=self.context.current_state.value,
        ))

        # 1. Update Qualification state heuristically
        self.context.qualification = LeadQualificationEngine.extract_and_update(
            self.context.qualification,
            clean_text,
        )

        # 2. Build Turn Messages for LLM
        messages = PromptBuilder.build_turn_messages(self.context, clean_text)
        fallback_ctx = {
            "customer_name": self.context.customer_name,
            "bank_name": self.context.bank_name,
            "product_name": self.context.product_name,
            "loan_amount": self.context.loan_amount,
            "interest_rate": self.context.interest_rate,
            "language": self.context.detected_language,
        }

        # 3. Call LLM Reasoning Engine
        reasoning = await self.llm_service.generate_reasoning_step(messages, fallback_ctx)

        # Extract parsed reasoning outputs
        raw_intent = reasoning.get("intent", "general")
        confidence = float(reasoning.get("confidence", 0.9))
        try:
            inferred_intent = CustomerIntent(raw_intent.lower())
        except ValueError:
            inferred_intent = CustomerIntent.GENERAL

        raw_state = reasoning.get("state_transition")
        proposed_state = None
        if raw_state:
            try:
                proposed_state = ConversationState(raw_state.upper())
            except ValueError:
                proposed_state = None

        # 4. Enforce Policy Engine Transitions and Guardrails
        new_state, is_terminal, override_reason = ConversationPolicyEngine.evaluate_transition(
            self.context,
            inferred_intent,
            proposed_state,
        )
        self.context.current_state = new_state
        self.context.current_intent = inferred_intent
        self.context.intent_confidence = confidence

        # 5. Execute Approved Tools
        executed_tools: list[ToolExecutionResult] = []
        raw_tool_calls = reasoning.get("tool_calls", [])
        for tc in raw_tool_calls:
            t_name = tc.get("tool_name")
            t_args = tc.get("arguments", {})
            if t_name:
                t_args.setdefault("entity_id", self.context.entity_id)
                t_args.setdefault("entity_type", self.context.entity_type)
                res = await self.tool_registry.execute_tool(t_name, t_args)
                executed_tools.append(res)

                # Update context flags based on critical tool actions
                if t_name == "mark_do_not_call":
                    self.context.is_do_not_call = True
                    is_terminal = True
                elif t_name == "schedule_callback":
                    self.context.callback_time = t_args.get("callback_time", "Later")
                    is_terminal = True
                elif t_name == "request_human_escalation":
                    self.context.is_escalated = True
                    is_terminal = True
                elif t_name == "record_customer_objection":
                    self.context.objections.append(t_args.get("objection_type", "General"))

        # 6. Apply structured qualification update from LLM
        llm_qual = reasoning.get("qualification_update")
        if llm_qual:
            self.context.qualification = LeadQualificationEngine.extract_and_update(
                self.context.qualification,
                clean_text,
                llm_qual,
            )

        # 7. Formulate Spoken Output
        spoken_response = reasoning.get("spoken_response", "").strip()
        if not spoken_response:
            spoken_response = "ధన్యవాదాలు అండీ, మీ వివరాలు నమోదు చేసుకున్నాము."

        self.context.history.append(DialogueTurn(
            speaker="agent",
            text=spoken_response,
            intent=inferred_intent.value,
            state=new_state.value,
            tool_calls=[{"name": t.tool_name, "success": t.success} for t in executed_tools],
        ))

        if is_terminal:
            self.context.is_completed = True

        return AgentTurnResponse(
            spoken_text=spoken_response,
            state=new_state,
            intent=inferred_intent,
            confidence=confidence,
            tools_executed=executed_tools,
            is_call_complete=self.context.is_completed,
            recommended_action=override_reason or "continue_conversation",
            qualification=self.context.qualification,
        )

    async def finalize_session(self) -> Dict[str, Any]:
        """
        Conclude conversational session, persist CRM outcome, and release resources.

        Returns:
            Persisted outcome dictionary.
        """
        if not self.context:
            return {}

        self.context.is_completed = True
        outcome = ConversationOutcomeExtractor.extract_outcome(self.context)
        await ConversationOutcomeExtractor.persist_outcome(self.db, self.context)
        await self.llm_service.close()
        return outcome

