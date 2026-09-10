"""Focused fail-closed contracts for the Stage-3 training router."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api import ppr_stage3_training_router as router
from app.services import ppr_stage3_training_service as service


class _Result:
    def __init__(self, rows=None, scalar=None):
        self.rows = rows or []
        self.scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar_one_or_none(self):
        return self.scalar


class _Connection:
    def execute(self, *_args, **_kwargs):
        return _Result(rows=[10])


def test_stage3_scope_is_fail_closed_when_scope_cannot_be_resolved():
    with pytest.raises(HTTPException) as exc:
        router._scope_cohort(_Connection(), 1, {})
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "STAGE3_SCOPE_UNRESOLVED"


def test_stage3_output_redacts_certificate_for_every_response_shape(monkeypatch):
    monkeypatch.setattr(service, "can_view_training_certificate_details", lambda _: False)
    monkeypatch.setattr(router, "organization_timezone", lambda: ("UTC", None))
    result = router._out({"proposal": {"certificate_number": "hidden"}, "current": {"certificate_number": "hidden"}}, {})
    assert "certificate_number" not in str(result)


@pytest.mark.parametrize(
    ("checker", "code"),
    [
        (router._require_preview_enabled, "STAGE3_PREVIEW_DISABLED"),
        (router._require_execution_enabled, "STAGE3_EXECUTION_DISABLED"),
        (router._require_accept_enabled, "STAGE3_ACCEPT_DISABLED"),
    ],
)
def test_stage3_route_feature_gates_fail_closed(monkeypatch, checker, code):
    monkeypatch.setattr(service, "ppr_stage3_training_preview_enabled", lambda: False)
    monkeypatch.setattr(service, "ppr_stage3_training_execution_enabled", lambda: False)
    monkeypatch.setattr(service, "ppr_stage3_training_accept_enabled", lambda: False)
    with pytest.raises(service.Stage3ValidationError) as exc:
        checker()
    assert str(exc.value) == code


def test_stage3_permission_is_checked_before_scope(monkeypatch):
    monkeypatch.setattr(router, "require_ppr_stage3_training_manage", lambda _: (_ for _ in ()).throw(HTTPException(403, detail={"code": "denied"})))
    with pytest.raises(HTTPException) as exc:
        router._actor({"user_id": 1})
    assert exc.value.status_code == 403
