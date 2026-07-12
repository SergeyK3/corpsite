# tests/document_engine/write/test_write_dependency_rules.py
"""Dependency direction guard for UDE-012 write runtime."""
from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WRITE_ROOT = REPO_ROOT / "app" / "document_engine" / "write"

FORBIDDEN_IN_WRITE = (
    "app.db",
    "app.directory",
    "app.api",
    "app.services.personnel",
    "app.services.operational",
    "app.document_engine.adapters",
    "sqlalchemy",
    "fastapi",
    "pydantic",
)

FORBIDDEN_SUBSTRINGS_IN_WRITE = (
    "personnel_orders",
    "personnel_order",
    "operational_orders",
    "operational_order",
)


def _iter_modules(package_path: Path, package_name: str):
    if not package_path.exists():
        return
    for module_info in pkgutil.walk_packages([str(package_path)], prefix=f"{package_name}."):
        yield module_info.name


def _collect_imports(module_name: str) -> set[str]:
    module = importlib.import_module(module_name)
    source_path = Path(module.__file__ or "")
    if not source_path.exists():
        return set()
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _violations_for_modules(
    modules: list[str],
    *,
    forbidden_prefixes: tuple[str, ...],
    forbidden_substrings: tuple[str, ...],
) -> list[str]:
    violations: list[str] = []
    for module_name in modules:
        for imported in sorted(_collect_imports(module_name)):
            lowered = imported.lower()
            if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in forbidden_prefixes):
                violations.append(f"{module_name} imports forbidden module {imported}")
            if any(token in lowered for token in forbidden_substrings):
                violations.append(f"{module_name} imports specialization module {imported}")
    return violations


def test_write_runtime_has_no_forbidden_dependencies() -> None:
    modules = list(_iter_modules(WRITE_ROOT, "app.document_engine.write"))
    assert modules, "write package should exist"
    violations = _violations_for_modules(
        modules,
        forbidden_prefixes=FORBIDDEN_IN_WRITE,
        forbidden_substrings=FORBIDDEN_SUBSTRINGS_IN_WRITE,
    )
    assert violations == []


def test_write_runtime_uses_lifecycle_and_editorial_layers() -> None:
    modules = list(_iter_modules(WRITE_ROOT, "app.document_engine.write"))
    has_lifecycle = False
    has_editorial = False
    for module_name in modules:
        for imported in sorted(_collect_imports(module_name)):
            if imported.startswith("app.document_engine.lifecycle"):
                has_lifecycle = True
            if imported.startswith("app.document_engine.editorial"):
                has_editorial = True
    assert has_lifecycle, "write runtime should consume lifecycle layer"
    assert has_editorial, "write runtime should consume editorial layer"


def test_write_runtime_does_not_import_personnel_services() -> None:
    modules = list(_iter_modules(WRITE_ROOT, "app.document_engine.write"))
    service_imports: list[str] = []
    for module_name in modules:
        for imported in sorted(_collect_imports(module_name)):
            if imported.startswith("app.services."):
                service_imports.append(f"{module_name} imports {imported}")
    assert service_imports == []


def test_personnel_orders_runtime_does_not_import_write() -> None:
    personnel_paths = [
        REPO_ROOT / "app" / "services" / "personnel_orders_query_service.py",
        REPO_ROOT / "app" / "services" / "personnel_orders_command_service.py",
        REPO_ROOT / "app" / "services" / "personnel_orders_cancel_service.py",
        REPO_ROOT / "app" / "directory" / "personnel_orders_routes.py",
        REPO_ROOT / "app" / "db" / "models" / "personnel_orders.py",
    ]
    violations: list[str] = []
    for path in personnel_paths:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "document_engine.write" in alias.name:
                        violations.append(f"{path.name} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if "document_engine.write" in node.module:
                    violations.append(f"{path.name} imports from {node.module}")
    assert violations == []
