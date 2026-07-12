"""Cancel command for unregistered personnel orders (WP-PO-LC-DEL-004)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_orders import (
    ITEM_STATUS_ACTIVE,
    ORDER_STATUS_DRAFT,
    ORDER_STATUS_READY_FOR_SIGNATURE,
    ORDER_STATUS_VOIDED,
    VOID_KIND_CANCEL,
)
from app.security.admin_permissions import has_admin_permission
from app.services.personnel_order_archive_guard import assert_order_not_archived
from app.services.personnel_order_cancel_scope_service import evaluate_order_cancel_scope
from app.services.personnel_order_lifecycle_audit_service import append_cancel_order_audit
from app.services.personnel_orders_command_service import PersonnelOrderConflictError
from app.services.personnel_orders_query_service import (
    PersonnelOrderNotFoundError,
    PersonnelOrderValidationError,
    get_personnel_order,
    personnel_orders_available,
)
from app.services.personnel_orders_void_service import (
    PersonnelOrderAlreadyVoidedError,
    _fetch_items,
    _mark_item_voided,
    _mark_order_voided,
)

CANCELABLE_ORDER_STATUSES = {
    ORDER_STATUS_DRAFT,
    ORDER_STATUS_READY_FOR_SIGNATURE,
}

CANCEL_REASON_CODES = frozenset(
    {
        "duplicate",
        "created_by_mistake",
        "no_longer_required",
        "replaced_before_registration",
        "test_record",
        "other",
    }
)

CANCEL_REASON_LABELS = {
    "duplicate": "Duplicate order",
    "created_by_mistake": "Created by mistake",
    "no_longer_required": "No longer required",
    "replaced_before_registration": "Replaced before registration",
    "test_record": "Test record",
    "other": "Other",
}

PERMISSION_CANCEL_OWN = "PERSONNEL_ORDERS_CANCEL_OWN"
PERMISSION_CANCEL_SCOPE = "PERSONNEL_ORDERS_CANCEL_SCOPE"


class PersonnelOrderCancelError(RuntimeError):
    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = str(code)


class PersonnelOrderCancelPermissionDeniedError(PersonnelOrderCancelError):
    def __init__(self, message: str = "Cancel permission denied."):
        super().__init__(message, code="CANCEL_PERMISSION_DENIED")


class PersonnelOrderCancelScopeDeniedError(PersonnelOrderCancelError):
    def __init__(self, message: str = "Cancel scope denied."):
        super().__init__(message, code="CANCEL_SCOPE_DENIED")


class PersonnelOrderNotCancellableError(PersonnelOrderCancelError):
    def __init__(self, message: str):
        super().__init__(message, code="ORDER_NOT_CANCELLABLE")


class PersonnelOrderAlreadyAppliedCancelError(PersonnelOrderCancelError):
    def __init__(self, message: str = "Order already has approved employee events."):
        super().__init__(message, code="ORDER_ALREADY_APPLIED")


class PersonnelOrderCancelReasonError(PersonnelOrderCancelError):
    def __init__(self, message: str):
        super().__init__(message, code="INVALID_CANCEL_REASON")


def _require_available() -> None:
    if not personnel_orders_available():
        raise PersonnelOrderValidationError("Personnel orders schema is not available.")


def _fetch_order_row_for_cancel(conn, order_id: int) -> Dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
                order_id,
                order_number,
                order_date,
                order_type_code,
                status,
                source_mode,
                void_kind,
                archived_at,
                created_by
            FROM public.personnel_orders
            WHERE order_id = :order_id
            """
        ),
        {"order_id": int(order_id)},
    ).mappings().first()
    if row is None:
        raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
    return dict(row)


