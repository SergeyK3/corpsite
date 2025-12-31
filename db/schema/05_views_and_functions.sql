-- Helper Views and Functions

-- View for active users with their managers
CREATE OR REPLACE VIEW v_users_with_managers AS
SELECT 
    u.id,
    u.username,
    u.email,
    u.full_name,
    u.is_active,
    am.full_name AS administrative_manager_name,
    fm.full_name AS functional_manager_name,
    u.created_at,
    u.updated_at
FROM users u
LEFT JOIN users am ON u.administrative_manager_id = am.id
LEFT JOIN users fm ON u.functional_manager_id = fm.id;

-- View for tasks with full details
CREATE OR REPLACE VIEW v_tasks_full AS
SELECT 
    t.id,
    t.title,
    t.description,
    r.name AS assigned_role,
    u.full_name AS assigned_user,
    ts.name AS status,
    t.priority,
    t.due_date,
    t.completed_at,
    creator.full_name AS created_by_name,
    t.created_at,
    t.updated_at
FROM tasks t
JOIN roles r ON t.assigned_to_role_id = r.id
LEFT JOIN users u ON t.assigned_to_user_id = u.id
JOIN task_statuses ts ON t.status_id = ts.id
LEFT JOIN users creator ON t.created_by = creator.id;

-- View for reports with approval status
CREATE OR REPLACE VIEW v_reports_with_status AS
SELECT 
    r.id,
    u.full_name AS reporter_name,
    rt.name AS report_type,
    r.period_year,
    r.period_month,
    r.title,
    r.is_approved,
    approver.full_name AS approved_by_name,
    r.approved_at,
    r.submitted_at,
    r.created_at,
    r.updated_at
FROM reports r
JOIN users u ON r.user_id = u.id
JOIN report_types rt ON r.report_type_id = rt.id
LEFT JOIN users approver ON r.approved_by = approver.id;

-- View for pending approvals (reports submitted but not yet approved)
CREATE OR REPLACE VIEW v_pending_approvals AS
SELECT 
    r.id,
    r.user_id,
    u.full_name AS reporter_name,
    u.administrative_manager_id,
    u.functional_manager_id,
    r.period_year,
    r.period_month,
    r.title,
    r.submitted_at,
    EXTRACT(DAY FROM CURRENT_TIMESTAMP - r.submitted_at) AS days_pending
FROM reports r
JOIN users u ON r.user_id = u.id
WHERE r.is_approved = FALSE 
  AND r.submitted_at IS NOT NULL
  AND r.approved_by IS NULL;

-- Function to get user's tasks by role
CREATE OR REPLACE FUNCTION get_user_tasks(p_user_id BIGINT)
RETURNS TABLE (
    task_id BIGINT,
    title VARCHAR(500),
    status VARCHAR(100),
    priority INT,
    due_date TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.id,
        t.title,
        ts.name,
        t.priority,
        t.due_date
    FROM tasks t
    JOIN task_statuses ts ON t.status_id = ts.id
    JOIN user_roles ur ON t.assigned_to_role_id = ur.role_id
    WHERE ur.user_id = p_user_id
      AND (t.assigned_to_user_id IS NULL OR t.assigned_to_user_id = p_user_id)
    ORDER BY t.priority ASC, t.due_date ASC NULLS LAST;
END;
$$ LANGUAGE plpgsql;

-- Function to get team reports (for managers)
CREATE OR REPLACE FUNCTION get_team_reports(
    p_manager_id BIGINT,
    p_management_type VARCHAR(50) DEFAULT 'administrative'
)
RETURNS TABLE (
    report_id BIGINT,
    reporter_name VARCHAR(500),
    period_year INT,
    period_month INT,
    is_approved BOOLEAN,
    submitted_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.id,
        u.full_name,
        r.period_year,
        r.period_month,
        r.is_approved,
        r.submitted_at
    FROM reports r
    JOIN users u ON r.user_id = u.id
    WHERE (
        (p_management_type = 'administrative' AND u.administrative_manager_id = p_manager_id) OR
        (p_management_type = 'functional' AND u.functional_manager_id = p_manager_id)
    )
    ORDER BY r.period_year DESC, r.period_month DESC, r.submitted_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get audit trail for a specific record
CREATE OR REPLACE FUNCTION get_audit_trail(
    p_table_name VARCHAR(255),
    p_record_id BIGINT
)
RETURNS TABLE (
    id BIGINT,
    operation VARCHAR(50),
    changed_by_name VARCHAR(500),
    changed_at TIMESTAMP WITH TIME ZONE,
    changed_fields JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        al.id,
        al.operation,
        u.full_name,
        al.changed_at,
        al.changed_fields
    FROM audit_log al
    LEFT JOIN users u ON al.changed_by = u.id
    WHERE al.table_name = p_table_name
      AND al.record_id = p_record_id
    ORDER BY al.changed_at DESC;
END;
$$ LANGUAGE plpgsql;
