"""Central, explicitly authorized HR stewardship. No per-upload mapping overrides."""
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def can_manage(conn, user):
    from app.services.access_resolver_service import _collect_subject_ids, _load_active_grants
    from app.security.directory_scope import is_system_admin
    from app.security.sysadmin_assistant import is_assistant
    if is_system_admin(user) or is_assistant(user):
        return False
    pid = conn.execute(text('SELECT person_id FROM employees WHERE employee_id=:id'), {'id': user.get('employee_id')}).scalar_one_or_none()
    subjects = _collect_subject_ids(conn, user_id=int(user['user_id']), employee_id=user.get('employee_id'), person_id=pid, role_id=user.get('role_id'))
    grants = [g for g in _load_active_grants(conn, subjects) if g.get('scope_type')=='GLOBAL'
              and g.get('resource_key') in {'*','certificate_classifiers'}]
    if any(g.get('access_level')=='NONE' for g in grants):
        return False
    codes = {g['access_role_code'] for g in grants}
    return 'CERTIFICATE_CLASSIFIERS_MANAGE' in codes and bool(codes & {'HR_ENROLLMENT_MANAGER','PERSONNEL_FILES_REVIEW'})


def audit(conn, user, action, detail):
    import json
    conn.execute(text('INSERT INTO certificate_classifier_events(actor_id,action,detail) VALUES(:uid,:action,CAST(:detail AS jsonb))'),
        {'uid': user['user_id'], 'action': action, 'detail': json.dumps(detail, default=str, ensure_ascii=False)})


def catalog(user):
    from app.personnel_files.service import engine, require_schema
    with engine.begin() as conn:
        require_schema(conn)
        manager = can_manage(conn, user)
        editions = [dict(r) for r in conn.execute(text('SELECT * FROM certificate_classifier_editions ORDER BY effective_from,edition_id')).mappings()]
        entries = [dict(r) for r in conn.execute(text('''SELECT e.*,d.code AS edition_code,d.title AS edition_title,d.accepts_new
            FROM certificate_classifier_entries e JOIN certificate_classifier_editions d USING(edition_id)
            ORDER BY d.effective_from,e.specialty_name''')).mappings()]
        mappings = [dict(r) for r in conn.execute(text('SELECT * FROM certificate_specialty_mappings ORDER BY mapping_id')).mappings()]
        specialties = [dict(r) for r in conn.execute(text('SELECT medical_specialty_id,name FROM medical_specialties WHERE is_active ORDER BY name')).mappings()] if manager else []
        return {'editions': editions, 'entries': entries, 'mappings': mappings, 'medical_specialties': specialties, 'can_manage': manager}


def manage(user, operation, payload):
    from app.personnel_files.service import engine, require_schema
    try:
        with engine.begin() as conn:
            require_schema(conn)
            if not can_manage(conn, user):
                raise HTTPException(403, 'Требуются кадровое полномочие и отдельное центральное разрешение на ведение соответствий.')
            if operation=='edition':
                result = conn.execute(text('''INSERT INTO certificate_classifier_editions(code,title,source_reference,effective_from,created_by)
                    VALUES(:code,:title,:source_reference,:effective_from,:uid) RETURNING *'''), {**payload, 'uid': user['user_id']}).mappings().one()
            elif operation=='entry':
                result = conn.execute(text('''INSERT INTO certificate_classifier_entries(edition_id,medical_specialty_id,specialty_code,specialty_name)
                    VALUES(:edition_id,:medical_specialty_id,:specialty_code,:specialty_name) RETURNING *'''), payload).mappings().one()
            elif operation=='mapping':
                editions = conn.execute(text('SELECT edition_id FROM certificate_classifier_entries WHERE entry_id IN (:from_entry_id,:to_entry_id) FOR SHARE'), payload).scalars().all()
                if len(editions)!=2 or editions[0]==editions[1]:
                    raise HTTPException(422, 'Для соответствия выберите две специальности из разных редакций.')
                result = conn.execute(text('''INSERT INTO certificate_specialty_mappings
                    (from_entry_id,to_entry_id,source_reference,reason,effective_from,confirmed_by)
                    VALUES(:from_entry_id,:to_entry_id,:source_reference,:reason,:effective_from,:uid) RETURNING *'''), {**payload, 'uid': user['user_id']}).mappings().one()
            elif operation=='edition-availability':
                result = conn.execute(text('UPDATE certificate_classifier_editions SET accepts_new=:accepts_new WHERE edition_id=:edition_id RETURNING *'), payload).mappings().one_or_none()
            elif operation=='mapping-revoke':
                result = conn.execute(text('UPDATE certificate_specialty_mappings SET active=false WHERE mapping_id=:mapping_id AND active RETURNING *'), payload).mappings().one_or_none()
            else:
                raise HTTPException(422, 'Неизвестное действие.')
            if result is None:
                raise HTTPException(404, 'Запись не найдена или действие уже выполнено.')
            detail = dict(result)
            if payload.get('reason'): detail['reason'] = payload['reason']
            audit(conn, user, operation, detail)
            return dict(result)
    except IntegrityError:
        raise HTTPException(409, 'Такая запись уже существует либо справочная запись не найдена.') from None
