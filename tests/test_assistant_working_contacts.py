"""Real assistant grants: organization-wide contact reads, filtering and no writes."""
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import text

from app.db.engine import engine
from tests.test_sysadmin_assistant_hr_postgres import assistant_http, _call


def test_unlinked_assistant_reads_all_contacts_and_exact_contact(assistant_http):
    me = _call(assistant_http, "GET", "/auth/me").json()
    assert me["employee_id"] is None and me["has_working_contacts_read"]
    assert not me["has_user_access_admin"] and not me["has_sysadmin_api"] and not me["is_privileged"]
    response = _call(assistant_http, "GET", "/directory/working-contacts?active_only=false&limit=2000").json()
    with engine.connect() as conn:
        expected = conn.execute(text("SELECT count(*) FROM users")).scalar_one()
    assert response["total"] == expected
    assert len(response["items"]) == expected
    contact = _call(assistant_http, "GET", f'/directory/working-contacts/{me["user_id"]}').json()
    assert contact["user_id"] == me["user_id"] and contact["employee_id"] is None
    assert not {"password_hash", "token_version", "must_change_password"}.intersection(contact)


def test_search_activity_and_group_filters_match_exported_contacts(assistant_http):
    me = assistant_http[2]
    found = _call(assistant_http, "GET", "/directory/working-contacts", body=None).json()
    assert all(row["is_active"] for row in found["items"])
    client, headers, _ = assistant_http
    response = client.get("/directory/working-contacts", headers=headers,
                          params={"q": me["login"], "active_only": True})
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1 and items[0]["user_id"] == me["user_id"]
    row = items[0]
    table = {"headers": ["ID", "ФИО", "Логин", "Телефон", "Telegram", "Роль", "Отделение", "Статус"],
             "rows": [[row["user_id"], row["full_name"], row["login"], row["phone"],
                       row["telegram_username"], row["role_name_ru"] or row["role_name"],
                       row["unit_name_ru"] or row["unit_name"], "Активен"]]}
    workbook = _call(assistant_http, "POST", "/exports/table.xlsx", table)
    values = list(load_workbook(BytesIO(workbook.content)).active.values)
    assert list(values[0]) == table["headers"]
    assert list(values[1]) == table["rows"][0]
    with engine.connect() as conn:
        group = conn.execute(text("""SELECT ou.group_id FROM users u
            JOIN org_units ou ON ou.unit_id=u.unit_id WHERE ou.group_id IS NOT NULL
            ORDER BY u.user_id LIMIT 1""")).scalar_one()
        expected_ids = set(conn.execute(text("""SELECT u.user_id FROM users u
            JOIN org_units ou ON ou.unit_id=u.unit_id WHERE ou.group_id=:g"""), {"g": group}).scalars())
        unit = conn.execute(text("SELECT unit_id FROM users WHERE unit_id IS NOT NULL ORDER BY user_id LIMIT 1")).scalar_one()
        units = set(conn.execute(text("""WITH RECURSIVE subtree AS (
            SELECT unit_id FROM org_units WHERE unit_id=:u UNION ALL
            SELECT c.unit_id FROM org_units c JOIN subtree s ON s.unit_id=c.parent_unit_id
            WHERE COALESCE(c.is_active,TRUE)) SELECT unit_id FROM subtree"""), {"u": unit}).scalars())
    grouped = client.get("/directory/working-contacts", headers=headers,
                         params={"org_group_id": group, "active_only": False, "limit": 2000}).json()
    assert {r["user_id"] for r in grouped["items"]} == expected_ids
    filtered = client.get("/directory/working-contacts", headers=headers,
                          params={"org_unit_id": unit, "active_only": False, "limit": 2000}).json()
    assert filtered["items"] and all(r["org_unit_id"] in units for r in filtered["items"])


def test_revocation_is_not_bypassed_by_documentation_read(assistant_http):
    uid = assistant_http[2]["user_id"]
    with engine.begin() as conn:
        grant = conn.execute(text("""SELECT g.grant_id FROM access_grants g
            JOIN access_roles a USING(access_role_id) WHERE g.target_type='USER'
            AND g.target_id=:u AND a.code='ASSISTANT_WORKING_CONTACTS_READ' AND g.active_flag"""),
            {"u": uid}).scalar_one()
        conn.execute(text("UPDATE access_grants SET active_flag=FALSE,revoked_at=now() WHERE grant_id=:g"), {"g": grant})
    try:
        _call(assistant_http, "GET", "/directory/working-contacts", status=403)
        _call(assistant_http, "GET", f"/directory/working-contacts/{uid}", status=403)
        assert not _call(assistant_http, "GET", "/auth/me").json()["has_working_contacts_read"]
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE access_grants SET active_flag=TRUE,revoked_at=NULL WHERE grant_id=:g"), {"g": grant})


@pytest.mark.parametrize("method,path", [
    ("POST", "/directory/contacts"), ("PATCH", "/directory/contacts/1"), ("DELETE", "/directory/contacts/1"),
    ("PATCH", "/directory/users/1/role"), ("POST", "/admin/users"), ("POST", "/admin/users/1/lock"),
    ("POST", "/directory/access/users/1/password-reset"), ("POST", "/admin/access/grants"),
    ("POST", "/admin/personnel/identity/user-linkage/execute"),
])
def test_contact_reads_never_enable_contact_or_account_changes(assistant_http, method, path):
    _call(assistant_http, method, path, {}, status=403)
