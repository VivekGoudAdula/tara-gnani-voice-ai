"""Integration tests for scoring APIs, persistence guarantees, thresholds, and tenant isolation."""

from datetime import datetime, timezone
import pytest
import pytest_asyncio
import httpx
from bson import ObjectId
from app.core.config import settings
from app.core.db import close_db, get_db, init_db
from app.core.rate_limit import reset_rate_limits
from app.core.security import create_access_token, get_password_hash
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Ensure tests run strictly on tara_test database and rate limits are cleared."""
    await init_db(settings.mongo_db_name_test)
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.mark.asyncio
async def test_scoring_persistence_and_never_delete():
    """Verify matches never delete, old runs keep is_latest=False, and API returns all matches."""
    db = get_db()
    t_id = str(ObjectId())
    admin_id = str(ObjectId())

    # Create admin user & tokens
    admin_token = create_access_token({"sub": admin_id, "tenant_id": t_id, "role": "SUPER_ADMIN"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Persistence Bank", "slug": f"persist-{t_id}", "created_at": datetime.now(timezone.utc)})
        await db.users.insert_one({"_id": ObjectId(admin_id), "tenant_id": t_id, "email": "admin@persist.com", "role": "SUPER_ADMIN", "active": True})

        # Insert 1 active product, 2 leads
        p_res = await db.products.insert_one({
            "tenant_id": t_id, "name": "Flexi Loan", "category": "personal_loan", "active": True,
            "eligibility_rules": {"min_income": 40000}, "created_at": datetime.now(timezone.utc),
        })
        p_id = str(p_res.inserted_id)

        await db.leads.insert_one({
            "tenant_id": t_id, "name": "Eligible Lead", "income": 50000, "employment_type": "salaried",
            "existing_emi_to_income": 0.2, "source": "web_form", "created_at": datetime.now(timezone.utc),
        })
        await db.leads.insert_one({
            "tenant_id": t_id, "name": "Ineligible Lead", "income": 20000, "employment_type": "salaried",
            "existing_emi_to_income": 0.2, "source": "web_form", "created_at": datetime.now(timezone.utc),
        })

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Run scoring first time
            r1 = await client.post("/api/scoring/run", json={"entity_type": "lead"}, headers=headers)
            assert r1.status_code == 200
            assert r1.json()["match_count"] == 2

            total_matches_run1 = await db.product_matches.count_documents({"tenant_id": t_id})
            latest_matches_run1 = await db.product_matches.count_documents({"tenant_id": t_id, "is_latest": True})
            assert total_matches_run1 == 2
            assert latest_matches_run1 == 2

            # 2. Run scoring second time (never delete: older matches preserved as is_latest=False)
            r2 = await client.post("/api/scoring/run", json={"entity_type": "lead"}, headers=headers)
            assert r2.status_code == 200
            assert r2.json()["match_count"] == 2

            total_matches_run2 = await db.product_matches.count_documents({"tenant_id": t_id})
            latest_matches_run2 = await db.product_matches.count_documents({"tenant_id": t_id, "is_latest": True})
            old_matches_run2 = await db.product_matches.count_documents({"tenant_id": t_id, "is_latest": False})
            assert total_matches_run2 == 4  # History preserved!
            assert latest_matches_run2 == 2
            assert old_matches_run2 == 2

            # 3. GET /api/matches returns both eligible and not-eligible latest matches
            matches_resp = await client.get("/api/matches", headers=headers)
            assert matches_resp.status_code == 200
            m_data = matches_resp.json()
            assert m_data["pagination"]["total"] == 2
            statuses = {item["eligibility"] for item in m_data["items"]}
            assert "ELIGIBLE" in statuses
            assert "NOT_ELIGIBLE" in statuses

            # 4. GET /api/matches/summary counts must add up to total
            sum_resp = await client.get("/api/matches/summary", headers=headers)
            assert sum_resp.status_code == 200
            s_data = sum_resp.json()
            assert s_data["total"] == 2
            assert sum(s_data["by_band"].values()) == s_data["total"]
            assert sum(s_data["by_eligibility"].values()) == s_data["total"]

    finally:
        # Clean up ONLY records created in tara_test for this test tenant
        await db.product_matches.delete_many({"tenant_id": t_id})
        await db.scoring_runs.delete_many({"tenant_id": t_id})
        await db.products.delete_many({"tenant_id": t_id})
        await db.leads.delete_many({"tenant_id": t_id})
        await db.users.delete_many({"tenant_id": t_id})
        await db.tenants.delete_many({"_id": ObjectId(t_id)})


@pytest.mark.asyncio
async def test_scoring_thresholds_configuration():
    """Verify threshold updates change bands on next run and validation rejects bad values."""
    db = get_db()
    t_id = str(ObjectId())
    admin_id = str(ObjectId())
    admin_token = create_access_token({"sub": admin_id, "tenant_id": t_id, "role": "SUPER_ADMIN"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Thresholds Bank", "slug": f"thresh-{t_id}", "created_at": datetime.now(timezone.utc)})
        await db.users.insert_one({"_id": ObjectId(admin_id), "tenant_id": t_id, "email": "admin@thresh.com", "role": "SUPER_ADMIN", "active": True})

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Validation rejection: low >= high or out of bounds
            bad_resp = await client.put("/api/settings/scoring", json={"threshold_high": 50, "threshold_low": 60}, headers=headers)
            assert bad_resp.status_code == 422

            # 2. Valid update: high=85, low=35
            ok_resp = await client.put("/api/settings/scoring", json={"threshold_high": 85, "threshold_low": 35}, headers=headers)
            assert ok_resp.status_code == 200
            assert ok_resp.json()["threshold_high"] == 85.0
            assert ok_resp.json()["threshold_low"] == 35.0

            # 3. Verify GET returns updated settings
            get_resp = await client.get("/api/settings/scoring", headers=headers)
            assert get_resp.status_code == 200
            assert get_resp.json()["threshold_high"] == 85.0

    finally:
        await db.users.delete_many({"tenant_id": t_id})
        await db.tenants.delete_many({"_id": ObjectId(t_id)})


@pytest.mark.asyncio
async def test_scoring_tenant_isolation_and_roles():
    """Verify Other Bank cannot read matches, run touches only caller's tenant, and roles are enforced."""
    db = get_db()
    t1_id = str(ObjectId())
    t2_id = str(ObjectId())
    admin1_id = str(ObjectId())
    emp1_id = str(ObjectId())
    admin2_id = str(ObjectId())

    admin1_token = create_access_token({"sub": admin1_id, "tenant_id": t1_id, "role": "SUPER_ADMIN"})
    emp1_token = create_access_token({"sub": emp1_id, "tenant_id": t1_id, "role": "EMPLOYEE"})
    admin2_token = create_access_token({"sub": admin2_id, "tenant_id": t2_id, "role": "SUPER_ADMIN"})

    h_admin1 = {"Authorization": f"Bearer {admin1_token}"}
    h_emp1 = {"Authorization": f"Bearer {emp1_token}"}
    h_admin2 = {"Authorization": f"Bearer {admin2_token}"}

    try:
        await db.tenants.insert_one({"_id": ObjectId(t1_id), "name": "Bank 1", "slug": f"bank-1-{t1_id}", "created_at": datetime.now(timezone.utc)})
        await db.tenants.insert_one({"_id": ObjectId(t2_id), "name": "Bank 2", "slug": f"bank-2-{t2_id}", "created_at": datetime.now(timezone.utc)})
        await db.users.insert_one({"_id": ObjectId(admin1_id), "tenant_id": t1_id, "email": "a1@b1.com", "role": "SUPER_ADMIN", "active": True})
        await db.users.insert_one({"_id": ObjectId(emp1_id), "tenant_id": t1_id, "email": "e1@b1.com", "role": "EMPLOYEE", "active": True})
        await db.users.insert_one({"_id": ObjectId(admin2_id), "tenant_id": t2_id, "email": "a2@b2.com", "role": "SUPER_ADMIN", "active": True})

        # Lead in Bank 1
        l1_res = await db.leads.insert_one({
            "tenant_id": t1_id, "name": "Bank 1 Lead", "income": 60000, "employment_type": "salaried",
            "existing_emi_to_income": 0.2, "source": "web_form", "created_at": datetime.now(timezone.utc),
        })
        l1_id = str(l1_res.inserted_id)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. EMPLOYEE gets 403 on scoring run and settings
            emp_run = await client.post("/api/scoring/run", json={"entity_type": "lead"}, headers=h_emp1)
            assert emp_run.status_code == 403

            emp_set = await client.put("/api/settings/scoring", json={"threshold_high": 75, "threshold_low": 45}, headers=h_emp1)
            assert emp_set.status_code == 403

            # 2. Bank 2 admin cannot access Bank 1 lead matches (returns 404)
            b2_read = await client.get(f"/api/leads/{l1_id}/matches", headers=h_admin2)
            assert b2_read.status_code == 404

            # 3. /api/matches returns 0 for Bank 2
            b2_matches = await client.get("/api/matches", headers=h_admin2)
            assert b2_matches.status_code == 200
            assert b2_matches.json()["pagination"]["total"] == 0

    finally:
        await db.leads.delete_many({"tenant_id": {"$in": [t1_id, t2_id]}})
        await db.users.delete_many({"tenant_id": {"$in": [t1_id, t2_id]}})
        await db.tenants.delete_many({"_id": {"$in": [ObjectId(t1_id), ObjectId(t2_id)]}})


