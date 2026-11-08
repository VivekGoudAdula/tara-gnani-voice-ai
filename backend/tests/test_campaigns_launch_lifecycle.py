"""Tests covering campaign launch execution, background dispatch, pacing, status reconciliation, and tenant isolation."""

import asyncio
from datetime import datetime, timezone
import json
from bson import ObjectId
import httpx
import pytest
import pytest_asyncio
from app.core.config import settings
from app.core.db import get_db, init_db
from app.core.rate_limit import reset_rate_limits
from app.main import app
from app.providers.base import ProviderResult
from app.providers.twilio_voice import TwilioVoiceProvider
from app.services.campaigns import refresh_recipient_statuses, run_campaign_dispatch

ALLOWLIST_PHONE = "+919876543210"


@pytest_asyncio.fixture(autouse=True)
async def setup_env(monkeypatch):
    """Configure settings and database before each test run, mocking outbound voice calls."""
    await init_db()
    reset_rate_limits()
    settings.test_mode = True
    settings.voice_provider = "twilio_gnani"
    settings.test_allowlist = f"{ALLOWLIST_PHONE},+919999988888"
    settings.twilio_account_sid = "ACtest1234567890abcdef1234567890"
    settings.twilio_auth_token = "authtoken1234567890abcdef"
    settings.twilio_from_number = "+12025550199"

    async def mock_twilio_send(self, req):
        return ProviderResult(success=True, provider_ref="CAmock123", status="DISPATCHED")

    monkeypatch.setattr(TwilioVoiceProvider, "send", mock_twilio_send)
    yield
    reset_rate_limits()


async def get_auth(client: httpx.AsyncClient) -> tuple[dict[str, str], dict[str, str], str, str]:
    """Return auth headers and tenant IDs for Test Bank and Other Bank."""
    tb = (await client.post("/api/auth/login", json={"email": "employee@testbank.com", "password": settings.seed_password})).json()
    ob = (await client.post("/api/auth/login", json={"email": "employee@otherbank.com", "password": settings.seed_password})).json()
    return {"Authorization": f"Bearer {tb['access_token']}"}, {"Authorization": f"Bearer {ob['access_token']}"}, tb["user"]["tenant_id"], ob["user"]["tenant_id"]


def make_test_lead(tid: str, name: str, phone: str, consent: bool = True, dnd: bool = False) -> dict:
    """Helper returning a schema-valid lead document."""
    return {
        "tenant_id": tid, "name": name, "phone": phone, "consent": consent, "dnd": dnd,
        "language": "telugu", "city": "Hyderabad", "age": 30, "income": 500000.0, "segment": "SALARIED",
        "source": "branch", "created_at": datetime.now(timezone.utc),
    }


@pytest.mark.asyncio
async def test_launch_safety_and_dispatch():
    """Test 5: Launch confirmation mismatch rejected, blocked recipients handled, idempotency applied."""
    transport = httpx.ASGITransport(app=app)
    db = get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tb_hdr, _, tid, _ = await get_auth(client)
        pid = str((await db.products.insert_one({"tenant_id": tid, "name": "Biz Loan", "active": True})).inserted_id)
        cid = (await client.post("/api/campaigns", headers=tb_hdr, json={"name": "Biz Outreach", "product_id": pid, "entity_type": "lead", "objective": "Biz"})).json()["id"]

        now = datetime.now(timezone.utc)
        l1 = str((await db.leads.insert_one(make_test_lead(tid, "Valid Lead", ALLOWLIST_PHONE, True, False))).inserted_id)
        l2 = str((await db.leads.insert_one(make_test_lead(tid, "Blocked Lead", "+919000000002", False, True))).inserted_id)

        await db.product_matches.insert_many([
            {"tenant_id": tid, "product_id": pid, "entity_type": "lead", "entity_id": l1, "score": 80.0, "band": "HIGH", "eligibility": "ELIGIBLE", "is_latest": True, "created_at": now},
            {"tenant_id": tid, "product_id": pid, "entity_type": "lead", "entity_id": l2, "score": 75.0, "band": "HIGH", "eligibility": "ELIGIBLE", "is_latest": True, "created_at": now},
        ])

        await client.put(f"/api/campaigns/{cid}/audience", headers=tb_hdr, json={"mode": "filter", "filter": {}})

        # Mismatched expected_recipient_count is rejected
        bad_launch = await client.post(f"/api/campaigns/{cid}/launch", headers=tb_hdr, json={"confirm": True, "expected_recipient_count": 99})
        assert bad_launch.status_code == 400

        # Unconfirmed launch is rejected
        unconf_launch = await client.post(f"/api/campaigns/{cid}/launch", headers=tb_hdr, json={"confirm": False, "expected_recipient_count": 2})
        assert unconf_launch.status_code == 400

        # Successful launch request sets status LAUNCHING (202 Accepted)
        launch_res = await client.post(f"/api/campaigns/{cid}/launch", headers=tb_hdr, json={"confirm": True, "expected_recipient_count": 2})
        assert launch_res.status_code == 202
        assert launch_res.json()["status"] == "LAUNCHING"
        assert launch_res.json()["test_mode"] is True

        # Run dispatch directly with zero delay for instant deterministic test
        user_dict = {"tenant_id": tid, "user_id": "test_emp", "tenant_name": "Test Bank"}
        await run_campaign_dispatch(db, cid, tid, user_dict, delay_seconds=0.0)

        # Check outcomes in database
        r1 = await db.campaign_recipients.find_one({"campaign_id": cid, "entity_id": l1})
        r2 = await db.campaign_recipients.find_one({"campaign_id": cid, "entity_id": l2})

        assert r1["status"] in ("CALLING", "CONTACTED")
        assert r2["status"] == "BLOCKED"
        assert r2["blocked_reason"] is not None

        # Verify idempotency key on dispatched communication
        comm1 = await db.communications.find_one({"campaign_id": cid, "recipient_id": l1})
        assert comm1 is not None
        assert comm1["idempotency_key"] == f"{cid}:{l1}:1"

        # Verify Pause, Resume, Cancel lifecycle
        pause_res = await client.post(f"/api/campaigns/{cid}/pause", headers=tb_hdr)
        assert pause_res.status_code == 200
        camp = await db.campaigns.find_one({"_id": ObjectId(cid)})
        assert camp["status"] == "PAUSED"

        resume_res = await client.post(f"/api/campaigns/{cid}/resume", headers=tb_hdr)
        assert resume_res.status_code == 200
        camp = await db.campaigns.find_one({"_id": ObjectId(cid)})
        assert camp["status"] in ("LAUNCHING", "RUNNING")

        cancel_res = await client.post(f"/api/campaigns/{cid}/cancel", headers=tb_hdr)
        assert cancel_res.status_code == 200
        camp = await db.campaigns.find_one({"_id": ObjectId(cid)})
        assert camp["status"] == "CANCELLED"

        # Cleanup test documents
        await db.leads.delete_many({"_id": {"$in": [ObjectId(l1), ObjectId(l2)]}})
        await db.product_matches.delete_many({"product_id": pid})


