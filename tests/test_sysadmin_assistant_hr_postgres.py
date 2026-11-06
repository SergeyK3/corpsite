"""Real-grant HTTP acceptance contracts, exclusively on corpsite_test."""
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.documentation_accounts_service import create_documentation_account


@pytest.fixture(scope="module")
def assistant_http():
    with engine.connect() as conn:
        assert conn.execute(text("SELECT current_database()")).scalar_one() == "corpsite_test"
        actor = conn.execute(text("""SELECT user_id FROM users WHERE role_id=2
            AND is_active AND locked_at IS NULL ORDER BY user_id LIMIT 1""")).scalar_one()
    login = "assistant-hr-test-" + uuid4().hex
    account = create_documentation_account(full_name=login, login=login,
        temporary_password="TemporaryAssistant2026!", actor_user_id=actor,
        profile_code="SYSADMIN_ASSISTANT")
    client = TestClient(app)
    token = client.post("/auth/login", json={"login": login, "password": "TemporaryAssistant2026!"})
    assert token.status_code == 200, token.text
    headers = {"Authorization": "Bearer " + token.json()["access_token"]}
    changed = client.post("/auth/password-change", headers=headers, json={
        "current_password": "TemporaryAssistant2026!", "new_password": "AssistantSupport2026!",
        "new_password_confirmation": "AssistantSupport2026!"})
    assert changed.status_code == 200, changed.text
    token = client.post("/auth/login", json={"login": login, "password": "AssistantSupport2026!"})
    headers = {"Authorization": "Bearer " + token.json()["access_token"]}
    me = client.get("/auth/me", headers=headers).json()
    assert me["employee_id"] is None and me["is_sysadmin_assistant"]
    assert not me["has_sysadmin_api"] and not me["has_user_access_admin"]
    yield client, headers, me
    # Keep immutable audit references; disable only this fixture's account/grants.
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_active=FALSE WHERE user_id=:id"), {"id": me["user_id"]})
        conn.execute(text("""UPDATE access_grants SET active_flag=FALSE,revoked_at=now()
            WHERE target_type='USER' AND target_id=:id AND revoked_at IS NULL"""), {"id": me["user_id"]})


def _call(session, method, path, body=None, status=200):
    client, headers, _ = session
    response = client.request(method, path, headers=headers, json=body)
    assert response.status_code == status, (path, response.status_code, response.text[:2000])
    return response


def test_real_card_correction_order_apply_and_filtered_excel(assistant_http):
    from tests.test_ppr_stage0_cohort_postgres import _seed_synthetic_candidate
    with engine.begin() as conn:
        _, _, employee = _seed_synthetic_candidate(conn)
        person = conn.execute(text("SELECT person_id FROM employees WHERE employee_id=:e"), {"e": employee}).scalar_one()
        row = conn.execute(text("""SELECT e.org_unit_id,e.position_id FROM employees e
            WHERE e.org_unit_id IS NOT NULL AND e.position_id IS NOT NULL
            ORDER BY e.employee_id LIMIT 1""")).mappings().one()
        conn.execute(text("UPDATE employees SET org_unit_id=:u,position_id=:p WHERE employee_id=:e"),
                     {"u": row["org_unit_id"], "p": row["position_id"], "e": employee})
    _call(assistant_http, "GET", f"/api/ppr/persons/{person}")
    _call(assistant_http, "PUT", f"/api/ppr/persons/{person}/contacts", {
        "command_id": uuid4().hex, "email": "hr-support@example.invalid"})
    assert "hr-support@example.invalid" in _call(assistant_http, "GET", f"/api/ppr/persons/{person}/contacts").text
    _call(assistant_http, "PUT", f"/api/ppr/persons/{person}/contacts", {
        "command_id": uuid4().hex, "email": "invalid email"}, status=422)
    draft = _call(assistant_http, "POST", "/directory/personnel-orders/manual-draft", {
        "order_number": "ASST-TEST-" + uuid4().hex[:12], "order_date": "2026-11-06",
        "source_title": "О приёме на работу", "source_title_locale": "ru", "item_type_code": "HIRE",
        "employee_id": employee, "effective_date": "2026-11-06",
        "document_subject_context": {"position_name": "Кадровая проверка", "org_unit_name": "Тестовое подразделение",
            "document_position_kk": "Тексеру", "document_org_unit_kk": "Тест бөлімі"},
        "item_payload": {"org_unit_id": row["org_unit_id"], "position_id": row["position_id"],
            "employment_rate": 1, "hire_basis": {"ru": "Заявление", "kk": "Өтініш"}}}, status=201).json()
    order = draft["order_id"]
    _call(assistant_http, "POST", f"/directory/personnel-orders/{order}/register", {"target_status": "REGISTERED"})
    _call(assistant_http, "POST", f"/directory/personnel-orders/{order}/apply")
    _call(assistant_http, "POST", f"/directory/personnel-orders/{order}/apply", status=409)
    _call(assistant_http, "DELETE", f"/directory/personnel-orders/{order}", {
        "reason": "Registered order cannot be deleted", "confirmation_phrase": f"DELETE DRAFT ORDER {order}"}, status=409)
    _call(assistant_http, "POST", f"/directory/personnel-orders/{order}/archive", {"reason_code": "completed"})
    _call(assistant_http, "POST", f"/directory/personnel-orders/{order}/restore", {})
    xlsx = _call(assistant_http, "GET", f"/directory/employees/export.xlsx?q={employee}")
    assert load_workbook(BytesIO(xlsx.content)).active.max_row >= 2
    _call(assistant_http, "POST", "/exports/table.xlsx", {"headers": ["Name"], "rows": [["Allowed row"]]})
    _call(assistant_http, "GET", f'/directory/personnel/reports/personnel-roster/{row["org_unit_id"]}/excel')
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM employee_events WHERE order_id=:o"), {"o": order}).scalar_one() > 0
        assert conn.execute(text("""SELECT count(*) FROM audit_log WHERE actor_user_id=:a
            AND action='ASSISTANT_BUSINESS_TRANSACTION'"""), {"a": assistant_http[2]["user_id"]}).scalar_one() > 0


