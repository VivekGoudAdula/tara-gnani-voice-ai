"""Customers router providing tenant-isolated customer management."""

import logging
import math
import re
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.db import build_tenant_query, doc_to_dict, get_db
from app.core.deps import get_current_user
from app.core.security import mask_phone
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.customer import CustomerResponse
from app.schemas.scoring import ProductMatchDetail

logger = logging.getLogger("tara.customers")
router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=PaginatedResponse[CustomerResponse])
async def list_customers(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    language: str | None = Query(None, description="Filter by language"),
    city: str | None = Query(None, description="Filter by city"),
    consent: bool | None = Query(None, description="Filter by consent flag"),
    dnd: bool | None = Query(None, description="Filter by DND status"),
    search: str | None = Query(None, description="Search by name or phone"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse[CustomerResponse]:
    """List internal bank customers scoped strictly to the authenticated tenant."""
    db = get_db()
    extra_criteria: dict[str, Any] = {}

    if language:
        extra_criteria["language"] = language.lower().strip()
    if city:
        extra_criteria["city"] = {"$regex": f"^{re.escape(city.strip())}$", "$options": "i"}
    if consent is not None:
        extra_criteria["consent"] = consent
    if dnd is not None:
        extra_criteria["dnd"] = dnd
    if search:
        search_clean = re.escape(search.strip())
        extra_criteria["$or"] = [
            {"name": {"$regex": search_clean, "$options": "i"}},
            {"phone": {"$regex": search_clean, "$options": "i"}},
        ]

    # Force tenant scoping
    query = build_tenant_query(current_user["tenant_id"], extra_criteria)

    total = await db.customers.count_documents(query)
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    skip = (page - 1) * page_size

    cursor = db.customers.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    items = []
    async for doc in cursor:
        items.append(CustomerResponse(**doc_to_dict(doc)))

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CustomerResponse:
    """
    Fetch a customer by ID.
    Returns 404 (not 403) if customer does not exist or belongs to another tenant.
    """
    db = get_db()
    id_matcher: Any = customer_id
    if ObjectId.is_valid(customer_id):
        id_matcher = {"$in": [customer_id, ObjectId(customer_id)]}

    query = build_tenant_query(current_user["tenant_id"], {"_id": id_matcher})
    doc = await db.customers.find_one(query)

    if not doc:
        logger.info("Customer %s not found for tenant %s", customer_id, current_user["tenant_id"])
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    logger.debug("Customer fetched: %s with phone %s", customer_id, mask_phone(doc.get("phone")))
    return CustomerResponse(**doc_to_dict(doc))


@router.get("/{customer_id}/matches", response_model=list[ProductMatchDetail])
async def get_customer_matches(
    customer_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[ProductMatchDetail]:
    """Retrieve all latest product matches for a customer sorted by match_score desc."""
    db = get_db()
    id_matcher: Any = customer_id
    if ObjectId.is_valid(customer_id):
        id_matcher = {"$in": [customer_id, ObjectId(customer_id)]}

    cust_query = build_tenant_query(current_user["tenant_id"], {"_id": id_matcher})
    customer = await db.customers.find_one(cust_query)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    matches_query = build_tenant_query(
        current_user["tenant_id"],
        {"entity_id": str(customer["_id"]), "is_latest": True},
    )
    cursor = db.product_matches.find(matches_query).sort("match_score", -1)
    results = []
    async for doc in cursor:
        d = doc_to_dict(doc)
        d["entity_name"] = customer.get("name")
        d["entity_language"] = customer.get("language")
        d["entity_city"] = customer.get("city")
        d["consent"] = customer.get("consent")
        d["dnd"] = customer.get("dnd")
        results.append(ProductMatchDetail(**d))
    return results
