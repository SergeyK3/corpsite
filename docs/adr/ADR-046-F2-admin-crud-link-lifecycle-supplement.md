# ADR-046 F2 — Admin CRUD and allowed-position link lifecycle supplement

| Field | Value |
|---|---|
| Status | **Accepted — Stage 5 Closed; Stage 6 Not Started** |
| Date | 2026-08-07 |
| Parent ADR | [ADR-046 — Org-unit allowed positions](./ADR-046-org-unit-allowed-positions.md) |
| Work package | [WP-ADR-046-F2](../work-packages/WP-ADR-046-F2-admin-crud-link-lifecycle.md) |
| Architecture clarification | **Architecture Re-Review: APPROVED — ADR clarification accepted** |
| Stage 5 final review | **Stage 5 Final Re-Review: APPROVED — all remaining findings resolved; Ready for Stage 5 closure** |
| Next stage | **Stage 6 — NOT STARTED; this closure does not authorize commencement** |
| Related | ADR-031, ADR-045, ADR-050, ADR-053, ADR-055 |
| Scope | F2 Admin API / CRUD for `org_unit_allowed_positions`; dependency and global-delete policy |

## 1. Purpose

ADR-046 F1 introduced `public.org_unit_allowed_positions`, active-link reads, the HR pilot seed, and consumers of `scope=allowed`. It intentionally deferred the admin mutation API and UI to F2.

F1 defines both:

- `is_active` as the soft-disable flag for an allowed-position link;
- `position_id → positions(position_id) ON DELETE RESTRICT`.

Without an explicit F2 lifecycle policy, an inactive junction row is hidden from `scope=allowed` but still blocks hard deletion of the global catalog position. The current generic Position dependency detector counts every `RESTRICT` / `NO ACTION` FK row and does not inspect `is_active`.

This supplement closes that lifecycle gap. It does not change the distinction between the global position catalog, allowed positions, used positions, and Employment established by ADR-046.

## 2. Decision

### 2.1. Link lifecycle

The identity of an allowed-position link is the unique pair:

```text
(org_unit_id, position_id)
```

The following rules are normative:

1. **Add to allowed** creates the pair when it has never existed.
2. **Re-add** of an inactive pair reactivates the same row by setting `is_active = TRUE`.
3. Re-add must preserve `org_unit_allowed_position_id`. `sort_order` follows the three-state input semantics defined in §3.1.
4. **Remove from allowed** soft-disables only the selected pair by setting `is_active = FALSE`.
5. Remove must not delete or modify the referenced row in `public.positions`.
6. Remove must not change links for any other org unit.
7. Active links are visible to `scope=allowed`; inactive links are not.

### 2.2. Global Position deletion

For hard deletion of a global `public.positions` row:

1. Active `org_unit_allowed_positions` rows are domain blockers.
2. Inactive `org_unit_allowed_positions` rows are not domain blockers.
3. The dependencies endpoint, `delete_status=blocked|deletable` filters, and deletion preflight count only active allowed-position links.
4. Immediately before deleting the Position, all of its inactive allowed-position links are physically deleted in the same database transaction.
5. Every other actual FK dependency retains its existing blocking semantics.
6. If another dependency is found, an active allowed-position link appears, or any database error occurs, the whole transaction rolls back, including physical cleanup of inactive links.
7. `ON DELETE RESTRICT` remains the final database integrity guard. F2 does not change this FK to `CASCADE`.

This policy preserves soft-disable and same-row reactivation throughout the Position lifetime while avoiding an inactive technical row making the catalog entry permanently undeletable.

### 2.3. Authorization

In F2, allowed-position management is restricted to the canonical system administrator:

```text
role_id = 2
```

Requirements:

- every mutation endpoint must perform the backend `_is_system_admin(user)` check;
- frontend visibility is defense-in-depth only and must use the matching system-admin gate;
- directory privileged allowlists, personnel visibility, personnel-admin capability, and org scope do not grant mutation authority in F2;
- read authorization for existing Position list endpoints remains unchanged.

## 3. API contract

F2 should expose the allowed link as a nested resource:

```text
PUT    /directory/org-units/{org_unit_id}/allowed-positions/{position_id}
DELETE /directory/org-units/{org_unit_id}/allowed-positions/{position_id}
```

`PUT` is selected for create/reactivate because the client supplies the complete stable resource identity. `DELETE` has domain soft-disable semantics; it does not physically delete the junction row.

### 3.1. Add or reactivate

Optional request body:

```json
{
  "sort_order": 10
}
```

`sort_order` has three distinct request states:

| Request state | Effective value |
|---|---|
| Field omitted | Preserve the current value for an existing pair; use `NULL` for a newly created pair |
| `{sort_order: null}` | Set `sort_order = NULL` |
| `{sort_order: <integer>}` | Set the supplied integer value |

Responses:

