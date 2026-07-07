# WP-CLEAN-005C — Kickoff Readiness Report

| Field | Value |
|-------|-------|
| Date | 2026-07-07 (updated post VPS Ops/DBA audit) |
| Scope | CCR-006 (legacy CSV/XLSX routes) + CCR-007 (`employees_import*` tables) |
| Type | Readiness audit — **no runtime / schema changes** |
| Rollback baseline | `a9fcf5d` (pre-005C HEAD) |

---

## 1. Executive decision

| Question | Answer |
|----------|--------|
| **Execution authorized?** | **NO** |
| Primary blocker | **B1 — formal 30-day nginx access-log window incomplete** (retention: daily rotate × 14) |
| CCR-007 (DBA) | **Blocker closed** — prod tables empty; no FK/views/triggers/ETL/runtime refs; safe to remove |
| CCR-006 (Ops) | **Partially closed** — ~15-day nginx zero + 30-day backend journal zero; formal 30-day nginx pending |

**Unblock path (either):**

- **A)** Collect full 30-day nginx zero-hit window (increase retention to 30d, then re-audit), or
- **B)** Explicit **policy waiver** if Architecture/Ops accept backend journal (30d) + nginx (~15d) as sufficient evidence.

Repo-level and VPS audits are **favorable**; CLEAN-GATE-001 formal G2 nginx window remains open.

---

## 2. Access-log evidence (G2)

### 2.1 Target endpoints

| Method | Path | nginx-proxied path (prod) |
|--------|------|---------------------------|
| POST | `/directory/import/employees_csv` | `/api/directory/import/employees_csv` |
| POST | `/directory/import/employees_xlsx` | `/api/directory/import/employees_xlsx` |

### 2.2 Sample window

| Parameter | Value |
|-----------|-------|
| Requested window | 30 days ending **2026-07-07** |
| Start date (formal gate) | 2026-06-07 |
| VPS nginx retention | **14 days** (daily rotate) — **~15 days** actually available |
| VPS backend journal | **30 days** available |

### 2.3 VPS Ops collection result (B1)

| Source | Window | Result |
|--------|--------|--------|
| **VPS nginx access log** | ~15 days (retention-limited) | **0 hits** on both legacy endpoints |
| **Backend journal** (`journalctl` / app logs) | 30 days | **0 mentions** of `import/employees_csv` or `import/employees_xlsx` |
| Repo / scripts | Static grep | **0 callers** (unchanged) |

**Retention gap:** formal CLEAN-GATE-001 **30-day nginx** evidence **not closed** — oldest retained nginx logs cover only ~15 days, not the full 2026-06-07…2026-07-07 window.

### 2.4 Access-log summary

| Endpoint | nginx hits (~15d) | backend journal (30d) | Last hit | User-Agent / source | Verdict |
|----------|-------------------|----------------------|----------|---------------------|---------|
| `POST /directory/import/employees_csv` | **0** | **0** | — | — | **Zero usage** (partial window) |
| `POST /directory/import/employees_xlsx` | **0** | **0** | — | — | **Zero usage** (partial window) |

**Combined Ops inference:** no production traffic detected in all available evidence. **Formal gate:** nginx 30-day window still **incomplete**.

### 2.5 Recommended Ops actions (close B1)

**Option A — preferred (full gate compliance):**

1. Increase nginx `access.log` retention to **≥ 30 days** (adjust `logrotate` / `rotate` count).
2. Wait until a full 30-day window is retained, re-run grep, attach zero-hit evidence.

```bash
# Re-audit after retention increase
LOG=/var/log/nginx/access.log
zgrep -h "POST.*/(api/)?directory/import/employees_(csv|xlsx)" "$LOG" /var/log/nginx/access.log.* \
  $(ls -1 /var/log/nginx/access.log.*.gz 2>/dev/null) 2>/dev/null
# Expect: empty output
```

**Option B — policy waiver:**

If Architecture + Ops accept **backend journal (30d zero) + nginx (~15d zero)** as sufficient for Med-High legacy route retirement:

1. Record waiver in CLEAN-GATE-001 exception log (date, approvers, retention constraint cited).
2. Attach this readiness report as evidence bundle.
3. Proceed to B3 (Med-High sign-off) without waiting for 30-day nginx retention.

**Option B is not automatic** — requires explicit approval; default gate remains Option A.

---

## 3. OpenAPI / router audit (G3)

### 3.1 Legacy endpoints — CCR-006 (**in scope for removal**)

Extracted from FastAPI app registry (`app.main`, 2026-07-07):

| Method | Path | Handler | Auth |
|--------|------|---------|------|
| POST | `/directory/import/employees_csv` | `import_employees_csv` | JWT + `_is_privileged(user)` |
| POST | `/directory/import/employees_xlsx` | `import_employees_xlsx` | JWT + `_is_privileged(user)` |

**Registration:** `app/directory/router.py` → `import_router` (line 38).

**Services:**

