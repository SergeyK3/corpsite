"""Dedicated, Person-rooted HR correction endpoints for a personnel card."""
from __future__ import annotations

import re
import json
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text

from app.auth import get_current_user
from app.db.engine import engine
from app.ppr.application.authorization import PersonnelCardEditAuthorizationAdapter
from app.ppr.application.command_models import PprCommandEnvelope
from app.ppr.application.section_service import PprSectionApplicationService
from app.ppr.domain.section_models import SECTION_CODE_PPR_EDUCATION, SECTION_CODE_PPR_FAMILY, SECTION_CODE_PPR_TRAINING
from app.api.ppr_errors import map_ppr_mutation_error
from app.security.personnel_card_edit import require_personnel_card_edit_for_person
from app.services.personnel_record_event_service import emit_personnel_record_event

router = APIRouter(prefix="/api/ppr/persons/{person_id}", tags=["ppr-card-corrections"])

class _Strict(BaseModel): model_config = ConfigDict(extra="forbid")
class _Command(_Strict): command_id: str = Field(min_length=1); correlation_id: str | None = None; comment: str | None = None
class _Void(_Command): expected_updated_at: datetime; reason: str = Field(min_length=1)
class Education(_Strict):
    education_kind: str; institution_type: str | None=None; institution_name: str | None=None; specialty: str | None=None; qualification: str | None=None; started_at: date | None=None; completed_at: date | None=None; diploma_number: str | None=None; document_date: date | None=None
class Training(_Strict):
    training_kind: str; title: str | None=None; organization_name: str | None=None; hours: float | None=None; started_at: date | None=None; completed_at: date | None=None; certificate_number: str | None=None; document_date: date | None=None
class Relative(_Strict):
    relationship_type: str; full_name: str; birth_date: date | None=None; birth_place: str | None=None; organization_name: str | None=None; residence_address: str | None=None; notes: str | None=None
class _Create(_Command): record: dict[str, Any]
class _Supersede(_Command): expected_updated_at: datetime; replacement: dict[str, Any]
class Contacts(_Command):
    expected_version: int | None = Field(default=None, ge=1)
    mobile_phone: str | None = Field(default=None, max_length=64)
    email: str | None = None
    registration_address: str | None = Field(default=None, max_length=2000)
    residence_address: str | None = Field(default=None, max_length=2000)
    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        value = (value or "").strip() or None
        if value is not None and ("@" not in value or value.startswith("@") or value.endswith("@")):
            raise ValueError("Invalid email")
        return value
class ForeignLanguage(_Strict):
    language: str = Field(min_length=1, max_length=200)
    proficiency: str = Field(min_length=1, max_length=100)
    @field_validator("language", "proficiency")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value: raise ValueError("Value is required")
        return value
class ForeignLanguagesCommand(_Command):
    expected_updated_at: datetime | None = None
    foreign_languages: list[ForeignLanguage]
_METHODS = {"education": (Education, "add_education", "supersede_education", "void_education", SECTION_CODE_PPR_EDUCATION), "training": (Training, "add_training", "supersede_training", "void_training", SECTION_CODE_PPR_TRAINING), "relatives": (Relative, "add_relative", "supersede_relative", "void_relative", SECTION_CODE_PPR_FAMILY)}

def _service(user: dict[str, Any]) -> PprSectionApplicationService:
    return PprSectionApplicationService(authorization=PersonnelCardEditAuthorizationAdapter(user))
def _envelope(user: dict[str, Any], person_id: int, body: _Command, command_type: str, payload: dict[str, Any]) -> PprCommandEnvelope:
    return PprCommandEnvelope(command_id=body.command_id, command_type=command_type, actor_id=str(user["user_id"]), requested_at=datetime.now(UTC), payload=payload, person_id=person_id, correlation_id=body.correlation_id)
def _run(fn):
    try: return fn()
    except HTTPException: raise
    except Exception as exc:
        mapped=map_ppr_mutation_error(exc)
        if mapped: raise mapped
        raise