| Condition | Status | Transition | Semantics |
|---|---:|---|---|
| Pair created | `201` | `created` | New active link returned |
| Inactive pair reactivated | `200` | `reactivated` | Same link id returned, `is_active=true` |
| Active pair, effective `sort_order` changed | `200` | `updated` | Existing link updated and returned |
| Active pair, effective `sort_order` unchanged | `200` | `noop` | Idempotent no-op; no duplicate row or audit event |
| Org unit does not exist | `404` | — | `ORG_UNIT_NOT_FOUND` |
| Position does not exist | `404` | — | `POSITION_NOT_FOUND` |
| Parent disappeared while waiting for a concurrent delete | `404` | — | Same missing-parent contract after lock acquisition |
| Request conflicts with a separately approved org-unit lifecycle invariant | `409` | — | Stable domain error code; F2 must not invent such a rule implicitly |

Repeated identical `PUT` requests converge on one active pair. The service returns a structured mutation result:

```text
link
transition = created | reactivated | updated | noop
previous_state
current_state
```

`transition` is determined by the service while the transaction and locks are still active. The route must not reread the link or reconstruct the transition after commit. `created` maps to HTTP `201`; `reactivated`, `updated`, and `noop` map to HTTP `200`. Audit selection is also derived exclusively from this transition. A no-op retry does not create an audit event or advance `updated_at`.

### 3.2. Deactivate

Responses:

| Condition | Status | Semantics |
|---|---:|---|
| Active pair soft-disabled | `200` | Updated link state returned |
| Pair already inactive | `200` | Idempotent success; existing inactive state returned |
| Pair has never existed | `404` | `ALLOWED_POSITION_LINK_NOT_FOUND` |
| Org unit does not exist | `404` | `ORG_UNIT_NOT_FOUND` |
| Position does not exist | `404` | `POSITION_NOT_FOUND` |

The distinction between “already inactive” and “never existed” is intentional: a successful request can be retried safely, while a wrong org-unit/position pair remains observable as a caller error. A no-op retry must not write another deactivation audit event.

For both mutation endpoints, parent lookup order is Position first and org unit second. Consequently, when both parents are absent, `404 POSITION_NOT_FOUND` has priority.

### 3.3. Global delete conflicts

The existing global Position delete contract remains:

| Condition | Status | Semantics |
|---|---:|---|
| Active allowed links or any other blocker | `409` | `POSITION_HAS_DEPENDENCIES` with current blocking counts |
| Position absent | `404` | `POSITION_NOT_FOUND` |
| No blockers after transactional inactive-link cleanup | `200` | Position deleted |
| Defensive late-FK branch on Position DELETE | `409` | Controlled dependency response with `race_detected=true`; this field identifies the accepted defensive branch, not a proven reproducible race in the current schema |

Inactive allowed links must not appear in the dependency response or contribute to `total_dependencies`.

### 3.4. Concurrent HTTP response matrix

The following outcomes are normative after lock waiting and state revalidation:

| First linearized operation | Waiting operation | Required outcome |
|---|---|---|
| Successful global Position delete | Add, reactivate, or deactivate | `404 POSITION_NOT_FOUND`; no link success may be reported |
| Add or reactivate | Global Position delete | Link mutation succeeds (`201` or `200`), then delete returns `409 POSITION_HAS_DEPENDENCIES` |
| Deactivate, with no other blockers | Global Position delete | Deactivate returns `200`; delete may return `200` and removes the inactive link transactionally |
| Global Position delete | Reactivate | Delete returns `200`; reactivate returns `404 POSITION_NOT_FOUND`; the link is absent |
| Child FK INSERT/UPDATE is established before the Position lock | Global Position delete | Delete waits when required, then the real dependency check sees the committed blocker and returns ordinary `409 POSITION_HAS_DEPENDENCIES` |
| Child FK INSERT/UPDATE starts after the Position lock and a true empty dependency check | Global Position delete | Child statement waits; delete may commit `200`, after which the child statement receives PostgreSQL `23503` and cannot create the dependency |

When both parents are absent for a waiting link mutation, the response remains `404 POSITION_NOT_FOUND`.

## 4. Transaction and lock protocol

### 4.1. Global ordering

Every F2 mutation that touches an allowed-position pair must acquire locks in the following order:

```text
1. public.positions
2. public.org_units
3. public.org_unit_allowed_positions
4. audit row append
```

Global Position deletion does not need an org-unit lock, but it must keep the shared prefix:

```text
public.positions → org_unit_allowed_positions rows → remaining dependency checks
```

For future bulk operations, parent ids and link rows must be locked in ascending primary-key order. No code path may lock a link first and then its Position parent.

### 4.2. Add/reactivate transaction

Normative sequence:

