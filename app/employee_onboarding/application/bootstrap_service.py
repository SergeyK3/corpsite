"""Bootstrap employee onboarding after HIRE apply (WP-ONBOARDING-001)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.engine import Connection

from app.employee_onboarding.domain.models import OnboardingDetailSnapshot
from app.employee_onboarding.domain.status import DEFAULT_ONBOARDING_DURATION_DAYS
from app.employee_onboarding.infrastructure.repository import SqlAlchemyEmployeeOnboardingRepository


def _now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class BootstrapOnboardingResult:
    onboarding_id: int
    employee_id: int
    application_id: int | None
    idempotent_replay: bool


def create_onboarding_from_hire(
    conn: Connection,
    *,
    employee_id: int,
    application_id: int | None,
    responsible_hr_id: int,
    mentor_employee_id: int | None = None,
    notes: str | None = None,
    started_at: datetime | None = None,
) -> BootstrapOnboardingResult:
    """Idempotent bootstrap after successful HIRE apply."""
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    if application_id is not None:
        existing = repo.get_by_application_id(application_id)
        if existing is not None:
            return BootstrapOnboardingResult(
                onboarding_id=existing.onboarding_id,
                employee_id=existing.employee_id,
                application_id=existing.application_id,
                idempotent_replay=True,
            )

    effective_started = started_at or _now_utc()
    planned_end = effective_started + timedelta(days=DEFAULT_ONBOARDING_DURATION_DAYS)
    onboarding = repo.create_onboarding(
        employee_id=employee_id,
        application_id=application_id,
        responsible_hr_id=responsible_hr_id,
        started_at=effective_started,
        planned_end_at=planned_end,
        mentor_employee_id=mentor_employee_id,
        notes=notes,
    )
    repo.seed_standard_checklist(onboarding.onboarding_id, planned_end_at=planned_end)
    from app.employee_onboarding.application.notification_service import notify_task_assigned

    items = repo.list_checklist_items(onboarding.onboarding_id)
    for item in items:
        notify_task_assigned(
            conn,
            onboarding=onboarding,
            item=item,
            actor_user_id=responsible_hr_id,
        )
    return BootstrapOnboardingResult(
        onboarding_id=onboarding.onboarding_id,
        employee_id=onboarding.employee_id,
        application_id=onboarding.application_id,
        idempotent_replay=False,
    )


def load_onboarding_detail(conn: Connection, onboarding_id: int) -> OnboardingDetailSnapshot:
    from app.employee_onboarding.domain.status import is_terminal_onboarding_status
    from app.employee_onboarding.infrastructure.repository import compute_progress_percent, is_task_overdue

    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    onboarding = repo.require_by_id(onboarding_id)
    items = repo.list_checklist_items(onboarding_id)
    item_ids = [item.item_id for item in items]
    attachments_map = repo.list_attachments_for_items(item_ids)
    overdue_count = sum(1 for item in items if is_task_overdue(item))
    return OnboardingDetailSnapshot(
        onboarding=onboarding,
        checklist_items=tuple(items),
        progress_percent=compute_progress_percent(items),
        is_read_only=is_terminal_onboarding_status(onboarding.status),
        overdue_count=overdue_count,
        attachments_by_item={
            item_id: tuple(attachments_map.get(item_id, [])) for item_id in item_ids
        },
    )


def load_onboarding_detail_for_employee(
    conn: Connection,
    employee_id: int,
) -> OnboardingDetailSnapshot | None:
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    onboarding = repo.get_active_by_employee_id(employee_id)
    if onboarding is None:
        return None
    return load_onboarding_detail(conn, onboarding.onboarding_id)
