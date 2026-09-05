"""WP-TD-005 stage 3 fail-closed provenance/catalog fingerprinting.

This module is analysis and approval infrastructure only.  It performs no
domain deletes, writes no tombstones, and exposes no execution endpoint.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection


FINGERPRINT_VERSION = "WP-TD-RELATIONSHIP/v2"
POLICY_VERSION = "WP-TD-005-APPLICANT/v1"
CATALOG_VERSION = "WP-TD-CATALOG/v1"
COMPATIBLE_ALEMBIC_REVISIONS = frozenset({"td005fp3v101", "td005audit401", "td005exec501"})

# Filled from reviewed schemas.  Values are deliberately static: calculating
# an "expected" value from a drifted runtime catalog would turn the safety
# check into a tautology.
EXPECTED_CATALOG_FINGERPRINT = "27aa61cead0a55840991fdaa4ea596c2e30277c254c918f265b50d20fc76f6a6"
EXPECTED_CATALOG_FINGERPRINTS = {
    "td005fp3v101": EXPECTED_CATALOG_FINGERPRINT,
    "td005audit401": "eabb56e613485f5fd72a789821b32403e323235b5437a28e90fb73824b18d1e9",
    "td005exec501": "23a1eee9fbdb2b2aa2a2412f083ed97cc96c004abcdd2c25d4cead3be96e9495",
}

# Every relation from which stage 5 can issue DELETE.  All inbound foreign
# keys to these tables are catalogued, including keys owned by otherwise
# unknown tables.  This prevents an unreviewed CASCADE/SET NULL/RESTRICT from
# being hidden behind a known parent delete.
EXECUTION_DELETE_TABLES = frozenset({
    "personnel_intake_drafts", "personnel_intake_links",
    "personnel_record_events", "ppr_command_executions",
    "personnel_application_lifecycle_audit", "personnel_record_metadata",
    "personnel_applications", "persons",
})

DELETE_RULES = frozenset({
    "ALL_APPLICATIONS_PRESENT",
    "SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED",
    "PPR_EVENT_TOMBSTONE_REQUIRED",
    "PPR_COMMAND_TOMBSTONE_REQUIRED",
    "PPR_METADATA_PRESENT",
    "APPLICATION_EARLY_LIFECYCLE_TOMBSTONE_REQUIRED",
    "INTAKE_LINK_PRESENT",
    "INTAKE_DRAFT_PRESENT",
})
PRESERVE_RULES = frozenset({
    "ENROLLMENT_HISTORY_RETAINED",
    "HR_REVIEW_OVERRIDE_RETAINED",
    "SECURITY_AUDIT_RETAINED",
    "PROVENANCE_STATE_RETAINED",
    "HR_REVIEW_OVERRIDE_HISTORY_RETAINED",
    "HR_IMPORT_ROW_RETAINED",
    "HR_IMPORT_NORMALIZED_RETAINED",
    "TERMINATION_AUDIT_RETAINED",
    "PERSONNEL_ORDER_AUDIT_RETAINED",
    "PERSONNEL_VISIBILITY_RETAINED",
    "LEGACY_IMPORT_STAGE_RETAINED",
    "HR_BASELINE_ENTRY_RETAINED",
    "HR_CHANGE_EVENT_RETAINED",
    "HR_IMPORT_DOCUMENT_CANDIDATE_RETAINED",
    "HR_MONTHLY_REFERENCE_ENTRY_RETAINED",
    "HR_CANONICAL_SNAPSHOT_ENTRY_RETAINED",
    "SECURITY_AUDIT_EMPLOYEE_RETAINED",
})

EXPECTED_RULE_CODES = frozenset({
    "ALL_APPLICATIONS_PRESENT", "SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED",
    "PERSON_ROOT_NOT_ELIGIBLE",
    "APPLICATION_STATUS_NOT_ELIGIBLE", "PERSONNEL_ORDER_PRESENT",
    "DIRECTOR_RESOLUTION_PRESENT", "EMPLOYEE_PRESENT", "LEGACY_PERSONNEL_PRESENT",
    "CONTACT_PRESENT", "CONTACT_ACCESS_PRESENT", "KEY_CONTACT_PRESENT",
    "ORG_UNIT_KEY_STAFF_PRESENT", "ASSIGNMENT_PRESENT", "ENROLLMENT_QUEUE_PRESENT",
    "PPR_EVENT_TOMBSTONE_REQUIRED", "PPR_COMMAND_TOMBSTONE_REQUIRED",
    "PPR_METADATA_PRESENT", "PPR_EDUCATION_PRESENT", "PPR_TRAINING_PRESENT",
    "PPR_RELATIVE_PRESENT", "PPR_EXTERNAL_EMPLOYMENT_PRESENT", "PPR_MILITARY_PRESENT",
    "PHOTO_PRESENT", "PHOTO_PROVENANCE_PRESENT", "TELEGRAM_BINDING_PRESENT",
    "TELEGRAM_ACTIVATION_PRESENT", "VERIFICATION_TASK_PRESENT",
    "VERIFICATION_ATTESTATION_PRESENT", "IDENTITY_RECONCILIATION_PRESENT",
    "HR_CHANGE_EVENT_PRESENT", "INCOMING_DOCUMENT_PRESENT",
    "MERGED_PERSON_REFERENCE_PRESENT", "INTAKE_REVIEW_PRESENT", "INTAKE_TRANSFER_PRESENT",
    "INTAKE_RECONCILIATION_PRESENT", "APPLICATION_BLOCKER_PRESENT",
    "APPLICATION_EARLY_LIFECYCLE_TOMBSTONE_REQUIRED",
    "APPLICATION_OFFICIAL_LIFECYCLE_PRESENT", "APPLICATION_RESOLUTION_AUDIT_PRESENT",
    "ONBOARDING_PRESENT", "INTAKE_LINK_PRESENT", "INTAKE_DRAFT_PRESENT",
    "ENROLLMENT_HISTORY_RETAINED", "HR_REVIEW_OVERRIDE_RETAINED",
    "SECURITY_AUDIT_RETAINED", "PROVENANCE_STATE_RETAINED",
    "HR_REVIEW_OVERRIDE_HISTORY_RETAINED", "HR_IMPORT_ROW_RETAINED",
    "HR_IMPORT_NORMALIZED_RETAINED", "USER_IDENTITY_PRESENT",
    "EMPLOYEE_DOCUMENT_PRESENT", "EMPLOYEE_ASSIGNMENT_LINK_PRESENT",
    "EMPLOYEE_EVENT_PRESENT", "EMPLOYEE_IDENTITY_PRESENT",
    "EMPLOYEE_PROFILE_OVERRIDE_PRESENT", "TERMINATION_RECORD_PRESENT",
    "TERMINATION_AUDIT_RETAINED", "ONBOARDING_ITEM_PRESENT",
    "ONBOARDING_ATTACHMENT_PRESENT", "PERSONNEL_ORDER_ITEM_PRESENT",
    "PERSONNEL_ORDER_SIGNATORY_PRESENT", "PERSONNEL_ORDER_AUDIT_RETAINED",
    "OPERATIONAL_ORDER_SIGNING_PRESENT", "ACCESS_GRANT_RETAINED",
    "PERSONNEL_VISIBILITY_RETAINED", "LEGACY_IMPORT_STAGE_RETAINED",
    "PERSONNEL_MIGRATION_RUN_PRESENT", "HR_BASELINE_ENTRY_RETAINED",
    "HR_CHANGE_EVENT_RETAINED", "HR_IMPORT_DOCUMENT_CANDIDATE_RETAINED",
    "HR_MONTHLY_REFERENCE_ENTRY_RETAINED", "INCOMING_DOCUMENT_PARTICIPATION_PRESENT",
    "INCOMING_DOCUMENT_ASSIGNMENT_PRESENT", "INCOMING_DOCUMENT_ATTACHMENT_PRESENT",
    "INCOMING_DOCUMENT_AUDIT_RETAINED", "INCOMING_DOCUMENT_DEADLINE_CHANGE_PRESENT",
    "INCOMING_DOCUMENT_OPERATIONAL_ORDER_LINK_PRESENT",
    "INCOMING_DOCUMENT_PERSONNEL_ORDER_LINK_PRESENT", "INCOMING_DOCUMENT_TRANSFER_PRESENT",
    "PERSONNEL_ORDER_ATTACHMENT_PRESENT", "PERSONNEL_ORDER_EDITORIAL_BLOCK_PRESENT",
    "PERSONNEL_ORDER_EVIDENCE_SCOPE_PRESENT", "PERSONNEL_ORDER_ITEM_BASIS_PRESENT",
    "PERSONNEL_ORDER_LOCALIZED_TEXT_PRESENT", "PERSONNEL_ORDER_PRINT_PRESENT",
    "ONBOARDING_NOTIFICATION_PRESENT", "ONBOARDING_TASK_AUDIT_PRESENT",
    "USER_LINKAGE_EXECUTE_ITEM_PRESENT", "USER_LINKAGE_REVIEW_DECISION_PRESENT",
    # WP-TD-004 section 11 satellites, now independently fingerprinted.
    "PERSONNEL_ORDER_ITEM_EDITORIAL_BLOCK_PRESENT",
    "ONBOARDING_NOTIFICATION_RECIPIENT_PRESENT",
    "ONBOARDING_NOTIFICATION_DELIVERY_PRESENT", "PERSONNEL_MIGRATION_ITEM_PRESENT",
    "ONBOARDING_MENTOR_PRESENT", "ONBOARDING_ASSIGNEE_PRESENT",
    "VERIFICATION_VERIFIER_PRESENT", "IDENTITY_RECONCILIATION_EMPLOYEE_PRESENT",
    "PPR_EDUCATION_EMPLOYEE_CONTEXT_PRESENT", "PPR_TRAINING_EMPLOYEE_CONTEXT_PRESENT",
    "PPR_EXTERNAL_EMPLOYMENT_CONTEXT_PRESENT", "PPR_MILITARY_CONTEXT_PRESENT",
    "PPR_EVENT_EMPLOYEE_CONTEXT_PRESENT", "HR_CANONICAL_SNAPSHOT_ENTRY_RETAINED",
    "SECURITY_AUDIT_EMPLOYEE_RETAINED", "TASK_USER_SATELLITE_PRESENT",
    "TASK_REPORT_USER_SATELLITE_PRESENT", "TASK_AUDIT_USER_SATELLITE_PRESENT",
    "AUDIT_LOG_USER_SATELLITE_PRESENT", "TASK_EVENT_USER_SATELLITE_PRESENT",
    "TASK_EVENT_RECIPIENT_USER_SATELLITE_PRESENT",
    "TASK_EVENT_DELIVERY_USER_SATELLITE_PRESENT",
    "NOTIFICATION_USER_SATELLITE_PRESENT", "TELEGRAM_USER_SATELLITE_PRESENT",
    "USER_ORG_RELATION_PRESENT", "USER_SUPERVISOR_RELATION_PRESENT",
    "ORG_UNIT_MANAGER_RELATION_PRESENT",
})

STRUCTURAL_TABLES = frozenset({
    "persons", "personnel_applications", "test_personnel_provenance",
    "test_personnel_deletion_requests", "test_personnel_deletion_targets",
    "test_personnel_deletion_manifest_v2_targets", "test_personnel_deletion_decisions",
    "test_personnel_deletion_history",
    "test_personnel_deletion_record_event_tombstones",
    "test_personnel_deletion_command_tombstones",
    "test_personnel_deletion_lifecycle_tombstones",
})
ADDITIONAL_CATALOG_TABLES = frozenset({
    "task_reports", "task_audit_log", "audit_log", "task_event_recipients",
    "task_event_deliveries", "user_supervisors", "org_unit_managers",
})
LOGICAL_ID_COLUMNS = frozenset({
    "person_id", "application_id", "employee_id", "user_id", "target_person_id",
    "target_employee_id", "employee_context_id", "source_application_id",
    "mentor_employee_id", "assignee_employee_id", "verifier_employee_id",
    "proposed_employee_id", "sender_person_id", "sender_employee_id",
    "addressee_employee_id", "actor_employee_id", "subject_employee_id",
    "signed_by_employee_id", "target_id", "target_type",
})


class FingerprintGateError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    return value


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        _canonical_value(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _rule_registry(rules: Sequence[Any]) -> list[dict[str, Any]]:
    codes = [str(rule.code) for rule in rules]
    if len(codes) != len(set(codes)) or set(codes) != EXPECTED_RULE_CODES:
        raise FingerprintGateError(
            "TD_RELATIONSHIP_REGISTRY_MISMATCH",
            "The server relationship registry is incomplete or contains an unknown rule.",
        )
    registry = []
    for rule in rules:
        code = str(rule.code)
        action = "DELETE" if code in DELETE_RULES else "PRESERVE" if code in PRESERVE_RULES else "BLOCK"
        registry.append({
            "code": code,
            "table": str(rule.table),
            "action": action,
            "category": str(rule.category),
            "lookup": str(rule.lookup),
            "keys": sorted(map(str, rule.keys)),
            "sql_digest": canonical_hash(" ".join(str(rule.sql).split())),
        })
    return sorted(registry, key=lambda item: item["code"])


def catalog_snapshot(conn: Connection, rules: Sequence[Any]) -> dict[str, Any]:
    registry = _rule_registry(rules)
    revision_rows = conn.execute(text(
        "SELECT version_num FROM public.alembic_version ORDER BY version_num"
    )).scalars().all()
    revision_tables = (
        {"test_personnel_deletion_execution_attempts"}
        if revision_rows == ["td005exec501"] else set()
    )
    registered_tables = sorted(
        STRUCTURAL_TABLES | revision_tables | ADDITIONAL_CATALOG_TABLES
        | {item["table"] for item in registry}
    )
    columns = [dict(row) for row in conn.execute(text("""SELECT
            c.relname AS table_name, a.attname AS column_name,
            pg_catalog.format_type(a.atttypid,a.atttypmod) AS data_type,
            a.attnotnull AS not_null, a.attidentity AS identity_kind,
            a.attgenerated AS generated_kind,
            pg_get_expr(default_def.adbin,default_def.adrelid) AS default_expression,
            CASE WHEN a.attcollation=0 THEN NULL ELSE collation_def.collname END AS collation
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
        LEFT JOIN pg_catalog.pg_attrdef default_def
          ON default_def.adrelid=a.attrelid AND default_def.adnum=a.attnum
        LEFT JOIN pg_catalog.pg_collation collation_def ON collation_def.oid=a.attcollation
        WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m')
          AND c.relname=ANY(:tables) AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY c.relname,a.attnum"""), {"tables": registered_tables}).mappings()]
    present_tables = {str(row["table_name"]) for row in columns}
    missing_tables = sorted(set(registered_tables) - present_tables)
    foreign_keys = [dict(row) for row in conn.execute(text("""SELECT
            source.relname AS source_table, constraint_def.conname AS constraint_name,
            array_agg(source_column.attname ORDER BY source_key.ordinality) AS source_columns,
            target.relname AS target_table,
            array_agg(target_column.attname ORDER BY source_key.ordinality) AS target_columns,
            CASE constraint_def.confdeltype WHEN 'a' THEN 'NO ACTION' WHEN 'r' THEN 'RESTRICT'
                WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL'
                WHEN 'd' THEN 'SET DEFAULT' ELSE constraint_def.confdeltype::text END AS on_delete
        FROM pg_catalog.pg_constraint constraint_def
        JOIN pg_catalog.pg_class source ON source.oid=constraint_def.conrelid
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid=source.relnamespace
        JOIN pg_catalog.pg_class target ON target.oid=constraint_def.confrelid
        JOIN unnest(constraint_def.conkey) WITH ORDINALITY source_key(attnum,ordinality) ON TRUE
        JOIN unnest(constraint_def.confkey) WITH ORDINALITY target_key(attnum,ordinality)
          ON target_key.ordinality=source_key.ordinality
        JOIN pg_catalog.pg_attribute source_column
          ON source_column.attrelid=source.oid AND source_column.attnum=source_key.attnum
        JOIN pg_catalog.pg_attribute target_column
          ON target_column.attrelid=target.oid AND target_column.attnum=target_key.attnum
        WHERE namespace.nspname='public' AND constraint_def.contype='f'
          AND (source.relname=ANY(:tables) OR target.relname=ANY(:delete_tables)
               OR target.relname IN ('employees','users'))
        GROUP BY source.relname,constraint_def.conname,target.relname,constraint_def.confdeltype
        ORDER BY source.relname,constraint_def.conname"""), {
            "tables": registered_tables,
            "delete_tables": sorted(EXECUTION_DELETE_TABLES),
        }).mappings()]
    triggers = [dict(row) for row in conn.execute(text("""SELECT
            table_def.relname AS table_name, trigger_def.tgname AS trigger_name,
            regexp_replace(pg_get_triggerdef(trigger_def.oid),'\\s+',' ','g') AS definition,
            regexp_replace(pg_get_functiondef(trigger_def.tgfoid),'\\s+',' ','g') AS function_definition
        FROM pg_catalog.pg_trigger trigger_def
        JOIN pg_catalog.pg_class table_def ON table_def.oid=trigger_def.tgrelid
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid=table_def.relnamespace
        WHERE namespace.nspname='public' AND NOT trigger_def.tgisinternal
          AND table_def.relname=ANY(:tables)
        ORDER BY table_def.relname,trigger_def.tgname"""), {"tables": registered_tables}).mappings()]
    logical_columns = [dict(row) for row in conn.execute(text("""SELECT
            table_def.relname AS table_name, column_def.attname AS column_name
        FROM pg_catalog.pg_class table_def
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid=table_def.relnamespace
        JOIN pg_catalog.pg_attribute column_def ON column_def.attrelid=table_def.oid
        WHERE namespace.nspname='public' AND table_def.relkind IN ('r','p')
          AND column_def.attnum>0 AND NOT column_def.attisdropped
          AND column_def.attname=ANY(:columns)
        ORDER BY table_def.relname,column_def.attname"""), {
            "columns": sorted(LOGICAL_ID_COLUMNS),
        }).mappings()]
    return {
        "catalog_version": CATALOG_VERSION,
        "alembic_revisions": sorted(map(str, revision_rows)),
        "registered_tables": registered_tables,
        "missing_tables": missing_tables,
        "columns": columns,
        "foreign_keys": foreign_keys,
        "protective_triggers": triggers,
        "logical_id_columns": logical_columns,
        "relationship_registry": registry,
    }


def catalog_state(
    conn: Connection, rules: Sequence[Any], *, enforce: bool = True,
) -> dict[str, Any]:
    snapshot = catalog_snapshot(conn, rules)
    digest = canonical_hash(snapshot)
    revision_compatible = (
        len(snapshot["alembic_revisions"]) == 1
        and snapshot["alembic_revisions"][0] in COMPATIBLE_ALEMBIC_REVISIONS
    )
    expected_fingerprint = (
        EXPECTED_CATALOG_FINGERPRINTS.get(snapshot["alembic_revisions"][0])
        if len(snapshot["alembic_revisions"]) == 1 else None
    )
    compatible = (
        revision_compatible
        and not snapshot["missing_tables"]
        and digest == expected_fingerprint
    )
    result = {
        "version": CATALOG_VERSION,
        "fingerprint": digest,
        "compatible": compatible,
        "revision_compatible": revision_compatible,
        "missing_tables": snapshot["missing_tables"],
    }
    if enforce and not compatible:
        raise FingerprintGateError(
            "TD_CATALOG_MISMATCH",
            "The PostgreSQL catalog or Alembic revision is not allowlisted.",
        )
    return result


def provenance_snapshot(conn: Connection, person_ids: Iterable[int]) -> list[dict[str, Any]]:
    environment = (os.getenv("APP_ENV") or "dev").strip().lower()
    result = []
    for person_id in sorted({int(value) for value in person_ids}):
        row = conn.execute(text("""SELECT provenance_id,provenance_version,
                provenance_state,source_artifact_hash,created_at,expires_at,
                (provenance_state='ACTIVE'
                 AND source_artifact_hash ~ '^[0-9a-f]{64}$'
                 AND (expires_at IS NULL OR expires_at>transaction_timestamp())) AS active
            FROM public.test_personnel_provenance
            WHERE target_type='PERSON' AND target_id=:person_id AND environment=:environment
            ORDER BY provenance_version DESC,provenance_id DESC LIMIT 1"""), {
                "person_id": person_id, "environment": environment,
            }).mappings().one_or_none()
        result.append({
            "person_id": person_id,
            "environment": environment,
            "provenance_id": int(row["provenance_id"]) if row else None,
            "provenance_version": int(row["provenance_version"]) if row else None,
            "provenance_state": str(row["provenance_state"]) if row else "MISSING",
            "source_artifact_hash": str(row["source_artifact_hash"]) if row else None,
            "created_at": row["created_at"] if row else None,
            "expires_at": row["expires_at"] if row else None,
            "active": bool(row and row["active"]),
        })
    return result


def build_fingerprint(
    conn: Connection,
    *,
    candidates: Sequence[Mapping[str, Any]],
    basis: str,
    rules: Sequence[Any],
) -> dict[str, Any]:
    catalog = catalog_state(conn, rules)
    registry = _rule_registry(rules)
    roots: dict[int, set[int]] = {}
    target_snapshots = []
    present_block_rules: set[str] = set()
    for candidate in candidates:
        person_id = int(candidate["person_id"])
        application_id = int(candidate["application_id"])
        roots.setdefault(person_id, set()).add(application_id)
        snapshot = candidate["relationship_snapshot"]
        relationships = snapshot.get("relationships") or {}
        if set(relationships) != EXPECTED_RULE_CODES:
            raise FingerprintGateError(
                "TD_RELATIONSHIP_SNAPSHOT_INCOMPLETE",
                "Every registered relationship rule, including absent rules, must be fingerprinted.",
            )
        for item in registry:
            if item["action"] == "BLOCK" and int(relationships[item["code"]]["count"]) > 0:
                present_block_rules.add(item["code"])
        target_snapshots.append({
            "person_id": person_id,
            "application_id": application_id,
            "relationship_fingerprint": str(candidate["relationship_fingerprint"]),
        })
    manifest = [
        {"root_type": "PERSON", "person_id": person_id, "application_ids": sorted(application_ids)}
        for person_id, application_ids in sorted(roots.items())
    ]
    provenance = provenance_snapshot(conn, roots)
    blockers = sorted(present_block_rules)
    if basis != "PROVENANCE":
        blockers.append("LEGACY_MANIFEST_NOT_EXECUTABLE")
    if any(not item["active"] for item in provenance):
        blockers.append("ACTIVE_PERSON_PROVENANCE_REQUIRED")
    payload = {
        "fingerprint_version": FINGERPRINT_VERSION,
        "policy_version": POLICY_VERSION,
        "catalog_version": catalog["version"],
        "catalog_fingerprint": catalog["fingerprint"],
        "basis": basis,
        "manifest": manifest,
        "targets": sorted(target_snapshots, key=lambda item: (item["person_id"], item["application_id"])),
        "provenance": provenance,
        "relationship_registry": registry,
    }
    return {
        **payload,
        "fingerprint": canonical_hash(payload),
        "policy_execution_ready": not blockers,
        "blockers": sorted(set(blockers)),
    }