1. Begin transaction.
2. Select the Position row `FOR UPDATE`; return `404 POSITION_NOT_FOUND` if absent.
3. Select the org-unit row `FOR UPDATE`; return `404 ORG_UNIT_NOT_FOUND` if absent.
4. Select the pair in `org_unit_allowed_positions` `FOR UPDATE` when present.
5. Resolve the effective `sort_order` from the three request states in §3.1. Omission preserves an existing value and resolves to `NULL` for a new row; explicit `null` resolves to `NULL`; an integer resolves to that integer.
6. If the pair is active and the effective `sort_order` is unchanged, construct the structured result with `transition=noop`, identical `previous_state` and `current_state`, append no audit event, commit, and return HTTP `200`.
7. If the pair is active and the effective `sort_order` changed, update `sort_order` and `updated_at`, append `ORG_UNIT_ALLOWED_POSITION_UPDATED` with the previous and new state and explicit previous/new `sort_order`, require a non-null `audit_id`, construct `transition=updated`, commit, and return HTTP `200`.
8. If the pair is inactive, update that same row to `is_active=TRUE`, apply the effective `sort_order`, and update `updated_at`; append `ORG_UNIT_ALLOWED_POSITION_REACTIVATED`, require a non-null `audit_id`, construct `transition=reactivated`, commit, and return HTTP `200`.
9. If the pair is absent, insert one active row with the effective `sort_order`; append `ORG_UNIT_ALLOWED_POSITION_CREATED`, require a non-null `audit_id`, construct `transition=created`, commit, and return HTTP `201`.
10. For every non-noop transition, any missing audit storage, `None` audit result, null `audit_id`, or audit SQL error aborts and rolls back the transaction.

The service must use a database-native conflict-safe write (`INSERT ... ON CONFLICT ... DO UPDATE`) or an equivalently safe locked implementation. A plain unlocked `SELECT` followed by `INSERT` is not sufficient.

`upsert_allowed_position_link()` must return the structured result defined in §3.1. It computes `transition`, `previous_state`, and `current_state` before commit while holding the locks. The route uses that result directly to select HTTP status and must not perform a post-commit state read or infer transition from request data.

### 4.3. Deactivate transaction

Normative sequence:

1. Begin transaction.
2. Select the Position row `FOR UPDATE`; return `404 POSITION_NOT_FOUND` if absent.
3. Select the org-unit row `FOR UPDATE`; return `404 ORG_UNIT_NOT_FOUND` if absent.
4. Select the pair `FOR UPDATE`; return `404 ALLOWED_POSITION_LINK_NOT_FOUND` if absent.
5. If already inactive, append no audit event, commit without changing `updated_at`, and return `200` as an idempotent no-op.
6. Update only that row: `is_active=FALSE`, `updated_at=now()`.
7. Append `ORG_UNIT_ALLOWED_POSITION_DEACTIVATED` with previous and new state in the same transaction and require a non-null `audit_id`.
8. If the audit storage is missing, the writer returns `None`, `audit_id` is null, or audit SQL fails, roll back the link update.
9. Commit and return the inactive link state with HTTP `200`.

No employee, assignment, Position, other org-unit link, or unrelated dependency is changed.

### 4.4. Global Position delete transaction

Normative sequence:

1. Begin transaction.
2. Select the Position row `FOR UPDATE`; return `404 POSITION_NOT_FOUND` if absent.
3. Lock all `org_unit_allowed_positions` rows for that Position `FOR UPDATE`, ordered by `org_unit_allowed_position_id`.
4. If any locked row is active, build the dependency summary using the F2 policy and return `409 POSITION_HAS_DEPENDENCIES`. The transaction rolls back.
5. Physically delete the locked inactive allowed-position rows.
6. Run the dependency detector for all actual blocking Position FKs using the F2 special policy described in §5.
7. If any blocker remains, return `409 POSITION_HAS_DEPENDENCIES`. The transaction rolls back, restoring the inactive rows removed in step 5.
8. Delete the Position row.
9. Commit.
10. If the direct Position `DELETE` itself raises a PostgreSQL FK `IntegrityError` that satisfies the defensive classifier contract in §6.2, roll back, refresh the dependency assessment, and return the controlled `409` response with `race_detected=true`.

Cleanup is never committed independently of Position deletion.

The 2026-08-07 PostgreSQL lock experiment established the reachability boundary for the current schema and this lock order:

- global delete acquires `SELECT public.positions ... FOR UPDATE` before junction locking, cleanup, dependency evaluation, and Position deletion;
- every current inbound FK to `public.positions` is non-deferrable;
- a child INSERT/UPDATE performs or waits for PostgreSQL's FK parent-row `KEY SHARE` protection;
- if the child write starts before the Position lock, global delete waits as necessary and the committed dependency is visible to the real dependency check;
- if the child write starts after the Position lock and a true empty dependency check, the child waits for the delete transaction and receives `23503` on its own statement after successful Position deletion.

Consequently, with the current schema and required Position lock, a concurrent FK INSERT/UPDATE cannot produce `23503` directly on production `DELETE FROM public.positions` after a true empty in-transaction dependency check. This is a scoped reachability result, not a claim that PostgreSQL can never raise `23503` on a Position DELETE under a future schema, trigger, deferrability rule, or other exceptional condition.

