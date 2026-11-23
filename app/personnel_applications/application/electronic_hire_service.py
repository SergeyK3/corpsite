"""Electronic HIRE application state and the shared order approval gate."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.personnel_orders_editorial.generators import _format_rate_value
from app.services.org_unit_allowed_positions_service import allowed_link_exists
from app.personnel_applications.application.envelope_projection import sync_envelope_intended_projection


class ElectronicHireError(ValueError):
    def __init__(self, message: str, code: str = "ELECTRONIC_HIRE_INVALID") -> None:
        super().__init__(message)
        self.code = code


def require_allowed_position(conn: Connection, *, org_unit_id: int, position_id: int) -> None:
    """Use the same active unit-position links as the order editor's allowed list."""
    if not allowed_link_exists(conn, org_unit_id=org_unit_id, position_id=position_id):
        raise ElectronicHireError(
            "Выбранная должность недоступна в этом отделении.", "POSITION_NOT_ALLOWED_IN_UNIT"
        )


def validate_hire_position_input(conn: Connection, *, org_unit_id: int, position_id: int | None,
                                 manual_position_name: str | None,
                                 manual_position_document_ru: str | None = None) -> tuple[int | None, str | None, str | None]:
    """Keep catalog choices and unmatched manual titles separate."""
    name = " ".join((manual_position_name or "").split())
    if bool(position_id) == bool(name):
        raise ElectronicHireError("Выберите должность или введите название вручную.", "POSITION_REQUIRED")
    if position_id is not None:
        require_allowed_position(conn, org_unit_id=org_unit_id, position_id=position_id)
        return position_id, None, None
    if len(name) > 500:
        raise ElectronicHireError("Название должности слишком длинное.", "POSITION_NAME_TOO_LONG")
    document_ru = " ".join((manual_position_document_ru or "").split())
    if not document_ru or document_ru.casefold() == name.casefold() or len(document_ru) > 500:
        raise ElectronicHireError(
            "Укажите форму должности после «на должность».", "POSITION_FORM_REQUIRED"
        )
    return None, name, document_ru


def load_electronic_hire(conn: Connection, application_id: int, *, lock: bool = False) -> dict[str, Any]:
    row = conn.execute(text(f"""
        SELECT a.application_id, a.person_id, a.application_source, a.status,
               a.application_received_at, a.intended_org_group_id,
               a.intended_org_unit_id, a.intended_position_id, a.intended_vacancy_text AS manual_position_name,
               a.intended_employment_rate, a.personnel_order_id,
               a.contact_mobile_phone, a.contact_email,
               e.planned_start_date, e.candidate_checked_at, e.manual_position_document_ru,
               p.full_name, p.iin,
               ou.name AS org_unit_ru,
               NULLIF(to_jsonb(ou)->>'name_kk', '') AS org_unit_kk,
               NULLIF(to_jsonb(ou)->>'document_genitive_ru', '') AS org_unit_genitive_ru,
               NULLIF(to_jsonb(ou)->>'document_genitive_kk', '') AS org_unit_genitive_kk,
               COALESCE(pos.name, a.intended_vacancy_text) AS position_ru,
               COALESCE(NULLIF(to_jsonb(pos)->>'name_kk', ''), a.intended_vacancy_text) AS position_kk,
               COALESCE(NULLIF(to_jsonb(pos)->>'document_nominative_ru', ''), e.manual_position_document_ru) AS position_document_ru,
               NULLIF(to_jsonb(pos)->>'document_possessive_kk', '') AS position_document_kk
        FROM public.personnel_applications a
        JOIN public.electronic_hire_applications e USING (application_id)
        JOIN public.persons p ON p.person_id = a.person_id
        LEFT JOIN public.org_units ou ON ou.unit_id = a.intended_org_unit_id
        LEFT JOIN public.positions pos ON pos.position_id = a.intended_position_id
        WHERE a.application_id = :id
        {"FOR UPDATE OF a, e" if lock else ""}
    """), {"id": application_id}).mappings().first()
    if row is None:
        raise ElectronicHireError("Электронное заявление не найдено.", "APPLICATION_NOT_FOUND")
    result = dict(row)
    result["position_resolution"] = (
        "matched_manual" if result["intended_position_id"] is not None and result["manual_position_name"]
        else "catalog" if result["intended_position_id"] is not None else "unmatched_manual"
    )
    return result


