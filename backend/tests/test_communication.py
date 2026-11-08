"""Tests covering communication dispatch, compliance, mocks, idempotency, and Twilio status webhooks."""

from datetime import datetime, timezone
import json
import uuid
from zoneinfo import ZoneInfo
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
from app.services.communication import reconcile_unmatched_webhook

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")
ALLOWLISTED_PHONE = "+919876543210"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_env():
    """Configure settings and database before each test run."""
    await init_db()
    reset_rate_limits()
    settings.test_mode = True
    settings.voice_provider = "twilio_gnani"
    settings.compliance_check_frequency_cap = True
    settings.compliance_check_duplicate_in_flight = True
    settings.test_allowlist = f"{ALLOWLISTED_PHONE},+919999988888,invalid-num"
    settings.twilio_account_sid = "ACtest1234567890abcdef1234567890"
    settings.twilio_auth_token = "authtoken1234567890abcdef"
    settings.twilio_from_number = "+12025550199"
    settings.call_window_start, settings.call_window_end = "09:00", "21:00"
    yield
    reset_rate_limits()


async def get_auth_context(client: httpx.AsyncClient) -> tuple[dict[str, str], dict[str, str], str, str]:
    """Return auth headers and tenant IDs for Test Bank and Other Bank."""
    tb = (await client.post("/api/auth/login", json={"email": "employee@testbank.com", "password": settings.seed_password})).json()
    ob = (await client.post("/api/auth/login", json={"email": "employee@otherbank.com", "password": settings.seed_password})).json()
    return {"Authorization": f"Bearer {tb['access_token']}"}, {"Authorization": f"Bearer {ob['access_token']}"}, tb["user"]["tenant_id"], ob["user"]["tenant_id"]


async def create_test_lead(db, tid: str, phone: str = ALLOWLISTED_PHONE, consent: bool = True, dnd: bool = False) -> str:
    """Helper to insert a test lead and return ID."""
    doc = {
        "tenant_id": tid, "name": "Ravi Kumar", "phone": phone, "language": "telugu",
        "city": "Hyderabad", "age": 30, "income": 500000.0, "segment": "SALARIED", "source": "branch",
        "consent": consent, "dnd": dnd, "created_at": datetime.now(timezone.utc),
    }
    res = await db.leads.insert_one(doc)
    return str(res.inserted_id)


@pytest.mark.asyncio
async def test_happy_path_dispatch(monkeypatch):
    """Happy path: allowlisted lead, consent true, dnd false, inside window -> 202 DISPATCHED."""
    transport, db, captured = httpx.ASGITransport(app=app), get_db(), {}

    async def mock_send(self, req):
        captured["phone"] = req.recipient_phone
        captured["customer_name"] = req.variables.get("customer_name")
        return ProviderResult(success=True, provider_ref="CAmock123456789", status="DISPATCHED")

    monkeypatch.setattr(TwilioVoiceProvider, "send", mock_send)
    monkeypatch.setattr("app.services.compliance.datetime", type("MockDT", (), {"now": lambda tz=None: datetime(2026, 10, 26, 14, 0, 0, tzinfo=KOLKATA_TZ)}))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tb_hdr, _, tb_tid, _ = await get_auth_context(client)
        lead_id = await create_test_lead(db, tb_tid)
        resp = await client.post("/api/communication/send", json={"channel": "voice", "recipient_ref": {"type": "lead", "id": lead_id}}, headers=tb_hdr)
        assert resp.status_code == 202 and resp.json()["status"] == "DISPATCHED"
        assert captured["phone"] == ALLOWLISTED_PHONE and captured["customer_name"] == "Ravi Kumar"
        comm = await db.communications.find_one({"_id": ObjectId(resp.json()["communication_id"])})
        assert comm["phone_masked"] == "+9198******10" and "phone" not in comm
        await db.leads.delete_one({"_id": ObjectId(lead_id)})
        await db.communications.delete_one({"_id": comm["_id"]})