## 5. Dependency detector policy

The detector must continue to discover actual PostgreSQL FKs with `NO ACTION` or `RESTRICT`. F2 must not remove `org_unit_allowed_positions.position_id` from FK discovery and must not add a broad `is_active` convention to arbitrary tables.

Introduce an explicit per-dependency policy whose lookup identity contains, at minimum:

```text
(child_schema, child_table, child_column)
= (public, org_unit_allowed_positions, position_id)
```

Where FK discovery exposes it, `constraint_name` must also be included in or validated by the lookup. The expected current constraint is `org_unit_allowed_positions_position_id_fkey`. A stable public response key such as `org_unit_allowed_positions.position_id` may remain schema-less for API compatibility; it must not be reused as the internal policy identity.

Conceptual contract:

```text
default blocking predicate for every discovered FK identity: TRUE
(public, org_unit_allowed_positions, position_id) predicate: dep.is_active = TRUE
```

The predicate must be applied consistently in:

- `check_position_dependencies()`;
- `check_positions_dependencies()`;
- `build_position_blocked_exists_sql()`;
- dependencies endpoint output;
- `delete_status=blocked|deletable` list filtering;
- the in-transaction global-delete preflight.

Safety requirements:

1. A missing or unknown schema/table/column/constraint combination means **all rows block**, preserving the secure default `TRUE`.
2. Only the exact `public.org_unit_allowed_positions.position_id` FK receives the active-row predicate.
3. An identically named table in any other schema does not receive the exception and remains fully blocking.
4. A renamed, replaced, or otherwise unknown FK remains blocking until explicitly reviewed.
5. The final database FK check remains authoritative.
6. Tests must compare discovered PostgreSQL blocking FKs with detector coverage and separately assert the exact schema-qualified special predicate and the secure default.

This design narrows one known junction dependency without weakening any other FK.

## 6. Concurrency and race protection

The current `upsert_allowed_position_link()` is sequentially idempotent but not concurrency-safe because it performs an unlocked read followed by insert/update. F2 must replace that behavior while preserving its public purpose.

Required guarantees:

- two concurrent adds cannot create duplicates or expose a unique-constraint error as an unhandled `500`;
- add and reactivate serialize with deactivate for the same pair;
- add/reactivate cannot report success after the parent Position has been globally deleted;
- global delete cannot miss an allowed link added through the F2 service while it holds the Position lock;
- concurrent writes use the same parent-first lock order, preventing link-parent lock inversion;
- row counts/`RETURNING` results are checked so an UPDATE of a row deleted by another transaction cannot be reported as success;
- database deadlock or serialization failures, if still possible, are translated according to the project-wide retry/error policy and never treated as successful mutation.

The parent Position lock is the serialization point shared by link mutations and global delete. The unique constraint remains the final duplicate guard; the FK remains the final parent-existence guard.

This parent lock is sufficient even when the junction row does not yet exist: every F2 add/reactivate/deactivate path and global Position delete must acquire `positions FOR UPDATE` before testing or writing the pair. Thus a second add for a missing pair waits on the Position row rather than relying on a nonexistent junction-row lock. The lock protocol must live inside the service transaction (or in a locked internal helper that cannot be called without it), not only in the route.

After any wait, the operation revalidates all state under its acquired locks before deciding its transition or HTTP response. The Position lock is held continuously from dependency evaluation through inactive-link cleanup and the actual Position `DELETE`, so there is no check/delete window for compliant F2 link writers or current non-deferrable inbound FK writers.

### 6.1. Locking/concurrency contract

Two-connection PostgreSQL tests without monkeypatching the production detector must prove both directions:

1. A real child FK INSERT/UPDATE established before the Position lock makes global delete wait when necessary; after the child commits, the real dependency check sees the blocker and deletion does not pass preflight.
2. A real child FK INSERT/UPDATE started after global delete holds the Position lock and has obtained a true empty dependency result waits on the parent row; global delete can complete, and the waiting child statement then receives `23503` instead of inserting a dependency between preflight and delete.

These tests prove that the approved lock order closes the designated late-FK concurrency window. They must not weaken `positions FOR UPDATE`, replace dependency SQL/results, add test-only FK/trigger objects, or be represented as a positive Position-DELETE race.

### 6.2. Defensive late-FK classifier contract

The Position DELETE route retains a defensive classifier for a real PostgreSQL FK error raised directly by the Position DELETE. This contract does not assert that the classified branch is reproducible through the current concurrency window. Classification requires all of the following:

