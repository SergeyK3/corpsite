#!/usr/bin/env python
"""Run the strictly local personnel-orders reconstruction pilot.

The program intentionally has no API route and no migration.  It reads the
specified journal, makes draft-only inserts into existing personnel-order
tables, and leaves a PII-containing audit JSON only under local-archive.
Running it again is idempotent by ``Excel file + sheet + row``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from contextlib import nullcontext
from functools import lru_cache
from datetime import date, datetime
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from docx import Document
from openpyxl import load_workbook
from sqlalchemy import create_engine, text


PILOT = "personnel-orders-reconstruction-pilot-01"
REQUIRE_SOURCE_INITIALS = False
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
    # The latter two are the three unambiguous source-recorded variants.  The
    # similarly worded withdrawal title is deliberately not classified here.
    "қосымша ақы туралы": "SUPPLEMENTARY_PAY",
    "қосымша ақы төлеу туралы": "SUPPLEMENTARY_PAY",
    "жұмысқа қосымша ақы туралы": "SUPPLEMENTARY_PAY",
    "жұмысқа қосымша ақы төлеу туралы": "SUPPLEMENTARY_PAY",
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
    if REQUIRE_SOURCE_INITIALS and len(source_parts) < 2:
        return False
    initials = [norm(part)[:1] for part in source_parts[1:] if norm(part)]
    candidate = [norm(part)[:1] for part in employee_parts[1:] if norm(part)]
    return not initials or candidate[: len(initials)] == initials


def match_people(source_people: list[str], employees: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retain every Excel figure, including ones requiring manual review."""
    matches: list[dict[str, Any]] = []
    for source_name in source_people:
        candidates = [employee for employee in employees if initials_match(source_name, employee["full_name"])]
        if not candidates:
            matches.append({
                "source_name": source_name,
                "employee_id": None,
                "match_status": "UNRESOLVED",
                "candidate_ids": [],
                "employee": None,
            })
            continue
        matches.append({
            "source_name": source_name,
            "employee_id": int(candidates[0]["employee_id"]) if len(candidates) == 1 else None,
            "match_status": "AUTO_MATCH" if len(candidates) == 1 else "AMBIGUOUS",
            "candidate_ids": [int(candidate["employee_id"]) for candidate in candidates],
            "employee": candidates[0] if len(candidates) == 1 else None,
        })
    return matches


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
        if "2025-2026" in path.stem:
            continue
        # Consolidated registers (for example the vacation collection) are not
        # evidence for an individual personnel order.
        if "РїСЂРёРєР°Р·С‹ 2025-2026 РЅР° РѕС‚РїСѓСЃРє" in path.stem.casefold():
            continue
        compact = re.sub(r"\s+", "", path.stem).casefold()
        if needle and needle in compact:
            return str(path)
    # File names are not authoritative.  A narrow contents check is used only
    # as a DOCX-presence marker and never changes reconstructed fields.
    date_tokens = {order_date.strftime("%d.%m.%Y"), order_date.isoformat()}
    for path, content in indexed:
        if "2025-2026" in path.stem:
            continue
        if "РїСЂРёРєР°Р·С‹ 2025-2026 РЅР° РѕС‚РїСѓСЃРє" in path.stem.casefold():
            continue
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


def template_key_for(action: str) -> str:
    return {
        "HIRE": "personnel.hire.standard",
        "TRANSFER": "personnel.transfer.permanent",
        "CONCURRENT_DUTY_START": "personnel.concurrent-duty.start",
        "TERMINATION": "personnel.termination.employee-initiative-unused-leave",
        "SUPPLEMENTARY_PAY": "personnel.supplementary-pay.review",
    }[action]


