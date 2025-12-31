-- =========================================================
-- 0) Базовые типы/перечисления
-- =========================================================

-- Линия назначения (матрица)
DO $$ BEGIN
  CREATE TYPE assignment_scope_t AS ENUM ('admin', 'functional');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Тип периода (пока только MONTH, WEEK на будущее)
DO $$ BEGIN
  CREATE TYPE period_kind_t AS ENUM ('MONTH', 'WEEK');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Канал уведомлений (бот позже)
DO $$ BEGIN
  CREATE TYPE notif_channel_t AS ENUM ('telegram', 'email', 'sms', 'system');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Политика назначения (по умолчанию CHAIN_ALLOWED, DIRECT_ONLY опционально)
DO $$ BEGIN
  CREATE TYPE assign_policy_t AS ENUM ('DIRECT_ONLY', 'CHAIN_ALLOWED');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- =========================================================
-- 1) Справочники: роли, подразделения, статусы
-- =========================================================

CREATE TABLE IF NOT EXISTS roles (
  role_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name           TEXT NOT NULL,
  code           TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS org_units (
  unit_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name           TEXT NOT NULL,
  code           TEXT UNIQUE,
  parent_unit_id BIGINT NULL REFERENCES org_units(unit_id) ON DELETE SET NULL,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE
);

-- Статусы задач (русские значения, как вы утвердили)
CREATE TABLE IF NOT EXISTS task_statuses (
  status_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code        TEXT NOT NULL UNIQUE,   -- IN_PROGRESS, WAITING_REPORT, WAITING_APPROVAL, DONE, ARCHIVED
  name_ru     TEXT NOT NULL,          -- "В работе", ...
  is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
  sort_order  INT NOT NULL DEFAULT 0
);

-- =========================================================
-- 2) Пользователи и матрица подчиненности
-- =========================================================

CREATE TABLE IF NOT EXISTS users (
  user_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  full_name     TEXT NOT NULL,
  google_login  TEXT NOT NULL UNIQUE,          -- SSO login
  phone         TEXT NULL,
  telegram_id   TEXT NULL,                     -- Telegram ID
  role_id       BIGINT NOT NULL REFERENCES roles(role_id),
  unit_id       BIGINT NULL REFERENCES org_units(unit_id) ON DELETE SET NULL,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Матричная связь: сотрудник -> руководитель (admin / functional)
CREATE TABLE IF NOT EXISTS user_supervisors (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id        BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  supervisor_id  BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  scope          assignment_scope_t NOT NULL,
  valid_from     TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to       TIMESTAMPTZ NULL,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_user_supervisor UNIQUE (user_id, supervisor_id, scope, valid_from),
  CONSTRAINT chk_not_self CHECK (user_id <> supervisor_id)
);

CREATE INDEX IF NOT EXISTS ix_user_supervisors_user ON user_supervisors(user_id, scope) WHERE is_active;
CREATE INDEX IF NOT EXISTS ix_user_supervisors_supervisor ON user_supervisors(supervisor_id, scope) WHERE is_active;

-- =========================================================
-- 3) Периоды отчетности (месяцы)
-- =========================================================

CREATE TABLE IF NOT EXISTS reporting_periods (
  period_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind         period_kind_t NOT NULL DEFAULT 'MONTH',
  date_start   DATE NOT NULL,
  date_end     DATE NOT NULL,
  label        TEXT NOT NULL, -- например "2025-02"
  is_closed    BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT chk_period_dates CHECK (date_start <= date_end),
  CONSTRAINT uq_period UNIQUE (kind, date_start, date_end)
);

CREATE INDEX IF NOT EXISTS ix_reporting_periods_kind_start ON reporting_periods(kind, date_start DESC);

-- =========================================================
-- 4) Регулярные задачи (источник генерации)
-- =========================================================

-- Это ваша вкладка "Регулярные задачи":
-- initiator_role_id ~ "Исполнитель" (кто контролирует/инициирует)
-- target_role_id    ~ "Подотчетный" (кому формируется задача/отчетность)
CREATE TABLE IF NOT EXISTS regular_tasks (
  regular_task_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  title              TEXT NOT NULL,
  periodicity        period_kind_t NOT NULL DEFAULT 'MONTH', -- для MVP используем MONTH
  initiator_role_id  BIGINT NOT NULL REFERENCES roles(role_id),
  target_role_id     BIGINT NOT NULL REFERENCES roles(role_id),
  assignment_scope   assignment_scope_t NOT NULL DEFAULT 'admin',
  template_link      TEXT NULL,
  order_link         TEXT NULL,
  is_active          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS ix_regular_tasks_active ON regular_tasks(is_active) WHERE is_active;

-- =========================================================
-- 5) Задачи (MVP: назначаются по роли + период)
-- =========================================================

CREATE TABLE IF NOT EXISTS tasks (
  task_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  period_id          BIGINT NOT NULL REFERENCES reporting_periods(period_id) ON DELETE RESTRICT,
  regular_task_id    BIGINT NULL REFERENCES regular_tasks(regular_task_id) ON DELETE SET NULL,

  title              TEXT NOT NULL,
  description        TEXT NULL,

  -- Кто инициировал/контролирует: в MVP фиксируем конкретного пользователя (директор/зам/зав.)
  initiator_user_id  BIGINT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,

  -- Исполнитель определяется РОЛЬЮ (как вы утвердили)
  executor_role_id   BIGINT NOT NULL REFERENCES roles(role_id) ON DELETE RESTRICT,

  assignment_scope   assignment_scope_t NOT NULL DEFAULT 'admin',

  status_id          BIGINT NOT NULL REFERENCES task_statuses(status_id),

  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- простая защита от дублей при генерации в рамках периода
  CONSTRAINT uq_task_period_regular_role UNIQUE (period_id, regular_task_id, executor_role_id, assignment_scope)
);

