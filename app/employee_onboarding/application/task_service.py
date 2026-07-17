"""Onboarding task update operations (WP-ONBOARDING-002)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.engine import Connection

from app.employee_onboarding.application.bootstrap_service import load_onboarding_detail
from app.employee_onboarding.application.notification_service import notify_task_assigned
from app.employee_onboarding.domain.errors import EmployeeOnboardingChecklistError
from app.employee_onboarding.domain.models import OnboardingDetailSnapshot
from app.employee_onboarding.domain.status import ASSIGNEE_KINDS, TASK_PRIORITIES
from app.employee_onboarding.domain.task_audit import (
    TASK_AUDIT_ASSIGNEE_CHANGED,
    TASK_AUDIT_ATTACHMENT_ADDED,
    TASK_AUDIT_COMMENT_CHANGED,
    TASK_AUDIT_DUE_DATE_CHANGED,
    TASK_AUDIT_PRIORITY_CHANGED,
    TASK_AUDIT_UPDATED,
)
from app.employee_onboarding.infrastructure.repository import SqlAlchemyEmployeeOnboardingRepository


def _now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class TaskActionResult:
    detail: OnboardingDetailSnapshot


def _validate_assignee(
    *,
    assignee_kind: str | None,
    assignee_user_id: int | None,
    assignee_employee_id: int | None,
) -> None:
    if assignee_kind is not None and assignee_kind not in ASSIGNEE_KINDS:
        raise EmployeeOnboardingChecklistError(
            f"Invalid assignee_kind: {assignee_kind}",
            code="INVALID_ASSIGNEE_KIND",
        )
    if assignee_kind == "employee" and assignee_employee_id is None:
        raise EmployeeOnboardingChecklistError(
            "assignee_employee_id is required for employee assignee.",
            code="ASSIGNEE_EMPLOYEE_REQUIRED",
        )


def update_checklist_task(
    conn: Connection,
    *,
    onboarding_id: int,
    item_id: int,
    actor_user_id: int,
    due_date: datetime | None = ...,
    assignee_kind: str | None = ...,
    assignee_user_id: int | None = ...,
    assignee_employee_id: int | None = ...,
    priority: str | None = ...,
    comment: str | None = ...,
) -> TaskActionResult:
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    onboarding = repo.require_by_id(onboarding_id)
    repo.assert_editable(onboarding)
    item = repo.require_checklist_item(item_id)
    if item.onboarding_id != onboarding_id:
        raise EmployeeOnboardingChecklistError(
            "Checklist item does not belong to onboarding.",
            code="CHECKLIST_ITEM_MISMATCH",
        )
    if priority is not ... and priority is not None and priority not in TASK_PRIORITIES:
        raise EmployeeOnboardingChecklistError(
            f"Invalid priority: {priority}",
            code="INVALID_PRIORITY",
        )
    if assignee_kind is not ...:
        _validate_assignee(
            assignee_kind=assignee_kind,
            assignee_user_id=assignee_user_id if assignee_user_id is not ... else item.assignee_user_id,
            assignee_employee_id=(
                assignee_employee_id if assignee_employee_id is not ... else item.assignee_employee_id
            ),
        )

    now = _now_utc()
    old_assignee_kind = item.assignee_kind
    repo.update_checklist_item_fields(
        item_id=item_id,
        due_date=due_date,
        assignee_kind=assignee_kind,
        assignee_user_id=assignee_user_id,
        assignee_employee_id=assignee_employee_id,
        priority=priority,
        comment=comment,
        updated_at=now,
    )
    updated_item = repo.require_checklist_item(item_id)

    if due_date is not ...:
        repo.write_task_audit(
            item_id=item_id,
            onboarding_id=onboarding_id,
            action=TASK_AUDIT_DUE_DATE_CHANGED,
            actor_user_id=actor_user_id,
            payload={"due_date": due_date.isoformat() if due_date else None},
        )
    if assignee_kind is not ...:
        repo.write_task_audit(
            item_id=item_id,
            onboarding_id=onboarding_id,
            action=TASK_AUDIT_ASSIGNEE_CHANGED,
            actor_user_id=actor_user_id,
            payload={
                "assignee_kind": assignee_kind,
                "assignee_user_id": assignee_user_id if assignee_user_id is not ... else None,
                "assignee_employee_id": (
                    assignee_employee_id if assignee_employee_id is not ... else None
                ),
            },
        )
    if priority is not ...:
        repo.write_task_audit(
            item_id=item_id,
            onboarding_id=onboarding_id,
            action=TASK_AUDIT_PRIORITY_CHANGED,
            actor_user_id=actor_user_id,
            payload={"priority": priority},
        )
    if comment is not ...:
        repo.write_task_audit(
            item_id=item_id,
            onboarding_id=onboarding_id,
            action=TASK_AUDIT_COMMENT_CHANGED,
            actor_user_id=actor_user_id,
            payload={"comment": comment},
        )
    if due_date is ... and assignee_kind is ... and priority is ... and comment is ...:
        repo.write_task_audit(
            item_id=item_id,
            onboarding_id=onboarding_id,
            action=TASK_AUDIT_UPDATED,
            actor_user_id=actor_user_id,
            payload={},
        )

    if assignee_kind is not ... and assignee_kind != old_assignee_kind:
        notify_task_assigned(
            conn,
            onboarding=onboarding,
            item=updated_item,
            actor_user_id=actor_user_id,
        )

    return TaskActionResult(detail=load_onboarding_detail(conn, onboarding_id))


def add_checklist_attachment(
    conn: Connection,
    *,
    onboarding_id: int,
    item_id: int,
    actor_user_id: int,
    file_url: str,
    file_comment: str | None = None,
) -> TaskActionResult:
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    onboarding = repo.require_by_id(onboarding_id)
    repo.assert_editable(onboarding)
    item = repo.require_checklist_item(item_id)
    if item.onboarding_id != onboarding_id:
        raise EmployeeOnboardingChecklistError(
            "Checklist item does not belong to onboarding.",
            code="CHECKLIST_ITEM_MISMATCH",
        )
    cleaned_url = str(file_url or "").strip()
    if not cleaned_url:
        raise EmployeeOnboardingChecklistError(
            "file_url is required.",
            code="ATTACHMENT_URL_REQUIRED",
        )
    attachment = repo.add_checklist_attachment(
        item_id=item_id,
        file_url=cleaned_url,
        file_comment=file_comment,
        created_by=actor_user_id,
    )
    repo.write_task_audit(
        item_id=item_id,
        onboarding_id=onboarding_id,
        action=TASK_AUDIT_ATTACHMENT_ADDED,
        actor_user_id=actor_user_id,
        payload={
            "attachment_id": attachment.attachment_id,
            "file_url": attachment.file_url,
        },
    )
    return TaskActionResult(detail=load_onboarding_detail(conn, onboarding_id))
