"""Rollback-only PostgreSQL integration tests for pojson018 soft deletion."""
from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine as database_engine
from app.services import personnel_order_draft_deletion_service as deletion
from app.services import personnel_order_quality_control_service as quality
from app.services import personnel_order_tombstone_service as tombstone
from app.services import personnel_orders_query_service as orders_query
from app.services.personnel_order_lifecycle_audit_service import append_personnel_order_lifecycle_audit
from app.services.personnel_orders_command_service import PersonnelOrderDeletedError, require_active_personnel_order


class _SameConnectionEngine:
    def __init__(self, conn): self.conn = conn
    @contextmanager
    def begin(self):
        nested = self.conn.begin_nested()
        try:
            yield self.conn
        except Exception:
            nested.rollback(); raise
        else:
            nested.commit()
    @contextmanager
    def connect(self): yield self.conn


@pytest.fixture()
def draft_tx(monkeypatch):
    with database_engine.connect() as conn:
        outer = conn.begin()
        try:
            if conn.execute(text("SELECT to_regclass('public.personnel_order_draft_deletion_audit')")).scalar_one() is None or conn.execute(text("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='personnel_orders' AND column_name='deleted_at'")).first() is None:
                pytest.skip("pojson018 has not been applied to corpsite_test")
            monkeypatch.setattr(deletion, "engine", _SameConnectionEngine(conn))
            monkeypatch.setattr(orders_query, "engine", _SameConnectionEngine(conn))
            monkeypatch.setattr(quality, "engine", _SameConnectionEngine(conn))
            monkeypatch.setattr(tombstone, "engine", _SameConnectionEngine(conn))
            yield conn
        finally:
            outer.rollback()


def _actor(conn) -> int:
    return int(conn.execute(text("SELECT user_id FROM public.users WHERE is_active=TRUE ORDER BY user_id LIMIT 1")).scalar_one())


def _order(conn) -> int:
    suffix = uuid4().hex[:12]
    return int(conn.execute(text("""INSERT INTO public.personnel_orders
      (order_number, order_date, order_type_code, status, source_mode, storage_json, created_by)
      VALUES (:number, CURRENT_DATE, 'HIRE', 'DRAFT', 'DIGITAL', '{}'::jsonb, :actor)
    RETURNING order_id"""), {"number": f"PYTEST-DRAFT-{suffix}", "actor": _actor(conn)}).scalar_one())


def _item(conn, order_id: int) -> int:
    return int(conn.execute(text("""INSERT INTO public.personnel_order_items
      (order_id,item_number,item_type_code,item_status,payload)
    VALUES (:order_id,1,'HIRE','ACTIVE','{}'::jsonb) RETURNING item_id"""), {"order_id": order_id}).scalar_one())


def _employee(conn) -> int:
    value = conn.execute(text("SELECT employee_id FROM public.employees ORDER BY employee_id LIMIT 1")).scalar_one_or_none()
    if value is None:
        pytest.skip("An employee fixture is required")
    return int(value)


def _assert_blocked(conn, order_id: int) -> None:
    actor = _actor(conn)
    assert deletion.preview(order_id)["can_delete"] is False
    with pytest.raises(deletion.DraftDeletionError, match="Blocking"):
        deletion.execute(order_id=order_id, actor_user_id=actor, reason="legal dependency", confirmation_phrase=f"DELETE DRAFT ORDER {order_id}")
    assert conn.execute(text("SELECT deleted_at FROM public.personnel_orders WHERE order_id=:id"), {"id": order_id}).scalar_one() is None


def _template_applications(conn, order_id: int, item_id: int) -> list[dict]:
    version_id = conn.execute(text("SELECT template_version_id FROM public.personnel_order_template_versions ORDER BY template_version_id LIMIT 1")).scalar_one_or_none()
    if version_id is None:
        pytest.skip("A template version is required for the template-application rollback test")
    actor = _actor(conn)
    for sequence in (1, 2):
        conn.execute(text("""INSERT INTO public.personnel_order_template_applications
          (order_id,order_item_id,template_version_id,template_snapshot,rendered_snapshot,previous_editorial_blocks,applied_by_user_id)
          VALUES (:order_id,:item_id,:version_id,CAST(:snapshot AS jsonb),CAST(:rendered AS jsonb),'{}'::jsonb,:actor)"""), {"order_id": order_id, "item_id": item_id, "version_id": version_id, "snapshot": '{"sequence":%s}' % sequence, "rendered": '{"text":"fixture-%s"}' % sequence, "actor": actor})
    return [dict(row) for row in conn.execute(text("SELECT template_application_id,template_snapshot,rendered_snapshot,previous_editorial_blocks FROM public.personnel_order_template_applications WHERE order_id=:id ORDER BY template_application_id"), {"id": order_id}).mappings()]


