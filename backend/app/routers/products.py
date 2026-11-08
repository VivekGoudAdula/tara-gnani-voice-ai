"""Products router providing tenant-scoped financial product catalog management."""

from datetime import datetime, timezone
import logging
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from app.core.db import build_tenant_query, doc_to_dict, get_db
from app.core.deps import get_current_user, require_role
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate

logger = logging.getLogger("tara.products")
router = APIRouter(prefix="/products", tags=["products"])


class ActiveTogglePayload(BaseModel):
    """Payload to toggle active state of a product."""

    active: bool = Field(..., description="Active status for product")


@router.get("", response_model=list[ProductResponse])
async def list_products(
    active: bool | None = Query(None, description="Filter by active status"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[ProductResponse]:
    """List financial products available for the authenticated user's tenant."""
    db = get_db()
    extra: dict[str, Any] = {}
    if active is not None:
        extra["active"] = active

    query = build_tenant_query(current_user["tenant_id"], extra)
    cursor = db.products.find(query).sort("name", 1)
    items = []
    async for doc in cursor:
        items.append(ProductResponse(**doc_to_dict(doc)))

    return items


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ProductResponse:
    """Retrieve single product by ID scoped strictly to caller's tenant."""
    db = get_db()
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    query = build_tenant_query(current_user["tenant_id"], {"_id": ObjectId(product_id)})
    doc = await db.products.find_one(query)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    return ProductResponse(**doc_to_dict(doc))


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> ProductResponse:
    """Create a new product in the catalog (SUPER_ADMIN only)."""
    db = get_db()
    now = datetime.now(timezone.utc)
    doc: dict[str, Any] = {
        "tenant_id": current_user["tenant_id"],
        "name": payload.name.strip(),
        "category": payload.category,
        "description": payload.description.strip(),
        "active": payload.active,
        "eligibility_rules": payload.eligibility_rules.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    result = await db.products.insert_one(doc)
    doc["_id"] = result.inserted_id
    doc["notice"] = "Product created. Run scoring to generate matches."

    await db.audit_log.insert_one({
        "tenant_id": current_user["tenant_id"],
        "actor_user_id": current_user.get("user_id", current_user.get("id")),
        "actor_email": current_user["email"],
        "action": "product_created",
        "entity_type": "product",
        "entity_id": str(result.inserted_id),
        "detail": {"name": payload.name, "category": payload.category},
        "at": now,
    })

    logger.info("Product '%s' (%s) created by %s", payload.name, str(result.inserted_id), current_user["email"])
    return ProductResponse(**doc_to_dict(doc))


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> ProductResponse:
    """Update product details or eligibility rules (SUPER_ADMIN only)."""
    db = get_db()
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    query = build_tenant_query(current_user["tenant_id"], {"_id": ObjectId(product_id)})
    existing = await db.products.find_one(query)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.category is not None:
        updates["category"] = payload.category
    if payload.description is not None:
        updates["description"] = payload.description.strip()
    if payload.active is not None:
        updates["active"] = payload.active
    if payload.eligibility_rules is not None:
        updates["eligibility_rules"] = payload.eligibility_rules.model_dump()

    await db.products.update_one({"_id": existing["_id"]}, {"$set": updates})
    updated_doc = await db.products.find_one({"_id": existing["_id"]})
    resp_dict = doc_to_dict(updated_doc)
    resp_dict["notice"] = "Rescore to apply updated eligibility rules."

    await db.audit_log.insert_one({
        "tenant_id": current_user["tenant_id"],
        "actor_user_id": current_user.get("user_id", current_user.get("id")),
        "actor_email": current_user["email"],
        "action": "product_updated",
        "entity_type": "product",
        "entity_id": str(existing["_id"]),
        "detail": {"updates": [k for k in updates.keys() if k != "updated_at"]},
        "at": updates["updated_at"],
    })

    logger.info("Product %s updated by %s", product_id, current_user["email"])
    return ProductResponse(**resp_dict)


@router.patch("/{product_id}/active", response_model=ProductResponse)
async def toggle_product_active(
    product_id: str,
    payload: ActiveTogglePayload,
    current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> ProductResponse:
    """Activate or deactivate a product (SUPER_ADMIN only)."""
    db = get_db()
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    query = build_tenant_query(current_user["tenant_id"], {"_id": ObjectId(product_id)})
    existing = await db.products.find_one(query)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    now = datetime.now(timezone.utc)
    await db.products.update_one({"_id": existing["_id"]}, {"$set": {"active": payload.active, "updated_at": now}})
    updated_doc = await db.products.find_one({"_id": existing["_id"]})
    resp_dict = doc_to_dict(updated_doc)
    resp_dict["notice"] = "Rescore to apply" if payload.active else "Product deactivated"

    await db.audit_log.insert_one({
        "tenant_id": current_user["tenant_id"],
        "actor_user_id": current_user.get("user_id", current_user.get("id")),
        "actor_email": current_user["email"],
        "action": "product_status_toggled",
        "entity_type": "product",
        "entity_id": str(existing["_id"]),
        "detail": {"active": payload.active},
        "at": now,
    })

    return ProductResponse(**resp_dict)
