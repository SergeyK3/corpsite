"""Focused coverage for typed document-only item corrections."""
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_order_document_item_service import list_document_items, patch_document_item
from app.services.personnel_order_document_review_service import (
    PersonnelOrderDocumentReviewConflictError,
    mutate_document_review,
)


def _create_order(seed, *, status="DRAFT", second_item=False):
    actor = int(seed["initiator_user_id"])
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        employee_ids = conn.execute(text("SELECT employee_id FROM employees ORDER BY employee_id LIMIT 2")).scalars().all()
        if len(employee_ids) < 2:
            raise RuntimeError("Test database needs two employees for item correction coverage.")
        employee_id, alternate_employee_id = (int(employee_ids[0]), int(employee_ids[1]))
        order_id = int(conn.execute(text("""
            INSERT INTO personnel_orders(order_number, order_date, order_type_code, status, source_mode, created_by)
            VALUES (:number, :day, 'HIRE', :status, 'PAPER', :actor)
            RETURNING order_id
        """), {"number": f"ITEM-{suffix}", "day": date(2026, 9, 1), "status": status, "actor": actor}).scalar_one())
        item_id = int(conn.execute(text("""
            INSERT INTO personnel_order_items(order_id, item_number, item_type_code, employee_id, effective_date, payload)
            VALUES (:order_id, 1, 'HIRE', :employee_id, :effective_date, '{}'::jsonb)
            RETURNING item_id
        """), {"order_id": order_id, "employee_id": employee_id, "effective_date": date(2026, 9, 2)}).scalar_one())
        if second_item:
            conn.execute(text("""
                INSERT INTO personnel_order_items(order_id, item_number, item_type_code, employee_id, effective_date, payload)
                VALUES (:order_id, 2, 'HIRE', :employee_id, :effective_date, '{}'::jsonb)
            """), {"order_id": order_id, "employee_id": employee_id, "effective_date": date(2026, 9, 2)})
        for locale in ("ru", "kk"):
            conn.execute(text("INSERT INTO personnel_order_editorial_blocks(order_id,locale,block_type,generated_text,review_status) VALUES(:id,:locale,'title','t','CURRENT')"), {"id": order_id, "locale": locale})
    return order_id, item_id, employee_id, alternate_employee_id, actor


def _clean(order_id):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM personnel_order_lifecycle_audit WHERE order_id=:id"), {"id": order_id})
        conn.execute(text("DELETE FROM personnel_order_editorial_blocks WHERE order_id=:id"), {"id": order_id})
        conn.execute(text("DELETE FROM personnel_order_item_editorial_blocks WHERE order_item_id IN (SELECT item_id FROM personnel_order_items WHERE order_id=:id)"), {"id": order_id})
        conn.execute(text("DELETE FROM personnel_order_item_bases WHERE order_item_id IN (SELECT item_id FROM personnel_order_items WHERE order_id=:id)"), {"id": order_id})
        conn.execute(text("DELETE FROM personnel_order_evidence_scopes WHERE order_id=:id"), {"id": order_id})
        conn.execute(text("DELETE FROM personnel_order_items WHERE order_id=:id"), {"id": order_id})
        conn.execute(text("DELETE FROM personnel_orders WHERE order_id=:id"), {"id": order_id})


def _patch(order_id, item_id, current_employee_id, actor, **overrides):
    return patch_document_item(
        order_id=order_id, item_id=item_id, expected_document_revision=overrides.pop("revision", 1),
        item_type_code=overrides.pop("item_type", "TRANSFER"), employee_id=overrides.pop("employee_id", current_employee_id),
        effective_date=overrides.pop("effective_date", date(2026, 9, 3)), reason_code=overrides.pop("reason_code", None),
        reason_text=overrides.pop("reason_text", None),
        document_subject_context=overrides.pop("document_subject_context", None), actor_user_id=actor,
    )


def test_item_change_recalculates_single_header_and_safe_projection(seed):
    order_id, item_id, employee_id, alternate_employee_id, actor = _create_order(seed)
    try:
        result = _patch(order_id, item_id, employee_id, actor, employee_id=alternate_employee_id)
        assert result["no_op"] is False
        assert result["header_type_code"] == "TRANSFER"
        safe = list_document_items(order_id=order_id)
        assert safe["items"][0] == {"item_id": item_id, "item_number": 1, "item_type_code": "TRANSFER", "employee_id": alternate_employee_id, "employee_name": safe["items"][0]["employee_name"], "org_unit_name": safe["items"][0]["org_unit_name"], "position_name": safe["items"][0]["position_name"], "specialty": None, "rate": None, "needs_employee_link": False, "effective_date": "2026-09-03"}
        assert "payload" not in safe["items"][0]
    finally:
        _clean(order_id)


