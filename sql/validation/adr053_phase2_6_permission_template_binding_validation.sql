-- ADR-053 Phase 2.6a/2.6b — Permission Template binding validation queries
-- Usage: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/validation/adr053_phase2_6_permission_template_binding_validation.sql
--
-- Phase 2.6a (engineering): schema + backfill mechanism may be deployed with zero contour rules.
--   Sections 1–3 will show templates_unmapped > 0 until Phase 2.6b — expected, not a deploy blocker.
-- Phase 2.6b (ops): after approved contour rules are inserted and backfill applied, re-run for binding coverage.
--   See docs/ops/OPS-030-permission-template-contour-binding.md (ADR-053 AC3 Pending).
--
-- Sections 1–3 are informational summaries.
-- Sections 4–8 return violating rows; empty result = OK.

-- =============================================================================
-- 1. Cabinet structural integrity (unchanged from Phase 2.2)
-- =============================================================================
SELECT
    'cabinet_counts' AS check_name,
    (SELECT COUNT(*) FROM public.org_unique_position) AS org_unique_position_count,
    (SELECT COUNT(*) FROM public.position_cabinet) AS position_cabinet_count,
    (SELECT COUNT(*) FROM public.permission_template) AS permission_template_count,
    (SELECT COUNT(*) FROM public.legacy_position_mapping) AS legacy_mapping_count;

-- =============================================================================
-- 2. Binding completeness summary
-- =============================================================================
SELECT
    'binding_completeness' AS check_name,
    COUNT(*) AS template_total,
    COUNT(*) FILTER (WHERE access_role_id IS NOT NULL) AS templates_with_access_role,
    COUNT(*) FILTER (WHERE role_id IS NOT NULL) AS templates_with_role_id,
    COUNT(*) FILTER (WHERE access_role_id IS NULL AND role_id IS NULL) AS templates_unmapped
FROM public.permission_template;

-- =============================================================================
-- 3. Active contour rules summary
-- =============================================================================
SELECT
    'contour_rules' AS check_name,
    COUNT(*) AS rule_total,
    COUNT(*) FILTER (WHERE is_active) AS active_rules
FROM public.permission_template_contour_rule;

-- =============================================================================
-- 4. Orphan access_role_id (FK target missing or inactive)
-- =============================================================================
SELECT
    'orphan_access_role_binding' AS check_name,
    pt.permission_template_id,
    pt.position_cabinet_id,
    pt.access_role_id
FROM public.permission_template pt
LEFT JOIN public.access_roles ar
  ON ar.access_role_id = pt.access_role_id
WHERE pt.access_role_id IS NOT NULL
  AND (ar.access_role_id IS NULL OR ar.is_active IS NOT TRUE);

-- =============================================================================
-- 5. Inactive contour rule still referenced (should not happen post-backfill)
-- =============================================================================
SELECT
    'inactive_contour_rule_referenced' AS check_name,
    cr.contour_rule_id,
    cr.org_unit_id,
    cr.catalog_position_id,
    cr.access_role_id,
    cr.is_active
FROM public.permission_template_contour_rule cr
JOIN public.org_unique_position oup
  ON oup.client_scope_id = cr.client_scope_id
 AND oup.org_unit_id = cr.org_unit_id
 AND oup.catalog_position_id = cr.catalog_position_id
JOIN public.position_cabinet pc
  ON pc.org_unique_position_id = oup.org_unique_position_id
JOIN public.permission_template pt
  ON pt.position_cabinet_id = pc.position_cabinet_id
WHERE cr.is_active IS NOT TRUE
  AND pt.access_role_id = cr.access_role_id;

-- =============================================================================
-- 6. Cabinet 1:1 template invariant (regression)
-- =============================================================================
SELECT
    'cabinet_template_invariant_violation' AS check_name,
    pc.position_cabinet_id,
    COUNT(pt.permission_template_id) AS template_count
FROM public.position_cabinet pc
LEFT JOIN public.permission_template pt
  ON pt.position_cabinet_id = pc.position_cabinet_id
GROUP BY pc.position_cabinet_id
HAVING COUNT(pt.permission_template_id) <> 1;

-- =============================================================================
-- 7. Contour rule without matching org-unique position (ops hygiene)
-- =============================================================================
SELECT
    'contour_rule_without_position' AS check_name,
    cr.contour_rule_id,
    cr.client_scope_id,
    cr.org_unit_id,
    cr.catalog_position_id
FROM public.permission_template_contour_rule cr
LEFT JOIN public.org_unique_position oup
  ON oup.client_scope_id = cr.client_scope_id
 AND oup.org_unit_id = cr.org_unit_id
 AND oup.catalog_position_id = cr.catalog_position_id
WHERE cr.is_active IS TRUE
  AND oup.org_unique_position_id IS NULL;

-- =============================================================================
-- 8. Shadow parity sample (informational — requires runtime logs for full stats)
-- =============================================================================
-- Manual: grep application logs for cabinet_access_shadow outcome=match|mismatch
-- after Phase 2.6b bind + deploy with CABINET_ACCESS_SHADOW_MODE=true.
SELECT
    'shadow_parity_sample_templates' AS check_name,
    pt.permission_template_id,
    pt.access_role_id,
    ar.code AS access_role_code,
    pt.role_id,
    r.code AS role_code
FROM public.permission_template pt
LEFT JOIN public.access_roles ar ON ar.access_role_id = pt.access_role_id
LEFT JOIN public.roles r ON r.role_id = pt.role_id
ORDER BY pt.permission_template_id
LIMIT 20;
