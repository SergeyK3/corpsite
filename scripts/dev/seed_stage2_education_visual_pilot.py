#!/usr/bin/env python3
"""Seed the *local-only* Stage 2 education visual-review pilot.

The default is a read-only dry run.  Writes need both ``--apply`` and the
literal ``--confirm APPLY_STAGE2_VISUAL_PILOT``.  The script reads only
TEST_DATABASE_URL -- DATABASE_URL is deliberately ignored.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, make_url

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MARKER = "S2VISUAL20260909"
LOGIN = "local_stage2_visual_hr_head"
CONFIRM = "APPLY_STAGE2_VISUAL_PILOT"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
REPLACEMENT_STALE_KEY = "stale_replacement_2"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def hash_password(password: str, *, iters: int = 200_000) -> str:
    """Match the local auth PBKDF2 format without importing app.auth/ DATABASE_URL."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters, dklen=32)
    return f"pbkdf2${iters}${_b64url(salt)}${_b64url(digest)}"


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _url(raw: str | None):
    if not raw:
        raise SystemExit("Refusing: TEST_DATABASE_URL is required; DATABASE_URL is never used.")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or (url.host or "").lower() not in LOOPBACK or (url.database or "").lower() != "corpsite_test":
        raise SystemExit("Refusing: TEST_DATABASE_URL must be PostgreSQL loopback database corpsite_test.")
    return url


def _identity(conn: Connection) -> None:
    row = conn.execute(text("select current_database() db, inet_server_addr()::text server_address")).mappings().one()
    if row["db"] != "corpsite_test":
        raise RuntimeError("Refusing: server did not report corpsite_test.")
    # This check is intentionally separate from URL validation.  Docker PostgreSQL
    # commonly reports its bridge address; it is printed for an auditable pilot.
    if not row["server_address"]:
        raise RuntimeError("Refusing: PostgreSQL did not report its server address.")
    print(f"DB verified: corpsite_test; PostgreSQL server address: {row['server_address']}")


def _actor(conn: Connection, password: str) -> tuple[int, int]:
    role = conn.execute(text("select role_id from public.roles where code='HR_HEAD'")).scalar_one_or_none()
    unit = conn.execute(text("select unit_id from public.org_units where is_active=true order by unit_id limit 1")).scalar_one_or_none()
    if role is None or unit is None:
        raise RuntimeError("Refusing: corpsite_test lacks HR_HEAD role or active org unit.")
    existing = conn.execute(text("select user_id from public.users where login=:login"), {"login": LOGIN}).scalar_one_or_none()
    if existing is None:
        user_id = conn.execute(text("""insert into public.users(full_name,login,password_hash,role_id,unit_id,is_active)
          values(:name,:login,:password_hash,:role,:unit,true) returning user_id"""),
          {"name": f"{MARKER} local HR_HEAD", "login": LOGIN, "password_hash": hash_password(password), "role": role, "unit": unit}).scalar_one()
        conn.execute(text("insert into public.user_org_units(user_id,unit_id,is_active) values(:user,:unit,true) on conflict(user_id,unit_id) do update set is_active=true"), {"user": user_id, "unit": unit})
    else:
        user_id = existing
        # The stable pilot identity is the only existing row this script may update.
        conn.execute(text("update public.users set is_active=true, role_id=:role, unit_id=:unit, password_hash=:password_hash where user_id=:user and login=:login"),
          {"user": user_id, "login": LOGIN, "role": role, "unit": unit, "password_hash": hash_password(password)})
        conn.execute(text("insert into public.user_org_units(user_id,unit_id,is_active) values(:user,:unit,true) on conflict(user_id,unit_id) do update set is_active=true"), {"user": user_id, "unit": unit})
    return int(user_id), int(unit)


