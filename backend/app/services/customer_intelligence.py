"""Customer Intelligence & Dynamic Lead Scoring service for TARA 2.0.

Translates conversation outcomes and signals into structured CRM updates, lead status transitions,
compliance flags, and auditable ML propensity score adjustments.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.db import build_tenant_query
from app.services.conversation.models import ConversationContext, CustomerIntent

logger = logging.getLogger("tara.services.customer_intelligence")

# Normalized lead status mappings based on conversation signals
def derive_lead_status(
    outcome: Dict[str, Any],
    context: Optional[ConversationContext] = None,
) -> str:
    """
    Map conversation outcome and context signals to standardized lead status.

    Priority:
    1. DO_NOT_CALL
    2. ESCALATED
    3. CALLBACK_SCHEDULED
    4. QUALIFIED
    5. INTERESTED
    6. NOT_INTERESTED
    7. CONTACTED / UNREACHABLE
    """
    if outcome.get("is_do_not_call"):
        return "DO_NOT_CALL"
    if outcome.get("is_escalated"):
        return "ESCALATED"
    if outcome.get("preferred_callback_time") or outcome.get("interest_level") == "callback":
        return "CALLBACK_SCHEDULED"

    qual_status = outcome.get("qualification_status", "")
    if qual_status == "qualified":
        return "QUALIFIED"

    interest = (outcome.get("interest_level") or "").lower().strip()
    if interest == "interested":
        return "INTERESTED"
    if interest == "not_interested":
        return "NOT_INTERESTED"
    if interest in ("no_answer", "busy", "unreachable"):
        return "UNREACHABLE"

    return "CONTACTED"


def calculate_score_adjustment(
    original_score: float,
    current_score: float,
    outcome: Dict[str, Any],
) -> Tuple[float, str]:
    """
    Calculate dynamic score adjustment and reason code based on conversation outcome.

    Preserves original score and keeps adjustment traceable.
    Returns:
        (delta_score, reason_code)
    """
    if outcome.get("is_do_not_call"):
        # Opt-out / DND drops score to 0
        return (-current_score, "DO_NOT_CALL_REQUESTED")

    interest = (outcome.get("interest_level") or "").lower().strip()
    qual_status = outcome.get("qualification_status", "")
    objections = outcome.get("objections_raised", [])

    if interest == "not_interested":
        # Explicit rejection drops score significantly (never treated as positive)
        return (-25.0, "CUSTOMER_REJECTED_OFFER")

    delta = 0.0
    reasons: list[str] = []

    if interest == "interested" or outcome.get("is_escalated"):
        delta += 15.0
        reasons.append("EXPRESSED_INTEREST")

    if qual_status == "qualified":
        delta += 10.0
        reasons.append("QUALIFIED_CRITERIA")
    elif qual_status == "in_progress":
        delta += 5.0
        reasons.append("PARTIALLY_QUALIFIED")

    if objections:
        delta -= min(10.0, 5.0 * len(objections))
        reasons.append("OBJECTIONS_RAISED")

    if outcome.get("preferred_callback_time"):
        delta += 5.0
        reasons.append("CALLBACK_REQUESTED")

    reason_str = "_AND_".join(reasons) if reasons else "CONVERSATION_ENGAGED"
    return (delta, reason_str)


async def update_customer_intelligence(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    outcome: Dict[str, Any],
    campaign_id: Optional[str] = None,
    communication_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply full customer intelligence update to lead/customer record and ML propensity match:
    1. Update lead status.
    2. Set DND flag immediately if customer requested opt-out.
    3. Record structured interaction history.
    4. Adjust propensity score with auditable adjustment tracking.
    """
    now_utc = datetime.now(timezone.utc)
    clean_id = entity_id.strip()
    id_obj = ObjectId(clean_id) if ObjectId.is_valid(clean_id) else clean_id
    coll = db.leads if entity_type == "lead" else db.customers

    entity = await coll.find_one(build_tenant_query(tenant_id, {"_id": id_obj}))
    if not entity:
        logger.warning("Entity %s (%s) not found for intelligence update", entity_id, entity_type)
        return {"updated": False, "reason": "entity_not_found"}

    new_lead_status = derive_lead_status(outcome)
    is_dnd = outcome.get("is_do_not_call", False) or entity.get("dnd", False)

    # 1. Prepare interaction entry
    interaction_entry = {
        "timestamp": now_utc,
        "campaign_id": campaign_id,
        "communication_id": communication_id,
        "lead_status": new_lead_status,
        "interest_level": outcome.get("interest_level"),
        "qualification_status": outcome.get("qualification_status"),
        "recommended_next_action": outcome.get("recommended_next_action"),
        "call_summary": outcome.get("call_summary"),
        "objections_raised": outcome.get("objections_raised", []),
        "preferred_amount": outcome.get("preferred_amount"),
        "preferred_callback_time": outcome.get("preferred_callback_time"),
    }

    # 2. Update Lead / Customer record
    lead_update: Dict[str, Any] = {
        "lead_status": new_lead_status,
        "last_contact_at": now_utc,
        "updated_at": now_utc,
    }
    if is_dnd:
        lead_update["dnd"] = True

    await coll.update_one(
        {"_id": id_obj},
        {
            "$set": lead_update,
            "$push": {"interaction_history": interaction_entry},
        },
    )

    # 3. Dynamic Lead Propensity Score Update in product_matches
    match_query: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "entity_type": entity_type,
        "entity_id": clean_id,
        "is_latest": True,
    }
    latest_match = await db.product_matches.find_one(match_query)

    score_result: Dict[str, Any] = {}
    if latest_match:
        orig_score = float(latest_match.get("original_score", latest_match.get("score", latest_match.get("match_score", 50.0))))
        curr_score = float(latest_match.get("match_score", latest_match.get("score", orig_score)))

        delta, reason_code = calculate_score_adjustment(orig_score, curr_score, outcome)
        updated_score = max(0.0, min(100.0, round(curr_score + delta, 1)))

        # Determine new band
        if updated_score >= 70.0:
            new_band = "HIGH"
        elif updated_score >= 40.0:
            new_band = "MEDIUM"
        else:
            new_band = "LOW"

        adjustment_entry = {
            "previous_score": curr_score,
            "adjustment": delta,
            "updated_score": updated_score,
            "reason_code": reason_code,
            "timestamp": now_utc,
            "communication_id": communication_id,
        }

        await db.product_matches.update_one(
            {"_id": latest_match["_id"]},
            {
                "$set": {
                    "original_score": orig_score,
                    "match_score": updated_score,
                    "score": updated_score,
                    "band": new_band,
                    "updated_at": now_utc,
                },
                "$push": {"score_adjustments": adjustment_entry},
            },
        )
        score_result = {
            "previous_score": curr_score,
            "updated_score": updated_score,
            "band": new_band,
            "adjustment": delta,
            "reason_code": reason_code,
        }

    logger.info(
        "Updated intelligence for %s %s: status=%s, score_result=%s",
        entity_type,
        entity_id,
        new_lead_status,
        score_result,
    )

    return {
        "updated": True,
        "entity_id": entity_id,
        "lead_status": new_lead_status,
        "dnd_applied": is_dnd,
        "score_result": score_result,
    }

