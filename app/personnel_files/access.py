"""Fresh server-side ownership, explicit scoped grants and direct supervision."""
from __future__ import annotations
from sqlalchemy import text
from fastapi import HTTPException
from app.personnel_files.policy import Access


def self_person(user: dict) -> int:
    from app.services.self_personal_card_access_service import SelfPersonalCardAccessService
    result = SelfPersonalCardAccessService().resolve_for_user(user)
    if result.status != 'READY' or result.composite is None:
        raise HTTPException(404, 'Связь с личной карточкой не определена.')
    return int(result.composite.person_id)


def access(conn, user: dict, person_id: int) -> Access:
    from app.security.directory_scope import is_system_admin
    from app.security.sysadmin_assistant import has_hr_support, is_assistant
    from app.services.access_resolver_service import _collect_subject_ids, _load_active_grants
    from app.org_scope.resolver import resolve_subtree_unit_ids
    uid = int(user['user_id'])
    owner = conn.execute(text('''SELECT EXISTS(
        SELECT 1 FROM public.users u JOIN public.employees e ON e.employee_id=u.employee_id
        WHERE u.user_id=:uid AND u.is_active AND e.is_active AND e.person_id=:pid
          AND (SELECT count(*) FROM public.employees e2 WHERE e2.person_id=:pid AND e2.is_active)=1
    )'''), {'uid': uid, 'pid': person_id}).scalar_one()
    if not conn.execute(text('SELECT 1 FROM public.persons WHERE person_id=:pid'), {'pid': person_id}).first():
        raise HTTPException(404, 'Карточка не найдена.')
    technical = is_system_admin(user) or has_hr_support(user)
    # Technical roles do not inherit reviewer/export capabilities from broad admin grants.
    units = set(conn.execute(text('''SELECT org_unit_id FROM public.employees
        WHERE person_id=:pid AND is_active AND org_unit_id IS NOT NULL'''), {'pid': person_id}).scalars())
    subjects = _collect_subject_ids(conn, user_id=uid, employee_id=user.get('employee_id'),
        person_id=conn.execute(text('SELECT person_id FROM public.employees WHERE employee_id=:eid'),
                               {'eid': user.get('employee_id')}).scalar_one_or_none(), role_id=user.get('role_id'))
    grants = _load_active_grants(conn, subjects)

    def in_scope(grant):
        scope = grant.get('scope_type')
        if scope == 'GLOBAL':
            return True
        if scope == 'SELF':
            return bool(owner)
        if scope == 'ORG_UNIT' and grant.get('scope_id') is not None:
            allowed = {int(grant['scope_id'])}
            if grant.get('include_subtree'):
                allowed = set(resolve_subtree_unit_ids(conn, root_unit_id=int(grant['scope_id'])))
            return bool(units & allowed)
        return False

    scoped = [g for g in grants if in_scope(g) and g.get('resource_key') in {'*', 'personnel_files'}]
    denied = any(g.get('access_level') == 'NONE' and g.get('resource_key') in {'*', 'personnel_files'} for g in scoped)
    codes = {g['access_role_code'] for g in scoped if g.get('access_level') != 'NONE'}
    reviewer = not (technical or is_assistant(user)) and bool(codes & {'HR_ENROLLMENT_MANAGER', 'PERSONNEL_FILES_REVIEW'})
    leader = 'PERSONNEL_FILES_READ' in codes
    # Confirm direct supervision, not a whole department or a title heuristic.
    direct = conn.execute(text('''SELECT EXISTS(
        SELECT 1 FROM public.user_supervisors s
        JOIN public.users subject ON subject.user_id=s.user_id
        JOIN public.employees e ON e.employee_id=subject.employee_id
        WHERE s.supervisor_id=:uid AND subject.is_active AND e.is_active AND e.person_id=:pid
          AND COALESCE((to_jsonb(s)->>'is_active')::boolean, true)
          AND COALESCE((to_jsonb(s)->>'valid_from')::timestamptz, '-infinity') <= now()
          AND COALESCE((to_jsonb(s)->>'valid_to')::timestamptz, 'infinity') > now()
          AND COALESCE(to_jsonb(s)->>'scope','admin')='admin'
    )'''), {'uid': uid, 'pid': person_id}).scalar_one()
    if denied:
        return Access(owner=bool(owner))
    return Access(owner=bool(owner), reviewer=reviewer, technical=technical, leader=leader or bool(direct))
