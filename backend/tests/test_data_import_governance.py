"""Integration tests for CSV injection, tenant isolation, scoring coverage, and audit governance."""

from datetime import datetime, timezone
import io
import json
import pytest
import pytest_asyncio
import httpx
from bson import ObjectId
from app.core.config import settings
from app.core.db import close_db, get_db, init_db
from app.core.rate_limit import reset_rate_limits
from app.core.security import create_access_token
from app.main import app
from app.services.data_import import sanitize_csv_cell, strip_control_chars


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Ensure tests run strictly on tara_test database and rate limits are cleared."""
    await init_db(settings.mongo_db_name_test)
    reset_rate_limits()
    settings.test_mode = True
    yield
    reset_rate_limits()


@pytest.mark.asyncio
async def test_csv_injection_and_control_char_sanitization():
    """Test 6: Exports escape =,+,-,@ prefixed cells; import strips control characters."""
    # Unit checks on sanitize functions
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+cmd") == "'+cmd"
    assert sanitize_csv_cell("-calc") == "'-calc"
    assert sanitize_csv_cell("@SUM") == "'@SUM"
    assert sanitize_csv_cell("Normal Text") == "Normal Text"

    cleaned = strip_control_chars("Hello\x00\x08World\x1f")
    assert cleaned == "HelloWorld"
    assert "\x00" not in cleaned

    # Test download rejected rows escapes =,+,-,@
    db = get_db()
    t_id = str(ObjectId())
    user_id = str(ObjectId())
    batch_id = str(ObjectId())
    token = create_access_token({"sub": user_id, "tenant_id": t_id, "role": "SUPER_ADMIN", "email": "a@b.com"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Sanitize Bank", "slug": f"san-{t_id}"})
        await db.users.insert_one({"_id": ObjectId(user_id), "tenant_id": t_id, "email": "a@b.com", "role": "SUPER_ADMIN", "active": True})
        await db.import_batches.insert_one({"_id": ObjectId(batch_id), "tenant_id": t_id, "status": "VALIDATED", "created_at": datetime.now(timezone.utc)})
        await db.import_batch_rows.insert_one({
            "batch_id": batch_id,
            "tenant_id": t_id,
            "row_number": 2,
            "raw_data": {"name": "=SUM(A1:A10)", "phone": "+919876500000"},
            "errors": ["Some error"],
            "is_duplicate": False,
        })

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get(f"/api/imports/{batch_id}/rejected.csv", headers=headers)
            assert res.status_code == 200
            csv_text = res.text
            assert "'=SUM(A1:A10)" in csv_text
    finally:
        await db.tenants.delete_one({"_id": ObjectId(t_id)})
        await db.users.delete_one({"_id": ObjectId(user_id)})
        await db.import_batches.delete_one({"_id": ObjectId(batch_id)})
        await db.import_batch_rows.delete_many({"batch_id": batch_id})


@pytest.mark.asyncio
async def test_tenant_isolation_and_role_permissions():
    """Test 7: Other Bank cannot see/confirm Test Bank batches (404); EMPLOYEE cannot call sample-data; audit 403 for EMPLOYEE."""
    db = get_db()
    tb_id = str(ObjectId())
    ob_id = str(ObjectId())
    tb_admin = str(ObjectId())
    ob_admin = str(ObjectId())
    tb_emp = str(ObjectId())

    tb_admin_token = create_access_token({"sub": tb_admin, "tenant_id": tb_id, "role": "SUPER_ADMIN", "email": "tb_admin@bank.com"})
    ob_admin_token = create_access_token({"sub": ob_admin, "tenant_id": ob_id, "role": "SUPER_ADMIN", "email": "ob_admin@other.com"})
    tb_emp_token = create_access_token({"sub": tb_emp, "tenant_id": tb_id, "role": "EMPLOYEE", "email": "tb_emp@bank.com"})

    transport = httpx.ASGITransport(app=app)
    batch_id = str(ObjectId())
    try:
        await db.tenants.insert_many([
            {"_id": ObjectId(tb_id), "name": "Test Bank", "slug": f"tb-{tb_id}"},
            {"_id": ObjectId(ob_id), "name": "Other Bank", "slug": f"ob-{ob_id}"},
        ])
        await db.users.insert_many([
            {"_id": ObjectId(tb_admin), "tenant_id": tb_id, "email": "tb_admin@bank.com", "role": "SUPER_ADMIN", "active": True},
            {"_id": ObjectId(ob_admin), "tenant_id": ob_id, "email": "ob_admin@other.com", "role": "SUPER_ADMIN", "active": True},
            {"_id": ObjectId(tb_emp), "tenant_id": tb_id, "email": "tb_emp@bank.com", "role": "EMPLOYEE", "active": True},
        ])
        # Test Bank batch
        await db.import_batches.insert_one({"_id": ObjectId(batch_id), "tenant_id": tb_id, "status": "VALIDATED", "created_at": datetime.now(timezone.utc)})

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Other bank tries to view Test Bank batch -> 404
            res = await client.get(f"/api/imports/{batch_id}", headers={"Authorization": f"Bearer {ob_admin_token}"})
            assert res.status_code == 404

            # Other bank tries to confirm Test Bank batch -> 404
            res_conf = await client.post(f"/api/imports/{batch_id}/confirm", headers={"Authorization": f"Bearer {ob_admin_token}"}, json={"attest_consent": True})
            assert res_conf.status_code == 404

            # EMPLOYEE cannot call sample-data -> 403
            res_sample = await client.post("/api/workspace/sample-data", headers={"Authorization": f"Bearer {tb_emp_token}"})
            assert res_sample.status_code == 403

            # EMPLOYEE cannot call audit -> 403
            res_audit = await client.get("/api/audit", headers={"Authorization": f"Bearer {tb_emp_token}"})
            assert res_audit.status_code == 403

            # SUPER_ADMIN can call audit -> 200
            res_audit_admin = await client.get("/api/audit", headers={"Authorization": f"Bearer {tb_admin_token}"})
            assert res_audit_admin.status_code == 200
            assert "compliance_controls" in res_audit_admin.json()
    finally:
        await db.tenants.delete_many({"_id": {"$in": [ObjectId(tb_id), ObjectId(ob_id)]}})
        await db.users.delete_many({"_id": {"$in": [ObjectId(tb_admin), ObjectId(ob_admin), ObjectId(tb_emp)]}})
        await db.import_batches.delete_one({"_id": ObjectId(batch_id)})


@pytest.mark.asyncio
async def test_scoring_run_covers_imported_records_and_masked_phone():
    """Test 8 & 9: Scoring covers newly imported records; preview responses mask phones; TEST_MODE blocks dispatch."""
    db = get_db()
    t_id = str(ObjectId())
    user_id = str(ObjectId())
    p_id = str(ObjectId())
    token = create_access_token({"sub": user_id, "tenant_id": t_id, "role": "SUPER_ADMIN", "email": "scoring@bank.com"})
    headers = {"Authorization": f"Bearer {token}"}

    csv_data = "name,phone,income,age,consent\nAnanya Sen,9811122233,65000,32,yes\n"
    mapping = json.dumps({"name": "name", "phone": "phone", "income": "income", "age": "age", "consent": "consent"})

    transport = httpx.ASGITransport(app=app)
    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Score Bank", "slug": f"score-{t_id}"})
        await db.users.insert_one({"_id": ObjectId(user_id), "tenant_id": t_id, "email": "scoring@bank.com", "role": "SUPER_ADMIN", "active": True})
        await db.products.insert_one({
            "_id": ObjectId(p_id),
            "tenant_id": t_id,
            "name": "Auto Loan",
            "category": "auto_loan",
            "active": True,
            "eligibility_rules": {"min_income": 25000, "min_age": 21, "max_age": 60},
        })

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Validate & confirm import
            files = {"file": ("leads.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
            val_res = await client.post("/api/imports/validate", headers=headers, files=files, data={"entity_type": "lead", "column_mapping": mapping})
            assert val_res.status_code == 200
            val_json = val_res.json()
            # Test 9: Preview problem phone masking if present
            for p in val_json.get("problems", []):
                assert not p["phone"].startswith("+919811122233")
            batch_id = val_json["batch_id"]

            conf = await client.post(f"/api/imports/{batch_id}/confirm", headers=headers, json={"attest_consent": True})
            assert conf.status_code == 200

            # 2. Trigger scoring run
            score_res = await client.post("/api/scoring/run", headers=headers, json={"entity_type": "lead"})
            assert score_res.status_code == 200
            score_data = score_res.json()
            assert score_data["entity_count"] == 1
            assert score_data["match_count"] >= 1

            # Verify match in DB
            matches = await db.product_matches.find({"tenant_id": t_id, "is_latest": True}).to_list(length=10)
            assert len(matches) == 1
            assert matches[0]["product_id"] == p_id

            # 3. Test communication dispatch blocked by TEST_MODE allowlist
            disp_res = await client.post(
                "/api/communication/send",
                headers=headers,
                json={
                    "channel": "voice",
                    "recipient_ref": {"type": "lead", "id": str(matches[0]["entity_id"])},
                    "content": {"variables": {"name": "Ananya Sen"}},
                },
            )
            assert disp_res.status_code == 200
            disp_json = disp_res.json()
            assert disp_json["status"].lower() == "blocked"
            assert "allowlist" in disp_json["blocked_reason"].lower()
    finally:
        await db.tenants.delete_one({"_id": ObjectId(t_id)})
        await db.users.delete_one({"_id": ObjectId(user_id)})
        await db.products.delete_one({"_id": ObjectId(p_id)})
        await db.leads.delete_many({"tenant_id": t_id})
        await db.product_matches.delete_many({"tenant_id": t_id})
        await db.scoring_runs.delete_many({"tenant_id": t_id})
        await db.communications.delete_many({"tenant_id": t_id})
        await db.import_batches.delete_many({"tenant_id": t_id})
        await db.import_batch_rows.delete_many({"tenant_id": t_id})
        await db.audit_log.delete_many({"tenant_id": t_id})
