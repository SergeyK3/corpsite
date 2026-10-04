"""Rollback-only integration coverage for multi-item unpaid template application."""
from __future__ import annotations

import json
import os
from contextlib import nullcontext

import pytest
from sqlalchemy import create_engine, text

from app.services import personnel_order_template_application_service as service
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_orders_editorial import service as editorial_service
from app.services.personnel_orders_editorial import generation_service


URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif("corpsite_test" not in URL, reason="requires TEST_DATABASE_URL=corpsite_test")


class _Engine:
    def __init__(self, connection): self.connection = connection
    def connect(self): return nullcontext(self.connection)
    def begin(self): return nullcontext(self.connection)


def _payload(index: int, kind: str = "CONTINUOUS_RANGE") -> dict:
    leave: dict = {"period_type": kind, "days": 1 if kind == "SINGLE_DAY" else 2}
    if kind == "SINGLE_DAY": leave.update({"start": "2026-07-07", "end": "2026-07-07"})
    else: leave.update({"start": "2026-07-13", "end": "2026-07-14"})
    return {
        "employee": {"name": {
            "canonical": f"Employee {index}",
            "full_name_dative_ru": f"Employee {index} RU",
            "full_name_dative_kk": f"Employee {index} KK-dative",
            "full_name_genitive_kk": f"Employee {index} KK-genitive",
        }},
        "position_name": {
            "ru": f"Position {index}", "kk": f"Position {index} KK",
            "document_nominative_ru": f"position {index}",
            "document_possessive_kk": f"position {index} KK-possessive",
        },
        "org_unit_name": {
            "ru": f"Unit {index}", "kk": f"Unit {index} KK",
            "document_genitive_kk": f"Unit {index} KK-genitive",
        },
        "document_forms_ru": {
            "employee_full_name_dative_ru": f"Employee {index} RU",
            "position_document_nominative_ru": f"position {index}",
        },
        "document_forms_kk": {
            "org_unit_document_genitive_kk": f"Unit {index} KK-genitive",
            "position_document_possessive_kk": f"position {index} KK-possessive",
            "employee_full_name_dative_kk": f"Employee {index} KK-dative",
            "employee_full_name_genitive_kk": f"Employee {index} KK-genitive",
        },
        "leave": leave,
    }


def _seed(conn, count: int, kind: str = "CONTINUOUS_RANGE") -> tuple[int, list[int], int]:
    actor = conn.execute(text("select user_id from users order by user_id limit 1")).scalar_one()
    employee = conn.execute(text("select employee_id from employees order by employee_id limit 1")).scalar_one()
    values = dict(get_personnel_order_template_spec("LEAVE.UNPAID.GRANT").initial_texts)
    # A test-only published template that uses the unambiguous period variable.
    # It intentionally does not alter the real INITIAL/DRAFT/PUBLISHED records.
    values.update({
        "title_ru": "Unpaid leave", "title_kk": "Unpaid leave kk",
        "preamble_ru": "Preamble", "preamble_kk": "Preamble kk",
        "body_template_ru": "{{employee.full_name_dative_ru}} {{position.document_nominative_ru}} {{org_unit.title_ru}} {{leave.period_clause_ru}} {{leave.days}}",
        "body_template_kk": "{{org_unit.document_genitive_kk}} {{position.document_possessive_kk}} {{employee.full_name_dative_kk}} {{leave.period_clause_kk}} еңбекақысы сақталмайтын демалыс берілсін.",
        "basis_template_ru": "Personal application", "basis_template_kk": "Негіз: {{employee.full_name_genitive_kk}} жеке өтініші.",
    })
    template = conn.execute(text("""insert into personnel_order_template_versions(item_type_code,version_number,status,title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk)
        values('LEAVE.UNPAID.GRANT', 889901, 'PUBLISHED', :title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk) returning template_version_id"""), values).scalar_one()
    order = conn.execute(text("insert into personnel_orders(order_type_code,status,source_mode,created_by) values('LEAVE.UNPAID.GRANT','DRAFT','MANUAL',:actor) returning order_id"), {"actor": actor}).scalar_one()
    item_ids = []
    # Deliberately reverse item_number insertion: preview must sort by number/id.
    for number in range(count, 0, -1):
        period_start = "2026-07-07" if kind == "SINGLE_DAY" else "2026-07-13"
        period_end = "2026-07-07" if kind == "SINGLE_DAY" else "2026-07-14"
        item = conn.execute(text("""insert into personnel_order_items(order_id,item_number,item_type_code,employee_id,effective_date,period_start,period_end,item_status,payload)
          values(:order,:number,'LEAVE.UNPAID.GRANT',:employee,:effective,:start,:end,'ACTIVE',cast(:payload as jsonb)) returning item_id"""), {"order": order, "number": number, "employee": employee, "effective": period_start, "start": period_start, "end": period_end, "payload": json.dumps(_payload(number, kind), ensure_ascii=False)}).scalar_one()
        item_ids.append(item)
        for locale in ("ru", "kk"):
            conn.execute(text("insert into personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text,review_status,basis_required) values(:item,:locale,'body','old body','CURRENT',false),(:item,:locale,'basis','old basis','CURRENT',false)"), {"item": item, "locale": locale})
    for locale in ("ru", "kk"):
        conn.execute(text("insert into personnel_order_editorial_blocks(order_id,locale,block_type,generated_text,review_status) values(:order,:locale,'title','old title','CURRENT'),(:order,:locale,'preamble','old preamble','CURRENT')"), {"order": order, "locale": locale})
    return order, item_ids, actor


