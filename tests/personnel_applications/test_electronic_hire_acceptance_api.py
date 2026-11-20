"""HTTP acceptance checks on the disposable PostgreSQL database only."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.main import app
from app.personnel_applications.application import electronic_hire_service as hire
from app.personnel_applications.application.hire_order_draft_service import create_hire_order_draft_for_application
from app.services.personnel_order_hire_wording import hire_position_accusative_ru
from tests.personnel_applications.test_electronic_hire_postgres import _complete_card, _setup
from tests.ppr.conftest import insert_employee


def _as_user(user_id: int, role_id: int):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id, "role_id": role_id}


def test_hire_approval_is_visible_in_task_inbox_only_to_appointed_head():
    with engine.begin() as conn:
        application, head, unit, _, _ = _setup(conn)
        _complete_card(conn, application.person_id)
        create_hire_order_draft_for_application(conn, application_id=application.application_id,
                                                created_by_user_id=head)
        role = int(conn.execute(text("SELECT role_id FROM public.users WHERE user_id=:id"),
                                {"id": head}).scalar_one())
        other = int(conn.execute(text("""
            INSERT INTO public.users(full_name, role_id, unit_id, is_active, login)
            VALUES ('Вымышленный коллега', :role, :unit, TRUE, :login)
            RETURNING user_id
        """), {"role": role, "unit": unit, "login": f"eha-colleague-{uuid4().hex}"}).scalar_one())
    client = TestClient(app)
    try:
        _as_user(head, role)
        period = client.get("/periods/current")
        assert period.status_code == 200, period.text
        period_id = period.json()["period_id"]
        assert period_id > 0
        active = client.get("/tasks", params={"scope": "mine", "status_filter": "active",
                                              "period_id": period_id})
        assert active.status_code == 200, active.text
        task = next(item for item in active.json()["items"]
                    if item.get("electronic_hire_application_id") == application.application_id)
        assert task["status_code"] == "IN_PROGRESS"
        assert task["executor_user_id"] == head
        assert "Тестова Айгуль" in task["title"] and "0,75" in task["description"]
        task_id = task["task_id"]

        _as_user(other, role)
        foreign = client.get("/tasks", params={"scope": "mine", "status_filter": "active",
                                               "period_id": period_id})
        assert foreign.status_code == 200, foreign.text
        assert all(item["task_id"] != task_id for item in foreign.json()["items"])
        assert client.get(f"/tasks/{task_id}").status_code == 404

        _as_user(head, role)
        visa = client.post(f"/directory/electronic-hire/applications/{application.application_id}/visa",
                           json={"decision": "rejected", "explanation": "Тестовое пояснение"})
        assert visa.status_code == 200, visa.text
        approvals = client.get("/directory/electronic-hire/approvals")
        assert approvals.status_code == 200, approvals.text
        saved_visa = next(item["current_visa"] for item in approvals.json()["items"]
                          if item["application_id"] == application.application_id)
        assert saved_visa["decided_by_user_id"] == head
        assert saved_visa["decided_by_name"]
        assert saved_visa["decided_at"]
        assert saved_visa["explanation"] == "Тестовое пояснение"
        rejected = client.get("/tasks", params={"scope": "mine", "status_filter": "rejected",
                                                "period_id": period_id})
        assert rejected.status_code == 200, rejected.text
        item = next(item for item in rejected.json()["items"] if item["task_id"] == task_id)
        assert item["electronic_hire_decision"] == "rejected"
        assert item["electronic_hire_explanation"] == "Тестовое пояснение"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_search_excludes_active_and_api_print_uses_actual_fields():
    with engine.begin() as conn:
        former, hr, _, _, _ = _setup(conn, former=True)
        active_iin = f"9{uuid4().int % 10**11:011d}"
        active_person = int(conn.execute(text("""
            INSERT INTO public.persons(full_name,last_name,first_name,birth_date,iin,match_key,person_status,source)
            VALUES ('Тестова Айгуль', 'Тестова', 'Айгуль', '1990-01-01', :iin, :key, 'active', 'manual')
            RETURNING person_id
        """), {"iin": active_iin, "key": f"eha-active:{uuid4().hex}"}).scalar_one())
        insert_employee(conn, full_name="Тестова Айгуль", person_id=active_person, is_active=True)
        former_iin = conn.execute(text("SELECT iin FROM public.persons WHERE person_id=:id"), {"id": former.person_id}).scalar_one()
        details = hire.load_electronic_hire(conn, former.application_id)

    _as_user(hr, 2)
    try:
        client = TestClient(app)
        results = client.get("/directory/electronic-hire/former-candidates", params={"q": "Тестова"})
        assert results.status_code == 200, results.text
        ids = {item["person_id"] for item in results.json()["items"]}
        assert former.person_id in ids
        assert active_person not in ids
        assert client.get("/directory/electronic-hire/former-candidates", params={"q": active_iin}).json()["items"] == []
        assert any(item["iin"] == former_iin for item in client.get(
            "/directory/electronic-hire/former-candidates", params={"q": former_iin}).json()["items"])

        response = client.get(f"/directory/electronic-hire/applications/{former.application_id}/print")
        assert response.status_code == 200, response.text
        rendered = response.json()
        for locale in ("ru", "kk"):
            text_value = rendered[locale]
            assert details["full_name"] in text_value
            assert "0,75" in text_value
            assert "01.12.2026" in text_value
        assert details["org_unit_ru"] in rendered["ru"]
        assert (details["org_unit_kk"] or details["org_unit_ru"]) in rendered["kk"]
        assert hire_position_accusative_ru(details["position_document_ru"] or details["position_ru"]).casefold() in rendered["ru"].casefold()
        assert (details["position_document_kk"] or details["position_kk"] or details["position_ru"]).casefold() in rendered["kk"].casefold()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_http_stale_visa_foreign_head_and_signed_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSONNEL_PHOTO_STORAGE_ROOT", str(tmp_path / "attachments"))
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", "")
    with engine.begin() as conn:
        application, head, unit, position, _ = _setup(conn)
        _complete_card(conn, application.person_id)
        order = create_hire_order_draft_for_application(
            conn, application_id=application.application_id, created_by_user_id=head)
        hire.record_visa(conn, application.application_id, actor_user_id=head,
                         decision="approved", explanation=None)
        conn.execute(text("UPDATE public.personnel_orders SET order_number=:number WHERE order_id=:id"),
                     {"number": f"EHA-HTTP-{uuid4().hex[:8]}", "id": order.personnel_order_id})
        foreign_unit = int(conn.execute(text("""
            INSERT INTO public.org_units(name, code)
            VALUES ('Другое тестовое отделение', :code) RETURNING unit_id
        """), {"code": f"EHA-FOREIGN-{uuid4().hex[:8]}"}).scalar_one())
        foreign_role = int(conn.execute(text("SELECT role_id FROM public.roles WHERE code='EMPLOYEE'")).scalar_one())
        foreign_head = int(conn.execute(text("""
            INSERT INTO public.users(full_name, role_id, unit_id, is_active, login)
            VALUES ('Тестовый чужой руководитель', :role, :unit, TRUE, :login)
            RETURNING user_id
        """), {"role": foreign_role, "unit": foreign_unit, "login": f"eha-foreign-{uuid4().hex[:10]}"}).scalar_one())
        conn.execute(text("""
            INSERT INTO public.org_unit_managers(unit_id,user_id,manager_type,is_active)
            VALUES (:unit,:user,'HEAD',TRUE)
        """), {"unit": foreign_unit, "user": foreign_head})

    client = TestClient(app)
    aid = application.application_id
    oid = order.personnel_order_id
    try:
        _as_user(foreign_head, foreign_role)
        assert client.get("/directory/electronic-hire/approvals").json()["items"] == []
        assert client.get(f"/directory/electronic-hire/applications/{aid}").status_code == 403
        assert client.get(f"/directory/electronic-hire/applications/{aid}/print").status_code == 403
        assert client.get(f"/directory/electronic-hire/orders/{oid}/application").status_code == 403
        assert client.post(f"/directory/electronic-hire/applications/{aid}/visa",
                           json={"decision": "approved"}).status_code == 403

        _as_user(head, 2)
        png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000b49444154789c636000020000050001a5f645400000000049454e44ae426082")
        uploaded = client.post(f"/directory/electronic-hire/applications/{aid}/signed-copy",
                               files={"file": ("signed-fictional.png", png, "image/png")})
        assert uploaded.status_code == 200, uploaded.text
        attachment_id = uploaded.json()["attachment_id"]
        downloaded = client.get(f"/directory/electronic-hire/applications/{aid}/signed-copy/{attachment_id}")
        assert downloaded.status_code == 200 and downloaded.content == png
        assert "signed-fictional.png" in downloaded.headers["content-disposition"]
        _as_user(foreign_head, foreign_role)
        assert client.get(f"/directory/electronic-hire/applications/{aid}/signed-copy/{attachment_id}").status_code == 403
        _as_user(head, 2)

        changed = client.patch(f"/directory/electronic-hire/applications/{aid}/conditions", json={
            "org_unit_id": unit, "position_id": position, "employment_rate": 0.5,
            "planned_start_date": str(date(2026, 12, 2)),
        })
        assert changed.status_code == 200, changed.text
        history = client.get(f"/directory/electronic-hire/applications/{aid}/visas")
        assert history.status_code == 200 and history.json()["items"][0]["is_current"] is False

        ready = client.post(f"/directory/personnel-orders/{oid}/ready-for-signature")
        assert ready.status_code == 422, ready.text
        assert "виз" in ready.text.lower()
        registered = client.post(f"/directory/personnel-orders/{oid}/register", json={"target_status": "SIGNED"})
        assert registered.status_code == 422, registered.text
        assert "виз" in registered.text.lower()
        with engine.begin() as conn:
            conn.execute(text("UPDATE public.personnel_orders SET status='SIGNED' WHERE order_id=:id"), {"id": oid})
        applied = client.post(f"/directory/personnel-orders/{oid}/apply")
        assert applied.status_code == 422, applied.text
        assert "виз" in applied.text.lower()
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM public.employee_events WHERE order_id=:id"), {"id": oid}).scalar_one() == 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)
