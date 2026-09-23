#!/usr/bin/env python
"""Run the strictly local personnel-orders reconstruction pilot.

The program intentionally has no API route and no migration.  It reads the
specified journal, makes draft-only inserts into existing personnel-order
tables, and leaves a PII-containing audit JSON only under local-archive.
Running it again is idempotent by ``Excel file + sheet + row``.
"""
from __future__ import annotations

import argparse
import json
import re
from functools import lru_cache
from datetime import date, datetime
from pathlib import Path
from typing import Any

from docx import Document
from openpyxl import load_workbook
from sqlalchemy import create_engine, text


PILOT = "personnel-orders-reconstruction-pilot-01"
SOURCE_FILE = Path(r"D:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\Журнал кадровых приказов\Ручное распознавание журналов.xlsx")
SHEET = "Лист1"
DOCX_ROOT = Path(r"D:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\2026 ПРИКАЗ")
ARCHIVE = Path("local-archive") / PILOT
REPORT = Path("docs/implementation/personnel-orders-reconstruction-pilot-01.md")
TITLE_TYPES = {
    "жұмысқа қабылдау туралы": "HIRE",
    "ауыстыру туралы": "TRANSFER",
    "қоса атқару туралы": "CONCURRENT_DUTY_START",
    "еңбек шартын бұзу туралы": "TERMINATION",
}
PLACEHOLDERS = {"[название отсутствует]", "", "-", "n/a"}


def clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def norm(value: str) -> str:
    return re.sub(r"[^а-яёәіңғүұқөһa-z]", "", clean(value).casefold().replace("ё", "е"))


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean(value), fmt).date()
        except ValueError:
            pass
    return None


def valid_date(value: Any) -> date | None:
    parsed = parse_date(value)
    # The source archive is explicitly 2026; 2027 is the known recognition error.
    return parsed if parsed and parsed.year == 2026 else None


def title_type(title: str) -> str | None:
    return TITLE_TYPES.get(clean(title).casefold())


def parse_people(value: Any) -> list[str]:
    return [clean(part) for part in re.split(r"[;,]", clean(value)) if clean(part)]


def initials_match(source: str, employee_name: str) -> bool:
    source_parts = clean(source).replace(".", " ").split()
    employee_parts = clean(employee_name).split()
    if not source_parts or not employee_parts or norm(source_parts[0]) != norm(employee_parts[0]):
        return False
    initials = [norm(part)[:1] for part in source_parts[1:] if norm(part)]
    candidate = [norm(part)[:1] for part in employee_parts[1:] if norm(part)]
    return not initials or candidate[: len(initials)] == initials


