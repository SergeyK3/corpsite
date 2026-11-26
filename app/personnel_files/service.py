"""Transactions serialize by Person, then lock version rows; originals are immutable."""
from __future__ import annotations
from datetime import datetime
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from app.db.engine import engine
from app.personnel_files.access import access
from app.personnel_files.policy import KINDS, transition
from app.personnel_files import storage, certificates


request_id: ContextVar[str | None] = ContextVar('personnel_file_request_id', default=None)

def event(conn, user, person_id, version_id, action, detail=None):
    conn.execute(text('''INSERT INTO public.personnel_file_events
        (person_id,version_id,actor_id,action,request_id,detail)
        VALUES(:pid,:vid,:uid,:action,:request,CAST(:detail AS jsonb))'''),
        {'pid': person_id, 'vid': version_id, 'uid': int(user['user_id']), 'action': action,
         'request': request_id.get() or str(uuid4()), 'detail': json.dumps(detail or {}, ensure_ascii=False, default=str)})


def denied(user, person_id, version_id=None):
    # Commit the denial independently of the rejected business transaction.
    with engine.begin() as conn:
        event(conn, user, person_id, None, 'access_denied', {'version_id': version_id})
    raise HTTPException(403, 'Недостаточно прав для операции с файлом.')


def require_schema(conn):
    if conn.execute(text("SELECT to_regclass('public.certificate_classifier_entries')")).scalar_one() is None:
        raise HTTPException(503, 'Файлы сотрудников ещё не подключены администратором.')


def row(conn, version_id, lock=False):
    result = conn.execute(text('''SELECT v.*,s.person_id,s.kind,s.title
        FROM public.personnel_file_versions v JOIN public.personnel_file_sets s USING(set_id)
        WHERE v.version_id=:vid''' + (' FOR UPDATE OF v' if lock else '')), {'vid': version_id}).mappings().one_or_none()
    if result is None:
        raise HTTPException(404, 'Версия файла не найдена.')
    return dict(result)


def public(r, rights, conn=None):
    # Never return a storage key, checksums of private previews or unfiltered row metadata.
    fields = ('version_id','set_id','person_id','kind','title','version_no','state','revision','original_name',
              'mime_type','byte_size','page_count','created_at','uploaded_by','decided_by','decided_at','reason',
              'proposed_name','name_applied_at','employee_document_id','replaces_version_id')
    return {**{k: r.get(k) for k in fields}, 'can_review': rights.reviewer,
            'can_replace': rights.upload, 'can_export': rights.export(r['kind'], r['state']),
            'certificate': certificates.document(conn, r.get('employee_document_id'), r['person_id']) if conn is not None and r['kind']=='certificate' else None}


def listing(user, person_id):
    with engine.begin() as conn:
        require_schema(conn)
        rights = access(conn, user, person_id)
        if not (rights.owner or rights.reviewer or rights.technical or rights.leader):
            denied(user, person_id)
        records = conn.execute(text('''SELECT v.*,s.person_id,s.kind,s.title
            FROM public.personnel_file_sets s JOIN public.personnel_file_versions v USING(set_id)
            WHERE s.person_id=:pid ORDER BY s.created_at DESC,v.version_no DESC'''), {'pid': person_id}).mappings()
        items = [public(dict(r), rights, conn) for r in records if rights.visible(r['state'])]
        event(conn, user, person_id, None, 'list')
        notifications = []
        if rights.owner:
            notifications = [dict(r) for r in conn.execute(text('''SELECT event_id,action,detail,created_at
                FROM public.personnel_file_events WHERE person_id=:pid AND action IN ('approve','return','revoke','name_applied')
                AND event_id > COALESCE((SELECT last_event_id FROM public.personnel_file_inbox WHERE user_id=:uid),0)
                ORDER BY event_id DESC LIMIT 50'''), {'pid': person_id, 'uid': user['user_id']}).mappings()]
        return {'items': items, 'can_upload': rights.upload, 'can_review': rights.reviewer, 'can_history': rights.owner or rights.reviewer or rights.technical, 'notifications': notifications}


