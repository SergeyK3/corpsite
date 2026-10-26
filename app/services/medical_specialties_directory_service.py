"""Administration of the existing professional-document specialty dictionary."""
import hashlib
import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy import text
from app.db.engine import engine


def normalize_name(value):
    return re.sub(r"[\W_]+", " ", unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")).strip()


def list_specialties(*, group_id=None, group_code=None, is_active=True, q=None, limit=None, offset=0):
    clauses, params = ["TRUE"], {}
    if is_active:
        clauses.append("ms.is_active=TRUE")
    if group_id is not None:
        clauses.append("ms.group_id=:group_id")
        params["group_id"] = group_id
    if group_code:
        clauses.append("g.code=:group_code")
        params["group_code"] = group_code.strip().upper()
    if q and q.strip():
        clauses.append("(ms.name ILIKE :q ESCAPE '\\' OR ms.name_kk ILIKE :q ESCAPE '\\')")
        params["q"] = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    source = " FROM public.medical_specialties ms JOIN public.medical_specialty_groups g USING(group_id) WHERE " + " AND ".join(clauses)
    pagination = ""
    if limit is not None:
        pagination = " LIMIT :limit OFFSET :offset"
        params.update(limit=limit, offset=offset)
    with engine.connect() as conn:
        total = conn.execute(text("SELECT count(*)" + source), params).scalar_one()
        rows = conn.execute(text("SELECT ms.medical_specialty_id,ms.group_id,g.code AS group_code,g.name AS group_name,ms.code,ms.name,ms.name_kk,ms.is_active" + source + " ORDER BY g.code,ms.name,ms.medical_specialty_id" + pagination), params).mappings().all()
    return {"items": [dict(row) for row in rows], "total": total}


def get_specialty(specialty_id, connection=None):
    if connection is None:
        with engine.connect() as conn:
            return get_specialty(specialty_id, conn)
    row = connection.execute(text("SELECT * FROM public.medical_specialties WHERE medical_specialty_id=:id"), {"id": specialty_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Медицинская специальность не найдена.")
    return dict(row)


def archive_specialties(specialty_ids):
    """Deactivate dictionary entries atomically; keep their IDs and references."""
    ids = sorted(set(specialty_ids))
    if not ids or any(type(id) is not int or id < 1 for id in ids):
        raise HTTPException(422, "Укажите ID специальностей для архивирования.")
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('medical_specialties_write'))"))
        rows = conn.execute(text("SELECT medical_specialty_id,is_active FROM public.medical_specialties WHERE medical_specialty_id=ANY(:ids) ORDER BY medical_specialty_id FOR UPDATE"), {"ids": ids}).mappings().all()
        if len(rows) != len(ids):
            raise HTTPException(404, "Одна из специальностей не найдена. Архивирование отменено.")
        changed = [row["medical_specialty_id"] for row in rows if row["is_active"]]
        if changed:
            conn.execute(text("UPDATE public.medical_specialties SET is_active=FALSE WHERE medical_specialty_id=ANY(:ids)"), {"ids": changed})
        return {"items": [get_specialty(id, conn) for id in ids], "archived_ids": changed}


def create_specialty(name, name_kk=None, group_id=None):
    if not name.strip() or (name_kk is not None and not name_kk.strip()):
        raise HTTPException(422, "Название не должно состоять только из пробелов.")
    # Comparison is normalized; persisted text is exactly what was supplied.
    wanted = {normalize_name(v) for v in (name, name_kk) if v}
    code = "MED_" + hashlib.sha256(normalize_name(name).encode()).hexdigest()[:24].upper()
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('medical_specialties_write'))"))
        existing = conn.execute(text("SELECT medical_specialty_id,name,name_kk FROM public.medical_specialties")).mappings()
        for row in existing:
            if wanted.intersection(normalize_name(v) for v in (row["name"], row["name_kk"]) if v):
                raise HTTPException(409, detail={"message": "Такая специальность уже существует или требует сверки.", "medical_specialty_id": row["medical_specialty_id"]})
        if group_id is None:
            conn.execute(text("INSERT INTO public.medical_specialty_groups(code,name) VALUES ('UNCLASSIFIED','Без классификации') ON CONFLICT(code) DO NOTHING"))
            group_id = conn.execute(text("SELECT group_id FROM public.medical_specialty_groups WHERE code='UNCLASSIFIED' AND is_active=TRUE")).scalar()
        if group_id is None or not conn.execute(text("SELECT 1 FROM public.medical_specialty_groups WHERE group_id=:id AND is_active=TRUE"), {"id": group_id}).first():
            raise HTTPException(422, "Группа специальности не найдена или неактивна.")
        id = conn.execute(text("INSERT INTO public.medical_specialties(group_id,code,name,name_kk) VALUES (:group,:code,:name,:kk) RETURNING medical_specialty_id"), {"group": group_id, "code": code, "name": name, "kk": name_kk}).scalar_one()
        return get_specialty(id, conn)
