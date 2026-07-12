"""Editorial workflow service for Operational Orders (OO-IMP-002)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.operational_orders import (
    ASSIGNMENT_ACTIVE_STATUSES,
    ASSIGNMENT_STATUS_ACCEPTED,
    ASSIGNMENT_STATUS_CANCELLED,
    ASSIGNMENT_STATUS_COMPLETED,
    ASSIGNMENT_STATUS_IN_PROGRESS,
    ASSIGNMENT_STATUS_REQUESTED,
    ASSIGNMENT_STATUS_SUPERSEDED,
    AUDIT_ACTION_ASSIGNMENT_ACCEPTED,
    AUDIT_ACTION_CONFIRMATION_CREATED,
    AUDIT_ACTION_CONFIRMATION_REVOKED,
    AUDIT_ACTION_CONFIRMATION_SUPERSEDED,
    AUDIT_ACTION_EDITORIAL_PACKAGE_READY,
    AUDIT_ACTION_EDITORIAL_PACKAGE_VALIDATION_FAILED,
    AUDIT_ACTION_RECONCILIATION_CREATED,
    AUDIT_ACTION_RECONCILIATION_INVALIDATED,
    AUDIT_ACTION_TRANSLATION_COMPLETED,
    AUDIT_ACTION_TRANSLATION_REQUESTED,
    AUDIT_ACTION_TRANSLATION_STARTED,
    AUDIT_ACTION_TRANSLATOR_ASSIGNED,
    AUDIT_ACTION_WORKSPACE_STAGE_CHANGED,
    CONFIRMATION_ROLE_CONTENT_AUTHOR,
    CONFIRMATION_ROLE_DOCUMENT_OPERATOR,
    CONFIRMATION_ROLE_TRANSLATOR,
    CONFIRMATION_STATUS_CONFIRMED,
    CONFIRMATION_STATUS_REVOKED,
    CONFIRMATION_STATUS_SUPERSEDED,
    LOCALE_KK,
    LOCALE_RU,
    LOCALES,
    PROVENANCE_ACTION_TRANSLATION,
    RECONCILIATION_STATUS_INVALIDATED,
    RECONCILIATION_STATUS_RECONCILED,
    RECONCILIATION_STATUS_SUPERSEDED,
    TEXT_SOURCE_IMPORTED,
    WORKSPACE_STAGE_BILINGUAL_RECONCILIATION,
    WORKSPACE_STAGE_CONTENT_CONFIRMATION_REQUIRED,
    WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY,
    WORKSPACE_STAGE_READY_FOR_EDITORIAL,
    WORKSPACE_STAGE_TRANSLATION_IN_PROGRESS,
    WORKSPACE_STAGE_TRANSLATION_REQUIRED,
)
from app.document_engine import ValidationResult
from app.operational_orders.domain import content_fingerprint, json_safe, normalize_party_reference, party_to_row
from app.operational_orders.errors import (
    OperationalOrderConfirmationConflictError,
    OperationalOrderConfirmationNotFoundError,
    OperationalOrderConfirmationPartyMismatchError,
    OperationalOrderConfirmationStaleTextError,
    OperationalOrderEditorialPackageNotReadyError,
    OperationalOrderInvalidWorkspaceStageError,
    OperationalOrderReconciliationNotFoundError,
    OperationalOrderReconciliationStaleError,
    OperationalOrderTranslationAssignmentConflictError,
    OperationalOrderTranslationAssignmentNotFoundError,
    OperationalOrderTranslationSourceStaleError,
    OperationalOrderValidationError,
    OperationalOrderVersionConflictError,
    OperationalOrderWorkspaceNotFoundError,
)
from app.operational_orders.repository import fetch_workspace_row, operational_orders_available
from app.operational_orders.services import draft_intake_service as intake_svc
from app.operational_orders.workspace_freeze import assert_workspace_not_frozen
from app.operational_orders.validation.editorial_validation import (
    block_effective_text,
    block_pair_key,
    locale_present,
    matched_block_pairs,
    required_roles_for_block,
    validate_editorial_package,
)

EDITORIAL_ENTRY_STAGES = {
    WORKSPACE_STAGE_READY_FOR_EDITORIAL,
    WORKSPACE_STAGE_TRANSLATION_REQUIRED,
    WORKSPACE_STAGE_TRANSLATION_IN_PROGRESS,
    WORKSPACE_STAGE_CONTENT_CONFIRMATION_REQUIRED,
    WORKSPACE_STAGE_BILINGUAL_RECONCILIATION,
    WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY,
}


def _require_available() -> None:
    if not operational_orders_available():
        raise OperationalOrderValidationError("Operational orders schema is not available.")


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
    intake_svc._append_audit(
        conn,
        workspace_id=workspace_id,
        action=action,
        actor_user_id=actor_user_id,
        metadata=metadata,
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
    action: str,
    text_value: str,
    metadata: dict[str, Any] | None = None,
) -> int:
    return intake_svc._append_provenance(
        conn,
        workspace_id=workspace_id,
        draft_block_id=draft_block_id,
        locale=locale,
        source_type=source_type,
        source_actor_type=source_actor_type,
        source_actor_reference=source_actor_reference,
        source_org_unit_id=source_org_unit_id,
        source_language=locale,
        action=action,
        submitted_or_effective_text=text_value,
        metadata=metadata,
    )


def _assert_version(entity: dict[str, Any], expected_version: int | None, *, label: str = "Entity") -> None:
    if expected_version is None:
        return
    current = int(entity.get("version") or 0)
    if current != int(expected_version):
        raise OperationalOrderVersionConflictError(
            f"{label} version conflict: expected {expected_version}, got {current}."
        )


def _fetch_assignments(conn, workspace_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_translation_assignments
            WHERE workspace_id = :workspace_id
            ORDER BY id
            """
        ),
        {"workspace_id": int(workspace_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def _fetch_confirmations(conn, workspace_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_content_confirmations
            WHERE workspace_id = :workspace_id
            ORDER BY id
            """
        ),
        {"workspace_id": int(workspace_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def _fetch_reconciliations(conn, workspace_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_bilingual_reconciliations
            WHERE workspace_id = :workspace_id
            ORDER BY id
            """
        ),
        {"workspace_id": int(workspace_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def _fetch_assignment(conn, workspace_id: int, assignment_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_translation_assignments
            WHERE workspace_id = :workspace_id AND id = :assignment_id
            """
        ),
        {"workspace_id": int(workspace_id), "assignment_id": int(assignment_id)},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_confirmation(conn, workspace_id: int, confirmation_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_content_confirmations
            WHERE workspace_id = :workspace_id AND id = :confirmation_id
            """
        ),
        {"workspace_id": int(workspace_id), "confirmation_id": int(confirmation_id)},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_reconciliation(conn, workspace_id: int, reconciliation_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_bilingual_reconciliations
            WHERE workspace_id = :workspace_id AND id = :reconciliation_id
            """
        ),
        {"workspace_id": int(workspace_id), "reconciliation_id": int(reconciliation_id)},
    ).mappings().first()
    return dict(row) if row else None


def _source_and_target_locales(blocks: Sequence[dict[str, Any]]) -> tuple[str, str] | None:
    ru = locale_present(blocks, LOCALE_RU)
    kk = locale_present(blocks, LOCALE_KK)
    if ru and not kk:
        return LOCALE_RU, LOCALE_KK
    if kk and not ru:
        return LOCALE_KK, LOCALE_RU
    return None


def _primary_source_block(blocks: Sequence[dict[str, Any]], locale: str) -> dict[str, Any]:
    locale_blocks = [b for b in blocks if str(b["locale"]) == locale]
    if not locale_blocks:
        raise OperationalOrderValidationError(f"No blocks for locale {locale}.")
    for preferred in ("BODY", "TITLE"):
        matches = [b for b in locale_blocks if str(b["block_type"]) == preferred]
        if matches:
            return sorted(matches, key=lambda b: int(b["sequence"]))[0]
    return sorted(locale_blocks, key=lambda b: (str(b["block_type"]), int(b["sequence"])))[0]


def _set_workspace_stage(
    conn,
    *,
    workspace_id: int,
    stage: str,
    actor_user_id: int | None,
    previous_stage: str | None = None,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.operational_order_draft_workspaces
            SET stage = :stage, updated_at = :updated_at
            WHERE workspace_id = :workspace_id
            """
        ),
        {"workspace_id": int(workspace_id), "stage": stage, "updated_at": _utcnow()},
    )
    if previous_stage != stage:
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_WORKSPACE_STAGE_CHANGED,
            actor_user_id=actor_user_id,
            metadata={"from_stage": previous_stage, "to_stage": stage},
        )


def _derive_editorial_stage(
    *,
    blocks: Sequence[dict[str, Any]],
    assignments: Sequence[dict[str, Any]],
    confirmations: Sequence[dict[str, Any]],
) -> str:
    pair = _source_and_target_locales(blocks)
    active = [a for a in assignments if str(a["status"]) in ASSIGNMENT_ACTIVE_STATUSES]
    if pair and not locale_present(blocks, pair[1]):
        if active:
            return WORKSPACE_STAGE_TRANSLATION_IN_PROGRESS
        return WORKSPACE_STAGE_TRANSLATION_REQUIRED
    if not locale_present(blocks, LOCALE_RU) or not locale_present(blocks, LOCALE_KK):
        return WORKSPACE_STAGE_TRANSLATION_REQUIRED

    for block in blocks:
        fp = content_fingerprint(block_effective_text(block))
        for role in required_roles_for_block(locale=str(block["locale"]), assignments=assignments):
            confirmed = any(
                int(c["block_id"]) == int(block["block_id"])
                and str(c["content_fingerprint"]) == fp
                and str(c["confirmation_role"]) == role
                and str(c["status"]) == CONFIRMATION_STATUS_CONFIRMED
                for c in confirmations
            )
            if not confirmed:
                return WORKSPACE_STAGE_CONTENT_CONFIRMATION_REQUIRED

    reconciliations = []
    return WORKSPACE_STAGE_BILINGUAL_RECONCILIATION


def supersede_confirmations_for_block(conn, *, workspace_id: int, block_id: int, actor_user_id: int | None) -> None:
    rows = conn.execute(
        text(
            """
            UPDATE public.operational_order_content_confirmations
            SET status = :superseded, version = version + 1
            WHERE workspace_id = :workspace_id
              AND block_id = :block_id
              AND status = :confirmed
            RETURNING id
            """
        ),
        {
            "workspace_id": int(workspace_id),
            "block_id": int(block_id),
            "superseded": CONFIRMATION_STATUS_SUPERSEDED,
            "confirmed": CONFIRMATION_STATUS_CONFIRMED,
        },
    ).fetchall()
    for row in rows:
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_CONFIRMATION_SUPERSEDED,
            actor_user_id=actor_user_id,
            metadata={"confirmation_id": int(row[0]), "block_id": int(block_id)},
        )


def invalidate_reconciliations_for_workspace(
    conn,
    *,
    workspace_id: int,
    reason: str,
    actor_user_id: int | None,
) -> None:
    rows = conn.execute(
        text(
            """
            UPDATE public.operational_order_bilingual_reconciliations
            SET status = :invalidated,
                invalidated_at = :invalidated_at,
                invalidation_reason = :reason,
                version = version + 1
            WHERE workspace_id = :workspace_id
              AND status = :reconciled
            RETURNING id
            """
        ),
        {
            "workspace_id": int(workspace_id),
            "invalidated": RECONCILIATION_STATUS_INVALIDATED,
            "reconciled": RECONCILIATION_STATUS_RECONCILED,
            "invalidated_at": _utcnow(),
            "reason": reason,
        },
    ).fetchall()
    for row in rows:
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_RECONCILIATION_INVALIDATED,
            actor_user_id=actor_user_id,
            metadata={"reconciliation_id": int(row[0]), "reason": reason},
        )


