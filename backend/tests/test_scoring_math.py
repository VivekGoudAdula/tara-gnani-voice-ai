"""Mathematical and algorithmic tests for scoring explainability, determinism, monotonicity, and fairness."""

import random
from pathlib import Path
import pytest
from app.ml.inference import ARTIFACTS_DIR, load_model_artifact, score_propensity
from app.services.eligibility import evaluate_eligibility


def test_explanation_faithfulness():
    """Verify log-odds additivity within 1e-9 and probability consistency."""
    rng = random.Random(42)
    categories = ["personal_loan", "credit_card", "home_loan", "other"]

    for _ in range(20):
        etype = rng.choice(["lead", "customer"])
        cat = rng.choice(categories)
        product = {"category": cat, "name": f"Test {cat.replace('_', ' ').title()}"}

        if etype == "lead":
            entity = {
                "income": rng.uniform(15000, 200000),
                "employment_type": rng.choice(["salaried", "self_employed", "other"]),
                "existing_emi_to_income": rng.uniform(0.0, 0.7),
                "source": rng.choice(["partner_referral", "web_form", "campaign"]),
            }
        else:
            entity = {
                "income": rng.uniform(20000, 300000),
                "employment_type": rng.choice(["salaried", "self_employed", "other"]),
                "existing_emi_to_income": rng.uniform(0.0, 0.7),
                "financial_health": rng.uniform(30, 95),
                "repayment_behaviour": rng.choice(["GOOD", "AVERAGE", "POOR"]),
                "existing_products": ["Savings Account"] if rng.random() > 0.5 else [],
                "tenure_months": rng.randint(6, 120),
            }

        res = score_propensity(entity, product, etype)
        model, _ = load_model_artifact(cat, etype)

        # 1. Additive faithfulness in log-odds space: intercept + sum of contributions equals logit
        computed_logit = float(model["intercept"]) + sum(res["contributions_log_odds"].values())
        assert abs(computed_logit - res["raw_logit"]) < 1e-9

        # 2. Probability matches match_score / 100 within rounding precision (0.1 pp)
        assert abs(res["conversion_probability"] * 100.0 - res["match_score"]) <= 0.1


def test_determinism():
    """Ensure identical inputs produce identical scores, bands, and reason codes."""
    product = {"category": "personal_loan", "name": "Quick Cash Loan"}
    entity = {
        "income": 75000,
        "employment_type": "salaried",
        "existing_emi_to_income": 0.25,
        "source": "partner_referral",
    }

    run1 = score_propensity(entity, product, "lead")
    run2 = score_propensity(entity, product, "lead")

    assert run1["match_score"] == run2["match_score"]
    assert run1["conversion_probability"] == run2["conversion_probability"]
    assert run1["band"] == run2["band"]
    assert len(run1["reason_codes"]) == len(run2["reason_codes"])
    for r1, r2 in zip(run1["reason_codes"], run2["reason_codes"]):
        assert r1["code"] == r2["code"]
        assert r1["contribution_pp"] == r2["contribution_pp"]


def test_monotonicity():
    """Verify logical directional shifts: income (+), emi (-), repayment (GOOD > POOR)."""
    prod = {"category": "personal_loan", "name": "Instant Credit"}

    # 1. Raising income raises personal_loan fit
    lead_low_inc = {"income": 20000, "employment_type": "salaried", "existing_emi_to_income": 0.2, "source": "web_form"}
    lead_high_inc = {"income": 120000, "employment_type": "salaried", "existing_emi_to_income": 0.2, "source": "web_form"}
    s_low = score_propensity(lead_low_inc, prod, "lead")
    s_high = score_propensity(lead_high_inc, prod, "lead")
    assert s_high["match_score"] > s_low["match_score"]

    # 2. Raising existing_emi_to_income lowers fit
    lead_high_emi = {"income": 60000, "employment_type": "salaried", "existing_emi_to_income": 0.6, "source": "web_form"}
    lead_low_emi = {"income": 60000, "employment_type": "salaried", "existing_emi_to_income": 0.1, "source": "web_form"}
    assert score_propensity(lead_low_emi, prod, "lead")["match_score"] > score_propensity(lead_high_emi, prod, "lead")["match_score"]

    # 3. Customer POOR repayment scores strictly below GOOD
    cust_good = {"income": 80000, "employment_type": "salaried", "existing_emi_to_income": 0.2, "financial_health": 80, "repayment_behaviour": "GOOD", "tenure_months": 24}
    cust_poor = {"income": 80000, "employment_type": "salaried", "existing_emi_to_income": 0.2, "financial_health": 80, "repayment_behaviour": "POOR", "tenure_months": 24}
    assert score_propensity(cust_good, prod, "customer")["match_score"] > score_propensity(cust_poor, prod, "customer")["match_score"]


