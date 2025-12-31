-- Tasks Schema
-- Tasks are assigned by role with execution-only statuses

-- Task statuses (execution-only, not approval)
CREATE TABLE task_statuses (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index for task_statuses
CREATE INDEX idx_task_statuses_is_active ON task_statuses(is_active);
CREATE INDEX idx_task_statuses_display_order ON task_statuses(display_order);

-- Insert default task statuses (execution-only)
INSERT INTO task_statuses (name, description, display_order) VALUES
    ('pending', 'Task has been created and is waiting to be started', 10),
    ('in_progress', 'Task is currently being worked on', 20),
    ('on_hold', 'Task is temporarily paused', 30),
    ('completed', 'Task execution has been completed', 40),
    ('cancelled', 'Task has been cancelled and will not be completed', 50);

-- Tasks table with role-based assignment
CREATE TABLE tasks (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    assigned_to_role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    assigned_to_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    status_id BIGINT NOT NULL REFERENCES task_statuses(id) ON DELETE RESTRICT,
    due_date TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    priority INT NOT NULL DEFAULT 5, -- 1 (highest) to 10 (lowest)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    updated_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_priority CHECK (priority >= 1 AND priority <= 10)
);

-- Indexes for tasks
CREATE INDEX idx_tasks_assigned_to_role ON tasks(assigned_to_role_id);
CREATE INDEX idx_tasks_assigned_to_user ON tasks(assigned_to_user_id);
CREATE INDEX idx_tasks_status ON tasks(status_id);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_created_by ON tasks(created_by);

-- Task comments for additional tracking
CREATE TABLE task_comments (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    comment_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by BIGINT REFERENCES users(id) ON DELETE SET NULL
);

-- Index for task_comments
CREATE INDEX idx_task_comments_task_id ON task_comments(task_id);
CREATE INDEX idx_task_comments_created_at ON task_comments(created_at);
