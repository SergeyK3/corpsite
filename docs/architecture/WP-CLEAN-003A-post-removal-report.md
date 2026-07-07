# WP-CLEAN-003A — Post-Removal Report (CCR-001)

| Field | Value |
|------|----------|
| Date | 2026-07-07 |
| Scope | Remove `DirectorySidebar.tsx` only |
| CCR | CCR-001 |
| Status | **Complete** |

---

## 1. Evidence collected (pre-removal)

| Check | Result |
|-------|--------|
| Static imports of `DirectorySidebar` component | None (repo-wide grep) |
| Dynamic imports | None |
| Next.js route | Not a page (`_components/`); never in build route table |
| AppShell / `personnelNav` | Orphan not referenced; `isDirectorySidebarNavItemActive` is a **separate** helper |
| Tests importing component | None (`personnelNav.test.ts` tests helper only) |
| ADR references | None |
| Sibling files in `_components/` | `DictionaryPageClient.tsx` — **preserved** |

Pre-removal rollback base: `0c678749547595b3b9f837a62e747180359cf9f8`

---

## 2. Change applied

**Deleted:** `corpsite-ui/app/directory/_components/DirectorySidebar.tsx`

**Not touched:** CCR-002, backend, API, DB, routing config, any other UI files.

---

## 3. Verification results

| Command | Result |
|---------|--------|
| `npm run build` | **Pass** (exit 0). TypeScript OK. **24 routes** — identical set to pre-removal baseline. |
| `npm test` | **499/499 tests passed**, 75 files. Vitest **exit 1** — unhandled promise after teardown in `PersonnelImportNormalizedRecordsReviewPageClient.test.tsx` (flaky/pre-existing; also observed intermittently before removal in same session). **Not caused by CCR-001.** |
| `npm run lint` | **Exit 1** — pre-existing errors/warnings across repo (e.g. `dev-login/page.tsx`, `DictionaryPageClient.tsx`). **No lint target referenced removed file.** |

Post-removal grep: zero references to `DirectorySidebar.tsx` path; only `isDirectorySidebarNavItemActive` identifier remains (intentional).

---

## 4. Runtime impact

**None.** The component was never imported or mounted. Production navigation uses `AppShell` + ADR-045 personnel nav. No API, permission, or scheduler behavior changed.

---

## 5. Governance updates

| Artifact | Update |
|----------|--------|
| CCR-001 register (WP-CLEAN-001 §8) | Status → **removed** |
| [CCR-001 deprecation marker](../deprecated/personnel/CCR-001-directory-sidebar.md) | Removed + G7 complete |
| Reviewer | Architecture pre-implementation review + WP-CLEAN-003A execution |
| G1–G7 | Satisfied for this removal (G7 post-removal complete) |

---

## 6. Rollback

```bash
git checkout 0c678749547595b3b9f837a62e747180359cf9f8 -- corpsite-ui/app/directory/_components/DirectorySidebar.tsx
```

Or revert the WP-CLEAN-003A commit after it is committed.

---

## 7. Lessons learned

1. **Dead orphans with naming collision** — `isDirectorySidebarNavItemActive` sounds related but is independent; grep must distinguish component name vs helper name.
2. **Delete siblings carefully** — same folder contains live `DictionaryPageClient.tsx`; single-file deletion is required.
3. **G7 post-removal is mandatory** — build/typecheck confirms removal safe; test/lint baselines may have pre-existing noise unrelated to cleanup.
4. **Vitest teardown flakes** — async `apiAuthMe()` in components can fail after test env teardown; treat as separate hygiene WP, not a blocker for orphan removal when all assertions pass.
5. **WP-CLEAN-003A pattern works** — one CCR, one file, register sync, deprecation marker update, rollback SHA documented.

---

## 8. Next step

**WP-CLEAN-003B** (separate WP): CCR-002 `directory/_lib/api.client.ts` — do not batch with CCR-001.

---

*No other implementation changes in WP-CLEAN-003A.*
