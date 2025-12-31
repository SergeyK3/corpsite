-- Sample Data for Testing
-- This file provides example data to demonstrate the schema functionality

-- Note: Run this AFTER installing the schema

-- Insert sample users (bootstrapping - first user created by system)
-- The first user will be the system admin
INSERT INTO users (username, email, full_name, created_by, updated_by) VALUES
    ('admin', 'admin@hospital.com', 'System Administrator', NULL, NULL)
ON CONFLICT (username) DO NOTHING;

-- Now insert other users with proper created_by references
INSERT INTO users (username, email, full_name, administrative_manager_id, functional_manager_id, created_by, updated_by) VALUES
    ('jsmith', 'john.smith@hospital.com', 'John Smith', 1, NULL, 1, 1),
    ('mjones', 'mary.jones@hospital.com', 'Mary Jones', 1, NULL, 1, 1),
    ('rdavis', 'robert.davis@hospital.com', 'Robert Davis', 2, 3, 1, 1),
    ('swilson', 'susan.wilson@hospital.com', 'Susan Wilson', 2, 3, 1, 1)
ON CONFLICT (username) DO NOTHING;

-- Insert sample roles
INSERT INTO roles (name, description, created_by, updated_by) VALUES
    ('Doctor', 'Medical doctor responsible for patient care', 1, 1),
    ('Nurse', 'Registered nurse providing patient care', 1, 1),
    ('Administrator', 'Administrative staff member', 1, 1),
    ('Department Head', 'Head of a medical department', 1, 1)
ON CONFLICT (name) DO NOTHING;

-- Assign roles to users
INSERT INTO user_roles (user_id, role_id, assigned_by) 
SELECT u.id, r.id, 1
FROM users u, roles r
WHERE (u.username = 'admin' AND r.name = 'Administrator')
   OR (u.username = 'jsmith' AND r.name = 'Department Head')
   OR (u.username = 'mjones' AND r.name = 'Department Head')
   OR (u.username = 'rdavis' AND r.name = 'Doctor')
   OR (u.username = 'swilson' AND r.name = 'Nurse')
ON CONFLICT (user_id, role_id) DO NOTHING;

-- Get status IDs for tasks
DO $$
DECLARE
    v_pending_status_id BIGINT;
    v_in_progress_status_id BIGINT;
    v_completed_status_id BIGINT;
    v_doctor_role_id BIGINT;
    v_nurse_role_id BIGINT;
    v_admin_role_id BIGINT;
    v_rdavis_id BIGINT;
    v_swilson_id BIGINT;
BEGIN
    -- Get status IDs
    SELECT id INTO v_pending_status_id FROM task_statuses WHERE name = 'pending';
    SELECT id INTO v_in_progress_status_id FROM task_statuses WHERE name = 'in_progress';
    SELECT id INTO v_completed_status_id FROM task_statuses WHERE name = 'completed';
    
    -- Get role IDs
    SELECT id INTO v_doctor_role_id FROM roles WHERE name = 'Doctor';
    SELECT id INTO v_nurse_role_id FROM roles WHERE name = 'Nurse';
    SELECT id INTO v_admin_role_id FROM roles WHERE name = 'Administrator';
    
    -- Get user IDs
    SELECT id INTO v_rdavis_id FROM users WHERE username = 'rdavis';
    SELECT id INTO v_swilson_id FROM users WHERE username = 'swilson';
    
    -- Insert sample tasks
    INSERT INTO tasks (title, description, assigned_to_role_id, assigned_to_user_id, status_id, priority, due_date, created_by, updated_by)
    VALUES
        ('Complete patient rounds', 'Review all patients in ward A', v_doctor_role_id, v_rdavis_id, v_in_progress_status_id, 1, CURRENT_TIMESTAMP + INTERVAL '2 days', 1, 1),
        ('Update medical records', 'Ensure all patient records are current', v_doctor_role_id, NULL, v_pending_status_id, 3, CURRENT_TIMESTAMP + INTERVAL '5 days', 1, 1),
        ('Medication administration', 'Administer scheduled medications', v_nurse_role_id, v_swilson_id, v_completed_status_id, 1, CURRENT_TIMESTAMP - INTERVAL '1 day', 1, 1),
        ('Inventory check', 'Check medical supplies inventory', v_nurse_role_id, NULL, v_pending_status_id, 5, CURRENT_TIMESTAMP + INTERVAL '7 days', 1, 1),
        ('Monthly budget review', 'Review department budget for current month', v_admin_role_id, NULL, v_pending_status_id, 4, CURRENT_TIMESTAMP + INTERVAL '10 days', 1, 1);
