"""Read-only HIRE catalog and published-template preflight for test/production."""
from __future__ import annotations

import json
from sqlalchemy import text
from app.db.engine import engine

RU = "В соответствии со статьей 34 Трудового кодекса Республики Казахстан"
KK = "Қазақстан Республикасы Еңбек кодексінің 34 - бабына сәйкес"

with engine.connect() as conn:
    db = conn.execute(text("select current_database()")).scalar_one()
    if db not in {"corpsite", "corpsite_hire_accept_20261120_test"}:
        raise SystemExit(f"Unexpected database {db}")
    template = conn.execute(text("""
        select t.template_id, v.template_version_id, v.version_number, v.revision,
               v.preamble_ru, v.preamble_kk
        from public.personnel_order_templates t
        join public.personnel_order_template_versions v on v.template_id=t.template_id
        where t.item_type_code='HIRE' and t.is_default and v.status='PUBLISHED'
    """)).mappings().one()
    units = conn.execute(text("""
        select u.unit_id, u.name, u.name_kk,
               to_jsonb(u)->>'document_genitive_ru' document_genitive_ru,
               to_jsonb(u)->>'document_genitive_kk' document_genitive_kk
        from public.org_units u
        where exists (
            select 1 from public.org_unit_managers m
            where m.unit_id=u.unit_id and m.manager_type='HEAD' and m.is_active)
        order by u.unit_id
    """)).mappings().all()
    positions = conn.execute(text("""
        select position_id, name, to_jsonb(p)->>'name_kk' name_kk,
               to_jsonb(p)->>'document_nominative_ru' document_nominative_ru,
               to_jsonb(p)->>'document_possessive_kk' document_possessive_kk
        from public.positions p order by position_id
    """)).mappings().all()
    has_modes = bool(conn.execute(text("select to_regclass('public.hire_approval_unit_modes') is not null")).scalar_one())
    modes = conn.execute(text("""
        select m.mode, count(*) n from public.hire_approval_unit_modes m
        group by m.mode order by m.mode
    """)).mappings().all() if has_modes else []
    complete_units = [u for u in units if all(u[k] for k in ("name_kk", "document_genitive_kk"))]
    groups = conn.execute(text("select group_id, count(*) n from public.org_units group by group_id order by group_id")).mappings().all()
    complete_positions = [p for p in positions if all(p[k] for k in ("name_kk", "document_nominative_ru", "document_possessive_kk"))]
    if template["preamble_ru"] != RU or template["preamble_kk"] != KK:
        raise SystemExit(f"Published HIRE template in {db} has different preambles")
    print(json.dumps({"database": db, "hire_template": {k: template[k] for k in
                      ("template_id", "template_version_id", "version_number", "revision")},
                      "article_34_preambles_ok": True,
                      "org_unit_groups": [dict(row) for row in groups],
                      "hire_approval_modes_schema_available": has_modes,
                      "explicit_hire_approval_modes": [dict(row) for row in modes],
                      "units_with_head": len(units), "complete_units": len(complete_units),
                      "complete_unit_examples": [{"unit_id": u["unit_id"], "name": u["name"]} for u in complete_units[:5]],
                      "positions": len(positions), "complete_positions": len(complete_positions),
                      "complete_position_examples": [{"position_id": p["position_id"], "name": p["name"]} for p in complete_positions[:5]]},
                     ensure_ascii=False, default=str))
