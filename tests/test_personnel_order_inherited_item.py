"""Rollback-only integration tests: exact contract, independent items and history."""
import os
from contextlib import nullcontext
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.services import personnel_order_add_item_service as inherited
from app.services import personnel_order_manual_draft_service as manual
from app.services import personnel_order_template_application_service as applications
from app.services import personnel_order_template_draft_service as templates
from app.services import personnel_orders_command_service as commands
from app.services.personnel_orders_query_service import PersonnelOrderValidationError

URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL or make_url(URL).host not in ("localhost", "127.0.0.1") or make_url(URL).database != "corpsite_test", reason="requires local migrated corpsite_test")


class TransactionEngine:
    def __init__(self, conn): self.conn = conn
    def begin(self): return nullcontext(self.conn)
    def connect(self): return nullcontext(self.conn)


@pytest.fixture
def database(monkeypatch):
    from app.services import personnel_order_document_header_service as headers, personnel_orders_query_service as queries
    from app.services.personnel_orders_editorial import service as editorial
    from app.services.personnel_orders_editorial import generation_service as generation
    engine = create_engine(URL)
    with engine.connect() as conn:
        transaction = conn.begin()
        for module in (inherited, manual, applications, templates, commands, headers, queries, editorial, generation):
            monkeypatch.setattr(module, "engine", TransactionEngine(conn))
        try: yield conn
        finally: transaction.rollback()
    engine.dispose()


def publish(conn, code="SUPPLEMENTARY_PAY", texts=None):
    actor = conn.execute(text("SELECT user_id FROM users ORDER BY user_id LIMIT 1")).scalar_one()
    draft = templates.copy_template(code, None, "TEST inherited " + uuid4().hex, "TEST KK", actor, None, base_source="INITIAL")
    if texts:
        content = {key: draft[key] for key in templates.TEXT_FIELDS}
        content.update(texts)
        draft = templates.save_draft(code, draft["revision"], content, actor, draft["template_id"])
    return templates.publish_draft(code, draft["revision"], actor, draft["template_id"]), actor


def pay_payload(percent=25, name="Сотруднику Первому", basis="Личное заявление"):
    from app.services.personnel_order_service_area_contract import SAMPLE_RECIPIENT
    return {"allowance_recipient": SAMPLE_RECIPIENT, "allowance": {"percent": percent, "employee_dative_ru": name, "employee_dative_kk": "Бірінші қызметкерге", "basis_ru": basis, "basis_kk": "Жеке өтініш"}}


def create_order(conn, version, actor, payload, code="SUPPLEMENTARY_PAY"):
    employees = list(conn.execute(text("SELECT employee_id FROM employees ORDER BY employee_id LIMIT 2")).scalars())
    assert len(employees) == 2
    result = manual.create_manual_draft(created_by=actor, template_version_id=version["template_version_id"], order_number="TEST-INHERIT-" + uuid4().hex, order_date=date(2026, 10, 10), source_title="TEST inherited", source_title_locale="ru", item_type_code=code, employee_id=employees[0], effective_date=date(2026, 2, 2), item_payload=payload)
    return result["order_id"], employees


def first_blocks(conn, order_id):
    return [dict(row) for row in conn.execute(text("SELECT b.* FROM personnel_order_item_editorial_blocks b JOIN personnel_order_items i ON i.item_id=b.order_item_id WHERE i.order_id=:id AND i.item_number=1 ORDER BY b.item_editorial_block_id"), {"id": order_id}).mappings()]