def conditions(application: dict[str, Any]) -> dict[str, Any]:
    rate = application.get("intended_employment_rate")
    return {
        "org_unit_id": application.get("intended_org_unit_id"),
        "position_id": application.get("intended_position_id"),
        "manual_position_name": application.get("manual_position_name"),
        "manual_position_document_ru": application.get("manual_position_document_ru"),
        "employment_rate": str(Decimal(str(rate)).normalize()) if rate is not None else None,
        "planned_start_date": str(application.get("planned_start_date")) if application.get("planned_start_date") else None,
    }


def conditions_hash(application: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(conditions(application), sort_keys=True).encode()).hexdigest()


def current_visa(conn: Connection, application: dict[str, Any]) -> dict[str, Any] | None:
    row = conn.execute(text("""
        SELECT visa_id, decision, explanation, conditions_hash, conditions,
               decided_by_user_id, decided_at
        FROM public.electronic_hire_visas
        WHERE application_id = :id ORDER BY visa_id DESC LIMIT 1
    """), {"id": application["application_id"]}).mappings().first()
    if row is None:
        return None
    result = dict(row)
    result["is_current"] = result["conditions_hash"] == conditions_hash(application)
    return result


def require_current_approval(conn: Connection, order_id: int) -> None:
    row = conn.execute(text("""
        SELECT a.application_id FROM public.personnel_applications a
        WHERE a.personnel_order_id = :order_id
    """), {"order_id": order_id}).mappings().first()
    if row is None:
        raise ElectronicHireError("Приказ о приёме не связан с электронным заявлением.", "APPLICATION_REQUIRED")
    application = load_electronic_hire(conn, int(row["application_id"]))
    if application["position_resolution"] == "unmatched_manual":
        raise ElectronicHireError(
            "Должность требует сопоставления со справочником. Отправьте на уточнение в заявлении.",
            "POSITION_RECONCILIATION_REQUIRED",
        )
    items = conn.execute(text("""
        SELECT effective_date, payload FROM public.personnel_order_items
        WHERE order_id=:id AND item_type_code='HIRE' AND item_status='ACTIVE'
    """), {"id": order_id}).mappings().all()
    expected = conditions(application)
    if len(items) != 1:
        raise ElectronicHireError("В проекте должен быть один пункт о приёме.", "HIRE_ITEM_MISMATCH")
    item = items[0]
    payload = item["payload"] or {}
    actual = {"org_unit_id": payload.get("org_unit_id"),
              "position_id": payload.get("position_id"),
              "manual_position_name": payload.get("manual_position_name"),
              "manual_position_document_ru": payload.get("manual_position_document_ru"),
              "employment_rate": str(Decimal(str(payload.get("employment_rate"))).normalize()) if payload.get("employment_rate") is not None else None,
              "planned_start_date": str(item["effective_date"]) if item["effective_date"] else None}
    if actual != expected or int(payload.get("person_id") or 0) != int(application["person_id"]):
        raise ElectronicHireError("Условия проекта отличаются от согласованного заявления.", "ORDER_CONDITIONS_MISMATCH")
    visa = current_visa(conn, application)
    if visa is None or not visa["is_current"] or visa["decision"] != "approved":
        raise ElectronicHireError("Требуется актуальная положительная виза руководителя.", "APPROVAL_REQUIRED")


def order_has_hire_item(conn: Connection, order_id: int) -> bool:
    return bool(conn.execute(text("""
        SELECT EXISTS(SELECT 1 FROM public.personnel_order_items
                      WHERE order_id=:id AND item_type_code='HIRE' AND item_status='ACTIVE')
            OR EXISTS(SELECT 1 FROM public.personnel_orders
                      WHERE order_id=:id AND order_type_code='HIRE')
    """), {"id": order_id}).scalar_one())


