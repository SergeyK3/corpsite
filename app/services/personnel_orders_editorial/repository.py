"""SQL load / upsert / patch helpers for editorial blocks (WP-PO-EDIT-002).

Must not import service, generation_service, or ready_gate (avoid cycles).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.personnel_orders import (
    BASIS_TYPE_PERSONAL_APPLICATION,
    REVIEW_STATUS_CURRENT,
    REVIEW_STATUS_GENERATION_FAILED,
    REVIEW_STATUS_REVIEW_REQUIRED,
    REVIEW_STATUS_STALE,
)
from app.services.personnel_orders_editorial.basis_policy import resolve_basis_required
from app.services.personnel_orders_editorial.exceptions import (
    PersonnelOrderEditorialBlockNotFoundError,
)
from app.services.personnel_orders_query_service import PersonnelOrderNotFoundError


def fetch_order(conn: Connection, order_id: int) -> Dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT
                order_id,
                order_number,
                order_date,
                order_type_code,
                status,
                legal_basis_article
            FROM public.personnel_orders
            WHERE order_id = :order_id
            """
        ),
        {"order_id": int(order_id)},
    ).mappings().first()
    if row is None:
        raise PersonnelOrderNotFoundError(f"Personnel order {order_id} not found.")
    return dict(row)


def load_employee_names(conn: Connection, employee_ids: Sequence[int]) -> Dict[int, str]:
    ids = sorted({int(eid) for eid in employee_ids if eid is not None})
    if not ids:
        return {}
    rows = conn.execute(
        text(
            """
            SELECT employee_id, full_name
            FROM public.employees
            WHERE employee_id = ANY(:ids)
            """
        ),
        {"ids": ids},
    ).mappings().all()
    return {int(r["employee_id"]): str(r["full_name"] or "").strip() for r in rows}


def load_items(conn: Connection, order_id: int) -> List[Dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                item_id,
                order_id,
                item_number,
                item_type_code,
                employee_id,
                effective_date,
                payload,
                item_status
            FROM public.personnel_order_items
            WHERE order_id = :order_id
            ORDER BY item_number ASC, item_id ASC
            """
        ),
        {"order_id": int(order_id)},
    ).mappings().all()
    return [dict(r) for r in rows]


def load_order_blocks(conn: Connection, order_id: int) -> List[Dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT
                editorial_block_id AS block_id,
                order_id,
                locale,
                block_type,
                generated_text,
                override_text,
                generator_key,
                generator_version,
                source_fingerprint,
                review_status,
                generated_at,
                edited_at,
                edited_by_user_id,
                revision,
                created_at,
                updated_at
            FROM public.personnel_order_editorial_blocks
            WHERE order_id = :order_id
            ORDER BY locale ASC, block_type ASC
            """
        ),
        {"order_id": int(order_id)},
    ).mappings().all()
    return [dict(r) for r in rows]


def load_item_blocks(
    conn: Connection,
    *,
    order_id: int,
    item_ids: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"order_id": int(order_id)}
    item_filter = ""
    if item_ids is not None:
        ids = [int(i) for i in item_ids]
        if not ids:
            return []
        params["item_ids"] = ids
        item_filter = "AND i.item_id = ANY(:item_ids)"
    rows = conn.execute(
        text(
            f"""
            SELECT
                b.item_editorial_block_id AS block_id,
                b.order_item_id,
                i.item_number,
                i.item_type_code,
                b.locale,
                b.block_type,
                b.generated_text,
                b.override_text,
                b.generator_key,
                b.generator_version,
                b.source_fingerprint,
                b.review_status,
                b.basis_required,
                b.generated_at,
                b.edited_at,
                b.edited_by_user_id,
                b.revision,
                b.created_at,
                b.updated_at
            FROM public.personnel_order_item_editorial_blocks b
            JOIN public.personnel_order_items i
              ON i.item_id = b.order_item_id
            WHERE i.order_id = :order_id
              {item_filter}
            ORDER BY i.item_number ASC, b.locale ASC, b.block_type ASC
            """
        ),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]


