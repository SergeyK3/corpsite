"""Electronic hire identity is resolved only after the applicant submits intake."""
from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.main import app
from app.personnel_intake.application.intake_service import issue_intake_link
from app.personnel_intake.domain.models import empty_intake_draft_payload
from tests.personnel_applications.test_electronic_hire_postgres import _setup
from tests.ppr.conftest import insert_employee


def _intake_payload(iin: str) -> dict:
    payload = empty_intake_draft_payload()
    payload["personal"].update({
        "iin": iin, "last_name": "Әлиева", "first_name": "Құралай",
        "middle_name": "Үмітқызы", "birth_date": "1992-02-03",
    })
    payload["contacts"]["mobile_phone"] = "+77001234567"
    payload["education"] = [{
        "institution": "Өркен оқу орталығы", "year_from": "2011-09-01",
        "year_to": "2015-06-30", "specialty": "Медицина",
        "qualification": "Маман", "diploma_number": "001",
    }]
    return payload


def test_new_and_former_identity_confirmed_once(monkeypatch):
    from app.directory import electronic_hire_routes as hire_routes
    from app.api import personnel_intake_public_router as public_routes

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            _, actor, unit, position, _ = _setup(conn)
            facade = SimpleNamespace(begin=lambda: nullcontext(conn), connect=lambda: nullcontext(conn))
            monkeypatch.setattr(hire_routes, "engine", facade)
            monkeypatch.setattr(public_routes, "engine", facade)
            monkeypatch.setattr(hire_routes, "_hr_user_id", lambda user: actor)
            app.dependency_overrides[get_current_user] = lambda: {"user_id": actor, "role_id": 2}
            client = TestClient(app)

            for former, known_iin in ((False, False), (True, False), (False, True)):
                iin = "9" + f"{uuid4().int % 10**11:011d}"
                former_id = None
                if former:
                    former_id = int(conn.execute(text("""
                        INSERT INTO public.persons(full_name, iin, birth_date, match_key, person_status, source)
                        VALUES ('Әлиева Құралай', :iin, '1992-02-03', :key, 'active', 'manual')
                        RETURNING person_id
                    """), {"iin": iin, "key": f"eha-former:{uuid4().hex}"}).scalar_one())
                    insert_employee(conn, full_name="Әлиева Құралай", person_id=former_id, is_active=False)

                created = client.post("/directory/electronic-hire/applications", json={
                    **({"iin": iin, "birth_date": "1992-02-03"} if known_iin else {}),
                    "full_name": "Әлиева Құралай", "application_received_at": "2026-11-24",
                    "planned_start_date": "2026-12-01", "org_unit_id": unit,
                    "position_id": position, "employment_rate": 1,
                })
                assert created.status_code == 200, created.text
                aid = created.json()["application_id"]
                assert created.json()["person_id"] is None
                assert conn.execute(text("SELECT person_id FROM public.personnel_applications WHERE application_id=:id"), {"id": aid}).scalar_one() is None
                if not former:
                    assert conn.execute(text("SELECT count(*) FROM public.persons WHERE iin=:iin"), {"iin": iin}).scalar_one() == 0
                if known_iin:
                    saved = client.get(f"/directory/electronic-hire/applications/{aid}")
                    assert saved.status_code == 200
                    assert saved.json()["preliminary_iin"] == iin
                    assert saved.json()["preliminary_birth_date"] == "1992-02-03"
                preliminary = client.get(f"/directory/electronic-hire/applications/{aid}/print",
                                         params={"preliminary": True})
                assert preliminary.status_code == 200, preliminary.text
                assert "Әлиева Құралай" in preliminary.json()["ru"]
                assert "Әлиева Құралай" in preliminary.json()["kk"]
                assert client.get(f"/directory/electronic-hire/applications/{aid}/print").status_code == 422
                order_url = f"/directory/electronic-hire/applications/{aid}/order-draft"
                blocked = client.post(order_url)
                assert blocked.status_code == 422 and "IDENTITY_NOT_CONFIRMED" in blocked.text

                issued = issue_intake_link(conn, application_id=aid, issued_by_user_id=actor)
                token = issued.raw_token
                opened = client.get(f"/intake/{token}")
                assert opened.status_code == 200, opened.text
                assert not opened.json()["payload"]["personal"].get("iin")
                payload = _intake_payload(iin)
                invalid = {**payload, "personal": {**payload["personal"], "iin": ""}}
                assert client.post(f"/intake/{token}/submit", json={"payload": invalid}).status_code == 422
                sent = client.post(f"/intake/{token}/submit", json={"payload": payload})
                assert sent.status_code == 200, sent.text
                assert client.post(order_url).status_code == 422

                identity_url = f"/directory/electronic-hire/applications/{aid}/identity"
                preview = client.get(identity_url)
                assert preview.status_code == 200, preview.text
                assert preview.json()["status"] == ("former" if former else "new")
                assert preview.json()["applicant_full_name"] == "Әлиева Құралай Үмітқызы"
                confirm_url = identity_url + "/confirm"
                body = {"verified_full_name": "Әлиева Құралай Үмітқызы", "document_checked": True}
                if former:
                    assert client.post(confirm_url, json=body).status_code == 422
                    body["confirm_reuse"] = True
                first = client.post(confirm_url, json=body)
                assert first.status_code == 200, first.text
                second = client.post(confirm_url, json=body)
                assert second.status_code == 200 and second.json()["idempotent_replay"] is True
                assert first.json()["person_id"] == second.json()["person_id"]
                if former:
                    assert first.json()["person_id"] == former_id
                assert conn.execute(text("SELECT count(*) FROM public.persons WHERE iin=:iin"), {"iin": iin}).scalar_one() == 1
                printed = client.get(f"/directory/electronic-hire/applications/{aid}/print")
                assert printed.status_code == 200, printed.text
                assert "Әлиева Құралай Үмітқызы" in printed.json()["ru"]
                assert "Әлиева Құралай Үмітқызы" in printed.json()["kk"]

            for conflict in ("active_employee", "birth_date"):
                iin = "9" + f"{uuid4().int % 10**11:011d}"
                person_id = int(conn.execute(text("""
                    INSERT INTO public.persons(full_name, iin, birth_date, match_key, person_status, source)
                    VALUES ('Әлиева Құралай', :iin, :birth_date, :key, 'active', 'manual')
                    RETURNING person_id
                """), {"iin": iin, "birth_date": "1991-02-03" if conflict == "birth_date" else "1992-02-03",
                       "key": f"eha-conflict:{uuid4().hex}"}).scalar_one())
                insert_employee(conn, full_name="Әлиева Құралай", person_id=person_id,
                                is_active=conflict == "active_employee")
                created = client.post("/directory/electronic-hire/applications", json={
                    "full_name": "Әлиева Құралай", "application_received_at": "2026-11-24",
                    "planned_start_date": "2026-12-01", "org_unit_id": unit,
                    "position_id": position, "employment_rate": 1,
                })
                assert created.status_code == 200, created.text
                aid = created.json()["application_id"]
                token = issue_intake_link(conn, application_id=aid, issued_by_user_id=actor).raw_token
                sent = client.post(f"/intake/{token}/submit", json={"payload": _intake_payload(iin)})
                assert sent.status_code == 200, sent.text
                identity_url = f"/directory/electronic-hire/applications/{aid}/identity"
                preview = client.get(identity_url)
                assert preview.status_code == 200 and preview.json()["status"] == "blocked"
                assert preview.json()["reason"]
                denied = client.post(identity_url + "/confirm", json={
                    "verified_full_name": "Әлиева Құралай Үмітқызы", "document_checked": True,
                    "confirm_reuse": True,
                })
                assert denied.status_code == 422
                assert conn.execute(text("SELECT person_id FROM public.personnel_applications WHERE application_id=:id"), {"id": aid}).scalar_one() is None
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            transaction.rollback()
