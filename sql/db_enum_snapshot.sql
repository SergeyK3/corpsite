-- FILE: docs/sql/db_enum_snapshot.sql
-- Purpose: Refresh ENUM snapshot (only enums)
-- This script recreates and fills db_enum_snapshot table.

BEGIN;

CREATE TABLE IF NOT EXISTS public.db_enum_snapshot (
    snapshot_at timestamptz NOT NULL DEFAULT now(),
    enum_name   text NOT NULL,
    enum_value  text NOT NULL,
    enum_order  integer NOT NULL
);

TRUNCATE public.db_enum_snapshot;

INSERT INTO public.db_enum_snapshot (enum_name, enum_value, enum_order)
SELECT
    t.typname,
    e.enumlabel,
    e.enumsortorder::int
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
ORDER BY t.typname, e.enumsortorder;

COMMIT;...existing code...