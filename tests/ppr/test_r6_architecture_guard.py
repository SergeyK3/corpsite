# tests/ppr/test_r6_architecture_guard.py
"""Architecture guards for PPR R6 composite query layer."""
from __future__ import annotations

import ast
from dataclasses import is_dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
READ_ROOT = REPO_ROOT / "app/ppr/read"

FORBIDDEN_IN_READ_LAYER = (
    "section_handlers",
    "section_commands",
    "SectionMutationContext",
    "SectionMutationRepository",
    "SqlAlchemySectionMutationRepository",
    "command_service",
    "lifecycle_service",
    "section_service",
    "import_bridge_service",
    "MaterializePpr",
    "materialize_ppr",
    "handle_add_education_record",
    "handle_void",
    "PprCommandEnvelope",
    "CommandIdempotencyRepository",
)

INFRASTRUCTURE_PATHS = (
    REPO_ROOT / "app/ppr/infrastructure/identity_repository.py",
    REPO_ROOT / "app/ppr/infrastructure/person_repository.py",
    REPO_ROOT / "app/ppr/infrastructure/section_repository.py",
    REPO_ROOT / "app/ppr/infrastructure/ppr_repository.py",
    REPO_ROOT / "app/ppr/infrastructure/ppr_event_repository.py",
)


def _read_py_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def test_composite_read_no_handler_imports() -> None:
    violations: list[str] = []
    for path in _read_py_files(READ_ROOT):
        content = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_IN_READ_LAYER:
            if forbidden in content:
                violations.append(f"{path.relative_to(REPO_ROOT)}: {forbidden}")
    assert not violations, "Read layer must not import write/mutation paths:\n" + "\n".join(violations)


def test_composite_read_no_mutation_repository_imports() -> None:
    violations: list[str] = []
    for path in _read_py_files(READ_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "section_mutation" in node.module or node.module.endswith("command_service"):
                    violations.append(f"{path.relative_to(REPO_ROOT)}: from {node.module}")
    assert not violations, "Mutation imports in read layer:\n" + "\n".join(violations)


def test_composite_read_no_application_write_imports() -> None:
    violations: list[str] = []
    write_modules = (
        "app.ppr.application.command_service",
        "app.ppr.application.lifecycle_service",
        "app.ppr.application.section_service",
        "app.ppr.application.import_bridge_service",
    )
    for path in _read_py_files(READ_ROOT):
        content = path.read_text(encoding="utf-8")
        for mod in write_modules:
            if mod in content:
                violations.append(f"{path.relative_to(REPO_ROOT)}: {mod}")
    assert not violations, "Application write imports in read layer:\n" + "\n".join(violations)


def test_repositories_do_not_import_query_service() -> None:
    violations: list[str] = []
    for path in INFRASTRUCTURE_PATHS:
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        if "app.ppr.read" in content or "PprQueryApplicationService" in content:
            violations.append(str(path.relative_to(REPO_ROOT)))
    assert not violations, "Repositories must not import query layer:\n" + "\n".join(violations)


def test_dto_immutable() -> None:
    from app.ppr.read import models

    for name in dir(models):
        obj = getattr(models, name)
        if is_dataclass(obj):
            params = getattr(obj, "__dataclass_params__")
            assert params.frozen is True, f"{name} must be frozen"


def test_query_service_only_imports_identity_resolution_from_application() -> None:
    path = READ_ROOT / "query_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    app_imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.ppr.application")
    ]
    assert app_imports == ["app.ppr.application.identity_resolution"]


def test_read_uow_has_no_mutation_repositories() -> None:
    content = (READ_ROOT / "uow.py").read_text(encoding="utf-8")
    assert "Mutation" not in content
    assert "command_idempotency" not in content
    assert "section_mutations" not in content


def test_orchestrator_never_calls_materialize() -> None:
    content = (READ_ROOT / "orchestrator.py").read_text(encoding="utf-8")
    assert "insert_envelope" not in content
    assert "update_envelope" not in content
    assert "append(" not in content