@router.post("/{section}/records")
def create_record(section: Literal["education","training","relatives"], body: _Create, person_id: int=Path(ge=1), user:dict=Depends(get_current_user)):
    require_personnel_card_edit_for_person(user, person_id)
    model, add, _, _, code = _METHODS[section]
    record=model.model_validate(body.record).model_dump()
    return _run(lambda: getattr(_service(user), add)(_envelope(user,person_id,body,f"PersonnelCardAdd{section.title()}",record)))

@router.post("/{section}/records/{record_id}/supersede")
def supersede_record(section: Literal["education","training","relatives"], record_id:int, body:_Supersede, person_id:int=Path(ge=1), user:dict=Depends(get_current_user)):
    require_personnel_card_edit_for_person(user, person_id)
    model, _, supersede, _, _ = _METHODS[section]
    replacement=model.model_validate(body.replacement).model_dump()
    return _run(lambda: getattr(_service(user), supersede)(_envelope(user,person_id,body,f"PersonnelCardSupersede{section.title()}",{"record_id":record_id,"expected_updated_at":body.expected_updated_at,"replacement":replacement})))

@router.post("/{section}/records/{record_id}/void")
def void_record(section: Literal["education","training","relatives"], record_id:int, body:_Void, person_id:int=Path(ge=1), user:dict=Depends(get_current_user)):
    require_personnel_card_edit_for_person(user, person_id)
    _, _, _, void, _ = _METHODS[section]
    return _run(lambda: getattr(_service(user), void)(_envelope(user,person_id,body,f"PersonnelCardVoid{section.title()}",{"record_id":record_id,"expected_updated_at":body.expected_updated_at,"reason":body.reason})))

def _clean(value: str | None) -> str | None:
    value=" ".join((value or "").split()); return value or None
def _phone(value: str | None) -> str | None:
    value=_clean(value)
    if value is None: return None
    normalized=re.sub(r"[^0-9+]", "", value)
    if normalized.startswith("+"): digits=normalized[1:]
    else: digits=normalized
    if len(digits) < 7 or len(digits)>15: raise HTTPException(422, "Invalid mobile_phone")
    return "+"+digits

@router.get("/contacts")
def get_contacts(person_id:int=Path(ge=1), user:dict=Depends(get_current_user)):
    from app.services.ppr_query_access_service import assert_ppr_read_allowed_for_person
    assert_ppr_read_allowed_for_person(user, person_id)
    with engine.connect() as conn:
        row=conn.execute(text("SELECT mobile_phone,email,registration_address,residence_address,version,updated_at FROM person_contacts WHERE person_id=:p"),{"p":person_id}).mappings().one_or_none()
        fallback = None
        if row is None:
            # Display-only hints.  They are never promoted or overwritten until
            # an HR user explicitly saves a canonical person_contacts row.
            application = conn.execute(text("""SELECT contact_mobile_phone AS mobile_phone, contact_email AS email
                FROM personnel_applications WHERE person_id=:p
                ORDER BY updated_at DESC NULLS LAST, application_id DESC LIMIT 1"""), {"p": person_id}).mappings().one_or_none()
            operational = conn.execute(text("SELECT phone AS mobile_phone FROM contacts WHERE person_id=:p AND COALESCE(is_deleted,false)=false ORDER BY updated_at DESC NULLS LAST LIMIT 1"), {"p": person_id}).mappings().one_or_none()
            if application or operational:
                fallback = {"mobile_phone": (application or {}).get("mobile_phone") or (operational or {}).get("mobile_phone"), "email": (application or {}).get("email"), "registration_address": None, "residence_address": None, "source": "intake_or_operational_unconfirmed"}
    return {"person_id":person_id,"canonical":dict(row) if row else None,"fallback":fallback}

