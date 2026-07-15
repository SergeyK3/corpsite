-- HR department allowed positions seed (post ADR-046 F1 migration).
-- Idempotent. Fail-fast. No catalog DDL. No employee mutations.
--
-- Prerequisites:
--   1. alembic upgrade head  (revision i9j0k1l2m3n4+)
--   2. scripts/pilot/hr_department_positions_bootstrap.sql  (global catalog)
--
-- Apply (example):
--   psql -U postgres -d corpsite -v ON_ERROR_STOP=1 \
--     -f scripts/pilot/hr_department_allowed_positions_seed.sql
--
-- Staffing units (informational — NOT stored):
--   Руководитель отдела кадров     : 1
--   Менеджер УЧР                  : 4
--   Менеджер                      : 4
--   секретарь-референт            : 3
--   Переводчик казахского языка   : 1

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.org_unit_allowed_positions') IS NULL THEN
        RAISE EXCEPTION
            'HR allowed-positions seed aborted: public.org_unit_allowed_positions missing — run Alembic migration i9j0k1l2m3n4 first';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION pg_temp._hr_seed_norm_name(p_name text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT lower(trim(p_name));
$$;

CREATE OR REPLACE FUNCTION pg_temp._hr_seed_resolve_hr_unit()
RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    v_by_code_count integer;
    v_unit_id bigint;
    v_name text;
    v_code text;
BEGIN
    SELECT COUNT(*)
    INTO v_by_code_count
    FROM public.org_units
    WHERE lower(trim(code)) = 'hr'
      AND COALESCE(is_active, TRUE) = TRUE;

    IF v_by_code_count = 1 THEN
        SELECT unit_id, name, code
        INTO v_unit_id, v_name, v_code
        FROM public.org_units
        WHERE lower(trim(code)) = 'hr'
          AND COALESCE(is_active, TRUE) = TRUE
        LIMIT 1;
        RAISE NOTICE 'HR org unit resolved by code=HR: unit_id=% name=%', v_unit_id, v_name;
        RETURN v_unit_id;
    END IF;

    IF v_by_code_count > 1 THEN
        RAISE EXCEPTION 'HR allowed-positions seed aborted: multiple active org_units with code=HR';
    END IF;

    SELECT unit_id, name, code
    INTO v_unit_id, v_name, v_code
    FROM public.org_units
    WHERE unit_id = 73
      AND COALESCE(is_active, TRUE) = TRUE
    LIMIT 1;

    IF v_unit_id IS NULL THEN
        RAISE EXCEPTION 'HR allowed-positions seed aborted: no active org_unit with code=HR and unit_id=73 fallback not found';
    END IF;

    IF lower(trim(COALESCE(v_code, ''))) <> 'hr'
       AND pg_temp._hr_seed_norm_name(COALESCE(v_name, '')) NOT LIKE '%кадр%' THEN
        RAISE EXCEPTION
            'HR allowed-positions seed aborted: unit_id=73 guard failed (code=%, name=%)',
            v_code, v_name;
    END IF;

    RAISE NOTICE 'HR org unit resolved by guarded fallback unit_id=73: name=% code=%', v_name, v_code;
    RETURN v_unit_id;
END;
$$;

CREATE OR REPLACE FUNCTION pg_temp._hr_seed_require_position(p_name text)
RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    v_id bigint;
BEGIN
    SELECT position_id
    INTO v_id
    FROM public.positions
    WHERE pg_temp._hr_seed_norm_name(name) = pg_temp._hr_seed_norm_name(p_name)
    LIMIT 1;

    IF v_id IS NULL THEN
        RAISE EXCEPTION
            'HR allowed-positions seed aborted: position "%" missing — run hr_department_positions_bootstrap.sql first',
            p_name;
    END IF;

    RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION pg_temp._hr_seed_upsert_link(
    p_org_unit_id bigint,
    p_position_id bigint,
    p_sort_order integer
)
RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    v_id bigint;
BEGIN
    SELECT org_unit_allowed_position_id
    INTO v_id
    FROM public.org_unit_allowed_positions
    WHERE org_unit_id = p_org_unit_id
      AND position_id = p_position_id
    LIMIT 1;

    IF v_id IS NOT NULL THEN
        UPDATE public.org_unit_allowed_positions
        SET sort_order = p_sort_order,
            is_active = TRUE,
            updated_at = now()
        WHERE org_unit_allowed_position_id = v_id;
        RETURN v_id;
    END IF;

    INSERT INTO public.org_unit_allowed_positions (
        org_unit_id,
        position_id,
        sort_order,
        is_active
    )
    VALUES (p_org_unit_id, p_position_id, p_sort_order, TRUE)
    RETURNING org_unit_allowed_position_id INTO v_id;

    RETURN v_id;
END;
$$;

DO $$
DECLARE
    v_hr_unit bigint;
    v_pos_head bigint;
    v_pos_mgr_uhr bigint;
    v_pos_mgr bigint;
    v_pos_sec bigint;
    v_pos_trans bigint;
BEGIN
    v_hr_unit := pg_temp._hr_seed_resolve_hr_unit();

    v_pos_head := pg_temp._hr_seed_require_position('Руководитель отдела кадров');
    v_pos_mgr_uhr := pg_temp._hr_seed_require_position('Менеджер УЧР');
    v_pos_mgr := pg_temp._hr_seed_require_position('Менеджер');
    v_pos_sec := pg_temp._hr_seed_require_position('секретарь-референт');
    v_pos_trans := pg_temp._hr_seed_require_position('Переводчик казахского языка');

    PERFORM pg_temp._hr_seed_upsert_link(v_hr_unit, v_pos_head, 10);
    PERFORM pg_temp._hr_seed_upsert_link(v_hr_unit, v_pos_mgr_uhr, 20);
    PERFORM pg_temp._hr_seed_upsert_link(v_hr_unit, v_pos_mgr, 30);
    PERFORM pg_temp._hr_seed_upsert_link(v_hr_unit, v_pos_sec, 40);
    PERFORM pg_temp._hr_seed_upsert_link(v_hr_unit, v_pos_trans, 50);

    RAISE NOTICE 'HR allowed-positions seed complete: unit_id=% links=5', v_hr_unit;
END;
$$;

COMMIT;

SELECT oap.org_unit_allowed_position_id,
       oap.org_unit_id,
       oap.position_id,
       p.name,
       oap.sort_order,
       oap.is_active
FROM public.org_unit_allowed_positions oap
JOIN public.positions p ON p.position_id = oap.position_id
WHERE oap.org_unit_id = (
    SELECT unit_id
    FROM public.org_units
    WHERE lower(trim(code)) = 'hr'
      AND COALESCE(is_active, TRUE) = TRUE
    LIMIT 1
)
   OR (
        NOT EXISTS (
            SELECT 1
            FROM public.org_units
            WHERE lower(trim(code)) = 'hr'
              AND COALESCE(is_active, TRUE) = TRUE
        )
        AND oap.org_unit_id = 73
    )
ORDER BY oap.sort_order, p.name;
