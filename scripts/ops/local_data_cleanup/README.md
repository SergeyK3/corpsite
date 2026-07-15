# Local / Dev Data Cleanup Toolkit

Universal utilities for auditing and removing **explicitly allowlisted** Personnel and Directory test data from a **local or development PostgreSQL database**.

This toolkit is **not** part of the application runtime. It does not modify ORM models, migrations, or production configuration.

## Scope and limitations

- Intended **only** for local/dev databases (`127.0.0.1`, `localhost`, `::1`).
- **Dry-run / audit is the default safe mode.** No rows are deleted unless `execute` is invoked with explicit confirmation.
- **Prefixes such as `pytest_`, `Pytest`, or `e1_` are not sufficient** for deletion. Every target row must appear in an external allowlist with an `expected_signature` that matches the live database row.
- **Blocked rows** (FK dependencies, live references) are reported separately and are never deleted automatically.
- **Working allowlists, manifests, and database dumps must live outside Git** and outside `scripts/ops/local_data_cleanup/`.

## Files

| File | Purpose |
|------|---------|
| `personnel_test_cleanup.py` | Audit / dry-run / execute / verify runner |
| `personnel_cleanup_fk_graph.py` | Read-only PostgreSQL FK dependency graph builder |
| `allowlist.example.json` | Safe example structure only — copy and edit externally |

## Safety guardrails

| Guard | Behavior |
|-------|----------|
| Production-like host blocking | Refuses non-local hosts and URLs containing cloud/production markers |
| Expected database name | `--expected-database-name` must match the connected database |
| Production-like DB names | Blocks names such as `prod`, `production`, `live`, `master`, `primary`, `replica` |
| External allowlist | Required; must be outside this toolkit directory |
| Signature verification | Every allowlisted ID must match all `expected_signature` fields or the run aborts |
| Protected entities | Must exist and must never overlap delete allowlist entries |
| FK validation | Catalog-based blocker detection runs before any delete plan is accepted |
| Transaction | Execute performs all deletes in one transaction; failure rolls back |
| Execute confirmation | Requires `--confirm-phrase DELETE_LOCAL_TEST_DATA` and `--confirm-database-name` |
| Backup proof | Requires `--backup-path` to an existing file **or** `--backup-acknowledged` |
| Manifest output | Must be written outside this toolkit directory |
| Secrets | Database URL comes from `DATABASE_URL` or `--database-url`; passwords are redacted in reports |

There is **no production bypass** in this version.

## Recommended workflow (Windows PowerShell)

```powershell
# 0. Set connection (example — use your local credentials)
$env:DATABASE_URL = "postgresql+psycopg2://USER@127.0.0.1:5432/your_dev_database"

# 1. Backup (store outside the repository)
pg_dump -h 127.0.0.1 -U USER -d your_dev_database -Fc -f C:\path\to\backups\dev_before_cleanup.dump

# 2. FK graph (read-only)
python scripts/ops/local_data_cleanup/personnel_cleanup_fk_graph.py `
  --expected-database-name your_dev_database `
  --allowlist C:\path\to\cleanup_allowlist.json `
  --output C:\path\to\manifests\fk_graph_report.json

# 3. Audit / dry-run (default safe mode)
python scripts/ops/local_data_cleanup/personnel_test_cleanup.py audit `
  --expected-database-name your_dev_database `
  --allowlist C:\path\to\cleanup_allowlist.json `
  --manifest-out C:\path\to\manifests\cleanup_dryrun.json

# 3a. Positions domain audit (no allowlist required)
python scripts/ops/local_data_cleanup/personnel_test_cleanup.py audit `
  --expected-database-name corpsite `
  --domain positions `
  --manifest-out C:\path\to\manifests\positions_audit.json

# 3b. HR allowed-positions audit for org unit 73
python scripts/ops/local_data_cleanup/personnel_test_cleanup.py audit `
  --expected-database-name corpsite `
  --domain allowed-positions `
  --org-unit-id 73 `
  --manifest-out C:\path\to\manifests\hr_allowed_audit.json

# 4. Review manifest: deletable / protected / blocked sections

# 5. Execute (only after backup and manifest review)
python scripts/ops/local_data_cleanup/personnel_test_cleanup.py execute `
  --expected-database-name your_dev_database `
  --confirm-database-name your_dev_database `
  --confirm-phrase DELETE_LOCAL_TEST_DATA `
  --allowlist C:\path\to\cleanup_allowlist.json `
  --backup-path C:\path\to\backups\dev_before_cleanup.dump `
  --before-manifest C:\path\to\manifests\cleanup_dryrun.json `
  --manifest-out C:\path\to\manifests\cleanup_after.json

# 5a. Execute HR allowed-link cleanup (explicit link IDs in allowlist.org_unit_allowed_position_links)
python scripts/ops/local_data_cleanup/personnel_test_cleanup.py execute `
  --expected-database-name corpsite `
  --domain allowed-positions `
  --org-unit-id 73 `
  --confirm-database-name corpsite `
  --confirm-phrase DELETE_LOCAL_TEST_DATA `
  --allowlist C:\path\to\local_hr_allowed_links_allowlist.json `
  --backup-acknowledged `
  --manifest-out C:\path\to\manifests\hr_allowed_execute.json

# 5c. Plan position-contours (read-only forensic + delete order + allowlist draft)
python scripts/ops/local_data_cleanup/personnel_test_cleanup.py plan `
  --expected-database-name corpsite `
  --domain position-contours `
  --manifest-out C:\path\to\manifests\position_contours_plan.json `
  --allowlist-out C:\path\to\local_position_contours_allowlist.json

# 5d. Execute position-contours (explicit contour allowlist)
python scripts/ops/local_data_cleanup/personnel_test_cleanup.py execute `
  --expected-database-name corpsite `
  --domain position-contours `
  --confirm-database-name corpsite `
  --confirm-phrase DELETE_LOCAL_TEST_DATA `
  --allowlist C:\path\to\local_position_contours_allowlist.json `
  --backup-path C:\path\to\backups\dev_before_contours.dump `
  --manifest-out C:\path\to\manifests\position_contours_execute.json

