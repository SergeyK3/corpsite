"""Workspace fingerprint drift detection vs promotion snapshot (OO-IMP-003B)."""
from __future__ import annotations

from typing import Any, Sequence

from app.operational_orders.validation.promotion_validation import workspace_fingerprint


def detect_workspace_drift(
    *,
    workspace: dict[str, Any],
    blocks: Sequence[dict[str, Any]],
    reconciliations: Sequence[dict[str, Any]],
    promotion_workspace_fingerprint: str,
) -> dict[str, Any]:
    current_fp = workspace_fingerprint(
        workspace_version=int(workspace.get("version") or 0),
        blocks=blocks,
        reconciliations=reconciliations,
    )
    drift = str(current_fp) != str(promotion_workspace_fingerprint)
    return {
        "current_workspace_fingerprint": current_fp,
        "promotion_workspace_fingerprint": str(promotion_workspace_fingerprint),
        "workspace_drift_detected": drift,
        "revision_recommended": drift,
    }
