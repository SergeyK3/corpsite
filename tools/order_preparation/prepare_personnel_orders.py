#!/usr/bin/env python
"""Offline preparation of personnel-order evidence for Corpsite.

This program never opens a database and never changes source documents.  It
creates a review workbook; a human must fill/confirm employee_id from the
Corpsite reference export before its rows can be imported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from docx import Document
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from pypdf import PdfReader

SCHEMA_VERSION = "PERSONNEL_ORDERS_XLSX_V1"
TOOL_VERSION = "1.0.0"
SAFE_PREFIXES = ("=", "+", "-", "@")
ORDER_NUMBER_RE = re.compile(r"(?:приказ\s*(?:№|N|No\.?|#)?\s*|№\s*)([A-Za-zА-Яа-яЁё0-9]+(?:[\-/][A-Za-zА-Яа-яЁё0-9]+)*)", re.I)
DATE_RE = re.compile(r"\b(\d{1,2}[.]\d{1,2}[.]\d{4}|\d{4}-\d{2}-\d{2})\b")
# Candidate only: it is deliberately never an automatic employee binding.
NAME_RE = re.compile(r"\b[А-ЯӘҒҚҢӨҰҮҺІЁ][а-яәғқңөұүһіё-]+\s+[А-ЯӘҒҚҢӨҰҮҺІЁ][а-яәғқңөұүһіё-]+(?:\s+[А-ЯӘҒҚҢӨҰҮҺІЁ][а-яәғқңөұүһіё-]+)?\b")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def safe_cell(value: object) -> str:
    text = str(value or "")
    return "'" + text if text.startswith(SAFE_PREFIXES) else text


def normal_name(value: str) -> str:
    return clean(value).casefold().replace("ё", "е")


def relative(root: Path, file: Path) -> str:
    # Always a portable, non-absolute provenance reference.
    return file.relative_to(root).as_posix()


def normalize_date(raw: str) -> str | None:
    raw = clean(raw)
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def extract_requisites(text: str) -> tuple[str, str, str, str, float, str]:
    number = ORDER_NUMBER_RE.search(text)
    date_match = DATE_RE.search(text)
    number_raw = clean(number.group(0)) if number else ""
    order_number = clean(number.group(1)) if number else ""
    date_raw = clean(date_match.group(1)) if date_match else ""
    order_date = normalize_date(date_raw) or ""
    confidence = 0.98 if number and order_date else (0.70 if number or date_match else 0.0)
    status = "READY" if confidence >= 0.95 else "REVIEW_REQUIRED"
    return number_raw, order_number, date_raw, order_date, confidence, status


def action_type(text: str) -> str:
    low = text.casefold()
    if "уволь" in low or "босат" in low: return "TERMINATION"
    if "перевод" in low or "ауыстыр" in low: return "TRANSFER"
    if "прием" in low or "қабыл" in low: return "HIRE"
    if "совмест" in low: return "CONCURRENT_DUTY"
    return "UNCLASSIFIED"


def extract_docx(path: Path) -> str:
    document = Document(path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            paragraphs.extend(cell.text for cell in row.cells)
    return "\n".join(part for part in paragraphs if part)


def _configure_tesseract(command: str | None, language: str) -> str | None:
    """Locate a local binary; never download or call a network OCR service."""
    candidate = command or os.getenv("TESSERACT_CMD") or shutil.which("tesseract")
    if not candidate:
        default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        candidate = str(default) if default.is_file() else None
    if not candidate or not Path(candidate).is_file(): return None
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = candidate
    try:
        available = set(pytesseract.get_languages(config=f'--tessdata-dir "{Path(candidate).parent / "tessdata"}"'))
    except Exception:
        return None
    return candidate if set(language.split("+")).issubset(available) else None


def extract_pdf(path: Path, *, ocr: bool, ocr_lang: str, tesseract_cmd: str | None) -> tuple[str, int, bool, list[str]]:
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    pages = len(reader.pages)
    warnings: list[str] = []
    if clean(text) or not ocr:
        return text, pages, False, warnings
    try:
        import fitz  # PyMuPDF
        import pytesseract
        from PIL import Image
    except ImportError:
        return "", pages, False, ["OCR_DEPENDENCY_MISSING"]
    if _configure_tesseract(tesseract_cmd, ocr_lang) is None:
        return "", pages, False, ["OCR_ENGINE_OR_LANGUAGE_MISSING"]
    try:
        document = fitz.open(path)
        pieces: list[str] = []
        for page in document:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            pieces.append(pytesseract.image_to_string(image, lang=ocr_lang))
        return "\n".join(pieces), pages, True, warnings
    except Exception:
        return "", pages, False, ["OCR_FAILED_REVIEW_REQUIRED"]


@dataclass(frozen=True)
class SourceFile:
    kind: str
    root: str
    relative_path: str
    sha256: str
    byte_size: int
    page_count: int = 0
    used_ocr: bool = False
    text: str = ""
    warnings: tuple[str, ...] = ()


def scan(root: Path, kind: str, *, ocr: bool, ocr_lang: str, tesseract_cmd: str | None = None) -> list[SourceFile]:
    suffixes = {".pdf"} if kind == "pdf" else {".docx"}
    result: list[SourceFile] = []
    for file in sorted(item for item in root.rglob("*") if item.is_file() and item.suffix.lower() in suffixes):
        try:
            if kind == "pdf":
                content, pages, used_ocr, warnings = extract_pdf(file, ocr=ocr, ocr_lang=ocr_lang, tesseract_cmd=tesseract_cmd)
            else:
                content, pages, used_ocr, warnings = extract_docx(file), 0, False, []
            result.append(SourceFile(kind, str(root), relative(root, file), sha256(file), file.stat().st_size, pages, used_ocr, content, tuple(warnings)))
        except Exception:
            result.append(SourceFile(kind, str(root), relative(root, file), sha256(file), file.stat().st_size, 0, False, "", ("SOURCE_READ_FAILED",)))
    return result


def reference_people(path: Path | None) -> dict[str, tuple[int, str]]:
    if path is None: return {}
    workbook = load_workbook(path, read_only=True, data_only=False)
    if "Employees" not in workbook.sheetnames: raise ValueError("Reference workbook has no Employees sheet.")
    rows = workbook["Employees"].iter_rows(min_row=2, values_only=True)
    result = {}
    for row in rows:
        try:
            employee_id, name = int(row[1]), clean(row[3])
        except (IndexError, TypeError, ValueError):
            continue
        if name and normal_name(name) not in result: result[normal_name(name)] = (employee_id, name)
    return result


def pair(pdf: list[SourceFile], word: list[SourceFile]) -> tuple[dict[str, SourceFile], list[dict[str, str]]]:
    """Pair only by independent normalized number *and* date evidence.

    Filename stems are retained as provenance only: they are never a proof that
    a scan and a Word draft describe the same official order.
    """
    word_index: dict[tuple[str, str], list[SourceFile]] = {}
    for item in word:
        _, number, _, order_date, _, _ = extract_requisites(item.text)
        if number and order_date:
            word_index.setdefault((number.casefold(), order_date), []).append(item)
    pairs: dict[str, SourceFile] = {}; conflicts: list[dict[str, str]] = []
    for item in pdf:
        _, number, _, order_date, _, _ = extract_requisites(item.text)
        candidates = word_index.get((number.casefold(), order_date), []) if number and order_date else []
        if len(candidates) == 1: pairs[item.sha256] = candidates[0]
        elif len(candidates) > 1: conflicts.append({"kind": "PDF_WORD_AMBIGUOUS_REQUISITES", "source": item.relative_path})
    return pairs, conflicts


def make_rows(pdf_files: list[SourceFile], word_files: list[SourceFile], people: dict[str, tuple[int, str]]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    word_by_stem, conflicts = pair(pdf_files, word_files)
    rows: list[dict[str, object]] = []
    unmatched: list[dict[str, object]] = []
    for pdf in pdf_files:
        word = word_by_stem.get(pdf.sha256)
        evidence = "\n".join(value for value in (pdf.text, word.text if word else "") if value)
        raw_no, no, raw_date, date, confidence, recognition = extract_requisites(evidence)
        names = sorted({clean(value) for value in NAME_RE.findall(word.text if word else evidence)})
        if not names: names = [""]
        for index, candidate in enumerate(names, start=1):
            found = people.get(normal_name(candidate))
            review = "PENDING" if found and recognition == "READY" else "REVIEW_REQUIRED"
            method = "EXACT_REFERENCE_NAME_CANDIDATE" if found else "NO_AUTOMATIC_MATCH"
            rows.append({
                "schema_version": SCHEMA_VERSION, "source_row_id": f"{pdf.sha256[:16]}-{index}",
                "employee_id": found[0] if found else "", "employee_full_name": found[1] if found else candidate,
                "order_number_raw": raw_no, "order_number": no, "order_date_raw": raw_date, "order_date": date,
                "order_kind": "PERSONNEL", "action_type": action_type(evidence), "pdf_source": pdf.relative_path,
                "pdf_sha256": pdf.sha256, "word_source": word.relative_path if word else "", "word_sha256": word.sha256 if word else "",
                "source_text": clean(evidence)[:10000], "recognition_confidence": confidence, "recognition_status": recognition,
                "matching_method": method, "review_status": review,
                "note": "" if review == "PENDING" else "Manual review required; no fuzzy employee binding.",
            })
            if not found: unmatched.append({"pdf_source": pdf.relative_path, "candidate_name": candidate, "reason": "NO_EXACT_REFERENCE_MATCH"})
        if word:
            word_req = extract_requisites(word.text)
            if (no and word_req[1] and no != word_req[1]) or (date and word_req[3] and date != word_req[3]):
                conflicts.append({"kind": "PDF_WORD_REQUISITE_CONFLICT", "source": pdf.relative_path, "word_source": word.relative_path})
    return rows, unmatched, conflicts


def write_workbook(path: Path, *, rows: list[dict[str, object]], unmatched: list[dict[str, object]], conflicts: list[dict[str, object]], sources: list[SourceFile], diagnostics: list[dict[str, object]]) -> None:
    workbook = Workbook(); orders = workbook.active; orders.title = "Orders"
    headers = ["schema_version", "source_row_id", "employee_id", "employee_full_name", "order_number_raw", "order_number", "order_date_raw", "order_date", "order_kind", "action_type", "pdf_source", "pdf_sha256", "word_source", "word_sha256", "source_text", "recognition_confidence", "recognition_status", "matching_method", "review_status", "note"]
    orders.append(headers)
    for row in rows: orders.append([safe_cell(row.get(key, "")) for key in headers])
    for title, records in (("UnmatchedEmployees", unmatched), ("AmbiguousMatches", []), ("DocumentConflicts", conflicts), ("Diagnostics", diagnostics)):
        sheet = workbook.create_sheet(title)
        keys = sorted({key for record in records for key in record}) or ["status"]
        sheet.append(keys)
        for record in records: sheet.append([safe_cell(record.get(key, "")) for key in keys])
    metadata = workbook.create_sheet("Metadata")
    metadata.append(["schema_version", SCHEMA_VERSION]); metadata.append(["tool_version", TOOL_VERSION]); metadata.append(["generated_at", datetime.now().astimezone().isoformat()]); metadata.append(["order_rows", len(rows)]); metadata.append(["source_files", len(sources)])
    manifest = workbook.create_sheet("SourceManifest")
    manifest.append(["kind", "relative_path", "sha256", "byte_size", "page_count", "used_ocr", "warnings"])
    for source in sources: manifest.append([source.kind, source.relative_path, source.sha256, source.byte_size, source.page_count, source.used_ocr, ";".join(source.warnings)])
    for sheet in workbook.worksheets:
        for index, column in enumerate(sheet.columns, start=1): sheet.column_dimensions[get_column_letter(index)].width = min(60, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
    path.parent.mkdir(parents=True, exist_ok=True); workbook.save(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-root", type=Path, required=True); parser.add_argument("--word-root", type=Path, required=True)
    parser.add_argument("--employee-reference", type=Path); parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics-json", type=Path); parser.add_argument("--ocr", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--ocr-lang", default="rus+eng"); parser.add_argument("--tesseract-cmd", type=str)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.pdf_root.is_dir() or not args.word_root.is_dir(): parser.error("Source roots must be existing directories.")
    if args.output.resolve().is_relative_to(args.pdf_root.resolve()) or args.output.resolve().is_relative_to(args.word_root.resolve()): parser.error("Output must not be inside a source directory.")
    sources = scan(args.pdf_root, "pdf", ocr=args.ocr, ocr_lang=args.ocr_lang, tesseract_cmd=args.tesseract_cmd) + scan(args.word_root, "word", ocr=False, ocr_lang=args.ocr_lang, tesseract_cmd=args.tesseract_cmd)
    diagnostics = [{"source": source.relative_path, "kind": source.kind, "warning": warning} for source in sources for warning in source.warnings]
    rows, unmatched, conflicts = make_rows([source for source in sources if source.kind == "pdf"], [source for source in sources if source.kind == "word"], reference_people(args.employee_reference))
    report = {"tool_version": TOOL_VERSION, "schema_version": SCHEMA_VERSION, "sources": len(sources), "pdf_sources": sum(source.kind == "pdf" for source in sources), "word_sources": sum(source.kind == "word" for source in sources), "pdf_pages": sum(source.page_count for source in sources if source.kind == "pdf"), "pdf_with_text": sum(source.kind == "pdf" and bool(clean(source.text)) and not source.used_ocr for source in sources), "pdf_ocr_used": sum(source.kind == "pdf" and source.used_ocr for source in sources), "rows": len(rows), "unmatched": len(unmatched), "conflicts": len(conflicts), "diagnostics": len(diagnostics)}
    if not args.dry_run: write_workbook(args.output, rows=rows, unmatched=unmatched, conflicts=conflicts, sources=sources, diagnostics=diagnostics)
    if args.diagnostics_json: args.diagnostics_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
