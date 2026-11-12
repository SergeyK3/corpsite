"""Linked employee actions report and its HR-only route."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.directory import personnel_reports_routes
from app.main import app
from app.services.personnel_employee_actions_report_service import build_personnel_employee_actions_report
from tests.ppr.conftest import cleanup_person_graph, insert_employee, insert_person, ppr_db_available, require_ppr_schema


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return _Rows(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Engine:
    def __init__(self, rows):
        self.connection = _Connection(rows)

    def connect(self):
        return self.connection


def _row(employee_id, full_name, *, item_id=None, order_id=None, action=None, status=None,
         order_type_code="HIRE", org_unit_id=10):
    return {"employee_id": employee_id, "full_name": full_name,
            "org_unit_id": org_unit_id, "org_unit_name": "Терапия",
            "item_id": item_id, "item_number": item_id, "item_type_code": action,
            "order_id": order_id, "order_number": str(order_id) if order_id else None,
            "order_date": date(2026, 11, 1) if order_id else None, "status": status,
            "order_type_code": order_type_code}


def test_counts_and_details_use_one_unpaginated_item_selection():
    fake = _Engine([
        _row(1, "Без приказов"),
        _row(2, "Иванова", item_id=11, order_id=100, action="HIRE", status="SIGNED"),
        _row(2, "Иванова", item_id=12, order_id=101, action="TRANSFER", status="REGISTERED", order_type_code="COMPOSITE"),
        _row(2, "Иванова", item_id=13, order_id=101, action="SUPPLEMENTARY_PAY", status="REGISTERED", order_type_code="COMPOSITE"),
        _row(3, "Петров", item_id=14, order_id=101, action="TRANSFER", status="REGISTERED", order_type_code="COMPOSITE"),
    ])
    report = build_personnel_employee_actions_report(fake)
    rows = {row["employee_id"]: row for row in report["employees"]}
    assert len(fake.connection.statements) == 1
    sql = fake.connection.statements[0]
    assert "poi.employee_id = ae.employee_id" in sql
    assert "po.status IN ('SIGNED', 'REGISTERED')" in sql
    assert "po.deleted_at IS NULL AND po.archived_at IS NULL" in sql
    assert "ou.unit_id AS org_unit_id" in sql
    assert "COALESCE(current_assignment.org_unit_id, e.org_unit_id)" in sql
    assert "LIMIT" not in sql.split("FROM active_employees ae")[1]
    assert (rows[1]["order_count"], rows[1]["action_count"], rows[1]["orders"]) == (0, 0, [])
    assert (rows[2]["order_count"], rows[2]["action_count"]) == (2, 3)
    assert (rows[2]["ordinary_order_count"], rows[2]["composite_order_count"]) == (1, 1)
    assert {action["code"]: action["count"] for action in rows[2]["actions_by_type"]} == {
        "HIRE": 1, "TRANSFER": 1, "SUPPLEMENTARY_PAY": 1,
    }
    assert next(action for action in rows[2]["actions_by_type"] if action["code"] == "SUPPLEMENTARY_PAY")["label"] == "Доплата"
    assert len(rows[2]["orders"]) == rows[2]["order_count"]
    assert sum(action["count"] for order in rows[2]["orders"] for action in order["actions"]) == rows[2]["action_count"]
    assert (rows[3]["order_count"], rows[3]["action_count"]) == (1, 1)
    assert (rows[3]["ordinary_order_count"], rows[3]["composite_order_count"]) == (0, 1)
    assert rows[3]["orders"][0]["is_composite"] is True


def test_report_route_checks_hr_access_before_reading_data(monkeypatch):
    called = False

    def deny(_user):
        raise HTTPException(status_code=403, detail="Personnel admin access required")

    def service(_engine):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(personnel_reports_routes, "require_personnel_admin_or_403", deny)
    monkeypatch.setattr(personnel_reports_routes, "build_personnel_employee_actions_report", service)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
    try:
        response = TestClient(app).get("/directory/personnel/reports/employee-actions")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403
    assert called is False


@pytest.mark.skipif(not ppr_db_available(), reason="PostgreSQL not available")
def test_synthetic_orders_match_employee_cabinet_counts(seed):
    require_ppr_schema()
    suffix = uuid4().hex[:10]
    user_id = int(seed["initiator_user_id"])
    order_ids = []
    person_ids = []
    employee_ids = []
    with engine.begin() as conn:
        old_employee_id = conn.execute(text("SELECT employee_id FROM public.users WHERE user_id=:id"), {"id": user_id}).scalar_one()
        hr_role = int(conn.execute(text("SELECT role_id FROM public.roles WHERE code='HR_HEAD'")).scalar_one())
        hr_user = int(conn.execute(text("""INSERT INTO public.users(full_name,role_id,is_active,login)
            VALUES(:name,:role,TRUE,:login) RETURNING user_id"""),
            {"name": f"Synthetic HR {suffix}", "role": hr_role, "login": f"synthetic-report-hr-{suffix}"}).scalar_one())
        conn.execute(text("""INSERT INTO public.access_grants
            (access_role_id,target_type,target_id,granted_by_user_id,reason)
            SELECT access_role_id,'USER',:hr_user,:grantor,'Synthetic employee report test'
            FROM public.access_roles WHERE code='HR_ENROLLMENT_MANAGER'"""),
            {"hr_user": hr_user, "grantor": user_id})
        for name in ("Own", "Other", "Without orders"):
            person_id = insert_person(conn, full_name=f"{name} {suffix}")
            person_ids.append(person_id)
            employee_ids.append(insert_employee(conn, full_name=f"{name} {suffix}", person_id=person_id))
        own, other, empty = employee_ids
        conn.execute(text("UPDATE public.users SET employee_id=:employee WHERE user_id=:user"), {"employee": own, "user": user_id})

        def add_order(status, mode, item_specs, label):
            order_id = int(conn.execute(text("""INSERT INTO public.personnel_orders
                (order_number,order_date,order_type_code,status,source_mode,created_by)
                VALUES(:number,:date,:type,:status,:mode,:user) RETURNING order_id"""),
                {"number": f"{label}-{suffix}", "date": date(2026, 11, 1),
                 "type": "COMPOSITE" if len(item_specs) > 1 else "HIRE",
                 "status": status, "mode": mode, "user": user_id}).scalar_one())
            order_ids.append(order_id)
            for index, (employee, action) in enumerate(item_specs, start=1):
                conn.execute(text("""INSERT INTO public.personnel_order_items
                    (order_id,item_number,item_type_code,employee_id,payload)
                    VALUES(:order,:number,:action,:employee,CAST(:payload AS jsonb))"""),
                    {"order": order_id, "number": index, "action": action, "employee": employee,
                     "payload": f'{{"source_name":"Own {suffix}"}}' if employee is None else '{}'})
            return order_id

        imported = add_order("SIGNED", "PAPER", [(own, "HIRE")], "imported")
        composite = add_order("REGISTERED", "MANUAL", [(own, "TRANSFER"), (own, "SUPPLEMENTARY_PAY"), (other, "TRANSFER")], "composite")
        add_order("DRAFT", "MANUAL", [(own, "HIRE")], "draft")
        add_order("REGISTERED", "PAPER", [(None, "HIRE")], "unlinked")
    try:
        report = build_personnel_employee_actions_report(engine)
        rows = {row["employee_id"]: row for row in report["employees"]}
        assert (rows[empty]["order_count"], rows[empty]["action_count"]) == (0, 0)
        assert (rows[own]["order_count"], rows[own]["action_count"]) == (2, 3)
        assert {order["order_id"] for order in rows[own]["orders"]} == {imported, composite}
        assert {action["code"]: action["count"] for action in rows[own]["actions_by_type"]} == {
            "HIRE": 1, "TRANSFER": 1, "SUPPLEMENTARY_PAY": 1,
        }
        assert (rows[other]["order_count"], rows[other]["action_count"]) == (1, 1)
        assert (rows[other]["ordinary_order_count"], rows[other]["composite_order_count"]) == (0, 1)
        assert rows[other]["orders"][0]["is_composite"] is True
        app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id, "role_id": seed["initiator_role_id"]}
        client = TestClient(app)
        response = client.get("/api/ppr/me/orders")
        assert response.status_code == 200
        assert {order["order_id"] for order in response.json()["orders"]} == {imported, composite}
        assert len(response.json()["orders"]) == rows[own]["order_count"]
        assert client.get("/directory/personnel/reports/employee-actions").status_code == 403
        assert client.get(f"/directory/personnel-orders/{composite}").status_code == 403
        app.dependency_overrides[get_current_user] = lambda: {"user_id": hr_user, "role_id": hr_role}
        hr_report = client.get("/directory/personnel/reports/employee-actions")
        assert hr_report.status_code == 200
        assert next(row for row in hr_report.json()["employees"] if row["employee_id"] == own)["order_count"] == 2
        assert client.get(f"/directory/personnel-orders/{composite}").status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id=ANY(:ids)"), {"ids": order_ids})
            conn.execute(text("DELETE FROM public.personnel_orders WHERE order_id=ANY(:ids)"), {"ids": order_ids})
            conn.execute(text("UPDATE public.users SET employee_id=:employee WHERE user_id=:user"),
                         {"employee": old_employee_id, "user": user_id})
            conn.execute(text("DELETE FROM public.access_grants WHERE target_type='USER' AND target_id=:id"), {"id": hr_user})
            conn.execute(text("DELETE FROM public.users WHERE user_id=:id"), {"id": hr_user})
            cleanup_person_graph(conn, person_ids=person_ids, employee_ids=employee_ids)
