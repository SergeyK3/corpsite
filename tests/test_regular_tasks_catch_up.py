# tests/test_regular_tasks_catch_up.py
from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.engine import engine
from app.main import app
from app.services.regular_tasks_service import (
    CatchUpTemplateFilters,
    _load_regular_task_templates,
    build_catch_up_resolved_payload,
    build_catch_up_template_filters,
    resolve_catch_up_run_for_date,
    resolve_catch_up_schedule_type,
    run_regular_tasks_catch_up_tx,
)
from app.services.tasks_service import SYSTEM_ADMIN_ROLE_ID


def test_resolve_past_week_last_wednesday_in_window():
    # Thursday 2026-03-12 -> window [2026-03-05 .. 2026-03-11], last Wed = 2026-03-11
    assert resolve_catch_up_run_for_date("past_week", date(2026, 3, 12)) == date(2026, 3, 11)


def test_resolve_past_week_fallback_before_today():
    # Tuesday 2026-03-10 -> no Wed in [2026-03-03 .. 2026-03-09], fallback Wed = 2026-03-04
    assert resolve_catch_up_run_for_date("past_week", date(2026, 3, 10)) == date(2026, 3, 4)


def test_resolve_past_month_first_day_previous_month():
    assert resolve_catch_up_run_for_date("past_month", date(2026, 3, 15)) == date(2026, 2, 1)


def test_resolve_manual_requires_date():
    with pytest.raises(ValueError):
        resolve_catch_up_run_for_date("manual", date(2026, 3, 1), manual_date=None)
    assert resolve_catch_up_run_for_date(
        "manual",
        date(2026, 3, 1),
        manual_date=date(2026, 2, 20),
    ) == date(2026, 2, 20)


def test_resolve_schedule_type_presets():
    assert resolve_catch_up_schedule_type("past_week", None) == "weekly"
    assert resolve_catch_up_schedule_type("past_month", None) == "monthly"
    assert resolve_catch_up_schedule_type("manual", None) is None
    assert resolve_catch_up_schedule_type("past_week", "monthly") == "monthly"


def test_build_catch_up_resolved_payload_includes_regular_task_id():
    payload = build_catch_up_resolved_payload(
        preset="past_month",
        run_for_date=date(2026, 2, 1),
        schedule_type="monthly",
        regular_task_id=12,
    )
    assert payload["regular_task_id"] == 12
    assert payload["schedule_type"] == "monthly"


def test_build_catch_up_template_filters_carries_regular_task_id():
    filters = build_catch_up_template_filters(
        schedule_type="monthly",
        org_unit_id=44,
        executor_role_id=3,
        regular_task_id=12,
    )
    assert filters.regular_task_id == 12
    assert filters.org_unit_id == 44
    assert filters.executor_role_id == 3


def test_load_regular_task_templates_applies_regular_task_id_sql_filter():
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.all.return_value = []

    _load_regular_task_templates(
        conn,
        template_filters=CatchUpTemplateFilters(
            schedule_type="monthly",
            regular_task_id=12,
        ),
    )

    sql = str(conn.execute.call_args[0][0])
    params = conn.execute.call_args[0][1]
    assert "rt.regular_task_id = :regular_task_id" in sql
    assert "LOWER(TRIM(COALESCE(rt.schedule_type, ''))) = :schedule_type" in sql
    assert params["regular_task_id"] == 12
    assert params["schedule_type"] == "monthly"