def _has_approved_employee_events(conn, order_id: int) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.employee_events
            WHERE order_id = :order_id
              AND lifecycle_status = 'APPROVED'
            LIMIT 1
            """
        ),
        {"order_id": int(order_id)},
    ).first()
    return row is not None


def _normalize_cancel_reason(*, reason_code: str, reason_text: Optional[str]) -> tuple[str, str, str]:
    normalized_code = str(reason_code or "").strip().lower()
    if normalized_code not in CANCEL_REASON_CODES:
        raise PersonnelOrderCancelReasonError(
            f"Unsupported cancel reason_code: {reason_code}"
        )

    normalized_text = str(reason_text or "").strip()
    if normalized_code == "other":
        if not normalized_text:
            raise PersonnelOrderCancelReasonError("reason_text is required when reason_code is other.")
        if len(normalized_text) > 2000:
            raise PersonnelOrderCancelReasonError("reason_text must be at most 2000 characters.")
    elif normalized_text and len(normalized_text) > 2000:
        raise PersonnelOrderCancelReasonError("reason_text must be at most 2000 characters.")

    void_reason = normalized_text or CANCEL_REASON_LABELS[normalized_code]
    return normalized_code, normalized_text or None, void_reason


def _assert_cancel_permission(
    conn,
    *,
    order: Dict[str, Any],
    actor_user_id: int,
) -> tuple[str, bool, str]:
    has_scope_permission = has_admin_permission(int(actor_user_id), PERMISSION_CANCEL_SCOPE)
    has_own_permission = has_admin_permission(int(actor_user_id), PERMISSION_CANCEL_OWN)
    is_owner = int(order["created_by"]) == int(actor_user_id)

    if has_scope_permission:
        in_scope, scope_rule = evaluate_order_cancel_scope(
            conn,
            order_id=int(order["order_id"]),
            created_by=int(order["created_by"]),
            actor_user_id=int(actor_user_id),
        )
        if in_scope:
            return PERMISSION_CANCEL_SCOPE, is_owner, scope_rule

    if has_own_permission:
        if not is_owner:
            if has_scope_permission:
                raise PersonnelOrderCancelScopeDeniedError(
                    f"Personnel order {order['order_id']} is outside actor cancel scope."
                )
            raise PersonnelOrderCancelPermissionDeniedError(
                f"Personnel order {order['order_id']} was not created by the current user."
            )
        return PERMISSION_CANCEL_OWN, True, "created_by_match"

    if has_scope_permission:
        raise PersonnelOrderCancelScopeDeniedError(
            f"Personnel order {order['order_id']} is outside actor cancel scope."
        )

    raise PersonnelOrderCancelPermissionDeniedError(
        "Cancel requires PERSONNEL_ORDERS_CANCEL_OWN or PERSONNEL_ORDERS_CANCEL_SCOPE."
    )


def cancel_personnel_order(
    *,
    order_id: int,
    reason_code: str,
    reason_text: Optional[str],
    actor_user_id: int,
) -> Dict[str, Any]:
    """Cancel a DRAFT/READY personnel order with granular permission enforcement."""
    _require_available()
    normalized_code, normalized_text, void_reason = _normalize_cancel_reason(
        reason_code=reason_code,
        reason_text=reason_text,
    )

    with engine.begin() as conn:
        order = _fetch_order_row_for_cancel(conn, int(order_id))
        assert_order_not_archived(order)
        status = str(order["status"])
        previous_void_kind = order.get("void_kind")

        if status == ORDER_STATUS_VOIDED:
            raise PersonnelOrderAlreadyVoidedError(
                f"Personnel order {order_id} is already voided."
            )
        if status not in CANCELABLE_ORDER_STATUSES:
            raise PersonnelOrderNotCancellableError(
                f"Personnel order {order_id} cannot be cancelled from status {status}."
            )
        if _has_approved_employee_events(conn, int(order_id)):
            raise PersonnelOrderAlreadyAppliedCancelError(
                f"Personnel order {order_id} already has approved employee events."
            )

        permission_used, ownership_match, scope_rule = _assert_cancel_permission(
            conn,
            order=order,
            actor_user_id=int(actor_user_id),
        )

        items = _fetch_items(conn, int(order_id), item_status=ITEM_STATUS_ACTIVE)
        for item in items:
            _mark_item_voided(
                conn,
                item_id=int(item["item_id"]),
                order_id=int(order_id),
                void_reason=void_reason,
                voided_by=int(actor_user_id),
            )
        _mark_order_voided(
            conn,
            order_id=int(order_id),
            void_reason=void_reason,
            voided_by=int(actor_user_id),
            void_kind=VOID_KIND_CANCEL,
        )
        append_cancel_order_audit(
            conn,
            order_id=int(order_id),
            previous_status=status,
            previous_void_kind=previous_void_kind,
            reason_code=normalized_code,
            reason_text=normalized_text or void_reason,
            void_reason=void_reason,
            actor_user_id=int(actor_user_id),
            metadata_json={
                "permission_used": permission_used,
                "ownership_match": ownership_match,
                "scope_rule": scope_rule,
            },
        )

    return get_personnel_order(int(order_id))
