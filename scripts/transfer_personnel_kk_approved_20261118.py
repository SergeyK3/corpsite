#!/usr/bin/env python3
"""Guarded, all-or-nothing transfer of the approved KK personnel names.

Default mode is a read-only preflight. --apply requires an exclusive backup file.
The package targets existing rows only; no IDs, RU names or links are changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from sqlalchemy import bindparam, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.db.engine import engine

PACKAGE = ROOT / "reference-data/dictionaries/personnel-kk-approved-transfer-20261118.json"
APPROVED_PACKAGE_SHA256 = "64f0eca90a06a12a7a2e7f0a265a7a292c0f7c467d76316244aa36fe05a204fd"
POSITION_GUARD = {"position_id", "name", "name_kk", "document_possessive_kk",
                  "translation_status", "document_form_status", "revision", "category",
                  "record_kind", "type_code", "job_code"}
ORG_GUARD = {"unit_id", "code", "name", "name_kk", "parent_unit_id", "group_id"}
COMMON_SET = {"name_kk", "translation_status"}
NURSE_SET = COMMON_SET | {"document_possessive_kk", "document_form_status"}


class TransferError(RuntimeError):
    pass


def read_package(path: Path) -> tuple[dict, str]:
    data = path.read_bytes()
    # Git checkouts may use CRLF on Windows; approval covers the JSON content
    # with canonical LF line endings rather than a host's newline setting.
    digest = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
    if digest != APPROVED_PACKAGE_SHA256:
        raise TransferError("Package checksum differs from reviewed approval set")
    package = json.loads(data)
    if (package.get("schema_version"), package.get("kind")) != (1, "personnel-kk-approved-transfer"):
        raise TransferError("Unexpected package format")
    if package.get("target", {}).get("database") != "corpsite":
        raise TransferError("Unexpected target database")
    positions = package.get("positions")
    orgs = package.get("org_units")
    if not isinstance(positions, list) or len(positions) != 29 or not isinstance(orgs, list) or len(orgs) != 1:
        raise TransferError("Expected exactly 29 positions and one org unit")
    source_ids = {item["source_local_id"] for item in positions}
    target_ids = {item["expected"]["position_id"] for item in positions}
    if len(source_ids) != 29 or len(target_ids) != 29 or 27 not in source_ids:
        raise TransferError("Duplicate or missing position identity")
    for item in positions:
        expected, change = item["expected"], item["set"]
        if set(expected) != POSITION_GUARD or set(change) != (NURSE_SET if item["source_local_id"] == 27 else COMMON_SET):
            raise TransferError("Unexpected position columns")
        if not isinstance(expected["position_id"], int) or expected["revision"] < 1:
            raise TransferError("Invalid position ID or revision")
        if change["translation_status"] != "confirmed" or ("document_form_status" in change and change["document_form_status"] != "confirmed"):
            raise TransferError("Invalid approval status")
        for field in ("name_kk", "document_possessive_kk"):
            if field in change and not isinstance(change[field], str):
                raise TransferError("Invalid approved text")
    if set(orgs[0]["expected"]) != ORG_GUARD or set(orgs[0]["set"]) != {"name_kk"}:
        raise TransferError("Unexpected org-unit columns")
    if orgs[0]["source_local_code"] != "ORG_MAIN" or orgs[0]["expected"]["code"] != "mmc_root":
        raise TransferError("Unexpected org-unit identity")
    return package, digest


def read_rows(conn, package: dict, *, lock: bool) -> tuple[dict[int, dict], dict]:
    ids = [item["expected"]["position_id"] for item in package["positions"]]
    stmt = text("""SELECT to_jsonb(p) AS row, m.job_code
        FROM public.positions p
        LEFT JOIN public.position_job_catalog m ON m.position_id=p.position_id
        WHERE p.position_id IN :ids""" + (" FOR UPDATE OF p" if lock else ""))
    stmt = stmt.bindparams(bindparam("ids", expanding=True))
    positions = {}
    for item in conn.execute(stmt, {"ids": ids}).mappings():
        row = dict(item["row"])
        key = row["position_id"]
        if key in positions:
            raise TransferError(f"Multiple catalog links for position {key}")
        positions[key] = {"row": row, "job_code": item["job_code"]}
    unit_id = package["org_units"][0]["expected"]["unit_id"]
    org_stmt = text("SELECT to_jsonb(o) FROM public.org_units o WHERE unit_id=:id" + (" FOR UPDATE" if lock else ""))
    org_rows = list(conn.execute(org_stmt, {"id": unit_id}).scalars())
    if len(org_rows) != 1:
        raise TransferError(f"Expected one org unit {unit_id}, found {len(org_rows)}")
    return positions, dict(org_rows[0])


def compare(package: dict, positions: dict[int, dict], org: dict, *, after: bool = False) -> None:
    if len(positions) != 29:
        raise TransferError(f"Expected 29 positions, found {len(positions)}")
    for item in package["positions"]:
        expected = dict(item["expected"])
        if after:
            expected.update(item["set"])
            expected["revision"] += 1
        position_id = expected["position_id"]
        found = positions.get(position_id)
        if found is None:
            raise TransferError(f"Missing position {position_id}")
        actual = {key: found["job_code"] if key == "job_code" else found["row"].get(key) for key in POSITION_GUARD}
        if actual != expected:
            fields = sorted(key for key in expected if actual[key] != expected[key])
            raise TransferError(f"Position {position_id} source drift: {', '.join(fields)}")
    expected_org = dict(package["org_units"][0]["expected"])
    if after:
        expected_org.update(package["org_units"][0]["set"])
    actual_org = {key: org.get(key) for key in ORG_GUARD}
    if actual_org != expected_org:
        fields = sorted(key for key in expected_org if actual_org[key] != expected_org[key])
        raise TransferError("Org-unit source drift: " + ", ".join(fields))


def save_backup(path: Path, package_sha256: str, positions: dict[int, dict], org: dict) -> None:
    snapshot = {"format": "personnel-kk-transfer-before-v1", "package_sha256": package_sha256,
                "positions": {str(key): value for key, value in positions.items()}, "org_unit": org}
    data = (json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def run(package_path: Path, *, apply: bool, backup: Path | None) -> str:
    package, digest = read_package(package_path)
    if apply and backup is None:
        raise TransferError("--apply requires --backup PATH")
    if backup is not None and backup.exists():
        raise TransferError("Backup path already exists")
    with engine.begin() as conn:
        if apply:
            conn.execute(text("SET LOCAL lock_timeout='5s'"))
            conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('position_directory_write'))"))
        else:
            conn.execute(text("SET TRANSACTION READ ONLY"))
        if conn.execute(text("SELECT current_database()")).scalar_one() != package["target"]["database"]:
            raise TransferError("Database name does not match package")
        positions, org = read_rows(conn, package, lock=apply)
        compare(package, positions, org)
        if not apply:
            return "PREFLIGHT OK: 29 positions and one org unit; zero writes"
        save_backup(backup, digest, positions, org)
        for item in package["positions"]:
            change = item["set"]
            position_id = item["expected"]["position_id"]
            if item["source_local_id"] == 27:
                stmt = text("""UPDATE public.positions SET name_kk=:name_kk,
                    document_possessive_kk=:document_possessive_kk,
                    translation_status=:translation_status,
                    document_form_status=:document_form_status, revision=revision+1
                    WHERE position_id=:position_id AND revision=:revision""")
            else:
                stmt = text("""UPDATE public.positions SET name_kk=:name_kk,
                    translation_status=:translation_status, revision=revision+1
                    WHERE position_id=:position_id AND revision=:revision""")
            result = conn.execute(stmt, {**change, "position_id": position_id, "revision": item["expected"]["revision"]})
            if result.rowcount != 1:
                raise TransferError(f"Position {position_id} changed during transfer")
        unit = package["org_units"][0]
        result = conn.execute(text("UPDATE public.org_units SET name_kk=:name_kk WHERE unit_id=:unit_id"),
                              {"name_kk": unit["set"]["name_kk"], "unit_id": unit["expected"]["unit_id"]})
        if result.rowcount != 1:
            raise TransferError("Org unit changed during transfer")
        post_positions, post_org = read_rows(conn, package, lock=False)
        compare(package, post_positions, post_org, after=True)
    return f"APPLIED: 29 positions and one org unit; backup: {backup}"


def rollback(package_path: Path, backup_path: Path) -> str:
    package, digest = read_package(package_path)
    saved = json.loads(backup_path.read_text(encoding="utf-8"))
    if saved.get("format") != "personnel-kk-transfer-before-v1" or saved.get("package_sha256") != digest:
        raise TransferError("Backup does not belong to this exact package")
    old_positions = {int(key): value for key, value in saved["positions"].items()}
    old_org = saved["org_unit"]
    compare(package, old_positions, old_org)
    with engine.begin() as conn:
        if conn.execute(text("SELECT current_database()")).scalar_one() != package["target"]["database"]:
            raise TransferError("Database name does not match package")
        conn.execute(text("SET LOCAL lock_timeout='5s'"))
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('position_directory_write'))"))
        positions, org = read_rows(conn, package, lock=True)
        compare(package, positions, org, after=True)
        for item in package["positions"]:
            before = item["expected"]
            position_id = before["position_id"]
            if item["source_local_id"] == 27:
                stmt = text("""UPDATE public.positions SET name_kk=:name_kk,
                    document_possessive_kk=:document_possessive_kk,
                    translation_status=:translation_status,
                    document_form_status=:document_form_status, revision=revision+1
                    WHERE position_id=:position_id AND revision=:revision""")
            else:
                stmt = text("""UPDATE public.positions SET name_kk=:name_kk,
                    translation_status=:translation_status, revision=revision+1
                    WHERE position_id=:position_id AND revision=:revision""")
            params = {key: before[key] for key in item["set"]}
            params.update(position_id=position_id, revision=before["revision"] + 1)
            if conn.execute(stmt, params).rowcount != 1:
                raise TransferError(f"Position {position_id} changed during rollback")
        unit = package["org_units"][0]["expected"]
        if conn.execute(text("UPDATE public.org_units SET name_kk=:name_kk WHERE unit_id=:unit_id"),
                        {"name_kk": unit["name_kk"], "unit_id": unit["unit_id"]}).rowcount != 1:
            raise TransferError("Org unit changed during rollback")
        restored, restored_org = read_rows(conn, package, lock=False)
        for item in package["positions"]:
            row = restored[item["expected"]["position_id"]]
            before = old_positions[item["expected"]["position_id"]]
            expected = dict(before["row"])
            expected["revision"] += 2  # keep optimistic revisions monotonic
            if row["row"] != expected or row["job_code"] != before["job_code"]:
                raise TransferError(f"Position {item['expected']['position_id']} rollback verification failed")
        if restored_org != old_org:
            raise TransferError("Org-unit rollback verification failed")
    return "ROLLED BACK: approved fields restored; position revisions advanced by two"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=PACKAGE)
    parser.add_argument("--apply", action="store_true", help="Explicitly apply all approved changes")
    parser.add_argument("--backup", type=Path, help="New exclusive backup JSON path on target host")
    parser.add_argument("--rollback", type=Path, metavar="BACKUP", help="Guarded rollback using the exact pre-apply backup")
    args = parser.parse_args()
    try:
        if args.rollback and (args.apply or args.backup):
            raise TransferError("--rollback cannot be combined with --apply or --backup")
        print(rollback(args.package, args.rollback) if args.rollback else
              run(args.package, apply=args.apply, backup=args.backup))
    except (TransferError, OSError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
