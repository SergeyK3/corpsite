"""Draft intake service for Operational Orders (OO-IMP-001)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.operational_orders import (
    AUDIT_ACTION_BLOCK_ADDED,
    AUDIT_ACTION_CLARIFICATION_RESOLVED,
    AUDIT_ACTION_EFFECTIVE_TEXT_CHANGED,
    AUDIT_ACTION_PROVENANCE_ADDED,
    AUDIT_ACTION_READY_FOR_EDITORIAL,
    AUDIT_ACTION_SUBMISSION_CREATED,
    AUDIT_ACTION_VALIDATION_EXECUTED,
    AUDIT_ACTION_WORKSPACE_ACCEPTED,
    BLOCK_TYPES,
    CLARIFICATION_STATUS_OPEN,
    CLARIFICATION_STATUS_RESOLVED,
    DRAFTING_PATH_SUBMITTED_TEXT,
    LOCALE_KK,
    LOCALE_RU,
    LOCALES,
    PROVENANCE_ACTION_ACCEPTANCE,
    PROVENANCE_ACTION_BLOCK_ADD,
    PROVENANCE_ACTION_EFFECTIVE_EDIT,
    PROVENANCE_ACTION_SUBMISSION,
    STALENESS_CURRENT,
    STALENESS_REVIEW_REQUIRED,
    TEXT_SOURCE_OVERRIDE,
    TEXT_SOURCE_SUBMITTED,
    WORKSPACE_STAGE_ACCEPTED,
    WORKSPACE_STAGE_CLARIFICATION_REQUIRED,
    WORKSPACE_STAGE_INTAKE_REVIEW,
    WORKSPACE_STAGE_READY_FOR_EDITORIAL,
    WORKSPACE_STAGE_SUBMITTED,
    WORKSPACE_STAGE_TRANSLATION_IN_PROGRESS,
    WORKSPACE_STAGE_TRANSLATION_REQUIRED,
    WORKSPACE_STAGE_CONTENT_CONFIRMATION_REQUIRED,
    WORKSPACE_STAGE_BILINGUAL_RECONCILIATION,
    WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY,
)
from app.document_engine import DraftingPath, DocumentKind, TextSourceType
from app.operational_orders.domain import (
    content_fingerprint,
    json_safe,
    normalize_party_reference,
    normalize_text_source,
    party_to_row,
)
from app.operational_orders.errors import (
    OperationalOrderBlockNotFoundError,
    OperationalOrderClarificationNotFoundError,
    OperationalOrderForbiddenError,
    OperationalOrderInvalidWorkspaceStageError,
    OperationalOrderSubmittedTextImmutableError,
    OperationalOrderValidationBlockedError,
    OperationalOrderValidationError,
    OperationalOrderVersionConflictError,
    OperationalOrderWorkspaceNotFoundError,
)
from app.operational_orders.repository import (
    dumps_json,
    fetch_workspace_row,
    operational_orders_available,
)
from app.operational_orders.validation.intake_validation import validate_intake_workspace

ACTIVE_INTAKE_STAGES = {
    WORKSPACE_STAGE_SUBMITTED,
    WORKSPACE_STAGE_ACCEPTED,
    WORKSPACE_STAGE_INTAKE_REVIEW,
    WORKSPACE_STAGE_CLARIFICATION_REQUIRED,
}


def _require_available() -> None:
    if not operational_orders_available():
        raise OperationalOrderValidationError("Operational orders intake schema is not available.")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _append_audit(
    conn,
    *,
    workspace_id: int,
    action: str,
    actor_user_id: int | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.operational_order_draft_audit (
                workspace_id, action, actor_user_id, metadata_json
            ) VALUES (
                :workspace_id, :action, :actor_user_id, CAST(:metadata_json AS jsonb)
            )
            """
        ),
        {
            "workspace_id": int(workspace_id),
            "action": action,
            "actor_user_id": actor_user_id,
            "metadata_json": json.dumps(json_safe(metadata) or {}),
        },
    )


