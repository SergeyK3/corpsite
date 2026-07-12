"""Synthetic PO detail fixtures for adapter tests (UDE-008)."""
from __future__ import annotations

from typing import Any, Dict


def synthetic_order_header(
    *,
    order_id: int = 1001,
    status: str = "DRAFT",
    is_archived: bool = False,
) -> Dict[str, Any]:
    return {
        "order_id": order_id,
        "order_number": "SYN-1001",
        "order_date": "2026-07-12",
        "order_type_code": "HIRE",
        "order_class": "PERSONNEL",
        "status": status,
        "source_mode": "PAPER",
        "legal_basis_article": "33",
        "signed_by_employee_id": None,
        "signed_by_name": None,
        "signed_by_position": None,
        "executor_name": None,
        "basis_summary": "Synthetic basis",
        "comment": None,
        "void_reason": None,
        "voided_at": None,
        "voided_by": None,
        "created_by": 1,
        "created_at": "2026-07-12T10:00:00+00:00",
        "updated_at": "2026-07-12T10:00:00+00:00",
        "is_archived": is_archived,
        "archive_summary_at": "2026-07-12T11:00:00+00:00" if is_archived else None,
        "archive_summary_by_name": "Synthetic Archiver" if is_archived else None,
        "archive_summary_reason": "completed" if is_archived else None,
    }


def synthetic_item(
    *,
    item_id: int = 501,
    order_id: int = 1001,
    item_type_code: str = "HIRE",
    employee_id: int | None = 42,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "item_id": item_id,
        "order_id": order_id,
        "item_number": 1,
        "item_type_code": item_type_code,
        "item_status": "ACTIVE",
        "employee_id": employee_id,
        "employee_name": "Synthetic Employee" if employee_id else None,
        "org_unit_id": 10,
        "org_unit_name": "Synthetic Unit",
        "effective_date": "2026-07-15",
        "period_start": None,
        "period_end": None,
        "payload": payload or {"employment_rate": 1.0},
        "void_reason": None,
        "voided_at": None,
        "voided_by": None,
        "created_at": "2026-07-12T10:00:00+00:00",
    }


def synthetic_detail(**overrides: Any) -> Dict[str, Any]:
    header = synthetic_order_header()
    detail = {
        "order": header,
        "items": [synthetic_item()],
        "localized_texts": [
            {
                "localized_text_id": 1,
                "order_id": header["order_id"],
                "locale": "ru",
                "title": "RU title",
                "preamble": None,
                "body_text": None,
                "render_version": 1,
                "is_authoritative": True,
                "created_at": "2026-07-12T10:00:00+00:00",
                "updated_at": "2026-07-12T10:00:00+00:00",
            },
            {
                "localized_text_id": 2,
                "order_id": header["order_id"],
                "locale": "kk",
                "title": "KK title",
                "preamble": None,
                "body_text": None,
                "render_version": 1,
                "is_authoritative": True,
                "created_at": "2026-07-12T10:00:00+00:00",
                "updated_at": "2026-07-12T10:00:00+00:00",
            },
        ],
        "attachments": [],
        "prints": [],
        "events": [],
    }
    detail.update(overrides)
    return detail


def synthetic_editorial_block(
    *,
    block_id: int = 9001,
    locale: str = "ru",
    block_type: str = "title",
    override_text: str | None = None,
) -> Dict[str, Any]:
    return {
        "block_id": block_id,
        "scope": "order",
        "order_item_id": None,
        "locale": locale,
        "block_type": block_type,
        "generated_text": "Generated title",
        "override_text": override_text,
        "effective_text": override_text or "Generated title",
        "generator_key": "title",
        "generator_version": "1",
        "source_fingerprint": "fp-1",
        "review_status": "CURRENT",
        "basis_required": None,
        "editable": True,
        "revision": 1,
        "generated_at": "2026-07-12T10:00:00+00:00",
        "edited_at": None,
        "edited_by_user_id": None,
    }


def synthetic_editorial_state(order_id: int = 1001) -> Dict[str, Any]:
    return {
        "order_id": order_id,
        "order_status": "DRAFT",
        "editable": True,
        "order_blocks": [
            synthetic_editorial_block(block_id=9001, locale="ru"),
            synthetic_editorial_block(block_id=9002, locale="kk", block_type="title"),
        ],
        "items": [
            {
                "order_item_id": 501,
                "item_number": 1,
                "item_type_code": "HIRE",
                "basis_required": True,
                "blocks": [
                    synthetic_editorial_block(block_id=9003, locale="ru", block_type="body"),
                ],
            }
        ],
    }


def synthetic_audit_row(
    *,
    event_id: int = 7001,
    action: str = "CANCEL",
) -> Dict[str, Any]:
    return {
        "id": event_id,
        "order_id": 1001,
        "action": action,
        "previous_status": "DRAFT",
        "new_status": "VOIDED",
        "previous_void_kind": None,
        "new_void_kind": "CANCEL",
        "actor_user_id": 1,
        "reason_code": "created_by_mistake",
        "reason_text": "Synthetic cancel",
        "metadata_json": {"permission_used": "PERSONNEL_ORDERS_CANCEL_OWN"},
        "created_at": "2026-07-12T12:00:00+00:00",
    }