@pytest.mark.asyncio
async def test_compliance_rules(monkeypatch):
    """Verify each compliance gate check returns 200 with status BLOCKED and right reason."""
    transport, db, mock_called = httpx.ASGITransport(app=app), get_db(), False

    async def mock_send(self, req):
        nonlocal mock_called
        mock_called = True
        return ProviderResult(success=True, provider_ref="CAmock", status="DISPATCHED")

    monkeypatch.setattr(TwilioVoiceProvider, "send", mock_send)
    valid_time = datetime(2026, 10, 26, 14, 0, 0, tzinfo=KOLKATA_TZ)
    monkeypatch.setattr("app.services.compliance.datetime", type("MockDT", (), {"now": lambda tz=None: valid_time}))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tb_hdr, _, tb_tid, _ = await get_auth_context(client)
        lids: list[str] = []
        try:
            cases = [
                (await create_test_lead(db, tb_tid, phone="+919876599999"), "test_mode_not_allowlisted"),
                (await create_test_lead(db, tb_tid, phone="+919000012345"), "non_dialable_number"),
                (await create_test_lead(db, tb_tid, phone="invalid-num"), "invalid_phone"),
                (await create_test_lead(db, tb_tid, consent=False), "no_consent"),
                (await create_test_lead(db, tb_tid, dnd=True), "dnd"),
            ]
            for lid, reason in cases:
                lids.append(lid)
                r = await client.post("/api/communication/send", json={"channel": "voice", "recipient_ref": {"type": "lead", "id": lid}}, headers=tb_hdr)
                assert r.status_code == 200 and r.json()["blocked_reason"] == reason

            # Outside hours check
            monkeypatch.setattr("app.services.compliance.datetime", type("MockDT", (), {"now": lambda tz=None: datetime(2026, 10, 26, 3, 0, 0, tzinfo=KOLKATA_TZ)}))
            lid_night = await create_test_lead(db, tb_tid)
            lids.append(lid_night)
            r = await client.post("/api/communication/send", json={"channel": "voice", "recipient_ref": {"type": "lead", "id": lid_night}}, headers=tb_hdr)
            assert r.status_code == 200 and r.json()["blocked_reason"] == "outside_calling_hours"

            monkeypatch.setattr("app.services.compliance.datetime", type("MockDT", (), {"now": lambda tz=None: valid_time}))
            monkeypatch.setattr(settings, "contact_cap_count", 2)
            monkeypatch.setattr(settings, "contact_cap_days", 7)

            # Frequency cap check
            lid_cap = await create_test_lead(db, tb_tid)
            lids.append(lid_cap)
            for _ in range(2):
                await db.communications.insert_one({"tenant_id": tb_tid, "recipient_id": lid_cap, "status": "COMPLETED", "created_at": datetime.now(timezone.utc)})
            r = await client.post("/api/communication/send", json={"channel": "voice", "recipient_ref": {"type": "lead", "id": lid_cap}}, headers=tb_hdr)
            assert r.status_code == 200 and r.json()["blocked_reason"] == "frequency_cap"

            # Duplicate in-flight check
            lid_dup = await create_test_lead(db, tb_tid)
            lids.append(lid_dup)
            await db.communications.insert_one({"tenant_id": tb_tid, "recipient_id": lid_dup, "status": "IN_PROGRESS", "created_at": datetime.now(timezone.utc)})
            r = await client.post("/api/communication/send", json={"channel": "voice", "recipient_ref": {"type": "lead", "id": lid_dup}}, headers=tb_hdr)
            assert r.status_code == 200 and r.json()["blocked_reason"] == "duplicate_in_flight"

            assert mock_called is False
        finally:
            if lids:
                await db.leads.delete_many({"_id": {"$in": [ObjectId(x) for x in lids]}})
            await db.communications.delete_many({"tenant_id": tb_tid, "status": "BLOCKED"})


@pytest.mark.asyncio
async def test_tenant_isolation_and_unsupported_channels():
    """Verify cross-tenant dispatch returns 404, list query is isolated, and stubs return 501."""
    transport, db = httpx.ASGITransport(app=app), get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tb_hdr, ob_hdr, tb_tid, _ = await get_auth_context(client)
        tb_lead_id = await create_test_lead(db, tb_tid)
        try:
            assert (await client.post("/api/communication/send", json={"channel": "voice", "recipient_ref": {"type": "lead", "id": tb_lead_id}}, headers=ob_hdr)).status_code == 404
            for ch in ("whatsapp", "sms", "email"):
                assert (await client.post("/api/communication/send", json={"channel": ch, "recipient_ref": {"type": "lead", "id": tb_lead_id}}, headers=tb_hdr)).status_code == 501
            assert (await client.get("/api/communications", headers=ob_hdr)).status_code == 200
        finally:
            await db.leads.delete_one({"_id": ObjectId(tb_lead_id)})


