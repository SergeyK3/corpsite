-- Test-only bootstrap for the current PostgreSQL schema.
-- The historical db/init seed targets the pre-ADR employee_id text schema and
-- must not be used by ADR-065 integration tests.
INSERT INTO public.roles (code, name)
VALUES ('HR_HEAD', 'ADR-065 test HR operator')
ON CONFLICT (code) DO NOTHING;

INSERT INTO public.roles (code, name)
VALUES ('ADMIN', 'ADR-065 test administrator')
ON CONFLICT (code) DO NOTHING;

INSERT INTO public.users (full_name, role_id, is_active, login, google_login)
SELECT 'ADR-065 test operator', r.role_id, TRUE,
       'adr065-test-operator', 'adr065-test-operator'
  FROM public.roles r
 WHERE r.code = 'HR_HEAD'
   AND NOT EXISTS (SELECT 1 FROM public.users WHERE login = 'adr065-test-operator');
