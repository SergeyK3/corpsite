-- OPS-009.15 — executor_role_id fix for QM_PILOT_WEEKLY_HOSP + task 10009
-- Run on VPS (read-only first, then fix after review):
--
--   cd /opt/projects/corpsite/app
--   set -a && source .env && set +a
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/ops/ops_009_15_executor_role_fix.sql
--
-- Or use Python helper:
--   ./venv/bin/python scripts/ops/ops_009_15_executor_role_fix.py snapshot
--   ./venv/bin/python scripts/ops/ops_009_15_executor_role_fix.py prepare
--   ./venv/bin/python scripts/ops/ops_009_15_executor_role_fix.py fix --execute
--   ./venv/bin/python scripts/ops/ops_009_15_executor_role_fix.py verify

\echo '=== OPS-009.15 snapshot: roles ==='
SELECT role_id, code, name
FROM public.roles
WHERE code IN ('QM_HEAD', 'QM_HOSP', 'QM_AMB')
ORDER BY role_id;

\echo '=== OPS-009.15 snapshot: templates 1 and 2 ==='
SELECT
    rt.regular_task_id,
    rt.code,
    rt.executor_role_id,
    er.code AS executor_role_code
FROM public.regular_tasks rt
LEFT JOIN public.roles er ON er.role_id = rt.executor_role_id
WHERE rt.regular_task_id IN (1, 2)
ORDER BY rt.regular_task_id;

\echo '=== OPS-009.15 snapshot: tasks 10009 and 10010 ==='
SELECT
    t.task_id,
    t.regular_task_id,
    t.period_id,
    t.executor_role_id,
    er.code AS executor_role_code,
    ts.code AS status_code,
    t.due_date
FROM public.tasks t
JOIN public.task_statuses ts ON ts.status_id = t.status_id
LEFT JOIN public.roles er ON er.role_id = t.executor_role_id
WHERE t.task_id IN (10009, 10010)
ORDER BY t.task_id;

\echo '=== OPS-009.15 snapshot: user qm_hosp ==='
SELECT u.user_id, u.login, u.role_id, r.code AS role_code
FROM public.users u
JOIN public.roles r ON r.role_id = u.role_id
WHERE lower(u.login) = 'qm_hosp@corp.local';

\echo '=== OPS-009.15 snapshot: other tasks for regular_task_id=1 (excluding 10009) ==='
SELECT
    t.task_id,
    t.period_id,
    t.executor_role_id,
    er.code AS executor_role_code,
    ts.code AS status_code,
    t.due_date
FROM public.tasks t
JOIN public.task_statuses ts ON ts.status_id = t.status_id
LEFT JOIN public.roles er ON er.role_id = t.executor_role_id
WHERE t.regular_task_id = 1
  AND t.task_id <> 10009
ORDER BY t.task_id;

-- Uncomment the block below after confirming snapshot (expected: QM_HEAD=3, QM_HOSP=4).
/*
BEGIN;

UPDATE public.regular_tasks
SET executor_role_id = 4
WHERE regular_task_id = 1
  AND executor_role_id = 3;

UPDATE public.tasks
SET executor_role_id = 4
WHERE task_id = 10009
  AND executor_role_id = 3;

COMMIT;
*/