def submit(user, person_id, *, kind, title, content, mime, filename, set_id=None, expected_revision=None, expected_version_id=None, proposed_name=None, certificate=None):
    if kind not in KINDS or not title.strip() or len(title.strip()) > 300:
        raise HTTPException(422, 'Выберите назначение и укажите название до 300 символов.')
    if proposed_name and kind != 'name_change':
        raise HTTPException(422, 'Новое ФИО указывается только для основания изменения ФИО.')
    if certificate and kind != 'certificate':
        raise HTTPException(422, 'Реквизиты сертификата допустимы только для сертификата.')
    with engine.connect() as conn:
        require_schema(conn)
        rights = access(conn, user, person_id)
        if not rights.upload:
            denied(user, person_id)
    key = str(uuid4())
    try:
        checksum, pages = storage.prepare(key, content, mime, kind)
    except HTTPException as exc:
        with engine.begin() as conn:
            event(conn, user, person_id, None, 'technical_rejected', {'status': exc.status_code, 'mime_type': mime, 'byte_size': len(content)})
        raise
    committed = False
    try:
        previews = {str(i): hashlib.sha256(storage.path(key, f'page-{i}.png').read_bytes()).hexdigest() for i in range(1, pages+1)}
        with engine.begin() as conn:
            # Serialize a new set/photo singleton and all concurrent replacements for this Person.
            conn.execute(text('SELECT person_id FROM public.persons WHERE person_id=:pid FOR NO KEY UPDATE'), {'pid': person_id}).one()
            rights = access(conn, user, person_id)
            if not rights.upload:
                denied(user, person_id)
            if set_id is None and kind == 'photo':
                set_id = conn.execute(text("SELECT set_id FROM public.personnel_file_sets WHERE person_id=:pid AND kind='photo'"), {'pid': person_id}).scalar_one_or_none()
            if set_id is not None:
                parent = conn.execute(text('SELECT * FROM public.personnel_file_sets WHERE set_id=:sid AND person_id=:pid AND kind=:kind'),
                    {'sid': set_id, 'pid': person_id, 'kind': kind}).mappings().one_or_none()
                if not parent:
                    raise HTTPException(404, 'Комплект не найден.')
                latest = conn.execute(text('SELECT * FROM public.personnel_file_versions WHERE set_id=:sid ORDER BY version_no DESC LIMIT 1 FOR UPDATE'), {'sid': set_id}).mappings().one()
                if expected_revision is None or latest['revision'] != expected_revision or str(latest['version_id']) != str(expected_version_id):
                    raise HTTPException(409, 'Версия изменилась. Обновите список файлов.')
                if latest['state'] == 'pending':
                    raise HTTPException(409, 'Предыдущая версия ещё находится на проверке.')
                version_no = latest['version_no'] + 1
            else:
                set_id = str(uuid4())
                conn.execute(text('INSERT INTO public.personnel_file_sets(set_id,person_id,kind,title) VALUES(:sid,:pid,:kind,:title)'),
                    {'sid': set_id, 'pid': person_id, 'kind': kind, 'title': title.strip()})
                version_no = 1
            vid = str(uuid4())
            document_id, registry_created = certificates.attach(conn, user, person_id, certificate) if kind=='certificate' else (None, False)
            replaces = conn.execute(text("SELECT version_id FROM personnel_file_versions WHERE set_id=:sid AND state='approved'"), {'sid': set_id}).scalar_one_or_none()
            conn.execute(text('''INSERT INTO public.personnel_file_versions
                (version_id,set_id,version_no,state,storage_key,original_name,mime_type,byte_size,checksum_sha256,page_count,uploaded_by,proposed_name,preview_checksums,employee_document_id,registry_created_by_upload,replaces_version_id)
                VALUES(:vid,:sid,:no,'pending',:key,:name,:mime,:size,:sha,:pages,:uid,CAST(:proposal AS jsonb),CAST(:previews AS jsonb),:document_id,:registry_created,:replaces)'''),
                {'vid': vid, 'sid': set_id, 'no': version_no, 'key': key,
                 'name': ''.join(c for c in Path(filename.replace('\\','/')).name if ord(c) >= 32 and ord(c) != 127)[:200] or 'document', 'mime': mime, 'size': len(content),
                 'sha': checksum, 'pages': pages, 'uid': user['user_id'],
                 'proposal': json.dumps(proposed_name) if proposed_name else None, 'previews': json.dumps(previews),
                 'document_id': document_id, 'registry_created': registry_created, 'replaces': replaces})
            event(conn, user, person_id, vid, 'submitted', {'checksum_sha256': checksum, 'byte_size': len(content), 'mime_type': mime, 'technical_check': 'passed', 'version_no': version_no, 'employee_document_id': document_id, 'replaces_version_id': replaces})
            result = public(row(conn, vid), rights, conn)
        committed = True
        return result
    finally:
        if not committed:
            storage.discard(key)


