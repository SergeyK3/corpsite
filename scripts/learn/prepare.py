"""Guarded, repeatable bootstrap for an isolated, synthetic learning database.

Usage: set LEARN_DATABASE_URL, DATABASE_URL (the same URL), LEARN_STORAGE_ROOT,
PERSONNEL_PHOTO_STORAGE_ROOT and PERSONNEL_FILE_STORAGE_ROOT; run check, then
apply. Never point this script at an existing Corpsite environment.
"""
from __future__ import annotations

import argparse
import base64
from datetime import date
import hashlib
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HEAD = "pfiles002"
HISTORICAL = "h5c6d7e8f9a0"
INTERMEDIATE = "ptype002"


def fail(message: str) -> None:
    raise SystemExit(f"learn preparation: {message}")


def setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"{name} is required")
    return value


def target(local_test: bool):
    url = setting("LEARN_DATABASE_URL")
    parsed = urlparse(url)
    name = parsed.path.removeprefix("/")
    if parsed.scheme not in {"postgresql", "postgresql+psycopg2"} or parsed.query or parsed.fragment:
        fail("database URL must be plain PostgreSQL without query or fragment")
    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        fail("database must be reached over loopback")
    if not parsed.password or parsed.password.startswith("REPLACE_"):
        fail("database password is missing or still a placeholder")
    if local_test:
        match = re.fullmatch(r"corpsite_learn_([0-9a-f]{12})_test", name)
        if not match:
            fail("local rehearsal requires a unique corpsite_learn_*_test database")
        if os.name != "nt" or parsed.username != f"learn_rehearsal_{match.group(1)}":
            fail("simulated scan is allowed only for the Windows disposable rehearsal role")
    elif name != "corpsite_learn":
        fail("target database must be exactly corpsite_learn")
    elif parsed.username != "corpsite_learn_app":
        fail("server database URL must use corpsite_learn_app")
    if os.environ.get("DATABASE_URL") != url:
        fail("DATABASE_URL must exactly match LEARN_DATABASE_URL")
    return url, name


def checked_paths(local_test: bool) -> None:
    base = Path(setting("LEARN_STORAGE_ROOT")).resolve()
    photo = Path(setting("PERSONNEL_PHOTO_STORAGE_ROOT")).resolve()
    files = Path(setting("PERSONNEL_FILE_STORAGE_ROOT")).resolve()
    if not all(p.is_absolute() and p != base and p.is_relative_to(base) for p in (photo, files)):
        fail("photo and file storage must be distinct children of LEARN_STORAGE_ROOT")
    if photo == files or photo.is_relative_to(files) or files.is_relative_to(photo):
        fail("photo and file storage overlap")
    if photo != base / "photos" or files != base / "files":
        fail("photo and file storage must be exact learn paths")
    if local_test and (base.parent != Path(tempfile.gettempdir()).resolve()
                       or not base.name.startswith("corpsite-learn-")):
        fail("local rehearsal storage must be a dedicated temporary directory")
    if not local_test and base != Path("/var/lib/corpsite-learn"):
        fail("server storage root must be /var/lib/corpsite-learn")
    if not base.is_dir() or not photo.is_dir() or not files.is_dir():
        fail("storage directories must exist before migration")
    for path in (base, photo, files):
        if path.is_symlink():
            fail(f"storage path may not be a symlink: {path}")
        if not local_test and path.stat().st_mode & 0o077:
            fail(f"storage path is accessible to group or others: {path}")
        if not local_test and path.stat().st_uid != os.getuid():
            fail(f"storage path must be owned by the service user: {path}")