- PostgreSQL SQLSTATE is exactly `23503`;
- `orig.diag.constraint_name` is present and non-empty;
- the constraint is discovered from PostgreSQL metadata as a restrictive inbound FK referencing `public.positions`;
- `orig.diag.schema_name` and `orig.diag.table_name`, when supplied by the driver, match the discovered child FK identity;
- the catch is immediately around the production Position DELETE, with no SQL-text or caller-controlled identity inference;
- savepoint rollback restores connection usability before metadata validation;
- confirmed classification rolls back inactive-link cleanup and Position deletion atomically;
- the client receives only HTTP `409`, `error_code=POSITION_HAS_DEPENDENCIES`, and `race_detected=true`, without constraint, SQL, or driver details.

Unknown constraints, other SQLSTATE values, another table or statement, metadata lookup failure, and generic database errors are not classified. The accepted API field name `race_detected` is retained for compatibility and means “the defensive late-FK branch was recognized”; it does not mean that the current schema's assigned concurrency race was reproduced.

## 7. Audit contract

F2 uses the existing append-only `public.security_audit_log` through `write_security_event(..., conn=conn)`. It must not introduce a parallel audit table.

The following event types are mandatory:

```text
ORG_UNIT_ALLOWED_POSITION_CREATED
ORG_UNIT_ALLOWED_POSITION_REACTIVATED
ORG_UNIT_ALLOWED_POSITION_UPDATED
ORG_UNIT_ALLOWED_POSITION_DEACTIVATED
```

Every event must persist:

- `event_type`;
- `actor_user_id` of the authenticated system administrator;
- `success = true`;
- non-null `audit_id` returned by the audit append;
- metadata containing `org_unit_allowed_position_id`, `org_unit_id`, `position_id`, `previous_state`, and `current_state`.

State payloads include at least `is_active` and `sort_order`. For create, `previous_state` is `null`; for reactivate it records inactive to active; for update both states are active and metadata must explicitly include previous and new `sort_order`; for deactivate it records active to inactive. `happened_at` is generated by the server-side database default and is not supplied by the caller. `request_id`, `ip_address`, and `user_agent` are optional contextual fields.

Audit rules:

1. The audit append occurs in the same transaction as the state change.
2. Each real domain transition requires exactly one corresponding event: `created` → `ORG_UNIT_ALLOWED_POSITION_CREATED`, `reactivated` → `ORG_UNIT_ALLOWED_POSITION_REACTIVATED`, `updated` → `ORG_UNIT_ALLOWED_POSITION_UPDATED`; deactivation emits `ORG_UNIT_ALLOWED_POSITION_DEACTIVATED`. `noop` emits none. The service result is the sole event selector for the upsert path.
3. Idempotent no-op retries do not append duplicate events.
4. Audit metadata must contain identifiers, not only display names.
5. The mutation succeeds only if the append returns a non-null `audit_id`. A `None` result, absent audit storage, null identifier, or any audit SQL error raises a domain/internal transaction error and rolls back the domain mutation.
6. Global deletion may record the count and ids of inactive links cleaned up in the existing Position deletion audit mechanism when that mechanism is introduced or extended; cleanup must not masquerade as user-requested deactivation.

An F2 audit migration is mandatory. Its upgrade must extend `chk_sal_event_type` with all four event types while preserving the complete and exact pre-F2 accepted event-type set. The Python `_ALLOWED_EVENT_TYPES` in `app/services/security_audit_service.py` must add the same four types in the same implementation. No new columns on `org_unit_allowed_positions` are required.

### 7.1. Guarded downgrade policy

The audit migration downgrade is guarded and is not unconditionally reversible. It is technically reversible only before any F2 allowed-position audit event has been persisted. After such an event exists, downgrade is intentionally blocked to preserve append-only audit history.

The following downgrade sequence is normative:

1. Before dropping, replacing, or otherwise modifying the extended `chk_sal_event_type`, query `public.security_audit_log` for the existence of any row whose `event_type` is one of:
   - `ORG_UNIT_ALLOWED_POSITION_CREATED`;
   - `ORG_UNIT_ALLOWED_POSITION_REACTIVATED`;
   - `ORG_UNIT_ALLOWED_POSITION_UPDATED`;
   - `ORG_UNIT_ALLOWED_POSITION_DEACTIVATED`.
2. If at least one matching row exists, raise a controlled migration error before any CHECK DDL is executed. Do not delete, update, archive, rewrite, or otherwise mutate F2 audit rows to make downgrade possible.
3. On that guarded failure, `public.security_audit_log`, all F2 and non-F2 audit rows, and the currently effective extended `chk_sal_event_type` must remain unchanged. The database must remain in the consistent upgraded state.
4. If no matching row exists, drop the extended CHECK and restore the complete and exact pre-F2 definition of `chk_sal_event_type`. Preserve every remaining `security_audit_log` row unchanged.

Automatic deletion of F2 audit events for downgrade is prohibited. Any future archival or audit-retention procedure capable of changing this precondition requires a separately approved architecture decision and is outside F2.

## 8. Frontend contract

On `/directory/positions`, the action **«Убрать из разрешённых»** is shown only when all conditions hold:

