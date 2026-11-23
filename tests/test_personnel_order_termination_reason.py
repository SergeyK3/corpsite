from contextlib import nullcontext
import os

import pytest
from sqlalchemy import create_engine, text

from app.services import personnel_order_template_application_service as preview_service
from app.services import personnel_orders_command_service as command_service
from app.services import personnel_orders_query_service as query_service
from app.services.personnel_order_template_application_service import _render
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_termination_reason import EMPLOYEE_INITIATIVE, termination_reason_text
from app.services.personnel_orders_editorial.position_dictionary import document_nominative_personnel_order_position, localized_personnel_order_position
from app.services.personnel_orders_editorial.generators import format_personnel_order_date_numeric


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    def connect(self):
        return nullcontext(self.connection)

    def begin(self):
        return nullcontext(self.connection)


def test_employee_initiative_reason_has_bilingual_rendering_for_template_preview():
    assert termination_reason_text(EMPLOYEE_INITIATIVE, "ru") == "по инициативе работника"
    assert termination_reason_text(EMPLOYEE_INITIATIVE, "kk") == "жұмыскердің бастамасы бойынша"

    template = dict(get_personnel_order_template_spec("TERMINATION").initial_texts)
    template["item_type_code"] = "TERMINATION"
    template["body_template_ru"] = "Причина: {{termination.reason}}"
    template["body_template_kk"] = "Себебі: {{termination.reason}}"
    rendered = _render(template, {
        "employee.full_name": "Сотрудник",
        "position.title_ru": "Врач",
        "position.title_kk": "Дәрігер",
        "org_unit.title_ru": "Отделение",
        "org_unit.title_kk": "Бөлімше",
        "effective_date": "2026-01-01",
        "termination.reason.ru": termination_reason_text(EMPLOYEE_INITIATIVE, "ru"),
        "termination.reason.kk": termination_reason_text(EMPLOYEE_INITIATIVE, "kk"),
        "termination.unused_leave_days": "0",
        "basis": "Личное заявление работника",
    })
    assert "по инициативе работника" in rendered["body_template_ru"]
    assert "жұмыскердің бастамасы бойынша" in rendered["body_template_kk"]


def test_termination_template_uses_dictionary_position_and_short_basis_without_employee_name():
    assert localized_personnel_order_position("Старшая медсестра", "kk") == "Аға мейіргер"
    assert document_nominative_personnel_order_position("Врач") == "врач"
    assert document_nominative_personnel_order_position("Врач") != "врачу"
    template = dict(get_personnel_order_template_spec("TERMINATION").initial_texts)
    template["item_type_code"] = "TERMINATION"
    template["basis_template_ru"] = "Личное заявление"
    template["basis_template_kk"] = "Жеке өтініш"
    rendered = _render(template, {
        "employee.full_name": "Айдарова А.",
        "position.title_ru": "Старшая медсестра", "position.title_kk": localized_personnel_order_position("Старшая медсестра", "kk"),
        "org_unit.title_ru": "Отделение", "org_unit.title_kk": "Бөлімше", "effective_date": "2026-01-01",
        "termination.reason.ru": termination_reason_text(EMPLOYEE_INITIATIVE, "ru"),
        "termination.reason.kk": termination_reason_text(EMPLOYEE_INITIATIVE, "kk"),
        "termination.unused_leave_days": "0", "basis": "Личное заявление работника",
    })
    assert "Аға мейіргер" in rendered["body_template_kk"]
    assert rendered["basis_template_ru"] == "Личное заявление"
    assert rendered["basis_template_kk"] == "Жеке өтініш"
    assert "Айдарова" not in rendered["basis_template_ru"] + rendered["basis_template_kk"]


def test_termination_draft_uses_neutral_name_and_common_local_date_formatter():
    assert format_personnel_order_date_numeric("2026-07-01") == "01.07.2026"
    template = dict(get_personnel_order_template_spec("TERMINATION").initial_texts)
    template["item_type_code"] = "TERMINATION"
    template["body_template_ru"] = (
        "Уволить сотрудника {{employee.full_name}}, должность: {{position.title_ru}}, "
        "отделение: {{org_unit.title_ru}}, с {{effective_date_local}}. "
        "Причина увольнения: {{termination.reason}}."
    )
    template["body_template_kk"] = (
        "Қызметкер {{employee.full_name}}, лауазымы: {{position.title_kk}}, "
        "бөлімшесі: {{org_unit.title_kk}}, {{effective_date_local}} бастап жұмыстан босатылсын. "
        "Жұмыстан босату себебі: {{termination.reason}}."
    )
    template["basis_template_ru"] = "Личное заявление"
    template["basis_template_kk"] = "Жеке өтініш"
    rendered = _render(template, {
        "employee.full_name": "Айдарова А.",
        "position.title_ru": "Старшая медсестра",
        "position.title_kk": localized_personnel_order_position("Старшая медсестра", "kk"),
        "org_unit.title_ru": "ЦСО", "org_unit.title_kk": "ЦСО",
        "effective_date": "2026-07-01", "effective_date_local": format_personnel_order_date_numeric("2026-07-01"),
        "termination.reason.ru": termination_reason_text(EMPLOYEE_INITIATIVE, "ru"),
        "termination.reason.kk": termination_reason_text(EMPLOYEE_INITIATIVE, "kk"),
        "termination.unused_leave_days": "", "basis": "не используется",
    })
    assert rendered["body_template_ru"] == (
        "Уволить сотрудника Айдарова А., должность: Старшая медсестра, отделение: ЦСО, "
        "с 01.07.2026. Причина увольнения: по инициативе работника."
    )
    assert rendered["body_template_kk"] == (
        "Қызметкер Айдарова А., лауазымы: Аға мейіргер, бөлімшесі: ЦСО, "
        "01.07.2026 бастап жұмыстан босатылсын. Жұмыстан босату себебі: жұмыскердің бастамасы бойынша."
    )
    assert rendered["basis_template_ru"] == "Личное заявление"
    assert rendered["basis_template_kk"] == "Жеке өтініш"


