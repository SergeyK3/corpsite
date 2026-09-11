"""Seed HR control-list department targets by stable organizational codes.

Revision ID: ppr005hdept01
Revises: ppr005gfull01
"""
from __future__ import annotations

from collections.abc import Mapping

from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection


revision = "ppr005hdept01"
down_revision = "ppr005gfull01"
branch_labels = None
depends_on = None


_UNITS = (
    ("SCREENING CENTER", "Скрининг центр", "DISP", "CLINICAL"),
    ("FOOD DEPARTMENT", "Пищеблок", "ROOT", "ADMINISTRATIVE"),
    ("PHYSICAL AND TECHNICAL DEPARTMENT", "Отдел физико-технический", "ROOT", "ADMINISTRATIVE"),
    ("ARCHIVE", "Архив", "ROOT", "ADMINISTRATIVE"),
)

_RECODINGS = (
    ("СКРИНИНГ ЦЕНТР", "SCREENING CENTER", "CLINICAL"),
    ("ПИЩЕБЛОК", "FOOD DEPARTMENT", "ADMINISTRATIVE"),
    ("Отдел физико-технический", "PHYSICAL AND TECHNICAL DEPARTMENT", "ADMINISTRATIVE"),
    ("АРХИВ", "ARCHIVE", "ADMINISTRATIVE"),
    ("IT бөлімі", "IT", "ADMINISTRATIVE"),
    ("ОБЩЕБОЛЬНИЧНЫЙ", "GENERAL", "ADMINISTRATIVE"),
    ("ОАХ", "Amb_chem", "CLINICAL"),
    ("КАБИНЕТ ТРАНСФУЗИОЛОГИИ", "TRANSFUSE", "PARACLINICAL"),
)

_NEW_ALIASES = frozenset({
    "СКРИНИНГ ЦЕНТР", "ПИЩЕБЛОК", "Отдел физико-технический",
    "ОБЩЕБОЛЬНИЧНЫЙ", "ОАХ",
})
_LEGACY_ALIAS_STATE = {
    "АРХИВ": ("Архив", "ADMINISTRATIVE", True),
    "IT бөлімі": ("IT", "ADMINISTRATIVE", True),
    "КАБИНЕТ ТРАНСФУЗИОЛОГИИ": ("Трансфузиология", "PARACLINICAL", True),
}


def _rows(conn: Connection, statement: str, **params: object) -> list[dict[str, object]]:
    return [dict(row) for row in conn.execute(text(statement), params).mappings()]


def _one_unit_by_code(conn: Connection, code: str) -> dict[str, object]:
    # Exact code is intentional.  It prevents an operator-facing seed from
    # silently selecting a similarly named unit or a case variant.
    rows = _rows(
        conn,
        """
        SELECT unit_id, name, code, parent_unit_id, group_id, is_active
        FROM public.org_units
        WHERE code = :code
        ORDER BY unit_id
        """,
        code=code,
    )
    if len(rows) != 1 or rows[0]["is_active"] is not True:
        raise RuntimeError(
            f"Expected exactly one active org_units.code={code!r}; found {len(rows)}"
        )
    return rows[0]


def _matching_units(conn: Connection, *, code: str, name: str) -> list[dict[str, object]]:
    return _rows(
        conn,
        """
        SELECT unit_id, name, code, parent_unit_id, group_id, is_active
        FROM public.org_units
        WHERE lower(btrim(code)) = lower(btrim(:code))
           OR lower(btrim(name)) = lower(btrim(:name))
        ORDER BY unit_id
        """,
        code=code,
        name=name,
    )