def match_people(source_people: list[str], employees: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    matches: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for source_name in source_people:
        candidates = [employee for employee in employees if initials_match(source_name, employee["full_name"])]
        if not candidates:
            unresolved.append(source_name)
            continue
        matches.append({
            "source_name": source_name,
            "employee_id": int(candidates[0]["employee_id"]) if len(candidates) == 1 else None,
            "match_status": "AUTO_MATCH" if len(candidates) == 1 else "AMBIGUOUS",
            "candidate_ids": [int(candidate["employee_id"]) for candidate in candidates],
            "employee": candidates[0] if len(candidates) == 1 else None,
        })
    return matches, unresolved


@lru_cache(maxsize=1)
def docx_index() -> tuple[tuple[Path, str], ...]:
    """Read each local DOCX once; source content is never copied to output."""
    indexed: list[tuple[Path, str]] = []
    for path in DOCX_ROOT.rglob("*.docx"):
        try:
            doc = Document(path)
            indexed.append((path, "\n".join(p.text for p in doc.paragraphs)))
        except Exception:
            indexed.append((path, ""))
    return tuple(indexed)


def find_docx(order_number: str, order_date: date) -> str | None:
    needle = re.sub(r"\s+", "", order_number).casefold()
    indexed = docx_index()
    for path, _ in indexed:
        compact = re.sub(r"\s+", "", path.stem).casefold()
        if needle and needle in compact:
            return str(path)
    # File names are not authoritative.  A narrow contents check is used only
    # as a DOCX-presence marker and never changes reconstructed fields.
    date_tokens = {order_date.strftime("%d.%m.%Y"), order_date.isoformat()}
    for path, content in indexed:
        if order_number in content and any(token in content for token in date_tokens):
            return str(path)
    return None


def signatory_role_from_docx(docx_path: str | None) -> str:
    """Use a found source only to distinguish director from acting director."""
    if docx_path:
        try:
            content = "\n".join(paragraph.text for paragraph in Document(docx_path).paragraphs).casefold()
            if any(marker in content for marker in (
                "и. о. директора", "ио директора", "директордың міндетін атқарушы",
            )):
                return "ACTING_DIRECTOR"
        except Exception:
            pass
    return "DIRECTOR"


def assignment_payload(employee: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    if employee is None:
        return {}, []
    # Current employees table has no effective-dated assignment history.
    # Consequently every copied appointment is explicit about this assumption.
    assumptions = ["CURRENT_PRIMARY_ASSIGNMENT_USED_NO_HISTORICAL_ASSIGNMENT"]
    unit_name = clean(employee.get("unit_name"))
    position_name = clean(employee.get("position_name"))
    return {
        "assignment": {
            "unit": {"kk": unit_name, "ru": unit_name},
            "position": {"kk": position_name, "ru": position_name},
            "rate": "1.0",
        },
        "employee": {"name": {"canonical": clean(employee.get("full_name"))}},
    }, assumptions


def source_key(row_number: int) -> str:
    return f"{SOURCE_FILE.name}|{SHEET}|{row_number}"


def load_candidates(conn) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    employees = [dict(row) for row in conn.execute(text("""
        SELECT e.employee_id, e.full_name, e.org_unit_id, e.position_id,
               ou.name AS unit_name, p.name AS position_name
        FROM public.employees e
        LEFT JOIN public.org_units ou ON ou.unit_id = e.org_unit_id
        LEFT JOIN public.positions p ON p.position_id = e.position_id
        WHERE e.full_name IS NOT NULL AND btrim(e.full_name) <> ''
    """)).mappings()]
    existing = set(conn.execute(text("""
        SELECT storage_json ->> 'source_identifier'
        FROM public.personnel_orders
        WHERE storage_json ->> 'reconstruction_pilot' = :pilot
    """), {"pilot": PILOT}).scalars())
    wb = load_workbook(SOURCE_FILE, read_only=True, data_only=True)
    ws = wb[SHEET]
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row_number, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        pdf, page, number, title, raw_date, _, figures, note, *_ = row
        key = source_key(row_number)
        if key in existing:
            continue
        action = title_type(clean(title))
        if action is None:
            continue
        order_date = valid_date(raw_date)
        if order_date is None:
            skipped.append({"excel_row": row_number, "order_number": clean(number), "reason": "MISSING_OR_INVALID_2026_DATE"})
            continue
        if clean(title).casefold() in PLACEHOLDERS:
            skipped.append({"excel_row": row_number, "order_number": clean(number), "reason": "PLACEHOLDER_TITLE"})
            continue
        people = parse_people(figures)
        matches, unresolved = match_people(people, employees)
        if not people or unresolved:
            skipped.append({"excel_row": row_number, "order_number": clean(number), "reason": "UNRESOLVABLE_SURNAME", "unresolved": unresolved})
            continue
        selected.append({
            "excel_row": row_number, "source_identifier": key, "pdf": clean(pdf), "pdf_page": clean(page),
            "order_number": f"{clean(number)}-ж", "order_date": order_date, "source_title": clean(title),
            "figures": clean(figures), "source_note": clean(note), "action": action, "matches": matches,
        })
        if len(selected) == 20:
            break
    return selected, skipped


def run(database_url: str, *, dry_run: bool) -> dict[str, Any]:
    engine = create_engine(database_url)
    with engine.begin() as conn:
        existing_count = int(conn.execute(text("""
            SELECT COUNT(*) FROM public.personnel_orders
            WHERE storage_json ->> 'reconstruction_pilot' = :pilot
        """), {"pilot": PILOT}).scalar_one())
        if existing_count:
            if existing_count != 20:
                raise RuntimeError(f"Pilot is incomplete: expected 20 existing drafts, found {existing_count}")
            archived = ARCHIVE / "run-report.json"
            if not archived.is_file():
                raise RuntimeError("Pilot drafts exist but their local PII audit JSON is missing")
            conn.execute(text("""
                INSERT INTO public.personnel_order_evidence_scopes(order_id)
                SELECT po.order_id
                FROM public.personnel_orders po
                LEFT JOIN public.personnel_order_evidence_scopes scope ON scope.order_id = po.order_id
                WHERE po.storage_json ->> 'reconstruction_pilot' = :pilot
                  AND scope.order_id IS NULL
                ON CONFLICT (order_id) DO NOTHING
            """), {"pilot": PILOT})
            result = json.loads(archived.read_text(encoding="utf-8"))
            result["dry_run"] = dry_run
            result["rerun_noop"] = True
            return result
        selected, skipped = load_candidates(conn)
        if len(selected) != 20:
            raise RuntimeError(f"Expected 20 eligible rows; found {len(selected)}")
        creator = conn.execute(text("SELECT user_id FROM public.users ORDER BY user_id LIMIT 1")).scalar_one()
        report_rows: list[dict[str, Any]] = []
        for candidate in selected:
            docx = find_docx(candidate["order_number"].removesuffix("-ж"), candidate["order_date"])
            auto_fields = ["effective_date=order_date", "rate=1.0", "basis=personal_application"]
            storage = {
                "reconstruction_pilot": PILOT,
                "reconstruction_status": "NEEDS_DOCX_REVIEW",
                "source_identifier": candidate["source_identifier"],
                "source_excel": {"file": str(SOURCE_FILE), "sheet": SHEET, "row": candidate["excel_row"]},
                "source_pdf": {"file": candidate["pdf"], "page": candidate["pdf_page"]},
                "source_title": candidate["source_title"], "source_figures": candidate["figures"],
                "auto_filled_fields": auto_fields, "docx_found": bool(docx), "docx_path": docx,
                "basis_documents": [{"basis_id": "application", "document_type": "EMPLOYEE_APPLICATION",
                                      "description": {"ru": "Личное заявление работника", "kk": "Қызметкердің жеке өтініші"}}],
            }
            order_id = None
            if not dry_run:
                order_id = conn.execute(text("""
                    INSERT INTO public.personnel_orders
                    (order_number, order_date, order_type_code, status, source_mode, basis_summary, storage_json, created_by)
                    VALUES (:number, :order_date, :action, 'DRAFT', 'PAPER', :basis, CAST(:storage AS jsonb), :creator)
                    RETURNING order_id
                """), {"number": candidate["order_number"], "order_date": candidate["order_date"], "action": candidate["action"],
                          "basis": "Личное заявление работника", "storage": json.dumps(storage, ensure_ascii=False), "creator": creator}).scalar_one()
                conn.execute(text("INSERT INTO public.personnel_order_evidence_scopes(order_id) VALUES (:order_id)"), {"order_id": order_id})
                for item_number, match in enumerate(candidate["matches"], start=1):
                    payload, assumptions = assignment_payload(match["employee"])
                    payload.update({"source_employee_name": match["source_name"], "rate": 1.0, "basis_ids": ["application"],
                                    "reconstruction_assumptions": assumptions})
                    conn.execute(text("""
                        INSERT INTO public.personnel_order_items
                        (order_id, item_number, item_type_code, employee_id, effective_date, payload, item_status)
                        VALUES (:order_id, :item_number, :action, :employee_id, :effective_date, CAST(:payload AS jsonb), 'ACTIVE')
                    """), {"order_id": order_id, "item_number": item_number, "action": candidate["action"],
                              "employee_id": match["employee_id"], "effective_date": candidate["order_date"],
                              "payload": json.dumps(payload, ensure_ascii=False)})
            report_rows.append({**candidate, "order_id": order_id, "docx_path": docx})
    return {"pilot": PILOT, "dry_run": dry_run, "orders": report_rows, "skipped": skipped}


def write_outputs(result: dict[str, Any]) -> None:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    (ARCHIVE / "run-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = ["# Personnel orders reconstruction pilot 01", "", "Local-only draft reconstruction. No employee events or assignments were created or changed.", "", f"Source: `{SOURCE_FILE}` · sheet `{SHEET}`.", "", "## Imported drafts", "", "| Excel row | Order | Date | template_key | order_id | DOCX | Visual check |", "|---:|---|---|---|---:|---|---|"]
    for row in result["orders"]:
        oid = row["order_id"] or "dry-run"
        link = f"/directory/personnel/orders?order_id={oid}" if row["order_id"] else "—"
        lines.append(f"| {row['excel_row']} | {row['order_number']} | {row['order_date']} | {row.get('template_key') or 'absent'} | {oid} | {'found' if row['docx_path'] else 'not found'} | {link} |")
    absent_templates = [row["order_number"] for row in result["orders"] if not row.get("template_key")]
    lines += ["", "## Template resolution", "", "- No pilot order is without an approved template." if not absent_templates else f"- Approved template absent: {', '.join(absent_templates)}."]
    auto_matches = sum(1 for row in result["orders"] for match in row["matches"] if match["match_status"] == "AUTO_MATCH")
    ambiguous_matches = sum(1 for row in result["orders"] for match in row["matches"] if match["match_status"] == "AMBIGUOUS")
    lines += ["", "## Matching and assumptions", "", f"- Matched people: {auto_matches} automatic, {ambiguous_matches} ambiguous (their source FIO is retained without employee_id); no unresolved people were imported.", "- employee_id is written only for an unambiguous surname-and-initials match; ambiguous matches retain source FIO in the item payload.", "- The database has no historical assignment table. Current primary employee position/unit was copied when available and is marked `CURRENT_PRIMARY_ASSIGNMENT_USED_NO_HISTORICAL_ASSIGNMENT`.", "- Effective date defaults to order date; rate defaults to 1.0; basis defaults to the bilingual personal application.", "- The current default signatory is filled only when all signatory fields of a pilot draft are empty; the storage assumption is `CURRENT_DEFAULT_SIGNATORY_USED`.", "", "## Bilingual template corrections", "", "- Approved titles are selected by action type, including `О переводе` (not `О постоянном переводе`); see `personnel-order-titles-bilingual-dictionary.md`.", "- The general renderer maps `медсестра` and `медицинская сестра` to `мейіргер` before rendering Kazakh. Proposed pilot position/unit values are listed in the existing bilingual dictionaries.", "- Template limitations: the generic wording remains a reconstruction and must be checked against DOCX; no native imported text or editorial overrides are overwritten.", "", "## Skipped rows", ""]
    if result["skipped"]:
        for row in result["skipped"]:
            lines.append(f"- Excel row {row['excel_row']}: {row['reason']}.")
    else:
        lines.append("- None before the first 20 eligible records.")
    lines += ["", "## Russian automatic wording", "", "- When unused leave days are not confirmed, the accounting point is `Бухгалтерии произвести расчёт за неиспользованные дни отпуска.`; no dash, count, or `календарных дней` is rendered.", "- Russian automatic position/unit wording is `должность (подразделение)`. The added order-text form is `Приемное` → `приемное отделение` (PROPOSED); an unknown unit is only normalized to lower case and remains marked for dictionary review."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_bilingual_presentations(database_url: str, result: dict[str, Any]) -> dict[int, str | None]:
    """Use the existing editorial generators, then expose both draft locales."""
    from app.services.personnel_orders_editorial_service import generate_editorial
    from app.services.personnel_order_signatory_resolver import resolve_default_personnel_order_signatory

    approved = {
        "personnel.hire.standard",
        "personnel.transfer.permanent",
        "personnel.concurrent-duty.start",
        "personnel.termination.employee-initiative-unused-leave",
        "personnel.transfer.permanent-with-concurrent-duty",
    }
    by_type = {
        "HIRE": "personnel.hire.standard",
        "TRANSFER": "personnel.transfer.permanent",
        "CONCURRENT_DUTY_START": "personnel.concurrent-duty.start",
        "TERMINATION": "personnel.termination.employee-initiative-unused-leave",
    }
    order_ids = [int(row["order_id"]) for row in result["orders"] if row.get("order_id")]
    pilot_signatory_roles = {
        int(row["order_id"]): signatory_role_from_docx(row.get("docx_path"))
        for row in result["orders"] if row.get("order_id")
    }
    selected: dict[int, str | None] = {}
    engine = create_engine(database_url)
    with engine.begin() as conn:
        signatory = resolve_default_personnel_order_signatory(conn)
        if signatory.resolved:
            conn.execute(text("""
                UPDATE public.personnel_orders
                SET signed_by_employee_id = :employee_id,
                    signed_by_name = :name,
                    signed_by_position = :position,
                    storage_json = storage_json || CAST(:metadata AS jsonb),
                    updated_at = transaction_timestamp()
                WHERE order_id = ANY(:order_ids)
                  AND signed_by_employee_id IS NULL
                  AND NULLIF(BTRIM(signed_by_name), '') IS NULL
                  AND NULLIF(BTRIM(signed_by_position), '') IS NULL
            """), {
                "order_ids": order_ids,
                "employee_id": signatory.employee_id,
                "name": signatory.signed_by_name,
                "position": signatory.signed_by_position,
                "metadata": json.dumps({
                    "reconstruction_signatory_source": signatory.source,
                    "reconstruction_assumptions": ["CURRENT_DEFAULT_SIGNATORY_USED"],
                }),
            })
        for order_id, role in pilot_signatory_roles.items():
            conn.execute(text("""
                UPDATE public.personnel_orders
                SET signed_by_position = :role,
                    storage_json = jsonb_set(
                        storage_json,
                        '{reconstruction}',
                        COALESCE(storage_json -> 'reconstruction', '{}'::jsonb) || CAST(:reconstruction AS jsonb),
                        TRUE
                    ) || CAST(:marker AS jsonb),
                    updated_at = transaction_timestamp()
                WHERE order_id = :order_id
                  AND storage_json ->> 'reconstruction_pilot' = :pilot
                  AND storage_json ->> 'signatory_role_reconstruction_initialized' IS NULL
            """), {
                "order_id": order_id,
                "role": role,
                "pilot": PILOT,
                "reconstruction": json.dumps({
                    "assumptions": [
                        "DOCX_SIGNATORY_ROLE_ACTING_DIRECTOR"
                        if role == "ACTING_DIRECTOR" else "DEFAULT_SIGNATORY_ROLE_DIRECTOR"
                    ],
                }),
                "marker": json.dumps({"signatory_role_reconstruction_initialized": True}),
            })
        source_rows = conn.execute(text("""
            SELECT po.order_id, po.order_type_code, po.storage_json,
                   array_agg(DISTINCT poi.item_type_code) FILTER (WHERE poi.item_type_code IS NOT NULL) AS item_types
            FROM public.personnel_orders po
            LEFT JOIN public.personnel_order_items poi ON poi.order_id = po.order_id
            WHERE po.order_id = ANY(:order_ids)
            GROUP BY po.order_id, po.order_type_code, po.storage_json
        """), {"order_ids": order_ids}).mappings()
        for source in source_rows:
            storage = source["storage_json"] if isinstance(source["storage_json"], dict) else {}
            saved = storage.get("template_key")
            types = {str(value).upper() for value in (source["item_types"] or [])}
            key = saved if saved in approved else (
                "personnel.transfer.permanent-with-concurrent-duty"
                if {"TRANSFER", "CONCURRENT_DUTY_START"}.issubset(types)
                else by_type.get(next(iter(types))) if len(types) == 1 else by_type.get(str(source["order_type_code"]).upper())
            )
            selected[int(source["order_id"])] = key
            if key:
                conn.execute(text("""
                    UPDATE public.personnel_orders
                    SET storage_json = storage_json || CAST(:template AS jsonb), updated_at = transaction_timestamp()
                    WHERE order_id = :order_id
                """), {"order_id": int(source["order_id"]), "template": json.dumps({
                    "template_key": key, "template_version": 1,
                    "template_versions": {"kk": 1, "ru": 1},
                    "template_resolution": "AUTO_BY_PERSONNEL_ORDER_ITEMS",
                })})
    for order_id in order_ids:
        generate_editorial(order_id, user_id=1)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO public.personnel_order_localized_texts
                (order_id, locale, title, preamble, body_text, is_authoritative)
            SELECT po.order_id, block.locale,
                   max(COALESCE(block.override_text, block.generated_text)) FILTER (WHERE block.block_type = 'title'),
                   max(COALESCE(block.override_text, block.generated_text)) FILTER (WHERE block.block_type = 'preamble'),
                   NULL, block.locale = 'kk'
            FROM public.personnel_orders po
            JOIN public.personnel_order_editorial_blocks block ON block.order_id = po.order_id
            WHERE po.storage_json ->> 'reconstruction_pilot' = :pilot
            GROUP BY po.order_id, block.locale
            ON CONFLICT (order_id, locale) DO UPDATE SET
                title = EXCLUDED.title,
                preamble = EXCLUDED.preamble,
                updated_at = transaction_timestamp()
            WHERE NOT EXISTS (
                SELECT 1
                FROM public.personnel_order_editorial_blocks existing_block
                WHERE existing_block.order_id = personnel_order_localized_texts.order_id
                  AND existing_block.locale = personnel_order_localized_texts.locale
                  AND existing_block.override_text IS NOT NULL
            )
        """), {"pilot": PILOT})
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run(args.database_url, dry_run=args.dry_run)
    if not args.dry_run:
        templates = ensure_bilingual_presentations(args.database_url, result)
        for row in result["orders"]:
            row["template_key"] = templates.get(int(row["order_id"])) if row.get("order_id") else None
    write_outputs(result)
    print(json.dumps({"orders": len(result["orders"]), "skipped": len(result["skipped"]), "dry_run": args.dry_run}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
