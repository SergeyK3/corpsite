"""Transactional scenarios against the explicitly selected training database."""
from datetime import date
from decimal import Decimal
from uuid import uuid4
from contextlib import nullcontext
from types import SimpleNamespace
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.db.engine import engine
from app.directory.electronic_hire_routes import _resolver_id
from app.personnel_applications.application import electronic_hire_service as hire
from app.personnel_applications.application.hire_order_draft_service import create_hire_order_draft_for_application
from app.personnel_applications.application.position_reconciliation_service import (
    request_position_review, resolve_position_review, position_review_history,
)
from app.services import personnel_orders_command_service as commands
from app.services.personnel_orders_apply_service import apply_personnel_order_in_conn
from tests.personnel_applications.test_electronic_hire_postgres import _setup, _complete_card


@pytest.mark.parametrize("mode", ["existing", "link", "new"])
def test_position_reconciliation_modes_keep_source_and_draft_edits(mode):
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            result, actor, unit, _, _ = _setup(conn)
            source = f"Учебная несопоставленная {uuid4().hex[:12]}"
            source_form = f"учебную несопоставленную {source.rsplit(' ', 1)[-1]}"
            hire.update_conditions(conn, result.application_id, org_unit_id=unit,
                position_id=None, manual_position_name=source, manual_position_document_ru=source_form,
                employment_rate=Decimal("0.75"), planned_start_date=date(2026, 12, 1))
            _complete_card(conn, result.person_id)
            draft = create_hire_order_draft_for_application(conn, application_id=result.application_id,
                                                            created_by_user_id=actor)
            item = conn.execute(text("SELECT item_id,payload FROM public.personnel_order_items WHERE order_id=:id"),
                                {"id": draft.personnel_order_id}).mappings().one()
            payload = dict(item["payload"])
            payload["other_manual_edit"] = "keep me"
            conn.execute(text("UPDATE public.personnel_order_items SET payload=CAST(:payload AS jsonb) WHERE item_id=:id"),
                         {"payload": json.dumps(payload, ensure_ascii=False), "id": item["item_id"]})
            before_print = hire.render_application(conn, result.application_id)
            with pytest.raises(hire.ElectronicHireError) as gate:
                hire.require_current_approval(conn, draft.personnel_order_id)
            assert gate.value.code == "POSITION_RECONCILIATION_REQUIRED"
            with pytest.raises(HTTPException) as forbidden:
                _resolver_id({"user_id": actor, "role_id": -1})
            assert forbidden.value.status_code == 403
            request = request_position_review(conn, application_id=result.application_id,
                                              actor_user_id=actor, explanation="Нет в списке отделения")
            repeated = request_position_review(conn, application_id=result.application_id,
                                               actor_user_id=actor, explanation="Повтор")
            assert request["request_id"] == repeated["request_id"]
            candidate_id = None
            new_position = None
            if mode in {"existing", "link"}:
                candidate_id = int(conn.execute(text("""
                    INSERT INTO public.positions(name,category,name_kk,document_nominative_ru,
                        document_possessive_kk,translation_status,document_form_status)
                    VALUES (:name,'other',:kk,:ru_form,:kk_form,'confirmed','confirmed') RETURNING position_id
                """), {"name": f"Учебный кандидат {uuid4().hex[:10]}",
                       "kk": "Оқу маманы", "ru_form": "учебного кандидата",
                       "kk_form": "оқу маманының"}).scalar_one())
                if mode == "existing":
                    conn.execute(text("""
                        INSERT INTO public.org_unit_allowed_positions(org_unit_id,position_id,is_active)
                        VALUES (:unit,:position,TRUE)
                    """), {"unit": unit, "position": candidate_id})
            else:
                new_position = {"name": f"Учебная новая {uuid4().hex[:10]}", "category": "other",
                                "name_kk": "Жаңа оқу маманы", "document_nominative_ru": "учебной новой должности",
                                "document_possessive_kk": "жаңа оқу маманының"}
                with pytest.raises(hire.ElectronicHireError) as missing_forms:
                    resolve_position_review(conn, request_id=int(request["request_id"]),
                        actor_user_id=actor, mode="new", position_id=None,
                        new_position={**new_position, "name_kk": ""})
                assert missing_forms.value.code == "POSITION_FIELDS_REQUIRED"
                existing_name = conn.execute(text("SELECT name FROM public.positions ORDER BY position_id LIMIT 1")).scalar_one()
                with pytest.raises(hire.ElectronicHireError) as duplicate_name:
                    resolve_position_review(conn, request_id=int(request["request_id"]),
                        actor_user_id=actor, mode="new", position_id=None,
                        new_position={**new_position, "name": existing_name})
                assert duplicate_name.value.code == "POSITION_DUPLICATE"
            decision = resolve_position_review(conn, request_id=int(request["request_id"]),
                actor_user_id=actor, mode=mode, position_id=candidate_id,
                new_position=new_position, decision_note="Проверено")
            position_id = int(decision["resolved_position_id"])
            reopened = hire.load_electronic_hire(conn, result.application_id)
            assert reopened["position_resolution"] == "matched_manual"
            assert reopened["manual_position_name"] == source
            assert reopened["intended_position_id"] == position_id
            assert hire.render_application(conn, result.application_id) == before_print
            final_payload = conn.execute(text("SELECT payload FROM public.personnel_order_items WHERE item_id=:id"),
                                         {"id": item["item_id"]}).scalar_one()
            assert final_payload["position_id"] == position_id
            assert final_payload["manual_position_name"] == source
            assert final_payload["other_manual_edit"] == "keep me"
            assert decision["changes"]["after_order_text"]["ru"] != decision["changes"]["before_order_text"]["ru"]
            assert decision["changes"]["after_order_text"]["kk"] != decision["changes"]["before_order_text"]["kk"]
            assert len(position_review_history(conn, int(request["request_id"]))) == 2
            with pytest.raises(hire.ElectronicHireError) as stale_approval:
                hire.require_current_approval(conn, draft.personnel_order_id)
            assert stale_approval.value.code == "APPROVAL_REQUIRED"
            with pytest.raises(hire.ElectronicHireError) as duplicate_decision:
                resolve_position_review(conn, request_id=int(request["request_id"]),
                    actor_user_id=actor, mode=mode, position_id=position_id, new_position=None)
            assert duplicate_decision.value.code == "POSITION_REQUEST_RESOLVED"
        finally:
            transaction.rollback()


