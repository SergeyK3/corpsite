"""ADR-042 Phase B5 — admin password reset design stub (not fully implemented)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AdminPasswordResetPlan:
    """
    Future admin-initiated temporary password issuance.

    TODO(C1/C2): implement when admin UI and user self-service password change exist.
    """

    user_id: int
    actor_user_id: int
    temp_password_expires_at: datetime
    must_change_password: bool = True
    increment_token_version: bool = True
    audit_event_type: str = "TEMP_PASSWORD_ISSUED"


def issue_temporary_password(
    *,
    user_id: int,
    actor_user_id: int,
    temp_password_ttl_hours: int = 24,
) -> Dict[str, Any]:
    """
    Design stub for future admin password reset.

    Planned behavior (NOT implemented in B5):
    1. Generate cryptographically secure temporary password.
    2. Store ONLY password_hash via app.auth.hash_password().
    3. Set temp_password_expires_at, must_change_password=true.
    4. Increment users.token_version.
    5. Write TEMP_PASSWORD_ISSUED to security_audit_log (no plaintext in metadata).
    6. Return delivery envelope WITHOUT echoing current or previous password.

    Raises:
        NotImplementedError: until C1/C2 hashing + delivery flow is approved.
    """
    _ = AdminPasswordResetPlan(
        user_id=int(user_id),
        actor_user_id=int(actor_user_id),
        temp_password_expires_at=datetime.now(timezone.utc) + timedelta(hours=temp_password_ttl_hours),
    )
    raise NotImplementedError(
        "Admin password reset is not implemented in Phase B5. "
        "See docs/adr/ADR-042-phase-b5-auth-policy.md and TODO(C1/C2)."
    )
