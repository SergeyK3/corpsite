"""Administrative hard-delete of an employee contour and dependent data."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import engine
from app.services.security_audit_service import write_security_event

_PERSON_SECTION_TABLES = (
    "person_education",
    "person_training",
    "person_external_employment",
    "person_military_service",
    "person_relatives",
)

_APPLICATION_CHILD_TABLES = (
    "personnel_intake_reconciliation_decisions",
    "personnel_intake_section_reviews",
    "personnel_intake_transfers",
    "personnel_intake_drafts",
    "personnel_intake_links",
    "personnel_application_lifecycle_audit",
    "personnel_application_resolution_audit",
)


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = :table
              AND table_type = 'BASE TABLE'
            LIMIT 1
            """
        ),
        {"table": table},
    ).first()
    return row is not None


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table
              AND column_name = :column
            LIMIT 1
            """
        ),
        {"table": table, "column": column},
    ).first()
    return row is not None


def _execute(conn: Connection, sql: str, **params: Any) -> None:
    conn.execute(text(sql), params)


def _fetch_application_ids(conn: Connection, person_id: int) -> List[int]:
    if not _table_exists(conn, "personnel_applications"):
        return []
    rows = conn.execute(
        text(
            """
            SELECT application_id
            FROM public.personnel_applications
            WHERE person_id = :person_id
            ORDER BY application_id
            """
        ),
        {"person_id": int(person_id)},
    ).scalars().all()
    return [int(row) for row in rows]


def _delete_by_application_ids(conn: Connection, table: str, application_ids: List[int]) -> None:
    if not application_ids or not _table_exists(conn, table):
        return
    if not _column_exists(conn, table, "application_id"):
        return
    _execute(
        conn,
        f"DELETE FROM public.{table} WHERE application_id = ANY(:application_ids)",
        application_ids=application_ids,
    )


def _delete_by_person_id(conn: Connection, table: str, person_id: int) -> None:
    if not _table_exists(conn, table) or not _column_exists(conn, table, "person_id"):
        return
    _execute(
        conn,
        f"DELETE FROM public.{table} WHERE person_id = :person_id",
        person_id=int(person_id),
    )


def _delete_by_employee_id(conn: Connection, table: str, employee_id: int) -> None:
    if not _table_exists(conn, table) or not _column_exists(conn, table, "employee_id"):
        return
    _execute(
        conn,
        f"DELETE FROM public.{table} WHERE employee_id = :employee_id",
        employee_id=int(employee_id),
    )


def _delete_by_employee_context(conn: Connection, table: str, employee_id: int) -> None:
    if not _table_exists(conn, table) or not _column_exists(conn, table, "employee_context_id"):
        return
    _execute(
        conn,
        f"DELETE FROM public.{table} WHERE employee_context_id = :employee_id",
        employee_id=int(employee_id),
    )


def _clear_cross_employee_references(conn: Connection, employee_id: int) -> None:
    if _table_exists(conn, "employee_onboardings") and _column_exists(
        conn, "employee_onboardings", "mentor_employee_id"
    ):
        _execute(
            conn,
            """
            UPDATE public.employee_onboardings
            SET mentor_employee_id = NULL
            WHERE mentor_employee_id = :employee_id
            """,
            employee_id=int(employee_id),
        )

    if _table_exists(conn, "employee_onboarding_checklist_items") and _column_exists(
        conn, "employee_onboarding_checklist_items", "assignee_employee_id"
    ):
        _execute(
            conn,
            """
            UPDATE public.employee_onboarding_checklist_items
            SET assignee_employee_id = NULL
            WHERE assignee_employee_id = :employee_id
            """,
            employee_id=int(employee_id),
        )


def _delete_onboarding_for_employee(conn: Connection, employee_id: int) -> None:
    if not _table_exists(conn, "employee_onboardings"):
        return
    onboarding_ids = conn.execute(
        text(
            """
            SELECT onboarding_id
            FROM public.employee_onboardings
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": int(employee_id)},
    ).scalars().all()
    if not onboarding_ids:
        return
    ids = [int(x) for x in onboarding_ids]
    if _table_exists(conn, "employee_onboarding_checklist_items"):
        _execute(
            conn,
            """
            DELETE FROM public.employee_onboarding_checklist_items
            WHERE onboarding_id = ANY(:ids)
            """,
            ids=ids,
        )
    _execute(
        conn,
        "DELETE FROM public.employee_onboardings WHERE employee_id = :employee_id",
        employee_id=int(employee_id),
    )


