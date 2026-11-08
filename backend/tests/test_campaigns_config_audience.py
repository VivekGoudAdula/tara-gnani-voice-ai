"""Tests for Campaign audience preview, selection, snapshotting, and voice configuration."""

import ast
from datetime import datetime, timezone
from pathlib import Path
from bson import ObjectId
import httpx
import pytest
import pytest_asyncio
from app.core.config import settings
from app.core.db import get_db, init_db
from app.core.rate_limit import reset_rate_limits
from app.main import app
from app.services.campaign_variables import FORBIDDEN_LEAKED_KEYS, map_campaign_voice_variables, validate_voice_config

ALLOWLIST_PHONE = "+919876543210"


@pytest_asyncio.fixture(autouse=True)
async def setup_env():
    """Ensure database connection and test mode allowlist before tests."""
    await init_db()
    reset_rate_limits()
    settings.test_mode = True
    settings.test_allowlist = f"{ALLOWLIST_PHONE},+919999988888"
    yield
    reset_rate_limits()


async def get_auth(client: httpx.AsyncClient) -> tuple[dict[str, str], dict[str, str], str, str]:
    """Return auth headers and tenant IDs for Test Bank and Other Bank."""
    tb = (await client.post("/api/auth/login", json={"email": "employee@testbank.com", "password": settings.seed_password})).json()
    ob = (await client.post("/api/auth/login", json={"email": "employee@otherbank.com", "password": settings.seed_password})).json()
    return {"Authorization": f"Bearer {tb['access_token']}"}, {"Authorization": f"Bearer {ob['access_token']}"}, tb["user"]["tenant_id"], ob["user"]["tenant_id"]


def make_test_lead(tid: str, name: str, phone: str, consent: bool = True, dnd: bool = False, lang: str = "telugu") -> dict:
    """Helper returning a schema-valid lead document."""
    return {
        "tenant_id": tid, "name": name, "phone": phone, "consent": consent, "dnd": dnd,
        "language": lang, "city": "Hyderabad", "age": 30, "income": 500000.0, "segment": "SALARIED",
        "source": "branch", "created_at": datetime.now(timezone.utc),
    }


