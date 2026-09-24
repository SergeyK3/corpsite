"""Read-only personal personnel-order projection.

This deliberately does not reuse the HR order detail endpoint: a multi-item
order must never reach an employee browser as a complete document.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import text

from app.api.ppr_self_schemas import PprSelfOrderDetailResponse, PprSelfOrderListResponse
from app.auth import get_current_user
from app.db.engine import engine


router = APIRouter(prefix="/api/ppr/me/orders", tags=["ppr-self-orders"])

_UNCONFIRMED_WARNING = (
    "Приказ ещё не подтверждён кадровой службой. Сведения могут быть уточнены после сверки с оригиналом."
)
_CONFIRMED_STATUSES = {"SIGNED", "REGISTERED", "VOIDED"}
_SELF_ITEM_TYPE_LABELS = {
    "HIRE": "Приём на работу",
    "TRANSFER": "Перевод",
    "TERMINATION": "Увольнение",
    "CONCURRENT_DUTY_START": "Совмещение (начало)",
    "CONCURRENT_DUTY_END": "Совмещение (окончание)",
    "SUPPLEMENTARY_PAY": "Дополнительная оплата",
    "LEAVE.ANNUAL.GRANT": "Ежегодный трудовой отпуск",
    "LEAVE.UNPAID.GRANT": "Отпуск без сохранения заработной платы",
}


def _employee_for_user(user: dict[str, Any]) -> tuple[Literal["READY", "NO_EMPLOYEE_LINK", "PERSON_NOT_LINKED", "IDENTITY_AMBIGUOUS"], int | None]:
    """Resolve the only allowed subject from the session, never a request ID."""
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT e.employee_id, e.person_id
            FROM public.users u
            LEFT JOIN public.employees e ON e.employee_id = u.employee_id
            WHERE u.user_id = :user_id AND COALESCE(u.is_active, FALSE) IS TRUE
              AND COALESCE(e.is_active, FALSE) IS TRUE
        """), {"user_id": int(user["user_id"])}).mappings().one_or_none()
        if row is None or row["employee_id"] is None:
            return "NO_EMPLOYEE_LINK", None
        # Personnel orders are scoped by Employee, not Person.  An Employee
        # without a materialized Person card can therefore still safely read
        # only items bound to their session-resolved employee_id.
        if row["person_id"] is None:
            return "READY", int(row["employee_id"])
        count = int(conn.execute(text("""
            SELECT COUNT(*) FROM public.employees
            WHERE COALESCE(is_active, FALSE) IS TRUE AND person_id = :person_id
        """), {"person_id": row["person_id"]}).scalar_one())
    if count != 1:
        return "IDENTITY_AMBIGUOUS", None
    return "READY", int(row["employee_id"])


def _confirmed(status: str, needs_review: bool) -> bool:
    return status in _CONFIRMED_STATUSES and not needs_review


