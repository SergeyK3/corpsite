# tests/document_engine/test_dependency_rules.py
"""Architectural dependency guard for UDE shared runtime package (UDE-007)."""
from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "app" / "document_engine"
CORE_ROOTS = (
    PACKAGE_ROOT / "contracts",
    PACKAGE_ROOT / "value_objects",
)

FORBIDDEN_PREFIXES = (
    "app.db",
    "app.directory",
    "app.api",
    "app.services.personnel",
    "app.services.operational",
    "sqlalchemy",
    "fastapi",
    "pydantic",
)

FORBIDDEN_SUBSTRINGS = (
    "personnel_orders",
    "personnel_order",
    "operational_orders",
    "operational_order",
)


def _iter_python_modules(package_path: Path, package_name: str):
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


def test_document_engine_core_has_no_forbidden_dependencies() -> None:
    violations: list[str] = []
    for core_root in CORE_ROOTS:
        package_name = "app.document_engine." + core_root.name
        for module_name in _iter_python_modules(core_root, package_name):
            for imported in sorted(_collect_imports(module_name)):
                lowered = imported.lower()
                if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in FORBIDDEN_PREFIXES):
                    violations.append(f"{module_name} imports forbidden module {imported}")
                if any(token in lowered for token in FORBIDDEN_SUBSTRINGS):
                    violations.append(f"{module_name} imports specialization module {imported}")
    assert violations == []


def test_document_engine_import_has_no_side_effects() -> None:
    import app.document_engine  # noqa: F401

    assert app.document_engine.__all__
