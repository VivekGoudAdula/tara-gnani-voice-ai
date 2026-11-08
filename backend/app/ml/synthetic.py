"""Synthetic data generator and ground-truth propensity functions for model training."""

import math
import numpy as np

RANDOM_SEED = 42

LEAD_SOURCES = ["partner_referral", "web_form", "campaign", "app_signup"]
EMPLOYMENT_TYPES = ["salaried", "self_employed", "other"]
REPAYMENT_LEVELS = {"GOOD": 2, "AVERAGE": 1, "POOR": 0}


def sigmoid(z: float) -> float:
    """Standard numerically stable logistic sigmoid."""
    if z < -40.0:
        return 0.0
    if z > 40.0:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


def generate_synthetic_leads(n_samples: int = 5000, seed: int = RANDOM_SEED) -> list[dict]:
    """Generate synthetic leads with realistic demographic-neutral features."""
    rng = np.random.default_rng(seed)
    records = []

    for i in range(n_samples):
        income = float(rng.lognormal(mean=10.9, sigma=0.65))
        income = max(18000.0, min(income, 450000.0))

        emp_type = rng.choice(EMPLOYMENT_TYPES, p=[0.70, 0.22, 0.08])
        emi_ratio = float(np.clip(rng.beta(a=2, b=5), 0.0, 0.70))
        source = rng.choice(LEAD_SOURCES, p=[0.30, 0.35, 0.20, 0.15])

        records.append({
            "income": income,
            "log_income": math.log(income),
            "employment_type": emp_type,
            "existing_emi_to_income": round(emi_ratio, 3),
            "source": source,
        })
    return records


def generate_synthetic_customers(n_samples: int = 5000, seed: int = RANDOM_SEED) -> list[dict]:
    """Generate synthetic customers with relationship and behavioral features."""
    rng = np.random.default_rng(seed + 100)
    records = []

    for i in range(n_samples):
        income = float(rng.lognormal(mean=11.1, sigma=0.60))
        income = max(25000.0, min(income, 500000.0))

        emp_type = rng.choice(EMPLOYMENT_TYPES, p=[0.72, 0.20, 0.08])
        emi_ratio = float(np.clip(rng.beta(a=2, b=5.5), 0.0, 0.65))
        fin_health = float(rng.integers(50, 96))
        repayment = rng.choice(["GOOD", "AVERAGE", "POOR"], p=[0.78, 0.17, 0.05])
        prod_count = int(rng.integers(1, 4))
        tenure = int(rng.integers(6, 121))

        records.append({
            "income": income,
            "log_income": math.log(income),
            "employment_type": emp_type,
            "existing_emi_to_income": round(emi_ratio, 3),
            "financial_health": fin_health,
            "repayment_behaviour": repayment,
            "existing_product_count": prod_count,
            "tenure_months": tenure,
        })
    return records


def compute_ground_truth_logit(row: dict, category: str, entity_type: str) -> float:
    """
    Compute deterministic ground-truth logit based on documented product affinity rules.

    Higher values correspond to higher likelihood of conversion/interest.
    """
    log_inc = row.get("log_income", 10.5)
    emi = row.get("existing_emi_to_income", 0.30)
    is_salaried = 1.0 if row.get("employment_type") == "salaried" else 0.0
    is_self = 1.0 if row.get("employment_type") == "self_employed" else 0.0

    if entity_type == "lead":
        src = row.get("source", "web_form")
        src_bonus = 0.30 if src in ("partner_referral", "web_form") else -0.15

        if category == "personal_loan":
            # Fits salaried individuals with manageable EMIs and middle-to-high income
            return -8.2 + 0.82 * log_inc - 3.2 * emi + 0.65 * is_salaried + src_bonus
        if category == "credit_card":
            # Rewards higher income, self-employed or salaried, low current debt
            return -7.8 + 0.75 * log_inc - 2.5 * emi + 0.35 * is_salaried + 0.30 * is_self + src_bonus
        if category == "home_loan":
            # Strong sensitivity to income, heavily penalized by existing EMI
            return -12.5 + 1.15 * log_inc - 4.5 * emi + 0.40 * is_salaried
        # Generic other
        return -7.0 + 0.65 * log_inc - 2.8 * emi + 0.30 * is_salaried + src_bonus

    # Customer entity
    fin_health = (row.get("financial_health", 75.0) - 50.0) / 45.0  # Normalized 0..1
    repay_ord = REPAYMENT_LEVELS.get(row.get("repayment_behaviour", "AVERAGE"), 1)
    repay_bonus = 0.80 if repay_ord == 2 else (-1.2 if repay_ord == 0 else 0.0)
    tenure_norm = min(row.get("tenure_months", 24) / 100.0, 1.0)
    prods = row.get("existing_product_count", 1)

    if category == "personal_loan":
        return -7.5 + 0.78 * log_inc - 3.0 * emi + 0.50 * is_salaried + 0.85 * fin_health + repay_bonus + 0.20 * tenure_norm
    if category == "credit_card":
        return -7.2 + 0.72 * log_inc - 2.4 * emi + 0.70 * fin_health + repay_bonus + 0.35 * prods
    if category == "home_loan":
        return -11.8 + 1.10 * log_inc - 4.2 * emi + 1.20 * fin_health + repay_bonus + 0.50 * tenure_norm
    # Generic other
    return -6.8 + 0.65 * log_inc - 2.6 * emi + 0.70 * fin_health + repay_bonus