def test_isolated_draft_preview_is_read_only_then_soft_delete_preserves_audit_and_neighbour(draft_tx):
    target, neighbour, actor = _order(draft_tx), _order(draft_tx), _actor(draft_tx)
    preview = deletion.preview(target)
    assert preview["can_delete"] is True
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": target}).scalar_one() == 1
    result = deletion.execute(order_id=target, actor_user_id=actor, reason="postgres isolated draft", confirmation_phrase=f"DELETE DRAFT ORDER {target}")
    assert result["status"] == "SOFT_DELETED"
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id AND deleted_at IS NOT NULL"), {"id": target}).scalar_one() == 1
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": neighbour}).scalar_one() == 1
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_order_draft_deletion_audit WHERE order_id=:id AND result_code='COMPLETED' AND deletion_mode='SOFT_DELETE'"), {"id": target}).scalar_one() == 1


def test_unknown_fk_blocks_preview_and_delete_without_touching_order_or_audit(draft_tx):
    target, actor = _order(draft_tx), _actor(draft_tx)
    draft_tx.execute(text("CREATE TABLE public.pytest_draft_delete_blocker (id BIGSERIAL PRIMARY KEY, order_id BIGINT NOT NULL REFERENCES public.personnel_orders(order_id))"))
    draft_tx.execute(text("INSERT INTO public.pytest_draft_delete_blocker(order_id) VALUES (:id)"), {"id": target})
    preview = deletion.preview(target)
    assert preview["can_delete"] is False
    assert any(row["table"] == "pytest_draft_delete_blocker" for row in preview["blocking_dependencies"])
    with pytest.raises(deletion.DraftDeletionError, match="Blocking"):
        deletion.execute(order_id=target, actor_user_id=actor, reason="postgres blocker", confirmation_phrase=f"DELETE DRAFT ORDER {target}")
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": target}).scalar_one() == 1
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_order_draft_deletion_audit WHERE order_id=:id"), {"id": target}).scalar_one() == 0


def test_dependency_added_after_preview_is_rechecked_and_blocks(draft_tx):
    target, actor = _order(draft_tx), _actor(draft_tx)
    assert deletion.preview(target)["can_delete"] is True
    draft_tx.execute(text("CREATE TABLE public.pytest_draft_delete_after_preview (id BIGSERIAL PRIMARY KEY, order_id BIGINT NOT NULL REFERENCES public.personnel_orders(order_id))"))
    draft_tx.execute(text("INSERT INTO public.pytest_draft_delete_after_preview(order_id) VALUES (:id)"), {"id": target})
    with pytest.raises(deletion.DraftDeletionError, match="Blocking"):
        deletion.execute(order_id=target, actor_user_id=actor, reason="postgres recheck", confirmation_phrase=f"DELETE DRAFT ORDER {target}")
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": target}).scalar_one() == 1


def test_audit_failure_rolls_back_soft_delete(draft_tx, monkeypatch):
    target, actor = _order(draft_tx), _actor(draft_tx)
    original = draft_tx.execute
    def fail_audit(statement, *args, **kwargs):
        if "personnel_order_draft_deletion_audit" in str(statement):
            raise RuntimeError("forced draft deletion audit failure")
        return original(statement, *args, **kwargs)
    monkeypatch.setattr(draft_tx, "execute", fail_audit)
    with pytest.raises(RuntimeError, match="forced draft deletion audit failure"):
        deletion.execute(order_id=target, actor_user_id=actor, reason="postgres audit rollback", confirmation_phrase=f"DELETE DRAFT ORDER {target}")
    monkeypatch.setattr(draft_tx, "execute", original)
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id AND deleted_at IS NULL"), {"id": target}).scalar_one() == 1


def test_scope_is_fail_closed_for_draft_without_in_scope_employee(draft_tx):
    target = _order(draft_tx)
    with pytest.raises(deletion.DraftDeletionError) as exc_info:
        deletion.preview(target, scope_unit_ids=[-999999])
    assert exc_info.value.code == "DRAFT_ORDER_SCOPE_FORBIDDEN"


def test_template_applications_are_retained_byte_for_byte_and_tombstone_is_read_only(draft_tx):
    target, actor = _order(draft_tx), _actor(draft_tx)
    item_id = _item(draft_tx, target)
    before = _template_applications(draft_tx, target, item_id)
    preview = deletion.preview(target)
    assert preview["can_delete"] is True
    deletion.execute(order_id=target, actor_user_id=actor, reason="retain application audit", confirmation_phrase=f"DELETE DRAFT ORDER {target}")
    order = draft_tx.execute(text("SELECT deleted_at,deleted_by_user_id,deletion_reason FROM public.personnel_orders WHERE order_id=:id"), {"id": target}).mappings().one()
    assert order["deleted_at"] is not None and int(order["deleted_by_user_id"]) == actor and order["deletion_reason"] == "retain application audit"
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_order_items WHERE order_id=:id"), {"id": target}).scalar_one() == 1
    after = [dict(row) for row in draft_tx.execute(text("SELECT template_application_id,template_snapshot,rendered_snapshot,previous_editorial_blocks FROM public.personnel_order_template_applications WHERE order_id=:id ORDER BY template_application_id"), {"id": target}).mappings()]
    assert after == before
    audit = draft_tx.execute(text("SELECT deletion_mode,order_snapshot FROM public.personnel_order_draft_deletion_audit WHERE order_id=:id"), {"id": target}).mappings().one()
    assert audit["deletion_mode"] == "SOFT_DELETE" and len(audit["order_snapshot"]["template_applications"]) == 2
    assert target not in {row["order_id"] for row in orders_query.list_personnel_orders(limit=500)["items"]}
    assert target not in {row["order_id"] for row in quality.list_personnel_order_quality_issues(limit=50)["items"]}
    with pytest.raises(orders_query.PersonnelOrderNotFoundError): orders_query.get_personnel_order(target)
    assert tombstone.get_deleted_personnel_order_tombstone(target)["template_application_count"] == 2


