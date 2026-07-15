"""PPR runtime configuration (R5 write path, R7 read-switch)."""
from __future__ import annotations

import os

from app.ppr.domain.errors import PprPmfBridgeError, PprReadPathConfigError

PPR_READ_PATH_MODES = frozenset({"legacy", "shadow", "ppr"})


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_production_profile() -> bool:
    profile = (
        os.environ.get("APP_ENV")
        or os.environ.get("ENVIRONMENT")
        or os.environ.get("ENV")
        or ""
    ).strip().lower()
    return profile in {"production", "prod", "live"}


def ppr_pmf_bridge_enabled() -> bool:
    """PMF internal PPR bridge — default OFF until parity proven."""
    return _truthy(os.environ.get("PPR_PMF_BRIDGE_ENABLED", ""))


def assert_ppr_pmf_bridge_activation_allowed() -> None:
    """Prevent accidental production enable without explicit opt-in."""
    if not ppr_pmf_bridge_enabled():
        return
    if _is_production_profile():
        if not _truthy(os.environ.get("PPR_PMF_BRIDGE_ALLOW_PRODUCTION", "")):
            raise PprPmfBridgeError(
                "PPR PMF bridge is enabled in production profile but "
                "PPR_PMF_BRIDGE_ALLOW_PRODUCTION is not set — activation blocked"
            )


def ppr_read_path_mode() -> str:
    """FULL-CARD read-switch mode — default legacy (DG-ReadSwitch R7)."""
    mode = os.environ.get("PPR_READ_PATH_MODE", "legacy").strip().lower()
    if mode not in PPR_READ_PATH_MODES:
        raise PprReadPathConfigError(
            f"Invalid PPR_READ_PATH_MODE={mode!r}; allowed: {sorted(PPR_READ_PATH_MODES)}"
        )
    return mode


def ppr_read_legacy_adapter_enabled() -> bool:
    """Legacy import-card adapter for mode=ppr — default OFF until R9 UI migration."""
    return _truthy(os.environ.get("PPR_READ_LEGACY_ADAPTER_ENABLED", ""))


def assert_ppr_read_path_activation_allowed() -> None:
    """Block shadow/ppr read-switch in production without explicit opt-in."""
    mode = ppr_read_path_mode()
    if mode == "legacy":
        return
    if _is_production_profile():
        if not _truthy(os.environ.get("PPR_READ_PATH_ALLOW_PRODUCTION", "")):
            raise PprReadPathConfigError(
                f"PPR read path mode={mode!r} is not allowed in production profile "
                "without PPR_READ_PATH_ALLOW_PRODUCTION=true"
            )
