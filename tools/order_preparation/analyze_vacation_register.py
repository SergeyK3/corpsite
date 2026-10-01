#!/usr/bin/env python
"""Read-only structural report for the vacation-register analysis workbook."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


def value_kind(value: Any) -> str:
    if value is None: return "empty"
    if isinstance(value, bool): return "boolean"
    if isinstance(value, (datetime, date)): return "date"
    if isinstance(value, (int, float)): return "number"
    if isinstance(value, str) and value.startswith("="): return "formula"
    return "text"


def text(value: Any) -> str:
    return " ".join(str(value or "").split())


def sheet_report(sheet) -> dict[str, Any]:
    rows = list(sheet.iter_rows(values_only=False))
    nonempty = [(row_number, row) for row_number, row in enumerate(rows, start=1) if any(cell.value is not None for cell in row)]
    # These workbooks may have title and instruction rows before the table.
    # Header cells are formatted bold; use that signal, then non-empty width.
    candidates = nonempty[: min(len(nonempty), 8)]
    header_index = max(
        range(len(candidates)),
        key=lambda index: (
            sum(bool(cell.font and cell.font.bold) for cell in candidates[index][1]),
            sum(cell.value is not None for cell in candidates[index][1]),
            index,
        ),
    ) if candidates else 0
    header_row = nonempty[header_index][0] if nonempty else None
    headers = [text(cell.value) for cell in nonempty[header_index][1]] if nonempty else []
    data = nonempty[header_index + 1:] if len(nonempty) > header_index + 1 else []
    kind_by_col: dict[str, Counter[str]] = {}
    blank_by_col: dict[str, int] = {}
    for index, header in enumerate(headers):
        label = header or f"column_{index + 1}"
        values = [row[index].value if index < len(row) else None for _, row in data]
        kind_by_col[label] = Counter(value_kind(value) for value in values)
        blank_by_col[label] = sum(value is None or text(value) == "" for value in values)
    return {
        "title": sheet.title, "max_row": sheet.max_row, "max_column": sheet.max_column,
        "first_nonempty_row": header_row, "data_rows": len(data), "headers": headers,
        "types": {key: dict(value) for key, value in kind_by_col.items()}, "blank_values": blank_by_col,
    }


def vacation_summary(workbook) -> dict[str, Any]:
    """Workbook-specific aggregate facts; intentionally excludes names/text."""
    output: dict[str, Any] = {"exception_sheets": {}}
    for title in ("Нет реквизитов", "Ошибки периодов", "Строка перевода"):
        if title not in workbook.sheetnames: continue
        sheet = workbook[title]
        headers = [text(cell.value) for cell in sheet[4]]
        rows = list(sheet.iter_rows(min_row=5, values_only=True))
        rows = [row for row in rows if any(value is not None for value in row)]
        index = {header: pos for pos, header in enumerate(headers)}
        def values(header: str) -> list[Any]: return [row[index[header]] for row in rows] if header in index else []
        reviewed = Counter(text(value) for value in values("Проверено кадровиком"))
        blocks = values("№ блока"); events = values("№ события")
        source_files = values("Исходный файл")
        output["exception_sheets"][title] = {
            "rows": len(rows), "reviewed": dict(reviewed),
            "unique_blocks": len({value for value in blocks if value is not None}),
            "unique_block_event_pairs": len({(blocks[pos], events[pos]) for pos in range(min(len(blocks), len(events)))}),
            "unique_source_files": len({text(value) for value in source_files if text(value)}),
            "missing_original_order_numbers": sum(not text(value) for value in values("Исходный № приказа") or values("№ приказа")),
            "missing_original_order_dates": sum(not text(value) for value in values("Исходная дата приказа") or values("Дата приказа")),
        }
    if "Классификация" in workbook.sheetnames:
        sheet = workbook["Классификация"]
        headers = [text(cell.value) for cell in sheet[4]]; index = {header: pos for pos, header in enumerate(headers)}
        rows = [row for row in sheet.iter_rows(min_row=5, values_only=True) if any(value is not None for value in row)]
        output["classification"] = [{
            "category_code": text(row[index.get("Код категории", -1)]) if index.get("Код категории") is not None else "",
            "subclass_code": text(row[index.get("Код подкласса", -1)]) if index.get("Код подкласса") is not None else "",
            "count": row[index.get("Количество строк", -1)] if index.get("Количество строк") is not None else None,
        } for row in rows]
        output["classification_total"] = sum(int(item["count"] or 0) for item in output["classification"])
    return output


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("workbook", type=Path); parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    workbook = load_workbook(args.workbook, read_only=False, data_only=False)
    report = {"sheets": [sheet_report(sheet) for sheet in workbook.worksheets], "vacation_summary": vacation_summary(workbook)}
    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.output: args.output.write_text(payload, encoding="utf-8")
    else: print(payload)
    return 0


if __name__ == "__main__": raise SystemExit(main())
