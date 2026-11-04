"""Persist document position independently of an employee's HR position."""
from typing import Any, Mapping
from sqlalchemy import text


def apply_document_position(conn: Any, payload: Mapping[str, Any], context: Mapping[str, Any] | None) -> dict[str, Any]:
    out = dict(payload)
    context = context or {}
    position_id = context.get("document_position_id")
    if position_id is not None and (isinstance(position_id, bool) or not isinstance(position_id, int) or position_id <= 0):
        from app.services.personnel_orders_query_service import PersonnelOrderValidationError
        raise PersonnelOrderValidationError("DOCUMENT_POSITION_NOT_FOUND")
    fields = {"name": "position_name", "name_kk": "document_position_kk", "document_nominative_ru": "document_position_nominative_ru", "document_possessive_kk": "document_position_possessive_kk"}
    if position_id is None and not any(context.get(key) is not None for key in list(fields.values())[1:]):
        return out
    saved = dict(out.get("document_position") or {})
    if position_id is not None and saved.get("position_id") != position_id:
        row = conn.execute(text("SELECT position_id,name,name_kk,document_nominative_ru,document_possessive_kk,translation_status,document_form_status FROM public.position_directory WHERE position_id=:id"), {"id": position_id}).mappings().one_or_none()
        if row is None:
            from app.services.personnel_orders_query_service import PersonnelOrderValidationError
            raise PersonnelOrderValidationError("DOCUMENT_POSITION_NOT_FOUND")
        saved = dict(row)
        if saved.get("translation_status") == "needs_review": saved["name_kk"] = ""
        if saved.get("document_form_status") == "needs_review": saved["document_possessive_kk"] = ""
    elif not saved:
        saved = {"position_id": None, "name": out.get("source_position_name"), "name_kk": out.get("position_title_kk"), "document_nominative_ru": (out.get("document_forms_ru") or {}).get("position_document_nominative_ru"), "document_possessive_kk": (out.get("document_forms_kk") or {}).get("position_document_possessive_kk")}
    for field, key in fields.items():
        if context.get(key) is not None: saved[field] = str(context[key]).strip()
    saved = {key: saved.get(key) for key in ("position_id", *fields)}
    out["document_position"] = saved
    out["source_position_name"] = out["position_title_ru"] = saved["name"] or ""
    out["position_title_kk"] = saved["name_kk"] or ""
    out["recall_position_kk"] = str(context.get("recall_position_kk") if context.get("recall_position_kk") is not None else saved["name_kk"] or "").strip()
    out["document_forms_ru"] = {**dict(out.get("document_forms_ru") or {}), "position_document_nominative_ru": saved["document_nominative_ru"] or ""}
    out["document_forms_kk"] = {**dict(out.get("document_forms_kk") or {}), "position_document_possessive_kk": saved["document_possessive_kk"] or ""}
    return out
