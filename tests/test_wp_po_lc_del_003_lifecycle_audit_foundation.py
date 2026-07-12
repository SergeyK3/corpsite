# tests/test_wp_po_lc_del_003_lifecycle_audit_foundation.py
"""Tests for WP-PO-LC-DEL-003 lifecycle audit and permission foundation."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.security.admin_permissions import PERMISSION_CODES
from app.services.personnel_order_lifecycle_audit_service import (
    append_personnel_order_lifecycle_audit,
    list_personnel_order_lifecycle_audit,
    personnel_order_lifecycle_audit_available,
    resolve_void_kind,
)
from tests.conftest import auth_headers, get_columns, insert_returning_id, table_exists
from tests.test_wp_po_003_personnel_orders_schema import (
    _delete_personnel_order_audit_rows,
    _insert_returning,
    _pick_employee_id,
    _pick_user_id,
    _require_lc_del_003_schema,
)

pytestmark = pytest.mark.usefixtures("_require_lc_del_003_schema_fixture")


@pytest.fixture(scope="module", autouse=True)
def _require_lc_del_003_schema_fixture():
    _require_lc_del_003_schema()


@pytest.fixture
def privileged_headers(seed, monkeypatch):
    monkeypatch.setenv("DIRECTORY_PRIVILEGED_USER_IDS", str(seed["initiator_user_id"]))
    return auth_headers(seed["initiator_user_id"])


def _cleanup_order(order_id: int) -> None:
    with engine.begin() as conn:
        _delete_personnel_order_audit_rows(conn, order_id)
        conn.execute(
            text("DELETE FROM public.employee_events WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_order_localized_texts WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_order_items WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
        conn.execute(
            text("DELETE FROM public.personnel_orders WHERE order_id = :order_id"),
            {"order_id": order_id},
        )


def _run_void_kind_backfill(conn) -> None:
    conn.execute(
        text(
            """
            UPDATE public.personnel_orders po
            SET void_kind = 'ANNUL'
            WHERE po.status = 'VOIDED'
              AND po.void_kind IS NULL
              AND EXISTS (
                  SELECT 1
                  FROM public.employee_events ev
                  WHERE ev.order_id = po.order_id
              )
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE public.personnel_orders po
            SET void_kind = 'ANNUL'
            WHERE po.status = 'VOIDED'
              AND po.void_kind IS NULL
              AND (
                  po.signed_by_employee_id IS NOT NULL
                  OR NULLIF(btrim(po.signed_by_name), '') IS NOT NULL
                  OR NULLIF(btrim(po.signed_by_position), '') IS NOT NULL
                  OR (
                      po.order_number IS NOT NULL
                      AND po.order_date IS NOT NULL
                      AND po.voided_at IS NOT NULL
                      AND po.voided_at > po.created_at + interval '1 minute'
                  )
              )
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE public.personnel_orders po
            SET void_kind = 'CANCEL'
            WHERE po.status = 'VOIDED'
              AND po.void_kind IS NULL
            """
        )
    )


def _create_position(conn, *, name: str) -> int:
    cols = get_columns(conn, "positions")
    values = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    return insert_returning_id(conn, table="positions", id_col="position_id", values=values)


def _create_test_employee(conn, *, org_unit_id: int, position_id: int, rate: float = 1.0) -> int:
    return insert_returning_id(
        conn,
        table="employees",
        id_col="employee_id",
        values={
            "full_name": f"DEL003A {uuid4().hex[:8]}",
            "org_unit_id": org_unit_id,
            "position_id": position_id,
            "employment_rate": rate,
            "is_active": True,
        },
    )


def _fetch_order_void_state(order_id: int) -> dict[str, object]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT status, void_kind
                FROM public.personnel_orders
                WHERE order_id = :order_id
                """
            ),
            {"order_id": int(order_id)},
        ).mappings().one()
    return {"status": str(row["status"]), "void_kind": row.get("void_kind")}


def _fetch_latest_audit(order_id: int) -> dict[str, object]:
    result = list_personnel_order_lifecycle_audit(order_id, limit=1, offset=0)
    assert result["total"] >= 1
    return result["items"][0]


