# tests/personnel_applications/test_wp_ppr_applicant_001b_migration.py
"""Migration tests for WP-PPR-APPLICANT-001B personnel_applications."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.engine import engine
from app.personnel_applications.domain.status import terminal_statuses_for_partial_index
from tests.conftest import get_columns, table_exists
from tests.ppr.conftest import insert_person

REVISION_ID = "q7r8s9t0u1v2"
PREVIOUS_REVISION = "p6q7r8s9t0u1"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "q7r8s9t0u1v2_wp_ppr_applicant_001b_personnel_applications.py"
)

EXPECTED_COLUMNS = {
    "application_id",
    "person_id",
    "status",
    "application_received_at",
    "application_source",
    "vacancy_check_status",
    "personnel_order_id",
    "idempotency_key",
    "registered_at",
    "registered_by_user_id",
}


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _current_revision() -> str | None:
    with engine.begin() as conn:
        if not table_exists(conn, "alembic_version"):
            return None
        row = conn.execute(text("SELECT version_num FROM public.alembic_version LIMIT 1")).first()
        return str(row[0]) if row else None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(REVISION_ID)
    assert rev is not None
    assert rev.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_personnel_applications_table_columns() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_applications"):
            pytest.skip("personnel_applications missing — run: alembic upgrade head")
        cols = get_columns(conn, "personnel_applications")
        assert EXPECTED_COLUMNS.issubset(cols)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_partial_unique_active_index_matches_terminal_set() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_applications"):
            pytest.skip("personnel_applications missing — run: alembic upgrade head")
        row = conn.execute(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'personnel_applications'
                  AND indexname = 'uq_personnel_applications_one_active_per_person'
                """
            )
        ).mappings().first()
    assert row is not None
    indexdef = str(row["indexdef"]).lower()
    for terminal in terminal_statuses_for_partial_index():
        assert terminal in indexdef


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_personnel_applications_fk_to_persons() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_applications"):
            pytest.skip("personnel_applications missing — run: alembic upgrade head")
        rows = conn.execute(
            text(
                """
                SELECT ccu.table_name AS referenced_table
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.constraint_schema = tc.constraint_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = 'personnel_applications'
                  AND tc.constraint_type = 'FOREIGN KEY'
                  AND tc.constraint_name LIKE '%person_id%'
                """
            )
        ).mappings().all()
    referenced = {str(r["referenced_table"]) for r in rows}
    assert "persons" in referenced


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_rejects_second_active_application_per_person() -> None:
    person_id: int | None = None
    try:
        with engine.begin() as conn:
            if not table_exists(conn, "personnel_applications"):
                pytest.skip("personnel_applications missing — run: alembic upgrade head")
            person_id = insert_person(conn, full_name="PA Migration Guard", prefix="pa-mig")
            user_row = conn.execute(text("SELECT user_id FROM public.users LIMIT 1")).mappings().first()
            if user_row is None:
                pytest.skip("users table empty")
            user_id = int(user_row["user_id"])
            conn.execute(
                text(
                    """
                    INSERT INTO public.personnel_applications (
                        person_id, application_received_at, vacancy_check_status,
                        registered_by_user_id, status
                    ) VALUES (
                        :person_id, CURRENT_DATE, 'confirmed_visually', :user_id, 'registered'
                    )
                    """
                ),
                {"person_id": person_id, "user_id": user_id},
            )
        with engine.begin() as conn:
            user_row = conn.execute(text("SELECT user_id FROM public.users LIMIT 1")).mappings().first()
            user_id = int(user_row["user_id"])
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        """
                        INSERT INTO public.personnel_applications (
                            person_id, application_received_at, vacancy_check_status,
                            registered_by_user_id, status
                        ) VALUES (
                            :person_id, CURRENT_DATE, 'confirmed_visually', :user_id, 'under_review'
                        )
                        """
                    ),
                    {"person_id": person_id, "user_id": user_id},
                )
    finally:
        if person_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM public.personnel_applications WHERE person_id = :person_id"),
                    {"person_id": person_id},
                )
                conn.execute(
                    text("DELETE FROM public.persons WHERE person_id = :person_id"),
                    {"person_id": person_id},
                )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_terminal_status_allows_new_application() -> None:
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_applications"):
            pytest.skip("personnel_applications missing — run: alembic upgrade head")
        person_id = insert_person(conn, full_name="PA Terminal Reapply", prefix="pa-term")
        user_row = conn.execute(text("SELECT user_id FROM public.users LIMIT 1")).mappings().first()
        if user_row is None:
            pytest.skip("users table empty")
        user_id = int(user_row["user_id"])
        conn.execute(
            text(
                """
                INSERT INTO public.personnel_applications (
                    person_id, application_received_at, vacancy_check_status,
                    registered_by_user_id, status
                ) VALUES (
                    :person_id, CURRENT_DATE, 'confirmed_visually', :user_id, 'withdrawn'
                )
                """
            ),
            {"person_id": person_id, "user_id": user_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO public.personnel_applications (
                    person_id, application_received_at, vacancy_check_status,
                    registered_by_user_id, status
                ) VALUES (
                    :person_id, CURRENT_DATE, 'confirmed_visually', :user_id, 'registered'
                )
                """
            ),
            {"person_id": person_id, "user_id": user_id},
        )
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.personnel_applications WHERE person_id = :person_id"
            ),
            {"person_id": person_id},
        ).scalar_one()
        assert int(count) == 2
        conn.execute(
            text("DELETE FROM public.personnel_applications WHERE person_id = :person_id"),
            {"person_id": person_id},
        )
        conn.execute(text("DELETE FROM public.persons WHERE person_id = :person_id"), {"person_id": person_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_personnel_order_id_unique_when_set() -> None:
    person_a: int | None = None
    person_b: int | None = None
    order_id: int | None = None
    try:
        with engine.begin() as conn:
            if not table_exists(conn, "personnel_applications"):
                pytest.skip("personnel_applications missing — run: alembic upgrade head")
            if not table_exists(conn, "personnel_orders"):
                pytest.skip("personnel_orders missing")
            person_a = insert_person(conn, full_name="PA Order Link A", prefix="pa-ord-a")
            person_b = insert_person(conn, full_name="PA Order Link B", prefix="pa-ord-b")
            user_row = conn.execute(text("SELECT user_id FROM public.users LIMIT 1")).mappings().first()
            order_row = conn.execute(
                text("SELECT order_id FROM public.personnel_orders LIMIT 1")
            ).mappings().first()
            if user_row is None or order_row is None:
                pytest.skip("users or personnel_orders seed data missing")
            user_id = int(user_row["user_id"])
            order_id = int(order_row["order_id"])
            conn.execute(
                text(
                    """
                    INSERT INTO public.personnel_applications (
                        person_id, application_received_at, vacancy_check_status,
                        registered_by_user_id, status, personnel_order_id
                    ) VALUES (
                        :person_id, CURRENT_DATE, 'confirmed_visually', :user_id, 'registered', :order_id
                    )
                    """
                ),
                {"person_id": person_a, "user_id": user_id, "order_id": order_id},
            )
        with engine.begin() as conn:
            user_row = conn.execute(text("SELECT user_id FROM public.users LIMIT 1")).mappings().first()
            user_id = int(user_row["user_id"])
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        """
                        INSERT INTO public.personnel_applications (
                            person_id, application_received_at, vacancy_check_status,
                            registered_by_user_id, status, personnel_order_id
                        ) VALUES (
                            :person_id, CURRENT_DATE, 'confirmed_visually', :user_id, 'withdrawn', :order_id
                        )
                        """
                    ),
                    {"person_id": person_b, "user_id": user_id, "order_id": order_id},
                )
    finally:
        if person_a is not None or person_b is not None:
            with engine.begin() as conn:
                for pid in (person_a, person_b):
                    if pid is None:
                        continue
                    conn.execute(
                        text("DELETE FROM public.personnel_applications WHERE person_id = :person_id"),
                        {"person_id": pid},
                    )
                    conn.execute(
                        text("DELETE FROM public.persons WHERE person_id = :person_id"),
                        {"person_id": pid},
                    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_upgrade_downgrade_roundtrip() -> None:
    current = _current_revision()
    heads = ScriptDirectory.from_config(_alembic_config()).get_heads()
    if REVISION_ID not in heads and current != REVISION_ID:
        head = next(iter(heads))
        walk = ScriptDirectory.from_config(_alembic_config()).get_revision(head)
        found = False
        while walk is not None:
            if walk.revision == REVISION_ID:
                found = True
                break
            walk = (
                ScriptDirectory.from_config(_alembic_config()).get_revision(walk.down_revision)
                if walk.down_revision
                else None
            )
        if not found:
            pytest.skip(f"{REVISION_ID} not on current migration chain")

    cfg = _alembic_config()
    command.upgrade(cfg, REVISION_ID)
    with engine.begin() as conn:
        assert table_exists(conn, "personnel_applications")

    command.downgrade(cfg, PREVIOUS_REVISION)
    with engine.begin() as conn:
        assert not table_exists(conn, "personnel_applications")

    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        assert table_exists(conn, "personnel_applications")
