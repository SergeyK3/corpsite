"""Validate explicit totals for a transfer followed by simple additional work."""
from decimal import Decimal, InvalidOperation, localcontext
from sqlalchemy import text


def _rate(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Ставки перевода, дополнительной работы и общая ставка должны быть положительными числами.") from None
    if not result.is_finite() or result <= 0:
        raise ValueError("Ставки перевода, дополнительной работы и общая ставка должны быть положительными числами.")
    return result


def validate_combined_rates(items):
    """Use only a preceding transfer for the same employee and effective date.

    Percentage/replacement contracts and standalone additional work retain their
    own validation. No employee assignment is read or changed here.
    """
    transfers = {}
    for item in sorted(items, key=lambda row: (row["item_number"], row.get("item_id", 0))):
        if item.get("item_status", "ACTIVE") != "ACTIVE" or item.get("employee_id") is None:
            continue
        key = (item["employee_id"], item.get("effective_date"))
        payload = item.get("payload") or {}
        if item["item_type_code"] == "TRANSFER" and "transfer" in payload:
            transfers[key] = payload["transfer"].get("rate")
        elif (item["item_type_code"] == "CONCURRENT_DUTY_START"
              and "concurrent" in payload and "replacement" not in payload and key in transfers):
            data = payload["concurrent"]
            primary, additional, total = map(_rate, (transfers[key], data.get("rate"), data.get("total_rate")))
            # Preserve all decimal places even for values exceeding the default
            # Decimal context. Never add binary floats or round the result.
            with localcontext() as ctx:
                ctx.prec = max(28, len(primary.as_tuple().digits) + len(additional.as_tuple().digits)
                               + abs(primary.as_tuple().exponent - additional.as_tuple().exponent) + 2)
                expected = primary + additional
            if total != expected:
                display = lambda value: format(value, "f").replace(".", ",")
                raise ValueError(
                    f"Пункт {item['item_number']}: общая ставка должна равняться ставке перевода "
                    f"плюс дополнительной ставке: {display(primary)} + {display(additional)} = {display(expected)}."
                )


def validate_order_combined_rates(conn, order_id):
    rows = conn.execute(text("""SELECT item_id,item_number,item_type_code,employee_id,effective_date,payload,item_status
        FROM personnel_order_items WHERE order_id=:id AND item_status='ACTIVE'
        ORDER BY item_number,item_id"""), {"id": order_id}).mappings().all()
    validate_combined_rates(rows)
