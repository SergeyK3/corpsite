"""Typed draft editor for the first editable personnel-order template."""
from __future__ import annotations

import re
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.engine import engine
from app.db.models.personnel_orders import ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE
from app.services.personnel_order_template_catalog_service import _pilot_detail, _unpaid_leave_detail

EDITABLE_TYPE = "LEAVE.UNPAID.GRANT"
EDITABLE_TYPES = frozenset({EDITABLE_TYPE, ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE})
_TOKEN = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
_FORBIDDEN = re.compile(r"<\s*/?\s*(?:script|style)|javascript:|=>|\b(?:if|for|function)\s*\(", re.I)
_REQUIRED_BY_TYPE = {
    EDITABLE_TYPE: {
        "body_template_ru": ("employee.full_name", "position.title_ru", "org_unit.title_ru", "leave.start_ru", "leave.end_ru", "leave.days"),
        "body_template_kk": ("employee.full_name", "position.title_kk", "org_unit.title_kk", "leave.start_kk", "leave.end_kk", "leave.days"),
    },
    ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE: {
        "body_template_ru": ("employee.full_name", "position.title_ru", "org_unit.title_ru", "rate", "effective_date"),
        "body_template_kk": ("employee.full_name", "position.title_kk", "org_unit.title_kk", "rate", "effective_date"),
        "basis_template_ru": ("basis",),
        "basis_template_kk": ("basis",),
    },
}


class TemplateDraftError(ValueError):
    def __init__(self, code: str, message: str, *, conflict: bool = False) -> None:
        super().__init__(message)
        self.code, self.conflict = code, conflict


def _row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in (
        "template_version_id", "item_type_code", "version_number", "status", "revision",
        "title_ru", "title_kk", "preamble_ru", "preamble_kk", "body_template_ru", "body_template_kk",
        "basis_template_ru", "basis_template_kk", "based_on_built_in", "created_at", "updated_at",
    )}


def _assert_type(item_type_code: str) -> None:
    if item_type_code not in EDITABLE_TYPES:
        raise TemplateDraftError("TEMPLATE_EDITOR_NOT_AVAILABLE", "Редактор пока доступен только для формализованных шаблонов.")


def _built_in(item_type_code: str = EDITABLE_TYPE) -> dict[str, str]:
    _assert_type(item_type_code)
    if item_type_code == ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE:
        detail = _pilot_detail()["previews"]
        return {
            "title_ru": detail["ru"]["title"], "title_kk": detail["kk"]["title"],
            "preamble_ru": detail["ru"]["preamble"], "preamble_kk": detail["kk"]["preamble"],
            "body_template_ru": "{{employee.full_name}}, {{position.title_ru}} подразделения «{{org_unit.title_ru}}», приступить к работе с {{effective_date}} с оплатой {{rate}} ставки.",
            "body_template_kk": "{{employee.full_name}}, «{{org_unit.title_kk}}» бөлімшесінің {{position.title_kk}} қызметкері, {{effective_date}} бастап {{rate}} ставкамен жұмысқа шықсын.",
            "basis_template_ru": "Основание: {{basis}}.",
            "basis_template_kk": "Негіз: {{basis}}.",
        }
    detail = _unpaid_leave_detail()["previews"]
    return {
        "title_ru": detail["ru"]["title"], "title_kk": detail["kk"]["title"],
        "preamble_ru": detail["ru"]["preamble"], "preamble_kk": detail["kk"]["preamble"],
        "body_template_ru": "Предоставить {{employee.full_name}}, {{position.title_ru}} подразделения «{{org_unit.title_ru}}», отпуск без сохранения заработной платы с {{leave.start_ru}} по {{leave.end_ru}} включительно продолжительностью {{leave.days}} календарных дней.",
        "body_template_kk": "{{employee.full_name}}, «{{org_unit.title_kk}}» бөлімшесінің «{{position.title_kk}}» қызметкеріне {{leave.start_kk}} мен {{leave.end_kk}} аралығындағы {{leave.days}} күнтізбелік күнге жалақы сақталмайтын демалыс берілсін.",
        "basis_template_ru": "Основание: Личное заявление{{basis.application_date_ru}}{{basis.application_number_suffix}}.",
        "basis_template_kk": "Негіз: Жеке өтініш{{basis.application_date_kk}}{{basis.application_number_suffix}}.",
    }


def _validate(values: Mapping[str, str], item_type_code: str = EDITABLE_TYPE) -> None:
    _assert_type(item_type_code)
    variables = {v["code"] for v in (_pilot_detail() if item_type_code == ORDER_TYPE_RETURN_FROM_CHILDCARE_LEAVE else _unpaid_leave_detail())["variables"]}
    for field, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise TemplateDraftError("TEMPLATE_TEXT_REQUIRED", f"{field} обязателен.")
        if _FORBIDDEN.search(value):
            raise TemplateDraftError("TEMPLATE_TEXT_UNSAFE", "HTML, скрипты и выражения запрещены.")
        unknown = {match.group(1) for match in _TOKEN.finditer(value)} - variables
        if unknown:
            raise TemplateDraftError("TEMPLATE_VARIABLE_UNKNOWN", "Неизвестная переменная: " + ", ".join(sorted(unknown)))
    for field, required in _REQUIRED_BY_TYPE[item_type_code].items():
        absent = [code for code in required if f"{{{{{code}}}}}" not in values[field]]
        if absent:
            raise TemplateDraftError("TEMPLATE_VARIABLE_REQUIRED", f"В {field} отсутствуют обязательные переменные: {', '.join(absent)}")


