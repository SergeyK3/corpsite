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
from app.medical_org_groups import SLUG_CLINICAL, SLUG_PARACLINICAL, group_by_id
from app.services.org_unit_allowed_positions_service import allowed_link_exists
from app.services.current_primary_assignment_sql import CURRENT_PRIMARY_ASSIGNMENT_LATERAL_SQL
from app.personnel_applications.application.envelope_projection import sync_envelope_intended_projection


class ElectronicHireError(ValueError):
    def __init__(self, message: str, code: str = "ELECTRONIC_HIRE_INVALID") -> None:
        super().__init__(message)
        self.code = code


def require_unit_group(conn: Connection, *, org_unit_id: int, org_group_id: int | None = None) -> int:
    """Resolve the same inherited group used by the shared unit selector."""
    rows = conn.execute(text("""
        WITH RECURSIVE lineage AS (
            SELECT unit_id, parent_unit_id, group_id, is_active, 0 AS depth
            FROM public.org_units WHERE unit_id=:unit
            UNION ALL
            SELECT parent.unit_id, parent.parent_unit_id, parent.group_id,
                   parent.is_active, child.depth + 1
            FROM public.org_units parent
            JOIN lineage child ON parent.unit_id=child.parent_unit_id
            WHERE child.depth < 20
        )
        SELECT group_id, is_active, depth FROM lineage ORDER BY depth
    """), {"unit": org_unit_id}).mappings().all()
    if not rows or not rows[0]["is_active"]:
        raise ElectronicHireError("Выбранное отделение недоступно.", "ORG_UNIT_NOT_AVAILABLE")
    resolved = next((int(row["group_id"]) for row in rows if row["group_id"] is not None), None)
    if resolved is None or (org_group_id is not None and resolved != org_group_id):
        raise ElectronicHireError("Группа отделений не соответствует отделению.", "ORG_GROUP_MISMATCH")
    return resolved


