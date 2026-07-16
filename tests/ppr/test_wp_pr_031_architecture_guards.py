"""WP-PR-031 architecture guards for PPR-MILITARY (AG-MIL-3…6)."""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.db.models.personnel_migration import (
    MILITARY_RECORD_KIND_REGISTRATION,
    SECTION_SOURCE_TYPE_ENTERED,
)
from app.ppr.application.authorization import AllowAllAuthorizationPort
from app.ppr.application.command_models import (
    COMMAND_TYPE_ACTIVATE_PPR,
    COMMAND_TYPE_CREATE_MILITARY_SERVICE,
    COMMAND_TYPE_MATERIALIZE_PPR,
    PprCommandEnvelope,
)
from app.ppr.application.lifecycle_service import PprLifecycleApplicationService
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.models import HR_RELATIONSHIP_EMPLOYED
from app.ppr.domain.section_models import SECTION_CODE_PPR_MILITARY, SUPPORTED_SECTION_CODES
from app.ppr.read.query_service import PprQueryApplicationService
from app.services.ppr_candidate_service import update_hr_relationship_context_tx
from tests.conftest import table_exists
from tests.ppr.conftest import cleanup_person_graph, insert_person, ppr_db_available, require_ppr_schema

REPO_ROOT = Path(__file__).resolve().parents[2]

PRODUCTION_MODULE_PATHS = (
    "app/services/personnel_migration_commit_service.py",
    "app/services/personnel_migration_query_service.py",
    "app/services/personnel_migration_record_events_query_service.py",
    "app/services/personnel_migration_domain_registry.py",
    "app/api/personnel_migration_router.py",
    "app/api/personnel_admin_router.py",
    "app/operational_orders/router.py",
    "app/main.py",
)

FORBIDDEN_MILITARY_WRITE_REFERENCES = (
    "person_military_service",
    "create_military_service",
    "void_military_service",
    "supersede_military_service",
    "handle_create_military_service_record",
    "handle_void_military_service_record",
    "handle_supersede_military_service_record",
    "COMMAND_TYPE_CREATE_MILITARY_SERVICE",
    "SECTION_CODE_PPR_MILITARY",
)


def test_production_paths_do_not_write_military_service() -> None:
    """AG-MIL-3: employment/order/migration services must not touch military writes."""
    violations: list[str] = []
    for rel_path in PRODUCTION_MODULE_PATHS:
        path = REPO_ROOT / rel_path
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_MILITARY_WRITE_REFERENCES:
            if forbidden in content:
                violations.append(f"{rel_path}: {forbidden}")
    assert not violations, "Military write path leaked into production modules:\n" + "\n".join(violations)


def test_supported_section_codes_includes_military() -> None:
    """AG-MIL-4."""
    assert SECTION_CODE_PPR_MILITARY in SUPPORTED_SECTION_CODES


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_composite_read_has_at_most_one_active_military_record() -> None:
    """AG-MIL-5: composite read exposes 0..1 active military record."""
    require_ppr_schema()
    with engine.begin() as conn:
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")
        person_id = insert_person(conn, full_name=f"WP31 Guard Active {uuid4().hex[:8]}")

    lifecycle = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    lifecycle.materialize_ppr(
        PprCommandEnvelope(
            command_id=f"mat-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="wp31-guard",
            requested_at=datetime.now(UTC),
            payload={},
            person_id=person_id,
        )
    )
    lifecycle.activate_ppr(
        PprCommandEnvelope(
            command_id=f"act-{uuid4().hex}",
            command_type=COMMAND_TYPE_ACTIVATE_PPR,
            actor_id="wp31-guard",
            requested_at=datetime.now(UTC),
            payload={},
            person_id=person_id,
        )
    )

    section = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    section.create_military_service(
        PprCommandEnvelope(
            command_id=f"cre-{uuid4().hex}",
            command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
            actor_id="wp31-guard",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": MILITARY_RECORD_KIND_REGISTRATION,
                "military_rank": "рядовой",
                "source_type": SECTION_SOURCE_TYPE_ENTERED,
            },
            person_id=person_id,
        )
    )

    query = PprQueryApplicationService()
    sections = query.load_sections(person_id)
    assert len(sections[SECTION_CODE_PPR_MILITARY].active) == 1

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_hire_context_change_preserves_military_service_rows() -> None:
    """AG-MIL-6: transitioning to EMPLOYED must not mutate military rows."""
    require_ppr_schema()
    with engine.begin() as conn:
        if not table_exists(conn, "person_military_service"):
            pytest.skip("person_military_service missing — run: alembic upgrade head")
        person_id = insert_person(conn, full_name=f"WP31 Hire Preserve {uuid4().hex[:8]}")

    lifecycle = PprLifecycleApplicationService(authorization=AllowAllAuthorizationPort())
    lifecycle.materialize_ppr(
        PprCommandEnvelope(
            command_id=f"mat-{uuid4().hex}",
            command_type=COMMAND_TYPE_MATERIALIZE_PPR,
            actor_id="wp31-guard",
            requested_at=datetime.now(UTC),
            payload={},
            person_id=person_id,
        )
    )

    section = PprSectionApplicationService(authorization=AllowAllAuthorizationPort())
    section.create_military_service(
        PprCommandEnvelope(
            command_id=f"cre-{uuid4().hex}",
            command_type=COMMAND_TYPE_CREATE_MILITARY_SERVICE,
            actor_id="wp31-guard",
            requested_at=datetime.now(UTC),
            payload={
                "record_kind": MILITARY_RECORD_KIND_REGISTRATION,
                "obligation_status": "liable",
                "military_rank": "рядовой",
                "registered_at": date(2010, 1, 1),
                "source_type": SECTION_SOURCE_TYPE_ENTERED,
            },
            person_id=person_id,
        )
    )

    with engine.begin() as conn:
        count_before = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_military_service
                WHERE person_id = :person_id
                """
            ),
            {"person_id": person_id},
        ).scalar_one()
        update_hr_relationship_context_tx(
            conn,
            person_id=person_id,
            hr_relationship_context=HR_RELATIONSHIP_EMPLOYED,
        )
        count_after = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM public.person_military_service
                WHERE person_id = :person_id
                """
            ),
            {"person_id": person_id},
        ).scalar_one()

    assert int(count_before) == 1
    assert int(count_after) == int(count_before)

    with engine.begin() as conn:
        cleanup_person_graph(conn, person_ids=[person_id], employee_ids=[])


def test_no_update_military_command_registered() -> None:
    """AG-MIL-10 (consolidated in WP-PR-031 guard suite)."""
    from app.ppr.domain import section_commands, section_handlers

    assert not hasattr(section_commands, "UpdateMilitaryServiceRecord")
    assert not hasattr(section_handlers, "handle_update_military_service_record")
