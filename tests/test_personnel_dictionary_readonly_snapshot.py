"""Read-only probe helpers; no database/network is opened by these tests."""
import ast
from scripts.read_personnel_dictionary_snapshot import revision_metadata, READ_ONLY_OPTIONS, TABLES


def test_graph_analysis_does_not_execute_migration_code():
    source="revision='TEST'\ndown_revision=('PARENT_A','PARENT_B')\nraise RuntimeError('must never execute')\n"
    assert revision_metadata(source)=={'revision':'TEST','down_revision':('PARENT_A','PARENT_B')}


def test_graph_metadata_cannot_execute_dynamic_revision_expressions():
    import pytest
    with pytest.raises((ValueError,TypeError)):
        revision_metadata("revision=__import__('os').system('must not run')")


def test_probe_scope_is_only_nonpersonal_dictionaries_and_has_readonly_default():
    assert set(TABLES)=={'positions','position_aliases','position_job_catalog','job_positions_catalog','medical_specialties','medical_specialty_groups'}
    assert '-c default_transaction_read_only=on' in READ_ONLY_OPTIONS


def test_versioned_fresh_plan_preserves_approved_targets_and_snapshot_provenance():
    import hashlib
    import json
    from pathlib import Path
    from scripts.plan_personnel_dictionary_transfer import make_plan
    root=Path(__file__).resolve().parents[1]
    read=lambda p:json.loads((root/p).read_text(encoding='utf-8'))
    plan=read('docs/deploy/personnel-dictionary-production-plan-20261026.json')
    snapshot=read(plan['planning_inputs']['production_snapshot'])
    assert snapshot['transaction_read_only']=='on'
    assert plan['planning_commit']=='daf276c816bd2d0d2f4ea9bb4311a56caea26b08'
    planner=(root/'scripts/plan_personnel_dictionary_transfer.py').read_bytes().replace(b'\r\n',b'\n')
    assert hashlib.sha256(planner).hexdigest()==plan['planning_inputs']['planner_sha256']
    generated=make_plan(read('reference-data/dictionaries/local-review-20261026.json'),snapshot,snapshot,
                        read('docs/deploy/personnel-dictionary-owner-approvals-20261026.json'))
    assert generated['records']==plan['records']
    assert generated['expected_operations']==plan['expected_operations']
    for target_id,code,operation in ((24,'LAUNDRY_MACHINE_OPERATOR','SKIP'),(52,'TECHNICIAN','INSERT')):
        record=next(r for r in plan['records'] if r.get('target_identity_guard',{}).get('expected_target_position_id')==target_id)
        assert record['before']['category']=='other' and record['desired']['category']=='technical'
        assert record['operation']=='UPDATE' and 'position_id' not in record['desired']
        link=next(r for r in plan['records'] if r['table']=='position_job_catalog' and r.get('approval_id')==record['approval_id'])
        assert link['desired']['job_code']==code and link['operation']==operation
    social=next(r for r in plan['records'] if r.get('approval_id')=='owner-social-worker-other-20261026' and r['table']=='positions')
    assert social['key']['category']==social['desired']['category']=='other'
