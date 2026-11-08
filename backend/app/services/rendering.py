"""Template rendering services using {{variable}} placeholder syntax."""

import re
from typing import Any

VAR_REGEX = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render_template(template: str, variables: dict[str, Any]) -> str:
    """
    Replace {{variable}} placeholders with values from variables dictionary.

    Unmatched placeholders are replaced with an empty string.
    """
    if not template:
        return ""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        val = variables.get(key)
        return str(val) if val is not None else ""

    return VAR_REGEX.sub(_replace, template)


def render_data_dict(data: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively render string values in a dictionary with provided variables.
    """
    rendered: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            rendered[key] = render_template(value, variables)
        elif isinstance(value, dict):
            rendered[key] = render_data_dict(value, variables)
        else:
            rendered[key] = value
    return rendered
