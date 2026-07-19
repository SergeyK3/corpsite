"""Minimal MRD schema repository for WP-MRD-001 contract tests."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Optional

from sqlalchemy import Connection, text


@dataclass(frozen=True, slots=True)
class MonthlyReferenceRow:
    mrd_id: int
    report_period: date
    version: int
    status: str
    row_version: int


@dataclass(frozen=True, slots=True)
class DetectedDifferenceRow:
    difference_id: int
    report_period: date
    mrd_id: int
    logical_key: str
    lifecycle_status: str
    difference_origin_code: str
    supersedes_difference_id: int | None
    row_version: int


@dataclass(frozen=True, slots=True)
class ConfirmedChangeRow:
    confirmed_change_id: int
    detected_difference_id: int
    mrd_id: int
    difference_origin_code: str


class MrdSchemaRepository:
    """Thin SQL repository used by schema/contract tests only."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def insert_monthly_reference(
        self,
        *,
        report_period: date,
        version: int,
        created_by: int,
        status: str = "ACTIVE",
        closed_at: datetime | None = None,
        closed_by: int | None = None,
    ) -> MonthlyReferenceRow:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.hr_monthly_references (
                    report_period, version, status, created_by, closed_at, closed_by
                )
                VALUES (
                    :report_period, :version, :status, :created_by, :closed_at, :closed_by
                )
                RETURNING mrd_id, report_period, version, status, row_version
                """
            ),
            {
                "report_period": report_period,
                "version": version,
                "status": status,
                "created_by": created_by,
                "closed_at": closed_at,
                "closed_by": closed_by,
            },
        ).mappings().one()
        return MonthlyReferenceRow(
            mrd_id=int(row["mrd_id"]),
            report_period=row["report_period"],
            version=int(row["version"]),
            status=str(row["status"]),
            row_version=int(row["row_version"]),
        )

    def insert_detected_difference(
        self,
        *,
        report_period: date,
        mrd_id: int,
        logical_key: str,
        entity_scope: str,
        attribute: str,
        business_type: str,
        difference_origin_code: str,
        origin_context: Mapping[str, Any] | None = None,
        lifecycle_status: str = "DETECTED",
        old_value: Any | None = None,
        new_value: Any | None = None,
        supersedes_difference_id: int | None = None,
    ) -> DetectedDifferenceRow:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.hr_detected_differences (
                    report_period,
                    mrd_id,
                    logical_key,
                    entity_scope,
                    attribute,
                    business_type,
                    lifecycle_status,
                    difference_origin_code,
                    origin_context,
                    old_value,
                    new_value,
                    supersedes_difference_id
                )
                VALUES (
                    :report_period,
                    :mrd_id,
                    :logical_key,
                    :entity_scope,
                    :attribute,
                    :business_type,
                    :lifecycle_status,
                    :difference_origin_code,
                    CAST(:origin_context AS jsonb),
                    CAST(:old_value AS jsonb),
                    CAST(:new_value AS jsonb),
                    :supersedes_difference_id
                )
                RETURNING
                    difference_id,
                    report_period,
                    mrd_id,
                    logical_key,
                    lifecycle_status,
                    difference_origin_code,
                    supersedes_difference_id,
                    row_version
                """
            ),
            {
                "report_period": report_period,
                "mrd_id": mrd_id,
                "logical_key": logical_key,
                "entity_scope": entity_scope,
                "attribute": attribute,
                "business_type": business_type,
                "lifecycle_status": lifecycle_status,
                "difference_origin_code": difference_origin_code,
                "origin_context": _json_param(origin_context or {}),
                "old_value": _json_param(old_value),
                "new_value": _json_param(new_value),
                "supersedes_difference_id": supersedes_difference_id,
            },
        ).mappings().one()
        return DetectedDifferenceRow(
            difference_id=int(row["difference_id"]),
            report_period=row["report_period"],
            mrd_id=int(row["mrd_id"]),
            logical_key=str(row["logical_key"]),
            lifecycle_status=str(row["lifecycle_status"]),
            difference_origin_code=str(row["difference_origin_code"]),
            supersedes_difference_id=(
                int(row["supersedes_difference_id"])
                if row["supersedes_difference_id"] is not None
                else None
            ),
            row_version=int(row["row_version"]),
        )

    def insert_confirmed_change(
        self,
        *,
        detected_difference_id: int,
        report_period: date,
        mrd_id: int,
        entity_scope: str,
        attribute: str,
        new_value: Any,
        confirmed_by: int,
        difference_origin_code: str,
        old_value: Any | None = None,
        origin_context: Mapping[str, Any] | None = None,
    ) -> ConfirmedChangeRow:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.hr_confirmed_changes (
                    detected_difference_id,
                    report_period,
                    mrd_id,
                    entity_scope,
                    attribute,
                    old_value,
                    new_value,
                    confirmed_by,
                    difference_origin_code,
                    origin_context
                )
                VALUES (
                    :detected_difference_id,
                    :report_period,
                    :mrd_id,
                    :entity_scope,
                    :attribute,
                    CAST(:old_value AS jsonb),
                    CAST(:new_value AS jsonb),
                    :confirmed_by,
                    :difference_origin_code,
                    CAST(:origin_context AS jsonb)
                )
                RETURNING confirmed_change_id, detected_difference_id, mrd_id, difference_origin_code
                """
            ),
            {
                "detected_difference_id": detected_difference_id,
                "report_period": report_period,
                "mrd_id": mrd_id,
                "entity_scope": entity_scope,
                "attribute": attribute,
                "old_value": _json_param(old_value),
                "new_value": _json_param(new_value),
                "confirmed_by": confirmed_by,
                "difference_origin_code": difference_origin_code,
                "origin_context": _json_param(origin_context),
            },
        ).mappings().one()
        return ConfirmedChangeRow(
            confirmed_change_id=int(row["confirmed_change_id"]),
            detected_difference_id=int(row["detected_difference_id"]),
            mrd_id=int(row["mrd_id"]),
            difference_origin_code=str(row["difference_origin_code"]),
        )

    def insert_entry(
        self,
        *,
        mrd_id: int,
        entity_scope: str,
        match_key: str,
        canonical_hash: str,
        effective_payload: Mapping[str, Any] | None = None,
        record_kind: str = "roster",
    ) -> int:
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.hr_monthly_reference_entries (
                    mrd_id,
                    entity_scope,
                    record_kind,
                    match_key,
                    canonical_hash,
                    effective_payload
                )
                VALUES (
                    :mrd_id,
                    :entity_scope,
                    :record_kind,
                    :match_key,
                    :canonical_hash,
                    CAST(:effective_payload AS jsonb)
                )
                RETURNING entry_id
                """
            ),
            {
                "mrd_id": mrd_id,
                "entity_scope": entity_scope,
                "record_kind": record_kind,
                "match_key": match_key,
                "canonical_hash": canonical_hash,
                "effective_payload": _json_param(effective_payload or {}),
            },
        ).scalar_one()
        return int(row)

    def load_origin_is_active(self, origin_code: str) -> Optional[bool]:
        row = self._conn.execute(
            text(
                """
                SELECT is_active
                FROM public.hr_difference_origin_types
                WHERE origin_code = :origin_code
                """
            ),
            {"origin_code": origin_code},
        ).scalar_one_or_none()
        return bool(row) if row is not None else None

    def count_confirmed_changes_for_difference(self, difference_id: int) -> int:
        value = self._conn.execute(
            text(
                """
                SELECT COUNT(*)::bigint
                FROM public.hr_confirmed_changes
                WHERE detected_difference_id = :difference_id
                """
            ),
            {"difference_id": difference_id},
        ).scalar_one()
        return int(value)


def _json_param(value: Any) -> str | None:
    if value is None:
        return None
    import json

    return json.dumps(value, ensure_ascii=False, default=str)
