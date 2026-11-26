"""Apply the accepted, non-personal HIRE position catalog and unit links.

Use --dry-run against production before --apply. The input contains position
names and unit codes, never test database IDs or candidate data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = ROOT / "reference-data/hire/accepted-position-links-20261126.json"


def _index_positions(rows: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for row in rows:
        key = row["name"].strip().casefold()
        if key in index:
            raise RuntimeError(f"Duplicate catalog position name: {row['name']}")
        index[key] = row
    return index


def apply(conn, spec: dict) -> dict:
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('hire-catalog-20261126'))"))
    positions = [dict(row) for row in conn.execute(text("SELECT * FROM public.positions FOR UPDATE")).mappings()]
    index = _index_positions(positions)
    aliases = spec["aliases"]
    inserted_positions: list[dict] = []
    reused_positions: list[dict] = []

    for approved in spec["approved_positions"]:
        name = approved["job_nameru"]
        row = index.get(name.casefold())
        if row is None and name in aliases:
            row = index.get(aliases[name].casefold())
        if row is None:
            row = dict(conn.execute(text("""
                INSERT INTO public.positions
                    (name, category, name_kk, document_nominative_ru,
                     document_possessive_kk, translation_status, document_form_status,
                     record_kind, revision, type_code)
                VALUES (:name, :category, :name_kk, :form_ru, :form_kk,
                        'confirmed', 'confirmed', 'standalone', 1, :type_code)
                RETURNING position_id, name
            """), {
                "name": name, "category": approved["category"],
                "name_kk": approved["job_namekk"],
                "form_ru": approved["hire_document_ru"],
                "form_kk": approved["hire_document_kk"],
                "type_code": approved["type_code"],
            }).mappings().one())
            inserted_positions.append(row)
        else:
            conn.execute(text("""
                UPDATE public.positions SET
                    name=:name, name_kk=:name_kk,
                    document_nominative_ru=:form_ru,
                    document_possessive_kk=:form_kk,
                    translation_status='confirmed', document_form_status='confirmed',
                    revision=revision+1
                WHERE position_id=:position_id
                  AND (name, name_kk, document_nominative_ru, document_possessive_kk,
                       translation_status, document_form_status)
                      IS DISTINCT FROM
                      (:name, :name_kk, :form_ru, :form_kk, 'confirmed', 'confirmed')
            """), {
                "position_id": row["position_id"], "name": name,
                "name_kk": approved["job_namekk"],
                "form_ru": approved["hire_document_ru"],
                "form_kk": approved["hire_document_kk"],
            })
            reused_positions.append({"position_id": row["position_id"], "name": name})
        index[name.casefold()] = row

    buffet_name = spec["existing_position_names"]["BUFFET_WORKER"]
    buffet = index.get(buffet_name.casefold())
    if buffet is None:
        raise RuntimeError("Existing Buffet Worker position is missing; no new ID may be created")
    conn.execute(text("""
        UPDATE public.positions SET name_kk='Буфетші',
            document_nominative_ru='буфетчицы',
            document_possessive_kk='буфетшісі',
            translation_status='confirmed', document_form_status='confirmed',
            revision=revision+1
        WHERE position_id=:id AND
          (name_kk, document_nominative_ru, document_possessive_kk,
           translation_status, document_form_status)
          IS DISTINCT FROM ('Буфетші', 'буфетчицы', 'буфетшісі', 'confirmed', 'confirmed')
    """), {"id": buffet["position_id"]})
    reused_positions.append({"position_id": buffet["position_id"], "name": buffet_name})

    units = [dict(row) for row in conn.execute(text("SELECT unit_id, code, group_id, is_active FROM public.org_units")).mappings()]
    unit_index = {row["code"]: row for row in units}
    if len(unit_index) != len(units):
        raise RuntimeError("Duplicate org unit codes")
    if unit_index.get("SURG_01", {}).get("group_id") != 1 or unit_index.get("ADMISSION", {}).get("group_id") != 2:
        raise RuntimeError("Production clinical/paraclinical group IDs differ from the reviewed baseline")

    existing_links = {
        (row["org_unit_id"], row["position_id"]): bool(row["is_active"])
        for row in conn.execute(text("SELECT org_unit_id, position_id, is_active FROM public.org_unit_allowed_positions")).mappings()
    }
    desired: dict[tuple[int, int], int | None] = {}
    for link in spec["links"]:
        unit = unit_index.get(link["unit_code"])
        position = index.get(link["position_name"].casefold())
        if unit is None or position is None:
            raise RuntimeError(f"Unmapped accepted link {link['unit_code']} / {link['position_name']}")
        desired[(unit["unit_id"], position["position_id"])] = link["sort_order"]

    code_to_name = {
        row["job_code"]: row["job_nameru"] for row in spec["approved_positions"]
    } | spec["existing_position_names"]
    for group_id, group_name in ((1, "Клинические"), (2, "Параклинические")):
        required_names = spec["approved_group_positions"][group_name]
        for unit in units:
            if not unit["is_active"] or unit["group_id"] != group_id:
                continue
            for code in required_names:
                position_name = code_to_name[code]
                position = index.get(position_name.casefold())
                if position is None:
                    raise RuntimeError(f"Required position missing: {code}")
                desired.setdefault((unit["unit_id"], position["position_id"]), None)

    legacy_name = spec["existing_position_names"]["SANITARY_BUFFET_WORKER"]
    legacy = index.get(legacy_name.casefold())
    if legacy is None:
        raise RuntimeError("Historical sanitary buffet position is missing")
    if any(position_id == legacy["position_id"] for _, position_id in desired):
        raise RuntimeError("Historical sanitary buffet position appears in new hire links")

    added_links = 0
    reactivated_links = 0
    for (unit_id, position_id), sort_order in sorted(desired.items()):
        prior = existing_links.get((unit_id, position_id))
        if prior is None:
            added_links += 1
        elif prior is False:
            reactivated_links += 1
        conn.execute(text("""
            INSERT INTO public.org_unit_allowed_positions
                (org_unit_id, position_id, sort_order, is_active)
            VALUES (:unit_id, :position_id, :sort_order, TRUE)
            ON CONFLICT ON CONSTRAINT uq_ouap_org_unit_position
            DO UPDATE SET is_active=TRUE,
              sort_order=COALESCE(org_unit_allowed_positions.sort_order, EXCLUDED.sort_order),
              updated_at=now()
        """), {"unit_id": unit_id, "position_id": position_id, "sort_order": sort_order})
    disabled_legacy = conn.execute(text("""
        UPDATE public.org_unit_allowed_positions SET is_active=FALSE, updated_at=now()
        WHERE position_id=:id AND is_active=TRUE
    """), {"id": legacy["position_id"]}).rowcount

    return {
        "inserted_positions": inserted_positions,
        "reused_positions": reused_positions,
        "buffet_position_id": buffet["position_id"],
        "historical_sanitary_buffet_position_id": legacy["position_id"],
        "accepted_link_pairs": len(desired),
        "added_links": added_links,
        "reactivated_links": reactivated_links,
        "disabled_historical_links": disabled_legacy,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--database", help="Isolated rehearsal database name")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    url = dotenv_values(args.env).get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL missing")
    if args.database:
        if args.database != "corpsite_hire_release_20261126_test":
            raise SystemExit("Only the named isolated rehearsal database may override DATABASE_URL")
        url = make_url(url).set(database=args.database)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    engine = create_engine(url)
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            result = apply(conn, spec)
            if args.apply:
                transaction.commit()
            else:
                transaction.rollback()
        except BaseException:
            transaction.rollback()
            raise
    print(json.dumps({"applied": args.apply, **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
