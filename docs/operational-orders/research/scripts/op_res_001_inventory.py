#!/usr/bin/env python3
"""
OP-RES-001 — read-only corpus inventory for production orders.
Scans source folder metadata and lightweight format probes only.
Does not modify, move, or copy source documents.
"""

from __future__ import annotations

import csv
import hashlib
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    import olefile
except ImportError:  # pragma: no cover
    olefile = None  # type: ignore

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore

# --- configuration ---------------------------------------------------------

SOURCE_ROOT = Path(
    r"d:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\Производственные приказы"
)
OUTPUT_CSV = Path(__file__).resolve().parents[1] / "data" / "OP-RES-001-corpus-inventory.csv"

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

KAZAKH_SPECIFIC = set("әғқңөүһіӘҒҚҢӨҮҺІ")
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
LATIN_RE = re.compile(r"[A-Za-z]")
YEAR_RE = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
VERSION_COPY_RE = re.compile(
    r"(копия|copy|версия|version|дубликат|duplicate|исправ|rev\d|v\d+|\(\d+\)|~\$)",
    re.IGNORECASE,
)
TEMP_LOCK_PREFIX = "~$"

COPY_MARKERS = (
    "копия",
    "copy",
    "версия",
    "version",
    "дубликат",
    "duplicate",
    "исправ",
    " backup",
    "бэкап",
)


@dataclass
class DocxProbe:
    ooxml_valid: bool
    has_document_xml: bool
    paragraph_count: int
    text_char_count: int
    has_tables: bool
    has_images: bool
    has_embedded_objects: bool
    encrypted_or_corrupt: bool
    notes: list[str]


@dataclass
class DocProbe:
    is_ole: bool
    has_word_document_stream: bool
    stream_names: list[str]
    safe_extraction_method: str
    notes: list[str]


@dataclass
class PdfProbe:
    page_count: int
    has_extractable_text: bool
    likely_scanned: bool
    encrypted: bool
    notes: list[str]


