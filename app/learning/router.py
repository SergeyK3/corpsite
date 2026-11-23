"""Training-only API. Enable explicitly in the learning instance."""
from __future__ import annotations

import json
import os
import secrets
from functools import wraps
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, insert, select, text

from app.auth import get_current_user
from app.db.engine import engine
from app.learning.catalog import COURSE, COURSES
from app.learning.model import attempts, criterion_results, screenshot_slots, screenshots, records, hire_applications
from app.learning import expert_service, hire_bridge, hire_path_link, hire_path_rehearsal, service
from app.personnel_intake.domain.errors import PersonnelIntakeError
from app.personnel_applications.domain.errors import PersonnelApplicationError
from app.personnel_applications.application.electronic_hire_service import ElectronicHireError
from app.services.personnel_orders_command_service import PersonnelOrderConflictError
from app.services.personnel_orders_query_service import PersonnelOrderNotFoundError, PersonnelOrderValidationError
from app.services.personnel_orders_editorial.exceptions import PersonnelOrderReadyGateError, PersonnelOrderEditorialConflictError
from app.person_photos.domain.errors import PersonPhotoError
from app.services.personnel_order_acknowledgement_service import PersonnelOrderAcknowledgementError
from app.personnel_files import storage
from app.security.platform_role_classification import LEADERSHIP_PLATFORM_ROLE_CODES

router = APIRouter(prefix="/learning", tags=["learning"])
preview_users: dict | None = None


def enabled() -> None:
    if os.getenv("LEARNING_PILOT_ENABLED") != "1":
        raise HTTPException(503, "Пилот обучения не включён в этом экземпляре")
    name = engine.url.database or ""
    local_test = name == "corpsite_test" and os.getenv("APP_ENV", "dev").lower() not in {"prod", "production"}
    isolated_server = name == "corpsite_learn" and os.getenv("TRAINING_SERVER_ENABLED") == "1"
    rehearsal = name.startswith("corpsite_learn_rehearsal_") and os.getenv("TRAINING_REHEARSAL") == "1" and os.getenv("APP_ENV", "dev").lower() not in {"prod", "production"}
    if engine.url.host not in {"127.0.0.1", "localhost", "::1"} or not (local_test or isolated_server or rehearsal):
        raise HTTPException(503, "Обучение доступно только в отдельной учебной базе")
    if os.getenv("TRAINING_MODE") != "1" or os.getenv("TRAINING_DISABLE_EXTERNAL") != "1":
        raise HTTPException(503, "Учебный режим и запрет внешних уведомлений обязательны")


class RecordIn(BaseModel):
    application_ref: str = Field(min_length=7, max_length=100)
    action: str
    detail: str = ""


class AttemptIn(BaseModel):
    lesson_code: str
    record_id: str


class ReviewIn(BaseModel):
    score: int = Field(ge=0, le=5)
    required_met: bool
    note: str = ""
    criteria: list[bool] | None = None
    reason: str = ""


class CourseIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    audience: str = Field(default="", max_length=120)


class LessonIn(BaseModel):
    course_code: str
    title: str = Field(min_length=1, max_length=200)
    target_role: str = Field(min_length=1, max_length=120)
    minutes: int = Field(ge=1, le=480)
    task: str = Field(min_length=1)
    instruction: str = ""
    guide_url: str = ""
    criteria: list[str] = Field(min_length=5, max_length=5)
    required_index: int = 0
    screenshots: list[str] = Field(min_length=1, max_length=5)


class AssignmentSelector(BaseModel):
    employee_ids: list[int] = Field(default_factory=list)
    position_name: str = ""
    unit_id: int | None = None


class AssignmentIn(BaseModel):
    target_type: str
    target_code: str
    selector: AssignmentSelector
    due_at: datetime | None = None
    expected_recipient_ids: list[int] = Field(default_factory=list)


class AutomaticResultIn(BaseModel):
    criteria: list[bool]
    note: str = ""


class AutomaticFailureIn(BaseModel):
    note: str = ""


class HireApplicationIn(BaseModel):
    confirmed: bool = True


class HireNumberIn(BaseModel):
    number: str = Field(min_length=1, max_length=80)