def render_application(conn: Connection, application_id: int) -> dict[str, str]:
    app = load_electronic_hire(conn, application_id)
    # The signed source statement remains as the applicant wrote it.  The
    # catalog identity is used by the draft order after reconciliation.
    if app["position_resolution"] == "matched_manual":
        app["position_ru"] = app["manual_position_name"]
        app["position_kk"] = app["manual_position_name"]
        app["position_document_ru"] = app["manual_position_document_ru"]
        app["position_document_kk"] = None
    rate = _format_rate_value(app["intended_employment_rate"])
    start = app["planned_start_date"]
    if not start or not app["org_unit_ru"] or not app["position_ru"]:
        raise ElectronicHireError("Укажите отделение, должность, ставку и дату начала работы.", "CONDITIONS_INCOMPLETE")
    date_ru = start.strftime("%d.%m.%Y")
    date_kk = start.strftime("%d.%m.%Y")
    from app.services.personnel_order_hire_wording import hire_department_destination_kk, hire_position_accusative_ru
    try:
        position_ru = hire_position_accusative_ru(
            app["position_ru"],
            app["position_document_ru"] if app["position_document_ru"] and
            app["position_document_ru"].strip().casefold() != app["position_ru"].strip().casefold() else "",
        )
    except ValueError as exc:
        raise ElectronicHireError(str(exc), "POSITION_FORM_REQUIRED") from exc
    position_kk = app["position_document_kk"] or app["position_kk"] or app["position_ru"]
    position_kk = position_kk[:1].lower() + position_kk[1:]
    unit_ru = app["org_unit_ru"]
    unit_kk = hire_department_destination_kk(app["org_unit_kk"] or unit_ru)
    name = app["full_name"]
    template_dir = Path(__file__).resolve().parents[1] / "templates"
    application_date = app["application_received_at"].strftime("%d.%m.%Y")
    return {
        "ru": (template_dir / "hire_application_ru.txt").read_text(encoding="utf-8").format(
            full_name=name, org_unit=unit_ru, position=position_ru, rate=rate,
            start_date=date_ru, application_date=application_date,
        ).strip(),
        "kk": (template_dir / "hire_application_kk.txt").read_text(encoding="utf-8").format(
            full_name=name, org_unit=unit_kk, position=position_kk, rate=rate,
            start_date=date_kk, application_date=application_date,
        ).strip(),
    }


