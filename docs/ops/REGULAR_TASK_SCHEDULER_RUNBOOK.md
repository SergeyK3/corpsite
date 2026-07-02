# Regular Tasks Scheduler — Operational Runbook

**Scope:** automatic generation of regular tasks via `POST /internal/regular-tasks/run`.

**Production host:** mmc.004.kz (VPS 46.247.42.47).

**Related ADR:** [ADR-020-regular-tasks-contract-v1.md](../adr/ADR-020-regular-tasks-contract-v1.md)  
**Operations addendum (RTS-1…RTS-4):** [ADR-020-scheduler-operations-addendum.md](../adr/ADR-020-scheduler-operations-addendum.md)

---

## Architecture rules (RTS)

| Rule | Summary |
|------|---------|
| **RTS-1** | Scheduler runs **once per day** at **08:30 Asia/Almaty (UTC+5)** |
| **RTS-2** | Active templates with `schedule_params.time` must use **`time` ≤ 08:30** |
| **RTS-3** | Scheduler **does not backfill** missed periods → use **catch-up** |
| **RTS-4** | **Infrastructure → Business** — timer time is fixed in git, **not** derived from `regular_tasks` |

**Forbidden:** choosing or adjusting timer time from `MAX(schedule_params.time)` in the database.

**Scheduler ≠ catch-up:** `/internal/regular-tasks/run` handles today's due templates; `/internal/regular-tasks/catch-up` recovers missed reporting periods.

After prolonged downtime: **restore timer** (root cause) **+ run catch-up** (consequences).

### Backlog (not implemented)

Backend validation on template create/update: reject `schedule_params.time` later than `REGULAR_TASKS_SCHEDULER_DAILY_RUN_TIME` (default `08:30`). See ADR addendum RTS-2.

---

## How automatic generation works

```
systemd timer (daily 03:30 UTC = 08:30 +05)
  └─ scripts/ops/run_regular_tasks_cron.sh
       └─ POST http://127.0.0.1:8000/internal/regular-tasks/run
            Headers:
              X-Internal-Api-Token: $INTERNAL_API_TOKEN
              X-User-Id: $REGULAR_TASKS_CRON_USER_ID
            Body: {"dry_run": false}
       └─ regular_tasks_service.run_regular_tasks_generation_tx(...)
            └─ INSERT regular_task_runs + regular_task_run_items + tasks
```

Important:

- Browser/nginx prefix **`/api` is not used** — scheduler calls uvicorn directly on `:8000`.
- With valid internal token, backend records `stats.trigger_source = "automatic"`.
- Admin UI manual run uses JWT and records `trigger_source = "manual"` — it does **not** restore scheduler health.
- **Catch-up** is a **separate** endpoint and must not be confused with daily scheduler.

---

## Standard production mechanism

| Component | Path |
|-----------|------|
| Invoke script | `scripts/ops/run_regular_tasks_cron.sh` |
| systemd service | `deploy/systemd/corpsite-regular-tasks.service` |
| systemd timer | `deploy/systemd/corpsite-regular-tasks.timer` |
| **Schedule** | **1× daily, 08:30 Asia/Almaty** — `OnCalendar=*-*-* 03:30:00` (VPS clock UTC) |

Install on VPS:

```bash
cd /opt/projects/corpsite/app
sudo cp deploy/systemd/corpsite-regular-tasks.service /etc/systemd/system/
sudo cp deploy/systemd/corpsite-regular-tasks.timer /etc/systemd/system/
sudo chmod +x scripts/ops/run_regular_tasks_cron.sh
sudo systemctl daemon-reload
sudo systemctl enable --now corpsite-regular-tasks.timer
systemctl list-timers | grep regular-tasks
```

Verify next trigger is ~08:30 local (+05):

```bash
systemctl list-timers corpsite-regular-tasks.timer
```

---

## Template time vs scheduler time

- **`schedule_params.time`** — business time gate on the template's due day (ADR-020).
- **08:30 +05** — fixed infrastructure invoke time (RTS-1).

Templates must satisfy RTS-2. Ops audit before first timer enable:

```sql
SELECT regular_task_id, code, schedule_params->>'time' AS template_time
FROM public.regular_tasks
WHERE COALESCE(is_active, FALSE) = TRUE
  AND archived_at IS NULL
  AND (schedule_params->>'time') IS NOT NULL
  AND (schedule_params->>'time') > '08:30';
```

Empty result = OK for RTS-2.

---

## Required environment variables

Set in repo root `.env` (loaded by backend and cron script). **Do not commit secrets.**

| Variable | Required | Purpose |
|----------|----------|---------|
| `INTERNAL_API_TOKEN` | yes | Auth for internal endpoints (bot, cron) |
| `REGULAR_TASKS_CRON_USER_ID` | yes | Active system admin (`role_id=2`) used as `X-User-Id` |
| `REGULAR_TASKS_SYSTEM_USER_ID` | no (default `1`) | `initiator_user_id` on generated tasks |
| `REGULAR_TASKS_TZ_OFFSET_HOURS` | no (default `5`) | Local TZ for due/period logic (Asia/Almaty) |
| `BACKEND_URL` | no (default `http://127.0.0.1:8000`) | Target for invoke script |

Dev/test only (must stay empty in prod):

- `REGULAR_TASKS_RUN_FOR_DATE`
- `REGULAR_TASKS_FORCE_DUE_ALL`
- `REGULAR_TASKS_IGNORE_TIME_GATE`

