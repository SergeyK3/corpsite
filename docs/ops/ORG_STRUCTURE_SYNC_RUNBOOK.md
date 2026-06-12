# Org Structure Sync Runbook — Phase 3 (`org_units`)

**Status:** Draft  
**Repo HEAD (baseline):** `fe0db5c`  
**Policy:** [ADR-014 — Data Sync Policy](../adr/ADR-014-data-sync-policy.md) § Phase 3  
**Direction:** Local → VPS (merge by `code`, preserve prod `unit_id`)  
**Dry-run artifact:** `data/sync/org_export_20260612_161743/` (`org_units.csv`, `deps_group.csv`)  
**Alias artifact:** [`scripts/ops/org_unit_aliases_v1.json`](../../scripts/ops/org_unit_aliases_v1.json)

---

## Core rules

1. **Match by `code`, never by `unit_id`.** Local export ids are not VPS ids.
2. **Resolve aliases before INSERT/UPDATE** (see alias artifact and §5).
3. **Parent remap through canonical code** — resolve local parent → parent code → alias (if any) → VPS `unit_id` via `code_map`.
4. **Preserve VPS `unit_id = 1`** for `mmc_root` and **`unit_id = 44`** for `qm_ovipd`.
5. **`GYNE` must never take id 44** on VPS (local id 44 ≠ pilot anchor).
6. **No DELETE** of VPS org rows.

---

## Scope

One-time alignment of the full local org tree onto VPS pilot/prod without touching operational or auth data.

| Action | Count | Notes |
|--------|------:|-------|
| **SKIP_ALIAS** | 3 | `ORG_MAIN`, `QM`, `Pharmacy` — not INSERTed |
| **UPDATE** | 2 | `mmc_root` ← `ORG_MAIN`, `qm_ovipd` ← `QM` |
| **INSERT** | 36 | Remaining local codes; **generated** `unit_id` on VPS |
| **KEEP** | 0 | Both VPS rows receive alias UPDATE |
| **DELETE** | 0 | Forbidden |

**Expected VPS row count after apply:** **38** (2 existing updated in place + 36 new rows).

---

## VPS baseline (must match before apply)

| unit_id | code | name | parent_unit_id | group_id |
|--------:|------|------|----------------:|---------:|
| 1 | `mmc_root` | Многопрофильный медицинский центр | NULL | NULL |
| 44 | `qm_ovipd` | Отдел внутреннего контроля и оценки качества медицинской помощи | 1 | 3 |

Pilot FK anchors on **`unit_id = 44`** (`users`, `employees`, `regular_tasks`).

Local export baseline: **39 rows**, root `ORG_MAIN` (local id **41**), `GYNE` at local id **44** (id collision with VPS only — not a code match).

---

## 1. Preconditions

Complete **before** starting Phase 3. Stop if any gate fails.

### 1.1 Phase dependencies (ADR-014)

| Phase | Table(s) | Exit criteria |
|-------|----------|---------------|
| **Phase 1** | `positions` | VPS count aligned with local (96); FK valid |
| **Phase 2** | `deps_group`, `departments` | VPS has groups 1/2/3; `department_id=44` present |

Phase 3 **depends on Phase 2** (`org_units.group_id` FK to `deps_group`).

### 1.2 Environment

| Check | Requirement |
|-------|-------------|
| VPS path | `/opt/projects/corpsite/app` |
| Postgres container | `corpsite-pg`, database `corpsite` |
| Alembic | `alembic current` = head (no pending migrations) |
| Operator | SSH access to VPS; local export + alias JSON available |
| Maintenance | Notify pilot users; no parallel Directory org edits during apply |

Copy alias artifact to VPS with CSV:

```bash
scp scripts/ops/org_unit_aliases_v1.json \
  ubuntu@46.247.42.47:/var/lib/corpsite/sync/org_export_20260612_161743/
```

### 1.3 Local export freshness

Re-export if local tree changed after `20260612_161743`:

