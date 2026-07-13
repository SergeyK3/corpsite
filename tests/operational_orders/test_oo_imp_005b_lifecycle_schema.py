# tests/operational_orders/test_oo_imp_005b_lifecycle_schema.py
"""Schema and lifecycle foundation tests for OO-IMP-005B."""
from __future__ import annotations

from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.operational_orders import (
    DOCUMENT_STATUS_CREATED,
    DOCUMENT_STATUS_PUBLISHED,
    DOCUMENT_STATUS_READY_FOR_SIGNATURE,
    DOCUMENT_STATUS_REGISTERED,
    DOCUMENT_STATUSES,
    OperationalOrderDocument,
)
from app.operational_orders.schemas.document_aggregate import DocumentSummaryOut
from app.operational_orders.validation.lifecycle_invariants import (
    validate_backward_compatible_document,
    validate_lifecycle_metadata,
    validate_published_metadata,
    validate_registered_metadata,
    validate_signed_metadata,
)
from tests.conftest import get_columns, table_exists

DDL_REVISION_005B = "c3d4e5f6a7b8"
DDL_REVISION_PREVIOUS = "b2c3d4e5f6a7"

NEW_DOCUMENT_COLUMNS = (
    "signed_at",
    "signed_by_user_id",
    "registration_number",
    "registration_year",
    "registration_date",
    "registered_at",
    "registered_by_user_id",
    "published_at",
    "published_by_user_id",
)


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


def _schema_available() -> bool:
    if not _db_available():
        return False
    with engine.connect() as conn:
        if not table_exists(conn, "operational_order_documents"):
            return False
        cols = get_columns(conn, "operational_order_documents")
    return all(column in cols for column in NEW_DOCUMENT_COLUMNS)


def _require_schema() -> None:
    if not _schema_available():
        pytest.skip(
            f"OO-IMP-005B schema missing — run: alembic upgrade head (revision {DDL_REVISION_005B})"
        )


