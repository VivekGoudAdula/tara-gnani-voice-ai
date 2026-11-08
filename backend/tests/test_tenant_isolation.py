"""Tests verifying multi-tenant isolation, signup flow, rate limiting, and sample data loading."""

import uuid
import pytest
import pytest_asyncio
import httpx
from bson import ObjectId
from app.main import app
from app.core.config import settings
from app.core.db import close_db, get_db, init_db
from app.core.rate_limit import reset_rate_limits


@pytest_asyncio.fixture(autouse=True)
async def setup_teardown():
    """Ensure database connection and clear rate limits before each test."""
    await init_db()
    reset_rate_limits()
    yield
    reset_rate_limits()



@pytest.mark.asyncio
async def test_tenant_isolation():
    """Verify standard Phase 1 isolation between Test Bank and Other Bank."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Login as employee@testbank.com
        testbank_login = await client.post(
            "/api/auth/login",
            json={"email": "employee@testbank.com", "password": settings.seed_password},
        )
        assert testbank_login.status_code == 200
        testbank_token = testbank_login.json()["access_token"]
        testbank_headers = {"Authorization": f"Bearer {testbank_token}"}

        tb_leads = await client.get("/api/leads?page_size=100", headers=testbank_headers)
        assert tb_leads.status_code == 200
        tb_leads_data = tb_leads.json()
        assert tb_leads_data["pagination"]["total"] >= 60

        tb_customers = await client.get("/api/customers?page_size=100", headers=testbank_headers)
        assert tb_customers.status_code == 200
        assert tb_customers.json()["pagination"]["total"] == 30

        # 2. Login as employee@otherbank.com
        otherbank_login = await client.post(
            "/api/auth/login",
            json={"email": "employee@otherbank.com", "password": settings.seed_password},
        )
        assert otherbank_login.status_code == 200
        otherbank_token = otherbank_login.json()["access_token"]
        otherbank_headers = {"Authorization": f"Bearer {otherbank_token}"}

        ob_leads = await client.get("/api/leads?page_size=100", headers=otherbank_headers)
        assert ob_leads.status_code == 200
        ob_leads_data = ob_leads.json()
        assert ob_leads_data["pagination"]["total"] >= 15

        ob_customers = await client.get("/api/customers?page_size=100", headers=otherbank_headers)
        assert ob_customers.status_code == 200
        assert ob_customers.json()["pagination"]["total"] == 10

        # 3. Cross tenant lookup returns 404
        sample_tb_lead_id = tb_leads_data["items"][0]["id"]
        cross_resp = await client.get(f"/api/leads/{sample_tb_lead_id}", headers=otherbank_headers)
        assert cross_resp.status_code == 404

        # 4. Token validation
        no_auth = await client.get("/api/leads")
        assert no_auth.status_code == 401
        tampered = await client.get("/api/leads", headers={"Authorization": "Bearer invalid.token"})
        assert tampered.status_code == 401

        # 5. Query param override ignored
        query_override = await client.get(
            "/api/leads?tenant_id=600000000000000000000000",
            headers=otherbank_headers,
        )
        assert query_override.status_code == 200
        assert query_override.json()["pagination"]["total"] >= 15


@pytest.mark.asyncio
async def test_signup_creates_isolated_empty_tenant():
    """Verify signup creates a fresh workspace with 0 records and no cross-tenant visibility."""
    rand_id = uuid.uuid4().hex[:8]
    test_email = f"founder_{rand_id}@newbank.com"
    transport = httpx.ASGITransport(app=app)
    db = get_db()

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/auth/signup",
            json={
                "workspace_name": f"New Fintech {rand_id}",
                "name": "Fintech Founder",
                "email": test_email,
                "password": "StrongPassword123!",
            },
        )
        assert resp.status_code == 201, f"Signup failed: {resp.text}"
        data = resp.json()
        token = data["access_token"]
        tenant_id = data["user"]["tenant_id"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check that user sees 0 leads, 0 customers, 0 products
        leads_res = await client.get("/api/leads", headers=headers)
        assert leads_res.json()["pagination"]["total"] == 0

        customers_res = await client.get("/api/customers", headers=headers)
        assert customers_res.json()["pagination"]["total"] == 0

        products_res = await client.get("/api/products", headers=headers)
        assert len(products_res.json()) == 0

        # Cleanup created records
        await db.users.delete_one({"email": test_email})
        await db.tenants.delete_one({"_id": ObjectId(tenant_id)})


@pytest.mark.asyncio
async def test_signup_field_tampering_prevented():
    """Verify signup rejects or ignores attempts to escalate role or override tenant_id."""
    rand_id = uuid.uuid4().hex[:8]
    test_email = f"tamper_{rand_id}@bank.com"
    fake_tenant = "600000000000000000000000"
    transport = httpx.ASGITransport(app=app)
    db = get_db()

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/auth/signup",
            json={
                "workspace_name": f"Tamper Test {rand_id}",
                "name": "Tamper User",
                "email": test_email,
                "password": "StrongPassword123!",
                "role": "SYSTEM_HACKER",
                "tenant_id": fake_tenant,
                "slug": "custom-hacked-slug",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user"]["role"] == "SUPER_ADMIN"
        assert data["user"]["tenant_id"] != fake_tenant

        # Cleanup
        await db.users.delete_one({"email": test_email})
        await db.tenants.delete_one({"_id": ObjectId(data["user"]["tenant_id"])})


@pytest.mark.asyncio
async def test_signup_validation():
    """Verify duplicate email returns 409 and weak password returns 422."""
    rand_id = uuid.uuid4().hex[:8]
    test_email = f"val_{rand_id}@bank.com"
    transport = httpx.ASGITransport(app=app)
    db = get_db()

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Weak password (<10 chars)
        weak_resp = await client.post(
            "/api/auth/signup",
            json={
                "workspace_name": "Weak Pass Bank",
                "name": "Weak User",
                "email": test_email,
                "password": "short",
            },
        )
        assert weak_resp.status_code == 422

        # Valid signup
        valid_resp = await client.post(
            "/api/auth/signup",
            json={
                "workspace_name": f"Valid Bank {rand_id}",
                "name": "Valid User",
                "email": test_email,
                "password": "ValidPassword123!",
            },
        )
        assert valid_resp.status_code == 201
        tenant_id = valid_resp.json()["user"]["tenant_id"]

        # Duplicate email -> 409
        dup_resp = await client.post(
            "/api/auth/signup",
            json={
                "workspace_name": "Another Bank",
                "name": "Duplicate User",
                "email": test_email,
                "password": "ValidPassword123!",
            },
        )
        assert dup_resp.status_code == 409
        assert "already registered" in dup_resp.json()["detail"].lower()

        # Cleanup
        await db.users.delete_one({"email": test_email})
        await db.tenants.delete_one({"_id": ObjectId(tenant_id)})


@pytest.mark.asyncio
async def test_rate_limiting():
    """Verify in-memory rate limiter triggers 429 when threshold exceeded."""
    reset_rate_limits()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        last_status = None
        for i in range(12):
            resp = await client.post(
                "/api/auth/login",
                json={"email": f"nonexistent_{i}@test.com", "password": "WrongPassword123!"},
            )
            last_status = resp.status_code

        assert last_status == 429, f"Expected 429 status, got {last_status}"


@pytest.mark.asyncio
async def test_sample_data_loading():
    """Verify sample data loading is restricted to SUPER_ADMIN, idempotent (409 on second run), and tenant-isolated."""
    rand_id = uuid.uuid4().hex[:8]
    test_email = f"sample_{rand_id}@bank.com"
    transport = httpx.ASGITransport(app=app)
    db = get_db()

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create fresh tenant
        signup_resp = await client.post(
            "/api/auth/signup",
            json={
                "workspace_name": f"Sample Bank {rand_id}",
                "name": "Sample Admin",
                "email": test_email,
                "password": "SamplePassword123!",
            },
        )
        assert signup_resp.status_code == 201
        admin_token = signup_resp.json()["access_token"]
        tenant_id = signup_resp.json()["user"]["tenant_id"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. EMPLOYEE token cannot call sample-data (403)
        emp_login = await client.post(
            "/api/auth/login",
            json={"email": "employee@testbank.com", "password": settings.seed_password},
        )
        emp_token = emp_login.json()["access_token"]
        emp_resp = await client.post("/api/workspace/sample-data", headers={"Authorization": f"Bearer {emp_token}"})
        assert emp_resp.status_code == 403

        # 2. SUPER_ADMIN calls sample-data -> 201
        load_resp = await client.post("/api/workspace/sample-data", headers=admin_headers)
        assert load_resp.status_code == 201
        load_data = load_resp.json()
        assert load_data["counts"]["products"] == 3
        assert load_data["counts"]["leads"] == 40
        assert load_data["counts"]["customers"] == 20

        # Check tenant has 40 leads and 20 customers
        leads_res = await client.get("/api/leads", headers=admin_headers)
        assert leads_res.json()["pagination"]["total"] == 40

        customers_res = await client.get("/api/customers", headers=admin_headers)
        assert customers_res.json()["pagination"]["total"] == 20

        # 3. Second call returns 409
        second_load = await client.post("/api/workspace/sample-data", headers=admin_headers)
        assert second_load.status_code == 409

        # Cleanup
        await db.products.delete_many({"tenant_id": tenant_id})
        await db.leads.delete_many({"tenant_id": tenant_id})
        await db.customers.delete_many({"tenant_id": tenant_id})
        await db.users.delete_one({"email": test_email})
        await db.tenants.delete_one({"_id": ObjectId(tenant_id)})
