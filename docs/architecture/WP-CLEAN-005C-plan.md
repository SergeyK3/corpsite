# WP-CLEAN-005C — Legacy Import Retirement Plan

| Field | Value |
|-------|-------|
| Date | 2026-07-07 (updated post VPS Ops/DBA audit) |
| Status | **VPS audit complete — execution NOT authorized** |
| CCR | CCR-006 (routes), CCR-007 (tables) |
| Prerequisite | [WP-CLEAN-005B doc audit](./WP-CLEAN-005B-doc-audit-report.md) ✓ |
| Readiness report | [WP-CLEAN-005C-kickoff-readiness](./WP-CLEAN-005C-kickoff-readiness.md) |

---

## 1. Scope

Retire the legacy bulk-import path superseded by ADR-038 HR import batches:

| Layer | Artifact | File / object |
|-------|----------|---------------|
| **CCR-006** | Legacy HTTP import | `POST /directory/import/employees_csv`, `POST /directory/import/employees_xlsx` in `import_routes.py` |
| **CCR-006** | Import services | `directory_import_csv.py`, `directory_import_xlsx.py` |
| **CCR-007** | Legacy staging tables | `employees_import*` (and related `departments` writes — L3) |

**Out of scope (this WP):** `hr_import_routes.py` / ADR-038 authoritative path, `hr_sync_routes.py`, employee CRUD, ADR-050/051 cutover items.

**Protected active contour:** 37 routes under `/directory/personnel/import/*` — see readiness report §3.2.

---

## 2. Gates (CLEAN-GATE-001)

| Gate | Requirement | Owner | Status |
|------|-------------|-------|--------|
| G1 | CCR register status ≥ `verified` for CCR-006 | Architecture | ☐ Open |
| G2 | **30-day access log zero** on `POST /directory/import/employees_csv\|xlsx` | Ops | **PARTIAL** — nginx ~15d zero; journal 30d zero; formal 30d nginx pending |
| G3 | OpenAPI / route audit — no undocumented callers | Architecture | ✓ PASS (repo + VPS logs) |
| G4 | DBA audit on `employees_import*` row counts + ETL dependencies | DBA / Ops | ✓ **CLOSED** — prod empty; safe to remove |
| G5 | CCR-007 blocked until CCR-006 route removal plan approved | Architecture | ☐ Pending authorization |
| G6 | Rollback commit identified before deletion | Dev | ✓ `a9fcf5d` |
| G7 | Post-removal report + register sync | Architecture | ☐ Post-execution |

**Med-High risk (CCR-006):** requires Architecture + Ops sign-off per CLEAN-GATE-001 — **not obtained**.

---

## 3. Pre-flight checklist (before kickoff)

| Item | Status | Notes |
|------|--------|-------|
| Collect 30-day production access log sample | **PARTIAL** | nginx ~15d zero (retention 14d rotate); journal 30d zero; formal gate open |
| Grep repo + ops scripts for legacy paths | ✓ | 0 callers outside routes/services |
| OpenAPI audit — legacy vs active HR import | ✓ | 2 legacy / 37 active routes mapped |
| DBA: `employees_import*` counts + FK | ✓ | Prod: both tables exist, **0 rows**, no deps — **safe to remove** |
| Confirm ADR-038 path authoritative | ✓ | UI uses `importApi.client.ts` → `/personnel/import/*` |
| Identify tests touching legacy import | ✓ | **0 tests** |
| Draft rollback SHA | ✓ | `a9fcf5d` |
| Hygiene: `demoApi.client.ts` orphan | Registered | CCR-024 candidate — out of 005C scope |

---

## 4. Key readiness findings

| Finding | Impact on 005C |
|---------|----------------|
| Legacy services write `employees`/`departments`/`positions` — **not** `employees_import*` | CCR-007 drop is low runtime risk; CCR-006 removal stops direct employee upsert |
| `employees_import*` — **0 app code references**; prod **0 rows**, no deps | **CCR-007 DBA blocker closed** |
| VPS nginx ~15d + backend journal 30d: **zero hits** | CCR-006 Ops **partially closed**; formal 30d nginx pending |
| No UI / script / test consumers | Confirmed |

