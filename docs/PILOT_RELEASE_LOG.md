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
