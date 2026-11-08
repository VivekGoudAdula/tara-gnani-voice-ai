"""Campaign voice configuration validation and provider variable mapping."""

from datetime import datetime
import re
from typing import Any
from fastapi import HTTPException, status

KNOWN_TEMPLATE_VARIABLES = {
    "customer_name",
    "lead_name",
    "product_name",
    "bank_name",
    "language",
    "tone",
    "objective",
    "preferred_amount",
}

FORBIDDEN_QUESTION_KEYWORDS = [
    "otp",
    "pin",
    "cvv",
    "cvc",
    "password",
    "full card number",
    "card number",
]

FORBIDDEN_ADDENDUM_KEYWORDS = [
    "promise approval",
    "guarantee approval",
    "guaranteed approval",
    "promise loan",
    "guarantee loan",
]

FORBIDDEN_LEAKED_KEYS = {
    "income",
    "monthly_income",
    "score",
    "match_score",
    "band",
    "eligibility",
    "financial_health",
    "reason",
    "reasons",
    "reason_codes",
}

SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
TEMPLATE_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def validate_voice_config(cfg: dict[str, Any]) -> list[str]:
    """Validate voice configuration schema and compliance guardrails."""
    errors: list[str] = []

    # 1. Objective non-empty
    objective = (cfg.get("objective") or "").strip()
    if not objective:
        errors.append("Objective must be non-empty.")

    # 2. Success condition non-empty
    success_cond = (cfg.get("success_condition") or "").strip()
    if not success_cond:
        errors.append("Success condition must be non-empty.")

    # 3. Opening message & template variables
    opening = (cfg.get("opening_message") or "").strip()
    if not opening:
        errors.append("Opening message must be non-empty.")
    else:
        found_vars = TEMPLATE_VAR_PATTERN.findall(opening)
        for var in found_vars:
            if var not in KNOWN_TEMPLATE_VARIABLES:
                errors.append(f"Unknown template variable '{{{{{var}}}}}'. Allowed: {', '.join(sorted(KNOWN_TEMPLATE_VARIABLES))}")

    # 4. Questions to collect
    questions = cfg.get("questions_to_collect") or []
    if not questions:
        errors.append("At least 1 question to collect is required.")
    elif len(questions) > 6:
        errors.append("Maximum 6 questions to collect are allowed.")

    seen_fields: set[str] = set()
    for idx, q in enumerate(questions):
        field = (q.get("field") or "").strip()
        q_text = (q.get("question") or "").strip()
        if not field:
            errors.append(f"Question #{idx + 1} field name is missing.")
        elif not SNAKE_CASE_PATTERN.match(field):
            errors.append(f"Question field '{field}' must be snake_case.")
        elif field in seen_fields:
            errors.append(f"Duplicate question field name '{field}'.")
        else:
            seen_fields.add(field)

        if not q_text:
            errors.append(f"Question #{idx + 1} text is missing.")

        # Guardrail on sensitive credentials in questions
        combined_q = f"{field} {q_text}".lower()
        for kw in FORBIDDEN_QUESTION_KEYWORDS:
            if kw in combined_q:
                errors.append(f"Compliance violation: Question asks for restricted credential '{kw}'.")

    # 5. System prompt addendum guardrails
    addendum = (cfg.get("system_prompt_addendum") or "").strip()
    if len(addendum) > 1500:
        errors.append("System prompt addendum exceeds 1500 characters maximum.")
    for kw in FORBIDDEN_ADDENDUM_KEYWORDS:
        if kw in addendum.lower():
            errors.append(f"Compliance violation: Addendum promises approval '{kw}'.")

    # 6. Retry policy attempts
    retry = cfg.get("retry_policy") or {}
    max_attempts = retry.get("max_attempts", 1)
    if not (1 <= int(max_attempts) <= 3):
        errors.append("Retry policy max_attempts must be between 1 and 3.")

    return errors


def enforce_valid_voice_config(cfg: dict[str, Any]) -> None:
    """Validate voice configuration and raise HTTP 422 if invalid."""
    errors = validate_voice_config(cfg)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Voice configuration validation failed", "errors": errors},
        )


def render_opening_message(template: str, variables: dict[str, Any]) -> str:
    """Safely replace {{variable}} in opening message template."""
    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1).strip()
        val = variables.get(var_name)
        return str(val) if val is not None else ""

    return TEMPLATE_VAR_PATTERN.sub(replacer, template)


def map_campaign_voice_variables(
    config: dict[str, Any],
    recipient: dict[str, Any],
    product_name: str,
    bank_name: str,
) -> dict[str, str]:
    """
    Construct exact variable map dispatched to provider.

    Strictly guarantees sensitive scoring and credit fields are NEVER leaked.
    """
    # 1. Resolve name and language
    rcpt_name = recipient.get("name", "Valued Customer")
    lang_mode = config.get("language_mode", "recipient")
    if lang_mode == "fixed":
        chosen_lang = config.get("language", "telugu")
    else:
        chosen_lang = recipient.get("language", "telugu")

    tone = config.get("tone", "Professional")
    objective = config.get("objective", "")
    addendum = config.get("system_prompt_addendum", "")
    success_cond = config.get("success_condition", "")
    fallback = config.get("fallback_behaviour", "")

    # Format questions to collect
    q_items = config.get("questions_to_collect", [])
    q_strs: list[str] = []
    for q in q_items:
        req_tag = " (required)" if q.get("required", True) else " (optional)"
        q_strs.append(f"{q.get('field')}: {q.get('question')}{req_tag}")
    questions_formatted = "; ".join(q_strs)

    # Format conversation steps
    steps = config.get("conversation_steps", [])
    steps_formatted = " | ".join(f"{s.get('key')}: {s.get('text')}" for s in steps if s.get("text"))

    # Initial template context for rendering opening message
    template_vars: dict[str, Any] = {
        "customer_name": rcpt_name,
        "lead_name": rcpt_name,
        "product_name": product_name,
        "bank_name": bank_name,
        "language": chosen_lang,
        "tone": tone,
        "objective": objective,
        "preferred_amount": recipient.get("preferred_amount", ""),
    }

    rendered_opening = render_opening_message(config.get("opening_message", ""), template_vars)

    # Final provider variable map
    variables: dict[str, str] = {
        "customer_name": str(rcpt_name),
        "lead_name": str(rcpt_name),
        "bank_name": str(bank_name),
        "product_name": str(product_name),
        "language": str(chosen_lang),
        "tone": str(tone),
        "objective": str(objective),
        "opening_message": str(rendered_opening),
        "system_prompt_addendum": str(addendum),
        "conversation_steps": str(steps_formatted),
        "questions_to_collect": str(questions_formatted),
        "success_condition": str(success_cond),
        "fallback_behaviour": str(fallback),
        "preferred_amount": str(recipient.get("preferred_amount", "")),
    }

    # Strict audit safety check: NEVER leak income, scores, bands, or reasons
    for forbidden in FORBIDDEN_LEAKED_KEYS:
        if forbidden in variables:
            del variables[forbidden]

    return variables
