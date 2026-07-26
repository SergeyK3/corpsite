"""Complete personnel application after HIRE order apply (WP-PPR-APPLICANT-003)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.db.models.personnel_orders import ORDER_TYPE_HIRE
from app.personnel_applications.application.envelope_projection import sync_envelope_intended_projection
from app.personnel_applications.domain.errors import PersonnelApplicationApplyError
from app.personnel_applications.domain.models import ApplicationApplyResult
from app.personnel_applications.domain.status import (
    APPLICATION_STATUS_APPROVED,
    APPLICATION_STATUS_COMPLETED,
    APPLICATION_STATUS_ORDER_DRAFT_CREATED,
    DIRECTOR_RESOLUTION_APPROVED,
)
from app.personnel_applications.infrastructure.repository import SqlAlchemyPersonnelApplicationRepository
from app.services.personnel_order_archive_guard import PersonnelOrderArchivedError
from app.services.personnel_order_hire_apply_readiness import (
    validate_authoritative_hire_target,
    validate_hire_order_ready_for_apply_readonly,
)
from app.services.personnel_orders_apply_service import (
    APPLYABLE_ORDER_STATUSES,
    PersonnelOrderAlreadyAppliedError,
    apply_personnel_order_in_conn,
)
from app.services.personnel_orders_query_service import PersonnelOrderValidationError


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _count_linked_events(conn: Connection, order_id: int) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.employee_events
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id)},
        ).scalar_one()
    )


def _resolve_hire_employee_id_for_order(conn: Connection, order_id: int) -> int | None:
    row = conn.execute(
        text(
            """
            SELECT ee.employee_id
            FROM public.employee_events ee
            WHERE ee.order_id = :order_id
              AND ee.event_type = 'HIRE'
            ORDER BY ee.event_id ASC
            LIMIT 1
            """
        ),
        {"order_id": int(order_id)},
    ).mappings().first()
    if row is None or row.get("employee_id") is None:
        return None
    return int(row["employee_id"])


def _load_order_row(conn: Connection, order_id: int) -> dict:
    row = conn.execute(
        text(
            """
            SELECT order_id, order_type_code, status, order_number, order_date
            FROM public.personnel_orders
            WHERE order_id = :order_id
            LIMIT 1
            """
        ),
        {"order_id": int(order_id)},
    ).mappings().first()
    if row is None:
        raise PersonnelApplicationApplyError(
            f"Personnel order not found: order_id={order_id}",
            code="ORDER_NOT_FOUND",
        )
    return dict(row)


def _person_has_active_employee(conn: Connection, person_id: int) -> int | None:
    row = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.employees
            WHERE person_id = :person_id
              AND is_active = TRUE
            ORDER BY employee_id ASC
            LIMIT 1
            """
        ),
        {"person_id": int(person_id)},
    ).mappings().first()
    if row is None:
        return None
    return int(row["employee_id"])


def _validate_application_can_apply(
    conn: Connection,
    *,
    application_id: int,
    allow_completed: bool = False,
) -> tuple:
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.require_by_id(application_id)

    if app.status == APPLICATION_STATUS_COMPLETED:
        if allow_completed:
            return app, None
        raise PersonnelApplicationApplyError(
            "Application is already completed.",
            code="APPLICATION_ALREADY_COMPLETED",
        )

    if app.status not in {APPLICATION_STATUS_APPROVED, APPLICATION_STATUS_ORDER_DRAFT_CREATED}:
        raise PersonnelApplicationApplyError(
            f"Apply is only allowed after approval with linked HIRE order (status={app.status}).",
            code="APPLY_NOT_ALLOWED",
        )

    if app.director_resolution_status != DIRECTOR_RESOLUTION_APPROVED:
        raise PersonnelApplicationApplyError(
            "Director resolution must be approved before apply.",
            code="DIRECTOR_RESOLUTION_REQUIRED",
        )

    if app.personnel_order_id is None:
        raise PersonnelApplicationApplyError(
            "Application has no linked personnel order.",
            code="ORDER_NOT_LINKED",
        )

    order = _load_order_row(conn, int(app.personnel_order_id))
    if str(order["order_type_code"]) != ORDER_TYPE_HIRE:
        raise PersonnelApplicationApplyError(
            "Linked personnel order must be HIRE.",
            code="ORDER_NOT_HIRE",
        )

    return app, order