def _delete_assignment_contour(conn: Connection, employee_id: int) -> Set[int]:
    assignment_ids: Set[int] = set()
    if not _table_exists(conn, "employee_assignment_links"):
        return assignment_ids

    rows = conn.execute(
        text(
            """
            SELECT assignment_id
            FROM public.employee_assignment_links
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": int(employee_id)},
    ).scalars().all()
    assignment_ids = {int(row) for row in rows}

    if _table_exists(conn, "enrollment_history"):
        _execute(
            conn,
            """
            DELETE FROM public.enrollment_history
            WHERE employee_id = :employee_id
               OR link_id IN (
                    SELECT link_id
                    FROM public.employee_assignment_links
                    WHERE employee_id = :employee_id
               )
            """,
            employee_id=int(employee_id),
        )

    _delete_by_employee_id(conn, "employee_assignment_links", employee_id)

    for assignment_id in assignment_ids:
        if not _table_exists(conn, "person_assignments"):
            continue
        remaining = conn.execute(
            text(
                """
                SELECT COUNT(*)::int
                FROM public.employee_assignment_links
                WHERE assignment_id = :assignment_id
                """
            ),
            {"assignment_id": int(assignment_id)},
        ).scalar_one()
        if int(remaining) == 0:
            _execute(
                conn,
                "DELETE FROM public.person_assignments WHERE assignment_id = :assignment_id",
                assignment_id=int(assignment_id),
            )
    return assignment_ids


def _delete_employee_documents(conn: Connection, employee_id: int) -> None:
    if not _table_exists(conn, "employee_documents"):
        return

    document_ids = conn.execute(
        text(
            """
            SELECT document_id
            FROM public.employee_documents
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": int(employee_id)},
    ).scalars().all()
    if not document_ids:
        return
    ids = [int(x) for x in document_ids]

    for table in (
        "hr_import_document_candidates",
        "hr_import_normalized_records",
    ):
        if _table_exists(conn, table) and _column_exists(conn, table, "document_id"):
            _execute(
                conn,
                f"DELETE FROM public.{table} WHERE document_id = ANY(:ids)",
                ids=ids,
            )

    for table in ("hr_import_document_candidates", "hr_import_rows"):
        if _table_exists(conn, table) and _column_exists(conn, table, "employee_id"):
            _delete_by_employee_id(conn, table, employee_id)

    _delete_by_employee_id(conn, "employee_documents", employee_id)


def _delete_hr_import_employee_data(conn: Connection, employee_id: int) -> None:
    for table in (
        "hr_import_rows",
        "hr_import_normalized_records",
        "hr_import_document_candidates",
        "hr_change_events",
        "hr_monthly_reference_entries",
        "identity_reconciliation_items",
        "user_linkage_review_decisions",
        "user_linkage_execute_items",
    ):
        _delete_by_employee_id(conn, table, employee_id)


def _delete_user_account(conn: Connection, employee_id: int) -> Optional[int]:
    if not _table_exists(conn, "users") or not _column_exists(conn, "users", "employee_id"):
        return None

    user_id = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE employee_id = :employee_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).scalar_one_or_none()
    if user_id is None:
        return None
    uid = int(user_id)

    if _table_exists(conn, "personnel_visibility_assignments"):
        for col in ("target_user_id", "created_by_user_id", "revoked_by_user_id"):
            if _column_exists(conn, "personnel_visibility_assignments", col):
                _execute(
                    conn,
                    f"""
                    DELETE FROM public.personnel_visibility_assignments
                    WHERE {col} = :user_id
                    """,
                    user_id=uid,
                )

    if _table_exists(conn, "access_grants"):
        _execute(
            conn,
            """
            DELETE FROM public.access_grants
            WHERE (target_type = 'USER' AND target_id = :user_id)
               OR granted_by_user_id = :user_id
               OR revoked_by_user_id = :user_id
            """,
            user_id=uid,
        )

    for table in ("user_roles", "users_roles", "role_users", "user_role_memberships"):
        if _table_exists(conn, table) and _column_exists(conn, table, "user_id"):
            _execute(conn, f"DELETE FROM public.{table} WHERE user_id = :user_id", user_id=uid)

    _execute(conn, "DELETE FROM public.users WHERE user_id = :user_id", user_id=uid)
    return uid


