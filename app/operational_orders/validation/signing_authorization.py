"""Signing command actor ↔ authority authorization (OO-IMP-005C)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from app.operational_orders.errors import (
    OperationalOrderForbiddenError,
    OperationalOrderSignAuthorityMismatchError,
    OperationalOrderSignOverrideReasonRequiredError,
)
from app.operational_orders.lifecycle_permissions import PERMISSION_SIGN
from app.security.admin_permissions import has_admin_permission
from app.security.directory_scope import is_privileged


@dataclass(frozen=True, slots=True)
class SigningAuthorization:
    """Resolved signing authorization mode for audit and attestation."""

    mode: str
    privileged_override: bool
    override_reason: str | None = None


def _fetch_user_linkage(conn, user_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT u.user_id, u.employee_id, e.position_id, e.org_unit_id, u.full_name
            FROM public.users u
            LEFT JOIN public.employees e ON e.employee_id = u.employee_id
            WHERE u.user_id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": int(user_id)},
    ).mappings().first()
    return dict(row) if row else None


def actor_matches_signing_authority(
    conn,
    *,
    user_id: int,
    authority: dict[str, Any],
) -> bool:
    party_type = str(authority.get("authority_party_type") or "").strip().upper()
    party_ref = str(authority.get("authority_party_reference") or "").strip()
    if not party_type or not party_ref:
        return False

    linkage = _fetch_user_linkage(conn, user_id)
    if linkage is None:
        return False

    if party_type == "PERSON":
        if party_ref == str(user_id):
            return True
        employee_id = linkage.get("employee_id")
        return employee_id is not None and party_ref == str(employee_id)

    if party_type == "POSITION_ROLE":
        position_id = authority.get("authority_position_id") or linkage.get("position_id")
        if position_id is None:
            return False
        return party_ref == str(position_id)

    if party_type == "ORG_UNIT":
        org_unit_id = authority.get("authority_org_unit_id") or linkage.get("org_unit_id")
        if org_unit_id is None:
            return False
        return party_ref == str(org_unit_id)

    return False


def resolve_signing_authorization(
    conn,
    *,
    user: dict[str, Any],
    authority: dict[str, Any],
    override_reason: str | None,
) -> SigningAuthorization:
    user_id = int(user["user_id"])
    reason_text = str(override_reason or "").strip()

    if is_privileged(user):
        if not reason_text:
            raise OperationalOrderSignOverrideReasonRequiredError(
                "Privileged signing override requires override_reason."
            )
        return SigningAuthorization(
            mode="privileged_override",
            privileged_override=True,
            override_reason=reason_text,
        )

    if not has_admin_permission(user_id, PERMISSION_SIGN):
        raise OperationalOrderForbiddenError("Signing permission is required.")

    if not actor_matches_signing_authority(conn, user_id=user_id, authority=authority):
        raise OperationalOrderSignAuthorityMismatchError(
            "Actor does not match assigned signing authority."
        )

    return SigningAuthorization(mode="normal", privileged_override=False)
