-- ADR-044 Phase R1a — post-migration / post-execute validation queries
-- Usage: psql $DATABASE_URL -f docs/adr/ADR-044-phase-r1a-validation.sql
-- Each section returns violating rows; empty result = OK.

-- =============================================================================
-- M1 — persons.iin coverage (active/inactive)
-- =============================================================================
SELECT
    'persons_iin_coverage' AS check_name,
    COUNT(*) FILTER (WHERE iin IS NOT NULL) AS with_iin,
    COUNT(*) AS total,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE iin IS NOT NULL) / NULLIF(COUNT(*), 0),
        2
    ) AS coverage_pct
FROM public.persons
WHERE person_status IN ('active', 'inactive');

-- =============================================================================
-- M3 — employee_identities coverage for linked employees with canonical IIN
-- =============================================================================
SELECT
    'ei_coverage_gap' AS check_name,
    p.person_id,
    e.employee_id,
    c.iin AS canonical_iin
FROM public.persons p
JOIN public.employees e ON e.person_id = p.person_id
JOIN public.hr_canonical_snapshot_entries c
  ON c.employee_id = e.employee_id AND c.record_kind = 'roster'
JOIN public.hr_canonical_snapshots s
  ON s.snapshot_id = c.snapshot_id AND s.status = 'active'
WHERE p.person_status IN ('active', 'inactive')
  AND length(regexp_replace(COALESCE(c.iin, ''), '[^0-9]', '', 'g')) = 12
  AND NOT EXISTS (
      SELECT 1
      FROM public.employee_identities ei
      WHERE ei.employee_id = e.employee_id
        AND ei.identity_type = 'IIN'
        AND ei.valid_to IS NULL
        AND regexp_replace(COALESCE(ei.identity_value, ''), '[^0-9]', '', 'g')
            = regexp_replace(COALESCE(c.iin, ''), '[^0-9]', '', 'g')
  )
ORDER BY p.person_id;

-- =============================================================================
-- G1 / V1b — duplicate active IIN across persons
-- =============================================================================
SELECT
    'duplicate_active_iin' AS check_name,
    p.iin,
    COUNT(*) AS cnt,
    array_agg(p.person_id ORDER BY p.person_id) AS person_ids
FROM public.persons p
WHERE p.iin IS NOT NULL AND p.person_status = 'active'
GROUP BY p.iin
HAVING COUNT(*) > 1;

-- =============================================================================
-- Invalid IIN format on persons
-- =============================================================================
SELECT
    'invalid_person_iin' AS check_name,
    p.person_id,
    p.iin
FROM public.persons p
WHERE p.iin IS NOT NULL
  AND (
      length(regexp_replace(p.iin, '[^0-9]', '', 'g')) <> 12
      OR regexp_replace(p.iin, '[^0-9]', '', 'g') !~ '^[0-9]{12}$'
  )
ORDER BY p.person_id;

-- =============================================================================
-- V1a — unresolved resolvable gap (canonical IIN on active snapshot, persons.iin NULL)
-- =============================================================================
SELECT
    'unresolved_resolvable_gap' AS check_name,
    p.person_id,
    p.full_name,
    p.match_key,
    c.iin AS canonical_iin
FROM public.persons p
JOIN public.employees e ON e.person_id = p.person_id
JOIN public.hr_canonical_snapshot_entries c
  ON c.employee_id = e.employee_id AND c.record_kind = 'roster'
JOIN public.hr_canonical_snapshots s
  ON s.snapshot_id = c.snapshot_id AND s.status = 'active'
WHERE p.person_status IN ('active', 'inactive')
  AND p.iin IS NULL
  AND length(regexp_replace(COALESCE(c.iin, ''), '[^0-9]', '', 'g')) = 12
ORDER BY p.person_id;

-- =============================================================================
-- V1e — match_key drift vs latest R1a execute rollback payload (when journal exists)
-- Compare current match_key to match_key stored at apply time.
-- =============================================================================
SELECT
    'match_key_drift_vs_journal' AS check_name,
    i.person_id,
    p.match_key AS current_match_key,
    i.rollback_payload->>'match_key' AS journal_match_key,
    i.run_id,
    i.item_id
FROM public.identity_reconciliation_items i
JOIN public.persons p ON p.person_id = i.person_id
JOIN public.identity_reconciliation_runs r ON r.run_id = i.run_id
WHERE r.phase = 'R1a'
  AND r.dry_run = FALSE
  AND i.status = 'applied'
  AND i.rollback_payload ? 'match_key'
  AND p.match_key IS DISTINCT FROM (i.rollback_payload->>'match_key')
ORDER BY i.item_id;

-- =============================================================================
-- users.employee_id unchanged check helper (manual baseline compare)
-- Export before execute: SELECT user_id, employee_id FROM users ORDER BY user_id;
-- Re-run same query after execute; diff must be empty.
-- =============================================================================
SELECT
    'users_employee_id_snapshot' AS check_name,
    user_id,
    employee_id
FROM public.users
ORDER BY user_id;

-- =============================================================================
-- No INSERT persons during R1a — persons count baseline compare (manual)
-- Record COUNT(*) FROM persons before execute; must match after execute.
-- =============================================================================
SELECT
    'persons_count' AS check_name,
    COUNT(*) AS total_persons
FROM public.persons;

-- =============================================================================
-- Idempotent dry-run after execute — apply_count should be 0 for already-filled cohort
-- Run service dry-run separately; this SQL approximates remaining APPLY gap:
-- persons with NULL iin linked to resolvable canonical IIN without blocking conflicts.
-- =============================================================================
SELECT
    'remaining_null_iin_with_canonical' AS check_name,
    COUNT(DISTINCT p.person_id) AS person_count
FROM public.persons p
JOIN public.employees e ON e.person_id = p.person_id
JOIN public.hr_canonical_snapshot_entries c
  ON c.employee_id = e.employee_id AND c.record_kind = 'roster'
JOIN public.hr_canonical_snapshots s
  ON s.snapshot_id = c.snapshot_id AND s.status = 'active'
WHERE p.person_status IN ('active', 'inactive')
  AND p.iin IS NULL
  AND length(regexp_replace(COALESCE(c.iin, ''), '[^0-9]', '', 'g')) = 12;

-- =============================================================================
-- G4 — multiple persons same canonical IIN (merge needed)
-- =============================================================================
SELECT
    'g4_shared_canonical_iin' AS check_name,
    c.iin,
    COUNT(DISTINCT p.person_id) AS person_count,
    array_agg(DISTINCT p.person_id ORDER BY p.person_id) AS person_ids
FROM public.persons p
JOIN public.employees e ON e.person_id = p.person_id
JOIN public.hr_canonical_snapshot_entries c
  ON c.employee_id = e.employee_id AND c.record_kind = 'roster'
JOIN public.hr_canonical_snapshots s
  ON s.snapshot_id = c.snapshot_id AND s.status = 'active'
WHERE p.iin IS NULL
  AND c.iin IS NOT NULL
  AND p.person_status = 'active'
GROUP BY c.iin
HAVING COUNT(DISTINCT p.person_id) > 1;

-- =============================================================================
-- Recent R1a execute runs summary
-- =============================================================================
SELECT
    'recent_r1a_runs' AS check_name,
    run_id,
    dry_run,
    status,
    started_at,
    finished_at,
    actor_user_id,
    snapshot_id,
    summary
FROM public.identity_reconciliation_runs
WHERE phase = 'R1a'
ORDER BY started_at DESC
LIMIT 10;
