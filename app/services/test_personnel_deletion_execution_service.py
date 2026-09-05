"""WP-TD-005 stage 5 transactional applicant-only deletion backend."""
from __future__ import annotations

import os
import re
from typing import Any, Callable, Iterable, Mapping, TypeVar
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from app.db.engine import engine
from app.services import test_personnel_deletion_execute_audit_service as execute_audit
from app.services import test_personnel_deletion_fingerprint_service as fingerprints
from app.services import test_personnel_deletion_service as approval_service
from app.services import test_personnel_deletion_tombstone_service as tombstones


FEATURE_FLAG = "TEST_PERSONNEL_DELETION_EXECUTION_ENABLED"
CONFIRMATION_TEMPLATE = "УДАЛИТЬ {request_number} / {target_count}"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_T = TypeVar("_T")


class _AtomicExecutionFailure(approval_service.TestPersonnelDeletionError):
    """Failure after R0 whose domain work must be rolled back before audit."""


def feature_enabled() -> bool:
    return (os.getenv(FEATURE_FLAG) or "").strip().lower() in _TRUE_VALUES


def confirmation_phrase(request_number: str, target_count: int) -> str:
    return CONFIRMATION_TEMPLATE.format(
        request_number=str(request_number), target_count=int(target_count),
    )


def assess_execution_readiness(
    *, request_id: UUID, executor_user_id: int, expected_version: int,
    expected_target_set_hash: str, expected_relationship_fingerprint: str,
) -> dict[str, Any]:
    """Return a server-owned, read-only hint; execute_request remains authoritative."""
    with engine.connect() as conn:
        request = approval_service._request_row(conn, request_id, False)
        roots = conn.execute(text("""SELECT person_id,application_ids,root_type
            FROM public.test_personnel_deletion_manifest_v2_targets
            WHERE request_id=:request_id ORDER BY manifest_order"""), {
            "request_id": request_id,
        }).mappings().all()
        person_count = len({int(root["person_id"]) for root in roots})
        readiness = {
            "allowed": False,
            "reason_code": None,
            "required_confirmation_phrase": confirmation_phrase(
                str(request["request_number"]), person_count,
            ),
            "target_person_count": person_count,
            "execution_enabled": feature_enabled(),
        }

        def denied(code: str) -> dict[str, Any]:
            return {**readiness, "reason_code": code}

        if (
            int(request["version"]) != int(expected_version)
            or request["target_set_hash"] != expected_target_set_hash
            or request["relationship_fingerprint"] != expected_relationship_fingerprint
        ):
            return denied("TD_READ_SNAPSHOT_CHANGED")
        try:
            execute_audit.assert_executor_permission(
                conn, executor_user_id=int(executor_user_id),
            )
        except execute_audit.ExecuteAuditContractError as error:
            return denied(error.code)
        if not readiness["execution_enabled"]:
            return denied("TD_EXECUTION_DISABLED")
        if int(request.get("manifest_version") or 1) != approval_service.MANIFEST_VERSION:
            return denied("TD_MANIFEST_V1_READ_ONLY")
        if request.get("process_type") != approval_service.APPLICANT_PROCESS_TYPE:
            return denied("TD_EMPLOYEE_DELETION_FORBIDDEN")
        if request.get("basis") != "PROVENANCE":
            return denied("TD_LEGACY_MANIFEST_NOT_EXECUTABLE")
        if request["status"] != "APPROVED" or not request.get("approval_expires_at"):
            return denied("TD_EXECUTE_APPROVAL_REQUIRED")
        if request["approval_expires_at"] <= request["db_now"]:
            return denied("TD_APPROVAL_EXPIRED")
        if not roots or any(root["root_type"] != "PERSON" for root in roots):
            return denied("TD_MANIFEST_V2_ROOTS_INVALID")
        try:
            approval = execute_audit.assert_approver_executor_separation(
                conn, request_id=request_id, executor_user_id=int(executor_user_id),
            )
            pairs = approval_service._manifest_v2_pairs(conn, request_id)
            candidates = approval_service._evaluate_candidates(conn, pairs)
            current = approval_service._request_fingerprint(
                conn, candidates, str(request["basis"]),
            )
        except execute_audit.ExecuteAuditContractError as error:
            return denied(error.code)
        except approval_service.TestPersonnelDeletionError as error:
            return denied(error.code)

        approval_mismatch = (
            int(approval["request_version"]) != int(request["version"])
            or approval["target_set_hash"] != request["target_set_hash"]
            or approval["relationship_fingerprint"] != request["relationship_fingerprint"]
            or approval["fingerprint_version"] != request["fingerprint_version"]
            or approval["catalog_fingerprint"] != request["catalog_fingerprint"]
        )
        current_mismatch = (
            approval_service._target_set_hash(candidates) != request["target_set_hash"]
            or current["fingerprint"] != request["relationship_fingerprint"]
            or request.get("fingerprint_version") != fingerprints.FINGERPRINT_VERSION
            or request.get("relationship_policy_version") != fingerprints.POLICY_VERSION
            or request.get("catalog_version") != fingerprints.CATALOG_VERSION
            or request.get("catalog_fingerprint") != current["catalog_fingerprint"]
            or bool(current["blockers"])
        )
        if approval_mismatch:
            return denied("TD_APPROVAL_FINGERPRINT_MISMATCH")
        if current_mismatch:
            return denied(
                f"TD_RELATIONSHIP_BLOCK_{current['blockers'][0]}"
                if current["blockers"] else "TD_FINGERPRINT_CHANGED"
            )
        return {**readiness, "allowed": True, "reason_code": None}


