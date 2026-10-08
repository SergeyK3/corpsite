"""Typed draft editor for the first editable personnel-order template."""
from __future__ import annotations

import re
from functools import wraps
from inspect import signature
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

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


def independent_template_schema_available() -> bool:
    with engine.connect() as conn:
        return bool(conn.execute(text("SELECT to_regclass('public.personnel_order_templates') IS NOT NULL")).scalar_one())


def require_independent_template_schema() -> None:
    if not independent_template_schema_available():
        raise TemplateDraftError("TEMPLATE_SCHEMA_REQUIRED", "Для независимых вариантов и отзыва требуется согласованное обновление структуры БД до hrrecall001. Прежние шаблоны доступны в редакторе; БД автоматически не изменяется.")


def compatible_template_schema(function):
    """Keep the existing per-type editor operational before stage-3 migration."""
    @wraps(function)
    def compatible(*args, **kwargs):
        if independent_template_schema_available():
            return function(*args, **kwargs)
        arguments=signature(function).bind(*args, **kwargs)
        arguments.apply_defaults()
        values=dict(arguments.arguments)
        if values.pop('template_id',None) is not None:
            require_independent_template_schema()
        if values.get('item_type_code') == 'LEAVE.ANNUAL.RECALL' and function.__name__ in {'create_draft_from_working_copy','save_draft','publish_draft'}:
            require_independent_template_schema()
        from app.services import personnel_order_template_legacy_service as legacy
        return getattr(legacy,function.__name__)(**values)
    return compatible


def _row(row: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: row[key] for key in (
        "template_version_id", "item_type_code", "version_number", "status", "revision",
        "title_ru", "title_kk", "preamble_ru", "preamble_kk", "body_template_ru", "body_template_kk",
        "basis_template_ru", "basis_template_kk", "based_on_built_in", "created_at", "updated_at",
    )}
    result["template_id"] = row.get("template_id")
    result["published_at"] = row.get("published_at")
    result["published_by_user_id"] = row.get("published_by_user_id")
    return result


def _assert_type(item_type_code: str) -> None:
    try:
        get_personnel_order_template_spec(item_type_code)
    except ValueError:
        raise TemplateDraftError("TEMPLATE_EDITOR_NOT_AVAILABLE", "Редактор для этого типа недоступен.")


def _resolve_template(conn: Any, item_type_code: str, template_id: int | None,
                      *, create: bool = False, lock: bool = False) -> int:
    clause = "template_id=:id" if template_id is not None else "is_default"
    row = conn.execute(text(f"SELECT template_id FROM public.personnel_order_templates WHERE item_type_code=:type AND {clause}" + (" FOR UPDATE" if lock else "")),
                       {"type": item_type_code, "id": template_id}).first()
    if row:
        return int(row[0])
    if template_id is not None:
        raise TemplateDraftError("TEMPLATE_NOT_FOUND", "Шаблон не найден для выбранного вида приказа.")
    if not create:
        return 0
    initial = get_personnel_order_template_spec(item_type_code).initial_texts
    return int(conn.execute(text("""
        INSERT INTO public.personnel_order_templates(item_type_code,name_ru,name_kk,is_default)
        VALUES(:type,:ru,:kk,TRUE)
        ON CONFLICT(item_type_code) WHERE is_default DO UPDATE SET is_default=TRUE
        RETURNING template_id
    """), {"type": item_type_code, "ru": initial["title_ru"], "kk": initial["title_kk"]}).scalar_one())


