"""Authenticated endpoints: never issue a public URL or trust a client owner ID."""
from __future__ import annotations
from datetime import date
from typing import Literal
from uuid import UUID, uuid4
import json
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from app.auth import get_current_user
from app.personnel_files import service, storage, classifiers
from app.personnel_files.access import self_person


async def request_audit():
    token = service.request_id.set(str(uuid4()))
    try:
        yield
    finally:
        service.request_id.reset(token)


router = APIRouter(prefix='/api/personnel-files', tags=['personnel-files'], dependencies=[Depends(request_audit)])


class Name(BaseModel):
    model_config = ConfigDict(extra='forbid')
    last_name: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str = Field(default='', max_length=100)

    @field_validator('last_name', 'first_name', 'middle_name')
    @classmethod
    def clean(cls, value, info):
        value = ' '.join(value.split())
        if not value and info.field_name != 'middle_name':
            raise ValueError('Укажите фамилию и имя.')
        if any(ord(c) < 32 for c in value):
            raise ValueError('Недопустимые символы в ФИО.')
        return value


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=1)
    action: Literal['approve','return','revoke','archive']
    reason: str = Field(default='', max_length=2000)
    expected_certificate_context: str | None = Field(default=None, min_length=64, max_length=64)


class Certificate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    employee_document_id: int | None = Field(default=None, ge=1)
    entry_id: int | None = Field(default=None, ge=1)
    specialty_name_at_issue: str | None = Field(default=None, min_length=1, max_length=500)
    issued_at: date | None = None
    valid_until: date | None = None
    document_number: str | None = Field(default=None, max_length=200)
    issued_by: str | None = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def complete(self):
        if self.employee_document_id:
            if self.model_fields_set != {'employee_document_id'}:
                raise ValueError('Реквизиты существующей записи нельзя переопределять при загрузке.')
        elif not all((self.entry_id,self.specialty_name_at_issue,self.issued_at,self.valid_until)):
            raise ValueError('Укажите специальность, исходное название и даты сертификата.')
        elif self.valid_until < self.issued_at:
            raise ValueError('Срок действия заканчивается раньше даты выдачи.')
        return self


class ApplyName(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=1)
    expected_full_name: str = Field(min_length=1, max_length=500)
    effective_date: date
    reason: str = Field(min_length=1, max_length=2000)


def upload(user, person_id, file, kind, title, set_id, expected_revision, expected_version_id, proposed_name, certificate=None):
    proposal = None
    if proposed_name:
        try:
            proposal = Name.model_validate(json.loads(proposed_name)).model_dump()
        except (ValueError, ValidationError) as exc:
            raise HTTPException(422, 'Проверьте предлагаемое ФИО.') from exc
    facts = None
    if certificate:
        try:
            facts = Certificate.model_validate(json.loads(certificate)).model_dump(exclude_none=True)
        except (ValueError, ValidationError):
            raise HTTPException(422, 'Проверьте реквизиты сертификата: специальность, исходное название и даты.') from None
    data = file.file.read(storage.MAX_BYTES + 1)
    if len(data) > storage.MAX_BYTES:
        raise HTTPException(413, 'Максимальный размер файла — 10 МиБ.')
    return service.submit(user, person_id, content=data, mime=(file.content_type or '').lower(),
        filename=file.filename or 'document', kind=kind, title=title, set_id=str(set_id) if set_id else None,
        expected_revision=expected_revision, expected_version_id=str(expected_version_id) if expected_version_id else None, proposed_name=proposal, certificate=facts)


@router.get('/me')
def my_files(user: dict = Depends(get_current_user)):
    return service.listing(user, self_person(user))


@router.post('/me', status_code=201)
def upload_my_file(file: UploadFile = File(...), kind: str = Form(...), title: str = Form(...),
                   set_id: UUID | None = Form(None), expected_revision: int | None = Form(None), expected_version_id: UUID | None = Form(None),
                   proposed_name: str | None = Form(None), certificate: str | None = Form(None), user: dict = Depends(get_current_user)):
    return upload(user, self_person(user), file, kind, title, set_id, expected_revision, expected_version_id, proposed_name, certificate)


@router.get('/me/history')
def my_history(user: dict = Depends(get_current_user)):
    return service.history(user, self_person(user))


@router.get('/persons/{person_id}')
def person_files(person_id: int, user: dict = Depends(get_current_user)):
    return service.listing(user, person_id)


@router.post('/persons/{person_id}', status_code=201)
def upload_person_file(person_id: int, file: UploadFile = File(...), kind: str = Form(...), title: str = Form(...),
                       set_id: UUID | None = Form(None), expected_revision: int | None = Form(None), expected_version_id: UUID | None = Form(None),
                       proposed_name: str | None = Form(None), certificate: str | None = Form(None), user: dict = Depends(get_current_user)):
    return upload(user, person_id, file, kind, title, set_id, expected_revision, expected_version_id, proposed_name, certificate)


