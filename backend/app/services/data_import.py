"""Service for parsing, validating, and normalizing CSV data imports."""

from datetime import datetime, timezone
import io
import re
from typing import Any

VALID_LANGUAGES = {"hindi": "hindi", "hi": "hindi", "telugu": "telugu", "te": "telugu", "english": "english", "en": "english"}
SYNONYMS: dict[str, list[str]] = {
    "phone": ["phone", "mobile", "msisdn", "contact", "phone_number", "mobile_number", "telephone"],
    "name": ["name", "full_name", "customer_name", "lead_name", "first_name"],
    "language": ["language", "lang", "pref_lang", "preferred_language"],
    "city": ["city", "location", "town"],
    "age": ["age", "years"],
    "income": ["income", "monthly_income", "salary", "earnings"],
    "segment": ["segment", "customer_segment", "lead_segment"],
    "source": ["source", "lead_source", "channel"],
    "employment_type": ["employment_type", "employment", "occupation", "job_type"],
    "existing_emi_to_income": ["existing_emi_to_income", "emi_ratio", "dti", "emi_to_income"],
    "consent": ["consent", "opt_in", "outreach_consent", "dpdp_consent"],
    "dnd": ["dnd", "do_not_disturb", "dnc"],
    "financial_health": ["financial_health", "cibil", "credit_score", "score"],
    "repayment_behaviour": ["repayment_behaviour", "repayment_behavior", "repayment"],
    "existing_products": ["existing_products", "current_products", "products"],
    "tenure_months": ["tenure_months", "tenure", "relationship_months"],
}


def sanitize_csv_cell(val: Any) -> Any:
    """Escape CSV formula injection characters (=, +, -, @)."""
    if isinstance(val, str) and val and val[0] in ("=", "+", "-", "@"):
        return f"'{val}"
    return val


def strip_control_chars(text: str) -> str:
    """Trim, enforce 120-char limit, and strip control characters."""
    if not text:
        return ""
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", str(text)).strip()
    return cleaned[:120]


def mask_phone(phone: str) -> str:
    """Return phone with middle digits masked."""
    if not phone or len(phone) < 8:
        return "***"
    return f"{phone[:4]}*****{phone[-3:]}"


def normalize_phone(raw: str) -> tuple[str | None, str | None]:
    """Normalize phone number to E.164 (+91 for 10-digit Indian numbers)."""
    if not raw:
        return None, "Phone number is missing"
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 10:
        return f"+91{digits}", None
    if len(digits) == 11 and digits.startswith("0"):
        return f"+91{digits[1:]}", None
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}", None
    if raw.strip().startswith("+") and 10 <= len(digits) <= 15:
        return f"+{digits}", None
    return None, f"Invalid phone format: must be valid 10-digit Indian or E.164 number"


def normalize_consent(val: Any) -> tuple[bool, bool]:
    """Parse consent strictly. Returns (consent_bool, was_flagged_missing)."""
    if val is None or (isinstance(val, str) and not val.strip()):
        return False, True
    s = str(val).strip().lower()
    if s in ("true", "yes", "y", "1"):
        return True, False
    if s in ("false", "no", "n", "0"):
        return False, False
    return False, True


def normalize_language(val: Any) -> tuple[str, bool]:
    """Map language to english/hindi/telugu, defaulting to english."""
    if not val or not str(val).strip():
        return "english", True
    clean = str(val).strip().lower()
    mapped = VALID_LANGUAGES.get(clean)
    if mapped:
        return mapped, False
    return "english", True


def auto_map_headers(headers: list[str]) -> dict[str, str]:
    """Auto-map CSV column headers using standard synonym dictionary."""
    mapping: dict[str, str] = {}
    normalized = [re.sub(r"[\s_-]+", "_", h.strip().lower()) for h in headers]
    for canon, syns in SYNONYMS.items():
        for idx, h in enumerate(normalized):
            if h in syns or h == canon:
                mapping[canon] = headers[idx]
                break
    return mapping


