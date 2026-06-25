-- OPS-026 — Telegram ID audit for QM_AMB (амбулаторный эксперт)
-- Usage (read-only):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f docs/ops/OPS-026-telegram-id-audit.sql
-- Replace step (ONLY after reviewing SELECT output):
--   Uncomment the UPDATE block at the bottom and set :old_tg from section 1.

-- Target telegram for QM_AMB operational expert (production):
--   7685102887

-- =============================================================================
-- 1. Current QM_AMB user bind (authoritative for bot delivery)
-- =============================================================================
SELECT
    'qm_amb_user' AS section,
    u.user_id,
    u.login,
    u.full_name,
    u.telegram_id,
    u.telegram_username,
    r.code AS role_code,
    r.name AS role_name,
    u.is_active
FROM public.users u
JOIN public.roles r ON r.role_id = u.role_id
WHERE lower(u.login) = 'qm_amb@corp.local'
   OR r.code = 'QM_AMB'
ORDER BY u.user_id;

-- =============================================================================
-- 2. contacts / key_contacts planes for ambulatory expert person
-- =============================================================================
SELECT
    'contacts_qm_amb_name' AS section,
    c.contact_id,
    c.person_id,
    c.full_name,
    c.phone,
    c.telegram_username,
    c.telegram_numeric_id
FROM public.contacts c
WHERE COALESCE(c.is_deleted, false) = false
  AND (
    lower(c.full_name) LIKE '%акил%'
    OR lower(c.full_name) LIKE '%амбул%'
  )
ORDER BY c.contact_id;

SELECT
    'key_contacts_qm_amb' AS section,
    kc.*
FROM public.key_contacts kc
WHERE kc.role_code = 'QM_AMB'
   OR lower(kc.full_name) LIKE '%акил%'
ORDER BY kc.role_code;

-- =============================================================================
-- 3. Duplicate telegram_id across users (C5)
-- =============================================================================
SELECT
    'duplicate_telegram_id' AS section,
    trim(u.telegram_id::text) AS telegram_id,
    array_agg(u.user_id ORDER BY u.user_id) AS user_ids,
    array_agg(u.login ORDER BY u.user_id) AS logins,
    array_agg(r.code ORDER BY u.user_id) AS role_codes
FROM public.users u
LEFT JOIN public.roles r ON r.role_id = u.role_id
WHERE u.telegram_id IS NOT NULL
  AND trim(u.telegram_id::text) <> ''
GROUP BY trim(u.telegram_id::text)
HAVING COUNT(*) > 1;

-- =============================================================================
-- 4. Who owns telegram 7685102887 and legacy dev placeholder 885342581
-- =============================================================================
SELECT
    'telegram_id_owners' AS section,
    u.user_id,
    u.login,
    u.full_name,
    u.telegram_id,
    r.code AS role_code
FROM public.users u
LEFT JOIN public.roles r ON r.role_id = u.role_id
WHERE trim(u.telegram_id::text) IN ('7685102887', '885342581')
ORDER BY u.telegram_id, u.user_id;

SELECT
    'contacts_telegram_id_owners' AS section,
    c.contact_id,
    c.full_name,
    c.telegram_numeric_id,
    c.person_id
FROM public.contacts c
WHERE c.telegram_numeric_id IN (7685102887, 885342581)
   OR trim(c.telegram_numeric_id::text) IN ('7685102887', '885342581');

-- =============================================================================
-- 5. Recent telegram task deliveries for QM_AMB user
-- =============================================================================
SELECT
    'recent_deliveries_qm_amb' AS section,
    ted.audit_id,
    ted.user_id,
    ted.channel,
    ted.status,
    ted.created_at,
    u.login,
    u.telegram_id
FROM public.task_event_deliveries ted
JOIN public.users u ON u.user_id = ted.user_id
JOIN public.roles r ON r.role_id = u.role_id
WHERE ted.channel = 'telegram'
  AND r.code = 'QM_AMB'
ORDER BY ted.created_at DESC NULLS LAST
LIMIT 20;

-- =============================================================================
-- 6. Point UPDATE (run manually after confirming :old_tg from section 1/4)
-- =============================================================================
-- BEGIN;
-- UPDATE public.users
-- SET telegram_id = '7685102887',
--     updated_at = NOW()
-- WHERE user_id = (
--     SELECT u.user_id
--     FROM public.users u
--     JOIN public.roles r ON r.role_id = u.role_id
--     WHERE lower(u.login) = 'qm_amb@corp.local'
--     LIMIT 1
-- )
--   AND trim(COALESCE(telegram_id::text, '')) = '<OLD_TG_FROM_SELECT>';
-- -- Optional: sync contacts plane if numeric id stored separately
-- UPDATE public.contacts
-- SET telegram_numeric_id = 7685102887,
--     updated_at = NOW()
-- WHERE contact_id IN (
--     SELECT c.contact_id
--     FROM public.contacts c
--     JOIN public.key_contacts kc ON kc.person_id = c.person_id
--     WHERE kc.role_code = 'QM_AMB'
-- )
--   AND COALESCE(telegram_numeric_id::text, '') = '<OLD_TG_FROM_SELECT>';
-- COMMIT;
