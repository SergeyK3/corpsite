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
    "kk": {
        "HIRE": "Жұмысқа қабылдау туралы",
        "RETURN_FROM_CHILDCARE_LEAVE": "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы",
        "TRANSFER": "Ауыстыру туралы",
        "TERMINATION": "Жұмыстан босату туралы",
        "CONCURRENT_DUTY_START": "Қоса атқару (басталуы)",
        "CONCURRENT_DUTY_END": "Қоса атқару (аяқталуы)",
        "SUPPLEMENTARY_PAY": "Қосымша ақы туралы",
        "LEAVE.ANNUAL.GRANT": "Жыл сайынғы еңбек демалысын беру туралы",
        "LEAVE.UNPAID.GRANT": "Жалақы сақталмайтын демалыс беру туралы",
        "LEAVE.CHILDCARE.GRANT": "Бала үш жасқа толғанға дейін оның күтіміне байланысты жалақы сақталмайтын демалыс беру туралы",
    },
    "ru": {
        "HIRE": "О приёме на работу",
        "RETURN_FROM_CHILDCARE_LEAVE": "О выходе на работу из отпуска по уходу за ребёнком",
        "TRANSFER": "О переводе",
        "TERMINATION": "Об увольнении",
        "CONCURRENT_DUTY_START": "Совмещение (начало)",
        "CONCURRENT_DUTY_END": "Совмещение (окончание)",
        "SUPPLEMENTARY_PAY": "О дополнительной оплате",
        "LEAVE.ANNUAL.GRANT": "О предоставлении ежегодного трудового отпуска",
        "LEAVE.UNPAID.GRANT": "О предоставлении отпуска без сохранения заработной платы",
        "LEAVE.CHILDCARE.GRANT": "О предоставлении отпуска без сохранения заработной платы по уходу за ребёнком до достижения им возраста трёх лет",
    },
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


def _confirmed(status: str, needs_review: bool, needs_docx_review: bool = False) -> bool:
    return status in _CONFIRMED_STATUSES and not needs_review and not needs_docx_review


def _safe_rows(
    employee_id: int,
    *,
    order_id: int | None = None,
    year: int | None = None,
    locale: Literal["kk", "ru"] = "kk",
):
    """Select only the matching item and its effective editorial body.

    Neither header/item payloads nor editorial metadata are selected.  In
    particular, this query cannot serialise another employee's item.
    """
    filters = ["poi.employee_id = :employee_id"]
    params: dict[str, Any] = {"employee_id": employee_id, "locale": locale}
    if order_id is not None:
        filters.append("po.order_id = :order_id")
        params["order_id"] = order_id
    if year is not None:
        filters.append("EXTRACT(YEAR FROM po.order_date) = :year")
        params["year"] = year
    where = " AND ".join(filters)
    statement = text(f"""
        SELECT po.order_id, po.order_number, po.order_date, po.order_type_code, po.status,
               COALESCE(NULLIF(BTRIM(title.override_text), ''), NULLIF(BTRIM(title.generated_text), '')) AS title,
               COALESCE(NULLIF(BTRIM(preamble.override_text), ''), NULLIF(BTRIM(preamble.generated_text), '')) AS preamble,
               COALESCE(NULLIF(BTRIM(body.override_text), ''), NULLIF(BTRIM(body.generated_text), '')) AS item_text,
               COALESCE(NULLIF(BTRIM(basis.override_text), ''), NULLIF(BTRIM(basis.generated_text), '')) AS basis,
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
               ) AS needs_review,
               (
                 po.source_mode = 'PAPER'
                 AND EXISTS (
                   SELECT 1
                   FROM public.personnel_order_items own_return_item
                   WHERE own_return_item.order_id = po.order_id
                     AND own_return_item.employee_id = :employee_id
                     AND own_return_item.item_type_code = 'RETURN_FROM_CHILDCARE_LEAVE'
                 )
               ) AS needs_docx_review
        FROM public.personnel_order_items poi
        JOIN public.personnel_orders po ON po.order_id = poi.order_id
        LEFT JOIN public.personnel_order_editorial_blocks title
          ON title.order_id = po.order_id AND title.locale = :locale AND title.block_type = 'title'
        LEFT JOIN public.personnel_order_editorial_blocks preamble
          ON preamble.order_id = po.order_id AND preamble.locale = :locale AND preamble.block_type = 'preamble'
        LEFT JOIN public.personnel_order_item_editorial_blocks body
          ON body.order_item_id = poi.item_id AND body.locale = :locale AND body.block_type = 'body'
        LEFT JOIN public.personnel_order_item_editorial_blocks basis
          ON basis.order_item_id = poi.item_id AND basis.locale = :locale AND basis.block_type = 'basis'
        WHERE {where}
        ORDER BY po.order_date DESC NULLS LAST, po.order_number DESC NULLS LAST, po.order_id DESC, poi.item_number ASC
    """)
    with engine.connect() as conn:
        return conn.execute(statement, params).mappings().all()


