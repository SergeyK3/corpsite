-- ADR-043 Phase B2 — post-migration validation queries
-- Usage: psql $DATABASE_URL -f docs/adr/ADR-043-phase-b2-validation.sql
-- Each section returns violating rows; empty result = OK.

-- =============================================================================
-- 1. duplicate active overrides (scope_key + field_path)
-- =============================================================================
SELECT
    'duplicate_active_overrides' AS check_name,
    o.scope_key,
    o.field_path,
    COUNT(*) AS cnt,
    array_agg(o.override_id ORDER BY o.override_id) AS override_ids
FROM public.hr_review_overrides o
WHERE o.status = 'active'
GROUP BY o.scope_key, o.field_path
HAVING COUNT(*) > 1
ORDER BY o.scope_key, o.field_path;

-- =============================================================================
-- 2. duplicate pending overrides
-- =============================================================================
SELECT
    'duplicate_pending_overrides' AS check_name,
    o.scope_key,
    o.field_path,
    COUNT(*) AS cnt,
    array_agg(o.override_id ORDER BY o.override_id) AS override_ids
FROM public.hr_review_overrides o
WHERE o.status = 'pending_approval'
GROUP BY o.scope_key, o.field_path
HAVING COUNT(*) > 1
ORDER BY o.scope_key, o.field_path;

-- =============================================================================
-- 3. Tier 2 active without approval
-- =============================================================================
SELECT
    'tier2_active_without_approval' AS check_name,
    o.override_id,
    o.scope_key,
    o.field_path,
    o.tier,
    o.status,
    o.approved_by_user_id,
    o.approved_at
FROM public.hr_review_overrides o
WHERE o.tier = 2
  AND o.status = 'active'
  AND (
      o.approved_by_user_id IS NULL
      OR o.approved_at IS NULL
      OR o.approved_by_user_id = o.created_by_user_id
  )
ORDER BY o.override_id;

-- =============================================================================
-- 4. Tier 2 IIN without evidence
-- =============================================================================
SELECT
    'tier2_iin_without_evidence' AS check_name,
    o.override_id,
    o.scope_key,
    o.field_path,
    o.status,
    o.evidence_url
FROM public.hr_review_overrides o
WHERE o.tier = 2
  AND o.status IN ('active', 'pending_approval')
  AND o.field_path = 'identity.iin'
  AND (o.evidence_url IS NULL OR length(trim(o.evidence_url)) = 0)
ORDER BY o.override_id;

-- =============================================================================
-- 5. stale overrides older than threshold (365 days)
-- =============================================================================
SELECT
    'stale_overrides_older_than_threshold' AS check_name,
    o.override_id,
    o.scope_key,
    o.field_path,
    o.stale_since,
    o.stale_reason
FROM public.hr_review_overrides o
WHERE o.stale_flag = TRUE
  AND o.stale_since IS NOT NULL
  AND o.stale_since < now() - interval '365 days'
ORDER BY o.stale_since;

-- =============================================================================
-- 6. active overrides without CREATED history
-- =============================================================================
SELECT
    'overrides_without_created_history' AS check_name,
    o.override_id,
    o.scope_key,
    o.field_path,
    o.status
FROM public.hr_review_overrides o
WHERE NOT EXISTS (
    SELECT 1
    FROM public.hr_review_override_history h
    WHERE h.override_id = o.override_id
      AND h.event_type = 'CREATED'
)
ORDER BY o.override_id;

-- =============================================================================
-- 7. active/pending overrides tier >= 1 without justification
-- =============================================================================
SELECT
    'overrides_missing_justification' AS check_name,
    o.override_id,
    o.scope_key,
    o.field_path,
    o.tier,
    o.status,
    o.justification
FROM public.hr_review_overrides o
WHERE o.tier >= 1
  AND o.status IN ('active', 'pending_approval')
  AND (
      o.justification IS NULL
      OR length(trim(o.justification)) < 10
  )
ORDER BY o.override_id;

-- =============================================================================
-- 8. personnel events without valid event_hash
-- =============================================================================
SELECT
    'personnel_events_invalid_hash' AS check_name,
    pe.personnel_event_id,
    pe.event_type,
    pe.event_hash
FROM public.hr_personnel_change_events pe
WHERE pe.event_hash IS NULL
   OR length(trim(pe.event_hash)) <> 64
ORDER BY pe.personnel_event_id;

-- =============================================================================
-- 9. duplicate personnel events by event_hash
-- =============================================================================
SELECT
    'duplicate_personnel_events' AS check_name,
    pe.event_hash,
    COUNT(*) AS cnt,
    array_agg(pe.personnel_event_id ORDER BY pe.personnel_event_id) AS event_ids
FROM public.hr_personnel_change_events pe
GROUP BY pe.event_hash
HAVING COUNT(*) > 1
ORDER BY pe.event_hash;