def list_templates(item_type_code: str, *, published_only: bool = False) -> list[dict[str, Any]]:
    _assert_type(item_type_code)
    require_independent_template_schema()
    with engine.connect() as conn:
        rows = conn.execute(text("""
          SELECT t.*, p.template_version_id, p.version_number, p.title_ru, p.title_kk,
                 d.template_version_id draft_version_id
          FROM public.personnel_order_templates t
          LEFT JOIN public.personnel_order_template_versions p ON p.template_id=t.template_id AND p.status='PUBLISHED'
          LEFT JOIN public.personnel_order_template_versions d ON d.template_id=t.template_id AND d.status='DRAFT'
          WHERE t.item_type_code=:type AND (:published_only=FALSE OR p.template_version_id IS NOT NULL)
            AND (t.is_default OR NOT EXISTS(SELECT 1 FROM public.personnel_order_template_versions v WHERE v.template_id=t.template_id)
                 OR EXISTS(SELECT 1 FROM public.personnel_order_template_versions v WHERE v.template_id=t.template_id AND v.status IN ('DRAFT','PUBLISHED')))
          ORDER BY t.is_default DESC,t.template_id
        """), {"type": item_type_code, "published_only": published_only}).mappings().all()
    return [dict(row) for row in rows]


def list_versions(item_type_code: str, template_id: int) -> list[dict[str, Any]]:
    _assert_type(item_type_code)
    require_independent_template_schema()
    with engine.connect() as conn:
        scope = _resolve_template(conn, item_type_code, template_id)
        rows = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE template_id=:id ORDER BY version_number DESC"), {"id": scope}).mappings().all()
    return [_row(row) for row in rows]


def copy_template(item_type_code: str, source_version_id: int | None, name_ru: str, name_kk: str,
                  actor_user_id: int, expected_revision: int | None, *, base_source: str = "VERSION", source_type_code: str | None = None) -> dict[str, Any]:
    _assert_type(item_type_code)
    require_independent_template_schema()
    source_type_code = source_type_code or item_type_code
    _assert_type(source_type_code)
    names = {"ru": name_ru.strip(), "kk": name_kk.strip()}
    if not all(names.values()) or any(len(v) > 200 for v in names.values()):
        raise TemplateDraftError("TEMPLATE_NAME_REQUIRED", "Укажите названия варианта RU и KZ (до 200 символов).")
    with engine.begin() as conn:
        if base_source == "INITIAL" and source_version_id is None and expected_revision is None:
            values = dict(get_personnel_order_template_spec(source_type_code).initial_texts)
            # Give the existing built-in template its default identity, without
            # creating/changing any of its versions or content.
            _resolve_template(conn, source_type_code, None, create=True, lock=True)
        elif base_source == "VERSION" and source_version_id is not None and expected_revision is not None:
            source = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE template_version_id=:id AND item_type_code=:type FOR SHARE"), {"id": source_version_id, "type": source_type_code}).mappings().first()
            if source is None:
                raise TemplateDraftError("TEMPLATE_VERSION_NOT_FOUND", "Исходная версия не найдена.")
            if int(source["revision"]) != expected_revision:
                raise TemplateDraftError("TEMPLATE_REVISION_CONFLICT", "Исходная версия изменена. Обновите страницу.", conflict=True)
            values = {field: source[field] for field in TEXT_FIELDS}
        else:
            raise TemplateDraftError("TEMPLATE_BASE_SOURCE_INVALID", "Некорректный источник копии.")
        # Keep copied tokens verbatim, including incompatible tokens in a draft.
        # Save, preview and publication retain full target-spec validation.
        _validate(values, item_type_code, check_variables=False)
        new_id = conn.execute(text("""
          INSERT INTO public.personnel_order_templates(item_type_code,name_ru,name_kk,created_by_user_id,copied_from_template_version_id)
          VALUES(:type,:ru,:kk,:actor,:source) RETURNING template_id
        """), {"type": item_type_code, **names, "actor": actor_user_id, "source": source_version_id}).scalar_one()
        row = conn.execute(text("""
          INSERT INTO public.personnel_order_template_versions(template_id,item_type_code,version_number,status,
            title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk,
            based_on_built_in,created_by_user_id,updated_by_user_id)
          VALUES(:template,:type,1,'DRAFT',:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,
            :basis_template_ru,:basis_template_kk,:built_in,:actor,:actor) RETURNING *
        """), {**values, "template": new_id, "type": item_type_code, "actor": actor_user_id, "built_in": base_source == "INITIAL"}).mappings().one()
    return {**_row(row), "name_ru": names["ru"], "name_kk": names["kk"]}


