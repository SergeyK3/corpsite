"""ADR-039 Phase 3H — promote HR import roster rows to directory employees."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.department_recoding_service import lookup_recoding
from app.services.hr_import_analytics_service import (
    BatchNotFoundError,
    _ensure_batch_exists,
    is_real_employee_row,
)
from app.services.hr_import_employee_binding_service import (
    _digits_only,
    _lookup_employees_by_iin,
    _norm_name,
    propagate_employee_id_to_normalized_records,
    repair_batch_employee_bindings,
)

OUTCOME_WOULD_CREATE = "would_create"
OUTCOME_WOULD_UPDATE = "would_update"
OUTCOME_ALREADY_LINKED = "already_linked"
OUTCOME_EXISTS = "exists"
OUTCOME_CONFLICT = "conflict"
OUTCOME_BLOCKED = "blocked"

OUTCOME_LABELS = {
    OUTCOME_WOULD_CREATE: "Будет создан",
    OUTCOME_WOULD_UPDATE: "Будет обновлён",
    OUTCOME_ALREADY_LINKED: "Уже привязан",
    OUTCOME_EXISTS: "Уже существует",
    OUTCOME_CONFLICT: "Конфликт",
    OUTCOME_BLOCKED: "Ошибка",
}

DEFAULT_POSITION_NAME = "Не указана"


@dataclass
class RosterPromotionItem:
    row_id: int
    outcome: str
    full_name: str
    iin: str
    iin_masked: str
    employee_id: Optional[int] = None
    target_employee_id: Optional[int] = None
    org_unit_id: Optional[int] = None
    org_unit_name: str = ""
    position_id: Optional[int] = None
    position_name: str = ""
    needs_hr_review: bool = False
    reason: Optional[str] = None
    candidate_employee_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "outcome": self.outcome,
            "full_name": self.full_name,
            "iin": self.iin,
            "iin_masked": self.iin_masked,
            "employee_id": self.employee_id,
            "target_employee_id": self.target_employee_id,
            "org_unit_id": self.org_unit_id,
            "org_unit_name": self.org_unit_name,
            "position_id": self.position_id,
            "position_name": self.position_name,
            "needs_hr_review": self.needs_hr_review,
            "reason": self.reason,
            "candidate_employee_ids": self.candidate_employee_ids,
        }


def _mask_iin(iin: str) -> str:
    digits = _digits_only(iin)
    if len(digits) != 12:
        return digits or "—"
    return f"{digits[:4]}******{digits[-2:]}"


def _parse_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        return json.loads(value) if value.strip() else {}
    return {}


def _coerce_date_from_payload(payload: dict[str, Any]) -> Optional[date]:
    birth = str(payload.get("birth_date") or "").strip()
    if not birth:
        return None
    if len(birth) >= 10:
        try:
            return date.fromisoformat(birth[:10])
        except ValueError:
            pass
    return None


def _load_roster_rows(conn: Connection, batch_id: int) -> list[dict[str, Any]]:
    _ensure_batch_exists(conn, batch_id)
    db_rows = conn.execute(
        text(
            """
            SELECT
                row_id,
                employee_id,
                source_sheet,
                source_row_number,
                normalized_payload,
                match_status
            FROM public.hr_import_rows
            WHERE batch_id = :batch_id
            ORDER BY row_id
            """
        ),
        {"batch_id": batch_id},
    ).mappings().all()

    items: list[dict[str, Any]] = []
    for db_row in db_rows:
        payload = _parse_payload(db_row["normalized_payload"])
        metadata = dict(payload.get("metadata") or {})
        row = {
            "row_id": int(db_row["row_id"]),
            "employee_id": int(db_row["employee_id"]) if db_row.get("employee_id") else None,
            "source_sheet": str(db_row["source_sheet"] or ""),
            "source_row_number": int(db_row["source_row_number"]),
            "full_name": str(payload.get("full_name") or "").strip(),
            "iin": _digits_only(str(payload.get("iin") or "")),
            "department": str(payload.get("department") or "").strip(),
            "position_raw": str(payload.get("position_raw") or "").strip(),
            "classification": str(metadata.get("classification") or ""),
            "row_type": str(metadata.get("row_type") or ""),
            "is_employee_roster": bool(metadata.get("is_employee_roster", metadata.get("row_type") == "EMPLOYEE")),
            "match_status": str(db_row.get("match_status") or ""),
            "payload": payload,
        }
        if not is_real_employee_row(row):
            continue
        items.append(row)
    return items


def _get_or_create_position_id(conn: Connection, position_name: str) -> int:
    name = (position_name or DEFAULT_POSITION_NAME).strip() or DEFAULT_POSITION_NAME
    row = conn.execute(
        text(
            """
            SELECT position_id
            FROM public.positions
            WHERE lower(trim(name)) = lower(trim(:name))
            LIMIT 1
            """
        ),
        {"name": name},
    ).mappings().first()
    if row:
        return int(row["position_id"])

    cols = {
        r[0]
        for r in conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'positions'
                """
            )
        ).fetchall()
    }
    values: dict[str, Any] = {"name": name}
    if "category" in cols:
        values["category"] = "other"
    columns = ", ".join(values.keys())
    placeholders = ", ".join(f":{key}" for key in values.keys())
    inserted = conn.execute(
        text(
            f"""
            INSERT INTO public.positions ({columns})
            VALUES ({placeholders})
            RETURNING position_id
            """
        ),
        values,
    ).scalar_one()
    return int(inserted)


