"""Shared transaction-aware PostgreSQL protocol for canonical IIN writers.

This module never commits, rolls back, logs, or exposes an IIN in an exception.  Callers must
already own the business transaction.  The advisory lock serializes the absent-row case; the
existing partial unique indexes remain the final database integrity barrier.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.domain.iin import IinValidationError, validate_iin


IIN_ADVISORY_LOCK_NAMESPACE = "personnel.identity_iin.v1"


class IinWriterProtocolError(RuntimeError):
    """Safe, code-only failure for IIN writers."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class IinLockedState:
    person_ids: tuple[int, ...]
    active_identity_ids: tuple[int, ...]
    active_identity_employee_ids: tuple[int, ...]


def _validated_normalized_iin(iin: str) -> str:
    try:
        return validate_iin(iin)
    except IinValidationError as exc:
        raise IinWriterProtocolError("IIN_INVALID") from exc


def acquire_iin_advisory_locks_tx(conn: Connection, iins: Iterable[str]) -> tuple[str, ...]:
    """Acquire transaction-scoped locks in deterministic normalized-IIN order."""
    normalized = tuple(sorted({_validated_normalized_iin(value) for value in iins}))
    for iin in normalized:
        conn.execute(
            text(
                "SELECT pg_advisory_xact_lock("
                "hashtextextended(:namespace || ':' || :iin, 0))"
            ),
            {"namespace": IIN_ADVISORY_LOCK_NAMESPACE, "iin": iin},
        )
    return normalized


def lock_and_recheck_iin_tx(conn: Connection, *, iin: str) -> IinLockedState:
    """Lock one normalized IIN then reread Person and active Employee-IIN holders."""
    normalized = acquire_iin_advisory_locks_tx(conn, (iin,))[0]
    person_ids = tuple(
        int(value)
        for value in conn.execute(
            text(
                "SELECT person_id FROM public.persons WHERE iin=:iin "
                "ORDER BY person_id FOR UPDATE"
            ),
            {"iin": normalized},
        ).scalars()
    )
    identity_rows = conn.execute(
        text(
            "SELECT identity_id, employee_id FROM public.employee_identities "
            "WHERE identity_type='IIN' AND identity_value=:iin AND valid_to IS NULL "
            "ORDER BY identity_id FOR UPDATE"
        ),
        {"iin": normalized},
    ).mappings().all()
    return IinLockedState(
        person_ids=person_ids,
        active_identity_ids=tuple(int(row["identity_id"]) for row in identity_rows),
        active_identity_employee_ids=tuple(int(row["employee_id"]) for row in identity_rows),
    )


def ensure_employee_iin_identity_tx(
    conn: Connection, *, employee_id: int, iin: str, created_by: int
) -> tuple[int, bool]:
    """Adopt the exact active IIN identity or insert it through the shared protocol."""
    normalized = _validated_normalized_iin(iin)
    state = lock_and_recheck_iin_tx(conn, iin=normalized)
    holders = set(state.active_identity_employee_ids)
    if holders - {int(employee_id)}:
        raise IinWriterProtocolError("IIN_EMPLOYEE_CONFLICT")

    employee_rows = conn.execute(
        text(
            "SELECT identity_id, identity_value FROM public.employee_identities "
            "WHERE employee_id=:employee_id AND identity_type='IIN' AND valid_to IS NULL "
            "ORDER BY identity_id FOR UPDATE"
        ),
        {"employee_id": int(employee_id)},
    ).mappings().all()
    if employee_rows:
        if len(employee_rows) != 1 or str(employee_rows[0]["identity_value"]) != normalized:
            raise IinWriterProtocolError("EMPLOYEE_IIN_CONFLICT")
        return int(employee_rows[0]["identity_id"]), False

    identity_id = conn.execute(
        text(
            "INSERT INTO public.employee_identities "
            "(employee_id, identity_type, identity_value, is_primary, created_by) "
            "VALUES (:employee_id, 'IIN', :iin, TRUE, :created_by) RETURNING identity_id"
        ),
        {"employee_id": int(employee_id), "iin": normalized, "created_by": int(created_by)},
    ).scalar_one()
    return int(identity_id), True