class HireEditorialBodyIn(BaseModel):
    locale: str
    text: str = Field(min_length=1, max_length=5000)


class HireReviewDecisionIn(BaseModel):
    decision: str


class HireAcknowledgementIn(BaseModel):
    method: str = "training_cabinet"
    evidence: str


def rehearsal_errors(fn):
    """Convert expected personnel-domain denials into actionable API errors."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except HTTPException:
            raise
        except PersonnelOrderReadyGateError as exc:
            raise HTTPException(422, {"code": "READY_GATE_FAILED", "problems": exc.problems}) from exc
        except (PersonnelOrderConflictError, PersonnelOrderEditorialConflictError) as exc:
            raise HTTPException(409, str(exc)) from exc
        except (PersonnelApplicationError, PersonnelIntakeError, ElectronicHireError,
                PersonnelOrderValidationError, PersonnelOrderAcknowledgementError,
                PersonPhotoError) as exc:
            raise HTTPException(422, {"code": getattr(exc, "code", type(exc).__name__),
                                      "message": str(exc)}) from exc
        except PersonnelOrderNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
    return wrapped


def require_expert(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if not user.get("has_learning_expert"):
        raise HTTPException(403, "Нет разрешения на кабинет внутреннего обучения")
    return user


@router.get("/catalog", dependencies=[Depends(enabled)])
def catalog(user: dict[str, Any] = Depends(get_current_user)):
    service.unit(user)
    with engine.connect() as conn:
        result = expert_service.visible_catalog(conn, user)
    return {**result, "guide": {"available": bool(approved_guide()),
                                "version": os.getenv("LEARNING_APPROVED_GUIDE_VERSION", "")}}


def approved_guide() -> Path | None:
    configured = os.getenv("LEARNING_APPROVED_GUIDE_PATH", "")
    version = os.getenv("LEARNING_APPROVED_GUIDE_VERSION", "")
    if not configured or not version:
        return None
    path = Path(configured).resolve()
    return path if path.is_file() and path.suffix.lower() in {".pdf", ".docx"} else None


@router.get("/guide", dependencies=[Depends(enabled)])
def guide(user: dict[str, Any] = Depends(get_current_user)):
    service.unit(user)
    path = approved_guide()
    if path is None:
        raise HTTPException(404, "Утверждённое руководство ещё не прикреплено к курсу")
    mime = "application/pdf" if path.suffix.lower() == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(path, media_type=mime, filename=path.name, headers={"Cache-Control": "private, no-store"})


@router.get("/assignments/{lesson_code}", dependencies=[Depends(enabled)])
def assignment(lesson_code: str, user: dict[str, Any] = Depends(get_current_user)):
    uid, unit_id = int(user["user_id"]), service.unit(user)
    with engine.connect() as conn:
        lesson = expert_service.lesson(conn, lesson_code)
        if lesson_code not in {item["code"] for item in expert_service.assigned_lessons(conn, uid, unit_id, user.get("role_code"))}:
            raise HTTPException(404, "Занятие не назначено")
        existing = conn.execute(select(records.c.application_ref).join(attempts, attempts.c.record_id == records.c.id).where(
            and_(attempts.c.participant_id == uid, attempts.c.unit_id == unit_id, attempts.c.lesson_code == lesson_code)
        ).order_by(attempts.c.attempt_no.desc())).scalar()
    group = "main" if lesson_code in {"resolution_1", "resolution_2", "visa_history_1"} else "objection" if lesson["expected_action"] == "rejected" else lesson_code
    ref = existing or f"LEARN-{unit_id}-{uid}-{group}"
    return {"lesson_code": lesson_code, "application_ref": ref, "work_url": None,
            "message": "Рабочий экран учебного заявления пока не подключён к пилоту. Нужна запись, выданная этому участнику, и её адрес в учебной среде."}


@router.post("/records", dependencies=[Depends(enabled)])
def create_record(body: RecordIn, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return service.record_action(conn, user, body.application_ref, body.action, body.detail)


@router.post("/attempts", dependencies=[Depends(enabled)])
def create_attempt(body: AttemptIn, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return service.start_attempt(conn, user, body.lesson_code, body.record_id)


@router.post("/lessons/{lesson_code}/hire-attempts", dependencies=[Depends(enabled)])
def start_hire_attempt(lesson_code: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return service.start_hire_attempt(conn, user, lesson_code)


def hire_state(conn, user: dict, attempt_id: str) -> dict:
    attempt = service.owned_attempt(conn, user, attempt_id)
    lesson = service.lesson_for_attempt(conn, attempt)
    if not hire_bridge.is_hire_lesson(lesson):
        raise HTTPException(404, "Кадровая форма для попытки не найдена")
    link = conn.execute(select(hire_applications).where(
        hire_applications.c.attempt_id == attempt_id)).mappings().first()
    saved = hire_bridge.application(link["application_id"], attempt_id, conn=conn) if link else None
    return {"attempt_id": attempt_id, "attempt_no": attempt["attempt_no"], "attempt_status": attempt["status"],
            "fixture": hire_bridge.fixture(attempt_id), "application": saved,
            "guide_url": lesson.get("guide_url"), "criteria": lesson["criteria"]}


@router.get("/attempts/{attempt_id}/hire-application", dependencies=[Depends(enabled)])
def get_hire_application(attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        return hire_state(conn, user, attempt_id)


@router.get("/attempts/{attempt_id}/hire-path", dependencies=[Depends(enabled)])
def get_hire_path(attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        return hire_path_link.linked_records(conn, user, attempt_id)


@router.post("/attempts/{attempt_id}/hire-application", dependencies=[Depends(enabled)])
def save_hire_application(attempt_id: str, body: HireApplicationIn,
                          user: dict[str, Any] = Depends(get_current_user)):
    if not body.confirmed:
        raise HTTPException(422, "Подтвердите вымышленные данные заявления")
    with engine.begin() as conn:
        attempt = service.owned_attempt(conn, user, attempt_id)
        lesson = service.lesson_for_attempt(conn, attempt)
        if not hire_bridge.is_hire_lesson(lesson):
            raise HTTPException(404, "Кадровая форма для попытки не найдена")
        link = conn.execute(select(hire_applications).where(
            hire_applications.c.attempt_id == attempt_id)).mappings().first()
        if link is None:
            if attempt["status"] != "draft":
                raise HTTPException(409, "Нельзя сохранить заявление после сдачи")
            expected = hire_bridge.fixture(attempt_id)
            saved = hire_bridge.create_application(conn, attempt_id, int(attempt["participant_id"]), expected)
            conn.execute(insert(hire_applications).values(
                attempt_id=attempt_id, participant_id=attempt["participant_id"], unit_id=attempt["unit_id"],
                application_id=saved["application_id"], person_id=saved["person_id"],
                fixture_json=json.dumps(expected, ensure_ascii=False)))
        return hire_state(conn, user, attempt_id)


@router.get("/attempts/{attempt_id}/hire-application/preview", dependencies=[Depends(enabled)])
def hire_application_preview(attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        service.owned_attempt(conn, user, attempt_id)
        link = conn.execute(select(hire_applications).where(
            hire_applications.c.attempt_id == attempt_id)).mappings().first()
        if link is None:
            raise HTTPException(404, "Заявление ещё не сохранено")
        return hire_bridge.print_preview(link["application_id"], attempt_id)


@router.post("/exercises/approval/start", dependencies=[Depends(enabled)])
def start_approval_exercise(user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return service.start_approval_exercise(conn, user)


@router.get("/exercises/{attempt_id}", dependencies=[Depends(enabled)])
def approval_exercise(attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        return service.approval_exercise(conn, user, attempt_id)


@router.post("/exercises/{attempt_id}/consent", dependencies=[Depends(enabled)])
def consent_approval_exercise(attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return service.save_approval_consent(conn, user, attempt_id)


@router.post("/attempts/{attempt_id}/screenshots", dependencies=[Depends(enabled)])
def upload_screenshot(attempt_id: str, file: UploadFile = File(...), slot: int | None = Form(default=None), user: dict[str, Any] = Depends(get_current_user)):
    mime = file.content_type or ""
    if mime not in {"image/png", "image/jpeg"}:
        raise HTTPException(422, "Нужен PNG или JPEG")
    with engine.connect() as conn:
        attempt = service.owned_attempt(conn, user, attempt_id)
        if attempt["status"] != "draft":
            raise HTTPException(409, "Попытка уже отправлена")
    content = file.file.read(storage.MAX_BYTES + 1)
    if not content or len(content) > storage.MAX_BYTES:
        raise HTTPException(422, "Снимок пуст или превышает 10 МиБ")
    key = str(uuid4())
    checksum, _ = storage.prepare(key, content, mime, "certificate")
    try:
        with engine.begin() as conn:
            return service.attach_screenshot(conn, user, attempt_id, key=key, mime=mime, checksum=checksum, size=len(content), slot=slot)
    except Exception:
        storage.discard(key)
        raise


@router.post("/attempts/{attempt_id}/submit", dependencies=[Depends(enabled)])
def submit(attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return service.submit_attempt(conn, user, attempt_id)


def may_view_work(user: dict[str, Any], participant_id: int, unit_id: int) -> bool:
    return bool(user.get("has_learning_expert") or user.get("has_learning_review")) or (
        unit_id == service.unit(user) and participant_id == int(user["user_id"]))


@router.get("/participants/{participant_id}/lessons/{lesson_code}/attempts", dependencies=[Depends(enabled)])
def lesson_attempts(participant_id: int, lesson_code: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        expert_service.lesson(conn, lesson_code, include_draft=bool(user.get("has_learning_expert")))
        rows = conn.execute(select(attempts).where(and_(attempts.c.participant_id == participant_id,
            attempts.c.lesson_code == lesson_code)).order_by(attempts.c.attempt_no.desc())).mappings().all()
        if (not rows and participant_id != int(user["user_id"])) or (rows and not may_view_work(user, participant_id, rows[0]["unit_id"])):
            raise HTTPException(404, "Работа не найдена")
        return {"items": [dict(row) for row in rows]}


@router.get("/attempts/{attempt_id}", dependencies=[Depends(enabled)])
def attempt_detail(attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        row = conn.execute(select(attempts).where(attempts.c.id == attempt_id)).mappings().first()
        if row is None or not may_view_work(user, row["participant_id"], row["unit_id"]):
            raise HTTPException(404, "Попытка не найдена")
        shots = conn.execute(select(screenshots.c.id, screenshots.c.participant_id, screenshots.c.record_id, screenshot_slots.c.slot)
            .outerjoin(screenshot_slots, screenshot_slots.c.screenshot_id == screenshots.c.id)
            .where(screenshots.c.attempt_id == attempt_id)
            .order_by(screenshot_slots.c.slot.is_(None), screenshot_slots.c.slot, screenshots.c.created_at, screenshots.c.id)).mappings().all()
        record = conn.execute(select(records.c.application_ref, records.c.action, records.c.detail).where(records.c.id == row["record_id"])).mappings().one()
        criteria = conn.execute(select(criterion_results.c.criterion_no, criterion_results.c.met).where(
            criterion_results.c.attempt_id == attempt_id)).mappings().all()
        link = conn.execute(select(hire_applications).where(hire_applications.c.attempt_id == attempt_id)).mappings().first()
        return {**dict(row), "lesson": service.lesson_for_attempt(conn, row), "record": dict(record), "screenshots": [dict(shot) for shot in shots],
                "hire_application": hire_bridge.application(link["application_id"], attempt_id) if link else None,
                "criteria_results": {item["criterion_no"]: item["met"] for item in criteria}}


@router.get("/screenshots/{screenshot_id}", dependencies=[Depends(enabled)])
def screenshot(screenshot_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        row = conn.execute(select(screenshots, attempts.c.unit_id).join(attempts, screenshots.c.attempt_id == attempts.c.id).where(screenshots.c.id == screenshot_id)).mappings().first()
        if row is None or not may_view_work(user, row["participant_id"], row["unit_id"]):
            raise HTTPException(404, "Снимок не найден")
        data = storage.read(row["storage_key"], row["checksum"])
        return Response(content=data, media_type=row["mime"], headers={"Cache-Control": "private, no-store"})


@router.delete("/screenshots/{screenshot_id}", dependencies=[Depends(enabled)])
def remove_draft_screenshot(screenshot_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        row = conn.execute(select(screenshots, attempts.c.status, attempts.c.unit_id).join(
            attempts, screenshots.c.attempt_id == attempts.c.id).where(screenshots.c.id == screenshot_id)).mappings().first()
        if row is None or row["participant_id"] != int(user["user_id"]) or row["unit_id"] != service.unit(user):
            raise HTTPException(404, "Снимок не найден")
        if row["status"] != "draft":
            raise HTTPException(409, "Снимок отправленной работы нельзя заменить")
        conn.execute(delete(screenshot_slots).where(screenshot_slots.c.screenshot_id == screenshot_id))
        conn.execute(delete(screenshots).where(screenshots.c.id == screenshot_id))
    storage.discard(row["storage_key"])
    return {"deleted": True}


@router.get("/reviews", dependencies=[Depends(enabled)])
def reviews(user: dict[str, Any] = Depends(get_current_user)):
    if not user.get("has_learning_review"):
        raise HTTPException(403, "Нет права проверки учебных работ")
    with engine.connect() as conn:
        rows = conn.execute(select(attempts).where(attempts.c.status == "manual_review").order_by(attempts.c.created_at)).mappings().all()
        return {"items": [dict(row) for row in rows]}


@router.post("/attempts/{attempt_id}/review", dependencies=[Depends(enabled)])
def review(attempt_id: str, body: ReviewIn, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return service.review_attempt(conn, user, attempt_id, body.score, body.required_met, body.note, body.criteria)


@router.patch("/attempts/{attempt_id}/review", dependencies=[Depends(enabled)])
def correct_review(attempt_id: str, body: ReviewIn, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return service.review_attempt(conn, user, attempt_id, body.score, body.required_met, body.note, body.criteria, allow_correction=True, reason=body.reason)


@router.get("/my-courses", dependencies=[Depends(enabled)])
def my_courses(user: dict[str, Any] = Depends(get_current_user)):
    service.unit(user)
    with engine.connect() as conn:
        return service.progress(conn, int(user["user_id"]), service.unit(user), user.get("role_code"))


@router.get("/summary", dependencies=[Depends(enabled)])
def summary(course_code: str = Query(default="all"), user: dict[str, Any] = Depends(get_current_user)):
    unit_id = service.unit(user)
    with engine.connect() as conn:
        result = service.progress(conn, int(user["user_id"]), unit_id, user.get("role_code"))
        items = expert_service.assigned_lessons(conn, int(user["user_id"]), unit_id, user.get("role_code"))
    if course_code == "all":
        totals = {"points": sum(item["points"] for item in result["courses"]),
                  "maximum": sum(item["maximum"] for item in result["courses"]),
                  "passed": sum(item["passed"] for item in result["courses"]),
                  "pending": sum(item["pending"] for item in result["courses"]),
                  "total": sum(item["total"] for item in result["courses"]),
                  "average": result["courses"][0]["average"] if len(result["courses"]) == 1 else None}
        return {"course": {"code": "all", "title": "Все назначения", **totals}, "lessons": result["lessons"]}
    selected = next((item for item in result["courses"] if item["code"] == course_code), None)
    if selected is None:
        raise HTTPException(404, "Курс не назначен")
    codes = {item["code"] for item in items if item["course_code"] == course_code}
    return {"course": selected, "lessons": {code: value for code, value in result["lessons"].items() if code in codes}}


@router.get("/unit-summary", dependencies=[Depends(enabled)])
def unit_summary(course_code: str = Query(default=COURSE["code"]), user: dict[str, Any] = Depends(get_current_user)):
    # Existing platform role and unit are authoritative; no client-provided unit filter.
    with engine.connect() as conn:
        leader = user.get("role_code") in LEADERSHIP_PLATFORM_ROLE_CODES
        if not leader and conn.dialect.name == "postgresql":
            leader = bool(conn.execute(text("""
                SELECT EXISTS(SELECT 1 FROM public.users u
                JOIN public.employees e ON e.employee_id=u.employee_id
                JOIN public.position_job_catalog j ON j.position_id=e.position_id
                WHERE u.user_id=:uid AND u.is_active AND e.is_active
                  AND e.org_unit_id=:unit
                  AND j.job_code IN ('CLINICAL_DEPARTMENT_HEAD','DEPARTMENT_HEAD_UNSPECIFIED'))
            """), {"uid": int(user["user_id"]), "unit": service.unit(user)}).scalar_one())
        if not leader:
            raise HTTPException(403, "Нет права на сводку обучения")
        course = next((item for item in COURSES if item["code"] == course_code), None)
        if course is None:
            raise HTTPException(404, "Курс не найден")
        if course["code"] != COURSE["code"]:
            return {"unit_id": service.unit(user), "course": course, "participants": []}
        participant_ids = conn.execute(select(attempts.c.participant_id).where(attempts.c.unit_id == service.unit(user)).distinct()).scalars().all()
        return {"unit_id": service.unit(user), "course": COURSE, "participants": [{"participant_id": uid, **service.progress(conn, uid, service.unit(user))} for uid in participant_ids]}


@router.get("/expert/catalog", dependencies=[Depends(enabled)])
def expert_catalog(user: dict[str, Any] = Depends(require_expert)):
    with engine.connect() as conn:
        return {"courses": expert_service.all_courses(conn, include_drafts=True),
                "lessons": expert_service.all_lessons(conn, include_drafts=True)}


@router.post("/expert/courses", dependencies=[Depends(enabled)])
def create_course(body: CourseIn, user: dict[str, Any] = Depends(require_expert)):
    with engine.begin() as conn:
        return expert_service.save_course(conn, user, body.model_dump())


@router.put("/expert/courses/{course_code}", dependencies=[Depends(enabled)])
def edit_course(course_code: str, body: CourseIn, user: dict[str, Any] = Depends(require_expert)):
    with engine.begin() as conn:
        expert_service.course(conn, course_code, include_draft=True)
        return expert_service.save_course(conn, user, body.model_dump(), code=course_code)


@router.post("/expert/courses/{course_code}/publish", dependencies=[Depends(enabled)])
def publish_course(course_code: str, user: dict[str, Any] = Depends(require_expert)):
    with engine.begin() as conn:
        return expert_service.publish_course(conn, course_code)


@router.post("/expert/lessons", dependencies=[Depends(enabled)])
def create_lesson(body: LessonIn, user: dict[str, Any] = Depends(require_expert)):
    with engine.begin() as conn:
        return expert_service.save_lesson(conn, user, body.model_dump())


@router.put("/expert/lessons/{lesson_code}", dependencies=[Depends(enabled)])
def edit_lesson(lesson_code: str, body: LessonIn, user: dict[str, Any] = Depends(require_expert)):
    with engine.begin() as conn:
        expert_service.lesson(conn, lesson_code, include_draft=True)
        return expert_service.save_lesson(conn, user, body.model_dump(), code=lesson_code)


@router.get("/expert/lessons/{lesson_code}/preview", dependencies=[Depends(enabled)])
def preview_lesson(lesson_code: str, user: dict[str, Any] = Depends(require_expert)):
    with engine.connect() as conn:
        return expert_service.lesson(conn, lesson_code, include_draft=True)


@router.post("/expert/lessons/{lesson_code}/publish", dependencies=[Depends(enabled)])
def publish_lesson(lesson_code: str, user: dict[str, Any] = Depends(require_expert)):
    with engine.begin() as conn:
        return expert_service.publish_lesson(conn, lesson_code)


@router.post("/expert/assignments/preview", dependencies=[Depends(enabled)])
def preview_assignment(body: AssignmentIn, user: dict[str, Any] = Depends(require_expert)):
    with engine.connect() as conn:
        if body.target_code == "training:skill_2":
            return expert_service.training_assignment_preview(conn, body.model_dump())
        return expert_service.assignment_preview(conn, body.model_dump(), preview_users)


@router.post("/expert/assignments", dependencies=[Depends(enabled)])
def create_assignment(body: AssignmentIn, user: dict[str, Any] = Depends(require_expert)):
    with engine.begin() as conn:
        if body.target_code == "training:skill_2":
            return expert_service.assign_training(conn, user, body.model_dump())
        return expert_service.assign(conn, user, body.model_dump(), preview_users)


@router.get("/expert/completion", dependencies=[Depends(enabled)])
def expert_completion(employee_id: int | None = None, unit_id: int | None = None,
                      course_code: str | None = None, lesson_code: str | None = None,
                      status: str | None = None, user: dict[str, Any] = Depends(require_expert)):
    with engine.connect() as conn:
        participant_id = employee_id
        if employee_id is not None and conn.dialect.name == "postgresql":
            participant_id = conn.execute(text("""
                SELECT COALESCE(link.training_user_id, u.user_id)
                FROM public.users u
                LEFT JOIN public.training_identity_links link
                  ON link.source_user_id=u.user_id AND link.source_kind='local'
                WHERE u.employee_id=:employee_id
            """), {"employee_id": employee_id}).scalar_one_or_none()
            if participant_id is None:
                return {"items": []}
        filters = {"participant_id": participant_id, "unit_id": unit_id, "course_code": course_code,
                   "lesson_code": lesson_code, "status": status}
        return {"items": expert_service.completion(conn, filters)}


@router.get("/expert/attempts/{attempt_id}", dependencies=[Depends(enabled)])
def expert_attempt(attempt_id: str, user: dict[str, Any] = Depends(require_expert)):
    with engine.connect() as conn:
        result = expert_service.attempt_history(conn, attempt_id)
        row = result["attempt"]
        shots = conn.execute(select(screenshots.c.id, screenshot_slots.c.slot)
            .outerjoin(screenshot_slots, screenshots.c.id == screenshot_slots.c.screenshot_id)
            .where(screenshots.c.attempt_id == attempt_id).order_by(screenshot_slots.c.slot)).mappings().all()
        marks = conn.execute(select(criterion_results.c.criterion_no, criterion_results.c.met)
            .where(criterion_results.c.attempt_id == attempt_id)).mappings().all()
        link = conn.execute(select(hire_applications).where(hire_applications.c.attempt_id == attempt_id)).mappings().first()
        return {**result, "lesson": service.lesson_for_attempt(conn, row),
                "hire_application": hire_bridge.application(link["application_id"], attempt_id) if link else None,
                "screenshots": [dict(item) for item in shots],
                "criteria_results": {item["criterion_no"]: item["met"] for item in marks}}


@router.post("/internal/attempts/{attempt_id}/automatic-result", dependencies=[Depends(enabled)])
def automatic_result(attempt_id: str, body: AutomaticResultIn,
                     token: str = Header(default="", alias="X-Learning-Auto-Token")):
    expected = os.getenv("LEARNING_AUTO_REVIEW_TOKEN", "")
    if not expected:
        raise HTTPException(503, "Автоматическая проверка не подключена")
    if not secrets.compare_digest(token, expected):
        raise HTTPException(403, "Нет доступа к автоматической проверке")
    with engine.begin() as conn:
        return service.automatic_result(conn, attempt_id, body.criteria, body.note)


@router.post("/internal/attempts/{attempt_id}/automatic-failure", dependencies=[Depends(enabled)])
def automatic_failure(attempt_id: str, body: AutomaticFailureIn,
                      token: str = Header(default="", alias="X-Learning-Auto-Token")):
    expected = os.getenv("LEARNING_AUTO_REVIEW_TOKEN", "")
    if not expected:
        raise HTTPException(503, "Автоматическая проверка не подключена")
    if not secrets.compare_digest(token, expected):
        raise HTTPException(403, "Нет доступа к автоматической проверке")
    with engine.begin() as conn:
        return service.automatic_failure(conn, attempt_id, body.note)


# Rehearsal endpoints are guarded twice: by enabled()'s isolated-DB check and
# by hire_path_rehearsal.require_rehearsal's exact role check.  IDs are always
# resolved through the saved first-lesson link, never trusted from the client.
@router.get("/hire-path/roots", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_roots(user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        return hire_path_rehearsal.roots(conn, user)


@router.get("/hire-path/inbox", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_inbox(user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        return hire_path_rehearsal.inbox(conn, user)


@router.get("/hire-path/approvals", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_approvals(user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        return hire_path_rehearsal.pending_approvals(conn, user)


@router.get("/hire-path/signatures", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_signatures(user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        return hire_path_rehearsal.pending_signatures(conn, user)


@router.post("/hire-path/{root_attempt_id}/steps/{lesson_code}", dependencies=[Depends(enabled)])
@rehearsal_errors
def start_hire_path_step(root_attempt_id: str, lesson_code: str,
                         user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return hire_path_rehearsal.start_step(conn, user, root_attempt_id, lesson_code)


@router.get("/hire-path/{root_attempt_id}", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_state(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        return hire_path_rehearsal.state(conn, user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/intake-link", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_intake_link(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return hire_path_rehearsal.issue_link(conn, user, root_attempt_id)


@router.get("/hire-path/{root_attempt_id}/review", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_review(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return hire_path_rehearsal.review_state(conn, user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/review/{section}", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_review_section(root_attempt_id: str, section: str, body: HireReviewDecisionIn,
                             user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return hire_path_rehearsal.review_section(conn, user, root_attempt_id, section, body.decision)


@router.post("/hire-path/{root_attempt_id}/transfer", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_transfer(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return hire_path_rehearsal.transfer_card(conn, user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/check-card", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_check_card(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return hire_path_rehearsal.check_card(conn, user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/order-draft", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_order_draft(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        result = hire_path_rehearsal.draft_order(conn, user, root_attempt_id)
    hire_path_rehearsal.configure_signatory(user, root_attempt_id)
    return result


@router.get("/hire-path/{root_attempt_id}/order", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_order(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        return hire_path_rehearsal.order_detail(conn, user, root_attempt_id)


@router.get("/hire-path/{root_attempt_id}/role-order", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_role_order(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        return hire_path_rehearsal.role_order(conn, user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/generate", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_generate(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    return hire_path_rehearsal.generate_text(user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/editorial-body", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_editorial_body(root_attempt_id: str, body: HireEditorialBodyIn,
                             user: dict[str, Any] = Depends(get_current_user)):
    return hire_path_rehearsal.save_editorial_body(user, root_attempt_id, body.locale, body.text)


@router.post("/hire-path/{root_attempt_id}/approve", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_approve(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return hire_path_rehearsal.approve_as_head(conn, user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/number", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_number(root_attempt_id: str, body: HireNumberIn,
                     user: dict[str, Any] = Depends(get_current_user)):
    return hire_path_rehearsal.save_number(user, root_attempt_id, body.number)


@router.post("/hire-path/{root_attempt_id}/ready", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_ready(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    return hire_path_rehearsal.ready(user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/sign", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_sign(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return hire_path_rehearsal.sign(conn, user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/register", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_register(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return hire_path_rehearsal.register(conn, user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/apply", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_apply(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    return hire_path_rehearsal.apply_registered_order(user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/notify", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_notify(root_attempt_id: str, user: dict[str, Any] = Depends(get_current_user)):
    with engine.begin() as conn:
        return hire_path_rehearsal.notified_recipient(conn, user, root_attempt_id)


@router.post("/hire-path/{root_attempt_id}/acknowledge", dependencies=[Depends(enabled)])
@rehearsal_errors
def hire_path_acknowledge(root_attempt_id: str, body: HireAcknowledgementIn,
                          user: dict[str, Any] = Depends(get_current_user)):
    with engine.connect() as conn:
        checked = hire_path_rehearsal.acknowledge(conn, user, root_attempt_id, body.method, body.evidence)
    if "idempotent_replay" in checked:
        return checked
    from app.control_list_projection.service import organization_timezone
    from app.services.personnel_order_acknowledgement_service import record as record_acknowledgement
    record_acknowledgement(checked["order_id"], checked["employee_id"],
                           datetime.now(organization_timezone()[1]).date(), int(user["user_id"]))
    with engine.begin() as conn:
        return hire_path_rehearsal.save_acknowledgement(conn, root_attempt_id, checked)