```powershell
# Local (PowerShell, repo root)
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = ".\data\sync\org_export_$stamp"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

docker exec corpsite-pg psql -U postgres -d corpsite -c "\copy (SELECT group_id, group_name FROM deps_group ORDER BY group_id) TO '/tmp/deps_group.csv' WITH CSV HEADER ENCODING 'UTF8'"
docker exec corpsite-pg psql -U postgres -d corpsite -c "\copy (SELECT unit_id, code, name, parent_unit_id, group_id, is_active FROM org_units ORDER BY unit_id) TO '/tmp/org_units.csv' WITH CSV HEADER ENCODING 'UTF8'"

docker cp corpsite-pg:/tmp/deps_group.csv "$outDir\"
docker cp corpsite-pg:/tmp/org_units.csv "$outDir\"
Write-Host $outDir
```

### 1.4 Pre-flight gates (VPS)

```bash
docker exec corpsite-pg psql -U postgres -d corpsite -c "
SELECT count(*) AS org_units FROM org_units;
SELECT unit_id, code FROM org_units ORDER BY unit_id;
SELECT count(*) AS deps_group FROM deps_group;
"
```

**Hard gates:**

- `org_units` count = **2**
- Rows exactly: `(1, mmc_root)`, `(44, qm_ovipd)`
- `deps_group` count = **3**

---

## 2. Backup command

Full DB backup **before** any staging load or apply. Store off-repo; do not commit dumps.

```bash
STAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/var/lib/corpsite/backups
mkdir -p "$BACKUP_DIR"

docker exec corpsite-pg pg_dump -U postgres -Fc -d corpsite \
  > "$BACKUP_DIR/pre_org_sync_${STAMP}.dump"

ls -lh "$BACKUP_DIR/pre_org_sync_${STAMP}.dump"
```

---

## 3. CSV transfer command

Transfer via **SCP/SFTP only**. Do not commit CSV to GitHub (ADR-014 §5.1).

```powershell
$LOCAL = "D:\MyActivity\MyInfoBusiness\MyPythonApps\09 Corpsite\data\sync\org_export_20260612_161743"
$REMOTE = "ubuntu@46.247.42.47:/var/lib/corpsite/sync/org_export_20260612_161743"

ssh ubuntu@46.247.42.47 "mkdir -p /var/lib/corpsite/sync/org_export_20260612_161743"
scp "$LOCAL\org_units.csv" "$LOCAL\deps_group.csv" "${REMOTE}/"
scp "scripts\ops\org_unit_aliases_v1.json" "${REMOTE}/"
```

```bash
wc -l /var/lib/corpsite/sync/org_export_20260612_161743/org_units.csv
# Expect: 40 lines (1 header + 39 data rows)
```

---

## 4. Dry-run checks

Run **all** checks below. Apply is blocked until dry-run report is signed off.

### 4.1 Pipeline order

```
1. Load staging.stg_org_units_local
2. Load alias map from org_unit_aliases_v1.json
3. Classify each local row: SKIP_ALIAS | UPDATE (via alias target) | INSERT
4. Build code_map: canonical local code → VPS unit_id
5. Parent remap: local parent_unit_id → parent code → canonical code → code_map
6. Emit dry-run report; operator sign-off
7. APPLY (separate step, §6)
```

### 4.2 Load staging (dry-run only)

```bash
SYNC=/var/lib/corpsite/sync/org_export_20260612_161743

docker exec -i corpsite-pg psql -U postgres -d corpsite <<SQL
DROP TABLE IF EXISTS staging.stg_org_units_local;
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE staging.stg_org_units_local (
    unit_id         BIGINT,
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    parent_unit_id  BIGINT,
    group_id        BIGINT,
    is_active       BOOLEAN
);

\copy staging.stg_org_units_local FROM '${SYNC}/org_units.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
SQL
```

### 4.3 Code overlap and classification

