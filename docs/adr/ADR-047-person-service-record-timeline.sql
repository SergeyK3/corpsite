-- ADR-047 — Person Service Record unified timeline (read-only SELECT)
--
-- Purpose: diagnostic query to assess whether a career timeline can be built
-- for a given person_id from existing sources (projection inputs).
--
-- Run:
--   psql "$DATABASE_URL" -v person_id=123 -f docs/adr/ADR-047-person-service-record-timeline.sql
--
-- Or interactively:
--   \set person_id 123
--   \i docs/adr/ADR-047-person-service-record-timeline.sql
--
-- Notes:
-- - NOT a production merge algorithm; sources may overlap and dates may conflict.
-- - employee_events has no person_id; joined via employees.person_id.
-- - hr_orders table does not exist yet; order_ref is TEXT on employee_events.
-- - Excludes VOIDED employee_events.

\echo '=== Person header ==='

SELECT
    p.person_id,
    p.full_name,
    p.iin,
    p.birth_date,
    p.person_status,
    p.match_key,
    (SELECT COUNT(*) FROM public.employees e WHERE e.person_id = p.person_id) AS linked_employees,
    (SELECT COUNT(*) FROM public.person_assignments pa WHERE pa.person_id = p.person_id) AS assignments,
    (SELECT COUNT(*)
     FROM public.employee_events ev
     JOIN public.employees e ON e.employee_id = ev.employee_id
     WHERE e.person_id = p.person_id
       AND COALESCE(ev.lifecycle_status, 'APPROVED') <> 'VOIDED'
    ) AS employee_events,
    (SELECT COUNT(*)
     FROM public.hr_personnel_change_events hpe
     WHERE hpe.person_id = p.person_id
    ) AS personnel_change_events
FROM public.persons p
WHERE p.person_id = :person_id::bigint;

\echo '=== Unified timeline (best-effort projection inputs) ==='

