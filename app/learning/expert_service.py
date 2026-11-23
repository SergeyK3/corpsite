"""Saved learning catalog, recipient snapshots and expert completion view."""
from __future__ import annotations

import json
import os
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, insert, select, text, update

from app.learning.catalog import BY_CODE, COURSE, COURSES, LESSONS
from app.learning.hire_path import COURSE_CODE as HIRE_COURSE_CODE, ROUTE_TITLE, STEP_BY_CODE, step_for_lesson
from app.learning.model import assignment_batches, assignments, attempts, courses, hire_applications, hire_step_links, lessons, review_events


def _json(value):
    return json.dumps(value, ensure_ascii=False)


def all_courses(conn, *, include_drafts: bool = False) -> list[dict]:
    result = {item["code"]: {**item, "state": "published" if item["state"] == "available" else item["state"]} for item in COURSES}
    for row in conn.execute(select(courses)).mappings():
        result[row["code"]] = {"code": row["code"], "title": row["title"], "audience": row["audience"], "state": row["state"]}
    return [item for item in result.values() if include_drafts or item["state"] == "published"]


def course(conn, code: str, *, include_draft: bool = False) -> dict:
    found = next((item for item in all_courses(conn, include_drafts=True) if item["code"] == code), None)
    if found is None or (found["state"] != "published" and not include_draft):
        raise HTTPException(404, "Курс не найден")
    return found


def all_lessons(conn, *, include_drafts: bool = False) -> list[dict]:
    base = {item["code"]: {**item, "course_code": COURSE["code"], "target_role": COURSE["audience"],
                            "state": "published"} for item in LESSONS}
    for row in conn.execute(select(lessons)).mappings():
        data = dict(row)
        criteria = json.loads(data["criteria_json"])
        shots = json.loads(data["screenshots_json"])
        base[row["code"]] = {"code": row["code"], "course_code": row["course_code"], "title": row["title"],
            "target_role": row["target_role"], "minutes": row["minutes"], "task": row["task"],
            "instruction": row["instruction"], "guide_url": row["guide_url"] or None,
            "criteria": criteria, "required": criteria[row["required_index"]], "required_index": row["required_index"],
            "screenshots": shots, "state": row["state"], "expected_action": "submitted",
            "function": "Практическое занятие", "skill": row["target_role"], "number": 1}
    result = []
    for item in base.values():
        step = step_for_lesson(item)
        if step is not None:
            item.update(route_step=step, route_title=ROUTE_TITLE, function=ROUTE_TITLE, number=step)
        if include_drafts or item["state"] == "published":
            result.append(item)
    return sorted(result, key=lambda item: (0 if item.get("route_step") else 1, item.get("route_step", 0)))


def lesson(conn, code: str, *, include_draft: bool = False) -> dict:
    found = next((item for item in all_lessons(conn, include_drafts=True) if item["code"] == code), None)
    if found is None or (found["state"] != "published" and not include_draft):
        raise HTTPException(404, "Занятие не найдено")
    return found


def assigned_lessons(conn, participant_id: int, unit_id: int, role_code: str | None = None) -> list[dict]:
    assigned = set(conn.execute(select(assignments.c.lesson_code).where(and_(
        assignments.c.participant_id == participant_id, assignments.c.unit_id == unit_id))).scalars())
    builtin = role_code is None or role_code in {"DIRECTOR", "DEPARTMENT_HEAD", "CLINICAL_DEPARTMENT_HEAD"}
    if builtin:
        assigned.update(BY_CODE)
    visible = [item for item in all_lessons(conn) if item["code"] in assigned]
    # Rehearsal makes the four draft cards visible only to the dedicated HR
    # role in the isolated learning instance. It does not publish the cards.
    database = conn.engine.url.database or ""
    isolated = database == "corpsite_learn" or (
        database.startswith("corpsite_learn_rehearsal_") and os.getenv("TRAINING_REHEARSAL") == "1")
    if (isolated
            and os.getenv("HIRE_PATH_REHEARSAL") == "1" and os.getenv("TRAINING_SERVER_ENABLED") == "1"
            and os.getenv("TRAINING_MODE") == "1" and os.getenv("TRAINING_DISABLE_EXTERNAL") == "1"
            and role_code == "LEARN_HR"):
        known = {item["code"] for item in visible}
        for item in all_lessons(conn, include_drafts=True):
            if step_for_lesson(item) not in {1, 2, 3, 4, 5} or item["code"] in known:
                continue
            if item["code"] in STEP_BY_CODE:
                item = {**item, "instruction": item["instruction"].split("Блокер публикации:", 1)[0].strip()}
            visible.append(item)
    return visible


