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


def _row(*, status: str = "REGISTERED", review: bool = False) -> dict[str, object]:
    return {
        "order_id": 11, "order_number": "11-К", "order_date": date(2026, 9, 1),
        "order_type_code": "HIRE", "status": status, "title": "Чужой заголовок",
        "preamble": "Преамбула с чужими именами", "basis": "Чужое основание",
        "item_number": 1, "item_type_code": "HIRE", "item_text": "Принять текущего работника.",
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
        "order_id": 11, "order_number": "11-К", "order_date": "2026-09-01", "title": "Жұмысқа қабылдау туралы",
        "items": [{"item_number": 1, "item_text": "Принять текущего работника."}], "confirmation_status": "CONFIRMED",
    }]}
    # Contract intentionally has neither the resolved employee ID nor any
    # other employee/item/evidence/editorial data.
    assert "employee_id" not in response.text
    assert "payload" not in response.text
    assert "Чужой заголовок" not in response.text
    assert "Преамбула с чужими именами" not in response.text
    assert "Чужое основание" not in response.text


def test_my_orders_default_to_kazakh_and_reject_an_invalid_locale(monkeypatch) -> None:
    row = _row(status="REGISTERED")
    row["item_type_code"] = "RETURN_FROM_CHILDCARE_LEAVE"
    row["preamble"] = "Қазақша преамбула"
    row["basis"] = "Қазақша негіздеме"
    seen: list[str] = []
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    monkeypatch.setattr(subject, "_employee_for_user", lambda user: ("READY", 42))
    monkeypatch.setattr(subject, "_safe_rows", lambda employee_id, **kwargs: (seen.append(kwargs["locale"]) or [row]))
    try:
        client = TestClient(app)
        default_response = client.get("/api/ppr/me/orders")
        default_detail = client.get("/api/ppr/me/orders/11")
        ru_response = client.get("/api/ppr/me/orders?locale=ru")
        ru_detail = client.get("/api/ppr/me/orders/11?locale=ru")
        invalid_response = client.get("/api/ppr/me/orders?locale=en")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert default_response.status_code == 200
    assert default_response.json()["orders"][0]["title"] == "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы"
    assert "preamble" not in default_detail.json()
    assert "basis" not in default_detail.json()
    assert "tenure_text" not in default_detail.json()
    assert ru_response.json()["orders"][0]["title"] == "О выходе на работу из отпуска по уходу за ребёнком"
    assert ru_detail.json()["items"] == [{"item_number": 1, "item_text": "Принять текущего работника."}]
    assert seen == ["kk", "kk", "ru", "ru"]
    assert invalid_response.status_code == 422


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


def test_document_review_event_overrides_legacy_derived_confirmation_without_leaking_audit(monkeypatch) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    monkeypatch.setattr(subject, "_employee_for_user", lambda user: ("READY", 42))
    confirmed_row = _row(status="SIGNED", review=True)
    confirmed_row["document_review_action"] = "DOCUMENT_CONFIRMED"
    reopened_row = _row(status="REGISTERED")
    reopened_row["document_review_action"] = "DOCUMENT_REOPENED"
    try:
        monkeypatch.setattr(subject, "_safe_rows", lambda employee_id, **kwargs: [confirmed_row])
        confirmed = TestClient(app).get("/api/ppr/me/orders/11")
        monkeypatch.setattr(subject, "_safe_rows", lambda employee_id, **kwargs: [reopened_row])
        reopened = TestClient(app).get("/api/ppr/me/orders/11")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert confirmed.json()["confirmation_status"] == "CONFIRMED"
    assert reopened.json()["confirmation_status"] == "UNCONFIRMED"
    for forbidden in ("actor", "reason", "note", "blockers", "history", "metadata_json"):
        assert forbidden not in confirmed.text
        assert forbidden not in reopened.text