def test_fairness_guard():
    """Verify protected demographic characteristics are excluded from artifacts and ignored by inference."""
    protected_fields = {"language", "city", "location", "age", "name", "phone", "gender", "consent", "dnd"}

    for artifact_file in ARTIFACTS_DIR.glob("*.json"):
        data, _ = load_model_artifact(artifact_file.stem.split("_", 1)[1], artifact_file.stem.split("_", 1)[0])
        feature_names = {f["name"] for f in data["features"]}
        assert protected_fields.isdisjoint(feature_names), f"Protected fields found in {artifact_file.name}: {protected_fields.intersection(feature_names)}"

    # Changing protected fields must not change the match score
    prod = {"category": "personal_loan", "name": "Fair Lending Loan"}
    base_lead = {"income": 50000, "employment_type": "salaried", "existing_emi_to_income": 0.2, "source": "web_form"}
    mutated_lead = {**base_lead, "language": "tamil", "city": "Bengaluru", "age": 75, "gender": "Female", "name": "Ananya", "phone": "+919876543210"}

    res_base = score_propensity(base_lead, prod, "lead")
    res_mutated = score_propensity(mutated_lead, prod, "lead")
    assert res_base["match_score"] == res_mutated["match_score"]
    assert res_base["conversion_probability"] == res_mutated["conversion_probability"]


def test_eligibility_policy_rules():
    """Verify deterministic boundary evaluations, missing data handling, and held product exclusion."""
    rules = {
        "min_income": 30000,
        "min_age": 21,
        "max_age": 60,
        "max_emi_to_income": 0.5,
        "min_financial_health": 65,
        "allowed_repayment_behaviours": ["GOOD", "AVERAGE"],
        "exclude_if_holds_product": True,
    }
    product = {"name": "Titanium Credit Card", "eligibility_rules": rules}

    # Boundary tests
    pass_cust = {"income": 30000, "age": 21, "existing_emi_to_income": 0.5, "financial_health": 65, "repayment_behaviour": "GOOD", "existing_products": []}
    status, checks = evaluate_eligibility(pass_cust, product, "customer")
    assert status == "ELIGIBLE"
    assert all(c["passed"] for c in checks)

    # Fail boundary
    fail_cust = {**pass_cust, "income": 29999}
    status, checks = evaluate_eligibility(fail_cust, product, "customer")
    assert status == "NOT_ELIGIBLE"
    inc_chk = next(c for c in checks if c["rule"] == "min_income")
    assert not inc_chk["passed"]

    # Missing field -> not_evaluable -> NOT_ELIGIBLE
    missing_cust = {**pass_cust}
    del missing_cust["age"]
    status, checks = evaluate_eligibility(missing_cust, product, "customer")
    assert status == "NOT_ELIGIBLE"
    age_chk = next(c for c in checks if c["rule"] == "min_age")
    assert age_chk["value"] == "not_evaluable"
    assert "Missing" in age_chk["message"]

    # Customer already holding product -> NOT_ELIGIBLE
    held_cust = {**pass_cust, "existing_products": ["Titanium Credit Card"]}
    status, checks = evaluate_eligibility(held_cust, product, "customer")
    assert status == "NOT_ELIGIBLE"
    held_chk = next(c for c in checks if c["rule"] == "exclude_if_holds_product")
    assert not held_chk["passed"]
