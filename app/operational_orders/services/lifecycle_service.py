"""Document lifecycle service — CREATED → READY_FOR_SIGNATURE (OO-IMP-004)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.operational_orders import (
    DOCUMENT_STATUS_CREATED,
    DOCUMENT_STATUS_READY_FOR_SIGNATURE,
    LIFECYCLE_AUDIT_ACTION_DOCUMENT_READY_FOR_SIGNATURE,
    LIFECYCLE_AUDIT_ACTION_DOCUMENT_RETURNED_TO_CREATED,
    LIFECYCLE_AUDIT_ACTION_SIGNATURE_READINESS_FAILED,
    LIFECYCLE_AUDIT_ACTION_SIGNATURE_READINESS_VALIDATED,
    LIFECYCLE_AUDIT_ACTION_SIGNING_AUTHORITY_ASSIGNED,
    LIFECYCLE_AUDIT_ACTION_SIGNING_AUTHORITY_SUPERSEDED,
    PARTY_REFERENCE_TYPES,
    SIGNING_AUTHORITY_STATUS_ACTIVE,
    SIGNING_AUTHORITY_STATUS_SUPERSEDED,
)
from app.document_engine import ValidationResult
from app.document_engine.lifecycle.lifecycle_rules import LifecycleRules
from app.document_engine.value_objects.lifecycle import DocumentLifecycleState
from app.operational_orders.domain import json_safe, normalize_party_reference
from app.operational_orders.errors import (
    OperationalOrderDocumentAlreadyReadyError,
    OperationalOrderDocumentNotFoundError,
    OperationalOrderDocumentNotReadyError,
    OperationalOrderDocumentStatusConflictError,
    OperationalOrderDocumentVersionConflictError,
    OperationalOrderLifecycleTransitionForbiddenError,
    OperationalOrderSigningAuthorityConflictError,
    OperationalOrderSigningAuthorityInvalidError,
    OperationalOrderValidationBlockedError,
    OperationalOrderValidationError,
)
from app.operational_orders.repository import fetch_workspace_row, lifecycle_available
from app.operational_orders.services import draft_intake_service as intake_svc
from app.operational_orders.services import editorial_workflow_service as editorial_svc
from app.operational_orders.services import promotion_service as promotion_svc
from app.operational_orders.services.workspace_drift_detector import detect_workspace_drift
from app.operational_orders.validation.signature_readiness_validation import (
    validate_signature_readiness,
)


def _require_available() -> None:
    if not lifecycle_available():
        raise OperationalOrderValidationError("Operational orders lifecycle schema is not available.")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _map_oo_status_to_ude(status: str) -> DocumentLifecycleState:
    if status == DOCUMENT_STATUS_CREATED:
        return DocumentLifecycleState.DRAFT
    return DocumentLifecycleState(str(status))


def _append_lifecycle_audit(
    conn,
    *,
    document_id: int,
    action: str,
    actor_user_id: int | None,
    document_version_id: int | None = None,
    transition_from: str | None = None,
    transition_to: str | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    document_version_before: int | None = None,
    document_version_after: int | None = None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.operational_order_lifecycle_audit (
                document_id,
                document_version_id,
                transition_from,
                transition_to,
                action,
                actor_user_id,
                reason,
                metadata_json,
                document_version_before,
                document_version_after
            ) VALUES (
                :document_id,
                :document_version_id,
                :transition_from,
                :transition_to,
                :action,
                :actor_user_id,
                :reason,
                CAST(:metadata_json AS jsonb),
                :document_version_before,
                :document_version_after
            )
            """
        ),
        {
            "document_id": int(document_id),
            "document_version_id": document_version_id,
            "transition_from": transition_from,
            "transition_to": transition_to,
            "action": action,
            "actor_user_id": actor_user_id,
            "reason": reason,
            "metadata_json": json.dumps(json_safe(metadata) or {}),
            "document_version_before": document_version_before,
            "document_version_after": document_version_after,
        },
    )


