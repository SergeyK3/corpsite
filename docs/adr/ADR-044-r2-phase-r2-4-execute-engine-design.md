# ADR-044 Phase R2.4 — User Linkage Execute Engine (Architecture Design)

## Status

**R2.4 execute engine** — R2.4a schema and R2.4b execute preview service implemented (2026-06-21).

| Phase | Scope | Status |
|-------|-------|--------|
| R2.1 | Validation SQL + dry-run contract | Complete |
| R2.2 | Preview engine + read-only API | Complete |
| R2.3 | Review queue + decisions + audit + UI | Complete |
| **R2.4** | **Execute engine design** | **Approved** |
| **R2.4a** | **Execute journal schema (migration)** | **Implemented** |
| R2.4b | Execute preview service + unit tests | **Implemented** |
| R2.4c | API + execute confirm flow | Not started |
| R2.5 | Manual admin link + V3 validation gate | Planned |

## Related documents

| Document | Role |
|----------|------|
| [ADR-044 Identity Reconciliation](./ADR-044-identity-reconciliation.md) | Ratified R2 scope, §2.2 priority, V3 gates |
| [ADR-044 R2 Discovery](./ADR-044-r2-user-linkage-discovery.md) | Schema inventory, rollback levels, journal extension |
| [ADR-044 R2.2 Preview](./ADR-044-r2-phase-r2-2-preview.md) | Classification engine |
| [ADR-044 R2.3 Review Queue](./ADR-044-r2-phase-r2-3-review-queue.md) | Decision inputs to execute |
| [ADR-044 R2.1 Validation SQL](./ADR-044-phase-r2-validation.sql) | Pre/post execute gates |
| [ADR-044 Phase R1a Blueprint](./ADR-044-phase-r1a-implementation-blueprint.md) | Execute/journal pattern to mirror |
| [OPS Backlog — OPS-007](../roadmap/ops-backlog.md) | Blocked until R2 execute + validation |

---

## 1. Problem statement

Identity chain today:

```text
Person → EmployeeIdentity → Employee          (R1a materialized)
User   → ???              → Employee          (R2 gap: users.employee_id NULL)
```

Operational pipeline:

```text
R2.2 Preview  →  classify unlinked active users
R2.3 Review   →  record APPROVE / REJECT / DEFER (no linkage writes)
R2.4 Execute  →  apply APPROVED links only     ← this design
```

**R2.4 is the first phase allowed to write `users.employee_id`.**  
It must not bypass human review, must not auto-link `AUTO_LINK_SAFE` (policy: bucket empty), and must be auditable and reversible.

---

## 2. Design principles

| Principle | R2.4 policy |
|-----------|-------------|
| Human gate | Execute consumes **latest `APPROVE`** from `user_linkage_review_decisions` only |
| Fresh validation | Every apply re-runs R2.2 preview for the target user |
| No silent drift | Preview mismatch vs approval snapshot → **skip**, not auto-correct |
| Single writer | One authoritative execute path; no parallel ad-hoc UPDATE outside journal |
| Mirror R1a | Run journal + line items + security audit + rollback payload |
| Idempotent | Re-execute must not corrupt state |
| Fail closed | Ambiguity, FK violation, or lock conflict → skip/fail item, not partial guess |

---

## 3. End-to-end architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ Admin / API (personnel_admin)                                           │
│   POST …/user-linkage/execute-preview   (dry_run=true, mandatory first) │
│   POST …/user-linkage/execute           (dry_run=false, confirmed)      │
│   POST …/user-linkage/execute/{user_id} (optional single-user apply)    │
│   GET  …/user-linkage/runs/{run_id}     (run report)                    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ user_linkage_execute_service.py (proposed)                              │
│   build_execute_plan()                                                  │
│     ├── load APPROVED candidates (review + preview merge)               │
│     ├── eligibility filter (§4)                                         │
│     ├── drift check vs approval snapshot (§7)                           │
│     └── preflight gates (R2.1 SQL subset / in-process checks)           │
│   run_user_linkage_execute()                                            │
│     ├── create identity_reconciliation_runs (phase='R2')                │
│     ├── FOR each plan item (serial or bounded parallel — §6):           │
│     │     SELECT users … FOR UPDATE                                     │
│     │     re-validate eligibility + uq_users_employee_id                │
│     │     UPDATE users SET employee_id = :target                        │
│     │     INSERT identity_reconciliation_items                          │
│     │     INSERT security_audit_log (USER_EMPLOYEE_LINKED)              │
│     └── finalize run summary                                            │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
   user_linkage_preview    user_linkage_review   identity_reconciliation_*
   (R2.2, read-only)       (R2.3 decisions)      (R1a journal, extended)
