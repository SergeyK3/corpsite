"""Integration checks in a dedicated, disposable PostgreSQL database only."""
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from scripts import import_annual_leave_recall_template as importer

URL = os.environ.get('TEST_RECALL_IMPORT_DATABASE_URL', '')
pytestmark = pytest.mark.skipif(not URL, reason='requires dedicated recall_import_test PostgreSQL')
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def database():
    url = make_url(URL)
    assert url.host == '127.0.0.1' and url.database == 'recall_import_test'
    from app.services import personnel_order_template_draft_service as service
    if os.environ.get('TEST_RECALL_SERVICE_FILE'):
        import importlib.util
        spec = importlib.util.spec_from_file_location('recall_server_service_probe',
                                                     os.environ['TEST_RECALL_SERVICE_FILE'])
        service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(service)
    engine = create_engine(url)
    with engine.connect() as conn:
        tx = conn.begin()
        conn.execute(text('CREATE TABLE alembic_version(version_num text PRIMARY KEY)'))
        conn.execute(text("INSERT INTO alembic_version VALUES ('hrjobmerge001')"))
        conn.execute(text('CREATE TABLE users(user_id bigint PRIMARY KEY, login text, is_active boolean)'))
        conn.execute(text("INSERT INTO users VALUES (901,'test-importer',TRUE)"))
        conn.execute(text('''CREATE TABLE personnel_order_templates(
            template_id bigserial PRIMARY KEY,item_type_code text,name_ru text,name_kk text,
            is_default boolean NOT NULL DEFAULT FALSE,created_by_user_id bigint REFERENCES users,
            created_at timestamptz DEFAULT now(), copied_from_template_version_id bigint,
            UNIQUE(template_id,item_type_code))'''))
        conn.execute(text('''CREATE UNIQUE INDEX uq_default ON personnel_order_templates(item_type_code)
            WHERE is_default'''))
        conn.execute(text('''CREATE TABLE personnel_order_template_versions(
            template_version_id bigserial PRIMARY KEY,template_id bigint,item_type_code text,
            version_number integer,status text,revision integer DEFAULT 1,
            title_ru text,title_kk text,preamble_ru text,preamble_kk text,
            body_template_ru text,body_template_kk text,basis_template_ru text,basis_template_kk text,
            based_on_built_in boolean DEFAULT TRUE,created_by_user_id bigint REFERENCES users,
            updated_by_user_id bigint REFERENCES users,created_at timestamptz DEFAULT now(),
            updated_at timestamptz DEFAULT now(),published_at timestamptz,published_by_user_id bigint,
            FOREIGN KEY(template_id,item_type_code) REFERENCES personnel_order_templates(template_id,item_type_code),
            UNIQUE(template_id,version_number))'''))
        conn.execute(text("INSERT INTO personnel_order_templates(item_type_code,name_ru,name_kk,is_default) "
                          "VALUES ('HIRE','Существующая основа','Бар негіз',TRUE)"))
        # Existing approved published texts must survive byte for byte.
        cols = ','.join(importer.FIELDS)
        vals = ','.join(':'+f for f in importer.FIELDS)
        conn.execute(text(f'INSERT INTO personnel_order_template_versions(template_id,item_type_code,version_number,'
            f'status,published_at,{cols}) VALUES (1,\'HIRE\',4,\'PUBLISHED\',now(),{vals})'),
            {f: 'Серверный утверждённый текст / Бекітілген мәтін '+f for f in importer.FIELDS})
        data = importer.read_source(ROOT/'reference-data/personnel-templates/annual-leave-recall.json')
        try:
            yield conn, service, data
        finally:
            tx.rollback()
    engine.dispose()


def run(database, **kwargs):
    conn, service, data = database
    return importer.run_import(conn, service, data, actor_login='test-importer', **kwargs)


