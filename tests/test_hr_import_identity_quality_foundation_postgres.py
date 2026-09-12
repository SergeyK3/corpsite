"""PostgreSQL DDL contracts for IQ-2; all direct DDL cycles roll back."""
from __future__ import annotations

from contextlib import contextmanager
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Text, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from app.db.engine import engine
from app.db.models.hr_import import IDENTITY_REVIEW_EVENT_TYPES
from tests.alembic_test_helpers import alembic_config, assert_revision_on_chain, get_alembic_heads

REVISION = "iq2a1b2c3d4"
PARENT = "ppr005hdept01"
FP = "a" * 64
POLICY = "IDENTITY_QUALITY_V1"
_DEFAULT_ACTOR = object()
MATRIX = {
    "SYSTEM_IIN_MISSING": dict(actor_type="SYSTEM", state="UNRESOLVED", reason="IIN_MISSING", original=None, entered=None),
    "SYSTEM_IIN_INVALID_FORMAT": dict(actor_type="SYSTEM", state="UNRESOLVED", reason="IIN_INVALID_FORMAT", original=FP, entered=None),
    "SYSTEM_IIN_UNMATCHED": dict(actor_type="SYSTEM", state="UNRESOLVED", reason="IIN_UNMATCHED", original=FP, entered=None),
    "IIN_CONFIRMED": dict(actor_type="HR", state="UNRESOLVED", reason="IIN_UNMATCHED", original=FP, entered=FP),
    "DEFERRED": dict(actor_type="HR", state="DEFERRED", reason="IIN_DEFERRED", original=FP, entered=None),
}


def _command_config(database_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return cfg


def _assert_disposable_url(url: str) -> tuple[object, str]:
    parsed = make_url(url)
    host = (parsed.host or "").lower()
    name = str(parsed.database or "")
    if not parsed.drivername.startswith("postgresql") or host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("IQ-2 disposable migration tests require loopback PostgreSQL")
    if name != "corpsite_test" and not (name.startswith("test_") or name.startswith("corpsite_iq2_")):
        raise RuntimeError("IQ-2 disposable migration tests require an explicitly test-only source database")
    return parsed, name


@contextmanager
def _iq2_disposable_database():
    """Clone the guarded test DB; all DDL and command API calls target only the clone."""
    source_url = os.environ["TEST_DATABASE_URL"].strip()
    source, _ = _assert_disposable_url(source_url)
    name = f"corpsite_iq2_{uuid4().hex[:16]}_test"
    target = source.set(database=name)
    _assert_disposable_url(target.render_as_string(hide_password=False))
    admin = source.set(database="postgres").render_as_string(hide_password=False)
    admin_engine = create_engine(admin, isolation_level="AUTOCOMMIT")
    target_url = target.render_as_string(hide_password=False)
    target_engine = create_engine(target_url)
    engine.dispose()
    try:
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text(f'CREATE DATABASE "{name}" TEMPLATE "{source.database}"'))
        cfg = _command_config(target_url)
        yield target_url, target_engine, cfg
    finally:
        target_engine.dispose()
        with admin_engine.connect() as admin_conn:
            admin_conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid <> pg_backend_pid()"), {"name": name})
            admin_conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin_engine.dispose()


def _version(conn) -> str:
    return str(conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one())


def _iq2_objects_exist(conn) -> bool:
    return bool(conn.execute(text("SELECT to_regclass('public.hr_import_identity_review_events') IS NOT NULL AND to_regclass('public.hr_import_identity_quality_states') IS NOT NULL")).scalar_one())


def _clear_cloned_local_iq2_ddl(conn) -> None:
    """Normalize only a disposable clone that may carry earlier local characterization DDL."""
    conn.execute(text("DROP TABLE IF EXISTS public.hr_import_identity_quality_states"))
    conn.execute(text("DROP TABLE IF EXISTS public.hr_import_identity_review_events"))
    conn.execute(text("DROP FUNCTION IF EXISTS public.prevent_hr_import_identity_review_event_mutation()"))
    conn.execute(text("DROP FUNCTION IF EXISTS public.assert_hr_import_iq_event_advances_state()"))
    conn.execute(text("DROP FUNCTION IF EXISTS public.assert_hr_import_iq_effective_event()"))
    conn.execute(text("ALTER TABLE public.hr_import_rows DROP CONSTRAINT IF EXISTS uq_hr_import_rows_batch_row"))
    conn.execute(text("ALTER TABLE public.employees DROP CONSTRAINT IF EXISTS uq_employees_employee_person"))


