"""Focused tests for append-only personnel-order document review."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text
from fastapi import HTTPException
from pydantic import ValidationError

from app.db.engine import engine
from app.services.personnel_order_document_review_service import (
    PersonnelOrderDocumentReviewConflictError,
    PersonnelOrderDocumentReviewValidationError,
    get_document_review,
    mutate_document_review,
)
from app.directory.personnel_orders_schemas import PersonnelOrderDocumentReviewConfirmIn
from app.directory.personnel_orders_routes import (
    confirm_personnel_order_document_review_route,
    reopen_personnel_order_document_review_route,
)


def _create_reviewable_order(seed) -> tuple[int, int]:
    suffix = uuid4().hex[:10]
    actor = int(seed["initiator_user_id"])
    with engine.begin() as conn:
        order_id = int(conn.execute(text("""INSERT INTO personnel_orders
            (order_number, order_date, order_type_code, status, source_mode, created_by)
            VALUES (:number, :day, 'HIRE', 'REGISTERED', 'PAPER', :actor) RETURNING order_id"""),
            {"number": f"DOC-REVIEW-{suffix}", "day": date(2026, 9, 1), "actor": actor}).scalar_one())
        item_id = int(conn.execute(text("""INSERT INTO personnel_order_items
            (order_id, item_number, item_type_code, employee_id, payload)
            VALUES (:order_id, 1, 'HIRE', NULL, '{"unresolved_subject":"Temporary subject"}'::jsonb)
            RETURNING item_id"""), {"order_id": order_id}).scalar_one())
        for locale in ("ru", "kk"):
            conn.execute(text("""INSERT INTO personnel_order_editorial_blocks
                (order_id, locale, block_type, generated_text, review_status)
                VALUES (:order_id, :locale, 'title', 'title', 'CURRENT')"""), {"order_id": order_id, "locale": locale})
            conn.execute(text("""INSERT INTO personnel_order_item_editorial_blocks
                (order_item_id, locale, block_type, generated_text, review_status)
                VALUES (:item_id, :locale, 'body', 'body', 'CURRENT')"""), {"item_id": item_id, "locale": locale})
    return order_id, actor


def _cleanup(order_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM personnel_order_lifecycle_audit WHERE order_id=:id"), {"id": order_id})
        conn.execute(text("DELETE FROM personnel_order_item_editorial_blocks WHERE order_item_id IN (SELECT item_id FROM personnel_order_items WHERE order_id=:id)"), {"id": order_id})
        conn.execute(text("DELETE FROM personnel_order_editorial_blocks WHERE order_id=:id"), {"id": order_id})
        conn.execute(text("DELETE FROM personnel_order_items WHERE order_id=:id"), {"id": order_id})
        conn.execute(text("DELETE FROM personnel_orders WHERE order_id=:id"), {"id": order_id})


def test_document_review_confirm_noop_reopen_is_append_only_and_document_only(seed) -> None:
    order_id, actor = _create_reviewable_order(seed)
    try:
        before = get_document_review(order_id)
        assert before["state"] == "NEEDS_REVIEW" and before["document_revision"] == 1
        confirmed = mutate_document_review(order_id, action="DOCUMENT_CONFIRMED", expected_document_revision=1, reason_code="HR_REVIEW", note=None, actor_user_id=actor)
        assert confirmed["state"] == "CONFIRMED" and confirmed["document_revision"] == 2
        again = mutate_document_review(order_id, action="DOCUMENT_CONFIRMED", expected_document_revision=2, reason_code="HR_REVIEW", note=None, actor_user_id=actor)
        assert again["document_revision"] == 2
        reopened = mutate_document_review(order_id, action="DOCUMENT_REOPENED", expected_document_revision=2, reason_code="CORRECTION", note="Needs check", actor_user_id=actor)
        assert reopened["state"] == "NEEDS_REVIEW" and reopened["document_revision"] == 3
        with engine.connect() as conn:
            actions = conn.execute(text("SELECT action FROM personnel_order_lifecycle_audit WHERE order_id=:id ORDER BY id"), {"id": order_id}).scalars().all()
            order = conn.execute(text("SELECT status, document_revision FROM personnel_orders WHERE order_id=:id"), {"id": order_id}).one()
            assert actions == ["DOCUMENT_CONFIRMED", "DOCUMENT_REOPENED"]
            assert order == ("REGISTERED", 3)
            assert conn.execute(text("SELECT COUNT(*) FROM employee_events WHERE order_id=:id"), {"id": order_id}).scalar_one() == 0
    finally:
        _cleanup(order_id)


def test_document_review_rejects_conflict_blockers_and_empty_reopen_note(seed) -> None:
    order_id, actor = _create_reviewable_order(seed)
    try:
        with pytest.raises(PersonnelOrderDocumentReviewConflictError):
            mutate_document_review(order_id, action="DOCUMENT_CONFIRMED", expected_document_revision=99, reason_code="HR_REVIEW", note=None, actor_user_id=actor)
        with pytest.raises(PersonnelOrderDocumentReviewValidationError):
            mutate_document_review(order_id, action="DOCUMENT_REOPENED", expected_document_revision=1, reason_code="CORRECTION", note="", actor_user_id=actor)
        with engine.begin() as conn:
            conn.execute(text("UPDATE personnel_orders SET order_number=NULL WHERE order_id=:id"), {"id": order_id})
        with pytest.raises(PersonnelOrderDocumentReviewValidationError) as exc:
            mutate_document_review(order_id, action="DOCUMENT_CONFIRMED", expected_document_revision=1, reason_code="HR_REVIEW", note=None, actor_user_id=actor)
        assert {row["code"] for row in exc.value.blockers} == {"MISSING_ORDER_NUMBER"}
    finally:
        _cleanup(order_id)


def _blocker(order_id: int, actor: int) -> set[str]:
    with pytest.raises(PersonnelOrderDocumentReviewValidationError) as exc:
        mutate_document_review(order_id, action="DOCUMENT_CONFIRMED", expected_document_revision=1, reason_code="HR_REVIEW", note=None, actor_user_id=actor)
    return {row["code"] for row in exc.value.blockers}


def test_document_review_blocks_missing_date(seed) -> None:
    order_id, actor = _create_reviewable_order(seed)
    try:
        with engine.begin() as conn: conn.execute(text("UPDATE personnel_orders SET order_date=NULL WHERE order_id=:id"), {"id": order_id})
        assert "MISSING_ORDER_DATE" in _blocker(order_id, actor)
    finally: _cleanup(order_id)


def test_document_review_blocks_missing_active_items(seed) -> None:
    order_id, actor = _create_reviewable_order(seed)
    try:
        with engine.begin() as conn: conn.execute(text("UPDATE personnel_order_items SET item_status='VOIDED', void_reason='test', voided_at=now(), voided_by=:actor WHERE order_id=:id"), {"id": order_id, "actor": actor})
        assert "MISSING_ACTIVE_ITEMS" in _blocker(order_id, actor)
    finally: _cleanup(order_id)


def test_document_review_blocks_item_without_employee_or_unresolved_subject(seed) -> None:
    order_id, actor = _create_reviewable_order(seed)
    try:
        with engine.begin() as conn: conn.execute(text("UPDATE personnel_order_items SET payload='{}'::jsonb WHERE order_id=:id"), {"id": order_id})
        assert "MISSING_SUBJECT" in _blocker(order_id, actor)
    finally: _cleanup(order_id)


@pytest.mark.parametrize("locale", ["ru", "kk"])
def test_document_review_blocks_missing_locale_presentation(seed, locale: str) -> None:
    order_id, actor = _create_reviewable_order(seed)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM personnel_order_editorial_blocks WHERE order_id=:id AND locale=:locale"), {"id": order_id, "locale": locale})
            conn.execute(text("DELETE FROM personnel_order_item_editorial_blocks WHERE order_item_id IN (SELECT item_id FROM personnel_order_items WHERE order_id=:id) AND locale=:locale"), {"id": order_id, "locale": locale})
        assert any(row.get("code") == "MISSING_DOCUMENT_PRESENTATION" and row.get("locale") == locale for row in get_document_review(order_id)["blockers"])
    finally: _cleanup(order_id)


def test_document_review_editorial_and_docx_are_warnings_not_blockers(seed) -> None:
    order_id, _ = _create_reviewable_order(seed)
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE personnel_orders SET storage_json=jsonb_build_object('reconstruction_status','NEEDS_DOCX_REVIEW') WHERE order_id=:id"), {"id": order_id})
            conn.execute(text("UPDATE personnel_order_editorial_blocks SET review_status='REVIEW_REQUIRED' WHERE order_id=:id AND locale='ru'"), {"id": order_id})
        review = get_document_review(order_id)
        assert review["blockers"] == []
        assert {row["code"] for row in review["warnings"]} == {"NEEDS_DOCX_REVIEW", "EDITORIAL_REVIEW_REQUIRED"}
    finally: _cleanup(order_id)


def test_document_review_schema_rejects_client_actor_and_route_denies_ordinary_user(seed) -> None:
    with pytest.raises(ValidationError):
        PersonnelOrderDocumentReviewConfirmIn(expected_document_revision=1, reason_code="HR", actor_user_id=999)
    order_id, _ = _create_reviewable_order(seed)
    try:
        with pytest.raises(HTTPException) as confirm_exc:
            confirm_personnel_order_document_review_route(PersonnelOrderDocumentReviewConfirmIn(expected_document_revision=1, reason_code="HR"), order_id=order_id, user={"user_id": 999999})
        assert confirm_exc.value.status_code == 403
        with pytest.raises(HTTPException) as reopen_exc:
            reopen_personnel_order_document_review_route(type("Payload", (), {"expected_document_revision": 1, "reason_code": "HR", "note": "Reason"})(), order_id=order_id, user={"user_id": 999999})
        assert reopen_exc.value.status_code == 403
    finally: _cleanup(order_id)


def test_document_review_reopen_noop_and_latest_event_tie_breaks_by_primary_key(seed) -> None:
    order_id, actor = _create_reviewable_order(seed)
    try:
        mutate_document_review(order_id, action="DOCUMENT_CONFIRMED", expected_document_revision=1, reason_code="HR", note=None, actor_user_id=actor)
        mutate_document_review(order_id, action="DOCUMENT_REOPENED", expected_document_revision=2, reason_code="FIX", note="Reason", actor_user_id=actor)
        noop = mutate_document_review(order_id, action="DOCUMENT_REOPENED", expected_document_revision=3, reason_code="FIX", note="Reason", actor_user_id=actor)
        assert noop["document_revision"] == 3
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM personnel_order_lifecycle_audit WHERE order_id=:id"), {"id": order_id}).scalar_one() == 2
    finally: _cleanup(order_id)


def test_document_review_mutations_change_only_revision_and_append_only_audit(seed) -> None:
    order_id, actor = _create_reviewable_order(seed)
    try:
        with engine.connect() as conn:
            before = conn.execute(text("""SELECT (SELECT count(*) FROM personnel_order_items WHERE order_id=:id),
                (SELECT count(*) FROM employee_events WHERE order_id=:id),
                (SELECT count(*) FROM person_assignments),
                (SELECT count(*) FROM personnel_order_acknowledgement_events WHERE order_id=:id),
                (SELECT count(*) FROM personnel_order_editorial_blocks WHERE order_id=:id),
                status, signed_by_name, signed_by_position FROM personnel_orders WHERE order_id=:id"""), {"id": order_id}).one()
        mutate_document_review(order_id, action="DOCUMENT_CONFIRMED", expected_document_revision=1, reason_code="HR", note=None, actor_user_id=actor)
        mutate_document_review(order_id, action="DOCUMENT_REOPENED", expected_document_revision=2, reason_code="FIX", note="Reason", actor_user_id=actor)
        with engine.connect() as conn:
            after = conn.execute(text("""SELECT (SELECT count(*) FROM personnel_order_items WHERE order_id=:id),
                (SELECT count(*) FROM employee_events WHERE order_id=:id), (SELECT count(*) FROM person_assignments),
                (SELECT count(*) FROM personnel_order_acknowledgement_events WHERE order_id=:id),
                (SELECT count(*) FROM personnel_order_editorial_blocks WHERE order_id=:id), status, signed_by_name, signed_by_position, document_revision FROM personnel_orders WHERE order_id=:id"""), {"id": order_id}).one()
        assert after[:8] == before and after[8] == 3
    finally: _cleanup(order_id)
