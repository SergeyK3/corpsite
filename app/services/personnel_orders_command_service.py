"""Write service for personnel orders draft/register flow (WP-PO-004B).

No employee_events apply and no void cascade in this work package.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from app.db.models.personnel_orders import (
    ITEM_STATUS_ACTIVE,
    LOCALE_KK,
    LOCALE_RU,
    MVP_HEADER_ORDER_TYPE_CODES,
    MVP_ITEM_TYPE_CODES,
    ORDER_STATUS_DRAFT,
    ORDER_STATUS_READY_FOR_SIGNATURE,
    ORDER_STATUS_REGISTERED,
    ORDER_STATUS_SIGNED,
    ORDER_STATUS_VOIDED,
    ORDER_TYPE_COMPOSITE,
    SOURCE_MODE_DIGITAL,
    SOURCE_MODE_PAPER,
)
from app.services.personnel_order_archive_guard import assert_order_not_archived
from app.services.personnel_order_signatory_resolver import (
    apply_default_signatory_if_needed,
)
from app.services.personnel_orders_query_service import (
    PersonnelOrderNotFoundError,
    PersonnelOrderValidationError,
    get_personnel_order,
    personnel_orders_available,
)

EDITABLE_ORDER_STATUSES = {
    ORDER_STATUS_DRAFT,
}
REGISTERABLE_FROM_STATUSES = {
    ORDER_STATUS_DRAFT,
    ORDER_STATUS_READY_FOR_SIGNATURE,
}
REGISTER_TARGET_STATUSES = {
    ORDER_STATUS_SIGNED,
    ORDER_STATUS_REGISTERED,
}
LOCKED_ORDER_STATUSES = {
    ORDER_STATUS_SIGNED,
    ORDER_STATUS_REGISTERED,
    ORDER_STATUS_VOIDED,
}
ALLOWED_LOCALES = {LOCALE_KK, LOCALE_RU}


class PersonnelOrderConflictError(RuntimeError):
    """Order is locked or business rule conflict."""


class PersonnelOrderItemNotFoundError(LookupError):
    """Personnel order item not found."""


def _mark_editorial_stale(conn, order_id: int, *, item_id: int | None = None) -> None:
    try:
        from app.services.personnel_orders_editorial_service import (
            mark_blocks_stale_after_structured_change,
        )

        mark_blocks_stale_after_structured_change(conn, int(order_id), item_id=item_id)
    except Exception:
        pass


def _require_available() -> None:
    if not personnel_orders_available():
        raise PersonnelOrderValidationError("Personnel orders schema is not available.")


def _normalize_header_type(order_type_code: str) -> str:
    normalized = str(order_type_code or "").strip().upper()
    if normalized not in MVP_HEADER_ORDER_TYPE_CODES:
        raise PersonnelOrderValidationError(f"Invalid order_type_code: {order_type_code}")
    return normalized


def _normalize_item_type(item_type_code: str) -> str:
    normalized = str(item_type_code or "").strip().upper()
    if normalized not in MVP_ITEM_TYPE_CODES:
        raise PersonnelOrderValidationError(f"Invalid item_type_code: {item_type_code}")
    return normalized


def _normalize_source_mode(source_mode: str) -> str:
    normalized = str(source_mode or "").strip().upper()
    if normalized not in {SOURCE_MODE_DIGITAL, SOURCE_MODE_PAPER}:
        raise PersonnelOrderValidationError(f"Invalid source_mode: {source_mode}")
    return normalized


def _normalize_locale(locale: str) -> str:
    normalized = str(locale or "").strip().lower()
    if normalized not in ALLOWED_LOCALES:
        raise PersonnelOrderValidationError(f"Invalid locale: {locale}")
    return normalized


def _normalize_register_target(target_status: str) -> str:
    normalized = str(target_status or "").strip().upper()
    if normalized not in REGISTER_TARGET_STATUSES:
        raise PersonnelOrderValidationError(
            f"Invalid target_status: {target_status}. Allowed: SIGNED, REGISTERED."
        )
    return normalized


def _fetch_order_row(conn, order_id: int) -> Dict[str, Any]:
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


def _ensure_order_editable(order: Dict[str, Any]) -> None:
    assert_order_not_archived(order)
    status = str(order["status"])
    if status in LOCKED_ORDER_STATUSES:
        raise PersonnelOrderConflictError(
            f"Personnel order {order['order_id']} is locked in status {status}."
        )
    if status not in EDITABLE_ORDER_STATUSES:
        raise PersonnelOrderConflictError(
            f"Personnel order {order['order_id']} cannot be edited in status {status}."
        )


def _ensure_employee_exists(conn, employee_id: int) -> None:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.employees
            WHERE employee_id = :employee_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).first()
    if row is None:
        raise PersonnelOrderValidationError(f"Employee {employee_id} not found.")


def _next_item_number(conn, order_id: int) -> int:
    current = conn.execute(
        text(
            """
            SELECT COALESCE(MAX(item_number), 0) AS max_item_number
            FROM public.personnel_order_items
            WHERE order_id = :order_id
            """
        ),
        {"order_id": int(order_id)},
    ).scalar_one()
    return int(current or 0) + 1


def _validate_registerable_order(conn, order: Dict[str, Any]) -> None:
    order_number = str(order.get("order_number") or "").strip()
    if not order_number:
        raise PersonnelOrderValidationError("order_number is required before registration.")

    if order.get("order_date") is None:
        raise PersonnelOrderValidationError("order_date is required before registration.")

    items = conn.execute(
        text(
            """
            SELECT
                item_id,
                item_type_code,
                employee_id,
                effective_date,
                item_status
            FROM public.personnel_order_items
            WHERE order_id = :order_id
              AND item_status = :item_status
            ORDER BY item_number ASC, item_id ASC
            """
        ),
        {"order_id": int(order["order_id"]), "item_status": ITEM_STATUS_ACTIVE},
    ).mappings().all()
    if not items:
        raise PersonnelOrderValidationError("At least one active order item is required before registration.")

    for item in items:
        if item.get("employee_id") is None:
            raise PersonnelOrderValidationError(
                f"Order item {item['item_id']} requires employee_id before registration."
            )
        if not str(item.get("item_type_code") or "").strip():
            raise PersonnelOrderValidationError(
                f"Order item {item['item_id']} requires item_type_code before registration."
            )
        if item.get("effective_date") is None:
            raise PersonnelOrderValidationError(
                f"Order item {item['item_id']} requires effective_date before registration."
            )


def _resolve_header_type_from_items(conn, order_id: int, fallback: str) -> str:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT item_type_code
            FROM public.personnel_order_items
            WHERE order_id = :order_id
              AND item_status = :item_status
            """
        ),
        {"order_id": int(order_id), "item_status": ITEM_STATUS_ACTIVE},
    ).scalars().all()
    types = {str(value).strip().upper() for value in rows if value}
    if not types:
        return fallback
    if len(types) == 1:
        return next(iter(types))
    return ORDER_TYPE_COMPOSITE


