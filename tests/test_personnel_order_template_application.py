from __future__ import annotations
import os
from contextlib import nullcontext
import pytest
from sqlalchemy import create_engine, text
from app.services import personnel_order_template_application_service as preview_service
from app.services.personnel_orders_editorial import service as editorial_service
from app.services.personnel_order_template_specs import get_personnel_order_template_spec

URL=os.environ.get("TEST_DATABASE_URL", "")
pytestmark=pytest.mark.skipif("corpsite_test" not in URL, reason="requires corpsite_test")
class _Engine:
    def __init__(self,c): self.c=c
    def connect(self): return nullcontext(self.c)
    def begin(self): return nullcontext(self.c)

def test_termination_template_preview_is_real_and_read_only(monkeypatch):
    e=create_engine(URL); c=e.connect(); outer=c.begin()
    try:
        actor=c.execute(text("select user_id from users order by user_id limit 1")).scalar_one()
        employee=c.execute(text("select e.employee_id,e.full_name,p.name as position_name,o.name as org_unit_name from employees e join positions p on p.position_id=e.position_id join org_units o on o.unit_id=e.org_unit_id order by e.employee_id limit 1")).mappings().one()
        values=dict(get_personnel_order_template_spec("TERMINATION").initial_texts)
        template=c.execute(text("""insert into personnel_order_template_versions(item_type_code,version_number,status,title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk)
          values('TERMINATION',880001,'PUBLISHED',:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk) returning template_version_id"""),values).scalar_one()
        order=c.execute(text("insert into personnel_orders(order_type_code,status,source_mode,created_by,basis_summary) values('TERMINATION','DRAFT','MANUAL',:actor,'Основание теста') returning order_id"),{"actor":actor}).scalar_one()
        item=c.execute(text("insert into personnel_order_items(order_id,item_number,item_type_code,employee_id,effective_date,item_status,payload) values(:order,1,'TERMINATION',:employee,'2026-01-15','ACTIVE','{\"termination_reason\":\"по соглашению сторон\",\"unused_leave_days\":\"0\",\"basis\":\"Основание теста\"}'::jsonb) returning item_id"),{"order":order,"employee":employee["employee_id"]}).scalar_one()
        for locale in ("ru","kk"):
            c.execute(text("insert into personnel_order_editorial_blocks(order_id,locale,block_type,generated_text,review_status) values(:id,:l,'title','old title','CURRENT'),(:id,:l,'preamble','old preamble','CURRENT')"),{"id":order,"l":locale})
            c.execute(text("insert into personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text,review_status,basis_required) values(:id,:l,'body','old body','CURRENT',false),(:id,:l,'basis','old basis','CURRENT',false)"),{"id":item,"l":locale})
        tables=("personnel_orders","personnel_order_items","personnel_order_editorial_blocks","personnel_order_item_editorial_blocks","personnel_order_template_applications","employee_events","person_assignments")
        before={t:c.execute(text(f"select to_jsonb(x) from {t} x")).scalars().all() for t in tables}
        monkeypatch.setattr(preview_service,"engine",_Engine(c)); result=preview_service.preview_template_application(order)
        assert result["template"]["template_version_id"]==template and result["template"]["version_number"]==880001
        proposed=" ".join(result["proposed"].values()); assert employee["full_name"] in proposed and "2026-01-15" in proposed and "по соглашению сторон" in proposed and "Основание теста" in proposed and "0" in proposed
        assert employee["position_name"] in result["proposed"]["body_template_ru"] and employee["position_name"] in result["proposed"]["body_template_kk"]
        assert employee["org_unit_name"] in result["proposed"]["body_template_ru"] and employee["org_unit_name"] in result["proposed"]["body_template_kk"]
        assert "{{" not in proposed and "[[" not in proposed
        assert set(result["current"])=={f"{l}:{b}" for l in ("ru","kk") for b in ("title","preamble","body","basis")}
        after={t:c.execute(text(f"select to_jsonb(x) from {t} x")).scalars().all() for t in tables}; assert after==before
    finally: outer.rollback(); c.close(); e.dispose()

