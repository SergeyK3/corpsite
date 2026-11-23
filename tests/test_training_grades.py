import pytest
from fastapi import HTTPException

from app.api.training_router import OrganizerDecision, _grade_decision, _guard
from app.db.engine import engine


def test_training_grade_priority() -> None:
    def result(**values):
        corrected = bool(values.pop("corrected", False))
        decision = OrganizerDecision(explanation="Проверены подтверждения", **values)
        return _grade_decision(decision, had_evidence_correction=corrected)

    assert result(evidence_valid=True) == (5, "passed")
    assert result(evidence_valid=True, corrected=True) == (4, "passed")
    assert result(evidence_valid=True, hint_or_action_correction=True) == (3, "passed")
    assert result(evidence_valid=False) == (2, "failed")
    assert result(evidence_valid=False, established_substitution=True) == (1, "failed")


def test_training_writes_refuse_production_flag(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TRAINING_MODE", "1")
    monkeypatch.setenv("TRAINING_DISABLE_EXTERNAL", "1")
    with engine.connect() as conn, pytest.raises(HTTPException) as blocked:
        _guard(conn, write=True)
    assert blocked.value.status_code == 503