def _assert_void_consistency(
    *,
    order_id: int,
    expected_kind: str,
    expected_previous_status: str,
) -> None:
    order_state = _fetch_order_void_state(order_id)
    assert order_state["status"] == "VOIDED"
    assert order_state["void_kind"] == expected_kind
    audit = _fetch_latest_audit(order_id)
    assert audit["action"] == expected_kind
    assert audit["new_void_kind"] == expected_kind
    assert audit["previous_status"] == expected_previous_status
    assert audit["new_status"] == "VOIDED"


def test_resolve_void_kind_matrix() -> None:
    assert resolve_void_kind("DRAFT") == "CANCEL"
    assert resolve_void_kind("READY_FOR_SIGNATURE") == "CANCEL"
    assert resolve_void_kind("SIGNED") == "ANNUL"
    assert resolve_void_kind("REGISTERED") == "ANNUL"


def test_backfill_preserves_existing_void_kind() -> None:
    suffix = uuid4().hex[:8]
    order_ids: list[int] = []
    with engine.begin() as conn:
        user_id = _pick_user_id(conn)
        cancel_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number, order_date, order_type_code, status, source_mode,
                void_kind, void_reason, voided_at, voided_by, created_by
            )
            VALUES (
                :order_number, CURRENT_DATE, 'HIRE', 'VOIDED', 'PAPER',
                'CANCEL', 'test', now(), :user_id, :user_id
            )
            RETURNING order_id
            """,
            {"order_number": f"DEL003A-KEEP-C-{suffix}", "user_id": user_id},
        )
        annul_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number, order_date, order_type_code, status, source_mode,
                void_kind, void_reason, voided_at, voided_by, created_by
            )
            VALUES (
                :order_number, CURRENT_DATE, 'HIRE', 'VOIDED', 'PAPER',
                'ANNUL', 'test', now(), :user_id, :user_id
            )
            RETURNING order_id
            """,
            {"order_number": f"DEL003A-KEEP-A-{suffix}", "user_id": user_id},
        )
        order_ids.extend([cancel_id, annul_id])
        _run_void_kind_backfill(conn)
        kinds = {
            int(row[0]): str(row[1])
            for row in conn.execute(
                text(
                    """
                    SELECT order_id, void_kind
                    FROM public.personnel_orders
                    WHERE order_id = ANY(:order_ids)
                    """
                ),
                {"order_ids": order_ids},
            ).all()
        }
    assert kinds[cancel_id] == "CANCEL"
    assert kinds[annul_id] == "ANNUL"
    for order_id in order_ids:
        _cleanup_order(order_id)


def test_backfill_leaves_non_voided_rows_null() -> None:
    suffix = uuid4().hex[:8]
    order_ids: list[int] = []
    with engine.begin() as conn:
        user_id = _pick_user_id(conn)
        draft_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number, order_date, order_type_code, status, source_mode, created_by
            )
            VALUES (:order_number, CURRENT_DATE, 'HIRE', 'DRAFT', 'PAPER', :user_id)
            RETURNING order_id
            """,
            {"order_number": f"DEL003A-DRAFT-{suffix}", "user_id": user_id},
        )
        registered_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number, order_date, order_type_code, status, source_mode, created_by
            )
            VALUES (:order_number, CURRENT_DATE, 'HIRE', 'REGISTERED', 'PAPER', :user_id)
            RETURNING order_id
            """,
            {"order_number": f"DEL003A-REG-{suffix}", "user_id": user_id},
        )
        order_ids.extend([draft_id, registered_id])
        _run_void_kind_backfill(conn)
        kinds = {
            int(row[0]): row[1]
            for row in conn.execute(
                text(
                    """
                    SELECT order_id, void_kind
                    FROM public.personnel_orders
                    WHERE order_id = ANY(:order_ids)
                    """
                ),
                {"order_ids": order_ids},
            ).all()
        }
    assert kinds[draft_id] is None
    assert kinds[registered_id] is None
    for order_id in order_ids:
        _cleanup_order(order_id)


def test_lifecycle_foundation_columns_exist() -> None:
    with engine.begin() as conn:
        cols = get_columns(conn, "personnel_orders")
        for column in (
            "void_kind",
            "archived_at",
            "archived_by",
            "archive_reason_code",
            "archive_reason_text",
        ):
            assert column in cols
        assert table_exists(conn, "personnel_order_lifecycle_audit")
        assert personnel_order_lifecycle_audit_available(conn)


