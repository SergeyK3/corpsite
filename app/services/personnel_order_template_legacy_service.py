"""Compatibility with the existing per-type schema; never creates schema or copies."""
from __future__ import annotations
from typing import Any, Mapping
from sqlalchemy import text
from app.db.engine import engine
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_template_draft_service import TEXT_FIELDS, _row, _assert_type, _validate, TemplateDraftError

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
        _validate({field: draft[field] for field in TEXT_FIELDS}, item_type_code)
        published = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='PUBLISHED' FOR UPDATE"), {"type": item_type_code}).mappings().first()
        if published is not None and all(draft[field] == published[field] for field in TEXT_FIELDS):
            raise TemplateDraftError("TEMPLATE_DRAFT_IDENTICAL_TO_PUBLISHED", "Draft must differ from the published template.")
        conn.execute(text("UPDATE public.personnel_order_template_versions SET status='ARCHIVED', updated_at=now() WHERE item_type_code=:type AND status='PUBLISHED'"), {"type": item_type_code})
        row = conn.execute(text("UPDATE public.personnel_order_template_versions SET status='PUBLISHED', published_at=now(), published_by_user_id=:actor, updated_by_user_id=:actor, updated_at=now() WHERE template_version_id=:id RETURNING *"), {"actor": actor_user_id, "id": draft["template_version_id"]}).mappings().one()
    return _row(row)


def save_draft(item_type_code: str, expected_revision: int, values: Mapping[str, str], actor_user_id: int, expected_template_version_id: int | None = None) -> dict[str, Any]:
    _assert_type(item_type_code); _validate(values, item_type_code, check_variables=False, require_complete=False)
    with engine.begin() as conn:
        current = conn.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='DRAFT' FOR UPDATE"), {"type": item_type_code}).mappings().first()
        if not current:
            raise TemplateDraftError("TEMPLATE_DRAFT_NOT_FOUND", "Черновая версия не создана.")
        if int(current["revision"]) != expected_revision:
            raise TemplateDraftError("TEMPLATE_REVISION_CONFLICT", "Черновик изменён другим пользователем.", conflict=True)
        if expected_template_version_id is not None and current["template_version_id"] != expected_template_version_id:
            raise TemplateDraftError("TEMPLATE_REVISION_CONFLICT", "Opened draft version changed.", conflict=True)
        if all(current[key] == values[key] for key in values): return _row(current)
        row = conn.execute(text("""
            UPDATE public.personnel_order_template_versions SET title_ru=:title_ru, title_kk=:title_kk, preamble_ru=:preamble_ru, preamble_kk=:preamble_kk,
            body_template_ru=:body_template_ru, body_template_kk=:body_template_kk, basis_template_ru=:basis_template_ru, basis_template_kk=:basis_template_kk,
            revision=revision+1, updated_by_user_id=:actor, updated_at=now() WHERE template_version_id=:id RETURNING *
        """), {**values, "actor": actor_user_id, "id": current["template_version_id"]}).mappings().one()
    return _row(row)
