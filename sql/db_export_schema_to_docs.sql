-- FILE: docs/sql/db_export_schema_to_docs.sql
-- Purpose: export schema snapshots to docs/db (client-side)

\copy (
  SELECT table_name, column_name, data_type, udt_name, is_nullable, column_default, ordinal_position
  FROM public.db_schema_snapshot
  ORDER BY table_name, ordinal_position
) TO 'docs/db/schema_columns.csv' CSV HEADER;

\copy (
  SELECT enum_name, enum_value, enum_order
  FROM public.db_enum_snapshot
  ORDER BY enum_name, enum_order
) TO 'docs/db/schema_enums.csv' CSV HEADER;