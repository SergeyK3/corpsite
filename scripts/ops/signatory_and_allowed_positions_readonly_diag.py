#!/usr/bin/env python3
"""Read-only diagnostics for personnel-order signatory and org-unit allowed positions.

Usage:
  PYTHONPATH=. python scripts/ops/signatory_and_allowed_positions_readonly_diag.py
  PYTHONPATH=. python scripts/ops/signatory_and_allowed_positions_readonly_diag.py --include-personal-data

SELECT-only. No INSERT/UPDATE/DELETE. By default outputs IDs/counts only (no FIO).
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Any, Dict, List

from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_order_signatory_resolver import resolve_default_personnel_order_signatory

_FIO_RE = re.compile(r"[\w\u0400-\u04FF.-]+", re.UNICODE)


def _mask_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return re.sub(_FIO_RE, "[redacted]", raw)


def _rows(conn, sql: str, **params: Any) -> List[Dict[str, Any]]:
    return [dict(row) for row in conn.execute(text(sql), params).mappings().all()]


def _sanitize_director_users(rows: List[Dict[str, Any]], include_personal: bool) -> List[Dict[str, Any]]:
    sanitized: List[Dict[str, Any]] = []
    for row in rows:
        item = {
            "user_id": row.get("user_id"),
            "employee_id": row.get("employee_id"),
            "role_code": row.get("role_code"),
            "matched_employee_id": row.get("matched_employee_id"),
            "has_matched_employee": row.get("matched_employee_id") is not None,
        }
        if include_personal:
            item["full_name"] = row.get("full_name")
            item["matched_employee_name"] = row.get("matched_employee_name")
            item["matched_position_name"] = row.get("matched_position_name")
        sanitized.append(item)
    return sanitized


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only signatory / allowed-positions diagnostics")
    parser.add_argument(
        "--include-personal-data",
        action="store_true",
        help="Include full names in output (default: IDs and counts only)",
    )
    args = parser.parse_args()
    include_personal = bool(args.include_personal_data)

    report: Dict[str, Any] = {"include_personal_data": include_personal}

    with engine.begin() as conn:
        report["migration_head"] = conn.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).scalar_one_or_none()

        report["users_employee_id_column"] = bool(
            conn.execute(
                text(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'users'
                      AND column_name = 'employee_id'
                    LIMIT 1
                    """
                )
            ).first()
        )

        director_users = _rows(
            conn,
            """
            SELECT u.user_id, u.employee_id, r.code AS role_code
            FROM public.users u
            JOIN public.roles r ON r.role_id = u.role_id
            WHERE UPPER(BTRIM(r.code)) = 'DIRECTOR'
              AND COALESCE(u.is_active, TRUE) = TRUE
            ORDER BY u.user_id
            """,
        )
        report["director_platform_role_user_count"] = len(director_users)
        report["director_platform_role_users"] = director_users

        report["director_position_fallback_employee_count"] = conn.execute(
            text(
                """
                SELECT COUNT(*)::int
                FROM public.employees e
                JOIN public.positions p ON p.position_id = e.position_id
                WHERE COALESCE(e.is_active, TRUE) = TRUE
                  AND LOWER(BTRIM(p.name)) = 'директор'
                """
            )
        ).scalar_one()

        resolution = resolve_default_personnel_order_signatory(conn)
        report["resolver_result"] = {
            "employee_id": resolution.employee_id,
            "signed_by_name": resolution.signed_by_name if include_personal else _mask_name(resolution.signed_by_name),
            "signed_by_position": resolution.signed_by_position,
            "warning": resolution.warning,
            "source": resolution.source,
            "resolved": resolution.resolved,
        }
        report["resolver_note"] = (
            "resolved=true requires verified complete signatory; "
            "name match alone is never sufficient for safety."
        )

        report["hr_org_units"] = _rows(
            conn,
            """
            SELECT unit_id, code, name
            FROM public.org_units
            WHERE code = 'HR' OR unit_id = 74
            ORDER BY unit_id
            """,
        )
        if not include_personal:
            for row in report["hr_org_units"]:
                row["name"] = _mask_name(row.get("name"))

        report["hr_allowed_position_count"] = conn.execute(
            text(
                """
                SELECT COUNT(*)::int
                FROM public.org_unit_allowed_positions ouap
                JOIN public.org_units ou ON ou.unit_id = ouap.org_unit_id
                WHERE (ou.code = 'HR' OR ouap.org_unit_id = 74)
                  AND COALESCE(ouap.is_active, TRUE) = TRUE
                """
            )
        ).scalar_one()

        if include_personal:
            report["hr_allowed_positions"] = _rows(
                conn,
                """
                SELECT ouap.org_unit_id, ou.code, p.position_id, p.name AS position_name,
                       ouap.sort_order
                FROM public.org_unit_allowed_positions ouap
                JOIN public.positions p ON p.position_id = ouap.position_id
                JOIN public.org_units ou ON ou.unit_id = ouap.org_unit_id
                WHERE ou.code = 'HR' OR ouap.org_unit_id = 74
                ORDER BY ouap.org_unit_id, ouap.sort_order, p.name
                """,
            )

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