def _command_prepare_parent(target_engine, cfg) -> None:
    """Bring only the disposable clone to the real parent revision without stamping."""
    with target_engine.connect() as conn:
        revision = _version(conn)
    if revision == REVISION:
        # Older local IQ-2 characterization DDL predates the inverse FK. Make the
        # clone compatible with this revision so its real command downgrade can run.
        with target_engine.begin() as conn:
            employee_pair = conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='uq_employees_employee_person')")).scalar_one()
            if not employee_pair:
                conn.execute(text("ALTER TABLE public.employees ADD CONSTRAINT uq_employees_employee_person UNIQUE(employee_id,person_id)"))
            exists = conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='fk_hr_import_iq_event_current_state')")).scalar_one()
            if not exists:
                conn.execute(text("ALTER TABLE public.hr_import_identity_review_events ADD CONSTRAINT fk_hr_import_iq_event_current_state FOREIGN KEY(batch_id,row_id) REFERENCES public.hr_import_identity_quality_states(batch_id,row_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED"))
        command.downgrade(cfg, PARENT)
    elif revision == PARENT:
        with target_engine.begin() as conn:
            _clear_cloned_local_iq2_ddl(conn)
        command.downgrade(cfg, PARENT)
    else:
        raise AssertionError(f"Disposable clone is not on an IQ-2-supported baseline: {revision}")


def _module():
    spec = spec_from_file_location("iq2", Path("alembic/versions/iq2a1b2c3d4_hr_import_identity_quality_foundation.py"))
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _apply(conn, method: str) -> None:
    with Operations.context(MigrationContext.configure(conn)):
        getattr(_module(), method)()


@pytest.fixture
def conn():
    engine.dispose()
    connection = engine.connect()
    transaction = connection.begin()
    try:
        if connection.execute(text("SELECT to_regclass('public.hr_import_identity_review_events')")).scalar_one():
            # The shared local DB can contain the previous uncommitted IQ-2 DDL.
            # Remove only that schema inside this rollback-only test transaction.
            connection.execute(text("DROP TABLE public.hr_import_identity_quality_states"))
            connection.execute(text("DROP TABLE public.hr_import_identity_review_events"))
            connection.execute(text("ALTER TABLE public.hr_import_rows DROP CONSTRAINT uq_hr_import_rows_batch_row"))
            connection.execute(text("ALTER TABLE public.employees DROP CONSTRAINT IF EXISTS uq_employees_employee_person"))
            connection.execute(text("DROP FUNCTION IF EXISTS public.prevent_hr_import_identity_review_event_mutation()"))
            connection.execute(text("DROP FUNCTION IF EXISTS public.assert_hr_import_iq_event_advances_state()"))
            connection.execute(text("DROP FUNCTION IF EXISTS public.assert_hr_import_iq_effective_event()"))
        _apply(connection, "upgrade")
        yield connection
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def _reject(conn, error, fn, match: str | None = None):
    nested = conn.begin_nested()
    try:
        with pytest.raises(error, match=match):
            fn()
    finally:
        nested.rollback()


def _row(conn):
    actor = int(conn.execute(text("select user_id from users order by user_id limit 1")).scalar_one())
    token = uuid4().hex
    batch = int(conn.execute(text("insert into hr_import_batches(source_type,file_name,import_code,imported_by,status) values('HR_CONTROL_LIST',:t,:t,:a,'IN_REVIEW') returning batch_id"), {"t": token, "a": actor}).scalar_one())
    row = int(conn.execute(text("insert into hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload) values(:b,'IQ2',1,'{}','{}') returning row_id"), {"b": batch}).scalar_one())
    return actor, batch, row


