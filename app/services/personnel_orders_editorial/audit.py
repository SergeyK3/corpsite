"""Editorial audit helpers (WP-PO-EDIT-002).

Uses a separate connection so audit CHECK failures never abort the caller's
editorial transaction. Never log full prose text in metadata.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.engine import Connection

from app.services.security_audit_service import write_security_event


def write_editorial_audit(
    *,
    event_type: str,
    actor_user_id: Optional[int],
    metadata: Dict[str, Any],
    success: bool = True,
    conn: Optional[Connection] = None,
) -> None:
    # Use a separate connection so audit CHECK failures never abort the
    # caller's editorial transaction.
    try:
        write_security_event(
            event_type=event_type,
            actor_user_id=actor_user_id,
            success=success,
            metadata=metadata,
            conn=None,
        )
    except Exception:
        return
