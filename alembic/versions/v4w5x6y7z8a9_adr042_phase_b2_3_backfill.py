"""ADR-042 Phase B2.3 — idempotent backfill employees → persons → assignments → links.

Revision ID: v4w5x6y7z8a9
Revises: u3v4w5x6y7z8
"""
from __future__ import annotations

from alembic import op

revision = "v4w5x6y7z8a9"
down_revision = "u3v4w5x6y7z8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            v_actor BIGINT;
            v_fallback_org BIGINT;
            v_fallback_pos BIGINT;
        BEGIN
            SELECT user_id INTO v_actor
            FROM public.users
            WHERE is_active = TRUE
            ORDER BY user_id
            LIMIT 1;

            IF v_actor IS NULL THEN
                RAISE NOTICE 'ADR-042 B2.3: no active users — skipping backfill';
                RETURN;
            END IF;

            SELECT unit_id INTO v_fallback_org
            FROM public.org_units
            WHERE is_active = TRUE
            ORDER BY unit_id
            LIMIT 1;

            SELECT position_id INTO v_fallback_pos
            FROM public.positions
            ORDER BY position_id
            LIMIT 1;

            IF v_fallback_org IS NULL OR v_fallback_pos IS NULL THEN
                RAISE NOTICE 'ADR-042 B2.3: missing org_units/positions — person link only';
            END IF;

            -- ---------------------------------------------------------------
            -- 1) Materialize persons (dedup: active IIN, then match_key)
            -- Inner DISTINCT ON (raw.match_key): one person row per match_key
            -- per INSERT batch. Prevents uq_persons_match_key_active violations
            -- when several unlinked employees share the same computed match_key.
            -- ---------------------------------------------------------------
            INSERT INTO public.persons (
                iin,
                full_name,
                match_key,
                person_status,
                source
            )
            SELECT
                src.iin,
                src.full_name,
                src.match_key,
                CASE WHEN src.is_active THEN 'active' ELSE 'inactive' END,
                'migration'
            FROM (
                SELECT DISTINCT ON (raw.match_key)
                    raw.employee_id,
                    raw.full_name,
                    raw.iin,
                    raw.match_key,
                    raw.is_active
                FROM (
                    SELECT DISTINCT ON (e.employee_id)
                        e.employee_id,
                        trim(e.full_name) AS full_name,
                        CASE
                            WHEN iin.iin IS NOT NULL THEN iin.iin
                            ELSE NULL
                        END AS iin,
                        CASE
                            WHEN iin.iin IS NOT NULL THEN 'iin:' || iin.iin
                            ELSE 'name:' || lower(
                                regexp_replace(trim(e.full_name), '\\s+', ' ', 'g')
                            )
                        END AS match_key,
                        e.is_active
                    FROM public.employees e
                    LEFT JOIN LATERAL (
                        SELECT regexp_replace(ei.identity_value, '[^0-9]', '', 'g') AS iin
                        FROM public.employee_identities ei
                        WHERE ei.employee_id = e.employee_id
                          AND ei.identity_type = 'IIN'
                          AND ei.valid_to IS NULL
                          AND length(regexp_replace(ei.identity_value, '[^0-9]', '', 'g')) = 12
                        ORDER BY ei.is_primary DESC NULLS LAST, ei.identity_id
                        LIMIT 1
                    ) iin ON TRUE
                    WHERE e.person_id IS NULL
                    ORDER BY e.employee_id
                ) raw
                ORDER BY raw.match_key, raw.employee_id
            ) src
            WHERE NOT EXISTS (
                SELECT 1
                FROM public.persons p
                WHERE p.person_status IN ('active', 'inactive')
                  AND (
                      (src.iin IS NOT NULL AND p.iin = src.iin AND p.person_status = 'active')
                      OR p.match_key = src.match_key
                  )
            );

            -- ---------------------------------------------------------------
            -- 2) Link employees → persons (IIN first, then match_key)
            -- ---------------------------------------------------------------
            UPDATE public.employees e
            SET
                person_id = p.person_id,
                enrollment_source = 'migration',
                operational_status = CASE
                    WHEN e.is_active THEN 'active'
                    ELSE 'terminated'
                END,
                enrolled_at = COALESCE(e.enrolled_at, now()),
                updated_at = now()
            FROM (
                SELECT DISTINCT ON (e2.employee_id)
                    e2.employee_id,
                    iin.iin
                FROM public.employees e2
                LEFT JOIN LATERAL (
                    SELECT regexp_replace(ei.identity_value, '[^0-9]', '', 'g') AS iin
                    FROM public.employee_identities ei
                    WHERE ei.employee_id = e2.employee_id
                      AND ei.identity_type = 'IIN'
                      AND ei.valid_to IS NULL
                      AND length(regexp_replace(ei.identity_value, '[^0-9]', '', 'g')) = 12
                    ORDER BY ei.is_primary DESC NULLS LAST, ei.identity_id
                    LIMIT 1
                ) iin ON TRUE
                WHERE e2.person_id IS NULL
                ORDER BY e2.employee_id
            ) src
            JOIN public.persons p
              ON p.iin = src.iin
             AND p.person_status = 'active'
            WHERE e.employee_id = src.employee_id
              AND e.person_id IS NULL
              AND src.iin IS NOT NULL;

            -- Match-key link: one employee per match_key (DISTINCT ON) and skip
            -- when an active employee already holds person_id (NOT EXISTS).
            -- Prevents uq_employees_person_active violations on re-backfill.
            UPDATE public.employees e
            SET
                person_id = p.person_id,
                enrollment_source = 'migration',
                operational_status = CASE
                    WHEN e.is_active THEN 'active'
                    ELSE 'terminated'
                END,
                enrolled_at = COALESCE(e.enrolled_at, now()),
                updated_at = now()
            FROM (
                SELECT DISTINCT ON (src.match_key)
                    src.employee_id,
                    src.match_key
                FROM (
                    SELECT
                        e2.employee_id,
                        CASE
                            WHEN iin.iin IS NOT NULL THEN 'iin:' || iin.iin
                            ELSE 'name:' || lower(
                                regexp_replace(trim(e2.full_name), '\\s+', ' ', 'g')
                            )
                        END AS match_key
                    FROM public.employees e2
                    LEFT JOIN LATERAL (
                        SELECT regexp_replace(ei.identity_value, '[^0-9]', '', 'g') AS iin
                        FROM public.employee_identities ei
                        WHERE ei.employee_id = e2.employee_id
                          AND ei.identity_type = 'IIN'
                          AND ei.valid_to IS NULL
                          AND length(regexp_replace(ei.identity_value, '[^0-9]', '', 'g')) = 12
                        ORDER BY ei.is_primary DESC NULLS LAST, ei.identity_id
                        LIMIT 1
                    ) iin ON TRUE
                    WHERE e2.person_id IS NULL
                ) src
                ORDER BY src.match_key, src.employee_id
            ) src
            JOIN public.persons p
              ON p.match_key = src.match_key
             AND p.person_status IN ('active', 'inactive')
            WHERE e.employee_id = src.employee_id
              AND e.person_id IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.employees e2
                  WHERE e2.person_id = p.person_id
                    AND e2.operational_status IN ('draft', 'active', 'suspended')
              );

            -- ---------------------------------------------------------------
            -- 3) Primary assignments from legacy employee snapshot
            -- ---------------------------------------------------------------
            IF v_fallback_org IS NOT NULL AND v_fallback_pos IS NOT NULL THEN
                INSERT INTO public.person_assignments (
                    person_id,
                    org_unit_id,
                    position_id,
                    department_id,
                    employment_type,
                    rate,
                    start_date,
                    end_date,
                    active_flag,
                    is_primary,
                    lifecycle_status,
                    assignment_key,
                    source
                )
                SELECT
                    e.person_id,
                    COALESCE(e.org_unit_id, v_fallback_org),
                    COALESCE(e.position_id, v_fallback_pos),
                    e.department_id,
                    'primary',
                    LEAST(GREATEST(COALESCE(e.employment_rate, 1.0), 0.01), 1.5),
                    COALESCE(e.date_from, CURRENT_DATE),
                    e.date_to,
                    CASE
                        WHEN e.is_active
                         AND COALESCE(e.date_from, CURRENT_DATE) <= CURRENT_DATE
                         AND (e.date_to IS NULL OR e.date_to >= CURRENT_DATE)
                        THEN TRUE
                        ELSE FALSE
                    END,
                    TRUE,
                    CASE
                        WHEN e.date_to IS NOT NULL AND e.date_to < CURRENT_DATE THEN 'closed'
                        WHEN e.is_active THEN 'active'
                        ELSE 'closed'
                    END,
                    lower(
                        COALESCE(e.org_unit_id, v_fallback_org)::text
                        || '|'
                        || COALESCE(e.position_id, v_fallback_pos)::text
                        || '|primary|'
                        || COALESCE(e.date_from, CURRENT_DATE)::text
                    ),
                    'migration'
                FROM public.employees e
                WHERE e.person_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.person_assignments pa
                      WHERE pa.person_id = e.person_id
                        AND pa.source = 'migration'
                        AND pa.is_primary = TRUE
                  );

                -- ---------------------------------------------------------------
                -- 4) Active operational links
                -- ---------------------------------------------------------------
                INSERT INTO public.employee_assignment_links (
                    employee_id,
                    assignment_id,
                    link_status,
                    enrolled_at,
                    enrolled_by_user_id,
                    unenrolled_at
                )
                SELECT
                    e.employee_id,
                    pa.assignment_id,
                    CASE
                        WHEN pa.active_flag AND e.is_active THEN 'active'
                        ELSE 'unenrolled'
                    END,
                    COALESCE(e.enrolled_at, now()),
                    v_actor,
                    CASE
                        WHEN pa.active_flag AND e.is_active THEN NULL
                        ELSE now()
                    END
                FROM public.employees e
                JOIN public.person_assignments pa
                  ON pa.person_id = e.person_id
                 AND pa.source = 'migration'
                 AND pa.is_primary = TRUE
                WHERE e.person_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM public.employee_assignment_links l
                      WHERE l.employee_id = e.employee_id
                        AND l.assignment_id = pa.assignment_id
                  );
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM public.employee_assignment_links l
        USING public.person_assignments pa
        WHERE l.assignment_id = pa.assignment_id
          AND pa.source = 'migration'
        """
    )
    op.execute(
        """
        DELETE FROM public.person_assignments
        WHERE source = 'migration'
        """
    )
    op.execute(
        """
        UPDATE public.employees
        SET
            person_id = NULL,
            enrolled_at = NULL,
            enrolled_by_user_id = NULL,
            operational_status = 'active',
            enrollment_source = 'migration',
            updated_at = NULL
        WHERE enrollment_source = 'migration'
        """
    )
    op.execute(
        """
        DELETE FROM public.persons p
        WHERE p.source = 'migration'
          AND NOT EXISTS (
              SELECT 1 FROM public.employees e WHERE e.person_id = p.person_id
          )
        """
    )
