"""WP-TD-002A: legacy personnel hard-delete is retired from the web process."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.main import app
from app.services.test_personnel_deletion_service import legacy_hard_delete_enabled


@pytest.mark.parametrize(
    ("app_env", "allow", "database_url"),
    [
        (None, None, None),
        ("production", "true", "postgresql://ignored@127.0.0.1/prod"),
        ("prd", "true", "postgresql://ignored@localhost/prod"),
        ("dev", "true", "postgresql://ignored@127.0.0.1/prod"),
        ("unexpected", "yes", "postgresql://ignored@[::1]/prod"),
    ],
)
def test_web_hard_delete_is_not_configurable(client, monkeypatch, app_env, allow, database_url):
    for name, value in {
        "APP_ENV": app_env,
        "ALLOW_LEGACY_PERSONNEL_HARD_DELETE": allow,
        "DATABASE_URL": database_url,
    }.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    assert legacy_hard_delete_enabled() is False
    with engine.connect() as conn:
        actor = conn.execute(text("SELECT user_id,role_id FROM users ORDER BY user_id LIMIT 1")).mappings().one()
        employee_id = conn.execute(text("SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1")).scalar_one_or_none()
    app.dependency_overrides[get_current_user] = lambda: dict(actor)
    employee_id = int(employee_id or 1)
    single = client.delete(
        f"/directory/employees/{employee_id}",
        headers={"X-Allow-Hard-Delete": "true"},
        params={"allow_hard_delete": "true"},
    )
    bulk = client.post(
        "/directory/employees/bulk-delete?allow_hard_delete=true",
        json={"employee_ids": [employee_id]},
        headers={"X-Allow-Hard-Delete": "true"},
    )
    assert single.status_code == bulk.status_code == 410
    assert single.json()["detail"]["code"] == "TD_LEGACY_HARD_DELETE_DISABLED"
    assert bulk.json()["detail"]["code"] == "TD_LEGACY_HARD_DELETE_DISABLED"