def _fetch_active_signing_authority(conn, document_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_signing_authority
            WHERE document_id = :document_id AND status = :status
            ORDER BY assigned_at DESC
            LIMIT 1
            """
        ),
        {"document_id": int(document_id), "status": SIGNING_AUTHORITY_STATUS_ACTIVE},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_latest_lifecycle_audit(conn, document_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_lifecycle_audit
            WHERE document_id = :document_id
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ),
        {"document_id": int(document_id)},
    ).mappings().first()
    return dict(row) if row else None


def _load_document_context(conn, document_id: int) -> dict[str, Any]:
    document = conn.execute(
        text(
            """
            SELECT d.*, w.submitting_org_unit_id, w.stage AS workspace_stage
            FROM public.operational_order_documents d
            JOIN public.operational_order_draft_workspaces w
              ON w.workspace_id = d.workspace_id
            WHERE d.id = :document_id
            """
        ),
        {"document_id": int(document_id)},
    ).mappings().first()
    if not document:
        raise OperationalOrderDocumentNotFoundError(f"Document {document_id} not found.")
    document = dict(document)

    current_versions = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_document_versions
            WHERE document_id = :document_id AND is_current = TRUE
            """
        ),
        {"document_id": int(document_id)},
    ).mappings().all()
    current_versions = [dict(row) for row in current_versions]

    current_version = current_versions[0] if len(current_versions) == 1 else None
    localizations: list[dict[str, Any]] = []
    if current_version is not None:
        localizations = [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    SELECT *
                    FROM public.operational_order_document_localizations
                    WHERE document_version_id = :document_version_id
                    ORDER BY locale, block_type, sequence
                    """
                ),
                {"document_version_id": int(current_version["id"])},
            ).mappings().all()
        ]

    promotion = conn.execute(
        text(
            """
            SELECT *
            FROM public.operational_order_promotions
            WHERE id = :promotion_id
            """
        ),
        {"promotion_id": int(document["promotion_id"])},
    ).mappings().first()
    promotion = dict(promotion) if promotion else None

    workspace = fetch_workspace_row(conn, int(document["workspace_id"]))
    blocks = intake_svc._fetch_blocks(conn, int(document["workspace_id"]))
    reconciliations = editorial_svc._fetch_reconciliations(conn, int(document["workspace_id"]))

    drift = {"workspace_drift_detected": False, "revision_recommended": False}
    if promotion is not None and workspace is not None:
        drift = detect_workspace_drift(
            workspace=workspace,
            blocks=blocks,
            reconciliations=reconciliations,
            promotion_workspace_fingerprint=str(promotion.get("workspace_fingerprint") or ""),
        )

    signing_authority = _fetch_active_signing_authority(conn, document_id)

    return {
        "document": document,
        "current_versions": current_versions,
        "current_version": current_version,
        "localizations": localizations,
        "promotion": promotion,
        "workspace": workspace,
        "signing_authority": signing_authority,
        "workspace_drift_detected": bool(drift.get("workspace_drift_detected")),
        "revision_recommended": bool(drift.get("revision_recommended")),
    }


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


def _signing_authority_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "document_id": int(row["document_id"]),
        "document_version_id": int(row["document_version_id"]),
        "authority_party_type": str(row["authority_party_type"]),
        "authority_party_reference": str(row["authority_party_reference"]),
        "authority_display_name": row.get("authority_display_name"),
        "authority_position_id": row.get("authority_position_id"),
        "authority_org_unit_id": row.get("authority_org_unit_id"),
        "authority_basis": row.get("authority_basis"),
        "assigned_by_user_id": int(row["assigned_by_user_id"]),
        "status": str(row["status"]),
        "assigned_at": row["assigned_at"],
        "superseded_at": row.get("superseded_at"),
        "version": int(row["version"]),
    }


def _lifecycle_audit_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "document_id": int(row["document_id"]),
        "document_version_id": row.get("document_version_id"),
        "transition_from": row.get("transition_from"),
        "transition_to": row.get("transition_to"),
        "action": str(row["action"]),
        "actor_user_id": row.get("actor_user_id"),
        "reason": row.get("reason"),
        "created_at": row["created_at"],
        "document_version_before": row.get("document_version_before"),
        "document_version_after": row.get("document_version_after"),
    }


def _build_document_detail(conn, document_id: int) -> dict[str, Any]:
    ctx = _load_document_context(conn, document_id)
    document = ctx["document"]
    promotion_detail = promotion_svc._build_document_detail(conn, document_id)
    latest_audit = _fetch_latest_lifecycle_audit(conn, document_id)
    validation = validate_signature_readiness(
        document=document,
        current_versions=ctx["current_versions"],
        localizations=ctx["localizations"],
        promotion=ctx["promotion"],
        workspace=ctx["workspace"],
        signing_authority=ctx["signing_authority"],
        workspace_drift_detected=ctx["workspace_drift_detected"],
        for_mark_ready=False,
    )
    return {
        "document": _document_summary(document),
        "current_version": promotion_detail.get("current_version"),
        "promotion": promotion_detail.get("promotion"),
        "signing_authority": _signing_authority_summary(ctx["signing_authority"]),
        "readiness_validation": validation,
        "latest_lifecycle_transition": _lifecycle_audit_summary(latest_audit),
        "org_scope_source": {
            "submitting_org_unit_id": int(document.get("submitting_org_unit_id") or 0) or None,
            "workspace_id": int(document["workspace_id"]),
        },
        "workspace_drift_detected": ctx["workspace_drift_detected"],
        "revision_recommended": ctx["revision_recommended"],
    }


def _assert_document_version(
    document: dict[str, Any],
    expected_document_version: int | None,
) -> None:
    if expected_document_version is None:
        return
    if int(document.get("version") or 0) != int(expected_document_version):
        raise OperationalOrderDocumentVersionConflictError("Document aggregate version conflict.")


def _validate_org_unit_exists(conn, org_unit_id: int) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM public.org_units
            WHERE unit_id = :unit_id
            LIMIT 1
            """
        ),
        {"unit_id": int(org_unit_id)},
    ).first()
    return row is not None


