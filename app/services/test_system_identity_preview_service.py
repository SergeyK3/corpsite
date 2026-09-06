"""WP-TD-006B read-only search and preview for proven test User/Role rows."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.test_personnel_deletion_fingerprint_service import canonical_hash


POLICY_VERSION = "WP-TD-006B/v2"
CATALOG_VERSION = "WP-TD-SYSTEM-CATALOG/v2"
FINGERPRINT_VERSION = "WP-TD-SYSTEM-RELATIONSHIP/v1"
MANIFEST_VERSION = "WP-TD-SYSTEM-MANIFEST/v1"
SUPPORTED_ALEMBIC_REVISIONS = frozenset({"td006afnd601"})
EXPECTED_CATALOG_FINGERPRINTS = {
    "td006afnd601": "516e9c2db97527314e44434c8d090b4c91e89109018cf4d60ca2320922ed62f8",
}
MAX_RESULTS = 200

OBJECT_TABLES = {"USER": ("users", "user_id"), "ROLE": ("roles", "role_id")}
SEARCH_FIELDS = {
    "USER": frozenset({"full_name", "login"}),
    "ROLE": frozenset({"name", "code"}),
}
CANONICAL_ROLE_CODES = frozenset({"ADMIN", "HR_HEAD"})
HISTORICAL_AUTHORSHIP = "HISTORICAL_AUTHORSHIP"

BLOCKING = "BLOCKING"
PRESERVE = "PRESERVE"
REBIND = "REBIND_HISTORICAL_AUTHORSHIP"
DELETE_ALLOWLIST = "DELETE_ALLOWLIST"

# CASCADE is never accepted merely because PostgreSQL reports CASCADE.  Each
# future child-delete relation is named here and remains non-executable in 006B.
CASCADE_DELETE_ALLOWLIST = frozenset({
    ("employee_onboarding_notification_deliveries", "user_id", "users"),
    ("employee_onboarding_notification_recipients", "user_id", "users"),
    ("notifications", "recipient_user_id", "users"),
    ("org_unit_managers", "user_id", "users"),
    ("personnel_visibility_assignments", "target_user_id", "users"),
    ("task_event_deliveries", "user_id", "users"),
    ("task_event_recipients", "user_id", "users"),
    ("tg_bindings", "user_id", "users"),
    ("user_org_units", "user_id", "users"),
    ("user_supervisors", "user_id", "users"),
})

# Exact application-level links without a User/Role FK.  Optional legacy and
# staging objects are capabilities: their mere presence is not catalog drift.
# A relationship is emitted only when its value exactly matches the selected
# target's technical ID, code, or name.
LOGICAL_RELATIONS = (
    ("USER", "contact_access", "changed_by_user_id", "user_id", REBIND),
    ("USER", "hr_baseline_deletion_log", "published_by", "user_id", REBIND),
    ("USER", "hr_import_diff_removals", "decided_by", "user_id", REBIND),
    ("USER", "personnel_migration_runs", "started_by", "user_id", REBIND),
    ("USER", "regular_tasks_stg", "created_by_user_id", "user_id", REBIND),
    ("USER", "stg_regular_tasks_30", "created_by_user_id", "user_id", REBIND),
    ("USER", "test_personnel_deletion_decisions", "actor_user_id", "user_id", REBIND),
    ("USER", "test_personnel_deletion_execution_attempts", "executor_user_id", "user_id", REBIND),
    ("USER", "test_personnel_deletion_history", "actor_user_id", "user_id", REBIND),
    ("USER", "test_personnel_deletion_requests", "initiated_by_user_id", "user_id", REBIND),
    ("USER", "test_personnel_provenance", "created_by_user_id", "user_id", REBIND),
    ("ROLE", "key_contacts", "role_code", "code", BLOCKING),
    ("ROLE", "key_contacts", "role_name", "name", BLOCKING),
    ("ROLE", "org_unit_key_staff", "role_code", "code", BLOCKING),
    ("ROLE", "regular_tasks_stg", "executor_role_id", "role_id", BLOCKING),
    ("ROLE", "regular_tasks_stg", "executorrolecode", "code", BLOCKING),
    ("ROLE", "regular_tasks_stg", "executorrolename_ru", "name", BLOCKING),
    ("ROLE", "regular_tasks_stg", "initiator_role_id", "role_id", BLOCKING),
    ("ROLE", "regular_tasks_stg", "reviewer_role_code", "code", BLOCKING),
    ("ROLE", "regular_tasks_stg", "reviewer_role_name_ru", "name", BLOCKING),
    ("ROLE", "report_catalog", "owner_role_code", "code", BLOCKING),
    ("ROLE", "stg_import_reports", "executor_role_code", "code", BLOCKING),
    ("ROLE", "stg_import_reports", "reviewer_role_code", "code", BLOCKING),
    ("ROLE", "stg_import_roles", "role_code", "code", BLOCKING),
    ("ROLE", "stg_regular_tasks_30", "executor_role_id", "role_id", BLOCKING),
    ("ROLE", "stg_regular_tasks_30", "executorrolecode", "code", BLOCKING),
    ("ROLE", "stg_regular_tasks_30", "executorrolename_ru", "name", BLOCKING),
    ("ROLE", "stg_regular_tasks_30", "initiator_role_id", "role_id", BLOCKING),
    ("ROLE", "stg_regular_tasks_30", "reviewer_role_code", "code", BLOCKING),
    ("ROLE", "stg_regular_tasks_30", "reviewer_role_name_ru", "name", BLOCKING),
    ("ROLE", "test_personnel_deletion_decisions", "actor_role_code", "code", BLOCKING),
    ("ROLE", "test_personnel_deletion_history", "actor_role_code", "code", BLOCKING),
)

# Exact false positives in the conservative unknown-logical-column detector.
IGNORED_IDENTITY_LIKE_COLUMNS = frozenset({
    ("access_grants", "access_role_id"),
    ("access_roles", "access_role_id"),
    ("permission_template", "access_role_id"),
    ("permission_template_contour_rule", "access_role_id"),
    ("person_telegram_bindings", "telegram_user_id"),
    ("tg_bindings", "tg_user_id"),
    ("users", "user_id"),
    ("roles", "role_id"),
})

AUTHORSHIP_COLUMN_NAMES = frozenset({
    "actor_user_id", "approver_user_id", "assigned_by_user_id",
    "cancelled_by_user_id", "canonicalized_by_user_id", "changed_by_user_id",
    "closed_by_user_id", "completed_by_user_id", "confirmer_user_id",
    "created_by", "created_by_user_id", "decided_by", "deleted_by",
    "director_resolution_by_user_id", "edited_by_user_id", "enrolled_by_user_id",
    "generated_by", "granted_by_user_id", "imported_by", "initiator_user_id",
    "issued_by_user_id", "performed_by", "promoted_by", "promoted_by_user_id",
    "published_by", "published_by_user_id", "reconciled_by_user_id",
    "record_creator_user_id", "registered_by_user_id", "requested_by_user_id",
    "resolved_by_user_id", "reviewed_by", "reviewed_by_user_id",
    "signed_by_user_id", "started_by", "submitted_by", "transferred_by_user_id",
    "uploaded_by_user_id", "verified_by", "verifier_user_id",
})


class SystemIdentityPreviewError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@contextmanager
def _read_only_connection():
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(text(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            ))
            yield conn
        finally:
            transaction.rollback()


def normalize_mask(mask: str) -> str:
    value = " ".join(unicodedata.normalize("NFC", mask or "").strip().split())
    if not 3 <= len(value) <= 100:
        raise SystemIdentityPreviewError(
            "TD_SYSTEM_MASK_LENGTH", "Mask length must be between 3 and 100.", 422,
        )
    if sum(character in "*?" for character in value) > 10:
        raise SystemIdentityPreviewError(
            "TD_SYSTEM_MASK_WILDCARDS", "Mask may contain at most 10 wildcards.", 422,
        )
    if sum(character.isalnum() for character in value) < 3:
        raise SystemIdentityPreviewError(
            "TD_SYSTEM_MASK_TOO_BROAD", "Mask needs at least 3 alphanumeric literals.", 422,
        )
    return value


def glob_to_ilike(mask: str) -> str:
    result = []
    for character in normalize_mask(mask):
        if character in "\\%_":
            result.append("\\" + character)
        elif character == "*":
            result.append("%")
        elif character == "?":
            result.append("_")
        else:
            result.append(character)
    return "".join(result)


def _looks_like_identity_logical_column(column_name: str) -> bool:
    return (
        column_name in AUTHORSHIP_COLUMN_NAMES
        or column_name in {"user_id", "role_id", "role_code", "role_name"}
        or column_name.endswith("_user_id")
        or column_name.endswith("_role_id")
        or column_name.endswith("_role_code")
        or "_role_name" in column_name
        or column_name in {"executorrolecode", "executorrolename_ru"}
    )


def _catalog_snapshot(conn: Connection) -> dict[str, Any]:
    revisions = list(map(str, conn.execute(text(
        "SELECT version_num FROM public.alembic_version ORDER BY version_num"
    )).scalars()))
    columns = [dict(row) for row in conn.execute(text("""SELECT
            namespace.nspname AS schema_name, table_def.relname AS table_name,
            table_def.relkind AS relation_kind, column_def.attname AS column_name,
            pg_catalog.format_type(column_def.atttypid,column_def.atttypmod) AS data_type,
            column_def.attnotnull AS not_null, column_def.attidentity AS identity_kind,
            column_def.attgenerated AS generated_kind,
            pg_get_expr(default_def.adbin,default_def.adrelid) AS default_expression,
            CASE WHEN column_def.attcollation=0 THEN NULL ELSE collation_def.collname END AS collation
        FROM pg_catalog.pg_class table_def
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid=table_def.relnamespace
        JOIN pg_catalog.pg_attribute column_def ON column_def.attrelid=table_def.oid
        LEFT JOIN pg_catalog.pg_attrdef default_def
          ON default_def.adrelid=table_def.oid AND default_def.adnum=column_def.attnum
        LEFT JOIN pg_catalog.pg_collation collation_def
          ON collation_def.oid=column_def.attcollation
        WHERE namespace.nspname='public' AND table_def.relkind IN ('r','p')
          AND table_def.relname IN ('users','roles','test_system_identity_provenance')
          AND NOT (table_def.relname='roles' AND column_def.attname='is_active')
          AND column_def.attnum>0 AND NOT column_def.attisdropped
        ORDER BY table_def.relname,column_def.attnum""")).mappings()]
    foreign_keys = [dict(row) for row in conn.execute(text("""SELECT
            source.relname AS source_table, constraint_def.conname AS constraint_name,
            array_agg(source_column.attname ORDER BY source_key.ordinality) AS source_columns,
            target.relname AS target_table,
            array_agg(target_column.attname ORDER BY source_key.ordinality) AS target_columns,
            CASE constraint_def.confdeltype WHEN 'a' THEN 'NO ACTION'
                WHEN 'r' THEN 'RESTRICT' WHEN 'c' THEN 'CASCADE'
                WHEN 'n' THEN 'SET NULL' WHEN 'd' THEN 'SET DEFAULT'
                ELSE constraint_def.confdeltype::text END AS on_delete
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
          AND target.relname IN ('users','roles')
        GROUP BY source.relname,constraint_def.conname,target.relname,constraint_def.confdeltype
        ORDER BY source.relname,constraint_def.conname""")).mappings()]
    relevant_trigger_tables = {
        "users", "roles", "test_system_identity_provenance",
        *(str(row["source_table"]) for row in foreign_keys),
    }
    triggers = [dict(row) for row in conn.execute(text("""SELECT
            table_def.relname AS table_name, trigger_def.tgname AS trigger_name,
            regexp_replace(pg_get_triggerdef(trigger_def.oid),'\\s+',' ','g') AS definition,
            regexp_replace(pg_get_functiondef(trigger_def.tgfoid),'\\s+',' ','g') AS function_definition
        FROM pg_catalog.pg_trigger trigger_def
        JOIN pg_catalog.pg_class table_def ON table_def.oid=trigger_def.tgrelid
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid=table_def.relnamespace
        WHERE namespace.nspname='public' AND NOT trigger_def.tgisinternal
          AND table_def.relname=ANY(:table_names)
        ORDER BY table_def.relname,trigger_def.tgname"""), {
            "table_names": sorted(relevant_trigger_tables),
        }).mappings()]
    role_active_shapes = [dict(row) for row in conn.execute(text("""SELECT
            pg_catalog.format_type(column_def.atttypid,column_def.atttypmod) AS data_type,
            column_def.attnotnull AS not_null,
            pg_get_expr(default_def.adbin,default_def.adrelid) AS default_expression
        FROM pg_catalog.pg_class table_def
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid=table_def.relnamespace
        JOIN pg_catalog.pg_attribute column_def ON column_def.attrelid=table_def.oid
        LEFT JOIN pg_catalog.pg_attrdef default_def
          ON default_def.adrelid=table_def.oid AND default_def.adnum=column_def.attnum
        WHERE namespace.nspname='public' AND table_def.relname='roles'
          AND column_def.attname='is_active' AND NOT column_def.attisdropped""")).mappings()]
    violations: list[str] = []
    if role_active_shapes and role_active_shapes != [{
        "data_type": "boolean", "not_null": True, "default_expression": "true",
    }]:
        violations.append("roles.is_active has an unsupported shape")

    physical_columns = {
        (str(row["source_table"]), str(row["source_columns"][0]))
        for row in foreign_keys if len(row["source_columns"]) == 1
    }
    registered_columns = {
        (table_name, column_name)
        for _, table_name, column_name, _, _ in LOGICAL_RELATIONS
    }
    candidate_columns = [
        (str(row["table_name"]), str(row["column_name"]))
        for row in conn.execute(text("""SELECT table_def.relname AS table_name,
                column_def.attname AS column_name
            FROM pg_catalog.pg_class table_def
            JOIN pg_catalog.pg_namespace namespace ON namespace.oid=table_def.relnamespace
            JOIN pg_catalog.pg_attribute column_def ON column_def.attrelid=table_def.oid
            WHERE namespace.nspname='public' AND table_def.relkind IN ('r','p')
              AND column_def.attnum>0 AND NOT column_def.attisdropped
            ORDER BY table_def.relname,column_def.attnum""")).mappings()
        if _looks_like_identity_logical_column(str(row["column_name"]))
    ]
    unknown_logical_columns = sorted(
        signature for signature in candidate_columns
        if signature not in physical_columns
        and signature not in registered_columns
        and signature not in IGNORED_IDENTITY_LIKE_COLUMNS
    )
    if unknown_logical_columns:
        violations.extend(
            f"unregistered logical identity column: {table_name}.{column_name}"
            for table_name, column_name in unknown_logical_columns
        )

    technical_identity = dict(conn.execute(text("""SELECT
            count(*)::int AS row_count,
            count(*) FILTER (WHERE is_system_identity=TRUE
                AND system_identity_purpose='HISTORICAL_AUTHORSHIP'
                AND is_active=FALSE AND login IS NULL AND password_hash IS NULL
                AND employee_id IS NULL AND google_login IS NULL
                AND phone IS NULL AND telegram_id IS NULL
                AND telegram_username IS NULL AND unit_id IS NULL)::int AS valid_count
        FROM public.users
        WHERE is_system_identity=TRUE
           OR system_identity_purpose='HISTORICAL_AUTHORSHIP'""")).mappings().one())
    return {
        "catalog_version": CATALOG_VERSION,
        "alembic_revisions": revisions,
        "identity_columns": columns,
        "incoming_identity_foreign_keys": foreign_keys,
        "protective_triggers": triggers,
        "technical_identity": technical_identity,
        "catalog_violations": violations,
        "contract": {
            "search_fields": {key: sorted(value) for key, value in sorted(SEARCH_FIELDS.items())},
            "canonical_role_codes": sorted(CANONICAL_ROLE_CODES),
            "cascade_delete_allowlist": sorted(CASCADE_DELETE_ALLOWLIST),
            "logical_relations": sorted(LOGICAL_RELATIONS),
            "ignored_identity_like_columns": sorted(IGNORED_IDENTITY_LIKE_COLUMNS),
            "active_role_guard": {
                "column": "roles.is_active",
                "missing_means_active": False,
                "present_shape": "boolean not null default true",
            },
        },
    }


def catalog_state(conn: Connection, *, enforce: bool = True) -> dict[str, Any]:
    snapshot = _catalog_snapshot(conn)
    fingerprint = canonical_hash(snapshot)
    revisions = snapshot["alembic_revisions"]
    revision_compatible = len(revisions) == 1 and revisions[0] in SUPPORTED_ALEMBIC_REVISIONS
    expected = EXPECTED_CATALOG_FINGERPRINTS.get(revisions[0]) if len(revisions) == 1 else None
    compatible = revision_compatible and fingerprint == expected
    result = {
        "version": CATALOG_VERSION,
        "fingerprint": fingerprint,
        "compatible": compatible,
        "revision_compatible": revision_compatible,
    }
    if enforce and not compatible:
        raise SystemIdentityPreviewError(
            "TD_SYSTEM_CATALOG_MISMATCH",
            "The system-identity catalog or Alembic revision is not allowlisted.",
        )
    return result


def _normalize_object_type(value: str) -> str:
    object_type = str(value or "").strip().upper()
    if object_type not in OBJECT_TABLES:
        raise SystemIdentityPreviewError(
            "TD_SYSTEM_OBJECT_TYPE_FORBIDDEN", "Only USER and ROLE are supported.", 422,
        )
    return object_type


def _typed_ids(values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = sorted({
        (_normalize_object_type(str(value["object_type"])), int(value["object_id"]))
        for value in values
    })
    if not result or any(object_id <= 0 for _, object_id in result):
        raise SystemIdentityPreviewError(
            "TD_SYSTEM_EXACT_IDS_REQUIRED", "Positive exact typed IDs are required.", 422,
        )
    if len(result) > MAX_RESULTS:
        raise SystemIdentityPreviewError(
            "TD_SYSTEM_PREVIEW_TOO_BROAD", "Preview exceeds 200 candidates.", 422,
        )
    return [
        {"object_type": object_type, "object_id": object_id}
        for object_type, object_id in result
    ]


def target_list_hash(targets: Sequence[Mapping[str, Any]]) -> str:
    return canonical_hash({"version": MANIFEST_VERSION, "targets": _typed_ids(targets)})


def search_candidates(
    *, object_type: str, field: str, mask: str | None, object_ids: Sequence[int],
) -> dict[str, Any]:
    normalized_type = _normalize_object_type(object_type)
    normalized_field = str(field or "").strip()
    if normalized_field not in SEARCH_FIELDS[normalized_type]:
        raise SystemIdentityPreviewError(
            "TD_SYSTEM_SEARCH_FIELD_FORBIDDEN",
            f"Field {normalized_field!r} is not searchable for {normalized_type}.", 422,
        )
    ids = sorted({int(value) for value in object_ids})
    if any(value <= 0 for value in ids):
        raise SystemIdentityPreviewError(
            "TD_SYSTEM_EXACT_IDS_REQUIRED", "Technical IDs must be positive.", 422,
        )
    if not mask and not ids:
        raise SystemIdentityPreviewError(
            "TD_SYSTEM_SEARCH_EMPTY", "A safe mask or exact technical IDs are required.", 422,
        )
    table_name, id_column = OBJECT_TABLES[normalized_type]
    clauses: list[str] = []
    params: dict[str, Any] = {"object_type": normalized_type, "limit": MAX_RESULTS + 1}
    normalized_mask = None
    if mask:
        normalized_mask = normalize_mask(mask)
        params["pattern"] = glob_to_ilike(mask)
        clauses.append(
            f'normalize(target."{normalized_field}",NFC) COLLATE "und-x-icu" '
            "ILIKE :pattern ESCAPE E'\\\\'"
        )
    if ids:
        params["object_ids"] = ids
        clauses.append(f'target."{id_column}"=ANY(:object_ids)')
    historical_clause = (
        "AND NOT (target.is_system_identity=TRUE "
        "AND target.system_identity_purpose='HISTORICAL_AUTHORSHIP')"
        if normalized_type == "USER" else ""
    )
    label_columns = (
        "target.full_name AS label,target.login AS secondary_label"
        if normalized_type == "USER"
        else "target.name AS label,target.code AS secondary_label"
    )
    with _read_only_connection() as conn:
        catalog = catalog_state(conn)
        rows = conn.execute(text(f"""SELECT target."{id_column}" AS object_id,
                {label_columns}
            FROM public."{table_name}" target
            WHERE ({' OR '.join(clauses)}) {historical_clause}
              AND EXISTS (
                  SELECT 1 FROM public.test_system_identity_provenance provenance
                  WHERE provenance.object_type=:object_type
                    AND provenance.object_id=target."{id_column}"
              )
            ORDER BY target."{id_column}" LIMIT :limit"""), params).mappings().all()
    if len(rows) > MAX_RESULTS:
        raise SystemIdentityPreviewError(
            "TD_SYSTEM_SEARCH_TOO_BROAD", "Search exceeds 200 candidates.", 422,
        )
    items = [{
        "object_type": normalized_type,
        "object_id": int(row["object_id"]),
        "label": str(row["label"] or "").strip() or f"{normalized_type} #{row['object_id']}",
        "secondary_label": str(row["secondary_label"]) if row["secondary_label"] else None,
    } for row in rows]
    typed = [{"object_type": item["object_type"], "object_id": item["object_id"]} for item in items]
    return {
        "items": items,
        "count": len(items),
        "typed_ids": typed,
        "target_list_hash": target_list_hash(typed) if typed else canonical_hash({
            "version": MANIFEST_VERSION, "targets": [],
        }),
        "normalized_mask": normalized_mask,
        "catalog": catalog,
    }


def _relationship_classification(foreign_key: Mapping[str, Any]) -> str:
    source_columns = list(map(str, foreign_key["source_columns"]))
    if len(source_columns) != 1:
        return BLOCKING
    signature = (
        str(foreign_key["source_table"]), source_columns[0],
        str(foreign_key["target_table"]),
    )
    if signature in {
        ("test_system_identity_provenance", "user_id", "users"),
        ("test_system_identity_provenance", "role_id", "roles"),
    }:
        return PRESERVE
    on_delete = str(foreign_key["on_delete"])
    if on_delete == "CASCADE":
        if signature not in CASCADE_DELETE_ALLOWLIST:
            raise SystemIdentityPreviewError(
                "TD_SYSTEM_RELATIONSHIP_REGISTRY_MISMATCH",
                "An ON DELETE CASCADE relation is not in the exact future delete allowlist.",
            )
        return DELETE_ALLOWLIST
    if on_delete == "SET NULL":
        return PRESERVE
    if (
        str(foreign_key["target_table"]) == "users"
        and source_columns[0] in AUTHORSHIP_COLUMN_NAMES
    ):
        return REBIND
    return BLOCKING


def _catalog_foreign_keys(conn: Connection, target_type: str) -> list[dict[str, Any]]:
    target_table = OBJECT_TABLES[target_type][0]
    return [dict(row) for row in conn.execute(text("""SELECT
            source.relname AS source_table, constraint_def.conname AS constraint_name,
            array_agg(source_column.attname ORDER BY source_key.ordinality) AS source_columns,
            target.relname AS target_table,
            array_agg(target_column.attname ORDER BY source_key.ordinality) AS target_columns,
            CASE constraint_def.confdeltype WHEN 'a' THEN 'NO ACTION'
                WHEN 'r' THEN 'RESTRICT' WHEN 'c' THEN 'CASCADE'
                WHEN 'n' THEN 'SET NULL' WHEN 'd' THEN 'SET DEFAULT'
                ELSE constraint_def.confdeltype::text END AS on_delete
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
          AND target.relname=:target_table
        GROUP BY source.relname,constraint_def.conname,target.relname,constraint_def.confdeltype
        ORDER BY source.relname,constraint_def.conname"""), {
            "target_table": target_table,
        }).mappings()]


def _physical_relationships(
    conn: Connection, targets: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, int], list[dict[str, Any]]]:
    result: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    by_type = {
        object_type: [int(item["object_id"]) for item in targets if item["object_type"] == object_type]
        for object_type in OBJECT_TABLES
    }
    for object_type, object_ids in by_type.items():
        if not object_ids:
            continue
        target_id_column = OBJECT_TABLES[object_type][1]
        for foreign_key in _catalog_foreign_keys(conn, object_type):
            source_columns = list(map(str, foreign_key["source_columns"]))
            target_columns = list(map(str, foreign_key["target_columns"]))
            if len(source_columns) != 1 or target_columns != [target_id_column]:
                raise SystemIdentityPreviewError(
                    "TD_SYSTEM_RELATIONSHIP_REGISTRY_MISMATCH",
                    "Composite or non-primary User/Role relation is not supported.",
                )
            source_table = str(foreign_key["source_table"])
            source_column = source_columns[0]
            if not re.fullmatch(r"[a-z_][a-z0-9_]*", source_table) or not re.fullmatch(
                r"[a-z_][a-z0-9_]*", source_column
            ):
                raise SystemIdentityPreviewError(
                    "TD_SYSTEM_RELATIONSHIP_REGISTRY_MISMATCH", "Unsafe catalog identifier.",
                )
            rows = conn.execute(text(
                f'SELECT "{source_column}" AS object_id,to_jsonb(source_row) AS state '
                f'FROM public."{source_table}" source_row '
                f'WHERE "{source_column}"=ANY(:object_ids)'
            ), {"object_ids": object_ids}).mappings()
            states: dict[int, list[Any]] = defaultdict(list)
            for row in rows:
                states[int(row["object_id"])].append(row["state"])
            classification = _relationship_classification(foreign_key)
            for object_id, values in states.items():
                result[(object_type, object_id)].append({
                    "relation_code": f"FK:{foreign_key['constraint_name']}",
                    "table": source_table,
                    "columns": source_columns,
                    "classification": classification,
                    "count": len(values),
                    "state_digest": canonical_hash(sorted(canonical_hash(value) for value in values)),
                    "on_delete": str(foreign_key["on_delete"]),
                })
    return result


def _logical_relationships(
    conn: Connection, targets: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, int], list[dict[str, Any]]]:
    result: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    user_ids = [int(item["object_id"]) for item in targets if item["object_type"] == "USER"]
    role_ids = [int(item["object_id"]) for item in targets if item["object_type"] == "ROLE"]
    for object_type, object_ids in (("USER", user_ids), ("ROLE", role_ids)):
        if not object_ids:
            continue
        rows = conn.execute(text("""SELECT target_id AS object_id,to_jsonb(grant_row) AS state
            FROM public.access_grants grant_row
            WHERE target_type=:object_type AND target_id=ANY(:object_ids)"""), {
                "object_type": object_type, "object_ids": object_ids,
            }).mappings()
        states: dict[int, list[Any]] = defaultdict(list)
        for row in rows:
            states[int(row["object_id"])].append(row["state"])
        for object_id, values in states.items():
            result[(object_type, object_id)].append({
                "relation_code": "LOGICAL:access_grants.target",
                "table": "access_grants",
                "columns": ["target_type", "target_id"],
                "classification": BLOCKING,
                "count": len(values),
                "state_digest": canonical_hash(sorted(canonical_hash(value) for value in values)),
                "on_delete": None,
            })
    present_columns = {
        (str(row["table_name"]), str(row["column_name"]))
        for row in conn.execute(text("""SELECT table_name,column_name
            FROM information_schema.columns WHERE table_schema='public'""")).mappings()
    }
    physical_columns = {
        (str(row["source_table"]), str(row["source_columns"][0]))
        for target_type in OBJECT_TABLES
        for row in _catalog_foreign_keys(conn, target_type)
        if len(row["source_columns"]) == 1
    }
    role_values: dict[str, dict[str, list[int]]] = {
        "role_id": defaultdict(list), "code": defaultdict(list), "name": defaultdict(list),
    }
    if role_ids:
        for row in conn.execute(text("""SELECT role_id,code,name FROM public.roles
            WHERE role_id=ANY(:role_ids)"""), {"role_ids": role_ids}).mappings():
            object_id = int(row["role_id"])
            role_values["role_id"][str(object_id)].append(object_id)
            role_values["code"][str(row["code"])].append(object_id)
            role_values["name"][str(row["name"])].append(object_id)
    user_values = {str(object_id): [object_id] for object_id in user_ids}

    for object_type, table_name, column_name, target_field, classification in LOGICAL_RELATIONS:
        if (table_name, column_name) not in present_columns or (table_name, column_name) in physical_columns:
            continue
        matches = user_values if object_type == "USER" else role_values[target_field]
        if not matches:
            continue
        rows = conn.execute(text(
            f'SELECT "{column_name}"::text AS match_value,to_jsonb(source_row) AS state '
            f'FROM public."{table_name}" source_row '
            f'WHERE "{column_name}"::text=ANY(:match_values)'
        ), {"match_values": sorted(matches)}).mappings()
        states: dict[int, list[Any]] = defaultdict(list)
        for row in rows:
            for object_id in matches[str(row["match_value"])]:
                states[object_id].append(row["state"])
        for object_id, values in states.items():
            result[(object_type, object_id)].append({
                "relation_code": f"LOGICAL:{table_name}.{column_name}",
                "table": table_name,
                "columns": [column_name],
                "classification": classification,
                "count": len(values),
                "state_digest": canonical_hash(sorted(canonical_hash(value) for value in values)),
                "on_delete": None,
            })
    return result


def preview_targets(*, targets: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    typed_ids = _typed_ids(targets)
    with _read_only_connection() as conn:
        catalog = catalog_state(conn)
        users = {
            int(row["user_id"]): dict(row)
            for row in conn.execute(text("""SELECT users.user_id,users.full_name,users.login,
                    users.employee_id,employees.person_id,users.is_system_identity,
                    users.system_identity_purpose,users.is_active,users.role_id,
                    to_jsonb(users) AS raw
                FROM public.users users
                LEFT JOIN public.employees employees ON employees.employee_id=users.employee_id
                WHERE users.user_id=ANY(:ids)"""), {
                    "ids": [item["object_id"] for item in typed_ids if item["object_type"] == "USER"] or [-1],
                }).mappings()
        }
        roles = {
            int(row["role_id"]): dict(row)
            for row in conn.execute(text("""SELECT roles.role_id,roles.name,roles.code,
                    COALESCE((to_jsonb(roles)->>'is_active')::boolean,FALSE) AS is_active,
                    count(users.user_id)::int AS user_count,to_jsonb(roles) AS raw
                FROM public.roles roles LEFT JOIN public.users users USING(role_id)
                WHERE roles.role_id=ANY(:ids)
                GROUP BY roles.role_id
                ORDER BY roles.role_id"""), {
                    "ids": [item["object_id"] for item in typed_ids if item["object_type"] == "ROLE"] or [-1],
                }).mappings()
        }
        for item in typed_ids:
            rows = users if item["object_type"] == "USER" else roles
            if item["object_id"] not in rows:
                raise SystemIdentityPreviewError(
                    "TD_SYSTEM_TARGET_NOT_FOUND", "An exact User/Role target was not found.", 404,
                )
        provenance_rows = conn.execute(text("""SELECT provenance.*
            FROM public.test_system_identity_provenance provenance
            WHERE (provenance.object_type='USER' AND provenance.object_id=ANY(:user_ids))
               OR (provenance.object_type='ROLE' AND provenance.object_id=ANY(:role_ids))
            ORDER BY provenance.object_type,provenance.object_id,provenance.provenance_id"""), {
                "user_ids": [item["object_id"] for item in typed_ids if item["object_type"] == "USER"] or [-1],
                "role_ids": [item["object_id"] for item in typed_ids if item["object_type"] == "ROLE"] or [-1],
            }).mappings().all()
        provenance: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
        for row in provenance_rows:
            provenance[(str(row["object_type"]), int(row["object_id"]))].append(dict(row))
        physical = _physical_relationships(conn, typed_ids)
        logical = _logical_relationships(conn, typed_ids)

        items = []
        for target in typed_ids:
            key = (str(target["object_type"]), int(target["object_id"]))
            row = users[key[1]] if key[0] == "USER" else roles[key[1]]
            relations = sorted(
                physical.get(key, []) + logical.get(key, []),
                key=lambda relation: relation["relation_code"],
            )
            blockers: list[str] = []
            proofs = provenance.get(key, [])
            if not proofs:
                blockers.append("TEST_SYSTEM_IDENTITY_PROVENANCE_REQUIRED")
            if key[0] == "USER":
                if bool(row["is_system_identity"]) or row["system_identity_purpose"] == HISTORICAL_AUTHORSHIP:
                    blockers.append("HISTORICAL_AUTHORSHIP_PROTECTED")
                if row["employee_id"] is not None:
                    blockers.append("EMPLOYEE_LINK_PRESENT")
                if row["person_id"] is not None:
                    blockers.append("PERSON_LINK_PRESENT")
                label = str(row["full_name"] or "").strip() or f"USER #{key[1]}"
                secondary = str(row["login"]) if row["login"] else None
            else:
                if str(row["code"]).upper() in CANONICAL_ROLE_CODES:
                    blockers.append("CANONICAL_ROLE_PROTECTED")
                if bool(row["is_active"]):
                    blockers.append("ACTIVE_ROLE_PROTECTED")
                if int(row["user_count"]) > 0:
                    blockers.append("ROLE_USED_BY_USERS")
                label = str(row["name"] or "").strip() or f"ROLE #{key[1]}"
                secondary = str(row["code"])
            blockers.extend(
                relation["relation_code"] for relation in relations
                if relation["classification"] == BLOCKING
            )
            relationship_snapshot = {
                "fingerprint_version": FINGERPRINT_VERSION,
                "policy_version": POLICY_VERSION,
                "target": target,
                "target_row_digest": canonical_hash(row["raw"]),
                "provenance_digests": sorted(canonical_hash(proof) for proof in proofs),
                "relationships": relations,
                "blockers": sorted(set(blockers)),
            }
            relationship_fingerprint = canonical_hash(relationship_snapshot)
            items.append({
                **target,
                "label": label,
                "secondary_label": secondary,
                "has_test_provenance": bool(proofs),
                "ready_for_deletion": not blockers and bool(proofs),
                "blocking_codes": sorted(set(blockers)),
                "relationships": relations,
                "relationship_fingerprint": relationship_fingerprint,
            })
    list_hash = target_list_hash(typed_ids)
    aggregate_fingerprint = canonical_hash({
        "fingerprint_version": FINGERPRINT_VERSION,
        "policy_version": POLICY_VERSION,
        "catalog_fingerprint": catalog["fingerprint"],
        "target_list_hash": list_hash,
        "targets": [
            (item["object_type"], item["object_id"], item["relationship_fingerprint"])
            for item in items
        ],
    })
    return {
        "typed_ids": typed_ids,
        "target_list_hash": list_hash,
        "relationship_fingerprint": aggregate_fingerprint,
        "fingerprint_version": FINGERPRINT_VERSION,
        "policy_version": POLICY_VERSION,
        "catalog": catalog,
        "items": items,
        "count": len(items),
        "ready_count": sum(bool(item["ready_for_deletion"]) for item in items),
    }