def on_block_text_changed(
    conn,
    *,
    workspace_id: int,
    block_id: int,
    locale: str,
    actor_user_id: int | None,
) -> None:
    supersede_confirmations_for_block(
        conn, workspace_id=workspace_id, block_id=block_id, actor_user_id=actor_user_id
    )
    invalidate_reconciliations_for_workspace(
        conn,
        workspace_id=workspace_id,
        reason="Block text changed.",
        actor_user_id=actor_user_id,
    )
    if str(locale) == LOCALE_RU:
        assignments = _fetch_assignments(conn, workspace_id)
        for assignment in assignments:
            if str(assignment["status"]) == ASSIGNMENT_STATUS_COMPLETED:
                conn.execute(
                    text(
                        """
                        UPDATE public.operational_order_translation_assignments
                        SET status = :superseded, updated_at = :updated_at
                        WHERE id = :id AND status = :completed
                        """
                    ),
                    {
                        "id": int(assignment["id"]),
                        "superseded": ASSIGNMENT_STATUS_SUPERSEDED,
                        "completed": ASSIGNMENT_STATUS_COMPLETED,
                        "updated_at": _utcnow(),
                    },
                )


def _require_mutable_workspace(conn, workspace_id: int) -> dict[str, Any]:
    workspace = fetch_workspace_row(conn, workspace_id)
    if workspace is None:
        raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
    assert_workspace_not_frozen(workspace)
    return workspace