def validate_linked_application_for_order_hire_precheck(
    conn: Connection,
    application_id: int,
) -> None:
    """Read-only linked application gate for order-side HIRE pre-check."""
    try:
        _validate_application_can_apply(conn, application_id=application_id)
    except PersonnelApplicationApplyError as exc:
        raise PersonnelOrderValidationError(str(exc)) from exc


def _complete_application(
    conn: Connection,
    *,
    application_id: int,
    person_id: int,
    now: datetime | None = None,
) -> None:
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app_repo.update_application_fields(
        application_id,
        status=APPLICATION_STATUS_COMPLETED,
        now=now or _now_utc(),
    )
    sync_envelope_intended_projection(conn, person_id)


def complete_application_after_hire(
    conn: Connection,
    *,
    application_id: int,
    employee_id: int,
    actor_user_id: int,
) -> ApplicationApplyResult:
    """Mark application completed after a successful HIRE apply."""
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.require_by_id(application_id)
    if app.status == APPLICATION_STATUS_COMPLETED:
        from app.employee_onboarding.application.bootstrap_service import create_onboarding_from_hire

        create_onboarding_from_hire(
            conn,
            employee_id=employee_id,
            application_id=application_id,
            responsible_hr_id=actor_user_id,
        )
        return ApplicationApplyResult(
            application_id=application_id,
            personnel_order_id=int(app.personnel_order_id) if app.personnel_order_id else 0,
            employee_id=employee_id,
            idempotent_replay=True,
            application_status=APPLICATION_STATUS_COMPLETED,
        )

    previous_status = app.status
    _complete_application(conn, application_id=application_id, person_id=app.person_id)
    from app.personnel_applications.application.lifecycle_service import record_completed_from_apply

    record_completed_from_apply(
        conn,
        application_id=application_id,
        previous_status=previous_status,
        actor_user_id=actor_user_id,
        employee_id=employee_id,
        personnel_order_id=int(app.personnel_order_id) if app.personnel_order_id else 0,
    )
    from app.employee_onboarding.application.bootstrap_service import create_onboarding_from_hire

    create_onboarding_from_hire(
        conn,
        employee_id=employee_id,
        application_id=application_id,
        responsible_hr_id=actor_user_id,
    )
    return ApplicationApplyResult(
        application_id=application_id,
        personnel_order_id=int(app.personnel_order_id) if app.personnel_order_id else 0,
        employee_id=employee_id,
        idempotent_replay=False,
        application_status=APPLICATION_STATUS_COMPLETED,
    )


def try_complete_linked_application_after_order_apply(
    conn: Connection,
    *,
    order_id: int,
    created_by_user_id: int,
) -> ApplicationApplyResult | None:
    """Hook: after personnel order apply, close linked application if present."""
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.get_by_personnel_order_id(order_id)
    if app is None:
        return None

    employee_id = _resolve_hire_employee_id_for_order(conn, order_id)
    if employee_id is None:
        return None

    if app.status == APPLICATION_STATUS_COMPLETED:
        return ApplicationApplyResult(
            application_id=app.application_id,
            personnel_order_id=int(order_id),
            employee_id=employee_id,
            idempotent_replay=True,
            application_status=APPLICATION_STATUS_COMPLETED,
        )

    return complete_application_after_hire(
        conn,
        application_id=app.application_id,
        employee_id=employee_id,
        actor_user_id=created_by_user_id,
    )


def _map_order_validation_to_apply_error(exc: Exception) -> None:
    if isinstance(exc, PersonnelOrderArchivedError):
        raise PersonnelApplicationApplyError(str(exc), code="ORDER_ARCHIVED") from exc
    if isinstance(exc, PersonnelOrderValidationError):
        message = str(exc)
        if "does not match linked application person_id" in message:
            code = "HIRE_TARGET_PERSON_MISMATCH"
        elif "HIRE target sources conflict" in message:
            code = "HIRE_ITEM_TARGET_SOURCES_MISMATCH"
        elif "requires resolvable target person_id" in message:
            code = "HIRE_ITEM_TARGET_MISSING"
        elif "multiple distinct HIRE target person_ids" in message:
            code = "HIRE_TARGET_AMBIGUOUS"
        elif "has no active HIRE items" in message:
            code = "HIRE_TARGET_MISSING"
        elif "cannot be applied in status" in message:
            code = "ORDER_NOT_APPLIABLE"
        elif "At least one active order item" in message:
            code = "ORDER_ITEMS_MISSING"
        elif "requires effective_date" in message:
            code = "ORDER_ITEM_INVALID"
        elif "HIRE payload requires org_unit_id" in message:
            code = "ORDER_ITEM_INVALID"
        else:
            code = "HIRE_APPLY_VALIDATION_FAILED"
        raise PersonnelApplicationApplyError(message, code=code) from exc
    raise exc


