from datetime import date
import hashlib

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.personnel_files import service, classifiers
from tests.personnel_files.test_workflow import submit, decide


def facts(entry=1):
    return dict(entry_id=entry,specialty_name_at_issue='Название как в выданном тестовом сертификате',issued_at=date(2025,1,1),valid_until=date(2031,1,1))


def replacement(actors, old, entry):
    return submit(actors,certificate=facts(entry),set_id=old['set_id'],expected_version_id=old['version_id'],expected_revision=old['revision'])


def confirm(database):
    with database.begin() as c:
        c.execute(text("""INSERT INTO certificate_specialty_mappings(from_entry_id,to_entry_id,source_reference,reason,effective_from,confirmed_by)
            VALUES(1,3,'FICTIONAL TEST PROTOCOL','Вымышленная проверка','2025-01-01',3)"""))


def test_same_edition_and_confirmed_mapping_replace_only_a(seeded,database):
    a=decide(seeded,submit(seeded,certificate=facts(1)))
    b=decide(seeded,submit(seeded,certificate=facts(2)))
    sha=hashlib.sha256(service.content(seeded[1],b['version_id'],operation='download')[0]).hexdigest()
    a2=decide(seeded,replacement(seeded,a,1))
    confirm(database)
    pending=replacement(seeded,a2,3)
    ctx=service.review_context(seeded[3],pending['version_id'])
    assert ctx['can_approve'] and ctx['basis']['kind']=='confirmed_mapping'
    assert ctx['previous']['version_id']==a2['version_id']
    assert ctx['previous']['certificate']['classifier_edition_at_issue']=='TEST-OLD'
    assert ctx['new_certificate']['classifier_edition_at_issue']=='TEST-NEW'
    approved=decide(seeded,pending)
    items=service.listing(seeded[1],1)['items']
    assert {r['version_id'] for r in items if r['state']=='approved'}=={b['version_id'],approved['version_id']}
    assert sha==hashlib.sha256(service.content(seeded[1],b['version_id'],operation='download')[0]).hexdigest()
    with database.connect() as c:
        rows={r['document_id']:r for r in c.execute(text('SELECT * FROM employee_documents')).mappings()}
        assert rows[a['employee_document_id']]['lifecycle_status']=='SUPERSEDED'
        assert rows[b['employee_document_id']]['lifecycle_status']=='ACTIVE'
        assert rows[approved['employee_document_id']]['verification_status']=='VERIFIED'
    audit=service.history(seeded[3],1)
    assert any(r['detail'].get('certificate_comparison',{}).get('basis',{}).get('mapping_id') for r in audit if r['detail'].get('certificate_comparison'))


def test_return_and_missing_mapping_preserve_previous_and_standalone_allowed(seeded,database):
    old=decide(seeded,submit(seeded,certificate=facts(1)))
    returned=decide(seeded,replacement(seeded,old,3),'return','Вымышленная причина возврата')
    assert service.listing(seeded[1],1)['items'][-1]['state']=='approved'
    pending=replacement(seeded,returned,4)
    ctx=service.review_context(seeded[3],pending['version_id'])
    assert not ctx['can_approve'] and ctx['basis']['kind']=='no_mapping'
    with pytest.raises(HTTPException) as exc: decide(seeded,pending)
    assert exc.value.status_code==409
    with database.connect() as c:
        assert c.execute(text('SELECT lifecycle_status FROM employee_documents WHERE document_id=:id'),{'id':old['employee_document_id']}).scalar_one()=='ACTIVE'
    separate=decide(seeded,submit(seeded,certificate=facts(4)))
    assert {r['version_id'] for r in service.listing(seeded[1],1)['items'] if r['state']=='approved'}=={old['version_id'],separate['version_id']}


def test_context_must_match_and_mapping_is_rechecked_at_approval(seeded,database):
    old=decide(seeded,submit(seeded))
    confirm(database)
    new=replacement(seeded,old,3)
    ctx=service.review_context(seeded[3],new['version_id'])
    with pytest.raises(HTTPException):
        service.decide(seeded[3],new['version_id'],expected_revision=1,action='approve',reason='')
    with database.begin() as c:c.execute(text('UPDATE certificate_specialty_mappings SET active=false'))
    with pytest.raises(HTTPException) as exc:
        service.decide(seeded[3],new['version_id'],expected_revision=1,action='approve',reason='',expected_certificate_context=ctx['context_token'])
    assert exc.value.status_code==409
    assert next(r for r in service.listing(seeded[1],1)['items'] if r['version_id']==old['version_id'])['state']=='approved'


