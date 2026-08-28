"""Seed personnel positions and organizational units safely.

Revision ID: t3u4v5w6x7y
Revises: s2t3u4v5w6x
"""
from __future__ import annotations

from typing import Any

from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection


revision = "t3u4v5w6x7y"
down_revision = "s2t3u4v5w6x"
branch_labels = None
depends_on = None


_POSITIONS: tuple[tuple[str, str], ...] = (
    ("Заведующий отделением", "other"),
    ("Машинист по стирке белья", "technical"),
    ("Социальный работник", "medical"),
    ("Медицинский статистик", "medical"),
    ("Техник", "technical"),
    ("Заведующий ОТ и ТБ", "leaders"),
    ("Санитар по транспортировке пациентов", "medical"),
    ("Врач-эксперт", "medical"),
    ("Руководитель административно-хозяйственной службы", "leaders"),
    ("Буфетчица", "technical"),
    ("Бухгалтер-экономист", "admin"),
    ("Руководитель отдела", "leaders"),
    ("Старший ординатор", "medical"),
    ("Комплаенс-офицер", "admin"),
    ("Главный инженер", "technical"),
)

_ENGINEER = "Инженер"
_ENGINEER_DUPLICATE = "инженер"
_NORMALIZED_SQL = (
    "regexp_replace(lower(btrim(replace({column}, chr(160), ' '))), "
    "'[[:space:]_-]+', '', 'g')"
)


def _normalized(column: str) -> str:
    return _NORMALIZED_SQL.format(column=column)


def _position_matches(conn: Connection, name: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            f"""
            SELECT position_id, name, category
            FROM public.positions
            WHERE {_normalized('name')} = {_normalized(':name')}
            ORDER BY position_id
            """
        ),
        {"name": name},
    ).mappings()
    return [dict(row) for row in rows]


