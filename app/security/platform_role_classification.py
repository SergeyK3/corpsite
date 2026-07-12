"""OO-SEC-001 — Leadership Workspace Read Policy (fail-closed classifier).

Approved leadership Platform Role codes for ``OPERATIONAL_ORDERS_INTAKE_READ``
ROLE grants. This module does NOT grant permissions at runtime and must not be
used as a permission bypass. Authority remains in ``access_grants`` resolved
via ``list_active_access_role_codes``.
"""
from __future__ import annotations

# Approved allowlist — each code requires explicit policy review before inclusion.
LEADERSHIP_PLATFORM_ROLE_CODES: frozenset[str] = frozenset(
    {
        "DIRECTOR",
        "DEP_MED",
        "DEP_OUTPATIENT_AUDIT",
        "DEP_ADMIN",
        "DEP_STRATEGY",
        "STAT_HEAD",
        "STAT_HEAD_DEPUTY",
        "QM_HEAD",
        "HR_HEAD",
        "ACC_HEAD",
        "ECON_HEAD",
    }
)

OO_SEC_001_GRANT_REASON = "OO-SEC-001: approved leadership workspace read policy"

# Privileged platform roles — OO access via is_privileged, not OO-SEC-001 grants.
_PRIVILEGED_PLATFORM_ROLE_CODES: frozenset[str] = frozenset({"ADMIN", "SYSTEM_ADMIN"})

# Canonical seed / pilot role codes (db/init + pilot scripts) for drift detection tests.
CANONICAL_SEED_PLATFORM_ROLE_CODES: frozenset[str] = frozenset(
    {
        "DIRECTOR",
        "DEP_MED",
        "DEP_OUTPATIENT_AUDIT",
        "DEP_ADMIN",
        "DEP_STRATEGY",
        "STAT_HEAD",
        "STAT_HEAD_DEPUTY",
        "STAT_EROB_INPUT",
        "STAT_EROB_OUTPUT",
        "STAT_EROB_ANALYTICS",
        "QM_HEAD",
        "QM_HOSP",
        "QM_AMB",
        "QM_COMPLAINT_REG",
        "QM_COMPLAINT_PAT",
        "QM_TRAINING_EXPERT",
        "HR_HEAD",
        "ACC_HEAD",
        "ECON_HEAD",
        "ECON_1",
        "ECON_2",
        "ECON_3",
    }
)


def is_approved_leadership_workspace_read_role(role_code: str | None) -> bool:
    """True only for OO-SEC-001 leadership workspace read allowlist codes."""
    code = (role_code or "").strip().upper()
    if not code:
        return False
    return code in LEADERSHIP_PLATFORM_ROLE_CODES


def looks_like_leadership_platform_role(role_code: str | None) -> bool:
    """Diagnostic heuristic — NOT authority for access grants."""
    code = (role_code or "").strip().upper()
    if not code:
        return False
    if code in _PRIVILEGED_PLATFORM_ROLE_CODES:
        return True
    if code == "DIRECTOR":
        return True
    if code.startswith("DEP_"):
        return True
    if code.endswith("_HEAD_DEPUTY"):
        return True
    if code.endswith("_HEAD"):
        return True
    return False


def find_potential_leadership_codes_missing_from_allowlist(
    role_codes: frozenset[str] | set[str],
) -> frozenset[str]:
    """Codes that look managerial but are not in the approved OO read allowlist."""
    return frozenset(
        code
        for code in role_codes
        if looks_like_leadership_platform_role(code)
        and not is_approved_leadership_workspace_read_role(code)
        and code not in _PRIVILEGED_PLATFORM_ROLE_CODES
    )