@pytest.mark.parametrize("count", [1, 2, 4])
@pytest.mark.parametrize("kind", ["SINGLE_DAY", "CONTINUOUS_RANGE"])
def test_unpaid_preview_and_apply_are_atomic_for_all_item_counts(monkeypatch, count, kind):
    engine = create_engine(URL); conn = engine.connect(); outer = conn.begin()
    try:
        order, item_ids, actor = _seed(conn, count, kind)
        adapter = _Engine(conn); monkeypatch.setattr(service, "engine", adapter); monkeypatch.setattr(editorial_service, "engine", adapter)
        preview = service.preview_template_application(order)
        assert [item["item_number"] for item in preview["items"]] == list(range(1, count + 1))
        assert all(not item["missing_data"] for item in preview["items"])
        state = service.apply_template_application(order, actor, expected_document_revision=1)
        assert len(state["items"]) == count
        assert conn.execute(text("select count(*) from personnel_order_editorial_blocks where order_id=:order and generated_text <> 'old title' and generated_text <> 'old preamble'"), {"order": order}).scalar_one() == 4
        assert conn.execute(text("select count(*) from personnel_order_item_editorial_blocks where order_item_id=any(:items) and generated_text not in ('old body','old basis')"), {"items": item_ids}).scalar_one() == count * 4
        audit = conn.execute(text("select rendered_snapshot from personnel_order_template_applications where order_id=:order"), {"order": order}).scalar_one()
        assert len(audit["items"]) == count and audit["order"] == preview["order_proposed"]
    finally:
        outer.rollback(); conn.close(); engine.dispose()


def test_unpaid_apply_rolls_back_blocks_when_audit_insert_fails(monkeypatch):
    engine = create_engine(URL); conn = engine.connect(); outer = conn.begin()
    try:
        order, item_ids, actor = _seed(conn, 2)
        adapter = _Engine(conn); monkeypatch.setattr(service, "engine", adapter); monkeypatch.setattr(editorial_service, "engine", adapter)
        # A nested savepoint makes the failpoint assertion meaningful while the
        # enclosing fixture transaction remains rollback-only.
        nested = conn.begin_nested()
        monkeypatch.setattr(service, "AUDIT_INSERT_HOOK", lambda: (_ for _ in ()).throw(RuntimeError("audit failpoint")))
        with pytest.raises(RuntimeError, match="audit failpoint"):
            service.apply_template_application(order, actor, expected_document_revision=1)
        nested.rollback()
        assert conn.execute(text("select count(*) from personnel_order_template_applications where order_id=:order"), {"order": order}).scalar_one() == 0
        assert conn.execute(text("select count(*) from personnel_order_item_editorial_blocks where order_item_id=any(:items) and generated_text='old body'"), {"items": item_ids}).scalar_one() == 4
    finally:
        outer.rollback(); conn.close(); engine.dispose()


def test_generic_editorial_generation_includes_all_saved_unpaid_items(monkeypatch):
    """The non-template Generate button must render every saved item, in order."""
    engine = create_engine(URL); conn = engine.connect(); outer = conn.begin()
    try:
        order, item_ids, actor = _seed(conn, 2)
        conn.execute(text("insert into personnel_order_evidence_scopes(order_id) values(:order)"), {"order": order})
        adapter = _Engine(conn)
        monkeypatch.setattr(editorial_service, "engine", adapter)
        result = generation_service.generate_editorial(order, user_id=actor, conn=conn)
        assert result == {"order_id": order, "generated_in_existing_transaction": True}
        bodies = conn.execute(text("""
            select i.item_number, b.generated_text
            from personnel_order_items i
            join personnel_order_item_editorial_blocks b on b.order_item_id = i.item_id
            where i.order_id=:order and b.locale='kk' and b.block_type='body'
            order by i.item_number
        """), {"order": order}).mappings().all()
        assert len(bodies) == 2
        assert all(row["generated_text"].strip() for row in bodies)
    finally:
        outer.rollback(); conn.close(); engine.dispose()


