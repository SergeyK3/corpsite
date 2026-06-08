-- Minimal QM pilot regular task templates (2 weekly templates for catch-up Preview).
-- Safe to re-run (idempotent upserts by code). Does NOT delete existing templates.
--
-- Prerequisites:
--   1. scripts/pilot/org_structure_bootstrap.sql
--   2. scripts/pilot/directory_prereq_bootstrap.sql
--   3. scripts/pilot/qm_roles_users_bootstrap.sql
--
-- After apply: catch-up Preview with org_unit_id=44, preset=past_week
-- (do NOT run live catch-up until templates are verified).
--
-- Note: regular_tasks.assignment_scope is stored as 'unit' here, but catch-up
-- normalizes it to 'structural' on tasks (see regular_tasks_service._normalize_assignment_scope).
-- This is expected; not a RBAC bug.
--
-- Example (review before apply on VPS):
--   docker exec -i corpsite-pg psql -U postgres -d corpsite < scripts/pilot/qm_regular_tasks_bootstrap.sql

BEGIN;

INSERT INTO public.regular_tasks (
    code,
    title,
    is_active,
    executor_role_id,
    initiator_role_id,
    target_role_id,
    assignment_scope,
    schedule_type,
    schedule_params,
    create_offset_days,
    due_offset_days,
    deadline_offset_days,
    escalation_offset_days,
    owner_unit_id,
    created_by_user_id,
    updated_at
)
SELECT
    'QM_PILOT_WEEKLY_HOSP',
    'Пилот QM: еженедельный контроль (госпитальный эксперт)',
    TRUE,
    ex.role_id,
    head.role_id,
    head.role_id,
    'unit',
    'weekly',
    '{"byweekday":[3]}'::jsonb,
    0,
    0,
    0,
    0,
    44,
    u.user_id,
    now()
FROM public.roles ex
CROSS JOIN public.roles head
JOIN public.users u ON lower(u.login) = 'qm_head@corp.local'
WHERE ex.code = 'QM_HOSP'
  AND head.code = 'QM_HEAD'
ON CONFLICT (code) DO UPDATE
SET
    title = EXCLUDED.title,
    is_active = EXCLUDED.is_active,
    executor_role_id = EXCLUDED.executor_role_id,
    initiator_role_id = EXCLUDED.initiator_role_id,
    target_role_id = EXCLUDED.target_role_id,
    assignment_scope = EXCLUDED.assignment_scope,
    schedule_type = EXCLUDED.schedule_type,
    schedule_params = EXCLUDED.schedule_params,
    create_offset_days = EXCLUDED.create_offset_days,
    due_offset_days = EXCLUDED.due_offset_days,
    deadline_offset_days = EXCLUDED.deadline_offset_days,
    escalation_offset_days = EXCLUDED.escalation_offset_days,
    owner_unit_id = EXCLUDED.owner_unit_id,
    created_by_user_id = EXCLUDED.created_by_user_id,
    updated_at = now();

INSERT INTO public.regular_tasks (
    code,
    title,
    is_active,
    executor_role_id,
    initiator_role_id,
    target_role_id,
    assignment_scope,
    schedule_type,
    schedule_params,
    create_offset_days,
    due_offset_days,
    deadline_offset_days,
    escalation_offset_days,
    owner_unit_id,
    created_by_user_id,
    updated_at
)
SELECT
    'QM_PILOT_WEEKLY_AMB',
    'Пилот QM: еженедельный контроль (амбулаторный эксперт)',
    TRUE,
    ex.role_id,
    head.role_id,
    head.role_id,
    'unit',
    'weekly',
    '{"byweekday":[3]}'::jsonb,
    0,
    0,
    0,
    0,
    44,
    u.user_id,
    now()
FROM public.roles ex
CROSS JOIN public.roles head
JOIN public.users u ON lower(u.login) = 'qm_head@corp.local'
WHERE ex.code = 'QM_AMB'
  AND head.code = 'QM_HEAD'
ON CONFLICT (code) DO UPDATE
SET
    title = EXCLUDED.title,
    is_active = EXCLUDED.is_active,
    executor_role_id = EXCLUDED.executor_role_id,
    initiator_role_id = EXCLUDED.initiator_role_id,
    target_role_id = EXCLUDED.target_role_id,
    assignment_scope = EXCLUDED.assignment_scope,
    schedule_type = EXCLUDED.schedule_type,
    schedule_params = EXCLUDED.schedule_params,
    create_offset_days = EXCLUDED.create_offset_days,
    due_offset_days = EXCLUDED.due_offset_days,
    deadline_offset_days = EXCLUDED.deadline_offset_days,
    escalation_offset_days = EXCLUDED.escalation_offset_days,
    owner_unit_id = EXCLUDED.owner_unit_id,
    created_by_user_id = EXCLUDED.created_by_user_id,
    updated_at = now();

COMMIT;

-- Quick verify: pilot templates in unit 44
SELECT
    rt.regular_task_id,
    rt.code,
    rt.title,
    rt.is_active,
    rt.owner_unit_id,
    rt.schedule_type,
    rt.schedule_params,
    ex.code AS executor_role_code,
    head.code AS target_role_code,
    u.login AS created_by_login
FROM public.regular_tasks rt
LEFT JOIN public.roles ex ON ex.role_id = rt.executor_role_id
LEFT JOIN public.roles head ON head.role_id = rt.target_role_id
LEFT JOIN public.users u ON u.user_id = rt.created_by_user_id
WHERE rt.code IN ('QM_PILOT_WEEKLY_HOSP', 'QM_PILOT_WEEKLY_AMB')
ORDER BY rt.code;
