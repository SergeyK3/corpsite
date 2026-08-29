from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.operational_orders.archive_import import (
    REQUIRED_COLUMNS,
    DryRunTechnicalError,
    run_dry_run,
)
from app.operational_orders.archive_import.dry_run import _is_within_root
from scripts.dry_run_operational_orders_archive_import import main as cli_main


SHEET_NAME = "Производственные приказы"


def _row(
    *,
    source_number: str = "1",
    file_name: str = "Приказ.docx",
    relative_path: str = "[Аптека]\\Приказ.docx",
    archive_section: str = "[Аптека]",
    order_number: str = "001-A",
    order_date: object = "01.02.2026",
) -> dict[str, object]:
    return {
        "№ п/п": source_number,
        "Имя файла (Word/PDF)": file_name,
        "Тип документа": "Приказ",
        "Статус": "Найден",
        "Тип события / предмет приказа": "Тест",
        "Номер приказа": order_number,
        "Дата приказа": order_date,
        "Примечание": "",
        "Исходная папка": "Производственные приказы",
        "Раздел архива": archive_section,
        "Относительный путь к файлу": relative_path,
    }


def _write_manifest(
    path: Path,
    rows: list[dict[str, object]],
    *,
    headers: tuple[str, ...] = REQUIRED_COLUMNS,
) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = SHEET_NAME
    worksheet.append(list(headers))
    for row in rows:
        worksheet.append([row.get(header) for header in headers])
    workbook.save(path)
    workbook.close()


