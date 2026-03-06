# FILE: tools/gen_test_tokens.py
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from app.auth import create_access_token
from app.db.engine import engine

ROLE_CODES = [
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
    "HR_HEAD",
    "ACC_HEAD",
    "ECON_HEAD",
    "ECON_1",
    "ECON_2",
    "ECON_3",
    "ADMISSION_HEAD",
]


def main() -> None:
    sql = text(
        """
        SELECT
            u.user_id,
            u.full_name,
            u.login,
            u.role_id,
            r.code AS role_code,
            r.name AS role_name,
            u.unit_id,
            ou.code AS unit_code,
            u.is_active
        FROM public.users u
        JOIN public.roles r
          ON r.role_id = u.role_id
        LEFT JOIN public.org_units ou
          ON ou.unit_id = u.unit_id
        WHERE u.is_active = TRUE
          AND r.code = ANY(:role_codes)
        ORDER BY r.code, u.user_id
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(sql, {"role_codes": ROLE_CODES}).mappings().all()

    items = []
    for r in rows:
        user_id = int(r["user_id"])
        token = create_access_token(user_id)

        items.append(
            {
                "user_id": user_id,
                "full_name": str(r["full_name"]) if r["full_name"] is not None else "",
                "login": str(r["login"]) if r["login"] is not None else "",
                "role_id": int(r["role_id"]) if r["role_id"] is not None else None,
                "role_code": str(r["role_code"]) if r["role_code"] is not None else "",
                "role_name": str(r["role_name"]) if r["role_name"] is not None else "",
                "unit_id": int(r["unit_id"]) if r["unit_id"] is not None else None,
                "unit_code": str(r["unit_code"]) if r["unit_code"] is not None else None,
                "access_token": token,
            }
        )

    out_dir = Path("tmp")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "corpsite_test_tokens.json"
    out_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved: {out_path.resolve()}")
    print(f"Generated tokens: {len(items)}")
    print()

    for x in items:
        print(f'{x["role_code"]:24} {x["login"]:32} user_id={x["user_id"]}')


if __name__ == "__main__":
    main()