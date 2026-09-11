"""WP-PPR-MIG-005E isolated PostgreSQL safe person-status slice."""
from sqlalchemy import event, text
from app.db.engine import engine
from app.services import ppr_migration_status_projection_service as projection
from app.services.ppr_migration_status_report_service import person_cells
from tests.test_ppr_migration_status_projection_postgres import _seed

def test_person_cells_scope_universe_safe_and_bounded():
    conn=engine.connect(); tx=conn.begin(); statements=[]
    def count(*args): statements.append(args[2])
    event.listen(conn,"before_cursor_execute",count)
    try:
        assert conn.execute(text("select current_database()")).scalar_one()=="corpsite_test"
        _actor, person, employee, _row, cohort=_seed(conn,suffix="wp005e-person")
        unit=int(conn.execute(text("insert into org_units(name,code) values('WP005E','wp005e-person') returning unit_id")).scalar_one())
        conn.execute(text("update employees set org_unit_id=:u where employee_id=:e"),{"u":unit,"e":employee})
        universe=projection.ensure_universe(conn,base_cohort_run_id=cohort); projection.rebuild_universe(conn,universe_id=universe)
        statements.clear(); result=person_cells(conn,universe_id=universe,person_id=person,scope={"privileged":False,"scope_unit_ids":[unit]})
        assert result and set(result["cells"])=={"general","education","training"}
        assert len(statements)==1 and not any(x in str(result).lower() for x in ("iin","fingerprint","payload","document"))
        assert person_cells(conn,universe_id=universe,person_id=person,scope={"privileged":False,"scope_unit_ids":[]}) is None
        assert person_cells(conn,universe_id=999999,person_id=person,scope={"privileged":True,"scope_unit_ids":None}) is None
    finally:
        event.remove(conn,"before_cursor_execute",count); tx.rollback(); conn.close()