def update_conditions(conn: Connection, application_id: int, *, org_unit_id: int, position_id: int | None,
                      employment_rate: Decimal, planned_start_date: date,
                      manual_position_name: str | None = None,
                      manual_position_document_ru: str | None = None) -> dict[str, Any]:
    app = load_electronic_hire(conn, application_id, lock=True)
    if app["status"] in {"completed", "cancelled", "withdrawn"}:
        raise ElectronicHireError("Заявление закрыто.", "APPLICATION_CLOSED")
    if app["personnel_order_id"] is not None:
        order_status = conn.execute(text("SELECT status FROM public.personnel_orders WHERE order_id=:id"),
                                    {"id": app["personnel_order_id"]}).scalar_one_or_none()
        if order_status != "DRAFT":
            raise ElectronicHireError("Условия можно менять только до публикации приказа.", "ORDER_ALREADY_PUBLISHED")
    if not (Decimal("0") < employment_rate <= Decimal("2")):
        raise ElectronicHireError("Ставка должна быть больше нуля и не выше двух.", "RATE_INVALID")
    position_id, manual_position_name, manual_position_document_ru = validate_hire_position_input(
        conn, org_unit_id=org_unit_id, position_id=position_id,
        manual_position_name=manual_position_name, manual_position_document_ru=manual_position_document_ru,
    )
    if app["position_resolution"] == "unmatched_manual" and position_id is not None:
        raise ElectronicHireError(
            "Должность требует сопоставления со справочником. Отправьте на уточнение.",
            "POSITION_RECONCILIATION_REQUIRED",
        )
    if app["position_resolution"] == "matched_manual" and position_id is not None:
        manual_position_name = app["manual_position_name"]
        manual_position_document_ru = app["manual_position_document_ru"]
    conn.execute(text("""
        UPDATE public.personnel_applications
        SET intended_org_unit_id=:unit, intended_position_id=:position,
            intended_vacancy_text=:manual_name,
            intended_employment_rate=:rate, updated_at=now()
        WHERE application_id=:id
    """), {"unit": org_unit_id, "position": position_id, "manual_name": manual_position_name,
           "rate": employment_rate, "id": application_id})
    sync_envelope_intended_projection(conn, int(app["person_id"]))
    conn.execute(text("""
        UPDATE public.electronic_hire_applications
        SET planned_start_date=:start, manual_position_document_ru=:manual_document,
            candidate_checked_at=NULL,
            candidate_checked_by_user_id=NULL, updated_at=now()
        WHERE application_id=:id
    """), {"start": planned_start_date, "manual_document": manual_position_document_ru, "id": application_id})
    updated = load_electronic_hire(conn, application_id)
    if updated["personnel_order_id"] is not None:
        item = conn.execute(text("""
            SELECT item_id, payload FROM public.personnel_order_items
            WHERE order_id=:order AND item_type_code='HIRE' AND item_status='ACTIVE'
            ORDER BY item_id LIMIT 1 FOR UPDATE
        """), {"order": updated["personnel_order_id"]}).mappings().first()
        if item is None:
            raise ElectronicHireError("Пункт проекта приказа не найден.", "ORDER_ITEM_NOT_FOUND")
        payload = dict(item["payload"] or {})
        payload.update({"org_unit_id": org_unit_id,
                        "employment_rate": float(employment_rate),
                        "source_org_unit_name": updated["org_unit_ru"],
                        "source_position_name": updated["position_ru"],
                        "org_unit_title_kk": updated["org_unit_kk"],
                        "position_title_kk": updated["position_kk"],
                        "position_resolution": updated["position_resolution"],
                        "position_document_nominative_ru": updated["position_document_ru"],
                        "document_forms_ru": {"position_document_nominative_ru": updated["position_document_ru"]},
                        "hire_position_manual_forms": {"ru": position_id is None}})
        if position_id is None:
            payload.pop("position_id", None)
            payload["manual_position_name"] = manual_position_name
            payload["manual_position_document_ru"] = manual_position_document_ru
        else:
            payload["position_id"] = position_id
            if manual_position_name is None:
                payload.pop("manual_position_name", None)
                payload.pop("manual_position_document_ru", None)
            else:
                payload["manual_position_name"] = manual_position_name
                payload["manual_position_document_ru"] = manual_position_document_ru
        conn.execute(text("""
            UPDATE public.personnel_order_items
            SET effective_date=:start, payload=CAST(:payload AS jsonb)
            WHERE item_id=:item
        """), {"start": planned_start_date, "payload": json.dumps(payload), "item": item["item_id"]})
        conn.execute(text("""
            UPDATE public.personnel_orders
            SET document_revision=document_revision+1, updated_at=now()
            WHERE order_id=:order
        """), {"order": updated["personnel_order_id"]})
        from app.services.personnel_orders_editorial_service import mark_blocks_stale_after_structured_change
        mark_blocks_stale_after_structured_change(conn, int(updated["personnel_order_id"]), item_id=int(item["item_id"]))
        queue_approval_notification(conn, application_id)
    return updated


def mark_candidate_checked(conn: Connection, application_id: int, actor_user_id: int) -> None:
    load_electronic_hire(conn, application_id)
    conn.execute(text("""
        UPDATE public.electronic_hire_applications
        SET candidate_checked_at=now(), candidate_checked_by_user_id=:user_id, updated_at=now()
        WHERE application_id=:id
    """), {"id": application_id, "user_id": actor_user_id})


