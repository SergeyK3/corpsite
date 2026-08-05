"""Incoming document SQL repository."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.incoming_information.domain.errors import IncomingDocumentNotFoundError
from app.incoming_information.domain.models import (
    IncomingDocumentCreatePayload,
    IncomingDocumentListItem,
    IncomingDocumentSnapshot,
)
from app.incoming_information.domain.status import INITIAL_STATUS_CODE, is_terminal_status_code
from app.incoming_information.infrastructure.list_access_sql import (
    document_list_scope_sql,
    restricted_document_visible_sql,
)


def _compute_is_overdue(*, due_date: date | None, status_code: str, today: date | None = None) -> bool:
    if due_date is None or is_terminal_status_code(status_code):
        return False
    current = today or date.today()
    return due_date < current


def _sender_display(row: dict[str, Any]) -> str:
    kind = str(row.get("sender_kind") or "")
    if kind == "EXTERNAL_TEXT":
        return str(row.get("sender_text") or "").strip()
    if kind == "PERSON":
        return str(row.get("sender_person_name") or "").strip() or f"person:{row.get('sender_person_id')}"
    if kind == "EMPLOYEE":
        return str(row.get("sender_employee_name") or "").strip() or f"employee:{row.get('sender_employee_id')}"
    if kind == "ORG_UNIT":
        return str(row.get("sender_org_unit_name") or "").strip() or f"unit:{row.get('sender_org_unit_id')}"
    return kind


def _addressee_display(row: dict[str, Any]) -> str:
    kind = str(row.get("addressee_kind") or "")
    if kind == "TEXT":
        return str(row.get("addressee_text") or "").strip()
    if kind == "USER":
        return str(row.get("addressee_user_login") or "").strip() or f"user:{row.get('addressee_user_id')}"
    if kind == "EMPLOYEE":
        return str(row.get("addressee_employee_name") or "").strip() or f"employee:{row.get('addressee_employee_id')}"
    if kind == "ORG_UNIT":
        return str(row.get("addressee_org_unit_name") or "").strip() or f"unit:{row.get('addressee_org_unit_id')}"
    if kind == "POSITION":
        return str(row.get("addressee_position_name") or "").strip() or f"position:{row.get('addressee_position_id')}"
    return kind


_SELECT_SNAPSHOT = """
SELECT
    d.incoming_document_id,
    d.registration_number,
    d.registration_year,
    d.registration_seq,
    d.received_at,
    d.registered_at,
    d.document_type_id,
    dt.code AS document_type_code,
    dt.label AS document_type_label,
    d.receipt_channel_id,
    rc.code AS receipt_channel_code,
    rc.label AS receipt_channel_label,
    d.status_id,
    st.code AS status_code,
    st.label AS status_label,
    st.is_terminal AS status_is_terminal,
    d.planned_result_id,
    pr.code AS planned_result_code,
    pr.label AS planned_result_label,
    d.summary,
    d.access_level,
    d.sender_kind,
    d.sender_person_id,
    d.sender_employee_id,
    d.sender_org_unit_id,
    d.sender_text,
    d.addressee_kind,
    d.addressee_user_id,
    d.addressee_employee_id,
    d.addressee_org_unit_id,
    d.addressee_position_id,
    d.addressee_text,
    d.registration_org_unit_id,
    d.responsible_org_unit_id,
    d.resolution_text,
    d.due_date,
    d.planned_result_note,
    d.executed_at,
    d.execution_result,
    d.closed_at,
    d.note,
    d.priority_level,
    d.is_control_document,
    d.received_after_registration_exception,
    d.exception_comment,
    d.transfer_comment,
    d.cancellation_reason,
    d.control_decision,
    d.control_comment,
    d.controller_user_id,
    d.row_version,
    d.closed_by_user_id,
    d.cancelled_at,
    d.cancelled_by_user_id,
    d.transferred_at,
    d.transferred_by_user_id,
    d.resolve_recorded_at,
    d.reopened_at,
    d.reopen_reason,
    d.reopen_count,
    d.external_recipient_kind,
    d.external_recipient_user_id,
    d.external_recipient_org_unit_id,
    d.external_recipient_text,
    d.created_by_user_id,
    d.updated_by_user_id,
    d.created_at,
    d.updated_at,
    sp.full_name AS sender_person_name,
    se.full_name AS sender_employee_name,
    sou.name AS sender_org_unit_name,
    au.login AS addressee_user_login,
    ae.full_name AS addressee_employee_name,
    aou.name AS addressee_org_unit_name,
    ap.name AS addressee_position_name
