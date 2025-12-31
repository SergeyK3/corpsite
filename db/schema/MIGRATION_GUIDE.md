# Schema Migration Guide

## Overview

This guide explains how to safely evolve the database schema over time while preserving data and maintaining audit history.

## General Principles

1. **Never delete audit_log records** - They are the historical record
2. **Use migrations for schema changes** - Don't modify original schema files
3. **Test migrations on a copy** - Always test on non-production data first
4. **Backup before migrating** - Always create a backup before running migrations
5. **Use transactions** - Wrap DDL in transactions where possible

## Migration File Naming

Create new migration files in `db/schema/migrations/` with the format:

```
migrations/
  ├── 001_add_column_example.sql
  ├── 002_create_new_table.sql
  └── 003_modify_constraint.sql
```

## Common Migration Patterns

### Adding a New Column

```sql
-- Migration: 001_add_column_example.sql
BEGIN;

-- Add new column
ALTER TABLE tasks 
ADD COLUMN estimated_hours DECIMAL(10,2);

-- Add comment
COMMENT ON COLUMN tasks.estimated_hours IS 'Estimated hours to complete the task';

-- Backfill existing data if needed
UPDATE tasks 
SET estimated_hours = 0 
WHERE estimated_hours IS NULL;

-- Make NOT NULL if desired (after backfill)
ALTER TABLE tasks 
ALTER COLUMN estimated_hours SET NOT NULL;

-- Add default for future inserts
ALTER TABLE tasks 
ALTER COLUMN estimated_hours SET DEFAULT 0;

COMMIT;
```

### Adding a New Table

```sql
-- Migration: 002_create_task_attachments.sql
BEGIN;

-- Create new table
CREATE TABLE task_attachments (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(255),
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    uploaded_by BIGINT REFERENCES users(id) ON DELETE SET NULL
);

-- Add indexes
CREATE INDEX idx_task_attachments_task_id ON task_attachments(task_id);
CREATE INDEX idx_task_attachments_uploaded_by ON task_attachments(uploaded_by);
CREATE INDEX idx_task_attachments_uploaded_at ON task_attachments(uploaded_at);

-- Add audit trigger
CREATE TRIGGER audit_task_attachments_trigger
    AFTER INSERT OR UPDATE OR DELETE ON task_attachments
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

-- Add comment
COMMENT ON TABLE task_attachments IS 'File attachments for tasks';

COMMIT;
```

### Modifying a Constraint

```sql
-- Migration: 003_modify_priority_range.sql
BEGIN;

-- Drop old constraint
ALTER TABLE tasks 
DROP CONSTRAINT IF EXISTS chk_priority;

-- Add new constraint with wider range
ALTER TABLE tasks 
ADD CONSTRAINT chk_priority CHECK (priority >= 1 AND priority <= 20);

COMMIT;
```

### Adding an Index

```sql
-- Migration: 004_add_performance_indexes.sql
BEGIN;

-- Add composite index for common query
CREATE INDEX idx_tasks_role_status 
ON tasks(assigned_to_role_id, status_id);

-- Add partial index for pending tasks
CREATE INDEX idx_tasks_pending 
ON tasks(due_date) 
WHERE status_id = (SELECT id FROM task_statuses WHERE name = 'pending');

COMMIT;
```

### Renaming a Column

```sql
-- Migration: 005_rename_column.sql
BEGIN;

-- Rename column
ALTER TABLE reports 
RENAME COLUMN content TO description;

-- Update audit records (optional - only if you need to update historical data)
-- Be very careful with this!
UPDATE audit_log 
SET changed_fields = jsonb_set(
    changed_fields,
    '{0}',
    '"description"'::jsonb
)
WHERE table_name = 'reports' 
  AND changed_fields @> '["content"]'::jsonb;

COMMIT;
```

### Adding a New Status

```sql
-- Migration: 006_add_task_status.sql
BEGIN;

-- Add new status
INSERT INTO task_statuses (name, description, display_order)
VALUES ('deferred', 'Task has been deferred to a later date', 35);

-- Adjust display order if needed
UPDATE task_statuses 
SET display_order = 40 
WHERE name = 'completed';

UPDATE task_statuses 
SET display_order = 50 
WHERE name = 'cancelled';

COMMIT;
```

## Data Migration Patterns

### Backfilling Data

```sql
-- Migration: 007_backfill_user_data.sql
BEGIN;

-- Example: Set default functional manager to administrative manager
-- where functional manager is not set
UPDATE users 
SET functional_manager_id = administrative_manager_id,
    updated_by = 1 -- System user
WHERE functional_manager_id IS NULL 
  AND administrative_manager_id IS NOT NULL;

COMMIT;
```

### Splitting Data

