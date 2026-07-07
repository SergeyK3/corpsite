# WP-CLEAN-003C — Architecture Audit: CCR-003 (`app/api/directory.ts`)

| Field | Value |
|------|----------|
| Date | 2026-07-07 |
| Work package | WP-CLEAN-003C |
| CCR | CCR-003 |
| Scope | Architecture investigation only — **no file changes** |
| Auditor | WP-CLEAN-003C execution |

---

## Executive summary

The artifact under review is a **TypeScript client API wrapper** that lives at **`app/api/directory.ts`** (repo root, inside the Python FastAPI package tree). It is **not** at `corpsite-ui/app/api/directory.ts` — that path exists only in the file header comment and was never created.

The file was introduced alongside the employees UI restoration (2026-01-16) but **never imported**. The live runtime client is `corpsite-ui/app/directory/employees/_lib/api.client.ts`, which was created in the **same commit** and has been the authoritative fetch layer ever since.

**Classification:** **Dead**

**Recommendation:** **RECLASSIFY** CCR-003 from Unknown → Dead; schedule deletion in a separate removal WP (WP-CLEAN-003D) after G7 build/test verification with the file absent.

---

## 0. Path clarification (critical)

| Reference | Actual |
|-----------|--------|
| User / CCR shorthand `corpsite-ui/app/api/directory.ts` | **Does not exist** — no `corpsite-ui/app/api/` directory in repo |
| On-disk path | **`app/api/directory.ts`** (sibling to `app/api/admin_router.py`, etc.) |
| File header comment (line 1) | `// corpsite-ui/app/api/directory.ts` — intended location, never applied |
| CCR-003 register path | `app/api/directory.ts` ✓ matches on-disk location |

This audit investigates the on-disk artifact `app/api/directory.ts`. References to `/api/directory/...` in nginx/deploy docs denote the **HTTP same-origin proxy prefix** to FastAPI routes (`/directory/employees`, etc.) — **not** this TypeScript module.

---

## 1. Provenance

### 1.1 Introduction timeline

| Commit | Date | Message | Change to artifact |
|--------|------|---------|-------------------|
| `ee444d9a4a356a9536681b33ac9aee66c02aa7be` | 2026-01-16 16:03 +0500 | `fix(directory): restore employee card routing and normalize employees UI` | **File created** at `app/api/directory.ts` (82 lines). Header: `// app/api/directory.ts` |
| `0b4065bf36989377900c73ae1e4f481ce90f8e35` | 2026-01-16 17:03 +0500 | `feat(directory): employees list + employee card restored; filters normalized; ui fixes` | Header comment changed to `// corpsite-ui/app/api/directory.ts` — **file not moved** |
| `76cc52a9de82ad8b5176b82b46f359b715606fb3` | 2026-01-20 07:03 +0500 | `refactor(directory): unify org units contract and align server API` | Types relaxed; added `getEmployee`, `getOrgTree`, `X-User-Id` dev header — **still zero imports** |

**Author:** SergeyK3 (`git blame`, `git log`)

### 1.2 Feature that created it

The **employees list + employee card restoration** work package (January 2026 directory MVP). Commit `ee444d9` simultaneously added:

- `app/api/directory.ts` ← orphan under review
- `app/directory.py` (backend route expansion)
- Full `corpsite-ui/app/directory/employees/**` module including `_lib/api.client.ts`, `_lib/types.ts`, pages, components

Evidence: `git show ee444d9 --name-only` lists all paths above in one changeset.

### 1.3 Was it ever runtime-authoritative?

**No.**

From introduction day, UI components imported `corpsite-ui/app/directory/employees/_lib/api.client.ts`, not `app/api/directory.ts`.

Evidence:

- Initial `api.client.ts` (commit `ee444d9`) exports `getEmployees`, `getEmployee`, `getDepartments`, `getPositions` — same domain as orphan file.
- Repo-wide grep for import paths (`from '...app/api/directory'`, `@/app/api/directory`, relative variants): **zero matches** (2026-07-07).
- `git log -S "app/api/directory"` across all branches: only commit `ee444d9` (creation) — **no subsequent import commits**.

### 1.4 Partial migration?

**Yes — functionally superseded, physically left behind.**