def _event(conn, actor, batch, row, *, event_type="IIN_CONFIRMED", state="UNRESOLVED", reason="IIN_UNMATCHED", original=FP, entered=FP, person=None, employee=None, source=FP, actor_type="HR", occurred_at="clock_timestamp()", policy=POLICY, actor_user_override=_DEFAULT_ACTOR):
    return int(conn.execute(text(f"""insert into hr_import_identity_review_events(idempotency_key,batch_id,row_id,event_type,resulting_state,reason_code,actor_type,actor_user_id,occurred_at,person_id,employee_id,original_iin_fingerprint,entered_iin_fingerprint,source_row_fingerprint,before_normalized_payload_fingerprint,after_normalized_payload_fingerprint,row_version,source_version,policy_version)
    values(:k,:b,:r,:t,:s,:reason,:actor_type,:a,{occurred_at},:p,:e,:o,:i,:src,:fp,:fp,1,1,:policy) returning event_id"""), {"k": str(uuid4()), "b": batch, "r": row, "t": event_type, "s": state, "reason": reason, "actor_type": actor_type, "a": (actor if actor_type == "HR" else None) if actor_user_override is _DEFAULT_ACTOR else actor_user_override, "p": person, "e": employee, "o": original, "i": entered, "src": source, "fp": FP, "policy": policy}).scalar_one())


def _state(conn, batch, row, event, *, state="UNRESOLVED", reason="IIN_UNMATCHED", source=FP, person=None, employee=None):
    return conn.execute(text("""insert into hr_import_identity_quality_states(batch_id,row_id,current_event_id,identity_state,reason_code,person_id,employee_id,source_row_fingerprint,normalized_payload_fingerprint,row_version,source_version,policy_version)
    values(:b,:r,:e,:s,:reason,:p,:employee,:src,:fp,1,1,:policy)"""), {"b": batch, "r": row, "e": event, "s": state, "reason": reason, "p": person, "employee": employee, "src": source, "fp": FP, "policy": POLICY})


def test_schema_shape_constraints_indexes_and_single_head(conn):
    assert get_alembic_heads(alembic_config()) == {REVISION}
    assert assert_revision_on_chain(REVISION) == REVISION
    cols = {r[0]: r[1] for r in conn.execute(text("select column_name,is_nullable from information_schema.columns where table_name='hr_import_identity_quality_states'"))}
    assert cols["current_event_id"] == "NO"
    constraints = set(conn.execute(text("select conname from pg_constraint where conrelid='hr_import_identity_quality_states'::regclass")).scalars())
    assert {"fk_hr_import_iq_state_effective_event", "fk_hr_import_iq_state_employee_person", "uq_hr_import_identity_quality_states_batch_row"} <= constraints
    event_constraints = set(conn.execute(text("select conname from pg_constraint where conrelid='hr_import_identity_review_events'::regclass")).scalars())
    assert "fk_hr_import_iq_event_current_state" in event_constraints
    event_columns = {
        row.column_name: (row.is_nullable, row.data_type)
        for row in conn.execute(text("select column_name,is_nullable,data_type from information_schema.columns where table_name='hr_import_identity_review_events'"))
    }
    assert event_columns["actor_type"] == ("NO", "text")
    indexdef = conn.execute(text("select indexdef from pg_indexes where indexname='ix_hr_import_identity_quality_queue'")).scalar_one()
    assert "(batch_id, identity_state, reason_code, row_id)" in indexdef and "WHERE (identity_state = ANY" in indexdef
    event_index = conn.execute(text("select indexdef from pg_indexes where indexname='ix_hr_import_identity_review_events_row_occurred'" )).scalar_one()
    assert "batch_id, row_id, occurred_at DESC, event_id DESC" in event_index
    from app.db.models.hr_import import HrImportIdentityQualityState, HrImportIdentityReviewEvent
    assert isinstance(HrImportIdentityReviewEvent.__table__.c.actor_type.type, Text)
    assert str(next(i for i in HrImportIdentityQualityState.__table__.indexes if i.name == "ix_hr_import_identity_quality_queue").dialect_options["postgresql"]["where"]) == "identity_state IN ('UNRESOLVED', 'DEFERRED')"
    assert [str(c) for c in next(i for i in HrImportIdentityReviewEvent.__table__.indexes if i.name == "ix_hr_import_identity_review_events_row_occurred").expressions][-2:] == ["occurred_at DESC", "event_id DESC"]


