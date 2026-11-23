"""Bind a real electronic hire application and freeze lesson criteria per attempt."""
from alembic import op

from app.learning.model import hire_applications

revision = "learning006"
down_revision = "learning005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE learning_attempts ADD COLUMN lesson_snapshot_json TEXT")
    hire_applications.create(op.get_bind())
    op.execute("""
        UPDATE learning_attempts AS attempt
        SET lesson_snapshot_json = json_build_object(
            'code', lesson.code, 'course_code', lesson.course_code,
            'title', lesson.title, 'target_role', lesson.target_role,
            'minutes', lesson.minutes, 'task', lesson.task,
            'instruction', lesson.instruction, 'guide_url', lesson.guide_url,
            'criteria', lesson.criteria_json::json,
            'required', lesson.criteria_json::json ->> lesson.required_index,
            'screenshots', lesson.screenshots_json::json,
            'state', lesson.state, 'expected_action', 'submitted',
            'function', 'Практическое занятие', 'skill', lesson.target_role,
            'number', 1
        )::text
        FROM learning_lessons AS lesson
        WHERE attempt.lesson_code = lesson.code
          AND attempt.lesson_snapshot_json IS NULL
    """)


def downgrade():
    raise RuntimeError("Hire links and attempt snapshots require a data-preserving rollback plan")