def _resolve_org_unit(conn: Connection, department: str) -> tuple[Optional[int], str]:
    if not department:
        return None, ""
    rec = lookup_recoding(conn, department)
    if not rec or not rec.get("org_unit_id"):
        return None, ""
    return int(rec["org_unit_id"]), str(rec.get("org_unit_name") or "")


def evaluate_roster_promotion(
    conn: Connection,
    batch_id: int,
    *,
    row_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Dry-run evaluation for roster rows in a batch."""
    rows = _load_roster_rows(conn, batch_id)
    if row_ids:
        allowed = {int(rid) for rid in row_ids}
        rows = [row for row in rows if row["row_id"] in allowed]

    items: list[RosterPromotionItem] = []
    for row in rows:
        items.append(_evaluate_single_row(conn, row))

    summary = {
        OUTCOME_WOULD_CREATE: 0,
        OUTCOME_WOULD_UPDATE: 0,
        OUTCOME_ALREADY_LINKED: 0,
        OUTCOME_EXISTS: 0,
        OUTCOME_CONFLICT: 0,
        OUTCOME_BLOCKED: 0,
    }
    for item in items:
        summary[item.outcome] = summary.get(item.outcome, 0) + 1

    return {
        "batch_id": batch_id,
        "dry_run": True,
        "total_rows": len(items),
        "summary": summary,
        "items": [item.to_dict() for item in items],
    }


def _evaluate_single_row(conn: Connection, row: dict[str, Any]) -> RosterPromotionItem:
    row_id = int(row["row_id"])
    full_name = str(row.get("full_name") or "").strip()
    iin = str(row.get("iin") or "").strip()
    linked_employee_id = row.get("employee_id")

    base = RosterPromotionItem(
        row_id=row_id,
        outcome=OUTCOME_BLOCKED,
        full_name=full_name,
        iin=iin,
        iin_masked=_mask_iin(iin),
        employee_id=linked_employee_id,
    )

    if linked_employee_id:
        base.outcome = OUTCOME_ALREADY_LINKED
        base.target_employee_id = int(linked_employee_id)
        base.reason = "Строка уже связана с employee_id"
        return base

    if not full_name:
        base.reason = "Не указано ФИО"
        return base

    if len(iin) != 12:
        base.reason = "ИИН отсутствует или не содержит 12 цифр"
        return base

    existing_ids = _lookup_employees_by_iin(conn, iin)
    if len(existing_ids) > 1:
        base.outcome = OUTCOME_CONFLICT
        base.candidate_employee_ids = existing_ids
        base.reason = f"Найдено несколько сотрудников с ИИН {iin}"
        return base

    org_unit_id, org_unit_name = _resolve_org_unit(conn, str(row.get("department") or ""))
    position_name = str(row.get("position_raw") or "").strip() or DEFAULT_POSITION_NAME
    needs_hr_review = org_unit_id is None

    if existing_ids:
        base.outcome = OUTCOME_WOULD_UPDATE
        base.target_employee_id = existing_ids[0]
        base.org_unit_id = org_unit_id
        base.org_unit_name = org_unit_name
        base.position_name = position_name
        base.needs_hr_review = needs_hr_review
        if needs_hr_review:
            base.reason = f"Отделение не сопоставлено: {row.get('department') or '—'}"
        return base

    if org_unit_id is None:
        base.reason = f"Отделение не сопоставлено с org_unit: {row.get('department') or '—'}"
        return base

    base.outcome = OUTCOME_WOULD_CREATE
    base.org_unit_id = org_unit_id
    base.org_unit_name = org_unit_name
    base.position_name = position_name
    base.needs_hr_review = needs_hr_review
    return base


def _insert_employee_identity(conn: Connection, *, employee_id: int, iin: str, created_by: int) -> None:
    existing = conn.execute(
        text(
            """
            SELECT identity_id
            FROM public.employee_identities
            WHERE employee_id = :employee_id
              AND identity_type = 'IIN'
              AND valid_to IS NULL
            LIMIT 1
            """
        ),
        {"employee_id": employee_id},
    ).first()
    if existing:
        return
    conn.execute(
        text(
            """
            INSERT INTO public.employee_identities (
                employee_id,
                identity_type,
                identity_value,
                is_primary,
                created_by
            )
            VALUES (:employee_id, 'IIN', :iin, TRUE, :created_by)
            """
        ),
        {"employee_id": employee_id, "iin": iin, "created_by": created_by},
    )


def _update_employee_name_if_needed(
    conn: Connection,
    *,
    employee_id: int,
    full_name: str,
) -> bool:
    row = conn.execute(
        text(
            """
            SELECT full_name
            FROM public.employees
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": employee_id},
    ).mappings().first()
    if row is None:
        return False
    current = str(row["full_name"] or "").strip()
    normalized = " ".join(full_name.split())
    if _norm_name(current) == _norm_name(normalized):
        return False
    conn.execute(
        text(
            """
            UPDATE public.employees
            SET full_name = :full_name
            WHERE employee_id = :employee_id
            """
        ),
        {"employee_id": employee_id, "full_name": normalized},
    )
    return True


