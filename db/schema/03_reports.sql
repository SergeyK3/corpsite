-- Monthly Reports Schema
-- Reports are stored as separate entities with single approval cycle

-- Report types
CREATE TABLE report_types (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index for report_types
CREATE INDEX idx_report_types_is_active ON report_types(is_active);

-- Insert default report type
INSERT INTO report_types (name, description) VALUES
    ('monthly', 'Monthly progress and activity report');

-- Reports table with single approval cycle
CREATE TABLE reports (
    id BIGSERIAL PRIMARY KEY,
    report_type_id BIGINT NOT NULL REFERENCES report_types(id) ON DELETE RESTRICT,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    period_year INT NOT NULL,
    period_month INT NOT NULL, -- 1-12
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    approved_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    submitted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    updated_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_period_month CHECK (period_month >= 1 AND period_month <= 12),
    CONSTRAINT chk_approved_consistency CHECK (
        (is_approved = FALSE AND approved_by IS NULL AND approved_at IS NULL) OR
        (is_approved = TRUE AND approved_by IS NOT NULL AND approved_at IS NOT NULL)
    ),
    UNIQUE(user_id, period_year, period_month, report_type_id)
);

-- Indexes for reports
CREATE INDEX idx_reports_user_id ON reports(user_id);
CREATE INDEX idx_reports_report_type_id ON reports(report_type_id);
CREATE INDEX idx_reports_period ON reports(period_year, period_month);
CREATE INDEX idx_reports_is_approved ON reports(is_approved);
CREATE INDEX idx_reports_approved_by ON reports(approved_by);
CREATE INDEX idx_reports_approved_at ON reports(approved_at);
CREATE INDEX idx_reports_submitted_at ON reports(submitted_at);
CREATE INDEX idx_reports_created_at ON reports(created_at);

-- Report sections for structured content
CREATE TABLE report_sections (
    id BIGSERIAL PRIMARY KEY,
    report_id BIGINT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    section_title VARCHAR(500) NOT NULL,
    section_content TEXT NOT NULL,
    display_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for report_sections
CREATE INDEX idx_report_sections_report_id ON report_sections(report_id);
CREATE INDEX idx_report_sections_display_order ON report_sections(display_order);

-- Link reports to tasks
CREATE TABLE report_tasks (
    id BIGSERIAL PRIMARY KEY,
    report_id BIGINT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(report_id, task_id)
);

-- Indexes for report_tasks
CREATE INDEX idx_report_tasks_report_id ON report_tasks(report_id);
CREATE INDEX idx_report_tasks_task_id ON report_tasks(task_id);
