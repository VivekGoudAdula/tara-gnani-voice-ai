"""Router handling communication dispatch, status listing, and detail inspection."""

import math
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from app.core.db import build_tenant_query, doc_to_dict, get_db
from app.core.deps import get_current_user, require_roles
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.communication import (
    CommunicationDetail,
    CommunicationSendRequest,
    CommunicationSendResponse,
)
from app.services.communication import dispatch_communication

router = APIRouter(tags=["communication"])


@router.post(
    "/communication/send",
    response_model=CommunicationSendResponse,
    summary="Dispatch outbound communication to a lead or customer",
)
async def send_communication(
    request: CommunicationSendRequest,
    response: Response,
    current_user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> CommunicationSendResponse:
    """
    Dispatch an outbound communication through the configured channel provider.

    Enforces recipient identity resolution, compliance rules, idempotency, and tenant isolation.
    """
    db = get_db()
    status_code, data = await dispatch_communication(db, request, current_user)
    response.status_code = status_code
    return CommunicationSendResponse(**data)


@router.get(
    "/communications",
    response_model=PaginatedResponse[CommunicationDetail],
    summary="List tenant-scoped communication records",
)
async def list_communications(
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    channel: str | None = Query(None, description="Filter by channel"),
    campaign_id: str | None = Query(None, description="Filter by campaign ID"),
    recipient_id: str | None = Query(None, description="Filter by recipient ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse[CommunicationDetail]:
    """List communication logs scoped strictly to the authenticated user's tenant."""
    db = get_db()
    extra_criteria: dict[str, Any] = {}

    if status_filter:
        extra_criteria["status"] = status_filter.upper().strip()
    if channel:
        extra_criteria["channel"] = channel.lower().strip()
    if campaign_id:
        extra_criteria["campaign_id"] = campaign_id.strip()
    if recipient_id:
        extra_criteria["recipient_id"] = recipient_id.strip()

    query = build_tenant_query(current_user["tenant_id"], extra_criteria)

    total = await db.communications.count_documents(query)
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    skip = (page - 1) * page_size

    cursor = db.communications.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    items: list[CommunicationDetail] = []
    async for doc in cursor:
        items.append(CommunicationDetail(**doc_to_dict(doc)))  # type: ignore[arg-type]

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/communications/{id}",
    response_model=CommunicationDetail,
    summary="Retrieve tenant-scoped communication detail",
)
async def get_communication(
    id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CommunicationDetail:
    """Retrieve full details of a specific communication record scoped to caller's tenant."""
    db = get_db()
    target_id = ObjectId(id) if ObjectId.is_valid(id) else id
    query = build_tenant_query(current_user["tenant_id"], {"_id": target_id})

    doc = await db.communications.find_one(query)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Communication '{id}' not found for tenant",
        )

    return CommunicationDetail(**doc_to_dict(doc))  # type: ignore[arg-type]
