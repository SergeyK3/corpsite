-- QM pilot roles, employees, and users for VPS schema
-- (employees.employee_id = BIGINT identity; no text role codes as employee_id).
-- Safe to re-run (idempotent). Does NOT touch ADMIN or other non-QM users.
--
-- Schema note (alembic baseline / VPS after migrations):
--   public.users: user_id, full_name, google_login, role_id, unit_id, is_active,
--                 login, password_hash, ...
--   public.employees: employee_id BIGINT identity, full_name, department_id,
--                     position_id, org_unit_id, ...
--
-- Prerequisites:
--   1. scripts/pilot/org_structure_bootstrap.sql      (org_units incl. unit 44)
--   2. scripts/pilot/directory_prereq_bootstrap.sql   (departments 44, positions 64)
--
-- QM pilot bootstrap order:
--   1. org_structure_bootstrap.sql
--   2. directory_prereq_bootstrap.sql
--   3. qm_roles_users_bootstrap.sql                   <-- this file
--   4. scripts/pilot/qm_pilot_bootstrap.sql           (optional extra unit_id sync)
--   5. ./venv/bin/python scripts/reset_pilot_password.py --yes
--   6. (separate stage) import/create regular_tasks, then catch-up Preview
--
-- Pilot password (all QM logins): Corp2026!
-- Hash below matches db/init seed and scripts/reset_pilot_password.py
--
-- Example (review before apply on VPS):
--   docker exec -i corpsite-pg psql -U postgres -d corpsite < scripts/pilot/qm_roles_users_bootstrap.sql

BEGIN;

INSERT INTO public.roles (code, name)
VALUES
    ('QM_HEAD', 'Руководитель ОВЭиПД'),
    ('QM_HOSP', 'Госпитальный эксперт ОВЭиПД'),
    ('QM_AMB', 'Амбулаторный эксперт ОВЭиПД'),
    ('QM_COMPLAINT_REG', 'Эксперт по регистрации жалоб ОВЭиПД'),
    ('QM_COMPLAINT_PAT', 'Эксперт по улаживанию жалоб ОВЭиПД'),
    ('QM_TRAINING_EXPERT', 'Эксперт по внутреннему обучению и аттестации')
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name;

-- Pilot roster: role_code, full_name, login
CREATE TEMP TABLE _qm_pilot_src (
    role_code TEXT NOT NULL,
    full_name TEXT NOT NULL,
    login TEXT NOT NULL
) ON COMMIT DROP;

INSERT INTO _qm_pilot_src (role_code, full_name, login)
VALUES
    ('QM_HEAD', 'Масимов Акрамжан Бакримжанович', 'qm_head@corp.local'),
    ('QM_HOSP', 'Сейтказина Гулбахрам Тельмановна', 'qm_hosp@corp.local'),
    ('QM_AMB', 'Акильтаева Бакыт Сагитовна', 'qm_amb@corp.local'),
    ('QM_COMPLAINT_REG', 'Абдина Анар Канапияновна', 'qm_complaint_reg@corp.local'),
    ('QM_COMPLAINT_PAT', 'Мусабеков Калижан Амарханович', 'qm_complaint_pat@corp.local');

-- Employees: match by full_name (employee_id is numeric identity)
INSERT INTO public.employees (
    full_name,
    department_id,
    position_id,
    org_unit_id,
    employment_rate,
    is_active,
    date_from
)
SELECT
    s.full_name,
    44,
    64,
    44,
    1.00,
    TRUE,
    CURRENT_DATE
FROM _qm_pilot_src s
WHERE NOT EXISTS (
    SELECT 1
    FROM public.employees e
    WHERE e.full_name = s.full_name
);

UPDATE public.employees e
SET
    department_id = 44,
    position_id = 64,
    org_unit_id = 44,
    employment_rate = 1.00,
    is_active = TRUE,
    date_from = COALESCE(e.date_from, CURRENT_DATE)
FROM _qm_pilot_src s
WHERE e.full_name = s.full_name;

-- Users: only QM pilot logins (never ADMIN or other accounts)
INSERT INTO public.users (
    full_name,
    google_login,
    role_id,
    unit_id,
    is_active,
    login,
    password_hash
)
SELECT
    s.full_name,
    s.login,
    r.role_id,
    44,
    TRUE,
    s.login,
    'pbkdf2$200000$8bbD1gvF3FQIPihfHqkoEQ$XGM1IDfJ267XQJ4vBWeLDTA2_1UcZCoyqm-AeM_ljdU'
FROM _qm_pilot_src s
JOIN public.roles r ON r.code = s.role_code
WHERE NOT EXISTS (
    SELECT 1
    FROM public.users u
    WHERE lower(u.login) = lower(s.login)
);

UPDATE public.users u
SET
    full_name = s.full_name,
    google_login = s.login,
    role_id = r.role_id,
    unit_id = 44,
    is_active = TRUE,
    login = s.login,
    password_hash = 'pbkdf2$200000$8bbD1gvF3FQIPihfHqkoEQ$XGM1IDfJ267XQJ4vBWeLDTA2_1UcZCoyqm-AeM_ljdU'
FROM _qm_pilot_src s
JOIN public.roles r ON r.code = s.role_code
WHERE lower(u.login) = lower(s.login);

COMMIT;

-- Quick verify: QM roles
SELECT role_id, code, name
FROM public.roles
WHERE code IN (
    'QM_HEAD',
    'QM_HOSP',
    'QM_AMB',
    'QM_COMPLAINT_REG',
    'QM_COMPLAINT_PAT',
    'QM_TRAINING_EXPERT'
)
ORDER BY code;

-- Quick verify: QM users
SELECT u.user_id, u.login, u.unit_id, u.is_active, r.code AS role_code
FROM public.users u
JOIN public.roles r ON r.role_id = u.role_id
WHERE lower(u.login) IN (
    'qm_head@corp.local',
    'qm_hosp@corp.local',
    'qm_amb@corp.local',
    'qm_complaint_reg@corp.local',
    'qm_complaint_pat@corp.local'
)
ORDER BY u.login;

-- Quick verify: QM employees in pilot unit
SELECT e.employee_id, e.full_name, e.department_id, e.position_id, e.org_unit_id, e.is_active
FROM public.employees e
WHERE e.org_unit_id = 44
  AND e.full_name IN (
    'Масимов Акрамжан Бакримжанович',
    'Сейтказина Гулбахрам Тельмановна',
    'Акильтаева Бакыт Сагитовна',
    'Абдина Анар Канапияновна',
    'Мусабеков Калижан Амарханович'
  )
ORDER BY e.full_name;
