"""Employee import card (Карта2) — staging profile linked to directory employee."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.department_recoding_service import lookup_recoding
from app.services.hr_import_analytics_service import BatchNotFoundError, load_row_payload
from app.services.hr_import_education_profile_service import (
    PROFILE_STATUS_ACTIVE,
    REVIEW_STATUS_PENDING,
    _load_profile_meta,
    _profile_columns_available,
    _resolve_merged_profile,
)
from app.services.hr_import_profile_override_service import prepare_profile_override_for_storage


class EmployeeImportCardNotFoundError(LookupError):
    pass


_ROW_SELECT = """
    SELECT
        r.row_id,
        r.batch_id,
        r.source_sheet,
        r.source_row_number,
        r.employee_id
    FROM public.hr_import_rows r
    JOIN public.hr_import_batches b ON b.batch_id = r.batch_id
"""


def _norm_name(value: str) -> str:
    text_val = (value or "").strip().lower().replace("ё", "е")
    return " ".join(text_val.split())


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _row_preference_order() -> str:
    """Prefer roster rows with a valid 12-digit IIN, then newest batch."""
    return """
        CASE
            WHEN length(regexp_replace(COALESCE(r.normalized_payload->>'iin', ''), '[^0-9]', '', 'g')) = 12
            THEN 0
            ELSE 1
        END,
        b.imported_at DESC NULLS LAST,
        r.row_id DESC
    """


def _roster_row_filters() -> str:
    return """
        COALESCE(r.normalized_payload->'metadata'->>'sheet_type', '') <> 'declaration'
        AND COALESCE((r.normalized_payload->'metadata'->>'is_employee_roster')::boolean, TRUE) = TRUE
    """


def _find_import_row_for_employee(conn: Connection, employee_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        text(
            f"""
            {_ROW_SELECT}
            WHERE r.employee_id = :employee_id
            ORDER BY {_row_preference_order()}
            LIMIT 1
            """
        ),
        {"employee_id": employee_id},
    ).mappings().first()
    if row:
        return dict(row)

    iin_row = conn.execute(
        text(
            """
            SELECT ei.identity_value
            FROM public.employee_identities ei
            WHERE ei.employee_id = :employee_id
              AND ei.identity_type = 'IIN'
              AND ei.valid_to IS NULL
            ORDER BY ei.is_primary DESC, ei.identity_id
            LIMIT 1
            """
        ),
        {"employee_id": employee_id},
    ).first()
    iin_digits = _digits_only(str(iin_row[0])) if iin_row and iin_row[0] else ""
    if iin_digits:
        row = conn.execute(
            text(
                f"""
                {_ROW_SELECT}
                WHERE regexp_replace(COALESCE(r.normalized_payload->>'iin', ''), '[^0-9]', '', 'g') = :iin
                  AND {_roster_row_filters()}
                ORDER BY {_row_preference_order()}
                LIMIT 1
                """
            ),
            {"iin": iin_digits},
        ).mappings().first()
        if row:
            return dict(row)

    emp = conn.execute(
        text("SELECT full_name FROM public.employees WHERE employee_id = :employee_id"),
        {"employee_id": employee_id},
    ).first()
    if not emp or not str(emp[0] or "").strip():
        return None

    norm_name = _norm_name(str(emp[0]))
    row = conn.execute(
        text(
            f"""
            {_ROW_SELECT}
            WHERE lower(replace(trim(r.normalized_payload->>'full_name'), 'ё', 'е')) = :norm_name
              AND {_roster_row_filters()}
            ORDER BY {_row_preference_order()}
            LIMIT 1
            """
        ),
        {"norm_name": norm_name},
    ).mappings().first()
    return dict(row) if row else None


def get_employee_import_card(conn: Connection, employee_id: int) -> dict[str, Any]:
    loc = _find_import_row_for_employee(conn, employee_id)
    if not loc:
        raise EmployeeImportCardNotFoundError(f"import card not found for employee_id={employee_id}")

    batch_id = int(loc["batch_id"])
    row_id = int(loc["row_id"])
    staging = load_row_payload(conn, batch_id, row_id)
    payload = staging["payload"]
    metadata = staging["metadata"]
    department = str(payload.get("department", "") or "").strip()
    recoding = lookup_recoding(conn, department)
    meta = _load_profile_meta(conn, batch_id, row_id)
    profile = _resolve_merged_profile(payload, meta)

    return {
        "batch_id": batch_id,
        "row_id": row_id,
        "profile_id": row_id,
        "employee_id": employee_id,
        "source_sheet": staging["source_sheet"],
        "source_row_number": staging["source_row_number"],
        "full_name": str(payload.get("full_name", "") or ""),
        "department_source": department,
        "department_recoding": {
            "org_unit_id": int(recoding["org_unit_id"]) if recoding and recoding.get("org_unit_id") else None,
            "org_unit_name": recoding["org_unit_name"] if recoding else "",
            "department_group": recoding["department_group"] if recoding else "",
        }
        if recoding
        else None,
        "position_raw": str(payload.get("position_raw", "") or ""),
        "sheet_type": metadata.get("sheet_type", ""),
        "profile": profile,
        "profile_status": meta["profile_status"],
        "review_status": meta["profile_review_status"],
        "has_override": bool(meta.get("profile_override")),
    }


def save_employee_import_card(
    conn: Connection,
    employee_id: int,
    *,
    profile: dict[str, Any],
) -> dict[str, Any]:
    if not _profile_columns_available(conn):
        raise BatchNotFoundError("profile staging columns not available — run alembic upgrade head")

    loc = _find_import_row_for_employee(conn, employee_id)
    if not loc:
        raise EmployeeImportCardNotFoundError(f"import card not found for employee_id={employee_id}")

    batch_id = int(loc["batch_id"])
    row_id = int(loc["row_id"])
    override = prepare_profile_override_for_storage(profile)
    conn.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET profile_override = CAST(:profile_override AS JSONB),
                profile_status = COALESCE(profile_status, :profile_status),
                profile_review_status = COALESCE(profile_review_status, :review_status)
            WHERE batch_id = :batch_id AND row_id = :row_id
            """
        ),
        {
            "batch_id": batch_id,
            "row_id": row_id,
            "profile_override": json.dumps(override, ensure_ascii=False),
            "profile_status": PROFILE_STATUS_ACTIVE,
            "review_status": REVIEW_STATUS_PENDING,
        },
    )
    return get_employee_import_card(conn, employee_id)


def delete_employee_import_card(conn: Connection, employee_id: int) -> dict[str, Any]:
    if not _profile_columns_available(conn):
        raise BatchNotFoundError("profile staging columns not available — run alembic upgrade head")

    loc = _find_import_row_for_employee(conn, employee_id)
    if not loc:
        raise EmployeeImportCardNotFoundError(f"import card not found for employee_id={employee_id}")

    batch_id = int(loc["batch_id"])
    row_id = int(loc["row_id"])
    conn.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET profile_override = NULL
            WHERE batch_id = :batch_id AND row_id = :row_id
            """
        ),
        {"batch_id": batch_id, "row_id": row_id},
    )
    return get_employee_import_card(conn, employee_id)
