"""Synthetic HIRE lifecycle tests, restricted to a dedicated schema-only database."""
import os
import unittest
from datetime import date
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import text

from app.services.personnel_order_hire_new_employee import normalize_new_employee, new_employee_full_name
from app.services.personnel_orders_query_service import PersonnelOrderValidationError


class HireNameContractTests(unittest.TestCase):
    def test_optional_patronymic_and_original_spelling(self):
        value = normalize_new_employee({"last_name": "  Синтетиков ", "first_name": "Сынақ", "middle_name": ""})
        self.assertEqual(new_employee_full_name(value), "Синтетиков Сынақ")

    def test_last_and_first_names_required(self):
        for value in ({}, {"last_name": "Синтетиков"}, {"first_name": "Тест"}, {"last_name": " ", "first_name": "Тест"}):
            with self.assertRaises(PersonnelOrderValidationError):
                normalize_new_employee(value)


@unittest.skipUnless(os.environ.get("HIRE_NEW_EMPLOYEE_ISOLATED_TESTS") == "1", "Requires dedicated synthetic HIRE database")
class HireNewEmployeeLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.db.engine import engine
        assert engine.url.host == "127.0.0.1" and engine.url.database == "corpsite_hire_new_employee_20261104_test"
        assert os.environ.get("CORPSITE_SKIP_DOTENV") == "1"
        cls.engine = engine
        from tests.conftest import create_deps_group, create_unit, create_non_privileged_role, create_user, insert_returning_id
        from app.services.personnel_order_template_initial_data import INITIAL_TEXTS_BY_TYPE
        with engine.begin() as conn:
            group = create_deps_group(conn, f"SYNTHETIC-HIRE-{uuid4().hex[:8]}")
            cls.unit = create_unit(conn, "SYNTHETIC HIRE UNIT", group_id=group)
            role = create_non_privileged_role(conn, f"SYNTHETIC-HIRE-{uuid4().hex[:8]}")
            cls.actor = create_user(conn, full_name="SYNTHETIC HIRE OPERATOR", role_id=role, unit_id=cls.unit)
            cls.position = insert_returning_id(conn, table="positions", id_col="position_id", values={"name": "SYNTHETIC HIRE POSITION", "category": "medical"})
            template = insert_returning_id(conn, table="personnel_order_templates", id_col="template_id", values={
                "item_type_code": "HIRE", "name_ru": "SYNTHETIC HIRE", "name_kk": "SYNTHETIC HIRE", "is_default": False})
            cls.version = insert_returning_id(conn, table="personnel_order_template_versions", id_col="template_version_id", values={
                **INITIAL_TEXTS_BY_TYPE['HIRE'],
                "template_id": template, "item_type_code": "HIRE", "version_number": 1, "status": "PUBLISHED",
                "print_title_ru": "О приёме на работу", "print_title_kk": "Жұмысқа қабылдау туралы",
            })

    def counts(self):
        with self.engine.connect() as conn:
            return {table: conn.execute(text(f"SELECT count(*) FROM public.{table}")).scalar_one()
                    for table in ("persons", "employees", "person_assignments", "employee_events")}

    def create(self, value, *, number=None, rate="0,75", basis="SYNTHETIC APPLICATION", position_kk="SYNTHETIC POSITION KK", position_kk_form=None, effective=date(2026, 11, 4), hire_details=None, locale='ru', paired_basis=None):
        from app.services.personnel_order_manual_draft_service import create_manual_draft
        return create_manual_draft(created_by=self.actor, template_version_id=self.version,
            order_number=number or f"SYNTHETIC-HIRE-{uuid4().hex[:12]}", order_date=date(2026, 11, 4),
            source_title="Жұмысқа қабылдау туралы" if locale == 'kk' else "О приёме на работу", source_title_locale=locale, item_type_code="HIRE",
            employee_id=None, unresolved_subject={"full_name": new_employee_full_name(value)}, effective_date=effective,
            document_subject_context={"org_unit_name": "SYNTHETIC HIRE UNIT", "document_org_unit_kk": "SYNTHETIC UNIT KK",
                "position_name": "SYNTHETIC HIRE POSITION", "document_position_kk": position_kk,
                "document_position_possessive_kk": position_kk_form},
            item_payload={"new_employee": value, "org_unit_id": self.unit, "position_id": self.position,
                **({'hire_details': hire_details} if hire_details is not None else {}),
                **({"document_forms_kk": {"position_document_possessive_kk": position_kk_form}} if position_kk_form is not None else {}),
                "employment_rate": rate, "basis_other_text": basis, "hire_basis":paired_basis if paired_basis is not None else {"ru":basis,"kk":basis}})

    def test_historical_certificate_names_and_intentionally_empty_kk_roundtrip(self):
        from app.services.personnel_orders_command_service import update_personnel_order_item
        from app.services.personnel_orders_query_service import get_personnel_order
        from app.services.personnel_order_template_application_service import preview_template_application
        before=self.counts()
        for locale in ('ru','kk'):
            name={'last_name':'Синтетиков'+uuid4().hex[:8],'first_name':'Сынақ','middle_name':''}
            certificate={'specialty':None,'issued_on':'2020-01-05','name_ru':'Лучевая диагностика','name_kk':'Сәулелік диагностика'}
            pair={'ru':'личное заявление, трудовой договор','kk':'','kk_intentionally_empty':True}
            created=self.create(name,locale=locale,paired_basis=pair,hire_details={'certificate':certificate})
            oid=created['order_id']
            first=get_personnel_order(oid)['items'][0]
            self.assertEqual(first['payload']['hire_details']['certificate'],certificate)
            self.assertEqual(first['payload']['hire_basis'],pair)
            preview=preview_template_application(oid)
            self.assertFalse(preview['items'][0]['blocked'],preview)
            self.assertEqual(preview['items'][0]['proposed']['basis_kk'],'')
            linked={**certificate,'specialty':{'medical_specialty_id':41,'name_ru':'Радиология','name_kk':'Радиология'}}
            update_personnel_order_item(order_id=oid,item_id=first['item_id'],actor_user_id=self.actor,
                payload={**first['payload'],'hire_details':{**first['payload']['hire_details'],'certificate':linked}})
            saved=get_personnel_order(oid)['items'][0]['payload']
            self.assertEqual(saved['hire_details']['certificate'],linked)
            self.assertEqual(saved['hire_basis'],pair)
        self.assertEqual(self.counts(),before)

    def test_hire_basis_and_certificate_create_add_edit_reopen_in_both_source_languages(self):
        from app.services.personnel_orders_command_service import create_personnel_order_item,update_personnel_order_item
        from app.services.personnel_orders_query_service import get_personnel_order
        from app.services.personnel_order_template_application_service import preview_template_application
        from app.services.personnel_order_hire_terms import default_hire_basis
        before=self.counts()
        defaults={locale:default_hire_basis(locale) for locale in ('ru','kk')}
        specialty={'medical_specialty_id':7,'name_ru':'SYNTHETIC CERT RU','name_kk':'SYNTHETIC CERT KK'}
        for source in ('ru','kk'):
            name={'last_name':'Синтетиков'+uuid4().hex[:8],'first_name':'Сынақ','middle_name':''}
            created=self.create(name,locale=source,paired_basis=defaults,hire_details={'certificate':{'specialty':None,'issued_on':''}})
            oid=created['order_id']
            create_personnel_order_item(order_id=oid,item_type_code='HIRE',actor_user_id=self.actor,
                template_version_id=self.version,effective_date=date(2026,11,4),unresolved_subject={'full_name':new_employee_full_name(name)},
                document_subject_context={'position_name':'SYNTHETIC RU','document_position_kk':'SYNTHETIC KK','org_unit_name':'SYNTHETIC RU UNIT','document_org_unit_kk':'SYNTHETIC KK UNIT'},
                payload={'new_employee':name,'employment_rate':1,'hire_basis':{'ru':'Ручное RU','kk':'Қолмен KK'},
                    'hire_details':{'certificate':{'specialty':specialty,'issued_on':'2026-02-02'}}})
            restored=get_personnel_order(oid)
            self.assertEqual(restored['order']['source_title_locale'],source)
            self.assertEqual(restored['items'][0]['payload']['hire_basis'],defaults)
            second=restored['items'][1]
            self.assertEqual(second['payload']['hire_details']['certificate'],{'specialty':specialty,'issued_on':'2026-02-02'})
            preview=preview_template_application(oid)
            for locale in ('ru','kk'):
                self.assertIn(defaults[locale],preview['items'][0]['proposed']['basis_'+locale])
                self.assertIn('Ручное RU' if locale=='ru' else 'Қолмен KK',preview['items'][1]['proposed']['basis_'+locale])
            updated={**second['payload'],'hire_basis':{'ru':'ИЗМЕНЕНО RU','kk':'ӨЗГЕРТІЛДІ KK'},
                'hire_details':{**second['payload']['hire_details'],'certificate':{'specialty':specialty,'issued_on':''}}}
            update_personnel_order_item(order_id=oid,item_id=second['item_id'],actor_user_id=self.actor,payload=updated)
            actual=get_personnel_order(oid)['items'][1]['payload']
            self.assertEqual(actual['hire_basis'],updated['hire_basis'])
            self.assertEqual(actual['hire_details']['certificate'],updated['hire_details']['certificate'])
        self.assertEqual(self.counts(),before)

    def test_decimal_hire_years_create_add_edit_and_clear_for_both_initial_languages(self):
        from app.services.personnel_orders_command_service import create_personnel_order_item, update_personnel_order_item
        from app.services.personnel_orders_query_service import get_personnel_order
        before = self.counts()
        for locale, raw in (('ru','17,3'),('kk','17.3')):
            with self.subTest(locale=locale):
                name={'last_name':'Синтетиков'+uuid4().hex[:8],'first_name':'Сынақ','middle_name':''}
                legacy={'ru':'17 лет и 3 месяца, по архиву','kk':'Мұрағат мәтіні'}
                created=self.create(name,locale=locale,hire_details={'service_length':legacy,'service_length_years':raw})
                oid=created['order_id']
                first=self.item(oid)
                self.assertEqual(first['payload']['hire_details']['service_length_years'],'17.3')
                self.assertEqual(first['payload']['hire_details']['service_length'],legacy)
                create_personnel_order_item(order_id=oid,item_type_code='HIRE',actor_user_id=self.actor,
                    template_version_id=self.version,effective_date=date(2026,11,4),
                    unresolved_subject={'full_name':new_employee_full_name(name)},
                    document_subject_context={'position_name':'SYNTHETIC RU','document_position_kk':'SYNTHETIC KK',
                        'org_unit_name':'SYNTHETIC RU UNIT','document_org_unit_kk':'SYNTHETIC KK UNIT'},
                    payload={'new_employee':name,'employment_rate':1,'basis_other_text':'SYNTHETIC','hire_basis':{'ru':'SYNTHETIC','kk':'SYNTHETIC'},'hire_details':{'service_length_years':0}})
                items=get_personnel_order(oid)['items']
                self.assertEqual(items[1]['payload']['hire_details']['service_length_years'],'0')
                for value in ('21,5','0',''):
                    payload={**first['payload'],'hire_details':{**first['payload']['hire_details'],'service_length_years':value}}
                    update_personnel_order_item(order_id=oid,item_id=first['item_id'],actor_user_id=self.actor,payload=payload)
                    restored=get_personnel_order(oid)
                    self.assertEqual(restored['order']['source_title_locale'],locale)
                    self.assertEqual(restored['items'][0]['payload']['hire_details']['service_length_years'],value.replace(',','.'))
                    self.assertEqual(restored['items'][0]['payload']['hire_details']['service_length'],legacy)
        self.assertEqual(self.counts(),before)

    def test_optional_hire_details_create_add_edit_clear_and_reopen_without_hr_changes(self):
        from copy import deepcopy
        from app.services.personnel_orders_command_service import create_personnel_order_item, update_personnel_order_item
        from app.services.personnel_orders_query_service import get_personnel_order
        details = {'education': {'code': 'HIGHER', 'ru': 'Высшее TEST', 'kk': 'Жоғары TEST'},
                   'service_length': {'ru': '  5 лет, по документам  ', 'kk': '5 жыл, құжат бойынша'}}
        before = self.counts()
        name = {'last_name': 'Синтетиков' + uuid4().hex[:8], 'first_name': 'Сынақ', 'middle_name': ''}
        created = self.create(name, hire_details=details)
        oid = created['order_id']
        self.assertEqual(self.item(oid)['payload']['hire_details'], details)
        create_personnel_order_item(order_id=oid, item_type_code='HIRE', actor_user_id=self.actor,
            template_version_id=self.version, effective_date=date(2026, 11, 4),
            unresolved_subject={'full_name': new_employee_full_name(name)},
            document_subject_context={'position_name':'SYNTHETIC RU POSITION','document_position_kk':'SYNTHETIC KK POSITION',
                'org_unit_name':'SYNTHETIC RU UNIT','document_org_unit_kk':'SYNTHETIC KK UNIT'},
            payload={'new_employee':name,'employment_rate':1,'basis_other_text':'SYNTHETIC','hire_basis':{'ru':'SYNTHETIC','kk':'SYNTHETIC'}})
        restored = get_personnel_order(oid)
        self.assertEqual(restored['items'][0]['payload']['hire_details'], details)
        self.assertNotIn('hire_details', restored['items'][1]['payload'])
        for index, item in enumerate(restored['items']):
            updated = deepcopy(details)
            updated['service_length']['ru'] = f'SYNTHETIC EDITED {index}'
            update_personnel_order_item(order_id=oid, item_id=item['item_id'], actor_user_id=self.actor,
                payload={**item['payload'], 'hire_details':updated})
            actual = get_personnel_order(oid)['items'][index]
            self.assertEqual(actual['payload']['hire_details'], updated)
        first = get_personnel_order(oid)['items'][0]
        blank = {'education':{'code':'','ru':'','kk':''},'service_length':{'ru':'','kk':''}}
        update_personnel_order_item(order_id=oid,item_id=first['item_id'],actor_user_id=self.actor,
            payload={**first['payload'],'hire_details':blank})
        self.assertEqual(get_personnel_order(oid)['items'][0]['payload']['hire_details'], blank)
        self.assertEqual(self.counts(), before)

    def test_hire_date_preview_and_saved_print_blocks_keep_iso_storage_and_manual_overrides(self):
        from app.services.personnel_order_template_application_service import preview_template_application
        from app.services.personnel_orders_editorial.generation_service import generate_editorial
        from app.services.personnel_orders_editorial.service import patch_editorial_block, get_editorial_state
        name = {'last_name': 'Синтетиков' + uuid4().hex[:8], 'first_name': 'Сынақ', 'middle_name': ''}
        created = self.create(name, effective=date(2026, 2, 2))
        oid = created['order_id']
        expected = {'ru': 'с 02.02.2026', 'kk': '2026 жылғы 2 ақпаннан бастап'}
        preview = preview_template_application(oid)
        item = self.item(oid)
        self.assertEqual(item['effective_date'], date(2026, 2, 2))
        state = get_editorial_state(oid)
        for block in state['items'][0]['blocks']:
            if block['block_type'] != 'body': continue
            locale = block['locale']
            self.assertIn(expected[locale], preview['items'][0]['proposed']['body_' + locale])
            self.assertIn(expected[locale], block['generated_text'])
            patch_editorial_block(oid, block['block_id'], user_id=self.actor,
                override_text='SYNTHETIC MANUAL ' + locale + ' 2026-02-02')
        generate_editorial(oid, user_id=self.actor)
        for block in get_editorial_state(oid)['items'][0]['blocks']:
            if block['block_type'] == 'body':
                self.assertEqual(block['effective_text'], 'SYNTHETIC MANUAL ' + block['locale'] + ' 2026-02-02')
        self.assertEqual(self.item(oid)['effective_date'], date(2026, 2, 2))

    def test_manual_kk_position_form_survives_creation_add_item_and_reopen(self):
        from app.services.personnel_orders_command_service import create_personnel_order_item, update_personnel_order_item
        from app.services.personnel_order_template_application_service import preview_template_application
        from app.services.personnel_orders_query_service import get_personnel_order

        before = self.counts()
        first_form, second_form = 'Сынақ бірінші лауазымы', 'Сынақ екінші лауазымы'
        name = {'last_name': 'Синтетиков' + uuid4().hex[:8], 'first_name': 'Сынақ', 'middle_name': ''}
        created = self.create(name, position_kk='', position_kk_form=first_form)
        oid = created['order_id']
        create_personnel_order_item(order_id=oid, item_type_code='HIRE', actor_user_id=self.actor,
            template_version_id=self.version, effective_date=date(2026, 11, 4),
            unresolved_subject={'full_name': new_employee_full_name(name)},
            document_subject_context={'position_name': 'SYNTHETIC RU POSITION', 'document_position_kk': '',
                'document_position_possessive_kk': second_form, 'document_org_unit_kk': 'SYNTHETIC KK UNIT',
                'org_unit_name': 'SYNTHETIC RU UNIT'},
            payload={'new_employee': name, 'employment_rate': 1, 'basis_other_text': 'SYNTHETIC', 'hire_basis':{'ru':'SYNTHETIC','kk':'SYNTHETIC'},
                'document_forms_kk': {'position_document_possessive_kk': second_form}})
        detail = get_personnel_order(oid)
        self.assertEqual(len(detail['items']), 2)
        for item, form in zip(detail['items'], (first_form, second_form)):
            self.assertEqual(item['payload']['document_forms_kk']['position_document_possessive_kk'], form)
            self.assertEqual(item['payload']['document_position']['name_kk'], '')
            update_personnel_order_item(order_id=oid, item_id=item['item_id'], actor_user_id=self.actor,
                payload=item['payload'])
        preview = preview_template_application(oid)
        for entry, form in zip(preview['items'], (first_form, second_form)):
            self.assertFalse(entry['blocked'], entry)
            self.assertIn(form, entry['proposed']['body_kk'])
        self.assertEqual(self.counts(), before)

    def test_hire_without_kk_position_is_still_rejected(self):
        name = {'last_name': 'Синтетиков' + uuid4().hex[:8], 'first_name': 'Сынақ', 'middle_name': ''}
        with self.engine.connect() as conn:
            before = conn.execute(text('SELECT count(*) FROM personnel_orders')).scalar_one()
        with self.assertRaisesRegex(ValueError, 'position.title_kk'):
            self.create(name, position_kk='', position_kk_form='')
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text('SELECT count(*) FROM personnel_orders')).scalar_one(), before)

    def item(self, order_id):
        with self.engine.connect() as conn:
            return dict(conn.execute(text("SELECT * FROM personnel_order_items WHERE order_id=:id"), {"id": order_id}).mappings().one())

    def test_full_draft_reopen_edit_bilingual_preview_apply_and_duplicate(self):
        from app.services.personnel_orders_command_service import update_personnel_order_item, register_personnel_order
        from app.services.personnel_order_template_application_service import preview_template_application, apply_template_application
        from app.services.personnel_orders_apply_service import apply_personnel_order, PersonnelOrderAlreadyAppliedError
        from app.services.personnel_orders_query_service import get_personnel_order

        for patronymic in ("", "Синтетикович"):
            with self.subTest(patronymic=patronymic):
                value = {"last_name": f"Синтетиков{uuid4().hex[:8]}", "first_name": "Тест", "middle_name": patronymic}
                before = self.counts()
                created = self.create(value)
                oid = created["order_id"]
                item = self.item(oid)
                self.assertIsNone(item["employee_id"])
                self.assertEqual(item["payload"]["new_employee"], value)
                self.assertEqual(item['payload']['employment_rate'], 0.75)
                self.assertEqual(item['payload']['basis_other_text'], 'SYNTHETIC APPLICATION')
                self.assertEqual(self.counts(), before)
                detail = get_personnel_order(oid)
                self.assertEqual(detail["items"][0]["payload"]["new_employee"], value)
                value = {**value, "first_name": "Сынақ"}
                payload = {**item["payload"], "new_employee": value}
                update_personnel_order_item(order_id=oid, item_id=item["item_id"], actor_user_id=self.actor,
                    unresolved_subject={"full_name": new_employee_full_name(value)}, payload=payload)
                item = self.item(oid)
                self.assertEqual(item["payload"]["new_employee"], value)
                self.assertEqual(item["payload"]["source_employee_name"], new_employee_full_name(value))
                self.assertEqual(self.counts(), before)
                preview = preview_template_application(oid)
                self.assertFalse(preview["items"][0]["blocked"], preview)
                for locale in ("ru", "kk"):
                    self.assertIn(new_employee_full_name(value), preview["items"][0]["proposed"][f"body_{locale}"])
                    self.assertIn('0.75', preview['items'][0]['proposed'][f'body_{locale}'])
                    self.assertIn('SYNTHETIC APPLICATION', preview['items'][0]['proposed'][f'basis_{locale}'])
                apply_template_application(oid, self.actor, expected_document_revision=preview["order_revision"], confirm_reapply=True)
                # The saved editorial blocks are the source consumed by RU/KK print.
                with self.engine.connect() as conn:
                    blocks = conn.execute(text("SELECT locale, generated_text, override_text FROM personnel_order_item_editorial_blocks WHERE order_item_id=:id AND block_type='body'"), {"id": item["item_id"]}).mappings().all()
                self.assertEqual({block["locale"] for block in blocks}, {"ru", "kk"})
                for block in blocks:
                    self.assertIn(new_employee_full_name(value), block["override_text"] or block["generated_text"])
                self.assertEqual(self.counts(), before)
                register_personnel_order(order_id=oid, target_status="REGISTERED")
                apply_personnel_order(order_id=oid, created_by=self.actor)
                item = self.item(oid)
                self.assertIsNotNone(item["employee_id"])
                after = self.counts()
                self.assertEqual(after, {key: count + 1 for key, count in before.items()})
                with self.engine.connect() as conn:
                    employee = conn.execute(text("SELECT e.full_name, e.is_active, p.last_name, p.first_name, p.middle_name FROM employees e JOIN persons p USING(person_id) WHERE employee_id=:id"), {"id": item["employee_id"]}).mappings().one()
                self.assertEqual(employee["full_name"], new_employee_full_name(value))
                self.assertTrue(employee["is_active"])
                self.assertEqual(employee["last_name"], value["last_name"])
                self.assertEqual(employee["middle_name"] or "", patronymic)
                with self.assertRaises(PersonnelOrderAlreadyAppliedError):
                    apply_personnel_order(order_id=oid, created_by=self.actor)
                self.assertEqual(self.counts(), after)
                duplicate = self.create({**value, "middle_name": "Другое"})
                register_personnel_order(order_id=duplicate["order_id"], target_status="REGISTERED")
                with self.assertRaisesRegex(PersonnelOrderValidationError, "Возможный дубликат"):
                    apply_personnel_order(order_id=duplicate["order_id"], created_by=self.actor)
                self.assertEqual(self.counts(), after)
                self.assertIsNone(self.item(duplicate["order_id"])["employee_id"])

    def test_failed_apply_rolls_back_person_employee_and_links(self):
        from app.services import personnel_orders_apply_service as service
        from app.services.personnel_orders_command_service import register_personnel_order
        value = {"last_name": f"Синтетиков{uuid4().hex[:8]}", "first_name": "Rollback", "middle_name": ""}
        created = self.create(value)
        oid = created["order_id"]
        register_personnel_order(order_id=oid, target_status="REGISTERED")
        before = self.counts()
        with patch.object(service, "_apply_item_events", side_effect=RuntimeError("synthetic apply failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic apply failure"):
                service.apply_personnel_order(order_id=oid, created_by=self.actor)
        self.assertEqual(self.counts(), before)
        item = self.item(oid)
        self.assertIsNone(item["employee_id"])
        self.assertNotIn("person_id", item["payload"])

    def test_terms_are_required_before_inserting_a_header_and_survive_editing(self):
        from app.services.personnel_orders_command_service import update_personnel_order_item
        from app.services.personnel_order_template_application_service import preview_template_application
        value = {"last_name": f"SYNTHETIC{uuid4().hex[:8]}", "first_name": "TERMS", "middle_name": ""}
        for overrides, message in (({'rate': ''}, 'Укажите ставку'), ({'basis': ' '}, 'Заполните основание')):
            number = f'SYNTHETIC-MISSING-TERMS-{uuid4().hex[:8]}'
            with self.assertRaisesRegex(PersonnelOrderValidationError, message):
                self.create(value, number=number, **overrides)
            with self.engine.connect() as conn:
                self.assertEqual(conn.execute(text('SELECT count(*) FROM personnel_orders WHERE order_number=:n'), {'n': number}).scalar_one(), 0)
        created = self.create(value)
        oid = created['order_id']
        saved = self.item(oid)
        edited_payload = {**saved['payload'], 'employment_rate': '0,5', 'basis_other_text': 'SYNTHETIC UPDATED BASIS',
            'basis_entries': [{'document_type': 'OTHER', 'basis_id': '', 'other_text': 'SYNTHETIC UPDATED BASIS'}]}
        update_personnel_order_item(order_id=oid, item_id=saved['item_id'], actor_user_id=self.actor,
                                    unresolved_subject={'full_name': new_employee_full_name(value)}, payload=edited_payload)
        reopened = self.item(oid)
        self.assertEqual(reopened['payload']['employment_rate'], 0.5)
        self.assertEqual(reopened['payload']['basis_other_text'], 'SYNTHETIC UPDATED BASIS')
        preview = preview_template_application(oid)
        self.assertFalse(preview['items'][0]['blocked'], preview)
        for locale in ('ru', 'kk'):
            self.assertIn('0.5', preview['items'][0]['proposed'][f'body_{locale}'])
            self.assertIn('SYNTHETIC UPDATED BASIS', preview['items'][0]['proposed'][f'basis_{locale}'])

    def test_existing_applicant_person_id_still_uses_the_original_apply_path(self):
        from app.personnel_applications.application.registration_service import _insert_person, _materialize_ppr_participating
        from app.ppr.domain.models import HR_RELATIONSHIP_CANDIDATE
        from app.services.personnel_orders_command_service import create_personnel_order_draft_tx, create_personnel_order_item_tx, register_personnel_order
        from app.services.personnel_orders_apply_service import apply_personnel_order
        with self.engine.begin() as conn:
            pid = _insert_person(conn, full_name=f"SYNTHETIC APPLICANT {uuid4().hex[:10]}", iin=None, birth_date=None)
            _materialize_ppr_participating(conn, person_id=pid, hr_relationship_context=HR_RELATIONSHIP_CANDIDATE, actor_id=str(self.actor))
            oid = create_personnel_order_draft_tx(conn, created_by=self.actor,
                order_number=f"SYNTHETIC-APPLICANT-{uuid4().hex[:10]}", order_date=date(2026, 11, 4), order_type_code="HIRE")
            create_personnel_order_item_tx(conn, order_id=oid, item_type_code="HIRE", effective_date=date(2026, 11, 4),
                employee_id=None, payload={"person_id": pid, "org_unit_id": self.unit, "position_id": self.position, "employment_rate": 1})
        before = self.counts()
        register_personnel_order(order_id=oid, target_status="REGISTERED")
        apply_personnel_order(order_id=oid, created_by=self.actor)
        after = self.counts()
        self.assertEqual(after["persons"], before["persons"])
        for table in ("employees", "person_assignments", "employee_events"):
            self.assertEqual(after[table], before[table] + 1)
        self.assertIsNotNone(self.item(oid)["employee_id"])

    def test_duplicate_of_another_type_and_failed_creation_leave_no_hire_header(self):
        from app.services.personnel_orders_command_service import create_personnel_order_draft_tx
        from app.services.personnel_order_document_header_service import PersonnelOrderDuplicateError
        from app.services import personnel_order_manual_draft_service as manual
        number = f"SYNTHETIC-DUPLICATE-{uuid4().hex[:10]}"
        with self.engine.begin() as conn:
            existing = create_personnel_order_draft_tx(conn, created_by=self.actor, order_number=number,
                order_date=date(2026, 11, 4), order_type_code="COMPOSITE")
        value = {"last_name": f"SYNTHETIC{uuid4().hex[:8]}", "first_name": "NO-ORPHAN", "middle_name": ""}
        before = self.counts()
        with self.assertRaises(PersonnelOrderDuplicateError) as failure:
            self.create(value, number=number)
        self.assertEqual(failure.exception.duplicate["candidates"][0]["order_id"], existing)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM personnel_orders WHERE order_number=:n"), {"n": number}).scalar_one(), 1)
        failed_number = f"SYNTHETIC-ROLLBACK-{uuid4().hex[:10]}"
        with patch.object(manual, "generate_editorial", side_effect=RuntimeError("synthetic generation failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic generation failure"):
                self.create(value, number=failed_number)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM personnel_orders WHERE order_number=:n"), {"n": failed_number}).scalar_one(), 0)
        self.assertEqual(self.counts(), before)
