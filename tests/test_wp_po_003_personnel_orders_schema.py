# tests/test_wp_po_003_personnel_orders_schema.py
"""Schema tests for WP-PO-003 personnel orders storage foundation."""
from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_orders import (
    ITEM_STATUS_ACTIVE,
    LOCALE_KK,
    ORDER_STATUS_REGISTERED,
    ORDER_TYPE_HIRE,
    SOURCE_MODE_PAPER,
)
from tests.conftest import get_columns, table_exists

DDL_REVISION = "p0q1r2s3t4u5"

PERSONNEL_ORDER_TABLES = (
    "personnel_orders",
    "personnel_order_items",
    "personnel_order_localized_texts",
    "personnel_order_attachments",
    "personnel_order_prints",
)

EMPLOYEE_EVENT_ORDER_COLUMNS = ("order_id", "order_item_id")


def _schema_available() -> bool:
    with engine.begin() as conn:
        if not all(table_exists(conn, table) for table in PERSONNEL_ORDER_TABLES):
            return False
        if not table_exists(conn, "employee_events"):
            return False
        cols = get_columns(conn, "employee_events")
        return all(column in cols for column in EMPLOYEE_EVENT_ORDER_COLUMNS)


def _require_schema() -> None:
    if not _schema_available():
        pytest.skip(
            f"WP-PO-003 personnel orders schema missing — run: alembic upgrade head "
            f"(revision {DDL_REVISION})"
        )


