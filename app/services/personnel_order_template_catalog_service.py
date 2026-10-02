"""Read-only catalogue projected from personnel-order template specifications."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.personnel_order_template_specs import PERSONNEL_ORDER_TEMPLATE_SPECS, get_personnel_order_template_spec


def list_personnel_order_template_catalog() -> list[dict[str, Any]]:
    """Expose only non-personal, registry-backed template capabilities."""
    rows: list[dict[str, Any]] = []
    for item_type_code in PERSONNEL_ORDER_TEMPLATE_SPECS:
        spec = get_personnel_order_template_spec(item_type_code)
        if spec.catalog_projection is None:
            raise RuntimeError(f"Missing catalog projection for {item_type_code}")
        rows.append({
            "type_code": item_type_code,
            **deepcopy(dict(spec.catalog_projection)),
            # The editor contract belongs to the current server-side spec.
            # Catalog detail is explanatory metadata and can be historical.
            "allowed_variables": list(spec.allowed_variables),
        })
    return rows
