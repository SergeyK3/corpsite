# Quick Reference Guide

## Common Operations

### Setup Current User for Audit Logging

Before performing any operations, set the current user ID for audit tracking:

```sql
SET app.current_user_id = 1; -- Replace 1 with actual user ID
```

## User Management

### Create a New User

```sql
SET app.current_user_id = 1; -- Set who is creating the user

INSERT INTO users (username, email, full_name, administrative_manager_id, functional_manager_id, created_by, updated_by)
VALUES ('jdoe', 'john.doe@hospital.com', 'John Doe', 2, 3, 1, 1);
```

### Assign Role to User

```sql
SET app.current_user_id = 1;

INSERT INTO user_roles (user_id, role_id, assigned_by)
VALUES (
    (SELECT id FROM users WHERE username = 'jdoe'),
    (SELECT id FROM roles WHERE name = 'Doctor'),
    1
);
```

### Update User's Manager

```sql
SET app.current_user_id = 1;

UPDATE users
SET administrative_manager_id = (SELECT id FROM users WHERE username = 'new_manager'),
    updated_by = 1
WHERE username = 'jdoe';
```

## Task Management

### Create a Task Assigned to a Role

```sql
SET app.current_user_id = 1;

INSERT INTO tasks (
    title, 
    description, 
    assigned_to_role_id, 
    status_id, 
    priority, 
    due_date,
    created_by,
    updated_by
)
VALUES (
    'Complete patient assessment',
    'Assess all new patients in the emergency department',
    (SELECT id FROM roles WHERE name = 'Doctor'),
    (SELECT id FROM task_statuses WHERE name = 'pending'),
    2,
    CURRENT_TIMESTAMP + INTERVAL '3 days',
    1,
    1
);
```

### Assign Task to Specific User

```sql
SET app.current_user_id = 1;

UPDATE tasks
SET assigned_to_user_id = (SELECT id FROM users WHERE username = 'jdoe'),
    updated_by = 1
WHERE id = 123;
```

### Update Task Status

```sql
SET app.current_user_id = 456; -- The user working on the task

UPDATE tasks
SET status_id = (SELECT id FROM task_statuses WHERE name = 'in_progress'),
    updated_by = 456
WHERE id = 123;
```

### Complete a Task

```sql
SET app.current_user_id = 456;

UPDATE tasks
SET status_id = (SELECT id FROM task_statuses WHERE name = 'completed'),
    completed_at = CURRENT_TIMESTAMP,
    updated_by = 456
WHERE id = 123;
```

### Add Comment to Task

```sql
SET app.current_user_id = 456;

INSERT INTO task_comments (task_id, comment_text, created_by)
VALUES (123, 'Patient assessment completed successfully', 456);
```

### Get User's Tasks

```sql
-- Get all tasks for a user based on their roles
SELECT * FROM get_user_tasks(456);

-- Or use the view for detailed information
SELECT * FROM v_tasks_full
WHERE assigned_user = 'John Doe'
   OR (assigned_role IN (
       SELECT r.name 
       FROM user_roles ur 
       JOIN roles r ON ur.role_id = r.id 
       WHERE ur.user_id = 456
   ) AND assigned_user IS NULL)
ORDER BY priority, due_date;
```

## Report Management

### Create a Monthly Report

```sql
SET app.current_user_id = 456;

INSERT INTO reports (
    report_type_id,
    user_id,
    period_year,
    period_month,
    title,
    content,
    created_by,
    updated_by
)
VALUES (
    (SELECT id FROM report_types WHERE name = 'monthly'),
    456,
    2025,
    12,
    'December 2025 Report',
    'Summary of activities and accomplishments for December 2025',
    456,
    456
);
```

### Add Section to Report

```sql
SET app.current_user_id = 456;

INSERT INTO report_sections (report_id, section_title, section_content, display_order)
VALUES (
    789,
    'Key Accomplishments',
    'Completed 50 patient assessments with 98% satisfaction rate',
    1
);
```

### Link Task to Report

```sql
SET app.current_user_id = 456;

INSERT INTO report_tasks (report_id, task_id, notes)
VALUES (789, 123, 'Completed ahead of schedule');
```

### Submit Report for Approval

```sql
SET app.current_user_id = 456;

UPDATE reports
SET submitted_at = CURRENT_TIMESTAMP,
    updated_by = 456
WHERE id = 789;
```

### Approve a Report

```sql
SET app.current_user_id = 2; -- Manager's user ID

UPDATE reports
SET is_approved = TRUE,
    approved_by = 2,
    approved_at = CURRENT_TIMESTAMP,
    updated_by = 2
WHERE id = 789;
```

### Reject a Report

```sql
SET app.current_user_id = 2; -- Manager's user ID

UPDATE reports
SET rejection_reason = 'Please provide more detail on patient outcomes',
    submitted_at = NULL, -- Allow resubmission
    updated_by = 2
WHERE id = 789;
```

