"""HR electronic HIRE applications and printable candidate statements."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.rbac import require_personnel_admin_or_403
from app.personnel_applications.application.electronic_hire_service import (
    ElectronicHireError, conditions_hash, current_visa, dispatch_approval_notification, load_electronic_hire, mark_candidate_checked,
    record_visa, render_application, resolve_approval_recipient, retry_approval_notification, update_conditions,
    configured_approval_mode, current_paper_confirmation, record_paper_confirmation,
)
from app.personnel_applications.application.registration_service import register_personnel_application
from app.personnel_applications.domain.errors import (
    ActiveEmployeeBlocksRegistrationError,
    PersonnelApplicationConflictError,
    PersonnelApplicationValidationError,
)
from app.personnel_intake.infrastructure.photo_storage import ensure_intake_photo_storage_root, resolve_path_within_root
from app.personnel_intake.application.hr_link_access_service import get_hr_intake_link_display
from app.personnel_applications.application.electronic_hire_service import send_telegram_text

router = APIRouter(prefix="/electronic-hire", tags=["electronic-hire"])


def _hr_user_id(user: dict) -> int:
    require_personnel_admin_or_403(user)
    uid = user.get("user_id") or user.get("id")
    if uid is None:
        raise HTTPException(401, "Unauthorized")
    return int(uid)


def _error(exc: ElectronicHireError) -> HTTPException:
    return HTTPException(422, {"code": exc.code, "message": str(exc)})


class ElectronicHireCreateIn(BaseModel):
    iin: str = Field(min_length=12, max_length=12)
    full_name: str = Field(min_length=1)
    birth_date: date | None = None
    application_received_at: date
    planned_start_date: date
    org_group_id: int | None = None
    org_unit_id: int = Field(ge=1)
    position_id: int = Field(ge=1)
    employment_rate: Decimal = Field(gt=0, le=2)
    contact_mobile_phone: str | None = None
    contact_email: str | None = None
    idempotency_key: str | None = None


class ElectronicHireConditionsIn(BaseModel):
    org_unit_id: int = Field(ge=1)
    position_id: int = Field(ge=1)
    employment_rate: Decimal = Field(gt=0, le=2)
    planned_start_date: date
    mode_change_reason: str | None = None


class VisaIn(BaseModel):
    decision: str
    explanation: str | None = None


class PaperConfirmationIn(BaseModel):
    approver_name: str = Field(min_length=1)
    approved_on: date
    note: str | None = None
    attachment_id: int | None = None


@router.get("/units/{unit_id}/approval-mode")
def get_hire_unit_approval_mode(unit_id: int, user: dict = Depends(get_current_user)) -> dict:
    _hr_user_id(user)
    try:
        with engine.connect() as conn:
            return {"unit_id": unit_id, "approval_mode": configured_approval_mode(conn, unit_id)}
    except ElectronicHireError as exc:
        raise _error(exc) from exc


@router.get("/former-candidates")
def search_former_candidates(q: str, user: dict = Depends(get_current_user)) -> dict:
    _hr_user_id(user)
    query = q.strip()
    if len(query) < 2:
        return {"items": []}
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT p.person_id, p.full_name, p.iin
            FROM public.persons p
            JOIN public.employees e ON e.person_id = p.person_id
            WHERE e.is_active = FALSE AND p.person_status = 'active'
              AND NOT EXISTS (SELECT 1 FROM public.employees active_e
                              WHERE active_e.person_id = p.person_id AND active_e.is_active = TRUE)
              AND (p.iin = :exact OR p.full_name ILIKE :pattern)
            ORDER BY p.full_name, p.person_id LIMIT 20
        """), {"exact": query, "pattern": f"%{query}%"}).mappings().all()
    return {"items": [dict(row) for row in rows]}