- current user is system administrator (`role_id=2`);
- a concrete org unit is selected;
- current position scope is `allowed`;
- the row represents an active allowed link for that exact org unit.

Before the request, the UI must show confirmation containing both Position and org-unit names. The confirmation must state that:

- the Position is removed only from the selected unit's allowed list;
- the global Position is not deleted;
- other org units are unaffected.

On success, the current scoped list is reloaded and the row disappears. Cancellation performs no request. A failed request leaves the row visible and presents the backend error.

The existing global **«Удалить»** action remains distinct and must not be reused for link deactivation.

## 9. Test requirements

### 9.1. Backend service and API tests

- create a previously absent pair and return `201` with `transition=created` and the structured service result;
- repeat create and return idempotent `200` with `transition=noop`, without duplicate row/audit or `updated_at` change;
- reactivate an inactive pair with `transition=reactivated`, preserving link id;
- cover omitted, explicit `null`, and integer `sort_order` for new, inactive, and active pairs;
- update an active pair's changed `sort_order`, set `updated_at`, return `200` with `transition=updated`, and emit exactly one update event containing previous/new values;
- submit an unchanged active `sort_order`, return `200` with `transition=noop`, and emit no event;
- assert `previous_state` and `current_state` are computed inside the service transaction and the route performs no post-commit transition inference;
- deactivate only the selected pair and return `200`;
- repeat deactivate and return idempotent `200` without duplicate audit;
- return `404` for a never-existing pair;
- return `404` for missing Position and missing org unit, including `POSITION_NOT_FOUND` priority when both are absent;
- return `403` for privileged non-sysadmin, personnel admin, and ordinary users;
- verify all four audit event types, actor, `success=true`, server-default timestamp, non-null `audit_id`, link id, org-unit id, Position id, and complete previous/current state;
- force audit writer `None`, absent audit storage, null audit id, and audit SQL failure; for each case verify rollback of the link mutation and absence of a partial audit event.

### 9.2. Dependency and global-delete tests

- active allowed link appears as a blocker in dependency endpoint;
- inactive allowed link does not appear as a blocker;
- `delete_status=blocked` includes a Position with an active link;
- `delete_status=deletable` includes a Position whose only allowed links are inactive;
- active and inactive links together still block deletion and no inactive cleanup commits;
- only inactive links are physically removed when global Position deletion succeeds;
- another FK dependency causes `409` and restores the transactionally deleted inactive links;
- the defensive late-FK branch produces controlled `409` and full rollback under the explicit test organization in §9.3.1;
- every other discovered `RESTRICT` / `NO ACTION` FK remains blocking;
- an identically named table/FK outside `public` remains fully blocking;
- an unknown schema/table/column/constraint identity uses secure-default blocking `TRUE`;
- direct database FK still rejects deletion when a dependent row survives unexpectedly.

### 9.3. Concurrency tests

- **Add/add:** hold the first request after `positions FOR UPDATE`; prove the second waits on that Position lock even when the junction row is missing. Release in order and assert HTTP `201` then `200`, one junction row, one stable link id, and exactly one `ORG_UNIT_ALLOWED_POSITION_CREATED` event.
- **Reactivate first/global-delete second:** hold reactivation under the Position lock, start delete, then release. Assert reactivate `200`, delete `409`, and both Position and active link remain.
- **Global-delete first/reactivate second:** hold delete after its Position lock, start reactivate, then release. Assert delete `200`, reactivate `404 POSITION_NOT_FOUND`, and both Position and junction link are absent.
- **Deactivate/reactivate:** exercise both lock orders with explicit barriers. The second linearized mutation determines final `is_active`; assert no `500`, duplicate row, stale/false success, or audit event inconsistent with a committed transition.
- **Deactivate first/global-delete second:** with no other blockers, assert deactivate `200`; global delete may then return `200`, and if so Position and inactive link are absent.
- **Add or reactivate first/global-delete second:** assert the link mutation succeeds and global delete returns `409 POSITION_HAS_DEPENDENCIES`.
- **Successful global-delete first/link mutation second:** separately cover waiting add, reactivate, and deactivate; each returns `404 POSITION_NOT_FOUND`.
- **Child dependency before Position lock:** complete a real child INSERT/UPDATE without commit, start global delete on another connection, prove the delete waits on the parent-row lock, commit the child, and assert the real dependency check returns ordinary `409` without passing preflight.
- **Child dependency after Position lock:** hold the Position lock, obtain a true empty production dependency result, start a real child INSERT and UPDATE on separate connections, prove each waits, then commit successful Position deletion and assert `23503` occurs on the waiting child statement rather than on Position DELETE.
- **Repeated mixed operations:** assert the prescribed lock order does not deadlock and stale UPDATE results cannot be reported as success.

Database-backed concurrency tests must use separate connections, lock-observation or explicit synchronization barriers, and bounded wait assertions; thread timing alone is not acceptable. After every unsuccessful transaction, tests must verify all three durable surfaces: the Position row, junction row/state/count/id, and relevant `security_audit_log` rows. No failed transaction may leave partial domain or audit state.