def normalize_stem(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = VERSION_COPY_RE.sub("", stem)
    stem = re.sub(r"[_\-\s]+", " ", stem).strip()
    return stem


def infer_year(filename: str) -> str:
    matches = YEAR_RE.findall(filename)
    if not matches:
        return ""
    # Prefer the latest plausible document year when multiple appear.
    years = [int(y) for y in matches]
    return str(max(years))


def infer_language(filename: str) -> str:
    text = Path(filename).stem
    has_cyrillic = bool(CYRILLIC_RE.search(text))
    has_latin = bool(LATIN_RE.search(text))
    has_kk_chars = any(ch in KAZAKH_SPECIFIC for ch in text)

    kk_words = (
        "аударым",
        "ауыстыру",
        "бұйрық",
        "буйрық",
        "буйрик",
        "қаз",
        "өтініш",
        "өтініш",
        "міндет",
    )
    ru_words = (
        "приказ",
        "распоряжение",
        "постановление",
        "командиров",
        "премия",
        "наказан",
        "отпуск",
        "служеб",
    )
    lower = text.lower()
    has_kk_words = any(w in lower for w in kk_words)
    has_ru_words = any(w in lower for w in ru_words)

    if not has_cyrillic and not has_latin:
        return "unknown"
    if has_kk_chars or has_kk_words:
        if has_ru_words or (has_cyrillic and not has_kk_chars):
            return "mixed"
        return "kk"
    if has_cyrillic:
        return "ru"
    return "unknown"


def infer_thematic_source(rel_path: str) -> str:
    parts = Path(rel_path).parts
    if len(parts) <= 1:
        return "root"
    return parts[0]


def is_version_or_copy(filename: str) -> str:
    lower = filename.lower()
    if lower.startswith(TEMP_LOCK_PREFIX):
        return "temp_lock"
    for marker in COPY_MARKERS:
        if marker in lower:
            return "yes"
    if VERSION_COPY_RE.search(filename):
        return "yes"
    return "no"


def probe_docx(path: Path) -> DocxProbe:
    notes: list[str] = []
    encrypted_or_corrupt = False
    has_document_xml = False
    paragraph_count = 0
    text_char_count = 0
    has_tables = False
    has_images = False
    has_embedded_objects = False
    ooxml_valid = False

    try:
        with zipfile.ZipFile(path) as zf:
            ooxml_valid = True
            names = set(zf.namelist())
            has_document_xml = "word/document.xml" in names
            if "word/media/" in "".join(names):
                has_images = any(n.startswith("word/media/") for n in names)
            if "word/embeddings/" in "".join(names):
                has_embedded_objects = any(
                    n.startswith("word/embeddings/") for n in names
                )

            if has_document_xml:
                raw = zf.read("word/document.xml")
                root = ET.fromstring(raw)
                paragraphs = root.findall(f".//{W_NS}p")
                paragraph_count = len(paragraphs)
                texts = [t.text or "" for t in root.findall(f".//{W_NS}t")]
                text_char_count = sum(len(t) for t in texts)
                has_tables = root.find(f".//{W_NS}tbl") is not None
            else:
                notes.append("missing word/document.xml")
    except zipfile.BadZipFile:
        encrypted_or_corrupt = True
        notes.append("not a valid ZIP/OOXML container")
    except ET.ParseError:
        encrypted_or_corrupt = True
        notes.append("document.xml parse error")
    except Exception as exc:  # noqa: BLE001 - research probe
        encrypted_or_corrupt = True
        notes.append(f"probe error: {type(exc).__name__}")

    return DocxProbe(
        ooxml_valid=ooxml_valid,
        has_document_xml=has_document_xml,
        paragraph_count=paragraph_count,
        text_char_count=text_char_count,
        has_tables=has_tables,
        has_images=has_images,
        has_embedded_objects=has_embedded_objects,
        encrypted_or_corrupt=encrypted_or_corrupt,
        notes=notes,
    )


def probe_doc(path: Path) -> DocProbe:
    notes: list[str] = []
    is_ole = False
    has_word_document_stream = False
    stream_names: list[str] = []

    header = path.read_bytes()[:8]
    if header == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        is_ole = True
    else:
        notes.append("missing OLE magic header")

    if olefile is not None:
        try:
            with olefile.OleFileIO(str(path)) as ole:
                stream_names = ["/".join(entry) for entry in ole.listdir()]
                has_word_document_stream = any(
                    s.lower() in {"worddocument", "word/document", "1table", "0table"}
                    or s.lower().endswith("worddocument")
                    for s in stream_names
                )
        except Exception as exc:  # noqa: BLE001
            notes.append(f"olefile probe error: {type(exc).__name__}")
    else:
        notes.append("olefile not installed")

    if has_word_document_stream:
        method = "olefile_stream_probe; text extraction via LibreOffice --headless or antiword (read-only copy to temp)"
    elif is_ole:
        method = "legacy OLE; verify streams manually; LibreOffice --headless recommended"
    else:
        method = "unknown binary; manual inspection required"

    return DocProbe(
        is_ole=is_ole,
        has_word_document_stream=has_word_document_stream,
        stream_names=stream_names,
        safe_extraction_method=method,
        notes=notes,
    )


def probe_pdf(path: Path) -> PdfProbe:
    notes: list[str] = []
    page_count = 0
    has_extractable_text = False
    likely_scanned = False
    encrypted = False

    if PdfReader is None:
        notes.append("pypdf not installed")
        return PdfProbe(0, False, False, False, notes)

    try:
        reader = PdfReader(str(path))
        encrypted = bool(getattr(reader, "is_encrypted", False))
        if encrypted:
            notes.append("encrypted PDF")
            return PdfProbe(0, False, False, True, notes)

        page_count = len(reader.pages)
        extracted_chars = 0
        for page in reader.pages[: min(3, page_count)]:
            text = page.extract_text() or ""
            extracted_chars += len(text.strip())
        has_extractable_text = extracted_chars >= 30
        likely_scanned = page_count > 0 and not has_extractable_text
        if likely_scanned:
            notes.append("no extractable text in first pages; likely scan/image PDF")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"pdf probe error: {type(exc).__name__}")

    return PdfProbe(
        page_count=page_count,
        has_extractable_text=has_extractable_text,
        likely_scanned=likely_scanned,
        encrypted=encrypted,
        notes=notes,
    )


def text_extraction_suitability(ext: str, docx: DocxProbe | None, doc: DocProbe | None, pdf: PdfProbe | None) -> str:
    ext = ext.lower()
    if ext == ".docx":
        assert docx is not None
        if docx.encrypted_or_corrupt:
            return "poor"
        if docx.text_char_count >= 100:
            return "good"
        if docx.text_char_count > 0:
            return "fair"
        return "poor"
    if ext == ".doc":
        assert doc is not None
        if doc.has_word_document_stream:
            return "fair"
        if doc.is_ole:
            return "fair"
        return "poor"
    if ext == ".pdf":
        assert pdf is not None
        if pdf.encrypted:
            return "poor"
        if pdf.has_extractable_text:
            return "good"
        if pdf.likely_scanned:
            return "poor_ocr_needed"
        return "unknown"
    if ext in {".xls", ".xlsx"}:
        return "fair"
    if ext in {".txt", ".rtf"}:
        return "good"
    return "unknown"