WITH timeline AS (

    -- ------------------------------------------------------------------
    -- 1. person_assignments — ASSIGNMENT_START
    -- ------------------------------------------------------------------
    SELECT
        'person_assignments'::text AS source,
        pa.assignment_id AS source_id,
        pa.start_date AS event_date,
        'ASSIGNMENT_START'::text AS event_type,
        pa.org_unit_id,
        ou.name AS org_unit_name,
        pa.position_id,
        pos.name AS position_name,
        pa.rate,
        NULL::bigint AS from_org_unit_id,
        NULL::text AS from_org_unit_name,
        NULL::bigint AS from_position_id,
        NULL::text AS from_position_name,
        NULL::numeric AS from_rate,
        pa.org_unit_id AS to_org_unit_id,
        ou.name AS to_org_unit_name,
        pa.position_id AS to_position_id,
        pos.name AS to_position_name,
        pa.rate AS to_rate,
        NULL::text AS order_ref,
        NULL::text AS comment,
        pa.lifecycle_status,
        NULL::bigint AS employee_id,
        pa.assignment_id,
        NULL::text AS person_key,
        jsonb_build_object(
            'assignment_key', pa.assignment_key,
            'employment_type', pa.employment_type,
            'active_flag', pa.active_flag,
            'source', pa.source,
            'end_date', pa.end_date
        ) AS diagnostic_json
    FROM public.person_assignments pa
    LEFT JOIN public.org_units ou ON ou.unit_id = pa.org_unit_id
    LEFT JOIN public.positions pos ON pos.position_id = pa.position_id
    WHERE pa.person_id = :person_id::bigint

    UNION ALL

    -- ------------------------------------------------------------------
    -- 1b. person_assignments — ASSIGNMENT_END
    -- ------------------------------------------------------------------
    SELECT
        'person_assignments'::text,
        pa.assignment_id,
        pa.end_date,
        'ASSIGNMENT_END'::text,
        pa.org_unit_id,
        ou.name,
        pa.position_id,
        pos.name,
        pa.rate,
        pa.org_unit_id,
        ou.name,
        pa.position_id,
        pos.name,
        pa.rate,
        NULL::bigint,
        NULL::text,
        NULL::bigint,
        NULL::text,
        NULL::numeric,
        NULL::text,
        NULL::text,
        pa.lifecycle_status,
        NULL::bigint,
        pa.assignment_id,
        NULL::text,
        jsonb_build_object(
            'assignment_key', pa.assignment_key,
            'employment_type', pa.employment_type,
            'active_flag', pa.active_flag,
            'source', pa.source,
            'start_date', pa.start_date
        )
    FROM public.person_assignments pa
    LEFT JOIN public.org_units ou ON ou.unit_id = pa.org_unit_id
    LEFT JOIN public.positions pos ON pos.position_id = pa.position_id
    WHERE pa.person_id = :person_id::bigint
      AND pa.end_date IS NOT NULL

    UNION ALL

    -- ------------------------------------------------------------------
    -- 2. employee_events (via employees.person_id)
    -- ------------------------------------------------------------------
    SELECT
        'employee_events'::text,
        ev.event_id,
        ev.effective_date,
        ev.event_type,
        ev.to_org_unit_id,
        ou_to.name,
        ev.to_position_id,
        pos_to.name,
        ev.to_rate,
        ev.from_org_unit_id,
        ou_from.name,
        ev.from_position_id,
        pos_from.name,
        ev.from_rate,
        ev.to_org_unit_id,
        ou_to.name,
        ev.to_position_id,
        pos_to.name,
        ev.to_rate,
        ev.order_ref,
        ev.comment,
        ev.lifecycle_status,
        ev.employee_id,
        NULL::bigint,
        NULL::text,
        jsonb_build_object(
            'event_class', ev.event_class,
            'metadata', ev.metadata,
            'created_by', ev.created_by,
            'created_at', ev.created_at
        )
    FROM public.employee_events ev
    JOIN public.employees e ON e.employee_id = ev.employee_id
    LEFT JOIN public.org_units ou_from ON ou_from.unit_id = ev.from_org_unit_id
    LEFT JOIN public.org_units ou_to ON ou_to.unit_id = ev.to_org_unit_id
    LEFT JOIN public.positions pos_from ON pos_from.position_id = ev.from_position_id
    LEFT JOIN public.positions pos_to ON pos_to.position_id = ev.to_position_id
    WHERE e.person_id = :person_id::bigint
      AND COALESCE(ev.lifecycle_status, 'APPROVED') <> 'VOIDED'

    UNION ALL

    -- ------------------------------------------------------------------
    -- 3. hr_personnel_change_events
    -- ------------------------------------------------------------------
    SELECT
        'hr_personnel_change_events'::text,
        hpe.personnel_event_id,
        hpe.detected_at::date,
        hpe.event_type,
        CASE
            WHEN hpe.new_value ? 'org_unit_id' THEN (hpe.new_value ->> 'org_unit_id')::bigint
            WHEN hpe.effective_new_value ? 'org_unit_id' THEN (hpe.effective_new_value ->> 'org_unit_id')::bigint
            ELSE NULL::bigint
        END,
        NULL::text,
        CASE
            WHEN hpe.new_value ? 'position_id' THEN (hpe.new_value ->> 'position_id')::bigint
            WHEN hpe.effective_new_value ? 'position_id' THEN (hpe.effective_new_value ->> 'position_id')::bigint
            ELSE NULL::bigint
        END,
        NULL::text,
        CASE
            WHEN hpe.new_value ? 'rate' THEN (hpe.new_value ->> 'rate')::numeric
            WHEN hpe.effective_new_value ? 'rate' THEN (hpe.effective_new_value ->> 'rate')::numeric
            ELSE NULL::numeric
        END,
        CASE
            WHEN hpe.old_value ? 'org_unit_id' THEN (hpe.old_value ->> 'org_unit_id')::bigint
            WHEN hpe.effective_old_value ? 'org_unit_id' THEN (hpe.effective_old_value ->> 'org_unit_id')::bigint
            ELSE NULL::bigint
        END,
        NULL::text,
        CASE
            WHEN hpe.old_value ? 'position_id' THEN (hpe.old_value ->> 'position_id')::bigint
            WHEN hpe.effective_old_value ? 'position_id' THEN (hpe.effective_old_value ->> 'position_id')::bigint
            ELSE NULL::bigint
        END,
        NULL::text,
        CASE
            WHEN hpe.old_value ? 'rate' THEN (hpe.old_value ->> 'rate')::numeric
            WHEN hpe.effective_old_value ? 'rate' THEN (hpe.effective_old_value ->> 'rate')::numeric
            ELSE NULL::numeric
        END,
        CASE
            WHEN hpe.new_value ? 'org_unit_id' THEN (hpe.new_value ->> 'org_unit_id')::bigint
            WHEN hpe.effective_new_value ? 'org_unit_id' THEN (hpe.effective_new_value ->> 'org_unit_id')::bigint
            ELSE NULL::bigint
        END,
        NULL::text,
        CASE
            WHEN hpe.new_value ? 'position_id' THEN (hpe.new_value ->> 'position_id')::bigint
            WHEN hpe.effective_new_value ? 'position_id' THEN (hpe.effective_new_value ->> 'position_id')::bigint
            ELSE NULL::bigint
        END,
        NULL::text,
        CASE
            WHEN hpe.new_value ? 'rate' THEN (hpe.new_value ->> 'rate')::numeric
            WHEN hpe.effective_new_value ? 'rate' THEN (hpe.effective_new_value ->> 'rate')::numeric
            ELSE NULL::numeric
        END,
        NULL::text,
        NULL::text,
        hpe.status,
        NULL::bigint,
        hpe.assignment_id,
        hpe.person_key,
        jsonb_build_object(
            'field_path', hpe.field_path,
            'old_value', hpe.old_value,
            'new_value', hpe.new_value,
            'effective_old_value', hpe.effective_old_value,
            'effective_new_value', hpe.effective_new_value,
            'metadata', hpe.metadata,
            'detected_at', hpe.detected_at,
            'snapshot_id', hpe.snapshot_id,
            'previous_snapshot_id', hpe.previous_snapshot_id,
            'source_event_id', hpe.source_event_id
        )
    FROM public.hr_personnel_change_events hpe
    WHERE hpe.person_id = :person_id::bigint

    UNION ALL

    -- ------------------------------------------------------------------
    -- 4. employees snapshot (current state per linked employee)
    -- ------------------------------------------------------------------
    SELECT
        'employees_snapshot'::text,
        e.employee_id,
        COALESCE(e.date_from, CURRENT_DATE),
        'CURRENT_SNAPSHOT'::text,
        e.org_unit_id,
        ou.name,
        e.position_id,
        pos.name,
        e.employment_rate,
        NULL::bigint,
        NULL::text,
        NULL::bigint,
        NULL::text,
        NULL::numeric,
        e.org_unit_id,
        ou.name,
        e.position_id,
        pos.name,
        e.employment_rate,
        NULL::text,
        NULL::text,
        e.operational_status,
        e.employee_id,
        NULL::bigint,
        NULL::text,
        jsonb_build_object(
            'is_active', e.is_active,
            'date_from', e.date_from,
            'date_to', e.date_to,
            'enrollment_source', e.enrollment_source,
            'full_name', e.full_name
        )
    FROM public.employees e
    LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
    LEFT JOIN public.positions pos ON pos.position_id = e.position_id
    WHERE e.person_id = :person_id::bigint

)

