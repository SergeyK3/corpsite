"""Safety contract for the narrowly scoped reconstruction pilot CLI."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from contextlib import AbstractContextManager
from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text

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

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _Engine:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        return self.conn

    def begin(self):  # pragma: no cover - a dry run must not select this path
        raise AssertionError("dry run must not open a write transaction")


def test_direct_script_bootstrap_exposes_app_services(tmp_path):
    code = (
        "import runpy; "
        f"runpy.run_path({str(SCRIPT)!r}, run_name='pilot_test'); "
        "import app.services.personnel_orders_editorial_service"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, text=True, capture_output=True, check=False,
        env={**os.environ, "DATABASE_URL": "postgresql://user:pass@localhost/corpsite_test"},
    )
    assert completed.returncode == 0, completed.stderr


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


def test_strict_source_initials_never_auto_match_a_surname_only_source(monkeypatch):
    monkeypatch.setattr(pilot, "REQUIRE_SOURCE_INITIALS", True)

    match = pilot.match_people(
        ["Ivanov"],
        [{"employee_id": 10, "full_name": "Ivanov Ivan Ivanovich"}],
    )[0]

    assert match["employee_id"] is None
    assert match["match_status"] == "UNRESOLVED"


def test_supplementary_pay_titles_are_classified_but_unrelated_payments_are_not():
    assert pilot.title_type("Қосымша ақы туралы") == "SUPPLEMENTARY_PAY"
    assert pilot.title_type("Қосымша ақы төлеу туралы") == "SUPPLEMENTARY_PAY"
    assert pilot.title_type("Жұмысқа қосымша ақы туралы") == "SUPPLEMENTARY_PAY"
    assert pilot.title_type("Қосымша ақыны алып тастау туралы") is None
    assert pilot.title_type("Сыйлықақы төлеу туралы") is None
    assert pilot.template_key_for("SUPPLEMENTARY_PAY") == "personnel.supplementary-pay.review"


def test_supplementary_pay_unresolved_preserves_source_name_without_employee_id():
    match = pilot.match_people(["Missing M."], [])[0]
    assert match == {
        "source_name": "Missing M.", "employee_id": None,
        "match_status": "UNRESOLVED", "candidate_ids": [], "employee": None,
    }


def test_supplementary_pay_duplicate_check_uses_its_own_item_type_code():
    class _Rows:
        def __init__(self, rows): self.rows = rows
        def all(self): return self.rows
        def scalars(self): return self
        def mappings(self): return self.rows

    class _DuplicateConnection:
        def __init__(self): self.params = []
        def execute(self, _statement, params):
            self.params.append(params)
            if "employee_id" in params:
                return _Rows([{"order_id": 77, "order_number": "77-ж"}])
            return _Rows([])

    candidate = {"source_identifier": "source.xlsx|Лист1|1", "order_number": "1-ж",
                 "order_date": date(2026, 1, 1), "action": "SUPPLEMENTARY_PAY",
                 "matches": [{"employee_id": 33}]}
    conn = _DuplicateConnection()
    result = pilot.duplicate_check(conn, [candidate])

    assert result[0]["blocking_duplicates"]["employee_and_action"] == [77]
    assert {params.get("action") for params in conn.params if "action" in params} == {"SUPPLEMENTARY_PAY"}


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
            "pdf": "",
            "pdf_page": "",
            "source_title": "",
            "figures": "",
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


def test_legacy_technical_employee_action_match_does_not_block_apply():
    blocking, legacy = pilot.classify_employee_action_matches([
        {"order_id": 125, "order_number": "PERSONNEL-IMPORT-2026-211"},
        {"order_id": 253, "order_number": "CSV-PILOT-2026-419"},
    ])

    finding = {
        "source_identifier": "source|Лист1|264",
        "blocking_duplicates": {
            "order_number_and_date": [], "source_excel_row": [], "employee_and_action": blocking,
        },
        "legacy_technical_matches": legacy,
    }

    assert not pilot.has_blocking_duplicates(finding)
    assert finding["legacy_technical_matches"] == [125, 253]


def test_regular_employee_action_number_date_and_source_matches_block_apply():
    blocking, legacy = pilot.classify_employee_action_matches([
        {"order_id": 99, "order_number": "27-ж"},
    ])
    assert blocking == [99]
    assert not legacy
    for blocking_duplicates in (
        {"order_number_and_date": [], "source_excel_row": [], "employee_and_action": [99]},
        {"order_number_and_date": [98], "source_excel_row": [], "employee_and_action": []},
        {"order_number_and_date": [], "source_excel_row": [97], "employee_and_action": []},
    ):
        assert pilot.has_blocking_duplicates({
            "source_identifier": "source|Лист1|264",
            "blocking_duplicates": blocking_duplicates,
            "legacy_technical_matches": [],
        })


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
    monkeypatch.setattr(pilot, "duplicate_check", lambda _conn, rows: [{
        "source_identifier": row["source_identifier"],
        "blocking_duplicates": {
            "order_number_and_date": [], "source_excel_row": [], "employee_and_action": [],
        },
        "legacy_technical_matches": [125] if row["excel_row"] == 1 else [],
    } for row in rows])
    monkeypatch.setattr(pilot, "find_docx", lambda *_args: None)

    result = pilot.run("postgresql://unused", dry_run=False)

    statements = "\n".join(conn.sql).lower()
    assert len(result["orders"]) == 20
    assert "'draft'" in statements
    assert "personnel_events" not in statements
    assert "insert into public.assignments" not in statements
    stored_orders = [json.loads(params["storage"]) for params in conn.params if "storage" in params]
    assert all(order["employee_match_review_required"] for order in stored_orders)
    assert stored_orders[0]["reconstruction"]["legacy_technical_order_ids"] == [125]


def test_apply_supplementary_pay_creates_no_events_assignments_or_invented_fields(monkeypatch):
    conn = _WriteConnection()
    selected = [{
        "excel_row": row, "source_identifier": f"source|Лист1|supp-{row}",
        "pdf": "", "pdf_page": "", "order_number": f"supp-{row}-ж",
        "order_date": date(2026, 7, 22), "source_title": "Қосымша ақы туралы",
        "figures": "Missing M.", "source_note": "", "action": "SUPPLEMENTARY_PAY",
        "matches": [{"source_name": "Missing M.", "employee_id": None,
                     "match_status": "UNRESOLVED", "candidate_ids": [], "employee": None}],
    } for row in range(1, 21)]
    monkeypatch.setattr(pilot, "create_engine", lambda _url: _WriteEngine(conn))
    monkeypatch.setattr(pilot, "load_candidates", lambda _conn, _manifest: (selected, []))
    monkeypatch.setattr(pilot, "duplicate_check", lambda _conn, rows: [{
        "source_identifier": row["source_identifier"],
        "blocking_duplicates": {"order_number": [], "order_number_and_date": [], "source_excel_row": [], "employee_and_action": []},
        "legacy_technical_matches": [],
    } for row in rows])
    monkeypatch.setattr(pilot, "find_docx", lambda *_args: None)

    pilot.run("postgresql://unused", dry_run=False)

    statements = "\n".join(conn.sql).lower()
    item_params = [params for params in conn.params if "item_number" in params]
    payload = json.loads(item_params[0]["payload"])
    storage = next(json.loads(params["storage"]) for params in conn.params if "storage" in params)
    assert "personnel_events" not in statements
    assert "insert into public.assignments" not in statements
    assert item_params[0]["effective_date"] is None
    assert payload["source_employee_name"] == "Missing M."
    assert payload["employee_match_status"] == "UNRESOLVED"
    assert "assignment" not in payload and "rate" not in payload and "basis_ids" not in payload
    assert storage["basis_documents"] == []
    assert storage["auto_filled_fields"] == []


def test_apply_keeps_one_multi_person_order_with_sequential_items(monkeypatch):
    conn = _WriteConnection()
    matches = [
        {"source_name": "Auto A.", "employee_id": 7, "match_status": "AUTO_MATCH", "candidate_ids": [7],
         "employee": {"employee_id": 7, "full_name": "Auto Anna", "unit_name": "Unit A", "position_name": "Position A"}},
        {"source_name": "Ambiguous B.", "employee_id": None, "match_status": "AMBIGUOUS", "candidate_ids": [8, 9], "employee": None},
        {"source_name": "Unresolved C.", "employee_id": None, "match_status": "UNRESOLVED", "candidate_ids": [], "employee": None},
    ]
    selected = [{
        "excel_row": row, "source_identifier": f"source|Лист1|{row}", "pdf": "", "pdf_page": "",
        "order_number": f"{row}-ж", "order_date": date(2026, 7, 22), "source_title": "", "figures": "",
        "source_note": "", "action": "HIRE", "matches": matches,
    } for row in range(1, 21)]
    monkeypatch.setattr(pilot, "create_engine", lambda _url: _WriteEngine(conn))
    monkeypatch.setattr(pilot, "load_candidates", lambda _conn, _manifest: (selected, []))
    monkeypatch.setattr(pilot, "duplicate_check", lambda _conn, rows: [{"source_identifier": row["source_identifier"], "blocking_duplicates": {"order_number_and_date": [], "source_excel_row": [], "employee_and_action": []}, "legacy_technical_matches": []} for row in rows])
    monkeypatch.setattr(pilot, "find_docx", lambda *_args: None)
    pilot.run("postgresql://unused", dry_run=False)
    item_params = [params for params in conn.params if "item_number" in params]
    assert [params["item_number"] for params in item_params[:3]] == [1, 2, 3]
    assert [params["employee_id"] for params in item_params[:3]] == [7, None, None]
    payloads = [json.loads(params["payload"]) for params in item_params[:3]]
    assert [payload["source_employee_name"] for payload in payloads] == ["Auto A.", "Ambiguous B.", "Unresolved C."]
    assert [payload["employee_match_status"] for payload in payloads] == ["AUTO_MATCH", "AMBIGUOUS", "UNRESOLVED"]


def test_docx_matcher_rejects_collection_but_accepts_individual_file(monkeypatch, tmp_path):
    collection = tmp_path / "Приказы 2025-2026 на отпуск.docx"
    individual = tmp_path / "Приказ 891-ж 16.04.2026.docx"
    monkeypatch.setattr(pilot, "docx_index", lambda: ((collection, "891 16.04.2026"),))
    assert pilot.find_docx("891", date(2026, 4, 16)) is None
    monkeypatch.setattr(pilot, "docx_index", lambda: ((individual, ""),))
    assert pilot.find_docx("891", date(2026, 4, 16)) == str(individual)


class _ResumeResult:
    def __init__(self, *, rows=None, scalar=None):
        self.rows = rows or []
        self.scalar = scalar

    def mappings(self):
        return self.rows

    def scalar_one(self):
        return self.scalar


class _ResumeConnection(AbstractContextManager):
    def __init__(self, rows, *, scopes, locales):
        self.rows = rows
        self.scopes = scopes
        self.locales = locales
        self.sql: list[str] = []

    def execute(self, statement, _params=None):
        sql = str(statement)
        self.sql.append(sql)
        if "FROM public.personnel_orders" in sql and "source_identifiers" in str(_params):
            return _ResumeResult(rows=self.rows)
        if "FROM public.personnel_order_evidence_scopes" in sql and "COUNT(*)" in sql:
            return _ResumeResult(scalar=self.scopes)
        if "FROM public.personnel_order_localized_texts" in sql:
            return _ResumeResult(scalar=self.locales)
        return _ResumeResult()

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _ResumeEngine:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        return self.conn

    def begin(self):
        return self.conn


def _manifest_and_existing_rows(count=20):
    manifest = {}
    rows = []
    for number in range(1, count + 1):
        source = f"source.xlsx|Лист1|{number}"
        manifest[source] = {
            "source_identifier": source, "excel_row": number,
            "order_number": f"{number}-ж", "order_date": "2026-01-01",
            "template_key": "personnel.hire.standard",
        }
        rows.append({
            "order_id": 399 + number, "order_number": f"{number}-ж",
            "order_date": date(2026, 1, 1), "order_type_code": "HIRE",
            "storage_json": {"source_identifier": source, "employee_matches": [], "reconstruction": {}},
        })
    return manifest, rows


def test_full_manifest_resume_creates_no_new_orders_and_second_run_is_noop(monkeypatch):
    manifest, rows = _manifest_and_existing_rows()
    first = _ResumeConnection(rows, scopes=0, locales=0)
    monkeypatch.setattr(pilot, "create_engine", lambda _url: _ResumeEngine(first))
    monkeypatch.setattr(pilot, "load_manifest", lambda _path: manifest)
    monkeypatch.setattr(pilot, "find_docx", lambda *_args: None)

    resumed = pilot.run("postgresql://unused", dry_run=False, manifest_path=Path("manifest.json"))

    assert resumed["resumed"] is True
    assert resumed["needs_presentation_repair"] is True
    assert "INSERT INTO public.personnel_orders" not in "\n".join(first.sql)
    assert any("INSERT INTO public.personnel_order_evidence_scopes" in sql for sql in first.sql)

    second = _ResumeConnection(rows, scopes=20, locales=40)
    monkeypatch.setattr(pilot, "create_engine", lambda _url: _ResumeEngine(second))
    noop = pilot.run("postgresql://unused", dry_run=False, manifest_path=Path("manifest.json"))
    assert noop["rerun_noop"] is True
    assert not any("INSERT" in sql.upper() for sql in second.sql)


def test_partial_manifest_state_is_blocked(monkeypatch):
    manifest, rows = _manifest_and_existing_rows()
    conn = _ResumeConnection(rows[:1], scopes=0, locales=0)
    monkeypatch.setattr(pilot, "create_engine", lambda _url: _ResumeEngine(conn))
    monkeypatch.setattr(pilot, "load_manifest", lambda _path: manifest)

    try:
        pilot.run("postgresql://unused", dry_run=False, manifest_path=Path("manifest.json"))
    except RuntimeError as exc:
        assert "PARTIAL_PILOT_STATE: found 1 of 20" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("partial pilot state was allowed")


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


def test_manifest_allows_a_pinned_batch_larger_than_the_legacy_twenty(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "orders": [{
            "source_identifier": f"source.xlsx|Лист1|{number}",
            "excel_row": number,
        } for number in range(1, 101)],
    }), encoding="utf-8")

    loaded = pilot.load_manifest(manifest)

    assert loaded is not None
    assert len(loaded) == 100


def _atomic_apply_candidate(key: str) -> tuple[dict, dict]:
    source = f"pytest-reconstruction.xlsx|Лист1|{uuid4().hex[:8]}"
    candidate = {
        "excel_row": 1,
        "source_identifier": source,
        "pdf": "",
        "pdf_page": "",
        "order_number": f"PYTEST-{uuid4().hex[:10]}-ж",
        "order_date": date(2026, 1, 1),
        "source_title": "Жұмысқа қабылдау туралы",
        "figures": "Missing M.",
        "source_note": "",
        "action": "HIRE",
        "matches": [{
            "source_name": "Missing M.", "employee_id": None,
            "match_status": "UNRESOLVED", "candidate_ids": [], "employee": None,
        }],
    }
    manifest = {
        source: {
            "source_identifier": source,
            "excel_row": 1,
            "order_number": candidate["order_number"],
            "order_date": "2026-01-01",
            "template_key": "personnel.hire.standard",
        }
    }
    return candidate, manifest


def _atomic_counts(database_url: str, key: str) -> dict[str, int]:
    engine = create_engine(database_url)
    with engine.connect() as conn:
        return dict(conn.execute(text("""
            SELECT
                (SELECT count(*) FROM public.personnel_orders po
                 WHERE po.storage_json ->> 'reconstruction_pilot' = :key) AS headers,
                (SELECT count(*) FROM public.personnel_order_items poi
                 JOIN public.personnel_orders po ON po.order_id = poi.order_id
                 WHERE po.storage_json ->> 'reconstruction_pilot' = :key) AS items,
                (SELECT count(*) FROM public.personnel_order_evidence_scopes scope
                 JOIN public.personnel_orders po ON po.order_id = scope.order_id
                 WHERE po.storage_json ->> 'reconstruction_pilot' = :key) AS scopes,
                (SELECT count(*) FROM public.personnel_order_editorial_blocks block
                 JOIN public.personnel_orders po ON po.order_id = block.order_id
                 WHERE po.storage_json ->> 'reconstruction_pilot' = :key) AS order_blocks,
                (SELECT count(*) FROM public.personnel_order_item_editorial_blocks block
                 JOIN public.personnel_order_items poi ON poi.item_id = block.order_item_id
                 JOIN public.personnel_orders po ON po.order_id = poi.order_id
                 WHERE po.storage_json ->> 'reconstruction_pilot' = :key) AS item_blocks,
                (SELECT count(*) FROM public.personnel_order_localized_texts localized
                 JOIN public.personnel_orders po ON po.order_id = localized.order_id
                 WHERE po.storage_json ->> 'reconstruction_pilot' = :key) AS localized
        """), {"key": key}).mappings().one())


def _delete_atomic_batch(database_url: str, key: str) -> None:
    engine = create_engine(database_url)
    with engine.begin() as conn:
        item_ids = conn.execute(text("""
            SELECT poi.item_id
            FROM public.personnel_order_items poi
            JOIN public.personnel_orders po ON po.order_id = poi.order_id
            WHERE po.storage_json ->> 'reconstruction_pilot' = :key
        """), {"key": key}).scalars().all()
        order_ids = conn.execute(text("""
            SELECT order_id FROM public.personnel_orders
            WHERE storage_json ->> 'reconstruction_pilot' = :key
        """), {"key": key}).scalars().all()
        if item_ids:
            conn.execute(text("DELETE FROM public.personnel_order_item_editorial_blocks WHERE order_item_id = ANY(:ids)"), {"ids": item_ids})
            conn.execute(text("DELETE FROM public.personnel_order_item_bases WHERE order_item_id = ANY(:ids)"), {"ids": item_ids})
        if order_ids:
            conn.execute(text("DELETE FROM public.personnel_order_editorial_blocks WHERE order_id = ANY(:ids)"), {"ids": order_ids})
            conn.execute(text("DELETE FROM public.personnel_order_localized_texts WHERE order_id = ANY(:ids)"), {"ids": order_ids})
            conn.execute(text("DELETE FROM public.personnel_order_evidence_scopes WHERE order_id = ANY(:ids)"), {"ids": order_ids})
            conn.execute(text("DELETE FROM public.personnel_order_items WHERE order_id = ANY(:ids)"), {"ids": order_ids})
        conn.execute(text("""
            DELETE FROM public.personnel_orders
            WHERE storage_json ->> 'reconstruction_pilot' = :key
        """), {"key": key})


def test_atomic_apply_creates_complete_presentation_set_and_is_idempotent(monkeypatch):
    database_url = os.environ["TEST_DATABASE_URL"]
    key = f"pytest-atomic-reconstruction-{uuid4().hex}"
    candidate, manifest = _atomic_apply_candidate(key)
    monkeypatch.setattr(pilot, "PILOT", key)
    monkeypatch.setattr(pilot, "load_manifest", lambda _path: manifest)
    monkeypatch.setattr(pilot, "load_candidates", lambda _conn, _manifest: ([candidate], []))
    monkeypatch.setattr(pilot, "duplicate_check", lambda _conn, _rows: [{
        "source_identifier": candidate["source_identifier"],
        "blocking_duplicates": {"order_number": [], "order_number_and_date": [], "source_excel_row": [], "employee_and_action": []},
        "legacy_technical_matches": [],
    }])
    monkeypatch.setattr(pilot, "find_docx", lambda *_args: None)

    try:
        result = pilot.apply_with_presentations(database_url, manifest_path=Path("manifest.json"))
        assert len(result["orders"]) == 1
        assert _atomic_counts(database_url, key) == {
            "headers": 1, "items": 1, "scopes": 1,
            "order_blocks": 6, "item_blocks": 4, "localized": 2,
        }

        second = pilot.apply_with_presentations(database_url, manifest_path=Path("manifest.json"))
        assert second["rerun_noop"] is True
        assert _atomic_counts(database_url, key)["headers"] == 1
        assert _atomic_counts(database_url, key)["items"] == 1
    finally:
        _delete_atomic_batch(database_url, key)


def test_atomic_apply_rolls_back_headers_items_scopes_and_presentations_on_failure(monkeypatch):
    database_url = os.environ["TEST_DATABASE_URL"]
    key = f"pytest-atomic-rollback-{uuid4().hex}"
    candidate, manifest = _atomic_apply_candidate(key)
    monkeypatch.setattr(pilot, "PILOT", key)
    monkeypatch.setattr(pilot, "load_manifest", lambda _path: manifest)
    monkeypatch.setattr(pilot, "load_candidates", lambda _conn, _manifest: ([candidate], []))
    monkeypatch.setattr(pilot, "duplicate_check", lambda _conn, _rows: [{
        "source_identifier": candidate["source_identifier"],
        "blocking_duplicates": {"order_number": [], "order_number_and_date": [], "source_excel_row": [], "employee_and_action": []},
        "legacy_technical_matches": [],
    }])
    monkeypatch.setattr(pilot, "find_docx", lambda *_args: None)
    monkeypatch.setattr(pilot, "ensure_bilingual_presentations", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("presentation failure")))

    try:
        try:
            pilot.apply_with_presentations(database_url, manifest_path=Path("manifest.json"))
        except RuntimeError as exc:
            assert str(exc) == "presentation failure"
        else:  # pragma: no cover
            raise AssertionError("presentation failure was committed")
        assert _atomic_counts(database_url, key) == {
            "headers": 0, "items": 0, "scopes": 0,
            "order_blocks": 0, "item_blocks": 0, "localized": 0,
        }
    finally:
        _delete_atomic_batch(database_url, key)