def load_bases(conn: Connection, item_ids: Sequence[int]) -> Dict[int, Dict[str, Any]]:
    ids = [int(i) for i in item_ids]
    if not ids:
        return {}
    rows = conn.execute(
        text(
            """
            SELECT
                item_basis_id,
                order_item_id,
                basis_type,
                subject_employee_id,
                document_date,
                document_number,
                free_text,
                metadata
            FROM public.personnel_order_item_bases
            WHERE order_item_id = ANY(:item_ids)
            """
        ),
        {"item_ids": ids},
    ).mappings().all()
    return {int(r["order_item_id"]): dict(r) for r in rows}


def ensure_default_basis(
    conn: Connection,
    item: Mapping[str, Any],
) -> Dict[str, Any]:
    item_id = int(item["item_id"])
    existing = conn.execute(
        text(
            """
            SELECT
                item_basis_id,
                order_item_id,
                basis_type,
                subject_employee_id,
                document_date,
                document_number,
                free_text,
                metadata
            FROM public.personnel_order_item_bases
            WHERE order_item_id = :item_id
            """
        ),
        {"item_id": item_id},
    ).mappings().first()
    if existing is not None:
        return dict(existing)

    basis_required, unsupported = resolve_basis_required(str(item["item_type_code"]))
    # Always create a default PERSONAL_APPLICATION row for supported types;
    # for unsupported still create so basis text can be generated.
    subject_id = int(item["employee_id"]) if item.get("employee_id") is not None else None
    row = conn.execute(
        text(
            """
            INSERT INTO public.personnel_order_item_bases (
                order_item_id,
                basis_type,
                subject_employee_id
            )
            VALUES (
                :order_item_id,
                :basis_type,
                :subject_employee_id
            )
            RETURNING
                item_basis_id,
                order_item_id,
                basis_type,
                subject_employee_id,
                document_date,
                document_number,
                free_text,
                metadata
            """
        ),
        {
            "order_item_id": item_id,
            "basis_type": BASIS_TYPE_PERSONAL_APPLICATION,
            "subject_employee_id": subject_id,
        },
    ).mappings().one()
    _ = basis_required, unsupported
    return dict(row)