def test_effective_event_fingerprint_policy_pair_and_append_only(conn):
    actor, batch, row = _row(conn)
    event = _event(conn, actor, batch, row)
    _state(conn, batch, row, event)
    _reject(conn, IntegrityError, lambda: _state(conn, batch, row, event, source="b" * 64))
    _reject(conn, IntegrityError, lambda: _event(conn, actor, batch, row + 1))
    _reject(conn, IntegrityError, lambda: _event(conn, actor, batch, row, original=None))
    _reject(conn, IntegrityError, lambda: _event(conn, actor, batch, row, entered=None))
    _reject(conn, IntegrityError, lambda: _event(conn, actor, batch, row, original="iin"))
    _reject(conn, IntegrityError, lambda: conn.execute(text("insert into hr_import_identity_review_events(idempotency_key,batch_id,row_id,event_type,resulting_state,reason_code,actor_type,actor_user_id,occurred_at,original_iin_fingerprint,entered_iin_fingerprint,source_row_fingerprint,before_normalized_payload_fingerprint,after_normalized_payload_fingerprint,row_version,source_version,policy_version) values(:k,:b,:r,'IIN_CONFIRMED','UNRESOLVED','IIN_UNMATCHED','HR',:a,clock_timestamp(),:fp,:fp,:fp,:fp,:fp,1,1,'raw-iin')"), {"k": str(uuid4()), "b": batch, "r": row, "a": actor, "fp": FP}))
    _reject(conn, DBAPIError, lambda: conn.execute(text("update hr_import_identity_review_events set policy_version=:p where event_id=:e"), {"p": POLICY, "e": event}), "append-only")
    _reject(conn, DBAPIError, lambda: conn.execute(text("delete from hr_import_identity_review_events where event_id=:e"), {"e": event}), "append-only")


def test_mismatched_canonical_pair_and_stale_event_are_rejected(conn):
    actor, batch, row = _row(conn)
    token = uuid4().hex
    p1 = int(conn.execute(text("insert into persons(full_name,match_key,person_status,source) values(:x,:x,'active','migration') returning person_id"), {"x": "p" + token}).scalar_one())
    p2 = int(conn.execute(text("insert into persons(full_name,match_key,person_status,source) values(:x,:x,'active','migration') returning person_id"), {"x": "q" + token}).scalar_one())
    employee = int(conn.execute(text("insert into employees(full_name,person_id,is_active) values(:x,:p,true) returning employee_id"), {"x": "e" + token, "p": p1}).scalar_one())
    _reject(conn, IntegrityError, lambda: _event(conn, actor, batch, row, event_type="PERSON_EMPLOYEE_LINK_CONFIRMED", state="RESOLVED", reason="IIN_CONFIRMED", person=p2, employee=employee))
    event = _event(conn, actor, batch, row)
    _state(conn, batch, row, event)
    nested = conn.begin_nested()
    try:
        _event(conn, actor, batch, row)
        with pytest.raises(DBAPIError, match="advance current state"):
            conn.execute(text("set constraints all immediate"))
    finally:
        nested.rollback()


def test_effective_event_pair_and_state_delete_are_enforced(conn):
    actor, batch, row = _row(conn)
    token = uuid4().hex
    p1 = int(conn.execute(text("insert into persons(full_name,match_key,person_status,source) values(:x,:x,'active','migration') returning person_id"), {"x": "p1" + token}).scalar_one())
    p2 = int(conn.execute(text("insert into persons(full_name,match_key,person_status,source) values(:x,:x,'active','migration') returning person_id"), {"x": "p2" + token}).scalar_one())
    p3 = int(conn.execute(text("insert into persons(full_name,match_key,person_status,source) values(:x,:x,'active','migration') returning person_id"), {"x": "p3" + token}).scalar_one())
    e1 = int(conn.execute(text("insert into employees(full_name,person_id,is_active) values(:x,:p,true) returning employee_id"), {"x": "e1" + token, "p": p1}).scalar_one())
    e2 = int(conn.execute(text("insert into employees(full_name,person_id,is_active) values(:x,:p,true) returning employee_id"), {"x": "e2" + token, "p": p2}).scalar_one())
    event = _event(conn, actor, batch, row, event_type="PERSON_EMPLOYEE_LINK_CONFIRMED", state="RESOLVED", reason="IIN_CONFIRMED", person=p1, employee=e1)
    _state(conn, batch, row, event, state="RESOLVED", reason="IIN_CONFIRMED", person=p1, employee=e1)
    conn.execute(text("set constraints all immediate"))
    nested = conn.begin_nested()
    try:
        with pytest.raises(DBAPIError, match="materialize the latest effective event"):
            conn.execute(text("update hr_import_identity_quality_states set person_id=:p,employee_id=:e where batch_id=:b and row_id=:r"), {"p": p2, "e": e2, "b": batch, "r": row})
    finally:
        nested.rollback()
    nested = conn.begin_nested()
    try:
        with pytest.raises(IntegrityError, match="fk_hr_import_iq_event_current_state"):
            conn.execute(text("delete from hr_import_identity_quality_states where batch_id=:b and row_id=:r"), {"b": batch, "r": row})
    finally:
        nested.rollback()
    _reject(conn, IntegrityError, lambda: conn.execute(text("update employees set person_id=:p where employee_id=:e"), {"p": p3, "e": e1}), "fk_hr_import_iq_event_employee_person|fk_hr_import_iq_state_employee_person")