def _delete_employee_scoped_journals(conn: Connection, employee_id: int) -> None:
    for table in (
        "employee_events",
        "employee_identities",
        "employee_import_profile_overrides",
        "personnel_order_items",
        "operational_order_signing_attestations",
        "verification_attestations",
        "personnel_migration_runs",
        "personnel_record_events",
        "person_education",
        "person_training",
        "person_external_employment",
        "person_military_service",
        "person_relatives",
    ):
        _delete_by_employee_id(conn, table, employee_id)
        _delete_by_employee_context(conn, table, employee_id)


def _delete_applications_for_person(conn: Connection, person_id: int) -> None:
    application_ids = _fetch_application_ids(conn, person_id)
    if not application_ids:
        return

    if _table_exists(conn, "employee_onboardings") and _column_exists(
        conn, "employee_onboardings", "application_id"
    ):
        _execute(
            conn,
            """
            DELETE FROM public.employee_onboardings
            WHERE application_id = ANY(:application_ids)
            """,
            application_ids=application_ids,
        )

    for table in _APPLICATION_CHILD_TABLES:
        _delete_by_application_ids(conn, table, application_ids)

    _delete_by_person_id(conn, "personnel_intake_reconciliation_decisions", person_id)
    _execute(
        conn,
        "DELETE FROM public.personnel_applications WHERE person_id = :person_id",
        person_id=int(person_id),
    )


def _delete_full_person_contour(conn: Connection, person_id: int) -> None:
    _delete_applications_for_person(conn, person_id)
    _delete_by_person_id(conn, "enrollment_queue", person_id)
    _delete_by_person_id(conn, "personnel_intake_reconciliation_decisions", person_id)
    _delete_by_person_id(conn, "person_assignments", person_id)
    _delete_by_person_id(conn, "personnel_record_events", person_id)
    _delete_by_person_id(conn, "personnel_migration_runs", person_id)
    _delete_by_person_id(conn, "verification_tasks", person_id)
    _delete_by_person_id(conn, "verification_attestations", person_id)
    _delete_by_person_id(conn, "person_telegram_bindings", person_id)
    _delete_by_person_id(conn, "person_telegram_bot_activations", person_id)
    _delete_by_person_id(conn, "identity_reconciliation_items", person_id)
    _delete_by_person_id(conn, "ppr_command_executions", person_id)
    _delete_by_person_id(conn, "hr_review_overrides", person_id)
    _delete_by_person_id(conn, "hr_personnel_change_events", person_id)
    _delete_by_person_id(conn, "enrollment_history", person_id)

    for table in _PERSON_SECTION_TABLES:
        _delete_by_person_id(conn, table, person_id)

    if _table_exists(conn, "contacts") and _column_exists(conn, "contacts", "person_id"):
        _delete_by_person_id(conn, "contacts", person_id)

    if _table_exists(conn, "personnel_record_metadata"):
        _execute(
            conn,
            "DELETE FROM public.personnel_record_metadata WHERE person_id = :person_id",
            person_id=int(person_id),
        )

    if _table_exists(conn, "persons"):
        _execute(
            conn,
            "DELETE FROM public.persons WHERE person_id = :person_id",
            person_id=int(person_id),
        )