def test_unmatched_blocks_ready_register_and_apply(monkeypatch):
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            result, actor, unit, _, _ = _setup(conn)
            title = f"Учебная несопоставленная {uuid4().hex[:10]}"
            hire.update_conditions(conn, result.application_id, org_unit_id=unit,
                position_id=None, manual_position_name=title,
                manual_position_document_ru=f"учебную несопоставленную {title.rsplit(' ',1)[-1]}",
                employment_rate=Decimal("1"), planned_start_date=date(2026, 12, 1))
            _complete_card(conn, result.person_id)
            order = create_hire_order_draft_for_application(conn, application_id=result.application_id,
                                                             created_by_user_id=actor)
            monkeypatch.setattr(commands, "engine", SimpleNamespace(begin=lambda: nullcontext(conn)))
            for action in (lambda: commands.mark_personnel_order_ready_for_signature(order_id=order.personnel_order_id),
                           lambda: commands.register_personnel_order(order_id=order.personnel_order_id, target_status="SIGNED")):
                with pytest.raises(commands.PersonnelOrderValidationError) as blocked:
                    action()
                assert "сопоставления" in str(blocked.value)
            conn.execute(text("UPDATE public.personnel_orders SET status='SIGNED' WHERE order_id=:id"),
                         {"id": order.personnel_order_id})
            with pytest.raises(commands.PersonnelOrderValidationError) as blocked_apply:
                apply_personnel_order_in_conn(conn, order_id=order.personnel_order_id, created_by=actor)
            assert "сопоставления" in str(blocked_apply.value)
        finally:
            transaction.rollback()