def checked_integrations(local_test: bool) -> None:
    if local_test:
        return
    if os.environ.get("APP_ENV") not in {"prod", "production"}:
        fail("APP_ENV must be prod or production")
    secret_names = ("AUTH_JWT_SECRET", "INTERNAL_API_TOKEN", "BOT_BIND_TOKEN",
                    "PERSONNEL_INTAKE_TOKEN_ENCRYPTION_KEY")
    secret_values = [os.environ.get(name, "") for name in secret_names]
    for name, value in zip(secret_names, secret_values):
        if value in {"", "change-me", "dev-secret-change-me"} or value.startswith("REPLACE_"):
            fail(f"{name} must be unique and non-default")
    if len(set(secret_values)) != len(secret_values):
        fail("learn application secrets must be distinct")
    for name in ("BOT_TOKEN", "INTAKE_BOT_TOKEN", "TELEGRAM_BOT_TOKEN",
                 "SMTP_HOST", "SMTP_USER"):
        if os.environ.get(name):
            fail(f"{name} must be unset for learn")
    command_line = setting("PERSONNEL_FILE_SCAN_COMMAND")
    command = shlex.split(command_line)
    if command != ["/usr/bin/clamscan", "--no-summary"] or not shutil.which(command[0]):
        fail("server scanner must be /usr/bin/clamscan --no-summary")
    version = subprocess.run([command[0], "--version"], capture_output=True, timeout=10)
    if version.returncode != 0:
        fail("ClamAV version check failed")
    if not any(Path("/var/lib/clamav").glob("*.cvd")) and not any(
        Path("/var/lib/clamav").glob("*.cld")
    ):
        fail("ClamAV signature database is absent")


def config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def revision(conn) -> str | None:
    if conn.execute(text("SELECT to_regclass('public.alembic_version')")).scalar_one() is None:
        count = conn.execute(text(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
        )).scalar_one()
        if count:
            fail("nonempty database has no alembic_version")
        return None
    rows = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    if len(rows) != 1:
        fail("expected exactly one Alembic revision")
    return rows[0]


def preflight(url: str, name: str, local_test: bool):
    checked_paths(local_test)
    checked_integrations(local_test)
    cfg = config(url)
    heads = ScriptDirectory.from_config(cfg).get_heads()
    if heads != [HEAD]:
        fail(f"unexpected Alembic heads: {heads}")
    engine = create_engine(url, hide_parameters=True)
    with engine.connect() as conn:
        actual = conn.execute(text("SELECT current_database(), current_user")).one()
        if actual[0] != name:
            fail("connected database name differs from URL")
        if not local_test and actual[1] != "corpsite_learn_app":
            fail("server connection must use corpsite_learn_app")
        if local_test and actual[1] != urlparse(url).username:
            fail("local rehearsal must connect as its disposable role")
        current = revision(conn)
    if current not in {None, HISTORICAL, INTERMEDIATE, HEAD}:
        fail(f"unexpected database revision: {current}")
    return cfg, engine, current


