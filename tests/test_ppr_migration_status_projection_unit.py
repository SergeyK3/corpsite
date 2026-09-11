from datetime import datetime, timezone
from app.services import ppr_migration_status_projection_service as service

FACT = {"stage0_cohort_run_id": 1, "stage0_participant_id": 2, "person_id": 3, "employee_id": 4,
        "source_row_id": 5, "employee_person_id": 3, "is_active": True, "operational_status": "active",
        "person_status": "active", "merged_into_person_id": None,
        "person_updated_at": datetime(2025,1,1,tzinfo=timezone.utc), "employee_updated_at": datetime(2025,1,1,tzinfo=timezone.utc), "source_payload": {}}

def _candidate(**overrides):
    base={"run_id": 9,"participant_id":10,"run_status":"ACCEPTED","participant_status":"COMPLETED",
          "source_fingerprint":"a"*64,"completed_at":datetime(2025,1,2,tzinfo=timezone.utc),"accepted_at":datetime(2025,1,3,tzinfo=timezone.utc),"policy_version":"v1","pmf_run_id":11}
    return {**base,**overrides}

def test_status_tree_accepts_participant_evidence_and_ignores_cancelled_by_contract(monkeypatch):
    monkeypatch.setattr(service,"_candidate",lambda *_a,**_k:_candidate())
    assert service._status(None, FACT, "education")["status_code"] == "ACCEPTED"

def test_status_tree_never_accepts_empty_general_without_evidence(monkeypatch):
    monkeypatch.setattr(service,"_candidate",lambda *_a,**_k:_candidate(pmf_run_id=None,accepted_at=None))
    assert service._status(None, FACT, "general")["status_code"] == "AUTO_READY"

def test_status_tree_prioritizes_blocked_and_stale(monkeypatch):
    monkeypatch.setattr(service,"_candidate",lambda *_a,**_k:_candidate())
    assert service._status(None,{**FACT,"is_active":False},"training")["status_code"] == "BLOCKED"
    changed={**FACT,"person_updated_at":datetime(2025,2,1,tzinfo=timezone.utc)}
    assert service._status(None,changed,"training")["status_code"] == "STALE"

def test_universe_key_is_order_independent():
    assert service.universe_key(7,[9,8,9]) == service.universe_key(7,[8,9])