def test_catch_up_endpoint_forwards_regular_task_id_ops_009_34(monkeypatch):
    """Regression: Network payload with regular_task_id must reach service and response."""
    captured: dict = {}

    def fake_catch_up_tx(conn, **kwargs):
        captured.update(kwargs)
        resolved = build_catch_up_resolved_payload(
            preset="past_month",
            run_for_date=date(2026, 2, 1),
            schedule_type="monthly",
            regular_task_id=kwargs.get("regular_task_id"),
        )
        stats = {
            "templates_total": 1,
            "templates_due": 1,
            "created": 0,
            "deduped": 0,
            "errors": 0,
            "catch_up": dict(resolved),
        }
        resolved["templates_in_scope"] = 1
        return 99, stats, resolved

    mock_conn = MagicMock()
    mock_tx = MagicMock()
    mock_tx.__enter__.return_value = mock_conn
    mock_tx.__exit__.return_value = False

    monkeypatch.setattr(
        "app.services.regular_tasks_router.engine.begin",
        lambda: mock_tx,
    )
    monkeypatch.setattr(
        "app.services.regular_tasks_router.run_regular_tasks_catch_up_tx",
        fake_catch_up_tx,
    )
    monkeypatch.setattr(
        "app.services.regular_tasks_router._resolve_runner_user",
        lambda **_: {"user_id": 1, "role_id": int(SYSTEM_ADMIN_ROLE_ID)},
    )

    client = TestClient(app)
    response = client.post(
        "/internal/regular-tasks/catch-up",
        json={
            "dry_run": True,
            "preset": "past_month",
            "schedule_type": "monthly",
            "regular_task_id": 12,
        },
        headers={"Authorization": "Bearer pytest-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert captured["regular_task_id"] == 12
    assert body["resolved"]["regular_task_id"] == 12
    assert body["resolved"]["templates_in_scope"] == 1
    assert body["stats"]["templates_total"] == 1
    assert body["stats"]["templates_due"] == 1
    assert body["stats"]["catch_up"]["regular_task_id"] == 12


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _col_exists(conn, table: str, col: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name=:t
                  AND column_name=:c
                LIMIT 1
                """
            ),
            {"t": table, "c": col},
        ).scalar()
    )


def _insert_catch_up_template(
    conn,
    *,
    title: str,
    schedule_type: str,
    schedule_params: dict,
    owner_unit_id: int | None = None,
    executor_role_id: int = 1,
) -> int:
    cols = ["title", "is_active", "schedule_type", "schedule_params", "create_offset_days", "executor_role_id"]
    vals: dict = {
        "title": title,
        "is_active": True,
        "schedule_type": schedule_type,
        "schedule_params": json.dumps(schedule_params, ensure_ascii=False),
        "create_offset_days": 0,
        "executor_role_id": int(executor_role_id),
    }
    if _col_exists(conn, "regular_tasks", "code"):
        cols.append("code")
        slug = "".join(c if c.isalnum() else "_" for c in title).strip("_").lower()[:48]
        vals["code"] = f"pytest_rt_{slug}"
    if _col_exists(conn, "regular_tasks", "assignment_scope"):
        cols.append("assignment_scope")
        vals["assignment_scope"] = "functional"
    if owner_unit_id is not None and _col_exists(conn, "regular_tasks", "owner_unit_id"):
        cols.append("owner_unit_id")
        vals["owner_unit_id"] = int(owner_unit_id)

    values_sql = ", ".join(
        "CAST(:schedule_params AS jsonb)" if c == "schedule_params" else f":{c}" for c in cols
    )
    cols_sql = ", ".join(cols)
    rid = conn.execute(
        text(
            f"""
            INSERT INTO public.regular_tasks ({cols_sql})
            VALUES ({values_sql})
            RETURNING regular_task_id
            """
        ),
        vals,
    ).scalar_one()
    return int(rid)


def _create_unit_with_group(conn, *, name: str, group_id: int) -> int:
    cols = [
        row[0]
        for row in conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'org_units'
                """
            )
        ).fetchall()
    ]
    values: dict = {"name": name}
    insert_cols = ["name"]
    if "code" in cols:
        values["code"] = name
        insert_cols.append("code")
    if "group_id" in cols:
        values["group_id"] = int(group_id)
        insert_cols.append("group_id")
    if "is_active" in cols:
        values["is_active"] = True
        insert_cols.append("is_active")

    cols_sql = ", ".join(insert_cols)
    vals_sql = ", ".join(f":{c}" for c in insert_cols)
    return int(
        conn.execute(
            text(
                f"""
                INSERT INTO public.org_units ({cols_sql})
                VALUES ({vals_sql})
                RETURNING unit_id
                """
            ),
            values,
        ).scalar_one()
    )


