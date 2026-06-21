-- ADR-044 Phase R2.1 — User Linkage validation (read-only)
-- Usage (local):
--   psql "postgresql://postgres:postgres@127.0.0.1:5432/corpsite" -f docs/adr/ADR-044-phase-r2-validation.sql
-- Usage (VPS, read-only session recommended):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f docs/adr/ADR-044-phase-r2-validation.sql
--
-- Guarantee: every statement is SELECT-only. No INSERT/UPDATE/DELETE/DDL.
-- Empty detail result sets for violation checks = OK.

-- =============================================================================
-- R2.1-S1 — Active users linked / unlinked (summary counts)
-- =============================================================================
SELECT
    'r2_active_users_linkage_summary' AS check_name,
    COUNT(*) FILTER (WHERE is_active AND employee_id IS NOT NULL) AS active_users_linked,
    COUNT(*) FILTER (WHERE is_active AND employee_id IS NULL) AS active_users_unlinked,
    COUNT(*) FILTER (WHERE is_active) AS active_users_total,
    COUNT(*) FILTER (WHERE employee_id IS NOT NULL) AS all_users_linked,
    COUNT(*) FILTER (WHERE employee_id IS NULL) AS all_users_unlinked,
    COUNT(*) AS all_users_total
FROM public.users;

-- Detail: active users already linked
SELECT
    'r2_active_users_linked_detail' AS check_name,
    u.user_id,
    u.login,
    u.full_name,
    u.employee_id,
    e.full_name AS employee_full_name,
    e.operational_status
FROM public.users u
JOIN public.employees e ON e.employee_id = u.employee_id
WHERE u.is_active
  AND u.employee_id IS NOT NULL
ORDER BY u.user_id;

-- =============================================================================
-- R2.1-S2 — Active employees with / without linked user (summary + detail)
-- Active employee cohort: draft, active, suspended (ADR-044 R2 discovery)
-- =============================================================================
SELECT
    'r2_active_employees_user_coverage_summary' AS check_name,
    COUNT(*) FILTER (WHERE u.user_id IS NOT NULL) AS active_employees_with_linked_user,
    COUNT(*) FILTER (WHERE u.user_id IS NULL) AS active_employees_without_linked_user,
    COUNT(*) AS active_employees_total
FROM public.employees e
LEFT JOIN public.users u ON u.employee_id = e.employee_id AND u.is_active
WHERE e.operational_status IN ('draft', 'active', 'suspended');

SELECT
    'r2_active_employees_with_linked_user_detail' AS check_name,
    e.employee_id,
    e.full_name AS employee_full_name,
    e.operational_status,
    u.user_id,
    u.login,
    u.full_name AS user_full_name
FROM public.employees e
JOIN public.users u ON u.employee_id = e.employee_id AND u.is_active
WHERE e.operational_status IN ('draft', 'active', 'suspended')
ORDER BY e.employee_id, u.user_id;

-- =============================================================================
-- R2.1-S3 — Login pattern candidates (review-only)
-- Rule: login ~ '^.+_[0-9]+$' AND numeric suffix = employees.employee_id
-- =============================================================================
SELECT
    'r2_login_pattern_candidates_summary' AS check_name,
    COUNT(*) AS login_pattern_candidate_count
FROM public.users u
WHERE u.employee_id IS NULL
  AND u.is_active
  AND u.login ~ '^.+_[0-9]+$'
  AND EXISTS (
      SELECT 1
      FROM public.employees e
      WHERE e.employee_id = (regexp_match(u.login, '^(.+)_([0-9]+)$'))[2]::bigint
        AND e.operational_status IN ('draft', 'active', 'suspended')
  );

SELECT
    'r2_login_pattern_candidates_detail' AS check_name,
    u.user_id,
    u.login,
    u.full_name AS user_full_name,
    (regexp_match(u.login, '^(.+)_([0-9]+)$'))[2]::bigint AS parsed_employee_id,
    e.full_name AS employee_full_name,
    e.operational_status
FROM public.users u
JOIN public.employees e
  ON e.employee_id = (regexp_match(u.login, '^(.+)_([0-9]+)$'))[2]::bigint
