"""Shared training summary calculations for intake draft and PPR training records."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

TRAINING_WINDOW_YEARS = 5
CERTIFICATE_VALIDITY_YEARS = 5
CERTIFICATE_EXPIRY_LOOKAHEAD_MONTHS = 6
TRAINING_DOCUMENT_TYPE_CERTIFICATE = "certificate"


@dataclass(frozen=True, slots=True)
class TrainingSummaryRecord:
    title: str | None
    completed_at: date | None
    hours: Decimal | None
    document_type: str | None = None
    lifecycle_status: str | None = "ACTIVE"


@dataclass(frozen=True, slots=True)
class ExpiringCertificateSummary:
    title: str
    expires_at: date
    days_remaining: int


def training_window_start(as_of: date) -> date:
    try:
        return as_of.replace(year=as_of.year - TRAINING_WINDOW_YEARS)
    except ValueError:
        return as_of.replace(year=as_of.year - TRAINING_WINDOW_YEARS, day=28)


def add_calendar_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(value.day, last_day))


def parse_iso_date(raw: Any) -> date | None:
    text = str(raw or "").strip()
    if not text or len(text) < 10 or text[4] != "-":
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_training_hours(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    normalized = text.replace(",", ".")
    try:
        value = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None
    if value < 0:
        return None
    return value


def normalize_document_type(raw: Any) -> str | None:
    text = str(raw or "").strip().lower()
    return text or None


def is_active_training_record(record: TrainingSummaryRecord) -> bool:
    status = str(record.lifecycle_status or "active").strip().lower()
    return status == "active"


def is_certificate_record(record: TrainingSummaryRecord) -> bool:
    document_type = normalize_document_type(record.document_type)
    return document_type == TRAINING_DOCUMENT_TYPE_CERTIFICATE


def training_summary_record_from_mapping(raw: Mapping[str, Any]) -> TrainingSummaryRecord:
    metadata = raw.get("metadata")
    document_type = raw.get("document_type")
    if document_type is None and isinstance(metadata, Mapping):
        document_type = metadata.get("document_type")
    return TrainingSummaryRecord(
        title=(str(raw.get("title") or raw.get("course_name") or "").strip() or None),
        completed_at=parse_iso_date(raw.get("completed_at") or raw.get("year_to") or raw.get("year")),
        hours=parse_training_hours(raw.get("hours")),
        document_type=normalize_document_type(document_type),
        lifecycle_status=str(raw.get("lifecycle_status") or "ACTIVE").strip() or "ACTIVE",
    )


def calculate_training_hours_last_5y(
    records: Sequence[TrainingSummaryRecord | Mapping[str, Any]],
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    ref = as_of or date.today()
    window_start = training_window_start(ref)
    total = Decimal("0")
    included_count = 0

    for raw in records:
        record = raw if isinstance(raw, TrainingSummaryRecord) else training_summary_record_from_mapping(raw)
        if not is_active_training_record(record):
            continue
        completed_at = record.completed_at
        if completed_at is None or completed_at < window_start or completed_at > ref:
            continue
        hours = record.hours
        if hours is None:
            continue
        total += hours
        included_count += 1

    normalized_total = int(total) if total == total.to_integral_value() else float(total)
    return {
        "as_of": ref.isoformat(),
        "window_start": window_start.isoformat(),
        "training_hours_last_5y": normalized_total,
        "qualifying_records_count": included_count,
    }


def calculate_expiring_certificates(
    records: Sequence[TrainingSummaryRecord | Mapping[str, Any]],
    *,
    as_of: date | None = None,
) -> list[ExpiringCertificateSummary]:
    ref = as_of or date.today()
    lookahead_end = add_calendar_months(ref, CERTIFICATE_EXPIRY_LOOKAHEAD_MONTHS)
    results: list[ExpiringCertificateSummary] = []

    for raw in records:
        record = raw if isinstance(raw, TrainingSummaryRecord) else training_summary_record_from_mapping(raw)
        if not is_active_training_record(record):
            continue
        if not is_certificate_record(record):
            continue
        title = str(record.title or "").strip()
        completed_at = record.completed_at
        if not title or completed_at is None:
            continue

        expires_at = add_calendar_years(completed_at, CERTIFICATE_VALIDITY_YEARS)
        if expires_at <= ref or expires_at > lookahead_end:
            continue

        days_remaining = (expires_at - ref).days
        if days_remaining <= 0:
            continue

        results.append(
            ExpiringCertificateSummary(
                title=title,
                expires_at=expires_at,
                days_remaining=days_remaining,
            )
        )

    results.sort(key=lambda item: (item.expires_at, item.title.casefold()))
    return results