def _person_has_independent_links(
    conn: Connection,
    person_id: int,
    *,
    exclude_employee_id: int | None = None,
) -> bool:
    if _table_exists(conn, "employees"):
        sql = """
            SELECT COUNT(*)::int
            FROM public.employees
            WHERE person_id = :person_id
        """
        params: Dict[str, Any] = {"person_id": int(person_id)}
        if exclude_employee_id is not None:
            sql += " AND employee_id <> :exclude_employee_id"
            params["exclude_employee_id"] = int(exclude_employee_id)
        count = conn.execute(text(sql), params).scalar_one()
        if int(count) > 0:
            return True

    checks = (
        ("personnel_applications", "person_id"),
        ("enrollment_queue", "person_id"),
        ("person_assignments", "person_id"),
    )
    for table, column in checks:
        if not _table_exists(conn, table) or not _column_exists(conn, table, column):
            continue
        count = conn.execute(
            text(f"SELECT COUNT(*)::int FROM public.{table} WHERE {column} = :person_id"),
            {"person_id": int(person_id)},
        ).scalar_one()
        if int(count) > 0:
            return True

    return False


def _load_employee(conn: Connection, employee_id: str) -> Dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT employee_id, person_id, full_name
            FROM public.employees
            WHERE CAST(employee_id AS TEXT) = :employee_id_text
            FOR UPDATE
            """
        ),
        {"employee_id_text": str(employee_id).strip()},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Сотрудник не найден.")
    return dict(row)


def hard_delete_employee(
    *,
    employee_id: str,
    actor_user_id: int,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Hard-delete employee contour in a single transaction.

    Removes linked account, assignments, documents, applications/intake (when person
    becomes orphan), and person shell when no independent links remain.
    """
    target_id_text = str(employee_id or "").strip()
    if not target_id_text:
        raise HTTPException(status_code=404, detail="Сотрудник не найден.")

    try:
        with engine.begin() as conn:
            employee = _load_employee(conn, target_id_text)
            eid = int(employee["employee_id"])
            person_id_raw = employee.get("person_id")
            person_id = int(person_id_raw) if person_id_raw is not None else None
            full_name = str(employee.get("full_name") or "").strip()

            _clear_cross_employee_references(conn, eid)
            _delete_onboarding_for_employee(conn, eid)
            _delete_by_employee_id(conn, "personnel_order_items", eid)
            _delete_assignment_contour(conn, eid)
            _delete_employee_documents(conn, eid)
            _delete_hr_import_employee_data(conn, eid)
            _delete_employee_scoped_journals(conn, eid)
            deleted_user_id = _delete_user_account(conn, eid)

            person_deleted = False
            if person_id is not None:
                for table in _PERSON_SECTION_TABLES:
                    _delete_by_employee_context(conn, table, eid)
                _delete_by_employee_context(conn, "personnel_record_events", eid)
                _delete_by_employee_context(conn, "personnel_migration_runs", eid)

                person_deleted = not _person_has_independent_links(
                    conn,
                    int(person_id),
                    exclude_employee_id=eid,
                )

            write_security_event(
                event_type="EMPLOYEE_HARD_DELETED",
                actor_user_id=int(actor_user_id),
                target_employee_id=eid,
                target_person_id=person_id if not person_deleted else None,
                success=True,
                metadata={
                    "employee_id": eid,
                    "full_name": full_name,
                    "person_id": person_id,
                    "person_deleted": person_deleted,
                    "deleted_user_id": deleted_user_id,
                },
                request_id=request_id,
                conn=conn,
            )

            _execute(
                conn,
                "DELETE FROM public.employees WHERE employee_id = :employee_id",
                employee_id=eid,
            )

            if person_id is not None and person_deleted:
                _delete_full_person_contour(conn, int(person_id))

            return {
                "ok": True,
                "employee_id": eid,
                "full_name": full_name,
                "person_id": person_id,
                "person_deleted": person_deleted,
            }
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="Не удалось удалить сотрудника: связанные данные заблокировали операцию.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Не удалось удалить сотрудника. Операция отменена.",
        ) from exc