def _append_provenance(
    conn,
    *,
    workspace_id: int,
    draft_block_id: int,
    locale: str,
    source_type: str,
    source_actor_type: str,
    source_actor_reference: str,
    source_org_unit_id: int | None,
    source_language: str | None,
    action: str,
    submitted_or_effective_text: str,
    derived_from_provenance_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    row = conn.execute(
        text(
            """
            INSERT INTO public.operational_order_text_provenance (
                workspace_id,
                draft_block_id,
                locale,
                source_type,
                source_actor_type,
                source_actor_reference,
                source_org_unit_id,
                source_language,
                derived_from_provenance_id,
                action,
                content_fingerprint,
                metadata_json
            ) VALUES (
                :workspace_id,
                :draft_block_id,
                :locale,
                :source_type,
                :source_actor_type,
                :source_actor_reference,
                :source_org_unit_id,
                :source_language,
                :derived_from_provenance_id,
                :action,
                :content_fingerprint,
                CAST(:metadata_json AS jsonb)
            )
            RETURNING provenance_id
            """
        ),
        {
            "workspace_id": int(workspace_id),
            "draft_block_id": int(draft_block_id),
            "locale": locale,
            "source_type": source_type,
            "source_actor_type": source_actor_type,
            "source_actor_reference": source_actor_reference,
            "source_org_unit_id": source_org_unit_id,
            "source_language": source_language,
            "derived_from_provenance_id": derived_from_provenance_id,
            "action": action,
            "content_fingerprint": content_fingerprint(submitted_or_effective_text),
            "metadata_json": json.dumps(json_safe(metadata) or {}),
        },
    ).fetchone()
    return int(row[0])


def _fetch_blocks(conn, workspace_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_draft_blocks
            WHERE workspace_id = :workspace_id
            ORDER BY locale, block_type, sequence, block_id
            """
        ),
        {"workspace_id": int(workspace_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def _fetch_clarifications(conn, workspace_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_clarifications
            WHERE workspace_id = :workspace_id
            ORDER BY clarification_id
            """
        ),
        {"workspace_id": int(workspace_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def _fetch_provenance(conn, workspace_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_text_provenance
            WHERE workspace_id = :workspace_id
            ORDER BY provenance_id
            """
        ),
        {"workspace_id": int(workspace_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def _fetch_audit(conn, workspace_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_draft_audit
            WHERE workspace_id = :workspace_id
            ORDER BY audit_id
            """
        ),
        {"workspace_id": int(workspace_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def _normalize_locale(locale: str) -> str:
    normalized = str(locale or "").strip().lower()
    if normalized not in LOCALES:
        raise OperationalOrderValidationError(f"Invalid locale: {locale}")
    return normalized


def _normalize_block_type(block_type: str) -> str:
    normalized = str(block_type or "").strip().upper()
    if normalized not in BLOCK_TYPES:
        raise OperationalOrderValidationError(f"Invalid block_type: {block_type}")
    return normalized


def _build_detail(conn, workspace_id: int) -> dict[str, Any]:
    workspace = fetch_workspace_row(conn, workspace_id)
    if not workspace:
        raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
    blocks = _fetch_blocks(conn, workspace_id)
    clarifications = _fetch_clarifications(conn, workspace_id)
    provenance = _fetch_provenance(conn, workspace_id)
    audit = _fetch_audit(conn, workspace_id)
    validation = validate_intake_workspace(
        workspace=workspace,
        blocks=blocks,
        clarifications=clarifications,
        provenance_count=len(provenance),
    )
    locales_present = sorted({str(b["locale"]) for b in blocks})
    from app.operational_orders.services import editorial_workflow_service as editorial_svc

    editorial = editorial_svc.fetch_editorial_entities(conn, workspace_id)
    return {
        "workspace": workspace,
        "blocks": blocks,
        "provenance": provenance,
        "clarifications": clarifications,
        "audit": audit,
        "validation": validation,
        "locale_completeness": {
            "ru_present": LOCALE_RU in locales_present,
            "kk_present": LOCALE_KK in locales_present,
            "locales_present": locales_present,
        },
        "readiness_for_editorial": workspace.get("stage") == WORKSPACE_STAGE_READY_FOR_EDITORIAL,
        "readiness_for_editorial_package": workspace.get("stage") == "EDITORIAL_PACKAGE_READY",
        **editorial,
    }


def _assert_version(workspace: dict[str, Any], expected_version: int | None) -> None:
    if expected_version is None:
        return
    current = int(workspace.get("version") or 0)
    if current != int(expected_version):
        raise OperationalOrderVersionConflictError(
            f"Workspace version conflict: expected {expected_version}, got {current}."
        )


def _resolve_organization_id(*, submitting_org_unit_id: int, organization_id: int | None) -> int:
    if organization_id is not None:
        return int(organization_id)
    return int(submitting_org_unit_id)


def create_submission(
    *,
    initiator_type: str,
    initiator_reference: str,
    initiator_display_name: str | None,
    content_author_type: str,
    content_author_reference: str,
    content_author_display_name: str | None,
    submitting_org_unit_id: int,
    record_creator_user_id: int,
    blocks: Sequence[dict[str, Any]],
    organization_id: int | None = None,
    proposed_title: str | None = None,
    proposed_signer_type: str | None = None,
    proposed_signer_reference: str | None = None,
    proposed_signer_display_name: str | None = None,
    source_language: str | None = None,
    required_locales: Sequence[str] | None = None,
    document_operator_user_id: int | None = None,
) -> dict[str, Any]:
    _require_available()
    if not blocks:
        raise OperationalOrderValidationError("At least one text block is required.")

    initiator = normalize_party_reference(
        reference_type=initiator_type,
        reference=initiator_reference,
        display_name=initiator_display_name,
    )
    content_author = normalize_party_reference(
        reference_type=content_author_type,
        reference=content_author_reference,
        display_name=content_author_display_name,
    )
    if (
        content_author.reference == str(record_creator_user_id)
        and content_author.reference_type.value == "PERSON"
        and initiator.reference == content_author.reference
        and initiator.reference_type.value == "PERSON"
    ):
        pass

    org_id = _resolve_organization_id(
        submitting_org_unit_id=int(submitting_org_unit_id),
        organization_id=organization_id,
    )
    locales_required = list(required_locales or [LOCALE_RU, LOCALE_KK])

    with engine.begin() as conn:
        workspace_row = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_draft_workspaces (
                    organization_id,
                    drafting_path,
                    stage,
                    initiator_type,
                    initiator_reference,
                    initiator_display_name,
                    content_author_type,
                    content_author_reference,
                    content_author_display_name,
                    submitting_org_unit_id,
                    record_creator_user_id,
                    document_operator_user_id,
                    intended_document_kind,
                    proposed_title,
                    proposed_signer_type,
                    proposed_signer_reference,
                    proposed_signer_display_name,
                    source_language,
                    required_locales
                ) VALUES (
                    :organization_id,
                    :drafting_path,
                    :stage,
                    :initiator_type,
                    :initiator_reference,
                    :initiator_display_name,
                    :content_author_type,
                    :content_author_reference,
                    :content_author_display_name,
                    :submitting_org_unit_id,
                    :record_creator_user_id,
                    :document_operator_user_id,
                    :intended_document_kind,
                    :proposed_title,
                    :proposed_signer_type,
                    :proposed_signer_reference,
                    :proposed_signer_display_name,
                    :source_language,
                    CAST(:required_locales AS jsonb)
                )
                RETURNING workspace_id
                """
            ),
            {
                "organization_id": org_id,
                "drafting_path": DraftingPath.SUBMITTED_TEXT.value,
                "stage": WORKSPACE_STAGE_SUBMITTED,
                "initiator_type": party_to_row(initiator)["reference_type"],
                "initiator_reference": initiator.reference,
                "initiator_display_name": initiator.display_name,
                "content_author_type": party_to_row(content_author)["reference_type"],
                "content_author_reference": content_author.reference,
                "content_author_display_name": content_author.display_name,
                "submitting_org_unit_id": int(submitting_org_unit_id),
                "record_creator_user_id": int(record_creator_user_id),
                "document_operator_user_id": document_operator_user_id,
                "intended_document_kind": DocumentKind.OPERATIONAL_ORDER.value,
                "proposed_title": proposed_title,
                "proposed_signer_type": proposed_signer_type,
                "proposed_signer_reference": proposed_signer_reference,
                "proposed_signer_display_name": proposed_signer_display_name,
                "source_language": _normalize_locale(source_language) if source_language else None,
                "required_locales": dumps_json(locales_required),
            },
        ).fetchone()
        workspace_id = int(workspace_row[0])

        for block in blocks:
            locale = _normalize_locale(str(block["locale"]))
            block_type = _normalize_block_type(str(block["block_type"]))
            submitted_text = str(block["submitted_text"]).strip()
            if not submitted_text:
                raise OperationalOrderValidationError("Submitted text must not be empty.")
            source_type = normalize_text_source(str(block.get("source_type") or TextSourceType.SUBMITTED.value))
            sequence = int(block.get("sequence") or 1)

            block_row = conn.execute(
                text(
                    """
                    INSERT INTO public.operational_order_draft_blocks (
                        workspace_id,
                        locale,
                        block_type,
                        submitted_text,
                        sequence,
                        source_type
                    ) VALUES (
                        :workspace_id,
                        :locale,
                        :block_type,
                        :submitted_text,
                        :sequence,
                        :source_type
                    )
                    RETURNING block_id
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "locale": locale,
                    "block_type": block_type,
                    "submitted_text": submitted_text,
                    "sequence": sequence,
                    "source_type": source_type,
                },
            ).fetchone()
            block_id = int(block_row[0])

            provenance_id = _append_provenance(
                conn,
                workspace_id=workspace_id,
                draft_block_id=block_id,
                locale=locale,
                source_type=source_type,
                source_actor_type=content_author.reference_type.value,
                source_actor_reference=content_author.reference,
                source_org_unit_id=int(submitting_org_unit_id),
                source_language=locale,
                action=PROVENANCE_ACTION_SUBMISSION,
                submitted_or_effective_text=submitted_text,
                metadata={"block_type": block_type, "sequence": sequence},
            )
            _append_audit(
                conn,
                workspace_id=workspace_id,
                action=AUDIT_ACTION_PROVENANCE_ADDED,
                actor_user_id=int(record_creator_user_id),
                metadata={"provenance_id": provenance_id, "block_id": block_id},
            )
            _append_audit(
                conn,
                workspace_id=workspace_id,
                action=AUDIT_ACTION_BLOCK_ADDED,
                actor_user_id=int(record_creator_user_id),
                metadata={"block_id": block_id},
            )

        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_SUBMISSION_CREATED,
            actor_user_id=int(record_creator_user_id),
            metadata={"drafting_path": DRAFTING_PATH_SUBMITTED_TEXT},
        )

        return _build_detail(conn, workspace_id)


def accept_submission(
    *,
    workspace_id: int,
    actor_user_id: int,
    expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        workspace = fetch_workspace_row(conn, workspace_id)
        if not workspace:
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
        _assert_version(workspace, expected_version)
        if workspace["stage"] != WORKSPACE_STAGE_SUBMITTED:
            raise OperationalOrderInvalidWorkspaceStageError(
                f"Workspace must be in SUBMITTED stage, got {workspace['stage']}."
            )

        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_draft_workspaces
                SET stage = :stage,
                    accepted_at = :accepted_at,
                    version = version + 1,
                    updated_at = :updated_at
                WHERE workspace_id = :workspace_id
                  AND version = :expected_version
                RETURNING workspace_id
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "stage": WORKSPACE_STAGE_ACCEPTED,
                "accepted_at": _utcnow(),
                "updated_at": _utcnow(),
                "expected_version": int(workspace["version"]),
            },
        ).fetchone()
        if not updated:
            raise OperationalOrderVersionConflictError("Workspace version conflict during acceptance.")

        blocks = _fetch_blocks(conn, workspace_id)
        for block in blocks:
            _append_provenance(
                conn,
                workspace_id=workspace_id,
                draft_block_id=int(block["block_id"]),
                locale=str(block["locale"]),
                source_type=str(block["source_type"]),
                source_actor_type=str(workspace["content_author_type"]),
                source_actor_reference=str(workspace["content_author_reference"]),
                source_org_unit_id=int(workspace["submitting_org_unit_id"]),
                source_language=str(block["locale"]),
                action=PROVENANCE_ACTION_ACCEPTANCE,
                submitted_or_effective_text=str(block["submitted_text"]),
            )

        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_WORKSPACE_ACCEPTED,
            actor_user_id=int(actor_user_id),
        )
        return _build_detail(conn, workspace_id)


