"""Local-only, exact-IIN importer for qualification categories from the June list."""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
import json
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import text

from app.db.engine import DATABASE_URL, engine
from app.personnel_intake.domain.additional_profile import normalize_additional_profile
from app.services.hr_import_qualification_category_service import parse_qualification_categories

IIN_HEADER = "ИИН"
CATEGORY_HEADER = "Квалификационная категория"
POLICY = "CONTROL_LIST_QUALIFICATION_CATEGORY_V1_EXCEL_VERIFIED"


def _loopback_only() -> None:
    if not any(host in DATABASE_URL.lower() for host in ("127.0.0.1", "localhost")):
        raise RuntimeError("refusing non-local database")


def _source_rows(source: Path) -> list[tuple[str, str]]:
    workbook = load_workbook(source, read_only=True, data_only=True)
    rows: list[tuple[str, str]] = []
    for sheet in workbook.worksheets:
        header = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True))
        columns = {str(value).strip(): index for index, value in enumerate(header) if value is not None}
        if IIN_HEADER not in columns or CATEGORY_HEADER not in columns:
            raise RuntimeError(f"required columns absent on sheet {sheet.title!r}")
        for row in sheet.iter_rows(min_row=2, values_only=True):
            iin = str(row[columns[IIN_HEADER]] or "").strip()
            raw = str(row[columns[CATEGORY_HEADER]] or "").strip()
            if iin.isdigit() and len(iin) == 12 and raw:
                rows.append((iin, raw))
    return rows


def import_categories(*, source: Path, batch_id: int, cohort_run_id: int = 3) -> dict[str, int]:
    _loopback_only()
    excel = _source_rows(source)
    iin_count = Counter(iin for iin, _ in excel)
    result = {"source_nonempty": len(excel), "unmatched": 0, "mismatched_source": 0, "outside_cohort": 0,
              "parsed_records": 0, "auto_ready": 0, "review_required": 0, "written_cards": 0,
              "written_records": 0, "already_present": 0, "preserved_hr_confirmed": 0}
    with engine.begin() as conn:
        cohort_people = set(conn.execute(text("SELECT person_id FROM public.ppr_stage0_cohort_participants WHERE stage0_cohort_run_id=:run"), {"run": cohort_run_id}).scalars())
        people: dict[str, list[dict]] = defaultdict(list)
        for row in conn.execute(text("SELECT p.iin,p.person_id,e.employee_id FROM public.persons p JOIN public.employees e ON e.person_id=p.person_id WHERE p.iin IS NOT NULL")).mappings():
            people[str(row["iin"])].append(dict(row))
        source_rows: dict[str, list[dict]] = defaultdict(list)
        for row in conn.execute(text("SELECT row_id,normalized_payload->>'iin' AS iin,normalized_payload->>'certification_raw' AS certification_raw FROM public.hr_import_rows WHERE batch_id=:batch"), {"batch": batch_id}).mappings():
            source_rows[str(row["iin"] or "").strip()].append(dict(row))
        for iin, raw in excel:
            if iin_count[iin] != 1 or len(people[iin]) != 1 or len(source_rows[iin]) != 1:
                result["unmatched"] += 1; continue
            person = people[iin][0]
            if person["person_id"] not in cohort_people:
                result["outside_cohort"] += 1; continue
            source_row = source_rows[iin][0]
            # IIN uniquely binds this worksheet row to batch 809.  The payload
            # is retained only as an audit cross-check: Excel formatting of a
            # date may differ from normalized JSON, so equality is not an
            # identity criterion and must not discard a deterministically bound
            # row.
            if raw != str(source_row["certification_raw"] or "").strip():
                result["mismatched_source"] += 1
            parsed = parse_qualification_categories(raw)
            result["parsed_records"] += len(parsed)
            result["auto_ready"] += sum(item.review_status == "AUTO_READY" for item in parsed)
            result["review_required"] += sum(item.review_status == "REVIEW_REQUIRED" for item in parsed)
            if not parsed:
                continue
            current = conn.execute(text("SELECT additional_profile FROM public.personnel_record_metadata WHERE person_id=:person_id FOR UPDATE"), {"person_id": person["person_id"]}).scalar_one_or_none()
            current = json.loads(current) if isinstance(current, str) else (current or {})
            profile = normalize_additional_profile(current)
            existing = profile.get("qualification_categories") or []
            if any(not isinstance(item.get("provenance"), dict) or item["provenance"].get("source") != "excel_control_list" for item in existing):
                result["preserved_hr_confirmed"] += 1; continue
            keys = {(item.get("provenance") or {}).get("source_row_id") for item in existing if isinstance(item, dict)}
            existing = [item for item in existing if (item.get("provenance") or {}).get("source_row_id") != source_row["row_id"]]
            additions = []
            for item in parsed:
                additions.append({"specialty": item.specialty, "category": item.category, "assigned_at": item.assigned_at,
                                  "assigned_at_calculated": item.assigned_at_calculated, "review_status": item.review_status,
                                  "review_reason": item.review_reason, "provenance": {"source": "excel_control_list", "source_batch_id": batch_id,
                                  "source_row_id": source_row["row_id"], "source_field": CATEGORY_HEADER, "override_origin": "none",
                                  "source_policy_version": POLICY, "source_fingerprint": item.fingerprint,
                                  "assigned_at_calculated_from_expiry": item.assigned_at_calculated}})
            if not additions: continue
            if source_row["row_id"] in keys:
                result["already_present"] += len(additions)
            profile["qualification_categories"] = existing + additions
            conn.execute(text("""INSERT INTO public.personnel_record_metadata(person_id,additional_profile) VALUES(:person_id,CAST(:profile AS jsonb))
                ON CONFLICT(person_id) DO UPDATE SET additional_profile=EXCLUDED.additional_profile,updated_at=now()"""),
                {"person_id": person["person_id"], "profile": json.dumps(profile, ensure_ascii=False)})
            result["written_cards"] += 1; result["written_records"] += len(additions)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument("--source-b64")
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument("--cohort-run-id", type=int, default=3)
    args = parser.parse_args()
    source = args.source or Path(base64.b64decode(args.source_b64).decode("utf-8"))
    print(import_categories(source=source, batch_id=args.batch_id, cohort_run_id=args.cohort_run_id))
