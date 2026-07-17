"""Transfer accepted intake draft sections into PPR (WP-PPR-INTAKE-002)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_REVIEW_COMPLETED,
    APPLICATION_STATUS_UNDER_REVIEW,
)
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.personnel_intake.application.intake_mapper import (
    build_full_name,
    intake_command_id,
    map_education_records,
    map_employment_records,
    map_military_record,
    map_relative_records,
    map_training_records,
    parse_date_value,
)
from app.personnel_intake.application.review_service import load_intake_review_state
from app.personnel_intake.domain.errors import PersonnelIntakeTransferError
from app.personnel_intake.domain.models import IntakeTransferSnapshot
from app.personnel_intake.domain.review_status import (
    INTAKE_SECTION_CONTACTS,
    INTAKE_SECTION_EDUCATION,
    INTAKE_SECTION_EMPLOYMENT_BIOGRAPHY,
    INTAKE_SECTION_MILITARY,
    INTAKE_SECTION_PERSONAL,
    INTAKE_SECTION_RELATIVES,
    INTAKE_SECTION_REVIEW_ACCEPTED,
    INTAKE_SECTION_REVIEW_SKIPPED,
    INTAKE_SECTION_TRAINING,
    INTAKE_TRANSFER_STATUS_COMPLETED,
    INTAKE_TRANSFER_STATUS_FAILED,
    PPR_TRANSFER_SECTION_GENERAL,
)
from app.personnel_intake.infrastructure.review_repository import SqlAlchemyPersonnelIntakeReviewRepository
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ACTIVATE_PPR,
    COMMAND_TYPE_MATERIALIZE_PPR,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.results import (
    RESULT_STATUS_ALREADY_MATERIALIZED,
    RESULT_STATUS_COMMITTED,
    RESULT_STATUS_IDEMPOTENT_REPLAY,
    RESULT_STATUS_NO_OP,
)
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _transition_application_status(
    conn: Connection,
    *,
    application_id: int,
    new_status: str,
    now: datetime,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.personnel_applications
            SET status = :status, updated_at = :now
            WHERE application_id = :application_id
            """
        ),
        {"status": new_status, "now": now, "application_id": int(application_id)},
    )


def _section_status_map(sections) -> dict[str, str]:
    return {s.section_code: s.status for s in sections}


@dataclass(frozen=True, slots=True)
class IntakeTransferResult:
    application_id: int
    transfer: IntakeTransferSnapshot
    idempotent_replay: bool


def _ensure_ppr_ready(person_id: int, *, application_id: int, actor_id: str) -> list[str]:
    command_ids: list[str] = []
    lifecycle = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    mat_id = intake_command_id(application_id, "materialize")
    mat = lifecycle.materialize_ppr(
        PprCommandEnvelope(
            command_id=mat_id,
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id=actor_id,
            requested_at=_now_utc(),
            person_id=person_id,
            payload=MaterializePprPayload(hr_relationship_context=HR_RELATIONSHIP_CANDIDATE),
        )
    )
    command_ids.append(mat_id)
    if mat.status not in {
        RESULT_STATUS_COMMITTED,
        RESULT_STATUS_IDEMPOTENT_REPLAY,
        RESULT_STATUS_ALREADY_MATERIALIZED,
    }:
        raise PersonnelIntakeTransferError(
            f"Failed to materialize PPR: {mat.status}",
            code="PPR_MATERIALIZE_FAILED",
        )
    act_id = intake_command_id(application_id, "activate")
    act = lifecycle.activate_ppr(
        PprCommandEnvelope(
            command_id=act_id,
            command_type=COMMAND_TYPE_ACTIVATE_PPR,
            actor_id=actor_id,
            requested_at=_now_utc(),
            payload={},
            person_id=person_id,
        )
    )
    command_ids.append(act_id)
    if act.status not in {RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY, RESULT_STATUS_NO_OP}:
        raise PersonnelIntakeTransferError(
            f"Failed to activate PPR: {act.status}",
            code="PPR_ACTIVATE_FAILED",
        )
    return command_ids