def test_real_delete_ownership_and_indirect_directory_write_are_enforced(assistant_http):
    from fastapi import HTTPException
    from app.auth import create_access_token
    from app.security.sysadmin_assistant import _action, HR_SUPPORT
    from app.services.hr_import_roster_promotion_service import _get_or_create_position_id
    client, _, me = assistant_http
    with engine.connect() as conn:
        hr = conn.execute(text("""SELECT u.user_id,u.token_version FROM users u JOIN roles r USING(role_id)
            WHERE r.code='HR_HEAD' AND u.is_active ORDER BY u.user_id LIMIT 1""")).mappings().one()
    hr_headers = {"Authorization": "Bearer " + create_access_token(hr["user_id"], token_version=hr["token_version"])}
    def draft(headers):
        response = client.post("/directory/personnel-orders", headers=headers, json={
            "order_number": "ASST-OWN-" + uuid4().hex[:12], "order_date": "2026-11-06",
            "order_type_code": "HIRE", "source_mode": "PAPER"})
        assert response.status_code == 201, response.text
        return response.json()["order"]["order_id"]
    foreign = draft(hr_headers)
    _call(assistant_http, "DELETE", f"/directory/personnel-orders/{foreign}", {
        "reason": "Foreign draft", "confirmation_phrase": f"DELETE DRAFT ORDER {foreign}"}, status=403)
    own = draft(assistant_http[1])
    _call(assistant_http, "DELETE", f"/directory/personnel-orders/{own}", {
        "reason": "Own draft", "confirmation_phrase": f"DELETE DRAFT ORDER {own}"})
    marker = "assistant-cannot-create-" + uuid4().hex
    token = _action.set({"actor_user_id": me["user_id"], "permission": HR_SUPPORT})
    try:
        with pytest.raises(HTTPException) as denied:
            with engine.begin() as conn:
                _get_or_create_position_id(conn, marker)
        assert denied.value.status_code == 403
    finally:
        _action.reset(token)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM positions WHERE name=:n"), {"n": marker}).scalar_one() == 0


