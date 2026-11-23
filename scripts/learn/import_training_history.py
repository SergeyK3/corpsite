"""Copy only the fictional hire-approval lesson history into corpsite_learn.

SOURCE_DATABASE_URL points to the local pilot PostgreSQL copy; DATABASE_URL
points to an empty, migrated, seeded isolated training database. Both may be
SSH loopback tunnels. This deliberately excludes all unrelated HR records.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


SOURCE_USERS = {
    "training_head_20261121_test": "learn.manager_test",
    "training_hr_partner_20261121": "training_hr_partner_20261121",
    "training_reviewer_20261121": "learn.expert",
}


def rows(conn, table: str, where: str = "TRUE", params: dict | None = None) -> list[dict]:
    return [dict(row) for row in conn.execute(text(f"SELECT * FROM public.{table} WHERE {where}"), params or {}).mappings()]


def copy(conn, inspector, table: str, records: list[dict], counts: dict, change=None) -> None:
    if not records:
        return
    columns = {column["name"]: column for column in inspector.get_columns(table, schema="public")}
    pk = inspector.get_pk_constraint(table, schema="public")["constrained_columns"]
    if table == "training_attempt_objects":
        pk = ["attempt_id", "object_role"]
    if not pk:
        raise ValueError(f"No primary key: {table}")
    for original in records:
        row = change(dict(original)) if change else dict(original)
        if set(row) - set(columns):
            raise ValueError(f"Unknown columns in {table}")
        condition = " AND ".join(f"{key}=:{key}" for key in pk)
        current = conn.execute(text(f"SELECT * FROM public.{table} WHERE {condition}"), row).mappings().one_or_none()
        if current is not None:
            for key, value in row.items():
                existing = current[key]
                if isinstance(existing, memoryview):
                    existing = bytes(existing)
                if isinstance(value, memoryview):
                    value = bytes(value)
                if existing != value:
                    raise ValueError(f"Changed historical row: {table} {tuple(row[k] for k in pk)} {key}")
            continue
        bindings = {}
        expressions = []
        for key, value in row.items():
            if str(columns[key]["type"]).upper().startswith("JSON"):
                bindings[key] = json.dumps(value, ensure_ascii=False)
                expressions.append(f"CAST(:{key} AS jsonb)")
            else:
                bindings[key] = value
                expressions.append(f":{key}")
        override = " OVERRIDING SYSTEM VALUE" if any(column.get("identity") for column in columns.values()) else ""
        conn.execute(text(f"INSERT INTO public.{table} ({','.join(row)}){override} VALUES ({','.join(expressions)})"), bindings)
        counts[table] += 1


def sequence_reset(conn, inspector, table: str) -> None:
    for column in inspector.get_columns(table, schema="public"):
        if not column.get("identity"):
            continue
        name = column["name"]
        seq = conn.execute(text("SELECT pg_get_serial_sequence(:table,:column)"),
                           {"table": f"public.{table}", "column": name}).scalar_one()
        if seq:
            conn.execute(text("SELECT setval(CAST(:sequence AS regclass), GREATEST((SELECT COALESCE(MAX(" + name + "),0) FROM public." + table + "),1), TRUE)"), {"sequence": seq})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rehearsal", action="store_true")
    args = parser.parse_args()
    source_url = make_url(os.environ["SOURCE_DATABASE_URL"])
    target_url = make_url(os.environ["DATABASE_URL"])
    if source_url.host not in {"localhost", "127.0.0.1", "::1"} or source_url.database not in {
        "corpsite_test", "corpsite_learn_rehearsal_20261122"
    }:
        raise SystemExit("Source must be the local training pilot copy")
    if target_url.host not in {"localhost", "127.0.0.1", "::1"} or (
        target_url.database != "corpsite_learn" and not (
            args.rehearsal and (target_url.database or "").startswith("corpsite_learn_")
        )
    ):
        raise SystemExit("Target must be isolated corpsite_learn")
    if source_url.database == target_url.database:
        raise SystemExit("Source and target databases are identical")
    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    inspector = inspect(target_engine)
    counts: dict[str, int] = defaultdict(int)
    with source_engine.connect() as source, target_engine.begin() as target:
        if target.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != "learning006":
            raise ValueError("Migrate target to learning006 before import")
        if source.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != "learning006":
            raise ValueError("Source schema must match learning006")
        user_map = {}
        for from_login, to_login in SOURCE_USERS.items():
            old = source.execute(text("SELECT user_id FROM users WHERE login=:login"), {"login": from_login}).scalar_one()
            new = target.execute(text("SELECT user_id FROM users WHERE login=:login"), {"login": to_login}).scalar_one()
            user_map[int(old)] = int(new)
        manager = user_map[source.execute(text("SELECT user_id FROM users WHERE login='training_head_20261121_test'")).scalar_one()]
        manager_role = target.execute(text("SELECT role_id FROM users WHERE user_id=:id"), {"id": manager}).scalar_one()
        base_unit = target.execute(text("SELECT unit_id FROM org_units WHERE code='LEARN-BASE'")).scalar_one()
        lesson_data = source.execute(text("""
            SELECT l.lesson_version_id,c.course_code,c.version,l.lesson_code
            FROM training_lesson_versions l JOIN training_course_versions c USING(course_version_id)
            WHERE c.course_code='application_administration' AND l.lesson_code='skill_2'
              AND c.version IN (2,3)
        """)).mappings().all()
        lesson_map = {}
        for lesson in lesson_data:
            row = target.execute(text("""
                SELECT l.lesson_version_id FROM training_lesson_versions l
                JOIN training_course_versions c USING(course_version_id)
                WHERE c.course_code=:course_code AND c.version=:version AND l.lesson_code=:lesson_code
            """), dict(lesson)).scalar_one()
            lesson_map[int(lesson["lesson_version_id"])] = int(row)
        if len(lesson_map) != 2:
            raise ValueError("Expected both published hire-approval lesson versions")
        assignments = rows(source, "training_assignments", "lesson_version_id=ANY(:ids)",
                           {"ids": list(lesson_map)})
        assignment_ids = [row["assignment_id"] for row in assignments]
        attempts = rows(source, "training_attempts", "assignment_id=ANY(:ids)", {"ids": assignment_ids})
        attempt_ids = [row["attempt_id"] for row in attempts]
        objects = rows(source, "training_attempt_objects", "attempt_id=ANY(:ids)", {"ids": attempt_ids})
        if len(attempts) != 8 or len(objects) != 8:
            raise ValueError("Expected eight source approval attempts and eight linked records")
        application_ids = [row["application_id"] for row in objects]
        order_ids = [row["order_id"] for row in objects]
        task_ids = [row["task_id"] for row in objects]
        applications = rows(source, "personnel_applications", "application_id=ANY(:ids)", {"ids": application_ids})
        if len(applications) != len(objects) or any(
            app["idempotency_key"] != f"training-hire-{obj['attempt_id']}"
            for obj in objects for app in applications if app["application_id"] == obj["application_id"]
        ):
            raise ValueError("Approval history includes a non-training application")
        person_ids = [row["person_id"] for row in applications]
        unit_ids = [row["intended_org_unit_id"] for row in applications]
        position_ids = [row["intended_position_id"] for row in applications]
        fictional_people = rows(source, "persons", "person_id=ANY(:ids)", {"ids": person_ids})
        fictional_units = rows(source, "org_units", "unit_id=ANY(:ids)", {"ids": unit_ids})
        if len(fictional_people) != len(person_ids) or any(
            not str(person["iin"] or "").startswith("9") for person in fictional_people
        ) or len(fictional_units) != len(unit_ids) or any(
            not str(unit["code"] or "").startswith("TRN-HIRE-") for unit in fictional_units
        ):
            raise ValueError("Approval history is not a fully fictional training fixture")
        tasks = rows(source, "tasks", "task_id=ANY(:ids)", {"ids": task_ids})
        period_ids = list({row["period_id"] for row in tasks})
        status_map = {}
        for row in source.execute(text("SELECT status_id,code FROM task_statuses")).mappings():
            new = target.execute(text("SELECT status_id FROM task_statuses WHERE code=:code"),
                                 {"code": row["code"]}).scalar_one()
            status_map[row["status_id"]] = new

        def users(row: dict, fields: tuple[str, ...]) -> dict:
            for field in fields:
                if row.get(field) is not None:
                    row[field] = user_map[int(row[field])]
            return row

        copy(target, inspector, "positions", rows(source, "positions", "position_id=ANY(:ids)",
                                                  {"ids": position_ids}), counts)
        copy(target, inspector, "org_units", fictional_units, counts,
             lambda row: {**row, "parent_unit_id": base_unit, "group_id": 2})
        copy(target, inspector, "org_unit_managers", [], counts)
        for unit_id in unit_ids:
            if not target.execute(text("SELECT 1 FROM org_unit_managers WHERE unit_id=:unit AND user_id=:user AND manager_type='HEAD'"),
                                  {"unit": unit_id, "user": manager}).first():
                target.execute(text("INSERT INTO org_unit_managers(unit_id,user_id,manager_type,date_from,is_active) VALUES (:unit,:user,'HEAD',CURRENT_DATE,TRUE)"),
                               {"unit": unit_id, "user": manager})
                counts["org_unit_managers"] += 1
        copy(target, inspector, "persons", fictional_people, counts)
        copy(target, inspector, "person_contacts", rows(source, "person_contacts", "person_id=ANY(:ids)",
                                                        {"ids": person_ids}), counts,
             lambda row: users(row, ("created_by_user_id", "updated_by_user_id")))
        copy(target, inspector, "person_education", rows(source, "person_education", "person_id=ANY(:ids)",
                                                         {"ids": person_ids}), counts)
        copy(target, inspector, "reporting_periods", rows(source, "reporting_periods", "period_id=ANY(:ids)",
                                                           {"ids": period_ids}), counts)
        copy(target, inspector, "personnel_orders", rows(source, "personnel_orders", "order_id=ANY(:ids)",
                                                         {"ids": order_ids}), counts,
             lambda row: users(row, ("created_by", "voided_by", "archived_by", "deleted_by_user_id")))
        copy(target, inspector, "personnel_applications", applications, counts,
             lambda row: users(row, ("registered_by_user_id", "vacancy_checked_by_user_id",
                                     "director_resolution_by_user_id", "cancelled_by_user_id", "closed_by_user_id")))
        copy(target, inspector, "electronic_hire_applications", rows(source, "electronic_hire_applications",
             "application_id=ANY(:ids)", {"ids": application_ids}), counts,
             lambda row: users(row, ("candidate_checked_by_user_id",)))
        copy(target, inspector, "electronic_hire_visas", rows(source, "electronic_hire_visas",
             "application_id=ANY(:ids)", {"ids": application_ids}), counts,
             lambda row: users(row, ("decided_by_user_id",)))
        copy(target, inspector, "personnel_order_items", rows(source, "personnel_order_items",
             "order_id=ANY(:ids)", {"ids": order_ids}), counts,
             lambda row: users(row, ("voided_by",)))
        copy(target, inspector, "tasks", tasks, counts,
             lambda row: {**users(row, ("initiator_user_id", "created_by_user_id", "approver_user_id")),
                          "executor_role_id": manager_role, "status_id": status_map[row["status_id"]]})
        for table, fields in (("task_reports", ("submitted_by", "approved_by")),):
            copy(target, inspector, table, rows(source, table, "task_id=ANY(:ids)",
                                                {"ids": task_ids}), counts,
                 lambda row, fields=fields: users(row, fields))
        def audit_actor(row: dict) -> dict:
            row = users(row, ("actor_user_id",))
            if row.get("actor_id") is not None:
                row["actor_id"] = user_map[int(row["actor_id"])]
            if row.get("actor_role") and str(row["actor_role"]).isdigit():
                row["actor_role"] = str(manager_role)
            return row
        copy(target, inspector, "task_audit_log", rows(source, "task_audit_log",
             "task_id=ANY(:ids)", {"ids": task_ids}), counts, audit_actor)
        copy(target, inspector, "task_events", rows(source, "task_events", "task_id=ANY(:ids)",
                                                     {"ids": task_ids}), counts,
             lambda row: {**users(row, ("actor_user_id",)), "actor_role_id": manager_role})
        copy(target, inspector, "training_assignments", assignments, counts,
             lambda row: {**users(row, ("participant_user_id",)),
                          "lesson_version_id": lesson_map[row["lesson_version_id"]]})
        copy(target, inspector, "training_attempts", attempts, counts)
        copy(target, inspector, "training_attempt_objects", objects, counts)
        copy(target, inspector, "training_evidence", rows(source, "training_evidence",
             "attempt_id=ANY(:ids)", {"ids": attempt_ids}), counts,
             lambda row: users(row, ("uploaded_by_user_id",)))
        copy(target, inspector, "training_attempt_events", rows(source, "training_attempt_events",
             "attempt_id=ANY(:ids)", {"ids": attempt_ids}), counts,
             lambda row: users(row, ("actor_user_id",)))
        copy(target, inspector, "training_reviews", rows(source, "training_reviews",
             "attempt_id=ANY(:ids)", {"ids": attempt_ids}), counts)
        for table in counts:
            sequence_reset(target, inspector, table)
    print(json.dumps({"source": source_url.database, "target": target_url.database,
                      "attempts": len(attempts), "applications": len(applications),
                      "inserted": dict(counts)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
