# Unified Corpsite training stand

This release serves one employee entry, `/training`. The existing approval
lesson stays in the versioned `training_*` tables. The expert catalog, hire
creation lesson and personal progress use `learning_*` tables in the **same**
isolated PostgreSQL database. Both sets appear in the expert completion view.
The HR hire lesson calls the existing registration service inside the attempt
transaction; it does not use a localhost API or `corpsite_test` connection.

`learn.mmc.004.kz` is the planned hostname. Do not use production
`mmc.004.kz` for this release. The isolated learning services on PS.kz use
ports 8004 and 3004. Public HTTPS requires an A record to 46.247.42.47 and
a valid TLS certificate. Until then, use the private port 8084 through an
SSH tunnel.

## Database and migration order

1. Create a fresh PostgreSQL database `corpsite_learn` and a dedicated login
   `corpsite_learn_app`; revoke public access. Bind it to loopback. Never point
   the learn process at `corpsite` or the working `corpsite_test`.
2. Run `python scripts/learn/bootstrap_schema.py` with `DATABASE_URL` set to
   the empty isolated database. Existing Corpsite migrations require an
   `HR_HEAD` role and active grantor by revision `i6j7k8l9m0n1`, then an
   active `DISP` unit with a parent. The script pauses at revision
   `h5c6d7e8f9a0`, creates only fictional reference rows, then advances to
   `learning008`. A restored learning PostgreSQL rehearsal reached this head
   twice without modifying existing results. The chain includes the personnel
   prerequisites, `trn001`–`trn007`, then `learning001`–`learning008`.
   Do not stamp an unrun migration.
3. Run `python scripts/learn/seed_demo_accounts.py --credentials-file
   /etc/corpsite-learn/acceptance-accounts.json` to create fictional users,
   roles, a training unit and position in the new database. The credentials
   file is private and is not rewritten on a second run. Set
   `CORPSITE_TRAINING_UNIT_ID`,
   `CORPSITE_TRAINING_PARENT_UNIT_ID`, and
   `CORPSITE_TRAINING_POSITION_ID` to those actual IDs. A passwordless
   `training_hr_partner_20261121` system account is required for the approval
   fixture. The seed grants `LEARNING_EXPERT` and, separately,
   `LEARNING_MANUAL_REVIEW` to `learn.expert`. The acceptance logins are
   `learn.hr.a`, `learn.hr.b`, `learn.manager_test`, `learn.expert`, and
   `learn.substitute`, `learn.signatory`, `learn.candidate.a`, and
   `learn.candidate.b`. The manager uses the password stored under
   `learn.manager` in the private credentials file. The substitute can open
   the expert cabinet but cannot grade manually.
4. Set `SOURCE_DATABASE_URL` to a read-only local tunnel to the reviewed
   PostgreSQL rehearsal copy and `DATABASE_URL` to the isolated target. Run
   `python scripts/learn/import_training_history.py`, then
   `python scripts/learn/import_learning_history.py --source-files <private
   pilot evidence> --target-files /var/lib/corpsite-learn/files`. These scripts
   copy only the fictional approval lesson and the preserved learning pilot,
   including assignments, attempts, reviews, comments, confirmations and
   evidence. The learning importer maps the old pilot participants onto the
   new demo HR A, HR B and manager accounts; the target manager uses the same
   login for both lessons. Run each importer twice. The second reports must
   contain no inserts or file copies. On a fresh local PostgreSQL rehearsal,
   the approval transfer preserved eight attempts and eight linked visa
   records; the learning transfer preserved ten attempts and applications
   537–539. No complete `corpsite_test` dump is copied to the server.
5. If importing directly from the earlier pilot SQLite is required, use
   `scripts/import_learning_pilot.py` with a reviewed user map and its
   `--source-sqlite`, `--source-files`, `--target-files`, and `--user-map-file`
   arguments. Choose one learning history source to avoid conflicting imports.

Before switching an existing stand, run `python scripts/learn/seed_hire_path.py --apply`
twice against its restored copy and then the training database. This preserves
the published first card, draft cards 2-5, assignments, attempts, scores and
evidence, and removes only the known obsolete blocker text in draft instructions.
Keep cards 2-5 in draft until their guides and both acknowledgement methods are
verified on the server.

## Application and HTTPS

- Install the unified commit under `/opt/projects/corpsite-learn/app`. Install
  Python requirements in a private virtual environment. Build the matching
  Next.js source with `NEXT_PUBLIC_API_BASE_URL=/api`; record the full commit
  SHA in `NEXT_DEPLOYMENT_ID`. Keep secrets out of Git.
- Use `backend.env.example` and `frontend.env.example` as templates for private
  files under `/etc/corpsite-learn` (mode `0600`). Enable
  `TRAINING_SERVER_ENABLED=1`, `TRAINING_MODE=1`,
  `TRAINING_DISABLE_EXTERNAL=1`, `LEARNING_PILOT_ENABLED=1`, and
  `HIRE_PATH_REHEARSAL=1`.
  Keep `BOT_TOKEN` and SMTP credentials absent. Do not run a bot or delivery
  timer on the training stand.
- Store screenshots and photos under separate private directories in
  `/var/lib/corpsite-learn`, outside Nginx roots. The backend preflight checks
  DB identity, migration head, flags, fixture IDs and storage directories.
- Install the supplied backend and frontend systemd units for the isolated
  learning services on PS.kz.
  The backend listens on `127.0.0.1:8004`, the frontend on
  `127.0.0.1:3004`. Verify `systemd-analyze verify`, both health checks, and
  `nginx -t`. Install the Nginx vhost only after DNS resolves to this VPS and a
  valid TLS certificate exists. HTTPS `/api/` proxies to the backend.

## Backup, rollback, acceptance

Before every migration or release switch, stop both learn services and capture
a dated `pg_dump -Fc corpsite_learn`, plus a paired archive of the private
evidence/photo roots and the current application commit. Encrypt and restrict
the backup. Verify a restore into a **new** database before deploying. To roll
back, stop the learn units, restore the paired DB/files backup into a separate
database and storage root, switch the private environment and previous
application release together, run preflight, then restart. Do not downgrade
the data-preserving `learning005`/`learning008` revisions in place.

Acceptance must be performed over the HTTPS hostname from another computer:
expert assigns the HR and approval lessons; HR saves and submits a fictional
hire application, sees its grade and points; manager approves a fictional
application; expert sees both in one completion view; manual review and
automatic source labels are shown. Repeat grading, deny direct access to a
different user's attempt and confirmation, restart the units, and verify that
attempts, grades and evidence remain. Keep `mmc.004.kz` untouched.