def validate_row_fields(row: dict[str, Any], entity_type: str) -> tuple[dict[str, Any] | None, list[str], dict[str, bool]]:
    """Validate and normalize a single record row."""
    errors: list[str] = []
    flags: dict[str, bool] = {"consent_missing": False, "language_defaulted": False}
    norm: dict[str, Any] = {}

    name = strip_control_chars(row.get("name", ""))
    if not name:
        errors.append("Name is required")
    else:
        norm["name"] = name

    phone_raw = str(row.get("phone", "")).strip()
    norm_phone, phone_err = normalize_phone(phone_raw)
    if phone_err:
        errors.append(phone_err)
    else:
        norm["phone"] = norm_phone

    lang, lang_def = normalize_language(row.get("language"))
    norm["language"] = lang
    if lang_def:
        flags["language_defaulted"] = True

    consent_bool, consent_flag = normalize_consent(row.get("consent"))
    norm["consent"] = consent_bool
    if consent_flag:
        flags["consent_missing"] = True

    dnd_val = str(row.get("dnd", "")).strip().lower()
    norm["dnd"] = dnd_val in ("true", "yes", "y", "1")

    for tf in ("city", "segment", "source", "employment_type"):
        if tf in row and str(row[tf]).strip():
            norm[tf] = strip_control_chars(str(row[tf]))

    if "income" in row and str(row["income"]).strip():
        try:
            inc = float(re.sub(r"[,\s₹]", "", str(row["income"])))
            if 0 <= inc <= 10_000_000:
                norm["income"] = inc
            else:
                errors.append(f"Income must be between 0 and 10,000,000 (got {inc})")
        except ValueError:
            errors.append(f"Income must be numeric (got {row['income']})")

    if "age" in row and str(row["age"]).strip():
        try:
            age = int(float(str(row["age"]).strip()))
            if 18 <= age <= 100:
                norm["age"] = age
            else:
                errors.append(f"Age must be between 18 and 100 (got {age})")
        except ValueError:
            errors.append(f"Age must be an integer (got {row['age']})")

    if "existing_emi_to_income" in row and str(row["existing_emi_to_income"]).strip():
        try:
            emi = float(str(row["existing_emi_to_income"]).strip())
            if 0.0 <= emi <= 1.0:
                norm["existing_emi_to_income"] = emi
            else:
                errors.append(f"EMI to income ratio must be between 0.0 and 1.0 (got {emi})")
        except ValueError:
            errors.append(f"EMI ratio must be numeric (got {row['existing_emi_to_income']})")

    if entity_type == "customer":
        if "financial_health" in row and str(row["financial_health"]).strip():
            try:
                fh = float(str(row["financial_health"]).strip())
                if 0 <= fh <= 100:
                    norm["financial_health"] = fh
                else:
                    errors.append(f"Financial health must be between 0 and 100 (got {fh})")
            except ValueError:
                errors.append("Financial health must be numeric")
        if "repayment_behaviour" in row and str(row["repayment_behaviour"]).strip():
            rb = str(row["repayment_behaviour"]).strip().upper()
            if rb in ("GOOD", "AVERAGE", "POOR"):
                norm["repayment_behaviour"] = rb
            else:
                errors.append(f"Repayment behaviour must be GOOD, AVERAGE, or POOR (got {rb})")
        if "tenure_months" in row and str(row["tenure_months"]).strip():
            try:
                tm = int(float(str(row["tenure_months"]).strip()))
                if tm >= 0:
                    norm["tenure_months"] = tm
                else:
                    errors.append("Tenure months must be non-negative")
            except ValueError:
                errors.append("Tenure months must be an integer")
        if "existing_products" in row and str(row["existing_products"]).strip():
            norm["existing_products"] = [strip_control_chars(p) for p in str(row["existing_products"]).split(";") if p.strip()]

    return (norm if not errors else None), errors, flags