def _transfer_general_and_contacts(
    conn: Connection,
    *,
    application_id: int,
    person_id: int,
    payload: dict,
) -> None:
    personal = payload.get("personal") or {}
    contacts = payload.get("contacts") or {}
    full_name = build_full_name(personal)
    birth_date = parse_date_value(personal.get("birth_date"))
    if full_name:
        conn.execute(
            text("UPDATE public.persons SET full_name = :full_name WHERE person_id = :person_id"),
            {"full_name": full_name, "person_id": int(person_id)},
        )
    if birth_date is not None:
        conn.execute(
            text("UPDATE public.persons SET birth_date = :birth_date WHERE person_id = :person_id"),
            {"birth_date": birth_date, "person_id": int(person_id)},
        )
    phone = str(contacts.get("mobile_phone") or "").strip() or None
    email = str(contacts.get("email") or "").strip() or None
    conn.execute(
        text(
            """
            UPDATE public.personnel_applications
            SET contact_mobile_phone = COALESCE(:phone, contact_mobile_phone),
                contact_email = COALESCE(:email, contact_email),
                updated_at = now()
            WHERE application_id = :application_id
            """
        ),
        {"phone": phone, "email": email, "application_id": int(application_id)},
    )


def _run_section_commands(
    *,
    person_id: int,
    application_id: int,
    actor_id: str,
    payload: dict,
    section_statuses: dict[str, str],
) -> tuple[list[str], list[str]]:
    section_service = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    transferred: list[str] = []
    command_ids: list[str] = []

    if section_statuses.get(INTAKE_SECTION_EDUCATION) == INTAKE_SECTION_REVIEW_ACCEPTED:
        for index, record in enumerate(map_education_records(payload.get("education") or [])):
            cmd_id = intake_command_id(application_id, "education", index)
            result = section_service.add_education(
                PprCommandEnvelope(
                    command_id=cmd_id,
                    command_type="AddEducationRecord",
                    actor_id=actor_id,
                    requested_at=_now_utc(),
                    payload=record,
                    person_id=person_id,
                )
            )
            command_ids.append(cmd_id)
            if result.status not in {RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY}:
                raise PersonnelIntakeTransferError(
                    f"Education transfer failed at index {index}: {result.status}",
                    code="TRANSFER_EDUCATION_FAILED",
                )
        transferred.append("education")

    if section_statuses.get(INTAKE_SECTION_TRAINING) == INTAKE_SECTION_REVIEW_ACCEPTED:
        for index, record in enumerate(map_training_records(payload.get("training") or [])):
            cmd_id = intake_command_id(application_id, "training", index)
            result = section_service.add_training(
                PprCommandEnvelope(
                    command_id=cmd_id,
                    command_type="AddTrainingRecord",
                    actor_id=actor_id,
                    requested_at=_now_utc(),
                    payload=record,
                    person_id=person_id,
                )
            )
            command_ids.append(cmd_id)
            if result.status not in {RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY}:
                raise PersonnelIntakeTransferError(
                    f"Training transfer failed at index {index}: {result.status}",
                    code="TRANSFER_TRAINING_FAILED",
                )
        transferred.append("training")

    if section_statuses.get(INTAKE_SECTION_RELATIVES) == INTAKE_SECTION_REVIEW_ACCEPTED:
        for index, record in enumerate(map_relative_records(payload.get("relatives") or [])):
            cmd_id = intake_command_id(application_id, "family", index)
            result = section_service.add_relative(
                PprCommandEnvelope(
                    command_id=cmd_id,
                    command_type="AddRelativeRecord",
                    actor_id=actor_id,
                    requested_at=_now_utc(),
                    payload=record,
                    person_id=person_id,
                )
            )
            command_ids.append(cmd_id)
            if result.status not in {RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY}:
                raise PersonnelIntakeTransferError(
                    f"Family transfer failed at index {index}: {result.status}",
                    code="TRANSFER_FAMILY_FAILED",
                )
        transferred.append("family")

    if section_statuses.get(INTAKE_SECTION_EMPLOYMENT_BIOGRAPHY) == INTAKE_SECTION_REVIEW_ACCEPTED:
        for index, record in enumerate(map_employment_records(payload.get("employment_biography") or [])):
            cmd_id = intake_command_id(application_id, "employment_biography", index)
            result = section_service.add_external_employment(
                PprCommandEnvelope(
                    command_id=cmd_id,
                    command_type="AddExternalEmploymentRecord",
                    actor_id=actor_id,
                    requested_at=_now_utc(),
                    payload=record,
                    person_id=person_id,
                )
            )
            command_ids.append(cmd_id)
            if result.status not in {RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY}:
                raise PersonnelIntakeTransferError(
                    f"Employment biography transfer failed at index {index}: {result.status}",
                    code="TRANSFER_EMPLOYMENT_FAILED",
                )
        transferred.append("employment_biography")

    if section_statuses.get(INTAKE_SECTION_MILITARY) == INTAKE_SECTION_REVIEW_ACCEPTED:
        cmd_id = intake_command_id(application_id, "military", 0)
        result = section_service.create_military_service(
            PprCommandEnvelope(
                command_id=cmd_id,
                command_type="CreateMilitaryServiceRecord",
                actor_id=actor_id,
                requested_at=_now_utc(),
                payload=map_military_record(payload.get("military") or {}),
                person_id=person_id,
            )
        )
        command_ids.append(cmd_id)
        if result.status not in {RESULT_STATUS_COMMITTED, RESULT_STATUS_IDEMPOTENT_REPLAY}:
            raise PersonnelIntakeTransferError(
                f"Military transfer failed: {result.status}",
                code="TRANSFER_MILITARY_FAILED",
            )
        transferred.append("military")

    return transferred, command_ids


