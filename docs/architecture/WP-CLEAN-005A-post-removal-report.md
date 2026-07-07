# WP-CLEAN-005A — Post-Removal Report (CCR-021, CCR-022)

| Field | Value |
|------|----------|
| Date | 2026-07-07 |
| Scope | Remove two verified Dead frontend orphans |
| CCR | CCR-021, CCR-022 |
| Status | **Complete** |
| Gate policy | [CLEAN-GATE-001](./CLEAN-GATE-001-cleanup-decision-gate.md) G1–G7 |

---

## 1. CCR-021 — `employees/_lib/directory.ts`

### G1 — Inventory

| Check | Result |
|-------|--------|
| CCR register match | CCR-021 → `corpsite-ui/app/directory/employees/_lib/directory.ts` ✓ |
| Purpose | Client-side org-tree fetch (`getOrgTree` → `/directory/org-units/tree`) |
| Runtime owner (intended) | Employees module — **never wired** |
| Architecture owner | Directory / org-units contract (ADR-031); canonical: `org-units/_lib/api.client.ts` (`getOrgUnitsTree`) |

### G2 — Reference audit

| Check | Result |
|-------|--------|
| Static imports (`from '...directory'`, `@/.../directory.ts`) | **0** |
| Dynamic imports / `require` / `next/dynamic` | **0** |
| Barrel re-exports in `employees/_lib/` | **None** (no `index.ts`) |
| TypeScript path aliases | **0** references |
| Tests | **0** |
| Exported symbol grep (`getOrgTree` from this file) | **0** importers (local type names in other files are unrelated inline types) |

### G3 — Classification validation

**Dead** confirmed. No active usage discovered. Proceed with removal.

### G4 — Removal

**Deleted:** `corpsite-ui/app/directory/employees/_lib/directory.ts`

**Preserved:** `org-units/_lib/api.client.ts`, `employees/_lib/api.client.ts`, `employees/_lib/types.ts` (`OrgTreeNode` types remain in types.ts for live module).

---

## 2. CCR-022 — `employees/_lib/api.server.ts`

### G1 — Inventory

| Check | Result |
|-------|--------|
| CCR register match | CCR-022 → `corpsite-ui/app/directory/employees/_lib/api.server.ts` ✓ |
| Purpose | Server-only fetch layer (`getDepartments`, `getPositions`, `getEmployees`, `getEmployeeById`) |
| Runtime owner (intended) | Server components for employees pages — **never wired** |
| Architecture owner | Directory employees module; canonical: `employees/_lib/api.client.ts` (client-side, used by `EmployeesPageClient`, drawers, admin tabs) |

### G2 — Reference audit

| Check | Result |
|-------|--------|
| Static imports (`api.server`) | **0** |
| Dynamic imports | **0** |
| `server-only` package consumers | **0** (only this file imported it) |
| Exported symbol grep (`getEmployeeById`) | **0** importers outside deleted file |
| Pages / server components | Staff and personnel pages use `EmployeesPageClient` + `api.client.ts` only |

### G3 — Classification validation

**Dead** confirmed. No active usage discovered. Proceed with removal.

### G4 — Removal

**Deleted:** `corpsite-ui/app/directory/employees/_lib/api.server.ts`

**Preserved:** `employees/_lib/api.client.ts`, all employee UI components, backend FastAPI routes unchanged.

---

## 3. G5 — Build verification

| Command | Result |
|---------|--------|
| `npm run build` (corpsite-ui) | **Pass** (exit 0). TypeScript OK. Route table unchanged (23 static + dynamic routes). |
| `npm test` | **499/499 passed**, 75 files, exit 0 |

Post-removal grep: zero runtime references to deleted paths; only governance/historical docs mention former files.

---

## 4. G6 — Rollback readiness

Pre-removal commit (rollback base): `a9fcf5d74f901522e4fe0d998a40d6d538e8153e`

```bash
git checkout a9fcf5d74f901522e4fe0d998a40d6d538e8153e -- \
  corpsite-ui/app/directory/employees/_lib/directory.ts \
  corpsite-ui/app/directory/employees/_lib/api.server.ts
```

Or revert the WP-CLEAN-005A commit after it is committed.

---

## 5. G7 — Documentation

| Artifact | Update |
|----------|--------|
| CCR-021 register (WP-CLEAN-001 §8) | Status → **removed** |
| CCR-022 register (WP-CLEAN-001 §8) | Status → **removed** |
| [CCR-021 marker](../deprecated/personnel/CCR-021-employees-directory-ts.md) | Created — removed + G7 |
| [CCR-022 marker](../deprecated/personnel/CCR-022-employees-api-server-ts.md) | Created — removed + G7 |
| [deprecated/personnel/INDEX.md](../deprecated/personnel/INDEX.md) | Moved 021/022 to Removed section |
| [WP-CLEAN-PROGRAM-REVIEW](./WP-CLEAN-PROGRAM-REVIEW.md) | 005A complete; next 005B |

---

## 6. Runtime impact

**None.** Both files were never imported. Production employees/staff flows use `api.client.ts` and `org-units/_lib/api.client.ts`. No API, permission, routing, or backend behavior changed.

---

## 7. Program discipline note

WP-CLEAN-005A removes **one logical group** (verified Dead frontend orphans discovered in Phase 1 scan). **WP-CLEAN-005B** (CCR-023 dead exports) remains a separate WP — do not batch.

---

## 8. Readiness for WP-CLEAN-005B

**Ready** for legacy import retirement (CCR-006/007) as a **separate** gated WP — requires access logs + DBA audit. Demo contour (008/023) is closed.

---

*End of WP-CLEAN-005A report.*