def test_permission_codes_registered() -> None:
    expected = {
        "PERSONNEL_ORDERS_CANCEL_OWN",
        "PERSONNEL_ORDERS_CANCEL_SCOPE",
        "PERSONNEL_ORDERS_VOID",
        "PERSONNEL_ORDERS_VOID_APPLIED",
        "PERSONNEL_ORDERS_ARCHIVE",
        "PERSONNEL_ORDERS_RESTORE",
        "PERSONNEL_ORDERS_AUDIT_READ",
        "PERSONNEL_RECOVERY_ADMIN",
    }
    assert expected.issubset(PERMISSION_CODES)

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT code
                FROM public.access_roles
                WHERE code = ANY(:codes)
                """
            ),
            {"codes": list(expected)},
        ).scalars().all()
    assert set(rows) == expected


def test_void_kind_backfill_heuristic() -> None:
    suffix = uuid4().hex[:8]
    order_ids: list[int] = []

    with engine.begin() as conn:
        user_id = _pick_user_id(conn)
        employee_id = _pick_employee_id(conn)

        annul_with_event = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number, order_date, order_type_code, status, source_mode,
                void_reason, voided_at, voided_by, created_by
            )
            VALUES (
                :order_number, CURRENT_DATE, 'HIRE', 'VOIDED', 'PAPER',
                'test', now(), :user_id, :user_id
            )
            RETURNING order_id
            """,
            {"order_number": f"DEL003-EVT-{suffix}", "user_id": user_id},
        )
        item_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_order_items (
                order_id, item_number, item_type_code, employee_id, effective_date,
                item_status, void_reason
            )
            VALUES (
                :order_id, 1, 'HIRE', :employee_id, CURRENT_DATE, 'VOIDED', 'test'
            )
            RETURNING item_id
            """,
            {"order_id": annul_with_event, "employee_id": employee_id},
        )
        _insert_returning(
            conn,
            """
            INSERT INTO public.employee_events (
                employee_id, event_type, effective_date, order_id, order_item_id, created_by
            )
            VALUES (:employee_id, 'HIRE', CURRENT_DATE, :order_id, :item_id, :user_id)
            RETURNING event_id
            """,
            {
                "employee_id": employee_id,
                "order_id": annul_with_event,
                "item_id": item_id,
                "user_id": user_id,
            },
        )

        annul_registered = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number, order_date, order_type_code, status, source_mode,
                signed_by_name, void_reason, voided_at, voided_by, created_by, created_at
            )
            VALUES (
                :order_number, CURRENT_DATE, 'HIRE', 'VOIDED', 'PAPER',
                'Director', 'test', now() + interval '5 minutes', :user_id, :user_id,
                now() - interval '10 minutes'
            )
            RETURNING order_id
            """,
            {"order_number": f"DEL003-REG-{suffix}", "user_id": user_id},
        )

        cancel_draft = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number, order_date, order_type_code, status, source_mode,
                void_reason, voided_at, voided_by, created_by
            )
            VALUES (
                NULL, NULL, 'HIRE', 'VOIDED', 'PAPER',
                'test', now(), :user_id, :user_id
            )
            RETURNING order_id
            """,
            {"user_id": user_id},
        )
        order_ids.extend([annul_with_event, annul_registered, cancel_draft])

        _run_void_kind_backfill(conn)

        kinds = {
            int(row[0]): str(row[1])
            for row in conn.execute(
                text(
                    """
                    SELECT order_id, void_kind
                    FROM public.personnel_orders
                    WHERE order_id = ANY(:order_ids)
                    """
                ),
                {"order_ids": order_ids},
            ).all()
        }

    assert kinds[annul_with_event] == "ANNUL"
    assert kinds[annul_registered] == "ANNUL"
    assert kinds[cancel_draft] == "CANCEL"

    for order_id in order_ids:
        _cleanup_order(order_id)


def test_append_audit_creates_row() -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        user_id = _pick_user_id(conn)
        order_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number, order_date, order_type_code, status, source_mode, created_by
            )
            VALUES (:order_number, CURRENT_DATE, 'HIRE', 'DRAFT', 'PAPER', :created_by)
            RETURNING order_id
            """,
            {"order_number": f"DEL003-AUD-{suffix}", "created_by": user_id},
        )
        audit_id = append_personnel_order_lifecycle_audit(
            conn,
            order_id=order_id,
            action="CANCEL",
            previous_status="DRAFT",
            new_status="VOIDED",
            previous_void_kind=None,
            new_void_kind="CANCEL",
            actor_user_id=user_id,
            reason_text="test append",
        )
        assert audit_id is not None

    try:
        result = list_personnel_order_lifecycle_audit(order_id, limit=10, offset=0)
        assert result["total"] == 1
        item = result["items"][0]
        assert item["id"] == audit_id
        assert item["action"] == "CANCEL"
        assert item["reason_text"] == "test append"
    finally:
        _cleanup_order(order_id)


