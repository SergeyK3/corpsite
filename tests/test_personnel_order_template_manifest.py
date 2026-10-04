from __future__ import annotations

import json
import os
import shutil
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text

from app.services.personnel_order_template_manifest import MANIFEST_FIELDS, MANIFEST_ROOT, TEXT_FIELDS, ManifestError, _manifest_bytes, _sync_plan, content_sha256, export_drafts, export_published, load_manifest, load_manifest_chains, manifest_path, sync_manifests, write_manifest
from app.services.personnel_order_template_specs import get_personnel_order_template_spec

TYPE = "TERMINATION"
TEST_URL = os.environ.get("TEST_DATABASE_URL", "")


def _texts() -> dict[str, str]: return dict(get_personnel_order_template_spec(TYPE).initial_texts)


class _Result:
    def __init__(self, row: dict[str, Any] | None = None) -> None: self.row = row
    def mappings(self) -> "_Result": return self
    def first(self) -> dict[str, Any] | None: return self.row


class _TemplateDb:
    """Transaction-aware SQL boundary double for the sync-only table."""
    def __init__(self, row: dict[str, Any] | None = None, *, fail_update: bool = False, fail_on_update: int | None = None) -> None:
        self.row, self.fail_update, self.fail_on_update, self.update_count, self.statements, self._snapshot = row, fail_update, fail_on_update, 0, [], None
    def connect(self) -> "_TemplateDb": return self
    def begin(self) -> "_TemplateDb": return self
    def __enter__(self) -> "_TemplateDb": self._snapshot = deepcopy(self.row); return self
    def __exit__(self, typ: object, *_: object) -> bool:
        if typ is not None: self.row = self._snapshot
        return False
    def execute(self, statement: object, values: dict[str, Any] | None = None) -> _Result:
        sql, values = str(statement), values or {}; self.statements.append(sql); compact = sql.lstrip().upper()
        if compact.startswith("SELECT"): return _Result(self.row)
        if compact.startswith("INSERT"):
            self.row = {"template_version_id": 800, "item_type_code": values["type"], "revision": 1, **{field: values[field] for field in TEXT_FIELDS}}
            return _Result(self.row)
        self.update_count += 1
        if self.fail_update or self.fail_on_update == self.update_count: raise RuntimeError("injected write failure")
        assert compact.startswith("UPDATE") and self.row is not None
        self.row.update({field: values[field] for field in TEXT_FIELDS}); self.row["revision"] += 1
        return _Result(self.row)


class _RealTransactionEngine:
    def __init__(self, connection: Any) -> None: self.connection = connection
    def begin(self): return nullcontext(self.connection)
    def connect(self): return nullcontext(self.connection)


def _pg_insert_template(conn: Any, code: str, version: int, status: str, values: dict[str, str]) -> int:
    return conn.execute(text("""INSERT INTO personnel_order_template_versions(item_type_code,version_number,status,title_ru,title_kk,preamble_ru,preamble_kk,body_template_ru,body_template_kk,basis_template_ru,basis_template_kk)
        VALUES(:type,:version,:status,:title_ru,:title_kk,:preamble_ru,:preamble_kk,:body_template_ru,:body_template_kk,:basis_template_ru,:basis_template_kk) RETURNING template_version_id"""), {**values, "type": code, "version": version, "status": status}).scalar_one()


def _write(tmp_path: Path, values: dict[str, str]) -> Path:
    assert write_manifest(TYPE, values, tmp_path) == "EXPORT"
    return manifest_path(TYPE, tmp_path)


def _chain(tmp_path: Path) -> tuple[dict[str, str], dict[str, str]]:
    v1 = _texts(); v1["title_ru"] += " v1"
    v2 = dict(v1); v2["preamble_ru"] += " редакция"
    assert write_manifest(TYPE, v1, tmp_path) == "EXPORT"
    assert write_manifest(TYPE, v2, tmp_path) == "EXPORT"
    return v1, v2


def test_canonical_export_is_stable_and_excludes_ids_and_personal_data(tmp_path: Path) -> None:
    path = _write(tmp_path, _texts()); first = path.read_bytes()
    assert write_manifest(TYPE, _texts(), tmp_path) == "NO_OP" and path.read_bytes() == first and b"\r\n" not in first
    decoded, manifest = first.decode("utf-8"), json.loads(first)
    assert "\\u" not in decoded and tuple(manifest) == MANIFEST_FIELDS
    assert not {"template_version_id", "user_id", "revision", "created_at", "updated_at", "password", "token"} & set(manifest)
    assert "Иванов" not in decoded and "IIN" not in decoded


