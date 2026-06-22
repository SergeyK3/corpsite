-- OPS-009.18c — unlock primary admin account (guarded, read-only by default)
--
-- Prefer Python helper (USER_UNLOCKED audit + single-row guard):
--   ./venv/bin/python scripts/ops/ops_009_18c_admin_unlock.py snapshot admin
--   ./venv/bin/python scripts/ops/ops_009_18c_admin_unlock.py unlock admin --execute
--   ./venv/bin/python scripts/ops/ops_009_18c_admin_unlock.py verify admin
--
-- SQL fallback (manual): uncomment UPDATE only after snapshot shows exactly one locked row.

\echo '=== OPS-009.18c snapshot: locked users ==='
SELECT
    u.user_id,
    u.login,
    u.role_id,
    r.code AS role_code,
    u.is_active,
    u.failed_login_count,
    u.locked_at,
    u.locked_until,
    u.locked_reason,
    u.token_version,
    u.must_change_password,
    u.last_failed_login_at,
    u.last_login_at
FROM public.users u
LEFT JOIN public.roles r ON r.role_id = u.role_id
WHERE u.locked_at IS NOT NULL
ORDER BY u.user_id;

\echo '=== OPS-009.18c snapshot: admin candidates ==='
SELECT
    u.user_id,
    u.login,
    u.role_id,
    r.code AS role_code,
    u.is_active,
    u.unit_id,
    u.failed_login_count,
    u.locked_at,
    u.locked_until,
    u.locked_reason,
    u.token_version,
    u.must_change_password,
    u.last_login_at
FROM public.users u
LEFT JOIN public.roles r ON r.role_id = u.role_id
WHERE u.role_id = 2
   OR lower(r.code) IN ('admin', 'system_admin')
   OR lower(u.login) IN ('admin', 'administrator', 'sysadmin')
ORDER BY u.user_id;

\echo '=== OPS-009.18c login match count for admin ==='
SELECT
    COUNT(*) AS login_match_count,
    COUNT(*) FILTER (WHERE locked_at IS NOT NULL) AS locked_match_count
FROM public.users
WHERE lower(login) = lower('admin');

\echo '=== OPS-009.18c recent lock events for login admin ==='
SELECT
    e.audit_id,
    e.event_type,
    e.happened_at,
    e.failure_reason,
    e.metadata
FROM public.security_audit_log e
JOIN public.users u ON u.user_id = e.target_user_id
WHERE lower(u.login) = 'admin'
  AND e.event_type IN ('USER_LOCKED', 'USER_UNLOCKED', 'LOGIN_FAILED')
ORDER BY e.audit_id DESC
LIMIT 15;

-- Uncomment only when login_match_count=1 AND locked_match_count=1:
/*
BEGIN;

UPDATE public.users
SET
    locked_at = NULL,
    locked_until = NULL,
    locked_reason = NULL,
    failed_login_count = 0,
    token_version = COALESCE(token_version, 1) + 1
WHERE lower(login) = lower('admin')
  AND locked_at IS NOT NULL;

-- Expect exactly 1 row updated; ROLLBACK if not.
COMMIT;
*/

\echo '=== OPS-009.18c verify row for login admin ==='
SELECT
    u.user_id,
    u.login,
    u.role_id,
    r.code AS role_code,
    u.is_active,
    u.unit_id,
    u.failed_login_count,
    u.locked_at,
    u.locked_until,
    u.locked_reason,
    u.token_version,
    u.must_change_password
FROM public.users u
LEFT JOIN public.roles r ON r.role_id = u.role_id
WHERE lower(u.login) = lower('admin');