def _delete_personnel_order_audit_rows(conn, order_id: int) -> None:
    if table_exists(conn, "personnel_order_lifecycle_audit"):
        conn.execute(
            text(
                """
                DELETE FROM public.personnel_order_lifecycle_audit
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id)},
        )


def _require_lc_del_003_schema() -> None:
    _require_schema()
    with engine.begin() as conn:
        cols = get_columns(conn, "personnel_orders")
        for column in (
            "void_kind",
            "archived_at",
            "archived_by",
            "archive_reason_code",
            "archive_reason_text",
        ):
            if column not in cols:
                pytest.skip(
                    "WP-PO-LC-DEL-003 lifecycle foundation missing — run: alembic upgrade head "
                    "(revision t4u5v6w7x8y9)"
                )
        if not table_exists(conn, "personnel_order_lifecycle_audit"):
            pytest.skip(
                "WP-PO-LC-DEL-003 lifecycle audit table missing — run: alembic upgrade head "
                "(revision t4u5v6w7x8y9)"
            )


def _insert_returning(conn, sql: str, params: dict[str, Any] | None = None) -> int:
    row = conn.execute(text(sql), params or {}).one()
    return int(row[0])


def _expect_sql_failure(sql: str, params: dict[str, Any] | None = None) -> None:
    with engine.begin() as conn:
        with pytest.raises(Exception):
            conn.execute(text(sql), params or {})


def _pick_user_id(conn) -> int:
    user_id = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE is_active = TRUE
            ORDER BY user_id
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if user_id is None:
        pytest.skip("active users row required")
    return int(user_id)


def _pick_employee_id(conn) -> int:
    employee_id = conn.execute(
        text(
            """
            SELECT employee_id
            FROM public.employees
            ORDER BY employee_id
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if employee_id is None:
        pytest.skip("employees row required")
    return int(employee_id)


def test_personnel_orders_tables_exist() -> None:
    _require_schema()


def test_employee_events_order_fk_columns_exist() -> None:
    _require_schema()
    with engine.begin() as conn:
        cols = get_columns(conn, "employee_events")
        assert "order_id" in cols
        assert "order_item_id" in cols


def test_personnel_order_hire_roundtrip_and_employee_event_fk() -> None:
    _require_schema()

    suffix = uuid4().hex[:8]
    order_number = f"WPPO3-{suffix}"

    with engine.begin() as conn:
        user_id = _pick_user_id(conn)
        employee_id = _pick_employee_id(conn)

        order_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number,
                order_date,
                order_type_code,
                status,
                source_mode,
                created_by
            )
            VALUES (
                :order_number,
                :order_date,
                :order_type_code,
                :status,
                :source_mode,
                :created_by
            )
            RETURNING order_id
            """,
            {
                "order_number": order_number,
                "order_date": date(2026, 7, 7),
                "order_type_code": ORDER_TYPE_HIRE,
                "status": ORDER_STATUS_REGISTERED,
                "source_mode": SOURCE_MODE_PAPER,
                "created_by": user_id,
            },
        )

        item_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_order_items (
                order_id,
                item_number,
                item_type_code,
                employee_id,
                effective_date,
                payload,
                item_status
            )
            VALUES (
                :order_id,
                1,
                :item_type_code,
                :employee_id,
                :effective_date,
                CAST(:payload AS jsonb),
                :item_status
            )
            RETURNING item_id
            """,
            {
                "order_id": order_id,
                "item_type_code": ORDER_TYPE_HIRE,
                "employee_id": employee_id,
                "effective_date": date(2026, 7, 7),
                "payload": '{"employment_rate": 1.0}',
                "item_status": ITEM_STATUS_ACTIVE,
            },
        )

        localized_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_order_localized_texts (
                order_id,
                locale,
                title,
                is_authoritative
            )
            VALUES (
                :order_id,
                :locale,
                :title,
                TRUE
            )
            RETURNING localized_text_id
            """,
            {
                "order_id": order_id,
                "locale": LOCALE_KK,
                "title": "Жұмысқа қабылдау туралы",
            },
        )

        attachment_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_order_attachments (
                order_id,
                attachment_kind,
                storage_type,
                file_path,
                created_by
            )
            VALUES (
                :order_id,
                'SIGNED_SCAN',
                'LOCAL_SHARE',
                :file_path,
                :created_by
            )
            RETURNING attachment_id
            """,
            {
                "order_id": order_id,
                "file_path": f"\\\\medserver\\hr\\orders\\2026\\{order_number}.pdf",
                "created_by": user_id,
            },
        )

        print_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_order_prints (
                order_id,
                locale,
                format,
                file_path,
                generated_by
            )
            VALUES (
                :order_id,
                :locale,
                'pdf',
                :file_path,
                :generated_by
            )
            RETURNING print_id
            """,
            {
                "order_id": order_id,
                "locale": LOCALE_KK,
                "file_path": f"\\\\medserver\\hr\\orders\\2026\\{order_number}-draft.pdf",
                "generated_by": user_id,
            },
        )

        event_id = _insert_returning(
            conn,
            """
            INSERT INTO public.employee_events (
                employee_id,
                event_type,
                effective_date,
                order_id,
                order_item_id,
                created_by
            )
            VALUES (
                :employee_id,
                'HIRE',
                :effective_date,
                :order_id,
                :order_item_id,
                :created_by
            )
            RETURNING event_id
            """,
            {
                "employee_id": employee_id,
                "effective_date": date(2026, 7, 7),
                "order_id": order_id,
                "order_item_id": item_id,
                "created_by": user_id,
            },
        )

        linked = conn.execute(
            text(
                """
                SELECT order_id, order_item_id
                FROM public.employee_events
                WHERE event_id = :event_id
                """
            ),
            {"event_id": event_id},
        ).one()
        assert int(linked.order_id) == order_id
        assert int(linked.order_item_id) == item_id

        conn.execute(
            text("DELETE FROM public.employee_events WHERE event_id = :event_id"),
            {"event_id": event_id},
        )
        _delete_personnel_order_audit_rows(conn, order_id)
        conn.execute(
            text("DELETE FROM public.personnel_order_prints WHERE print_id = :print_id"),
            {"print_id": print_id},
        )
        conn.execute(
            text(
                "DELETE FROM public.personnel_order_attachments WHERE attachment_id = :attachment_id"
            ),
            {"attachment_id": attachment_id},
        )
        conn.execute(
            text(
                "DELETE FROM public.personnel_order_localized_texts WHERE localized_text_id = :localized_text_id"
            ),
            {"localized_text_id": localized_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_order_items WHERE item_id = :item_id"),
            {"item_id": item_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"),
            {"order_id": order_id},
        )


def test_rejects_invalid_order_type_and_duplicate_item_number() -> None:
    _require_schema()

    suffix = uuid4().hex[:8]
    order_number = f"WPPO3-BAD-{suffix}"

    with engine.begin() as conn:
        user_id = _pick_user_id(conn)

    _expect_sql_failure(
        """
        INSERT INTO public.personnel_orders (
            order_number,
            order_date,
            order_type_code,
            status,
            source_mode,
            created_by
        )
        VALUES (
            :order_number,
            CURRENT_DATE,
            'ANNUAL_LEAVE',
            'REGISTERED',
            'PAPER',
            :created_by
        )
        """,
        {"order_number": f"{order_number}-invalid", "created_by": user_id},
    )

    with engine.begin() as conn:
        user_id = _pick_user_id(conn)
        employee_id = _pick_employee_id(conn)
        order_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number,
                order_date,
                order_type_code,
                status,
                source_mode,
                created_by
            )
            VALUES (
                :order_number,
                CURRENT_DATE,
                'HIRE',
                'REGISTERED',
                'PAPER',
                :created_by
            )
            RETURNING order_id
            """,
            {"order_number": f"{order_number}-dup", "created_by": user_id},
        )

        _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_order_items (
                order_id,
                item_number,
                item_type_code,
                employee_id,
                effective_date
            )
            VALUES (
                :order_id,
                1,
                'HIRE',
                :employee_id,
                CURRENT_DATE
            )
            RETURNING item_id
            """,
            {"order_id": order_id, "employee_id": employee_id},
        )

    _expect_sql_failure(
        """
        INSERT INTO public.personnel_order_items (
            order_id,
            item_number,
            item_type_code,
            employee_id,
            effective_date
        )
        VALUES (
            :order_id,
            1,
            'HIRE',
            :employee_id,
            CURRENT_DATE
        )
        """,
        {"order_id": order_id, "employee_id": employee_id},
    )

    with engine.begin() as conn:
        _delete_personnel_order_audit_rows(conn, order_id)
        conn.execute(
            text("DELETE FROM public.personnel_order_items WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"),
            {"order_id": order_id},
        )


def test_employee_event_rejects_unknown_order_id() -> None:
    _require_schema()

    with engine.begin() as conn:
        user_id = _pick_user_id(conn)
        employee_id = _pick_employee_id(conn)

    _expect_sql_failure(
        """
        INSERT INTO public.employee_events (
            employee_id,
            event_type,
            effective_date,
            order_id,
            created_by
        )
        VALUES (
            :employee_id,
            'HIRE',
            CURRENT_DATE,
            :order_id,
            :created_by
        )
        """,
        {"employee_id": employee_id, "order_id": 999999999, "created_by": user_id},
    )