WHERE u.employee_id IS NULL
  AND u.is_active
  AND u.login ~ '^.+_[0-9]+$'
  AND e.operational_status IN ('draft', 'active', 'suspended')
ORDER BY u.user_id;

-- =============================================================================
-- R2.1-S4 — Normalized FIO: unique 1:1 matches (review-only) + collision groups
-- Normalize: lower(trim), collapse whitespace
-- Each query is self-contained (psql executes statement-by-statement).
-- =============================================================================
SELECT
    'r2_fio_unique_1_1_summary' AS check_name,
    COUNT(*) AS unique_fio_match_group_count
FROM (
    WITH user_norm AS (
        SELECT
            u.user_id,
            lower(regexp_replace(trim(u.full_name), '\s+', ' ', 'g')) AS normalized_name
        FROM public.users u
        WHERE u.employee_id IS NULL
          AND u.is_active
          AND length(trim(COALESCE(u.full_name, ''))) > 0
    ),
    emp_norm AS (
        SELECT
            e.employee_id,
            lower(regexp_replace(trim(e.full_name), '\s+', ' ', 'g')) AS normalized_name
        FROM public.employees e
        WHERE e.operational_status IN ('draft', 'active', 'suspended')
          AND length(trim(COALESCE(e.full_name, ''))) > 0
    ),
    fio_join AS (
        SELECT
            un.normalized_name,
            un.user_id,
            en.employee_id
        FROM user_norm un
        JOIN emp_norm en ON en.normalized_name = un.normalized_name
    )
    SELECT normalized_name
    FROM fio_join
    GROUP BY normalized_name
    HAVING COUNT(DISTINCT user_id) = 1
       AND COUNT(DISTINCT employee_id) = 1
) unique_groups;

SELECT
    'r2_fio_unique_1_1_detail' AS check_name,
    fj.normalized_name,
    fj.user_id,
    fj.login,
    fj.user_full_name,
    fj.employee_id AS proposed_employee_id,
    fj.employee_full_name,
    fj.operational_status
FROM (
    WITH user_norm AS (
        SELECT
            u.user_id,
            u.login,
            u.full_name,
            lower(regexp_replace(trim(u.full_name), '\s+', ' ', 'g')) AS normalized_name
        FROM public.users u
        WHERE u.employee_id IS NULL
          AND u.is_active
          AND length(trim(COALESCE(u.full_name, ''))) > 0
    ),
    emp_norm AS (
        SELECT
            e.employee_id,
            e.full_name,
            e.operational_status,
            lower(regexp_replace(trim(e.full_name), '\s+', ' ', 'g')) AS normalized_name
        FROM public.employees e
        WHERE e.operational_status IN ('draft', 'active', 'suspended')
          AND length(trim(COALESCE(e.full_name, ''))) > 0
    ),
    fio_join AS (
        SELECT
            un.normalized_name,
            un.user_id,
            un.login,
            un.full_name AS user_full_name,
            en.employee_id,
            en.full_name AS employee_full_name,
            en.operational_status
        FROM user_norm un
        JOIN emp_norm en ON en.normalized_name = un.normalized_name
    ),
    fio_stats AS (
        SELECT
            normalized_name,
            COUNT(DISTINCT user_id) AS user_count,
            COUNT(DISTINCT employee_id) AS employee_count
        FROM fio_join
        GROUP BY normalized_name
    )
    SELECT fj.*
    FROM fio_join fj
    JOIN fio_stats fs ON fs.normalized_name = fj.normalized_name
    WHERE fs.user_count = 1
      AND fs.employee_count = 1
) fj
ORDER BY fj.normalized_name, fj.user_id;

SELECT
    'r2_fio_collision_groups_summary' AS check_name,
    COUNT(*) AS fio_collision_group_count
