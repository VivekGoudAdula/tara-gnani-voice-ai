"""Pure Python runtime scoring, Platt calibration, and exact explainability engine."""

from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any
from app.ml.synthetic import sigmoid

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

REASON_TEMPLATES: dict[tuple[str, str], str] = {
    ("log_income", "positive"): "Monthly income ₹{raw_income:,.0f} is well above typical for this product",
    ("log_income", "negative"): "Monthly income ₹{raw_income:,.0f} is below optimal target for this product",
    ("existing_emi_to_income", "positive"): "Low existing debt burden ({value:.1%}) supports comfortable capacity",
    ("existing_emi_to_income", "negative"): "Existing debt burden of {value:.1%} lowers capacity",
    ("is_salaried", "positive"): "Salaried employment profile provides preferred income stability",
    ("is_salaried", "negative"): "Non-salaried profile carries stricter underwriting requirements",
    ("is_self_employed", "positive"): "Self-employed professional profile matches product requirements",
    ("is_self_employed", "negative"): "Self-employed risk adjustment slightly lowers fit score",
    ("financial_health", "positive"): "Strong financial health score ({value:.0f}/100) indicates high stability",
    ("financial_health", "negative"): "Financial health score ({value:.0f}/100) is below target band",
    ("repayment_score", "positive"): "Demonstrated good repayment track record enhances approval likelihood",
    ("repayment_score", "negative"): "Sub-optimal repayment history lowers likelihood of conversion",
    ("tenure_months", "positive"): "Long banking relationship tenure ({value} months) signals high loyalty",
    ("tenure_months", "negative"): "Short relationship tenure ({value} months) provides limited history",
    ("existing_product_count", "positive"): "Deep product adoption ({value} existing products) indicates strong engagement",
    ("existing_product_count", "negative"): "Limited existing product relationship ({value} held)",
    ("is_partner_referral", "positive"): "Inbound referral channel carries high historical affinity",
    ("is_partner_referral", "negative"): "Channel origin has standard baseline propensity",
    ("is_web_form", "positive"): "Direct digital inquiry indicates active product search intent",
    ("is_web_form", "negative"): "Application channel origin shows moderate intent",
}


@lru_cache(maxsize=16)
def load_model_artifact(category: str, entity_type: str) -> tuple[dict[str, Any], bool]:
    """Load model artifact from disk, falling back to 'other' if category unknown."""
    clean_cat = category.lower().strip() if category else "other"
    path = ARTIFACTS_DIR / f"{entity_type}_{clean_cat}.json"
    fallback = False

    if not path.exists():
        path = ARTIFACTS_DIR / f"{entity_type}_other.json"
        fallback = True

    data = json.loads(path.read_text(encoding="utf-8"))
    return data, fallback


