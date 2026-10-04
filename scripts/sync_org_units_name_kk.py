#!/usr/bin/env python3
"""Safely synchronize confirmed org-unit Kazakh names by canonical code.

The default mode is a read-only dry run.  ``--apply`` updates *only*
``public.org_units.name_kk`` in one transaction, after rejecting every missing,
duplicate, or otherwise ambiguous code from the JSON package.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import bindparam, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.engine import engine

DEFAULT_PACKAGE = ROOT / "reference-data" / "org_units_name_kk.json"
DEFAULT_BACKUP_DIR = ROOT / "runtime" / "org_units_name_kk_backups"
REQUIRED_ORG_UNITS_COLUMNS = frozenset({"unit_id", "code", "name", "group_id", "name_kk", "document_genitive_kk"})


class SyncSafetyError(RuntimeError):
    """A package or target does not satisfy the all-or-nothing contract."""


def clean(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def code_key(value: str) -> str:
    return value.casefold()


def load_package(path: Path) -> list[dict[str, str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncSafetyError(f"cannot read JSON package {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("items"), list):
        raise SyncSafetyError("package must contain schema_version=1 and an items array")

    items: list[dict[str, str]] = []
    for index, raw_item in enumerate(raw["items"], start=1):
        if not isinstance(raw_item, dict):
            raise SyncSafetyError(f"item #{index} is not an object")
        code = clean(raw_item.get("code"))
        name_kk = clean(raw_item.get("name_kk"))
        if code is None or name_kk is None:
            raise SyncSafetyError(f"item #{index} must have non-empty code and name_kk")
        items.append({"code": code, "name_kk": name_kk})

    duplicate_codes = sorted(key for key, count in Counter(code_key(item["code"]) for item in items).items() if count > 1)
    if duplicate_codes:
        raise SyncSafetyError(f"duplicate package codes: {', '.join(duplicate_codes)}")
    if len(items) != 46:
        raise SyncSafetyError(f"expected exactly 46 confirmed names, got {len(items)}")
    return items


def assert_org_units_schema(connection: Any) -> None:
    """Fail before the first org_units data query when the schema is outdated."""
    statement = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'org_units'
    """)
    present = {str(row["column_name"]) for row in connection.execute(statement).mappings()}
    missing = sorted(REQUIRED_ORG_UNITS_COLUMNS - present)
    if missing:
        raise SyncSafetyError(
            "public.org_units is missing required columns: "
            + ", ".join(missing)
            + ". Run the tracked Alembic migrations (alembic upgrade head) before syncing names."
        )


def load_target_rows(connection: Any, codes: Iterable[str]) -> list[dict[str, Any]]:
    statement = text("""
        SELECT unit_id, code, name, group_id,
               NULLIF(BTRIM(name_kk), '') AS name_kk,
               NULLIF(BTRIM(document_genitive_kk), '') AS document_genitive_kk
        FROM public.org_units
        WHERE LOWER(BTRIM(code)) IN :codes
        ORDER BY unit_id
    """).bindparams(bindparam("codes", expanding=True))
    return [dict(row) for row in connection.execute(statement, {"codes": [code_key(code) for code in codes]}).mappings()]