def transfer_intake_to_ppr(
    conn: Connection,
    *,
    application_id: int,
    transferred_by_user_id: int,
    actor_id: str,
) -> IntakeTransferResult:
    review_state = load_intake_review_state(conn, application_id)
    review_repo = SqlAlchemyPersonnelIntakeReviewRepository(conn)
    existing = review_repo.get_transfer(application_id)
    if existing is not None and existing.status == INTAKE_TRANSFER_STATUS_COMPLETED:
        return IntakeTransferResult(
            application_id=application_id,
            transfer=existing,
            idempotent_replay=True,
        )

    if not review_state.can_transfer:
        raise PersonnelIntakeTransferError(
            review_state.transfer_blocked_reason or "Transfer is not allowed.",
            code="TRANSFER_NOT_ALLOWED",
        )

    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.require_by_id(application_id)
    if app.status not in {APPLICATION_STATUS_UNDER_REVIEW, APPLICATION_STATUS_REVIEW_COMPLETED}:
        raise PersonnelIntakeTransferError(
            f"Application status {app.status} does not allow transfer.",
            code="TRANSFER_INVALID_STATUS",
        )

    now = _now_utc()
    if existing is None:
        review_repo.ensure_transfer_row(application_id, now=now)
    elif existing.status == INTAKE_TRANSFER_STATUS_FAILED:
        review_repo.reset_transfer_for_retry(application_id, now=now)

    section_statuses = _section_status_map(review_state.sections)
    payload = review_state.draft.payload
    all_command_ids: list[str] = []
    transferred_sections: list[str] = []

    try:
        lifecycle_ids = _ensure_ppr_ready(app.person_id, application_id=application_id, actor_id=actor_id)
        all_command_ids.extend(lifecycle_ids)

        personal_ok = section_statuses.get(INTAKE_SECTION_PERSONAL) == INTAKE_SECTION_REVIEW_ACCEPTED
        contacts_ok = section_statuses.get(INTAKE_SECTION_CONTACTS) == INTAKE_SECTION_REVIEW_ACCEPTED
        if personal_ok or contacts_ok:
            _transfer_general_and_contacts(
                conn,
                application_id=application_id,
                person_id=app.person_id,
                payload=payload,
            )
            transferred_sections.append(PPR_TRANSFER_SECTION_GENERAL)
            all_command_ids.append(intake_command_id(application_id, "general", 0))

        section_transferred, section_command_ids = _run_section_commands(
            person_id=app.person_id,
            application_id=application_id,
            actor_id=actor_id,
            payload=payload,
            section_statuses=section_statuses,
        )
        transferred_sections.extend(section_transferred)
        all_command_ids.extend(section_command_ids)

        # Record skipped sections in audit metadata only (no PPR writes).
        for code, status in section_statuses.items():
            if status == INTAKE_SECTION_REVIEW_SKIPPED:
                transferred_sections.append(f"skipped:{code}")

        transfer = review_repo.mark_transfer_completed(
            application_id,
            transferred_by_user_id=transferred_by_user_id,
            transferred_at=now,
            sections_transferred=sorted(set(transferred_sections)),
            command_ids=all_command_ids,
        )
        _transition_application_status(
            conn,
            application_id=application_id,
            new_status=APPLICATION_STATUS_REVIEW_COMPLETED,
            now=now,
        )
        return IntakeTransferResult(
            application_id=application_id,
            transfer=transfer,
            idempotent_replay=False,
        )
    except Exception as exc:
        review_repo.mark_transfer_failed(
            application_id,
            transferred_by_user_id=transferred_by_user_id,
            failed_at=now,
            sections_transferred=transferred_sections,
            command_ids=all_command_ids,
            error_message=str(exc),
        )
        if isinstance(exc, PersonnelIntakeTransferError):
            raise
        raise PersonnelIntakeTransferError(str(exc), code="TRANSFER_FAILED") from exc


def list_intake_transfer_audit(
    conn: Connection,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[IntakeTransferSnapshot]:
    review_repo = SqlAlchemyPersonnelIntakeReviewRepository(conn)
    return review_repo.list_transfers(limit=limit, offset=offset)
