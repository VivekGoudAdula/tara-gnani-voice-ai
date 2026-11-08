"""Authentication and authorization dependencies for FastAPI endpoints."""

from typing import Any
from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from app.core.db import get_db
from app.core.security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any]:
    """
    Validate the Bearer JWT token and extract authenticated user context.
    Ensures user is active and attaches tenant information.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    role = payload.get("role")

    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db = get_db()
    user_query: dict[str, Any] = {}
    if ObjectId.is_valid(str(user_id)):
        user_query = {"_id": ObjectId(str(user_id))}
    else:
        user_query = {"_id": str(user_id)}

    user = await db.users.find_one(user_query)
    if not user or not user.get("active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch tenant name
    tenant_query: dict[str, Any] = {}
    if ObjectId.is_valid(str(tenant_id)):
        tenant_query = {"_id": ObjectId(str(tenant_id))}
    else:
        tenant_query = {"_id": str(tenant_id)}

    tenant = await db.tenants.find_one(tenant_query)
    tenant_name = tenant.get("name", "Unknown Bank") if tenant else "Unknown Bank"

    return {
        "user_id": str(user["_id"]),
        "email": user["email"],
        "name": user.get("name", ""),
        "role": role,
        "tenant_id": str(tenant_id),
        "tenant_name": tenant_name,
    }


def require_role(allowed_role: str):
    """Dependency factory restricting access to specific user roles."""

    async def role_checker(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        user_role = current_user.get("role")
        if user_role != "SUPER_ADMIN" and user_role != allowed_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires {allowed_role} privileges",
            )
        return current_user

    return role_checker


def require_roles(allowed_roles: list[str]):
    """Dependency factory restricting access to any of the specified roles."""

    async def roles_checker(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        user_role = current_user.get("role")
        if user_role not in allowed_roles and user_role != "SUPER_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires one of {allowed_roles} privileges",
            )
        return current_user

    return roles_checker

