# RBAC Visibility — Issue #118 (Closed)

**HEAD:** `6878e3e` — `fix(tasks): harden RBAC visibility parity for #118`  
**Closed:** 2026-06-10  
**Scope:** Task visibility parity between `list_tasks` and `ensure_task_visible_or_404`

---

## Verdict

**Issue #118 is closed — functional gap resolved and hardened on `6878e3e`.**

Tasks visible in `GET /tasks?scope=mine` are reachable via `ensure_task_visible_or_404` on detail and mutating endpoints. Fixture gaps no longer reproduce.

---

## Root cause

`list_tasks` and `ensure_task_visible_or_404` maintained **separate visibility predicates**:

- **`list_tasks`** (`scope=mine`): inline SQL — executor role, any report by user, explicit approver (`WAITING_APPROVAL`), legacy approver via `regular_tasks.target_role_id`.
- **`ensure_task_visible_or_404`** (before fix): relied on `_is_report_author` (latest report only) and a legacy `_can_view` path (no legacy approver, no any-report check, no team scope).

**Symptom:** task visible in `GET /tasks?scope=mine` but `ensure_task_visible_or_404` returned 404 (`Task not found`). `GET /tasks/{id}` was partially masked by router fallbacks (`_user_reported_task`, `_user_is_approver_for_task`); mutating endpoints (`POST /report`, `PATCH`, etc.) had no equivalent fallback.

**Unified Org Filter was not the cause.** `apply_org_scope` only narrows the list query; it does not widen list visibility relative to ensure. Org filter cannot produce “in list, 404 on detail.”

---

## Fix commits

| Commit | Summary |
|--------|---------|
| `433dd5b` | **Functional fix** — `_is_task_visible_to_user` gained `_user_has_any_report_on_task` and `_is_legacy_approver_role`; fixture SQL, verifier script, and regression tests added. |
| `6878e3e` | **P1 hardening** — removed unused `conn=None` / `_can_view` path; explicit approver aligned with list via `WAITING_APPROVAL` guard; GET fallbacks documented as defensive; additional parity tests. |

---

## Fixture cases

Synthetic data: `scripts/pilot/rbac_visibility_gaps_fixture.sql`

| Case | Viewer | Task | List predicate (`scope=mine`) | Ensure predicate |
|------|--------|------|-------------------------------|------------------|
| **Legacy approver** | user_id=5 (QM_COMPLAINT_REG) | task_id=10001 — executor role differs, `WAITING_APPROVAL`, `regular_tasks.target_role_id` matches viewer role | `legacy_approver_visibility` | `_is_legacy_approver_role` |
| **Historical report author** | user_id=3 (qm_hosp) | task_id=10002 — user submitted an older report; latest report is by another user | `report_visibility` (`EXISTS` any report by user) | `_user_has_any_report_on_task` |

Apply fixture:

```bash
docker exec -i corpsite-pg psql -U postgres -d corpsite \
  < scripts/pilot/rbac_visibility_gaps_fixture.sql
```

---

## Smoke results (VPS, 2026-06-10, `6878e3e`)

Deploy: `git pull origin master` → `sudo systemctl restart corpsite-backend`

| Check | Result |
|-------|--------|
| `pytest tests/test_task_visibility_gaps.py -v` | **PASS** — 7/7 |
| `python scripts/pilot/verify_rbac_visibility_gaps.py` | **PASS** — `gap_confirmed: False` for both cases; GET via `ensure` (no fallback) |
| `pytest tests/test_tasks_org_scope.py -v` | **PASS** — 4/4 |

Commands:

```bash
./.venv/bin/pytest tests/test_task_visibility_gaps.py -v
./.venv/bin/python scripts/pilot/verify_rbac_visibility_gaps.py
./.venv/bin/pytest tests/test_tasks_org_scope.py -v
```

---

## Closure decision

| Item | Decision |
|------|----------|
| **#118** | **Closed** — resolved in `433dd5b`, hardened in `6878e3e`, verified on VPS |
| **P2 refactor** | **Future improvement** — not in scope for #118; do not start now |

### Out of scope (future P2)

- Extract shared visibility module (single source of truth for list SQL and ensure predicates).
- Full parity test matrix (mine/team × all predicate paths).
- Remove GET fallbacks after long-term parity is proven in production.
- Align remaining asymmetries (e.g. initiator/created_by / manager scope in list vs ensure).

---

## References

- Fixture: `scripts/pilot/rbac_visibility_gaps_fixture.sql`
- Verifier: `scripts/pilot/verify_rbac_visibility_gaps.py`
- Tests: `tests/test_task_visibility_gaps.py`
- Pilot note: `docs/PILOT_QM_ROSTER.md` — RBAC visibility not reproduced on QM pilot flow
