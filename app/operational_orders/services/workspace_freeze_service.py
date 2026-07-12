"""Workspace freeze side effects after promotion (OO-IMP-003B)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.db.models.operational_orders import (
    AUDIT_ACTION_WORKSPACE_FROZEN,
    AUDIT_ACTION_WORKSPACE_STAGE_CHANGED,
    PROVENANCE_ACTION_WORKSPACE_FROZEN,
    PROVENANCE_ACTION_WORKSPACE_PROMOTED,
    WORKSPACE_STAGE_DOCUMENT_PROMOTED,
)
from app.operational_orders.services import draft_intake_service as intake_svc


def freeze_workspace(
    conn,
    *,
    workspace_id: int,
    actor_user_id: int,
    document_id: int,
    promotion_id: int,
    representative_block_id: int,
    representative_locale: str,
    representative_text: str,
    previous_stage: str,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.operational_order_draft_workspaces
            SET stage = :stage, updated_at = now()
            WHERE workspace_id = :workspace_id
            """
        ),
        {
            "workspace_id": int(workspace_id),
            "stage": WORKSPACE_STAGE_DOCUMENT_PROMOTED,
        },
    )
    intake_svc._append_audit(
        conn,
        workspace_id=workspace_id,
        action=AUDIT_ACTION_WORKSPACE_STAGE_CHANGED,
        actor_user_id=actor_user_id,
        metadata={"from_stage": previous_stage, "to_stage": WORKSPACE_STAGE_DOCUMENT_PROMOTED},
    )
    intake_svc._append_audit(
        conn,
        workspace_id=workspace_id,
        action=AUDIT_ACTION_WORKSPACE_FROZEN,
        actor_user_id=actor_user_id,
        metadata={"document_id": document_id, "promotion_id": promotion_id},
    )
    for action in (PROVENANCE_ACTION_WORKSPACE_PROMOTED, PROVENANCE_ACTION_WORKSPACE_FROZEN):
        intake_svc._append_provenance(
            conn,
            workspace_id=workspace_id,
            draft_block_id=int(representative_block_id),
            locale=str(representative_locale),
            source_type="GENERATED",
            source_actor_type="PERSON",
            source_actor_reference=str(actor_user_id),
            source_org_unit_id=None,
            source_language=str(representative_locale),
            action=action,
            submitted_or_effective_text=str(representative_text),
            metadata={"document_id": document_id, "promotion_id": promotion_id},
        )


def ensure_workspace_frozen_if_promoted(
    conn,
    *,
    workspace: dict[str, Any],
    actor_user_id: int | None = None,
) -> None:
    """Repair path: document exists but stage was not frozen (pre-003B data)."""
    from app.operational_orders.workspace_freeze import is_workspace_frozen

    if is_workspace_frozen(workspace):
        return
    workspace_id = int(workspace["workspace_id"])
    row = conn.execute(
        text(
            """
            SELECT d.id AS document_id, d.promotion_id, p.workspace_fingerprint
            FROM public.operational_order_documents d
            JOIN public.operational_order_promotions p ON p.id = d.promotion_id
            WHERE d.workspace_id = :workspace_id
            LIMIT 1
            """
        ),
        {"workspace_id": workspace_id},
    ).mappings().first()
    if not row:
        return
    block = conn.execute(
        text(
            """
            SELECT block_id, locale, COALESCE(workspace_effective_text, submitted_text) AS text_value
            FROM public.operational_order_draft_blocks
            WHERE workspace_id = :workspace_id
            ORDER BY CASE block_type WHEN 'TITLE' THEN 0 ELSE 1 END, block_id
            LIMIT 1
            """
        ),
        {"workspace_id": workspace_id},
    ).mappings().first()
    if not block:
        return
    freeze_workspace(
        conn,
        workspace_id=workspace_id,
        actor_user_id=int(actor_user_id or workspace.get("record_creator_user_id") or 0),
        document_id=int(row["document_id"]),
        promotion_id=int(row["promotion_id"]),
        representative_block_id=int(block["block_id"]),
        representative_locale=str(block["locale"]),
        representative_text=str(block["text_value"]),
        previous_stage=str(workspace.get("stage") or ""),
    )
