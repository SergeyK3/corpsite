"""SQLAlchemy repository for employee onboarding (WP-ONBOARDING-001)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.employee_onboarding.domain.errors import (
    EmployeeOnboardingChecklistError,
    EmployeeOnboardingNotFoundError,
)
from app.employee_onboarding.domain.models import (
    EmployeeOnboardingSnapshot,
    OnboardingChecklistAttachmentSnapshot,
    OnboardingChecklistItemSnapshot,
    OnboardingTaskAuditSnapshot,
    OnboardingTaskListItemSnapshot,
)
from app.employee_onboarding.domain.status import (
    CHECKLIST_ITEM_STATUS_COMPLETED,
    CHECKLIST_ITEM_STATUS_PENDING,
    CHECKLIST_ITEM_STATUS_SKIPPED,
    ONBOARDING_STATUS_ACTIVE,
    STANDARD_CHECKLIST_CODES,
    STANDARD_CHECKLIST_TITLES,
    is_onboarding_editable,
)


def _row_to_onboarding(row) -> EmployeeOnboardingSnapshot:
    return EmployeeOnboardingSnapshot(
        onboarding_id=int(row["onboarding_id"]),
        employee_id=int(row["employee_id"]),
        application_id=int(row["application_id"]) if row.get("application_id") is not None else None,
        status=str(row["status"]),
        started_at=row["started_at"],
        planned_end_at=row.get("planned_end_at"),
        completed_at=row.get("completed_at"),
        responsible_hr_id=int(row["responsible_hr_id"]),
        mentor_employee_id=(
            int(row["mentor_employee_id"]) if row.get("mentor_employee_id") is not None else None
        ),
        notes=row.get("notes"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_checklist_item(row) -> OnboardingChecklistItemSnapshot:
    return OnboardingChecklistItemSnapshot(
        item_id=int(row["item_id"]),
        onboarding_id=int(row["onboarding_id"]),
        item_code=row.get("item_code"),
        title=str(row["title"]),
        sort_order=int(row["sort_order"]),
        is_custom=bool(row["is_custom"]),
        status=str(row["status"]),
        completed_at=row.get("completed_at"),
        completed_by_user_id=(
            int(row["completed_by_user_id"]) if row.get("completed_by_user_id") is not None else None
        ),
        comment=row.get("comment"),
        due_date=row.get("due_date"),
        assignee_kind=str(row["assignee_kind"]) if row.get("assignee_kind") is not None else None,
        assignee_user_id=(
            int(row["assignee_user_id"]) if row.get("assignee_user_id") is not None else None
        ),
        assignee_employee_id=(
            int(row["assignee_employee_id"]) if row.get("assignee_employee_id") is not None else None
        ),
        priority=str(row.get("priority") or "normal"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_attachment(row) -> OnboardingChecklistAttachmentSnapshot:
    return OnboardingChecklistAttachmentSnapshot(
        attachment_id=int(row["attachment_id"]),
        item_id=int(row["item_id"]),
        file_url=str(row["file_url"]),
        file_comment=row.get("file_comment"),
        created_by=int(row["created_by"]),
        created_at=row["created_at"],
    )


def _row_to_task_audit(row) -> OnboardingTaskAuditSnapshot:
    payload = row.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    return OnboardingTaskAuditSnapshot(
        audit_id=int(row["audit_id"]),
        item_id=int(row["item_id"]),
        onboarding_id=int(row["onboarding_id"]),
        action=str(row["action"]),
        actor_user_id=int(row["actor_user_id"]) if row.get("actor_user_id") is not None else None,
        payload=payload,
        created_at=row["created_at"],
        actor_name=str(row["actor_name"]).strip() if row.get("actor_name") else None,
    )


def is_task_overdue(item: OnboardingChecklistItemSnapshot, *, now: datetime | None = None) -> bool:
    from datetime import UTC

    if item.status != CHECKLIST_ITEM_STATUS_PENDING or item.due_date is None:
        return False
    effective_now = now or datetime.now(UTC)
    return item.due_date < effective_now


def compute_progress_percent(items: list[OnboardingChecklistItemSnapshot]) -> int:
    if not items:
        return 0
    done = sum(
        1
        for item in items
        if item.status in {CHECKLIST_ITEM_STATUS_COMPLETED, CHECKLIST_ITEM_STATUS_SKIPPED}
    )
    return int(round(done * 100 / len(items)))


class SqlAlchemyEmployeeOnboardingRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get_by_id(self, onboarding_id: int) -> EmployeeOnboardingSnapshot | None:
        row = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.employee_onboardings
                WHERE onboarding_id = :onboarding_id
                LIMIT 1
                """
            ),
            {"onboarding_id": int(onboarding_id)},
        ).mappings().first()
        return _row_to_onboarding(row) if row else None

    def require_by_id(self, onboarding_id: int) -> EmployeeOnboardingSnapshot:
        onboarding = self.get_by_id(onboarding_id)
        if onboarding is None:
            raise EmployeeOnboardingNotFoundError(
                f"Onboarding not found: onboarding_id={onboarding_id}"
            )
        return onboarding

    def get_by_application_id(self, application_id: int) -> EmployeeOnboardingSnapshot | None:
        row = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.employee_onboardings
                WHERE application_id = :application_id
                LIMIT 1
                """
            ),
            {"application_id": int(application_id)},
        ).mappings().first()
        return _row_to_onboarding(row) if row else None

    def get_active_by_employee_id(self, employee_id: int) -> EmployeeOnboardingSnapshot | None:
        row = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.employee_onboardings
                WHERE employee_id = :employee_id
                ORDER BY started_at DESC, onboarding_id DESC
                LIMIT 1
                """
            ),
            {"employee_id": int(employee_id)},
        ).mappings().first()
        return _row_to_onboarding(row) if row else None

    def create_onboarding(
        self,
        *,
        employee_id: int,
        application_id: int | None,
        responsible_hr_id: int,
        started_at: datetime,
        planned_end_at: datetime | None,
        mentor_employee_id: int | None = None,
        notes: str | None = None,
    ) -> EmployeeOnboardingSnapshot:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.employee_onboardings (
                    employee_id,
                    application_id,
                    status,
                    started_at,
                    planned_end_at,
                    responsible_hr_id,
                    mentor_employee_id,
                    notes
                )
                VALUES (
                    :employee_id,
                    :application_id,
                    :status,
                    :started_at,
                    :planned_end_at,
                    :responsible_hr_id,
                    :mentor_employee_id,
                    :notes
                )
                RETURNING *
                """
            ),
            {
                "employee_id": int(employee_id),
                "application_id": int(application_id) if application_id is not None else None,
                "status": ONBOARDING_STATUS_ACTIVE,
                "started_at": started_at,
                "planned_end_at": planned_end_at,
                "responsible_hr_id": int(responsible_hr_id),
                "mentor_employee_id": int(mentor_employee_id) if mentor_employee_id is not None else None,
                "notes": notes,
            },
        ).mappings().one()
        return _row_to_onboarding(row)

    def seed_standard_checklist(
        self,
        onboarding_id: int,
        *,
        planned_end_at: datetime | None = None,
    ) -> list[OnboardingChecklistItemSnapshot]:
        from app.employee_onboarding.domain.status import (
            DEFAULT_ASSIGNEE_BY_CHECKLIST_CODE,
            DEFAULT_ASSIGNEE_KIND,
        )

        items: list[OnboardingChecklistItemSnapshot] = []
        for index, code in enumerate(STANDARD_CHECKLIST_CODES):
            assignee_kind = DEFAULT_ASSIGNEE_BY_CHECKLIST_CODE.get(code, DEFAULT_ASSIGNEE_KIND)
            row = self._conn.execute(
                text(
                    """
                    INSERT INTO public.employee_onboarding_checklist_items (
                        onboarding_id,
                        item_code,
                        title,
                        sort_order,
                        is_custom,
                        status,
                        due_date,
                        assignee_kind,
                        priority
                    )
                    VALUES (
                        :onboarding_id,
                        :item_code,
                        :title,
                        :sort_order,
                        FALSE,
                        :status,
                        :due_date,
                        :assignee_kind,
                        :priority
                    )
                    RETURNING *
                    """
                ),
                {
                    "onboarding_id": int(onboarding_id),
                    "item_code": code,
                    "title": STANDARD_CHECKLIST_TITLES[code],
                    "sort_order": index,
                    "status": CHECKLIST_ITEM_STATUS_PENDING,
                    "due_date": planned_end_at,
                    "assignee_kind": assignee_kind,
                    "priority": "normal",
                },
            ).mappings().one()
            items.append(_row_to_checklist_item(row))
        return items

    def list_checklist_items(self, onboarding_id: int) -> list[OnboardingChecklistItemSnapshot]:
        rows = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.employee_onboarding_checklist_items
                WHERE onboarding_id = :onboarding_id
                ORDER BY sort_order ASC, item_id ASC
                """
            ),
            {"onboarding_id": int(onboarding_id)},
        ).mappings().all()
        return [_row_to_checklist_item(row) for row in rows]

    def get_checklist_item(self, item_id: int) -> OnboardingChecklistItemSnapshot | None:
        row = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.employee_onboarding_checklist_items
                WHERE item_id = :item_id
                LIMIT 1
                """
            ),
            {"item_id": int(item_id)},
        ).mappings().first()
        return _row_to_checklist_item(row) if row else None

    def require_checklist_item(self, item_id: int) -> OnboardingChecklistItemSnapshot:
        item = self.get_checklist_item(item_id)
        if item is None:
            raise EmployeeOnboardingChecklistError(
                f"Checklist item not found: item_id={item_id}",
                code="CHECKLIST_ITEM_NOT_FOUND",
            )
        return item

    def add_custom_checklist_item(
        self,
        *,
        onboarding_id: int,
        title: str,
        sort_order: int | None = None,
    ) -> OnboardingChecklistItemSnapshot:
        if sort_order is None:
            sort_order = int(
                self._conn.execute(
                    text(
                        """
                        SELECT COALESCE(MAX(sort_order), -1) + 1
                        FROM public.employee_onboarding_checklist_items
                        WHERE onboarding_id = :onboarding_id
                        """
                    ),
                    {"onboarding_id": int(onboarding_id)},
                ).scalar_one()
            )
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.employee_onboarding_checklist_items (
                    onboarding_id,
                    item_code,
                    title,
                    sort_order,
                    is_custom,
                    status
                )
                VALUES (
                    :onboarding_id,
                    NULL,
                    :title,
                    :sort_order,
                    TRUE,
                    :status
                )
                RETURNING *
                """
            ),
            {
                "onboarding_id": int(onboarding_id),
                "title": title,
                "sort_order": int(sort_order),
                "status": CHECKLIST_ITEM_STATUS_PENDING,
            },
        ).mappings().one()
        return _row_to_checklist_item(row)

    def update_checklist_item_status(
        self,
        *,
        item_id: int,
        status: str,
        completed_at: datetime | None,
        completed_by_user_id: int | None,
        comment: str | None,
        updated_at: datetime,
    ) -> OnboardingChecklistItemSnapshot:
        row = self._conn.execute(
            text(
                """
                UPDATE public.employee_onboarding_checklist_items
                SET status = :status,
                    completed_at = :completed_at,
                    completed_by_user_id = :completed_by_user_id,
                    comment = :comment,
                    updated_at = :updated_at
                WHERE item_id = :item_id
                RETURNING *
                """
            ),
            {
                "item_id": int(item_id),
                "status": status,
                "completed_at": completed_at,
                "completed_by_user_id": completed_by_user_id,
                "comment": comment,
                "updated_at": updated_at,
            },
        ).mappings().one()
        return _row_to_checklist_item(row)

    def update_onboarding_status(
        self,
        *,
        onboarding_id: int,
        status: str,
        completed_at: datetime | None,
        updated_at: datetime,
        notes: str | None = None,
    ) -> EmployeeOnboardingSnapshot:
        row = self._conn.execute(
            text(
                """
                UPDATE public.employee_onboardings
                SET status = :status,
                    completed_at = :completed_at,
                    notes = COALESCE(:notes, notes),
                    updated_at = :updated_at
                WHERE onboarding_id = :onboarding_id
                RETURNING *
                """
            ),
            {
                "onboarding_id": int(onboarding_id),
                "status": status,
                "completed_at": completed_at,
                "notes": notes,
                "updated_at": updated_at,
            },
        ).mappings().one()
        return _row_to_onboarding(row)

    def assert_editable(self, onboarding: EmployeeOnboardingSnapshot) -> None:
        if not is_onboarding_editable(onboarding.status):
            raise EmployeeOnboardingChecklistError(
                f"Onboarding is read-only (status={onboarding.status}).",
                code="ONBOARDING_READ_ONLY",
            )

    def update_checklist_item_fields(
        self,
        *,
        item_id: int,
        due_date: datetime | None = ...,
        assignee_kind: str | None = ...,
        assignee_user_id: int | None = ...,
        assignee_employee_id: int | None = ...,
        priority: str | None = ...,
        comment: str | None = ...,
        updated_at: datetime,
    ) -> OnboardingChecklistItemSnapshot:
        sets: list[str] = ["updated_at = :updated_at"]
        params: dict[str, Any] = {"item_id": int(item_id), "updated_at": updated_at}
        if due_date is not ...:
            sets.append("due_date = :due_date")
            params["due_date"] = due_date
        if assignee_kind is not ...:
            sets.append("assignee_kind = :assignee_kind")
            params["assignee_kind"] = assignee_kind
        if assignee_user_id is not ...:
            sets.append("assignee_user_id = :assignee_user_id")
            params["assignee_user_id"] = assignee_user_id
        if assignee_employee_id is not ...:
            sets.append("assignee_employee_id = :assignee_employee_id")
            params["assignee_employee_id"] = assignee_employee_id
        if priority is not ...:
            sets.append("priority = :priority")
            params["priority"] = priority
        if comment is not ...:
            sets.append("comment = :comment")
            params["comment"] = comment
        row = self._conn.execute(
            text(
                f"""
                UPDATE public.employee_onboarding_checklist_items
                SET {", ".join(sets)}
                WHERE item_id = :item_id
                RETURNING *
                """
            ),
            params,
        ).mappings().one()
        return _row_to_checklist_item(row)

    def add_checklist_attachment(
        self,
        *,
        item_id: int,
        file_url: str,
        file_comment: str | None,
        created_by: int,
    ) -> OnboardingChecklistAttachmentSnapshot:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.employee_onboarding_checklist_attachments (
                    item_id, file_url, file_comment, created_by
                )
                VALUES (:item_id, :file_url, :file_comment, :created_by)
                RETURNING *
                """
            ),
            {
                "item_id": int(item_id),
                "file_url": file_url,
                "file_comment": file_comment,
                "created_by": int(created_by),
            },
        ).mappings().one()
        return _row_to_attachment(row)

    def list_attachments_for_items(
        self,
        item_ids: list[int],
    ) -> dict[int, list[OnboardingChecklistAttachmentSnapshot]]:
        if not item_ids:
            return {}
        rows = self._conn.execute(
            text(
                """
                SELECT *
                FROM public.employee_onboarding_checklist_attachments
                WHERE item_id = ANY(:item_ids)
                ORDER BY created_at ASC, attachment_id ASC
                """
            ),
            {"item_ids": [int(x) for x in item_ids]},
        ).mappings().all()
        out: dict[int, list[OnboardingChecklistAttachmentSnapshot]] = {}
        for row in rows:
            attachment = _row_to_attachment(row)
            out.setdefault(attachment.item_id, []).append(attachment)
        return out

    def write_task_audit(
        self,
        *,
        item_id: int,
        onboarding_id: int,
        action: str,
        actor_user_id: int | None,
        payload: dict | None = None,
    ) -> int:
        return int(
            self._conn.execute(
                text(
                    """
                    INSERT INTO public.employee_onboarding_task_audit (
                        item_id, onboarding_id, action, actor_user_id, payload
                    )
                    VALUES (:item_id, :onboarding_id, :action, :actor_user_id, CAST(:payload AS jsonb))
                    RETURNING audit_id
                    """
                ),
                {
                    "item_id": int(item_id),
                    "onboarding_id": int(onboarding_id),
                    "action": action,
                    "actor_user_id": actor_user_id,
                    "payload": __import__("json").dumps(payload or {}),
                },
            ).scalar_one()
        )

    def list_task_audit(self, item_id: int, *, limit: int = 50) -> list[OnboardingTaskAuditSnapshot]:
        rows = self._conn.execute(
            text(
                """
                SELECT a.*, u.full_name AS actor_name
                FROM public.employee_onboarding_task_audit a
                LEFT JOIN public.users u ON u.user_id = a.actor_user_id
                WHERE a.item_id = :item_id
                ORDER BY a.created_at DESC, a.audit_id DESC
                LIMIT :limit
                """
            ),
            {"item_id": int(item_id), "limit": max(1, min(int(limit), 200))},
        ).mappings().all()
        return [_row_to_task_audit(row) for row in rows]

    def resolve_assignee_user_id(
        self,
        *,
        onboarding: EmployeeOnboardingSnapshot,
        item: OnboardingChecklistItemSnapshot,
    ) -> int | None:
        kind = item.assignee_kind
        if kind == "hr":
            return int(onboarding.responsible_hr_id)
        if kind == "mentor":
            mentor_employee_id = onboarding.mentor_employee_id
            if mentor_employee_id is None:
                return None
            row = self._conn.execute(
                text(
                    """
                    SELECT user_id
                    FROM public.users
                    WHERE employee_id = :employee_id
                      AND COALESCE(is_active, true) = true
                    ORDER BY user_id ASC
                    LIMIT 1
                    """
                ),
                {"employee_id": int(mentor_employee_id)},
            ).mappings().first()
            return int(row["user_id"]) if row and row.get("user_id") is not None else None
        if kind == "employee":
            if item.assignee_employee_id is None:
                return None
            row = self._conn.execute(
                text(
                    """
                    SELECT user_id
                    FROM public.users
                    WHERE employee_id = :employee_id
                      AND COALESCE(is_active, true) = true
                    ORDER BY user_id ASC
                    LIMIT 1
                    """
                ),
                {"employee_id": int(item.assignee_employee_id)},
            ).mappings().first()
            return int(row["user_id"]) if row and row.get("user_id") is not None else None
        if item.assignee_user_id is not None:
            return int(item.assignee_user_id)
        return None