def _ensure_editorial_entry(workspace: dict[str, Any]) -> None:
    if workspace["stage"] not in EDITORIAL_ENTRY_STAGES:
        raise OperationalOrderInvalidWorkspaceStageError(
            f"Workspace must be in editorial workflow stage, got {workspace['stage']}."
        )


def _bump_workspace(conn, workspace_id: int, *, expected_version: int | None = None) -> None:
    workspace = _require_mutable_workspace(conn, workspace_id)
    _assert_version(workspace, expected_version, label="Workspace")
    updated = conn.execute(
        text(
            """
            UPDATE public.operational_order_draft_workspaces
            SET version = version + 1, updated_at = :updated_at
            WHERE workspace_id = :workspace_id
              AND (:expected_version IS NULL OR version = :expected_version)
            RETURNING workspace_id
            """
        ),
        {
            "workspace_id": int(workspace_id),
            "updated_at": _utcnow(),
            "expected_version": expected_version,
        },
    ).fetchone()
    if not updated:
        raise OperationalOrderVersionConflictError("Workspace version conflict.")


def create_translation_assignment(
    *,
    workspace_id: int,
    target_locale: str,
    assigned_to_type: str,
    assigned_to_reference: str,
    assigned_to_display_name: str | None,
    assigned_by_user_id: int,
    due_at: datetime | None = None,
    notes: str | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    target = str(target_locale).strip().lower()
    if target not in LOCALES:
        raise OperationalOrderValidationError(f"Invalid target locale: {target_locale}")

    with engine.begin() as conn:
        workspace = _require_mutable_workspace(conn, workspace_id)
        _ensure_editorial_entry(workspace)
        blocks = intake_svc._fetch_blocks(conn, workspace_id)
        pair = _source_and_target_locales(blocks)
        if pair is None:
            raise OperationalOrderTranslationAssignmentConflictError(
                "Translation assignment is not required when both locales are present."
            )
        source_locale, expected_target = pair
        if target != expected_target:
            raise OperationalOrderValidationError(
                f"Target locale must be {expected_target} for this workspace."
            )
        if locale_present(blocks, target):
            raise OperationalOrderTranslationAssignmentConflictError(
                f"Target locale {target} already has blocks."
            )

        active = conn.execute(
            text(
                """
                SELECT id FROM public.operational_order_translation_assignments
                WHERE workspace_id = :workspace_id
                  AND target_locale = :target_locale
                  AND status = ANY(:active_statuses)
                LIMIT 1
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "target_locale": target,
                "active_statuses": list(ASSIGNMENT_ACTIVE_STATUSES),
            },
        ).first()
        if active:
            raise OperationalOrderTranslationAssignmentConflictError(
                "Active translation assignment already exists for target locale."
            )

        source_block = _primary_source_block(blocks, source_locale)
        source_text = block_effective_text(source_block)
        source_fp = content_fingerprint(source_text)
        party = normalize_party_reference(
            reference_type=assigned_to_type,
            reference=assigned_to_reference,
            display_name=assigned_to_display_name,
        )

        row = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_translation_assignments (
                    workspace_id,
                    source_locale,
                    target_locale,
                    assigned_to_type,
                    assigned_to_reference,
                    assigned_to_display_name,
                    assigned_by_user_id,
                    status,
                    due_at,
                    source_block_version,
                    source_content_fingerprint,
                    notes
                ) VALUES (
                    :workspace_id,
                    :source_locale,
                    :target_locale,
                    :assigned_to_type,
                    :assigned_to_reference,
                    :assigned_to_display_name,
                    :assigned_by_user_id,
                    :status,
                    :due_at,
                    :source_block_version,
                    :source_content_fingerprint,
                    :notes
                )
                RETURNING id
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "source_locale": source_locale,
                "target_locale": target,
                "assigned_to_type": party_to_row(party)["reference_type"],
                "assigned_to_reference": party.reference,
                "assigned_to_display_name": party.display_name,
                "assigned_by_user_id": int(assigned_by_user_id),
                "status": ASSIGNMENT_STATUS_REQUESTED,
                "due_at": due_at,
                "source_block_version": int(source_block["version"]),
                "source_content_fingerprint": source_fp,
                "notes": notes,
            },
        ).fetchone()
        assignment_id = int(row[0])
        previous_stage = str(workspace["stage"])
        _bump_workspace(conn, workspace_id, expected_version=expected_version)
        _set_workspace_stage(
            conn,
            workspace_id=workspace_id,
            stage=WORKSPACE_STAGE_TRANSLATION_REQUIRED,
            actor_user_id=assigned_by_user_id,
            previous_stage=previous_stage,
        )
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_TRANSLATION_REQUESTED,
            actor_user_id=assigned_by_user_id,
            metadata={"assignment_id": assignment_id, "target_locale": target},
        )
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_TRANSLATOR_ASSIGNED,
            actor_user_id=assigned_by_user_id,
            metadata={"assignment_id": assignment_id, "assigned_to_reference": party.reference},
        )
        return _return_detail(conn, workspace_id)


def list_translation_assignments(*, workspace_id: int) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        workspace = fetch_workspace_row(conn, workspace_id)
        if not workspace:
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
        return {"items": _fetch_assignments(conn, workspace_id)}


def accept_translation_assignment(
    *,
    workspace_id: int,
    assignment_id: int,
    actor_user_id: int,
    expected_version: int | None = None,
    assignment_expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        workspace = _require_mutable_workspace(conn, workspace_id)
        _ensure_editorial_entry(workspace)
        assignment = _fetch_assignment(conn, workspace_id, assignment_id)
        if not assignment:
            raise OperationalOrderTranslationAssignmentNotFoundError(
                f"Assignment {assignment_id} not found."
            )
        _assert_version(assignment, assignment_expected_version, label="Assignment")
        if str(assignment["status"]) != ASSIGNMENT_STATUS_REQUESTED:
            raise OperationalOrderTranslationAssignmentConflictError(
                f"Assignment must be REQUESTED, got {assignment['status']}."
            )

        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_translation_assignments
                SET status = :status,
                    accepted_at = :accepted_at,
                    version = version + 1,
                    updated_at = :updated_at
                WHERE id = :id
                  AND workspace_id = :workspace_id
                  AND status = :requested
                  AND (:assignment_expected_version IS NULL OR version = :assignment_expected_version)
                RETURNING id
                """
            ),
            {
                "id": int(assignment_id),
                "workspace_id": int(workspace_id),
                "status": ASSIGNMENT_STATUS_ACCEPTED,
                "accepted_at": _utcnow(),
                "updated_at": _utcnow(),
                "requested": ASSIGNMENT_STATUS_REQUESTED,
                "assignment_expected_version": assignment_expected_version,
            },
        ).fetchone()
        if not updated:
            raise OperationalOrderVersionConflictError("Assignment version conflict.")

        previous_stage = str(workspace["stage"])
        _bump_workspace(conn, workspace_id, expected_version=expected_version)
        _set_workspace_stage(
            conn,
            workspace_id=workspace_id,
            stage=WORKSPACE_STAGE_TRANSLATION_IN_PROGRESS,
            actor_user_id=actor_user_id,
            previous_stage=previous_stage,
        )
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_ASSIGNMENT_ACCEPTED,
            actor_user_id=actor_user_id,
            metadata={"assignment_id": assignment_id},
        )
        return _return_detail(conn, workspace_id)