FROM (
    WITH user_norm AS (
        SELECT
            u.user_id,
            lower(regexp_replace(trim(u.full_name), '\s+', ' ', 'g')) AS normalized_name
        FROM public.users u
        WHERE u.employee_id IS NULL
          AND u.is_active
          AND length(trim(COALESCE(u.full_name, ''))) > 0
    ),
    emp_norm AS (
        SELECT
            e.employee_id,
            lower(regexp_replace(trim(e.full_name), '\s+', ' ', 'g')) AS normalized_name
        FROM public.employees e
        WHERE e.operational_status IN ('draft', 'active', 'suspended')
          AND length(trim(COALESCE(e.full_name, ''))) > 0
    ),
    fio_join AS (
        SELECT
            un.normalized_name,
            un.user_id,
            en.employee_id
        FROM user_norm un
        JOIN emp_norm en ON en.normalized_name = un.normalized_name
    )
    SELECT normalized_name
    FROM fio_join
    GROUP BY normalized_name
    HAVING COUNT(DISTINCT user_id) > 1
        OR COUNT(DISTINCT employee_id) > 1
) collision_groups;

SELECT
    'r2_fio_collision_groups_detail' AS check_name,
    agg.normalized_name,
    agg.user_count,
    agg.employee_count,
    agg.user_ids,
    agg.employee_ids
FROM (
    WITH user_norm AS (
        SELECT
            u.user_id,
            lower(regexp_replace(trim(u.full_name), '\s+', ' ', 'g')) AS normalized_name
        FROM public.users u
        WHERE u.employee_id IS NULL
          AND u.is_active
          AND length(trim(COALESCE(u.full_name, ''))) > 0
    ),
    emp_norm AS (
        SELECT
            e.employee_id,
            lower(regexp_replace(trim(e.full_name), '\s+', ' ', 'g')) AS normalized_name
        FROM public.employees e
        WHERE e.operational_status IN ('draft', 'active', 'suspended')
          AND length(trim(COALESCE(e.full_name, ''))) > 0
    ),
    fio_join AS (
        SELECT
            un.normalized_name,
            un.user_id,
            en.employee_id
        FROM user_norm un
        JOIN emp_norm en ON en.normalized_name = un.normalized_name
    ),
    fio_stats AS (
        SELECT
            normalized_name,
            COUNT(DISTINCT user_id) AS user_count,
            COUNT(DISTINCT employee_id) AS employee_count
        FROM fio_join
        GROUP BY normalized_name
        HAVING COUNT(DISTINCT user_id) > 1
            OR COUNT(DISTINCT employee_id) > 1
    )
    SELECT
        fs.normalized_name,
        fs.user_count,
        fs.employee_count,
        array_agg(DISTINCT fj.user_id ORDER BY fj.user_id) AS user_ids,
        array_agg(DISTINCT fj.employee_id ORDER BY fj.employee_id) AS employee_ids
    FROM fio_stats fs
    JOIN fio_join fj ON fj.normalized_name = fs.normalized_name
    GROUP BY fs.normalized_name, fs.user_count, fs.employee_count
) agg
ORDER BY agg.user_count DESC, agg.employee_count DESC, agg.normalized_name
LIMIT 100;

-- =============================================================================
-- R2.1-S5 — Telegram bind without employee link
-- =============================================================================
SELECT
    'r2_telegram_without_employee_summary' AS check_name,
    COUNT(*) AS telegram_without_employee_count
FROM public.users u
WHERE u.is_active
  AND u.telegram_id IS NOT NULL
  AND u.employee_id IS NULL;

SELECT
    'r2_telegram_without_employee_detail' AS check_name,
    u.user_id,
    u.login,
    u.full_name,
    u.telegram_id,
    u.telegram_username,
    u.telegram_bound_at
FROM public.users u
WHERE u.is_active
  AND u.telegram_id IS NOT NULL
  AND u.employee_id IS NULL
ORDER BY u.user_id;

-- =============================================================================
-- R2.1-S6 — Service / admin / system-like accounts (EXCLUDED from linkage)
-- Heuristics (R2.1 policy — tune before execute):
--   - role_id = 2 (SYSTEM_ADMIN)
--   - login/google_login prefix tokens: admin, system, service, cron, bot, api, internal, sysadmin
--   - login suffix _admin or prefix admin_
--   - display name contains service/bot/cron markers (RU/EN)
-- =============================================================================
SELECT
    'r2_excluded_service_accounts_summary' AS check_name,
    COUNT(*) AS excluded_service_account_count
