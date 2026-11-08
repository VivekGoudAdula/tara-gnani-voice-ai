"""Customer schemas and attributes."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class CustomerResponse(BaseModel):
    """Internal bank customer details returned for authenticated tenant users."""

    id: str
    tenant_id: str
    name: str
    phone: str
    language: str
    city: str = ""
    age: int | None = None
    income: float | None = None
    segment: str = ""
    consent: bool = False
    dnd: bool = False
    source: str = "direct"
    import_batch_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    existing_products: list[str] = Field(default_factory=list)
    repayment_behaviour: str = "GOOD"
    financial_health: int = Field(ge=0, le=100, default=75)
    created_at: datetime | str

    model_config = ConfigDict(from_attributes=True, extra="ignore")
