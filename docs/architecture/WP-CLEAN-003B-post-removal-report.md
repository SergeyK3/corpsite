# WP-CLEAN-003B — Post-Removal Report (CCR-002)

| Field | Value |
|------|----------|
| Date | 2026-07-07 |
| Scope | Remove `directory/_lib/api.client.ts` only |
| CCR | CCR-002 |
| Status | **Complete** |

---

## 1. Evidence collected (pre-removal)

| Check | Result |
|-------|--------|
| Static imports of `directory/_lib/api.client` | None (repo-wide grep) |
| Dynamic imports | None |
| Exports `apiDirectoryDepartments` / `apiDirectoryEmployees` | Only defined in removed file; zero call sites |
| Replacement client | `employees/_lib/api.client.ts` — active, multiple importers |
| Sibling files in `_lib/` | `dictionaries.config.ts` — **preserved** |
| CCR-003 | **Not touched** |

Pre-removal rollback base: `0c678749547595b3b9f837a62e747180359cf9f8`

---

## 2. Change applied

**Deleted:** `corpsite-ui/app/directory/_lib/api.client.ts`

**Preserved:**

- `corpsite-ui/app/directory/_lib/dictionaries.config.ts`
- `corpsite-ui/app/directory/employees/_lib/api.client.ts`

**Not touched:** CCR-003, backend, API, DB, routing config, any other UI files.

---

## 3. Verification results

| Command | Result |
|---------|--------|
| `npm run build` | **Pass** (exit 0). TypeScript OK. Route table unchanged from pre-removal baseline. |
| `npm test` | **499/499 tests passed**, 75 files, exit 0. **Not caused by CCR-002** — removed file had no test references. |
| `npm run lint` | **Exit 1** — pre-existing errors/warnings across repo. Representative baseline issues: `dev-login/page.tsx` (`react-hooks/purity` — `Date.now` during render), `DictionaryPageClient.tsx` (`@typescript-eslint/no-explicit-any`), `contacts/page.tsx` (`@next/next/no-html-link-for-pages`). **No lint target referenced removed file** (grep of lint output: zero matches for `directory/_lib/api.client`). Failures existed before this removal (same pattern documented in WP-CLEAN-003A). |

Post-removal grep: zero references to `directory/_lib/api.client` path or `apiDirectoryDepartments` / `apiDirectoryEmployees` symbols outside git history.

---

## 4. Runtime impact

**None.** The module was never imported. Live directory API access uses `employees/_lib/api.client.ts` and `org-units/_lib/api.client.ts`. No API, permission, or scheduler behavior changed.

---

## 5. Governance updates

| Artifact | Update |
|----------|--------|
| CCR-002 register (WP-CLEAN-001 §8) | Status → **removed** |
| [CCR-002 deprecation marker](../deprecated/personnel/CCR-002-directory-api-client.md) | Removed + G7 complete |
| [INDEX.md](../deprecated/personnel/INDEX.md) | CCR-002 moved to Removed section |
| Reviewer | Architecture pre-implementation review + WP-CLEAN-003B execution |
| G1–G7 | Satisfied for this removal (G7 post-removal complete) |

---

## 6. Rollback

```bash
git checkout 0c678749547595b3b9f837a62e747180359cf9f8 -- corpsite-ui/app/directory/_lib/api.client.ts
```

Or revert the WP-CLEAN-003B commit after it is committed.

---

## 7. Lessons learned

1. **Orphan API clients after module extraction** — superseded clients can linger in parent `_lib/` folders; grep for path *and* exported symbol names before deletion.
2. **Preserve siblings explicitly** — same folder contains live `dictionaries.config.ts`; single-file deletion is required.
3. **Lint baseline noise is orthogonal** — pre-existing ESLint errors must not block orphan removal when build + tests pass and removed file is unreferenced.
4. **WP-CLEAN-003B pattern** — one CCR, one file, register sync, deprecation marker update, rollback SHA documented; do not batch with CCR-003.

---

## 8. Next step

**WP-CLEAN-003C** (separate WP): CCR-003 `app/api/directory.ts` — requires CI/build audit per CLEAN-GATE-001; do not batch with CCR-002.

---

*No other implementation changes in WP-CLEAN-003B.*
