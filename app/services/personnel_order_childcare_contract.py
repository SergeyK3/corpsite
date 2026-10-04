"""LEAVE.CHILDCARE.GRANT: explicit dates, document forms and two grounds.

The existing item payload owns basis (application) and basis.birth_certificate.
Certificate issuance is never used as the child's birthday or leave end date.
"""
from datetime import date
from typing import Any, Mapping
import re

from app.services.personnel_order_unpaid_leave_contract import format_leave_date

TYPE = "LEAVE.CHILDCARE.GRANT"
TEXTS = {
    "title_ru": "О неоплачиваемом отпуске по уходу за ребенком",
    "title_kk": "Бала күтіміне байланысты жалақы сақталмайтын демалыс туралы",
    "preamble_ru": "В соответствии со статьёй 100 Трудового кодекса Республики Казахстан",
    "preamble_kk": "Қазақстан Республикасы Еңбек Кодексінің 100 - бабына сәйкес",
    "body_template_ru": "Предоставить {{employee.full_name_dative_ru}} (должность: {{position.document_nominative_ru}}, подразделение: «{{org_unit.title_ru}}») отпуск без сохранения заработной платы по уходу за ребёнком до достижения им возраста трёх лет с {{leave.start_ru}} по {{leave.end_ru}}.",
    "body_template_kk": "{{org_unit.document_genitive_kk}} {{position.document_possessive_kk}} {{employee.full_name_dative_kk}} {{leave.period_clause_kk}} бала үш жасқа толғанға дейін бала күтіміне байланысты жалақысы сақталмайтын демалыс берілсін.",
    "basis_template_ru": "Основание: личное заявление {{employee.full_name_genitive_ru}}{{basis.application_date_ru}}{{basis.application_number_suffix}}, свидетельство о рождении от {{basis.birth_certificate_date_ru}} № {{basis.birth_certificate_number}}.",
    "basis_template_kk": "Негіз: {{employee.full_name_genitive_kk}}{{basis.application_date_kk}}{{basis.application_number_suffix}} жеке өтініші, {{basis.birth_certificate_date_kk}} № {{basis.birth_certificate_number}} туу туралы куәлік.",
}
REQUIRED_VARIABLES = {
    field: tuple(re.findall(r"\{\{([\w.]+)\}\}", value))
    for field, value in TEXTS.items() if field.startswith(("body_", "basis_"))
}
VARIABLES = tuple(dict.fromkeys(v for values in REQUIRED_VARIABLES.values() for v in values))
REQUIRED_FIELDS = (
    "Сотрудник", "Дата начала отпуска", "Дата окончания отпуска (вводится отдельно)",
    "ФИО RU: дательный и родительный падежи", "ФИО KK: дательный и родительный падежи",
    "Документная форма должности RU и KK", "Подразделение RU и родительная форма KK",
    "Дата личного заявления", "Дата выдачи свидетельства о рождении", "Номер свидетельства о рождении",
)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _date(value: Any, label: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        raise ValueError(f"Для отпуска по уходу за ребёнком заполните: {label}.") from None


def childcare_values(payload: Mapping[str, Any], *, org_unit_ru: str = "") -> dict[str, str]:
    start = _date(payload.get("leave_start"), "дата начала отпуска")
    end = _date(payload.get("leave_end"), "дата окончания отпуска")
    if end < start:
        raise ValueError("Дата окончания отпуска не может быть раньше даты начала.")
    basis = payload.get("basis") or {}
    if not isinstance(basis, Mapping) or basis.get("kind") != "PERSONAL_APPLICATION":
        raise ValueError("Для отпуска по уходу за ребёнком требуется личное заявление.")
    application_date = _date(basis.get("date"), "дата личного заявления")
    certificate = basis.get("birth_certificate") or {}
    if not isinstance(certificate, Mapping):
        raise ValueError("Заполните реквизиты свидетельства о рождении.")
    certificate_date = _date(certificate.get("date"), "дата выдачи свидетельства о рождении")
    certificate_number = _text(certificate.get("number"))
    if not certificate_number:
        raise ValueError("Заполните номер свидетельства о рождении.")
    values: dict[str, str] = {"org_unit.title_ru": _text(org_unit_ru)}
    forms_by_locale = {
        "kk": {"org_unit.document_genitive_kk": "org_unit_document_genitive_kk", "position.document_possessive_kk": "position_document_possessive_kk", "employee.full_name_dative_kk": "employee_full_name_dative_kk", "employee.full_name_genitive_kk": "employee_full_name_genitive_kk"},
        "ru": {"position.document_nominative_ru": "position_document_nominative_ru", "employee.full_name_dative_ru": "employee_full_name_dative_ru", "employee.full_name_genitive_ru": "employee_full_name_genitive_ru"},
    }
    for locale, fields in forms_by_locale.items():
        forms = payload.get(f"document_forms_{locale}") or {}
        for variable, key in fields.items():
            values[variable] = _text(forms.get(key)) if isinstance(forms, Mapping) else ""
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError("Заполните документные формы: " + ", ".join(missing))
    number = _text(basis.get("number"))
    values.update({
        "leave.start_ru": format_leave_date(start, "ru"), "leave.end_ru": format_leave_date(end, "ru"),
        "leave.start_kk": format_leave_date(start, "kk"), "leave.end_kk": format_leave_date(end, "kk"),
        "leave.period_clause_kk": f"{format_leave_date(start, 'kk')} {'бен' if start.month in (3, 8) else 'пен' if start.month == 9 else 'мен'} {format_leave_date(end, 'kk')} аралығында",
        "basis.application_date_ru": " от " + format_leave_date(application_date, "ru"),
        "basis.application_date_kk": " " + format_leave_date(application_date, "kk") + " күнгі",
        "basis.application_number_suffix": " № " + number if number else "",
        "basis.birth_certificate_date_ru": format_leave_date(certificate_date, "ru"),
        "basis.birth_certificate_date_kk": format_leave_date(certificate_date, "kk") + ("дегі" if certificate_date.month in (4, 7) else "тегі" if certificate_date.month == 9 else "дағы"),
        "basis.birth_certificate_number": certificate_number,
    })
    return values


def render_childcare(field: str, values: Mapping[str, str]) -> str:
    return re.sub(r"\{\{([\w.]+)\}\}", lambda m: values[m[1]], TEXTS[field])


def without_directive(value: str) -> str:
    """Preserve stored user text; the shared document view owns the directive."""
    return re.sub(r"(?:ПРИКАЗЫВАЮ|БҰЙЫРАМЫН)\s*:", "", value, flags=re.I).strip().rstrip(",").strip()
