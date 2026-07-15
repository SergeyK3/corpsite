# tests/ppr/test_pmf_command_id.py
"""Unit tests for deterministic PMF bridge command_id."""
from __future__ import annotations

from app.ppr.application.pmf_command_id import (
    build_pmf_commit_command_id,
    build_pmf_supersede_command_id,
    build_pmf_void_command_id,
)


def test_commit_command_id_deterministic() -> None:
    a = build_pmf_commit_command_id(migration_run_id=10, migration_item_id=20)
    b = build_pmf_commit_command_id(migration_run_id=10, migration_item_id=20)
    c = build_pmf_commit_command_id(migration_run_id=10, migration_item_id=21)
    assert a == b
    assert a != c
    assert a.startswith("ppr-cmd-")


def test_void_and_supersede_distinct() -> None:
    void_id = build_pmf_void_command_id(migration_run_id=1, migration_item_id=2)
    sup_id = build_pmf_supersede_command_id(
        domain_code="education",
        record_table_name="person_education",
        old_record_id=5,
        replacement_identity="abc",
    )
    commit_id = build_pmf_commit_command_id(migration_run_id=1, migration_item_id=2)
    assert void_id != sup_id
    assert void_id != commit_id
