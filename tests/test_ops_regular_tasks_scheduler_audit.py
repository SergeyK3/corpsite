from __future__ import annotations

from scripts.ops.ops_regular_tasks_scheduler_audit import validate_scheduler_status_payload


def _valid_payload() -> dict:
    return {
        "automatic_enabled": True,
        "status": "healthy",
        "status_label": "OK",
        "status_explanation": "Automatic runs observed.",
        "observation_window_days": 8,
        "last_result_label": "2026-07-01",
        "hint": "none",
        "checked_at": "2026-07-02T12:00:00+05:00",
    }


def test_validate_scheduler_status_payload_accepts_minimal_contract():
    assert validate_scheduler_status_payload(_valid_payload()) is None


def test_validate_scheduler_status_payload_rejects_missing_keys():
    payload = _valid_payload()
    del payload["status"]
    err = validate_scheduler_status_payload(payload)
    assert err is not None
    assert "status" in err


def test_validate_scheduler_status_payload_rejects_empty_status():
    payload = _valid_payload()
    payload["status"] = "   "
    assert validate_scheduler_status_payload(payload) == "status must be a non-empty string"
