"""Synchronize all tenants with Test User 1 verified phone and up-to-date scores."""

import asyncio
from datetime import datetime, timezone
import os
import sys

# Add backend root directory to path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings
from app.core.db import get_db, init_db
from app.services.scoring import score_entity_product


async def sync():
    await init_db()
    db = get_db()
    tenants = await db.tenants.find({}).to_list(20)
    target_phone = settings.seed_test_phone_1 or "+919381118626"
    if not target_phone.startswith("+"):
        target_phone = f"+91{target_phone}"

    now = datetime.now(timezone.utc)

    for t in tenants:
        tid = str(t["_id"])
        tname = t.get("name", "Unknown")

        # 1. Update any existing Test User 1 to Vivek Goud
        await db.leads.update_many({"tenant_id": tid, "name": "Test User 1"}, {"$set": {"name": "Vivek Goud", "phone": target_phone}})

        lead_doc = {
            "tenant_id": tid,
            "name": "Vivek Goud",
            "phone": target_phone,
            "language": "telugu",
            "city": "Hyderabad",
            "age": 28,
            "income": 75000.0,
            "segment": "SALARIED_IT",
            "employment_type": "salaried",
            "existing_emi_to_income": 0.15,
            "consent": True,
            "dnd": False,
            "source": "partner_referral",
            "attributes": {},
            "updated_at": now,
        }
        existing = await db.leads.find_one({"tenant_id": tid, "$or": [{"name": "Vivek Goud"}, {"phone": target_phone}]})
        if existing:
            await db.leads.update_one({"_id": existing["_id"]}, {"$set": lead_doc})
        else:
            lead_doc["created_at"] = now
            await db.leads.insert_one(lead_doc)
        print(f"[{tname}] Vivek Goud ready with {target_phone}")

        # 2. Canonical categories for products
        cat_map = {"personal loan": "personal_loan", "credit card": "credit_card", "home loan": "home_loan"}
        async for p in db.products.find({"tenant_id": tid}):
            pname = p.get("name", "").lower().strip()
            cat = cat_map.get(pname, "other")
            if p.get("category") != cat:
                await db.products.update_one({"_id": p["_id"]}, {"$set": {"category": cat, "updated_at": now}})

        # 3. Generate matches with unique run id
        prods = await db.products.find({"tenant_id": tid, "active": True}).to_list(20)
        leads = await db.leads.find({"tenant_id": tid}).to_list(200)
        if prods and leads:
            await db.product_matches.update_many({"tenant_id": tid}, {"$set": {"is_latest": False}})
            run_id = f"sync_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{tid[:6]}"
            matches = []
            for l in leads:
                for p in prods:
                    res = score_entity_product(l, p, "lead")
                    matches.append({
                        "tenant_id": tid,
                        "scoring_run_id": run_id,
                        "is_latest": True,
                        "entity_type": "lead",
                        "entity_id": str(l["_id"]),
                        "product_id": str(p["_id"]),
                        "product_name": p.get("name"),
                        "match_score": res["match_score"],
                        "conversion_probability": res["conversion_probability"],
                        "band": res["band"],
                        "eligibility": res["eligibility"],
                        "eligibility_checks": res["eligibility_checks"],
                        "reason_codes": res["reason_codes"],
                        "imputed_features": res["imputed_features"],
                        "model_id": res["model_id"],
                        "model_version": res["model_version"],
                        "fallback_model": res["fallback_model"],
                        "feature_snapshot": res["feature_snapshot"],
                        "created_at": now,
                    })
            if matches:
                await db.product_matches.insert_many(matches, ordered=False)
                print(f"[{tname}] Generated {len(matches)} product matches across {len(leads)} leads.")


if __name__ == "__main__":
    asyncio.run(sync())
