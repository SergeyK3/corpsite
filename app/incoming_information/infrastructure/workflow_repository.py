"""Workflow persistence helpers for Incoming Information."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.incoming_information.domain.errors import (
    IncomingDocumentConflictError,
    IncomingDocumentNotFoundError,
    IncomingDocumentVersionConflictError,
)
from app.incoming_information.domain.status import (
    ASSIGNMENT_ROLE_COEXECUTOR,
    ASSIGNMENT_ROLE_PRIMARY,
)


class SqlAlchemyIncomingWorkflowRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def lock_document(self, incoming_document_id: int) -> None:
        row = self._conn.execute(
            text(
                """
                SELECT incoming_document_id
                FROM public.incoming_documents
                WHERE incoming_document_id = :id
                FOR UPDATE
                """
            ),
            {"id": int(incoming_document_id)},
        ).first()
        if not row:
            raise IncomingDocumentNotFoundError(
                f"Incoming document {incoming_document_id} not found."
            )

    def get_row_version(self, incoming_document_id: int) -> int:
        row = self._conn.execute(
            text(
                """
                SELECT row_version
                FROM public.incoming_documents
                WHERE incoming_document_id = :id
                """
            ),
            {"id": int(incoming_document_id)},
        ).first()
        if not row:
            raise IncomingDocumentNotFoundError(
                f"Incoming document {incoming_document_id} not found."
            )
        return int(row[0])

    def assert_expected_version(self, incoming_document_id: int, expected_version: int) -> None:
        current = self.get_row_version(incoming_document_id)
        if current != int(expected_version):
            raise IncomingDocumentVersionConflictError(
                f"Document version conflict: expected {expected_version}, got {current}."
            )

    def bump_version(
        self,
        *,
        incoming_document_id: int,
        expected_version: int,
        updated_by_user_id: int,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                UPDATE public.incoming_documents
                SET row_version = row_version + 1,
                    updated_by_user_id = :updated_by_user_id,
                    updated_at = now()
                WHERE incoming_document_id = :id
                  AND row_version = :expected_version
                RETURNING row_version
                """
            ),
            {
                "id": int(incoming_document_id),
                "expected_version": int(expected_version),
                "updated_by_user_id": int(updated_by_user_id),
            },
        ).first()
        if not row:
            raise IncomingDocumentVersionConflictError(
                f"Document version conflict: expected {expected_version}."
            )
        return int(row[0])

    def update_document_fields(
        self,
        *,
        incoming_document_id: int,
        expected_version: int,
        updated_by_user_id: int,
        fields: dict[str, Any],
    ) -> int:
        if not fields:
            return self.bump_version(
                incoming_document_id=incoming_document_id,
                expected_version=expected_version,
                updated_by_user_id=updated_by_user_id,
            )
        set_parts = [
            "row_version = row_version + 1",
            "updated_by_user_id = :updated_by_user_id",
            "updated_at = now()",
        ]
        params: dict[str, Any] = {
            "id": int(incoming_document_id),
            "expected_version": int(expected_version),
            "updated_by_user_id": int(updated_by_user_id),
        }
        for idx, (key, value) in enumerate(fields.items()):
            param = f"f_{idx}"
            set_parts.append(f"{key} = :{param}")
            params[param] = value
        row = self._conn.execute(
            text(
                f"""
                UPDATE public.incoming_documents
                SET {", ".join(set_parts)}
                WHERE incoming_document_id = :id
                  AND row_version = :expected_version
                RETURNING row_version
                """
            ),
            params,
        ).first()
        if not row:
            raise IncomingDocumentVersionConflictError(
                f"Document version conflict: expected {expected_version}."
            )
        return int(row[0])

    def get_active_primary(self, incoming_document_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            text(
                """
                SELECT
                    assignment_id,
                    assignee_user_id,
                    assignee_employee_id,
                    org_unit_id,
                    role,
                    assigned_at
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :id
                  AND role = :role
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                LIMIT 1
                """
            ),
            {"id": int(incoming_document_id), "role": ASSIGNMENT_ROLE_PRIMARY},
        ).mappings().first()
        return dict(row) if row else None

    def get_active_assignments(self, incoming_document_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            text(
                """
                SELECT
                    assignment_id,
                    assignee_user_id,
                    assignee_employee_id,
                    org_unit_id,
                    role,
                    assigned_at
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :id
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                ORDER BY assigned_at ASC, assignment_id ASC
                """
            ),
            {"id": int(incoming_document_id)},
        ).mappings().all()
        return [dict(row) for row in rows]

    def user_is_active_primary(self, incoming_document_id: int, user_id: int) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :id
                  AND assignee_user_id = :user_id
                  AND role = :role
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                LIMIT 1
                """
            ),
            {
                "id": int(incoming_document_id),
                "user_id": int(user_id),
                "role": ASSIGNMENT_ROLE_PRIMARY,
            },
        ).first()
        return row is not None

    def user_is_active_assignee(self, incoming_document_id: int, user_id: int) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :id
                  AND assignee_user_id = :user_id
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                LIMIT 1
                """
            ),
            {"id": int(incoming_document_id), "user_id": int(user_id)},
        ).first()
        return row is not None

    def user_is_active_coexecutor(self, incoming_document_id: int, user_id: int) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :id
                  AND assignee_user_id = :user_id
                  AND role = :role
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                LIMIT 1
                """
            ),
            {
                "id": int(incoming_document_id),
                "user_id": int(user_id),
                "role": ASSIGNMENT_ROLE_COEXECUTOR,
            },
        ).first()
        return row is not None

    def cancel_active_assignments(
        self,
        *,
        incoming_document_id: int,
        cancel_reason: str,
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            text(
                """
                UPDATE public.incoming_document_assignments
                SET cancelled_at = now(),
                    cancel_reason = :cancel_reason
                WHERE incoming_document_id = :id
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                RETURNING assignment_id, assignee_user_id, role
                """
            ),
            {"id": int(incoming_document_id), "cancel_reason": cancel_reason},
        ).mappings().all()
        return [dict(row) for row in rows]

    def cancel_active_primary(
        self,
        *,
        incoming_document_id: int,
        cancel_reason: str,
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            text(
                """
                UPDATE public.incoming_document_assignments
                SET cancelled_at = now(),
                    cancel_reason = :cancel_reason
                WHERE incoming_document_id = :id
                  AND role = :role
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                RETURNING assignment_id, assignee_user_id, role
                """
            ),
            {
                "id": int(incoming_document_id),
                "role": ASSIGNMENT_ROLE_PRIMARY,
                "cancel_reason": cancel_reason,
            },
        ).mappings().first()
        return dict(row) if row else None

    def create_assignment(
        self,
        *,
        incoming_document_id: int,
        assignee_user_id: int,
        assignee_employee_id: int | None,
        org_unit_id: int,
        role: str,
        assigned_by_user_id: int,
        due_date: date | None = None,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.incoming_document_assignments (
                    incoming_document_id,
                    assignee_user_id,
                    assignee_employee_id,
                    org_unit_id,
                    role,
                    assigned_by_user_id,
                    due_date
                )
                VALUES (
                    :incoming_document_id,
                    :assignee_user_id,
                    :assignee_employee_id,
                    :org_unit_id,
                    :role,
                    :assigned_by_user_id,
                    :due_date
                )
                RETURNING assignment_id
                """
            ),
            {
                "incoming_document_id": int(incoming_document_id),
                "assignee_user_id": int(assignee_user_id),
                "assignee_employee_id": assignee_employee_id,
                "org_unit_id": int(org_unit_id),
                "role": role,
                "assigned_by_user_id": int(assigned_by_user_id),
                "due_date": due_date,
            },
        ).one()
        return int(row[0])

    def insert_deadline_change(
        self,
        *,
        incoming_document_id: int,
        previous_due_date: date | None,
        new_due_date: date,
        reason: str,
        changed_by_user_id: int,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.incoming_document_deadline_changes (
                    incoming_document_id,
                    previous_due_date,
                    new_due_date,
                    reason,
                    changed_by_user_id
                )
                VALUES (
                    :incoming_document_id,
                    :previous_due_date,
                    :new_due_date,
                    :reason,
                    :changed_by_user_id
                )
                RETURNING deadline_change_id
                """
            ),
            {
                "incoming_document_id": int(incoming_document_id),
                "previous_due_date": previous_due_date,
                "new_due_date": new_due_date,
                "reason": reason.strip(),
                "changed_by_user_id": int(changed_by_user_id),
            },
        ).one()
        return int(row[0])

    def insert_transfer(
        self,
        *,
        incoming_document_id: int,
        transfer_scope: str,
        from_responsible_org_unit_id: int,
        to_responsible_org_unit_id: int | None,
        recipient_kind: str | None,
        recipient_user_id: int | None,
        recipient_org_unit_id: int | None,
        recipient_text: str | None,
        comment: str,
        previous_status_code: str,
        new_status_code: str,
        actor_user_id: int,
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.incoming_document_transfers (
                    incoming_document_id,
                    transfer_scope,
                    from_responsible_org_unit_id,
                    to_responsible_org_unit_id,
                    recipient_kind,
                    recipient_user_id,
                    recipient_org_unit_id,
                    recipient_text,
                    comment,
                    previous_status_code,
                    new_status_code,
                    actor_user_id
                )
                VALUES (
                    :incoming_document_id,
                    :transfer_scope,
                    :from_responsible_org_unit_id,
                    :to_responsible_org_unit_id,
                    :recipient_kind,
                    :recipient_user_id,
                    :recipient_org_unit_id,
                    :recipient_text,
                    :comment,
                    :previous_status_code,
                    :new_status_code,
                    :actor_user_id
                )
                RETURNING transfer_id
                """
            ),
            {
                "incoming_document_id": int(incoming_document_id),
                "transfer_scope": transfer_scope,
                "from_responsible_org_unit_id": int(from_responsible_org_unit_id),
                "to_responsible_org_unit_id": to_responsible_org_unit_id,
                "recipient_kind": recipient_kind,
                "recipient_user_id": recipient_user_id,
                "recipient_org_unit_id": recipient_org_unit_id,
                "recipient_text": recipient_text,
                "comment": comment.strip(),
                "previous_status_code": previous_status_code,
                "new_status_code": new_status_code,
                "actor_user_id": int(actor_user_id),
            },
        ).one()
        return int(row[0])

    def resolve_employee_id_for_user(self, user_id: int) -> int | None:
        row = self._conn.execute(
            text(
                """
                SELECT employee_id
                FROM public.users
                WHERE user_id = :user_id
                LIMIT 1
                """
            ),
            {"user_id": int(user_id)},
        ).first()
        if not row or row[0] is None:
            return None
        return int(row[0])

    def org_unit_exists(self, org_unit_id: int) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1
                FROM public.org_units
                WHERE unit_id = :unit_id
                LIMIT 1
                """
            ),
            {"unit_id": int(org_unit_id)},
        ).first()
        return row is not None

    def user_exists(self, user_id: int) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1
                FROM public.users
                WHERE user_id = :user_id
                LIMIT 1
                """
            ),
            {"user_id": int(user_id)},
        ).first()
        return row is not None
