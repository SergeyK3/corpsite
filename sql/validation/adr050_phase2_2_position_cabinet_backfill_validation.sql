-- ADR-050 Phase 2.2 — post-backfill validation queries
-- Usage: psql $DATABASE_URL -f sql/validation/adr050_phase2_2_position_cabinet_backfill_validation.sql
--
-- Sections 1–2 are informational summaries.
-- Sections 3–7 return violating rows; empty result = OK.

-- =============================================================================
-- Shared inventory CTE (matches l6m7n8o9p0q1 backfill migration)
-- =============================================================================
-- inventory AS (
--     SELECT DISTINCT
--         1 AS client_scope_id,
--         pairs.org_unit_id,
--         pairs.catalog_position_id
--     FROM (
--         SELECT e.org_unit_id, e.position_id AS catalog_position_id
--         FROM public.employees e
--         WHERE e.org_unit_id IS NOT NULL
--           AND e.position_id IS NOT NULL
--         UNION
--         SELECT pa.org_unit_id, pa.position_id AS catalog_position_id
--         FROM public.person_assignments pa
--         WHERE pa.org_unit_id IS NOT NULL
--           AND pa.position_id IS NOT NULL
--     ) pairs
--     INNER JOIN public.org_units ou ON ou.unit_id = pairs.org_unit_id
--     INNER JOIN public.positions pos ON pos.position_id = pairs.catalog_position_id
-- )

-- =============================================================================
-- 1. Row counts (informational)
-- =============================================================================
SELECT
    'row_counts' AS check_name,
    (SELECT COUNT(*) FROM public.org_unique_position) AS org_unique_position_count,
    (SELECT COUNT(*) FROM public.position_cabinet) AS position_cabinet_count,
    (SELECT COUNT(*) FROM public.permission_template) AS permission_template_count,
    (SELECT COUNT(*) FROM public.legacy_position_mapping) AS legacy_position_mapping_count;

-- =============================================================================
-- 2. Inventory count (informational)
--    Distinct valid (client_scope_id=1, org_unit_id, catalog_position_id) pairs
--    from employees UNION person_assignments with FK-resolvable org_units/positions.
-- =============================================================================
SELECT
    'inventory_count' AS check_name,
    COUNT(*) AS inventory_pair_count
FROM (
    SELECT DISTINCT
        1 AS client_scope_id,
        pairs.org_unit_id,
        pairs.catalog_position_id
    FROM (
        SELECT e.org_unit_id, e.position_id AS catalog_position_id
        FROM public.employees e
        WHERE e.org_unit_id IS NOT NULL
          AND e.position_id IS NOT NULL
        UNION
        SELECT pa.org_unit_id, pa.position_id AS catalog_position_id
        FROM public.person_assignments pa
        WHERE pa.org_unit_id IS NOT NULL
          AND pa.position_id IS NOT NULL
    ) pairs
    INNER JOIN public.org_units ou ON ou.unit_id = pairs.org_unit_id
    INNER JOIN public.positions pos ON pos.position_id = pairs.catalog_position_id
) inventory;

-- =============================================================================
-- 3. Missing mappings — inventory pairs absent from legacy_position_mapping
-- =============================================================================
SELECT
    'missing_mapping' AS check_name,
    inv.client_scope_id,
    inv.org_unit_id,
    inv.catalog_position_id
FROM (
    SELECT DISTINCT
        1 AS client_scope_id,
        pairs.org_unit_id,
        pairs.catalog_position_id
    FROM (
        SELECT e.org_unit_id, e.position_id AS catalog_position_id
        FROM public.employees e
        WHERE e.org_unit_id IS NOT NULL
          AND e.position_id IS NOT NULL
        UNION
        SELECT pa.org_unit_id, pa.position_id AS catalog_position_id
        FROM public.person_assignments pa
        WHERE pa.org_unit_id IS NOT NULL
          AND pa.position_id IS NOT NULL
    ) pairs
    INNER JOIN public.org_units ou ON ou.unit_id = pairs.org_unit_id
    INNER JOIN public.positions pos ON pos.position_id = pairs.catalog_position_id
) inv
WHERE NOT EXISTS (
    SELECT 1
    FROM public.legacy_position_mapping lpm
    WHERE lpm.client_scope_id = inv.client_scope_id
      AND lpm.org_unit_id = inv.org_unit_id
      AND lpm.catalog_position_id = inv.catalog_position_id
)
ORDER BY inv.org_unit_id, inv.catalog_position_id;