```

**Proposed module split (implementation phase, not in R2.4 design deliverable):**

| Module | Responsibility |
|--------|----------------|
| `user_linkage_preview_service.py` | Unchanged classification |
| `user_linkage_review_service.py` | Read decisions; no execute |
| `user_linkage_execute_service.py` | Plan + apply + journal |
| `identity_reconciliation_service.py` | Shared run/item helpers (extend for R2 columns) |

---

## 4. Execute model

### 4.1. Options considered

| Model | Pros | Cons |
|-------|------|------|
| **Per-user only** | Surgical, easy retry | No HR batch sign-off; noisy audit |
| **Batch only** | Matches R1a; operational runbook | Slow feedback for one fix |
| **Hybrid** | Batch default + single-user escape hatch | Slightly more API surface |

### 4.2. Decision: **Hybrid** (recommended)

| Mode | Use case | Behaviour |
|------|----------|-----------|
| **Batch execute** (primary) | HR-approved cohort after VPS validation | `POST …/execute` with optional `limit`, `user_ids[]`, `strategy`, `match_strategy` filters |
| **Per-user execute** (secondary) | Retry one skipped item after re-approval | `POST …/execute/{user_id}` — same core `apply_one_user()` as batch |
| **Execute preview** (mandatory gate) | Sign-off before writes | `POST …/execute-preview` — identical plan builder, `dry_run=true`, **zero writes** |

**Alignment with R1a:** `run_r1a_execute()` accepts optional `person_id` + `limit` on top of batch apply list. R2.4 should mirror that shape.

**Explicit non-goals for R2.4 v1:**

- No background/cron auto-execute
- No `AUTO_LINK_SAFE` auto batch (preview policy keeps count at 0)
- No enrollment hook writes (ADR §2.3 — enrollment apply unchanged)

---

## 5. Eligibility rules

Execute plan includes a user **only if all** conditions hold at plan-build time **and** are re-checked immediately before UPDATE.

### 5.1. Review decision state (latest per `user_id`)

| Latest decision | Execute |
|-----------------|---------|
| **`APPROVE`** | **Eligible** (subject to preview + DB checks below) |
| `REJECT` | **Skip** — outcome `SKIPPED_DECISION_REJECT` |
| `DEFER` | **Skip** — outcome `SKIPPED_DECISION_DEFER` |
| `PENDING` (no row) | **Skip** — outcome `SKIPPED_NO_APPROVAL` |

Latest decision = `DISTINCT ON (user_id) … ORDER BY created_at DESC` (same as R2.3).

### 5.2. Preview classification (fresh R2.2)

| Classification | Execute when APPROVED? | Notes |
|----------------|------------------------|-------|
| `REVIEW_REQUIRED` | **Yes** | Primary happy path |
| `AMBIGUOUS` | **Yes, with strict drift checks** | R2.3 allows approve; execute must confirm `proposed_employee_id` still matches approval **and** fresh preview |
| `IMPOSSIBLE` | **No** | Even if erroneous APPROVE exists — outcome `SKIPPED_CLASSIFICATION` |
| `EXCLUDED_SERVICE_ACCOUNT` | **No** | Service/admin accounts — outcome `SKIPPED_EXCLUDED` |
| `AUTO_LINK_SAFE` | **No in v1** | Policy: bucket not emitted; if ever emitted, still requires APPROVE in v1 |

### 5.3. User row preconditions

| Check | Fail outcome |
|-------|--------------|
| `users.is_active = TRUE` (or COALESCE TRUE) | `SKIPPED_INACTIVE_USER` |
| `users.employee_id IS NULL` | If already set to **same** target → `NOOP_ALREADY_LINKED`; if **different** → `FAILED_CONFLICT_EXISTING_LINK` |
| User row exists | `FAILED_USER_NOT_FOUND` |

### 5.4. Employee target preconditions

| Check | Fail outcome |
|-------|--------------|
| `proposed_employee_id` not null (from approval snapshot) | `SKIPPED_NO_TARGET` |
| Employee exists | `SKIPPED_MISSING_EMPLOYEE` |
| `operational_status IN ('draft','active','suspended')` | `SKIPPED_INACTIVE_EMPLOYEE` |
| No other active user with same `employee_id` (`uq_users_employee_id`) | `FAILED_EMPLOYEE_ALREADY_LINKED` |

### 5.5. Approval ↔ preview consistency (drift)

At plan time and at apply time:

| Condition | Policy |
|-----------|--------|
| Fresh preview `proposed_employee_id` = approval `proposed_employee_id` | Proceed |
| Fresh preview target differs | **Skip** — `SKIPPED_PREVIEW_DRIFT` — **requires re-review (§7)** |
| Fresh preview classification ∈ `{IMPOSSIBLE, EXCLUDED}` | **Skip** — `SKIPPED_PREVIEW_REGRESSED` |
| Fresh preview classification `AMBIGUOUS` but same single target as approval | Allow (explicit HR override path) |
| Fresh preview classification `AMBIGUOUS` and targets disagree | **Skip** — `SKIPPED_PREVIEW_DRIFT` |

### 5.6. Eligibility summary matrix

```text
EXECUTE_ALLOWED =
  latest_decision = APPROVE
  AND classification NOT IN (IMPOSSIBLE, EXCLUDED_SERVICE_ACCOUNT)
  AND user.employee_id IS NULL
  AND employee operational
  AND uq_users_employee_id clear
  AND preview target matches approval target (strict)
