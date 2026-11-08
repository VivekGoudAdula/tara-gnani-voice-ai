"""Common schemas and response models for pagination and metadata."""

from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Metadata regarding pagination state."""

    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=100, default=20)
    total: int = Field(ge=0, default=0)
    total_pages: int = Field(ge=0, default=0)

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated list response wrapper."""

    items: list[T]
    pagination: PaginationMeta

    model_config = ConfigDict(from_attributes=True)
