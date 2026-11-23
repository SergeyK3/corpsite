"""Apply Corpsite migrations to a new isolated training DB with fictional seed refs.

Existing Corpsite migrations assume HR_HEAD, ADMIN and a DISP unit exist.
This script pauses at their first data-dependent revision, seeds only those
reference rows, then applies the remaining migrations. No live HR rows are copied.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
BASE_REVISION = "h5c6d7e8f9a0"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rehearsal", action="store_true")
    args = parser.parse_args()
    url = make_url(os.environ["DATABASE_URL"])
    dbname = url.database or ""
    if url.host not in {"127.0.0.1", "localhost", "::1"} or (
        dbname != "corpsite_learn" and not (args.rehearsal and dbname.startswith("corpsite_learn_"))
    ):
        raise SystemExit("Refusing to bootstrap a non-training database")
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
    with create_engine(url).connect() as conn:
        has_version = conn.execute(text("SELECT to_regclass('public.alembic_version') IS NOT NULL")).scalar_one()
        revision = conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one_or_none() if has_version else None
    if revision not in (None, BASE_REVISION, "learning006", "learning007", "learning008"):
        raise SystemExit(f"Unexpected partial schema revision: {revision}")
    if revision is None:
        command.upgrade(config, BASE_REVISION)
    if revision != "learning008":
        with create_engine(url).begin() as conn:
            groups = set(conn.execute(text("SELECT group_id FROM public.deps_group WHERE group_id IN (2,3)")).scalars())
            if groups != {2, 3}:
                raise SystemExit("Expected fictional group reference IDs 2 and 3")
            for code, name in (("HR_HEAD", "Учебный кадровый руководитель"), ("ADMIN", "Учебный администратор")):
                conn.execute(text("INSERT INTO public.roles(name,code) VALUES (:name,:code) ON CONFLICT(code) DO NOTHING"),
                             {"name": name, "code": code})
            hr_role = conn.execute(text("SELECT role_id FROM public.roles WHERE code='HR_HEAD'")).scalar_one()
            conn.execute(text("""
                INSERT INTO public.users(full_name,role_id,is_active,login)
                SELECT 'Учебный системный грантор',:role,TRUE,'learn-bootstrap'
                WHERE NOT EXISTS (SELECT 1 FROM public.users WHERE login='learn-bootstrap')
            """), {"role": hr_role})
            root = conn.execute(text("SELECT unit_id FROM public.org_units WHERE code='LEARN-ROOT'")).scalar_one_or_none()
            if root is None:
                root = conn.execute(text("""
                    INSERT INTO public.org_units(name,code,is_active)
                    VALUES ('Учебная организация','LEARN-ROOT',TRUE) RETURNING unit_id
                """)).scalar_one()
            disp = conn.execute(text("SELECT unit_id FROM public.org_units WHERE code='DISP'")).scalar_one_or_none()
            if disp is None:
                conn.execute(text("""
                    INSERT INTO public.org_units(name,code,parent_unit_id,group_id,is_active)
                    VALUES ('Учебная диспетчерская','DISP',:parent,2,TRUE)
                """), {"parent": root})
        command.upgrade(config, "head")
    with create_engine(url).connect() as conn:
        if conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() != "learning008":
            raise SystemExit("Schema did not reach learning008")
    print(f"Schema ready: {dbname}, learning008")


if __name__ == "__main__":
    main()