def score_propensity(
    entity: dict[str, Any],
    product: dict[str, Any],
    entity_type: str,
    threshold_high: float = 70.0,
    threshold_low: float = 40.0,
) -> dict[str, Any]:
    """
    Score entity propensity for a product using calibrated logistic regression with exact explanations.

    Uses zero external ML libraries at runtime.
    """
    category = product.get("category", "other")
    model, is_fallback = load_model_artifact(category, entity_type)

    features_meta = model["features"]
    feat_map = {f["name"]: f for f in features_meta}
    imputed_features: list[str] = []
    raw_feature_values: dict[str, float] = {}

    # 1. Extract and impute features
    if entity_type == "lead":
        # log_income
        inc = entity.get("income")
        if inc is not None and float(inc) > 0:
            raw_feature_values["log_income"] = math.log(float(inc))
        else:
            raw_feature_values["log_income"] = feat_map["log_income"]["mean"]
            imputed_features.append("income")

        # existing_emi_to_income
        emi = entity.get("existing_emi_to_income")
        if emi is not None:
            raw_feature_values["existing_emi_to_income"] = float(emi)
        else:
            raw_feature_values["existing_emi_to_income"] = feat_map["existing_emi_to_income"]["mean"]
            imputed_features.append("existing_emi_to_income")

        # employment_type
        emp = entity.get("employment_type")
        if emp:
            raw_feature_values["is_salaried"] = 1.0 if emp == "salaried" else 0.0
            raw_feature_values["is_self_employed"] = 1.0 if emp == "self_employed" else 0.0
        else:
            raw_feature_values["is_salaried"] = feat_map["is_salaried"]["mean"]
            raw_feature_values["is_self_employed"] = feat_map["is_self_employed"]["mean"]
            imputed_features.append("employment_type")

        # source
        src = entity.get("source")
        if src:
            raw_feature_values["is_partner_referral"] = 1.0 if src == "partner_referral" else 0.0
            raw_feature_values["is_web_form"] = 1.0 if src == "web_form" else 0.0
        else:
            raw_feature_values["is_partner_referral"] = feat_map["is_partner_referral"]["mean"]
            raw_feature_values["is_web_form"] = feat_map["is_web_form"]["mean"]
            imputed_features.append("source")

    else:  # customer
        inc = entity.get("income")
        if inc is not None and float(inc) > 0:
            raw_feature_values["log_income"] = math.log(float(inc))
        else:
            raw_feature_values["log_income"] = feat_map["log_income"]["mean"]
            imputed_features.append("income")

        emi = entity.get("existing_emi_to_income")
        if emi is not None:
            raw_feature_values["existing_emi_to_income"] = float(emi)
        else:
            raw_feature_values["existing_emi_to_income"] = feat_map["existing_emi_to_income"]["mean"]
            imputed_features.append("existing_emi_to_income")

        emp = entity.get("employment_type")
        if emp:
            raw_feature_values["is_salaried"] = 1.0 if emp == "salaried" else 0.0
            raw_feature_values["is_self_employed"] = 1.0 if emp == "self_employed" else 0.0
        else:
            raw_feature_values["is_salaried"] = feat_map["is_salaried"]["mean"]
            raw_feature_values["is_self_employed"] = feat_map["is_self_employed"]["mean"]
            imputed_features.append("employment_type")

        fh = entity.get("financial_health")
        if fh is not None:
            raw_feature_values["financial_health"] = float(fh)
        else:
            raw_feature_values["financial_health"] = feat_map["financial_health"]["mean"]
            imputed_features.append("financial_health")

        rep = entity.get("repayment_behaviour")
        if rep:
            repay_map = {"GOOD": 2.0, "AVERAGE": 1.0, "POOR": 0.0}
            raw_feature_values["repayment_score"] = repay_map.get(str(rep).upper(), 1.0)
        else:
            raw_feature_values["repayment_score"] = feat_map["repayment_score"]["mean"]
            imputed_features.append("repayment_behaviour")

        prods = entity.get("existing_products")
        if prods is not None and isinstance(prods, list):
            raw_feature_values["existing_product_count"] = float(len(prods))
        else:
            raw_feature_values["existing_product_count"] = float(entity.get("existing_product_count", feat_map["existing_product_count"]["mean"]))

        ten = entity.get("tenure_months")
        if ten is not None:
            raw_feature_values["tenure_months"] = float(ten)
        else:
            raw_feature_values["tenure_months"] = feat_map["tenure_months"]["mean"]
            imputed_features.append("tenure_months")

    # 2. Standardize and calculate exact log-odds contributions
    intercept = float(model["intercept"])
    logit = intercept
    contributions_log_odds: dict[str, float] = {}

    for f in features_meta:
        fname = f["name"]
        x_val = raw_feature_values[fname]
        scale = f["scale"] if f["scale"] != 0.0 else 1.0
        std_val = (x_val - f["mean"]) / scale
        c_i = f["coef"] * std_val
        contributions_log_odds[fname] = c_i
        logit += c_i

    # 3. Platt calibration: P = 1 / (1 + exp(-(a * logit + b)))
    a_param = float(model["calibration"]["a"])
    b_param = float(model["calibration"]["b"])
    calib_logit = a_param * logit + b_param
    p_actual = sigmoid(calib_logit)

    # 4. Reason codes: compute contribution in percentage points
    raw_income = float(entity.get("income", math.exp(raw_feature_values["log_income"])))
    all_reasons = []

    for f in features_meta:
        fname = f["name"]
        c_i = contributions_log_odds[fname]
        # Logit if feature i were set to mean (i.e. std_val = 0, so c_i = 0)
        logit_without = logit - c_i
        p_without = sigmoid(a_param * logit_without + b_param)
        delta_pp = (p_actual - p_without) * 100.0

        direction = "positive" if delta_pp >= 0 else "negative"
        template = REASON_TEMPLATES.get((fname, direction), f"{fname} contributes {delta_pp:+.1f}pp")
        val = raw_feature_values[fname]

        text = template.format(value=val, raw_income=raw_income)
        all_reasons.append({
            "code": f"{fname.upper()}_{direction.upper()}",
            "feature": fname,
            "value": round(val, 2),
            "direction": direction,
            "contribution_pp": round(delta_pp, 2),
            "text": text,
        })

    # Pick top 3 positive and top 2 negative reasons by abs(contribution_pp)
    positives = sorted([r for r in all_reasons if r["direction"] == "positive"], key=lambda x: x["contribution_pp"], reverse=True)[:3]
    negatives = sorted([r for r in all_reasons if r["direction"] == "negative"], key=lambda x: x["contribution_pp"])[:2]
    selected_reasons = positives + negatives

    # 5. Final scores and propensity band
    match_score = round(p_actual * 100.0, 1)
    if match_score >= threshold_high:
        band = "HIGH"
    elif match_score >= threshold_low:
        band = "MEDIUM"
    else:
        band = "LOW"

    return {
        "match_score": match_score,
        "conversion_probability": round(p_actual, 4),
        "band": band,
        "reason_codes": selected_reasons,
        "imputed_features": imputed_features,
        "model_id": model["model_id"],
        "model_version": model["version"],
        "fallback_model": is_fallback,
        "feature_snapshot": raw_feature_values,
        "raw_logit": logit,
        "contributions_log_odds": contributions_log_odds,
    }
