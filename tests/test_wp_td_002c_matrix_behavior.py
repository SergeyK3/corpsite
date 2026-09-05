"""WP-TD-002C behavioral coverage for every server-owned relationship rule."""
from __future__ import annotations

import itertools
import json
import re
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text

from app.services import test_personnel_deletion_service as service
from tests.test_wp_td_005_manifest_v2 import _alembic_config, _ephemeral_database
from alembic import command


@pytest.fixture(autouse=True)
def hr_import_storage_dir(monkeypatch):
    """The relationship matrix does not use the HR-import filesystem."""
    monkeypatch.setenv("HR_IMPORT_STORAGE_DIR", "wp-td-002c-unused-test-storage")


_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
_SEQUENCE = itertools.count(100_000)


def _identifier(value: str) -> str:
    assert _IDENTIFIER.fullmatch(value)
    return value


def _generic_value(conn, udt_name: str, column_name: str):
    number = next(_SEQUENCE)
    if udt_name in {"numeric", "float4", "float8"}:
        return 1
    if udt_name == "int2":
        return 1
    if udt_name in {"int4", "int8"}:
        return number
    if udt_name == "uuid":
        return uuid.uuid4()
    if udt_name in {"date"}:
        return date(2035, 1, 1)
    if udt_name in {"timestamp", "timestamptz"}:
        return datetime(2035, 1, 1, tzinfo=timezone.utc)
    if udt_name == "bool":
        return False
    if udt_name in {"json", "jsonb"}:
        return {}
    if udt_name == "bytea":
        return b"wp-td-002c"
    if udt_name.startswith("_"):
        return []
    enum_value = conn.execute(text("""SELECT e.enumlabel FROM pg_type t
        JOIN pg_enum e ON e.enumtypid=t.oid WHERE t.typname=:name
        ORDER BY e.enumsortorder LIMIT 1"""), {"name": udt_name}).scalar_one_or_none()
    if enum_value is not None:
        return enum_value
    if udt_name in {"inet", "cidr"}:
        return "127.0.0.1"
    return f"wp-td-002c-{column_name}-{number}"


def _insert_minimal(conn, table: str, payload: dict) -> dict:
    table = _identifier(table)
    columns = conn.execute(text("""SELECT column_name,udt_name,column_default,is_nullable,is_identity,is_generated
        FROM information_schema.columns WHERE table_schema='public' AND table_name=:table
        ORDER BY ordinal_position"""), {"table": table}).mappings().all()
    assert columns, table
    known = {row["column_name"] for row in columns}
    assert set(payload) <= known, (table, set(payload) - known)
    values = dict(payload)
    for row in columns:
        name = str(row["column_name"])
        if name in values or row["is_nullable"] == "YES" or row["column_default"] is not None:
            continue
        if row["is_identity"] == "YES" or row["is_generated"] != "NEVER":
            continue
        values[name] = _generic_value(conn, str(row["udt_name"]), name)
    names = list(values)
    types = {str(row["column_name"]): str(row["udt_name"]) for row in columns}
    expressions = []
    for name in names:
        if types[name] in {"json", "jsonb"}:
            values[name] = json.dumps(values[name])
            expressions.append(f"CAST(:{name} AS {types[name]})")
        elif types[name].startswith("_"):
            element_type = types[name][1:]
            expressions.append(f"CAST(:{name} AS {element_type}[])")
        else:
            expressions.append(f":{name}")
    sql = f"INSERT INTO public.{table} ({','.join(_identifier(name) for name in names)}) VALUES ({','.join(expressions)}) RETURNING ctid::text AS _fixture_ctid,*"
    return dict(conn.execute(text(sql), values).mappings().one())


def _drop_test_only_checks(conn, tables):
    for row in conn.execute(text("""SELECT c.conname,n.nspname,t.relname
        FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE c.contype='c' AND n.nspname='public' AND t.relname=ANY(:tables)"""), {
        "tables": sorted(set(tables)),
    }).mappings():
        conn.execute(text(f"ALTER TABLE public.{_identifier(row['relname'])} DROP CONSTRAINT {_identifier(row['conname'])}"))


