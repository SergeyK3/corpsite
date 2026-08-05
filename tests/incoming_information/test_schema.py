# tests/incoming_information/test_schema.py
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.incoming_information.domain.status import INITIAL_STATUS_CODE, terminal_status_codes_for_guard
from app.incoming_information.repository import II_TABLES, incoming_information_available
from tests.conftest import get_columns, table_exists
from tests.incoming_information.conftest import _require_schema


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_incoming_information_schema_tables_exist():
    _require_schema()
    with engine.connect() as conn:
        for table in II_TABLES:
            assert table_exists(conn, table), table
            assert get_columns(conn, table), table


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_incoming_information_seed_statuses_and_permissions():
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT code, is_terminal
                FROM public.incoming_document_statuses
                WHERE code = :code
                """
            ),
            {"code": INITIAL_STATUS_CODE},
        ).mappings().one()
        assert row["code"] == INITIAL_STATUS_CODE
        assert row["is_terminal"] is False

        perms = conn.execute(
            text(
                """
                SELECT code
                FROM public.access_roles
                WHERE code LIKE 'INCOMING_INFO_%'
                ORDER BY code
                """
            )
        ).scalars().all()
        assert "INCOMING_INFO_REGISTER" in perms
        assert "INCOMING_INFO_ADMIN" in perms


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_incoming_information_primary_assignment_unique_index_exists():
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = 'uq_incoming_document_assignments_one_primary'
                LIMIT 1
                """
            )
        ).first()
        assert row is not None
        assert "PRIMARY" in row[0]


@pytest.mark.usefixtures("_require_ii_schema_fixture")
def test_terminal_status_domain_matches_seed():
    with engine.connect() as conn:
        terminal_codes = set(
            conn.execute(
                text(
                    """
                    SELECT code
                    FROM public.incoming_document_statuses
                    WHERE is_terminal = TRUE
                    """
                )
            ).scalars().all()
        )
    assert terminal_codes == set(terminal_status_codes_for_guard())
