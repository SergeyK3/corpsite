# app/services/directory_import_csv.py
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import text

from app.db.engine import engine


# ============================================================
# IMPORT helpers (CSV)
# ============================================================
def _decode_csv_bytes(b: bytes) -> str:
    if not b:
        return ""

    # BOM UTF-8
    if b.startswith(b"\xef\xbb\xbf"):
        return b.decode("utf-8-sig")

    # UTF-16 BOM
    if b.startswith(b"\xff\xfe") or b.startswith(b"\xfe\xff"):
        return b.decode("utf-16")

    # Heuristic: many NULs => utf-16 variants
    if b[:200].count(b"\x00") > 10:
        for enc in ("utf-16le", "utf-16be", "utf-16"):
            try:
                return b.decode(enc, errors="strict")
            except UnicodeDecodeError:
                pass

    # Common encodings in RU/KZ exports
    for enc in ("utf-8", "utf-8-sig", "cp1251", "cp866", "koi8-r"):
        try:
            return b.decode(enc, errors="strict")
        except UnicodeDecodeError:
            continue

    # FAIL FAST: do NOT corrupt data with replacement characters.
    raise HTTPException(
        status_code=400,
        detail=(
            "Cannot decode CSV bytes as UTF-8/UTF-16/CP1251/CP866/KOI8-R without data loss. "
            "Re-export the CSV as UTF-8 (UTF-8 with BOM is OK) or provide a properly encoded file."
        ),
    )


def _sniff_delimiter(sample: str) -> str:
    semi = sample.count(";")
    comma = sample.count(",")
    return ";" if semi > comma else ","


def _norm_header(h: str) -> str:
    if h is None:
        return ""
    s = str(h).strip().lstrip("\ufeff")
    s = s.replace("\u00a0", " ")
    return s.strip().lower()


def _parse_bool(v: Optional[str]) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s == "":
        return None
    if s in ("1", "true", "yes", "y", "on", "да"):
        return True
    if s in ("0", "false", "no", "n", "off", "нет"):
        return False
    return None


def _parse_rate(v: Optional[str]) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date_any(v: Optional[str]) -> Optional[date]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None

    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

    return None


# ============================================================
# Dictionary helpers (departments/positions)
# ============================================================
def _get_columns(table: str, schema: str = "public") -> list[str]:
    q = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = :table
        ORDER BY ordinal_position
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(q, {"schema": schema, "table": table}).fetchall()
    return [r[0] for r in rows]


def _pick_first(existing: list[str], candidates: list[str]) -> Optional[str]:
    s = set(existing)
    for c in candidates:
        if c in s:
            return c
    return None


def _dept_table_meta() -> tuple[str, str]:
    cols = _get_columns("departments", "public")
    if not cols:
        raise HTTPException(status_code=500, detail="departments table not found.")
    id_col = _pick_first(cols, ["department_id", "id"])
    name_col = _pick_first(cols, ["name", "name_ru", "department_name", "dept_name"])
    if not id_col or not name_col:
        raise HTTPException(status_code=500, detail="departments table has no recognizable id/name columns.")
    return id_col, name_col


def _pos_table_meta() -> tuple[str, str]:
    cols = _get_columns("positions", "public")
    if not cols:
        raise HTTPException(status_code=500, detail="positions table not found.")
    id_col = _pick_first(cols, ["position_id", "id"])
    name_col = _pick_first(cols, ["name", "name_ru", "position_name", "pos_name"])
    if not id_col or not name_col:
        raise HTTPException(status_code=500, detail="positions table has no recognizable id/name columns.")
    return id_col, name_col


def _get_or_create_department_id(conn, name: str) -> int:
    name = name.strip()
    if not name:
        raise ValueError("department_name is empty")

    id_col, name_col = _dept_table_meta()

    row = conn.execute(
        text(f"SELECT {id_col} AS id FROM public.departments WHERE {name_col} = :name"),
        {"name": name},
    ).mappings().first()
    if row:
        return int(row["id"])

    row2 = conn.execute(
        text(
            f"""
            INSERT INTO public.departments ({name_col})
            VALUES (:name)
            ON CONFLICT ({name_col}) DO NOTHING
            RETURNING {id_col} AS id
            """
        ),
        {"name": name},
    ).mappings().first()

    if row2 and row2.get("id") is not None:
        return int(row2["id"])

    row3 = conn.execute(
        text(f"SELECT {id_col} AS id FROM public.departments WHERE {name_col} = :name"),
        {"name": name},
    ).mappings().first()
    if not row3:
        raise ValueError(f"cannot resolve department id for name={name}")
    return int(row3["id"])