@pytest.mark.parametrize("first_percent,second_percent", [(25, 50), (50, 25)])
@pytest.mark.parametrize("missing_kk_position", [False, True])
def test_same_version_new_employee_own_text_and_bases_preserves_first(database, first_percent, second_percent, missing_kk_position):
    from app.services.personnel_order_supplementary_pay_contract import BODY_RU, BODY_KK
    version, actor = publish(database, texts={"body_template_ru": BODY_RU, "body_template_kk": BODY_KK})
    initial_payload = pay_payload(first_percent)
    second_payload = pay_payload(second_percent, "Сотруднику Второму", "Заявление второго сотрудника")
    if missing_kk_position:
        for payload in (initial_payload, second_payload):
            payload['allowance_recipient'] = {**payload['allowance_recipient'], 'position_kk': ''}
    order_id, employees = create_order(database, version, actor, initial_payload)
    before = first_blocks(database, order_id)
    # Later publication of another independent template must not replace this binding.
    publish(database, texts={"body_template_ru": BODY_RU, "body_template_kk": BODY_KK})
    context = inherited.get_add_item_context(order_id)
    assert context["template"]["template_version_id"] == version["template_version_id"]
    detail = commands.create_personnel_order_item(order_id=order_id, item_type_code="SUPPLEMENTARY_PAY", employee_id=employees[1], effective_date=date(2026, 2, 3), payload=second_payload, actor_user_id=actor, template_version_id=version["template_version_id"])
    assert len(detail["items"]) == 2
    assert first_blocks(database, order_id) == before
    second = detail["items"][1]
    assert second["payload"]["allowance"]["percent"] == second_percent
    assert isinstance(second["payload"]["allowance"]["percent"], int)
    blocks = {f"{r['block_type']}_{r['locale']}": r["generated_text"] for r in database.execute(text("SELECT * FROM personnel_order_item_editorial_blocks WHERE order_item_id=:id"), {"id": second["item_id"]}).mappings()}
    assert f"{second_percent}%" in blocks["body_ru"] and f"{second_percent}%" in blocks["body_kk"]
    assert "Сотруднику Второму" in blocks["body_ru"]
    if missing_kk_position:
        assert blocks['body_kk'].startswith('Бірінші қызметкерге ')
        assert 'терапия бөлімшесінің' not in blocks['body_kk']
    assert "Заявление второго сотрудника" in blocks["basis_ru"]
    assert "Жеке өтініш" in blocks["basis_kk"]
    assert inherited.get_add_item_context(order_id)["template"]["template_version_id"] == version["template_version_id"]
    assert set(database.execute(text("SELECT template_version_id FROM personnel_order_template_applications WHERE order_id=:id"), {"id": order_id}).scalars()) == {version["template_version_id"]}


@pytest.mark.parametrize("problem", ["other_type", "same_employee", "wrong_version", "invalid_percent", "missing_basis"])
def test_invalid_addition_is_atomic(database, problem):
    from app.services.personnel_order_supplementary_pay_contract import BODY_RU, BODY_KK
    version, actor = publish(database, texts={"body_template_ru": BODY_RU, "body_template_kk": BODY_KK})
    order_id, employees = create_order(database, version, actor, pay_payload())
    args = dict(order_id=order_id, item_type_code="SUPPLEMENTARY_PAY", employee_id=employees[1], effective_date=date(2026, 2, 2), payload=pay_payload(), actor_user_id=actor, template_version_id=version["template_version_id"])
    if problem == "other_type": args["item_type_code"] = "TRANSFER"
    if problem == "same_employee": args["employee_id"] = employees[0]
    if problem == "wrong_version": args["template_version_id"] += 100000
    if problem == "invalid_percent": args["payload"]["allowance"]["percent"] = 30
    if problem == "missing_basis": args["payload"]["allowance"]["basis_kk"] = ""
    before = first_blocks(database, order_id)
    with pytest.raises(PersonnelOrderValidationError): commands.create_personnel_order_item(**args)
    assert database.execute(text("SELECT count(*) FROM personnel_order_items WHERE order_id=:id"), {"id": order_id}).scalar_one() == 1
    assert first_blocks(database, order_id) == before