def decide(user, version_id, *, expected_revision, action, reason, expected_certificate_context=None):
    with engine.begin() as conn:
        require_schema(conn)
        initial = row(conn, version_id)
        conn.execute(text('SELECT person_id FROM public.persons WHERE person_id=:pid FOR NO KEY UPDATE'), {'pid': initial['person_id']}).one()
        return decide_participating(conn, user, version_id, expected_revision=expected_revision,
            action=action, reason=reason, expected_certificate_context=expected_certificate_context)


def decide_participating(conn, user, version_id, *, expected_revision, action, reason,
                         expected_certificate_context=None):
    """Apply a file decision inside a caller-owned transaction after the Person lock."""
    require_schema(conn)
    r = row(conn, version_id, lock=True)
    pid = r['person_id']
    rights = access(conn, user, pid)
    if not rights.reviewer:
        denied(user, pid, version_id)
    if r['revision'] != expected_revision:
        raise HTTPException(409, 'Решение устарело. Обновите список файлов.')
    try:
        state = transition(r['state'], action, reason)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    comparison = None
    if action == 'approve':
        latest = conn.execute(text('SELECT max(version_no) FROM public.personnel_file_versions WHERE set_id=:sid'), {'sid': r['set_id']}).scalar_one()
        if r['version_no'] != latest:
            raise HTTPException(409, 'Нельзя одобрить устаревшую версию.')
        if r['kind']=='certificate':
            comparison = certificates.context(conn, r, lock=True)
            if not comparison['can_approve']:
                # Separate append-only denial audit; do not wait on the locked version FK.
                with engine.begin() as audit_conn:
                    event(audit_conn, user, pid, None, 'replacement_blocked', {'version_id': version_id, 'comparison': comparison})
                raise HTTPException(409, comparison['basis']['description'])
            if expected_certificate_context != comparison['context_token']:
                raise HTTPException(409, 'Сравнение сертификатов изменилось. Откройте решение заново.')
            certificates.publish(conn, r, comparison)
        storage.read(r['storage_key'], r['checksum_sha256'])
        old = conn.execute(text("UPDATE public.personnel_file_versions SET state='superseded',revision=revision+1 WHERE set_id=:sid AND state='approved' RETURNING version_id"), {'sid': r['set_id']}).scalars().all()
        for previous in old:
            event(conn, user, pid, previous, 'superseded', {'replacement_version_id': version_id, 'certificate_comparison': comparison})
    conn.execute(text('''UPDATE public.personnel_file_versions SET state=:state,revision=revision+1,
        decided_by=:uid,decided_at=now(),reason=:reason WHERE version_id=:vid'''),
        {'state': state, 'uid': user['user_id'], 'reason': reason.strip(), 'vid': version_id})
    if r['kind']=='certificate' and r['registry_created_by_upload'] and action=='return':
        conn.execute(text("UPDATE employee_documents SET verification_status='REJECTED',updated_at=now() WHERE document_id=:id"), {'id': r['employee_document_id']})
    if r['kind']=='certificate' and r.get('employee_document_id') and action=='revoke':
        conn.execute(text("UPDATE employee_documents SET lifecycle_status='SUPERSEDED',updated_at=now() WHERE document_id=:id"), {'id': r['employee_document_id']})
    event(conn, user, pid, version_id, action, {'before': r['state'], 'after': state, 'reason': reason.strip(), 'employee_document_id': r.get('employee_document_id'), 'certificate_comparison': comparison})
    return public(row(conn, version_id), rights, conn)


def review_context(user, version_id):
    with engine.begin() as conn:
        require_schema(conn)
        r = row(conn, version_id)
        if not access(conn, user, r['person_id']).reviewer:
            denied(user, r['person_id'], version_id)
        if r['kind']!='certificate' or r['state']!='pending':
            raise HTTPException(409, 'Сравнение доступно для сертификата на проверке.')
        return certificates.context(conn, r)


