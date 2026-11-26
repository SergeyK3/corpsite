"""Employee-owned proposals for adding or correcting a PPR relative."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from app.ppr.application.authorization import PersonnelCardEditAuthorizationAdapter
from app.ppr.application.command_models import (
    COMMAND_TYPE_MATERIALIZE_PPR,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.errors import PprNotMaterializedError
from app.ppr.domain.models import HR_RELATIONSHIP_EMPLOYED
from app.ppr.infrastructure.application_unit_of_work import PprApplicationUnitOfWork
from app.api.ppr_errors import map_ppr_mutation_error
from app.api.ppr_card_command_router import Relative
from app.db.models.personnel_migration import RELATIONSHIP_TYPES
from app.security.personnel_card_edit import has_personnel_card_edit, require_personnel_card_edit_for_person
from app.services.self_personal_card_access_service import SelfPersonalCardAccessService


def _self_person(user: dict) -> int:
    resolution = SelfPersonalCardAccessService().resolve_for_user(user)
    if resolution.status != "READY" or resolution.composite is None:
        raise HTTPException(403, "Личная карточка недоступна.")
    return int(resolution.composite.person_id)


def _relative(conn, person_id: int, relative_id: int):
    row = conn.execute(text("""SELECT relative_id,person_id,relationship_type,full_name,birth_date,
        birth_place,organization_name,residence_address,notes,lifecycle_status,updated_at
        FROM public.person_relatives WHERE relative_id=:rid AND person_id=:pid"""),
        {"rid": relative_id, "pid": person_id}).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Запись о родственнике не найдена.")
    return dict(row)


def _request(conn, request_id: UUID):
    row = conn.execute(text("SELECT * FROM public.person_relative_change_requests WHERE request_id=:rid FOR UPDATE"),
                       {"rid": str(request_id)}).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Заявка не найдена.")
    return dict(row)


def _event(conn, request_id: UUID, user: dict, action: str, detail: dict):
    conn.execute(text("""INSERT INTO public.person_relative_change_events(request_id,actor_id,action,detail)
        VALUES(:rid,:uid,:action,CAST(:detail AS jsonb))"""),
        {"rid": str(request_id), "uid": int(user["user_id"]), "action": action,
         "detail": json.dumps(detail, default=str, ensure_ascii=False)})


def _public(row: dict) -> dict:
    return {key: row.get(key) for key in ("request_id", "request_kind", "relative_id", "expected_updated_at", "proposed",
        "status", "revision", "submitted_at", "decided_at", "reason", "approved_relative_id")}


def _validate_addition(proposed: dict) -> None:
    if not str(proposed.get("full_name") or "").strip():
        raise HTTPException(422, "Укажите ФИО родственника.")
    if proposed.get("relationship_type") not in RELATIONSHIP_TYPES:
        raise HTTPException(422, "Выберите степень родства.")


def _ensure_ppr_envelope(conn, user: dict, person_id: int, request_id: UUID) -> None:
    uow = PprApplicationUnitOfWork().bind_participating(conn)
    if uow.envelopes.exists_envelope(person_id):
        return
    PprLifecycleApplicationService(
        authorization=PersonnelCardEditAuthorizationAdapter(user),
    ).materialize_ppr_participating(
        uow,
        PprCommandEnvelope(
            command_id=f"relative-request-{request_id}:materialize",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id=str(user["user_id"]),
            requested_at=datetime.now(UTC),
            person_id=person_id,
            payload=MaterializePprPayload(hr_relationship_context=HR_RELATIONSHIP_EMPLOYED),
            audit_source="EMPLOYEE_REQUEST_REVIEW",
        ),
    )


def list_mine(user: dict) -> list[dict]:
    person_id = _self_person(user)
    with engine.connect() as conn:
        rows = conn.execute(text("""SELECT * FROM public.person_relative_change_requests
            WHERE person_id=:pid AND submitted_by=:uid ORDER BY submitted_at DESC, request_id DESC"""),
            {"pid": person_id, "uid": int(user["user_id"])}).mappings().all()
    return [_public(dict(row)) for row in rows]


def submit(user: dict, relative_id: int, expected_updated_at: datetime, proposed: dict) -> dict:
    person_id = _self_person(user)
    request_id = uuid4()
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT person_id FROM public.persons WHERE person_id=:pid FOR NO KEY UPDATE"),
                         {"pid": person_id}).one()
            current = _relative(conn, person_id, relative_id)
            if current["lifecycle_status"] != "active" or current["updated_at"] != expected_updated_at:
                raise HTTPException(409, "Запись изменилась. Обновите карточку.")
            row = conn.execute(text("""INSERT INTO public.person_relative_change_requests
                (request_id,person_id,relative_id,expected_updated_at,proposed,status,submitted_by)
                VALUES(:rid,:pid,:relative_id,:expected,CAST(:proposed AS jsonb),'pending',:uid)
                RETURNING *"""), {"rid": str(request_id), "pid": person_id, "relative_id": relative_id,
                "expected": expected_updated_at, "proposed": json.dumps(proposed, ensure_ascii=False),
                "uid": int(user["user_id"])}).mappings().one()
            _event(conn, request_id, user, "submitted", {"current": current, "proposed": proposed})
        return _public(dict(row))
    except IntegrityError as exc:
        raise HTTPException(409, "По этой записи уже есть заявка на проверке.") from exc


def submit_addition(user: dict, proposed: dict) -> dict:
    person_id = _self_person(user)
    _validate_addition(proposed)
    request_id = uuid4()
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT person_id FROM public.persons WHERE person_id=:pid FOR NO KEY UPDATE"),
                         {"pid": person_id}).one()
            row = conn.execute(text("""INSERT INTO public.person_relative_change_requests
                (request_id,person_id,request_kind,proposed,status,submitted_by)
                VALUES(:rid,:pid,'addition',CAST(:proposed AS jsonb),'pending',:uid)
                RETURNING *"""), {"rid": str(request_id), "pid": person_id,
                "proposed": json.dumps(proposed, ensure_ascii=False),
                "uid": int(user["user_id"])}).mappings().one()
            _event(conn, request_id, user, "submitted", {"current": None, "proposed": proposed})
        return _public(dict(row))
    except IntegrityError as exc:
        raise HTTPException(409, "Новый родственник уже ожидает проверки кадровиком.") from exc


def resubmit(user: dict, request_id: UUID, expected_revision: int, expected_updated_at: datetime | None, proposed: dict) -> dict:
    person_id = _self_person(user)
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT person_id FROM public.persons WHERE person_id=:pid FOR NO KEY UPDATE"),
                         {"pid": person_id}).one()
            row = _request(conn, request_id)
            if row["person_id"] != person_id or row["submitted_by"] != int(user["user_id"]):
                raise HTTPException(404, "Заявка не найдена.")
            if row["status"] != "returned" or row["revision"] != expected_revision:
                raise HTTPException(409, "Заявка изменилась. Обновите карточку.")
            current = None
            if row["request_kind"] == "correction":
                if expected_updated_at is None:
                    raise HTTPException(422, "Укажите версию исправляемой записи.")
                current = _relative(conn, person_id, int(row["relative_id"]))
                if current["lifecycle_status"] != "active" or current["updated_at"] != expected_updated_at:
                    raise HTTPException(409, "Запись изменилась. Обновите карточку.")
            else:
                if expected_updated_at is not None:
                    raise HTTPException(422, "Для нового родственника версия записи не требуется.")
                _validate_addition(proposed)
            changed = conn.execute(text("""UPDATE public.person_relative_change_requests SET
                expected_updated_at=:expected,proposed=CAST(:proposed AS jsonb),status='pending',
                revision=revision+1,submitted_at=now(),decided_by=NULL,decided_at=NULL,reason=''
                WHERE request_id=:rid RETURNING *"""),
                {"rid": str(request_id), "expected": expected_updated_at,
                 "proposed": json.dumps(proposed, ensure_ascii=False)}).mappings().one()
            _event(conn, request_id, user, "resubmitted", {"current": current, "proposed": proposed})
            return _public(dict(changed))
    except IntegrityError as exc:
        raise HTTPException(409, "Заявка о родственнике уже находится на проверке.") from exc


def review_queue(user: dict) -> list[dict]:
    if not has_personnel_card_edit(user):
        raise HTTPException(403, "Недостаточно прав для проверки заявок.")
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(text("""SELECT r.*,p.full_name AS employee_name
            FROM public.person_relative_change_requests r JOIN public.persons p USING(person_id)
            WHERE r.status='pending' ORDER BY r.submitted_at, r.request_id LIMIT 200""")).mappings()]
        items = []
        for row in rows:
            try:
                require_personnel_card_edit_for_person(user, int(row["person_id"]))
            except HTTPException:
                continue
            items.append({**_public(row), "person_id": row["person_id"], "employee_name": row["employee_name"],
                          "current": _relative(conn, int(row["person_id"]), int(row["relative_id"]))
                          if row["request_kind"] == "correction" else {}})
        return items


def decide(user: dict, request_id: UUID, expected_revision: int, action: str, reason: str) -> dict:
    with engine.begin() as conn:
        target = conn.execute(text("SELECT person_id FROM public.person_relative_change_requests WHERE request_id=:rid"),
                              {"rid": str(request_id)}).scalar_one_or_none()
        if target is None:
            raise HTTPException(404, "Заявка не найдена.")
        conn.execute(text("SELECT person_id FROM public.persons WHERE person_id=:pid FOR NO KEY UPDATE"),
                     {"pid": target}).one()
        return decide_participating(conn, user, request_id, expected_revision, action, reason)


def decide_participating(conn, user: dict, request_id: UUID, expected_revision: int,
                         action: str, reason: str) -> dict:
    """Apply a relative decision inside a caller-owned transaction after the Person lock."""
    row = _request(conn, request_id)
    person_id = int(row["person_id"])
    require_personnel_card_edit_for_person(user, person_id)
    if row["status"] != "pending" or row["revision"] != expected_revision:
        raise HTTPException(409, "Решение устарело. Обновите очередь.")
    current = _relative(conn, person_id, int(row["relative_id"])) if row["request_kind"] == "correction" else None
    approved_id = None
    if action == "approve":
        if current is not None and (current["lifecycle_status"] != "active" or current["updated_at"] != row["expected_updated_at"]):
            raise HTTPException(409, "Запись о родственнике изменилась. Заявку нельзя применить.")
        proposed = Relative.model_validate(row["proposed"]).model_dump()
        adding = row["request_kind"] == "addition"
        envelope = PprCommandEnvelope(command_id=f"relative-request-{request_id}",
            command_type="PersonnelCardAddRelatives" if adding else "PersonnelCardSupersedeRelatives",
            actor_id=str(user["user_id"]), requested_at=datetime.now(UTC), person_id=person_id,
            payload=proposed if adding else {"record_id": int(row["relative_id"]),
                "expected_updated_at": row["expected_updated_at"], "replacement": proposed},
            audit_source="EMPLOYEE_REQUEST_REVIEW")
        try:
            _ensure_ppr_envelope(conn, user, person_id, request_id)
            section_service = PprSectionApplicationService(
                authorization=PersonnelCardEditAuthorizationAdapter(user),
                uow_factory=lambda: PprApplicationUnitOfWork().bind_participating(conn),
            )
            result = section_service.add_relative(envelope) if adding else section_service.supersede_relative(envelope)
        except PprNotMaterializedError as exc:
            raise HTTPException(409, "Личная карточка не подготовлена для изменения. Обновите очередь и повторите попытку.") from exc
        except Exception as exc:
            mapped = map_ppr_mutation_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        approved_id = result.section_record_id
        status = "approved"
    else:
        if not reason.strip():
            raise HTTPException(422, "Укажите пояснение для возврата.")
        status = "returned"
    updated = conn.execute(text("""UPDATE public.person_relative_change_requests SET status=:status,
        revision=revision+1,decided_by=:uid,decided_at=now(),reason=:reason,
        approved_relative_id=:approved_id WHERE request_id=:rid RETURNING *"""),
        {"rid": str(request_id), "status": status, "uid": int(user["user_id"]),
         "reason": reason.strip(), "approved_id": approved_id}).mappings().one()
    _event(conn, request_id, user, action, {"current": current, "proposed": row["proposed"],
        "reason": reason.strip(), "approved_relative_id": approved_id})
    return _public(dict(updated))
