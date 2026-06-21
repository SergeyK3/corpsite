-- OPS-007 — Telegram Bot Operational Audit (read-only)
-- Usage: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f docs/ops/OPS-007-telegram-integrity-audit.sql
-- Guarantee: SELECT-only. No mutations.

-- =============================================================================
-- Phase B — Database inventory (row counts)
-- =============================================================================
SELECT 'table_inventory' AS section, 'users' AS table_name, COUNT(*) AS row_count FROM public.users
UNION ALL
SELECT 'table_inventory', 'users_with_telegram_id', COUNT(*) FROM public.users WHERE telegram_id IS NOT NULL AND trim(telegram_id::text) <> ''
UNION ALL
SELECT 'table_inventory', 'tg_bindings_legacy', COUNT(*) FROM public.tg_bindings
UNION ALL
SELECT 'table_inventory', 'contacts_with_telegram', COUNT(*) FROM public.contacts WHERE telegram_numeric_id IS NOT NULL OR (telegram_username IS NOT NULL AND trim(telegram_username) <> '')
UNION ALL
SELECT 'table_inventory', 'task_event_deliveries_telegram', COUNT(*) FROM public.task_event_deliveries WHERE channel = 'telegram';

-- =============================================================================
-- Phase C — Identity integrity (counts only)
-- =============================================================================

-- C1: Telegram linked but no User (orphan telegram in users.telegram_id without user row — impossible by PK; check invalid user refs via tg_bindings)
SELECT 'C1_tg_bindings_orphan_user' AS check_name, COUNT(*) AS cnt
FROM public.tg_bindings tb
LEFT JOIN public.users u ON u.user_id = tb.user_id
WHERE u.user_id IS NULL;

-- C2: User linked (telegram_id set) but no Employee
SELECT 'C2_telegram_without_employee' AS check_name, COUNT(*) AS cnt
FROM public.users u
WHERE u.is_active
  AND u.telegram_id IS NOT NULL
  AND trim(u.telegram_id::text) <> ''
  AND u.employee_id IS NULL;

-- C3: Employee with active linked user but no Telegram
SELECT 'C3_employee_user_no_telegram' AS check_name, COUNT(*) AS cnt
FROM public.employees e
JOIN public.users u ON u.employee_id = e.employee_id AND u.is_active
WHERE e.operational_status IN ('draft', 'active', 'suspended')
  AND (u.telegram_id IS NULL OR trim(u.telegram_id::text) = '');

-- C4: Multiple Telegram accounts per User (should be 0 — one column)
SELECT 'C4_multiple_tg_per_user' AS check_name, 0 AS cnt; -- structural N/A

-- C5: Multiple Users per Telegram account (duplicate telegram_id)
SELECT 'C5_duplicate_telegram_id' AS check_name, COUNT(*) AS cnt
FROM (
    SELECT trim(telegram_id::text) AS tg
    FROM public.users
    WHERE telegram_id IS NOT NULL AND trim(telegram_id::text) <> ''
    GROUP BY trim(telegram_id::text)
    HAVING COUNT(*) > 1
) d;

-- C6: Service accounts incorrectly linked to Telegram
SELECT 'C6_service_account_with_telegram' AS check_name, COUNT(*) AS cnt
FROM public.users u
WHERE u.telegram_id IS NOT NULL
  AND trim(u.telegram_id::text) <> ''
  AND (
    lower(COALESCE(u.login, '')) ~ '(^svc_|^service_|^bot_|^system_|^cron_)'
    OR lower(COALESCE(u.full_name, '')) ~ '(системн|service account|\mbot\b|\mcron\b)'
  );

-- C7: Inactive users still bound to Telegram
SELECT 'C7_inactive_user_with_telegram' AS check_name, COUNT(*) AS cnt
FROM public.users u
WHERE NOT COALESCE(u.is_active, TRUE)
  AND u.telegram_id IS NOT NULL
  AND trim(u.telegram_id::text) <> '';

-- C8: Legacy tg_bindings vs users.telegram_id drift
SELECT 'C8_tg_bindings_drift_from_users' AS check_name, COUNT(*) AS cnt
FROM public.tg_bindings tb
JOIN public.users u ON u.user_id = tb.user_id
WHERE u.telegram_id IS NULL OR trim(u.telegram_id::text) = '' OR trim(u.telegram_id::text) <> tb.tg_user_id::text;

-- C9: tg_bindings duplicate tg_user_id vs users (cross-table)
SELECT 'C9_tg_bindings_user_mismatch' AS check_name, COUNT(*) AS cnt
FROM public.tg_bindings tb
JOIN public.users u ON u.user_id = tb.user_id
WHERE trim(COALESCE(u.telegram_id::text, '')) <> '' AND trim(u.telegram_id::text) <> tb.tg_user_id::text;

-- Summary rollup
SELECT 'identity_integrity_summary' AS section,
       check_name,
       cnt
FROM (
    SELECT 'C2_telegram_without_employee' AS check_name, COUNT(*)::bigint AS cnt
    FROM public.users u
    WHERE u.is_active AND u.telegram_id IS NOT NULL AND trim(u.telegram_id::text) <> '' AND u.employee_id IS NULL
    UNION ALL
    SELECT 'C5_duplicate_telegram_id', COUNT(*) FROM (
        SELECT trim(telegram_id::text) FROM public.users
        WHERE telegram_id IS NOT NULL AND trim(telegram_id::text) <> ''
        GROUP BY 1 HAVING COUNT(*) > 1
    ) x
    UNION ALL
    SELECT 'C6_service_account_with_telegram', COUNT(*) FROM public.users u
    WHERE u.telegram_id IS NOT NULL AND trim(u.telegram_id::text) <> ''
      AND (lower(COALESCE(u.login, '')) ~ '(^svc_|^service_|^bot_|^system_|^cron_)'
           OR lower(COALESCE(u.full_name, '')) ~ '(системн|service account|\mbot\b|\mcron\b)')
) s
ORDER BY check_name;
