"""Resolve exact item bindings, including legacy applications covering many items."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from app.services.personnel_order_print_titles import pin_print_titles, version_print_titles


def resolve_item_templates(conn: Any, order: Any, items: list[Any], *, allow_defaults: bool = False, lock: bool = True) -> dict[int, dict[str, Any]]:
    from app.services.personnel_order_template_application_service import TemplateApplicationError

    applications = conn.execute(text("SELECT * FROM personnel_order_template_applications WHERE order_id=:id ORDER BY applied_at DESC,template_application_id DESC"), {"id": order["order_id"]}).mappings().all()
    bindings: dict[int, int] = {}
    snapshots = {}
    for application in applications:
        covered = {application["order_item_id"]}
        snapshot = application["rendered_snapshot"] or {}
        covered.update(entry.get("order_item_id") for entry in snapshot.get("items", []) if isinstance(entry, dict))
        for item_id in covered:
            if item_id is not None:
                bindings.setdefault(int(item_id), int(application["template_version_id"]))
                snapshots.setdefault(int(item_id), (application.get('template_snapshot') or {}, snapshot.get('order') or {}))

    first = items[0]
    pinned = order.get("selected_template_version_id")
    first_binding = bindings.get(int(first["item_id"]))
    if pinned is not None and first_binding is not None and int(pinned) != first_binding:
        raise TemplateApplicationError("Привязки шаблона приказа и первого пункта противоречат друг другу.")
    homogeneous = len({item["item_type_code"] for item in items}) == 1
    result = {}
    for item in items:
        item_id = int(item["item_id"])
        version_id = bindings.get(item_id)
        if version_id is None and (homogeneous or item_id == int(first["item_id"])):
            version_id = pinned if pinned is not None else first_binding
        if version_id is not None:
            suffix = " FOR SHARE OF v" if lock else ""
            template = conn.execute(text("SELECT v.*,t.name_ru,t.name_kk,t.is_default FROM personnel_order_template_versions v LEFT JOIN personnel_order_templates t USING(template_id) WHERE v.template_version_id=:id AND v.item_type_code=:code AND v.status IN ('PUBLISHED','ARCHIVED')" + suffix), {"id": version_id, "code": item["item_type_code"]}).mappings().first()
        elif allow_defaults and homogeneous:
            template = conn.execute(text("SELECT v.*,t.name_ru,t.name_kk,t.is_default FROM personnel_order_template_versions v JOIN personnel_order_templates t USING(template_id) WHERE v.item_type_code=:code AND v.status='PUBLISHED' AND t.is_default"), {"code": item["item_type_code"]}).mappings().first()
        else:
            raise TemplateApplicationError(f"Пункт {item['item_number']}: отсутствует привязка к конкретной версии шаблона.")
        if template is None:
            if version_id is None:
                raise TemplateApplicationError("No PUBLISHED template exists for this item type.")
            raise TemplateApplicationError(f"Пункт {item['item_number']}: закреплённая версия {version_id} отсутствует, имеет другой тип или недоступный статус.")
        saved = snapshots.get(item_id)
        if saved is None and version_id == (pinned if pinned is not None else first_binding):
            saved = snapshots.get(int(first['item_id']))
        result[item_id] = pin_print_titles(version_print_titles(template), *(saved or (None, None)))
    return result


def common_order_text(conn: Any, order_id: int, fallback: dict[str, str]) -> dict[str, str]:
    """Keep the existing common heading when item templates differ."""
    result = {key: fallback[key] for key in ("title_ru", "title_kk", "preamble_ru", "preamble_kk")}
    blocks = conn.execute(text("SELECT locale,block_type,generated_text FROM personnel_order_editorial_blocks WHERE order_id=:id AND block_type IN ('title','preamble')"), {"id": order_id}).mappings().all()
    for block in blocks:
        result[f"{block['block_type']}_{block['locale']}"] = block["generated_text"] or ""
    return result