| Concern | Orphan `app/api/directory.ts` | Live replacement |
|---------|------------------------------|------------------|
| Employee list/detail fetch | `getEmployees`, `getEmployee` | `corpsite-ui/app/directory/employees/_lib/api.client.ts` |
| Departments / positions | `getDepartments`, `getPositions` | same `api.client.ts` |
| Org tree | `getOrgTree` → `/directory/departments/tree` | `corpsite-ui/app/directory/employees/_lib/directory.ts` → `/directory/org-units/tree` (updated contract) |
| Types | inline `EmployeeListItem`, etc. | `corpsite-ui/app/directory/employees/_lib/types.ts` (`EmployeeDTO`, etc.) |
| URL resolution | `NEXT_PUBLIC_API_BASE_URL` + raw path | `resolveApiUrl()` via `@/lib/apiBase` |
| Auth headers | dev `X-User-Id` from env | `apiAuthHeaders()` + `@/lib/api` `buildHeaders()` |

The orphan reflects an **older API contract** (e.g. `/directory/departments/tree`, `department_id` filters). Live code evolved separately.

### 1.5 Accidentally left behind?

**Most likely yes.** Evidence:

1. Created in Python router directory (`app/api/`) alongside `.py` files — atypical for frontend TypeScript.
2. Header comment updated to intended `corpsite-ui/` path in the **next commit** but file never relocated.
3. Parallel `api.client.ts` in corpsite-ui served all UI call sites from day one.
4. No ADR, WP, or migration doc references this file as canonical.

### 1.6 ADRs / work packages

| Document | Relevance |
|----------|-----------|
| ADR-031 (directory personnel contacts) | Defines backend `/directory/*` HTTP contract — **does not reference** `app/api/directory.ts` |
| ADR-045 (personnel HR processes split) | `/directory/staff` navigation — uses live employees client |
| WP-CLEAN-001 §8 (CCR-003) | Register entry; class Unknown pending audit |
| WP-CLEAN-002 | CCR-003 deprecation marker created |
| WP-CLEAN-003A/003B | Orphan removals (CCR-001/002); CCR-003 explicitly deferred to 003C |

No normative ADR cites this file path.

---

## 2. Runtime analysis

### 2.1 Static imports

| Search | Result |
|--------|--------|
| `from '...app/api/directory'` / `@/app/api/directory` / relative import variants | **0 matches** (repo-wide, `.ts/.tsx/.js/.jsx`) |
| Symbol imports (`getEmployees`, `EmployeesQuery`, `EmployeeListItem` from orphan path) | All live usages resolve to `employees/_lib/api.client.ts` or `employees/_lib/types.ts` |

### 2.2 Dynamic imports

| Search | Result |
|--------|--------|
| `import(`, `require(`, `next/dynamic` referencing `app/api/directory` | **0 matches** |
| Vitest `importOriginal` mocks | None target this path |

### 2.3 Route registration

| Layer | Participates? | Evidence |
|-------|---------------|----------|
| **Next.js App Router** | **No** | `corpsite-ui/app/api/` directory **does not exist**. Next.js Route Handlers require `route.ts` under `app/api/` inside the Next project. |
| **FastAPI / Python** | **No** | `app/api/` contains only Python modules (`admin_router.py`, `regular_tasks.py`, …) plus this lone `.ts` file. `grep '\.ts' app/**/*.py`: **0 matches**. |
| **HTTP `/api/directory/*`** | **Unrelated** | Nginx rewrites `/api/directory/employees` → FastAPI `/directory/employees` ([NGINX_SAME_ORIGIN_API_RUNBOOK.md](../ops/NGINX_SAME_ORIGIN_API_RUNBOOK.md)). That is **backend HTTP routing**, not this source file. |

### 2.4 Next.js App Router behaviour

