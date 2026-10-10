"""Offline tests: no application database or server required (python -m unittest)."""
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from io import BytesIO

from openpyxl import Workbook
from openpyxl.worksheet.table import Table
from sqlalchemy import create_engine, text

from app.services.job_catalog_service import read_catalog, plan_catalog, apply_catalog
from app.services.personnel_order_catalog_context import snapshot_catalog_forms
from app.services.personnel_orders_editorial.mapper import build_item_ctx, effective_text
from app.services.personnel_orders_editorial.generators import generate_item_body

SOURCE = Path(__file__).resolve().parents[1] / "reference-data/job-positions/catalog-v1.json"


class CatalogTests(unittest.TestCase):
    def test_catalog_api_edit_persists_and_keeps_code_immutable(self):
        from app.directory import positions_routes as routes
        from fastapi import HTTPException
        from pydantic import ValidationError
        engine = create_engine('sqlite://')
        with engine.begin() as conn:
            conn.execute(text("ATTACH DATABASE ':memory:' AS public"))
            conn.execute(text('CREATE TABLE public.job_positions_catalog(job_code TEXT PRIMARY KEY, job_nameru TEXT, job_namekk TEXT, job_namekk_doc TEXT)'))
            conn.execute(text("INSERT INTO public.job_positions_catalog VALUES ('NURSE', 'Old', 'Old', 'Old')"))
        values = dict(job_nameru='Медицинская сестра', job_namekk='Мейіргер', job_namekk_doc='мейіргері')
        with patch.object(routes, 'engine', engine), patch.object(routes, '_is_privileged', return_value=True):
            self.assertEqual(routes.edit_job_catalog('NURSE', routes.JobCatalogEdit(**values), {}), {'job_code': 'NURSE', **values})
        with engine.connect() as conn:
            self.assertEqual(dict(conn.execute(text("SELECT * FROM public.job_positions_catalog WHERE job_code='NURSE'")).mappings().one()), {'job_code': 'NURSE', **values})
        with self.assertRaises(ValidationError):
            routes.JobCatalogEdit(**values, job_code='CHANGED')
        with patch.object(routes, '_is_privileged', return_value=False), self.assertRaises(HTTPException) as denied:
            routes.edit_job_catalog('NURSE', routes.JobCatalogEdit(**values), {})
        self.assertEqual(denied.exception.status_code, 403)

    def test_exact_source_and_merges(self):
        rows = read_catalog(SOURCE)
        report = plan_catalog(rows)
        self.assertEqual(len(rows), 88)
        self.assertEqual(sum(len(r['legacy_position_ids']) for r in rows), 108)
        self.assertEqual(len(report['merges']), 5)
        self.assertEqual(report['conflicts'], [])
        self.assertIsNone(report['missing_ids'])
        self.assertFalse(report['can_apply'])
        with BytesIO() as stream:
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = 'catl_job'
            sheet.append(['job_code','job_nameru','job_namekk','job_namekk_doc','legacy_position_ids'])
            for row in rows:
                sheet.append([row[key] for key in ('job_code','job_nameru','job_namekk','job_namekk_doc')] + [', '.join(map(str,row['legacy_position_ids']))])
            sheet.add_table(Table(displayName='CatlJobPositionsV2',ref='A1:E89'))
            workbook.create_sheet('ignored').append(['BAD', '=1/0'])
            workbook.save(stream)
            workbook.close()
            stream.seek(0)
            self.assertEqual(read_catalog(stream), rows)

    def test_missing_duplicate_and_existing_edit_conflicts(self):
        row = read_catalog(SOURCE)[0]
        report = plan_catalog([row, row], [{'position_id': 999, 'name': 'Other'}])
        self.assertEqual(report['missing_ids'], [1])
        self.assertEqual(report['unmapped_existing_ids'], [999])
        self.assertFalse(report['can_apply'])
        self.assertTrue(report['conflicts'])
        report = plan_catalog([row], [{'position_id': 1}], [{**row, 'job_namekk_doc': 'Edited'}], [{'position_id': 1, 'job_code': 'OTHER'}])
        self.assertEqual(len(report['conflicts']), 2)

    def test_non_destructive_idempotent_import_and_reopen(self):
        # SQLite exercises real SQL persistence; PostgreSQL lock statements are
        # recorded by the adapter and need the separate local PostgreSQL check.
        engine = create_engine('sqlite://')
        with engine.begin() as conn:
            conn.execute(text("ATTACH DATABASE ':memory:' AS public"))
            conn.connection.driver_connection.create_function('to_regclass', 1, lambda _: 'job_positions_catalog')
            conn.execute(text('CREATE TABLE public.positions(position_id INTEGER PRIMARY KEY, name TEXT)'))
            conn.execute(text('CREATE TABLE public.job_positions_catalog(job_code TEXT PRIMARY KEY, job_nameru TEXT, job_namekk TEXT, job_namekk_doc TEXT)'))
            conn.execute(text('CREATE TABLE public.position_job_catalog(position_id INTEGER PRIMARY KEY, job_code TEXT)'))
            conn.execute(text('CREATE TABLE public.person_assignments(assignment_id INTEGER PRIMARY KEY, position_id INTEGER)'))
            rows = read_catalog(SOURCE)
            ids = [pid for row in rows for pid in row['legacy_position_ids']]
            conn.execute(text('INSERT INTO public.positions VALUES (:id, :name)'), [{'id': pid, 'name': f'Old {pid}'} for pid in ids])
            conn.execute(text('INSERT INTO public.person_assignments VALUES (1, 27)'))
            before = conn.execute(text('SELECT * FROM public.positions')).all()
            class Adapter:
                def execute(self, query, params=None):
                    if str(query).startswith('LOCK TABLE'):
                        return None
                    return conn.execute(query, params or {})
            apply_catalog(Adapter(), rows)
            apply_catalog(Adapter(), rows)
            self.assertEqual(conn.execute(text('SELECT count(*) FROM public.job_positions_catalog')).scalar(), 88)
            self.assertEqual(conn.execute(text('SELECT count(*) FROM public.position_job_catalog')).scalar(), 108)
            self.assertEqual(conn.execute(text('SELECT * FROM public.positions')).all(), before)
            self.assertEqual(conn.execute(text('SELECT position_id FROM public.person_assignments')).scalar(), 27)
            conn.execute(text("UPDATE public.job_positions_catalog SET job_namekk_doc='Manual' WHERE job_code='NURSE'"))
            with self.assertRaises(ValueError):
                apply_catalog(Adapter(), rows)
            self.assertEqual(conn.execute(text("SELECT job_namekk_doc FROM public.job_positions_catalog WHERE job_code='NURSE'")).scalar(), 'Manual')

    def test_snapshot_priority_and_bilingual_generation(self):
        context = {'job_code': 'NURSE', 'position_name': 'Медицинская сестра', 'position_ru': 'Медицинская сестра', 'position_kk': 'мейіргері', 'org_unit_name': 'Отделение'}
        original = snapshot_catalog_forms({}, context)
        saved = json.loads(json.dumps(original))
        for type_code in ('HIRE', 'TRANSFER', 'TERMINATION', 'RETURN_FROM_CHILDCARE_LEAVE', 'LEAVE.ANNUAL.GRANT', 'LEAVE.UNPAID.GRANT', 'CONCURRENT_DUTY_START', 'CONCURRENT_DUTY_END', 'SUPPLEMENTARY_PAY'):
            with self.subTest(type=type_code):
                item = {'item_type_code': type_code, 'effective_date': '2026-10-05', 'payload': saved}
                ctx = build_item_ctx(item, 'Тест')
                self.assertEqual(ctx['position_document_nominative_ru'], 'Медицинская сестра')
                for locale, expected in [('ru', 'Медицинская сестра'), ('kk', 'мейіргері')]:
                    body = generate_item_body(locale, ctx)['generated_text']
                    self.assertTrue(body)
                    if type_code in ('HIRE', 'TRANSFER', 'TERMINATION', 'LEAVE.ANNUAL.GRANT', 'LEAVE.UNPAID.GRANT'):
                        self.assertIn(expected, body)
        changed_catalog = {**context, 'position_kk': 'Updated catalog'}
        self.assertEqual(snapshot_catalog_forms(saved, changed_catalog), saved)
        saved['document_forms_kk']['position_document_possessive_kk'] = 'Manual'
        self.assertEqual(snapshot_catalog_forms(saved, changed_catalog)['document_forms_kk']['position_document_possessive_kk'], 'Manual')
        self.assertEqual(effective_text('Manual editorial text', 'Generated text'), 'Manual editorial text')

    def test_templates_use_saved_forms_for_all_non_leave_types(self):
        from app.services.personnel_order_template_application_service import _values
        class Conn:
            def execute(self, *args): return self
            def mappings(self): return self
            def first(self): return {'full_name': 'Тест', 'position_name': 'Old position', 'org_unit_name': 'Old unit'}
        for code in ('HIRE', 'TRANSFER', 'TERMINATION', 'RETURN_FROM_CHILDCARE_LEAVE', 'CONCURRENT_DUTY_START', 'CONCURRENT_DUTY_END', 'SUPPLEMENTARY_PAY', 'LEAVE.ANNUAL.GRANT'):
            with self.subTest(type=code):
                values, _, _ = _values(Conn(), {'employee_id': 1, 'item_type_code': code, 'payload': {'document_forms_ru': {'position_document_nominative_ru': 'Ручная RU'}, 'document_forms_kk': {'position_document_possessive_kk': 'Ручная KK'}, 'source_org_unit_name': 'Справочное подразделение'}})
                self.assertEqual(values['position.title_ru'], 'Ручная RU')
                self.assertEqual(values['position.document_nominative_ru'], 'Ручная RU')
                self.assertEqual(values['position.title_kk'], 'Ручная KK')
                self.assertEqual(values['org_unit.title_ru'], 'Справочное подразделение')


    def test_nominal_titles_and_grammatical_forms_are_distinct_snapshots(self):
        from app.services.personnel_order_template_application_service import _values
        context={'job_code':'CLINICAL_DEPARTMENT_HEAD','position_title_ru':'Заведующий клиническим отделением',
            'position_title_kk':'Клиникалық бөлімше меңгерушісі','position_ru':'Заведующий клиническим отделением',
            'position_kk':'клиникалық бөлімшесінің меңгерушісі','org_unit_title_kk':'№1 химиотерапия бөлімшесі'}
        payload=snapshot_catalog_forms({'source_org_unit_name':'Химиотерапия 1'},context)
        class Conn:
            def execute(self,*args):return self
            def mappings(self):return self
            def first(self):return {'full_name':'Тест','position_name':'Historic department position','org_unit_name':'Historic unit'}
        values,_,_=_values(Conn(),{'employee_id':29,'item_type_code':'HIRE','payload':payload})
        self.assertEqual(values['position.title_kk'],context['position_title_kk'])
        self.assertEqual(values['position.document_possessive_kk'],context['position_kk'])
        self.assertEqual(values['position.title_ru'],context['position_title_ru'])
        self.assertEqual(values['org_unit.title_kk'],context['org_unit_title_kk'])
        self.assertEqual(snapshot_catalog_forms(payload,{**context,'position_title_kk':'Changed'}),payload)


if __name__ == '__main__':
    unittest.main()
