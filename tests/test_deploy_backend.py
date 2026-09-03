from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCRIPT = ROOT / "scripts" / "deploy_backend.sh"
HEAD_REVISION = "x7y8z9a0b1c2"


def _bash_executable() -> str:
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        shutil.which("bash"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    pytest.fail("bash is required for deploy_backend.sh tests")


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def _shell_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name == "nt":
        drive = resolved.drive.rstrip(":").lower()
        return f"/{drive}{resolved.as_posix()[2:]}"
    return resolved.as_posix()


def _deploy_fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    repo = tmp_path / "repo"
    deploy_script = repo / "scripts" / "deploy_backend.sh"
    deploy_script.parent.mkdir(parents=True)
    shutil.copy2(SOURCE_SCRIPT, deploy_script)
    deploy_script.chmod(0o755)

    log_path = repo / "calls.log"
    mock_bin = repo / "mock-bin"
    bash_env = repo / "mock-env.sh"
    _write_executable(
        repo / ".venv" / "bin" / "alembic",
        f"""#!/usr/bin/env bash
echo "alembic:$*" >> "$TEST_LOG"
case "$1 $2" in
  "upgrade head") exit "${{MOCK_ALEMBIC_UPGRADE_EXIT:-0}}" ;;
  "heads ") echo "{HEAD_REVISION} (head)" ;;
  "current ") echo "${{MOCK_ALEMBIC_CURRENT:-{HEAD_REVISION}}} (head)" ;;
  *) exit 2 ;;
esac
""",
    )
    _write_executable(
        repo / "scripts" / "ops" / "ensure_port_free.sh",
        """#!/usr/bin/env bash
echo "port-guard:$*" >> "$TEST_LOG"
""",
    )
    _write_executable(
        repo / "scripts" / "ops" / "scheduler_post_deploy_smoke.sh",
        """#!/usr/bin/env bash
echo "scheduler-smoke" >> "$TEST_LOG"
""",
    )
    _write_executable(
        mock_bin / "systemctl",
        """#!/usr/bin/env bash
echo "systemctl:$*" >> "$TEST_LOG"
""",
    )
    _write_executable(mock_bin / "id", "#!/usr/bin/env bash\necho 0\n")
    _write_executable(
        mock_bin / "journalctl",
        """#!/usr/bin/env bash
echo "journalctl:$*" >> "$TEST_LOG"
""",
    )
    _write_executable(
        mock_bin / "curl",
        """#!/usr/bin/env bash
echo "curl:$*" >> "$TEST_LOG"
printf '200'
""",
    )
    _write_executable(
        bash_env,
        """systemctl() { echo "systemctl:$*" >> "$TEST_LOG"; }
id() { echo 0; }
journalctl() { echo "journalctl:$*" >> "$TEST_LOG"; }
curl() { echo "curl:$*" >> "$TEST_LOG"; printf '200'; }
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "BASH_ENV": _shell_path(bash_env),
            "TEST_LOG": _shell_path(log_path),
            "CORPSITE_BACKEND_SERVICE": "test-backend",
            "CORPSITE_BACKEND_HEALTH_URL": "http://127.0.0.1:18000/health",
        }
    )
    return deploy_script, log_path, env


def _run_deploy(script: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_bash_executable(), str(script)],
        cwd=script.parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_deploy_applies_and_verifies_migrations_before_restart(tmp_path: Path) -> None:
    script, log_path, env = _deploy_fixture(tmp_path)

    result = _run_deploy(script, env)

    assert result.returncode == 0, result.stderr
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.index("alembic:upgrade head") < calls.index("systemctl:restart test-backend")
    assert "alembic:heads" in calls
    assert "alembic:current" in calls
    assert "scheduler-smoke" in calls
    assert "deploy backend OK" in result.stdout


def test_deploy_fails_before_restart_when_alembic_upgrade_fails(tmp_path: Path) -> None:
    script, log_path, env = _deploy_fixture(tmp_path)
    env["MOCK_ALEMBIC_UPGRADE_EXIT"] = "7"

    result = _run_deploy(script, env)

    assert result.returncode != 0
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls[0] == "systemctl:cat test-backend"
    assert calls[1] == "alembic:upgrade head"
    assert "systemctl:restart test-backend" not in calls
    assert not any(call.startswith("port-guard:") for call in calls)
    assert "scheduler-smoke" not in calls
    assert "deploy backend OK" not in result.stdout
    assert "alembic upgrade head failed" in result.stderr


def test_deploy_fails_before_restart_when_current_is_not_head(tmp_path: Path) -> None:
    script, log_path, env = _deploy_fixture(tmp_path)
    env["MOCK_ALEMBIC_CURRENT"] = "v5w6x7y8z9a"

    result = _run_deploy(script, env)

    assert result.returncode != 0
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert "alembic:heads" in calls
    assert "alembic:current" in calls
    assert "systemctl:restart test-backend" not in calls
    assert "database revision does not match the single Alembic head" in result.stderr
    assert "deploy backend OK" not in result.stdout
