"""Integration tests for CSV data import: validation, confirmation, normalization, and caps."""

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


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Ensure tests run strictly on tara_test database and rate limits are cleared."""
    await init_db(settings.mongo_db_name_test)
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.mark.asyncio
async def test_import_happy_path_and_idempotent_confirm():
    """Test 1: Valid rows land in leads with tenant_id from JWT, source=csv_import, import_batch_id set; second confirm is no-op."""
    db = get_db()
    t_id = str(ObjectId())
    user_id = str(ObjectId())
    token = create_access_token({"sub": user_id, "tenant_id": t_id, "role": "SUPER_ADMIN", "email": "admin@bank.com"})
    headers = {"Authorization": f"Bearer {token}"}

    csv_data = "name,phone,language,city,income,consent\nRahul Sharma,9876543210,hindi,Delhi,55000,yes\nPriya Patel,+91 9876543211,english,Mumbai,75000,true\n"
    mapping = json.dumps({"name": "name", "phone": "phone", "language": "language", "city": "city", "income": "income", "consent": "consent"})

    transport = httpx.ASGITransport(app=app)
    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Import Test Bank", "slug": f"import-{t_id}", "created_at": datetime.now(timezone.utc)})
        await db.users.insert_one({"_id": ObjectId(user_id), "tenant_id": t_id, "email": "admin@bank.com", "role": "SUPER_ADMIN", "active": True})

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("leads.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
            data = {"entity_type": "lead", "column_mapping": mapping}
            val_res = await client.post("/api/imports/validate", headers=headers, files=files, data=data)
            assert val_res.status_code == 200, val_res.text
            val_json = val_res.json()
            assert val_json["counts"]["valid"] == 2
            assert val_json["counts"]["rejected"] == 0
            batch_id = val_json["batch_id"]

            # Confirm batch
            conf_res = await client.post(f"/api/imports/{batch_id}/confirm", headers=headers, json={"attest_consent": True})
            assert conf_res.status_code == 200
            assert conf_res.json()["imported_count"] == 2

            # Verify in DB
            leads = await db.leads.find({"tenant_id": t_id, "import_batch_id": batch_id}).to_list(length=10)
            assert len(leads) == 2
            for lead in leads:
                assert lead["source"] == "csv_import"
                assert lead["tenant_id"] == t_id
                assert lead["import_batch_id"] == batch_id

            # Idempotent second confirm
            conf_res2 = await client.post(f"/api/imports/{batch_id}/confirm", headers=headers, json={"attest_consent": True})
            assert conf_res2.status_code == 200
            assert conf_res2.json()["imported_count"] == 2
            leads_after = await db.leads.count_documents({"tenant_id": t_id, "import_batch_id": batch_id})
            assert leads_after == 2  # No duplicate inserts
    finally:
        await db.tenants.delete_one({"_id": ObjectId(t_id)})
        await db.users.delete_one({"_id": ObjectId(user_id)})
        await db.leads.delete_many({"tenant_id": t_id})
        await db.import_batches.delete_many({"tenant_id": t_id})
        await db.import_batch_rows.delete_many({"tenant_id": t_id})


@pytest.mark.asyncio
async def test_consent_and_attestation_rules():
    """Test 2: Missing/garbled consent becomes false; attest_consent absent -> rejected."""
    db = get_db()
    t_id = str(ObjectId())
    user_id = str(ObjectId())
    token = create_access_token({"sub": user_id, "tenant_id": t_id, "role": "EMPLOYEE", "email": "emp@bank.com"})
    headers = {"Authorization": f"Bearer {token}"}

    csv_data = "name,phone,consent\nPerson One,9876500001,unknown_val\nPerson Two,9876500002,\n"
    mapping = json.dumps({"name": "name", "phone": "phone", "consent": "consent"})

    transport = httpx.ASGITransport(app=app)
    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Consent Bank", "slug": f"consent-{t_id}"})
        await db.users.insert_one({"_id": ObjectId(user_id), "tenant_id": t_id, "email": "emp@bank.com", "role": "EMPLOYEE", "active": True})

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("consent.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
            val_res = await client.post("/api/imports/validate", headers=headers, files=files, data={"entity_type": "lead", "column_mapping": mapping})
            assert val_res.status_code == 200
            val_json = val_res.json()
            assert val_json["flags"]["consent_missing"] == 2
            batch_id = val_json["batch_id"]

            # Missing attest_consent -> 400
            rej_conf = await client.post(f"/api/imports/{batch_id}/confirm", headers=headers, json={"attest_consent": False})
            assert rej_conf.status_code == 400

            # Successful attestation
            ok_conf = await client.post(f"/api/imports/{batch_id}/confirm", headers=headers, json={"attest_consent": True})
            assert ok_conf.status_code == 200

            leads = await db.leads.find({"tenant_id": t_id, "import_batch_id": batch_id}).to_list(length=10)
            assert len(leads) == 2
            for l in leads:
                assert l["consent"] is False  # Never default to true
    finally:
        await db.tenants.delete_one({"_id": ObjectId(t_id)})
        await db.users.delete_one({"_id": ObjectId(user_id)})
        await db.leads.delete_many({"tenant_id": t_id})
        await db.import_batches.delete_many({"tenant_id": t_id})
        await db.import_batch_rows.delete_many({"tenant_id": t_id})


@pytest.mark.asyncio
async def test_phone_normalization_and_duplicate_skipping():
    """Test 3: Phone normalization (+91) and duplicates within file and existing DB records skipped."""
    db = get_db()
    t_id = str(ObjectId())
    user_id = str(ObjectId())
    token = create_access_token({"sub": user_id, "tenant_id": t_id, "role": "SUPER_ADMIN", "email": "admin@bank.com"})
    headers = {"Authorization": f"Bearer {token}"}

    # Pre-insert existing lead with phone +919999900001
    existing_phone = "+919999900001"
    transport = httpx.ASGITransport(app=app)
    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Dup Bank", "slug": f"dup-{t_id}"})
        await db.users.insert_one({"_id": ObjectId(user_id), "tenant_id": t_id, "email": "admin@bank.com", "role": "SUPER_ADMIN", "active": True})
        await db.leads.insert_one({"tenant_id": t_id, "name": "Existing Lead", "phone": existing_phone, "source": "manual"})

        csv_data = (
            "name,phone\n"
            "Fresh Lead,9999900002\n"          # Valid -> +919999900002
            "Existing Dup,9999900001\n"         # Matches existing DB phone
            "In File Dup,9999900002\n"          # Matches row 1
            "Invalid Phone,12345\n"             # Bad length -> rejected
        )
        mapping = json.dumps({"name": "name", "phone": "phone"})

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            files = {"file": ("dups.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
            res = await client.post("/api/imports/validate", headers=headers, files=files, data={"entity_type": "lead", "column_mapping": mapping})
            assert res.status_code == 200
            data = res.json()
            assert data["counts"]["total"] == 4
            assert data["counts"]["valid"] == 1  # Only Fresh Lead
            assert data["counts"]["duplicates"] == 2  # Existing Dup & In File Dup
            assert data["counts"]["rejected"] == 3  # 2 duplicates + 1 invalid phone

            # Ensure existing lead record was NOT modified
            ex = await db.leads.find_one({"tenant_id": t_id, "phone": existing_phone})
            assert ex["name"] == "Existing Lead"
    finally:
        await db.tenants.delete_one({"_id": ObjectId(t_id)})
        await db.users.delete_one({"_id": ObjectId(user_id)})
        await db.leads.delete_many({"tenant_id": t_id})
        await db.import_batches.delete_many({"tenant_id": t_id})
        await db.import_batch_rows.delete_many({"tenant_id": t_id})


@pytest.mark.asyncio
async def test_caps_and_mapping_validation():
    """Test 4 & 5: Size/row caps, missing required columns (422), unmapped ignored."""
    db = get_db()
    t_id = str(ObjectId())
    user_id = str(ObjectId())
    token = create_access_token({"sub": user_id, "tenant_id": t_id, "role": "SUPER_ADMIN", "email": "admin@bank.com"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    try:
        await db.tenants.insert_one({"_id": ObjectId(t_id), "name": "Caps Bank", "slug": f"caps-{t_id}"})
        await db.users.insert_one({"_id": ObjectId(user_id), "tenant_id": t_id, "email": "admin@bank.com", "role": "SUPER_ADMIN", "active": True})

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Non-csv extension -> 400
            bad_ext = await client.post(
                "/api/imports/validate",
                headers=headers,
                files={"file": ("data.txt", io.BytesIO(b"name,phone\n"), "text/plain")},
                data={"entity_type": "lead", "column_mapping": json.dumps({"name": "name", "phone": "phone"})},
            )
            assert bad_ext.status_code == 400

            # Missing required phone mapping -> 422
            no_phone = await client.post(
                "/api/imports/validate",
                headers=headers,
                files={"file": ("test.csv", io.BytesIO(b"name,phone\nJohn,9876543210"), "text/csv")},
                data={"entity_type": "lead", "column_mapping": json.dumps({"name": "name"})},
            )
            assert no_phone.status_code == 422
            assert "phone" in no_phone.json()["detail"].lower()

            # Unmapped columns are ignored and valid row accepted
            unmapped = await client.post(
                "/api/imports/validate",
                headers=headers,
                files={"file": ("test.csv", io.BytesIO(b"name,phone,custom_col\nJohn,9876543210,secret"), "text/csv")},
                data={"entity_type": "lead", "column_mapping": json.dumps({"name": "name", "phone": "phone"})},
            )
            assert unmapped.status_code == 200
            assert unmapped.json()["counts"]["valid"] == 1
    finally:
        await db.tenants.delete_one({"_id": ObjectId(t_id)})
        await db.users.delete_one({"_id": ObjectId(user_id)})
        await db.import_batches.delete_many({"tenant_id": t_id})