```sql
-- Strict code overlap: expected 0 rows
SELECT l.code AS local_code, p.code AS vps_code
FROM staging.stg_org_units_local l
JOIN public.org_units p ON lower(trim(l.code)) = lower(trim(p.code));

-- SKIP_ALIAS sources (must not appear in INSERT set)
SELECT code, unit_id FROM staging.stg_org_units_local
WHERE trim(code) IN ('ORG_MAIN', 'QM', 'Pharmacy')
ORDER BY code;
-- Expected: 3 rows

-- INSERT candidates (exclude SKIP_ALIAS sources; PHARM is INSERT source for pharmacy)
SELECT l.code, l.unit_id AS local_unit_id, l.parent_unit_id, l.group_id
FROM staging.stg_org_units_local l
WHERE trim(l.code) NOT IN ('ORG_MAIN', 'QM', 'Pharmacy')
  AND NOT EXISTS (SELECT 1 FROM public.org_units p WHERE trim(p.code) = trim(l.code))
ORDER BY l.code;
-- Expected: 36 rows
```

### 4.4 Collision checks

```sql
-- CRITICAL: never import by unit_id — GYNE vs qm_ovipd on id 44
SELECT l.code, l.unit_id AS local_id, p.code AS vps_code, p.unit_id AS vps_id
FROM staging.stg_org_units_local l
JOIN public.org_units p ON l.unit_id = p.unit_id
WHERE trim(l.code) <> trim(p.code);
-- Expected: 1 row — GYNE (local 44) vs qm_ovipd (VPS 44)

-- Single local root (alias to mmc_root, not INSERT)
SELECT code, unit_id FROM staging.stg_org_units_local
WHERE parent_unit_id IS NULL OR trim(parent_unit_id::text) = '';
-- Expected: ORG_MAIN only
```

### 4.5 Parent remap sanity

Resolve parents through **canonical code**, not local numeric id:

| Local parent id | Local parent code | Canonical code | VPS parent |
|----------------:|-------------------|----------------|------------|
| 41 | `ORG_MAIN` | `mmc_root` | **1** |
| 72 | `QM` | `qm_ovipd` | **44** |
| 79 | `Pharmacy` | `PHARM` | id(`PHARM`) after INSERT |
| 68 | `STAT` | `STAT` | id(`STAT`) after pass 1 |

```sql
SELECT count(*) FROM staging.stg_org_units_local WHERE parent_unit_id = 41;
-- Expected: 35 (remap via ORG_MAIN → mmc_root → 1)

SELECT count(*) FROM staging.stg_org_units_local WHERE parent_unit_id = 68;
-- Expected: 3
```

**Insert passes:**

1. **Pass 1:** 33 rows — exclude SKIP_ALIAS sources and `parent_unit_id = 68`.
2. **Pass 2:** 3 rows — STAT subtree; parent = VPS id(`STAT`).

### 4.6 Dry-run summary (operator sign-off)

| Check | Expected |
|-------|----------|
| VPS `org_units` count (before) | 2 |
| Strict code overlap | 0 |
| **SKIP_ALIAS** | **3** |
| **UPDATE** | **2** |
| **INSERT** | **36** |
| **KEEP** | **0** |
| `unit_id` collision (GYNE / 44) | 1 (INSERT with generated id) |
| **Post-apply count** | **38** |

**Do not apply** until this table matches.

---

## 5. Alias rules

Canonical map: **`scripts/ops/org_unit_aliases_v1.json`**

| Local code | VPS / canonical code | VPS unit_id | Action |
|------------|----------------------|------------:|--------|
| `ORG_MAIN` | `mmc_root` | **1** | **UPDATE** target; SKIP_ALIAS source |
| `QM` | `qm_ovipd` | **44** | **UPDATE** target; SKIP_ALIAS source |
| `Pharmacy` | `PHARM` | *(new on INSERT)* | **SKIP_ALIAS** source; canonical row is local `PHARM` |

### Resolution order

1. If `local.code` is a **SKIP_ALIAS source** → do not INSERT; map to target/canonical code.
2. If alias target exists on VPS → **UPDATE** VPS row; preserve `unit_id` and `code`.
3. If local code is canonical and not on VPS → **INSERT** with generated `unit_id`.
4. Parent remap: `local.parent_unit_id` → parent code → **alias resolve** → `code_map[canonical]`.

### Allowed UPDATE fields on alias targets (`mmc_root`, `qm_ovipd`)

