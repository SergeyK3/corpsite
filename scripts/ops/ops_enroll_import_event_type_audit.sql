-- ADR-039 Phase 3I — read-only audit: enrollment event_type constraint + partial enroll state
-- Usage (production, read-only role):
--   psql "$DATABASE_URL" -v employee_id=43 -f scripts/ops/ops_enroll_import_event_type_audit.sql
--
-- Do NOT DELETE or UPDATE without HR/ops sign-off.

\echo '=== 1. Alembic head vs DB (manual compare with repo) ==='
SELECT version_num AS alembic_version
FROM public.alembic_version
ORDER BY version_num DESC
LIMIT 1;

\echo '=== 2. employee_events event_type CHECK constraint ==='
SELECT
    conname,
    pg_get_constraintdef(oid) AS constraint_def
FROM pg_constraint
WHERE conrelid = 'public.employee_events'::regclass
  AND conname = 'chk_employee_events_event_type';

\echo '=== 3. security_audit_log event_type CHECK (same deploy) ==='
SELECT
    conname,
    pg_get_constraintdef(oid) AS constraint_def
FROM pg_constraint
WHERE conrelid = 'public.security_audit_log'::regclass
  AND conname = 'chk_sal_event_type';

\echo '=== 4. Target employee (set -v employee_id=N) ==='
SELECT
    e.employee_id,
    e.full_name,
    e.org_unit_id,
    ou.name AS org_unit_name,
    e.position_id,
    p.name AS position_name,
    e.date_from,
    e.employment_rate,
    e.is_active,
    e.created_at
FROM public.employees e
LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
LEFT JOIN public.positions p ON p.position_id = e.position_id
WHERE e.employee_id = :employee_id;

\echo '=== 5. employee_identities for target ==='
SELECT employee_id, iin, created_at
FROM public.employee_identities
WHERE employee_id = :employee_id;

\echo '=== 6. employee_events for target ==='
SELECT event_id, event_type, event_class, lifecycle_status, effective_date, created_at
FROM public.employee_events
WHERE employee_id = :employee_id
ORDER BY event_id;

\echo '=== 7. security_audit_log (enrollment) for target ==='
SELECT audit_id, event_type, actor_user_id, target_employee_id, created_at
FROM public.security_audit_log
WHERE target_employee_id = :employee_id
   OR event_type = 'EMPLOYEE_ENROLLED_FROM_IMPORT'
ORDER BY audit_id DESC
LIMIT 20;

\echo '=== 8. hr_import rows still unbound with same IIN as target employee ==='
WITH target_iin AS (
    SELECT regexp_replace(iin, '[^0-9]', '', 'g') AS iin_digits
    FROM public.employee_identities
    WHERE employee_id = :employee_id
    LIMIT 1
)
SELECT
    r.row_id,
    r.batch_id,
    r.employee_id AS row_employee_id,
    r.match_status,
    r.normalized_payload->>'full_name' AS full_name,
    regexp_replace(COALESCE(r.normalized_payload->>'iin', ''), '[^0-9]', '', 'g') AS iin
FROM public.hr_import_rows r
CROSS JOIN target_iin t
WHERE t.iin_digits <> ''
  AND regexp_replace(COALESCE(r.normalized_payload->>'iin', ''), '[^0-9]', '', 'g') = t.iin_digits
ORDER BY r.row_id;

\echo '=== 9. normalized records linkage for target IIN ==='
WITH target_iin AS (
    SELECT regexp_replace(iin, '[^0-9]', '', 'g') AS iin_digits
    FROM public.employee_identities
    WHERE employee_id = :employee_id
    LIMIT 1
)
SELECT
    nr.normalized_record_id,
    nr.row_id,
    nr.employee_id,
    nr.review_status,
    nr.record_kind
FROM public.hr_import_normalized_records nr
JOIN public.hr_import_rows r ON r.row_id = nr.row_id
CROSS JOIN target_iin t
WHERE t.iin_digits <> ''
  AND regexp_replace(COALESCE(r.normalized_payload->>'iin', ''), '[^0-9]', '', 'g') = t.iin_digits
ORDER BY nr.normalized_record_id;

\echo '=== Interpretation ==='
\echo '- If employee row EXISTS but sections 6-7 empty and 8-9 show employee_id NULL:'
\echo '  likely failed mid-transaction WITHOUT rollback (investigate) OR employee from another flow.'
\echo '- With engine.begin() in API, expect NO orphan employee after constraint error (full rollback).'
\echo '- Fix: alembic upgrade head (revision h7i8j9k0l1m2) then retry enrollment.'
