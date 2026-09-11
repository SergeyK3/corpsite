"""Local PostgreSQL contracts for stable-code HR control-list targets."""
from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

from app.db.engine import engine
from app.services.department_recoding_service import seed_department_recoding
from tests.alembic_test_helpers import alembic_config, assert_revision_on_chain, get_alembic_heads


REVISION = "ppr005hdept01"
EXPECTED_UNITS = {
    "SCREENING CENTER": "Скрининг центр",
    "FOOD DEPARTMENT": "Пищеблок",
    "PHYSICAL AND TECHNICAL DEPARTMENT": "Отдел физико-технический",
    "ARCHIVE": "Архив",
}
EXPECTED_RECODINGS = {
    "СКРИНИНГ ЦЕНТР": ("SCREENING CENTER", "CLINICAL"),
    "ПИЩЕБЛОК": ("FOOD DEPARTMENT", "ADMINISTRATIVE"),
    "Отдел физико-технический": ("PHYSICAL AND TECHNICAL DEPARTMENT", "ADMINISTRATIVE"),
    "АРХИВ": ("ARCHIVE", "ADMINISTRATIVE"),
    "IT бөлімі": ("IT", "ADMINISTRATIVE"),
    "ОБЩЕБОЛЬНИЧНЫЙ": ("GENERAL", "ADMINISTRATIVE"),
    "ОАХ": ("Amb_chem", "CLINICAL"),
    "КАБИНЕТ ТРАНСФУЗИОЛОГИИ": ("TRANSFUSE", "PARACLINICAL"),
}


def _assert_test_db(conn) -> None:
    assert conn.execute(text("select current_database()")).scalar_one() == "corpsite_test"