def registry_options(user, person_id):
    with engine.begin() as conn:
        require_schema(conn)
        if not access(conn, user, person_id).upload:
            denied(user, person_id)
        ids = conn.execute(text('''SELECT ed.document_id FROM employee_documents ed
            JOIN employees emp USING(employee_id) JOIN document_types dt USING(document_type_id)
            WHERE emp.person_id=:pid AND dt.code='SPECIALIST_CERTIFICATION' AND ed.lifecycle_status='ACTIVE'
            AND NOT EXISTS(SELECT 1 FROM personnel_file_versions v WHERE v.employee_document_id=ed.document_id)
            ORDER BY ed.document_id'''), {'pid': person_id}).scalars().all()
        return {'items': [certificates.document(conn, id, person_id) for id in ids]}


def content(user, version_id, *, operation, page=1):
    with engine.begin() as conn:
        require_schema(conn)
        r = row(conn, version_id)
        rights = access(conn, user, r['person_id'])
        if not rights.visible(r['state']) or (operation in {'download', 'print'} and not rights.export(r['kind'], r['state'])):
            denied(user, r['person_id'], version_id)
        if not 1 <= page <= r['page_count']:
            raise HTTPException(404, 'Страница не найдена.')
        data = storage.read(r['storage_key'], r['checksum_sha256'], None if operation == 'download' else page)
        if operation != 'download' and hashlib.sha256(data).hexdigest() != r['preview_checksums'].get(str(page)):
            raise HTTPException(404, 'Превью недоступно.')
        event(conn, user, r['person_id'], version_id, operation, {'page': page if operation != 'download' else None})
        return data, r['mime_type'] if operation == 'download' else 'image/png', r


def history(user, person_id):
    with engine.begin() as conn:
        require_schema(conn)
        rights = access(conn, user, person_id)
        if not (rights.owner or rights.reviewer or rights.technical):
            denied(user, person_id)
        event(conn, user, person_id, None, 'history')
        return [dict(x) for x in conn.execute(text('''SELECT event_id,version_id,actor_id,action,created_at,detail
            FROM public.personnel_file_events WHERE person_id=:pid ORDER BY event_id DESC LIMIT 500'''), {'pid': person_id}).mappings()]


def apply_name(user, version_id, *, expected_revision, expected_full_name, effective_date, reason):
    with engine.begin() as conn:
        require_schema(conn)
        r = row(conn, version_id)
        pid = r['person_id']
        person = conn.execute(text('SELECT full_name,last_name,first_name,middle_name FROM public.persons WHERE person_id=:pid FOR NO KEY UPDATE'), {'pid': pid}).mappings().one()
        r = row(conn, version_id, lock=True)
        rights = access(conn, user, pid)
        if not rights.reviewer:
            denied(user, pid, version_id)
        if r['revision'] != expected_revision or r['state'] != 'approved' or r['kind'] != 'name_change' or r['name_applied_at']:
            raise HTTPException(409, 'Основание не одобрено, устарело или уже применено.')
        if person['full_name'] != expected_full_name or not reason.strip():
            raise HTTPException(409, 'ФИО изменилось либо не указана причина. Обновите карточку.')
        from app.control_list_projection.service import organization_timezone
        if effective_date > datetime.now(organization_timezone()[1]).date():
            raise HTTPException(422, 'Будущая дата изменения ФИО пока не поддерживается.')
        identity = conn.execute(text("""SELECT v.version_id FROM public.personnel_file_versions v
            JOIN public.personnel_file_sets s USING(set_id) WHERE s.person_id=:pid AND s.kind='identity'
            AND v.state='approved' ORDER BY v.decided_at DESC LIMIT 1"""), {'pid': pid}).scalar_one_or_none()
        if identity is None:
            raise HTTPException(409, 'Сначала одобрите удостоверение личности работника.')
        storage.read(r['storage_key'], r['checksum_sha256'])
        identity_file = row(conn, identity)
        storage.read(identity_file['storage_key'], identity_file['checksum_sha256'])
        proposal = r['proposed_name']
        if not proposal:
            raise HTTPException(422, 'Предлагаемое ФИО не указано.')
        name = ' '.join(proposal[k] for k in ('last_name','first_name','middle_name') if proposal.get(k))
        conn.execute(text('''UPDATE public.persons SET last_name=:last_name,first_name=:first_name,
            middle_name=:middle_name,full_name=:name,updated_at=now() WHERE person_id=:pid'''), {**proposal, 'name': name, 'pid': pid})
        conn.execute(text('UPDATE public.employees SET full_name=:name WHERE person_id=:pid'), {'name': name, 'pid': pid})
        conn.execute(text('UPDATE public.personnel_file_versions SET name_applied_at=now(),revision=revision+1 WHERE version_id=:vid'), {'vid': version_id})
        detail = {'before': dict(person), 'after': {**proposal, 'full_name': name}, 'reason': reason.strip(), 'effective_date': str(effective_date), 'identity_version_id': str(identity)}
        event(conn, user, pid, version_id, 'name_applied', detail)
        from app.services.personnel_record_event_service import emit_personnel_record_event
        emit_personnel_record_event(conn, person_id=pid, domain_code='general_information', record_table_name='persons',
            record_id=pid, event_type='PPR_NAME_CHANGED_FROM_FILE', actor_id=str(user['user_id']), event_payload={**detail, 'file_version_id': str(version_id)})
        return public(row(conn, version_id), rights, conn)


