"""Opt-in PostgreSQL round trip; every write is rolled back in corpsite_test."""
import os
import sys
from contextlib import contextmanager, nullcontext
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.services import personnel_order_template_draft_service as drafts
from app.services import personnel_order_template_application_service as templates
from app.services import personnel_order_manual_draft_service as manual
from app.services import personnel_orders_command_service as commands
from app.services import personnel_orders_query_service as queries
from app.services.personnel_orders_editorial import generation_service
from app.services.personnel_order_childcare_contract import TYPE, TEXTS
from tests.test_personnel_order_childcare_template import childcare_payload


class RollbackEngine:
    def __init__(self, connection): self.connection = connection
    def connect(self): return nullcontext(self.connection)
    @contextmanager
    def begin(self):
        with self.connection.begin_nested():
            yield self.connection


def test_childcare_template_save_publish_create_edit_read_generate_apply(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("requires explicitly configured local corpsite_test")
    parsed = make_url(url)
    assert parsed.host in {"127.0.0.1", "localhost"} and parsed.database == "corpsite_test"
    engine = create_engine(url)
    with engine.connect() as conn:
        outer = conn.begin()
        try:
            adapter = RollbackEngine(conn)
            original = manual.engine
            for name, module in list(sys.modules.items()):
                if name.startswith("app.") and getattr(module, "engine", None) is original:
                    monkeypatch.setattr(module, "engine", adapter)
            assert conn.execute(text("select current_database()")).scalar_one() == "corpsite_test"
            assert not conn.execute(text("select 1 from personnel_order_template_versions where item_type_code=:t and status in ('DRAFT','PUBLISHED')"), {"t": TYPE}).first(), "Use a test database without a childcare working template"
            actor = conn.execute(text("select user_id from users order by user_id limit 1")).scalar_one()
            employee = conn.execute(text("select employee_id from employees where is_active order by employee_id limit 1")).scalar_one()
            # User fields 1–4 are persisted verbatim, including a pre-existing directive.
            values = {**TEXTS, "preamble_ru": TEXTS["preamble_ru"] + ", ПРИКАЗЫВАЮ:"}
            assert drafts.get_draft(TYPE) is None
            created = drafts.create_draft_from_working_copy(TYPE, "INITIAL", None, None, values, actor)
            reopened = drafts.get_draft(TYPE)
            assert all(reopened[k] == v for k, v in values.items())
            drafts.publish_draft(TYPE, created["revision"], actor)
            assert drafts.get_published(TYPE)["template_version_id"] == created["template_version_id"]
            payload = childcare_payload()
            result = manual.create_manual_draft(created_by=actor, order_number="CHILD-" + uuid4().hex[:10], order_date=date(2026, 7, 28), source_title=TEXTS["title_kk"], source_title_locale="kk", item_type_code=TYPE, employee_id=employee, effective_date=date(2026, 8, 1), period_start=date(2026, 8, 1), period_end=date(2029, 2, 13), item_payload=payload)
            order = result["order_id"]
            item = queries.get_personnel_order(order)["items"][0]
            assert item["payload"]["basis"] == payload["basis"]
            payload["basis"]["number"] = "APP-18"
            payload["basis"]["birth_certificate"]["number"] = "CERT-19"
            commands.update_personnel_order_item(order_id=order, item_id=item["item_id"], payload=payload)
            reopened = queries.get_personnel_order(order)["items"][0]
            for key in ("basis", "document_forms_ru", "document_forms_kk", "leave_start", "leave_end"):
                assert reopened["payload"][key] == payload[key]
            generation_service.generate_editorial(order, user_id=actor, conn=conn)
            preview = templates.preview_template_application(order)
            assert not any(x["missing_data"] for x in preview["items"])
            assert "ПРИКАЗЫВАЮ" not in preview["order_proposed"]["preamble_ru"]
            templates.apply_template_application(order, actor, expected_document_revision=1)
            blocks = conn.execute(text("select locale,block_type,generated_text from personnel_order_item_editorial_blocks where order_item_id=:id"), {"id": item["item_id"]}).mappings().all()
            assert len(blocks) == 4
            for block in blocks:
                assert "{{" not in block["generated_text"]
                if block["block_type"] == "basis":
                    assert "APP-18" in block["generated_text"] and "CERT-19" in block["generated_text"]
            kk = next(x["generated_text"] for x in blocks if x["locale"] == "kk" and x["block_type"] == "body")
            for value in (payload["document_forms_kk"][k] for k in ("org_unit_document_genitive_kk", "position_document_possessive_kk", "employee_full_name_dative_kk")):
                assert value in kk
        finally:
            outer.rollback()
    engine.dispose()
