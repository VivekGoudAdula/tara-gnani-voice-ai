"""Audience filtering, candidate preview, compliance pre-flight, and snapshot persistence."""

from datetime import datetime, timezone
import math
import re
from typing import Any
from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.db import build_tenant_query, doc_to_dict
from app.core.security import mask_phone
from app.schemas.campaigns import (
    AudienceCandidateItem,
    AudiencePreviewResponse,
    AudienceSetRequest,
    AudienceSummaryCounts,
)
from app.services.compliance import is_e164, is_fake_seeded_number


def preview_blocked_reason(entity: dict[str, Any], test_mode: bool, allowlist: set[str]) -> str | None:
    """Pre-flight compliance check to predict if outreach will be blocked."""
    phone = (entity.get("phone") or "").strip()
    if is_fake_seeded_number(phone):
        return "non_dialable_number"
    if test_mode and phone not in allowlist:
        return "test_mode_not_allowlisted"
    if not is_e164(phone):
        return "invalid_phone"
    if entity.get("consent") is not True:
        return "no_consent"
    if entity.get("dnd") is True:
        return "dnd"
    return None


def build_candidate_filter(
    campaign: dict[str, Any],
    bands: list[str] | None = None,
    eligibility: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
) -> dict[str, Any]:
    """Build product_matches query for candidate audience selection."""
    crit: dict[str, Any] = {
        "tenant_id": campaign["tenant_id"],
        "product_id": campaign["product_id"],
        "entity_type": campaign["entity_type"],
        "is_latest": True,
    }
    if bands:
        clean_bands = [b.upper().strip() for b in bands if b.strip()]
        if clean_bands:
            crit["band"] = {"$in": clean_bands}
    if eligibility and eligibility.upper() != "ALL":
        crit["eligibility"] = eligibility.upper().strip()

    if min_score is not None or max_score is not None:
        score_crit: dict[str, Any] = {}
        if min_score is not None:
            score_crit["$gte"] = float(min_score)
        if max_score is not None:
            score_crit["$lte"] = float(max_score)
        crit["match_score"] = score_crit

    return crit


