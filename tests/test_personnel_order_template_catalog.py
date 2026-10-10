from app.services.personnel_order_template_catalog_service import list_personnel_order_template_catalog
from app.services.personnel_order_template_catalog_data import CATALOG_PROJECTIONS
from app.services.personnel_order_template_specs import assert_personnel_order_template_specs, get_personnel_order_template_spec
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
    assert all(set(item) == {"type_code", "title_ru", "title_kk", "source", "support_level", "supported_locales", "uses_specialized_generator", "is_pilot", "editor_available", "allowed_variables", "required_variables", "required_fields", "notes", "pilot_detail", "template_detail"} for item in items)
    assert all(item["allowed_variables"] == list(get_personnel_order_template_spec(item["type_code"]).allowed_variables) for item in items)
    assert all(item["required_variables"] == {field: list(codes) for field, codes in get_personnel_order_template_spec(item["type_code"]).required_variables.items()} for item in items)
    assert {item["type_code"] for item in items if item["editor_available"]} == codes


def test_catalog_projections_match_the_migrated_golden_snapshot_for_all_types():
    assert_personnel_order_template_specs()
    actual = {
        item["type_code"]: {key: value for key, value in item.items() if key not in {"type_code", "allowed_variables", "required_variables"}}
        for item in list_personnel_order_template_catalog()
    }
    assert actual == CATALOG_PROJECTIONS


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
    assert "[[ФИО сотрудника]]" in ru["body"]
    assert all(value.casefold() in ru["body"].casefold() for value in ("[[ФИО сотрудника]]", "[[Должность]]", "[[Подразделение]]", "[[Дата выхода]]", "[[Ставка]]"))
    assert all(value.casefold() in kk["body"].casefold() for value in ("[[Қызметкердің аты-жөні]]", "[[Лауазым]]", "[[Бөлімше]]", "[[Жұмысқа шығу күні]]", "[[Мөлшерлеме]]"))
    assert all(value not in preview_text for value in ("15 января 2026", "2026 жылғы 15 қаңтар", "1.0"))
    assert "««" not in preview_text and "»»" not in preview_text
    assert all(item["pilot_detail"] is None for item in items if not item["is_pilot"])


def test_unpaid_leave_has_formalized_requisites_and_a_non_personal_bilingual_preview():
    items = list_personnel_order_template_catalog()
    unpaid = next(item for item in items if item["type_code"] == "LEAVE.UNPAID.GRANT")
    detail = unpaid["template_detail"]

    assert unpaid["support_level"] == "SUPPORTED"
    assert unpaid["allowed_variables"] == list(get_personnel_order_template_spec("LEAVE.UNPAID.GRANT").allowed_variables)
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
    assert all(forbidden not in preview_text for forbidden in ("15 января 2026", "2026 жылғы 15 қаңтар", "1.0", "««", "»»"))
    assert all(value in preview_text for value in ("[[фио сотрудника]]", "[[должность]]", "[[подразделение]]", "[[дата начала отпуска]]", "[[количество дней]]"))


def test_termination_has_typed_requisites_and_a_neutral_bilingual_preview():
    items = list_personnel_order_template_catalog()
    termination = next(item for item in items if item["type_code"] == "TERMINATION")
    detail = termination["template_detail"]

    assert termination["support_level"] == "SUPPORTED"
    assert termination["editor_available"] is True
    assert termination["pilot_detail"] is None
    assert termination["required_fields"] == detail["required_fields"] == [
        "ФИО сотрудника", "Текущая должность на русском языке", "Текущая должность на казахском языке", "Текущее подразделение на русском языке", "Текущее подразделение на казахском языке", "Дата увольнения", "Причина увольнения", "Количество дней неиспользованного отпуска", "Основание",
    ]
    assert [variable["code"] for variable in detail["variables"]] == [
        "employee.full_name", "position.title_ru", "position.title_kk", "org_unit.title_ru", "org_unit.title_kk", "effective_date", "effective_date_local", "termination.reason", "termination.unused_leave_days", "basis",
    ]

    ru, kk = detail["previews"]["ru"], detail["previews"]["kk"]
    assert ru["directive"] == "ПРИКАЗЫВАЮ:"
    assert kk["directive"] == "БҰЙЫРАМЫН:"
    assert all(value in ru["body"] for value in ("[[ФИО сотрудника]]", "[[Должность]]", "[[Подразделение]]", "[[Дата увольнения]]", "[[Причина увольнения]]"))
    assert all(value in kk["body"] for value in ("[[Қызметкердің аты-жөні]]", "[[Лауазым]]", "[[Бөлімше]]", "[[Жұмыстан босату күні]]", "[[Жұмыстан босату себебі]]"))
    assert "[[Количество дней неиспользованного отпуска]]" in ru["body"]
    assert "[[Пайдаланылмаған демалыс күндерінің саны]]" in kk["body"]
    assert ru["basis"] == "Основание: [[Основание]]"
    assert kk["basis"] == "Негіз: [[Негіз]]"
    assert "Основание:" not in ru["body"]
    assert "Негіздеме:" not in kk["body"]
    assert "Негіз:" not in kk["body"]
    assert kk["body"].count("еңбек шарты") == kk["body"].count("бұзылсын") == 1
    preview_text = " ".join(value for preview in (ru, kk) for value in preview.values()).casefold()
    assert all(forbidden not in preview_text for forbidden in ("ставка", "1.0", "15 января 2026", "2026 жылғы 15 қаңтар", "««", "»»", "райник", "оразбекова"))


def test_catalog_endpoint_requires_existing_admin_guard():
    app.dependency_overrides[require_sysadmin_api] = lambda: {"user_id": 2, "role_id": 2}
    try:
        response = TestClient(app).get("/admin/personnel-order-templates")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "payload" not in response.text and "employee_id" not in response.text

    assert TestClient(app).get("/admin/personnel-order-templates").status_code in {401, 403}
