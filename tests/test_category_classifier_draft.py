"""Opt-in, disposable PostgreSQL rehearsal containing synthetic records only."""
import json
import os
import unittest
from copy import deepcopy
from datetime import date
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy import create_engine, text


@unittest.skipUnless(os.getenv('CATEGORY_CLASSIFIER_TESTS') == '1', 'Disposable local database opt-in required')
class CategoryClassifierDraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.db.engine import engine
        from app.db.medical_qualification_categories_schema import upgrade
        from tests.category_template_fixture import seed_category_fixture
        assert engine.url.host in {'127.0.0.1', 'localhost', '::1'}
        cls.name = 'category_classifier_' + uuid4().hex + '_test'
        cls.admin = create_engine(engine.url.set(database='postgres'), isolation_level='AUTOCOMMIT', hide_parameters=True)
        with cls.admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{cls.name}"'))
        cls.database = create_engine(engine.url.set(database=cls.name), hide_parameters=True)
        seed_category_fixture(cls.database)
        with cls.database.begin() as conn:
            upgrade(conn)
            conn.execute(text('CREATE TABLE employees(employee_id bigint PRIMARY KEY,full_name text)'))
            conn.execute(text("INSERT INTO employees VALUES(900001,'TEST ONLY employee')"))
            conn.execute(text('CREATE TABLE category_samples(id int PRIMARY KEY,payload jsonb NOT NULL)'))

    @classmethod
    def tearDownClass(cls):
        cls.database.dispose()
        with cls.admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{cls.name}"'))
        cls.admin.dispose()

    def sample(self, code=2, specialty=True):
        from app.services.personnel_order_category_contract import SAMPLE
        from app.services.personnel_order_category_classifier_contract import CONTRACT
        from app.db.medical_qualification_categories_schema import CATEGORIES
        sample = deepcopy(SAMPLE)
        sample.update(contract=CONTRACT, employee_id=900001, effective_date='2026-07-01', basis='TEST основание')
        _, ru, kk = CATEGORIES[code-1]
        sample['qualification_category'] = dict(code=code, name_ru=ru, name_kk=kk, assigned_at='2026-06-11')
        if not specialty:
            sample['medical_specialty'] = None
        return sample

    def texts(self):
        from app.services.personnel_order_category_contract import TEXTS
        from app.services.personnel_order_category_classifier_contract import BODY_RU, BODY_KK
        return dict(TEXTS, body_template_ru=BODY_RU, body_template_kk=BODY_KK)

    def test_six_combinations_prepare_save_reopen_and_render(self):
        from app.services.personnel_order_manual_draft_service import prepare_manual_item_payload
        from app.services.personnel_order_template_application_service import _values, _render
        from app.services.personnel_order_category_classifier_contract import LEVELS
        template = dict(self.texts(), item_type_code='QUALIFICATION_CATEGORY', print_title_ru=self.texts()['title_ru'], print_title_kk=self.texts()['title_kk'])
        with self.database.begin() as conn:
            for code in (2, 3, 4):
                for specialty in (False, True):
                    with self.subTest(code=code, specialty=specialty):
                        sample = self.sample(code, specialty)
                        sample['basis'] = 'TEST основание'
                        sample['qualification_category']['name_ru'] = 'FORGED'
                        saved = prepare_manual_item_payload(conn, item_type_code='QUALIFICATION_CATEGORY', employee_id=900001,
                            effective_date=date(2026,7,1), item_payload=sample)
                        self.assertNotEqual(saved['qualification_category']['name_ru'], 'FORGED')
                        self.assertEqual(saved['qualification_category']['valid_until'], '2031-06-10')
                        key = code * 10 + int(specialty)
                        conn.execute(text('INSERT INTO category_samples VALUES (:id,CAST(:payload AS jsonb))'), {'id':key, 'payload':json.dumps(saved)})
                        reopened = conn.execute(text('SELECT payload FROM category_samples WHERE id=:id'), {'id':key}).scalar_one()
                        self.assertEqual(reopened, saved)
                        values, warnings, missing = _values(conn, dict(item_type_code='QUALIFICATION_CATEGORY', payload=reopened), template)
                        self.assertEqual((warnings, missing), ([], []))
                        rendered = _render(template, values)
                        self.assertEqual(rendered['body_template_ru'], f'С 01.07.2026 категория врача-терапевта' + (' («Терапия»)' if specialty else '') + f' тестового отделения терапии Тестова Айдара Ерлановича будет считаться „{LEVELS[code][0]}“ до 10.06.2031.')
                        self.assertEqual(rendered['body_template_kk'], '2026 жылғы 1 шілдеден бастап Тестілік терапия бөлімшесінің дәрігер-терапевті' + (' («Терапия»)' if specialty else '') + f' Айдар Ерланұлы Тестовтың санаты „{LEVELS[code][1]}“ 2031 жылғы 10 маусымға дейін болып есептелсін.')
                        for locale in ('ru','kk'):
                            body = rendered['body_template_' + locale]
                            self.assertNotIn('  ', body)
                            self.assertNotIn('«»', body)
                            self.assertNotIn('7.2 (', body)
                        self.assertFalse({'category_code_ru','category_code_kk','category_code_source'} & saved['qualification_category'].keys())

    def test_invalid_categories_and_calendar_dates(self):
        from app.services.personnel_order_category_contract import category_values
        from app.services.personnel_order_category_classifier_contract import classifier_values
        for code in (1, 0, 5, '2', True, None):
            sample = self.sample(); sample['qualification_category']['code'] = code
            with self.subTest(code=code), self.assertRaises(ValueError): classifier_values(sample)
        for assigned, end in (('2024-02-29','27.02.2029'), ('2023-03-01','29.02.2028'), ('2026-12-31','30.12.2031')):
            sample = self.sample(); sample['qualification_category']['assigned_at'] = assigned
            self.assertEqual(category_values(sample)['qualification_category.valid_until_ru'], end)
            self.assertEqual(category_values(sample)['effective_date.ru'], '01.07.2026')

    def test_current_catalog_and_minimal_required_body_forms(self):
        from app.services.personnel_order_template_catalog_service import list_personnel_order_template_catalog
        from app.api.admin_schemas import PersonnelOrderTemplateCatalogResponse
        from app.services.personnel_order_category_classifier_contract import classifier_values, REQUIRED, REQUIRED_ORDER_FIELDS
        from app.services.personnel_order_category_contract import prepare_category_payload
        catalog = list_personnel_order_template_catalog()
        projected = PersonnelOrderTemplateCatalogResponse(items=catalog).model_dump()['items']
        row = next(item for item in projected if item['type_code']=='QUALIFICATION_CATEGORY')
        self.assertEqual(row['required_fields'], list(REQUIRED_ORDER_FIELDS))
        self.assertEqual(row['required_variables'], {key:list(value) for key,value in REQUIRED.items()})
        self.assertEqual(row['support_level'], 'PARTIAL')
        self.assertNotIn('Код RU/KK', row['required_fields'])
        self.assertNotIn('Специальность RU/KK', row['required_fields'])
        self.assertIn('Медицинская специальность', row['optional_fields'][0])
        self.assertIn('Дата окончания', row['computed_fields'][0])
        self.assertIn('подтверждающий документ', row['formalization_warning'])
        sample = self.sample(3, False)
        sample.pop('source_employee_name')
        sample['document_org_unit'].pop('name');sample['document_org_unit'].pop('name_kk')
        sample['qualification_category']['valid_until'] = '2099-01-01'
        with self.database.begin() as conn:
            prepared = prepare_category_payload(conn,sample,900001,date(2026,7,1))
        self.assertEqual(prepared['qualification_category']['valid_until'],'2031-06-10')
        classifier_values(prepared)
        for namespace,field in (
            ('document_forms_ru','employee_full_name_genitive_ru'), ('document_forms_kk','employee_full_name_genitive_kk'),
            ('document_forms_ru','position_document_genitive_ru'), ('document_forms_kk','position_document_possessive_kk'),
            ('document_org_unit','document_genitive_ru'), ('document_org_unit','document_genitive_kk'),
        ):
            invalid=deepcopy(prepared);invalid[namespace][field]=''
            with self.subTest(field=field), self.assertRaises(ValueError):classifier_values(invalid)
        for value in ('','20260201','2026-02-30','1899-01-01','9995-01-01'):
            for field in ('assigned_at','effective_date'):
                invalid=deepcopy(prepared)
                if field=='assigned_at':invalid['qualification_category'][field]=value
                else:invalid[field]=value
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):classifier_values(invalid)

    def test_native_draft_save_reopen_sample_api_and_published_preservation(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.admin_router import router
        from app.security.admin_guard import require_sysadmin_api
        from app.services import personnel_order_template_draft_service as service
        from app.services.personnel_order_category_contract import TEXTS
        with self.database.begin() as conn:
            template_id = conn.execute(text("INSERT INTO personnel_order_templates(item_type_code,name_ru,name_kk) VALUES('QUALIFICATION_CATEGORY','TEST RU','TEST KK') RETURNING template_id")).scalar_one()
            fields = ','.join(service.TEXT_FIELDS)
            params = {**TEXTS, 'template_id':template_id}
            published = dict(conn.execute(text(f"INSERT INTO personnel_order_template_versions(template_id,item_type_code,version_number,status,{fields}) VALUES(:template_id,'QUALIFICATION_CATEGORY',1,'PUBLISHED'," + ','.join(':'+field for field in service.TEXT_FIELDS) + ') RETURNING *'), params).mappings().one())
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[require_sysadmin_api] = lambda: {'user_id':900001}
        with patch.object(service, 'engine', self.database), TestClient(app) as client:
            base = f'/admin/personnel-order-templates/QUALIFICATION_CATEGORY'
            version_texts = dict(self.texts(), print_title_ru=self.texts()['title_ru'], print_title_kk=self.texts()['title_kk'])
            draft = service.create_draft_from_working_copy('QUALIFICATION_CATEGORY','PUBLISHED',published['template_version_id'],published['revision'],version_texts,900001,template_id)
            self.assertEqual(service.get_published('QUALIFICATION_CATEGORY',template_id)['template_version_id'], published['template_version_id'])
            saved = service.save_draft('QUALIFICATION_CATEGORY',draft['revision'], version_texts,900001,template_id,expected_template_version_id=draft['template_version_id'])
            self.assertEqual(client.get(base+'/draft',params={'template_id':template_id}).json()['template_version_id'],saved['template_version_id'])
            for code in (2,3,4):
                for specialty in (False,True):
                    request = dict(expected_template_version_id=saved['template_version_id'],expected_revision=saved['revision'],sample=self.sample(code,specialty))
                    response = client.post(base+'/draft/sample-preview',params={'template_id':template_id},json=request)
                    self.assertEqual(response.status_code,200,response.text)
            request['expected_revision'] += 1
            self.assertEqual(client.post(base+'/draft/sample-preview',params={'template_id':template_id},json=request).status_code,409)
            self.assertEqual(service.get_draft('QUALIFICATION_CATEGORY',template_id),saved)
            self.assertEqual(service.preview_draft('QUALIFICATION_CATEGORY',self.texts())['ru']['body'].count('высшей'),1)
        with self.database.connect() as conn:
            actual = dict(conn.execute(text('SELECT * FROM personnel_order_template_versions WHERE template_version_id=:id'), {'id':published['template_version_id']}).mappings().one())
        self.assertEqual(actual,published)
