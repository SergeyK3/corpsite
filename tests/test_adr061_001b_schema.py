"""Schema contract tests for WP-ADR061-001B person photo foundation."""
from __future__ import annotations

from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import get_columns, table_exists
from tests.ppr.conftest import insert_person, ppr_db_available

REVISION_ID = "c0d1e2f3a4b5"
PREVIOUS_REVISION = "a9b0c1d2e3f4"

MIME_TYPE_JPEG = "image/jpeg"
SOURCE_KIND_INTAKE = "intake"
CANONICALIZATION_MODE_HIRE_APPLY = "hire_apply"
CANONICALIZATION_MODE_BACKFILL = "backfill"
CANONICALIZATION_MODE_TRANSFER = "transfer"
BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE = "INTAKE_PHOTO_UNAVAILABLE"
BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED = "PHOTO_CANONICALIZATION_FAILED"

ADR061_001B_TABLES = (
    "person_photos",
    "person_photo_sources",
    "personnel_application_blockers",
)

EXPECTED_INDEXES = (
    "uq_person_photos_one_active",
    "uq_person_photos_storage_rel_path",
    "uq_person_photo_sources_intake_material",
    "uq_person_photo_sources_command_id",
    "uq_personnel_application_blockers_open",
)


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)))
    return cfg


def _require_schema() -> None:
    with engine.begin() as conn:
        if not all(table_exists(conn, name) for name in ADR061_001B_TABLES):
            pytest.skip(
                f"WP-ADR061-001B tables missing — run: alembic upgrade head (revision {REVISION_ID})"
            )


def _expect_sql_failure(conn, sql: str, params: dict | None = None) -> None:
    nested = conn.begin_nested()
    with pytest.raises(Exception):
        conn.execute(text(sql), params or {})
    nested.rollback()


def _file_id() -> str:
    return uuid4().hex


def _sha256() -> str:
    return "a" * 64


def _storage_path(*, person_id: int, file_id: str | None = None) -> str:
    return f"person/{person_id}/{file_id or _file_id()}.jpg"


def _sample_user_id(conn) -> int:
    row = conn.execute(text("SELECT user_id FROM public.users LIMIT 1")).mappings().first()
    if row is None:
        pytest.skip("users table empty")
    return int(row["user_id"])


def _insert_active_photo(
    conn,
    *,
    person_id: int,
    file_id: str | None = None,
    storage_rel_path: str | None = None,
    checksum: str | None = None,
    user_id: int | None = None,
) -> int:
    fid = file_id or _file_id()
    path = storage_rel_path or _storage_path(person_id=person_id, file_id=fid)
    row = conn.execute(
        text(
            """
            INSERT INTO public.person_photos (
                person_id, file_id, storage_rel_path, mime_type, byte_size,
                checksum_sha256, is_active, uploaded_by_user_id
            ) VALUES (
                :person_id, :file_id, :storage_rel_path, :mime_type, :byte_size,
                :checksum_sha256, TRUE, :user_id
            )
            RETURNING person_photo_id
            """
        ),
        {
            "person_id": person_id,
            "file_id": fid,
            "storage_rel_path": path,
            "mime_type": MIME_TYPE_JPEG,
            "byte_size": 1024,
            "checksum_sha256": checksum or _sha256(),
            "user_id": user_id,
        },
    ).mappings().one()
    return int(row["person_photo_id"])


def _insert_terminal_photo(
    conn,
    *,
    person_id: int,
    file_id: str | None = None,
) -> int:
    fid = file_id or _file_id()
    row = conn.execute(
        text(
            """
            INSERT INTO public.person_photos (
                person_id, file_id, storage_rel_path, mime_type, byte_size,
                checksum_sha256, is_active, superseded_at
            ) VALUES (
                :person_id, :file_id, :storage_rel_path, :mime_type, :byte_size,
                :checksum_sha256, FALSE, NOW()
            )
            RETURNING person_photo_id
            """
        ),
        {
            "person_id": person_id,
            "file_id": fid,
            "storage_rel_path": _storage_path(person_id=person_id, file_id=fid),
            "mime_type": MIME_TYPE_JPEG,
            "byte_size": 1024,
            "checksum_sha256": _sha256(),
        },
    ).mappings().one()
    return int(row["person_photo_id"])


