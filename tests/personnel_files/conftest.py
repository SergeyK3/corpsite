"""Isolated PostgreSQL contract fixture. Never uses the application's configured database."""
import importlib.util
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture(scope='session')
def database():
    url = os.environ.get('TEST_DATABASE_URL', '')
    parsed = urlparse(url)
    if parsed.hostname not in {'127.0.0.1', 'localhost'} or parsed.path != '/corpsite_selfcard_test':
        pytest.skip('Requires isolated loopback corpsite_selfcard_test database')
    eng = create_engine(url, hide_parameters=True)
    with eng.begin() as conn:
        # The fixture is explicitly dedicated to this feature and contains only synthetic data.
        conn.execute(text('''
            CREATE TABLE persons(person_id bigint primary key,full_name text,last_name text,first_name text,middle_name text,updated_at timestamptz default now());
            CREATE TABLE users(user_id bigint primary key,role_id bigint,employee_id bigint,is_active boolean default true,full_name text);
            CREATE TABLE employees(employee_id bigint primary key,person_id bigint,org_unit_id bigint,is_active boolean default true,full_name text);
            CREATE TABLE org_units(unit_id bigint primary key,parent_unit_id bigint,is_active boolean default true);
            CREATE TABLE person_assignments(assignment_id bigint,person_id bigint,position_id bigint,org_unit_id bigint,active_flag boolean,lifecycle_status text);
            CREATE TABLE access_roles(access_role_id bigint generated always as identity primary key,code text unique,name text,access_level text,level_rank int,is_active boolean default true,
                CHECK ((access_level='NONE' AND level_rank=0) OR (access_level='MANAGER' AND level_rank=20) OR (access_level='ADMIN' AND level_rank=30)));
            CREATE TABLE access_grants(grant_id bigint generated always as identity primary key,access_role_id bigint,target_type text,target_id bigint,
                resource_key text default '*',scope_type text default 'GLOBAL',scope_id bigint,include_subtree boolean default false,
                starts_at timestamptz default now(),ends_at timestamptz,reason text,active_flag boolean default true);
            CREATE TABLE user_supervisors(user_id bigint primary key,supervisor_id bigint,is_active boolean default true,valid_from timestamptz default now(),valid_to timestamptz);
            CREATE TABLE personnel_record_events(event_id bigint generated always as identity primary key,person_id bigint,employee_context_id bigint,
                domain_code text,record_table_name text,record_id bigint,event_type text,actor_id text,event_payload jsonb,migration_run_id bigint,migration_item_id bigint);
            CREATE TABLE medical_specialties(medical_specialty_id bigint PRIMARY KEY,name text,code text,is_active boolean default true,group_id bigint default 1);
            CREATE TABLE document_types(document_type_id bigint PRIMARY KEY,code text,is_active boolean default true,
                name text,category text,requires_medical_specialty boolean default true,has_valid_until boolean default true,tracks_hours boolean default false);
            CREATE TABLE document_kinds(document_kind_id bigint PRIMARY KEY,code text,name text,is_active boolean);
            CREATE TABLE employee_documents(document_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,employee_id bigint REFERENCES employees,
                document_type_id bigint REFERENCES document_types,medical_specialty_id bigint REFERENCES medical_specialties,
                issued_at date,valid_until date,document_number text,issued_by text,lifecycle_status text,verification_status text,
                created_by bigint,created_at timestamptz default now(),updated_at timestamptz default now(),
                document_kind_id bigint,title text,training_title text,hours integer,file_url text,comment text);
        '''))
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        spec = importlib.util.spec_from_file_location('files_migration', Path('alembic/versions/pfiles001_reviewed_personnel_files.py'))
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        spec = importlib.util.spec_from_file_location('certificate_migration', Path('alembic/versions/pfiles002_certificate_registry.py'))
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
    yield eng
    eng.dispose()


