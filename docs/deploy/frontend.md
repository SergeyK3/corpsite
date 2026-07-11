# Frontend deploy — ADR-INFRA-004

Production frontend (`corpsite-frontend`) must **never** start without a valid Next.js production build in `corpsite-ui/.next/`.

## I/O guardrails (WP-INFRA-IO-002)

Production VPS disk is IOPS-limited. **Do not** run on-VPS `npm run build` while **Cursor Remote** is connected.

| Rule | Detail |
|------|--------|
| **Forbidden** | Cursor remote + `npm run build` / `deploy_frontend.sh` concurrently |
| **Guard** | `deploy_frontend.sh` calls `scripts/ops/check_cursor_remote.sh` |
| **Preferred deploy** | Off-box build → `deploy_frontend_artifact.sh` (no compile on VPS) |
| **Config** | `.cursorignore`, `.vscode/settings.json` (`files.watcherExclude`, `files.exclude`) |

Full runbook: [`docs/ops/WP-INFRA-IO-002-VPS-IO-Guardrails.md`](../ops/WP-INFRA-IO-002-VPS-IO-Guardrails.md)

## Standard deploy (VPS, on-box build)

From the repository root on the server:

```bash
git pull
sudo ./scripts/deploy_frontend.sh
```

The script:

1. `cd corpsite-ui`
2. `npm ci`
3. `npm run build`
4. Verifies `.next/BUILD_ID` exists
5. `systemctl restart corpsite-frontend`
6. Health-checks `http://127.0.0.1:3000/` (HTTP 200 or redirect)

**Do not** run `git pull` followed by `systemctl restart corpsite-frontend` alone — that skips the build and causes:

```text
Error: Could not find a production build in the '.next' directory
```

## systemd unit

Reference unit: `deploy/systemd/corpsite-frontend.service`

Install or update on VPS:

```bash
sudo cp deploy/systemd/corpsite-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable corpsite-frontend
```

Requirements:

| Setting | Purpose |
|---------|---------|
| `ExecStartPre=.../check_frontend_build.sh` | Fail fast if `.next/BUILD_ID` is missing |
| `Restart=always` / `RestartSec=5` | Recover from runtime crashes after a valid start |
| `RestartPreventExitStatus=203` | Do **not** loop-restart when the build is missing |
| `StartLimitBurst=5` / `StartLimitIntervalSec=120` (in `[Unit]`) | Cap rapid restart storms |

### Service user (VPS)

The reference unit uses **`User=ubuntu`** and **`Group=ubuntu`** — this matches the current production VPS (mmc.004.kz).

If you prefer a dedicated account (`corpsite`), create it and fix ownership **before** enabling the unit:

```bash
sudo useradd --system --home /opt/projects/corpsite --shell /usr/sbin/nologin corpsite
sudo chown -R corpsite:corpsite /opt/projects/corpsite/app
# then edit User=/Group= in the unit file
```

Without that step, `User=corpsite` fails with **`status=217/USER`**.

Adjust paths if the repo lives outside `/opt/projects/corpsite/app`.

## Manual checks

```bash
# Build marker present
test -f corpsite-ui/.next/BUILD_ID && cat corpsite-ui/.next/BUILD_ID

# Pre-start gate (same as systemd ExecStartPre)
./scripts/check_frontend_build.sh

# Service status + recent logs
sudo systemctl status corpsite-frontend
sudo journalctl -u corpsite-frontend -n 50 --no-pager

# Through nginx (after frontend is up)
curl -sS -o /dev/null -w "%{http_code}\n" https://mmc.004.kz/
curl -sS -o /dev/null -w "%{http_code}\n" https://mmc.004.kz/api/health
```

## Hardening test — missing build must not restart-loop

Simulates a bad deploy (`.next` removed, service restarted without build):

```bash
rm -rf corpsite-ui/.next
sudo systemctl restart corpsite-frontend
sudo systemctl status corpsite-frontend
sudo journalctl -u corpsite-frontend -n 20 --no-pager
```

**Expected:**

- Service is **inactive (failed)** or **not running**
- Journal shows: `production build missing` and `Run: sudo ./scripts/deploy_frontend.sh`
- **No** endless crash/restart cycle (thanks to exit code `203` + `RestartPreventExitStatus=203`)

Restore:

```bash
sudo ./scripts/deploy_frontend.sh
```

## Root `package.json` / `package-lock.json` (workspace audit)

Both files at the **repository root** are **intentional** — they are **not** used for VPS production deploy.

| File | Role |
|------|------|
| Root `package.json` | Local dev orchestration: `npm run dev` starts Postgres + backend + frontend via `concurrently` |
| Root `package-lock.json` | Locks root devDependencies (`concurrently`, `wait-on`) |
| `corpsite-ui/package.json` | Production frontend app |
| `corpsite-ui/package-lock.json` | Production frontend dependencies — **only lockfile used by `deploy_frontend.sh`** |

VPS production always runs `npm ci` / `npm run build` inside **`corpsite-ui/`** only.

Next.js may warn about multiple lockfiles when building from `corpsite-ui/`. This is silenced by pinning the app root in `corpsite-ui/next.config.ts`:

- `turbopack.root` — dev / Turbopack
- `outputFileTracingRoot` — production build / `next start`

Removing the root lockfiles would break `npm run dev` at the repo root unless dev scripts are moved elsewhere.

## Preferred deploy — artifact (off-box build)

Avoids compile I/O on the production VPS:

```bash
# Off-box (laptop / CI)
./scripts/build_frontend_artifact.sh

# Copy tarball to VPS, then:
sudo ./scripts/deploy_frontend_artifact.sh tmp/frontend-artifacts/corpsite-ui-next-....tar.gz
```

If `corpsite-ui/package-lock.json` changed, run `cd corpsite-ui && npm ci` on VPS before artifact install.

Optional CI: `.github/workflows/frontend-artifact.yml` (`workflow_dispatch` or tag `v*-frontend*`).

## Environment

Production browser API base URL is baked at build time. See `docs/ops/NGINX_SAME_ORIGIN_API_RUNBOOK.md`:

```bash
# corpsite-ui/.env.production (on VPS, not committed)
NEXT_PUBLIC_API_BASE_URL=/api
NEXT_PUBLIC_APP_ENV=prod
BACKEND_URL=http://127.0.0.1:8000
```

After changing `NEXT_PUBLIC_*`, run a frontend deploy again (rebuild or new artifact required).

## Related

- `README_DEPLOY.md` — full stack deploy checklist
- `docs/deploy/VPS_STABILITY.md` — ADR-INFRA-005 port guard, recovery, health timer
- `docs/ops/WP-INFRA-IO-002-VPS-IO-Guardrails.md` — disk I/O guardrails, Cursor rule, artifact deploy
- `docs/ops/NGINX_SAME_ORIGIN_API_RUNBOOK.md` — nginx `/api` + UI routing
- `scripts/verify_frontend_phase2f3.sh` — optional bundle content verification after build
