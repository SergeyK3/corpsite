# WP-CLEAN-PROGRAM-REVIEW — Personnel Cleanup Program

| Field | Value |
|-------|-------|
| Date | 2026-07-07 |
| Scope | Full program status through Phase 2 pause |
| Register authority | [WP-CLEAN-001 §8](./WP-CLEAN-001-personnel-domain-assessment.md#8-cleanup-candidates-register) |
| Gate policy | [CLEAN-GATE-001](./CLEAN-GATE-001-cleanup-decision-gate.md) |
| Phase 2 closure | [WP-CLEAN-PHASE2-CLOSURE-REPORT](./WP-CLEAN-PHASE2-CLOSURE-REPORT.md) |
| Runtime changes | **None** in this review |

---

## Cleanup Program Roadmap

| Phase | Status | Milestone |
|-------|--------|-----------|
| **Phase 1** — Dead orphan removal | **Complete** | WP-CLEAN-003A…D |
| **Phase 2** — Simplification + legacy retirement | **Paused (Governance)** | B1 blocker — see [closure report](./WP-CLEAN-PHASE2-CLOSURE-REPORT.md) |
| **Phase 3** — ADR cutover cleanup | **Not started** | WP-CLEAN-006 |

**Next milestone:** WP-CLEAN-005C authorization (after B1 close or waiver).

---

## 1. Purpose

Close **Phase 1** of the Personnel Domain Cleanup Program (orphan removal under CLEAN-GATE-001), re-assess every remaining Cleanup Candidate Register (CCR) entry, scan for **new** candidates exposed by removals and by post-removal codebase review, and define **Phase 2** work packages (WP-CLEAN-004…005).

This review does **not** authorize deletion. It updates classification, blocking dependencies, and recommended next packages only.

---

## 2. Review scope

| In scope | Out of scope |
|----------|--------------|
| CCR-001…020 register rows | HR Head permission fix (separate functional WP) |
| New CCR-021…023 from Phase 1 scan | ADR-050/051 implementation |
| Legacy / Transitional / Dead reclassification | Database migrations |
| Dependency matrix | Runtime code changes |
| WP-CLEAN-004 / 005 proposals | Automatic removal |

**Evidence methods:** register sync, repo-wide grep (imports, routes), ADR cross-reference, WP-CLEAN-003A…D post-removal reports, backend router inventory, frontend client usage scan.

---

## 3. Completed removals (Phase 1)

| CCR | Artifact | WP | Rollback base | G7 |
|-----|----------|-----|---------------|-----|
| CCR-001 | `corpsite-ui/app/directory/_components/DirectorySidebar.tsx` | [003A](./WP-CLEAN-003A-post-removal-report.md) | `0c678749` | ✓ |
| CCR-002 | `corpsite-ui/app/directory/_lib/api.client.ts` | [003B](./WP-CLEAN-003B-post-removal-report.md) | `0c678749` | ✓ |
| CCR-003 | `app/api/directory.ts` | [003C audit](./WP-CLEAN-003C-CCR003-audit.md) + [003D](./WP-CLEAN-003D-post-removal-report.md) | `d1c31cd` | ✓ |

**Phase 1 outcome:** All confirmed **Dead** orphans in the original CCR-001…003 set are removed. Zero runtime regressions reported (build + 499 frontend tests + targeted backend tests per removal reports).

**Invariant validated:** Audit-before-delete (003C → 003D) prevented misclassification of HTTP `/api/directory/` proxy vs misplaced TypeScript source file.

---

## 4. Remaining candidates — summary by class

### 4.1. Dead (eligible for removal — Phase 2, not now)

| ID | Artifact | Status | Target WP | Notes |
|----|----------|--------|-----------|-------|
| **CCR-021** | ~~`corpsite-ui/app/directory/employees/_lib/directory.ts`~~ | **removed** | 005A | Zero importers; superseded by `org-units/_lib/api.client.ts` |
| **CCR-022** | ~~`corpsite-ui/app/directory/employees/_lib/api.server.ts`~~ | **removed** | 005A | Zero importers; pages use `api.client.ts` |
| **CCR-023** | ~~`personnelJournalApi.client.ts` demo exports~~ | **removed** | 005B | Retired with CCR-008 demo contour |

**CCR-021…023:** all removed (005A + 005B). Gated removal complete for Phase 2 orphan/demo adapter scan.

### 4.2. Transitional (required until migration completes)

| ID | Artifact | Blocked by | Target WP |
|----|----------|------------|-----------|
| CCR-010 | `/directory/employees/[id]` redirect alias | **frozen** — ADR-045 migration complete (004) | — |
| CCR-013 | `persons` / `person_assignments` | **Dual registry** (ARCH-001); not removable | — (rejected removal) |
| CCR-015 | `access_grants` + `users.role_id` | **ADR-051 cutover** — shadow parity | 004+ |
| CCR-016 | `cabinet_access_shadow_service` | **ADR-051 cutover** — OPS-030 | 004+ |
| CCR-017 | ~~`demoApi.client.ts`~~ → `personnelJournalApi.client.ts` | **archived** (004 complete) | — |
| CCR-018 | `hr_review_override_backfill_service` | **ADR-043** ops sign-off | — (ops tool) |
| CCR-019 | `access_resolver_service` | **ADR-051** — runtime enforcement | — (rejected removal) |
| CCR-020 | `user_linkage_*` suite | **ADR-044** linkage program | — (rejected removal) |

**Additional transitional (register-only, not CCR IDs):** `users.employee_id`, `operational_contact_service`, `cabinet_access_resolver_service`, `access_grant_service` — see WP-CLEAN-001 §3.4–3.6.

### 4.3. Legacy (frozen until separate decision / audit)

| ID | Artifact | Blocked by | Target WP |
|----|----------|------------|-----------|
| CCR-005 | `/directory` home redirect | **frozen** — alias keep (004) | — |
| CCR-006 | `import_routes.py` + CSV/XLSX | Formal 30d nginx log; waiver alt. | **005C** — Ops **partial** (zero ~15d nginx + 30d journal) |
| CCR-007 | `employees_import*` tables | CCR-006 + DBA audit | **005C** — DBA **closed** (empty; safe to remove) |
| CCR-008 | ~~`professional_documents*` demo API~~ | **removed** (005B) — optional local tables remain |
| CCR-009 | `/directory/employees` redirect | Bookmark policy — **keep** | — (blocked keep) |
| CCR-014 | Global `positions` catalog | **ADR-050 Phase 3** Employment FK retarget | **004+** |
| L3 | `departments` table | CCR-006/007 retirement | **005** |
| L8 | `legacy_position_mapping` | **ADR-050 Phase 3** | **004+** |

### 4.4. Resolved / non-removal register entries

| ID | Artifact | Class | Status |
|----|----------|-------|--------|
| CCR-004 | Runbook `hr-dual-personnel-registry.md` | Gap → closed | **verified** — keep |
| CCR-011 | `employees` + CRUD | Core | **rejected** |
| CCR-012 | `employee_events` / Journal | Core | **rejected** |

---

## 5. Dependency matrix

| Candidate | Blocking ADR / migration | Can remove when |
|-----------|-------------------------|-----------------|
| CCR-005 | ADR-045 nav (`/directory/staff` primary) | Redirect deployed ✓ (004) |
| CCR-006, CCR-007, L3 | ADR-038 HR import batches authoritative | Legacy path zero in VPS logs; **formal 30d nginx** or waiver; CCR-007 DBA ✓ |
| CCR-008 | ADR-037 Phase 1A+ (`employee_documents`) | Demo **routes/service removed** ✓ (005B); optional local tables out of scope |
| CCR-009 | ADR-045 bookmark compatibility | Policy decision only (likely never) |
| CCR-010 | ADR-045 detail URL | Redirect + staff drawer deep-link ✓ (004) |
| CCR-014, L8 | **ADR-050 Phase 3** | Employment FK on `org_unique_position` |
| CCR-015, CCR-016, CCR-019 | **ADR-051 cutover** | Cabinet resolver authoritative; shadow clean |
| CCR-018 | **ADR-043** ops | Override backfill complete + ops sign-off |
| CCR-020 | **ADR-044** | User linkage program complete |
| CCR-021, CCR-022 | None (Dead orphans) | **Removed** ✓ (005A) |
| CCR-023 | CCR-008 demo contour (family) | **Removed** ✓ (005B, after 008 backend) |
| CCR-017 | None (rename) | **Complete** (004) |
| Position Cabinet gap | **ARCH-001** task assessment | Tasks ↔ cabinet wiring ADR (future) |

---

## 6. New candidates (post CCR-001…003 scan)

> **Historical snapshot** (pre-005B). CCR-021…023 **removed** in WP-CLEAN-005A/005B. Rows below document the original scan; do not treat CCR-008/023 as open candidates.

Discovered during program review — **registered as CCR-021…023**.

| Scan area | Finding | CCR | Current status |
|-----------|---------|-----|----------------|
| Frontend orphans | `employees/_lib/directory.ts` — 0 imports | CCR-021 | **removed** (005A) |
| Frontend orphans | `employees/_lib/api.server.ts` — 0 imports | CCR-022 | **removed** (005A) |
| Obsolete adapter exports | `personnelJournalApi.client.ts` professional-documents functions | CCR-023 | **removed** (005B) |
| Backend endpoints (Legacy) | `POST /directory/import/employees_csv\|xlsx` — privileged, no UI | CCR-006 | **open** → 005C; VPS zero usage (partial window) |
| Backend endpoints (Legacy) | ~~`GET /directory/professional-documents*`~~ | CCR-008 | **removed** (005B) |
| Backend endpoints (Transitional) | `hr_sync_routes.py` — admin sync only, privileged | — | Not a removal candidate (Core admin) |
| Compatibility wrappers | None new beyond CCR-021/022 | — | — |
| Feature flags | No personnel-domain `FEATURE_*` toggles found | — | Document only |
| Re-export files | None found | — | — |

**Not promoted to CCR:** `hr_sync_routes` (active admin sync UI), `query.ts` / `types.ts` (active staff module), `documentsApi.client.ts` (Core ADR-037).

---

## 7. Recommended next cleanup packages

### WP-CLEAN-004 — Frontend simplification & URL hygiene (**complete**, 2026-07-07)

See [WP-CLEAN-004 report](./WP-CLEAN-004-post-removal-report.md).

| Item | CCR | Result |
|------|-----|--------|
| `/directory` → `/directory/staff` | CCR-005 | Server redirect (query preserved) |
| `/directory/employees/[id]` → staff drawer | CCR-010 | Redirect + `employeeId` deep-link |
| Rename journal client | CCR-017 | `personnelJournalApi.client.ts` |
| Positions catalog UI read paths | CCR-014 | **Blocked** ADR-050 Ph.3 — not in scope |

**No backend schema drops in 004.**

### WP-CLEAN-005 — Legacy backend & demo retirement

| Sub-WP | Items | Status |
|--------|-------|--------|
| **005A** | CCR-021, CCR-022 (verified Dead orphans) | ✓ [report](./WP-CLEAN-005A-post-removal-report.md) |
| **005B** | CCR-008 demo API + CCR-023 exports (unified demo contour) | ✓ [report](./WP-CLEAN-005B-post-removal-report.md) |
| **005C** | CCR-006 legacy import routes + CCR-007 tables | **Blocked** — [readiness](./WP-CLEAN-005C-kickoff-readiness.md); CCR-007 ✓; CCR-006 formal nginx 30d pending |

### WP-CLEAN-006 (future) — ADR-gated simplification

Blocked until **ADR-051 cutover** (CCR-015/016/019) and **ADR-050 Phase 3** (CCR-014/L8). Not scheduled in Phase 2.

---

## 8. Program status

| Phase | WPs | Status |
|-------|-----|--------|
| **Assessment** | WP-CLEAN-001 R2 | ✓ Complete |
| **Governance** | WP-CLEAN-002 + CLEAN-GATE-001 | ✓ Complete |
| **Phase 1 — Dead orphan removal** | WP-CLEAN-003A, 003B, 003C, 003D | ✓ **Complete** |
| **Phase 1 review** | WP-CLEAN-PROGRAM-REVIEW | ✓ **Complete** (this document) |
| **Phase 2 — Simplification** | WP-CLEAN-004 | ✓ **Complete** ([report](./WP-CLEAN-004-post-removal-report.md)) |
| **Phase 2 — Legacy retirement (orphans)** | WP-CLEAN-005A | ✓ **Complete** ([report](./WP-CLEAN-005A-post-removal-report.md)) |
| **Phase 2 — Legacy retirement (demo contour)** | WP-CLEAN-005B | ✓ **Complete** ([report](./WP-CLEAN-005B-post-removal-report.md)) |
| **Phase 2 — Legacy retirement (import)** | WP-CLEAN-005C | **Paused** — readiness complete; execution not authorized ([closure](./WP-CLEAN-PHASE2-CLOSURE-REPORT.md)) |
| **Phase 2 — Official stop** | WP-CLEAN-PHASE2-CLOSURE | ✓ **Published** ([report](./WP-CLEAN-PHASE2-CLOSURE-REPORT.md)) |
| **Phase 3 — ADR cutover cleanup** | WP-CLEAN-006+ | Blocked ADR-050/051 |

### Phase 1 complete — definition of done

- [x] CCR-001…003 removed with G7 evidence
- [x] Register synchronized with removal reports
- [x] No remaining **Unknown** orphans from original inventory
- [x] New orphans from scan registered (CCR-021…023)
- [x] Legacy and Transitional candidates explicitly blocked with ADR references

---

## 9. Recommendations

1. **Cleanup Program paused at Phase 2** — official closure: [WP-CLEAN-PHASE2-CLOSURE-REPORT](./WP-CLEAN-PHASE2-CLOSURE-REPORT.md). Resume after B1 (30d nginx zero or waiver).
2. **Ops action:** increase nginx log retention to ≥ 30 days **or** obtain Architecture/Ops waiver for partial window evidence.
3. **Maintain rejected status** on Core/Transitional enforcement paths (CCR-011/012/019/020) — do not re-open without ADR amendment.
4. **Program discipline:** one WP = one logically complete candidate group (005A ≠ 005B ≠ 005C) — preserves traceability, rollback, and independent G1–G7 evidence sets.
5. ~~**Optional:** update `docs/demo/HR-DEMO-LOCAL-RUNBOOK.md`~~ — **Done** ([doc audit](./WP-CLEAN-005B-doc-audit-report.md)).
6. **Optional:** production access-log sample for CCR-005/009/010 redirect aliases before ever removing alias routes.
7. **Next program sync point:** WP-CLEAN-005C authorization → execution → G7 report.

---

## 10. Related documents

| Document | Role |
|----------|------|
| [WP-CLEAN-001 §8](./WP-CLEAN-001-personnel-domain-assessment.md#8-cleanup-candidates-register) | Authoritative CCR table (updated) |
| [deprecated/personnel/INDEX.md](../deprecated/personnel/INDEX.md) | Deprecation markers |
| [WP-CLEAN-003A…D reports](./WP-CLEAN-003A-post-removal-report.md) | Phase 1 evidence |
| [WP-CLEAN-005B doc audit](./WP-CLEAN-005B-doc-audit-report.md) | Post-cleanup demo contour documentation |
| [WP-CLEAN-PHASE2-CLOSURE-REPORT](./WP-CLEAN-PHASE2-CLOSURE-REPORT.md) | Official Phase 2 stop + resume criteria |
| [WP-CLEAN-005C kickoff-readiness](./WP-CLEAN-005C-kickoff-readiness.md) | VPS Ops/DBA evidence + authorization decision |
| [WP-CLEAN-005C plan](./WP-CLEAN-005C-plan.md) | Execution plan (CCR-006/007) |
| [ADR-045](../adr/ADR-045-personnel-hr-processes-split.md) | Staff vs HR processes |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) Phase 3 | Positions catalog |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | Access cutover |

---

*Phase 2 paused — [closure report](./WP-CLEAN-PHASE2-CLOSURE-REPORT.md) published 2026-07-07.*
