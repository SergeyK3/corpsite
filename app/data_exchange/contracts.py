"""Small, explicit contracts shared by registered exchange scenarios."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol


PackageStatus = Literal[
    "UPLOADED", "VALIDATING", "PREVIEW_READY", "BLOCKED", "DRY_RUN_PASSED",
    "AWAITING_CONFIRMATION", "APPLYING", "APPLIED", "FAILED", "CANCELLED",
]
RowGroup = Literal[
    "CREATE", "UPDATE", "UNCHANGED", "NOT_FOUND", "AMBIGUOUS", "ERROR", "POSSIBLE_DUPLICATE",
]

PACKAGE_STATUSES: frozenset[str] = frozenset({
    "UPLOADED", "VALIDATING", "PREVIEW_READY", "BLOCKED", "DRY_RUN_PASSED",
    "AWAITING_CONFIRMATION", "APPLYING", "APPLIED", "FAILED", "CANCELLED",
})
ROW_GROUPS: frozenset[str] = frozenset({
    "CREATE", "UPDATE", "UNCHANGED", "NOT_FOUND", "AMBIGUOUS", "ERROR", "POSSIBLE_DUPLICATE",
})


@dataclass(frozen=True)
class PreviewRow:
    source_row_number: int
    source_keys: dict[str, Any]
    target_ref: dict[str, Any] | None
    result_group: RowGroup
    proposed_action: str
    reason_code: str | None = None
    message: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class ScenarioResult:
    rows: list[PreviewRow]
    target_fingerprint: str
    warnings: list[str]


class Scenario(Protocol):
    code: str
    schema_version: str
    label: str
    accepted_suffixes: tuple[str, ...]
    max_bytes: int
    atomic_apply: bool
    upload_permission: str
    dry_run_permission: str
    apply_permission: str
    export_permission: str | None

    def validate_and_preview(self, conn: Any, content: bytes, *, scope_unit_ids: set[int] | None) -> ScenarioResult: ...
    def apply(self, conn: Any, *, package_id: int, rows: list[PreviewRow], actor_user_id: int) -> dict[str, int]: ...


ScenarioFactory = Callable[[], Scenario]
