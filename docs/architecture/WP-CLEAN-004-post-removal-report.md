# WP-CLEAN-004 — Frontend Simplification Report

| Field | Value |
|------|----------|
| Date | 2026-07-07 |
| Scope | CCR-005 redirect cleanup; CCR-010 ADR-045 URL migration; CCR-017 journal client rename |
| Status | **Complete** |
| Runtime changes | **Yes** — redirects, deep-link drawer, client rename |
| Out of scope | CCR-021…023 removal; ADR-050 Ph.3; ADR-051 cutover |

---

## 1. Per-CCR analysis and actions

### CCR-005 — `/directory` home redirect

| Aspect | Finding |
|--------|---------|
| **Current usage (pre-change)** | Standalone client page (`page.tsx`, ~240 lines) with duplicate employee list; not in ADR-045 nav; reachable via direct URL and legacy links to `/directory/org`, `/directory/employees` |
| **Architectural goal** | Single canonical personnel entry: `/directory/staff` (ADR-045) |
| **Risk** | Medium — bookmarks to `/directory` and query params (`org_unit_id`, filters) |
| **Runtime vs docs** | **Runtime required** — server redirect with query-string preservation |
| **Change** | Replaced page body with `redirect()` to `/directory/staff` (+ preserved search params) |

### CCR-010 — `/directory/employees/[id]` URL migration (ADR-045)

| Aspect | Finding |
|--------|---------|
| **Current usage (pre-change)** | Standalone client detail page (~125 lines); superseded by staff drawer; runbook reference in `POSITIONS_SYNC_RUNBOOK.md` |
| **Architectural goal** | Staff drawer is sole employee-card UX; legacy URL becomes compatibility alias |
| **Risk** | High — external bookmarks and ops runbooks |
| **Runtime vs docs** | **Runtime required** — redirect + deep-link support in `EmployeesPageClient` |
| **Change** | Redirect to `/directory/staff?employeeId={id}`; drawer auto-opens from `employeeId` param; param cleared on drawer close |
| **G5 milestone** | ADR-045 detail URL migration — **satisfied** |

### CCR-017 — rename active journal client

| Aspect | Finding |
|--------|---------|
| **Current usage** | `listPersonnelEvents` consumed by `PersonnelJournalPageClient`; dead `listProfessionalDocuments*` exports had zero UI callers (CCR-023) |
| **Architectural goal** | Naming reflects production journal API, not demo probe |
| **Risk** | Low — single import site |
| **Runtime vs docs** | **Runtime required** — rename file + import sweep; dead exports retained with `@deprecated CCR-023` markers for WP-CLEAN-005B |
| **Change** | `demoApi.client.ts` → `personnelJournalApi.client.ts`; `mapDemoApiError` → `mapPersonnelJournalApiError` |

---

## 2. Changes applied

| CCR | Artifact | Action |
|-----|----------|--------|
| CCR-005 | `corpsite-ui/app/directory/page.tsx` | Server redirect → `/directory/staff` |
| CCR-010 | `corpsite-ui/app/directory/employees/[id]/page.tsx` | Server redirect → `/directory/staff?employeeId=` |
| CCR-010 | `EmployeesPageClient.tsx` | Deep-link drawer from `employeeId` query param |
| CCR-017 | `personnelJournalApi.client.ts` | New canonical journal client |
| CCR-017 | ~~`demoApi.client.ts`~~ | Deleted (renamed) |
| CCR-017 | `PersonnelJournalPageClient.tsx` | Import path updated |

**Not touched:** CCR-021, CCR-022, CCR-023 exports (body preserved in renamed file), backend, DB, CCR-009 redirect, ADR-050/051 paths.

---

## 3. Verification

| Command | Result |
|---------|--------|
| `npm run build` (corpsite-ui) | **Pass** (exit 0, Next.js 16.1.1) |
| `npm test` | **499/499 passed**, 75 files |
| Grep `demoApi.client` in corpsite-ui | **0** runtime imports post-rename |

---

## 4. What remains transitional

| Item | Status | Next WP |
|------|--------|---------|
| `/directory/employees` redirect (CCR-009) | **Keep** — bookmark alias | — |
| `/directory/employees/[id]` redirect (CCR-010) | **Keep** — bookmark alias | analytics / optional removal |
| `/directory` redirect (CCR-005) | **Keep** — bookmark alias | analytics / optional removal |
| `personnelJournalApi.client.ts` demo-doc exports (CCR-023) | **Keep** — `@deprecated` | WP-CLEAN-005B |
| CCR-014, L8 (ADR-050 Ph.3) | **Blocked** | WP-CLEAN-006 |
| CCR-015/016/019 (ADR-051) | **Blocked** | WP-CLEAN-006 |

---

## 5. Dependencies eliminated / blockers cleared

| Dependency | Outcome |
|------------|---------|
| ADR-045 detail URL migration (G5 for CCR-010) | **Cleared** — redirect + drawer deep-link live |
| Duplicate `/directory` employee list UX | **Eliminated** — redirect only |
| Misleading `demoApi.client.ts` name for active journal | **Eliminated** — renamed client |
| WP-CLEAN-005A prerequisite (architectural prep) | **Cleared** — no further Phase 2 prep before orphan removals |

---

## 6. Readiness for WP-CLEAN-005A

**Ready.** Phase 2 architectural simplification (004 scope) is complete. Next packages may proceed as gated orphan removals:

- **WP-CLEAN-005A** — CCR-021, CCR-022 (verified dead orphans)
- **WP-CLEAN-005B** — CCR-023 dead exports, then CCR-008 backend
- **WP-CLEAN-005C** — CCR-006/007 legacy import

No additional architectural preparation required before 005A.

---

## 7. Rollback

```bash
git checkout <pre-WP-CLEAN-004> -- \
  corpsite-ui/app/directory/page.tsx \
  corpsite-ui/app/directory/employees/[id]/page.tsx \
  corpsite-ui/app/directory/employees/_components/EmployeesPageClient.tsx \
  corpsite-ui/app/directory/personnel/_lib/demoApi.client.ts \
  corpsite-ui/app/directory/personnel/_lib/personnelJournalApi.client.ts \
  corpsite-ui/app/directory/personnel/_components/PersonnelJournalPageClient.tsx
```

---

## 8. Governance updates

| Artifact | Update |
|----------|--------|
| CCR-005 register | Status → **frozen** (redirect alias) |
| CCR-010 register | Status → **frozen** (redirect alias); G5 cleared |
| CCR-017 register | Status → **archived** (rename complete) |
| [CCR-005 marker](../deprecated/personnel/CCR-005-directory-home.md) | Redirect deployed |
| [CCR-010 marker](../deprecated/personnel/CCR-010-employees-detail-redirect.md) | Created |
| [PROGRAM-REVIEW](./WP-CLEAN-PROGRAM-REVIEW.md) | Phase 2 §004 complete |
| [WP-CLEAN-001 §8](./WP-CLEAN-001-personnel-domain-assessment.md#8-cleanup-candidates-register) | CCR rows synchronized |
