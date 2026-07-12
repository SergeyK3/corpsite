# tests/document_engine/read_services/test_read_service_dependency_rules.py
"""Dependency direction guard for UDE-009 read services."""
from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
READ_SERVICES_ROOT = REPO_ROOT / "app" / "document_engine" / "read_services"
READ_MODELS_ROOT = REPO_ROOT / "app" / "document_engine" / "read_models"

FORBIDDEN_IN_READ_LAYER = (
    "app.db",
    "app.directory",
    "app.api",
    "app.services.personnel",
    "app.services.operational",
    "sqlalchemy",
    "fastapi",
    "pydantic",
)

FORBIDDEN_SUBSTRINGS_IN_READ_LAYER = (
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


def test_read_models_have_no_forbidden_dependencies() -> None:
    modules = list(_iter_modules(READ_MODELS_ROOT, "app.document_engine.read_models"))
    violations = _violations_for_modules(
        modules,
        forbidden_prefixes=FORBIDDEN_IN_READ_LAYER,
        forbidden_substrings=FORBIDDEN_SUBSTRINGS_IN_READ_LAYER,
    )
    assert violations == []


def test_read_services_have_no_forbidden_dependencies() -> None:
    modules = list(_iter_modules(READ_SERVICES_ROOT, "app.document_engine.read_services"))
    assert modules, "read_services package should exist"
    violations = _violations_for_modules(
        modules,
        forbidden_prefixes=FORBIDDEN_IN_READ_LAYER,
        forbidden_substrings=FORBIDDEN_SUBSTRINGS_IN_READ_LAYER,
    )
    assert violations == []


def test_read_services_only_import_adapters_not_personnel_services() -> None:
    modules = list(_iter_modules(READ_SERVICES_ROOT, "app.document_engine.read_services"))
    personnel_service_imports: list[str] = []
    for module_name in modules:
        for imported in sorted(_collect_imports(module_name)):
            if imported.startswith("app.services."):
                personnel_service_imports.append(f"{module_name} imports {imported}")
    assert personnel_service_imports == []


def test_read_services_may_import_document_engine_adapters() -> None:
    modules = list(_iter_modules(READ_SERVICES_ROOT, "app.document_engine.read_services"))
    has_adapter_import = False
    for module_name in modules:
        for imported in sorted(_collect_imports(module_name)):
            if imported.startswith("app.document_engine.adapters"):
                has_adapter_import = True
                break
    assert has_adapter_import, "read services should consume adapters"


def test_personnel_orders_runtime_does_not_import_read_services() -> None:
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
                    if "read_services" in alias.name or "read_models" in alias.name:
                        violations.append(f"{path.name} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if "read_services" in node.module or "read_models" in node.module:
                    violations.append(f"{path.name} imports from {node.module}")
    assert violations == []
