"""Offline model training script generating calibrated JSON artifacts from synthetic ground truth."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.ml.synthetic import (
    RANDOM_SEED,
    compute_ground_truth_logit,
    generate_synthetic_customers,
    generate_synthetic_leads,
    sigmoid,
)

ARTIFACTS_DIR = backend_root / "app" / "ml" / "artifacts"
CATEGORIES = ["personal_loan", "credit_card", "home_loan", "other"]

EXCLUDED_FEATURES = [
    {"name": "language", "reason": "Proxy for protected characteristics; fairness exclusion"},
    {"name": "city", "reason": "Geographic proxy for demographics; fairness exclusion"},
    {"name": "age", "reason": "Restricted exclusively to deterministic policy rules, never ML score"},
    {"name": "gender", "reason": "Protected characteristic; fairness exclusion"},
    {"name": "name", "reason": "Personally Identifiable Information"},
    {"name": "phone", "reason": "Contact identifier; non-predictive"},
    {"name": "consent", "reason": "Regulatory compliance gate flag, enforced at dispatch only"},
    {"name": "dnd", "reason": "Regulatory compliance gate flag, enforced at dispatch only"},
]

LIMITATIONS = [
    "Trained on synthetic audience distribution for demonstration pipeline validation.",
    "Must be retrained on tenant bank's historical product conversion data before production usage.",
    "Ranks outreach propensity only; eligibility is strictly enforced by separate deterministic policy rules.",
]


def extract_lead_vector(row: dict) -> list[float]:
    """Extract lead features into numerical vector."""
    return [
        float(row["log_income"]),
        float(row["existing_emi_to_income"]),
        1.0 if row["employment_type"] == "salaried" else 0.0,
        1.0 if row["employment_type"] == "self_employed" else 0.0,
        1.0 if row["source"] == "partner_referral" else 0.0,
        1.0 if row["source"] == "web_form" else 0.0,
    ]


LEAD_FEATURE_NAMES = [
    "log_income", "existing_emi_to_income", "is_salaried",
    "is_self_employed", "is_partner_referral", "is_web_form",
]


def extract_customer_vector(row: dict) -> list[float]:
    """Extract customer features into numerical vector."""
    repay_map = {"GOOD": 2.0, "AVERAGE": 1.0, "POOR": 0.0}
    return [
        float(row["log_income"]),
        float(row["existing_emi_to_income"]),
        1.0 if row["employment_type"] == "salaried" else 0.0,
        1.0 if row["employment_type"] == "self_employed" else 0.0,
        float(row["financial_health"]),
        repay_map.get(row["repayment_behaviour"], 1.0),
        float(row["existing_product_count"]),
        float(row["tenure_months"]),
    ]


CUSTOMER_FEATURE_NAMES = [
    "log_income", "existing_emi_to_income", "is_salaried",
    "is_self_employed", "financial_health", "repayment_score",
    "existing_product_count", "tenure_months",
]


def compute_calibration_table(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> list[dict]:
    """Calculate 10-bin calibration table."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    table = []
    for i in range(n_bins):
        low, high = bins[i], bins[i + 1]
        mask = (y_prob >= low) & (y_prob < high if i < n_bins - 1 else y_prob <= high)
        bin_count = int(np.sum(mask))
        if bin_count > 0:
            pred_mean = float(np.mean(y_prob[mask]))
            true_mean = float(np.mean(y_true[mask]))
        else:
            pred_mean = round((low + high) / 2.0, 3)
            true_mean = 0.0
        table.append({
            "bin": f"{low:.1f}-{high:.1f}",
            "count": bin_count,
            "mean_predicted": round(pred_mean, 4),
            "fraction_positive": round(true_mean, 4),
        })
    return table


