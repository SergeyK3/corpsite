"""One local training HIRE approval attempt backed by the production business services.

The caller must enforce the training-only database guard before invoking writes.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import json
import os

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.application.electronic_hire_service import (
    ElectronicHireError, conditions, conditions_hash, current_visa, load_electronic_hire,
    record_visa, require_current_approval, resolve_unit_head,
)
from app.personnel_applications.application.hire_order_draft_service import create_hire_order_draft_for_application
from app.personnel_applications.application.registration_service import register_personnel_application
from app.services.tasks_fsm import transition


def _object(conn: Connection, attempt_id: int) -> dict | None:
    row = conn.execute(text("""
        SELECT application_id, order_id, task_id FROM public.training_attempt_objects
        WHERE attempt_id=:id AND object_role='hire_approval'
    """), {"id": attempt_id}).mappings().one_or_none()
    return dict(row) if row else None


def _system_hr(conn: Connection) -> int:
    value = conn.execute(text("""
        SELECT user_id FROM public.users
        WHERE login='training_hr_partner_20261121' AND password_hash IS NULL
          AND is_active=TRUE ORDER BY user_id LIMIT 1
    """)).scalar_one_or_none()
    if value is None:
        raise RuntimeError("Не подготовлен системный кадровый партнёр учебной среды.")
    return int(value)


def _event(conn: Connection, attempt_id: int, kind: str, event: str, detail: dict | None = None,
           user_id: int | None = None) -> None:
    conn.execute(text("""
        INSERT INTO public.training_attempt_events(attempt_id, actor_kind, actor_user_id, event_type, detail)
        VALUES (:id, :kind, :user, :event, CAST(:detail AS jsonb))
    """), {"id": attempt_id, "kind": kind, "user": user_id, "event": event,
           "detail": json.dumps(detail or {}, ensure_ascii=False)})


def _period(conn: Connection) -> int:
    today = date.today()
    first = today.replace(day=1)
    end = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    existing = conn.execute(text("""
        SELECT period_id FROM public.reporting_periods
        WHERE kind='monthly' AND date_start=:start AND date_end=:end
        ORDER BY period_id LIMIT 1
    """), {"start": first, "end": end}).scalar_one_or_none()
    if existing:
        return int(existing)
    return int(conn.execute(text("""
        INSERT INTO public.reporting_periods(kind,date_start,date_end,label)
        VALUES ('monthly',:start,:end,:label) RETURNING period_id
    """), {"start": first, "end": end, "label": f"Учебный период {first:%Y-%m}"}).scalar_one())


def prepare(conn: Connection, *, attempt_id: int, participant_user_id: int,
            participant_role_id: int) -> dict:
    """Create all records once, inside the attempt-start transaction."""
    previous = _object(conn, attempt_id)
    if previous:
        return fixture(conn, attempt_id)
    hr_user_id = _system_hr(conn)
    unit_id = int(conn.execute(text("""
        INSERT INTO public.org_units(name,code,parent_unit_id,is_active)
        VALUES (:name,:code,:parent,TRUE) RETURNING unit_id
    """), {"name": f"Учебное отделение №{attempt_id}",
           "code": f"TRN-HIRE-{attempt_id}",
           "parent": int(os.getenv("CORPSITE_TRAINING_PARENT_UNIT_ID", "8"))}).scalar_one())
    conn.execute(text("""
        INSERT INTO public.org_unit_managers(unit_id,user_id,manager_type,date_from,is_active)
        VALUES (:unit,:user,'HEAD',CURRENT_DATE,TRUE)
    """), {"unit": unit_id, "user": participant_user_id})
    _event(conn, attempt_id, "system", "unit_prepared", {"unit_id": unit_id})
    iin = f"9{attempt_id:011d}"
    start_date = date.today() + timedelta(days=14)
    registered = register_personnel_application(
        conn, iin_raw=iin, full_name="Тестовая Алия Нурлановна",
        birth_date=date(1992, 4, 17), application_received_at=date.today(),
        vacancy_check_status="pending", vacancy_checked_at=None,
        vacancy_checked_by_user_id=None, intended_org_group_id=None,
        intended_org_unit_id=unit_id,
        intended_position_id=int(os.getenv("CORPSITE_TRAINING_POSITION_ID", "25")),
        intended_employment_rate=Decimal("0.50"), intended_vacancy_text=None,
        contact_mobile_phone="+77000000000", contact_email=None,
        hr_note=f"Учебная попытка {attempt_id}; вымышленный кандидат",
        idempotency_key=f"training-hire-{attempt_id}",
        registered_by_user_id=hr_user_id, actor_id=f"user:{hr_user_id}",
        application_source="electronic",
    )
    if registered.action != "created":
        raise RuntimeError("Учебное заявление не было создано заново.")
    conn.execute(text("""
        INSERT INTO public.electronic_hire_applications(application_id,planned_start_date)
        VALUES (:id,:start)
    """), {"id": registered.application_id, "start": start_date})
    conn.execute(text("""
        UPDATE public.persons SET last_name='Тестовая', first_name='Алия',
            middle_name='Нурлановна' WHERE person_id=:id
    """), {"id": registered.person_id})
    conn.execute(text("""
        INSERT INTO public.person_contacts(person_id,mobile_phone)
        VALUES (:id,'+77000000000')
        ON CONFLICT(person_id) DO UPDATE SET mobile_phone=EXCLUDED.mobile_phone
    """), {"id": registered.person_id})
    conn.execute(text("""
        INSERT INTO public.person_education(person_id,education_kind,institution_name)
        SELECT :id,code,'Учебный медицинский институт (вымышленный)'
        FROM public.education_program_kinds ORDER BY code LIMIT 1
    """), {"id": registered.person_id})
    order = create_hire_order_draft_for_application(
        conn, application_id=registered.application_id, created_by_user_id=hr_user_id)
    task_id = int(conn.execute(text("""
        INSERT INTO public.tasks
          (period_id,title,description,initiator_user_id,executor_role_id,status_id,
           created_by_user_id,task_kind,requires_report,requires_approval,source_kind,source_note)
        VALUES (:period,:title,:description,:hr,:role,:status,:hr,'adhoc',TRUE,FALSE,
                'manual',:note) RETURNING task_id
    """), {"period": _period(conn),
           "title": f"Согласовать учебное заявление №{registered.application_id}",
           "description": "Проверить условия и сохранить согласие в учебной записи.",
           "hr": hr_user_id, "role": participant_role_id,
           "status": conn.execute(text("SELECT status_id FROM public.task_statuses WHERE code='IN_PROGRESS'")).scalar_one(),
           "note": f"training_attempt:{attempt_id}"}).scalar_one())
    conn.execute(text("""
        INSERT INTO public.training_attempt_objects
          (attempt_id,application_id,order_id,task_id,object_role)
        VALUES (:attempt,:application,:order,:task,'hire_approval')
    """), {"attempt": attempt_id, "application": registered.application_id,
           "order": order.personnel_order_id, "task": task_id})
    _event(conn, attempt_id, "system", "hire_application_prepared", {
        "person_id": registered.person_id, "application_id": registered.application_id,
        "order_id": order.personnel_order_id, "task_id": task_id,
    })
    return fixture(conn, attempt_id)


def fixture(conn: Connection, attempt_id: int) -> dict:
    obj = _object(conn, attempt_id)
    if not obj:
        raise RuntimeError("У попытки нет учебного заявления.")
    app = load_electronic_hire(conn, int(obj["application_id"]))
    return {
        "full_name": app["full_name"], "org_unit": app["org_unit_ru"],
        "position": app["position_ru"], "rate": str(app["intended_employment_rate"]),
        "start_date": str(app["planned_start_date"]),
        "application_number": app["application_id"],
        "order_number": obj["order_id"], "task_number": obj["task_id"],
        "person_id": app["person_id"], "org_unit_id": app["intended_org_unit_id"],
        "position_id": app["intended_position_id"],
        "conditions_hash": conditions_hash(app),
    }


def record(conn: Connection, attempt_id: int) -> dict:
    obj = _object(conn, attempt_id)
    if not obj:
        raise ValueError("Учебная запись не найдена.")
    app = load_electronic_hire(conn, int(obj["application_id"]))
    visa = current_visa(conn, app)
    task = conn.execute(text("""
        SELECT s.code AS status, t.task_id FROM public.tasks t
        JOIN public.task_statuses s USING(status_id) WHERE t.task_id=:id
    """), {"id": obj["task_id"]}).mappings().one()
    order = conn.execute(text("""
        SELECT status,order_number FROM public.personnel_orders WHERE order_id=:id
    """), {"id": obj["order_id"]}).mappings().one()
    attempt_status = conn.execute(text("""
        SELECT status FROM public.training_attempts WHERE attempt_id=:id
    """), {"id": attempt_id}).scalar_one()
    order_visa_valid = False
    if visa and visa["decision"] == "approved" and visa["is_current"]:
        try:
            require_current_approval(conn, int(obj["order_id"]))
            order_visa_valid = True
        except ElectronicHireError:
            pass
    approver = None
    if visa:
        approver = conn.execute(text("SELECT full_name FROM public.users WHERE user_id=:id"),
                                {"id": visa["decided_by_user_id"]}).scalar_one_or_none()
    return {**fixture(conn, attempt_id), "task_status": task["status"],
            "attempt_status": attempt_status, "order_visa_valid": order_visa_valid,
            "order_status": order["status"], "order_registered_number": order["order_number"],
            "visa": {"decision": visa["decision"], "decided_at": visa["decided_at"],
                     "decided_by_user_id": visa["decided_by_user_id"],
                     "decided_by_name": approver, "is_current": visa["is_current"]} if visa else None}


def consent(conn: Connection, *, attempt_id: int, participant_user_id: int,
            participant_role_id: int) -> dict:
    obj = _object(conn, attempt_id)
    if not obj:
        raise ValueError("Учебная запись не найдена.")
    app = load_electronic_hire(conn, int(obj["application_id"]))
    if resolve_unit_head(conn, int(app["intended_org_unit_id"])) != participant_user_id:
        raise ValueError("Заявление назначено другому руководителю.")
    old = current_visa(conn, app)
    visa = record_visa(conn, int(obj["application_id"]), actor_user_id=participant_user_id,
                       decision="approved", explanation=None)
    if not old or old["visa_id"] != visa["visa_id"]:
        _event(conn, attempt_id, "participant", "consent_saved",
               {"application_id": obj["application_id"], "visa_id": visa["visa_id"]},
               participant_user_id)
    task_status = conn.execute(text("""
        SELECT s.code FROM public.tasks t JOIN public.task_statuses s USING(status_id)
        WHERE t.task_id=:id
    """), {"id": obj["task_id"]}).scalar_one()
    if task_status != "DONE":
        transition(conn=conn, task_id=int(obj["task_id"]), action="report",
                   actor_user_id=participant_user_id, actor_role_id=participant_role_id,
                   payload={"report_link": f"/training/attempts/{attempt_id}/record",
                            "comment": "Согласие с условиями учебного заявления сохранено."})
        _event(conn, attempt_id, "participant", "task_completed",
               {"task_id": obj["task_id"]}, participant_user_id)
    return record(conn, attempt_id)


def verify_partner(conn: Connection, attempt_id: int) -> dict:
    """Check the order using the existing approval gate after consent is committed."""
    obj = _object(conn, attempt_id)
    if not obj:
        raise RuntimeError("Связанный черновик приказа не найден.")
    require_current_approval(conn, int(obj["order_id"]))
    if not conn.execute(text("""
        SELECT EXISTS(SELECT 1 FROM public.training_attempt_events
                      WHERE attempt_id=:id AND actor_kind='system'
                        AND event_type='order_visa_verified')
    """), {"id": attempt_id}).scalar_one():
        app = load_electronic_hire(conn, int(obj["application_id"]))
        visa = current_visa(conn, app)
        _event(conn, attempt_id, "system", "order_visa_verified",
               {"order_id": obj["order_id"], "visa_id": visa["visa_id"] if visa else None})
    conn.execute(text("""
        UPDATE public.training_attempts SET status='in_progress'
        WHERE attempt_id=:id AND status='technical_pause'
    """), {"id": attempt_id})
    return record(conn, attempt_id)


def business_check(conn: Connection, *, attempt_id: int, participant_user_id: int,
                   issued: dict) -> tuple[bool, str, bool]:
    """Return (all mandatory business facts, exact reason, technical failure)."""
    obj = _object(conn, attempt_id)
    if not obj:
        return False, "Учебное заявление этой попытки отсутствует.", True
    app = load_electronic_hire(conn, int(obj["application_id"]))
    if int(issued.get("application_number") or 0) != obj["application_id"]:
        return False, "Заявление не совпадает с выданным этой попытке.", False
    if int(issued.get("order_number") or 0) != obj["order_id"]:
        return False, "Черновик приказа не совпадает с выданным.", False
    if int(issued.get("task_number") or 0) != obj["task_id"]:
        return False, "Задача не совпадает с выданной.", False
    if issued.get("conditions_hash") != conditions_hash(app):
        return False, "Условия заявления изменились после выдачи задания.", False
    if (issued.get("full_name") != app["full_name"] or
        issued.get("org_unit") != app["org_unit_ru"] or
        issued.get("position") != app["position_ru"] or
        str(issued.get("rate")) != str(app["intended_employment_rate"]) or
        issued.get("start_date") != str(app["planned_start_date"])):
        return False, "Реквизиты заявления не совпадают с заданием.", False
    if resolve_unit_head(conn, int(app["intended_org_unit_id"])) != participant_user_id:
        return False, "Согласующий этого заявления изменился.", False
    visa = current_visa(conn, app)
    if not visa or not visa["is_current"] or visa["decision"] != "approved" or visa["decided_by_user_id"] != participant_user_id:
        return False, "Согласие нужного руководителя не сохранено.", False
    task_status = conn.execute(text("""
        SELECT s.code FROM public.tasks t JOIN public.task_statuses s USING(status_id)
        WHERE t.task_id=:id
    """), {"id": obj["task_id"]}).scalar_one_or_none()
    if task_status != "DONE":
        return False, "Задача согласования не завершена.", False
    try:
        require_current_approval(conn, int(obj["order_id"]))
    except Exception as exc:
        return False, f"Системный партнёр не подтвердил визу в приказе: {exc}", True
    status = conn.execute(text("SELECT status FROM public.personnel_orders WHERE order_id=:id"),
                          {"id": obj["order_id"]}).scalar_one()
    if status != "DRAFT":
        return False, "Связанный приказ перестал быть черновиком.", False
    return True, "Условия, согласие, задача и виза в черновике приказа подтверждены.", False
