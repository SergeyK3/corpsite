"""Transactional lifecycle for registered exchange packages."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import PurePath, PureWindowsPath
from typing import Any

from sqlalchemy import text

from app.data_exchange.contracts import PreviewRow
from app.data_exchange.order_scenario import WorkbookValidationError
from app.data_exchange.registry import get_scenario


class ExchangeError(ValueError):
    pass


class ExchangeConflict(ExchangeError):
    pass


def _safe_filename(filename: str) -> str:
    value = str(filename or "").strip()
    if not value or len(value) > 255:
        raise ExchangeError("Invalid filename.")
    path = PureWindowsPath(value)
    if path.name != value or path.drive or path.root or PurePath(value).is_absolute():
        raise ExchangeError("Invalid filename.")
    return value


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def _row_fingerprint(row: PreviewRow) -> str:
    return _sha(_json({
        "row": row.source_row_number, "source": row.source_keys, "target": row.target_ref,
        "group": row.result_group, "action": row.proposed_action, "reason": row.reason_code,
        "payload": row.payload,
    }).encode("utf-8"))


def _audit(conn, *, package_id: int, event_type: str, actor_user_id: int | None, metadata: dict[str, Any]) -> None:
    conn.execute(text("""
        INSERT INTO public.data_exchange_audit_events(package_id,event_type,actor_user_id,metadata_json)
        VALUES(:package_id,:event_type,:actor_user_id,CAST(:metadata AS jsonb))
    """), {"package_id": package_id, "event_type": event_type, "actor_user_id": actor_user_id,
            "metadata": _json(metadata)})


def _package(conn, package_id: int, *, lock: bool = False) -> dict[str, Any]:
    row = conn.execute(text(f"""
        SELECT package_id,scenario_code,schema_version,status,original_filename,media_type,byte_size,
               content_sha256,file_content,uploaded_by_user_id,uploaded_at,validated_at,dry_run_at,
               dry_run_target_fingerprint,confirmed_at,confirmed_by_user_id,applied_at,applied_by_user_id,
               counters,report,version
        FROM public.data_exchange_packages WHERE package_id=:package_id {'FOR UPDATE' if lock else ''}
    """), {"package_id": package_id}).mappings().one_or_none()
    if row is None:
        raise ExchangeError("Package not found.")
    return dict(row)


def _scenario_for(package: dict[str, Any]):
    scenario = get_scenario(str(package["scenario_code"]))
    if scenario is None or scenario.schema_version != package["schema_version"]:
        raise ExchangeError("Package scenario is unavailable.")
    return scenario


def _counters(rows: list[PreviewRow]) -> dict[str, int]:
    values = Counter(row.result_group for row in rows)
    return {key.lower(): int(values.get(key, 0)) for key in (
        "CREATE", "UPDATE", "UNCHANGED", "NOT_FOUND", "AMBIGUOUS", "ERROR", "POSSIBLE_DUPLICATE",
    )} | {"total": len(rows), "valid": int(values.get("CREATE", 0) + values.get("UPDATE", 0) + values.get("UNCHANGED", 0)),
          "blocked": int(values.get("NOT_FOUND", 0) + values.get("AMBIGUOUS", 0) + values.get("ERROR", 0) + values.get("POSSIBLE_DUPLICATE", 0))}


def _store_preview(conn, *, package_id: int, rows: list[PreviewRow]) -> None:
    conn.execute(text("DELETE FROM public.data_exchange_preview_rows WHERE package_id=:package_id"), {"package_id": package_id})
    for row in rows:
        conn.execute(text("""
            INSERT INTO public.data_exchange_preview_rows(
              package_id,source_row_number,source_keys,target_ref,result_group,proposed_action,
              reason_code,message,row_payload,row_fingerprint)
            VALUES(:package_id,:source_row_number,CAST(:source_keys AS jsonb),CAST(:target_ref AS jsonb),
                   :result_group,:proposed_action,:reason_code,:message,CAST(:row_payload AS jsonb),:row_fingerprint)
        """), {"package_id": package_id, "source_row_number": row.source_row_number,
                "source_keys": _json(row.source_keys), "target_ref": _json(row.target_ref) if row.target_ref else None,
                "result_group": row.result_group, "proposed_action": row.proposed_action,
                "reason_code": row.reason_code, "message": row.message,
                "row_payload": _json(row.payload) if row.payload is not None else None,
                "row_fingerprint": _row_fingerprint(row)})


def _load_preview_rows(conn, package_id: int) -> list[PreviewRow]:
    values = conn.execute(text("""
        SELECT source_row_number,source_keys,target_ref,result_group,proposed_action,reason_code,message,row_payload
        FROM public.data_exchange_preview_rows WHERE package_id=:package_id ORDER BY source_row_number
    """), {"package_id": package_id}).mappings().all()
    return [PreviewRow(int(row["source_row_number"]), dict(row["source_keys"] or {}),
                       dict(row["target_ref"]) if row["target_ref"] else None, row["result_group"],
                       row["proposed_action"], row["reason_code"], row["message"],
                       dict(row["row_payload"]) if row["row_payload"] else None) for row in values]


def _public(package: dict[str, Any]) -> dict[str, Any]:
    return {key: package[key] for key in (
        "package_id", "scenario_code", "schema_version", "status", "original_filename", "media_type", "byte_size",
        "content_sha256", "uploaded_at", "validated_at", "dry_run_at", "dry_run_target_fingerprint",
        "confirmed_at", "confirmed_by_user_id", "applied_at", "applied_by_user_id", "counters", "report", "version",
    )}


def list_scenarios() -> list[dict[str, Any]]:
    from app.data_exchange.registry import catalog
    return catalog()


def mark_failed(conn, *, package_id: int, actor_user_id: int, stage: str) -> None:
    """Persist a non-sensitive failure marker after the business transaction rolled back."""
    package = _package(conn, package_id, lock=True)
    if package["status"] in {"APPLIED", "CANCELLED"}:
        return
    conn.execute(text("""UPDATE public.data_exchange_packages
        SET status='FAILED', report=CAST(:report AS jsonb), version=version+1
        WHERE package_id=:package_id"""), {
        "package_id": package_id,
        "report": _json({"errors": ["Operation failed; inspect server audit reference."], "stage": stage}),
    })
    _audit(conn, package_id=package_id, event_type="FAILED", actor_user_id=actor_user_id, metadata={"stage": stage})


def upload_package(conn, *, scenario_code: str, filename: str, content: bytes, media_type: str | None, actor_user_id: int) -> dict[str, Any]:
    scenario = get_scenario(scenario_code)
    if scenario is None:
        raise ExchangeError("Unknown data-exchange scenario.")
    safe_name = _safe_filename(filename)
    if not safe_name.lower().endswith(scenario.accepted_suffixes) or len(content) > scenario.max_bytes or not content:
        raise ExchangeError("File does not meet the scenario policy.")
    digest = _sha(content)
    existing = conn.execute(text("""
        SELECT package_id FROM public.data_exchange_packages
        WHERE scenario_code=:scenario_code AND schema_version=:schema_version AND content_sha256=:content_sha256
    """), {"scenario_code": scenario.code, "schema_version": scenario.schema_version, "content_sha256": digest}).scalar_one_or_none()
    if existing is not None:
        return {"duplicate": True, "package": _public(_package(conn, int(existing)))}
    package_id = conn.execute(text("""
        INSERT INTO public.data_exchange_packages(
          scenario_code,schema_version,status,original_filename,media_type,byte_size,content_sha256,file_content,uploaded_by_user_id)
        VALUES(:scenario_code,:schema_version,'UPLOADED',:original_filename,:media_type,:byte_size,:content_sha256,:file_content,:actor)
        RETURNING package_id
    """), {"scenario_code": scenario.code, "schema_version": scenario.schema_version,
            "original_filename": safe_name, "media_type": (media_type or "")[:255] or None, "byte_size": len(content),
            "content_sha256": digest, "file_content": content, "actor": actor_user_id}).scalar_one()
    _audit(conn, package_id=int(package_id), event_type="UPLOADED", actor_user_id=actor_user_id,
           metadata={"sha256": digest, "byte_size": len(content), "scenario": scenario.code})
    return {"duplicate": False, "package": _public(_package(conn, int(package_id)))}


def preview_package(conn, *, package_id: int, actor_user_id: int, scope_unit_ids: set[int] | None) -> dict[str, Any]:
    package = _package(conn, package_id, lock=True)
    if package["status"] in {"APPLYING", "APPLIED", "CANCELLED"}:
        raise ExchangeConflict("Package cannot be previewed in its current state.")
    scenario = _scenario_for(package)
    conn.execute(text("UPDATE public.data_exchange_packages SET status='VALIDATING',version=version+1 WHERE package_id=:package_id"), {"package_id": package_id})
    try:
        result = scenario.validate_and_preview(conn, bytes(package["file_content"]), scope_unit_ids=scope_unit_ids)
    except WorkbookValidationError as exc:
        conn.execute(text("""UPDATE public.data_exchange_packages
            SET status='BLOCKED',validated_at=now(),report=CAST(:report AS jsonb),version=version+1 WHERE package_id=:package_id"""),
            {"package_id": package_id, "report": _json({"errors": [str(exc)]})})
        _audit(conn, package_id=package_id, event_type="VALIDATION_BLOCKED", actor_user_id=actor_user_id, metadata={"code": "STRUCTURAL_VALIDATION"})
        return {"package": _public(_package(conn, package_id)), "rows": []}
    counters = _counters(result.rows)
    status = "BLOCKED" if counters["blocked"] else "PREVIEW_READY"
    _store_preview(conn, package_id=package_id, rows=result.rows)
    conn.execute(text("""UPDATE public.data_exchange_packages SET status=:status,validated_at=now(),
        counters=CAST(:counters AS jsonb),report=CAST(:report AS jsonb),version=version+1 WHERE package_id=:package_id"""),
        {"package_id": package_id, "status": status, "counters": _json(counters),
         "report": _json({"warnings": result.warnings, "target_fingerprint": result.target_fingerprint})})
    _audit(conn, package_id=package_id, event_type="PREVIEW_READY" if status == "PREVIEW_READY" else "PREVIEW_BLOCKED",
           actor_user_id=actor_user_id, metadata={"counters": counters, "target_fingerprint": result.target_fingerprint})
    return {"package": _public(_package(conn, package_id)), "rows": result.rows}


def dry_run_package(conn, *, package_id: int, actor_user_id: int, scope_unit_ids: set[int] | None) -> dict[str, Any]:
    package = _package(conn, package_id, lock=True)
    if package["status"] != "PREVIEW_READY":
        raise ExchangeConflict("Preview without blockers is required before dry-run.")
    scenario = _scenario_for(package)
    result = scenario.validate_and_preview(conn, bytes(package["file_content"]), scope_unit_ids=scope_unit_ids)
    previous = _load_preview_rows(conn, package_id)
    if [_row_fingerprint(row) for row in previous] != [_row_fingerprint(row) for row in result.rows]:
        _store_preview(conn, package_id=package_id, rows=result.rows)
        conn.execute(text("""UPDATE public.data_exchange_packages SET status='BLOCKED',validated_at=now(),
            counters=CAST(:counters AS jsonb),report=CAST(:report AS jsonb),version=version+1 WHERE package_id=:package_id"""),
            {"package_id": package_id, "counters": _json(_counters(result.rows)),
             "report": _json({"errors": ["Preview became stale; inspect the new preview."], "target_fingerprint": result.target_fingerprint})})
        _audit(conn, package_id=package_id, event_type="DRY_RUN_STALE", actor_user_id=actor_user_id, metadata={})
        raise ExchangeConflict("Preview changed; re-run preview.")
    if _counters(result.rows)["blocked"]:
        raise ExchangeConflict("Blocked rows cannot pass dry-run.")
    conn.execute(text("""UPDATE public.data_exchange_packages SET status='AWAITING_CONFIRMATION',dry_run_at=now(),
        dry_run_target_fingerprint=:target_fingerprint,version=version+1 WHERE package_id=:package_id"""),
        {"package_id": package_id, "target_fingerprint": result.target_fingerprint})
    _audit(conn, package_id=package_id, event_type="DRY_RUN_PASSED", actor_user_id=actor_user_id,
           metadata={"target_fingerprint": result.target_fingerprint})
    return _public(_package(conn, package_id))


def confirm_package(conn, *, package_id: int, expected_sha256: str, expected_schema_version: str,
                    expected_target_fingerprint: str, actor_user_id: int) -> dict[str, Any]:
    package = _package(conn, package_id, lock=True)
    if package["status"] != "AWAITING_CONFIRMATION" or package["confirmed_at"] is not None:
        raise ExchangeConflict("Package is not awaiting confirmation.")
    if (expected_sha256 != package["content_sha256"] or expected_schema_version != package["schema_version"]
            or expected_target_fingerprint != package["dry_run_target_fingerprint"]):
        raise ExchangeConflict("Confirmation does not match the dry-run package.")
    conn.execute(text("""UPDATE public.data_exchange_packages SET confirmed_at=now(),confirmed_by_user_id=:actor,
        version=version+1 WHERE package_id=:package_id"""), {"package_id": package_id, "actor": actor_user_id})
    _audit(conn, package_id=package_id, event_type="CONFIRMED", actor_user_id=actor_user_id,
           metadata={"sha256": package["content_sha256"], "schema_version": package["schema_version"]})
    return _public(_package(conn, package_id))


def cancel_package(conn, *, package_id: int, actor_user_id: int) -> dict[str, Any]:
    package = _package(conn, package_id, lock=True)
    if package["status"] in {"APPLYING", "APPLIED", "CANCELLED"}:
        raise ExchangeConflict("Package cannot be cancelled in its current state.")
    conn.execute(text("UPDATE public.data_exchange_packages SET status='CANCELLED',version=version+1 WHERE package_id=:package_id"), {"package_id": package_id})
    _audit(conn, package_id=package_id, event_type="CANCELLED", actor_user_id=actor_user_id, metadata={})
    return _public(_package(conn, package_id))


def apply_package(conn, *, package_id: int, actor_user_id: int, scope_unit_ids: set[int] | None) -> dict[str, Any]:
    package = _package(conn, package_id, lock=True)
    if package["status"] != "AWAITING_CONFIRMATION" or package["confirmed_at"] is None:
        raise ExchangeConflict("A confirmed dry-run is required before apply.")
    scenario = _scenario_for(package)
    result = scenario.validate_and_preview(conn, bytes(package["file_content"]), scope_unit_ids=scope_unit_ids)
    existing = _load_preview_rows(conn, package_id)
    if result.target_fingerprint != package["dry_run_target_fingerprint"] or [_row_fingerprint(row) for row in existing] != [_row_fingerprint(row) for row in result.rows]:
        raise ExchangeConflict("Related data changed after dry-run; re-preview and dry-run are required.")
    if _counters(result.rows)["blocked"]:
        raise ExchangeConflict("Blocked rows cannot be applied.")
    conn.execute(text("UPDATE public.data_exchange_packages SET status='APPLYING',version=version+1 WHERE package_id=:package_id"), {"package_id": package_id})
    counts = scenario.apply(conn, package_id=package_id, rows=result.rows, actor_user_id=actor_user_id)
    conn.execute(text("""UPDATE public.data_exchange_packages SET status='APPLIED',applied_at=now(),applied_by_user_id=:actor,
        counters=counters || CAST(:counts AS jsonb),version=version+1 WHERE package_id=:package_id"""),
        {"package_id": package_id, "actor": actor_user_id, "counts": _json(counts)})
    _audit(conn, package_id=package_id, event_type="APPLIED", actor_user_id=actor_user_id, metadata=counts)
    return _public(_package(conn, package_id))
