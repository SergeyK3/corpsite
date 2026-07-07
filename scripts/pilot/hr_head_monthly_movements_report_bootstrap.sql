-- HR_HEAD — monthly personnel movements report (first dedicated HR regular task template).
-- Safe to re-run (idempotent upsert by code). Does NOT delete existing templates.
--
-- Prerequisites:
--   - public.roles.code = 'HR_HEAD'
--   - public.org_units.code = 'HR' (Отдел кадров)
--   - active admin user (login admin) or hr_head@corp.local as created_by fallback
--
-- After apply: verify in UI «Шаблоны регулярных задач» (/admin/regular-tasks).
-- Catch-up (manual, review first): /admin/regular-tasks/catch-up — do NOT run live without confirmation.
--
-- Example (local Docker Postgres):
--   docker exec -i corpsite-pg psql -U postgres -d corpsite < scripts/pilot/hr_head_monthly_movements_report_bootstrap.sql
--
-- Example (psql from host):
--   psql "$DATABASE_URL" -f scripts/pilot/hr_head_monthly_movements_report_bootstrap.sql

BEGIN;

INSERT INTO public.regular_tasks (
    code,
    title,
    description,
    is_active,
    executor_role_id,
    initiator_role_id,
    target_role_id,
    assignment_scope,
    schedule_type,
    schedule_params,
    periodicity,
    create_offset_days,
    due_offset_days,
    deadline_offset_days,
    escalation_offset_days,
    owner_unit_id,
    priority,
    created_by_user_id,
    updated_at
)
SELECT
    'HR_MONTHLY_PERSONNEL_MOVEMENTS_REPORT',
    'Ежемесячный отчет по кадровым движениям',
    $desc$Подготовить ежемесячный отчет по:
- приемам;
- увольнениям;
- переводам;
- выходам в трудовой отпуск;
- возвратам из трудового отпуска;
- выходам в декретный отпуск;
- возвратам из декретного отпуска;
- отпускам без сохранения заработной платы.$desc$,
    TRUE,
    hr.role_id,
    hr.role_id,
    dep.role_id,
    'admin',
    'monthly',
    '{"bymonthday": [1], "time": "10:00"}'::jsonb,
    'monthly',
    0,
    7,
    0,
    0,
    ou.unit_id,
    'medium',
    COALESCE(admin_u.user_id, hr_u.user_id, 1),
    now()
FROM public.roles hr
CROSS JOIN public.org_units ou
CROSS JOIN public.roles dep
LEFT JOIN public.users admin_u
    ON lower(admin_u.login) = 'admin' AND COALESCE(admin_u.is_active, TRUE) = TRUE
LEFT JOIN public.users hr_u
    ON lower(hr_u.login) = 'hr_head@corp.local' AND COALESCE(hr_u.is_active, TRUE) = TRUE
WHERE hr.code = 'HR_HEAD'
  AND ou.code = 'HR'
  AND dep.code = 'DEP_ADMIN'
ON CONFLICT (code) DO UPDATE
SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active,
    executor_role_id = EXCLUDED.executor_role_id,
    initiator_role_id = EXCLUDED.initiator_role_id,
    target_role_id = EXCLUDED.target_role_id,
    assignment_scope = EXCLUDED.assignment_scope,
    schedule_type = EXCLUDED.schedule_type,
    schedule_params = EXCLUDED.schedule_params,
    periodicity = EXCLUDED.periodicity,
    create_offset_days = EXCLUDED.create_offset_days,
    due_offset_days = EXCLUDED.due_offset_days,
    deadline_offset_days = EXCLUDED.deadline_offset_days,
    escalation_offset_days = EXCLUDED.escalation_offset_days,
    owner_unit_id = EXCLUDED.owner_unit_id,
    priority = EXCLUDED.priority,
    created_by_user_id = EXCLUDED.created_by_user_id,
    updated_at = now();

COMMIT;

-- Quick verify
SELECT
    rt.regular_task_id,
    rt.code,
    rt.title,
    rt.is_active,
    rt.schedule_type,
    rt.schedule_params,
    rt.owner_unit_id,
    ou.name AS owner_unit_name,
    ex.code AS executor_role_code,
    ex.name AS executor_role_name,
    tgt.code AS target_role_code,
    u.login AS created_by_login
FROM public.regular_tasks rt
LEFT JOIN public.org_units ou ON ou.unit_id = rt.owner_unit_id
LEFT JOIN public.roles ex ON ex.role_id = rt.executor_role_id
LEFT JOIN public.roles tgt ON tgt.role_id = rt.target_role_id
LEFT JOIN public.users u ON u.user_id = rt.created_by_user_id
WHERE rt.code = 'HR_MONTHLY_PERSONNEL_MOVEMENTS_REPORT';