FROM public.incoming_documents d
JOIN public.incoming_document_types dt ON dt.document_type_id = d.document_type_id
JOIN public.incoming_receipt_channels rc ON rc.receipt_channel_id = d.receipt_channel_id
JOIN public.incoming_document_statuses st ON st.status_id = d.status_id
LEFT JOIN public.incoming_planned_results pr ON pr.planned_result_id = d.planned_result_id
LEFT JOIN public.persons sp ON sp.person_id = d.sender_person_id
LEFT JOIN public.employees se ON se.employee_id = d.sender_employee_id
LEFT JOIN public.org_units sou ON sou.unit_id = d.sender_org_unit_id
LEFT JOIN public.users au ON au.user_id = d.addressee_user_id
LEFT JOIN public.employees ae ON ae.employee_id = d.addressee_employee_id
LEFT JOIN public.org_units aou ON aou.unit_id = d.addressee_org_unit_id
LEFT JOIN public.positions ap ON ap.position_id = d.addressee_position_id
"""


def _row_to_snapshot(row: dict[str, Any]) -> IncomingDocumentSnapshot:
    status_code = str(row["status_code"])
    due_date = row.get("due_date")
    return IncomingDocumentSnapshot(
        incoming_document_id=int(row["incoming_document_id"]),
        registration_number=str(row["registration_number"]),
        registration_year=int(row["registration_year"]),
        registration_seq=int(row["registration_seq"]),
        received_at=row["received_at"],
        registered_at=row["registered_at"],
        document_type_id=int(row["document_type_id"]),
        document_type_code=str(row["document_type_code"]),
        document_type_label=str(row["document_type_label"]),
        receipt_channel_id=int(row["receipt_channel_id"]),
        receipt_channel_code=str(row["receipt_channel_code"]),
        receipt_channel_label=str(row["receipt_channel_label"]),
        status_id=int(row["status_id"]),
        status_code=status_code,
        status_label=str(row["status_label"]),
        status_is_terminal=bool(row["status_is_terminal"]),
        planned_result_id=int(row["planned_result_id"]) if row.get("planned_result_id") is not None else None,
        planned_result_code=str(row["planned_result_code"]) if row.get("planned_result_code") is not None else None,
        planned_result_label=str(row["planned_result_label"]) if row.get("planned_result_label") is not None else None,
        summary=str(row["summary"]),
        access_level=str(row["access_level"]),
        sender_kind=str(row["sender_kind"]),
        sender_person_id=int(row["sender_person_id"]) if row.get("sender_person_id") is not None else None,
        sender_employee_id=int(row["sender_employee_id"]) if row.get("sender_employee_id") is not None else None,
        sender_org_unit_id=int(row["sender_org_unit_id"]) if row.get("sender_org_unit_id") is not None else None,
        sender_text=str(row["sender_text"]) if row.get("sender_text") is not None else None,
        addressee_kind=str(row["addressee_kind"]),
        addressee_user_id=int(row["addressee_user_id"]) if row.get("addressee_user_id") is not None else None,
        addressee_employee_id=int(row["addressee_employee_id"]) if row.get("addressee_employee_id") is not None else None,
        addressee_org_unit_id=int(row["addressee_org_unit_id"]) if row.get("addressee_org_unit_id") is not None else None,
        addressee_position_id=int(row["addressee_position_id"]) if row.get("addressee_position_id") is not None else None,
        addressee_text=str(row["addressee_text"]) if row.get("addressee_text") is not None else None,
        registration_org_unit_id=int(row["registration_org_unit_id"]),
        responsible_org_unit_id=int(row["responsible_org_unit_id"]),
        resolution_text=str(row["resolution_text"]) if row.get("resolution_text") is not None else None,
        due_date=due_date if isinstance(due_date, date) else None,
        planned_result_note=str(row["planned_result_note"]) if row.get("planned_result_note") is not None else None,
        executed_at=row.get("executed_at"),
        execution_result=str(row["execution_result"]) if row.get("execution_result") is not None else None,
        closed_at=row.get("closed_at"),
        note=str(row["note"]) if row.get("note") is not None else None,
        priority_level=str(row["priority_level"]) if row.get("priority_level") is not None else None,
        is_control_document=bool(row.get("is_control_document")),
        received_after_registration_exception=bool(row.get("received_after_registration_exception")),
        exception_comment=str(row["exception_comment"]) if row.get("exception_comment") is not None else None,
        transfer_comment=str(row["transfer_comment"]) if row.get("transfer_comment") is not None else None,
        cancellation_reason=str(row["cancellation_reason"]) if row.get("cancellation_reason") is not None else None,
        control_decision=str(row["control_decision"]) if row.get("control_decision") is not None else None,
        control_comment=str(row["control_comment"]) if row.get("control_comment") is not None else None,
        controller_user_id=int(row["controller_user_id"]) if row.get("controller_user_id") is not None else None,
        row_version=int(row.get("row_version") or 1),
        closed_by_user_id=int(row["closed_by_user_id"]) if row.get("closed_by_user_id") is not None else None,
        cancelled_at=row.get("cancelled_at"),
        cancelled_by_user_id=int(row["cancelled_by_user_id"])
        if row.get("cancelled_by_user_id") is not None
        else None,
        transferred_at=row.get("transferred_at"),
        transferred_by_user_id=int(row["transferred_by_user_id"])
        if row.get("transferred_by_user_id") is not None
        else None,
        resolve_recorded_at=row.get("resolve_recorded_at"),
        reopened_at=row.get("reopened_at"),
        reopen_reason=str(row["reopen_reason"]) if row.get("reopen_reason") is not None else None,
        reopen_count=int(row.get("reopen_count") or 0),
        external_recipient_kind=str(row["external_recipient_kind"])
        if row.get("external_recipient_kind") is not None
        else None,
        external_recipient_user_id=int(row["external_recipient_user_id"])
        if row.get("external_recipient_user_id") is not None
        else None,
        external_recipient_org_unit_id=int(row["external_recipient_org_unit_id"])
        if row.get("external_recipient_org_unit_id") is not None
        else None,
        external_recipient_text=str(row["external_recipient_text"])
        if row.get("external_recipient_text") is not None
        else None,
        created_by_user_id=int(row["created_by_user_id"]),
        updated_by_user_id=int(row["updated_by_user_id"]) if row.get("updated_by_user_id") is not None else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        is_overdue=_compute_is_overdue(due_date=due_date if isinstance(due_date, date) else None, status_code=status_code),
    )


class SqlAlchemyIncomingDocumentRepository:
    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get_status_id_by_code(self, code: str) -> int | None:
        row = self._conn.execute(
            text(
                """
                SELECT status_id
                FROM public.incoming_document_statuses
                WHERE code = :code AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"code": code},
        ).first()
        return int(row[0]) if row else None

    def dictionary_exists(self, table: str, id_value: int) -> bool:
        allowed = {
            "incoming_document_types": "document_type_id",
            "incoming_receipt_channels": "receipt_channel_id",
        }
        if table not in allowed:
            raise ValueError(f"Unsupported dictionary table: {table}")
        id_col = allowed[table]
        row = self._conn.execute(
            text(
                f"""
                SELECT 1
                FROM public.{table}
                WHERE {id_col} = :id_value AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"id_value": int(id_value)},
        ).first()
        return row is not None

    def get_by_id(self, incoming_document_id: int) -> IncomingDocumentSnapshot | None:
        row = self._conn.execute(
            text(_SELECT_SNAPSHOT + " WHERE d.incoming_document_id = :id LIMIT 1"),
            {"id": int(incoming_document_id)},
        ).mappings().first()
        return _row_to_snapshot(dict(row)) if row else None

    def require_by_id(self, incoming_document_id: int) -> IncomingDocumentSnapshot:
        doc = self.get_by_id(incoming_document_id)
        if doc is None:
            raise IncomingDocumentNotFoundError(
                f"Incoming document {incoming_document_id} not found."
            )
        return doc

    def create(
        self,
        *,
        payload: IncomingDocumentCreatePayload,
        registration_number: str,
        registration_year: int,
        registration_seq: int,
        status_id: int,
        registered_at: datetime,
    ) -> IncomingDocumentSnapshot:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.incoming_documents (
                    registration_number,
                    registration_year,
                    registration_seq,
                    received_at,
                    registered_at,
                    document_type_id,
                    receipt_channel_id,
                    status_id,
                    summary,
                    access_level,
                    sender_kind,
                    sender_person_id,
                    sender_employee_id,
                    sender_org_unit_id,
                    sender_text,
                    addressee_kind,
                    addressee_user_id,
                    addressee_employee_id,
                    addressee_org_unit_id,
                    addressee_position_id,
                    addressee_text,
                    registration_org_unit_id,
                    responsible_org_unit_id,
                    received_after_registration_exception,
                    exception_comment,
                    note,
                    is_control_document,
                    priority_level,
                    created_by_user_id,
                    updated_by_user_id
                )
                VALUES (
                    :registration_number,
                    :registration_year,
                    :registration_seq,
                    :received_at,
                    :registered_at,
                    :document_type_id,
                    :receipt_channel_id,
                    :status_id,
                    :summary,
                    :access_level,
                    :sender_kind,
                    :sender_person_id,
                    :sender_employee_id,
                    :sender_org_unit_id,
                    :sender_text,
                    :addressee_kind,
                    :addressee_user_id,
                    :addressee_employee_id,
                    :addressee_org_unit_id,
                    :addressee_position_id,
                    :addressee_text,
                    :registration_org_unit_id,
                    :responsible_org_unit_id,
                    :received_after_registration_exception,
                    :exception_comment,
                    :note,
                    :is_control_document,
                    :priority_level,
                    :created_by_user_id,
                    :created_by_user_id
                )
                RETURNING incoming_document_id
                """
            ),
            {
                "registration_number": registration_number,
                "registration_year": registration_year,
                "registration_seq": registration_seq,
                "received_at": payload.received_at,
                "registered_at": registered_at,
                "document_type_id": payload.document_type_id,
                "receipt_channel_id": payload.receipt_channel_id,
                "status_id": status_id,
                "summary": payload.summary.strip(),
                "access_level": payload.access_level,
                "sender_kind": payload.sender_kind,
                "sender_person_id": payload.sender_person_id,
                "sender_employee_id": payload.sender_employee_id,
                "sender_org_unit_id": payload.sender_org_unit_id,
                "sender_text": payload.sender_text.strip() if payload.sender_text else None,
                "addressee_kind": payload.addressee_kind,
                "addressee_user_id": payload.addressee_user_id,
                "addressee_employee_id": payload.addressee_employee_id,
                "addressee_org_unit_id": payload.addressee_org_unit_id,
                "addressee_position_id": payload.addressee_position_id,
                "addressee_text": payload.addressee_text.strip() if payload.addressee_text else None,
                "registration_org_unit_id": payload.registration_org_unit_id,
                "responsible_org_unit_id": payload.responsible_org_unit_id,
                "received_after_registration_exception": payload.received_after_registration_exception,
                "exception_comment": payload.exception_comment,
                "note": payload.note,
                "is_control_document": payload.is_control_document,
                "priority_level": payload.priority_level,
                "created_by_user_id": payload.created_by_user_id,
            },
        ).one()
        created = self.require_by_id(int(row[0]))
        return created

    def list_documents(
        self,
        *,
        q: str | None,
        status_id: int | None,
        document_type_id: int | None,
        responsible_org_unit_id: int | None,
        responsible_org_unit_ids: set[int] | None,
        overdue_only: bool | None,
        limit: int,
        offset: int,
        sort: str,
        access_user_id: int,
        access_employee_id: int | None,
        restricted_bypass: bool,
    ) -> tuple[list[IncomingDocumentListItem], int]:
        where: list[str] = ["1=1"]
        params: dict[str, Any] = {
            "limit": int(limit),
            "offset": int(offset),
            "access_user_id": int(access_user_id),
            "access_employee_id": access_employee_id,
            "restricted_bypass": bool(restricted_bypass),
        }
        where.append(restricted_document_visible_sql())

        if q:
            where.append(
                """
                (
                    d.registration_number ILIKE :q
                    OR d.summary ILIKE :q
                    OR COALESCE(d.sender_text, '') ILIKE :q
                    OR COALESCE(d.addressee_text, '') ILIKE :q
                )
                """
            )
            params["q"] = f"%{q.strip()}%"

        if status_id is not None:
            where.append("d.status_id = :status_id")
            params["status_id"] = int(status_id)

        if document_type_id is not None:
            where.append("d.document_type_id = :document_type_id")
            params["document_type_id"] = int(document_type_id)

        if responsible_org_unit_id is not None:
            where.append("d.responsible_org_unit_id = :responsible_org_unit_id")
            params["responsible_org_unit_id"] = int(responsible_org_unit_id)

        if responsible_org_unit_ids is not None:
            where.append(
                document_list_scope_sql(
                    scope_param="scope_unit_ids",
                    bypass_param="restricted_bypass",
                )
            )
            params["scope_unit_ids"] = list(responsible_org_unit_ids)

        if overdue_only:
            where.append(
                """
                d.due_date IS NOT NULL
                AND d.due_date < CURRENT_DATE
                AND st.code NOT IN ('CLOSED', 'TRANSFERRED', 'CANCELLED')
                """
            )

        where_sql = " AND ".join(where)
        order_sql = "d.registered_at DESC, d.incoming_document_id DESC"
        if sort == "due_date":
            order_sql = "d.due_date ASC NULLS LAST, d.registered_at DESC"

        total_row = self._conn.execute(
            text(
                f"""
                SELECT COUNT(*) AS total
                FROM public.incoming_documents d
                JOIN public.incoming_document_statuses st ON st.status_id = d.status_id
                WHERE {where_sql}
                """
            ),
            params,
        ).one()
        total = int(total_row[0])

        rows = self._conn.execute(
            text(
                f"""
                SELECT
                    d.incoming_document_id,
                    d.registration_number,
                    d.registered_at,
                    dt.label AS document_type_label,
                    d.summary,
                    d.sender_kind,
                    d.sender_text,
                    d.sender_person_id,
                    d.sender_employee_id,
                    d.sender_org_unit_id,
                    d.addressee_kind,
                    d.addressee_text,
                    d.addressee_user_id,
                    d.addressee_employee_id,
                    d.addressee_org_unit_id,
                    d.addressee_position_id,
                    d.due_date,
                    st.code AS status_code,
                    st.label AS status_label,
                    d.access_level,
                    d.responsible_org_unit_id,
                    sp.full_name AS sender_person_name,
                    se.full_name AS sender_employee_name,
                    sou.name AS sender_org_unit_name,
                    au.login AS addressee_user_login,
                    ae.full_name AS addressee_employee_name,
                    aou.name AS addressee_org_unit_name,
                    ap.name AS addressee_position_name,
                    pe.full_name AS primary_executor_name
                FROM public.incoming_documents d
                JOIN public.incoming_document_types dt ON dt.document_type_id = d.document_type_id
                JOIN public.incoming_document_statuses st ON st.status_id = d.status_id
                LEFT JOIN public.persons sp ON sp.person_id = d.sender_person_id
                LEFT JOIN public.employees se ON se.employee_id = d.sender_employee_id
                LEFT JOIN public.org_units sou ON sou.unit_id = d.sender_org_unit_id
                LEFT JOIN public.users au ON au.user_id = d.addressee_user_id
                LEFT JOIN public.employees ae ON ae.employee_id = d.addressee_employee_id
                LEFT JOIN public.org_units aou ON aou.unit_id = d.addressee_org_unit_id
                LEFT JOIN public.positions ap ON ap.position_id = d.addressee_position_id
                LEFT JOIN LATERAL (
                    SELECT e.full_name
                    FROM public.incoming_document_assignments a
                    JOIN public.employees e ON e.employee_id = a.assignee_employee_id
                    WHERE a.incoming_document_id = d.incoming_document_id
                      AND a.role = 'PRIMARY'
                      AND a.completed_at IS NULL
                      AND a.cancelled_at IS NULL
                    ORDER BY a.assigned_at DESC
                    LIMIT 1
                ) pe ON TRUE
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

        items: list[IncomingDocumentListItem] = []
        for row in rows:
            mapping = dict(row)
            status_code = str(mapping["status_code"])
            due_date = mapping.get("due_date")
            items.append(
                IncomingDocumentListItem(
                    incoming_document_id=int(mapping["incoming_document_id"]),
                    registration_number=str(mapping["registration_number"]),
                    registered_at=mapping["registered_at"],
                    document_type_label=str(mapping["document_type_label"]),
                    summary=str(mapping["summary"]),
                    sender_display=_sender_display(mapping),
                    addressee_display=_addressee_display(mapping),
                    primary_executor_display=str(mapping["primary_executor_name"]).strip()
                    if mapping.get("primary_executor_name")
                    else None,
                    due_date=due_date if isinstance(due_date, date) else None,
                    status_code=status_code,
                    status_label=str(mapping["status_label"]),
                    access_level=str(mapping["access_level"]),
                    responsible_org_unit_id=int(mapping["responsible_org_unit_id"]),
                    is_overdue=_compute_is_overdue(
                        due_date=due_date if isinstance(due_date, date) else None,
                        status_code=status_code,
                    ),
                )
            )
        return items, total

    def user_is_active_assignee(self, incoming_document_id: int, user_id: int) -> bool:
        row = self._conn.execute(
            text(
                """
                SELECT 1
                FROM public.incoming_document_assignments
                WHERE incoming_document_id = :incoming_document_id
                  AND assignee_user_id = :user_id
                  AND completed_at IS NULL
                  AND cancelled_at IS NULL
                LIMIT 1
                """
            ),
            {"incoming_document_id": int(incoming_document_id), "user_id": int(user_id)},
        ).first()
        return row is not None

    def resolve_initial_status_id(self) -> int:
        status_id = self.get_status_id_by_code(INITIAL_STATUS_CODE)
        if status_id is None:
            raise RuntimeError(f"Missing incoming status seed: {INITIAL_STATUS_CODE}")
        return status_id