def test_first_application_fallback_missing_and_conflicting_bindings(database):
    from app.services.personnel_order_supplementary_pay_contract import BODY_RU, BODY_KK
    version, actor = publish(database, texts={"body_template_ru": BODY_RU, "body_template_kk": BODY_KK})
    order_id, employees = create_order(database, version, actor, pay_payload())
    database.execute(text("UPDATE personnel_orders SET selected_template_version_id=NULL WHERE order_id=:id"), {"id": order_id})
    assert inherited.get_add_item_context(order_id)["template"]["template_version_id"] == version["template_version_id"]
    # Archived exact versions remain usable; no fallback to a new publication.
    database.execute(text("UPDATE personnel_order_template_versions SET status='ARCHIVED' WHERE template_version_id=:id"), {"id": version["template_version_id"]})
    assert inherited.get_add_item_context(order_id)["available"]
    commands.create_personnel_order_item(order_id=order_id, item_type_code="SUPPLEMENTARY_PAY", employee_id=employees[1], effective_date=date(2026, 2, 3), payload=pay_payload(50), actor_user_id=actor)
    assert inherited.get_add_item_context(order_id)["template"]["template_version_id"] == version["template_version_id"]
    other, _ = publish(database, texts={"body_template_ru": BODY_RU, "body_template_kk": BODY_KK})
    database.execute(text("UPDATE personnel_orders SET selected_template_version_id=:version WHERE order_id=:id"), {"id": order_id, "version": other["template_version_id"]})
    context = inherited.get_add_item_context(order_id)
    assert not context["available"] and "противоречат" in context["reason"]
    unbound_id = manual._insert_manual_order(database, {"number": "TEST-UNBOUND-" + uuid4().hex, "order_date": date(2026, 10, 10), "item_type": "SUPPLEMENTARY_PAY", "source_mode": "MANUAL", "title": "TEST unbound", "locale": "ru", "created_by": actor, "template_version": None}, supports_selection=True)
    database.execute(text("INSERT INTO personnel_order_items(order_id,item_number,item_type_code,item_status,employee_id,effective_date,payload) SELECT :unbound,item_number,item_type_code,item_status,employee_id,effective_date,payload FROM personnel_order_items WHERE order_id=:id"), {"id": order_id, "unbound": unbound_id})
    context = inherited.get_add_item_context(unbound_id)
    assert not context["available"] and "отсутствует привязка" in context["reason"]


@pytest.mark.parametrize("mode", ["RATE", "PAY"])
def test_concurrent_variants_inherit_exact_version_and_render_second_item(database, mode):
    from app.services.personnel_order_replacement_contract import RATE_RU, RATE_KK, SAMPLE_CONCURRENT, SAMPLE_REPLACEMENT
    from app.services.personnel_order_service_area_contract import BODY_RU, BODY_KK, SAMPLE_RECIPIENT
    content = {"body_template_ru": RATE_RU if mode == "RATE" else BODY_RU, "body_template_kk": RATE_KK if mode == "RATE" else BODY_KK}
    version, actor = publish(database, "CONCURRENT_DUTY_START", content)
    payload = {"concurrent": dict(SAMPLE_CONCURRENT), "replacement": dict(SAMPLE_REPLACEMENT)}
    if mode == "PAY":
        payload["allowance_recipient"] = SAMPLE_RECIPIENT
        payload["replacement"] = {"term_type": "NONE", "allowance_percent": 25}
        payload["concurrent"].pop("rate"); payload["concurrent"].pop("total_rate")
    order_id, employees = create_order(database, version, actor, payload, "CONCURRENT_DUTY_START")
    before = first_blocks(database, order_id)
    # A competing variant of the same type does not affect this order.
    publish(database, "CONCURRENT_DUTY_START", {"body_template_ru": BODY_RU if mode == "RATE" else RATE_RU, "body_template_kk": BODY_KK if mode == "RATE" else RATE_KK})
    context = inherited.get_add_item_context(order_id)
    assert context["template"]["template_version_id"] == version["template_version_id"]
    assert context["template"]["replacement_mode"] == mode
    payload["concurrent"]["employee_dative_ru"] = "Второму Сотруднику"
    if mode == "PAY": payload["replacement"]["allowance_percent"] = 50
    detail = commands.create_personnel_order_item(order_id=order_id, item_type_code="CONCURRENT_DUTY_START", employee_id=employees[1], effective_date=date(2026, 2, 3), payload=payload, actor_user_id=actor)
    assert first_blocks(database, order_id) == before
    second = detail["items"][1]
    body = database.execute(text("SELECT generated_text FROM personnel_order_item_editorial_blocks WHERE order_item_id=:id AND locale='ru' AND block_type='body'"), {"id": second["item_id"]}).scalar_one()
    assert "Второму Сотруднику" in body
    if mode == "PAY":
        assert "50%" in body and second["payload"]["replacement"]["allowance_percent"] == 50
        assert "rate" not in second["payload"]["concurrent"]
    else:
        assert "0,25 ставки" in body and "%" not in body


