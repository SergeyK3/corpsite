"""Disposable local PostgreSQL rehearsal; creates and drops only its own DB."""
from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from uuid import uuid4

import pymupdf
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
CONTAINER = "corpsite-pg"


def admin_sql(statement: str) -> None:
    # Socket access inside the local container; no existing database is modified.
    subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres",
                    "-v", "ON_ERROR_STOP=1", "-d", "postgres"],
                   input=statement, text=True, capture_output=True, check=True)


def actor(conn, login):
    row = conn.execute(text("""
        SELECT u.user_id,u.role_id,u.employee_id,e.person_id,r.code AS role_code
        FROM users u JOIN roles r USING(role_id)
        JOIN employees e ON e.employee_id=u.employee_id WHERE u.login=:login
    """), {"login": login}).mappings().one()
    return dict(row)


def pdf_bytes():
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "FICTIONAL LEARN REPLACEMENT A")
    result = doc.tobytes()
    doc.close()
    return result


def seed_counts(url):
    engine = create_engine(url, hide_parameters=True)
    with engine.connect() as conn:
        counts = tuple(conn.execute(text(query)).scalar_one() for query in (
            "SELECT count(*) FROM users WHERE login IN ('learn.worker','learn.hr','learn.outsider')",
            "SELECT count(*) FROM certificate_classifier_editions WHERE code LIKE 'LEARN-%'",
            "SELECT count(*) FROM certificate_classifier_entries WHERE specialty_code IN ('OLD-A','OLD-B','NEW-A','NEW-B')",
            "SELECT count(*) FROM certificate_specialty_mappings m JOIN certificate_classifier_entries e ON e.entry_id=m.from_entry_id WHERE e.specialty_code='OLD-A'",
            "SELECT count(*) FROM employee_documents WHERE document_number IN ('LEARN-A-OLD','LEARN-B-OLD')",
            "SELECT count(*) FROM personnel_file_versions v JOIN employee_documents d ON d.document_id=v.employee_document_id WHERE d.document_number IN ('LEARN-A-OLD','LEARN-B-OLD')",
        ))
    engine.dispose()
    return counts


def flow(url, storage_root, passwords):
    os.environ["DATABASE_URL"] = url
    os.environ["CORPSITE_SKIP_DOTENV"] = "1"
    os.environ["PERSONNEL_FILE_STORAGE_ROOT"] = str(storage_root / "files")
    from app.personnel_files import service, storage
    from app.personnel_files.access import self_person
    from app.auth import verify_password
    from fastapi import HTTPException
    engine = create_engine(url, hide_parameters=True)
    with engine.connect() as conn:
        worker = actor(conn, "learn.worker")
        hr = actor(conn, "learn.hr")
        outsider = actor(conn, "learn.outsider")
        docs = dict(conn.execute(text("""
            SELECT document_number,document_id FROM employee_documents
            WHERE document_number IN ('LEARN-A-OLD','LEARN-B-OLD')
        """)).all())
        new_entry = conn.execute(text("""
            SELECT entry_id FROM certificate_classifier_entries
            WHERE specialty_code='NEW-A'
        """)).scalar_one()
        old = conn.execute(text("""
            SELECT version_id,set_id,revision FROM personnel_file_versions
            WHERE employee_document_id=:id AND state='approved'
        """), {"id": docs["LEARN-A-OLD"]}).mappings().one()
        for label in ("worker", "hr", "outsider"):
            stored = conn.execute(text("SELECT password_hash FROM users WHERE login=:login"),
                                  {"login": f"learn.{label}"}).scalar_one()
            assert verify_password(passwords[label], stored)
    assert self_person(worker) == worker["person_id"]
    with engine.connect() as conn:
        version_count = conn.execute(text("SELECT count(*) FROM personnel_file_versions")).scalar_one()
    os.environ["PERSONNEL_FILE_SCAN_COMMAND"] = "learn-clamscan-unavailable"
    try:
        service.submit(worker, worker["person_id"], kind="certificate",
            title="[LEARN] Scanner failure", content=pdf_bytes(), mime="application/pdf",
            filename="scanner-failure.pdf",
            certificate={"entry_id": new_entry, "specialty_name_at_issue": "[LEARN] A",
                         "issued_at": date(2026, 1, 1), "valid_until": date(2032, 1, 1)})
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("upload succeeded without a scanner")
    finally:
        os.environ.pop("PERSONNEL_FILE_SCAN_COMMAND", None)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM personnel_file_versions")).scalar_one() == version_count
    print("PASS normal upload returns HTTP 503 without ClamAV and writes no file version")
    storage.scan = lambda _: None  # disposable local rehearsal, never server bootstrap
    try:
        service.listing(outsider, worker["person_id"])
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("outsider could read another employee's files")
    cert = {"entry_id": new_entry, "specialty_name_at_issue": "[LEARN] A as issued",
            "issued_at": date(2026, 1, 1), "valid_until": date(2032, 1, 1)}
    def submit(previous):
        return service.submit(worker, worker["person_id"], kind="certificate",
            title="[LEARN] Replacement A", content=pdf_bytes(), mime="application/pdf",
            filename="learn-a-replacement.pdf", certificate=cert, set_id=previous["set_id"],
            expected_version_id=previous["version_id"], expected_revision=previous["revision"])
    pending = submit(old)
    returned = service.decide(hr, str(pending["version_id"]),
        expected_revision=pending["revision"], action="return",
        reason="[LEARN] Synthetic return for correction")
    with engine.connect() as conn:
        before = {r[0]: r[1:] for r in conn.execute(text("""
            SELECT document_id,lifecycle_status,verification_status
            FROM employee_documents WHERE document_id IN (:a,:b,:returned)
        """), {"a": docs["LEARN-A-OLD"], "b": docs["LEARN-B-OLD"],
               "returned": returned["employee_document_id"]}).all()}
    assert before[docs["LEARN-A-OLD"]] == ("ACTIVE", "VERIFIED")
    assert before[docs["LEARN-B-OLD"]] == ("ACTIVE", "VERIFIED")
    assert before[returned["employee_document_id"]] == ("DRAFT", "REJECTED")
    print("PASS after return: old A/B ACTIVE/VERIFIED; returned A DRAFT/REJECTED")
    pending = submit(returned)
    comparison = service.review_context(hr, str(pending["version_id"]))
    assert comparison["can_approve"] and comparison["basis"]["kind"] == "confirmed_mapping"
    approved = service.decide(hr, str(pending["version_id"]),
        expected_revision=pending["revision"], action="approve", reason="",
        expected_certificate_context=comparison["context_token"])
    with engine.connect() as conn:
        rows = {r[0]: r[1:] for r in conn.execute(text("""
            SELECT document_id,lifecycle_status,verification_status FROM employee_documents
            WHERE document_id IN (:a,:b,:returned,:new)
        """), {"a": docs["LEARN-A-OLD"], "b": docs["LEARN-B-OLD"],
               "returned": returned["employee_document_id"],
               "new": approved["employee_document_id"]}).all()}
    assert rows[docs["LEARN-A-OLD"]] == ("SUPERSEDED", "VERIFIED")
    assert rows[docs["LEARN-B-OLD"]] == ("ACTIVE", "VERIFIED")
    assert rows[returned["employee_document_id"]] == ("DRAFT", "REJECTED")
    assert rows[approved["employee_document_id"]] == ("ACTIVE", "VERIFIED")
    print("PASS after approval: old A SUPERSEDED; new A ACTIVE/VERIFIED; B ACTIVE/VERIFIED")
    engine.dispose()


