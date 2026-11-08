"""Deterministic policy evaluation engine for financial product eligibility."""

from typing import Any


def evaluate_eligibility(
    entity: dict[str, Any],
    product: dict[str, Any],
    entity_type: str,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Evaluate deterministic policy rules from product catalogue.

    Returns:
        (eligibility_status, list_of_checks)
        eligibility_status is 'ELIGIBLE' or 'NOT_ELIGIBLE'.
    """
    rules: dict[str, Any] = product.get("eligibility_rules") or {}
    checks: list[dict[str, Any]] = []
    is_eligible = True

    # 1. Minimum Income
    if rules.get("min_income") is not None:
        thresh = float(rules["min_income"])
        val = entity.get("income")
        if val is None:
            is_eligible = False
            checks.append({
                "rule": "min_income",
                "passed": False,
                "value": "not_evaluable",
                "threshold": thresh,
                "message": "Missing income data",
            })
        else:
            inc = float(val)
            passed = inc >= thresh
            if not passed:
                is_eligible = False
            checks.append({
                "rule": "min_income",
                "passed": passed,
                "value": inc,
                "threshold": thresh,
                "message": f"Income ₹{inc:,.0f} meets minimum ₹{thresh:,.0f}" if passed else f"Income ₹{inc:,.0f} is below minimum requirement ₹{thresh:,.0f}",
            })

    # 2. Minimum Age
    if rules.get("min_age") is not None:
        thresh = int(rules["min_age"])
        val = entity.get("age")
        if val is None:
            is_eligible = False
            checks.append({
                "rule": "min_age",
                "passed": False,
                "value": "not_evaluable",
                "threshold": thresh,
                "message": "Missing age data",
            })
        else:
            age = int(val)
            passed = age >= thresh
            if not passed:
                is_eligible = False
            checks.append({
                "rule": "min_age",
                "passed": passed,
                "value": age,
                "threshold": thresh,
                "message": f"Age {age} meets minimum {thresh} years" if passed else f"Age {age} is below minimum {thresh} years",
            })

    # 3. Maximum Age
    if rules.get("max_age") is not None:
        thresh = int(rules["max_age"])
        val = entity.get("age")
        if val is None:
            is_eligible = False
            checks.append({
                "rule": "max_age",
                "passed": False,
                "value": "not_evaluable",
                "threshold": thresh,
                "message": "Missing age data",
            })
        else:
            age = int(val)
            passed = age <= thresh
            if not passed:
                is_eligible = False
            checks.append({
                "rule": "max_age",
                "passed": passed,
                "value": age,
                "threshold": thresh,
                "message": f"Age {age} is within maximum limit {thresh} years" if passed else f"Age {age} exceeds maximum limit {thresh} years",
            })

    # 4. Maximum Existing EMI to Income Ratio
    if rules.get("max_emi_to_income") is not None:
        thresh = float(rules["max_emi_to_income"])
        val = entity.get("existing_emi_to_income")
        if val is None:
            is_eligible = False
            checks.append({
                "rule": "max_emi_to_income",
                "passed": False,
                "value": "not_evaluable",
                "threshold": thresh,
                "message": "Missing debt obligations data",
            })
        else:
            emi_ratio = float(val)
            passed = emi_ratio <= thresh
            if not passed:
                is_eligible = False
            checks.append({
                "rule": "max_emi_to_income",
                "passed": passed,
                "value": round(emi_ratio, 3),
                "threshold": thresh,
                "message": f"EMI burden {emi_ratio:.1%} is within allowable {thresh:.1%}" if passed else f"EMI burden {emi_ratio:.1%} exceeds maximum ceiling {thresh:.1%}",
            })

    # 5. Customer-specific rules
    if entity_type == "customer":
        # Financial Health
        if rules.get("min_financial_health") is not None:
            thresh = float(rules["min_financial_health"])
            val = entity.get("financial_health")
            if val is None:
                is_eligible = False
                checks.append({
                    "rule": "min_financial_health",
                    "passed": False,
                    "value": "not_evaluable",
                    "threshold": thresh,
                    "message": "Missing financial health score",
                })
            else:
                score = float(val)
                passed = score >= thresh
                if not passed:
                    is_eligible = False
                checks.append({
                    "rule": "min_financial_health",
                    "passed": passed,
                    "value": score,
                    "threshold": thresh,
                    "message": f"Financial health {score:.0f}/100 meets threshold {thresh:.0f}" if passed else f"Financial health {score:.0f}/100 is below threshold {thresh:.0f}",
                })

        # Allowed Repayment Behaviours
        if rules.get("allowed_repayment_behaviours"):
            allowed_list = [str(b).upper() for b in rules["allowed_repayment_behaviours"]]
            val = entity.get("repayment_behaviour")
            if not val:
                is_eligible = False
                checks.append({
                    "rule": "allowed_repayment_behaviours",
                    "passed": False,
                    "value": "not_evaluable",
                    "threshold": allowed_list,
                    "message": "Missing repayment history data",
                })
            else:
                rep = str(val).upper()
                passed = rep in allowed_list
                if not passed:
                    is_eligible = False
                checks.append({
                    "rule": "allowed_repayment_behaviours",
                    "passed": passed,
                    "value": rep,
                    "threshold": allowed_list,
                    "message": f"Repayment rating '{rep}' is approved" if passed else f"Repayment rating '{rep}' is not in approved list {allowed_list}",
                })

        # Exclude If Holds Product (default True)
        exclude_held = rules.get("exclude_if_holds_product", True)
        if exclude_held:
            existing_prods = [str(p).lower() for p in entity.get("existing_products", [])]
            pname = str(product.get("name", "")).lower()
            holds = any(pname in p or p in pname for p in existing_prods) if pname else False
            if holds:
                is_eligible = False
                checks.append({
                    "rule": "exclude_if_holds_product",
                    "passed": False,
                    "value": entity.get("existing_products", []),
                    "threshold": "Product not currently held",
                    "message": f"Customer already holds active '{product.get('name')}'",
                })
            else:
                checks.append({
                    "rule": "exclude_if_holds_product",
                    "passed": True,
                    "value": entity.get("existing_products", []),
                    "threshold": "Product not currently held",
                    "message": f"Customer does not currently hold '{product.get('name')}'",
                })

    status_str = "ELIGIBLE" if is_eligible else "NOT_ELIGIBLE"
    return status_str, checks
