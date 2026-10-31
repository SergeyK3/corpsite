"""Documentation access: explicit operation policy, never an admin permission.

Unknown operations are denied, including GETs. Only reviewed pure previews are
allowed as POSTs. PostgreSQL read-only transactions provide a second boundary
against accidental writes in a read service (including data-modifying CTEs).
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import event, text
from sqlalchemy.engine import Engine

ROLE_CODE = "DOCUMENTATION_VIEWER"
READ_PERMISSION = "DOCUMENTATION_READ"
_reading: ContextVar[bool] = ContextVar("documentation_reading", default=False)


def is_documentation_viewer(user: dict[str, Any]) -> bool:
    return str(user.get("role_code") or "").upper() == ROLE_CODE


def is_standalone_profile(user: dict[str, Any]) -> bool:
    return str(user.get("role_code") or "").upper() in {ROLE_CODE, "SYSADMIN_ASSISTANT"}


def documentation_read_allowed(user: dict[str, Any]) -> bool:
    return is_standalone_profile(user) and _reading.get()


# Route templates, not prefixes: new endpoints require a semantic review.
READ_OPERATIONS = frozenset(("GET", path) for path in """
/auth/me
/meta/task-statuses
/personnel/settings
/regular-tasks
/regular-tasks/{regular_task_id}
/regular-tasks/scheduler-status
/regular-task-runs
/regular-task-runs/{run_id}/items
/directory/org-units/tree
/directory/org-units
/directory/departments/tree
/directory/departments
/directory/department-groups
/directory/employees
/directory/employees/{employee_id}
/directory/employees/{employee_id}/events
/directory/roles
/directory/position-families
/directory/job-positions
/directory/positions
/directory/positions/{position_id}
/directory/positions/{position_id}/dependencies
/directory/contacts
/directory/contacts/{contact_id}
/directory/users
/directory/working-contacts
/directory/working-contacts/{user_id}
/directory/personnel-events
/directory/hr-event-registry
/directory/document-types
/directory/document-kinds
/directory/medical-specialty-groups
/directory/medical-specialties
/directory/medical-specialties/{specialty_id}
/directory/medical-qualification-categories
/directory/employee-documents
/directory/employee-documents/training-summary
/directory/employee-documents/{document_id}
/directory/personnel-orders
/directory/personnel-orders/signatory-default
/directory/personnel-orders/templates/{item_type_code}/published-variants
/directory/personnel-orders/templates/{item_type_code}/published-title
/directory/personnel-orders/{order_id}
/directory/personnel-orders/{order_id}/add-item-context
/directory/personnel-orders/{order_id}/template-application/preview
/directory/personnel-orders/{order_id}/editorial
/directory/personnel-orders/{order_id}/acknowledgements
/directory/personnel-orders/{order_id}/lifecycle-audit
/directory/personnel-orders/{order_id}/document-review
/directory/personnel-orders/{order_id}/document-history
/directory/personnel-orders/{order_id}/document-items
/directory/personnel-orders/{order_id}/draft-deletion-preview
/directory/personnel-applications
/directory/personnel-applications/{application_id}
/directory/personnel-applications/{application_id}/timeline
/directory/hiring-document-checklist
/directory/personnel/employees/{employee_id}/access
/directory/personnel/employees/{employee_id}/access/termination-preview
/directory/access/users
/admin/org-units
/admin/org-units/{unit_id}
/admin/org-units/{unit_id}/dependencies
/admin/personnel-order-templates
/admin/personnel-order-templates/{item_type_code}/templates
/admin/personnel-order-templates/{item_type_code}/versions
/admin/personnel-order-templates/{item_type_code}/draft
/admin/personnel-order-templates/{item_type_code}/published
/admin/personnel-order-templates/{item_type_code}/editor-base
/admin/personnel-order-templates/{item_type_code}/draft/preview
/admin/access/roles
/admin/access/guard-mode
/admin/access/targets/search
/admin/access/effective
/admin/access/effective/{user_id}
/admin/access/grants
/admin/enrollment/queue
/admin/enrollment/queue/{queue_id}/explain
/admin/assignments/drift
/admin/security-audit
/admin/users
/admin/users/{user_id}
/admin/personnel/visibility/assignments
/admin/personnel/visibility/effective
/admin/system/telegram-health
/admin/personnel/lifecycle/runs
/admin/personnel/lifecycle/runs/{run_id}
/admin/personnel/lifecycle/validation
/admin/personnel/events
/admin/personnel/events/{event_id}
/admin/personnel/overrides
/admin/personnel/overrides/{override_id}
/admin/personnel/effective-person
/admin/personnel/identity/user-linkage/preview
/admin/personnel/identity/user-linkage/review
/admin/personnel/identity/user-linkage/review/audit
/admin/personnel/identity/user-linkage/operations/runs
/admin/personnel/identity/user-linkage/operations/runs/{run_id}
/admin/personnel/identity/user-linkage/operations/items
/admin/personnel/identity/user-linkage/operations/items/{item_id}
/api/ppr/persons/{person_id}
/api/ppr/persons/{person_id}/summary
/api/ppr/persons/{person_id}/photo
/api/ppr/persons/{person_id}/contacts
/api/ppr/persons/{person_id}/operational-assignment
/api/ppr/persons/{person_id}/hire-defaults
/api/ppr/persons/{person_id}/applications
/api/ppr/employees/{employee_id}
/api/ppr/education-program-kinds
/api/ppr/education-levels
/api/ppr/education-levels/selection
/api/ppr/document-kinds
/api/ppr/document-kinds/selection
""".split()) | frozenset({
    # These compute results from supplied values; they do not save a draft,
    # generate persisted editorial blocks, register an application or audit a run.
    ("POST", "/admin/personnel-order-templates/{item_type_code}/draft/preview"),
    ("POST", "/directory/personnel-orders/header-duplicate-preview"),
})

ACCOUNT_OPERATIONS = frozenset({("POST", "/auth/login"), ("GET", "/auth/me"), ("POST", "/auth/password-change")})


@event.listens_for(Engine, "begin")
def _read_only_transaction(conn) -> None:
    if _reading.get() and conn.dialect.name == "postgresql":
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")


async def enforce_documentation_request(request: Request):
    """Global dependency: protects JWT and legacy routes before their handlers.

    Authentication and role are reloaded from the DB, never taken from JWT role
    claims or client capability flags. Other users retain their existing guards.
    """
    route = request.scope.get("route")
    operation = (request.method, getattr(route, "path", ""))
    if operation == ("POST", "/auth/login"):
        # Login authenticates its supplied credentials itself, even if a client
        # sends an old session header. Only authentication state can be changed.
        yield
        return
    from starlette.concurrency import run_in_threadpool
    from app.auth import _get_user_by_id, decode_and_verify_token, is_user_locked
    from app.db.engine import engine
    from app.security.auth_policy import validate_token_version_claim

    authorization = request.headers.get("authorization", "").split()
    payload = None
    uid = None
    if len(authorization) == 2 and authorization[0].lower() == "bearer":
        try:
            payload = decode_and_verify_token(authorization[1])
            uid = int(payload["sub"])
        except Exception:
            pass  # Existing authentication determines the response for others.
    if uid is None and request.headers.get("x-user-id"):
        try:
            uid = int(request.headers["x-user-id"])
        except ValueError:
            pass

    def lookup_role():
        with engine.connect() as conn:
            return conn.execute(text("""SELECT r.code FROM public.users u
                JOIN public.roles r ON r.role_id=u.role_id WHERE u.user_id=:uid"""),
                {"uid": uid}).scalar_one_or_none()

    if uid is None or await run_in_threadpool(lookup_role) not in {ROLE_CODE, "SYSADMIN_ASSISTANT"}:
        yield
        return
    if payload is None:
        raise HTTPException(401, "Documentation access requires a Bearer token.")
    user = await run_in_threadpool(_get_user_by_id, uid)
    if not user or not user["is_active"] or is_user_locked(user):
        raise HTTPException(403, "Account unavailable.")
    validate_token_version_claim(payload, user)
    if user.get("must_change_password") and operation not in ACCOUNT_OPERATIONS:
        raise HTTPException(403, "Password change required.")
    if operation in ACCOUNT_OPERATIONS:
        yield
        return
    from app.security.sysadmin_assistant import is_assistant, OPERATIONS, _action
    from app.security.admin_permissions import has_admin_permission
    if is_assistant(user) and operation in OPERATIONS:
        permission = OPERATIONS[operation]
        if not await run_in_threadpool(has_admin_permission, uid, permission):
            raise HTTPException(403, f"Permission required: {permission}")
        from uuid import uuid4
        marker = _action.set({"actor_user_id": uid, "permission": permission,
            "method": request.method, "route": operation[1],
            "path_params": dict(request.path_params), "request_id": uuid4().hex,
            "stage": "transaction_commit"})
        try:
            yield
        finally:
            _action.reset(marker)
        return
    if operation not in READ_OPERATIONS:
        raise HTTPException(403, f"{user['role_code']}: operation is not available.")
    if not await run_in_threadpool(has_admin_permission, uid, READ_PERMISSION):
        raise HTTPException(403, "Permission required: DOCUMENTATION_READ")
    token = _reading.set(True)
    try:
        yield
    finally:
        _reading.reset(token)
