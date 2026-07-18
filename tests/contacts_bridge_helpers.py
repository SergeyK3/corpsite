"""Test helpers for contacts operational bridge (contacts_working view)."""
from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from tests.conftest import get_columns, insert_returning_id, safe_delete_many, table_exists


def relation_type(conn, name: str, *, schema: str = "public") -> str | None:
    row = conn.execute(
        text(
            """
            SELECT table_type
            FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :name
            """
        ),
        {"schema": schema, "name": name},
    ).first()
    return str(row[0]) if row else None


def is_view(conn, name: str, *, schema: str = "public") -> bool:
    return relation_type(conn, name, schema=schema) == "VIEW"


def create_test_person(conn, *, full_name: str) -> int:
    if not table_exists(conn, "persons"):
        pytest.skip("persons table not available")

    cols = get_columns(conn, "persons")
    values: dict[str, Any] = {"full_name": full_name}
    if "person_status" in cols:
        values["person_status"] = "active"
    if "match_key" in cols:
        values["match_key"] = f"pytest:{full_name}:{uuid4().hex[:8]}"

    return insert_returning_id(
        conn,
        table="persons",
        id_col="person_id",
        values=values,
    )


def create_test_contact(
    conn,
    *,
    full_name: str,
    person_id: int | None = None,
) -> int:
    if not table_exists(conn, "contacts"):
        pytest.skip("contacts table not available")

    values: dict[str, Any] = {"full_name": full_name, "is_deleted": False}
    cols = get_columns(conn, "contacts")
    if person_id is not None and "person_id" in cols:
        values["person_id"] = int(person_id)
        conn.execute(
            text("DELETE FROM public.contacts WHERE person_id = :person_id"),
            {"person_id": int(person_id)},
        )

    return insert_returning_id(
        conn,
        table="contacts",
        id_col="contact_id",
        values=values,
    )


def _upsert_personnel_bridge(conn, *, person_id: int, dept_code: str) -> None:
    if not table_exists(conn, "personnel"):
        pytest.skip("personnel table not available for contacts_working view bridge")

    cols = get_columns(conn, "personnel")
    values: dict[str, Any] = {
        "person_id": person_id,
        "dept_code": dept_code,
        "dept_name": dept_code,
        "date_from": date(2000, 1, 1),
    }
    if "date_to" in cols:
        values["date_to"] = None

    existing = conn.execute(
        text("SELECT 1 FROM public.personnel WHERE person_id = :person_id"),
        {"person_id": person_id},
    ).first()
    if existing:
        conn.execute(
            text(
                """
                UPDATE public.personnel
                SET dept_code = :dept_code,
                    dept_name = :dept_name,
                    date_from = :date_from,
                    date_to = :date_to
                WHERE person_id = :person_id
                """
            ),
            {
                "person_id": person_id,
                "dept_code": dept_code,
                "dept_name": dept_code,
                "date_from": values["date_from"],
                "date_to": values.get("date_to"),
            },
        )
    else:
        insert_returning_id(
            conn,
            table="personnel",
            id_col="person_id",
            values=values,
        )

    if table_exists(conn, "contact_access"):
        access_exists = conn.execute(
            text("SELECT 1 FROM public.contact_access WHERE person_id = :person_id"),
            {"person_id": person_id},
        ).first()
        if not access_exists:
            insert_returning_id(
                conn,
                table="contact_access",
                id_col="person_id",
                values={"person_id": person_id},
            )


def link_person_to_dept_code(conn, *, person_id: int, dept_code: str) -> int:
    _upsert_personnel_bridge(conn, person_id=int(person_id), dept_code=dept_code)
    return int(person_id)


def link_contact_to_dept_code(
    conn,
    *,
    contact_id: int,
    dept_code: str,
    person_id: int | None = None,
) -> int:
    """Write canonical personnel bridge data backing ``contacts_working.dept_code``."""
    if is_view(conn, "contacts_working"):
        if person_id is None:
            row = conn.execute(
                text(
                    """
                    SELECT person_id
                    FROM public.contacts
                    WHERE contact_id = :contact_id
                    """
                ),
                {"contact_id": int(contact_id)},
            ).mappings().first()
            if not row or row.get("person_id") is None:
                raise RuntimeError(
                    "contacts_working is a view — contact must have person_id before dept_code link"
                )
            person_id = int(row["person_id"])

        link_person_to_dept_code(conn, person_id=int(person_id), dept_code=dept_code)
        return int(person_id)

    conn.execute(
        text(
            """
            INSERT INTO public.contacts_working (contact_id, person_id, dept_code)
            VALUES (:contact_id, :person_id, :dept_code)
            """
        ),
        {
            "contact_id": int(contact_id),
            "person_id": person_id,
            "dept_code": str(dept_code),
        },
    )
    assert person_id is not None
    return person_id


def cleanup_contacts_bridge(
    *,
    contact_ids: list[int] | None = None,
    person_ids: list[int] | None = None,
) -> None:
    contact_ids = [int(x) for x in (contact_ids or [])]
    person_ids = [int(x) for x in (person_ids or [])]
    if not contact_ids and not person_ids:
        return

    with engine.begin() as conn:
        if person_ids:
            safe_delete_many(conn, "contact_access", "person_id", person_ids)
            safe_delete_many(conn, "personnel", "person_id", person_ids)
            conn.execute(
                text("DELETE FROM public.contacts WHERE person_id = ANY(:person_ids)"),
                {"person_ids": person_ids},
            )
        if contact_ids:
            safe_delete_many(conn, "contacts", "contact_id", contact_ids)
        if person_ids:
            safe_delete_many(conn, "persons", "person_id", person_ids)