### 9.3.1. Defensive late-FK classifier tests

The defensive branch requires separate evidence from the locking tests:

- a real PostgreSQL integration case must produce an actual `23503` with an actual restrictive inbound FK constraint from the production schema and exercise classifier/savepoint rollback;
- a separate route assertion must verify the exact HTTP `409` envelope with `error_code=POSITION_HAS_DEPENDENCIES` and `race_detected=true`;
- Position and inactive junction rows must be restored and the connection must remain usable;
- negative cases cover unknown or missing constraint identity, non-`23503`, another FK/table/statement, misleading SQL text, metadata lookup failure, generic `IntegrityError`, and other database errors;
- a minimal controlled test arrangement may bypass the production dependency preflight solely to cause the real PostgreSQL Position-DELETE FK error needed to exercise the defensive branch. The test name and comment must state that this is classifier/rollback evidence, not proof of a reachable current-schema concurrency race.

A synthetic `IntegrityError` cannot be the only positive evidence. Tests must not substitute constraint identity, weaken the Position lock or dependency policy, add an FK/trigger absent from the production schema, or introduce Stage 6 retry/advisory-lock behavior.

### 9.4. Frontend and contract tests

- action visible only to `role_id=2` in selected-unit `allowed` mode;
- action hidden in global and `used` modes and for non-sysadmins;
- confirmation includes both names;
- cancel sends no request;
- confirm calls the nested DELETE endpoint with the selected org-unit and Position ids;
- successful response reloads the current list;
- API error is displayed without removing the row locally;
- global Position delete action remains separate;
- frontend request/response fixtures match backend status and error-code contracts.

### 9.5. Audit migration tests

- upgrade extends `chk_sal_event_type` with all four F2 event types without dropping any pre-F2 accepted value;
- upgraded schema accepts each F2 event type, continues to accept the complete pre-F2 set, and rejects an unknown type;
- Python `_ALLOWED_EVENT_TYPES` contains exactly the four required additions;
- with no persisted F2 event rows, downgrade succeeds and restores the complete and exact pre-F2 `chk_sal_event_type` while preserving all other audit rows;
- with each of the four F2 event types in turn, or an equivalent parameterized matrix, downgrade fails with the controlled guarded-downgrade error;
- on guarded failure, the triggering F2 rows and all other audit rows remain byte-for-byte logically unchanged;
- on guarded failure, the extended `chk_sal_event_type` remains installed and continues to accept all four F2 types and reject unknown types;
- instrumentation or transactional assertions prove that the guarded error occurs before any `DROP CONSTRAINT`, `ALTER CONSTRAINT`, or replacement `ADD CONSTRAINT` operation;
- after guarded failure, the database remains in a consistent upgraded state and a subsequent valid audit insert behaves according to the extended CHECK;
- migration tests run against PostgreSQL so real transactional DDL and the real CHECK, not mocks, are exercised.

## 10. Expected implementation files

The implementation WP is expected to touch only the necessary subset of these files:

### Backend

- `app/services/org_unit_allowed_positions_service.py`
  - concurrency-safe create/reactivate/update/noop with structured mutation result;
  - soft-deactivate operation;
  - shared lock protocol.
- `app/services/position_dependencies_service.py`
  - explicit per-dependency blocking predicate.
- `app/directory/positions_routes.py`
  - nested mutation endpoints or router delegation;
  - transactional inactive-link cleanup in global delete;
  - system-admin backend guard.
- `app/services/security_audit_service.py`
  - mandatory `_ALLOWED_EVENT_TYPES` extension with all four F2 event types;
  - strict non-null `audit_id` handling by the mutation caller using the same transaction.
- `alembic/versions/<revision>_adr046_f2_allowed_position_audit_events.py`
  - mandatory `chk_sal_event_type` extension;
  - guarded downgrade that restores the exact pre-F2 CHECK only when no F2 audit rows exist and otherwise fails before CHECK DDL without mutating audit history;
  - no FK action change.

### Frontend

- `corpsite-ui/app/directory/positions/_components/PositionsPageClient.tsx`
  - scoped action, confirmation, request, refresh, and error state.
- `corpsite-ui/lib/adminNav.ts`
  - reuse existing `isSystemAdminRole`; no broader permission gate.

### Tests

- `tests/test_adr046_f2_org_unit_allowed_positions_crud.py` (new focused API/service/concurrency coverage);
- `tests/test_adr046_f2_allowed_position_audit_migration.py` (new PostgreSQL migration/constraint coverage);
- `tests/test_directory_contacts_positions_routes.py` (global-delete and dependency behavior);
- `tests/test_adr046_f1_org_unit_allowed_positions.py` only if shared read-contract assertions need extension;
- `corpsite-ui/app/directory/positions/_components/PositionsPageClient.test.tsx`;
- optional focused contract fixture/module if the project adopts shared generated API types.

