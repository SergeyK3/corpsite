"""Contract tests for the private, self-scoped personnel-orders projection."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api import ppr_self_orders_router as subject
from app.auth import get_current_user
from app.db.engine import engine
from app.main import app
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available, require_ppr_schema


def _row(*, status: str = "DRAFT", review: bool = False) -> dict[str, object]:
    return {
        "order_id": 11, "order_number": "11-К", "order_date": date(2026, 9, 1),
        "order_type_code": "HIRE", "status": status, "title": "О приёме", "item_text": "Принять текущего работника.",
        "needs_review": review,
    }


def test_my_orders_api_returns_only_safe_personal_projection(monkeypatch) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    monkeypatch.setattr(subject, "_employee_for_user", lambda user: ("READY", 42))
    monkeypatch.setattr(subject, "_safe_rows", lambda employee_id, **kwargs: [_row()])
    try:
        response = TestClient(app).get("/api/ppr/me/orders?employee_id=9999")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200
    assert response.json() == {"status": "READY", "orders": [{
        "order_id": 11, "order_number": "11-К", "order_date": "2026-09-01", "title": "О приёме",
        "item_text": "Принять текущего работника.", "confirmation_status": "UNCONFIRMED",
    }]}
    # Contract intentionally has neither the resolved employee ID nor any
    # other employee/item/evidence/editorial data.
    assert "employee_id" not in response.text
    assert "payload" not in response.text


def test_my_order_confirmation_uses_status_and_existing_review_signal(monkeypatch) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    monkeypatch.setattr(subject, "_employee_for_user", lambda user: ("READY", 42))
    monkeypatch.setattr(subject, "_safe_rows", lambda employee_id, **kwargs: [_row(status="REGISTERED")])
    try:
        confirmed = TestClient(app).get("/api/ppr/me/orders/11")
        monkeypatch.setattr(subject, "_safe_rows", lambda employee_id, **kwargs: [_row(status="REGISTERED", review=True)])
        review = TestClient(app).get("/api/ppr/me/orders/11")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert confirmed.json()["confirmation_status"] == "CONFIRMED"
    assert confirmed.json()["warning"] is None
    assert review.json()["confirmation_status"] == "UNCONFIRMED"
    assert "ещё не подтверждён" in review.json()["warning"]


def test_my_orders_composite_title_uses_only_current_employee_item_types(monkeypatch) -> None:
    row = _row(status="REGISTERED")
    row["title"] = "COMPOSITE"
    row["item_text"] = None
    row["employee_item_types"] = ["HIRE", "CONCURRENT_DUTY_START"]
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    monkeypatch.setattr(subject, "_employee_for_user", lambda user: ("READY", 42))
    monkeypatch.setattr(subject, "_safe_rows", lambda employee_id, **kwargs: [row])
    try:
        response = TestClient(app).get("/api/ppr/me/orders/11")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200
    assert response.json()["title"] == "Приём на работу; Совмещение (начало)"
    assert response.json()["confirmation_status"] == "CONFIRMED"
    assert response.json()["item_text"] is None
    assert "COMPOSITE" not in response.text


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_my_orders_use_session_employee_when_person_link_is_missing(seed) -> None:
    """An Employee-only account remains safe: items are still Employee-scoped."""
    require_ppr_schema()
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_orders"):
            pytest.skip("personnel order schema missing")
        user_id = int(seed["initiator_user_id"])
        previous_employee_id = conn.execute(
            text("SELECT employee_id FROM public.users WHERE user_id=:id"), {"id": user_id}
        ).scalar_one()
        suffix = uuid4().hex[:8]
        own_employee = insert_employee(conn, full_name=f"Employee only {suffix}")
        other_employee = insert_employee(conn, full_name=f"Other employee {suffix}")
        conn.execute(text("UPDATE public.users SET employee_id=:employee WHERE user_id=:user"), {"employee": own_employee, "user": user_id})
        order_id = int(conn.execute(text("""INSERT INTO public.personnel_orders(order_number,order_date,order_type_code,status,source_mode,created_by)
            VALUES(:number,:date,'COMPOSITE','DRAFT','PAPER',:user) RETURNING order_id"""), {"number": f"NO-PERSON-{suffix}", "date": date(2026, 9, 2), "user": user_id}).scalar_one())
        own_item = int(conn.execute(text("""INSERT INTO public.personnel_order_items(order_id,item_number,item_type_code,employee_id,payload)
            VALUES(:order,1,'HIRE',:employee,'{}'::jsonb) RETURNING item_id"""), {"order": order_id, "employee": own_employee}).scalar_one())
        other_item = int(conn.execute(text("""INSERT INTO public.personnel_order_items(order_id,item_number,item_type_code,employee_id,payload)
            VALUES(:order,2,'HIRE',:employee,'{}'::jsonb) RETURNING item_id"""), {"order": order_id, "employee": other_employee}).scalar_one())
        conn.execute(text("INSERT INTO public.personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text) VALUES(:item,'ru','body',:body)"), {"item": own_item, "body": "Только собственный пункт."})
        conn.execute(text("INSERT INTO public.personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text) VALUES(:item,'ru','body',:body)"), {"item": other_item, "body": "Чужой пункт."})
    try:
        app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}
        client = TestClient(app)
        listing = client.get("/api/ppr/me/orders?employee_id=999999")
        detail = client.get(f"/api/ppr/me/orders/{order_id}")
        for response in (listing, detail):
            assert response.status_code == 200
            assert "Только собственный пункт." in response.text
            assert "Чужой пункт." not in response.text
            for forbidden in ("employee_id", "payload", "evidence", "assumptions", "editorial"):
                assert forbidden not in response.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.personnel_order_item_editorial_blocks WHERE order_item_id IN (:own,:other)"), {"own": own_item, "other": other_item})
            conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id=:id"), {"id": order_id})
            conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id})
            conn.execute(text("UPDATE public.users SET employee_id=:employee WHERE user_id=:user"), {"employee": previous_employee_id, "user": user_id})
            conn.execute(text("DELETE FROM public.employees WHERE employee_id IN (:own,:other)"), {"own": own_employee, "other": other_employee})


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_my_orders_integration_isolates_two_users_and_multi_item_order(seed) -> None:
    """The database query, rather than a mocked service, enforces item isolation."""
    require_ppr_schema()
    with engine.begin() as conn:
        if not table_exists(conn, "personnel_orders"):
            pytest.skip("personnel order schema missing")
        owner_user = int(seed["initiator_user_id"])
        role_id = conn.execute(text("SELECT role_id FROM public.users WHERE user_id=:id"), {"id": owner_user}).scalar_one()
        suffix = uuid4().hex[:8]
        other_user = int(conn.execute(text("""INSERT INTO public.users(full_name, role_id, is_active, login)
            VALUES(:name,:role,TRUE,:login) RETURNING user_id"""), {"name": f"Order other {suffix}", "role": role_id, "login": f"orders-other-{suffix}"}).scalar_one())
        owner_person = insert_person(conn, full_name=f"Private Alice {suffix}")
        other_person = insert_person(conn, full_name=f"Private Bob {suffix}")
        owner_employee = insert_employee(conn, full_name=f"Private Alice {suffix}", person_id=owner_person)
        other_employee = insert_employee(conn, full_name=f"Private Bob {suffix}", person_id=other_person)
        conn.execute(text("UPDATE public.users SET employee_id=:employee WHERE user_id=:user"), {"employee": owner_employee, "user": owner_user})
        conn.execute(text("UPDATE public.users SET employee_id=:employee WHERE user_id=:user"), {"employee": other_employee, "user": other_user})
        order_id = int(conn.execute(text("""INSERT INTO public.personnel_orders(order_number,order_date,order_type_code,status,source_mode,created_by)
            VALUES(:number,:date,'COMPOSITE','DRAFT','PAPER',:user) RETURNING order_id"""), {"number": f"SELF-{suffix}", "date": date(2026, 9, 1), "user": owner_user}).scalar_one())
        owner_item = int(conn.execute(text("""INSERT INTO public.personnel_order_items(order_id,item_number,item_type_code,employee_id,payload)
            VALUES(:order,1,'HIRE',:employee,'{}'::jsonb) RETURNING item_id"""), {"order": order_id, "employee": owner_employee}).scalar_one())
        other_item = int(conn.execute(text("""INSERT INTO public.personnel_order_items(order_id,item_number,item_type_code,employee_id,payload)
            VALUES(:order,2,'HIRE',:employee,'{}'::jsonb) RETURNING item_id"""), {"order": order_id, "employee": other_employee}).scalar_one())
        for item, name in ((owner_item, "Alice"), (other_item, "Bob")):
            conn.execute(text("""INSERT INTO public.personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text)
            VALUES(:item,'ru','body',:body)"""), {"item": item, "body": f"Только пункт {name}."})
    try:
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": owner_user}
        owner_list = client.get("/api/ppr/me/orders"); owner_detail = client.get(f"/api/ppr/me/orders/{order_id}")
        app.dependency_overrides[get_current_user] = lambda: {"user_id": other_user}
        other_list = client.get("/api/ppr/me/orders"); other_detail = client.get(f"/api/ppr/me/orders/{order_id}")
        for response, own, foreign in ((owner_list, "Alice", "Bob"), (owner_detail, "Alice", "Bob"), (other_list, "Bob", "Alice"), (other_detail, "Bob", "Alice")):
            assert response.status_code == 200
            assert own in response.text and foreign not in response.text
            for forbidden in ("employee_id", "payload", "evidence", "assumptions", "editorial"):
                assert forbidden not in response.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.personnel_order_item_editorial_blocks WHERE order_item_id IN (:a,:b)"), {"a": owner_item, "b": other_item})
            conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id=:id"), {"id": order_id})
            conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id})
            conn.execute(text("UPDATE public.users SET employee_id=NULL WHERE user_id=:id"), {"id": owner_user})
            conn.execute(text("DELETE FROM public.users WHERE user_id=:id"), {"id": other_user})
            cleanup_person_graph(conn, person_ids=[owner_person, other_person], employee_ids=[owner_employee, other_employee])