def upsert_order_block(
    conn: Connection,
    *,
    order_id: int,
    locale: str,
    block_type: str,
    generated: Mapping[str, str],
    user_id: Optional[int],
    legacy_text: Optional[str],
    is_first: bool,
    force_review_required: bool = False,
) -> Tuple[str, str]:
    """Insert or update an order block. Returns (old_status, new_status)."""
    existing = conn.execute(
        text(
            """
            SELECT
                editorial_block_id,
                generated_text,
                override_text,
                source_fingerprint,
                review_status,
                revision
            FROM public.personnel_order_editorial_blocks
            WHERE order_id = :order_id
              AND locale = :locale
              AND block_type = :block_type
            """
        ),
        {"order_id": int(order_id), "locale": locale, "block_type": block_type},
    ).mappings().first()

    new_fp = generated["source_fingerprint"]
    new_text = generated["generated_text"]

    if existing is None:
        override = None
        status = REVIEW_STATUS_CURRENT
        if is_first and legacy_text and legacy_text.strip():
            if legacy_text.strip() != (new_text or "").strip():
                # Hand-authored legacy text becomes override.
                override = legacy_text
                status = REVIEW_STATUS_CURRENT
            # else: seed generated only
        if force_review_required:
            status = REVIEW_STATUS_REVIEW_REQUIRED
        conn.execute(
            text(
                """
                INSERT INTO public.personnel_order_editorial_blocks (
                    order_id,
                    locale,
                    block_type,
                    generated_text,
                    override_text,
                    generator_key,
                    generator_version,
                    source_fingerprint,
                    review_status,
                    generated_at,
                    edited_at,
                    edited_by_user_id,
                    revision
                )
                VALUES (
                    :order_id,
                    :locale,
                    :block_type,
                    :generated_text,
                    :override_text,
                    :generator_key,
                    :generator_version,
                    :source_fingerprint,
                    :review_status,
                    now(),
                    CASE WHEN :override_text IS NOT NULL THEN now() ELSE NULL END,
                    CASE WHEN :override_text IS NOT NULL THEN :user_id ELSE NULL END,
                    1
                )
                """
            ),
            {
                "order_id": int(order_id),
                "locale": locale,
                "block_type": block_type,
                "generated_text": new_text,
                "override_text": override,
                "generator_key": generated["generator_key"],
                "generator_version": generated["generator_version"],
                "source_fingerprint": new_fp,
                "review_status": status,
                "user_id": user_id,
            },
        )
        return ("", status)

    old_status = str(existing["review_status"])
    override = existing.get("override_text")
    old_fp = existing.get("source_fingerprint")
    has_override = bool((override or "").strip())

    if has_override and old_fp and old_fp != new_fp:
        status = REVIEW_STATUS_REVIEW_REQUIRED
    elif force_review_required:
        status = REVIEW_STATUS_REVIEW_REQUIRED
    else:
        status = REVIEW_STATUS_CURRENT

    conn.execute(
        text(
            """
            UPDATE public.personnel_order_editorial_blocks
            SET generated_text = :generated_text,
                generator_key = :generator_key,
                generator_version = :generator_version,
                source_fingerprint = :source_fingerprint,
                review_status = :review_status,
                generated_at = now(),
                updated_at = now(),
                revision = revision + 1
            WHERE editorial_block_id = :block_id
            """
        ),
        {
            "block_id": int(existing["editorial_block_id"]),
            "generated_text": new_text,
            "generator_key": generated["generator_key"],
            "generator_version": generated["generator_version"],
            "source_fingerprint": new_fp,
            "review_status": status,
        },
    )
    return (old_status, status)


def mark_order_block_failed(
    conn: Connection,
    *,
    order_id: int,
    locale: str,
    block_type: str,
) -> None:
    existing = conn.execute(
        text(
            """
            SELECT editorial_block_id
            FROM public.personnel_order_editorial_blocks
            WHERE order_id = :order_id
              AND locale = :locale
              AND block_type = :block_type
            """
        ),
        {"order_id": int(order_id), "locale": locale, "block_type": block_type},
    ).scalar_one_or_none()
    if existing is None:
        conn.execute(
            text(
                """
                INSERT INTO public.personnel_order_editorial_blocks (
                    order_id,
                    locale,
                    block_type,
                    review_status,
                    generated_at,
                    revision
                )
                VALUES (
                    :order_id,
                    :locale,
                    :block_type,
                    :review_status,
                    now(),
                    1
                )
                """
            ),
            {
                "order_id": int(order_id),
                "locale": locale,
                "block_type": block_type,
                "review_status": REVIEW_STATUS_GENERATION_FAILED,
            },
        )
    else:
        conn.execute(
            text(
                """
                UPDATE public.personnel_order_editorial_blocks
                SET review_status = :review_status,
                    updated_at = now(),
                    revision = revision + 1
                WHERE editorial_block_id = :block_id
                """
            ),
            {
                "block_id": int(existing),
                "review_status": REVIEW_STATUS_GENERATION_FAILED,
            },
        )


