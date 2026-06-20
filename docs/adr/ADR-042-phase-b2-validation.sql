-- ADR-042 Phase B2 — post-migration validation queries
-- Usage: psql $DATABASE_URL -f docs/adr/ADR-042-phase-b2-validation.sql
-- Each section returns violating rows; empty result = OK.

-- =============================================================================
-- 1. employees без person_id (кроме terminated без backfill)
-- =============================================================================
SELECT
    'employees_without_person' AS check_name,
    e.employee_id,
    e.full_name,
    e.operational_status,
    e.is_active
FROM public.employees e
WHERE e.person_id IS NULL
  AND e.operational_status <> 'terminated'
ORDER BY e.employee_id;

-- =============================================================================
-- 2. persons с active employee link но без employee (enrolled orphan persons)
-- =============================================================================
SELECT
    'persons_without_employee' AS check_name,
    p.person_id,
    p.full_name,
    p.match_key,
    p.source
FROM public.persons p
WHERE p.person_status = 'active'
  AND p.source IN ('migration', 'enrollment')
  AND EXISTS (
      SELECT 1
      FROM public.person_assignments pa
      JOIN public.employee_assignment_links l
        ON l.assignment_id = pa.assignment_id
       AND l.link_status = 'active'
      WHERE pa.person_id = p.person_id
  )
  AND NOT EXISTS (
      SELECT 1
      FROM public.employees e
      WHERE e.person_id = p.person_id
        AND e.operational_status IN ('draft', 'active', 'suspended')
  )
ORDER BY p.person_id;

-- =============================================================================
-- 3. active employee_assignment_links без active assignment
-- =============================================================================
SELECT
    'active_link_inactive_assignment' AS check_name,
    l.link_id,
    l.employee_id,
    l.assignment_id,
    l.link_status,
    pa.active_flag,
    pa.lifecycle_status
FROM public.employee_assignment_links l
JOIN public.person_assignments pa ON pa.assignment_id = l.assignment_id
WHERE l.link_status = 'active'
  AND (
      pa.active_flag = FALSE
      OR pa.lifecycle_status <> 'active'
  )
ORDER BY l.link_id;

-- =============================================================================
-- 4. assignments без person
-- =============================================================================
SELECT
    'assignments_without_person' AS check_name,
    pa.assignment_id,
    pa.person_id
FROM public.person_assignments pa
LEFT JOIN public.persons p ON p.person_id = pa.person_id
WHERE p.person_id IS NULL
ORDER BY pa.assignment_id;

-- =============================================================================
-- 5. duplicate persons by iin (active)
-- =============================================================================
SELECT
    'duplicate_persons_by_iin' AS check_name,
    p.iin,
    COUNT(*) AS cnt,
    array_agg(p.person_id ORDER BY p.person_id) AS person_ids
FROM public.persons p
WHERE p.iin IS NOT NULL
  AND p.person_status = 'active'
GROUP BY p.iin
HAVING COUNT(*) > 1
ORDER BY p.iin;

-- =============================================================================
-- 6. duplicate persons by match_key (active/inactive)
-- =============================================================================
SELECT
    'duplicate_persons_by_match_key' AS check_name,
    p.match_key,
    COUNT(*) AS cnt,
    array_agg(p.person_id ORDER BY p.person_id) AS person_ids
FROM public.persons p
WHERE p.person_status IN ('active', 'inactive')
GROUP BY p.match_key
HAVING COUNT(*) > 1
ORDER BY p.match_key;

-- =============================================================================
-- 7. несколько active operational employees на одного person
-- =============================================================================
SELECT
    'multiple_active_employees_per_person' AS check_name,
    e.person_id,
    COUNT(*) AS cnt,
    array_agg(e.employee_id ORDER BY e.employee_id) AS employee_ids
FROM public.employees e
WHERE e.person_id IS NOT NULL
  AND e.operational_status IN ('draft', 'active', 'suspended')
GROUP BY e.person_id
HAVING COUNT(*) > 1
ORDER BY e.person_id;

