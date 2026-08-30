"""PostgreSQL migration checks for WP-PO-002 Stage 2D."""
from __future__ import annotations

from pathlib import Path
import hashlib
import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.db.engine import engine

REVISION = "v5w6x7y8z9a"
PARENT = "u4v5w6x7y8z"


def _cfg() -> Config:
    return Config(str(Path(__file__).parents[2] / "alembic.ini"))


def _migrate(action, revision: str) -> None:
    test_url = os.environ["TEST_DATABASE_URL"]
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url
    try:
        action(_cfg(), revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@pytest.fixture
def migration_row(seed) -> Iterator[int]:
    fingerprint = hashlib.sha256(f"stage2d-migration-{uuid.uuid4()}".encode()).hexdigest()
    with engine.begin() as conn:
        batch_id = int(conn.execute(text("""
            INSERT INTO operational_order_import_batches (
                source_manifest_name, source_manifest_sha256, batch_fingerprint,
                format_version, source_root_name, sheet_name, status, total_rows,
                valid_rows, error_rows, file_count, archive_section_count, created_by_user_id
            ) VALUES ('migration.xlsx', :sha, :fp, 'v1', 'archive', 'orders',
                      'IMPORTED', 1, 1, 0, 1, 1, :actor) RETURNING id
        """), {"sha": hashlib.sha256(b"migration").hexdigest(), "fp": fingerprint, "actor": int(seed["initiator_user_id"])}).scalar_one())
        row_id = int(conn.execute(text("""
            INSERT INTO operational_order_import_rows (
                batch_id, source_row_number, source_filename, source_document_type,
                source_status, source_event_type, source_folder, archive_section,
                relative_path, file_extension, file_size, file_sha256, initial_review_state
            ) VALUES (:batch, '1', 'migration.docx', 'Приказ', 'Найден', 'Subject',
                      'archive', 'Section', 'Section/migration.docx', '.docx', 1, :sha,
                      'NEEDS_REQUISITES') RETURNING id
        """), {"batch": batch_id, "sha": hashlib.sha256(b"migration-file").hexdigest()}).scalar_one())
    try:
        yield row_id
    finally:
        _migrate(command.upgrade, REVISION)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM operational_order_import_batches WHERE id=:id"), {"id": batch_id})


def test_migration_upgrade_permission_grants_and_columns():
    _migrate(command.upgrade, REVISION)
    with engine.connect() as conn:
        columns = set(conn.execute(text("select column_name from information_schema.columns where table_name='operational_order_import_rows' and column_name in ('confirmed_subject','review_comment')")).scalars())
        grants = set(conn.execute(text("""select r.code from access_grants g join access_roles ar on ar.access_role_id=g.access_role_id join roles r on g.target_type='ROLE' and g.target_id=r.role_id where ar.code='OPERATIONAL_ORDER_ARCHIVE_REVIEW' and g.active_flag""")).scalars())
    assert columns == {"confirmed_subject", "review_comment"}
    assert grants == {"HR_reg", "ADMIN"}


def test_revision_has_the_single_expected_parent_and_head():
    scripts = ScriptDirectory.from_config(_cfg())
    assert scripts.get_heads() == [REVISION]
    assert scripts.get_revision(REVISION).down_revision == PARENT


def test_review_outcome_and_required_field_checks(migration_row):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("update operational_order_import_rows set review_outcome='OTHER' where id=:id"), {"id": migration_row})
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("update operational_order_import_rows set review_outcome='CONFIRMED' where id=:id"), {"id": migration_row})
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text("update operational_order_import_rows set review_outcome='DUPLICATE' where id=:id"), {"id": migration_row})