def upsert_item_block(
    conn: Connection,
    *,
    order_item_id: int,
    locale: str,
    block_type: str,
    generated: Mapping[str, str],
    basis_required: bool,
    force_review_required: bool = False,
) -> Tuple[str, str]:
    existing = conn.execute(
        text(
            """
            SELECT
                item_editorial_block_id,
                override_text,
                source_fingerprint,
                review_status
            FROM public.personnel_order_item_editorial_blocks
            WHERE order_item_id = :order_item_id
              AND locale = :locale
              AND block_type = :block_type
            """
        ),
        {
            "order_item_id": int(order_item_id),
            "locale": locale,
            "block_type": block_type,
        },
    ).mappings().first()

    new_fp = generated["source_fingerprint"]
    new_text = generated["generated_text"]

    if existing is None:
        status = (
            REVIEW_STATUS_REVIEW_REQUIRED
            if force_review_required
            else REVIEW_STATUS_CURRENT
        )
        conn.execute(
            text(
                """
                INSERT INTO public.personnel_order_item_editorial_blocks (
                    order_item_id,
                    locale,
                    block_type,
                    generated_text,
                    generator_key,
                    generator_version,
                    source_fingerprint,
                    review_status,
                    basis_required,
                    generated_at,
                    revision
                )
                VALUES (
                    :order_item_id,
                    :locale,
                    :block_type,
                    :generated_text,
                    :generator_key,
                    :generator_version,
                    :source_fingerprint,
                    :review_status,
                    :basis_required,
                    now(),
                    1
                )
                """
            ),
            {
                "order_item_id": int(order_item_id),
                "locale": locale,
                "block_type": block_type,
                "generated_text": new_text,
                "generator_key": generated["generator_key"],
                "generator_version": generated["generator_version"],
                "source_fingerprint": new_fp,
                "review_status": status,
                "basis_required": bool(basis_required),
            },
        )
        return ("", status)

    old_status = str(existing["review_status"])
    has_override = bool((existing.get("override_text") or "").strip())
    old_fp = existing.get("source_fingerprint")
    if has_override and old_fp and old_fp != new_fp:
        status = REVIEW_STATUS_REVIEW_REQUIRED
    elif force_review_required:
        status = REVIEW_STATUS_REVIEW_REQUIRED
    else:
        status = REVIEW_STATUS_CURRENT

    conn.execute(
        text(
            """
            UPDATE public.personnel_order_item_editorial_blocks
            SET generated_text = :generated_text,
                generator_key = :generator_key,
                generator_version = :generator_version,
                source_fingerprint = :source_fingerprint,
                review_status = :review_status,
                basis_required = :basis_required,
                generated_at = now(),
                updated_at = now(),
                revision = revision + 1
            WHERE item_editorial_block_id = :block_id
            """
        ),
        {
            "block_id": int(existing["item_editorial_block_id"]),
            "generated_text": new_text,
            "generator_key": generated["generator_key"],
            "generator_version": generated["generator_version"],
            "source_fingerprint": new_fp,
            "review_status": status,
            "basis_required": bool(basis_required),
        },
    )
    return (old_status, status)


def mark_item_block_failed(
    conn: Connection,
    *,
    order_item_id: int,
    locale: str,
    block_type: str,
    basis_required: bool,
) -> None:
    existing = conn.execute(
        text(
            """
            SELECT item_editorial_block_id
            FROM public.personnel_order_item_editorial_blocks
            WHERE order_item_id = :order_item_id
              AND locale = :locale
              AND block_type = :block_type
            """
        ),
        {
            "order_item_id": int(order_item_id),
            "locale": locale,
            "block_type": block_type,
        },
    ).scalar_one_or_none()
    if existing is None:
        conn.execute(
            text(
                """
                INSERT INTO public.personnel_order_item_editorial_blocks (
                    order_item_id,
                    locale,
                    block_type,
                    review_status,
                    basis_required,
                    generated_at,
                    revision
                )
                VALUES (
                    :order_item_id,
                    :locale,
                    :block_type,
                    :review_status,
                    :basis_required,
                    now(),
                    1
                )
                """
            ),
            {
                "order_item_id": int(order_item_id),
                "locale": locale,
                "block_type": block_type,
                "review_status": REVIEW_STATUS_GENERATION_FAILED,
                "basis_required": bool(basis_required),
            },
        )
    else:
        conn.execute(
            text(
                """
                UPDATE public.personnel_order_item_editorial_blocks
                SET review_status = :review_status,
                    basis_required = :basis_required,
                    updated_at = now(),
                    revision = revision + 1
                WHERE item_editorial_block_id = :block_id
                """
            ),
            {
                "block_id": int(existing),
                "review_status": REVIEW_STATUS_GENERATION_FAILED,
                "basis_required": bool(basis_required),
            },
        )


