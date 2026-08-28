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
    next_id = int(
        conn.execute(text("SELECT COALESCE(MAX(position_id), 0) + 1 FROM public.positions")).scalar_one()
    )
    conn.execute(
        text(
            """
            INSERT INTO public.positions (position_id, name, category)
            VALUES (:position_id, :name, :category)
            """
        ),
        {"position_id": next_id, "name": name, "category": category},
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
                SELECT unit_id, name, name_ru, name_en, code, parent_unit_id,
                       group_id, is_active, unit_type, org_level, sort_order1, sort_order2
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


def _one_group(conn: Connection, *names: str) -> int:
    conditions = " OR ".join(
        f"{_normalized('group_name')} = {_normalized(f':name_{index}')}"
        for index, _ in enumerate(names)
    )
    params = {f"name_{index}": name for index, name in enumerate(names)}
    rows = conn.execute(
        text(
            f"""
            SELECT group_id, group_name
            FROM public.deps_group
            WHERE {conditions}
            ORDER BY group_id
            """
        ),
        params,
    ).mappings().all()
    if len(rows) != 1:
        raise RuntimeError(f"Expected one organizational group named in {names}: {list(rows)}")
    return int(rows[0]["group_id"])


def _org_unit_matches(conn: Connection, *, code: str, name: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            f"""
            SELECT unit_id, name, name_ru, name_en, code, parent_unit_id,
                   group_id, is_active, unit_type, org_level, sort_order1, sort_order2
            FROM public.org_units
            WHERE lower(btrim(code)) = lower(btrim(:code))
               OR {_normalized('name')} = {_normalized(':name')}
               OR {_normalized("COALESCE(name_ru, name)")} = {_normalized(':name')}
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

    if expected["sort_order1"] is not None:
        sort_conflicts = conn.execute(
            text(
                """
                SELECT unit_id, code, name
                FROM public.org_units
                WHERE parent_unit_id = :parent_unit_id
                  AND group_id = :group_id
                  AND sort_order1 = :sort_order1
                ORDER BY unit_id
                """
            ),
            {
                "parent_unit_id": expected["parent_unit_id"],
                "group_id": expected["group_id"],
                "sort_order1": expected["sort_order1"],
            },
        ).mappings().all()
        if sort_conflicts:
            raise RuntimeError(
                f"Conflicting sort order for '{expected['code']}': {list(sort_conflicts)}"
            )

    conn.execute(
        text(
            """
            INSERT INTO public.org_units
                (name, name_ru, name_en, code, parent_unit_id, group_id, is_active,
                 unit_type, org_level, sort_order1, sort_order2)
            VALUES
                (:name, :name_ru, :name_en, :code, :parent_unit_id, :group_id, :is_active,
                 :unit_type, :org_level, :sort_order1, :sort_order2)
            """
        ),
        expected,
    )


def _ensure_org_units(conn: Connection) -> None:
    conn.execute(text("LOCK TABLE public.org_units IN SHARE ROW EXCLUSIVE MODE"))
    root = _one_by_code(conn, "ORG_MAIN")
    dispensary = _one_by_code(conn, "DISP")
    if dispensary["parent_unit_id"] != root["unit_id"]:
        raise RuntimeError("DISP must be a direct child of ORG_MAIN")

    clinical_group = _one_group(conn, "Клинические")
    paraclinical_group = _one_group(conn, "Параклинические")
    admin_group = _one_group(conn, "Адмхоз", "Административно-хозяйственные")

    common = {
        "is_active": True,
        "sort_order2": None,
    }
    _ensure_unit(
        conn,
        expected={
            **common,
            "name": "Трансфузиология",
            "name_ru": "Трансфузиология",
            "name_en": None,
            "code": "TRANSFUSE",
            "parent_unit_id": root["unit_id"],
            "group_id": paraclinical_group,
            "unit_type": None,
            "org_level": None,
            "sort_order1": None,
        },
        create_if_missing=False,
    )
    _ensure_unit(
        conn,
        expected={
            **common,
            "name": "Секция амбулаторной химиотерапии",
            "name_ru": "Секция амбулаторной химиотерапии",
            "name_en": "Amb chemotherapy section",
            "code": "Amb_chem",
            "parent_unit_id": dispensary["unit_id"],
            "group_id": clinical_group,
            "unit_type": "BRANCH",
            "org_level": 2,
            "sort_order1": 59,
        },
        create_if_missing=True,
    )
    _ensure_unit(
        conn,
        expected={
            **common,
            "name": "Комплаенс",
            "name_ru": "Комплаенс",
            "name_en": None,
            "code": "COMPL",
            "parent_unit_id": root["unit_id"],
            "group_id": admin_group,
            "unit_type": None,
            "org_level": None,
            "sort_order1": 58,
        },
        create_if_missing=True,
    )


def upgrade() -> None:
    conn = op.get_bind()
    _ensure_positions(conn)
    _ensure_org_units(conn)


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade of t3u4v5w6x7y is intentionally blocked: the migration may have "
        "accepted pre-existing reference rows and cannot identify ownership safely"
    )