def test_termination_template_apply_updates_blocks_and_writes_audit(monkeypatch):
    e=create_engine(URL); c=e.connect(); outer=c.begin()
    try:
        actor=c.execute(text("select user_id from users order by user_id limit 1")).scalar_one(); employee=c.execute(text("select e.employee_id from employees e join positions p on p.position_id=e.position_id join org_units o on o.unit_id=e.org_unit_id order by e.employee_id limit 1")).scalar_one()
        values=dict(get_personnel_order_template_spec("TERMINATION").initial_texts)
        template=c.execute(text("""insert into personnel_order_template_versions(item_type_code,version_number,status,title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk) values('TERMINATION',880101,'PUBLISHED',:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk) returning template_version_id"""),values).scalar_one()
        order=c.execute(text("insert into personnel_orders(order_type_code,status,source_mode,created_by,basis_summary) values('TERMINATION','DRAFT','MANUAL',:a,'Основание apply') returning order_id"),{"a":actor}).scalar_one(); item=c.execute(text("insert into personnel_order_items(order_id,item_number,item_type_code,employee_id,effective_date,item_status,payload) values(:o,1,'TERMINATION',:e,'2026-01-15','ACTIVE','{\"termination_reason\":\"по соглашению\",\"unused_leave_days\":\"0\",\"basis\":\"Основание apply\"}'::jsonb) returning item_id"),{"o":order,"e":employee}).scalar_one()
        for locale in ("ru","kk"):
            c.execute(text("insert into personnel_order_editorial_blocks(order_id,locale,block_type,generated_text,review_status) values(:o,:l,'title','old title','CURRENT'),(:o,:l,'preamble','old preamble','CURRENT')"),{"o":order,"l":locale}); c.execute(text("insert into personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text,review_status,basis_required) values(:i,:l,'body','old body','CURRENT',false),(:i,:l,'basis','old basis','CURRENT',false)"),{"i":item,"l":locale})
        before=c.execute(text("select locale,block_type,generated_text,override_text,revision from personnel_order_editorial_blocks where order_id=:o union all select locale,block_type,generated_text,override_text,revision from personnel_order_item_editorial_blocks where order_item_id=:i order by locale,block_type"),{"o":order,"i":item}).mappings().all()
        adapter=_Engine(c); monkeypatch.setattr(preview_service,"engine",adapter); monkeypatch.setattr(editorial_service,"engine",adapter)
        preview=preview_service.preview_template_application(order); result=preview_service.apply_template_application(order,actor,expected_document_revision=1)
        blocks=c.execute(text("select locale,block_type,generated_text,override_text from personnel_order_editorial_blocks where order_id=:o union all select locale,block_type,generated_text,override_text from personnel_order_item_editorial_blocks where order_item_id=:i"),{"o":order,"i":item}).mappings().all()
        actual={f"{r['locale']}:{r['block_type']}":r for r in blocks}
        for locale in ("ru","kk"):
            assert actual[f"{locale}:title"]["generated_text"]==preview["proposed"][f"title_{locale}"] and actual[f"{locale}:preamble"]["generated_text"]==preview["proposed"][f"preamble_{locale}"]
            assert actual[f"{locale}:body"]["generated_text"]==preview["proposed"][f"body_template_{locale}"] and actual[f"{locale}:basis"]["generated_text"]==preview["proposed"][f"basis_template_{locale}"]
        audit=c.execute(text("select * from personnel_order_template_applications where order_id=:o"),{"o":order}).mappings().one(); assert audit["order_item_id"]==item and audit["template_version_id"]==template and audit["applied_by_user_id"]==actor and audit["applied_at"] and all(audit["template_snapshot"][k]==values[k] for k in values) and sorted(audit["previous_editorial_blocks"],key=lambda x:(x["locale"],x["block_type"]))==[dict(x) for x in before]
        assert "{{" not in str(audit["rendered_snapshot"]) and "[[" not in str(audit["rendered_snapshot"]) and result["order_id"]==order
    finally: outer.rollback(); c.close(); e.dispose()