def _safe_rows(employee_id: int, *, order_id: int | None = None, year: int | None = None):
    """Select only the matching item and its effective editorial body.

    Neither header/item payloads nor editorial metadata are selected.  In
    particular, this query cannot serialise another employee's item.
    """
    filters = ["poi.employee_id = :employee_id"]
    params: dict[str, Any] = {"employee_id": employee_id}
    if order_id is not None:
        filters.append("po.order_id = :order_id")
        params["order_id"] = order_id
    if year is not None:
        filters.append("EXTRACT(YEAR FROM po.order_date) = :year")
        params["year"] = year
    where = " AND ".join(filters)
    statement = text(f"""
        SELECT po.order_id, po.order_number, po.order_date, po.order_type_code, po.status,
               COALESCE(NULLIF(BTRIM(title.override_text), ''), NULLIF(BTRIM(title.generated_text), ''),
                        NULLIF(BTRIM(localized.title), ''), po.order_type_code) AS title,
               COALESCE(NULLIF(BTRIM(body.override_text), ''), NULLIF(BTRIM(body.generated_text), '')) AS item_text,
               ARRAY(
                 SELECT own_item.item_type_code
                 FROM public.personnel_order_items own_item
                 WHERE own_item.order_id = po.order_id
                   AND own_item.employee_id = :employee_id
                 ORDER BY own_item.item_number ASC
               ) AS employee_item_types,
               (
                 COALESCE(po.storage_json ->> 'reconstruction_status', '') = 'NEEDS_DOCX_REVIEW'
                 OR EXISTS (
                   SELECT 1 FROM public.personnel_order_editorial_blocks eb
                   WHERE eb.order_id = po.order_id AND eb.review_status <> 'CURRENT'
                 )
                 OR EXISTS (
                   SELECT 1 FROM public.personnel_order_item_editorial_blocks ib
                   WHERE ib.order_item_id = poi.item_id AND ib.review_status <> 'CURRENT'
                 )
               ) AS needs_review
        FROM public.personnel_order_items poi
        JOIN public.personnel_orders po ON po.order_id = poi.order_id
        LEFT JOIN public.personnel_order_editorial_blocks title
          ON title.order_id = po.order_id AND title.locale = 'ru' AND title.block_type = 'title'
        LEFT JOIN public.personnel_order_item_editorial_blocks body
          ON body.order_item_id = poi.item_id AND body.locale = 'ru' AND body.block_type = 'body'
        LEFT JOIN public.personnel_order_localized_texts localized
          ON localized.order_id = po.order_id AND localized.locale = 'ru'
        WHERE {where}
        ORDER BY po.order_date DESC NULLS LAST, po.order_number DESC NULLS LAST, po.order_id DESC, poi.item_number ASC
    """)
    with engine.connect() as conn:
        return conn.execute(statement, params).mappings().all()


def _serialize(row: Any, *, detail: bool = False) -> dict[str, Any]:
    confirmed = _confirmed(str(row["status"]), bool(row["needs_review"]))
    title = str(row["title"])
    if title == "COMPOSITE":
        labels = [
            _SELF_ITEM_TYPE_LABELS.get(str(item_type), str(item_type))
            for item_type in (row.get("employee_item_types") or [])
        ]
        if labels:
            title = "; ".join(dict.fromkeys(labels))
    result = {
        "order_id": int(row["order_id"]), "order_number": row["order_number"], "order_date": row["order_date"],
        "title": title, "item_text": row["item_text"],
        "confirmation_status": "CONFIRMED" if confirmed else "UNCONFIRMED",
    }
    if detail:
        result["warning"] = None if confirmed else _UNCONFIRMED_WARNING
    return result


@router.get("", response_model=PprSelfOrderListResponse)
def list_my_orders(
    year: int | None = Query(default=None, ge=1900, le=9999),
    confirmation: Literal["all", "confirmed", "unconfirmed"] = Query(default="all"),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprSelfOrderListResponse:
    status, employee_id = _employee_for_user(user)
    if status != "READY":
        return PprSelfOrderListResponse(status=status)
    rows = [_serialize(row) for row in _safe_rows(employee_id, year=year)]
    if confirmation != "all":
        expected = "CONFIRMED" if confirmation == "confirmed" else "UNCONFIRMED"
        rows = [row for row in rows if row["confirmation_status"] == expected]
    return PprSelfOrderListResponse(status="READY", orders=rows)


@router.get("/{order_id}", response_model=PprSelfOrderDetailResponse)
def get_my_order(order_id: int = Path(ge=1), user: dict[str, Any] = Depends(get_current_user)) -> PprSelfOrderDetailResponse:
    status, employee_id = _employee_for_user(user)
    if status != "READY":
        raise HTTPException(status_code=403, detail="Self personnel orders are unavailable")
    rows = _safe_rows(employee_id, order_id=order_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Order not found")
    # There is normally one item per employee/order.  The first stable item is
    # the personal document view; no other items are disclosed.
    return PprSelfOrderDetailResponse(**_serialize(rows[0], detail=True))
