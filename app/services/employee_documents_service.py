# FILE: app/services/employee_documents_service.py
"""ADR-037 Phase 1A/1B: production employee documents registry."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from app.db.engine import engine

EXPIRY_WARN_60_DAYS = 60
EXPIRY_WARN_30_DAYS = 30

DEFAULT_TRAINING_HOURS_REQUIRED = 144
TRAINING_WINDOW_YEARS = 5

TRAINING_HOURS_STATUS_MET = "MET"
TRAINING_HOURS_STATUS_BELOW = "BELOW"
TRAINING_HOURS_STATUS_EMPTY = "EMPTY"
TRAINING_HOURS_STATUS_INCOMPLETE = "INCOMPLETE"

EXPIRY_STATUS_VALUES = frozenset(
    {"VALID", "EXPIRING_60", "EXPIRING_30", "EXPIRED", "NO_EXPIRY"}
)

LIFECYCLE_ACTIVE = "ACTIVE"
LIFECYCLE_SUPERSEDED = "SUPERSEDED"
LIFECYCLE_DRAFT = "DRAFT"

FILE_URL_MAX_LEN = 2000


class EmployeeDocumentValidationError(ValueError):
    """Business validation error for employee document payloads."""


class EmployeeDocumentNotFoundError(LookupError):
    """Referenced employee or document not found."""


def _table_exists(conn, table: str, schema: str = "public") -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :table
            LIMIT 1
            """
        ),
        {"schema": schema, "table": table},
    ).first()
    return row is not None


def employee_documents_available() -> bool:
    with engine.begin() as conn:
        return (
            _table_exists(conn, "employee_documents")
            and _table_exists(conn, "document_types")
            and _table_exists(conn, "document_kinds")
        )


def compute_expiry_status(
    valid_until: Optional[date],
    *,
    today: Optional[date] = None,
) -> str:
    if valid_until is None:
        return "NO_EXPIRY"
    ref = today or date.today()
    days_left = (valid_until - ref).days
    if days_left < 0:
        return "EXPIRED"
    if days_left <= EXPIRY_WARN_30_DAYS:
        return "EXPIRING_30"
    if days_left <= EXPIRY_WARN_60_DAYS:
        return "EXPIRING_60"
    return "VALID"


def _expiry_status_sql(alias: str = "ed") -> str:
    return f"""
        CASE
            WHEN {alias}.valid_until IS NULL THEN 'NO_EXPIRY'
            WHEN {alias}.valid_until < CURRENT_DATE THEN 'EXPIRED'
            WHEN {alias}.valid_until <= CURRENT_DATE + INTERVAL '{EXPIRY_WARN_30_DAYS} days'
                THEN 'EXPIRING_30'
            WHEN {alias}.valid_until <= CURRENT_DATE + INTERVAL '{EXPIRY_WARN_60_DAYS} days'
                THEN 'EXPIRING_60'
            ELSE 'VALID'
        END
    """


