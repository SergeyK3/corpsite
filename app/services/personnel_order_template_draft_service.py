"""Typed draft editor for the first editable personnel-order template."""
from __future__ import annotations

import re
from typing import Any, Mapping

from sqlalchemy import text

from app.db.engine import engine
from app.services.personnel_order_template_specs import get_personnel_order_template_spec

EDITABLE_TYPE = "LEAVE.UNPAID.GRANT"
TEXT_FIELDS = ("title_ru", "title_kk", "preamble_ru", "preamble_kk", "body_template_ru", "body_template_kk", "basis_template_ru", "basis_template_kk")
_TOKEN = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
_FORBIDDEN = re.compile(r"<\s*/?\s*(?:script|style)|javascript:|=>|\b(?:if|for|function)\s*\(", re.I)


class TemplateDraftError(ValueError):
    def __init__(self, code: str, message: str, *, conflict: bool = False) -> None:
        super().__init__(message)
        self.code, self.conflict = code, conflict


def _row(row: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: row[key] for key in (
        "template_version_id", "item_type_code", "version_number", "status", "revision",
        "title_ru", "title_kk", "preamble_ru", "preamble_kk", "body_template_ru", "body_template_kk",
        "basis_template_ru", "basis_template_kk", "based_on_built_in", "created_at", "updated_at",
    )}
    result["published_at"] = row.get("published_at")
    result["published_by_user_id"] = row.get("published_by_user_id")
    return result


def _assert_type(item_type_code: str) -> None:
    try:
        get_personnel_order_template_spec(item_type_code)
    except ValueError:
        raise TemplateDraftError("TEMPLATE_EDITOR_NOT_AVAILABLE", "Редактор для этого типа недоступен.")


def _validate(values: Mapping[str, str], item_type_code: str = EDITABLE_TYPE) -> None:
    _assert_type(item_type_code)
    spec = get_personnel_order_template_spec(item_type_code)
    variables = set(spec.allowed_variables)
    for field, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise TemplateDraftError("TEMPLATE_TEXT_REQUIRED", f"{field} обязателен.")
        if _FORBIDDEN.search(value):
            raise TemplateDraftError("TEMPLATE_TEXT_UNSAFE", "HTML, скрипты и выражения запрещены.")
        unknown = {match.group(1) for match in _TOKEN.finditer(value)} - variables
        if unknown:
            raise TemplateDraftError("TEMPLATE_VARIABLE_UNKNOWN", "Неизвестная переменная: " + ", ".join(sorted(unknown)))
    for field, required in spec.required_variables.items():
        absent = [code for code in required if f"{{{{{code}}}}}" not in values[field]]
        if absent:
            raise TemplateDraftError("TEMPLATE_VARIABLE_REQUIRED", f"В {field} отсутствуют обязательные переменные: {', '.join(absent)}")


def get_draft(item_type_code: str) -> dict[str, Any] | None:
    _assert_type(item_type_code)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='DRAFT'"), {"type": item_type_code}).mappings().first()
    return _row(row) if row else None


def get_published(item_type_code: str) -> dict[str, Any] | None:
    """Read the immutable published snapshot without creating a DRAFT."""
    _assert_type(item_type_code)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='PUBLISHED'"),
            {"type": item_type_code},
        ).mappings().first()
    return _row(row) if row else None


def get_editor_base(item_type_code: str) -> dict[str, Any]:
    """Read-only source for a client working copy; never creates a DRAFT."""
    published = get_published(item_type_code)
    if published is not None:
        # The editor-base response is intentionally narrower than a version
        # response.  In particular, do not leak DRAFT/PUBLISHED lifecycle
        # metadata into a client-only working copy (and keep it compatible
        # with the strict editor-base response schema).
        return {
            "source": "PUBLISHED",
            "item_type_code": published["item_type_code"],
            "template_version_id": published["template_version_id"],
            "version_number": published["version_number"],
            "revision": published["revision"],
            **{field: published[field] for field in TEXT_FIELDS},
        }
    return {"source": "INITIAL", "item_type_code": item_type_code,
            "template_version_id": None, "version_number": None, "revision": None,
            **dict(get_personnel_order_template_spec(item_type_code).initial_texts)}


