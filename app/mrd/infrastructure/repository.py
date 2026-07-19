"""SQLAlchemy repositories for MRD application layer (WP-MRD-002)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping

from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from app.mrd.domain.candidate_builder import CONFLICT_ATTRIBUTE, RECORD_PRESENCE_ATTRIBUTE
from app.mrd.domain.difference_models import CreateDifferenceCommand, DetectedDifferenceRecord
from app.mrd.domain.errors import (
    DifferenceNotFoundError,
    DifferenceOriginError,
    MrdNotFoundError,
    MrdOptimisticConcurrencyConflictError,
)
from app.mrd.domain.invariants import validate_active_origin
from app.mrd.domain.types import (
    DIFFERENCE_LIFECYCLE_DETECTED,
    DIFFERENCE_LIFECYCLE_SUPERSEDED,
    MRD_STATUS_ACTIVE,
    MRD_STATUS_CLOSED,
)
from app.services.hr_canonical_snapshot_service import compute_canonical_hash


@dataclass(frozen=True, slots=True)
class MonthlyReferenceRow:
    mrd_id: int
    report_period: date
    version: int
    status: str
    row_version: int
    entry_count: int


@dataclass(frozen=True, slots=True)
class MrdVersionDetailRow:
    mrd_id: int
    report_period: date
    version: int
    status: str
    row_version: int
    entry_count: int
    forked_from_reference_id: int | None


@dataclass(frozen=True, slots=True)
class MrdEntryRow:
    entry_id: int
    mrd_id: int
    match_key: str
    entity_scope: str
    record_kind: str
    canonical_hash: str
    effective_payload: dict[str, Any]
    row_version: int


class SqlAlchemyMrdRepository:
    """Read/write access to MRD tables within caller transaction."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def resolve_active_mrd(self, report_period: date) -> MonthlyReferenceRow | None:
        rows = self.list_active_mrd_candidates(report_period)
        if not rows:
            return None
        return rows[0]

    def list_active_mrd_candidates(self, report_period: date) -> list[MonthlyReferenceRow]:
        rows = self._conn.execute(
            text(
                """
                SELECT mrd_id, report_period, version, status, row_version, entry_count
                FROM public.hr_monthly_references
                WHERE report_period = :report_period
                  AND status = 'ACTIVE'
                ORDER BY mrd_id
                """
            ),
            {"report_period": report_period},
        ).mappings().all()
        return [_to_mrd_row(row) for row in rows]

    def lock_active_mrd_for_period(self, report_period: date) -> MonthlyReferenceRow | None:
        row = self._conn.execute(
            text(
                """
                SELECT mrd_id, report_period, version, status, row_version, entry_count
                FROM public.hr_monthly_references
                WHERE report_period = :report_period
                  AND status = 'ACTIVE'
                FOR UPDATE
                """
            ),
            {"report_period": report_period},
        ).mappings().one_or_none()
        return _to_mrd_row(row) if row else None

    def period_has_mrd(self, report_period: date) -> bool:
        value = self._conn.execute(
            text(
                """
                SELECT 1
                FROM public.hr_monthly_references
                WHERE report_period = :report_period
                LIMIT 1
                """
            ),
            {"report_period": report_period},
        ).first()
        return value is not None

    def max_version_for_period(self, report_period: date) -> int:
        value = self._conn.execute(
            text(
                """
                SELECT COALESCE(MAX(version), 0)::int
                FROM public.hr_monthly_references
                WHERE report_period = :report_period
                """
            ),
            {"report_period": report_period},
        ).scalar_one()
        return int(value)

    def close_mrd(
        self,
        mrd_id: int,
        *,
        closed_by: int,
        expected_row_version: int,
        closed_at: datetime,
    ) -> None:
        updated = self._conn.execute(
            text(
                """
                UPDATE public.hr_monthly_references
                SET status = :closed_status,
                    closed_at = :closed_at,
                    closed_by = :closed_by,
                    row_version = row_version + 1
                WHERE mrd_id = :mrd_id
                  AND status = :active_status
                  AND row_version = :expected_row_version
                """
            ),
            {
                "mrd_id": mrd_id,
                "closed_status": MRD_STATUS_CLOSED,
                "active_status": MRD_STATUS_ACTIVE,
                "closed_at": closed_at,
                "closed_by": closed_by,
                "expected_row_version": expected_row_version,
            },
        ).rowcount
        if updated != 1:
            raise MrdOptimisticConcurrencyConflictError(
                f"Failed to close ACTIVE MRD mrd_id={mrd_id}"
            )

    def create_mrd_version(
        self,
        *,
        report_period: date,
        version: int,
        created_by: int,
        forked_from_reference_id: int,
        entry_count: int,
        notes: str | None = None,
    ) -> MonthlyReferenceRow:
        try:
            row = self._conn.execute(
                text(
                    """
                    INSERT INTO public.hr_monthly_references (
                        report_period,
                        version,
                        status,
                        forked_from_reference_id,
                        entry_count,
                        created_by,
                        notes
                    )
                    VALUES (
                        :report_period,
                        :version,
                        :active_status,
                        :forked_from_reference_id,
                        :entry_count,
                        :created_by,
                        :notes
                    )
                    RETURNING mrd_id, report_period, version, status, row_version, entry_count
                    """
                ),
                {
                    "report_period": report_period,
                    "version": version,
                    "active_status": MRD_STATUS_ACTIVE,
                    "forked_from_reference_id": forked_from_reference_id,
                    "entry_count": entry_count,
                    "created_by": created_by,
                    "notes": notes,
                },
            ).mappings().one()
        except IntegrityError as exc:
            raise MrdOptimisticConcurrencyConflictError(
                f"Failed to create MRD version {report_period.isoformat()} v{version}"
            ) from exc
        return _to_mrd_row(row)

    def copy_confirmed_entries(self, *, source_mrd_id: int, target_mrd_id: int) -> int:
        copied = int(
            self._conn.execute(
                text(
                    """
                    INSERT INTO public.hr_monthly_reference_entries (
                        mrd_id,
                        entity_scope,
                        record_kind,
                        match_key,
                        canonical_hash,
                        employee_id,
                        iin,
                        effective_payload,
                        source_row_id,
                        source_normalized_record_id,
                        last_confirmed_change_id
                    )
                    SELECT
                        :target_mrd_id,
                        entity_scope,
                        record_kind,
                        match_key,
                        canonical_hash,
                        employee_id,
                        iin,
                        effective_payload,
                        source_row_id,
                        source_normalized_record_id,
                        NULL
                    FROM public.hr_monthly_reference_entries
                    WHERE mrd_id = :source_mrd_id
                    """
                ),
                {"source_mrd_id": source_mrd_id, "target_mrd_id": target_mrd_id},
            ).rowcount
        )
        return copied

    def insert_version_event(
        self,
        *,
        event_type: str,
        report_period: date,
        mrd_id: int,
        performed_by: int,
        source_mrd_id: int | None = None,
        event_context: Mapping[str, Any] | None = None,
        performed_at: datetime | None = None,
    ) -> int:
        params = {
            "event_type": event_type,
            "report_period": report_period,
            "mrd_id": mrd_id,
            "source_mrd_id": source_mrd_id,
            "performed_by": performed_by,
            "event_context": _json(event_context or {}),
            "performed_at": performed_at,
        }
        if performed_at is None:
            return int(
                self._conn.execute(
                    text(
                        """
                        INSERT INTO public.hr_reference_version_events (
                            event_type,
                            report_period,
                            mrd_id,
                            source_mrd_id,
                            performed_by,
                            event_context
                        )
                        VALUES (
                            :event_type,
                            :report_period,
                            :mrd_id,
                            :source_mrd_id,
                            :performed_by,
                            CAST(:event_context AS jsonb)
                        )
                        RETURNING event_id
                        """
                    ),
                    params,
                ).scalar_one()
            )
        return int(
            self._conn.execute(
                text(
                    """
                    INSERT INTO public.hr_reference_version_events (
                        event_type,
                        report_period,
                        mrd_id,
                        source_mrd_id,
                        performed_by,
                        performed_at,
                        event_context
                    )
                    VALUES (
                        :event_type,
                        :report_period,
                        :mrd_id,
                        :source_mrd_id,
                        :performed_by,
                        :performed_at,
                        CAST(:event_context AS jsonb)
                    )
                    RETURNING event_id
                    """
                ),
                params,
            ).scalar_one()
        )

    def list_version_events(self, *, mrd_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            text(
                """
                SELECT event_id, event_type, report_period, mrd_id, source_mrd_id, event_context
                FROM public.hr_reference_version_events
                WHERE mrd_id = :mrd_id
                ORDER BY event_id
                """
            ),
            {"mrd_id": mrd_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def count_comparison_runs_for_mrd(self, mrd_id: int) -> int:
        return int(
            self._conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.hr_comparison_runs
                    WHERE mrd_id = :mrd_id
                    """
                ),
                {"mrd_id": mrd_id},
            ).scalar_one()
        )

    def load_mrd(self, mrd_id: int) -> MonthlyReferenceRow | None:
        row = self._conn.execute(
            text(
                """
                SELECT mrd_id, report_period, version, status, row_version, entry_count
                FROM public.hr_monthly_references
                WHERE mrd_id = :mrd_id
                """
            ),
            {"mrd_id": mrd_id},
        ).mappings().one_or_none()
        return _to_mrd_row(row) if row else None

    def load_mrd_version_detail(self, mrd_id: int) -> MrdVersionDetailRow | None:
        row = self._conn.execute(
            text(
                """
                SELECT
                    mrd_id,
                    report_period,
                    version,
                    status,
                    row_version,
                    entry_count,
                    forked_from_reference_id
                FROM public.hr_monthly_references
                WHERE mrd_id = :mrd_id
                """
            ),
            {"mrd_id": mrd_id},
        ).mappings().one_or_none()
        return _to_version_detail_row(row) if row else None

    def list_mrd_version_details(
        self,
        *,
        report_period: date | None = None,
        limit: int = 500,
    ) -> list[MrdVersionDetailRow]:
        params: dict[str, Any] = {"limit": int(limit)}
        period_filter = ""
        if report_period is not None:
            period_filter = "WHERE report_period = :report_period"
            params["report_period"] = report_period
        rows = self._conn.execute(
            text(
                f"""
                SELECT
                    mrd_id,
                    report_period,
                    version,
                    status,
                    row_version,
                    entry_count,
                    forked_from_reference_id
                FROM public.hr_monthly_references
                {period_filter}
                ORDER BY report_period DESC, version DESC, mrd_id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        return [_to_version_detail_row(row) for row in rows]

    def load_mrd_entries(self, mrd_id: int) -> list[MrdEntryRow]:
        rows = self._conn.execute(
            text(
                """
                SELECT
                    entry_id,
                    mrd_id,
                    match_key,
                    entity_scope,
                    record_kind,
                    canonical_hash,
                    effective_payload,
                    row_version
                FROM public.hr_monthly_reference_entries
                WHERE mrd_id = :mrd_id
                ORDER BY entry_id
                """
            ),
            {"mrd_id": mrd_id},
        ).mappings().all()
        return [_to_entry_row(row) for row in rows]

    def load_entry_by_match_key(self, *, mrd_id: int, match_key: str) -> MrdEntryRow | None:
        row = self._conn.execute(
            text(
                """
                SELECT
                    entry_id,
                    mrd_id,
                    match_key,
                    entity_scope,
                    record_kind,
                    canonical_hash,
                    effective_payload,
                    row_version
                FROM public.hr_monthly_reference_entries
                WHERE mrd_id = :mrd_id
                  AND match_key = :match_key
                """
            ),
            {"mrd_id": mrd_id, "match_key": match_key},
        ).mappings().one_or_none()
        return _to_entry_row(row) if row else None

    def count_differences_for_mrd(self, mrd_id: int) -> int:
        return int(
            self._conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.hr_detected_differences
                    WHERE mrd_id = :mrd_id
                    """
                ),
                {"mrd_id": mrd_id},
            ).scalar_one()
        )

    def count_differences_for_mrd_by_status(self, mrd_id: int, lifecycle_status: str) -> int:
        return int(
            self._conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.hr_detected_differences
                    WHERE mrd_id = :mrd_id
                      AND lifecycle_status = :lifecycle_status
                    """
                ),
                {"mrd_id": mrd_id, "lifecycle_status": lifecycle_status},
            ).scalar_one()
        )

    def list_mrd_entries_page(
        self,
        *,
        mrd_id: int,
        limit: int,
        offset: int,
    ) -> tuple[list[MrdEntryRow], int]:
        total = int(
            self._conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.hr_monthly_reference_entries
                    WHERE mrd_id = :mrd_id
                    """
                ),
                {"mrd_id": mrd_id},
            ).scalar_one()
        )
        rows = self._conn.execute(
            text(
                """
                SELECT
                    entry_id,
                    mrd_id,
                    match_key,
                    entity_scope,
                    record_kind,
                    canonical_hash,
                    effective_payload,
                    row_version
                FROM public.hr_monthly_reference_entries
                WHERE mrd_id = :mrd_id
                ORDER BY match_key, entry_id
                LIMIT :limit OFFSET :offset
                """
            ),
            {"mrd_id": mrd_id, "limit": limit, "offset": offset},
        ).mappings().all()
        return [_to_entry_row(row) for row in rows], total

    def list_roster_entries_for_org_unit(
        self,
        *,
        mrd_id: int,
        org_unit_id: int,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MrdEntryRow], int]:
        search_pattern = f"%{search.strip()}%" if search and search.strip() else None
        count_params: dict[str, Any] = {"mrd_id": mrd_id, "org_unit_id": org_unit_id}
        search_clause = ""
        if search_pattern:
            search_clause = " AND effective_payload->>'full_name' ILIKE :search"
            count_params["search"] = search_pattern
        total = int(
            self._conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)::bigint
                    FROM public.hr_monthly_reference_entries
                    WHERE mrd_id = :mrd_id
                      AND record_kind = 'roster'
                      AND NULLIF(effective_payload->>'org_unit_id', '')::bigint = :org_unit_id
                    {search_clause}
                    """
                ),
                count_params,
            ).scalar_one()
        )
        list_params = {**count_params, "limit": limit, "offset": offset}
        rows = self._conn.execute(
            text(
                f"""
                SELECT
                    entry_id,
                    mrd_id,
                    match_key,
                    entity_scope,
                    record_kind,
                    canonical_hash,
                    effective_payload,
                    row_version
                FROM public.hr_monthly_reference_entries
                WHERE mrd_id = :mrd_id
                  AND record_kind = 'roster'
                  AND NULLIF(effective_payload->>'org_unit_id', '')::bigint = :org_unit_id
                {search_clause}
                ORDER BY effective_payload->>'full_name', match_key
                LIMIT :limit OFFSET :offset
                """
            ),
            list_params,
        ).mappings().all()
        return [_to_entry_row(row) for row in rows], total

    def list_all_roster_entries_for_org_unit(
        self,
        *,
        mrd_id: int,
        org_unit_id: int,
        search: str | None = None,
    ) -> list[MrdEntryRow]:
        rows, _total = self.list_roster_entries_for_org_unit(
            mrd_id=mrd_id,
            org_unit_id=org_unit_id,
            search=search,
            limit=100000,
            offset=0,
        )
        return rows

    def list_confirmed_changes_for_mrd(
        self,
        *,
        mrd_id: int,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        total = int(
            self._conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.hr_confirmed_changes
                    WHERE mrd_id = :mrd_id
                    """
                ),
                {"mrd_id": mrd_id},
            ).scalar_one()
        )
        rows = self._conn.execute(
            text(
                """
                SELECT
                    confirmed_change_id,
                    detected_difference_id,
                    report_period,
                    mrd_id,
                    entity_scope,
                    attribute,
                    old_value,
                    new_value,
                    confirmed_by,
                    confirmed_at,
                    basis,
                    difference_origin_code,
                    source_batch_id
                FROM public.hr_confirmed_changes
                WHERE mrd_id = :mrd_id
                ORDER BY confirmed_at DESC, confirmed_change_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"mrd_id": mrd_id, "limit": limit, "offset": offset},
        ).mappings().all()
        return [dict(row) for row in rows], total

    def count_confirmed_changes_for_mrd(self, mrd_id: int) -> int:
        return int(
            self._conn.execute(
                text(
                    """
                    SELECT COUNT(*)::bigint
                    FROM public.hr_confirmed_changes
                    WHERE mrd_id = :mrd_id
                    """
                ),
                {"mrd_id": mrd_id},
            ).scalar_one()
        )

    def origin_is_active(self, origin_code: str) -> bool:
        value = self._conn.execute(
            text(
                """
                SELECT is_active
                FROM public.hr_difference_origin_types
                WHERE origin_code = :origin_code
                """
            ),
            {"origin_code": origin_code},
        ).scalar_one_or_none()
        return bool(value) if value is not None else False

    def load_difference(self, difference_id: int) -> DetectedDifferenceRecord | None:
        row = self._conn.execute(
            text(
                """
                SELECT
                    difference_id,
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
                    technical_diff_class,
                    row_version,
                    record_kind,
                    supersedes_difference_id
                FROM public.hr_detected_differences
                WHERE difference_id = :difference_id
                """
            ),
            {"difference_id": difference_id},
        ).mappings().one_or_none()
        return _to_difference_row(row) if row else None

    def list_differences_for_mrd(self, mrd_id: int) -> list[DetectedDifferenceRecord]:
        rows = self._conn.execute(
            text(
                """
                SELECT
                    difference_id,
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
                    technical_diff_class,
                    row_version,
                    record_kind,
                    supersedes_difference_id
                FROM public.hr_detected_differences
                WHERE mrd_id = :mrd_id
                ORDER BY difference_id
                """
            ),
            {"mrd_id": mrd_id},
        ).mappings().all()
        return [_to_difference_row(row) for row in rows]

    def insert_difference(self, command: CreateDifferenceCommand) -> DetectedDifferenceRecord:
        if not self.origin_is_active(command.difference_origin_code):
            raise DifferenceOriginError(
                f"difference_origin_code {command.difference_origin_code!r} is missing or inactive"
            )
        validate_active_origin(command.difference_origin_code, is_active=True)
        row = self._conn.execute(
            text(
                """
                INSERT INTO public.hr_detected_differences (
                    report_period,
                    mrd_id,
                    logical_key,
                    entity_scope,
                    record_kind,
                    attribute,
                    business_type,
                    lifecycle_status,
                    technical_diff_class,
                    difference_origin_code,
                    origin_context,
                    old_value,
                    new_value,
                    supersedes_difference_id,
                    last_comparison_run_id
                )
                VALUES (
                    :report_period,
                    :mrd_id,
                    :logical_key,
                    :entity_scope,
                    :record_kind,
                    :attribute,
                    :business_type,
                    'DETECTED',
                    :technical_diff_class,
                    :difference_origin_code,
                    CAST(:origin_context AS jsonb),
                    CAST(:old_value AS jsonb),
                    CAST(:new_value AS jsonb),
                    :supersedes_difference_id,
                    :last_comparison_run_id
                )
                RETURNING
                    difference_id,
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
                    technical_diff_class,
                    row_version,
                    record_kind,
                    supersedes_difference_id
                """
            ),
            {
                "report_period": command.report_period,
                "mrd_id": command.mrd_id,
                "logical_key": command.logical_key,
                "entity_scope": command.entity_scope,
                "record_kind": command.record_kind,
                "attribute": command.attribute,
                "business_type": command.business_type,
                "technical_diff_class": command.technical_diff_class,
                "difference_origin_code": command.difference_origin_code,
                "origin_context": _json(command.origin_context),
                "old_value": _json(command.old_value),
                "new_value": _json(command.new_value),
                "supersedes_difference_id": command.supersedes_difference_id,
                "last_comparison_run_id": command.last_comparison_run_id,
            },
        ).mappings().one()
        return _to_difference_row(row)

    def mark_superseded(self, difference_id: int, *, expected_row_version: int) -> None:
        updated = self._conn.execute(
            text(
                """
                UPDATE public.hr_detected_differences
                SET lifecycle_status = 'SUPERSEDED',
                    row_version = row_version + 1
                WHERE difference_id = :difference_id
                  AND lifecycle_status = 'DETECTED'
                  AND row_version = :expected_row_version
                """
            ),
            {"difference_id": difference_id, "expected_row_version": expected_row_version},
        ).rowcount
        if updated != 1:
            raise MrdOptimisticConcurrencyConflictError(
                f"Failed to supersede difference_id={difference_id}"
            )

    def mark_confirmed(
        self,
        difference_id: int,
        *,
        expected_row_version: int,
        confirmed_by: int,
        confirmed_at: datetime,
    ) -> None:
        updated = self._conn.execute(
            text(
                """
                UPDATE public.hr_detected_differences
                SET lifecycle_status = 'CONFIRMED',
                    confirmed_by = :confirmed_by,
                    confirmed_at = :confirmed_at,
                    row_version = row_version + 1
                WHERE difference_id = :difference_id
                  AND lifecycle_status = 'DETECTED'
                  AND row_version = :expected_row_version
                """
            ),
            {
                "difference_id": difference_id,
                "expected_row_version": expected_row_version,
                "confirmed_by": confirmed_by,
                "confirmed_at": confirmed_at,
            },
        ).rowcount
        if updated != 1:
            raise MrdOptimisticConcurrencyConflictError(
                f"Failed to confirm difference_id={difference_id}"
            )

    def mark_rejected(
        self,
        difference_id: int,
        *,
        expected_row_version: int,
        rejected_by: int,
        rejected_at: datetime,
        basis: str | None,
    ) -> None:
        updated = self._conn.execute(
            text(
                """
                UPDATE public.hr_detected_differences
                SET lifecycle_status = 'REJECTED',
                    rejected_by = :rejected_by,
                    rejected_at = :rejected_at,
                    reject_basis = :basis,
                    row_version = row_version + 1
                WHERE difference_id = :difference_id
                  AND lifecycle_status = 'DETECTED'
                  AND row_version = :expected_row_version
                """
            ),
            {
                "difference_id": difference_id,
                "expected_row_version": expected_row_version,
                "rejected_by": rejected_by,
                "rejected_at": rejected_at,
                "basis": basis,
            },
        ).rowcount
        if updated != 1:
            raise MrdOptimisticConcurrencyConflictError(
                f"Failed to reject difference_id={difference_id}"
            )

    def touch_comparison_run(self, difference_id: int, *, comparison_run_id: int) -> None:
        self._conn.execute(
            text(
                """
                UPDATE public.hr_detected_differences
                SET last_comparison_run_id = :comparison_run_id
                WHERE difference_id = :difference_id
                  AND lifecycle_status = 'DETECTED'
                """
            ),
            {"difference_id": difference_id, "comparison_run_id": comparison_run_id},
        )

    def insert_comparison_run(
        self,
        *,
        batch_id: int,
        mrd_id: int,
        report_period: date,
        started_by: int | None,
        stats: Mapping[str, int],
    ) -> int:
        return int(
            self._conn.execute(
                text(
                    """
                    INSERT INTO public.hr_comparison_runs (
                        batch_id,
                        mrd_id,
                        report_period,
                        status,
                        started_by,
                        stats,
                        completed_at
                    )
                    VALUES (
                        :batch_id,
                        :mrd_id,
                        :report_period,
                        'COMPLETED',
                        :started_by,
                        CAST(:stats AS jsonb),
                        NOW()
                    )
                    RETURNING comparison_run_id
                    """
                ),
                {
                    "batch_id": batch_id,
                    "mrd_id": mrd_id,
                    "report_period": report_period,
                    "started_by": started_by,
                    "stats": _json(dict(stats)),
                },
            ).scalar_one()
        )

    def insert_confirmed_change(
        self,
        *,
        difference: DetectedDifferenceRecord,
        confirmed_by: int,
        confirmed_at: datetime,
        basis: str | None,
    ) -> int:
        source_batch_id_raw = difference.origin_context.get("batch_id")
        source_batch_id: int | None = None
        if source_batch_id_raw is not None:
            exists = self._conn.execute(
                text(
                    """
                    SELECT 1
                    FROM public.hr_import_batches
                    WHERE batch_id = :batch_id
                    LIMIT 1
                    """
                ),
                {"batch_id": int(source_batch_id_raw)},
            ).first()
            if exists:
                source_batch_id = int(source_batch_id_raw)
        try:
            return int(
                self._conn.execute(
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
                            confirmed_at,
                            basis,
                            difference_origin_code,
                            origin_context,
                            source_batch_id
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
                            :confirmed_at,
                            :basis,
                            :difference_origin_code,
                            CAST(:origin_context AS jsonb),
                            :source_batch_id
                        )
                        RETURNING confirmed_change_id
                        """
                    ),
                    {
                        "detected_difference_id": difference.difference_id,
                        "report_period": difference.report_period,
                        "mrd_id": difference.mrd_id,
                        "entity_scope": difference.entity_scope,
                        "attribute": difference.attribute,
                        "old_value": _json(difference.old_value),
                        "new_value": _json(difference.new_value),
                        "confirmed_by": confirmed_by,
                        "confirmed_at": confirmed_at,
                        "basis": basis,
                        "difference_origin_code": difference.difference_origin_code,
                        "origin_context": _json(difference.origin_context),
                        "source_batch_id": source_batch_id,
                    },
                ).scalar_one()
            )
        except IntegrityError as exc:
            raise MrdOptimisticConcurrencyConflictError(
                "Confirmed Change already exists for difference"
            ) from exc

    def apply_attribute_change(
        self,
        *,
        mrd_id: int,
        match_key: str,
        entity_scope: str,
        record_kind: str,
        attribute: str,
        old_value: Any,
        new_value: Any,
        confirmed_change_id: int,
    ) -> int | None:
        mrd = self.load_mrd(mrd_id)
        if mrd is None:
            raise MrdNotFoundError(f"MRD mrd_id={mrd_id} not found")
        if mrd.status != MRD_STATUS_ACTIVE:
            raise MrdNotFoundError(f"MRD mrd_id={mrd_id} is not ACTIVE")

        existing = self.load_entry_by_match_key(mrd_id=mrd_id, match_key=match_key)
        if attribute == RECORD_PRESENCE_ATTRIBUTE:
            if existing is not None:
                self._conn.execute(
                    text(
                        """
                        DELETE FROM public.hr_monthly_reference_entries
                        WHERE entry_id = :entry_id
                        """
                    ),
                    {"entry_id": existing.entry_id},
                )
                self._adjust_entry_count(mrd_id, delta=-1)
            return existing.entry_id if existing else None

        if attribute == CONFLICT_ATTRIBUTE:
            return existing.entry_id if existing else None

        if existing is None:
            payload = {attribute: new_value}
            entry_id = int(
                self._conn.execute(
                    text(
                        """
                        INSERT INTO public.hr_monthly_reference_entries (
                            mrd_id,
                            entity_scope,
                            record_kind,
                            match_key,
                            canonical_hash,
                            effective_payload,
                            last_confirmed_change_id
                        )
                        VALUES (
                            :mrd_id,
                            :entity_scope,
                            :record_kind,
                            :match_key,
                            :canonical_hash,
                            CAST(:effective_payload AS jsonb),
                            :confirmed_change_id
                        )
                        RETURNING entry_id
                        """
                    ),
                    {
                        "mrd_id": mrd_id,
                        "entity_scope": entity_scope,
                        "record_kind": record_kind,
                        "match_key": match_key,
                        "canonical_hash": compute_canonical_hash(
                            record_kind=record_kind,
                            entity_scope=entity_scope,
                            payload=payload,
                        ),
                        "effective_payload": _json(payload),
                        "confirmed_change_id": confirmed_change_id,
                    },
                ).scalar_one()
            )
            self._adjust_entry_count(mrd_id, delta=1)
            return entry_id

        payload = dict(existing.effective_payload)
        payload[attribute] = new_value
        updated = self._conn.execute(
            text(
                """
                UPDATE public.hr_monthly_reference_entries
                SET effective_payload = CAST(:effective_payload AS jsonb),
                    canonical_hash = :canonical_hash,
                    last_confirmed_change_id = :confirmed_change_id,
                    updated_at = NOW(),
                    row_version = row_version + 1
                WHERE entry_id = :entry_id
                  AND row_version = :expected_row_version
                """
            ),
            {
                "entry_id": existing.entry_id,
                "expected_row_version": existing.row_version,
                "effective_payload": _json(payload),
                "canonical_hash": compute_canonical_hash(
                    record_kind=record_kind,
                    entity_scope=entity_scope,
                    payload=payload,
                ),
                "confirmed_change_id": confirmed_change_id,
            },
        ).rowcount
        if updated != 1:
            raise MrdOptimisticConcurrencyConflictError(
                f"Failed to update MRD entry entry_id={existing.entry_id}"
            )
        return existing.entry_id

    def _adjust_entry_count(self, mrd_id: int, *, delta: int) -> None:
        self._conn.execute(
            text(
                """
                UPDATE public.hr_monthly_references
                SET entry_count = GREATEST(0, entry_count + :delta),
                    row_version = row_version + 1
                WHERE mrd_id = :mrd_id
                """
            ),
            {"mrd_id": mrd_id, "delta": delta},
        )


def mrd_tables_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'hr_monthly_references'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _to_version_detail_row(row: Mapping[str, Any]) -> MrdVersionDetailRow:
    forked_from = row.get("forked_from_reference_id")
    return MrdVersionDetailRow(
        mrd_id=int(row["mrd_id"]),
        report_period=row["report_period"],
        version=int(row["version"]),
        status=str(row["status"]),
        row_version=int(row["row_version"]),
        entry_count=int(row["entry_count"]),
        forked_from_reference_id=int(forked_from) if forked_from is not None else None,
    )


def _to_mrd_row(row: Mapping[str, Any]) -> MonthlyReferenceRow:
    return MonthlyReferenceRow(
        mrd_id=int(row["mrd_id"]),
        report_period=row["report_period"],
        version=int(row["version"]),
        status=str(row["status"]),
        row_version=int(row["row_version"]),
        entry_count=int(row["entry_count"]),
    )


def _to_entry_row(row: Mapping[str, Any]) -> MrdEntryRow:
    payload = row["effective_payload"] or {}
    if not isinstance(payload, dict):
        payload = dict(payload)
    return MrdEntryRow(
        entry_id=int(row["entry_id"]),
        mrd_id=int(row["mrd_id"]),
        match_key=str(row["match_key"]),
        entity_scope=str(row["entity_scope"]),
        record_kind=str(row["record_kind"]),
        canonical_hash=str(row["canonical_hash"]),
        effective_payload=dict(payload),
        row_version=int(row["row_version"]),
    )


def _to_difference_row(row: Mapping[str, Any]) -> DetectedDifferenceRecord:
    origin_context = row["origin_context"] or {}
    if not isinstance(origin_context, dict):
        origin_context = dict(origin_context)
    return DetectedDifferenceRecord(
        difference_id=int(row["difference_id"]),
        report_period=row["report_period"],
        mrd_id=int(row["mrd_id"]),
        logical_key=str(row["logical_key"]),
        entity_scope=str(row["entity_scope"]),
        attribute=str(row["attribute"]),
        business_type=str(row["business_type"]),
        lifecycle_status=str(row["lifecycle_status"]),
        difference_origin_code=str(row["difference_origin_code"]),
        origin_context=dict(origin_context),
        old_value=row["old_value"],
        new_value=row["new_value"],
        technical_diff_class=(
            str(row["technical_diff_class"]) if row.get("technical_diff_class") is not None else None
        ),
        row_version=int(row["row_version"]),
        record_kind=str(row["record_kind"]) if row.get("record_kind") is not None else None,
        supersedes_difference_id=(
            int(row["supersedes_difference_id"])
            if row.get("supersedes_difference_id") is not None
            else None
        ),
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