def _locator(conn, table: str, row: dict) -> dict:
    keys = conn.execute(text("""SELECT a.attname FROM pg_index i
        JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey)
        WHERE i.indrelid=CAST(:table AS regclass) AND i.indisprimary ORDER BY a.attnum"""), {
        "table": f"public.{table}",
    }).scalars().all()
    if not keys:
        return {"__ctid__": row["_fixture_ctid"]}
    return {str(key): row[str(key)] for key in keys}


def _update_linked_row(conn, rule, locator):
    columns = conn.execute(text("""SELECT column_name,udt_name,is_generated
        FROM information_schema.columns WHERE table_schema='public' AND table_name=:table
        ORDER BY CASE column_name WHEN 'updated_at' THEN 0 WHEN 'created_at' THEN 1 ELSE 2 END,ordinal_position"""), {
        "table": rule.table,
    }).mappings().all()
    if rule.code == "PROVENANCE_STATE_RETAINED":
        changed = conn.execute(text("""UPDATE public.test_personnel_provenance
            SET source_artifact_hash=repeat('b',64)
            WHERE provenance_id=:provenance_id"""), locator).rowcount
        assert changed == 1
        return
    if rule.code == "PERSON_ROOT_NOT_ELIGIBLE":
        changed = conn.execute(text("""UPDATE public.persons SET full_name=full_name||' changed'
            WHERE person_id=:person_id"""), locator).rowcount
        assert changed == 1
        return
    if rule.code == "ONBOARDING_NOTIFICATION_RECIPIENT_PRESENT":
        changed = conn.execute(text("""UPDATE public.employee_onboarding_notification_recipients r
            SET notification_id=(
                SELECT replacement.notification_id
                FROM public.employee_onboarding_notifications current
                JOIN public.employee_onboarding_notifications replacement
                  ON replacement.onboarding_id=current.onboarding_id
                 AND replacement.notification_id<>current.notification_id
                WHERE current.notification_id=r.notification_id
                ORDER BY replacement.notification_id LIMIT 1)
            WHERE notification_id=:notification_id AND user_id=:user_id"""), locator).rowcount
        assert changed == 1
        return
    if rule.code == "TASK_EVENT_RECIPIENT_USER_SATELLITE_PRESENT":
        changed = conn.execute(text("""UPDATE public.task_event_recipients r
            SET audit_id=(SELECT e.audit_id FROM public.task_events e
                WHERE e.audit_id<>r.audit_id ORDER BY e.audit_id DESC LIMIT 1)
            WHERE audit_id=:audit_id AND user_id=:user_id"""), locator).rowcount
        assert changed == 1
        return
    if rule.code == "USER_SUPERVISOR_RELATION_PRESENT":
        changed = conn.execute(text("""UPDATE public.user_supervisors
            SET supervisor_id=(SELECT candidate.user_id FROM public.users candidate
                WHERE candidate.user_id<>user_supervisors.supervisor_id
                  AND candidate.user_id<>user_supervisors.user_id
                ORDER BY candidate.user_id LIMIT 1)
            WHERE user_id=:user_id"""), locator).rowcount
        assert changed == 1
        return
    predicate_names = {name.lower() for name in re.findall(r"[a-z_][a-z0-9_]*", rule.sql.lower())}
    candidates = [row for row in columns if row["column_name"] not in locator
        and row["column_name"].lower() not in predicate_names and row["is_generated"] == "NEVER"]
    if not candidates:
        candidates = [row for row in columns if row["column_name"].lower() not in predicate_names
            and row["is_generated"] == "NEVER" and row["column_name"] != "__ctid__"]
    assert candidates, rule.code
    row = candidates[0]
    column = _identifier(str(row["column_name"]))
    udt_name = str(row["udt_name"])
    if udt_name in {"int2", "int4", "int8", "numeric", "float4", "float8"}:
        expression = f"COALESCE({column},0)+1"
    elif udt_name in {"timestamp", "timestamptz"}:
        expression = f"COALESCE({column},statement_timestamp())+interval '1 second'"
    elif udt_name == "date":
        expression = f"COALESCE({column},current_date)+1"
    elif udt_name == "bool":
        expression = f"NOT COALESCE({column},FALSE)"
    elif udt_name == "jsonb":
        expression = f"COALESCE({column},'{{}}'::jsonb)||'{{\"wp_td_002c_changed\":true}}'::jsonb"
    elif udt_name in {"text", "varchar", "bpchar"}:
        expression = f"COALESCE({column},'')||'-wp-td-002c-changed'"
    else:
        enum_count = conn.execute(text("""SELECT COUNT(*) FROM pg_type t
            JOIN pg_enum e ON e.enumtypid=t.oid WHERE t.typname=:name"""), {"name": udt_name}).scalar_one()
        if enum_count > 1:
            enum_type = _identifier(udt_name)
            expression = f"(SELECT CAST(e.enumlabel AS {enum_type}) FROM pg_type t JOIN pg_enum e ON e.enumtypid=t.oid WHERE t.typname='{enum_type}' AND e.enumlabel<>{column}::text ORDER BY e.enumsortorder LIMIT 1)"
        else:
            raise AssertionError(f"No deterministic mutation expression for {rule.code}:{column}:{udt_name}")
    if "__ctid__" in locator:
        where = "ctid=CAST(:__ctid__ AS tid)"
    else:
        where = " AND ".join(f"{_identifier(name)}=:{name}" for name in locator)
    changed = conn.execute(text(f"UPDATE public.{_identifier(rule.table)} SET {column}={expression} WHERE {where}"), locator).rowcount
    assert changed == 1


