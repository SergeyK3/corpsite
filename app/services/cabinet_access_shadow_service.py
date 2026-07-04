"""ADR-051 Phase 2.4 — shadow-mode comparison for Cabinet Access Resolver.

Runs alongside ``access_resolver_service.resolve_effective_access`` when
``CABINET_ACCESS_SHADOW_MODE`` is enabled. Legacy grant resolution remains
the sole source of truth; this module only emits diagnostics.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.engine import Connection

from app.config import cabinet_access_shadow_mode_enabled
from app.services.cabinet_access_resolver_service import resolve_effective_permissions

logger = logging.getLogger(__name__)


def _legacy_permission_codes(legacy_result: Dict[str, Any]) -> Set[str]:
    codes: Set[str] = set()
    effective = legacy_result.get("effective_role_code")
    if effective and str(effective) != "IMPLICIT_NONE":
        codes.add(str(effective))
    for grant in legacy_result.get("matched_grants") or []:
        code = grant.get("access_role_code")
        if code:
            codes.add(str(code))
    return codes


def _cabinet_permission_codes(cabinet_result: Dict[str, Any]) -> Set[str]:
    codes: Set[str] = set()
    for item in cabinet_result.get("effective_permissions") or []:
        code = item.get("permission_code")
        if code:
            codes.add(str(code))
    return codes


def compare_legacy_and_cabinet_access(
    *,
    legacy_result: Dict[str, Any],
    cabinet_result: Dict[str, Any],
    user_id: int,
    employee_id: Optional[int],
    org_unit_id: Optional[int],
    catalog_position_id: Optional[int],
) -> Dict[str, Any]:
    legacy_codes = _legacy_permission_codes(legacy_result)
    cabinet_codes = _cabinet_permission_codes(cabinet_result)

    if not cabinet_result.get("resolved"):
        outcome = "cabinet_unresolved"
        mismatch_type = str(cabinet_result.get("reason") or "cabinet_unresolved")
    elif legacy_codes == cabinet_codes:
        outcome = "match"
        mismatch_type = None
    elif not cabinet_codes:
        template = cabinet_result.get("permission_template") or {}
        if (
            cabinet_result.get("resolved")
            and template
            and not template.get("access_role_id")
            and not template.get("role_id")
        ):
            outcome = "mismatch"
            mismatch_type = "permission_template_unmapped"
        elif not legacy_codes:
            outcome = "neutral"
            mismatch_type = "both_empty"
        else:
            outcome = "mismatch"
            mismatch_type = "permission_code_set_mismatch"
    else:
        outcome = "mismatch"
        mismatch_type = "permission_code_set_mismatch"
        template = cabinet_result.get("permission_template") or {}
        if (
            template.get("role_id")
            and not template.get("access_role_id")
            and legacy_codes != cabinet_codes
        ):
            mismatch_type = "namespace_mismatch"

    return {
        "outcome": outcome,
        "mismatch_type": mismatch_type,
        "user_id": int(user_id),
        "employee_id": int(employee_id) if employee_id is not None else None,
        "org_unit_id": int(org_unit_id) if org_unit_id is not None else None,
        "catalog_position_id": int(catalog_position_id) if catalog_position_id is not None else None,
        "legacy_permission_count": len(legacy_codes),
        "cabinet_permission_count": len(cabinet_codes),
        "legacy_permission_codes": sorted(legacy_codes),
        "cabinet_permission_codes": sorted(cabinet_codes),
        "cabinet_reason": cabinet_result.get("reason"),
    }


def log_cabinet_access_shadow_result(diagnostic: Dict[str, Any]) -> None:
    logger.info(
        "cabinet_access_shadow outcome=%s mismatch_type=%s user_id=%s employee_id=%s "
        "org_unit_id=%s catalog_position_id=%s legacy_count=%s cabinet_count=%s "
        "legacy_codes=%s cabinet_codes=%s cabinet_reason=%s",
        diagnostic.get("outcome"),
        diagnostic.get("mismatch_type"),
        diagnostic.get("user_id"),
        diagnostic.get("employee_id"),
        diagnostic.get("org_unit_id"),
        diagnostic.get("catalog_position_id"),
        diagnostic.get("legacy_permission_count"),
        diagnostic.get("cabinet_permission_count"),
        diagnostic.get("legacy_permission_codes"),
        diagnostic.get("cabinet_permission_codes"),
        diagnostic.get("cabinet_reason"),
    )


def _empty_cabinet_result(*, reason: str) -> Dict[str, Any]:
    return {
        "resolved": False,
        "employee_id": None,
        "org_unit_id": None,
        "catalog_position_id": None,
        "org_unique_position": None,
        "position_cabinet": None,
        "permission_template": None,
        "effective_permissions": [],
        "reason": reason,
    }


def maybe_run_cabinet_access_shadow(
    *,
    user_id: int,
    legacy_result: Dict[str, Any],
    conn: Optional[Connection] = None,
) -> None:
    """Invoke cabinet resolver in parallel for diagnostics when shadow mode is enabled."""
    if not cabinet_access_shadow_mode_enabled():
        return

    try:
        employee_id = legacy_result.get("employee_id")
        if employee_id is not None:
            employee_id = int(employee_id)
            cabinet_result = resolve_effective_permissions(
                employee_id=employee_id,
                conn=conn,
            )
            org_unit_id = cabinet_result.get("org_unit_id")
            catalog_position_id = cabinet_result.get("catalog_position_id")
        else:
            cabinet_result = _empty_cabinet_result(reason="employee_not_linked")
            org_unit_id = None
            catalog_position_id = None

        diagnostic = compare_legacy_and_cabinet_access(
            legacy_result=legacy_result,
            cabinet_result=cabinet_result,
            user_id=int(user_id),
            employee_id=employee_id,
            org_unit_id=int(org_unit_id) if org_unit_id is not None else None,
            catalog_position_id=int(catalog_position_id) if catalog_position_id is not None else None,
        )
        log_cabinet_access_shadow_result(diagnostic)
    except Exception:
        logger.exception(
            "cabinet_access_shadow_failed user_id=%s employee_id=%s",
            user_id,
            legacy_result.get("employee_id"),
        )