def remove_template(item_type_code: str, template_id: int, name_ru: str, name_kk: str,
                    actor_user_id: int, *, archive: bool = False) -> dict[str, Any]:
    """Delete only unreferenced independent copies; archive keeps every identity."""
    _assert_type(item_type_code)
    require_independent_template_schema()
    try:
        with engine.begin() as conn:
            template = conn.execute(text("SELECT * FROM public.personnel_order_templates WHERE template_id=:id AND item_type_code=:type FOR UPDATE"),
                {"id": template_id, "type": item_type_code}).mappings().first()
            if template is None:
                raise TemplateDraftError("TEMPLATE_NOT_FOUND", "Шаблон не найден.")
            if template["is_default"]:
                raise TemplateDraftError("TEMPLATE_DEFAULT_PROTECTED", "Встроенную основу нельзя удалить или архивировать.")
            if template["name_ru"] != name_ru or template["name_kk"] != name_kk:
                raise TemplateDraftError("TEMPLATE_NAME_CONFLICT", "Название шаблона изменилось. Обновите список.", conflict=True)
            conn.execute(text("SELECT template_version_id FROM public.personnel_order_template_versions WHERE template_id=:id FOR UPDATE"), {"id": template_id}).all()
            if archive:
                conn.execute(text("UPDATE public.personnel_order_template_versions SET status='ARCHIVED',updated_at=now(),updated_by_user_id=:actor WHERE template_id=:id AND status IN ('DRAFT','PUBLISHED')"), {"id": template_id, "actor": actor_user_id})
            else:
                used = conn.execute(text("""
                    SELECT EXISTS(SELECT 1 FROM public.personnel_orders o JOIN public.personnel_order_template_versions v ON v.template_version_id=o.selected_template_version_id WHERE v.template_id=:id)
                    OR EXISTS(SELECT 1 FROM public.personnel_order_template_applications a JOIN public.personnel_order_template_versions v ON v.template_version_id=a.template_version_id WHERE v.template_id=:id)
                    OR EXISTS(SELECT 1 FROM public.personnel_order_templates t JOIN public.personnel_order_template_versions v ON v.template_version_id=t.copied_from_template_version_id WHERE v.template_id=:id)
                """), {"id": template_id}).scalar_one()
                if used:
                    raise TemplateDraftError("TEMPLATE_IN_USE", "Шаблон использован. Можно архивировать его с сохранением истории.", conflict=True)
                conn.execute(text("DELETE FROM public.personnel_order_template_versions WHERE template_id=:id"), {"id": template_id})
                conn.execute(text("DELETE FROM public.personnel_order_templates WHERE template_id=:id"), {"id": template_id})
        return {"template_id": template_id, "action": "ARCHIVED" if archive else "DELETED"}
    except IntegrityError as exc:
        raise TemplateDraftError("TEMPLATE_IN_USE", "Шаблон использован. Можно архивировать его с сохранением истории.", conflict=True) from exc


