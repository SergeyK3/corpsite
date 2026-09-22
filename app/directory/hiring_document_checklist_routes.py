"""Editable, organization-wide hiring document checklist."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.directory.common import as_http500
from app.directory.rbac import require_personnel_admin_or_403
from app.security.directory_scope import is_privileged

router = APIRouter(prefix="/hiring-document-checklist", tags=["personnel-applications"])
_CODE = "HIRING_DOCUMENT_CHECKLIST"

_DEFAULT_CONTENT = {
    "items": [
        "Документ, удостоверяющий личность.",
        "Документ об образовании и квалификации — диплом, сертификат, лицензия или иной документ, если работа требует соответствующих знаний, квалификации или подготовки.",
        "Документ, подтверждающий трудовую деятельность — для лиц, имеющих трудовой стаж.",
        "Документ о прохождении предварительного медицинского осмотра — если его прохождение обязательно для соответствующей должности.",
        "Справка о наличии либо отсутствии судимости — в случаях, предусмотренных законодательством. Справку можно получить на портале eGov.kz.",
    ],
    "note": "Точный перечень документов определяется в зависимости от должности и сообщается сотрудником отдела кадров.",
    "show_additional_notes": True,
    "additional_notes_lines": 3,
}
_DEFAULT_TITLE = "Краткий перечень документов при приёме на работу"


class HiringDocumentChecklistOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    items: list[str]
    note: str
    show_additional_notes: bool
    additional_notes_lines: int
    can_edit: bool


class HiringDocumentChecklistUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    items: list[str] = Field(min_length=1, max_length=30)
    note: str = Field(min_length=1, max_length=4000)
    show_additional_notes: bool = True
    additional_notes_lines: int = Field(default=3, ge=1, le=10)

    @field_validator("title", "note")
    @classmethod
    def non_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text must not be blank.")
        return value

    @field_validator("items")
    @classmethod
    def non_blank_items(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item or len(item) > 1000 for item in cleaned):
            raise ValueError("Each item must contain 1 to 1000 characters.")
        return cleaned


def _can_edit(user: dict[str, Any]) -> bool:
    return is_privileged(user) or str(user.get("role_code") or "").upper() == "HR_HEAD"


def _row_to_out(row: Any | None, *, can_edit: bool) -> HiringDocumentChecklistOut:
    content = dict(row["content"]) if row else _DEFAULT_CONTENT
    return HiringDocumentChecklistOut(
        title=str(row["title"]) if row else _DEFAULT_TITLE,
        items=list(content.get("items") or _DEFAULT_CONTENT["items"]),
        note=str(content.get("note") or _DEFAULT_CONTENT["note"]),
        show_additional_notes=bool(content.get("show_additional_notes", True)),
        additional_notes_lines=int(content.get("additional_notes_lines") or 3),
        can_edit=can_edit,
    )


@router.get("", response_model=HiringDocumentChecklistOut)
def get_hiring_document_checklist(user: dict[str, Any] = Depends(get_current_user)) -> HiringDocumentChecklistOut:
    require_personnel_admin_or_403(user)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT title, content FROM public.hiring_document_checklists WHERE code = :code"),
                {"code": _CODE},
            ).mappings().first()
        return _row_to_out(row, can_edit=_can_edit(user))
    except Exception as exc:
        raise as_http500(exc)


@router.put("", response_model=HiringDocumentChecklistOut)
def put_hiring_document_checklist(
    body: HiringDocumentChecklistUpdateIn,
    user: dict[str, Any] = Depends(get_current_user),
) -> HiringDocumentChecklistOut:
    require_personnel_admin_or_403(user)
    if not _can_edit(user):
        raise HTTPException(status_code=403, detail="Hiring document checklist editing requires HR_HEAD role.")
    content = {
        "items": body.items,
        "note": body.note,
        "show_additional_notes": body.show_additional_notes,
        "additional_notes_lines": body.additional_notes_lines,
    }
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO public.hiring_document_checklists (code, title, content)
                    VALUES (:code, :title, CAST(:content AS jsonb))
                    ON CONFLICT (code) DO UPDATE
                    SET title = EXCLUDED.title, content = EXCLUDED.content, updated_at = now()
                    """
                ),
                {"code": _CODE, "title": body.title, "content": json.dumps(content)},
            )
        return HiringDocumentChecklistOut(title=body.title, **content, can_edit=True)
    except Exception as exc:
        raise as_http500(exc)