def test_document_context_is_typed_and_regenerates_bilingual_item_blocks(seed):
    order_id, item_id, employee_id, _alternate_employee_id, actor = _create_order(seed)
    try:
        result = _patch(
            order_id, item_id, employee_id, actor,
            item_type="RETURN_FROM_CHILDCARE_LEAVE",
            effective_date=date(2026, 8, 5),
            document_subject_context={
                "position_name": "врач (ординатор)",
                "org_unit_name": "Инсультный центр",
                "specialty": "невропатолог",
            },
        )
        assert result["no_op"] is False
        with engine.connect() as conn:
            payload = conn.execute(text("SELECT payload FROM personnel_order_items WHERE item_id=:id"), {"id": item_id}).scalar_one()
            blocks = conn.execute(text("SELECT locale, generated_text FROM personnel_order_item_editorial_blocks WHERE order_item_id=:id AND block_type='body' ORDER BY locale"), {"id": item_id}).mappings().all()
        assert payload["source_position_name"] == "врач (ординатор)"
        assert payload["source_org_unit_name"] == "Инсультный центр"
        assert payload["document_specialty"] == "невропатолог"
        assert {row["locale"] for row in blocks} == {"kk", "ru"}
        assert all("2026" in row["generated_text"] for row in blocks)
        safe = list_document_items(order_id=order_id)["items"][0]
        assert safe["position_name"] == "врач (ординатор)"
        assert safe["org_unit_name"] == "Инсультный центр"
        assert safe["specialty"] == "невропатолог"
        assert "payload" not in safe
    finally:
        _clean(order_id)


def test_mixed_item_types_recalculate_header_to_composite_and_noop(seed):
    order_id, item_id, employee_id, _alternate_employee_id, actor = _create_order(seed, second_item=True)
    try:
        result = _patch(order_id, item_id, employee_id, actor)
        assert result["header_type_code"] == "COMPOSITE"
        noop = _patch(order_id, item_id, employee_id, actor, revision=2)
        assert noop["no_op"] is True and noop["audit_event_ids"] == []
    finally:
        _clean(order_id)


@pytest.mark.parametrize("status", ["REGISTERED", "SIGNED"])
def test_registered_or_signed_requires_document_correction_reason(seed, status):
    order_id, item_id, employee_id, _alternate_employee_id, actor = _create_order(seed, status=status)
    try:
        with pytest.raises(ValueError, match="CORRECTION_REASON_REQUIRED"):
            _patch(order_id, item_id, employee_id, actor)
        assert _patch(order_id, item_id, employee_id, actor, reason_code="CORRECTION", reason_text="Verified")["no_op"] is False
    finally:
        _clean(order_id)


def test_conflict_reopens_confirmed_document_and_preserves_hr_facts(seed):
    order_id, item_id, employee_id, _alternate_employee_id, actor = _create_order(seed, status="REGISTERED")
    try:
        mutate_document_review(order_id, action="DOCUMENT_CONFIRMED", expected_document_revision=1, reason_code="HR", note=None, actor_user_id=actor)
        with pytest.raises(PersonnelOrderDocumentReviewConflictError):
            _patch(order_id, item_id, employee_id, actor, revision=1, reason_code="CORRECTION", reason_text="Verified")
        with engine.connect() as conn:
            before = tuple(int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()) for table in ("employee_events", "person_assignments"))
        result = _patch(order_id, item_id, employee_id, actor, revision=2, reason_code="CORRECTION", reason_text="Verified")
        assert result["resulting_document_revision"] == 3 and result["document_review_state"] == "NEEDS_REVIEW"
        with engine.connect() as conn:
            actions = conn.execute(text("SELECT action FROM personnel_order_lifecycle_audit WHERE order_id=:id ORDER BY id"), {"id": order_id}).scalars().all()
            after = tuple(int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()) for table in ("employee_events", "person_assignments"))
        assert actions == ["DOCUMENT_CONFIRMED", "ITEM_UPDATED", "DOCUMENT_REOPENED"]
        assert before == after == (0, 0)
    finally:
        _clean(order_id)
