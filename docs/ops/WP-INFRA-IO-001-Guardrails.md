# WP-INFRA-IO-001 — Guardrails (Design Only)

**Status:** **Superseded** — implemented in [WP-INFRA-IO-002-VPS-IO-Guardrails.md](./WP-INFRA-IO-002-VPS-IO-Guardrails.md).  
**Companion:** `WP-INFRA-IO-001-Incident-Analysis.md`  
**Goal:** Prevent recurrence of Read IOPS saturation on the production VPS when Cursor remote + Next.js builds share the same disk.

---

## 1. Design principles

1. **Production VPS is a runtime host**, not a CI/build farm or primary IDE disk.  
2. **Heavy read/write workloads must not overlap** with live traffic on the same IOPS-limited volume.  
3. **Cursor remote is allowed for ops/debug**, but must be constrained so watchers/indexers do not amplify build churn.  
4. Prefer **exclude / move / schedule** over buying hardware first; upgrade storage if residual risk remains.

---

## 2. Recommendations ranked by expected impact

| Rank | Recommendation | Expected IOPS impact | Effort | Risk if applied carelessly | Apply now? |
|------|----------------|----------------------|--------|----------------------------|------------|
| 1 | **Stop production `npm run build` / `deploy_frontend.sh` on the live VPS while Cursor remote is connected**; build elsewhere or in maintenance window | **Very High** | Low (process) | Stale deploys if process not followed | **No** (policy only until approved) |
| 2 | **Move Next production builds off-box** (CI artifact or dedicated build host); deploy only `.next` + restart | **Very High** | Medium | Broken artifact promotion | No |
| 3 | Add **`.cursorignore`** + Cursor/VS Code **files.watcherExclude / search.exclude / files.exclude** for `.next`, `node_modules`, `.venv`, `.git`, caches | **High** (reduces watcher/index amplification) | Low | Over-exclude may hide files from search | No |
| 4 | Enforce **single-flight deploys** (no overlapping builds); never wipe `.next` without a successful replacement | **High** | Low | Slower iteration | No |
| 5 | **Disconnect Cursor remote** (or stop `fileWatcher`/window) during on-box builds if on-box builds remain temporarily | **High** | Low | Ops inconvenience | No |
| 6 | Raise VPS **disk IOPS / switch to SSD-class volume** with provider | **High** (capacity) | Medium (cost/ops) | Cost; may mask bad workflow | No |
| 7 | Dedicated **build host** or GitHub Actions runner for `corpsite-ui` | **High** | Medium–High | Pipeline setup | No |
| 8 | Shorter atop / `pidstat -d` during deploys (observability) | None directly; enables proof | Low | Disk for logs | No |
| 9 | Memory headroom (reduce Cursor + build concurrency; avoid `%commit>100%`) | **Medium** | Low–Medium | — | No |
| 10 | PostgreSQL tuning / separate data disk | **Low** for *this* incident class | Medium | Unnecessary churn | No |

---

## 3. Directories to exclude from Cursor indexing / watching

### 3.1 Must exclude (strong recommendation)

These paths are large, generated, or change violently during builds:

| Path | Why |
|------|-----|
| `corpsite-ui/node_modules/` | ~660 MiB / ~24k files; build reads heavily |
| `corpsite-ui/.next/` | Regenerated every production build; caused mass watcher delete storms |
| `.venv/` | ~251 MiB / ~10k files; irrelevant to UI indexing |
| `**/__pycache__/` | Generated |
| `**/.turbo/`, `**/.cache/`, `**/coverage/`, `**/dist/`, `**/build/` (artifacts) | Generated |
| `**/playwright*` browser caches / `/tmp/cursor-sandbox-cache/**` if under workspace | Large binaries |
| `logs/`, `tmp/`, `*.log` | Noise |

### 3.2 Usually exclude from *watchers*, optionally keep for *git* UI

| Path | Guidance |
|------|----------|
| `.git/` | Exclude from **file watchers** and search; git extension still works via git CLI. Do not need full recursive watch. |

### 3.3 Keep indexed (source)

- `corpsite-ui/app/`, `corpsite-ui/lib/`, `app/`, `tests/`, `docs/` (as needed), `scripts/`, `deploy/`, config files.

**Note:** Cursor indexing on this host already reported ~**1213 embeddable files** (source-scale). The danger is less “indexing node_modules” and more **fileWatcher reacting to `.next` churn** during builds.

---

## 4. Proposed ignore / settings content (do not apply yet)

### 4.1 New file: `.cursorignore` (repo root)

```gitignore
# WP-INFRA-IO-001 — proposed (not applied)
**/node_modules/
**/.next/
**/.venv/
**/venv/
**/__pycache__/
**/.turbo/
**/.cache/
**/coverage/
**/dist/
**/build/
**/out/
**/.vercel/
**/playwright-report/
**/test-results/
logs/
tmp/
*.log
*.tsbuildinfo
package-lock.json
```

Optional (if search still too heavy):

```gitignore
.git/
```

### 4.2 Cursor / VS Code user or workspace settings (proposed)

Workspace file example: `corpsite-ui/.vscode/settings.json` **or** multi-root settings at repo root — choose one place to avoid drift.

```json
{
  "files.watcherExclude": {
    "**/.git/objects/**": true,
    "**/.git/subtree-cache/**": true,
    "**/node_modules/**": true,
    "**/.next/**": true,
    "**/.venv/**": true,
    "**/venv/**": true,
    "**/__pycache__/**": true,
    "**/.turbo/**": true,
    "**/.cache/**": true,
    "**/coverage/**": true,
    "**/dist/**": true,
    "**/build/**": true
  },
  "search.exclude": {
    "**/node_modules": true,
    "**/.next": true,
    "**/.venv": true,
    "**/coverage": true,
    "**/.git": true,
    "**/dist": true,
    "**/build": true
  },
  "files.exclude": {
    "**/.next": true,
    "**/.venv": true
  },
  "typescript.tsserver.maxTsServerMemory": 2048
}
```

