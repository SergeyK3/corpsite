# tests/test_qm_team_scope.py
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.tasks_fsm import _resolve_qm_head_fallback_role_id
from app.services.tasks_service import (
    QM_HEAD_TEAM_EXECUTOR_ROLE_CODES,
    _task_matches_team_scope,
    get_team_scope_context,
)


def test_qm_head_fallback_uses_role_codes_not_hardcoded_ids():
    conn = MagicMock()

    def execute_side_effect(stmt, params=None):
        sql = str(stmt)
        m = MagicMock()
        if "WHERE role_id = :rid" in sql:
            m.mappings.return_value.first.return_value = {"code": "QM_HOSP"}
        elif "WHERE code = :code" in sql and params.get("code") == "QM_HEAD":
            m.mappings.return_value.first.return_value = {"role_id": 42}
        else:
            m.mappings.return_value.first.return_value = None
        return m

    conn.execute.side_effect = execute_side_effect

    assert _resolve_qm_head_fallback_role_id(conn, actor_role_id=11) == 42


def test_qm_head_team_scope_includes_qm_expert_roles():
    conn = MagicMock()
    calls = {"n": 0}

    def execute_side_effect(stmt, params=None):
        calls["n"] += 1
        sql = str(stmt)
        m = MagicMock()
        if "FROM public.users u" in sql and "WHERE u.user_id" in sql:
            m.mappings.return_value.first.return_value = {
                "user_id": 1,
                "role_id": 10,
                "unit_id": 44,
                "full_name": "Head",
                "login": "qm_head@corp.local",
                "is_active": True,
            }
        elif "FROM public.roles" in sql and "WHERE role_id = :rid" in sql:
            m.mappings.return_value.first.return_value = {
                "role_id": 10,
                "code": "QM_HEAD",
                "name": "Руководитель ОВЭиПД",
            }
        elif "POSTCOMPILE_role_codes" in sql or "r.code IN" in sql:
            m.mappings.return_value.all.return_value = [
                {"role_id": 11},
                {"role_id": 12},
            ]
        else:
            m.mappings.return_value.first.return_value = None
            m.mappings.return_value.all.return_value = []
        return m

    conn.execute.side_effect = execute_side_effect

    ctx = get_team_scope_context(conn, current_user_id=1, current_role_id=10)
    assert ctx["scope_mode"] == "qm_head"
    assert ctx["team_executor_role_ids"] == [11, 12]


def test_task_matches_team_scope_qm_head_accepts_qm_expert_role(monkeypatch):
    conn = MagicMock()

    monkeypatch.setattr(
        "app.services.tasks_service.can_view_team_tasks",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "app.services.tasks_service.load_role_meta",
        lambda conn, *, role_id: {"role_id": int(role_id), "code": "QM_HEAD", "name": "Head"},
    )
    monkeypatch.setattr(
        "app.services.tasks_service.get_team_scope_context",
        lambda conn, *, current_user_id, current_role_id: {
            "scope_mode": "qm_head",
            "team_executor_role_ids": [11, 12],
            "current_unit_id": 44,
            "team_user_ids": [],
        },
    )

    assert _task_matches_team_scope(
        conn,
        current_user_id=1,
        current_role_id=10,
        task_row={"executor_role_id": 11},
    )


def test_task_matches_team_scope_qm_head_rejects_unrelated_role(monkeypatch):
    conn = MagicMock()

    monkeypatch.setattr(
        "app.services.tasks_service.can_view_team_tasks",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "app.services.tasks_service.load_role_meta",
        lambda conn, *, role_id: {"role_id": int(role_id), "code": "QM_HEAD", "name": "Head"},
    )
    monkeypatch.setattr(
        "app.services.tasks_service.get_team_scope_context",
        lambda conn, *, current_user_id, current_role_id: {
            "scope_mode": "qm_head",
            "team_executor_role_ids": [11, 12],
            "current_unit_id": 44,
            "team_user_ids": [],
        },
    )

    assert not _task_matches_team_scope(
        conn,
        current_user_id=1,
        current_role_id=10,
        task_row={"executor_role_id": 99},
    )


def test_qm_head_team_scope_allowlist_excludes_training_expert():
    assert "QM_TRAINING_EXPERT" not in QM_HEAD_TEAM_EXECUTOR_ROLE_CODES


def test_qm_head_team_scope_query_uses_explicit_allowlist_not_training_expert():
    conn = MagicMock()
    captured: dict = {}

    def execute_side_effect(stmt, params=None):
        sql = str(stmt)
        m = MagicMock()
        if "FROM public.users u" in sql and "WHERE u.user_id" in sql:
            m.mappings.return_value.first.return_value = {
                "user_id": 1,
                "role_id": 10,
                "unit_id": 44,
                "full_name": "Head",
                "login": "qm_head@corp.local",
                "is_active": True,
            }
        elif "FROM public.roles" in sql and "WHERE role_id = :rid" in sql:
            m.mappings.return_value.first.return_value = {
                "role_id": 10,
                "code": "QM_HEAD",
                "name": "Руководитель ОВЭиПД",
            }
        elif "POSTCOMPILE_role_codes" in sql or "r.code IN" in sql:
            captured["role_codes"] = list((params or {}).get("role_codes") or [])
            m.mappings.return_value.all.return_value = [
                {"role_id": 4},
                {"role_id": 5},
                {"role_id": 6},
                {"role_id": 7},
            ]
        else:
            m.mappings.return_value.first.return_value = None
            m.mappings.return_value.all.return_value = []
        return m

    conn.execute.side_effect = execute_side_effect

    ctx = get_team_scope_context(conn, current_user_id=1, current_role_id=10)
    assert ctx["scope_mode"] == "qm_head"
    assert captured["role_codes"] == list(QM_HEAD_TEAM_EXECUTOR_ROLE_CODES)
    assert "QM_TRAINING_EXPERT" not in captured["role_codes"]
    assert ctx["team_executor_role_ids"] == [4, 5, 6, 7]