# 5e. Verify position-contours
python scripts/ops/local_data_cleanup/personnel_test_cleanup.py verify `
  --expected-database-name corpsite `
  --domain position-contours `
  --allowlist C:\path\to\local_position_contours_allowlist.json `
  --before-manifest C:\path\to\manifests\position_contours_plan.json `
  --manifest-out C:\path\to\manifests\position_contours_verify.json

# 5b. Execute global test positions cleanup (explicit IDs in allowlist.positions)
python scripts/ops/local_data_cleanup/personnel_test_cleanup.py execute `
  --expected-database-name corpsite `
  --domain positions `
  --confirm-database-name corpsite `
  --confirm-phrase DELETE_LOCAL_TEST_DATA `
  --allowlist C:\path\to\local_test_positions_allowlist.json `
  --backup-acknowledged `
  --manifest-out C:\path\to\manifests\positions_execute.json

# 6. Verify positions domain (read-only)
python scripts/ops/local_data_cleanup/personnel_test_cleanup.py verify `
  --expected-database-name corpsite `
  --domain positions `
  --allowlist C:\path\to\local_test_positions_allowlist.json `
  --before-manifest C:\path\to\manifests\positions_audit_before.json `
  --manifest-out C:\path\to\manifests\positions_verify.json

# 6b. Verify general personnel cleanup
python scripts/ops/local_data_cleanup/personnel_test_cleanup.py verify `
  --expected-database-name your_dev_database `
  --allowlist C:\path\to\cleanup_allowlist.json `
  --before-manifest C:\path\to\manifests\cleanup_dryrun.json `
  --manifest-out C:\path\to\manifests\cleanup_verify.json
```

## CLI modes (`personnel_test_cleanup.py`)

| Command | Description |
|---------|-------------|
| `audit` | Read-only report: signatures, FK validation, deletable / protected / blocked |
| `dry-run` | Alias for `audit` |
| `execute` | Delete allowlisted rows inside a transaction (requires confirmation + backup proof) |
| `verify` | Post-cleanup checks: allowlisted rows removed, protected entities still present |

### Positions domain verify policy

- **Read-only** — no INSERT/UPDATE/DELETE/DDL.
- **Blocked positions** listed in `--before-manifest` `blocked_candidates` must still exist; unexpected absence **fails** verify.
- **Protected** `position_id=1` (Архивариус) and HR etalon position names must remain.
- **Optional tables** (for example `org_unit_allowed_positions`) are **skipped**, not fatal.
- **ID reuse** (same `position_id`, different `name` than allowlist signature) **fails** verify.

## Allowlist rules

1. Copy `allowlist.example.json` to a path **outside Git**.
2. List every deletable object by explicit numeric `id`.
3. Provide `expected_signature` fields that must match the current database row exactly.
4. List production entities under `protected` with their own signatures.
5. Re-run `audit` after any allowlist change and review the manifest before `execute`.

Never add objects by numeric range, name pattern, or prefix alone.

## Output categories

| Category | Meaning |
|----------|---------|
| **found** | Allowlisted rows whose signatures matched the database |
| **deletable** | Found rows planned for deletion (FK validation passed) |
| **protected** | Protected entities verified present |
| **blocked** | Rows that cannot be deleted yet (for example roles still referenced) |
| **deleted** | Rows removed during `execute` (recorded in post-execute manifest) |

## FK graph tool

`personnel_cleanup_fk_graph.py` reads PostgreSQL catalog metadata only (no DDL/DML). It reports:

- incoming and outgoing FK edges for allowlist tables
- dependency paths and detected cycles
- blocking child tables with RESTRICT / NO ACTION rules
- topological delete order compared against the runner phase order

## What not to store here

Do **not** place in this directory:

- working `cleanup_allowlist.json` copies with real IDs
- manifests (`cleanup_dryrun_*.json`, `cleanup_after_*.json`, …)
- database dumps (`.dump`, `.sql`)
- machine-specific absolute paths

## Note on `_sync_allowlist_signatures.py`

The legacy helper that auto-refreshes allowlist signatures from the current database was **not** included in this toolkit.

| Aspect | Detail |
|--------|--------|
| Purpose | Convenience: copy live field values into `expected_signature` |
| Risk | Can silently turn the current DB state into trusted allowlist data |
| Auto-trust problem | Running it after tests could protect or delete the wrong rows on the next cleanup |
| Mitigation | Signatures must be authored or reviewed manually; audit mode verifies them read-only |

If a future sync helper is added, it should emit a **draft** file for human review and must never overwrite a working allowlist without explicit operator confirmation.

## Related legacy script

`scripts/ops/ops030_cleanup_pytest_roles.py` remains a narrower audit/delete tool for orphan `pytest_*` platform roles. The toolkit in this directory is the generalized, allowlist-driven Personnel/Directory cleanup path.
