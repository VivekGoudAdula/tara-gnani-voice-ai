"""Post-call outcome extraction and structured persistence for TARA 2.0."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.services.conversation.models import (
    ConversationContext,
    CustomerIntent,
)
from app.services.customer_intelligence import update_customer_intelligence

logger = logging.getLogger("tara.conversation.outcome_extractor")


class ConversationOutcomeExtractor:
    """
    Synthesizes multi-turn dialogue into structured CRM outcomes, lead updates,
    and reporting records consumed by TARA's Outcomes Dashboard.
    """

    @staticmethod
    def extract_outcome(context: ConversationContext) -> Dict[str, Any]:
        """
        Derive normalized conversation summary and analytics metrics from dialogue context.

        Args:
            context: Final conversation context.

        Returns:
            Dictionary matching TARA's CommunicationOutcome schema.
        """
        # Determine high-level interest
        if context.is_do_not_call:
            interest = "not_interested"
            action = "opt_out_dnd"
        elif context.current_intent == CustomerIntent.NOT_INTERESTED:
            interest = "not_interested"
            action = "close_lead"
        elif context.current_intent in (CustomerIntent.CALLBACK_REQUESTED, CustomerIntent.BUSY_NOW) or context.callback_time:
            interest = "callback"
            action = "schedule_followup_call"
        elif context.is_escalated:
            interest = "interested"
            action = "human_relationship_manager_assigned"
        elif context.qualification.status in ("qualified", "in_progress") or context.current_intent == CustomerIntent.INTERESTED:
            interest = "interested"
            action = "dispatch_digital_application_link"
        else:
            interest = "unknown"
            action = "review_recording"

        # Build transcript representation
        transcript_list = [
            {"speaker": t.speaker, "text": t.text, "timestamp": t.timestamp}
            for t in context.history
        ]

        summary_text = (
            f"Conversed with {context.customer_name} regarding {context.product_name}. "
            f"Interest: {interest}. "
            f"Stated need: {context.qualification.stated_need or 'Not specified'}. "
            f"Target amount: {context.qualification.budget_or_amount or context.loan_amount}."
        )

        return {
            "interest_level": interest,
            "preferred_amount": context.qualification.budget_or_amount or context.loan_amount,
            "preferred_callback_time": context.callback_time,
            "language_used": context.detected_language,
            "transcript": transcript_list,
            "duration_source": "twilio_media_stream",
            "duration_type": "actual",
            "turn_count": context.turn_count,
            "objections_raised": context.objections,
            "qualification_status": context.qualification.status,
            "recommended_next_action": action,
            "call_summary": summary_text,
            "is_do_not_call": context.is_do_not_call,
            "is_escalated": context.is_escalated,
            "completed_at": datetime.now(timezone.utc),
        }

    @staticmethod
    async def persist_outcome(
        db: AsyncIOMotorDatabase,
        context: ConversationContext,
    ) -> None:
        """
        Persist extracted outcome to MongoDB communications and audit log collections.

        Args:
            db: Motor MongoDB database instance.
            context: Final conversation context.
        """
        outcome_data = ConversationOutcomeExtractor.extract_outcome(context)
        now_utc = datetime.now(timezone.utc)

        # Build communication record query
        comm_query: Optional[Dict[str, Any]] = None
        if context.communication_id:
            cid = ObjectId(context.communication_id) if ObjectId.is_valid(context.communication_id) else context.communication_id
            comm_query = {"_id": cid}
        elif context.session_id:
            comm_query = {"provider_ref": context.session_id}

        if comm_query:
            try:
                await db.communications.update_one(
                    comm_query,
                    {
                        "$set": {
                            "status": "COMPLETED",
                            "outcome": outcome_data,
                            "completed_at": now_utc,
                            "updated_at": now_utc,
                        }
                    },
                )
                logger.info("Persisted call outcome to communication record (%s)", comm_query)
            except Exception as exc:
                logger.error("Failed to update communication with call outcome: %s", exc)

        # Write to audit log
        try:
            await db.audit_log.insert_one({
                "tenant_id": context.tenant_id,
                "actor_user_id": "tara_voice_agent",
                "action": "conversation_completed",
                "entity_type": "communication",
                "entity_id": context.communication_id or context.session_id,
                "detail": {
                    "interest_level": outcome_data["interest_level"],
                    "turn_count": context.turn_count,
                    "action_recommended": outcome_data["recommended_next_action"],
                },
                "at": now_utc,
            })
        except Exception as exc:
            logger.debug("Audit log recording skipped: %s", exc)

        # Update customer intelligence and lead propensity score in CRM
        try:
            comm = await db.communications.find_one(comm_query) if comm_query else None
            camp_id = context.campaign_id or (comm.get("campaign_id") if comm else None)
            comm_id_str = str(comm["_id"]) if comm else context.communication_id
            target_entity_id = context.entity_id or (comm.get("recipient_id") if comm else None)
            target_entity_type = context.entity_type or (comm.get("recipient_type") if comm else "lead")

            if target_entity_id:
                await update_customer_intelligence(
                    db=db,
                    tenant_id=context.tenant_id,
                    entity_type=target_entity_type,
                    entity_id=str(target_entity_id),
                    outcome=outcome_data,
                    campaign_id=camp_id,
                    communication_id=comm_id_str,
                )
        except Exception as exc:
            logger.error("Failed to update customer intelligence: %s", exc)