def _payload_hash(
    request_id: UUID, idempotency_key: UUID, confirmation: str,
    expected_snapshot: Mapping[str, Any],
) -> str:
    return fingerprints.canonical_hash({
        "contract": "WP-TD-005-EXECUTE/v1",
        "request_id": str(request_id),
        "idempotency_key": str(idempotency_key),
        "confirmation_phrase": confirmation,
        "expected_snapshot": dict(expected_snapshot),
    })


def _timestamp_text(value: Any) -> str:
    rendered = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return f"{rendered[:-1]}+00:00" if rendered.endswith("Z") else rendered


def _assert_execution_snapshot(
    *, request: Mapping[str, Any], approval: Mapping[str, Any] | None,
    target_person_count: int, expected_snapshot: Mapping[str, Any],
) -> None:
    actual = {
        "request_version": int(request["version"]),
        "approval_decision_id": int(approval["decision_id"]) if approval else None,
        "approval_request_version": int(approval["request_version"]) if approval else None,
        "target_set_hash": str(request["target_set_hash"]),
        "relationship_fingerprint": str(request["relationship_fingerprint"]),
        "fingerprint_version": str(request["fingerprint_version"]),
        "relationship_policy_version": str(request["relationship_policy_version"]),
        "catalog_version": str(request["catalog_version"]),
        "catalog_fingerprint": str(request["catalog_fingerprint"]),
        "approval_expires_at": _timestamp_text(request.get("approval_expires_at")),
        "target_person_count": int(target_person_count),
    }
    expected = {
        **dict(expected_snapshot),
        "request_version": int(expected_snapshot["request_version"]),
        "approval_decision_id": int(expected_snapshot["approval_decision_id"]),
        "approval_request_version": int(expected_snapshot["approval_request_version"]),
        "approval_expires_at": _timestamp_text(expected_snapshot["approval_expires_at"]),
        "target_person_count": int(expected_snapshot["target_person_count"]),
    }
    if actual != expected:
        raise approval_service.TestPersonnelDeletionError(
            "TD_EXECUTION_SNAPSHOT_CHANGED",
            "The approved execution snapshot changed; review it and confirm again.",
            409,
        )


def _is_serialization_failure(error: DBAPIError) -> bool:
    original = getattr(error, "orig", None)
    code = getattr(original, "pgcode", None) or getattr(original, "sqlstate", None)
    return code in {"40001", "40P01"}


def _run_serializable(work: Callable[[Connection], _T]) -> _T:
    for attempt in range(3):
        try:
            with engine.connect().execution_options(isolation_level="SERIALIZABLE") as conn:
                with conn.begin():
                    return work(conn)
        except DBAPIError as error:
            if not _is_serialization_failure(error):
                raise
            if attempt == 2:
                raise approval_service.TestPersonnelDeletionError(
                    "TD_SERIALIZATION_RETRY_EXHAUSTED",
                    "Concurrent state change; retry execution with a new idempotency key.",
                    409,
                ) from error
    raise AssertionError("unreachable")


def _lock_execution_catalog(conn: Connection) -> None:
    tables = {
        rule.table for rule in approval_service.RELATIONSHIP_MATRIX
    } | {
        "access_roles", "roles", "access_grants", "users",
        "test_personnel_deletion_requests", "test_personnel_deletion_targets",
        "test_personnel_deletion_manifest_v2_targets",
        "test_personnel_deletion_decisions", "test_personnel_deletion_history",
        "test_personnel_provenance",
        "test_personnel_deletion_record_event_tombstones",
        "test_personnel_deletion_command_tombstones",
        "test_personnel_deletion_lifecycle_tombstones",
        "test_personnel_deletion_execution_attempts",
    }
    if any(not _SAFE_IDENTIFIER.fullmatch(table) for table in tables):
        raise _AtomicExecutionFailure(
            "TD_EXECUTION_CATALOG_IDENTIFIER_INVALID", "Server relationship catalog is invalid.", 409,
        )
    # SHARE ROW EXCLUSIVE is deliberately acquired in a global order.  It
    # blocks legacy writers that do not yet participate in the advisory-lock
    # protocol, while still allowing this transaction's explicit DML.
    for table in sorted(tables):
        conn.execute(text(f'LOCK TABLE public."{table}" IN SHARE ROW EXCLUSIVE MODE'))


def _existing_by_key(
    conn: Connection, *, request_id: UUID, executor_user_id: int,
    idempotency_key: UUID, payload_hash: str,
) -> dict[str, Any] | None:
    key = str(idempotency_key)
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {
        "key": f"WP-TD-005:EXECUTE:{key}",
    })
    row = conn.execute(text("""SELECT request_id,actor_user_id,command_payload_hash,
            result_projection FROM public.test_personnel_deletion_history
        WHERE action='EXECUTE' AND idempotency_key=:key"""), {"key": key}).mappings().one_or_none()
    if row is None:
        return None
    if (
        row["request_id"] != request_id
        or int(row["actor_user_id"]) != int(executor_user_id)
        or row["command_payload_hash"] != payload_hash
    ):
        raise approval_service.TestPersonnelDeletionError(
            "TD_EXECUTE_IDEMPOTENCY_CONFLICT",
            "Idempotency key is already bound to different technical content.",
            409,
        )
    return dict(row["result_projection"])


def _completed_result(conn: Connection, request_id: UUID) -> dict[str, Any] | None:
    value = conn.execute(text("""SELECT result_projection
        FROM public.test_personnel_deletion_history
        WHERE request_id=:request_id AND action='EXECUTE'
          AND result_code='TD_EXECUTION_COMPLETED'
        ORDER BY history_id DESC LIMIT 1"""), {"request_id": request_id}).scalar_one_or_none()
    return dict(value) if value is not None else None


