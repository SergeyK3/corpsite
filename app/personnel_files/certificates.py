"""Certificate facts come from employee_documents, never PDF names or inferred mappings."""
from datetime import date
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import text


def entry_facts(conn, entry_id):
    r = conn.execute(text('''SELECT e.*,d.code AS edition_code,d.title AS edition_title,d.accepts_new
        FROM certificate_classifier_entries e JOIN certificate_classifier_editions d USING(edition_id)
        WHERE entry_id=:id FOR SHARE OF e,d'''), {'id': entry_id}).mappings().one_or_none()
    if not r or not r['accepts_new']:
        raise HTTPException(422, 'Выберите специальность в доступной редакции классификатора.')
    return dict(r)


def document(conn, document_id, person_id):
    if document_id is None:
        return None
    r = conn.execute(text('''SELECT ed.document_id,ed.employee_id,ed.certificate_entry_id,
        ed.medical_specialty_id,ed.specialty_name_at_issue,ed.specialty_code_at_issue,
        ed.classifier_edition_at_issue,ed.issued_at,ed.valid_until,ed.document_number,ed.issued_by,
        ed.lifecycle_status,ed.verification_status,dt.code AS document_type_code
        FROM employee_documents ed JOIN employees emp USING(employee_id)
        JOIN document_types dt USING(document_type_id)
        WHERE ed.document_id=:id AND emp.person_id=:pid FOR SHARE OF ed'''),
        {'id': document_id, 'pid': person_id}).mappings().one_or_none()
    if not r or r['document_type_code'] != 'SPECIALIST_CERTIFICATION':
        raise HTTPException(404, 'Сертификат реестра этого сотрудника не найден.')
    return dict(r)


def attach(conn, user, person_id, certificate):
    if not certificate:
        raise HTTPException(422, 'Выберите запись реестра или заполните реквизиты нового сертификата.')
    if certificate.get('employee_document_id'):
        r = document(conn, certificate['employee_document_id'], person_id)
        if r['lifecycle_status'] != 'ACTIVE':
            raise HTTPException(409, 'Выберите действующую запись реестра.')
        if conn.execute(text('SELECT 1 FROM personnel_file_versions WHERE employee_document_id=:id'), {'id': r['document_id']}).first():
            raise HTTPException(409, 'К этой записи уже привязан файл. Для новой версии создайте новую запись сертификата.')
        return r['document_id'], False
    facts = entry_facts(conn, certificate['entry_id'])
    issued = certificate['issued_at']; until = certificate['valid_until']
    if not isinstance(issued, date): issued = date.fromisoformat(issued)
    if not isinstance(until, date): until = date.fromisoformat(until)
    if until < issued:
        raise HTTPException(422, 'Срок действия не может заканчиваться раньше выдачи.')
    employees = conn.execute(text('SELECT employee_id FROM employees WHERE person_id=:pid AND is_active ORDER BY employee_id'), {'pid': person_id}).scalars().all()
    if len(employees) != 1:
        raise HTTPException(409, 'Нужна однозначная связь сотрудника с реестром документов.')
    doc_id = conn.execute(text('''INSERT INTO employee_documents
        (employee_id,document_type_id,medical_specialty_id,certificate_entry_id,specialty_name_at_issue,
         issued_at,valid_until,document_number,issued_by,lifecycle_status,verification_status,created_by)
        SELECT :eid,document_type_id,:sid,:entry,:name,:issued,:until,:number,:issuer,'DRAFT','UNVERIFIED',:uid
        FROM document_types WHERE code='SPECIALIST_CERTIFICATION' RETURNING document_id'''),
        {'eid': employees[0], 'sid': facts['medical_specialty_id'], 'entry': facts['entry_id'],
         'name': certificate['specialty_name_at_issue'].strip(), 'issued': issued, 'until': until,
         'number': certificate.get('document_number'), 'issuer': certificate.get('issued_by'), 'uid': user['user_id']}).scalar_one()
    return doc_id, True