def start_translation_assignment(
    *,
    workspace_id: int,
    assignment_id: int,
    actor_user_id: int,
    expected_version: int | None = None,
    assignment_expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        _require_mutable_workspace(conn, workspace_id)
        assignment = _fetch_assignment(conn, workspace_id, assignment_id)
        if not assignment:
            raise OperationalOrderTranslationAssignmentNotFoundError(
                f"Assignment {assignment_id} not found."
            )
        _assert_version(assignment, assignment_expected_version, label="Assignment")
        if str(assignment["status"]) not in {ASSIGNMENT_STATUS_ACCEPTED, ASSIGNMENT_STATUS_IN_PROGRESS}:
            raise OperationalOrderTranslationAssignmentConflictError(
                "Assignment must be ACCEPTED before start."
            )

        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_translation_assignments
                SET status = :status,
                    version = version + 1,
                    updated_at = :updated_at
                WHERE id = :id
                  AND workspace_id = :workspace_id
                  AND status = ANY(:allowed)
                  AND (:assignment_expected_version IS NULL OR version = :assignment_expected_version)
                RETURNING id
                """
            ),
            {
                "id": int(assignment_id),
                "workspace_id": int(workspace_id),
                "status": ASSIGNMENT_STATUS_IN_PROGRESS,
                "updated_at": _utcnow(),
                "allowed": [ASSIGNMENT_STATUS_ACCEPTED, ASSIGNMENT_STATUS_IN_PROGRESS],
                "assignment_expected_version": assignment_expected_version,
            },
        ).fetchone()
        if not updated:
            raise OperationalOrderVersionConflictError("Assignment version conflict.")

        _bump_workspace(conn, workspace_id, expected_version=expected_version)
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_TRANSLATION_STARTED,
            actor_user_id=actor_user_id,
            metadata={"assignment_id": assignment_id},
        )
        return _return_detail(conn, workspace_id)


def complete_translation_assignment(
    *,
    workspace_id: int,
    assignment_id: int,
    actor_user_id: int,
    target_block_id: int,
    expected_version: int | None = None,
    assignment_expected_version: int | None = None,
    block_expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        workspace = _require_mutable_workspace(conn, workspace_id)
        assignment = _fetch_assignment(conn, workspace_id, assignment_id)
        if not assignment:
            raise OperationalOrderTranslationAssignmentNotFoundError(
                f"Assignment {assignment_id} not found."
            )
        _assert_version(assignment, assignment_expected_version, label="Assignment")
        if str(assignment["status"]) not in ASSIGNMENT_ACTIVE_STATUSES:
            raise OperationalOrderTranslationAssignmentConflictError("Assignment is not active.")

        blocks = intake_svc._fetch_blocks(conn, workspace_id)
        source_dict = next(
            (
                b
                for b in blocks
                if str(b["locale"]) == str(assignment["source_locale"])
                and int(b["version"]) == int(assignment["source_block_version"])
                and content_fingerprint(block_effective_text(b))
                == str(assignment["source_content_fingerprint"])
            ),
            None,
        )
        if source_dict is None:
            raise OperationalOrderTranslationSourceStaleError(
                "Source block version or fingerprint changed since assignment was created."
            )

        target_block = conn.execute(
            text(
                """
                SELECT *
                FROM public.operational_order_draft_blocks
                WHERE workspace_id = :workspace_id AND block_id = :block_id
                """
            ),
            {"workspace_id": int(workspace_id), "block_id": int(target_block_id)},
        ).mappings().first()
        if not target_block:
            raise OperationalOrderValidationError(f"Target block {target_block_id} not found.")
        target_dict = dict(target_block)
        if str(target_dict["locale"]) != str(assignment["target_locale"]):
            raise OperationalOrderValidationError("Target block locale mismatch.")
        if block_expected_version is not None and int(target_dict["version"]) != int(block_expected_version):
            raise OperationalOrderVersionConflictError("Target block version conflict.")

        target_text = block_effective_text(target_dict)
        if not target_text.strip():
            raise OperationalOrderValidationError("Target block has no effective text.")

        produced_fp = content_fingerprint(target_text)
        conn.execute(
            text(
                """
                UPDATE public.operational_order_translation_assignments
                SET status = :status,
                    completed_at = :completed_at,
                    target_block_version = :target_block_version,
                    produced_content_fingerprint = :produced_fp,
                    version = version + 1,
                    updated_at = :updated_at
                WHERE id = :id
                  AND workspace_id = :workspace_id
                """
            ),
            {
                "id": int(assignment_id),
                "workspace_id": int(workspace_id),
                "status": ASSIGNMENT_STATUS_COMPLETED,
                "completed_at": _utcnow(),
                "target_block_version": int(target_dict["version"]),
                "produced_fp": produced_fp,
                "updated_at": _utcnow(),
            },
        )

        _append_provenance(
            conn,
            workspace_id=workspace_id,
            draft_block_id=int(target_block_id),
            locale=str(target_dict["locale"]),
            source_type=TEXT_SOURCE_IMPORTED,
            source_actor_type=str(assignment["assigned_to_type"]),
            source_actor_reference=str(assignment["assigned_to_reference"]),
            source_org_unit_id=int(workspace["submitting_org_unit_id"]),
            action=PROVENANCE_ACTION_TRANSLATION,
            text_value=target_text,
            metadata={"assignment_id": assignment_id, "source_block_id": int(source_dict["block_id"])},
        )
        previous_stage = str(workspace["stage"])
        _bump_workspace(conn, workspace_id, expected_version=expected_version)
        _set_workspace_stage(
            conn,
            workspace_id=workspace_id,
            stage=WORKSPACE_STAGE_CONTENT_CONFIRMATION_REQUIRED,
            actor_user_id=actor_user_id,
            previous_stage=previous_stage,
        )
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_TRANSLATION_COMPLETED,
            actor_user_id=actor_user_id,
            metadata={"assignment_id": assignment_id, "target_block_id": target_block_id},
        )
        return _return_detail(conn, workspace_id)


def cancel_translation_assignment(
    *,
    workspace_id: int,
    assignment_id: int,
    actor_user_id: int,
    expected_version: int | None = None,
    assignment_expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        _require_mutable_workspace(conn, workspace_id)
        assignment = _fetch_assignment(conn, workspace_id, assignment_id)
        if not assignment:
            raise OperationalOrderTranslationAssignmentNotFoundError(
                f"Assignment {assignment_id} not found."
            )
        _assert_version(assignment, assignment_expected_version, label="Assignment")
        if str(assignment["status"]) not in ASSIGNMENT_ACTIVE_STATUSES:
            raise OperationalOrderTranslationAssignmentConflictError("Assignment is not active.")

        conn.execute(
            text(
                """
                UPDATE public.operational_order_translation_assignments
                SET status = :status,
                    cancelled_at = :cancelled_at,
                    version = version + 1,
                    updated_at = :updated_at
                WHERE id = :id AND workspace_id = :workspace_id
                """
            ),
            {
                "id": int(assignment_id),
                "workspace_id": int(workspace_id),
                "status": ASSIGNMENT_STATUS_CANCELLED,
                "cancelled_at": _utcnow(),
                "updated_at": _utcnow(),
            },
        )
        _bump_workspace(conn, workspace_id, expected_version=expected_version)
        return _return_detail(conn, workspace_id)


def list_content_confirmations(*, workspace_id: int) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        if not fetch_workspace_row(conn, workspace_id):
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
        return {"items": _fetch_confirmations(conn, workspace_id)}


def create_content_confirmation(
    *,
    workspace_id: int,
    block_id: int,
    confirmation_role: str,
    confirmer_party_type: str,
    confirmer_party_reference: str,
    confirmer_display_name: str | None,
    confirmer_user_id: int,
    block_expected_version: int | None = None,
    expected_version: int | None = None,
    operator_recorded: bool = False,
) -> dict[str, Any]:
    _require_available()
    role = str(confirmation_role).strip().upper()
    with engine.begin() as conn:
        workspace = _require_mutable_workspace(conn, workspace_id)
        _ensure_editorial_entry(workspace)

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
            raise OperationalOrderValidationError(f"Block {block_id} not found.")
        block_dict = dict(block)
        if block_expected_version is not None and int(block_dict["version"]) != int(block_expected_version):
            raise OperationalOrderConfirmationStaleTextError(
                "Block version does not match expected version."
            )

        fp = content_fingerprint(block_effective_text(block_dict))
        if role == CONFIRMATION_ROLE_CONTENT_AUTHOR:
            if not operator_recorded:
                if workspace.get("content_author_type") != "PERSON":
                    raise OperationalOrderConfirmationPartyMismatchError(
                        "Content author party type must be PERSON."
                    )
                if str(workspace.get("content_author_reference")) != str(confirmer_user_id):
                    raise OperationalOrderConfirmationPartyMismatchError(
                        "Authenticated user does not match content author."
                    )
        elif role == CONFIRMATION_ROLE_TRANSLATOR:
            assignments = _fetch_assignments(conn, workspace_id)
            matching = [
                a
                for a in assignments
                if str(a["target_locale"]) == str(block_dict["locale"])
                and str(a["status"]) == ASSIGNMENT_STATUS_COMPLETED
                and str(a["assigned_to_type"]) == "PERSON"
                and str(a["assigned_to_reference"]) == str(confirmer_user_id)
            ]
            if not matching and str(confirmer_party_reference) != str(confirmer_user_id):
                raise OperationalOrderConfirmationPartyMismatchError(
                    "Authenticated user is not the assigned translator."
                )

        existing = conn.execute(
            text(
                """
                SELECT id, status
                FROM public.operational_order_content_confirmations
                WHERE workspace_id = :workspace_id
                  AND block_id = :block_id
                  AND confirmation_role = :role
                  AND content_fingerprint = :fingerprint
                  AND status = :confirmed
                LIMIT 1
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "block_id": int(block_id),
                "role": role,
                "fingerprint": fp,
                "confirmed": CONFIRMATION_STATUS_CONFIRMED,
            },
        ).mappings().first()
        if existing:
            return _return_detail(conn, workspace_id)

        party = normalize_party_reference(
            reference_type=confirmer_party_type,
            reference=confirmer_party_reference,
            display_name=confirmer_display_name,
        )
        row = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_content_confirmations (
                    workspace_id,
                    locale,
                    block_id,
                    block_version,
                    content_fingerprint,
                    confirmer_party_type,
                    confirmer_party_reference,
                    confirmer_display_name,
                    confirmer_user_id,
                    confirmation_role,
                    status,
                    confirmed_at
                ) VALUES (
                    :workspace_id,
                    :locale,
                    :block_id,
                    :block_version,
                    :content_fingerprint,
                    :confirmer_party_type,
                    :confirmer_party_reference,
                    :confirmer_display_name,
                    :confirmer_user_id,
                    :confirmation_role,
                    :status,
                    :confirmed_at
                )
                RETURNING id
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "locale": str(block_dict["locale"]),
                "block_id": int(block_id),
                "block_version": int(block_dict["version"]),
                "content_fingerprint": fp,
                "confirmer_party_type": party_to_row(party)["reference_type"],
                "confirmer_party_reference": party.reference,
                "confirmer_display_name": party.display_name,
                "confirmer_user_id": int(confirmer_user_id),
                "confirmation_role": role,
                "status": CONFIRMATION_STATUS_CONFIRMED,
                "confirmed_at": _utcnow(),
            },
        ).fetchone()
        confirmation_id = int(row[0])
        _bump_workspace(conn, workspace_id, expected_version=expected_version)
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_CONFIRMATION_CREATED,
            actor_user_id=confirmer_user_id,
            metadata={
                "confirmation_id": confirmation_id,
                "block_id": block_id,
                "role": role,
                "operator_recorded": operator_recorded,
            },
        )
        blocks = intake_svc._fetch_blocks(conn, workspace_id)
        confirmations = _fetch_confirmations(conn, workspace_id)
        assignments = _fetch_assignments(conn, workspace_id)
        stage = _derive_editorial_stage(blocks=blocks, assignments=assignments, confirmations=confirmations)
        _set_workspace_stage(
            conn,
            workspace_id=workspace_id,
            stage=stage,
            actor_user_id=confirmer_user_id,
            previous_stage=str(workspace["stage"]),
        )
        return _return_detail(conn, workspace_id)


