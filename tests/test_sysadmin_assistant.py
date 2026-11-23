"""Assistant HTTP authorization and transactional ownership/audit contracts."""
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

import app.auth as auth
from app.main import app
from app.db.engine import engine
from app.security import documentation_viewer as reading
from app.security import sysadmin_assistant as assistant_policy
from app.directory.rbac import require_personnel_admin_or_403
from tests.test_documentation_viewer import viewer


@pytest.fixture
def assistant(viewer, monkeypatch):
    user, headers = viewer
    user["role_code"] = "SYSADMIN_ASSISTANT"
    allowed = set(assistant_policy.PERMISSIONS) | {reading.READ_PERMISSION}
    import app.security.admin_permissions as permissions
    monkeypatch.setattr(permissions, "has_admin_permission", lambda uid, code: code in allowed)
    return user, headers, allowed


def detail(status="DRAFT", actor=970001):
    return {"order": {"order_id": 71, "order_type_code": "HIRE", "order_class": "PERSONNEL",
        "status": status, "source_mode": "PAPER", "created_by": actor},
        "items": [], "localized_texts": [], "attachments": [], "prints": [], "events": []}


def test_assistant_is_unlinked_and_does_not_receive_admin_capabilities(assistant):
    response = TestClient(app).get("/auth/me", headers=assistant[1])
    assert response.status_code == 200
    user = response.json()
    assert user["is_sysadmin_assistant"] and not user["is_documentation_viewer"]
    assert user["employee_id"] is None
    assert all(user["assistant_permissions"].values())
    for code in ("has_sysadmin_api", "has_personnel_admin", "has_user_access_admin", "is_privileged", "is_system_admin"):
        assert not user[code]


@pytest.mark.parametrize("method,path", [
    ("POST", "/directory/roles"), ("PUT", "/directory/roles/1"), ("DELETE", "/directory/roles/1"),
    ("POST", "/directory/positions"), ("PUT", "/directory/positions/1"), ("DELETE", "/directory/positions/1"),
    ("POST", "/directory/medical-specialties"), ("PATCH", "/directory/org-units/1"),
    ("POST", "/api/ppr/education-levels"), ("POST", "/directory/department-groups"),
    ("POST", "/admin/users"), ("PATCH", "/directory/users/1/role"), ("POST", "/admin/users/1/lock"),
    ("POST", "/directory/access/users/1/password-reset"), ("POST", "/admin/access/grants"),
    ("PUT", "/personnel/settings"), ("POST", "/admin/org-units"),
    ("POST", "/admin/personnel-order-templates/HIRE/draft"),
    ("PUT", "/admin/personnel-order-templates/HIRE/draft"),
    ("POST", "/admin/personnel-order-templates/HIRE/draft/publish"),
    ("POST", "/admin/personnel-order-templates/HIRE/copies"),
    ("DELETE", "/directory/personnel-orders/71/hr-head"),
    ("POST", "/directory/personnel-orders/71/void"),
    ("POST", "/directory/personnel-orders/71/acknowledgements/clear"),
    ("PATCH", "/directory/employees/1"), ("DELETE", "/directory/employees/1"),
    ("POST", "/regular-tasks"), ("POST", "/directory/personnel/sync/apply"),
])
def test_forbidden_direct_api_calls(assistant, method, path):
    response = TestClient(app).request(method, path, headers=assistant[1], json={})
    assert response.status_code == 403, (path, response.text)
    assert "SYSADMIN_ASSISTANT" in response.text


def test_all_declared_operations_require_separate_grants_and_allow_standard_guard(assistant):
    user, headers, allowed = assistant
    probe = FastAPI(dependencies=[Depends(reading.enforce_documentation_request)])
    def endpoint():
        require_personnel_admin_or_403(user)
        assert not reading._reading.get(), "Writes must not use the read-only bypass"
        return {"actor": assistant_policy._action.get()["actor_user_id"]}
    for (method, path), permission in assistant_policy.OPERATIONS.items():
        probe.add_api_route(path, endpoint, methods=[method])
    client = TestClient(probe)
    for (method, path), permission in assistant_policy.OPERATIONS.items():
        url = path.replace("{order_id}", "71").replace("{item_id}", "1").replace("{block_id}", "1").replace("{locale}", "ru")
        assert client.request(method, url, headers=headers).json() == {"actor": user["user_id"]}
        allowed.remove(permission)
        assert client.request(method, url, headers=headers).status_code == 403
        allowed.add(permission)
    assert assistant_policy._action.get() is None


def test_real_apply_route_has_no_demo_or_employee_filter_and_uses_personal_actor(assistant, monkeypatch):
    import app.directory.personnel_orders_routes as routes
    service = MagicMock(return_value=detail("REGISTERED"))
    monkeypatch.setattr(routes, "apply_personnel_order", service)
    response = TestClient(app).post("/directory/personnel-orders/71/apply", headers=assistant[1])
    assert response.status_code == 200, response.text
    service.assert_called_once_with(order_id=71, created_by=assistant[0]["user_id"])