def review_queue(user, after):
    with engine.begin() as conn:
        require_schema(conn)
        candidates = conn.execute(text('''SELECT v.*,s.person_id,s.kind,s.title,p.full_name,
            row_number() OVER(ORDER BY v.created_at,v.version_id) AS position
            FROM public.personnel_file_versions v JOIN public.personnel_file_sets s USING(set_id)
            JOIN public.persons p USING(person_id) WHERE v.state='pending'
              AND (CAST(:after AS uuid) IS NULL OR v.version_id>CAST(:after AS uuid))
            ORDER BY v.version_id LIMIT 100'''), {'after': after}).mappings().all()
        items = []
        for r in candidates:
            rights = access(conn, user, r['person_id'])
            if rights.reviewer:
                items.append({**public(dict(r), rights, conn), 'full_name': r['full_name']})
        return {'items': items, 'next': str(candidates[-1]['version_id']) if len(candidates) == 100 else None}


def active_photo(user, person_id):
    """Return (managed, bytes). A revoked managed photo must never reveal an old legacy photo."""
    with engine.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.personnel_file_sets')")).scalar_one() is None:
            return False, None
        records = [dict(r) for r in conn.execute(text('''SELECT v.*,s.person_id,s.kind,s.title
            FROM public.personnel_file_versions v JOIN public.personnel_file_sets s USING(set_id)
            WHERE s.person_id=:pid AND s.kind='photo' ORDER BY v.version_no DESC'''), {'pid': person_id}).mappings()]
        managed = bool(conn.execute(text('''SELECT EXISTS(SELECT 1 FROM public.personnel_file_events e
            JOIN public.personnel_file_versions v USING(version_id) JOIN public.personnel_file_sets s USING(set_id)
            WHERE s.person_id=:pid AND s.kind='photo' AND e.action='approve')'''), {'pid': person_id}).scalar_one())
        approved = next((r for r in records if r['state']=='approved'), None)
        if not approved:
            return managed, None
        rights = access(conn, user, person_id)
        if not rights.visible('approved'):
            denied(user, person_id, approved['version_id'])
        result = storage.read(approved['storage_key'], approved['checksum_sha256'])
        event(conn, user, person_id, approved['version_id'], 'view')
        return True, result


def acknowledge(user, person_id, through_event_id):
    with engine.begin() as conn:
        require_schema(conn)
        if not access(conn, user, person_id).owner:
            denied(user, person_id)
        last = conn.execute(text("SELECT max(event_id) FROM public.personnel_file_events WHERE person_id=:pid AND event_id<=:eid"),
                            {'pid': person_id, 'eid': through_event_id}).scalar_one()
        if last is not None:
            conn.execute(text("""INSERT INTO public.personnel_file_inbox(user_id,last_event_id) VALUES(:uid,:eid)
                ON CONFLICT(user_id) DO UPDATE SET last_event_id=GREATEST(personnel_file_inbox.last_event_id,EXCLUDED.last_event_id)"""),
                {'uid': user['user_id'], 'eid': last})
        return {'ok': True}


def authorize_photo_export(user, person_id):
    """The existing card PDF must not smuggle a view-only portrait into an export."""
    with engine.begin() as conn:
        require_schema(conn)
        if not access(conn, user, person_id).reviewer:
            denied(user, person_id)
        event(conn, user, person_id, None, 'download', {'kind': 'photo', 'source': 'person_card_pdf'})
