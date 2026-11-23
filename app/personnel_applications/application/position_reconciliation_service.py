"""Application-scoped review of unmatched HIRE position titles."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.application.electronic_hire_service import (
    ElectronicHireError, load_electronic_hire, queue_approval_notification, render_application,
)
from app.services.org_unit_allowed_positions_service import allowed_link_exists, upsert_allowed_position_link
from app.services.position_directory_service import resolve_existing_name, save_details
from app.services.personnel_orders_editorial.mapper import build_item_ctx
from app.services.personnel_orders_editorial.generators import generate_item_body


def _fingerprint(unit_id: int, title: str) -> str:
    return hashlib.sha256(f"{unit_id}\0{' '.join(title.casefold().split())}".encode()).hexdigest()


def _request_row(conn: Connection, request_id: int, *, lock: bool = False) -> dict[str, Any]:
    row = conn.execute(text(f"""
        SELECT r.*, a.personnel_order_id, p.full_name AS requester_name,
               d.full_name AS decider_name, ou.name AS org_unit_name,
               pos.name AS resolved_position_name, pos.name_kk AS resolved_position_name_kk
        FROM public.electronic_hire_position_requests r
        JOIN public.personnel_applications a USING(application_id)
        JOIN public.users p ON p.user_id=r.requested_by_user_id
        LEFT JOIN public.users d ON d.user_id=r.decided_by_user_id
        JOIN public.org_units ou ON ou.unit_id=r.org_unit_id
        LEFT JOIN public.positions pos ON pos.position_id=r.resolved_position_id
        WHERE r.request_id=:id {"FOR UPDATE OF r" if lock else ""}
    """), {"id": request_id}).mappings().first()
    if row is None:
        raise ElectronicHireError("Запрос уточнения не найден.", "POSITION_REQUEST_NOT_FOUND")
    return dict(row)


def request_position_review(conn: Connection, *, application_id: int, actor_user_id: int,
                            explanation: str) -> dict[str, Any]:
    app = load_electronic_hire(conn, application_id, lock=True)
    if app["position_resolution"] != "unmatched_manual":
        raise ElectronicHireError("У заявления нет несопоставленной должности.", "POSITION_ALREADY_MATCHED")
    note = explanation.strip()
    if not note:
        raise ElectronicHireError("Добавьте пояснение к запросу.", "EXPLANATION_REQUIRED")
    unit_id = int(app["intended_org_unit_id"])
    fingerprint = _fingerprint(unit_id, str(app["manual_position_name"]))
    inserted = conn.execute(text("""
        INSERT INTO public.electronic_hire_position_requests
            (application_id, source_fingerprint, source_title, org_unit_id, explanation, requested_by_user_id)
        VALUES (:app, :fingerprint, :title, :unit, :explanation, :actor)
        ON CONFLICT(application_id, source_fingerprint) DO NOTHING
        RETURNING request_id
    """), {"app": application_id, "fingerprint": fingerprint, "title": app["manual_position_name"],
           "unit": unit_id, "explanation": note, "actor": actor_user_id}).scalar_one_or_none()
    if inserted is not None:
        conn.execute(text("""
            INSERT INTO public.electronic_hire_position_request_audit(request_id,action,actor_user_id,details)
            VALUES (:id,'requested',:actor,CAST(:details AS jsonb))
        """), {"id": inserted, "actor": actor_user_id,
               "details": json.dumps({"source_title": app["manual_position_name"],
                                      "org_unit_id": unit_id, "explanation": note}, ensure_ascii=False)})
        request_id = int(inserted)
    else:
        request_id = int(conn.execute(text("""
            SELECT request_id FROM public.electronic_hire_position_requests
            WHERE application_id=:app AND source_fingerprint=:fingerprint
        """), {"app": application_id, "fingerprint": fingerprint}).scalar_one())
    return _request_row(conn, request_id)


def latest_position_review(conn: Connection, application_id: int) -> dict[str, Any] | None:
    row = conn.execute(text("""
        SELECT request_id FROM public.electronic_hire_position_requests
        WHERE application_id=:id ORDER BY request_id DESC LIMIT 1
    """), {"id": application_id}).scalar_one_or_none()
    return _request_row(conn, int(row)) if row is not None else None


def list_position_reviews(conn: Connection, *, status: str | None = None) -> list[dict[str, Any]]:
    if status not in {None, "open", "resolved"}:
        raise ElectronicHireError("Неизвестное состояние запроса.", "STATUS_INVALID")
    ids = conn.execute(text("""
        SELECT request_id FROM public.electronic_hire_position_requests
        WHERE (:status IS NULL OR status=:status)
        ORDER BY CASE WHEN status='open' THEN 0 ELSE 1 END, requested_at DESC, request_id DESC
        LIMIT 200
    """), {"status": status}).scalars().all()
    return [_request_row(conn, int(i)) for i in ids]


def position_review_history(conn: Connection, request_id: int) -> list[dict[str, Any]]:
    _request_row(conn, request_id)
    return [dict(row) for row in conn.execute(text("""
        SELECT audit_id, action, actor_user_id, recorded_at, details
        FROM public.electronic_hire_position_request_audit
        WHERE request_id=:id ORDER BY audit_id
    """), {"id": request_id}).mappings()]


def _require_complete_position(conn: Connection, position_id: int) -> dict[str, Any]:
    row = conn.execute(text("""
        SELECT position_id,name,name_kk,document_nominative_ru,document_possessive_kk
        FROM public.positions WHERE position_id=:id
    """), {"id": position_id}).mappings().first()
    if row is None:
        raise ElectronicHireError("Должность не найдена.", "POSITION_NOT_FOUND")
    if any(not str(row[key] or "").strip() for key in
           ("name", "name_kk", "document_nominative_ru", "document_possessive_kk")):
        raise ElectronicHireError("Заполните формы должности RU/KK в справочнике.", "POSITION_FORMS_REQUIRED")
    return dict(row)


def _item_text(payload: dict[str, Any], *, date_value: Any, employee_name: str) -> dict[str, str]:
    context = build_item_ctx({"item_type_code": "HIRE", "payload": payload,
                              "effective_date": date_value}, employee_name)
    return {locale: generate_item_body(locale, context)["generated_text"] for locale in ("ru", "kk")}


def resolve_position_review(conn: Connection, *, request_id: int, actor_user_id: int,
                            mode: str, position_id: int | None, new_position: dict[str, Any] | None,
                            decision_note: str | None = None) -> dict[str, Any]:
    request = _request_row(conn, request_id, lock=True)
    if request["status"] != "open":
        raise ElectronicHireError("Запрос уже решён.", "POSITION_REQUEST_RESOLVED")
    app = load_electronic_hire(conn, int(request["application_id"]), lock=True)
    if app["position_resolution"] != "unmatched_manual" or app["manual_position_name"] != request["source_title"] or int(app["intended_org_unit_id"]) != int(request["org_unit_id"]):
        raise ElectronicHireError("Условия заявления изменились. Создайте новый запрос.", "POSITION_REQUEST_STALE")
    order_id = app["personnel_order_id"]
    if order_id is not None:
        status = conn.execute(text("SELECT status FROM public.personnel_orders WHERE order_id=:id FOR UPDATE"),
                              {"id": order_id}).scalar_one()
        if status != "DRAFT":
            raise ElectronicHireError("Подписанный или зарегистрированный приказ изменять нельзя.", "ORDER_ALREADY_PUBLISHED")
    unit_id = int(request["org_unit_id"])
    if mode == "existing":
        if position_id is None or not allowed_link_exists(conn, org_unit_id=unit_id, position_id=position_id):
            raise ElectronicHireError("Выберите должность, разрешённую для отделения.", "POSITION_NOT_ALLOWED_IN_UNIT")
    elif mode == "link":
        if position_id is None:
            raise ElectronicHireError("Выберите существующую должность.", "POSITION_REQUIRED")
    elif mode == "new":
        required = ("name", "category", "name_kk", "document_nominative_ru", "document_possessive_kk")
        if position_id is not None or not new_position or any(not str(new_position.get(key) or "").strip() for key in required):
            raise ElectronicHireError("Для новой должности заполните название, категорию и формы RU/KK.", "POSITION_FIELDS_REQUIRED")
        from app.directory.positions_routes import PositionUpsert, _normalize_category, _normalize_name
        try:
            entry = PositionUpsert(**{**new_position, "translation_status": "confirmed",
                                      "document_form_status": "confirmed"})
            category = _normalize_category(entry.category)
        except (ValueError, TypeError) as exc:
            raise ElectronicHireError(str(exc), "POSITION_FIELDS_INVALID") from exc
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('position_directory_write'))"))
        name = _normalize_name(entry.name)
        if resolve_existing_name(conn, name) or conn.execute(text("SELECT 1 FROM public.positions WHERE lower(name)=lower(:name) LIMIT 1"), {"name": name}).first():
            raise ElectronicHireError("Должность или синоним уже есть в справочнике.", "POSITION_DUPLICATE")
        position_id = int(conn.execute(text("""
            INSERT INTO public.positions(name,category) VALUES (:name,:category) RETURNING position_id
        """), {"name": name, "category": category}).scalar_one())
        save_details(conn, position_id, entry)
    else:
        raise ElectronicHireError("Выберите способ решения.", "DECISION_MODE_INVALID")
    assert position_id is not None
    position = _require_complete_position(conn, position_id)
    if mode in {"link", "new"}:
        upsert_allowed_position_link(conn, org_unit_id=unit_id, position_id=position_id,
                                     actor_user_id=actor_user_id)
    before_print = render_application(conn, int(request["application_id"]))
    item = None
    before_item_text = None
    if order_id is not None:
        item = conn.execute(text("""
            SELECT item_id,payload,effective_date FROM public.personnel_order_items
            WHERE order_id=:order AND item_type_code='HIRE' AND item_status='ACTIVE'
            ORDER BY item_id LIMIT 1 FOR UPDATE
        """), {"order": order_id}).mappings().first()
        if item is None:
            raise ElectronicHireError("Пункт проекта приказа не найден.", "ORDER_ITEM_NOT_FOUND")
        before_item_text = _item_text(dict(item["payload"] or {}), date_value=item["effective_date"], employee_name=app["full_name"])
    conn.execute(text("""
        UPDATE public.personnel_applications SET intended_position_id=:position,updated_at=now()
        WHERE application_id=:app
    """), {"position": position_id, "app": request["application_id"]})
    from app.personnel_applications.application.envelope_projection import sync_envelope_intended_projection
    sync_envelope_intended_projection(conn, int(app["person_id"]))
    updated = load_electronic_hire(conn, int(request["application_id"]))
    after_item_text = None
    if item is not None:
        payload = dict(item["payload"] or {})
        payload.update({"position_id": position_id, "position_resolution": "matched_manual",
                        "source_position_name": position["name"], "position_title_kk": position["name_kk"],
                        "position_document_nominative_ru": position["document_nominative_ru"],
                        "position_document_possessive_kk": position["document_possessive_kk"]})
        forms_ru = dict(payload.get("document_forms_ru") or {})
        forms_ru["position_document_nominative_ru"] = position["document_nominative_ru"]
        payload["document_forms_ru"] = forms_ru
        forms_kk = dict(payload.get("document_forms_kk") or {})
        forms_kk["position_document_possessive_kk"] = position["document_possessive_kk"]
        payload["document_forms_kk"] = forms_kk
        manual_flags = dict(payload.get("hire_position_manual_forms") or {})
        manual_flags["ru"] = True
        payload["hire_position_manual_forms"] = manual_flags
        after_item_text = _item_text(payload, date_value=item["effective_date"], employee_name=app["full_name"])
        conn.execute(text("""
            UPDATE public.personnel_order_items SET payload=CAST(:payload AS jsonb) WHERE item_id=:item
        """), {"payload": json.dumps(payload, ensure_ascii=False), "item": item["item_id"]})
        conn.execute(text("""
            UPDATE public.personnel_orders SET document_revision=document_revision+1,updated_at=now()
            WHERE order_id=:order
        """), {"order": order_id})
        from app.services.personnel_orders_editorial_service import mark_blocks_stale_after_structured_change
        mark_blocks_stale_after_structured_change(conn, int(order_id), item_id=int(item["item_id"]))
        queue_approval_notification(conn, int(request["application_id"]))
    after_print = render_application(conn, int(request["application_id"]))
    conn.execute(text("""
        UPDATE public.electronic_hire_position_requests
        SET status='resolved',decision_mode=:mode,resolved_position_id=:position,
            decision_note=:note,decided_by_user_id=:actor,decided_at=now()
        WHERE request_id=:id
    """), {"id": request_id, "mode": mode, "position": position_id,
           "note": (decision_note or "").strip() or None, "actor": actor_user_id})
    changes = {"source_title": request["source_title"], "position_id": position_id,
               "position_name_ru": position["name"], "position_name_kk": position["name_kk"],
               "decision_mode": mode, "before_print": before_print, "after_print": after_print,
               "before_order_text": before_item_text, "after_order_text": after_item_text}
    conn.execute(text("""
        INSERT INTO public.electronic_hire_position_request_audit(request_id,action,actor_user_id,details)
        VALUES (:id,'resolved',:actor,CAST(:details AS jsonb))
    """), {"id": request_id, "actor": actor_user_id,
           "details": json.dumps(changes, ensure_ascii=False)})
    return {**_request_row(conn, request_id), "changes": changes,
            "reapproval_required": order_id is not None, "application": updated}
