"""Backfill script for populating missing ML features and canonical product categories."""

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import random
import sys

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

CATEGORY_MAP = {
    "personal loan": "personal_loan",
    "credit card": "credit_card",
    "home loan": "home_loan",
    "auto loan": "other",
    "sme business loan": "other",
}


async def backfill(tenant_slug: str = "test-bank", apply: bool = False) -> None:
    """Scan and conditionally backfill missing model attributes and product categories."""
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client[settings.mongo_db_name]

    tenant = await db.tenants.find_one({"slug": tenant_slug})
    if not tenant:
        print(f"[-] Tenant with slug '{tenant_slug}' not found.")
        client.close()
        return

    tid_str = str(tenant["_id"])
    t_filter = {"$in": [tid_str, ObjectId(tid_str)]}

    print(f"=== TARA Attribute Backfill Tool ===")
    print(f"Tenant: {tenant.get('name')} ({tid_str})")
    print(f"Mode: {'APPLY (Database will be updated)' if apply else 'DRY RUN (No changes will be written)'}\n")

    # 1. Backfill Products
    products_cursor = db.products.find({"tenant_id": t_filter})
    products_to_update = []
    async for p in products_cursor:
        cat = p.get("category")
        pname_lower = p.get("name", "").lower().strip()
        canonical = CATEGORY_MAP.get(pname_lower, "other")
        if not cat or cat not in ("personal_loan", "credit_card", "home_loan", "other"):
            products_to_update.append((p["_id"], p.get("name"), cat, canonical))

    print(f"Products requiring category backfill: {len(products_to_update)}")
    for pid, name, old_cat, new_cat in products_to_update:
        print(f"  - Product '{name}' (ID: {pid}): '{old_cat}' -> '{new_cat}'")
        if apply:
            await db.products.update_one(
                {"_id": pid},
                {"$set": {"category": new_cat, "updated_at": datetime.now(timezone.utc)}},
            )

    # 2. Backfill Leads
    leads_cursor = db.leads.find({"tenant_id": t_filter})
    leads_needing_update = 0
    leads_sample = []
    async for l in leads_cursor:
        needs_emp = "employment_type" not in l or not l["employment_type"]
        needs_emi = "existing_emi_to_income" not in l or l["existing_emi_to_income"] is None
        if needs_emp or needs_emi:
            leads_needing_update += 1
            up = {}
            if needs_emp:
                up["employment_type"] = random.choices(["salaried", "self_employed", "other"], weights=[0.70, 0.22, 0.08])[0]
            if needs_emi:
                up["existing_emi_to_income"] = round(random.uniform(0.0, 0.55), 3)

            if len(leads_sample) < 3:
                leads_sample.append((l.get("name"), up))

            if apply:
                await db.leads.update_one({"_id": l["_id"]}, {"$set": up})

    print(f"\nLeads requiring feature backfill: {leads_needing_update}")
    if leads_sample:
        print("  Sample updates that would be applied:")
        for name, up in leads_sample:
            print(f"    - Lead '{name}': {up}")

    # 3. Backfill Customers
    cust_cursor = db.customers.find({"tenant_id": t_filter})
    cust_needing_update = 0
    cust_sample = []
    async for c in cust_cursor:
        needs_emp = "employment_type" not in c or not c["employment_type"]
        needs_emi = "existing_emi_to_income" not in c or c["existing_emi_to_income"] is None
        needs_ten = "tenure_months" not in c or c["tenure_months"] is None
        if needs_emp or needs_emi or needs_ten:
            cust_needing_update += 1
            up = {}
            if needs_emp:
                up["employment_type"] = random.choices(["salaried", "self_employed", "other"], weights=[0.72, 0.20, 0.08])[0]
            if needs_emi:
                up["existing_emi_to_income"] = round(random.uniform(0.0, 0.50), 3)
            if needs_ten:
                up["tenure_months"] = random.randint(6, 120)

            if len(cust_sample) < 3:
                cust_sample.append((c.get("name"), up))

            if apply:
                await db.customers.update_one({"_id": c["_id"]}, {"$set": up})

    print(f"\nCustomers requiring feature backfill: {cust_needing_update}")
    if cust_sample:
        print("  Sample updates that would be applied:")
        for name, up in cust_sample:
            print(f"    - Customer '{name}': {up}")

    print("\n" + "=" * 40)
    if apply:
        print("[+] Backfill completed successfully on database.")
    else:
        print("[!] Dry-run complete. No changes were committed.")
        print("[!] To execute changes, run: python scripts/backfill_attributes.py --apply")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill missing ML features and product categories.")
    parser.add_argument("--tenant", default="test-bank", help="Tenant slug to backfill (default: test-bank)")
    parser.add_argument("--apply", action="store_true", help="Execute database updates (default is dry-run)")
    args = parser.parse_args()

    asyncio.run(backfill(tenant_slug=args.tenant, apply=args.apply))