def get_draft(item_type_code: str) -> dict[str, Any] | None:
    _assert_type(item_type_code)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='DRAFT'"), {"type": item_type_code}).mappings().first()
    return _row(row) if row else None


def create_draft(item_type_code: str, actor_user_id: int) -> dict[str, Any]:
    _assert_type(item_type_code)
    values = _built_in(item_type_code)
    with engine.begin() as conn:
        existing = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='DRAFT'"), {"type": item_type_code}).mappings().first()
        if existing:
            return _row(existing)
        try:
            row = conn.execute(text("""
                INSERT INTO public.personnel_order_template_versions
                (item_type_code, version_number, status, title_ru, title_kk, preamble_ru, preamble_kk, body_template_ru, body_template_kk, basis_template_ru, basis_template_kk, created_by_user_id, updated_by_user_id)
                VALUES (:type, 1, 'DRAFT', :title_ru, :title_kk, :preamble_ru, :preamble_kk, :body_template_ru, :body_template_kk, :basis_template_ru, :basis_template_kk, :actor, :actor)
                RETURNING *
            """), {**values, "type": item_type_code, "actor": actor_user_id}).mappings().one()
        except IntegrityError:
            row = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='DRAFT'"), {"type": item_type_code}).mappings().one()
    return _row(row)


def save_draft(item_type_code: str, expected_revision: int, values: Mapping[str, str], actor_user_id: int) -> dict[str, Any]:
    _assert_type(item_type_code); _validate(values, item_type_code)
    with engine.begin() as conn:
        current = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='DRAFT' FOR UPDATE"), {"type": item_type_code}).mappings().first()
        if not current:
            raise TemplateDraftError("TEMPLATE_DRAFT_NOT_FOUND", "Черновая версия не создана.")
        if int(current["revision"]) != expected_revision:
            raise TemplateDraftError("TEMPLATE_REVISION_CONFLICT", "Черновик изменён другим пользователем.", conflict=True)
        if all(current[key] == values[key] for key in values): return _row(current)
        row = conn.execute(text("""
            UPDATE public.personnel_order_template_versions SET title_ru=:title_ru, title_kk=:title_kk, preamble_ru=:preamble_ru, preamble_kk=:preamble_kk,
            body_template_ru=:body_template_ru, body_template_kk=:body_template_kk, basis_template_ru=:basis_template_ru, basis_template_kk=:basis_template_kk,
            revision=revision+1, updated_by_user_id=:actor, updated_at=now() WHERE template_version_id=:id RETURNING *
        """), {**values, "actor": actor_user_id, "id": current["template_version_id"]}).mappings().one()
    return _row(row)


def preview_draft(item_type_code: str, values: Mapping[str, str]) -> dict[str, Any]:
    _assert_type(item_type_code); _validate(values, item_type_code)
    samples = {
        "employee.full_name": "«ФИО сотрудника»", "position.title_ru": "«Должность»", "position.title_kk": "«Лауазым»", "org_unit.title_ru": "«Подразделение»", "org_unit.title_kk": "«Бөлімше»",
        "leave.start_ru": "«Дата начала отпуска»", "leave.start_kk": "«Демалыстың басталу күні»", "leave.end_ru": "«Дата окончания отпуска»", "leave.end_kk": "«Демалыстың аяқталу күні»", "leave.days": "«Количество дней»",
        "basis.application_date_ru": "", "basis.application_date_kk": "", "basis.application_number_suffix": "",
        "rate": "«Ставка»",
    }
    locale_samples = {
        "ru": {**samples, "effective_date": "«Дата выхода»", "basis": "личное заявление"},
        "kk": {**samples, "employee.full_name": "«Қызметкердің аты-жөні»", "position.title_kk": "«Лауазым»", "org_unit.title_kk": "«Бөлімше»", "effective_date": "«Жұмысқа шығу күні»", "rate": "«Мөлшерлеме»", "basis": "жеке өтініш"},
    }
    def render(value: str, locale: str) -> str: return _TOKEN.sub(lambda m: locale_samples[locale][m.group(1)], value)
    return {"ru": {"title": render(values["title_ru"], "ru"), "preamble": render(values["preamble_ru"], "ru"), "directive": "ПРИКАЗЫВАЮ:", "body": render(values["body_template_ru"], "ru"), "basis": render(values["basis_template_ru"], "ru")}, "kk": {"title": render(values["title_kk"], "kk"), "preamble": render(values["preamble_kk"], "kk"), "directive": "БҰЙЫРАМЫН:", "body": render(values["body_template_kk"], "kk"), "basis": render(values["basis_template_kk"], "kk")}}
