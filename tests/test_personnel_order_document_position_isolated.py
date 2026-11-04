"""Dedicated synthetic database only; no production or working-database fixtures."""
import json
import os
import unittest
from datetime import date
from sqlalchemy import text
from sqlalchemy.engine import make_url


@unittest.skipUnless(os.environ.get("POSITION_ISOLATED_TESTS")=="1", "Requires task-owned fixture database")
class DocumentPositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url=make_url(os.environ["DATABASE_URL"])
        assert (url.host,url.port,url.database)==("127.0.0.1",55440,"corpsite_department_test")
        assert os.environ.get("CORPSITE_SKIP_DOTENV")=="1"
        from app.db.engine import engine
        assert engine.url==url
        cls.engine=engine

    def fingerprint(self):
        with self.engine.connect() as c:
            return {t:c.execute(text(f"SELECT row_to_json(t)::text FROM {t} t ORDER BY row_to_json(t)::text")).scalars().all() for t in ("employees","person_assignments","employee_events")}

    def create(self,position=2):
        from app.services.personnel_order_manual_draft_service import prepare_manual_item_payload
        from app.services.personnel_orders_editorial.generation_service import generate_editorial
        with self.engine.begin() as c:
            payload=prepare_manual_item_payload(c,item_type_code="HIRE",employee_id=2,effective_date=date(2026,10,25),capabilities={"job_catalog_supported":True},document_subject_context={"document_position_id":position})
            order=c.execute(text("INSERT INTO personnel_orders(order_number,order_date,order_type_code,status,source_mode,created_by) VALUES ('POSITION-UNIT','2026-10-25','HIRE','DRAFT','MANUAL',1) RETURNING order_id")).scalar_one()
            c.execute(text("INSERT INTO personnel_order_evidence_scopes(order_id) VALUES (:o)"),{"o":order})
            item=c.execute(text("INSERT INTO personnel_order_items(order_id,item_number,item_type_code,employee_id,effective_date,payload) VALUES (:o,1,'HIRE',2,'2026-10-25',CAST(:p AS jsonb)) RETURNING item_id"),{"o":order,"p":json.dumps(payload)}).scalar_one()
            generate_editorial(order,user_id=1,conn=c)
        return order,item

    def patch(self,order,item,context,revision=1):
        from app.services.personnel_order_document_item_service import patch_document_item
        return patch_document_item(order_id=order,item_id=item,expected_document_revision=revision,item_type_code="HIRE",employee_id=2,effective_date=date(2026,10,25),document_subject_context=context,reason_code=None,reason_text=None,actor_user_id=1)

    def test_create_expert_survives_read_and_regeneration_without_hr_changes(self):
        from app.services.personnel_order_document_item_service import list_document_items
        from app.services.personnel_order_template_application_service import _values
        from app.services.personnel_orders_editorial.generation_service import generate_editorial
        before=self.fingerprint();order,item=self.create()
        for _ in range(2):
            generate_editorial(order,user_id=1)
            saved=list_document_items(order_id=order)["items"][0]
            self.assertEqual(saved["document_position_id"],2)
            self.assertEqual(saved["position_name"],"Эксперт ОВЭиПД госпитальный")
            with self.engine.connect() as c:
                row=c.execute(text("SELECT * FROM personnel_order_items WHERE item_id=:i"),{"i":item}).mappings().one()
                values,_,_=_values(c,row)
                self.assertEqual(values["position.title_ru"],"Эксперт ОВЭиПД госпитальный")
                self.assertEqual(values["position.title_kk"],"Госпиталь сарапшысы")
                blocks=c.execute(text("SELECT locale,generated_text FROM personnel_order_item_editorial_blocks WHERE order_item_id=:i AND block_type='body'"),{"i":item}).mappings().all()
                self.assertEqual({r["locale"] for r in blocks},{"ru","kk"})
                for r in blocks:
                    self.assertNotIn("Архивариус",r["generated_text"])
                    self.assertIn("эксперт" if r["locale"]=="ru" else "госпиталь сарапшысының",r["generated_text"].lower())
        self.assertEqual(before,self.fingerprint())

    def test_patch_changes_only_document_position_and_is_audited(self):
        from app.services.personnel_order_document_item_service import list_document_items
        before=self.fingerprint();order,item=self.create(1)
        self.patch(order,item,{"document_position_id":2})
        saved=list_document_items(order_id=order)["items"][0]
        self.assertEqual(saved["document_position_id"],2)
        self.assertEqual(saved["document_position_kk"],"Госпиталь сарапшысы")
        with self.engine.connect() as c:
            metadata=c.execute(text("SELECT metadata_json FROM personnel_order_lifecycle_audit WHERE order_id=:o AND action='ITEM_UPDATED'"),{"o":order}).scalar_one()
            self.assertEqual(metadata["before"]["document_subject_context"]["document_position"]["position_id"],1)
            self.assertEqual(metadata["after"]["document_subject_context"]["document_position"]["position_id"],2)
        self.assertEqual(before,self.fingerprint())

    def test_invalid_id_rolls_back_and_repeat_is_noop(self):
        from app.services.personnel_order_document_item_service import list_document_items
        order,item=self.create();before=list_document_items(order_id=order)
        with self.assertRaisesRegex(ValueError,"DOCUMENT_POSITION_NOT_FOUND"):
            self.patch(order,item,{"document_position_id":999999,"position_name":"must roll back"})
        self.assertEqual(before,list_document_items(order_id=order))
        self.assertTrue(self.patch(order,item,{"document_position_id":2})["no_op"])

    def test_existing_snapshot_does_not_refresh_from_catalog(self):
        from app.services.personnel_order_document_item_service import list_document_items
        order,item=self.create()
        with self.engine.begin() as c:
            c.execute(text("UPDATE positions SET name='Fixture rename',name_kk='Fixture rename KK' WHERE position_id=2"))
        try:
            self.patch(order,item,{"document_position_id":2,"specialty":"fixture"})
            saved=list_document_items(order_id=order)["items"][0]
            self.assertEqual(saved["position_name"],"Эксперт ОВЭиПД госпитальный")
            self.assertEqual(saved["document_position_kk"],"Госпиталь сарапшысы")
        finally:
            with self.engine.begin() as c:
                c.execute(text("UPDATE positions SET name='Эксперт ОВЭиПД госпитальный',name_kk='Госпиталь сарапшысы' WHERE position_id=2"))

    def test_no_kk_does_not_reuse_archivist_translation(self):
        from app.services.personnel_order_document_item_service import list_document_items
        order,item=self.create(1)
        with self.engine.begin() as c:
            c.execute(text("UPDATE positions SET name_kk=NULL,document_possessive_kk=NULL WHERE position_id=3"))
        try:
            self.patch(order,item,{"document_position_id":3})
            saved=list_document_items(order_id=order)["items"][0]
            self.assertIn(saved["document_position_kk"],(None,""))
            self.assertIn(saved["document_position_possessive_kk"],(None,""))
            with self.engine.connect() as c:
                body=c.execute(text("SELECT generated_text FROM personnel_order_item_editorial_blocks WHERE order_item_id=:i AND locale='kk' AND block_type='body'"),{"i":item}).scalar_one()
                self.assertNotIn("мұрағат",body.lower())
        finally:
            with self.engine.begin() as c:
                c.execute(text("UPDATE positions SET name_kk='Дәрігер',document_possessive_kk='дәрігері' WHERE position_id=3"))

    def test_draft_command_validates_position_and_rolls_back_invalid_id(self):
        from unittest.mock import patch
        from app.services import personnel_orders_command_service as command
        before=self.fingerprint();order,item=self.create(1)
        with self.engine.connect() as c:
            original=c.execute(text("SELECT payload FROM personnel_order_items WHERE item_id=:i"),{"i":item}).scalar_one()
        incoming={**original,"document_position":{**original["document_position"],"position_id":999999}}
        with patch.object(command,"get_personnel_order",return_value={}):
            with self.assertRaisesRegex(ValueError,"DOCUMENT_POSITION_NOT_FOUND"):
                command.update_personnel_order_item(order_id=order,item_id=item,payload=incoming,actor_user_id=1)
        with self.engine.connect() as c:
            self.assertEqual(original,c.execute(text("SELECT payload FROM personnel_order_items WHERE item_id=:i"),{"i":item}).scalar_one())
        self.assertEqual(before,self.fingerprint())

    def test_repreparing_saved_item_preserves_its_selected_position(self):
        from app.services.personnel_order_manual_draft_service import prepare_manual_item_payload
        order,item=self.create(2)
        with self.engine.begin() as c:
            payload=c.execute(text("SELECT payload FROM personnel_order_items WHERE item_id=:i"),{"i":item}).scalar_one()
            prepared=prepare_manual_item_payload(c,item_type_code="HIRE",employee_id=2,effective_date=date(2026,10,25),item_payload=payload,capabilities={"job_catalog_supported":True})
        self.assertEqual(prepared["document_position"]["position_id"],2)
        self.assertEqual(prepared["source_position_name"],"Эксперт ОВЭиПД госпитальный")


if __name__=="__main__":unittest.main(verbosity=2)
