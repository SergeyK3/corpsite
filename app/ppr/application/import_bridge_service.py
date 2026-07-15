"""PMF → PPR application bridge (R5 — transitional, default OFF)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.ppr.application.authorization import AuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ADD_EDUCATION,
    COMMAND_TYPE_ADD_TRAINING,
    COMMAND_TYPE_SUPERSEDE_EDUCATION,
    COMMAND_TYPE_SUPERSEDE_TRAINING,
    COMMAND_TYPE_VOID_EDUCATION,
    COMMAND_TYPE_VOID_TRAINING,
    PprCommandEnvelope,
)
from app.ppr.application.config import ppr_pmf_bridge_enabled
from app.ppr.application.pmf_command_id import (
    build_pmf_commit_command_id,
    build_pmf_supersede_command_id,
    build_pmf_void_command_id,
)
from app.ppr.application.results import PprApplicationResult
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.errors import PprPmfBridgeError, PprPmfCommandMappingError
from app.services.personnel_migration_types import DraftItemContext, RunContext, WrittenRecord


class PprImportBridgeApplicationService:
    """Delegates PMF section mutations to PPR Application Layer when bridge enabled."""

    def __init__(
        self,
        *,
        section_service: PprSectionApplicationService,
        authorization: AuthorizationPort,
    ) -> None:
        self._section_service = section_service
        self._authorization = authorization

    @staticmethod
    def is_enabled() -> bool:
        return ppr_pmf_bridge_enabled()

    def write_pmf_item_via_ppr(
        self,
        *,
        run: RunContext,
        item: DraftItemContext,
        actor_id: str,
        written: WrittenRecord,
    ) -> PprApplicationResult:
        if not self.is_enabled():
            raise PprPmfBridgeError("PPR PMF bridge is disabled")
        envelope = self._commit_envelope(run=run, item=item, actor_id=actor_id)
        payload = self._map_commit_payload(item)
        if item.record_kind == "education":
            envelope = PprCommandEnvelope(
                command_id=envelope.command_id,
                command_type=COMMAND_TYPE_ADD_EDUCATION,
                actor_id=actor_id,
                requested_at=envelope.requested_at,
                payload=payload,
                person_id=run.person_id,
                employee_id=run.employee_context_id,
                employee_context_id=run.employee_context_id,
                correlation_id=f"pmf-run-{run.run_id}",
            )
            return self._section_service.add_education(envelope)
        if item.record_kind == "training":
            envelope = PprCommandEnvelope(
                command_id=envelope.command_id,
                command_type=COMMAND_TYPE_ADD_TRAINING,
                actor_id=actor_id,
                requested_at=envelope.requested_at,
                payload=payload,
                person_id=run.person_id,
                employee_id=run.employee_context_id,
                employee_context_id=run.employee_context_id,
                correlation_id=f"pmf-run-{run.run_id}",
            )
            return self._section_service.add_training(envelope)
        raise PprPmfCommandMappingError(f"Unsupported PMF record_kind: {item.record_kind!r}")

    def void_pmf_record_via_ppr(
        self,
        *,
        run: RunContext,
        item: DraftItemContext,
        actor_id: str,
        target_record_id: int,
        expected_updated_at,
        reason: str,
    ) -> PprApplicationResult:
        if not self.is_enabled():
            raise PprPmfBridgeError("PPR PMF bridge is disabled")
        command_id = build_pmf_void_command_id(
            migration_run_id=run.run_id,
            migration_item_id=item.item_id,
        )
        base = self._base_envelope(
            command_id=command_id,
            command_type=COMMAND_TYPE_VOID_EDUCATION,
            actor_id=actor_id,
            run=run,
        )
        payload = {
            "record_id": target_record_id,
            "reason": reason,
            "expected_updated_at": expected_updated_at,
        }
        if item.record_kind == "education":
            return self._section_service.void_education(
                PprCommandEnvelope(**{**base, "command_type": COMMAND_TYPE_VOID_EDUCATION, "payload": payload})
            )
        if item.record_kind == "training":
            return self._section_service.void_training(
                PprCommandEnvelope(**{**base, "command_type": COMMAND_TYPE_VOID_TRAINING, "payload": payload})
            )
        raise PprPmfCommandMappingError(f"Unsupported PMF record_kind: {item.record_kind!r}")

    @staticmethod
    def _commit_envelope(*, run: RunContext, item: DraftItemContext, actor_id: str) -> PprCommandEnvelope:
        command_id = build_pmf_commit_command_id(
            migration_run_id=run.run_id,
            migration_item_id=item.item_id,
        )
        return PprCommandEnvelope(
            command_id=command_id,
            command_type=COMMAND_TYPE_ADD_EDUCATION,
            actor_id=actor_id,
            requested_at=datetime.now(UTC),
            payload={},
            person_id=run.person_id,
            employee_id=run.employee_context_id,
            employee_context_id=run.employee_context_id,
            correlation_id=f"pmf-run-{run.run_id}",
        )

    @staticmethod
    def _base_envelope(*, command_id: str, command_type: str, actor_id: str, run: RunContext) -> dict[str, Any]:
        return {
            "command_id": command_id,
            "command_type": command_type,
            "actor_id": actor_id,
            "requested_at": datetime.now(UTC),
            "person_id": run.person_id,
            "employee_id": run.employee_context_id,
            "employee_context_id": run.employee_context_id,
            "correlation_id": f"pmf-run-{run.run_id}",
        }

    @staticmethod
    def _map_commit_payload(item: DraftItemContext) -> dict[str, Any]:
        draft = dict(item.draft_payload or {})
        if item.record_kind == "education":
            return {
                "education_kind": draft.get("education_kind"),
                "institution_type": draft.get("institution_type"),
                "institution_name": draft.get("institution_name"),
                "specialty": draft.get("specialty"),
                "qualification": draft.get("qualification"),
                "started_at": draft.get("started_at"),
                "completed_at": draft.get("completed_at"),
                "diploma_number": draft.get("diploma_number"),
                "document_date": draft.get("document_date"),
                "metadata": draft.get("metadata"),
                "employee_context_id": draft.get("employee_context_id"),
            }
        if item.record_kind == "training":
            return {
                "training_kind": draft.get("training_kind"),
                "title": draft.get("title"),
                "organization_name": draft.get("organization_name"),
                "hours": draft.get("hours"),
                "started_at": draft.get("started_at"),
                "completed_at": draft.get("completed_at"),
                "certificate_number": draft.get("certificate_number"),
                "document_date": draft.get("document_date"),
                "metadata": draft.get("metadata"),
                "employee_context_id": draft.get("employee_context_id"),
            }
        raise PprPmfCommandMappingError(f"Unsupported PMF record_kind: {item.record_kind!r}")
