"""Shared validation for editable template snapshots and manifests."""
from __future__ import annotations

import re
from typing import Mapping

from app.services.personnel_order_template_specs import get_personnel_order_template_spec

TEXT_FIELDS = ("title_ru", "title_kk", "preamble_ru", "preamble_kk", "body_template_ru", "body_template_kk", "basis_template_ru", "basis_template_kk")
_TOKEN = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
_FORBIDDEN = re.compile(r"<\s*/?\s*(?:script|style)|javascript:|=>|\b(?:if|for|function)\s*\(", re.I)


class TemplateValidationError(ValueError):
    pass


def validate_template_texts(item_type_code: str, values: Mapping[str, str]) -> None:
    spec = get_personnel_order_template_spec(item_type_code)
    if set(values) != set(TEXT_FIELDS):
        raise TemplateValidationError("Template must contain exactly eight text fields")
    variables = set(spec.allowed_variables)
    for field in TEXT_FIELDS:
        value = values[field]
        if not isinstance(value, str) or not value.strip():
            raise TemplateValidationError(f"{field} is required")
        if _FORBIDDEN.search(value):
            raise TemplateValidationError("HTML, scripts and expressions are forbidden")
        unknown = {match.group(1) for match in _TOKEN.finditer(value)} - variables
        if unknown:
            raise TemplateValidationError("Unknown variable: " + ", ".join(sorted(unknown)))
    for field, required in spec.required_variables.items():
        absent = [code for code in required if f"{{{{{code}}}}}" not in values[field]]
        if absent:
            raise TemplateValidationError(f"Required variable absent from {field}: {', '.join(absent)}")

    if item_type_code == "SUPPLEMENTARY_PAY":
        from app.services.personnel_order_supplementary_pay_contract import validate_bodies
        try: validate_bodies(values)
        except ValueError as exc: raise TemplateValidationError(str(exc)) from exc
    if item_type_code == "CONCURRENT_DUTY_START":
        from app.services.personnel_order_replacement_contract import validate_bodies
        try: validate_bodies(values)
        except ValueError as exc: raise TemplateValidationError(str(exc)) from exc