def change_template_type(item_type_code: str, template_id: int, target_type_code: str,
                         expected_template_version_id: int, expected_revision: int,
                         actor_user_id: int) -> dict[str, Any]:
    """Rebind only an independent, never-used, single-version draft in place."""
    _assert_type(item_type_code)
    require_independent_template_schema()
    _assert_type(target_type_code)
    with engine.begin() as conn:
        template = conn.execute(text("SELECT * FROM personnel_order_templates WHERE template_id=:id AND item_type_code=:type FOR UPDATE"), {"id": template_id, "type": item_type_code}).mappings().first()
        if template is None:
            raise TemplateDraftError("TEMPLATE_NOT_FOUND", "Шаблон не найден / Үлгі табылмады.")
        if template['is_default']:
            raise TemplateDraftError("TEMPLATE_DEFAULT_PROTECTED", "Вид встроенной основы менять нельзя / Кірістірілген үлгінің түрін өзгертуге болмайды.")
        versions = conn.execute(text("SELECT * FROM personnel_order_template_versions WHERE template_id=:id FOR UPDATE"), {"id": template_id}).mappings().all()
        if len(versions) != 1 or versions[0]['status'] != 'DRAFT' or versions[0]['published_at'] is not None:
            raise TemplateDraftError("TEMPLATE_TYPE_CHANGE_UNAVAILABLE", "Вид можно менять только у самостоятельного черновика без истории публикаций / Түрді тек жарияланбаған дербес жобада өзгертуге болады.", conflict=True)
        draft = versions[0]
        if draft['template_version_id'] != expected_template_version_id or draft['revision'] != expected_revision:
            raise TemplateDraftError("TEMPLATE_REVISION_CONFLICT", "Черновик изменён. Обновите страницу / Жоба өзгерді. Бетті жаңартыңыз.", conflict=True)
        used = conn.execute(text("""
            SELECT EXISTS(SELECT 1 FROM personnel_orders WHERE selected_template_version_id=:version)
            OR EXISTS(SELECT 1 FROM personnel_order_template_applications WHERE template_version_id=:version)
            OR EXISTS(SELECT 1 FROM personnel_order_templates WHERE copied_from_template_version_id=:version)
        """), {"version": expected_template_version_id}).scalar_one()
        if used:
            raise TemplateDraftError("TEMPLATE_IN_USE", "Шаблон использован; изменение вида недоступно / Үлгі қолданылған; түрін өзгертуге болмайды.", conflict=True)
        if item_type_code == target_type_code:
            return {**_row(draft), 'name_ru': template['name_ru'], 'name_kk': template['name_kk']}
        # Keep incompatible tokens visible for correction; publication still
        # enforces the complete target contract. Text is never rewritten here.
        _validate({field: draft[field] for field in TEXT_FIELDS}, target_type_code, check_variables=False, require_complete=False)
        conn.execute(text('SET CONSTRAINTS fk_personnel_template_version_template DEFERRED'))
        conn.execute(text('UPDATE personnel_order_templates SET item_type_code=:target WHERE template_id=:id'), {"target": target_type_code, "id": template_id})
        row = conn.execute(text('UPDATE personnel_order_template_versions SET item_type_code=:target,revision=revision+1,updated_at=now(),updated_by_user_id=:actor WHERE template_version_id=:version RETURNING *'), {"target": target_type_code, "actor": actor_user_id, "version": expected_template_version_id}).mappings().one()
        conn.execute(text('SET CONSTRAINTS fk_personnel_template_version_template IMMEDIATE'))
    return {**_row(row), 'name_ru': template['name_ru'], 'name_kk': template['name_kk']}


def _validate(values: Mapping[str, str], item_type_code: str = EDITABLE_TYPE, *, check_variables: bool = True, require_complete: bool = True) -> None:
    _assert_type(item_type_code)
    spec = get_personnel_order_template_spec(item_type_code)
    variables = set(spec.allowed_variables)
    for field, value in values.items():
        if not isinstance(value, str) or (require_complete and not value.strip()):
            raise TemplateDraftError("TEMPLATE_TEXT_REQUIRED", f"{field} обязателен.")
        if _FORBIDDEN.search(value):
            raise TemplateDraftError("TEMPLATE_TEXT_UNSAFE", "HTML, скрипты и выражения запрещены.")
        if not check_variables:
            continue
        unknown = {match.group(1) for match in _TOKEN.finditer(value)} - variables
        if unknown:
            raise TemplateDraftError("TEMPLATE_VARIABLE_UNKNOWN", "Неизвестная переменная: " + ", ".join(sorted(unknown)))
    if not check_variables or not require_complete:
        return
    for field, required in spec.required_variables.items():
        absent = [code for code in required if f"{{{{{code}}}}}" not in values[field]]
        if absent:
            raise TemplateDraftError("TEMPLATE_VARIABLE_REQUIRED", f"В {field} отсутствуют обязательные переменные: {', '.join(absent)}")