def _attempt_event(
    conn: Connection, *, request_id: UUID, executor_user_id: int,
    idempotency_key: UUID, payload_hash: str, event_type: str,
    result_code: str | None = None, error_code: str | None = None,
) -> None:
    key = str(idempotency_key)
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {
        "key": f"WP-TD-005:EXECUTE:{key}",
    })
    intent = conn.execute(text("""SELECT request_id,executor_user_id,command_payload_hash
        FROM public.test_personnel_deletion_execution_attempts
        WHERE idempotency_key=:key AND event_type='INTENT'"""), {"key": key}).mappings().one_or_none()
    identity = (request_id, int(executor_user_id), payload_hash)
    if intent is not None and (
        intent["request_id"], int(intent["executor_user_id"]), intent["command_payload_hash"]
    ) != identity:
        raise approval_service.TestPersonnelDeletionError(
            "TD_EXECUTE_IDEMPOTENCY_CONFLICT",
            "Idempotency key is already bound to different technical content.", 409,
        )
    if event_type == "RESULT" and intent is None:
        raise _AtomicExecutionFailure(
            "TD_EXECUTION_INTENT_MISSING", "Durable execution intent is missing.", 409,
        )
    existing = conn.execute(text("""SELECT request_id,executor_user_id,command_payload_hash,
            result_code,error_code
        FROM public.test_personnel_deletion_execution_attempts
        WHERE idempotency_key=:key AND event_type=:event_type"""), {
            "key": key, "event_type": event_type,
        }).mappings().one_or_none()
    expected = (*identity, result_code, error_code)
    if existing is not None:
        actual = (
            existing["request_id"], int(existing["executor_user_id"]),
            existing["command_payload_hash"], existing["result_code"], existing["error_code"],
        )
        if actual != expected:
            raise approval_service.TestPersonnelDeletionError(
                "TD_EXECUTE_IDEMPOTENCY_CONFLICT",
                "Idempotency key is already bound to a different attempt result.", 409,
            )
        return
    conn.execute(text("""INSERT INTO public.test_personnel_deletion_execution_attempts(
            request_id,executor_user_id,idempotency_key,command_payload_hash,event_type,
            result_code,error_code)
        VALUES(:request_id,:executor,:key,:payload_hash,:event_type,:result_code,:error_code)"""), {
        "request_id": request_id, "executor": int(executor_user_id), "key": key,
        "payload_hash": payload_hash, "event_type": event_type,
        "result_code": result_code, "error_code": error_code,
    })


def _prepare_attempt(
    *, request_id: UUID, executor_user_id: int, idempotency_key: UUID, payload_hash: str,
) -> None:
    def work(conn: Connection) -> None:
        execute_audit.assert_executor_permission(conn, executor_user_id=executor_user_id)
        approval_service._request_row(conn, request_id, False)
        _attempt_event(
            conn, request_id=request_id, executor_user_id=executor_user_id,
            idempotency_key=idempotency_key, payload_hash=payload_hash, event_type="INTENT",
        )
    _run_serializable(work)


def _technical_ids(conn: Connection, sql: str, params: Mapping[str, Any]) -> list[Any]:
    return list(conn.execute(text(sql), dict(params)).scalars())


def _id_hash(values: Iterable[Any]) -> str:
    return fingerprints.canonical_hash(sorted(map(str, values)))


_PRESERVE_SET_NULL_COLUMNS = {
    "ENROLLMENT_HISTORY_RETAINED": frozenset({"person_id"}),
    "HR_REVIEW_OVERRIDE_RETAINED": frozenset({"person_id"}),
    "SECURITY_AUDIT_RETAINED": frozenset({"target_person_id"}),
}


def _primary_key_columns(conn: Connection, table: str) -> list[str]:
    return list(conn.execute(text("""SELECT attribute.attname
        FROM pg_catalog.pg_constraint constraint_def
        JOIN unnest(constraint_def.conkey) WITH ORDINALITY key_def(attnum,position) ON TRUE
        JOIN pg_catalog.pg_attribute attribute
          ON attribute.attrelid=constraint_def.conrelid AND attribute.attnum=key_def.attnum
        WHERE constraint_def.contype='p'
          AND constraint_def.conrelid=to_regclass(:qualified_table)
        ORDER BY key_def.position"""), {"qualified_table": f"public.{table}"}).scalars())