def _get_or_create_position_id(conn, name: str) -> int:
    name = name.strip()
    if not name:
        raise ValueError("position_name is empty")

    id_col, name_col = _pos_table_meta()

    row = conn.execute(
        text(f"SELECT {id_col} AS id FROM public.positions WHERE {name_col} = :name"),
        {"name": name},
    ).mappings().first()
    if row:
        return int(row["id"])

    row2 = conn.execute(
        text(
            f"""
            INSERT INTO public.positions ({name_col})
            VALUES (:name)
            ON CONFLICT ({name_col}) DO NOTHING
            RETURNING {id_col} AS id
            """
        ),
        {"name": name},
    ).mappings().first()

    if row2 and row2.get("id") is not None:
        return int(row2["id"])

    row3 = conn.execute(
        text(f"SELECT {id_col} AS id FROM public.positions WHERE {name_col} = :name"),
        {"name": name},
    ).mappings().first()
    if not row3:
        raise ValueError(f"cannot resolve position id for name={name}")
    return int(row3["id"])


# ============================================================
# Public service API
# ============================================================
def import_employees_csv_bytes(*, raw: bytes) -> Dict[str, Any]:
    text_csv = _decode_csv_bytes(raw)
    if not text_csv.strip():
        raise HTTPException(status_code=400, detail="Empty CSV body.")

    delim = _sniff_delimiter(text_csv[:4096])
    f = io.StringIO(text_csv)
    reader = csv.DictReader(f, delimiter=delim)

    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no header row.")

    field_map: Dict[str, str] = {}
    for h in reader.fieldnames:
        field_map[_norm_header(h)] = h

    def col(name: str) -> Optional[str]:
        return field_map.get(name)

    c_emp = col("employee_id")
    c_name = col("full_name")
    c_dept = col("department_name")
    c_pos = col("position_name")

    if not (c_emp and c_name and c_dept and c_pos):
        raise HTTPException(
            status_code=400,
            detail="CSV header must include: employee_id, full_name, department_name, position_name.",
        )

    c_from = col("date_from")
    c_to = col("date_to")
    c_rate = col("employment_rate")
    c_active = col("is_active")

    rows_seen = 0
    emp_upserted = 0

    with engine.begin() as conn:
        dep_cache: Dict[str, int] = {}
        pos_cache: Dict[str, int] = {}

        for r in reader:
            rows_seen += 1

            employee_id = str((r.get(c_emp) or "")).strip()
            full_name = str((r.get(c_name) or "")).strip()
            dept_name = str((r.get(c_dept) or "")).strip()
            pos_name = str((r.get(c_pos) or "")).strip()

            if not employee_id or not full_name or not dept_name or not pos_name:
                continue

            if dept_name not in dep_cache:
                dep_cache[dept_name] = _get_or_create_department_id(conn, dept_name)

            if pos_name not in pos_cache:
                pos_cache[pos_name] = _get_or_create_position_id(conn, pos_name)

            department_id = dep_cache[dept_name]
            position_id = pos_cache[pos_name]

            date_from_v = _parse_date_any(r.get(c_from)) if c_from else None
            date_to_v = _parse_date_any(r.get(c_to)) if c_to else None
            rate_v = _parse_rate(r.get(c_rate)) if c_rate else None
            active_v = _parse_bool(r.get(c_active)) if c_active else None

            if rate_v is None:
                rate_v = 1.00
            if active_v is None:
                active_v = True
            if date_to_v is not None:
                active_v = False

            conn.execute(
                text(
                    """
                    INSERT INTO public.employees
                      (employee_id, full_name, department_id, position_id, date_from, date_to, employment_rate, is_active)
                    VALUES
                      (:employee_id, :full_name, :department_id, :position_id, :date_from, :date_to, :employment_rate, :is_active)
                    ON CONFLICT (employee_id) DO UPDATE SET
                      full_name = EXCLUDED.full_name,
                      department_id = EXCLUDED.department_id,
                      position_id = EXCLUDED.position_id,
                      date_from = EXCLUDED.date_from,
                      date_to = EXCLUDED.date_to,
                      employment_rate = EXCLUDED.employment_rate,
                      is_active = EXCLUDED.is_active
                    """
                ),
                {
                    "employee_id": employee_id,
                    "full_name": full_name,
                    "department_id": department_id,
                    "position_id": position_id,
                    "date_from": date_from_v,
                    "date_to": date_to_v,
                    "employment_rate": rate_v,
                    "is_active": active_v,
                },
            )
            emp_upserted += 1

    return {
        "rows_seen": rows_seen,
        "departments_touched": len(dep_cache),
        "positions_touched": len(pos_cache),
        "employees_upserted": emp_upserted,
        "delimiter": delim,
        "encoding": "auto(utf-8/cp1251)",
    }