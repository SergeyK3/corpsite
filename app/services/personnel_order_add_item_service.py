"""Resolve an existing order's exact contract and render only its new item."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_order_template_application_service import _FIELDS, _render, _values, TemplateApplicationError
from app.services.personnel_orders_query_service import PersonnelOrderValidationError


def resolve_add_item_context(conn: Any, order: Any) -> dict[str, Any]:
    # The generic command row intentionally omits newer template columns.
    # Read the actual persisted binding under the same transaction's lock.
    order = conn.execute(text("SELECT * FROM personnel_orders WHERE order_id=:id FOR UPDATE"), {"id": order["order_id"]}).mappings().one()
    items = conn.execute(text("SELECT * FROM personnel_order_items WHERE order_id=:id AND item_status='ACTIVE' ORDER BY item_number,item_id"), {"id": order["order_id"]}).mappings().all()
    if not items:
        raise PersonnelOrderValidationError("Добавление недоступно: в приказе нет действующего первого пункта с привязкой к шаблону.")
    code = str(items[0]["item_type_code"])
    if any(str(item["item_type_code"]) != code for item in items) or str(order["order_type_code"]) not in {code, "COMPOSITE"}:
        raise PersonnelOrderValidationError("Добавление недоступно: исторический приказ содержит разные типы действий. Его пункты сохранены без изменений.")
    applications = conn.execute(text("SELECT * FROM personnel_order_template_applications WHERE order_id=:id ORDER BY applied_at DESC,template_application_id DESC"), {"id": order["order_id"]}).mappings().all()
    bindings = {}
    for application in applications:
        covered = {application["order_item_id"]}
        snapshot = application["rendered_snapshot"] or {}
        covered.update(entry.get("order_item_id") for entry in snapshot.get("items", []) if isinstance(entry, dict))
        for item in items:
            if item["item_status"] != "ACTIVE":
                continue
            if item["item_id"] in covered:
                bindings.setdefault(item["item_id"], application["template_version_id"])
    pinned = order.get("selected_template_version_id")
    first_binding = bindings.get(items[0]["item_id"])
    version_id = pinned if pinned is not None else first_binding
    if version_id is None:
        raise PersonnelOrderValidationError("Добавление недоступно: в приказе и применении первого пункта отсутствует привязка к конкретной версии шаблона.")
    if any(value != version_id for value in bindings.values()):
        raise PersonnelOrderValidationError(f"Добавление недоступно: привязки шаблона противоречат друг другу (приказ: {pinned}, применения пунктов: {bindings}).")
    template = conn.execute(text("SELECT v.*,t.name_ru,t.name_kk,t.is_default FROM personnel_order_template_versions v JOIN personnel_order_templates t USING(template_id) WHERE v.template_version_id=:id AND v.item_type_code=:code AND v.status IN ('PUBLISHED','ARCHIVED') FOR SHARE OF v,t"), {"id": version_id, "code": code}).mappings().first()
    if template is None:
        raise PersonnelOrderValidationError(f"Добавление недоступно: закреплённая версия {version_id} отсутствует, имеет другой тип или недоступный статус.")
    return {"item_type_code": code, "template": dict(template), "employee_ids": [item["employee_id"] for item in items if item["employee_id"] is not None]}


def get_add_item_context(order_id: int) -> dict[str, Any]:
    from app.services.personnel_orders_command_service import _fetch_order_row, _ensure_order_editable
    from app.services.personnel_order_replacement_contract import variant, optional_placement
    from app.services.personnel_order_service_area_contract import enabled

    with engine.begin() as conn:
        order = _fetch_order_row(conn, order_id)
        _ensure_order_editable(order)
        try:
            context = resolve_add_item_context(conn, order)
        except PersonnelOrderValidationError as exc:
            return {"available": False, "reason": str(exc)}
        template = context["template"]
        keys = ("template_id", "template_version_id", "version_number", "name_ru", "name_kk", "title_ru", "title_kk", "is_default")
        return {"available": True, "item_type_code": context["item_type_code"], "employee_ids": context["employee_ids"], "template": {**{key: template[key] for key in keys}, "replacement_mode": variant(template), "replacement_optional_placement": optional_placement(template), "service_area_allowance": enabled(template)}}


def bound_template_generation(conn: Any, order_id: int, items: list[Any]) -> dict[str, Any] | None:
    """Resolve saved text before regeneration; never replace a binding with a default."""
    order = conn.execute(text("SELECT * FROM personnel_orders WHERE order_id=:id"), {"id": order_id}).mappings().one()
    has_history = conn.execute(text("SELECT to_regclass('public.personnel_order_template_applications') IS NOT NULL")).scalar_one()
    has_application = has_history and conn.execute(text("SELECT EXISTS(SELECT 1 FROM personnel_order_template_applications WHERE order_id=:id)"), {"id": order_id}).scalar_one()
    if order.get("selected_template_version_id") is None and not has_application:
        return None  # Historical unbound documents keep their existing generator.
    context = resolve_add_item_context(conn, order)
    template = context["template"]
    rendered_items = {}
    try:
        for item in items:
            if item["item_status"] != "ACTIVE":
                continue
            values, _, _ = _values(conn, item, template)
            rendered_items[int(item["item_id"])] = _render(template, values)
    except ValueError as exc:
        raise PersonnelOrderValidationError(str(exc)) from exc
    return {"template_version_id": template["template_version_id"], "order": next(iter(rendered_items.values())), "items": rendered_items}


def render_added_item(conn: Any, *, order_id: int, item_id: int, template: dict[str, Any], actor_user_id: int) -> None:
    from app.services.personnel_orders_editorial.repository import upsert_item_block

    item = conn.execute(text("SELECT * FROM personnel_order_items WHERE item_id=:id"), {"id": item_id}).mappings().one()
    try:
        values, _, _ = _values(conn, item, template)
        rendered = _render(template, values)
    except TemplateApplicationError as exc:
        raise PersonnelOrderValidationError(str(exc)) from exc
    for locale in ("ru", "kk"):
        for block in ("body", "basis"):
            value = rendered[f"{block}_template_{locale}"]
            fingerprint = hashlib.sha256(json.dumps({"template": template["template_version_id"], "item": dict(item), "text": value}, default=str, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            upsert_item_block(conn, order_item_id=item_id, locale=locale, block_type=block, generated={"generated_text": value, "source_fingerprint": fingerprint, "generator_key": "bound_template", "generator_version": "1"}, basis_required=bool(rendered[f"basis_template_{locale}"].strip()))
    entry = {"order_item_id": item_id, "item_number": item["item_number"], "proposed": {f"{block}_{locale}": rendered[f"{block}_template_{locale}"] for block in ("body", "basis") for locale in ("ru", "kk")}}
    conn.execute(text("INSERT INTO personnel_order_template_applications(order_id,order_item_id,template_version_id,template_snapshot,rendered_snapshot,previous_editorial_blocks,applied_by_user_id) VALUES(:o,:i,:v,CAST(:t AS jsonb),CAST(:r AS jsonb),'[]'::jsonb,:a)"), {"o": order_id, "i": item_id, "v": template["template_version_id"], "t": json.dumps({key: template[key] for key in _FIELDS}, ensure_ascii=False), "r": json.dumps({"items": [entry]}, ensure_ascii=False), "a": actor_user_id})