def test_historical_mixed_order_is_blocked_without_converting_its_items(database):
    from app.services.personnel_order_supplementary_pay_contract import BODY_RU, BODY_KK
    version, actor = publish(database, texts={"body_template_ru": BODY_RU, "body_template_kk": BODY_KK})
    order_id, employees = create_order(database, version, actor, pay_payload())
    database.execute(text("INSERT INTO personnel_order_items(order_id,item_number,item_type_code,item_status,employee_id,effective_date,payload) VALUES(:order,2,'TRANSFER','ACTIVE',:employee,'2026-02-02','{}'::jsonb)"), {"order": order_id, "employee": employees[1]})
    before = [dict(row) for row in database.execute(text("SELECT * FROM personnel_order_items WHERE order_id=:id ORDER BY item_number"), {"id": order_id}).mappings()]
    context = inherited.get_add_item_context(order_id)
    assert not context["available"] and "разные типы" in context["reason"]
    with pytest.raises(PersonnelOrderValidationError):
        commands.create_personnel_order_item(order_id=order_id, item_type_code="SUPPLEMENTARY_PAY", employee_id=employees[1], effective_date=date(2026, 2, 3), payload=pay_payload(50), actor_user_id=actor)
    assert [dict(row) for row in database.execute(text("SELECT * FROM personnel_order_items WHERE order_id=:id ORDER BY item_number"), {"id": order_id}).mappings()] == before


def test_regeneration_uses_exact_saved_template_and_keeps_overrides(database):
    from app.services.personnel_orders_editorial.generation_service import generate_editorial
    from app.services.personnel_order_supplementary_pay_contract import BODY_RU, BODY_KK
    content = {"title_ru": "Сохранённый заголовок", "preamble_ru": "Сохранённая преамбула", "body_template_ru": BODY_RU, "body_template_kk": BODY_KK}
    version, actor = publish(database, texts=content)
    order_id, employees = create_order(database, version, actor, pay_payload(25))
    commands.create_personnel_order_item(order_id=order_id, item_type_code="SUPPLEMENTARY_PAY", employee_id=employees[1], effective_date=date(2026, 2, 3), payload=pay_payload(50, "Второму Сотруднику", "Заявление второго"), actor_user_id=actor)
    database.execute(text("UPDATE personnel_order_template_versions SET status='ARCHIVED' WHERE template_version_id=:id"), {"id": version["template_version_id"]})
    publish(database, texts={"body_template_ru": BODY_RU, "body_template_kk": BODY_KK})
    first_id = database.execute(text("SELECT item_id FROM personnel_order_items WHERE order_id=:id AND item_number=1"), {"id": order_id}).scalar_one()
    database.execute(text("UPDATE personnel_order_item_editorial_blocks SET override_text='Ручная поправка' WHERE order_item_id=:id AND locale='ru' AND block_type='body'"), {"id": first_id})
    generate_editorial(order_id, user_id=actor, conn=database)
    order_blocks = {f"{r['block_type']}_{r['locale']}":r['generated_text'] for r in database.execute(text("SELECT * FROM personnel_order_editorial_blocks WHERE order_id=:id"), {"id": order_id}).mappings()}
    assert order_blocks["title_ru"] == content["title_ru"]
    assert order_blocks["preamble_ru"] == content["preamble_ru"]
    blocks = [dict(r) for r in database.execute(text("SELECT b.*,i.item_number FROM personnel_order_item_editorial_blocks b JOIN personnel_order_items i ON i.item_id=b.order_item_id WHERE i.order_id=:id"), {"id": order_id}).mappings()]
    assert not any("DOCX" in r['generated_text'] for r in blocks)
    assert next(r for r in blocks if r['item_number']==1 and r['locale']=='ru' and r['block_type']=='body')['override_text']=='Ручная поправка'
    for item_number,percent in ((1,25),(2,50)):
        for locale in ('ru','kk'):
            body=next(r for r in blocks if r['item_number']==item_number and r['locale']==locale and r['block_type']=='body')['generated_text']
            assert f'{percent}%' in body
    assert inherited.get_add_item_context(order_id)['template']['template_version_id']==version['template_version_id']