def revoke_content_confirmation(
    *,
    workspace_id: int,
    confirmation_id: int,
    actor_user_id: int,
    revocation_reason: str | None = None,
    expected_version: int | None = None,
    confirmation_expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        _require_mutable_workspace(conn, workspace_id)
        confirmation = _fetch_confirmation(conn, workspace_id, confirmation_id)
        if not confirmation:
            raise OperationalOrderConfirmationNotFoundError(
                f"Confirmation {confirmation_id} not found."
            )
        _assert_version(confirmation, confirmation_expected_version, label="Confirmation")
        if str(confirmation["status"]) != CONFIRMATION_STATUS_CONFIRMED:
            raise OperationalOrderConfirmationConflictError("Confirmation is not active.")

        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_content_confirmations
                SET status = :revoked,
                    revoked_at = :revoked_at,
                    revocation_reason = :reason,
                    version = version + 1
                WHERE id = :id
                  AND workspace_id = :workspace_id
                  AND status = :confirmed
                RETURNING id
                """
            ),
            {
                "id": int(confirmation_id),
                "workspace_id": int(workspace_id),
                "revoked": CONFIRMATION_STATUS_REVOKED,
                "revoked_at": _utcnow(),
                "reason": revocation_reason,
                "confirmed": CONFIRMATION_STATUS_CONFIRMED,
            },
        ).fetchone()
        if not updated:
            raise OperationalOrderConfirmationNotFoundError("Confirmation not found or already revoked.")

        _bump_workspace(conn, workspace_id, expected_version=expected_version)
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_CONFIRMATION_REVOKED,
            actor_user_id=actor_user_id,
            metadata={"confirmation_id": confirmation_id, "reason": revocation_reason},
        )
        return _return_detail(conn, workspace_id)


def list_bilingual_reconciliations(*, workspace_id: int) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        if not fetch_workspace_row(conn, workspace_id):
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
        return {"items": _fetch_reconciliations(conn, workspace_id)}


def create_bilingual_reconciliation(
    *,
    workspace_id: int,
    ru_block_id: int,
    kk_block_id: int,
    reconciled_by_user_id: int,
    notes: str | None = None,
    ru_block_expected_version: int | None = None,
    kk_block_expected_version: int | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        workspace = _require_mutable_workspace(conn, workspace_id)
        _ensure_editorial_entry(workspace)
        blocks = intake_svc._fetch_blocks(conn, workspace_id)
        confirmations = _fetch_confirmations(conn, workspace_id)
        assignments = _fetch_assignments(conn, workspace_id)

        ru_block = next((b for b in blocks if int(b["block_id"]) == int(ru_block_id)), None)
        kk_block = next((b for b in blocks if int(b["block_id"]) == int(kk_block_id)), None)
        if not ru_block or not kk_block:
            raise OperationalOrderValidationError("RU/KK block pair not found.")
        if str(ru_block["locale"]) != LOCALE_RU or str(kk_block["locale"]) != LOCALE_KK:
            raise OperationalOrderValidationError("Block locale mismatch for reconciliation.")
        if ru_block_expected_version is not None and int(ru_block["version"]) != int(ru_block_expected_version):
            raise OperationalOrderVersionConflictError("RU block version conflict.")
        if kk_block_expected_version is not None and int(kk_block["version"]) != int(kk_block_expected_version):
            raise OperationalOrderVersionConflictError("KK block version conflict.")

        ru_fp = content_fingerprint(block_effective_text(ru_block))
        kk_fp = content_fingerprint(block_effective_text(kk_block))
        for block, fp in ((ru_block, ru_fp), (kk_block, kk_fp)):
            for role in required_roles_for_block(locale=str(block["locale"]), assignments=assignments):
                confirmed = any(
                    int(c["block_id"]) == int(block["block_id"])
                    and str(c["content_fingerprint"]) == fp
                    and str(c["confirmation_role"]) == role
                    and str(c["status"]) == CONFIRMATION_STATUS_CONFIRMED
                    for c in confirmations
                )
                if not confirmed:
                    raise OperationalOrderEditorialPackageNotReadyError(
                        f"Missing {role} confirmation for block {block['block_id']}."
                    )

        existing = conn.execute(
            text(
                """
                SELECT id
                FROM public.operational_order_bilingual_reconciliations
                WHERE workspace_id = :workspace_id
                  AND ru_block_id = :ru_block_id
                  AND kk_block_id = :kk_block_id
                  AND ru_content_fingerprint = :ru_fp
                  AND kk_content_fingerprint = :kk_fp
                  AND status = :reconciled
                LIMIT 1
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "ru_block_id": int(ru_block_id),
                "kk_block_id": int(kk_block_id),
                "ru_fp": ru_fp,
                "kk_fp": kk_fp,
                "reconciled": RECONCILIATION_STATUS_RECONCILED,
            },
        ).first()
        if existing:
            return _return_detail(conn, workspace_id)

        conn.execute(
            text(
                """
                UPDATE public.operational_order_bilingual_reconciliations
                SET status = :superseded, version = version + 1
                WHERE workspace_id = :workspace_id
                  AND ru_block_id = :ru_block_id
                  AND kk_block_id = :kk_block_id
                  AND status = :reconciled
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "ru_block_id": int(ru_block_id),
                "kk_block_id": int(kk_block_id),
                "superseded": RECONCILIATION_STATUS_SUPERSEDED,
                "reconciled": RECONCILIATION_STATUS_RECONCILED,
            },
        )

        row = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_bilingual_reconciliations (
                    workspace_id,
                    ru_block_id,
                    ru_block_version,
                    ru_content_fingerprint,
                    kk_block_id,
                    kk_block_version,
                    kk_content_fingerprint,
                    status,
                    reconciled_by_user_id,
                    reconciled_at,
                    notes
                ) VALUES (
                    :workspace_id,
                    :ru_block_id,
                    :ru_block_version,
                    :ru_fp,
                    :kk_block_id,
                    :kk_block_version,
                    :kk_fp,
                    :status,
                    :reconciled_by_user_id,
                    :reconciled_at,
                    :notes
                )
                RETURNING id
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "ru_block_id": int(ru_block_id),
                "ru_block_version": int(ru_block["version"]),
                "ru_fp": ru_fp,
                "kk_block_id": int(kk_block_id),
                "kk_block_version": int(kk_block["version"]),
                "kk_fp": kk_fp,
                "status": RECONCILIATION_STATUS_RECONCILED,
                "reconciled_by_user_id": int(reconciled_by_user_id),
                "reconciled_at": _utcnow(),
                "notes": notes,
            },
        ).fetchone()
        reconciliation_id = int(row[0])
        _bump_workspace(conn, workspace_id, expected_version=expected_version)
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_RECONCILIATION_CREATED,
            actor_user_id=reconciled_by_user_id,
            metadata={"reconciliation_id": reconciliation_id},
        )
        return _return_detail(conn, workspace_id)


def invalidate_bilingual_reconciliation(
    *,
    workspace_id: int,
    reconciliation_id: int,
    actor_user_id: int,
    invalidation_reason: str | None = None,
    expected_version: int | None = None,
    reconciliation_expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        _require_mutable_workspace(conn, workspace_id)
        reconciliation = _fetch_reconciliation(conn, workspace_id, reconciliation_id)
        if not reconciliation:
            raise OperationalOrderReconciliationNotFoundError(
                f"Reconciliation {reconciliation_id} not found."
            )
        _assert_version(reconciliation, reconciliation_expected_version, label="Reconciliation")
        if str(reconciliation["status"]) != RECONCILIATION_STATUS_RECONCILED:
            raise OperationalOrderReconciliationStaleError("Reconciliation is not active.")

        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_bilingual_reconciliations
                SET status = :invalidated,
                    invalidated_at = :invalidated_at,
                    invalidation_reason = :reason,
                    version = version + 1
                WHERE id = :id
                  AND workspace_id = :workspace_id
                  AND status = :reconciled
                RETURNING id
                """
            ),
            {
                "id": int(reconciliation_id),
                "workspace_id": int(workspace_id),
                "invalidated": RECONCILIATION_STATUS_INVALIDATED,
                "invalidated_at": _utcnow(),
                "reason": invalidation_reason,
                "reconciled": RECONCILIATION_STATUS_RECONCILED,
            },
        ).fetchone()
        if not updated:
            raise OperationalOrderReconciliationNotFoundError("Reconciliation not found.")

        _bump_workspace(conn, workspace_id, expected_version=expected_version)
        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_RECONCILIATION_INVALIDATED,
            actor_user_id=actor_user_id,
            metadata={"reconciliation_id": reconciliation_id, "reason": invalidation_reason},
        )
        return _return_detail(conn, workspace_id)