@dataclass(frozen=True, slots=True)
class ApplicationHireApplyPrecheck:
    outcome: Literal["completed_replay", "order_applied_completion", "fresh_hire"]
    application_id: int
    person_id: int
    personnel_order_id: int
    replay_result: ApplicationApplyResult | None = None


def precheck_application_hire_apply(application_id: int) -> ApplicationHireApplyPrecheck:
    """Read-only pre-check for application HIRE apply (closed read txn)."""
    with engine.connect() as conn:
        app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
        app = app_repo.require_by_id(application_id)

        if app.status == APPLICATION_STATUS_COMPLETED:
            if app.personnel_order_id is None:
                raise PersonnelApplicationApplyError(
                    "Completed application has no linked order.",
                    code="ORDER_NOT_LINKED",
                )
            employee_id = _resolve_hire_employee_id_for_order(conn, int(app.personnel_order_id))
            if employee_id is None:
                raise PersonnelApplicationApplyError(
                    "Completed application has no linked HIRE employee event.",
                    code="EMPLOYEE_NOT_FOUND",
                )
            return ApplicationHireApplyPrecheck(
                outcome="completed_replay",
                application_id=application_id,
                person_id=int(app.person_id),
                personnel_order_id=int(app.personnel_order_id),
                replay_result=ApplicationApplyResult(
                    application_id=application_id,
                    personnel_order_id=int(app.personnel_order_id),
                    employee_id=employee_id,
                    idempotent_replay=True,
                    application_status=APPLICATION_STATUS_COMPLETED,
                ),
            )

        app, order = _validate_application_can_apply(conn, application_id=application_id)
        order_id = int(app.personnel_order_id)
        assert order is not None

        if str(order["order_type_code"]) != ORDER_TYPE_HIRE:
            raise PersonnelApplicationApplyError(
                "Linked personnel order must be HIRE.",
                code="ORDER_NOT_HIRE",
            )

        if _count_linked_events(conn, order_id) > 0:
            return ApplicationHireApplyPrecheck(
                outcome="order_applied_completion",
                application_id=application_id,
                person_id=int(app.person_id),
                personnel_order_id=order_id,
            )

        order_status = str(order["status"])
        if order_status not in APPLYABLE_ORDER_STATUSES:
            raise PersonnelApplicationApplyError(
                f"Personnel order {order_id} cannot be applied in status {order_status}. "
                f"Allowed: {', '.join(sorted(APPLYABLE_ORDER_STATUSES))}.",
                code="ORDER_NOT_APPLIABLE",
            )

        try:
            validate_hire_order_ready_for_apply_readonly(
                conn,
                order_id=order_id,
                linked_application_person_id=int(app.person_id),
            )
        except (PersonnelOrderArchivedError, PersonnelOrderValidationError) as exc:
            _map_order_validation_to_apply_error(exc)

        return ApplicationHireApplyPrecheck(
            outcome="fresh_hire",
            application_id=application_id,
            person_id=int(app.person_id),
            personnel_order_id=order_id,
        )


def orchestrate_hire_apply_for_application(
    *,
    application_id: int,
    created_by_user_id: int,
) -> ApplicationApplyResult:
    """Pre-check, optional photo hook, then caller-owned HIRE transaction."""
    precheck = precheck_application_hire_apply(application_id)
    if precheck.outcome == "completed_replay":
        assert precheck.replay_result is not None
        return precheck.replay_result

    if precheck.outcome == "fresh_hire":
        from app.person_photos.application.hire_apply_hook import ensure_hire_photo_ready

        ensure_hire_photo_ready(
            application_id=precheck.application_id,
            person_id=precheck.person_id,
            actor_user_id=created_by_user_id,
            correlation_id=f"hire-apply:application:{application_id}",
        )

    with engine.begin() as conn:
        return apply_hire_for_application(
            conn,
            application_id=application_id,
            created_by_user_id=created_by_user_id,
        )


