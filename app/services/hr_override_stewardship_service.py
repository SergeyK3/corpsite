"""ADR-043 Phase B3 — stewardship rule resolution from hr_override_stewardship_rules."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine


class StewardshipRuleNotFoundError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).first()
    return row is not None


def stewardship_rules_available(conn: Connection) -> bool:
    return _table_exists(conn, "hr_override_stewardship_rules")


def resolve_stewardship_rule(
    conn: Connection,
    *,
    field_path: str,
    scope_type: str,
) -> dict[str, Any]:
    """Return highest-priority active stewardship rule for field_path + scope_type."""
    if not stewardship_rules_available(conn):
        raise StewardshipRuleNotFoundError("hr_override_stewardship_rules table is not available")

    row = conn.execute(
        text(
            """
            SELECT
                rule_id,
                field_path_pattern,
                scope_type,
                owner_domain,
                required_tier,
                requires_evidence,
                requires_second_approval,
                persistence_policy_default,
                priority
            FROM public.hr_override_stewardship_rules
            WHERE active_flag = TRUE
              AND (scope_type IS NULL OR scope_type = :scope_type)
              AND :field_path LIKE field_path_pattern ESCAPE '\\'
            ORDER BY priority ASC, rule_id ASC
            LIMIT 1
            """
        ),
        {"field_path": field_path.strip(), "scope_type": scope_type},
    ).mappings().first()

    if not row:
        raise StewardshipRuleNotFoundError(
            f"no stewardship rule for field_path={field_path!r} scope_type={scope_type!r}"
        )
    return dict(row)


def validate_stewardship_for_override(
    conn: Connection,
    *,
    field_path: str,
    scope_type: str,
    tier: int,
    owner_domain: str,
    evidence_url: Optional[str],
    justification: Optional[str],
    for_status: str,
) -> dict[str, Any]:
    """Validate tier, owner_domain, evidence, and justification against stewardship rule."""
    rule = resolve_stewardship_rule(conn, field_path=field_path, scope_type=scope_type)

    required_tier = int(rule["required_tier"])
    if int(tier) != required_tier:
        raise StewardshipRuleNotFoundError(
            f"tier {tier} does not match required_tier {required_tier} for {field_path}"
        )

    expected_owner = str(rule["owner_domain"])
    if str(owner_domain) != expected_owner:
        raise StewardshipRuleNotFoundError(
            f"owner_domain {owner_domain!r} does not match stewardship rule {expected_owner!r}"
        )

    if bool(rule["requires_evidence"]):
        if not evidence_url or not str(evidence_url).strip():
            raise StewardshipRuleNotFoundError(f"evidence_url is required for field_path={field_path}")

    terminal = frozenset({"expired", "revoked", "superseded", "rejected"})
    if required_tier >= 1 and for_status not in terminal:
        if not justification or len(str(justification).strip()) < 10:
            raise StewardshipRuleNotFoundError(
                f"justification (>=10 chars) is required for tier {required_tier} overrides"
            )

    return rule
