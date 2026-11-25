"""Create and inspect one fictional Order 67 acceptance case on the test DB only."""
from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from app.db.engine import engine
from app.personnel_applications.application.registration_service import register_personnel_application
from app.personnel_applications.application.electronic_hire_service import mark_candidate_checked

EXPECTED_DB = "corpsite_hire_accept_20261120_test"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["setup", "ready", "inspect"])
    parser.add_argument("--application-id", type=int)
    parser.add_argument("--person-id", type=int)
    args = parser.parse_args()
    with engine.begin() as conn:
        db = conn.execute(text("select current_database()")).scalar_one()
        if db != EXPECTED_DB:
            raise SystemExit(f"Refusing database {db!r}; expected {EXPECTED_DB!r}")
        if args.action == "setup":
            old = conn.execute(text("select selected_template_version_id from public.personnel_orders where order_id=59")).scalar_one()
            if old != 2:
                raise SystemExit(f"Old draft 59 changed before acceptance: {old}")
            row = conn.execute(text("""
                select m.user_id, u.unit_id, p.position_id
                from public.org_unit_managers m
                join public.org_units u on u.unit_id=m.unit_id
                cross join lateral (select position_id from public.positions order by position_id limit 1) p
                where u.group_id=3 and m.manager_type='HEAD' and m.is_active=true
                order by u.unit_id limit 1
            """)).mappings().one()
            iin = f"9{uuid4().int % 10**11:011d}"
            result = register_personnel_application(
                conn, iin_raw=iin, full_name="Тестовая Майра", birth_date=date(1990, 1, 1),
                application_received_at=date(2026, 11, 25), vacancy_check_status="pending",
                vacancy_checked_at=None, vacancy_checked_by_user_id=None,
                intended_org_group_id=None, intended_org_unit_id=row["unit_id"],
                intended_position_id=row["position_id"], intended_employment_rate=Decimal("0.75"),
                intended_vacancy_text=None, contact_mobile_phone=None, contact_email=None,
                hr_note="Вымышленный кандидат для приёмки приказа №67",
                idempotency_key=f"order67-accept-{uuid4().hex}", registered_by_user_id=row["user_id"],
                actor_id=f"user:{row['user_id']}", application_source="electronic",
            )
            conn.execute(text("""
                insert into public.electronic_hire_applications(application_id, planned_start_date, approval_mode)
                values (:id, '2026-12-02', 'electronic')
            """), {"id": result.application_id})
            conn.execute(text("""
                update public.persons set last_name='Тестовая', first_name='Майра'
                where person_id=:id
            """), {"id": result.person_id})
            conn.execute(text("""
                insert into public.person_contacts(person_id, mobile_phone)
                values (:id, '+77001234567')
                on conflict (person_id) do update set mobile_phone=excluded.mobile_phone
            """), {"id": result.person_id})
            conn.execute(text("""
                insert into public.person_education(person_id, education_kind, institution_name)
                select :id, code, 'Вымышленный учебный центр'
                from public.education_program_kinds order by code limit 1
            """), {"id": result.person_id})
            print(json.dumps({"database": db, "application_id": result.application_id,
                              "person_id": result.person_id, "card_href": result.card_href,
                              "unit_id": row["unit_id"], "position_id": row["position_id"],
                              "head_user_id": row["user_id"], "draft_59_template_version_id": old}, ensure_ascii=False))
        elif args.action == "ready":
            if not args.application_id or not args.person_id:
                raise SystemExit("--application-id and --person-id required")
            row = conn.execute(text("""
                update public.personnel_applications
                set status='intake_submitted'
                where application_id=:id and person_id=:person_id and status in ('registered', 'intake_submitted')
                returning application_id, person_id, status, registered_by_user_id
            """), {"id": args.application_id, "person_id": args.person_id}).mappings().one()
            mark_candidate_checked(conn, args.application_id, int(row["registered_by_user_id"]))
            conn.execute(text("""
                insert into public.personnel_intake_transfers
                    (application_id, status, result, transferred_by_user_id, transferred_at,
                     sections_transferred, command_ids)
                values (:id, 'completed', 'success', :actor, now(), '["general"]'::jsonb, '[]'::jsonb)
                on conflict (application_id) do nothing
            """), {"id": args.application_id, "actor": row["registered_by_user_id"]})
            print(json.dumps(dict(row)))
        else:
            if not args.application_id:
                raise SystemExit("--application-id required")
            row = conn.execute(text("""
                select a.application_id, a.person_id, a.personnel_order_id, a.status,
                       a.intended_org_unit_id, a.intended_position_id, a.intended_employment_rate,
                       o.status order_status, o.order_number, o.order_date,
                       o.signed_by_name, o.selected_template_version_id,
                       (select count(*) from public.employees where person_id=a.person_id) employee_count,
                       (select count(*) from public.person_assignments where person_id=a.person_id) assignment_count,
                       (select jsonb_agg(jsonb_build_object('org_unit_id', org_unit_id,
                            'position_id', position_id, 'rate', rate, 'start_date', start_date))
                        from public.person_assignments where person_id=a.person_id) assignments,
                       (select jsonb_agg(jsonb_build_object('employee_id', employee_id,
                            'org_unit_id', org_unit_id, 'position_id', position_id,
                            'employment_rate', employment_rate, 'is_active', is_active))
                        from public.employees where person_id=a.person_id) employees,
                       (select jsonb_agg(jsonb_build_object('item_id', item_id, 'employee_id', employee_id,
                            'rate', payload->>'employment_rate'))
                        from public.personnel_order_items where order_id=o.order_id) order_items,
                       (select count(*) from public.employee_events where order_id=o.order_id and event_type='HIRE') hire_event_count
                from public.personnel_applications a
                left join public.personnel_orders o on o.order_id=a.personnel_order_id
                where a.application_id=:id
            """), {"id": args.application_id}).mappings().one()
            print(json.dumps({"database": db, **dict(row),
                              "draft_59_template_version_id": conn.execute(text("select selected_template_version_id from public.personnel_orders where order_id=59")).scalar_one()},
                             ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