def visible_catalog(conn, user: dict) -> dict:
    user_lessons = assigned_lessons(conn, int(user["user_id"]), int(user["unit_id"]), user.get("role_code"))
    codes = {item["course_code"] for item in user_lessons}
    course_items = [item for item in all_courses(conn) if item["code"] in codes]
    return {"course": course_items[0] if course_items else {**COURSE, "state": "published"},
            "courses": course_items, "lessons": user_lessons}


def save_course(conn, user: dict, data: dict, code: str | None = None) -> dict:
    title = data["title"].strip()
    if not title:
        raise HTTPException(422, "Укажите название курса")
    code = code or f"course_{uuid4().hex[:12]}"
    existing = conn.execute(select(courses).where(courses.c.code == code)).mappings().first()
    if existing is None and code in {item["code"] for item in COURSES} and code != COURSE["code"]:
        raise HTTPException(409, "Курс в подготовке пока недоступен для редактирования")
    values = {"title": title, "audience": data.get("audience", "").strip()}
    if existing:
        conn.execute(update(courses).where(courses.c.code == code).values(**values, updated_at=datetime.utcnow()))
    else:
        conn.execute(insert(courses).values(code=code, **values, state="published" if code == COURSE["code"] else "draft",
                                           created_by=int(user["user_id"])))
    return course(conn, code, include_draft=True)


def save_lesson(conn, user: dict, data: dict, code: str | None = None) -> dict:
    course(conn, data["course_code"], include_draft=True)
    criteria = [str(item).strip() for item in data["criteria"]]
    shots = [str(item).strip() for item in data["screenshots"]]
    if len(criteria) != 5 or any(not item for item in criteria) or len(set(criteria)) != len(criteria):
        raise HTTPException(422, "Нужно пять различных критериев")
    if not 1 <= len(shots) <= 5 or any(not item for item in shots):
        raise HTTPException(422, "Укажите поля для снимков")
    if not 0 <= data["required_index"] < len(criteria):
        raise HTTPException(422, "Укажите обязательный критерий")
    if not data["title"].strip() or not data["target_role"].strip() or not data["task"].strip():
        raise HTTPException(422, "Название, целевая роль и задание обязательны")
    guide_url = data.get("guide_url", "").strip()
    if guide_url and not guide_url.startswith("https://docs.google.com/document/"):
        raise HTTPException(422, "Укажите ссылку на инструкцию в Google Документах")
    code = code or f"lesson_{uuid4().hex[:12]}"
    old = conn.execute(select(lessons).where(lessons.c.code == code)).mappings().first()
    if old is None and code in BY_CODE:
        raise HTTPException(409, "Системное занятие нельзя заменить черновиком")
    if old and old["state"] == "published":
        unsnapshotted = conn.execute(select(attempts.c.id).where(and_(
            attempts.c.lesson_code == code, attempts.c.lesson_snapshot_json.is_(None))).limit(1)).first()
        if unsnapshotted and (json.loads(old["criteria_json"]) != criteria or old["required_index"] != data["required_index"]):
            raise HTTPException(409, "Сначала сохраните критерии прежних попыток")
    values = {"course_code": data["course_code"], "title": data["title"].strip(),
              "target_role": data["target_role"].strip(), "minutes": data["minutes"],
              "task": data["task"].strip(), "instruction": data.get("instruction", "").strip(),
              "guide_url": guide_url, "criteria_json": _json(criteria), "required_index": data["required_index"],
              "screenshots_json": _json(shots)}
    if old:
        conn.execute(update(lessons).where(lessons.c.code == code).values(**values, updated_at=datetime.utcnow()))
    else:
        conn.execute(insert(lessons).values(code=code, **values, state="draft", created_by=int(user["user_id"])))
    return lesson(conn, code, include_draft=True)