@compatible_template_schema
def get_draft(item_type_code: str, template_id: int | None = None) -> dict[str, Any] | None:
    _assert_type(item_type_code)
    with engine.connect() as conn:
        scope = _resolve_template(conn, item_type_code, template_id)
        row = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE template_id=:template AND status='DRAFT'"), {"template": scope}).mappings().first()
    return _row(row) if row else None


@compatible_template_schema
def get_published(item_type_code: str, template_id: int | None = None) -> dict[str, Any] | None:
    """Read the immutable published snapshot without creating a DRAFT."""
    _assert_type(item_type_code)
    with engine.connect() as conn:
        scope = _resolve_template(conn, item_type_code, template_id)
        row = conn.execute(
            text("SELECT * FROM public.personnel_order_template_versions WHERE template_id=:template AND status='PUBLISHED'"),
            {"template": scope},
        ).mappings().first()
    return _row(row) if row else None


@compatible_template_schema
def get_editor_base(item_type_code: str, template_id: int | None = None) -> dict[str, Any]:
    """Read-only source for a client working copy; never creates a DRAFT."""
    published = get_published(item_type_code, template_id)
    if published is not None:
        # The editor-base response is intentionally narrower than a version
        # response.  In particular, do not leak DRAFT/PUBLISHED lifecycle
        # metadata into a client-only working copy (and keep it compatible
        # with the strict editor-base response schema).
        return {
            "source": "PUBLISHED", "template_id": published["template_id"],
            "item_type_code": published["item_type_code"],
            "template_version_id": published["template_version_id"],
            "version_number": published["version_number"],
            "revision": published["revision"],
            **{field: published[field] for field in TEXT_FIELDS},
        }
    return {"source": "INITIAL", "item_type_code": item_type_code, "template_id": template_id,
            "template_version_id": None, "version_number": None, "revision": None,
            **dict(get_personnel_order_template_spec(item_type_code).initial_texts)}


@compatible_template_schema
def create_draft_from_working_copy(
    item_type_code: str,
    base_source: str,
    base_published_template_version_id: int | None,
    base_published_revision: int | None,
    values: Mapping[str, str],
    actor_user_id: int,
    template_id: int | None = None,
) -> dict[str, Any]:
    """Atomically persist the first edited client-only working copy."""
    _assert_type(item_type_code)
    _validate(values, item_type_code)
    with engine.begin() as conn:
        scope = _resolve_template(conn, item_type_code, template_id, create=True, lock=True)
        published = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE template_id=:template AND status='PUBLISHED' FOR UPDATE"), {"template": scope}).mappings().first()
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
        existing = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE template_id=:template AND status='DRAFT' FOR UPDATE"), {"template": scope}).mappings().first()
        if existing is not None:
            raise TemplateDraftError("TEMPLATE_DRAFT_ALREADY_EXISTS", "A draft already exists.", conflict=True)
        row = conn.execute(text("""
            INSERT INTO public.personnel_order_template_versions
            (template_id, item_type_code, version_number, status, title_ru, title_kk, preamble_ru, preamble_kk, body_template_ru, body_template_kk, basis_template_ru, basis_template_kk, created_by_user_id, updated_by_user_id)
            VALUES (:template, :type, (SELECT COALESCE(MAX(version_number), 0) + 1 FROM public.personnel_order_template_versions WHERE template_id=:template), 'DRAFT', :title_ru, :title_kk, :preamble_ru, :preamble_kk, :body_template_ru, :body_template_kk, :basis_template_ru, :basis_template_kk, :actor, :actor)
            RETURNING *
        """), {**{field: values[field] for field in TEXT_FIELDS}, "type": item_type_code, "template": scope, "actor": actor_user_id}).mappings().one()
    return _row(row)