def _serialize_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _serialize_ts(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _map_document_row(row: Dict[str, Any]) -> Dict[str, Any]:
    valid_until = row.get("valid_until")
    if isinstance(valid_until, date):
        expiry_status = compute_expiry_status(valid_until)
    else:
        expiry_status = row.get("expiry_status") or "NO_EXPIRY"

    return {
        "document_id": int(row["document_id"]),
        "employee_id": int(row["employee_id"]),
        "employee_name": str(row.get("employee_name") or ""),
        "employee_is_active": bool(row.get("employee_is_active", True)),
        "document_type_id": int(row["document_type_id"]),
        "document_type_code": str(row.get("document_type_code") or ""),
        "document_type_name": str(row.get("document_type_name") or ""),
        "document_kind_id": int(row["document_kind_id"])
        if row.get("document_kind_id") is not None
        else None,
        "document_kind_code": str(row.get("document_kind_code") or "")
        if row.get("document_kind_code") is not None
        else None,
        "document_kind_name": str(row.get("document_kind_name") or "")
        if row.get("document_kind_name") is not None
        else None,
        "medical_specialty_id": int(row["medical_specialty_id"])
        if row.get("medical_specialty_id") is not None
        else None,
        "medical_specialty_name": str(row.get("medical_specialty_name") or "")
        if row.get("medical_specialty_name") is not None
        else None,
        "medical_specialty_group_id": int(row["medical_specialty_group_id"])
        if row.get("medical_specialty_group_id") is not None
        else None,
        "title": row.get("title"),
        "training_title": row.get("training_title"),
        "document_number": row.get("document_number"),
        "issued_by": row.get("issued_by"),
        "issued_at": _serialize_date(row.get("issued_at")),
        "hours": int(row["hours"]) if row.get("hours") is not None else None,
        "tracks_hours": bool(row.get("tracks_hours", False)),
        "valid_until": _serialize_date(valid_until),
        "file_url": row.get("file_url"),
        "comment": row.get("comment"),
        "lifecycle_status": str(row.get("lifecycle_status") or LIFECYCLE_ACTIVE),
        "expiry_status": str(expiry_status),
        "created_by": int(row["created_by"]),
        "created_at": _serialize_ts(row.get("created_at")),
        "updated_at": _serialize_ts(row.get("updated_at")),
    }


def _load_document_kind(conn, document_kind_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT document_kind_id, code, name, is_active
            FROM public.document_kinds
            WHERE document_kind_id = :document_kind_id
            """
        ),
        {"document_kind_id": int(document_kind_id)},
    ).mappings().first()
    return dict(row) if row else None


def _load_document_type(conn, document_type_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT
                document_type_id,
                code,
                name,
                category,
                has_valid_until,
                requires_medical_specialty,
                tracks_hours,
                is_active
            FROM public.document_types
            WHERE document_type_id = :document_type_id
            """
        ),
        {"document_type_id": int(document_type_id)},
    ).mappings().first()
    return dict(row) if row else None


def _load_specialty(conn, medical_specialty_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        text(
            """
            SELECT medical_specialty_id, group_id, code, name, is_active
            FROM public.medical_specialties
            WHERE medical_specialty_id = :medical_specialty_id
            """
        ),
        {"medical_specialty_id": int(medical_specialty_id)},
    ).mappings().first()
    return dict(row) if row else None