@router.put("/contacts")
def save_contacts(body:Contacts, person_id:int=Path(ge=1), user:dict=Depends(get_current_user)):
    require_personnel_card_edit_for_person(user, person_id)
    after={"mobile_phone":_phone(body.mobile_phone),"email":str(body.email).lower() if body.email else None,"registration_address":_clean(body.registration_address),"residence_address":_clean(body.residence_address)}
    if not any(after.values()): raise HTTPException(422,"At least one contact value is required")
    with engine.begin() as conn:
        before=conn.execute(text("SELECT mobile_phone,email,registration_address,residence_address,version FROM person_contacts WHERE person_id=:p FOR UPDATE"),{"p":person_id}).mappings().one_or_none()
        if before and body.expected_version != int(before["version"]): raise HTTPException(409,"Contacts were changed; reload the card")
        if not before and body.expected_version not in (None,0): raise HTTPException(409,"Contacts were created; reload the card")
        row=conn.execute(text("""INSERT INTO person_contacts(person_id,mobile_phone,email,registration_address,residence_address,version,created_by_user_id,updated_by_user_id)
          VALUES(:p,:mobile_phone,:email,:registration_address,:residence_address,1,:u,:u)
          ON CONFLICT(person_id) DO UPDATE SET mobile_phone=EXCLUDED.mobile_phone,email=EXCLUDED.email,registration_address=EXCLUDED.registration_address,residence_address=EXCLUDED.residence_address,version=person_contacts.version+1,updated_at=now(),updated_by_user_id=:u
          RETURNING version,updated_at"""),{"p":person_id,"u":int(user["user_id"]),**after}).mappings().one()
        emit_personnel_record_event(conn,person_id=person_id,domain_code="contacts",record_table_name="person_contacts",record_id=person_id,event_type="PPR_CONTACTS_HR_CORRECTED",actor_id=str(user["user_id"]),event_payload={"section":"contacts","action":"upsert","before":dict(before) if before else None,"after":after,"comment":body.comment,"command_id":body.command_id,"correlation_id":body.correlation_id})
    return {"person_id":person_id,**after,"version":row["version"],"updated_at":row["updated_at"]}

@router.put("/foreign-languages")
def save_foreign_languages(body: ForeignLanguagesCommand, person_id: int = Path(ge=1), user: dict = Depends(get_current_user)):
    """Narrow CAS command: preserve every additional_profile key except languages."""
    require_personnel_card_edit_for_person(user, person_id)
    after = [item.model_dump() for item in body.foreign_languages]
    keys = [item["language"].casefold() for item in after]
    if len(keys) != len(set(keys)):
        raise HTTPException(422, "Duplicate foreign language")
    with engine.begin() as conn:
        prior_event = conn.execute(text("""SELECT event_payload FROM personnel_record_events
          WHERE person_id=:p AND event_type='PPR_FOREIGN_LANGUAGES_HR_CORRECTED'
            AND event_payload->>'command_id'=:c ORDER BY event_id DESC LIMIT 1"""), {"p": person_id, "c": body.command_id}).mappings().one_or_none()
        if prior_event:
            return {"person_id": person_id, "foreign_languages": after, "idempotent": True}
        row = conn.execute(text("SELECT additional_profile,updated_at FROM personnel_record_metadata WHERE person_id=:p FOR UPDATE"), {"p": person_id}).mappings().one_or_none()
        if row and body.expected_updated_at and body.expected_updated_at != row["updated_at"]:
            raise HTTPException(409, "Foreign languages were changed; reload the card")
        if not row and body.expected_updated_at is not None:
            raise HTTPException(409, "Foreign languages were created; reload the card")
        profile = dict(row["additional_profile"] or {}) if row else {}
        before = profile.get("foreign_languages", [])
        profile["foreign_languages"] = after
        profile["foreign_languages_none"] = not after
        updated = conn.execute(text("""INSERT INTO personnel_record_metadata(person_id,additional_profile)
          VALUES(:p,CAST(:profile AS jsonb)) ON CONFLICT(person_id) DO UPDATE
          SET additional_profile=EXCLUDED.additional_profile,updated_at=now() RETURNING updated_at"""),
          {"p": person_id, "profile": json.dumps(profile, ensure_ascii=False)}).scalar_one()
        emit_personnel_record_event(conn, person_id=person_id, domain_code="general_information", record_table_name="personnel_record_metadata", record_id=person_id, event_type="PPR_FOREIGN_LANGUAGES_HR_CORRECTED", actor_id=str(user["user_id"]), event_payload={"section":"foreign_languages","action":"replace","before":before,"after":after,"command_id":body.command_id,"correlation_id":body.correlation_id})
    return {"person_id": person_id, "foreign_languages": after, "updated_at": updated, "idempotent": False}
