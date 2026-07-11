# WP-INFRA-IO-002 — VPS I/O Guardrails (implemented)

**Status:** Applied on 2026-07-12  
**Related:** [WP-INFRA-IO-001 Incident Analysis](./WP-INFRA-IO-001-Incident-Analysis.md), [WP-INFRA-IO-001 Guardrails (design)](./WP-INFRA-IO-001-Guardrails.md)

## Problem

Production VPS (`mmc.004.kz`) uses a HDD-class volume with low read IOPS. Concurrent **on-VPS `npm run build`** and **Cursor Remote** (file watchers, indexing) saturated disk I/O on 2026-07-11 and left the frontend without `.next/BUILD_ID`.

This work package applies the guardrails designed in WP-INFRA-IO-001.

---

## 1. Applied configuration

### 1.1 `.cursorignore` (repo root)

File: [`.cursorignore`](../../.cursorignore)

Excludes from Cursor indexing and retrieval:

- `node_modules/`, `.next/`, `.venv/`, `__pycache__/`
- build caches (`.turbo/`, `.cache/`, `coverage/`, `dist/`, `build/`)
- logs, tmp, `.git/objects/`

**Action after pull:** Reload Cursor window on VPS (`Developer: Reload Window`) so ignores take effect.

### 1.2 Workspace VS Code / Cursor settings

File: [`.vscode/settings.json`](../../.vscode/settings.json) (tracked in git)

| Setting | Purpose |
|---------|---------|
| `files.watcherExclude` | **Primary mitigation** — stops recursive watches on heavy dirs |
| `search.exclude` | Reduces search/index churn |
| `files.exclude` | Hides `.next`, `.venv`, `node_modules` in explorer |
| `typescript.tsserver.maxTsServerMemory` | Caps TS server RAM on 4 GiB-class VPS |

`.gitignore` allows only `.vscode/settings.json`; other `.vscode/*` stays local.

---

## 2. Hard rule — no Cursor Remote during on-VPS build

**Forbidden:** Cursor remote connected **and** `npm run build` / `npm ci` / `deploy_frontend.sh` on the same VPS at the same time.

### Why

Cursor `fileWatcher` reacts to thousands of `.next` file creates/deletes during a Next.js production build. On HDD this stacks with the build itself and can push `await` to ~180 ms and `%iowait` above 40%.

### Before on-VPS frontend deploy

1. **Close** the Cursor remote window to this VPS (or disconnect SSH Remote).
2. Confirm no cursor-server processes:

   ```bash
   pgrep -af cursor-server || echo "OK: no cursor-server"
   ```

3. Run deploy:

   ```bash
   cd /opt/projects/corpsite/app
   sudo ./scripts/deploy_frontend.sh
   ```

4. Reconnect Cursor after `deploy-frontend complete`.

### Automated guard

`scripts/deploy_frontend.sh` calls `scripts/ops/check_cursor_remote.sh` before `npm ci`. It exits **1** if cursor-server is running.

Emergency override (not for routine use):

```bash
CORPSITE_ALLOW_CURSOR_BUILD=1 sudo ./scripts/deploy_frontend.sh
```

---

## 3. Recommended deploy process

### 3.1 Preferred — off-box build + artifact deploy

Avoids compile I/O on the production VPS entirely.

**On developer laptop or CI:**

```bash
cd /path/to/corpsite/app
./scripts/build_frontend_artifact.sh
# → tmp/frontend-artifacts/corpsite-ui-next-<timestamp>-<git>.tar.gz
```

**Copy artifact to VPS** (example):

```bash
scp tmp/frontend-artifacts/corpsite-ui-next-*.tar.gz ubuntu@mmc.004.kz:/opt/projects/corpsite/app/tmp/
```

**On VPS:**

```bash
cd /opt/projects/corpsite/app
git pull   # source sync; no npm run build required for UI-only change
sudo ./scripts/deploy_frontend_artifact.sh tmp/corpsite-ui-next-....tar.gz
```

