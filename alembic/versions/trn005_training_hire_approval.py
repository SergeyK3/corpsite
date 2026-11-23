"""Bind a training approval attempt to its task and publish lesson version 2.

Revision ID: trn005
Revises: trn004
"""
from __future__ import annotations

import json
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "trn005"
down_revision = "trn004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.training_attempt_objects
          ADD COLUMN task_id BIGINT REFERENCES public.tasks(task_id) ON DELETE RESTRICT;
        CREATE UNIQUE INDEX uq_training_attempt_object_application
          ON public.training_attempt_objects(application_id) WHERE application_id IS NOT NULL;
        CREATE UNIQUE INDEX uq_training_attempt_object_order
          ON public.training_attempt_objects(order_id) WHERE order_id IS NOT NULL;
        CREATE UNIQUE INDEX uq_training_attempt_object_task
          ON public.training_attempt_objects(task_id) WHERE task_id IS NOT NULL;
    """)
    catalog = json.loads((Path(__file__).resolve().parents[2] / "app" / "training_catalog_v2.json").read_text(encoding="utf-8"))
    conn = op.get_bind()
    course_id = conn.execute(text("""
        INSERT INTO public.training_course_versions(course_code, version, title)
        VALUES (:code, :version, :title) RETURNING course_version_id
    """), {"code": catalog["course_code"], "version": catalog["version"],
           "title": catalog["course_title"]}).scalar_one()
    lesson = catalog["lesson"]
    conn.execute(text("""
        INSERT INTO public.training_lesson_versions
          (course_version_id, lesson_code, title, position_label, duration_minutes,
           source_data, expected_result, steps, rules)
        VALUES (:course, :code, :title, :position, :duration, :source, :expected,
                CAST(:steps AS jsonb), CAST(:rules AS jsonb))
    """), {"course": course_id, "code": lesson["code"], "title": lesson["title"],
           "position": lesson["position_label"], "duration": lesson["duration_minutes"],
           "source": lesson["source_data"], "expected": lesson["expected_result"],
           "steps": json.dumps(lesson["steps"], ensure_ascii=False),
           "rules": json.dumps(lesson["rules"], ensure_ascii=False)})


def downgrade() -> None:
    op.execute("DELETE FROM public.training_lesson_versions WHERE course_version_id IN (SELECT course_version_id FROM public.training_course_versions WHERE course_code='application_administration' AND version=2)")
    op.execute("DELETE FROM public.training_course_versions WHERE course_code='application_administration' AND version=2")
    op.execute("DROP INDEX public.uq_training_attempt_object_task")
    op.execute("DROP INDEX public.uq_training_attempt_object_order")
    op.execute("DROP INDEX public.uq_training_attempt_object_application")
    op.execute("ALTER TABLE public.training_attempt_objects DROP COLUMN task_id")
