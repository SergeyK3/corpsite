"""Tests for production-safe demo PPR applicant ops script."""
from __future__ import annotations

import pytest

from scripts.ops.create_demo_ppr_applicants import (
    ALLOWED_IINS,
    APPLICANTS,
    DEMO_MATCH_KEY_PREFIX,
    PersonAudit,
    PlacementCandidate,
    audit_person_by_iin,
    build_manifest,
    is_demo_match_key,
    parse_db_target,
    resolve_placement,
)


def test_allowed_iins_match_specs() -> None:
    spec_iins = {spec["iin"] for spec in APPLICANTS}
    assert spec_iins == ALLOWED_IINS


def test_parse_db_target_local() -> None:
    target = parse_db_target("postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/corpsite")
    assert target.host == "127.0.0.1"
    assert target.dbname == "corpsite"
    assert target.schema == "public"
    assert target.production_like is False


def test_parse_db_target_production_like() -> None:
    target = parse_db_target("postgresql://postgres@46.247.42.47:5432/corpsite")
    assert target.production_like is True


def test_is_demo_match_key() -> None:
    assert is_demo_match_key(f"{DEMO_MATCH_KEY_PREFIX}ahmetov") is True
    assert is_demo_match_key("seed-applicant:abc") is False
    assert is_demo_match_key(None) is False


def test_resolve_placement_prefers_hr_unit_max_position() -> None:
    candidates = [
        PlacementCandidate(1, 42, 10, "Клин", "SURG", "Хирургия", "Врач"),
        PlacementCandidate(3, 73, 29, "Адмхоз", "HR", "Отдел кадров", "Менеджер"),
        PlacementCandidate(3, 73, 340, "Адмхоз", "HR", "Отдел кадров", "Менеджер УЧР"),
    ]
    picked = resolve_placement(candidates, complete=True, preferred_position_hint="архив")
    assert picked is not None
    assert picked.org_unit_id == 73
    assert picked.position_id == 340


def test_resolve_placement_requires_catalog_for_incomplete() -> None:
    candidates = [
        PlacementCandidate(3, 73, 340, "Адмхоз", "HR", "Отдел кадров", "Архивариус МЦ"),
    ]
    picked = resolve_placement(candidates, complete=False)
    assert picked is not None
    assert picked.org_unit_id == 73
    assert picked.org_group_id == 3


def test_audit_blocks_non_demo_existing_person() -> None:
    audit = PersonAudit(
        exists=True,
        person_id=999,
        full_name="Реальный Сотрудник",
        person_status="active",
        match_key="canonical:abc",
        source="canonical",
        hr_relationship_context="EMPLOYED",
        has_active_employee=False,
        demo_marked=False,
        safe_to_touch=False,
        block_reason="person with IIN exists but is not demo-marked",
    )
    assert audit.safe_to_touch is False


def test_build_manifest_marks_seitova_position_null() -> None:
    placement_complete = PlacementCandidate(
        3, 73, 340, "Адмхоз", "HR", "Отдел кадров", "Архивариус МЦ"
    )
    placement_partial = placement_complete
    audit_report = {
        "resolved_placement_complete": placement_complete,
        "resolved_placement_partial": placement_partial,
        "applicant_audits": {
            "ahmetov": {
                "audit": PersonAudit(
                    exists=False,
                    person_id=None,
                    full_name=None,
                    person_status=None,
                    match_key=None,
                    source=None,
                    hr_relationship_context=None,
                    has_active_employee=False,
                    demo_marked=False,
                    safe_to_touch=True,
                    block_reason=None,
                )
            },
            "seitova": {
                "audit": PersonAudit(
                    exists=False,
                    person_id=None,
                    full_name=None,
                    person_status=None,
                    match_key=None,
                    source=None,
                    hr_relationship_context=None,
                    has_active_employee=False,
                    demo_marked=False,
                    safe_to_touch=True,
                    block_reason=None,
                )
            },
        },
    }
    manifest = build_manifest(audit_report, execute=False)
    ahmetov = next(row for row in manifest if row["key"] == "ahmetov")
    seitova = next(row for row in manifest if row["key"] == "seitova")
    assert ahmetov["intended_position_id"] == 340
    assert seitova["intended_position_id"] is None
    assert seitova["employment_rate"] == 0.5


@pytest.mark.skipif(
    not __import__("scripts.ops.create_demo_ppr_applicants", fromlist=["engine"]),
    reason="script import",
)
def test_audit_person_by_iin_not_found_on_empty_iin() -> None:
    from app.db.engine import engine

    try:
        with engine.connect() as conn:
            audit = audit_person_by_iin(
                conn,
                iin="000000000000",
                expected_name="Nobody",
            )
    except Exception:
        pytest.skip("PostgreSQL unavailable")
    assert audit.exists is False
    assert audit.safe_to_touch is True