def missing_card_fields(conn: Connection, person_id: int, application_id: int) -> list[str]:
    row = conn.execute(text("""
        SELECT p.full_name, p.iin, p.birth_date, p.last_name, p.first_name,
               m.person_id AS card_person_id,
               COALESCE(NULLIF(BTRIM(c.mobile_phone), ''), NULLIF(BTRIM(a.contact_mobile_phone), '')) AS mobile_phone,
               EXISTS (SELECT 1 FROM public.person_education pe
                       WHERE pe.person_id=p.person_id AND pe.lifecycle_status='active') AS has_education
        FROM public.persons p
        LEFT JOIN public.personnel_record_metadata m ON m.person_id = p.person_id
        LEFT JOIN public.person_contacts c ON c.person_id = p.person_id
        LEFT JOIN public.personnel_applications a ON a.application_id=:application_id AND a.person_id=p.person_id
        WHERE p.person_id=:id
    """), {"id": person_id, "application_id": application_id}).mappings().first()
    if row is None:
        return ["Личная карточка"]
    required = (("full_name", "ФИО"), ("iin", "ИИН"), ("birth_date", "Дата рождения"),
                ("last_name", "Фамилия"), ("first_name", "Имя"), ("card_person_id", "Личная карточка"),
                ("mobile_phone", "Мобильный телефон"), ("has_education", "Образование"))
    return [label for key, label in required if not row[key]]


def resolve_unit_head(conn: Connection, org_unit_id: int) -> int | None:
    row = conn.execute(text("""
        SELECT m.user_id FROM public.org_unit_managers m
        JOIN public.users u ON u.user_id=m.user_id
        WHERE m.unit_id=:unit AND upper(btrim(m.manager_type))='HEAD'
          AND m.is_active=TRUE AND u.is_active=TRUE
          AND (m.date_from IS NULL OR m.date_from <= CURRENT_DATE)
          AND (m.date_to IS NULL OR m.date_to >= CURRENT_DATE)
        ORDER BY m.date_from DESC NULLS LAST, m.manager_id DESC LIMIT 1
    """), {"unit": org_unit_id}).mappings().first()
    return int(row["user_id"]) if row else None


def queue_approval_notification(conn: Connection, application_id: int) -> dict[str, Any]:
    app = load_electronic_hire(conn, application_id)
    fingerprint = conditions_hash(app)
    head = resolve_unit_head(conn, int(app["intended_org_unit_id"]))
    status = "pending" if head is not None else "no_manager"
    row = conn.execute(text("""
        INSERT INTO public.electronic_hire_notifications
            (application_id, conditions_hash, recipient_user_id, status)
        VALUES (:id, :hash, :recipient, :status)
        ON CONFLICT (application_id, conditions_hash) DO UPDATE
        SET recipient_user_id=COALESCE(public.electronic_hire_notifications.recipient_user_id, EXCLUDED.recipient_user_id),
            status=CASE WHEN public.electronic_hire_notifications.status='no_manager' AND EXCLUDED.recipient_user_id IS NOT NULL
                        THEN 'pending' ELSE public.electronic_hire_notifications.status END,
            updated_at=now()
        RETURNING notification_id, status, recipient_user_id, attempts, last_error
    """), {"id": application_id, "hash": fingerprint, "recipient": head, "status": status}).mappings().one()
    return dict(row)


def retry_approval_notification(conn: Connection, application_id: int) -> dict[str, Any]:
    app = load_electronic_hire(conn, application_id)
    notification = queue_approval_notification(conn, application_id)
    if notification["status"] == "sent":
        return notification
    head = resolve_unit_head(conn, int(app["intended_org_unit_id"]))
    if head is None:
        return notification
    row = conn.execute(text("""
        UPDATE public.electronic_hire_notifications
        SET status='pending', recipient_user_id=:head, last_error=NULL, updated_at=now()
        WHERE notification_id=:id RETURNING notification_id, status, recipient_user_id, attempts, last_error
    """), {"id": notification["notification_id"], "head": head}).mappings().one()
    return dict(row)


def send_telegram_text(chat_id: int, message: str, *, bot_token: str) -> None:
    """Delivery seam; tests replace this function and never contact Telegram."""
    import httpx
    response = httpx.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",
                          json={"chat_id": chat_id, "text": message}, timeout=10.0)
    response.raise_for_status()
    if not response.json().get("ok"):
        raise RuntimeError("Telegram did not accept the message")


