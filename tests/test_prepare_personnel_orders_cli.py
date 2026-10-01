from __future__ import annotations

import hashlib
from pathlib import Path

from docx import Document
from pypdf import PdfWriter

from tools.order_preparation.prepare_personnel_orders import (
    action_type, extract_requisites, normalize_date, scan,
)


def test_requisites_normalization_preserves_number_suffix() -> None:
    raw, number, raw_date, value, confidence, status = extract_requisites("Приказ № 17-К/а от 01.02.2026")
    assert raw == "Приказ № 17-К/а"
    assert number == "17-К/а"
    assert raw_date == "01.02.2026"
    assert value == "2026-02-01"
    assert confidence >= 0.95 and status == "READY"
    assert normalize_date("2026-02-01") == "2026-02-01"
    assert action_type("Прием на работу") == "HIRE"


def test_scan_reads_synthetic_docx_without_changing_source(tmp_path: Path) -> None:
    source = tmp_path / "word"; source.mkdir()
    document = Document(); document.add_paragraph("Приказ № 1-К от 01.01.2026"); document.save(source / "order.docx")
    before = hashlib.sha256((source / "order.docx").read_bytes()).hexdigest()
    records = scan(source, "word", ocr=False, ocr_lang="rus")
    assert len(records) == 1
    assert "1-К" in records[0].text
    assert hashlib.sha256((source / "order.docx").read_bytes()).hexdigest() == before


def test_scan_reports_blank_synthetic_pdf_as_scan_when_ocr_disabled(tmp_path: Path) -> None:
    source = tmp_path / "pdf"; source.mkdir()
    writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
    with (source / "scan.pdf").open("wb") as target: writer.write(target)
    records = scan(source, "pdf", ocr=False, ocr_lang="rus")
    assert len(records) == 1
    assert records[0].page_count == 1
    assert records[0].used_ocr is False