def test_manual_overrides_require_confirmation_and_remain_editable(monkeypatch):
    e=create_engine(URL); c=e.connect(); outer=c.begin()
    try:
        actor=c.execute(text("select user_id from users order by user_id limit 1")).scalar_one(); employee=c.execute(text("select e.employee_id from employees e join positions p on p.position_id=e.position_id join org_units o on o.unit_id=e.org_unit_id order by e.employee_id limit 1")).scalar_one(); vals=dict(get_personnel_order_template_spec("TERMINATION").initial_texts)
        template=c.execute(text("""insert into personnel_order_template_versions(item_type_code,version_number,status,title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk) values('TERMINATION',880201,'PUBLISHED',:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk) returning template_version_id"""),vals).scalar_one(); order=c.execute(text("insert into personnel_orders(order_type_code,status,source_mode,created_by,basis_summary) values('TERMINATION','DRAFT','MANUAL',:a,'basis') returning order_id"),{"a":actor}).scalar_one(); item=c.execute(text("insert into personnel_order_items(order_id,item_number,item_type_code,employee_id,effective_date,item_status,payload) values(:o,1,'TERMINATION',:e,'2026-01-15','ACTIVE','{\"termination_reason\":\"reason\",\"unused_leave_days\":\"0\",\"basis\":\"basis\"}'::jsonb) returning item_id"),{"o":order,"e":employee}).scalar_one()
        for l in ('ru','kk'):
            c.execute(text("insert into personnel_order_editorial_blocks(order_id,locale,block_type,generated_text,review_status) values(:o,:l,'title','old','CURRENT'),(:o,:l,'preamble','old','CURRENT')"),{"o":order,"l":l}); c.execute(text("insert into personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text,review_status,basis_required) values(:i,:l,'body','old','CURRENT',false),(:i,:l,'basis','old','CURRENT',false)"),{"i":item,"l":l})
        order_block=c.execute(text("select editorial_block_id from personnel_order_editorial_blocks where order_id=:o and locale='ru' and block_type='title'"),{"o":order}).scalar_one(); item_block=c.execute(text("select item_editorial_block_id from personnel_order_item_editorial_blocks where order_item_id=:i and locale='kk' and block_type='body'"),{"i":item}).scalar_one(); c.execute(text("update personnel_order_editorial_blocks set override_text='manual order' where editorial_block_id=:id"),{"id":order_block}); c.execute(text("update personnel_order_item_editorial_blocks set override_text='manual item' where item_editorial_block_id=:id"),{"id":item_block})
        adapter=_Engine(c); monkeypatch.setattr(preview_service,'engine',adapter); monkeypatch.setattr(editorial_service,'engine',adapter); preview=preview_service.preview_template_application(order)
        assert preview['has_overrides'] and {(x['block_id'],x['scope'],x['block_type'],x['language'],x['order_item_id']) for x in preview['override_blocks']}=={(order_block,'ORDER','TITLE','RU',None),(item_block,'ITEM','BODY','KK',item)} and preview['current']['ru:title']['override_text']=='manual order' and preview['current']['kk:body']['override_text']=='manual item'
        with pytest.raises(preview_service.TemplateApplicationError) as exc: preview_service.apply_template_application(order,actor,expected_document_revision=1)
        assert exc.value.conflict and c.execute(text("select count(*) from personnel_order_template_applications where order_id=:o"),{"o":order}).scalar_one()==0
        preview_service.apply_template_application(order,actor,expected_document_revision=1,confirm_replace_overrides=True)
        audit=c.execute(text("select previous_editorial_blocks from personnel_order_template_applications where order_id=:o"),{"o":order}).scalar_one(); assert any(x['override_text']=='manual order' for x in audit) and any(x['override_text']=='manual item' for x in audit)
        state=editorial_service.patch_editorial_block(order,order_block,user_id=actor,override_text='new manual',expected_revision=2); assert state['order_id']==order
    finally: outer.rollback(); c.close(); e.dispose()

def test_reapply_requires_confirmation_and_preserves_first_audit(monkeypatch):
    e=create_engine(URL); c=e.connect(); outer=c.begin()
    try:
        actor=c.execute(text("select user_id from users order by user_id limit 1")).scalar_one(); emp=c.execute(text("select e.employee_id from employees e join positions p on p.position_id=e.position_id join org_units o on o.unit_id=e.org_unit_id limit 1")).scalar_one(); v=dict(get_personnel_order_template_spec('TERMINATION').initial_texts)
        tid=c.execute(text("""insert into personnel_order_template_versions(item_type_code,version_number,status,title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk) values('TERMINATION',880301,'PUBLISHED',:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk) returning template_version_id"""),v).scalar_one(); oid=c.execute(text("insert into personnel_orders(order_type_code,status,source_mode,created_by,basis_summary) values('TERMINATION','DRAFT','MANUAL',:a,'basis') returning order_id"),{'a':actor}).scalar_one(); iid=c.execute(text("insert into personnel_order_items(order_id,item_number,item_type_code,employee_id,effective_date,item_status,payload) values(:o,1,'TERMINATION',:e,'2026-01-15','ACTIVE','{\"termination_reason\":\"reason\",\"unused_leave_days\":\"0\",\"basis\":\"basis\"}'::jsonb) returning item_id"),{'o':oid,'e':emp}).scalar_one()
        for l in ('ru','kk'):
            c.execute(text("insert into personnel_order_editorial_blocks(order_id,locale,block_type,generated_text,review_status) values(:o,:l,'title','old','CURRENT'),(:o,:l,'preamble','old','CURRENT')"),{'o':oid,'l':l}); c.execute(text("insert into personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text,review_status,basis_required) values(:i,:l,'body','old','CURRENT',false),(:i,:l,'basis','old','CURRENT',false)"),{'i':iid,'l':l})
        adapter=_Engine(c); monkeypatch.setattr(preview_service,'engine',adapter); monkeypatch.setattr(editorial_service,'engine',adapter); preview_service.apply_template_application(oid,actor,expected_document_revision=1)
        first=c.execute(text("select to_jsonb(x) from personnel_order_template_applications x where order_id=:o"),{'o':oid}).scalar_one(); first_id=first['template_application_id']; blocks=c.execute(text("select locale,block_type,generated_text,override_text,revision from personnel_order_editorial_blocks where order_id=:o union all select locale,block_type,generated_text,override_text,revision from personnel_order_item_editorial_blocks where order_item_id=:i"),{'o':oid,'i':iid}).mappings().all()
        p=preview_service.preview_template_application(oid); assert p['has_prior_application'] and p['last_application']['application_id']==first_id and p['last_application']['template_version_id']==tid and p['last_application']['template_version_number']==880301 and p['last_application']['applied_by_user_id']==actor and p['last_application']['applied_at']
        with pytest.raises(preview_service.TemplateApplicationError) as exc: preview_service.apply_template_application(oid,actor,expected_document_revision=1)
        assert exc.value.conflict and c.execute(text("select count(*) from personnel_order_template_applications where order_id=:o"),{'o':oid}).scalar_one()==1 and c.execute(text("select to_jsonb(x) from personnel_order_template_applications x where template_application_id=:id"),{'id':first_id}).scalar_one()==first
        preview_service.apply_template_application(oid,actor,expected_document_revision=1,confirm_reapply=True); audits=c.execute(text("select * from personnel_order_template_applications where order_id=:o order by template_application_id"),{'o':oid}).mappings().all(); assert len(audits)==2 and audits[0]['template_application_id']==first_id and audits[1]['template_application_id']>first_id and audits[1]['previous_editorial_blocks']==[dict(x) for x in blocks]
        assert preview_service.preview_template_application(oid)['last_application']['application_id']==audits[1]['template_application_id']
    finally: outer.rollback(); c.close(); e.dispose()

