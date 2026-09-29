"""Real PostgreSQL DDL contract for pojson014; never runs outside corpsite_test."""
from __future__ import annotations
import os
import uuid
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

REVISION="pojson014"; PARENT="pojson013"
URL=os.environ.get("TEST_DATABASE_URL", "")
pytestmark=pytest.mark.skipif("corpsite_test" not in URL, reason="requires TEST_DATABASE_URL=corpsite_test")

def cfg():
    c=Config(str(Path(__file__).parents[1]/"alembic.ini")); c.set_main_option("sqlalchemy.url",URL); return c

@pytest.fixture(scope="module", autouse=True)
def migrated():
    command.downgrade(cfg(), PARENT); command.upgrade(cfg(), REVISION)
    yield
    command.downgrade(cfg(), PARENT); command.upgrade(cfg(), REVISION)

@pytest.fixture
def db():
    e=create_engine(URL)
    c=e.connect(); outer=c.begin()
    try: yield c
    finally: outer.rollback(); c.close()

def objects(db):
    return set(db.execute(text("select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relname in ('personnel_order_template_applications','uq_personnel_order_template_versions_one_published') union select tgname from pg_trigger where not tgisinternal union select proname from pg_proc join pg_namespace n on n.oid=pronamespace where n.nspname='public'" )).scalars())

def ins_template(db, code, status="DRAFT"):
    return db.execute(text("""insert into personnel_order_template_versions(item_type_code,version_number,status,title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk) values(:c,(select coalesce(max(version_number),0)+1 from personnel_order_template_versions where item_type_code=:c),:s,'ru','kk','ru','kk','ru','kk','ru','kk') returning template_version_id"""),{"c":code,"s":status}).scalar_one()

def code(prefix): return f"SQL.MIG.{prefix}.{uuid.uuid4().hex}"

def test_upgrade_objects_and_published_guards(db):
    cols=set(db.execute(text("select column_name from information_schema.columns where table_schema='public' and table_name='personnel_order_template_versions'")).scalars())
    assert {"published_at","published_by_user_id"} <= cols
    names=objects(db); assert {"personnel_order_template_applications","uq_personnel_order_template_versions_one_published","trg_guard_published_personnel_order_template","guard_published_personnel_order_template","trg_guard_personnel_order_template_application_append_only","guard_personnel_order_template_application_append_only"} <= names
    tid=ins_template(db,code("TEST"),"PUBLISHED")
    with pytest.raises(Exception):
        with db.begin_nested(): db.execute(text("update personnel_order_template_versions set title_ru='changed' where template_version_id=:id"),{"id":tid})

def test_unique_published_and_archive_transition(db):
    unique=code("UNIQUE"); a=ins_template(db,unique,"PUBLISHED")
    with pytest.raises(Exception):
        with db.begin_nested(): ins_template(db,unique,"PUBLISHED")
    db.execute(text("update personnel_order_template_versions set status='ARCHIVED',updated_at=now() where template_version_id=:id"),{"id":a})
    assert ins_template(db,code("OTHER"),"PUBLISHED")

def test_published_rejects_all_protected_columns_and_allows_only_archive(db):
    tid=ins_template(db,code("IMMUTABLE"),"PUBLISHED")
    changes=(
        "revision=revision+1", "published_at=now()", "published_by_user_id=NULL",
        "version_number=version_number+10", "item_type_code='SQL.MIG.RENAMED'", "basis_template_ru='changed'",
    )
    for change in changes:
        with pytest.raises(Exception):
            with db.begin_nested(): db.execute(text(f"update personnel_order_template_versions set {change} where template_version_id=:id"),{"id":tid})
    db.execute(text("update personnel_order_template_versions set status='ARCHIVED',updated_at=now() where template_version_id=:id"),{"id":tid})
    row=db.execute(text("select status,revision,basis_template_ru from personnel_order_template_versions where template_version_id=:id"),{"id":tid}).mappings().one()
    assert row["status"]=="ARCHIVED" and row["revision"]==1 and row["basis_template_ru"]=="ru"

def test_application_audit_is_insert_only_with_real_foreign_keys(db):
    actor=db.execute(text("select user_id from users order by user_id limit 1")).scalar_one()
    template=ins_template(db,code("AUDIT"),"PUBLISHED")
    order=db.execute(text("""insert into personnel_orders(order_type_code,status,source_mode,created_by)
        values('TERMINATION','DRAFT','MANUAL',:actor) returning order_id"""),{"actor":actor}).scalar_one()
    item=db.execute(text("""insert into personnel_order_items(order_id,item_number,item_type_code,item_status)
        values(:order,1,'TERMINATION','ACTIVE') returning item_id"""),{"order":order}).scalar_one()
    app=db.execute(text("""insert into personnel_order_template_applications(order_id,order_item_id,template_version_id,template_snapshot,rendered_snapshot,previous_editorial_blocks,applied_by_user_id)
        values(:order,:item,:template,cast(:template_snapshot as jsonb),cast(:rendered_snapshot as jsonb),'[]'::jsonb,:actor) returning template_application_id"""),{"order":order,"item":item,"template":template,"actor":actor,"template_snapshot":"{\"x\":1}","rendered_snapshot":"{\"ru\":\"ok\"}"}).scalar_one()
    saved=db.execute(text("select template_snapshot,rendered_snapshot,previous_editorial_blocks from personnel_order_template_applications where template_application_id=:id"),{"id":app}).mappings().one()
    assert saved["template_snapshot"]=={"x":1} and saved["rendered_snapshot"]=={"ru":"ok"} and saved["previous_editorial_blocks"]==[]
    for statement in ("update personnel_order_template_applications set rendered_snapshot='{}'::jsonb where template_application_id=:id", "delete from personnel_order_template_applications where template_application_id=:id"):
        with pytest.raises(Exception):
            with db.begin_nested(): db.execute(text(statement),{"id":app})

def test_downgrade_removes_and_reupgrade_restores():
    command.downgrade(cfg(),PARENT)
    e=create_engine(URL)
    with e.connect() as db:
        assert not objects(db) & {"personnel_order_template_applications","uq_personnel_order_template_versions_one_published","trg_guard_published_personnel_order_template","guard_published_personnel_order_template","trg_guard_personnel_order_template_application_append_only","guard_personnel_order_template_application_append_only"}
    command.upgrade(cfg(),REVISION)
    with e.connect() as db: assert "personnel_order_template_applications" in objects(db)