@pytest.mark.skipif("corpsite_test" not in TEST_DATABASE_URL, reason="requires corpsite_test")
def test_termination_reason_save_reload_and_preview_use_the_persisted_payload(monkeypatch):
    engine = create_engine(TEST_DATABASE_URL)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        actor = connection.execute(text("SELECT user_id FROM users ORDER BY user_id LIMIT 1")).scalar_one()
        employee_id = connection.execute(text("""
            SELECT e.employee_id
            FROM employees e
            JOIN positions p ON p.position_id = e.position_id
            JOIN org_units ou ON ou.unit_id = e.org_unit_id
            ORDER BY e.employee_id
            LIMIT 1
        """)).scalar_one()
        template_values = dict(get_personnel_order_template_spec("TERMINATION").initial_texts)
        template_values["version_number"] = 889950
        template_values["body_template_ru"] = "Employee: {{employee.full_name}}. Reason: {{termination.reason}}"
        template_values["body_template_kk"] = "Employee: {{employee.full_name}}. Reason: {{termination.reason}}"
        connection.execute(text("""
            INSERT INTO personnel_order_template_versions(
                item_type_code, version_number, status, title_ru, title_kk, preamble_ru, preamble_kk,
                body_template_ru, body_template_kk, basis_template_ru, basis_template_kk
            ) VALUES ('TERMINATION', :version_number, 'PUBLISHED', :title_ru, :title_kk, :preamble_ru,
                :preamble_kk, :body_template_ru, :body_template_kk, :basis_template_ru, :basis_template_kk)
        """), template_values)
        order_id = connection.execute(text("""
            INSERT INTO personnel_orders(order_type_code, status, source_mode, created_by, basis_summary)
            VALUES ('TERMINATION', 'DRAFT', 'MANUAL', :actor, 'Личное заявление работника')
            RETURNING order_id
        """), {"actor": actor}).scalar_one()
        connection.execute(text("""
            INSERT INTO personnel_order_evidence_scopes(order_id, generation)
            VALUES (:order_id, 1)
        """), {"order_id": order_id})
        item_id = connection.execute(text("""
            INSERT INTO personnel_order_items(order_id, item_number, item_type_code, employee_id,
                effective_date, item_status, payload)
            VALUES (:order_id, 1, 'TERMINATION', :employee_id, '2026-09-30', 'ACTIVE',
                '{"basis":"Личное заявление работника","basis_ids":["application-1"],"position_name":"Архивная должность","org_unit_name":"Архивное подразделение","source_reference":{"file_id":"source-1"}}'::jsonb)
            RETURNING item_id
        """), {"order_id": order_id, "employee_id": employee_id}).scalar_one()
        adapter = _Engine(connection)
        monkeypatch.setattr(command_service, "engine", adapter)
        monkeypatch.setattr(query_service, "engine", adapter)
        monkeypatch.setattr(preview_service, "engine", adapter)

        command_service.update_personnel_order_item(
            order_id=order_id,
            item_id=item_id,
            payload={
                "termination_reason": EMPLOYEE_INITIATIVE,
                "unused_leave_days": "0",
                "basis": "Личное заявление работника",
                "basis_ids": ["application-1"],
                "position_name": "Архивная должность",
                "org_unit_name": "Архивное подразделение",
                "source_reference": {"file_id": "source-1"},
                # Equivalent to the historical item for №1169-ж: this is the
                # canonical snapshot, while employees.full_name may be short.
                "employee": {"name": {"canonical": "Айдарова Алтынай Амангельдиновна"}},
            },
        )
        reloaded = query_service.get_personnel_order(order_id)
        assert reloaded["items"][0]["payload"]["termination_reason"] == EMPLOYEE_INITIATIVE
        assert reloaded["items"][0]["employee_id"] == employee_id
        assert reloaded["items"][0]["effective_date"] == "2026-09-30"
        assert reloaded["items"][0]["payload"]["basis_ids"] == ["application-1"]
        assert reloaded["items"][0]["payload"]["source_reference"] == {"file_id": "source-1"}
        preview = preview_service.preview_template_application(order_id)
        assert "по инициативе работника" in preview["proposed"]["body_template_ru"]
        assert "жұмыскердің бастамасы бойынша" in preview["proposed"]["body_template_kk"]
        assert "Айдарова Алтынай Амангельдиновна" in preview["proposed"]["body_template_ru"]
        assert "Айдарова Алтынай Амангельдиновна" in preview["proposed"]["body_template_kk"]
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()