@compatible_template_schema
def publish_draft(item_type_code: str, expected_revision: int, actor_user_id: int, template_id: int | None = None) -> dict[str, Any]:
    _assert_type(item_type_code)
    with engine.begin() as conn:
        scope = _resolve_template(conn, item_type_code, template_id, create=True, lock=True)
        draft = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE template_id=:template AND status='DRAFT' FOR UPDATE"), {"template": scope}).mappings().first()
        if draft is None: raise TemplateDraftError("TEMPLATE_DRAFT_NOT_FOUND", "Черновая версия не создана.")
        if int(draft["revision"]) != expected_revision: raise TemplateDraftError("TEMPLATE_REVISION_CONFLICT", "Черновик изменён другим пользователем.", conflict=True)
        _validate({field: draft[field] for field in TEXT_FIELDS}, item_type_code)
        published = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE template_id=:template AND status='PUBLISHED' FOR UPDATE"), {"template": scope}).mappings().first()
        if published is not None and all(draft[field] == published[field] for field in TEXT_FIELDS):
            raise TemplateDraftError("TEMPLATE_DRAFT_IDENTICAL_TO_PUBLISHED", "Draft must differ from the published template.")
        conn.execute(text("UPDATE public.personnel_order_template_versions SET status='ARCHIVED', updated_at=now() WHERE template_id=:template AND status='PUBLISHED'"), {"template": scope})
        row = conn.execute(text("UPDATE public.personnel_order_template_versions SET status='PUBLISHED', published_at=now(), published_by_user_id=:actor, updated_by_user_id=:actor, updated_at=now() WHERE template_version_id=:id RETURNING *"), {"actor": actor_user_id, "id": draft["template_version_id"]}).mappings().one()
    return _row(row)


@compatible_template_schema
def save_draft(item_type_code: str, expected_revision: int, values: Mapping[str, str], actor_user_id: int, template_id: int | None = None, *, expected_template_version_id: int | None = None) -> dict[str, Any]:
    # A draft may be incomplete or carry tokens still being edited. Safety and
    # optimistic revision checks remain mandatory; publication validates fully.
    _assert_type(item_type_code); _validate(values, item_type_code, check_variables=False, require_complete=False)
    with engine.begin() as conn:
        scope = _resolve_template(conn, item_type_code, template_id, create=True, lock=True)
        current = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE template_id=:template AND status='DRAFT' FOR UPDATE"), {"template": scope}).mappings().first()
        if not current:
            raise TemplateDraftError("TEMPLATE_DRAFT_NOT_FOUND", "Черновая версия не создана.")
        if int(current["revision"]) != expected_revision:
            raise TemplateDraftError("TEMPLATE_REVISION_CONFLICT", "Черновик изменён другим пользователем.", conflict=True)
        if expected_template_version_id is not None and int(current["template_version_id"]) != expected_template_version_id:
            raise TemplateDraftError("TEMPLATE_REVISION_CONFLICT", "Открыта другая версия черновика. Обновите редактор.", conflict=True)
        if all(current[key] == values[key] for key in values): return _row(current)
        row = conn.execute(text("""
            UPDATE public.personnel_order_template_versions SET title_ru=:title_ru, title_kk=:title_kk, preamble_ru=:preamble_ru, preamble_kk=:preamble_kk,
            body_template_ru=:body_template_ru, body_template_kk=:body_template_kk, basis_template_ru=:basis_template_ru, basis_template_kk=:basis_template_kk,
            revision=revision+1, updated_by_user_id=:actor, updated_at=now() WHERE template_version_id=:id RETURNING *
        """), {**values, "actor": actor_user_id, "id": current["template_version_id"]}).mappings().one()
    return _row(row)


def preview_draft(item_type_code: str, values: Mapping[str, str]) -> dict[str, Any]:
    _assert_type(item_type_code); _validate(values, item_type_code, require_complete=False)
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