Exact router splitting and test file placement may change during WP planning, but the contracts and invariants in this document must not.

## 11. Compatibility and governance

### 11.1. Compatibility with accepted ADRs

This decision is compatible with ADR-046 because it preserves:

- soft-disable as the normal remove operation;
- same-pair reactivation;
- direct org-unit semantics without inheritance;
- `ON DELETE RESTRICT`;
- separation of allowed links from the global catalog and actual Employment.

It is also compatible with ADR-050: F2 governs the current transitional catalog junction and does not redefine org-unique Position or Position Cabinet lifecycle.

### 11.2. Required document type

A new independent ADR is **not required** because the decision does not override ADR-046 or the Architecture Baseline. It fills an explicitly deferred F2 lifecycle and CRUD gap.

The accepted documentation structure should be:

1. This document — ADR-046 F2 architecture supplement, approved before implementation.
2. `WP-ADR-046-F2` — separate implementation work package created after architecture approval, containing tasks, rollout, rollback, observability, and acceptance evidence.
3. ADR-046 parent status/history update when F2 is approved and later implemented.
4. Deployment note after implementation if schema/event-type migration or operational rollout requires it.

A separate ADR becomes necessary only if review chooses to change the FK to `ON DELETE CASCADE`, forbid global catalog deletion after any historical link, or redefine the target model away from the accepted ADR-046/ADR-050 boundary.

## 12. Out of scope

- Implementation of endpoints, services, UI, tests, or migrations.
- Manual modification of `org_unit_allowed_positions` data.
- Deletion or modification of Position ID 100.
- Bulk allowed-position import or org templates (ADR-046 F4).
- Staffing headcount, vacancies, or org-unique Position redesign.
- Granting F2 mutation rights to HR or directory-privileged operators.
- Changing any non-`org_unit_allowed_positions` dependency policy.

## 13. Review and acceptance checklist

Architecture review and the future WP acceptance criteria must explicitly require:

- nested resource endpoint shape;
- `404` for never-existing pair versus idempotent `200` for already inactive pair;
- active-only dependency semantics;
- transactionally coupled inactive-link cleanup;
- parent-first lock order;
- use of `security_audit_log` and event names;
- mandatory audit migration, strict non-null `audit_id`, and rollback semantics;
- guarded audit downgrade: success only before F2 audit events exist, controlled pre-DDL refusal afterward, exact pre-F2 CHECK restoration on the success path, and no automatic audit-history deletion;
- system-admin-only F2 authorization;
- structured mutation result and service-owned transition selection;
- schema-qualified secure-default dependency policy;
- normative lock-safety concurrency matrix and separate defensive late-FK classifier/rollback evidence.

### 13.1. Stage 5 implementation closure

Stage 5 is **CLOSED / APPROVED** as of 2026-08-07. The final independent conclusion is:

> Stage 5 Final Re-Review: APPROVED — all remaining findings resolved; Ready for Stage 5 closure

The final three findings are closed by accepted evidence that:

- post-rollback dependency refresh runs through the production detector outside the request-level `engine.begin()` transaction;
- the complete negative defensive-classifier matrix is covered while the closed defensive `409` exposes no PostgreSQL or internal details;
- global Position DELETE `409` OpenAPI documentation uses a union of the ordinary dependency-conflict detail and the closed defensive detail.

The authorized repository-guarded `corpsite_test` runs completed with `34 passed` and `28 passed`. No Stage 5 findings remain open. Stage 6 is a separate stage and remains **NOT STARTED**; this documentation update neither starts nor authorizes Stage 6.

## 14. Document history

| Date | Status | Change |
|---|---|---|
| 2026-08-07 | Draft — Ready for Architecture Review | Initial F2 lifecycle, dependency, transaction, concurrency, audit, authorization, UI, and test contract |
| 2026-08-07 | Draft — Ready for Architecture Review | Architecture-review corrections: complete `sort_order` semantics, structured transitions, mandatory audit migration/rollback, schema-qualified dependency policy, and normative concurrency matrix/tests |
| 2026-08-07 | Draft — Ready for Architecture Review | Guarded audit downgrade contract, failure invariants, PostgreSQL migration matrix, and acceptance criterion |
| 2026-08-07 | Draft — Ready for Architecture Re-Review | PostgreSQL experiment proved the former positive late-FK interleaving unreachable under the current non-deferrable FK schema and Position-first lock order; evidence is now split into lock-safety and defensive classifier contracts without changing production semantics |
| 2026-08-07 | Accepted — Stage 5 Closed; Stage 6 Not Started | Architecture clarification accepted and final Stage 5 re-review approved; post-rollback refresh, complete negative classifier matrix, and two-variant `409` OpenAPI union closed the last findings; authorized checks passed (`34 passed`, `28 passed`); Stage 6 remains separate and not authorized |
