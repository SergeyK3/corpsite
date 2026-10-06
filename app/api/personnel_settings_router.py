"""Shared display language, independent from personnel document languages."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.auth import get_current_user
from app.db.engine import engine

router = APIRouter(prefix="/personnel/settings", tags=["personnel-settings"])


class PersonnelSettings(BaseModel):
    language: Literal["kk", "ru"]
    can_edit: bool = False


class PersonnelSettingsUpdate(BaseModel):
    language: Literal["kk", "ru"]


def can_edit_settings(user: dict) -> bool:
    return str(user.get("role_code") or "").upper() in {"HR_HEAD", "ADMIN"}


def settings_schema_unavailable(error: ProgrammingError):
    if getattr(error.orig, "pgcode", None) == "42P01":
        raise HTTPException(status_code=503, detail={
            "code": "PERSONNEL_SETTINGS_SCHEMA_REQUIRED",
            "message": "Настройка языка пока недоступна. Обратитесь к администратору.",
        }) from error
    raise error


@router.get("", response_model=PersonnelSettings)
def read_settings(response: Response, user: dict = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    try:
        with engine.connect() as conn:
            language = conn.execute(text("SELECT language FROM public.personnel_section_settings WHERE settings_id=1")).scalar_one()
    except ProgrammingError as error:
        settings_schema_unavailable(error)
    return PersonnelSettings(language=language, can_edit=can_edit_settings(user))


@router.put("", response_model=PersonnelSettings)
def update_settings(payload: PersonnelSettingsUpdate, response: Response, user: dict = Depends(get_current_user)):
    if not can_edit_settings(user):
        raise HTTPException(status_code=403, detail="HR_HEAD or ADMIN role required.")
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE public.personnel_section_settings SET language=:language WHERE settings_id=1"), {"language": payload.language})
    except ProgrammingError as error:
        settings_schema_unavailable(error)
    response.headers["Cache-Control"] = "no-store"
    return PersonnelSettings(language=payload.language, can_edit=True)
