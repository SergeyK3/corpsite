"""Create a reversible-looking synthetic Stage 0 UI scenario in corpsite_test only.

The script never reads production configuration as an authority: an explicit
TEST_DATABASE_URL is required and validated before the first connection.
"""
from __future__ import annotations

import argparse
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def _test_url(raw: str):
    url = make_url(raw)
    if (url.host or "").lower() not in {"127.0.0.1", "localhost", "::1"} or (url.database or "").lower() != "corpsite_test":
        raise SystemExit("Refusing: TEST_DATABASE_URL must be loopback corpsite_test.")
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="create synthetic demo rows")
    parser.add_argument("--test-database-url", required=True)
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit("Dry mode: pass --apply to create the synthetic corpsite_test scenario.")
    engine = create_engine(_test_url(args.test_database_url))
    marker = uuid4().hex[:10]
    with engine.begin() as conn:
        if conn.execute(text("SELECT current_database()")).scalar_one() != "corpsite_test":
            raise SystemExit("Refusing: server reported a non-test database.")
        actor = conn.execute(text("SELECT min(user_id) FROM public.users WHERE is_active=true")).scalar_one()
        if actor is None:
            raise SystemExit("corpsite_test has no active user.")
        person_id = conn.execute(text("""
            INSERT INTO public.persons(iin,full_name,match_key,person_status,source)
            VALUES(NULL,:name,:key,'active','migration') RETURNING person_id
        """), {"name": f"Тестовый сотрудник Stage 0 {marker}", "key": f"stage0-demo-{marker}"}).scalar_one()
        employee_id = conn.execute(text("""
            INSERT INTO public.employees(full_name,person_id,is_active,operational_status)
            VALUES(:name,:person_id,true,'active') RETURNING employee_id
        """), {"name": f"Тестовый сотрудник Stage 0 {marker}", "person_id": person_id}).scalar_one()
        batch_id = conn.execute(text("""
            INSERT INTO public.hr_import_batches(source_type,file_name,import_code,imported_by,status)
            VALUES('HR_CONTROL_LIST',:file,:code,:actor,'APPLY_PENDING') RETURNING batch_id
        """), {"file": f"stage0-demo-{marker}.xlsx", "code": f"stage0-demo-{marker}", "actor": actor}).scalar_one()
        conn.execute(text("""
            INSERT INTO public.hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload,employee_id)
            VALUES(:batch_id,'Synthetic',1,'{}'::jsonb,CAST(:eligible_payload AS JSONB),:employee_id),
                  (:batch_id,'Synthetic',2,'{}'::jsonb,CAST(:blocked_payload AS JSONB),NULL)
        """), {
            "batch_id": batch_id,
            "employee_id": employee_id,
            "eligible_payload": '{"full_name":"Тестовый допущенный сотрудник"}',
            "blocked_payload": '{"full_name":"Тестовый сотрудник без связи"}',
        })
    print(f"Created synthetic Stage 0 scenario in corpsite_test: batch_id={batch_id}; eligible_employee_id={employee_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
