-- Verification and Testing Queries
-- Run these queries to verify the schema is working correctly

-- 1. Check all tables exist
SELECT 'Checking table existence...' AS test_section;
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- 2. Check all views exist
SELECT 'Checking views...' AS test_section;
SELECT table_name 
FROM information_schema.views 
WHERE table_schema = 'public'
ORDER BY table_name;

-- 3. Check all functions exist
SELECT 'Checking functions...' AS test_section;
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public' 
  AND routine_type = 'FUNCTION'
ORDER BY routine_name;

-- 4. Verify users with matrix management
SELECT 'Testing matrix management...' AS test_section;
SELECT * FROM v_users_with_managers
WHERE is_active = TRUE;

-- 5. Verify role-based task assignment
SELECT 'Testing role-based task assignment...' AS test_section;
SELECT * FROM v_tasks_full
ORDER BY priority, due_date;

-- 6. Test get_user_tasks function
SELECT 'Testing get_user_tasks function...' AS test_section;
SELECT * FROM get_user_tasks(
    (SELECT id FROM users WHERE username = 'rdavis')
);

-- 7. Verify reports with approval cycle
SELECT 'Testing report approval cycle...' AS test_section;
SELECT * FROM v_reports_with_status
ORDER BY period_year DESC, period_month DESC;

-- 8. Check pending approvals
SELECT 'Testing pending approvals view...' AS test_section;
SELECT * FROM v_pending_approvals;

-- 9. Test get_team_reports function (administrative)
SELECT 'Testing get_team_reports (administrative)...' AS test_section;
SELECT * FROM get_team_reports(
    (SELECT id FROM users WHERE username = 'jsmith'),
    'administrative'
);

-- 10. Test get_team_reports function (functional)
SELECT 'Testing get_team_reports (functional)...' AS test_section;
SELECT * FROM get_team_reports(
    (SELECT id FROM users WHERE username = 'mjones'),
    'functional'
);

-- 11. Verify audit logging
SELECT 'Testing audit logging...' AS test_section;
SELECT 
    table_name,
    COUNT(*) AS audit_record_count,
    COUNT(DISTINCT operation) AS operation_types
FROM audit_log
GROUP BY table_name
ORDER BY audit_record_count DESC;

-- 12. Check audit trail for a specific report
SELECT 'Testing audit trail for a specific report...' AS test_section;
SELECT * FROM get_audit_trail('reports', 
    (SELECT id FROM reports LIMIT 1)
);

-- 13. Verify constraint on report approval consistency
SELECT 'Testing report approval constraint...' AS test_section;
SELECT 
    id,
    is_approved,
    approved_by IS NOT NULL AS has_approver,
    approved_at IS NOT NULL AS has_timestamp,
    CASE 
        WHEN is_approved = TRUE AND approved_by IS NOT NULL AND approved_at IS NOT NULL THEN 'Valid'
        WHEN is_approved = FALSE AND approved_by IS NULL AND approved_at IS NULL THEN 'Valid'
        ELSE 'Invalid'
    END AS approval_status
FROM reports;

-- 14. Verify task status is execution-only (no approval fields)
SELECT 'Verifying task statuses (execution-only)...' AS test_section;
SELECT * FROM task_statuses ORDER BY display_order;

-- 15. Check indexes
SELECT 'Checking indexes...' AS test_section;
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- 16. Verify foreign key constraints
SELECT 'Checking foreign key constraints...' AS test_section;
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' 
  AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;

-- 17. Test JSONB audit data querying
SELECT 'Testing JSONB audit queries...' AS test_section;
SELECT 
    id,
    table_name,
    record_id,
    operation,
    changed_at,
    after_data->>'title' AS title_after,
    before_data->>'title' AS title_before
FROM audit_log
WHERE table_name IN ('tasks', 'reports')
  AND operation = 'UPDATE'
LIMIT 5;

-- 18. Summary statistics
SELECT 'Summary statistics...' AS test_section;
SELECT 
    'Users' AS entity,
    COUNT(*) AS total_count,
    COUNT(*) FILTER (WHERE is_active = TRUE) AS active_count
FROM users
UNION ALL
SELECT 
    'Roles' AS entity,
    COUNT(*) AS total_count,
    COUNT(*) FILTER (WHERE is_active = TRUE) AS active_count
FROM roles
UNION ALL
SELECT 
    'Tasks' AS entity,
    COUNT(*) AS total_count,
    NULL AS active_count
FROM tasks
UNION ALL
SELECT 
    'Reports' AS entity,
    COUNT(*) AS total_count,
    COUNT(*) FILTER (WHERE is_approved = TRUE) AS approved_count
FROM reports
UNION ALL
SELECT 
    'Audit Log Entries' AS entity,
    COUNT(*) AS total_count,
    NULL AS active_count
FROM audit_log;

-- Success message
SELECT 'All verification tests completed!' AS status;
