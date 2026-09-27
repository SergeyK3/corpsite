from app.services.personnel_order_template_catalog_service import list_personnel_order_template_catalog
from app.services.personnel_orders_editorial.generators import generate_order_block
from app.main import app
from app.security.admin_guard import require_sysadmin_api
from fastapi.testclient import TestClient


def test_catalog_is_registry_backed_and_safe():
    items = list_personnel_order_template_catalog()
    codes = {item["type_code"] for item in items}
    assert {"HIRE", "TRANSFER", "TERMINATION", "LEAVE.ANNUAL.GRANT", "LEAVE.UNPAID.GRANT", "LEAVE.CHILDCARE.GRANT", "RETURN_FROM_CHILDCARE_LEAVE", "CONCURRENT_DUTY_START", "CONCURRENT_DUTY_END", "SUPPLEMENTARY_PAY"} <= codes
    assert "COMPOSITE" not in codes
    pilot = next(item for item in items if item["type_code"] == "RETURN_FROM_CHILDCARE_LEAVE")
    assert pilot["is_pilot"] is True and pilot["support_level"] == "SUPPORTED"
    assert all(set(item) == {"type_code", "title_ru", "title_kk", "source", "support_level", "supported_locales", "uses_specialized_generator", "is_pilot", "required_fields", "notes", "pilot_detail", "template_detail"} for item in items)


def test_pilot_has_typed_requisites_and_non_personal_bilingual_preview():
    items = list_personnel_order_template_catalog()
    pilot = next(item for item in items if item["type_code"] == "RETURN_FROM_CHILDCARE_LEAVE")
    detail = pilot["pilot_detail"]

    assert pilot["required_fields"] == detail["required_fields"]
    assert detail["required_fields"] == [
        "ФИО сотрудника",
        "Должность на русском языке",
        "Должность на казахском языке",
        "Подразделение на русском языке",
        "Подразделение на казахском языке",
        "Ставка",
        "Дата выхода на работу",
        "Основание: личное заявление или другое подтверждённое основание",
    ]
    assert detail["additional_fields"] == []
    assert "Печатный подвал" in detail["document_parts"]
    assert detail["specialty_note"] == "Специальность хранится отдельно и в тело этого приказа не включается."

    ru, kk = detail["previews"]["ru"], detail["previews"]["kk"]
    assert ru["directive"] == "ПРИКАЗЫВАЮ:"
    assert kk["directive"] == "БҰЙЫРАМЫН:"
    assert ru["basis"] == "Основание: Личное заявление."
    assert kk["basis"] == "Негіз: Жеке өтініші."
    assert ru["footer"] == (
        "С приказом ознакомлен(а): ___________________ [Фамилия И.]\n"
        "«___» ______________ 20___ г.\n"
        "Исполнитель: [Инициалы и фамилия исполнителя]"
    )
    assert kk["footer"] == (
        "Бұйрықпен таныстым: ___________________ [Тегі А.]\n"
        "«___» ______________ 20___ ж.\n"
        "Орындаушы: [Орындаушының аты-жөні]"
    )
    assert ru["basis"].count("Основание:") == 1
    assert kk["basis"].count("Негіз:") == 1
    preview_text = " ".join(value for preview in (ru, kk) for value in preview.values()).lower()
    assert all(forbidden not in preview_text for forbidden in ("стаж", "дополнительное распоряжение", "контроль", "docx"))
    assert all(real_name not in preview_text for real_name in ("райник", "оразбекова"))
    assert "сотруднику сотрудник" not in ru["body"].lower()
    assert "сотрудникға" not in kk["body"].lower()
    assert "«ФИО сотрудника»" in ru["body"]
    assert "шартты адамға" in kk["body"].lower()
    assert all(item["pilot_detail"] is None for item in items if not item["is_pilot"])


def test_unpaid_leave_has_formalized_requisites_and_a_non_personal_bilingual_preview():
    items = list_personnel_order_template_catalog()
    unpaid = next(item for item in items if item["type_code"] == "LEAVE.UNPAID.GRANT")
    detail = unpaid["template_detail"]

    assert unpaid["support_level"] == "SUPPORTED"
    assert unpaid["pilot_detail"] is None
    assert unpaid["required_fields"] == detail["required_fields"]
    assert detail["required_fields"] == [
        "ФИО сотрудника",
        "Должность на русском языке",
        "Должность на казахском языке",
        "Подразделение на русском языке",
        "Подразделение на казахском языке",
        "Дата начала отпуска",
        "Дата окончания отпуска",
        "Вычисляемое количество календарных дней",
        "Личное заявление",
    ]
    assert detail["additional_fields"] == ["Дата заявления (если известна)", "Номер заявления (если известен)"]
    assert detail["document_parts"] == []
    assert [variable["code"] for variable in detail["variables"]] == [
        "employee.full_name", "position.title_ru", "position.title_kk", "org_unit.title_ru", "org_unit.title_kk",
        "leave.start_ru", "leave.start_kk", "leave.end_ru", "leave.end_kk", "leave.days",
        "basis.application_date_ru", "basis.application_date_kk", "basis.application_number_suffix",
    ]

    ru, kk = detail["previews"]["ru"], detail["previews"]["kk"]
    assert "Основание:" not in ru["body"]
    assert "Негіз:" not in kk["body"]
    assert ru["basis"].count("Основание:") == 1
    assert kk["basis"].count("Негіз:") == 1
    assert "Контроль" not in generate_order_block("closing", "ru", {"order_type_code": "LEAVE.UNPAID.GRANT"})["generated_text"]
    preview_text = " ".join(value for preview in (ru, kk) for value in preview.values()).casefold()
    assert all(forbidden not in preview_text for forbidden in ("райник", "оразбекова", "ставка", "специальность", "ребён"))


def test_catalog_endpoint_requires_existing_admin_guard():
    app.dependency_overrides[require_sysadmin_api] = lambda: {"user_id": 2, "role_id": 2}
    try:
        response = TestClient(app).get("/admin/personnel-order-templates")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "payload" not in response.text and "employee_id" not in response.text

    assert TestClient(app).get("/admin/personnel-order-templates").status_code in {401, 403}
