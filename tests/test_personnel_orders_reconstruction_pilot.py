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
