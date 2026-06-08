-- Ensure PostgreSQL enum task_event_type exists (required for POST /tasks/{id}/report).
-- Safe to re-run (idempotent). Does NOT delete data.
--
-- Symptom when missing:
--   psycopg2.errors.UndefinedObject: type "task_event_type" does not exist
--   at write_task_audit() → CAST(... AS task_event_type)
--
-- Root cause on restored VPS: alembic revision 9d9d8a6c2a11 was not applied
-- (migration file lacked .py extension and was outside the active chain).
--
-- Prefer long-term fix: alembic upgrade head (revision a7c4e1f903de).
-- Use this script for immediate hotfix before deploy.
--
-- Example:
--   docker exec -i corpsite-pg psql -U postgres -d corpsite < scripts/pilot/task_event_type_bootstrap.sql

BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_event_type') THEN
    CREATE TYPE public.task_event_type AS ENUM (
      'REPORT_SUBMITTED',
      'APPROVED',
      'REJECTED',
      'ARCHIVED'
    );
  END IF;
END $$;

COMMIT;

-- Verify
SELECT typname, typtype
FROM pg_type
WHERE typname = 'task_event_type';
