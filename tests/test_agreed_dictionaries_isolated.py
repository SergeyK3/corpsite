"""Real dictionary migrations and services, exclusively in a disposable database."""
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from tests.test_personnel_order_print_titles_migration_isolated import fresh_database


def test_positions_migration_edit_reopen_alias_and_transaction_rollback(fresh_database):
    from app.db.position_directory_migration import upgrade
    from app.directory.positions_routes import PositionUpsert
    from app.services.position_directory_service import save_details, get_position, resolve_existing_name
    with fresh_database.begin() as c:
        c.execute(text("""CREATE TABLE positions(position_id bigint PRIMARY KEY,name text,category text,name_kk text);
            CREATE TABLE job_positions_catalog(job_code text PRIMARY KEY,job_nameru text,job_namekk text,job_namekk_doc text);
            CREATE TABLE position_job_catalog(position_id bigint PRIMARY KEY,job_code text);
            CREATE TABLE position_aliases(alias_id bigserial PRIMARY KEY,position_id bigint,alias_text text,normalized_alias text UNIQUE);
            INSERT INTO positions VALUES(1,'TEST exact variant','medical',NULL);
            INSERT INTO job_positions_catalog VALUES('TEST_FAMILY','TEST family','TEST KK family','TEST KK family doc');
            INSERT INTO position_job_catalog VALUES(1,'TEST_FAMILY');"""))
        upgrade(c)
        initial=get_position(c,1)
        assert initial['name']=='TEST exact variant'
        assert initial['record_kind']=='variant'
        payload=PositionUpsert(name=initial['name'],category='medical',name_kk='TEST exact KK',
            document_nominative_ru='TEST official RU',document_possessive_kk='TEST official KK',
            translation_status='confirmed',document_form_status='confirmed',aliases=['TEST synonym'],job_code='TEST_FAMILY')
        save_details(c,1,payload)
        assert resolve_existing_name(c,'test SYNONYM')==1
    with fresh_database.connect() as c:
        reopened=get_position(c,1)
        assert reopened['job_namekk']=='TEST exact KK'
        assert reopened['job_namekk_doc']=='TEST official KK'
        assert reopened['family_name_ru']=='TEST family'
        assert reopened['aliases']==['TEST synonym']
    with pytest.raises(HTTPException):
        with fresh_database.begin() as c:
            save_details(c,1,PositionUpsert(name='TEST exact variant',category='medical',
                name_kk='TEST must rollback',translation_status='confirmed',job_code='MISSING'))
    with fresh_database.connect() as c:
        assert get_position(c,1)==reopened


def test_specialty_bilingual_search_duplicate_archive_and_reopen(fresh_database,monkeypatch):
    from app.db.medical_specialties_schema import upgrade
    from app.services import medical_specialties_directory_service as service
    with fresh_database.begin() as c:
        c.execute(text("""CREATE TABLE medical_specialty_groups(group_id bigserial PRIMARY KEY,code text UNIQUE,name text,is_active boolean DEFAULT true);
            CREATE TABLE medical_specialties(medical_specialty_id bigserial PRIMARY KEY,group_id bigint REFERENCES medical_specialty_groups,code text UNIQUE,name text,is_active boolean DEFAULT true);"""))
        upgrade(c)
        upgrade(c)
    monkeypatch.setattr(service,'engine',fresh_database)
    chosen=service.create_specialty('TEST specialty RU','TEST specialty KK')
    id=chosen['medical_specialty_id']
    assert service.get_specialty(id)==chosen
    for q in ('specialty RU','specialty KK'):
        assert service.list_specialties(q=q,limit=1)['items'][0]['medical_specialty_id']==id
        assert service.list_specialties(q=q,limit=1,offset=1)['items']==[]
    with pytest.raises(HTTPException) as duplicate:
        service.create_specialty('test specialty ru','TEST other KK')
    assert duplicate.value.status_code==409
    with pytest.raises(HTTPException):
        service.archive_specialties([id,id+1000])
    assert service.get_specialty(id)['is_active']
    assert service.archive_specialties([id])['archived_ids']==[id]
    assert service.list_specialties()['items']==[]
    assert service.list_specialties(is_active=False)['total']==1