def test_childcare_package_sync_is_type_scoped_and_never_publishes(tmp_path: Path) -> None:
    childcare = "LEAVE.CHILDCARE.GRANT"
    manifest = load_manifest(manifest_path(childcare))
    assert _sync_plan([manifest], {"status": "PUBLISHED", **{f: manifest[f] for f in TEXT_FIELDS}}) == ("NO_OP", [])
    write_manifest(childcare, {field: manifest[field] for field in TEXT_FIELDS}, tmp_path)
    _write(tmp_path, _texts())
    db = _TemplateDb()
    assert sync_manifests(apply=False, db_engine=db, root=tmp_path, item_type_code=childcare) == {childcare: "CREATE"}
    assert db.row is None
    assert sync_manifests(apply=True, db_engine=db, root=tmp_path, item_type_code=childcare) == {childcare: "CREATE"}
    assert db.row['item_type_code'] == childcare
    assert all(db.row[field] == manifest[field] for field in TEXT_FIELDS)
    assert any("'DRAFT'" in sql for sql in db.statements if sql.lstrip().startswith('INSERT'))
    assert sync_manifests(apply=False, db_engine=db, root=tmp_path, item_type_code=childcare) == {childcare: "NO_OP"}
    with pytest.raises(ManifestError):
        sync_manifests(apply=True, db_engine=db, root=tmp_path, item_type_code="NOT_IN_PACKAGE")


def test_export_reads_draft_without_writing_database(tmp_path: Path) -> None:
    db = _TemplateDb({"template_version_id": 99, "revision": 7, **_texts()})
    assert export_drafts([TYPE], db_engine=db, root=tmp_path) == {TYPE: "EXPORT"}
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in db.statements)


def test_export_published_requires_explicit_matching_immutable_snapshot_and_is_idempotent(tmp_path: Path) -> None:
    values = _texts(); values["title_ru"] += " published"
    row = {"template_version_id": 99, "item_type_code": TYPE, "status": "PUBLISHED", "revision": 7, **values}
    db, before = _TemplateDb(deepcopy(row)), deepcopy(row)

    assert export_published(TYPE, expected_template_version_id=99, db_engine=db, root=tmp_path) == {TYPE: "EXPORT"}
    exported = load_manifest(manifest_path(TYPE, tmp_path))
    assert {field: exported[field] for field in TEXT_FIELDS} == values
    assert db.row == before
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in db.statements)
    first = manifest_path(TYPE, tmp_path).read_bytes()
    assert export_published(TYPE, expected_template_version_id=99, db_engine=db, root=tmp_path) == {TYPE: "NO_OP"}
    assert manifest_path(TYPE, tmp_path).read_bytes() == first and db.row == before


@pytest.mark.parametrize("status", ("DRAFT", "ARCHIVED"))
def test_export_published_rejects_nonpublished_snapshot_without_writes(tmp_path: Path, status: str) -> None:
    db = _TemplateDb({"template_version_id": 99, "item_type_code": TYPE, "status": status, **_texts()})
    with pytest.raises(ManifestError, match="PUBLISHED"):
        export_published(TYPE, expected_template_version_id=99, db_engine=db, root=tmp_path)
    assert not manifest_path(TYPE, tmp_path).exists()
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in db.statements)


def test_export_published_rejects_id_or_type_mismatch_without_writes(tmp_path: Path) -> None:
    mismatched_id = _TemplateDb({"template_version_id": 100, "item_type_code": TYPE, "status": "PUBLISHED", **_texts()})
    with pytest.raises(ManifestError, match="id mismatch"):
        export_published(TYPE, expected_template_version_id=99, db_engine=mismatched_id, root=tmp_path)

    mismatched_type = _TemplateDb({"template_version_id": 99, "item_type_code": "HIRE", "status": "PUBLISHED", **_texts()})
    with pytest.raises(ManifestError, match="item type"):
        export_published(TYPE, expected_template_version_id=99, db_engine=mismatched_type, root=tmp_path)
    assert not manifest_path(TYPE, tmp_path).exists()
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in mismatched_id.statements + mismatched_type.statements)


def test_export_published_extends_v2_chain_and_plans_only_a_new_draft(tmp_path: Path) -> None:
    v1, v2 = _chain(tmp_path)
    v3 = dict(v2); v3["body_template_ru"] += " published-v3"
    published = {"template_version_id": 99, "item_type_code": TYPE, "status": "PUBLISHED", "version_number": 2, **v3}
    db = _TemplateDb(deepcopy(published))

    assert export_published(TYPE, expected_template_version_id=99, db_engine=db, root=tmp_path) == {TYPE: "EXPORT"}
    chain = load_manifest_chains(tmp_path)[TYPE]
    assert len(chain) == 3
    assert chain[2]["base_content_sha256"] == chain[1]["content_sha256"]
    assert chain[2]["content_sha256"] == content_sha256(TYPE, v3)
    action, manifests = _sync_plan(chain, {"status": "PUBLISHED", "version_number": 2, **v2})
    assert action == "CREATE" and len(manifests) == 1
    assert {field: manifests[0][field] for field in TEXT_FIELDS} == v3
    assert db.row == published


