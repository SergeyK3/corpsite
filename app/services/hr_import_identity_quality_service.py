"""IQ-3 system classification for identity-quality exceptions on new HR imports."""
from __future__ import annotations

import hashlib
import json
import re
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.hr_import import IDENTITY_QUALITY_POLICY_V1

_IIN_RE = re.compile(r"[0-9]{12}\Z")

_SYSTEM_DECISIONS = {
    "IIN_MISSING": ("SYSTEM_IIN_MISSING", "UNRESOLVED"),
    "IIN_INVALID_FORMAT": ("SYSTEM_IIN_INVALID_FORMAT", "UNRESOLVED"),
    "IIN_UNMATCHED": ("SYSTEM_IIN_UNMATCHED", "UNRESOLVED"),
}


def _fingerprint(payload: object) -> str:
    """Return a PII-free SHA-256 digest; never persist the serialized input."""
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _identity_reason(
    conn: Connection,
    iin: object,
    *,
    iin_quality_issue: object = None,
) -> str | None:
    if iin_quality_issue == "IIN_INVALID_FORMAT":
        return "IIN_INVALID_FORMAT"
    if iin is None or iin == "":
        return "IIN_MISSING"
    if not isinstance(iin, str) or _IIN_RE.fullmatch(iin) is None:
        return "IIN_INVALID_FORMAT"

    employee_ids = conn.execute(
        text(
            """
            SELECT DISTINCT ei.employee_id
            FROM public.employee_identities ei
            JOIN public.employees e ON e.employee_id = ei.employee_id
            WHERE ei.identity_type = 'IIN'
              AND ei.valid_to IS NULL
              AND e.is_active IS TRUE
              AND ei.identity_value = :iin
            ORDER BY ei.employee_id
            """
        ),
        {"iin": iin},
    ).scalars().all()
    return None if len(employee_ids) == 1 else "IIN_UNMATCHED"


def _persist_system_decision(
    conn: Connection,
    *,
    batch_id: int,
    row_id: int,
    raw_payload: object,
    normalized_payload: object,
    reason_code: str,
) -> bool:
    event_type, identity_state = _SYSTEM_DECISIONS[reason_code]
    source_fingerprint = _fingerprint(raw_payload)
    payload_fingerprint = _fingerprint(normalized_payload)
    original_iin_fingerprint = None
    iin = (normalized_payload or {}).get("iin") if isinstance(normalized_payload, dict) else None
    if reason_code != "IIN_MISSING":
        original_iin_fingerprint = _fingerprint({"iin": iin})

    current = conn.execute(
        text(
            """
            SELECT current_event_id, identity_state, reason_code,
                   source_row_fingerprint, normalized_payload_fingerprint,
                   person_id, employee_id
            FROM public.hr_import_identity_quality_states
            WHERE batch_id = :batch_id AND row_id = :row_id
            FOR UPDATE
            """
        ),
        {"batch_id": batch_id, "row_id": row_id},
    ).mappings().first()
    if current is not None:
        expected = {
            "identity_state": identity_state,
            "reason_code": reason_code,
            "source_row_fingerprint": source_fingerprint,
            "normalized_payload_fingerprint": payload_fingerprint,
            "person_id": None,
            "employee_id": None,
        }
        if all(current[key] == value for key, value in expected.items()):
            return False
        raise RuntimeError("IQ-3 refuses to overwrite an existing identity-quality decision")

    idempotency_key = str(
        uuid5(NAMESPACE_URL, f"hr-import-iq3:{batch_id}:{row_id}:{source_fingerprint}:{event_type}")
    )
    event_id = conn.execute(
        text(
            """
            INSERT INTO public.hr_import_identity_review_events (
                idempotency_key, batch_id, row_id, event_type, resulting_state,
                reason_code, actor_type, actor_user_id, occurred_at,
                person_id, employee_id, original_iin_fingerprint,
                entered_iin_fingerprint, source_row_fingerprint,
                before_normalized_payload_fingerprint, after_normalized_payload_fingerprint,
                row_version, source_version, policy_version
            ) VALUES (
                CAST(:idempotency_key AS uuid), :batch_id, :row_id, :event_type,
                :identity_state, :reason_code, 'SYSTEM', NULL, clock_timestamp(),
                NULL, NULL, :original_iin_fingerprint, NULL, :source_fingerprint,
                :payload_fingerprint, :payload_fingerprint, 1, 1, :policy_version
            )
            RETURNING event_id
            """
        ),
        {
            "idempotency_key": idempotency_key,
            "batch_id": batch_id,
            "row_id": row_id,
            "event_type": event_type,
            "identity_state": identity_state,
            "reason_code": reason_code,
            "original_iin_fingerprint": original_iin_fingerprint,
            "source_fingerprint": source_fingerprint,
            "payload_fingerprint": payload_fingerprint,
            "policy_version": IDENTITY_QUALITY_POLICY_V1,
        },
    ).scalar_one()
    conn.execute(
        text(
            """
            INSERT INTO public.hr_import_identity_quality_states (
                batch_id, row_id, current_event_id, identity_state, reason_code,
                person_id, employee_id, source_row_fingerprint,
                normalized_payload_fingerprint, row_version, source_version,
                policy_version
            ) VALUES (
                :batch_id, :row_id, :event_id, :identity_state, :reason_code,
                NULL, NULL, :source_fingerprint, :payload_fingerprint, 1, 1,
                :policy_version
            )
            """
        ),
        {
            "batch_id": batch_id,
            "row_id": row_id,
            "event_id": event_id,
            "identity_state": identity_state,
            "reason_code": reason_code,
            "source_fingerprint": source_fingerprint,
            "payload_fingerprint": payload_fingerprint,
            "policy_version": IDENTITY_QUALITY_POLICY_V1,
        },
    )
    return True


def classify_import_identity_quality(conn: Connection, *, batch_id: int) -> int:
    """Persist IQ-3 SYSTEM state/events for employee rows requiring HR review.

    Exact active-IIN matches deliberately create no identity exception.  The
    existing IQ-1 binding path remains the sole automatic binding mechanism.
    """
    rows = conn.execute(
        text(
            """
            SELECT row_id, raw_payload, normalized_payload
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
              AND COALESCE((normalized_payload->'metadata'->>'is_employee_roster')::boolean, FALSE)
            FOR UPDATE
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()
    persisted = 0
    for row in rows:
        normalized_payload = dict(row["normalized_payload"] or {})
        metadata = normalized_payload.get("metadata") or {}
        reason_code = _identity_reason(
            conn,
            normalized_payload.get("iin"),
            iin_quality_issue=(metadata.get("iin_quality_issue") if isinstance(metadata, dict) else None),
        )
        if reason_code is None:
            continue
        if _persist_system_decision(
            conn,
            batch_id=batch_id,
            row_id=int(row["row_id"]),
            raw_payload=dict(row["raw_payload"] or {}),
            normalized_payload=normalized_payload,
            reason_code=reason_code,
        ):
            persisted += 1
    return persisted