def complete(d):
    return bool(d and all(d.get(k) for k in ('certificate_entry_id','specialty_name_at_issue',
        'specialty_code_at_issue','classifier_edition_at_issue','issued_at','valid_until')))


def context(conn, r, *, lock=False):
    new = document(conn, r.get('employee_document_id'), r['person_id'])
    old = conn.execute(text('''SELECT v.*,s.person_id,s.kind,s.title FROM personnel_file_versions v
        JOIN personnel_file_sets s USING(set_id) WHERE v.set_id=:sid AND v.state='approved'
        AND v.version_id<>:vid''' + (' FOR UPDATE OF v' if lock else '')),
        {'sid': r['set_id'], 'vid': r['version_id']}).mappings().one_or_none()
    previous = dict(old) if old else None
    before = document(conn, previous.get('employee_document_id'), r['person_id']) if previous else None
    allowed = new is not None
    basis = {'kind': 'standalone', 'description': 'Самостоятельная запись. Прежние сертификаты не заменяются.'}
    if not allowed:
        basis = {'kind': 'unknown', 'description': 'Файл не связан с реестром. Подайте сертификат с реквизитами отдельной записью.'}
    elif previous:
        allowed = False
        basis = {'kind': 'unknown', 'description': 'Реквизиты прежнего или нового сертификата неизвестны. Замена запрещена; можно подать отдельную запись.'}
        if complete(before) and complete(new):
            if before['certificate_entry_id'] == new['certificate_entry_id']:
                allowed = True
                basis = {'kind': 'same_specialty', 'description': 'Та же специальность в той же редакции классификатора.'}
            elif before['classifier_edition_at_issue'] != new['classifier_edition_at_issue']:
                mapping = conn.execute(text('''SELECT * FROM certificate_specialty_mappings
                    WHERE from_entry_id=:old AND to_entry_id=:new AND active AND effective_from<=:issued
                    AND effective_from<=CURRENT_DATE FOR SHARE'''),
                    {'old': before['certificate_entry_id'], 'new': new['certificate_entry_id'], 'issued': new['issued_at']}).mappings().one_or_none()
                if mapping:
                    allowed = True
                    basis = {'kind': 'confirmed_mapping', 'description': 'Централизованно подтверждённое соответствие между редакциями.', **dict(mapping)}
            if not allowed:
                basis = {'kind': 'no_mapping', 'description': 'Подтверждённого соответствия специальностей нет. Замена запрещена; подайте новый сертификат отдельной записью.'}
    if r.get('replaces_version_id') is not None and (previous is None or str(previous['version_id']) != str(r['replaces_version_id'])):
        allowed = False
        basis = {'kind': 'changed_target', 'description': 'Состояние прежнего сертификата изменилось. Верните заявку и подайте её заново.'}
    # Binds the confirmation to precisely the comparison and centrally confirmed basis shown to HR.
    from app.personnel_files.service import public
    from app.personnel_files.policy import Access
    previous_public = public(previous, Access(reviewer=True), conn) if previous else None
    payload = {'previous': previous_public, 'new_certificate': new, 'can_approve': allowed, 'basis': basis}
    token = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return {**payload, 'context_token': token}


def publish(conn, r, comparison):
    # Existing legacy requisites are never inferred or rewritten when merely attaching a scan.
    if r['registry_created_by_upload'] or complete(comparison['new_certificate']):
        conn.execute(text("UPDATE employee_documents SET lifecycle_status='ACTIVE',verification_status='VERIFIED',updated_at=now() WHERE document_id=:id"), {'id': r['employee_document_id']})
    previous = comparison['previous']
    if previous:
        conn.execute(text("UPDATE employee_documents SET lifecycle_status='SUPERSEDED',updated_at=now() WHERE document_id=:id"), {'id': previous['certificate']['document_id']})