def publish_course(conn, code: str) -> dict:
    current = course(conn, code, include_draft=True)
    if code == COURSE["code"] and current["state"] == "published":
        return current
    if not conn.execute(select(lessons.c.code).where(and_(lessons.c.course_code == code,
                                                            lessons.c.state == "published")).limit(1)).first():
        raise HTTPException(409, "Сначала опубликуйте хотя бы одно занятие")
    conn.execute(update(courses).where(courses.c.code == code).values(state="published", updated_at=datetime.utcnow()))
    return course(conn, code)


def publish_lesson(conn, code: str) -> dict:
    current = lesson(conn, code, include_draft=True)
    if code in BY_CODE:
        return current
    if code in STEP_BY_CODE:
        if os.getenv("HIRE_PATH_APPROVED") != "1":
            raise HTTPException(409, "Маршрут приёма ещё не прошёл сквозную проверку и согласование правил")
        if not current.get("guide_url"):
            raise HTTPException(409, "Сначала прикрепите проверенное руководство")
    conn.execute(update(lessons).where(lessons.c.code == code).values(state="published", updated_at=datetime.utcnow()))
    return lesson(conn, code)


def recipients(conn, selector: dict, preview_users: dict | None = None) -> list[dict]:
    ids = {int(item) for item in selector.get("employee_ids", [])}
    position = (selector.get("position_name") or "").strip()
    unit_id = selector.get("unit_id")
    if not ids and not (position and unit_id):
        raise HTTPException(422, "Укажите сотрудников или группу по должности и подразделению")
    if preview_users is not None:
        items = [{"user_id": int(item["user_id"]), "employee_id": int(item.get("employee_id", item["user_id"])),
                  "name": item.get("full_name", ""),
                  "unit_id": int(item["unit_id"]), "position_name": item.get("position_name", "")}
                 for item in preview_users.values() if item.get("is_active", True)]
    else:
        items = [dict(row) for row in conn.execute(text("""
            SELECT u.user_id, e.employee_id, u.full_name AS name, e.org_unit_id AS unit_id, p.name AS position_name
            FROM public.users u
            LEFT JOIN public.training_identity_links link ON link.training_user_id=u.user_id
                AND link.source_kind='local'
            LEFT JOIN public.users source_user ON source_user.user_id=link.source_user_id
            JOIN public.employees e ON e.employee_id=COALESCE(u.employee_id, source_user.employee_id)
            JOIN public.positions p ON p.position_id=e.position_id
            WHERE u.is_active AND e.is_active
              AND NOT EXISTS (SELECT 1 FROM public.training_identity_links source_link
                  WHERE source_link.source_kind='local' AND source_link.source_user_id=u.user_id)
        """)).mappings()]
    result = [item for item in items if item["employee_id"] in ids or
              (position and unit_id and item["position_name"] == position and item["unit_id"] == int(unit_id))]
    if ids - {item["employee_id"] for item in result}:
        raise HTTPException(404, "Один из сотрудников не найден")
    return sorted(result, key=lambda item: (item["name"], item["user_id"]))


HIRE_ROUTE_ASSIGNMENT_CODE = "hire_route_v1"
HIRE_ROUTE_FIRST_CODE = "lesson_5b2e5028ea63"
HIRE_ROUTE_MEMBERS = (HIRE_ROUTE_FIRST_CODE, *STEP_BY_CODE)


def _single_hire_route_enabled(conn) -> bool:
    database = conn.engine.url.database or ""
    isolated = database == "corpsite_learn" or (
        database.startswith("corpsite_learn_rehearsal_") and os.getenv("TRAINING_REHEARSAL") == "1")
    return isolated and os.getenv("HIRE_PATH_REHEARSAL") == "1" and os.getenv("TRAINING_SERVER_ENABLED") == "1"


def _assignment_display(items: list[dict]) -> list[dict]:
    result = []
    route_shown = False
    for item in items:
        if item["code"] in HIRE_ROUTE_MEMBERS:
            if not route_shown:
                result.append({"code": HIRE_ROUTE_ASSIGNMENT_CODE, "title": ROUTE_TITLE})
                route_shown = True
        else:
            result.append({"code": item["code"], "title": item["title"]})
    return result