def test_historical_row_is_unchanged_and_downgrade_is_guarded(conn):
    # The row exists before the IQ-2 upgrade within this transaction.
    _apply(conn, "downgrade")
    actor, batch, row = _row(conn)
    before = conn.execute(text("select status,total_rows,valid_rows,error_rows,raw_payload,normalized_payload,error_codes,employee_id from hr_import_batches b join hr_import_rows r using(batch_id) where row_id=:r"), {"r": row}).one()
    _apply(conn, "upgrade")
    assert conn.execute(text("select count(*) from hr_import_identity_quality_states where batch_id=:b"), {"b": batch}).scalar_one() == 0
    assert conn.execute(text("select count(*) from hr_import_identity_review_events where batch_id=:b"), {"b": batch}).scalar_one() == 0
    assert conn.execute(text("select status,total_rows,valid_rows,error_rows,raw_payload,normalized_payload,error_codes,employee_id from hr_import_batches b join hr_import_rows r using(batch_id) where row_id=:r"), {"r": row}).one() == before
    event = _event(conn, actor, batch, row)
    _state(conn, batch, row, event)
    nested = conn.begin_nested()
    try:
        with pytest.raises(DBAPIError, match="Cannot downgrade iq2a1b2c3d4") as exc_info:
            _apply(conn, "downgrade")
        sqlstate = getattr(exc_info.value.orig, "sqlstate", None) or getattr(exc_info.value.orig, "pgcode", None)
        assert sqlstate == "P0001"
        assert "identity-quality event or state data exists" in str(exc_info.value.orig)
    finally:
        nested.rollback()
    assert conn.execute(text("select event_id from hr_import_identity_review_events where event_id=:e"), {"e": event}).scalar_one() == event


def test_event_state_order_fingerprint_reason_and_system_matrix(conn):
    actor, batch, row = _row(conn)
    # An event cannot become durable without its materialized current state.
    nested = conn.begin_nested()
    try:
        _event(conn, actor, batch, row)
        with pytest.raises(IntegrityError, match="fk_hr_import_iq_event_current_state"):
            conn.execute(text("set constraints all immediate"))
    finally:
        nested.rollback()
    # event -> state and state -> event are both valid within one transaction.
    event = _event(conn, actor, batch, row)
    _state(conn, batch, row, event)
    conn.execute(text("set constraints all immediate"))
    actor2, batch2, row2 = _row(conn)
    conn.execute(text("set constraints all deferred"))
    pending = int(conn.execute(text("select nextval(pg_get_serial_sequence('hr_import_identity_review_events','event_id'))")).scalar_one())
    _state(conn, batch2, row2, pending)
    event2 = int(conn.execute(text("""insert into hr_import_identity_review_events(event_id,idempotency_key,batch_id,row_id,event_type,resulting_state,reason_code,actor_type,actor_user_id,occurred_at,original_iin_fingerprint,entered_iin_fingerprint,source_row_fingerprint,before_normalized_payload_fingerprint,after_normalized_payload_fingerprint,row_version,source_version,policy_version)
    overriding system value values(:e,:k,:b,:r,'IIN_CONFIRMED','UNRESOLVED','IIN_UNMATCHED','HR',:a,clock_timestamp(),:fp,:fp,:fp,:fp,:fp,1,1,:policy) returning event_id"""), {"e": pending, "k": str(uuid4()), "b": batch2, "r": row2, "a": actor2, "fp": FP, "policy": POLICY}).scalar_one())
    assert event2 == pending
    conn.execute(text("set constraints all immediate"))
    conn.execute(text("set constraints all deferred"))
    for event_type, reason, original in (("SYSTEM_IIN_MISSING", "IIN_MISSING", None), ("SYSTEM_IIN_INVALID_FORMAT", "IIN_INVALID_FORMAT", FP)):
        a, b, r = _row(conn)
        e = _event(conn, a, b, r, event_type=event_type, reason=reason, original=original, entered=None, actor_type="SYSTEM")
        _state(conn, b, r, e, reason=reason)
        conn.execute(text("set constraints all immediate"))
        conn.execute(text("set constraints all deferred"))
    a, b, r = _row(conn)
    _reject(conn, IntegrityError, lambda: _event(conn, None, b, r, actor_type="HR"))
    _reject(conn, IntegrityError, lambda: _event(conn, a, b, r, event_type="DEFERRED", state="DEFERRED", reason="IIN_DEFERRED", entered=FP))