@pytest.fixture(scope="module")
def matrix_graph():
    with _ephemeral_database(upgrade=False) as (url, db):
        command.upgrade(_alembic_config(url), "head")
        with db.begin() as conn:
            conn.execute(text("SET LOCAL session_replication_role='replica'"))
            tables = {rule.table for rule in service.RELATIONSHIP_MATRIX}
            _drop_test_only_checks(conn, tables)
            actor = conn.execute(text("SELECT user_id FROM users ORDER BY user_id LIMIT 1")).scalar_one()
            person = _insert_minimal(conn, "persons", {"full_name": "WP TD 002C matrix person", "match_key": f"wp-td-002c-{uuid.uuid4().hex}", "source": "manual", "person_status": "inactive"})
            person_id = int(person["person_id"])
            application = _insert_minimal(conn, "personnel_applications", {"person_id": person_id, "status": "intake_pending", "registered_by_user_id": actor, "idempotency_key": f"wp-td-002c-app-{uuid.uuid4().hex}"})
            application_id = int(application["application_id"])
            employee = _insert_minimal(conn, "employees", {"person_id": person_id, "full_name": "WP TD 002C employee"})
            employee_id = int(employee["employee_id"])
            role_id = conn.execute(text("SELECT role_id FROM roles ORDER BY role_id LIMIT 1")).scalar_one()
            user = _insert_minimal(conn, "users", {"employee_id": employee_id, "role_id": role_id, "full_name": "WP TD 002C user", "login": f"wp-td-002c-{uuid.uuid4().hex}"})
            user_id = int(user["user_id"])

            rows = {}
            def add(code, table, payload):
                row = _insert_minimal(conn, table, payload)
                rows[code] = (table, _locator(conn, table, row))
                return row

            for code in ("ALL_APPLICATIONS_PRESENT", "SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED", "APPLICATION_STATUS_NOT_ELIGIBLE", "PERSONNEL_ORDER_PRESENT", "DIRECTOR_RESOLUTION_PRESENT"):
                rows[code] = ("personnel_applications", {"application_id": application_id})
            rows["PERSON_ROOT_NOT_ELIGIBLE"] = ("persons", {"person_id": person_id})
            rows["EMPLOYEE_PRESENT"] = ("employees", {"employee_id": employee_id})
            rows["USER_IDENTITY_PRESENT"] = ("users", {"user_id": user_id})

            direct_person = {
                "LEGACY_PERSONNEL_PRESENT":"personnel", "CONTACT_PRESENT":"contacts", "CONTACT_ACCESS_PRESENT":"contact_access",
                "KEY_CONTACT_PRESENT":"key_contacts", "ORG_UNIT_KEY_STAFF_PRESENT":"org_unit_key_staff", "ASSIGNMENT_PRESENT":"person_assignments",
                "ENROLLMENT_QUEUE_PRESENT":"enrollment_queue", "PPR_EVENT_TOMBSTONE_REQUIRED":"personnel_record_events",
                "PPR_COMMAND_TOMBSTONE_REQUIRED":"ppr_command_executions", "PPR_METADATA_PRESENT":"personnel_record_metadata",
                "PPR_EDUCATION_PRESENT":"person_education", "PPR_TRAINING_PRESENT":"person_training", "PPR_RELATIVE_PRESENT":"person_relatives",
                "PPR_EXTERNAL_EMPLOYMENT_PRESENT":"person_external_employment", "PPR_MILITARY_PRESENT":"person_military_service",
                "PHOTO_PRESENT":"person_photos", "TELEGRAM_BINDING_PRESENT":"person_telegram_bindings",
                "TELEGRAM_ACTIVATION_PRESENT":"person_telegram_bot_activations", "VERIFICATION_TASK_PRESENT":"verification_tasks",
                "VERIFICATION_ATTESTATION_PRESENT":"verification_attestations", "IDENTITY_RECONCILIATION_PRESENT":"identity_reconciliation_items",
                "HR_CHANGE_EVENT_PRESENT":"hr_personnel_change_events", "ENROLLMENT_HISTORY_RETAINED":"enrollment_history",
                "HR_REVIEW_OVERRIDE_RETAINED":"hr_review_overrides", "PERSONNEL_MIGRATION_RUN_PRESENT":"personnel_migration_runs",
            }
            created = {}
            for code, table in direct_person.items():
                created[code] = add(code, table, {"person_id": person_id})
            add("PHOTO_PROVENANCE_PRESENT", "person_photo_sources", {"person_id": person_id, "source_application_id": application_id})
            add("INCOMING_DOCUMENT_PRESENT", "incoming_documents", {"sender_person_id": person_id})
            incoming_row = created.get("INCOMING_DOCUMENT_PRESENT") or conn.execute(text("SELECT * FROM incoming_documents WHERE sender_person_id=:id LIMIT 1"), {"id": person_id}).mappings().one()
            incoming_id = int(incoming_row["incoming_document_id"])
            rows["INCOMING_DOCUMENT_PARTICIPATION_PRESENT"] = rows["INCOMING_DOCUMENT_PRESENT"]
            add("MERGED_PERSON_REFERENCE_PRESENT", "persons", {"full_name": "WP TD merged", "match_key": f"wp-td-merged-{uuid.uuid4().hex}", "source": "manual", "merged_into_person_id": person_id})

            app_tables = {
                "INTAKE_REVIEW_PRESENT":"personnel_intake_section_reviews", "INTAKE_TRANSFER_PRESENT":"personnel_intake_transfers",
                "APPLICATION_BLOCKER_PRESENT":"personnel_application_blockers", "APPLICATION_RESOLUTION_AUDIT_PRESENT":"personnel_application_resolution_audit",
                "INTAKE_LINK_PRESENT":"personnel_intake_links", "INTAKE_DRAFT_PRESENT":"personnel_intake_drafts",
            }
            for code, table in app_tables.items(): add(code, table, {"application_id": application_id})
            add("INTAKE_RECONCILIATION_PRESENT", "personnel_intake_reconciliation_decisions", {"person_id": person_id, "application_id": application_id})
            add("APPLICATION_EARLY_LIFECYCLE_TOMBSTONE_REQUIRED", "personnel_application_lifecycle_audit", {"application_id": application_id, "action": service.EARLY_LIFECYCLE_ACTIONS[0]})
            add("APPLICATION_OFFICIAL_LIFECYCLE_PRESENT", "personnel_application_lifecycle_audit", {"application_id": application_id, "action": "official_decision"})

            onboarding = add("ONBOARDING_PRESENT", "employee_onboardings", {"application_id": application_id, "employee_id": employee_id})
            onboarding_id = int(onboarding["onboarding_id"])
            item = add("ONBOARDING_ITEM_PRESENT", "employee_onboarding_checklist_items", {"onboarding_id": onboarding_id})
            item_id = int(item["item_id"])
            add("ONBOARDING_ATTACHMENT_PRESENT", "employee_onboarding_checklist_attachments", {"item_id": item_id})
            onboarding_notification = add("ONBOARDING_NOTIFICATION_PRESENT", "employee_onboarding_notifications", {"onboarding_id": onboarding_id})
            _insert_minimal(conn, "employee_onboarding_notifications", {"onboarding_id": onboarding_id})
            add("ONBOARDING_TASK_AUDIT_PRESENT", "employee_onboarding_task_audit", {"onboarding_id": onboarding_id})

            override_id = int(created["HR_REVIEW_OVERRIDE_RETAINED"]["override_id"])
            add("HR_REVIEW_OVERRIDE_HISTORY_RETAINED", "hr_review_override_history", {"override_id": override_id})
            employee_tables = {
                "HR_IMPORT_ROW_RETAINED":"hr_import_rows", "HR_IMPORT_NORMALIZED_RETAINED":"hr_import_normalized_records",
                "EMPLOYEE_DOCUMENT_PRESENT":"employee_documents", "EMPLOYEE_ASSIGNMENT_LINK_PRESENT":"employee_assignment_links",
                "EMPLOYEE_EVENT_PRESENT":"employee_events", "EMPLOYEE_IDENTITY_PRESENT":"employee_identities",
                "EMPLOYEE_PROFILE_OVERRIDE_PRESENT":"employee_import_profile_overrides", "HR_BASELINE_ENTRY_RETAINED":"hr_baseline_entries",
                "HR_CHANGE_EVENT_RETAINED":"hr_change_events", "HR_IMPORT_DOCUMENT_CANDIDATE_RETAINED":"hr_import_document_candidates",
                "HR_MONTHLY_REFERENCE_ENTRY_RETAINED":"hr_monthly_reference_entries", "LEGACY_IMPORT_STAGE_RETAINED":"employees_import_stage",
            }
            for code, table in employee_tables.items(): created[code] = add(code, table, {"employee_id": employee_id})
            termination = add("TERMINATION_RECORD_PRESENT", "employee_termination_records", {"employee_id": employee_id})
            add("TERMINATION_AUDIT_RETAINED", "employee_termination_record_audit", {"termination_record_id": termination["termination_record_id"]})

            order = add("PERSONNEL_ORDER_SIGNATORY_PRESENT", "personnel_orders", {"signed_by_employee_id": employee_id})
            order_id = int(order["order_id"])
            order_item = add("PERSONNEL_ORDER_ITEM_PRESENT", "personnel_order_items", {"order_id": order_id, "employee_id": employee_id})
            order_item_id = int(order_item["item_id"])
            add("PERSONNEL_ORDER_AUDIT_RETAINED", "personnel_order_lifecycle_audit", {"order_id": order_id})
            add("OPERATIONAL_ORDER_SIGNING_PRESENT", "operational_order_signing_attestations", {"actor_employee_id": employee_id})
            for code, table in {
                "PERSONNEL_ORDER_ATTACHMENT_PRESENT":"personnel_order_attachments", "PERSONNEL_ORDER_EDITORIAL_BLOCK_PRESENT":"personnel_order_editorial_blocks",
                "PERSONNEL_ORDER_EVIDENCE_SCOPE_PRESENT":"personnel_order_evidence_scopes", "PERSONNEL_ORDER_LOCALIZED_TEXT_PRESENT":"personnel_order_localized_texts",
                "PERSONNEL_ORDER_PRINT_PRESENT":"personnel_order_prints",
            }.items(): add(code, table, {"order_id": order_id})
            add("PERSONNEL_ORDER_ITEM_BASIS_PRESENT", "personnel_order_item_bases", {"subject_employee_id": employee_id, "order_item_id": order_item_id})

            add("SECURITY_AUDIT_RETAINED", "security_audit_log", {"target_person_id": person_id})
            add("PROVENANCE_STATE_RETAINED", "test_personnel_provenance", {"target_type": "PERSON", "target_id": person_id, "environment": (service.os.getenv("APP_ENV") or "dev").strip().lower(), "created_by_user_id": actor, "source_artifact_hash": "a" * 64})
            add("ACCESS_GRANT_RETAINED", "access_grants", {"target_type": "PERSON", "target_id": person_id, "access_role_id": 1, "granted_by_user_id": actor})
            add("PERSONNEL_VISIBILITY_RETAINED", "personnel_visibility_assignments", {"target_user_id": user_id})

            incoming_tables = {
                "INCOMING_DOCUMENT_ASSIGNMENT_PRESENT":"incoming_document_assignments", "INCOMING_DOCUMENT_ATTACHMENT_PRESENT":"incoming_document_attachments",
                "INCOMING_DOCUMENT_AUDIT_RETAINED":"incoming_document_audit", "INCOMING_DOCUMENT_DEADLINE_CHANGE_PRESENT":"incoming_document_deadline_changes",
                "INCOMING_DOCUMENT_OPERATIONAL_ORDER_LINK_PRESENT":"incoming_document_operational_order_links",
                "INCOMING_DOCUMENT_TRANSFER_PRESENT":"incoming_document_transfers",
            }
            for code, table in incoming_tables.items(): add(code, table, {"incoming_document_id": incoming_id})
            add("INCOMING_DOCUMENT_PERSONNEL_ORDER_LINK_PRESENT", "incoming_document_personnel_order_links", {"incoming_document_id": incoming_id, "personnel_order_id": order_id})

            decision = add("USER_LINKAGE_REVIEW_DECISION_PRESENT", "user_linkage_review_decisions", {"proposed_employee_id": employee_id, "user_id": user_id})
            add("USER_LINKAGE_EXECUTE_ITEM_PRESENT", "user_linkage_execute_items", {"proposed_employee_id": employee_id, "user_id": user_id, "source_decision_id": decision["decision_id"]})

            add("PERSONNEL_ORDER_ITEM_EDITORIAL_BLOCK_PRESENT", "personnel_order_item_editorial_blocks", {"order_item_id": order_item_id})
            add("ONBOARDING_NOTIFICATION_RECIPIENT_PRESENT", "employee_onboarding_notification_recipients", {"notification_id": onboarding_notification["notification_id"], "user_id": user_id})
            add("ONBOARDING_NOTIFICATION_DELIVERY_PRESENT", "employee_onboarding_notification_deliveries", {"notification_id": onboarding_notification["notification_id"], "user_id": user_id})
            add("PERSONNEL_MIGRATION_ITEM_PRESENT", "personnel_migration_items", {"run_id": created["PERSONNEL_MIGRATION_RUN_PRESENT"]["run_id"]})
            rows["ONBOARDING_MENTOR_PRESENT"] = ("employee_onboardings", {"onboarding_id": onboarding_id})
            conn.execute(text("UPDATE employee_onboardings SET mentor_employee_id=:employee_id WHERE onboarding_id=:id"), {"employee_id": employee_id, "id": onboarding_id})
            rows["ONBOARDING_ASSIGNEE_PRESENT"] = ("employee_onboarding_checklist_items", {"item_id": item_id})
            conn.execute(text("UPDATE employee_onboarding_checklist_items SET assignee_employee_id=:employee_id WHERE item_id=:id"), {"employee_id": employee_id, "id": item_id})
            for code, original_code, table, key in (
                ("VERIFICATION_VERIFIER_PRESENT", "VERIFICATION_ATTESTATION_PRESENT", "verification_attestations", "verifier_employee_id"),
                ("IDENTITY_RECONCILIATION_EMPLOYEE_PRESENT", "IDENTITY_RECONCILIATION_PRESENT", "identity_reconciliation_items", "employee_id"),
                ("PPR_EDUCATION_EMPLOYEE_CONTEXT_PRESENT", "PPR_EDUCATION_PRESENT", "person_education", "employee_context_id"),
                ("PPR_TRAINING_EMPLOYEE_CONTEXT_PRESENT", "PPR_TRAINING_PRESENT", "person_training", "employee_context_id"),
                ("PPR_EXTERNAL_EMPLOYMENT_CONTEXT_PRESENT", "PPR_EXTERNAL_EMPLOYMENT_PRESENT", "person_external_employment", "employee_context_id"),
                ("PPR_MILITARY_CONTEXT_PRESENT", "PPR_MILITARY_PRESENT", "person_military_service", "employee_context_id"),
                ("PPR_EVENT_EMPLOYEE_CONTEXT_PRESENT", "PPR_EVENT_TOMBSTONE_REQUIRED", "personnel_record_events", "employee_context_id"),
            ):
                locator = rows[original_code][1]
                where = " AND ".join(f"{name}=:{name}" for name in locator)
                conn.execute(text(f"UPDATE public.{table} SET {key}=:employee_id WHERE {where}"), {**locator, "employee_id": employee_id})
                rows[code] = (table, locator)
            rows["HR_CANONICAL_SNAPSHOT_ENTRY_RETAINED"] = ("hr_baseline_entries", _locator(conn, "hr_baseline_entries", created["HR_BASELINE_ENTRY_RETAINED"]))
            add("SECURITY_AUDIT_EMPLOYEE_RETAINED", "security_audit_log", {"target_employee_id": employee_id})
            task = add("TASK_USER_SATELLITE_PRESENT", "tasks", {"initiator_user_id": user_id})
            task_id = int(task["task_id"])
            add("TASK_REPORT_USER_SATELLITE_PRESENT", "task_reports", {"task_id": task_id, "submitted_by": user_id})
            add("TASK_AUDIT_USER_SATELLITE_PRESENT", "task_audit_log", {"task_id": task_id, "actor_user_id": user_id})
            add("AUDIT_LOG_USER_SATELLITE_PRESENT", "audit_log", {"actor_user_id": user_id})
            task_event = add("TASK_EVENT_USER_SATELLITE_PRESENT", "task_events", {"task_id": task_id, "actor_user_id": user_id})
            task_event_id = int(task_event["audit_id"])
            _insert_minimal(conn, "task_events", {"task_id": task_id, "actor_user_id": user_id})
            add("TASK_EVENT_RECIPIENT_USER_SATELLITE_PRESENT", "task_event_recipients", {"audit_id": task_event_id, "user_id": user_id})
            add("TASK_EVENT_DELIVERY_USER_SATELLITE_PRESENT", "task_event_deliveries", {"audit_id": task_event_id, "user_id": user_id})
            add("NOTIFICATION_USER_SATELLITE_PRESENT", "notifications", {"recipient_user_id": user_id})
            add("TELEGRAM_USER_SATELLITE_PRESENT", "tg_bindings", {"user_id": user_id})
            add("USER_ORG_RELATION_PRESENT", "user_org_units", {"user_id": user_id})
            add("USER_SUPERVISOR_RELATION_PRESENT", "user_supervisors", {"user_id": user_id, "supervisor_id": actor})
            add("ORG_UNIT_MANAGER_RELATION_PRESENT", "org_unit_managers", {
                "manager_id": next(_SEQUENCE), "user_id": user_id,
            })
            assert set(rows) == {rule.code for rule in service.RELATIONSHIP_MATRIX}
        special_application_rules = {"ALL_APPLICATIONS_PRESENT", "SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED",
            "APPLICATION_STATUS_NOT_ELIGIBLE", "PERSONNEL_ORDER_PRESENT", "DIRECTOR_RESOLUTION_PRESENT"}
        results = {}
        with db.begin() as conn:
            conn.execute(text("SET LOCAL session_replication_role='replica'"))
            for rule in service.RELATIONSHIP_MATRIX:
                if rule.code not in special_application_rules:
                    continue
                conn.execute(text("""UPDATE personnel_applications SET status='intake_pending',
                    personnel_order_id=NULL,director_resolution_status=NULL WHERE application_id=:id"""), {"id": application_id})
                if rule.code == "SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED":
                    conn.execute(text("UPDATE personnel_applications SET status='intake_submitted' WHERE application_id=:id"), {"id": application_id})
                elif rule.code == "APPLICATION_STATUS_NOT_ELIGIBLE":
                    conn.execute(text("UPDATE personnel_applications SET status='wp_td_ineligible' WHERE application_id=:id"), {"id": application_id})
                elif rule.code == "PERSONNEL_ORDER_PRESENT":
                    conn.execute(text("UPDATE personnel_applications SET personnel_order_id=:order_id WHERE application_id=:id"), {"order_id": order_id, "id": application_id})
                elif rule.code == "DIRECTOR_RESOLUTION_PRESENT":
                    conn.execute(text("UPDATE personnel_applications SET director_resolution_status='approved' WHERE application_id=:id"), {"id": application_id})
                before = service._evaluate_candidates(conn, [(person_id, application_id)])[0]
                _update_linked_row(conn, rule, rows[rule.code][1])
                after = service._evaluate_candidates(conn, [(person_id, application_id)])[0]
                results[rule.code] = (before, after)

            conn.execute(text("""UPDATE personnel_applications SET status='intake_pending',
                personnel_order_id=NULL,director_resolution_status=NULL WHERE application_id=:id"""), {"id": application_id})
            before = service._evaluate_candidates(conn, [(person_id, application_id)])[0]
            for rule in service.RELATIONSHIP_MATRIX:
                if rule.code not in special_application_rules:
                    _update_linked_row(conn, rule, rows[rule.code][1])
            after = service._evaluate_candidates(conn, [(person_id, application_id)])[0]
            for rule in service.RELATIONSHIP_MATRIX:
                if rule.code not in special_application_rules:
                    results[rule.code] = (before, after)
        yield rows, results


