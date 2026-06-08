-- Minimal directory prereq for QM pilot seed (departments + positions).
-- Safe to re-run (idempotent upserts). Does NOT touch roles, users, or ADMIN.
--
-- Purpose:
--   db/init/020_seed_roles_users_employees.sql references
--     department_id = 44, position_id = 64
--   without creating those rows. This script fills the gap.
--
-- QM pilot bootstrap order (do NOT mix regular_tasks import here):
--   1. scripts/pilot/org_structure_bootstrap.sql
--   2. scripts/pilot/directory_prereq_bootstrap.sql   <-- this file
--   3. db/init/020_seed_roles_users_employees.sql
--   4. scripts/pilot/qm_pilot_bootstrap.sql
--   5. ./venv/bin/python scripts/reset_pilot_password.py --yes
--   6. (separate stage) import/create regular_tasks, then catch-up Preview
--
-- Example (local Docker Postgres, not for unattended VPS apply):
--   docker exec -i corpsite-pg psql -U postgres -d corpsite < scripts/pilot/directory_prereq_bootstrap.sql

BEGIN;

INSERT INTO public.departments (department_id, name)
OVERRIDING SYSTEM VALUE
VALUES (
    44,
    'Отдел внутреннего контроля и оценки качества медицинской помощи'
)
ON CONFLICT (department_id) DO UPDATE
SET name = EXCLUDED.name;

INSERT INTO public.positions (position_id, name)
OVERRIDING SYSTEM VALUE
VALUES (
    64,
    'Специалист'
)
ON CONFLICT (position_id) DO UPDATE
SET name = EXCLUDED.name;

SELECT setval(
    pg_get_serial_sequence('public.departments', 'department_id'),
    GREATEST((SELECT COALESCE(MAX(department_id), 1) FROM public.departments), 1)
);

SELECT setval(
    pg_get_serial_sequence('public.positions', 'position_id'),
    GREATEST((SELECT COALESCE(MAX(position_id), 1) FROM public.positions), 1)
);

COMMIT;

-- Quick verify
SELECT department_id, name
FROM public.departments
WHERE department_id = 44;

SELECT position_id, name
FROM public.positions
WHERE position_id = 64;