def _serialize(row: Any, *, locale: Literal["kk", "ru"], detail: bool = False) -> dict[str, Any]:
    confirmed = _confirmed(
        str(row["status"]),
        bool(row["needs_review"]),
        bool(row.get("needs_docx_review")),
    )
    title = str(row.get("title") or "").strip()
    labels_by_type = _SELF_ITEM_TYPE_LABELS[locale]
    if not title or title == "COMPOSITE":
        labels = [
            labels_by_type.get(str(item_type), "Кадрлық бұйрық" if locale == "kk" else "Кадровый приказ")
            for item_type in (row.get("employee_item_types") or [])
        ]
        if labels:
            title = "; ".join(dict.fromkeys(labels))
        else:
            title = labels_by_type.get(str(row["order_type_code"]), "Кадрлық бұйрық" if locale == "kk" else "Кадровый приказ")
    elif title in labels_by_type:
        title = labels_by_type[title]
    result = {
        "order_id": int(row["order_id"]), "order_number": row["order_number"], "order_date": row["order_date"],
        "title": title, "item_text": row["item_text"],
        "confirmation_status": "CONFIRMED" if confirmed else "UNCONFIRMED",
    }
    if detail:
        result["warning"] = None if confirmed else _UNCONFIRMED_WARNING
        result["preamble"] = row.get("preamble")
        result["basis"] = row.get("basis")
    return result


@router.get("", response_model=PprSelfOrderListResponse)
def list_my_orders(
    year: int | None = Query(default=None, ge=1900, le=9999),
    confirmation: Literal["all", "confirmed", "unconfirmed"] = Query(default="all"),
    locale: Literal["kk", "ru"] = Query(default="kk"),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprSelfOrderListResponse:
    status, employee_id = _employee_for_user(user)
    if status != "READY":
        return PprSelfOrderListResponse(status=status)
    rows = [_serialize(row, locale=locale) for row in _safe_rows(employee_id, year=year, locale=locale)]
    if confirmation != "all":
        expected = "CONFIRMED" if confirmation == "confirmed" else "UNCONFIRMED"
        rows = [row for row in rows if row["confirmation_status"] == expected]
    return PprSelfOrderListResponse(status="READY", orders=rows)


@router.get("/{order_id}", response_model=PprSelfOrderDetailResponse)
def get_my_order(
    order_id: int = Path(ge=1),
    locale: Literal["kk", "ru"] = Query(default="kk"),
    user: dict[str, Any] = Depends(get_current_user),
) -> PprSelfOrderDetailResponse:
    status, employee_id = _employee_for_user(user)
    if status != "READY":
        raise HTTPException(status_code=403, detail="Self personnel orders are unavailable")
    rows = _safe_rows(employee_id, order_id=order_id, locale=locale)
    if not rows:
        raise HTTPException(status_code=404, detail="Order not found")
    # There is normally one item per employee/order.  The first stable item is
    # the personal document view; no other items are disclosed.
    return PprSelfOrderDetailResponse(**_serialize(rows[0], locale=locale, detail=True))
