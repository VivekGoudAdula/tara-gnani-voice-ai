"""Idempotent database seeding script for TARA tenants, users, products, leads, and customers."""

import argparse
import asyncio
from datetime import datetime, timezone
import os
import sys
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.sample_data import generate_sample_customers, generate_sample_leads, get_default_products
from app.core.security import get_password_hash


async def seed_data(reset: bool = False) -> None:
    """Seed tenants, users, products, leads, and customers idempotently."""
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client[settings.mongo_db_name]

    if reset:
        print("[*] Reset flag provided. Wiping existing collections...")
        for col in ["tenants", "users", "products", "leads", "customers"]:
            await db[col].delete_many({})
        print("[+] Existing data wiped.")

    # Check if Test Bank already exists
    test_tenant = await db.tenants.find_one({"slug": "test-bank"})
    other_tenant = await db.tenants.find_one({"slug": "other-bank"})

    if test_tenant and other_tenant and not reset:
        leads_count = await db.leads.count_documents({})
        customers_count = await db.customers.count_documents({})
        if leads_count >= 75 and customers_count >= 40:
            print(f"[+] Database already populated ({leads_count} leads, {customers_count} customers).")
            print("\nLogins available:")
            print("  Test Bank Admin:    admin@testbank.com    / " + settings.seed_password)
            print("  Test Bank Employee: employee@testbank.com / " + settings.seed_password)
            print("  Other Bank Employee: employee@otherbank.com / " + settings.seed_password)
            client.close()
            return

    now = datetime.now(timezone.utc)
    if not test_tenant:
        res = await db.tenants.insert_one({"name": "Test Bank", "slug": "test-bank", "created_at": now})
        test_tenant_id = res.inserted_id
    else:
        test_tenant_id = test_tenant["_id"]

    if not other_tenant:
        res = await db.tenants.insert_one({"name": "Other Bank", "slug": "other-bank", "created_at": now})
        other_tenant_id = res.inserted_id
    else:
        other_tenant_id = other_tenant["_id"]

    # Seed Users
    password_hash = get_password_hash(settings.seed_password)
    users_to_seed = [
        {
            "tenant_id": test_tenant_id,
            "name": "Test Bank Admin",
            "email": "admin@testbank.com",
            "password_hash": password_hash,
            "role": "SUPER_ADMIN",
            "active": True,
        },
        {
            "tenant_id": test_tenant_id,
            "name": "Test Bank Employee",
            "email": "employee@testbank.com",
            "password_hash": password_hash,
            "role": "EMPLOYEE",
            "active": True,
        },
        {
            "tenant_id": other_tenant_id,
            "name": "Other Bank Employee",
            "email": "employee@otherbank.com",
            "password_hash": password_hash,
            "role": "EMPLOYEE",
            "active": True,
        },
    ]

    for user in users_to_seed:
        await db.users.update_one(
            {"email": user["email"]},
            {"$set": user},
            upsert=True,
        )

    # Seed Products using shared sample data generator
    for p in get_default_products(str(test_tenant_id)):
        await db.products.update_one(
            {"tenant_id": str(test_tenant_id), "name": p["name"]},
            {"$set": p},
            upsert=True,
        )

    other_products = [
        {
            "tenant_id": str(other_tenant_id),
            "name": "Auto Loan",
            "category": "auto",
            "description": "Vehicle financing with minimal documentation",
            "active": True,
            "eligibility_rules": {"min_income": 35000, "min_age": 21, "max_age": 60},
        },
        {
            "tenant_id": str(other_tenant_id),
            "name": "SME Business Loan",
            "category": "business",
            "description": "Working capital facility for small and medium enterprises",
            "active": True,
            "eligibility_rules": {"min_income": 50000, "min_age": 25, "max_age": 65},
        },
    ]
    for p in other_products:
        await db.products.update_one(
            {"tenant_id": str(other_tenant_id), "name": p["name"]},
            {"$set": p},
            upsert=True,
        )

    # Seed Leads & Customers
    test_verified_phones = [
        p for p in [settings.seed_test_phone_1, settings.seed_test_phone_2, settings.seed_test_phone_3] if p
    ]

    tb_leads_count = await db.leads.count_documents({"tenant_id": {"$in": [str(test_tenant_id), ObjectId(test_tenant_id)]}})
    if tb_leads_count < 60:
        tb_leads = generate_sample_leads(str(test_tenant_id), count=60, verified_phones=test_verified_phones)
        await db.leads.insert_many(tb_leads)

    tb_cust_count = await db.customers.count_documents({"tenant_id": {"$in": [str(test_tenant_id), ObjectId(test_tenant_id)]}})
    if tb_cust_count < 30:
        tb_customers = generate_sample_customers(str(test_tenant_id), count=30)
        await db.customers.insert_many(tb_customers)

    ob_leads_count = await db.leads.count_documents({"tenant_id": {"$in": [str(other_tenant_id), ObjectId(other_tenant_id)]}})
    if ob_leads_count < 15:
        ob_leads = generate_sample_leads(str(other_tenant_id), count=15)
        await db.leads.insert_many(ob_leads)

    ob_cust_count = await db.customers.count_documents({"tenant_id": {"$in": [str(other_tenant_id), ObjectId(other_tenant_id)]}})
    if ob_cust_count < 10:
        ob_customers = generate_sample_customers(str(other_tenant_id), count=10)
        await db.customers.insert_many(ob_customers)

    print("\n[+] Seeding completed successfully.")
    print("Logins available:")
    print("  Test Bank Admin:    admin@testbank.com    / " + settings.seed_password)
    print("  Test Bank Employee: employee@testbank.com / " + settings.seed_password)
    print("  Other Bank Employee: employee@otherbank.com / " + settings.seed_password)
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed database with tenants, users, and entities.")
    parser.add_argument("--reset", action="store_true", help="Drop and reseed existing data.")
    args = parser.parse_args()
    asyncio.run(seed_data(reset=args.reset))