Verify presence without printing secrets:

```bash
set -a && source .env && set +a
.venv/bin/python scripts/ops/ops_regular_tasks_scheduler_audit.py
```

---

## Operational audit (read-only)

Run on VPS after any deploy or scheduler incident:

```bash
cd /opt/projects/corpsite/app
set -a && source .env && set +a
.venv/bin/python scripts/ops/ops_regular_tasks_scheduler_audit.py
```

Optional endpoint dry-run (same auth as cron, no task creation):

```bash
.venv/bin/python scripts/ops/ops_regular_tasks_scheduler_audit.py --probe-endpoint
```

JSON output:

```bash
.venv/bin/python scripts/ops/ops_regular_tasks_scheduler_audit.py --json
```

The audit checks:

1. systemd timer / crontab entries
2. env presence (`INTERNAL_API_TOKEN`, cron user)
3. cron user exists and is system admin
4. `regular_task_runs` journal (automatic live runs)
5. computed scheduler-status (overdue, explanation)

---

## Verify scheduler is working

### 1. Admin UI (fastest)

Open `/regular-tasks` → panel **«Автоматический запуск»**.

Healthy state:

- status **«Включён — работает»** (or no overdue within 8-day window)
- no missed periods in summary, or catch-up already executed

Unhealthy state:

- **«Требует внимания»** + overdue badge
- missed Weekly/Monthly periods listed

Data source: `GET /regular-tasks/scheduler-status` (browser: `/api/regular-tasks/scheduler-status`).

### 2. Run journal

`/regular-task-runs` — look for `stats.trigger_source = "automatic"`, `dry_run = false`, **not** catch-up.

SQL on VPS:

```sql
SELECT run_id, started_at, status,
       stats->>'trigger_source' AS trigger_source,
       stats->>'run_kind' AS run_kind
FROM public.regular_task_runs
ORDER BY run_id DESC
LIMIT 20;
```

### 3. systemd timer

```bash
systemctl status corpsite-regular-tasks.timer
systemctl list-timers corpsite-regular-tasks.timer
journalctl -u corpsite-regular-tasks.service -n 50 --no-pager
```

### 4. Manual invoke (same as cron)

Dry-run:

```bash
./scripts/ops/run_regular_tasks_cron.sh --dry-run
```

Live (creates tasks if due today):

```bash
./scripts/ops/run_regular_tasks_cron.sh
```

---

## Safe manual recovery

| Scenario | Action |
|----------|--------|
| Timer stopped, **today's** due templates missing | `./scripts/ops/run_regular_tasks_cron.sh` |
| **Past reporting periods** missing tasks | **Catch-up** — `/admin/regular-tasks/catch-up` |
| Token/user misconfigured | Fix `.env`, re-run audit with `--probe-endpoint` |

Do **not** use catch-up to test daily scheduler — use `--dry-run` on `/run`.

Do **not** expect scheduler to backfill after downtime — always catch-up for missed periods.

---

## Diagnose missing automatic runs

1. **Infrastructure** — `systemctl is-enabled corpsite-regular-tasks.timer` (expect `enabled`)
2. **Environment** — audit script (token/user, not placeholder)
3. **Auth** — `--probe-endpoint` → HTTP 200
4. **Journal** — last `trigger_source=automatic` run
5. **Backend** — `curl -sS http://127.0.0.1:8000/health`

---

## Typical root causes of stopped scheduler

| Cause | Symptom | Fix |
|-------|---------|-----|
| **Timer never installed** | No automatic runs | Enable `corpsite-regular-tasks.timer` |
| **Timer disabled after maintenance** | Gap after VPS work | `systemctl enable --now corpsite-regular-tasks.timer` |
| **`INTERNAL_API_TOKEN` rotated** | HTTP 403 in journal | Update `.env`, probe endpoint |
| **Invalid cron user** | HTTP 403/401 | Set active system admin id |
| **Backend down** | curl/health fails | `sudo ./scripts/deploy_backend.sh` |
| **Only catch-up / manual runs** | No `trigger_source=automatic` | Install timer; scheduler ≠ catch-up |

---

## Post-deploy smoke

```bash
curl -sS http://127.0.0.1:8000/health
systemctl is-active corpsite-regular-tasks.timer || echo "WARN: scheduler timer not active"
.venv/bin/python scripts/ops/ops_regular_tasks_scheduler_audit.py
```

After frontend deploy: scheduler panel on `/regular-tasks`.

---

## Incident: missed periods accumulated

Scheduler restore **does not backfill** (RTS-3).

1. Install/restore timer at **08:30 +05** (RTS-1).
2. Run **catch-up** for missed Weekly/Monthly periods.
3. Confirm panel: **«Пропущенных периодов не обнаружено»**.

---

## Related files

| File | Role |
|------|------|
| `docs/adr/ADR-020-scheduler-operations-addendum.md` | RTS-1…RTS-4 |
| `deploy/systemd/corpsite-regular-tasks.timer` | daily 03:30 UTC |
| `app/services/regular_tasks_router.py` | `/internal/regular-tasks/run` |
| `app/services/regular_task_scheduler_status.py` | scheduler-status API |
| `scripts/ops/run_regular_tasks_cron.sh` | production invoke |
| `scripts/ops/ops_regular_tasks_scheduler_audit.py` | read-only audit |
| `corpsite-ui/.../SchedulerStatusPanel.tsx` | admin diagnostics UI |