def test_latest_event_tiebreaker_and_new_fingerprint_requires_state_replacement(conn):
    actor, batch, row = _row(conn)
    first = _event(conn, actor, batch, row, occurred_at="TIMESTAMPTZ '2026-01-01 00:00:00+00'")
    _state(conn, batch, row, first)
    second = _event(conn, actor, batch, row, occurred_at="TIMESTAMPTZ '2026-01-01 00:00:00+00'")
    conn.execute(text("update hr_import_identity_quality_states set current_event_id=:e where batch_id=:b and row_id=:r"), {"e": second, "b": batch, "r": row})
    conn.execute(text("set constraints all immediate"))
    nested = conn.begin_nested()
    try:
        with pytest.raises(DBAPIError, match="source fingerprint"):
            _event(conn, actor, batch, row, source="b" * 64)
    finally:
        nested.rollback()


@pytest.mark.parametrize("event_type", sorted(IDENTITY_REVIEW_EVENT_TYPES))
def test_event_matrix_each_type_and_named_negative_constraints(conn, event_type):
    """Every matrix branch has a valid row and independent named CHECK coverage."""
    assert set(IDENTITY_REVIEW_EVENT_TYPES) == set(MATRIX) | {"PERSON_EMPLOYEE_LINK_CONFIRMED"}
    actor, batch, row = _row(conn)
    token = uuid4().hex
    other_person = int(conn.execute(text("insert into persons(full_name,match_key,person_status,source) values(:v,:v,'active','migration') returning person_id"), {"v": "o" + token}).scalar_one())
    other_employee = int(conn.execute(text("insert into employees(full_name,person_id,is_active) values(:v,:p,true) returning employee_id"), {"v": "o" + token, "p": other_person}).scalar_one())
    spec = MATRIX.get(event_type)
    person = employee = None
    if event_type == "PERSON_EMPLOYEE_LINK_CONFIRMED":
        token = uuid4().hex
        person = int(conn.execute(text("insert into persons(full_name,match_key,person_status,source) values(:v,:v,'active','migration') returning person_id"), {"v": token}).scalar_one())
        employee = int(conn.execute(text("insert into employees(full_name,person_id,is_active) values(:v,:p,true) returning employee_id"), {"v": token, "p": person}).scalar_one())
        spec = dict(actor_type="HR", state="RESOLVED", reason="IIN_CONFIRMED", original=FP, entered=FP)
    event = _event(conn, actor, batch, row, event_type=event_type, person=person, employee=employee, **spec)
    _state(conn, batch, row, event, state=spec["state"], reason=spec["reason"], person=person, employee=employee)
    conn.execute(text("set constraints all immediate"))
    conn.execute(text("set constraints all deferred"))
    bad_actor = "HR" if spec["actor_type"] == "SYSTEM" else "SYSTEM"
    changes = [
        {"actor_type": bad_actor},
        {"actor_user_override": actor if spec["actor_type"] == "SYSTEM" else None},
        {"state": "DEFERRED" if spec["state"] != "DEFERRED" else "UNRESOLVED"},
        {"reason": "IIN_DEFERRED" if spec["reason"] != "IIN_DEFERRED" else "IIN_UNMATCHED"},
        {"person": other_person if person is None else None},
        {"employee": other_employee if employee is None else None},
        {"original": FP if spec["original"] is None else None},
        {"entered": FP if spec["entered"] is None else None},
    ]
    if event_type == "DEFERRED":
        changes.pop(6)  # original fingerprint is intentionally optional.
    for change in changes:
        _reject(conn, IntegrityError, lambda change=change: _event(conn, actor, batch, row, **({"event_type": event_type, "person": person, "employee": employee} | spec | change)), "chk_hr_import_iq_event_decision")
    _reject(conn, IntegrityError, lambda: _event(conn, actor, batch, row, event_type=event_type, person=person, employee=employee, **spec, policy="UNSAFE"), "hr_import_identity_review_events_policy_version_check")
    if spec["original"] is not None:
        _reject(conn, IntegrityError, lambda: _event(conn, actor, batch, row, **({"event_type": event_type, "person": person, "employee": employee} | spec | {"original": "A" * 64})), "hr_import_identity_review_events_original_iin_fingerprint_check")
    if spec["entered"] is not None:
        _reject(conn, IntegrityError, lambda: _event(conn, actor, batch, row, **({"event_type": event_type, "person": person, "employee": employee} | spec | {"entered": "A" * 64})), "hr_import_identity_review_events_entered_iin_fingerprint_check")


