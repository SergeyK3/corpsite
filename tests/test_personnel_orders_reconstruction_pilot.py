"""Safety contract for the narrowly scoped reconstruction pilot CLI."""
from __future__ import annotations

import importlib.util
import json
from contextlib import AbstractContextManager
from datetime import date
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "tools/order_preparation/run_personnel_orders_reconstruction_pilot.py"
SPEC = importlib.util.spec_from_file_location("reconstruction_pilot", SCRIPT)
assert SPEC and SPEC.loader
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class _Scalar:
    def scalar_one(self):
        return 0


class _Connection(AbstractContextManager):
    def __init__(self):
        self.sql: list[str] = []

    def execute(self, statement, _params=None):
        self.sql.append(str(statement))
        return _Scalar()


class _Engine:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        return self.conn

    def begin(self):  # pragma: no cover - a dry run must not select this path
        raise AssertionError("dry run must not open a write transaction")


def test_match_people_marks_unique_ambiguous_and_unresolved():
    employees = [
        {"employee_id": 10, "full_name": "Ivanov Ivan Ivanovich"},
        {"employee_id": 20, "full_name": "Petrov Petr Petrovich"},
        {"employee_id": 21, "full_name": "Petrov Pavel Petrovich"},
    ]

    unique = pilot.match_people(["Ivanov I.I."], employees)[0]
    ambiguous = pilot.match_people(["Petrov"], employees)[0]
    unresolved = pilot.match_people(["Missing M."], employees)[0]

    assert unique == {
        "source_name": "Ivanov I.I.", "employee_id": 10,
        "match_status": "AUTO_MATCH", "candidate_ids": [10], "employee": employees[0],
    }
    assert ambiguous["employee_id"] is None
    assert ambiguous["match_status"] == "AMBIGUOUS"
    assert ambiguous["candidate_ids"] == [20, 21]
    assert ambiguous["employee"] is None
    assert unresolved == {
        "source_name": "Missing M.", "employee_id": None,
        "match_status": "UNRESOLVED", "candidate_ids": [], "employee": None,
    }


class _CandidateResult:
    def __init__(self, values):
        self.values = values

    def mappings(self):
        return self.values

    def scalars(self):
        return self.values


class _CandidateConnection:
    def __init__(self):
        self.calls = 0

    def execute(self, *_args, **_kwargs):
        self.calls += 1
        return _CandidateResult([])


def test_manifest_rows_are_retained_when_people_are_unresolved(monkeypatch):
    class _Sheet:
        def iter_rows(self, **_kwargs):
            for number in range(20):
                yield ("", "", str(number), "title", date(2026, 1, 1), "", "Missing M.", "")

    class _Workbook:
        def __getitem__(self, _sheet):
            return _Sheet()

    monkeypatch.setattr(pilot, "load_workbook", lambda *_args, **_kwargs: _Workbook())
    monkeypatch.setattr(pilot, "title_type", lambda _title: "HIRE")
    manifest = {
        pilot.source_key(row): {
            "source_identifier": pilot.source_key(row),
            "order_number": f"{row - 2}-ж",
            "order_date": "2026-01-01",
            "template_key": pilot.template_key_for("HIRE"),
        }
        for row in range(2, 22)
    }

    selected, skipped = pilot.load_candidates(_CandidateConnection(), manifest)

    assert len(selected) == 20
    assert not skipped
    assert {match["match_status"] for row in selected for match in row["matches"]} == {"UNRESOLVED"}
    assert all(match["employee_id"] is None for row in selected for match in row["matches"])


