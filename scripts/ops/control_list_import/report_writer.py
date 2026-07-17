"""JSON and Markdown report writers for workbook profile."""
from __future__ import annotations

from pathlib import Path
from typing import Any

_EMPLOYMENT_MODE_RU = {
    "primary": "основные",
    "concurrent": "совместители",
    "unknown": "неизвестно",
}

_PERSONNEL_CATEGORY_RU = {
    "doctor": "врачи",
    "nursing_staff": "средний медперсонал",
    "junior_medical_staff": "младший медперсонал",
    "other_staff": "прочий персонал",
    "unknown": "неизвестно",
}

_SHEET_PURPOSE_RU = {
    "personnel_control_list": "кадровый контрольный список",
    "declaration": "декларация",
    "unknown": "неизвестно",
}


def write_json_report(path: Path, report: dict[str, Any]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _classification_labels(sheet: dict[str, Any]) -> tuple[str, str, str, str]:
    cls = sheet.get("classification") or {}
    cat = _PERSONNEL_CATEGORY_RU.get(cls.get("proposed_personnel_category", "unknown"), "неизвестно")
    mode = _EMPLOYMENT_MODE_RU.get(cls.get("proposed_employment_mode", "unknown"), "неизвестно")
    purpose = _SHEET_PURPOSE_RU.get(cls.get("proposed_sheet_purpose", "unknown"), "неизвестно")
    conf = str(cls.get("classification_confidence", "—"))
    return cat, mode, purpose, conf


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    source = report.get("source", {})
    summary = report.get("summary", {})
    workbook = report.get("workbook", {})
    config = report.get("configuration", {})

    lines.append("# Control List Workbook Profile")
    lines.append("")
    lines.append("## 1. Резюме")
    lines.append("")
    lines.append(f"- **Файл:** `{source.get('filename', '')}`")
    lines.append(f"- **Размер:** {source.get('size_bytes', 0)} bytes")
    lines.append(f"- **Проанализировано листов:** {workbook.get('analyzed_sheet_count', 0)}")
    lines.append(f"- **Исключено листов:** {workbook.get('excluded_sheet_count', 0)}")
    lines.append(f"- **Probable person rows:** {summary.get('probable_person_rows', 0)}")
    lines.append(f"- **Составные ячейки:** {summary.get('composite_cell_count', 0)}")
    lines.append("")

    lines.append("## 2. SHA-256")
    lines.append("")
    lines.append(f"- **До анализа:** `{source.get('sha256_before', '')}`")
    lines.append(f"- **После анализа:** `{source.get('sha256_after', '')}`")
    lines.append("")

    lines.append("## 3. Неизменность файла")
    lines.append("")
    unchanged = source.get("unchanged")
    lines.append(
        f"- **Файл не изменён:** {'да' if unchanged else 'нет — анализ прерван'}"
    )
    lines.append("")

    lines.append("## 4. Конфигурация исключения листов")
    lines.append("")
    terms = config.get("excluded_sheet_name_contains") or []
    lines.append(f"- `exclude_sheet_name_contains`: {', '.join(f'`{t}`' for t in terms)}")
    lines.append("")

    lines.append("## 5. Все листы")
    lines.append("")
    lines.append(
        "| Лист | Статус | Категория | Режим | Назначение | Conf | "
        "Диапазон | Header | Исключение |"
    )
    lines.append(
        "|------|--------|-----------|-------|------------|------|"
        "---------|--------|------------|"
    )
    for sheet in workbook.get("sheets", []):
        cat, mode, purpose, conf = _classification_labels(sheet)
        if sheet.get("status") == "excluded":
            actual = f"max {sheet.get('excel_max_row', 0)}×{sheet.get('excel_max_column', 0)}"
            header = "—"
            reason = sheet.get("exclusion_reason") or ""
        else:
            actual = (
                f"{sheet.get('actual_last_row', 0)}×{sheet.get('actual_last_column', 0)} "
                f"(excel {sheet.get('excel_max_row', 0)}×{sheet.get('excel_max_column', 0)})"
            )
            header = str(sheet.get("probable_header_row") or "—")
            reason = "—"
        lines.append(
            f"| {sheet.get('sheet_name', '')} | {sheet.get('status', '')} | {cat} | {mode} | "
            f"{purpose} | {conf} | {actual} | {header} | {reason} |"
        )
    lines.append("")

    excluded = [s for s in workbook.get("sheets", []) if s.get("status") == "excluded"]
    lines.append("## 6. Excluded-листы")
    lines.append("")
    if not excluded:
        lines.append("_Нет excluded-листов._")
    else:
        for sheet in excluded:
            cat, mode, purpose, conf = _classification_labels(sheet)
            lines.append(
                f"- **{sheet.get('sheet_name')}** — `{sheet.get('exclusion_reason')}` "
                f"(term: `{sheet.get('matched_exclusion_term')}`); "
                f"классификация: {cat}, режим {mode}, {purpose} (conf {conf})"
            )
    lines.append("")

    analyzed = [s for s in workbook.get("sheets", []) if s.get("status") == "analyzed"]
    lines.append("## 7. Analyzed-листы")
    lines.append("")
    for sheet in analyzed:
        cls = sheet.get("classification") or {}
        lines.append(f"### {sheet.get('sheet_name')}")
        lines.append("")
        lines.append(
            f"- Классификация: **{_PERSONNEL_CATEGORY_RU.get(cls.get('proposed_personnel_category', 'unknown'))}** / "
            f"**{_EMPLOYMENT_MODE_RU.get(cls.get('proposed_employment_mode', 'unknown'))}** "
            f"(confidence {cls.get('classification_confidence')})"
        )
        lines.append(
            f"- Probable header row: **{sheet.get('probable_header_row')}** "
            f"(confidence {sheet.get('header_confidence')})"
        )
        lines.append(f"- Matched aliases: {', '.join(sheet.get('matched_header_aliases') or []) or '—'}")
        stats = sheet.get("statistics") or {}
        lines.append(f"- Probable person rows: {stats.get('probable_person_rows', 0)}")
        lines.append(f"- Inherited section rows: {stats.get('probable_inherited_section_rows', 0)}")
        lines.append("")

        lines.append("#### Карта столбцов")
        lines.append("")
        lines.append("| Col | Header | Semantic field | Confidence | Types | Issues |")
        lines.append("|-----|--------|----------------|------------|-------|--------|")
        for col in sheet.get("columns") or []:
            types = ", ".join(f"{k}:{v}" for k, v in (col.get("value_type_distribution") or {}).items())
            issues = ", ".join(f"{k}:{v}" for k, v in (col.get("issue_counts") or {}).items()) or "—"
            lines.append(
                f"| {col.get('column_letter')} | {col.get('raw_header') or '—'} | "
                f"{col.get('proposed_semantic_field') or '—'} | {col.get('semantic_confidence')} | "
                f"{types or '—'} | {issues} |"
            )
        lines.append("")

        sheet_issues = stats.get("issue_counts") or {}
        if sheet_issues:
            lines.append("#### Проблемы листа")
            lines.append("")
            for code, count in sorted(sheet_issues.items()):
                lines.append(f"- `{code}`: {count}")
            lines.append("")

    lines.append("## 8. Общая статистика (только analyzed-листы)")
    lines.append("")
    lines.append(f"- Probable person rows: {summary.get('probable_person_rows', 0)}")
    lines.append(f"- Rows with IIN: {summary.get('rows_with_iin', 0)}")
    lines.append(f"- Rows without IIN: {summary.get('rows_without_iin', 0)}")
    lines.append(f"- Composite cells: {summary.get('composite_cell_count', 0)}")
    lines.append("")

    emp = summary.get("rows_by_employment_mode") or {}
    lines.append("### Режим занятости источника")
    lines.append("")
    lines.append(f"- основные: {emp.get('primary', 0)}")
    lines.append(f"- совместители: {emp.get('concurrent', 0)}")
    lines.append(f"- неизвестно: {emp.get('unknown', 0)}")
    lines.append("")

    cat = summary.get("rows_by_personnel_category") or {}
    lines.append("### Категории персонала")
    lines.append("")
    lines.append(f"- врачи: {cat.get('doctor', 0)}")
    lines.append(f"- средний медперсонал: {cat.get('nursing_staff', 0)}")
    lines.append(f"- младший медперсонал: {cat.get('junior_medical_staff', 0)}")
    lines.append(f"- прочий персонал: {cat.get('other_staff', 0)}")
    lines.append(f"- неизвестно: {cat.get('unknown', 0)}")
    lines.append("")

    lines.append("### Issues by code")
    lines.append("")
    issues = summary.get("issues_by_code") or {}
    if issues:
        for code, count in sorted(issues.items()):
            lines.append(f"- `{code}`: {count}")
    else:
        lines.append("_Нет зарегистрированных проблем._")
    lines.append("")

    lines.append("## 9. Рекомендации для mapping profile")
    lines.append("")
    semantic = summary.get("semantic_fields_detected") or {}
    if semantic:
        for field, count in sorted(semantic.items()):
            lines.append(f"- `{field}` — обнаружено на {count} столбц(ах); требует явного mapping profile")
    else:
        lines.append("_Semantic fields не обнаружены на analyzed-листах._")
    lines.append("")
    lines.append(
        "> Профилировщик не выполняет импорт в PPR. Semantic mappings и классификация листов "
        "носят рекомендательный характер."
    )
    lines.append("")

    with path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
