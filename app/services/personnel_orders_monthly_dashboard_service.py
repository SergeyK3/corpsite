"""Monthly order counts using the unfiltered orders summary's header scope."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.models.personnel_orders import (
    ITEM_STATUS_ACTIVE,
    ORDER_STATUS_VOIDED,
    ORDER_TYPE_COMPOSITE,
    ORDER_TYPE_HIRE,
    ORDER_TYPE_TERMINATION,
    ORDER_TYPE_TRANSFER,
)


FILTER_TYPES = {ORDER_TYPE_HIRE, ORDER_TYPE_TERMINATION, ORDER_TYPE_TRANSFER}


def build_personnel_orders_monthly_dashboard(
    engine: Engine, *, today: date | None = None, order_type: str | None = None,
) -> dict[str, Any]:
    """Count unique, non-voided order headers by official date, without pagination."""
    selected_type = None if order_type is None or order_type.lower() == "all" else order_type.upper()
    if selected_type is not None and selected_type not in FILTER_TYPES:
        raise ValueError("Unsupported order type filter.")

    type_filter_sql = ""
    params: dict[str, Any] = {"voided_status": ORDER_STATUS_VOIDED}
    if selected_type is not None:
        type_filter_sql = """
              AND (
                po.order_type_code = :order_type
                OR (po.order_type_code = :composite_type AND EXISTS (
                    SELECT 1 FROM public.personnel_order_items poi
                    WHERE poi.order_id = po.order_id
                      AND poi.item_status = :active_item_status
                      AND poi.item_type_code = :order_type
                ))
              )
        """
        params.update({
            "order_type": selected_type,
            "composite_type": ORDER_TYPE_COMPOSITE,
            "active_item_status": ITEM_STATUS_ACTIVE,
        })

    with engine.connect() as conn:
        report_date = today or conn.execute(text("SELECT CURRENT_DATE")).scalar_one()
        params.update({"date_from": date(report_date.year, 1, 1), "today": report_date})
        rows = conn.execute(text(f"""
            SELECT EXTRACT(MONTH FROM po.order_date)::int AS month,
                   COUNT(DISTINCT po.order_id)::int AS order_count
            FROM public.personnel_orders po
            WHERE po.archived_at IS NULL
              AND UPPER(BTRIM(COALESCE(po.status, ''))) <> :voided_status
              AND po.order_date >= :date_from
              AND po.order_date <= :today
              {type_filter_sql}
            GROUP BY EXTRACT(MONTH FROM po.order_date)
        """), params).mappings().all()

    counts = {int(row["month"]): int(row["order_count"]) for row in rows}
    months = [
        {"month": month, "count": counts.get(month, 0), "is_current": month == report_date.month}
        for month in range(1, report_date.month + 1)
    ]
    return {
        "report_code": "personnel_orders_monthly_dashboard",
        "year": report_date.year,
        "as_of": report_date.isoformat(),
        "order_type": selected_type,
        "months": months,
        "total": sum(item["count"] for item in months),
    }