- `corpsite-ui/next.config.ts` pins `turbopack.root` and `outputFileTracingRoot` to **`corpsite-ui/`** project root — repo-root `app/api/directory.ts` is **outside** the Next.js application boundary.
- Comment in `next.config.ts`: *«Никаких rewrites для /directory/* — UI-роуты обрабатывает Next.js»* — confirms UI/API separation; this file is neither.

### 2.5 Build participation

| Build | Includes file? | Evidence |
|-------|------------------|----------|
| **corpsite-ui `npm run build`** | **No** | `corpsite-ui/tsconfig.json` / `tsconfig.app.json` `include` patterns scope to `corpsite-ui/**` only. File is at repo root `app/api/`. |
| **TypeScript project** | **No** | Only `corpsite-ui/tsconfig*.json` exist; no root TS project references `app/api/directory.ts`. |
| **Python / uvicorn** | **No** | Backend loads `.py` modules only; `.ts` is inert on disk. |
| **Deploy scripts** | Copied as repo file, not executed | `scripts/deploy_frontend.sh` builds only `corpsite-ui/`. `scripts/deploy_backend.sh` restarts uvicorn — no TS compilation step. |

**Note:** WP-CLEAN-003B executed `npm run build` successfully (2026-07-07) with unrelated orphan removed; this file was already outside the compile graph. Formal G7 **removal experiment** (delete → build → test) for CCR-003 is **not yet executed** — deferred to removal WP.

### 2.6 Code generation

| Check | Result |
|-------|--------|
| OpenAPI / codegen output referencing `app/api/directory.ts` | **None found** |
| `.next/types` / generated imports | **None** — file outside Next root |

### 2.7 Test references

| Search | Result |
|--------|--------|
| `directory.ts` in `**/*.{test,spec}.{ts,tsx,py}` | **0 matches** for `app/api/directory.ts` |
| `tests/` grep for path | **0 matches** |

(Live `corpsite-ui/app/directory/employees/_lib/directory.ts` is a **different file** — org-tree client — and is unrelated to CCR-003.)

### 2.8 Documentation references

| Document | Reference type |
|----------|----------------|
| [WP-CLEAN-001](./WP-CLEAN-001-personnel-domain-assessment.md) | Inventory / CCR register — **non-normative** |
| [CCR-003](../deprecated/personnel/CCR-003-app-api-directory-ts.md) | Deprecation marker |
| nginx / deploy runbooks | `/api/directory/` **HTTP prefix** only — not this source file |
| ADRs | **No** reference to `app/api/directory.ts` |

### 2.9 IDE-only usage

| Check | Result |
|-------|--------|
| Repo CI workflows (`.github/`) | **None present** in repo |
| External tooling / IDE project refs | **Not verified** — only residual uncertainty (see §5) |

---

## 3. Semantic analysis

### What the file represents

**Misplaced, superseded frontend API client — an obsolete duplicate of early MVP fetch helpers.**

Characteristics:

| Pattern | Applies? |
|---------|----------|
| Obsolete API wrapper | **Yes** — duplicate of `employees/_lib/api.client.ts` with older endpoints/types |
| Unfinished feature | Partially — org-tree helpers added 2026-01-20 but never wired |
| Temporary migration artifact | **Yes** — created during employees UI restoration, canonical client moved to corpsite-ui in same commit |
| Generated artifact | **No** |
| Misplaced source file | **Yes** — TypeScript in Python `app/api/` package; comment admits intended `corpsite-ui/` location |
| Future implementation placeholder | **No evidence** — live replacement is far richer (mutations, user linkage, error mapping) |

### Why it exists

Historical accident during the January 2026 **directory employees restoration**: a standalone fetch module was written at repo-root `app/api/directory.ts` (possibly intended as shared client or early prototype) while the real UI module (`employees/_lib/api.client.ts`) was implemented in parallel. The header comment was corrected to `corpsite-ui/app/api/directory.ts` but the file was **never moved or deleted**. Subsequent refactors (org-units contract, ADR-045 staff split, expanded API client) evolved the corpsite-ui module only.

---

## 4. Ownership

| Role | Owner |
|------|-------|
| **Runtime owner** | **None** — zero importers; not in any build or router graph |
| **Architecture owner** | **Directory / Employees frontend module** (ADR-031 backend contract, ADR-045 personnel navigation). Canonical client: `corpsite-ui/app/directory/employees/_lib/api.client.ts` |
| **Replacement** | `corpsite-ui/app/directory/employees/_lib/api.client.ts` + `_lib/types.ts` (+ `_lib/directory.ts` for org-tree) |
| **Migration blocker** | **None** for runtime behaviour. Procedural: CCR-003 G7 «build after removal» checkbox still open in register |
| **Future destination** | **Delete** in WP-CLEAN-003D (recommended). **Move** to corpsite-ui would recreate a duplicate — not justified. |

---

## 5. Removal simulation

*Assume `app/api/directory.ts` does not exist.*

| Surface | Would anything change? | Confidence | Evidence |
|---------|------------------------|------------|----------|
| **corpsite-ui build** | **No** | High | File outside `corpsite-ui/` TS project and Next root (`next.config.ts`, `tsconfig*.json`) |
| **Next.js routes** | **No** | High | Not a route handler; no `corpsite-ui/app/api/` tree |
| **FastAPI routes / OpenAPI** | **No** | High | Python backend unaffected; HTTP `/directory/*` served by `app/directory.py` et al. |
| **Vitest / pytest** | **No** | High | Zero test imports |
| **TypeScript typecheck (corpsite-ui)** | **No** | High | No cross-project reference |
| **Production runtime (UI + API)** | **No** | High | All live fetch paths use `employees/_lib/api.client.ts` |
| **Deploy scripts** | **No functional change** | High | Backend restart / frontend build unchanged |
| **Documentation** | Inventory rows only | High | CCR-003 / WP-CLEAN-001 would need update on actual removal |
| **External / undocumented tooling** | **Unknown** | Low | No CI in repo; not exhaustively audited |

**Verdict for removal simulation:** No runtime, build, route, test, or TypeScript impact expected. Residual uncertainty is **procedural** (external tooling), not evidence of active use.

Per CLEAN-GATE-001 I1, prior class **Unknown** reflected incomplete audit. This investigation resolves substantive uncertainty; remaining gap is G7 execution in a future removal WP.

---

## 6. Classification

### **Dead**

### Justification

All substantive checks from WP-CLEAN-001 §13 (Dead classification checklist) are **confirmed false**:

| §13 Check | Result |
|-----------|--------|
| Runtime import / include | ✓ None — ever |
| Router registration | ✓ Not registered (Next or FastAPI) |
| Sidebar / nav href | ✓ None |
| Test dependency | ✓ None |
| ADR normative reference | ✓ None |
| OpenAPI exposure (as server) | ✓ N/A — client file, unused |
| Ops script / cron | ✓ None |
| Active migration path | ✓ None — superseded same day |

Additional corroboration:

- Same introduction pattern as CCR-002 (`directory/_lib/api.client.ts`) — confirmed **Dead**, removed in WP-CLEAN-003B.
- Misplaced duplicate with stale API contract (`/directory/departments/tree` vs live `/directory/org-units/tree`).
- Not **Core** (no production use), **Transitional** (no active migration), or **Legacy** (never served production traffic as authoritative client).

**Why not Unknown:** Unknown was appropriate before this audit (I1: *Unknown > Dead* when evidence incomplete). WP-CLEAN-003C completes import/build/router/test analysis. Residual «external tooling» gap does not indicate runtime participation.

---

## 7. Recommendation

### **RECLASSIFY**

Update CCR-003 register status: **Unknown → Dead** (verified).

### Why RECLASSIFY (not DELETE in this WP)

| Option | Rationale |
|--------|-----------|
| KEEP | ❌ Misleading — duplicate in wrong directory suggests false ownership |
| **RECLASSIFY** | ✅ **Selected** — audit completes classification; enables gated removal WP |
| MOVE | ❌ Would duplicate existing `employees/_lib/api.client.ts` |
| ARCHIVE | ❌ `.ts` source must not move to docs per WP-CLEAN program (I5) |
| DELETE | ❌ Out of scope for 003C — requires separate WP-CLEAN-003D with G6 rollback + G7 removal experiment |
| NOT ENOUGH EVIDENCE | ❌ Substantive runtime evidence is complete |

### Follow-on (not part of 003C)

**WP-CLEAN-003D — CCR-003 removal** (proposed):

1. Delete `app/api/directory.ts` only.
2. Run `npm run build`, `npm test`, `npm run lint`, backend pytest smoke.
3. Update CCR-003 → **removed**; sync INDEX + register.
4. Document rollback: `git checkout <pre-removal-sha> -- app/api/directory.ts`

---

## 8. CCR-003 register update (proposed)

| Field | Before | After (post-audit) |
|-------|--------|---------------------|
| Class | Unknown | **Dead** |
| Status | open | **verified** |
| Verification | ✓ grep ☐ build | ✓ grep ✓ audit (003C); ☐ G7 removal build |
| Blocking milestone | CI/build audit | **Clear for removal WP** |
| Target WP | 003 | **003D** (removal) |

---

## 9. Evidence index

| # | Method | Command / source | Date |
|---|--------|------------------|------|
| E1 | Static import grep | `rg "app/api/directory"` — 0 importers | 2026-07-07 |
| E2 | Git history | `git log --follow app/api/directory.ts` | 2026-07-07 |
| E3 | Introduction commit | `git show ee444d9 --stat` | 2026-07-07 |
| E4 | Pickaxe import history | `git log -S "app/api/directory"` — creation only | 2026-07-07 |
| E5 | Next.js scope | `corpsite-ui/next.config.ts`, `tsconfig*.json` | 2026-07-07 |
| E6 | Python backend | `app/api/*.py` listing; no `.ts` imports | 2026-07-07 |
| E7 | Live client | `corpsite-ui/app/directory/employees/_lib/api.client.ts` | 2026-07-07 |
| E8 | Test grep | `rg directory.ts tests/ **/*.test.*` — 0 for CCR-003 path | 2026-07-07 |

---

## 10. Out of scope (confirmed)

- [x] No file removal
- [x] No rename
- [x] No runtime behaviour changes
- [x] No CCR-003 marker edit in this WP (audit doc only; marker update optional follow-up)
- [x] CCR-002 / other CCRs untouched

---

*WP-CLEAN-003C — architecture audit only.*