def _subject(conn: Connection, actor: int, unit: int, key: str, fragments: list[tuple[str, str]]) -> tuple[int, int, int, int]:
    """Create an isolated synthetic source batch/employee; no IIN is ever stored."""
    name = f"{MARKER} {key} employee"
    person = conn.execute(text("insert into public.persons(iin,full_name,match_key,person_status,source) values(null,:name,:key,'active','migration') returning person_id"), {"name": name, "key": f"{MARKER}:{key}"}).scalar_one()
    employee = conn.execute(text("insert into public.employees(full_name,person_id,org_unit_id,is_active,operational_status,enrollment_source) values(:name,:person,:unit,true,'active','migration') returning employee_id"), {"name": name, "person": person, "unit": unit}).scalar_one()
    conn.execute(text("insert into public.personnel_record_metadata(person_id,ppr_lifecycle_state,version) values(:person,'CREATED',1)"), {"person": person})
    batch = conn.execute(text("""insert into public.hr_import_batches(source_type,file_name,import_code,imported_by,status,total_rows,valid_rows)
      values('HR_CONTROL_LIST',:file,:code,:actor,'APPLY_PENDING',1,1) returning batch_id"""), {"file": f"{MARKER}-{key}.xlsx", "code": f"{MARKER}:{key}", "actor": actor}).scalar_one()
    row = conn.execute(text("""insert into public.hr_import_rows(batch_id,source_sheet,source_row_number,raw_payload,normalized_payload,match_status,review_status,employee_id)
      values(:batch,'Synthetic',1,'{}'::jsonb,cast(:payload as jsonb),'AUTO_MATCH','APPROVED',:employee) returning row_id"""), {"batch": batch, "employee": employee, "payload": json.dumps({"full_name": name, "education_raw": "\n".join(x[0] for x in fragments)})}).scalar_one()
    for index, (title, specialty) in enumerate(fragments):
        conn.execute(text("""insert into public.hr_import_normalized_records(batch_id,row_id,employee_id,fragment_index,source_field,source_text,source_record_key,record_kind,title,specialty_text,end_date,parse_method,review_status)
          values(:batch,:row,:employee,:index,'education_raw',:title,:source_key,'education',:title,:specialty,'2020-06-30','manual','approved')"""),
          {"batch": batch, "row": row, "employee": employee, "index": index, "title": title, "specialty": specialty, "source_key": f"{MARKER}:{key}:row1:{index}"})
    preview = stage0.preview_stage0_cohort(conn, source_batch_id=int(batch), scope={"privileged": True})
    cohort = stage0.freeze_stage0_cohort(conn, source_batch_id=int(batch), preview_fingerprint=preview["preview_fingerprint"], actor_user_id=actor, scope={"privileged": True})["stage0_cohort_run_id"]
    return int(person), int(employee), int(batch), int(cohort)


def _run(conn: Connection, actor: int, cohort: int) -> int:
    return int(stage2.preview_stage2(conn, stage0_cohort_run_id=cohort, actor_user_id=actor)["run"]["stage_run_id"])


def _pause_participant(conn: Connection, run: int) -> None:
    participant = conn.execute(text("select stage_run_participant_id from public.ppr_stage_run_participants where stage_run_id=:run"), {"run": run}).scalar_one()
    # Test-only fault fixture: service errors cannot be deterministically induced
    # without corrupting an otherwise valid source.  These values satisfy all DB
    # pause/participant constraints and leave the source resumable via the service.
    ref = _hash({"pilot": MARKER, "run": run, "fault": "participant"})
    conn.execute(text("update public.ppr_stage_run_participants set status='ERROR',error_code='SYNTHETIC_PARTICIPANT_FAILURE',error_reference=:ref,errored_at=now() where stage_run_participant_id=:id"), {"id": participant, "ref": ref})
    conn.execute(text("update public.ppr_stage_runs set status='PAUSED_ON_ERROR',paused_operation='PARTICIPANT_EXECUTION',stopped_participant_id=:participant,paused_at=now(),last_error_code='SYNTHETIC_PARTICIPANT_FAILURE',last_error_reference=:ref where stage_run_id=:run"), {"run": run, "participant": participant, "ref": ref})


def _pause_acceptance(conn: Connection, run: int) -> None:
    # Test-only transient acceptance fault.  The normal service writes the
    # constraint-valid acceptance pause after a rolled-back acceptance transaction.
    stage2.pause_acceptance_after_rollback(conn, run_id=run, exc=RuntimeError("SYNTHETIC_ACCEPTANCE_TRANSIENT"))


def _ids(conn: Connection) -> dict[str, dict[str, int]]:
    rows = conn.execute(text("""select b.import_code, c.stage0_cohort_run_id, r.stage_run_id
      from public.hr_import_batches b join public.ppr_stage0_cohort_runs c on c.source_batch_id=b.batch_id
      left join public.ppr_stage_runs r on r.stage0_cohort_run_id=c.stage0_cohort_run_id and r.stage_code='education'
      where b.import_code like :prefix order by b.import_code"""), {"prefix": f"{MARKER}:%"}).mappings()
    return {str(x["import_code"]).split(":", 1)[1]: {"cohort": int(x["stage0_cohort_run_id"]), "run": int(x["stage_run_id"])} for x in rows if x["stage_run_id"] is not None}


