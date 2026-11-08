"""Authentication router handling login, signup, and current user profile."""

from datetime import datetime, timezone
import logging
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import check_rate_limit
from app.core.sample_data import slugify
from app.core.security import create_access_token, get_password_hash, verify_password
from app.schemas.auth import LoginRequest, LoginResponse, SignupRequest, UserInfo

logger = logging.getLogger("tara.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest, request: Request) -> LoginResponse:
    """
    Authenticate user via email and password, returning a tenant-scoped JWT token.
    Enforces per-IP rate limiting.
    """
    check_rate_limit(request)
    db = get_db()
    email_clean = credentials.email.lower().strip()

    user = await db.users.find_one({"email": email_clean})
    if not user or not user.get("active", True):
        logger.warning("Failed login attempt for email: %s", email_clean)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not verify_password(credentials.password, user.get("password_hash", "")):
        logger.warning("Invalid password for user: %s", email_clean)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user_id_str = str(user["_id"])
    tenant_id_str = str(user["tenant_id"])
    role = user.get("role", "EMPLOYEE")

    # Fetch tenant name
    tenant_query: dict[str, Any] = {}
    if ObjectId.is_valid(tenant_id_str):
        tenant_query = {"_id": ObjectId(tenant_id_str)}
    else:
        tenant_query = {"_id": tenant_id_str}

    tenant = await db.tenants.find_one(tenant_query)
    tenant_name = tenant.get("name", "Unknown Bank") if tenant else "Unknown Bank"

    token_data = {
        "sub": user_id_str,
        "tenant_id": tenant_id_str,
        "role": role,
    }
    access_token = create_access_token(token_data)

    logger.info("Successful login for user %s at tenant %s", email_clean, tenant_name)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserInfo(
            id=user_id_str,
            name=user.get("name", ""),
            email=user["email"],
            role=role,
            tenant_id=tenant_id_str,
            tenant_name=tenant_name,
        ),
    )


@router.post("/signup", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, request: Request) -> LoginResponse:
    """
    Create a new isolated tenant and root SUPER_ADMIN user.
    Enforces rate limiting, email uniqueness, and strict tenant isolation.
    """
    check_rate_limit(request)
    db = get_db()
    email_clean = payload.email.lower().strip()

    # Reject duplicate email with generic 409
    existing_user = await db.users.find_one({"email": email_clean})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Derive unique slug for the new tenant
    base_slug = slugify(payload.workspace_name)
    candidate_slug = base_slug
    suffix = 1
    while await db.tenants.find_one({"slug": candidate_slug}):
        candidate_slug = f"{base_slug}-{suffix}"
        suffix += 1

    # Insert tenant
    now = datetime.now(timezone.utc)
    tenant_doc = {
        "name": payload.workspace_name.strip(),
        "slug": candidate_slug,
        "created_at": now,
    }
    tenant_result = await db.tenants.insert_one(tenant_doc)
    tenant_id_str = str(tenant_result.inserted_id)

    # Insert initial SUPER_ADMIN user
    password_hash = get_password_hash(payload.password)
    user_doc = {
        "tenant_id": tenant_result.inserted_id,
        "name": payload.name.strip(),
        "email": email_clean,
        "password_hash": password_hash,
        "role": "SUPER_ADMIN",
        "active": True,
        "created_at": now,
    }
    user_result = await db.users.insert_one(user_doc)
    user_id_str = str(user_result.inserted_id)

    token_data = {
        "sub": user_id_str,
        "tenant_id": tenant_id_str,
        "role": "SUPER_ADMIN",
    }
    access_token = create_access_token(token_data)

    logger.info("New workspace registered: %s (slug=%s)", payload.workspace_name, candidate_slug)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserInfo(
            id=user_id_str,
            name=payload.name.strip(),
            email=email_clean,
            role="SUPER_ADMIN",
            tenant_id=tenant_id_str,
            tenant_name=payload.workspace_name.strip(),
        ),
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user_profile(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UserInfo:
    """Return the currently authenticated user's profile and tenant details."""
    return UserInfo(
        id=current_user["user_id"],
        name=current_user["name"],
        email=current_user["email"],
        role=current_user["role"],
        tenant_id=current_user["tenant_id"],
        tenant_name=current_user["tenant_name"],
    )
