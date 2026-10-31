"""HTTP policy tests use DB doubles; the PostgreSQL test only uses corpsite_test."""
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

import app.auth as auth
import app.security.documentation_viewer as policy
from app.db.engine import engine
from app.main import app
from app.security.admin_guard import require_sysadmin_api, evaluate_admin_access
from app.security.personnel_admin_guard import require_personnel_admin_api
from app.security.directory_scope import is_privileged

_lookup_user = auth._get_user_by_id


@pytest.fixture(autouse=True)
def _cleanup_orphan_hr_baseline_artifacts():
    # These tests own no persistent business records.
    yield


@pytest.fixture
def viewer(monkeypatch):
    user = {"user_id": 970001, "role_id": 970001, "role_code": policy.ROLE_CODE,
            "full_name": "Documentation test", "login": "documentation_test",
            "employee_id": None, "unit_id": None, "is_active": True,
            "token_version": 1, "must_change_password": False, "locked_at": None}
    monkeypatch.setattr(auth, "_get_user_by_id", lambda uid: dict(user))
    connection = MagicMock()
    connection.execute.return_value.scalar_one_or_none.side_effect = lambda: user["role_code"]
    @contextmanager
    def connect():
        yield connection
    monkeypatch.setattr(engine, "connect", connect)
    import app.security.admin_permissions as permissions
    monkeypatch.setattr(permissions, "has_admin_permission", lambda uid, code: code == policy.READ_PERMISSION)
    token = auth.create_access_token(user["user_id"], token_version=1)
    return user, {"Authorization": f"Bearer {token}"}


def test_unlinked_me_has_no_administrative_write_capabilities(viewer):
    user, headers = viewer
    response = TestClient(app).get("/auth/me", headers=headers)
    assert response.status_code == 200
    me = response.json()
    assert me["employee_id"] is None and me["is_documentation_viewer"]
    for name in ("is_privileged", "is_system_admin", "has_sysadmin_api",
                 "has_personnel_admin", "has_user_access_admin", "has_personnel_card_edit"):
        assert me[name] is False
    assert not is_privileged(user)
    assert not evaluate_admin_access(user)


def test_login_without_employee_link(viewer, monkeypatch):
    user, headers = viewer
    monkeypatch.setattr(auth, "_get_user_auth_row_by_login", lambda login: {
        **user, "password_hash": auth.hash_password("Temporary123")})
    success = MagicMock()
    monkeypatch.setattr(auth, "record_login_success", success)
    client = TestClient(app)
    response = client.post("/auth/login", headers=headers, json={"login": user["login"], "password": "Temporary123"})
    assert response.status_code == 200
    success.assert_called_once()
    response = client.get("/auth/me", headers={"Authorization": "Bearer " + response.json()["access_token"]})
    assert response.status_code == 200 and response.json()["employee_id"] is None


def test_real_user_lookup_accepts_null_employee_and_unit(monkeypatch):
    row = {"user_id": 970001, "role_id": 970001, "role_code": policy.ROLE_CODE,
        "role_name_ru": "Documentation", "unit_id": None, "employee_id": None,
        "is_active": True, "full_name": "Author", "login": "guide"}
    monkeypatch.setattr(auth, "fetch_user_auth_policy_row", lambda uid: {"token_version": 1})
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.first.return_value = row
    @contextmanager
    def connect():
        yield connection
    monkeypatch.setattr(engine, "connect", connect)
    user = _lookup_user(970001)
    assert user["employee_id"] is None and user["unit_id"] is None
    assert "LEFT JOIN public.employees" in str(connection.execute.call_args.args[0])


def test_create_service_sets_unlinked_profile_and_audits_without_password(monkeypatch):
    import app.services.documentation_accounts_service as accounts
    conn = MagicMock()
    conn.execute.return_value.scalar_one_or_none.side_effect = [2, 970001, 970003]
    conn.execute.return_value.first.return_value = None
    conn.execute.return_value.scalar_one.return_value = 970002
    @contextmanager
    def begin():
        yield conn
    monkeypatch.setattr(engine, "begin", begin)
    monkeypatch.setattr(accounts, "_fetch_user", lambda c, uid: {"user_id": uid, "employee_id": None,
        "login": "guide", "must_change_password": True})
    audit = MagicMock()
    monkeypatch.setattr(accounts, "write_security_event", audit)
    result = accounts.create_documentation_account(full_name="Guide author", login="GUIDE",
        temporary_password="Temporary123", actor_user_id=2)
    assert result["employee_id"] is None and result["must_change_password"]
    insert = next(c for c in conn.execute.call_args_list if "INSERT INTO public.users" in str(c.args[0]))
    assert "NULL,NULL,TRUE,TRUE,1" in str(insert.args[0])
    assert insert.args[1]["role"] == 970001
    assert insert.args[1]["login"] == "guide"
    assert auth.verify_password("Temporary123", insert.args[1]["hash"])
    grant = next(c for c in conn.execute.call_args_list if "INSERT INTO public.access_grants" in str(c.args[0]))
    assert grant.args[1] == {"permission": 970003, "uid": 970002, "actor": 2}
    assert "Temporary123" not in str(audit.call_args)
    assert not any("INSERT INTO public.employees" in str(c.args[0]) for c in conn.execute.call_args_list)


