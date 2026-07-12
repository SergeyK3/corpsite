"""Document aggregate factory — promotion from editorial package (OO-IMP-003)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.operational_orders import (
    AUDIT_ACTION_PROMOTION_REPLAY,
    AUDIT_ACTION_REVISION_ADVISORY_RETURNED,
    CONFIRMATION_STATUS_CONFIRMED,
    DOCUMENT_KIND_OPERATIONAL_ORDER,
    DOCUMENT_STATUS_CREATED,
    LOCALE_KK,
    LOCALE_RU,
    PROMOTION_AUDIT_ACTION_COMPLETED,
    PROMOTION_AUDIT_ACTION_DOCUMENT_CREATED,
    PROMOTION_AUDIT_ACTION_LOCALIZATION_SNAPSHOTTED,
    PROMOTION_AUDIT_ACTION_PROMOTION_REPLAY,
    PROMOTION_AUDIT_ACTION_REVISION_ADVISORY_RETURNED,
    PROMOTION_AUDIT_ACTION_STARTED,
    PROMOTION_AUDIT_ACTION_VERSION_CREATED,
    PROMOTION_AUDIT_ACTION_WORKSPACE_FROZEN,
    PROMOTION_STATUS_COMPLETED,
    PROMOTION_STATUS_STARTED,
    PROVENANCE_ACTION_DOCUMENT_VERSION_CREATED,
    PROVENANCE_ACTION_PROMOTED_FROM_WORKSPACE,
    PROVENANCE_ACTION_PROMOTION_REPLAY,
    PROVENANCE_ACTION_SNAPSHOT_CREATED,
    PROVENANCE_ACTION_WORKSPACE_DRIFT_DETECTED,
    RECONCILIATION_STATUS_RECONCILED,
    WORKSPACE_STAGE_DOCUMENT_PROMOTED,
    WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY,
)
from app.document_engine import ValidationResult
from app.operational_orders.domain import content_fingerprint, json_safe
from app.operational_orders.errors import (
    OperationalOrderDocumentNotFoundError,
    OperationalOrderDocumentVersionNotFoundError,
    OperationalOrderPromotionNotReadyError,
    OperationalOrderPromotionVersionConflictError,
    OperationalOrderValidationError,
    OperationalOrderVersionConflictError,
    OperationalOrderWorkspaceNotFoundError,
)
from app.operational_orders.repository import document_aggregate_available, fetch_workspace_row
from app.operational_orders.services import draft_intake_service as intake_svc
from app.operational_orders.services import editorial_workflow_service as editorial_svc
from app.operational_orders.services.workspace_drift_detector import detect_workspace_drift
from app.operational_orders.services.workspace_freeze_service import (
    ensure_workspace_frozen_if_promoted,
    freeze_workspace,
)
from app.operational_orders.validation.workspace_freeze_validation import build_replay_advisories
from app.operational_orders.validation.editorial_validation import (
    block_effective_text,
    block_pair_key,
    matched_block_pairs,
)
from app.operational_orders.validation.promotion_validation import (
    snapshot_fingerprint,
    validate_promotion,
    workspace_fingerprint,
)


def _require_available() -> None:
    if not document_aggregate_available():
        raise OperationalOrderValidationError("Operational orders document schema is not available.")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _append_promotion_audit(
    conn,
    *,
    promotion_id: int,
    action: str,
    actor_user_id: int | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.operational_order_promotion_audit (
                promotion_id, action, actor_user_id, metadata_json
            ) VALUES (
                :promotion_id, :action, :actor_user_id, CAST(:metadata_json AS jsonb)
            )
            """
        ),
        {
            "promotion_id": int(promotion_id),
            "action": action,
            "actor_user_id": actor_user_id,
            "metadata_json": json.dumps(json_safe(metadata) or {}),
        },
    )


