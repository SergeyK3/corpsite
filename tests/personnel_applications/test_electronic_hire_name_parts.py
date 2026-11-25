"""Structured names stay intact from the HR draft through identity confirmation."""
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.main import app
from app.personnel_intake.application.intake_service import issue_intake_link
from tests.personnel_applications.test_electronic_hire_deferred_identity import _intake_payload
from tests.personnel_applications.test_electronic_hire_postgres import _complete_card, _setup
from tests.ppr.conftest import insert_employee


def test_structured_draft_and_verified_name_parts(monkeypatch):
    from app.directory import electronic_hire_routes as routes
    from app.api import personnel_intake_public_router as public_routes

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            _, actor, unit, position, _ = _setup(conn)
            # The isolated test database has legacy blank print headings. Supply
            # approved headings at the resolver seam without changing the DB.
            from app.personnel_applications.application import electronic_hire_order_preview as order_preview_service
            original_titles = order_preview_service.version_print_titles
            def with_test_titles(row):
                result = dict(original_titles(row))
                result["print_title_ru"] = result["title_ru"]
                result["print_title_kk"] = result["title_kk"]
                return result
            monkeypatch.setattr(order_preview_service, "version_print_titles", with_test_titles)
            facade = SimpleNamespace(begin=lambda: nullcontext(conn), connect=lambda: nullcontext(conn))
            monkeypatch.setattr(routes, "engine", facade)
            monkeypatch.setattr(public_routes, "engine", facade)
            monkeypatch.setattr(routes, "_hr_user_id", lambda user: actor)
            app.dependency_overrides[get_current_user] = lambda: {"user_id": actor, "role_id": 2}
            client = TestClient(app)
            iin = "9" + f"{uuid4().int % 10**11:011d}"

            created = client.post("/directory/electronic-hire/applications", json={
                "last_name": "Қара Қызы", "first_name": "Әсем", "middle_name": "",
                "application_received_at": "2026-11-24", "planned_start_date": "2026-12-01",
                "org_unit_id": unit, "position_id": position, "employment_rate": 1,
            })
            assert created.status_code == 200, created.text
            aid = created.json()["application_id"]
            row = conn.execute(text("""
                SELECT a.person_id, e.preliminary_full_name, e.preliminary_last_name,
                       e.preliminary_first_name, e.preliminary_middle_name
                FROM public.personnel_applications a
                JOIN public.electronic_hire_applications e USING(application_id)
                WHERE a.application_id=:id
            """), {"id": aid}).mappings().one()
            assert row["person_id"] is None and row["preliminary_full_name"] is None
            assert (row["preliminary_last_name"], row["preliminary_first_name"], row["preliminary_middle_name"]) == (
                "Қара Қызы", "Әсем", None)
            saved = client.get(f"/directory/electronic-hire/applications/{aid}")
            assert saved.status_code == 200 and saved.json()["full_name"] == "Қара Қызы Әсем"
            listed = client.get("/directory/electronic-hire/applications")
            assert any(item["application_id"] == aid and item["full_name"] == "Қара Қызы Әсем"
                       for item in listed.json()["items"])

            changed = client.patch(f"/directory/electronic-hire/applications/{aid}/preliminary-name",
                                   json={"last_name": "Қара Қызы", "first_name": "Әсем", "middle_name": "Ұлы"})
            assert changed.status_code == 200, changed.text
            assert changed.json()["preliminary_middle_name"] == "Ұлы"
            preliminary = client.get(f"/directory/electronic-hire/applications/{aid}/print",
                                     params={"preliminary": True})
            assert preliminary.status_code == 200
            assert "Қара Қызы Әсем Ұлы" in preliminary.json()["ru"]
            assert "Қара Қызы Әсем Ұлы" in preliminary.json()["kk"]
            order_preview = client.get(f"/directory/electronic-hire/applications/{aid}/order-preview")
            assert order_preview.status_code == 200, order_preview.text
            assert order_preview.json()["saved"] is False
            for language in ("ru", "kk"):
                assert "Қара Қызы Әсем Ұлы" in order_preview.json()[language]["body"]
            assert conn.execute(text("""
                SELECT person_id, personnel_order_id FROM public.personnel_applications
                WHERE application_id=:id
            """), {"id": aid}).one() == (None, None)
            assert client.post(f"/directory/electronic-hire/applications/{aid}/order-draft").status_code == 422

            token = issue_intake_link(conn, application_id=aid, issued_by_user_id=actor).raw_token
            payload = _intake_payload(iin)
            payload["personal"].update({"last_name": "Қара Қызы", "first_name": "Әсемгүл", "middle_name": ""})
            submitted = client.post(f"/intake/{token}/submit", json={"payload": payload})
            assert submitted.status_code == 200, submitted.text
            preview = client.get(f"/directory/electronic-hire/applications/{aid}/identity")
            assert preview.status_code == 200, preview.text
            assert preview.json()["name_differences"] == ["first_name", "middle_name"]
            assert preview.json()["applicant_name_parts"] == {
                "last_name": "Қара Қызы", "first_name": "Әсемгүл", "middle_name": ""}
            confirmed = client.post(f"/directory/electronic-hire/applications/{aid}/identity/confirm", json={
                "verified_last_name": "Қара Қызы", "verified_first_name": "Әсемгүл",
                "verified_middle_name": "", "document_checked": True,
            })
            assert confirmed.status_code == 200, confirmed.text
            person = conn.execute(text("""
                SELECT full_name, last_name, first_name, middle_name FROM public.persons WHERE person_id=:id
            """), {"id": confirmed.json()["person_id"]}).mappings().one()
            assert dict(person) == {"full_name": "Қара Қызы Әсемгүл", "last_name": "Қара Қызы",
                                    "first_name": "Әсемгүл", "middle_name": None}
            printed = client.get(f"/directory/electronic-hire/applications/{aid}/print")
            assert printed.status_code == 200
            assert "Қара Қызы Әсемгүл" in printed.json()["ru"]
            assert "Қара Қызы Әсемгүл" in printed.json()["kk"]
            verified_preview = client.get(f"/directory/electronic-hire/applications/{aid}/order-preview")
            assert verified_preview.status_code == 200, verified_preview.text
            for language in ("ru", "kk"):
                assert person["full_name"] in verified_preview.json()[language]["body"]
            before_transfer = client.post(f"/directory/electronic-hire/applications/{aid}/order-draft")
            assert before_transfer.status_code == 422
            assert before_transfer.json()["detail"]["code"] == "INTAKE_TRANSFER_REQUIRED"
            conn.execute(text("""
                INSERT INTO public.personnel_intake_transfers
                    (application_id, status, result, transferred_by_user_id,
                     transferred_at, sections_transferred)
                VALUES (:id, 'completed', 'success', :actor, now(), '["general"]'::jsonb)
            """), {"id": aid, "actor": actor})
            _complete_card(conn, confirmed.json()["person_id"])
            conn.execute(text("""
                UPDATE public.persons SET last_name=:last_name, first_name=:first_name
                WHERE person_id=:id
            """), {"last_name": "Қара Қызы", "first_name": "Әсемгүл",
                   "id": confirmed.json()["person_id"]})
            order = client.post(f"/directory/electronic-hire/applications/{aid}/order-draft")
            assert order.status_code == 200, order.text
            payload = conn.execute(text("""
                SELECT payload FROM public.personnel_order_items
                WHERE order_id=:id AND item_number=1
            """), {"id": order.json()["personnel_order_id"]}).scalar_one()
            assert payload["source_employee_name"] == "Қара Қызы Әсемгүл"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            transaction.rollback()