def test_standard_apply_conflict_is_not_bypassed(assistant, monkeypatch):
    import app.directory.personnel_orders_routes as routes
    service = MagicMock(side_effect=routes.PersonnelOrderAlreadyAppliedError("already applied"))
    monkeypatch.setattr(routes, "apply_personnel_order", service)
    response = TestClient(app).post("/directory/personnel-orders/71/apply", headers=assistant[1])
    assert response.status_code == 409


def test_register_and_create_use_existing_services(assistant, monkeypatch):
    import app.directory.personnel_orders_routes as routes
    create = MagicMock(return_value=detail())
    register = MagicMock(return_value=detail("REGISTERED"))
    monkeypatch.setattr(routes, "create_personnel_order_draft", create)
    monkeypatch.setattr(routes, "register_personnel_order", register)
    client = TestClient(app)
    response = client.post("/directory/personnel-orders", headers=assistant[1], json={
        "order_number": "DEMO-ASSISTANT", "order_date": "2026-10-31", "order_type_code": "HIRE", "source_mode": "PAPER"})
    assert response.status_code == 201, response.text
    assert create.call_args.kwargs["created_by"] == assistant[0]["user_id"]
    assert client.post("/directory/personnel-orders/71/register", headers=assistant[1],
        json={"target_status": "REGISTERED"}).status_code == 200
    register.assert_called_once_with(order_id=71, target_status="REGISTERED")


@pytest.mark.parametrize("owner,status,expected", [(970001,"DRAFT",200),(42,"DRAFT",403),
    (970001,"REGISTERED",409),(970001,"SIGNED",409)])
def test_deletion_checks_locked_owner_and_existing_status(assistant, monkeypatch, owner, status, expected):
    from app.services import personnel_order_draft_deletion_service as deletion
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "order_id": 71, "created_by": owner, "status": status, "deleted_at": None}
    conn.execute.return_value.scalars.return_value = []
    monkeypatch.setattr(deletion, "_fk_rows", lambda *args: [])
    action = assistant_policy._action.set({"actor_user_id":970001,"permission":assistant_policy.DELETE_OWN})
    try:
        if expected == 200:
            assert deletion._preview_tx(conn, 71, lock=True)["can_delete"]
        elif expected == 403:
            with pytest.raises(HTTPException) as denied:
                deletion._preview_tx(conn, 71, lock=True)
            assert denied.value.status_code == 403
        else:
            with pytest.raises(deletion.DraftDeletionError) as denied:
                deletion._preview_tx(conn, 71, lock=True)
            assert denied.value.status_code == expected
        assert "FOR UPDATE" in str(conn.execute.call_args_list[0].args[0])
    finally:
        assistant_policy._action.reset(action)


def test_deletion_keeps_dependency_blockers(assistant, monkeypatch):
    from app.services import personnel_order_draft_deletion_service as deletion
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.return_value = {"order_id":71,"created_by":970001,"status":"DRAFT"}
    conn.execute.return_value.scalars.return_value = []
    monkeypatch.setattr(deletion, "_fk_rows", lambda *args: [{"table":"employee_events","count":1}])
    assert not deletion._preview_tx(conn,71,owner_user_id=970001)["can_delete"]


def test_item_deletion_rejects_foreign_parent_before_any_deletes(assistant, monkeypatch):
    from app.services import personnel_orders_command_service as commands
    monkeypatch.setattr(commands,"_require_available",lambda:None)
    monkeypatch.setattr(commands,"lock_personnel_order_evidence_scopes_tx",lambda *a,**k:[])
    monkeypatch.setattr(commands,"_fetch_order_row",lambda *a:{"created_by":42,"status":"DRAFT"})
    conn=MagicMock()
    @contextmanager
    def begin(): yield conn
    monkeypatch.setattr(commands.engine,"begin",begin)
    token=assistant_policy._action.set({"actor_user_id":970001,"permission":assistant_policy.DELETE_OWN})
    try:
        with pytest.raises(HTTPException): commands.delete_personnel_order_item(order_id=71,item_id=1)
        conn.execute.assert_not_called()
    finally: assistant_policy._action.reset(token)


def test_item_deletion_rejects_applied_own_order_even_with_legacy_draft_status(assistant, monkeypatch):
    from app.services import personnel_orders_command_service as commands
    monkeypatch.setattr(commands,"_require_available",lambda:None)
    monkeypatch.setattr(commands,"lock_personnel_order_evidence_scopes_tx",lambda *a,**k:[])
    monkeypatch.setattr(commands,"_fetch_order_row",lambda *a:{"created_by":970001,"status":"DRAFT"})
    conn=MagicMock();conn.execute.return_value.scalar_one.return_value=True
    @contextmanager
    def begin(): yield conn
    monkeypatch.setattr(commands.engine,"begin",begin)
    token=assistant_policy._action.set({"actor_user_id":970001,"permission":assistant_policy.DELETE_OWN})
    try:
        with pytest.raises(commands.PersonnelOrderConflictError): commands.delete_personnel_order_item(order_id=71,item_id=1)
        assert not any("DELETE" in str(c.args[0]) for c in conn.execute.call_args_list)
    finally: assistant_policy._action.reset(token)