def _employee_exists(conn, employee_id: int) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM public.employees
            WHERE employee_id = :employee_id
            LIMIT 1
            """
        ),
        {"employee_id": int(employee_id)},
    ).first()
    return row is not None


def _training_window_start(as_of: date) -> date:
    """Rolling N-year window start (inclusive), calendar-aware via PostgreSQL in queries."""
    try:
        return as_of.replace(year=as_of.year - TRAINING_WINDOW_YEARS)
    except ValueError:
        # Feb 29 → Feb 28 on non-leap target year
        return as_of.replace(year=as_of.year - TRAINING_WINDOW_YEARS, day=28)


def _validate_hours_for_type(
    doc_type: Dict[str, Any],
    *,
    hours: Optional[int],
    issued_at: Optional[date],
    lifecycle_status: str,
) -> Optional[int]:
    tracks = bool(doc_type.get("tracks_hours"))
    if not tracks:
        if hours is not None:
            raise EmployeeDocumentValidationError(
                "hours must be null for this document type."
            )
        return None

    if lifecycle_status == LIFECYCLE_SUPERSEDED:
        if hours is not None and int(hours) < 0:
            raise EmployeeDocumentValidationError("hours must be >= 0.")
        return int(hours) if hours is not None else None

    if issued_at is None:
        raise EmployeeDocumentValidationError(
            "issued_at is required for this document type."
        )
    if hours is None:
        raise EmployeeDocumentValidationError("hours is required for this document type.")
    hours_int = int(hours)
    if hours_int <= 0:
        raise EmployeeDocumentValidationError(
            "hours must be greater than 0 for this document type."
        )
    return hours_int


def _validate_lifecycle_for_api(lifecycle_status: Optional[str], *, on_create: bool) -> str:
    status = (lifecycle_status or LIFECYCLE_ACTIVE).strip().upper()
    if status == LIFECYCLE_DRAFT:
        raise EmployeeDocumentValidationError("lifecycle_status DRAFT is not accepted in Phase 1A.")
    if on_create and status != LIFECYCLE_ACTIVE:
        raise EmployeeDocumentValidationError("Only lifecycle_status ACTIVE is allowed on create.")
    if not on_create and status not in {LIFECYCLE_ACTIVE, LIFECYCLE_SUPERSEDED}:
        raise EmployeeDocumentValidationError(
            "lifecycle_status must be ACTIVE or SUPERSEDED."
        )
    return status


def _validate_payload(
    conn,
    *,
    document_type_id: int,
    document_kind_id: Optional[int],
    medical_specialty_id: Optional[int],
    issued_at: Optional[date],
    hours: Optional[int],
    valid_until: Optional[date],
    file_url: Optional[str],
    lifecycle_status: Optional[str],
    on_create: bool,
) -> Tuple[Dict[str, Any], str, Optional[int]]:
    doc_type = _load_document_type(conn, document_type_id)
    if doc_type is None:
        raise EmployeeDocumentValidationError("document_type_id not found.")
    if not bool(doc_type.get("is_active")):
        raise EmployeeDocumentValidationError("document_type is not active.")

    if document_kind_id is not None:
        doc_kind = _load_document_kind(conn, document_kind_id)
        if doc_kind is None:
            raise EmployeeDocumentValidationError("document_kind_id not found.")
        if not bool(doc_kind.get("is_active")):
            raise EmployeeDocumentValidationError("document_kind is not active.")

    status = _validate_lifecycle_for_api(lifecycle_status, on_create=on_create)

    if bool(doc_type.get("requires_medical_specialty")):
        if medical_specialty_id is None:
            raise EmployeeDocumentValidationError(
                "medical_specialty_id is required for this document type."
            )
    if medical_specialty_id is not None:
        specialty = _load_specialty(conn, medical_specialty_id)
        if specialty is None:
            raise EmployeeDocumentValidationError("medical_specialty_id not found.")
        if not bool(specialty.get("is_active")):
            raise EmployeeDocumentValidationError("medical_specialty is not active.")

    if bool(doc_type.get("has_valid_until")):
        if valid_until is None:
            raise EmployeeDocumentValidationError("valid_until is required for this document type.")
    elif valid_until is not None:
        raise EmployeeDocumentValidationError(
            "valid_until must be null for this document type."
        )

    if file_url is not None:
        url = str(file_url).strip()
        if len(url) > FILE_URL_MAX_LEN:
            raise EmployeeDocumentValidationError(
                f"file_url must be at most {FILE_URL_MAX_LEN} characters."
            )
        file_url = url or None

    validated_hours = _validate_hours_for_type(
        doc_type,
        hours=hours,
        issued_at=issued_at,
        lifecycle_status=status,
    )

    return doc_type, status, validated_hours


def _select_documents_base_sql() -> str:
    expiry_sql = _expiry_status_sql("ed")
    return f"""
        SELECT
            ed.document_id,
            ed.employee_id,
            e.full_name AS employee_name,
            COALESCE(e.is_active, TRUE) AS employee_is_active,
            ed.document_type_id,
            dt.code AS document_type_code,
            dt.name AS document_type_name,
            ed.document_kind_id,
            dk.code AS document_kind_code,
            dk.name AS document_kind_name,
            ed.medical_specialty_id,
            ms.name AS medical_specialty_name,
            ms.group_id AS medical_specialty_group_id,
            ed.title,
            ed.training_title,
            ed.document_number,
            ed.issued_by,
            ed.issued_at,
            ed.hours,
            dt.tracks_hours,
            ed.valid_until,
            ed.file_url,
            ed.comment,
            ed.lifecycle_status,
            ed.created_by,
            ed.created_at,
            ed.updated_at,
            {expiry_sql} AS expiry_status
        FROM public.employee_documents ed
        JOIN public.employees e ON e.employee_id = ed.employee_id
        JOIN public.document_types dt ON dt.document_type_id = ed.document_type_id
        LEFT JOIN public.document_kinds dk ON dk.document_kind_id = ed.document_kind_id
        LEFT JOIN public.medical_specialties ms
            ON ms.medical_specialty_id = ed.medical_specialty_id
    """


def _fetch_document_by_id(conn, document_id: int) -> Optional[Dict[str, Any]]:
    sql = _select_documents_base_sql() + " WHERE ed.document_id = :document_id"
    row = conn.execute(text(sql), {"document_id": int(document_id)}).mappings().first()
    return _map_document_row(dict(row)) if row else None


def list_document_types(*, is_active: bool = True) -> Dict[str, Any]:
    if not employee_documents_available():
        return {"items": [], "total": 0}

    where = "WHERE is_active = TRUE" if is_active else ""
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT
                    document_type_id,
                    code,
                    name,
                    category,
                    has_valid_until,
                    requires_medical_specialty,
                    tracks_hours,
                    is_active,
                    sort_order
                FROM public.document_types
                {where}
                ORDER BY sort_order, name
                """
            )
        ).mappings().all()

    items = [
        {
            "document_type_id": int(r["document_type_id"]),
            "code": str(r["code"]),
            "name": str(r["name"]),
            "category": str(r["category"]),
            "has_valid_until": bool(r["has_valid_until"]),
            "requires_medical_specialty": bool(r["requires_medical_specialty"]),
            "tracks_hours": bool(r["tracks_hours"]),
            "is_active": bool(r["is_active"]),
            "sort_order": int(r["sort_order"]),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def list_document_kinds(*, is_active: bool = True) -> Dict[str, Any]:
    if not employee_documents_available():
        return {"items": [], "total": 0}

    where = "WHERE is_active = TRUE" if is_active else ""
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT
                    document_kind_id,
                    code,
                    name,
                    is_active,
                    sort_order
                FROM public.document_kinds
                {where}
                ORDER BY sort_order, name
                """
            )
        ).mappings().all()

    items = [
        {
            "document_kind_id": int(r["document_kind_id"]),
            "code": str(r["code"]),
            "name": str(r["name"]),
            "is_active": bool(r["is_active"]),
            "sort_order": int(r["sort_order"]),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def list_medical_specialty_groups() -> Dict[str, Any]:
    if not employee_documents_available():
        return {"items": [], "total": 0}

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT group_id, code, name, is_active
                FROM public.medical_specialty_groups
                WHERE is_active = TRUE
                ORDER BY code
                """
            )
        ).mappings().all()

    items = [
        {
            "group_id": int(r["group_id"]),
            "code": str(r["code"]),
            "name": str(r["name"]),
            "is_active": bool(r["is_active"]),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def list_medical_specialties(
    *,
    group_id: Optional[int] = None,
    group_code: Optional[str] = None,
    is_active: bool = True,
) -> Dict[str, Any]:
    if not employee_documents_available():
        return {"items": [], "total": 0}

    clauses = ["1=1"]
    params: Dict[str, Any] = {}
    if is_active:
        clauses.append("ms.is_active = TRUE")
    if group_id is not None:
        clauses.append("ms.group_id = :group_id")
        params["group_id"] = int(group_id)
    if group_code:
        clauses.append("g.code = :group_code")
        params["group_code"] = str(group_code).strip().upper()

    where_sql = " AND ".join(clauses)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT
                    ms.medical_specialty_id,
                    ms.group_id,
                    g.code AS group_code,
                    ms.code,
                    ms.name,
                    ms.is_active
                FROM public.medical_specialties ms
                JOIN public.medical_specialty_groups g ON g.group_id = ms.group_id
                WHERE {where_sql}
                ORDER BY g.code, ms.name
                """
            ),
            params,
        ).mappings().all()

    items = [
        {
            "medical_specialty_id": int(r["medical_specialty_id"]),
            "group_id": int(r["group_id"]),
            "group_code": str(r["group_code"]),
            "code": str(r["code"]),
            "name": str(r["name"]),
            "is_active": bool(r["is_active"]),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def list_employee_documents(
    *,
    employee_id: Optional[int] = None,
    employee_is_active: Optional[bool] = None,
    document_type_id: Optional[int] = None,
    medical_specialty_id: Optional[int] = None,
    group_id: Optional[int] = None,
    lifecycle_status: str = LIFECYCLE_ACTIVE,
    expiry_status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    if not employee_documents_available():
        return {"items": [], "total": 0}

    if expiry_status is not None:
        key = str(expiry_status).strip().upper()
        if key not in EXPIRY_STATUS_VALUES:
            raise EmployeeDocumentValidationError(f"Invalid expiry_status: {expiry_status}")
        expiry_status = key

    expiry_sql = _expiry_status_sql("ed")
    clauses = ["1=1"]
    params: Dict[str, Any] = {
        "limit": int(limit),
        "offset": int(offset),
    }

    if lifecycle_status:
        clauses.append("ed.lifecycle_status = :lifecycle_status")
        params["lifecycle_status"] = str(lifecycle_status).strip().upper()

    if employee_id is not None:
        clauses.append("ed.employee_id = :employee_id")
        params["employee_id"] = int(employee_id)

    if employee_is_active is not None:
        clauses.append("COALESCE(e.is_active, TRUE) = :employee_is_active")
        params["employee_is_active"] = bool(employee_is_active)

    if document_type_id is not None:
        clauses.append("ed.document_type_id = :document_type_id")
        params["document_type_id"] = int(document_type_id)

    if medical_specialty_id is not None:
        clauses.append("ed.medical_specialty_id = :medical_specialty_id")
        params["medical_specialty_id"] = int(medical_specialty_id)

    if group_id is not None:
        clauses.append("ms.group_id = :group_id")
        params["group_id"] = int(group_id)

    if expiry_status is not None:
        clauses.append(f"({expiry_sql}) = :expiry_status")
        params["expiry_status"] = expiry_status

    if q:
        clauses.append(
            """
            (
                e.full_name ILIKE :q_pattern
                OR COALESCE(ed.title, '') ILIKE :q_pattern
                OR COALESCE(ed.training_title, '') ILIKE :q_pattern
                OR COALESCE(ed.document_number, '') ILIKE :q_pattern
            )
            """
        )
        params["q_pattern"] = f"%{str(q).strip()}%"

    where_sql = " AND ".join(clauses)
    base = _select_documents_base_sql()

    with engine.begin() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) AS cnt FROM ({base} WHERE {where_sql}) sub"),
            params,
        ).scalar()
        rows = conn.execute(
            text(
                f"""
                {base}
                WHERE {where_sql}
                ORDER BY e.full_name, dt.sort_order, ed.document_id
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings().all()

    items = [_map_document_row(dict(r)) for r in rows]
    return {"items": items, "total": int(total or 0)}


def get_employee_document(document_id: int) -> Optional[Dict[str, Any]]:
    if not employee_documents_available():
        return None
    with engine.begin() as conn:
        return _fetch_document_by_id(conn, int(document_id))


def create_employee_document(
    *,
    employee_id: int,
    document_type_id: int,
    created_by: int,
    document_kind_id: Optional[int] = None,
    medical_specialty_id: Optional[int] = None,
    title: Optional[str] = None,
    training_title: Optional[str] = None,
    document_number: Optional[str] = None,
    issued_by: Optional[str] = None,
    issued_at: Optional[date] = None,
    hours: Optional[int] = None,
    valid_until: Optional[date] = None,
    file_url: Optional[str] = None,
    comment: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
) -> Dict[str, Any]:
    if not employee_documents_available():
        raise RuntimeError("employee_documents tables are not available")

    with engine.begin() as conn:
        if not _employee_exists(conn, employee_id):
            raise EmployeeDocumentNotFoundError("employee_id not found.")

        _, status, validated_hours = _validate_payload(
            conn,
            document_type_id=document_type_id,
            document_kind_id=document_kind_id,
            medical_specialty_id=medical_specialty_id,
            issued_at=issued_at,
            hours=hours,
            valid_until=valid_until,
            file_url=file_url,
            lifecycle_status=lifecycle_status,
            on_create=True,
        )

        row = conn.execute(
            text(
                """
                INSERT INTO public.employee_documents (
                    employee_id,
                    document_type_id,
                    document_kind_id,
                    medical_specialty_id,
                    title,
                    training_title,
                    document_number,
                    issued_by,
                    issued_at,
                    hours,
                    valid_until,
                    file_url,
                    comment,
                    lifecycle_status,
                    created_by
                )
                VALUES (
                    :employee_id,
                    :document_type_id,
                    :document_kind_id,
                    :medical_specialty_id,
                    :title,
                    :training_title,
                    :document_number,
                    :issued_by,
                    :issued_at,
                    :hours,
                    :valid_until,
                    :file_url,
                    :comment,
                    :lifecycle_status,
                    :created_by
                )
                RETURNING document_id
                """
            ),
            {
                "employee_id": int(employee_id),
                "document_type_id": int(document_type_id),
                "document_kind_id": int(document_kind_id)
                if document_kind_id is not None
                else None,
                "medical_specialty_id": int(medical_specialty_id)
                if medical_specialty_id is not None
                else None,
                "title": title,
                "training_title": training_title,
                "document_number": document_number,
                "issued_by": issued_by,
                "issued_at": issued_at,
                "hours": validated_hours,
                "valid_until": valid_until,
                "file_url": file_url,
                "comment": comment,
                "lifecycle_status": status,
                "created_by": int(created_by),
            },
        ).mappings().first()
        document_id = int(row["document_id"])
        item = _fetch_document_by_id(conn, document_id)
        if item is None:
            raise RuntimeError("Failed to load created employee document.")
        return item


def update_employee_document(
    document_id: int,
    *,
    document_type_id: Optional[int] = None,
    document_kind_id: Optional[int] = None,
    clear_document_kind: bool = False,
    medical_specialty_id: Optional[int] = None,
    clear_medical_specialty: bool = False,
    title: Optional[str] = None,
    training_title: Optional[str] = None,
    document_number: Optional[str] = None,
    issued_by: Optional[str] = None,
    issued_at: Optional[date] = None,
    hours: Optional[int] = None,
    valid_until: Optional[date] = None,
    clear_valid_until: bool = False,
    file_url: Optional[str] = None,
    clear_file_url: bool = False,
    comment: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not employee_documents_available():
        raise RuntimeError("employee_documents tables are not available")

    with engine.begin() as conn:
        existing = conn.execute(
            text(
                """
                SELECT *
                FROM public.employee_documents
                WHERE document_id = :document_id
                """
            ),
            {"document_id": int(document_id)},
        ).mappings().first()
        if not existing:
            return None

        merged_type_id = int(document_type_id or existing["document_type_id"])

        if clear_document_kind:
            merged_kind_id = None
        elif document_kind_id is not None:
            merged_kind_id = int(document_kind_id)
        else:
            merged_kind_id = existing.get("document_kind_id")

        if clear_medical_specialty:
            merged_specialty_id = None
        elif medical_specialty_id is not None:
            merged_specialty_id = int(medical_specialty_id)
        else:
            merged_specialty_id = existing.get("medical_specialty_id")

        if clear_valid_until:
            merged_valid_until = None
        elif valid_until is not None:
            merged_valid_until = valid_until
        else:
            merged_valid_until = existing.get("valid_until")

        if clear_file_url:
            merged_file_url = None
        elif file_url is not None:
            merged_file_url = file_url
        else:
            merged_file_url = existing.get("file_url")

        merged_issued_at = issued_at if issued_at is not None else existing.get("issued_at")

        merged_hours = hours if hours is not None else existing.get("hours")

        merged_lifecycle = (
            lifecycle_status if lifecycle_status is not None else existing.get("lifecycle_status")
        )

        _, status, validated_hours = _validate_payload(
            conn,
            document_type_id=merged_type_id,
            document_kind_id=int(merged_kind_id) if merged_kind_id is not None else None,
            medical_specialty_id=int(merged_specialty_id)
            if merged_specialty_id is not None
            else None,
            issued_at=merged_issued_at,
            hours=int(merged_hours) if merged_hours is not None else None,
            valid_until=merged_valid_until,
            file_url=merged_file_url,
            lifecycle_status=merged_lifecycle,
            on_create=False,
        )

        conn.execute(
            text(
                """
                UPDATE public.employee_documents
                SET
                    document_type_id = :document_type_id,
                    document_kind_id = :document_kind_id,
                    medical_specialty_id = :medical_specialty_id,
                    title = :title,
                    training_title = :training_title,
                    document_number = :document_number,
                    issued_by = :issued_by,
                    issued_at = :issued_at,
                    hours = :hours,
                    valid_until = :valid_until,
                    file_url = :file_url,
                    comment = :comment,
                    lifecycle_status = :lifecycle_status,
                    updated_at = now()
                WHERE document_id = :document_id
                """
            ),
            {
                "document_id": int(document_id),
                "document_type_id": merged_type_id,
                "document_kind_id": int(merged_kind_id)
                if merged_kind_id is not None
                else None,
                "medical_specialty_id": int(merged_specialty_id)
                if merged_specialty_id is not None
                else None,
                "title": title if title is not None else existing.get("title"),
                "training_title": training_title
                if training_title is not None
                else existing.get("training_title"),
                "document_number": document_number
                if document_number is not None
                else existing.get("document_number"),
                "issued_by": issued_by if issued_by is not None else existing.get("issued_by"),
                "issued_at": merged_issued_at,
                "hours": validated_hours,
                "valid_until": merged_valid_until,
                "file_url": merged_file_url,
                "comment": comment if comment is not None else existing.get("comment"),
                "lifecycle_status": status,
            },
        )
        return _fetch_document_by_id(conn, int(document_id))


def soft_delete_employee_document(document_id: int) -> Optional[Dict[str, Any]]:
    if not employee_documents_available():
        raise RuntimeError("employee_documents tables are not available")

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                UPDATE public.employee_documents
                SET lifecycle_status = :lifecycle_status, updated_at = now()
                WHERE document_id = :document_id
                RETURNING document_id, lifecycle_status
                """
            ),
            {
                "document_id": int(document_id),
                "lifecycle_status": LIFECYCLE_SUPERSEDED,
            },
        ).mappings().first()
        if not row:
            return None
        return {
            "document_id": int(row["document_id"]),
            "lifecycle_status": str(row["lifecycle_status"]),
        }


def get_employee_training_hours_summary(
    *,
    employee_id: int,
    as_of: Optional[date] = None,
    training_hours_required: Optional[int] = None,
) -> Dict[str, Any]:
    if not employee_documents_available():
        raise RuntimeError("employee_documents tables are not available")

    ref = as_of or date.today()
    required = (
        int(training_hours_required)
        if training_hours_required is not None
        else DEFAULT_TRAINING_HOURS_REQUIRED
    )
    window_start = _training_window_start(ref)

    with engine.begin() as conn:
        if not _employee_exists(conn, employee_id):
            raise EmployeeDocumentNotFoundError("employee_id not found.")

        incomplete_count = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM public.employee_documents ed
                    JOIN public.document_types dt
                        ON dt.document_type_id = ed.document_type_id
                    WHERE ed.employee_id = :employee_id
                      AND ed.lifecycle_status = :lifecycle_active
                      AND dt.tracks_hours = TRUE
                      AND (
                          ed.issued_at IS NULL
                          OR ed.hours IS NULL
                          OR ed.hours <= 0
                      )
                    """
                ),
                {
                    "employee_id": int(employee_id),
                    "lifecycle_active": LIFECYCLE_ACTIVE,
                },
            ).scalar()
            or 0
        )

        sum_row = conn.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(ed.hours), 0)::int AS total_hours,
                    COUNT(*)::int AS qualifying_documents_count
                FROM public.employee_documents ed
                JOIN public.document_types dt
                    ON dt.document_type_id = ed.document_type_id
                WHERE ed.employee_id = :employee_id
                  AND ed.lifecycle_status = :lifecycle_active
                  AND dt.tracks_hours = TRUE
                  AND ed.issued_at IS NOT NULL
                  AND ed.hours IS NOT NULL
                  AND ed.hours > 0
                  AND ed.issued_at >= :window_start
                  AND ed.issued_at <= :as_of
                """
            ),
            {
                "employee_id": int(employee_id),
                "lifecycle_active": LIFECYCLE_ACTIVE,
                "window_start": window_start,
                "as_of": ref,
            },
        ).mappings().first()

    total = int(sum_row["total_hours"] if sum_row else 0)
    qualifying_count = int(sum_row["qualifying_documents_count"] if sum_row else 0)
    remaining = max(0, required - total)

    if incomplete_count > 0:
        status = TRAINING_HOURS_STATUS_INCOMPLETE
    elif total >= required:
        status = TRAINING_HOURS_STATUS_MET
    elif total > 0:
        status = TRAINING_HOURS_STATUS_BELOW
    else:
        status = TRAINING_HOURS_STATUS_EMPTY

    return {
        "employee_id": int(employee_id),
        "as_of": ref.isoformat(),
        "window_start": window_start.isoformat(),
        "training_hours_last_5y": total,
        "training_hours_required": required,
        "training_hours_remaining": remaining,
        "training_hours_status": status,
        "incomplete_documents_count": incomplete_count,
        "qualifying_documents_count": qualifying_count,
    }
