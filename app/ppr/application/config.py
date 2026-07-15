"""PPR runtime configuration (R5)."""
from __future__ import annotations

import os

from app.ppr.domain.errors import PprPmfBridgeError


def ppr_pmf_bridge_enabled() -> bool:
    """PMF internal PPR bridge — default OFF until parity proven."""
    return os.environ.get("PPR_PMF_BRIDGE_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _is_production_profile() -> bool:
    profile = (
        os.environ.get("APP_ENV")
        or os.environ.get("ENVIRONMENT")
        or os.environ.get("ENV")
        or ""
    ).strip().lower()
    return profile in {"production", "prod", "live"}


def assert_ppr_pmf_bridge_activation_allowed() -> None:
    """Prevent accidental production enable without explicit opt-in."""
    if not ppr_pmf_bridge_enabled():
        return
    if _is_production_profile():
        allow = os.environ.get("PPR_PMF_BRIDGE_ALLOW_PRODUCTION", "").strip().lower()
        if allow not in {"1", "true", "yes", "on"}:
            raise PprPmfBridgeError(
                "PPR PMF bridge is enabled in production profile but "
                "PPR_PMF_BRIDGE_ALLOW_PRODUCTION is not set — activation blocked"
            )