def _validate_position_exists(conn, position_id: int) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM public.positions
            WHERE position_id = :position_id
            LIMIT 1
            """
        ),
        {"position_id": int(position_id)},
    ).first()
    return row is not None


def get_document_detail(*, document_id: int) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        return _build_document_detail(conn, document_id)


def get_signature_readiness(*, document_id: int) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        ctx = _load_document_context(conn, document_id)
        validation = validate_signature_readiness(
            document=ctx["document"],
            current_versions=ctx["current_versions"],
            localizations=ctx["localizations"],
            promotion=ctx["promotion"],
            workspace=ctx["workspace"],
            signing_authority=ctx["signing_authority"],
            workspace_drift_detected=ctx["workspace_drift_detected"],
            for_mark_ready=False,
        )
        return {
            "document_id": int(document_id),
            "status": str(ctx["document"]["status"]),
            "aggregate_version": int(ctx["document"]["version"]),
            "signing_authority": _signing_authority_summary(ctx["signing_authority"]),
            "readiness_validation": validation,
            "workspace_drift_detected": ctx["workspace_drift_detected"],
            "revision_recommended": ctx["revision_recommended"],
        }


def get_signing_authority(*, document_id: int) -> dict[str, Any]:
    _require_available()
    with engine.connect() as conn:
        ctx = _load_document_context(conn, document_id)
        return {
            "document_id": int(document_id),
            "signing_authority": _signing_authority_summary(ctx["signing_authority"]),
        }


def validate_ready_for_signature_command(
    *,
    document_id: int,
    expected_document_version: int | None = None,
    actor_user_id: int | None = None,
    record_audit: bool = False,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        ctx = _load_document_context(conn, document_id)
        document = ctx["document"]
        validation = validate_signature_readiness(
            document=document,
            current_versions=ctx["current_versions"],
            localizations=ctx["localizations"],
            promotion=ctx["promotion"],
            workspace=ctx["workspace"],
            signing_authority=ctx["signing_authority"],
            expected_document_version=expected_document_version,
            workspace_drift_detected=ctx["workspace_drift_detected"],
            for_mark_ready=False,
        )
        if record_audit and actor_user_id is not None:
            action = (
                LIFECYCLE_AUDIT_ACTION_SIGNATURE_READINESS_VALIDATED
                if validation.is_valid
                else LIFECYCLE_AUDIT_ACTION_SIGNATURE_READINESS_FAILED
            )
            _append_lifecycle_audit(
                conn,
                document_id=document_id,
                document_version_id=int(ctx["current_version"]["id"])
                if ctx["current_version"]
                else None,
                action=action,
                actor_user_id=actor_user_id,
                metadata={"issue_codes": [issue.code for issue in validation.issues]},
            )
        return {
            "document_id": int(document_id),
            "status": str(document["status"]),
            "aggregate_version": int(document["version"]),
            "validation": validation,
            "signing_authority": _signing_authority_summary(ctx["signing_authority"]),
        }


def assign_signing_authority(
    *,
    document_id: int,
    authority_party_type: str,
    authority_party_reference: str,
    authority_display_name: str | None,
    authority_position_id: int | None,
    authority_org_unit_id: int | None,
    authority_basis: str | None,
    assigned_by_user_id: int,
    expected_document_version: int | None = None,
    scope_unit_ids: set[int] | None = None,
) -> dict[str, Any]:
    _require_available()
    party = normalize_party_reference(
        reference_type=authority_party_type,
        reference=authority_party_reference,
        display_name=authority_display_name,
    )
    if party.reference_type.value not in PARTY_REFERENCE_TYPES:
        raise OperationalOrderSigningAuthorityInvalidError("Invalid authority party type.")

    with engine.begin() as conn:
        ctx = _load_document_context(conn, document_id)
        document = ctx["document"]
        _assert_document_version(document, expected_document_version)

        if str(document["status"]) not in {
            DOCUMENT_STATUS_CREATED,
            DOCUMENT_STATUS_READY_FOR_SIGNATURE,
        }:
            raise OperationalOrderDocumentStatusConflictError(
                "Signing authority can only be assigned while document is CREATED or READY_FOR_SIGNATURE."
            )

        current_version = ctx["current_version"]
        if current_version is None:
            raise OperationalOrderSigningAuthorityInvalidError("Current document version is missing.")
        if int(current_version.get("document_id") or 0) != int(document_id):
            raise OperationalOrderSigningAuthorityInvalidError(
                "Current document version does not belong to document."
            )

        if authority_org_unit_id is not None:
            if not _validate_org_unit_exists(conn, int(authority_org_unit_id)):
                raise OperationalOrderSigningAuthorityInvalidError("Authority org unit does not exist.")
            if scope_unit_ids is not None and int(authority_org_unit_id) not in scope_unit_ids:
                raise OperationalOrderSigningAuthorityInvalidError(
                    "Authority org unit is outside permitted scope."
                )

        if authority_position_id is not None and not _validate_position_exists(
            conn, int(authority_position_id)
        ):
            raise OperationalOrderSigningAuthorityInvalidError("Authority position does not exist.")

        active = ctx["signing_authority"]
        if active is not None:
            same_assignment = (
                str(active["authority_party_type"]) == party.reference_type.value
                and str(active["authority_party_reference"]) == party.reference
                and (active.get("authority_position_id") or None)
                == (int(authority_position_id) if authority_position_id is not None else None)
                and (active.get("authority_org_unit_id") or None)
                == (int(authority_org_unit_id) if authority_org_unit_id is not None else None)
                and (active.get("authority_basis") or None) == (authority_basis or None)
            )
            if same_assignment:
                return {
                    "document_id": int(document_id),
                    "signing_authority": _signing_authority_summary(active),
                    "document": _document_summary(document),
                    "idempotent_replay": True,
                }
            now = _utcnow()
            conn.execute(
                text(
                    """
                    UPDATE public.operational_order_signing_authority
                    SET status = :status, superseded_at = :superseded_at
                    WHERE id = :id
                    """
                ),
                {
                    "id": int(active["id"]),
                    "status": SIGNING_AUTHORITY_STATUS_SUPERSEDED,
                    "superseded_at": now,
                },
            )
            _append_lifecycle_audit(
                conn,
                document_id=document_id,
                document_version_id=int(current_version["id"]),
                action=LIFECYCLE_AUDIT_ACTION_SIGNING_AUTHORITY_SUPERSEDED,
                actor_user_id=assigned_by_user_id,
                metadata={"superseded_authority_id": int(active["id"])},
                document_version_before=int(document["version"]),
                document_version_after=int(document["version"]),
            )

        new_version = int(document["version"]) + 1
        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_documents
                SET version = :new_version
                WHERE id = :document_id AND version = :expected_version
                RETURNING *
                """
            ),
            {
                "document_id": int(document_id),
                "new_version": new_version,
                "expected_version": int(document["version"]),
            },
        ).mappings().first()
        if not updated:
            raise OperationalOrderDocumentVersionConflictError("Document aggregate version conflict.")

        inserted = conn.execute(
            text(
                """
                INSERT INTO public.operational_order_signing_authority (
                    document_id,
                    document_version_id,
                    authority_party_type,
                    authority_party_reference,
                    authority_display_name,
                    authority_position_id,
                    authority_org_unit_id,
                    authority_basis,
                    assigned_by_user_id,
                    status,
                    assigned_at,
                    version
                ) VALUES (
                    :document_id,
                    :document_version_id,
                    :authority_party_type,
                    :authority_party_reference,
                    :authority_display_name,
                    :authority_position_id,
                    :authority_org_unit_id,
                    :authority_basis,
                    :assigned_by_user_id,
                    :status,
                    :assigned_at,
                    :version
                )
                RETURNING *
                """
            ),
            {
                "document_id": int(document_id),
                "document_version_id": int(current_version["id"]),
                "authority_party_type": party.reference_type.value,
                "authority_party_reference": party.reference,
                "authority_display_name": party.display_name,
                "authority_position_id": authority_position_id,
                "authority_org_unit_id": authority_org_unit_id,
                "authority_basis": authority_basis,
                "assigned_by_user_id": int(assigned_by_user_id),
                "status": SIGNING_AUTHORITY_STATUS_ACTIVE,
                "assigned_at": _utcnow(),
                "version": 1,
            },
        ).mappings().first()
        authority = dict(inserted)

        _append_lifecycle_audit(
            conn,
            document_id=document_id,
            document_version_id=int(current_version["id"]),
            action=LIFECYCLE_AUDIT_ACTION_SIGNING_AUTHORITY_ASSIGNED,
            actor_user_id=assigned_by_user_id,
            metadata={"signing_authority_id": int(authority["id"])},
            document_version_before=int(document["version"]),
            document_version_after=new_version,
        )

        updated_document = dict(updated)
        updated_document["submitting_org_unit_id"] = document.get("submitting_org_unit_id")
        return {
            "document_id": int(document_id),
            "signing_authority": _signing_authority_summary(authority),
            "document": _document_summary(updated_document),
            "idempotent_replay": False,
        }


