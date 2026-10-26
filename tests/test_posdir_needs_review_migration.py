"""Real PostgreSQL migration tests on new disposable loopback databases only."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from sqlalchemy import text
from app.db import position_directory_review_migration as current
from app.db.position_directory_migration import upgrade as legacy_upgrade
from scripts.rehearse_posdir_backfill import restore,fingerprint
from tests.test_personnel_order_print_titles_migration_isolated import fresh_database

BASELINE=Path(__file__).resolve().parents[1]/'reference-data/dictionaries/posdir001-production-baseline-20261026.json'


def initialize(db):
    baseline=json.loads(BASELINE.read_text(encoding='utf-8'))
    with db.begin() as conn:restore(conn,baseline)
    return baseline


def rows(conn):
    return [dict(r) for r in conn.execute(text('SELECT '+','.join(current.ROW_FIELDS)+' FROM public.positions ORDER BY position_id')).mappings()]


def test_all_111_texts_equal_legacy_with_only_statuses_changed(fresh_database):
    baseline=initialize(fresh_database)
    with fresh_database.connect() as conn:
        before=fingerprint(conn)
        tx=conn.begin_nested()
        legacy_upgrade(conn);expected=rows(conn)
        tx.rollback()
        current.upgrade(conn);actual=rows(conn)
        compare=lambda rs:[{k:v for k,v in r.items() if k not in ('translation_status','document_form_status')} for r in rs]
        assert compare(actual)==compare(expected)
        assert len(actual)==111
        assert all(r['translation_status']==r['document_form_status']=='needs_review' for r in actual)
        assert sum(bool(r['name_kk']) for r in actual)==73
        assert sum(bool(r['document_possessive_kk']) for r in actual)==73
        assert conn.execute(text('SELECT count(*) FROM public.position_directory WHERE job_namekk IS NOT NULL OR job_namekk_doc IS NOT NULL')).scalar()==0
        source={r['position_id']:r for r in baseline['dictionaries']['positions']['rows']}
        assert sum(r['name_kk']!=source[r['position_id']]['name_kk'] for r in actual)==72
        assert all(r['document_nominative_ru']==source[r['position_id']]['name'] for r in actual)
        for id in (47,52):
            record=next(r for r in actual if r['position_id']==id)
            assert record['name_kk'] is None and record['document_possessive_kk'] is None
        after=fingerprint(conn)
        assert all(before[t]==after[t] for t in ('employees','person_assignments','personnel_orders','personnel_order_items','position_job_catalog','job_positions_catalog'))


def test_repeat_is_noop_and_keeps_later_manual_confirmation_and_clearing(fresh_database):
    initialize(fresh_database)
    with fresh_database.begin() as conn:current.upgrade(conn)
    with fresh_database.begin() as conn:
        before=fingerprint(conn);current.upgrade(conn);assert fingerprint(conn)==before
        conn.execute(text("UPDATE public.positions SET translation_status='confirmed',document_form_status='confirmed' WHERE position_id=24"))
        conn.execute(text("UPDATE public.positions SET name_kk=NULL,document_possessive_kk=NULL WHERE position_id=25"))
        manual=fingerprint(conn);current.upgrade(conn);assert fingerprint(conn)==manual


def test_empty_unmapped_values_and_existing_kk_text_are_not_invented_or_trimmed(fresh_database):
    initialize(fresh_database)
    with fresh_database.begin() as conn:
        conn.execute(text('UPDATE public.positions SET name_kk=:value WHERE position_id=44'),{'value':'  TEST exact existing KK  '})
        conn.execute(text("UPDATE public.positions SET name_kk='' WHERE position_id=52"))
        current.upgrade(conn)
        records={r['position_id']:r for r in rows(conn)}
        assert records[44]['name_kk']=='  TEST exact existing KK  '
        assert records[52]['name_kk']=='' and records[52]['document_possessive_kk'] is None
        assert records[47]['name_kk'] is None and records[47]['document_possessive_kk'] is None


def test_legacy_schema_refuses_blind_reset_and_explicit_transition_preserves_text(fresh_database):
    initialize(fresh_database)
    with fresh_database.begin() as conn:legacy_upgrade(conn)
    with fresh_database.connect() as conn:before=fingerprint(conn);original=rows(conn)
    with pytest.raises(RuntimeError,match='owner-reviewed'):
        with fresh_database.begin() as conn:current.upgrade(conn)
    with fresh_database.connect() as conn:assert fingerprint(conn)==before
    manifest={'policy':current.POLICY,'owner_approved':True,'positions':[
        {'before':r,'translation_status':'needs_review','document_form_status':'needs_review'} for r in original]}
    chosen=next(r for r in manifest['positions'] if r['before']['position_id']==24)
    chosen.update(translation_status='confirmed',document_form_status='confirmed',confirmation_evidence='SYNTHETIC owner review')
    with fresh_database.begin() as conn:current.review_existing_directory(conn,manifest)
    with fresh_database.begin() as conn:
        migrated=rows(conn)
        for old,new in zip(original,migrated):
            assert all(old[k]==new[k] for k in current.ROW_FIELDS if k not in ('translation_status','document_form_status','revision'))
            if new['position_id']==24:assert new['translation_status']==new['document_form_status']=='confirmed'
            else:assert new['translation_status']==new['document_form_status']=='needs_review'
        approved=fingerprint(conn)
        current.review_existing_directory(conn,manifest);current.upgrade(conn)
        assert fingerprint(conn)==approved


def test_legacy_transition_requires_complete_review_and_rejects_drift(fresh_database):
    initialize(fresh_database)
    with fresh_database.begin() as conn:legacy_upgrade(conn)
    with fresh_database.connect() as conn:original=rows(conn);before=fingerprint(conn)
    manifest={'policy':current.POLICY,'owner_approved':True,'positions':[
        {'before':r,'translation_status':'needs_review','document_form_status':'needs_review'} for r in original]}
    for mutation in ('approval','coverage','drift','empty_confirmation'):
        invalid=deepcopy(manifest)
        if mutation=='approval':invalid['owner_approved']=False
        elif mutation=='coverage':invalid['positions'].pop()
        elif mutation=='drift':invalid['positions'][0]['before']['revision']+=1
        else:
            item=next(r for r in invalid['positions'] if r['before']['position_id']==52)
            item.update(translation_status='confirmed',confirmation_evidence='SYNTHETIC')
        with pytest.raises(RuntimeError):
            with fresh_database.begin() as conn:current.review_existing_directory(conn,invalid)
        with fresh_database.connect() as conn:assert fingerprint(conn)==before