def target_lessons(conn, target_type: str, target_code: str) -> list[dict]:
    single_route = _single_hire_route_enabled(conn)
    if target_type == "lesson":
        if single_route and target_code == HIRE_ROUTE_ASSIGNMENT_CODE:
            course(conn, HIRE_COURSE_CODE)
            return [lesson(conn, code, include_draft=True) for code in HIRE_ROUTE_MEMBERS]
        if single_route and target_code in HIRE_ROUTE_MEMBERS:
            raise HTTPException(409, "Назначьте единый маршрут «Приём нового сотрудника на работу».")
        item = lesson(conn, target_code)
        if course(conn, item["course_code"])["state"] != "published":
            raise HTTPException(409, "Курс не опубликован")
        return [item]
    if target_type != "course":
        raise HTTPException(422, "Неизвестный тип назначения")
    course(conn, target_code)
    items = [item for item in all_lessons(conn) if item["course_code"] == target_code]
    if single_route and target_code == HIRE_COURSE_CODE and HIRE_ROUTE_FIRST_CODE in {item["code"] for item in items}:
        members = [lesson(conn, code, include_draft=True) for code in HIRE_ROUTE_MEMBERS]
        items = members + [item for item in items if item["code"] not in HIRE_ROUTE_MEMBERS]
    if not items:
        raise HTTPException(409, "В курсе нет опубликованных занятий")
    return items


def assignment_preview(conn, data: dict, preview_users: dict | None = None) -> dict:
    items = target_lessons(conn, data["target_type"], data["target_code"])
    people = recipients(conn, data["selector"], preview_users)
    if not people:
        raise HTTPException(422, "Получатели не найдены")
    display = _assignment_display(items) if _single_hire_route_enabled(conn) else [
        {"code": item["code"], "title": item["title"]} for item in items]
    return {"lessons": display, "recipients": people, "due_at": data.get("due_at")}


def assign(conn, user: dict, data: dict, preview_users: dict | None = None) -> dict:
    preview = assignment_preview(conn, data, preview_users)
    ids = [item["user_id"] for item in preview["recipients"]]
    if sorted(ids) != sorted(set(data["expected_recipient_ids"])):
        raise HTTPException(409, "Список получателей изменился; повторите предпросмотр")
    batch_id = str(uuid4())
    conn.execute(insert(assignment_batches).values(id=batch_id, target_type=data["target_type"],
        target_code=data["target_code"], selector_json=_json(data["selector"]),
        recipients_json=_json(preview["recipients"]), due_at=data.get("due_at"),
        created_by=int(user["user_id"])))
    created = 0
    members = target_lessons(conn, data["target_type"], data["target_code"])
    for person in preview["recipients"]:
        for item in members:
            exists = conn.execute(select(assignments.c.id).where(and_(
                assignments.c.lesson_code == item["code"], assignments.c.participant_id == person["user_id"]))).first()
            if exists:
                continue
            conn.execute(insert(assignments).values(id=str(uuid4()), batch_id=batch_id,
                lesson_code=item["code"], participant_id=person["user_id"], unit_id=person["unit_id"],
                recipient_name=person["name"], position_name=person["position_name"], due_at=data.get("due_at")))
            created += 1
    return {"batch_id": batch_id, "recipients": preview["recipients"], "lessons": preview["lessons"],
            "created": created, "existing": len(ids) * len(members) - created, "due_at": data.get("due_at")}


def training_assignment_preview(conn, data: dict) -> dict:
    if data["target_type"] != "lesson" or data["target_code"] != "training:skill_2":
        raise HTTPException(404, "Занятие обучения не найдено")
    lesson = conn.execute(text("""
        SELECT l.lesson_version_id, l.title FROM public.training_lesson_versions l
        JOIN public.training_course_versions c USING(course_version_id)
        WHERE c.course_code='application_administration' AND c.version=3
          AND l.lesson_code='skill_2'
    """)).mappings().one_or_none()
    if lesson is None:
        raise HTTPException(409, "Занятие по согласованию ещё не опубликовано")
    people = recipients(conn, data["selector"])
    if not people:
        raise HTTPException(422, "Получатели не найдены")
    for person in people:
        linked = conn.execute(text("""
            SELECT 1 FROM public.training_identity_links
            WHERE training_user_id=:uid AND source_kind='local'
        """), {"uid": person["user_id"]}).first()
        if person["position_name"] != "Заведующий отделением" or linked is None:
            raise HTTPException(422, "Для согласования нужен связанный учебный аккаунт заведующего отделением")
    return {"lessons": [{"code": "training:skill_2", "title": lesson["title"]}],
            "recipients": people, "due_at": data.get("due_at"),
            "lesson_version_id": lesson["lesson_version_id"]}


