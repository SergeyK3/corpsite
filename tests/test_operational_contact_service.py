# tests/test_operational_contact_service.py
"""OPS-026.4 — operational contact ensure helper."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.operational_contact_service import (
    ensure_operational_contact_for_employee,
    find_operational_contact_id,
    normalize_contact_full_name,
    parse_telegram_numeric_id,
)
from tests.conftest import insert_returning_id, table_exists
from tests.test_employee_documents_routes import _create_employee, _phase_1a_available


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def test_normalize_contact_full_name():
    assert normalize_contact_full_name("  Нурбеков  Бахдат ") == "нурбеков бахдат"


def test_parse_telegram_numeric_id():
    assert parse_telegram_numeric_id("1051243522") == 1051243522
    assert parse_telegram_numeric_id(None) is None


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_ensure_operational_contact_is_idempotent(seed):
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    employee_id = None
    contact_id = None
    try:
        with engine.begin() as conn:
            if not table_exists(conn, "contacts"):
                pytest.skip("contacts table missing")
            employee_id = _create_employee(
                conn,
                full_name="Ops026 Contact Idempotent",
                org_unit_id=int(seed["unit_id"]),
            )
            first = ensure_operational_contact_for_employee(
                conn,
                employee_id=employee_id,
                full_name="Ops026 Contact Idempotent",
            )
            second = ensure_operational_contact_for_employee(
                conn,
                employee_id=employee_id,
                full_name="Ops026 Contact Idempotent",
            )
            contact_id = first.contact_id
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.contacts
                    WHERE lower(replace(trim(full_name), 'ё', 'е')) = :name
                      AND COALESCE(is_deleted, false) = false
                    """
                ),
                {"name": normalize_contact_full_name("Ops026 Contact Idempotent")},
            ).scalar_one()

        assert first.created is True
        assert first.contact_id is not None
        assert second.created is False
        assert second.existed is True
        assert second.contact_id == first.contact_id
        assert int(count) == 1
    finally:
        with engine.begin() as conn:
            if contact_id:
                conn.execute(text("DELETE FROM public.contacts WHERE contact_id = :id"), {"id": contact_id})
            if employee_id:
                conn.execute(text("DELETE FROM public.employees WHERE employee_id = :id"), {"id": employee_id})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_find_operational_contact_by_telegram(seed):
    if not _phase_1a_available():
        pytest.skip("employees tables missing")

    contact_id = None
    try:
        with engine.begin() as conn:
            if not table_exists(conn, "contacts"):
                pytest.skip("contacts table missing")
            contact_id = insert_returning_id(
                conn,
                table="contacts",
                id_col="contact_id",
                values={
                    "full_name": "Telegram Match Contact",
                    "telegram_numeric_id": 4242424242,
                    "is_deleted": False,
                },
            )
            found = find_operational_contact_id(
                conn,
                person_id=None,
                telegram_numeric_id=4242424242,
                full_name="Other Name",
            )
        assert found == contact_id
    finally:
        with engine.begin() as conn:
            if contact_id:
                conn.execute(text("DELETE FROM public.contacts WHERE contact_id = :id"), {"id": contact_id})
