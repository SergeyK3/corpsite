-- scripts/e2e-seed.sql
-- E2E seed: functional supervision
-- Цель: чтобы Executor (devUserId=34) имел allowed_actions=report,
-- а Supervisor (devUserId=5) мог approve/reject по задачам executor-а.

BEGIN;

-- Идемпотентность без ON CONFLICT: чистим конкретную связку и создаем заново.
-- Это работает на любой схеме, даже если нет UNIQUE constraint.
DELETE FROM user_supervisors
WHERE supervisor_user_id = 5
  AND user_id = 34
  AND scope = 'functional';

INSERT INTO user_supervisors (supervisor_user_id, user_id, scope)
VALUES (5, 34, 'functional');

COMMIT;