@pytest.mark.asyncio
async def test_audience_preview_and_selection():
    """Test 1: Audience preview counts add up, filter selects all, NOT_ELIGIBLE excluded by default."""
    transport = httpx.ASGITransport(app=app)
    db = get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tb_hdr, _, tid, _ = await get_auth(client)

        # Create product & campaign
        p_res = await db.products.insert_one({"tenant_id": tid, "name": "Quick Personal Loan", "code": "QPL", "active": True})
        pid = str(p_res.inserted_id)
        c_res = await client.post("/api/campaigns", headers=tb_hdr, json={
            "name": "QPL Campaign", "product_id": pid, "entity_type": "lead", "objective": "Drive personal loan growth",
        })
        assert c_res.status_code == 201
        cid = c_res.json()["id"]

        # Insert 3 test leads & product matches (HIGH eligible, MEDIUM eligible, LOW ineligible)
        now = datetime.now(timezone.utc)
        l1 = str((await db.leads.insert_one(make_test_lead(tid, "Lead One", ALLOWLIST_PHONE, True, False, "telugu"))).inserted_id)
        l2 = str((await db.leads.insert_one(make_test_lead(tid, "Lead Two", "+919000000001", False, True, "hindi"))).inserted_id)
        l3 = str((await db.leads.insert_one(make_test_lead(tid, "Lead Three", "+919876543211", True, False, "english"))).inserted_id)

        await db.product_matches.insert_many([
            {"tenant_id": tid, "product_id": pid, "entity_type": "lead", "entity_id": l1, "score": 85.0, "band": "HIGH", "eligibility": "ELIGIBLE", "is_latest": True, "created_at": now},
            {"tenant_id": tid, "product_id": pid, "entity_type": "lead", "entity_id": l2, "score": 60.0, "band": "MEDIUM", "eligibility": "ELIGIBLE", "is_latest": True, "created_at": now},
            {"tenant_id": tid, "product_id": pid, "entity_type": "lead", "entity_id": l3, "score": 30.0, "band": "LOW", "eligibility": "NOT_ELIGIBLE", "is_latest": True, "created_at": now},
        ])

        # Preview with eligibility=ALL -> returns all 3 including low and not-eligible
        prev = (await client.get(f"/api/campaigns/{cid}/audience/preview?eligibility=ALL", headers=tb_hdr)).json()
        assert prev["summary"]["total"] == 3
        assert prev["summary"]["by_band"]["HIGH"] == 1
        assert prev["summary"]["by_band"]["MEDIUM"] == 1
        assert prev["summary"]["by_band"]["LOW"] == 1
        assert prev["summary"]["by_eligibility"]["ELIGIBLE"] == 2
        assert prev["summary"]["by_eligibility"]["NOT_ELIGIBLE"] == 1
        assert prev["summary"]["would_be_blocked"] >= 1  # l2 has no consent + dnd + fake number

        # Filter mode select without confirm_override -> excludes NOT_ELIGIBLE by default
        sel_res = await client.put(f"/api/campaigns/{cid}/audience", headers=tb_hdr, json={"mode": "filter", "filter": {}})
        assert sel_res.status_code == 200
        assert sel_res.json()["recipient_count"] == 2

        # Selecting not-eligible without confirm_override fails
        fail_res = await client.put(f"/api/campaigns/{cid}/audience", headers=tb_hdr, json={"mode": "filter", "filter": {}, "include_not_eligible": True, "confirm_override": False})
        assert fail_res.status_code == 400

        # Cleanup inserted test documents
        await db.leads.delete_many({"_id": {"$in": [ObjectId(l1), ObjectId(l2), ObjectId(l3)]}})
        await db.product_matches.delete_many({"product_id": pid})


@pytest.mark.asyncio
async def test_snapshot_rescoring_immutability():
    """Test 2: Rescoring after selection does not mutate stored recipient scores."""
    transport = httpx.ASGITransport(app=app)
    db = get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tb_hdr, _, tid, _ = await get_auth(client)
        pid = str((await db.products.insert_one({"tenant_id": tid, "name": "Home Loan", "active": True})).inserted_id)
        cid = (await client.post("/api/campaigns", headers=tb_hdr, json={"name": "HL Outreach", "product_id": pid, "entity_type": "lead", "objective": "Home loans"})).json()["id"]

        now = datetime.now(timezone.utc)
        lid = str((await db.leads.insert_one(make_test_lead(tid, "Aditya Rao", ALLOWLIST_PHONE, True, False, "telugu"))).inserted_id)
        await db.product_matches.insert_one({"tenant_id": tid, "product_id": pid, "entity_type": "lead", "entity_id": lid, "score": 92.0, "band": "HIGH", "eligibility": "ELIGIBLE", "is_latest": True, "created_at": now})

        # Select recipient
        await client.put(f"/api/campaigns/{cid}/audience", headers=tb_hdr, json={"mode": "filter", "filter": {}})

        # Mutate product_matches (simulate rescoring)
        await db.product_matches.update_one({"entity_id": lid, "product_id": pid}, {"$set": {"score": 45.0, "band": "LOW"}})

        # Verify stored recipient snapshot is unchanged
        rcpt = await db.campaign_recipients.find_one({"campaign_id": cid, "entity_id": lid})
        assert rcpt["match_score"] == 92.0
        assert rcpt["band"] == "HIGH"

        # Cleanup
        await db.leads.delete_one({"_id": ObjectId(lid)})
        await db.product_matches.delete_many({"product_id": pid})