SELECT
    source,
    source_id,
    event_date,
    event_type,
    org_unit_id,
    org_unit_name,
    position_id,
    position_name,
    rate,
    from_org_unit_id,
    from_org_unit_name,
    from_position_id,
    from_position_name,
    from_rate,
    to_org_unit_id,
    to_org_unit_name,
    to_position_id,
    to_position_name,
    to_rate,
    order_ref,
    comment,
    lifecycle_status,
    employee_id,
    assignment_id,
    person_key,
    diagnostic_json
FROM timeline
ORDER BY event_date NULLS LAST, source, event_type, source_id;

\echo '=== Source counts for this person_id ==='

SELECT source, COUNT(*) AS row_count
FROM (
    SELECT 'person_assignments_start' AS source
    FROM public.person_assignments pa
    WHERE pa.person_id = :person_id::bigint
    UNION ALL
    SELECT 'person_assignments_end'
    FROM public.person_assignments pa
    WHERE pa.person_id = :person_id::bigint AND pa.end_date IS NOT NULL
    UNION ALL
    SELECT 'employee_events'
    FROM public.employee_events ev
    JOIN public.employees e ON e.employee_id = ev.employee_id
    WHERE e.person_id = :person_id::bigint
      AND COALESCE(ev.lifecycle_status, 'APPROVED') <> 'VOIDED'
    UNION ALL
    SELECT 'hr_personnel_change_events'
    FROM public.hr_personnel_change_events hpe
    WHERE hpe.person_id = :person_id::bigint
    UNION ALL
    SELECT 'employees_snapshot'
    FROM public.employees e
    WHERE e.person_id = :person_id::bigint
) counts
GROUP BY source
ORDER BY source;

\echo '=== hr_orders availability (expected: not implemented) ==='

SELECT
    to_regclass('public.hr_orders') IS NOT NULL AS hr_orders_table_exists,
    'Use employee_events.order_ref until ADR-036 Phase 1b' AS interim_note;
