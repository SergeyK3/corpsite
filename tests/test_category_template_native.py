from copy import deepcopy
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

import os
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from tests.category_template_fixture import seed_category_fixture
from app.api.admin_router import router
from app.security.admin_guard import require_sysadmin_api
from app.services import personnel_order_template_draft_service as service
from app.services.personnel_order_category_contract import TYPE, TEXTS, SAMPLE, LEVELS, category_values, valid_until
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_template_validation import validate_template_texts, TemplateValidationError


@pytest.fixture
def fresh_database():
    source = make_url(os.environ['TEST_DATABASE_URL'])
    assert source.host in {'localhost','127.0.0.1','::1'} and source.database.endswith('_test')
    name = 'corpsite_category_' + uuid4().hex + '_test'
    admin = create_engine(source.set(database='postgres'), isolation_level='AUTOCOMMIT', hide_parameters=True)
    isolated = create_engine(source.set(database=name), hide_parameters=True)
    with admin.connect() as conn:
        conn.execute(text('CREATE DATABASE "'+name+'"'))
    try:
        yield isolated
    finally:
        isolated.dispose()
        with admin.connect() as conn:
            conn.execute(text('DROP DATABASE "'+name+'"'))
        admin.dispose()


@pytest.fixture
def client(fresh_database, monkeypatch):
    seed_category_fixture(fresh_database)
    monkeypatch.setattr(service, 'engine', fresh_database)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_sysadmin_api] = lambda: {'user_id': 900001}
    with TestClient(app) as client:
        yield client, fresh_database


def test_all_tokens_registered_and_no_extra_prose():
    spec = get_personnel_order_template_spec(TYPE)
    validate_template_texts(TYPE, TEXTS)
    assert {t for text in TEXTS.values() for t in re.findall(r'\{\{([\w.]+)\}\}', text)} <= set(spec.allowed_variables)
    assert all(term not in TEXTS['body_template_ru'] for term in ('сроком действия','включительно','высшей квалификационной'))
    altered = {**TEXTS, 'body_template_ru': TEXTS['body_template_ru'] + '{{unknown.code}}'}
    with pytest.raises(TemplateValidationError): validate_template_texts(TYPE, altered)


def test_native_save_edit_reopen_all_levels_snapshot_and_print(client):
    api, engine = client
    base = '/admin/personnel-order-templates/' + TYPE
    initial = api.get(base+'/editor-base').json()
    assert initial['source'] == 'INITIAL'
    assert api.get(base+'/draft').json() is None
    body = {**TEXTS, 'base_source':'INITIAL', 'title_ru':'TEST внутреннее название', 'title_kk':'TEST ішкі атау',
            'print_title_ru':'Об изменении квалификационной категории', 'print_title_kk':'Біліктілік санатын өзгерту туралы'}
    response = api.post(base+'/draft', json=body)
    assert response.status_code == 200, response.text
    draft = response.json()
    query = '?template_id='+str(draft['template_id'])
    assert api.get(base+'/draft'+query).json() == draft
    body.pop('base_source')
    response = api.put(base+'/draft'+query, json={**body,'title_ru':'TEST исправленное внутреннее название',
        'expected_revision':draft['revision'],'expected_template_version_id':draft['template_version_id']})
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated['revision'] == draft['revision']+1
    assert updated['print_title_ru'] == draft['print_title_ru']
    assert api.get(base+'/draft'+query).json() == updated
    sample = deepcopy(SAMPLE)
    # Rename the dictionary after choosing a specialty; rendering must use the snapshot.
    with engine.begin() as conn:
        conn.execute(text("UPDATE medical_specialties SET name='CHANGED',name_kk='CHANGED'"))
    for code, (ru,kk) in LEVELS.items():
        sample['qualification_category']['category'] = code
        request = dict(sample=sample,expected_revision=updated['revision'],expected_template_version_id=updated['template_version_id'])
        response = api.post(base+'/draft/sample-preview'+query, json=request)
        assert response.status_code == 200, response.text
        preview = response.json()
        assert preview['previews']['ru']['title'] == 'Об изменении квалификационной категории'
        assert 'TEST исправленное' not in preview['previews']['ru']['title']
        assert preview['previews']['ru']['body'] == f'С 11.06.2026 категория врача-терапевта («Терапия») тестового отделения терапии Тестова Айдара Ерлановича будет считаться 7.2 (Р) „{ru}“ до 10.06.2031.'
        assert preview['previews']['kk']['body'] == f'2026 жылғы 11 маусымнан бастап Тестілік терапия бөлімшесінің дәрігер-терапевті («Терапия») Айдар Ерланұлы Тестовтың санаты 7.2 (R) „{kk}“ 2031 жылғы 10 маусымға дейін болып есептелсін.'
        assert 'CHANGED' not in str(preview)
    stale = api.post(base+'/draft/sample-preview'+query, json={**request,'expected_revision':draft['revision']})
    assert stale.status_code == 409
    sample['qualification_category']['category'] = 'none'
    assert api.post(base+'/draft/sample-preview'+query, json={**request,'sample':sample}).status_code == 400
    assert api.get(base+'/published'+query).json() is None
    assert api.get(base+'/draft'+query).json() == updated


@pytest.mark.parametrize('start,end',[('2026-06-11','2031-06-10'),('2024-02-29','2029-02-27'),('2023-03-01','2028-02-29')])
def test_calendar_expiry(start,end):
    assert valid_until(start).isoformat() == end


@pytest.mark.parametrize('key',['medical_specialty','document_forms_ru','qualification_category'])
def test_invalid_sample_is_validation_error(key):
    sample=deepcopy(SAMPLE);sample[key]='invalid'
    with pytest.raises(ValueError): category_values(sample)