def test_dry_run_uses_read_connection_and_never_emits_insert(monkeypatch):
    conn = _Connection()
    selected = [{
        "excel_row": 113,
        "source_identifier": "Ручное распознавание журналов.xlsx|Лист1|113",
        "order_number": "1262-ж",
        "order_date": date(2026, 7, 22),
        "action": "TERMINATION",
        "matches": [],
    } for _ in range(20)]
    # Each source identifier must be distinct for a valid real manifest.
    for number, row in enumerate(selected, start=113):
        row["excel_row"] = number
        row["source_identifier"] = f"Ручное распознавание журналов.xlsx|Лист1|{number}"

    monkeypatch.setattr(pilot, "create_engine", lambda _url: _Engine(conn))
    monkeypatch.setattr(pilot, "load_candidates", lambda _conn, _manifest: (selected, []))
    monkeypatch.setattr(pilot, "duplicate_check", lambda _conn, _rows: [])
    monkeypatch.setattr(pilot, "find_docx", lambda *_args: None)

    result = pilot.run("postgresql://unused", dry_run=True)

    assert len(result["orders"]) == 20
    assert result["orders"][0]["template_key"] == "personnel.termination.employee-initiative-unused-leave"
    assert all("INSERT" not in sql.upper() for sql in conn.sql)


class _WriteResult:
    def __init__(self, sql):
        self.sql = sql

    def scalar_one(self):
        if "COUNT(*)" in self.sql:
            return 0
        if "SELECT user_id" in self.sql:
            return 1
        if "RETURNING order_id" in self.sql:
            return 100
        raise AssertionError(f"unexpected scalar query: {self.sql}")


class _WriteConnection(_Connection):
    def __init__(self):
        super().__init__()
        self.params: list[dict] = []

    def execute(self, statement, _params=None):
        sql = str(statement)
        self.sql.append(sql)
        self.params.append(_params or {})
        return _WriteResult(sql)


class _WriteEngine(_Engine):
    def begin(self):
        return self.conn


def test_apply_creates_only_draft_order_rows_not_events_or_assignments(monkeypatch):
    conn = _WriteConnection()
    selected = [{
        "excel_row": row, "source_identifier": f"source|Лист1|{row}",
        "pdf": "", "pdf_page": "", "order_number": f"{row}-ж",
        "order_date": date(2026, 7, 22), "source_title": "", "figures": "Missing M.",
        "source_note": "", "action": "TERMINATION",
        "matches": [{"source_name": "Missing M.", "employee_id": None,
                     "match_status": "UNRESOLVED", "candidate_ids": [], "employee": None}],
    } for row in range(1, 21)]
    monkeypatch.setattr(pilot, "create_engine", lambda _url: _WriteEngine(conn))
    monkeypatch.setattr(pilot, "load_candidates", lambda _conn, _manifest: (selected, []))
    monkeypatch.setattr(pilot, "duplicate_check", lambda _conn, _rows: [])
    monkeypatch.setattr(pilot, "find_docx", lambda *_args: None)

    result = pilot.run("postgresql://unused", dry_run=False)

    statements = "\n".join(conn.sql).lower()
    assert len(result["orders"]) == 20
    assert "'draft'" in statements
    assert "personnel_events" not in statements
    assert "insert into public.assignments" not in statements
    stored_orders = [json.loads(params["storage"]) for params in conn.params if "storage" in params]
    assert all(order["employee_match_review_required"] for order in stored_orders)


def test_cli_exposes_portable_sources_and_pinned_manifest():
    source = SCRIPT.read_text(encoding="utf-8")
    for option in ("--source-file", "--sheet", "--docx-root", "--archive", "--manifest"):
        assert option in source
    assert "JOIN public.personnel_order_items" in source
    assert "storage_json ->> 'source_identifier'" in source


def test_manifest_verification_rejects_changed_excel(tmp_path):
    excel = tmp_path / "Ручное распознавание журналов.xlsx"
    excel.write_bytes(b"original")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "source_excel": {"path": excel.name, "sha256": pilot.sha256(excel)},
        "docx_files": [],
        "orders": [],
    }), encoding="utf-8")

    pilot.verify_manifest_files(manifest, excel)
    excel.write_bytes(b"changed")

    try:
        pilot.verify_manifest_files(manifest, excel)
    except RuntimeError as exc:
        assert "SHA-256" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("tampered package was accepted")
