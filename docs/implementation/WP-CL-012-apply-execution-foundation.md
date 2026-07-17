# WP-CL-012 — Apply Execution Foundation

## Scope

WP-CL-012 introduces a **persistent apply execution journal** and a safe executor boundary for approved `ApplyPlan` objects. It does **not** perform canonical Person/PPR/Employment mutations.

## Components

| Layer | Responsibility |
|-------|----------------|
| `ApplyExecutionService` | Preconditions, idempotency, run/action state machine, dispatch |
| `ApplyActionDispatcher` | Routes `ApplyActionType` to executor implementations |
| Executors (`Skip`, `Deferred*`) | Return `skipped` / `deferred` outcomes only |
| `SqlAlchemyApplyExecutionRepository` | Journal persistence via explicit transition APIs |
| Alembic `z5a6b7c8d9e0f1` | `control_list_apply_runs`, `control_list_apply_actions` |

## State machines (WP-CL-012)

### Apply run

- `pending → running`
- `running → succeeded | partially_succeeded | failed`
- `pending|running → cancelled` (explicit operation only)
- **Forbidden:** any terminal status → `running` or `pending`

### Apply action

- `pending → running`
- `running → succeeded | skipped | deferred | failed`
- **Forbidden:** any terminal status → `running` or `pending`

`attempt_count` is persisted for future recovery workflows. It increments on transition to `running` (initial execution yields `1`). It is **not** used to overwrite terminal execution history in WP-CL-012.

## Retry semantics

WP-CL-012 **does not implement retry execution**.

- Failed run/action journal rows are **immutable**.
- Re-executing the same approved plan fingerprint while a run is `failed` raises `ApplyExecutionRetryRequired`.
- No status reset (`failed → pending → running`) is performed.
- Manual SQL status edits are **not** retry.
- A future WP may add successor runs (`retry_of_apply_run_id`) or a separate action-attempt history table.
- `retry_failed_run()` is **not** part of the public API.

## Idempotency

Persistent idempotency is enforced by:

- `UNIQUE(plan_fingerprint)` on `control_list_apply_runs`
- `UNIQUE(idempotency_key)` on `control_list_apply_actions`
- Stored `plan_snapshot` fingerprint validation on replay

| Existing run status | Behaviour |
|---------------------|-----------|
| `succeeded`, `partially_succeeded` | Return existing result; no new rows; executors not called |
| `pending`, `running` | `ApplyExecutionInProgress`; journal unchanged |
| `failed` | `ApplyExecutionRetryRequired`; journal unchanged |

Conflicts fail closed before executor calls:

- Same idempotency key, different action fingerprint → `ApplyIdempotencyConflict`
- Caller digest / recomputed snapshot mismatch with persisted fingerprint → `ApplyIdempotencyConflict`
- Stored snapshot hash mismatch with stored fingerprint → `ApplyIdempotencyConflict`

## Plan snapshot

Deterministic canonical JSON (sorted keys, UTF-8, compact separators):

- Mapping key order does **not** affect fingerprint
- Action list order **does** affect fingerprint
- Precondition tuple order **does not** affect fingerprint (serialized as list in stable action order)
- Precondition value changes **do** affect fingerprint
- No runtime `datetime.now`, object repr, Python hash, or random UUID in snapshot payload
- Persisted `plan_snapshot` must match computed `plan_fingerprint`

## Action execution matrix (WP-CL-012)

| Action type | Outcome |
|-------------|---------|
| `skip` | `skipped` |
| `create_person` | `deferred` |
| `update_person_contact` | `deferred` |
| `resolve_assignment` | `deferred` |
| `add_education` | `deferred` |
| `add_training` | `deferred` |
| `update_other_ppr_field` | `deferred` |
| `create_external_employment` | `deferred` (not generated from WP-CL-006) |

Rules:

- `deferred` is not `failed`
- All deferred → run `partially_succeeded`
- Only succeeded/skipped → run `succeeded`
- Any failed action → run `failed`; subsequent actions stay `pending`
- Executor layer must not import or call canonical ORM repositories

## Error sanitization

Persisted `error_message` / `result_payload` contain safe codes/messages/summaries only. Exception class names, tracebacks, SQL, connection strings, and raw workbook rows are excluded from journal fields (full traceback remains in application logs).

## Out of scope (WP-CL-012)

- Canonical command integration (none wired)
- HTTP apply API (blocked on persisted review snapshot)
- Generic rollback / compensation
- Retry / successor apply runs
- Mass production apply readiness

## Tests

- `tests/test_wp_cl_012_apply_execution_foundation.py` — service, snapshot, idempotency, state machine, sanitization
- `tests/test_wp_cl_012_apply_execution_schema.py` — DB-gated migration/schema/constraints (requires local PostgreSQL + `alembic upgrade head`)
