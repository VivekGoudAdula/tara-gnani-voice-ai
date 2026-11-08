"""Authentication request and response schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Credentials required to authenticate."""

    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    """Payload to register a new workspace and root SUPER_ADMIN user."""

    workspace_name: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    # Disallow tampering by ignoring any extra fields
    model_config = ConfigDict(extra="ignore")


class UserInfo(BaseModel):
    """User profile data returned upon authentication."""

    id: str
    name: str
    email: EmailStr
    role: str
    tenant_id: str
    tenant_name: str

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    """JWT response after successful login or registration."""

    access_token: str
    token_type: str = "bearer"
    user: UserInfo

    model_config = ConfigDict(from_attributes=True)
