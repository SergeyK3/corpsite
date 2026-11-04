"""Immutable document placement snapshots; never mutate HR placement."""
from typing import Any, Mapping

from sqlalchemy import text


def apply_document_department(conn: Any, payload: Mapping[str, Any], context: Mapping[str, Any] | None) -> dict[str, Any]:
    out = dict(payload)
    context = dict(context or {})
    draft = context.get("document_department")
    genitive_ru = None
    if isinstance(draft, Mapping):
        from app.services.personnel_order_russian_reference_forms import russian_reference_case
        from app.services.personnel_orders_query_service import PersonnelOrderValidationError
        unit = draft.get("unit") or {}
        overrides = draft.get("overrides") or {}
        if not isinstance(unit, Mapping) or not isinstance(overrides, Mapping):
            raise PersonnelOrderValidationError("INVALID_DOCUMENT_DEPARTMENT")
        if unit.get("unit_id") is not None and (isinstance(unit["unit_id"], bool) or not isinstance(unit["unit_id"], int) or unit["unit_id"] <= 0):
            raise PersonnelOrderValidationError("INVALID_DOCUMENT_DEPARTMENT")
        if any(unit.get(key) is not None and (not isinstance(unit[key], str) or len(unit[key]) > 300) for key in ("name", "name_kk", "document_genitive_kk")):
            raise PersonnelOrderValidationError("INVALID_DOCUMENT_DEPARTMENT")
        unit = {key: unit.get(key) for key in ("unit_id", "name", "name_kk", "document_genitive_kk")} if unit else {}
        allowed = {"name_ru", "name_kk", "genitive_ru", "genitive_kk"}
        if any(key not in allowed or not isinstance(value, str) or len(value) > 300 for key, value in overrides.items()):
            raise PersonnelOrderValidationError("INVALID_DOCUMENT_DEPARTMENT")
        name_ru = str(overrides.get("name_ru", unit.get("name")) or "").strip()
        name_kk = str(overrides.get("name_kk", unit.get("name_kk")) or "").strip()
        genitive_ru = str(overrides.get("genitive_ru", russian_reference_case(name_ru, "genitive")) or "").strip()
        # The client calculates a proposed KK case from the same canonical
        # nominal value. Explicit manual forms are always stored separately.
        genitive_kk = str(overrides.get("genitive_kk", context.get("document_org_unit_genitive_kk") if "name_kk" in overrides else unit.get("document_genitive_kk") or context.get("document_org_unit_genitive_kk")) or "").strip()
        context.update(document_org_unit_id=unit.get("unit_id"), org_unit_name=name_ru,
                       document_org_unit_kk=name_kk, document_org_unit_genitive_kk=genitive_kk,
                       recall_org_unit_kk=name_kk)
        draft = {"unit": dict(unit) if unit else None, "overrides": dict(overrides)}
    unit_id = context.get("document_org_unit_id")
    if unit_id is None and not any(context.get(key) is not None for key in ("document_org_unit_kk", "document_org_unit_genitive_kk")):
        return out
    # Reopening/saving an existing snapshot must not refresh its translations
    # from a directory that may have changed since the document was written.
    snapshot = dict(out.get("document_org_unit") or {})
    if unit_id is not None and snapshot.get("unit_id") != unit_id:
        row = conn.execute(text("SELECT unit_id,name,name_kk,document_genitive_kk FROM org_units WHERE unit_id=:id"), {"id": unit_id}).mappings().one_or_none()
        if row is None:
            raise ValueError("DOCUMENT_ORG_UNIT_NOT_FOUND")
        snapshot = dict(row)
    elif not snapshot:
        snapshot = {"unit_id": None, "name": out.get("source_org_unit_name"), "name_kk": out.get("org_unit_title_kk"), "document_genitive_kk": (out.get("document_forms_kk") or {}).get("org_unit_document_genitive_kk")}
    for field, source in (("name", "org_unit_name"), ("name_kk", "document_org_unit_kk"), ("document_genitive_kk", "document_org_unit_genitive_kk")):
        if context.get(source) is not None:
            snapshot[field] = str(context[source]).strip()
    snapshot = {key: snapshot.get(key) for key in ("unit_id", "name", "name_kk", "document_genitive_kk")}
    if isinstance(draft, Mapping):
        snapshot["unit_id"] = unit_id
        snapshot["draft"] = draft
    elif (payload.get("document_org_unit") or {}).get("draft") and all(
        context.get(key) is None or context[key] == (payload.get("document_org_unit") or {}).get(field)
        for key, field in (("org_unit_name", "name"), ("document_org_unit_kk", "name_kk"), ("document_org_unit_genitive_kk", "document_genitive_kk"))
    ):
        snapshot["draft"] = payload["document_org_unit"]["draft"]
    out["document_org_unit"] = snapshot
    out["source_org_unit_name"] = snapshot["name"] or ""
    out["org_unit_title_kk"] = snapshot["name_kk"] or ""
    if isinstance(draft, Mapping):
        out["org_unit_name"] = {"ru": snapshot["name"] or "", "kk": snapshot["name_kk"] or ""}
    out["recall_org_unit_kk"] = str(context.get("recall_org_unit_kk") if context.get("recall_org_unit_kk") is not None else snapshot["name_kk"] or "").strip()
    out["document_forms_kk"] = {**dict(out.get("document_forms_kk") or {}), "org_unit_document_genitive_kk": snapshot["document_genitive_kk"] or ""}
    if isinstance(draft, Mapping) and isinstance(out.get("allowance_recipient"), Mapping):
        if not snapshot["name"] or not snapshot["document_genitive_kk"]:
            from app.services.personnel_orders_query_service import PersonnelOrderValidationError
            raise PersonnelOrderValidationError("DOCUMENT_DEPARTMENT_FORMS_REQUIRED")
        out["allowance_recipient"] = {**out["allowance_recipient"], "org_unit_id": snapshot["unit_id"],
                                    "org_unit_ru": snapshot["name"], "org_unit_kk": snapshot["document_genitive_kk"],
                                    "org_unit_genitive_ru": genitive_ru or ""}
    return out