def main():
    suffix = uuid4().hex[:12]
    name = f"corpsite_learn_{suffix}_test"
    user = f"learn_rehearsal_{suffix}"
    password = secrets.token_urlsafe(36)
    created = False
    try:
        admin_sql(f"CREATE ROLE {user} LOGIN PASSWORD '{password}';")
        created = True
        admin_sql(f"CREATE DATABASE {name} OWNER {user};")
        with tempfile.TemporaryDirectory(prefix="corpsite-learn-") as temp:
            storage = Path(temp)
            (storage / "photos").mkdir()
            (storage / "files").mkdir()
            url = URL.create("postgresql+psycopg2", username=user, password=password,
                             host="127.0.0.1", database=name).render_as_string(hide_password=False)
            env = dict(os.environ, LEARN_DATABASE_URL=url, DATABASE_URL=url,
                       LEARN_STORAGE_ROOT=str(storage),
                       PERSONNEL_PHOTO_STORAGE_ROOT=str(storage / "photos"),
                       PERSONNEL_FILE_STORAGE_ROOT=str(storage / "files"))
            command = [sys.executable, str(ROOT / "scripts/learn/prepare.py")]
            passwords = {label: secrets.token_urlsafe(32) for label in ("worker", "hr", "outsider")}
            for label, value in passwords.items():
                env[f"LEARN_{label.upper()}_PASSWORD"] = value
            wrong_db = dict(env, LEARN_DATABASE_URL=url.replace(name, "corpsite"),
                            DATABASE_URL=url.replace(name, "corpsite"))
            rejected = subprocess.run([*command, "check", "--local-test"], cwd=ROOT,
                                      env=wrong_db, capture_output=True, text=True)
            assert rejected.returncode != 0 and "unique corpsite_learn_*_test" in rejected.stderr
            wrong_path = dict(env, PERSONNEL_FILE_STORAGE_ROOT=str(storage.parent / "other-files"))
            rejected = subprocess.run([*command, "check", "--local-test"], cwd=ROOT,
                                      env=wrong_path, capture_output=True, text=True)
            assert rejected.returncode != 0 and "storage" in rejected.stderr
            print("PASS preflight rejects wrong database and storage path before migration")
            for action in ("check", "apply", "apply"):
                subprocess.run([*command, action, "--local-test"], cwd=ROOT, env=env, check=True)
            before_counts = seed_counts(url)
            assert before_counts == (3, 2, 4, 1, 2, 2), before_counts
            flow(url, storage, passwords)
            after_flow_counts = seed_counts(url)
            subprocess.run([*command, "apply", "--local-test"], cwd=ROOT, env=env, check=True)
            assert seed_counts(url) == after_flow_counts
            print("PASS repeat preparation after completed replacement")
    finally:
        if created:
            admin_sql(f"DROP DATABASE IF EXISTS {name} WITH (FORCE); DROP ROLE IF EXISTS {user};")
    print("PASS disposable database dropped")


if __name__ == "__main__":
    main()