def validate_editorial_package_command(
    *,
    workspace_id: int,
    expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        workspace = fetch_workspace_row(conn, workspace_id)
        if not workspace:
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
        blocks = intake_svc._fetch_blocks(conn, workspace_id)
        clarifications = intake_svc._fetch_clarifications(conn, workspace_id)
        assignments = _fetch_assignments(conn, workspace_id)
        confirmations = _fetch_confirmations(conn, workspace_id)
        reconciliations = _fetch_reconciliations(conn, workspace_id)
        validation = validate_editorial_package(
            workspace=workspace,
            blocks=blocks,
            clarifications=clarifications,
            assignments=assignments,
            confirmations=confirmations,
            reconciliations=reconciliations,
            expected_version=expected_version,
        )
        return {"validation": validation, "workspace_id": workspace_id}


def mark_editorial_package_ready(
    *,
    workspace_id: int,
    actor_user_id: int,
    expected_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        workspace = _require_mutable_workspace(conn, workspace_id)
        if str(workspace["stage"]) == WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY:
            return _return_detail(conn, workspace_id)

        blocks = intake_svc._fetch_blocks(conn, workspace_id)
        clarifications = intake_svc._fetch_clarifications(conn, workspace_id)
        assignments = _fetch_assignments(conn, workspace_id)
        confirmations = _fetch_confirmations(conn, workspace_id)
        reconciliations = _fetch_reconciliations(conn, workspace_id)
        validation = validate_editorial_package(
            workspace=workspace,
            blocks=blocks,
            clarifications=clarifications,
            assignments=assignments,
            confirmations=confirmations,
            reconciliations=reconciliations,
            expected_version=expected_version,
        )
        if not validation.is_valid:
            _append_audit(
                conn,
                workspace_id=workspace_id,
                action=AUDIT_ACTION_EDITORIAL_PACKAGE_VALIDATION_FAILED,
                actor_user_id=actor_user_id,
                metadata={"issue_count": len(validation.issues)},
            )
            raise OperationalOrderEditorialPackageNotReadyError(
                "Editorial package is not ready."
            )

        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_draft_workspaces
                SET stage = :stage,
                    version = version + 1,
                    updated_at = :updated_at
                WHERE workspace_id = :workspace_id
                  AND (:expected_version IS NULL OR version = :expected_version)
                RETURNING workspace_id
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "stage": WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY,
                "updated_at": _utcnow(),
                "expected_version": expected_version,
            },
        ).fetchone()
        if not updated:
            raise OperationalOrderVersionConflictError("Workspace version conflict.")

        _append_audit(
            conn,
            workspace_id=workspace_id,
            action=AUDIT_ACTION_EDITORIAL_PACKAGE_READY,
            actor_user_id=actor_user_id,
        )
        return _return_detail(conn, workspace_id)


def fetch_editorial_entities(conn, workspace_id: int) -> dict[str, Any]:
    return {
        "translation_assignments": _fetch_assignments(conn, workspace_id),
        "content_confirmations": _fetch_confirmations(conn, workspace_id),
        "bilingual_reconciliations": _fetch_reconciliations(conn, workspace_id),
    }


def _return_detail(conn, workspace_id: int) -> dict[str, Any]:
    return intake_svc._build_detail(conn, workspace_id)