def assign_training(conn, user: dict, data: dict) -> dict:
    preview = training_assignment_preview(conn, data)
    ids = [person["user_id"] for person in preview["recipients"]]
    if sorted(ids) != sorted(set(data["expected_recipient_ids"])):
        raise HTTPException(409, "Список получателей изменился; повторите предпросмотр")
    batch_id = str(uuid4())
    conn.execute(insert(assignment_batches).values(id=batch_id, target_type="lesson",
        target_code="training:skill_2", selector_json=_json(data["selector"]),
        recipients_json=_json(preview["recipients"]), due_at=data.get("due_at"),
        created_by=int(user["user_id"])))
    created = 0
    for person in preview["recipients"]:
        row = conn.execute(text("""
            INSERT INTO public.training_assignments
              (participant_user_id,lesson_version_id,required,instruction_url)
            VALUES (:participant,:lesson,TRUE,'/training')
            ON CONFLICT(participant_user_id,lesson_version_id) DO NOTHING
            RETURNING assignment_id
        """), {"participant": person["user_id"], "lesson": preview["lesson_version_id"]}).first()
        created += int(row is not None)
    return {"batch_id": batch_id, "recipients": preview["recipients"],
            "lessons": preview["lessons"], "created": created,
            "existing": len(ids) - created, "due_at": data.get("due_at")}