-- =============================================================================
-- 10. enrollment-trigger events not queued (informational; detector not required yet)
-- =============================================================================
SELECT
    'enrollment_trigger_not_queued' AS check_name,
    pe.personnel_event_id,
    pe.event_type,
    pe.person_key,
    pe.detected_at
FROM public.hr_personnel_change_events pe
WHERE pe.event_type IN (
    'NEW_PERSON', 'NEW_ASSIGNMENT', 'CLOSED_ASSIGNMENT',
    'TERMINATED_PERSON', 'TRANSFER', 'POSITION_CHANGED'
)
  AND pe.status = 'detected'
  AND pe.detected_at < now() - interval '1 day'
  AND NOT EXISTS (
      SELECT 1
      FROM public.enrollment_queue eq
      WHERE eq.personnel_event_id = pe.personnel_event_id
         OR (
             eq.change_event_id = pe.source_event_id
             AND eq.queue_status IN ('PENDING', 'APPROVED')
         )
  )
ORDER BY pe.detected_at;

-- =============================================================================
-- 11. outdated effective snapshot entries vs active overrides
-- =============================================================================
SELECT
    'effective_cache_outdated' AS check_name,
    e.effective_entry_id,
    e.snapshot_id,
    e.match_key,
    e.computed_at,
    o.override_id,
    o.updated_at AS override_updated_at
FROM public.hr_snapshot_effective_entries e
JOIN public.hr_canonical_snapshots s
  ON s.snapshot_id = e.snapshot_id
 AND s.status = 'active'
JOIN public.hr_review_overrides o
  ON o.scope_key = e.scope_key
 AND o.status = 'active'
 AND o.updated_at > e.computed_at
ORDER BY e.effective_entry_id;

-- =============================================================================
-- 12. orphan source_file references on batches
-- =============================================================================
SELECT
    'orphan_batch_source_file' AS check_name,
    b.batch_id,
    b.source_file_id
FROM public.hr_import_batches b
WHERE b.source_file_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.hr_source_files sf
      WHERE sf.source_file_id = b.source_file_id
  )
ORDER BY b.batch_id;

-- =============================================================================
-- 13. invalid scope_key format
-- =============================================================================
SELECT
    'invalid_override_scope_key' AS check_name,
    o.override_id,
    o.scope_key
FROM public.hr_review_overrides o
WHERE o.scope_key !~ '^(PERSON|ASSIGNMENT|DOCUMENT|TRAINING|CERTIFICATE|CATEGORY):'
ORDER BY o.override_id;

-- =============================================================================
-- 14. pending replacement without supersedes when active exists
-- =============================================================================
SELECT
    'pending_without_supersedes_when_active_exists' AS check_name,
    p.override_id AS pending_id,
    p.scope_key,
    p.field_path,
    p.supersedes_override_id
FROM public.hr_review_overrides p
WHERE p.status = 'pending_approval'
  AND p.supersedes_override_id IS NULL
  AND EXISTS (
      SELECT 1
      FROM public.hr_review_overrides a
      WHERE a.scope_key = p.scope_key
        AND a.field_path = p.field_path
        AND a.status = 'active'
  )
ORDER BY p.override_id;

-- =============================================================================
-- 15. field_paths without stewardship coverage (no matching active rule)
-- =============================================================================
SELECT
    'field_paths_without_stewardship_rule' AS check_name,
    o.override_id,
    o.field_path,
    o.scope_type
FROM public.hr_review_overrides o
WHERE o.status IN ('active', 'pending_approval')
        AND NOT EXISTS (
      SELECT 1
      FROM public.hr_override_stewardship_rules r
      WHERE r.active_flag = TRUE
        AND (r.scope_type IS NULL OR r.scope_type = o.scope_type)
        AND (
            r.field_path_pattern = '%'
            OR o.field_path LIKE r.field_path_pattern
            OR o.field_path = r.field_path_pattern
        )
  )
ORDER BY o.override_id;

-- =============================================================================
-- Summary counts (informational)
-- =============================================================================
SELECT 'summary' AS section, 'hr_source_files' AS entity, COUNT(*) AS cnt FROM public.hr_source_files
UNION ALL
SELECT 'summary', 'hr_review_overrides', COUNT(*) FROM public.hr_review_overrides
UNION ALL
SELECT 'summary', 'hr_review_overrides_active', COUNT(*) FROM public.hr_review_overrides WHERE status = 'active'
UNION ALL
SELECT 'summary', 'hr_review_override_history', COUNT(*) FROM public.hr_review_override_history
UNION ALL
SELECT 'summary', 'hr_personnel_change_events', COUNT(*) FROM public.hr_personnel_change_events
UNION ALL
SELECT 'summary', 'hr_snapshot_effective_entries', COUNT(*) FROM public.hr_snapshot_effective_entries
UNION ALL
SELECT 'summary', 'hr_override_stewardship_rules_active', COUNT(*)
FROM public.hr_override_stewardship_rules WHERE active_flag = TRUE;