When `corpsite-ui/package-lock.json` changed, run `npm ci` on VPS **without** build (deps only), or rebuild artifact after lockfile change:

```bash
cd corpsite-ui && npm ci && cd ..
```

### 3.2 Interim — on-VPS build (when artifact path unavailable)

1. Announce low-traffic window if possible.
2. **Disconnect Cursor** from VPS.
3. Single-flight deploy — never two overlapping `deploy_frontend.sh`.
4. Do **not** delete `.next` before the new build finishes.
5. `deploy_frontend.sh` logs a short `sar -d` snapshot at start.

```bash
cd /opt/projects/corpsite/app
git pull
sudo ./scripts/deploy_frontend.sh
```

### 3.3 Full stack deploy (unchanged order)

See [README_DEPLOY.md](../../README_DEPLOY.md) and [frontend.md](../deploy/frontend.md):

1. DB backup / `.env` check  
2. `git pull`  
3. `alembic upgrade head` (if schema changed)  
4. `sudo ./scripts/deploy_backend.sh`  
5. Frontend: **artifact deploy** (preferred) or `sudo ./scripts/deploy_frontend.sh` (Cursor disconnected)  
6. Smoke checks  

---

## 4. CI / local artifact pipeline

| Script | Role |
|--------|------|
| `scripts/build_frontend_artifact.sh` | `npm ci` + `npm run build` + `.tar.gz` + manifest |
| `scripts/deploy_frontend_artifact.sh` | Atomic `.next` switch + restart + health check |
| `scripts/ops/check_cursor_remote.sh` | Guard for on-VPS compile |

Optional GitHub Actions template: [`.github/workflows/frontend-artifact.yml`](../../.github/workflows/frontend-artifact.yml) — builds artifact on push/tag; upload artifact manually or extend with scp/deploy step.

Artifact output directory: `tmp/frontend-artifacts/` (gitignored).

---

## 5. Cursor operational guidance (production VPS)

**Do:**

- Keep remote sessions short; use SSH + `journalctl` for pure ops.
- Reload window after pulling `.cursorignore` / `.vscode/settings.json`.
- Prefer artifact deploy for UI releases.

**Don't:**

- Run `npm ci` / `npm run build` under Cursor on production.
- Open multiple Cursor windows on the same VPS workspace.
- Leave `.next` absent after a failed build (`check_frontend_build.sh` exits 203).

---

## 6. Storage tier (secondary mitigation)

HDD-class disk (`ROTA=1`) remains a risk even with guardrails. Discuss SSD / higher IOPS plan with PS.kz. Off-box build is the primary mitigation.

---

## 7. Acceptance checklist

- [x] `.cursorignore` at repo root  
- [x] `files.watcherExclude` + `files.exclude` + `search.exclude` in `.vscode/settings.json`  
- [x] Rule documented: no Cursor Remote during on-VPS `npm run build`  
- [x] `check_cursor_remote.sh` integrated into `deploy_frontend.sh`  
- [x] Artifact build/deploy scripts  
- [x] Ops docs updated (`docs/deploy/frontend.md`, `VPS_STABILITY.md`)  
- [ ] One controlled deploy with `sar -d` / `pidstat -d` confirming acceptable `await` (run during next maintenance window)

---

## 8. Related files

| Path | Change |
|------|--------|
| `.cursorignore` | New |
| `.vscode/settings.json` | New |
| `.gitignore` | Track `!.vscode/settings.json` |
| `scripts/deploy_frontend.sh` | Cursor guard + disk snapshot |
| `scripts/build_frontend_artifact.sh` | New |
| `scripts/deploy_frontend_artifact.sh` | New |
| `scripts/ops/check_cursor_remote.sh` | New |
| `docs/deploy/frontend.md` | I/O guardrails + artifact path |
| `docs/deploy/VPS_STABILITY.md` | Forbidden Cursor + build overlap |
