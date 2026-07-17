"""Personnel Application registration service (WP-PPR-APPLICANT-001B)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.db.engine import engine as default_engine
from app.domain.iin import IinValidationError, normalize_and_validate_iin
from app.personnel_applications.application.envelope_projection import sync_envelope_intended_projection
from app.personnel_applications.domain.errors import (
    ActiveEmployeeBlocksRegistrationError,
    PersonnelApplicationDuplicateActiveError,
    PersonnelApplicationValidationError,
    VacancyCheckGateError,
)
from app.personnel_applications.domain.models import PersonnelApplicationCreatePayload
from app.personnel_applications.domain.status import (
    APPLICATION_SOURCE_PAPER,
    REGISTRATION_INITIAL_STATUS,
    VACANCY_CHECK_CONFIRMED_VISUALLY,
)
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_MATERIALIZE_PPR,
    MaterializePprPayload,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.domain.models import (
    HR_RELATIONSHIP_CANDIDATE,
    HR_RELATIONSHIP_FORMER_EMPLOYEE,
)
from app.ppr.infrastructure.application_unit_of_work import PprApplicationUnitOfWork
from app.ppr.infrastructure.ppr_repository import SqlAlchemyPprRepository

CARD_HREF_TEMPLATE = "/directory/personnel/persons/{person_id}/card"


@dataclass(frozen=True, slots=True)
class RegistrationPreviewResult:
    iin: str
    person_exists: bool
    person_id: int | None
    full_name: str | None
    hr_relationship_context: str | None
    has_active_employee: bool
    has_active_application: bool
    active_application_id: int | None
    can_register: bool
    block_reason: str | None


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    person_id: int
    application_id: int
    action: str
    card_href: str


def build_card_href(person_id: int) -> str:
    return CARD_HREF_TEMPLATE.format(person_id=int(person_id))


def _person_has_active_employee(conn: Connection, person_id: int) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.employees e
            WHERE e.person_id = :person_id
              AND COALESCE(e.is_active, TRUE) = TRUE
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).first()
    return row is not None


def _find_person_by_iin(conn: Connection, iin: str) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT person_id, full_name, person_status
            FROM public.persons
            WHERE iin = :iin
              AND person_status = 'active'
            ORDER BY person_id ASC
            LIMIT 1
            """
        ),
        {"iin": iin},
    ).mappings().first()
    return dict(row) if row else None


def _load_hr_relationship_context(conn: Connection, person_id: int) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT hr_relationship_context
            FROM public.personnel_record_metadata
            WHERE person_id = :person_id
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    if row is None:
        return None
    value = str(row.get("hr_relationship_context") or "").strip()
    return value or None


