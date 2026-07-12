# tests/operational_orders/test_draft_intake_service.py
"""Unit/service tests for Operational Orders draft intake."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.operational_orders import LOCALE_KK, LOCALE_RU, STALENESS_REVIEW_REQUIRED
from app.operational_orders.errors import (
    OperationalOrderSubmittedTextImmutableError,
    OperationalOrderValidationBlockedError,
    OperationalOrderVersionConflictError,
)
from app.operational_orders.services import draft_intake_service as svc
from tests.operational_orders.conftest import cleanup_workspace

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")


def _party(ref: str, *, display: str | None = None) -> dict:
    return {
        "reference_type": "PERSON",
        "reference": ref,
        "display_name": display or ref,
    }


def _block(locale: str, text_value: str, *, block_type: str = "BODY", sequence: int = 1) -> dict:
    return {
        "locale": locale,
        "block_type": block_type,
        "submitted_text": text_value,
        "source_type": "SUBMITTED",
        "sequence": sequence,
    }


@pytest.fixture
def seed_unit(seed):
    return int(seed["unit_id"])


@pytest.fixture
def creator_id(seed):
    return int(seed["initiator_user_id"])


def _create_ru_kk(seed_unit: int, creator_id: int, author_ref: str = "author-001"):
    return svc.create_submission(
        initiator_type="PERSON",
        initiator_reference="initiator-001",
        initiator_display_name="Initiator One",
        content_author_type="PERSON",
        content_author_reference=author_ref,
        content_author_display_name="Author One",
        submitting_org_unit_id=seed_unit,
        record_creator_user_id=creator_id,
        blocks=[
            _block(LOCALE_RU, "RU body text", block_type="TITLE"),
            _block(LOCALE_KK, "KK body text", block_type="TITLE"),
        ],
        organization_id=seed_unit,
    )


def test_create_ru_only_submission(seed_unit, creator_id):
    detail = svc.create_submission(
        initiator_type="PERSON",
        initiator_reference="init-ru",
        initiator_display_name=None,
        content_author_type="PERSON",
        content_author_reference="author-ru",
        content_author_display_name=None,
        submitting_org_unit_id=seed_unit,
        record_creator_user_id=creator_id,
        blocks=[_block(LOCALE_RU, "Only RU text")],
        organization_id=seed_unit,
    )
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        assert detail["workspace"]["stage"] == "SUBMITTED"
        assert len(detail["blocks"]) == 1
        assert detail["blocks"][0]["locale"] == LOCALE_RU
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_create_kk_only_submission(seed_unit, creator_id):
    detail = svc.create_submission(
        initiator_type="PERSON",
        initiator_reference="init-kk",
        initiator_display_name=None,
        content_author_type="PERSON",
        content_author_reference="author-kk",
        content_author_display_name=None,
        submitting_org_unit_id=seed_unit,
        record_creator_user_id=creator_id,
        blocks=[_block(LOCALE_KK, "Only KK text")],
        organization_id=seed_unit,
    )
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        assert detail["blocks"][0]["locale"] == LOCALE_KK
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_create_ru_kk_submission(seed_unit, creator_id):
    detail = _create_ru_kk(seed_unit, creator_id)
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        locales = {block["locale"] for block in detail["blocks"]}
        assert locales == {LOCALE_RU, LOCALE_KK}
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_content_author_differs_from_record_creator(seed_unit, creator_id):
    detail = _create_ru_kk(seed_unit, creator_id, author_ref="different-author")
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        ws = detail["workspace"]
        assert str(ws["content_author_reference"]) != str(ws["record_creator_user_id"])
        assert int(ws["record_creator_user_id"]) == creator_id
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_missing_author_rejected(seed_unit, creator_id):
    with pytest.raises(Exception):
        svc.create_submission(
            initiator_type="PERSON",
            initiator_reference="init",
            initiator_display_name=None,
            content_author_type="PERSON",
            content_author_reference="",
            content_author_display_name=None,
            submitting_org_unit_id=seed_unit,
            record_creator_user_id=creator_id,
            blocks=[_block(LOCALE_RU, "Text")],
            organization_id=seed_unit,
        )


def test_submitted_text_immutable_guard():
    with pytest.raises(OperationalOrderSubmittedTextImmutableError):
        svc.guard_submitted_text_immutable(current_submitted_text="A", new_submitted_text="B")


def test_effective_text_editable_and_marks_kk_stale(seed_unit, creator_id):
    detail = _create_ru_kk(seed_unit, creator_id)
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        detail = svc.accept_submission(workspace_id=workspace_id, actor_user_id=creator_id)
        ru_block = next(b for b in detail["blocks"] if b["locale"] == LOCALE_RU)
        detail = svc.update_workspace_effective_text(
            workspace_id=workspace_id,
            block_id=int(ru_block["block_id"]),
            workspace_effective_text="Edited RU effective",
            actor_user_id=creator_id,
        )
        kk_block = next(b for b in detail["blocks"] if b["locale"] == LOCALE_KK)
        assert kk_block["review_state"] == STALENESS_REVIEW_REQUIRED
        ru_block = next(b for b in detail["blocks"] if b["locale"] == LOCALE_RU)
        assert ru_block["workspace_effective_text"] == "Edited RU effective"
        assert ru_block["submitted_text"] != ru_block["workspace_effective_text"]
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_provenance_append_only(seed_unit, creator_id):
    detail = _create_ru_kk(seed_unit, creator_id)
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        initial_count = len(detail["provenance"])
        detail = svc.accept_submission(workspace_id=workspace_id, actor_user_id=creator_id)
        assert len(detail["provenance"]) > initial_count
        with engine.begin() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM public.operational_order_text_provenance
                    WHERE workspace_id = :workspace_id
                    """
                ),
                {"workspace_id": workspace_id},
            ).scalar()
        assert int(count or 0) == len(detail["provenance"])
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_validation_findings_for_missing_locales(seed_unit, creator_id):
    detail = svc.create_submission(
        initiator_type="PERSON",
        initiator_reference="init",
        initiator_display_name=None,
        content_author_type="PERSON",
        content_author_reference="author",
        content_author_display_name=None,
        submitting_org_unit_id=seed_unit,
        record_creator_user_id=creator_id,
        blocks=[_block(LOCALE_RU, "RU only")],
        organization_id=seed_unit,
    )
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        detail = svc.run_intake_validation(workspace_id=workspace_id, actor_user_id=creator_id)
        codes = {issue.code for issue in detail["validation"].issues}
        assert "OI010" in codes
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_ready_for_editorial_allows_ru_only_for_translation_path(seed_unit, creator_id):
    detail = svc.create_submission(
        initiator_type="PERSON",
        initiator_reference="init",
        initiator_display_name=None,
        content_author_type="PERSON",
        content_author_reference="author",
        content_author_display_name=None,
        submitting_org_unit_id=seed_unit,
        record_creator_user_id=creator_id,
        blocks=[_block(LOCALE_RU, "RU only", block_type="TITLE")],
        organization_id=seed_unit,
    )
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        svc.accept_submission(workspace_id=workspace_id, actor_user_id=creator_id)
        detail = svc.mark_ready_for_editorial(workspace_id=workspace_id, actor_user_id=creator_id)
        assert detail["workspace"]["stage"] == "READY_FOR_EDITORIAL"
        assert any(issue.code == "OI010" for issue in detail["validation"].issues)
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_ready_for_editorial_success(seed_unit, creator_id):
    detail = _create_ru_kk(seed_unit, creator_id)
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        svc.accept_submission(workspace_id=workspace_id, actor_user_id=creator_id)
        detail = svc.mark_ready_for_editorial(workspace_id=workspace_id, actor_user_id=creator_id)
        assert detail["workspace"]["stage"] == "READY_FOR_EDITORIAL"
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_version_conflict(seed_unit, creator_id):
    detail = _create_ru_kk(seed_unit, creator_id)
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        version = int(detail["workspace"]["version"])
        svc.accept_submission(
            workspace_id=workspace_id,
            actor_user_id=creator_id,
            expected_version=version,
        )
        with pytest.raises(OperationalOrderVersionConflictError):
            svc.accept_submission(
                workspace_id=workspace_id,
                actor_user_id=creator_id,
                expected_version=version,
            )
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_no_document_id_created(seed_unit, creator_id):
    detail = _create_ru_kk(seed_unit, creator_id)
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        ws = detail["workspace"]
        assert "document_id" not in ws
        with engine.connect() as conn:
            cols = {row[0] for row in conn.execute(text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'operational_order_draft_workspaces'
                """
            ))}
        assert "document_id" not in cols
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_no_document_lifecycle_state(seed_unit, creator_id):
    detail = _create_ru_kk(seed_unit, creator_id)
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        assert detail["workspace"]["stage"] not in {
            "DRAFT",
            "READY_FOR_SIGNATURE",
            "SIGNED",
            "REGISTERED",
        }
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
