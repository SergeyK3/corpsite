# tests/pytest_db_guard_plugin.py
"""Early pytest plugin: enforce TEST_DATABASE_URL before conftest and fixtures load."""
from __future__ import annotations

import os
from pathlib import Path


def _write_probe(name: str, content: str = "1") -> None:
    probe_dir = os.environ.get("PYTEST_DB_GUARD_PROBE_DIR")
    if not probe_dir:
        return
    path = Path(probe_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / name).write_text(content, encoding="utf-8")
    order_path = path / "load_order.txt"
    with order_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{name}\n")


def pytest_load_initial_conftests(early_config, parser, args):  # noqa: ARG001
    _write_probe("01_plugin_hook_ran")
    from tests.db_guard import bind_app_engine_to_test_database

    test_url = bind_app_engine_to_test_database()
    _write_probe("02_plugin_bound_engine", test_url)
