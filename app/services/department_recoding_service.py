"""Department recoding lookup — import department names → org_units (Phase 2F)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.models.department_recoding import (
    DEPARTMENT_GROUP_ADMINISTRATIVE,
    DEPARTMENT_GROUP_CLINICAL,
    DEPARTMENT_GROUP_PARACLINICAL,
)

DEFAULT_SEED_PATH = (
    Path(__file__).resolve().parents[1].parent / "scripts" / "data" / "department_recoding_seed.json"
)

_ADMIN_KEYWORDS = (
    "администр",
    "бухгалтер",
    "кадр",
    "хоз",
    "ахч",
    "it ",
    "it бөлім",
    "архив",
    "закуп",
    "эконом",
    "статотдел",
    "ситуацион",
    "менеджмен",
    "прач",
    "организацион",
    "методич",
    "фармацевт",
    "аптек",
    "провizor",
)

_PARACLINICAL_KEYWORDS = (
    "лабор",
    "кдл",
    "радиolog",
    "лучев",
    "цитolog",
    "патанатом",
    "патolog",
    "эндоскоп",
    "трансфуз",
    "рожто",
    "вцро",
    "цсо",
    "стерилиз",
    "диагност",
)


def _norm_name(value: str) -> str:
    text_val = (value or "").strip().lower().replace("ё", "е")
    return " ".join(text_val.split())


def infer_department_group(*, import_name: str, org_unit_name: str) -> str:
    combined = _norm_name(f"{import_name} {org_unit_name}")
    for kw in _ADMIN_KEYWORDS:
        if kw in combined:
            return DEPARTMENT_GROUP_ADMINISTRATIVE
    for kw in _PARACLINICAL_KEYWORDS:
        if kw in combined:
            return DEPARTMENT_GROUP_PARACLINICAL
    return DEPARTMENT_GROUP_CLINICAL


def _table_exists(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'department_recoding'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def _resolve_org_unit_id(conn: Connection, org_unit_name: str) -> Optional[int]:
    name = (org_unit_name or "").strip()
    if not name:
        return None
    row = conn.execute(
        text(
            """
            SELECT unit_id
            FROM public.org_units
            WHERE is_active = TRUE
              AND LOWER(TRIM(name)) = LOWER(TRIM(:name))
            ORDER BY unit_id
            LIMIT 1
            """
        ),
        {"name": name},
    ).first()
    if row:
        return int(row[0])
    row = conn.execute(
        text(
            """
            SELECT unit_id
            FROM public.org_units
            WHERE is_active = TRUE
              AND LOWER(name) LIKE LOWER(:pattern)
            ORDER BY LENGTH(name), unit_id
            LIMIT 1
            """
        ),
        {"pattern": f"%{name}%"},
    ).first()
    return int(row[0]) if row else None


def seed_department_recoding(
    conn: Connection,
    *,
    seed_path: Optional[Path] = None,
    replace: bool = False,
) -> dict[str, int]:
    if not _table_exists(conn):
        return {"inserted": 0, "updated": 0, "skipped": True}
    path = seed_path or DEFAULT_SEED_PATH
    if not path.exists():
        return {"inserted": 0, "updated": 0, "missing_seed": True}
    entries = json.loads(path.read_text(encoding="utf-8"))
    if replace:
        conn.execute(text("DELETE FROM public.department_recoding"))
    now = datetime.now(timezone.utc)
    inserted = 0
    updated = 0
    skipped_duplicates = 0
    seen_aliases: set[str] = set()
    for entry in entries:
        import_name = str(entry.get("import_department_name") or "").strip()
        org_unit_name = str(entry.get("org_unit_name") or "").strip()
        if not import_name:
            continue
        alias_key = _norm_name(import_name)
        if alias_key in seen_aliases:
            skipped_duplicates += 1
            continue
        seen_aliases.add(alias_key)
        org_unit_id = _resolve_org_unit_id(conn, org_unit_name)
        group = infer_department_group(import_name=import_name, org_unit_name=org_unit_name)
        existing = conn.execute(
            text(
                """
                SELECT id FROM public.department_recoding
                WHERE LOWER(TRIM(import_department_name)) = LOWER(TRIM(:name))
                LIMIT 1
                """
            ),
            {"name": import_name},
        ).first()
        if existing:
            conn.execute(
                text(
                    """
                    UPDATE public.department_recoding
                    SET org_unit_id = :org_unit_id,
                        org_unit_name = :org_unit_name,
                        department_group = :department_group,
                        is_active = TRUE,
                        updated_at = :updated_at
                    WHERE id = :id
                    """
                ),
                {
                    "id": int(existing[0]),
                    "org_unit_id": org_unit_id,
                    "org_unit_name": org_unit_name,
                    "department_group": group,
                    "updated_at": now,
                },
            )
            updated += 1
        else:
            conn.execute(
                text(
                    """
                    INSERT INTO public.department_recoding (
                        import_department_name, org_unit_id, org_unit_name,
                        department_group, is_active, created_at, updated_at
                    )
                    VALUES (
                        :import_department_name, :org_unit_id, :org_unit_name,
                        :department_group, TRUE, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "import_department_name": import_name,
                    "org_unit_id": org_unit_id,
                    "org_unit_name": org_unit_name,
                    "department_group": group,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            inserted += 1
    return {"inserted": inserted, "updated": updated, "skipped_duplicates": skipped_duplicates}


def _load_recoding_map(conn: Connection) -> dict[str, dict[str, Any]]:
    if not _table_exists(conn):
        return {}
    rows = conn.execute(
        text(
            """
            SELECT id, import_department_name, org_unit_id, org_unit_name, department_group
            FROM public.department_recoding
            WHERE is_active = TRUE
            """
        )
    ).mappings().all()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _norm_name(str(row["import_department_name"]))
        result[key] = dict(row)
    return result


def lookup_recoding(conn: Connection, import_department_name: str) -> Optional[dict[str, Any]]:
    """Resolve import alias → canonical org unit (exact normalized match only)."""
    key = _norm_name(import_department_name)
    if not key:
        return None
    mapping = _load_recoding_map(conn)
    return mapping.get(key)


def _canonical_option_key(org_unit_id: Any, org_unit_name: str) -> str:
    if org_unit_id is not None:
        return f"id:{int(org_unit_id)}"
    return f"name:{_norm_name(org_unit_name)}"


def _deps_group_table_exists(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'deps_group'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def _org_units_table_exists(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'org_units'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def load_org_unit_group_ids(conn: Connection) -> dict[int, int]:
    """Map org_units.unit_id → deps_group.group_id."""
    if not _org_units_table_exists(conn):
        return {}
    rows = conn.execute(
        text(
            """
            SELECT unit_id, group_id
            FROM public.org_units
            WHERE group_id IS NOT NULL
            """
        )
    ).mappings().all()
    result: dict[int, int] = {}
    for row in rows:
        try:
            unit_id = int(row["unit_id"])
            group_id = int(row["group_id"])
        except (TypeError, ValueError):
            continue
        if group_id >= 1:
            result[unit_id] = group_id
    return result


def list_recoding_options(conn: Connection) -> dict[str, Any]:
    """Groups from medical_org_groups registry; departments from org_units."""
    from app.medical_org_groups import list_filter_group_options

    if not _org_units_table_exists(conn):
        return {"groups": list_filter_group_options(), "departments": []}

    unit_rows = conn.execute(
        text(
            """
            SELECT unit_id, name, group_id
            FROM public.org_units
            WHERE COALESCE(is_active, TRUE) = TRUE
              AND group_id IS NOT NULL
            ORDER BY sort_order1 NULLS LAST, name
            """
        )
    ).mappings().all()

    groups = list_filter_group_options()
    departments = [
        {
            "org_unit_id": int(row["unit_id"]),
            "org_unit_name": str(row["name"] or "").strip(),
            "org_group_id": int(row["group_id"]),
        }
        for row in unit_rows
        if row.get("unit_id") is not None and row.get("group_id") is not None
    ]
    return {"groups": groups, "departments": departments}
