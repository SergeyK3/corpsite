"""Focused RBAC contract for protected Stage 2 routes."""
from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any

import pytest
from fastapi import HTTPException

from app.api import ppr_stage2_education_router as router
from app.security.ppr_stage2_permissions import require_ppr_stage2_education_manage
from app.services import ppr_stage2_education_service as service


class _Result:
    def __init__(self, *, scalar: Any = None, rows: list[dict[str, Any]] | None = None) -> None:
        self.scalar = scalar
        self.rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self.scalar

    def scalar_one(self) -> Any:
        return self.scalar

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list[Any]:
        return self.rows

    def mappings(self) -> "_Result":
        return self

    def __iter__(self):
        return iter(self.rows)


class _Connection:
    def __init__(self, execute) -> None:
        self._execute = execute

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Result:
        return self._execute(str(statement), params or {})

    def execution_options(self, **_: Any) -> "_Connection":
        return self

    def begin(self) -> "_Context":
        return _Context(self)


class _Context(AbstractContextManager[_Connection]):
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def __enter__(self) -> _Connection:
        return self.connection

    def __exit__(self, *_: Any) -> bool:
        return False


class _Engine:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def connect(self) -> _Context:
        return _Context(self.connection)

    def begin(self) -> _Context:
        return _Context(self.connection)


def test_stage2_requires_hr_head_before_permission_lookup(monkeypatch):
    monkeypatch.setattr("app.security.ppr_stage2_permissions.has_admin_permission", lambda *_: True)
    with pytest.raises(HTTPException) as exc:
        require_ppr_stage2_education_manage({"user_id": 7, "role_code": "HR_MANAGER"})
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PPR_STAGE2_EDUCATION_PERMISSION_DENIED"


def test_stage2_requires_dedicated_permission(monkeypatch):
    monkeypatch.setattr("app.security.ppr_stage2_permissions.has_admin_permission", lambda *_: False)
    with pytest.raises(HTTPException) as exc:
        require_ppr_stage2_education_manage({"user_id": 7, "role_code": "HR_HEAD"})
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PPR_STAGE2_EDUCATION_PERMISSION_DENIED"


def test_stage2_allows_hr_head_with_dedicated_permission(monkeypatch):
    monkeypatch.setattr("app.security.ppr_stage2_permissions.has_admin_permission", lambda *_: True)
    assert require_ppr_stage2_education_manage({"user_id": 7, "role_code": "HR_HEAD"}) == 7


def test_scope_cohort_rejects_any_out_of_scope_participant_without_leaking_units() -> None:
    conn = _Connection(lambda *_: _Result(rows=[10, 900]))

    with pytest.raises(HTTPException) as exc:
        router._scope_cohort(conn, 55, {"privileged": False, "scope_unit_ids": [10]})

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "STAGE2_COHORT_OUT_OF_SCOPE"
    assert "900" not in exc.value.detail["message"]


def test_scope_cohort_allows_privileged_and_organization_wide_visibility_without_query() -> None:
    def unexpected_query(*_: Any) -> _Result:
        pytest.fail("organization-wide scope must not enumerate cohort units")

    conn = _Connection(unexpected_query)
    router._scope_cohort(conn, 55, {"privileged": True, "scope_unit_ids": []})
    router._scope_cohort(conn, 55, {"privileged": False, "scope_unit_ids": None})


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (service.Stage2NotFoundError("STAGE2_RUN_NOT_FOUND"), 404, "STAGE2_RUN_NOT_FOUND"),
        (service.Stage2ConflictError("STAGE2_INVALID_STATE"), 409, "STAGE2_INVALID_STATE"),
        (service.Stage2ValidationError("STAGE2_VALIDATION"), 409, "STAGE2_VALIDATION"),
    ],
)
def test_stage2_error_contract_preserves_status_and_machine_code(error, status, code) -> None:
    response = router._error(error)
    assert response.status_code == status
    assert response.detail["code"] == code


def test_execute_endpoint_maps_state_conflict_to_409_with_exact_code(monkeypatch) -> None:
    conn = _Connection(lambda *_: _Result())
    monkeypatch.setattr(router, "engine", _Engine(conn))
    monkeypatch.setattr(router, "_actor", lambda _: (7, {"privileged": True}))
    monkeypatch.setattr(router, "_scope_run", lambda *_: None)
    monkeypatch.setattr(
        router.service,
        "execute_next_stage2",
        lambda *_args, **_: (_ for _ in ()).throw(service.Stage2ConflictError("STAGE2_RUN_PAUSED")),
    )

    with pytest.raises(HTTPException) as exc:
        router.execute(44, user={})

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "STAGE2_RUN_PAUSED"


def test_acceptance_fault_is_redacted_and_paused_in_separate_uow(monkeypatch) -> None:
    conn = _Connection(lambda *_: _Result())
    paused: list[tuple[int, Exception]] = []
    monkeypatch.setattr(router, "engine", _Engine(conn))
    monkeypatch.setattr(router, "_actor", lambda _: (7, {"privileged": True}))
    monkeypatch.setattr(router, "_scope_run", lambda *_: None)
    monkeypatch.setattr(
        router.service,
        "accept_stage2",
        lambda *_args, **_: (_ for _ in ()).throw(RuntimeError("password=do-not-disclose")),
    )
    monkeypatch.setattr(
        router.service,
        "pause_acceptance_after_rollback",
        lambda _, *, run_id, exc: paused.append((run_id, exc)) or True,
    )

    with pytest.raises(HTTPException) as exc:
        router.accept(44, router.Stage2AcceptRequest(stage_run_id=44), user={})

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "STAGE2_ACCEPTANCE_PAUSED"
    assert "do-not-disclose" not in exc.value.detail["message"]
    assert paused and paused[0][0] == 44
    assert "do-not-disclose" not in service._safe_error(paused[0][1])[1]


def test_concurrent_preview_replay_uses_advisory_lock_and_reuses_single_run(monkeypatch) -> None:
    calls: list[str] = []
    created = False

    def execute(sql: str, _: dict[str, Any]) -> _Result:
        nonlocal created
        calls.append(sql)
        if "pg_advisory_xact_lock" in sql:
            return _Result()
        if "FROM public.ppr_stage_runs WHERE stage_code='education'" in sql:
            return _Result(scalar=71 if created else None)
        if "INSERT INTO public.ppr_stage_runs" in sql:
            created = True
            return _Result(scalar=71)
        if "ppr_stage0_cohort_participants" in sql:
            return _Result(rows=[])
        pytest.fail(f"unexpected SQL: {sql}")

    conn = _Connection(execute)
    monkeypatch.setattr(
        service,
        "compute_preview_stage2",
        lambda *_args, **_kwargs: {"preview_fingerprint": "fingerprint"},
    )
    monkeypatch.setattr(service, "_view_run", lambda _conn, run_id: {"run": {"stage_run_id": run_id}})

    first = service.persist_preview_stage2(
        conn, stage0_cohort_run_id=12, actor_user_id=7, expected_preview_fingerprint="fingerprint"
    )
    replay = service.persist_preview_stage2(
        conn, stage0_cohort_run_id=12, actor_user_id=8, expected_preview_fingerprint="fingerprint"
    )

    assert first["run"]["stage_run_id"] == replay["run"]["stage_run_id"] == 71
    assert sum("pg_advisory_xact_lock" in sql for sql in calls) == 2
    assert sum("INSERT INTO public.ppr_stage_runs" in sql for sql in calls) == 1