def test_create_service_rejects_non_system_administrator(monkeypatch):
    from app.services.documentation_accounts_service import create_documentation_account
    conn = MagicMock()
    conn.execute.return_value.scalar_one_or_none.return_value = 8
    @contextmanager
    def begin():
        yield conn
    monkeypatch.setattr(engine, "begin", begin)
    with pytest.raises(PermissionError):
        create_documentation_account(full_name="Author", login="guide",
            temporary_password="Temporary123", actor_user_id=8)
    assert not any("INSERT" in str(c.args[0]) for c in conn.execute.call_args_list)


def test_read_surfaces_use_real_http_guards(viewer, monkeypatch):
    import app.api.admin_router as admin
    import app.directory.employees_routes as employees
    import app.directory.personnel_orders_routes as orders
    monkeypatch.setattr(admin, "list_personnel_order_template_catalog", lambda **kw: [])
    monkeypatch.setattr(employees, "svc_list_employees", lambda **kw: {"items": [], "total": 0})
    monkeypatch.setattr(orders, "list_personnel_orders", lambda **kw: {"items": [], "total": 0, "limit": 100, "offset": 0})
    client = TestClient(app)
    for path in ("/admin/personnel-order-templates", "/directory/employees", "/directory/personnel-orders"):
        response = client.get(path, headers=viewer[1])
        assert response.status_code == 200, (path, response.text)


def test_viewer_routes_in_policy_exist():
    from fastapi.routing import APIRoute
    operations = {(method, r.path) for r in app.routes if isinstance(r, APIRoute) for method in r.methods}
    assert not (policy.READ_OPERATIONS - operations)


@pytest.mark.parametrize("method,path", [
    ("POST", "/admin/users"), ("POST", "/admin/access/grants"),
    ("POST", "/admin/users/1/lock"), ("POST", "/directory/access/users/1/password-reset"),
    ("PATCH", "/directory/users/1/role"), ("POST", "/directory/employees"),
    ("PATCH", "/directory/employees/1"), ("DELETE", "/directory/employees/1"),
    ("POST", "/directory/personnel-orders"),
    ("POST", "/directory/personnel-orders/manual-draft"),
    ("PATCH", "/directory/personnel-orders/1"),
    ("POST", "/directory/personnel-orders/1/apply"),
    ("POST", "/directory/personnel-orders/1/editorial/generate"),
    ("POST", "/directory/personnel-orders/1/template-application"),
    ("POST", "/admin/personnel-order-templates/HIRE/draft"),
    ("PUT", "/admin/personnel-order-templates/HIRE/draft"),
    ("POST", "/admin/personnel-order-templates/HIRE/draft/publish"),
    ("POST", "/api/ppr/persons/1/photo"),
    ("PUT", "/api/ppr/persons/1/contacts"),
    ("POST", "/directory/roles"), ("POST", "/tasks/manual"),
    ("POST", "/regular-tasks"), ("POST", "/import-xlsx"),
    ("POST", "/auth/self-bind"), ("POST", "/directory/personnel/sync/export"),
    # GETs outside the reviewed list are also denied.
    ("GET", "/directory/_debug/rbac"),
    ("GET", "/directory/technical-personnel-order-cleanup/search"),
])
def test_direct_mutations_and_unreviewed_reads_denied_before_handler(viewer, method, path):
    _, headers = viewer
    response = TestClient(app).request(method, path, headers=headers)
    assert response.status_code == 403, response.text
    assert "DOCUMENTATION_VIEWER" in response.text


