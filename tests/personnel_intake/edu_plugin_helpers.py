"""Shared helpers for education reconciliation plugin tests."""
from __future__ import annotations

from typing import Any

from app.personnel_intake.application.reconciliation.dto import CanonicalRecordRef
from app.personnel_intake.application.reconciliation.plugins.education import (
    EducationReconciliationPlugin,
    QUALITY_KEY,
    education_identity_fingerprint,
)


def intake_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "education_type": "basic",
        "institution": "МГУ",
        "year_from": "2015-09-01",
        "year_to": "2019-06-30",
        "specialty": "Математика",
        "qualification": "Бакалавр",
        "document_type": "diploma",
        "diploma_number": "D-1",
    }
    row.update(overrides)
    return row


def build_proposal(plugin: EducationReconciliationPlugin, **overrides: Any):
    refs = plugin.build_proposal_refs({"records": [intake_row(**overrides)]}, "canon-json-v1")
    return refs[0]


def canonical_ref(
    record_id: int,
    *,
    education_kind: str = "basic",
    institution_name: str = "МГУ",
    specialty: str | None = "Математика",
    qualification: str | None = "Бакалавр",
    started_at: str | None = "2015-09-01",
    completed_at: str | None = "2019-06-30",
    diploma_number: str | None = "D-1",
    document_type: str | None = "diploma",
    row_version: str = "2026-07-24T10:00:00",
) -> CanonicalRecordRef:
    content = {
        "education_kind": education_kind,
        "institution_name": institution_name,
        "specialty": specialty,
        "qualification": qualification,
        "started_at": started_at,
        "completed_at": completed_at,
        "diploma_number": diploma_number,
        "document_type": document_type,
        QUALITY_KEY: {
            "started_at": {
                "precision": "day" if started_at else "missing",
                "raw": started_at,
            },
            "completed_at": {
                "precision": "day" if completed_at else "missing",
                "raw": completed_at,
            },
        },
    }
    return CanonicalRecordRef(
        record_id=record_id,
        lifecycle_status="active",
        row_version=row_version,
        record_fingerprint=education_identity_fingerprint(content),
        normalized_content=content,
    )
