"""Migration and authoring contract; must run on a dedicated test DB."""
import hashlib
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.db.engine import engine
from app.db.education_program_kind_migration import upgrade,SEED,downgrade
from app.services.education_program_kinds_service import save_entry,list_entries
from app.ppr.domain.section_commands import AddEducationRecord,UpdateEducationRecord,SupersedeEducationRecord,VoidEducationRecord
from app.ppr.domain.section_handlers import handle_add_education_record,handle_update_education_record,handle_supersede_education_record,handle_void_education_record
from app.ppr.domain.errors import SectionValidationError
from app.ppr.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from tests.ppr.conftest import insert_person


def fingerprint(c):
    return hashlib.sha256('\n'.join(c.execute(text('SELECT to_jsonb(t)::text FROM person_education t ORDER BY education_id')).scalars()).encode()).hexdigest()


def test_01_migration_preserves_old_codes_rows_and_history_and_replaces_check():
    assert engine.url.database.startswith('corpsite_program_kinds_') and engine.url.database.endswith('_test')
    with engine.begin() as c:
        p=insert_person(c,full_name='SYNTHETIC Migration Education')
        for i,(code,_,_,_) in enumerate(SEED[:6]):
            c.execute(text("INSERT INTO person_education(person_id,education_kind,institution_name,lifecycle_status,metadata) VALUES(:p,:code,:name,:status,CAST(:meta AS jsonb))"),dict(p=p,code=code,name='SYNTHETIC '+code,status=['active','superseded','voided'][i%3],meta='{"source":"synthetic-original"}'))
        before=fingerprint(c)
        upgrade(c)
        assert fingerprint(c)==before
        rows=c.execute(text('SELECT code,name_ru,name_kk FROM education_program_kinds WHERE code=ANY(:codes) ORDER BY sort_order'),{'codes':[r[0] for r in SEED]}).all()
        assert [r[0] for r in rows]==[r[0] for r in SEED]
        assert rows[-1][1:]==('Аспирантура','Аспирантура')
        constraints=c.execute(text("SELECT conname FROM pg_constraint WHERE conrelid='person_education'::regclass")).scalars().all()
        assert 'chk_person_education_kind' not in constraints
        assert 'fk_person_education_program_kind' in constraints
        with pytest.raises(IntegrityError),c.begin_nested():
            c.execute(text("INSERT INTO person_education(person_id,education_kind) VALUES(:p,'unregistered')"),{'p':p})
        with pytest.raises(IntegrityError),c.begin_nested():
            c.execute(text("DELETE FROM education_program_kinds WHERE code='basic'"))
        with pytest.raises(IntegrityError),c.begin_nested():
            c.execute(text("UPDATE education_program_kinds SET code='renamed' WHERE code='basic'"))
        with pytest.raises(RuntimeError):downgrade(c)


def test_02_dynamic_kind_rename_deactivate_and_legacy_record_correction():
    code='test_'+uuid4().hex[:8]
    new=save_entry(code=code,name_ru='Синтетическая программа',name_kk='Синтетикалық бағдарлама',sort_order=80,actor_user_id=25)
    with engine.begin() as c:p=insert_person(c,full_name='SYNTHETIC Dynamic Education')
    with SqlAlchemyUnitOfWork() as uow:
        result=handle_add_education_record(AddEducationRecord(person_id=p,education_kind=code,institution_name='SYNTHETIC school'),uow)
        record=result.record;uow.commit()
    renamed=save_entry(code=code,name_ru='Исправленное название',name_kk='Түзетілген атау',sort_order=80,actor_user_id=25,expected_revision=new['revision'],is_active=False)
    assert renamed['revision']==2 and not renamed['is_active']
    with pytest.raises(HTTPException) as conflict:
        save_entry(code=code,name_ru='Old',name_kk='Old',sort_order=80,actor_user_id=25,expected_revision=1)
    assert conflict.value.status_code==409
    with SqlAlchemyUnitOfWork() as uow:
        result=handle_update_education_record(UpdateEducationRecord(person_id=p,record_id=record.record_id,expected_updated_at=record.updated_at,institution_name='SYNTHETIC corrected school'),uow)
        updated=result.record;uow.commit()
    with SqlAlchemyUnitOfWork() as uow:
        with pytest.raises(SectionValidationError):handle_add_education_record(AddEducationRecord(person_id=p,education_kind=code),uow)
    with SqlAlchemyUnitOfWork() as uow:
        result=handle_supersede_education_record(SupersedeEducationRecord(person_id=p,record_id=updated.record_id,expected_updated_at=updated.updated_at,replacement=AddEducationRecord(person_id=p,education_kind=code,institution_name='SYNTHETIC final school')),uow)
        replacement=result.record;uow.commit()
    with SqlAlchemyUnitOfWork() as uow:
        handle_void_education_record(VoidEducationRecord(person_id=p,record_id=replacement.record_id,expected_updated_at=replacement.updated_at,reason='SYNTHETIC correction'),uow);uow.commit()
    with engine.begin() as c:
        assert c.execute(text('SELECT count(*) FROM person_education WHERE person_id=:p AND education_kind=:code'),dict(p=p,code=code)).scalar_one()==2
        before=fingerprint(c);upgrade(c);assert before==fingerprint(c)
        assert c.execute(text('SELECT name_ru FROM education_program_kinds WHERE code=:code'),{'code':code}).scalar_one()=='Исправленное название'
        assert c.execute(text('SELECT count(*) FROM education_program_kind_audit WHERE code=:code'),{'code':code}).scalar_one()==2