@pytest.mark.parametrize("status,archived", [("REGISTERED",False),("SIGNED",False),("DRAFT",True)])
def test_preview_rejects_non_draft_or_archived_without_writes(monkeypatch,status,archived):
    e=create_engine(URL); c=e.connect(); outer=c.begin()
    try:
        actor=c.execute(text("select user_id from users order by user_id limit 1")).scalar_one(); order=c.execute(text("insert into personnel_orders(order_type_code,status,source_mode,created_by,archived_at) values('TERMINATION',:s,'MANUAL',:a,:archived) returning order_id"),{"s":status,"a":actor,"archived":"now()" if False else None}).scalar_one()
        if archived: c.execute(text("update personnel_orders set archived_at=now() where order_id=:id"),{"id":order})
        before=c.execute(text("select to_jsonb(x) from personnel_orders x where order_id=:id"),{"id":order}).scalar_one(); monkeypatch.setattr(preview_service,"engine",_Engine(c))
        with pytest.raises(preview_service.TemplateApplicationError): preview_service.preview_template_application(order)
        assert c.execute(text("select to_jsonb(x) from personnel_orders x where order_id=:id"),{"id":order}).scalar_one()==before
    finally: outer.rollback(); c.close(); e.dispose()

@pytest.mark.parametrize("case",["no_active","two_active","type_mismatch","no_published"])
def test_preview_rejects_invalid_item_or_template_shape_without_audit(monkeypatch,case):
    e=create_engine(URL); c=e.connect(); outer=c.begin()
    try:
        actor=c.execute(text("select user_id from users order by user_id limit 1")).scalar_one(); employee=c.execute(text("select employee_id from employees order by employee_id limit 1")).scalar_one(); order=c.execute(text("insert into personnel_orders(order_type_code,status,source_mode,created_by) values('TERMINATION','DRAFT','MANUAL',:a) returning order_id"),{"a":actor}).scalar_one()
        if case!="no_active":
            typ="HIRE" if case=="type_mismatch" else "TERMINATION"; count=2 if case=="two_active" else 1
            for n in range(count): c.execute(text("insert into personnel_order_items(order_id,item_number,item_type_code,employee_id,item_status,payload) values(:o,:n,:t,:e,'ACTIVE','{}'::jsonb)"),{"o":order,"n":n+1,"t":typ,"e":employee})
        if case=="type_mismatch":
            vals=dict(get_personnel_order_template_spec("TERMINATION").initial_texts); c.execute(text("insert into personnel_order_template_versions(item_type_code,version_number,status,title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk) values('TERMINATION',870001,'PUBLISHED',:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk)"),vals)
        before=c.execute(text("select count(*) from personnel_order_template_applications")).scalar_one(); monkeypatch.setattr(preview_service,"engine",_Engine(c))
        with pytest.raises(preview_service.TemplateApplicationError): preview_service.preview_template_application(order)
        assert c.execute(text("select count(*) from personnel_order_template_applications")).scalar_one()==before
    finally: outer.rollback(); c.close(); e.dispose()