def completion(conn, filters: dict) -> list[dict]:
    lesson_map = {item["code"]: item for item in all_lessons(conn, include_drafts=True)}
    rows = conn.execute(select(assignments)).mappings().all()
    result = []
    for row in rows:
        item = lesson_map.get(row["lesson_code"])
        if item is None:
            continue
        history = conn.execute(select(attempts).where(and_(attempts.c.participant_id == row["participant_id"],
            attempts.c.lesson_code == row["lesson_code"])).order_by(attempts.c.attempt_no.desc())).mappings().all()
        for attempt in history or [None]:
            status = attempt["status"] if attempt else "not_started"
            application_id = conn.execute(select(hire_applications.c.application_id).where(
                hire_applications.c.attempt_id == attempt["id"])).scalar_one_or_none() if attempt else None
            result.append({"participant_id": row["participant_id"], "participant_name": row["recipient_name"],
                "unit_id": row["unit_id"], "course_code": item["course_code"], "lesson_code": item["code"],
                "lesson_title": item["title"], "status": status, "attempt_id": attempt["id"] if attempt else None,
                "attempt_no": attempt["attempt_no"] if attempt else None, "application_id": application_id,
                "score": attempt["score"] if attempt else None,
                "review_source": attempt["review_source"] if attempt else None,
                "auto_status": attempt["auto_status"] if attempt else "unavailable", "due_at": row["due_at"]})
    # The isolated rehearsal exposes unpublished hire steps to its HR role.
    # Their attempts must also be visible to the expert even though draft
    # lessons cannot be assigned through the normal catalog.
    database = conn.engine.url.database or ""
    if (conn.dialect.name == "postgresql"
            and (database == "corpsite_learn" or (
                database.startswith("corpsite_learn_rehearsal_") and os.getenv("TRAINING_REHEARSAL") == "1"))
            and os.getenv("HIRE_PATH_REHEARSAL") == "1"
            and os.getenv("TRAINING_SERVER_ENABLED") == "1"
            and os.getenv("TRAINING_MODE") == "1"
            and os.getenv("TRAINING_DISABLE_EXTERNAL") == "1"):
        represented = {item["attempt_id"] for item in result if item["attempt_id"]}
        for attempt in conn.execute(select(attempts).where(
                attempts.c.lesson_code.in_(tuple(STEP_BY_CODE)))).mappings():
            if attempt["id"] in represented:
                continue
            item = lesson_map.get(attempt["lesson_code"])
            if item is None:
                continue
            root_id = conn.execute(select(hire_step_links.c.root_attempt_id).where(
                hire_step_links.c.attempt_id == attempt["id"])).scalar_one_or_none()
            application_id = conn.execute(select(hire_applications.c.application_id).where(
                hire_applications.c.attempt_id == root_id)).scalar_one_or_none() if root_id else None
            participant_name = conn.execute(text("SELECT full_name FROM public.users WHERE user_id=:id"),
                {"id": attempt["participant_id"]}).scalar_one_or_none() or f"#{attempt['participant_id']}"
            result.append({"participant_id": attempt["participant_id"], "participant_name": participant_name,
                "unit_id": attempt["unit_id"], "course_code": item["course_code"],
                "lesson_code": item["code"], "lesson_title": item["title"],
                "status": attempt["status"], "attempt_id": attempt["id"],
                "attempt_no": attempt["attempt_no"], "application_id": application_id,
                "score": attempt["score"], "review_source": attempt["review_source"],
                "auto_status": attempt["auto_status"], "due_at": None})
    # The established /training assignments remain in their own versioned
    # tables.  Read them into the same expert view without rewriting history.
    if conn.dialect.name == "postgresql":
        training = conn.execute(text("""
            SELECT a.participant_user_id, u.full_name AS participant_name,
                   COALESCE(e.org_unit_id, 0) AS unit_id,
                   c.course_code, l.lesson_code, l.title AS lesson_title,
                   t.attempt_id, t.attempt_number, t.status AS attempt_status,
                   t.outcome, t.score, o.application_id
            FROM public.training_assignments a
            JOIN public.users u ON u.user_id=a.participant_user_id
            LEFT JOIN public.training_identity_links link
              ON link.training_user_id=u.user_id AND link.source_kind='local'
            LEFT JOIN public.users source_user ON source_user.user_id=link.source_user_id
            LEFT JOIN public.employees e ON e.employee_id=COALESCE(u.employee_id,source_user.employee_id)
            JOIN public.training_lesson_versions l ON l.lesson_version_id=a.lesson_version_id
            JOIN public.training_course_versions c ON c.course_version_id=l.course_version_id
            LEFT JOIN public.training_attempts t ON t.assignment_id=a.assignment_id
            LEFT JOIN public.training_attempt_objects o ON o.attempt_id=t.attempt_id
                  AND o.object_role='hire_approval'
            ORDER BY a.assignment_id, t.attempt_number DESC NULLS LAST
        """)).mappings().all()
        for row in training:
            status = ("passed" if row["outcome"] == "passed" else "failed") if row["attempt_status"] == "completed" else (
                "manual_review" if row["attempt_status"] == "under_review" else
                "draft" if row["attempt_status"] == "in_progress" else
                row["attempt_status"] or "not_started")
            result.append({"participant_id": row["participant_user_id"],
                "participant_name": row["participant_name"], "unit_id": row["unit_id"],
                "course_code": row["course_code"], "lesson_code": row["lesson_code"],
                "lesson_title": row["lesson_title"], "status": status,
                "attempt_id": str(row["attempt_id"]) if row["attempt_id"] is not None else None,
                "attempt_no": row["attempt_number"], "application_id": row["application_id"],
                "score": row["score"], "review_source": "manual" if row["score"] is not None else None,
                "auto_status": "unavailable", "due_at": None, "source_system": "training"})
    return [row for row in result if all(value in (None, "") or row.get(key) == value for key, value in filters.items())]


def attempt_history(conn, attempt_id: str) -> dict:
    row = conn.execute(select(attempts).where(attempts.c.id == attempt_id)).mappings().first()
    if row is None:
        raise HTTPException(404, "Попытка не найдена")
    history = conn.execute(select(attempts).where(and_(attempts.c.participant_id == row["participant_id"],
        attempts.c.lesson_code == row["lesson_code"])).order_by(attempts.c.attempt_no.desc())).mappings().all()
    events = conn.execute(select(review_events).where(review_events.c.attempt_id == attempt_id)
        .order_by(review_events.c.created_at, review_events.c.id)).mappings().all()
    return {"attempt": dict(row), "history": [dict(item) for item in history], "review_events": [dict(item) for item in events]}
