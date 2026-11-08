"""Outcomes router providing tenant-scoped summaries, calls lists, exports, and evidence reports."""

from datetime import datetime, timezone
import math
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.outcomes import OutcomesCallDetail, OutcomesCallItem, OutcomesSummaryResponse
from app.services.outcomes import get_outcomes_summary
from app.services.outcomes_calls import get_outcomes_call_detail, list_outcomes_calls
from app.services.outcomes_report import generate_evidence_markdown, generate_outcomes_export

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


@router.get("/summary", response_model=OutcomesSummaryResponse)
async def outcomes_summary(
    campaign_id: str | None = Query(None),
    test_run_label: str | None = Query(None),
    channel: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
) -> OutcomesSummaryResponse:
    """Retrieve tenant-scoped aggregate outcomes metrics and distributions."""
    db, tid = get_db(), user["tenant_id"]
    return await get_outcomes_summary(
        db, tid, campaign_id=campaign_id, test_run_label=test_run_label,
        channel=channel, date_from=date_from, date_to=date_to,
    )


@router.get("/calls", response_model=PaginatedResponse[OutcomesCallItem])
async def outcomes_calls(
    campaign_id: str | None = Query(None),
    test_run_label: str | None = Query(None),
    channel: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    outcome: str | None = Query(None),
    search: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse[OutcomesCallItem]:
    """Retrieve tenant-scoped paginated calls list with outcomes and resolved names."""
    db, tid = get_db(), user["tenant_id"]
    items, total = await list_outcomes_calls(
        db, tid, campaign_id=campaign_id, test_run_label=test_run_label,
        channel=channel, status_filter=status_filter, outcome=outcome,
        search=search, date_from=date_from, date_to=date_to,
        page=page, page_size=page_size,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.get("/calls/{id}", response_model=OutcomesCallDetail)
async def outcomes_call_detail(
    id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> OutcomesCallDetail:
    """Retrieve single call details with reconstructed timeline and honest transcript."""
    db, tid = get_db(), user["tenant_id"]
    is_super = user.get("role") == "SUPER_ADMIN"
    return await get_outcomes_call_detail(db, tid, id, is_super_admin=is_super)


@router.get("/export")
async def export_outcomes(
    format: Literal["csv", "json"] = Query("csv"),
    campaign_id: str | None = Query(None),
    test_run_label: str | None = Query(None),
    channel: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    outcome: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN"])),
) -> Any:
    """Export up to 5000 communication records (SUPER_ADMIN only). Audited."""
    db, tid, uid = get_db(), user["tenant_id"], user["user_id"]
    filters = {
        "campaign_id": campaign_id, "test_run_label": test_run_label, "channel": channel,
        "status": status_filter, "outcome": outcome, "date_from": date_from, "date_to": date_to,
    }
    result = await generate_outcomes_export(db, tid, filters, export_format=format)

    # Audit log the export
    count = len(result) if isinstance(result, list) else result.count("\n")
    await db.audit_log.insert_one({
        "tenant_id": tid, "actor_user_id": uid, "action": "outcomes_exported",
        "entity_type": "outcomes", "entity_id": tid,
        "detail": {"format": format, "filters": {k: str(v) for k, v in filters.items() if v is not None}, "row_count": count},
        "at": datetime.now(timezone.utc),
    })

    if format == "csv":
        return Response(
            content=result,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="outcomes_export.csv"'},
        )
    return result


@router.get("/evidence-report")
async def get_evidence_report(
    test_run_label: str = Query(..., min_length=1, description="Required test run tag"),
    user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN"])),
) -> Response:
    """Generate database-backed Markdown evidence report for a test run (SUPER_ADMIN only)."""
    db, tid, uid = get_db(), user["tenant_id"], user["user_id"]
    report_md = await generate_evidence_markdown(db, tid, test_run_label=test_run_label.strip())

    await db.audit_log.insert_one({
        "tenant_id": tid, "actor_user_id": uid, "action": "evidence_report_generated",
        "entity_type": "outcomes", "entity_id": test_run_label,
        "detail": {"test_run_label": test_run_label},
        "at": datetime.now(timezone.utc),
    })

    safe_name = test_run_label.strip().replace(" ", "_").replace("/", "-")
    return Response(
        content=report_md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="evidence_report_{safe_name}.md"'},
    )
