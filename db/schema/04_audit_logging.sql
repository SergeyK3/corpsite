-- Audit Logging Schema
-- Full audit logging: who/what/when/before/after

-- Audit log table for tracking all changes
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    record_id BIGINT NOT NULL,
    operation VARCHAR(50) NOT NULL, -- INSERT, UPDATE, DELETE
    changed_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    before_data JSONB, -- Previous state (NULL for INSERT)
    after_data JSONB,  -- New state (NULL for DELETE)
    changed_fields JSONB, -- Array of changed field names for UPDATE
    ip_address INET,
    user_agent TEXT,
    CONSTRAINT chk_operation CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE'))
);

-- Indexes for audit_log
CREATE INDEX idx_audit_log_table_name ON audit_log(table_name);
CREATE INDEX idx_audit_log_record_id ON audit_log(record_id);
CREATE INDEX idx_audit_log_changed_by ON audit_log(changed_by);
CREATE INDEX idx_audit_log_changed_at ON audit_log(changed_at);
CREATE INDEX idx_audit_log_operation ON audit_log(operation);
CREATE INDEX idx_audit_log_table_record ON audit_log(table_name, record_id);

-- GIN indexes for JSONB columns to enable efficient querying
CREATE INDEX idx_audit_log_before_data ON audit_log USING GIN (before_data);
CREATE INDEX idx_audit_log_after_data ON audit_log USING GIN (after_data);
CREATE INDEX idx_audit_log_changed_fields ON audit_log USING GIN (changed_fields);

-- Audit trigger function
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
DECLARE
    changed_fields_array JSONB;
    current_user_id BIGINT;
BEGIN
    -- Get current user ID from session variable (set by application)
    current_user_id := NULLIF(current_setting('app.current_user_id', TRUE), '')::BIGINT;
    
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO audit_log (
            table_name,
            record_id,
            operation,
            changed_by,
            changed_at,
            before_data,
            after_data,
            changed_fields
        ) VALUES (
            TG_TABLE_NAME,
            NEW.id,
            'INSERT',
            current_user_id,
            CURRENT_TIMESTAMP,
            NULL,
            to_jsonb(NEW),
            NULL
        );
        RETURN NEW;
        
    ELSIF (TG_OP = 'UPDATE') THEN
        -- Build array of changed field names
        SELECT jsonb_agg(DISTINCT key)
        INTO changed_fields_array
        FROM (
            SELECT key
            FROM jsonb_each(to_jsonb(OLD))
            WHERE to_jsonb(OLD) -> key IS DISTINCT FROM to_jsonb(NEW) -> key
        ) AS changed;
        
        INSERT INTO audit_log (
            table_name,
            record_id,
            operation,
            changed_by,
            changed_at,
            before_data,
            after_data,
            changed_fields
        ) VALUES (
            TG_TABLE_NAME,
            NEW.id,
            'UPDATE',
            current_user_id,
            CURRENT_TIMESTAMP,
            to_jsonb(OLD),
            to_jsonb(NEW),
            changed_fields_array
        );
        RETURN NEW;
        
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO audit_log (
            table_name,
            record_id,
            operation,
            changed_by,
            changed_at,
            before_data,
            after_data,
            changed_fields
        ) VALUES (
            TG_TABLE_NAME,
            OLD.id,
            'DELETE',
            current_user_id,
            CURRENT_TIMESTAMP,
            to_jsonb(OLD),
            NULL,
            NULL
        );
        RETURN OLD;
    END IF;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Apply audit triggers to all main tables
CREATE TRIGGER audit_users_trigger
    AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_roles_trigger
    AFTER INSERT OR UPDATE OR DELETE ON roles
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_user_roles_trigger
    AFTER INSERT OR UPDATE OR DELETE ON user_roles
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_task_statuses_trigger
    AFTER INSERT OR UPDATE OR DELETE ON task_statuses
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_tasks_trigger
    AFTER INSERT OR UPDATE OR DELETE ON tasks
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_task_comments_trigger
    AFTER INSERT OR UPDATE OR DELETE ON task_comments
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_report_types_trigger
    AFTER INSERT OR UPDATE OR DELETE ON report_types
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_reports_trigger
    AFTER INSERT OR UPDATE OR DELETE ON reports
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_report_sections_trigger
    AFTER INSERT OR UPDATE OR DELETE ON report_sections
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_report_tasks_trigger
    AFTER INSERT OR UPDATE OR DELETE ON report_tasks
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();
