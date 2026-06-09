-- Synthetic fixture for RBAC visibility gaps (issue #118).
-- Reproduces:
--   1) pure legacy approver: target_role_id match, executor_role_id differs
--   2) historical report author: user submitted an older report, not the latest
--
-- Safe to re-run (deletes fixture rows by fixed IDs / codes first).
-- Does NOT modify application code.
--
-- Apply:
--   docker exec -i corpsite-pg psql -U postgres -d corpsite < scripts/pilot/rbac_visibility_gaps_fixture.sql
-- Verify:
--   ./.venv/bin/python scripts/pilot/verify_rbac_visibility_gaps.py

BEGIN;

-- ---------------------------------------------------------------------------
-- Cleanup (fixed synthetic IDs)
-- ---------------------------------------------------------------------------
DELETE FROM public.task_reports
WHERE report_id IN (10001, 10002, 10003);

DELETE FROM public.tasks
WHERE task_id IN (10001, 10002);

DELETE FROM public.regular_tasks
WHERE code IN ('RBAC_GAP_LEGACY', 'RBAC_GAP_HISTORICAL');

-- ---------------------------------------------------------------------------
-- Shared lookups
-- ---------------------------------------------------------------------------
-- QM roles/users expected from qm_roles_users_bootstrap.sql:
--   QM_COMPLAINT_REG -> role_id 6, user_id 5 (qm_complaint_reg@corp.local)
--   QM_COMPLAINT_PAT -> role_id 7, user_id 6 (qm_complaint_pat@corp.local)
--   QM_HOSP          -> role_id 4, user_id 3 (qm_hosp@corp.local)
--   QM_AMB           -> role_id 5, user_id 4 (qm_amb@corp.local)

-- ---------------------------------------------------------------------------
-- Gap 1: pure legacy approver
-- Viewer: user_id=5 (role_id=6) sees list via regular_tasks.target_role_id
-- Task executor_role_id=7 (different role), status=WAITING_APPROVAL
-- ---------------------------------------------------------------------------
INSERT INTO public.regular_tasks (
    regular_task_id,
    code,
    title,
    is_active,
    executor_role_id,
    initiator_role_id,
    target_role_id,
    assignment_scope,
    schedule_type,
    schedule_params,
    owner_unit_id,
    created_by_user_id,
    updated_at
)
SELECT
    10001,
    'RBAC_GAP_LEGACY',
    'RBAC gap fixture: pure legacy approver',
    TRUE,
    pat.role_id,
    admin.role_id,
    reg.role_id,
    'unit',
    'weekly',
    '{"byweekday":[1]}'::jsonb,
    44,
    u_admin.user_id,
    now()
FROM public.roles pat
JOIN public.roles reg ON reg.code = 'QM_COMPLAINT_REG'
JOIN public.roles admin ON admin.code = 'ADMIN'
JOIN public.users u_admin ON lower(u_admin.login) = 'admin'
WHERE pat.code = 'QM_COMPLAINT_PAT';

INSERT INTO public.tasks (
    task_id,
    period_id,
    regular_task_id,
    title,
    description,
    initiator_user_id,
    created_by_user_id,
    approver_user_id,
    executor_role_id,
    assignment_scope,
    status_id,
    task_kind,
    requires_report,
    requires_approval,
    source_kind,
    created_at,
    updated_at
)
SELECT
    10001,
    1,
    10001,
    'RBAC gap #1: legacy approver (REG approves PAT executor task)',
    'Synthetic fixture for issue #118',
    u_admin.user_id,
    u_admin.user_id,
    NULL,
    pat.role_id,
    'unit',
    ts.status_id,
    'regular',
    TRUE,
    TRUE,
    'manual',
    now(),
    now()
FROM public.roles pat
JOIN public.users u_admin ON lower(u_admin.login) = 'admin'
JOIN public.task_statuses ts ON ts.code = 'WAITING_APPROVAL'
WHERE pat.code = 'QM_COMPLAINT_PAT';

-- ---------------------------------------------------------------------------
-- Gap 2: historical report author
-- Viewer: user_id=3 (qm_hosp) submitted an older report
-- Latest report: user_id=4 (qm_amb, current executor role holder)
-- ---------------------------------------------------------------------------
INSERT INTO public.regular_tasks (
    regular_task_id,
    code,
    title,
    is_active,
    executor_role_id,
    initiator_role_id,
    target_role_id,
    assignment_scope,
    schedule_type,
    schedule_params,
    owner_unit_id,
    created_by_user_id,
    updated_at
)
SELECT
    10002,
    'RBAC_GAP_HISTORICAL',
    'RBAC gap fixture: historical report author',
    TRUE,
    amb.role_id,
    admin.role_id,
    head.role_id,
    'unit',
    'weekly',
    '{"byweekday":[1]}'::jsonb,
    44,
    u_admin.user_id,
    now()
FROM public.roles amb
JOIN public.roles head ON head.code = 'QM_HEAD'
JOIN public.roles admin ON admin.code = 'ADMIN'
JOIN public.users u_admin ON lower(u_admin.login) = 'admin'
WHERE amb.code = 'QM_AMB';

INSERT INTO public.tasks (
    task_id,
    period_id,
    regular_task_id,
    title,
    description,
    initiator_user_id,
    created_by_user_id,
    approver_user_id,
    executor_role_id,
    assignment_scope,
    status_id,
    task_kind,
    requires_report,
    requires_approval,
    source_kind,
    created_at,
    updated_at
)
SELECT
    10002,
    1,
    10002,
    'RBAC gap #2: historical report author (HOSP old, AMB latest)',
    'Synthetic fixture for issue #118',
    u_admin.user_id,
    u_admin.user_id,
    NULL,
    amb.role_id,
    'unit',
    ts.status_id,
    'regular',
    TRUE,
    TRUE,
    'manual',
    now(),
    now()
FROM public.roles amb
JOIN public.users u_admin ON lower(u_admin.login) = 'admin'
JOIN public.task_statuses ts ON ts.code = 'WAITING_REPORT'
WHERE amb.code = 'QM_AMB';

INSERT INTO public.task_reports (
    report_id,
    task_id,
    report_link,
    submitted_at,
    submitted_by,
    current_comment
)
VALUES
    (
        10001,
        10002,
        'https://fixture.local/report-hosp-old',
        '2026-06-01 10:00:00+00',
        3,
        'Older report by qm_hosp (historical author)'
    ),
    (
        10002,
        10002,
        'https://fixture.local/report-amb-latest',
        '2026-06-02 12:00:00+00',
        4,
        'Latest report by qm_amb (current submitter)'
    );

COMMIT;

-- Quick verify fixture rows
SELECT
    t.task_id,
    t.title,
    ts.code AS status,
    t.executor_role_id,
    rt.target_role_id,
    t.approver_user_id
FROM public.tasks t
LEFT JOIN public.task_statuses ts ON ts.status_id = t.status_id
LEFT JOIN public.regular_tasks rt ON rt.regular_task_id = t.regular_task_id
WHERE t.task_id IN (10001, 10002)
ORDER BY t.task_id;

SELECT report_id, task_id, submitted_by, submitted_at
FROM public.task_reports
WHERE task_id = 10002
ORDER BY submitted_at;