def test_all_four_migration_stages_use_real_grants_and_existing_acceptance(assistant_http, monkeypatch):
    from tests.test_ppr_stage0_cohort_postgres import _seed_synthetic_candidate
    for flag in ("PPR_PMF_BRIDGE_ENABLED", "PPR_STAGE3_TRAINING_PREVIEW_ENABLED",
                 "PPR_STAGE3_TRAINING_EXECUTION_ENABLED", "PPR_STAGE3_TRAINING_ACCEPT_ENABLED"):
        monkeypatch.setenv(flag, "true")
    monkeypatch.setenv("PPR_STAGE3_CERTIFICATE_HMAC_SECRET", "isolated-assistant-hr-test-secret")
    with engine.begin() as conn:
        _, batch, employee = _seed_synthetic_candidate(conn)
        person = conn.execute(text("SELECT person_id FROM employees WHERE employee_id=:e"), {"e": employee}).scalar_one()
        conn.execute(text("""UPDATE hr_import_rows r SET normalized_payload=
            jsonb_build_object('full_name',e.full_name)
            FROM employees e WHERE r.employee_id=e.employee_id AND r.batch_id=:b"""), {"b": batch})
        row = conn.execute(text("SELECT row_id FROM hr_import_rows WHERE batch_id=:b AND employee_id=:e"),
                           {"b": batch, "e": employee}).scalar_one()
        conn.execute(text("""INSERT INTO hr_import_normalized_records
            (batch_id,row_id,employee_id,fragment_index,source_field,source_text,source_record_key,
             record_kind,title,parse_method,review_status)
            VALUES(:b,:r,:e,0,'education','','education-0','education','Диплом University','manual','approved')"""),
            {"b": batch, "r": row, "e": employee})
        conn.execute(text("""INSERT INTO hr_import_normalized_records
            (batch_id,row_id,employee_id,fragment_index,source_field,source_text,source_record_key,
             record_kind,title,provider,hours,end_date,document_number,parse_method,review_status)
            VALUES(:b,:r,:e,1,'training',:source,'training-0','training','ACLS','Provider',36,
                   '2024-03-01','AB-1','regex_v1','approved')"""),
            {"b": batch, "r": row, "e": employee,
             "source": "Курс: ACLS; Организатор: Provider; 36 часов; 01.03.2024; № AB-1"})
    base = "/personnel/ppr-migration/stage-0"
    preview = _call(assistant_http, "POST", base + "/preview", {"source_batch_id": batch}).json()
    frozen = _call(assistant_http, "POST", base + "/freeze", {
        "source_batch_id": batch, "preview_fingerprint": preview["preview_fingerprint"]}).json()
    cohort = frozen["stage0_cohort_run_id"]
    base = "/personnel/ppr-migration/stage-1"
    run = _call(assistant_http, "POST", base + "/preview", {"stage0_cohort_run_id": cohort}).json()
    body = {"stage1_run_id": run["run"]["stage1_run_id"]}
    _call(assistant_http, "POST", base + "/approve", body)
    for _ in range(5):
        run = _call(assistant_http, "POST", base + "/execute-next", body).json()
        if run["run"]["status"] == "COMPLETED_PENDING_REVIEW":
            break
    assert _call(assistant_http, "POST", base + "/accept", body).json()["run"]["status"] == "ACCEPTED"
    for stage, kind, cohort, person, table in (
        (2, "education", cohort, person, "person_education"),
        (3, "training", cohort, person, "person_training"),
    ):
        base = f"/personnel/ppr-migration/stage-{stage}/{kind}"
        preview = _call(assistant_http, "POST", base + "/preview", {"stage0_cohort_run_id": cohort}).json()
        run = preview if stage == 2 else _call(assistant_http, "POST", base + "/runs", {
            "stage0_cohort_run_id": cohort, "preview_fingerprint": preview["preview_fingerprint"]}).json()
        run_id = run["run"]["stage_run_id"]
        path = base + f"/runs/{run_id}"
        _call(assistant_http, "POST", path + "/approve")
        for _ in range(5):
            run = _call(assistant_http, "POST", path + "/execute-next").json()
            if run["run"]["status"] == "COMPLETED_PENDING_REVIEW":
                break
        summary = _call(assistant_http, "GET", path + "/acceptance-summary").json()
        accepted = _call(assistant_http, "POST", path + "/accept", {
            "stage_run_id": run_id, "acceptance_fingerprint": summary["acceptance_fingerprint"]}).json()
        assert accepted["run"]["status"] == "ACCEPTED"
        with engine.connect() as conn:
            assert conn.execute(text(f"SELECT count(*) FROM {table} WHERE person_id=:p"), {"p": person}).scalar_one() > 0


@pytest.mark.parametrize("method,path", [
    ("POST", "/directory/roles"), ("PATCH", "/directory/org-units/1"),
    ("POST", "/api/ppr/education-levels"), ("PUT", "/personnel/settings"),
    ("POST", "/admin/users"), ("POST", "/admin/access/grants"),
    ("POST", "/directory/access/users/1/password-reset"),
    ("POST", "/admin/personnel-order-templates/HIRE/draft/publish"),
    ("DELETE", "/directory/personnel-orders/1/hr-head"),
    ("POST", "/directory/test-personnel-deletion/preview"),
])
def test_forbidden_operations_with_real_assistant_identity(assistant_http, method, path):
    _call(assistant_http, method, path, {}, status=403)
