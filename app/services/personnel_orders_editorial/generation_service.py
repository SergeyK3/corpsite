"""Editorial text generation / regeneration (WP-PO-EDIT-002).

Per-block try/except: a failed block is marked GENERATION_FAILED while
successful blocks in the same generate call are still committed in the same
transaction. Overrides are never cleared on regenerate.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from app.db.engine import engine
from app.db.models.personnel_orders import (
    ITEM_BLOCK_TYPE_BASIS,
    ITEM_BLOCK_TYPE_BODY,
    ITEM_BLOCK_TYPES,
    ORDER_BLOCK_TYPE_PREAMBLE,
    ORDER_BLOCK_TYPE_TITLE,
    ORDER_BLOCK_TYPES,
    REVIEW_STATUS_GENERATION_FAILED,
)
from app.services.personnel_orders_editorial.audit import write_editorial_audit
from app.services.personnel_orders_editorial.availability import require_available
from app.services.personnel_orders_editorial.basis_policy import resolve_basis_required
from app.services.personnel_orders_editorial.constants import ALLOWED_LOCALES
from app.services.personnel_orders_editorial.fallback import load_legacy_localized
from app.services.personnel_orders_editorial.generators import (
    generate_basis_text,
    generate_item_body,
    generate_order_block,
)
from app.services.personnel_orders_editorial.mapper import build_item_ctx, iso_date
from app.services.personnel_orders_editorial.repository import (
    ensure_default_basis,
    fetch_order,
    load_employee_names,
    load_item_blocks,
    load_items,
    load_order_blocks,
    mark_item_block_failed,
    mark_order_block_failed,
    touch_order_updated_at,
    upsert_item_block,
    upsert_order_block,
)
from app.services.personnel_orders_editorial.write_lock import ensure_draft_writable


def scope_allows(
    scope: Optional[Mapping[str, Any]],
    *,
    locale: str,
    block_type: str,
    item_id: Optional[int] = None,
    block_id: Optional[int] = None,
    level: str,
) -> bool:
    """Return True if this block should be (re)generated under ``scope``."""
    if not scope:
        return True
    if scope.get("item_id") is not None:
        if level == "order":
            return False
        if item_id is None or int(scope["item_id"]) != int(item_id):
            return False
    if scope.get("locale") is not None:
        if str(scope["locale"]).strip().lower() != str(locale).strip().lower():
            return False
    if scope.get("block_type") is not None:
        if str(scope["block_type"]).strip().lower() != str(block_type).strip().lower():
            return False
    if scope.get("block_id") is not None:
        if block_id is None or int(scope["block_id"]) != int(block_id):
            return False
    return True


def generate_editorial(
    order_id: int,
    *,
    user_id: Optional[int],
    scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create missing blocks and regenerate generated_text; never clears overrides.

    Failure isolation: each block is generated in its own try/except. A failed
    block is persisted as GENERATION_FAILED; other successful blocks in the same
    call remain committed in the same transaction.
    """
    require_available()
    scope = dict(scope) if scope else None

    with engine.begin() as conn:
        order = fetch_order(conn, order_id)
        ensure_draft_writable(order)

        items = load_items(conn, order_id)
        employee_ids = [
            int(i["employee_id"]) for i in items if i.get("employee_id") is not None
        ]
        bases: Dict[int, Dict[str, Any]] = {}
        for item in items:
            if scope and scope.get("item_id") is not None and int(scope["item_id"]) != int(item["item_id"]):
                continue
            bases[int(item["item_id"])] = ensure_default_basis(conn, item)

        for basis in bases.values():
            if basis.get("subject_employee_id") is not None:
                employee_ids.append(int(basis["subject_employee_id"]))
        names = load_employee_names(conn, employee_ids)
        legacy = load_legacy_localized(conn, order_id)

        existing_order_blocks = {
            (b["locale"], b["block_type"]): b for b in load_order_blocks(conn, order_id)
        }
        is_first_generate = len(existing_order_blocks) == 0

        order_ctx = {
            "order_type_code": order.get("order_type_code"),
            "legal_basis_article": order.get("legal_basis_article"),
        }

        for locale in ALLOWED_LOCALES:
            for block_type in ORDER_BLOCK_TYPES:
                existing = existing_order_blocks.get((locale, block_type))
                current_id = int(existing["block_id"]) if existing else None
                if not scope_allows(
                    scope,
                    locale=locale,
                    block_type=block_type,
                    block_id=current_id,
                    level="order",
                ):
                    continue

                try:
                    generated = generate_order_block(block_type, locale, order_ctx)
                    legacy_field = None
                    if block_type in (ORDER_BLOCK_TYPE_TITLE, ORDER_BLOCK_TYPE_PREAMBLE):
                        legacy_field = (legacy.get(locale) or {}).get(block_type)
                    old_status, new_status = upsert_order_block(
                        conn,
                        order_id=int(order_id),
                        locale=locale,
                        block_type=block_type,
                        generated=generated,
                        user_id=user_id,
                        legacy_text=legacy_field,
                        is_first=is_first_generate and existing is None,
                    )
                    write_editorial_audit(
                        event_type=(
                            "EDITORIAL_GENERATED" if existing is None else "EDITORIAL_REGENERATED"
                        ),
                        actor_user_id=user_id,
                        metadata={
                            "order_id": int(order_id),
                            "block_type": block_type,
                            "locale": locale,
                            "user_id": user_id,
                            "result": "ok",
                            "generator_version": generated["generator_version"],
                            "old_review_status": old_status or None,
                            "new_review_status": new_status,
                        },
                        conn=conn,
                    )
                except Exception:
                    mark_order_block_failed(
                        conn,
                        order_id=int(order_id),
                        locale=locale,
                        block_type=block_type,
                    )
                    write_editorial_audit(
                        event_type="EDITORIAL_GENERATED",
                        actor_user_id=user_id,
                        success=False,
                        metadata={
                            "order_id": int(order_id),
                            "block_type": block_type,
                            "locale": locale,
                            "user_id": user_id,
                            "result": "GENERATION_FAILED",
                            "generator_version": None,
                            "old_review_status": None,
                            "new_review_status": REVIEW_STATUS_GENERATION_FAILED,
                        },
                        conn=conn,
                    )

        existing_item_blocks = {
            (int(b["order_item_id"]), b["locale"], b["block_type"]): b
            for b in load_item_blocks(conn, order_id=order_id)
        }

        for item in items:
            item_id = int(item["item_id"])
            basis_required, unsupported = resolve_basis_required(str(item["item_type_code"]))
            force_review = unsupported is not None
            employee_name = names.get(int(item["employee_id"])) if item.get("employee_id") else None
            item_ctx = build_item_ctx(item, employee_name)
            basis = bases.get(item_id)
            if basis is None:
                if scope and scope.get("item_id") is not None and int(scope["item_id"]) != item_id:
                    continue
                basis = ensure_default_basis(conn, item)
                bases[item_id] = basis
            subject_id = basis.get("subject_employee_id")
            subject_name = names.get(int(subject_id)) if subject_id is not None else employee_name
            basis_fact = {
                "basis_type": basis.get("basis_type"),
                "subject_employee_id": subject_id,
                "subject_employee_name": subject_name,
                "document_date": iso_date(basis.get("document_date")),
                "document_number": basis.get("document_number"),
                "free_text": basis.get("free_text"),
            }

            for locale in ALLOWED_LOCALES:
                for block_type in ITEM_BLOCK_TYPES:
                    existing = existing_item_blocks.get((item_id, locale, block_type))
                    current_id = int(existing["block_id"]) if existing else None
                    if not scope_allows(
                        scope,
                        locale=locale,
                        block_type=block_type,
                        item_id=item_id,
                        block_id=current_id,
                        level="item",
                    ):
                        continue

                    try:
                        if block_type == ITEM_BLOCK_TYPE_BODY:
                            generated = generate_item_body(locale, item_ctx)
                        else:
                            generated = generate_basis_text(locale, basis_fact)
                        old_status, new_status = upsert_item_block(
                            conn,
                            order_item_id=item_id,
                            locale=locale,
                            block_type=block_type,
                            generated=generated,
                            basis_required=(
                                basis_required if block_type == ITEM_BLOCK_TYPE_BASIS else False
                            ),
                            force_review_required=(
                                force_review and block_type == ITEM_BLOCK_TYPE_BASIS
                            ),
                        )
                        write_editorial_audit(
                            event_type=(
                                "EDITORIAL_GENERATED"
                                if existing is None
                                else "EDITORIAL_REGENERATED"
                            ),
                            actor_user_id=user_id,
                            metadata={
                                "order_id": int(order_id),
                                "item_id": item_id,
                                "block_type": block_type,
                                "locale": locale,
                                "user_id": user_id,
                                "result": "ok",
                                "generator_version": generated["generator_version"],
                                "old_review_status": old_status or None,
                                "new_review_status": new_status,
                            },
                            conn=conn,
                        )
                    except Exception:
                        mark_item_block_failed(
                            conn,
                            order_item_id=item_id,
                            locale=locale,
                            block_type=block_type,
                            basis_required=(
                                basis_required if block_type == ITEM_BLOCK_TYPE_BASIS else False
                            ),
                        )
                        write_editorial_audit(
                            event_type="EDITORIAL_GENERATED",
                            actor_user_id=user_id,
                            success=False,
                            metadata={
                                "order_id": int(order_id),
                                "item_id": item_id,
                                "block_type": block_type,
                                "locale": locale,
                                "user_id": user_id,
                                "result": "GENERATION_FAILED",
                                "generator_version": None,
                                "old_review_status": None,
                                "new_review_status": REVIEW_STATUS_GENERATION_FAILED,
                            },
                            conn=conn,
                        )

        touch_order_updated_at(conn, int(order_id))

    # Lazy import avoids cycle with service (which does not import this module).
    from app.services.personnel_orders_editorial.service import get_editorial_state

    return get_editorial_state(int(order_id))
