"""Shared write runtime (UDE-012).

Write orchestration and runtime aggregate — no persistence, no production wiring.
"""
from __future__ import annotations

from app.document_engine.write.aggregate_factory import AggregateFactory
from app.document_engine.write.aggregate_models import AggregateMetadata, DocumentAggregate
from app.document_engine.write.command_models import (
    AnnulDocumentCommand,
    ArchiveDocumentCommand,
    CancelDocumentCommand,
    CreateDocumentCommand,
    MarkReadyCommand,
    PromoteDraftCommand,
    RegisterDocumentCommand,
    RestoreDocumentCommand,
    ReturnToDraftCommand,
    SignDocumentCommand,
)
from app.document_engine.write.command_policies import CommandPolicy
from app.document_engine.write.command_results import (
    CreateResult,
    LifecycleMutationPlan,
    PromotionResult,
    RegistrationResult,
    WriteEvaluation,
)
from app.document_engine.write.compatibility import (
    WriteCompatibilityDifference,
    WriteCompatibilityReport,
    compare_aggregate_to_lifecycle,
    compare_write_evaluation_to_lifecycle,
    format_write_compatibility_report,
)
from app.document_engine.write.domain_events import (
    DocumentActivated,
    DocumentAnnulled,
    DocumentArchived,
    DocumentCancelled,
    DocumentMarkedReady,
    DocumentPromoted,
    DocumentRegistered,
    DocumentRestored,
    DocumentReturnedToDraft,
    DocumentSigned,
    DomainEvent,
)
from app.document_engine.write.facade import (
    DocumentEngineWriteContext,
    DocumentEngineWriteFacade,
    DocumentEngineWriteSnapshot,
)
from app.document_engine.write.write_orchestrator import WriteCommand, WriteOrchestrator

__all__ = [
    "AggregateFactory",
    "AggregateMetadata",
    "AnnulDocumentCommand",
    "ArchiveDocumentCommand",
    "CancelDocumentCommand",
    "CommandPolicy",
    "CreateDocumentCommand",
    "CreateResult",
    "DocumentActivated",
    "DocumentAggregate",
    "DocumentAnnulled",
    "DocumentArchived",
    "DocumentCancelled",
    "DocumentEngineWriteContext",
    "DocumentEngineWriteFacade",
    "DocumentEngineWriteSnapshot",
    "DocumentMarkedReady",
    "DocumentPromoted",
    "DocumentRegistered",
    "DocumentRestored",
    "DocumentReturnedToDraft",
    "DocumentSigned",
    "DomainEvent",
    "LifecycleMutationPlan",
    "MarkReadyCommand",
    "PromoteDraftCommand",
    "PromotionResult",
    "RegisterDocumentCommand",
    "RegistrationResult",
    "RestoreDocumentCommand",
    "ReturnToDraftCommand",
    "SignDocumentCommand",
    "WriteCommand",
    "WriteCompatibilityDifference",
    "WriteCompatibilityReport",
    "WriteEvaluation",
    "WriteOrchestrator",
    "compare_aggregate_to_lifecycle",
    "compare_write_evaluation_to_lifecycle",
    "format_write_compatibility_report",
]
