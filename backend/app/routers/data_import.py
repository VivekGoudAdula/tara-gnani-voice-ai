"""Router for CSV data imports, validation, batch confirmation, and rejected rows export."""

import csv
from datetime import datetime, timedelta, timezone
import io
import json
import logging
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from app.core.db import build_tenant_query, doc_to_dict, get_db
from app.core.deps import get_current_user, require_roles
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.services.data_import import (
    auto_map_headers,
    mask_phone,
    sanitize_csv_cell,
    strip_control_chars,
    validate_row_fields,
)

logger = logging.getLogger("tara.data_import")
router = APIRouter(prefix="/imports", tags=["imports"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 5000
MAX_COLS = 50


class ConfirmImportRequest(BaseModel):
    """Payload to confirm an import batch."""

    attest_consent: bool = Field(..., description="DPDP Act consent attestation flag")


@router.get("/template")
async def get_import_template(
    entity_type: str = Query("lead", pattern="^(lead|customer)$"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Download a CSV template with example records."""
    output = io.StringIO()
    if entity_type == "customer":
        headers = [
            "name", "phone", "language", "city", "age", "income", "segment", "source",
            "employment_type", "existing_emi_to_income", "consent", "dnd",
            "financial_health", "repayment_behaviour", "existing_products", "tenure_months"
        ]
        rows = [
            ["Amit Verma", "9800000001", "hindi", "Delhi", "38", "75000", "Prime", "referral", "SALARIED", "0.20", "true", "false", "82", "GOOD", "savings_account;credit_card", "36"],
            ["Priya Rao", "9800000002", "telugu", "Hyderabad", "31", "90000", "Affluent", "in-app", "SALARIED", "0.10", "true", "false", "88", "GOOD", "savings_account;auto_loan", "24"],
        ]
    else:
        headers = [
            "name", "phone", "language", "city", "age", "income", "segment", "source",
            "employment_type", "existing_emi_to_income", "consent", "dnd"
        ]
        rows = [
            ["Ramesh Kumar", "9800000001", "hindi", "Lucknow", "34", "45000", "Retail", "website", "SALARIED", "0.25", "true", "false"],
            ["Sneha Patel", "9800000002", "english", "Ahmedabad", "29", "60000", "SME", "branch", "SELF_EMPLOYED", "0.15", "true", "false"],
        ]

    writer = csv.writer(output)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)

    filename = f"{entity_type}_import_template.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/validate")
async def validate_csv_import(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    column_mapping: str = Form(...),
    current_user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> dict[str, Any]:
    """Validate uploaded CSV file and generate an import preview with validation report."""
    db = get_db()
    if entity_type not in ("lead", "customer"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entity_type must be 'lead' or 'customer'")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .csv files are supported")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 5 MB limit")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be UTF-8 encoded")

    try:
        mapping = json.loads(column_mapping) if isinstance(column_mapping, str) else column_mapping
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid column_mapping JSON")

    # Validate required mapping columns
    for req in ("name", "phone"):
        if not mapping.get(req) or not str(mapping[req]).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Required column '{req}' is not mapped to any CSV header",
            )

    csv_file = io.StringIO(text)
    reader = csv.reader(csv_file)
    try:
        raw_headers = next(reader)
    except StopIteration:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file is empty")

    if len(raw_headers) > MAX_COLS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Column count exceeds maximum of {MAX_COLS}")

    header_indices = {h.strip(): idx for idx, h in enumerate(raw_headers)}
    for req in ("name", "phone"):
        mapped_col = mapping[req]
        if mapped_col not in header_indices:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Mapped header '{mapped_col}' for required field '{req}' was not found in CSV",
            )

    # Pre-fetch existing normalized phone numbers for this tenant & entity type
    tenant_id = current_user["tenant_id"]
    collection = db.leads if entity_type == "lead" else db.customers
    existing_cursor = collection.find(build_tenant_query(tenant_id), {"phone": 1})
    existing_phones = {doc.get("phone") async for doc in existing_cursor if doc.get("phone")}

    seen_phones_in_file: set[str] = set()
    rows_to_store: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    consent_missing_count = 0
    language_defaulted_count = 0
    valid_count = 0
    rejected_count = 0
    duplicate_count = 0
    total_count = 0

    for row_idx, row_values in enumerate(reader, start=2):
        if total_count >= MAX_ROWS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Row count exceeds limit of {MAX_ROWS} rows")
        total_count += 1

        # Extract mapped values
        row_dict: dict[str, Any] = {}
        for canon, mapped_h in mapping.items():
            if mapped_h in header_indices and header_indices[mapped_h] < len(row_values):
                row_dict[canon] = row_values[header_indices[mapped_h]]

        norm, errors, flags = validate_row_fields(row_dict, entity_type)
        if flags.get("consent_missing"):
            consent_missing_count += 1
        if flags.get("language_defaulted"):
            language_defaulted_count += 1

        is_dup = False
        if norm and "phone" in norm:
            phone = norm["phone"]
            if phone in seen_phones_in_file:
                is_dup = True
                duplicate_count += 1
                errors.append("Duplicate phone number in file")
            elif phone in existing_phones:
                is_dup = True
                duplicate_count += 1
                errors.append("Phone number already exists in workspace database")
            else:
                seen_phones_in_file.add(phone)

        if errors:
            rejected_count += 1
            if len(problems) < 50:
                masked_disp = mask_phone(norm["phone"]) if norm and "phone" in norm else "***"
                problems.append({
                    "row_number": row_idx,
                    "phone": masked_disp,
                    "name": strip_control_chars(row_dict.get("name", "")),
                    "reasons": errors,
                    "is_duplicate": is_dup,
                })
        else:
            valid_count += 1

        rows_to_store.append({
            "tenant_id": tenant_id,
            "row_number": row_idx,
            "raw_data": {k: mask_phone(v) if k == "phone" else strip_control_chars(v) for k, v in row_dict.items()},
            "normalized": norm if not errors else None,
            "errors": errors,
            "is_duplicate": is_dup,
        })

    batch_doc = {
        "tenant_id": tenant_id,
        "entity_type": entity_type,
        "file_name": strip_control_chars(file.filename),
        "file_size": len(content),
        "mapping": mapping,
        "status": "VALIDATED",
        "counts": {
            "total": total_count,
            "valid": valid_count,
            "rejected": rejected_count,
            "duplicates": duplicate_count,
            "imported": 0,
        },
        "flags": {
            "consent_missing": consent_missing_count,
            "language_defaulted": language_defaulted_count,
        },
        "uploaded_by": current_user["email"],
        "created_at": datetime.now(timezone.utc),
        "confirmed_at": None,
    }
    batch_res = await db.import_batches.insert_one(batch_doc)
    batch_id_str = str(batch_res.inserted_id)

    for item in rows_to_store:
        item["batch_id"] = batch_id_str
    if rows_to_store:
        await db.import_batch_rows.insert_many(rows_to_store)

    logger.info("Import batch %s validated: %d total, %d valid, %d rejected", batch_id_str, total_count, valid_count, rejected_count)

    return {
        "batch_id": batch_id_str,
        "file_name": batch_doc["file_name"],
        "entity_type": entity_type,
        "status": "VALIDATED",
        "counts": {
            "total": total_count,
            "valid": valid_count,
            "rejected": rejected_count,
            "duplicates": duplicate_count,
            "will_be_created": valid_count,
            "will_be_skipped": rejected_count,
        },
        "flags": batch_doc["flags"],
        "problems": problems,
    }


def _is_expired(created_at: datetime | None) -> bool:
    """Check if created_at is older than 24 hours (timezone-safe)."""
    if not created_at:
        return False
    dt = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    return dt < datetime.now(timezone.utc) - timedelta(hours=24)


@router.post("/{batch_id}/confirm")
async def confirm_csv_import(
    batch_id: str,
    payload: ConfirmImportRequest,
    current_user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> dict[str, Any]:
    """Commit valid, non-duplicate rows from a validated batch into leads/customers."""
    db = get_db()
    if not payload.attest_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must confirm records were collected with consent under the DPDP Act",
        )

    if not ObjectId.is_valid(batch_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")

    query = build_tenant_query(current_user["tenant_id"], {"_id": ObjectId(batch_id)})
    batch = await db.import_batches.find_one(query)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")

    # Idempotent check: if already imported, return previous result
    if batch.get("status") == "IMPORTED":
        return {
            "status": "success",
            "batch_id": str(batch["_id"]),
            "entity_type": batch["entity_type"],
            "imported_count": batch["counts"].get("imported", 0),
            "message": "Batch already confirmed and imported (idempotent)",
        }

    # Check expiration (24h)
    if _is_expired(batch.get("created_at")):
        await db.import_batches.update_one({"_id": batch["_id"]}, {"$set": {"status": "EXPIRED"}})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch has expired (older than 24h). Please re-upload.")

    tenant_id = current_user["tenant_id"]
    entity_type = batch["entity_type"]
    collection = db.leads if entity_type == "lead" else db.customers

    # Fetch valid rows
    row_cursor = db.import_batch_rows.find({
        "batch_id": str(batch["_id"]),
        "tenant_id": tenant_id,
        "is_duplicate": False,
        "errors": {"$size": 0},
    })

    docs_to_insert: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    async for row in row_cursor:
        if row.get("normalized"):
            doc = dict(row["normalized"])
            doc["tenant_id"] = tenant_id
            doc["source"] = "csv_import"
            doc["import_batch_id"] = str(batch["_id"])
            doc["created_at"] = now
            doc["updated_at"] = now
            docs_to_insert.append(doc)

    imported_count = len(docs_to_insert)
    # Insert in chunks of 500
    chunk_size = 500
    for i in range(0, len(docs_to_insert), chunk_size):
        chunk = docs_to_insert[i : i + chunk_size]
        if chunk:
            await collection.insert_many(chunk)

    # Update batch
    await db.import_batches.update_one(
        {"_id": batch["_id"]},
        {
            "$set": {
                "status": "IMPORTED",
                "confirmed_at": now,
                "counts.imported": imported_count,
            }
        },
    )

    # Audit log
    await db.audit_log.insert_one({
        "tenant_id": tenant_id,
        "actor_user_id": current_user.get("user_id", current_user.get("id")),
        "actor_email": current_user["email"],
        "action": "import_confirmed",
        "entity_type": entity_type,
        "entity_id": str(batch["_id"]),
        "detail": {
            "file_name": batch["file_name"],
            "imported_count": imported_count,
            "total_rows": batch["counts"]["total"],
        },
        "at": now,
    })

    logger.info("Import batch %s confirmed: %d rows inserted", str(batch["_id"]), imported_count)

    return {
        "status": "success",
        "batch_id": str(batch["_id"]),
        "entity_type": entity_type,
        "imported_count": imported_count,
        "message": f"Successfully imported {imported_count} {entity_type}s",
    }


@router.get("", response_model=PaginatedResponse[dict[str, Any]])
async def list_import_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse[dict[str, Any]]:
    """List historical import batches for the authenticated tenant."""
    db = get_db()
    query = build_tenant_query(current_user["tenant_id"])
    total = await db.import_batches.count_documents(query)

    cursor = db.import_batches.find(query).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    items: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    async for doc in cursor:
        d = doc_to_dict(doc)
        # Check expired on read
        if d.get("status") == "VALIDATED" and _is_expired(doc.get("created_at")):
            d["status"] = "EXPIRED"
            await db.import_batches.update_one({"_id": doc["_id"]}, {"$set": {"status": "EXPIRED"}})
        items.append(d)

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size if total > 0 else 0,
        ),
    )


@router.get("/{batch_id}")
async def get_import_batch_detail(
    batch_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve details for a single import batch."""
    db = get_db()
    if not ObjectId.is_valid(batch_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")

    query = build_tenant_query(current_user["tenant_id"], {"_id": ObjectId(batch_id)})
    doc = await db.import_batches.find_one(query)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")

    d = doc_to_dict(doc)
    if d.get("status") == "VALIDATED" and _is_expired(doc.get("created_at")):
        d["status"] = "EXPIRED"
        await db.import_batches.update_one({"_id": doc["_id"]}, {"$set": {"status": "EXPIRED"}})
    return d


@router.get("/{batch_id}/rejected.csv")
async def download_rejected_csv(
    batch_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Download rejected rows for an import batch with injection sanitization."""
    db = get_db()
    if not ObjectId.is_valid(batch_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")

    query = build_tenant_query(current_user["tenant_id"], {"_id": ObjectId(batch_id)})
    batch = await db.import_batches.find_one(query)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")

    rows_cursor = db.import_batch_rows.find({
        "batch_id": str(batch["_id"]),
        "tenant_id": current_user["tenant_id"],
        "$or": [{"errors": {"$ne": []}}, {"is_duplicate": True}],
    }).sort("row_number", 1)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["row_number", "phone", "name", "reasons", "is_duplicate"])

    async for r in rows_cursor:
        raw = r.get("raw_data", {})
        writer.writerow([
            r.get("row_number"),
            sanitize_csv_cell(raw.get("phone", "")),
            sanitize_csv_cell(raw.get("name", "")),
            sanitize_csv_cell("; ".join(r.get("errors", []))),
            r.get("is_duplicate", False),
        ])

    filename = f"rejected_rows_batch_{batch_id}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
