"""Fork Version — new MRD version within the same report_period (WP-MRD-003)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.mrd.application.fork_idempotency import begin_idempotent_command, build_request_fingerprint
from app.mrd.domain.errors import (
    MrdNotFoundError,
    MrdOptimisticConcurrencyConflictError,
)
from app.mrd.domain.fork_models import ForkVersionCommand, ForkVersionResult
from app.mrd.domain.types import (
    MRD_COMMAND_FORK_VERSION,
    REFERENCE_EVENT_ACTIVATE,
    REFERENCE_EVENT_CLOSE,
    REFERENCE_EVENT_CREATE,
)
from app.mrd.infrastructure.command_idempotency_repository import SqlAlchemyMrdCommandIdempotencyRepository
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository, utcnow


def _result_from_payload(payload: dict, *, command_id: str, idempotent_replay: bool) -> ForkVersionResult:
    return ForkVersionResult(
        command_id=command_id,
        source_mrd_id=int(payload["source_mrd_id"]),
        target_mrd_id=int(payload["target_mrd_id"]),
        target_report_period=datetime.fromisoformat(str(payload["target_report_period"])).date(),
        target_version=int(payload["target_version"]),
        closed_mrd_id=int(payload["closed_mrd_id"]) if payload.get("closed_mrd_id") is not None else None,
        copied_entry_count=int(payload["copied_entry_count"]),
        version_event_ids=tuple(int(v) for v in payload["version_event_ids"]),
        idempotent_replay=idempotent_replay,
    )


class ForkVersionService:
    """Create vN+1 in the same period from an explicit source version."""

    def __init__(
        self,
        repo: SqlAlchemyMrdRepository,
        idempotency: SqlAlchemyMrdCommandIdempotencyRepository,
    ) -> None:
        self._repo = repo
        self._idempotency = idempotency

    def fork_version(self, command: ForkVersionCommand) -> ForkVersionResult:
        fingerprint = build_request_fingerprint(
            {
                "command_type": MRD_COMMAND_FORK_VERSION,
                "source_mrd_id": command.source_mrd_id,
                "performed_by": command.performed_by,
                "notes": command.notes,
            }
        )
        replay = begin_idempotent_command(
            self._idempotency,
            command_id=command.command_id,
            command_type=MRD_COMMAND_FORK_VERSION,
            performed_by=command.performed_by,
            request_fingerprint=fingerprint,
        )
        if replay is not None:
            return _result_from_payload(replay.result_payload, command_id=command.command_id, idempotent_replay=True)

        performed_at = utcnow()
        try:
            source = self._repo.load_mrd(command.source_mrd_id)
            if source is None:
                raise MrdNotFoundError(f"source_mrd_id={command.source_mrd_id} not found")

            report_period = source.report_period
            next_version = self._repo.max_version_for_period(report_period) + 1

            locked_active = self._repo.lock_active_mrd_for_period(report_period)
            closed_mrd_id: int | None = None
            event_ids: list[int] = []

            if locked_active is not None:
                expected = command.expected_active_row_version
                if expected is not None and locked_active.row_version != expected:
                    raise MrdOptimisticConcurrencyConflictError(
                        "Stale ACTIVE MRD row_version for fork-version"
                    )
                self._repo.close_mrd(
                    locked_active.mrd_id,
                    closed_by=command.performed_by,
                    expected_row_version=locked_active.row_version,
                    closed_at=performed_at,
                )
                closed_mrd_id = locked_active.mrd_id
                event_ids.append(
                    self._repo.insert_version_event(
                        event_type=REFERENCE_EVENT_CLOSE,
                        report_period=report_period,
                        mrd_id=locked_active.mrd_id,
                        performed_by=command.performed_by,
                        source_mrd_id=command.source_mrd_id,
                        performed_at=performed_at,
                        event_context={
                            "command_id": command.command_id,
                            "fork_kind": MRD_COMMAND_FORK_VERSION,
                        },
                    )
                )

            source_entries = self._repo.load_mrd_entries(command.source_mrd_id)
            target = self._repo.create_mrd_version(
                report_period=report_period,
                version=next_version,
                created_by=command.performed_by,
                forked_from_reference_id=command.source_mrd_id,
                entry_count=len(source_entries),
                notes=command.notes,
            )

            copied = self._repo.copy_confirmed_entries(
                source_mrd_id=command.source_mrd_id,
                target_mrd_id=target.mrd_id,
            )

            event_context = {
                "command_id": command.command_id,
                "source_mrd_id": command.source_mrd_id,
                "source_version": source.version,
                "target_version": target.version,
                "closed_mrd_id": closed_mrd_id,
            }
            event_ids.append(
                self._repo.insert_version_event(
                    event_type=REFERENCE_EVENT_CREATE,
                    report_period=report_period,
                    mrd_id=target.mrd_id,
                    performed_by=command.performed_by,
                    source_mrd_id=command.source_mrd_id,
                    performed_at=performed_at,
                    event_context=event_context,
                )
            )
            event_ids.append(
                self._repo.insert_version_event(
                    event_type=REFERENCE_EVENT_ACTIVATE,
                    report_period=report_period,
                    mrd_id=target.mrd_id,
                    performed_by=command.performed_by,
                    source_mrd_id=command.source_mrd_id,
                    performed_at=performed_at,
                    event_context=event_context,
                )
            )

            result_payload = {
                "source_mrd_id": command.source_mrd_id,
                "target_mrd_id": target.mrd_id,
                "target_report_period": report_period.isoformat(),
                "target_version": target.version,
                "closed_mrd_id": closed_mrd_id,
                "copied_entry_count": copied,
                "version_event_ids": event_ids,
            }
            self._idempotency.complete_execution(command.command_id, result_payload=result_payload)
            return ForkVersionResult(
                command_id=command.command_id,
                source_mrd_id=command.source_mrd_id,
                target_mrd_id=target.mrd_id,
                target_report_period=report_period,
                target_version=target.version,
                closed_mrd_id=closed_mrd_id,
                copied_entry_count=copied,
                version_event_ids=tuple(event_ids),
                idempotent_replay=False,
            )
        except Exception:
            self._idempotency.delete_execution(command.command_id)
            raise
