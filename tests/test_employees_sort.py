# tests/test_employees_sort.py
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists


def _list_employees(client, user_id: int, **params):
    return client.get(
        "/directory/employees",
        params=params,
        headers=auth_headers(user_id),
    )


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _admin_user_id(conn) -> int:
    row = conn.execute(
        text(
            """
            SELECT user_id
            FROM public.users
            WHERE role_id = :role_id
              AND COALESCE(is_active, TRUE) = TRUE
            LIMIT 1
            """
        ),
        {"role_id": int(SYSTEM_ADMIN_ROLE_ID)},
    ).first()
    if row:
        return int(row[0])
    return 1


def _insert_sort_employee(
    conn,
    *,
    full_name: str,
    org_unit_id: int,
    employment_rate: Optional[float] = None,
    status: Optional[str] = None,
) -> str:
    if not table_exists(conn, "employees"):
        pytest.skip("employees table not available")

    cols = get_columns(conn, "employees")
    values: Dict[str, Any] = {
        "full_name": full_name,
        "org_unit_id": int(org_unit_id),
        "is_active": True,
    }
    if employment_rate is not None and "employment_rate" in cols:
        values["employment_rate"] = float(employment_rate)
    elif "employment_rate" in cols:
        values["employment_rate"] = 1.00
    if status is not None and "status" in cols:
        values["status"] = status
    if "date_from" in cols:
        values["date_from"] = date.today()

    emp_id_col = next((c for c in ("employee_id", "id") if c in cols), None)
    if emp_id_col:
        probe = conn.execute(
            text(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'employees'
                  AND column_name = :col
                LIMIT 1
                """
            ),
            {"col": emp_id_col},
        ).first()
        if probe and str(probe[0]).lower() in {"text", "character varying"}:
            values[emp_id_col] = f"PY{uuid4().hex[:12].upper()}"

    filtered = {k: v for k, v in values.items() if k in cols}
    col_list = ", ".join(filtered.keys())
    bind_list = ", ".join(f":{k}" for k in filtered.keys())
    returning_col = emp_id_col or "full_name"
    row = conn.execute(
        text(
            f"""
            INSERT INTO public.employees ({col_list})
            VALUES ({bind_list})
            RETURNING {returning_col}
            """
        ),
        filtered,
    ).first()
    return str(row[0])


def _cleanup_employees(full_names: List[str]) -> None:
    if not full_names:
        return
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.employees WHERE full_name = ANY(:names)"),
            {"names": full_names},
        )


def _fio_list(payload: dict) -> List[str]:
    return [str(item.get("fio") or "") for item in payload.get("items", [])]


def _rate_list(payload: dict) -> List[float]:
    out: List[float] = []
    for item in payload.get("items", []):
        raw = item.get("rate")
        if raw is None:
            out.append(float("nan"))
        else:
            out.append(float(raw))
    return out


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employees_sort_fio_asc_and_desc(client, seed):
    prefix = f"PytestEmpSortFio_{uuid4().hex[:8]}"
    names = [f"{prefix} Антонов", f"{prefix} Борисов", f"{prefix} Ёжиков"]
    created_names: List[str] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            for name in names:
                _insert_sort_employee(conn, full_name=name, org_unit_id=int(seed["unit_id"]))
                created_names.append(name)

        asc = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            q=prefix,
            limit=50,
            offset=0,
            sort="fio",
            order="asc",
        )
        assert asc.status_code == 200, asc.text
        asc_names = _fio_list(asc.json())
        assert asc_names == sorted(asc_names, key=lambda s: s.casefold())

        desc = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            q=prefix,
            limit=50,
            offset=0,
            sort="fio",
            order="desc",
        )
        assert desc.status_code == 200, desc.text
        desc_names = _fio_list(desc.json())
        assert desc_names == sorted(desc_names, key=lambda s: s.casefold(), reverse=True)
    finally:
        _cleanup_employees(created_names)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employees_sort_rate_and_switch_column(client, seed):
    prefix = f"PytestEmpSortRate_{uuid4().hex[:8]}"
    rows = [
        (f"{prefix} Низкая ставка", 0.25),
        (f"{prefix} Средняя ставка", 1.0),
        (f"{prefix} Высокая ставка", 1.75),
    ]
    created_names: List[str] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            for name, rate in rows:
                _insert_sort_employee(
                    conn,
                    full_name=name,
                    org_unit_id=int(seed["unit_id"]),
                    employment_rate=rate,
                )
                created_names.append(name)

        asc = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            q=prefix,
            limit=50,
            offset=0,
            sort="rate",
            order="asc",
        )
        assert asc.status_code == 200, asc.text
        asc_rates = [r for r in _rate_list(asc.json()) if r == r]
        assert asc_rates == sorted(asc_rates)

        desc = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            q=prefix,
            limit=50,
            offset=0,
            sort="rate",
            order="desc",
        )
        assert desc.status_code == 200, desc.text
        desc_rates = [r for r in _rate_list(desc.json()) if r == r]
        assert desc_rates == sorted(desc_rates, reverse=True)

        by_status = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            q=prefix,
            limit=50,
            offset=0,
            sort="status",
            order="asc",
        )
        assert by_status.status_code == 200, by_status.text
        assert len(by_status.json().get("items", [])) == len(rows)
    finally:
        _cleanup_employees(created_names)


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_list_employees_sort_puts_empty_values_last(client, seed):
    prefix = f"PytestEmpSortEmpty_{uuid4().hex[:8]}"
    names = [f"{prefix} Без ставки", f"{prefix} Со ставкой"]
    created_names: List[str] = []
    admin_user_id: Optional[int] = None

    try:
        with engine.begin() as conn:
            admin_user_id = _admin_user_id(conn)
            cols = get_columns(conn, "employees")
            _insert_sort_employee(
                conn,
                full_name=names[0],
                org_unit_id=int(seed["unit_id"]),
            )
            created_names.append(names[0])
            if "employment_rate" in cols:
                conn.execute(
                    text(
                        """
                        UPDATE public.employees
                        SET employment_rate = NULL
                        WHERE full_name = :full_name
                        """
                    ),
                    {"full_name": names[0]},
                )
            values: Dict[str, Any] = {
                "full_name": names[1],
                "org_unit_id": int(seed["unit_id"]),
                "is_active": True,
            }
            if "employment_rate" in cols:
                values["employment_rate"] = 0.5
            if "date_from" in cols:
                values["date_from"] = date.today()
            insert_returning_id(conn, table="employees", id_col="employee_id", values=values)
            created_names.append(names[1])

        asc = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            q=prefix,
            limit=50,
            offset=0,
            sort="rate",
            order="asc",
        )
        assert asc.status_code == 200, asc.text
        payload = asc.json()
        assert payload["items"][-1]["fio"] == names[0]

        desc = _list_employees(
            client,
            int(admin_user_id),
            status="all",
            q=prefix,
            limit=50,
            offset=0,
            sort="rate",
            order="desc",
        )
        assert desc.status_code == 200, desc.text
        assert desc.json()["items"][-1]["fio"] == names[0]
    finally:
        _cleanup_employees(created_names)