def test_employee_event_blocks_soft_delete(draft_tx):
    target, item_id, actor, employee_id = _order(draft_tx), None, _actor(draft_tx), _employee(draft_tx)
    item_id = _item(draft_tx, target)
    draft_tx.execute(text("UPDATE public.personnel_order_items SET employee_id=:employee WHERE item_id=:item"), {"employee": employee_id, "item": item_id})
    draft_tx.execute(text("""INSERT INTO public.employee_events(employee_id,event_type,effective_date,order_id,order_item_id,created_by)
      VALUES (:employee,'HIRE',CURRENT_DATE,:order_id,:item_id,:actor)"""), {"employee": employee_id, "order_id": target, "item_id": item_id, "actor": actor})
    _assert_blocked(draft_tx, target)


def test_lifecycle_audit_blocks_soft_delete(draft_tx):
    target, actor = _order(draft_tx), _actor(draft_tx)
    append_personnel_order_lifecycle_audit(draft_tx, order_id=target, action="DOCUMENT_REOPENED", previous_status="DRAFT", new_status="DRAFT", previous_void_kind=None, new_void_kind=None, actor_user_id=actor, reason_code="TEST", reason_text="fixture", metadata_json={})
    _assert_blocked(draft_tx, target)


def test_acknowledgement_blocks_soft_delete(draft_tx):
    target, item_id, actor, employee_id = _order(draft_tx), None, _actor(draft_tx), _employee(draft_tx)
    item_id = _item(draft_tx, target)
    draft_tx.execute(text("UPDATE public.personnel_order_items SET employee_id=:employee WHERE item_id=:item"), {"employee": employee_id, "item": item_id})
    draft_tx.execute(text("""INSERT INTO public.personnel_order_acknowledgement_events(order_id,employee_id,event_type,acknowledged_on,created_by_user_id)
      VALUES (:order_id,:employee,'RECORDED',CURRENT_DATE,:actor)"""), {"order_id": target, "employee": employee_id, "actor": actor})
    _assert_blocked(draft_tx, target)


def test_soft_deleted_real_row_is_rejected_by_common_guard_and_employee_search(draft_tx):
    target, actor, employee_id = _order(draft_tx), _actor(draft_tx), _employee(draft_tx)
    item_id = _item(draft_tx, target)
    draft_tx.execute(text("UPDATE public.personnel_order_items SET employee_id=:employee WHERE item_id=:item"), {"employee": employee_id, "item": item_id})
    deletion.execute(order_id=target, actor_user_id=actor, reason="guard and search", confirmation_phrase=f"DELETE DRAFT ORDER {target}")
    with pytest.raises(PersonnelOrderDeletedError) as raised:
        require_active_personnel_order(draft_tx, target, lock=True)
    assert raised.value.code == "PERSONNEL_ORDER_DELETED"
    assert target not in {row["order_id"] for row in orders_query.list_personnel_orders(employee_id=employee_id, limit=500)["items"]}


def test_privileged_physical_delete_removes_order_owned_rows_and_keeps_neighbour(draft_tx):
    target, neighbour, employee_id = _order(draft_tx), _order(draft_tx), _employee(draft_tx)
    item_id = _item(draft_tx, target)
    draft_tx.execute(text("UPDATE public.personnel_order_items SET employee_id=:employee WHERE item_id=:item"), {"employee": employee_id, "item": item_id})
    draft_tx.execute(text("""INSERT INTO public.employee_events(employee_id,event_type,effective_date,order_id,order_item_id,created_by)
      VALUES (:employee,'HIRE',CURRENT_DATE,:order_id,:item_id,:actor)"""), {"employee": employee_id, "order_id": target, "item_id": item_id, "actor": _actor(draft_tx)})
    _template_applications(draft_tx, target, item_id)
    result = deletion.execute_physical_delete(order_id=target)
    assert result == {"status": "PHYSICALLY_DELETED", "order_id": target}
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": target}).scalar_one() == 0
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_order_items WHERE order_id=:id"), {"id": target}).scalar_one() == 0
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_order_template_applications WHERE order_id=:id"), {"id": target}).scalar_one() == 0
    assert draft_tx.execute(text("SELECT count(*) FROM public.employee_events WHERE order_id=:id"), {"id": target}).scalar_one() == 0
    assert draft_tx.execute(text("SELECT count(*) FROM public.personnel_orders WHERE order_id=:id"), {"id": neighbour}).scalar_one() == 1
