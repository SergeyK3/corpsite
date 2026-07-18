"""Shared Alembic characterization helpers for migration tests."""
from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def alembic_config(ini_path: str | None = None) -> Config:
    path = ini_path or str(Path(__file__).resolve().parents[1] / "alembic.ini")
    return Config(path)


def get_alembic_heads(cfg: Config | None = None) -> set[str]:
    script = ScriptDirectory.from_config(cfg or alembic_config())
    return set(script.get_heads())


def get_current_alembic_head(cfg: Config | None = None) -> str:
    heads = get_alembic_heads(cfg)
    if len(heads) != 1:
        raise AssertionError(f"Expected single Alembic head, got {sorted(heads)}")
    return next(iter(heads))


def _down_revision_ids(revision: object) -> tuple[str, ...]:
    down = getattr(revision, "down_revision", None)
    if down is None:
        return ()
    if isinstance(down, (tuple, list)):
        return tuple(str(item) for item in down)
    return (str(down),)


def revision_is_ancestor(revision_id: str, ancestor_id: str, *, cfg: Config | None = None) -> bool:
    script = ScriptDirectory.from_config(cfg or alembic_config())
    current = script.get_revision(revision_id)
    if current is None:
        return False

    queue = [current]
    seen: set[str] = set()
    while queue:
        node = queue.pop(0)
        if node.revision in seen:
            continue
        seen.add(node.revision)
        if node.revision == ancestor_id:
            return True
        queue.extend(
            parent
            for parent_id in _down_revision_ids(node)
            if (parent := script.get_revision(parent_id)) is not None
        )
    return False


def revision_is_ancestor_of_head(revision_id: str, head_revision_id: str, *, cfg: Config | None = None) -> bool:
    return revision_is_ancestor(head_revision_id, revision_id, cfg=cfg)


def assert_revision_on_chain(revision_id: str, *, cfg: Config | None = None) -> str:
    head = get_current_alembic_head(cfg)
    if not revision_is_ancestor_of_head(revision_id, head, cfg=cfg):
        raise AssertionError(f"{revision_id} is not an ancestor of head {head!r}")
    return head
