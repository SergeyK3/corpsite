# VPS Stability — ADR-INFRA-005

Production stability runbook for mmc.004.kz (46.247.42.47).

## Incident summary

| Field | Detail |
|-------|--------|
| **Incident** | 2026-06-20 |
| **Root cause** | Frontend service failed due to **EADDRINUSE on port 3000** (orphan `next-server` after restart; systemd exhausted `StartLimitBurst`). |
| **Impact** | **502** on `/directory/personnel` and `/admin/system` (nginx upstream `:3000` down). |
| **Resolution** | **ADR-INFRA-005** — port guard, deploy scripts, systemd hardening, healthcheck timer. |

Related backend incident (2026-06-16): stale orphan **uvicorn** on `:8000` — same class of failure.

## Запрещено / разрешено

### Запрещено

- **`nohup uvicorn`** (и любой ручной uvicorn вне systemd)
- **`npm run start` вручную** на VPS (и `next start` вне `corpsite-frontend.service`)
- `git pull` + `systemctl restart corpsite-frontend` **без** `npm run build`
- Игнорировать `systemctl status` = **failed** после deploy
- **Cursor Remote + on-VPS `npm run build`** одновременно (WP-INFRA-IO-002) — отключить Cursor перед `deploy_frontend.sh`

### Разрешено

- **`sudo ./scripts/deploy_backend.sh`** — единственный путь restart backend
- **`sudo ./scripts/deploy_frontend.sh`** — build + port guard + restart + smoke (Cursor отключён)
- **`sudo ./scripts/deploy_frontend_artifact.sh`** — установка готового `.next` без сборки на VPS (предпочтительно)

## Root causes (confirmed)

### Frontend — 2026-06-20 06:03–06:04 UTC

1. `systemctl restart corpsite-frontend` during deploy
2. Old `next-server` did not release `:3000` (`Failed to kill control group`)
3. New `npm run start` → **`EADDRINUSE :::3000`**
4. systemd retried 5× (`Restart=always`, `RestartSec=5`)
5. **`StartLimitBurst` exhausted** → unit **`failed`**
6. nginx `/` → `127.0.0.1:3000` → **502** until manual fix

Build was present (`BUILD_ID` OK). **Not** a missing `.next` issue.

### Backend — 2026-06-16 (and similar)

1. Stale **orphan uvicorn** on `127.0.0.1:8000` (manual run / failed stop)
2. systemd backend → **`EADDRINUSE`**
3. Restart loop + frontend cascade (`Requires=backend` at the time)

## Golden rules

| Do | Don't |
|----|-------|
| `sudo ./scripts/deploy_frontend.sh` | `git pull && systemctl restart corpsite-frontend` alone |
| `sudo ./scripts/deploy_backend.sh` | `nohup uvicorn … &` |
| `sudo ss -lptn 'sport = :3000'` before deploy | Manual `npm run start` on VPS |
| `journalctl -u corpsite-frontend -n 50` on failure | Ignore `failed` unit state |

## Correct deploy path

```bash
cd /opt/projects/corpsite/app
git pull

# Backend (migrations if needed first)
.venv/bin/alembic upgrade head   # when schema changed
sudo ./scripts/deploy_backend.sh

# Frontend (always builds)
sudo ./scripts/deploy_frontend.sh

# Frontend (preferred when artifact available — no on-VPS compile)
# sudo ./scripts/deploy_frontend_artifact.sh tmp/frontend-artifacts/corpsite-ui-next-....tar.gz
```

## Install / update systemd units (VPS)

```bash
cd /opt/projects/corpsite/app
sudo cp deploy/systemd/corpsite-backend.service /etc/systemd/system/
sudo cp deploy/systemd/corpsite-frontend.service /etc/systemd/system/
sudo cp deploy/systemd/corpsite-healthcheck.service /etc/systemd/system/
sudo cp deploy/systemd/corpsite-healthcheck.timer /etc/systemd/system/
sudo cp deploy/systemd/corpsite-regular-tasks.service /etc/systemd/system/
sudo cp deploy/systemd/corpsite-regular-tasks.timer /etc/systemd/system/
sudo chmod +x scripts/ops/run_regular_tasks_cron.sh
sudo touch /var/log/corpsite-healthcheck.log
sudo chmod 644 /var/log/corpsite-healthcheck.log
sudo systemctl daemon-reload
sudo systemctl enable corpsite-healthcheck.timer
sudo systemctl start corpsite-healthcheck.timer
sudo systemctl enable corpsite-regular-tasks.timer
sudo systemctl start corpsite-regular-tasks.timer
```

Regular tasks scheduler runbook: `docs/ops/REGULAR_TASK_SCHEDULER_RUNBOOK.md`.

Ensure ops scripts are executable:

