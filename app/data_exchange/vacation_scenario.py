"""Adapter for the unapproved vacation-register analysis workbook.

It preserves evidence and HR work items in review staging only.  It never
interprets empty correction cells as deletion and never promotes a proposal to
an official leave/order.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text

from app.data_exchange.contracts import PreviewRow, ScenarioResult
from app.data_exchange.order_scenario import MAX_XLSX_BYTES, WorkbookValidationError, _open_xlsx
from app.data_exchange.permissions import DATA_EXCHANGE_CONFIRM_APPLY, DATA_EXCHANGE_DRY_RUN, DATA_EXCHANGE_UPLOAD_PREVIEW
from app.data_exchange.vacation_validation import validate_period

VACATION_SCENARIO_CODE = "PERSONNEL_VACATION_REGISTER_REVIEW_IMPORT"
VACATION_SCHEMA_VERSION = "PERSONNEL_VACATION_REGISTER_ANALYSIS_XLSX_V1"
_SHEETS = ("Нет реквизитов", "Ошибки периодов", "Строка перевода")


def _text(value: Any) -> str: return " ".join(str(value or "").split())
def _sha(value: Any) -> str: return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
def _truthy_yes(value: Any) -> bool: return _text(value).casefold() in {"да", "yes", "true", "1"}


def _header(sheet) -> tuple[int, list[str]]:
    for number in range(1, min(sheet.max_row, 8) + 1):
        row = list(sheet[number]); labels = [_text(cell.value) for cell in row]
        if "Строка исходного Excel" in labels and "Проверено кадровиком" in labels:
            return number, labels
    raise WorkbookValidationError("Vacation review worksheet has no recognized header.")


def _load(content: bytes) -> list[dict[str, Any]]:
    book = _open_xlsx(content)
    if any(sheet not in book.sheetnames for sheet in _SHEETS) or "Классификация" not in book.sheetnames:
        raise WorkbookValidationError("Vacation analysis workbook has required worksheets missing.")
    values: dict[str, dict[str, Any]] = {}
    for title in _SHEETS:
        sheet = book[title]; header_row, headers = _header(sheet)
        for number, row in enumerate(sheet.iter_rows(min_row=header_row + 1, values_only=False), start=header_row + 1):
            if not any(cell.value is not None for cell in row): continue
            if any(cell.data_type == "f" for cell in row): raise WorkbookValidationError("Workbook formulas are not accepted in review rows.")
            item = {headers[index]: row[index].value if index < len(row) else None for index in range(len(headers))}
            source_row = _text(item.get("Строка исходного Excel"))
            if not source_row: raise WorkbookValidationError("Vacation review row has no source row identifier.")
            existing = values.get(source_row)
            # The transfer row is deliberately also present in the missing-
            # requisites list. Merge annotations, never duplicate an event.
            if existing is None: values[source_row] = {"source_row": source_row, "sheets": [title], "values": item}
            else: existing["sheets"].append(title); existing["values"].update({key: value for key, value in item.items() if _text(value)})
    return list(values.values())


def _item_payload(record: dict[str, Any], source_file_sha: str) -> dict[str, Any]:
    raw = record["values"]
    reviewed = _truthy_yes(raw.get("Проверено кадровиком"))
    correction = {
        "order_number": _text(raw.get("Исправленный № приказа")),
        "order_date": _text(raw.get("Исправленная дата приказа")),
        "period": _text(raw.get("Исправленный период")),
    }
    source = {
        "source_row_id": record["source_row"], "source_file_name": _text(raw.get("Исходный файл")),
        "block_number": _text(raw.get("№ блока")), "event_number": _text(raw.get("№ события")),
        "event_type_raw": _text(raw.get("Исходный вид события") or raw.get("Вид события")),
        "order_number_raw": _text(raw.get("Исходный № приказа") or raw.get("№ приказа")),
        "order_date_raw": _text(raw.get("Исходная дата приказа") or raw.get("Дата приказа")),
        "source_text": _text(raw.get("Исходный текст")), "source_sheet": ",".join(record["sheets"]),
    }
    proposed = {"category": _text(raw.get("Предлагаемая категория")), "subclass": _text(raw.get("Предлагаемый подкласс"))}
    decision = _text(raw.get("Решение кадровика"))
    period_issues = validate_period(correction["period"] or source["source_text"])
    reason = "HR_CONFIRMATION_REQUIRED" if not reviewed else "SOURCE_DOCUMENT_REQUISITES_NOT_PROVEN"
    if period_issues: reason = period_issues[0].code
    return {"source": source, "correction": correction, "proposed": proposed, "reviewed": reviewed,
            "decision": decision, "comment": _text(raw.get("Комментарий кадровика")),
            "source_file_sha256": source_file_sha,
            "period_issues": [issue.__dict__ for issue in period_issues], "block_reason": reason}


class PersonnelVacationRegisterReviewScenario:
    code = VACATION_SCENARIO_CODE; schema_version = VACATION_SCHEMA_VERSION
    label = "Аналитический реестр отпускных событий (review-staging)"
    accepted_suffixes = (".xlsx",); max_bytes = MAX_XLSX_BYTES; atomic_apply = True
    upload_permission = DATA_EXCHANGE_UPLOAD_PREVIEW; dry_run_permission = DATA_EXCHANGE_DRY_RUN
    apply_permission = DATA_EXCHANGE_CONFIRM_APPLY; export_permission = None

    def validate_and_preview(self, conn, content: bytes, *, scope_unit_ids: set[int] | None) -> ScenarioResult:
        source_sha = hashlib.sha256(content).hexdigest(); records = _load(content); rows: list[PreviewRow] = []
        for index, record in enumerate(records, start=1):
            payload = _item_payload(record, source_sha); source = payload["source"]
            key = _sha({"scenario": self.code, "source_sha": source_sha, "source_row": source["source_row_id"], "block": source["block_number"], "event": source["event_number"]})
            existing = conn.execute(text("SELECT review_record_id FROM public.personnel_order_import_review_records WHERE business_key=:key"), {"key": key}).scalar_one_or_none()
            group, action = ("UNCHANGED", "SKIP") if existing else ("CREATE", "CREATE_REVIEW_RECORD")
            rows.append(PreviewRow(index, {"source_row_id": source["source_row_id"], "block_number": source["block_number"], "event_number": source["event_number"]},
                {"review_record_id": int(existing)} if existing else None, group, action,
                payload["block_reason"], "Unconfirmed analytical evidence is retained for HR review.", {**payload, "business_key": key}))
        return ScenarioResult(rows, _sha([{ "key": row.payload["business_key"], "reviewed": row.payload["reviewed"] } for row in rows if row.payload]), [])

    def apply(self, conn, *, package_id: int, rows: list[PreviewRow], actor_user_id: int) -> dict[str, int]:
        created = skipped = 0
        for row in rows:
            if row.result_group == "UNCHANGED": skipped += 1; continue
            payload = row.payload or {}
            if row.result_group != "CREATE": raise WorkbookValidationError("Blocked review row cannot be applied.")
            source = payload["source"]
            inserted = conn.execute(text("""
                INSERT INTO public.personnel_order_import_review_records(
                  package_id,source_row_number,business_key,employee_id,order_kind,order_number,order_date,action_type,
                  source_payload,created_by_user_id,schema_version,source_file_sha256,source_row_id,block_number,event_number,
                  source_values,normalized_values,proposed_values,hr_correction,hr_reviewed,hr_decision,hr_comment,block_reason)
                VALUES(:package_id,:number,:key,NULL,'VACATION_REVIEW',:order_number,NULL,:action_type,
                  CAST(:payload AS jsonb),:actor,:schema,:source_sha,:source_row,:block,:event,
                  CAST(:source AS jsonb),'{}'::jsonb,CAST(:proposed AS jsonb),CAST(:correction AS jsonb),:reviewed,:decision,:comment,:reason)
                ON CONFLICT (business_key) DO NOTHING RETURNING review_record_id
            """), {"package_id": package_id, "number": row.source_row_number, "key": payload["business_key"], "order_number": source["order_number_raw"] or "UNCONFIRMED", "action_type": source["event_type_raw"] or "UNCLASSIFIED", "payload": json.dumps(payload, ensure_ascii=False), "actor": actor_user_id, "schema": self.schema_version, "source_sha": payload["source_file_sha256"], "source_row": source["source_row_id"], "block": source["block_number"], "event": source["event_number"], "source": json.dumps(source, ensure_ascii=False), "proposed": json.dumps(payload["proposed"], ensure_ascii=False), "correction": json.dumps(payload["correction"], ensure_ascii=False), "reviewed": payload["reviewed"], "decision": payload["decision"] or None, "comment": payload["comment"] or None, "reason": payload["block_reason"]}).scalar_one_or_none()
            created += int(inserted is not None); skipped += int(inserted is None)
        return {"created": created, "updated": 0, "skipped": skipped}
