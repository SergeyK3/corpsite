"""Explicit assistant operations; no administrative-role escalation."""
from contextvars import ContextVar
from typing import Any

import json
from sqlalchemy import event, text
from sqlalchemy.engine import Engine

ROLE_CODE = "SYSADMIN_ASSISTANT"
EDIT = "ASSISTANT_PERSONNEL_ORDERS_EDIT"
REGISTER = "ASSISTANT_PERSONNEL_ORDERS_REGISTER"
APPLY = "ASSISTANT_PERSONNEL_ORDERS_APPLY"
DELETE_OWN = "ASSISTANT_PERSONNEL_ORDERS_DELETE_OWN"
PERMISSIONS = frozenset({EDIT, REGISTER, APPLY, DELETE_OWN})
_action: ContextVar[dict | None] = ContextVar("sysadmin_assistant_action", default=None)

OPERATIONS = {
    **{(method, "/directory/personnel-orders" + path): EDIT for method, path in (
        ("POST", ""), ("POST", "/manual-draft"), ("PATCH", "/{order_id}"),
        ("POST", "/{order_id}/items"), ("PATCH", "/{order_id}/items/{item_id}"),
        ("PUT", "/{order_id}/localized-texts/{locale}"),
        ("POST", "/{order_id}/ready-for-signature"),
        ("POST", "/{order_id}/template-application"),
        ("POST", "/{order_id}/editorial/generate"),
        ("PATCH", "/{order_id}/editorial/blocks/{block_id}"),
        ("POST", "/{order_id}/editorial/blocks/{block_id}/reset-to-generated"),
        ("POST", "/{order_id}/document-review/confirm"),
        ("POST", "/{order_id}/document-review/reopen"),
        ("PATCH", "/{order_id}/document-header"),
        ("PATCH", "/{order_id}/document-items/{item_id}"),
        ("POST", "/{order_id}/acknowledgements"),
    )},
    ("POST", "/directory/personnel-orders/{order_id}/register"): REGISTER,
    ("POST", "/directory/personnel-orders/{order_id}/apply"): APPLY,
    ("DELETE", "/directory/personnel-orders/{order_id}"): DELETE_OWN,
    ("DELETE", "/directory/personnel-orders/{order_id}/items/{item_id}"): DELETE_OWN,
}


def is_assistant(user: dict[str, Any]) -> bool:
    return str(user.get("role_code") or "").upper() == ROLE_CODE


def assistant_order_operation_allowed(user: dict[str, Any]) -> bool:
    action = _action.get()
    return bool(is_assistant(user) and action and action["actor_user_id"] == int(user["user_id"]))


def assert_delete_owner(order: dict[str, Any], *, owner_user_id: int | None = None) -> None:
    """Call after loading/locking the parent, before existing deletion rules."""
    from fastapi import HTTPException
    action = _action.get()
    if owner_user_id is None and action and action["permission"] == DELETE_OWN:
        owner_user_id = action["actor_user_id"]
    if owner_user_id is not None and order.get("created_by") != owner_user_id:
        raise HTTPException(403, "SYSADMIN_ASSISTANT may delete only personally created records.")


@event.listens_for(Engine, "commit")
def audit_assistant_transaction(conn) -> None:
    """The actor's audit is committed atomically with each business transaction.

    A request can have several transactions. This event describes a committed
    transaction, not success of a later transaction or of the entire request.
    """
    action = _action.get()
    if action and conn.dialect.name == "postgresql":
        conn.execute(text("""INSERT INTO public.audit_log
            (actor_user_id,entity,entity_id,action,before_data,after_data)
            VALUES (:actor,'sysadmin_assistant_operations',:actor,
                'ASSISTANT_BUSINESS_TRANSACTION',NULL,CAST(:metadata AS jsonb))"""),
            {"actor": action["actor_user_id"], "metadata": json.dumps(
                {key: value for key, value in action.items() if key != "actor_user_id"})})
