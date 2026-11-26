"""Atomically complete all pending photo and relative proposals for one employee."""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text

from app.personnel_files import service as files
from app.personnel_files.access import access
from app.security.personnel_card_edit import require_personnel_card_edit_for_person
from app.services import relative_change_request_service as relatives


def complete(user: dict, person_id: int, decisions: list[dict]) -> dict:
    if not decisions:
        raise HTTPException(422, "Выберите решения по всем заявкам сотрудника.")
    submitted = {(item["kind"], str(item["id"])): item for item in decisions}
    if len(submitted) != len(decisions):
        raise HTTPException(422, "Одна заявка указана несколько раз.")
    if any(item["action"] == "return" and not item["reason"].strip() for item in decisions):
        raise HTTPException(422, "Укажите пояснение для каждой возвращаемой заявки.")

    with files.engine.begin() as conn:
        person = conn.execute(text("SELECT person_id FROM public.persons WHERE person_id=:pid FOR NO KEY UPDATE"),
                              {"pid": person_id}).scalar_one_or_none()
        if person is None:
            raise HTTPException(404, "Сотрудник не найден.")
        photos = [dict(row) for row in conn.execute(text("""SELECT v.version_id AS id,v.revision
            FROM public.personnel_file_versions v JOIN public.personnel_file_sets s USING(set_id)
            WHERE s.person_id=:pid AND s.kind='photo' AND v.state='pending'"""),
            {"pid": person_id}).mappings()]
        requests = [dict(row) for row in conn.execute(text("""SELECT request_id AS id,revision
            FROM public.person_relative_change_requests
            WHERE person_id=:pid AND status='pending'"""), {"pid": person_id}).mappings()]
        if photos and not access(conn, user, person_id).reviewer:
            raise HTTPException(403, "Недостаточно прав для проверки фото сотрудника.")
        if requests:
            require_personnel_card_edit_for_person(user, person_id)
        current = {("photo", str(row["id"])): row["revision"] for row in photos}
        current.update({("relative", str(row["id"])): row["revision"] for row in requests})
        if set(submitted) != set(current) or any(
            item["expected_revision"] != current[key] for key, item in submitted.items()
        ):
            raise HTTPException(409, "Набор заявок изменился. Обновите карточку и перепроверьте все решения.")

        results = []
        for key in sorted(current):
            item = submitted[key]
            if key[0] == "photo":
                result = files.decide_participating(conn, user, key[1],
                    expected_revision=item["expected_revision"], action=item["action"], reason=item["reason"])
            else:
                result = relatives.decide_participating(conn, user, UUID(key[1]),
                    item["expected_revision"], item["action"], item["reason"])
            results.append({"kind": key[0], "id": key[1],
                "status": result["state"] if key[0] == "photo" else result["status"]})
        return {"person_id": person_id, "results": results}
