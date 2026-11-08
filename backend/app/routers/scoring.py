"""Router for propensity scoring, product matches, explainability, and model governance."""

from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import re
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.db import build_tenant_query, doc_to_dict, get_db
from app.core.deps import get_current_user, require_role
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.scoring import (
    ModelCardResponse,
    ProductMatchDetail,
    ProductMatchSummary,
    ScoringRunRequest,
    ScoringRunSummary,
    TenantScoringSettings,
)
from app.services.scoring import get_tenant_scoring_thresholds, run_scoring_batch

logger = logging.getLogger("tara.scoring")
router = APIRouter(tags=["scoring"])
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "ml" / "artifacts"


@router.post("/scoring/run", response_model=ScoringRunSummary)
async def trigger_scoring_run(
    payload: ScoringRunRequest,
    current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> ScoringRunSummary:
    """Execute a scoring run generating product matches across entities (SUPER_ADMIN only)."""
    try:
        run_dict = await run_scoring_batch(
            tenant_id=current_user["tenant_id"],
            triggered_by=current_user["email"],
            entity_type=payload.entity_type,
            product_ids=payload.product_ids,
        )
        db = get_db()
        await db.audit_log.insert_one({
            "tenant_id": current_user["tenant_id"],
            "actor_user_id": current_user.get("user_id", current_user.get("id")),
            "actor_email": current_user["email"],
            "action": "scoring_run",
            "entity_type": payload.entity_type,
            "entity_id": run_dict.get("id"),
            "detail": {
                "entity_count": run_dict.get("entity_count", 0),
                "match_count": run_dict.get("match_count", 0),
                "product_ids": run_dict.get("product_ids", []),
            },
            "at": datetime.now(timezone.utc),
        })
        return ScoringRunSummary(**run_dict)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Scoring run execution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Scoring pipeline failed")


@router.get("/scoring/runs", response_model=PaginatedResponse[ScoringRunSummary])
async def list_scoring_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse[ScoringRunSummary]:
    """List historical scoring runs for the authenticated tenant."""
    db = get_db()
    query = build_tenant_query(current_user["tenant_id"])
    total = await db.scoring_runs.count_documents(query)
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    skip = (page - 1) * page_size

    cursor = db.scoring_runs.find(query).sort("started_at", -1).skip(skip).limit(page_size)
    items = [ScoringRunSummary(**doc_to_dict(doc)) async for doc in cursor]

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.get("/matches", response_model=PaginatedResponse[ProductMatchDetail])
async def list_latest_matches(
    entity_type: str | None = Query(None),
    product_id: str | None = Query(None),
    band: list[str] | None = Query(None),
    eligibility: str | None = Query(None),
    min_score: float | None = Query(None, ge=0.0, le=100.0),
    max_score: float | None = Query(None, ge=0.0, le=100.0),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse[ProductMatchDetail]:
    """Retrieve latest product matches with filters for campaign builder and UI table."""
    db = get_db()
    tenant_id = current_user["tenant_id"]
    criteria: dict[str, Any] = {"is_latest": True}

    if entity_type:
        criteria["entity_type"] = entity_type
    if product_id:
        criteria["product_id"] = product_id
    if band:
        criteria["band"] = {"$in": band}
    if eligibility:
        criteria["eligibility"] = eligibility
    if min_score is not None or max_score is not None:
        score_filter: dict[str, Any] = {}
        if min_score is not None:
            score_filter["$gte"] = min_score
        if max_score is not None:
            score_filter["$lte"] = max_score
        criteria["match_score"] = score_filter

    if search:
        s_re = {"$regex": re.escape(search.strip()), "$options": "i"}
        leads_q = build_tenant_query(tenant_id, {"name": s_re})
        custs_q = build_tenant_query(tenant_id, {"name": s_re})
        lead_ids = [str(d["_id"]) async for d in db.leads.find(leads_q, {"_id": 1})]
        cust_ids = [str(d["_id"]) async for d in db.customers.find(custs_q, {"_id": 1})]
        criteria["entity_id"] = {"$in": lead_ids + cust_ids}

    query = build_tenant_query(tenant_id, criteria)
    total = await db.product_matches.count_documents(query)
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    skip = (page - 1) * page_size

    cursor = db.product_matches.find(query).sort("match_score", -1).skip(skip).limit(page_size)
    raw_matches = await cursor.to_list(length=page_size)

    # Batch resolve entity display fields (NO full phone)
    leads_needed = [ObjectId(m["entity_id"]) for m in raw_matches if m["entity_type"] == "lead" and ObjectId.is_valid(m["entity_id"])]
    custs_needed = [ObjectId(m["entity_id"]) for m in raw_matches if m["entity_type"] == "customer" and ObjectId.is_valid(m["entity_id"])]
    ent_map: dict[str, Any] = {}

    if leads_needed:
        async for d in db.leads.find(build_tenant_query(tenant_id, {"_id": {"$in": leads_needed}}), {"name": 1, "language": 1, "city": 1, "consent": 1, "dnd": 1}):
            ent_map[str(d["_id"])] = d
    if custs_needed:
        async for d in db.customers.find(build_tenant_query(tenant_id, {"_id": {"$in": custs_needed}}), {"name": 1, "language": 1, "city": 1, "consent": 1, "dnd": 1}):
            ent_map[str(d["_id"])] = d

    items: list[ProductMatchDetail] = []
    for m in raw_matches:
        d = doc_to_dict(m)
        e = ent_map.get(m["entity_id"])
        if e:
            d["entity_name"] = e.get("name")
            d["entity_language"] = e.get("language")
            d["entity_city"] = e.get("city")
            d["consent"] = e.get("consent")
            d["dnd"] = e.get("dnd")
        items.append(ProductMatchDetail(**d))

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.get("/matches/summary", response_model=ProductMatchSummary)
async def get_matches_summary(
    product_id: str | None = Query(None),
    entity_type: str | None = Query(None),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ProductMatchSummary:
    """Return aggregate statistics across latest matches. Band and eligibility sum to total."""
    db = get_db()
    tenant_id = current_user["tenant_id"]
    t_high, t_low = await get_tenant_scoring_thresholds(tenant_id)
    criteria: dict[str, Any] = {"is_latest": True}
    if product_id:
        criteria["product_id"] = product_id
    if entity_type:
        criteria["entity_type"] = entity_type

    query = build_tenant_query(tenant_id, criteria)
    cursor = db.product_matches.find(query, {"band": 1, "eligibility": 1, "match_score": 1})
    by_band = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    by_eligibility = {"ELIGIBLE": 0, "NOT_ELIGIBLE": 0}
    total_score = 0.0
    total = 0

    async for doc in cursor:
        total += 1
        b = doc.get("band", "LOW")
        by_band[b] = by_band.get(b, 0) + 1
        el = doc.get("eligibility", "NOT_ELIGIBLE")
        by_eligibility[el] = by_eligibility.get(el, 0) + 1
        total_score += float(doc.get("match_score", 0.0))

    avg = round(total_score / total, 1) if total > 0 else 0.0
    return ProductMatchSummary(
        total=total,
        by_band=by_band,
        by_eligibility=by_eligibility,
        avg_score=avg,
        thresholds={"threshold_high": t_high, "threshold_low": t_low},
    )


@router.get("/models", response_model=list[ModelCardResponse])
async def list_model_cards(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[ModelCardResponse]:
    """Return model cards for all trained propensity models with normalized feature importance."""
    cards: list[ModelCardResponse] = []
    for artifact_file in sorted(ARTIFACTS_DIR.glob("*.json")):
        try:
            data = json.loads(artifact_file.read_text(encoding="utf-8"))
            features = data.get("features", [])
            total_abs_coef = sum(abs(f.get("coef", 0.0)) for f in features)
            importance = [
                {
                    "feature": f["name"],
                    "importance_percent": round(abs(f.get("coef", 0.0)) / total_abs_coef * 100.0, 1) if total_abs_coef > 0 else 0.0,
                    "direction": "positive" if f.get("coef", 0.0) >= 0 else "negative",
                    "coefficient": round(f.get("coef", 0.0), 4),
                }
                for f in features
            ]
            importance.sort(key=lambda x: x["importance_percent"], reverse=True)
            data["global_feature_importance"] = importance
            cards.append(ModelCardResponse(**data))
        except Exception as exc:
            logger.warning("Failed parsing model artifact %s: %s", artifact_file.name, exc)

    return cards


@router.get("/settings/scoring", response_model=TenantScoringSettings)
async def get_scoring_settings(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> TenantScoringSettings:
    """Get current scoring thresholds for caller's tenant."""
    t_high, t_low = await get_tenant_scoring_thresholds(current_user["tenant_id"])
    return TenantScoringSettings(threshold_high=t_high, threshold_low=t_low)


@router.put("/settings/scoring", response_model=TenantScoringSettings)
async def update_scoring_settings(
    payload: TenantScoringSettings,
    current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> TenantScoringSettings:
    """Update propensity scoring thresholds (SUPER_ADMIN only). Enforces 0 < low < high <= 100."""
    db = get_db()
    tenant_id = current_user["tenant_id"]
    update_doc = {
        "settings.threshold_high": payload.threshold_high,
        "settings.threshold_low": payload.threshold_low,
    }
    if ObjectId.is_valid(tenant_id):
        await db.tenants.update_one({"_id": ObjectId(tenant_id)}, {"$set": update_doc})
    else:
        await db.tenants.update_one({"_id": tenant_id}, {"$set": update_doc})

    await db.audit_log.insert_one({
        "tenant_id": tenant_id,
        "actor_user_id": current_user.get("user_id", current_user.get("id")),
        "actor_email": current_user["email"],
        "action": "settings_updated",
        "entity_type": "settings",
        "entity_id": str(tenant_id),
        "detail": {
            "threshold_high": payload.threshold_high,
            "threshold_low": payload.threshold_low,
        },
        "at": datetime.now(timezone.utc),
    })

    logger.info("Scoring thresholds updated for tenant %s: high=%.1f, low=%.1f", tenant_id, payload.threshold_high, payload.threshold_low)
    return payload