END $$;

-- Insert task comments
INSERT INTO task_comments (task_id, comment_text, created_by)
SELECT t.id, 'Started rounds at 8 AM', u.id
FROM tasks t, users u
WHERE t.title = 'Complete patient rounds' AND u.username = 'rdavis';

INSERT INTO task_comments (task_id, comment_text, created_by)
SELECT t.id, 'All medications administered successfully', u.id
FROM tasks t, users u
WHERE t.title = 'Medication administration' AND u.username = 'swilson';

-- Get report type ID
DO $$
DECLARE
    v_monthly_report_type_id BIGINT;
    v_rdavis_id BIGINT;
    v_swilson_id BIGINT;
    v_jsmith_id BIGINT;
BEGIN
    SELECT id INTO v_monthly_report_type_id FROM report_types WHERE name = 'monthly';
    SELECT id INTO v_rdavis_id FROM users WHERE username = 'rdavis';
    SELECT id INTO v_swilson_id FROM users WHERE username = 'swilson';
    SELECT id INTO v_jsmith_id FROM users WHERE username = 'jsmith';
    
    -- Insert sample reports
    INSERT INTO reports (report_type_id, user_id, period_year, period_month, title, content, submitted_at, created_by, updated_by)
    VALUES
        (v_monthly_report_type_id, v_rdavis_id, 2025, 12, 'December 2025 Monthly Report', 
         'This month I completed patient rounds daily and updated all medical records. Focus was on improving patient care quality.',
         CURRENT_TIMESTAMP - INTERVAL '2 days', v_rdavis_id, v_rdavis_id),
        (v_monthly_report_type_id, v_swilson_id, 2025, 11, 'November 2025 Monthly Report',
         'All medication schedules were maintained. Participated in training for new medical equipment.',
         CURRENT_TIMESTAMP - INTERVAL '30 days', v_swilson_id, v_swilson_id);
    
    -- Approve one report
    UPDATE reports 
    SET is_approved = TRUE, 
        approved_by = v_jsmith_id, 
        approved_at = CURRENT_TIMESTAMP - INTERVAL '25 days',
        updated_by = v_jsmith_id
    WHERE user_id = v_swilson_id AND period_month = 11;
END $$;

-- Add report sections
INSERT INTO report_sections (report_id, section_title, section_content, display_order)
SELECT r.id, 'Key Accomplishments', 'Completed all assigned patient rounds on time. Improved patient satisfaction scores.', 1
FROM reports r
JOIN users u ON r.user_id = u.id
WHERE u.username = 'rdavis' AND r.period_month = 12;

INSERT INTO report_sections (report_id, section_title, section_content, display_order)
SELECT r.id, 'Challenges', 'High patient load during flu season required additional coordination.', 2
FROM reports r
JOIN users u ON r.user_id = u.id
WHERE u.username = 'rdavis' AND r.period_month = 12;

-- Link tasks to reports
INSERT INTO report_tasks (report_id, task_id, notes)
SELECT r.id, t.id, 'Successfully completed on time'
FROM reports r
JOIN users u ON r.user_id = u.id
JOIN tasks t ON t.title = 'Complete patient rounds'
WHERE u.username = 'rdavis' AND r.period_month = 12;

INSERT INTO report_tasks (report_id, task_id, notes)
SELECT r.id, t.id, 'Completed without issues'
FROM reports r
JOIN users u ON r.user_id = u.id
JOIN tasks t ON t.title = 'Medication administration'
WHERE u.username = 'swilson' AND r.period_month = 11;

-- Display summary
SELECT 'Sample data inserted successfully!' AS status;
SELECT COUNT(*) AS user_count FROM users;
SELECT COUNT(*) AS role_count FROM roles;
SELECT COUNT(*) AS task_count FROM tasks;
SELECT COUNT(*) AS report_count FROM reports;
SELECT COUNT(*) AS audit_log_count FROM audit_log;