def _preserve_snapshot(
    conn: Connection, *, roots: Iterable[Mapping[str, Any]], phase: str,
    before: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rules = [
        rule for rule in approval_service.RELATIONSHIP_MATRIX
        if rule.code in fingerprints.PRESERVE_RULES
    ]
    result: dict[str, Any] = {}
    for rule in sorted(rules, key=lambda item: item.code):
        if not _SAFE_IDENTIFIER.fullmatch(rule.table):
            raise _AtomicExecutionFailure(
                "TD_PRESERVE_IDENTIFIER_INVALID", "Preservation catalog is invalid.", 409,
            )
        pk_columns = _primary_key_columns(conn, rule.table)
        states_by_identity: dict[str, dict[str, Any]] = {}
        if phase == "before":
            for root in roots:
                application_ids = sorted(map(int, root["application_ids"]))
                params = {
                    "person_id": int(root["person_id"]),
                    "application_ids": application_ids,
                    "application_id": application_ids[0],
                    "early_actions": list(approval_service.EARLY_LIFECYCLE_ACTIONS),
                    "environment": (os.getenv("APP_ENV") or "dev").strip().lower(),
                }
                for state in conn.execute(text(rule.sql), params).scalars():
                    state = dict(state)
                    if not pk_columns or any(column not in state for column in pk_columns):
                        raise _AtomicExecutionFailure(
                            "TD_PRESERVE_TECHNICAL_ID_MISSING",
                            "A preserved row has no server-known technical identity.", 409,
                        )
                    identity = {column: state[column] for column in pk_columns}
                    identity_key = fingerprints.canonical_hash(identity)
                    predicates = " AND ".join(f'"{column}"=:{column}' for column in identity)
                    full_state = dict(conn.execute(text(
                        f'SELECT to_jsonb(preserved) FROM public."{rule.table}" preserved WHERE {predicates}'
                    ), identity).scalar_one())
                    expected = dict(full_state)
                    for column in _PRESERVE_SET_NULL_COLUMNS.get(rule.code, ()):
                        if column in expected:
                            expected[column] = None
                    states_by_identity[identity_key] = {
                        "identity": identity,
                        "before_digest": fingerprints.canonical_hash(full_state),
                        "expected_after_digest": fingerprints.canonical_hash(expected),
                    }
        else:
            assert before is not None
            previous = before[rule.code]
            for row in previous["rows"]:
                identity = row["identity"]
                predicates = " AND ".join(f'"{column}"=:{column}' for column in identity)
                current = conn.execute(text(
                    f'SELECT to_jsonb(preserved) FROM public."{rule.table}" preserved WHERE {predicates}'
                ), identity).scalar_one_or_none()
                if current is None or fingerprints.canonical_hash(current) != row["expected_after_digest"]:
                    raise _AtomicExecutionFailure(
                        "TD_EXECUTION_PRESERVE_MISMATCH",
                        "A required preserved row is missing or changed outside its approved SET NULL projection.",
                        409,
                    )
                states_by_identity[fingerprints.canonical_hash(identity)] = dict(row)
        rows = [states_by_identity[key] for key in sorted(states_by_identity)]
        result[rule.code] = {
            "table": rule.table,
            "primary_key_columns": pk_columns,
            "count": len(rows),
            "technical_id_digest": fingerprints.canonical_hash(
                [row["identity"] for row in rows]
            ),
            "row_digest": fingerprints.canonical_hash(
                [row["before_digest"] for row in rows]
            ),
            "expected_after_digest": fingerprints.canonical_hash(
                [row["expected_after_digest"] for row in rows]
            ),
            "rows": rows,
        }
    return result


def _delete_returning(
    conn: Connection, *, table: str, id_column: str, where: str,
    params: Mapping[str, Any], expected_ids: Iterable[Any],
) -> list[Any]:
    expected = sorted(map(str, expected_ids))
    returned = conn.execute(text(
        f'DELETE FROM public."{table}" WHERE {where} RETURNING "{id_column}"'
    ), dict(params)).scalars().all()
    if len(returned) != len(expected) or _id_hash(returned) != _id_hash(expected):
        raise _AtomicExecutionFailure(
            "TD_EXECUTION_COUNT_HASH_MISMATCH",
            "A deletion step did not match its frozen technical set.",
            409,
        )
    return returned


def _fail_if_requested(fault_after_step: str | None, step: str) -> None:
    if fault_after_step == step:
        raise _AtomicExecutionFailure(
            "TD_EXECUTION_FAULT_INJECTED", "Execution fault injection requested.", 409,
        )


def _record_execute(
    conn: Connection, *, request: Mapping[str, Any], executor_user_id: int,
    idempotency_key: UUID, payload_hash: str, table_counts: Mapping[str, int],
    before_hash: str, after_hash: str, result: str, error_code: str | None,
    new_status: str, new_version: int,
    allow_approval_drift: bool = False,
) -> dict[str, Any]:
    try:
        return execute_audit.record_execute_audit(
            conn,
            request_id=request["request_id"],
            executor_user_id=executor_user_id,
            table_counts=table_counts,
            before_hash=before_hash,
            after_hash=after_hash,
            idempotency_key=str(idempotency_key),
            result=result,
            error_code=error_code,
            command_payload_hash=payload_hash,
            old_status="APPROVED",
            new_status=new_status,
            old_version=int(request["version"]),
            new_version=new_version,
            allow_approval_drift=allow_approval_drift,
        )
    except execute_audit.ExecuteAuditContractError as error:
        raise approval_service.TestPersonnelDeletionError(error.code, str(error), 409) from error


def _mark_reapproval(
    conn: Connection, *, request: Mapping[str, Any], executor_user_id: int,
    idempotency_key: UUID, payload_hash: str, reason: str,
    current_hash: str | None = None,
) -> dict[str, Any]:
    new_version = int(request["version"]) + 1
    before_hash = fingerprints.canonical_hash({
        "request_id": str(request["request_id"]),
        "request_version": int(request["version"]),
        "relationship_fingerprint": request["relationship_fingerprint"],
    })
    after_hash = fingerprints.canonical_hash({
        "request_id": str(request["request_id"]),
        "request_version": new_version,
        "relationship_fingerprint": current_hash,
        "reapproval_reason": reason,
    })
    projection = _record_execute(
        conn, request=request, executor_user_id=executor_user_id,
        idempotency_key=idempotency_key, payload_hash=payload_hash,
        table_counts={}, before_hash=before_hash, after_hash=after_hash,
        result="TD_REAPPROVAL_REQUIRED", error_code=reason,
        new_status="REAPPROVAL_REQUIRED", new_version=new_version,
        allow_approval_drift=True,
    )
    updated = conn.execute(text("""UPDATE public.test_personnel_deletion_requests
        SET status='REAPPROVAL_REQUIRED',version=:new_version,
            approved_at=NULL,approval_expires_at=NULL,last_checked_at=statement_timestamp()
        WHERE request_id=:request_id AND status='APPROVED' AND version=:old_version
        RETURNING request_id"""), {
        "request_id": request["request_id"], "old_version": request["version"],
        "new_version": new_version,
    }).scalar_one_or_none()
    if updated is None:
        raise _AtomicExecutionFailure(
            "TD_EXECUTION_REQUEST_STATE_RACE", "Request state changed concurrently.", 409,
        )
    _attempt_event(
        conn, request_id=request["request_id"], executor_user_id=executor_user_id,
        idempotency_key=idempotency_key, payload_hash=payload_hash, event_type="RESULT",
        result_code="TD_REAPPROVAL_REQUIRED", error_code=reason,
    )
    return projection


def _rule_rows_after_delete(
    conn: Connection, *, person_id: int, application_ids: list[int], application_id: int,
) -> list[str]:
    params = {
        "person_id": person_id,
        "application_ids": application_ids,
        "application_id": application_id,
        "early_actions": list(approval_service.EARLY_LIFECYCLE_ACTIONS),
        "environment": (os.getenv("APP_ENV") or "dev").strip().lower(),
    }
    remaining: list[str] = []
    for rule in approval_service.RELATIONSHIP_MATRIX:
        action = (
            "DELETE" if rule.code in fingerprints.DELETE_RULES
            else "PRESERVE" if rule.code in fingerprints.PRESERVE_RULES else "BLOCK"
        )
        if action == "PRESERVE":
            continue
        if conn.execute(text(f"SELECT EXISTS({rule.sql})"), params).scalar_one():
            remaining.append(rule.code)
    return remaining


def _execute_transaction(
    conn: Connection, *, request_id: UUID, executor_user_id: int,
    idempotency_key: UUID, confirmation: str, payload_hash: str,
    expected_snapshot: Mapping[str, Any],
    fault_after_step: str | None,
    step_hook: Callable[[str], None] | None,
) -> dict[str, Any]:
    execute_audit.assert_executor_permission(conn, executor_user_id=executor_user_id)
    request = approval_service._request_row(conn, request_id, True)
    existing = _existing_by_key(
        conn, request_id=request_id, executor_user_id=executor_user_id,
        idempotency_key=idempotency_key, payload_hash=payload_hash,
    )
    if existing is not None:
        stored_status = {
            "TD_EXECUTION_COMPLETED": "COMPLETED",
            "TD_REAPPROVAL_REQUIRED": "REAPPROVAL_REQUIRED",
            "TD_EXECUTION_FAILED": "FAILED",
        }.get(str(existing.get("result")), "STORED")
        return {"status": stored_status, "replayed": True, "result": existing}
    if request["status"] == "COMPLETED":
        raise approval_service.TestPersonnelDeletionError(
            "TD_EXECUTE_ALREADY_COMPLETED",
            "The request is completed; only its original idempotency key can replay the result.", 409,
        )

    if int(request.get("manifest_version") or 1) != approval_service.MANIFEST_VERSION:
        raise approval_service.TestPersonnelDeletionError(
            "TD_MANIFEST_V1_READ_ONLY", "Manifest v1 is retained for viewing only.", 409,
        )
    if request.get("process_type") != approval_service.APPLICANT_PROCESS_TYPE:
        raise approval_service.TestPersonnelDeletionError(
            "TD_EMPLOYEE_DELETION_FORBIDDEN", "Only applicant-only requests can be executed.", 409,
        )
    if request.get("basis") != "PROVENANCE":
        raise approval_service.TestPersonnelDeletionError(
            "TD_LEGACY_MANIFEST_NOT_EXECUTABLE", "Legacy manifests cannot be executed.", 409,
        )
    roots = conn.execute(text("""SELECT person_id,application_ids,root_type
        FROM public.test_personnel_deletion_manifest_v2_targets
        WHERE request_id=:request_id ORDER BY manifest_order FOR SHARE"""), {
        "request_id": request_id,
    }).mappings().all()
    person_ids = sorted(int(root["person_id"]) for root in roots)
    application_ids = sorted(
        int(application_id) for root in roots for application_id in root["application_ids"]
    )
    for person_id in person_ids:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {
            "key": f"WP-TD-005:PERSON:{person_id}",
        })
    _lock_execution_catalog(conn)
    # Recheck permission after all permission/identity writer tables are locked.
    execute_audit.assert_executor_permission(conn, executor_user_id=executor_user_id)
    approval_snapshot = conn.execute(text("""SELECT decision_id,request_version
        FROM public.test_personnel_deletion_decisions
        WHERE request_id=:request_id AND decision='APPROVE'
        ORDER BY decision_id DESC LIMIT 1 FOR SHARE"""), {
        "request_id": request_id,
    }).mappings().one_or_none()
    _assert_execution_snapshot(
        request=request, approval=approval_snapshot,
        target_person_count=len(roots), expected_snapshot=expected_snapshot,
    )
    if request["status"] != "APPROVED" or not request.get("approval_expires_at"):
        raise approval_service.TestPersonnelDeletionError(
            "TD_EXECUTE_APPROVAL_REQUIRED", "A current approval is required.", 409,
        )
    if request["approval_expires_at"] <= request["db_now"]:
        return {
            "status": "REAPPROVAL_REQUIRED", "replayed": False,
            "result": _mark_reapproval(
                conn, request=request, executor_user_id=executor_user_id,
                idempotency_key=idempotency_key, payload_hash=payload_hash,
                reason="TD_APPROVAL_EXPIRED",
            ),
        }
    if not roots or any(root["root_type"] != "PERSON" for root in roots):
        return {
            "status": "REAPPROVAL_REQUIRED", "replayed": False,
            "result": _mark_reapproval(
                conn, request=request, executor_user_id=executor_user_id,
                idempotency_key=idempotency_key, payload_hash=payload_hash,
                reason="TD_MANIFEST_V2_ROOTS_INVALID",
            ),
        }
    if confirmation != confirmation_phrase(request["request_number"], len(roots)):
        raise approval_service.TestPersonnelDeletionError(
            "TD_EXECUTION_CONFIRMATION_MISMATCH", "The exact confirmation phrase is required.", 422,
        )
    approval = execute_audit.assert_approver_executor_separation(
        conn, request_id=request_id, executor_user_id=executor_user_id,
    )
    locked_people = _technical_ids(conn, """SELECT person_id FROM public.persons
        WHERE person_id=ANY(:ids) ORDER BY person_id FOR UPDATE""", {"ids": person_ids})
    locked_apps = _technical_ids(conn, """SELECT application_id FROM public.personnel_applications
        WHERE application_id=ANY(:ids) ORDER BY application_id FOR UPDATE""", {"ids": application_ids})
    if list(map(int, locked_people)) != person_ids or list(map(int, locked_apps)) != application_ids:
        return {
            "status": "REAPPROVAL_REQUIRED", "replayed": False,
            "result": _mark_reapproval(
                conn, request=request, executor_user_id=executor_user_id,
                idempotency_key=idempotency_key, payload_hash=payload_hash,
                reason="TD_TARGET_STATE_MISSING",
            ),
        }

    try:
        pairs = approval_service._manifest_v2_pairs(conn, request_id)
        candidates = approval_service._evaluate_candidates(conn, pairs)
        current = approval_service._request_fingerprint(conn, candidates, str(request["basis"]))
    except approval_service.TestPersonnelDeletionError as error:
        return {
            "status": "REAPPROVAL_REQUIRED", "replayed": False,
            "result": _mark_reapproval(
                conn, request=request, executor_user_id=executor_user_id,
                idempotency_key=idempotency_key, payload_hash=payload_hash,
                reason=error.code,
            ),
        }

    approval_mismatch = (
        int(approval["request_version"]) != int(request["version"])
        or approval["target_set_hash"] != request["target_set_hash"]
        or approval["relationship_fingerprint"] != request["relationship_fingerprint"]
        or approval["fingerprint_version"] != request["fingerprint_version"]
        or approval["catalog_fingerprint"] != request["catalog_fingerprint"]
    )
    current_mismatch = (
        approval_service._target_set_hash(candidates) != request["target_set_hash"]
        or current["fingerprint"] != request["relationship_fingerprint"]
        or request.get("fingerprint_version") != fingerprints.FINGERPRINT_VERSION
        or request.get("relationship_policy_version") != fingerprints.POLICY_VERSION
        or request.get("catalog_version") != fingerprints.CATALOG_VERSION
        or request.get("catalog_fingerprint") != current["catalog_fingerprint"]
        or bool(current["blockers"])
    )
    if approval_mismatch or current_mismatch:
        reason = (
            "TD_APPROVAL_FINGERPRINT_MISMATCH" if approval_mismatch
            else f"TD_RELATIONSHIP_BLOCK_{current['blockers'][0]}" if current["blockers"]
            else "TD_FINGERPRINT_CHANGED"
        )
        return {
            "status": "REAPPROVAL_REQUIRED", "replayed": False,
            "result": _mark_reapproval(
                conn, request=request, executor_user_id=executor_user_id,
                idempotency_key=idempotency_key, payload_hash=payload_hash,
                reason=reason, current_hash=current["fingerprint"],
            ),
        }
    _fail_if_requested(fault_after_step, "R0")
    if step_hook is not None:
        step_hook("R0")

    params = {"person_ids": person_ids, "application_ids": application_ids}
    source_sets = {
        "personnel_intake_drafts": _technical_ids(conn,
            "SELECT draft_id FROM public.personnel_intake_drafts WHERE application_id=ANY(:application_ids) ORDER BY draft_id", params),
        "personnel_intake_links": _technical_ids(conn,
            "SELECT link_id FROM public.personnel_intake_links WHERE application_id=ANY(:application_ids) ORDER BY link_id", params),
        "personnel_record_events": _technical_ids(conn,
            "SELECT event_id FROM public.personnel_record_events WHERE person_id=ANY(:person_ids) ORDER BY event_id", params),
        "ppr_command_executions": _technical_ids(conn,
            "SELECT command_execution_id FROM public.ppr_command_executions WHERE person_id=ANY(:person_ids) ORDER BY command_execution_id", params),
        "personnel_application_lifecycle_audit": _technical_ids(conn, """SELECT audit_id
            FROM public.personnel_application_lifecycle_audit
            WHERE application_id=ANY(:application_ids) AND action=ANY(:early_actions)
            ORDER BY audit_id""", {**params, "early_actions": list(approval_service.EARLY_LIFECYCLE_ACTIONS)}),
        "personnel_record_metadata": _technical_ids(conn,
            "SELECT person_id FROM public.personnel_record_metadata WHERE person_id=ANY(:person_ids) ORDER BY person_id", params),
        "personnel_applications": application_ids,
        "persons": person_ids,
    }
    preserve_before = _preserve_snapshot(conn, roots=roots, phase="before")
    before_hash = fingerprints.canonical_hash({
        "request_id": str(request_id), "request_version": int(request["version"]),
        "target_set_hash": request["target_set_hash"],
        "relationship_fingerprint": request["relationship_fingerprint"],
        "source_id_hashes": {table: _id_hash(ids) for table, ids in sorted(source_sets.items())},
        "preserve_verification": preserve_before,
    })

    deleted: dict[str, list[Any]] = {}
    deleted["personnel_intake_drafts"] = _delete_returning(
        conn, table="personnel_intake_drafts", id_column="draft_id",
        where="application_id=ANY(:application_ids)", params=params,
        expected_ids=source_sets["personnel_intake_drafts"],
    )
    _fail_if_requested(fault_after_step, "D1")
    deleted["personnel_intake_links"] = _delete_returning(
        conn, table="personnel_intake_links", id_column="link_id",
        where="application_id=ANY(:application_ids)", params=params,
        expected_ids=source_sets["personnel_intake_links"],
    )
    _fail_if_requested(fault_after_step, "D2")

    captured = tombstones.capture_tombstones(
        conn, request_id=request_id,
        record_event_ids=source_sets["personnel_record_events"],
        command_execution_ids=source_sets["ppr_command_executions"],
        lifecycle_audit_ids=source_sets["personnel_application_lifecycle_audit"],
    )
    if (
        len(captured["record_events"]) != len(source_sets["personnel_record_events"])
        or len(captured["commands"]) != len(source_sets["ppr_command_executions"])
        or len(captured["lifecycle"]) != len(source_sets["personnel_application_lifecycle_audit"])
    ):
        raise _AtomicExecutionFailure(
            "TD_EXECUTION_TOMBSTONE_COUNT_MISMATCH", "Tombstone coverage is incomplete.", 409,
        )
    _fail_if_requested(fault_after_step, "TOMBSTONES")
    deleted["personnel_record_events"] = _delete_returning(
        conn, table="personnel_record_events", id_column="event_id",
        where="person_id=ANY(:person_ids)", params=params,
        expected_ids=source_sets["personnel_record_events"],
    )
    deleted["ppr_command_executions"] = _delete_returning(
        conn, table="ppr_command_executions", id_column="command_execution_id",
        where="person_id=ANY(:person_ids)", params=params,
        expected_ids=source_sets["ppr_command_executions"],
    )
    deleted["personnel_application_lifecycle_audit"] = _delete_returning(
        conn, table="personnel_application_lifecycle_audit", id_column="audit_id",
        where="application_id=ANY(:application_ids) AND action=ANY(:early_actions)",
        params={**params, "early_actions": list(approval_service.EARLY_LIFECYCLE_ACTIONS)},
        expected_ids=source_sets["personnel_application_lifecycle_audit"],
    )
    _fail_if_requested(fault_after_step, "JOURNALS")
    deleted["personnel_record_metadata"] = _delete_returning(
        conn, table="personnel_record_metadata", id_column="person_id",
        where="person_id=ANY(:person_ids)", params=params,
        expected_ids=source_sets["personnel_record_metadata"],
    )
    _fail_if_requested(fault_after_step, "D3")
    deleted["personnel_applications"] = _delete_returning(
        conn, table="personnel_applications", id_column="application_id",
        where="application_id=ANY(:application_ids)", params=params,
        expected_ids=source_sets["personnel_applications"],
    )
    _fail_if_requested(fault_after_step, "D4")
    deleted["persons"] = _delete_returning(
        conn, table="persons", id_column="person_id",
        where="person_id=ANY(:person_ids)", params=params,
        expected_ids=source_sets["persons"],
    )
    _fail_if_requested(fault_after_step, "D5")

    remaining_rules: list[str] = []
    for root in roots:
        root_apps = sorted(map(int, root["application_ids"]))
        remaining_rules.extend(_rule_rows_after_delete(
            conn, person_id=int(root["person_id"]), application_ids=root_apps,
            application_id=root_apps[0],
        ))
    if remaining_rules:
        raise _AtomicExecutionFailure(
            "TD_EXECUTION_DANGLING_REFERENCE", "A domain or logical reference remains.", 409,
        )
    preserved = conn.execute(text("""SELECT COUNT(*) FROM public.test_personnel_provenance
        WHERE target_type='PERSON' AND target_id=ANY(:person_ids)"""), params).scalar_one()
    if int(preserved) < len(person_ids):
        raise _AtomicExecutionFailure(
            "TD_EXECUTION_PROVENANCE_NOT_PRESERVED", "Required provenance was not preserved.", 409,
        )
    preserve_after = _preserve_snapshot(
        conn, roots=roots, phase="after", before=preserve_before,
    )

    table_counts = {table: len(ids) for table, ids in sorted(deleted.items())}
    table_counts.update({
        "test_personnel_deletion_record_event_tombstones": len(captured["record_events"]),
        "test_personnel_deletion_command_tombstones": len(captured["commands"]),
        "test_personnel_deletion_lifecycle_tombstones": len(captured["lifecycle"]),
    })
    table_counts.update({
        f"preserved_{item['table']}": int(item["count"])
        for item in preserve_after.values()
    })
    after_hash = fingerprints.canonical_hash({
        "request_id": str(request_id),
        "deleted_id_hashes": {table: _id_hash(ids) for table, ids in sorted(deleted.items())},
        "tombstone_digests": sorted(
            row["canonical_digest"] for rows in captured.values() for row in rows
        ),
        "preserved_provenance_count": int(preserved),
        "preserve_verification": preserve_after,
        "remaining_rules": [],
    })
    new_version = int(request["version"]) + 1
    projection = _record_execute(
        conn, request=request, executor_user_id=executor_user_id,
        idempotency_key=idempotency_key, payload_hash=payload_hash,
        table_counts=table_counts, before_hash=before_hash, after_hash=after_hash,
        result="TD_EXECUTION_COMPLETED", error_code=None,
        new_status="COMPLETED", new_version=new_version,
    )
    updated = conn.execute(text("""UPDATE public.test_personnel_deletion_requests
        SET status='COMPLETED',version=:new_version,last_checked_at=statement_timestamp()
        WHERE request_id=:request_id AND status='APPROVED' AND version=:old_version
        RETURNING request_id"""), {
        "request_id": request_id, "old_version": request["version"], "new_version": new_version,
    }).scalar_one_or_none()
    if updated is None:
        raise _AtomicExecutionFailure(
            "TD_EXECUTION_REQUEST_STATE_RACE", "Request state changed concurrently.", 409,
        )
    _attempt_event(
        conn, request_id=request_id, executor_user_id=executor_user_id,
        idempotency_key=idempotency_key, payload_hash=payload_hash, event_type="RESULT",
        result_code="TD_EXECUTION_COMPLETED", error_code=None,
    )
    _fail_if_requested(fault_after_step, "AUDIT")
    return {"status": "COMPLETED", "replayed": False, "result": projection}


