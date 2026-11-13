"""Printable, assignment-based staff reconciliation workbook."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from io import BytesIO
import re
from typing import Any, Iterable, Mapping

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.page import PageMargins
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from app.security.directory_scope import build_dept_scope_cte
from app.services.personnel_position_ordering import normalize_position_name


HEADERS = ("№", "ФИО", "Должность", "Основное / совмещение", "Ставка", "Поправки и замечания")
UNKNOWN_UNIT = "Отделение не указано"


def position_rank(name: str | None, type_code: int | None) -> int:
    """Requested print order; an unknown type always follows the typed groups."""
    if type_code not in (1, 2, 3, 4):
        return 6
    normalized = normalize_position_name(name)
    if "заведующ" in normalized and "отделен" in normalized:
        return 0
    if "врач" in normalized or type_code == 1:
        return 1
    if "старш" in normalized and any(stem in normalized for stem in ("медсестр", "медбрат", "медицинск сестр")):
        return 2
    if "фельдшер" in normalized or type_code == 2:
        return 3
    if "санитарк" in normalized or "санитар" in normalized or type_code == 3:
        return 4
    return 5


def fetch_current_assignments(
    engine: Engine, *, scope_unit_id: int | None, scope_unit_ids: list[int] | None,
) -> tuple[date, list[dict[str, Any]]]:
    """Read all visible current assignments, independent of roster filters/pages."""
    if scope_unit_ids is not None and not scope_unit_ids:
        return date.today(), []
    scope_cte, scope_where, params = build_dept_scope_cte(scope_unit_id=scope_unit_id, alias="pa")
    predicates = [
        "pa.active_flag IS TRUE", "pa.lifecycle_status='active'",
        "pa.start_date<=:as_of", "(pa.end_date IS NULL OR pa.end_date>=:as_of)",
        "e.is_active IS TRUE", "e.operational_status='active'",
        "COALESCE(e.date_from, :as_of)<=:as_of", "(e.date_to IS NULL OR e.date_to>=:as_of)",
        "COALESCE(person.person_status, 'active')='active'",
        "person.merged_into_person_id IS NULL",
    ]
    if scope_where:
        predicates.append(scope_where)
    if scope_unit_id is not None:
        # The existing roster is scoped by employee owner unit as well.
        predicates.append("e.org_unit_id IN (SELECT unit_id FROM rbac_subtree)")
    if scope_unit_ids is not None:
        predicates.append("pa.org_unit_id IN :visible_units")
        predicates.append("e.org_unit_id IN :visible_units")
        params["visible_units"] = sorted({int(unit_id) for unit_id in scope_unit_ids})
    sql = text(f"""
        {scope_cte}
        SELECT pa.assignment_id, pa.org_unit_id, ou.name AS org_unit_name,
               pa.position_id, pos.name AS position_name,
               COALESCE(pa.manual_type_code, pos.type_code) AS type_code,
               pa.rate, pa.is_primary, e.employee_id,
               COALESCE(NULLIF(BTRIM(person.full_name), ''), NULLIF(BTRIM(e.full_name), '')) AS full_name
        FROM public.person_assignments pa
        JOIN public.employees e ON e.person_id=pa.person_id
        JOIN public.persons person ON person.person_id=pa.person_id
        LEFT JOIN public.positions pos ON pos.position_id=pa.position_id
        LEFT JOIN public.org_units ou ON ou.unit_id=pa.org_unit_id
        WHERE {' AND '.join(predicates)}
        ORDER BY pa.assignment_id
    """)
    if scope_unit_ids is not None:
        sql = sql.bindparams(bindparam("visible_units", expanding=True))
    with engine.connect() as conn:
        conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        as_of = conn.execute(text("SELECT CURRENT_DATE")).scalar_one()
        rows = conn.execute(sql, {**params, "as_of": as_of}).mappings().all()
    return as_of, [dict(row) for row in rows]


def _sheet_title(name: str, unit_id: int | None, used: set[str]) -> str:
    cleaned = re.sub(r"[\\/*?:\[\]]", " ", name).strip().strip("'") or UNKNOWN_UNIT
    title = cleaned[:31]
    if title.casefold() in used:
        suffix = f" ({unit_id if unit_id is not None else 'без ID'})"
        title = cleaned[:31 - len(suffix)] + suffix
    serial = 2
    while title.casefold() in used:
        suffix = f" ({serial})"
        title = cleaned[:31 - len(suffix)] + suffix
        serial += 1
    used.add(title.casefold())
    return title


def build_reconciliation_workbook(rows: Iterable[Mapping[str, Any]], *, as_of: date) -> bytes:
    """One line per assignment on its own department sheet."""
    by_assignment: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        assignment_id = int(row["assignment_id"])
        if assignment_id in by_assignment and dict(by_assignment[assignment_id]) != dict(row):
            raise ValueError(f"Assignment {assignment_id} has conflicting export rows")
        by_assignment[assignment_id] = row
    groups: dict[tuple[int | None, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in by_assignment.values():
        unit_id = int(row["org_unit_id"]) if row.get("org_unit_id") is not None else None
        unit_name = str(row.get("org_unit_name") or UNKNOWN_UNIT).strip() or UNKNOWN_UNIT
        groups[(unit_id, unit_name)].append(row)
    if not groups:
        groups[(None, UNKNOWN_UNIT)] = []

    wb = Workbook()
    wb.remove(wb.active)
    used_titles: set[str] = set()
    for (unit_id, unit_name), items in sorted(groups.items(), key=lambda entry: (entry[0][1].casefold(), entry[0][0] or -1)):
        ws = wb.create_sheet(_sheet_title(unit_name, unit_id, used_titles))
        ws.merge_cells("A1:F1")
        ws["A1"] = f"Отделение: {unit_name}"
        ws["A1"].font = Font(bold=True, size=14)
        ws.merge_cells("A2:F2")
        ws["A2"] = f"Дата выгрузки: {as_of.strftime('%d.%m.%Y')}"
        ws["A2"].font = Font(size=11)
        for col, title in enumerate(HEADERS, 1):
            cell = ws.cell(3, col, title)
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DCE6F1")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[3].height = 32
        ordered = sorted(items, key=lambda row: (
            position_rank(row.get("position_name"), row.get("type_code")),
            str(row.get("full_name") or "").casefold(),
            int(row["assignment_id"]),
        ))
        for number, row in enumerate(ordered, 1):
            line = number + 3
            values = (
                number,
                str(row.get("full_name") or ""),
                str(row.get("position_name") or ""),
                "Основное" if row.get("is_primary") else "Совмещение",
                float(row["rate"]) if row.get("rate") is not None else None,
                None,
            )
            for col, value in enumerate(values, 1):
                cell = ws.cell(line, col, value)
                cell.alignment = Alignment(vertical="center", wrap_text=True)
                cell.border = Border(bottom=Side(style="hair", color="C7CDD3"))
            ws.cell(line, 5).number_format = "0.##"
            ws.row_dimensions[line].height = 25
        for col, width in {"A": 6, "B": 34, "C": 38, "D": 22, "E": 11, "F": 48}.items():
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A4"
        ws.print_title_rows = "1:3"
        ws.print_options.horizontalCentered = True
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.page_margins = PageMargins(left=0.3, right=0.3, top=0.5, bottom=0.5, header=0.2, footer=0.2)
        ws.print_area = f"A1:F{max(3, len(ordered) + 3)}"
    out = BytesIO()
    wb.save(out)
    return out.getvalue()
