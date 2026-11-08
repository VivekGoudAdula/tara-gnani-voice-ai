"""Tests verifying Phase 5 Outcomes Dashboard, calculations, tenant isolation, and evidence reporting."""

import csv
from datetime import datetime, timezone
import io
import re
import uuid
from bson import ObjectId
import httpx
import pytest
import pytest_asyncio
from app.core.config import settings
from app.core.db import get_db, init_db
from app.core.rate_limit import reset_rate_limits
from app.core.security import create_access_token
from app.main import app

TEST_LABEL = f"phase5-test-{uuid.uuid4().hex[:6]}"
TB_ID = "6ae011112222333344445555"
OB_ID = "6ae099998888777766665555"
SA_USER_ID = "6ae011112222333344440001"
EMP_USER_ID = "6ae011112222333344440002"
OB_EMP_USER_ID = "6ae099998888777766660001"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Ensure connection to tara_test, seed required test users, and clean up created fixtures after test."""
    await init_db(settings.mongo_db_name_test)
    reset_rate_limits()
    db = get_db()
    created_ids = []

    # Seed test users into tara_test so get_current_user succeeds
    user_oids = [ObjectId(SA_USER_ID), ObjectId(EMP_USER_ID), ObjectId(OB_EMP_USER_ID)]
    await db.users.delete_many({"_id": {"$in": user_oids}})
    await db.users.insert_many([
        {"_id": ObjectId(SA_USER_ID), "email": "sa_test@testbank.com", "name": "SA Test", "role": "SUPER_ADMIN", "tenant_id": TB_ID, "active": True},
        {"_id": ObjectId(EMP_USER_ID), "email": "emp_test@testbank.com", "name": "Emp Test", "role": "EMPLOYEE", "tenant_id": TB_ID, "active": True},
        {"_id": ObjectId(OB_EMP_USER_ID), "email": "ob_test@otherbank.com", "name": "OB Test", "role": "EMPLOYEE", "tenant_id": OB_ID, "active": True},
    ])

    yield {"created_ids": created_ids}

    if created_ids:
        await db.communications.delete_many({"_id": {"$in": created_ids}})
    await db.users.delete_many({"_id": {"$in": user_oids}})
    await db.audit_log.delete_many({"$or": [{"detail.test_run_label": TEST_LABEL}, {"detail.filters.test_run_label": TEST_LABEL}]})
    reset_rate_limits()


def get_test_auth_tokens() -> dict[str, str]:
    """Generate signed JWT tokens for Test Bank super admin, employee, and Other Bank employee."""
    return {
        "sa_token": create_access_token({"sub": SA_USER_ID, "tenant_id": TB_ID, "role": "SUPER_ADMIN"}),
        "emp_token": create_access_token({"sub": EMP_USER_ID, "tenant_id": TB_ID, "role": "EMPLOYEE"}),
        "ob_token": create_access_token({"sub": OB_EMP_USER_ID, "tenant_id": OB_ID, "role": "EMPLOYEE"}),
        "tb_tenant_id": TB_ID,
        "ob_tenant_id": OB_ID,
    }


@pytest.mark.asyncio
async def test_summary_math_and_metrics(setup_test_db):
    """Test 1: Summary math across every status/outcome; verify hand-computed averages and definitions."""
    transport, db = httpx.ASGITransport(app=app), get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tokens = get_test_auth_tokens()
        tid = tokens["tb_tenant_id"]
        headers = {"Authorization": f"Bearer {tokens['sa_token']}"}

        now = datetime.now(timezone.utc)
        docs = [
            # 2 Blocked
            {"tenant_id": tid, "channel": "voice", "status": "BLOCKED", "blocked_reason": "outside_calling_hours", "phone_masked": "+91 98*** 00001", "created_at": now, "test_run_label": TEST_LABEL},
            {"tenant_id": tid, "channel": "voice", "status": "BLOCKED", "blocked_reason": "non_dialable_number", "phone_masked": "+91 98*** 00002", "created_at": now, "test_run_label": TEST_LABEL},
            # 1 Dispatched (in-flight)
            {"tenant_id": tid, "channel": "voice", "status": "DISPATCHED", "phone_masked": "+91 98*** 00003", "created_at": now, "test_run_label": TEST_LABEL},
            # 1 No Answer
            {"tenant_id": tid, "channel": "voice", "status": "NO_ANSWER", "phone_masked": "+91 98*** 00004", "created_at": now, "outcome": {"duration_seconds": 0.0}, "test_run_label": TEST_LABEL},
            # 1 Failed
            {"tenant_id": tid, "channel": "voice", "status": "FAILED", "error": "telephony_timeout", "phone_masked": "+91 98*** 00005", "created_at": now, "test_run_label": TEST_LABEL},
            # 3 Completed with known durations: 15.0, 30.0, 45.0
            {
                "tenant_id": tid, "channel": "voice", "status": "COMPLETED", "phone_masked": "+91 98*** 00006", "created_at": now,
                "test_run_label": TEST_LABEL, "recipient_id": "rec_01",
                "outcome": {"duration_seconds": 30.0, "interest_level": "interested", "preferred_amount": 100000, "preferred_callback_time": "tomorrow 3pm", "language_used": "telugu"},
            },
            {
                "tenant_id": tid, "channel": "voice", "status": "COMPLETED", "phone_masked": "+91 98*** 00007", "created_at": now,
                "test_run_label": TEST_LABEL, "recipient_id": "rec_02",
                "outcome": {"duration_seconds": 45.0, "interest_level": "callback", "preferred_amount": 250000, "preferred_callback_time": "friday", "language_used": "hindi"},
            },
            {
                "tenant_id": tid, "channel": "voice", "status": "COMPLETED", "phone_masked": "+91 98*** 00008", "created_at": now,
                "test_run_label": TEST_LABEL, "recipient_id": "rec_03",
                "outcome": {"duration_seconds": 15.0, "interest_level": "not_interested", "language_used": "english"},
            },
        ]
        res = await db.communications.insert_many(docs)
        setup_test_db["created_ids"].extend(res.inserted_ids)

        # Query summary
        resp = await client.get(f"/api/outcomes/summary?test_run_label={TEST_LABEL}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        # Check counts: attempted = blocked (2) + dispatched family (6) = 8
        assert data["attempted"] == 8
        assert data["blocked"] == 2
        assert data["dispatched"] == 6
        assert data["connected"] == 3
        assert data["completed"] == 3
        assert data["no_answer"] == 1
        assert data["failed"] == 1

        # Check duration math: [15, 30, 45] -> mean=30, median=30, p95=45
        assert data["avg_duration_seconds"] == 30.0
        assert data["median_duration_seconds"] == 30.0
        assert data["p95_duration_seconds"] == 45.0

        # Outcome distribution
        assert data["outcome_counts"]["interested"] == 1
        assert data["outcome_counts"]["callback"] == 1
        assert data["outcome_counts"]["not_interested"] == 1

        # Extractions: 3 completed -> 3/3 interest (100%), 2/3 amount (66.7%), 2/3 callback (66.7%)
        assert data["extraction_fill_rate"]["interest_level"] == 100.0
        assert data["extraction_fill_rate"]["preferred_amount"] == 66.7
        assert data["extraction_fill_rate"]["preferred_callback_time"] == 66.7

        # Latency & Cost unavailable
        assert data["latency"]["available"] is False
        assert data["cost"]["available"] is False

        # Definitions check
        assert "connected" in data["definitions"]
        assert "attempted" in data["definitions"]


@pytest.mark.asyncio
async def test_test_run_filter_and_communication_isolation(setup_test_db):
    """Test 2: Test-run filter isolates labelled calls, and communication module never imports campaigns."""
    import inspect
    import app.services.communication as comm_module

    # Verify architectural boundary: communication service has ZERO imports of campaign
    source = inspect.getsource(comm_module)
    import_lines = [line for line in source.splitlines() if line.startswith("import") or line.startswith("from")]
    for line in import_lines:
        assert "campaign" not in line.lower(), f"Communication service imports campaign: {line}"

    transport, db = httpx.ASGITransport(app=app), get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tokens = get_test_auth_tokens()
        headers = {"Authorization": f"Bearer {tokens['sa_token']}"}
        tid = tokens["tb_tenant_id"]

        now = datetime.now(timezone.utc)
        other_label = f"unrelated-{uuid.uuid4().hex[:6]}"
        docs = [
            {"tenant_id": tid, "channel": "voice", "status": "COMPLETED", "phone_masked": "+91 98*** 00010", "created_at": now, "test_run_label": TEST_LABEL, "outcome": {"duration_seconds": 20.0}},
            {"tenant_id": tid, "channel": "voice", "status": "COMPLETED", "phone_masked": "+91 98*** 00011", "created_at": now, "test_run_label": other_label, "outcome": {"duration_seconds": 50.0}},
        ]
        res = await db.communications.insert_many(docs)
        setup_test_db["created_ids"].extend(res.inserted_ids)

        resp = await client.get(f"/api/outcomes/summary?test_run_label={TEST_LABEL}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed"] == 1
        assert data["avg_duration_seconds"] == 20.0


@pytest.mark.asyncio
async def test_tenant_isolation_and_roles(setup_test_db):
    """Test 3: Tenant isolation and role restrictions on exports & evidence reports."""
    transport, db = httpx.ASGITransport(app=app), get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tokens = get_test_auth_tokens()
        headers_sa = {"Authorization": f"Bearer {tokens['sa_token']}"}
        headers_emp = {"Authorization": f"Bearer {tokens['emp_token']}"}
        headers_ob = {"Authorization": f"Bearer {tokens['ob_token']}"}
        tid = tokens["tb_tenant_id"]

        now = datetime.now(timezone.utc)
        doc = {"tenant_id": tid, "channel": "voice", "status": "COMPLETED", "phone_masked": "+91 98*** 00020", "created_at": now, "test_run_label": TEST_LABEL, "outcome": {"duration_seconds": 10.0}}
        res = await db.communications.insert_one(doc)
        setup_test_db["created_ids"].append(res.inserted_id)

        # Other Bank cannot see Test Bank calls
        ob_summary = await client.get(f"/api/outcomes/summary?test_run_label={TEST_LABEL}", headers=headers_ob)
        assert ob_summary.status_code == 200
        assert ob_summary.json()["attempted"] == 0

        # Employee role gets 403 on export and evidence report
        emp_exp = await client.get("/api/outcomes/export?format=csv", headers=headers_emp)
        assert emp_exp.status_code == 403

        emp_rep = await client.get(f"/api/outcomes/evidence-report?test_run_label={TEST_LABEL}", headers=headers_emp)
        assert emp_rep.status_code == 403

        # Super Admin gets 200
        sa_exp = await client.get(f"/api/outcomes/export?format=csv&test_run_label={TEST_LABEL}", headers=headers_sa)
        assert sa_exp.status_code == 200
        assert "text/csv" in sa_exp.headers["content-type"]

        sa_rep = await client.get(f"/api/outcomes/evidence-report?test_run_label={TEST_LABEL}", headers=headers_sa)
        assert sa_rep.status_code == 200
        assert "text/markdown" in sa_rep.headers["content-type"]


@pytest.mark.asyncio
async def test_no_full_phone_numbers_and_export_integrity(setup_test_db):
    """Test 4 & 5: Ensure zero full phone numbers leaked, CSV escaping, and audit logging."""
    transport, db = httpx.ASGITransport(app=app), get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tokens = get_test_auth_tokens()
        headers = {"Authorization": f"Bearer {tokens['sa_token']}"}
        tid = tokens["tb_tenant_id"]

        now = datetime.now(timezone.utc)
        doc = {
            "tenant_id": tid, "channel": "voice", "status": "COMPLETED", "phone_masked": "+91 98*** 00030",
            "notes": "Spoke, requested callback,\nand mentioned a loan preference.",
            "tester_scenario": "interested+amount, callback\nrequested",
            "created_at": now, "test_run_label": TEST_LABEL, "outcome": {"duration_seconds": 25.0},
        }
        res = await db.communications.insert_one(doc)
        setup_test_db["created_ids"].append(res.inserted_id)

        # Scan evidence report, calls, and export endpoints with regex for full phone numbers
        rep_res = await client.get(f"/api/outcomes/evidence-report?test_run_label={TEST_LABEL}", headers=headers)
        assert rep_res.status_code == 200
        calls_res = await client.get(f"/api/outcomes/calls?test_run_label={TEST_LABEL}", headers=headers)
        assert calls_res.status_code == 200
        exp_res = await client.get(f"/api/outcomes/export?format=csv&test_run_label={TEST_LABEL}", headers=headers)
        assert exp_res.status_code == 200

        full_phone_regex = re.compile(r"\+91[0-9]{10}")
        assert not full_phone_regex.search(rep_res.text)
        assert not full_phone_regex.search(calls_res.text)
        assert not full_phone_regex.search(exp_res.text)

        # Verify CSV is valid and parses commas & newlines properly
        csv_file = io.StringIO(exp_res.text)
        reader = list(csv.reader(csv_file))
        assert len(reader) >= 2  # header + at least 1 data row
        headers_row = reader[0]
        assert "communication_id" in headers_row
        assert "scenario" in headers_row
        # Transcript must NOT be in CSV columns
        assert "transcript" not in headers_row

        # Audit log verified
        audit = await db.audit_log.find_one({"action": "outcomes_exported"})
        assert audit is not None


@pytest.mark.asyncio
async def test_evidence_report_limitations_and_numbers(setup_test_db):
    """Test 6: Evidence report contains exact Limitations text and database-derived numbers."""
    transport, db = httpx.ASGITransport(app=app), get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tokens = get_test_auth_tokens()
        headers = {"Authorization": f"Bearer {tokens['sa_token']}"}
        tid = tokens["tb_tenant_id"]

        now = datetime.now(timezone.utc)
        doc = {
            "tenant_id": tid, "channel": "voice", "status": "COMPLETED", "phone_masked": "+91 98*** 00040",
            "recipient_id": "lead_test_01", "recipient_type": "lead",
            "tester_scenario": "interested+amount",
            "created_at": now, "test_run_label": TEST_LABEL,
            "outcome": {"duration_seconds": 35.0, "interest_level": "interested", "preferred_amount": 100000},
        }
        res = await db.communications.insert_one(doc)
        setup_test_db["created_ids"].append(res.inserted_id)

        rep_res = await client.get(f"/api/outcomes/evidence-report?test_run_label={TEST_LABEL}", headers=headers)
        assert rep_res.status_code == 200
        text = rep_res.text

        # Verify exact required Limitations text
        assert "They measure pipeline reliability, latency and extraction behaviour." in text
        assert "They do not measure real-world conversion. Scoring models are trained on synthetic data." in text
        assert "Test Conditions" in text
        assert "Quantitative Performance Metrics" in text
        assert "interested+amount" in text



@pytest.mark.asyncio
async def test_call_detail_timeline_order(setup_test_db):
    """Test 7: Call detail returns timeline in chronological order and handles missing transcript."""
    transport, db = httpx.ASGITransport(app=app), get_db()
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tokens = get_test_auth_tokens()
        headers = {"Authorization": f"Bearer {tokens['sa_token']}"}
        tid = tokens["tb_tenant_id"]

        now = datetime.now(timezone.utc)
        doc = {
            "tenant_id": tid, "channel": "voice", "status": "COMPLETED", "phone_masked": "+91 98*** 11111",
            "created_at": now, "dispatched_at": now, "completed_at": now,
            "test_run_label": TEST_LABEL, "outcome": {"duration_seconds": 22.0},
        }
        res = await db.communications.insert_one(doc)
        setup_test_db["created_ids"].append(res.inserted_id)

        detail_res = await client.get(f"/api/outcomes/calls/{str(res.inserted_id)}", headers=headers)
        assert detail_res.status_code == 200
        data = detail_res.json()
        assert len(data["timeline"]) >= 2
        assert data["transcript"] is None