def test_my_orders_composite_title_uses_only_current_employee_item_types(monkeypatch) -> None:
    row = _row(status="REGISTERED")
    row["title"] = "Чужой сотрудник указан в заголовке"
    row["item_text"] = None
    row["item_type_code"] = "RETURN_FROM_CHILDCARE_LEAVE"
    second = {**row, "item_number": 3, "item_type_code": "CONCURRENT_DUTY_START", "item_text": "Второй свой пункт"}
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    monkeypatch.setattr(subject, "_employee_for_user", lambda user: ("READY", 42))
    monkeypatch.setattr(subject, "_safe_rows", lambda employee_id, **kwargs: [row, second])
    try:
        response = TestClient(app).get("/api/ppr/me/orders/11?locale=ru")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200
    assert response.json()["title"] == "О выходе на работу из отпуска по уходу за ребёнком; О совмещении"
    assert response.json()["confirmation_status"] == "CONFIRMED"
    assert response.json()["items"] == [
        {"item_number": 1, "item_text": None}, {"item_number": 3, "item_text": "Второй свой пункт"},
    ]
    assert "Чужой сотрудник" not in response.text
    assert "COMPOSITE" not in response.text


def test_my_orders_return_from_childcare_composite_is_unconfirmed_and_hides_codes(monkeypatch) -> None:
    row = _row(status="REGISTERED", review=False)
    row["item_type_code"] = "RETURN_FROM_CHILDCARE_LEAVE"
    second = {**row, "item_number": 2, "item_type_code": "CONCURRENT_DUTY_START"}
    row["needs_docx_review"] = True
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    monkeypatch.setattr(subject, "_employee_for_user", lambda user: ("READY", 42))
    monkeypatch.setattr(subject, "_safe_rows", lambda employee_id, **kwargs: [row, second])
    try:
        response = TestClient(app).get("/api/ppr/me/orders/11?locale=ru")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "О выходе на работу из отпуска по уходу за ребёнком; О совмещении"
    assert body["confirmation_status"] == "UNCONFIRMED"
    assert "ещё не подтверждён кадровой службой" in body["warning"]
    assert "RETURN_FROM_CHILDCARE_LEAVE" not in response.text
    assert "COMPOSITE" not in response.text


