"""Run with unittest and an explicitly supplied disposable loopback database.

No application migrations, production connections, or production fixtures.
"""
import json
import os
import unittest
from datetime import date

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateTable


@unittest.skipUnless(os.environ.get("DEPARTMENT_ISOLATED_TESTS") == "1", "Requires task-owned disposable PostgreSQL")
class DepartmentIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = make_url(os.environ["DATABASE_URL"])
        assert url.host == "127.0.0.1" and url.port == 55440
        assert url.database == "corpsite_department_test"
        assert os.environ.get("CORPSITE_SKIP_DOTENV") == "1"
        from app.db.engine import engine as application_engine
        assert application_engine.url == url, "Application services must use the same isolated database"
        cls.engine = create_engine(url)
        from app.db.models import personnel_orders  # noqa: F401
        from app.db.base import Base
        with cls.engine.begin() as c:
            assert c.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")).scalar_one() == 0, "Use a fresh fixture database"
            c.execute(text("""
              CREATE TABLE org_units(unit_id integer PRIMARY KEY,name text,name_kk text,document_genitive_kk text);
              CREATE TABLE positions(position_id integer PRIMARY KEY,name text,document_nominative_ru text,document_possessive_kk text);
              CREATE TABLE employees(employee_id integer PRIMARY KEY,person_id integer,full_name text,position_id integer,org_unit_id integer);
              CREATE TABLE person_assignments(assignment_id integer PRIMARY KEY,person_id integer,position_id integer,org_unit_id integer,start_date date,end_date date,active_flag boolean,is_primary boolean,lifecycle_status text);
              CREATE TABLE users(user_id integer PRIMARY KEY);
              CREATE TABLE employee_events(event_id integer PRIMARY KEY,order_id bigint,order_item_id bigint);
              INSERT INTO org_units VALUES(1,'Отдел А','А бөлімі','А бөлімінің'),(2,'Отдел Б','Б бөлімі','Б бөлімінің'),(3,'Отдел без перевода',NULL,NULL);
              INSERT INTO positions VALUES(1,'Врач','врач','дәрігері'),(2,'Эксперт','эксперт','сарапшысы');
              INSERT INTO employees VALUES(1,1,'Fixture Employee',1,1);
              INSERT INTO person_assignments VALUES(1,1,1,1,'2020-01-01',NULL,true,true,'active');
              INSERT INTO users VALUES(1);
            """))
            for name in ("personnel_orders", "personnel_order_items", "personnel_order_localized_texts", "personnel_order_attachments", "personnel_order_prints", "personnel_order_editorial_blocks", "personnel_order_item_editorial_blocks", "personnel_order_item_bases", "personnel_order_lifecycle_audit"):
                c.execute(CreateTable(Base.metadata.tables[name], include_foreign_key_constraints=[]))
            c.execute(text("ALTER TABLE personnel_orders ADD COLUMN deleted_at timestamptz; CREATE TABLE personnel_order_evidence_scopes(order_id bigint PRIMARY KEY,generation bigint NOT NULL DEFAULT 0,updated_at timestamptz DEFAULT now());"))

    def fingerprint(self):
        with self.engine.connect() as c:
            return {table: c.execute(text(f"SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text")).scalars().all() for table in ("employees", "person_assignments", "employee_events")}

    def make_item(self, position="Врач", unit=2):
        from app.services.personnel_order_manual_draft_service import prepare_manual_item_payload
        before = self.fingerprint()
        with self.engine.begin() as c:
            payload = prepare_manual_item_payload(c, item_type_code="HIRE", employee_id=1, effective_date=date(2026, 10, 25), capabilities={"job_catalog_supported": True}, document_subject_context={"position_name": position, "document_org_unit_id": unit})
            order = c.execute(text("INSERT INTO personnel_orders(order_number,order_date,order_type_code,status,source_mode,created_by) VALUES ('FIXTURE','2026-10-25','HIRE','DRAFT','MANUAL',1) RETURNING order_id")).scalar_one()
            c.execute(text("INSERT INTO personnel_order_evidence_scopes(order_id) VALUES (:o)"), {"o":order})
            item = c.execute(text("INSERT INTO personnel_order_items(order_id,item_number,item_type_code,employee_id,effective_date,payload) VALUES (:o,1,'HIRE',1,'2026-10-25',CAST(:p AS jsonb)) RETURNING item_id"), {"o": order,"p": json.dumps(payload)}).scalar_one()
        self.assertEqual(before, self.fingerprint())
        return order, item, payload

    def test_create_patch_reopen_regenerate_and_catalog_changes(self):
        from app.services.personnel_order_document_item_service import list_document_items, patch_document_item
        from app.services.personnel_orders_editorial.generation_service import generate_editorial
        from app.services.personnel_order_template_application_service import _values
        before = self.fingerprint()
        order, item, payload = self.make_item()
        self.assertEqual(payload["source_org_unit_name"], "Отдел Б")
        self.assertEqual(payload["org_unit_title_kk"], "Б бөлімі")
        for position in ("Врач", "Эксперт"):
            result = patch_document_item(order_id=order, item_id=item, expected_document_revision=list_document_items(order_id=order)["document_revision"], item_type_code="HIRE", employee_id=1, effective_date=date(2026,10,25), document_subject_context={"document_org_unit_id":2,"position_name":position}, reason_code=None, reason_text=None, actor_user_id=1)
            saved = list_document_items(order_id=order)["items"][0]
            self.assertEqual(saved["document_org_unit_id"],2)
            self.assertEqual(saved["position_name"],position)
            self.assertEqual(saved["document_org_unit_genitive_kk"],"Б бөлімінің")
            generate_editorial(order,user_id=1)
            with self.engine.connect() as c:
                row = c.execute(text("SELECT * FROM personnel_order_items WHERE item_id=:i"), {"i":item}).mappings().one()
                values, _, _ = _values(c,row)
                self.assertEqual(values["org_unit.title_ru"],"Отдел Б")
                self.assertEqual(values["org_unit.title_kk"],"Б бөлімі")
                blocks = c.execute(text("SELECT locale,generated_text,review_status FROM personnel_order_item_editorial_blocks WHERE order_item_id=:i AND block_type='body'"), {"i":item}).mappings().all()
                self.assertEqual({r["locale"] for r in blocks},{"ru","kk"})
                for r in blocks:
                    self.assertIn("Отдел Б" if r["locale"]=="ru" else "Б бөлімінің",r["generated_text"])
                    self.assertNotEqual(r["review_status"],"GENERATION_FAILED")
        with self.engine.begin() as c:
            c.execute(text("UPDATE org_units SET name='Fixture rename',name_kk='Fixture rename KK' WHERE unit_id=2"))
        generate_editorial(order,user_id=1)
        saved = list_document_items(order_id=order)["items"][0]
        self.assertEqual(saved["org_unit_name"],"Отдел Б")
        patch_document_item(order_id=order,item_id=item,expected_document_revision=list_document_items(order_id=order)["document_revision"],item_type_code="HIRE",employee_id=1,effective_date=date(2026,10,25),document_subject_context={"document_org_unit_id":2,"specialty":"fixture"},reason_code=None,reason_text=None,actor_user_id=1)
        self.assertEqual(list_document_items(order_id=order)["items"][0]["org_unit_name"],"Отдел Б")
        with self.engine.begin() as c:
            c.execute(text("UPDATE org_units SET name='Отдел Б',name_kk='Б бөлімі' WHERE unit_id=2"))
        self.assertEqual(before,self.fingerprint())

    def test_invalid_department_rolls_back_whole_correction(self):
        from app.services.personnel_order_document_item_service import list_document_items, patch_document_item
        order,item,_=self.make_item(unit=1)
        before=list_document_items(order_id=order)
        with self.assertRaisesRegex(ValueError,"DOCUMENT_ORG_UNIT_NOT_FOUND"):
            patch_document_item(order_id=order,item_id=item,expected_document_revision=1,item_type_code="HIRE",employee_id=1,effective_date=date(2026,10,25),document_subject_context={"document_org_unit_id":99999,"position_name":"must roll back"},reason_code=None,reason_text=None,actor_user_id=1)
        self.assertEqual(before,list_document_items(order_id=order))
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT count(*) FROM personnel_order_lifecycle_audit WHERE order_id=:o"),{"o":order}).scalar_one(),0)

    def test_missing_kk_never_reuses_employee_department(self):
        from app.services.personnel_order_template_application_service import _values
        order,item,payload=self.make_item(unit=3)
        with self.engine.connect() as c:
            values,_,_=_values(c,{"payload":payload,"item_type_code":"HIRE","employee_id":1,"effective_date":date(2026,10,25)})
        self.assertEqual(values["org_unit.title_kk"],"")
        self.assertEqual(values["org_unit.document_genitive_kk"],"")

    def test_manual_kk_form_and_nominal_name_survive_correction(self):
        from app.services.personnel_order_document_item_service import list_document_items, patch_document_item
        from app.services.personnel_orders_editorial.generation_service import generate_editorial
        order,item,_=self.make_item(unit=1)
        before=self.fingerprint()
        patch_document_item(order_id=order,item_id=item,expected_document_revision=1,item_type_code="HIRE",employee_id=1,effective_date=date(2026,10,25),document_subject_context={"document_org_unit_id":2,"org_unit_name":"Отдел Б","document_org_unit_kk":"Қолмен түзетілген бөлім","document_org_unit_genitive_kk":"Қолмен түзетілген бөлімнің"},reason_code=None,reason_text=None,actor_user_id=1)
        generate_editorial(order,user_id=1)
        saved=list_document_items(order_id=order)["items"][0]
        self.assertEqual(saved["document_org_unit_kk"],"Қолмен түзетілген бөлім")
        self.assertEqual(saved["document_org_unit_genitive_kk"],"Қолмен түзетілген бөлімнің")
        with self.engine.connect() as c:
            generated=c.execute(text("SELECT generated_text FROM personnel_order_item_editorial_blocks WHERE order_item_id=:i AND locale='kk' AND block_type='body'"),{"i":item}).scalar_one()
            self.assertIn("Қолмен түзетілген бөлімнің",generated)
            metadata=c.execute(text("SELECT metadata_json FROM personnel_order_lifecycle_audit WHERE order_id=:o AND action='ITEM_UPDATED' ORDER BY id DESC LIMIT 1"),{"o":order}).scalar_one()
            self.assertEqual(metadata["after"]["document_subject_context"]["document_org_unit"]["unit_id"],2)
        self.assertEqual(before,self.fingerprint())

    def test_recall_uses_document_department_in_both_languages(self):
        from app.services.personnel_order_manual_draft_service import prepare_manual_item_payload
        from app.services.personnel_order_template_application_service import _values
        from app.services.personnel_order_recall_contract import render
        before=self.fingerprint()
        with self.engine.begin() as c:
            payload=prepare_manual_item_payload(c,item_type_code="LEAVE.ANNUAL.RECALL",employee_id=1,effective_date=date(2026,10,25),capabilities={"job_catalog_supported":True},document_subject_context={"document_org_unit_id":2,"position_name":"эксперт","document_org_unit_kk":"Б бөлімі"},item_payload={"recall_position_kk":"сарапшы","recall_org_unit_kk":"Б бөлімі","basis_ru":"Fixture RU","basis_kk":"Fixture KK"})
            # A legacy bilingual source must not override the manual snapshot.
            payload["org_unit_name"]={"ru":"Старый отдел","kk":"Ескі бөлім"}
            values,_,_=_values(c,{"payload":payload,"item_type_code":"LEAVE.ANNUAL.RECALL","employee_id":1,"effective_date":date(2026,10,25)})
            self.assertIn("Отдел Б",render("body_template_ru",values))
            self.assertIn("Б бөлімі",render("body_template_kk",values))
            self.assertEqual(values["position.title_ru"],"эксперт")
            self.assertEqual(values["position.title_kk"],"сарапшы")
        self.assertEqual(before,self.fingerprint())

    def test_unsnapshotted_legacy_item_uses_primary_assignment_not_employee_cache(self):
        from app.services.personnel_order_document_item_service import list_document_items
        order,item,_=self.make_item(unit=1)
        with self.engine.begin() as c:
            c.execute(text("UPDATE personnel_order_items SET payload='{}'::jsonb WHERE item_id=:i"),{"i":item})
            c.execute(text("UPDATE person_assignments SET org_unit_id=2,position_id=2 WHERE assignment_id=1"))
        try:
            saved=list_document_items(order_id=order)["items"][0]
            self.assertEqual(saved["org_unit_name"],"Отдел Б")
            self.assertEqual(saved["position_name"],"Эксперт")
        finally:
            with self.engine.begin() as c:
                c.execute(text("UPDATE person_assignments SET org_unit_id=1,position_id=1 WHERE assignment_id=1"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
