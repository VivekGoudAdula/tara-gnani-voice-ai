"""Product models and eligibility rules schemas."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

ProductCategory = Literal["personal_loan", "credit_card", "home_loan", "other"]


class EligibilityRules(BaseModel):
    """Eligibility gating policy rules for financial products."""

    min_income: float | None = Field(default=None, ge=0)
    min_age: int | None = Field(default=None, ge=18, le=100)
    max_age: int | None = Field(default=None, ge=18, le=100)
    min_financial_health: float | None = Field(default=None, ge=0, le=100)
    allowed_repayment_behaviours: list[str] | None = Field(default=None)
    exclude_if_holds_product: bool = Field(default=True)
    max_emi_to_income: float | None = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_age_range(self) -> "EligibilityRules":
        """Validate min_age does not exceed max_age."""
        if self.min_age is not None and self.max_age is not None and self.min_age > self.max_age:
            raise ValueError(f"min_age ({self.min_age}) cannot exceed max_age ({self.max_age})")
        return self


class ProductCreate(BaseModel):
    """Schema for creating a new product."""

    name: str = Field(min_length=2, max_length=100)
    category: ProductCategory = Field(default="other")
    description: str = Field(default="", max_length=500)
    active: bool = True
    eligibility_rules: EligibilityRules = Field(default_factory=EligibilityRules)


class ProductUpdate(BaseModel):
    """Schema for updating an existing product."""

    name: str | None = Field(default=None, min_length=2, max_length=100)
    category: ProductCategory | None = None
    description: str | None = Field(default=None, max_length=500)
    active: bool | None = None
    eligibility_rules: EligibilityRules | None = None


class ProductResponse(BaseModel):
    """Product representation returned by the API."""

    id: str
    tenant_id: str
    name: str
    category: str = "other"
    description: str
    active: bool = True
    eligibility_rules: EligibilityRules
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    notice: str | None = None

    model_config = ConfigDict(from_attributes=True)