def get_workspace(*, workspace_id: int) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        return _build_detail(conn, workspace_id)


def list_workspaces(
    *,
    stage: str | None = None,
    submitting_org_unit_id: int | None = None,
    record_creator_user_id: int | None = None,
    scope_unit_ids: list[int] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    _require_available()
    clauses = ["stage = ANY(:active_stages)"]
    params: dict[str, Any] = {
        "active_stages": list(ACTIVE_INTAKE_STAGES),
        "limit": max(1, min(int(limit), 200)),
        "offset": max(0, int(offset)),
    }
    if stage:
        clauses = ["stage = :stage"]
        params["stage"] = str(stage).strip().upper()
    if submitting_org_unit_id is not None:
        clauses.append("submitting_org_unit_id = :submitting_org_unit_id")
        params["submitting_org_unit_id"] = int(submitting_org_unit_id)
    if record_creator_user_id is not None:
        clauses.append("record_creator_user_id = :record_creator_user_id")
        params["record_creator_user_id"] = int(record_creator_user_id)
    if scope_unit_ids is not None:
        if not scope_unit_ids:
            return {"items": [], "total": 0, "limit": params["limit"], "offset": params["offset"]}
        clauses.append("submitting_org_unit_id = ANY(:scope_unit_ids)")
        params["scope_unit_ids"] = [int(unit_id) for unit_id in scope_unit_ids]

    where_sql = " AND ".join(clauses)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT
                    w.*,
                    EXISTS (
                        SELECT 1 FROM public.operational_order_draft_blocks b
                        WHERE b.workspace_id = w.workspace_id AND b.locale = 'ru'
                    ) AS ru_present,
                    EXISTS (
                        SELECT 1 FROM public.operational_order_draft_blocks b
                        WHERE b.workspace_id = w.workspace_id AND b.locale = 'kk'
                    ) AS kk_present
                FROM public.operational_order_draft_workspaces w
                WHERE {where_sql}
                ORDER BY w.created_at DESC, w.workspace_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()
        total = conn.execute(
            text(
                f"""
                SELECT COUNT(1)
                FROM public.operational_order_draft_workspaces w
                WHERE {where_sql}
                """
            ),
            params,
        ).scalar()
    return {"items": [dict(row) for row in rows], "total": int(total or 0), "limit": params["limit"], "offset": params["offset"]}


def add_draft_block(
    *,
    workspace_id: int,
    locale: str,
    block_type: str,
    submitted_text: str,
    source_type: str,
    sequence: int,
    actor_user_id: int,
    expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    locale_norm = _normalize_locale(locale)
    block_type_norm = _normalize_block_type(block_type)
    submitted = str(submitted_text).strip()
    if not submitted:
        raise OperationalOrderValidationError("Submitted text must not be empty.")
    source_type_norm = normalize_text_source(source_type)

    with engine.begin() as conn:
        workspace = fetch_workspace_row(conn, workspace_id)
        if not workspace:
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
        _assert_version(workspace, expected_version)
        if workspace["stage"] == WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY:
            raise OperationalOrderInvalidWorkspaceStageError(
                "Cannot add blocks after EDITORIAL_PACKAGE_READY."
            )

        block_row = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_draft_blocks (
                    workspace_id, locale, block_type, submitted_text, sequence, source_type
                ) VALUES (
                    :workspace_id, :locale, :block_type, :submitted_text, :sequence, :source_type
                )
                RETURNING block_id
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "locale": locale_norm,
                "block_type": block_type_norm,
                "submitted_text": submitted,
                "sequence": int(sequence),
                "source_type": source_type_norm,
            },
        ).fetchone()
        block_id = int(block_row[0])

        conn.execute(
            text(
                """
                UPDATE public.operational_order_draft_workspaces
                SET version = version + 1, updated_at = :updated_at
                WHERE workspace_id = :workspace_id
                """
            ),
            {"workspace_id": int(workspace_id), "updated_at": _utcnow()},
        )

        _append_provenance(
            conn,
            workspace_id=workspace_id,
            draft_block_id=block_id,
            locale=locale_norm,
            source_type=source_type_norm,
            source_actor_type=str(workspace["content_author_type"]),
            source_actor_reference=str(workspace["content_author_reference"]),
            source_org_unit_id=int(workspace["submitting_org_unit_id"]),
            source_language=locale_norm,
            action=PROVENANCE_ACTION_BLOCK_ADD,
            submitted_or_effective_text=submitted,
        )
        _append_audit(conn, workspace_id=workspace_id, action=AUDIT_ACTION_BLOCK_ADDED, actor_user_id=actor_user_id)
        return _build_detail(conn, workspace_id)


