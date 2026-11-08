"""Scoring orchestration service for evaluating eligibility and propensity matching."""

from datetime import datetime, timezone
import logging
from typing import Any
from bson import ObjectId
from app.core.db import build_tenant_query, get_db
from app.ml.inference import score_propensity
from app.services.eligibility import evaluate_eligibility

logger = logging.getLogger("tara.scoring")


def score_entity_product(
    entity: dict[str, Any],
    product: dict[str, Any],
    entity_type: str,
    threshold_high: float = 70.0,
    threshold_low: float = 40.0,
) -> dict[str, Any]:
    """
    Score a single entity against a product.

    Evaluates deterministic eligibility policy rules and calibrated propensity fit.
    """
    eligibility, checks = evaluate_eligibility(entity, product, entity_type)
    propensity = score_propensity(
        entity=entity,
        product=product,
        entity_type=entity_type,
        threshold_high=threshold_high,
        threshold_low=threshold_low,
    )

    return {
        "match_score": propensity["match_score"],
        "conversion_probability": propensity["conversion_probability"],
        "band": propensity["band"],
        "eligibility": eligibility,
        "eligibility_checks": checks,
        "reason_codes": propensity["reason_codes"],
        "imputed_features": propensity["imputed_features"],
        "model_id": propensity["model_id"],
        "model_version": propensity["model_version"],
        "fallback_model": propensity["fallback_model"],
        "feature_snapshot": propensity["feature_snapshot"],
    }


async def get_tenant_scoring_thresholds(tenant_id: str) -> tuple[float, float]:
    """Retrieve tenant scoring thresholds from tenant settings with defaults (70.0, 40.0)."""
    db = get_db()
    tenant_query = build_tenant_query(tenant_id)
    # Search by _id if tenant_id is an ObjectId
    if ObjectId.is_valid(tenant_id):
        tenant = await db.tenants.find_one({"_id": ObjectId(tenant_id)})
    else:
        tenant = await db.tenants.find_one(tenant_query)

    settings = (tenant or {}).get("settings", {})
    threshold_high = float(settings.get("threshold_high", 70.0))
    threshold_low = float(settings.get("threshold_low", 40.0))
    return threshold_high, threshold_low