def create_draft_from_working_copy(
    item_type_code: str,
    base_source: str,
    base_published_template_version_id: int | None,
    base_published_revision: int | None,
    values: Mapping[str, str],
    actor_user_id: int,
) -> dict[str, Any]:
    """Atomically persist the first edited client-only working copy."""
    _assert_type(item_type_code)
    _validate(values, item_type_code)
    with engine.begin() as conn:
        published = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='PUBLISHED' FOR UPDATE"), {"type": item_type_code}).mappings().first()
        if base_source == "INITIAL":
            if published is not None:
                raise TemplateDraftError("TEMPLATE_INITIAL_CONFLICT", "A published template now exists.", conflict=True)
        elif base_source == "PUBLISHED":
            if published is None:
                raise TemplateDraftError("TEMPLATE_PUBLISHED_CONFLICT", "Published template has changed.", conflict=True)
            if int(published["template_version_id"]) != base_published_template_version_id or int(published["revision"]) != base_published_revision:
                raise TemplateDraftError("TEMPLATE_PUBLISHED_CONFLICT", "Published template has changed.", conflict=True)
        else:
            raise TemplateDraftError("TEMPLATE_BASE_SOURCE_INVALID", "Invalid editor base.")
        if published is not None and all(published[field] == values[field] for field in TEXT_FIELDS):
            raise TemplateDraftError("TEMPLATE_DRAFT_IDENTICAL_TO_PUBLISHED", "Draft must differ from the published template.")
        existing = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='DRAFT' FOR UPDATE"), {"type": item_type_code}).mappings().first()
        if existing is not None:
            raise TemplateDraftError("TEMPLATE_DRAFT_ALREADY_EXISTS", "A draft already exists.", conflict=True)
        row = conn.execute(text("""
            INSERT INTO public.personnel_order_template_versions
            (item_type_code, version_number, status, title_ru, title_kk, preamble_ru, preamble_kk, body_template_ru, body_template_kk, basis_template_ru, basis_template_kk, created_by_user_id, updated_by_user_id)
            VALUES (:type, (SELECT COALESCE(MAX(version_number), 0) + 1 FROM public.personnel_order_template_versions WHERE item_type_code=:type), 'DRAFT', :title_ru, :title_kk, :preamble_ru, :preamble_kk, :body_template_ru, :body_template_kk, :basis_template_ru, :basis_template_kk, :actor, :actor)
            RETURNING *
        """), {**{field: values[field] for field in TEXT_FIELDS}, "type": item_type_code, "actor": actor_user_id}).mappings().one()
    return _row(row)


