"""Normative ADR-065 ``adr065-po-evidence`` v1 verifier."""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import struct
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection


PROFILE_ID = "adr065-po-evidence"
PROFILE_VERSION = 1
KeyState = Literal["SCHEDULED", "ACTIVE", "VERIFICATION_ONLY", "REVOKED", "DESTROYED"]


@dataclass(frozen=True, slots=True)
class EvidenceKeySnapshot:
    organization_scope_id: str
    profile_id: str
    profile_version: int
    key_id: str
    state: KeyState
    column_hmac_key: bytes | None
    outer_hmac_key: bytes | None


class EvidenceKeyProvider(Protocol):
    def resolve_verification_key(
        self, *, organization_scope_id: str, profile_id: str, profile_version: int, key_id: str
    ) -> EvidenceKeySnapshot: ...


_provider: EvidenceKeyProvider | None = None


def configure_evidence_key_provider(provider: EvidenceKeyProvider | None) -> None:
    global _provider
    _provider = provider


def resolve_evidence_key_snapshot(
    *, profile_id: str, profile_version: int, key_id: str
) -> EvidenceKeySnapshot | None:
    """Resolve once before BEGIN; secrets never come from request or PostgreSQL."""
    organization_scope_id = os.getenv("ADR065_ORGANIZATION_SCOPE_ID", "")
    if not organization_scope_id or not organization_scope_id.isascii() or _provider is None:
        return None
    return _provider.resolve_verification_key(
        organization_scope_id=organization_scope_id,
        profile_id=profile_id,
        profile_version=profile_version,
        key_id=key_id,
    )


def _u64(value: int) -> bytes:
    return struct.pack(">Q", value)


def _lp(value: bytes) -> bytes:
    return _u64(len(value)) + value


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("non-finite decimal")
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"-0", ""} else rendered


def _jcs_number(value: int | float) -> str:
    if isinstance(value, bool):
        raise TypeError
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    if value == 0:
        return "0"
    absolute = abs(value)
    shortest = repr(value).lower()
    if 1e-6 <= absolute < 1e21:
        return _canonical_decimal(Decimal(shortest))
    mantissa, exponent = shortest.split("e") if "e" in shortest else (shortest, "0")
    mantissa = mantissa.rstrip("0").rstrip(".") if "." in mantissa else mantissa
    exponent_int = int(exponent)
    sign = "+" if exponent_int >= 0 else ""
    return f"{mantissa}e{sign}{exponent_int}"


def jcs_bytes(value: Any) -> bytes:
    def encode(item: Any) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            return _jcs_number(item)
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        if isinstance(item, dict):
            if not all(isinstance(key, str) for key in item):
                raise ValueError("JSON object key is not text")
            keys = sorted(item, key=lambda key: key.encode("utf-16-be", "surrogatepass"))
            return "{" + ",".join(
                json.dumps(key, ensure_ascii=False) + ":" + encode(item[key]) for key in keys
            ) + "}"
        raise ValueError("unsupported JSON value")

    return encode(value).encode("utf-8")


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("naive timestamp")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _tv(value: Any) -> bytes:
    if value is None:
        return b"N"
    if isinstance(value, bool):
        return b"B" + (b"\x01" if value else b"\x00")
    if isinstance(value, int):
        return b"I" + _lp(str(value).encode("ascii"))
    if isinstance(value, Decimal):
        return b"D" + _lp(_canonical_decimal(value).encode("ascii"))
    if isinstance(value, datetime):
        return b"t" + _lp(_timestamp(value).encode("ascii"))
    if isinstance(value, date):
        return b"d" + _lp(value.isoformat().encode("ascii"))
    if isinstance(value, UUID):
        return b"u" + _lp(str(value).encode("ascii"))
    if isinstance(value, bytes):
        return b"x" + _lp(value)
    if isinstance(value, str):
        return b"s" + _lp(value.encode("utf-8"))
    if isinstance(value, (dict, list, float)):
        return b"j" + _lp(jcs_bytes(value))
    raise ValueError("unsupported typed value")


