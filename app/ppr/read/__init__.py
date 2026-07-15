"""PPR read model layer — composite query (R6)."""
from __future__ import annotations

from app.ppr.read.models import (
    PprCompositeReadModel,
    PprCompositeReadMetadata,
    PprCompositeSummary,
    PprEnvelopeReadSlice,
    PprEventSummary,
    PprEventSummaryEntry,
    PprSectionAggregation,
)
from app.ppr.read.orchestrator import PprCompositeReadOrchestrator
from app.ppr.read.query_service import PprQueryApplicationService
from app.ppr.read.uow import PprReadUnitOfWork

__all__ = [
    "PprCompositeReadMetadata",
    "PprCompositeReadModel",
    "PprCompositeReadOrchestrator",
    "PprCompositeSummary",
    "PprEnvelopeReadSlice",
    "PprEventSummary",
    "PprEventSummaryEntry",
    "PprQueryApplicationService",
    "PprReadUnitOfWork",
    "PprSectionAggregation",
]
