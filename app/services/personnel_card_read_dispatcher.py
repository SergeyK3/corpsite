"""Legacy import-card read-switch dispatcher (R7 — FULL-CARD mode)."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.engine import Connection

from app.ppr.application.config import (
    assert_ppr_read_path_activation_allowed,
    ppr_read_legacy_adapter_enabled,
    ppr_read_path_mode,
)
from app.ppr.application.shadow_comparator import (
    SHADOW_RESULT_PPR_ERROR,
    compare_legacy_import_card_to_ppr,
    log_shadow_comparison,
)
from app.ppr.domain.errors import PprReadLegacyAdapterError
from app.ppr.read.models import PprCompositeReadModel
from app.ppr.read.query_service import PprQueryApplicationService
from app.services.hr_import_employee_card_service import get_employee_import_card

logger = logging.getLogger("app.ppr.read_switch")


class PersonnelCardReadDispatcher:
    """Dispatches legacy import-card reads through legacy/shadow/ppr FULL-CARD switch."""

    def __init__(
        self,
        *,
        query_service: PprQueryApplicationService | None = None,
    ) -> None:
        self._query_service = query_service or PprQueryApplicationService()

    def load_import_card(
        self,
        conn: Connection,
        employee_id: int,
        *,
        user_ctx: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        mode = ppr_read_path_mode()
        assert_ppr_read_path_activation_allowed()

        if mode == "legacy":
            return get_employee_import_card(conn, employee_id)

        if mode == "shadow":
            legacy_result = get_employee_import_card(conn, employee_id)
            self._run_shadow_compare(
                employee_id=employee_id,
                legacy_result=legacy_result,
                correlation_id=correlation_id,
            )
            return legacy_result

        if mode == "ppr":
            if not ppr_read_legacy_adapter_enabled():
                raise PprReadLegacyAdapterError(
                    "PPR read path mode=ppr is blocked for legacy import-card endpoint "
                    "until legacy adapter parity is complete (PPR_READ_LEGACY_ADAPTER_ENABLED)"
                )
            composite = self._query_service.load_by_employee_id(employee_id)
            return _ppr_to_legacy_import_card_adapter(composite, employee_id)

        raise PprReadLegacyAdapterError(f"Unsupported PPR read path mode: {mode!r}")

    def _run_shadow_compare(
        self,
        *,
        employee_id: int,
        legacy_result: dict[str, Any],
        correlation_id: str | None,
    ) -> None:
        try:
            ppr_result = self._query_service.load_by_employee_id(employee_id)
            comparison = compare_legacy_import_card_to_ppr(legacy_result, ppr_result)
            log_shadow_comparison(
                employee_id=employee_id,
                comparison=comparison,
                read_mode="shadow",
                correlation_id=correlation_id,
            )
        except Exception as exc:
            logger.warning(
                "ppr_shadow_compare employee_id=%s result=%s error_type=%s read_mode=shadow correlation_id=%s",
                employee_id,
                SHADOW_RESULT_PPR_ERROR,
                type(exc).__name__,
                correlation_id or "-",
            )


def _ppr_to_legacy_import_card_adapter(composite: PprCompositeReadModel, employee_id: int) -> dict[str, Any]:
    """Minimal transitional adapter — not full legacy parity (blocked by default)."""
    warnings = [
        "PPR_READ_LEGACY_ADAPTER: partial parity only — import staging fields unavailable",
        f"materialized={composite.materialized}",
    ]
    profile_basic = {
        "full_name": composite.general.full_name,
        "birth_date": composite.general.birth_date.isoformat() if composite.general.birth_date else None,
        "iin": composite.general.iin,
    }
    return {
        "employee_id": employee_id,
        "full_name": composite.general.full_name,
        "profile": {
            "basic": profile_basic,
            "education": [
                {
                    "institution_name": record.institution_name,
                    "specialty": record.specialty,
                }
                for record in composite.education.active
            ],
            "training": [
                {
                    "title": record.title,
                    "organization_name": record.organization_name,
                }
                for record in composite.training.active
            ],
        },
        "profile_status": "ppr_adapter",
        "review_status": "ppr_adapter",
        "has_override": False,
        "ppr_read_adapter": True,
        "resolved_person_id": composite.person_id,
        "materialized": composite.materialized,
        "lifecycle_state": composite.lifecycle_state,
        "adapter_warnings": warnings,
    }