def _migration_module():
    path = Path("alembic/versions/ppr005hdept01_hr_control_list_department_targets.py")
    spec = spec_from_file_location("hr_control_list_department_targets", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_resolves_all_parent_group_and_recoding_targets_by_stable_codes():
    cfg = alembic_config()
    assert get_alembic_heads(cfg) == {REVISION}
    conn = engine.connect()
    transaction = conn.begin()
    try:
        _assert_test_db(conn)
        disp = conn.execute(text("select unit_id, parent_unit_id, group_id from public.org_units where code='DISP'")).mappings().one()
        general = conn.execute(text("select group_id from public.org_units where code='GENERAL'")).scalar_one()
        assert general == conn.execute(text("select group_id from public.org_units where code='IT'")).scalar_one()
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            _migration_module().upgrade()
        unit_rows = conn.execute(
            text(
                """
                SELECT child.code, child.name, child.parent_unit_id, child.group_id
                FROM public.org_units child
                JOIN public.org_units parent ON parent.unit_id = child.parent_unit_id
                WHERE child.code = ANY(:codes)
                ORDER BY child.code
                """
            ),
            {"codes": sorted(EXPECTED_UNITS)},
        ).all()
        assert {row[0]: row[1] for row in unit_rows} == EXPECTED_UNITS
        unit_context = {row[0]: tuple(row[2:]) for row in unit_rows}
        assert unit_context["SCREENING CENTER"] == (disp["unit_id"], disp["group_id"])
        for code in set(EXPECTED_UNITS) - {"SCREENING CENTER"}:
            assert unit_context[code] == (disp["parent_unit_id"], general)
        recoding_rows = conn.execute(
            text(
                """
                SELECT recoding.import_department_name, unit.code, recoding.department_group
                FROM public.department_recoding recoding
                JOIN public.org_units unit ON unit.unit_id = recoding.org_unit_id
                WHERE lower(btrim(recoding.import_department_name)) = ANY(:aliases)
                """
            ),
            {"aliases": [name.lower() for name in EXPECTED_RECODINGS]},
        ).all()
        assert {row[0]: tuple(row[1:]) for row in recoding_rows} == EXPECTED_RECODINGS
        # Re-invoking the exact migration function is idempotent and cannot
        # create a second normalized alias or unit.
        with Operations.context(context):
            _migration_module().upgrade()
        assert conn.execute(text("select count(*) from public.org_units where code = any(:codes)"), {"codes": sorted(EXPECTED_UNITS)}).scalar_one() == 4
        assert conn.execute(text("select count(*) from public.department_recoding where lower(btrim(import_department_name)) = any(:aliases)"), {"aliases": [name.lower() for name in EXPECTED_RECODINGS]}).scalar_one() == 8
        with Operations.context(context):
            _migration_module().downgrade()
        assert conn.execute(
            text("select count(*) from public.org_units where code = any(:codes)"),
            {"codes": sorted(EXPECTED_UNITS)},
        ).scalar_one() == 0
        assert conn.execute(
            text("select count(*) from public.department_recoding where lower(btrim(import_department_name)) = any(:aliases)"),
            {"aliases": [name.lower() for name in {"СКРИНИНГ ЦЕНТР", "ПИЩЕБЛОК", "Отдел физико-технический", "ОБЩЕБОЛЬНИЧНЫЙ", "ОАХ"}]},
        ).scalar_one() == 0
        assert conn.execute(
            text("select count(*) from public.department_recoding where lower(btrim(import_department_name)) = any(:aliases) and org_unit_id is null"),
            {"aliases": [name.lower() for name in {"АРХИВ", "IT бөлімі", "КАБИНЕТ ТРАНСФУЗИОЛОГИИ"}]},
        ).scalar_one() == 3
        with Operations.context(context):
            _migration_module().upgrade()
    finally:
        transaction.rollback()
        conn.close()
    assert assert_revision_on_chain(REVISION) == REVISION


def test_code_target_seed_is_exact_and_never_uses_name_substring_fallback(tmp_path: Path):
    token = uuid4().hex[:12]
    code = f"TARGET_{token}"
    canonical_name = f"Canonical {token}"
    alias = f"Alias {token}"
    seed_path = tmp_path / "department_recoding.json"
    seed_path.write_text(
        json.dumps([{"import_department_name": alias, "target_org_unit_code": code}]),
        encoding="utf-8",
    )
    with engine.begin() as conn:
        _assert_test_db(conn)
        group_id = conn.execute(
            text("select group_id from public.deps_group where group_name='Клинические'")
        ).scalar_one()
        conn.execute(
            text("insert into public.org_units(name, code, group_id, is_active) values(:name,:code,:group_id,true)"),
            {"name": canonical_name, "code": code, "group_id": group_id},
        )
        result = seed_department_recoding(conn, seed_path=seed_path)
        assert result["inserted"] == 1
        repeat = seed_department_recoding(conn, seed_path=seed_path)
        assert repeat["updated"] == 1
        row = conn.execute(
            text("select recoding.org_unit_name, unit.code from public.department_recoding recoding join public.org_units unit on unit.unit_id=recoding.org_unit_id where recoding.import_department_name=:alias"),
            {"alias": alias},
        ).one()
        assert row == (canonical_name, code)
        conn.execute(text("delete from public.department_recoding where import_department_name=:alias"), {"alias": alias})
        conn.execute(text("delete from public.org_units where code=:code"), {"code": code})
    missing_path = tmp_path / "missing-target.json"
    missing_path.write_text(json.dumps([{"import_department_name": alias, "target_org_unit_code": "missing"}]), encoding="utf-8")
    with engine.begin() as conn:
        _assert_test_db(conn)
        result = seed_department_recoding(conn, seed_path=missing_path)
        assert result["skipped_unresolved_targets"] == 1
        assert conn.execute(
            text("select count(*) from public.department_recoding where import_department_name=:alias"),
            {"alias": alias},
        ).scalar_one() == 0


def test_upgrade_uses_disp_and_general_ids_not_root_or_group_names():
    """Production-like root/group labels must not affect the code-only contract."""
    conn = engine.connect()
    transaction = conn.begin()
    try:
        _assert_test_db(conn)
        disp = conn.execute(text("select parent_unit_id, group_id from public.org_units where code='DISP'")).mappings().one()
        general_group = conn.execute(text("select group_id from public.org_units where code='GENERAL'")).scalar_one()
        conn.execute(text("update public.org_units set code='mmc_root' where unit_id=:id"), {"id": disp["parent_unit_id"]})
        conn.execute(text("update public.deps_group set group_name='Административно-хозяйственные' where group_id=:id"), {"id": general_group})
        conn.execute(text("update public.deps_group set group_name='Клинические' where group_id=:id"), {"id": disp["group_id"]})
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            _migration_module().upgrade()
        assert conn.execute(
            text("select count(*) from public.org_units where code = any(:codes)"),
            {"codes": sorted(EXPECTED_UNITS)},
        ).scalar_one() == 4
    finally:
        transaction.rollback()
        conn.close()


@pytest.mark.parametrize("mutation", [
    "name='changed'",
    "parent_unit_id=(select parent_unit_id from public.org_units where code='DISP')",
    "group_id=NULL",
    "is_active=false",
])
def test_changed_org_unit_blocks_atomic_downgrade(mutation):
    conn = engine.connect(); transaction = conn.begin()
    try:
        _assert_test_db(conn); context = MigrationContext.configure(conn)
        with Operations.context(context): _migration_module().upgrade()
        conn.execute(text(f"update public.org_units set {mutation} where code='SCREENING CENTER'"))
        with pytest.raises(RuntimeError, match="Cannot downgrade ppr005hdept01"):
            with Operations.context(context): _migration_module().downgrade()
        assert conn.execute(text("select count(*) from public.org_units where code='SCREENING CENTER'")).scalar_one() == 1
        assert conn.execute(text("select count(*) from public.department_recoding where lower(btrim(import_department_name))='скрининг центр'")).scalar_one() == 1
    finally:
        transaction.rollback(); conn.close()


@pytest.mark.parametrize("alias", list(EXPECTED_RECODINGS))
def test_changed_alias_blocks_atomic_downgrade(alias):
    conn = engine.connect(); transaction = conn.begin()
    try:
        _assert_test_db(conn); context = MigrationContext.configure(conn)
        with Operations.context(context): _migration_module().upgrade()
        conn.execute(text("update public.department_recoding set org_unit_name='changed' where lower(btrim(import_department_name))=lower(btrim(:alias))"), {"alias": alias})
        with pytest.raises(RuntimeError, match="Cannot downgrade ppr005hdept01"):
            with Operations.context(context): _migration_module().downgrade()
        assert conn.execute(text("select count(*) from public.org_units where code='ARCHIVE'")).scalar_one() == 1
    finally:
        transaction.rollback(); conn.close()
