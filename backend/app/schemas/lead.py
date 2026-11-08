"""Lead schemas and filter definitions."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class LeadResponse(BaseModel):
    """External lead details returned for authenticated tenant users."""

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
    created_at: datetime | str

    model_config = ConfigDict(from_attributes=True, extra="ignore")
