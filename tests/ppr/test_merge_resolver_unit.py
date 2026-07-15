# tests/ppr/test_merge_resolver_unit.py
"""Unit tests for iterative merge redirect resolver."""
from __future__ import annotations

import pytest

from app.ppr.domain.errors import (
    PprMergeCycleError,
    PprMergeDepthExceededError,
    PprMergeTargetMissingError,
    PprPersonNotFoundError,
)
from app.ppr.domain.identity_models import PERSON_STATUS_ACTIVE, PERSON_STATUS_MERGED, PersonIdentitySnapshot
from app.ppr.infrastructure.merge_resolver import resolve_merge_chain


def _snap(
    person_id: int,
    *,
    status: str = PERSON_STATUS_ACTIVE,
    merged_into: int | None = None,
    match_key: str | None = None,
) -> PersonIdentitySnapshot:
    return PersonIdentitySnapshot(
        person_id=person_id,
        person_status=status,
        merged_into_person_id=merged_into,
        match_key=match_key or f"mk:{person_id}",
        iin=None,
    )


def test_resolve_direct_active_person() -> None:
    store = {10: _snap(10)}
    result = resolve_merge_chain(10, store.get)
    assert result.resolved_person_id == 10
    assert result.merge_redirected is False
    assert result.merge_chain == (10,)


def test_resolve_single_merge_redirect() -> None:
    store = {
        1: _snap(1, status=PERSON_STATUS_MERGED, merged_into=2),
        2: _snap(2),
    }
    result = resolve_merge_chain(1, store.get)
    assert result.resolved_person_id == 2
    assert result.merge_redirected is True
    assert result.merge_chain == (1, 2)


def test_resolve_multi_hop_chain() -> None:
    store = {
        1: _snap(1, status=PERSON_STATUS_MERGED, merged_into=2),
        2: _snap(2, status=PERSON_STATUS_MERGED, merged_into=3),
        3: _snap(3),
    }
    result = resolve_merge_chain(1, store.get)
    assert result.resolved_person_id == 3
    assert result.merge_chain == (1, 2, 3)


def test_resolve_missing_start_person() -> None:
    with pytest.raises(PprPersonNotFoundError):
        resolve_merge_chain(99, {}.get)


def test_resolve_broken_merge_target() -> None:
    store = {1: _snap(1, status=PERSON_STATUS_MERGED, merged_into=2)}
    with pytest.raises(PprMergeTargetMissingError):
        resolve_merge_chain(1, store.get)


def test_resolve_merge_cycle() -> None:
    store = {
        1: _snap(1, status=PERSON_STATUS_MERGED, merged_into=2),
        2: _snap(2, status=PERSON_STATUS_MERGED, merged_into=1),
    }
    with pytest.raises(PprMergeCycleError):
        resolve_merge_chain(1, store.get)


def test_resolve_merge_depth_exceeded() -> None:
    depth = 4
    store: dict[int, PersonIdentitySnapshot] = {}
    for i in range(1, depth + 2):
        store[i] = _snap(i, status=PERSON_STATUS_MERGED, merged_into=i + 1)
    store[depth + 1] = _snap(depth + 1)
    with pytest.raises(PprMergeDepthExceededError):
        resolve_merge_chain(1, store.get, max_depth=depth)


def test_repeated_resolution_deterministic() -> None:
    store = {
        5: _snap(5, status=PERSON_STATUS_MERGED, merged_into=6),
        6: _snap(6),
    }
    first = resolve_merge_chain(5, store.get)
    second = resolve_merge_chain(5, store.get)
    assert first == second
