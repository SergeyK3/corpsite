"""Isolated checks for the admin-only deleted-order tombstone contract."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.directory import personnel_orders_routes as routes


def test_tombstone_access_requires_system_admin_and_cleanup_permission(monkeypatch) -> None:
    monkeypatch.setattr(routes, "has_technical_personnel_order_cleanup_permission", lambda _user_id: True)
    routes._require_deleted_order_tombstone_access_or_403({"user_id": 1, "is_system_admin": True, "has_sysadmin_api": True})
    with pytest.raises(HTTPException) as denied:
        routes._require_deleted_order_tombstone_access_or_403({"user_id": 1, "is_system_admin": False, "has_sysadmin_api": True})
    assert denied.value.status_code == 403
    monkeypatch.setattr(routes, "has_technical_personnel_order_cleanup_permission", lambda _user_id: False)
    with pytest.raises(HTTPException) as denied_without_grant:
        routes._require_deleted_order_tombstone_access_or_403({"user_id": 1, "is_system_admin": True, "has_sysadmin_api": True})
    assert denied_without_grant.value.status_code == 403
