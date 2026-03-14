# FILE: app/directory/contacts_routes.py
from __future__ import annotations

from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user
from app.db.engine import engine
from app.security.directory_scope import is_privileged as _is_privileged

router = APIRouter()


class ContactUpsert(BaseModel):
    person_id: Optional[int] = Field(default=None, ge=1)
    full_name: str = Field(..., min_length=1, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=100)
    telegram_username: Optional[str] = Field(default=None, max_length=255)
    telegram_numeric_id: Optional[int] = Field(default=None, ge=1)


CONTACT_SELECT_SQL = """
SELECT
    c.contact_id,
    c.person_id,
    c.full_name,
    c.phone,
    c.telegram_username,
    c.telegram_numeric_id,
    c.created_at,
    c.updated_at
FROM public.contacts c
"""


def _normalize_text(value: Optional[str]) -> Optional[str]:
    s = " ".join(str(value or "").split()).strip()
    return s or None


def _normalize_telegram(value: Optional[str]) -> Optional[str]:
    s = _normalize_text(value)
    if not s:
        return None
    if s.startswith("@"):
        s = s[1:]
    return s.lower()


def _map_contact(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "contact_id": int(row["contact_id"]),
        "person_id": int(row["person_id"]) if row.get("person_id") is not None else None,
        "full_name": str(row["full_name"] or "").strip(),
        "phone": str(row["phone"] or "").strip() or None,
        "telegram_username": str(row["telegram_username"] or "").strip() or None,
        "telegram_numeric_id": (
            int(row["telegram_numeric_id"]) if row.get("telegram_numeric_id") is not None else None
        ),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _fetch_contact(conn, contact_id: int) -> Optional[Dict[str, Any]]:
    q = text(
        f"""
        {CONTACT_SELECT_SQL}
        WHERE c.contact_id = :contact_id
          AND COALESCE(c.is_deleted, false) = false
        LIMIT 1
        """
    )
    row = conn.execute(q, {"contact_id": contact_id}).mappings().first()
    return dict(row) if row else None


def _list_relations(schema: str = "public") -> List[str]:
    q = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = :schema
          AND table_type IN ('BASE TABLE', 'VIEW')
        ORDER BY table_name
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(q, {"schema": schema}).fetchall()
    return [str(r[0]) for r in rows]


def _relation_exists(rel: str) -> bool:
    return rel in set(_list_relations("public"))


def _get_org_unit_caption(org_unit_id: int) -> str:
    q = text(
        """
        SELECT COALESCE(NULLIF(TRIM(name), ''), CONCAT('unit #', CAST(unit_id AS TEXT))) AS unit_name
        FROM public.org_units
        WHERE unit_id = :org_unit_id
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(q, {"org_unit_id": int(org_unit_id)}).mappings().first()

    if not row:
        return f"unit #{int(org_unit_id)}"

    return str(row.get("unit_name") or f"unit #{int(org_unit_id)}").strip()


def _build_eligible_contacts_cte_sql() -> str:
    parts: List[str] = []

    if _relation_exists("contacts_working"):
        parts.append(
            """
            SELECT DISTINCT
                cw.contact_id AS contact_id,
                cw.person_id AS person_id
            FROM public.contacts_working cw
            WHERE COALESCE(NULLIF(TRIM(cw.dept_code), ''), '∅') IN (
                SELECT sc.code
                FROM subtree_codes sc
            )
            """.strip()
        )

    if _relation_exists("key_contacts"):
        parts.append(
            """
            SELECT DISTINCT
                NULL::integer AS contact_id,
                kc.person_id AS person_id
            FROM public.key_contacts kc
            WHERE COALESCE(NULLIF(TRIM(kc.unit_code), ''), '∅') IN (
                SELECT sc.code
                FROM subtree_codes sc
            )
            """.strip()
        )

    if _relation_exists("v_key_contacts_auto"):
        parts.append(
            """
            SELECT DISTINCT
                NULL::integer AS contact_id,
                ka.person_id AS person_id
            FROM public.v_key_contacts_auto ka
            WHERE COALESCE(NULLIF(TRIM(ka.unit_code), ''), '∅') IN (
                SELECT sc.code
                FROM subtree_codes sc
            )
            """.strip()
        )

    return "\nUNION\n".join(parts)


@router.get("/contacts")
def list_contacts(
    q: Optional[str] = Query(default=None),
    org_unit_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    params: Dict[str, Any] = {"limit": int(limit), "offset": int(offset)}
    where_parts = ["COALESCE(c.is_deleted, false) = false"]
    with_prefix = ""
    filter_org_unit_name: Optional[str] = None

    if q and q.strip():
        params["q"] = f"%{q.strip().lower()}%"
        where_parts.append(
            """
            (
                LOWER(COALESCE(CAST(c.contact_id AS TEXT), '')) LIKE :q
                OR LOWER(COALESCE(CAST(c.person_id AS TEXT), '')) LIKE :q
                OR LOWER(COALESCE(CAST(c.full_name AS TEXT), '')) LIKE :q
                OR LOWER(COALESCE(CAST(c.phone AS TEXT), '')) LIKE :q
                OR LOWER(COALESCE(CAST(c.telegram_username AS TEXT), '')) LIKE :q
                OR LOWER(COALESCE(CAST(c.telegram_numeric_id AS TEXT), '')) LIKE :q
            )
            """
        )

    if org_unit_id is not None:
        params["org_unit_id"] = int(org_unit_id)
        filter_org_unit_name = _get_org_unit_caption(int(org_unit_id))

        eligible_contacts_sql = _build_eligible_contacts_cte_sql()

        if eligible_contacts_sql:
            with_prefix = f"""
            WITH RECURSIVE subtree AS (
                SELECT ou.unit_id, ou.code
                FROM public.org_units ou
                WHERE ou.unit_id = :org_unit_id

                UNION ALL

                SELECT child.unit_id, child.code
                FROM public.org_units child
                JOIN subtree s ON s.unit_id = child.parent_unit_id
            ),
            subtree_codes AS (
                SELECT DISTINCT TRIM(code) AS code
                FROM subtree
                WHERE COALESCE(TRIM(code), '') <> ''
            ),
            eligible_contacts AS (
                {eligible_contacts_sql}
            )
            """

            where_parts.append(
                """
                EXISTS (
                    SELECT 1
                    FROM eligible_contacts ec
                    WHERE
                        (ec.contact_id IS NOT NULL AND ec.contact_id = c.contact_id)
                        OR
                        (ec.person_id IS NOT NULL AND c.person_id IS NOT NULL AND ec.person_id = c.person_id)
                )
                """
            )
        else:
            where_parts.append("FALSE")

    where_sql = " AND ".join(where_parts)

    q_total = text(
        f"""
        {with_prefix}
        SELECT COUNT(*) AS cnt
        FROM public.contacts c
        WHERE {where_sql}
        """
    )

    q_list = text(
        f"""
        {with_prefix}
        {CONTACT_SELECT_SQL}
        WHERE {where_sql}
        ORDER BY LOWER(COALESCE(CAST(c.full_name AS TEXT), '')) ASC, c.contact_id ASC
        LIMIT :limit OFFSET :offset
        """
    )

    with engine.begin() as conn:
        total = int(conn.execute(q_total, params).mappings().first()["cnt"])
        rows = conn.execute(q_list, params).mappings().all()

    items = [_map_contact(dict(r)) for r in rows]
    return {
        "items": items,
        "total": total,
        "filter_org_unit_id": int(org_unit_id) if org_unit_id is not None else None,
        "filter_org_unit_name": filter_org_unit_name,
    }


@router.get("/contacts/{contact_id}")
def get_contact(
    contact_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    with engine.begin() as conn:
        row = _fetch_contact(conn, int(contact_id))

    if not row:
        raise HTTPException(status_code=404, detail="Contact not found.")

    return _map_contact(row)


@router.post("/contacts")
def create_contact(
    payload: ContactUpsert,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    full_name = _normalize_text(payload.full_name)
    phone = _normalize_text(payload.phone)
    telegram_username = _normalize_telegram(payload.telegram_username)
    person_id = payload.person_id
    telegram_numeric_id = payload.telegram_numeric_id

    if not full_name:
        raise HTTPException(status_code=422, detail="full_name is required.")

    q_existing_person = text(
        """
        SELECT contact_id, COALESCE(is_deleted, false) AS is_deleted
        FROM public.contacts
        WHERE person_id = :person_id
        LIMIT 1
        """
    )

    q_revive = text(
        """
        UPDATE public.contacts
        SET is_deleted = false,
            full_name = :full_name,
            phone = :phone,
            telegram_username = :telegram_username,
            telegram_numeric_id = :telegram_numeric_id,
            updated_at = NOW()
        WHERE contact_id = :contact_id
        RETURNING contact_id
        """
    )

    q_insert = text(
        """
        INSERT INTO public.contacts (
            person_id,
            full_name,
            phone,
            telegram_username,
            telegram_numeric_id
        )
        VALUES (
            :person_id,
            :full_name,
            :phone,
            :telegram_username,
            :telegram_numeric_id
        )
        RETURNING contact_id
        """
    )

    try:
        with engine.begin() as conn:
            if person_id is not None:
                existing_person = conn.execute(
                    q_existing_person,
                    {"person_id": person_id},
                ).mappings().first()

                if existing_person and not bool(existing_person["is_deleted"]):
                    raise HTTPException(status_code=409, detail="Contact with this person_id already exists.")

                if existing_person and bool(existing_person["is_deleted"]):
                    revived = conn.execute(
                        q_revive,
                        {
                            "contact_id": int(existing_person["contact_id"]),
                            "full_name": full_name,
                            "phone": phone,
                            "telegram_username": telegram_username,
                            "telegram_numeric_id": telegram_numeric_id,
                        },
                    ).mappings().first()
                    row = _fetch_contact(conn, int(revived["contact_id"]))
                    if not row:
                        raise HTTPException(status_code=500, detail="Contact restored but cannot be reloaded.")
                    return _map_contact(row)

            inserted = conn.execute(
                q_insert,
                {
                    "person_id": person_id,
                    "full_name": full_name,
                    "phone": phone,
                    "telegram_username": telegram_username,
                    "telegram_numeric_id": telegram_numeric_id,
                },
            ).mappings().first()

            row = _fetch_contact(conn, int(inserted["contact_id"]))
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Unable to create contact.")

    if not row:
        raise HTTPException(status_code=500, detail="Contact created but cannot be reloaded.")

    return _map_contact(row)


@router.patch("/contacts/{contact_id}")
@router.put("/contacts/{contact_id}")
def update_contact(
    contact_id: int,
    payload: ContactUpsert,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    full_name = _normalize_text(payload.full_name)
    phone = _normalize_text(payload.phone)
    telegram_username = _normalize_telegram(payload.telegram_username)
    person_id = payload.person_id
    telegram_numeric_id = payload.telegram_numeric_id

    if not full_name:
        raise HTTPException(status_code=422, detail="full_name is required.")

    q_conflict_person = text(
        """
        SELECT contact_id
        FROM public.contacts
        WHERE person_id = :person_id
          AND contact_id <> :contact_id
        LIMIT 1
        """
    )

    q_update = text(
        """
        UPDATE public.contacts
        SET person_id = :person_id,
            full_name = :full_name,
            phone = :phone,
            telegram_username = :telegram_username,
            telegram_numeric_id = :telegram_numeric_id,
            updated_at = NOW()
        WHERE contact_id = :contact_id
          AND COALESCE(is_deleted, false) = false
        RETURNING contact_id
        """
    )

    try:
        with engine.begin() as conn:
            if person_id is not None:
                conflict_person = conn.execute(
                    q_conflict_person,
                    {
                        "person_id": person_id,
                        "contact_id": int(contact_id),
                    },
                ).mappings().first()
                if conflict_person:
                    raise HTTPException(status_code=409, detail="Contact with this person_id already exists.")

            updated = conn.execute(
                q_update,
                {
                    "contact_id": int(contact_id),
                    "person_id": person_id,
                    "full_name": full_name,
                    "phone": phone,
                    "telegram_username": telegram_username,
                    "telegram_numeric_id": telegram_numeric_id,
                },
            ).mappings().first()

            if not updated:
                raise HTTPException(status_code=404, detail="Contact not found.")

            row = _fetch_contact(conn, int(updated["contact_id"]))
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Unable to update contact.")

    if not row:
        raise HTTPException(status_code=500, detail="Contact updated but cannot be reloaded.")

    return _map_contact(row)


@router.delete("/contacts/{contact_id}")
def delete_contact(
    contact_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if not _is_privileged(user):
        raise HTTPException(status_code=403, detail="Forbidden.")

    q_delete = text(
        """
        UPDATE public.contacts
        SET is_deleted = true,
            updated_at = NOW()
        WHERE contact_id = :contact_id
          AND COALESCE(is_deleted, false) = false
        RETURNING contact_id
        """
    )

    with engine.begin() as conn:
        deleted = conn.execute(q_delete, {"contact_id": int(contact_id)}).mappings().first()

    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found.")

    return {"ok": True, "contact_id": int(deleted["contact_id"])}