def make_plan(items: list[dict[str, str]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows_by_code: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        normalized = clean(row.get("code"))
        if normalized is not None:
            rows_by_code.setdefault(code_key(normalized), []).append(row)

    missing_codes: list[str] = []
    ambiguous_codes: dict[str, list[dict[str, Any]]] = {}
    plan_items: list[dict[str, Any]] = []
    for item in items:
        candidates = rows_by_code.get(code_key(item["code"]), [])
        if not candidates:
            missing_codes.append(item["code"])
            continue
        if len(candidates) != 1:
            ambiguous_codes[item["code"]] = candidates
            continue
        row = candidates[0]
        old_name_kk = clean(row["name_kk"])
        plan_items.append({
            "unit_id": int(row["unit_id"]),
            "code": item["code"],
            "database_code": row["code"],
            "name": row["name"],
            "old_name_kk": old_name_kk,
            "new_name_kk": item["name_kk"],
            "changes": old_name_kk != item["name_kk"],
            "group_id": row["group_id"],
            "document_genitive_kk": row["document_genitive_kk"],
        })
    plan_items.sort(key=lambda item: item["unit_id"])
    return {
        "items": plan_items,
        "missing_codes": sorted(missing_codes, key=code_key),
        "ambiguous_codes": {
            code: [{"unit_id": row["unit_id"], "code": row["code"], "name": row["name"]} for row in candidates]
            for code, candidates in sorted(ambiguous_codes.items(), key=lambda pair: code_key(pair[0]))
        },
        "summary": {
            "package_items": len(items),
            "matched": len(plan_items),
            "updates": sum(item["changes"] for item in plan_items),
            "already_matching": sum(not item["changes"] for item in plan_items),
            "missing": len(missing_codes),
            "ambiguous": len(ambiguous_codes),
        },
    }


def assert_safe(plan: dict[str, Any]) -> None:
    if plan["missing_codes"] or plan["ambiguous_codes"] or plan["summary"]["matched"] != 46:
        raise SyncSafetyError(json.dumps({
            "missing_codes": plan["missing_codes"],
            "ambiguous_codes": plan["ambiguous_codes"],
            "summary": plan["summary"],
        }, ensure_ascii=False))


def backup_payload(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "description": "Pre-apply name_kk values for org_units_name_kk synchronization.",
        "items": [{"unit_id": item["unit_id"], "code": item["database_code"], "name_kk": item["old_name_kk"]} for item in plan["items"]],
    }


def write_backup(path: Path, plan: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise SyncSafetyError(f"refusing to overwrite existing backup: {path}")
    path.write_text(json.dumps(backup_payload(plan), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def apply_plan(connection: Any, plan: dict[str, Any]) -> int:
    changes = [item for item in plan["items"] if item["changes"]]
    statement = text("""
        UPDATE public.org_units
        SET name_kk = :new_name_kk
        WHERE unit_id = :unit_id
          AND NULLIF(BTRIM(name_kk), '') IS NOT DISTINCT FROM :old_name_kk
    """)
    for item in changes:
        result = connection.execute(statement, item)
        if result.rowcount != 1:
            raise SyncSafetyError(f"concurrent name_kk change for code {item['database_code']}")
    return len(changes)


def run(package_path: Path, *, apply: bool, backup_path: Path | None = None) -> dict[str, Any]:
    items = load_package(package_path)
    with engine.begin() as connection:
        assert_org_units_schema(connection)
        plan = make_plan(items, load_target_rows(connection, (item["code"] for item in items)))
        assert_safe(plan)
        if not apply:
            return {"dry_run": True, **plan}
        if backup_path is None:
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            backup_path = DEFAULT_BACKUP_DIR / f"org_units_name_kk_before_{stamp}.json"
        backup = write_backup(backup_path, plan)
        updated = apply_plan(connection, plan)
        verification = make_plan(items, load_target_rows(connection, (item["code"] for item in items)))
        assert_safe(verification)
        if verification["summary"]["updates"] != 0:
            raise SyncSafetyError("post-update verification still has differences")
        return {"dry_run": False, "backup_path": str(backup), "updated": updated, "already_matching": plan["summary"]["already_matching"], **verification}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Sync confirmed org_units name_kk values by canonical code")
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--apply", action="store_true", help="write name_kk in one transaction; dry-run is the default")
    parser.add_argument("--backup", type=Path, help="required only for a custom backup location when using --apply")
    args = parser.parse_args()
    if args.backup is not None and not args.apply:
        parser.error("--backup requires --apply")
    try:
        print(json.dumps(run(args.package, apply=args.apply, backup_path=args.backup), ensure_ascii=False, indent=2, default=str))
    except SyncSafetyError as exc:
        print(f"sync blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