@pytest.mark.asyncio
async def test_status_derivation_and_campaign_auto_completion():
    """Test 7: Recipient status derivation from communications and auto-completion."""
    db = get_db()
    tid = str(ObjectId())
    cid = str(ObjectId())
    now = datetime.now(timezone.utc)

    # Insert campaign in ACTIVE state
    await db.campaigns.insert_one({"_id": ObjectId(cid), "tenant_id": tid, "status": "ACTIVE", "config_version": 1, "created_at": now})

    # Insert recipients
    rcpt1 = {"campaign_id": cid, "tenant_id": tid, "entity_type": "lead", "entity_id": "lead_int", "name": "Interested Person", "status": "CALLING", "attempts": 1, "created_at": now}
    rcpt2 = {"campaign_id": cid, "tenant_id": tid, "entity_type": "lead", "entity_id": "lead_busy", "name": "Busy Person", "status": "CALLING", "attempts": 1, "created_at": now}
    await db.campaign_recipients.insert_many([rcpt1, rcpt2])

    # Insert communications with webhook outcomes
    await db.communications.insert_one({
        "tenant_id": tid, "campaign_id": cid, "recipient_id": "lead_int", "status": "COMPLETED",
        "outcome": {"interest_level": "interested"}, "created_at": now,
    })
    await db.communications.insert_one({
        "tenant_id": tid, "campaign_id": cid, "recipient_id": "lead_busy", "status": "NO_ANSWER",
        "outcome": None, "created_at": now,
    })

    # Run single aggregation status refresh
    await refresh_recipient_statuses(db, cid, tid)

    r1 = await db.campaign_recipients.find_one({"campaign_id": cid, "entity_id": "lead_int"})
    r2 = await db.campaign_recipients.find_one({"campaign_id": cid, "entity_id": "lead_busy"})
    assert r1["status"] == "INTERESTED"
    assert r2["status"] == "NO_ANSWER"

    # Since all recipients are terminal, campaign should have auto-completed
    camp = await db.campaigns.find_one({"_id": ObjectId(cid)})
    assert camp["status"] == "COMPLETED"
    assert camp["completed_at"] is not None


@pytest.mark.asyncio
async def test_tenant_isolation_campaigns():
    """Test 8: Other Bank cannot access, modify, or launch Test Bank campaigns."""
    transport = httpx.ASGITransport(app=app)
    db = get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tb_hdr, ob_hdr, tb_tid, ob_tid = await get_auth(client)

        p_tb = str((await db.products.insert_one({"tenant_id": tb_tid, "name": "TB Exclusive", "active": True})).inserted_id)
        cid = (await client.post("/api/campaigns", headers=tb_hdr, json={"name": "Confidential Campaign", "product_id": p_tb, "entity_type": "lead", "objective": "Secret"})).json()["id"]

        # Other Bank GET campaign -> 404
        assert (await client.get(f"/api/campaigns/{cid}", headers=ob_hdr)).status_code == 404

        # Other Bank PUT campaign -> 404
        assert (await client.put(f"/api/campaigns/{cid}", headers=ob_hdr, json={"name": "Tampered"})).status_code == 404

        # Other Bank DELETE campaign -> 404
        assert (await client.delete(f"/api/campaigns/{cid}", headers=ob_hdr)).status_code == 404

        # Other Bank LAUNCH campaign -> 404
        assert (await client.post(f"/api/campaigns/{cid}/launch", headers=ob_hdr, json={"confirm": True, "expected_recipient_count": 0})).status_code == 404