```sql
-- Migration: 008_split_report_content.sql
BEGIN;

-- Move content to sections
INSERT INTO report_sections (report_id, section_title, section_content, display_order)
SELECT 
    id,
    'Content',
    content,
    1
FROM reports 
WHERE content IS NOT NULL 
  AND NOT EXISTS (
      SELECT 1 FROM report_sections rs WHERE rs.report_id = reports.id
  );

-- Optionally drop the old column
-- ALTER TABLE reports DROP COLUMN content;

COMMIT;
```

## Rolling Back Migrations

Always create a rollback script alongside your migration:

```sql
-- Migration: 009_add_feature.sql
BEGIN;
-- Forward migration
ALTER TABLE tasks ADD COLUMN priority_label VARCHAR(50);
COMMIT;

-- Rollback: 009_add_feature_rollback.sql
BEGIN;
-- Reverse migration
ALTER TABLE tasks DROP COLUMN priority_label;
COMMIT;
```

## Migration Checklist

Before running a migration:

- [ ] Create a full database backup
- [ ] Test migration on a copy of production data
- [ ] Review migration in code review
- [ ] Check for table locks and long-running queries
- [ ] Plan for downtime if needed
- [ ] Create a rollback script
- [ ] Document the migration in CHANGELOG.md
- [ ] Verify audit_log still works after migration

After running a migration:

- [ ] Verify data integrity
- [ ] Check that application still works
- [ ] Monitor performance
- [ ] Update schema documentation
- [ ] Update application code if needed
- [ ] Run verify.sql to check schema

## Best Practices

### 1. Use Transactions

```sql
BEGIN;
-- migration statements
COMMIT;
-- Use ROLLBACK; if something goes wrong
```

### 2. Make Migrations Idempotent

```sql
-- Use IF NOT EXISTS
CREATE TABLE IF NOT EXISTS new_table (...);

-- Use DROP IF EXISTS
ALTER TABLE tasks DROP COLUMN IF EXISTS old_column;

-- Check before inserting
INSERT INTO roles (name, description)
SELECT 'NewRole', 'Description'
WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'NewRole');
```

### 3. Handle Existing Data

```sql
-- Add column as nullable first
ALTER TABLE tasks ADD COLUMN new_column VARCHAR(100);

-- Backfill data
UPDATE tasks SET new_column = 'default_value' WHERE new_column IS NULL;

-- Then make NOT NULL
ALTER TABLE tasks ALTER COLUMN new_column SET NOT NULL;
```

### 4. Performance Considerations

```sql
-- Create indexes CONCURRENTLY to avoid table locks
CREATE INDEX CONCURRENTLY idx_tasks_new 
ON tasks(new_column);

-- For large tables, batch updates
DO $$
DECLARE
    batch_size INT := 1000;
    offset_val INT := 0;
    rows_updated INT;
BEGIN
    LOOP
        UPDATE tasks
        SET new_column = 'value'
        WHERE id IN (
            SELECT id 
            FROM tasks 
            WHERE new_column IS NULL 
            LIMIT batch_size
        );
        
        GET DIAGNOSTICS rows_updated = ROW_COUNT;
        EXIT WHEN rows_updated = 0;
        
        -- Optional: commit in batches (outside transaction)
        -- COMMIT;
    END LOOP;
END $$;
```

## Migration Tracking

Consider creating a migrations table to track applied migrations:

```sql
CREATE TABLE schema_migrations (
    id BIGSERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_by VARCHAR(255),
    success BOOLEAN NOT NULL DEFAULT TRUE
);

-- Record migration
INSERT INTO schema_migrations (migration_name, applied_by)
VALUES ('001_add_column_example.sql', current_user);
```

## Emergency Rollback

If a migration fails in production:

1. **Stop application** - Prevent further data corruption
2. **Restore from backup** - If data was corrupted
3. **Apply rollback script** - If structure only changed
4. **Verify integrity** - Run verify.sql
5. **Restart application** - Only after verification
6. **Post-mortem** - Document what went wrong

## Testing Migrations

```bash
# 1. Create test database with production dump
pg_dump -U postgres production_db > prod_dump.sql
createdb -U postgres test_migration
psql -U postgres test_migration < prod_dump.sql

# 2. Run migration on test database
psql -U postgres test_migration -f migrations/001_migration.sql

# 3. Verify
psql -U postgres test_migration -f db/schema/verify.sql

# 4. Test application against test database

# 5. Clean up
dropdb -U postgres test_migration
```

## Version Control

- Keep migration files in version control
- Never modify applied migrations
- Include rollback scripts
- Document breaking changes
- Update schema documentation

## Resources

- PostgreSQL ALTER TABLE: https://www.postgresql.org/docs/current/sql-altertable.html
- PostgreSQL Indexes: https://www.postgresql.org/docs/current/indexes.html
- PostgreSQL Constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
