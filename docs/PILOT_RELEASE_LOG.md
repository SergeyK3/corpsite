# Corpsite Pilot Release Log

Use one entry for each deployment during the pilot.

---

## Release Entry

- Date: 2026-03-31
- Version / label: `pilot-v0.1`
- Environment: pilot / initial deployment point
- Responsible person: Sergey

### What changed

- backend: improved task filtering by effective org unit in `app/services/tasks_router.py`
- frontend: refresh on tasks and roles pages now resets filters and returns to the default pilot state
- database: no schema change required for this release point
- bot: no changes in this release point

### Why this release was made

- bug fix: task list filtering now accounts for effective unit data coming from task or linked regular task
- pilot support: tagged a stable release point before first pilot deployment
- usability improvement: refresh behavior is now predictable and clears stale filters
- access / security update: no new security change in this release point

### What to verify after deployment

1. Health endpoint works.
2. Login works for a test user.
3. Tasks page opens.
4. One real task flow works.
5. Department access boundaries are correct.
6. Bot flow works if affected.
7. Tasks filter by department works correctly for pilot users.
8. Refresh on `Tasks` and `Roles` resets filters and URL params as expected.

### Rollback note

- rollback needed if: pilot users cannot open tasks, task visibility is incorrect, or refresh/reset behavior breaks normal navigation
- rollback method: redeploy previous backend/frontend version and return to previous git tag or commit
- backup used: database backup required before first live deployment

### Result

- status: prepared and tagged, awaiting pilot deployment
- issues found: none in focused local verification; deployment verification still pending
- follow-up actions: deploy `pilot-v0.1`, run smoke check, and record actual pilot outcome under this entry

---

## Release Entry

- Date: 2026-06-09
- Version / label: `pilot-v0.2-directory-smoke`
- Environment: VPS pilot (46.247.42.47)
- Responsible person: Sergey

### What changed

- backend: `GET /directory/working-contacts` — SQL aligned with VPS `org_units.name` (no `name_ru`)
- database: Alembic `f8c2a91b4e10` — `public.contacts` table + `public.positions.category`
- backend: Alembic chain repair — `a7c4e1f903de` down_revision fixed for `alembic upgrade head`
- frontend: no changes in this release point
- bot: no changes in this release point

### Why this release was made

- bug fix: directory visual smoke failures (`working-contacts`, `contacts`, `positions`) returned HTTP 500
- pilot support: close schema drift between directory API contracts and VPS PostgreSQL
- usability improvement: directory screens load lists without server errors

### What to verify after deployment

1. `GET /directory/working-contacts` → 200, list renders.
2. `GET /directory/contacts` → 200, list renders (may be empty).
3. `GET /directory/positions` → 200, list renders with `category`.
4. Tasks RBAC boundaries still hold for pilot users.
5. Tasks search (`/tasks?q=…`) returns 200.
6. Regular Tasks admin list opens (`/regular-tasks`).

### Rollback note

- rollback needed if: directory routes regress to 500, or `alembic_version` diverges from `f8c2a91b4e10`
- rollback method: redeploy previous git commit; DB rollback from pre-migration dump if schema change must be reverted
- backup used: `/tmp/corpsite-backups/pre_f8c2a91b4e10_20260609_072839.dump` (pg_dump via `corpsite-pg` container)

### Result

- status: **PASS** — final pilot smoke green for RBAC, Search, Regular Tasks, Working Contacts, Contacts, Positions
- issues found: none blocking after commits `d8126d0` (working-contacts) and `28dccbd` (contacts/positions schema)
- follow-up actions: optional UI login smoke with pilot credentials; populate `contacts` seed data if business needs non-empty list

---

## Release Entry

- Date: 2026-06-10
- Version / label: `pilot-v0.3-week1-prep`
- Environment: VPS pilot (46.247.42.47)
- Responsible person: Sergey
- Git HEAD: `17bcdd9` (код без изменений; ops-only на VPS)

### What changed

- **database backup:** `/tmp/corpsite-backups/pre_week1_day0_20260610_152756.dump` (pg_dump `-Fc`, 80 KB)
- **RBAC fixture cleanup:** удалены `RBAC_GAP_LEGACY`, `RBAC_GAP_HISTORICAL`, tasks `10001`/`10002`, связанные reports
- **stale pilot tasks:**
  - task `2` (P1 AMB): `WAITING_APPROVAL` → **DONE** (approve от qm_head, Day-0 prep)
  - task `4` (P2 AMB): `WAITING_REPORT` → **ARCHIVED** (admin, Day-0 prep)
  - tasks `1`, `3` (DONE): **оставлены** как исторический audit trail
- **catch-up live:** `run_id=27`, `run_for_date=2026-06-17`, `org_unit_id=44` → period **2026-06-10..2026-06-16**
  - создано **2** задачи: `10009` (QM_HOSP), `10010` (QM_AMB), status `IN_PROGRESS`
- **env hardening** (`.env`, `corpsite-ui/.env.production`):
  - `APP_ENV=prod`
  - `ENABLE_DIRECTORY_DEBUG=0`
  - `ENABLE_LEGACY_X_USER_ID=0`
  - `NEXT_PUBLIC_APP_ENV=prod`
  - prod-secrets rotated (`AUTH_JWT_SECRET`, `INTERNAL_API_TOKEN`, `BOT_BIND_TOKEN`) — значения только в `.env`, не в git
- **frontend:** `npm run build` после смены `NEXT_PUBLIC_APP_ENV`
- **services:** restart `corpsite-backend`, `corpsite-frontend`, `corpsite-bot`

### Why this release was made

- Подготовка **QM Pilot Week 1 Day-0**: чистый старт без RBAC-fixture шума, актуальная неделя Jun 10–16, prod-флаги.

### What to verify after deployment

1. `GET /health` → 200
2. Frontend → 200
3. `qm_head` / `qm_hosp` / `qm_amb` login (JWT re-login после rotation secrets)
4. `qm_hosp` видит task `10009`, `qm_amb` — task `10010`
5. Tasks `1`, `2`, `3` (DONE), `4` (ARCHIVED) — история сохранена
6. `./venv/bin/python scripts/pilot/qm_notifications_check.py` с `TASK_IDS=10009,10010` — events появятся после первого report
7. `pytest tests/test_tasks_org_scope.py` — PASS

### Rollback note

- **backup:** `/tmp/corpsite-backups/pre_week1_day0_20260610_152756.dump`
- restore: `pg_restore -c -d corpsite < backup.dump` (через docker exec)
- env rollback: вернуть прежние флаги/secrets из backup `.env` (не в git)
- rollback если: pilot users не логинятся, неверная видимость задач, catch-up создал не те задачи

### Result

- status: **PASS (Day-0 prep)** — backup, cleanup, catch-up, env, services active
- issues found:
  - `qm_notifications_check` для tasks `10009/10010` — FAIL ожидаемо (ещё нет events; пройдёт после первого report)
  - visibility fixture tests — SKIPPED (fixture удалён из prod, корректно)
- follow-up actions:
  - UI login smoke для 3 pilot users
  - Day 1: hosp report (`10009`) → amb report (`10010`) → head approve
  - заполнить pilot prep table в `docs/PILOT_QM_ROSTER.md`