def _persist_row_roster_metadata(
    conn: Connection,
    *,
    row_id: int,
    payload: dict[str, Any],
    employee_id: int,
    outcome: str,
    needs_hr_review: bool,
    reason: Optional[str],
) -> None:
    metadata = dict(payload.get("metadata") or {})
    metadata["roster_promotion_outcome"] = outcome
    metadata["roster_promotion_needs_hr_review"] = needs_hr_review
    metadata["roster_promotion_reason"] = reason
    payload["metadata"] = metadata
    conn.execute(
        text(
            """
            UPDATE public.hr_import_rows
            SET
                employee_id = :employee_id,
                match_status = 'AUTO_MATCH',
                normalized_payload = CAST(:normalized_payload AS JSONB)
            WHERE row_id = :row_id
            """
        ),
        {
            "row_id": row_id,
            "employee_id": employee_id,
            "normalized_payload": json.dumps(payload, ensure_ascii=False),
        },
    )


def promote_roster_batch(
    conn: Connection,
    batch_id: int,
    *,
    created_by: int,
    dry_run: bool = True,
    row_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Create/update employees from import roster rows and link hr_import_rows."""
    preview = evaluate_roster_promotion(conn, batch_id, row_ids=row_ids)
    if dry_run:
        preview["dry_run"] = True
        return preview

    applied: list[dict[str, Any]] = []
    for item_dict in preview["items"]:
        item = RosterPromotionItem(
            row_id=int(item_dict["row_id"]),
            outcome=str(item_dict["outcome"]),
            full_name=str(item_dict.get("full_name") or ""),
            iin=str(item_dict.get("iin") or ""),
            iin_masked=str(item_dict.get("iin_masked") or ""),
            employee_id=item_dict.get("employee_id"),
            target_employee_id=item_dict.get("target_employee_id"),
            org_unit_id=item_dict.get("org_unit_id"),
            org_unit_name=str(item_dict.get("org_unit_name") or ""),
            position_id=item_dict.get("position_id"),
            position_name=str(item_dict.get("position_name") or ""),
            needs_hr_review=bool(item_dict.get("needs_hr_review")),
            reason=item_dict.get("reason"),
            candidate_employee_ids=list(item_dict.get("candidate_employee_ids") or []),
        )
        if item.outcome in {OUTCOME_ALREADY_LINKED, OUTCOME_BLOCKED, OUTCOME_CONFLICT}:
            applied.append(item.to_dict())
            continue

        row = conn.execute(
            text(
                """
                SELECT normalized_payload
                FROM public.hr_import_rows
                WHERE row_id = :row_id
                """
            ),
            {"row_id": item.row_id},
        ).mappings().first()
        payload = _parse_payload(row["normalized_payload"]) if row else {}

        if item.outcome == OUTCOME_WOULD_CREATE:
            assert item.org_unit_id is not None
            position_id = _get_or_create_position_id(conn, item.position_name)
            hired_on = _coerce_date_from_payload(payload) or date.today()
            employee_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO public.employees (
                            full_name,
                            org_unit_id,
                            position_id,
                            date_from,
                            employment_rate,
                            is_active
                        )
                        VALUES (
                            :full_name,
                            :org_unit_id,
                            :position_id,
                            :date_from,
                            1.0,
                            TRUE
                        )
                        RETURNING employee_id
                        """
                    ),
                    {
                        "full_name": item.full_name,
                        "org_unit_id": item.org_unit_id,
                        "position_id": position_id,
                        "date_from": hired_on,
                    },
                ).scalar_one()
            )
            _insert_employee_identity(
                conn,
                employee_id=employee_id,
                iin=item.iin,
                created_by=created_by,
            )
        elif item.outcome == OUTCOME_WOULD_UPDATE:
            employee_id = int(item.target_employee_id)
            _update_employee_name_if_needed(conn, employee_id=employee_id, full_name=item.full_name)
            _insert_employee_identity(
                conn,
                employee_id=employee_id,
                iin=item.iin,
                created_by=created_by,
            )
        else:
            applied.append(item.to_dict())
            continue

        _persist_row_roster_metadata(
            conn,
            row_id=item.row_id,
            payload=payload,
            employee_id=employee_id,
            outcome=item.outcome.replace("would_", ""),
            needs_hr_review=item.needs_hr_review,
            reason=item.reason,
        )
        propagate_employee_id_to_normalized_records(conn, item.row_id, employee_id)
        applied.append(
            {
                **item.to_dict(),
                "employee_id": employee_id,
                "applied": True,
            }
        )

    binding_summary = repair_batch_employee_bindings(conn, batch_id)
    result = evaluate_roster_promotion(conn, batch_id, row_ids=row_ids)
    result["dry_run"] = False
    result["applied"] = applied
    result["binding_repair"] = binding_summary
    return result
