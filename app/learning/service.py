"""Learning pilot state and progress. All decisions use saved records, never client claims."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, delete, func, insert, select, update

from app.learning import expert_service, hire_bridge
from app.learning.catalog import COURSE
from app.learning.model import attempts, criterion_results, exercise_applications, hire_applications, records, review_events, screenshot_slots, screenshots


def unit(user: dict) -> int:
    value = user.get("unit_id")
    if value is None:
        raise HTTPException(403, "Учебное отделение не определено")
    return int(value)


def record_action(conn, user: dict, application_ref: str, action: str, detail: str = "") -> dict:
    ref = application_ref.strip()
    if not ref.startswith("LEARN-") or len(ref) > 100:
        raise HTTPException(422, "Нужен номер изолированного учебного заявления LEARN-…")
    if action not in {"opened", "approved", "rejected", "visa_viewed", "submitted"}:
        raise HTTPException(422, "Неизвестное учебное действие")
    uid = int(user["user_id"])
    prior = conn.execute(select(records).where(and_(records.c.participant_id == uid, records.c.unit_id == unit(user), records.c.application_ref == ref)).order_by(records.c.created_at, records.c.id)).mappings().all()
    actions = {row["action"] for row in prior}
    if action in {"approved", "rejected"} and ("opened" not in actions or actions & {"approved", "rejected"}):
        raise HTTPException(422, "Сначала откройте отдельное учебное заявление")
    if action == "visa_viewed" and not actions & {"approved", "rejected"}:
        raise HTTPException(422, "Для истории виз нужен сохранённый учебный результат")
    if action == "rejected" and not detail.strip():
        raise HTTPException(422, "Для возражения нужна причина")
    rid = str(uuid4())
    conn.execute(insert(records).values(id=rid, participant_id=uid, unit_id=unit(user), application_ref=ref, action=action, detail=detail.strip()))
    return {"id": rid, "application_ref": ref, "action": action}


def start_attempt(conn, user: dict, lesson_code: str, record_id: str) -> dict:
    lesson = expert_service.lesson(conn, lesson_code)
    assigned = {item["code"] for item in expert_service.assigned_lessons(conn, int(user["user_id"]), unit(user), user.get("role_code"))}
    if lesson_code not in assigned:
        raise HTTPException(404, "Занятие не назначено")
    if lesson_code == "resolution_2":
        raise HTTPException(409, "Для этого занятия начните попытку из карточки: учебное заявление создаётся автоматически")
    uid = int(user["user_id"])
    record = conn.execute(select(records).where(records.c.id == record_id)).mappings().first()
    if record is None or record["participant_id"] != uid or record["unit_id"] != unit(user):
        raise HTTPException(404, "Учебная запись не найдена")
    if record["action"] != lesson["expected_action"]:
        raise HTTPException(422, "Учебная запись не подтверждает действие занятия")
    existing = conn.execute(select(attempts).where(and_(attempts.c.participant_id == uid, attempts.c.unit_id == unit(user), attempts.c.lesson_code == lesson_code)).order_by(attempts.c.attempt_no.desc())).mappings().all()
    if existing and existing[0]["status"] in {"draft", "manual_review"}:
        raise HTTPException(409, "Предыдущая попытка ожидает проверки")
    attempt_id = str(uuid4())
    attempt_no = int(existing[0]["attempt_no"]) + 1 if existing else 1
    conn.execute(insert(attempts).values(id=attempt_id, participant_id=uid, unit_id=unit(user), lesson_code=lesson_code, record_id=record_id, attempt_no=attempt_no, status="draft",
                                        lesson_snapshot_json=json.dumps(lesson, ensure_ascii=False)))
    return {"id": attempt_id, "attempt_no": attempt_no, "status": "draft"}


def start_hire_attempt(conn, user: dict, lesson_code: str) -> dict:
    lesson = expert_service.lesson(conn, lesson_code)
    if not hire_bridge.is_hire_lesson(lesson):
        raise HTTPException(404, "Для занятия нет кадровой формы")
    uid, unit_id = int(user["user_id"]), unit(user)
    if lesson_code not in {item["code"] for item in expert_service.assigned_lessons(conn, uid, unit_id, user.get("role_code"))}:
        raise HTTPException(404, "Занятие не назначено")
    latest = conn.execute(select(attempts).where(and_(
        attempts.c.participant_id == uid, attempts.c.unit_id == unit_id,
        attempts.c.lesson_code == lesson_code)).order_by(attempts.c.attempt_no.desc())).mappings().first()
    if latest and latest["status"] == "draft":
        return {"id": latest["id"], "attempt_no": latest["attempt_no"], "status": "draft"}
    if latest and latest["status"] == "manual_review":
        raise HTTPException(409, "Попытка ожидает проверки")
    ref = f"LEARN-HIRE-{uid}-{uuid4().hex[:12]}"
    record = record_action(conn, user, ref, "submitted")
    return start_attempt(conn, user, lesson_code, record["id"])


def approval_exercise(conn, user: dict, attempt_id: str) -> dict:
    row = conn.execute(select(exercise_applications, attempts.c.attempt_no, attempts.c.status.label("attempt_status"))
        .join(attempts, exercise_applications.c.attempt_id == attempts.c.id)
        .where(exercise_applications.c.attempt_id == attempt_id)).mappings().first()
    if row is None or row["participant_id"] != int(user["user_id"]) or row["unit_id"] != unit(user):
        raise HTTPException(404, "Учебное заявление не найдено")
    return dict(row)


def start_approval_exercise(conn, user: dict) -> dict:
    uid, unit_id = int(user["user_id"]), unit(user)
    if "resolution_2" not in {item["code"] for item in expert_service.assigned_lessons(conn, uid, unit_id, user.get("role_code"))}:
        raise HTTPException(404, "Занятие не назначено")
    latest = conn.execute(select(attempts).where(and_(attempts.c.participant_id == uid,
        attempts.c.unit_id == unit_id, attempts.c.lesson_code == "resolution_2"))
        .order_by(attempts.c.attempt_no.desc())).mappings().first()
    if latest and latest["status"] in {"draft", "manual_review"}:
        return approval_exercise(conn, user, latest["id"])
    attempt_no = int(latest["attempt_no"]) + 1 if latest else 1
    ref = f"LEARN-APP-{unit_id}-{uid}-{attempt_no}"
    opened_id = record_action(conn, user, ref, "opened")["id"]
    attempt_id = str(uuid4())
    conn.execute(insert(attempts).values(id=attempt_id, participant_id=uid, unit_id=unit_id,
        lesson_code="resolution_2", record_id=opened_id, attempt_no=attempt_no, status="draft"))
    fictional_names = ("Учебная Анна Сергеевна", "Примеров Алексей Иванович", "Учебная Мария Павловна")
    conn.execute(insert(exercise_applications).values(id=str(uuid4()), attempt_id=attempt_id,
        participant_id=uid, unit_id=unit_id, application_ref=ref,
        candidate_name=fictional_names[(uid + attempt_no) % len(fictional_names)],
        position_title="Врач отделения", employment_fraction="0,50", start_date="15.12.2026",
        status="awaiting_consent"))
    return approval_exercise(conn, user, attempt_id)


def save_approval_consent(conn, user: dict, attempt_id: str) -> dict:
    exercise = approval_exercise(conn, user, attempt_id)
    if exercise["status"] == "approved":
        return exercise
    if exercise["attempt_status"] != "draft":
        raise HTTPException(409, "Решение по отправленной попытке менять нельзя")
    approved_id = record_action(conn, user, exercise["application_ref"], "approved")["id"]
    conn.execute(update(attempts).where(attempts.c.id == attempt_id).values(record_id=approved_id))
    conn.execute(update(exercise_applications).where(exercise_applications.c.attempt_id == attempt_id)
        .values(status="approved", approved_at=func.now()))
    return approval_exercise(conn, user, attempt_id)


def owned_attempt(conn, user: dict, attempt_id: str) -> dict:
    row = conn.execute(select(attempts).where(attempts.c.id == attempt_id)).mappings().first()
    if row is None or row["participant_id"] != int(user["user_id"]) or row["unit_id"] != unit(user):
        raise HTTPException(404, "Попытка не найдена")
    return dict(row)


def lesson_for_attempt(conn, attempt: dict) -> dict:
    snapshot = attempt.get("lesson_snapshot_json")
    return json.loads(snapshot) if snapshot else expert_service.lesson(conn, attempt["lesson_code"], include_draft=True)


def attach_screenshot(conn, user: dict, attempt_id: str, *, key: str, mime: str, checksum: str, size: int, slot: int | None = None) -> dict:
    attempt = owned_attempt(conn, user, attempt_id)
    if attempt["status"] != "draft":
        raise HTTPException(409, "Попытка уже отправлена")
    if attempt["lesson_code"] == "resolution_2" and slot is None:
        raise HTTPException(422, "Укажите поле снимка")
    if slot is not None:
        if slot < 0 or slot >= len(lesson_for_attempt(conn, attempt)["screenshots"]):
            raise HTTPException(422, "Неизвестное поле снимка")
        existing = conn.execute(select(screenshot_slots.c.screenshot_id).where(and_(
            screenshot_slots.c.attempt_id == attempt_id, screenshot_slots.c.slot == slot))).scalar()
        if existing:
            raise HTTPException(409, "Снимок для этого поля уже загружен")
    sid = str(uuid4())
    conn.execute(insert(screenshots).values(id=sid, attempt_id=attempt_id, participant_id=attempt["participant_id"], record_id=attempt["record_id"], storage_key=key, mime=mime, checksum=checksum, bytes=size))
    if slot is not None:
        conn.execute(insert(screenshot_slots).values(screenshot_id=sid, attempt_id=attempt_id, slot=slot))
    return {"id": sid, "attempt_id": attempt_id, "participant_id": attempt["participant_id"], "record_id": attempt["record_id"], "slot": slot}


def submit_attempt(conn, user: dict, attempt_id: str) -> dict:
    attempt = owned_attempt(conn, user, attempt_id)
    lesson = lesson_for_attempt(conn, attempt)
    hire_link = None
    if hire_bridge.is_hire_lesson(lesson):
        hire_link = conn.execute(select(hire_applications).where(
            hire_applications.c.attempt_id == attempt_id)).mappings().first()
        if hire_link is None:
            raise HTTPException(422, "Сначала сохраните заявление")
    if attempt["status"] != "draft":
        raise HTTPException(409, "Попытка уже отправлена")
    if attempt["lesson_code"] in expert_service.STEP_BY_CODE:
        from app.learning import hire_path_rehearsal
        hire_path_rehearsal.validate_step_submission(conn, user, attempt_id)
    if attempt["lesson_code"] == "resolution_2":
        exercise = approval_exercise(conn, user, attempt_id)
        if exercise["status"] != "approved":
            raise HTTPException(422, "Сначала сохраните согласие по учебному заявлению этой попытки")
        action = conn.execute(select(records.c.action).where(records.c.id == attempt["record_id"])).scalar_one()
        if action != "approved":
            raise HTTPException(422, "Сохранённое согласие не подтверждено учебной записью")
        slots = set(conn.execute(select(screenshot_slots.c.slot).where(screenshot_slots.c.attempt_id == attempt_id)).scalars().all())
        if slots != {0, 1}:
            raise HTTPException(422, "Приложите резолюцию и карточку статуса в отдельные поля")
    count = conn.execute(select(func.count()).select_from(screenshots).where(screenshots.c.attempt_id == attempt_id)).scalar_one()
    if count < len(lesson["screenshots"]):
        raise HTTPException(422, "Приложите все снимки, перечисленные в карточке")
    # Image meaning and criteria are not evaluated by this pilot.
    conn.execute(update(attempts).where(attempts.c.id == attempt_id).values(status="manual_review", pre_score=None, pre_required=None))
    if hire_link is not None:
        try:
            marks, note = hire_bridge.evaluate(hire_link["application_id"], attempt_id,
                                                json.loads(hire_link["fixture_json"]))
        except Exception as exc:
            automatic_failure(conn, attempt_id, f"Автоматическая проверка недоступна: {exc}")
            return {"id": attempt_id, "status": "manual_review", "auto_status": "failed"}
        return automatic_result(conn, attempt_id, marks, note)
    return {"id": attempt_id, "status": "manual_review", "preliminary_score": None, "preliminary_required": None,
            "reason": "Содержание снимка и результат требуют подтверждения проверяющего"}


def save_final_result(conn, attempt_id: str, score: int, required_met: bool, note: str,
                      criteria: list[bool] | None, *, source: str, actor_id: int | None,
                      allow_correction: bool = False, reason: str = "") -> dict:
    row = conn.execute(select(attempts).where(attempts.c.id == attempt_id)).mappings().first()
    if row is None:
        raise HTTPException(404, "Попытка не найдена")
    if row["status"] not in {"manual_review", "passed", "failed"}:
        raise HTTPException(409, "Работа ещё не отправлена на проверку")
    lesson = lesson_for_attempt(conn, row)
    if not 0 <= score <= len(lesson["criteria"]):
        raise HTTPException(422, "Оценка вне шкалы занятия")
    if criteria is None and lesson["expected_action"] == "submitted":
        raise HTTPException(422, "Отметьте каждый критерий занятия")
    if criteria is not None:
        if len(criteria) != len(lesson["criteria"]) or criteria[lesson["criteria"].index(lesson["required"])] != required_met:
            raise HTTPException(422, "Проверка критериев не совпадает с обязательным критерием")
        if sum(criteria) != score:
            raise HTTPException(422, "Баллы должны совпадать с числом выполненных критериев")
    passed = score >= 3 and required_met
    if passed and hire_bridge.is_hire_lesson(lesson) and lesson.get("guide_url") == hire_bridge.GUIDE_URL:
        link = conn.execute(select(hire_applications).where(
            hire_applications.c.attempt_id == attempt_id)).mappings().first()
        if link is None or not hire_bridge.application(link["application_id"], attempt_id).get("application_id"):
            raise HTTPException(422, "Для зачёта нужно сохранённое заявление с номером")
    new_status = "passed" if passed else "failed"
    prior_marks = conn.execute(select(criterion_results.c.met).where(criterion_results.c.attempt_id == attempt_id)
        .order_by(criterion_results.c.criterion_no)).scalars().all()
    same_source = row["review_source"] == source or (row["review_source"] is None and not allow_correction)
    if row["status"] in {"passed", "failed"} and row["score"] == score and row["required_met"] == required_met and same_source and row["review_note"] == note.strip() and (criteria is None or prior_marks == criteria):
        return {"id": attempt_id, "status": row["status"], "score": score, "required_met": required_met}
    if row["status"] in {"passed", "failed"}:
        if not allow_correction:
            raise HTTPException(409, "Итоговая оценка уже сохранена; для исправления используйте изменение оценки")
        if not reason.strip():
            raise HTTPException(422, "Укажите основание пересмотра оценки")
    conn.execute(delete(criterion_results).where(criterion_results.c.attempt_id == attempt_id))
    if criteria is not None:
        conn.execute(insert(criterion_results), [{"attempt_id": attempt_id, "criterion_no": index, "met": met} for index, met in enumerate(criteria)])
    conn.execute(update(attempts).where(attempts.c.id == attempt_id).values(status=new_status, score=score,
        required_met=required_met, reviewer_id=actor_id, reviewed_at=func.now(), review_note=note.strip(),
        review_source=source, auto_status="complete" if source == "automatic" else row["auto_status"],
        auto_note=note.strip() if source == "automatic" else row["auto_note"]))
    conn.execute(insert(review_events).values(id=str(uuid4()), attempt_id=attempt_id, source=source,
        old_status=row["status"], old_score=row["score"], new_status=new_status, new_score=score,
        criteria_json=json.dumps(criteria or []), note=note.strip(), reason=reason.strip(), actor_id=actor_id,
        created_at=datetime.now(timezone.utc)))
    return {"id": attempt_id, "status": new_status, "score": score, "required_met": required_met}


def review_attempt(conn, user: dict, attempt_id: str, score: int, required_met: bool, note: str = "",
                   criteria: list[bool] | None = None, *, allow_correction: bool = False, reason: str = "") -> dict:
    if not user.get("has_learning_review"):
        raise HTTPException(403, "Нет разрешения на ручную проверку обучения")
    row = conn.execute(select(attempts.c.participant_id).where(attempts.c.id == attempt_id)).mappings().first()
    if row is None:
        raise HTTPException(404, "Попытка не найдена")
    if row["participant_id"] == int(user["user_id"]):
        raise HTTPException(403, "Свою работу проверять нельзя")
    link = conn.execute(select(hire_applications).where(hire_applications.c.attempt_id == attempt_id)).mappings().first()
    if link is not None:
        saved = hire_bridge.application(link["application_id"], attempt_id)
        if not saved.get("application_id"):
            raise HTTPException(422, "У заявления нет номера")
        if criteria is not None and (not criteria or not criteria[0]):
            raise HTTPException(422, "Сохранённое заявление удовлетворяет обязательному критерию")
    return save_final_result(conn, attempt_id, score, required_met, note, criteria, source="manual",
                             actor_id=int(user["user_id"]), allow_correction=allow_correction, reason=reason)


def automatic_result(conn, attempt_id: str, criteria: list[bool], note: str = "") -> dict:
    row = conn.execute(select(attempts).where(attempts.c.id == attempt_id)).mappings().first()
    if row is None:
        raise HTTPException(404, "Попытка не найдена")
    item = lesson_for_attempt(conn, row)
    if len(criteria) != len(item["criteria"]):
        raise HTTPException(422, "Нужен результат для каждого критерия")
    return save_final_result(conn, attempt_id, sum(criteria), criteria[item["criteria"].index(item["required"])],
                             note, criteria, source="automatic", actor_id=None)


def automatic_failure(conn, attempt_id: str, note: str) -> dict:
    row = conn.execute(select(attempts).where(attempts.c.id == attempt_id)).mappings().first()
    if row is None:
        raise HTTPException(404, "Попытка не найдена")
    if row["status"] != "manual_review":
        raise HTTPException(409, "Попытка не ожидает проверки")
    conn.execute(update(attempts).where(attempts.c.id == attempt_id).values(auto_status="failed", auto_note=note.strip()))
    return {"id": attempt_id, "status": "manual_review", "auto_status": "failed"}


def progress(conn, participant_id: int, unit_id: int, role_code: str | None = None) -> dict:
    assigned_items = expert_service.assigned_lessons(conn, participant_id, unit_id, role_code)
    rows = conn.execute(select(attempts).where(and_(attempts.c.participant_id == participant_id, attempts.c.unit_id == unit_id)).order_by(attempts.c.attempt_no)).mappings().all()
    latest_attempt = {row["lesson_code"]: row for row in rows}
    latest_result = {row["lesson_code"]: row for row in rows if row["status"] in {"passed", "failed"}}
    best_passed = {}
    for row in rows:
        if row["status"] == "passed" and row["score"] is not None and row["score"] >= 3 and row["required_met"]:
            current = best_passed.get(row["lesson_code"])
            if current is None or row["score"] >= current["score"]:
                best_passed[row["lesson_code"]] = row
    def aggregate(items):
        points = sum(int(best_passed[lesson["code"]]["score"]) for lesson in items if lesson["code"] in best_passed)
        passed = sum(lesson["code"] in best_passed for lesson in items)
        pending = sum(latest_attempt.get(lesson["code"], {}).get("status") == "manual_review" for lesson in items)
        return {"points": points, "maximum": len(items) * 5, "passed": passed, "pending": pending, "total": len(items)}
    skills = {}
    functions = {}
    for lesson in assigned_items:
        skills.setdefault(lesson["skill"], []).append(lesson)
        functions.setdefault(lesson["function"], []).append(lesson)
    course_groups = {}
    for item in assigned_items:
        course_groups.setdefault(item["course_code"], []).append(item)
    course_lookup = {item["code"]: item for item in expert_service.all_courses(conn, include_drafts=True)}
    course_list = []
    for code, items in course_groups.items():
        subtotal = aggregate(items)
        subtotal["average"] = round(subtotal["points"] / len(items), 2) if subtotal["passed"] == len(items) else None
        course_list.append({**course_lookup[code], **subtotal})
    course = course_list[0] if len(course_list) == 1 else {"code": "all", "title": "Все назначения", **aggregate(assigned_items), "average": None}
    lessons = {}
    for lesson in assigned_items:
        code = lesson["code"]
        current = latest_attempt.get(code)
        best = best_passed.get(code)
        result = best or latest_result.get(code)
        status = current["status"] if current else "not_started"
        if status == "failed" and best:
            status = "passed"
        display_score = best["score"] if status == "passed" and best else current["score"] if current and current["status"] == "failed" else None
        lessons[code] = {"status": status, "score": display_score,
                         "review_source": (best["review_source"] if best else None) if status == "passed" else
                                          (current["review_source"] if current else None) if status == "failed" else None,
                         "best_score": best["score"] if best else None, "maximum": 5,
                         "attempt_id": current["id"] if current else None,
                         "result_attempt_id": result["id"] if result else None,
                         "attempt_no": current["attempt_no"] if current else None}
    return {"course": course, "courses": course_list, "skills": {name: aggregate(items) for name, items in skills.items()},
            "functions": {name: aggregate(items) for name, items in functions.items()}, "lessons": lessons}