Full evidence: [kickoff-readiness report](./WP-CLEAN-005C-kickoff-readiness.md).

---

## 5. Proposed execution order

Single logical package (005C), two phases within one WP — **execute only after authorization**:

| Phase | Action | Depends on |
|-------|--------|------------|
| **A** | Remove `import_routes.py` registration + route module + CSV/XLSX services | G2 zero + G3 external clear + ops sign-off |
| **B** | Drop `employees_import*` tables (Alembic migration) | Phase A deployed + G4 DBA sign-off + row audit |

Do **not** merge with 005A/005B/006. Independent G1–G7 evidence set required.

---

## 6. Blockers (active)

| ID | Blocker | Owner | Status |
|----|---------|-------|--------|
| **B1** | Formal 30-day nginx access-log window | Ops | **PARTIAL** — see readiness §2.5 |
| **B2** | Production `employees_import*` row/ETL audit | DBA | **CLOSED** |
| **B3** | Med-High removal sign-off | Ops + Architecture | **OPEN** — after B1 close or waiver |

### Recommended Ops action (unblock B1)

1. **Option A:** Increase nginx log retention to **≥ 30 days**, re-audit, attach zero-hit evidence.
2. **Option B:** Policy waiver — Architecture/Ops accept backend journal (30d) + nginx (~15d) as sufficient evidence.

---

## 7. Verification plan (post-execution)

| Check | Command / method |
|-------|------------------|
| Route removal | `pytest` green; OpenAPI diff shows endpoints gone |
| No importers | `rg import_routes\|import_employees_csv\|import_employees_xlsx` in `app/` |
| UI unaffected | `npm run build` in corpsite-ui |
| HR import path | ADR-038 routes still registered and tested |
| DB migration | `alembic upgrade head` on clean DB; downgrade tested in staging |

---

## 8. Risks

| Risk | L | I | Mitigation |
|------|:-:|:-:|------------|
| Hidden script still calls legacy CSV/XLSX | M | High | 30d access log + ops script inventory |
| `departments` table still written by legacy path | M | Med | DBA audit before table drop |
| Confusion with ADR-038 import | L | Med | Explicit scope boundary in report |

---

## 9. Related documents

| Document | Role |
|----------|------|
| [WP-CLEAN-005C-kickoff-readiness](./WP-CLEAN-005C-kickoff-readiness.md) | Evidence + authorization decision |
| [WP-CLEAN-001 §8](./WP-CLEAN-001-personnel-domain-assessment.md#8-cleanup-candidates-register) | CCR-006/007 register |
| [WP-CLEAN-PROGRAM-REVIEW §7](./WP-CLEAN-PROGRAM-REVIEW.md#wp-clean-005--legacy-backend--demo-retirement) | Program status |
| [CLEAN-GATE-001](./CLEAN-GATE-001-cleanup-decision-gate.md) | Gate policy |
| [ADR-038](../adr/ADR-038-data-sync-and-hr-import-persistence.md) | Replacement import model |

---

## 10. Decision

| Question | Answer (2026-07-07, post VPS audit) |
|----------|-------------------------------------|
| Kickoff readiness audit complete? | **YES** |
| VPS Ops/DBA audit complete? | **YES** |
| CCR-007 (DBA) blocker closed? | **YES** — safe to remove |
| CCR-006 (Ops) blocker closed? | **PARTIAL** — zero usage; formal 30d nginx pending |
| Execution authorized? | **NO** |
| Unblock path | **A)** 30d nginx retention + zero re-audit, **or** **B)** explicit policy waiver + B3 sign-off |

**Demo contour (CCR-008/023): closed.** Legacy import retirement **blocked** on B1 formal gate (or approved waiver).

---

*Updated post VPS Ops/DBA audit (2026-07-07).*