@pytest.mark.asyncio
async def test_idempotency_key(monkeypatch):
    """Verify second identical send returns same record with status 200, provider called once."""
    transport, db, call_count = httpx.ASGITransport(app=app), get_db(), 0

    async def mock_send(self, req):
        nonlocal call_count
        call_count += 1
        return ProviderResult(success=True, provider_ref="CAidemp99", status="DISPATCHED")

    monkeypatch.setattr(TwilioVoiceProvider, "send", mock_send)
    monkeypatch.setattr("app.services.compliance.datetime", type("MockDT", (), {"now": lambda tz=None: datetime(2026, 10, 26, 14, 0, 0, tzinfo=KOLKATA_TZ)}))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tb_hdr, _, tb_tid, _ = await get_auth_context(client)
        lid, key = await create_test_lead(db, tb_tid), f"idemp_{uuid.uuid4().hex}"
        p = {"channel": "voice", "recipient_ref": {"type": "lead", "id": lid}, "idempotency_key": key}
        try:
            r1 = await client.post("/api/communication/send", json=p, headers=tb_hdr)
            assert r1.status_code == 202
            cid = r1.json()["communication_id"]

            r2 = await client.post("/api/communication/send", json=p, headers=tb_hdr)
            assert r2.status_code == 200 and r2.json()["communication_id"] == cid and call_count == 1
            await db.communications.delete_one({"_id": ObjectId(cid)})
        finally:
            await db.leads.delete_one({"_id": ObjectId(lid)})


@pytest.mark.asyncio
async def test_provider_failures(monkeypatch):
    """Verify provider error returns 502 with structured error detail."""
    transport, db = httpx.ASGITransport(app=app), get_db()
    monkeypatch.setattr("app.services.compliance.datetime", type("MockDT", (), {"now": lambda tz=None: datetime(2026, 10, 26, 14, 0, 0, tzinfo=KOLKATA_TZ)}))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tb_hdr, _, tb_tid, _ = await get_auth_context(client)
        lid = await create_test_lead(db, tb_tid)
        try:
            async def mock_fail(self, req):
                return ProviderResult(success=False, error="twilio_bad_gateway", status="FAILED")

            monkeypatch.setattr(TwilioVoiceProvider, "send", mock_fail)
            r1 = await client.post("/api/communication/send", json={"channel": "voice", "recipient_ref": {"type": "lead", "id": lid}}, headers=tb_hdr)
            assert r1.status_code == 502
            assert "twilio_bad_gateway" in r1.json()["detail"]["error"]
        finally:
            await db.leads.delete_one({"_id": ObjectId(lid)})


@pytest.mark.asyncio
async def test_webhooks_flow():
    """Verify Twilio status webhook mapping, monotonic state preservation, and reconciliation."""
    transport, db = httpx.ASGITransport(app=app), get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Mapping & updating matching communication
        exec_id = f"CA{uuid.uuid4().hex[:30]}"
        res = await db.communications.insert_one({"tenant_id": "tb", "status": "DISPATCHED", "provider_ref": exec_id, "created_at": datetime.now(timezone.utc)})
        cid = res.inserted_id

        # Send Twilio completed callback
        form_payload = {
            "CallSid": exec_id,
            "CallStatus": "completed",
            "CallDuration": "40",
            "To": "+919876543210",
            "From": "+12025550199",
        }
        res_wh = await client.post(
            "/api/webhooks/twilio/status",
            data=form_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert res_wh.status_code == 200
        c_up = await db.communications.find_one({"_id": cid})
        assert c_up["status"] == "COMPLETED" and c_up["outcome"]["duration_seconds"] == 40.0

        # Monotonic state protection: out-of-order in-progress event does not regress completed
        await client.post(
            "/api/webhooks/twilio/status",
            data={"CallSid": exec_id, "CallStatus": "in-progress"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert (await db.communications.find_one({"_id": cid}))["status"] == "COMPLETED"

        # Reconciliation: event arrives before provider_ref is saved
        pre_id = f"CA{uuid.uuid4().hex[:30]}"
        await client.post(
            "/api/webhooks/twilio/status",
            data={"CallSid": pre_id, "CallStatus": "completed", "CallDuration": "15"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        late_res = await db.communications.insert_one({"tenant_id": "tb", "status": "DISPATCHED", "provider_ref": pre_id})
        await reconcile_unmatched_webhook(db, str(late_res.inserted_id), pre_id, "tb")
        assert (await db.communications.find_one({"_id": late_res.inserted_id}))["status"] == "COMPLETED"

        # Cleanup
        await db.communications.delete_many({"_id": {"$in": [cid, late_res.inserted_id]}})
        await db.webhook_events.delete_many({"provider_ref": {"$in": [exec_id, pre_id]}})