def test_void_writes_lifecycle_audit(client, privileged_headers) -> None:
    suffix = uuid4().hex[:8]
    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"DEL003-VOID-{suffix}",
            "order_date": "2026-07-12",
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    try:
        void_resp = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "DEL-003 audit test"},
            headers=privileged_headers,
        )
        assert void_resp.status_code == 200, void_resp.text
        assert void_resp.json()["order"]["status"] == "VOIDED"

        audit_resp = client.get(
            f"/directory/personnel-orders/{order_id}/lifecycle-audit",
            headers=privileged_headers,
        )
        assert audit_resp.status_code == 200, audit_resp.text
        payload = audit_resp.json()
        assert payload["total"] >= 1
        entry = payload["items"][0]
        assert entry["action"] == "CANCEL"
        assert entry["previous_status"] == "DRAFT"
        assert entry["new_status"] == "VOIDED"
        assert entry["new_void_kind"] == "CANCEL"
        assert entry["reason_text"] == "DEL-003 audit test"
        _assert_void_consistency(
            order_id=order_id,
            expected_kind="CANCEL",
            expected_previous_status="DRAFT",
        )
    finally:
        _cleanup_order(order_id)


def test_void_ready_for_signature_persists_cancel_kind(client, privileged_headers) -> None:
    suffix = uuid4().hex[:8]
    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"DEL003A-READY-{suffix}",
            "order_date": "2026-07-12",
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE public.personnel_orders
                    SET status = 'READY_FOR_SIGNATURE'
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            )

        void_resp = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "ready cancel"},
            headers=privileged_headers,
        )
        assert void_resp.status_code == 200, void_resp.text
        _assert_void_consistency(
            order_id=order_id,
            expected_kind="CANCEL",
            expected_previous_status="READY_FOR_SIGNATURE",
        )
    finally:
        _cleanup_order(order_id)


def test_void_signed_persists_annul_kind(client, privileged_headers) -> None:
    suffix = uuid4().hex[:8]
    order_number = f"DEL003A-SIGNED-{suffix}"
    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": order_number,
            "order_date": "2026-07-12",
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]
    with engine.begin() as conn:
        employee_id = _pick_employee_id(conn)
    item_resp = client.post(
        f"/directory/personnel-orders/{order_id}/items",
        json={
            "item_type_code": "HIRE",
            "employee_id": employee_id,
            "effective_date": "2026-07-12",
            "payload": {"employment_rate": 1.0},
        },
        headers=privileged_headers,
    )
    assert item_resp.status_code == 200, item_resp.text
    register_resp = client.post(
        f"/directory/personnel-orders/{order_id}/register",
        json={"target_status": "SIGNED"},
        headers=privileged_headers,
    )
    assert register_resp.status_code == 200, register_resp.text

    try:
        void_resp = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "signed annul"},
            headers=privileged_headers,
        )
        assert void_resp.status_code == 200, void_resp.text
        _assert_void_consistency(
            order_id=order_id,
            expected_kind="ANNUL",
            expected_previous_status="SIGNED",
        )
    finally:
        _cleanup_order(order_id)