def _insert_intake_source(
    conn,
    *,
    person_photo_id: int,
    person_id: int,
    application_id: int,
    intake_file_id: str | None = None,
    command_id: str | None = None,
    mode: str = CANONICALIZATION_MODE_HIRE_APPLY,
    user_id: int | None = None,
) -> int:
    intake_file_id = intake_file_id or _file_id()
    command_id = command_id or (
        f"person-photo:canonicalize:intake:{application_id}:{intake_file_id}"
    )
    row = conn.execute(
        text(
            """
            INSERT INTO public.person_photo_sources (
                person_photo_id, person_id, source_kind, canonicalization_mode,
                source_application_id, source_intake_photo_file_id, command_id,
                canonicalized_by_user_id
            ) VALUES (
                :person_photo_id, :person_id, :source_kind, :mode,
                :application_id, :intake_file_id, :command_id, :user_id
            )
            RETURNING person_photo_source_id
            """
        ),
        {
            "person_photo_id": person_photo_id,
            "person_id": person_id,
            "source_kind": SOURCE_KIND_INTAKE,
            "mode": mode,
            "application_id": application_id,
            "intake_file_id": intake_file_id,
            "command_id": command_id,
            "user_id": user_id,
        },
    ).mappings().one()
    return int(row["person_photo_source_id"])


