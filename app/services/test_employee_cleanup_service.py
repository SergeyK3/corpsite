"""Fail-closed physical cleanup of explicitly marked test employees.

The plan is built from the live PostgreSQL FK catalog.  A row is removed only
when an exact, reviewed ownership edge reaches it.  Every other incoming FK
is a blocker, including SET NULL and CASCADE edges.  This prevents a future
schema change from silently widening the deletion contour.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import engine
from app.person_photos.infrastructure.photo_storage import (
    canonical_photo_absolute_path, delete_canonical_photo_file,
)
from app.personnel_intake.infrastructure.photo_storage import (
    delete_intake_photo, intake_photo_path, intake_photo_storage_root, normalize_intake_photo_file_id,
    resolve_path_within_root,
)

logger = logging.getLogger(__name__)


class TestEmployeeCleanupError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


# The existing authentication projection defines the system administrator by
# primary role_id=2.  A matching role code or delegated grant alone is not enough.
SYSTEM_ADMIN_ROLE_ID = 2
SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
PERSONNEL_STORAGE_KEY = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
PERSONNEL_BUNDLE_FILE = re.compile(r"^(?:original|page-(?:[1-9]|1[0-9]|20)\.png)$")

# These exact FK references describe historical activity, not ownership.
# The original identity is kept in an append-only sidecar before SET NULL.
RETAINED_HISTORY = {
    ("users", "personnel_file_events", "actor_id"),
    ("users", "personnel_file_versions", "uploaded_by"),
    ("users", "personnel_file_versions", "decided_by"),
    ("users", "security_audit_log", "actor_user_id"),
    ("users", "security_audit_log", "target_user_id"),
    ("persons", "security_audit_log", "target_person_id"),
    ("employees", "security_audit_log", "target_employee_id"),
    ("users", "tasks", "created_by_user_id"),
    ("users", "tasks", "initiator_user_id"),
    ("users", "tasks", "approver_user_id"),
    ("users", "user_linkage_execute_items", "user_id"),
    ("employees", "user_linkage_execute_items", "proposed_employee_id"),
    ("users", "employee_onboarding_notifications", "actor_user_id"),
    ("electronic_hire_applications", "electronic_hire_approval_tasks", "application_id"),
    ("employee_onboardings", "employee_onboarding_notifications", "onboarding_id"),
    ("employee_onboarding_checklist_items", "employee_onboarding_notifications", "item_id"),
    ("employees", "ppr_stage0_cohort_participants", "employee_id"),
    ("persons", "ppr_stage0_cohort_participants", "person_id"),
}
HISTORY_KEYS = {"personnel_file_events": "event_id", "personnel_file_versions": "version_id",
                "security_audit_log": "audit_id", "tasks": "task_id",
                "user_linkage_execute_items": "item_id",
                "employee_onboarding_notifications": "notification_id",
                "electronic_hire_approval_tasks": "task_id",
                "ppr_stage0_cohort_participants": "stage0_participant_id"}

# Exact owner edges.  Shared reports, authorship, signatories, journal numbers,
# and references from other employees are deliberately absent.
OWNED: dict[str, dict[str, set[str]]] = {
    "persons": {
        "person_assignments": {"person_id"},
        "person_contacts": {"person_id"},
        "person_education": {"person_id"},
        "person_external_employment": {"person_id"},
        "person_military_service": {"person_id"},
        "person_photos": {"person_id"},
        "person_photo_sources": {"person_id"},
        "person_relatives": {"person_id"},
        "person_status_facts": {"person_id"},
        "person_telegram_bindings": {"person_id"},
        "person_telegram_bot_activations": {"person_id"},
        "person_training": {"person_id"},
        "person_card_change_requests": {"person_id"},
        "person_card_change_documents": {"person_id"},
        "person_card_record_documents": {"person_id"},
        "person_relative_change_requests": {"person_id"},
        "personnel_file_sets": {"person_id"},
        "personnel_file_events": {"person_id"},
        "personnel_applications": {"person_id"},
        "personnel_intake_reconciliation_decisions": {"person_id"},
        "personnel_migration_runs": {"person_id"},
        "personnel_record_events": {"person_id"},
        "personnel_record_metadata": {"person_id"},
        "verification_tasks": {"person_id"},
        "verification_attestations": {"person_id"},
        "ppr_command_executions": {"person_id"},
        "ppr_migration_projection_outbox": {"person_id"},
        "ppr_migration_section_status_projection": {"person_id"},
        "ppr_section_manual_correction_events": {"person_id"},
    },
    "employees": {
        "employee_assignment_links": {"employee_id"},
        "employee_documents": {"employee_id"},
        "employee_events": {"employee_id"},
        "employee_identities": {"employee_id"},
        "employee_import_profile_overrides": {"employee_id"},
        "employee_onboardings": {"employee_id"},
        "employee_termination_records": {"employee_id"},
        "enrollment_history": {"employee_id"},
        "hr_change_events": {"employee_id"},
        "hr_import_document_candidates": {"employee_id"},
        "hr_import_normalized_records": {"employee_id"},
        "hr_import_rows": {"employee_id"},
        "identity_reconciliation_items": {"employee_id"},
        "personnel_migration_runs": {"employee_context_id"},
        "personnel_record_events": {"employee_context_id"},
        "person_education": {"employee_context_id"},
        "person_training": {"employee_context_id"},
        "person_status_facts": {"employee_context_id"},
        "users": {"employee_id"},
    },
    "users": {
        "notifications": {"recipient_user_id"},
        "telegram_bind_codes": {"user_id"},
        "telegram_password_recovery_requests": {"user_id"},
        "tg_bindings": {"user_id"},
        "user_org_units": {"user_id"},
        "org_unit_managers": {"user_id"},
        "personnel_visibility_assignments": {"target_user_id"},
        "personnel_event_visibility_assignments": {"target_user_id"},
        "personnel_file_inbox": {"user_id"},
    },
    "person_assignments": {
        "employee_assignment_links": {"assignment_id"},
        "enrollment_history": {"assignment_id"},
        "enrollment_queue": {"assignment_id"},
    },
    "personnel_applications": {
        "electronic_hire_applications": {"application_id"},
        "employee_onboardings": {"application_id"},
        "personnel_application_blockers": {"application_id"},
        "personnel_application_lifecycle_audit": {"application_id"},
        "personnel_application_resolution_audit": {"application_id"},
        "personnel_intake_drafts": {"application_id"},
        "personnel_intake_links": {"application_id"},
        "personnel_intake_reconciliation_decisions": {"application_id"},
        "personnel_intake_section_reviews": {"application_id"},
        "personnel_intake_transfers": {"application_id"},
    },
    "personnel_orders": {
        "personnel_order_items": {"order_id"},
        "personnel_order_attachments": {"order_id"},
        "personnel_order_editorial_blocks": {"order_id"},
        "personnel_order_evidence_scopes": {"order_id"},
        "personnel_order_localized_texts": {"order_id"},
        "personnel_order_prints": {"order_id"},
        "personnel_order_lifecycle_audit": {"order_id"},
        "personnel_order_template_applications": {"order_id"},
        "employee_events": {"order_id"},
    },
    "personnel_order_items": {
        "personnel_order_item_bases": {"order_item_id"},
        "personnel_order_item_editorial_blocks": {"order_item_id"},
        "personnel_order_template_applications": {"order_item_id"},
        "employee_events": {"order_item_id"},
    },
    "personnel_intake_links": {
        "electronic_hire_link_deliveries": {"link_id"},
        "personnel_intake_drafts": {"link_id"},
    },
    "person_photos": {"person_photo_sources": {"person_photo_id"}},
    "employee_documents": {
        "hr_import_document_candidates": {"document_id"},
        "hr_import_normalized_records": {"document_id"},
    },
    "personnel_file_sets": {"personnel_file_versions": {"set_id"}},
    "employee_onboardings": {
        "employee_onboarding_checklist_items": {"onboarding_id"},
        "employee_onboarding_task_audit": {"onboarding_id"},
    },
    "employee_onboarding_checklist_items": {
        "employee_onboarding_checklist_attachments": {"item_id"},
        "employee_onboarding_task_audit": {"item_id"},
    },
    "electronic_hire_applications": {
        "electronic_hire_attachments": {"application_id"},
        "electronic_hire_link_deliveries": {"application_id"},
        "electronic_hire_notifications": {"application_id"},
        "electronic_hire_position_requests": {"application_id"},
        "electronic_hire_visas": {"application_id"},
    },
    "employee_termination_records": {"employee_termination_record_audit": {"termination_record_id"}},
    "person_card_change_requests": {
        "person_card_change_events": {"request_id"},
        "person_card_change_documents": {"request_id"},
        "person_card_record_documents": {"request_id"},
    },
    "person_card_change_documents": {
        "person_card_record_documents": {"document_id"},
    },
    "person_relative_change_requests": {
        "person_relative_change_events": {"request_id"},
    },
}


@dataclass(frozen=True)
class Edge:
    parent: str
    parent_column: str
    child: str
    child_column: str
    constraint: str


@dataclass(frozen=True)
class CompositeEdge:
    parent: str
    parent_columns: tuple[str, ...]
    child: str
    child_columns: tuple[str, ...]
    constraint: str


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _identity_hash(employee: dict[str, Any]) -> str:
    return _hash({key: employee.get(key) for key in ("employee_id", "person_id", "full_name")})


def _assert_sysadmin(conn: Connection, actor_user_id: int, *, lock: bool = False) -> None:
    suffix = " FOR SHARE OF u" if lock else ""
    row = conn.execute(text(f"""SELECT u.role_id, u.is_active, r.code
        FROM public.users u JOIN public.roles r ON r.role_id=u.role_id
        WHERE u.user_id=:uid{suffix}"""), {"uid": actor_user_id}).mappings().one_or_none()
    if not row or not row["is_active"] or row["role_id"] != SYSTEM_ADMIN_ROLE_ID:
        raise TestEmployeeCleanupError("SYSADMIN_REQUIRED", "Операция доступна только системному администратору.", 403)


def _employee(conn: Connection, employee_id: int, *, lock: bool = False) -> dict[str, Any]:
    suffix = " FOR UPDATE" if lock else ""
    row = conn.execute(text(f"SELECT * FROM public.employees WHERE employee_id=:id{suffix}"), {"id": employee_id}).mappings().one_or_none()
    if row is None:
        raise TestEmployeeCleanupError("EMPLOYEE_NOT_FOUND", "Сотрудник не найден.", 404)
    return dict(row)


def mark_employee(*, employee_id: int, actor_user_id: int, evidence: str, confirmed_name: str) -> dict[str, Any]:
    evidence = evidence.strip()
    if len(evidence) < 12 or len(evidence) > 1000:
        raise TestEmployeeCleanupError("EVIDENCE_REQUIRED", "Укажите основание подтверждения тестовой записи (12–1000 символов).", 422)
    with engine.begin() as conn:
        _assert_sysadmin(conn, actor_user_id)
        employee = _employee(conn, employee_id, lock=True)
        if confirmed_name != employee["full_name"]:
            raise TestEmployeeCleanupError("NAME_CONFIRMATION_MISMATCH", "ФИО изменилось. Повторно проверьте запись.", 409)
        if conn.execute(text("SELECT 1 FROM public.users WHERE employee_id=:id AND user_id=:actor"), {"id": employee_id, "actor": actor_user_id}).first():
            raise TestEmployeeCleanupError("OWN_ACCOUNT", "Свою учётную запись отмечать для удаления нельзя.", 403)
        existing = conn.execute(text("SELECT marker_id FROM public.test_employee_marks WHERE employee_id=:id"), {"id": employee_id}).scalar_one_or_none()
        if existing:
            raise TestEmployeeCleanupError("ALREADY_MARKED", "Тестовая запись уже отмечена.", 409)
        marker_id = conn.execute(text("""INSERT INTO public.test_employee_marks
            (employee_id,person_id,full_name,snapshot_hash,evidence,marked_by_user_id)
            VALUES (:id,:person_id,:name,:digest,:evidence,:actor) RETURNING marker_id"""), {
                "id": employee_id, "person_id": employee.get("person_id"),
                "name": employee["full_name"], "digest": _identity_hash(employee),
                "evidence": evidence, "actor": actor_user_id,
            }).scalar_one()
    return {"marker_id": int(marker_id), "employee_id": employee_id}


def _fk_edges(conn: Connection) -> list[Edge]:
    rows = conn.execute(text("""SELECT p.relname parent, c.relname child, pa.attname parent_column,
        ca.attname child_column, con.conname constraint_name
        FROM pg_constraint con
        JOIN pg_class p ON p.oid=con.confrelid JOIN pg_class c ON c.oid=con.conrelid
        JOIN pg_namespace pn ON pn.oid=p.relnamespace
        JOIN pg_namespace cn ON cn.oid=c.relnamespace
        JOIN pg_attribute pa ON pa.attrelid=p.oid AND pa.attnum=con.confkey[1]
        JOIN pg_attribute ca ON ca.attrelid=c.oid AND ca.attnum=con.conkey[1]
        WHERE con.contype='f' AND cardinality(con.conkey)=1
          AND pn.nspname='public' AND cn.nspname='public'
        ORDER BY p.relname,c.relname,con.conname""")).mappings()
    return [Edge(str(r["parent"]), str(r["parent_column"]), str(r["child"]),
                 str(r["child_column"]), str(r["constraint_name"])) for r in rows]


def _composite_fk_edges(conn: Connection) -> list[CompositeEdge]:
    rows = conn.execute(text("""SELECT p.relname parent,c.relname child,con.conname constraint_name,
        ARRAY(SELECT a.attname FROM unnest(con.confkey) WITH ORDINALITY AS x(attnum,ord)
              JOIN pg_attribute a ON a.attrelid=p.oid AND a.attnum=x.attnum ORDER BY x.ord) parent_columns,
        ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY AS x(attnum,ord)
              JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=x.attnum ORDER BY x.ord) child_columns
        FROM pg_constraint con
        JOIN pg_class p ON p.oid=con.confrelid JOIN pg_class c ON c.oid=con.conrelid
        JOIN pg_namespace pn ON pn.oid=p.relnamespace JOIN pg_namespace cn ON cn.oid=c.relnamespace
        WHERE con.contype='f' AND cardinality(con.conkey)>1
          AND pn.nspname='public' AND cn.nspname='public'""")).mappings()
    return [CompositeEdge(str(r["parent"]), tuple(r["parent_columns"]), str(r["child"]),
                          tuple(r["child_columns"]), str(r["constraint_name"])) for r in rows]


def _composite_child_rows(conn: Connection, edge: CompositeEdge,
                          parents: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    if not SAFE_NAME.fullmatch(edge.child) or any(not SAFE_NAME.fullmatch(c) for c in edge.child_columns):
        raise TestEmployeeCleanupError("UNSAFE_CATALOG", "Недопустимое имя столбца внешнего ключа.")
    result: dict[str, dict[str, Any]] = {}
    for parent in parents.values():
        values = [parent.get(column) for column in edge.parent_columns]
        if any(value is None for value in values):
            continue
        where = " AND ".join(f't."{column}"=:v{i}' for i, column in enumerate(edge.child_columns))
        for tid, state in _rows(conn, edge.child, where, {f"v{i}": value for i, value in enumerate(values)}):
            result[tid] = state
    return list(result.items())


def _rows(conn: Connection, table: str, where: str, params: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    if not SAFE_NAME.fullmatch(table):
        raise AssertionError("Unsafe catalog identifier")
    return [(str(row["tid"]), dict(row["state"])) for row in conn.execute(
        text(f'SELECT t.ctid::text tid,to_jsonb(t) state FROM public."{table}" t WHERE {where}'), params
    ).mappings()]


def _order_ids(conn: Connection, employee_id: int) -> list[int]:
    return [int(value) for value in conn.execute(text("""SELECT DISTINCT order_id
        FROM public.personnel_order_items WHERE employee_id=:id ORDER BY order_id"""), {"id": employee_id}).scalars()]


def _order_state(conn: Connection, order_id: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    order = dict(conn.execute(text("SELECT * FROM public.personnel_orders WHERE order_id=:id"),
                              {"id": order_id}).mappings().one())
    items = [dict(row) for row in conn.execute(text("""SELECT * FROM public.personnel_order_items
        WHERE order_id=:id ORDER BY item_number,item_id"""), {"id": order_id}).mappings()]
    return order, items


def _order_digest(order: dict[str, Any], items: list[dict[str, Any]]) -> str:
    return _hash({"order": order, "items": items})


def mark_personnel_order(*, employee_id: int, order_id: int, actor_user_id: int,
                         evidence: str | None, confirmed_number: str,
                         expected_snapshot_hash: str, confirmed_test_origin: bool) -> dict[str, Any]:
    if not confirmed_test_origin:
        raise TestEmployeeCleanupError("ORDER_CONFIRMATION_REQUIRED",
            "Подтвердите тестовое происхождение приказа.", 422)
    with engine.begin() as conn:
        _assert_sysadmin(conn, actor_user_id, lock=True)
        employee = _employee(conn, employee_id, lock=True)
        if conn.execute(text("SELECT 1 FROM public.users WHERE employee_id=:employee AND user_id=:actor"),
                        {"employee": employee_id, "actor": actor_user_id}).first():
            raise TestEmployeeCleanupError("OWN_ACCOUNT", "Свою учётную запись удалять нельзя.", 403)
        if not conn.execute(text("SELECT 1 FROM public.test_employee_marks WHERE employee_id=:id"),
                            {"id": employee_id}).first():
            raise TestEmployeeCleanupError("EMPLOYEE_NOT_MARKED", "Сначала подтвердите тестовое происхождение сотрудника.")
        order, items = _order_state(conn, order_id)
        if not items or not any(item["employee_id"] == employee_id for item in items):
            raise TestEmployeeCleanupError("ORDER_NOT_RELATED", "Приказ не относится к этому сотруднику.", 404)
        if str(order.get("order_number") or "") != confirmed_number:
            raise TestEmployeeCleanupError("ORDER_NUMBER_MISMATCH", "Номер приказа изменился. Обновите предварительный просмотр.")
        digest = _order_digest(order, items)
        if digest != expected_snapshot_hash:
            raise TestEmployeeCleanupError("ORDER_SNAPSHOT_CHANGED",
                "Приказ изменился. Обновите предварительный просмотр.", 409)
        existing = conn.execute(text("""SELECT marker_id,order_snapshot_hash
            FROM public.test_personnel_order_marks
            WHERE order_id=:id ORDER BY marker_id DESC LIMIT 1"""),
            {"id": order_id}).mappings().one_or_none()
        if existing and existing["order_snapshot_hash"] == digest:
            return {"order_id": order_id, "marker_id": int(existing["marker_id"])}
        evidence = (evidence or "").strip()
        if not 20 <= len(evidence) <= 2000:
            raise TestEmployeeCleanupError("ORDER_EVIDENCE_REQUIRED",
                "Укажите документированное основание тестового происхождения приказа (20–2000 символов).", 422)
        if evidence.casefold() in {employee["full_name"].casefold(),
                                   str(order.get("order_number") or "").casefold()}:
            raise TestEmployeeCleanupError("ORDER_EVIDENCE_REQUIRED", "Одного ФИО или номера приказа недостаточно.", 422)
        marker_id = conn.execute(text("""INSERT INTO public.test_personnel_order_marks
            (order_id,order_number,order_snapshot_hash,evidence,marked_by_user_id)
            VALUES (:order_id,:number,:digest,:evidence,:actor) RETURNING marker_id"""), {
                "order_id": order_id, "number": order.get("order_number"),
                "digest": digest, "evidence": evidence,
                "actor": actor_user_id,
            }).scalar_one()
    return {"order_id": order_id, "marker_id": int(marker_id)}


def _order_blockers(conn: Connection, order_ids: list[int], employee_id: int) -> tuple[list[str], list[dict[str, Any]]]:
    blockers: list[str] = []
    details: list[dict[str, Any]] = []
    for order_id in order_ids:
        order, items = _order_state(conn, order_id)
        mark = conn.execute(text("""SELECT * FROM public.test_personnel_order_marks
            WHERE order_id=:id ORDER BY marker_id DESC LIMIT 1"""),
                            {"id": order_id}).mappings().one_or_none()
        others = [item for item in items if item["employee_id"] != employee_id]
        people = [dict(row) for row in conn.execute(text("""SELECT DISTINCT i.employee_id,e.full_name
            FROM public.personnel_order_items i LEFT JOIN public.employees e ON e.employee_id=i.employee_id
            WHERE i.order_id=:id ORDER BY i.employee_id"""), {"id": order_id}).mappings()]
        signed = conn.execute(text("""SELECT count(*) FROM public.personnel_order_prints
            WHERE order_id=:id AND is_signed_copy=true"""), {"id": order_id}).scalar_one()
        attachments = conn.execute(text("""SELECT count(*) FROM public.personnel_order_attachments
            WHERE order_id=:id"""), {"id": order_id}).scalar_one()
        acknowledged = conn.execute(text("""SELECT count(*) FROM public.personnel_order_acknowledgement_events
            WHERE order_id=:id"""), {"id": order_id}).scalar_one()
        event_others = conn.execute(text("""SELECT count(*) FROM public.employee_events
            WHERE order_id=:id AND employee_id IS DISTINCT FROM :employee"""),
            {"id": order_id, "employee": employee_id}).scalar_one()
        details.append({"order_id": order_id, "order_number": order.get("order_number"),
                        "order_date": str(order["order_date"]) if order.get("order_date") else None,
                        "order_type_code": order["order_type_code"], "status": order["status"],
                        "item_count": len(items), "employees": people,
                        "signed_copy_count": signed, "attachment_count": attachments,
                        "acknowledgement_count": acknowledged,
                        "snapshot_hash": _order_digest(order, items),
                        "is_test_marked": mark is not None and
                            mark["order_snapshot_hash"] == _order_digest(order, items),
                        "marker_id": int(mark["marker_id"]) if mark else None})
        if others:
            blockers.append(f"Приказ ID {order_id} содержит пункты других сотрудников")
        if event_others:
            blockers.append(f"Приказ ID {order_id} связан с кадровыми событиями других сотрудников")
        if mark is None:
            blockers.append(f"Подтвердите тестовое происхождение приказа ID {order_id} отдельно")
        elif mark["order_snapshot_hash"] != _order_digest(order, items):
            blockers.append(f"Приказ ID {order_id} изменился после подтверждения тестового происхождения")
        if order.get("signed_by_employee_id") is not None:
            blockers.append(f"Приказ ID {order_id} подписан")
        if signed:
            blockers.append(f"Приказ ID {order_id} содержит подписанную копию")
        if attachments:
            blockers.append(f"Приказ ID {order_id} содержит вложения с неустановленным статусом подписи")
        if acknowledged:
            blockers.append(f"Приказ ID {order_id} содержит события ознакомления")
        if order["status"] not in {"DRAFT", "READY_FOR_SIGNATURE", "REGISTERED"}:
            blockers.append(f"Статус приказа ID {order_id} требует отдельного решения")
    return blockers, details


def _add(plan: dict[str, dict[str, dict[str, Any]]], table: str,
         rows: list[tuple[str, dict[str, Any]]]) -> bool:
    bucket = plan.setdefault(table, {})
    changed = False
    for tid, state in rows:
        if tid not in bucket:
            bucket[tid] = state
            changed = True
    return changed


def _owned(edge: Edge) -> bool:
    return edge.child_column in OWNED.get(edge.parent, {}).get(edge.child, set())


def _edge_rows(conn: Connection, edge: Edge,
               parents: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    values = sorted({state[edge.parent_column] for state in parents.values()
                     if state.get(edge.parent_column) is not None})
    if not values:
        return []
    # to_jsonb converts UUID keys to strings. PostgreSQL cannot compare a
    # UUID column to a text[] bind, so use the catalog's parent column type.
    parent_type = conn.execute(text("""SELECT a.atttypid::regtype::text FROM pg_attribute a
        JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relname=:table AND a.attname=:column"""),
        {"table": edge.parent, "column": edge.parent_column}).scalar_one()
    if parent_type not in {"bigint", "integer", "smallint", "uuid", "text", "character varying"}:
        raise TestEmployeeCleanupError("UNSAFE_CATALOG", "Неизвестный тип ключа связанной записи.")
    return _rows(conn, edge.child,
                 f't."{edge.child_column}" = ANY(CAST(:values AS {parent_type}[]))',
                 {"values": values})


def _logical_blockers(conn: Connection, plan: dict[str, dict[str, dict[str, Any]]],
                      employee_id: int, person_id: int | None, user_ids: list[int],
                      edges: list[Edge]) -> list[str]:
    # Exact, unkeyed identity columns are checked as well as foreign keys.
    # This is intentionally conservative: new logical relations block execution.
    physical = {(edge.child, edge.child_column) for edge in edges}
    identities: dict[str, list[Any]] = {"employee_id": [employee_id],
                                       "employee_context_id": [employee_id],
                                       "user_id": user_ids}
    if person_id is not None:
        identities["person_id"] = [person_id]
    # Also inspect unkeyed references to the primary keys of every selected
    # child (orders, applications, assignments, photos, and so on).
    primary_keys = conn.execute(text("""SELECT c.relname table_name,a.attname column_name
        FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=con.conkey[1]
        WHERE con.contype='p' AND cardinality(con.conkey)=1 AND n.nspname='public'""")).mappings()
    for key in primary_keys:
        table, column = str(key["table_name"]), str(key["column_name"])
        if table not in plan or not column.endswith("_id"):
            continue
        # event_id is a local sequence in many independent append-only event
        # streams. Matching its bare numeric value cannot establish a link.
        # Actual FK references to personnel_file_events are checked above.
        if table in {"personnel_file_events", "person_card_change_events",
                     "person_relative_change_events"} and column == "event_id":
            continue
        values = [state.get(column) for state in plan[table].values()]
        identities.setdefault(column, []).extend(value for value in values
                                               if isinstance(value, int) or
                                               (isinstance(value, str) and PERSONNEL_STORAGE_KEY.fullmatch(value)))
    rows = conn.execute(text("""SELECT columns.table_name,columns.column_name,columns.data_type,
               columns.is_identity,columns.column_default
        FROM information_schema.columns columns
        JOIN information_schema.tables tables
          ON tables.table_schema=columns.table_schema AND tables.table_name=columns.table_name
        WHERE columns.table_schema='public' AND tables.table_type='BASE TABLE'
          AND columns.column_name=ANY(:column_names)
        ORDER BY columns.table_name,columns.column_name"""),
        {"column_names": sorted(identities)}).mappings()
    blockers: list[str] = []
    if user_ids and conn.execute(text("SELECT to_regclass('public.training_identity_links') IS NOT NULL")).scalar_one():
        linked_training_users = conn.execute(text("""SELECT count(*)
            FROM public.training_identity_links
            WHERE source_kind='local' AND source_user_id=ANY(:ids)"""),
            {"ids": user_ids}).scalar_one()
        if linked_training_users:
            blockers.append(f"Учётная запись служит источником для учебных пользователей: {linked_training_users}")
    for row in rows:
        table, column = str(row["table_name"]), str(row["column_name"])
        # Generated journal IDs are local sequences. A numeric collision is
        # not a relationship; actual FK references are checked above.
        if column == "audit_id" and (row["is_identity"] == "YES"
                                     or str(row["column_default"] or "").startswith("nextval(")):
            continue
        # These three event streams allocate event_id independently. A numeric
        # collision is not a reference; genuine FKs are checked above.
        if column == "event_id" and table in {
            "personnel_record_events", "person_card_change_events", "personnel_file_events",
            "person_relative_change_events",
        }:
            continue
        # These two item streams have independent local sequences.  Their
        # identically named IDs are not a relationship; genuine FKs are
        # inspected through the catalog above.
        if column == "item_id" and table in {
            "personnel_order_items", "employee_onboarding_checklist_items",
        } and ({"personnel_order_items", "employee_onboarding_checklist_items"} - {table}) & plan.keys():
            continue
        if row["data_type"] not in {"smallint", "integer", "bigint", "numeric", "uuid"}:
            continue
        if (table, column) in physical or table in {
            "test_employee_marks", "test_employee_deletion_audit", "test_employee_file_cleanup",
            "test_employee_retained_history_refs", "test_employee_history_snapshots",
            "test_personnel_order_marks", "test_personnel_order_deletion_audit",
        }:
            continue
        values = [value for value in identities.get(column, [])
                  if (isinstance(value, str) and PERSONNEL_STORAGE_KEY.fullmatch(value))
                  == (row["data_type"] == "uuid")]
        if not values or not SAFE_NAME.fullmatch(table):
            continue
        cast = "CAST(:values AS uuid[])" if row["data_type"] == "uuid" else ":values"
        found = _rows(conn, table, f't."{column}" = ANY({cast})', {"values": values})
        unknown = sum(tid not in plan.get(table, {}) for tid, _ in found)
        if unknown:
            blockers.append(f"Неописанная связь {table}.{column}: {unknown}")
    return blockers


def _reviewed_card_blockers(plan: dict[str, dict[str, dict[str, Any]]],
                            employee_id: int, person_id: int | None) -> list[str]:
    """Validate both sides of every reviewed-card ownership path before deletion."""
    blockers: list[str] = []
    requests = {str(row["request_id"]): row for row in
                plan.get("person_card_change_requests", {}).values()}
    documents = {str(row["document_id"]): row for row in
                 plan.get("person_card_change_documents", {}).values()}
    relatives = {int(row["relative_id"]): row for row in
                 plan.get("person_relatives", {}).values()}
    known_sections = {"contacts", "education", "training", "category",
                      "employment_biography", "languages", "awards"}
    for row in requests.values():
        if (row.get("person_id") != person_id
                or row.get("employee_context_id") not in (None, employee_id)
                or row.get("section") not in known_sections):
            blockers.append("Заявка на изменение карточки содержит неоднозначного владельца или раздел")
    for row in documents.values():
        request = requests.get(str(row["request_id"]))
        if (row.get("person_id") != person_id or request is None
                or request.get("person_id") != person_id
                or row.get("section") != request.get("section")):
            blockers.append("Документ заявки на карточку связан с другой записью")
    for row in plan.get("person_card_record_documents", {}).values():
        document = documents.get(str(row["document_id"]))
        request = requests.get(str(row["request_id"]))
        if (row.get("person_id") != person_id or document is None or request is None
                or document.get("person_id") != person_id
                or request.get("person_id") != person_id
                or row.get("section") != document.get("section")
                or row.get("section") != request.get("section")):
            blockers.append("Связь документа с разделом карточки принадлежит другой записи")
    for row in plan.get("person_relative_change_requests", {}).values():
        if row.get("person_id") != person_id:
            blockers.append("Заявка на родственника принадлежит другому физическому лицу")
        for column in ("relative_id", "approved_relative_id"):
            relative_id = row.get(column)
            if relative_id is not None and relatives.get(int(relative_id), {}).get("person_id") != person_id:
                blockers.append("Заявка на родственника ссылается на чужую запись")
    return sorted(set(blockers))


def _history_removals(conn: Connection, plan: dict[str, dict[str, dict[str, Any]]],
                      user_ids: list[int]) -> list[dict[str, Any]]:
    """Archive only known participant/delivery rows before severing their FK."""
    result: dict[tuple[str, str], dict[str, Any]] = {}

    def collect(table: str, key: str, where: str, params: dict[str, Any],
                *, pending_only: bool = False) -> None:
        for tid, state in _rows(conn, table, where, params):
            if tid in plan.get(table, {}):
                continue
            source_key = ":".join(str(state[column]) for column in key.split(","))
            disposition = ("CANCELLED" if state.get("status") == "PENDING"
                           else "REMOVED")
            if pending_only and disposition != "CANCELLED":
                continue
            result[(table, source_key)] = {"table": table, "key": source_key,
                                           "tid": tid, "state": state,
                                           "disposition": disposition}

    if user_ids:
        collect("task_event_recipients", "audit_id,user_id", "t.user_id=ANY(:ids)",
                {"ids": user_ids})
        collect("task_event_deliveries", "audit_id,user_id,channel", "t.user_id=ANY(:ids)",
                {"ids": user_ids})
        collect("employee_onboarding_notification_recipients", "notification_id,user_id",
                "t.user_id=ANY(:ids)", {"ids": user_ids})
        collect("employee_onboarding_notification_deliveries", "notification_id,user_id,channel",
                "t.user_id=ANY(:ids)", {"ids": user_ids})
    notification_ids = [state["notification_id"] for state in
                        plan.get("employee_onboarding_notifications", {}).values()]
    # Notifications are retained, so find them through the owned onboarding.
    onboarding_ids = [state["onboarding_id"] for state in
                      plan.get("employee_onboardings", {}).values()]
    if onboarding_ids:
        notification_ids = [int(value) for value in conn.execute(text("""SELECT notification_id
            FROM public.employee_onboarding_notifications WHERE onboarding_id=ANY(:ids)"""),
            {"ids": onboarding_ids}).scalars()]
    if notification_ids:
        collect("employee_onboarding_notification_deliveries", "notification_id,user_id,channel",
                "t.notification_id=ANY(:ids)", {"ids": notification_ids}, pending_only=True)
    return sorted(result.values(), key=lambda row: (row["table"], row["key"]))


def _preserved_onboarding_history(conn: Connection,
                                  plan: dict[str, dict[str, dict[str, Any]]],
                                  removed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    onboarding_ids = [state["onboarding_id"] for state in
                      plan.get("employee_onboardings", {}).values()]
    if not onboarding_ids:
        return []
    notification_ids = [int(value) for value in conn.execute(text("""SELECT notification_id
        FROM public.employee_onboarding_notifications WHERE onboarding_id=ANY(:ids)"""),
        {"ids": onboarding_ids}).scalars()]
    if not notification_ids:
        return []
    removed_keys = {(row["table"], row["key"]) for row in removed}
    preserved: list[dict[str, Any]] = []
    for table, key in (("employee_onboarding_notification_recipients", "notification_id,user_id"),
                       ("employee_onboarding_notification_deliveries", "notification_id,user_id,channel")):
        for _, state in _rows(conn, table, "t.notification_id=ANY(:ids)",
                              {"ids": notification_ids}):
            source_key = ":".join(str(state[column]) for column in key.split(","))
            if (table, source_key) not in removed_keys:
                preserved.append({"table": table, "key": source_key, "state": state})
    return sorted(preserved, key=lambda row: (row["table"], row["key"]))


def _historical_safety_blockers(conn: Connection, retained: list[dict[str, Any]],
                                plan: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    blockers: list[str] = []
    for ref in retained:
        state, table = ref["state"], ref["table"]
        if table == "user_linkage_execute_items" and (
                state["status"] != "SKIPPED" or state["action"] != "SKIP_NOT_APPROVED"):
            blockers.append("Операция привязки учётной записи была применена или имеет неоднозначный статус")
        if table == "ppr_stage0_cohort_participants":
            if state.get("retired_at") is not None:
                blockers.append("Участник кадровой когорты уже архивирован")
            cohort_id = state["stage0_cohort_run_id"]
            for run_table in ("ppr_stage_runs", "ppr_stage1_general_runs"):
                if conn.execute(text(f"SELECT 1 FROM public.{run_table} "
                                       "WHERE stage0_cohort_run_id=:id LIMIT 1"),
                                {"id": cohort_id}).first():
                    blockers.append("По замороженной кадровой когорте уже запущен этап обработки")
    return sorted(set(blockers))


def _personnel_bundle(key: str) -> Path:
    if not PERSONNEL_STORAGE_KEY.fullmatch(key):
        raise ValueError("Invalid personnel file storage key")
    configured = os.environ.get("PERSONNEL_FILE_STORAGE_ROOT")
    if not configured:
        raise ValueError("Personnel file storage root is not configured")
    root = Path(configured).resolve(strict=True)
    bundle = root / key
    if bundle.is_symlink() or not bundle.resolve().is_relative_to(root):
        raise ValueError("Personnel file path escapes its storage root")
    if bundle.exists():
        if not bundle.is_dir():
            raise ValueError("Personnel file bundle is not a directory")
        for entry in bundle.iterdir():
            if entry.is_symlink() or not entry.is_file() or not PERSONNEL_BUNDLE_FILE.fullmatch(entry.name):
                raise ValueError("Personnel file bundle contains an unrecognized entry")
    return bundle


def _bundle_has_external_references(conn: Connection,
                                    plan: dict[str, dict[str, dict[str, Any]]],
                                    key: str) -> bool:
    # Reviewed card attachments and personnel-file versions share the same
    # private storage. A new owner must be reviewed before physical cleanup.
    for table in ("personnel_file_versions", "person_card_change_documents"):
        if not conn.scalar(text("SELECT to_regclass(:name) IS NOT NULL"),
                           {"name": f"public.{table}"}):
            continue
        matching = _rows(conn, table, "t.storage_key::text=:key", {"key": key})
        if any(tid not in plan.get(table, {}) for tid, _ in matching):
            return True
    matching_documents = _rows(conn, "employee_documents", "t.file_url LIKE :needle",
                               {"needle": f"%{key}%"})
    return any(tid not in plan.get("employee_documents", {})
               for tid, _ in matching_documents)


def _file_plan(conn: Connection, plan: dict[str, dict[str, dict[str, Any]]]) -> tuple[list[tuple[str, str]], list[str]]:
    files: list[tuple[str, str]] = []
    blockers: list[str] = []
    for table, rows in plan.items():
        for state in rows.values():
            if table in {"personnel_file_versions", "person_card_change_documents"}:
                key = str(state["storage_key"])
                try:
                    _personnel_bundle(key)
                except (ValueError, OSError) as exc:
                    blockers.append(f"Недопустимое хранилище файла личного дела: {exc}")
                else:
                    if _bundle_has_external_references(conn, plan, key):
                        blockers.append("Файл личного дела используется другой записью")
                    else:
                        files.append(("PERSONNEL_FILE_BUNDLE", key))
            for column in ("storage_rel_path", "storage_path", "file_path", "file_url"):
                value = state.get(column)
                if not value:
                    continue
                if table == "person_photos" and column == "storage_rel_path":
                    try:
                        canonical_photo_absolute_path(str(value))
                    except (ValueError, RuntimeError):
                        blockers.append("Недопустимый путь фотографии")
                    else:
                        files.append(("CANONICAL_PHOTO", str(value)))
                elif table == "electronic_hire_attachments" and column == "storage_path":
                    application_id = state.get("application_id")
                    try:
                        root = resolve_path_within_root(intake_photo_storage_root(),
                                                        "signed-applications", str(int(application_id)))
                        path = Path(str(value)).resolve()
                        if not path.is_relative_to(root):
                            raise ValueError("Unexpected signed-copy path")
                    except (ValueError, TypeError, RuntimeError):
                        blockers.append("Недопустимый путь подписанной копии заявления")
                    else:
                        files.append(("SIGNED_HIRE_COPY", str(path)))
                else:
                    blockers.append(f"Файл {table}.{column} требует отдельного безопасного обработчика")
            # Intake photos are referenced inside the draft JSON rather than a FK.
            if table == "personnel_intake_drafts":
                payload = state.get("payload") or {}
                personal = payload.get("personal") if isinstance(payload, dict) else {}
                file_id = (personal or {}).get("photo_file_id") if isinstance(personal, dict) else None
                if file_id:
                    try:
                        files.append(("INTAKE_PHOTO", f"{int(state['application_id'])}/{normalize_intake_photo_file_id(file_id)}"))
                    except (ValueError, TypeError):
                        blockers.append("Недопустимый идентификатор фото в анкете")
            if table == "person_photo_sources" and state.get("source_application_id") and state.get("source_intake_photo_file_id"):
                try:
                    files.append(("INTAKE_PHOTO", f"{int(state['source_application_id'])}/{normalize_intake_photo_file_id(state['source_intake_photo_file_id'])}"))
                except (ValueError, TypeError):
                    blockers.append("Недопустимый идентификатор исходного фото")
    return sorted(set(files)), sorted(set(blockers))


def _build_plan(conn: Connection, employee_id: int) -> dict[str, Any]:
    employee = _employee(conn, employee_id)
    person_id = int(employee["person_id"]) if employee.get("person_id") is not None else None
    users = conn.execute(text("SELECT user_id,login FROM public.users WHERE employee_id=:id"),
                         {"id": employee_id}).mappings().all()
    user_ids = [int(row["user_id"]) for row in users]
    marker = conn.execute(text("SELECT * FROM public.test_employee_marks WHERE employee_id=:id"),
                          {"id": employee_id}).mappings().one_or_none()
    blockers: list[str] = []
    if marker is None:
        blockers.append("Сотрудник не подтверждён как тестовый системным администратором")
    elif marker["snapshot_hash"] != _identity_hash(employee):
        blockers.append("Данные сотрудника изменились после подтверждения тестового происхождения")
    if person_id is not None:
        other_employees = conn.execute(text("""SELECT count(*) FROM public.employees
            WHERE person_id=:pid AND employee_id<>:eid"""), {"pid": person_id, "eid": employee_id}).scalar_one()
        if other_employees:
            blockers.append("Физическое лицо связано с другим сотрудником")
        if conn.execute(text("SELECT 1 FROM public.persons WHERE merged_into_person_id=:pid LIMIT 1"),
                        {"pid": person_id}).first():
            blockers.append("На физическое лицо ссылается объединённая запись")
    order_ids = _order_ids(conn, employee_id)
    order_blockers, order_details = _order_blockers(conn, order_ids, employee_id)
    blockers.extend(order_blockers)
    edges = _fk_edges(conn)
    composite_edges = _composite_fk_edges(conn)
    by_parent: dict[str, list[Edge]] = defaultdict(list)
    for edge in edges:
        by_parent[edge.parent].append(edge)
    plan: dict[str, dict[str, dict[str, Any]]] = {}
    _add(plan, "employees", _rows(conn, "employees", "t.employee_id=:id", {"id": employee_id}))
    if person_id is not None:
        _add(plan, "persons", _rows(conn, "persons", "t.person_id=:id", {"id": person_id}))
        # ADR-061 provenance intentionally has no FK to persons/photos.
        _add(plan, "person_photo_sources", _rows(conn, "person_photo_sources",
                                                  "t.person_id=:id", {"id": person_id}))
    if order_ids:
        _add(plan, "personnel_orders", _rows(conn, "personnel_orders",
                                               "t.order_id=ANY(:ids)", {"ids": order_ids}))
    # Access grants have a polymorphic target rather than a target FK.
    for kind, ids in (("EMPLOYEE", [employee_id]), ("PERSON", [person_id] if person_id else []),
                      ("USER", user_ids)):
        if ids:
            _add(plan, "access_grants", _rows(conn, "access_grants",
                "t.target_type=:kind AND t.target_id=ANY(:ids)", {"kind": kind, "ids": ids}))
    queue = deque(plan)
    while queue:
        parent = queue.popleft()
        for edge in by_parent.get(parent, []):
            if _owned(edge) and _add(plan, edge.child, _edge_rows(conn, edge, plan[parent])):
                queue.append(edge.child)
    # Assignment grants use a polymorphic target ID and have no target FK.
    assignment_ids = [int(state["assignment_id"])
                      for state in plan.get("person_assignments", {}).values()]
    if assignment_ids:
        _add(plan, "access_grants", _rows(conn, "access_grants",
            "t.target_type='ASSIGNMENT' AND t.target_id=ANY(:ids)",
            {"ids": assignment_ids}))
    blockers.extend(_reviewed_card_blockers(plan, employee_id, person_id))
    archive_remove = _history_removals(conn, plan, user_ids)
    preserved_history = _preserved_onboarding_history(conn, plan, archive_remove)
    removal_tids: dict[str, set[str]] = defaultdict(set)
    for row in archive_remove:
        removal_tids[row["table"]].add(row["tid"])
    retained: list[dict[str, Any]] = []
    blocked_rows: dict[str, set[str]] = defaultdict(set)
    blocked_columns: dict[str, set[str]] = defaultdict(set)
    # A child reached through another owner edge is safe. Every remaining
    # reference, even ON DELETE CASCADE/SET NULL, must be resolved explicitly.
    for parent, parents in list(plan.items()):
        for edge in by_parent.get(parent, []):
            external = [(tid, state) for tid, state in _edge_rows(conn, edge, parents)
                        if tid not in plan.get(edge.child, {})
                        and tid not in removal_tids.get(edge.child, set())]
            if external and (edge.parent, edge.child, edge.child_column) in RETAINED_HISTORY:
                key_column = HISTORY_KEYS[edge.child]
                for _, state in external:
                    retained.append({"table": edge.child, "column": edge.child_column,
                                     "key": str(state[key_column]), "kind": edge.parent,
                                     "id": int(state[edge.child_column]), "state": state})
            elif external:
                blockers.append(f"Внешняя зависимость {edge.child}.{edge.child_column}: {len(external)}")
                blocked_rows[edge.child].update(tid for tid, _ in external)
                blocked_columns[edge.child].add(edge.child_column)
        for edge in composite_edges:
            if edge.parent != parent:
                continue
            external_composite = [tid for tid, _ in _composite_child_rows(conn, edge, parents)
                                  if tid not in plan.get(edge.child, {})
                                  and tid not in removal_tids.get(edge.child, set())]
            unknown = len(external_composite)
            if unknown:
                blockers.append(f"Составная внешняя зависимость {edge.child}.{edge.constraint}: {unknown}")
                blocked_rows[edge.child].update(external_composite)
                blocked_columns[edge.child].update(edge.child_columns)
    blockers.extend(_historical_safety_blockers(conn, retained, plan))
    blockers.extend(_logical_blockers(conn, plan, employee_id, person_id, user_ids, edges))
    files, file_blockers = _file_plan(conn, plan)
    blockers.extend(file_blockers)
    for kind, path in files:
        if kind == "CANONICAL_PHOTO":
            matching = _rows(conn, "person_photos", "t.storage_rel_path=:path", {"path": path})
            if any(tid not in plan.get("person_photos", {}) for tid, _ in matching):
                blockers.append("Файл фотографии используется другой записью")
        elif kind == "SIGNED_HIRE_COPY":
            matching = _rows(conn, "electronic_hire_attachments", "t.storage_path=:path", {"path": path})
            if any(tid not in plan.get("electronic_hire_attachments", {}) for tid, _ in matching):
                blockers.append("Подписанная копия используется другой записью")
    # The exact state digest is checked again under SERIALIZABLE locks at commit.
    state_hash = _hash({"delete": {table: sorted(rows.values(), key=lambda row: _hash(row))
                                   for table, rows in sorted(plan.items())},
                        "retain": sorted(retained, key=lambda row: (row["table"], row["key"], row["column"])),
                        "archive_remove": archive_remove, "preserved_history": preserved_history,
                        "orders": order_details})
    counts = {table: len(rows) for table, rows in sorted(plan.items()) if rows}
    retained_counts = {table: len({row["key"] for row in retained if row["table"] == table})
                       for table in sorted({row["table"] for row in retained})}
    for table in sorted({row["table"] for row in archive_remove}):
        retained_counts[table] = retained_counts.get(table, 0) + sum(
            row["table"] == table for row in archive_remove)
    for table in sorted({row["table"] for row in preserved_history}):
        retained_counts[table] = retained_counts.get(table, 0) + sum(
            row["table"] == table for row in preserved_history)
    retained_keys = lambda table: {row["key"] for row in retained if row["table"] == table}
    history_actions = [
        {"code": "CANCEL_PENDING_DELIVERIES", "count": sum(
            row["disposition"] == "CANCELLED" for row in archive_remove)},
        {"code": "ARCHIVE_COMPLETED_DELIVERIES", "count": sum(
            row["table"] in {"task_event_deliveries", "employee_onboarding_notification_deliveries"}
            and row["disposition"] == "REMOVED" for row in archive_remove)},
        {"code": "KEEP_COMPLETED_DELIVERIES", "count": sum(
            row["table"] == "employee_onboarding_notification_deliveries"
            and row["state"].get("status") == "SENT" for row in preserved_history)},
        {"code": "KEEP_APPROVAL_DECISIONS", "count": len(retained_keys("electronic_hire_approval_tasks"))},
        {"code": "KEEP_PPR_COHORT", "count": len(retained_keys("ppr_stage0_cohort_participants"))},
        {"code": "KEEP_USER_LINKAGE", "count": len(retained_keys("user_linkage_execute_items"))},
        {"code": "KEEP_TASK_ATTRIBUTION", "count": len(retained_keys("tasks"))},
    ]
    history_actions = [row for row in history_actions if row["count"]]
    return {
        "employee_id": employee_id, "person_id": person_id,
        "full_name": employee["full_name"],
        "login": users[0]["login"] if len(users) == 1 else None,
        "user_ids": user_ids, "marker_id": int(marker["marker_id"]) if marker else None,
        "is_test_marked": marker is not None, "counts": counts,
        "retained_counts": retained_counts,
        "files": files, "blockers": sorted(set(blockers)),
        "personnel_orders": order_details,
        "history_actions": history_actions,
        "blocker_groups": [{"table": table, "count": len(rows),
                            "columns": sorted(blocked_columns[table])}
                           for table, rows in sorted(blocked_rows.items())],
        "can_delete": marker is not None and not blockers,
        "snapshot_hash": state_hash, "_plan": plan, "_edges": edges,
        "_composite_edges": composite_edges, "_retained": retained,
        "_archive_remove": archive_remove, "_preserved_history": preserved_history,
    }


def _public(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if not key.startswith("_") and key != "files"} | {
        "file_count": len(plan["files"]),
    }


def preview(*, employee_id: int, actor_user_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            _assert_sysadmin(conn, actor_user_id)
            result = _public(_build_plan(conn, employee_id))
        finally:
            transaction.rollback()
    return result


def _delete_order(plan: dict[str, dict[str, dict[str, Any]]], edges: list[Edge],
                  composite_edges: list[CompositeEdge]) -> list[str]:
    tables = {table for table, rows in plan.items() if rows}
    requires: dict[str, set[str]] = {table: set() for table in tables}
    for edge in edges:
        if edge.parent == edge.child or edge.parent not in tables or edge.child not in tables:
            continue
        parent_values = {state.get(edge.parent_column) for state in plan[edge.parent].values()}
        if any(state.get(edge.child_column) in parent_values for state in plan[edge.child].values()):
            requires[edge.parent].add(edge.child)
    for edge in composite_edges:
        if edge.parent == edge.child or edge.parent not in tables or edge.child not in tables:
            continue
        parent_keys = {tuple(state.get(column) for column in edge.parent_columns)
                       for state in plan[edge.parent].values()}
        if any(tuple(state.get(column) for column in edge.child_columns) in parent_keys
               for state in plan[edge.child].values()):
            requires[edge.parent].add(edge.child)
    result: list[str] = []
    while requires:
        ready = sorted(table for table, children in requires.items() if not children)
        if not ready:
            raise TestEmployeeCleanupError("DEPENDENCY_CYCLE", "Циклическая зависимость препятствует удалению.")
        result.extend(ready)
        for table in ready:
            del requires[table]
        for children in requires.values():
            children.difference_update(ready)
    return result


def _lock_catalog(conn: Connection) -> None:
    # Logical references have no FK.  Block concurrent writers while the
    # authoritative plan is recomputed and the physical DELETE is performed.
    conn.execute(text("SET LOCAL lock_timeout = '3s'"))
    tables = [str(name) for name in conn.execute(text("""SELECT c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname""")).scalars()]
    for table in tables:
        if not SAFE_NAME.fullmatch(table):
            raise TestEmployeeCleanupError("UNSAFE_CATALOG", "Обнаружено неожиданное имя таблицы.")
        conn.execute(text(f'LOCK TABLE public."{table}" IN SHARE ROW EXCLUSIVE MODE'))


def _run_file_cleanup(deletion_id: str) -> dict[str, int]:
    completed = pending = deleted_files = 0
    with engine.connect() as conn:
        rows = conn.execute(text("""SELECT cleanup_id,storage_kind,storage_path
            FROM public.test_employee_file_cleanup
            WHERE deletion_id=CAST(:id AS uuid) AND completed_at IS NULL
            ORDER BY cleanup_id"""), {"id": deletion_id}).mappings().all()
    for row in rows:
        error = None
        try:
            if row["storage_kind"] == "CANONICAL_PHOTO":
                existed = canonical_photo_absolute_path(str(row["storage_path"])).is_file()
                delete_canonical_photo_file(str(row["storage_path"]))
                deleted_files += int(existed)
            elif row["storage_kind"] == "INTAKE_PHOTO":
                app_id, file_id = str(row["storage_path"]).split("/", 1)
                existed = intake_photo_path(int(app_id), file_id).is_file()
                delete_intake_photo(int(app_id), file_id)
                deleted_files += int(existed)
            elif row["storage_kind"] == "SIGNED_HIRE_COPY":
                path = Path(str(row["storage_path"])).resolve()
                root = resolve_path_within_root(intake_photo_storage_root(), "signed-applications")
                if not path.is_relative_to(root):
                    raise ValueError("Signed-copy path escapes the configured storage root")
                existed = path.is_file()
                path.unlink(missing_ok=True)
                deleted_files += int(existed)
            elif row["storage_kind"] == "PERSONNEL_FILE_BUNDLE":
                key = str(row["storage_path"])
                with engine.connect() as conn:
                    if _bundle_has_external_references(conn, {}, key):
                        raise ValueError("Personnel file has another database reference")
                bundle = _personnel_bundle(key)
                if bundle.exists():
                    for entry in bundle.iterdir():
                        entry.unlink()
                        deleted_files += 1
                    bundle.rmdir()
            else:
                raise ValueError("Unsupported storage kind")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:500]
        with engine.begin() as conn:
            if error is None:
                conn.execute(text("""UPDATE public.test_employee_file_cleanup
                    SET completed_at=now(),last_error=NULL WHERE cleanup_id=:id"""),
                    {"id": int(row["cleanup_id"])})
                completed += 1
            else:
                conn.execute(text("""UPDATE public.test_employee_file_cleanup
                    SET last_error=:error WHERE cleanup_id=:id"""),
                    {"id": int(row["cleanup_id"]), "error": error})
                pending += 1
    return {"completed": completed, "pending": pending, "deleted_files": deleted_files}


def retry_file_cleanup(*, deletion_id: str, actor_user_id: int) -> dict[str, int]:
    try:
        deletion_id = str(UUID(deletion_id))
    except (ValueError, AttributeError):
        raise TestEmployeeCleanupError("INVALID_DELETION_ID", "Неверный идентификатор операции удаления.", 422) from None
    with engine.connect() as conn:
        _assert_sysadmin(conn, actor_user_id)
        if not conn.execute(text("SELECT 1 FROM public.test_employee_deletion_audit WHERE deletion_id=CAST(:id AS uuid)"),
                            {"id": deletion_id}).first():
            raise TestEmployeeCleanupError("DELETION_NOT_FOUND", "Операция удаления не найдена.", 404)
    return _run_file_cleanup(deletion_id)


def _archive_snapshot(conn: Connection, deletion_id: str, table: str, key: str,
                      state: dict[str, Any], disposition: str) -> None:
    conn.execute(text("""INSERT INTO public.test_employee_history_snapshots
        (deletion_id,source_table,source_key,disposition,row_snapshot)
        VALUES (CAST(:deletion AS uuid),:table,:key,:disposition,CAST(:snapshot AS jsonb))
        ON CONFLICT (deletion_id,source_table,source_key) DO NOTHING"""), {
            "deletion": deletion_id, "table": table, "key": key,
            "disposition": disposition, "snapshot": json.dumps(state, default=str, ensure_ascii=False),
        })


def _archive_order(conn: Connection, deletion_id: str, order_id: int) -> None:
    order, items = _order_state(conn, order_id)
    marker = conn.execute(text("""SELECT marker_id,evidence FROM public.test_personnel_order_marks
        WHERE order_id=:id ORDER BY marker_id DESC LIMIT 1"""), {"id": order_id}).mappings().one()
    events = [dict(row) for row in conn.execute(text("""SELECT * FROM public.employee_events
        WHERE order_id=:id ORDER BY event_id"""), {"id": order_id}).mappings()]
    conn.execute(text("""INSERT INTO public.test_personnel_order_deletion_audit
        (deletion_id,order_id,order_number,order_snapshot,item_snapshots,
         employee_event_snapshots,marker_id,marker_evidence)
        VALUES (CAST(:deletion AS uuid),:order_id,:number,CAST(:order AS jsonb),
                CAST(:items AS jsonb),CAST(:events AS jsonb),:marker,:evidence)"""), {
            "deletion": deletion_id, "order_id": order_id,
            "number": order.get("order_number"),
            "order": json.dumps(order, default=str, ensure_ascii=False),
            "items": json.dumps(items, default=str, ensure_ascii=False),
            "events": json.dumps(events, default=str, ensure_ascii=False),
            "marker": marker["marker_id"], "evidence": marker["evidence"],
        })


def execute(*, employee_id: int, actor_user_id: int, confirmation: str,
            expected_snapshot_hash: str) -> dict[str, Any]:
    if confirmation != "УДАЛИТЬ":
        raise TestEmployeeCleanupError("CONFIRMATION_REQUIRED", "Для подтверждения введите слово «УДАЛИТЬ».", 422)
    deletion_id = str(uuid4())
    with engine.connect().execution_options(isolation_level="SERIALIZABLE") as conn:
        with conn.begin():
            _assert_sysadmin(conn, actor_user_id, lock=True)
            _lock_catalog(conn)
            _assert_sysadmin(conn, actor_user_id)
            employee = _employee(conn, employee_id, lock=True)
            if conn.execute(text("SELECT 1 FROM public.users WHERE employee_id=:id AND user_id=:actor"),
                            {"id": employee_id, "actor": actor_user_id}).first():
                raise TestEmployeeCleanupError("OWN_ACCOUNT", "Нельзя удалить собственную учётную запись.", 403)
            plan = _build_plan(conn, employee_id)
            if not plan["can_delete"]:
                raise TestEmployeeCleanupError("DEPENDENCIES_BLOCKED",
                    "; ".join(plan["blockers"][:5]), 409)
            if plan["snapshot_hash"] != expected_snapshot_hash:
                raise TestEmployeeCleanupError("SNAPSHOT_CHANGED", "Связанные данные изменились. Повторно откройте предварительный просмотр.", 409)
            conn.execute(text("SELECT set_config('corpsite.allow_personnel_order_physical_delete','on',true)"))
            conn.execute(text("SELECT set_config('corpsite.test_employee_cleanup','on',true)"))
            for order in plan["personnel_orders"]:
                _archive_order(conn, deletion_id, order["order_id"])
            for row in plan["_archive_remove"]:
                _archive_snapshot(conn, deletion_id, row["table"], row["key"],
                                  row["state"], row["disposition"])
                deleted = conn.execute(text(f'DELETE FROM public."{row["table"]}" '
                                            'WHERE ctid::text=:tid'), {"tid": row["tid"]})
                if deleted.rowcount != 1:
                    raise TestEmployeeCleanupError("HISTORY_CHANGED", "Историческая доставка изменилась.")
            for row in plan["_preserved_history"]:
                _archive_snapshot(conn, deletion_id, row["table"], row["key"],
                                  row["state"], "RETAINED")
            archived_refs: set[tuple[str, str]] = set()
            retired_participants: dict[str, dict[str, Any]] = {}
            for ref in plan["_retained"]:
                archive_key = (ref["table"], ref["key"])
                if archive_key not in archived_refs:
                    _archive_snapshot(conn, deletion_id, ref["table"], ref["key"],
                                      ref["state"], "RETAINED")
                    archived_refs.add(archive_key)
                conn.execute(text("""INSERT INTO public.test_employee_retained_history_refs
                    (deletion_id,source_table,source_key,source_column,deleted_entity_kind,
                     deleted_entity_id,deleted_full_name,deleted_login)
                    VALUES (CAST(:deletion AS uuid),:table,:key,:column,:kind,:entity_id,:name,:login)"""), {
                    "deletion": deletion_id, "table": ref["table"], "key": ref["key"],
                    "column": ref["column"], "kind": ref["kind"], "entity_id": ref["id"],
                    "name": plan["full_name"], "login": plan["login"],
                })
                if ref["table"] == "ppr_stage0_cohort_participants":
                    retired_participants[ref["key"]] = ref["state"]
                elif ref["table"] in {"personnel_file_events", "personnel_file_versions",
                                      "tasks", "user_linkage_execute_items",
                                      "employee_onboarding_notifications",
                                      "electronic_hire_approval_tasks"}:
                    key_column = HISTORY_KEYS[ref["table"]]
                    changed = conn.execute(text(f'UPDATE public."{ref["table"]}" '
                                                f'SET "{ref["column"]}"=NULL '
                                                f'WHERE "{key_column}"=:key AND "{ref["column"]}"=:old'),
                                           {"key": ref["key"], "old": ref["id"]})
                    if changed.rowcount != 1:
                        raise TestEmployeeCleanupError("HISTORY_CHANGED", "Историческая ссылка изменилась во время удаления.")
            for key, state in retired_participants.items():
                changed = conn.execute(text("""UPDATE public.ppr_stage0_cohort_participants
                    SET employee_id=NULL,person_id=NULL,retired_test_employee_id=:employee,
                        retired_test_person_id=:person,retired_at=now(),
                        retired_deletion_id=CAST(:deletion AS uuid)
                    WHERE stage0_participant_id=:id AND employee_id=:employee AND person_id=:person
                      AND retired_at IS NULL"""), {
                    "id": int(key), "employee": state["employee_id"],
                    "person": state["person_id"], "deletion": deletion_id,
                })
                if changed.rowcount != 1:
                    raise TestEmployeeCleanupError("HISTORY_CHANGED", "Состав кадровой когорты изменился.")
            historical_tables = {
                "employee_onboarding_task_audit": "audit_id",
                "personnel_order_lifecycle_audit": "id",
                "employee_events": "event_id",
                "ppr_migration_section_status_projection": None,
                "personnel_application_lifecycle_audit": "audit_id",
                "personnel_application_resolution_audit": "audit_id",
            }
            for table, key_column in historical_tables.items():
                for state in plan["_plan"].get(table, {}).values():
                    key = (str(state[key_column]) if key_column else _hash(state))
                    _archive_snapshot(conn, deletion_id, table, key, state, "REMOVED")
            deleted_counts: dict[str, int] = {}
            for table in _delete_order(plan["_plan"], plan["_edges"], plan["_composite_edges"]):
                tids = sorted(plan["_plan"][table])
                deleted = conn.execute(text(f'DELETE FROM public."{table}" WHERE ctid::text=ANY(:tids)'),
                                       {"tids": tids})
                if deleted.rowcount != len(tids):
                    raise TestEmployeeCleanupError("DELETE_COUNT_CHANGED", "Количество записей изменилось во время удаления.")
                deleted_counts[table] = len(tids)
            # The marker is retained as non-FK administrative provenance.
            conn.execute(text("""INSERT INTO public.test_employee_deletion_audit
                (deletion_id,employee_id,person_id,full_name,login,marker_id,
                 deleted_by_user_id,deleted_counts,snapshot_hash)
                VALUES (CAST(:id AS uuid),:employee,:person,:name,:login,:marker,
                        :actor,CAST(:counts AS jsonb),:digest)"""), {
                "id": deletion_id, "employee": employee_id, "person": plan["person_id"],
                "name": plan["full_name"], "login": plan["login"],
                "marker": plan["marker_id"], "actor": actor_user_id,
                "counts": json.dumps(deleted_counts), "digest": plan["snapshot_hash"],
            })
            for kind, path in plan["files"]:
                conn.execute(text("""INSERT INTO public.test_employee_file_cleanup
                    (deletion_id,storage_kind,storage_path)
                    VALUES (CAST(:id AS uuid),:kind,:path)"""),
                    {"id": deletion_id, "kind": kind, "path": path})
    try:
        cleanup = _run_file_cleanup(deletion_id)
    except SQLAlchemyError:
        # PostgreSQL deletion has already committed.  The durable queue keeps
        # every file eligible for the SYSADMIN retry endpoint.
        logger.exception("post-commit test employee file cleanup unavailable deletion_id=%s", deletion_id)
        cleanup = {"completed": 0, "pending": len(plan["files"]), "deleted_files": 0}
    return {"deletion_id": deletion_id, "employee_id": employee_id,
            "full_name": plan["full_name"], "deleted_counts": deleted_counts,
            "retained_counts": plan["retained_counts"], "file_cleanup": cleanup}