def create_personnel_order_draft(
    *,
    created_by: int,
    order_number: Optional[str] = None,
    order_date: Optional[date] = None,
    order_type_code: str,
    source_mode: str = SOURCE_MODE_DIGITAL,
    legal_basis_article: Optional[str] = None,
    signed_by_employee_id: Optional[int] = None,
    signed_by_name: Optional[str] = None,
    signed_by_position: Optional[str] = None,
    executor_name: Optional[str] = None,
    basis_summary: Optional[str] = None,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    _require_available()

    # Paper First: registration number/date may be filled later from the paper journal.
    normalized_number = str(order_number or "").strip() or None
    normalized_type = _normalize_header_type(order_type_code)
    normalized_source_mode = _normalize_source_mode(source_mode)

    try:
        with engine.begin() as conn:
            (
                signed_by_employee_id,
                signed_by_name,
                signed_by_position,
                _signatory_warning,
            ) = apply_default_signatory_if_needed(
                signed_by_employee_id=signed_by_employee_id,
                signed_by_name=signed_by_name,
                signed_by_position=signed_by_position,
                conn=conn,
            )

            if signed_by_employee_id is not None:
                _ensure_employee_exists(conn, signed_by_employee_id)

            order_id = conn.execute(
                text(
                    """
                    INSERT INTO public.personnel_orders (
                        order_number,
                        order_date,
                        order_type_code,
                        status,
                        source_mode,
                        legal_basis_article,
                        signed_by_employee_id,
                        signed_by_name,
                        signed_by_position,
                        executor_name,
                        basis_summary,
                        comment,
                        created_by
                    )
                    VALUES (
                        :order_number,
                        :order_date,
                        :order_type_code,
                        :status,
                        :source_mode,
                        :legal_basis_article,
                        :signed_by_employee_id,
                        :signed_by_name,
                        :signed_by_position,
                        :executor_name,
                        :basis_summary,
                        :comment,
                        :created_by
                    )
                    RETURNING order_id
                    """
                ),
                {
                    "order_number": normalized_number,
                    "order_date": order_date,
                    "order_type_code": normalized_type,
                    "status": ORDER_STATUS_DRAFT,
                    "source_mode": normalized_source_mode,
                    "legal_basis_article": legal_basis_article,
                    "signed_by_employee_id": signed_by_employee_id,
                    "signed_by_name": signed_by_name,
                    "signed_by_position": signed_by_position,
                    "executor_name": executor_name,
                    "basis_summary": basis_summary,
                    "comment": comment,
                    "created_by": int(created_by),
                },
            ).scalar_one()
    except IntegrityError as exc:
        if normalized_number:
            raise PersonnelOrderConflictError(
                f"Personnel order number already exists: {normalized_number}"
            ) from exc
        raise

    return get_personnel_order(int(order_id))


def update_personnel_order_draft(
    *,
    order_id: int,
    order_number: Optional[str] = None,
    order_date: Optional[date] = None,
    order_type_code: Optional[str] = None,
    source_mode: Optional[str] = None,
    legal_basis_article: Optional[str] = None,
    signed_by_employee_id: Optional[int] = None,
    signed_by_name: Optional[str] = None,
    signed_by_position: Optional[str] = None,
    executor_name: Optional[str] = None,
    basis_summary: Optional[str] = None,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    _require_available()

    updates: Dict[str, Any] = {}
    if order_number is not None:
        normalized_number = str(order_number).strip()
        if not normalized_number:
            raise PersonnelOrderValidationError("order_number cannot be empty.")
        updates["order_number"] = normalized_number
    if order_date is not None:
        updates["order_date"] = order_date
    if order_type_code is not None:
        updates["order_type_code"] = _normalize_header_type(order_type_code)
    if source_mode is not None:
        updates["source_mode"] = _normalize_source_mode(source_mode)
    if legal_basis_article is not None:
        updates["legal_basis_article"] = legal_basis_article
    if signed_by_employee_id is not None:
        updates["signed_by_employee_id"] = int(signed_by_employee_id)
    if signed_by_name is not None:
        updates["signed_by_name"] = signed_by_name
    if signed_by_position is not None:
        updates["signed_by_position"] = signed_by_position
    if executor_name is not None:
        updates["executor_name"] = executor_name
    if basis_summary is not None:
        updates["basis_summary"] = basis_summary
    if comment is not None:
        updates["comment"] = comment

    if not updates:
        raise PersonnelOrderValidationError("No fields provided for update.")

    try:
        with engine.begin() as conn:
            order = _fetch_order_row(conn, order_id)
            _ensure_order_editable(order)
            if signed_by_employee_id is not None:
                _ensure_employee_exists(conn, signed_by_employee_id)

            set_parts = [f"{column} = :{column}" for column in updates]
            set_parts.append("updated_at = now()")
            params = dict(updates)
            params["order_id"] = int(order_id)

            conn.execute(
                text(
                    f"""
                    UPDATE public.personnel_orders
                    SET {", ".join(set_parts)}
                    WHERE order_id = :order_id
                    """
                ),
                params,
            )
            try:
                _mark_editorial_stale(conn, int(order_id))
            except Exception:
                pass
    except IntegrityError as exc:
        raise PersonnelOrderConflictError("Personnel order number already exists.") from exc

    return get_personnel_order(int(order_id))


def create_personnel_order_item(
    *,
    order_id: int,
    item_type_code: str,
    employee_id: Optional[int] = None,
    effective_date: Optional[date] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    payload: Optional[Dict[str, Any]] = None,
    item_number: Optional[int] = None,
) -> Dict[str, Any]:
    _require_available()
    normalized_type = _normalize_item_type(item_type_code)
    payload_json = json.dumps(payload or {})

    with engine.begin() as conn:
        order = _fetch_order_row(conn, order_id)
        _ensure_order_editable(order)

        if employee_id is not None:
            _ensure_employee_exists(conn, employee_id)

        next_number = int(item_number) if item_number is not None else _next_item_number(conn, order_id)
        if next_number < 1:
            raise PersonnelOrderValidationError("item_number must be positive.")

        conn.execute(
            text(
                """
                INSERT INTO public.personnel_order_items (
                    order_id,
                    item_number,
                    item_type_code,
                    employee_id,
                    effective_date,
                    period_start,
                    period_end,
                    payload,
                    item_status
                )
                VALUES (
                    :order_id,
                    :item_number,
                    :item_type_code,
                    :employee_id,
                    :effective_date,
                    :period_start,
                    :period_end,
                    CAST(:payload AS jsonb),
                    :item_status
                )
                """
            ),
            {
                "order_id": int(order_id),
                "item_number": next_number,
                "item_type_code": normalized_type,
                "employee_id": int(employee_id) if employee_id is not None else None,
                "effective_date": effective_date,
                "period_start": period_start,
                "period_end": period_end,
                "payload": payload_json,
                "item_status": ITEM_STATUS_ACTIVE,
            },
        )

        conn.execute(
            text(
                """
                UPDATE public.personnel_orders
                SET updated_at = now()
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id)},
        )
        try:
            _mark_editorial_stale(conn, int(order_id))
        except Exception:
            pass

    return get_personnel_order(int(order_id))


def update_personnel_order_item(
    *,
    order_id: int,
    item_id: int,
    item_type_code: Optional[str] = None,
    employee_id: Optional[int] = None,
    effective_date: Optional[date] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    payload: Optional[Dict[str, Any]] = None,
    item_number: Optional[int] = None,
) -> Dict[str, Any]:
    _require_available()

    updates: Dict[str, Any] = {}
    if item_type_code is not None:
        updates["item_type_code"] = _normalize_item_type(item_type_code)
    if employee_id is not None:
        updates["employee_id"] = int(employee_id)
    if effective_date is not None:
        updates["effective_date"] = effective_date
    if period_start is not None:
        updates["period_start"] = period_start
    if period_end is not None:
        updates["period_end"] = period_end
    if payload is not None:
        updates["payload"] = json.dumps(payload)
    if item_number is not None:
        if int(item_number) < 1:
            raise PersonnelOrderValidationError("item_number must be positive.")
        updates["item_number"] = int(item_number)

    if not updates:
        raise PersonnelOrderValidationError("No fields provided for item update.")

    with engine.begin() as conn:
        order = _fetch_order_row(conn, order_id)
        _ensure_order_editable(order)

        item_row = conn.execute(
            text(
                """
                SELECT item_id
                FROM public.personnel_order_items
                WHERE item_id = :item_id
                  AND order_id = :order_id
                """
            ),
            {"item_id": int(item_id), "order_id": int(order_id)},
        ).first()
        if item_row is None:
            raise PersonnelOrderItemNotFoundError(
                f"Personnel order item {item_id} not found for order {order_id}."
            )

        if employee_id is not None:
            _ensure_employee_exists(conn, employee_id)

        set_parts = []
        params: Dict[str, Any] = {
            "item_id": int(item_id),
            "order_id": int(order_id),
        }
        for column, value in updates.items():
            if column == "payload":
                set_parts.append("payload = CAST(:payload AS jsonb)")
                params["payload"] = value
            else:
                set_parts.append(f"{column} = :{column}")
                params[column] = value

        conn.execute(
            text(
                f"""
                UPDATE public.personnel_order_items
                SET {", ".join(set_parts)}
                WHERE item_id = :item_id
                  AND order_id = :order_id
                """
            ),
            params,
        )
        conn.execute(
            text(
                """
                UPDATE public.personnel_orders
                SET updated_at = now()
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id)},
        )
        try:
            _mark_editorial_stale(conn, int(order_id), item_id=int(item_id))
        except Exception:
            pass

    return get_personnel_order(int(order_id))


def upsert_personnel_order_localized_text(
    *,
    order_id: int,
    locale: str,
    title: Optional[str] = None,
    preamble: Optional[str] = None,
    body_text: Optional[str] = None,
    is_authoritative: Optional[bool] = None,
) -> Dict[str, Any]:
    _require_available()
    normalized_locale = _normalize_locale(locale)

    with engine.begin() as conn:
        order = _fetch_order_row(conn, order_id)
        _ensure_order_editable(order)

        existing = conn.execute(
            text(
                """
                SELECT localized_text_id
                FROM public.personnel_order_localized_texts
                WHERE order_id = :order_id
                  AND locale = :locale
                """
            ),
            {"order_id": int(order_id), "locale": normalized_locale},
        ).scalar_one_or_none()

        if existing is None:
            conn.execute(
                text(
                    """
                    INSERT INTO public.personnel_order_localized_texts (
                        order_id,
                        locale,
                        title,
                        preamble,
                        body_text,
                        is_authoritative
                    )
                    VALUES (
                        :order_id,
                        :locale,
                        :title,
                        :preamble,
                        :body_text,
                        COALESCE(:is_authoritative, FALSE)
                    )
                    """
                ),
                {
                    "order_id": int(order_id),
                    "locale": normalized_locale,
                    "title": title,
                    "preamble": preamble,
                    "body_text": body_text,
                    "is_authoritative": is_authoritative,
                },
            )
        else:
            updates: Dict[str, Any] = {}
            if title is not None:
                updates["title"] = title
            if preamble is not None:
                updates["preamble"] = preamble
            if body_text is not None:
                updates["body_text"] = body_text
            if is_authoritative is not None:
                updates["is_authoritative"] = bool(is_authoritative)

            if not updates:
                raise PersonnelOrderValidationError("No fields provided for localized text update.")

            set_parts = [f"{column} = :{column}" for column in updates]
            set_parts.append("updated_at = now()")
            set_parts.append("render_version = render_version + 1")
            params = dict(updates)
            params["order_id"] = int(order_id)
            params["locale"] = normalized_locale

            conn.execute(
                text(
                    f"""
                    UPDATE public.personnel_order_localized_texts
                    SET {", ".join(set_parts)}
                    WHERE order_id = :order_id
                      AND locale = :locale
                    """
                ),
                params,
            )

        conn.execute(
            text(
                """
                UPDATE public.personnel_orders
                SET updated_at = now()
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id)},
        )

    return get_personnel_order(int(order_id))


def mark_personnel_order_ready_for_signature(*, order_id: int) -> Dict[str, Any]:
    _require_available()

    with engine.begin() as conn:
        order = _fetch_order_row(conn, order_id)
        assert_order_not_archived(order)
        if str(order["status"]) != ORDER_STATUS_DRAFT:
            raise PersonnelOrderConflictError(
                f"Only DRAFT orders can move to READY_FOR_SIGNATURE (current: {order['status']})."
            )
        _validate_registerable_order(conn, order)

    from app.services.personnel_orders_editorial_service import (
        PersonnelOrderReadyGateError,
        editorial_tables_available,
        evaluate_ready_gate,
    )

    if editorial_tables_available():
        problems = evaluate_ready_gate(int(order_id))
        if problems:
            try:
                from app.services.security_audit_service import write_security_event

                write_security_event(
                    event_type="READY_GATE_REJECTED",
                    success=False,
                    metadata={
                        "order_id": int(order_id),
                        "result": "READY_GATE_FAILED",
                        "problem_count": len(problems),
                        "problem_codes": sorted(
                            {str(p.get("code")) for p in problems if p.get("code")}
                        ),
                    },
                )
            except Exception:
                pass
            raise PersonnelOrderReadyGateError(problems)

    with engine.begin() as conn:
        order = _fetch_order_row(conn, order_id)
        assert_order_not_archived(order)
        if str(order["status"]) != ORDER_STATUS_DRAFT:
            raise PersonnelOrderConflictError(
                f"Only DRAFT orders can move to READY_FOR_SIGNATURE (current: {order['status']})."
            )
        conn.execute(
            text(
                """
                UPDATE public.personnel_orders
                SET status = :status,
                    updated_at = now()
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id), "status": ORDER_STATUS_READY_FOR_SIGNATURE},
        )

    return get_personnel_order(int(order_id))


def register_personnel_order(
    *,
    order_id: int,
    target_status: str,
) -> Dict[str, Any]:
    _require_available()
    normalized_target = _normalize_register_target(target_status)

    with engine.begin() as conn:
        order = _fetch_order_row(conn, order_id)
        assert_order_not_archived(order)
        current_status = str(order["status"])
        if current_status in LOCKED_ORDER_STATUSES:
            raise PersonnelOrderConflictError(
                f"Personnel order {order_id} is already locked in status {current_status}."
            )
        if current_status not in REGISTERABLE_FROM_STATUSES:
            raise PersonnelOrderConflictError(
                f"Personnel order {order_id} cannot be registered from status {current_status}."
            )

        _validate_registerable_order(conn, order)
        resolved_type = _resolve_header_type_from_items(
            conn,
            int(order_id),
            str(order["order_type_code"]),
        )

        conn.execute(
            text(
                """
                UPDATE public.personnel_orders
                SET status = :status,
                    order_type_code = :order_type_code,
                    updated_at = now()
                WHERE order_id = :order_id
                """
            ),
            {
                "order_id": int(order_id),
                "status": normalized_target,
                "order_type_code": resolved_type,
            },
        )

    return get_personnel_order(int(order_id))
