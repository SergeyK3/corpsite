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

## Suggested first live scenario

Use one simple weekly control flow:

1. `qm_head@corp.local` creates or supervises the pilot task set.
2. `qm_hosp@corp.local` receives and updates one task.
3. `qm_amb@corp.local` receives and updates one task.
4. `qm_head@corp.local` checks results and confirms visibility/control.

Do not start the first week with all complaint and support flows at once.

## Pilot preparation table

Copy this section and fill it before launch.

| Login | Real employee | Role confirmed | Unit confirmed | Password checked | Login ok | Tasks visible | Notes |
|---|---|---|---|---|---|---|---|
| `qm_head@corp.local` |  |  |  |  |  |  |  |
| `qm_hosp@corp.local` |  |  |  |  |  |  |  |
| `qm_amb@corp.local` |  |  |  |  |  |  |  |
| `qm_complaint_pat@corp.local` |  |  |  |  |  |  |  |
| `qm_complaint_reg@corp.local` |  |  |  |  |  |  |  |
| `admin` |  |  |  |  |  |  |  |

## Go-live rule

Go live only if:

- the head account works
- at least two executor accounts work
- access boundaries look correct
- one full task flow succeeds end-to-end

If any of these fail, fix them before involving more users.
