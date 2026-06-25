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
-- 2. contacts + optional operational bridge planes
--    public.contacts is migrated (Alembic f8c2a91b4e10).
--    public.key_contacts is optional — repo has key_contacts.csv but production
--    VPS schema may not include the table; expert delivery uses users.telegram_id.
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
    'operational_bridge_schema' AS section,
    to_regclass('public.key_contacts')::text AS key_contacts,
    to_regclass('public.v_key_contacts_auto')::text AS v_key_contacts_auto,
    to_regclass('public.contacts_working')::text AS contacts_working;

DROP TABLE IF EXISTS _ops026_optional_audit;
CREATE TEMP TABLE _ops026_optional_audit (
    section text NOT NULL,
    row_num int NOT NULL,
    data jsonb NOT NULL,
    PRIMARY KEY (section, row_num)
);

DO $ops026$
BEGIN
    IF to_regclass('public.key_contacts') IS NOT NULL THEN
        EXECUTE $sql$
            INSERT INTO _ops026_optional_audit (section, row_num, data)
            SELECT
                'key_contacts_qm_amb',
                row_number() OVER (ORDER BY kc.role_code, kc.person_id NULLS LAST),
                row_to_json(kc)::jsonb
            FROM public.key_contacts kc
            WHERE kc.role_code = 'QM_AMB'
               OR lower(COALESCE(kc.full_name, '')) LIKE '%акил%'
        $sql$;
    ELSE
        INSERT INTO _ops026_optional_audit (section, row_num, data) VALUES (
            'key_contacts_qm_amb',
            1,
            jsonb_build_object(
                'status', 'table_absent',
                'message', 'public.key_contacts is not in this database schema',
                'authoritative_bind', 'public.users.telegram_id (section 1)',
                'static_reference', 'repo key_contacts.csv (not loaded to production DB)'
            )
        );
    END IF;

    IF to_regclass('public.contacts_working') IS NOT NULL THEN
        EXECUTE $sql$
            INSERT INTO _ops026_optional_audit (section, row_num, data)
            SELECT
                'contacts_working_qm_amb',
                row_number() OVER (ORDER BY cw.contact_id),
                row_to_json(cw)::jsonb || jsonb_build_object(
                    'contact_full_name', c.full_name,
                    'contact_telegram_numeric_id', c.telegram_numeric_id
                )
            FROM public.contacts_working cw
            JOIN public.contacts c ON c.contact_id = cw.contact_id
            WHERE COALESCE(c.is_deleted, false) = false
              AND (
                lower(c.full_name) LIKE '%акил%'
                OR lower(c.full_name) LIKE '%амбул%'
              )
        $sql$;
    END IF;
END
$ops026$;

SELECT
    section,
    row_num,
    data
FROM _ops026_optional_audit
ORDER BY section, row_num;

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
-- -- Optional: sync contacts plane if numeric id stored separately (section 2a match)
-- UPDATE public.contacts
-- SET telegram_numeric_id = 7685102887,
--     updated_at = NOW()
-- WHERE contact_id IN (
--     SELECT c.contact_id
--     FROM public.contacts c
--     WHERE COALESCE(c.is_deleted, false) = false
--       AND lower(c.full_name) LIKE '%акил%'
-- )
--   AND COALESCE(telegram_numeric_id::text, '') = '<OLD_TG_FROM_SELECT>';
-- -- If public.key_contacts exists (to_regclass check), prefer its person_id bridge
-- -- instead of name match; production VPS typically has no key_contacts table.
-- COMMIT;