def _find_distinct_group_ids(conn, *, limit: int = 2) -> list[int]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT group_id
            FROM public.org_units
            WHERE group_id IS NOT NULL
              AND group_id >= 1
            ORDER BY group_id
            LIMIT :limit
            """
        ),
        {"limit": int(limit)},
    ).mappings().all()
    return [int(r["group_id"]) for r in rows if r.get("group_id") is not None]


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_catch_up_dry_run_scoped_by_org_group_id(seed):
    suffix = date.today().isoformat()
    with engine.begin() as conn:
        group_ids = _find_distinct_group_ids(conn, limit=2)
        if len(group_ids) < 2:
            group_a = 1
            group_b = 3
        else:
            group_a, group_b = group_ids[0], group_ids[1]

        unit_a = _create_unit_with_group(conn, name=f"pytest_rt_catchup_a_{suffix}", group_id=group_a)
        unit_b = _create_unit_with_group(conn, name=f"pytest_rt_catchup_b_{suffix}", group_id=group_b)

        rid_in = _insert_catch_up_template(
            conn,
            title=f"CATCHUP GROUP IN {suffix}",
            schedule_type="weekly",
            schedule_params={"byweekday": [4], "time": "00:00"},
            owner_unit_id=unit_a,
            executor_role_id=seed["executor_role_id"],
        )
        rid_out = _insert_catch_up_template(
            conn,
            title=f"CATCHUP GROUP OUT {suffix}",
            schedule_type="weekly",
            schedule_params={"byweekday": [4], "time": "00:00"},
            owner_unit_id=unit_b,
            executor_role_id=seed["executor_role_id"],
        )

        run_id, stats, resolved = run_regular_tasks_catch_up_tx(
            conn,
            preset="manual",
            dry_run=True,
            run_for_date_manual=date(2026, 3, 5),
            schedule_type="weekly",
            org_group_id=group_a,
        )

        assert resolved["org_group_id"] == group_a
        assert stats["templates_total"] == 1
        assert stats["templates_due"] == 1
        assert stats["created"] == 0

        conn.execute(
            text("DELETE FROM public.regular_tasks WHERE regular_task_id IN (:a, :b)"),
            {"a": rid_in, "b": rid_out},
        )
        conn.execute(text("DELETE FROM public.org_units WHERE unit_id IN (:a, :b)"), {"a": unit_a, "b": unit_b})
        conn.execute(text("DELETE FROM public.regular_task_runs WHERE run_id = :rid"), {"rid": int(run_id)})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_catch_up_dry_run_scoped_by_org_unit(seed):
    suffix = date.today().isoformat()
    with engine.begin() as conn:
        group_ids = _find_distinct_group_ids(conn, limit=1)
        group_id = group_ids[0] if group_ids else 1
        unit_in = _create_unit_with_group(conn, name=f"pytest_rt_catchup_in_{suffix}", group_id=group_id)
        unit_out = _create_unit_with_group(conn, name=f"pytest_rt_catchup_out_{suffix}", group_id=group_id)

        rid_in = _insert_catch_up_template(
            conn,
            title=f"CATCHUP IN {suffix}",
            schedule_type="weekly",
            schedule_params={"byweekday": [4], "time": "00:00"},
            owner_unit_id=unit_in,
            executor_role_id=seed["executor_role_id"],
        )
        rid_out = _insert_catch_up_template(
            conn,
            title=f"CATCHUP OUT {suffix}",
            schedule_type="weekly",
            schedule_params={"byweekday": [4], "time": "00:00"},
            owner_unit_id=unit_out,
            executor_role_id=seed["executor_role_id"],
        )

        run_id, stats, resolved = run_regular_tasks_catch_up_tx(
            conn,
            preset="manual",
            dry_run=True,
            run_for_date_manual=date(2026, 3, 5),
            schedule_type="weekly",
            org_unit_id=unit_in,
        )

        assert resolved["org_unit_id"] == unit_in
        assert stats["templates_total"] == 1
        assert stats["templates_due"] == 1
        assert stats["created"] == 0

        conn.execute(
            text("DELETE FROM public.regular_tasks WHERE regular_task_id IN (:a, :b)"),
            {"a": rid_in, "b": rid_out},
        )
        conn.execute(text("DELETE FROM public.org_units WHERE unit_id IN (:a, :b)"), {"a": unit_in, "b": unit_out})
        conn.execute(text("DELETE FROM public.regular_task_runs WHERE run_id = :rid"), {"rid": int(run_id)})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_catch_up_dry_run_scoped_by_regular_task_id(seed):
    suffix = date.today().isoformat()
    with engine.begin() as conn:
        group_ids = _find_distinct_group_ids(conn, limit=1)
        group_id = group_ids[0] if group_ids else 1
        unit_id = _create_unit_with_group(conn, name=f"pytest_rt_catchup_tpl_{suffix}", group_id=group_id)

        rid_a = _insert_catch_up_template(
            conn,
            title=f"CATCHUP TPL A {suffix}",
            schedule_type="weekly",
            schedule_params={"byweekday": [4], "time": "00:00"},
            owner_unit_id=unit_id,
            executor_role_id=seed["executor_role_id"],
        )
        rid_b = _insert_catch_up_template(
            conn,
            title=f"CATCHUP TPL B {suffix}",
            schedule_type="weekly",
            schedule_params={"byweekday": [4], "time": "00:00"},
            owner_unit_id=unit_id,
            executor_role_id=seed["executor_role_id"],
        )

        run_id, stats, resolved = run_regular_tasks_catch_up_tx(
            conn,
            preset="manual",
            dry_run=True,
            run_for_date_manual=date(2026, 3, 5),
            schedule_type="weekly",
            org_unit_id=unit_id,
            regular_task_id=rid_a,
        )

        assert resolved["regular_task_id"] == rid_a
        assert stats["templates_total"] == 1
        assert stats["templates_due"] == 1
        assert stats["created"] == 0

        conn.execute(
            text("DELETE FROM public.regular_tasks WHERE regular_task_id IN (:a, :b)"),
            {"a": rid_a, "b": rid_b},
        )
        conn.execute(text("DELETE FROM public.org_units WHERE unit_id = :unit_id"), {"unit_id": unit_id})
        conn.execute(text("DELETE FROM public.regular_task_runs WHERE run_id = :rid"), {"rid": int(run_id)})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_catch_up_past_month_monthly_scoped_by_regular_task_id(seed):
    """OPS-009.34: past_month + monthly + regular_task_id scopes to one template."""
    suffix = date.today().isoformat()
    with engine.begin() as conn:
        group_ids = _find_distinct_group_ids(conn, limit=1)
        group_id = group_ids[0] if group_ids else 1
        unit_id = _create_unit_with_group(conn, name=f"pytest_rt_catchup_monthly_{suffix}", group_id=group_id)

        monthly_params = {"day": 1, "time": "00:00"}
        rid_a = _insert_catch_up_template(
            conn,
            title=f"CATCHUP MONTHLY A {suffix}",
            schedule_type="monthly",
            schedule_params=monthly_params,
            owner_unit_id=unit_id,
            executor_role_id=seed["executor_role_id"],
        )
        rid_b = _insert_catch_up_template(
            conn,
            title=f"CATCHUP MONTHLY B {suffix}",
            schedule_type="monthly",
            schedule_params=monthly_params,
            owner_unit_id=unit_id,
            executor_role_id=seed["executor_role_id"],
        )
        rid_c = _insert_catch_up_template(
            conn,
            title=f"CATCHUP MONTHLY C {suffix}",
            schedule_type="monthly",
            schedule_params=monthly_params,
            owner_unit_id=unit_id,
            executor_role_id=seed["executor_role_id"],
        )

        run_id, stats, resolved = run_regular_tasks_catch_up_tx(
            conn,
            preset="past_month",
            dry_run=True,
            schedule_type="monthly",
            regular_task_id=rid_b,
        )

        assert resolved["regular_task_id"] == rid_b
        assert resolved["schedule_type"] == "monthly"
        assert stats["templates_total"] == 1
        assert stats["templates_due"] == 1
        assert stats["created"] == 0
        assert resolved["templates_in_scope"] == 1
        assert stats["catch_up"]["regular_task_id"] == rid_b

        conn.execute(
            text("DELETE FROM public.regular_tasks WHERE regular_task_id IN (:a, :b, :c)"),
            {"a": rid_a, "b": rid_b, "c": rid_c},
        )
        conn.execute(text("DELETE FROM public.org_units WHERE unit_id = :unit_id"), {"unit_id": unit_id})
        conn.execute(text("DELETE FROM public.regular_task_runs WHERE run_id = :rid"), {"rid": int(run_id)})


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_catch_up_dry_run_stores_empty_errors_array():
    with engine.begin() as conn:
        run_id, stats, _resolved = run_regular_tasks_catch_up_tx(
            conn,
            preset="manual",
            dry_run=True,
            run_for_date_manual=date(2026, 3, 5),
            schedule_type="weekly",
            org_unit_id=999999,
        )

        assert stats["errors"] == 0

        errors_json = conn.execute(
            text("SELECT errors FROM public.regular_task_runs WHERE run_id = :rid"),
            {"rid": int(run_id)},
        ).scalar_one()

        conn.execute(text("DELETE FROM public.regular_task_runs WHERE run_id = :rid"), {"rid": int(run_id)})

    assert errors_json == []


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_catch_up_endpoint_requires_admin():
    client = TestClient(app)
    r = client.post(
        "/internal/regular-tasks/catch-up",
        json={"dry_run": True, "preset": "past_week"},
        headers={"X-User-Id": "999999"},
    )
    assert r.status_code in {401, 403, 404}