| Service | Writes to |
|---------|-----------|
| `directory_import_csv.import_employees_csv_bytes` | `employees`, `departments`, `positions` |
| `directory_import_xlsx.import_employees_xlsx_bytes` | `employees`, `departments`, `positions` |

> **Important:** legacy services **do not** read/write `employees_import*` tables (see §4).

### 3.2 Active HR Import contour — **must NOT be touched**

`hr_import_routes.py` — **37 routes** under `/directory/personnel/import/*` (+ employee import-card). UI consumer: `importApi.client.ts`.

| Category | Example routes | UI |
|----------|----------------|-----|
| Batch lifecycle | `GET/DELETE /personnel/import/batches*` | ✓ |
| Upload | `POST /personnel/import/upload` | ✓ |
| Review / promotion | `.../rows/{row_id}/review`, `.../normalized-records/promote` | ✓ |
| Analytics | `.../summary`, `.../training`, `.../risks` | ✓ |
| Employee card | `GET/PATCH/DELETE /personnel/employees/{id}/import-card` | ✓ |

**HR Sync (separate Core contour):** `hr_sync_routes.py` — `/directory/personnel/sync/*` (export/preview/apply). **Out of scope.**

### 3.3 Consumer audit

| Consumer type | Legacy `POST /import/employees_*` | Evidence |
|---------------|-------------------------------------|----------|
| **UI** (`corpsite-ui`) | **0** | Grep: no matches |
| **Tests** | **0** | Grep `tests/`: no matches |
| **Ops scripts** (`scripts/`) | **0** | Grep: no matches |
| **App importers** | **2** (route module only) | `import_routes.py` → services |
| **External / undocumented** | **Unknown** | Requires access log (§2) |

### 3.4 OpenAPI verdict

| Check | Status |
|-------|--------|
| Legacy endpoints published | ✓ 2 routes registered |
| UI consumers | ✓ None |
| Repo consumers | ✓ Routes + services only |
| Active HR import isolated | ✓ Distinct path prefix `/personnel/import/` |
| Undocumented external callers | ✓ **None detected** (VPS nginx ~15d + backend journal 30d) |

**G3: PASS** — repo + VPS log evidence consistent with zero external consumers.

---

## 4. DBA-readiness audit (G4)

### 4.1 Schema inventory (Alembic)

| Table | Alembic origin | Later migrations |
|-------|----------------|------------------|
| `employees_import_stage` | `02b0d99063cd_baseline.py` | **None** |
| `employees_import` | `02b0d99063cd_baseline.py` | **None** |

Both defined in baseline only. No FK constraints in DDL. No PK. Flat staging shape.

### 4.2 Runtime code references

| Layer | `employees_import_stage` | `employees_import` |
|-------|--------------------------|----------------------|
| `app/` Python | **0 references** | **0 references** |
| `scripts/` | **0 references** | **0 references** |
| `tests/` | **0 references** | **0 references** |
| Legacy CSV/XLSX services | **Not used** | **Not used** |

**Finding:** CCR-007 tables appear **fully orphaned** from application code. CCR-006 legacy path writes directly to `employees` / `departments` / `positions` — **not** to `employees_import*`.

### 4.3 VPS production DBA audit (B2) — **closed**

| Table | Exists (prod) | Row count | FK | Views | Triggers | Functions | ETL refs | Runtime refs |
|-------|---------------|-----------|-----|-------|----------|-----------|----------|--------------|
| `employees_import_stage` | **Yes** | **0** | None | None | None | None | None | None |
| `employees_import` | **Yes** | **0** | None | None | None | None | None | None |

**DBA verdict:** **Safe to remove.** Archive not required. Optional DDL snapshot before drop (recommended hygiene, not a gate).

### 4.4 Local DB sample (dev, prior audit — supplementary)

| Table | Exists | Row count |
|-------|--------|-----------|
| `employees_import_stage` | Yes | 0 |
| `employees_import` | No (local diverges) | — |

Prod audit supersedes local sample for authorization purposes.

### 4.5 DBA queries (reference — executed on VPS)

```sql
-- Row counts
SELECT 'employees_import_stage' AS t, count(*) FROM public.employees_import_stage
UNION ALL
SELECT 'employees_import', count(*) FROM public.employees_import;

-- Existence
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name LIKE 'employees_import%';

-- FK / dependents
SELECT tc.table_name, tc.constraint_name, tc.constraint_type
FROM information_schema.table_constraints tc
WHERE tc.table_schema = 'public'
  AND tc.table_name LIKE 'employees_import%';
```

### 4.6 Safe retirement assessment

| Question | Production (VPS DBA) |
|----------|----------------------|
| App reads tables? | **No** |
| App writes tables? | **No** |
| FK dependents? | **None** |
| Views / triggers / functions? | **None** |
| ETL / manual SQL deps? | **None** |
| Drop vs archive | **Drop** — archive not required; optional DDL snapshot before drop |

### 4.7 CCR-006 ↔ CCR-007 coupling note

