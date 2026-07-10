"""Read-only query service for personnel orders (WP-PO-004A)."""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_orders import (
    MVP_HEADER_ORDER_TYPE_CODES,
    MVP_ITEM_TYPE_CODES,
    ORDER_STATUSES,
)
from app.services.hr_event_registry import get_event_class, get_event_label

PERSONNEL_ORDERS_TABLES = (
    "personnel_orders",
    "personnel_order_items",
    "personnel_order_localized_texts",
    "personnel_order_attachments",
    "personnel_order_prints",
)


class PersonnelOrderValidationError(ValueError):
    """Invalid filter parameter for personnel orders queries."""


class PersonnelOrderNotFoundError(LookupError):
    """Personnel order not found."""


def personnel_orders_available() -> bool:
    with engine.begin() as conn:
        for table in PERSONNEL_ORDERS_TABLES:
            row = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = :table_name
                    LIMIT 1
                    """
                ),
                {"table_name": table},
            ).first()
            if row is None:
                return False
        cols = {
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'employee_events'
                    """
                )
            ).all()
        }
        return "order_id" in cols and "order_item_id" in cols


def _iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _iso_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _rate(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _parse_metadata(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _parse_payload(value: Any) -> Dict[str, Any]:
    parsed = _parse_metadata(value)
    return parsed if parsed is not None else {}


def _normalize_status_filter(status: Optional[str]) -> Optional[str]:
    if status is None:
        return None
    normalized = status.strip().upper()
    if normalized not in ORDER_STATUSES:
        raise PersonnelOrderValidationError(f"Invalid status filter: {status}")
    return normalized


def _normalize_order_type_filter(order_type_code: Optional[str]) -> Optional[str]:
    if order_type_code is None:
        return None
    normalized = order_type_code.strip().upper()
    allowed = set(MVP_HEADER_ORDER_TYPE_CODES) | set(MVP_ITEM_TYPE_CODES)
    if normalized not in allowed:
        raise PersonnelOrderValidationError(f"Invalid order_type_code filter: {order_type_code}")
    return normalized


def _build_list_filters(
    *,
    status: Optional[str],
    order_type_code: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
    employee_id: Optional[int],
    org_unit_id: Optional[int],
    q: Optional[str],
) -> tuple[list[str], Dict[str, Any]]:
    where_parts = ["TRUE"]
    params: Dict[str, Any] = {}

    normalized_status = _normalize_status_filter(status)
    if normalized_status is not None:
        where_parts.append("po.status = :status")
        params["status"] = normalized_status

    normalized_type = _normalize_order_type_filter(order_type_code)
    if normalized_type is not None:
        where_parts.append(
            """
            (
                po.order_type_code = :order_type_code
                OR EXISTS (
                    SELECT 1
                    FROM public.personnel_order_items poi_type
                    WHERE poi_type.order_id = po.order_id
                      AND poi_type.item_type_code = :order_type_code
                )
            )
            """.strip()
        )
        params["order_type_code"] = normalized_type

    if date_from is not None:
        where_parts.append("po.order_date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        where_parts.append("po.order_date <= :date_to")
        params["date_to"] = date_to

    if employee_id is not None:
        where_parts.append(
            """
            EXISTS (
                SELECT 1
                FROM public.personnel_order_items poi_emp
                WHERE poi_emp.order_id = po.order_id
                  AND poi_emp.employee_id = :employee_id
            )
            """.strip()
        )
        params["employee_id"] = int(employee_id)

    if org_unit_id is not None:
        where_parts.append(
            """
            EXISTS (
                SELECT 1
                FROM public.personnel_order_items poi_org
                JOIN public.employees e_org ON e_org.employee_id = poi_org.employee_id
                WHERE poi_org.order_id = po.order_id
                  AND e_org.org_unit_id = :org_unit_id
            )
            """.strip()
        )
        params["org_unit_id"] = int(org_unit_id)

    if q:
        where_parts.append("po.order_number ILIKE :q_pattern")
        params["q_pattern"] = f"%{str(q).strip()}%"

    return where_parts, params


def _serialize_order_header(row: Dict[str, Any]) -> Dict[str, Any]:
    raw_number = row.get("order_number")
    order_number = str(raw_number).strip() if raw_number is not None and str(raw_number).strip() else None
    return {
        "order_id": int(row["order_id"]),
        "order_number": order_number,
        "order_date": _iso_date(row.get("order_date")),
        "order_type_code": str(row["order_type_code"]),
        "order_class": str(row.get("order_class") or "PERSONNEL"),
        "status": str(row["status"]),
        "source_mode": str(row["source_mode"]),
        "legal_basis_article": row.get("legal_basis_article"),
        "signed_by_employee_id": int(row["signed_by_employee_id"])
        if row.get("signed_by_employee_id") is not None
        else None,
        "signed_by_name": row.get("signed_by_name"),
        "signed_by_position": row.get("signed_by_position"),
        "executor_name": row.get("executor_name"),
        "basis_summary": row.get("basis_summary"),
        "comment": row.get("comment"),
        "void_reason": row.get("void_reason"),
        "voided_at": _iso_datetime(row.get("voided_at")),
        "voided_by": int(row["voided_by"]) if row.get("voided_by") is not None else None,
        "created_by": int(row["created_by"]),
        "created_at": _iso_datetime(row.get("created_at")),
        "updated_at": _iso_datetime(row.get("updated_at")),
    }


def _serialize_list_item(row: Dict[str, Any]) -> Dict[str, Any]:
    employee_ids_raw = row.get("employee_ids") or []
    employee_ids: List[int] = []
    if isinstance(employee_ids_raw, list):
        employee_ids = [int(v) for v in employee_ids_raw if v is not None]
    employee_names_raw = row.get("employee_names") or []
    employee_names: List[str] = []
    if isinstance(employee_names_raw, list):
        employee_names = [str(v) for v in employee_names_raw if v is not None]

    item = _serialize_order_header(row)
    item["item_count"] = int(row.get("item_count") or 0)
    item["employee_ids"] = employee_ids
    item["employee_names"] = employee_names
    return item


def _serialize_order_item(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "item_id": int(row["item_id"]),
        "order_id": int(row["order_id"]),
        "item_number": int(row["item_number"]),
        "item_type_code": str(row["item_type_code"]),
        "item_status": str(row["item_status"]),
        "employee_id": int(row["employee_id"]) if row.get("employee_id") is not None else None,
        "employee_name": row.get("employee_name"),
        "org_unit_id": int(row["org_unit_id"]) if row.get("org_unit_id") is not None else None,
        "org_unit_name": row.get("org_unit_name"),
        "effective_date": _iso_date(row.get("effective_date")),
        "period_start": _iso_date(row.get("period_start")),
        "period_end": _iso_date(row.get("period_end")),
        "payload": _parse_payload(row.get("payload")),
        "void_reason": row.get("void_reason"),
        "voided_at": _iso_datetime(row.get("voided_at")),
        "voided_by": int(row["voided_by"]) if row.get("voided_by") is not None else None,
        "created_at": _iso_datetime(row.get("created_at")),
    }


def _serialize_localized_text(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "localized_text_id": int(row["localized_text_id"]),
        "order_id": int(row["order_id"]),
        "locale": str(row["locale"]),
        "title": row.get("title"),
        "preamble": row.get("preamble"),
        "body_text": row.get("body_text"),
        "render_version": int(row.get("render_version") or 1),
        "is_authoritative": bool(row.get("is_authoritative")),
        "created_at": _iso_datetime(row.get("created_at")),
        "updated_at": _iso_datetime(row.get("updated_at")),
    }


def _serialize_attachment(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "attachment_id": int(row["attachment_id"]),
        "order_id": int(row["order_id"]),
        "attachment_kind": str(row["attachment_kind"]),
        "storage_type": str(row["storage_type"]),
        "file_path": row.get("file_path"),
        "file_url": row.get("file_url"),
        "file_comment": row.get("file_comment"),
        "locale": row.get("locale"),
        "created_by": int(row["created_by"]),
        "created_at": _iso_datetime(row.get("created_at")),
    }


def _serialize_print(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "print_id": int(row["print_id"]),
        "order_id": int(row["order_id"]),
        "locale": str(row["locale"]),
        "format": str(row["format"]),
        "file_path": row.get("file_path"),
        "file_url": row.get("file_url"),
        "is_signed_copy": bool(row.get("is_signed_copy")),
        "render_version": int(row.get("render_version") or 1),
        "generated_at": _iso_datetime(row.get("generated_at")),
        "generated_by": int(row["generated_by"]) if row.get("generated_by") is not None else None,
    }


def _serialize_linked_event(row: Dict[str, Any]) -> Dict[str, Any]:
    event_type = str(row["event_type"])
    metadata = _parse_metadata(row.get("metadata"))
    lifecycle_status = row.get("lifecycle_status")
    event_class = row.get("event_class")
    return {
        "event_id": int(row["event_id"]),
        "order_id": int(row["order_id"]) if row.get("order_id") is not None else None,
        "order_item_id": int(row["order_item_id"]) if row.get("order_item_id") is not None else None,
        "employee_id": int(row["employee_id"]),
        "employee_name": row.get("employee_name"),
        "event_type": event_type,
        "event_class": str(event_class) if event_class is not None else get_event_class(event_type),
        "event_label": get_event_label(event_type),
        "lifecycle_status": str(lifecycle_status) if lifecycle_status is not None else "APPROVED",
        "metadata": metadata,
        "effective_date": _iso_date(row.get("effective_date")),
        "from_org_unit_id": int(row["from_org_unit_id"]) if row.get("from_org_unit_id") is not None else None,
        "from_org_unit_name": row.get("from_org_unit_name"),
        "to_org_unit_id": int(row["to_org_unit_id"]) if row.get("to_org_unit_id") is not None else None,
        "to_org_unit_name": row.get("to_org_unit_name"),
        "from_position_id": int(row["from_position_id"]) if row.get("from_position_id") is not None else None,
        "from_position_name": row.get("from_position_name"),
        "to_position_id": int(row["to_position_id"]) if row.get("to_position_id") is not None else None,
        "to_position_name": row.get("to_position_name"),
        "from_rate": _rate(row.get("from_rate")),
        "to_rate": _rate(row.get("to_rate")),
        "order_ref": row.get("order_ref"),
        "comment": row.get("comment"),
        "created_at": _iso_datetime(row.get("created_at")),
    }


def list_personnel_orders(
    *,
    status: Optional[str] = None,
    order_type_code: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    employee_id: Optional[int] = None,
    org_unit_id: Optional[int] = None,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    if not personnel_orders_available():
        return {"items": [], "total": 0, "limit": int(limit), "offset": int(offset)}

    where_parts, params = _build_list_filters(
        status=status,
        order_type_code=order_type_code,
        date_from=date_from,
        date_to=date_to,
        employee_id=employee_id,
        org_unit_id=org_unit_id,
        q=q,
    )
    params["limit"] = int(limit)
    params["offset"] = int(offset)
    where_sql = " AND ".join(where_parts)

    q_total = text(
        f"""
        SELECT COUNT(*) AS cnt
        FROM public.personnel_orders po
        WHERE {where_sql}
        """
    )
    q_list = text(
        f"""
        SELECT
            po.order_id,
            po.order_number,
            po.order_date,
            po.order_type_code,
            po.order_class,
            po.status,
            po.source_mode,
            po.legal_basis_article,
            po.signed_by_employee_id,
            po.signed_by_name,
            po.signed_by_position,
            po.executor_name,
            po.basis_summary,
            po.comment,
            po.void_reason,
            po.voided_at,
            po.voided_by,
            po.created_by,
            po.created_at,
            po.updated_at,
            (
                SELECT COUNT(*)
                FROM public.personnel_order_items poi_cnt
                WHERE poi_cnt.order_id = po.order_id
            ) AS item_count,
            (
                SELECT COALESCE(
                    array_agg(DISTINCT poi_emp.employee_id ORDER BY poi_emp.employee_id),
                    ARRAY[]::bigint[]
                )
                FROM public.personnel_order_items poi_emp
                WHERE poi_emp.order_id = po.order_id
                  AND poi_emp.employee_id IS NOT NULL
            ) AS employee_ids,
            (
                SELECT COALESCE(
                    array_agg(DISTINCT e.full_name ORDER BY e.full_name),
                    ARRAY[]::text[]
                )
                FROM public.personnel_order_items poi_name
                JOIN public.employees e ON e.employee_id = poi_name.employee_id
                WHERE poi_name.order_id = po.order_id
            ) AS employee_names
        FROM public.personnel_orders po
        WHERE {where_sql}
        ORDER BY po.order_date DESC, po.order_id DESC
        LIMIT :limit OFFSET :offset
        """
    )

    with engine.begin() as conn:
        total = int(conn.execute(q_total, params).scalar_one())
        rows = conn.execute(q_list, params).mappings().all()

    items = [_serialize_list_item(dict(row)) for row in rows]
    return {
        "items": items,
        "total": total,
        "limit": int(limit),
        "offset": int(offset),
    }


def get_personnel_order(order_id: int) -> Dict[str, Any]:
    if not personnel_orders_available():
        raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")

    with engine.begin() as conn:
        header_row = conn.execute(
            text(
                """
                SELECT
                    po.order_id,
                    po.order_number,
                    po.order_date,
                    po.order_type_code,
                    po.order_class,
                    po.status,
                    po.source_mode,
                    po.legal_basis_article,
                    po.signed_by_employee_id,
                    po.signed_by_name,
                    po.signed_by_position,
                    po.executor_name,
                    po.basis_summary,
                    po.comment,
                    po.void_reason,
                    po.voided_at,
                    po.voided_by,
                    po.created_by,
                    po.created_at,
                    po.updated_at
                FROM public.personnel_orders po
                WHERE po.order_id = :order_id
                """
            ),
            {"order_id": int(order_id)},
        ).mappings().first()
        if header_row is None:
            raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")

        item_rows = conn.execute(
            text(
                """
                SELECT
                    poi.item_id,
                    poi.order_id,
                    poi.item_number,
                    poi.item_type_code,
                    poi.item_status,
                    poi.employee_id,
                    e.full_name AS employee_name,
                    e.org_unit_id,
                    ou.name AS org_unit_name,
                    poi.effective_date,
                    poi.period_start,
                    poi.period_end,
                    poi.payload,
                    poi.void_reason,
                    poi.voided_at,
                    poi.voided_by,
                    poi.created_at
                FROM public.personnel_order_items poi
                LEFT JOIN public.employees e ON e.employee_id = poi.employee_id
                LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
                WHERE poi.order_id = :order_id
                ORDER BY poi.item_number ASC, poi.item_id ASC
                """
            ),
            {"order_id": int(order_id)},
        ).mappings().all()

        localized_rows = conn.execute(
            text(
                """
                SELECT
                    localized_text_id,
                    order_id,
                    locale,
                    title,
                    preamble,
                    body_text,
                    render_version,
                    is_authoritative,
                    created_at,
                    updated_at
                FROM public.personnel_order_localized_texts
                WHERE order_id = :order_id
                ORDER BY locale ASC
                """
            ),
            {"order_id": int(order_id)},
        ).mappings().all()

        attachment_rows = conn.execute(
            text(
                """
                SELECT
                    attachment_id,
                    order_id,
                    attachment_kind,
                    storage_type,
                    file_path,
                    file_url,
                    file_comment,
                    locale,
                    created_by,
                    created_at
                FROM public.personnel_order_attachments
                WHERE order_id = :order_id
                ORDER BY created_at DESC, attachment_id DESC
                """
            ),
            {"order_id": int(order_id)},
        ).mappings().all()

        print_rows = conn.execute(
            text(
                """
                SELECT
                    print_id,
                    order_id,
                    locale,
                    format,
                    file_path,
                    file_url,
                    is_signed_copy,
                    render_version,
                    generated_at,
                    generated_by
                FROM public.personnel_order_prints
                WHERE order_id = :order_id
                ORDER BY generated_at DESC, print_id DESC
                """
            ),
            {"order_id": int(order_id)},
        ).mappings().all()

        event_rows = conn.execute(
            text(
                """
                SELECT
                    ev.event_id,
                    ev.order_id,
                    ev.order_item_id,
                    ev.employee_id,
                    e.full_name AS employee_name,
                    ev.event_type,
                    ev.event_class,
                    ev.lifecycle_status,
                    ev.metadata,
                    ev.effective_date,
                    ev.from_org_unit_id,
                    fou.name AS from_org_unit_name,
                    ev.to_org_unit_id,
                    tou.name AS to_org_unit_name,
                    ev.from_position_id,
                    fp.name AS from_position_name,
                    ev.to_position_id,
                    tp.name AS to_position_name,
                    ev.from_rate,
                    ev.to_rate,
                    ev.order_ref,
                    ev.comment,
                    ev.created_at
                FROM public.employee_events ev
                JOIN public.employees e ON e.employee_id = ev.employee_id
                LEFT JOIN public.org_units fou ON fou.unit_id = ev.from_org_unit_id
                LEFT JOIN public.org_units tou ON tou.unit_id = ev.to_org_unit_id
                LEFT JOIN public.positions fp ON fp.position_id = ev.from_position_id
                LEFT JOIN public.positions tp ON tp.position_id = ev.to_position_id
                WHERE ev.order_id = :order_id
                ORDER BY ev.effective_date DESC, ev.event_id DESC
                """
            ),
            {"order_id": int(order_id)},
        ).mappings().all()

    return {
        "order": _serialize_order_header(dict(header_row)),
        "items": [_serialize_order_item(dict(row)) for row in item_rows],
        "localized_texts": [_serialize_localized_text(dict(row)) for row in localized_rows],
        "attachments": [_serialize_attachment(dict(row)) for row in attachment_rows],
        "prints": [_serialize_print(dict(row)) for row in print_rows],
        "events": [_serialize_linked_event(dict(row)) for row in event_rows],
    }


def validation_error_to_http422(exc: PersonnelOrderValidationError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))
