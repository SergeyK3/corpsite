"""Post-commit hook contract (R5 — no Evaluation Engine)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.ppr.application.results import PprApplicationResult


@dataclass(frozen=True, slots=True)
class PostCommitAction:
    action_type: str
    person_id: int
    command_id: str


POST_COMMIT_REEVALUATION = "request_reevaluation"
POST_COMMIT_PROJECTION_INVALIDATE = "invalidate_projection"


class PostCommitHookRunner(Protocol):
    def run(self, actions: tuple[PostCommitAction, ...]) -> tuple[str, ...]:
        """Return warning messages; must not raise for normal failures."""
        ...


class NoOpPostCommitHookRunner:
    def run(self, actions: tuple[PostCommitAction, ...]) -> tuple[str, ...]:
        del actions
        return ()


class LoggingPostCommitHookRunner:
    """Records intent only — no background scheduling."""

    def __init__(self) -> None:
        self.last_actions: tuple[PostCommitAction, ...] = ()

    def run(self, actions: tuple[PostCommitAction, ...]) -> tuple[str, ...]:
        self.last_actions = actions
        return ()


def default_post_commit_actions(result: PprApplicationResult) -> tuple[PostCommitAction, ...]:
    if result.status not in {"committed", "idempotent_replay", "already_materialized", "no_op"}:
        return ()
    return (
        PostCommitAction(
            action_type=POST_COMMIT_REEVALUATION,
            person_id=result.resolved_person_id,
            command_id=result.command_id,
        ),
        PostCommitAction(
            action_type=POST_COMMIT_PROJECTION_INVALIDATE,
            person_id=result.resolved_person_id,
            command_id=result.command_id,
        ),
    )