def find_block(
    conn: Connection,
    order_id: int,
    block_id: int,
) -> Tuple[str, Dict[str, Any]]:
    """Return ('order'|'item', row) verifying ownership by order_id."""
    order_row = conn.execute(
        text(
            """
            SELECT
                editorial_block_id AS block_id,
                order_id,
                locale,
                block_type,
                generated_text,
                override_text,
                generator_key,
                generator_version,
                source_fingerprint,
                review_status,
                generated_at,
                edited_at,
                edited_by_user_id,
                revision
            FROM public.personnel_order_editorial_blocks
            WHERE editorial_block_id = :block_id
              AND order_id = :order_id
            """
        ),
        {"block_id": int(block_id), "order_id": int(order_id)},
    ).mappings().first()
    if order_row is not None:
        return "order", dict(order_row)

    item_row = conn.execute(
        text(
            """
            SELECT
                b.item_editorial_block_id AS block_id,
                b.order_item_id,
                i.order_id,
                b.locale,
                b.block_type,
                b.generated_text,
                b.override_text,
                b.generator_key,
                b.generator_version,
                b.source_fingerprint,
                b.review_status,
                b.basis_required,
                b.generated_at,
                b.edited_at,
                b.edited_by_user_id,
                b.revision
            FROM public.personnel_order_item_editorial_blocks b
            JOIN public.personnel_order_items i
              ON i.item_id = b.order_item_id
            WHERE b.item_editorial_block_id = :block_id
              AND i.order_id = :order_id
            """
        ),
        {"block_id": int(block_id), "order_id": int(order_id)},
    ).mappings().first()
    if item_row is not None:
        return "item", dict(item_row)

    raise PersonnelOrderEditorialBlockNotFoundError(
        f"Editorial block {block_id} not found for order {order_id}."
    )


def update_order_block_override(
    conn: Connection,
    *,
    block_id: int,
    override_text: Optional[str],
    review_status: str,
    user_id: Optional[int],
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.personnel_order_editorial_blocks
            SET override_text = :override_text,
                review_status = :review_status,
                edited_at = now(),
                edited_by_user_id = :user_id,
                updated_at = now(),
                revision = revision + 1
            WHERE editorial_block_id = :block_id
            """
        ),
        {
            "block_id": int(block_id),
            "override_text": override_text,
            "review_status": review_status,
            "user_id": user_id,
        },
    )


def update_item_block_override(
    conn: Connection,
    *,
    block_id: int,
    override_text: Optional[str],
    review_status: str,
    user_id: Optional[int],
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.personnel_order_item_editorial_blocks
            SET override_text = :override_text,
                review_status = :review_status,
                edited_at = now(),
                edited_by_user_id = :user_id,
                updated_at = now(),
                revision = revision + 1
            WHERE item_editorial_block_id = :block_id
            """
        ),
        {
            "block_id": int(block_id),
            "override_text": override_text,
            "review_status": review_status,
            "user_id": user_id,
        },
    )


def mark_order_block_stale(conn: Connection, *, block_id: int) -> None:
    conn.execute(
        text(
            """
            UPDATE public.personnel_order_editorial_blocks
            SET review_status = :review_status,
                updated_at = now()
            WHERE editorial_block_id = :block_id
            """
        ),
        {
            "block_id": int(block_id),
            "review_status": REVIEW_STATUS_STALE,
        },
    )


def mark_item_block_stale(conn: Connection, *, block_id: int) -> None:
    conn.execute(
        text(
            """
            UPDATE public.personnel_order_item_editorial_blocks
            SET review_status = :review_status,
                updated_at = now()
            WHERE item_editorial_block_id = :block_id
            """
        ),
        {
            "block_id": int(block_id),
            "review_status": REVIEW_STATUS_STALE,
        },
    )


def touch_order_updated_at(conn: Connection, order_id: int) -> None:
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
