#!/usr/bin/env python3
"""Seed controlled HR pilot data for WP-PO-007.

Creates four [PILOT-PO] employees and sample personnel orders in mixed states.
Safe to re-run: uses unique order numbers with timestamp suffix.

Usage:
  python -m scripts.local_demo.wp_po_007_pilot_seed --operator-user-id 8 --reset
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.engine import engine
from app.main import app
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values: Dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_employee(conn, *, full_name: str, org_unit_id: int, position_id: int, rate: float = 1.0) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": full_name,
            "org_unit_id": org_unit_id,
            "position_id": position_id,
            "employment_rate": rate,
            "is_active": True,
        },
    )


def _employee_row(conn, employee_id: int) -> Dict[str, Any]:
    return dict(
        conn.execute(
            text(
                """
                SELECT org_unit_id, position_id, employment_rate
                FROM public.employees
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).mappings().one()
    )


def _cleanup_order(conn, order_id: int) -> None:
    conn.execute(text("DELETE FROM public.employee_events WHERE order_id = :order_id"), {"order_id": order_id})
    conn.execute(
        text("DELETE FROM public.personnel_order_localized_texts WHERE order_id = :order_id"),
        {"order_id": order_id},
    )
    conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id = :order_id"), {"order_id": order_id})
    conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"), {"order_id": order_id})