def test_alembic_command_disposable_iq2_path() -> None:
    """Uses alembic.command, never revision functions, against a unique loopback clone."""
    with _iq2_disposable_database() as (_url, target_engine, cfg):
        _command_prepare_parent(target_engine, cfg)
        with target_engine.connect() as target_conn:
            assert _version(target_conn) == PARENT
            assert not _iq2_objects_exist(target_conn)
        command.downgrade(cfg, PARENT)
        with target_engine.connect() as target_conn:
            assert _version(target_conn) == PARENT
            assert not _iq2_objects_exist(target_conn)
        command.upgrade(cfg, REVISION)
        with target_engine.connect() as target_conn:
            assert _version(target_conn) == REVISION
            assert _iq2_objects_exist(target_conn)
        command.downgrade(cfg, PARENT)
        with target_engine.connect() as target_conn:
            assert _version(target_conn) == PARENT
            assert not _iq2_objects_exist(target_conn)
        command.upgrade(cfg, REVISION)
        with target_engine.connect() as target_conn:
            assert _version(target_conn) == REVISION
            assert _iq2_objects_exist(target_conn)


@pytest.mark.parametrize("kind", ["state", "event"])
def test_command_downgrade_guard_preserves_state_or_event_only_corruption(kind):
    """Only disposable clones manufacture otherwise-impossible one-sided data."""
    with _iq2_disposable_database() as (_url, target_engine, cfg):
        _command_prepare_parent(target_engine, cfg)
        command.upgrade(cfg, REVISION)
        with target_engine.begin() as conn:
            actor, batch, row = _row(conn)
            if kind == "state":
                conn.execute(text("ALTER TABLE hr_import_identity_quality_states DROP CONSTRAINT fk_hr_import_iq_state_effective_event"))
                conn.execute(text("DROP TRIGGER trg_hr_import_iq_state_effective_event ON hr_import_identity_quality_states"))
                _state(conn, batch, row, 999999999)
            else:
                conn.execute(text("ALTER TABLE hr_import_identity_review_events DROP CONSTRAINT fk_hr_import_iq_event_current_state"))
                conn.execute(text("DROP TRIGGER trg_hr_import_iq_event_advances_state ON hr_import_identity_review_events"))
                _event(conn, actor, batch, row)
        with pytest.raises(DBAPIError, match="Cannot downgrade iq2a1b2c3d4"):
            command.downgrade(cfg, PARENT)
        with target_engine.connect() as conn:
            assert _version(conn) == REVISION and _iq2_objects_exist(conn)
            assert int(conn.execute(text(f"select count(*) from hr_import_identity_{'quality_states' if kind == 'state' else 'review_events'}")).scalar_one()) == 1


