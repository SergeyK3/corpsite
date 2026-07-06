-- ADR-042 E1 — idempotent QM pilot personnel visibility bootstrap (local).
-- Grants org sidebar / personnel directory visibility to all users in QM org unit.
--
-- Safe to re-run (skips when equivalent active row exists).
-- Does NOT revoke or modify existing assignments.
-- Not intended for production VPS apply.
--
-- Prerequisites:
--   - Alembic migration b0c1d2e3f4a5 (personnel_visibility_assignments)
--   - QM org unit present (default local expanded tree: unit_id = 72)
--   - Sysadmin user for created_by_user_id (login = admin)
--
-- QM pilot bootstrap order (after users seeded on unit 72):
--   ... prior pilot scripts ...
--   ./venv/bin/python scripts/pilot/qm_personnel_visibility_bootstrap.py --yes
--
-- SQL-only apply (local Docker):
--   docker exec -i corpsite-pg psql -U postgres -d corpsite \
--     < scripts/pilot/qm_personnel_visibility_bootstrap.sql
--
-- Verify:
--   ./venv/bin/python -m pytest tests/test_qm_personnel_visibility_bootstrap.py -q

BEGIN;

INSERT INTO public.personnel_visibility_assignments (
    target_type,
    target_user_id,
    target_position_id,
    target_department_id,
    scope_type,
    scope_department_id,
    scope_department_group_id,
    can_view_personnel,
    can_view_tasks,
    is_active,
    created_by_user_id
)
SELECT
    'DEPARTMENT',
    NULL,
    NULL,
    72,
    'DEPARTMENT',
    72,
    NULL,
    TRUE,
    TRUE,
    TRUE,
    u.user_id
FROM public.users u
WHERE lower(u.login) = 'admin'
  AND u.is_active = TRUE
  AND EXISTS (
      SELECT 1 FROM public.org_units ou WHERE ou.unit_id = 72
  )
  AND NOT EXISTS (
      SELECT 1
      FROM public.personnel_visibility_assignments pva
      WHERE pva.is_active = TRUE
        AND pva.target_type = 'DEPARTMENT'
        AND pva.target_department_id = 72
        AND pva.scope_type = 'DEPARTMENT'
        AND pva.scope_department_id = 72
        AND pva.can_view_personnel = TRUE
        AND pva.can_view_tasks = TRUE
  )
LIMIT 1;

COMMIT;
