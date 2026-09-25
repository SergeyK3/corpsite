"""Contract coverage for typed document-header corrections."""
from datetime import date
from uuid import uuid4
import pytest
from sqlalchemy import text
from pydantic import ValidationError
from app.db.engine import engine
from app.directory.personnel_orders_schemas import PersonnelOrderDocumentHeaderPatchIn
from app.services.personnel_order_document_header_service import duplicate_preview, patch_document_header
from app.services.personnel_order_document_review_service import mutate_document_review, PersonnelOrderDocumentReviewConflictError

def _order(seed, *, number=None, day=date(2026,9,1), status="DRAFT"):
    suffix=uuid4().hex[:8]; actor=int(seed["initiator_user_id"])
    with engine.begin() as c:
        oid=int(c.execute(text("INSERT INTO personnel_orders(order_number,order_date,order_type_code,status,source_mode,created_by) VALUES(:n,:d,'HIRE',:s,'PAPER',:u) RETURNING order_id"),{"n":number or f"HDR-{suffix}","d":day,"s":status,"u":actor}).scalar_one())
        c.execute(text("INSERT INTO personnel_order_items(order_id,item_number,item_type_code,payload) VALUES(:id,1,'HIRE','{\"unresolved_subject\":\"Test\"}'::jsonb)"),{"id":oid})
        for locale in ("ru","kk"):
            c.execute(text("INSERT INTO personnel_order_editorial_blocks(order_id,locale,block_type,generated_text,review_status) VALUES(:id,:l,'title','t','CURRENT')"),{"id":oid,"l":locale})
            c.execute(text("INSERT INTO personnel_order_item_editorial_blocks(order_item_id,locale,block_type,generated_text,review_status) SELECT item_id,:l,'body','b','CURRENT' FROM personnel_order_items WHERE order_id=:id"),{"id":oid,"l":locale})
    return oid,actor
def _clean(oid):
    with engine.begin() as c:
        c.execute(text("DELETE FROM personnel_order_lifecycle_audit WHERE order_id=:id"),{"id":oid}); c.execute(text("DELETE FROM personnel_order_item_editorial_blocks WHERE order_item_id IN (SELECT item_id FROM personnel_order_items WHERE order_id=:id)"),{"id":oid}); c.execute(text("DELETE FROM personnel_order_editorial_blocks WHERE order_id=:id"),{"id":oid}); c.execute(text("DELETE FROM personnel_order_items WHERE order_id=:id"),{"id":oid}); c.execute(text("DELETE FROM personnel_orders WHERE order_id=:id"),{"id":oid})
def _patch(oid,actor,**kw): return patch_document_header(order_id=oid,expected_document_revision=kw.pop("rev",1),order_number=kw.pop("number","Changed-1"),order_date=kw.pop("day",date(2026,9,2)),source_title=kw.pop("title","Source"),source_title_locale=kw.pop("locale","kk"),reason_code=kw.pop("code",None),reason_text=kw.pop("text",None),actor_user_id=actor)

def test_draft_update_allowlisted_audit_and_noop(seed):
    oid,a=_order(seed)
    try:
        result=_patch(oid,a); assert result["no_op"] is False and result["resulting_document_revision"]==2
        noop=_patch(oid,a,rev=2); assert noop["no_op"] is True
        with engine.connect() as c:
            row=c.execute(text("SELECT action,metadata_json FROM personnel_order_lifecycle_audit WHERE order_id=:id"),{"id":oid}).mappings().one(); assert row["action"]=="HEADER_UPDATED"; assert set(row["metadata_json"]["before"])=={"order_number","order_date","source_title","source_title_locale"}
    finally:_clean(oid)

@pytest.mark.parametrize("status",["REGISTERED","SIGNED"])
def test_registered_and_signed_require_reason(seed,status):
    oid,a=_order(seed,status=status)
    try:
        with pytest.raises(ValueError):_patch(oid,a)
        assert _patch(oid,a,code="CORRECTION",text="Confirmed")["resulting_document_revision"]==2
    finally:_clean(oid)

def test_duplicate_rules_and_current_order_excluded(seed):
    one,a=_order(seed,number="125-к",day=date(2026,7,10)); two,_=_order(seed,number="125-ж",day=date(2026,7,10))
    try:
        assert duplicate_preview(order_number="125-к",order_date=date(2026,7,10))["blocking"]
        assert duplicate_preview(order_number="125-к",order_date=date(2026,7,11))["warnings"]
        assert not duplicate_preview(order_number="125-ж",order_date=date(2026,7,10),order_id=two)["blocking"]
        assert not duplicate_preview(order_number="125\u2013\u043a",order_date=date(2026,7,10),order_id=one)["blocking"]
    finally:_clean(one);_clean(two)

def test_confirmed_header_change_reopens_once_and_preserves_facts(seed):
    oid,a=_order(seed,status="REGISTERED")
    try:
        mutate_document_review(oid,action="DOCUMENT_CONFIRMED",expected_document_revision=1,reason_code="HR",note=None,actor_user_id=a)
        result=_patch(oid,a,rev=2,code="CORRECTION",text="Confirmed"); assert result["resulting_document_revision"]==3 and result["document_review_state"]=="NEEDS_REVIEW"
        with engine.connect() as c:
            actions=c.execute(text("SELECT action FROM personnel_order_lifecycle_audit WHERE order_id=:id ORDER BY id"),{"id":oid}).scalars().all(); assert actions==["DOCUMENT_CONFIRMED","HEADER_UPDATED","DOCUMENT_REOPENED"]
            assert c.execute(text("SELECT count(*) FROM employee_events WHERE order_id=:id"),{"id":oid}).scalar_one()==0
    finally:_clean(oid)

def test_schema_forbids_actor_metadata_and_invalid_locale(seed):
    with pytest.raises(ValidationError):PersonnelOrderDocumentHeaderPatchIn(expected_document_revision=1,order_number="1",actor_user_id=1)
    with pytest.raises(ValidationError):PersonnelOrderDocumentHeaderPatchIn(expected_document_revision=1,order_number="1",source_title_locale="en")
