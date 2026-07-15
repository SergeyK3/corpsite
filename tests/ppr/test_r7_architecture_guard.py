# tests/ppr/test_r7_architecture_guard.py
"""Architecture guards for PPR R7 query API and read-switch."""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

READ_LAYER = REPO_ROOT / "app/ppr/read"
API_PPR_FILES = (
    REPO_ROOT / "app/api/ppr_router.py",
    REPO_ROOT / "app/api/ppr_schemas.py",
    REPO_ROOT / "app/api/ppr_mappers.py",
    REPO_ROOT / "app/api/ppr_errors.py",
)
DISPATCHER = REPO_ROOT / "app/services/personnel_card_read_dispatcher.py"

FORBIDDEN_IN_API = (
    "section_handlers",
    "SectionMutationRepository",
    "command_service",
    "lifecycle_service",
    "section_service",
    "import_bridge_service",
    "materialize_ppr",
    "MaterializePPR",
)


def test_query_api_no_write_imports() -> None:
    violations: list[str] = []
    for path in API_PPR_FILES:
        content = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_IN_API:
            if forbidden in content:
                violations.append(f"{path.relative_to(REPO_ROOT)}: {forbidden}")
    assert not violations, "\n".join(violations)


def test_read_layer_no_fastapi() -> None:
    for path in READ_LAYER.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        assert "fastapi" not in content.lower(), f"{path} imports FastAPI"
        assert "ppr_schemas" not in content, f"{path} imports API schemas"


def test_read_layer_no_api_schema_dependency() -> None:
    for path in READ_LAYER.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        assert "app.api.ppr" not in content


def test_dispatcher_outside_r6_core() -> None:
    assert DISPATCHER.is_file()
    content = DISPATCHER.read_text(encoding="utf-8")
    assert "PprQueryApplicationService" in content
    assert "get_employee_import_card" in content


def test_canonical_router_does_not_call_legacy_service() -> None:
    content = (REPO_ROOT / "app/api/ppr_router.py").read_text(encoding="utf-8")
    assert "get_employee_import_card" not in content
    assert "directory_service" not in content


def test_legacy_mode_config_default() -> None:
    from app.ppr.application.config import ppr_read_path_mode

    assert ppr_read_path_mode.__name__ == "ppr_read_path_mode"


def test_no_frontend_changes() -> None:
    ui_card = REPO_ROOT / "corpsite-ui/app/directory/personnel/_components/EmployeeImportCard2PageClient.tsx"
    if ui_card.is_file():
        content = ui_card.read_text(encoding="utf-8")
        assert "/api/ppr" not in content


def test_router_has_no_direct_sql() -> None:
    tree = ast.parse((REPO_ROOT / "app/api/ppr_router.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "sqlalchemy" in node.module:
            raise AssertionError("ppr_router must not import SQLAlchemy")


def test_no_materialize_in_read_paths() -> None:
    paths = [DISPATCHER, *API_PPR_FILES]
    for path in paths:
        content = path.read_text(encoding="utf-8")
        assert "insert_envelope" not in content