-- =============================================================================
-- 4. Broken mappings — legacy_position_mapping without matching org_unique_position
--    or with mismatched (client_scope_id, org_unit_id, catalog_position_id)
-- =============================================================================
SELECT
    'broken_mapping_missing_target' AS check_name,
    lpm.legacy_position_mapping_id,
    lpm.org_unique_position_id,
    lpm.client_scope_id,
    lpm.org_unit_id,
    lpm.catalog_position_id
FROM public.legacy_position_mapping lpm
LEFT JOIN public.org_unique_position oup
    ON oup.org_unique_position_id = lpm.org_unique_position_id
WHERE oup.org_unique_position_id IS NULL
ORDER BY lpm.legacy_position_mapping_id;

SELECT
    'broken_mapping_mismatched_target' AS check_name,
    lpm.legacy_position_mapping_id,
    lpm.org_unique_position_id,
    lpm.client_scope_id AS mapping_client_scope_id,
    oup.client_scope_id AS target_client_scope_id,
    lpm.org_unit_id AS mapping_org_unit_id,
    oup.org_unit_id AS target_org_unit_id,
    lpm.catalog_position_id AS mapping_catalog_position_id,
    oup.catalog_position_id AS target_catalog_position_id
FROM public.legacy_position_mapping lpm
JOIN public.org_unique_position oup
    ON oup.org_unique_position_id = lpm.org_unique_position_id
WHERE lpm.client_scope_id <> oup.client_scope_id
   OR lpm.org_unit_id <> oup.org_unit_id
   OR lpm.catalog_position_id <> oup.catalog_position_id
ORDER BY lpm.legacy_position_mapping_id;

-- =============================================================================
-- 5. Cabinet invariant — org_unique_position without exactly one position_cabinet
-- =============================================================================
SELECT
    'cabinet_invariant_violation' AS check_name,
    oup.org_unique_position_id,
    oup.org_unit_id,
    oup.catalog_position_id,
    COUNT(pc.position_cabinet_id) AS cabinet_count
FROM public.org_unique_position oup
LEFT JOIN public.position_cabinet pc
    ON pc.org_unique_position_id = oup.org_unique_position_id
GROUP BY oup.org_unique_position_id, oup.org_unit_id, oup.catalog_position_id
HAVING COUNT(pc.position_cabinet_id) <> 1
ORDER BY oup.org_unique_position_id;

-- =============================================================================
-- 6. Permission template invariant — position_cabinet without exactly one template
-- =============================================================================
SELECT
    'permission_template_invariant_violation' AS check_name,
    pc.position_cabinet_id,
    pc.org_unique_position_id,
    COUNT(pt.permission_template_id) AS template_count
FROM public.position_cabinet pc
LEFT JOIN public.permission_template pt
    ON pt.position_cabinet_id = pc.position_cabinet_id
GROUP BY pc.position_cabinet_id, pc.org_unique_position_id
HAVING COUNT(pt.permission_template_id) <> 1
ORDER BY pc.position_cabinet_id;

-- =============================================================================
-- 7. Forbidden ownership — Person/Employee/User/Employment columns or FKs
--    on position_cabinet and permission_template (ADR-050: Cabinet belongs to Position)
-- =============================================================================
SELECT
    'forbidden_ownership_column' AS check_name,
    c.table_name,
    c.column_name
FROM information_schema.columns c
WHERE c.table_schema = 'public'
  AND c.table_name IN ('position_cabinet', 'permission_template')
  AND c.column_name IN (
      'person_id',
      'employee_id',
      'user_id',
      'person_assignment_id',
      'assignment_id',
      'employment_id'
  )
ORDER BY c.table_name, c.column_name;

SELECT
    'forbidden_ownership_fk' AS check_name,
    t.relname AS table_name,
    rt.relname AS referenced_table
FROM pg_constraint c
JOIN pg_class t ON t.oid = c.conrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
JOIN pg_class rt ON rt.oid = c.confrelid
JOIN pg_namespace rn ON rn.oid = rt.relnamespace
WHERE n.nspname = 'public'
  AND t.relname IN ('position_cabinet', 'permission_template')
  AND rn.nspname = 'public'
  AND c.contype = 'f'
  AND rt.relname IN ('users', 'persons', 'employees', 'person_assignments')
ORDER BY t.relname, rt.relname;