@pytest.mark.asyncio
async def test_config_versioning_and_validation():
    """Test 3: New version on every save, old versions retained, validation catches all forbidden cases."""
    transport = httpx.ASGITransport(app=app)
    db = get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tb_hdr, _, tid, _ = await get_auth(client)
        pid = str((await db.products.insert_one({"tenant_id": tid, "name": "Test Prod", "active": True})).inserted_id)
        cid = (await client.post("/api/campaigns", headers=tb_hdr, json={"name": "Cfg Test", "product_id": pid, "entity_type": "lead", "objective": "Test"})).json()["id"]

        valid_cfg = {
            "language_mode": "recipient", "tone": "Friendly",
            "opening_message": "Hello {{customer_name}}, calling from {{bank_name}} for {{product_name}}.",
            "objective": "Collect feedback", "success_condition": "Customer responds",
            "fallback_behaviour": "Say goodbye",
            "questions_to_collect": [{"field": "feedback_score", "question": "Rate from 1 to 5?", "required": True}],
            "retry_policy": {"max_attempts": 2, "interval_minutes": 30},
        }

        # Save version 2
        res2 = await client.put(f"/api/campaigns/{cid}/config/voice", headers=tb_hdr, json=valid_cfg)
        assert res2.status_code == 200
        assert res2.json()["version"] == 2

        # Check versions list has 2 versions
        vers = (await client.get(f"/api/campaigns/{cid}/config/voice/versions", headers=tb_hdr)).json()
        assert len(vers) == 2
        assert vers[0]["version"] == 2
        assert vers[1]["version"] == 1

        # Validation rejects unknown variables
        bad_var = dict(valid_cfg, opening_message="Hello {{unknown_variable_foo}}")
        assert len(validate_voice_config(bad_var)) > 0

        # Validation rejects OTP/PIN/CVV/Password in questions
        bad_q = dict(valid_cfg, questions_to_collect=[{"field": "customer_pin", "question": "Please provide your debit PIN", "required": True}])
        assert any("restricted credential" in e for e in validate_voice_config(bad_q))

        # Validation rejects promising approval in addendum
        bad_add = dict(valid_cfg, system_prompt_addendum="You can promise approval right on the call.")
        assert any("promises approval" in e for e in validate_voice_config(bad_add))

        # Validation rejects max_attempts out of range
        bad_ret = dict(valid_cfg, retry_policy={"max_attempts": 5})
        assert any("max_attempts" in e for e in validate_voice_config(bad_ret))


@pytest.mark.asyncio
async def test_preview_endpoint_and_leak_prevention():
    """Test 4 & 6: Preview endpoint is read-only, makes 0 comms, and never leaks sensitive credit keys."""
    transport = httpx.ASGITransport(app=app)
    db = get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tb_hdr, _, tid, _ = await get_auth(client)
        pid = str((await db.products.insert_one({"tenant_id": tid, "name": "Credit Card", "active": True})).inserted_id)
        cid = (await client.post("/api/campaigns", headers=tb_hdr, json={"name": "CC Preview", "product_id": pid, "entity_type": "lead", "objective": "Offer Card"})).json()["id"]

        comm_count_before = await db.communications.count_documents({})
        prev_res = await client.post(f"/api/campaigns/{cid}/preview", headers=tb_hdr, json={})
        assert prev_res.status_code == 200
        data = prev_res.json()
        assert "rendered_opening_message" in data
        assert "user_data_variables" in data
        assert await db.communications.count_documents({}) == comm_count_before  # 0 comms created

        # Assert no sensitive credit keys leaked in mapped variables
        vars_map = data["user_data_variables"]
        for key in FORBIDDEN_LEAKED_KEYS:
            assert key not in vars_map


def test_communication_module_has_no_campaign_imports():
    """Test 9: Verify communication module never imports anything from campaign code."""
    comm_dir = Path(__file__).resolve().parent.parent / "app" / "services" / "communication.py"
    content = comm_dir.read_text(encoding="utf-8")
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "campaign" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert "campaign" not in node.module