```bash
chmod +x scripts/check_frontend_build.sh
chmod +x scripts/deploy_frontend.sh scripts/deploy_backend.sh
chmod +x scripts/ops/ensure_port_free.sh scripts/ops/corpsite_healthcheck.sh
chmod +x scripts/ops/run_regular_tasks_cron.sh scripts/ops/scheduler_post_deploy_smoke.sh
```

## Port guard

`scripts/ops/ensure_port_free.sh`:

- Port free → OK
- Listener in expected service cgroup → stop (cleanup)
- Orphan matching `next-server` / `npm` / `uvicorn` → kill
- Unknown process → **fail** with PID + cmdline

Used in:

- `ExecStartPre` (frontend `:3000`, backend `:8000`)
- `deploy_frontend.sh` / `deploy_backend.sh`
- `corpsite_healthcheck.sh` recovery

## Diagnostics

```bash
systemctl status corpsite-frontend corpsite-backend --no-pager -l
sudo ss -lptn 'sport = :3000'
sudo ss -lptn 'sport = :8000'
ps aux | grep -E 'next-server|npm run start|uvicorn' | grep -v grep

journalctl -u corpsite-frontend --since "1 hour ago" --no-pager
journalctl -u corpsite-backend --since "1 hour ago" --no-pager

./scripts/check_frontend_build.sh
curl -sf http://127.0.0.1:8000/health
curl -I http://127.0.0.1:3000/directory/personnel
curl -I https://mmc.004.kz/directory/personnel
```

Look for: `EADDRINUSE`, `Start request repeated too quickly`, `Failed to kill control group`.

## Recovery procedure

### Frontend 502, unit failed

```bash
cd /opt/projects/corpsite/app
sudo systemctl reset-failed corpsite-frontend
sudo ./scripts/ops/ensure_port_free.sh 3000 \
  --service corpsite-frontend \
  --orphan-pattern next-server \
  --orphan-pattern "npm run start" \
  --orphan-pattern node
sudo ./scripts/deploy_frontend.sh
```

### Backend API down, stale uvicorn

```bash
cd /opt/projects/corpsite/app
sudo ./scripts/deploy_backend.sh
```

### Healthcheck log

```bash
tail -50 /var/log/corpsite-healthcheck.log
systemctl list-timers corpsite-healthcheck.timer
```

## Smoke checklist (after every deploy)

- [ ] `systemctl is-active corpsite-backend corpsite-frontend`
- [ ] `ss -lptn 'sport = :8000'` → uvicorn on `127.0.0.1`
- [ ] `ss -lptn 'sport = :3000'` → next-server
- [ ] `curl -sf http://127.0.0.1:8000/health`
- [ ] `curl -I http://127.0.0.1:3000/directory/personnel` → 200
- [ ] `curl -I https://mmc.004.kz/directory/personnel` → 200
- [ ] `curl -I https://mmc.004.kz/admin/system` → 200 or 302 (auth)

### Post-deploy Scheduler Smoke (automatic)

`sudo ./scripts/deploy_backend.sh` runs **scheduler post-deploy smoke** after a successful `/health` check (unless `CORPSITE_SKIP_SCHEDULER_SMOKE=1`).

Pipeline:

```
Backend restart → Healthcheck → Scheduler smoke → Deploy OK
```

Manual run (same checks):

```bash
cd /opt/projects/corpsite/app
set -a && source .env && set +a
sudo ./scripts/ops/scheduler_post_deploy_smoke.sh
```

Expected results (all must pass for deploy to succeed):

| Check | Expected |
|-------|----------|
| `corpsite-regular-tasks.timer` exists | `systemctl cat` succeeds |
| Timer enabled | `is-enabled` → `enabled` |
| Timer active | `is-active` → `active` (waiting) |
| Next trigger | `systemctl list-timers corpsite-regular-tasks.timer` shows a future LEFT time |
| `corpsite-regular-tasks.service` exists | `systemctl cat` succeeds |
| Audit script | `ops_regular_tasks_scheduler_audit.py --post-deploy-smoke` exit 0 |
| Internal endpoint probe | `POST /internal/regular-tasks/run` with `dry_run=true` → HTTP 200 |
| Scheduler-status routing | `GET /regular-tasks/scheduler-status` → HTTP 401 (not 422) |
| Scheduler-status contract | JSON from DB matches contract (`status`, `checked_at`, …) |

Safe mode guarantees: **no task creation**, **no catch-up**, **no live `/run`**.

Optional: set `CORPSITE_SMOKE_ADMIN_LOGIN` / `CORPSITE_SMOKE_ADMIN_PASSWORD` in `.env` for an additional authenticated HTTP contract check.

Runbook: `docs/ops/REGULAR_TASK_SCHEDULER_RUNBOOK.md`.

## Related

- `docs/deploy/frontend.md` — ADR-INFRA-004 frontend deploy
- `README_DEPLOY.md` — full stack checklist
- `deploy/systemd/*.service` — reference units