FROM public.users u
WHERE u.is_active
  AND u.employee_id IS NULL
  AND (
      u.role_id = 2
      OR lower(COALESCE(u.login, '')) ~ '^(admin|system|service|cron|bot|api|internal|sysadmin)'
      OR lower(COALESCE(u.login, '')) LIKE 'admin\_%' ESCAPE '\'
      OR lower(COALESCE(u.login, '')) LIKE '%\_admin' ESCAPE '\'
      OR lower(COALESCE(u.google_login, '')) ~ '^(admin|system|service|cron|bot|api|internal|sysadmin)'
      OR lower(COALESCE(u.google_login, '')) LIKE 'admin\_%' ESCAPE '\'
      OR lower(COALESCE(u.full_name, '')) ~ '(системн|service account|\mbot\b|\mcron\b)'
  );

SELECT
    'r2_excluded_service_accounts_detail' AS check_name,
    u.user_id,
    u.login,
    u.google_login,
    u.full_name,
    u.role_id,
    r.code AS role_code,
    r.name AS role_name,
    CASE
        WHEN u.role_id = 2 THEN 'SYSTEM_ADMIN_ROLE'
        WHEN lower(COALESCE(u.login, '')) ~ '^(admin|system|service|cron|bot|api|internal|sysadmin)' THEN 'LOGIN_PREFIX'
        WHEN lower(COALESCE(u.login, '')) LIKE 'admin\_%' ESCAPE '\' THEN 'LOGIN_ADMIN_PREFIX'
        WHEN lower(COALESCE(u.login, '')) LIKE '%\_admin' ESCAPE '\' THEN 'LOGIN_ADMIN_SUFFIX'
        WHEN lower(COALESCE(u.google_login, '')) ~ '^(admin|system|service|cron|bot|api|internal|sysadmin)' THEN 'GOOGLE_LOGIN_PREFIX'
        WHEN lower(COALESCE(u.google_login, '')) LIKE 'admin\_%' ESCAPE '\' THEN 'GOOGLE_LOGIN_ADMIN_PREFIX'
        WHEN lower(COALESCE(u.full_name, '')) ~ '(системн|service account|\mbot\b|\mcron\b)' THEN 'DISPLAY_NAME_MARKER'
        ELSE 'OTHER'
    END AS exclusion_reason
FROM public.users u
LEFT JOIN public.roles r ON r.role_id = u.role_id
WHERE u.is_active
  AND u.employee_id IS NULL
  AND (
      u.role_id = 2
      OR lower(COALESCE(u.login, '')) ~ '^(admin|system|service|cron|bot|api|internal|sysadmin)'
      OR lower(COALESCE(u.login, '')) LIKE 'admin\_%' ESCAPE '\'
      OR lower(COALESCE(u.login, '')) LIKE '%\_admin' ESCAPE '\'
      OR lower(COALESCE(u.google_login, '')) ~ '^(admin|system|service|cron|bot|api|internal|sysadmin)'
      OR lower(COALESCE(u.google_login, '')) LIKE 'admin\_%' ESCAPE '\'
      OR lower(COALESCE(u.full_name, '')) ~ '(системн|service account|\mbot\b|\mcron\b)'
  )
ORDER BY u.user_id;

-- =============================================================================
-- R2.1-S7 — Login suffix points to missing employee_id (impossible / parse noise)
-- Pattern matches but employees.employee_id does not exist
-- =============================================================================
SELECT
    'r2_login_suffix_missing_employee_summary' AS check_name,
    COUNT(*) AS login_suffix_missing_employee_count
FROM public.users u
WHERE u.employee_id IS NULL
  AND u.is_active
  AND u.login ~ '^.+_[0-9]+$'
  AND NOT EXISTS (
      SELECT 1
      FROM public.employees e
      WHERE e.employee_id = (regexp_match(u.login, '^(.+)_([0-9]+)$'))[2]::bigint
  );

SELECT
    'r2_login_suffix_missing_employee_detail' AS check_name,
    u.user_id,
    u.login,
    u.full_name,
    (regexp_match(u.login, '^(.+)_([0-9]+)$'))[2]::bigint AS parsed_employee_id