def test_compatibility_loader_accepts_only_unchanged_historical_termination_v1_v2(tmp_path: Path) -> None:
    root = tmp_path / "manifests"
    shutil.copytree(MANIFEST_ROOT / TYPE, root / TYPE)
    chain = load_manifest_chains(root)[TYPE]
    assert len(chain) == 3

    v1_path = manifest_path(TYPE, root, 1)
    changed = json.loads(v1_path.read_text(encoding="utf-8"))
    changed["title_ru"] += " changed"
    v1_path.write_bytes(_manifest_bytes(changed))
    with pytest.raises(ManifestError, match="content_sha256 mismatch"):
        load_manifest_chains(root)

    changed["content_sha256"] = content_sha256(TYPE, {field: changed[field] for field in TEXT_FIELDS})
    v1_path.write_bytes(_manifest_bytes(changed))
    with pytest.raises(ManifestError, match="variable contract does not match"):
        load_manifest_chains(root)


def test_new_manifest_cannot_use_historical_variable_contract(tmp_path: Path) -> None:
    path = _write(tmp_path, _texts())
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["allowed_variables"] = [
        "employee.full_name", "employee.full_name_instrumental_kk",
        "position.title_ru", "position.title_kk", "org_unit.title_ru",
        "org_unit.title_kk", "effective_date", "termination.reason",
        "termination.unused_leave_days", "basis",
    ]
    path.write_bytes(_manifest_bytes(manifest))
    with pytest.raises(ManifestError, match="variable contract does not match"):
        load_manifest(path)


def test_sync_without_any_manifests_is_a_safe_noop(tmp_path: Path) -> None:
    db = _TemplateDb()
    assert sync_manifests(apply=False, db_engine=db, root=tmp_path) == {}
    assert sync_manifests(apply=True, db_engine=db, root=tmp_path) == {}
    assert db.statements == []


def test_sync_create_noop_and_round_trip_to_separate_database(tmp_path: Path) -> None:
    values = _texts(); values["title_ru"] += " (локальная редакция)"; _write(tmp_path, values); target = _TemplateDb()
    assert sync_manifests(apply=False, db_engine=target, root=tmp_path) == {TYPE: "CREATE"}
    assert sync_manifests(apply=True, db_engine=target, root=tmp_path) == {TYPE: "CREATE"}
    assert {field: target.row[field] for field in TEXT_FIELDS} == values
    revision = target.row["revision"]
    assert sync_manifests(apply=True, db_engine=target, root=tmp_path) == {TYPE: "NO_OP"} and target.row["revision"] == revision


def test_sync_updates_only_when_server_matches_base_and_only_template_table(tmp_path: Path) -> None:
    values = _texts(); values["preamble_ru"] += " редакция"; _write(tmp_path, values)
    server = _TemplateDb({"template_version_id": 12, "revision": 3, **_texts()})
    assert sync_manifests(apply=True, db_engine=server, root=tmp_path) == {TYPE: "UPDATE"} and server.row["revision"] == 4
    sql = "\n".join(server.statements).lower()
    assert "personnel_order_template_versions" in sql and not any(table in sql for table in ("personnel_orders", "personnel_order_items", "employee_events", "person_assignments", "editorial_blocks"))


def test_sync_conflict_does_not_partially_change_draft(tmp_path: Path) -> None:
    values = _texts(); values["body_template_ru"] += " target"; _write(tmp_path, values)
    server_values = _texts(); server_values["body_template_ru"] += " independent"; server = _TemplateDb({"template_version_id": 12, "revision": 3, **server_values}); before = deepcopy(server.row)
    assert sync_manifests(apply=True, db_engine=server, root=tmp_path) == {TYPE: "CONFLICT"} and server.row == before
    assert not any(statement.lstrip().upper().startswith(("INSERT", "UPDATE")) for statement in server.statements)


def test_sync_rolls_back_on_write_error(tmp_path: Path) -> None:
    values = _texts(); values["title_kk"] += " target"; _write(tmp_path, values)
    server = _TemplateDb({"template_version_id": 12, "revision": 3, **_texts()}, fail_update=True); before = deepcopy(server.row)
    with pytest.raises(RuntimeError, match="injected"): sync_manifests(apply=True, db_engine=server, root=tmp_path)
    assert server.row == before