def _create_replacement_stale(engine, actor: int, unit: int) -> None:
    """Freeze replacement stale pilot, commit, then change its source in a new TX.

    This intentionally preserves the historical ``stale`` run (23), which was
    advanced during an earlier smoke check.  It never rewrites that history.
    """
    with engine.begin() as conn:
        _identity(conn)
        if REPLACEMENT_STALE_KEY in _ids(conn):
            return
        _, _, batch, cohort = _subject(
            conn, actor, unit, REPLACEMENT_STALE_KEY,
            [("Высшее образование replacement stale", "")],
        )
        run = _run(conn, actor, cohort)
        stage2.approve_stage2(conn, run_id=run, actor_user_id=actor)
        # The PREVIEW fingerprint and APPROVED state are committed on exit.

    with engine.begin() as conn:
        _identity(conn)
        # A real fingerprinted payload mutation (title/source_text), plus a
        # clock timestamp from this second transaction.  Do not use now() in
        # the creation transaction: PostgreSQL makes it transaction-stable.
        changed = conn.execute(text("""
            UPDATE public.hr_import_normalized_records
               SET title = title || ' — source changed after PREVIEW',
                   source_text = source_text || ' — source changed after PREVIEW',
                   updated_at = clock_timestamp()
             WHERE batch_id=:batch AND record_kind='education'
        """), {"batch": batch}).rowcount
        if changed != 1:
            raise RuntimeError("Replacement stale pilot source was not mutated exactly once.")