@pytest.mark.parametrize(
    ("outcome", "values"),
    [
        ("CONFIRMED", {"document_type": "Приказ", "number": "1", "date": "2026-08-30", "subject": "Название", "comment": None}),
        ("NEEDS_CLARIFICATION", {"document_type": None, "number": None, "date": None, "subject": None, "comment": "Уточнить"}),
        ("DRAFT_ORDER", {"document_type": None, "number": None, "date": None, "subject": None, "comment": "Проект"}),
        ("ORDER_ANNEX", {"document_type": None, "number": None, "date": None, "subject": None, "comment": "Приложение"}),
        ("SUPPORTING_DOCUMENT", {"document_type": None, "number": None, "date": None, "subject": None, "comment": "Основание"}),
        ("DUPLICATE", {"document_type": None, "number": None, "date": None, "subject": None, "comment": "Дубль"}),
        ("NOT_AN_ORDER", {"document_type": None, "number": None, "date": None, "subject": None, "comment": "Не приказ"}),
    ],
)
def test_database_accepts_each_supported_outcome(migration_row, outcome, values):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE operational_order_import_rows
                SET review_outcome=:outcome,
                    confirmed_document_type=:document_type,
                    confirmed_order_number=:number,
                    confirmed_order_date=:date,
                    confirmed_subject=:subject,
                    review_comment=:comment
                WHERE id=:id
                """
            ),
            {"id": migration_row, "outcome": outcome, **values},
        )


@pytest.mark.parametrize("column", ["confirmed_document_type", "confirmed_order_number", "confirmed_subject"])
def test_confirmed_required_text_rejects_whitespace(migration_row, column):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE operational_order_import_rows
                SET confirmed_document_type='Приказ', confirmed_order_number='1',
                    confirmed_order_date=DATE '2026-08-30', confirmed_subject='Название'
                WHERE id=:id
                """
            ),
            {"id": migration_row},
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE operational_order_import_rows SET review_outcome='CONFIRMED', {column}='   ' WHERE id=:id"),
                {"id": migration_row},
            )


@pytest.mark.parametrize(
    "outcome",
    [
        "NEEDS_CLARIFICATION",
        "DRAFT_ORDER",
        "ORDER_ANNEX",
        "SUPPORTING_DOCUMENT",
        "DUPLICATE",
        "NOT_AN_ORDER",
    ],
)
def test_non_confirmed_comment_rejects_whitespace(migration_row, outcome):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE operational_order_import_rows SET review_outcome=:outcome, review_comment='   ' WHERE id=:id"),
                {"id": migration_row, "outcome": outcome},
            )


@pytest.mark.parametrize(
    "outcome",
    ["NEEDS_CLARIFICATION", "DRAFT_ORDER", "ORDER_ANNEX", "SUPPORTING_DOCUMENT", "DUPLICATE", "NOT_AN_ORDER"],
)
def test_non_confirmed_outcome_rejects_confirmed_fields(migration_row, outcome):
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE operational_order_import_rows
                    SET review_outcome=:outcome, review_comment='Причина',
                        confirmed_document_type='Приказ'
                    WHERE id=:id
                    """
                ),
                {"id": migration_row, "outcome": outcome},
            )


def test_source_fields_still_immutable_and_review_fields_mutable(migration_row):
    with pytest.raises(DBAPIError):
        with engine.begin() as conn:
            conn.execute(text("update operational_order_import_rows set source_event_type='changed' where id=:id"), {"id": migration_row})
    with engine.begin() as conn:
        conn.execute(text("update operational_order_import_rows set confirmed_subject='Allowed', review_comment='Allowed' where id=:id"), {"id": migration_row})


def test_guarded_downgrade_for_confirmed_subject(migration_row):
    with engine.begin() as conn:
        conn.execute(text("update operational_order_import_rows set confirmed_subject='Reviewed' where id=:id"), {"id": migration_row})
    with pytest.raises(Exception, match="downgrade refused"):
        _migrate(command.downgrade, PARENT)


def test_guarded_downgrade_for_review_comment(migration_row):
    with engine.begin() as conn:
        conn.execute(text("update operational_order_import_rows set review_comment='Reviewed' where id=:id"), {"id": migration_row})
    with pytest.raises(Exception, match="downgrade refused"):
        _migrate(command.downgrade, PARENT)


def test_empty_downgrade_and_reupgrade():
    with engine.begin() as conn:
        used = conn.execute(text("select count(*) from operational_order_import_rows where confirmed_subject is not null or review_comment is not null")).scalar_one()
    assert used == 0
    _migrate(command.downgrade, PARENT)
    with engine.connect() as conn:
        assert conn.execute(text("select version_num from alembic_version")).scalar_one() == PARENT
        assert conn.execute(text("select to_regclass('public.operational_order_import_rows') is not null")).scalar_one()
    _migrate(command.upgrade, REVISION)
