# tests/operational_orders/test_clarification_idempotency.py
"""Clarification idempotency tests for OO intake validation."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.operational_orders import CLARIFICATION_STATUS_OPEN, CLARIFICATION_STATUS_RESOLVED
from app.operational_orders.services import draft_intake_service as svc
from tests.operational_orders.conftest import cleanup_workspace

pytestmark = pytest.mark.usefixtures("_require_oo_schema_fixture")


def _create_ru_only(seed_unit: int, creator_id: int) -> dict:
    return svc.create_submission(
        initiator_type="PERSON",
        initiator_reference="init-clar",
        initiator_display_name=None,
        content_author_type="PERSON",
        content_author_reference="author-clar",
        content_author_display_name=None,
        submitting_org_unit_id=seed_unit,
        record_creator_user_id=creator_id,
        blocks=[
            {
                "locale": "ru",
                "block_type": "TITLE",
                "submitted_text": "RU only title",
                "source_type": "SUBMITTED",
                "sequence": 1,
            }
        ],
        organization_id=seed_unit,
    )


def _open_clarifications(conn, workspace_id: int, code: str) -> list[dict]:
    rows = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_clarifications
            WHERE workspace_id = :workspace_id
              AND code = :code
              AND status = :status
            ORDER BY clarification_id
            """
        ),
        {
            "workspace_id": int(workspace_id),
            "code": code,
            "status": CLARIFICATION_STATUS_OPEN,
        },
    ).mappings().all()
    return [dict(row) for row in rows]


@pytest.fixture
def creator_id(seed):
    return int(seed["initiator_user_id"])


def test_validate_twice_does_not_duplicate_open_clarification(seed, creator_id):
    detail = _create_ru_only(int(seed["unit_id"]), creator_id)
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        svc.run_intake_validation(workspace_id=workspace_id, actor_user_id=creator_id)
        svc.run_intake_validation(workspace_id=workspace_id, actor_user_id=creator_id)
        with engine.connect() as conn:
            open_rows = _open_clarifications(conn, workspace_id, "OI010")
        assert len(open_rows) == 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_resolve_then_validate_without_fix_reopens_clarification(seed, creator_id):
    detail = _create_ru_only(int(seed["unit_id"]), creator_id)
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        detail = svc.run_intake_validation(workspace_id=workspace_id, actor_user_id=creator_id)
        clar_id = next(c["clarification_id"] for c in detail["clarifications"] if c["code"] == "OI010")
        svc.resolve_clarification(
            workspace_id=workspace_id,
            clarification_id=int(clar_id),
            actor_user_id=creator_id,
            resolution_note="temporary",
        )
        detail = svc.run_intake_validation(workspace_id=workspace_id, actor_user_id=creator_id)
        with engine.connect() as conn:
            open_rows = _open_clarifications(conn, workspace_id, "OI010")
            resolved_count = conn.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM public.operational_order_clarifications
                    WHERE workspace_id = :workspace_id
                      AND code = 'OI010'
                      AND status = :status
                    """
                ),
                {"workspace_id": workspace_id, "status": CLARIFICATION_STATUS_RESOLVED},
            ).scalar()
        assert len(open_rows) == 1
        assert int(resolved_count or 0) >= 1
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)


def test_add_kk_locale_then_validate_closes_missing_kk_path(seed, creator_id):
    detail = _create_ru_only(int(seed["unit_id"]), creator_id)
    workspace_id = detail["workspace"]["workspace_id"]
    try:
        svc.run_intake_validation(workspace_id=workspace_id, actor_user_id=creator_id)
        svc.add_draft_block(
            workspace_id=workspace_id,
            locale="kk",
            block_type="TITLE",
            submitted_text="KK title",
            source_type="SUBMITTED",
            sequence=1,
            actor_user_id=creator_id,
        )
        detail = svc.run_intake_validation(workspace_id=workspace_id, actor_user_id=creator_id)
        with engine.connect() as conn:
            open_rows = _open_clarifications(conn, workspace_id, "OI010")
            dismissed_count = conn.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM public.operational_order_clarifications
                    WHERE workspace_id = :workspace_id
                      AND code = 'OI010'
                      AND status = 'DISMISSED'
                    """
                ),
                {"workspace_id": workspace_id},
            ).scalar()
        assert open_rows == []
        assert int(dismissed_count or 0) >= 1
        assert not any(issue.code == "OI010" for issue in detail["validation"].issues)
    finally:
        with engine.begin() as conn:
            cleanup_workspace(conn, workspace_id)