| Field | Rule |
|-------|------|
| `name` | From local source; ops may keep VPS `qm_ovipd` name on pilot |
| `group_id` | From local source; **`mmc_root` root should stay `NULL`** (do not copy local `1`) |
| `parent_unit_id` | `qm_ovipd` → **1**; `mmc_root` → NULL |
| `is_active` | From local source |
| `code` | **Never change** |
| `unit_id` | **Never change** (1 and 44) |

### Forbidden

- INSERT `ORG_MAIN`, `QM`, or `Pharmacy` as separate VPS rows
- Second root (`parent_unit_id IS NULL` count > 1)
- Second QM unit (duplicate of `qm_ovipd`)
- Second pharmacy unit (`Pharmacy` code on VPS)
- Match or upsert by `unit_id`
- `DELETE` / `TRUNCATE` of VPS org rows

---

## 6. Apply rules

Single transaction recommended. Requires operator approval after dry-run sign-off.

### 6.1 Reserved VPS ids

| unit_id | code | Rule |
|--------:|------|------|
| **1** | `mmc_root` | Never INSERT; alias UPDATE only |
| **44** | `qm_ovipd` | Never INSERT; **`GYNE` must never take id 44** |

Use generated `unit_id` (omit on INSERT) for all **36** new rows.

### 6.2 Apply sequence

```
1. BEGIN
2. Resolve aliases (load org_unit_aliases_v1.json)
3. UPDATE mmc_root FROM local ORG_MAIN (preserve unit_id=1, code=mmc_root)
4. UPDATE qm_ovipd FROM local QM (preserve unit_id=44, code=qm_ovipd)
5. INSERT pass 1 — 33 rows; exclude SKIP_ALIAS sources and parent_unit_id=68
   Parent remap via canonical code_map (41→mmc_root→1, etc.)
6. INSERT pass 2 — 3 STAT subtree rows
7. setval(org_units unit_id sequence, max(unit_id))
8. Export code_map for Phase 4 employees
9. COMMIT (only if §7 verification passes)
```

### 6.3 Match and merge policy

| Situation | Action |
|-----------|--------|
| Local code in SKIP_ALIAS | **SKIP_ALIAS** — no INSERT |
| Alias target on VPS | **UPDATE**; preserve VPS `unit_id` |
| Local code not on VPS, not SKIP_ALIAS | **INSERT**; generated `unit_id` |
| VPS row, no local code (after aliases) | Unchanged (none expected at baseline) |
| Same VPS `unit_id`, different code | **Never** upsert by `unit_id` |

### 6.4 Explicit denials

- No **DELETE**
- No touch of `users`, `employees`, `regular_tasks` in Phase 3
- No `OVERRIDING SYSTEM VALUE` for `unit_id` on INSERT
- No import script run until ops tooling is reviewed (future `import_org_units.py`)

### 6.5 Reference apply SQL (illustrative)

```sql
BEGIN;

-- Step A: alias UPDATEs (preserve unit_id and code)
UPDATE public.org_units v
SET name = l.name, group_id = NULL, is_active = l.is_active
FROM staging.stg_org_units_local l
WHERE v.code = 'mmc_root' AND l.code = 'ORG_MAIN';

UPDATE public.org_units v
SET
    name = l.name,
    parent_unit_id = 1,
    group_id = l.group_id,
    is_active = l.is_active
FROM staging.stg_org_units_local l
WHERE v.code = 'qm_ovipd' AND l.code = 'QM';

-- Step B: pass 1 INSERT — exclude SKIP_ALIAS sources and STAT subtree
-- Parent must be resolved via canonical code_map, not local unit_id
INSERT INTO public.org_units (code, name, parent_unit_id, group_id, is_active)
SELECT l.code, l.name, /* code_map parent */, l.group_id, l.is_active
FROM staging.stg_org_units_local l
WHERE l.code NOT IN ('ORG_MAIN', 'QM', 'Pharmacy')
  AND (l.parent_unit_id IS NULL OR l.parent_unit_id <> 68)
  AND NOT EXISTS (SELECT 1 FROM public.org_units p WHERE p.code = l.code);

-- Step C: pass 2 — STAT subtree
INSERT INTO public.org_units (code, name, parent_unit_id, group_id, is_active)
SELECT l.code, l.name, p_stat.unit_id, l.group_id, l.is_active
FROM staging.stg_org_units_local l
JOIN public.org_units p_stat ON p_stat.code = 'STAT'
WHERE l.parent_unit_id = 68
  AND NOT EXISTS (SELECT 1 FROM public.org_units p WHERE p.code = l.code);

SELECT setval(
    pg_get_serial_sequence('public.org_units', 'unit_id'),
    (SELECT COALESCE(MAX(unit_id), 1) FROM public.org_units)
);

COMMIT;
```