def _insert_application(conn, *, person_id: int, user_id: int) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO public.personnel_applications (
                person_id, application_received_at, vacancy_check_status,
                registered_by_user_id, status
            ) VALUES (
                :person_id, CURRENT_DATE, 'confirmed_visually', :user_id, 'registered'
            )
            RETURNING application_id
            """
        ),
        {"person_id": person_id, "user_id": user_id},
    ).mappings().one()
    return int(row["application_id"])


@pytest.fixture
def db_tx():
    conn = engine.connect()
    tx = conn.begin()
    try:
        yield conn
    finally:
        tx.rollback()
        conn.close()


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    revision = script.get_revision(REVISION_ID)
    assert revision is not None
    assert revision.down_revision == PREVIOUS_REVISION


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_tables_columns_and_indexes_exist(db_tx) -> None:
    _require_schema()
    for name in ADR061_001B_TABLES:
        assert table_exists(db_tx, name)

    photo_cols = get_columns(db_tx, "person_photos")
    assert {
        "person_photo_id",
        "person_id",
        "file_id",
        "storage_rel_path",
        "mime_type",
        "byte_size",
        "checksum_sha256",
        "is_active",
        "superseded_at",
        "uploaded_by_user_id",
        "created_at",
    }.issubset(photo_cols)

    indexes = {
        row[0]
        for row in db_tx.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = ANY(:names)
                """
            ),
            {"names": list(EXPECTED_INDEXES)},
        )
    }
    assert indexes == set(EXPECTED_INDEXES)


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_photos_check_constraints(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 CHECK {uuid4().hex[:6]}")
    user_id = _sample_user_id(db_tx)
    base = {
        "person_id": person_id,
        "file_id": _file_id(),
        "storage_rel_path": _storage_path(person_id=person_id),
        "mime_type": MIME_TYPE_JPEG,
        "byte_size": 1024,
        "checksum_sha256": _sha256(),
        "user_id": user_id,
    }
    insert_sql = """
        INSERT INTO public.person_photos (
            person_id, file_id, storage_rel_path, mime_type, byte_size,
            checksum_sha256, is_active, uploaded_by_user_id
        ) VALUES (
            :person_id, :file_id, :storage_rel_path, :mime_type, :byte_size,
            :checksum_sha256, TRUE, :user_id
        )
    """

    _expect_sql_failure(
        db_tx,
        insert_sql,
        {**base, "file_id": "not-hex"},
    )
    _expect_sql_failure(
        db_tx,
        insert_sql,
        {**base, "mime_type": "image/png"},
    )
    _expect_sql_failure(
        db_tx,
        insert_sql,
        {**base, "byte_size": 0},
    )
    _expect_sql_failure(
        db_tx,
        insert_sql,
        {**base, "byte_size": 512001},
    )
    _expect_sql_failure(
        db_tx,
        insert_sql,
        {**base, "checksum_sha256": "zz" * 32},
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photos (
            person_id, file_id, storage_rel_path, mime_type, byte_size,
            checksum_sha256, is_active, superseded_at
        ) VALUES (
            :person_id, :file_id, :storage_rel_path, :mime_type, :byte_size,
            :checksum_sha256, TRUE, NOW()
        )
        """,
        base,
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photos (
            person_id, file_id, storage_rel_path, mime_type, byte_size,
            checksum_sha256, is_active, superseded_at
        ) VALUES (
            :person_id, :file_id, :storage_rel_path, :mime_type, :byte_size,
            :checksum_sha256, FALSE, NULL
        )
        """,
        base,
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_photos_partial_unique_active_and_storage_path(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 UQ {uuid4().hex[:6]}")
    user_id = _sample_user_id(db_tx)
    file_id = _file_id()
    path = _storage_path(person_id=person_id, file_id=file_id)
    _insert_active_photo(
        db_tx,
        person_id=person_id,
        file_id=file_id,
        storage_rel_path=path,
        user_id=user_id,
    )

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photos (
            person_id, file_id, storage_rel_path, mime_type, byte_size,
            checksum_sha256, is_active
        ) VALUES (
            :person_id, :file_id, :storage_rel_path, :mime_type, :byte_size,
            :checksum_sha256, TRUE
        )
        """,
        {
            "person_id": person_id,
            "file_id": _file_id(),
            "storage_rel_path": _storage_path(person_id=person_id),
            "mime_type": MIME_TYPE_JPEG,
            "byte_size": 2048,
            "checksum_sha256": "b" * 64,
        },
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photos (
            person_id, file_id, storage_rel_path, mime_type, byte_size,
            checksum_sha256, is_active
        ) VALUES (
            :person_id, :file_id, :storage_rel_path, :mime_type, :byte_size,
            :checksum_sha256, TRUE
        )
        """,
        {
            "person_id": insert_person(db_tx, full_name=f"ADR061 UQ2 {uuid4().hex[:6]}"),
            "file_id": _file_id(),
            "storage_rel_path": path,
            "mime_type": MIME_TYPE_JPEG,
            "byte_size": 2048,
            "checksum_sha256": "c" * 64,
        },
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_photos_fk_to_persons(db_tx) -> None:
    _require_schema()
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photos (
            person_id, file_id, storage_rel_path, mime_type, byte_size,
            checksum_sha256, is_active
        ) VALUES (
            999999999, :file_id, :storage_rel_path, :mime_type, :byte_size,
            :checksum_sha256, TRUE
        )
        """,
        {
            "file_id": _file_id(),
            "storage_rel_path": "person/999999999/x.jpg",
            "mime_type": MIME_TYPE_JPEG,
            "byte_size": 1024,
            "checksum_sha256": _sha256(),
        },
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_photos_terminal_superseded_trigger(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 TRG {uuid4().hex[:6]}")
    user_id = _sample_user_id(db_tx)
    photo_id = _insert_active_photo(db_tx, person_id=person_id, user_id=user_id)

    db_tx.execute(
        text(
            """
            UPDATE public.person_photos
            SET is_active = FALSE, superseded_at = NOW()
            WHERE person_photo_id = :photo_id
            """
        ),
        {"photo_id": photo_id},
    )

    _expect_sql_failure(
        db_tx,
        """
        UPDATE public.person_photos
        SET is_active = TRUE
        WHERE person_photo_id = :photo_id
        """,
        {"photo_id": photo_id},
    )
    _expect_sql_failure(
        db_tx,
        """
        UPDATE public.person_photos
        SET superseded_at = NULL
        WHERE person_photo_id = :photo_id
        """,
        {"photo_id": photo_id},
    )
    _expect_sql_failure(
        db_tx,
        """
        UPDATE public.person_photos
        SET checksum_sha256 = :checksum
        WHERE person_photo_id = :photo_id
        """,
        {"photo_id": photo_id, "checksum": "d" * 64},
    )
    _expect_sql_failure(
        db_tx,
        "DELETE FROM public.person_photos WHERE person_photo_id = :photo_id",
        {"photo_id": photo_id},
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_photos_cannot_reactivate_inactive_without_superseded(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 REACT {uuid4().hex[:6]}")
    photo_id = _insert_terminal_photo(db_tx, person_id=person_id)
    _expect_sql_failure(
        db_tx,
        """
        UPDATE public.person_photos
        SET is_active = TRUE
        WHERE person_photo_id = :photo_id
        """,
        {"photo_id": photo_id},
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_photos_deactivate_requires_superseded_at(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 DEACT {uuid4().hex[:6]}")
    photo_id = _insert_active_photo(db_tx, person_id=person_id)
    _expect_sql_failure(
        db_tx,
        """
        UPDATE public.person_photos
        SET is_active = FALSE
        WHERE person_photo_id = :photo_id
        """,
        {"photo_id": photo_id},
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_photo_sources_conditional_checks(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 SRC {uuid4().hex[:6]}")
    user_id = _sample_user_id(db_tx)
    application_id = _insert_application(db_tx, person_id=person_id, user_id=user_id)
    photo_id = _insert_active_photo(db_tx, person_id=person_id, user_id=user_id)
    intake_file_id = _file_id()

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photo_sources (
            person_photo_id, person_id, source_kind, canonicalization_mode,
            source_application_id, source_intake_photo_file_id, command_id
        ) VALUES (
            :photo_id, :person_id, 'intake', :mode, NULL, :file_id, :command_id
        )
        """,
        {
            "photo_id": photo_id,
            "person_id": person_id,
            "mode": CANONICALIZATION_MODE_HIRE_APPLY,
            "file_id": intake_file_id,
            "command_id": f"person-photo:canonicalize:intake:{application_id}:{intake_file_id}",
        },
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photo_sources (
            person_photo_id, person_id, source_kind, canonicalization_mode,
            command_id
        ) VALUES (
            :photo_id, :person_id, 'manual_upload', 'hire_apply', :command_id
        )
        """,
        {
            "photo_id": photo_id,
            "person_id": person_id,
            "command_id": f"manual-{uuid4().hex}",
        },
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photo_sources (
            person_photo_id, person_id, source_kind, canonicalization_mode,
            source_application_id, source_intake_photo_file_id, command_id
        ) VALUES (
            :photo_id, :person_id, 'manual_upload', 'transfer',
            :application_id, :file_id, :command_id
        )
        """,
        {
            "photo_id": photo_id,
            "person_id": person_id,
            "application_id": application_id,
            "file_id": intake_file_id,
            "command_id": f"manual-{uuid4().hex}",
        },
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photo_sources (
            person_photo_id, person_id, source_kind, canonicalization_mode,
            command_id
        ) VALUES (
            :photo_id, :person_id, 'manual_upload', 'transfer', '   '
        )
        """,
        {"photo_id": photo_id, "person_id": person_id},
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_photo_sources_composite_fk_and_intake_partial_unique(db_tx) -> None:
    _require_schema()
    person_a = insert_person(db_tx, full_name=f"ADR061 A {uuid4().hex[:6]}")
    person_b = insert_person(db_tx, full_name=f"ADR061 B {uuid4().hex[:6]}")
    user_id = _sample_user_id(db_tx)
    app_a = _insert_application(db_tx, person_id=person_a, user_id=user_id)
    photo_a = _insert_active_photo(db_tx, person_id=person_a, user_id=user_id)
    intake_file_id = _file_id()
    command_id = f"person-photo:canonicalize:intake:{app_a}:{intake_file_id}"

    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photo_sources (
            person_photo_id, person_id, source_kind, canonicalization_mode,
            source_application_id, source_intake_photo_file_id, command_id
        ) VALUES (
            :photo_id, :wrong_person_id, 'intake', :mode,
            :application_id, :file_id, :command_id
        )
        """,
        {
            "photo_id": photo_a,
            "wrong_person_id": person_b,
            "mode": CANONICALIZATION_MODE_HIRE_APPLY,
            "application_id": app_a,
            "file_id": intake_file_id,
            "command_id": command_id,
        },
    )

    _insert_intake_source(
        db_tx,
        person_photo_id=photo_a,
        person_id=person_a,
        application_id=app_a,
        intake_file_id=intake_file_id,
        command_id=command_id,
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photo_sources (
            person_photo_id, person_id, source_kind, canonicalization_mode,
            source_application_id, source_intake_photo_file_id, command_id
        ) VALUES (
            :photo_id, :person_id, 'intake', :mode,
            :application_id, :file_id, :command_id2
        )
        """,
        {
            "photo_id": photo_a,
            "person_id": person_a,
            "mode": CANONICALIZATION_MODE_BACKFILL,
            "application_id": app_a,
            "file_id": intake_file_id,
            "command_id2": f"person-photo:canonicalize:intake:{app_a}:{intake_file_id}:dup",
        },
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_photo_sources_command_id_unique(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 CMD {uuid4().hex[:6]}")
    user_id = _sample_user_id(db_tx)
    application_id = _insert_application(db_tx, person_id=person_id, user_id=user_id)
    photo_id = _insert_active_photo(db_tx, person_id=person_id, user_id=user_id)
    command_id = f"manual-{uuid4().hex}"
    _insert_intake_source(
        db_tx,
        person_photo_id=photo_id,
        person_id=person_id,
        application_id=application_id,
        command_id=command_id,
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photo_sources (
            person_photo_id, person_id, source_kind, canonicalization_mode,
            source_application_id, source_intake_photo_file_id, command_id
        ) VALUES (
            :photo_id, :person_id, 'intake', :mode,
            :application_id, :file_id, :command_id
        )
        """,
        {
            "photo_id": photo_id,
            "person_id": person_id,
            "mode": CANONICALIZATION_MODE_TRANSFER,
            "application_id": application_id + 1,
            "file_id": _file_id(),
            "command_id": command_id,
        },
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_person_photo_sources_append_only(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 AO {uuid4().hex[:6]}")
    user_id = _sample_user_id(db_tx)
    application_id = _insert_application(db_tx, person_id=person_id, user_id=user_id)
    photo_id = _insert_active_photo(db_tx, person_id=person_id, user_id=user_id)
    source_id = _insert_intake_source(
        db_tx,
        person_photo_id=photo_id,
        person_id=person_id,
        application_id=application_id,
    )
    _expect_sql_failure(
        db_tx,
        """
        UPDATE public.person_photo_sources
        SET correlation_id = 'changed'
        WHERE person_photo_source_id = :source_id
        """,
        {"source_id": source_id},
    )
    _expect_sql_failure(
        db_tx,
        """
        DELETE FROM public.person_photo_sources
        WHERE person_photo_source_id = :source_id
        """,
        {"source_id": source_id},
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_personnel_application_blockers_checks_and_partial_unique(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 BLK {uuid4().hex[:6]}")
    user_id = _sample_user_id(db_tx)
    application_id = _insert_application(db_tx, person_id=person_id, user_id=user_id)

    db_tx.execute(
        text(
            """
            INSERT INTO public.personnel_application_blockers (
                application_id, blocker_code
            ) VALUES (
                :application_id, :blocker_code
            )
            """
        ),
        {
            "application_id": application_id,
            "blocker_code": BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
        },
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.personnel_application_blockers (
            application_id, blocker_code
        ) VALUES (
            :application_id, :blocker_code
        )
        """,
        {
            "application_id": application_id,
            "blocker_code": BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
        },
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.personnel_application_blockers (
            application_id, blocker_code
        ) VALUES (
            :application_id, 'UNKNOWN_BLOCKER'
        )
        """,
        {"application_id": application_id},
    )
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.personnel_application_blockers (
            application_id, blocker_code, resolved_at
        ) VALUES (
            :application_id, :blocker_code, NOW()
        )
        """,
        {
            "application_id": application_id,
            "blocker_code": BLOCKER_CODE_PHOTO_CANONICALIZATION_FAILED,
        },
    )

    db_tx.execute(
        text(
            """
            UPDATE public.personnel_application_blockers
            SET resolved_at = NOW(), resolved_by_user_id = :user_id
            WHERE application_id = :application_id
              AND blocker_code = :blocker_code
            """
        ),
        {
            "application_id": application_id,
            "blocker_code": BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
            "user_id": user_id,
        },
    )
    db_tx.execute(
        text(
            """
            INSERT INTO public.personnel_application_blockers (
                application_id, blocker_code
            ) VALUES (
                :application_id, :blocker_code
            )
            """
        ),
        {
            "application_id": application_id,
            "blocker_code": BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
        },
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_source_application_id_has_no_fk(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 NOFK {uuid4().hex[:6]}")
    user_id = _sample_user_id(db_tx)
    photo_id = _insert_active_photo(db_tx, person_id=person_id, user_id=user_id)
    orphan_app_id = 9_000_000 + int(uuid4().hex[:6], 16) % 1_000_000
    intake_file_id = _file_id()
    _insert_intake_source(
        db_tx,
        person_photo_id=photo_id,
        person_id=person_id,
        application_id=orphan_app_id,
        intake_file_id=intake_file_id,
        command_id=f"person-photo:canonicalize:intake:{orphan_app_id}:{intake_file_id}",
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_insert_without_is_active_rejected(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 NOIA {uuid4().hex[:6]}")
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photos (
            person_id, file_id, storage_rel_path, mime_type, byte_size, checksum_sha256
        ) VALUES (
            :person_id, :file_id, :storage_rel_path, :mime_type, :byte_size, :checksum_sha256
        )
        """,
        {
            "person_id": person_id,
            "file_id": _file_id(),
            "storage_rel_path": _storage_path(person_id=person_id),
            "mime_type": MIME_TYPE_JPEG,
            "byte_size": 1024,
            "checksum_sha256": _sha256(),
        },
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_update_person_photo_id_rejected(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 PK {uuid4().hex[:6]}")
    photo_id = _insert_active_photo(db_tx, person_id=person_id)
    _expect_sql_failure(
        db_tx,
        """
        UPDATE public.person_photos
        SET person_photo_id = :new_id
        WHERE person_photo_id = :photo_id
        """,
        {"photo_id": photo_id, "new_id": photo_id + 1},
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_blocker_resolved_by_without_resolved_at_rejected(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 RES {uuid4().hex[:6]}")
    user_id = _sample_user_id(db_tx)
    application_id = _insert_application(db_tx, person_id=person_id, user_id=user_id)
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.personnel_application_blockers (
            application_id, blocker_code, resolved_by_user_id
        ) VALUES (
            :application_id, :blocker_code, :user_id
        )
        """,
        {
            "application_id": application_id,
            "blocker_code": BLOCKER_CODE_INTAKE_PHOTO_UNAVAILABLE,
            "user_id": user_id,
        },
    )


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_invalid_source_intake_photo_file_id_rejected(db_tx) -> None:
    _require_schema()
    person_id = insert_person(db_tx, full_name=f"ADR061 IFID {uuid4().hex[:6]}")
    user_id = _sample_user_id(db_tx)
    application_id = _insert_application(db_tx, person_id=person_id, user_id=user_id)
    photo_id = _insert_active_photo(db_tx, person_id=person_id, user_id=user_id)
    _expect_sql_failure(
        db_tx,
        """
        INSERT INTO public.person_photo_sources (
            person_photo_id, person_id, source_kind, canonicalization_mode,
            source_application_id, source_intake_photo_file_id, command_id
        ) VALUES (
            :photo_id, :person_id, 'intake', :mode,
            :application_id, :file_id, :command_id
        )
        """,
        {
            "photo_id": photo_id,
            "person_id": person_id,
            "mode": CANONICALIZATION_MODE_HIRE_APPLY,
            "application_id": application_id,
            "file_id": "not-a-valid-hex-file-id",
            "command_id": f"person-photo:canonicalize:intake:{application_id}:bad",
        },
    )