def test_03_aspirantura_does_not_reinterpret_phd_and_api_keeps_string_codes():
    from app.api.ppr_card_command_router import Education
    from app.api.ppr_self_schemas import SelfEducationRecord
    assert Education(education_kind='aspirantura').education_kind=='aspirantura'
    assert SelfEducationRecord(education_kind='phd').education_kind=='phd'
    with engine.begin() as c:p=insert_person(c,full_name='SYNTHETIC PhD and Aspirantura')
    for code in ('aspirantura','phd'):
        with SqlAlchemyUnitOfWork() as uow:
            result=handle_add_education_record(AddEducationRecord(person_id=p,education_kind=code,institution_name='SYNTHETIC '+code),uow)
            assert result.record.education_kind==code;uow.commit()
    names={r['code']:r for r in list_entries()['items']}
    assert names['phd']['name_ru']=='Докторантура (PhD)'
    assert names['aspirantura']['name_kk']=='Аспирантура'


def test_04_reference_api_authorization_revision_and_no_delete():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth import get_current_user
    from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
    previous=app.dependency_overrides.copy()
    try:
        app.dependency_overrides[get_current_user]=lambda:dict(user_id=25,role_id=SYSTEM_ADMIN_ROLE_ID)
        with TestClient(app) as client:
            path='/api/ppr/education-program-kinds'
            rows=client.get(path).json()
            assert rows['can_manage'] and rows['schema_ready']
            code='api_'+uuid4().hex[:8]
            created=client.post(path,json=dict(code=code,name_ru='API RU',name_kk='API KK')).json()
            assert created['code']==code
            assert client.post(path,json=dict(code=code,name_ru='RU',name_kk='KK')).status_code==409
            assert client.patch(path+'/'+code,json=dict(expected_revision=1,name_ru='RU edited',name_kk='KK edited',is_active=False)).status_code==200
            assert client.patch(path+'/'+code,json=dict(expected_revision=1,name_ru='stale',name_kk='stale')).status_code==409
            renamed=client.patch(path+'/'+code,json=dict(expected_revision=2,name_ru='New RU only'))
            assert renamed.status_code==200 and renamed.json()['is_active'] is False
            assert renamed.json()['name_kk']=='KK edited'
            assert client.patch(path+'/'+code,json=dict(code='renamed',expected_revision=2,name_ru='RU',name_kk='KK')).status_code==422
            assert client.delete(path+'/'+code).status_code==405
            assert code in {r['code'] for r in client.get(path+'?state=inactive').json()['items']}
            app.dependency_overrides[get_current_user]=lambda:dict(user_id=99998,role_id=99998)
            assert client.get(path).status_code==200
            assert client.get(path).json()['can_manage'] is False
            assert client.post(path,json=dict(code='no_rights',name_ru='RU',name_kk='KK')).status_code==403
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(previous)
