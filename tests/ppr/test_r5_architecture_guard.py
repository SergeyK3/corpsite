# tests/ppr/test_r5_architecture_guard.py
"""Architecture guards for PPR R5 application layer."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_IN_DOMAIN_HANDLERS = (
    "PprEventRepository",
    "app.ppr.application",
    "authorize_mutation",
)

FORBIDDEN_IN_REPOSITORIES = (
    "app.ppr.application.authorization",
    "authorize_mutation",
)

FORBIDDEN_HTTP_IMPORTS = (
    "fastapi",
    "HTTPException",
    "status_code",
    "require_hr_import_admin_or_403",
    "require_.*_or_403",
)


def _iter_ppr_py(root: Path):
    for path in root.rglob("*.py"):
        if path.name == "__init__.py":
            yield path
        elif path.parent.name in {"application", "infrastructure", "domain"}:
            yield path


def test_domain_handlers_do_not_import_application_or_events() -> None:
    path = REPO_ROOT / "app/ppr/domain/section_handlers.py"
    content = path.read_text(encoding="utf-8")
    for forbidden in FORBIDDEN_IN_DOMAIN_HANDLERS:
        assert forbidden not in content


def test_section_repository_no_authorization_imports() -> None:
    path = REPO_ROOT / "app/ppr/infrastructure/section_repository.py"
    content = path.read_text(encoding="utf-8")
    for forbidden in FORBIDDEN_IN_REPOSITORIES:
        assert forbidden not in content


def test_ppr_application_and_infrastructure_no_fastapi() -> None:
    violations: list[str] = []
    for sub in ("application", "infrastructure"):
        base = REPO_ROOT / "app/ppr" / sub
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            if "fastapi" in content.lower():
                violations.append(str(path.relative_to(REPO_ROOT)))
            if "HTTPException" in content:
                violations.append(f"{path.relative_to(REPO_ROOT)}: HTTPException")
            if "require_hr_import_admin_or_403" in content:
                violations.append(f"{path.relative_to(REPO_ROOT)}: require_hr_import_admin_or_403")
    assert not violations, "HTTP semantics in PPR layer:\n" + "\n".join(violations)


def test_pmf_bridge_default_off() -> None:
    from app.ppr.application.config import ppr_pmf_bridge_enabled

    assert ppr_pmf_bridge_enabled() is False


def test_api_routers_do_not_import_domain_handlers_directly() -> None:
    router = REPO_ROOT / "app/api/personnel_migration_router.py"
    content = router.read_text(encoding="utf-8")
    assert "section_handlers" not in content
    assert "PprSectionApplicationService" not in content


def test_commit_service_has_bridge_branch() -> None:
    path = REPO_ROOT / "app/services/personnel_migration_commit_service.py"
    content = path.read_text(encoding="utf-8")
    assert "pmf_ppr_bridge_active" in content
    assert "commit_run_via_ppr_bridge" in content


def test_education_plugin_no_section_mutation_repository() -> None:
    path = REPO_ROOT / "app/services/education_migration_plugin.py"
    content = path.read_text(encoding="utf-8")
    assert "SectionMutationRepository" not in content
    assert "section_handlers" not in content