def test_registered_return_from_childcare_requires_docx_review() -> None:
    assert subject._confirmed("REGISTERED", False, needs_docx_review=True) is False
    assert subject._confirmed("REGISTERED", False, needs_docx_review=False) is True


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
            VALUES(:number,:date,'COMPOSITE','SIGNED','PAPER',:user) RETURNING order_id"""), {"number": f"NO-PERSON-{suffix}", "date": date(2026, 9, 2), "user": user_id}).scalar_one())
        own_item = int(conn.execute(text("""INSERT INTO public.personnel_order_items(order_id,item_number,item_type_code,employee_id,payload)
            VALUES(:order,1,'HIRE',:employee,'{}'::jsonb) RETURNING item_id"""), {"order": order_id, "employee": own_employee}).scalar_one())
        other_item = int(conn.execute(text("""INSERT INTO public.personnel_order_items(order_id,item_number,item_type_code,employee_id,payload)
            VALUES(:order,2,'HIRE',:employee,'{}'::jsonb) RETURNING item_id"""), {"order": order_id, "employee": other_employee}).scalar_one())
        conn.execute(text("INSERT INTO public.personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text) VALUES(:item,'ru','body',:body)"), {"item": own_item, "body": "Только собственный пункт."})
        conn.execute(text("INSERT INTO public.personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text) VALUES(:item,'ru','body',:body)"), {"item": other_item, "body": "Чужой пункт."})
    try:
        app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}
        client = TestClient(app)
        listing = client.get("/api/ppr/me/orders?employee_id=999999&locale=ru")
        detail = client.get(f"/api/ppr/me/orders/{order_id}?locale=ru")
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
            VALUES(:number,:date,'COMPOSITE','REGISTERED','PAPER',:user) RETURNING order_id"""), {"number": f"SELF-{suffix}", "date": date(2026, 9, 1), "user": owner_user}).scalar_one())
        owner_item = int(conn.execute(text("""INSERT INTO public.personnel_order_items(order_id,item_number,item_type_code,employee_id,payload)
            VALUES(:order,1,'HIRE',:employee,'{}'::jsonb) RETURNING item_id"""), {"order": order_id, "employee": owner_employee}).scalar_one())
        owner_second_item = int(conn.execute(text("""INSERT INTO public.personnel_order_items(order_id,item_number,item_type_code,employee_id,payload)
            VALUES(:order,2,'TRANSFER',:employee,'{}'::jsonb) RETURNING item_id"""), {"order": order_id, "employee": owner_employee}).scalar_one())
        other_item = int(conn.execute(text("""INSERT INTO public.personnel_order_items(order_id,item_number,item_type_code,employee_id,payload)
            VALUES(:order,3,'HIRE',:employee,'{}'::jsonb) RETURNING item_id"""), {"order": order_id, "employee": other_employee}).scalar_one())
        for item, name in ((owner_item, "Alice"), (owner_second_item, "Alice second"), (other_item, "Bob")):
            conn.execute(text("""INSERT INTO public.personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text)
            VALUES(:item,'ru','body',:body)"""), {"item": item, "body": f"Только пункт {name}."})
    try:
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": owner_user}
        owner_list = client.get("/api/ppr/me/orders?locale=ru"); owner_detail = client.get(f"/api/ppr/me/orders/{order_id}?locale=ru")
        app.dependency_overrides[get_current_user] = lambda: {"user_id": other_user}
        other_list = client.get("/api/ppr/me/orders?locale=ru"); other_detail = client.get(f"/api/ppr/me/orders/{order_id}?locale=ru")
        for response, own, foreign in ((owner_list, "Alice", "Bob"), (owner_detail, "Alice", "Bob"), (other_list, "Bob", "Alice"), (other_detail, "Bob", "Alice")):
            assert response.status_code == 200
            assert own in response.text and foreign not in response.text
            for forbidden in ("employee_id", "payload", "evidence", "assumptions", "editorial"):
                assert forbidden not in response.text
        assert [item["item_number"] for item in owner_detail.json()["items"]] == [1, 2]
        assert [item["item_number"] for item in owner_list.json()["orders"][0]["items"]] == [1, 2]
        assert len(owner_list.json()["orders"]) == 1
        assert [item["item_number"] for item in other_detail.json()["items"]] == [3]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.personnel_order_item_editorial_blocks WHERE order_item_id IN (:a,:b,:c)"), {"a": owner_item, "b": owner_second_item, "c": other_item})
            conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id=:id"), {"id": order_id})
            conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id})
            conn.execute(text("UPDATE public.users SET employee_id=NULL WHERE user_id=:id"), {"id": owner_user})
            conn.execute(text("DELETE FROM public.users WHERE user_id=:id"), {"id": other_user})
            cleanup_person_graph(conn, person_ids=[owner_person, other_person], employee_ids=[owner_employee, other_employee])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_stage1_signed_registered_imports_and_hr_full_document(seed) -> None:
    """Ordinary account receives linked final orders; HR keeps the complete view."""
    require_ppr_schema()
    suffix = uuid4().hex[:8]
    owner_user = int(seed["initiator_user_id"])
    other_user = int(seed["executor_user_id"])
    order_ids: list[int] = []
    item_ids: list[int] = []
    with engine.begin() as conn:
        hr_role = conn.execute(text("SELECT role_id FROM public.roles WHERE code='HR_HEAD'")).scalar_one()
        hr_user = int(conn.execute(text("""INSERT INTO public.users(full_name,role_id,is_active,login)
            VALUES(:name,:role,TRUE,:login) RETURNING user_id"""),
            {"name": f"Synthetic HR {suffix}", "role": hr_role, "login": f"synthetic-hr-{suffix}"}).scalar_one())
        conn.execute(text("""INSERT INTO public.access_grants
            (access_role_id,target_type,target_id,granted_by_user_id,reason)
            SELECT access_role_id,'USER',:hr_user,:grantor,'Synthetic HR read test'
            FROM public.access_roles WHERE code='HR_ENROLLMENT_MANAGER'"""),
            {"hr_user": hr_user, "grantor": owner_user})
        own_person = insert_person(conn, full_name=f"Same Name {suffix}")
        other_person = insert_person(conn, full_name=f"Other Name {suffix}")
        own_employee = insert_employee(conn, full_name=f"Same Name {suffix}", person_id=own_person)
        other_employee = insert_employee(conn, full_name=f"Other Name {suffix}", person_id=other_person)
        conn.execute(text("UPDATE public.users SET employee_id=:e WHERE user_id=:u"), {"e": own_employee, "u": owner_user})
        conn.execute(text("UPDATE public.users SET employee_id=:e WHERE user_id=:u"), {"e": other_employee, "u": other_user})

        def add_order(status: str, mode: str, employee_id: int | None, label: str) -> int:
            order_id = int(conn.execute(text("""INSERT INTO public.personnel_orders
                (order_number,order_date,order_type_code,status,source_mode,source_title,created_by)
                VALUES(:number,:date,'HIRE',:status,:mode,:source_title,:user) RETURNING order_id"""),
                {"number": f"{label}-{suffix}", "date": date(2026, 9, 1), "status": status,
                 "mode": mode, "source_title": f"Full document names Other Name {suffix}", "user": hr_user}).scalar_one())
            item_id = int(conn.execute(text("""INSERT INTO public.personnel_order_items
                (order_id,item_number,item_type_code,employee_id,payload)
                VALUES(:order,1,'HIRE',:employee,CAST(:payload AS jsonb)) RETURNING item_id"""),
                {"order": order_id, "employee": employee_id,
                 "payload": f'{{"source_name":"Same Name {suffix}"}}' if employee_id is None else '{}'}).scalar_one())
            conn.execute(text("""INSERT INTO public.personnel_order_item_editorial_blocks
                (order_item_id,locale,block_type,generated_text) VALUES(:item,'ru','body',:body)"""),
                {"item": item_id, "body": f"Own clause {label}"})
            order_ids.append(order_id)
            item_ids.append(item_id)
            return order_id

        signed_import = add_order("SIGNED", "PAPER", own_employee, "signed-import")
        registered = add_order("REGISTERED", "MANUAL", own_employee, "registered")
        foreign = add_order("SIGNED", "PAPER", other_employee, "foreign")
        draft = add_order("DRAFT", "PAPER", own_employee, "draft")
        unlinked_import = add_order("REGISTERED", "PAPER", None, "unlinked-import")
    try:
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": owner_user, "role_id": seed["initiator_role_id"]}
        listing = client.get("/api/ppr/me/orders?locale=ru")
        assert listing.status_code == 200
        assert {order["order_id"] for order in listing.json()["orders"]} == {signed_import, registered}
        for order_id in (signed_import, registered):
            response = client.get(f"/api/ppr/me/orders/{order_id}?locale=ru")
            assert response.status_code == 200
            assert response.json()["items"][0]["item_text"]
            assert f"Other Name {suffix}" not in response.text
        for order_id in (foreign, draft, unlinked_import):
            assert client.get(f"/api/ppr/me/orders/{order_id}?locale=ru").status_code == 404
        assert client.get(f"/directory/personnel-orders/{signed_import}").status_code == 403

        app.dependency_overrides[get_current_user] = lambda: {"user_id": hr_user, "role_id": hr_role}
        hr_list = client.get("/directory/personnel-orders?record_quality=ALL")
        hr_detail = client.get(f"/directory/personnel-orders/{signed_import}")
        assert hr_list.status_code == 200
        assert hr_detail.status_code == 200
        assert f"Other Name {suffix}" in hr_detail.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.personnel_order_item_editorial_blocks WHERE order_item_id=ANY(:ids)"), {"ids": item_ids})
            conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id=ANY(:ids)"), {"ids": order_ids})
            conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id=ANY(:ids)"), {"ids": order_ids})
            conn.execute(text("UPDATE public.users SET employee_id=NULL WHERE user_id IN (:a,:b)"), {"a": owner_user, "b": other_user})
            conn.execute(text("DELETE FROM public.access_grants WHERE target_type='USER' AND target_id=:id"), {"id": hr_user})
            conn.execute(text("DELETE FROM public.users WHERE user_id=:id"), {"id": hr_user})
            cleanup_person_graph(conn, person_ids=[own_person, other_person], employee_ids=[own_employee, other_employee])
