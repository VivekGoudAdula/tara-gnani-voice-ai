"""Governance & Audit router for compliance controls and immutable event logging."""

from datetime import datetime, timezone
import logging
from typing import Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from app.core.config import settings
from app.core.db import build_tenant_query, doc_to_dict, get_db
from app.core.deps import require_role
from app.schemas.common import PaginationMeta

logger = logging.getLogger("tara.audit")
router = APIRouter(prefix="/audit", tags=["audit"])


class ComplianceControls(BaseModel):
    """Active policy controls enforced at dispatch."""

    test_mode: bool
    calling_window: str
    contact_cap: str
    consent_required: bool
    dnd_check: bool
    label: str = "Policy controls enforced at dispatch"


class AuditResponse(BaseModel):
    """Audit query response with pagination and policy controls."""

    items: list[dict[str, Any]]
    pagination: PaginationMeta
    compliance_controls: ComplianceControls


@router.get("", response_model=AuditResponse)
async def list_audit_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = Query(None, description="Filter by event action"),
    entity_type: str | None = Query(None, description="Filter by target entity type"),
    actor: str | None = Query(None, description="Filter by actor email or ID"),
    start_date: str | None = Query(None, description="ISO start date filter"),
    end_date: str | None = Query(None, description="ISO end date filter"),
    current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> AuditResponse:
    """Retrieve tenant-scoped audit trail and active dispatch compliance controls (SUPER_ADMIN only)."""
    db = get_db()
    extra: dict[str, Any] = {}
    if action:
        extra["action"] = action
    if entity_type:
        extra["entity_type"] = entity_type
    if actor:
        extra["$or"] = [{"actor_email": actor}, {"actor_user_id": actor}]

    time_filter: dict[str, Any] = {}
    if start_date:
        try:
            time_filter["$gte"] = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if end_date:
        try:
            time_filter["$lte"] = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if time_filter:
        extra["at"] = time_filter

    query = build_tenant_query(current_user["tenant_id"], extra)
    total = await db.audit_log.count_documents(query)

    cursor = db.audit_log.find(query).sort("at", -1).skip((page - 1) * page_size).limit(page_size)
    items: list[dict[str, Any]] = []
    async for doc in cursor:
        d = doc_to_dict(doc)
        if "at" in d and isinstance(d["at"], datetime):
            d["at"] = d["at"].isoformat()
        items.append(d)

    controls = ComplianceControls(
        test_mode=settings.test_mode,
        calling_window=f"{settings.call_window_start} - {settings.call_window_end} IST",
        contact_cap=f"Max {settings.contact_cap_count} attempts / {settings.contact_cap_days} days",
        consent_required=True,
        dnd_check=True,
        label="Policy controls enforced at dispatch",
    )

    return AuditResponse(
        items=items,
        pagination=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size if total > 0 else 0,
        ),
        compliance_controls=controls,
    )
