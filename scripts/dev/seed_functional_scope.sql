-- scripts/dev/seed_functional_scope.sql
-- Dev/E2E seed: связь supervisor↔executor для scope=functional
-- Идемпотентно: повторный запуск не создаёт дублей.
-- Схема: public.user_supervisors(user_id, supervisor_id, scope, is_active, valid_from, valid_to)

BEGIN;

-- Executor(user_id)=5 -> Supervisor(supervisor_id)=34 (functional scope)
INSERT INTO public.user_supervisors (user_id, supervisor_id, scope, is_active)
SELECT 5, 34, 'functional'::assignment_scope_t, true
WHERE NOT EXISTS (
  SELECT 1
  FROM public.user_supervisors
  WHERE user_id = 5
    AND supervisor_id = 34
    AND scope = 'functional'::assignment_scope_t
    AND is_active = true
);

COMMIT;
