"""Transfer the already preserved /learning pilot from its PostgreSQL rehearsal.

Run after seed_demo_accounts.py and import_training_history.py. The source is
the local reviewed rehearsal copy; target is the isolated training database.
Evidence files are copied with checksums and the original attempt UUIDs stay.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.import_learning_pilot import copy_evidence
from scripts.learn.import_training_history import copy, rows, sequence_reset


USER_LOGINS = {
    "training_head_20261121": "learn.manager_test",
    "training_head_20261121_test": "learn.manager_test",
    "training_hr_partner_20261121": "learn.hr.a",
    "training_source_d10808de0076_test": "learn.hr.b",
    "training_reviewer_20261121": "learn.expert",
}
TABLES = (
    "learning_records", "learning_courses", "learning_lessons",
    "learning_assignment_batches", "learning_assignments", "learning_attempts",
    "learning_screenshots", "learning_screenshot_slots", "learning_criterion_results",
    "learning_exercise_applications", "learning_review_events",
)
USER_FIELDS = {
    "learning_records": ("participant_id",), "learning_courses": ("created_by",),
    "learning_lessons": ("created_by",), "learning_assignment_batches": ("created_by",),
    "learning_assignments": ("participant_id",),
    "learning_attempts": ("participant_id", "reviewer_id"),
    "learning_screenshots": ("participant_id",),
    "learning_exercise_applications": ("participant_id",),
    "learning_review_events": ("actor_id",),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-files", required=True)
    parser.add_argument("--target-files", required=True)
    parser.add_argument("--rehearsal", action="store_true")
    args = parser.parse_args()
    source_url = make_url(os.environ["SOURCE_DATABASE_URL"])
    target_url = make_url(os.environ["DATABASE_URL"])
    if source_url.host not in {"localhost", "127.0.0.1", "::1"} or source_url.database != "corpsite_learn_rehearsal_20261122":
        raise SystemExit("Source must be the local reviewed learning rehearsal")
    if target_url.host not in {"localhost", "127.0.0.1", "::1"} or (
        target_url.database != "corpsite_learn" and not (
            args.rehearsal and (target_url.database or "").startswith("corpsite_learn_rehearsal_")
        )
    ):
        raise SystemExit("Target must be isolated corpsite_learn")
    if source_url.database == target_url.database:
        raise SystemExit("Source and target are identical")
    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    inspector = inspect(target_engine)
    counts: dict[str, int] = defaultdict(int)
    with source_engine.connect() as source, target_engine.begin() as target:
        if target.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != "learning006":
            raise ValueError("Migrate target through learning006 first")
        user_map = {}
        for source_login, target_login in USER_LOGINS.items():
            old = source.execute(text("SELECT user_id FROM users WHERE login=:login"),
                                 {"login": source_login}).scalar_one()
            new = target.execute(text("SELECT user_id FROM users WHERE login=:login"),
                                 {"login": target_login}).scalar_one()
            user_map[int(old)] = int(new)
        unit_id = target.execute(text("SELECT unit_id FROM org_units WHERE code='LEARN-BASE'")).scalar_one()
        source_unit = source.execute(text("""
            SELECT DISTINCT a.intended_org_unit_id
            FROM learning_hire_applications h
            JOIN personnel_applications a ON a.application_id=h.application_id
        """)).scalar_one()
        source_unit_code = source.execute(text("SELECT code FROM org_units WHERE unit_id=:id"),
                                          {"id": source_unit}).scalar_one()
        if source_unit_code != "TRN-HEAD-BASE":
            raise ValueError("Pilot hire applications do not use the fictional training unit")
        source_position = source.execute(text("SELECT position_id FROM positions WHERE position_id=25")).scalar_one()
        copy(target, inspector, "positions", rows(source, "positions", "position_id=:id",
                                                  {"id": source_position}), counts)
        copy(target, inspector, "org_units", rows(source, "org_units", "unit_id=:id",
                                                  {"id": source_unit}), counts,
             lambda row: {**row, "parent_unit_id": unit_id, "group_id": 2})

        def mapped(row: dict, table: str) -> dict:
            for field in USER_FIELDS.get(table, ()):
                if row.get(field) is not None:
                    row[field] = user_map[int(row[field])]
            if "unit_id" in row:
                row["unit_id"] = unit_id
            if table == "learning_assignment_batches":
                recipients = json.loads(row["recipients_json"])
                for recipient in recipients:
                    if "user_id" in recipient:
                        recipient["user_id"] = user_map[int(recipient["user_id"])]
                        recipient["unit_id"] = unit_id
                row["recipients_json"] = json.dumps(recipients, ensure_ascii=False)
            return row

        evidence = rows(source, "learning_screenshots")
        copied_files = copy_evidence(evidence, Path(args.source_files), Path(args.target_files))
        for table in TABLES:
            copy(target, inspector, table, rows(source, table), counts,
                 lambda row, table=table: mapped(row, table))
        from app.learning import hire_bridge
        application_map = {}
        for row in sorted(rows(source, "learning_hire_applications"), key=lambda item: item["application_id"]):
            participant = user_map[int(row["participant_id"])]
            expected = json.loads(row["fixture_json"])
            if expected.get("idempotency_key") != f"learning-hire-{row['attempt_id']}" or not str(expected.get("iin", "")).startswith("9"):
                raise ValueError("Pilot hire confirmation is not a fictional training record")
            expected["org_unit_id"] = int(source_unit)
            expected["position_id"] = int(source_position)
            saved = hire_bridge.create_application(target, row["attempt_id"], participant, expected)
            application_map[row["application_id"]] = saved["application_id"]
            data = {**row, "participant_id": participant, "unit_id": unit_id,
                    "application_id": saved["application_id"], "person_id": saved["person_id"],
                    "fixture_json": json.dumps(expected, ensure_ascii=False)}
            copy(target, inspector, "learning_hire_applications", [data], counts)
        for table in counts:
            sequence_reset(target, inspector, table)
    print(json.dumps({"source": source_url.database, "target": target_url.database,
                      "inserted": dict(counts), "copied_files": copied_files,
                      "application_numbers": application_map}, ensure_ascii=False))


if __name__ == "__main__":
    main()