def historical_seed(engine) -> None:
    # Historical i6/j7 migrations require these synthetic predecessors.
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO roles(code,name) VALUES
              ('HR_HEAD','[LEARN] Migration role'),('ADMIN','[LEARN] Admin role')
            ON CONFLICT(code) DO NOTHING
        """))
        role = conn.execute(text("SELECT role_id FROM roles WHERE code='HR_HEAD'")).scalar_one()
        if not conn.execute(text("SELECT 1 FROM users WHERE login='learn.migration'")).first():
            conn.execute(text("""
                INSERT INTO users(full_name,role_id,login,is_active)
                VALUES('[LEARN] Migration actor',:role,'learn.migration',true)
            """), {"role": role})
        conn.execute(text("""
            INSERT INTO org_units(code,name,is_active)
            VALUES('LEARN_ROOT','[LEARN] Organization',true)
            ON CONFLICT(code) DO NOTHING
        """))
        parent = conn.execute(text("SELECT unit_id FROM org_units WHERE code='LEARN_ROOT'")).scalar_one()
        conn.execute(text("""
            INSERT INTO org_units(code,name,parent_unit_id,is_active,group_id)
            VALUES('DISP','[LEARN] Department',:parent,true,1)
            ON CONFLICT(code) DO NOTHING
        """), {"parent": parent})


def migrate(cfg, engine, current) -> None:
    if current is None:
        command.upgrade(cfg, HISTORICAL)
        current = HISTORICAL
    if current == HISTORICAL:
        historical_seed(engine)
        command.upgrade(cfg, INTERMEDIATE)
        current = INTERMEDIATE
    if current == INTERMEDIATE:
        command.upgrade(cfg, HEAD)
    command.upgrade(cfg, HEAD)  # repeat upgrade must be harmless
    with engine.connect() as conn:
        if revision(conn) != HEAD:
            fail("migration did not reach pfiles002")


def one(conn, select_sql: str, insert_sql: str, params: dict) -> int:
    existing = conn.execute(text(select_sql), params).scalar_one_or_none()
    if existing is not None:
        return existing
    return conn.execute(text(insert_sql), params).scalar_one()


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000, dklen=32)
    encode = lambda data: base64.urlsafe_b64encode(data).decode().rstrip("=")
    return f"pbkdf2$200000${encode(salt)}${encode(digest)}"


def synthetic_seed(engine, local_test: bool) -> dict:
    password_names = ("LEARN_WORKER_PASSWORD", "LEARN_HR_PASSWORD", "LEARN_OUTSIDER_PASSWORD")
    passwords = {key: os.environ.get(key) or secrets.token_urlsafe(32) for key in password_names}
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO roles(code,name) VALUES
              ('LEARN_WORKER','[LEARN] Worker'),('LEARN_HR','[LEARN] HR')
            ON CONFLICT(code) DO NOTHING
        """))
        root = conn.execute(text("SELECT unit_id FROM org_units WHERE code='LEARN_ROOT'")).scalar_one()
        conn.execute(text("""
            INSERT INTO org_units(code,name,parent_unit_id,is_active,group_id)
            VALUES('LEARN_OTHER','[LEARN] Other department',:parent,true,1)
            ON CONFLICT(code) DO NOTHING
        """), {"parent": root})
        units = {code: conn.execute(text("SELECT unit_id FROM org_units WHERE code=:code"), {"code": code}).scalar_one()
                 for code in ("DISP", "LEARN_OTHER")}
        position = one(conn, "SELECT position_id FROM positions WHERE name='[LEARN] Employee'",
                       "INSERT INTO positions(name,category) VALUES('[LEARN] Employee','other') RETURNING position_id", {})
        accounts = {}
        specs = (
            ("worker", "learn.worker", "[LEARN] Алима Работник", "LEARN_WORKER", "DISP"),
            ("hr", "learn.hr", "[LEARN] Дана Кадровик", "LEARN_HR", "DISP"),
            ("outsider", "learn.outsider", "[LEARN] Мира Посторонняя", "LEARN_WORKER", "LEARN_OTHER"),
        )
        for label, login, full_name, role_code, unit_code in specs:
            role = conn.execute(text("SELECT role_id FROM roles WHERE code=:code"), {"code": role_code}).scalar_one()
            person = one(conn, "SELECT person_id FROM persons WHERE match_key=:key",
                         """INSERT INTO persons(full_name,last_name,first_name,match_key,source)
                            VALUES(:name,'Учебная',:first,:key,'manual') RETURNING person_id""",
                         {"key": login, "name": full_name, "first": label})
            employee = one(conn, "SELECT employee_id FROM employees WHERE person_id=:pid AND is_active",
                           """INSERT INTO employees(full_name,person_id,org_unit_id,position_id,
                               employment_rate,is_active,date_from)
                              VALUES(:name,:pid,:unit,:pos,1,true,'2024-01-01') RETURNING employee_id""",
                           {"name": full_name, "pid": person, "unit": units[unit_code], "pos": position})
            user = one(conn, "SELECT user_id FROM users WHERE login=:login",
                       """INSERT INTO users(full_name,login,password_hash,role_id,unit_id,employee_id,is_active)
                          VALUES(:name,:login,:hash,:role,:unit,:eid,true) RETURNING user_id""",
                       {"name": full_name, "login": login,
                        "hash": password_hash(passwords[f"LEARN_{label.upper()}_PASSWORD"]),
                        "role": role, "unit": units[unit_code], "eid": employee})
            accounts[label] = {"user_id": user, "role_id": role, "employee_id": employee,
                               "role_code": role_code, "person_id": person}
        hr = accounts["hr"]["user_id"]
        conn.execute(text("""
            INSERT INTO access_grants(access_role_id,target_type,target_id,scope_type,scope_id,
                                      granted_by_user_id,reason)
            SELECT ar.access_role_id,'USER',:uid,'ORG_UNIT',:unit,:uid,'[LEARN] File review'
            FROM access_roles ar WHERE ar.code='PERSONNEL_FILES_REVIEW'
              AND NOT EXISTS(SELECT 1 FROM access_grants g WHERE g.access_role_id=ar.access_role_id
                             AND g.target_type='USER' AND g.target_id=:uid AND g.active_flag)
        """), {"uid": hr, "unit": units["DISP"]})
        group = conn.execute(text("SELECT group_id FROM medical_specialty_groups WHERE code='DOCTOR'")).scalar_one()
        for code, name in (("LEARN_A", "[LEARN] Specialty A"), ("LEARN_B", "[LEARN] Specialty B")):
            conn.execute(text("""
                INSERT INTO medical_specialties(group_id,code,name,is_active)
                VALUES(:group,:code,:name,true)
                ON CONFLICT ON CONSTRAINT uq_medical_specialties_group_code DO NOTHING
            """), {"group": group, "code": code, "name": name})
        specialty = {code: conn.execute(text(
            "SELECT medical_specialty_id FROM medical_specialties WHERE group_id=:group AND code=:code"
        ), {"group": group, "code": code}).scalar_one() for code in ("LEARN_A", "LEARN_B")}
        editions = {}
        for code, day in (("LEARN-OLD", "2020-01-01"), ("LEARN-NEW", "2025-01-01")):
            editions[code] = one(conn, "SELECT edition_id FROM certificate_classifier_editions WHERE code=:code",
                                 """INSERT INTO certificate_classifier_editions
                                    (code,title,source_reference,effective_from,created_by)
                                    VALUES(:code,:title,'[LEARN] Fictional classifier',:day,:uid)
                                    RETURNING edition_id""",
                                 {"code": code, "title": code, "day": day, "uid": hr})
        entries = {}
        for edition, spec, code in (("LEARN-OLD", "LEARN_A", "OLD-A"),
                                    ("LEARN-OLD", "LEARN_B", "OLD-B"),
                                    ("LEARN-NEW", "LEARN_A", "NEW-A"),
                                    ("LEARN-NEW", "LEARN_B", "NEW-B")):
            entries[code] = one(conn,
                "SELECT entry_id FROM certificate_classifier_entries WHERE edition_id=:edition AND specialty_code=:code",
                """INSERT INTO certificate_classifier_entries
                   (edition_id,medical_specialty_id,specialty_code,specialty_name)
                   VALUES(:edition,:specialty,:code,:name) RETURNING entry_id""",
                {"edition": editions[edition], "specialty": specialty[spec],
                 "code": code, "name": f"[LEARN] {spec}"})
        conn.execute(text("""
            INSERT INTO certificate_specialty_mappings
              (from_entry_id,to_entry_id,source_reference,reason,effective_from,confirmed_by)
            SELECT :old,:new,'[LEARN] Fictional protocol','[LEARN] Same specialty','2025-01-01',:uid
            WHERE NOT EXISTS(SELECT 1 FROM certificate_specialty_mappings
                             WHERE from_entry_id=:old AND to_entry_id=:new)
        """), {"old": entries["OLD-A"], "new": entries["NEW-A"], "uid": hr})
        docs = {}
        for label, code, entry in (("A", "LEARN_A", "OLD-A"), ("B", "LEARN_B", "OLD-B")):
            docs[label] = one(conn,
                "SELECT document_id FROM employee_documents WHERE employee_id=:eid AND document_number=:number",
                """INSERT INTO employee_documents
                  (employee_id,document_type_id,medical_specialty_id,certificate_entry_id,
                   specialty_name_at_issue,issued_at,valid_until,document_number,issued_by,
                   lifecycle_status,verification_status,created_by)
                  SELECT :eid,document_type_id,:specialty,:entry,:name,'2024-01-01','2031-01-01',
                         :number,'[LEARN] Fictional issuer','ACTIVE','VERIFIED',:uid
                  FROM document_types WHERE code='SPECIALIST_CERTIFICATION' RETURNING document_id""",
                {"eid": accounts["worker"]["employee_id"], "number": f"LEARN-{label}-OLD",
                 "specialty": specialty[code], "entry": entries[entry],
                 "name": f"[LEARN] {code} as issued", "uid": hr})
    return {"accounts": accounts, "entries": entries, "documents": docs}