async def get_audience_preview(
    db: AsyncIOMotorDatabase,
    campaign: dict[str, Any],
    bands: list[str] | None = None,
    eligibility: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AudiencePreviewResponse:
    """Fetch paginated candidates matching filter with compliance previews and aggregate counts."""
    tid = campaign["tenant_id"]
    cid = str(campaign["_id"])
    coll = db.leads if campaign["entity_type"] == "lead" else db.customers

    # Existing recipients set for already_selected flag
    existing_cursor = db.campaign_recipients.find({"campaign_id": cid}, {"entity_id": 1})
    selected_ids = {doc["entity_id"] async for doc in existing_cursor}

    # Base match query
    query = build_candidate_filter(campaign, bands, eligibility, min_score, max_score)
    all_matches = await db.product_matches.find(query).to_list(length=1000)

    # Fetch referenced entities in batch
    entity_ids = [m["entity_id"] for m in all_matches]
    id_objects = [ObjectId(e) if ObjectId.is_valid(e) else e for e in entity_ids]
    ent_cursor = coll.find(build_tenant_query(tid, {"_id": {"$in": id_objects}}))
    ent_map = {str(e["_id"]): e async for e in ent_cursor}

    allowlist = {num.strip() for num in settings.test_allowlist.split(",") if num.strip()}
    candidates: list[AudienceCandidateItem] = []
    summary = AudienceSummaryCounts(
        total=0, by_band={"HIGH": 0, "MEDIUM": 0, "LOW": 0},
        by_eligibility={"ELIGIBLE": 0, "NOT_ELIGIBLE": 0}, selectable=0, would_be_blocked=0,
    )

    search_clean = (search or "").lower().strip()
    for m in all_matches:
        eid = m["entity_id"]
        entity = ent_map.get(eid)
        if not entity:
            continue
        ename = entity.get("name", "")
        ephone = entity.get("phone", "")
        if search_clean and search_clean not in ename.lower() and search_clean not in ephone.lower():
            continue

        band = m.get("band", "LOW")
        elig = m.get("eligibility", "NOT_ELIGIBLE")
        summary.total += 1
        summary.by_band[band] = summary.by_band.get(band, 0) + 1
        summary.by_eligibility[elig] = summary.by_eligibility.get(elig, 0) + 1

        already_sel = eid in selected_ids
        blocked_r = preview_blocked_reason(entity, settings.test_mode, allowlist)
        if blocked_r:
            summary.would_be_blocked += 1
        if not already_sel:
            summary.selectable += 1

        candidates.append(AudienceCandidateItem(
            entity_id=eid, name=ename, phone_masked=mask_phone(ephone),
            language=entity.get("language", "telugu"), band=band, match_score=float(m.get("match_score", m.get("score", 0.0))),
            eligibility=elig, consent=bool(entity.get("consent")), dnd=bool(entity.get("dnd")),
            already_selected=already_sel, will_be_blocked_reason=blocked_r, match_id=str(m["_id"]),
        ))

    # Prioritize dialable (unblocked) candidates at the top, then sort by highest match score
    candidates.sort(key=lambda c: (1 if c.will_be_blocked_reason else 0, -c.match_score))

    total = len(candidates)
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    start_idx = (page - 1) * page_size
    paged = candidates[start_idx : start_idx + page_size]

    return AudiencePreviewResponse(
        candidates=paged, summary=summary, page=page, page_size=page_size, total=total, total_pages=total_pages,
    )


async def set_campaign_audience(
    db: AsyncIOMotorDatabase,
    campaign: dict[str, Any],
    req: AudienceSetRequest,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    """Apply audience selection (filter, manual, add, remove) with snapshotting and limits."""
    tid, cid = campaign["tenant_id"], str(campaign["_id"])
    now_utc = datetime.now(timezone.utc)
    coll = db.leads if campaign["entity_type"] == "lead" else db.customers

    if req.include_not_eligible and not req.confirm_override:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Overriding eligibility requires explicit confirm_override=true.",
        )

    if req.mode == "remove":
        rm_ids = req.entity_ids or []
        res = await db.campaign_recipients.delete_many({"campaign_id": cid, "entity_id": {"$in": rm_ids}})
        await db.audit_log.insert_one({
            "tenant_id": tid, "actor_user_id": current_user["user_id"], "action": "recipient_removed",
            "entity_type": "campaign", "entity_id": cid, "detail": {"removed_count": res.deleted_count}, "at": now_utc,
        })
        return {"message": "Recipients removed", "count": res.deleted_count}

    # Resolve target matches
    target_matches: list[dict[str, Any]] = []
    if req.mode == "filter":
        f = req.filter or {}
        crit = build_candidate_filter(campaign, f.get("bands"), f.get("eligibility"), f.get("min_score"), f.get("max_score"))
        if not req.include_not_eligible and "eligibility" not in crit:
            crit["eligibility"] = "ELIGIBLE"
        target_matches = await db.product_matches.find(crit).to_list(length=1000)
    elif req.mode in ("manual", "add"):
        eids = req.entity_ids or []
        crit = {
            "tenant_id": tid, "product_id": campaign["product_id"], "entity_type": campaign["entity_type"],
            "entity_id": {"$in": eids}, "is_latest": True,
        }
        if not req.include_not_eligible:
            crit["eligibility"] = "ELIGIBLE"
        target_matches = await db.product_matches.find(crit).to_list(length=len(eids))

    # Resolve entity details for display name and language
    eids = [m["entity_id"] for m in target_matches]
    id_objs = [ObjectId(e) if ObjectId.is_valid(e) else e for e in eids]
    ent_cursor = coll.find(build_tenant_query(tid, {"_id": {"$in": id_objs}}))
    ent_map = {str(e["_id"]): e async for e in ent_cursor}

    # If full replacement (filter / manual), remove existing
    if req.mode in ("filter", "manual"):
        await db.campaign_recipients.delete_many({"campaign_id": cid})

    existing_count = await db.campaign_recipients.count_documents({"campaign_id": cid})
    if existing_count + len(target_matches) > settings.campaign_max_recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audience size would exceed limit of {settings.campaign_max_recipients} recipients.",
        )

    # Insert snapshot records
    docs: list[dict[str, Any]] = []
    scoring_run_id = None
    for m in target_matches:
        eid = m["entity_id"]
        entity = ent_map.get(eid, {})
        scoring_run_id = m.get("scoring_run_id") or scoring_run_id
        docs.append({
            "campaign_id": cid, "tenant_id": tid, "entity_type": campaign["entity_type"], "entity_id": eid,
            "name": entity.get("name", "Unknown"), "language": entity.get("language", "telugu"),
            "match_id": str(m["_id"]), "match_score": float(m.get("match_score", m.get("score", 0.0))), "band": m.get("band", "LOW"),
            "eligibility": m.get("eligibility", "NOT_ELIGIBLE"), "status": "PENDING",
            "blocked_reason": None, "last_communication_id": None, "attempts": 0,
            "last_contact_at": None, "created_at": now_utc, "updated_at": now_utc,
        })

    if docs:
        await db.campaign_recipients.insert_many(docs, ordered=False)

    # Update campaign metadata and status
    new_status = "READY" if (docs or existing_count > 0) and campaign.get("status") == "DRAFT" else campaign.get("status")
    await db.campaigns.update_one(
        {"_id": campaign["_id"]},
        {"$set": {
            "audience_filter": req.filter or {}, "include_not_eligible": req.include_not_eligible,
            "scoring_run_id": scoring_run_id or campaign.get("scoring_run_id"), "status": new_status,
            "updated_at": now_utc,
        }},
    )

    await db.audit_log.insert_one({
        "tenant_id": tid, "actor_user_id": current_user["user_id"], "action": "audience_changed",
        "entity_type": "campaign", "entity_id": cid, "detail": {"count": len(docs), "mode": req.mode}, "at": now_utc,
    })
    return {"message": "Audience set successfully", "recipient_count": len(docs)}