def test_versioned_chain_syncs_built_in_then_v1_then_v2(tmp_path: Path) -> None:
    v1, v2 = _chain(tmp_path)
    chain = load_manifest_chains(tmp_path)[TYPE]
    assert len(chain) == 2
    assert chain[1]["base_content_sha256"] == chain[0]["content_sha256"]
    assert write_manifest(TYPE, v2, tmp_path) == "NO_OP"

    built_in = _TemplateDb({"template_version_id": 12, "revision": 3, **_texts()})
    assert sync_manifests(apply=True, db_engine=built_in, root=tmp_path) == {TYPE: "UPDATE"}
    assert {field: built_in.row[field] for field in TEXT_FIELDS} == v2 and built_in.row["revision"] == 5


def test_versioned_chain_applies_only_v2_from_v1_and_noops_at_v2(tmp_path: Path) -> None:
    v1, v2 = _chain(tmp_path)
    at_v1 = _TemplateDb({"template_version_id": 12, "revision": 3, **v1})
    assert sync_manifests(apply=True, db_engine=at_v1, root=tmp_path) == {TYPE: "UPDATE"}
    assert {field: at_v1.row[field] for field in TEXT_FIELDS} == v2 and at_v1.row["revision"] == 4
    at_v2 = _TemplateDb({"template_version_id": 12, "revision": 4, **v2})
    assert sync_manifests(apply=True, db_engine=at_v2, root=tmp_path) == {TYPE: "NO_OP"}
    assert at_v2.row["revision"] == 4


def test_versioned_chain_conflicts_for_unknown_hash_and_rolls_back_intermediate_failure(tmp_path: Path) -> None:
    v1, _ = _chain(tmp_path)
    unknown = dict(v1); unknown["body_template_ru"] += " independent"
    conflicting = _TemplateDb({"template_version_id": 12, "revision": 3, **unknown})
    assert sync_manifests(apply=True, db_engine=conflicting, root=tmp_path) == {TYPE: "CONFLICT"}
    assert not any(sql.lstrip().upper().startswith("UPDATE") for sql in conflicting.statements)
    failing = _TemplateDb({"template_version_id": 12, "revision": 3, **_texts()}, fail_on_update=2)
    before = deepcopy(failing.row)
    with pytest.raises(RuntimeError, match="injected"):
        sync_manifests(apply=True, db_engine=failing, root=tmp_path)
    assert failing.row == before


def test_published_target_is_noop_without_draft(tmp_path: Path) -> None:
    _, v2 = _chain(tmp_path); chain = load_manifest_chains(tmp_path)[TYPE]
    row = {"status": "PUBLISHED", "revision": 7, "version_number": 9, **v2}
    assert _sync_plan(chain, row) == ("NO_OP", [])
    assert row["revision"] == 7 and row["version_number"] == 9 and row["status"] == "PUBLISHED"


def test_published_v1_plans_new_draft_v2_and_unknown_conflicts(tmp_path: Path) -> None:
    v1, v2 = _chain(tmp_path); chain = load_manifest_chains(tmp_path)[TYPE]
    published = {"status": "PUBLISHED", "revision": 5, "version_number": 11, **v1}
    action, manifests = _sync_plan(chain, published)
    assert action == "CREATE" and len(manifests) == 1 and {f: manifests[0][f] for f in TEXT_FIELDS} == v2
    draft = {"status": "DRAFT", "revision": 8, "version_number": 12, **v2}
    assert _sync_plan(chain, draft) == ("NO_OP", [])
    unknown = dict(published); unknown["title_ru"] += " unknown"
    assert _sync_plan(chain, unknown) == ("CONFLICT", [])