def publish_draft(item_type_code: str, expected_revision: int, actor_user_id: int) -> dict[str, Any]:
    _assert_type(item_type_code)
    with engine.begin() as conn:
        draft = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='DRAFT' FOR UPDATE"), {"type": item_type_code}).mappings().first()
        if draft is None: raise TemplateDraftError("TEMPLATE_DRAFT_NOT_FOUND", "Черновая версия не создана.")
        if int(draft["revision"]) != expected_revision: raise TemplateDraftError("TEMPLATE_REVISION_CONFLICT", "Черновик изменён другим пользователем.", conflict=True)
        if item_type_code == "LEAVE.CHILDCARE.GRANT":
            _validate({field: draft[field] for field in TEXT_FIELDS}, item_type_code)
        published = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='PUBLISHED' FOR UPDATE"), {"type": item_type_code}).mappings().first()
        if published is not None and all(draft[field] == published[field] for field in TEXT_FIELDS):
            raise TemplateDraftError("TEMPLATE_DRAFT_IDENTICAL_TO_PUBLISHED", "Draft must differ from the published template.")
        conn.execute(text("UPDATE public.personnel_order_template_versions SET status='ARCHIVED', updated_at=now() WHERE item_type_code=:type AND status='PUBLISHED'"), {"type": item_type_code})
        row = conn.execute(text("UPDATE public.personnel_order_template_versions SET status='PUBLISHED', published_at=now(), published_by_user_id=:actor, updated_by_user_id=:actor, updated_at=now() WHERE template_version_id=:id RETURNING *"), {"actor": actor_user_id, "id": draft["template_version_id"]}).mappings().one()
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
    spec = get_personnel_order_template_spec(item_type_code)
    samples = {
        "employee.full_name": "[[ФИО сотрудника]]", "position.title_ru": "[[Должность]]", "position.title_kk": "[[Лауазым]]", "position.document_nominative_ru": "[[Должность в именительном падеже]]", "org_unit.title_ru": "[[Подразделение]]", "org_unit.title_kk": "[[Бөлімше]]",
        "org_unit.document_genitive_kk": "[[Бөлімшенің құжаттық нысаны]]", "position.document_possessive_kk": "[[Лауазымның құжаттық нысаны]]", "employee.full_name_dative_ru": "[[ФИО сотрудника в дательном падеже]]", "employee.full_name_dative_kk": "[[Қызметкердің барыс септігі]]", "employee.full_name_genitive_kk": "[[Қызметкердің ілік септігі]]",
        "leave.start_ru": "[[Дата начала отпуска]]", "leave.start_kk": "[[Демалыстың басталу күні]]", "leave.end_ru": "[[Дата окончания отпуска]]", "leave.end_kk": "[[Демалыстың аяқталу күні]]", "leave.days": "[[Количество дней]]", "leave.period_clause_ru": "7 июля 2026 года", "leave.period_clause_kk": "2026 жылғы 7 шілде күніне",
        "basis.application_date_ru": " от [[Дата заявления]]", "basis.application_date_kk": "", "basis.application_number_suffix": " № [[Номер заявления]]",
        "rate": "[[Ставка]]",
        "termination.reason": "[[Причина увольнения]]", "termination.unused_leave_days": "[[Количество дней неиспользованного отпуска]]", "effective_date_local": "[[Дата увольнения]]", "concurrent.rate": "[[Ставка совмещения]]", "total.rate": "[[Итоговая ставка]]", "remaining.rate": "[[Остающаяся ставка]]",
    }
    locale_samples = {
        "ru": {**samples, "effective_date": "[[Дата выхода]]", "effective_date_local": "[[Дата выхода]]", "basis": "[[Основание]]"},
        "kk": {**samples, "employee.full_name": "[[Қызметкердің аты-жөні]]", "position.title_ru": "[[Лауазым]]", "position.title_kk": "[[Лауазым]]", "org_unit.title_ru": "[[Бөлімше]]", "org_unit.title_kk": "[[Бөлімше]]", "leave.days": "[[Күн саны]]", "basis.application_date_kk": " [[Өтініш күні]]", "basis.application_number_suffix": " № [[Өтініш нөмірі]]", "effective_date": "[[Жұмысқа шығу күні]]", "effective_date_local": "[[Жұмыстан босату күні]]", "rate": "[[Мөлшерлеме]]", "basis": "[[Негіз]]", "termination.reason": "[[Жұмыстан босату себебі]]", "termination.unused_leave_days": "[[Пайдаланылмаған демалыс күндерінің саны]]", "concurrent.rate": "[[Қоса атқару мөлшерлемесі]]", "total.rate": "[[Жалпы мөлшерлеме]]", "remaining.rate": "[[Қалған мөлшерлеме]]"},
    }
    for locale, overrides in spec.preview_context.items():
        locale_samples[locale].update(overrides)
    if item_type_code == "LEAVE.CHILDCARE.GRANT":
        for samples in locale_samples.values():
            samples.update({"employee.full_name_genitive_ru": "[[ФИО в родительном падеже]]", "basis.birth_certificate_date_ru": "[[Дата выдачи свидетельства]]", "basis.birth_certificate_date_kk": "[[Куәліктің берілген күні]]", "basis.birth_certificate_number": "[[Номер свидетельства]]"})
    def render(value: str, locale: str) -> str:
        result = _TOKEN.sub(lambda m: locale_samples[locale][m.group(1)], value)
        if item_type_code == "LEAVE.CHILDCARE.GRANT":
            from app.services.personnel_order_childcare_contract import without_directive
            result = without_directive(result)
        return result
    return {"ru": {"title": render(values["title_ru"], "ru"), "preamble": render(values["preamble_ru"], "ru"), "directive": "ПРИКАЗЫВАЮ:", "body": render(values["body_template_ru"], "ru"), "basis": render(values["basis_template_ru"], "ru")}, "kk": {"title": render(values["title_kk"], "kk"), "preamble": render(values["preamble_kk"], "kk"), "directive": "БҰЙЫРАМЫН:", "body": render(values["body_template_kk"], "kk"), "basis": render(values["basis_template_kk"], "kk")}}
