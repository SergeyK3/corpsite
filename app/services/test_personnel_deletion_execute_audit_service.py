"""WP-TD-005 stage 4 EXECUTE audit contract.

The helpers in this module are intentionally not connected to an HTTP route or
to the approval workflow.  They perform no deletion and write no tombstones.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.test_personnel_deletion_fingerprint_service import canonical_hash


EXECUTE_PERMISSION = "TEST_PERSONNEL_DELETION_EXECUTE"
_HASH = re.compile(r"^[0-9a-f]{64}$")
_SAFE_CODE = re.compile(r"^TD_[A-Z0-9_]{1,124}$")
_SAFE_IDEMPOTENCY_KEY = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_SAFE_TABLE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class ExecuteAuditContractError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _request_uuid(value: Any) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ExecuteAuditContractError("TD_EXECUTE_REQUEST_ID_INVALID", "Invalid request ID.") from error


def _safe_hash(value: str, field: str) -> str:
    normalized = str(value or "")
    if not _HASH.fullmatch(normalized):
        raise ExecuteAuditContractError("TD_EXECUTE_AUDIT_HASH_INVALID", f"Invalid {field}.")
    return normalized


def _safe_code(value: str, field: str) -> str:
    normalized = str(value or "")
    if not _SAFE_CODE.fullmatch(normalized):
        raise ExecuteAuditContractError("TD_EXECUTE_AUDIT_CODE_INVALID", f"Invalid {field}.")
    return normalized


def _safe_counts(value: Mapping[str, int]) -> dict[str, int]:
    result: dict[str, int] = {}
    for table, count in value.items():
        name = str(table)
        if not _SAFE_TABLE.fullmatch(name) or isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ExecuteAuditContractError(
                "TD_EXECUTE_AUDIT_COUNTS_INVALID", "Table counts must be non-negative technical counters.",
            )
        result[name] = count
    return dict(sorted(result.items()))


def assert_approver_executor_separation(
    conn: Connection, *, request_id: Any, executor_user_id: int,
) -> dict[str, Any]:
    """Return the frozen approval or fail if its approver is the executor."""
    request_uuid = _request_uuid(request_id)
    approval = conn.execute(text("""SELECT decision_id,actor_user_id,request_version,
            target_set_hash,relationship_fingerprint,fingerprint_version,
            catalog_fingerprint,decided_at
        FROM public.test_personnel_deletion_decisions
        WHERE request_id=:request_id AND decision='APPROVE'
        ORDER BY decision_id DESC LIMIT 1"""), {
            "request_id": request_uuid,
        }).mappings().one_or_none()
    if approval is None:
        raise ExecuteAuditContractError("TD_EXECUTE_APPROVAL_REQUIRED", "Approved decision is required.")
    if int(approval["actor_user_id"]) == int(executor_user_id):
        raise ExecuteAuditContractError(
            "TD_EXECUTE_APPROVER_CONFLICT",
            "The approving HR_HEAD user cannot execute the same request.",
        )
    return dict(approval)


def assert_executor_permission(conn: Connection, *, executor_user_id: int) -> None:
    """Fail unless the active executor is an ADMIN covered by the execute grant."""
    allowed = conn.execute(text("""SELECT EXISTS(
            SELECT 1 FROM public.users executor
            JOIN public.roles primary_role ON primary_role.role_id=executor.role_id
            JOIN public.access_grants grant_def
              ON grant_def.target_type='ROLE' AND grant_def.target_id=primary_role.role_id
            JOIN public.access_roles access_role
              ON access_role.access_role_id=grant_def.access_role_id
            WHERE executor.user_id=:executor_user_id AND executor.is_active=TRUE
              AND primary_role.code='ADMIN'
              AND access_role.code='TEST_PERSONNEL_DELETION_EXECUTE'
              AND grant_def.active_flag=TRUE
              AND grant_def.starts_at<=transaction_timestamp()
              AND (grant_def.ends_at IS NULL OR grant_def.ends_at>transaction_timestamp())
        )"""), {"executor_user_id": int(executor_user_id)}).scalar_one()
    if not allowed:
        raise ExecuteAuditContractError(
            "TD_EXECUTE_PERMISSION_REQUIRED", "Executor permission is required.",
        )


def record_execute_audit(
    conn: Connection,
    *,
    request_id: Any,
    executor_user_id: int,
    table_counts: Mapping[str, int],
    before_hash: str,
    after_hash: str,
    idempotency_key: str,
    result: str,
    error_code: str | None,
) -> dict[str, Any]:
    """Write a simulated EXECUTE audit row; caller owns the transaction.

    Stage 4 exposes no endpoint and no workflow caller.  A later stage may call
    this only from the same transaction as execution after all gates pass.
    """
    request_uuid = _request_uuid(request_id)
    executor_id = int(executor_user_id)
    key = str(idempotency_key or "")
    if executor_id <= 0 or not _SAFE_IDEMPOTENCY_KEY.fullmatch(key):
        raise ExecuteAuditContractError(
            "TD_EXECUTE_AUDIT_IDENTITY_INVALID", "Executor ID or idempotency key is invalid.",
        )
    result_code = _safe_code(result, "result")
    safe_error = None if error_code is None else _safe_code(error_code, "error_code")
    counts = _safe_counts(table_counts)
    safe_before = _safe_hash(before_hash, "before_hash")
    safe_after = _safe_hash(after_hash, "after_hash")

    request = conn.execute(text("""SELECT request_id,status,version,manifest_version,
            process_type,target_set_hash,relationship_fingerprint,fingerprint_version,
            relationship_policy_version,catalog_version,catalog_fingerprint,
            approval_expires_at
        FROM public.test_personnel_deletion_requests
        WHERE request_id=:request_id"""), {"request_id": request_uuid}).mappings().one_or_none()
    if request is None:
        raise ExecuteAuditContractError("TD_EXECUTE_REQUEST_NOT_FOUND", "Request was not found.")
    if request["status"] != "APPROVED" or (
        request["approval_expires_at"] is None
        or request["approval_expires_at"] <= conn.execute(text("SELECT transaction_timestamp()" )).scalar_one()
    ):
        raise ExecuteAuditContractError("TD_EXECUTE_APPROVAL_REQUIRED", "Current approval is required.")
    assert_executor_permission(conn, executor_user_id=executor_id)
    approval = assert_approver_executor_separation(
        conn, request_id=request_uuid, executor_user_id=executor_id,
    )
    if (
        int(approval["request_version"]) != int(request["version"])
        or approval["target_set_hash"] != request["target_set_hash"]
        or approval["relationship_fingerprint"] != request["relationship_fingerprint"]
        or approval["fingerprint_version"] != request["fingerprint_version"]
        or approval["catalog_fingerprint"] != request["catalog_fingerprint"]
    ):
        raise ExecuteAuditContractError(
            "TD_EXECUTE_APPROVAL_FINGERPRINT_MISMATCH", "Approval does not match the frozen request.",
        )

    frozen = {
        "request_id": str(request_uuid),
        "executor_user_id": executor_id,
        "manifest_version": int(request["manifest_version"]),
        "fingerprint_version": str(request["fingerprint_version"]),
        "target_set_hash": _safe_hash(request["target_set_hash"], "target_set_hash"),
        "relationship_fingerprint": _safe_hash(
            request["relationship_fingerprint"], "relationship_fingerprint",
        ),
        "policy_version": str(request["relationship_policy_version"]),
        "catalog_version": str(request["catalog_version"]),
        "catalog_fingerprint": _safe_hash(request["catalog_fingerprint"], "catalog_fingerprint"),
        "table_counts": counts,
        "before_hash": safe_before,
        "after_hash": safe_after,
        "idempotency_key": key,
        "result": result_code,
        "error_code": safe_error,
    }
    command_hash = canonical_hash(frozen)
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {
        "key": f"WP-TD-005:EXECUTE:{key}",
    })
    existing = conn.execute(text("""SELECT request_id,actor_user_id,
            command_payload_hash,result_projection
        FROM public.test_personnel_deletion_history
        WHERE action='EXECUTE' AND idempotency_key=:key"""), {"key": key}).mappings().one_or_none()
    if existing is not None:
        if (
            existing["request_id"] != request_uuid
            or int(existing["actor_user_id"]) != executor_id
            or existing["command_payload_hash"] != command_hash
        ):
            raise ExecuteAuditContractError(
                "TD_EXECUTE_IDEMPOTENCY_CONFLICT",
                "Idempotency key is already bound to different technical content.",
            )
        return dict(existing["result_projection"])

    occurred_at = conn.execute(text("SELECT statement_timestamp()" )).scalar_one()
    projection = {**frozen, "timestamp": occurred_at.isoformat()}
    inserted = conn.execute(text("""INSERT INTO public.test_personnel_deletion_history(
            request_id,actor_user_id,actor_role_code,permission_code,action,
            old_status,new_status,old_version,new_version,target_set_hash,comment,
            idempotency_key,command_payload_hash,occurred_at,result_code,result_projection)
        VALUES(:request_id,:executor,'ADMIN',:permission,'EXECUTE',
            'APPROVED','APPROVED',:version,:version,:target_hash,NULL,
            :key,:command_hash,:occurred_at,:result,CAST(:projection AS jsonb))
        RETURNING result_projection"""), {
            "request_id": request_uuid,
            "executor": executor_id,
            "permission": EXECUTE_PERMISSION,
            "version": int(request["version"]),
            "target_hash": request["target_set_hash"],
            "key": key,
            "command_hash": command_hash,
            "occurred_at": occurred_at,
            "result": result_code,
            "projection": json.dumps(projection, sort_keys=True, separators=(",", ":")),
        }).scalar_one()
    return dict(inserted)
