-- FILE: docs/sql/db_refresh_schema_snapshots.sql
-- Purpose: refresh snapshots inside DB

CREATE TABLE IF NOT EXISTS public.db_schema_snapshot (
    snapshot_at       timestamptz NOT NULL DEFAULT now(),
    table_name        text NOT NULL,
    column_name       text NOT NULL,
    data_type         text NOT NULL,
    udt_name          text,
    is_nullable       boolean,
    column_default    text,
    ordinal_position  integer
);

CREATE TABLE IF NOT EXISTS public.db_enum_snapshot (
    snapshot_at timestamptz NOT NULL DEFAULT now(),
    enum_name   text NOT NULL,
    enum_value  text NOT NULL,
    enum_order  integer NOT NULL
);

TRUNCATE public.db_schema_snapshot;
INSERT INTO public.db_schema_snapshot (
    table_name, column_name, data_type, udt_name, is_nullable, column_default, ordinal_position
)
SELECT
    c.table_name,
    c.column_name,
    c.data_type,
    c.udt_name,
    (c.is_nullable = 'YES') AS is_nullable,
    c.column_default,
    c.ordinal_position
FROM information_schema.columns c
WHERE c.table_schema = 'public'
ORDER BY c.table_name, c.ordinal_position;

TRUNCATE public.db_enum_snapshot;
INSERT INTO public.db_enum_snapshot (enum_name, enum_value, enum_order)
SELECT
    t.typname,
    e.enumlabel,
    e.enumsortorder::int
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
ORDER BY t.typname, e.enumsortorder;