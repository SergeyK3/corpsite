-- =========================================================
-- DDL v1: regular_tasks + task_audit_log
-- Project: Corpsite
-- =========================================================

-- ---------- regular_tasks (если таблица уже есть — пропустите CREATE)
CREATE TABLE IF NOT EXISTS regular_tasks (
    regular_task_id   SERIAL PRIMARY KEY,
    code              TEXT UNIQUE,
    title             TEXT NOT NULL,
    description       TEXT,
    executor_role_id  INTEGER NOT NULL,
    period_kind       period_kind_t NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- tasks (изменения, которые вы вносили)
ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS description TEXT;

-- ---------- audit log for tasks
CREATE TABLE IF NOT EXISTS task_audit_log (
    audit_id        BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    task_id         INTEGER NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    actor_user_id   INTEGER NOT NULL REFERENCES users(user_id),
    action          TEXT NOT NULL, -- CREATE | PATCH | ARCHIVE
    fields_changed  JSONB
);

-- ---------- индексы для audit log
CREATE INDEX IF NOT EXISTS ix_task_audit_log_task_id
    ON task_audit_log(task_id);

CREATE INDEX IF NOT EXISTS ix_task_audit_log_created_at
    ON task_audit_log(created_at);

-- =========================================================
-- END
-- =========================================================