def _create_file(root: Path, relative_path: str, content: bytes = b"document") -> Path:
    path = root.joinpath(*relative_path.replace("\\", "/").split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _issue_codes(report) -> set[str]:
    return {issue.code for issue in report.errors} | {issue.code for issue in report.warnings}


def test_successful_small_manifest_and_root_file(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    nested = _row()
    root_row = _row(
        source_number="2",
        file_name="Корневой.pdf",
        relative_path="Корневой.pdf",
        archive_section="Корень архива",
        order_number="",
        order_date="",
    )
    _create_file(archive_root, str(nested["Относительный путь к файлу"]), b"nested")
    root_file = _create_file(archive_root, str(root_row["Относительный путь к файлу"]), b"root")
    xlsx = tmp_path / "manifest.xlsx"
    _write_manifest(xlsx, [nested, root_row])

    report = run_dry_run(xlsx_path=xlsx, archive_root=archive_root, expected_rows=2)

    assert report.outcome == "PASS"
    assert report.summary.total_rows == 2
    assert report.summary.valid_rows == 2
    assert report.summary.existing_files == 2
    assert report.summary.root_archive_files == 1
    assert report.summary.empty_order_numbers == 1
    assert report.summary.empty_order_dates == 1
    assert report.rows[0].source.order_number == "001-A"
    assert report.rows[1].sha256 == hashlib.sha256(root_file.read_bytes()).hexdigest()


def test_missing_required_column_is_technical_error(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    xlsx = tmp_path / "manifest.xlsx"
    headers = tuple(header for header in REQUIRED_COLUMNS if header != "Статус")
    _write_manifest(xlsx, [_row()], headers=headers)

    with pytest.raises(DryRunTechnicalError) as error:
        run_dry_run(xlsx_path=xlsx, archive_root=archive_root)

    assert error.value.code == "REQUIRED_COLUMNS_MISSING"
    assert "Статус" in str(error.value)


def test_duplicate_required_column_is_technical_error(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    xlsx = tmp_path / "manifest.xlsx"
    headers = (*REQUIRED_COLUMNS, "Статус")
    _write_manifest(xlsx, [_row()], headers=headers)

    with pytest.raises(DryRunTechnicalError) as error:
        run_dry_run(xlsx_path=xlsx, archive_root=archive_root)

    assert error.value.code == "REQUIRED_COLUMN_DUPLICATE"
    assert "Статус" in str(error.value)


@pytest.mark.parametrize(
    ("rows", "files", "expected_code"),
    [
        (
            [
                _row(source_number="7"),
                _row(
                    source_number="7",
                    file_name="Второй.docx",
                    relative_path="[Аптека]\\Второй.docx",
                ),
            ],
            ["[Аптека]\\Приказ.docx", "[Аптека]\\Второй.docx"],
            "SOURCE_NUMBER_DUPLICATE",
        ),
        (
            [_row(source_number="1"), _row(source_number="2")],
            ["[Аптека]\\Приказ.docx"],
            "RELATIVE_PATH_DUPLICATE",
        ),
    ],
)
def test_duplicate_identifiers_are_errors(
    tmp_path: Path,
    rows: list[dict[str, object]],
    files: list[str],
    expected_code: str,
) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    for relative_path in files:
        _create_file(archive_root, relative_path)
    xlsx = tmp_path / "manifest.xlsx"
    _write_manifest(xlsx, rows)

    report = run_dry_run(xlsx_path=xlsx, archive_root=archive_root)

    assert report.outcome == "FAIL"
    assert expected_code in _issue_codes(report)


@pytest.mark.parametrize(
    ("row", "expected_code"),
    [
        (
            _row(file_name="outside.docx", relative_path="C:\\outside.docx", archive_section="C:"),
            "PATH_ABSOLUTE",
        ),
        (
            _row(file_name="outside.docx", relative_path="..\\outside.docx", archive_section=".."),
            "PATH_PARENT_ESCAPE",
        ),
        (_row(), "FILE_NOT_FOUND"),
        (
            _row(file_name="Приказ.txt", relative_path="[Аптека]\\Приказ.txt"),
            "EXTENSION_NOT_ALLOWED",
        ),
        (
            _row(file_name="Другое.docx", relative_path="[Аптека]\\Приказ.docx"),
            "FILE_NAME_MISMATCH",
        ),
        (_row(archive_section="[Экономисты]"), "ARCHIVE_SECTION_MISMATCH"),
    ],
)
def test_row_validation_errors(
    tmp_path: Path,
    row: dict[str, object],
    expected_code: str,
) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    relative_path = str(row["Относительный путь к файлу"])
    if expected_code in {"EXTENSION_NOT_ALLOWED", "FILE_NAME_MISMATCH", "ARCHIVE_SECTION_MISMATCH"}:
        _create_file(archive_root, relative_path)
    xlsx = tmp_path / "manifest.xlsx"
    _write_manifest(xlsx, [row])

    report = run_dry_run(xlsx_path=xlsx, archive_root=archive_root)

    assert report.outcome == "FAIL"
    assert expected_code in _issue_codes(report)


def test_resolved_path_containment_check(tmp_path: Path) -> None:
    archive_root = (tmp_path / "archive").resolve()
    archive_root.mkdir()
    assert _is_within_root(archive_root / "inside.docx", archive_root)
    assert not _is_within_root(tmp_path.resolve() / "outside.docx", archive_root)
    if os.name == "nt":
        assert _is_within_root(Path(str(archive_root / "inside.docx").swapcase()), archive_root)
        assert not _is_within_root(Path("Z:\\outside.docx"), archive_root)


def test_symlink_outside_archive_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _create_file(outside, "Приказ.docx")
    link = archive_root / "[Аптека]"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        candidate = archive_root / "[Аптека]" / "Приказ.docx"
        resolved_target = (outside / "Приказ.docx").resolve()
        original_resolve = Path.resolve

        def resolve_link(path: Path, strict: bool = False) -> Path:
            if path == candidate:
                return resolved_target
            return original_resolve(path, strict=strict)

        monkeypatch.setattr(Path, "resolve", resolve_link)
    xlsx = tmp_path / "manifest.xlsx"
    _write_manifest(xlsx, [_row()])

    report = run_dry_run(xlsx_path=xlsx, archive_root=archive_root)

    assert report.outcome == "FAIL"
    assert "PATH_OUTSIDE_ARCHIVE_ROOT" in _issue_codes(report)


def test_symlink_alias_must_match_physical_filename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    section = archive_root / "[Аптека]"
    target = _create_file(archive_root, "[Аптека]\\Настоящий.docx")
    alias = section / "Приказ.docx"
    try:
        alias.symlink_to(target)
    except OSError:
        resolved_target = target.resolve()
        original_resolve = Path.resolve

        def resolve_link(path: Path, strict: bool = False) -> Path:
            if path == alias:
                return resolved_target
            return original_resolve(path, strict=strict)

        monkeypatch.setattr(Path, "resolve", resolve_link)
    xlsx = tmp_path / "manifest.xlsx"
    _write_manifest(xlsx, [_row()])

    report = run_dry_run(xlsx_path=xlsx, archive_root=archive_root)

    assert report.outcome == "FAIL"
    assert "PHYSICAL_FILE_NAME_MISMATCH" in _issue_codes(report)


def test_duplicate_sha256_is_warning_only(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    first = _row()
    second = _row(
        source_number="2",
        file_name="Копия.docx",
        relative_path="[Экономисты]\\Копия.docx",
        archive_section="[Экономисты]",
    )
    _create_file(archive_root, str(first["Относительный путь к файлу"]), b"same")
    _create_file(archive_root, str(second["Относительный путь к файлу"]), b"same")
    xlsx = tmp_path / "manifest.xlsx"
    _write_manifest(xlsx, [first, second])

    report = run_dry_run(xlsx_path=xlsx, archive_root=archive_root)

    assert report.outcome == "PASS"
    assert len(report.summary.duplicate_sha256) == 1
    assert [warning.code for warning in report.warnings] == ["DUPLICATE_SHA256"]


def test_expected_rows_mismatch_is_failure(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    row = _row()
    _create_file(archive_root, str(row["Относительный путь к файлу"]))
    xlsx = tmp_path / "manifest.xlsx"
    _write_manifest(xlsx, [row])

    report = run_dry_run(xlsx_path=xlsx, archive_root=archive_root, expected_rows=2)

    assert report.outcome == "FAIL"
    assert "EXPECTED_ROWS_MISMATCH" in _issue_codes(report)


def test_excel_date_value_and_unformatted_serial_are_not_confused(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    dated = _row(order_date=datetime(2026, 2, 1))
    serial = _row(
        source_number="2",
        file_name="Серийная.docx",
        relative_path="[Аптека]\\Серийная.docx",
        order_date=46054,
    )
    _create_file(archive_root, str(dated["Относительный путь к файлу"]))
    _create_file(archive_root, str(serial["Относительный путь к файлу"]))
    xlsx = tmp_path / "manifest.xlsx"
    _write_manifest(xlsx, [dated, serial])

    report = run_dry_run(xlsx_path=xlsx, archive_root=archive_root)

    assert report.rows[0].parsed_order_date == date(2026, 2, 1)
    assert report.rows[1].parsed_order_date is None
    assert "ORDER_DATE_INVALID" in {issue.code for issue in report.rows[1].issues}


def test_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    row = _row()
    _create_file(archive_root, str(row["Относительный путь к файлу"]))
    xlsx = tmp_path / "manifest.xlsx"
    _write_manifest(xlsx, [row])
    common = ["--xlsx", str(xlsx), "--archive-root", str(archive_root)]

    assert cli_main([*common, "--expected-rows", "1"]) == 0
    assert "Result: PASS" in capsys.readouterr().out
    assert cli_main([*common, "--expected-rows", "2"]) == 1
    assert "Result: FAIL" in capsys.readouterr().out
    assert cli_main(["--xlsx", str(tmp_path / "missing.xlsx"), "--archive-root", str(archive_root)]) == 2
    assert "XLSX_NOT_FOUND" in capsys.readouterr().err


def test_json_report_matches_summary_and_cannot_modify_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()
    row = _row()
    _create_file(archive_root, str(row["Относительный путь к файлу"]))
    xlsx = tmp_path / "manifest.xlsx"
    _write_manifest(xlsx, [row])
    original_xlsx = xlsx.read_bytes()
    json_out = tmp_path / "report.json"
    common = ["--xlsx", str(xlsx), "--archive-root", str(archive_root)]

    assert cli_main([*common, "--json-out", str(json_out)]) == 0
    console = capsys.readouterr().out
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["outcome"] == "PASS"
    assert payload["summary"]["total_rows"] == 1
    assert payload["summary"]["valid_rows"] == 1
    assert "Rows: 1" in console
    assert "Valid rows: 1" in console
    assert "Result: PASS" in console

    existing_json = tmp_path / "existing.json"
    existing_json.write_text("keep", encoding="utf-8")
    assert cli_main([*common, "--json-out", str(existing_json)]) == 2
    assert "JSON_OUTPUT_EXISTS" in capsys.readouterr().err
    assert existing_json.read_text(encoding="utf-8") == "keep"

    assert cli_main([*common, "--json-out", str(xlsx)]) == 2
    assert "JSON_OUTPUT_CONFLICT" in capsys.readouterr().err
    assert xlsx.read_bytes() == original_xlsx
    archive_json = archive_root / "report.json"
    assert cli_main([*common, "--json-out", str(archive_json)]) == 2
    assert "JSON_OUTPUT_CONFLICT" in capsys.readouterr().err
    assert not archive_json.exists()


def test_importer_has_no_database_write_dependency() -> None:
    module_dir = Path(__file__).parents[2] / "app" / "operational_orders" / "archive_import"
    cli = Path(__file__).parents[2] / "scripts" / "dry_run_operational_orders_archive_import.py"
    source = "\n".join(path.read_text(encoding="utf-8") for path in module_dir.glob("*.py"))
    source += cli.read_text(encoding="utf-8")

    forbidden = (
        "app.db",
        "sqlalchemy",
        "session.commit",
        "session.add",
        "engine.begin",
        "create_workspace",
        "promote_workspace",
        "signing_service",
    )
    assert all(token not in source for token in forbidden)
