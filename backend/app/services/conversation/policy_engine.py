"""Deterministic conversation policy engine and state machine transitions."""

import logging
from typing import Optional, Tuple
from app.services.conversation.models import (
    ConversationContext,
    ConversationState,
    CustomerIntent,
)

logger = logging.getLogger("tara.conversation.policy")


class ConversationPolicyEngine:
    """
    Enforces regulatory compliance, banking ethics, and conversational state machine
    transition rules independently of LLM output.
    """

    @staticmethod
    def evaluate_transition(
        context: ConversationContext,
        inferred_intent: CustomerIntent,
        proposed_state: Optional[ConversationState] = None,
    ) -> Tuple[ConversationState, bool, Optional[str]]:
        """
        Evaluate and constrain conversational state transition.

        Args:
            context: Active conversation context.
            inferred_intent: Detected customer intent.
            proposed_state: State transition proposed by the LLM.

        Returns:
            Tuple of (new_state, is_terminal, policy_override_reason).
        """
        curr = context.current_state

        # 1. DO NOT CALL is absolute priority: immediate termination
        if inferred_intent == CustomerIntent.DO_NOT_CALL:
            logger.info("Policy: DO_NOT_CALL intent detected. Enforcing immediate termination.")
            return ConversationState.COMPLETED, True, "do_not_call_enforced"

        # 2. CLEAR REJECTION: Accept immediately and terminate politely
        if inferred_intent == CustomerIntent.NOT_INTERESTED:
            logger.info("Policy: Customer declined. Enforcing polite termination.")
            return ConversationState.COMPLETED, True, "customer_declined"

        # 3. CALLBACK or BUSY: Transition to FOLLOW_UP and terminate
        if inferred_intent in (CustomerIntent.CALLBACK_REQUESTED, CustomerIntent.BUSY_NOW):
            logger.info("Policy: Callback requested. Scheduling follow up and ending turn.")
            return ConversationState.COMPLETED, True, "callback_scheduled"

        # 4. HUMAN ESCALATION: Transfer to human representative
        if inferred_intent == CustomerIntent.ESCALATE_HUMAN:
            logger.info("Policy: Escalating conversation to human specialist.")
            return ConversationState.ESCALATION, True, "human_escalation"

        # 5. GOODBYE
        if inferred_intent == CustomerIntent.GOODBYE:
            return ConversationState.COMPLETED, True, "goodbye"

        # 6. OBJECTION: Transition to OBJECTION_HANDLING unless already handling
        if inferred_intent == CustomerIntent.OBJECTION:
            return ConversationState.OBJECTION_HANDLING, False, None

        # 7. Normal State Machine Flow
        if proposed_state:
            # Prevent regressions from QUALIFICATION back to GREETING
            if curr == ConversationState.QUALIFICATION and proposed_state in (ConversationState.GREETING, ConversationState.DISCOVERY):
                return ConversationState.QUALIFICATION, False, "prevented_state_regression"
            return proposed_state, proposed_state in (ConversationState.COMPLETED, ConversationState.FAILED), None

        # Fallback progression
        flow_map = {
            ConversationState.INITIATED: ConversationState.GREETING,
            ConversationState.GREETING: ConversationState.DISCOVERY,
            ConversationState.DISCOVERY: ConversationState.INFORMATION,
            ConversationState.INFORMATION: ConversationState.QUALIFICATION,
            ConversationState.QUALIFICATION: ConversationState.COMPLETED,
            ConversationState.OBJECTION_HANDLING: ConversationState.INFORMATION,
        }
        next_st = flow_map.get(curr, ConversationState.INFORMATION)
        return next_st, next_st == ConversationState.COMPLETED, None