def test_import_preview_idempotence_and_receipt(database):
    conn, _, data = database
    preview = run(database)
    assert preview['action'] == 'WOULD_CREATE'
    assert conn.execute(text('SELECT count(*) FROM personnel_order_templates')).scalar_one() == 1
    result = run(database, apply=True)
    assert result['action'] == 'CREATED' and result['version_number'] == 1 and result['status'] == 'DRAFT'
    assert result['all_eight_fields_verified'] and result['existing_templates_unchanged']
    assert result['saved_fields'] == data['texts']
    assert '\n\n' in result['previews']['ru']['body'] and '\n\n' in result['previews']['kk']['body']
    assert 'Неиспользованную часть' in result['previews']['ru']['body']
    assert 'пайдаланылмаған бөлігі' in result['previews']['kk']['body']
    assert run(database, apply=True)['action'] == 'EXISTS'  # crash before saving receipt also safe
    assert run(database, apply=True, receipt=result)['action'] == 'EXISTS'
    assert run(database, verify_only=True, receipt=result)['template_version_id'] == result['template_version_id']
    assert conn.execute(text('SELECT count(*) FROM personnel_order_templates')).scalar_one() == 2


@pytest.mark.parametrize('change', ['text', 'published', 'renamed', 'removed'])
def test_modified_import_never_recreated_or_overwritten(database, change):
    conn, _, _ = database
    result = run(database, apply=True)
    if change == 'text':
        conn.execute(text("UPDATE personnel_order_template_versions SET body_template_ru='Changed' WHERE template_id=:id"), {'id': result['template_id']})
    elif change == 'published':
        conn.execute(text("UPDATE personnel_order_template_versions SET status='PUBLISHED',published_at=now() WHERE template_id=:id"), {'id': result['template_id']})
    elif change == 'renamed':
        conn.execute(text("UPDATE personnel_order_templates SET name_ru='Renamed',name_kk='Renamed' WHERE template_id=:id"), {'id': result['template_id']})
    else:
        conn.execute(text('DELETE FROM personnel_order_template_versions WHERE template_id=:id'), {'id': result['template_id']})
        conn.execute(text('DELETE FROM personnel_order_templates WHERE template_id=:id'), {'id': result['template_id']})
    before = conn.execute(text('SELECT count(*) FROM personnel_order_templates')).scalar_one()
    with pytest.raises(RuntimeError):
        run(database, apply=True, receipt=result)
    assert conn.execute(text('SELECT count(*) FROM personnel_order_templates')).scalar_one() == before


def test_post_write_preview_failure_rolls_back(database, monkeypatch):
    conn, service, _ = database
    original = service.preview_draft
    calls = 0

    def broken(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('injected saved-preview failure')
        return original(*args)

    monkeypatch.setattr(service, 'preview_draft', broken)
    with pytest.raises(RuntimeError, match='injected'):
        with conn.begin_nested():
            run(database, apply=True)
    assert conn.execute(text('SELECT count(*) FROM personnel_order_templates')).scalar_one() == 1
    assert conn.execute(text('SELECT count(*) FROM personnel_order_template_versions')).scalar_one() == 1


def test_collision_and_missing_base_block(database):
    conn, _, data = database
    conn.execute(text('INSERT INTO personnel_order_templates(item_type_code,name_ru,name_kk) VALUES (:code,:ru,:kk)'),
        {'code': importer.CODE, 'ru': data['name_ru'], 'kk': data['name_kk']})
    with pytest.raises(RuntimeError, match='one version'):
        run(database, apply=True)
    conn.execute(text('DELETE FROM personnel_order_templates WHERE NOT is_default'))
    conn.execute(text('UPDATE personnel_order_templates SET is_default=FALSE'))
    with pytest.raises(RuntimeError, match='no existing editable default'):
        run(database, apply=True)


def test_migration_and_actor_gates(database):
    conn, service, data = database
    with pytest.raises(RuntimeError, match='actor'):
        importer.run_import(conn, service, data, apply=True, actor_login='absent')
    conn.execute(text("UPDATE alembic_version SET version_num='hrlang001'"))
    with pytest.raises(RuntimeError, match='hrjobmerge001'):
        run(database, apply=True)