def update_workspace_effective_text(
    *,
    workspace_id: int,
    block_id: int,
    workspace_effective_text: str,
    actor_user_id: int,
    expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    effective = str(workspace_effective_text)
    with engine.begin() as conn:
        workspace = fetch_workspace_row(conn, workspace_id)
        if not workspace:
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
        _assert_version(workspace, expected_version)

        block = conn.execute(
            text(
                """
                SELECT *
                FROM public.operational_order_draft_blocks
                WHERE workspace_id = :workspace_id AND block_id = :block_id
                """
            ),
            {"workspace_id": int(workspace_id), "block_id": int(block_id)},
        ).mappings().first()
        if not block:
            raise OperationalOrderBlockNotFoundError(f"Block {block_id} not found.")
        block_dict = dict(block)

        conn.execute(
            text(
                """
                UPDATE public.operational_order_draft_blocks
                SET workspace_effective_text = :workspace_effective_text,
                    review_state = :review_state,
                    version = version + 1,
                    updated_at = :updated_at
                WHERE block_id = :block_id
                """
            ),
            {
                "block_id": int(block_id),
                "workspace_effective_text": effective,
                "review_state": STALENESS_CURRENT,
                "updated_at": _utcnow(),
            },
        )

        if str(block_dict["locale"]) == LOCALE_RU:
            conn.execute(
                text(
                    """
                    UPDATE public.operational_order_draft_blocks
                    SET review_state = :review_state,
                        updated_at = :updated_at
                    WHERE workspace_id = :workspace_id
                      AND locale = :kk_locale
                      AND block_id <> :block_id
                    """
                ),
                {
                    "workspace_id": int(workspace_id),
                    "kk_locale": LOCALE_KK,
                    "block_id": int(block_id),
                    "review_state": STALENESS_REVIEW_REQUIRED,
                    "updated_at": _utcnow(),
                },
            )

        conn.execute(
            text(
                """
                UPDATE public.operational_order_draft_workspaces
                SET version = version + 1,
                    stage = CASE
                        WHEN stage = :ready_stage THEN :intake_review_stage
                        ELSE stage
                    END,
                    updated_at = :updated_at
                WHERE workspace_id = :workspace_id
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "updated_at": _utcnow(),
                "ready_stage": WORKSPACE_STAGE_READY_FOR_EDITORIAL,
                "intake_review_stage": WORKSPACE_STAGE_INTAKE_REVIEW,
            },
        )

        _append_provenance(
            conn,
            workspace_id=workspace_id,
            draft_block_id=int(block_id),
            locale=str(block_dict["locale"]),
            source_type=TEXT_SOURCE_OVERRIDE,
            source_actor_type="PERSON",
            source_actor_reference=str(actor_user_id),
            source_org_unit_id=int(workspace["submitting_org_unit_id"]),
            source_language=str(block_dict["locale"]),
            action=PROVENANCE_ACTION_EFFECTIVE_EDIT,
            submitted_or_effective_text=effective,
            metadata={"previous_submitted_text_hash": content_fingerprint(str(block_dict["submitted_text"]))},
        )
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_EFFECTIVE_TEXT_CHANGED,
            actor_user_id=actor_user_id,
            metadata={"block_id": int(block_id)},
        )
        from app.operational_orders.services import editorial_workflow_service as editorial_svc

        editorial_svc.on_block_text_changed(
            conn,
            workspace_id=workspace_id,
            block_id=int(block_id),
            locale=str(block_dict["locale"]),
            actor_user_id=actor_user_id,
        )
        return _build_detail(conn, workspace_id)


def guard_submitted_text_immutable(*, current_submitted_text: str, new_submitted_text: str) -> None:
    if str(current_submitted_text) != str(new_submitted_text):
        raise OperationalOrderSubmittedTextImmutableError("Submitted text is immutable.")


def run_intake_validation(
    *,
    workspace_id: int,
    actor_user_id: int,
    expected_version: int | None = None,
    for_ready_for_editorial: bool = False,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        workspace = fetch_workspace_row(conn, workspace_id)
        if not workspace:
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
        _assert_version(workspace, expected_version)
        blocks = _fetch_blocks(conn, workspace_id)
        clarifications = _fetch_clarifications(conn, workspace_id)
        provenance = _fetch_provenance(conn, workspace_id)
        validation = validate_intake_workspace(
            workspace=workspace,
            blocks=blocks,
            clarifications=clarifications,
            provenance_count=len(provenance),
            for_ready_for_editorial=for_ready_for_editorial,
        )

        if validation.has_errors and any(
            issue.code in {"OI009", "OI010"} and issue.severity.value == "WARNING"
            for issue in validation.issues
        ):
            pass

        open_clarification_codes = {
            issue.code
            for issue in validation.issues
            if issue.code in {"OI009", "OI010"} and issue.severity.value == "WARNING"
        }
        for issue in validation.issues:
            if issue.code in {"OI009", "OI010"} and issue.severity.value == "WARNING":
                conn.execute(
                    text(
                        """
                        INSERT INTO public.operational_order_clarifications (
                            workspace_id, code, severity, category, message, field_path, requested_by
                        )
                        SELECT
                            :workspace_id, :code, 'WARNING', 'Localization', :message, :field_path, :requested_by
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM public.operational_order_clarifications c
                            WHERE c.workspace_id = :workspace_id
                              AND c.code = :code
                              AND c.status = 'OPEN'
                              AND c.field_path IS NOT DISTINCT FROM :field_path
                        )
                        """
                    ),
                    {
                        "workspace_id": int(workspace_id),
                        "code": issue.code,
                        "message": issue.message,
                        "field_path": issue.field_path,
                        "requested_by": int(actor_user_id),
                    },
                )

        for stale_code in {"OI009", "OI010"} - open_clarification_codes:
            conn.execute(
                text(
                    """
                    UPDATE public.operational_order_clarifications
                    SET status = 'DISMISSED',
                        resolved_by = :resolved_by,
                        resolution_note = :resolution_note,
                        resolved_at = :resolved_at
                    WHERE workspace_id = :workspace_id
                      AND code = :code
                      AND status = 'OPEN'
                    """
                ),
                {
                    "workspace_id": int(workspace_id),
                    "code": stale_code,
                    "resolved_by": int(actor_user_id),
                    "resolution_note": "Auto-dismissed: validation issue no longer present.",
                    "resolved_at": _utcnow(),
                },
            )

        stage = workspace["stage"]
        if validation.has_errors:
            stage = WORKSPACE_STAGE_CLARIFICATION_REQUIRED
        elif open_clarification_codes or any(
            c.get("status") == CLARIFICATION_STATUS_OPEN for c in clarifications
        ):
            stage = WORKSPACE_STAGE_CLARIFICATION_REQUIRED
        elif workspace["stage"] in {WORKSPACE_STAGE_SUBMITTED, WORKSPACE_STAGE_ACCEPTED}:
            stage = WORKSPACE_STAGE_INTAKE_REVIEW

        conn.execute(
            text(
                """
                UPDATE public.operational_order_draft_workspaces
                SET stage = :stage,
                    version = version + 1,
                    updated_at = :updated_at
                WHERE workspace_id = :workspace_id
                """
            ),
            {"workspace_id": int(workspace_id), "stage": stage, "updated_at": _utcnow()},
        )
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_VALIDATION_EXECUTED,
            actor_user_id=actor_user_id,
            metadata={"issue_count": len(validation.issues), "has_errors": validation.has_errors},
        )
        detail = _build_detail(conn, workspace_id)
        detail["validation"] = validation
        return detail


def resolve_clarification(
    *,
    workspace_id: int,
    clarification_id: int,
    actor_user_id: int,
    resolution_note: str | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        workspace = fetch_workspace_row(conn, workspace_id)
        if not workspace:
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
        _assert_version(workspace, expected_version)

        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_clarifications
                SET status = :status,
                    resolved_by = :resolved_by,
                    resolution_note = :resolution_note,
                    resolved_at = :resolved_at
                WHERE clarification_id = :clarification_id
                  AND workspace_id = :workspace_id
                  AND status = 'OPEN'
                RETURNING clarification_id
                """
            ),
            {
                "clarification_id": int(clarification_id),
                "workspace_id": int(workspace_id),
                "status": CLARIFICATION_STATUS_RESOLVED,
                "resolved_by": int(actor_user_id),
                "resolution_note": resolution_note,
                "resolved_at": _utcnow(),
            },
        ).fetchone()
        if not updated:
            raise OperationalOrderClarificationNotFoundError(
                f"Clarification {clarification_id} not found in workspace {workspace_id}."
            )

        conn.execute(
            text(
                """
                UPDATE public.operational_order_draft_workspaces
                SET version = version + 1, updated_at = :updated_at
                WHERE workspace_id = :workspace_id
                """
            ),
            {"workspace_id": int(workspace_id), "updated_at": _utcnow()},
        )
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_CLARIFICATION_RESOLVED,
            actor_user_id=actor_user_id,
            metadata={"clarification_id": int(clarification_id)},
        )
        return _build_detail(conn, workspace_id)