@router.post("/applications")
def create_electronic_hire(body: ElectronicHireCreateIn, user: dict = Depends(get_current_user)) -> dict:
    actor = _hr_user_id(user)
    try:
        with engine.begin() as conn:
            result = register_personnel_application(
                conn, iin_raw=body.iin, full_name=body.full_name,
                birth_date=body.birth_date, application_received_at=body.application_received_at,
                vacancy_check_status="pending", vacancy_checked_at=None,
                vacancy_checked_by_user_id=None, intended_org_group_id=body.org_group_id,
                intended_org_unit_id=body.org_unit_id, intended_position_id=body.position_id,
                intended_employment_rate=body.employment_rate, intended_vacancy_text=None,
                contact_mobile_phone=body.contact_mobile_phone, contact_email=body.contact_email,
                hr_note=None, idempotency_key=body.idempotency_key,
                registered_by_user_id=actor, actor_id=f"user:{actor}", application_source="electronic",
            )
            if result.action == "created":
                conn.execute(text("""
                    INSERT INTO public.electronic_hire_applications (application_id, planned_start_date, approval_mode)
                    VALUES (:id, :start, :mode)
                """), {"id": result.application_id, "start": body.planned_start_date,
                       "mode": configured_approval_mode(conn, body.org_unit_id)})
            app = load_electronic_hire(conn, result.application_id)
            return {"application_id": result.application_id, "person_id": result.person_id,
                    "card_href": result.card_href, "action": result.action,
                    "planned_start_date": app["planned_start_date"], "approval_mode": app["approval_mode"]}
    except ElectronicHireError as exc:
        raise _error(exc) from exc
    except ActiveEmployeeBlocksRegistrationError as exc:
        raise HTTPException(409, {"code": exc.code, "message": "Кандидат уже работает. Приём через заявление недоступен."}) from exc
    except PersonnelApplicationConflictError as exc:
        raise HTTPException(409, {"code": exc.code, "message": str(exc)}) from exc
    except PersonnelApplicationValidationError as exc:
        raise HTTPException(422, {"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(422, {"message": str(exc)}) from exc


@router.get("/applications")
def list_electronic_hire(user: dict = Depends(get_current_user)) -> dict:
    _hr_user_id(user)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT a.application_id, a.person_id, p.full_name, a.status,
                   e.planned_start_date, a.personnel_order_id
            FROM public.electronic_hire_applications e
            JOIN public.personnel_applications a USING (application_id)
            JOIN public.persons p ON p.person_id=a.person_id
            WHERE a.status NOT IN ('completed','cancelled','withdrawn','expired')
            ORDER BY a.application_id DESC LIMIT 50
        """)).mappings().all()
    return {"items": [dict(row) for row in rows]}


@router.get("/applications/{application_id}")
def get_electronic_hire(application_id: int, user: dict = Depends(get_current_user)) -> dict:
    _hr_user_id(user)
    try:
        with engine.connect() as conn:
            app = load_electronic_hire(conn, application_id)
            visa = current_visa(conn, app)
            notification = conn.execute(text("""
                SELECT notification_id, status, recipient_user_id, attempts, last_error
                FROM public.electronic_hire_notifications
                WHERE application_id=:id AND conditions_hash=:hash
            """), {"id": application_id, "hash": conditions_hash(app)}).mappings().first()
            recipient_error = None
            if app["approval_mode"] == "electronic" and not (visa and visa["is_current"]):
                try:
                    resolve_approval_recipient(conn, app)
                except ElectronicHireError as exc:
                    recipient_error = str(exc)
            return {**app, "current_visa": visa, "current_paper_confirmation": current_paper_confirmation(conn, app),
                    "recipient_error": recipient_error,
                    "notification": dict(notification) if notification else None}
    except ElectronicHireError as exc:
        raise _error(exc) from exc


@router.patch("/applications/{application_id}/conditions")
def patch_electronic_hire_conditions(application_id: int, body: ElectronicHireConditionsIn,
                                   user: dict = Depends(get_current_user)) -> dict:
    actor = _hr_user_id(user)
    try:
        with engine.begin() as conn:
            result = update_conditions(conn, application_id, org_unit_id=body.org_unit_id,
                                     position_id=body.position_id, employment_rate=body.employment_rate,
                                     planned_start_date=body.planned_start_date,
                                     actor_user_id=actor, mode_change_reason=body.mode_change_reason)
        if result["personnel_order_id"] is not None:
            with engine.begin() as conn:
                dispatch_approval_notification(conn, application_id)
        return result
    except ElectronicHireError as exc:
        raise _error(exc) from exc


@router.get("/applications/{application_id}/print")
def get_electronic_hire_print(application_id: int, user: dict = Depends(get_current_user)) -> dict:
    _hr_user_id(user)
    try:
        with engine.connect() as conn:
            return render_application(conn, application_id)
    except ElectronicHireError as exc:
        raise _error(exc) from exc


@router.post("/applications/{application_id}/candidate-checked")
def post_candidate_checked(application_id: int, user: dict = Depends(get_current_user)) -> dict:
    actor = _hr_user_id(user)
    try:
        with engine.begin() as conn:
            mark_candidate_checked(conn, application_id, actor)
            return {"candidate_checked": True}
    except ElectronicHireError as exc:
        raise _error(exc) from exc


@router.post("/applications/{application_id}/order-draft")
def post_electronic_hire_order_draft(application_id: int, user: dict = Depends(get_current_user)) -> dict:
    actor = _hr_user_id(user)
    from app.personnel_applications.application.hire_order_draft_service import create_hire_order_draft_for_application
    from app.personnel_applications.domain.errors import PersonnelApplicationHireOrderError
    try:
        with engine.begin() as conn:
            app = load_electronic_hire(conn, application_id)
            result = create_hire_order_draft_for_application(conn, application_id=app["application_id"], created_by_user_id=actor)
        with engine.begin() as conn:
            notification = dispatch_approval_notification(conn, application_id)
        return {"application_id": application_id, "personnel_order_id": result.personnel_order_id,
                "idempotent_replay": result.idempotent_replay, "notification": notification}
    except (PersonnelApplicationHireOrderError, ElectronicHireError) as exc:
        raise HTTPException(422, {"code": getattr(exc, "code", "ORDER_DRAFT_INVALID"), "message": str(exc)}) from exc


@router.post("/applications/{application_id}/paper-confirmation")
def post_hire_paper_confirmation(application_id: int, body: PaperConfirmationIn,
                                 user: dict = Depends(get_current_user)) -> dict:
    actor = _hr_user_id(user)
    try:
        with engine.begin() as conn:
            return record_paper_confirmation(conn, application_id, actor_user_id=actor,
                                             approver_name=body.approver_name,
                                             approved_on=body.approved_on, note=body.note,
                                             attachment_id=body.attachment_id)
    except ElectronicHireError as exc:
        raise _error(exc) from exc


@router.get("/applications/{application_id}/visas")
def list_electronic_hire_visas(application_id: int, user: dict = Depends(get_current_user)) -> dict:
    _hr_user_id(user)
    with engine.connect() as conn:
        app = load_electronic_hire(conn, application_id)
        rows = conn.execute(text("""
            SELECT visa_id, decision, explanation, conditions, conditions_hash,
                   decided_by_user_id, decided_at FROM public.electronic_hire_visas
            WHERE application_id=:id ORDER BY visa_id DESC
        """), {"id": application_id}).mappings().all()
        return {"items": [{**dict(row), "is_current": row["conditions_hash"] == conditions_hash(app)} for row in rows]}


@router.get("/orders/{order_id}/application")
def get_electronic_hire_by_order(order_id: int, user: dict = Depends(get_current_user)) -> dict:
    _hr_user_id(user)
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT a.application_id FROM public.personnel_applications a
            JOIN public.electronic_hire_applications e USING (application_id)
            WHERE a.personnel_order_id=:order
        """), {"order": order_id}).mappings().first()
        if row is None:
            raise HTTPException(404, "Электронное заявление не связано с приказом.")
        app = load_electronic_hire(conn, int(row["application_id"]))
        visas = conn.execute(text("""
            SELECT visa_id, decision, explanation, conditions, conditions_hash,
                   decided_by_user_id, decided_at FROM public.electronic_hire_visas
            WHERE application_id=:id ORDER BY visa_id DESC
        """), {"id": app["application_id"]}).mappings().all()
        return {"application_id": app["application_id"], "full_name": app["full_name"],
                "approval_mode": app["approval_mode"],
                "current_paper_confirmation": current_paper_confirmation(conn, app),
                "current_visa": current_visa(conn, app),
                "visas": [{**dict(visa), "is_current": visa["conditions_hash"] == conditions_hash(app)} for visa in visas]}


