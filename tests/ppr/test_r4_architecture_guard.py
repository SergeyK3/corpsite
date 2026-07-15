# tests/ppr/test_r4_architecture_guard.py
"""Architecture guard: production paths must not import R4 section mutation layer."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PRODUCTION_MODULE_PATHS = (
    "app/services/personnel_migration_commit_service.py",
    "app/services/education_migration_plugin.py",
    "app/services/personnel_migration_query_service.py",
    "app/services/personnel_migration_record_events_query_service.py",
    "app/services/personnel_migration_domain_registry.py",
    "app/api/personnel_migration_router.py",
    "app/api/personnel_admin_router.py",
    "app/operational_orders/router.py",
    "app/main.py",
)

FORBIDDEN_R4_SECTION_IMPORTS = (
    "app.ppr.domain.section_handlers",
    "app.ppr.domain.section_commands",
    "app.ppr.domain.section_mutation_context",
    "app.ppr.infrastructure.section_repository",
    "app.ppr.infrastructure.unit_of_work",
    "SectionMutationRepository",
    "SqlAlchemySectionMutationRepository",
    "SectionMutationContext",
    "handle_add_education_record",
    "handle_supersede_education_record",
)


def test_production_paths_do_not_import_r4_section_mutation_layer() -> None:
    violations: list[str] = []
    for rel_path in PRODUCTION_MODULE_PATHS:
        path = REPO_ROOT / rel_path
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_R4_SECTION_IMPORTS:
            if forbidden in content:
                violations.append(f"{rel_path}: {forbidden}")
    assert not violations, "R4 section layer leaked into production:\n" + "\n".join(violations)