-- =============================================================================
-- 8. access_grants с несуществующим target (polymorphic FK sanity)
-- =============================================================================
SELECT
    'access_grants_invalid_target' AS check_name,
    g.grant_id,
    g.target_type,
    g.target_id,
    g.active_flag
FROM public.access_grants g
WHERE g.active_flag = TRUE
  AND (
      (g.target_type = 'PERSON' AND NOT EXISTS (
          SELECT 1 FROM public.persons p WHERE p.person_id = g.target_id
      ))
      OR (g.target_type = 'ASSIGNMENT' AND NOT EXISTS (
          SELECT 1 FROM public.person_assignments pa WHERE pa.assignment_id = g.target_id
      ))
      OR (g.target_type = 'POSITION' AND NOT EXISTS (
          SELECT 1 FROM public.positions pos WHERE pos.position_id = g.target_id
      ))
      OR (g.target_type = 'ORG_UNIT' AND NOT EXISTS (
          SELECT 1 FROM public.org_units ou WHERE ou.unit_id = g.target_id
      ))
      OR (g.target_type = 'EMPLOYEE' AND NOT EXISTS (
          SELECT 1 FROM public.employees e WHERE e.employee_id = g.target_id
      ))
      OR (g.target_type = 'USER' AND NOT EXISTS (
          SELECT 1 FROM public.users u WHERE u.user_id = g.target_id
      ))
  )
ORDER BY g.grant_id;

-- =============================================================================
-- 9. security_audit_log с password-like данными в metadata
-- =============================================================================
SELECT
    'audit_password_like_metadata' AS check_name,
    s.audit_id,
    s.event_type,
    s.happened_at,
    s.metadata
FROM public.security_audit_log s
WHERE s.metadata::text ~* '(password|passwd|pwd|secret|token)[^a-z_]*[:=]'
   OR s.metadata ? 'password'
   OR s.metadata ? 'password_plain'
   OR s.metadata ? 'temp_password'
ORDER BY s.audit_id;

-- =============================================================================
-- 10. drift: employees snapshot columns vs primary assignment
-- =============================================================================
SELECT
    'employees_primary_assignment_drift' AS check_name,
    e.employee_id,
    e.org_unit_id AS emp_org_unit_id,
    pa.org_unit_id AS pa_org_unit_id,
    e.position_id AS emp_position_id,
    pa.position_id AS pa_position_id,
    e.employment_rate AS emp_rate,
    pa.rate AS pa_rate,
    e.date_from AS emp_date_from,
    pa.start_date AS pa_start_date,
    e.date_to AS emp_date_to,
    pa.end_date AS pa_end_date
FROM public.employees e
JOIN public.person_assignments pa
  ON pa.person_id = e.person_id
 AND pa.is_primary = TRUE
 AND pa.lifecycle_status = 'active'
WHERE e.person_id IS NOT NULL
  AND (
      e.org_unit_id IS DISTINCT FROM pa.org_unit_id
      OR e.position_id IS DISTINCT FROM pa.position_id
      OR e.employment_rate IS DISTINCT FROM pa.rate
      OR e.date_from IS DISTINCT FROM pa.start_date
      OR e.date_to IS DISTINCT FROM pa.end_date
  )
ORDER BY e.employee_id;

-- =============================================================================
-- Summary counts (informational)
-- =============================================================================
SELECT 'summary' AS section, 'persons' AS entity, COUNT(*) AS cnt FROM public.persons
UNION ALL
SELECT 'summary', 'person_assignments', COUNT(*) FROM public.person_assignments
UNION ALL
SELECT 'summary', 'employees_with_person', COUNT(*) FROM public.employees WHERE person_id IS NOT NULL
UNION ALL
SELECT 'summary', 'employee_assignment_links_active', COUNT(*)
FROM public.employee_assignment_links WHERE link_status = 'active'
UNION ALL
SELECT 'summary', 'access_roles', COUNT(*) FROM public.access_roles
UNION ALL
SELECT 'summary', 'access_grants_active', COUNT(*) FROM public.access_grants WHERE active_flag = TRUE;