def _append_workspace_provenance(
    conn,
    *,
    workspace_id: int,
    draft_block_id: int,
    locale: str,
    action: str,
    actor_user_id: int,
    text_value: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    intake_svc._append_provenance(
        conn,
        workspace_id=workspace_id,
        draft_block_id=draft_block_id,
        locale=locale,
        source_type="GENERATED",
        source_actor_type="PERSON",
        source_actor_reference=str(actor_user_id),
        source_org_unit_id=None,
        source_language=locale,
        action=action,
        submitted_or_effective_text=text_value,
        metadata=metadata,
    )


def _fetch_document_by_workspace(conn, workspace_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT d.*, w.submitting_org_unit_id
            FROM public.operational_order_documents d
            JOIN public.operational_order_draft_workspaces w
              ON w.workspace_id = d.workspace_id
            WHERE d.workspace_id = :workspace_id
            """
        ),
        {"workspace_id": int(workspace_id)},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_document(conn, document_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT d.*, w.submitting_org_unit_id
            FROM public.operational_order_documents d
            JOIN public.operational_order_draft_workspaces w
              ON w.workspace_id = d.workspace_id
            WHERE d.id = :document_id
            """
        ),
        {"document_id": int(document_id)},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_promotion(conn, promotion_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_promotions
            WHERE id = :promotion_id
            """
        ),
        {"promotion_id": int(promotion_id)},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_current_version(conn, document_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_document_versions
            WHERE document_id = :document_id AND is_current = TRUE
            ORDER BY version_number DESC
            LIMIT 1
            """
        ),
        {"document_id": int(document_id)},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_version(conn, document_id: int, version_number: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_document_versions
            WHERE document_id = :document_id AND version_number = :version_number
            """
        ),
        {"document_id": int(document_id), "version_number": int(version_number)},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_localizations(conn, document_version_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_document_localizations
            WHERE document_version_id = :document_version_id
            ORDER BY locale, block_type, sequence
            """
        ),
        {"document_version_id": int(document_version_id)},
    ).mappings().all()
    return [dict(row) for row in rows]


def _confirmation_ids_for_block(
    confirmations: Sequence[dict[str, Any]],
    *,
    block_id: int,
    fingerprint: str,
) -> list[int]:
    return sorted(
        int(c["id"])
        for c in confirmations
        if int(c["block_id"]) == int(block_id)
        and str(c["content_fingerprint"]) == fingerprint
        and str(c["status"]) == CONFIRMATION_STATUS_CONFIRMED
    )


def _reconciliation_for_pair(
    reconciliations: Sequence[dict[str, Any]],
    *,
    ru_block: dict[str, Any],
    kk_block: dict[str, Any],
) -> int | None:
    ru_fp = content_fingerprint(block_effective_text(ru_block))
    kk_fp = content_fingerprint(block_effective_text(kk_block))
    match = next(
        (
            r
            for r in reconciliations
            if str(r["status"]) == RECONCILIATION_STATUS_RECONCILED
            and int(r["ru_block_id"]) == int(ru_block["block_id"])
            and int(r["kk_block_id"]) == int(kk_block["block_id"])
            and str(r["ru_content_fingerprint"]) == ru_fp
            and str(r["kk_content_fingerprint"]) == kk_fp
        ),
        None,
    )
    return int(match["id"]) if match else None