def test_former_search_and_legacy_name_are_not_split(monkeypatch):
    from app.directory import electronic_hire_routes as routes

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            _, actor, unit, position, _ = _setup(conn)
            facade = SimpleNamespace(begin=lambda: nullcontext(conn), connect=lambda: nullcontext(conn))
            monkeypatch.setattr(routes, "engine", facade)
            monkeypatch.setattr(routes, "_hr_user_id", lambda user: actor)
            app.dependency_overrides[get_current_user] = lambda: {"user_id": actor, "role_id": 2}
            client = TestClient(app)
            for structured in (True, False):
                iin = "9" + f"{uuid4().int % 10**11:011d}"
                name = "Төре Қызы Әсем" if structured else "Ескі Толық Аты"
                person_id = int(conn.execute(text("""
                    INSERT INTO public.persons(full_name, iin, birth_date, match_key, person_status, source,
                                               last_name, first_name)
                    VALUES (:name, :iin, '1992-02-03', :key, 'active', 'manual', :last_name, :first_name)
                    RETURNING person_id
                """), {"name": name, "iin": iin, "key": f"former:{uuid4().hex}",
                       "last_name": "Төре Қызы" if structured else None,
                       "first_name": "Әсем" if structured else None}).scalar_one())
                insert_employee(conn, full_name=name, person_id=person_id, is_active=False)
                found = client.get("/directory/electronic-hire/former-candidates", params={"q": iin})
                assert found.status_code == 200
                candidate = next(item for item in found.json()["items"] if item["person_id"] == person_id)
                assert candidate["full_name"] == name
                assert candidate["last_name"] == ("Төре Қызы" if structured else None)
                assert candidate["first_name"] == ("Әсем" if structured else None)

            legacy = client.post("/directory/electronic-hire/applications", json={
                "full_name": "Ескі Составной ФИО", "application_received_at": "2026-11-24",
                "planned_start_date": "2026-12-01", "org_unit_id": unit,
                "position_id": position, "employment_rate": 1,
            })
            assert legacy.status_code == 200, legacy.text
            aid = legacy.json()["application_id"]
            opened = client.get(f"/directory/electronic-hire/applications/{aid}").json()
            assert opened["preliminary_full_name"] == "Ескі Составной ФИО"
            assert opened["preliminary_last_name"] is None
            assert opened["preliminary_first_name"] is None
            updated = client.patch(f"/directory/electronic-hire/applications/{aid}/preliminary-name",
                                   json={"last_name": "Ескі Составной", "first_name": "ФИО", "middle_name": ""})
            assert updated.status_code == 200, updated.text
            assert updated.json()["preliminary_full_name"] == "Ескі Составной ФИО"
            assert updated.json()["preliminary_last_name"] == "Ескі Составной"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            transaction.rollback()
