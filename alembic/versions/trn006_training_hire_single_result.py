"""Publish the single-result hire lesson while preserving version 2 attempts.

Revision ID: trn006
Revises: trn005
"""
from __future__ import annotations

import json
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "trn006"
down_revision = "trn005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    catalog = json.loads((Path(__file__).resolve().parents[2] / "app" / "training_catalog_v3.json").read_text(encoding="utf-8"))
    lesson = catalog["lesson"]
    conn = op.get_bind()
    course_id = conn.execute(text("""
        INSERT INTO public.training_course_versions(course_code, version, title)
        VALUES (:code, :version, :title) RETURNING course_version_id
    """), {"code": catalog["course_code"], "version": catalog["version"], "title": catalog["course_title"]}).scalar_one()
    lesson_id = conn.execute(text("""
        INSERT INTO public.training_lesson_versions
          (course_version_id, lesson_code, title, position_label, duration_minutes,
           source_data, expected_result, steps, rules)
        VALUES (:course, :code, :title, :position, :duration, :source, :expected,
                CAST(:steps AS jsonb), CAST(:rules AS jsonb))
        RETURNING lesson_version_id
    """), {"course": course_id, "code": lesson["code"], "title": lesson["title"],
           "position": lesson["position_label"], "duration": lesson["duration_minutes"],
           "source": lesson["source_data"], "expected": lesson["expected_result"],
           "steps": json.dumps(lesson["steps"], ensure_ascii=False),
           "rules": json.dumps(lesson["rules"], ensure_ascii=False)}).scalar_one()
    conn.execute(text("""
        INSERT INTO public.training_assignments
          (participant_user_id, lesson_version_id, required, instruction_url)
        SELECT a.participant_user_id, :lesson, a.required, a.instruction_url
        FROM public.training_assignments a
        JOIN public.training_lesson_versions l USING (lesson_version_id)
        JOIN public.training_course_versions c USING (course_version_id)
        WHERE c.course_code=:code AND c.version=2 AND l.lesson_code='skill_2'
    """), {"lesson": lesson_id, "code": catalog["course_code"]})


def downgrade() -> None:
    raise RuntimeError("Training history is immutable; trn006 cannot be downgraded.")
