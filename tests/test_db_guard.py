# tests/test_db_guard.py
"""Unit tests for pytest database isolation guard (no DB connections)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.db_guard import (
    PytestDatabaseGuardError,
    enforce_pytest_database_isolation,
    is_test_database_name,
    normalize_database_url,
    validate_test_database_url,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestNormalizeDatabaseUrl:
    def test_localhost_and_127_0_0_1_are_equivalent(self):
        a = normalize_database_url("postgresql+psycopg2://user:secret@localhost:5432/corpsite")
        b = normalize_database_url("postgresql://user:other@127.0.0.1:5432/corpsite")
        assert a.identity_key() == b.identity_key()

    def test_driver_and_query_params_do_not_affect_identity(self):
        a = normalize_database_url("postgresql+psycopg2://user:pass@127.0.0.1:5432/corpsite_test?sslmode=disable")
        b = normalize_database_url("postgresql://user:pass@127.0.0.1:5432/corpsite_test")
        assert a.identity_key() == b.identity_key()

    def test_default_postgres_port(self):
        target = normalize_database_url("postgresql://user:pass@127.0.0.1/corpsite_test")
        assert target.port == 5432


class TestIsTestDatabaseName:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("corpsite_test", True),
            ("corpsite-test", True),
            ("corpsite", False),
            ("test_corpsite", False),
        ],
    )
    def test_suffix_rules(self, name: str, expected: bool):
        assert is_test_database_name(name) is expected


class TestValidateTestDatabaseUrl:
    def test_missing_test_url(self):
        with pytest.raises(PytestDatabaseGuardError, match="TEST_DATABASE_URL is required"):
            validate_test_database_url(test_database_url=None)

    def test_same_as_app_url_rejected(self):
        dev = "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite_test"
        test = "postgresql://postgres:other@localhost:5432/corpsite_test"
        with pytest.raises(PytestDatabaseGuardError, match="must not target the same database"):
            validate_test_database_url(test_database_url=test, app_database_url=dev)

    def test_non_test_database_name_rejected(self):
        with pytest.raises(PytestDatabaseGuardError, match="ends with '_test' or '-test'"):
            validate_test_database_url(
                test_database_url="postgresql://postgres:postgres@127.0.0.1:5432/corpsite",
                app_database_url="postgresql://postgres:postgres@127.0.0.1:5432/corpsite_dev",
            )

    def test_valid_test_database_accepted(self):
        target = validate_test_database_url(
            test_database_url="postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite_test",
            app_database_url="postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite",
        )
        assert target.database == "corpsite_test"


class TestEnforcePytestDatabaseIsolation:
    def test_enforce_accepts_corpsite_test(self, monkeypatch):
        monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite",
        )
        monkeypatch.setenv(
            "TEST_DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite_test",
        )
        import tests.db_guard as guard_module

        guard_module._GUARD_APPLIED = False
        guard_module._ENGINE_BOUND = False

        target = enforce_pytest_database_isolation()
        assert target.database == "corpsite_test"


def _run_guard_subprocess(*, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    script = """
import os
import sys
sys.path.insert(0, os.getcwd())
from tests.db_guard import enforce_pytest_database_isolation
try:
    enforce_pytest_database_isolation()
except SystemExit as exc:
    raise SystemExit(exc.code)
print("OK")
"""
    merged = {
        k: v
        for k, v in os.environ.items()
        if k not in {"TEST_DATABASE_URL", "DATABASE_URL", "PYTHONPATH"}
    }
    merged.update(env)
    merged["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )


class TestGuardSubprocessExit:
    def test_missing_test_url_exits_with_error(self):
        result = _run_guard_subprocess(
            env={
                "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/corpsite",
            }
        )
        assert result.returncode == 1
        assert "TEST_DATABASE_URL is required" in result.stderr

    def test_same_database_as_dev_exits_with_error(self):
        url = "postgresql://postgres:postgres@127.0.0.1:5432/corpsite_test"
        result = _run_guard_subprocess(
            env={
                "DATABASE_URL": url,
                "TEST_DATABASE_URL": "postgresql://postgres:secret@localhost:5432/corpsite_test",
            }
        )
        assert result.returncode == 1
        assert "must not target the same database" in result.stderr

    def test_invalid_database_name_exits_with_error(self):
        result = _run_guard_subprocess(
            env={
                "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/corpsite",
                "TEST_DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/corpsite_staging",
            }
        )
        assert result.returncode == 1
        assert "ends with '_test' or '-test'" in result.stderr

    def test_valid_test_database_passes(self):
        result = _run_guard_subprocess(
            env={
                "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/corpsite",
                "TEST_DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/corpsite_test",
            }
        )
        assert result.returncode == 0
        assert "OK" in result.stdout


def _write_isolated_conftest(isolated_dir: Path) -> None:
    isolated_dir.mkdir(parents=True, exist_ok=True)
    (isolated_dir / "conftest.py").write_text(
        """
