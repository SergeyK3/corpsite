"""Local training catalog and the sanitary-worker access lesson.

Other lessons remain unavailable for attempts until their business fixtures and
partner actions are implemented.  A preparation failure cannot become a grade.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import os

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.auth import _enrich_user_context, _get_user_by_id, get_current_user
from app.db.engine import engine
from app import training_hire_approval as hire_training

router = APIRouter(prefix="/training", tags=["training"])
MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
# The first catalog occurrence fixes a lesson's position across course versions.
# A later version may publish only one lesson and must retain its original number.
LESSON_NUMBER_SQL = """(
    SELECT numbered.lesson_number FROM (
        SELECT origin.course_code, origin.lesson_code,
               ROW_NUMBER() OVER (PARTITION BY origin.course_code ORDER BY origin.first_id) AS lesson_number
        FROM (
            SELECT versions.course_code, lessons.lesson_code,
                   MIN(lessons.lesson_version_id) AS first_id
            FROM public.training_lesson_versions lessons
            JOIN public.training_course_versions versions USING (course_version_id)
            GROUP BY versions.course_code, lessons.lesson_code
        ) origin
    ) numbered
    WHERE numbered.course_code=c.course_code AND numbered.lesson_code=l.lesson_code
)"""


def _guard(conn: Connection, *, write: bool = False) -> None:
    url = engine.url
    name = str(conn.execute(text("SELECT current_database()")).scalar_one()).lower()
    local_test = name == "corpsite_test" and os.getenv("APP_ENV", "dev").lower() not in {"prod", "production"}
    isolated_server = name == "corpsite_learn" and os.getenv("TRAINING_SERVER_ENABLED") == "1"
    rehearsal = name.startswith("corpsite_learn_rehearsal_") and os.getenv("TRAINING_REHEARSAL") == "1" and os.getenv("APP_ENV", "dev").lower() not in {"prod", "production"}
    if url.host not in {"127.0.0.1", "localhost", "::1"} or not (local_test or isolated_server or rehearsal):
        raise HTTPException(503, "Обучение доступно только в отдельной учебной базе.")
    if write and (os.getenv("TRAINING_MODE") != "1" or os.getenv("TRAINING_DISABLE_EXTERNAL") != "1"):
        raise HTTPException(503, "Для учебных изменений нужны TRAINING_MODE=1 и TRAINING_DISABLE_EXTERNAL=1.")


def _actor(user: dict) -> int:
    return int(user["user_id"])


def _linked_training_user(conn: Connection, user_id: int) -> bool:
    return bool(conn.execute(text("""
        SELECT EXISTS(SELECT 1 FROM public.training_identity_links
                      WHERE training_user_id=:id AND source_kind='local')
    """), {"id": user_id}).scalar_one())


def _can_view_participant(conn: Connection, user: dict, participant: int) -> bool:
    if participant == _actor(user) or bool(user.get("has_learning_expert") or user.get("has_learning_review")):
        return True
    if not user.get("is_hire_approver"):
        return False
    return bool(conn.execute(text("""
        SELECT EXISTS (
          SELECT 1 FROM public.users target
          JOIN public.employees e ON e.employee_id=target.employee_id
          JOIN public.org_unit_managers m ON m.unit_id=e.org_unit_id
          WHERE target.user_id=:target AND m.user_id=:viewer
            AND upper(btrim(m.manager_type))='HEAD' AND m.is_active=TRUE
            AND (m.date_from IS NULL OR m.date_from<=CURRENT_DATE)
            AND (m.date_to IS NULL OR m.date_to>=CURRENT_DATE)
        )
    """), {"target": participant, "viewer": _actor(user)}).scalar_one())


def _assignment(conn: Connection, assignment_id: int) -> dict:
    row = conn.execute(text("""
        SELECT a.assignment_id, a.participant_user_id, a.required, a.instruction_url,
               l.lesson_version_id, l.lesson_code, l.title, l.position_label,
               l.duration_minutes, l.source_data, l.expected_result, l.steps, l.rules,
               c.course_version_id, c.course_code, c.version AS course_version, c.title AS course_title
        FROM public.training_assignments a
        JOIN public.training_lesson_versions l USING (lesson_version_id)
        JOIN public.training_course_versions c USING (course_version_id)
        WHERE a.assignment_id=:id
    """), {"id": assignment_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Назначение не найдено.")
    return dict(row)


def _attempt(conn: Connection, attempt_id: int, user: dict) -> dict:
    row = conn.execute(text(f"""
        SELECT t.*, a.participant_user_id, a.lesson_version_id, a.required,
               l.lesson_code, l.title AS lesson_title, l.position_label,
               l.duration_minutes, l.source_data, l.expected_result, l.steps, l.rules,
               c.course_version_id, c.version AS course_version, c.title AS course_title,
               {LESSON_NUMBER_SQL} AS lesson_number
        FROM public.training_attempts t
        JOIN public.training_assignments a USING (assignment_id)
        JOIN public.training_lesson_versions l USING (lesson_version_id)
        JOIN public.training_course_versions c USING (course_version_id)
        WHERE t.attempt_id=:id
    """), {"id": attempt_id}).mappings().first()
    if not row or not _can_view_participant(conn, user, int(row["participant_user_id"])):
        raise HTTPException(404, "Попытка не найдена.")
    return dict(row)


def _sanitary_fixture(conn: Connection, user_id: int) -> dict:
    identity = _get_user_by_id(user_id)
    if not identity or identity.get("role_code") != "EMPLOYEE" or str(identity.get("position_name") or "").casefold() != "санитарка":
        raise HTTPException(422, "Нет действующей должности «Санитарка» с обычной ролью сотрудника.")
    identity = _enrich_user_context(identity)
    if identity.get("is_hire_approver") or identity.get("has_personnel_admin"):
        raise HTTPException(422, "Учебная санитарка имеет лишние полномочия.")
    row = conn.execute(text("""
        SELECT e.employee_id, e.person_id, p.full_name AS card_full_name,
               pa.assignment_id, pa.rate, pa.start_date
        FROM public.users u
        LEFT JOIN public.training_identity_links training_link
          ON training_link.training_user_id=u.user_id AND training_link.source_kind='local'
        LEFT JOIN public.users source_user ON source_user.user_id=training_link.source_user_id
        JOIN public.employees e ON e.employee_id=COALESCE(u.employee_id, source_user.employee_id)
        JOIN public.persons p ON p.person_id=e.person_id
        JOIN public.person_assignments pa ON pa.person_id=e.person_id
        WHERE u.user_id=:uid AND pa.is_primary=TRUE AND pa.active_flag=TRUE
          AND pa.lifecycle_status='active' AND pa.start_date<=CURRENT_DATE
          AND (pa.end_date IS NULL OR pa.end_date>=CURRENT_DATE)
    """), {"uid": user_id}).mappings().all()
    if len(row) != 1:
        raise HTTPException(422, "Действующее основное назначение не определено однозначно.")
    item = dict(row[0])
    if str(item["card_full_name"]).strip() != str(identity["full_name"]).strip():
        raise HTTPException(422, "ФИО аккаунта и собственной карточки не совпадают.")
    item.update({"full_name": identity["full_name"], "position": identity["position_name"],
                 "rate": str(item["rate"]), "start_date": item["start_date"].isoformat()})
    return item


@router.get("/catalog")
def catalog(user: dict = Depends(get_current_user)) -> dict:
    with engine.connect() as conn:
        _guard(conn)
        rows = conn.execute(text(f"""
            SELECT c.course_version_id, c.title AS course_title, c.version,
                   l.lesson_version_id, l.lesson_code, l.title, l.position_label,
                   l.duration_minutes, a.assignment_id, a.required, a.instruction_url,
                   {LESSON_NUMBER_SQL} AS lesson_number
            FROM public.training_course_versions c
            JOIN public.training_lesson_versions l USING (course_version_id)
            LEFT JOIN public.training_assignments a
              ON a.lesson_version_id=l.lesson_version_id AND a.participant_user_id=:uid
            ORDER BY c.course_version_id, l.lesson_version_id
        """), {"uid": _actor(user)}).mappings().all()
    return {"items": [dict(row) for row in rows]}


def _current_assignment_rows(conn: Connection, user: dict) -> list[dict]:
    rows = conn.execute(text(f"""
             SELECT a.assignment_id, a.required, a.instruction_url,
                    l.title, l.lesson_code, l.position_label, l.duration_minutes,
                    c.course_code, c.title AS course_title, c.version AS course_version,
                     {LESSON_NUMBER_SQL} AS lesson_number,
                    latest.attempt_id AS latest_attempt_id,
                    latest.attempt_number AS latest_attempt_number,
                    latest.status AS latest_status, latest.outcome AS latest_outcome,
                    latest.score AS latest_score, latest.last_checked_at AS latest_checked_at,
                    latest.fixture->>'application_number' AS latest_application_number
            FROM public.training_assignments a
            JOIN public.training_lesson_versions l USING (lesson_version_id)
            JOIN public.training_course_versions c USING (course_version_id)
             LEFT JOIN LATERAL (
                 SELECT t.attempt_id, t.attempt_number, t.status, t.outcome,
                        t.score, t.last_checked_at, t.fixture
                 FROM public.training_attempts t WHERE t.assignment_id=a.assignment_id
                 ORDER BY t.attempt_number DESC LIMIT 1
             ) latest ON TRUE
             WHERE a.participant_user_id=:uid
               AND NOT EXISTS (SELECT 1 FROM public.training_assignments newer
                   JOIN public.training_lesson_versions nl USING (lesson_version_id)
                   JOIN public.training_course_versions nc USING (course_version_id)
                   WHERE newer.participant_user_id=a.participant_user_id
                     AND nl.lesson_code=l.lesson_code AND nc.course_code=c.course_code
                     AND nc.version>c.version)
             ORDER BY a.assignment_id
    """), {"uid": _actor(user)}).mappings().all()
    return [dict(row) for row in rows]


@router.get("/assignments")
def assignments(user: dict = Depends(get_current_user)) -> dict:
    with engine.connect() as conn:
        _guard(conn)
        return {"items": _current_assignment_rows(conn, user)}


@router.post("/assignments/{assignment_id}/preview")
def preview(assignment_id: int, user: dict = Depends(get_current_user)) -> dict:
    with engine.connect() as conn:
        _guard(conn)
        assigned = _assignment(conn, assignment_id)
        if assigned["participant_user_id"] != _actor(user):
            raise HTTPException(404, "Назначение не найдено.")
        if assigned["lesson_code"] == "skill_2" and assigned["course_version"] in {2, 3}:
            identity = _enrich_user_context(_get_user_by_id(_actor(user)))
            if not _linked_training_user(conn, _actor(user)) or identity.get("position_name") != "Заведующий отделением":
                return {"ready": False, "reason": "Нужен связанный учебный аккаунт заведующего отделением с действующим кадровым назначением."}
            try:
                hire_training._system_hr(conn)
            except RuntimeError as exc:
                return {"ready": False, "reason": str(exc)}
            return {"ready": True, "fixture": {"full_name": identity["full_name"],
                    "position": identity["position_name"]}, "lesson": assigned}
        if assigned["lesson_code"] != "skill_8":
            return {"ready": False, "reason": "Для этого навыка ещё нет безопасной подготовки учебных заявлений и системного партнёра."}
        try:
            fixture = _sanitary_fixture(conn, _actor(user))
        except HTTPException as exc:
            return {"ready": False, "reason": exc.detail}
        return {"ready": True, "fixture": fixture, "lesson": assigned}


@router.post("/assignments/{assignment_id}/attempts")
def start_attempt(assignment_id: int, idempotency_key: str | None = Header(default=None),
                  user: dict = Depends(get_current_user)) -> dict:
    if idempotency_key is not None and (not 8 <= len(idempotency_key) <= 100):
        raise HTTPException(422, "Неверный ключ повторного запроса.")
    with engine.begin() as conn:
        _guard(conn, write=True)
        assigned = _assignment(conn, assignment_id)
        if assigned["participant_user_id"] != _actor(user):
            raise HTTPException(404, "Назначение не найдено.")
        is_hire = assigned["lesson_code"] == "skill_2" and assigned["course_version"] in {2, 3}
        if assigned["lesson_code"] != "skill_8" and not is_hire:
            raise HTTPException(422, "Подготовка исходных данных этого навыка ещё недоступна.")
        conn.execute(text("SELECT assignment_id FROM public.training_assignments WHERE assignment_id=:id FOR UPDATE"), {"id": assignment_id})
        if idempotency_key:
            existing = conn.execute(text("""
                SELECT attempt_id, attempt_number FROM public.training_attempts
                WHERE assignment_id=:id AND idempotency_key=:key
            """), {"id": assignment_id, "key": idempotency_key}).mappings().first()
            if existing:
                return dict(existing)
        if is_hire:
            identity = _enrich_user_context(_get_user_by_id(_actor(user)))
            if not _linked_training_user(conn, _actor(user)) or identity.get("position_name") != "Заведующий отделением":
                raise HTTPException(422, "Нужен связанный учебный аккаунт заведующего отделением.")
            fixture = None
        else:
            fixture = _sanitary_fixture(conn, _actor(user))
        number = int(conn.execute(text("""
            SELECT COALESCE(MAX(attempt_number),0)+1 FROM public.training_attempts WHERE assignment_id=:id
        """), {"id": assignment_id}).scalar_one())
        row = conn.execute(text("""
            INSERT INTO public.training_attempts(assignment_id, attempt_number, idempotency_key, fixture)
            VALUES (:assignment, :number, :key, CAST(:fixture AS jsonb))
            RETURNING attempt_id, attempt_number
        """), {"assignment": assignment_id, "number": number, "key": idempotency_key,
               "fixture": json.dumps(fixture, ensure_ascii=False)}).mappings().one()
        if is_hire:
            try:
                fixture = hire_training.prepare(conn, attempt_id=int(row["attempt_id"]),
                                                participant_user_id=_actor(user),
                                                participant_role_id=int(user["role_id"]))
            except Exception as exc:
                raise HTTPException(503, f"Техническая ошибка подготовки учебного задания: {exc}") from exc
            conn.execute(text("""
                UPDATE public.training_attempts SET fixture=CAST(:fixture AS jsonb)
                WHERE attempt_id=:id
            """), {"fixture": json.dumps(fixture, ensure_ascii=False), "id": row["attempt_id"]})
        conn.execute(text("""
            INSERT INTO public.training_attempt_events(attempt_id, actor_kind, actor_user_id, event_type)
            VALUES (:id, 'participant', :user, 'attempt_started')
        """), {"id": row["attempt_id"], "user": _actor(user)})
        return dict(row)


@router.get("/attempts/{attempt_id}")
def attempt_detail(attempt_id: int, user: dict = Depends(get_current_user)) -> dict:
    with engine.connect() as conn:
        _guard(conn)
        attempt = _attempt(conn, attempt_id, user)
        evidence = conn.execute(text("""
            SELECT evidence_id, step_key, mime_type, width, height, uploaded_at
            FROM public.training_evidence WHERE attempt_id=:id AND superseded_at IS NULL
            ORDER BY evidence_id
        """), {"id": attempt_id}).mappings().all()
        events = conn.execute(text("""
            SELECT event_id, step_key, actor_kind, event_type, detail, created_at
            FROM public.training_attempt_events WHERE attempt_id=:id ORDER BY event_id
        """), {"id": attempt_id}).mappings().all()
        reviews = conn.execute(text("""
            SELECT r.review_id, r.outcome, r.score, r.explanation, r.created_at,
                   reviewer.full_name AS reviewer_name
            FROM public.training_reviews r
            LEFT JOIN LATERAL (
                SELECT u.full_name FROM public.training_attempt_events e
                JOIN public.users u ON u.user_id=e.actor_user_id
                WHERE e.attempt_id=r.attempt_id AND e.created_at=r.created_at
                  AND e.event_type IN ('review_completed','review_revised')
                ORDER BY e.event_id DESC LIMIT 1
            ) reviewer ON TRUE
            WHERE r.attempt_id=:id ORDER BY r.review_id
        """), {"id": attempt_id}).mappings().all()
    return {"attempt": attempt, "evidence": [dict(x) for x in evidence],
            "events": [dict(x) for x in events], "reviews": [dict(x) for x in reviews]}


@router.get("/attempts/{attempt_id}/record")
def hire_record(attempt_id: int, user: dict = Depends(get_current_user)) -> dict:
    with engine.connect() as conn:
        _guard(conn)
        attempt = _attempt(conn, attempt_id, user)
        if attempt["participant_user_id"] != _actor(user) or attempt["lesson_code"] != "skill_2" or attempt["course_version"] not in {2, 3}:
            raise HTTPException(404, "Учебная запись не найдена.")
        return hire_training.record(conn, attempt_id)


@router.post("/attempts/{attempt_id}/record/consent")
def hire_consent(attempt_id: int, user: dict = Depends(get_current_user)) -> dict:
    with engine.begin() as conn:
        _guard(conn, write=True)
        attempt = _attempt(conn, attempt_id, user)
        if attempt["participant_user_id"] != _actor(user) or attempt["lesson_code"] != "skill_2" or attempt["course_version"] not in {2, 3}:
            raise HTTPException(404, "Учебная запись не найдена.")
        if attempt["status"] == "completed":
            raise HTTPException(409, "Оценённая попытка закрыта; начните пересдачу.")
        conn.execute(text("SELECT attempt_id FROM public.training_attempts WHERE attempt_id=:id FOR UPDATE"), {"id": attempt_id})
        try:
            hire_training.consent(conn, attempt_id=attempt_id,
                                  participant_user_id=_actor(user),
                                  participant_role_id=int(user["role_id"]))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    try:
        with engine.begin() as conn:
            _guard(conn, write=True)
            return hire_training.verify_partner(conn, attempt_id)
    except Exception as exc:
        with engine.begin() as conn:
            _guard(conn, write=True)
            conn.execute(text("""
                UPDATE public.training_attempts SET status='technical_pause' WHERE attempt_id=:id
                  AND status<>'completed'
            """), {"id": attempt_id})
            hire_training._event(conn, attempt_id, "system", "partner_technical_error",
                                 {"reason": str(exc)})
            result = hire_training.record(conn, attempt_id)
        return {**result, "technical_message": f"Проверка визы в приказе временно недоступна: {exc}"}


def _image_info(content: bytes) -> tuple[str, int, int, str]:
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            if getattr(image, "n_frames", 1) != 1 or image.format not in IMAGE_TYPES:
                raise ValueError("Поддерживаются только неподвижные PNG, JPEG и WebP.")
            width, height = image.size
            if width < 100 or height < 100 or width > 10000 or height > 10000:
                raise ValueError("Размер изображения должен быть от 100 до 10000 пикселей по каждой стороне.")
            gray = image.convert("L").resize((9, 8))
            pixels = list(gray.getdata())
            bits = 0
            for y in range(8):
                for x in range(8):
                    bits = (bits << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
            return IMAGE_TYPES[image.format], width, height, f"{bits:016x}"
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Содержимое файла не является допустимым изображением.") from exc


@router.post("/attempts/{attempt_id}/steps/{step_key}/evidence")
async def upload_evidence(attempt_id: int, step_key: str, file: UploadFile = File(...),
                          user: dict = Depends(get_current_user)) -> dict:
    content = await file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES or not content:
        raise HTTPException(413, "Снимок должен быть непустым и не больше 5 МБ.")
    try:
        mime, width, height, visual_hash = _image_info(content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if file.content_type != mime:
        raise HTTPException(422, "Тип файла не совпадает с содержимым.")
    with engine.begin() as conn:
        _guard(conn, write=True)
        attempt = _attempt(conn, attempt_id, user)
        if attempt["participant_user_id"] != _actor(user):
            raise HTTPException(403, "Чужая попытка.")
        if attempt["lesson_code"] == "skill_2" and attempt["course_version"] in {2, 3} and attempt["status"] == "completed":
            raise HTTPException(409, "Оценённая попытка закрыта; начните пересдачу.")
        if step_key not in {x["key"] for x in attempt["steps"] if x["actor"] == "participant"}:
            raise HTTPException(404, "Шаг не найден.")
        conn.execute(text("""
            UPDATE public.training_evidence SET superseded_at=now()
            WHERE attempt_id=:id AND step_key=:step AND superseded_at IS NULL
        """), {"id": attempt_id, "step": step_key})
        evidence_id = conn.execute(text("""
            INSERT INTO public.training_evidence
              (attempt_id, step_key, uploaded_by_user_id, mime_type, width, height,
               sha256, perceptual_hash, image_bytes)
            VALUES (:id, :step, :user, :mime, :width, :height, :sha, :visual, :bytes)
            RETURNING evidence_id
        """), {"id": attempt_id, "step": step_key, "user": _actor(user),
               "mime": mime, "width": width, "height": height,
               "sha": sha256(content).hexdigest(), "visual": visual_hash,
               "bytes": content}).scalar_one()
        conn.execute(text("""
            INSERT INTO public.training_attempt_events
              (attempt_id, step_key, actor_kind, actor_user_id, event_type, detail)
            VALUES (:id, :step, 'participant', :user, 'evidence_uploaded',
                    jsonb_build_object('evidence_id', :evidence))
        """), {"id": attempt_id, "step": step_key, "user": _actor(user), "evidence": evidence_id})
        conn.execute(text("""
            UPDATE public.training_attempts
            SET status='in_progress', outcome=NULL, score=NULL WHERE attempt_id=:id
        """), {"id": attempt_id})
    return {"evidence_id": evidence_id, "step_key": step_key, "mime_type": mime,
            "width": width, "height": height}


@router.get("/evidence/{evidence_id}")
def read_evidence(evidence_id: int, user: dict = Depends(get_current_user)) -> Response:
    with engine.connect() as conn:
        _guard(conn)
        row = conn.execute(text("""
            SELECT attempt_id, mime_type, image_bytes FROM public.training_evidence
            WHERE evidence_id=:id AND superseded_at IS NULL
        """), {"id": evidence_id}).mappings().first()
        if not row:
            raise HTTPException(404, "Снимок не найден.")
        _attempt(conn, int(row["attempt_id"]), user)
        return Response(content=bytes(row["image_bytes"]), media_type=row["mime_type"],
                        headers={"Cache-Control": "private, no-store"})


@router.delete("/evidence/{evidence_id}")
def delete_evidence(evidence_id: int, user: dict = Depends(get_current_user)) -> dict:
    with engine.begin() as conn:
        _guard(conn, write=True)
        row = conn.execute(text("""
            SELECT attempt_id, step_key FROM public.training_evidence
            WHERE evidence_id=:id AND superseded_at IS NULL FOR UPDATE
        """), {"id": evidence_id}).mappings().first()
        if not row:
            raise HTTPException(404, "Снимок не найден.")
        attempt = _attempt(conn, int(row["attempt_id"]), user)
        if attempt["participant_user_id"] != _actor(user):
            raise HTTPException(403, "Чужая попытка.")
        if attempt["lesson_code"] == "skill_2" and attempt["course_version"] in {2, 3} and attempt["status"] == "completed":
            raise HTTPException(409, "Оценённая попытка закрыта; начните пересдачу.")
        conn.execute(text("UPDATE public.training_evidence SET superseded_at=now() WHERE evidence_id=:id"), {"id": evidence_id})
        conn.execute(text("""
            INSERT INTO public.training_attempt_events
              (attempt_id, step_key, actor_kind, actor_user_id, event_type)
            VALUES (:attempt, :step, 'participant', :user, 'evidence_removed')
        """), {"attempt": row["attempt_id"], "step": row["step_key"], "user": _actor(user)})
        conn.execute(text("""
            UPDATE public.training_attempts
            SET status='in_progress', outcome=NULL, score=NULL WHERE attempt_id=:id
        """), {"id": row["attempt_id"]})
    return {"removed": True}


@router.post("/attempts/{attempt_id}/check")
def check_attempt(attempt_id: int, user: dict = Depends(get_current_user)) -> dict:
    with engine.begin() as conn:
        _guard(conn, write=True)
        attempt = _attempt(conn, attempt_id, user)
        if attempt["participant_user_id"] != _actor(user):
            raise HTTPException(403, "Чужая попытка.")
        if attempt["lesson_code"] == "skill_2" and attempt["course_version"] in {2, 3}:
            return _check_hire_attempt(conn, attempt, user)
        if attempt["lesson_code"] != "skill_8":
            raise HTTPException(422, "Правила проверки занятия ещё не подготовлены.")
        rows = conn.execute(text("""
            SELECT evidence_id, step_key, sha256, perceptual_hash
            FROM public.training_evidence WHERE attempt_id=:id AND superseded_at IS NULL
        """), {"id": attempt_id}).mappings().all()
        required = set(attempt["rules"]["required_user_steps"])
        missing = sorted(required - {row["step_key"] for row in rows})
        if missing:
            return {"status": "in_progress", "missing_steps": missing,
                    "message": "Добавьте подтверждение для каждого шага."}
        try:
            fixture = _sanitary_fixture(conn, _actor(user))
            if fixture["employee_id"] != attempt["fixture"]["employee_id"]:
                raise HTTPException(422, "Карточка участника изменилась с начала попытки.")
            from app.services.self_personal_card_access_service import SelfPersonalCardAccessService
            if SelfPersonalCardAccessService().resolve_for_user(user).status != "READY":
                raise HTTPException(422, "Собственная карточка недоступна.")
        except HTTPException as exc:
            conn.execute(text("UPDATE public.training_attempts SET status='technical_pause' WHERE attempt_id=:id"), {"id": attempt_id})
            return {"status": "technical_pause", "message": exc.detail}
        exact_duplicate = len({r["sha256"] for r in rows}) < len(rows) or bool(conn.execute(text("""
            SELECT EXISTS (
              SELECT 1 FROM public.training_evidence other
              WHERE other.attempt_id<>:id AND other.sha256 = ANY(:hashes)
            )
        """), {"id": attempt_id, "hashes": [r["sha256"] for r in rows]}).scalar_one())
        other_visual = conn.execute(text("""
            SELECT DISTINCT perceptual_hash FROM public.training_evidence
            WHERE attempt_id<>:id AND perceptual_hash IS NOT NULL
            LIMIT 5000
        """), {"id": attempt_id}).scalars().all()
        near_duplicate = any(
            (int(current["perceptual_hash"], 16) ^ int(other, 16)).bit_count() <= 4
            for current in rows for other in other_visual
        )
        explanation = ("Снимок совпадает с другой попыткой; требуется проверка эксперта по внутреннему обучению."
                       if exact_duplicate else
                       "Снимок визуально похож на другую попытку; требуется проверка эксперта по внутреннему обучению."
                       if near_duplicate else
                       "Права и карточка проверены системой. Содержимое снимков ожидает проверки эксперта по внутреннему обучению.")
        evidence_ids = [int(r["evidence_id"]) for r in rows]
        previous = conn.execute(text("""
            SELECT evidence_ids FROM public.training_reviews
            WHERE attempt_id=:id ORDER BY review_id DESC LIMIT 1
        """), {"id": attempt_id}).mappings().first()
        if previous and set(previous["evidence_ids"]) == set(evidence_ids) and attempt["status"] in {"under_review", "completed"}:
            return {"status": attempt["status"], "outcome": attempt["outcome"],
                    "score": attempt["score"], "message": "Проверка уже сохранена."}
        conn.execute(text("""
            INSERT INTO public.training_reviews(attempt_id, rules, evidence_ids, explanation)
            VALUES (:id, CAST(:rules AS jsonb), :evidence, :explanation)
        """), {"id": attempt_id, "rules": json.dumps(attempt["rules"], ensure_ascii=False),
               "evidence": evidence_ids, "explanation": explanation})
        conn.execute(text("""
            UPDATE public.training_attempts
            SET status='under_review', outcome=NULL, score=NULL, last_checked_at=now()
            WHERE attempt_id=:id
        """), {"id": attempt_id})
        return {"status": "under_review", "message": explanation}


def _check_hire_attempt(conn: Connection, attempt: dict, user: dict) -> dict:
    attempt_id = int(attempt["attempt_id"])
    conn.execute(text("SELECT attempt_id FROM public.training_attempts WHERE attempt_id=:id FOR UPDATE"), {"id": attempt_id})
    rows = conn.execute(text("""
        SELECT evidence_id, step_key, sha256 FROM public.training_evidence
        WHERE attempt_id=:id AND superseded_at IS NULL ORDER BY step_key
    """), {"id": attempt_id}).mappings().all()
    required = set(attempt["rules"]["required_user_steps"])
    missing = sorted(required - {r["step_key"] for r in rows})
    if missing:
        return {"status": "in_progress", "missing_steps": missing,
                "message": "Добавьте подтверждение для каждого обязательного окна этого занятия."}
    evidence_ids = [int(r["evidence_id"]) for r in rows]
    previous = conn.execute(text("""
        SELECT evidence_ids FROM public.training_reviews WHERE attempt_id=:id
        ORDER BY review_id DESC LIMIT 1
    """), {"id": attempt_id}).mappings().first()
    if previous and set(previous["evidence_ids"]) == set(evidence_ids) and attempt["status"] in {"under_review", "completed"}:
        return {"status": attempt["status"], "outcome": attempt["outcome"],
                "score": attempt["score"], "message": "Проверка уже сохранена."}
    try:
        valid, reason, technical = hire_training.business_check(
            conn, attempt_id=attempt_id, participant_user_id=_actor(user), issued=attempt["fixture"])
    except Exception as exc:
        valid, reason, technical = False, f"Системная проверка недоступна: {exc}", True
    if technical:
        conn.execute(text("UPDATE public.training_attempts SET status='technical_pause' WHERE attempt_id=:id"),
                     {"id": attempt_id})
        return {"status": "technical_pause", "message": reason}
    if not valid:
        score = 1 if "не совпадает с выданным" in reason else 2
        explanation = f"Зачёт недоступен: {reason}"
        conn.execute(text("""
            INSERT INTO public.training_reviews(attempt_id,rules,evidence_ids,outcome,score,explanation)
            VALUES (:id,CAST(:rules AS jsonb),:evidence,'failed',:score,:reason)
        """), {"id": attempt_id, "rules": json.dumps(attempt["rules"], ensure_ascii=False),
               "evidence": evidence_ids, "score": score, "reason": explanation})
        conn.execute(text("""
            UPDATE public.training_attempts SET status='completed',outcome='failed',score=:score,
                last_checked_at=now() WHERE attempt_id=:id
        """), {"id": attempt_id, "score": score})
        hire_training._event(conn, attempt_id, "system", "check_failed", {"reason": reason, "score": score})
        return {"status": "completed", "outcome": "failed", "score": score, "message": explanation}
    duplicate = len({r["sha256"] for r in rows}) != len(rows) or bool(conn.execute(text("""
        SELECT EXISTS(SELECT 1 FROM public.training_evidence e
                      WHERE e.attempt_id<>:id AND e.sha256=ANY(:hashes))
    """), {"id": attempt_id, "hashes": [r["sha256"] for r in rows]}).scalar_one())
    explanation = ("Снимок совпадает с другой попыткой; эксперт по внутреннему обучению должен проверить его вручную."
                   if duplicate else
                    "Кадровые условия, согласие, задача и виза проверены. Содержимое и происхождение подтверждения нельзя надёжно установить автоматически: ожидается проверка эксперта по внутреннему обучению.")
    conn.execute(text("""
        INSERT INTO public.training_reviews(attempt_id,rules,evidence_ids,explanation)
        VALUES (:id,CAST(:rules AS jsonb),:evidence,:reason)
    """), {"id": attempt_id, "rules": json.dumps(attempt["rules"], ensure_ascii=False),
           "evidence": evidence_ids, "reason": explanation})
    conn.execute(text("""
        UPDATE public.training_attempts SET status='under_review',outcome=NULL,score=NULL,
            last_checked_at=now() WHERE attempt_id=:id
    """), {"id": attempt_id})
    hire_training._event(conn, attempt_id, "system", "business_check_passed",
                         {"evidence_ids": evidence_ids})
    return {"status": "under_review", "message": explanation}


class OrganizerDecision(BaseModel):
    evidence_valid: bool
    established_substitution: bool = False
    hint_or_action_correction: bool = False
    explanation: str = Field(min_length=10, max_length=2000)


def _grade_decision(decision: OrganizerDecision, *, had_evidence_correction: bool) -> tuple[int, str]:
    if decision.established_substitution:
        return 1, "failed"
    if not decision.evidence_valid:
        return 2, "failed"
    if decision.hint_or_action_correction:
        return 3, "passed"
    if had_evidence_correction:
        return 4, "passed"
    return 5, "passed"


@router.post("/attempts/{attempt_id}/review")
def organizer_review(attempt_id: int, body: OrganizerDecision,
                     user: dict = Depends(get_current_user)) -> dict:
    if not user.get("has_learning_review"):
        raise HTTPException(403, "Требуется право эксперта по внутреннему обучению.")
    with engine.begin() as conn:
        _guard(conn, write=True)
        attempt = _attempt(conn, attempt_id, user)
        if attempt["status"] != "under_review":
            raise HTTPException(409, "Попытка не ожидает проверки.")
        if attempt["lesson_code"] == "skill_2" and attempt["course_version"] in {2, 3}:
            valid, reason, technical = hire_training.business_check(
                conn, attempt_id=attempt_id,
                participant_user_id=int(attempt["participant_user_id"]), issued=attempt["fixture"])
            if technical:
                raise HTTPException(503, reason)
            if not valid and body.evidence_valid:
                raise HTTPException(409, f"Зачёт недоступен: {reason}")
            current_evidence = conn.execute(text("""
                SELECT step_key,evidence_id FROM public.training_evidence
                WHERE attempt_id=:id AND superseded_at IS NULL
            """), {"id": attempt_id}).mappings().all()
            if {r["step_key"] for r in current_evidence} != set(attempt["rules"]["required_user_steps"]):
                raise HTTPException(409, "Подтверждения этой попытки изменились; отправьте их повторно.")
        latest = conn.execute(text("""
            SELECT evidence_ids FROM public.training_reviews
            WHERE attempt_id=:id ORDER BY review_id DESC LIMIT 1
        """), {"id": attempt_id}).mappings().one()
        if attempt["lesson_code"] == "skill_2" and attempt["course_version"] in {2, 3}:
            if set(latest["evidence_ids"]) != {int(r["evidence_id"]) for r in current_evidence}:
                raise HTTPException(409, "Проверяемые снимки изменились; отправьте их повторно.")
        count = conn.execute(text("""
            SELECT count(*) FROM public.training_evidence
            WHERE attempt_id=:id AND superseded_at IS NOT NULL
        """), {"id": attempt_id}).scalar_one()
        score, outcome = _grade_decision(body, had_evidence_correction=bool(count))
        review_id = int(conn.execute(text("""
            INSERT INTO public.training_reviews
              (attempt_id, rules, evidence_ids, outcome, score, explanation)
            VALUES (:id, CAST(:rules AS jsonb), :evidence, :outcome, :score, :explanation)
            RETURNING review_id
        """), {"id": attempt_id, "rules": json.dumps(attempt["rules"], ensure_ascii=False),
               "evidence": latest["evidence_ids"], "outcome": outcome, "score": score,
               "explanation": body.explanation}).scalar_one())
        conn.execute(text("""
            UPDATE public.training_attempts
            SET status='completed', outcome=:outcome, score=:score, last_checked_at=now()
            WHERE attempt_id=:id
        """), {"id": attempt_id, "outcome": outcome, "score": score})
        conn.execute(text("""
            INSERT INTO public.training_attempt_events
              (attempt_id, actor_kind, actor_user_id, event_type,
               detail)
            VALUES (:id, 'organizer', :user, 'review_completed',
                    jsonb_build_object('outcome', :outcome, 'score', :score))
        """), {"id": attempt_id, "user": _actor(user), "outcome": outcome, "score": score})
        conn.execute(text("""
            INSERT INTO public.notifications(channel,recipient_user_id,payload,status)
            VALUES ('IN_APP_TRAINING',:participant,
                    jsonb_build_object('training_review_id',:review,'attempt_id',:attempt,'assignment_id',:assignment),
                    'PENDING')
            ON CONFLICT DO NOTHING
        """), {"participant": int(attempt["participant_user_id"]), "review": review_id,
               "attempt": attempt_id, "assignment": int(attempt["assignment_id"])})
        return {"status": "completed", "outcome": outcome, "score": score}


@router.post("/attempts/{attempt_id}/review/revise")
def revise_hire_review(attempt_id: int, body: OrganizerDecision,
                       user: dict = Depends(get_current_user)) -> dict:
    """Append an audited correction when an organizer discovers a mistaken review."""
    if not user.get("has_learning_review"):
        raise HTTPException(403, "Требуется право эксперта по внутреннему обучению.")
    with engine.begin() as conn:
        _guard(conn, write=True)
        attempt = _attempt(conn, attempt_id, user)
        if attempt["lesson_code"] != "skill_2" or attempt["course_version"] not in {2, 3} or attempt["status"] != "completed":
            raise HTTPException(409, "Исправление доступно только для оценённого учебного согласования.")
        conn.execute(text("SELECT attempt_id FROM public.training_attempts WHERE attempt_id=:id FOR UPDATE"), {"id": attempt_id})
        evidence = conn.execute(text("""
            SELECT evidence_id,step_key FROM public.training_evidence
            WHERE attempt_id=:id AND superseded_at IS NULL
        """), {"id": attempt_id}).mappings().all()
        if {r["step_key"] for r in evidence} != set(attempt["rules"]["required_user_steps"]):
            raise HTTPException(409, "Подтверждения этой попытки изменились.")
        evidence_ids = [int(r["evidence_id"]) for r in evidence]
        valid, reason, technical = hire_training.business_check(
            conn, attempt_id=attempt_id, participant_user_id=int(attempt["participant_user_id"]),
            issued=attempt["fixture"])
        if technical:
            raise HTTPException(503, reason)
        if not valid and body.evidence_valid:
            raise HTTPException(409, f"Зачёт недоступен: {reason}")
        corrections = int(conn.execute(text("""
            SELECT count(*) FROM public.training_evidence
            WHERE attempt_id=:id AND superseded_at IS NOT NULL
        """), {"id": attempt_id}).scalar_one())
        score, outcome = _grade_decision(body, had_evidence_correction=corrections > 0)
        previous = conn.execute(text("""
            SELECT outcome,score,explanation,evidence_ids FROM public.training_reviews
            WHERE attempt_id=:id ORDER BY review_id DESC LIMIT 1
        """), {"id": attempt_id}).mappings().one()
        if (previous["outcome"] == outcome and previous["score"] == score and
            previous["explanation"] == body.explanation and
            set(previous["evidence_ids"]) == set(evidence_ids)):
            return {"status": "completed", "outcome": outcome, "score": score}
        review_id = int(conn.execute(text("""
            INSERT INTO public.training_reviews
              (attempt_id,rules,evidence_ids,outcome,score,explanation)
            VALUES (:id,CAST(:rules AS jsonb),:evidence,:outcome,:score,:explanation)
            RETURNING review_id
        """), {"id": attempt_id, "rules": json.dumps(attempt["rules"], ensure_ascii=False),
               "evidence": evidence_ids, "outcome": outcome, "score": score,
               "explanation": body.explanation}).scalar_one())
        conn.execute(text("""
            UPDATE public.training_attempts SET outcome=:outcome,score=:score,last_checked_at=now()
            WHERE attempt_id=:id
        """), {"id": attempt_id, "outcome": outcome, "score": score})
        hire_training._event(conn, attempt_id, "organizer", "review_revised",
                             {"old_score": previous["score"], "score": score,
                              "reason": body.explanation}, _actor(user))
        conn.execute(text("""
            INSERT INTO public.notifications(channel,recipient_user_id,payload,status)
            VALUES ('IN_APP_TRAINING',:participant,
                    jsonb_build_object('training_review_id',:review,'attempt_id',:attempt,'assignment_id',:assignment),
                    'PENDING')
            ON CONFLICT DO NOTHING
        """), {"participant": int(attempt["participant_user_id"]), "review": review_id,
               "attempt": attempt_id, "assignment": int(attempt["assignment_id"])})
        return {"status": "completed", "outcome": outcome, "score": score}


@router.get("/me/summary")
def my_training_summary(user: dict = Depends(get_current_user)) -> dict:
    with engine.connect() as conn:
        _guard(conn)
        rows = conn.execute(text(f"""
            SELECT a.assignment_id, l.lesson_code, l.title AS lesson_title,
                   c.course_code, c.title AS course_title, c.version AS course_version,
                   {LESSON_NUMBER_SQL} AS lesson_number,
                   t.attempt_id, t.attempt_number, t.status, t.outcome, t.score,
                   t.started_at, t.last_checked_at,
                   t.fixture->>'application_number' AS application_number,
                   latest_review.explanation, latest_review.reviewed_at,
                   latest_review.reviewer_name
            FROM public.training_assignments a
            JOIN public.training_lesson_versions l USING(lesson_version_id)
            JOIN public.training_course_versions c USING(course_version_id)
            LEFT JOIN public.training_attempts t USING(assignment_id)
            LEFT JOIN LATERAL (
                SELECT r.explanation, r.created_at AS reviewed_at,
                       reviewer.full_name AS reviewer_name
                FROM public.training_reviews r
                LEFT JOIN LATERAL (
                    SELECT u.full_name FROM public.training_attempt_events e
                    JOIN public.users u ON u.user_id=e.actor_user_id
                    WHERE e.attempt_id=r.attempt_id AND e.created_at=r.created_at
                      AND e.event_type IN ('review_completed','review_revised')
                    ORDER BY e.event_id DESC LIMIT 1
                ) reviewer ON TRUE
                WHERE r.attempt_id=t.attempt_id
                ORDER BY r.review_id DESC LIMIT 1
            ) latest_review ON TRUE
            WHERE a.participant_user_id=:user
            ORDER BY a.assignment_id, t.attempt_number DESC NULLS LAST
        """), {"user": _actor(user)}).mappings().all()
    grouped: dict[int, dict] = {}
    for row in rows:
        key = int(row["assignment_id"])
        item = grouped.setdefault(key, {
            "assignment_id": key, "course_code": row["course_code"], "lesson_code": row["lesson_code"],
            "lesson_title": row["lesson_title"], "course_title": row["course_title"],
            "course_version": row["course_version"], "lesson_number": row["lesson_number"], "attempts": [],
        })
        if row["attempt_id"] is not None:
            item["attempts"].append({k: row[k] for k in (
                "attempt_id", "attempt_number", "status", "outcome", "score",
                "started_at", "last_checked_at", "application_number", "explanation",
                "reviewed_at", "reviewer_name")})
    return {"full_name": user.get("full_name"), "position_name": user.get("position_name"),
            "items": list(grouped.values())}


@router.get("/me/notifications")
def my_training_notifications(user: dict = Depends(get_current_user)) -> dict:
    """In-app notices backed by the existing notifications table."""
    with engine.connect() as conn:
        _guard(conn)
        rows = conn.execute(text(f"""
            SELECT n.notification_id, r.review_id, r.score, r.outcome,
                   r.explanation, r.created_at AS reviewed_at,
                   reviewer.full_name AS reviewer_name,
                   t.attempt_id, t.attempt_number,
                   t.fixture->>'application_number' AS application_number,
                   c.title AS course_title, l.title AS lesson_title,
                   {LESSON_NUMBER_SQL} AS lesson_number
            FROM public.notifications n
            JOIN public.training_reviews r
              ON r.review_id=(n.payload->>'training_review_id')::bigint
            JOIN public.training_attempts t ON t.attempt_id=r.attempt_id
            JOIN public.training_assignments a ON a.assignment_id=t.assignment_id
            JOIN public.training_lesson_versions l ON l.lesson_version_id=a.lesson_version_id
            JOIN public.training_course_versions c ON c.course_version_id=l.course_version_id
            LEFT JOIN LATERAL (
                SELECT u.full_name FROM public.training_attempt_events e
                JOIN public.users u ON u.user_id=e.actor_user_id
                WHERE e.attempt_id=r.attempt_id AND e.created_at=r.created_at
                  AND e.event_type IN ('review_completed','review_revised')
                ORDER BY e.event_id DESC LIMIT 1
            ) reviewer ON TRUE
            WHERE n.channel='IN_APP_TRAINING' AND n.recipient_user_id=:uid
              AND a.participant_user_id=:uid AND r.score IS NOT NULL
            ORDER BY n.notification_id DESC
        """), {"uid": _actor(user)}).mappings().all()
    return {"items": [dict(row) for row in rows]}


@router.get("/me/tasks")
def my_training_tasks(user: dict = Depends(get_current_user)) -> dict:
    """Personal task read model keyed by a required training assignment.

    Generic tasks are scoped by executor role, so using public.tasks here
    would expose one participant's assignment to colleagues sharing that role.
    """
    with engine.connect() as conn:
        _guard(conn)
        return {"items": _training_task_rows(conn, user)}


def _training_task_rows(conn: Connection, user: dict) -> list[dict]:
    current = [item for item in _current_assignment_rows(conn, user) if item["required"]]
    if not current:
        return []
    else:
        passed = conn.execute(text("""
            SELECT DISTINCT ON (t.assignment_id) t.assignment_id, t.attempt_id,
                   t.attempt_number
            FROM public.training_attempts t
            JOIN public.training_assignments a ON a.assignment_id=t.assignment_id
            WHERE a.participant_user_id=:uid AND t.outcome='passed'
              AND t.assignment_id=ANY(:ids)
            ORDER BY t.assignment_id, t.attempt_number DESC
        """), {"uid": _actor(user), "ids": [int(item["assignment_id"]) for item in current]}).mappings().all()
    passed_by_assignment = {int(row["assignment_id"]): row for row in passed}
    items = []
    for item in current:
        assignment_id = int(item["assignment_id"])
        passed_attempt = passed_by_assignment.get(assignment_id)
        if passed_attempt:
            state = "passed"
            target = f"/training/attempts/{passed_attempt['attempt_id']}"
        elif item["latest_status"] == "completed":
            state = "failed"
            target = f"/training#assignment-{assignment_id}"
        elif item["latest_status"] == "under_review":
            state = "under_review"
            target = f"/training/attempts/{item['latest_attempt_id']}"
        elif item["latest_status"] in {"in_progress", "technical_pause"}:
            state = "in_progress"
            target = f"/training/attempts/{item['latest_attempt_id']}"
        else:
            state = "not_started"
            target = f"/training#assignment-{assignment_id}"
        items.append({
            "assignment_id": assignment_id, "source_kind": "training_assignment",
            "course_title": item["course_title"], "lesson_title": item["title"],
            "lesson_number": item["lesson_number"], "state": state, "href": target,
            "due_at": None,
        })
    return items


def _visible_attempt_rows(conn: Connection, user: dict, *, participant: str | None,
                          course_id: int | None, date_from: str | None,
                          date_to: str | None, result: str | None) -> list[dict]:
    rows = conn.execute(text(f"""
        SELECT t.attempt_id, t.attempt_number, t.status, t.outcome, t.score,
               t.started_at, t.last_checked_at, t.fixture,
               a.participant_user_id, a.required, u.full_name,
               l.title AS lesson_title, l.lesson_code,
               {LESSON_NUMBER_SQL} AS lesson_number,
               c.course_version_id, c.title AS course_title, c.version AS course_version
        FROM public.training_attempts t
        JOIN public.training_assignments a USING (assignment_id)
        JOIN public.users u ON u.user_id=a.participant_user_id
        JOIN public.training_lesson_versions l USING (lesson_version_id)
        JOIN public.training_course_versions c USING (course_version_id)
        WHERE (:participant IS NULL OR u.full_name ILIKE :participant)
          AND (:course IS NULL OR c.course_version_id=:course)
          AND (:date_from IS NULL OR t.started_at::date>=CAST(:date_from AS date))
          AND (:date_to IS NULL OR t.started_at::date<=CAST(:date_to AS date))
          AND (:result IS NULL OR t.status=:result OR t.outcome=:result)
        ORDER BY t.attempt_id DESC
    """), {"participant": f"%{participant}%" if participant else None,
           "course": course_id, "date_from": date_from, "date_to": date_to,
           "result": result}).mappings().all()
    return [dict(row) for row in rows
            if _can_view_participant(conn, user, int(row["participant_user_id"]))]


@router.get("/results/attempts")
def attempt_results(participant: str | None = None, course_id: int | None = None,
                    date_from: str | None = None, date_to: str | None = None,
                    result: str | None = None, sort: str = "desc",
                    page: int = Query(default=1, ge=1),
                    page_size: int = Query(default=20, ge=1, le=100),
                    user: dict = Depends(get_current_user)) -> dict:
    if sort not in {"asc", "desc"}:
        raise HTTPException(422, "Неверная сортировка.")
    with engine.connect() as conn:
        _guard(conn)
        rows = _visible_attempt_rows(conn, user, participant=participant,
                                     course_id=course_id, date_from=date_from,
                                     date_to=date_to, result=result)
    rows.sort(key=lambda row: (row["last_checked_at"] or row["started_at"], row["attempt_id"]),
              reverse=sort == "desc")
    start = (page - 1) * page_size
    return {"items": rows[start:start + page_size], "total": len(rows),
            "page": page, "page_size": page_size}


@router.get("/results/courses")
def course_results(participant: str | None = None, course_id: int | None = None,
                   result: str | None = None, sort: str = "desc",
                   page: int = Query(default=1, ge=1),
                   page_size: int = Query(default=20, ge=1, le=100),
                   user: dict = Depends(get_current_user)) -> dict:
    if sort not in {"asc", "desc"}:
        raise HTTPException(422, "Неверная сортировка.")
    with engine.connect() as conn:
        _guard(conn)
        rows = conn.execute(text("""
            SELECT a.assignment_id, a.participant_user_id, a.required,
                   u.full_name, current_position.name AS position_name, c.course_version_id,
                   c.title AS course_title, c.version AS course_version,
                   latest.score, latest.outcome, latest.last_checked_at
            FROM public.training_assignments a
            JOIN public.users u ON u.user_id=a.participant_user_id
            JOIN public.training_lesson_versions l USING (lesson_version_id)
            JOIN public.training_course_versions c USING (course_version_id)
            LEFT JOIN public.training_identity_links training_link
              ON training_link.training_user_id=u.user_id AND training_link.source_kind='local'
            LEFT JOIN public.users source_user ON source_user.user_id=training_link.source_user_id
            LEFT JOIN public.employees e ON e.employee_id=COALESCE(u.employee_id, source_user.employee_id)
            LEFT JOIN LATERAL (
              SELECT MIN(pa.position_id) AS position_id
              FROM public.person_assignments pa
              WHERE pa.person_id=e.person_id AND pa.is_primary=TRUE AND pa.active_flag=TRUE
                AND pa.lifecycle_status='active' AND pa.start_date<=CURRENT_DATE
                AND (pa.end_date IS NULL OR pa.end_date>=CURRENT_DATE)
              HAVING COUNT(*)=1
            ) current_assignment ON TRUE
            LEFT JOIN public.positions current_position
              ON current_position.position_id=current_assignment.position_id
            LEFT JOIN LATERAL (
              SELECT t.score, t.outcome, t.last_checked_at
              FROM public.training_attempts t
              WHERE t.assignment_id=a.assignment_id AND t.status='completed'
              ORDER BY t.last_checked_at DESC, t.attempt_id DESC LIMIT 1
            ) latest ON TRUE
            WHERE (:participant IS NULL OR u.full_name ILIKE :participant)
              AND (:course IS NULL OR c.course_version_id=:course)
            ORDER BY a.participant_user_id, c.course_version_id, a.assignment_id
        """), {"participant": f"%{participant}%" if participant else None,
               "course": course_id}).mappings().all()
        groups: dict[tuple[int, int], dict] = {}
        for source in rows:
            if not _can_view_participant(conn, user, int(source["participant_user_id"])):
                continue
            key = (int(source["participant_user_id"]), int(source["course_version_id"]))
            group = groups.setdefault(key, {
                "participant_user_id": key[0], "course_version_id": key[1],
                "full_name": source["full_name"], "position": source["position_name"],
                "course_title": source["course_title"], "course_version": source["course_version"],
                "required_total": 0, "required_passed": 0, "scores": [],
                "last_checked_at": None,
            })
            if source["required"]:
                group["required_total"] += 1
                if source["outcome"] == "passed" and source["score"] is not None and source["score"] >= 3:
                    group["required_passed"] += 1
                    group["scores"].append(int(source["score"]))
            checked = source["last_checked_at"]
            if checked and (group["last_checked_at"] is None or checked > group["last_checked_at"]):
                group["last_checked_at"] = checked
    items = []
    for group in groups.values():
        done = group["required_total"] > 0 and group["required_passed"] == group["required_total"]
        group["status"] = "passed" if done else "in_progress"
        group["score"] = round(sum(group["scores"]) / len(group["scores"]), 1) if done else None
        group["reason"] = (None if done else
                           "Обязательные занятия не назначены." if group["required_total"] == 0 else
                           "Не все обязательные занятия зачтены.")
        del group["scores"]
        if result is None or result == group["status"]:
            items.append(group)
    items.sort(key=lambda row: (row["last_checked_at"].timestamp() if row["last_checked_at"] else 0,
                               row["participant_user_id"]), reverse=sort == "desc")
    start = (page - 1) * page_size
    return {"items": items[start:start + page_size], "total": len(items),
            "page": page, "page_size": page_size}
