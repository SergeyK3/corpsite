"""Mark overridden editorial blocks STALE after structured changes (R9)."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from sqlalchemy.engine import Connection

from app.db.models.personnel_orders import (
    ITEM_BLOCK_TYPE_BODY,
    REVIEW_STATUS_STALE,
)
from app.services.personnel_orders_editorial.audit import write_editorial_audit
from app.services.personnel_orders_editorial.availability import editorial_tables_available
from app.services.personnel_orders_editorial.generators import (
    generate_basis_text,
    generate_item_body,
    generate_order_block,
)
from app.services.personnel_orders_editorial.mapper import build_item_ctx, iso_date
from app.services.personnel_orders_editorial.repository import (
    fetch_order,
    load_bases,
    load_employee_names,
    load_item_blocks,
    load_items,
    load_order_blocks,
    mark_item_block_stale,
    mark_order_block_stale,
)


def current_order_fingerprint(
    order: Mapping[str, Any],
    block_type: str,
    locale: str,
) -> str:
    generated = generate_order_block(
        block_type,
        locale,
        {
            "order_type_code": order.get("order_type_code"),
            "legal_basis_article": order.get("legal_basis_article"),
        },
    )
    return generated["source_fingerprint"]


def current_item_body_fingerprint(
    item: Mapping[str, Any],
    employee_name: Optional[str],
    locale: str,
) -> str:
    return generate_item_body(locale, build_item_ctx(item, employee_name))["source_fingerprint"]


def current_item_basis_fingerprint(
    basis: Mapping[str, Any],
    subject_name: Optional[str],
    locale: str,
) -> str:
    return generate_basis_text(
        locale,
        {
            "basis_type": basis.get("basis_type"),
            "subject_employee_id": basis.get("subject_employee_id"),
            "subject_employee_name": subject_name,
            "document_date": iso_date(basis.get("document_date")),
            "document_number": basis.get("document_number"),
            "free_text": basis.get("free_text"),
        },
    )["source_fingerprint"]


def mark_blocks_stale_after_structured_change(
    conn: Connection,
    order_id: int,
    *,
    item_id: Optional[int] = None,
) -> None:
    """Mark overridden blocks STALE when structured fingerprint diverges (R9).

    If no override is present, leave CURRENT (outdated fingerprint is OK until regen).
    """
    if not editorial_tables_available(conn):
        return

    order = fetch_order(conn, order_id)
    items = load_items(conn, order_id)
    if item_id is not None:
        items = [i for i in items if int(i["item_id"]) == int(item_id)]

    employee_ids = [int(i["employee_id"]) for i in items if i.get("employee_id") is not None]
    bases = load_bases(conn, [int(i["item_id"]) for i in items])
    for basis in bases.values():
        if basis.get("subject_employee_id") is not None:
            employee_ids.append(int(basis["subject_employee_id"]))
    names = load_employee_names(conn, employee_ids)

    # Order-level: only when not scoped to a single item.
    if item_id is None:
        for block in load_order_blocks(conn, order_id):
            has_override = bool((block.get("override_text") or "").strip())
            if not has_override:
                continue
            try:
                current_fp = current_order_fingerprint(
                    order, str(block["block_type"]), str(block["locale"])
                )
            except Exception:
                continue
            stored = block.get("source_fingerprint")
            if stored and stored != current_fp:
                old_status = str(block["review_status"])
                mark_order_block_stale(conn, block_id=int(block["block_id"]))
                write_editorial_audit(
                    event_type="EDITORIAL_MARKED_STALE",
                    actor_user_id=None,
                    metadata={
                        "order_id": int(order_id),
                        "item_id": None,
                        "block_type": block["block_type"],
                        "locale": block["locale"],
                        "user_id": None,
                        "result": "stale",
                        "generator_version": block.get("generator_version"),
                        "old_review_status": old_status,
                        "new_review_status": REVIEW_STATUS_STALE,
                    },
                    conn=conn,
                )

    item_map = {int(i["item_id"]): i for i in items}
    item_blocks = load_item_blocks(
        conn,
        order_id=order_id,
        item_ids=[int(i["item_id"]) for i in items] if items else [],
    )
    for block in item_blocks:
        has_override = bool((block.get("override_text") or "").strip())
        if not has_override:
            continue
        item = item_map.get(int(block["order_item_id"]))
        if item is None:
            continue
        locale = str(block["locale"])
        try:
            if block["block_type"] == ITEM_BLOCK_TYPE_BODY:
                emp_name = (
                    names.get(int(item["employee_id"]))
                    if item.get("employee_id") is not None
                    else None
                )
                current_fp = current_item_body_fingerprint(item, emp_name, locale)
            else:
                basis = bases.get(int(block["order_item_id"]))
                if basis is None:
                    continue
                subject_id = basis.get("subject_employee_id")
                subject_name = (
                    names.get(int(subject_id)) if subject_id is not None else None
                )
                current_fp = current_item_basis_fingerprint(basis, subject_name, locale)
        except Exception:
            continue
        stored = block.get("source_fingerprint")
        if stored and stored != current_fp:
            old_status = str(block["review_status"])
            mark_item_block_stale(conn, block_id=int(block["block_id"]))
            write_editorial_audit(
                event_type="EDITORIAL_MARKED_STALE",
                actor_user_id=None,
                metadata={
                    "order_id": int(order_id),
                    "item_id": int(block["order_item_id"]),
                    "block_type": block["block_type"],
                    "locale": locale,
                    "user_id": None,
                    "result": "stale",
                    "generator_version": block.get("generator_version"),
                    "old_review_status": old_status,
                    "new_review_status": REVIEW_STATUS_STALE,
                },
                conn=conn,
            )