def apply_hire_for_application(
    conn: Connection,
    *,
    application_id: int,
    created_by_user_id: int,
) -> ApplicationApplyResult:
    """Apply linked HIRE order and complete personnel application."""
    app_repo = SqlAlchemyPersonnelApplicationRepository(conn)
    app = app_repo.require_by_id(application_id)

    if app.status == APPLICATION_STATUS_COMPLETED:
        if app.personnel_order_id is None:
            raise PersonnelApplicationApplyError(
                "Completed application has no linked order.",
                code="ORDER_NOT_LINKED",
            )
        employee_id = _resolve_hire_employee_id_for_order(conn, int(app.personnel_order_id))
        if employee_id is None:
            raise PersonnelApplicationApplyError(
                "Completed application has no linked HIRE employee event.",
                code="EMPLOYEE_NOT_FOUND",
            )
        return ApplicationApplyResult(
            application_id=application_id,
            personnel_order_id=int(app.personnel_order_id),
            employee_id=employee_id,
            idempotent_replay=True,
            application_status=APPLICATION_STATUS_COMPLETED,
        )

    app, order = _validate_application_can_apply(conn, application_id=application_id)
    order_id = int(app.personnel_order_id)
    assert order is not None

    active_employee_id = _person_has_active_employee(conn, app.person_id)
    if active_employee_id is not None:
        raise PersonnelApplicationApplyError(
            f"Person already has active employee_id={active_employee_id}.",
            code="ACTIVE_EMPLOYEE_EXISTS",
        )

    order_status = str(order["status"])
    order_already_applied = _count_linked_events(conn, order_id) > 0

    if order_already_applied:
        employee_id = _resolve_hire_employee_id_for_order(conn, order_id)
        if employee_id is None:
            raise PersonnelApplicationApplyError(
                "Linked order is applied but HIRE employee event is missing.",
                code="EMPLOYEE_NOT_FOUND",
            )
        result = complete_application_after_hire(
            conn,
            application_id=application_id,
            employee_id=employee_id,
            actor_user_id=created_by_user_id,
        )
        return ApplicationApplyResult(
            application_id=result.application_id,
            personnel_order_id=order_id,
            employee_id=result.employee_id,
            idempotent_replay=True,
            application_status=result.application_status,
        )

    if order_status not in APPLYABLE_ORDER_STATUSES:
        raise PersonnelApplicationApplyError(
            f"Personnel order {order_id} cannot be applied in status {order_status}. "
            f"Allowed: {', '.join(sorted(APPLYABLE_ORDER_STATUSES))}.",
            code="ORDER_NOT_APPLIABLE",
        )

    try:
        validate_authoritative_hire_target(
            conn,
            order_id=order_id,
            linked_application_person_id=int(app.person_id),
        )
    except (PersonnelOrderArchivedError, PersonnelOrderValidationError) as exc:
        _map_order_validation_to_apply_error(exc)

    try:
        apply_personnel_order_in_conn(
            conn,
            order_id=order_id,
            created_by=int(created_by_user_id),
            complete_linked_application=False,
        )
    except PersonnelOrderAlreadyAppliedError:
        employee_id = _resolve_hire_employee_id_for_order(conn, order_id)
        if employee_id is None:
            raise
        result = complete_application_after_hire(
            conn,
            application_id=application_id,
            employee_id=employee_id,
            actor_user_id=created_by_user_id,
        )
        return ApplicationApplyResult(
            application_id=result.application_id,
            personnel_order_id=order_id,
            employee_id=result.employee_id,
            idempotent_replay=True,
            application_status=result.application_status,
        )

    employee_id = _resolve_hire_employee_id_for_order(conn, order_id)
    if employee_id is None:
        raise PersonnelApplicationApplyError(
            "HIRE apply completed but employee event was not created.",
            code="EMPLOYEE_NOT_FOUND",
        )

    result = complete_application_after_hire(
        conn,
        application_id=application_id,
        employee_id=employee_id,
        actor_user_id=created_by_user_id,
    )
    return ApplicationApplyResult(
        application_id=result.application_id,
        personnel_order_id=order_id,
        employee_id=result.employee_id,
        idempotent_replay=False,
        application_status=result.application_status,
    )