def _verify(conn: Connection, ids: dict[str, dict[str, int]]) -> None:
    required = {"ready", "review_blocked", "participant_pause", "acceptance_pause", "stale", REPLACEMENT_STALE_KEY}
    if not required.issubset(ids):
        raise RuntimeError("Pilot is incomplete; refusing to report it as ready.")
    ready = ids["ready"]["run"]
    row = conn.execute(text("""select count(*) from public.ppr_stage_run_participants p join public.hr_import_normalized_records n on n.employee_id=p.employee_id
      join public.ppr_stage0_cohort_participants s on s.stage0_participant_id=p.stage0_participant_id and s.source_row_id=n.row_id
      where p.stage_run_id=:run and n.record_kind='education'"""), {"run": ready}).scalar_one()
    if int(row) != 2:
        raise RuntimeError("Ready pilot must contain exactly two fragments in its one source row.")
    leaked = conn.execute(text("""select count(*) from public.ppr_stage_runs r join public.hr_import_batches b on b.batch_id=(select source_batch_id from public.ppr_stage0_cohort_runs c where c.stage0_cohort_run_id=r.stage0_cohort_run_id)
      where b.import_code like :prefix and r.safe_snapshot::text ~ '[0-9]{12}'"""), {"prefix": f"{MARKER}:%"}).scalar_one()
    if leaked:
        raise RuntimeError("Refusing: a safe snapshot contains an IIN-shaped value.")
    stale = ids[REPLACEMENT_STALE_KEY]
    changed = conn.execute(text("""
        SELECT count(*) FROM public.hr_import_normalized_records n
        JOIN public.ppr_stage0_cohort_runs c ON c.source_batch_id=n.batch_id
        WHERE c.stage0_cohort_run_id=:cohort
          AND n.source_text LIKE '%source changed after PREVIEW%'
    """), {"cohort": stale["cohort"]}).scalar_one()
    if int(changed) != 1:
        raise RuntimeError("Replacement stale source is not a committed post-PREVIEW mutation.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="validate only (the default)")
    parser.add_argument("--apply", action="store_true", help="write the synthetic local pilot")
    parser.add_argument("--confirm", help=f"required with --apply: {CONFIRM}")
    parser.add_argument("--test-database-url", default=os.environ.get("TEST_DATABASE_URL"))
    args = parser.parse_args()
    if args.dry_run and args.apply:
        raise SystemExit("Choose either --dry-run or --apply.")
    url = _url(args.test_database_url)
    engine = create_engine(url, future=True)
    with engine.connect() as conn:
        _identity(conn)
        found = _ids(conn)
        print("dry-run" if not args.apply else "apply")
        print("existing pilot runs:", found or "none")
    if not args.apply:
        print(f"No writes. Re-run with --apply --confirm {CONFIRM} after reviewing the loopback target.")
        return 0
    if args.confirm != CONFIRM:
        raise SystemExit("Refusing: --apply requires the exact explicit confirmation phrase.")
    password = os.environ.get("STAGE2_VISUAL_HR_PASSWORD")
    if not password:
        raise SystemExit("Refusing: STAGE2_VISUAL_HR_PASSWORD is required for --apply before any DML.")
    # Stage services import the global engine.  Give them only the URL already
    # checked above; the caller's DATABASE_URL is never read or trusted.
    os.environ["DATABASE_URL"] = str(url)
    from app.services import ppr_stage0_cohort_service as stage0_module
    from app.services import ppr_stage2_education_service as stage2_module

    global stage0, stage2
    stage0, stage2 = stage0_module, stage2_module
    os.environ["PPR_PMF_BRIDGE_ENABLED"] = "true"  # process-local pilot permission; never persisted.
    with engine.begin() as conn:
        _identity(conn)
        # The stable local-only identity is rotated on every explicit apply.
        # The password is accepted only from the process environment and is never logged.
        actor, unit = _actor(conn, password)
        found = _ids(conn)
        if found:
            ids = found
        else:
            ids: dict[str, dict[str, int]] = {}
            # Ready / accepted replay: two soft-line-break fragments in one source row.
            person, employee, batch, cohort = _subject(conn, actor, unit, "ready", [("Высшее образование Pilot A", "therapy"), ("Высшее образование Pilot B", "surgery")])
            run = _run(conn, actor, cohort)
            participant = conn.execute(text("select * from public.ppr_stage_run_participants where stage_run_id=:run"), {"run": run}).mappings().one()
            fragments = stage2._derive(conn, dict(participant), stage_run_id=run)["fragments"]
            for f in fragments:
                conn.execute(text("""insert into public.person_education(person_id,employee_context_id,education_kind,institution_name,specialty,completed_at,import_batch_id,import_row_id,metadata)
                  values(:person,:employee,:kind,:name,:specialty,:completed,:batch,:row,cast(:metadata as jsonb))"""),
                  {"person": person, "employee": employee, "kind": f["proposal"]["education_kind"], "name": f["proposal"]["institution_name"], "specialty": f["proposal"]["specialty"], "completed": f["proposal"]["completed_at"], "batch": batch, "row": f["import_row_id"], "metadata": json.dumps({"stage2": {"source_record_key": f["source_record_key"], "fragment_index": f["fragment_index"], "policy_version": "EDU-KIND-ALLOWLIST-v1", "item_key": f["item_key"]}})})
            fresh = stage2._derive(conn, dict(participant), stage_run_id=run)
            conn.execute(text("update public.ppr_stage_run_participants set safe_fingerprint=:f where stage_run_participant_id=:id"), {"f": fresh["fingerprint"], "id": participant["stage_run_participant_id"]})
            stage2.approve_stage2(conn, run_id=run, actor_user_id=actor); stage2.execute_next_stage2(conn, run_id=run, actor_user_id=actor); stage2.execute_next_stage2(conn, run_id=run, actor_user_id=actor); stage2.accept_stage2(conn, run_id=run, actor_user_id=actor)
            ids["ready"] = {"cohort": cohort, "run": run}
            # Review blocked: canonical conflict plus intentionally ambiguous review-required fragment.
            person, employee, batch, cohort = _subject(conn, actor, unit, "review_blocked", [("Высшее образование Conflict", "new"), ("послевузовское образование без вида", "")])
            conn.execute(text("insert into public.person_education(person_id,employee_context_id,education_kind,institution_name,specialty) values(:person,:employee,'basic','Высшее образование Conflict','old')"), {"person": person, "employee": employee})
            ids["review_blocked"] = {"cohort": cohort, "run": _run(conn, actor, cohort)}
            # Resumable controlled participant fault.
            _, _, _, cohort = _subject(conn, actor, unit, "participant_pause", [("Высшее образование Resume", "")]); run = _run(conn, actor, cohort); stage2.approve_stage2(conn, run_id=run, actor_user_id=actor); _pause_participant(conn, run); ids["participant_pause"] = {"cohort": cohort, "run": run}
            # Completed data plus a transient acceptance pause; retry-accept can proceed normally.
            _, _, _, cohort = _subject(conn, actor, unit, "acceptance_pause", [("Высшее образование Accept", "")]); run = _run(conn, actor, cohort); stage2.approve_stage2(conn, run_id=run, actor_user_id=actor); stage2.execute_next_stage2(conn, run_id=run, actor_user_id=actor); stage2.execute_next_stage2(conn, run_id=run, actor_user_id=actor); _pause_acceptance(conn, run); ids["acceptance_pause"] = {"cohort": cohort, "run": run}
            # Stale run: freeze then mutate only its synthetic normalized source.
            _, _, batch, cohort = _subject(conn, actor, unit, "stale", [("Высшее образование Stale", "")]); run = _run(conn, actor, cohort); stage2.approve_stage2(conn, run_id=run, actor_user_id=actor); conn.execute(text("update public.hr_import_normalized_records set updated_at=now() where batch_id=:batch"), {"batch": batch}); ids["stale"] = {"cohort": cohort, "run": run}
    # The original five-run setup is committed before the replacement stale
    # run is frozen and before that replacement source is mutated.
    if REPLACEMENT_STALE_KEY not in ids:
        with engine.begin() as conn:
            _identity(conn)
            actor, unit = _actor(conn, password)
        _create_replacement_stale(engine, actor, unit)
    with engine.connect() as conn:
        _identity(conn)
        ids = _ids(conn)
        _verify(conn, ids)
    print(f"local HR_HEAD login: {LOGIN}")
    for key, value in ids.items():
        print(f"{key}: stage0_cohort_run_id={value['cohort']}; stage2_run_id={value['run']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