@router.post("/applications/{application_id}/notification/retry")
def post_electronic_hire_notification_retry(application_id: int, user: dict = Depends(get_current_user)) -> dict:
    _hr_user_id(user)
    try:
        with engine.begin() as conn:
            retry_approval_notification(conn, application_id)
            return dispatch_approval_notification(conn, application_id)
    except ElectronicHireError as exc:
        raise _error(exc) from exc


@router.get("/approvals")
def list_head_electronic_hire_approvals(application_id: int | None = None,
                                       user: dict = Depends(get_current_user)) -> dict:
    actor = user.get("user_id") or user.get("id")
    if not actor:
        raise HTTPException(401, "Unauthorized")
    try:
        require_personnel_admin_or_403(user)
        is_hr = True
    except HTTPException:
        is_hr = False
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT a.application_id FROM public.personnel_applications a
            JOIN public.electronic_hire_applications e USING (application_id)
            WHERE a.personnel_order_id IS NOT NULL
              AND a.status NOT IN ('cancelled', 'withdrawn', 'expired')
              AND ((:is_hr AND e.approval_mode='paper') OR
                   (e.approval_mode='electronic' AND
                    (EXISTS (SELECT 1 FROM public.org_unit_managers m
                           WHERE m.unit_id=a.intended_org_unit_id AND m.user_id=:actor
                             AND m.is_active=TRUE AND (m.date_from IS NULL OR m.date_from<=CURRENT_DATE)
                             AND (m.date_to IS NULL OR m.date_to>=CURRENT_DATE))
                   OR EXISTS (SELECT 1 FROM public.electronic_hire_approval_tasks t
                              WHERE t.application_id=a.application_id AND t.head_user_id=:actor))))
            ORDER BY CASE WHEN a.application_id=:target THEN 0 ELSE 1 END,
                     a.application_id DESC LIMIT 100
        """), {"actor": int(actor), "target": application_id or 0, "is_hr": is_hr}).mappings().all()
        items = []
        for row in rows:
            app = load_electronic_hire(conn, int(row["application_id"]))
            if app["approval_mode"] == "paper":
                paper = current_paper_confirmation(conn, app)
                if paper is None or not paper["is_current"]:
                    continue
                paper_history = conn.execute(text("""
                    SELECT c.confirmation_id, c.approver_name, c.approved_on, c.note, c.attachment_id,
                           c.conditions_hash, c.recorded_by_user_id,
                           u.full_name AS recorded_by_name, c.recorded_at
                    FROM public.electronic_hire_paper_confirmations c
                    JOIN public.users u ON u.user_id=c.recorded_by_user_id
                    WHERE c.application_id=:id ORDER BY c.confirmation_id DESC
                """), {"id": app["application_id"]}).mappings().all()
                items.append({"application_id": app["application_id"], "full_name": app["full_name"],
                              "application_type": "hire", "application_type_label": "Приём на работу",
                              "approval_mode": "paper", "org_unit": app["org_unit_ru"],
                              "position": app["position_ru"], "employment_rate": app["intended_employment_rate"],
                              "planned_start_date": app["planned_start_date"],
                              "current_visa": {"visa_id": -paper["confirmation_id"], "decision": "approved",
                                               "is_current": True, "explanation": paper["note"],
                                               "decided_by_user_id": paper["recorded_by_user_id"],
                                               "decided_by_name": paper["approver_name"],
                                               "decided_at": paper["recorded_at"],
                                               "approved_on": paper["approved_on"],
                                               "attachment_id": paper["attachment_id"],
                                               "recorded_by_name": paper["recorded_by_name"], "kind": "paper"},
                              "visa_history": [],
                              "paper_history": [{**dict(p), "is_current": p["conditions_hash"] == conditions_hash(app)} for p in paper_history]})
                continue
            visa = current_visa(conn, app)
            assigned_current = False
            try:
                assigned_current = resolve_approval_recipient(conn, app) == int(actor)
            except ElectronicHireError:
                pass
            historical_task = conn.execute(text("""
                SELECT EXISTS (SELECT 1 FROM public.electronic_hire_approval_tasks
                    WHERE application_id=:id AND head_user_id=:actor AND decision IS NOT NULL)
            """), {"id": app["application_id"], "actor": int(actor)}).scalar_one()
            if not assigned_current and not (historical_task and visa and visa["is_current"]):
                continue
            if app["status"] == "completed" and (visa is None or not visa["is_current"]):
                continue
            history = conn.execute(text("""
                SELECT v.visa_id, v.decision, v.explanation, v.conditions_hash,
                       v.decided_by_user_id, u.full_name AS decided_by_name, v.decided_at
                FROM public.electronic_hire_visas v
                JOIN public.users u ON u.user_id=v.decided_by_user_id
                WHERE v.application_id=:id ORDER BY v.visa_id DESC
            """), {"id": app["application_id"]}).mappings().all()
            paper_history = conn.execute(text("""
                SELECT c.confirmation_id, c.approver_name, c.approved_on, c.note, c.attachment_id,
                       c.conditions_hash, c.recorded_by_user_id,
                       u.full_name AS recorded_by_name, c.recorded_at
                FROM public.electronic_hire_paper_confirmations c
                JOIN public.users u ON u.user_id=c.recorded_by_user_id
                WHERE c.application_id=:id ORDER BY c.confirmation_id DESC
            """), {"id": app["application_id"]}).mappings().all()
            items.append({"application_id": app["application_id"], "full_name": app["full_name"],
                          "application_type": "hire", "application_type_label": "Приём на работу",
                          "approval_mode": "electronic",
                          "org_unit": app["org_unit_ru"], "position": app["position_ru"],
                          "employment_rate": app["intended_employment_rate"],
                          "planned_start_date": app["planned_start_date"],
                          "current_visa": visa,
                          "visa_history": [{**dict(row), "is_current": row["conditions_hash"] == conditions_hash(app)}
                                           for row in history],
                          "paper_history": [{**dict(p), "is_current": p["conditions_hash"] == conditions_hash(app)}
                                            for p in paper_history]})
        return {"items": items}


@router.get("/approvals/{application_id}/statement")
def get_head_electronic_hire_statement(application_id: int,
                                       user: dict = Depends(get_current_user)) -> dict[str, str]:
    # Use the same visibility and historical-task rules as the approval list.
    approvals = list_head_electronic_hire_approvals(application_id=application_id, user=user)
    if not any(item["application_id"] == application_id for item in approvals["items"]):
        raise HTTPException(404, "Заявление недоступно для согласования.")
    try:
        with engine.connect() as conn:
            return render_application(conn, application_id)
    except ElectronicHireError as exc:
        raise _error(exc) from exc


@router.post("/applications/{application_id}/visa")
def post_head_electronic_hire_visa(application_id: int, body: VisaIn,
                                  user: dict = Depends(get_current_user)) -> dict:
    actor = user.get("user_id") or user.get("id")
    if not actor:
        raise HTTPException(401, "Unauthorized")
    try:
        with engine.begin() as conn:
            return record_visa(conn, application_id, actor_user_id=int(actor),
                               decision=body.decision, explanation=body.explanation)
    except ElectronicHireError as exc:
        if exc.code == "HEAD_ACCESS_DENIED":
            raise HTTPException(403, {"code": exc.code, "message": str(exc)}) from exc
        raise _error(exc) from exc


@router.post("/applications/{application_id}/intake-link/telegram")
def send_candidate_intake_link(application_id: int, user: dict = Depends(get_current_user)) -> dict:
    _hr_user_id(user)
    with engine.begin() as conn:
        app = load_electronic_hire(conn, application_id)
        display = get_hr_intake_link_display(conn, application_id)
        if display.display_state != "active" or not display.intake_url_path or display.link_id is None:
            raise HTTPException(422, "Сначала выдайте действующую ссылку на заполнение ЛК.")
        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(display.link_id)})
        existing = conn.execute(text("""
            SELECT status, attempts, last_error FROM public.electronic_hire_link_deliveries
            WHERE link_id=:id
        """), {"id": display.link_id}).mappings().first()
        if existing and existing["status"] == "sent":
            return {"status": "sent", "idempotent_replay": True}
        binding = conn.execute(text("""
            SELECT telegram_user_id FROM public.person_telegram_bindings
            WHERE person_id=:person AND revoked_at IS NULL ORDER BY binding_id DESC LIMIT 1
        """), {"person": app["person_id"]}).mappings().first()
        if binding is None:
            raise HTTPException(422, "У кандидата нет Telegram. ЛК можно заполнить вместе с кадровиком.")
        base = os.getenv("PERSONNEL_INTAKE_PUBLIC_BASE_URL", "").rstrip("/")
        token = os.getenv("INTAKE_BOT_TOKEN", "").strip()
        if not base or not token:
            raise HTTPException(422, "Отправка через Telegram не настроена. ЛК можно заполнить вместе с кадровиком.")
        message = f"Заполните личную карточку по ссылке (действует 24 часа): {base}{display.intake_url_path}"
        error = None
        try:
            send_telegram_text(int(binding["telegram_user_id"]), message, bot_token=token)
        except Exception as exc:
            error = f"Telegram: {type(exc).__name__}"
        status = "failed" if error else "sent"
        conn.execute(text("""
            INSERT INTO public.electronic_hire_link_deliveries
                (link_id, application_id, status, last_error, attempts)
            VALUES (:link, :app, :status, :error, 1)
            ON CONFLICT (link_id) DO UPDATE
            SET status=EXCLUDED.status, last_error=EXCLUDED.last_error,
                attempts=public.electronic_hire_link_deliveries.attempts+1, updated_at=now()
        """), {"link": display.link_id, "app": application_id, "status": status, "error": error})
        return {"status": status, "last_error": error, "idempotent_replay": False}


@router.post("/applications/{application_id}/signed-copy")
async def upload_signed_copy(application_id: int, file: UploadFile = File(...),
                             user: dict = Depends(get_current_user)) -> dict:
    actor = _hr_user_id(user)
    allowed = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
    suffix = allowed.get(file.content_type or "")
    if suffix is None:
        raise HTTPException(422, "Допустимы PDF, JPEG или PNG.")
    data = await file.read(10 * 1024 * 1024 + 1)
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(422, "Файл должен иметь размер от 1 байта до 10 МБ.")
    with engine.begin() as conn:
        try:
            load_electronic_hire(conn, application_id)
        except ElectronicHireError as exc:
            raise _error(exc) from exc
        root = ensure_intake_photo_storage_root()
        path = resolve_path_within_root(root, "signed-applications", str(application_id), uuid4().hex + suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        row = conn.execute(text("""
            INSERT INTO public.electronic_hire_attachments
                (application_id, file_name, content_type, storage_path, uploaded_by_user_id)
            VALUES (:id, :name, :type, :path, :actor) RETURNING attachment_id
        """), {"id": application_id, "name": Path(file.filename or "signed" + suffix).name,
               "type": file.content_type, "path": str(path), "actor": actor}).mappings().one()
    return {"attachment_id": row["attachment_id"], "file_name": file.filename}


@router.get("/applications/{application_id}/signed-copy/{attachment_id}")
def download_signed_copy(application_id: int, attachment_id: int, user: dict = Depends(get_current_user)):
    _hr_user_id(user)
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT file_name, content_type, storage_path FROM public.electronic_hire_attachments
            WHERE application_id=:id AND attachment_id=:attachment
        """), {"id": application_id, "attachment": attachment_id}).mappings().first()
    if row is None:
        raise HTTPException(404, "Файл не найден.")
    root = ensure_intake_photo_storage_root()
    path = Path(row["storage_path"]).resolve()
    if not path.is_relative_to(resolve_path_within_root(root, "signed-applications", str(application_id))) or not path.is_file():
        raise HTTPException(404, "Файл не найден.")
    return FileResponse(path, media_type=row["content_type"], filename=row["file_name"])
