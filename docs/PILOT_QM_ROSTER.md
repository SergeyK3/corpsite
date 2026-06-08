# Corpsite QM Pilot Roster

This document is a practical starting point for the first pilot in the quality management / patient support area.

It is based on the seeded logins already visible in the project.
Use it as an operational checklist, not as a strict org chart.

## Suggested pilot group

Use a small first-wave group:

- 1 controller / head
- 2-3 executors
- 1 backup or complaint-focused user
- 1 admin/support user for troubleshooting

## Suggested accounts from current project data

These logins already appear in the project:

| Purpose | Suggested login | Notes |
|---|---|---|
| Pilot owner / head | `qm_head@corp.local` | Main controller for the first week |
| Executor 1 | `qm_hosp@corp.local` | Hospital quality flow |
| Executor 2 | `qm_amb@corp.local` | Ambulatory quality flow |
| Executor 3 or backup | `qm_complaint_pat@corp.local` | Patient complaint flow |
| Complaint / registry role | `qm_complaint_reg@corp.local` | Registry complaint flow |
| Admin / support | `admin` | Only for support and rollback checks |

`Passwords are not taken from the repository.`  
Set or verify them separately before the pilot.

## Pre-go-live data checks

Before launch on VPS run (via Docker if `psql` is not on the host):

```bash
docker exec -i corpsite-pg psql -U postgres -d corpsite < scripts/pilot/org_structure_bootstrap.sql
docker exec -i corpsite-pg psql -U postgres -d corpsite < scripts/pilot/qm_pilot_bootstrap.sql
```

`org_structure_bootstrap.sql` creates `deps_group`, seeds department groups (1/2/3), and a minimal
`org_units` tree including unit `44` (QM / OВЭиПД). Without it, catch-up and directory org-unit
dropdowns stay empty.

Verify for each QM account:

```sql
SELECT u.login, u.unit_id, r.code
FROM public.users u
JOIN public.roles r ON r.role_id = u.role_id
WHERE lower(u.login) LIKE 'qm_%@corp.local'
ORDER BY u.login;
```

`unit_id` must be NOT NULL for dept RBAC and team tasks.

## Environment (QM pilot)

Use [`deploy/env/.env.qm-pilot.example`](../deploy/env/.env.qm-pilot.example) as template.

Minimum production flags:

- `APP_ENV=prod`
- `NEXT_PUBLIC_APP_ENV=prod`
- `ENABLE_DIRECTORY_DEBUG=0`
- `ENABLE_LEGACY_X_USER_ID=0`
- `SUPERVISOR_ROLE_IDS=<role_id of QM_HEAD>`
- `INTERNAL_API_TOKEN` matches backend and bot
- `DATA_DIR=/var/lib/corpsite`

## Bot bind checklist

For each pilot user who needs Telegram notifications:

1. Log in to web UI.
2. Request bind code (when UI flow is available) or use API `POST /me/tg-bind-code`.
3. In Telegram: `/bind <code>`.
4. Verify: `/whoami` shows `user_id`.
5. Trigger one task event and confirm delivery.

Admin unbind (clears DB binding):

- `/unbind <tg_user_id>` from admin Telegram account listed in `ADMIN_TG_IDS`.

## Minimum first-week rollout

Recommended first-week subset:

1. `qm_head@corp.local`
2. `qm_hosp@corp.local`
3. `qm_amb@corp.local`

Add complaint-focused users only after the base flow is stable.

## What to verify per account

For each selected user verify:

- login works
- the correct role opens
- the user sees the expected task list
- the user does not see unrelated data
- status changes work if that user is supposed to act
- `qm_head` sees team tasks for all `QM_*` expert roles (not only same unit)

## Suggested first live scenario

Use one simple weekly control flow:

1. `qm_head@corp.local` creates or supervises the pilot task set.
2. `qm_hosp@corp.local` receives and updates one task.
3. `qm_amb@corp.local` receives and updates one task.
4. `qm_head@corp.local` checks results and confirms visibility/control.

Do not start the first week with all complaint and support flows at once.

## Pilot preparation table

Copy this section and fill it before launch.

| Login | Real employee | Role confirmed | Unit confirmed | Password checked | Login ok | Tasks visible | Bot bound | Notes |
|---|---|---|---|---|---|---|---|---|
| `qm_head@corp.local` |  |  |  |  |  |  |  |  |
| `qm_hosp@corp.local` |  |  |  |  |  |  |  |  |
| `qm_amb@corp.local` |  |  |  |  |  |  |  |  |
| `qm_complaint_pat@corp.local` |  |  |  |  |  |  |  |  |
| `qm_complaint_reg@corp.local` |  |  |  |  |  |  |  |  |
| `admin` |  |  |  |  |  |  |  |  |

## Go-live rule

Go live only if:

- the head account works
- at least two executor accounts work
- access boundaries look correct
- one full task flow succeeds end-to-end
- smoke check passes (`scripts/smoke_check.sh`)
- database backup exists

If any of these fail, fix them before involving more users.

## VPS checkpoint (2026-06-08)

Stage closed on VPS after restore and end-to-end task flow verification.

### Verified

| Area | Result |
|---|---|
| roles / users / employees | OK |
| task_statuses | OK |
| regular_tasks + catch-up | OK (2 tasks created) |
| RBAC visibility (issue #118) | Not reproduced on QM pilot |
| `qm_hosp` list/get | task 1 only |
| `qm_amb` list/get | task 2 only |
| `POST /report` | OK → `WAITING_APPROVAL`, executor → `QM_HEAD` |
| `POST /approve` (HOSP / task 1) | OK → `DONE` (`report_id=3`, `approved_by=2`) |
| `POST /reject` (AMB / task 2) | OK → `WAITING_REPORT` (`report_id=4`, `approved_by=NULL`) |
| Backend errors after fix | None |

### Fixes applied on VPS

- **`task_event_type` missing** — caused 500 on `POST /report` at `write_task_audit()` cast.
  - Hotfix: `scripts/pilot/task_event_type_bootstrap.sql`
  - Permanent: git `4909d6a` — `alembic upgrade head` → `a7c4e1f903de`

### Known non-issue

- `regular_tasks.assignment_scope = unit`, `tasks.assignment_scope = structural` after catch-up.
  Normalized by `_normalize_assignment_scope()`; not an RBAC bug.

### Regression script

```bash
./venv/bin/python scripts/pilot/qm_task_flow_check.py
```

Requires fresh `WAITING_REPORT` tasks (re-run catch-up for a new period if tasks are already `DONE`).

### Next steps (in order)

1. Notifications and delivery (API → bot / Telegram).
2. Bindings and bot cursor storage.
3. UX copy after logic is stable.
