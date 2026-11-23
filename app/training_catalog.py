"""Immutable v1 catalog imported from the local v0.6 testing guide."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection


CATALOG_V1 = Path(__file__).with_name("training_catalog_v1.json")


def seed_catalog_v1(conn: Connection) -> int:
    catalog = json.loads(CATALOG_V1.read_text(encoding="utf-8"))
    row = conn.execute(text("""
        INSERT INTO public.training_course_versions(course_code, version, title)
        VALUES (:code, :version, :title)
        ON CONFLICT (course_code, version) DO NOTHING
        RETURNING course_version_id
    """), {"code": catalog["course_code"], "version": catalog["version"],
           "title": catalog["course_title"]}).scalar_one_or_none()
    if row is None:
        existing = conn.execute(text("""
            SELECT course_version_id, title FROM public.training_course_versions
            WHERE course_code=:code AND version=:version
        """), {"code": catalog["course_code"], "version": catalog["version"]}).mappings().one()
        if existing["title"] != catalog["course_title"]:
            raise RuntimeError("Catalog v1 differs from an existing frozen version")
        course_id = int(existing["course_version_id"])
    else:
        course_id = int(row)
    for lesson in catalog["lessons"]:
        values = {
            "course": course_id, "code": lesson["code"], "title": lesson["title"],
            "position": lesson["position_label"], "duration": lesson["duration_minutes"],
            "source": lesson["source_data"], "expected": lesson["expected_result"],
            "steps": json.dumps(lesson["steps"], ensure_ascii=False),
            "rules": json.dumps(lesson["rules"], ensure_ascii=False),
        }
        inserted = conn.execute(text("""
            INSERT INTO public.training_lesson_versions
                (course_version_id, lesson_code, title, position_label, duration_minutes,
                 source_data, expected_result, steps, rules)
            VALUES (:course, :code, :title, :position, :duration,
                    :source, :expected, CAST(:steps AS jsonb), CAST(:rules AS jsonb))
            ON CONFLICT (course_version_id, lesson_code) DO NOTHING
            RETURNING lesson_version_id
        """), values).scalar_one_or_none()
        if inserted is None:
            existing = conn.execute(text("""
                SELECT title, position_label, duration_minutes, source_data,
                       expected_result, steps, rules
                FROM public.training_lesson_versions
                WHERE course_version_id=:course AND lesson_code=:code
            """), values).mappings().one()
            if (existing["title"] != lesson["title"] or
                existing["position_label"] != lesson["position_label"] or
                existing["duration_minutes"] != lesson["duration_minutes"] or
                existing["source_data"] != lesson["source_data"] or
                existing["expected_result"] != lesson["expected_result"] or
                existing["steps"] != lesson["steps"] or
                existing["rules"] != lesson["rules"]):
                raise RuntimeError(f"Lesson {lesson['code']} differs from frozen v1")
    return course_id
