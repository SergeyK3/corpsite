"""Canonical qualification-category write operation with optimistic locking."""
from __future__ import annotations
import json
from datetime import date
from sqlalchemy import text
from sqlalchemy.engine import Connection
from app.personnel_intake.domain.additional_profile import normalize_additional_profile
from app.services.personnel_record_event_service import emit_personnel_record_event


class CategoryVersionConflict(RuntimeError): pass


def save_categories(conn: Connection, *, person_id: int, employee_id: int, expected_version: str | None, rows: list[dict], actor_id: int) -> dict:
    metadata = conn.execute(text("SELECT additional_profile,updated_at FROM personnel_record_metadata WHERE person_id=:p FOR UPDATE"), {"p": person_id}).mappings().one_or_none()
    current_version = str(metadata["updated_at"]) if metadata else ""
    if expected_version != current_version:
        raise CategoryVersionConflict()
    raw = metadata["additional_profile"] if metadata else {}
    raw = json.loads(raw) if isinstance(raw, str) else raw
    profile = normalize_additional_profile(raw or {})
    prior = {str((entry.get("provenance") or {}).get("source_fingerprint") or ""): entry for entry in profile.get("qualification_categories") or []}
    normalized=[]
    for row in rows:
        specialty=str(row.get("specialty") or "").strip(); category=str(row.get("category") or "").strip()
        assigned_at=str(row.get("assigned_at") or "").strip(); fingerprint=str(row.get("source_fingerprint") or "")
        if not specialty or category not in {"highest","first","second"}:
            raise ValueError("specialty and normalized category are required")
        try: date.fromisoformat(assigned_at)
        except ValueError: raise ValueError("assigned_at must be a complete ISO date")
        old=prior.get(fingerprint, {})
        provenance=dict(old.get("provenance") or {})
        provenance["override_origin"]="HR_CORRECTION"
        normalized.append({"specialty":specialty,"category":category,"assigned_at":assigned_at,
                           "assigned_at_calculated":False,"review_status":"AUTO_READY","review_reason":None,
                           "provenance":provenance})
    profile["qualification_categories"]=normalized
    result=conn.execute(text("""INSERT INTO personnel_record_metadata(person_id,additional_profile) VALUES(:p,CAST(:profile AS jsonb))
      ON CONFLICT(person_id) DO UPDATE SET additional_profile=EXCLUDED.additional_profile,updated_at=now() RETURNING updated_at"""), {"p":person_id,"profile":json.dumps(profile,ensure_ascii=False)}).scalar_one()
    emit_personnel_record_event(conn,person_id=person_id,employee_context_id=employee_id,domain_code="additional",
      record_table_name="personnel_record_metadata",record_id=person_id,event_type="PPR_QUALIFICATION_CATEGORY_HR_CORRECTED",
      actor_id=str(actor_id),event_payload={"row_count":len(normalized),"operation":"HR_CORRECTION"})
    return {"qualification_categories":normalized,"version":str(result)}