Notes:

- `files.watcherExclude` is the **highest-value** setting relative to this incident.  
- Cap TS server memory to reduce memory-pressure amplification on a 4 GiB-class VPS.  
- Do **not** rely on `.gitignore` alone for Cursor watchers.

### 4.3 Configuration status (WP-INFRA-IO-002)

| Control | Status |
|---------|--------|
| `.cursorignore` | **Yes** — repo root |
| Workspace `files.watcherExclude` for `.next` | **Yes** — `.vscode/settings.json` |
| `corpsite-ui/.gitignore` ignores `.next` / `node_modules` | **Yes** (git only; not sufficient for Cursor) |

See [WP-INFRA-IO-002-VPS-IO-Guardrails.md](./WP-INFRA-IO-002-VPS-IO-Guardrails.md).

---

## 5. Safe deployment workflow (proposed policy)

### 5.1 Target state (preferred)

```text
Developer laptop or CI
  → npm ci && npm run build (corpsite-ui)
  → pack .next (+ package-lock metadata)
  → copy artifact to VPS
  → atomic switch BUILD_ID / restart corpsite-frontend only
  → no on-VPS compile
```

### 5.2 Interim state (if on-VPS build must continue)

1. Announce maintenance / low-traffic window.  
2. **Disconnect Cursor remote** from the VPS (or close the window) before build.  
3. Ensure only **one** build at a time.  
4. Prefer `npm run build` then restart — avoid deleting `.next` long before the new build finishes (morning failure mode: missing `BUILD_ID`).  
5. After `build OK`, reconnect Cursor if needed.  
6. Never run overlapping `deploy_frontend.sh` invocations.

### 5.3 Hard rules (proposed)

- **Forbidden:** Cursor remote connected **and** `npm run build` / `npm ci` on the same VPS concurrently.  
- **Forbidden:** Leaving `.next` absent on a production host (healthcheck restart loops).  
- **Required:** Deploy log line with start/end timestamps and host load/`sar -d 1 5` snapshot.

---

## 6. Build host / CI justification

| Option | When justified | Comment |
|--------|----------------|---------|
| Build on laptop, scp `.next` | Small team, infrequent deploys | Fastest to adopt |
| GitHub Actions (or similar) CI artifact | Regular deploys, need reproducibility | Best long-term |
| Dedicated small build VM | CI not ready; VPS too weak | Isolates IOPS from prod |
| Keep building on prod VPS | Only with Cursor disconnected + SSD IOPS upgrade | Accept residual risk |

**Recommendation:** Treat **off-box build** as the primary mitigation; storage upgrade as secondary insurance.

---

## 7. Storage tier upgrade

**Evidence:** `QEMU HARDDISK`, `ROTA=1`, await ~180 ms with aqu-sz >100 under ~700–800 read IOPS — this volume is **not suitable** for concurrent Next builds + IDE watchers + production.

| Action | Justification |
|--------|----------------|
| Ask PS.kz for **SSD / higher IOPS** plan and published IOPS limits | Removes artificial ceiling |
| Optionally split **DB data** to separate volume later | Nice-to-have; not proven primary for this incident |

Upgrade alone **without** workflow changes may still allow recurrence if builds + Cursor overlap.

---

## 8. Cursor Server operational guidance (remote Linux)

Observed Cursor processes that touch the filesystem:

1. `fileWatcher` — recursive watches; **primary concern** during `.next` rebuilds.  
2. `extensionHost` — agent, extensions, retrieval.  
3. Indexing & Retrieval — merkle over ~1.2k embeddable files (periodic).  
4. Grep Service — on-demand; can scan many files per agent query.  
5. TypeScript language service — project graph; keep `node_modules` excluded from watch where possible.  

**Do:**

- Keep remote sessions short on production.  
- Prefer SSH + journalctl for pure ops when not editing.  
- Add excludes before large refactors that rewrite `.next`.  

**Don’t:**

- Run `npm ci` under Cursor on production.  
- Open multiple Cursor windows on the same VPS workspace.  

---

## 9. Observability guardrails (design)

Before next risky deploy, capture (manually or scripted):

```bash
# design sketch only — not installed
pidstat -d 1 | tee /tmp/pidstat-disk.txt &
sar -d 1 120 | tee /tmp/sar-disk.txt &
# run build
# stop collectors; attach to deploy ticket
```

Retain atop at **≤60s** interval if disk allows.

---

## 10. Suggested implementation order (when approved)

1. **Process freeze:** no Cursor+build overlap (immediate, zero config).  
2. Add `.cursorignore` + watcher excludes.  
3. Change deploy to **artifact-based** (CI or laptop).  
4. Discuss SSD/IOPS upgrade with PS.kz.  
5. Add deploy-time disk accounting.  

---

## 11. Out of scope / non-recommendations (for this WP)

- Changing nginx/postgres production tuning as the primary fix.  
- Disabling Cursor entirely forever (unnecessary if excludes + off-box build).  
- Unauthenticated or weakened app security changes.  

---

## 12. Acceptance criteria for a future “applied” WP

- [ ] No on-VPS `next build` during Cursor remote sessions.  
- [ ] `.cursorignore` + `files.watcherExclude` cover `.next` and `node_modules`.  
- [ ] Deploy runbook updated.  
- [ ] One controlled build with `pidstat -d` shows acceptable `await` / no aqu-sz collapse.  
- [ ] Frontend never left without `BUILD_ID` after failed build.