def dispatch_approval_notification(conn: Connection, application_id: int) -> dict[str, Any]:
    app = load_electronic_hire(conn, application_id)
    row = conn.execute(text("""
        SELECT n.notification_id, n.status, n.recipient_user_id, n.attempts,
               u.telegram_id
        FROM public.electronic_hire_notifications n
        LEFT JOIN public.users u ON u.user_id=n.recipient_user_id
        WHERE n.application_id=:id AND n.conditions_hash=:hash
        FOR UPDATE OF n
    """), {"id": application_id, "hash": conditions_hash(app)}).mappings().first()
    if row is None:
        return queue_approval_notification(conn, application_id)
    if row["status"] == "sent":
        return dict(row)
    if row["recipient_user_id"] is None:
        return dict(row)
    token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = row["telegram_id"]
    error = None
    if not chat_id:
        error = "У руководителя не привязан Telegram. Заявление доступно в кабинете."
    elif not token:
        error = "Telegram-бот не настроен. Заявление доступно в кабинете."
    else:
        rate = _format_rate_value(app["intended_employment_rate"])
        message = (f"Поступило заявление о приёме на должность {app['position_ru']} "
                   f"в отделение {app['org_unit_ru']} на {rate} ставки. "
                   "Просим указать решение в визе согласования.")
        try:
            send_telegram_text(int(chat_id), message, bot_token=token)
        except Exception as exc:
            error = f"Telegram: {type(exc).__name__}"
    status = "failed" if error else "sent"
    updated = conn.execute(text("""
        UPDATE public.electronic_hire_notifications
        SET status=:status, last_error=:error, attempts=attempts+1, updated_at=now()
        WHERE notification_id=:id
        RETURNING notification_id, status, recipient_user_id, attempts, last_error
    """), {"status": status, "error": error, "id": row["notification_id"]}).mappings().one()
    return dict(updated)


def record_visa(conn: Connection, application_id: int, *, actor_user_id: int,
                decision: str, explanation: str | None) -> dict[str, Any]:
    app = load_electronic_hire(conn, application_id, lock=True)
    if app["status"] in {"completed", "cancelled", "withdrawn"}:
        raise ElectronicHireError("Заявление закрыто.", "APPLICATION_CLOSED")
    if app["personnel_order_id"] is None:
        raise ElectronicHireError("Проект приказа ещё не создан.", "ORDER_DRAFT_REQUIRED")
    head = resolve_unit_head(conn, int(app["intended_org_unit_id"]))
    if head != actor_user_id:
        raise ElectronicHireError("Вы не являетесь руководителем выбранного отделения.", "HEAD_ACCESS_DENIED")
    if decision not in {"approved", "rejected"}:
        raise ElectronicHireError("Выберите согласие или отказ.", "DECISION_INVALID")
    if decision == "rejected" and not (explanation or "").strip():
        raise ElectronicHireError("При отказе требуется пояснение.", "EXPLANATION_REQUIRED")
    latest = current_visa(conn, app)
    if latest and latest["is_current"] and latest["decision"] == decision and latest["explanation"] == (explanation or None):
        return latest
    row = conn.execute(text("""
        INSERT INTO public.electronic_hire_visas
            (application_id, decision, explanation, conditions_hash, conditions, decided_by_user_id)
        VALUES (:id, :decision, :explanation, :hash, CAST(:conditions AS jsonb), :actor)
        RETURNING visa_id, decision, explanation, conditions_hash, conditions, decided_by_user_id, decided_at
    """), {"id": application_id, "decision": decision, "explanation": explanation,
           "hash": conditions_hash(app), "conditions": json.dumps(conditions(app)), "actor": actor_user_id}).mappings().one()
    conn.execute(text("""
        UPDATE public.personnel_applications SET director_resolution_status=:decision,
            director_resolution_by_user_id=:actor, director_resolution_note=:explanation,
            director_resolution_at=now(), updated_at=now() WHERE application_id=:id
    """), {"id": application_id, "decision": decision, "actor": actor_user_id, "explanation": explanation})
    return {**dict(row), "is_current": True}
