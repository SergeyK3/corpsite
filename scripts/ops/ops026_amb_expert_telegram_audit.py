"""OPS-026 — read-only Telegram ID audit for QM_AMB expert slot."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

# Allow running from repo root:
#   .venv/bin/python scripts/ops/ops026_amb_expert_telegram_audit.py
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.engine import engine  # noqa: E402

QM_AMB_EXPECTED = "7685102887"
FORBIDDEN_DEV_IDS = ("885342581",)

QUERIES: list[tuple[str, str]] = [
    (
        "qm_amb_users",
        """
        SELECT u.user_id, u.login, u.full_name, u.telegram_id, r.code AS role_code, u.is_active
        FROM public.users u
        JOIN public.roles r ON r.role_id = u.role_id
        WHERE lower(u.login) = 'qm_amb@corp.local' OR r.code = 'QM_AMB'
        ORDER BY u.user_id
        """,
    ),
    (
        "telegram_id_owners",
        """
        SELECT u.user_id, u.login, u.full_name, u.telegram_id, r.code AS role_code
        FROM public.users u
        LEFT JOIN public.roles r ON r.role_id = u.role_id
        WHERE trim(u.telegram_id::text) = ANY(:ids)
        ORDER BY u.telegram_id, u.user_id
        """,
    ),
    (
        "duplicate_telegram_id",
        """
        SELECT trim(u.telegram_id::text) AS telegram_id,
               array_agg(u.user_id ORDER BY u.user_id) AS user_ids,
               array_agg(u.login ORDER BY u.user_id) AS logins
        FROM public.users u
        WHERE u.telegram_id IS NOT NULL AND trim(u.telegram_id::text) <> ''
        GROUP BY trim(u.telegram_id::text)
        HAVING COUNT(*) > 1
        """,
    ),
    (
        "contacts_ambulatory",
        """
        SELECT contact_id, person_id, full_name, telegram_numeric_id
        FROM public.contacts
        WHERE COALESCE(is_deleted, false) = false
          AND lower(full_name) LIKE '%акил%'
        ORDER BY contact_id
        """,
    ),
]


def _rows(conn, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = conn.execute(text(sql), params or {})
    return [dict(r) for r in result.mappings().all()]


def main() -> int:
    report: dict[str, Any] = {
        "expected_qm_amb_telegram_id": QM_AMB_EXPECTED,
        "forbidden_dev_ids": list(FORBIDDEN_DEV_IDS),
        "sections": {},
        "findings": [],
    }

    with engine.connect() as conn:
        for name, sql in QUERIES:
            params = None
            if name == "telegram_id_owners":
                params = {"ids": [QM_AMB_EXPECTED, *FORBIDDEN_DEV_IDS]}
            report["sections"][name] = _rows(conn, sql, params)

    qm_amb = report["sections"].get("qm_amb_users") or []
    for row in qm_amb:
        tg = str(row.get("telegram_id") or "").strip()
        if tg in FORBIDDEN_DEV_IDS:
            report["findings"].append(
                {
                    "severity": "HIGH",
                    "message": f"QM_AMB user_id={row.get('user_id')} bound to forbidden dev telegram_id={tg}",
                }
            )
        elif tg and tg != QM_AMB_EXPECTED:
            report["findings"].append(
                {
                    "severity": "MEDIUM",
                    "message": f"QM_AMB user_id={row.get('user_id')} telegram_id={tg} (expected {QM_AMB_EXPECTED})",
                }
            )
        elif not tg:
            report["findings"].append(
                {
                    "severity": "LOW",
                    "message": f"QM_AMB user_id={row.get('user_id')} has no telegram_id",
                }
            )

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 1 if any(f["severity"] == "HIGH" for f in report["findings"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
