import pytest

from app.services.personnel_order_template_application_service import _render
from app.services.personnel_order_template_initial_data import INITIAL_TEXTS_BY_TYPE


TEMPLATE = {
    **INITIAL_TEXTS_BY_TYPE["LEAVE.UNPAID.GRANT"],
    "item_type_code": "LEAVE.UNPAID.GRANT",
    "body_template_ru": "Предоставить работнику {{employee.full_name_dative_ru}}, {{position.document_nominative_ru}} подразделения «{{org_unit.title_ru}}», отпуск без сохранения заработной платы {{leave.period_clause_ru}} продолжительностью {{leave.days}} календарных дней.",
    "body_template_kk": "{{org_unit.document_genitive_kk}} {{position.document_possessive_kk}} {{employee.full_name_dative_kk}} {{leave.period_clause_kk}} еңбекақысы сақталмайтын демалыс берілсін.",
    "basis_template_kk": "Негіз: {{employee.full_name_genitive_kk}} жеке өтініші.",
}


def test_unpaid_leave_ru_document_preview_uses_nominative_position_not_dative() -> None:
    rendered = _render(TEMPLATE, {
        "employee.full_name": "Ильясова Ассель Адиловна",
        "employee.full_name_dative_ru": "Ильясовой Ассель Адиловне",
        "position.title_ru": "Врач",
        "position.document_nominative_ru": "врач",
        "org_unit.title_ru": "Лучевая диагностика",
        "leave.start_ru": "13 июля 2026 года",
        "leave.end_ru": "17 июля 2026 года",
        "leave.period_clause_ru": "с 13 по 17 июля 2026 года включительно",
        "leave.days": "5",
        "org_unit.document_genitive_kk": "Сәулелік диагностика бөлімшесінің",
        "position.document_possessive_kk": "дәрігері",
        "employee.full_name_dative_kk": "Ассель Адиловна Ильясоваға",
        "employee.full_name_genitive_kk": "Ассель Адиловна Ильясованың",
        "leave.period_clause_kk": "2026 жылғы 13 шілдеден 17 шілдеге дейін қоса алғанда",
    })
    assert rendered["body_template_ru"] == (
        "Предоставить работнику Ильясовой Ассель Адиловне, врач подразделения «Лучевая диагностика», "
        "отпуск без сохранения заработной платы с 13 по 17 июля 2026 года включительно продолжительностью 5 календарных дней."
    )
    assert "врачу" not in rendered["body_template_ru"]


@pytest.mark.parametrize(
    ("forms", "period", "expected_body", "expected_basis"),
    [
        (
            {
                "org_unit.document_genitive_kk": "Сәулелік диагностика бөлімшесінің",
                "position.document_possessive_kk": "КТ дәрігері",
                "employee.full_name_dative_kk": "Жамантаеваға",
                "employee.full_name_genitive_kk": "Жамантаеваның",
            },
            "2026 жылғы 7 шілде күніне",
            "Сәулелік диагностика бөлімшесінің КТ дәрігері Жамантаеваға 2026 жылғы 7 шілде күніне еңбекақысы сақталмайтын демалыс берілсін.",
            "Негіз: Жамантаеваның жеке өтініші.",
        ),
        (
            {
                "org_unit.document_genitive_kk": "Емдеу-алдын алу жұмысы және сапаны бақылау бөлімінің",
                "position.document_possessive_kk": "дәрігер-статист қоса атқарушы",
                "employee.full_name_dative_kk": "Алимбаеваға",
                "employee.full_name_genitive_kk": "Алимбаеваның",
            },
            "2026 жылғы 13 мен 15 шілде аралығында",
            "Емдеу-алдын алу жұмысы және сапаны бақылау бөлімінің дәрігер-статист қоса атқарушы Алимбаеваға 2026 жылғы 13 мен 15 шілде аралығында еңбекақысы сақталмайтын демалыс берілсін.",
            "Негіз: Алимбаеваның жеке өтініші.",
        ),
        (
            {
                "org_unit.document_genitive_kk": "Қабылдау бөлімінің",
                "position.document_possessive_kk": "мейіргері",
                "employee.full_name_dative_kk": "Кимге",
                "employee.full_name_genitive_kk": "Кимнің",
            },
            "2026 жылғы 13 мен 15 шілде аралығында",
            "Қабылдау бөлімінің мейіргері Кимге 2026 жылғы 13 мен 15 шілде аралығында еңбекақысы сақталмайтын демалыс берілсін.",
            "Негіз: Кимнің жеке өтініші.",
        ),
    ],
)
def test_confirmed_document_forms_render_verbatim(forms, period, expected_body, expected_basis):
    values = {
        "employee.full_name": "Canonical name must not be inflected",
        "employee.full_name_dative_ru": "Каноническому сотруднику",
        "position.title_ru": "Position",
        "position.document_nominative_ru": "position",
        "org_unit.title_ru": "Unit",
        "leave.start_ru": "7 July 2026", "leave.end_ru": "7 July 2026", "leave.days": "1",
        "leave.period_clause_ru": "7 July 2026",
        "leave.period_clause_kk": period,
        **forms,
    }
    rendered = _render(TEMPLATE, values)
    assert rendered["body_template_kk"] == expected_body
    assert rendered["basis_template_kk"] == expected_basis


def test_document_template_reports_the_exact_missing_form() -> None:
    values = {
        "employee.full_name": "Canonical", "employee.full_name_dative_ru": "Каноническому", "position.title_ru": "Position", "position.document_nominative_ru": "position", "org_unit.title_ru": "Unit", "leave.start_ru": "7 July 2026", "leave.end_ru": "7 July 2026", "leave.days": "1", "leave.period_clause_ru": "7 July 2026",
        "org_unit.document_genitive_kk": "Бөлімшенің", "position.document_possessive_kk": "дәрігері",
        "employee.full_name_dative_kk": "Кимге", "employee.full_name_genitive_kk": "", "leave.period_clause_kk": "2026 жылғы 7 шілде күніне",
    }
    with pytest.raises(Exception, match="employee.full_name_genitive_kk"):
        _render(TEMPLATE, values)
