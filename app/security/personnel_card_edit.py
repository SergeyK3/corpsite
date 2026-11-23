"""Authorization boundary for Person-rooted personnel-card corrections."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.security.admin_guard import evaluate_admin_access
from app.security.admin_permissions import PERSONNEL_CARD_EDIT, has_admin_permission


def has_personnel_card_edit(user_ctx: dict[str, Any]) -> bool:
    """Only the explicit administrative bypass or the dedicated grant may write."""
    if evaluate_admin_access(user_ctx):
        return True
    try:
        return has_admin_permission(int(user_ctx["user_id"]), PERSONNEL_CARD_EDIT)
    except (KeyError, TypeError, ValueError):
        return False


def require_personnel_card_edit_for_person(user_ctx: dict[str, Any], person_id: int) -> None:
    if not has_personnel_card_edit(user_ctx):
        raise HTTPException(status_code=403, detail="Permission required: PERSONNEL_CARD_EDIT")
    # The subject is exclusively the route parameter.  Visibility is still
    # evaluated for that resolved Person and cannot be supplied by the client.
    # Delayed to avoid the legacy directory package's import-time router cycle.
    from app.services.ppr_query_access_service import assert_ppr_read_allowed_for_person
    assert_ppr_read_allowed_for_person(user_ctx, int(person_id))