def _cleanup_pilot(conn) -> None:
    order_ids = [
        int(r[0])
        for r in conn.execute(
            text(
                """
                SELECT order_id
                FROM public.personnel_orders
                WHERE order_number LIKE 'PILOT-2026-%'
                """
            )
        ).all()
    ]
    for order_id in order_ids:
        _cleanup_order(conn, order_id)

    employee_ids = [
        int(r[0])
        for r in conn.execute(
            text(
                """
                SELECT employee_id
                FROM public.employees
                WHERE full_name LIKE '[PILOT-PO]%'
                """
            )
        ).all()
    ]
    if employee_ids:
        conn.execute(
            text("DELETE FROM public.employee_events WHERE employee_id = ANY(:ids)"),
            {"ids": employee_ids},
        )
        conn.execute(
            text("DELETE FROM public.employees WHERE employee_id = ANY(:ids)"),
            {"ids": employee_ids},
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed WP-PO-007 pilot personnel orders data")
    parser.add_argument("--operator-user-id", type=int, default=8, help="HR operator user_id (default: 8 = hr_head)")
    parser.add_argument("--reset", action="store_true", help="Remove previous [PILOT-PO] rows before seeding")
    args = parser.parse_args()

    with engine.connect() as conn:
        if not table_exists(conn, "personnel_orders"):
            print("personnel_orders schema missing — run: alembic upgrade head", file=sys.stderr)
            return 1

    suffix = date.today().isoformat().replace("-", "")
    headers = auth_headers(args.operator_user_id)
    manifest: List[Dict[str, Any]] = []

    from fastapi.testclient import TestClient

    client = TestClient(app)

    with engine.begin() as conn:
        if args.reset:
            _cleanup_pilot(conn)

        org_unit_id = int(
            conn.execute(
                text("SELECT unit_id FROM public.org_units WHERE is_active = TRUE ORDER BY unit_id LIMIT 1")
            ).scalar_one()
        )
        pos_hire = _create_position(conn, name=f"PILOT hire {suffix}")
        pos_transfer = _create_position(conn, name=f"PILOT transfer {suffix}")
        pos_concur = _create_position(conn, name=f"PILOT concurrent {suffix}")

        employees = {
            "hire": _create_employee(
                conn,
                full_name="[PILOT-PO] Иванов Пилот Приём",
                org_unit_id=org_unit_id,
                position_id=pos_hire,
            ),
            "transfer": _create_employee(
                conn,
                full_name="[PILOT-PO] Петров Пилот Перевод",
                org_unit_id=org_unit_id,
                position_id=pos_hire,
            ),
            "termination": _create_employee(
                conn,
                full_name="[PILOT-PO] Сидоров Пилот Увольнение",
                org_unit_id=org_unit_id,
                position_id=pos_hire,
            ),
            "concurrent": _create_employee(
                conn,
                full_name="[PILOT-PO] Ким Пилот Совмещение",
                org_unit_id=org_unit_id,
                position_id=pos_hire,
                rate=1.0,
            ),
        }

    effective = date.today().isoformat()

    def create_order(order_type: str, order_number: str) -> int:
        resp = client.post(
            "/directory/personnel-orders",
            json={
                "order_number": order_number,
                "order_date": effective,
                "order_type_code": order_type,
                "source_mode": "PAPER",
            },
            headers=headers,
        )
        resp.raise_for_status()
        return int(resp.json()["order"]["order_id"])

    def add_item(order_id: int, item_type: str, employee_id: int, payload: Dict[str, Any]) -> int:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": item_type,
                "employee_id": employee_id,
                "effective_date": effective,
                "payload": payload,
            },
            headers=headers,
        )
        resp.raise_for_status()
        return int(resp.json()["items"][-1]["item_id"])

    def register(order_id: int) -> None:
        resp = client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "REGISTERED"},
            headers=headers,
        )
        resp.raise_for_status()

    def apply(order_id: int) -> None:
        resp = client.post(f"/directory/personnel-orders/{order_id}/apply", headers=headers)
        resp.raise_for_status()

    with engine.begin() as conn:
        hire_row = _employee_row(conn, employees["hire"])

    # 1) HIRE — applied (reference success path)
    hire_order_id = create_order("HIRE", f"PILOT-2026-HIRE-{suffix}")
    add_item(
        hire_order_id,
        "HIRE",
        employees["hire"],
        {
            "org_unit_id": int(hire_row["org_unit_id"]),
            "position_id": int(hire_row["position_id"]),
            "employment_rate": float(hire_row["employment_rate"] or 1.0),
        },
    )
    register(hire_order_id)
    apply(hire_order_id)
    manifest.append(
        {
            "scenario": "HIRE",
            "employee_id": employees["hire"],
            "employee_name": "[PILOT-PO] Иванов Пилот Приём",
            "order_id": hire_order_id,
            "order_number": f"PILOT-2026-HIRE-{suffix}",
            "state": "REGISTERED+APPLIED",
        }
    )

    # 2) TRANSFER — applied
    transfer_order_id = create_order("TRANSFER", f"PILOT-2026-TR-{suffix}")
    add_item(
        transfer_order_id,
        "TRANSFER",
        employees["transfer"],
        {"to_position_id": pos_transfer, "includes_concurrent_duty": False},
    )
    register(transfer_order_id)
    apply(transfer_order_id)
    manifest.append(
        {
            "scenario": "TRANSFER",
            "employee_id": employees["transfer"],
            "employee_name": "[PILOT-PO] Петров Пилот Перевод",
            "order_id": transfer_order_id,
            "order_number": f"PILOT-2026-TR-{suffix}",
            "state": "REGISTERED+APPLIED",
        }
    )

    # 3) TERMINATION — registered only (HR applies during pilot walkthrough)
    with engine.begin() as conn:
        term_row = _employee_row(conn, employees["termination"])
    term_order_id = create_order("TERMINATION", f"PILOT-2026-TERM-{suffix}")
    add_item(
        term_order_id,
        "TERMINATION",
        employees["termination"],
        {
            "org_unit_id": int(term_row["org_unit_id"]),
            "position_id": int(term_row["position_id"]),
            "termination_reason": "PILOT_DEMO",
        },
    )
    register(term_order_id)
    manifest.append(
        {
            "scenario": "TERMINATION",
            "employee_id": employees["termination"],
            "employee_name": "[PILOT-PO] Сидоров Пилот Увольнение",
            "order_id": term_order_id,
            "order_number": f"PILOT-2026-TERM-{suffix}",
            "state": "REGISTERED (apply during pilot)",
        }
    )

    # 4) CONCURRENT_DUTY_START — draft (HR registers/applies or cancels during pilot)
    concur_order_id = create_order("CONCURRENT_DUTY_START", f"PILOT-2026-CON-{suffix}")
    add_item(
        concur_order_id,
        "CONCURRENT_DUTY_START",
        employees["concurrent"],
        {
            "concurrent_position_id": pos_concur,
            "concurrent_rate": 0.5,
            "total_rate": 1.5,
        },
    )
    manifest.append(
        {
            "scenario": "CONCURRENT_DUTY_START",
            "employee_id": employees["concurrent"],
            "employee_name": "[PILOT-PO] Ким Пилот Совмещение",
            "order_id": concur_order_id,
            "order_number": f"PILOT-2026-CON-{suffix}",
            "state": "DRAFT (register/apply or void during pilot)",
        }
    )

    print(json.dumps({"pilot_manifest": manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
