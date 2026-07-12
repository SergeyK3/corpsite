"""Workspace freeze helpers after document promotion (OO-IMP-003B)."""
from __future__ import annotations

from typing import Any

from app.db.models.operational_orders import WORKSPACE_STAGE_DOCUMENT_PROMOTED
from app.operational_orders.errors import OperationalOrderWorkspaceFrozenError


def is_workspace_frozen(workspace: dict[str, Any]) -> bool:
    return str(workspace.get("stage")) == WORKSPACE_STAGE_DOCUMENT_PROMOTED


def assert_workspace_not_frozen(workspace: dict[str, Any]) -> None:
    if is_workspace_frozen(workspace):
        raise OperationalOrderWorkspaceFrozenError(
            "Workspace is frozen after promotion and cannot be modified."
        )