def mark_ready_for_editorial(
    *,
    workspace_id: int,
    actor_user_id: int,
    expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        workspace = fetch_workspace_row(conn, workspace_id)
        if not workspace:
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
        _assert_version(workspace, expected_version)
        blocks = _fetch_blocks(conn, workspace_id)
        clarifications = _fetch_clarifications(conn, workspace_id)
        provenance = _fetch_provenance(conn, workspace_id)
        validation = validate_intake_workspace(
            workspace=workspace,
            blocks=blocks,
            clarifications=clarifications,
            provenance_count=len(provenance),
            for_ready_for_editorial=True,
        )
        if not validation.is_valid:
            raise OperationalOrderValidationBlockedError(
                "Workspace cannot be marked ready for editorial while validation errors remain."
            )

        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_draft_workspaces
                SET stage = :stage,
                    version = version + 1,
                    updated_at = :updated_at
                WHERE workspace_id = :workspace_id
                  AND version = :expected_version
                RETURNING workspace_id
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "stage": WORKSPACE_STAGE_READY_FOR_EDITORIAL,
                "updated_at": _utcnow(),
                "expected_version": int(workspace["version"]),
            },
        ).fetchone()
        if not updated:
            raise OperationalOrderVersionConflictError("Workspace version conflict.")

        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_READY_FOR_EDITORIAL,
            actor_user_id=actor_user_id,
        )
        detail = _build_detail(conn, workspace_id)
        detail["validation"] = validation
        return detail