def test_void_applied_registered_persists_annul_kind(client, privileged_headers, seed) -> None:
    pos_ids: list[int] = []
    employee_id = 0
    with engine.begin() as conn:
        org_unit_id = int(seed["unit_id"])
        position_id = _create_position(conn, name=f"DEL003A-applied-{uuid4().hex[:8]}")
        pos_ids.append(position_id)
        employee_id = _create_test_employee(
            conn,
            org_unit_id=org_unit_id,
            position_id=position_id,
        )
        row = conn.execute(
            text(
                """
                SELECT org_unit_id, position_id, employment_rate
                FROM public.employees
                WHERE employee_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).mappings().one()

    suffix = uuid4().hex[:8]
    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"DEL003A-APPLIED-{suffix}",
            "order_date": "2026-07-12",
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    try:
        item_resp = client.post(
            f"/directory/personnel-orders/{order_id}/items",
            json={
                "item_type_code": "HIRE",
                "employee_id": employee_id,
                "effective_date": "2026-07-12",
                "payload": {
                    "org_unit_id": int(row["org_unit_id"]),
                    "position_id": int(row["position_id"]),
                    "employment_rate": float(row["employment_rate"] or 1.0),
                },
            },
            headers=privileged_headers,
        )
        assert item_resp.status_code == 200, item_resp.text
        register_resp = client.post(
            f"/directory/personnel-orders/{order_id}/register",
            json={"target_status": "REGISTERED"},
            headers=privileged_headers,
        )
        assert register_resp.status_code == 200, register_resp.text
        apply_resp = client.post(
            f"/directory/personnel-orders/{order_id}/apply",
            headers=privileged_headers,
        )
        assert apply_resp.status_code == 200, apply_resp.text

        void_resp = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "applied annul"},
            headers=privileged_headers,
        )
        assert void_resp.status_code == 200, void_resp.text
        _assert_void_consistency(
            order_id=order_id,
            expected_kind="ANNUL",
            expected_previous_status="REGISTERED",
        )
    finally:
        _cleanup_order(order_id)
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public.employees WHERE employee_id = :employee_id"),
                {"employee_id": employee_id},
            )
            if pos_ids:
                conn.execute(
                    text("DELETE FROM public.positions WHERE position_id = ANY(:ids)"),
                    {"ids": pos_ids},
                )


def test_void_rolls_back_when_audit_insert_fails(client, privileged_headers, monkeypatch) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("audit insert blocked for test")

    monkeypatch.setattr(
        "app.services.personnel_orders_void_service.append_void_order_audit",
        _boom,
    )
    suffix = uuid4().hex[:8]
    create_resp = client.post(
        "/directory/personnel-orders",
        json={
            "order_number": f"DEL003A-RB-{suffix}",
            "order_date": "2026-07-12",
            "order_type_code": "HIRE",
            "source_mode": "PAPER",
        },
        headers=privileged_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    order_id = create_resp.json()["order"]["order_id"]

    try:
        void_resp = client.post(
            f"/directory/personnel-orders/{order_id}/void",
            json={"void_reason": "should rollback"},
            headers=privileged_headers,
        )
        assert void_resp.status_code == 500, void_resp.text
        order_state = _fetch_order_void_state(order_id)
        assert order_state["status"] == "DRAFT"
        assert order_state["void_kind"] is None
        audit = list_personnel_order_lifecycle_audit(order_id, limit=10, offset=0)
        assert audit["total"] == 0
    finally:
        _cleanup_order(order_id)


def test_lifecycle_audit_endpoint_requires_auth(client, seed) -> None:
    suffix = uuid4().hex[:8]
    with engine.begin() as conn:
        user_id = _pick_user_id(conn)
        order_id = _insert_returning(
            conn,
            """
            INSERT INTO public.personnel_orders (
                order_number, order_date, order_type_code, status, source_mode, created_by
            )
            VALUES (:order_number, CURRENT_DATE, 'HIRE', 'DRAFT', 'PAPER', :created_by)
            RETURNING order_id
            """,
            {"order_number": f"DEL003-403-{suffix}", "created_by": user_id},
        )

    try:
        unauth = client.get(f"/directory/personnel-orders/{order_id}/lifecycle-audit")
        assert unauth.status_code == 401

        unprivileged = client.get(
            f"/directory/personnel-orders/{order_id}/lifecycle-audit",
            headers=auth_headers(seed["executor_user_id"]),
        )
        assert unprivileged.status_code == 403
    finally:
        _cleanup_order(order_id)


def test_lifecycle_audit_not_found(client, privileged_headers) -> None:
    resp = client.get(
        "/directory/personnel-orders/999999999/lifecycle-audit",
        headers=privileged_headers,
    )
    assert resp.status_code == 404
