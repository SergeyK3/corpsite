from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.services.personnel_order_template_manifest import MANIFEST_FIELDS, TEXT_FIELDS, ManifestError, content_sha256, export_drafts, load_manifest, manifest_path, sync_manifests, write_manifest
from app.services.personnel_order_template_specs import get_personnel_order_template_spec

TYPE = "TERMINATION"


def _texts() -> dict[str, str]: return dict(get_personnel_order_template_spec(TYPE).initial_texts)


class _Result:
    def __init__(self, row: dict[str, Any] | None = None) -> None: self.row = row
    def mappings(self) -> "_Result": return self
    def first(self) -> dict[str, Any] | None: return self.row


class _TemplateDb:
    """Transaction-aware SQL boundary double for the sync-only table."""
    def __init__(self, row: dict[str, Any] | None = None, *, fail_update: bool = False) -> None:
        self.row, self.fail_update, self.statements, self._snapshot = row, fail_update, [], None
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
        if self.fail_update: raise RuntimeError("injected write failure")
        assert compact.startswith("UPDATE") and self.row is not None
        self.row.update({field: values[field] for field in TEXT_FIELDS}); self.row["revision"] += 1
        return _Result(self.row)


def _write(tmp_path: Path, values: dict[str, str]) -> Path:
    assert write_manifest(TYPE, values, tmp_path) == "EXPORT"
    return manifest_path(TYPE, tmp_path)


def test_canonical_export_is_stable_and_excludes_ids_and_personal_data(tmp_path: Path) -> None:
    path = _write(tmp_path, _texts()); first = path.read_bytes()
    assert write_manifest(TYPE, _texts(), tmp_path) == "NO_OP" and path.read_bytes() == first and b"\r\n" not in first
    decoded, manifest = first.decode("utf-8"), json.loads(first)
    assert "\\u" not in decoded and tuple(manifest) == MANIFEST_FIELDS
    assert not {"template_version_id", "user_id", "revision", "created_at", "updated_at", "password", "token"} & set(manifest)
    assert "Иванов" not in decoded and "IIN" not in decoded


def test_export_reads_draft_without_writing_database(tmp_path: Path) -> None:
    db = _TemplateDb({"template_version_id": 99, "revision": 7, **_texts()})
    assert export_drafts([TYPE], db_engine=db, root=tmp_path) == {TYPE: "EXPORT"}
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in db.statements)


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


@pytest.mark.parametrize("unsafe", ("{{unknown.variable}}", "<script>alert(1)</script>"))
def test_invalid_or_unknown_manifest_variable_is_rejected(tmp_path: Path, unsafe: str) -> None:
    path = _write(tmp_path, _texts()); manifest = json.loads(path.read_text(encoding="utf-8")); manifest["body_template_ru"] += " {{unknown.variable}}"
    manifest["body_template_ru"] = manifest["body_template_ru"].replace("{{unknown.variable}}", unsafe)
    manifest["content_sha256"] = content_sha256(TYPE, {field: manifest[field] for field in TEXT_FIELDS}); path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ManifestError): load_manifest(path)