```

---

## 6. Idempotency model

### 6.1. User-level idempotency

| State before apply | Action | Item outcome |
|--------------------|--------|--------------|
| `employee_id IS NULL`, all checks pass | `UPDATE` | `applied` |
| `employee_id = proposed_employee_id` | No write | `noop` / `skipped` (`NOOP_ALREADY_LINKED`) |
| `employee_id ≠ proposed_employee_id` | No write | `failed` (`FAILED_CONFLICT_EXISTING_LINK`) |
| Same APPROVE re-executed after successful link | No write | `noop` |

**Rule:** Idempotency key for apply = `(user_id, proposed_employee_id)` at decision time, validated against live row.

### 6.2. Run-level idempotency

| Mechanism | Purpose |
|-----------|---------|
| `identity_reconciliation_runs.dry_run` | Preview runs never write |
| Item `status` ∈ `{planned, applied, skipped, failed}` | Re-reporting a run does not duplicate applied items |
| Optional: `source_decision_id` on item | Tie apply to specific APPROVE row; skip if that decision already has `applied` item |

**Recommended:** store on each R2 item:

```json
{
  "user_id": 123,
  "decision_id": 456,
  "previous_employee_id": null,
  "proposed_employee_id": 789,
  "match_strategy": "LOGIN_SUFFIX",
  "classification_at_execute": "REVIEW_REQUIRED"
}
```

Re-execute with same `decision_id` already `applied` → item-level **noop** (do not fail run).

### 6.3. API idempotency

| Header / field | Recommendation |
|----------------|----------------|
| `Idempotency-Key` (optional v1.1) | Same key within 24h returns same `run_id` report |
| `confirm_token` from execute-preview | Required on execute POST — prevents double-submit from UI |

---

## 7. Re-review requirements when preview data changed

### 7.1. Drift scenarios

| Scenario | Example | R2.4 behaviour |
|----------|---------|----------------|
| Employee terminated after APPROVE | Login suffix pointed to active employee | Skip; queue shows `PREVIEW_REGRESSED` |
| Another user took employee slot | `uq_users_employee_id` | Fail item; no steal |
| FIO collision emerged | Was 1:1, now ambiguous | Skip unless target unchanged and still in `{REVIEW_REQUIRED, AMBIGUOUS}` with same target |
| Login renamed | Suffix no longer parses | Skip — target mismatch |
| Reviewer approved employee A, preview now suggests B | Data correction | Skip — **mandatory re-approve** |

### 7.2. Strict drift policy (recommended v1)

```text
IF fresh_preview.proposed_employee_id IS DISTINCT FROM approval.proposed_employee_id:
  SKIP (no execute)
  surface in execute report + admin UI as "Stale approval — re-review required"