def _insert_position(conn: Connection, name: str, category: str) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.positions (name, category)
            VALUES (:name, :category)
            """
        ),
        {"name": name, "category": category},
    )


def _assert_position_unreferenced(conn: Connection, position_id: int) -> None:
    references = conn.execute(
        text(
            """
            SELECT child_ns.nspname AS schema_name,
                   child.relname AS table_name,
                   child_col.attname AS column_name
            FROM pg_constraint fk
            JOIN pg_class child ON child.oid = fk.conrelid
            JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
            JOIN LATERAL unnest(fk.conkey) WITH ORDINALITY child_key(attnum, ord)
              ON TRUE
            JOIN LATERAL unnest(fk.confkey) WITH ORDINALITY parent_key(attnum, ord)
              ON parent_key.ord = child_key.ord
            JOIN pg_attribute child_col
              ON child_col.attrelid = fk.conrelid
             AND child_col.attnum = child_key.attnum
            JOIN pg_attribute parent_col
              ON parent_col.attrelid = fk.confrelid
             AND parent_col.attnum = parent_key.attnum
            WHERE fk.contype = 'f'
              AND fk.confrelid = 'public.positions'::regclass
              AND parent_col.attname = 'position_id'
            ORDER BY child_ns.nspname, child.relname, child_col.attname
            """
        )
    ).mappings()

    for reference in references:
        schema = str(reference["schema_name"]).replace('"', '""')
        table = str(reference["table_name"]).replace('"', '""')
        column = str(reference["column_name"]).replace('"', '""')
        has_rows = conn.exec_driver_sql(
            f'SELECT EXISTS (SELECT 1 FROM "{schema}"."{table}" '
            f'WHERE "{column}" = %s)',
            (position_id,),
        ).scalar_one()
        if has_rows:
            raise RuntimeError(
                "Cannot remove duplicate position 'инженер': "
                f"position_id={position_id} is referenced by {schema}.{table}.{column}"
            )


def _ensure_engineer(conn: Connection) -> None:
    matches = _position_matches(conn, _ENGINEER)
    canonical = [
        row
        for row in matches
        if row["name"] == _ENGINEER and row["category"] == "technical"
    ]
    duplicate = [
        row
        for row in matches
        if row["name"] == _ENGINEER_DUPLICATE and row["category"] == "technical"
    ]
    accepted_ids = {
        int(row["position_id"])
        for row in canonical + duplicate
    }
    conflicting = [
        row for row in matches if int(row["position_id"]) not in accepted_ids
    ]

    if len(canonical) > 1 or len(duplicate) > 1 or conflicting:
        raise RuntimeError(f"Conflicting normalized position name for '{_ENGINEER}': {matches}")

    if duplicate:
        duplicate_id = int(duplicate[0]["position_id"])
        _assert_position_unreferenced(conn, duplicate_id)
        conn.execute(
            text("DELETE FROM public.positions WHERE position_id = :position_id"),
            {"position_id": duplicate_id},
        )

    if not canonical:
        _insert_position(conn, _ENGINEER, "technical")


def _ensure_positions(conn: Connection) -> None:
    conn.execute(text("LOCK TABLE public.positions IN SHARE ROW EXCLUSIVE MODE"))
    _ensure_engineer(conn)

    for name, category in _POSITIONS:
        matches = _position_matches(conn, name)
        if not matches:
            _insert_position(conn, name, category)
            continue
        if len(matches) == 1 and matches[0]["name"] == name and matches[0]["category"] == category:
            continue
        raise RuntimeError(f"Conflicting normalized position name for '{name}': {matches}")


def _one_by_code(conn: Connection, code: str, *, active: bool = True) -> dict[str, Any]:
    rows = [
        dict(row)
        for row in conn.execute(
            text(
                """
                SELECT unit_id, name, code, parent_unit_id, group_id, is_active
                FROM public.org_units
                WHERE lower(btrim(code)) = lower(btrim(:code))
                ORDER BY unit_id
                """
            ),
            {"code": code},
        ).mappings()
    ]
    if len(rows) != 1 or (active and rows[0]["is_active"] is not True):
        raise RuntimeError(f"Expected one active organizational unit with code '{code}': {rows}")
    return rows[0]


def _org_unit_matches(conn: Connection, *, code: str, name: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            f"""
            SELECT unit_id, name, code, parent_unit_id, group_id, is_active
            FROM public.org_units
            WHERE lower(btrim(code)) = lower(btrim(:code))
               OR {_normalized('name')} = {_normalized(':name')}
            ORDER BY unit_id
            """
        ),
        {"code": code, "name": name},
    ).mappings()
    return [dict(row) for row in rows]


def _same_unit(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def _ensure_unit(
    conn: Connection,
    *,
    expected: dict[str, Any],
    create_if_missing: bool,
) -> None:
    matches = _org_unit_matches(conn, code=str(expected["code"]), name=str(expected["name"]))
    if matches:
        if len(matches) == 1 and _same_unit(matches[0], expected):
            return
        raise RuntimeError(
            f"Conflicting organizational unit code/name for '{expected['code']}': {matches}"
        )
    if not create_if_missing:
        raise RuntimeError(
            f"Required existing organizational unit '{expected['code']}' is missing"
        )

    conn.execute(
        text(
            """
            INSERT INTO public.org_units
                (name, code, parent_unit_id, group_id, is_active)
            VALUES
                (:name, :code, :parent_unit_id, :group_id, :is_active)
            """
        ),
        expected,
    )


def _ensure_org_units(conn: Connection) -> None:
    conn.execute(text("LOCK TABLE public.org_units IN SHARE ROW EXCLUSIVE MODE"))
    dispensary = _one_by_code(conn, "DISP")
    root_unit_id = dispensary["parent_unit_id"]
    if root_unit_id is None:
        raise RuntimeError("DISP must have a parent organizational unit")
    root_is_active = conn.execute(
        text(
            """
            SELECT is_active
            FROM public.org_units
            WHERE unit_id = :unit_id
            """
        ),
        {"unit_id": root_unit_id},
    ).scalar_one_or_none()
    if root_is_active is not True:
        raise RuntimeError("DISP must reference an active parent organizational unit")

    common = {"is_active": True}
    _ensure_unit(
        conn,
        expected={
            **common,
            "name": "Трансфузиология",
            "code": "TRANSFUSE",
            "parent_unit_id": root_unit_id,
            "group_id": 2,
        },
        create_if_missing=True,
    )
    _ensure_unit(
        conn,
        expected={
            **common,
            "name": "Секция амбулаторной химиотерапии",
            "code": "Amb_chem",
            "parent_unit_id": dispensary["unit_id"],
            "group_id": 1,
        },
        create_if_missing=True,
    )
    _ensure_unit(
        conn,
        expected={
            **common,
            "name": "Комплаенс",
            "code": "COMPL",
            "parent_unit_id": root_unit_id,
            "group_id": 3,
        },
        create_if_missing=True,
    )


def upgrade() -> None:
    conn = op.get_bind()
    _ensure_positions(conn)
    _ensure_org_units(conn)


def downgrade() -> None:
    # TRANSFUSE belongs to s2t3u4v5w6x.  Position rows may also predate this
    # migration, so removing them here could damage assignments or reference data.
    op.execute(
        """
        DELETE FROM public.org_units target
        USING public.org_units dispensary
        WHERE dispensary.code = 'DISP'
          AND dispensary.is_active IS TRUE
          AND dispensary.parent_unit_id IS NOT NULL
          AND target.is_active IS TRUE
          AND (
              (target.name = 'Секция амбулаторной химиотерапии'
               AND target.code = 'Amb_chem'
               AND target.parent_unit_id = dispensary.unit_id
               AND target.group_id = 1)
              OR
              (target.name = 'Комплаенс'
               AND target.code = 'COMPL'
               AND target.parent_unit_id = dispensary.parent_unit_id
               AND target.group_id = 3)
          )
        """
    )