def mark_ready_for_signature(
    *,
    document_id: int,
    actor_user_id: int,
    expected_document_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    with engine.begin() as conn:
        ctx = _load_document_context(conn, document_id)
        document = ctx["document"]
        current_version = ctx["current_version"]
        status = str(document["status"])

        if status == DOCUMENT_STATUS_READY_FOR_SIGNATURE:
            _assert_document_version(document, expected_document_version)
            validation = validate_signature_readiness(
                document=document,
                current_versions=ctx["current_versions"],
                localizations=ctx["localizations"],
                promotion=ctx["promotion"],
                workspace=ctx["workspace"],
                signing_authority=ctx["signing_authority"],
                expected_document_version=expected_document_version,
                workspace_drift_detected=ctx["workspace_drift_detected"],
                for_mark_ready=False,
            )
            if validation.is_valid:
                return {
                    "document": _build_document_detail(conn, document_id),
                    "validation": validation,
                    "idempotent_replay": True,
                }
            raise OperationalOrderDocumentAlreadyReadyError(
                "Document is already ready for signature but readiness state is inconsistent."
            )

        if status != DOCUMENT_STATUS_CREATED:
            raise OperationalOrderDocumentStatusConflictError(
                "Document must be in CREATED status to mark ready for signature."
            )

        _assert_document_version(document, expected_document_version)

        ude_current = _map_oo_status_to_ude(status)
        transition = LifecycleRules.evaluate_transition(
            ude_current,
            DocumentLifecycleState.READY_FOR_SIGNATURE,
            gate_ready=True,
        )
        if not transition.allowed:
            raise OperationalOrderLifecycleTransitionForbiddenError(
                "Lifecycle transition to READY_FOR_SIGNATURE is forbidden."
            )

        validation = validate_signature_readiness(
            document=document,
            current_versions=ctx["current_versions"],
            localizations=ctx["localizations"],
            promotion=ctx["promotion"],
            workspace=ctx["workspace"],
            signing_authority=ctx["signing_authority"],
            expected_document_version=expected_document_version,
            workspace_drift_detected=ctx["workspace_drift_detected"],
            for_mark_ready=True,
        )
        if not validation.is_valid:
            raise OperationalOrderValidationBlockedError("Signature readiness validation failed.")

        new_version = int(document["version"]) + 1
        now = _utcnow()
        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_documents
                SET status = :status,
                    version = :new_version,
                    ready_for_signature_at = :ready_at,
                    ready_for_signature_by_user_id = :ready_by
                WHERE id = :document_id AND version = :expected_version
                RETURNING *
                """
            ),
            {
                "document_id": int(document_id),
                "status": DOCUMENT_STATUS_READY_FOR_SIGNATURE,
                "new_version": new_version,
                "ready_at": now,
                "ready_by": int(actor_user_id),
                "expected_version": int(document["version"]),
            },
        ).mappings().first()
        if not updated:
            raise OperationalOrderDocumentVersionConflictError("Document aggregate version conflict.")

        _append_lifecycle_audit(
            conn,
            document_id=document_id,
            document_version_id=int(current_version["id"]) if current_version else None,
            transition_from=DOCUMENT_STATUS_CREATED,
            transition_to=DOCUMENT_STATUS_READY_FOR_SIGNATURE,
            action=LIFECYCLE_AUDIT_ACTION_DOCUMENT_READY_FOR_SIGNATURE,
            actor_user_id=actor_user_id,
            document_version_before=int(document["version"]),
            document_version_after=new_version,
        )

        return {
            "document": _build_document_detail(conn, document_id),
            "validation": validation,
            "idempotent_replay": False,
        }


def return_to_created(
    *,
    document_id: int,
    actor_user_id: int,
    reason: str,
    expected_document_version: int | None = None,
) -> dict[str, Any]:
    _require_available()
    reason_text = str(reason or "").strip()
    if not reason_text:
        raise OperationalOrderValidationError("Return reason is required.")

    with engine.begin() as conn:
        ctx = _load_document_context(conn, document_id)
        document = ctx["document"]
        current_version = ctx["current_version"]
        status = str(document["status"])

        if status == DOCUMENT_STATUS_CREATED:
            _assert_document_version(document, expected_document_version)
            return {
                "document": _build_document_detail(conn, document_id),
                "idempotent_replay": True,
            }

        if status != DOCUMENT_STATUS_READY_FOR_SIGNATURE:
            raise OperationalOrderLifecycleTransitionForbiddenError(
                "Only READY_FOR_SIGNATURE documents can be returned to CREATED."
            )

        ude_current = _map_oo_status_to_ude(status)
        transition = LifecycleRules.evaluate_transition(
            ude_current,
            DocumentLifecycleState.DRAFT,
            gate_ready=True,
            reason=reason_text,
        )
        if not transition.allowed:
            raise OperationalOrderLifecycleTransitionForbiddenError(
                "Lifecycle transition to CREATED is forbidden."
            )

        _assert_document_version(document, expected_document_version)
        new_version = int(document["version"]) + 1
        updated = conn.execute(
            text(
                """
                UPDATE public.operational_order_documents
                SET status = :status,
                    version = :new_version,
                    ready_for_signature_at = NULL,
                    ready_for_signature_by_user_id = NULL
                WHERE id = :document_id AND version = :expected_version
                RETURNING *
                """
            ),
            {
                "document_id": int(document_id),
                "status": DOCUMENT_STATUS_CREATED,
                "new_version": new_version,
                "expected_version": int(document["version"]),
            },
        ).mappings().first()
        if not updated:
            raise OperationalOrderDocumentVersionConflictError("Document aggregate version conflict.")

        _append_lifecycle_audit(
            conn,
            document_id=document_id,
            document_version_id=int(current_version["id"]) if current_version else None,
            transition_from=DOCUMENT_STATUS_READY_FOR_SIGNATURE,
            transition_to=DOCUMENT_STATUS_CREATED,
            action=LIFECYCLE_AUDIT_ACTION_DOCUMENT_RETURNED_TO_CREATED,
            actor_user_id=actor_user_id,
            reason=reason_text,
            document_version_before=int(document["version"]),
            document_version_after=new_version,
        )

        return {
            "document": _build_document_detail(conn, document_id),
            "idempotent_replay": False,
        }


def assert_document_ready_for_read(*, document_id: int) -> dict[str, Any]:
    detail = get_document_detail(document_id=document_id)
    if str(detail["document"]["status"]) != DOCUMENT_STATUS_READY_FOR_SIGNATURE:
        raise OperationalOrderDocumentNotReadyError("Document is not ready for signature.")
    return detail