| Phase | Removes | Side effect |
|-------|---------|-------------|
| **A (CCR-006)** | Routes + import services | Stops privileged upsert into `employees`, `departments`, `positions` via legacy path |
| **B (CCR-007)** | `employees_import*` tables | Schema-only; **no runtime impact** if §4.2 holds |

**L3 (`departments`) risk:** legacy import can create department rows. Removal of CCR-006 is safe only if no external caller still uses it (G2).

### 4.8 DBA verdict

| Check | Status |
|-------|--------|
| Repo orphan confirmation | ✓ PASS |
| Production row audit | ✓ PASS (both tables empty) |
| FK / views / triggers / ETL | ✓ PASS (none) |
| DBA sign-off | ✓ **CLOSED** |

**G4 / B2 / CCR-007: CLEARED** for execution authorization (Phase B table drop).

---

## 5. Prerequisites checklist

| # | Prerequisite | Status | Blocker? |
|---|--------------|--------|----------|
| P0 | WP-CLEAN-005B doc audit complete | ✓ | — |
| P1 | 30-day access log zero (G2) | **PARTIAL** — nginx ~15d + journal 30d zero; formal nginx 30d pending | **YES** |
| P2 | OpenAPI / repo consumer audit (G3) | ✓ | — |
| P3 | External caller verification | ✓ VPS logs — zero | — |
| P4 | Production DBA audit (G4) | ✓ **Closed** | — |
| P5 | Ops sign-off (Med-High, CCR-006) | ☐ Pending B1 formal close or waiver | **YES** |
| P6 | Rollback SHA identified | ✓ `a9fcf5d` | — |
| P7 | Active HR import contour mapped | ✓ 37 routes protected | — |

---

## 6. Hygiene candidate (out of 005C scope)

| ID | Artifact | Finding | Recommendation |
|----|----------|---------|----------------|
| **CCR-024** (candidate) | `corpsite-ui/.../demoApi.client.ts` | HEAD still contains `listProfessionalDocuments*` / `fetchProfessionalDocumentsAvailability`; working tree shows file **deleted** (`D`), replacement `personnelJournalApi.client.ts` untracked; **0 importers** for stale exports | Register as **Dead orphan file** hygiene — separate micro-WP or commit completion of 005B rename/delete; **not blocking 005C** |

CCR-017/023 covered rename and export removal in active client; CCR-024 addresses uncommitted orphan file state only.

---

## 7. Blockers summary

| ID | Blocker | Owner | Status | Close action |
|----|---------|-------|--------|--------------|
| B1 | Formal 30-day nginx access-log window | Ops | **PARTIAL** | Option A: retention → 30d + re-audit; Option B: policy waiver (§2.5) |
| B2 | Production `employees_import*` row/ETL audit | DBA | **CLOSED** | ✓ Empty tables; no deps; safe to remove |
| B3 | Med-High sign-off for CCR-006 route removal | Ops + Architecture | **OPEN** | After B1 formal close **or** approved waiver |

---

## 8. Authorization matrix

| Gate | Required | Evidence | Cleared |
|------|----------|----------|---------|
| G2 Access log zero (formal 30d nginx) | Yes | §2 | **NO** — partial (~15d nginx + 30d journal) |
| G2-alt Policy waiver | Optional | §2.5 Option B | ☐ Not approved |
| G3 No active consumers | Yes | §3 | **YES** |
| G4 DBA safe on `employees_import*` | Yes | §4 | **YES** — CCR-007 blocker closed |
| CLEAN-GATE Med-High sign-off | Yes | — | **NO** — pending B1 |

### CCR status summary

| CCR | Blocker | Status |
|-----|---------|--------|
| **CCR-007** | DBA (B2) | **Closed** — safe to remove |
| **CCR-006** | Ops (B1) | **Partially closed** — zero usage in available logs; formal 30d nginx pending |

### Final decision

```
WP-CLEAN-005C execution: NOT AUTHORIZED (2026-07-07, post VPS audit)
```

**Blocked until:**

- **A)** Full 30-day nginx zero-hit window collected (retention ≥ 30d), **or**
- **B)** Explicit Architecture/Ops policy waiver approving backend journal + ~15-day nginx as sufficient.

CCR-007 (DBA) does **not** block kickoff; CCR-006 formal access-log gate remains the sole authorization blocker (+ B3 sign-off).

---

## 9. Related documents

| Document | Role |
|----------|------|
| [WP-CLEAN-005C-plan](./WP-CLEAN-005C-plan.md) | Execution plan (updated) |
| [CLEAN-GATE-001](./CLEAN-GATE-001-cleanup-decision-gate.md) | Gate policy |
| [WP-CLEAN-001 §8](./WP-CLEAN-001-personnel-domain-assessment.md#8-cleanup-candidates-register) | CCR-006/007 register |
| [ADR-038](../adr/ADR-038-employee-identity-hr-import-architecture.md) | Replacement import model |

---

*End of kickoff readiness report. Last updated post VPS Ops/DBA audit (2026-07-07).*
