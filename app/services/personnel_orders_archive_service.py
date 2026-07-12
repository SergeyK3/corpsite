"""Archive / restore commands for personnel orders (WP-PO-LC-DEL-005)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_orders import (
    LIFECYCLE_AUDIT_ACTION_ARCHIVE,
    LIFECYCLE_AUDIT_ACTION_RESTORE,
    ORDER_STATUS_REGISTERED,
    ORDER_STATUS_VOIDED,
)
from app.security.admin_permissions import has_admin_permission
from app.services.personnel_order_lifecycle_audit_service import (
    append_archive_order_audit,
    append_restore_order_audit,
)
from app.services.personnel_orders_query_service import (
    PersonnelOrderNotFoundError,
    PersonnelOrderValidationError,
    get_personnel_order,
    personnel_orders_available,
)

ARCHIVABLE_ORDER_STATUSES = {
    ORDER_STATUS_REGISTERED,
    ORDER_STATUS_VOIDED,
}

ARCHIVE_REASON_CODES = frozenset(
    {
        "completed",
        "voided_record",
        "migrated_legacy",
        "duplicate_reference",
        "other",
    }
)

ARCHIVE_REASON_LABELS = {
    "completed": "Lifecycle completed",
    "voided_record": "Voided record",
    "migrated_legacy": "Migrated legacy",
    "duplicate_reference": "Duplicate reference",
    "other": "Other",
}

PERMISSION_ARCHIVE = "PERSONNEL_ORDERS_ARCHIVE"
PERMISSION_RESTORE = "PERSONNEL_ORDERS_RESTORE"


class PersonnelOrderArchiveError(RuntimeError):
    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = str(code)


class PersonnelOrderArchivePermissionDeniedError(PersonnelOrderArchiveError):
    def __init__(self, message: str = "Archive permission denied."):
        super().__init__(message, code="ARCHIVE_PERMISSION_DENIED")


class PersonnelOrderRestorePermissionDeniedError(PersonnelOrderArchiveError):
    def __init__(self, message: str = "Restore permission denied."):
        super().__init__(message, code="RESTORE_PERMISSION_DENIED")


class PersonnelOrderNotArchivableError(PersonnelOrderArchiveError):
    def __init__(self, message: str):
        super().__init__(message, code="ORDER_NOT_ARCHIVABLE")


class PersonnelOrderAlreadyArchivedError(PersonnelOrderArchiveError):
    def __init__(self, message: str = "Order is already archived."):
        super().__init__(message, code="ORDER_ALREADY_ARCHIVED")


class PersonnelOrderNotArchivedError(PersonnelOrderArchiveError):
    def __init__(self, message: str = "Order is not archived."):
        super().__init__(message, code="ORDER_NOT_ARCHIVED")


class PersonnelOrderArchiveReasonError(PersonnelOrderArchiveError):
    def __init__(self, message: str):
        super().__init__(message, code="INVALID_ARCHIVE_REASON")


def _require_available() -> None:
    if not personnel_orders_available():
        raise PersonnelOrderValidationError("Personnel orders schema is not available.")


def _fetch_order_row_for_archive(conn, order_id: int) -> Dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
                order_id,
                status,
                void_kind,
                archived_at
            FROM public.personnel_orders
            WHERE order_id = :order_id
            """
        ),
        {"order_id": int(order_id)},
    ).mappings().first()
    if row is None:
        raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
    return dict(row)


def _normalize_archive_reason(*, reason_code: str, reason_text: Optional[str]) -> tuple[str, str, str]:
    normalized_code = str(reason_code or "").strip().lower()
    if normalized_code not in ARCHIVE_REASON_CODES:
        raise PersonnelOrderArchiveReasonError(
            f"Unsupported archive reason_code: {reason_code}"
        )

    normalized_text = str(reason_text or "").strip()
    if normalized_code == "other":
        if not normalized_text:
            raise PersonnelOrderArchiveReasonError("reason_text is required when reason_code is other.")
        if len(normalized_text) > 2000:
            raise PersonnelOrderArchiveReasonError("reason_text must be at most 2000 characters.")
    elif normalized_text and len(normalized_text) > 2000:
        raise PersonnelOrderArchiveReasonError("reason_text must be at most 2000 characters.")

    display_reason = normalized_text or ARCHIVE_REASON_LABELS[normalized_code]
    return normalized_code, normalized_text or None, display_reason


