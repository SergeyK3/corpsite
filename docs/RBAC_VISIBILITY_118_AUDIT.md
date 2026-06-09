# RBAC Visibility — Issue #118 Audit

**HEAD:** `bd6cbb8` — `feat(directory): unify org filter for positions roles contacts`  
**Date:** 2026-06-09  
**Scope:** Task visibility parity between `list_tasks` and `ensure_task_visible_or_404`

---

## Verdict

**#118 functional gap on `bd6cbb8` is not reproducible.**

Fixture cases pass. `ensure_task_visible_or_404` (with `conn`) now grants visibility for both historical gap scenarios that previously caused list/ensure divergence.

---

## Fixture cases

Synthetic data: `scripts/pilot/rbac_visibility_gaps_fixture.sql`

| Case | Viewer | Task | List predicate (`scope=mine`) | Ensure predicate (fixed) |
|------|--------|------|-------------------------------|--------------------------|
| **Legacy approver** | user_id=5 (QM_COMPLAINT_REG) | task_id=10001 — executor role differs, `WAITING_APPROVAL`, `regular_tasks.target_role_id` matches viewer role | `legacy_approver_visibility` | `_is_legacy_approver_role` |
| **Historical report author** | user_id=3 (qm_hosp) | task_id=10002 — user submitted an older report; latest report is by another user | `report_visibility` (`EXISTS` any report by user) | `_user_has_any_report_on_task` |

Apply fixture:

```bash
docker exec -i corpsite-pg psql -U postgres -d corpsite \
  < scripts/pilot/rbac_visibility_gaps_fixture.sql
```

---

## Verify result

On `bd6cbb8` (VPS, 2026-06-09):

| Check | Result |
|-------|--------|
| `scripts/pilot/verify_rbac_visibility_gaps.py` | **PASS** — `gap_confirmed: False` for both cases |
| `tests/test_task_visibility_gaps.py` | **PASS** — 4/4 |

Commands:

```bash
./.venv/bin/python scripts/pilot/verify_rbac_visibility_gaps.py
./.venv/bin/pytest tests/test_task_visibility_gaps.py -v
```

---

## Root cause (historical)

`list_tasks` and `ensure_task_visible_or_404` maintained **separate visibility predicates**:

- **`list_tasks`** (`scope=mine`): inline SQL — executor role, any report by user, explicit approver (`WAITING_APPROVAL`), legacy approver via `regular_tasks.target_role_id`.
- **`ensure_task_visible_or_404`** (before fix): relied on `_is_report_author` (latest report only) and `_can_view` (no legacy approver, no any-report check).

**Symptom:** task visible in `GET /tasks?scope=mine` but `ensure_task_visible_or_404` returned 404. `GET /tasks/{id}` was partially masked by router fallbacks (`_user_reported_task`, `_user_is_approver_for_task`); mutating endpoints (`POST /report`, `PATCH`, etc.) had no equivalent fallback.

**Fix applied (prior to this audit):** `_is_task_visible_to_user` gained `_user_has_any_report_on_task` and `_is_legacy_approver_role`, aligning ensure with list for the two fixture cases.

---

## Current decision

| Item | Decision |
|------|----------|
| **#118** | Close as **functional resolved** on `bd6cbb8` |
| **Architectural debt** | Track separately: **Task visibility parity / single source of truth** |

Remaining debt (out of #118 scope):

- Visibility rules still live in two places (`tasks_router.py` SQL vs `tasks_service.py` predicates).
- `list_tasks` `scope=mine` and `ensure` are not fully equivalent (e.g. initiator/created_by, explicit approver status guard).
- Router fallbacks on `GET /tasks/{id}` remain as a defensive layer.
- Legacy `_can_view` path (`conn=None`) still exists but is unused by router handlers.

Recommended follow-up (separate task): extract shared visibility module; parity test matrix; remove GET fallbacks after parity is proven.

---

## References

- Fixture: `scripts/pilot/rbac_visibility_gaps_fixture.sql`
- Verifier: `scripts/pilot/verify_rbac_visibility_gaps.py`
- Tests: `tests/test_task_visibility_gaps.py`
- Pilot note: `docs/PILOT_QM_ROSTER.md` — RBAC visibility not reproduced on QM pilot flow
