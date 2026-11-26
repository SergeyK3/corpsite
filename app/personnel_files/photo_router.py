"""Photo-only public surface for the first self-card proposal iteration."""
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import text

from app.auth import get_current_user
from app.personnel_files import service, storage
from app.personnel_files.access import access, self_person
from app.personnel_files.router import Decision, request_audit
from app.services.ppr_person_photo_read_service import load_verified_person_photo

router = APIRouter(prefix="/api/personnel-files", tags=["personnel-files"],
                   dependencies=[Depends(request_audit)])


def _photo_version(version_id: UUID) -> None:
    with service.engine.connect() as conn:
        kind = conn.execute(text("""SELECT s.kind FROM public.personnel_file_versions v
            JOIN public.personnel_file_sets s USING(set_id) WHERE v.version_id=:vid"""),
            {"vid": str(version_id)}).scalar_one_or_none()
    if kind != "photo":
        raise HTTPException(404, "Версия фото не найдена.")


@router.get("/me")
def my_photos(user: dict = Depends(get_current_user)):
    result = service.listing(user, self_person(user))
    return {**result, "items": [item for item in result["items"] if item["kind"] == "photo"]}


@router.post("/me", status_code=201)
def upload_photo(file: UploadFile = File(...), kind: str = Form(...), title: str = Form(...),
                 set_id: UUID | None = Form(None), expected_revision: int | None = Form(None),
                 expected_version_id: UUID | None = Form(None), user: dict = Depends(get_current_user)):
    if kind != "photo":
        raise HTTPException(422, "В этой форме можно отправить только фото.")
    data = file.file.read(storage.MAX_BYTES + 1)
    if len(data) > storage.MAX_BYTES:
        raise HTTPException(413, "Максимальный размер фото — 10 МиБ.")
    return service.submit(user, self_person(user), content=data, mime=(file.content_type or "").lower(),
        filename=file.filename or "photo.jpg", kind="photo", title=title,
        set_id=str(set_id) if set_id else None, expected_revision=expected_revision,
        expected_version_id=str(expected_version_id) if expected_version_id else None)


@router.get("/review-queue")
def review_queue(user: dict = Depends(get_current_user)):
    result = service.review_queue(user, None)
    return {**result, "items": [item for item in result["items"] if item["kind"] == "photo"]}


@router.get("/persons/{person_id}/current-photo")
def current_photo(person_id: int, user: dict = Depends(get_current_user)):
    with service.engine.connect() as conn:
        if not access(conn, user, person_id).reviewer:
            raise HTTPException(403, "Недостаточно прав для просмотра фото.")
    content = load_verified_person_photo(person_id, user=user)
    if content is None:
        raise HTTPException(404, "Действующее фото не найдено.")
    return Response(content, media_type="image/jpeg", headers={"Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff"})


@router.get("/versions/{version_id}/preview")
def preview(version_id: UUID, user: dict = Depends(get_current_user)):
    _photo_version(version_id)
    data, mime, _ = service.content(user, str(version_id), operation="view", page=1)
    return Response(data, media_type=mime, headers={"Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff", "Content-Disposition": "inline",
        "Content-Security-Policy": "default-src 'none'; sandbox", "Referrer-Policy": "no-referrer"})


@router.post("/versions/{version_id}/decision")
def decide(version_id: UUID, body: Decision, user: dict = Depends(get_current_user)):
    _photo_version(version_id)
    if body.action not in {"approve", "return"}:
        raise HTTPException(422, "Для фото доступны одобрение и возврат.")
    return service.decide(user, str(version_id), **body.model_dump())
