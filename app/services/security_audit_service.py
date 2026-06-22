"""ADR-042 Phase B3 — security audit writer (append-only)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from ipaddress import ip_address as parse_ip_address
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine

_FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "password",
        "password_plain",
        "password_hash",
        "temp_password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "hash",
    }
)

_FORBIDDEN_METADATA_PATTERN = re.compile(
    r"(password|passwd|pwd|secret|token|hash)",
    re.IGNORECASE,
)

_ALLOWED_EVENT_TYPES = frozenset(
    {
        "LOGIN_SUCCESS",
        "LOGIN_FAILED",
        "LOGOUT",
        "PASSWORD_RESET_REQUESTED",
        "PASSWORD_RESET_COMPLETED",
        "PASSWORD_CHANGED",
        "TEMP_PASSWORD_ISSUED",
        "USER_LOCKED",
        "USER_UNLOCKED",
        "ACCESS_GRANTED",
        "ACCESS_REVOKED",
        "ACCESS_CHANGED",
        "ENROLLMENT_APPROVED",
        "ENROLLMENT_REJECTED",
        "ENROLLMENT_COMPLETED",
        "USER_BLOCKED",
        "USER_UNBLOCKED",
        "PERSON_IIN_RECONCILED",
        "VISIBILITY_GRANTED",
        "VISIBILITY_REVOKED",
        "USER_EMPLOYEE_LINKED",
        "USER_EMPLOYEE_UNLINKED",
        "USER_EMPLOYEE_LINK_ROLLED_BACK",
        "EMPLOYEE_ENROLLED_FROM_IMPORT",
    }
)


def security_audit_log_available(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'security_audit_log'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Remove password-like keys; raise ValueError if nested forbidden content detected."""
    if not metadata:
        return {}

    def _walk(obj: Any, path: str = "") -> Dict[str, Any]:
        if isinstance(obj, dict):
            cleaned: Dict[str, Any] = {}
            for key, value in obj.items():
                key_str = str(key)
                key_lower = key_str.lower()
                if key_lower in _FORBIDDEN_METADATA_KEYS:
                    raise ValueError(f"Forbidden metadata key: {key_str}")
                if _FORBIDDEN_METADATA_PATTERN.search(key_str):
                    raise ValueError(f"Forbidden metadata key pattern: {key_str}")
                cleaned[key_str] = _walk(value, f"{path}.{key_str}" if path else key_str)
            return cleaned
        if isinstance(obj, list):
            return [_walk(item, path) for item in obj]
        if isinstance(obj, str) and _FORBIDDEN_METADATA_PATTERN.search(path):
            raise ValueError(f"Forbidden metadata at path: {path}")
        return obj

    return _walk(dict(metadata))


def _normalize_ip_address(value: Optional[str]) -> Optional[str]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return str(parse_ip_address(raw))
    except ValueError:
        return None


def write_security_event(
    *,
    event_type: str,
    actor_user_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
    target_person_id: Optional[int] = None,
    target_employee_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    failure_reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    conn: Optional[Connection] = None,
) -> Optional[int]:
    normalized_type = (event_type or "").strip().upper()
    if normalized_type not in _ALLOWED_EVENT_TYPES:
        raise ValueError(f"Unsupported event_type: {event_type}")

    clean_metadata = sanitize_metadata(metadata)
    normalized_ip = _normalize_ip_address(ip_address)

    sql = text(
        """
        INSERT INTO public.security_audit_log (
            event_type,
            actor_user_id,
            target_user_id,
            target_person_id,
            target_employee_id,
            ip_address,
            user_agent,
            success,
            failure_reason,
            metadata,
            request_id
        )
        VALUES (
            :event_type,
            :actor_user_id,
            :target_user_id,
            :target_person_id,
            :target_employee_id,
            CAST(:ip_address AS inet),
            :user_agent,
            :success,
            :failure_reason,
            CAST(:metadata AS jsonb),
            :request_id
        )
        RETURNING audit_id
        """
    )
    params = {
        "event_type": normalized_type,
        "actor_user_id": actor_user_id,
        "target_user_id": target_user_id,
        "target_person_id": target_person_id,
        "target_employee_id": target_employee_id,
        "ip_address": normalized_ip,
        "user_agent": user_agent,
        "success": success,
        "failure_reason": failure_reason,
        "metadata": json.dumps(clean_metadata),
        "request_id": request_id,
    }

    if conn is not None:
        if not security_audit_log_available(conn):
            return None
        row = conn.execute(sql, params).first()
        return int(row[0]) if row else None

    with engine.begin() as own_conn:
        if not security_audit_log_available(own_conn):
            return None
        row = own_conn.execute(sql, params).first()
        return int(row[0]) if row else None


def list_security_events(
    *,
    event_type: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
    target_person_id: Optional[int] = None,
    target_employee_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))

    filters = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if event_type:
        filters.append("event_type = :event_type")
        params["event_type"] = event_type.strip().upper()
    if actor_user_id is not None:
        filters.append("actor_user_id = :actor_user_id")
        params["actor_user_id"] = int(actor_user_id)
    if target_user_id is not None:
        filters.append("target_user_id = :target_user_id")
        params["target_user_id"] = int(target_user_id)
    if target_person_id is not None:
        filters.append("target_person_id = :target_person_id")
        params["target_person_id"] = int(target_person_id)
    if target_employee_id is not None:
        filters.append("target_employee_id = :target_employee_id")
        params["target_employee_id"] = int(target_employee_id)
    if date_from is not None:
        filters.append("happened_at >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        filters.append("happened_at <= :date_to")
        params["date_to"] = date_to

    where_sql = " AND ".join(filters)

    with engine.connect() as conn:
        if not security_audit_log_available(conn):
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        total = int(
            conn.execute(
                text(f"SELECT COUNT(*) FROM public.security_audit_log WHERE {where_sql}"),
                params,
            ).scalar_one()
        )
        rows = conn.execute(
            text(
                f"""
                SELECT
                    sal.audit_id,
                    sal.event_type,
                    sal.happened_at,
                    sal.actor_user_id,
                    sal.target_user_id,
                    sal.target_person_id,
                    sal.target_employee_id,
                    sal.ip_address,
                    sal.user_agent,
                    sal.success,
                    sal.failure_reason,
                    sal.metadata,
                    sal.request_id,
                    actor_u.login AS actor_login,
                    COALESCE(actor_e.full_name, actor_u.login) AS actor_label,
                    target_u.login AS target_user_login,
                    COALESCE(target_ue.full_name, target_u.login) AS target_user_label,
                    target_e.full_name AS target_employee_label,
                    target_p.full_name AS target_person_label
                FROM public.security_audit_log sal
                LEFT JOIN public.users actor_u ON actor_u.user_id = sal.actor_user_id
                LEFT JOIN public.employees actor_e ON actor_e.employee_id = actor_u.employee_id
                LEFT JOIN public.users target_u ON target_u.user_id = sal.target_user_id
                LEFT JOIN public.employees target_ue ON target_ue.employee_id = target_u.employee_id
                LEFT JOIN public.employees target_e ON target_e.employee_id = sal.target_employee_id
                LEFT JOIN public.persons target_p ON target_p.person_id = sal.target_person_id
                WHERE {where_sql}
                ORDER BY sal.happened_at DESC, sal.audit_id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

    items: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        happened_at = item.get("happened_at")
        if isinstance(happened_at, datetime):
            item["happened_at"] = happened_at.isoformat()
        meta = item.get("metadata")
        if isinstance(meta, str):
            item["metadata"] = json.loads(meta)
        items.append(item)

    return {"items": items, "total": total, "limit": limit, "offset": offset}
