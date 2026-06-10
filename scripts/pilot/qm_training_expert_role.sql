-- Idempotent seed: QM_TRAINING_EXPERT (обучение/аттестация, вне QM task FSM).
-- Safe to re-run. Does NOT create users or regular tasks.
--
-- Example (VPS):
--   docker exec -i corpsite-pg psql -U postgres -d corpsite < scripts/pilot/qm_training_expert_role.sql

BEGIN;

INSERT INTO public.roles (code, name)
VALUES (
    'QM_TRAINING_EXPERT',
    'Эксперт по внутреннему обучению и аттестации'
)
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name;

COMMIT;

SELECT role_id, code, name
FROM public.roles
WHERE code = 'QM_TRAINING_EXPERT';