def load_manifest(path: Path | None) -> dict[str, dict[str, Any]] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("orders")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Manifest must contain at least one order")
    indexed = {str(row.get("source_identifier")): row for row in rows}
    if len(indexed) != len(rows) or "None" in indexed:
        raise RuntimeError("Manifest has missing or duplicate source_identifier values")
    return indexed


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest_files(path: Path, source_file: Path) -> None:
    """Reject a moved/tampered package before it is allowed to query or write."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = payload.get("source_excel", {})
    if source.get("path") != source_file.name or source.get("sha256") != sha256(source_file):
        raise RuntimeError("Excel source does not match the package manifest SHA-256")
    package_root = path.parent.resolve()
    for item in payload.get("docx_files", []):
        file_path = (package_root / str(item.get("path", ""))).resolve()
        if package_root not in file_path.parents or not file_path.is_file():
            raise RuntimeError(f"Manifest DOCX is outside package or missing: {item.get('path')}")
        if item.get("sha256") != sha256(file_path):
            raise RuntimeError(f"Manifest DOCX SHA-256 mismatch: {item.get('path')}")


def load_candidates(conn, manifest: dict[str, dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
        if key in existing and manifest is None:
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
        if not people:
            skipped.append({"excel_row": row_number, "order_number": clean(number), "reason": "EMPTY_FIGURES"})
            continue
        matches = match_people(people, employees)
        candidate = {
            "excel_row": row_number, "source_identifier": key, "pdf": clean(pdf), "pdf_page": clean(page),
            "order_number": f"{clean(number)}-ж", "order_date": order_date, "source_title": clean(title),
            "figures": clean(figures), "source_note": clean(note), "action": action, "matches": matches,
        }
        if manifest is not None:
            expected = manifest.get(key)
            if expected is None:
                continue
            if (clean(expected.get("order_number")) != candidate["order_number"]
                    or clean(expected.get("order_date")) != candidate["order_date"].isoformat()
                    or expected.get("template_key") != template_key_for(action)):
                raise RuntimeError(f"Manifest does not match Excel source row {key}")
        selected.append(candidate)
        if manifest is None and len(selected) == 20:
            break
    if manifest is not None:
        actual = {row["source_identifier"] for row in selected}
        missing = set(manifest) - actual
        if missing:
            raise RuntimeError(f"Manifest rows not selected from Excel: {sorted(missing)}")
    return selected, skipped


LEGACY_TECHNICAL_PREFIXES = ("PERSONNEL-IMPORT-", "CSV-PILOT-")


def classify_employee_action_matches(rows: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    """Separate technical predecessor orders from blocking business duplicates."""
    legacy: list[int] = []
    blocking: list[int] = []
    for row in rows:
        order_id = int(row["order_id"])
        order_number = clean(row.get("order_number")).upper()
        (legacy if order_number.startswith(LEGACY_TECHNICAL_PREFIXES) else blocking).append(order_id)
    return sorted(set(blocking)), sorted(set(legacy))


def has_blocking_duplicates(finding: dict[str, Any]) -> bool:
    return any(finding["blocking_duplicates"].values())


def duplicate_check(conn, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Report every requested collision before an apply; it never changes data."""
    findings: list[dict[str, Any]] = []
    for candidate in candidates:
        number_only = conn.execute(text("""
            SELECT order_id FROM public.personnel_orders
            WHERE order_number = :number
        """), {"number": candidate["order_number"]}).scalars().all()
        number_date = conn.execute(text("""
            SELECT order_id FROM public.personnel_orders
            WHERE order_number = :number AND order_date = :order_date
        """), {"number": candidate["order_number"], "order_date": candidate["order_date"]}).scalars().all()
        source_row = conn.execute(text("""
            SELECT order_id FROM public.personnel_orders
            WHERE storage_json ->> 'source_identifier' = :source_identifier
        """), {"source_identifier": candidate["source_identifier"]}).scalars().all()
        employee_action_rows: list[dict[str, Any]] = []
        for match in candidate["matches"]:
            if match["employee_id"] is not None:
                employee_action_rows.extend(dict(row) for row in conn.execute(text("""
                    SELECT DISTINCT po.order_id, po.order_number
                    FROM public.personnel_orders po
                    JOIN public.personnel_order_items poi ON poi.order_id = po.order_id
                    WHERE poi.employee_id = :employee_id AND poi.item_type_code = :action
                """), {"employee_id": match["employee_id"], "action": candidate["action"]}).mappings())
        blocking_employee_action, legacy_technical = classify_employee_action_matches(employee_action_rows)
        findings.append({
            "source_identifier": candidate["source_identifier"],
            "blocking_duplicates": {
                "order_number": sorted(set(map(int, number_only))),
                "order_number_and_date": sorted(set(map(int, number_date))),
                "source_excel_row": sorted(set(map(int, source_row))),
                "employee_and_action": blocking_employee_action,
            },
            "legacy_technical_matches": legacy_technical,
        })
    return findings


