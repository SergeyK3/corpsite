"""Read-only catalogue projected from personnel-order template specifications."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.personnel_order_template_specs import PERSONNEL_ORDER_TEMPLATE_SPECS, get_personnel_order_template_spec


def list_personnel_order_template_catalog(*, include_saved_names: bool = False) -> list[dict[str, Any]]:
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
            "required_variables": {field: list(codes) for field, codes in spec.required_variables.items()},
        })
    if include_saved_names:
        from sqlalchemy import text
        from app.services.personnel_order_template_draft_service import engine, independent_template_schema_available
        if independent_template_schema_available():
            with engine.connect() as conn:
                identities = [dict(row) for row in conn.execute(text("""
                    SELECT t.template_id,t.item_type_code,t.name_ru,t.name_kk,t.is_default,
                           p.template_version_id,p.version_number,d.template_version_id AS draft_version_id,
                           d.version_number AS draft_version_number
                    FROM personnel_order_templates t
                    LEFT JOIN personnel_order_template_versions p ON p.template_id=t.template_id AND p.status='PUBLISHED'
                    LEFT JOIN personnel_order_template_versions d ON d.template_id=t.template_id AND d.status='DRAFT'
                    WHERE (NOT EXISTS(SELECT 1 FROM personnel_order_template_versions v WHERE v.template_id=t.template_id)
                      OR EXISTS(SELECT 1 FROM personnel_order_template_versions v WHERE v.template_id=t.template_id AND v.status IN ('DRAFT','PUBLISHED')))
                    ORDER BY t.is_default DESC,t.template_id
                """)).mappings()]
            names = {row["item_type_code"]: row for row in identities if row["is_default"]}
            for row in rows:
                row["templates"] = [{key: value for key, value in identity.items() if key != "item_type_code"} for identity in identities if identity["item_type_code"] == row["type_code"]]
                if row["type_code"] in names:
                    current=names[row["type_code"]]
                    row.update(title_ru=current["name_ru"],title_kk=current["name_kk"])
    return rows