async def run_scoring_batch(
    tenant_id: str,
    triggered_by: str,
    entity_type: str = "both",
    product_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Execute batch scoring run across entities and active products.

    Preserves history: writes matches with is_latest=False before atomic flip to True.
    """
    db = get_db()
    clean_tenant_id = str(tenant_id).strip()
    threshold_high, threshold_low = await get_tenant_scoring_thresholds(clean_tenant_id)

    # 1. Resolve active products
    prod_filter: dict[str, Any] = {"active": True}
    if product_ids:
        id_objs = [ObjectId(pid) for pid in product_ids if ObjectId.is_valid(pid)]
        prod_filter["$or"] = [{"_id": {"$in": id_objs}}, {"_id": {"$in": product_ids}}]

    products_cursor = db.products.find(build_tenant_query(clean_tenant_id, prod_filter))
    products = await products_cursor.to_list(length=200)
    if not products:
        raise ValueError("No active products available to score.")

    # 2. Determine target entity types
    targets = ["lead", "customer"] if entity_type == "both" else [entity_type]
    entities_by_type: dict[str, list[dict[str, Any]]] = {}

    if "lead" in targets:
        leads_cursor = db.leads.find(build_tenant_query(clean_tenant_id))
        entities_by_type["lead"] = await leads_cursor.to_list(length=10000)
    if "customer" in targets:
        customers_cursor = db.customers.find(build_tenant_query(clean_tenant_id))
        entities_by_type["customer"] = await customers_cursor.to_list(length=10000)

    # 3. Create scoring run record
    now = datetime.now(timezone.utc)
    run_id = ObjectId()
    run_doc: dict[str, Any] = {
        "_id": run_id,
        "tenant_id": clean_tenant_id,
        "entity_type": entity_type,
        "product_ids": [str(p["_id"]) for p in products],
        "started_at": now,
        "finished_at": None,
        "entity_count": sum(len(items) for items in entities_by_type.values()),
        "match_count": 0,
        "model_versions": {},
        "triggered_by": triggered_by,
        "thresholds": {"threshold_high": threshold_high, "threshold_low": threshold_low},
    }
    await db.scoring_runs.insert_one(run_doc)

    # 4. Generate all matches
    matches: list[dict[str, Any]] = []
    model_versions: dict[str, str] = {}
    scored_entity_ids: set[str] = set()

    for etype, entities in entities_by_type.items():
        for entity in entities:
            ent_id = str(entity["_id"])
            scored_entity_ids.add(ent_id)
            for product in products:
                prod_id = str(product["_id"])
                scored = score_entity_product(
                    entity=entity,
                    product=product,
                    entity_type=etype,
                    threshold_high=threshold_high,
                    threshold_low=threshold_low,
                )
                model_key = f"{etype}_{product.get('category', 'other')}"
                model_versions[model_key] = scored["model_version"]

                match_doc: dict[str, Any] = {
                    "tenant_id": clean_tenant_id,
                    "scoring_run_id": str(run_id),
                    "is_latest": False,  # Written as false initially
                    "entity_type": etype,
                    "entity_id": ent_id,
                    "product_id": prod_id,
                    "product_name": product.get("name", "Unknown Product"),
                    "match_score": scored["match_score"],
                    "conversion_probability": scored["conversion_probability"],
                    "band": scored["band"],
                    "eligibility": scored["eligibility"],
                    "eligibility_checks": scored["eligibility_checks"],
                    "reason_codes": scored["reason_codes"],
                    "imputed_features": scored["imputed_features"],
                    "model_id": scored["model_id"],
                    "model_version": scored["model_version"],
                    "fallback_model": scored["fallback_model"],
                    "feature_snapshot": scored["feature_snapshot"],
                    "created_at": datetime.now(timezone.utc),
                }
                matches.append(match_doc)

    # 5. Insert matches in batches
    if matches:
        batch_size = 500
        for i in range(0, len(matches), batch_size):
            await db.product_matches.insert_many(matches[i : i + batch_size])

    # 6. Atomic transition: set previous matches is_latest=False, new ones is_latest=True
    active_prod_ids = [str(p["_id"]) for p in products]
    prev_query = build_tenant_query(
        clean_tenant_id,
        {
            "entity_type": {"$in": targets},
            "product_id": {"$in": active_prod_ids},
            "scoring_run_id": {"$ne": str(run_id)},
            "is_latest": True,
        },
    )
    await db.product_matches.update_many(prev_query, {"$set": {"is_latest": False}})

    # Flip newly created matches to is_latest=True
    await db.product_matches.update_many(
        {"scoring_run_id": str(run_id)},
        {"$set": {"is_latest": True}},
    )

    # 7. Finalize scoring run
    finished_time = datetime.now(timezone.utc)
    await db.scoring_runs.update_one(
        {"_id": run_id},
        {
            "$set": {
                "finished_at": finished_time,
                "entity_count": len(scored_entity_ids),
                "match_count": len(matches),
                "model_versions": model_versions,
            }
        },
    )

    logger.info(
        "Scoring run %s completed: %d matches created across %d entities",
        str(run_id),
        len(matches),
        len(scored_entity_ids),
    )

    return {
        "id": str(run_id),
        "tenant_id": clean_tenant_id,
        "entity_type": entity_type,
        "product_ids": active_prod_ids,
        "started_at": now.isoformat(),
        "finished_at": finished_time.isoformat(),
        "entity_count": len(scored_entity_ids),
        "match_count": len(matches),
        "model_versions": model_versions,
        "triggered_by": triggered_by,
        "thresholds": {"threshold_high": threshold_high, "threshold_low": threshold_low},
    }