def manifest_resume_rows(conn, manifest: dict[str, dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Return all pre-existing manifest drafts, or reject a dangerous partial pilot."""
    rows = [dict(row) for row in conn.execute(text("""
        SELECT order_id, order_number, order_date, order_type_code, storage_json
        FROM public.personnel_orders
        WHERE storage_json ->> 'reconstruction_pilot' = :pilot
          AND storage_json ->> 'source_identifier' = ANY(:source_identifiers)
        ORDER BY order_id
    """), {"pilot": PILOT, "source_identifiers": list(manifest)}).mappings()]
    present = {str((row.get("storage_json") or {}).get("source_identifier")) for row in rows}
    if not present:
        return None
    if len(present) != len(manifest):
        raise RuntimeError(f"PARTIAL_PILOT_STATE: found {len(present)} of {len(manifest)} manifest orders")
    return rows


def resume_result(conn, manifest: dict[str, dict[str, Any]], rows: list[dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
    order_ids = [int(row["order_id"]) for row in rows]
    scope_count = int(conn.execute(text("""
        SELECT COUNT(*) FROM public.personnel_order_evidence_scopes
        WHERE order_id = ANY(:order_ids)
    """), {"order_ids": order_ids}).scalar_one())
    locale_count = int(conn.execute(text("""
        SELECT COUNT(*) FROM public.personnel_order_localized_texts
        WHERE order_id = ANY(:order_ids) AND locale IN ('kk', 'ru')
    """), {"order_ids": order_ids}).scalar_one())
    needs_repair = scope_count != len(order_ids) or locale_count != len(order_ids) * 2
    if needs_repair and not dry_run:
        conn.execute(text("""
            INSERT INTO public.personnel_order_evidence_scopes(order_id)
            SELECT po.order_id
            FROM public.personnel_orders po
            LEFT JOIN public.personnel_order_evidence_scopes scope ON scope.order_id = po.order_id
            WHERE po.order_id = ANY(:order_ids) AND scope.order_id IS NULL
            ON CONFLICT (order_id) DO NOTHING
        """), {"order_ids": order_ids})
    orders: list[dict[str, Any]] = []
    for row in rows:
        storage = row["storage_json"] if isinstance(row["storage_json"], dict) else {}
        source_identifier = str(storage["source_identifier"])
        manifest_row = manifest[source_identifier]
        order_number = str(row["order_number"])
        order_date = row["order_date"]
        orders.append({
            "order_id": int(row["order_id"]), "source_identifier": source_identifier,
            "excel_row": manifest_row["excel_row"], "order_number": order_number,
            "order_date": order_date, "action": str(row["order_type_code"]),
            "matches": storage.get("employee_matches", []),
            "docx_path": find_docx(order_number.removesuffix("-ж"), order_date),
            "template_key": storage.get("template_key") or manifest_row.get("template_key"),
            "employee_match_review_required": bool(storage.get("employee_match_review_required")),
            "duplicate_checks": {"source_identifier": source_identifier, "blocking_duplicates": {
                "order_number": [], "order_number_and_date": [], "source_excel_row": [], "employee_and_action": [],
            }, "legacy_technical_matches": storage.get("reconstruction", {}).get("legacy_technical_order_ids", [])},
        })
    return {
        "pilot": PILOT, "dry_run": dry_run, "orders": orders, "skipped": [],
        "duplicate_check": [], "blocking_duplicates": [], "legacy_technical_matches": [],
        "resumed": needs_repair, "rerun_noop": not needs_repair,
        "needs_presentation_repair": needs_repair,
    }


def run(
    database_url: str,
    *,
    dry_run: bool,
    manifest_path: Path | None = None,
    conn=None,
) -> dict[str, Any]:
    """Build the reconstruction result using an optional caller-owned connection.

    ``conn`` is used by the apply CLI to keep inserts and generated
    presentations in one database transaction. Dry-runs intentionally retain
    their independent read-only connection.
    """
    if dry_run and conn is not None:
        raise RuntimeError("dry-run must not receive a write transaction connection")
    engine = None if conn is not None else create_engine(database_url)
    manifest = load_manifest(manifest_path)
    # A dry run deliberately uses a non-transactional read-only connection:
    # no repair, audit, scope, or report database writes are possible here.
    connection_context = nullcontext(conn) if conn is not None else (
        engine.connect() if dry_run else engine.begin()
    )
    with connection_context as active_conn:
        if manifest is not None:
            existing_manifest_rows = manifest_resume_rows(active_conn, manifest)
            if existing_manifest_rows is not None:
                return resume_result(active_conn, manifest, existing_manifest_rows, dry_run=dry_run)
        existing_count = int(active_conn.execute(text("""
            SELECT COUNT(*) FROM public.personnel_orders
            WHERE storage_json ->> 'reconstruction_pilot' = :pilot
        """), {"pilot": PILOT}).scalar_one())
        if existing_count and manifest is None:
            if existing_count != 20:
                raise RuntimeError(f"Pilot is incomplete: expected 20 existing drafts, found {existing_count}")
            archived = ARCHIVE / "run-report.json"
            if not archived.is_file():
                raise RuntimeError("Pilot drafts exist but their local PII audit JSON is missing")
            if not dry_run:
                active_conn.execute(text("""
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
        selected, skipped = load_candidates(active_conn, manifest)
        expected_count = len(manifest) if manifest is not None else 20
        if len(selected) != expected_count:
            raise RuntimeError(f"Expected {expected_count} eligible rows; found {len(selected)}")
        duplicates = duplicate_check(active_conn, selected)
        duplicates_by_source = {row["source_identifier"]: row for row in duplicates}
        if not dry_run and any(has_blocking_duplicates(row) for row in duplicates):
            raise RuntimeError("Potential duplicates found; inspect a --dry-run report before apply")
        creator = None if dry_run else active_conn.execute(text("SELECT user_id FROM public.users ORDER BY user_id LIMIT 1")).scalar_one()
        report_rows: list[dict[str, Any]] = []
        for candidate in selected:
            docx = find_docx(candidate["order_number"].removesuffix("-ж"), candidate["order_date"])
            supplementary_pay = candidate["action"] == "SUPPLEMENTARY_PAY"
            auto_fields = [] if supplementary_pay else ["effective_date=order_date", "rate=1.0", "basis=personal_application"]
            duplicate_result = duplicates_by_source.get(candidate["source_identifier"], {
                "source_identifier": candidate["source_identifier"],
                "blocking_duplicates": {
                    "order_number": [], "order_number_and_date": [], "source_excel_row": [], "employee_and_action": [],
                },
                "legacy_technical_matches": [],
            })
            review_required = any(
                match["match_status"] != "AUTO_MATCH" for match in candidate["matches"]
            ) or bool(duplicate_result["legacy_technical_matches"])
            storage = {
                "reconstruction_pilot": PILOT,
                "reconstruction_status": "NEEDS_DOCX_REVIEW",
                "source_identifier": candidate["source_identifier"],
                "source_excel": {"file": str(SOURCE_FILE), "sheet": SHEET, "row": candidate["excel_row"]},
                "source_pdf": {"file": candidate["pdf"], "page": candidate["pdf_page"]},
                "source_title": candidate["source_title"], "source_figures": candidate["figures"],
                "employee_matches": [{
                    "source_name": match["source_name"],
                    "employee_id": match["employee_id"],
                    "match_status": match["match_status"],
                    "candidate_ids": match["candidate_ids"],
                } for match in candidate["matches"]],
                "employee_match_review_required": review_required,
                "reconstruction": {
                    "legacy_technical_order_ids": duplicate_result["legacy_technical_matches"],
                },
                "auto_filled_fields": auto_fields, "docx_found": bool(docx), "docx_path": docx,
                "basis_documents": [] if supplementary_pay else [{"basis_id": "application", "document_type": "EMPLOYEE_APPLICATION",
                                      "description": {"ru": "Личное заявление работника", "kk": "Қызметкердің жеке өтініші"}}],
            }
            order_id = None
            if not dry_run:
                order_id = active_conn.execute(text("""
                    INSERT INTO public.personnel_orders
                    (order_number, order_date, order_type_code, status, source_mode, basis_summary, storage_json, created_by)
                    VALUES (:number, :order_date, :action, 'DRAFT', 'PAPER', :basis, CAST(:storage AS jsonb), :creator)
                    RETURNING order_id
                """), {"number": candidate["order_number"], "order_date": candidate["order_date"], "action": candidate["action"],
                          "basis": None if supplementary_pay else "Личное заявление работника", "storage": json.dumps(storage, ensure_ascii=False), "creator": creator}).scalar_one()
                active_conn.execute(text("INSERT INTO public.personnel_order_evidence_scopes(order_id) VALUES (:order_id)"), {"order_id": order_id})
                for item_number, match in enumerate(candidate["matches"], start=1):
                    payload, assumptions = ({}, []) if supplementary_pay else assignment_payload(match["employee"])
                    payload.update({"source_employee_name": match["source_name"],
                                    "employee_match_status": match["match_status"],
                                    "employee_match_review_required": match["match_status"] != "AUTO_MATCH",
                                    "reconstruction_assumptions": assumptions})
                    active_conn.execute(text("""
                        INSERT INTO public.personnel_order_items
                        (order_id, item_number, item_type_code, employee_id, effective_date, payload, item_status)
                        VALUES (:order_id, :item_number, :action, :employee_id, :effective_date, CAST(:payload AS jsonb), 'ACTIVE')
                    """), {"order_id": order_id, "item_number": item_number, "action": candidate["action"],
                              "employee_id": match["employee_id"], "effective_date": None if supplementary_pay else candidate["order_date"],
                              "payload": json.dumps(payload, ensure_ascii=False)})
            report_rows.append({**candidate, "order_id": order_id, "docx_path": docx,
                                "template_key": template_key_for(candidate["action"]),
                                "employee_match_review_required": review_required,
                                "duplicate_checks": duplicate_result})
    return {"pilot": PILOT, "dry_run": dry_run, "orders": report_rows, "skipped": skipped,
            "duplicate_check": duplicates,
            "blocking_duplicates": [row for row in duplicates if has_blocking_duplicates(row)],
            "legacy_technical_matches": [row for row in duplicates if row["legacy_technical_matches"]]}


def write_outputs(result: dict[str, Any], *, write_repository_report: bool = True) -> None:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    (ARCHIVE / "run-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = ["# Personnel orders reconstruction pilot 01", "", "Local-only draft reconstruction. No employee events or assignments were created or changed.", "", f"Source: `{SOURCE_FILE}` · sheet `{SHEET}`.", "", "## Imported drafts", "", "| Excel row | Order | Date | template_key | order_id | DOCX | Visual check |", "|---:|---|---|---|---:|---|---|"]
    lines[0] = f"# Personnel orders reconstruction {PILOT}"
    for row in result["orders"]:
        oid = row["order_id"] or "dry-run"
        link = f"/directory/personnel/orders?order_id={oid}" if row["order_id"] else "—"
        lines.append(f"| {row['excel_row']} | {row['order_number']} | {row['order_date']} | {row.get('template_key') or 'absent'} | {oid} | {'found' if row['docx_path'] else 'not found'} | {link} |")
    absent_templates = [row["order_number"] for row in result["orders"] if not row.get("template_key")]
    lines += ["", "## Template resolution", "", "- No pilot order is without an approved template." if not absent_templates else f"- Approved template absent: {', '.join(absent_templates)}."]
    auto_matches = sum(1 for row in result["orders"] for match in row["matches"] if match["match_status"] == "AUTO_MATCH")
    ambiguous_matches = sum(1 for row in result["orders"] for match in row["matches"] if match["match_status"] == "AMBIGUOUS")
    unresolved_matches = sum(1 for row in result["orders"] for match in row["matches"] if match["match_status"] == "UNRESOLVED")
    lines += ["", "## Matching and assumptions", "", f"- Matched people: {auto_matches} automatic, {ambiguous_matches} ambiguous (their source FIO is retained without employee_id); no unresolved people were imported.", "- employee_id is written only for an unambiguous surname-and-initials match; ambiguous matches retain source FIO in the item payload.", "- The database has no historical assignment table. Current primary employee position/unit was copied when available and is marked `CURRENT_PRIMARY_ASSIGNMENT_USED_NO_HISTORICAL_ASSIGNMENT`.", "- Effective date defaults to order date; rate defaults to 1.0; basis defaults to the bilingual personal application.", "- The current default signatory is filled only when all signatory fields of a pilot draft are empty; the storage assumption is `CURRENT_DEFAULT_SIGNATORY_USED`.", "", "## Bilingual template corrections", "", "- Approved titles are selected by action type, including `О переводе` (not `О постоянном переводе`); see `personnel-order-titles-bilingual-dictionary.md`.", "- The general renderer maps `медсестра` and `медицинская сестра` to `мейіргер` before rendering Kazakh. Proposed pilot position/unit values are listed in the existing bilingual dictionaries.", "- Template limitations: the generic wording remains a reconstruction and must be checked against DOCX; no native imported text or editorial overrides are overwritten.", "", "## Skipped rows", ""]
    lines.append(f"- Unresolved figures retained for manual review: {unresolved_matches}; no employee_id or assignment is copied for them.")
    if result["skipped"]:
        for row in result["skipped"]:
            lines.append(f"- Excel row {row['excel_row']}: {row['reason']}.")
    else:
        lines.append("- None before the first 20 eligible records.")
    lines += ["", "## Russian automatic wording", "", "- When unused leave days are not confirmed, the accounting point is `Бухгалтерии произвести расчёт за неиспользованные дни отпуска.`; no dash, count, or `календарных дней` is rendered.", "- Russian automatic position/unit wording is `должность (подразделение)`. The added order-text form is `Приемное` → `приемное отделение` (PROPOSED); an unknown unit is only normalized to lower case and remains marked for dictionary review."]
    (ARCHIVE / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if write_repository_report:
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_bilingual_presentations(
    database_url: str,
    result: dict[str, Any],
    *,
    conn=None,
) -> dict[int, str | None]:
    """Use the existing editorial generators, then expose both draft locales.

    A caller-owned connection keeps batch reconstruction atomically coupled to
    its generated evidence/editorial records. The default remains compatible
    with ordinary callers that expect this function to own transactions.
    """
    from app.services.personnel_orders_editorial_service import generate_editorial
    from app.services.personnel_order_signatory_resolver import resolve_default_personnel_order_signatory

    approved = {
        "personnel.hire.standard",
        "personnel.transfer.permanent",
        "personnel.concurrent-duty.start",
        "personnel.termination.employee-initiative-unused-leave",
        "personnel.transfer.permanent-with-concurrent-duty",
        "personnel.supplementary-pay.review",
    }
    by_type = {
        "HIRE": "personnel.hire.standard",
        "TRANSFER": "personnel.transfer.permanent",
        "CONCURRENT_DUTY_START": "personnel.concurrent-duty.start",
        "TERMINATION": "personnel.termination.employee-initiative-unused-leave",
        "SUPPLEMENTARY_PAY": "personnel.supplementary-pay.review",
    }
    order_ids = [int(row["order_id"]) for row in result["orders"] if row.get("order_id")]
    pilot_signatory_roles = {
        int(row["order_id"]): signatory_role_from_docx(row.get("docx_path"))
        for row in result["orders"] if row.get("order_id")
    }
    selected: dict[int, str | None] = {}
    engine = None if conn is not None else create_engine(database_url)
    first_context = nullcontext(conn) if conn is not None else engine.begin()
    with first_context as active_conn:
        signatory = resolve_default_personnel_order_signatory(active_conn)
        if signatory.resolved:
            active_conn.execute(text("""
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
            active_conn.execute(text("""
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
        source_rows = active_conn.execute(text("""
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
                active_conn.execute(text("""
                    UPDATE public.personnel_orders
                    SET storage_json = storage_json || CAST(:template AS jsonb), updated_at = transaction_timestamp()
                    WHERE order_id = :order_id
                """), {"order_id": int(source["order_id"]), "template": json.dumps({
                    "template_key": key, "template_version": 1,
                    "template_versions": {"kk": 1, "ru": 1},
                    "template_resolution": "AUTO_BY_PERSONNEL_ORDER_ITEMS",
                })})
    for order_id in order_ids:
        generate_editorial(order_id, user_id=1, conn=conn)
    second_context = nullcontext(conn) if conn is not None else engine.begin()
    with second_context as active_conn:
        active_conn.execute(text("""
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


def apply_with_presentations(database_url: str, *, manifest_path: Path | None = None) -> dict[str, Any]:
    """Atomically create (or resume) a batch and all required presentations."""
    apply_engine = create_engine(database_url)
    with apply_engine.begin() as apply_conn:
        result = run(
            database_url,
            dry_run=False,
            manifest_path=manifest_path,
            conn=apply_conn,
        )
        if result.get("needs_presentation_repair", True):
            templates = ensure_bilingual_presentations(database_url, result, conn=apply_conn)
            for row in result["orders"]:
                row["template_key"] = templates.get(int(row["order_id"])) if row.get("order_id") else None
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source-file", type=Path, help="Portable Excel source path (defaults to the local research source)")
    parser.add_argument("--sheet", help="Excel sheet name")
    parser.add_argument("--docx-root", type=Path, help="Portable directory containing only source DOCX files")
    parser.add_argument("--archive", type=Path, help="Local output directory; never add it to Git")
    parser.add_argument("--manifest", type=Path, help="Pinned 20-row manifest to validate before processing")
    parser.add_argument("--pilot-key", help="Separate reconstruction pilot identifier")
    parser.add_argument("--strict-source-initials", action="store_true", help="Require source initials for automatic employee matching")
    parser.add_argument("--no-repository-report", action="store_true", help="Keep the report only in --archive")
    args = parser.parse_args()
    global PILOT, REQUIRE_SOURCE_INITIALS, SOURCE_FILE, SHEET, DOCX_ROOT, ARCHIVE
    if args.pilot_key:
        PILOT = args.pilot_key
    REQUIRE_SOURCE_INITIALS = args.strict_source_initials
    if args.source_file:
        SOURCE_FILE = args.source_file
    if args.sheet:
        SHEET = args.sheet
    if args.docx_root:
        DOCX_ROOT = args.docx_root
    if args.archive:
        ARCHIVE = args.archive
    docx_index.cache_clear()
    if not SOURCE_FILE.is_file():
        parser.error(f"Excel source file does not exist: {SOURCE_FILE}")
    if not DOCX_ROOT.is_dir():
        parser.error(f"DOCX root does not exist: {DOCX_ROOT}")
    if args.manifest:
        verify_manifest_files(args.manifest, SOURCE_FILE)
    if args.dry_run:
        result = run(args.database_url, dry_run=True, manifest_path=args.manifest)
    else:
        result = apply_with_presentations(args.database_url, manifest_path=args.manifest)
    write_outputs(result, write_repository_report=not args.dry_run and not args.no_repository_report)
    print(json.dumps({"orders": len(result["orders"]), "skipped": len(result["skipped"]), "dry_run": args.dry_run}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