---

## 7. Verification SQL

```sql
SELECT count(*) AS org_units FROM org_units;
-- Expected: 38

SELECT unit_id, code FROM org_units WHERE unit_id IN (1, 44);
-- Expected: (1, mmc_root), (44, qm_ovipd)

SELECT count(*) FROM org_units WHERE parent_unit_id IS NULL;
-- Expected: 1 (mmc_root only)

SELECT count(*) FROM org_units WHERE code IN ('QM', 'Pharmacy', 'ORG_MAIN');
-- Expected: 0

SELECT count(*) FROM org_units WHERE code = 'PHARM';
-- Expected: 1

SELECT unit_id, code FROM org_units WHERE unit_id = 44;
-- Expected: qm_ovipd only (not GYNE)
```

Pilot FK counts on `unit_id = 44` must match pre-apply snapshot.

---

## 8. Rollback

Restore pre-apply `pg_dump -Fc`. Do not DELETE-based undo.

```bash
docker exec -i corpsite-pg pg_restore -U postgres -d corpsite --clean --if-exists \
  < /var/lib/corpsite/backups/pre_org_sync_${STAMP}.dump
```

Confirm post-restore: `org_units` count = 2; `unit_id=44` = `qm_ovipd`.

---

## 9. Explicit danger list

| Rule | Detail |
|------|--------|
| **Never import by `unit_id`** | Local `GYNE`=44 would overwrite pilot `qm_ovipd` |
| **Never overwrite `unit_id=44`** | Pilot anchor for users/employees/regular_tasks |
| **Never create a second root** | `ORG_MAIN` → UPDATE `mmc_root`, not INSERT |
| **Never duplicate QM** | `QM` → UPDATE `qm_ovipd`, not INSERT |
| **Never duplicate Pharmacy** | `Pharmacy` → SKIP; canonical `PHARM` only |
| **GYNE never id 44** | INSERT `GYNE` with generated id |
| **No DELETE** | VPS rows kept; additive merge only |

---

## Phase 4 handoff (employees)

After apply, export `code_map` for employee sync:

- Local `QM` (unit 72) → VPS **44** (`qm_ovipd`)
- Local `Pharmacy` (unit 79) → VPS id(`PHARM`)
- Resolve via **canonical code**, not local `unit_id`

---

## Ops log entry (template)

```
Date:
Operator:
VPS HEAD:
Local export:
Alias artifact: org_unit_aliases_v1.json
Backup: /var/lib/corpsite/backups/pre_org_sync_YYYYMMDD_HHMMSS.dump
Dry-run: SKIP_ALIAS=3 UPDATE=2 INSERT=36 KEEP=0
Apply: SUCCESS | ROLLBACK
Post count: org_units=38
Pilot unit 44: qm_ovipd OK
Notes:
```

---

## Related documents

- [ADR-014 — Data Sync Policy](../adr/ADR-014-data-sync-policy.md)
- [`scripts/ops/org_unit_aliases_v1.json`](../../scripts/ops/org_unit_aliases_v1.json)
- [PILOT_QM_ROSTER.md](../PILOT_QM_ROSTER.md)

---

## Change history

| Date | Change |
|------|--------|
| 2026-06-12 | Draft from dry-run `org_export_20260612_161743` at HEAD `fe0db5c` |
| 2026-06-12 | Alias-aware revision: 3 aliases, SKIP_ALIAS=3, UPDATE=2, INSERT=36, post-apply=38 |
