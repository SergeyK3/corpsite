"""Deterministic ApplyPlan snapshot and fingerprint (WP-CL-012)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.control_list_import.domain.review_models import ApplyAction, ApplyPlan, ReviewDecision


def build_plan_key(*, import_run_id: int | None, source_row_id: int | None, plan_fingerprint: str) -> str:
    return f"cl-plan:{import_run_id}:row:{source_row_id}:{plan_fingerprint[:32]}"


def serialize_apply_plan(plan: ApplyPlan, *, review_run_key: str) -> dict[str, Any]:
    """Canonical JSON-serializable snapshot without unstable runtime values."""
    return {
        "review_run_key": review_run_key,
        "import_run_id": plan.import_run_id,
        "source_row_id": plan.source_row_id,
        "decision": plan.decision.value,
        "is_executable": plan.is_executable,
        "blocking_reasons": list(plan.blocking_reasons),
        "actions": [_serialize_action(index, action) for index, action in enumerate(plan.actions)],
    }


def compute_plan_fingerprint(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_action_fingerprint(action: ApplyAction) -> str:
    payload = {
        "action_type": action.action_type.value,
        "target_aggregate": action.target_aggregate,
        "source_candidate_ref": action.source_candidate_ref,
        "preconditions": sorted(action.preconditions),
        "idempotency_key": action.idempotency_key,
        "is_ready": action.is_ready,
        "blocking_reason": action.blocking_reason,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def plan_snapshot_and_fingerprint(
    plan: ApplyPlan,
    *,
    review_run_key: str,
) -> tuple[dict[str, Any], str, str]:
    snapshot = serialize_apply_plan(plan, review_run_key=review_run_key)
    fingerprint = compute_plan_fingerprint(snapshot)
    plan_key = build_plan_key(
        import_run_id=plan.import_run_id,
        source_row_id=plan.source_row_id,
        plan_fingerprint=fingerprint,
    )
    return snapshot, fingerprint, plan_key


def _serialize_action(index: int, action: ApplyAction) -> dict[str, Any]:
    return {
        "action_index": index,
        "action_type": action.action_type.value,
        "target_aggregate": action.target_aggregate,
        "source_candidate_ref": action.source_candidate_ref,
        "preconditions": sorted(action.preconditions),
        "idempotency_key": action.idempotency_key,
        "action_fingerprint": compute_action_fingerprint(action),
        "is_ready": action.is_ready,
        "blocking_reason": action.blocking_reason,
    }


def validate_plan_fingerprint(plan: ApplyPlan, *, review_run_key: str, expected_fingerprint: str) -> None:
    _, fingerprint, _ = plan_snapshot_and_fingerprint(plan, review_run_key=review_run_key)
    if fingerprint != expected_fingerprint:
        raise ValueError("ApplyPlan fingerprint mismatch — fail closed")
