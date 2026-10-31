"""Resolve an existing order's exact contract and render only its new item."""
from __future__ import annotations

from app.services.personnel_order_print_titles import template_text_snapshot

import hashlib
import json
from typing import Any

from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_order_template_application_service import _FIELDS, _render, _values, TemplateApplicationError
from app.services.personnel_orders_query_service import PersonnelOrderValidationError


def resolve_add_item_context(conn: Any, order: Any, *, lock: bool = True) -> dict[str, Any]:
    # The generic command row intentionally omits newer template columns.
    # Read the persisted binding; mutation callers retain the transaction lock.
    suffix = " FOR UPDATE" if lock else ""
    order = conn.execute(text("SELECT * FROM personnel_orders WHERE order_id=:id" + suffix), {"id": order["order_id"]}).mappings().one()
    items = conn.execute(text("SELECT * FROM personnel_order_items WHERE order_id=:id AND item_status='ACTIVE' ORDER BY item_number,item_id"), {"id": order["order_id"]}).mappings().all()
    if not items:
        raise PersonnelOrderValidationError("Добавление недоступно: в приказе нет действующего первого пункта с привязкой к шаблону.")
    from app.services.personnel_order_item_templates import resolve_item_templates
    try:
        templates = resolve_item_templates(conn, order, list(items), lock=lock)
    except TemplateApplicationError as exc:
        raise PersonnelOrderValidationError(str(exc)) from exc
    first = items[0]
    return {"item_type_code": first["item_type_code"], "template": templates[int(first["item_id"])], "templates": templates,
            "employee_ids": [item["employee_id"] for item in items if item["employee_id"] is not None],
            "default_employee_id": first["employee_id"]}



def get_add_item_context(order_id: int) -> dict[str, Any]:
    from app.services.personnel_orders_command_service import _fetch_order_row, _ensure_order_editable
    from app.services.personnel_order_replacement_contract import variant, optional_placement
    from app.services.personnel_order_service_area_contract import enabled

    with engine.begin() as conn:
        order = _fetch_order_row(conn, order_id)
        _ensure_order_editable(order)
        try:
            context = resolve_add_item_context(conn, order, lock=False)
        except PersonnelOrderValidationError as exc:
            return {"available": False, "reason": str(exc)}
        template = context["template"]
        keys = ("template_id", "template_version_id", "version_number", "name_ru", "name_kk", "title_ru", "title_kk", "is_default")
        return {"available": True, "item_type_code": context["item_type_code"], "employee_ids": context["employee_ids"], "default_employee_id": context["default_employee_id"], "template": {**{key: template[key] for key in keys}, "replacement_mode": variant(template), "replacement_optional_placement": optional_placement(template), "service_area_allowance": enabled(template)}}


def bound_template_generation(conn: Any, order_id: int, items: list[Any]) -> dict[str, Any] | None:
    """Resolve saved text before regeneration; never replace a binding with a default."""
    order = conn.execute(text("SELECT * FROM personnel_orders WHERE order_id=:id"), {"id": order_id}).mappings().one()
    has_history = conn.execute(text("SELECT to_regclass('public.personnel_order_template_applications') IS NOT NULL")).scalar_one()
    has_application = has_history and conn.execute(text("SELECT EXISTS(SELECT 1 FROM personnel_order_template_applications WHERE order_id=:id)"), {"id": order_id}).scalar_one()
    if order.get("selected_template_version_id") is None and not has_application:
        return None  # Historical unbound documents keep their existing generator.
    from app.services.personnel_order_item_templates import resolve_item_templates, common_order_text
    active_items = [item for item in items if item["item_status"] == "ACTIVE"]
    if not active_items:
        raise PersonnelOrderValidationError("Нет действующих пунктов для формирования текста.")
    rendered_items = {}
    try:
        templates = resolve_item_templates(conn, order, active_items)
        combined = len({t["template_version_id"] for t in templates.values()}) > 1 or order["order_type_code"] == "COMPOSITE"
        for item in active_items:
            template = templates[int(item["item_id"])]
            values, _, _ = _values(conn, item, template)
            rendered_items[int(item["item_id"])] = _render(template, values, item_only=combined)
    except ValueError as exc:
        raise PersonnelOrderValidationError(str(exc)) from exc
    first_template = templates[int(active_items[0]["item_id"])]
    order_text = next(iter(rendered_items.values()))
    if combined:
        order_text = common_order_text(conn, order_id, order_text)
    return {"template_version_id": first_template["template_version_id"], "template_versions": {key: value["template_version_id"] for key, value in templates.items()}, "order": order_text, "items": rendered_items}



def render_added_item(conn: Any, *, order_id: int, item_id: int, template: dict[str, Any], actor_user_id: int) -> None:
    from app.services.personnel_orders_editorial.repository import upsert_item_block

    item = conn.execute(text("SELECT * FROM personnel_order_items WHERE item_id=:id"), {"id": item_id}).mappings().one()
    try:
        values, _, _ = _values(conn, item, template)
        rendered = _render(template, values, item_only=True)
    except TemplateApplicationError as exc:
        raise PersonnelOrderValidationError(str(exc)) from exc
    for locale in ("ru", "kk"):
        for block in ("body", "basis"):
            value = rendered[f"{block}_template_{locale}"]
            fingerprint = hashlib.sha256(json.dumps({"template": template["template_version_id"], "item": dict(item), "text": value}, default=str, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            upsert_item_block(conn, order_item_id=item_id, locale=locale, block_type=block, generated={"generated_text": value, "source_fingerprint": fingerprint, "generator_key": "bound_template", "generator_version": "1"}, basis_required=bool(rendered[f"basis_template_{locale}"].strip()))
    entry = {"order_item_id": item_id, "item_number": item["item_number"], "proposed": {f"{block}_{locale}": rendered[f"{block}_template_{locale}"] for block in ("body", "basis") for locale in ("ru", "kk")}}
    conn.execute(text("INSERT INTO personnel_order_template_applications(order_id,order_item_id,template_version_id,template_snapshot,rendered_snapshot,previous_editorial_blocks,applied_by_user_id) VALUES(:o,:i,:v,CAST(:t AS jsonb),CAST(:r AS jsonb),'[]'::jsonb,:a)"), {"o": order_id, "i": item_id, "v": template["template_version_id"], "t": json.dumps(template_text_snapshot(template, _FIELDS), ensure_ascii=False), "r": json.dumps({"items": [entry]}, ensure_ascii=False), "a": actor_user_id})