CREATE INDEX IF NOT EXISTS ix_tasks_period ON tasks(period_id, status_id);
CREATE INDEX IF NOT EXISTS ix_tasks_initiator ON tasks(initiator_user_id);
CREATE INDEX IF NOT EXISTS ix_tasks_executor_role ON tasks(executor_role_id);

-- Автообновление updated_at
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_tasks_updated_at ON tasks;
CREATE TRIGGER set_tasks_updated_at
BEFORE UPDATE ON tasks
FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();

-- =========================================================
-- 6) Отчеты (TaskReports) — отдельная сущность
-- =========================================================

CREATE TABLE IF NOT EXISTS task_reports (
  report_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  task_id          BIGINT NOT NULL UNIQUE REFERENCES tasks(task_id) ON DELETE CASCADE,

  report_link      TEXT NOT NULL,                 -- ссылка на файл/папку/документ
  submitted_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  submitted_by     BIGINT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,

  -- утверждение (один цикл): при возврате очищаем approved_*
  approved_at      TIMESTAMPTZ NULL,
  approved_by      BIGINT NULL REFERENCES users(user_id) ON DELETE RESTRICT,

  current_comment  TEXT NULL                      -- одно поле, перезаписываемое
);

CREATE INDEX IF NOT EXISTS ix_task_reports_submitted_at ON task_reports(submitted_at DESC);
CREATE INDEX IF NOT EXISTS ix_task_reports_approved_at ON task_reports(approved_at DESC);

-- =========================================================
-- 7) Уведомления (лог) — бот подключите позже
-- =========================================================

CREATE TABLE IF NOT EXISTS notifications (
  notification_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  channel           notif_channel_t NOT NULL DEFAULT 'system',
  recipient_user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  related_task_id   BIGINT NULL REFERENCES tasks(task_id) ON DELETE SET NULL,
  payload           JSONB NOT NULL,          -- текст/метаданные
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at           TIMESTAMPTZ NULL,
  status            TEXT NOT NULL DEFAULT 'CREATED' -- CREATED/SENT/FAILED
);

CREATE INDEX IF NOT EXISTS ix_notifications_recipient ON notifications(recipient_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_notifications_status ON notifications(status, created_at DESC);

-- =========================================================
-- 8) Аудит (кто/что/когда/до/после)
-- =========================================================

CREATE TABLE IF NOT EXISTS audit_log (
  audit_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  happened_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor_user_id BIGINT NULL REFERENCES users(user_id) ON DELETE SET NULL,

  entity        TEXT NOT NULL,     -- 'tasks', 'task_reports', etc
  entity_id     BIGINT NOT NULL,
  action        TEXT NOT NULL,     -- CREATE/UPDATE/CHANGE_STATUS/SUBMIT_REPORT/APPROVE_REPORT/RETURN_REPORT...

  before_data   JSONB NULL,
  after_data    JSONB NULL
);

CREATE INDEX IF NOT EXISTS ix_audit_entity ON audit_log(entity, entity_id, happened_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_actor ON audit_log(actor_user_id, happened_at DESC);

-- =========================================================
-- 9) Минимальные правила консистентности (MVP)
-- DONE разрешён только если отчет утвержден (approved_at not null).
-- Реализуем как CHECK через подзапрос нельзя; делаем триггером.
-- =========================================================

CREATE OR REPLACE FUNCTION trg_tasks_done_requires_approved_report()
RETURNS trigger AS $$
DECLARE
  v_approved_at TIMESTAMPTZ;
  v_done_status_id BIGINT;
BEGIN
  SELECT status_id INTO v_done_status_id FROM task_statuses WHERE code = 'DONE';

  IF NEW.status_id = v_done_status_id THEN
    SELECT approved_at INTO v_approved_at
    FROM task_reports
    WHERE task_id = NEW.task_id;

    IF v_approved_at IS NULL THEN
      RAISE EXCEPTION 'Cannot set DONE: task % has no approved report', NEW.task_id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tasks_done_requires_approved_report ON tasks;
CREATE TRIGGER tasks_done_requires_approved_report
BEFORE UPDATE OF status_id ON tasks
FOR EACH ROW EXECUTE FUNCTION trg_tasks_done_requires_approved_report();

-- =========================================================
-- 10) Генерация задач на месяц из regular_tasks (MVP)
-- =========================================================

CREATE OR REPLACE FUNCTION generate_monthly_tasks(p_period_id BIGINT, p_initiator_user_id BIGINT)
RETURNS BIGINT AS $$
DECLARE
  v_count BIGINT;
  v_waiting_report BIGINT;
BEGIN
  SELECT status_id INTO v_waiting_report FROM task_statuses WHERE code = 'WAITING_REPORT';

  INSERT INTO tasks (
    period_id, regular_task_id, title, description,
    initiator_user_id, executor_role_id, assignment_scope, status_id
  )
  SELECT
    p_period_id,
    rt.regular_task_id,
    rt.title,
    NULL,
    p_initiator_user_id,
    rt.target_role_id,
    rt.assignment_scope,
    v_waiting_report
  FROM regular_tasks rt
  WHERE rt.is_active = TRUE
    AND rt.periodicity = 'MONTH'
  ON CONFLICT (period_id, regular_task_id, executor_role_id, assignment_scope) DO NOTHING;

  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END;
$$ LANGUAGE plpgsql;
