"""Script to upsert Test User 1 with the allowlisted phone number in Test Bank."""

import argparse
import asyncio
from datetime import datetime, timezone
import os
import sys
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
from app.core.config import settings


async def upsert_test_user(tenant_slug: str = "bangalore-bank", apply: bool = False) -> None:
    """Ensure Test User 1 with allowlisted phone exists in specified tenant."""
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client[settings.mongo_db_name]

    tenant = await db.tenants.find_one({"slug": tenant_slug})
    if not tenant:
        print("[-] Tenant 'test-bank' not found.")
        client.close()
        return

    tid_str = str(tenant["_id"])
    target_phone = settings.seed_test_phone_1 or "+919381118626"
    if not target_phone.startswith("+"):
        target_phone = f"+91{target_phone}"

    print(f"=== Upsert Test User 1 ===")
    print(f"Tenant: {tenant.get('name')} ({tid_str})")
    print(f"Target Phone: {target_phone}")
    print(f"Mode: {'APPLY (Database will be updated)' if apply else 'DRY RUN (No changes)'}\n")

    existing = await db.leads.find_one({"tenant_id": {"$in": [tid_str, ObjectId(tid_str)]}, "name": "Test User 1"})

    lead_doc = {
        "tenant_id": tid_str,
        "name": "Test User 1",
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
        "updated_at": datetime.now(timezone.utc),
    }

    if existing:
        print(f"[+] Found existing lead '{existing.get('name')}' (ID: {existing['_id']}). Will update phone to {target_phone}.")
        if apply:
            await db.leads.update_one({"_id": existing["_id"]}, {"$set": lead_doc})
            print("[+] Updated Test User 1 successfully.")
    else:
        print(f"[+] No existing 'Test User 1' found. Will insert new lead with phone {target_phone}.")
        if apply:
            lead_doc["created_at"] = datetime.now(timezone.utc)
            res = await db.leads.insert_one(lead_doc)
            print(f"[+] Inserted Test User 1 with ID: {res.inserted_id}")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", type=str, default="bangalore-bank", help="Tenant slug (default: bangalore-bank)")
    parser.add_argument("--apply", action="store_true", help="Apply updates to database")
    args = parser.parse_args()
    asyncio.run(upsert_test_user(tenant_slug=args.tenant, apply=args.apply))