def test_mandatory_password_change_even_when_legacy_flag_is_disabled(viewer, monkeypatch):
    user, headers = viewer
    monkeypatch.setenv("ADR042_MUST_CHANGE_PASSWORD_ENFORCEMENT", "false")
    user["must_change_password"] = True
    client = TestClient(app)
    assert client.get("/auth/me", headers=headers).json()["must_change_password"]
    assert client.get("/admin/users", headers=headers).json()["detail"] == "Password change required."
    # Reaches the password endpoint's body validation, rather than a policy denial.
    assert client.post("/auth/password-change", headers=headers, json={}).status_code == 422


@pytest.mark.parametrize("authorization", [None, "Bearer invalid-token"])
def test_legacy_identity_cannot_bypass_viewer_policy(viewer, authorization):
    headers = {"X-User-Id": "970001"}
    if authorization:
        headers["Authorization"] = authorization
    response = TestClient(app).post("/directory/personnel-orders", headers=headers, json={})
    assert response.status_code == 401


def test_read_guards_allow_only_inside_reviewed_request(viewer, monkeypatch):
    import app.api.admin_router as admin_router
    monkeypatch.setattr(admin_router, "list_admin_users", lambda **kw: {"items": [{"user_id": 1}]})
    _, headers = viewer
    assert TestClient(app).get("/admin/users", headers=headers).status_code == 200
    assert not policy._reading.get()
    with pytest.raises(HTTPException) as denied:
        require_sysadmin_api(viewer[0])
    assert denied.value.status_code == 403


def test_read_permission_can_be_revoked(viewer, monkeypatch):
    import app.security.admin_permissions as permissions
    monkeypatch.setattr(permissions, "has_admin_permission", lambda *args: False)
    response = TestClient(app).get("/admin/users", headers=viewer[1])
    assert response.status_code == 403
    assert "DOCUMENTATION_READ" in response.text


def test_reviewed_post_preview_allowed_but_get_side_effect_not_allowed(viewer):
    probe = FastAPI(dependencies=[Depends(policy.enforce_documentation_request)])
    @probe.post("/admin/personnel-order-templates/{item_type_code}/draft/preview")
    def preview(item_type_code: str, user=Depends(require_sysadmin_api)):
        return {"reading": policy._reading.get()}
    @probe.get("/dangerous-read")
    def dangerous_read():
        pytest.fail("Unreviewed GET handler must not execute")
    client = TestClient(probe)
    assert client.post("/admin/personnel-order-templates/HIRE/draft/preview", headers=viewer[1]).json() == {"reading": True}
    assert client.get("/dangerous-read", headers=viewer[1]).status_code == 403


def test_real_template_preview_computes_without_saving(viewer):
    from app.services.personnel_order_template_specs import get_personnel_order_template_spec
    values = dict(get_personnel_order_template_spec("TERMINATION").initial_texts)
    response = TestClient(app).post("/admin/personnel-order-templates/TERMINATION/draft/preview",
        headers=viewer[1], json=values)
    assert response.status_code == 200, response.text
    assert "previews" in response.json()


def test_personnel_guard_read_only_scope(viewer):
    token = policy._reading.set(True)
    try:
        assert require_personnel_admin_api(viewer[0]) == viewer[0]
    finally:
        policy._reading.reset(token)


def test_read_only_transaction_hook():
    conn = MagicMock()
    conn.dialect.name = "postgresql"
    token = policy._reading.set(True)
    try:
        policy._read_only_transaction(conn)
        conn.exec_driver_sql.assert_called_once_with("SET TRANSACTION READ ONLY")
    finally:
        policy._reading.reset(token)
    conn.reset_mock()
    policy._read_only_transaction(conn)
    conn.exec_driver_sql.assert_not_called()


def test_ordinary_user_operations_are_unchanged(viewer):
    viewer[0]["role_code"] = "EMPLOYEE"
    probe = FastAPI(dependencies=[Depends(policy.enforce_documentation_request)])
    @probe.post("/business-write")
    def write():
        return {"reading": policy._reading.get()}
    assert TestClient(probe).post("/business-write", headers=viewer[1]).json() == {"reading": False}


def test_postgres_read_only_rejects_data_modifying_cte():
    assert engine.url.database == "corpsite_test", "Only corpsite_test is authorized"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except DBAPIError:
        pytest.skip("corpsite_test is unavailable")
    token = policy._reading.set(True)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
            with pytest.raises(DBAPIError) as error:
                conn.execute(text("WITH changed AS (UPDATE public.users SET full_name=full_name WHERE FALSE RETURNING user_id) SELECT * FROM changed"))
            assert getattr(error.value.orig, "pgcode", "") == "25006"
    finally:
        policy._reading.reset(token)
