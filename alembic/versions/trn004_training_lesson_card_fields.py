"""Persist v1 source and expected-result text already present in guide seed.

Revision ID: trn004
Revises: trn003
"""
import json
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "trn004"
down_revision = "trn003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE public.training_lesson_versions
          ADD COLUMN source_data TEXT,
          ADD COLUMN expected_result TEXT;
    """)
    catalog_path = Path(__file__).resolve().parents[2] / "app" / "training_catalog_v1.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    conn = op.get_bind()
    for lesson in catalog["lessons"]:
        conn.execute(text("""
            UPDATE public.training_lesson_versions l
            SET source_data=:source, expected_result=:expected
            FROM public.training_course_versions c
            WHERE l.course_version_id=c.course_version_id
              AND c.course_code=:course AND c.version=:version
              AND l.lesson_code=:lesson
              AND l.source_data IS NULL AND l.expected_result IS NULL
        """), {"source": lesson["source_data"], "expected": lesson["expected_result"],
               "course": catalog["course_code"], "version": catalog["version"],
               "lesson": lesson["code"]})


def downgrade() -> None:
    op.execute("ALTER TABLE public.training_lesson_versions DROP COLUMN expected_result")
    op.execute("ALTER TABLE public.training_lesson_versions DROP COLUMN source_data")