PROTECTED = {
    "personnel_orders": {"basis_summary", "comment"},
    "personnel_order_items": {"payload"},
    "personnel_order_item_bases": {"free_text", "metadata"},
    "personnel_order_attachments": {"file_path", "file_url", "file_comment"},
}


def _replacement(
    *, snapshot: EvidenceKeySnapshot, table: str, pk_name: str, pk: int, column: str, value: Any
) -> Any:
    if value is None:
        return None
    if snapshot.column_hmac_key is None:
        raise RuntimeError("key unavailable")
    message = (
        b"ADR065-PO-EVIDENCE-COLUMN\x00"
        + _lp(PROFILE_ID.encode("ascii")) + _lp(b"1")
        + _lp(snapshot.organization_scope_id.encode("utf-8"))
        + _lp(snapshot.key_id.encode("utf-8"))
        + _lp(table.encode("ascii")) + _lp(pk_name.encode("ascii"))
        + _lp(str(pk).encode("ascii")) + _lp(column.encode("ascii"))
        + _lp(_tv(value))
    )
    digest = hmac.new(snapshot.column_hmac_key, message, hashlib.sha256).hexdigest()
    return {"algorithm": "HMAC-SHA-256", "profile_id": PROFILE_ID,
            "profile_version": 1, "key_id": snapshot.key_id, "fingerprint": digest}


COLLECTIONS = (
    ("header", "personnel_orders", "order_id", ("order_id", "order_number", "order_date", "order_type_code", "order_class", "status", "source_mode", "legal_basis_article", "signed_by_employee_id", "signed_by_name", "signed_by_position", "executor_name", "basis_summary", "comment", "void_reason", "voided_at", "voided_by", "void_kind", "archived_at", "archived_by", "archive_reason_code", "archive_reason_text", "created_by", "created_at", "updated_at")),
    ("items", "personnel_order_items", "item_id", ("item_id", "order_id", "item_number", "item_type_code", "employee_id", "effective_date", "period_start", "period_end", "payload", "item_status", "void_reason", "voided_at", "voided_by", "created_at")),
    ("item_bases", "personnel_order_item_bases", "item_basis_id", ("item_basis_id", "order_item_id", "basis_type", "subject_employee_id", "document_date", "document_number", "free_text", "metadata", "created_at", "updated_at")),
    ("attachments", "personnel_order_attachments", "attachment_id", ("attachment_id", "order_id", "attachment_kind", "storage_type", "file_path", "file_url", "file_comment", "locale", "created_by", "created_at")),
)