def test_concurrent_writers_serialize_current_state_and_first_state_creation() -> None:
    """Two independent PostgreSQL transactions cannot commit incompatible state materializations."""
    with _iq2_disposable_database() as (_url, target_engine, cfg):
        _command_prepare_parent(target_engine, cfg)
        command.upgrade(cfg, REVISION)
        with target_engine.begin() as setup:
            actor, batch, row = _row(setup)
            initial = _event(setup, actor, batch, row)
            _state(setup, batch, row, initial)
            _, first_batch, first_row = _row(setup)

        first = target_engine.connect()
        second = target_engine.connect()
        first_tx = first.begin()
        second_tx = second.begin()
        try:
            for connection in (first, second):
                connection.execute(text("SET LOCAL lock_timeout='500ms'"))
                connection.execute(text("SET LOCAL statement_timeout='3s'"))
            winner = _event(first, actor, batch, row)
            first.execute(text("UPDATE hr_import_identity_quality_states SET current_event_id=:event WHERE batch_id=:batch AND row_id=:row"), {"event": winner, "batch": batch, "row": row})
            stale = _event(second, actor, batch, row)
            with pytest.raises(OperationalError, match="lock timeout|canceling statement"):
                second.execute(text("UPDATE hr_import_identity_quality_states SET current_event_id=:event WHERE batch_id=:batch AND row_id=:row"), {"event": stale, "batch": batch, "row": row})
            second_tx.rollback()
            first.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            first_tx.commit()
        finally:
            if second_tx.is_active:
                second_tx.rollback()
            if first_tx.is_active:
                first_tx.rollback()
            first.close()
            second.close()

        with target_engine.connect() as check:
            assert int(check.execute(text("SELECT current_event_id FROM hr_import_identity_quality_states WHERE batch_id=:batch AND row_id=:row"), {"batch": batch, "row": row}).scalar_one()) == winner
            assert int(check.execute(text("SELECT count(*) FROM hr_import_identity_review_events WHERE batch_id=:batch AND row_id=:row"), {"batch": batch, "row": row}).scalar_one()) == 2
            assert not check.execute(text("SELECT EXISTS(SELECT 1 FROM hr_import_identity_review_events WHERE event_id=:event)"), {"event": stale}).scalar_one()
        with target_engine.begin() as retry_conn:
            retry = _event(retry_conn, actor, batch, row)
            retry_conn.execute(text("UPDATE hr_import_identity_quality_states SET current_event_id=:event WHERE batch_id=:batch AND row_id=:row"), {"event": retry, "batch": batch, "row": row})
            retry_conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        with target_engine.connect() as check:
            assert int(check.execute(text("SELECT current_event_id FROM hr_import_identity_quality_states WHERE batch_id=:batch AND row_id=:row"), {"batch": batch, "row": row}).scalar_one()) == retry
            assert int(check.execute(text("SELECT count(*) FROM hr_import_identity_review_events WHERE batch_id=:batch AND row_id=:row"), {"batch": batch, "row": row}).scalar_one()) == 3
            with pytest.raises(IntegrityError, match="fk_hr_import_iq_event_current_state"):
                check.execute(text("DELETE FROM hr_import_identity_quality_states WHERE batch_id=:batch AND row_id=:row"), {"batch": batch, "row": row})

        first = target_engine.connect()
        second = target_engine.connect()
        first_tx = first.begin()
        second_tx = second.begin()
        try:
            for connection in (first, second):
                connection.execute(text("SET LOCAL lock_timeout='500ms'"))
                connection.execute(text("SET LOCAL statement_timeout='3s'"))
            first_event = _event(first, actor, first_batch, first_row)
            _state(first, first_batch, first_row, first_event)
            second_event = _event(second, actor, first_batch, first_row)
            with pytest.raises(OperationalError, match="lock timeout|canceling statement"):
                _state(second, first_batch, first_row, second_event)
            second_tx.rollback()
            first.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            first_tx.commit()
        finally:
            if second_tx.is_active:
                second_tx.rollback()
            if first_tx.is_active:
                first_tx.rollback()
            first.close()
            second.close()

        with target_engine.connect() as check:
            assert int(check.execute(text("SELECT current_event_id FROM hr_import_identity_quality_states WHERE batch_id=:batch AND row_id=:row"), {"batch": first_batch, "row": first_row}).scalar_one()) == first_event
            assert int(check.execute(text("SELECT count(*) FROM hr_import_identity_review_events WHERE batch_id=:batch AND row_id=:row"), {"batch": first_batch, "row": first_row}).scalar_one()) == 1