@router.get('/me/registry-certificates')
def my_registry_certificates(user: dict = Depends(get_current_user)):
    return service.registry_options(user, self_person(user))


@router.get('/persons/{person_id}/registry-certificates')
def person_registry_certificates(person_id: int, user: dict = Depends(get_current_user)):
    return service.registry_options(user, person_id)


@router.get('/versions/{version_id}/review-context')
def certificate_review_context(version_id: UUID, user: dict = Depends(get_current_user)):
    return service.review_context(user, str(version_id))


@router.get('/persons/{person_id}/history')
def person_history(person_id: int, user: dict = Depends(get_current_user)):
    return service.history(user, person_id)


@router.post('/versions/{version_id}/decision')
def decision(version_id: UUID, body: Decision, user: dict = Depends(get_current_user)):
    return service.decide(user, str(version_id), **body.model_dump())


@router.post('/versions/{version_id}/apply-name')
def apply_name(version_id: UUID, body: ApplyName, user: dict = Depends(get_current_user)):
    return service.apply_name(user, str(version_id), **body.model_dump())


def binary(user, version_id, operation, page):
    data, mime, r = service.content(user, str(version_id), operation=operation, page=page)
    extension = {'image/jpeg':'jpg','image/png':'png','application/pdf':'pdf'}[r['mime_type']]
    disposition = f'attachment; filename="{r["kind"]}-{r["version_no"]}.{extension}"' if operation == 'download' else 'inline'
    return Response(data, media_type=mime, headers={'Cache-Control':'private, no-store',
        'X-Content-Type-Options':'nosniff', 'Content-Disposition': disposition,
        'Content-Security-Policy': "default-src 'none'; sandbox", 'Referrer-Policy':'no-referrer'})


@router.get('/versions/{version_id}/preview')
def preview(version_id: UUID, page: int = Query(1, ge=1), user: dict = Depends(get_current_user)):
    return binary(user, version_id, 'view', page)


@router.get('/versions/{version_id}/download')
def download(version_id: UUID, user: dict = Depends(get_current_user)):
    return binary(user, version_id, 'download', 1)


@router.get('/versions/{version_id}/print')
def print_page(version_id: UUID, page: int = Query(1, ge=1), user: dict = Depends(get_current_user)):
    return binary(user, version_id, 'print', page)


@router.get('/review-queue')
def review_queue(after: UUID | None = Query(None), user: dict = Depends(get_current_user)):
    return service.review_queue(user, str(after) if after else None)


class Acknowledge(BaseModel):
    model_config = ConfigDict(extra='forbid')
    through_event_id: int = Field(ge=1)


@router.post('/me/notifications/read')
def acknowledge(body: Acknowledge, user: dict = Depends(get_current_user)):
    return service.acknowledge(user, self_person(user), body.through_event_id)


class CentralInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class EditionInput(CentralInput):
    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    source_reference: str = Field(min_length=1, max_length=2000)
    effective_from: date


class EntryInput(CentralInput):
    edition_id: int = Field(ge=1)
    medical_specialty_id: int = Field(ge=1)
    specialty_code: str = Field(min_length=1, max_length=100)
    specialty_name: str = Field(min_length=1, max_length=500)


class MappingInput(CentralInput):
    from_entry_id: int = Field(ge=1)
    to_entry_id: int = Field(ge=1)
    source_reference: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)
    effective_from: date


class AvailabilityInput(CentralInput):
    accepts_new: bool
    reason: str = Field(min_length=1, max_length=2000)


class RevokeMappingInput(CentralInput):
    reason: str = Field(min_length=1, max_length=2000)


@router.get('/certificate-classifiers')
def certificate_classifiers(user: dict = Depends(get_current_user)):
    return classifiers.catalog(user)


@router.post('/certificate-classifiers/editions', status_code=201)
def create_edition(payload: EditionInput, user: dict = Depends(get_current_user)):
    return classifiers.manage(user, 'edition', payload.model_dump())


@router.post('/certificate-classifiers/entries', status_code=201)
def create_classifier_entry(payload: EntryInput, user: dict = Depends(get_current_user)):
    return classifiers.manage(user, 'entry', payload.model_dump())


@router.post('/certificate-classifiers/mappings', status_code=201)
def confirm_mapping(payload: MappingInput, user: dict = Depends(get_current_user)):
    return classifiers.manage(user, 'mapping', payload.model_dump())


@router.post('/certificate-classifiers/editions/{edition_id}/availability')
def edition_availability(edition_id: int, payload: AvailabilityInput, user: dict = Depends(get_current_user)):
    return classifiers.manage(user, 'edition-availability', {'edition_id': edition_id, **payload.model_dump()})


@router.post('/certificate-classifiers/mappings/{mapping_id}/revoke')
def revoke_mapping(mapping_id: int, payload: RevokeMappingInput, user: dict = Depends(get_current_user)):
    return classifiers.manage(user, 'mapping-revoke', {'mapping_id': mapping_id, **payload.model_dump()})
