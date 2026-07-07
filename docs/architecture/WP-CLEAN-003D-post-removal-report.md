# WP-CLEAN-003D — Post-Removal Report (CCR-003)

| Field | Value |
|------|----------|
| Date | 2026-07-07 |
| Scope | Remove `app/api/directory.ts` only |
| CCR | CCR-003 |
| Status | **Complete** |

---

## 1. Evidence collected (pre-removal)

| Check | Result |
|-------|--------|
| Architecture audit | [WP-CLEAN-003C audit](./WP-CLEAN-003C-CCR003-audit.md) — class **Dead**, zero importers |
| Static / dynamic imports | None (repo-wide grep) |
| Next.js / FastAPI route registration | None — misplaced TypeScript in Python `app/api/` tree |
| Build graph | Outside `corpsite-ui/` TypeScript project and Next root |
| Replacement | `corpsite-ui/app/directory/employees/_lib/api.client.ts` + `_lib/types.ts` |
| HTTP `/api/directory/*` (nginx/deploy) | **Unrelated** — same-origin proxy to FastAPI; **not touched** |
| FastAPI routers | **Not touched** |

Pre-removal rollback base: `d1c31cd80d03867f554aed6ee59a5f907db6d716`

---

## 2. Change applied

**Deleted:** `app/api/directory.ts`

**Preserved (explicit):**

- `corpsite-ui/app/directory/employees/_lib/api.client.ts`
- FastAPI routers (`app/directory.py`, `app/api/*.py`, etc.)
- nginx/deploy docs referencing HTTP `/api/directory/...`

**Not touched:** Any other runtime code, CCR-001/002 markers, backend routes, proxy config.

---

## 3. Verification results

| Command | Result |
|---------|--------|
| `npm run build` | **Pass** (exit 0). TypeScript OK. Route table unchanged. |
| `npm test` | **499/499 tests passed**, 75 files, exit 0. Removed file had no test references. |
| `npm run lint` | **Exit 1** — pre-existing baseline errors/warnings (e.g. `dev-login/page.tsx` `react-hooks/purity`, `DictionaryPageClient.tsx` `@typescript-eslint/no-explicit-any`, `contacts/page.tsx` `@next/next/no-html-link-for-pages`). **No lint target referenced removed file.** Failures existed before this removal (same pattern as WP-CLEAN-003A/003B). |

Post-removal grep: zero references to `app/api/directory.ts` outside git history and governance docs.

---

## 4. Runtime impact

**None.** The file was never imported and was outside the frontend compile graph. Live directory API access uses `employees/_lib/api.client.ts`. HTTP `/api/directory/...` proxy behaviour unchanged. No FastAPI, permission, or scheduler behaviour changed.

---

## 5. Governance updates

| Artifact | Update |
|----------|--------|
| CCR-003 register (WP-CLEAN-001 §8) | Status → **removed** |
| [CCR-003 deprecation marker](../deprecated/personnel/CCR-003-app-api-directory-ts.md) | Removed + G7 complete |
| [INDEX.md](../deprecated/personnel/INDEX.md) | CCR-003 moved to Removed section |
| Reviewer | Architecture audit (WP-CLEAN-003C) + WP-CLEAN-003D execution |
| Removal date | 2026-07-07 |
| G1–G7 | Satisfied for this removal (G7 post-removal complete) |

---

## 6. Rollback

```bash
git checkout d1c31cd80d03867f554aed6ee59a5f907db6d716 -- app/api/directory.ts
```

Or revert the WP-CLEAN-003D commit after it is committed.

---

## 7. Lessons learned

1. **Path confusion is a smell** — header comment claimed `corpsite-ui/app/api/directory.ts` but file lived in Python `app/api/`; audit (003C) before delete prevented mistaken class Unknown.
2. **HTTP prefix ≠ source file** — `/api/directory/` in nginx docs is proxy routing, not this orphan module.
3. **Audit-then-delete pattern** — 003C (RECLASSIFY Dead) → 003D (single-file delete) mirrors 003A/003B success.
4. **Lint baseline is orthogonal** — build + 499 tests pass is sufficient G7 bar when removed artifact had zero references.

---

## 8. Next step

**WP-CLEAN-004** — simplification items (CCR-005+, ADR-gated). Orphan removals CCR-001…003 **complete**.

---

*No other implementation changes in WP-CLEAN-003D.*
