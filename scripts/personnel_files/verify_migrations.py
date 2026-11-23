"""Reproduce the combined feature migration on an empty, dedicated local test DB.

Historical i6/j7 migrations need an HR role, an audit actor and a DISP unit.
Only synthetic prerequisites are inserted; no logins or passwords are created.
This is a verification utility, not an application startup or production bootstrap.
"""
from __future__ import annotations

from datetime import date
import os
from pathlib import Path
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def main():
    url = os.environ.get('TEST_DATABASE_URL', '')
    parsed = urlparse(url)
    if parsed.hostname not in {'127.0.0.1', 'localhost'} or not parsed.path.endswith('_test'):
        raise SystemExit('Requires an explicit loopback TEST_DATABASE_URL ending in _test.')
    engine = create_engine(url, hide_parameters=True)
    with engine.connect() as conn:
        if conn.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar_one():
            raise SystemExit('Requires an empty test database; this utility never clears existing data.')
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / 'alembic.ini'))
    cfg.set_main_option('script_location', str(root / 'alembic'))
    cfg.set_main_option('sqlalchemy.url', url.replace('%', '%%'))
    command.upgrade(cfg, 'h5c6d7e8f9a0')
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO roles(code,name) VALUES ('HR_HEAD','[TEST] HR migration role'),('ADMIN','[TEST] Administrator role') ON CONFLICT(code) DO NOTHING"))
        actor = conn.execute(text("INSERT INTO users(full_name,role_id,is_active) SELECT '[TEST] Migration audit actor',role_id,true FROM roles WHERE code='HR_HEAD' RETURNING user_id")).scalar_one()
        parent = conn.execute(text("INSERT INTO org_units(code,name,is_active) VALUES('FILE_TEST_ROOT','[TEST] Organization',true) RETURNING unit_id")).scalar_one()
        conn.execute(text("INSERT INTO org_units(code,name,parent_unit_id,is_active,group_id) VALUES('DISP','[TEST] Department',:parent,true,1)"), {'parent': parent})
    command.upgrade(cfg, 'ptype002')
    with engine.begin() as conn:
        person = conn.execute(text("INSERT INTO persons(full_name,last_name,first_name,match_key,source) VALUES('[TEST] Legacy certificate holder','[TEST]','Legacy','file-migration-test','manual') RETURNING person_id")).scalar_one()
        unit = conn.execute(text("SELECT unit_id FROM org_units WHERE code='DISP'")).scalar_one()
        position = conn.execute(text("INSERT INTO positions(name,category) VALUES('[TEST] Position','other') RETURNING position_id")).scalar_one()
        employee = conn.execute(text("INSERT INTO employees(full_name,person_id,org_unit_id,position_id,employment_rate,is_active,date_from) VALUES('[TEST] Legacy certificate holder',:pid,:unit,:pos,1,true,'2024-01-01') RETURNING employee_id"), {'pid': person,'unit':unit,'pos':position}).scalar_one()
        specialty = conn.execute(text('SELECT min(medical_specialty_id) FROM medical_specialties')).scalar_one()
        for issued,until in [(date(2024,1,1),date(2030,1,1)),(None,None)]:
            conn.execute(text("""INSERT INTO employee_documents(employee_id,document_type_id,medical_specialty_id,issued_at,valid_until,lifecycle_status,verification_status,created_by)
                SELECT :eid,document_type_id,:spec,:issued,:until,'ACTIVE','VERIFIED',:actor FROM document_types WHERE code='SPECIALIST_CERTIFICATION'"""),
                {'eid':employee,'spec':specialty,'issued':issued,'until':until,'actor':actor})
        query = text('SELECT document_id,medical_specialty_id,issued_at,valid_until,lifecycle_status,verification_status FROM employee_documents ORDER BY document_id')
        before = conn.execute(query).all()
    command.upgrade(cfg, 'head')
    command.upgrade(cfg, 'head')
    with engine.connect() as conn:
        assert conn.execute(query).all() == before
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'pfiles002'
        assert conn.execute(text('''SELECT count(*) FROM employee_documents WHERE
            certificate_entry_id IS NOT NULL OR specialty_name_at_issue IS NOT NULL OR
            specialty_code_at_issue IS NOT NULL OR classifier_edition_at_issue IS NOT NULL''')).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM access_grants g JOIN access_roles r USING(access_role_id) WHERE r.code IN ('PERSONNEL_FILES_READ','PERSONNEL_FILES_REVIEW','CERTIFICATE_CLASSIFIERS_MANAGE')")).scalar_one() == 0
        for table in ('personnel_file_sets','personnel_file_versions','personnel_file_events','certificate_classifier_editions','certificate_classifier_entries','certificate_specialty_mappings','certificate_classifier_events'):
            assert conn.execute(text('SELECT to_regclass(:table)'), {'table':'public.'+table}).scalar_one()
    engine.dispose()
    print('PASS: full migration chain with synthetic historical prerequisites; head=pfiles002; repeat upgrade; legacy requisites and statuses preserved; no inferred facts or automatic grants.')


if __name__ == '__main__':
    main()