def technical_notes(
    ext: str,
    docx: DocxProbe | None,
    doc: DocProbe | None,
    pdf: PdfProbe | None,
) -> str:
    parts: list[str] = []
    if ext == ".docx" and docx is not None:
        parts.append(
            f"ooxml_valid={docx.ooxml_valid}; paragraphs={docx.paragraph_count}; "
            f"text_chars={docx.text_char_count}; tables={docx.has_tables}; "
            f"images={docx.has_images}; embeddings={docx.has_embedded_objects}"
        )
        parts.extend(docx.notes)
    elif ext == ".doc" and doc is not None:
        parts.append(
            f"ole={doc.is_ole}; word_stream={doc.has_word_document_stream}; "
            f"method={doc.safe_extraction_method}"
        )
        if doc.stream_names:
            parts.append("streams=" + ",".join(doc.stream_names[:8]))
        parts.extend(doc.notes)
    elif ext == ".pdf" and pdf is not None:
        parts.append(
            f"pages={pdf.page_count}; extractable_text={pdf.has_extractable_text}; "
            f"likely_scanned={pdf.likely_scanned}; encrypted={pdf.encrypted}"
        )
        parts.extend(pdf.notes)
    return "; ".join(p for p in parts if p)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append(path)
    return files


def build_duplicate_flags(files: Iterable[Path], root: Path) -> dict[Path, str]:
    by_name: dict[str, list[Path]] = defaultdict(list)
    by_size: dict[int, list[Path]] = defaultdict(list)
    by_norm: dict[str, list[Path]] = defaultdict(list)
    by_hash: dict[str, list[Path]] = defaultdict(list)

    hashes: dict[Path, str] = {}
    for path in files:
        rel = path.relative_to(root)
        by_name[path.name.lower()].append(path)
        size = path.stat().st_size
        by_size[size].append(path)
        by_norm[normalize_stem(path.name)].append(path)
        digest = sha256_file(path)
        hashes[path] = digest
        by_hash[digest].append(path)

    flags: dict[Path, str] = {}
    for path in files:
        reasons: list[str] = []
        if len(by_name[path.name.lower()]) > 1:
            reasons.append("same_filename")
        norm = normalize_stem(path.name)
        if len(by_norm[norm]) > 1:
            reasons.append("same_normalized_stem")
        size = path.stat().st_size
        if len(by_size[size]) > 1:
            reasons.append("same_size")
        digest = hashes[path]
        if len(by_hash[digest]) > 1:
            reasons.append("identical_content_hash")
        flags[path] = "|".join(reasons) if reasons else "no"
    return flags


def inventory_row(path: Path, root: Path, duplicate_flag: str) -> dict[str, str]:
    rel = path.relative_to(root).as_posix()
    stat = path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    ext = path.suffix.lower()
    filename = path.name
    parent = path.parent.relative_to(root).as_posix() if path.parent != root else "."

    docx_probe: DocxProbe | None = None
    doc_probe: DocProbe | None = None
    pdf_probe: PdfProbe | None = None

    if ext == ".docx":
        docx_probe = probe_docx(path)
    elif ext == ".doc":
        doc_probe = probe_doc(path)
    elif ext == ".pdf":
        pdf_probe = probe_pdf(path)

    return {
        "relative_path": rel,
        "filename": filename,
        "parent_folder": parent,
        "extension": ext,
        "size_bytes": str(stat.st_size),
        "modified_utc": modified,
        "presumed_year": infer_year(filename),
        "presumed_language": infer_language(filename),
        "thematic_source_folder": infer_thematic_source(rel),
        "possible_duplicate": duplicate_flag,
        "version_or_copy": is_version_or_copy(filename),
        "text_extraction_suitability": text_extraction_suitability(
            ext, docx_probe, doc_probe, pdf_probe
        ),
        "technical_notes": technical_notes(ext, docx_probe, doc_probe, pdf_probe),
    }


FIELDNAMES = [
    "relative_path",
    "filename",
    "parent_folder",
    "extension",
    "size_bytes",
    "modified_utc",
    "presumed_year",
    "presumed_language",
    "thematic_source_folder",
    "possible_duplicate",
    "version_or_copy",
    "text_extraction_suitability",
    "technical_notes",
]


def main() -> int:
    if not SOURCE_ROOT.is_dir():
        print(f"Source folder not found: {SOURCE_ROOT}", file=sys.stderr)
        return 1

    files = collect_files(SOURCE_ROOT)
    duplicate_flags = build_duplicate_flags(files, SOURCE_ROOT)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        for path in files:
            writer.writerow(inventory_row(path, SOURCE_ROOT, duplicate_flags[path]))

    print(f"Scanned {len(files)} files")
    print(f"Wrote {OUTPUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