def _record_failed_attempt(
    *, request_id: UUID, executor_user_id: int, idempotency_key: UUID,
    payload_hash: str, error_code: str,
) -> None:
    """Persist a safe result after rollback; never hide persistence failure."""
    safe_code = error_code if re.fullmatch(r"TD_[A-Z0-9_]{1,124}", error_code) else "TD_EXECUTION_FAILED"
    def finish_attempt(conn: Connection) -> None:
        _attempt_event(
            conn, request_id=request_id, executor_user_id=executor_user_id,
            idempotency_key=idempotency_key, payload_hash=payload_hash, event_type="RESULT",
            result_code="TD_EXECUTION_FAILED", error_code=safe_code,
        )
    _run_serializable(finish_attempt)

    def write_audit(conn: Connection) -> None:
        request = approval_service._request_row(conn, request_id, True)
        if (
            request["status"] != "APPROVED"
            or int(request.get("manifest_version") or 1) != approval_service.MANIFEST_VERSION
        ):
            return
        if _existing_by_key(
            conn, request_id=request_id, executor_user_id=executor_user_id,
            idempotency_key=idempotency_key, payload_hash=payload_hash,
        ) is not None:
            return
        digest = fingerprints.canonical_hash({
            "request_id": str(request_id), "error_code": safe_code,
            "request_version": int(request["version"]),
        })
        _record_execute(
            conn, request=request, executor_user_id=executor_user_id,
            idempotency_key=idempotency_key, payload_hash=payload_hash,
            table_counts={}, before_hash=digest, after_hash=digest,
            result="TD_EXECUTION_FAILED", error_code=safe_code,
            new_status="APPROVED", new_version=int(request["version"]),
        )
    try:
        _run_serializable(write_audit)
    except Exception as error:
        raise approval_service.TestPersonnelDeletionError(
            "TD_EXECUTION_FAILURE_AUDIT_FAILED",
            "The failed attempt is durable, but its EXECUTE audit could not be persisted.", 503,
        ) from error


