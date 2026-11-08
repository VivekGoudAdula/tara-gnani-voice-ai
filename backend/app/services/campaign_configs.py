"""Campaign configuration versioning, default templates, and multi-channel persistence."""

from datetime import datetime, timezone
from typing import Any
from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.services.campaign_variables import enforce_valid_voice_config, validate_voice_config

DEFAULT_VOICE_CONFIG: dict[str, Any] = {
    "language_mode": "recipient",
    "language": "telugu",
    "tone": "Professional",
    "opening_message": "Hello {{customer_name}}, I am reaching out from {{bank_name}} regarding our {{product_name}}. Do you have two minutes to speak?",
    "objective": "Introduce product benefits and confirm interest in proceeding.",
    "system_prompt_addendum": "Be courteous, professional, and clear. Do not make false claims regarding credit approvals.",
    "conversation_steps": [
        {"key": "greeting", "text": "Warmly greet recipient and confirm identity."},
        {"key": "intro", "text": "Introduce product and benefits."},
        {"key": "product_explanation", "text": "Explain interest rate and flexible repayment options."},
        {"key": "objection_handling", "text": "Answer questions politely."},
        {"key": "closing", "text": "Thank the customer and conclude."},
    ],
    "questions_to_collect": [
        {"field": "interest_level", "question": "Are you interested in applying for this offer?", "required": True},
        {"field": "preferred_amount", "question": "What is your preferred loan amount?", "required": False},
        {"field": "callback_time", "question": "When is the best time for our executive to call back?", "required": False},
    ],
    "success_condition": "Customer expresses interest or requests a callback.",
    "fallback_behaviour": "Politely acknowledge if customer is busy and offer to call back.",
    "retry_policy": {"max_attempts": 2, "interval_minutes": 60},
    "call_termination": "Polite sign-off and thank you.",
}


async def save_campaign_config(
    db: AsyncIOMotorDatabase,
    campaign_id: str,
    tenant_id: str,
    channel: str,
    config_dict: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    """Save a new versioned configuration document and update campaign pointer."""
    clean_channel = channel.lower().strip()
    if clean_channel == "voice":
        enforce_valid_voice_config(config_dict)

    # Determine next version
    latest = await db.campaign_configs.find_one(
        {"campaign_id": campaign_id, "channel": clean_channel},
        sort=[("version", -1)],
    )
    next_version = (latest["version"] + 1) if latest else 1
    now_utc = datetime.now(timezone.utc)

    doc: dict[str, Any] = {
        "tenant_id": tenant_id,
        "campaign_id": campaign_id,
        "channel": clean_channel,
        "version": next_version,
        "config": config_dict,
        "created_by": user_id,
        "created_at": now_utc,
    }
    await db.campaign_configs.insert_one(doc)

    # Update current config_version pointer on campaign
    if clean_channel == "voice":
        await db.campaigns.update_one(
            {"_id": ObjectId(campaign_id)},
            {"$set": {"config_version": next_version, "updated_at": now_utc}},
        )

    await db.audit_log.insert_one({
        "tenant_id": tenant_id,
        "actor_user_id": user_id,
        "action": "config_saved",
        "entity_type": "campaign",
        "entity_id": campaign_id,
        "detail": {"channel": clean_channel, "version": next_version},
        "at": now_utc,
    })

    return {"message": "Config saved successfully", "channel": clean_channel, "version": next_version}


async def get_campaign_configs(
    db: AsyncIOMotorDatabase,
    campaign_id: str,
    channel: str,
) -> list[dict[str, Any]]:
    """Fetch all historical configuration versions for a channel."""
    cursor = db.campaign_configs.find(
        {"campaign_id": campaign_id, "channel": channel.lower().strip()}
    ).sort("version", -1)
    results: list[dict[str, Any]] = []
    async for c in cursor:
        results.append({
            "version": c["version"],
            "channel": c["channel"],
            "config": c["config"],
            "created_by": c.get("created_by"),
            "created_at": c["created_at"],
        })
    return results