def require_allowed_position(conn: Connection, *, org_unit_id: int, position_id: int) -> None:
    """Accept explicit links, or an existing assignment when the unit has no active links."""
    if allowed_link_exists(conn, org_unit_id=org_unit_id, position_id=position_id):
        return
    has_allowed_links = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM public.org_unit_allowed_positions
            WHERE org_unit_id=:unit AND is_active=TRUE
        )
    """), {"unit": org_unit_id}).scalar_one()
    if not has_allowed_links:
        is_used = conn.execute(text(f"""
            WITH RECURSIVE unit_subtree AS (
                SELECT unit_id FROM public.org_units WHERE unit_id=:unit
                UNION ALL
                SELECT child.unit_id FROM public.org_units child
                JOIN unit_subtree parent ON child.parent_unit_id=parent.unit_id
                WHERE COALESCE(child.is_active, TRUE)=TRUE
            )
            SELECT EXISTS (
                SELECT 1 FROM public.employees e
                {CURRENT_PRIMARY_ASSIGNMENT_LATERAL_SQL}
                JOIN public.positions p ON p.position_id=(
                    CASE WHEN current_pa.assignment_id IS NOT NULL
                         THEN current_pa.position_id ELSE e.position_id END
                )
                WHERE e.is_active=TRUE
                  AND (CASE WHEN current_pa.assignment_id IS NOT NULL
                            THEN current_pa.org_unit_id ELSE e.org_unit_id END)
                      IN (SELECT unit_id FROM unit_subtree)
                  AND p.position_id=:position
                  AND NOT EXISTS (
                      SELECT 1 FROM public.org_unit_allowed_positions inactive
                      WHERE inactive.org_unit_id=:unit AND inactive.position_id=:position
                        AND inactive.is_active=FALSE
                  )
            )
        """), {"unit": org_unit_id, "position": position_id}).scalar_one()
        if is_used:
            return
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
               e.planned_start_date, e.candidate_checked_at, e.conditions_version, e.approval_mode, e.manual_position_document_ru,
               e.preliminary_full_name, e.preliminary_last_name, e.preliminary_first_name,
               e.preliminary_middle_name, e.preliminary_iin, e.preliminary_birth_date,
               p.last_name AS verified_last_name, p.first_name AS verified_first_name,
               p.middle_name AS verified_middle_name,
               COALESCE(CASE WHEN e.preliminary_last_name IS NOT NULL THEN
                            CONCAT_WS(' ', e.preliminary_last_name, e.preliminary_first_name,
                                      NULLIF(e.preliminary_middle_name, '')) END,
                        e.preliminary_full_name) AS preliminary_name,
               COALESCE(CASE WHEN e.candidate_checked_at IS NULL AND e.preliminary_last_name IS NOT NULL THEN
                            CONCAT_WS(' ', e.preliminary_last_name, e.preliminary_first_name,
                                      NULLIF(e.preliminary_middle_name, '')) END,
                        p.full_name,
                        e.preliminary_full_name) AS full_name,
               COALESCE(p.iin, e.preliminary_iin) AS iin,
               ou.name AS org_unit_ru,
               NULLIF(to_jsonb(ou)->>'name_kk', '') AS org_unit_kk,
               NULLIF(to_jsonb(ou)->>'document_genitive_ru', '') AS org_unit_genitive_ru,
               NULLIF(to_jsonb(ou)->>'document_genitive_kk', '') AS org_unit_genitive_kk,
               COALESCE(pos.name, a.intended_vacancy_text) AS position_ru, pos.type_code AS position_type_code,
               ou.group_id AS org_unit_group_id,
               COALESCE(NULLIF(to_jsonb(pos)->>'name_kk', ''), a.intended_vacancy_text) AS position_kk,
               COALESCE(NULLIF(to_jsonb(pos)->>'document_nominative_ru', ''), e.manual_position_document_ru) AS position_document_ru,
               NULLIF(to_jsonb(pos)->>'document_possessive_kk', '') AS position_document_kk
        FROM public.personnel_applications a
        JOIN public.electronic_hire_applications e USING (application_id)
        LEFT JOIN public.persons p ON p.person_id = a.person_id
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


def update_preliminary_name(conn: Connection, application_id: int, *, last_name: str,
                            first_name: str, middle_name: str | None) -> dict[str, Any]:
    app = load_electronic_hire(conn, application_id, lock=True)
    if app["personnel_order_id"] is not None or app["candidate_checked_at"] is not None or app["status"] in {
        "completed", "cancelled", "withdrawn", "expired",
    }:
        raise ElectronicHireError("ФИО в этом заявлении уже нельзя изменить.", "NAME_EDIT_NOT_ALLOWED")
    last = last_name.strip()
    first = first_name.strip()
    middle = (middle_name or "").strip() or None
    if not last or not first:
        raise ElectronicHireError("Укажите фамилию и имя.", "NAME_REQUIRED")
    conn.execute(text("""
        UPDATE public.electronic_hire_applications
        SET preliminary_last_name=:last_name, preliminary_first_name=:first_name,
            preliminary_middle_name=:middle_name, updated_at=now()
        WHERE application_id=:id
    """), {"id": application_id, "last_name": last, "first_name": first,
           "middle_name": middle})
    return load_electronic_hire(conn, application_id)


def conditions(application: dict[str, Any]) -> dict[str, Any]:
    rate = application.get("intended_employment_rate")
    result = {
        "org_unit_id": application.get("intended_org_unit_id"),
        "position_id": application.get("intended_position_id"),
        "manual_position_name": application.get("manual_position_name"),
        "manual_position_document_ru": application.get("manual_position_document_ru"),
        "employment_rate": str(Decimal(str(rate)).normalize()) if rate is not None else None,
        "planned_start_date": str(application.get("planned_start_date")) if application.get("planned_start_date") else None,
    }
    if application.get("manual_position_name"):
        result["manual_position_name"] = application["manual_position_name"]
        result["manual_position_document_ru"] = application.get("manual_position_document_ru")
    return result


def conditions_hash(application: dict[str, Any]) -> str:
    payload = conditions(application)
    version = int(application.get("conditions_version") or 1)
    # Preserve v1 hashes and existing visas when deploying this change.
    if version > 1:
        payload["conditions_version"] = version
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def current_visa(conn: Connection, application: dict[str, Any]) -> dict[str, Any] | None:
    row = conn.execute(text("""
        SELECT v.visa_id, v.decision, v.explanation, v.conditions_hash, v.conditions,
               v.decided_by_user_id, u.full_name AS decided_by_name, v.decided_at
        FROM public.electronic_hire_visas v
        JOIN public.users u ON u.user_id=v.decided_by_user_id
        WHERE v.application_id = :id ORDER BY v.visa_id DESC LIMIT 1
    """), {"id": application["application_id"]}).mappings().first()
    if row is None:
        return None
    result = dict(row)
    result["is_current"] = result["conditions_hash"] == conditions_hash(application)
    return result


def configured_approval_mode(conn: Connection, org_unit_id: int) -> str:
    row = conn.execute(text("""
        SELECT u.unit_id, COALESCE(m.mode, 'paper') AS mode
        FROM public.org_units u LEFT JOIN public.hire_approval_unit_modes m USING (unit_id)
        WHERE u.unit_id=:id AND u.is_active=TRUE
    """), {"id": org_unit_id}).mappings().first()
    if row is None:
        raise ElectronicHireError("Отделение не найдено или неактивно.", "UNIT_NOT_FOUND")
    return str(row["mode"])


def current_paper_confirmation(conn: Connection, application: dict[str, Any]) -> dict[str, Any] | None:
    row = conn.execute(text("""
        SELECT c.confirmation_id, c.approver_name, c.approved_on, c.note,
               c.attachment_id, c.conditions_hash, c.recorded_by_user_id,
               u.full_name AS recorded_by_name, c.recorded_at
        FROM public.electronic_hire_paper_confirmations c
        JOIN public.users u ON u.user_id=c.recorded_by_user_id
        WHERE c.application_id=:id ORDER BY c.confirmation_id DESC LIMIT 1
    """), {"id": application["application_id"]}).mappings().first()
    return {**dict(row), "is_current": row["conditions_hash"] == conditions_hash(application)} if row else None


def record_paper_confirmation(conn: Connection, application_id: int, *, actor_user_id: int,
                              approver_name: str, approved_on: date, note: str | None,
                              attachment_id: int | None = None) -> dict[str, Any]:
    app = load_electronic_hire(conn, application_id, lock=True)
    if app["approval_mode"] != "paper":
        raise ElectronicHireError("Для заявления требуется электронная виза.", "ELECTRONIC_APPROVAL_REQUIRED")
    if app["status"] in {"completed", "cancelled", "withdrawn"}:
        raise ElectronicHireError("Заявление закрыто.", "APPLICATION_CLOSED")
    name = approver_name.strip()
    if not name:
        raise ElectronicHireError("Укажите, кто согласовал заявление на бумаге.", "APPROVER_REQUIRED")
    if attachment_id is not None:
        exists = conn.execute(text("""
            SELECT 1 FROM public.electronic_hire_attachments
            WHERE attachment_id=:attachment AND application_id=:application
        """), {"attachment": attachment_id, "application": application_id}).scalar_one_or_none()
        if not exists:
            raise ElectronicHireError("Файл не относится к этому заявлению.", "ATTACHMENT_INVALID")
    old = current_paper_confirmation(conn, app)
    if old and old["is_current"]:
        if (old["approver_name"], old["approved_on"], old["note"], old["attachment_id"]) == (name, approved_on, note, attachment_id):
            return old
        raise ElectronicHireError("Бумажное согласование уже подтверждено. Для новой отметки измените условия заявления.", "PAPER_ALREADY_CONFIRMED")
    row = conn.execute(text("""
        INSERT INTO public.electronic_hire_paper_confirmations
            (application_id, conditions_hash, conditions, approver_name, approved_on,
             note, attachment_id, recorded_by_user_id)
        VALUES (:id, :hash, CAST(:conditions AS jsonb), :name, :approved_on,
                :note, :attachment, :actor)
        RETURNING confirmation_id, approver_name, approved_on, note, attachment_id,
                  recorded_by_user_id, recorded_at
    """), {"id": application_id, "hash": conditions_hash(app),
           "conditions": json.dumps(conditions(app)), "name": name, "approved_on": approved_on,
           "note": note, "attachment": attachment_id, "actor": actor_user_id}).mappings().one()
    return {**dict(row), "is_current": True}


def require_current_approval(conn: Connection, order_id: int) -> None:
    row = conn.execute(text("""
        SELECT a.application_id FROM public.personnel_applications a
        WHERE a.personnel_order_id = :order_id
    """), {"order_id": order_id}).mappings().first()
    if row is None:
        raise ElectronicHireError("Приказ о приёме не связан с электронным заявлением.", "APPLICATION_REQUIRED")
    application = load_electronic_hire(conn, int(row["application_id"]))
    if application["position_resolution"] == "unmatched_manual":
        raise ElectronicHireError("Должность требует сопоставления со справочником.", "POSITION_RECONCILIATION_REQUIRED")
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
    if application.get("manual_position_name"):
        actual["manual_position_name"] = payload.get("manual_position_name")
        actual["manual_position_document_ru"] = payload.get("manual_position_document_ru")
    if actual != expected or int(payload.get("person_id") or 0) != int(application["person_id"]):
        raise ElectronicHireError("Условия проекта отличаются от согласованного заявления.", "ORDER_CONDITIONS_MISMATCH")
    if application["approval_mode"] == "paper":
        confirmation = current_paper_confirmation(conn, application)
        if confirmation is None or not confirmation["is_current"]:
            raise ElectronicHireError("Требуется актуальное подтверждение бумажного согласования.", "PAPER_APPROVAL_REQUIRED")
    else:
        visa = current_visa(conn, application)
        if visa is None or not visa["is_current"] or visa["decision"] != "approved":
            raise ElectronicHireError("Требуется актуальная положительная электронная виза.", "APPROVAL_REQUIRED")


def order_has_hire_item(conn: Connection, order_id: int) -> bool:
    return bool(conn.execute(text("""
        SELECT EXISTS(SELECT 1 FROM public.personnel_order_items
                      WHERE order_id=:id AND item_type_code='HIRE' AND item_status='ACTIVE')
            OR EXISTS(SELECT 1 FROM public.personnel_orders
                      WHERE order_id=:id AND order_type_code='HIRE')
    """), {"id": order_id}).scalar_one())


def render_application(conn: Connection, application_id: int, locale: str | None = None,
                       *, preliminary: bool = False) -> dict[str, str]:
    app = load_electronic_hire(conn, application_id)
    unverified = app["preliminary_name"] is not None and (
        app["person_id"] is None or app["candidate_checked_at"] is None
    )
    if unverified and not preliminary:
        raise ElectronicHireError("Сначала проверьте личность претендента по документу.", "IDENTITY_NOT_CONFIRMED")
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
    if locale not in (None, "ru", "kk"):
        raise ValueError(f"Unsupported application locale: {locale}")
    if locale != "kk":
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
    name = app["preliminary_name"] if unverified else app["full_name"]
    template_dir = Path(__file__).resolve().parents[1] / "templates"
    application_date = app["application_received_at"].strftime("%d.%m.%Y")
    result: dict[str, str] = {}
    if locale != "kk":
        result["ru"] = (template_dir / "hire_application_ru.txt").read_text(encoding="utf-8").format(
            full_name=name, org_unit=unit_ru, position=position_ru, rate=rate,
            start_date=date_ru, application_date=application_date,
        ).strip()
    if locale != "ru":
        result["kk"] = (template_dir / "hire_application_kk.txt").read_text(encoding="utf-8").format(
            full_name=name, org_unit=unit_kk, position=position_kk, rate=rate,
            start_date=date_kk, application_date=application_date,
        ).strip()
    return result


def update_conditions(conn: Connection, application_id: int, *, org_unit_id: int, position_id: int | None,
                      employment_rate: Decimal, planned_start_date: date,
                      actor_user_id: int | None = None, mode_change_reason: str | None = None,
                      manual_position_name: str | None = None, manual_position_document_ru: str | None = None) -> dict[str, Any]:
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
    org_group_id = require_unit_group(conn, org_unit_id=org_unit_id)
    position_id, manual_position_name, manual_position_document_ru = validate_hire_position_input(
        conn, org_unit_id=org_unit_id, position_id=position_id,
        manual_position_name=manual_position_name, manual_position_document_ru=manual_position_document_ru,
    )
    if app["position_resolution"] == "unmatched_manual" and position_id is not None:
        raise ElectronicHireError("Должность требует сопоставления со справочником.", "POSITION_RECONCILIATION_REQUIRED")
    if app["position_resolution"] == "matched_manual" and position_id is not None:
        manual_position_name = app["manual_position_name"]
        manual_position_document_ru = app["manual_position_document_ru"]
    requested = {"org_unit_id": org_unit_id, "position_id": position_id,
                 "employment_rate": str(Decimal(str(employment_rate)).normalize()),
                 "planned_start_date": str(planned_start_date)}
    if manual_position_name:
        requested["manual_position_name"] = manual_position_name
        requested["manual_position_document_ru"] = manual_position_document_ru
    if conditions(app) == requested:
        return app
    new_mode = app["approval_mode"]
    if int(app["intended_org_unit_id"]) != org_unit_id:
        if actor_user_id is None or not (mode_change_reason or "").strip():
            raise ElectronicHireError("Подтвердите смену отделения и порядок согласования целевого отделения.", "MODE_CHANGE_ACK_REQUIRED")
        new_mode = configured_approval_mode(conn, org_unit_id)
    conn.execute(text("""
        UPDATE public.personnel_applications
        SET intended_org_group_id=:group_id, intended_org_unit_id=:unit, intended_position_id=:position,
            intended_vacancy_text=:manual_name,
            intended_employment_rate=:rate, updated_at=now()
        WHERE application_id=:id
    """), {"group_id": org_group_id, "unit": org_unit_id, "position": position_id, "manual_name": manual_position_name, "rate": employment_rate, "id": application_id})
    if app["person_id"] is not None:
        sync_envelope_intended_projection(conn, int(app["person_id"]))
    conn.execute(text("""
        UPDATE public.electronic_hire_applications
        SET planned_start_date=:start, manual_position_document_ru=:manual_document,
            conditions_version=conditions_version+1, candidate_checked_at=NULL,
            candidate_checked_by_user_id=NULL, approval_mode=:mode, updated_at=now()
        WHERE application_id=:id
    """), {"start": planned_start_date, "manual_document": manual_position_document_ru, "mode": new_mode, "id": application_id})
    if int(app["intended_org_unit_id"]) != org_unit_id:
        conn.execute(text("""
            INSERT INTO public.hire_approval_mode_audit
                (unit_id, application_id, old_mode, new_mode, changed_by_user_id, reason)
            VALUES (:unit, :application, :old, :new, :actor, :reason)
        """), {"unit": org_unit_id, "application": application_id, "old": app["approval_mode"],
               "new": new_mode, "actor": actor_user_id, "reason": mode_change_reason.strip()})
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
        payload.update({"org_group_id": org_group_id, "org_unit_id": org_unit_id,
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
        from app.personnel_applications.application.hire_approval_task_service import archive_superseded_hire_tasks
        archive_superseded_hire_tasks(conn, application_id=application_id,
                                      current_fingerprint=conditions_hash(updated))
        if new_mode == "electronic":
            ensure_approval_task(conn, updated)
            queue_approval_notification(conn, application_id)
    return updated


def _submitted_identity(conn: Connection, application_id: int) -> tuple[str, str, date, dict[str, str]]:
    from app.domain.iin import IinValidationError, normalize_and_validate_iin
    from app.personnel_intake.application.intake_mapper import build_full_name, parse_date_value
    from app.personnel_intake.application.intake_service import get_hr_intake_draft

    draft = get_hr_intake_draft(conn, application_id)
    if draft is None or draft.status != "submitted":
        raise ElectronicHireError("Сначала дождитесь отправки анкеты претендентом.", "INTAKE_NOT_SUBMITTED")
    personal = draft.payload.get("personal") or {}
    parts = {key: str(personal.get(key) or "").strip()
             for key in ("last_name", "first_name", "middle_name")}
    name = build_full_name(parts)
    if not parts["last_name"] or not parts["first_name"]:
        raise ElectronicHireError("В анкете не указано полное ФИО.", "IDENTITY_NAME_REQUIRED")
    try:
        iin = normalize_and_validate_iin(str(personal.get("iin") or ""))
    except IinValidationError as exc:
        raise ElectronicHireError("Проверьте ИИН в анкете.", "IDENTITY_IIN_INVALID") from exc
    birth_date = parse_date_value(personal.get("birth_date"))
    if birth_date is None or birth_date > date.today():
        raise ElectronicHireError("Проверьте дату рождения в анкете.", "IDENTITY_BIRTH_DATE_INVALID")
    return name, iin, birth_date, parts


def preview_candidate_identity(conn: Connection, application_id: int) -> dict[str, Any]:
    from app.personnel_applications.application.registration_service import _person_has_active_employee
    from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository

    app = load_electronic_hire(conn, application_id)
    result: dict[str, Any] = {
        "preliminary_full_name": app["preliminary_name"] or app["full_name"],
        "legacy_full_name": app["preliminary_full_name"] or (
            app["full_name"] if app["preliminary_last_name"] is None else None),
        "preliminary_name_parts": {key: app[f"preliminary_{key}"] or ""
                                   for key in ("last_name", "first_name", "middle_name")},
        "preliminary_iin": app["preliminary_iin"],
        "person_id": app["person_id"],
        "confirmed": app["person_id"] is not None and app["candidate_checked_at"] is not None,
    }
    if result["confirmed"]:
        return {**result, "status": "confirmed", "verified_full_name": app["full_name"],
                "verified_name_parts": {key: app[f"verified_{key}"] or ""
                                        for key in ("last_name", "first_name", "middle_name")}}
    name, iin, birth_date, parts = _submitted_identity(conn, application_id)
    differences = [key for key in ("last_name", "first_name", "middle_name")
                   if (app[f"preliminary_{key}"] or "") != parts[key]]
    result.update({"applicant_full_name": name, "applicant_name_parts": parts,
                   "name_differences": differences, "iin": iin,
                   "birth_date": birth_date.isoformat()})
    if app["preliminary_iin"] and app["preliminary_iin"] != iin:
        return {**result, "status": "blocked", "reason": "ИИН в анкете отличается от указанного кадровиком. Сверьте документ."}
    persons = conn.execute(text("""
        SELECT person_id, full_name, birth_date, person_status FROM public.persons
        WHERE iin=:iin ORDER BY person_id LIMIT 2
    """), {"iin": iin}).mappings().all()
    if len(persons) > 1 or (persons and persons[0]["person_status"] != "active"):
        return {**result, "status": "blocked", "reason": "Конфликт карточек по ИИН. Требуется ручная проверка."}
    if not persons:
        return {**result, "status": "new"}
    person = persons[0]
    person_id = int(person["person_id"])
    result.update({"existing_person_id": person_id, "existing_full_name": person["full_name"]})
    if person["birth_date"] and person["birth_date"] != birth_date:
        return {**result, "status": "blocked", "reason": "Дата рождения не совпадает с прежней карточкой."}
    if _person_has_active_employee(conn, person_id):
        return {**result, "status": "blocked", "reason": "Сотрудник с этим ИИН уже работает. Оформление остановлено."}
    active = SqlAlchemyPersonnelApplicationRepository(conn).get_active_by_person_id(person_id)
    if active and active.application_id != application_id:
        return {**result, "status": "blocked", "reason": f"По этому ИИН уже есть действующее заявление №{active.application_id}."}
    return {**result, "status": "former"}


def confirm_candidate_identity(
    conn: Connection, application_id: int, *, actor_user_id: int,
    verified_full_name: str | None = None,
    verified_last_name: str | None = None, verified_first_name: str | None = None,
    verified_middle_name: str | None = None, confirm_reuse: bool,
) -> dict[str, Any]:
    from app.personnel_applications.application.registration_service import _ensure_envelope_exists, _insert_person
    from app.services.iin_writer_protocol import lock_and_recheck_iin_tx

    app = load_electronic_hire(conn, application_id, lock=True)
    if app["person_id"] is not None and app["candidate_checked_at"] is not None:
        return {"person_id": int(app["person_id"]), "idempotent_replay": True}
    name, iin, birth_date, parts = _submitted_identity(conn, application_id)
    if verified_last_name is not None or verified_first_name is not None or verified_middle_name is not None:
        verified_parts = {"last_name": (verified_last_name or "").strip(),
                          "first_name": (verified_first_name or "").strip(),
                          "middle_name": (verified_middle_name or "").strip()}
        if verified_parts != parts:
            raise ElectronicHireError("Подтвердите каждое поле ФИО из анкеты после сверки с документом.",
                                      "IDENTITY_NAME_MISMATCH")
    elif (verified_full_name or "").strip() != name:
        raise ElectronicHireError("Подтвердите ФИО из анкеты после сверки с документом.", "IDENTITY_NAME_MISMATCH")
    lock_and_recheck_iin_tx(conn, iin=iin)
    preview = preview_candidate_identity(conn, application_id)
    if preview["status"] == "blocked":
        raise ElectronicHireError(preview["reason"], "IDENTITY_CONFLICT")
    if preview["status"] == "former" and not confirm_reuse:
        raise ElectronicHireError("Подтвердите привязку к прежней карточке.", "REUSE_CONFIRMATION_REQUIRED")
    person_id = preview.get("existing_person_id")
    if person_id is None:
        person_id = _insert_person(conn, full_name=name, iin=iin, birth_date=birth_date)
    else:
        person_id = int(person_id)
    conn.execute(text("""
        UPDATE public.persons
        SET full_name=:name, last_name=:last_name, first_name=:first_name,
            middle_name=:middle_name, birth_date=COALESCE(birth_date, :birth_date)
        WHERE person_id=:person_id
    """), {"name": name, "last_name": parts["last_name"], "first_name": parts["first_name"],
           "middle_name": parts["middle_name"] or None, "birth_date": birth_date,
           "person_id": person_id})
    _ensure_envelope_exists(conn, person_id=person_id, is_new_person=preview["status"] == "new", actor_id=f"user:{actor_user_id}")
    conn.execute(text("""
        UPDATE public.personnel_applications SET person_id=:person_id, updated_at=now()
        WHERE application_id=:id AND person_id IS NULL
    """), {"person_id": person_id, "id": application_id})
    conn.execute(text("""
        UPDATE public.electronic_hire_applications
        SET candidate_checked_at=now(), candidate_checked_by_user_id=:actor, updated_at=now()
        WHERE application_id=:id
    """), {"actor": actor_user_id, "id": application_id})
    sync_envelope_intended_projection(conn, person_id)
    return {"person_id": person_id, "idempotent_replay": False}


def mark_candidate_checked(conn: Connection, application_id: int, actor_user_id: int) -> None:
    app = load_electronic_hire(conn, application_id)
    if app["person_id"] is None:
        raise ElectronicHireError("Сначала проверьте личность претендента по документу.", "IDENTITY_NOT_CONFIRMED")
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


def order_draft_readiness(conn: Connection, application_id: int) -> dict[str, Any]:
    """Use the same persisted identity, intake transfer and card gates as order creation."""
    app = load_electronic_hire(conn, application_id)
    identity_confirmed = app["person_id"] is not None and app["candidate_checked_at"] is not None
    transfer = conn.execute(text("""
        SELECT status, sections_transferred FROM public.personnel_intake_transfers
        WHERE application_id=:id
    """), {"id": application_id}).mappings().first()
    intake_transferred = bool(transfer and transfer["status"] == "completed"
                              and "general" in (transfer["sections_transferred"] or []))
    card_missing = (missing_card_fields(conn, int(app["person_id"]), application_id)
                    if identity_confirmed and intake_transferred else [])
    missing_steps: list[str] = []
    if not identity_confirmed:
        missing_steps.append("Проверьте анкету и подтвердите личность по документу.")
    if not intake_transferred:
        missing_steps.append("Завершите проверку анкеты и перенесите принятые данные в личную карточку.")
    if card_missing:
        missing_steps.append("Заполните обязательные поля личной карточки: " + ", ".join(card_missing) + ".")
    return {"application_id": application_id, "ready": not missing_steps,
            "identity_confirmed": identity_confirmed, "intake_transferred": intake_transferred,
            "missing_card_fields": card_missing, "missing_steps": missing_steps}


def resolve_approval_recipient(conn: Connection, application: dict[str, Any]) -> int:
    """One source of truth for tasks, notices, listing, reading and decisions."""
    if application["approval_mode"] != "electronic":
        raise ElectronicHireError("Для заявления действует бумажное согласование.", "PAPER_APPROVAL_MODE")
    # A started approval round has an explicit recipient. Preserve it until the
    # conditions change; the next fingerprint is routed by the current catalog.
    existing = conn.execute(text("""
        SELECT h.head_user_id, u.is_active
        FROM public.electronic_hire_approval_tasks h
        JOIN public.users u ON u.user_id=h.head_user_id
        WHERE h.application_id=:id AND h.conditions_hash=:hash
    """), {"id": application["application_id"], "hash": conditions_hash(application)}).mappings().first()
    if existing is not None:
        if not existing["is_active"]:
            raise ElectronicHireError("Назначенный согласующий сейчас неактивен. Обновите назначение и условия заявления.",
                                      "APPROVER_INACTIVE")
        return int(existing["head_user_id"])
    group = group_by_id(int(application["org_unit_group_id"] or 0))
    if group is None:
        raise ElectronicHireError("Для отделения не определена группа. Уточните справочник подразделений.",
                                  "UNIT_GROUP_REQUIRED")
    medical = group.slug in {SLUG_CLINICAL, SLUG_PARACLINICAL}
    if medical:
        category = application["position_type_code"]
        if category not in {1, 2, 3}:
            raise ElectronicHireError(
                "Для медицинского отделения у должности не задана категория: врач, средний или младший медперсонал.",
                "POSITION_TYPE_REQUIRED")
        manager_type = "HEAD" if category == 1 else "SENIOR_NURSE"
        role_label = "руководитель отделения" if category == 1 else "старшая медицинская сестра"
    else:
        manager_type = "HEAD"
        role_label = "руководитель отделения"
    rows = conn.execute(text("""
        SELECT DISTINCT m.user_id FROM public.org_unit_managers m
        JOIN public.users u ON u.user_id=m.user_id
        WHERE m.unit_id=:unit AND upper(btrim(m.manager_type))=:manager_type
          AND m.is_active=TRUE AND u.is_active=TRUE
          AND (m.date_from IS NULL OR m.date_from <= CURRENT_DATE)
          AND (m.date_to IS NULL OR m.date_to >= CURRENT_DATE)
    """), {"unit": application["intended_org_unit_id"], "manager_type": manager_type}).mappings().all()
    if not rows:
        raise ElectronicHireError(f"Не назначен согласующий: {role_label}.", "APPROVER_NOT_CONFIGURED")
    if len(rows) != 1:
        raise ElectronicHireError(f"Назначено несколько согласующих ({role_label}). Уточните назначения отделения.",
                                  "APPROVER_AMBIGUOUS")
    return int(rows[0]["user_id"])


def resolve_unit_head(conn: Connection, org_unit_id: int) -> int | None:
    """Legacy helper retained for callers that need a non-authorizing lookup."""
    rows = conn.execute(text("""
        SELECT DISTINCT m.user_id FROM public.org_unit_managers m JOIN public.users u ON u.user_id=m.user_id
        WHERE m.unit_id=:unit AND upper(btrim(m.manager_type))='HEAD' AND m.is_active AND u.is_active
          AND (m.date_from IS NULL OR m.date_from <= CURRENT_DATE)
          AND (m.date_to IS NULL OR m.date_to >= CURRENT_DATE)
    """), {"unit": org_unit_id}).scalars().all()
    return int(rows[0]) if len(rows) == 1 else None


def ensure_approval_task(conn: Connection, application: dict[str, Any]) -> dict[str, Any]:
    """The task is durable and independent of optional Telegram delivery."""
    from app.personnel_applications.application.hire_approval_task_service import (
        ensure_hire_approval_task, finish_hire_approval_task,
    )
    head = resolve_approval_recipient(conn, application)
    creator = conn.execute(text("""
        SELECT created_by FROM public.personnel_orders WHERE order_id=:id
    """), {"id": application["personnel_order_id"]}).scalar_one()
    task = ensure_hire_approval_task(conn, application=application,
                                     fingerprint=conditions_hash(application),
                                     head_user_id=head, created_by_user_id=int(creator))
    visa = current_visa(conn, application)
    if visa and visa["is_current"]:
        finish_hire_approval_task(conn, task_id=int(task["task_id"]),
                                  decision=visa["decision"], explanation=visa["explanation"],
                                  decided_at=visa["decided_at"])
    return task


def queue_approval_notification(conn: Connection, application_id: int) -> dict[str, Any]:
    app = load_electronic_hire(conn, application_id)
    if app["approval_mode"] != "electronic":
        return {"status": "paper", "recipient_user_id": None}
    fingerprint = conditions_hash(app)
    head = resolve_approval_recipient(conn, app)
    status = "pending"
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
    if app["approval_mode"] != "electronic":
        return notification
    head = resolve_approval_recipient(conn, app)
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
    if app["approval_mode"] != "electronic":
        return {"status": "paper", "recipient_user_id": None}
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
    head = resolve_approval_recipient(conn, app)
    if head != actor_user_id:
        raise ElectronicHireError("Вы не назначены согласующим для этого заявления.", "HEAD_ACCESS_DENIED")
    if decision not in {"approved", "rejected"}:
        raise ElectronicHireError("Выберите согласие или отказ.", "DECISION_INVALID")
    if decision == "rejected" and not (explanation or "").strip():
        raise ElectronicHireError("При отказе требуется пояснение.", "EXPLANATION_REQUIRED")
    task = ensure_approval_task(conn, app)
    latest = current_visa(conn, app)
    if latest and latest["is_current"]:
        if latest["decision"] == decision and latest["explanation"] == (explanation or None):
            return latest
        raise ElectronicHireError("Решение по текущим условиям уже сохранено.", "VISA_ALREADY_RECORDED")
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
    from app.personnel_applications.application.hire_approval_task_service import finish_hire_approval_task
    finish_hire_approval_task(conn, task_id=int(task["task_id"]), decision=decision,
                              explanation=explanation, decided_at=row["decided_at"])
    return {**dict(row), "is_current": True}