def _record_rejected_attempt_result(
    *, request_id: UUID, executor_user_id: int, idempotency_key: UUID,
    payload_hash: str, error_code: str,
) -> None:
    """Close an intent rejected by an authorization/approval contract gate."""
    safe_code = error_code if re.fullmatch(r"TD_[A-Z0-9_]{1,124}", error_code) else "TD_EXECUTION_FAILED"
    _run_serializable(lambda conn: _attempt_event(
        conn, request_id=request_id, executor_user_id=executor_user_id,
        idempotency_key=idempotency_key, payload_hash=payload_hash, event_type="RESULT",
        result_code="TD_EXECUTION_FAILED", error_code=safe_code,
    ))


def execute_request(
    *, request_id: UUID, executor_user_id: int, idempotency_key: UUID,
    confirmation: str, expected_snapshot: Mapping[str, Any],
    fault_after_step: str | None = None,
    _test_step_hook: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if not feature_enabled():
        raise approval_service.TestPersonnelDeletionError(
            "TD_EXECUTION_DISABLED", "Test personnel deletion execution is disabled.", 503,
        )
    request_uuid = UUID(str(request_id))
    key_uuid = UUID(str(idempotency_key))
    payload_hash = _payload_hash(
        request_uuid, key_uuid, confirmation, expected_snapshot,
    )
    intent_prepared = False
    try:
        _prepare_attempt(
            request_id=request_uuid, executor_user_id=int(executor_user_id),
            idempotency_key=key_uuid, payload_hash=payload_hash,
        )
        intent_prepared = True
        return _run_serializable(lambda conn: _execute_transaction(
            conn, request_id=request_uuid, executor_user_id=int(executor_user_id),
            idempotency_key=key_uuid, confirmation=confirmation,
            payload_hash=payload_hash, expected_snapshot=expected_snapshot,
            fault_after_step=fault_after_step,
            step_hook=_test_step_hook,
        ))
    except execute_audit.ExecuteAuditContractError as error:
        if intent_prepared:
            _record_rejected_attempt_result(
                request_id=request_uuid, executor_user_id=int(executor_user_id),
                idempotency_key=key_uuid, payload_hash=payload_hash, error_code=error.code,
            )
        raise approval_service.TestPersonnelDeletionError(error.code, str(error), 403) from error
    except _AtomicExecutionFailure as error:
        _record_failed_attempt(
            request_id=request_uuid, executor_user_id=int(executor_user_id),
            idempotency_key=key_uuid, payload_hash=payload_hash, error_code=error.code,
        )
        raise approval_service.TestPersonnelDeletionError(error.code, error.message, error.status_code) from error
    except approval_service.TestPersonnelDeletionError as error:
        if intent_prepared and error.code != "TD_EXECUTE_IDEMPOTENCY_CONFLICT":
            _record_failed_attempt(
                request_id=request_uuid, executor_user_id=int(executor_user_id),
                idempotency_key=key_uuid, payload_hash=payload_hash, error_code=error.code,
            )
        raise
    except DBAPIError as error:
        if intent_prepared:
            _record_failed_attempt(
                request_id=request_uuid, executor_user_id=int(executor_user_id),
                idempotency_key=key_uuid, payload_hash=payload_hash,
                error_code="TD_EXECUTION_DATABASE_CONSTRAINT",
            )
        raise approval_service.TestPersonnelDeletionError(
            "TD_EXECUTION_FAILED", "Execution failed safely; no partial deletion was committed.", 409,
        ) from error
