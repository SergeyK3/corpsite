"""One real, rollback-only publication lifecycle integration test."""
from __future__ import annotations
import os
from contextlib import nullcontext
import pytest
from sqlalchemy import create_engine, text
from app.services import personnel_order_template_draft_service as service
from app.services.personnel_order_template_manifest import TEXT_FIELDS
from app.services.personnel_order_template_specs import get_personnel_order_template_spec

URL=os.environ.get("TEST_DATABASE_URL", "")
pytestmark=pytest.mark.skipif("corpsite_test" not in URL, reason="requires corpsite_test")

class _TransactionEngine:
    def __init__(self, connection): self.connection=connection
    def begin(self): return nullcontext(self.connection)
    def connect(self): return nullcontext(self.connection)

def _insert(conn, code, version, status, values):
    return conn.execute(text("""insert into personnel_order_template_versions(item_type_code,version_number,status,title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk)
      values(:type,:version,:status,:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk) returning template_version_id"""), {**values,"type":code,"version":version,"status":status}).scalar_one()

def _seed(conn, suffix):
    code="TERMINATION"; values=dict(get_personnel_order_template_spec("TERMINATION").initial_texts); changed=dict(values); changed["title_ru"]+=suffix
    old=_insert(conn,code,900001,"PUBLISHED",values); draft=_insert(conn,code,900002,"DRAFT",changed)
    return code,old,draft,values,changed

def test_publish_and_create_next_draft_uses_published_snapshot(monkeypatch):
    engine=create_engine(URL); conn=engine.connect(); outer=conn.begin()
    try:
        actor=conn.execute(text("select user_id from users order by user_id limit 1")).scalar_one()
        code="TERMINATION"; other="HIRE"; initial=dict(get_personnel_order_template_spec(code).initial_texts)
        changed=dict(initial); changed["title_ru"] += " integration publication"
        def insert(item_type, version, status, values):
            return conn.execute(text("""insert into personnel_order_template_versions(item_type_code,version_number,status,title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk)
              values(:type,:version,:status,:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk) returning template_version_id"""), {**values,"type":item_type,"version":version,"status":status}).scalar_one()
        old=insert(code, 900001, "PUBLISHED", initial)
        draft=insert(code, 900002, "DRAFT", changed)
        other_id=insert(other, 900001, "PUBLISHED", dict(get_personnel_order_template_spec(other).initial_texts))
        monkeypatch.setattr(service,"engine",_TransactionEngine(conn))
        published=service.publish_draft(code, 1, actor)
        rows=conn.execute(text("select template_version_id,status,published_at,published_by_user_id,title_ru from personnel_order_template_versions where template_version_id in (:old,:draft,:other)"),{"old":old,"draft":draft,"other":other_id}).mappings().all(); by_id={r["template_version_id"]:r for r in rows}
        assert by_id[old]["status"]=="ARCHIVED" and by_id[draft]["status"]=="PUBLISHED"
        assert by_id[draft]["published_at"] is not None and by_id[draft]["published_by_user_id"]==actor
        assert by_id[other_id]["status"]=="PUBLISHED"
        assert all(published[field]==changed[field] for field in TEXT_FIELDS)
        assert conn.execute(text("select count(*) from personnel_order_template_versions where item_type_code=:type and status='PUBLISHED'"),{"type":code}).scalar_one()==1
        next_draft=service.create_draft(code,actor)
        assert next_draft["version_number"]==900003 and all(next_draft[field]==changed[field] for field in TEXT_FIELDS)
        assert service.create_draft(code,actor)["template_version_id"]==next_draft["template_version_id"]
    finally:
        outer.rollback(); conn.close(); engine.dispose()

def test_publish_rejects_stale_revision_without_changes(monkeypatch):
    engine=create_engine(URL); conn=engine.connect(); outer=conn.begin()
    try:
        actor=conn.execute(text("select user_id from users order by user_id limit 1")).scalar_one(); code,old,draft,before_old,before_draft=_seed(conn,"STALE")
        monkeypatch.setattr(service,"engine",_TransactionEngine(conn))
        with pytest.raises(service.TemplateDraftError) as exc: service.publish_draft(code,99,actor)
        assert exc.value.conflict
        rows=conn.execute(text("select status,published_at,published_by_user_id,title_ru from personnel_order_template_versions where template_version_id in (:old,:draft) order by template_version_id"),{"old":old,"draft":draft}).mappings().all()
        assert rows[0]["status"]=="PUBLISHED" and rows[1]["status"]=="DRAFT" and rows[1]["published_at"] is None and rows[1]["published_by_user_id"] is None
        assert rows[0]["title_ru"]==before_old["title_ru"] and rows[1]["title_ru"]==before_draft["title_ru"]
    finally: outer.rollback(); conn.close(); engine.dispose()

def test_save_flow_rejects_published_snapshot(monkeypatch):
    engine=create_engine(URL); conn=engine.connect(); outer=conn.begin()
    try:
        actor=conn.execute(text("select user_id from users order by user_id limit 1")).scalar_one(); code,_,draft,_,changed=_seed(conn,"SAVE")
        monkeypatch.setattr(service,"engine",_TransactionEngine(conn)); published=service.publish_draft(code,1,actor)
        modified=dict(changed); modified["title_ru"]="must not save"
        with pytest.raises(service.TemplateDraftError): service.save_draft(code,published["revision"],modified,actor)
        row=conn.execute(text("select revision,title_ru from personnel_order_template_versions where template_version_id=:id"),{"id":draft}).mappings().one()
        assert row["revision"]==published["revision"] and row["title_ru"]==changed["title_ru"]
    finally: outer.rollback(); conn.close(); engine.dispose()

def test_publish_rolls_back_when_database_failpoint_rejects_draft(monkeypatch):
    engine=create_engine(URL); conn=engine.connect(); outer=conn.begin()
    try:
        actor=conn.execute(text("select user_id from users order by user_id limit 1")).scalar_one(); code,old,draft,_,_=_seed(conn,"FAIL")
        conn.execute(text("""create function public.test_publish_failpoint() returns trigger as $$ begin if new.template_version_id=:id and new.status='PUBLISHED' then raise exception 'test failpoint'; end if; return new; end $$ language plpgsql"""),{"id":draft})
        conn.execute(text("create trigger test_publish_failpoint before update on personnel_order_template_versions for each row execute function public.test_publish_failpoint()"))
        monkeypatch.setattr(service,"engine",_TransactionEngine(conn))
        with pytest.raises(Exception):
            with conn.begin_nested(): service.publish_draft(code,1,actor)
        rows=conn.execute(text("select template_version_id,status,published_at from personnel_order_template_versions where template_version_id in (:old,:draft)"),{"old":old,"draft":draft}).mappings().all(); state={r["template_version_id"]:r for r in rows}
        assert state[old]["status"]=="PUBLISHED" and state[draft]["status"]=="DRAFT" and state[draft]["published_at"] is None
    finally: outer.rollback(); conn.close(); engine.dispose()
