# tests/test_acl_regression.py
from __future__ import annotations

import pytest

from app.db.engine import engine

# Импортируем внутренние хелперы из conftest.
# Да, они с подчёркиванием — это осознанно: тест должен быть устойчивым к схеме БД.
from tests.conftest import (  # noqa: F401
    create_task,
    _create_role,
    _create_user,
    _create_unit,
    _detect_unit_table,
    _set_user_unit,
    _table_exists,
    _get_columns,
    _safe_delete,
    _safe_delete_many,
)


def test_executor_from_other_unit_cannot_see_task(client, seed):
    """
    REGRESSION (ACL):
    Пользователь из другого unit не должен видеть задачу (404),
    даже если роль/статус корректны.
    """
    if seed.get("unit_id") is None:
        pytest.skip("unit table not available; cannot assert unit-based ACL")

    # Создаём задачу в unit из seed
    task_id = create_task(
        period_id=seed["period_id"],
        title=seed["title"],
        initiator_user_id=seed["initiator_user_id"],
        executor_role_id=seed["executor_role_id"],
        assignment_scope=seed["assignment_scope"],
        status_code="WAITING_REPORT",
        unit_id=seed["unit_id"],
    )

    # Создаём другого пользователя в ДРУГОМ unit
    created_role_ids = []
    created_user_ids = []
    other_unit_id = None

    try:
        with engine.begin() as conn:
            # safety: если нет unit таблицы (теоретически), пропускаем
            if not _detect_unit_table(conn):
                pytest.skip("unit table not detected; cannot assert unit-based ACL")

            other_unit_id = _create_unit(conn, name="pytest_other_unit")
            if other_unit_id is None:
                pytest.skip("failed to create other unit; cannot assert unit-based ACL")

            other_role_id = _create_role(conn, name="pytest_other_role")
            created_role_ids.append(other_role_id)

            other_user_id = _create_user(conn, role_id=other_role_id, full_name="Pytest Other User")
            created_user_ids.append(other_user_id)

            _set_user_unit(conn, other_user_id, other_unit_id)

        # Проверка: чужой unit -> 404
        r = client.get(f"/tasks/{task_id}", headers={"X-User-Id": str(other_user_id)})
        assert r.status_code == 404, r.text

    finally:
        # удаляем созданные сущности (порядок: users -> roles -> unit)
        with engine.begin() as conn:
            if created_user_ids and _table_exists(conn, "users"):
                ucols = _get_columns(conn, "users")
                uid_col = "user_id" if "user_id" in ucols else "id"
                _safe_delete_many(conn, "users", uid_col, created_user_ids)

            if created_role_ids and _table_exists(conn, "roles"):
                rcols = _get_columns(conn, "roles")
                rid_col = "role_id" if "role_id" in rcols else "id"
                _safe_delete_many(conn, "roles", rid_col, created_role_ids)

            if other_unit_id is not None:
                ut = _detect_unit_table(conn)
                if ut:
                    ucols = _get_columns(conn, ut)
                    uid_col = "unit_id" if "unit_id" in ucols else ("org_unit_id" if "org_unit_id" in ucols else "id")
                    _safe_delete(conn, ut, f"{uid_col} = :id", {"id": other_unit_id})

        # задачу чистит ваш per-test teardown (через seed), но это не мешает;
        # оставляем как есть, чтобы не дублировать логику.
