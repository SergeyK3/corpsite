"""Seed fictional acceptance accounts in corpsite_learn, without password resets.

The private credentials JSON is created only on the first run. Keep it outside
the release tree with mode 0600. Repeated runs leave password hashes intact.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


LOGINS = ("learn.hr.a", "learn.hr.b", "learn.manager", "learn.expert", "learn.substitute",
          "learn.signatory", "learn.candidate.a", "learn.candidate.b")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials-file", required=True)
    parser.add_argument("--rehearsal", action="store_true")
    args = parser.parse_args()
    url = make_url(os.environ["DATABASE_URL"])
    database = url.database or ""
    if url.host not in {"127.0.0.1", "localhost", "::1"} or (
        database != "corpsite_learn" and not (args.rehearsal and database.startswith("corpsite_learn_"))
    ):
        raise SystemExit("Refusing to seed outside the isolated training database")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.auth import hash_password
    credentials_file = Path(args.credentials_file)
    if credentials_file.exists():
        credentials = json.loads(credentials_file.read_text(encoding="utf-8"))
    else:
        credentials = {}
    credentials_updated = False
    for login in LOGINS:
        if login not in credentials:
            credentials[login] = secrets.token_urlsafe(18)
            credentials_updated = True
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        if conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != "learning008":
            raise SystemExit("Run bootstrap_schema.py first")
        existing = {row[0] for row in conn.execute(text("SELECT login FROM public.users WHERE login=ANY(:logins)"),
                                                   {"logins": list(LOGINS)})}
        if existing and not credentials_file.exists():
            raise SystemExit("Acceptance users exist but the private credentials file is missing")
        disp = conn.execute(text("SELECT unit_id FROM public.org_units WHERE code='DISP'")).scalar_one()
        unit = conn.execute(text("SELECT unit_id FROM public.org_units WHERE code='LEARN-BASE'")).scalar_one_or_none()
        if unit is None:
            unit = conn.execute(text("""
                INSERT INTO public.org_units(name,name_kk,code,parent_unit_id,group_id,is_active)
                VALUES ('Учебное отделение','Оқу бөлімі','LEARN-BASE',:parent,2,TRUE) RETURNING unit_id
            """), {"parent": disp}).scalar_one()
        else:
            conn.execute(text("""
                UPDATE public.org_units SET name_kk='Оқу бөлімі'
                WHERE unit_id=:unit AND code='LEARN-BASE' AND name_kk IS NULL
            """), {"unit": unit})
        positions = {}
        for key, name in (("hr", "Кадровик"), ("manager", "Заведующий отделением")):
            value = conn.execute(text("SELECT position_id FROM public.positions WHERE name=:name ORDER BY position_id LIMIT 1"),
                                 {"name": name}).scalar_one_or_none()
            if value is None:
                value = conn.execute(text("""
                    INSERT INTO public.positions(name,document_nominative_ru,document_form_status)
                    VALUES (:name,:name,'needs_review') RETURNING position_id
                """), {"name": name}).scalar_one()
            positions[key] = int(value)
        hire_position = conn.execute(text("""
            SELECT position_id FROM public.positions WHERE name='Учебный специалист'
            ORDER BY position_id LIMIT 1
        """)).scalar_one_or_none()
        if hire_position is None:
            hire_position = conn.execute(text("""
                INSERT INTO public.positions
                  (name,name_kk,document_nominative_ru,document_possessive_kk,document_form_status)
                VALUES ('Учебный специалист','Оқу маманы','учебного специалиста',
                        'оқу маманының','confirmed') RETURNING position_id
            """)).scalar_one()
        positions["hire"] = int(hire_position)
        roles = {}
        for code, name in (("LEARN_HR", "Учебный кадровик"),
                           ("TRAINING_HEAD_LOCAL", "Учебный заведующий отделением"),
                           ("QM_TRAINING_EXPERT", "Эксперт по внутреннему обучению и аттестации"),
                           ("LEARN_SIGNATORY", "Учебный подписант приказа"),
                           ("LEARN_CANDIDATE", "Учебный кандидат и сотрудник")):
            conn.execute(text("""
                INSERT INTO public.roles(name,code,is_active)
                VALUES (:name,:code,TRUE) ON CONFLICT(code) DO NOTHING
            """), {"name": name, "code": code})
            roles[code] = conn.execute(text("SELECT role_id FROM public.roles WHERE code=:code"),
                                       {"code": code}).scalar_one()

        def employee_user(login: str, name: str, role: int, position: int) -> tuple[int, int]:
            row = conn.execute(text("SELECT user_id,employee_id FROM public.users WHERE login=:login"),
                               {"login": login}).first()
            if row is not None:
                return int(row.user_id), int(row.employee_id)
            person = conn.execute(text("""
                INSERT INTO public.persons(full_name,match_key,person_status,source)
                VALUES (:name,:key,'active','manual') RETURNING person_id
            """), {"name": name, "key": f"learn-demo:{login}"}).scalar_one()
            employee = conn.execute(text("""
                INSERT INTO public.employees(full_name,position_id,org_unit_id,person_id,
                                             employment_rate,is_active,operational_status)
                VALUES (:name,:position,:unit,:person,1.0,TRUE,'active') RETURNING employee_id
            """), {"name": name, "position": position, "unit": unit, "person": person}).scalar_one()
            conn.execute(text("""
                INSERT INTO public.person_assignments
                  (person_id,org_unit_id,position_id,employment_type,rate,start_date,
                   active_flag,is_primary,lifecycle_status,assignment_key,source)
                VALUES (:person,:unit,:position,'primary',1.0,CURRENT_DATE,TRUE,TRUE,
                        'active',:key,'manual')
            """), {"person": person, "unit": unit, "position": position,
                   "key": f"learn-demo:{login}"})
            user_id = conn.execute(text("""
                INSERT INTO public.users(full_name,role_id,unit_id,employee_id,is_active,login,password_hash)
                VALUES (:name,:role,:unit,:employee,TRUE,:login,:password) RETURNING user_id
            """), {"name": name, "role": role, "unit": unit, "employee": employee,
                   "login": login, "password": hash_password(credentials[login])}).scalar_one()
            return int(user_id), int(employee)

        people = {}
        for login, name in (("learn.hr.a", "Учебный кадровик А"),
                            ("learn.hr.b", "Учебный кадровик Б")):
            people[login] = employee_user(login, name, roles["LEARN_HR"], positions["hr"])[0]
        source_id, manager_employee = employee_user("learn.manager", "Учебный руководитель",
            roles["TRAINING_HEAD_LOCAL"], positions["manager"])
        people["learn.manager"] = int(source_id)
        signatory_id, signatory_employee = employee_user(
            "learn.signatory", "Учебный подписант", roles["LEARN_SIGNATORY"], positions["manager"])
        people["learn.signatory"] = signatory_id
        for login, name in (("learn.candidate.a", "Учебный кандидат А"),
                            ("learn.candidate.b", "Учебный кандидат Б")):
            candidate = conn.execute(text("SELECT user_id FROM public.users WHERE login=:login"),
                                     {"login": login}).scalar_one_or_none()
            if candidate is None:
                candidate = conn.execute(text("""
                    INSERT INTO public.users(full_name,role_id,unit_id,is_active,login,password_hash)
                    VALUES (:name,:role,:unit,TRUE,:login,:password) RETURNING user_id
                """), {"name": name, "role": roles["LEARN_CANDIDATE"], "unit": unit,
                       "login": login, "password": hash_password(credentials[login])}).scalar_one()
            people[login] = int(candidate)
        target_id = conn.execute(text("SELECT user_id FROM public.users WHERE login='learn.manager_test'")).scalar_one_or_none()
        if target_id is None:
            target_id = conn.execute(text("""
                INSERT INTO public.users(full_name,role_id,unit_id,is_active,login)
                VALUES ('Учебный руководитель',:role,:unit,TRUE,'learn.manager_test') RETURNING user_id
            """), {"role": roles["TRAINING_HEAD_LOCAL"], "unit": unit}).scalar_one()
            conn.execute(text("""
                INSERT INTO public.training_identity_links(training_user_id,source_user_id,source_kind)
                VALUES (:target,:source,'local')
            """), {"target": target_id, "source": source_id})
        if conn.execute(text("SELECT source_user_id FROM public.training_identity_links WHERE training_user_id=:id"),
                        {"id": target_id}).scalar_one() != source_id:
            raise SystemExit("Manager identity link differs from the expected source")
        conn.execute(text("""
            INSERT INTO public.org_unit_managers(unit_id,user_id,manager_type,date_from,is_active)
            SELECT :unit,:user,'HEAD',CURRENT_DATE,TRUE
            WHERE NOT EXISTS (SELECT 1 FROM public.org_unit_managers
                              WHERE unit_id=:unit AND user_id=:user AND manager_type='HEAD' AND is_active)
        """), {"unit": unit, "user": target_id})
        people["learn.manager_test"] = int(target_id)
        expert = conn.execute(text("SELECT user_id FROM public.users WHERE login='learn.expert'")).scalar_one_or_none()
        if expert is None:
            expert = conn.execute(text("""
                INSERT INTO public.users(full_name,role_id,unit_id,is_active,login,password_hash)
                VALUES ('Учебный эксперт',:role,:unit,TRUE,'learn.expert',:password)
                RETURNING user_id
            """), {"role": roles["QM_TRAINING_EXPERT"], "unit": unit,
                   "password": hash_password(credentials["learn.expert"])}).scalar_one()
        people["learn.expert"] = int(expert)
        substitute = conn.execute(text("SELECT user_id FROM public.users WHERE login='learn.substitute'")).scalar_one_or_none()
        if substitute is None:
            substitute = conn.execute(text("""
                INSERT INTO public.users(full_name,role_id,unit_id,is_active,login,password_hash)
                VALUES ('Учебный замещающий эксперт',:role,:unit,TRUE,'learn.substitute',:password)
                RETURNING user_id
            """), {"role": roles["QM_TRAINING_EXPERT"], "unit": unit,
                   "password": hash_password(credentials["learn.substitute"])}).scalar_one()
        people["learn.substitute"] = int(substitute)
        for code in ("LEARNING_EXPERT", "LEARNING_MANUAL_REVIEW"):
            conn.execute(text("""
                INSERT INTO public.access_grants
                  (access_role_id,target_type,target_id,granted_by_user_id,reason)
                SELECT ar.access_role_id,'USER',:expert,:grantor,'Training acceptance'
                FROM public.access_roles ar WHERE ar.code=:code
                  AND NOT EXISTS (SELECT 1 FROM public.access_grants g
                    WHERE g.access_role_id=ar.access_role_id AND g.target_type='USER'
                      AND g.target_id=:expert AND g.active_flag AND g.revoked_at IS NULL)
            """), {"expert": expert, "grantor": expert, "code": code})
        conn.execute(text("""
            INSERT INTO public.access_grants
              (access_role_id,target_type,target_id,granted_by_user_id,reason)
            SELECT ar.access_role_id,'USER',:substitute,:grantor,'Training substitute acceptance'
            FROM public.access_roles ar WHERE ar.code='LEARNING_EXPERT'
              AND NOT EXISTS (SELECT 1 FROM public.access_grants g
                WHERE g.access_role_id=ar.access_role_id AND g.target_type='USER'
                  AND g.target_id=:substitute AND g.active_flag AND g.revoked_at IS NULL)
        """), {"substitute": substitute, "grantor": expert})
        hr_role = conn.execute(text("SELECT role_id FROM public.roles WHERE code='HR_HEAD'")).scalar_one()
        conn.execute(text("""
            INSERT INTO public.users(full_name,role_id,unit_id,is_active,login)
            SELECT 'Учебный кадровый партнёр',:role,:unit,TRUE,'training_hr_partner_20261121'
            WHERE NOT EXISTS (SELECT 1 FROM public.users WHERE login='training_hr_partner_20261121')
        """), {"role": hr_role, "unit": unit})
    if credentials_updated:
        credentials_file.parent.mkdir(parents=True, exist_ok=True)
        credentials_file.write_text(json.dumps(credentials, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(credentials_file, 0o600)
    print(json.dumps({"database": database, "unit_id": unit, "parent_unit_id": disp,
                      "position_id": positions["hire"], "users": people,
                      "manager_employee_id": manager_employee,
                      "signatory_employee_id": signatory_employee}, ensure_ascii=False))


if __name__ == "__main__":
    main()
