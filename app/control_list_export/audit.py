"""PII-minimizing audit writer for control-list export attempts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from sqlalchemy.engine import Engine

from app.services.security_audit_service import write_security_event

CONTROL_LIST_EXPORT_AUDIT_EVENT = "CONTROL_LIST_EXPORT"
ControlListExportAuditResult = Literal["SUCCESS", "FORBIDDEN", "CONFLICT", "ERROR"]


class ControlListAuditError(RuntimeError):
    """The mandatory export audit record could not be persisted."""


@dataclass(frozen=True)
class ControlListAuditScope:
    organization_wide: bool | None
    org_unit_ids: tuple[int, ...] | None
    resolution: Literal["RESOLVED", "NOT_RESOLVED"]

    @classmethod
    def unresolved(cls) -> "ControlListAuditScope":
        return cls(
            organization_wide=None,
            org_unit_ids=None,
            resolution="NOT_RESOLVED",
        )

    @classmethod
    def from_projection_scope(cls, scope: Any) -> "ControlListAuditScope":
        return cls(
            organization_wide=scope.organization_wide,
            org_unit_ids=(
                None
                if scope.org_unit_ids is None
                else tuple(sorted({int(value) for value in scope.org_unit_ids}))
            ),
            resolution="RESOLVED",
        )


def write_control_list_export_audit(
    db_engine: Engine,
    *,
    actor_user_id: int | None,
    request_id: str,
    result: ControlListExportAuditResult,
    scope: ControlListAuditScope,
    schema_version: str,
    as_of_date: date | None = None,
    row_count: int | None = None,
    error_code: str | None = None,
    sha256: str | None = None,
    ip_address: str | None = None,
) -> int:
    """Persist one attempt in its own transaction, without projection content."""

    if result == "SUCCESS":
        if row_count is None or error_code is not None or sha256 is None:
            raise ValueError(
                "Successful audit requires row_count, checksum and no error_code."
            )
    elif row_count is not None or not error_code or sha256 is not None:
        raise ValueError(
            "Failed audit requires error_code and no row_count or checksum."
        )

    metadata = {
        "operation": "CONTROL_LIST_EXPORT",
        "result": result,
        "scope": {
            "organization_wide": scope.organization_wide,
            "org_unit_ids": list(scope.org_unit_ids) if scope.org_unit_ids is not None else None,
            "resolution": scope.resolution,
        },
        "filters": {},
        "schema_version": schema_version,
        "as_of_date": as_of_date.isoformat() if as_of_date is not None else None,
        "row_count": row_count,
        "error_code": error_code,
        "sha256": sha256,
    }
    with db_engine.begin() as conn:
        audit_id = write_security_event(
            event_type=CONTROL_LIST_EXPORT_AUDIT_EVENT,
            actor_user_id=actor_user_id,
            ip_address=ip_address,
            success=result == "SUCCESS",
            failure_reason=error_code,
            metadata=metadata,
            request_id=request_id,
            conn=conn,
        )
    if audit_id is None:
        raise ControlListAuditError("Control-list export audit is unavailable.")
    return audit_id
