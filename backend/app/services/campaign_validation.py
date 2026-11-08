"""Campaign validation service for pre-flight readiness checks in TARA 2.0."""

import logging
from typing import Any, Dict, List
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.db import build_tenant_query
from app.schemas.campaigns import CampaignValidationResponse
from app.services.campaign_audience import preview_blocked_reason
from app.services.campaign_variables import validate_voice_config

logger = logging.getLogger("tara.services.campaign_validation")


async def validate_campaign_readiness(
    db: AsyncIOMotorDatabase,
    campaign_id: str,
    tenant_id: str,
) -> CampaignValidationResponse:
    """
    Execute comprehensive pre-flight validation on campaign configuration,
    voice settings, product status, audience snapshots, and compliance gates.
    """
    camp = await db.campaigns.find_one({"_id": ObjectId(campaign_id), "tenant_id": tenant_id})
    if not camp:
        return CampaignValidationResponse(
            is_valid=False,
            status="NOT_FOUND",
            total_recipients=0,
            eligible_recipients=0,
            blocked_estimate=0,
            voice_config_valid=False,
            errors=["Campaign does not exist"],
            warnings=[],
        )

    errors: List[str] = []
    warnings: List[str] = []

    # 1. Product validation
    prod_id = camp.get("product_id")
    if not prod_id:
        errors.append("No product associated with campaign")
    else:
        pid_obj = ObjectId(prod_id) if ObjectId.is_valid(prod_id) else prod_id
        prod = await db.products.find_one(build_tenant_query(tenant_id, {"_id": pid_obj}))
        if not prod:
            errors.append(f"Associated product '{prod_id}' not found")
        elif not prod.get("active", True):
            errors.append(f"Associated product '{prod.get('name')}' is inactive")

    # 2. Audience validation
    total_recipients = await db.campaign_recipients.count_documents({"campaign_id": campaign_id, "tenant_id": tenant_id})
    if total_recipients == 0:
        errors.append("Campaign has no audience recipients selected")

    # 3. Voice Config validation
    v_doc = await db.campaign_configs.find_one({
        "campaign_id": campaign_id,
        "channel": "voice",
        "version": camp.get("config_version", 1),
    })
    v_cfg = v_doc.get("config", {}) if v_doc else {}
    voice_errors = validate_voice_config(v_cfg)
    if voice_errors:
        errors.extend([f"Voice config: {e}" for e in voice_errors])
    voice_config_valid = len(voice_errors) == 0

    # 4. Telephony credentials validation (in production mode)
    if not settings.test_mode:
        if not settings.twilio_account_sid:
            errors.append("TWILIO_ACCOUNT_SID is not configured")
        if not settings.twilio_auth_token:
            errors.append("TWILIO_AUTH_TOKEN is not configured")
        if not settings.twilio_from_number:
            errors.append("TWILIO_FROM_NUMBER is not configured")

    # 5. Pre-flight compliance estimate
    blocked_estimate = 0
    eligible_count = 0
    allowlist = {num.strip() for num in settings.test_allowlist.split(",") if num.strip()}
    coll = db.leads if camp.get("entity_type") == "lead" else db.customers

    cursor = db.campaign_recipients.find({"campaign_id": campaign_id, "tenant_id": tenant_id})
    async for r in cursor:
        eid = r.get("entity_id")
        eid_obj = ObjectId(eid) if ObjectId.is_valid(eid) else eid
        ent = await coll.find_one({"_id": eid_obj})
        if ent:
            blocked_reason = preview_blocked_reason(ent, settings.test_mode, allowlist)
            if blocked_reason:
                blocked_estimate += 1
            else:
                eligible_count += 1
        else:
            blocked_estimate += 1

    if total_recipients > 0 and eligible_count == 0:
        errors.append("All recipients in audience would be blocked by compliance rules")
    elif blocked_estimate > 0:
        warnings.append(f"{blocked_estimate} of {total_recipients} recipients may be blocked by compliance checks")

    is_valid = len(errors) == 0

    return CampaignValidationResponse(
        is_valid=is_valid,
        status=camp.get("status", "DRAFT"),
        total_recipients=total_recipients,
        eligible_recipients=eligible_count,
        blocked_estimate=blocked_estimate,
        voice_config_valid=voice_config_valid,
        errors=errors,
        warnings=warnings,
    )