def approved_files(engine, data: dict, local_test: bool) -> None:
    # The production path always invokes the configured real scanner.
    os.environ["CORPSITE_SKIP_DOTENV"] = "1"
    from app.personnel_files import service, storage
    import pymupdf
    if local_test:
        storage.scan = lambda _: None  # explicit disposable-DB rehearsal only
    worker = data["accounts"]["worker"]
    hr = data["accounts"]["hr"]
    for label, doc_id in data["documents"].items():
        with engine.connect() as conn:
            existing = conn.execute(text("""
                SELECT state FROM personnel_file_versions
                WHERE employee_document_id=:doc ORDER BY created_at DESC LIMIT 1
            """), {"doc": doc_id}).scalar_one_or_none()
        if existing in {"approved", "superseded"}:
            continue
        if existing is not None:
            fail(f"initial certificate {label} has a non-approved file; inspect manually")
        pdf = pymupdf.open()
        pdf.new_page().insert_text((72, 72), f"FICTIONAL LEARN CERTIFICATE {label}")
        content = pdf.tobytes()
        pdf.close()
        row = service.submit(worker, worker["person_id"], kind="certificate",
            title=f"[LEARN] Certificate {label}", content=content, mime="application/pdf",
            filename=f"learn-{label.lower()}-old.pdf",
            certificate={"employee_document_id": doc_id})
        comparison = service.review_context(hr, str(row["version_id"]))
        service.decide(hr, str(row["version_id"]), expected_revision=row["revision"],
                       action="approve", reason="[LEARN] Initial synthetic certificate",
                       expected_certificate_context=comparison["context_token"])
    with engine.connect() as conn:
        statuses = conn.execute(text("""
            SELECT document_number,lifecycle_status,verification_status
            FROM employee_documents WHERE document_id IN (:a,:b)
        """), {"a": data["documents"]["A"], "b": data["documents"]["B"]}).all()
        by_number = {r[0]: (r[1], r[2]) for r in statuses}
        if (by_number.get("LEARN-B-OLD") != ("ACTIVE", "VERIFIED") or
                by_number.get("LEARN-A-OLD") not in {
                    ("ACTIVE", "VERIFIED"), ("SUPERSEDED", "VERIFIED")
                }):
            fail("initial certificate statuses are unexpected")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "apply"))
    parser.add_argument("--env-file", type=Path, help="private backend.env for CLI invocation")
    parser.add_argument("--password-file", type=Path, help="private one-time fictional login passwords")
    parser.add_argument("--local-test", action="store_true",
                        help="allow only a unique loopback *_test DB; simulated scan only there")
    args = parser.parse_args()
    for path in (args.env_file, args.password_file):
        if path is None:
            continue
        if not path.is_file():
            fail(f"environment file does not exist: {path}")
        if os.name == "posix" and (path.stat().st_mode & 0o077 or path.stat().st_uid != os.getuid()):
            fail(f"environment file must be private and owned by current user: {path}")
        load_dotenv(path, override=False)
    url, name = target(args.local_test)
    cfg, engine, current = preflight(url, name, args.local_test)
    print(f"PASS preflight: database={name}, revision={current or 'empty'}, head={HEAD}")
    if args.action == "apply":
        if not args.local_test and any(not os.environ.get(key) for key in
                ("LEARN_WORKER_PASSWORD", "LEARN_HR_PASSWORD", "LEARN_OUTSIDER_PASSWORD")):
            if current != HEAD:
                fail("all three LEARN_*_PASSWORD values are required before migration")
            with engine.connect() as conn:
                existing = conn.execute(text("""
                    SELECT count(*) FROM users
                    WHERE login IN ('learn.worker','learn.hr','learn.outsider')
                      AND password_hash IS NOT NULL
                """)).scalar_one()
            if existing != 3:
                fail("all three LEARN_*_PASSWORD values are required to finish bootstrap")
        migrate(cfg, engine, current)
        data = synthetic_seed(engine, args.local_test)
        approved_files(engine, data, args.local_test)
        print("PASS bootstrap: pfiles002; three fictional accounts; two editions; A/B approved")
    engine.dispose()


if __name__ == "__main__":
    main()
