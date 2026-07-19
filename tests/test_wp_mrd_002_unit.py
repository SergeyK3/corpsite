# tests/test_wp_mrd_002_unit.py
"""Unit tests for WP-MRD-002 reconcile and candidate planning."""
from __future__ import annotations

from datetime import date

import pytest

from app.mrd.domain.comparison_models import ComparisonCandidate
from app.mrd.domain.difference_models import DetectedDifferenceRecord
from app.mrd.domain.logical_key import build_logical_key, candidate_signature
from app.mrd.domain.reconcile import ReconcileActionKind, plan_reconcile
from app.mrd.domain.types import (
    DIFFERENCE_BUSINESS_NEVER_CONFIRMED,
    DIFFERENCE_BUSINESS_PERIOD_CHANGED,
    DIFFERENCE_LIFECYCLE_CONFIRMED,
    DIFFERENCE_LIFECYCLE_DETECTED,
    DIFFERENCE_LIFECYCLE_REJECTED,
    DIFFERENCE_LIFECYCLE_SUPERSEDED,
    ORIGIN_IMPORT_COMPARE,
    TECHNICAL_DIFF_CHANGED,
    TECHNICAL_DIFF_NEW,
)


def _period() -> date:
    return date(2099, 6, 1)


def _candidate(*, attribute: str, new_value: object, old_value: object | None = None) -> ComparisonCandidate:
    return ComparisonCandidate(
        report_period=_period(),
        mrd_id=10,
        entity_scope="emp:1",
        attribute=attribute,
        business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
        technical_diff_class=TECHNICAL_DIFF_CHANGED,
        old_value=old_value,
        new_value=new_value,
        record_kind="roster",
        match_key="emp:1",
        origin_context={"batch_id": 1},
    )


def _difference(
    *,
    difference_id: int,
    logical_key: str,
    lifecycle_status: str,
    old_value: object | None = None,
    new_value: object | None = None,
    row_version: int = 1,
) -> DetectedDifferenceRecord:
    return DetectedDifferenceRecord(
        difference_id=difference_id,
        report_period=_period(),
        mrd_id=10,
        logical_key=logical_key,
        entity_scope="emp:1",
        attribute="position_raw",
        business_type=DIFFERENCE_BUSINESS_PERIOD_CHANGED,
        lifecycle_status=lifecycle_status,
        difference_origin_code=ORIGIN_IMPORT_COMPARE,
        origin_context={"batch_id": 1},
        old_value=old_value,
        new_value=new_value,
        technical_diff_class=TECHNICAL_DIFF_CHANGED,
        row_version=row_version,
        record_kind="roster",
    )


def test_logical_key_format() -> None:
    key = build_logical_key(
        report_period=_period(),
        mrd_id=10,
        entity_scope="emp:1",
        attribute="position_raw",
        record_kind="roster",
    )
    assert key == "2099-06-01|10|emp:1|position_raw|roster"


def test_plan_reconcile_creates_new_candidate() -> None:
    candidate = _candidate(attribute="position_raw", new_value="Senior")
    actions = plan_reconcile(candidates=[candidate], existing=[])
    assert len(actions) == 1
    assert actions[0].kind == ReconcileActionKind.CREATE_DETECTED


def test_plan_reconcile_keeps_same_candidate() -> None:
    candidate = _candidate(attribute="position_raw", old_value="Nurse", new_value="Senior")
    logical_key = candidate.logical_key
    existing = [
        _difference(
            difference_id=1,
            logical_key=logical_key,
            lifecycle_status=DIFFERENCE_LIFECYCLE_DETECTED,
            old_value="Nurse",
            new_value="Senior",
        )
    ]
    actions = plan_reconcile(candidates=[candidate], existing=existing)
    assert actions[0].kind == ReconcileActionKind.KEEP_DETECTED


def test_plan_reconcile_supersedes_changed_candidate() -> None:
    candidate = _candidate(attribute="position_raw", old_value="Nurse", new_value="Chief")
    logical_key = candidate.logical_key
    existing = [
        _difference(
            difference_id=1,
            logical_key=logical_key,
            lifecycle_status=DIFFERENCE_LIFECYCLE_DETECTED,
            old_value="Nurse",
            new_value="Senior",
        )
    ]
    actions = plan_reconcile(candidates=[candidate], existing=existing)
    assert actions[0].kind == ReconcileActionKind.SUPERSEDE_AND_CREATE


def test_plan_reconcile_skips_terminal_confirmed() -> None:
    candidate = _candidate(attribute="position_raw", new_value="Senior")
    logical_key = candidate.logical_key
    existing = [
        _difference(
            difference_id=1,
            logical_key=logical_key,
            lifecycle_status=DIFFERENCE_LIFECYCLE_CONFIRMED,
            old_value="Nurse",
            new_value="Senior",
        )
    ]
    actions = plan_reconcile(candidates=[candidate], existing=existing)
    assert actions[0].kind == ReconcileActionKind.SKIP_TERMINAL


def test_plan_reconcile_supersedes_orphan_detected() -> None:
    logical_key = build_logical_key(
        report_period=_period(),
        mrd_id=10,
        entity_scope="emp:1",
        attribute="position_raw",
        record_kind="roster",
    )
    existing = [
        _difference(
            difference_id=1,
            logical_key=logical_key,
            lifecycle_status=DIFFERENCE_LIFECYCLE_DETECTED,
            old_value="Nurse",
            new_value="Senior",
        )
    ]
    actions = plan_reconcile(candidates=[], existing=existing)
    assert actions[0].kind == ReconcileActionKind.SUPERSEDE_ORPHAN


def test_candidate_signature_stable() -> None:
    sig1 = candidate_signature(old_value="A", new_value="B")
    sig2 = candidate_signature(old_value="A", new_value="B")
    assert sig1 == sig2
