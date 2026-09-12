"""Tests for HR control list staging parser (Phase 0B)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from app.services.hr_import_profile_service import build_import_profile
from scripts.import_hr_control_list import (
    _is_lossless_control_list_header,
    build_field_map,
    build_audit,
    build_merged_section_lookup,
    clean_iin,
    export_outputs,
    get_layout_profile,
    mask_iin,
    parse_birth_date,
    parse_sheet_generic,
    parse_sheet_with_profile,
    parse_workbook,
    resolve_section_department,
    resolve_sheet_type,
)


def _build_doctors_sheet(ws) -> None:
    ws.append([""] * 20)
    ws.append([""] * 20)
    ws.append([""] * 20)
    ws.append([""] * 20)
    ws.append([""] * 20)
    ws.append([""] * 20)
    ws.append(
        [
            "№",
            "",
            "Фамилия, имя, отчество",
            "Год рождения",
            "ИИН",
            "пол",
            "",
            "",
            "",
            "Занимаемая должность",
            "",
            "",
            "Повышение квалификации",
            "Квалификационная категория",
        ]
        + [""] * 6
    )
    ws.append(
        [
            1,
            "АДМИНИСТРАТИВНЫЙ ПЕРСОНАЛ",
            "Иванов Иван Иванович",
            datetime(1990, 1, 1),
            "900101300123",
            "муж",
            "",
            "",
            "",
            "Директор",
            "",
            "",
            "2024 курс ПК",
            "высшая",
        ]
        + [""] * 6
    )
    ws.append(
        [
            2,
            "",
            "Петрова Анна Сергеевна",
            32874,
            "900101300123",
            "жен",
            "",
            "",
            "",
            "Врач-хирург",
            "",
            "",
            "",
            "",
        ]
        + [""] * 6
    )
    ws.append([3, "ХИРУРГИЯ", "", "", "", "", "", "", "", "", "", "", "", "", ""] + [""] * 6)
    ws.cell(row=11, column=2, value="ХИРУРГИЯ")
    ws.merge_cells("B11:B12")
    ws.append(
        [
            4,
            "",
            "Сидоров Петр",
            datetime(1985, 5, 5),
            "850505400456",
            "муж",
            "",
            "",
            "",
            "Хирург",
            "",
            "",
            "",
            "",
        ]
        + [""] * 6
    )


def _build_nurses_sheet(ws) -> None:
    ws.append([""] * 12)
    ws.append([""] * 12)
    ws.append([""] * 12)
    ws.append(
        [
            "",
            "№",
            "",
            "Фамилия, имя, отчество",
            "Год рождения",
            "ИИН",
            "пол",
            "",
            "",
            "",
            "Занимаемая должность, дата назнач.",
            "",
        ]
    )
    ws.append(
        [
            "",
            "",
            "ТЕРАПИЯ",
            "Сидорова Мария",
            datetime(1985, 5, 5),
            "850505400456",
            "жен",
            "",
            "",
            "",
            "Медсестра",
            "",
        ]
    )
    ws.append(["", 1, "", "Кузнецова Анна", datetime(1980, 3, 16), "800316400190", "жен", "", "", "", "М/с", ""])


def _build_junior_staff_sheet(ws) -> None:
    ws.append([""] * 10)
    ws.append([""] * 10)
    ws.append([""] * 10)
    ws.append([""] * 10)
    ws.append(
        [
            "",
            "",
            "Фамилия, имя, отчество",
            "Год рождения",
            "ИИН",
            "пол",
            "",
            "Занимаемая должность",
            "",
            "Телефон",
        ]
    )
    ws.append(
        [
            "",
            "ОБЩЕБОЛЬНИЧНЫЙ",
            "Амангельдинова Балжан",
            datetime(1974, 8, 26),
            "740826400893",
            "жен",
            "",
            "санитарка",
            "",
            "87025059904",
        ]
    )
    ws.append(["", "", "Шокумова Гульмира", datetime(1976, 1, 11), "760111450360", "жен", "", "санитарка", "", ""])


def _build_sample_workbook(path: Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    _build_doctors_sheet(wb.create_sheet("врачи"))
    _build_nurses_sheet(wb.create_sheet("медсестра"))
    _build_junior_staff_sheet(wb.create_sheet("санитарки"))
    wb.create_sheet("неизвестный лист").append(["ФИО", "ИИН"])
    wb.save(path)


def test_resolve_sheet_type():
    assert resolve_sheet_type("врачи") == "doctors"
    assert resolve_sheet_type("медсестра") == "nurses"
    assert resolve_sheet_type("санитарки") == "junior_staff"
    assert resolve_sheet_type("врачи совместители") == "part_time"
    assert resolve_sheet_type("декларационные листы") == "declaration"
    assert resolve_sheet_type("лист1") is None


def test_clean_iin_and_birth_date():
    assert clean_iin("900 101 300 123")[0:2] == ("900 101 300 123", False)
    assert clean_iin("12345")[1] is False
    assert clean_iin(580131300091.0)[1] is False
    assert clean_iin("580131300091.0")[1] is False
    assert parse_birth_date(32874) == "1990-01-01"
    assert mask_iin("900101300123") == "9001****23"


def _build_director_regression_sheet(ws) -> None:
    """Doctors sheet with director row — regression for IIN 580131300091."""
    ws.append([""] * 20)
    ws.append([""] * 20)
    ws.append([""] * 20)
    ws.append([""] * 20)
    ws.append([""] * 20)
    ws.append([""] * 20)
    ws.append(
        [
            "№",
            "",
            "Фамилия, имя, отчество",
            "Год рождения",
            "ИИН",
            "пол",
            "Национальность",
            "Вуз, год окончания",
            "Специальность по диплому",
            "Занимаемая должность",
        ]
        + [""] * 10
    )
    ws.append(
        [
            1,
            "АДМИНИСТРАТИВНЫЙ ПЕРСОНАЛ",
            "Тулеутаев Мухтар Есетжанович",
            datetime(1958, 1, 31),
            580131300091.0,
            "муж",
            "",
            "КазНМУ, 1982",
            "Лечебное дело",
            "Директор",
        ]
        + [""] * 10
    )


def test_director_iin_not_missing_after_float_excel_value(tmp_path: Path):
    path = tmp_path / "director_iin.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    _build_director_regression_sheet(wb.create_sheet("врачи"))
    wb.save(path)

    rows, _ = parse_workbook(path)
    director = next(r for r in rows if r.full_name == "Тулеутаев Мухтар Есетжанович")
    assert director.iin_digits == "580131300091"
    assert director.iin_valid is True
    assert director.data["iin"] == "580131300091"


def test_director_iin_with_shifted_column_by_header(tmp_path: Path):
    """IIN must resolve by header even when fixed profile column letter is wrong."""
    path = tmp_path / "shifted_iin.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("врачи")
    for _ in range(6):
        ws.append([""] * 22)
    ws.append(
        [
            "№",
            "",
            "Фамилия, имя, отчество",
            "Год рождения",
            "Примечание",
            "ИИН",
            "пол",
        ]
        + [""] * 15
    )
    ws.append(
        [
            1,
            "АДМИНИСТРАТИВНЫЙ ПЕРСОНАЛ",
            "Тулеутаев Мухтар Есетжанович",
            datetime(1958, 1, 31),
            "",
            "580131300091",
            "муж",
        ]
        + [""] * 15
    )
    wb.save(path)

    rows, _ = parse_workbook(path)
    director = next(r for r in rows if "Тулеутаев" in r.full_name)
    assert director.iin_digits == "580131300091"
    assert director.iin_valid is True


def test_parses_doctors_layout_profile(tmp_path: Path):
    path = tmp_path / "doctors.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    _build_doctors_sheet(wb.create_sheet("врачи"))
    wb.save(path)

    wb = __import__("openpyxl").load_workbook(path, data_only=True)
    rows = parse_sheet_with_profile(wb["врачи"], sheet_type="doctors", profile=get_layout_profile("doctors"))
    wb.close()

    first = rows[0]
    assert first.full_name == "Иванов Иван Иванович"
    assert first.department == "АДМИНИСТРАТИВНЫЙ ПЕРСОНАЛ"
    assert first.data["position_raw"] == "Директор"
    assert first.education_training_raw == "2024 курс ПК"
    assert first.training_raw == "2024 курс ПК"
    assert first.certification_raw == "высшая"


def test_parses_nurses_layout_profile(tmp_path: Path):
    path = tmp_path / "nurses.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    _build_nurses_sheet(wb.create_sheet("медсестра"))
    wb.save(path)

    wb = __import__("openpyxl").load_workbook(path, data_only=True)
    rows = parse_sheet_with_profile(wb["медсестра"], sheet_type="nurses", profile=get_layout_profile("nurses"))
    wb.close()

    assert rows[0].full_name == "Сидорова Мария"
    assert rows[0].department == "ТЕРАПИЯ"
    assert rows[1].department == "ТЕРАПИЯ"


def test_parses_junior_staff_layout_profile(tmp_path: Path):
    path = tmp_path / "junior.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    _build_junior_staff_sheet(wb.create_sheet("санитарки"))
    wb.save(path)

    wb = __import__("openpyxl").load_workbook(path, data_only=True)
    rows = parse_sheet_with_profile(
        wb["санитарки"],
        sheet_type="junior_staff",
        profile=get_layout_profile("junior_staff"),
    )
    wb.close()

    assert rows[0].full_name == "Амангельдинова Балжан"
    assert rows[0].department == "ОБЩЕБОЛЬНИЧНЫЙ"
    assert rows[1].department == "ОБЩЕБОЛЬНИЧНЫЙ"


def test_resolves_department_from_merged_section(tmp_path: Path):
    path = tmp_path / "merged.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    _build_doctors_sheet(wb.create_sheet("врачи"))
    wb.save(path)

    wb = __import__("openpyxl").load_workbook(path, data_only=True)
    ws = wb["врачи"]
    lookup = build_merged_section_lookup(ws, 2)
    assert lookup[11] == "ХИРУРГИЯ"
    assert lookup[12] == "ХИРУРГИЯ"
    assert resolve_section_department(ws, 12, 2, lookup, "PREV") == "ХИРУРГИЯ"

    rows = parse_sheet_with_profile(ws, sheet_type="doctors", profile=get_layout_profile("doctors"))
    surgeon = next(row for row in rows if row.full_name == "Сидоров Петр")
    assert surgeon.department == "ХИРУРГИЯ"
    wb.close()


def test_section_value_same_row_as_employee(tmp_path: Path):
    path = tmp_path / "same_row.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    _build_doctors_sheet(wb.create_sheet("врачи"))
    wb.save(path)

    wb = __import__("openpyxl").load_workbook(path, data_only=True)
    rows = parse_sheet_with_profile(wb["врачи"], sheet_type="doctors", profile=get_layout_profile("doctors"))
    wb.close()

    first = rows[0]
    assert first.full_name == "Иванов Иван Иванович"
    assert first.department == "АДМИНИСТРАТИВНЫЙ ПЕРСОНАЛ"
    assert first.full_name != first.department


def _build_lossless_a_to_s_sheet(ws) -> None:
    ws.append(
        [
            "Отделение",
            "ФИО",
            "Год рождения",
            "ИИН",
            "пол",
            "Национальность",
            "ВУЗ, год окончания",
            "Специальность по диплому",
            "Занимаемая должность",
            "Должность",
            "Дата",
            "Категория должности",
            "Стаж работы",
            "Повышение квалификации",
            "Квалификационная категория",
            "Степень",
            "Награды",
            "Примечание (декрет, инвалид, пенсионер)",
            "Телефоны",
        ]
    )
    ws.append(
        [
            "Тестовое отделение",
            "Тестовый Сотрудник",
            1984,
            "840101300123",
            "муж",
            "тестовая национальность",
            "Тестовый ВУЗ, 2006",
            "Тестовая специальность",
            "Занимаемая должность",
            "Штатная должность",
            "2017-04-03",
            "Должностная категория",
            "15 лет",
            "Тестовое повышение квалификации",
            "Квалификационная категория",
            "Тестовая степень",
            "Тестовая награда",
            "Тестовое примечание",
            "70000000000",
        ]
    )


def test_lossless_a_to_s_header_mapping_and_parser_idempotency(tmp_path: Path):
    path = tmp_path / "контрольный2606.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "врачи"
    _build_lossless_a_to_s_sheet(sheet)
    workbook.save(path)
    workbook.close()

    first_rows, first_warnings = parse_workbook(path)
    second_rows, second_warnings = parse_workbook(path)

    assert first_warnings == second_warnings == []
    assert [row.data for row in first_rows] == [row.data for row in second_rows]
    assert len(first_rows) == 1
    data = first_rows[0].data
    assert data == {
        "full_name": "Тестовый Сотрудник",
        "iin": "840101300123",
        "birth_date": "",
        "birth_year_raw": "1984",
        "sex": "муж",
        "nationality": "тестовая национальность",
        "department": "Тестовое отделение",
        "position_raw": "Занимаемая должность",
        "staff_position_raw": "Штатная должность",
        "position_date_raw": "2017-04-03",
        "job_category_raw": "Должностная категория",
        "education_raw": "Тестовый ВУЗ, 2006",
        "diploma_specialty_raw": "Тестовая специальность",
        "qualification_raw": "Квалификационная категория",
        "qualification_category_raw": "Квалификационная категория",
        "experience_raw": "15 лет",
        "training_raw": "Тестовое повышение квалификации",
        "education_training_raw": "Тестовое повышение квалификации",
        "certification_raw": "Квалификационная категория",
        "degree_raw": "Тестовая степень",
        "awards_raw": "Тестовая награда",
        "note_raw": "Тестовое примечание",
        "phone_raw": "70000000000",
        "source_sheet": "врачи",
        "source_row_number": "2",
    }


def test_lossless_a_to_s_fields_do_not_change_legacy_profile_fallback(tmp_path: Path):
    path = tmp_path / "legacy_doctors.xlsx"
    workbook = Workbook()
    workbook.remove(workbook.active)
    _build_doctors_sheet(workbook.create_sheet("врачи"))
    workbook.save(path)
    workbook.close()

    rows, _ = parse_workbook(path)

    assert rows[0].data["staff_position_raw"] == ""
    assert rows[0].data["position_date_raw"] == ""
    assert rows[0].data["job_category_raw"] == ""
    assert rows[0].data["qualification_category_raw"] == ""
    assert rows[0].data["position_raw"] == "Директор"
    assert rows[0].training_raw == "2024 курс ПК"


def test_lossless_a_to_s_recognition_requires_every_header_at_its_position():
    headers = [
        "Отделение", "ФИО", "Год рождения", "ИИН", "пол", "Национальность",
        "ВУЗ, год окончания", "Специальность по диплому", "Занимаемая должность",
        "Должность", "Дата", "Категория должности", "Стаж работы",
        "Повышение квалификации", "Квалификационная категория", "Степень", "Награды",
        "Примечание (декрет, инвалид, пенсионер)", "Телефоны",
    ]
    assert _is_lossless_control_list_header(headers) is True

    partial = [
        "Отделение", "ФИО", "ИИН", "Занимаемая должность", "Должность", "Дата",
        "Категория должности", "Квалификационная категория",
    ]
    assert _is_lossless_control_list_header(partial) is False
    partial_map = build_field_map(partial)
    assert "staff_position_raw" not in partial_map
    assert "position_date_raw" not in partial_map
    assert "job_category_raw" not in partial_map
    assert "qualification_category_raw" not in partial_map

    swapped_positions = headers.copy()
    swapped_positions[8], swapped_positions[9] = swapped_positions[9], swapped_positions[8]
    assert _is_lossless_control_list_header(swapped_positions) is False
    swapped_categories = headers.copy()
    swapped_categories[11], swapped_categories[14] = swapped_categories[14], swapped_categories[11]
    assert _is_lossless_control_list_header(swapped_categories) is False


def test_legacy_coincident_captions_do_not_populate_iq4_fields(tmp_path: Path):
    path = tmp_path / "legacy_coincident_headers.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["ФИО", "ИИН", "Дата", "Должность", "Категория должности"])
    sheet.append(["Тестовый Сотрудник", "840101300123", "2020-01-01", "Тестовая должность", "Тестовая категория"])
    workbook.save(path)
    workbook.close()

    workbook = __import__("openpyxl").load_workbook(path, data_only=True)
    rows = parse_sheet_generic(workbook.active, sheet_type="part_time")
    workbook.close()

    assert len(rows) == 1
    assert rows[0].data["staff_position_raw"] == ""
    assert rows[0].data["position_date_raw"] == ""
    assert rows[0].data["job_category_raw"] == ""
    assert rows[0].data["qualification_category_raw"] == ""


def test_legacy_position_aliases_keep_leftmost_source_column(tmp_path: Path):
    path = tmp_path / "legacy_position_aliases.xlsx"
    headers = ["ФИО", "ИИН", "Занимаемая должность", "Должность"]
    assert build_field_map(headers)["position_raw"] == 3

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    sheet.append([
        "Тестовый Сотрудник",
        "840101300123",
        "Занимаемая должность",
        "Штатная должность",
    ])
    workbook.save(path)
    workbook.close()

    workbook = __import__("openpyxl").load_workbook(path, data_only=True)
    rows = parse_sheet_generic(workbook.active, sheet_type="part_time")
    workbook.close()

    assert len(rows) == 1
    assert rows[0].data["position_raw"] == "Занимаемая должность"
    assert rows[0].data["staff_position_raw"] == ""
    assert rows[0].data["position_date_raw"] == ""
    assert rows[0].data["job_category_raw"] == ""
    assert rows[0].data["qualification_category_raw"] == ""


def test_modern_job_category_never_normalizes_as_qualification_category(tmp_path: Path):
    path = tmp_path / "контрольный2606.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "врачи"
    _build_lossless_a_to_s_sheet(sheet)
    sheet.cell(2, 15).value = None  # O: qualification category is intentionally empty.
    workbook.save(path)
    workbook.close()

    rows, _ = parse_workbook(path)
    data = rows[0].data
    profile = build_import_profile(data)

    assert data["job_category_raw"] == "Должностная категория"
    assert data["qualification_category_raw"] == ""
    assert data["qualification_raw"] == ""
    assert profile["category_records"] == []


def test_modern_qualification_category_remains_in_profile_pipeline(tmp_path: Path):
    path = tmp_path / "контрольный2606.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "врачи"
    _build_lossless_a_to_s_sheet(sheet)
    workbook.save(path)
    workbook.close()

    rows, _ = parse_workbook(path)
    data = rows[0].data
    profile = build_import_profile(data)

    assert data["qualification_category_raw"] == "Квалификационная категория"
    assert data["qualification_raw"] == data["qualification_category_raw"]
    assert profile["category_records"]


def _build_generic_legacy_department_sheet(ws) -> None:
    """Generic layout: B is the legacy section column but has no header."""
    ws.append(["№", "", "ФИО", "ИИН", "Должность"])
    # Section-only context must be applied even though this row is not data.
    ws.append(["", "ОТДЕЛ А", "", "", ""])
    ws.append([1, "", "Тестов Один", "900101300123", "Специалист"])
    # The next section is a merged B range spanning two employee rows.
    ws.append([2, "ОТДЕЛ Б", "Тестов Два", "900102300124", "Специалист"])
    ws.merge_cells("B4:B5")
    ws.append([3, "", "Тестов Три", "900103300125", "Специалист"])


def test_generic_legacy_b_department_carries_section_and_merged_context(tmp_path: Path):
    path = tmp_path / "generic_legacy_department.xlsx"
    wb = Workbook()
    ws = wb.active
    _build_generic_legacy_department_sheet(ws)
    wb.save(path)

    wb = __import__("openpyxl").load_workbook(path, data_only=True)
    rows = parse_sheet_generic(wb.active, sheet_type="part_time")
    wb.close()

    employees = [row for row in rows if row.is_employee_roster]
    assert len(employees) == 3
    assert [row.department for row in employees] == ["ОТДЕЛ А", "ОТДЕЛ Б", "ОТДЕЛ Б"]


def test_generic_legacy_b_department_leaves_rows_before_first_section_empty(tmp_path: Path):
    path = tmp_path / "generic_legacy_department_before_section.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["№", "", "ФИО", "ИИН", "Должность"])
    ws.append([1, "", "Тестов До", "900101300123", "Специалист"])
    ws.append(["", "ОТДЕЛ А", "", "", ""])
    ws.append([2, "", "Тестов После", "900102300124", "Специалист"])
    wb.save(path)

    wb = __import__("openpyxl").load_workbook(path, data_only=True)
    rows = parse_sheet_generic(wb.active, sheet_type="part_time")
    wb.close()

    employees = [row for row in rows if row.is_employee_roster]
    # This also locks the employee-row count: department context must not
    # alter the existing row-classification policy.
    assert len(employees) == 2
    assert [row.department for row in employees] == ["", "ОТДЕЛ А"]


def test_parse_workbook(tmp_path: Path):
    source = tmp_path / "control.xlsx"
    _build_sample_workbook(source)

    rows, warnings = parse_workbook(source)
    audit = build_audit(rows)

    assert any(w.startswith("skip_unknown_sheet:") for w in warnings)
    assert audit["total_rows"] >= 5
    assert audit["valid_iin"] >= 4
    assert audit["duplicate_iin"] >= 1
    assert audit["missing_full_name"] <= 1
    assert audit["missing_department"] == 0
    assert audit["with_training"] >= 1
    assert audit["with_certification"] >= 1


def test_export_outputs(tmp_path: Path):
    source = tmp_path / "control.xlsx"
    out_dir = tmp_path / "out"
    _build_sample_workbook(source)
    rows, _ = parse_workbook(source)
    audit = build_audit(rows)
    paths = export_outputs(rows, audit, out_dir)

    assert paths["preview"].exists()
    assert paths["errors"].exists()
    assert paths["duplicates"].exists()
