"""Tests for dashboard checklist metrics and governance audit trail."""

from datetime import datetime, timezone
import pytest
import pytest_asyncio
import httpx
from bson import ObjectId
from app.core.config import settings
from app.core.db import close_db, get_db, init_db
from app.core.rate_limit import reset_rate_limits
from app.core.security import create_access_token
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Ensure tests run strictly on tara_test database and rate limits are cleared."""
    await init_db(settings.mongo_db_name_test)
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.mark.asyncio
async def test_dashboard_checklist_and_summary_metrics():
    """Test dashboard endpoint computes real checklist states and summary numbers from DB."""
    db = get_db()
    t_id = str(ObjectId())
    user_id = str(ObjectId())
    token = create_access_token({"sub": user_id, "tenant_id": t_id, "role": "SUPER_ADMIN", "email": "admin@dash.com"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Dash Bank", "slug": f"dash-{t_id}"})
        await db.users.insert_one({"_id": ObjectId(user_id), "tenant_id": t_id, "email": "admin@dash.com", "role": "SUPER_ADMIN", "active": True})

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Initially empty -> Step 1 is "next"
            res = await client.get("/api/workspace/dashboard", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert len(data["checklist"]) == 5
            assert data["checklist"][0]["state"] == "next"
            assert data["checklist"][1]["state"] == "blocked"
            assert data["summary"]["leads"] == 0

            # Insert lead -> Step 1 becomes "done", Step 2 becomes "next"
            await db.leads.insert_one({"tenant_id": t_id, "name": "First Lead", "phone": "+919800000001", "created_at": datetime.now(timezone.utc)})
            res2 = await client.get("/api/workspace/dashboard", headers=headers)
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["checklist"][0]["state"] == "done"
            assert data2["checklist"][1]["state"] == "next"
            assert data2["summary"]["leads"] == 1
    finally:
        await db.tenants.delete_one({"_id": ObjectId(t_id)})
        await db.users.delete_one({"_id": ObjectId(user_id)})
        await db.leads.delete_many({"tenant_id": t_id})


@pytest.mark.asyncio
async def test_audit_endpoint_filters_and_controls():
    """Test audit log endpoint pagination, filtering by action/entity_type, and compliance controls card."""
    db = get_db()
    t_id = str(ObjectId())
    user_id = str(ObjectId())
    token = create_access_token({"sub": user_id, "tenant_id": t_id, "role": "SUPER_ADMIN", "email": "admin@audit.com"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Audit Bank", "slug": f"audit-{t_id}"})
        await db.users.insert_one({"_id": ObjectId(user_id), "tenant_id": t_id, "email": "admin@audit.com", "role": "SUPER_ADMIN", "active": True})

        # Insert 3 audit records
        now = datetime.now(timezone.utc)
        await db.audit_log.insert_many([
            {"tenant_id": t_id, "action": "send", "entity_type": "communication", "at": now, "detail": {"note": "test"}},
            {"tenant_id": t_id, "action": "blocked", "entity_type": "communication", "at": now, "detail": {"note": "test"}},
            {"tenant_id": t_id, "action": "product_created", "entity_type": "product", "at": now, "detail": {"note": "test"}},
        ])

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get("/api/audit", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["pagination"]["total"] == 3
            assert len(data["items"]) == 3
            assert data["compliance_controls"]["label"] == "Policy controls enforced at dispatch"
            assert "calling_window" in data["compliance_controls"]

            # Filter by action
            res_filt = await client.get("/api/audit?action=product_created", headers=headers)
            assert res_filt.status_code == 200
            assert res_filt.json()["pagination"]["total"] == 1
    finally:
        await db.tenants.delete_one({"_id": ObjectId(t_id)})
        await db.users.delete_one({"_id": ObjectId(user_id)})
        await db.audit_log.delete_many({"tenant_id": t_id})


@pytest.mark.asyncio
async def test_providers_health_endpoint():
    """Verify provider health check returns structured connectivity and 09:00-21:00 calling window."""
    db = get_db()
    t_id = str(ObjectId())
    user_id = str(ObjectId())
    token = create_access_token({"sub": user_id, "tenant_id": t_id, "role": "EMPLOYEE", "email": "emp@audit.com"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Health Bank", "slug": f"health-{t_id}"})
        await db.users.insert_one({"_id": ObjectId(user_id), "tenant_id": t_id, "email": "emp@audit.com", "role": "EMPLOYEE", "active": True})

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get("/api/workspace/providers-health", headers=headers)
            assert res.status_code == 200
            data = res.json()

            # Provider health structure verification
            assert "twilio" in data
            assert "gnani_prisma" in data
            assert "gnani_timbre" in data
            assert "groq_llm" in data
            assert "compliance" in data

            # Calling hours compliance consistency (dynamically matches settings)
            assert data["compliance"]["calling_window_start"] == settings.call_window_start
            assert data["compliance"]["calling_window_end"] == settings.call_window_end

            # Security check: zero unmasked tokens or secrets
            assert settings.twilio_auth_token not in str(data)
            assert settings.gnani_api_key not in str(data)
            assert settings.groq_api_key not in str(data)
    finally:
        await db.tenants.delete_one({"_id": ObjectId(t_id)})
        await db.users.delete_one({"_id": ObjectId(user_id)})


