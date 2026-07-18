# tests/test_alembic_test_helpers.py
"""Smoke tests for Alembic test helper graph traversal."""
from __future__ import annotations

from tests.alembic_test_helpers import (
    assert_revision_on_chain,
    get_current_alembic_head,
    revision_is_ancestor,
)


def test_current_head_is_resolvable() -> None:
    head = get_current_alembic_head()
    assert head


def test_wp_cl_012_revision_is_on_current_head_chain() -> None:
    head = assert_revision_on_chain("z5a6b7c8d9e0f1")
    assert head


def test_ancestor_walk_supports_merge_down_revision_tuple(monkeypatch) -> None:
    class FakeRevision:
        def __init__(self, revision: str, down_revision: object) -> None:
            self.revision = revision
            self.down_revision = down_revision

    class FakeScript:
        def get_revision(self, revision_id: str):
            nodes = {
                "head": FakeRevision("head", ("left", "right")),
                "left": FakeRevision("left", "base"),
                "right": FakeRevision("right", "base"),
                "base": FakeRevision("base", None),
            }
            return nodes.get(revision_id)

    monkeypatch.setattr(
        "tests.alembic_test_helpers.ScriptDirectory.from_config",
        lambda _cfg: FakeScript(),
    )
    assert revision_is_ancestor("head", "base")
    assert revision_is_ancestor("head", "left")
    assert revision_is_ancestor("head", "right")
    assert not revision_is_ancestor("head", "missing")
