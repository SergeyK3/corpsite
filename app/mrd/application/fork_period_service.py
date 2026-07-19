"""Fork Period — create v1 of a new report_period from any source version (WP-MRD-003)."""
from __future__ import annotations

from datetime import datetime

from app.mrd.application.fork_idempotency import begin_idempotent_command, build_request_fingerprint
from app.mrd.domain.errors import MrdNotFoundError, MrdPeriodExistsError
from app.mrd.domain.period_window import require_period_in_creation_window
from app.mrd.domain.fork_models import ForkPeriodCommand, ForkPeriodResult
from app.mrd.domain.types import (
    MRD_COMMAND_FORK_PERIOD,
    REFERENCE_EVENT_ACTIVATE,
    REFERENCE_EVENT_CREATE,
    REFERENCE_EVENT_FORK_PERIOD,
)
from app.mrd.infrastructure.command_idempotency_repository import SqlAlchemyMrdCommandIdempotencyRepository
from app.mrd.infrastructure.repository import SqlAlchemyMrdRepository, utcnow


def _result_from_payload(payload: dict, *, command_id: str, idempotent_replay: bool) -> ForkPeriodResult:
    return ForkPeriodResult(
        command_id=command_id,
        source_mrd_id=int(payload["source_mrd_id"]),
        target_mrd_id=int(payload["target_mrd_id"]),
        target_report_period=datetime.fromisoformat(str(payload["target_report_period"])).date(),
        target_version=int(payload["target_version"]),
        copied_entry_count=int(payload["copied_entry_count"]),
        version_event_ids=tuple(int(v) for v in payload["version_event_ids"]),
        idempotent_replay=idempotent_replay,
    )


class ForkPeriodService:
    """Bootstrap ACTIVE v1 for a new report_period from an explicit source MRD."""

    def __init__(
        self,
        repo: SqlAlchemyMrdRepository,
        idempotency: SqlAlchemyMrdCommandIdempotencyRepository,
    ) -> None:
        self._repo = repo
        self._idempotency = idempotency

    def fork_period(self, command: ForkPeriodCommand) -> ForkPeriodResult:
        fingerprint = build_request_fingerprint(
            {
                "command_type": MRD_COMMAND_FORK_PERIOD,
                "source_mrd_id": command.source_mrd_id,
                "target_report_period": command.target_report_period.isoformat(),
                "performed_by": command.performed_by,
                "notes": command.notes,
            }
        )
        replay = begin_idempotent_command(
            self._idempotency,
            command_id=command.command_id,
            command_type=MRD_COMMAND_FORK_PERIOD,
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

            require_period_in_creation_window(command.target_report_period)

            if self._repo.period_has_mrd(command.target_report_period):
                raise MrdPeriodExistsError(
                    f"report_period={command.target_report_period.isoformat()} already has an MRD"
                )

            source_entries = self._repo.load_mrd_entries(command.source_mrd_id)
            target = self._repo.create_mrd_version(
                report_period=command.target_report_period,
                version=1,
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
                "source_report_period": source.report_period.isoformat(),
                "source_version": source.version,
                "target_version": target.version,
            }
            event_ids = [
                self._repo.insert_version_event(
                    event_type=REFERENCE_EVENT_CREATE,
                    report_period=command.target_report_period,
                    mrd_id=target.mrd_id,
                    performed_by=command.performed_by,
                    source_mrd_id=command.source_mrd_id,
                    performed_at=performed_at,
                    event_context=event_context,
                ),
                self._repo.insert_version_event(
                    event_type=REFERENCE_EVENT_FORK_PERIOD,
                    report_period=command.target_report_period,
                    mrd_id=target.mrd_id,
                    performed_by=command.performed_by,
                    source_mrd_id=command.source_mrd_id,
                    performed_at=performed_at,
                    event_context=event_context,
                ),
                self._repo.insert_version_event(
                    event_type=REFERENCE_EVENT_ACTIVATE,
                    report_period=command.target_report_period,
                    mrd_id=target.mrd_id,
                    performed_by=command.performed_by,
                    source_mrd_id=command.source_mrd_id,
                    performed_at=performed_at,
                    event_context=event_context,
                ),
            ]

            result_payload = {
                "source_mrd_id": command.source_mrd_id,
                "target_mrd_id": target.mrd_id,
                "target_report_period": command.target_report_period.isoformat(),
                "target_version": target.version,
                "copied_entry_count": copied,
                "version_event_ids": event_ids,
            }
            self._idempotency.complete_execution(command.command_id, result_payload=result_payload)
            return ForkPeriodResult(
                command_id=command.command_id,
                source_mrd_id=command.source_mrd_id,
                target_mrd_id=target.mrd_id,
                target_report_period=command.target_report_period,
                target_version=target.version,
                copied_entry_count=copied,
                version_event_ids=tuple(event_ids),
                idempotent_replay=False,
            )
        except Exception:
            self._idempotency.delete_execution(command.command_id)
            raise
