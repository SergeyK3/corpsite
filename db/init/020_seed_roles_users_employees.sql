-- =========================================================
-- SEED: ROLES
-- =========================================================

INSERT INTO public.roles (code, name)
VALUES
    ('DIRECTOR','Директор'),
    ('DEP_MED','Зам по лечебной работе'),
    ('DEP_OUTPATIENT_AUDIT','Зам по диспансеру и внутр экспертизе'),
    ('DEP_ADMIN','Зам по адм вопросам'),
    ('DEP_STRATEGY','Зам по стратегии'),
    ('STAT_HEAD','Руководитель отдела статистики'),
    ('STAT_HEAD_DEPUTY','зам рук-ля отдела статистики'),
    ('STAT_EROB_INPUT','статистик по вводу в ЭРОБ'),
    ('STAT_EROB_OUTPUT','статистик по выводу из ЭРОБ'),
    ('STAT_EROB_ANALYTICS','Аналитик ЭРОБ'),
    ('QM_HEAD','Руководитель ОВЭиПД'),
    ('QM_HOSP','Госпитальный эксперт ОВЭиПД'),
    ('QM_AMB','Амбулаторный эксперт ОВЭиПД'),
    ('QM_COMPLAINT_REG','Эксперт по регистрации жалоб ОВЭиПД'),
    ('QM_COMPLAINT_PAT','Эксперт по улаживанию жалоб ОВЭиПД'),
    ('HR_HEAD','Руководитель отдела кадров'),
    ('ACC_HEAD','Главный бухгалтер'),
    ('ECON_HEAD','Руководитель'),
    ('ECON_1','экономист1'),
    ('ECON_2','экономист2'),
    ('ECON_3','экономист3')
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name;


-- =========================================================
-- SEED: EMPLOYEES
-- =========================================================

INSERT INTO public.employees (
  employee_id,
  full_name,
  department_id,
  position_id,
  org_unit_id,
  employment_rate,
  is_active,
  date_from
)
VALUES
  ('DIRECTOR','Тулеутаев Мухтар Есенжанович',44,64,44,1.00,true,CURRENT_DATE),
  ('DEP_MED','Оразбеков Бактыбай Сеиткадырович',44,64,44,1.00,true,CURRENT_DATE),
  ('DEP_OUTPATIENT_AUDIT','Козгамбаева Ляззат Таласпаевна',44,64,44,1.00,true,CURRENT_DATE),
  ('DEP_ADMIN','Нурбеков Бахдат Байтлевич',44,64,44,1.00,true,CURRENT_DATE),
  ('DEP_STRATEGY','Курманов Талгат Аманжолович',44,64,44,1.00,true,CURRENT_DATE),
  ('STAT_HEAD','Мустафина Багдаш Каиртаевна',44,64,44,1.00,true,CURRENT_DATE),
  ('STAT_HEAD_DEPUTY','Досмаганбетова Айжан Бекбосыновна',44,64,44,1.00,true,CURRENT_DATE),
  ('STAT_EROB_INPUT','Темиргалиева Жумагуль Амангельдиновна',44,64,44,1.00,true,CURRENT_DATE),
  ('STAT_EROB_OUTPUT','Абитаева Айгуль Савеловна',44,64,44,1.00,true,CURRENT_DATE),
  ('STAT_EROB_ANALYTICS','Кумысбаев Мирас Еркебаевич',44,64,44,1.00,true,CURRENT_DATE),
  ('QM_HEAD','Масимов Акрамжан Бакримжанович',44,64,44,1.00,true,CURRENT_DATE),
  ('QM_HOSP','Сейтказина Гулбахрам Тельмановна',44,64,44,1.00,true,CURRENT_DATE),
  ('QM_AMB','Акильтаева Бакыт Сагитовна',44,64,44,1.00,true,CURRENT_DATE),
  ('QM_COMPLAINT_REG','Абдина Анар Канапияновна',44,64,44,1.00,true,CURRENT_DATE),
  ('QM_COMPLAINT_PAT','Мусабеков Калижан Амарханович',44,64,44,1.00,true,CURRENT_DATE),
  ('HR_HEAD','Өсерова Айсара Асанқызы',44,64,44,1.00,true,CURRENT_DATE),
  ('ACC_HEAD','Жортабайқызы Аягүл',44,64,44,1.00,true,CURRENT_DATE),
  ('ECON_HEAD','Кутжанова Айгерим Жанибеккызы',44,64,44,1.00,true,CURRENT_DATE),
  ('ECON_1','Қабиденова Бибигуль Мырзамсеитовна',44,64,44,1.00,true,CURRENT_DATE),
  ('ECON_2','Мустафина Елизавета Марсовна',44,64,44,1.00,true,CURRENT_DATE),
  ('ECON_3','Сергазина Нургуль Газизовна',44,64,44,1.00,true,CURRENT_DATE)
ON CONFLICT (employee_id) DO UPDATE
SET full_name = EXCLUDED.full_name,
    is_active = true;


-- =========================================================
-- SEED: USERS
-- Пароль для всех: Corp2026!
-- =========================================================

WITH src AS (
  SELECT
    e.full_name,
    lower(e.employee_id) || '@corp.local' AS login,
    lower(e.employee_id) || '@corp.local' AS google_login,
    r.role_id
  FROM public.employees e
  JOIN public.roles r ON r.code = e.employee_id
  WHERE e.employee_id IN (
    'DIRECTOR','DEP_MED','DEP_OUTPATIENT_AUDIT','DEP_ADMIN','DEP_STRATEGY',
    'STAT_HEAD','STAT_HEAD_DEPUTY','STAT_EROB_INPUT','STAT_EROB_OUTPUT','STAT_EROB_ANALYTICS',
    'QM_HEAD','QM_HOSP','QM_AMB','QM_COMPLAINT_REG','QM_COMPLAINT_PAT',
    'HR_HEAD','ACC_HEAD','ECON_HEAD','ECON_1','ECON_2','ECON_3'
  )
)
INSERT INTO public.users (
  full_name,
  google_login,
  role_id,
  is_active,
  login,
  password_hash
)
SELECT
  s.full_name,
  s.google_login,
  s.role_id,
  TRUE,
  s.login,
  'pbkdf2$200000$8bbD1gvF3FQIPihfHqkoEQ$XGM1IDfJ267XQJ4vBWeLDTA2_1UcZCoyqm-AeM_ljdU'
FROM src s
ON CONFLICT (google_login) DO UPDATE
SET
  full_name = EXCLUDED.full_name,
  role_id = EXCLUDED.role_id,
  login = EXCLUDED.login,
  password_hash = EXCLUDED.password_hash,
  is_active = TRUE;