def train_single_model(category: str, entity_type: str, rows: list[dict], feat_names: list[str], extractor) -> dict:
    """Train logistic regression with Platt scaling calibration on synthetic holdout."""
    rng = np.random.default_rng(RANDOM_SEED + hash(category + entity_type) % 1000)

    # 1. Compute ground truth labels with logistic noise
    X_raw = np.array([extractor(r) for r in rows])
    logits = np.array([compute_ground_truth_logit(r, category, entity_type) for r in rows])
    noise = rng.normal(loc=0.0, scale=0.8, size=len(rows))
    noisy_probs = np.array([sigmoid(l + n) for l, n in zip(logits, noise)])
    y = (noisy_probs >= rng.uniform(0.0, 1.0, size=len(rows))).astype(int)

    # 2. Train/holdout split (80/20)
    X_train, X_val, y_train, y_val, l_train, l_val = train_test_split(
        X_raw, y, logits, test_size=0.20, random_state=RANDOM_SEED, stratify=y
    )

    # 3. Standardize features
    scaler = StandardScaler()
    X_train_std = scaler.fit_transform(X_train)
    X_val_std = scaler.transform(X_val)

    # 4. Fit L2 regularized Logistic Regression
    clf = LogisticRegression(penalty="l2", C=1.0, random_state=RANDOM_SEED, max_iter=500)
    clf.fit(X_train_std, y_train)

    # 5. Fit Platt Calibration on validation log-odds
    val_raw_logits = clf.decision_function(X_val_std)
    calibrator = LogisticRegression(penalty=None, solver="lbfgs")
    calibrator.fit(val_raw_logits.reshape(-1, 1), y_val)
    a_param = float(calibrator.coef_[0][0])
    b_param = float(calibrator.intercept_[0])

    # 6. Evaluate on holdout using calibrated probabilities
    calib_val_probs = calibrator.predict_proba(val_raw_logits.reshape(-1, 1))[:, 1]
    auc = float(roc_auc_score(y_val, calib_val_probs))
    brier = float(brier_score_loss(y_val, calib_val_probs))
    base_rate = float(np.mean(y_val))
    calib_table = compute_calibration_table(y_val, calib_val_probs)

    # 7. Build feature specs
    features_meta = []
    for idx, name in enumerate(feat_names):
        features_meta.append({
            "name": name,
            "type": "numeric" if "log" in name or "income" in name or "emi" in name or "health" in name else "binary",
            "mean": round(float(scaler.mean_[idx]), 5),
            "scale": round(float(scaler.scale_[idx]), 5),
            "coef": round(float(clf.coef_[0][idx]), 5),
        })

    model_hash = hashlib.sha256(f"{category}_{entity_type}_{RANDOM_SEED}".encode()).hexdigest()[:8]
    version = f"1.0.0-{model_hash}"

    return {
        "model_id": f"propensity_{entity_type}_{category}",
        "version": version,
        "category": category,
        "entity_type": entity_type,
        "features": features_meta,
        "intercept": round(float(clf.intercept_[0]), 5),
        "calibration": {"a": round(a_param, 5), "b": round(b_param, 5)},
        "metrics": {
            "auc": round(auc, 4),
            "brier_score": round(brier, 4),
            "base_rate": round(base_rate, 4),
            "holdout_samples": len(y_val),
            "calibration_table": calib_table,
            "disclaimer": "Synthetic data. Metrics demonstrate the pipeline, not real-world performance.",
        },
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_data": "synthetic",
        "ground_truth_description": "Documented logistic ground truth with Gaussian noise based on income, debt burden, and repayment.",
        "excluded_features": EXCLUDED_FEATURES,
        "limitations": LIMITATIONS,
    }


def main():
    """Generate training sets and train all 8 models."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    print("=== Training Propensity Models on Synthetic Data ===")

    leads = generate_synthetic_leads(n_samples=5000, seed=RANDOM_SEED)
    customers = generate_synthetic_customers(n_samples=5000, seed=RANDOM_SEED)

    for cat in CATEGORIES:
        # Lead model
        l_artifact = train_single_model(cat, "lead", leads, LEAD_FEATURE_NAMES, extract_lead_vector)
        l_path = ARTIFACTS_DIR / f"lead_{cat}.json"
        l_path.write_text(json.dumps(l_artifact, indent=2), encoding="utf-8")
        print(f"[+] Lead / {cat.ljust(14)} -> AUC: {l_artifact['metrics']['auc']:.3f}, Brier: {l_artifact['metrics']['brier_score']:.3f}, BaseRate: {l_artifact['metrics']['base_rate']:.3f} -> {l_path.name}")

        # Customer model
        c_artifact = train_single_model(cat, "customer", customers, CUSTOMER_FEATURE_NAMES, extract_customer_vector)
        c_path = ARTIFACTS_DIR / f"customer_{cat}.json"
        c_path.write_text(json.dumps(c_artifact, indent=2), encoding="utf-8")
        print(f"[+] Customer / {cat.ljust(14)} -> AUC: {c_artifact['metrics']['auc']:.3f}, Brier: {c_artifact['metrics']['brier_score']:.3f}, BaseRate: {c_artifact['metrics']['base_rate']:.3f} -> {c_path.name}")

    print("\n[+] All 8 model artifacts successfully generated in app/ml/artifacts/")


if __name__ == "__main__":
    main()