FROM public.users u
WHERE u.employee_id IS NULL
  AND u.is_active
  AND u.login ~ '^.+_[0-9]+$'
  AND NOT EXISTS (
      SELECT 1
      FROM public.employees e
      WHERE e.employee_id = (regexp_match(u.login, '^(.+)_([0-9]+)$'))[2]::bigint
  )
ORDER BY u.user_id;

-- =============================================================================
-- R2.1-S8 — Employees linked to more than one active user (V3b precursor)
-- Should be 0 when uq_users_employee_id partial unique index is enforced
-- =============================================================================
SELECT
    'r2_employees_multiple_active_users_summary' AS check_name,
    COUNT(*) AS employees_with_multiple_active_users
FROM (
    SELECT u.employee_id
    FROM public.users u
    WHERE u.is_active
      AND u.employee_id IS NOT NULL
    GROUP BY u.employee_id
    HAVING COUNT(*) > 1
) dup;

SELECT
    'r2_employees_multiple_active_users_detail' AS check_name,
    u.employee_id,
    COUNT(*) AS active_user_count,
    array_agg(u.user_id ORDER BY u.user_id) AS user_ids,
    array_agg(u.login ORDER BY u.user_id) AS logins
FROM public.users u
WHERE u.is_active
  AND u.employee_id IS NOT NULL
GROUP BY u.employee_id
HAVING COUNT(*) > 1
ORDER BY u.employee_id;

-- =============================================================================
-- R2.1-S9 — users.employee_id pointing to missing or inactive employees (V3a)
-- =============================================================================
SELECT
    'r2_orphan_users_employee_id_summary' AS check_name,
    COUNT(*) AS orphan_users_employee_id_count
FROM public.users u
LEFT JOIN public.employees e ON e.employee_id = u.employee_id
WHERE u.employee_id IS NOT NULL
  AND e.employee_id IS NULL;

SELECT
    'r2_orphan_users_employee_id_detail' AS check_name,
    u.user_id,
    u.login,
    u.full_name,
    u.employee_id,
    u.is_active
FROM public.users u
LEFT JOIN public.employees e ON e.employee_id = u.employee_id
WHERE u.employee_id IS NOT NULL
  AND e.employee_id IS NULL
ORDER BY u.user_id;

SELECT
    'r2_users_employee_inactive_target_summary' AS check_name,
    COUNT(*) AS users_pointing_to_inactive_employee_count
FROM public.users u
JOIN public.employees e ON e.employee_id = u.employee_id
WHERE u.employee_id IS NOT NULL
  AND e.operational_status NOT IN ('draft', 'active', 'suspended');

SELECT
    'r2_users_employee_inactive_target_detail' AS check_name,
    u.user_id,
    u.login,
    u.full_name,
    u.employee_id,
    u.is_active AS user_is_active,
    e.full_name AS employee_full_name,
    e.operational_status
FROM public.users u
JOIN public.employees e ON e.employee_id = u.employee_id
WHERE u.employee_id IS NOT NULL
  AND e.operational_status NOT IN ('draft', 'active', 'suspended')
ORDER BY u.user_id;

-- =============================================================================
-- R2.1-S10 — Validation gate rollup (empty violating rows = pass)
-- =============================================================================
SELECT
    'r2_validation_gate_rollup' AS check_name,
    (SELECT COUNT(*) FROM public.users u
     LEFT JOIN public.employees e ON e.employee_id = u.employee_id
     WHERE u.employee_id IS NOT NULL AND e.employee_id IS NULL) AS v3a_orphan_users_employee_id,
    (SELECT COUNT(*) FROM (
         SELECT u.employee_id
         FROM public.users u
         WHERE u.is_active AND u.employee_id IS NOT NULL
         GROUP BY u.employee_id
         HAVING COUNT(*) > 1
     ) x) AS v3b_duplicate_active_user_per_employee,
    (SELECT COUNT(*) FROM public.users u
     JOIN public.employees e ON e.employee_id = u.employee_id
     WHERE u.employee_id IS NOT NULL
       AND e.operational_status NOT IN ('draft', 'active', 'suspended')) AS inactive_employee_target_count;
