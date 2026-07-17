"""Onboarding task bulk operations (WP-ONBOARDING-002)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Connection

from app.employee_onboarding.application.checklist_service import complete_checklist_item
from app.employee_onboarding.application.task_service import update_checklist_task
from app.employee_onboarding.domain.errors import EmployeeOnboardingChecklistError
from app.employee_onboarding.infrastructure.repository import SqlAlchemyEmployeeOnboardingRepository


def _now_utc() -> datetime:
    return datetime.now(UTC)


def bulk_assign_tasks(
    conn: Connection,
    *,
    item_ids: list[int],
    actor_user_id: int,
    assignee_kind: str,
    assignee_user_id: int | None = None,
    assignee_employee_id: int | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    for item_id in item_ids:
        try:
            item = repo.require_checklist_item(int(item_id))
            result = update_checklist_task(
                conn,
                onboarding_id=item.onboarding_id,
                item_id=int(item_id),
                actor_user_id=actor_user_id,
                assignee_kind=assignee_kind,
                assignee_user_id=assignee_user_id,
                assignee_employee_id=assignee_employee_id,
            )
            results.append({"item_id": int(item_id), "onboarding_id": item.onboarding_id})
        except (EmployeeOnboardingChecklistError, ValueError) as exc:
            errors.append({"item_id": int(item_id), "error": str(exc)})
    return {
        "processed": len(item_ids),
        "succeeded": len(results),
        "failed": len(errors),
        "items": results,
        "errors": errors,
    }


def bulk_update_due_dates(
    conn: Connection,
    *,
    item_ids: list[int],
    actor_user_id: int,
    due_date: datetime | None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    for item_id in item_ids:
        try:
            item = repo.require_checklist_item(int(item_id))
            update_checklist_task(
                conn,
                onboarding_id=item.onboarding_id,
                item_id=int(item_id),
                actor_user_id=actor_user_id,
                due_date=due_date,
            )
            results.append({"item_id": int(item_id), "onboarding_id": item.onboarding_id})
        except (EmployeeOnboardingChecklistError, ValueError) as exc:
            errors.append({"item_id": int(item_id), "error": str(exc)})
    return {
        "processed": len(item_ids),
        "succeeded": len(results),
        "failed": len(errors),
        "items": results,
        "errors": errors,
    }


def bulk_complete_tasks(
    conn: Connection,
    *,
    item_ids: list[int],
    actor_user_id: int,
    comment: str | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    repo = SqlAlchemyEmployeeOnboardingRepository(conn)
    for item_id in item_ids:
        try:
            item = repo.require_checklist_item(int(item_id))
            complete_checklist_item(
                conn,
                onboarding_id=item.onboarding_id,
                item_id=int(item_id),
                actor_user_id=actor_user_id,
                comment=comment,
            )
            results.append({"item_id": int(item_id), "onboarding_id": item.onboarding_id})
        except (EmployeeOnboardingChecklistError, ValueError) as exc:
            errors.append({"item_id": int(item_id), "error": str(exc)})
    return {
        "processed": len(item_ids),
        "succeeded": len(results),
        "failed": len(errors),
        "items": results,
        "errors": errors,
    }