### Get Pending Reports for Manager

```sql
-- For administrative reports
SELECT * FROM get_team_reports(2, 'administrative')
WHERE is_approved = FALSE AND submitted_at IS NOT NULL;

-- For functional reports
SELECT * FROM get_team_reports(3, 'functional')
WHERE is_approved = FALSE AND submitted_at IS NOT NULL;

-- Or use the view
SELECT * FROM v_pending_approvals
WHERE administrative_manager_id = 2 OR functional_manager_id = 3;
```

## Audit Trail

### View Audit Trail for a Specific Record

```sql
-- For a task
SELECT * FROM get_audit_trail('tasks', 123);

-- For a report
SELECT * FROM get_audit_trail('reports', 789);

-- For a user
SELECT * FROM get_audit_trail('users', 456);
```

### Query Audit Log for Specific Changes

```sql
-- Find all changes by a specific user
SELECT * FROM audit_log
WHERE changed_by = 456
ORDER BY changed_at DESC;

-- Find all changes to a specific table
SELECT * FROM audit_log
WHERE table_name = 'tasks'
ORDER BY changed_at DESC;

-- Find changes within a date range
SELECT * FROM audit_log
WHERE changed_at BETWEEN '2025-12-01' AND '2025-12-31'
ORDER BY changed_at DESC;

-- Find specific field changes using JSONB
SELECT 
    id,
    table_name,
    record_id,
    operation,
    changed_at,
    before_data->>'status_id' AS old_status,
    after_data->>'status_id' AS new_status
FROM audit_log
WHERE table_name = 'tasks'
  AND operation = 'UPDATE'
  AND changed_fields ? 'status_id'; -- Field name in changed_fields array
```

## Reporting and Analytics

### Tasks by Status

```sql
SELECT 
    ts.name AS status,
    COUNT(*) AS task_count,
    COUNT(*) FILTER (WHERE t.due_date < CURRENT_TIMESTAMP) AS overdue_count
FROM tasks t
JOIN task_statuses ts ON t.status_id = ts.id
GROUP BY ts.name, ts.display_order
ORDER BY ts.display_order;
```

### Tasks by Role

```sql
SELECT 
    r.name AS role,
    COUNT(*) AS total_tasks,
    COUNT(*) FILTER (WHERE t.assigned_to_user_id IS NOT NULL) AS assigned_tasks,
    COUNT(*) FILTER (WHERE t.assigned_to_user_id IS NULL) AS unassigned_tasks
FROM tasks t
JOIN roles r ON t.assigned_to_role_id = r.id
GROUP BY r.name
ORDER BY total_tasks DESC;
```

### Report Approval Rate

```sql
SELECT 
    period_year,
    period_month,
    COUNT(*) AS total_reports,
    COUNT(*) FILTER (WHERE is_approved = TRUE) AS approved_count,
    COUNT(*) FILTER (WHERE submitted_at IS NOT NULL AND is_approved = FALSE) AS pending_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_approved = TRUE) / NULLIF(COUNT(*), 0), 2) AS approval_rate
FROM reports
GROUP BY period_year, period_month
ORDER BY period_year DESC, period_month DESC;
```

### User Activity Summary

```sql
SELECT 
    u.full_name,
    COUNT(DISTINCT t.id) AS tasks_assigned,
    COUNT(DISTINCT r.id) AS reports_submitted,
    COUNT(DISTINCT al.id) AS total_actions
FROM users u
LEFT JOIN tasks t ON t.assigned_to_user_id = u.id
LEFT JOIN reports r ON r.user_id = u.id
LEFT JOIN audit_log al ON al.changed_by = u.id
WHERE u.is_active = TRUE
GROUP BY u.id, u.full_name
ORDER BY total_actions DESC;
```

## Maintenance

### Cleanup Old Audit Logs (Optional)

```sql
-- Delete audit logs older than 2 years (be careful with this!)
DELETE FROM audit_log
WHERE changed_at < CURRENT_TIMESTAMP - INTERVAL '2 years';
```

### Deactivate User

```sql
SET app.current_user_id = 1;

UPDATE users
SET is_active = FALSE,
    updated_by = 1
WHERE username = 'jdoe';
```

### Archive Completed Tasks

```sql
-- You could create an archive table and move old completed tasks
-- This is an example structure, not implemented in the schema
CREATE TABLE IF NOT EXISTS tasks_archive (LIKE tasks INCLUDING ALL);

INSERT INTO tasks_archive
SELECT * FROM tasks
WHERE status_id = (SELECT id FROM task_statuses WHERE name = 'completed')
  AND completed_at < CURRENT_TIMESTAMP - INTERVAL '1 year';

DELETE FROM tasks
WHERE status_id = (SELECT id FROM task_statuses WHERE name = 'completed')
  AND completed_at < CURRENT_TIMESTAMP - INTERVAL '1 year';
```