def _assert_archive_permission(*, actor_user_id: int) -> None:
    if not has_admin_permission(int(actor_user_id), PERMISSION_ARCHIVE):
        raise PersonnelOrderArchivePermissionDeniedError(
            "Archive requires PERSONNEL_ORDERS_ARCHIVE."
        )


def _assert_restore_permission(*, actor_user_id: int) -> None:
    if not has_admin_permission(int(actor_user_id), PERMISSION_RESTORE):
        raise PersonnelOrderRestorePermissionDeniedError(
            "Restore requires PERSONNEL_ORDERS_RESTORE."
        )


def archive_personnel_order(
    *,
    order_id: int,
    reason_code: str,
    reason_text: Optional[str],
    actor_user_id: int,
) -> Dict[str, Any]:
    """Archive a REGISTERED/VOIDED personnel order without changing lifecycle status."""
    _require_available()
    normalized_code, normalized_text, display_reason = _normalize_archive_reason(
        reason_code=reason_code,
        reason_text=reason_text,
    )

    with engine.begin() as conn:
        order = _fetch_order_row_for_archive(conn, int(order_id))
        status = str(order["status"])
        previous_void_kind = order.get("void_kind")

        if order.get("archived_at") is not None:
            raise PersonnelOrderAlreadyArchivedError(
                f"Personnel order {order_id} is already archived."
            )
        if status not in ARCHIVABLE_ORDER_STATUSES:
            raise PersonnelOrderNotArchivableError(
                f"Personnel order {order_id} cannot be archived from status {status}."
            )

        _assert_archive_permission(actor_user_id=int(actor_user_id))

        updated = conn.execute(
            text(
                """
                UPDATE public.personnel_orders
                SET archived_at = now(),
                    archived_by = :archived_by,
                    archive_reason_code = :archive_reason_code,
                    archive_reason_text = :archive_reason_text,
                    updated_at = now()
                WHERE order_id = :order_id
                  AND archived_at IS NULL
                RETURNING order_id
                """
            ),
            {
                "order_id": int(order_id),
                "archived_by": int(actor_user_id),
                "archive_reason_code": normalized_code,
                "archive_reason_text": normalized_text or display_reason,
            },
        ).first()
        if updated is None:
            raise PersonnelOrderAlreadyArchivedError(
                f"Personnel order {order_id} is already archived."
            )
        append_archive_order_audit(
            conn,
            order_id=int(order_id),
            previous_status=status,
            previous_void_kind=previous_void_kind,
            reason_code=normalized_code,
            reason_text=normalized_text or display_reason,
            actor_user_id=int(actor_user_id),
            metadata_json={
                "permission_used": PERMISSION_ARCHIVE,
                "display_reason": display_reason,
            },
        )

    return get_personnel_order(int(order_id))


def restore_personnel_order(
    *,
    order_id: int,
    actor_user_id: int,
) -> Dict[str, Any]:
    """Restore an archived personnel order by clearing archive fields only."""
    _require_available()

    with engine.begin() as conn:
        order = _fetch_order_row_for_archive(conn, int(order_id))
        status = str(order["status"])
        previous_void_kind = order.get("void_kind")

        if order.get("archived_at") is None:
            raise PersonnelOrderNotArchivedError(
                f"Personnel order {order_id} is not archived."
            )

        _assert_restore_permission(actor_user_id=int(actor_user_id))

        restored = conn.execute(
            text(
                """
                UPDATE public.personnel_orders
                SET archived_at = NULL,
                    archived_by = NULL,
                    archive_reason_code = NULL,
                    archive_reason_text = NULL,
                    updated_at = now()
                WHERE order_id = :order_id
                  AND archived_at IS NOT NULL
                RETURNING order_id
                """
            ),
            {"order_id": int(order_id)},
        ).first()
        if restored is None:
            raise PersonnelOrderNotArchivedError(
                f"Personnel order {order_id} is not archived."
            )
        append_restore_order_audit(
            conn,
            order_id=int(order_id),
            previous_status=status,
            previous_void_kind=previous_void_kind,
            actor_user_id=int(actor_user_id),
            metadata_json={"permission_used": PERMISSION_RESTORE},
        )

    return get_personnel_order(int(order_id))