@pytest.fixture
def seeded(database, monkeypatch, tmp_path):
    from app.personnel_files import service
    from app.db import engine as engine_module
    monkeypatch.setattr(service, 'engine', database)
    monkeypatch.setattr(engine_module, 'engine', database)
    monkeypatch.setenv('PERSONNEL_FILE_STORAGE_ROOT', str(tmp_path / 'files'))
    from app.personnel_files import storage
    # Scanner is stubbed for deterministic fixtures; scanner failures have separate tests.
    monkeypatch.setattr(storage, 'scan', lambda _: None)
    with database.begin() as conn:
        conn.execute(text('''TRUNCATE personnel_file_inbox,personnel_file_events,personnel_file_versions,personnel_file_sets,
            employee_documents,certificate_classifier_events,certificate_specialty_mappings,certificate_classifier_entries,
            certificate_classifier_editions,medical_specialties,document_types,
            personnel_record_events,access_grants,user_supervisors,person_assignments,users,employees,persons,org_units RESTART IDENTITY CASCADE;
            INSERT INTO persons(person_id,full_name,last_name,first_name) VALUES (1,'Вымышленный Работник','Вымышленный','Работник'),(2,'Другой Тест','Другой','Тест');
            INSERT INTO employees VALUES(1,1,10,true,'Вымышленный Работник'),(2,2,20,true,'Другой Тест');
            INSERT INTO users VALUES(1,10,1,true,'Вымышленный Работник'),(2,10,2,true,'Другой Тест'),(3,10,NULL,true,'Кадровик Тест'),
                (4,10,NULL,true,'Начальник Тест'),(5,10,NULL,true,'Заместитель Тест'),(6,2,NULL,true,'Сисадмин Тест'),(7,10,NULL,true,'Помощник Тест'),(8,10,NULL,true,'Директор Тест');
            INSERT INTO org_units VALUES(10,NULL,true),(20,NULL,true);
            INSERT INTO access_grants(access_role_id,target_type,target_id,scope_type,scope_id)
                SELECT access_role_id,'USER',3,'ORG_UNIT',10 FROM access_roles WHERE code='PERSONNEL_FILES_REVIEW';
            INSERT INTO access_grants(access_role_id,target_type,target_id,scope_type,scope_id)
                SELECT access_role_id,'USER',5,'ORG_UNIT',10 FROM access_roles WHERE code='PERSONNEL_FILES_READ';
            INSERT INTO access_grants(access_role_id,target_type,target_id)
                SELECT access_role_id,'USER',8 FROM access_roles WHERE code='PERSONNEL_FILES_READ';
            INSERT INTO user_supervisors(user_id,supervisor_id) VALUES(1,4);
            INSERT INTO medical_specialties(medical_specialty_id,name,code,is_active) VALUES(1,'Вымышленная А','TEST-A',true),(2,'Вымышленная Б','TEST-B',true),(3,'Вымышленная Х','TEST-X',true);
            INSERT INTO document_types(document_type_id,code,name,category) VALUES(1,'SPECIALIST_CERTIFICATION','Сертификат','CERTIFICATION');
            INSERT INTO certificate_classifier_editions(code,title,source_reference,effective_from,created_by)
                VALUES('TEST-OLD','Вымышленная старая редакция','Учебный источник','2020-01-01',3),
                      ('TEST-NEW','Вымышленная новая редакция','Учебный источник','2025-01-01',3);
            INSERT INTO certificate_classifier_entries(edition_id,medical_specialty_id,specialty_code,specialty_name)
                VALUES(1,1,'OLD-A','Вымышленная А'),(1,2,'OLD-B','Вымышленная Б'),
                      (2,1,'NEW-A','Вымышленная новая А'),(2,3,'NEW-X','Вымышленная Х');
        '''))
    actors = {i: {'user_id':i,'role_id':2 if i==6 else 10,'employee_id':i if i in (1,2) else None,'role_code':'SYSADMIN_ASSISTANT' if i==7 else 'TEST'} for i in range(1,9)}
    # Avoid legacy global DB helpers for assistant capability only; grants and scope remain real SQL.
    import app.security.sysadmin_assistant as assistant
    monkeypatch.setattr(assistant, 'has_hr_support', lambda u: u['user_id']==7)
    return actors