@pytest.mark.skipif("corpsite_test" not in TEST_URL, reason="requires corpsite_test")
def test_real_apply_keeps_published_v1_and_creates_draft_v2(tmp_path: Path) -> None:
    v1, v2 = _chain(tmp_path); db = create_engine(TEST_URL); conn = db.connect(); outer = conn.begin()
    try:
        published_id = _pg_insert_template(conn, TYPE, 990001, "PUBLISHED", v1)
        adapter = _RealTransactionEngine(conn)
        assert sync_manifests(apply=True, db_engine=adapter, root=tmp_path) == {TYPE: "CREATE"}
        rows = conn.execute(text("SELECT template_version_id,status,version_number,revision,title_ru,preamble_ru FROM personnel_order_template_versions WHERE item_type_code=:type ORDER BY version_number"), {"type": TYPE}).mappings().all()
        assert len(rows) == 2 and rows[0]["template_version_id"] == published_id and rows[0]["status"] == "PUBLISHED"
        assert rows[0]["version_number"] == 990001 and rows[0]["revision"] == 1 and rows[0]["title_ru"] == v1["title_ru"]
        assert rows[1]["status"] == "DRAFT" and rows[1]["version_number"] == 990002 and rows[1]["preamble_ru"] == v2["preamble_ru"]
        revision = rows[1]["revision"]
        assert sync_manifests(apply=False, db_engine=adapter, root=tmp_path) == {TYPE: "NO_OP"}
        assert sync_manifests(apply=True, db_engine=adapter, root=tmp_path) == {TYPE: "NO_OP"}
        assert conn.execute(text("SELECT revision FROM personnel_order_template_versions WHERE template_version_id=:id"), {"id": rows[1]["template_version_id"]}).scalar_one() == revision
    finally: outer.rollback(); conn.close(); db.dispose()


@pytest.mark.skipif("corpsite_test" not in TEST_URL, reason="requires corpsite_test")
def test_real_apply_rolls_back_all_types_when_second_insert_fails(tmp_path: Path) -> None:
    first, second = "TERMINATION", "HIRE"; db = create_engine(TEST_URL); conn = db.connect(); outer = conn.begin()
    try:
        values1, values2 = dict(get_personnel_order_template_spec(first).initial_texts), dict(get_personnel_order_template_spec(second).initial_texts)
        target1, target2 = dict(values1), dict(values2); target1["title_ru"] += " sync"; target2["title_ru"] += " sync"
        assert write_manifest(first, target1, tmp_path) == "EXPORT" and write_manifest(second, target2, tmp_path) == "EXPORT"
        id1 = _pg_insert_template(conn, first, 990101, "PUBLISHED", values1); id2 = _pg_insert_template(conn, second, 990101, "PUBLISHED", values2)
        conn.execute(text("""CREATE FUNCTION public.test_manifest_sync_fail() RETURNS trigger AS $$ BEGIN IF NEW.item_type_code='HIRE' AND NEW.status='DRAFT' THEN RAISE EXCEPTION 'sync failpoint'; END IF; RETURN NEW; END $$ LANGUAGE plpgsql"""))
        conn.execute(text("CREATE TRIGGER test_manifest_sync_fail BEFORE INSERT ON personnel_order_template_versions FOR EACH ROW EXECUTE FUNCTION public.test_manifest_sync_fail()"))
        with pytest.raises(Exception, match="sync failpoint"):
            with conn.begin_nested(): sync_manifests(apply=True, db_engine=_RealTransactionEngine(conn), root=tmp_path)
        rows = conn.execute(text("SELECT template_version_id,status,revision,version_number FROM personnel_order_template_versions WHERE template_version_id IN (:one,:two)"), {"one": id1, "two": id2}).mappings().all()
        assert len(rows) == 2 and all(r["status"] == "PUBLISHED" and r["revision"] == 1 and r["version_number"] == 990101 for r in rows)
        assert conn.execute(text("SELECT count(*) FROM personnel_order_template_versions WHERE status='DRAFT' AND item_type_code IN (:one,:two)"), {"one": first, "two": second}).scalar_one() == 0
    finally: outer.rollback(); conn.close(); db.dispose()


def test_validator_rejects_a_broken_or_noncontinuous_chain(tmp_path: Path) -> None:
    _, v2 = _chain(tmp_path)
    broken = json.loads(manifest_path(TYPE, tmp_path, 2).read_text(encoding="utf-8"))
    broken["base_content_sha256"] = "0" * 64
    manifest_path(TYPE, tmp_path, 2).write_bytes((json.dumps(broken, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    with pytest.raises(ManifestError, match="chain"):
        load_manifest_chains(tmp_path)
    assert v2["preamble_ru"]


@pytest.mark.parametrize("unsafe", ("{{unknown.variable}}", "<script>alert(1)</script>"))
def test_invalid_or_unknown_manifest_variable_is_rejected(tmp_path: Path, unsafe: str) -> None:
    path = _write(tmp_path, _texts()); manifest = json.loads(path.read_text(encoding="utf-8")); manifest["body_template_ru"] += " {{unknown.variable}}"
    manifest["body_template_ru"] = manifest["body_template_ru"].replace("{{unknown.variable}}", unsafe)
    manifest["content_sha256"] = content_sha256(TYPE, {field: manifest[field] for field in TEXT_FIELDS}); path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ManifestError): load_manifest(path)
