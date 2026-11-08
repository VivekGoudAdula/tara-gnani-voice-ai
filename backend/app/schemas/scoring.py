"""Schemas for scoring runs, product matching, explainability reason codes, and model cards."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScoringRunRequest(BaseModel):
    """Payload to initiate a scoring and product matching run."""

    entity_type: Literal["lead", "customer", "both"] = "both"
    product_ids: list[str] | None = None


class EligibilityCheckResult(BaseModel):
    """Evaluation result of a single deterministic policy rule."""

    rule: str
    passed: bool
    value: Any = None
    threshold: Any = None
    message: str

    model_config = ConfigDict(from_attributes=True)


class ReasonCode(BaseModel):
    """Explainability reason code quantifying feature contribution to fit score."""

    code: str
    feature: str
    value: Any
    direction: Literal["positive", "negative"]
    contribution_pp: float
    text: str

    model_config = ConfigDict(from_attributes=True)


class ProductMatchDetail(BaseModel):
    """Full detail model for a persisted product match record."""

    id: str
    tenant_id: str
    scoring_run_id: str
    is_latest: bool
    entity_type: Literal["lead", "customer"]
    entity_id: str
    product_id: str
    product_name: str
    match_score: float
    conversion_probability: float
    band: Literal["HIGH", "MEDIUM", "LOW"]
    eligibility: Literal["ELIGIBLE", "NOT_ELIGIBLE"]
    eligibility_checks: list[EligibilityCheckResult] = Field(default_factory=list)
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    imputed_features: list[str] = Field(default_factory=list)
    model_id: str
    model_version: str
    fallback_model: bool = False
    feature_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | str

    # Joined entity display attributes (No full phone)
    entity_name: str | None = None
    entity_language: str | None = None
    entity_city: str | None = None
    consent: bool | None = None
    dnd: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductMatchSummary(BaseModel):
    """Aggregate summary statistics for product matches."""

    total: int
    by_band: dict[str, int]
    by_eligibility: dict[str, int]
    avg_score: float
    thresholds: dict[str, float]

    model_config = ConfigDict(from_attributes=True)


class ScoringRunSummary(BaseModel):
    """Summary of a completed or in-progress scoring run."""

    id: str
    tenant_id: str
    entity_type: str
    product_ids: list[str]
    started_at: datetime | str
    finished_at: datetime | str | None = None
    entity_count: int = 0
    match_count: int = 0
    model_versions: dict[str, str] = Field(default_factory=dict)
    triggered_by: str
    thresholds: dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class TenantScoringSettings(BaseModel):
    """Tenant configuration for scoring propensity bands."""

    threshold_high: float = Field(default=70.0, ge=0.0, le=100.0)
    threshold_low: float = Field(default=40.0, ge=0.0, le=100.0)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "TenantScoringSettings":
        """Enforce 0 < threshold_low < threshold_high <= 100."""
        if not (0 < self.threshold_low < self.threshold_high <= 100):
            raise ValueError(
                f"Invalid thresholds: must satisfy 0 < threshold_low ({self.threshold_low}) < threshold_high ({self.threshold_high}) <= 100"
            )
        return self


class ModelCardResponse(BaseModel):
    """Transparent model card describing architecture, features, fairness, and metrics."""

    model_id: str
    version: str
    category: str
    entity_type: str
    features: list[dict[str, Any]]
    global_feature_importance: list[dict[str, Any]]
    intercept: float
    calibration: dict[str, Any]
    metrics: dict[str, Any]
    trained_at: str
    training_data: str
    ground_truth_description: str
    excluded_features: list[dict[str, str]]
    limitations: list[str]

    model_config = ConfigDict(from_attributes=True)