def _build_localization_rows(
    *,
    blocks: Sequence[dict[str, Any]],
    confirmations: Sequence[dict[str, Any]],
    reconciliations: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    pair_reconciliation = {
        block_pair_key(ru): _reconciliation_for_pair(reconciliations, ru_block=ru, kk_block=kk)
        for ru, kk in matched_block_pairs(blocks)
    }
    rows: list[dict[str, Any]] = []
    for block in sorted(
        blocks,
        key=lambda item: (str(item["locale"]), str(item["block_type"]), int(item["sequence"])),
    ):
        text_value = block_effective_text(block)
        if not text_value.strip():
            continue
        fp = content_fingerprint(text_value)
        reconciliation_id = pair_reconciliation.get(block_pair_key(block))
        rows.append(
            {
                "locale": str(block["locale"]),
                "block_type": str(block["block_type"]),
                "sequence": int(block["sequence"]),
                "official_text": text_value,
                "content_fingerprint": fp,
                "source_workspace_block_version": int(block["version"]),
                "source_confirmation_ids": _confirmation_ids_for_block(
                    confirmations,
                    block_id=int(block["block_id"]),
                    fingerprint=fp,
                ),
                "source_reconciliation_id": reconciliation_id,
                "source_block_id": int(block["block_id"]),
            }
        )
    return rows


def _document_summary(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": int(document["id"]),
        "workspace_id": int(document["workspace_id"]),
        "document_kind": str(document["document_kind"]),
        "status": str(document["status"]),
        "created_from_workspace_version": int(document["created_from_workspace_version"]),
        "created_from_workspace_fingerprint": str(document["created_from_workspace_fingerprint"]),
        "promotion_id": int(document["promotion_id"]),
        "created_at": document["created_at"],
        "created_by_user_id": int(document["created_by_user_id"]),
        "version": int(document["version"]),
        "submitting_org_unit_id": int(document.get("submitting_org_unit_id") or 0) or None,
        "ready_for_signature_at": document.get("ready_for_signature_at"),
        "ready_for_signature_by_user_id": document.get("ready_for_signature_by_user_id"),
    }


def _build_document_detail(conn, document_id: int) -> dict[str, Any]:
    document = _fetch_document(conn, document_id)
    if not document:
        raise OperationalOrderDocumentNotFoundError(f"Document {document_id} not found.")
    current_version = _fetch_current_version(conn, document_id)
    promotion = _fetch_promotion(conn, int(document["promotion_id"]))
    return {
        "document": _document_summary(document),
        "current_version": dict(current_version) if current_version else None,
        "promotion": dict(promotion) if promotion else None,
    }


def _promotion_result_payload(
    *,
    workspace_id: int,
    document_detail: dict[str, Any],
    validation: ValidationResult,
    idempotent_replay: bool,
    workspace_frozen: bool,
    workspace_drift_detected: bool,
    revision_recommended: bool,
) -> dict[str, Any]:
    document = document_detail["document"]
    promotion = document_detail.get("promotion") or {}
    return {
        "workspace_id": int(workspace_id),
        "document": document_detail,
        "validation": validation,
        "idempotent_replay": idempotent_replay,
        "workspace_frozen": workspace_frozen,
        "workspace_drift_detected": workspace_drift_detected,
        "revision_recommended": revision_recommended,
        "document_id": int(document["document_id"]),
        "promotion_id": int(document.get("promotion_id") or promotion.get("id") or 0),
    }


def _handle_promotion_replay(
    conn,
    *,
    workspace_id: int,
    workspace: dict[str, Any],
    existing_document: dict[str, Any],
    actor_user_id: int,
) -> dict[str, Any]:
    ensure_workspace_frozen_if_promoted(conn, workspace=workspace, actor_user_id=actor_user_id)
    workspace = fetch_workspace_row(conn, workspace_id) or workspace
    blocks = intake_svc._fetch_blocks(conn, workspace_id)
    reconciliations = editorial_svc._fetch_reconciliations(conn, workspace_id)
    promotion_fp = str(existing_document.get("created_from_workspace_fingerprint") or "")
    drift = detect_workspace_drift(
        workspace=workspace,
        blocks=blocks,
        reconciliations=reconciliations,
        promotion_workspace_fingerprint=promotion_fp,
    )
    document_detail = _build_document_detail(conn, int(existing_document["id"]))
    promotion_id = int(existing_document.get("promotion_id") or 0)
    representative_block = next(
        (b for b in blocks if str(b.get("block_type")) == "TITLE"),
        blocks[0] if blocks else None,
    )
    if representative_block is not None:
        intake_svc._append_provenance(
            conn,
            workspace_id=workspace_id,
            draft_block_id=int(representative_block["block_id"]),
            locale=str(representative_block["locale"]),
            source_type="GENERATED",
            source_actor_type="PERSON",
            source_actor_reference=str(actor_user_id),
            source_org_unit_id=None,
            source_language=str(representative_block["locale"]),
            action=PROVENANCE_ACTION_PROMOTION_REPLAY,
            submitted_or_effective_text=str(
                representative_block.get("workspace_effective_text")
                or representative_block.get("submitted_text")
                or ""
            ),
            metadata={
                "document_id": int(existing_document["id"]),
                "promotion_id": promotion_id,
                "workspace_drift_detected": drift["workspace_drift_detected"],
            },
        )
        if drift["workspace_drift_detected"]:
            intake_svc._append_provenance(
                conn,
                workspace_id=workspace_id,
                draft_block_id=int(representative_block["block_id"]),
                locale=str(representative_block["locale"]),
                source_type="GENERATED",
                source_actor_type="PERSON",
                source_actor_reference=str(actor_user_id),
                source_org_unit_id=None,
                source_language=str(representative_block["locale"]),
                action=PROVENANCE_ACTION_WORKSPACE_DRIFT_DETECTED,
                submitted_or_effective_text=str(
                    representative_block.get("workspace_effective_text")
                    or representative_block.get("submitted_text")
                    or ""
                ),
                metadata={
                    "document_id": int(existing_document["id"]),
                    "current_workspace_fingerprint": drift["current_workspace_fingerprint"],
                    "promotion_workspace_fingerprint": drift["promotion_workspace_fingerprint"],
                },
            )
    intake_svc._append_audit(
        conn,
        workspace_id=workspace_id,
        action=AUDIT_ACTION_PROMOTION_REPLAY,
        actor_user_id=actor_user_id,
        metadata={
            "document_id": int(existing_document["id"]),
            "workspace_drift_detected": drift["workspace_drift_detected"],
        },
    )
    if promotion_id:
        _append_promotion_audit(
            conn,
            promotion_id=promotion_id,
            action=PROMOTION_AUDIT_ACTION_PROMOTION_REPLAY,
            actor_user_id=actor_user_id,
            metadata={"document_id": int(existing_document["id"]), **drift},
        )
        if drift["workspace_drift_detected"]:
            intake_svc._append_audit(
                conn,
                workspace_id=workspace_id,
                action=AUDIT_ACTION_REVISION_ADVISORY_RETURNED,
                actor_user_id=actor_user_id,
                metadata={"document_id": int(existing_document["id"]), **drift},
            )
            _append_promotion_audit(
                conn,
                promotion_id=promotion_id,
                action=PROMOTION_AUDIT_ACTION_REVISION_ADVISORY_RETURNED,
                actor_user_id=actor_user_id,
                metadata={"document_id": int(existing_document["id"]), **drift},
            )
    validation = build_replay_advisories(drift_detected=bool(drift["workspace_drift_detected"]))
    return _promotion_result_payload(
        workspace_id=workspace_id,
        document_detail=document_detail,
        validation=validation,
        idempotent_replay=True,
        workspace_frozen=True,
        workspace_drift_detected=bool(drift["workspace_drift_detected"]),
        revision_recommended=bool(drift["revision_recommended"]),
    )


def promote_workspace(
    *,
    workspace_id: int,
    actor_user_id: int,
    expected_workspace_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        workspace = fetch_workspace_row(conn, workspace_id)
        if not workspace:
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")

        existing_document = _fetch_document_by_workspace(conn, workspace_id)
        if existing_document is not None:
            return _handle_promotion_replay(
                conn,
                workspace_id=workspace_id,
                workspace=workspace,
                existing_document=existing_document,
                actor_user_id=actor_user_id,
            )

        blocks = intake_svc._fetch_blocks(conn, workspace_id)
        clarifications = intake_svc._fetch_clarifications(conn, workspace_id)
        assignments = editorial_svc._fetch_assignments(conn, workspace_id)
        confirmations = editorial_svc._fetch_confirmations(conn, workspace_id)
        reconciliations = editorial_svc._fetch_reconciliations(conn, workspace_id)

        validation = validate_promotion(
            workspace=workspace,
            blocks=blocks,
            clarifications=clarifications,
            assignments=assignments,
            confirmations=confirmations,
            reconciliations=reconciliations,
            expected_version=expected_workspace_version,
        )
        if not validation.is_valid:
            if any(issue.code == "OO305" for issue in validation.issues):
                raise OperationalOrderPromotionVersionConflictError(
                    "Workspace version conflict during promotion."
                )
            raise OperationalOrderPromotionNotReadyError("Promotion preconditions are not satisfied.")

        ws_version = int(workspace["version"])
        ws_fp = workspace_fingerprint(
            workspace_version=ws_version,
            blocks=blocks,
            reconciliations=reconciliations,
        )
        localization_rows = _build_localization_rows(
            blocks=blocks,
            confirmations=confirmations,
            reconciliations=reconciliations,
        )
        if not localization_rows:
            raise OperationalOrderPromotionNotReadyError("No localization content available for snapshot.")
        snap_fp = snapshot_fingerprint(localization_rows)

        promotion_row = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_promotions (
                    workspace_id,
                    status,
                    workspace_version,
                    workspace_fingerprint,
                    snapshot_fingerprint,
                    snapshot_version,
                    promoted_by_user_id,
                    promoted_at,
                    metadata_json
                ) VALUES (
                    :workspace_id,
                    :status,
                    :workspace_version,
                    :workspace_fingerprint,
                    :snapshot_fingerprint,
                    :snapshot_version,
                    :promoted_by_user_id,
                    :promoted_at,
                    CAST(:metadata_json AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "status": PROMOTION_STATUS_STARTED,
                "workspace_version": ws_version,
                "workspace_fingerprint": ws_fp,
                "snapshot_fingerprint": snap_fp,
                "snapshot_version": 1,
                "promoted_by_user_id": int(actor_user_id),
                "promoted_at": None,
                "metadata_json": json.dumps(
                    json_safe(
                        {
                            "workspace_stage": str(workspace["stage"]),
                            "block_count": len(localization_rows),
                        }
                    )
                    or {}
                ),
            },
        ).fetchone()
        promotion_id = int(promotion_row[0])
        _append_promotion_audit(
            conn,
            promotion_id=promotion_id,
            action=PROMOTION_AUDIT_ACTION_STARTED,
            actor_user_id=actor_user_id,
            metadata={"workspace_id": workspace_id, "workspace_version": ws_version},
        )

        document_row = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_documents (
                    workspace_id,
                    document_kind,
                    status,
                    created_from_workspace_version,
                    created_from_workspace_fingerprint,
                    promotion_id,
                    created_by_user_id
                ) VALUES (
                    :workspace_id,
                    :document_kind,
                    :status,
                    :created_from_workspace_version,
                    :created_from_workspace_fingerprint,
                    :promotion_id,
                    :created_by_user_id
                )
                RETURNING id
                """
            ),
            {
                "workspace_id": int(workspace_id),
                "document_kind": DOCUMENT_KIND_OPERATIONAL_ORDER,
                "status": DOCUMENT_STATUS_CREATED,
                "created_from_workspace_version": ws_version,
                "created_from_workspace_fingerprint": ws_fp,
                "promotion_id": promotion_id,
                "created_by_user_id": int(actor_user_id),
            },
        ).fetchone()
        document_id = int(document_row[0])
        _append_promotion_audit(
            conn,
            promotion_id=promotion_id,
            action=PROMOTION_AUDIT_ACTION_DOCUMENT_CREATED,
            actor_user_id=actor_user_id,
            metadata={"document_id": document_id},
        )

        version_row = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_document_versions (
                    document_id,
                    version_number,
                    workspace_version,
                    promotion_snapshot_version,
                    snapshot_fingerprint,
                    is_current,
                    created_by_user_id
                ) VALUES (
                    :document_id,
                    :version_number,
                    :workspace_version,
                    :promotion_snapshot_version,
                    :snapshot_fingerprint,
                    TRUE,
                    :created_by_user_id
                )
                RETURNING id
                """
            ),
            {
                "document_id": document_id,
                "version_number": 1,
                "workspace_version": ws_version,
                "promotion_snapshot_version": 1,
                "snapshot_fingerprint": snap_fp,
                "created_by_user_id": int(actor_user_id),
            },
        ).fetchone()
        document_version_id = int(version_row[0])
        _append_promotion_audit(
            conn,
            promotion_id=promotion_id,
            action=PROMOTION_AUDIT_ACTION_VERSION_CREATED,
            actor_user_id=actor_user_id,
            metadata={"document_version_id": document_version_id, "version_number": 1},
        )

        representative_block = next(
            (row for row in localization_rows if row["block_type"] == "TITLE"),
            localization_rows[0],
        )
        _append_workspace_provenance(
            conn,
            workspace_id=workspace_id,
            draft_block_id=int(representative_block["source_block_id"]),
            locale=str(representative_block["locale"]),
            action=PROVENANCE_ACTION_PROMOTED_FROM_WORKSPACE,
            actor_user_id=actor_user_id,
            text_value=str(representative_block["official_text"]),
            metadata={"document_id": document_id, "promotion_id": promotion_id},
        )
        _append_workspace_provenance(
            conn,
            workspace_id=workspace_id,
            draft_block_id=int(representative_block["source_block_id"]),
            locale=str(representative_block["locale"]),
            action=PROVENANCE_ACTION_DOCUMENT_VERSION_CREATED,
            actor_user_id=actor_user_id,
            text_value=str(representative_block["official_text"]),
            metadata={
                "document_id": document_id,
                "document_version_id": document_version_id,
                "version_number": 1,
            },
        )

        for row in localization_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO public.operational_order_document_localizations (
                        document_version_id,
                        locale,
                        block_type,
                        sequence,
                        official_text,
                        content_fingerprint,
                        source_workspace_block_version,
                        source_confirmation_ids,
                        source_reconciliation_id
                    ) VALUES (
                        :document_version_id,
                        :locale,
                        :block_type,
                        :sequence,
                        :official_text,
                        :content_fingerprint,
                        :source_workspace_block_version,
                        CAST(:source_confirmation_ids AS jsonb),
                        :source_reconciliation_id
                    )
                    """
                ),
                {
                    "document_version_id": document_version_id,
                    "locale": row["locale"],
                    "block_type": row["block_type"],
                    "sequence": row["sequence"],
                    "official_text": row["official_text"],
                    "content_fingerprint": row["content_fingerprint"],
                    "source_workspace_block_version": row["source_workspace_block_version"],
                    "source_confirmation_ids": json.dumps(row["source_confirmation_ids"]),
                    "source_reconciliation_id": row["source_reconciliation_id"],
                },
            )
            _append_workspace_provenance(
                conn,
                workspace_id=workspace_id,
                draft_block_id=int(row["source_block_id"]),
                locale=str(row["locale"]),
                action=PROVENANCE_ACTION_SNAPSHOT_CREATED,
                actor_user_id=actor_user_id,
                text_value=str(row["official_text"]),
                metadata={
                    "document_id": document_id,
                    "document_version_id": document_version_id,
                    "block_type": row["block_type"],
                    "sequence": row["sequence"],
                },
            )

        _append_promotion_audit(
            conn,
            promotion_id=promotion_id,
            action=PROMOTION_AUDIT_ACTION_LOCALIZATION_SNAPSHOTTED,
            actor_user_id=actor_user_id,
            metadata={"localization_count": len(localization_rows)},
        )

        conn.execute(
            text(
                """
                UPDATE public.operational_order_promotions
                SET status = :status,
                    document_id = :document_id,
                    promoted_at = :promoted_at,
                    snapshot_fingerprint = :snapshot_fingerprint
                WHERE id = :promotion_id
                """
            ),
            {
                "promotion_id": promotion_id,
                "status": PROMOTION_STATUS_COMPLETED,
                "document_id": document_id,
                "promoted_at": _utcnow(),
                "snapshot_fingerprint": snap_fp,
            },
        )
        _append_promotion_audit(
            conn,
            promotion_id=promotion_id,
            action=PROMOTION_AUDIT_ACTION_COMPLETED,
            actor_user_id=actor_user_id,
            metadata={"document_id": document_id, "snapshot_fingerprint": snap_fp},
        )

        previous_stage = str(workspace.get("stage") or WORKSPACE_STAGE_EDITORIAL_PACKAGE_READY)
        freeze_workspace(
            conn,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            document_id=document_id,
            promotion_id=promotion_id,
            representative_block_id=int(representative_block["source_block_id"]),
            representative_locale=str(representative_block["locale"]),
            representative_text=str(representative_block["official_text"]),
            previous_stage=previous_stage,
        )
        _append_promotion_audit(
            conn,
            promotion_id=promotion_id,
            action=PROMOTION_AUDIT_ACTION_WORKSPACE_FROZEN,
            actor_user_id=actor_user_id,
            metadata={"document_id": document_id, "stage": WORKSPACE_STAGE_DOCUMENT_PROMOTED},
        )

        return _promotion_result_payload(
            workspace_id=int(workspace_id),
            document_detail=_build_document_detail(conn, document_id),
            validation=validation,
            idempotent_replay=False,
            workspace_frozen=True,
            workspace_drift_detected=False,
            revision_recommended=False,
        )


def get_document(*, document_id: int) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        return _build_document_detail(conn, document_id)


def list_documents(
    *,
    status: str | None = None,
    workspace_id: int | None = None,
    submitting_org_unit_id: int | None = None,
    scope_unit_ids: list[int] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    _require_available()
    clauses = ["1=1"]
    params: dict[str, Any] = {
        "limit": max(1, min(int(limit), 200)),
        "offset": max(0, int(offset)),
    }
    if status:
        clauses.append("d.status = :status")
        params["status"] = str(status).strip().upper()
    if workspace_id is not None:
        clauses.append("d.workspace_id = :workspace_id")
        params["workspace_id"] = int(workspace_id)
    if submitting_org_unit_id is not None:
        clauses.append("w.submitting_org_unit_id = :submitting_org_unit_id")
        params["submitting_org_unit_id"] = int(submitting_org_unit_id)
    if scope_unit_ids is not None:
        if not scope_unit_ids:
            return {"items": [], "total": 0, "limit": params["limit"], "offset": params["offset"]}
        clauses.append("w.submitting_org_unit_id = ANY(:scope_unit_ids)")
        params["scope_unit_ids"] = [int(unit_id) for unit_id in scope_unit_ids]

    where_sql = " AND ".join(clauses)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT d.*, w.submitting_org_unit_id
                FROM public.operational_order_documents d
                JOIN public.operational_order_draft_workspaces w
                  ON w.workspace_id = d.workspace_id
                WHERE {where_sql}
                ORDER BY d.created_at DESC, d.id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()
        total = conn.execute(
            text(
                f"""
                SELECT COUNT(1)
                FROM public.operational_order_documents d
                JOIN public.operational_order_draft_workspaces w
                  ON w.workspace_id = d.workspace_id
                WHERE {where_sql}
                """
            ),
            params,
        ).scalar()
    return {
        "items": [_document_summary(dict(row)) for row in rows],
        "total": int(total or 0),
        "limit": params["limit"],
        "offset": params["offset"],
    }


def list_document_versions(*, document_id: int) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        document = _fetch_document(conn, document_id)
        if not document:
            raise OperationalOrderDocumentNotFoundError(f"Document {document_id} not found.")
        rows = conn.execute(
            text(
                """
                SELECT *
                FROM public.operational_order_document_versions
                WHERE document_id = :document_id
                ORDER BY version_number
                """
            ),
            {"document_id": int(document_id)},
        ).mappings().all()
        return {
            "document": _document_summary(document),
            "items": [dict(row) for row in rows],
        }


def get_document_version(*, document_id: int, version_number: int) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        document = _fetch_document(conn, document_id)
        if not document:
            raise OperationalOrderDocumentNotFoundError(f"Document {document_id} not found.")
        version = _fetch_version(conn, document_id, version_number)
        if not version:
            raise OperationalOrderDocumentVersionNotFoundError(
                f"Document version {version_number} not found."
            )
        localizations = _fetch_localizations(conn, int(version["id"]))
        return {
            "document": _document_summary(document),
            "version": dict(version),
            "localizations": localizations,
        }


def list_document_localizations(
    *,
    document_id: int,
    version_number: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        document = _fetch_document(conn, document_id)
        if not document:
            raise OperationalOrderDocumentNotFoundError(f"Document {document_id} not found.")
        if version_number is None:
            version = _fetch_current_version(conn, document_id)
        else:
            version = _fetch_version(conn, document_id, version_number)
        if not version:
            raise OperationalOrderDocumentVersionNotFoundError("Document version not found.")
        localizations = _fetch_localizations(conn, int(version["id"]))
        return {
            "document_id": int(document_id),
            "version_number": int(version["version_number"]),
            "items": localizations,
        }


def validate_promotion_command(
    *,
    workspace_id: int,
    expected_workspace_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        workspace = fetch_workspace_row(conn, workspace_id)
        if not workspace:
            raise OperationalOrderWorkspaceNotFoundError(f"Workspace {workspace_id} not found.")
        existing_document = _fetch_document_by_workspace(conn, workspace_id)
        blocks = intake_svc._fetch_blocks(conn, workspace_id)
        clarifications = intake_svc._fetch_clarifications(conn, workspace_id)
        assignments = editorial_svc._fetch_assignments(conn, workspace_id)
        confirmations = editorial_svc._fetch_confirmations(conn, workspace_id)
        reconciliations = editorial_svc._fetch_reconciliations(conn, workspace_id)
        validation = validate_promotion(
            workspace=workspace,
            blocks=blocks,
            clarifications=clarifications,
            assignments=assignments,
            confirmations=confirmations,
            reconciliations=reconciliations,
            expected_version=expected_workspace_version,
            existing_document=existing_document,
        )
        return {"workspace_id": workspace_id, "validation": validation}