@pytest.mark.parametrize("rule", service.RELATIONSHIP_MATRIX, ids=lambda rule: rule.code)
def test_every_relationship_rule_detects_real_row_and_changes_fingerprint(matrix_graph, rule):
    rows, results = matrix_graph
    before, after = results[rule.code]
    relationship = before["relationship_summary"].get(rule.code)
    assert relationship is not None
    assert relationship["category"] == rule.category
    assert relationship["count"] >= 1
    assert relationship["state_digest"]
    assert relationship["create_allowed"] is rule.create_allowed
    assert relationship["submit_allowed"] is rule.submit_allowed
    assert relationship["approval_allowed"] is rule.approval_allowed
    assert relationship["future_execution_allowed"] is rule.future_execution_allowed
    assert service._stage_admissibility([rule]) == {
        "create": rule.create_allowed,
        "submit": rule.submit_allowed,
        "approve": rule.approval_allowed,
        "future_execution": rule.future_execution_allowed,
    }
    assert relationship["required_hr_decision"] == rule.required_hr_decision
    assert before["stage_admissibility"]["create"] is all(
        item["create_allowed"] for item in before["relationship_summary"].values()
    )
    assert rows[rule.code][0] == rule.table
    assert after["relationship_summary"][rule.code]["state_digest"] != relationship["state_digest"]
    assert after["relationship_fingerprint"] != before["relationship_fingerprint"]