def _ensure_unit(
    conn: Connection,
    *,
    code: str,
    name: str,
    parent_unit_id: int,
    group_id: int,
) -> None:
    expected = {
        "name": name,
        "code": code,
        "parent_unit_id": parent_unit_id,
        "group_id": group_id,
        "is_active": True,
    }
    matches = _matching_units(conn, code=code, name=name)
    if matches:
        if len(matches) == 1 and all(matches[0][key] == value for key, value in expected.items()):
            return
        raise RuntimeError(
            "Conflicting lower(code) or canonical name for organizational unit "
            f"{code!r}/{name!r}: {matches}"
        )
    conn.execute(
        text(
            """
            INSERT INTO public.org_units(name, code, parent_unit_id, group_id, is_active)
            VALUES (:name, :code, :parent_unit_id, :group_id, :is_active)
            """
        ),
        expected,
    )


def _ensure_recoding(conn: Connection, *, import_name: str, target_code: str, department_group: str) -> None:
    target = _one_unit_by_code(conn, target_code)
    rows = _rows(
        conn,
        """
        SELECT id, is_active
        FROM public.department_recoding
        WHERE lower(btrim(import_department_name)) = lower(btrim(:import_name))
        ORDER BY id
        """,
        import_name=import_name,
    )
    if len(rows) > 1:
        raise RuntimeError(
            "Conflicting normalized department_recoding aliases for "
            f"{import_name!r}: {rows}"
        )
    values: Mapping[str, object] = {
        "import_name": import_name,
        "org_unit_id": target["unit_id"],
        "org_unit_name": target["name"],
        "department_group": department_group,
    }
    if rows:
        conn.execute(
            text(
                """
                UPDATE public.department_recoding
                SET org_unit_id = :org_unit_id,
                    org_unit_name = :org_unit_name,
                    department_group = :department_group,
                    is_active = TRUE,
                    updated_at = NOW()
                WHERE id = :id
                """
            ),
            {**values, "id": rows[0]["id"]},
        )
        return
    conn.execute(
        text(
            """
            INSERT INTO public.department_recoding(
                import_department_name, org_unit_id, org_unit_name,
                department_group, is_active
            ) VALUES (
                :import_name, :org_unit_id, :org_unit_name,
                :department_group, TRUE
            )
            """
        ),
        values,
    )


def upgrade() -> None:
    conn = op.get_bind()
    # The locks cover both conflict checks and idempotent insert/update.
    conn.execute(text("LOCK TABLE public.org_units IN SHARE ROW EXCLUSIVE MODE"))
    conn.execute(text("LOCK TABLE public.department_recoding IN SHARE ROW EXCLUSIVE MODE"))
    dispensary = _one_unit_by_code(conn, "DISP")
    general = _one_unit_by_code(conn, "GENERAL")
    information_technology = _one_unit_by_code(conn, "IT")
    root_id = dispensary["parent_unit_id"]
    if root_id is None:
        raise RuntimeError("DISP must have an active parent unit")
    root = _rows(
        conn,
        "SELECT unit_id, is_active FROM public.org_units WHERE unit_id = :unit_id",
        unit_id=root_id,
    )
    if len(root) != 1 or root[0]["is_active"] is not True:
        raise RuntimeError("DISP parent must be exactly one active organizational unit")
    if dispensary["group_id"] is None:
        raise RuntimeError("DISP must have a clinical group_id")
    if general["group_id"] is None or general["group_id"] != information_technology["group_id"]:
        raise RuntimeError("GENERAL and IT must share one non-null administrative group_id")
    for code, name, parent_kind, group_kind in _UNITS:
        parent_unit_id = int(dispensary["unit_id"]) if parent_kind == "DISP" else int(root_id)
        group_id = int(dispensary["group_id"]) if group_kind == "CLINICAL" else int(general["group_id"])
        _ensure_unit(
            conn,
            code=code,
            name=name,
            parent_unit_id=parent_unit_id,
            group_id=group_id,
        )
    for import_name, target_code, department_group in _RECODINGS:
        _ensure_recoding(
            conn,
            import_name=import_name,
            target_code=target_code,
            department_group=department_group,
        )
    expected_codes = {name: code for name, code, _group in _RECODINGS}
    actual = conn.execute(
        text(
            """
            SELECT lower(btrim(recoding.import_department_name)), unit.code
            FROM public.department_recoding recoding
            JOIN public.org_units unit ON unit.unit_id = recoding.org_unit_id
            WHERE recoding.is_active IS TRUE
              AND lower(btrim(recoding.import_department_name)) = ANY(:aliases)
            """
        ),
        {"aliases": [alias.strip().lower() for alias in expected_codes]},
    ).all()
    if {alias: code for alias, code in actual} != {
        alias.strip().lower(): code for alias, code in expected_codes.items()
    }:
        raise RuntimeError("Postcondition failed: department_recoding aliases do not resolve to expected codes")