def _infer_materialize_context(conn: Connection, person_id: int) -> str:
    context = _load_hr_relationship_context(conn, person_id)
    if context:
        return context
    row = conn.execute(
        text(
            """
            SELECT BOOL_OR(COALESCE(is_active, FALSE) = FALSE) AS has_former
            FROM public.employees
            WHERE person_id = :person_id
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    if row and row.get("has_former"):
        return HR_RELATIONSHIP_FORMER_EMPLOYEE
    return HR_RELATIONSHIP_CANDIDATE


def _insert_person(
    conn: Connection,
    *,
    full_name: str,
    iin: str,
    birth_date: date | None,
) -> int:
    suffix = uuid4().hex[:12]
    row = conn.execute(
        text(
            """
            INSERT INTO public.persons (
                full_name, iin, birth_date, match_key, person_status, source
            )
            VALUES (
                :full_name, :iin, :birth_date, :match_key, 'active', 'manual'
            )
            RETURNING person_id
            """
        ),
        {
            "full_name": full_name.strip(),
            "iin": iin,
            "birth_date": birth_date,
            "match_key": f"applicant:{suffix}",
        },
    ).mappings().one()
    return int(row["person_id"])


def _materialize_ppr_participating(
    conn: Connection,
    *,
    person_id: int,
    hr_relationship_context: str,
    actor_id: str,
) -> None:
    uow = PprApplicationUnitOfWork().bind_participating(conn)
    lifecycle = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    lifecycle.materialize_ppr_participating(
        uow,
        PprCommandEnvelope(
            command_id=f"personnel-application:materialize:{person_id}:{uuid4().hex[:8]}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id=actor_id,
            requested_at=datetime.now(UTC),
            person_id=person_id,
            payload=MaterializePprPayload(hr_relationship_context=hr_relationship_context),
        ),
    )


def _ensure_envelope_exists(
    conn: Connection,
    *,
    person_id: int,
    is_new_person: bool,
    actor_id: str,
) -> None:
    repo = SqlAlchemyPprRepository(conn)
    if repo.exists_envelope(person_id):
        return
    hr_context = HR_RELATIONSHIP_CANDIDATE if is_new_person else _infer_materialize_context(conn, person_id)
    _materialize_ppr_participating(
        conn,
        person_id=person_id,
        hr_relationship_context=hr_context,
        actor_id=actor_id,
    )


def preview_registration(
    conn: Connection,
    *,
    iin_raw: str,
) -> RegistrationPreviewResult:
    try:
        iin = normalize_and_validate_iin(iin_raw)
    except IinValidationError as exc:
        raise PersonnelApplicationValidationError(str(exc)) from exc

    person = _find_person_by_iin(conn, iin)
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)

    if person is None:
        return RegistrationPreviewResult(
            iin=iin,
            person_exists=False,
            person_id=None,
            full_name=None,
            hr_relationship_context=None,
            has_active_employee=False,
            has_active_application=False,
            active_application_id=None,
            can_register=True,
            block_reason=None,
        )

    person_id = int(person["person_id"])
    active = app_repo.get_active_by_person_id(person_id)
    has_active_employee = _person_has_active_employee(conn, person_id)
    block_reason: str | None = None
    can_register = True
    if has_active_employee:
        can_register = False
        block_reason = "ACTIVE_EMPLOYEE_BLOCKS_REGISTRATION"

    return RegistrationPreviewResult(
        iin=iin,
        person_exists=True,
        person_id=person_id,
        full_name=str(person.get("full_name") or "").strip() or None,
        hr_relationship_context=_load_hr_relationship_context(conn, person_id),
        has_active_employee=has_active_employee,
        has_active_application=active is not None,
        active_application_id=active.application_id if active else None,
        can_register=can_register,
        block_reason=block_reason,
    )


def register_personnel_application(
    conn: Connection,
    *,
    iin_raw: str,
    full_name: str | None,
    birth_date: date | None,
    application_received_at: date,
    vacancy_check_status: str,
    vacancy_checked_at: datetime | None,
    vacancy_checked_by_user_id: int | None,
    intended_org_group_id: int | None,
    intended_org_unit_id: int | None,
    intended_position_id: int | None,
    intended_employment_rate: Decimal | float | None,
    intended_vacancy_text: str | None,
    contact_mobile_phone: str | None,
    contact_email: str | None,
    hr_note: str | None,
    idempotency_key: str | None,
    registered_by_user_id: int,
    actor_id: str,
) -> RegistrationResult:
    try:
        iin = normalize_and_validate_iin(iin_raw)
    except IinValidationError as exc:
        raise PersonnelApplicationValidationError(str(exc)) from exc

    if vacancy_check_status != VACANCY_CHECK_CONFIRMED_VISUALLY:
        raise VacancyCheckGateError()

    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)

    if idempotency_key:
        existing = app_repo.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            sync_envelope_intended_projection(conn, existing.person_id)
            return RegistrationResult(
                person_id=existing.person_id,
                application_id=existing.application_id,
                action="opened_existing",
                card_href=build_card_href(existing.person_id),
            )

    person = _find_person_by_iin(conn, iin)
    is_new_person = person is None

    if is_new_person:
        if not full_name or not str(full_name).strip():
            raise PersonnelApplicationValidationError("full_name is required for a new person.")
        person_id = _insert_person(
            conn,
            full_name=str(full_name),
            iin=iin,
            birth_date=birth_date,
        )
        _ensure_envelope_exists(
            conn,
            person_id=person_id,
            is_new_person=True,
            actor_id=actor_id,
        )
    else:
        person_id = int(person["person_id"])
        if _person_has_active_employee(conn, person_id):
            raise ActiveEmployeeBlocksRegistrationError(person_id=person_id)
        _ensure_envelope_exists(
            conn,
            person_id=person_id,
            is_new_person=False,
            actor_id=actor_id,
        )

    active = app_repo.get_active_by_person_id(person_id)
    if active is not None:
        sync_envelope_intended_projection(conn, person_id)
        return RegistrationResult(
            person_id=person_id,
            application_id=active.application_id,
            action="opened_existing",
            card_href=build_card_href(person_id),
        )

    rate: Decimal | None = None
    if intended_employment_rate is not None:
        rate = Decimal(str(intended_employment_rate))

    checked_at = vacancy_checked_at
    if checked_at is None and vacancy_check_status == VACANCY_CHECK_CONFIRMED_VISUALLY:
        checked_at = datetime.now(UTC)

    payload = PersonnelApplicationCreatePayload(
        person_id=person_id,
        application_received_at=application_received_at,
        application_source=APPLICATION_SOURCE_PAPER,
        vacancy_check_status=vacancy_check_status,
        vacancy_checked_at=checked_at,
        vacancy_checked_by_user_id=vacancy_checked_by_user_id or registered_by_user_id,
        intended_org_group_id=intended_org_group_id,
        intended_org_unit_id=intended_org_unit_id,
        intended_position_id=intended_position_id,
        intended_employment_rate=rate,
        intended_vacancy_text=intended_vacancy_text,
        contact_mobile_phone=contact_mobile_phone,
        contact_email=contact_email,
        registered_by_user_id=registered_by_user_id,
        hr_note=hr_note,
        idempotency_key=idempotency_key,
        status=REGISTRATION_INITIAL_STATUS,
    )

    try:
        created = app_repo.create(payload)
    except PersonnelApplicationDuplicateActiveError as exc:
        sync_envelope_intended_projection(conn, person_id)
        return RegistrationResult(
            person_id=person_id,
            application_id=exc.application_id,
            action="opened_existing",
            card_href=build_card_href(person_id),
        )

    sync_envelope_intended_projection(conn, person_id)
    return RegistrationResult(
        person_id=person_id,
        application_id=created.application_id,
        action="created",
        card_href=build_card_href(person_id),
    )


def preview_registration_with_engine(
    *,
    iin_raw: str,
    db_engine: Engine | None = None,
) -> RegistrationPreviewResult:
    db = db_engine or default_engine
    with db.connect() as conn:
        return preview_registration(conn, iin_raw=iin_raw)


def register_personnel_application_with_engine(
    *,
    db_engine: Engine | None = None,
    **kwargs: Any,
) -> RegistrationResult:
    db = db_engine or default_engine
    with db.begin() as conn:
        return register_personnel_application(conn, **kwargs)