import os
from pathlib import Path

_probe_dir = os.environ["PYTEST_DB_GUARD_PROBE_DIR"]
_path = Path(_probe_dir)
_path.mkdir(parents=True, exist_ok=True)
(_path / "03_conftest_import_started").write_text("1", encoding="utf-8")
with (_path / "load_order.txt").open("a", encoding="utf-8") as handle:
    handle.write("03_conftest_import_started\\n")

from app.db.engine import engine

(_path / "04_engine_imported_in_conftest").write_text(
    str(engine.url.database or ""),
    encoding="utf-8",
)
with (_path / "load_order.txt").open("a", encoding="utf-8") as handle:
    handle.write("04_engine_imported_in_conftest\\n")
""",
        encoding="utf-8",
    )
    (isolated_dir / "test_probe_noop.py").write_text(
        "def test_probe_noop() -> None:\n    pass\n",
        encoding="utf-8",
    )


def _run_pytest_with_isolated_conftest(
    *,
    env: dict[str, str],
    probe_dir: Path,
    isolated_dir: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    _write_isolated_conftest(isolated_dir)
    merged = {
        k: v
        for k, v in os.environ.items()
        if k not in {"TEST_DATABASE_URL", "DATABASE_URL", "PYTHONPATH", "PYTEST_DB_GUARD_PROBE_DIR"}
    }
    merged.update(env)
    merged["PYTHONPATH"] = str(REPO_ROOT)
    merged["PYTEST_DB_GUARD_PROBE_DIR"] = str(probe_dir)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(isolated_dir / "test_probe_noop.py"),
        "-q",
        "-c",
        str(REPO_ROOT / "pytest.ini"),
        f"--confcutdir={isolated_dir}",
        "--rootdir",
        str(REPO_ROOT),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )


class TestGuardPluginLoadOrder:
    def test_guard_blocks_before_isolated_conftest_imports_engine(self, tmp_path: Path):
        probe_dir = tmp_path / "probe_fail"
        isolated_dir = tmp_path / "isolated_fail"
        result = _run_pytest_with_isolated_conftest(
            env={
                "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/corpsite",
            },
            probe_dir=probe_dir,
            isolated_dir=isolated_dir,
        )
        assert result.returncode == 1
        assert "TEST_DATABASE_URL is required" in result.stderr
        assert (probe_dir / "01_plugin_hook_ran").exists()
        assert not (probe_dir / "02_plugin_bound_engine").exists()
        assert not (probe_dir / "03_conftest_import_started").exists()
        assert not (probe_dir / "04_engine_imported_in_conftest").exists()

    def test_guard_rebinds_engine_before_isolated_conftest(self, tmp_path: Path):
        probe_dir = tmp_path / "probe_ok"
        isolated_dir = tmp_path / "isolated_ok"
        result = _run_pytest_with_isolated_conftest(
            env={
                "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/corpsite",
                "TEST_DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/corpsite_test",
            },
            probe_dir=probe_dir,
            isolated_dir=isolated_dir,
        )
        assert result.returncode == 0, result.stderr
        order = (probe_dir / "load_order.txt").read_text(encoding="utf-8").splitlines()
        assert order == [
            "01_plugin_hook_ran",
            "02_plugin_bound_engine",
            "03_conftest_import_started",
            "04_engine_imported_in_conftest",
        ]
        assert (probe_dir / "02_plugin_bound_engine").read_text(encoding="utf-8").endswith(
            "corpsite_test"
        )
        assert (probe_dir / "04_engine_imported_in_conftest").read_text(encoding="utf-8") == "corpsite_test"

    def test_without_ini_plugin_guard_does_not_run_before_conftest(self, tmp_path: Path):
        probe_dir = tmp_path / "probe_no_plugin"
        isolated_dir = tmp_path / "isolated_no_plugin"
        result = _run_pytest_with_isolated_conftest(
            env={
                "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/corpsite",
            },
            probe_dir=probe_dir,
            isolated_dir=isolated_dir,
            extra_args=["--override-ini=addopts="],
        )
        assert not (probe_dir / "01_plugin_hook_ran").exists()
        assert (probe_dir / "03_conftest_import_started").exists()
        assert (probe_dir / "04_engine_imported_in_conftest").exists()