IF fresh_preview.classification IN (IMPOSSIBLE, EXCLUDED_SERVICE_ACCOUNT):
  SKIP

IF fresh_preview.reason_codes added blockers not present at approval:
  SKIP (optional v1.1 — log WARN only for same target)
```

### 7.3. Re-review workflow (no auto-mutation)

1. Execute report lists skipped drift items with `user_id`, old/new targets.
2. Reviewer opens R2.3 queue → new **APPROVE** (append-only decision row).
3. Per-user or batch execute retries only users with fresh APPROVE.

**Do not** auto-update `user_linkage_review_decisions` rows — append-only audit preserved.

### 7.4. Staleness indicator (UI, future impl)

Show on review queue when `latest APPROVE.proposed_employee_id ≠ fresh preview target`:

```text
decision_state = APPROVE
execute_ready = false
drift_reason = PREVIEW_DRIFT
```

---

## 8. Audit model

Three layers — same pattern as R1a + R2.3.

### 8.1. Run journal (`identity_reconciliation_runs`)

| Field | R2 value |
|-------|----------|
| `phase` | `'R2'` (requires CHECK extension migration in impl phase) |
| `dry_run` | `true` for execute-preview |
| `actor_user_id` | Execute operator |
| `snapshot_id` | **NULL** (R2 does not use HR snapshot) or optional validation snapshot ref |
| `status` | `running` → `completed` / `failed` |
| `summary` | JSONB: `{ selected, applied, skipped, failed, noop, drift_skipped }` |

### 8.2. Line items (`identity_reconciliation_items` — extended)

**Proposed R2 columns** (impl migration):

| Column | Purpose |
|--------|---------|
| `user_id` | Target user (new; R1a used `person_id`) |
| `previous_employee_id` | Before linkage |
| `proposed_employee_id` | Intended target |
| `resolved_employee_id` | Actual after apply (= proposed on success) |
| `source_decision_id` | FK/logical ref to `user_linkage_review_decisions.decision_id` |
| `match_strategy` | Snapshot |
| `outcome` | `LINK_USER_EMPLOYEE` / `NOOP` / `SKIP` |
| `action` | `UPDATE_USERS_EMPLOYEE_ID` / `NOOP` / `SKIP` |
| `rollback_payload` | `{ user_id, previous_employee_id, employee_id, decision_id }` |

R1a items remain person-scoped; R2 items are user-scoped. Same table with nullable `person_id` / `user_id` discriminator, or phase-specific views — **implementation choice**; design requires both dimensions auditable.

### 8.3. Security audit (`security_audit_log`)

Register event type **`USER_EMPLOYEE_LINKED`** (migration + `_ALLOWED_EVENT_TYPES`).

| Field | Content |
|-------|---------|
| `event_type` | `USER_EMPLOYEE_LINKED` |
| `actor_user_id` | Execute operator |
| `target_user_id` | Linked user |
| `metadata` | `{ user_id, employee_id, previous_employee_id, decision_id, run_id, match_strategy, classification }` |

One event per successful apply. Skips do not emit link events.

### 8.4. Review audit (unchanged)

`user_linkage_review_decisions` remains append-only. Execute **reads** APPROVE rows; it does not rewrite them.

Optional future column (out of R2.4 v1): `executed_at` / `execute_run_id` on a separate `user_linkage_execute_outcomes` table to avoid mutating review rows.

---

## 9. Rollback strategy

Aligned with [R2 discovery §6.5](./ADR-044-r2-user-linkage-discovery.md) and R1a L1/L2/L3.

| Level | Scope | Action | Validation |
|-------|-------|--------|------------|
| **L1 — per user** | Single mistaken link | `UPDATE users SET employee_id = NULL WHERE user_id = :id` using item `rollback_payload.previous_employee_id` verification | User unlinked; audit note / compensating event |
| **L2 — per run** | Whole execute batch | Reverse all items where `status='applied'` for `run_id`, in reverse order | Count restored = applied count |
| **L3 — snapshot** | Catastrophic | Restore `users` slice from pre-R2 CSV / `pg_restore` | V3a/V3b SQL gates |

**Rollback service (R2.4b or R2.5):** not required for first execute ship, but journal **must** store rollback payload at apply time.

**Compensating audit:** consider `USER_EMPLOYEE_UNLINKED` event type in rollback impl — design note only.

**Never rollback by deleting review APPROVE rows** — forward-fix via REJECT + L1 unlink.

---

## 10. Concurrency protection

### 10.1. Database constraints (authoritative)

| Constraint | Protection |
|------------|------------|
| `uq_users_employee_id` | At most one active user per employee |
| `fk_users_employee` | Target employee must exist |
| `SELECT … FOR UPDATE` on `users` row | Serialize concurrent execute on same user |

### 10.2. Application-level locks

| Lock | Recommendation |
|------|----------------|
| Per-user row lock | `SELECT user_id, employee_id FROM users WHERE user_id = :id FOR UPDATE` inside apply transaction |
| Per-employee check | Re-query `COUNT(*) FROM users WHERE employee_id = :eid AND user_id <> :id AND is_active` inside same transaction |
| Run mutex (optional) | Advisory lock `pg_advisory_xact_lock(hashtext('r2_execute'))` — one batch at a time per DB |

### 10.3. Concurrent scenarios

| Scenario | Result |
|----------|--------|
| Two execute workers, same `user_id` | Second blocks on `FOR UPDATE`; re-checks; likely noop or skip |
| Execute + manual admin PATCH same user | **Out of scope v1** — manual PATCH is R2.5; until then only execute writes |
| Execute + enrollment apply | Enrollment unchanged; no conflict on `employee_id` |
| Approve (R2.3) during execute | Allowed; execute uses decision snapshot at item start |

**Recommendation:** single-flight batch execute on production (advisory lock) for v1; per-user endpoint uses row lock only.

---

## 11. Safety guarantees

| # | Guarantee | Enforcement |
|---|-----------|-------------|
| G1 | No linkage without APPROVE | Plan builder filters latest decision |
| G2 | No auto-link bypassing review | `AUTO_LINK_SAFE` excluded; no execute path without decision_id |
| G3 | No link on ambiguity unless HR approved that target | Drift check + classification gate |
| G4 | No orphan FK | Pre-check employee exists + operational |
| G5 | No duplicate user per employee | `uq_users_employee_id` + pre-check |
| G6 | No overwrite of existing link | Conflict → fail item, not silent reassignment |
| G7 | Preview re-validated at apply time | `run_user_linkage_preview` per user or incremental classify |
| G8 | Execute preview mandatory | API rejects `dry_run=false` without prior preview token or inline `confirm` payload hash |
| G9 | Full audit trail | Run item + `USER_EMPLOYEE_LINKED` |
| G10 | Reversible | Rollback payload on every apply |
| G11 | VPS gate | R2.1 validation SQL pass documented before first prod execute |
| G12 | Personnel admin only | `require_personnel_admin_api` |
| G13 | Service accounts excluded | Classification gate |
| G14 | Idempotent re-run | NOOP when already linked correctly |

---

## 12. Recommended API contract

Paths follow existing R2.2/R2.3 namespace under `personnel_admin_router`.

### 12.1. Execute preview (dry run)

```http
POST /admin/personnel/identity/user-linkage/execute-preview
Authorization: personnel admin
Content-Type: application/json
```

**Request body:**

```json
{
  "user_ids": [101, 102],
  "limit": 100,
  "strategy": "LOGIN_SUFFIX",
  "classification": "REVIEW_REQUIRED",
  "include_already_linked": false
}
```

All fields optional; default = all eligible APPROVED users matching filters.

**Response:** `UserLinkageExecuteReportResponse`

```json
{
  "phase": "R2",
  "dry_run": true,
  "generated_at": "2026-06-21T12:00:00Z",
  "execute_allowed": true,
  "blocking_gates": [],
  "summary": {
    "eligible": 12,
    "would_apply": 10,
    "would_skip": 2,
    "would_fail": 0,
    "drift_skipped": 1
  },
  "items": [
    {
      "user_id": 101,
      "login": "ivanov_42",
      "proposed_employee_id": 42,
      "employee_name": "Иванов И.И.",
      "decision_id": 9001,
      "decision_at": "2026-06-20T10:00:00Z",
      "classification": "REVIEW_REQUIRED",
      "match_strategy": "LOGIN_SUFFIX",
      "planned_outcome": "apply",
      "skip_reason": null
    }
  ],
  "confirm_token": "sha256:…"
}
```

`execute_allowed=false` when R2.1 blocking gates fail (orphan FK in DB, etc.).

### 12.2. Batch execute

```http
POST /admin/personnel/identity/user-linkage/execute
```

**Request body:**

```json
{
  "dry_run": false,
  "confirm_token": "sha256:…",
  "user_ids": [101],
  "limit": 50,
  "reason": "HR sign-off 2026-06-21"
}
```

**Response:**

```json
{
  "phase": "R2",
  "dry_run": false,
  "run_id": 77,
  "run_status": "completed",
  "summary": { "applied": 10, "skipped": 2, "failed": 0, "noop": 0 },
  "item_results": [ … ]
}
```

### 12.3. Per-user execute

```http
POST /admin/personnel/identity/user-linkage/execute/{user_id}
```

Same body as batch (without `user_ids`); delegates to shared `apply_one_user()`.

Use for retry after re-approval — not a bypass of review.

### 12.4. Run history

```http
GET /admin/personnel/identity/user-linkage/runs?limit=20&offset=0
GET /admin/personnel/identity/user-linkage/runs/{run_id}
```

Mirror R1a run list pattern; filter `phase=R2`.

### 12.5. Unchanged endpoints

| Endpoint | Role |
|----------|------|
| `GET …/preview` | R2.2 classification (read-only) |
| `GET …/review` | R2.3 queue |
| `POST …/review/{user_id}/approve\|reject\|defer` | R2.3 decisions |
| `GET …/review/audit` | R2.3 decision history |

### 12.6. Auth and errors

| HTTP | Condition |
|------|-----------|
| 403 | Non personnel admin |
| 400 | Invalid confirm_token, execute blocked by gates |
| 404 | `user_id` not in eligible set |
| 409 | Run mutex / concurrent execute (optional) |

---

## 13. Pre-execute and post-execute validation

### 13.1. Pre-execute (blocking)

Run [ADR-044-phase-r2-validation.sql](./ADR-044-phase-r2-validation.sql) gates:

| Gate | Blocks execute? |
|------|-----------------|
| V3a orphan `users.employee_id` | **Yes** |
| V3b duplicate user per employee | **Yes** |
| Inactive employee targets in DB | **Yes** (data already corrupt) |

Plus in-process: at least one eligible APPROVED item (else empty run allowed with warning).

### 13.2. Post-execute (R2.5 / R3)

Re-run validation SQL; expect:

- Linked users ⊆ approved execute items
- V3b remains 0
- Review queue APPROVED count decreases only via apply or drift skip

---

## 14. UI sketch (implementation follow-up)

| Surface | Change |
|---------|--------|
| User Linkage Review tab | Replace R2.3 warning with execute panel: Preview → Confirm → Execute |
| Execute report | Applied / skipped / drift tables |
| Drift badge | `APPROVE` + `execute_ready=false` |
| Personnel Lifecycle | Link to R2 runs (optional) |

Localization: [OPS-008](../roadmap/ops-backlog.md).

---

## 15. Implementation phases (after this design)

| Step | Deliverable | Depends on | Status |
|------|-------------|------------|--------|
| R2.4a | Migration: phase CHECK, `operation`, `user_linkage_execute_items`, `USER_EMPLOYEE_LINKED` | This ADR | **Done** — `e4f5a6b7c8d9` |
| R2.4b | `user_linkage_execute_service.py` + unit tests | R2.4a | **Done** |
| R2.4c | API + execute-preview confirm flow | R2.4b | Not started |
| R2.4d | Admin UI execute panel | R2.4c | Not started |
| R2.5 | Manual PATCH link + L1 rollback tool + V3 sign-off | R2.4d | Planned |
| OPS-007 | Telegram audit | R2.5 validation | Blocked |

### 15.1 R2.4a schema (implemented)

**Migration:** `alembic/versions/e4f5a6b7c8d9_adr044_r2_4a_user_linkage_execute_schema.py`

| Object | Change |
|--------|--------|
| `identity_reconciliation_runs` | `phase` CHECK extended to `'R1a' \| 'R2'`; new nullable `operation` with R2 values; `chk_irr_phase_operation` couples phase + operation |
| `identity_reconciliation_runs.actor_user_id` | Documented as operator / `created_by_user_id` (column not renamed — R1a backward compatible) |
| `identity_reconciliation_runs.operation` | Required for `phase='R2'`; must be `USER_LINKAGE_EXECUTE_PREVIEW` or `USER_LINKAGE_EXECUTE` |
| `user_linkage_execute_items` | **New table** — R2 per-user execute line items (`identity_reconciliation_items` unchanged for R1a person rows) |
| `user_linkage_review_decisions` | **Unchanged** — append-only, read-only for execute |
| `users.uq_users_employee_id` | **Not added** — already exists since `c3d8e12a5f01` (partial unique on `employee_id WHERE NOT NULL`) |
| `security_audit_log` | `USER_EMPLOYEE_LINKED` registered in `chk_sal_event_type` |

**Safety:** migration performs DDL only — no `UPDATE users.employee_id`, no changes to review decision rows.

**Tests:** `tests/test_adr044_phase_r2_4a_user_linkage_execute_schema.py`

**Verify:**

```bash
alembic upgrade head
python -m pytest tests/test_adr044_phase_r2_4a_user_linkage_execute_schema.py -v
```

### 15.2 R2.4b Execute Preview Service

**Module:** `app/services/user_linkage_execute_service.py`

**Entry point:**

```python
build_user_linkage_execute_preview(
    *,
    actor_user_id: int,
    limit: int | None = None,
    user_id: int | None = None,
) -> ExecutePreviewResult
```

Tests call `_build_user_linkage_execute_preview(conn, …)` directly inside rolled-back transactions.

#### Implemented behavior

1. Creates an `identity_reconciliation_runs` row with `phase='R2'`, `operation='USER_LINKAGE_EXECUTE_PREVIEW'`, `dry_run=true`, `status='completed'`, `actor_user_id` = operator, and a JSONB `summary`.
2. Loads latest review decision per user (`DISTINCT ON (user_id) … ORDER BY created_at DESC`).
3. Re-runs fresh R2.2 preview via `run_user_linkage_preview`.
4. Evaluates the union of fresh preview candidates and users whose latest decision is `APPROVE` (covers already-linked NOOP/FAIL paths).
5. Applies optional `user_id` and `limit` filters (stable `user_id` ordering).
6. Writes one `user_linkage_execute_items` row per evaluated user with snapshots; **does not** update `users.employee_id` or mutate R2.3 review rows.

#### Action / status mapping (preview only)

| Action | Status | When |
|--------|--------|------|
| `LINK` | `PLANNED` | Latest `APPROVE`, fresh preview target matches approval, classification executable, user unlinked, employee slot free |
| `NOOP_ALREADY_LINKED` | `SKIPPED` | `users.employee_id` already equals approved `proposed_employee_id` |
| `SKIP_NOT_APPROVED` | `SKIPPED` | Latest decision is `REJECT`, `DEFER`, or absent |
| `SKIP_PREVIEW_DRIFT` | `SKIPPED` | Approved `proposed_employee_id` ≠ fresh preview target |
| `SKIP_CLASSIFICATION_REGRESSION` | `SKIPPED` | Fresh classification no longer executable (`REVIEW_REQUIRED` / `AMBIGUOUS` only) |
| `SKIP_EXCLUDED` | `SKIPPED` | Fresh classification is `EXCLUDED_SERVICE_ACCOUNT` or `IMPOSSIBLE` |
| `FAIL_ALREADY_LINKED_DIFFERENT` | `FAILED` | User linked to a different employee than approved |
| `FAIL_EMPLOYEE_CONFLICT` | `FAILED` | Proposed employee already linked to another active user (`uq_users_employee_id`) |

Executable classifications: `REVIEW_REQUIRED`, `AMBIGUOUS`.

#### Snapshots per item

| Field | Preview value |
|-------|---------------|
| `preview_snapshot` | Fresh R2.2 candidate dict (or `{}` if absent) |
| `decision_snapshot` | Latest review decision fields |
| `before_user_snapshot` | Live user row before any apply |
| `after_user_snapshot` | JSON `null` (no apply in preview) |
| `rollback_payload` | JSON `null` (populated only on apply in R2.4c+) |

#### Run summary keys

`total_evaluated`, `planned_link`, `noop_already_linked`, `skipped_not_approved`, `skipped_preview_drift`, `skipped_classification_regression`, `skipped_excluded`, `failed_already_linked_different`, `failed_employee_conflict`.

#### Safety guarantees (R2.4b)

- **No `users.employee_id` updates** — preview persists journal rows only.
- **Review decisions append-only** — execute preview reads decisions; never INSERT/UPDATE/DELETE on `user_linkage_review_decisions`.
- **Fresh preview gate** — every eligible `APPROVE` is re-validated against live R2.2 classification before a `LINK` plan item is emitted.
- **Idempotent re-run** — each call creates a new preview run + item rows; user linkage state is unchanged.

#### Tests

`tests/test_adr044_phase_r2_4b_user_linkage_execute_preview.py`

**Verify:**

```bash
python -m pytest tests/test_adr044_phase_r2_4b_user_linkage_execute_preview.py -v
python -m pytest tests/test_adr044_phase_r2_4a_user_linkage_execute_schema.py -q
python -m pytest tests/test_adr044_phase_r2_3_user_linkage_review.py -q
```

---

## 16. Open questions (for sign-off)

| # | Question | Recommendation |
|---|----------|----------------|
| Q1 | Allow execute on `AMBIGUOUS` + APPROVE when preview still ambiguous but same target? | **Yes** — HR explicitly approved |
| Q2 | Separate `user_linkage_execute_outcomes` vs extend reconciliation items? | **Extend items** for parity with R1a |
| Q3 | Require VPS R2.1 SQL file pass in CI or manual ops only? | **Manual ops gate** for prod; CI uses test DB |
| Q4 | Emit unlink audit event on rollback? | Defer to R2.5 rollback tool |
| Q5 | Batch size limit default? | **50** per run (align R1a `limit` cap) |

---

## 17. Decision log

| Date | Decision |
|------|----------|
| 2026-06-21 | R2.4 execute model = **hybrid** (batch primary, per-user secondary) |
| 2026-06-21 | Eligibility = **latest APPROVE** + fresh preview strict target match |
| 2026-06-21 | No `AUTO_LINK_SAFE` auto execute in v1 |
| 2026-06-21 | Audit = extended `identity_reconciliation_*` + `USER_EMPLOYEE_LINKED` |
| 2026-06-21 | Preview drift → skip + mandatory re-review (no silent apply) |

---

## 18. Non-goals (R2.4 design scope)

- No code
- No migrations
- No endpoints
- No enrollment changes
- No `persons` / `employee_identities` writes
- No R1b match_key work
- No automatic scheduled execute
