"""Checklist and lifecycle operations (WP-ONBOARDING-001)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.engine import Connection

from app.employee_onboarding.application.bootstrap_service import load_onboarding_detail
from app.employee_onboarding.application.notification_service import notify_task_completed
from app.employee_onboarding.domain.errors import EmployeeOnboardingChecklistError
from app.employee_onboarding.domain.models import OnboardingDetailSnapshot
from app.employee_onboarding.domain.status import (
    CHECKLIST_ITEM_STATUS_COMPLETED,
    CHECKLIST_ITEM_STATUS_PENDING,
    CHECKLIST_ITEM_STATUS_SKIPPED,
    ONBOARDING_STATUS_CANCELLED,
    ONBOARDING_STATUS_COMPLETED,
)
from app.employee_onboarding.domain.task_audit import TASK_AUDIT_COMPLETED, TASK_AUDIT_SKIPPED
from app.employee_onboarding.infrastructure.repository import SqlAlchemyEmployeeOnboardingRepository


def _now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ChecklistActionResult:
    detail: OnboardingDetailSnapshot


def complete_checklist_item(
    conn: Connection,
    *,
    onboarding_id: int,
    item_id: int,
    actor_user_id: int,
    comment: str | None = None,
) -> ChecklistActionResult:
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    onboarding = repo.require_by_id(onboarding_id)
    repo.assert_editable(onboarding)
    item = repo.require_checklist_item(item_id)
    if item.onboarding_id != onboarding_id:
        raise EmployeeOnboardingChecklistError(
            "Checklist item does not belong to onboarding.",
            code="CHECKLIST_ITEM_MISMATCH",
        )
    if item.status != CHECKLIST_ITEM_STATUS_PENDING:
        raise EmployeeOnboardingChecklistError(
            f"Checklist item is already {item.status}.",
            code="CHECKLIST_ITEM_NOT_PENDING",
        )
    now = _now_utc()
    repo.update_checklist_item_status(
        item_id=item_id,
        status=CHECKLIST_ITEM_STATUS_COMPLETED,
        completed_at=now,
        completed_by_user_id=actor_user_id,
        comment=comment,
        updated_at=now,
    )
    updated_item = repo.require_checklist_item(item_id)
    repo.write_task_audit(
        item_id=item_id,
        onboarding_id=onboarding_id,
        action=TASK_AUDIT_COMPLETED,
        actor_user_id=actor_user_id,
        payload={"comment": comment},
    )
    notify_task_completed(
        conn,
        onboarding=onboarding,
        item=updated_item,
        actor_user_id=actor_user_id,
    )
    return ChecklistActionResult(detail=load_onboarding_detail(conn, onboarding_id))


def skip_checklist_item(
    conn: Connection,
    *,
    onboarding_id: int,
    item_id: int,
    actor_user_id: int,
    comment: str | None = None,
) -> ChecklistActionResult:
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    onboarding = repo.require_by_id(onboarding_id)
    repo.assert_editable(onboarding)
    item = repo.require_checklist_item(item_id)
    if item.onboarding_id != onboarding_id:
        raise EmployeeOnboardingChecklistError(
            "Checklist item does not belong to onboarding.",
            code="CHECKLIST_ITEM_MISMATCH",
        )
    if item.status != CHECKLIST_ITEM_STATUS_PENDING:
        raise EmployeeOnboardingChecklistError(
            f"Checklist item is already {item.status}.",
            code="CHECKLIST_ITEM_NOT_PENDING",
        )
    now = _now_utc()
    repo.update_checklist_item_status(
        item_id=item_id,
        status=CHECKLIST_ITEM_STATUS_SKIPPED,
        completed_at=now,
        completed_by_user_id=actor_user_id,
        comment=comment,
        updated_at=now,
    )
    repo.write_task_audit(
        item_id=item_id,
        onboarding_id=onboarding_id,
        action=TASK_AUDIT_SKIPPED,
        actor_user_id=actor_user_id,
        payload={"comment": comment},
    )
    return ChecklistActionResult(detail=load_onboarding_detail(conn, onboarding_id))


def add_custom_checklist_item(
    conn: Connection,
    *,
    onboarding_id: int,
    title: str,
    actor_user_id: int,
) -> ChecklistActionResult:
    del actor_user_id
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    onboarding = repo.require_by_id(onboarding_id)
    repo.assert_editable(onboarding)
    cleaned = str(title or "").strip()
    if not cleaned:
        raise EmployeeOnboardingChecklistError(
            "Custom checklist title is required.",
            code="CHECKLIST_TITLE_REQUIRED",
        )
    repo.add_custom_checklist_item(onboarding_id=onboarding_id, title=cleaned)
    return ChecklistActionResult(detail=load_onboarding_detail(conn, onboarding_id))


def complete_onboarding(
    conn: Connection,
    *,
    onboarding_id: int,
    actor_user_id: int,
    notes: str | None = None,
) -> ChecklistActionResult:
    del actor_user_id
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    onboarding = repo.require_by_id(onboarding_id)
    repo.assert_editable(onboarding)
    now = _now_utc()
    repo.update_onboarding_status(
        onboarding_id=onboarding_id,
        status=ONBOARDING_STATUS_COMPLETED,
        completed_at=now,
        updated_at=now,
        notes=notes,
    )
    return ChecklistActionResult(detail=load_onboarding_detail(conn, onboarding_id))


def cancel_onboarding(
    conn: Connection,
    *,
    onboarding_id: int,
    actor_user_id: int,
    reason: str,
) -> ChecklistActionResult:
    del actor_user_id
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    onboarding = repo.require_by_id(onboarding_id)
    repo.assert_editable(onboarding)
    cleaned = str(reason or "").strip()
    if not cleaned:
        raise EmployeeOnboardingChecklistError(
            "Cancel reason is required.",
            code="CANCEL_REASON_REQUIRED",
        )
    now = _now_utc()
    repo.update_onboarding_status(
        onboarding_id=onboarding_id,
        status=ONBOARDING_STATUS_CANCELLED,
        completed_at=now,
        updated_at=now,
        notes=cleaned,
    )
    return ChecklistActionResult(detail=load_onboarding_detail(conn, onboarding_id))