def downgrade() -> None:
    conn = op.get_bind()
    expected_units = {code: name for code, name, _parent, _group in _UNITS}
    aliases = {alias: (code, group) for alias, code, group in _RECODINGS}
    dispensary = _one_unit_by_code(conn, "DISP")
    general = _one_unit_by_code(conn, "GENERAL")
    expected_context = {
        "SCREENING CENTER": ("Скрининг центр", dispensary["unit_id"], dispensary["group_id"], True),
        "FOOD DEPARTMENT": ("Пищеблок", dispensary["parent_unit_id"], general["group_id"], True),
        "PHYSICAL AND TECHNICAL DEPARTMENT": ("Отдел физико-технический", dispensary["parent_unit_id"], general["group_id"], True),
        "ARCHIVE": ("Архив", dispensary["parent_unit_id"], general["group_id"], True),
    }
    for code, expected in expected_context.items():
        actual_rows = _rows(conn, "SELECT name, parent_unit_id, group_id, is_active FROM public.org_units WHERE code=:code", code=code)
        if len(actual_rows) != 1 or tuple(actual_rows[0].values()) != expected:
            raise RuntimeError(f"Cannot downgrade ppr005hdept01: org unit {code!r} was changed")

    rows = conn.execute(
        text(
            """
            SELECT lower(btrim(recoding.import_department_name)) AS alias,
                   target.code, recoding.org_unit_name, recoding.department_group, recoding.is_active
            FROM public.department_recoding recoding
            JOIN public.org_units target ON target.unit_id = recoding.org_unit_id
            WHERE lower(btrim(recoding.import_department_name)) = ANY(:aliases)
            """
        ),
        {"aliases": [value.lower() for value in aliases]},
    ).all()
    target_names = {code: _one_unit_by_code(conn, code)["name"] for code, _group in aliases.values()}
    expected_aliases = {
        alias.lower(): (code, target_names[code], group)
        for alias, (code, group) in aliases.items()
    }
    if len(rows) != len(expected_aliases) or any(
        expected_aliases.get(row[0]) != (row[1], row[2], row[3]) or row[4] is not True
        for row in rows
    ):
        raise RuntimeError("Cannot downgrade ppr005hdept01: alias state was changed")

    # All guards passed; these are the only reversible alias changes.
    conn.execute(
        text("DELETE FROM public.department_recoding WHERE lower(btrim(import_department_name)) = ANY(:aliases)"),
        {"aliases": [alias.lower() for alias in _NEW_ALIASES]},
    )
    for alias, (name, group, active) in _LEGACY_ALIAS_STATE.items():
        result = conn.execute(
            text("""UPDATE public.department_recoding
                    SET org_unit_id=NULL, org_unit_name=:name, department_group=:group,
                        is_active=:active, updated_at=NOW()
                    WHERE lower(btrim(import_department_name))=lower(btrim(:alias))"""),
            {"alias": alias, "name": name, "group": group, "active": active},
        )
        if result.rowcount != 1:
            raise RuntimeError(f"Cannot downgrade ppr005hdept01: legacy alias {alias!r} missing")
    # No CASCADE: FK dependencies reject the ordinary delete.
    conn.execute(
        text("DELETE FROM public.org_units WHERE code = ANY(:codes)"),
        {"codes": list(expected_units)},
    )
