-- HR department official positions bootstrap (Stage 1 — global catalog only).
-- Idempotent. Fail-fast on catalog conflicts. No schema DDL. No employee mutations.
--
-- Scope (this script):
--   Create or reuse five official titles in public.positions (one row per name).
--
-- Out of scope (requires ADR-046 implementation — Alembic + API):
--   public.org_unit_allowed_positions links (department allowed-positions list).
--   Staffing headcount persistence (informational only — see comments below).
--   Operational Role registry (ADR-055).
--
-- Staffing units (informational — NOT stored in DB):
--   Руководитель отдела кадров     : 1
--   Менеджер УЧР                  : 4
--   Менеджер                      : 4
--   секретарь-референт            : 3
--   Переводчик казахского языка   : 1
--
-- Pilot org unit convention (verification only — not mutated):
--   code='HR', typical unit_id=73 (ACCESS-001).
--
-- Apply (example):
--   psql -U postgres -d corpsite -v ON_ERROR_STOP=1 \
--     -f scripts/pilot/hr_department_positions_bootstrap.sql
--
-- Verify catalog:
--   SELECT position_id, name, category
--   FROM public.positions
--   WHERE lower(trim(name)) IN (
--     lower('Руководитель отдела кадров'),
--     lower('Менеджер УЧР'),
--     lower('Менеджер'),
--     lower('секретарь-референт'),
--     lower('Переводчик казахского языка')
--   )
--   ORDER BY name;

BEGIN;

-- Fail-fast: ADR-046 junction table must NOT be created by pilot scripts.
-- If missing, allowed-positions links are deferred to ADR-046 F1 (Alembic migration).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'positions'
          AND column_name = 'category'
    ) THEN
        RAISE EXCEPTION 'HR bootstrap aborted: public.positions.category column missing (run Alembic migrations first)';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION pg_temp._hr_norm_name(p_name text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT lower(trim(p_name));
$$;

CREATE OR REPLACE FUNCTION pg_temp._hr_resolve_or_create_position(
    p_name text,
    p_category text,
    p_expected_position_id bigint DEFAULT NULL
)
RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    v_norm text := pg_temp._hr_norm_name(p_name);
    v_id bigint;
    v_existing_name text;
BEGIN
    IF v_norm = '' THEN
        RAISE EXCEPTION 'HR bootstrap aborted: empty position name';
    END IF;

    SELECT position_id, name
    INTO v_id, v_existing_name
    FROM public.positions
    WHERE pg_temp._hr_norm_name(name) = v_norm
    LIMIT 1;

    IF v_id IS NOT NULL THEN
        RETURN v_id;
    END IF;

    IF p_expected_position_id IS NOT NULL THEN
        SELECT name
        INTO v_existing_name
        FROM public.positions
        WHERE position_id = p_expected_position_id;

        IF FOUND THEN
            IF pg_temp._hr_norm_name(v_existing_name) <> v_norm THEN
                RAISE EXCEPTION
                    'HR bootstrap aborted: position_id=% already exists as "%", expected "%"',
                    p_expected_position_id, v_existing_name, p_name;
            END IF;
            RETURN p_expected_position_id;
        END IF;

        INSERT INTO public.positions (position_id, name, category)
        OVERRIDING SYSTEM VALUE
        VALUES (p_expected_position_id, p_name, p_category);
        RETURN p_expected_position_id;
    END IF;

    INSERT INTO public.positions (name, category)
    VALUES (p_name, p_category)
    RETURNING position_id INTO v_id;

    RETURN v_id;
END;
$$;

DO $$
DECLARE
    v_pos_head bigint;
    v_pos_mgr_uhr bigint;
    v_pos_mgr bigint;
    v_pos_sec bigint;
    v_pos_trans bigint;
    v_hr_by_code_count integer;
    v_hr_unit_id bigint;
BEGIN
    v_pos_head := pg_temp._hr_resolve_or_create_position(
        'Руководитель отдела кадров', 'leaders', 86
    );
    v_pos_mgr_uhr := pg_temp._hr_resolve_or_create_position('Менеджер УЧР', 'admin');
    v_pos_mgr := pg_temp._hr_resolve_or_create_position('Менеджер', 'admin');
    v_pos_sec := pg_temp._hr_resolve_or_create_position('секретарь-референт', 'admin');
    v_pos_trans := pg_temp._hr_resolve_or_create_position('Переводчик казахского языка', 'admin');

    RAISE NOTICE 'HR bootstrap catalog: head=% mgr_uhr=% mgr=% sec=% trans=%',
        v_pos_head, v_pos_mgr_uhr, v_pos_mgr, v_pos_sec, v_pos_trans;

    -- Pilot environment check (informational — does not mutate org structure).
    IF to_regclass('public.org_units') IS NOT NULL THEN
        SELECT COUNT(*)
        INTO v_hr_by_code_count
        FROM public.org_units
        WHERE lower(trim(code)) = 'hr'
          AND COALESCE(is_active, TRUE) = TRUE;

        IF v_hr_by_code_count = 1 THEN
            SELECT unit_id INTO v_hr_unit_id
            FROM public.org_units
            WHERE lower(trim(code)) = 'hr'
              AND COALESCE(is_active, TRUE) = TRUE
            LIMIT 1;
            RAISE NOTICE 'HR pilot org unit resolved: unit_id=% (code=HR)', v_hr_unit_id;
        ELSIF v_hr_by_code_count > 1 THEN
            RAISE WARNING 'HR pilot check: multiple active org_units with code=HR — resolve before ADR-046 allowed-positions seed';
        ELSE
            RAISE WARNING 'HR pilot check: no active org_unit with code=HR — allowed-positions seed deferred until org structure is ready';
        END IF;
    END IF;

    IF to_regclass('public.org_unit_allowed_positions') IS NULL THEN
        RAISE NOTICE 'org_unit_allowed_positions table absent — department allowed-positions links require ADR-046 F1 (Alembic migration) before seeding';
    END IF;
END;
$$;

SELECT setval(
    pg_get_serial_sequence('public.positions', 'position_id'),
    GREATEST((SELECT COALESCE(MAX(position_id), 1) FROM public.positions), 1)
);

COMMIT;

-- Post-check: one catalog row per official title.
SELECT position_id, name, category
FROM public.positions
WHERE lower(trim(name)) IN (
    lower(trim('Руководитель отдела кадров')),
    lower(trim('Менеджер УЧР')),
    lower(trim('Менеджер')),
    lower(trim('секретарь-референт')),
    lower(trim('Переводчик казахского языка'))
)
ORDER BY name;