class EvidenceFingerprintError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def verify_personnel_order_evidence_tx(
    conn: Connection, *, order_id: int, item_id: int, requested_hex: str,
    profile_id: str, profile_version: int, key_id: str,
    key_snapshot: EvidenceKeySnapshot | None,
) -> None:
    if profile_id != PROFILE_ID:
        raise EvidenceFingerprintError("EVIDENCE_PROFILE_UNSUPPORTED")
    if profile_version != PROFILE_VERSION:
        raise EvidenceFingerprintError("EVIDENCE_PROFILE_VERSION_UNSUPPORTED")

    scope_relation = conn.execute(text("SELECT to_regclass('public.personnel_order_evidence_scopes')")).scalar_one()
    if scope_relation is None:
        raise EvidenceFingerprintError("EVIDENCE_STATE_INCOMPLETE")
    scope_rows = list(conn.execute(text("SELECT order_id,generation FROM public.personnel_order_evidence_scopes WHERE order_id=:id"), {"id": order_id}).mappings())
    if len(scope_rows) != 1 or int(scope_rows[0]["generation"]) <= 0:
        raise EvidenceFingerprintError("EVIDENCE_STATE_INCOMPLETE")

    queries = {
        "header": "SELECT * FROM public.personnel_orders WHERE order_id=:id ORDER BY order_id",
        "items": "SELECT * FROM public.personnel_order_items WHERE order_id=:id ORDER BY item_id",
        "item_bases": "SELECT b.* FROM public.personnel_order_item_bases b JOIN public.personnel_order_items i ON i.item_id=b.order_item_id WHERE i.order_id=:id ORDER BY b.item_basis_id",
        "attachments": "SELECT * FROM public.personnel_order_attachments WHERE order_id=:id ORDER BY attachment_id",
    }
    raw = {name: list(conn.execute(text(sql), {"id": order_id}).mappings()) for name, sql in queries.items()}
    if len(raw["header"]) != 1 or not raw["items"]:
        raise EvidenceFingerprintError("EVIDENCE_STATE_INCOMPLETE")
    if item_id not in {int(row["item_id"]) for row in raw["items"]}:
        raise EvidenceFingerprintError("EVIDENCE_REFERENCE_INVALID")

    if key_snapshot is None:
        raise EvidenceFingerprintError("EVIDENCE_FINGERPRINT_UNVERIFIABLE")
    if (key_snapshot.profile_id, key_snapshot.profile_version, key_snapshot.key_id) != (profile_id, profile_version, key_id):
        raise EvidenceFingerprintError("EVIDENCE_KEY_UNKNOWN")
    state_codes = {"SCHEDULED": "EVIDENCE_KEY_NOT_YET_VALID", "REVOKED": "EVIDENCE_KEY_REVOKED", "DESTROYED": "EVIDENCE_KEY_DESTROYED"}
    if key_snapshot.state in state_codes:
        raise EvidenceFingerprintError(state_codes[key_snapshot.state])
    if key_snapshot.state not in {"ACTIVE", "VERIFICATION_ONLY"}:
        raise EvidenceFingerprintError("EVIDENCE_KEY_UNKNOWN")
    if not key_snapshot.column_hmac_key or not key_snapshot.outer_hmac_key:
        raise EvidenceFingerprintError("EVIDENCE_FINGERPRINT_UNVERIFIABLE")

    envelope_collections: dict[str, Any] = {}
    try:
        for name, table, pk_name, columns in COLLECTIONS:
            tuples = []
            for row in raw[name]:
                pk = int(row[pk_name])
                values = []
                for column in columns:
                    if column not in row:
                        raise EvidenceFingerprintError("EVIDENCE_STRUCTURAL_CONFLICT")
                    value = row[column]
                    if column in PROTECTED[table]:
                        value = _replacement(snapshot=key_snapshot, table=table, pk_name=pk_name, pk=pk, column=column, value=value)
                    elif isinstance(value, Decimal):
                        value = _canonical_decimal(value)
                    elif isinstance(value, datetime):
                        value = _timestamp(value)
                    elif isinstance(value, date):
                        value = value.isoformat()
                    elif isinstance(value, int) and not isinstance(value, bool):
                        value = str(value)
                    values.append(value)
                tuples.append(values)
            envelope_collections[name] = tuples
        envelope = {"algorithm": "HMAC-SHA-256", "profile_id": PROFILE_ID,
                    "profile_version": 1, "key_id": key_id,
                    "organization_scope_id": key_snapshot.organization_scope_id,
                    "personnel_order_id": str(order_id),
                    "selected_evidence_item_id": str(item_id),
                    "evidence_scope_generation": str(int(scope_rows[0]["generation"])),
                    **envelope_collections}
        encoded = jcs_bytes(envelope)
    except EvidenceFingerprintError:
        raise
    except Exception as exc:
        raise EvidenceFingerprintError("EVIDENCE_STRUCTURAL_CONFLICT") from exc
    message = (b"ADR065-PO-EVIDENCE-OUTER\x00" + _lp(PROFILE_ID.encode("ascii"))
               + _lp(b"1") + _lp(key_snapshot.organization_scope_id.encode("utf-8"))
               + _lp(key_id.encode("utf-8")) + _lp(encoded))
    computed = hmac.new(key_snapshot.outer_hmac_key, message, hashlib.sha256).digest()
    if not hmac.compare_digest(bytes.fromhex(requested_hex), computed):
        raise EvidenceFingerprintError("EVIDENCE_FINGERPRINT_MISMATCH")