def _migration_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "c3d4e5f6a7b8_oo_imp_005b_lifecycle_schema_foundation.py"
    )
    spec = spec_from_file_location("oo_imp_005b_migration", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration from {path}")
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_005b_downgrade_upgrade(conn) -> None:
    ctx = MigrationContext.configure(conn)
    mod = _migration_module()
    with Operations.context(ctx):
        mod.downgrade()
        conn.execute(
            text(
                """
                UPDATE public.operational_order_documents
                SET status = 'CREATED'
                WHERE status IN ('SIGNED', 'REGISTERED', 'PUBLISHED')
                """
            )
        )
        mod.upgrade()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_migration_revision_chain() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    rev = script.get_revision(DDL_REVISION_005B)
    assert rev is not None
    assert rev.down_revision == DDL_REVISION_PREVIOUS


def test_document_status_constants_include_published() -> None:
    assert DOCUMENT_STATUS_PUBLISHED == "PUBLISHED"
    assert DOCUMENT_STATUS_PUBLISHED in DOCUMENT_STATUSES


def test_operational_order_document_model_has_new_fields() -> None:
    for field_name in NEW_DOCUMENT_COLUMNS:
        assert field_name in OperationalOrderDocument.__table__.columns


def test_document_summary_serializes_new_nullable_fields() -> None:
    payload = DocumentSummaryOut(
        document_id=1,
        workspace_id=2,
        document_kind="OPERATIONAL_ORDER",
        status=DOCUMENT_STATUS_CREATED,
        created_from_workspace_version=1,
        created_from_workspace_fingerprint="fp",
        promotion_id=3,
        created_at=datetime.now(timezone.utc),
        created_by_user_id=4,
        version=1,
        signed_at=None,
        signed_by_user_id=None,
        registration_number=None,
        registration_year=None,
        registration_date=None,
        registered_at=None,
        registered_by_user_id=None,
        published_at=None,
        published_by_user_id=None,
    )
    dumped = payload.model_dump()
    for field_name in NEW_DOCUMENT_COLUMNS:
        assert field_name in dumped
        assert dumped[field_name] is None


def test_backward_compatible_created_document_valid() -> None:
    document = {"status": DOCUMENT_STATUS_CREATED, "id": 1}
    assert validate_backward_compatible_document(document).is_valid is True
    assert validate_lifecycle_metadata(document).is_valid is True


def test_backward_compatible_ready_for_signature_valid() -> None:
    document = {"status": DOCUMENT_STATUS_READY_FOR_SIGNATURE, "id": 1}
    assert validate_backward_compatible_document(document).is_valid is True


def test_registered_without_metadata_fails_invariant_helpers() -> None:
    document = {"status": DOCUMENT_STATUS_REGISTERED, "id": 1}
    assert validate_registered_metadata(document).is_valid is False


def test_signed_requires_signed_at() -> None:
    document = {"status": "SIGNED", "id": 1}
    assert validate_signed_metadata(document).is_valid is False
    document["signed_at"] = datetime.now(timezone.utc)
    assert validate_signed_metadata(document).is_valid is True


def test_published_requires_publication_metadata() -> None:
    document = {"status": DOCUMENT_STATUS_PUBLISHED, "id": 1}
    assert validate_published_metadata(document).is_valid is False
    document["published_at"] = datetime.now(timezone.utc)
    document["published_by_user_id"] = 10
    assert validate_published_metadata(document).is_valid is True


def test_personnel_orders_tables_unchanged() -> None:
    if not _db_available():
        pytest.skip("PostgreSQL not available")
    with engine.connect() as conn:
        assert table_exists(conn, "personnel_orders")
        cols = get_columns(conn, "personnel_orders")
    assert "order_id" in cols
    assert "published_at" not in cols


def test_005b_columns_exist() -> None:
    _require_schema()
    with engine.connect() as conn:
        cols = get_columns(conn, "operational_order_documents")
    for column in NEW_DOCUMENT_COLUMNS:
        assert column in cols


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_005b_migration_downgrade_upgrade() -> None:
    _require_schema()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            _run_005b_downgrade_upgrade(conn)
        finally:
            trans.rollback()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_registration_unique_allows_null() -> None:
    _require_schema()
    suffix = uuid4().hex[:8]
    workspace_ids: list[int] = []

    with engine.begin() as conn:
        for idx in range(2):
            workspace_id = conn.execute(
                text(
                    """
                    INSERT INTO public.operational_order_draft_workspaces (
                        organization_id,
                        drafting_path,
                        stage,
                        initiator_type,
                        initiator_reference,
                        content_author_type,
                        content_author_reference,
                        submitting_org_unit_id,
                        record_creator_user_id
                    )
                    SELECT
                        ou.unit_id,
                        'SUBMITTED_TEXT',
                        'DOCUMENT_PROMOTED',
                        'PERSON',
                        'pytest',
                        'PERSON',
                        :author_ref,
                        ou.unit_id,
                        u.user_id
                    FROM public.org_units ou
                    CROSS JOIN public.users u
                    WHERE ou.parent_unit_id IS NULL
                    ORDER BY ou.unit_id, u.user_id
                    LIMIT 1
                    RETURNING workspace_id
                    """
                ),
                {"author_ref": f"pytest-005b-null-{suffix}-{idx}"},
            ).scalar_one()
            workspace_ids.append(int(workspace_id))

            promotion_id = conn.execute(
                text(
                    """
                    INSERT INTO public.operational_order_promotions (
                        workspace_id,
                        status,
                        workspace_version,
                        workspace_fingerprint,
                        promoted_by_user_id
                    ) VALUES (
                        :workspace_id,
                        'COMPLETED',
                        1,
                        :fingerprint,
                        (SELECT user_id FROM public.users ORDER BY user_id LIMIT 1)
                    )
                    RETURNING id
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "fingerprint": f"fp-{suffix}-{idx}",
                },
            ).scalar_one()

            conn.execute(
                text(
                    """
                    INSERT INTO public.operational_order_documents (
                        workspace_id,
                        status,
                        created_from_workspace_version,
                        created_from_workspace_fingerprint,
                        promotion_id,
                        created_by_user_id,
                        registration_year,
                        registration_number
                    ) VALUES (
                        :workspace_id,
                        'CREATED',
                        1,
                        :fingerprint,
                        :promotion_id,
                        (SELECT user_id FROM public.users ORDER BY user_id LIMIT 1),
                        NULL,
                        NULL
                    )
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "fingerprint": f"doc-fp-{suffix}-{idx}",
                    "promotion_id": promotion_id,
                },
            )

        count = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM public.operational_order_documents
                WHERE created_from_workspace_fingerprint LIKE :pattern
                """
            ),
            {"pattern": f"doc-fp-{suffix}-%"},
        ).scalar_one()
        assert int(count) == 2


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_registration_unique_rejects_duplicate_year_number() -> None:
    _require_schema()
    suffix = uuid4().hex[:8]
    reg_year = 2026
    reg_number = f"OO-005B-{suffix}"

    with engine.begin() as conn:
        workspace_id = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_draft_workspaces (
                    organization_id,
                    drafting_path,
                    stage,
                    initiator_type,
                    initiator_reference,
                    content_author_type,
                    content_author_reference,
                    submitting_org_unit_id,
                    record_creator_user_id
                )
                SELECT
                    ou.unit_id,
                    'SUBMITTED_TEXT',
                    'DOCUMENT_PROMOTED',
                    'PERSON',
                    'pytest',
                    'PERSON',
                    :author_ref,
                    ou.unit_id,
                    u.user_id
                FROM public.org_units ou
                CROSS JOIN public.users u
                WHERE ou.parent_unit_id IS NULL
                ORDER BY ou.unit_id, u.user_id
                LIMIT 1
                RETURNING workspace_id
                """
            ),
            {"author_ref": f"pytest-005b-uniq-{suffix}-1"},
        ).scalar_one()

        promotion_id = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_promotions (
                    workspace_id,
                    status,
                    workspace_version,
                    workspace_fingerprint,
                    promoted_by_user_id
                ) VALUES (
                    :workspace_id,
                    'COMPLETED',
                    1,
                    :fingerprint,
                    (SELECT user_id FROM public.users ORDER BY user_id LIMIT 1)
                )
                RETURNING id
                """
            ),
            {
                "workspace_id": workspace_id,
                "fingerprint": f"fp-uniq-{suffix}-1",
            },
        ).scalar_one()

        conn.execute(
            text(
                """
                INSERT INTO public.operational_order_documents (
                    workspace_id,
                    status,
                    created_from_workspace_version,
                    created_from_workspace_fingerprint,
                    promotion_id,
                    created_by_user_id,
                    registration_year,
                    registration_number
                ) VALUES (
                    :workspace_id,
                    'CREATED',
                    1,
                    :fingerprint,
                    :promotion_id,
                    (SELECT user_id FROM public.users ORDER BY user_id LIMIT 1),
                    :registration_year,
                    :registration_number
                )
                """
            ),
            {
                "workspace_id": workspace_id,
                "fingerprint": f"doc-uniq-{suffix}-1",
                "promotion_id": promotion_id,
                "registration_year": reg_year,
                "registration_number": reg_number,
            },
        )

        workspace_id_2 = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_draft_workspaces (
                    organization_id,
                    drafting_path,
                    stage,
                    initiator_type,
                    initiator_reference,
                    content_author_type,
                    content_author_reference,
                    submitting_org_unit_id,
                    record_creator_user_id
                )
                SELECT
                    ou.unit_id,
                    'SUBMITTED_TEXT',
                    'DOCUMENT_PROMOTED',
                    'PERSON',
                    'pytest',
                    'PERSON',
                    :author_ref,
                    ou.unit_id,
                    u.user_id
                FROM public.org_units ou
                CROSS JOIN public.users u
                WHERE ou.parent_unit_id IS NULL
                ORDER BY ou.unit_id, u.user_id
                LIMIT 1
                RETURNING workspace_id
                """
            ),
            {"author_ref": f"pytest-005b-uniq-{suffix}-2"},
        ).scalar_one()

        promotion_id_2 = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_promotions (
                    workspace_id,
                    status,
                    workspace_version,
                    workspace_fingerprint,
                    promoted_by_user_id
                ) VALUES (
                    :workspace_id,
                    'COMPLETED',
                    1,
                    :fingerprint,
                    (SELECT user_id FROM public.users ORDER BY user_id LIMIT 1)
                )
                RETURNING id
                """
            ),
            {
                "workspace_id": workspace_id_2,
                "fingerprint": f"fp-uniq-{suffix}-2",
            },
        ).scalar_one()

        with pytest.raises(Exception):
            conn.execute(
                text(
                    """
                    INSERT INTO public.operational_order_documents (
                        workspace_id,
                        status,
                        created_from_workspace_version,
                        created_from_workspace_fingerprint,
                        promotion_id,
                        created_by_user_id,
                        registration_year,
                        registration_number
                    ) VALUES (
                        :workspace_id,
                        'CREATED',
                        1,
                        :fingerprint,
                        :promotion_id,
                        (SELECT user_id FROM public.users ORDER BY user_id LIMIT 1),
                        :registration_year,
                        :registration_number
                    )
                    """
                ),
                {
                    "workspace_id": workspace_id_2,
                    "fingerprint": f"doc-uniq-{suffix}-2",
                    "promotion_id": promotion_id_2,
                    "registration_year": reg_year,
                    "registration_number": reg_number,
                },
            )