def test_delete_route_uses_actor_not_client_supplied_owner(assistant, monkeypatch):
    import app.directory.personnel_orders_routes as routes
    service=MagicMock(return_value={"status":"SOFT_DELETED","order_id":71})
    monkeypatch.setattr(routes.draft_deletion,"execute",service)
    response=TestClient(app).request(
        "DELETE","/directory/personnel-orders/71",headers=assistant[1],json={"reason":"own demo draft",
        "confirmation_phrase":"DELETE DRAFT ORDER 71","owner_user_id":42})
    assert response.status_code==200,response.text
    assert service.call_args.kwargs["actor_user_id"]==970001
    assert service.call_args.kwargs["owner_user_id"]==970001


def test_manual_demonstration_draft_needs_no_employee_account(assistant, monkeypatch):
    import app.directory.personnel_orders_routes as routes
    service=MagicMock(return_value={"order_id":71,"order_number":"DEMO-71","order_type_code":"HIRE",
        "status":"DRAFT","source_mode":"MANUAL","document_revision":1,"document_review_state":"NEEDS_REVIEW"})
    monkeypatch.setattr(routes,"create_manual_draft",service)
    response=TestClient(app).post("/directory/personnel-orders/manual-draft",headers=assistant[1],json={
        "order_number":"DEMO-71","order_date":"2026-10-31","source_title":"Демонстрационный приказ",
        "source_title_locale":"ru","item_type_code":"HIRE","effective_date":"2026-10-31",
        "unresolved_subject":{"full_name":"Демонстрационный субъект"}})
    assert response.status_code==201,response.text
    assert service.call_args.kwargs["created_by"]==970001
    # A missing keyword also looks like None through .get(), but crashes the
    # real service, whose employee_id keyword is required for manual subjects.
    assert service.call_args.kwargs["employee_id"] is None


def test_business_audit_is_atomic_and_uses_personal_actor():
    conn=MagicMock();conn.dialect.name="postgresql"
    token=assistant_policy._action.set({"actor_user_id":970001,"permission":assistant_policy.APPLY,
        "route":"/directory/personnel-orders/{order_id}/apply","path_params":{"order_id":71}})
    try:
        assistant_policy.audit_assistant_transaction(conn)
        assert conn.execute.call_args.args[1]["actor"] == 970001
        assert '"order_id": 71' in conn.execute.call_args.args[1]["metadata"]
        conn.execute.side_effect=RuntimeError("audit unavailable")
        with pytest.raises(RuntimeError): assistant_policy.audit_assistant_transaction(conn)
    finally: assistant_policy._action.reset(token)


def test_assistant_first_login_and_legacy_bypass(assistant):
    assistant[0]["must_change_password"]=True
    client=TestClient(app)
    assert client.post("/directory/personnel-orders/71/apply",headers=assistant[1]).status_code==403
    assert client.get("/auth/me",headers=assistant[1]).json()["must_change_password"]
    assert client.post("/auth/password-change",headers=assistant[1],json={}).status_code==422
    assert client.post("/directory/personnel-orders/71/apply",headers={"X-User-Id":"970001"}).status_code==401


def test_operation_templates_exist():
    from fastapi.routing import APIRoute
    actual={(method,r.path) for r in app.routes if isinstance(r,APIRoute) for method in r.methods}
    assert not (set(assistant_policy.OPERATIONS)-actual)


def test_create_assistant_account_has_only_specific_grants(monkeypatch):
    import app.services.documentation_accounts_service as accounts
    conn=MagicMock()
    conn.execute.return_value.scalar_one_or_none.side_effect=[2,970001,100,101,102,103,104]
    conn.execute.return_value.scalar_one.return_value=970002
    conn.execute.return_value.first.return_value=None
    @contextmanager
    def begin(): yield conn
    monkeypatch.setattr(engine,"begin",begin)
    monkeypatch.setattr(accounts,"_fetch_user",lambda c,uid:{"user_id":uid,"employee_id":None,"must_change_password":True})
    audit=MagicMock();monkeypatch.setattr(accounts,"write_security_event",audit)
    result=accounts.create_documentation_account(full_name="Assistant",login="helper",temporary_password="Temporary123",
        actor_user_id=2,profile_code="SYSADMIN_ASSISTANT")
    assert result["employee_id"] is None and result["must_change_password"]
    grants=[call for call in conn.execute.call_args_list if "INSERT INTO public.access_grants" in str(call.args[0])]
    assert len(grants)==5
    metadata=audit.call_args.kwargs["metadata"]
    assert metadata["role_code"]=="SYSADMIN_ASSISTANT"
    assert set(metadata["access_role_codes"])==assistant_policy.PERMISSIONS|{"DOCUMENTATION_READ"}