def test_unknown_legacy_requisites_are_not_inferred_and_block_replacement(seeded,database):
    with database.begin() as c:
        did=c.execute(text("""INSERT INTO employee_documents(employee_id,document_type_id,medical_specialty_id,lifecycle_status,verification_status,created_by)
            VALUES(1,1,1,'ACTIVE','VERIFIED',3) RETURNING document_id""")).scalar_one()
    legacy=decide(seeded,submit(seeded,certificate={'employee_document_id':did}))
    assert legacy['certificate']['specialty_name_at_issue'] is None
    assert legacy['certificate']['classifier_edition_at_issue'] is None
    new=replacement(seeded,legacy,1)
    with pytest.raises(HTTPException) as exc:decide(seeded,new)
    assert exc.value.status_code==409
    with database.connect() as c:
        r=c.execute(text('SELECT * FROM employee_documents WHERE document_id=:id'),{'id':did}).mappings().one()
        assert r['lifecycle_status']=='ACTIVE' and r['verification_status']=='VERIFIED'
        assert r['issued_at'] is None and r['valid_until'] is None and r['certificate_entry_id'] is None


def test_dictionary_edition_change_preserves_issued_facts_and_status(seeded,database):
    old=decide(seeded,submit(seeded,certificate=facts(1)))
    before=old['certificate']
    with database.begin() as c:
        c.execute(text("UPDATE medical_specialties SET name='Текущее изменённое название',is_active=false WHERE medical_specialty_id=1"))
        c.execute(text('UPDATE certificate_classifier_editions SET accepts_new=false WHERE edition_id=1'))
    after=service.listing(seeded[1],1)['items'][0]
    assert after['certificate']==before and after['state']=='approved'
    with pytest.raises(DBAPIError):
        with database.begin() as c:c.execute(text("UPDATE employee_documents SET valid_until='2039-01-01' WHERE document_id=:id"),{'id':old['employee_document_id']})


def test_registry_link_ownership_and_review_context_access(seeded,database):
    old=decide(seeded,submit(seeded))
    with pytest.raises(HTTPException) as exc:
        service.submit(seeded[2],2,kind='certificate',title='Чужой тест',content=b'',mime='application/pdf',filename='test.pdf',certificate={'employee_document_id':old['employee_document_id']})
    # File validation may reject first; direct registry resolution must not reveal another person's requisites.
    from app.personnel_files.certificates import document
    with database.begin() as c:
        with pytest.raises(HTTPException) as err:document(c,old['employee_document_id'],2)
        assert err.value.status_code==404
    pending=replacement(seeded,old,1)
    with pytest.raises(HTTPException) as err:service.review_context(seeded[1],pending['version_id'])
    assert err.value.status_code==403


def test_only_authorized_central_hr_can_confirm_correspondence(seeded,database):
    payload=dict(from_entry_id=1,to_entry_id=3,source_reference='Тестовый источник',reason='Вымышленное подтверждение',effective_from=date(2025,1,1))
    with pytest.raises(HTTPException) as err:classifiers.manage(seeded[3],'mapping',payload)
    assert err.value.status_code==403
    with database.begin() as c:
        c.execute(text("INSERT INTO access_grants(access_role_id,target_type,target_id) SELECT access_role_id,'USER',3 FROM access_roles WHERE code IN ('PERSONNEL_FILES_REVIEW','CERTIFICATE_CLASSIFIERS_MANAGE')"))
    result=classifiers.manage(seeded[3],'mapping',payload)
    assert result['confirmed_by']==3
    for actor in (1,6,7):
        with pytest.raises(HTTPException):classifiers.manage(seeded[actor],'edition',dict(code='NO',title='NO',source_reference='NO',effective_from=date(2025,1,1)))


def test_http_cannot_override_registry_metadata(seeded):
    from pydantic import ValidationError
    from app.personnel_files.router import Certificate,Decision
    with pytest.raises(ValidationError):Certificate.model_validate({'employee_document_id':1,'entry_id':4})
    with pytest.raises(ValidationError):Decision.model_validate({'expected_revision':1,'action':'approve','mapping_id':999})


def test_registry_creation_snapshots_facts_and_pdf_attaches_without_overrides(seeded,database,monkeypatch):
    from app.services import employee_documents_service as registry
    monkeypatch.setattr(registry,'engine',database)
    with pytest.raises(registry.EmployeeDocumentValidationError):
        registry.create_employee_document(employee_id=1,document_type_id=1,created_by=3,medical_specialty_id=1,issued_at=date(2025,1,1),valid_until=date(2031,1,1))
    record=registry.create_employee_document(employee_id=1,document_type_id=1,created_by=3,medical_specialty_id=1,
        certificate_entry_id=1,specialty_name_at_issue='Именно как выдано',issued_at=date(2025,1,1),valid_until=date(2031,1,1))
    assert record['medical_specialty_name']=='Именно как выдано'
    assert record['classifier_edition_at_issue']=='TEST-OLD'
    attached=decide(seeded,submit(seeded,certificate={'employee_document_id':record['document_id']}))
    assert attached['certificate']['issued_at']==date(2025,1,1)
    with pytest.raises(registry.EmployeeDocumentValidationError):
        registry.update_employee_document(record['document_id'],valid_until=date(2039,1,1))
    with pytest.raises(registry.EmployeeDocumentValidationError):registry.soft_delete_employee_document(record['document_id'])
