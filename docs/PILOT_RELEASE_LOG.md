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
