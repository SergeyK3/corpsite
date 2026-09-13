"""WP-PPR-MIG-005C isolated PostgreSQL report-query contracts."""
from __future__ import annotations

import pytest
from sqlalchemy import event, text

from app.db.engine import engine
from app.services import ppr_migration_status_projection_service as projection
from app.services.ppr_migration_status_report_service import ProjectionIntegrityError, list_universes, matrix, person_cells
from tests.test_ppr_migration_status_projection_postgres import _seed


def _tx():
    conn = engine.connect(); tx = conn.begin()
    assert conn.execute(text("select current_database()")).scalar_one() == "corpsite_test"
    return conn, tx


def _fixture(conn):
    a, first, first_employee, _row, base = _seed(conn, suffix="report-a")
    _a, second, second_employee, _row, supplemental = _seed(conn, suffix="report-b")
    unit_a = int(conn.execute(text("insert into org_units(name,code) values('WP005C A','wp005c-a') returning unit_id")).scalar_one())
    unit_b = int(conn.execute(text("insert into org_units(name,code) values('WP005C B','wp005c-b') returning unit_id")).scalar_one())
    conn.execute(text("update employees set org_unit_id=:unit where employee_id=:employee"), {"unit": unit_a, "employee": first_employee})
    conn.execute(text("update employees set org_unit_id=:unit where employee_id=:employee"), {"unit": unit_b, "employee": second_employee})
    conn.execute(text("update persons set full_name='Canonical Alpha', match_key='canonical alpha' where person_id=:p"), {"p": first})
    conn.execute(text("update persons set full_name='Canonical Beta', match_key='canonical beta' where person_id=:p"), {"p": second})
    conn.execute(text("update ppr_stage0_cohort_runs set run_kind='SUPPLEMENTAL', supplemental_of_run_id=:base where stage0_cohort_run_id=:run"), {"base": base, "run": supplemental})
    universe = projection.ensure_universe(conn, base_cohort_run_id=base, supplemental_cohort_run_ids=[supplemental])
    assert projection.rebuild_universe(conn, universe_id=universe) == 20
    conn.execute(text("update ppr_migration_section_status_projection set status_code='ACCEPTED', reason_code='RUN_PARTICIPANT_ACCEPTED' where universe_id=:u and person_id=:p and section_code='general'"), {"u": universe, "p": second})
    return universe, first, second, unit_a, unit_b


def test_universe_visibility_scope_filtering_pagination_and_counts():
    conn, tx = _tx()
    try:
        universe, first, second, unit_a, unit_b = _fixture(conn)
        scoped = {"privileged": False, "scope_unit_ids": [unit_a]}
        assert [x["universe_id"] for x in list_universes(conn, scoped)] == [universe]
        result = matrix(conn, universe_id=universe, scope=scoped, page=1, page_size=50, section=None, status=None, reason=None, org_unit_id=None, q=None)
        assert result and result["total"] == 1 and {x["person_id"] for x in result["items"]} == {first}
        assert tuple(result["items"][0]["cells"]) == projection.SECTIONS
        assert sum(x["count"] for x in result["counts"]) == 10
        assert matrix(conn, universe_id=universe, scope=scoped, page=1, page_size=50, section=None, status=None, reason=None, org_unit_id=None, q="Beta")["total"] == 0
        assert list_universes(conn, {"privileged": False, "scope_unit_ids": []}) == []
        assert matrix(conn, universe_id=universe, scope={"privileged": False, "scope_unit_ids": []}, page=1, page_size=50, section=None, status=None, reason=None, org_unit_id=None, q=None) is None
        assert second not in {x["person_id"] for x in result["items"]}
    finally:
        tx.rollback(); conn.close()


def test_filters_search_safe_payload_and_stable_pagination():
    conn, tx = _tx()
    try:
        universe, first, second, unit_a, unit_b = _fixture(conn)
        scope = {"privileged": True, "scope_unit_ids": None}
        one = matrix(conn, universe_id=universe, scope=scope, page=1, page_size=1, section=None, status=None, reason=None, org_unit_id=None, q=None)
        two = matrix(conn, universe_id=universe, scope=scope, page=2, page_size=1, section=None, status=None, reason=None, org_unit_id=None, q=None)
        assert one["total"] == 2 and one["items"][0]["person_id"] != two["items"][0]["person_id"]
        again = matrix(conn, universe_id=universe, scope=scope, page=1, page_size=1, section=None, status=None, reason=None, org_unit_id=None, q=None)
        assert one["items"][0]["person_id"] == again["items"][0]["person_id"]
        filtered = matrix(conn, universe_id=universe, scope=scope, page=1, page_size=50, section="general", status="ACCEPTED", reason="RUN_PARTICIPANT_ACCEPTED", org_unit_id=unit_b, q="Beta")
        assert filtered["total"] == 1 and filtered["items"][0]["person_id"] == second
        assert tuple(filtered["items"][0]["cells"]) == projection.SECTIONS
        serialized = str(filtered).lower()
        assert not any(secret in serialized for secret in ("iin", "fingerprint", "raw_payload", "document", "normalized_payload"))
        assert matrix(conn, universe_id=999999999, scope=scope, page=1, page_size=50, section=None, status=None, reason=None, org_unit_id=None, q=None) is None
    finally:
        tx.rollback(); conn.close()


def test_report_query_count_is_bounded_for_rows_pagination_and_aggregation():
    conn, tx = _tx(); statements = []
    def count(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "ppr_migration_" in statement: statements.append(statement)
    event.listen(conn, "before_cursor_execute", count)
    try:
        universe, *_ = _fixture(conn)
        statements.clear()
        result = matrix(conn, universe_id=universe, scope={"privileged": True, "scope_unit_ids": None}, page=1, page_size=1, section=None, status=None, reason=None, org_unit_id=None, q=None)
        # Existence/integrity, page, counts and full-set presentation summary
        # are bounded set queries; the latter is required for the ten-section UI.
        assert result and len(statements) == 6
    finally:
        event.remove(conn, "before_cursor_execute", count); tx.rollback(); conn.close()


def test_full_catalog_filters_person_cells_and_missing_cell_is_integrity_error():
    conn, tx = _tx()
    try:
        universe, first, second, _unit_a, _unit_b = _fixture(conn)
        scope = {"privileged": True, "scope_unit_ids": None}
        result = matrix(conn, universe_id=universe, scope=scope, page=1, page_size=50,
                        section="awards", status="NOT_STARTED",
                        reason="SECTION_PROCESSING_NOT_CONNECTED", org_unit_id=None, q=None)
        assert result and result["total"] == 2
        assert all(tuple(item["cells"]) == projection.SECTIONS for item in result["items"])
        assert all(item["cells"]["awards"]["status_code"] == "NOT_STARTED" for item in result["items"])
        person = person_cells(conn, universe_id=universe, person_id=first, scope=scope)
        assert person and tuple(person["cells"]) == projection.SECTIONS
        assert person["cells"]["foreign_languages"]["reason_code"] == "SECTION_PROCESSING_NOT_CONNECTED"
        conn.execute(text("""delete from ppr_migration_section_status_projection
          where universe_id=:u and person_id=:p and section_code='awards'"""), {"u": universe, "p": second})
        with pytest.raises(ProjectionIntegrityError):
            matrix(conn, universe_id=universe, scope=scope, page=1, page_size=50,
                   section=None, status=None, reason=None, org_unit_id=None, q=None)
        with pytest.raises(ProjectionIntegrityError):
            person_cells(conn, universe_id=universe, person_id=second, scope=scope)
    finally:
        tx.rollback(); conn.close()