def test_multi_item_override_requires_confirmation_and_is_snapshotted(monkeypatch):
    engine = create_engine(URL); conn = engine.connect(); outer = conn.begin()
    try:
        order, item_ids, actor = _seed(conn, 4)
        adapter = _Engine(conn); monkeypatch.setattr(service, "engine", adapter); monkeypatch.setattr(editorial_service, "engine", adapter)
        overridden_item = item_ids[2]
        block_id = conn.execute(text("select item_editorial_block_id from personnel_order_item_editorial_blocks where order_item_id=:item and locale='kk' and block_type='body'"), {"item": overridden_item}).scalar_one()
        conn.execute(text("update personnel_order_item_editorial_blocks set override_text='manual kk body' where item_editorial_block_id=:id"), {"id": block_id})
        before = service._blocks(conn, order, item_ids)
        preview = service.preview_template_application(order)
        assert preview["has_overrides"]
        assert preview["override_blocks"] == [{"block_id": block_id, "scope": "ITEM", "block_type": "BODY", "language": "KK", "order_item_id": overridden_item}]
        with pytest.raises(service.TemplateApplicationError, match="Manual overrides"):
            service.apply_template_application(order, actor, expected_document_revision=1)
        assert service._blocks(conn, order, item_ids) == before
        assert conn.execute(text("select count(*) from personnel_order_template_applications where order_id=:order"), {"order": order}).scalar_one() == 0
        service.apply_template_application(order, actor, expected_document_revision=1, confirm_replace_overrides=True)
        assert conn.execute(text("select count(*) from personnel_order_item_editorial_blocks where order_item_id=any(:items) and generated_text not in ('old body','old basis') and override_text is null"), {"items": item_ids}).scalar_one() == 16
        audit = conn.execute(text("select previous_editorial_blocks from personnel_order_template_applications where order_id=:order"), {"order": order}).scalar_one()
        assert any(block["block_id"] == block_id and block["override_text"] == "manual kk body" for block in audit)
    finally:
        outer.rollback(); conn.close(); engine.dispose()


def test_multi_item_reapply_preserves_first_audit_and_snapshots_first_state(monkeypatch):
    engine = create_engine(URL); conn = engine.connect(); outer = conn.begin()
    try:
        order, item_ids, actor = _seed(conn, 2)
        adapter = _Engine(conn); monkeypatch.setattr(service, "engine", adapter); monkeypatch.setattr(editorial_service, "engine", adapter)
        service.apply_template_application(order, actor, expected_document_revision=1)
        first = conn.execute(text("select template_application_id,template_snapshot::text,rendered_snapshot::text,previous_editorial_blocks::text from personnel_order_template_applications where order_id=:order"), {"order": order}).mappings().one()
        after_first = service._blocks(conn, order, item_ids)
        with pytest.raises(service.TemplateApplicationError, match="already applied"):
            service.apply_template_application(order, actor, expected_document_revision=1)
        assert conn.execute(text("select template_snapshot::text,rendered_snapshot::text,previous_editorial_blocks::text from personnel_order_template_applications where template_application_id=:id"), {"id": first["template_application_id"]}).one() == (first["template_snapshot"], first["rendered_snapshot"], first["previous_editorial_blocks"])
        service.apply_template_application(order, actor, expected_document_revision=1, confirm_reapply=True)
        audits = conn.execute(text("select template_application_id,template_snapshot::text,rendered_snapshot::text,previous_editorial_blocks from personnel_order_template_applications where order_id=:order order by template_application_id"), {"order": order}).mappings().all()
        assert len(audits) == 2
        assert (audits[0]["template_snapshot"], audits[0]["rendered_snapshot"]) == (first["template_snapshot"], first["rendered_snapshot"])
        expected = {(block["scope"], block["order_item_id"], block["locale"], block["block_type"], block["generated_text"], block["override_text"], block["revision"]) for block in after_first}
        actual = {(block["scope"], block["order_item_id"], block["locale"], block["block_type"], block["generated_text"], block["override_text"], block["revision"]) for block in audits[1]["previous_editorial_blocks"]}
        assert actual == expected
    finally:
        outer.rollback(); conn.close(); engine.dispose()


def test_multi_item_missing_confirmed_kk_blocks_order_without_writes(monkeypatch):
    engine = create_engine(URL); conn = engine.connect(); outer = conn.begin()
    try:
        order, item_ids, actor = _seed(conn, 2)
        broken = _payload(1)
        broken["document_forms_kk"] = {}
        broken["org_unit_name"].pop("document_genitive_kk")
        broken["position_name"].pop("document_possessive_kk")
        broken["employee"]["name"].pop("full_name_dative_kk")
        broken["employee"]["name"].pop("full_name_genitive_kk")
        conn.execute(text("update personnel_order_items set payload=cast(:payload as jsonb) where item_id=:item"), {"item": item_ids[0], "payload": json.dumps(broken)})
        adapter = _Engine(conn); monkeypatch.setattr(service, "engine", adapter); monkeypatch.setattr(editorial_service, "engine", adapter)
        before_blocks = service._blocks(conn, order, item_ids)
        preview = service.preview_template_application(order)
        blocked = next(item for item in preview["items"] if item["order_item_id"] == item_ids[0])
        assert blocked["blocked"] and {"org_unit.document_genitive_kk", "position.document_possessive_kk", "employee.full_name_dative_kk", "employee.full_name_genitive_kk"} <= set(blocked["missing_data"])
        with pytest.raises(service.TemplateApplicationError, match="blocked"):
            service.apply_template_application(order, actor, expected_document_revision=1)
        assert service._blocks(conn, order, item_ids) == before_blocks
        assert conn.execute(text("select count(*) from personnel_order_template_applications where order_id=:order"), {"order": order}).scalar_one() == 0
    finally:
        outer.rollback(); conn.close(); engine.dispose()