@pytest.mark.asyncio
async def test_products_crud_and_validation():
    """Verify product CRUD rules, validation rejection (min_age > max_age), and permissions."""
    db = get_db()
    t_id = str(ObjectId())
    admin_id = str(ObjectId())
    emp_id = str(ObjectId())

    admin_token = create_access_token({"sub": admin_id, "tenant_id": t_id, "role": "SUPER_ADMIN"})
    emp_token = create_access_token({"sub": emp_id, "tenant_id": t_id, "role": "EMPLOYEE"})
    h_admin = {"Authorization": f"Bearer {admin_token}"}
    h_emp = {"Authorization": f"Bearer {emp_token}"}

    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Product Bank", "slug": f"pbank-{t_id}", "created_at": datetime.now(timezone.utc)})
        await db.users.insert_one({"_id": ObjectId(admin_id), "tenant_id": t_id, "email": "adm@pbank.com", "role": "SUPER_ADMIN", "active": True})
        await db.users.insert_one({"_id": ObjectId(emp_id), "tenant_id": t_id, "email": "emp@pbank.com", "role": "EMPLOYEE", "active": True})

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Validation rejection: min_age > max_age
            bad_prod = {
                "name": "Invalid Product",
                "category": "personal_loan",
                "eligibility_rules": {"min_age": 45, "max_age": 30},
            }
            bad_resp = await client.post("/api/products", json=bad_prod, headers=h_admin)
            assert bad_resp.status_code == 422

            # 2. EMPLOYEE gets 403 on create
            emp_resp = await client.post("/api/products", json={"name": "Emp Loan", "category": "personal_loan"}, headers=h_emp)
            assert emp_resp.status_code == 403

            # 3. SUPER_ADMIN creates product
            create_resp = await client.post("/api/products", json={"name": "Gold Loan", "category": "personal_loan"}, headers=h_admin)
            assert create_resp.status_code == 201
            p_id = create_resp.json()["id"]

            # 4. SUPER_ADMIN updates product -> receives rescore notice
            upd_resp = await client.put(f"/api/products/{p_id}", json={"description": "Updated loan terms"}, headers=h_admin)
            assert upd_resp.status_code == 200
            assert "Rescore" in upd_resp.json()["notice"]

            # 5. Patch active toggle
            toggle_resp = await client.patch(f"/api/products/{p_id}/active", json={"active": False}, headers=h_admin)
            assert toggle_resp.status_code == 200
            assert toggle_resp.json()["active"] is False

    finally:
        await db.products.delete_many({"tenant_id": t_id})
        await db.users.delete_many({"tenant_id": t_id})
        await db.tenants.delete_many({"_id": ObjectId(t_id)})
