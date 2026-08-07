# WP-ADR-046-F2 — Admin CRUD and allowed-position link lifecycle

| Field | Value |
|---|---|
| Status | **Stage 5 Closed — Stage 6 Not Started** |
| Date | 2026-08-07 |
| Architecture source | [ADR-046 F2 supplement](../adr/ADR-046-F2-admin-crud-link-lifecycle-supplement.md) |
| Parent decision | [ADR-046](../adr/ADR-046-org-unit-allowed-positions.md) |
| Architecture review | **Architecture Review: APPROVED — Ready for WP-ADR-046-F2 preparation** |
| Clarification gate | **Architecture Re-Review: APPROVED — ADR clarification accepted** |
| Stage 5 final review | **Stage 5 Final Re-Review: APPROVED — all remaining findings resolved; Ready for Stage 5 closure** |
| Next stage | **Stage 6 — NOT STARTED; this closure does not authorize commencement** |
| Scope | F2 mutations, dependency/global-delete policy, audit, and sysadmin UI |

## 1. Purpose and boundary

This WP converts the ADR into review-gated implementation tasks. The lock-safety/defensive-classifier clarification passed Architecture Re-Review without changing production semantics.

Stage 5 is closed after final independent re-review. Stage 6 is separate and **NOT STARTED**; this closure record does not authorize Stage 6 work.

Deliver:

- create/reactivate/update/noop/soft-deactivate lifecycle for `public.org_unit_allowed_positions`;
- active-only blocking for the exact allowed-position FK and transactional cleanup of inactive links during global Position deletion;
- atomic audit for every real transition;
- canonical `SYSTEM_ADMIN role_id=2` authorization on backend and frontend;
- deterministic PostgreSQL migration, rollback, dependency, and concurrency evidence;
- confirmed **«Убрать из разрешённых»** UI.

Out of scope: changing the ADR or FK actions; manual SQL/data repair; deleting Position ID 100; bulk/template/headcount work; broader permissions; a parallel audit table; automatic audit-history deletion; implementation before WP review.

## 2. Frozen contracts

### 2.1. Routes and authorization

```text
PUT    /directory/org-units/{org_unit_id}/allowed-positions/{position_id}
DELETE /directory/org-units/{org_unit_id}/allowed-positions/{position_id}
```

Every mutation must call the canonical backend system-admin check. Only `role_id=2` is authorized. Privileged allowlists, personnel visibility/admin, org scope, and `has_sysadmin_api` do not grant F2 mutation rights. Frontend uses `isSystemAdminRole(me)` only; backend remains authoritative.

### 2.2. PUT input, transitions, and result

| Request | Effective `sort_order` |
|---|---|
| Body/field omitted | Preserve existing value; use `NULL` for a new pair |
| `{sort_order: null}` | Set `NULL` |
| `{sort_order: <integer>}` | Set supplied integer |

Service result, computed under locks before commit:

```text
link
transition = created | reactivated | updated | noop
previous_state
current_state
```

Route must not reread state or infer transition after commit.

| Before/effect | Transition | HTTP | Audit |
|---|---|---:|---|
| Pair absent; create active | `created` | `201` | one `ORG_UNIT_ALLOWED_POSITION_CREATED` |
| Pair inactive; reactivate same row | `reactivated` | `200` | one `ORG_UNIT_ALLOWED_POSITION_REACTIVATED` |
| Pair active; effective sort changes | `updated` | `200` | one `ORG_UNIT_ALLOWED_POSITION_UPDATED` |
| Pair active; no effective change | `noop` | `200` | none; `updated_at` unchanged |

`previous_state` is null for create. Other states contain at least `is_active` and `sort_order`. Noop states are identical.

### 2.3. Link DELETE

| Condition | HTTP | Contract |
|---|---:|---|
| Active pair | `200` | Set only this pair `is_active=FALSE`; one deactivation event |
| Already inactive | `200` | Noop; no audit or timestamp change |
| Pair never existed | `404` | `ALLOWED_POSITION_LINK_NOT_FOUND` |
| Position absent | `404` | `POSITION_NOT_FOUND` |
| Org unit absent | `404` | `ORG_UNIT_NOT_FOUND` |
| Both parents absent | `404` | `POSITION_NOT_FOUND` takes priority |
| Non-system-admin | `403` | Forbidden |

Deactivation never deletes the Position, changes another unit, or mutates employee/assignment data.

### 2.4. Global Position delete

| Condition | HTTP | Contract |
|---|---:|---|
| Active link or any other real blocker | `409` | `POSITION_HAS_DEPENDENCIES` |
| Position absent | `404` | `POSITION_NOT_FOUND` |
| Only inactive links, no other blocker | `200` | Inactive links and Position deleted in one transaction |
| Defensive Position-DELETE FK branch is recognized | `409` | Controlled response with mandatory `race_detected=true`; the field names the accepted defensive branch and does not assert a reproducible current-schema race |

Inactive links are excluded from dependency details, `delete_status` filters, preflight, and totals. Cleanup occurs immediately before Position delete in the same transaction; any later blocker/error restores it.

### 2.5. Locks and races

Pair mutations:

```text
positions FOR UPDATE
→ org_units FOR UPDATE
→ junction FOR UPDATE when present
→ audit append
→ commit
```

Global delete:

```text
positions FOR UPDATE
→ all matching junction rows FOR UPDATE in PK order
→ active decision / inactive cleanup
→ remaining dependency checks
→ Position DELETE
→ commit
```

Position is the serialization point even when no junction exists and stays locked through actual DELETE, closing the check/delete window.

The 2026-08-07 PostgreSQL experiment established the current-schema reachability boundary. All existing inbound FKs to `public.positions` are non-deferrable. A child INSERT/UPDATE obtains or waits for FK `KEY SHARE` protection of the parent row:

- when the child write starts before the Position lock, global delete waits when necessary and the committed dependency is found by the real dependency check;
- when the child write starts after the Position lock and a true empty dependency result, the child waits, successful Position deletion commits, and the child statement receives `23503`.

Therefore the assigned concurrent child-write interleaving cannot produce `23503` directly on production Position DELETE with the current schema and lock order. This does not claim that a future or exceptional PostgreSQL Position DELETE can never raise `23503`.

Locking evidence and defensive-classifier evidence are separate:

1. **Locking/concurrency:** two real PostgreSQL connections, the unmodified detector, and observed lock waits prove both child-before-lock and child-after-lock outcomes. No dependency-result monkeypatch, weakened Position lock, test-only FK/trigger, retry, or advisory lock is allowed.
2. **Defensive classifier:** a real `23503` raised directly at Position DELETE is classified only with non-empty `orig.diag.constraint_name` that metadata discovery identifies as a restrictive inbound FK to `public.positions`; driver-supplied diagnostic schema/table must match the discovered child FK identity. The catch is local to the DELETE, does not inspect SQL text, rolls back its savepoint before metadata lookup, and then rolls back cleanup/Position deletion before returning `409` with `error_code=POSITION_HAS_DEPENDENCIES` and `race_detected=true`.

For API compatibility, `race_detected=true` means the defensive late-FK branch was recognized; it is not evidence that the current-schema concurrency interleaving is reachable. Unknown/missing constraints, non-`23503`, another table/statement, metadata failure, generic integrity errors, and other database errors are not classified or disclosed to the client.

### 2.6. Dependency policy

Internal identity contains at least:

```text
(child_schema, child_table, child_column)
= (public, org_unit_allowed_positions, position_id)
```

Because discovery exposes it, include or validate `constraint_name`; expected current name is `org_unit_allowed_positions_position_id_fkey`. Only this exact FK uses `dep.is_active=TRUE`. Every unknown schema/table/column/constraint uses secure default `TRUE`. Same-named tables in other schemas remain fully blocking. Preserve the schema-less public response key.

### 2.7. Audit contract

Mandatory types:

```text
ORG_UNIT_ALLOWED_POSITION_CREATED
ORG_UNIT_ALLOWED_POSITION_REACTIVATED
ORG_UNIT_ALLOWED_POSITION_UPDATED
ORG_UNIT_ALLOWED_POSITION_DEACTIVATED
```

Every real transition uses `write_security_event(..., conn=conn)` in the domain transaction and requires non-null `audit_id`, sysadmin `actor_user_id`, `success=true`, server-default `happened_at`, link/org/Position ids, and previous/current state. Update includes old/new sort. Request/IP/user-agent fields are optional. Noop has no event.

`None`, missing audit storage, null id, or audit INSERT SQL failure prevents success and rolls back the whole domain mutation. Separate-connection/best-effort audit is prohibited.

### 2.8. Guarded downgrade

Upgrade adds all four types to both `chk_sal_event_type` and Python `_ALLOWED_EVENT_TYPES` while retaining the exact pre-F2 set.

Before any downgrade CHECK DDL, query for all four F2 types. If any row exists, raise a controlled error before DDL; preserve all rows and the extended CHECK; never delete/rewrite/archive audit history automatically. If none exists, restore the exact full pre-F2 CHECK and preserve all other rows. Downgrade is technically reversible only before an F2 event is persisted.

## 3. Sequential implementation stages

Each stage is a review gate; the next starts only after evidence from the previous stage is accepted.

### Stage 1 — Audit CHECK migration and migration tests

**Goal:** register the four DB event types and prove guarded downgrade before emitters exist.

**Files**

- `alembic/versions/<new_revision>_adr046_f2_allowed_position_audit_events.py` (new).
- `tests/test_adr046_f2_allowed_position_audit_migration.py` (new).

**Changes**

- Capture the complete current pre-F2 tuple; upgrade to that tuple plus exactly four F2 types.
- In downgrade, query all four types before any CHECK DDL.
- Refuse downgrade on any match; otherwise restore the exact pre-F2 CHECK.
- Preserve all audit rows on both paths.

**Tests**

- Upgrade accepts each F2 type, all pre-F2 types, and rejects unknown types.
- Empty-F2 downgrade succeeds, restores exact pre-F2 CHECK, and preserves unrelated rows.
- Parameterized test: each F2 type independently blocks downgrade.
- On refusal, F2/unrelated rows and extended CHECK remain unchanged.
- Instrumentation/transaction assertions prove refusal precedes DROP/replacement DDL.
- After refusal, valid F2 insert succeeds, unknown type fails, and DB is consistent.

**Acceptance:** PostgreSQL tests pass; migration contains no audit deletion; behavior matches the existing guarded migration pattern and is not called unconditionally reversible.

**Depends on:** approved ADR.

**Stop for review:** verify tuple completeness, Alembic ancestry, pre-DDL guard, failure atomicity, and PostgreSQL evidence. Do not change the audit service yet.

### Stage 2 — Audit allowlist and existing-writer contract

**Goal:** add the four event types to the Python allowlist and characterize the existing audit writer contract that the Stage 4 mutation caller must enforce.

**Files**

- `app/services/security_audit_service.py`.
- `tests/test_adr046_f2_org_unit_allowed_positions_crud.py` (new; audit-focused start).

**Changes**

- Add exactly four F2 values to `_ALLOWED_EVENT_TYPES`.
- Reuse `write_security_event(..., conn=conn)`.
- Do not add an F2-specific helper or a new generic wrapper to `security_audit_service.py`.
- Preserve the existing writer behavior: successful insert returns `audit_id`; missing storage may return `None`; audit SQL errors propagate; `happened_at` remains server-defaulted.
- Defer mandatory result validation and domain rollback to the mutation caller in `org_unit_allowed_positions_service.py` in Stage 4.

**Tests:** allowlist parity; all four values pass validation; unknown value remains rejected; successful existing-writer insert returns non-null id; server-default timestamp; missing storage returns `None`; SQL errors propagate. Domain rollback and noop audit behavior are Stage 4 tests.

**Acceptance:** DB/Python additions match; the current writer contract is evidenced without adding a wrapper or changing unrelated caller behavior; Stage 4 has an explicit dependency on these evidenced outcomes.

**Depends on:** Stage 1 accepted.

**Stop for review:** inspect allowlist, metadata, connection ownership, and failure evidence. Do not implement link mutations.

### Stage 3 — Schema-qualified dependency policy

**Goal:** make only inactive rows of the exact public junction FK non-blocking.

**Files**

- `app/services/position_dependencies_service.py`.
- `tests/test_directory_contacts_positions_routes.py`.
- `tests/test_adr046_f2_org_unit_allowed_positions_crud.py`.

**Changes**

- Add structural schema/table/column/constraint policy identity.
- Apply active-only predicate consistently to single/multi checks and blocked/deletable SQL.
- Keep public response key compatible.
- Default unknown identities to blocking TRUE.

**Tests:** active/inactive/mixed links; filters and details; same-named other-schema FK; unknown constraint; all other discovered restrictive FKs; public key compatibility.

**Acceptance:** exception is limited to exact public FK; secure default is proven across all detector entry points.

**Depends on:** Stage 2 accepted.

**Stop for review:** inspect policy identity, SQL, discovery coverage, and public response. Do not alter global delete.

### Stage 4 — Service lifecycle and transactional locks

**Goal:** replace unlocked read-then-insert with the approved concurrency-safe service.

**Files**

- `app/services/org_unit_allowed_positions_service.py`.
- `tests/test_adr046_f2_org_unit_allowed_positions_crud.py`.

**Changes**

- Represent omitted `sort_order` separately from explicit `None`.
- Lock Position → org unit → existing pair.
- Use the Position lock as absent-row serialization point and a conflict-safe insert as final guard.
- Return `link/transition/previous_state/current_state` under locks.
- Implement created/reactivated/updated/noop plus same-row soft-deactivation.
- In `org_unit_allowed_positions_service.py`, append the exact audit event on the same connection and inside the same domain transaction for each real transition.
- The mutation caller must inspect the audit INSERT result before commit. `None`, null `audit_id`, missing audit storage, or audit SQL error must raise and roll back the complete domain mutation.
- Noop must not call the audit writer.
- Check RETURNING/row counts so stale writes cannot report success.

**Tests:** all three sort inputs for absent/inactive/active rows; stable id; every transition/state/audit mapping; noop timestamp/audit invariants; selected-pair-only deactivation; parent/pair 404 precedence; complete rollback for every audit failure.

**Acceptance:** no unlocked F2 SELECT-then-INSERT remains; service result alone determines response; every real transition commits only with one non-null audit id; every audit failure rolls back domain state; noop emits zero events.

**Depends on:** Stages 1–3 accepted.

**Stop for review:** inspect transaction ownership, SQL lock order, input presence type, result type, and rollback evidence. Do not expose routes.

### Stage 5 — Backend routes, schemas, and global delete — CLOSED / APPROVED

**Goal:** expose approved nested routes and couple inactive cleanup to global Position deletion.

**Files**

- `app/directory/positions_routes.py`.
- `app/services/org_unit_allowed_positions_service.py` only for reviewed route-facing types.
- `tests/test_adr046_f2_org_unit_allowed_positions_crud.py`.
- `tests/test_directory_contacts_positions_routes.py`.

**Changes**

- Add presence-aware PUT schema and nested PUT/DELETE routes.
- Enforce `_is_system_admin(user)` before mutation.
- Map service transition directly to 201/200; no reread.
- Implement exact 403/404/409 contracts and Position-first missing-parent priority.
- In global delete, lock Position and junction rows, reject active rows, clean inactive rows, check all other dependencies, and delete Position in one transaction.
- Retain the defensive direct-Position-DELETE FK classifier: validate real `23503` plus discovered restrictive inbound constraint identity, restore cleanup through savepoint/full rollback, and return controlled 409 with mandatory `race_detected=true`.

**Tests:** request presence parsing; all HTTP/error rows in §2; non-sysadmin 403 matrix; active-only dependency/filter behavior; other-blocker rollback; defensive classifier/savepoint integration using a real PostgreSQL `23503` and real production-schema inbound FK; exact route 409 envelope with `race_detected=true`; negative classifier cases; no route-level transition inference. A minimal controlled preflight bypass is permitted only to cause the real Position-DELETE FK error and must be named/commented as defensive classifier evidence, never as production concurrency reachability.

**Acceptance:** paths and statuses match ADR; no partial cleanup/mutation; non-allowed dependencies retain behavior; defensive evidence does not claim that the current-schema late-FK concurrency interleaving is reachable.

**Depends on:** Stage 4 accepted.

**Closure (2026-08-07):** Stage 5 is **CLOSED / APPROVED**.

Final independent conclusion:

> Stage 5 Final Re-Review: APPROVED — all remaining findings resolved; Ready for Stage 5 closure

The final three findings are closed: post-rollback refresh runs outside request-level `engine.begin()` through the production detector; the complete negative classifier matrix is covered and the defensive `409` remains closed; generated OpenAPI represents ordinary and defensive `409` details as a union. The authorized repository-guarded `corpsite_test` runs completed with `34 passed` and `28 passed`. No Stage 5 findings remain open.

**Next-stage gate:** Stage 6 remains **NOT STARTED** and separate. This closure update does not authorize starting Stage 6 or frontend work.

### Stage 6 — Backend rollback and concurrency proof — NOT STARTED

**Status:** **NOT STARTED**. Stage 5 closure does not authorize implementation of this stage.

**Goal:** prove linearization, exact HTTP outcomes, durable state, rollback, and audit cardinality with PostgreSQL.

**Files**

- `tests/test_adr046_f2_org_unit_allowed_positions_crud.py`.
- `tests/test_directory_contacts_positions_routes.py`.

**Changes**

- Add a concurrency harness using separate database connections and transactions.
- Add named synchronization barriers and bounded wait assertions.
- Add lock observation/assertion rather than timing-only sleeps.
- After every unsuccessful transaction, assert Position, junction count/id/state, and F2 audit rows.

**Tests**

**Normative concurrency matrix**

Every row uses independent PostgreSQL connections. A wait is accepted only when a bounded observation query sees the waiting backend in `pg_stat_activity.wait_event_type='Lock'` and/or its relevant `pg_locks` request with `granted=FALSE`. Thread liveness or elapsed time alone is insufficient.

| Scenario/start | Connections, order, barrier, and wait proof | Exact operation results | Final Position / junction and failed-transaction rollback | Exact F2 audit events |
|---|---|---|---|---|
| Add/add; pair absent | Connection A locks Position, then org unit, confirms no junction, and stops at `add_a_before_insert`. Connection B issues the same PUT and is observed waiting on A's Position lock. Release A to insert, audit, and commit; B then locks parents and the created junction. | A: `201 created`. B: `200 noop`. No 500 or unique error. | Position exists. Exactly one active junction row with one stable link id; B changes nothing and reports no false create. | Exactly 1 `ORG_UNIT_ALLOWED_POSITION_CREATED`; 0 events from B. |
| Successful global delete first → waiting add | Pair absent. Connection A locks Position at `delete_position_locked`. B issues PUT/add and is observed waiting on Position. Release A to delete/commit; B re-runs its locked Position lookup. | A: `200`. B: `404 POSITION_NOT_FOUND`. | Position absent; junction absent. B's failed transaction leaves both absent and creates no row. | 0 F2 events. |
| Successful global delete first → waiting reactivate | Pair initially inactive. A locks Position and junction at `delete_links_locked`. B issues PUT/reactivate and is observed waiting on Position. Release A to clean inactive link, delete Position, and commit. | A: `200`. B: `404 POSITION_NOT_FOUND`. | Position absent; junction absent. B cannot report reactivation or recreate the pair. | 0 new F2 events; specifically 0 `ORG_UNIT_ALLOWED_POSITION_REACTIVATED`. |
| Successful global delete first → waiting deactivate | Pair initially inactive. A locks Position/junction at `delete_links_locked`. B issues nested DELETE and is observed waiting on Position. Release A to delete link and Position. | A: `200`. B: `404 POSITION_NOT_FOUND`. | Position absent; junction absent. B cannot return idempotent 200 after parent deletion. | 0 new F2 events; specifically 0 `ORG_UNIT_ALLOWED_POSITION_DEACTIVATED`. |
| Add first → waiting global delete | Pair absent. A locks parents, inserts/audits, and pauses before commit at `add_audited_uncommitted`. B issues global DELETE and is observed waiting on Position. Commit A; B obtains Position lock, locks active junction, and rolls back its delete attempt. | A: `201 created`. B: `409 POSITION_HAS_DEPENDENCIES`. | Position exists; one active junction with A's link id. B rollback preserves both and cannot report success. | Exactly 1 `ORG_UNIT_ALLOWED_POSITION_CREATED` from A; 0 events from B. |
| Reactivate first → waiting global delete | Pair inactive. A locks parents/junction, reactivates/audits, and pauses at `reactivate_audited_uncommitted`. B global DELETE is observed waiting on Position. Commit A; B sees active link and rolls back. | A: `200 reactivated`. B: `409 POSITION_HAS_DEPENDENCIES`. | Position exists; same junction id is active. B rollback preserves both. | Exactly 1 `ORG_UNIT_ALLOWED_POSITION_REACTIVATED`; 0 events from B. |
| Deactivate first, no other blocker → waiting global delete | Pair active. A locks parents/junction, deactivates/audits, and pauses at `deactivate_audited_uncommitted`. B global DELETE is observed waiting on Position. Commit A; B locks inactive junction, cleans it, deletes Position, and commits. | A: `200`. B: `200`. | Position absent; junction absent. Neither operation reports false success. | Exactly 1 `ORG_UNIT_ALLOWED_POSITION_DEACTIVATED` from A; no additional F2 event from global cleanup. |
| Deactivate → reactivate | Pair active. A pauses after deactivate audit at `deactivate_audited_uncommitted`; B PUT/reactivate is observed waiting on Position. Commit A, then B locks and reactivates. | A: `200`. B: `200 reactivated`. | Position exists; same single junction id, final active. No duplicates. | Exactly 1 `ORG_UNIT_ALLOWED_POSITION_DEACTIVATED` and 1 `ORG_UNIT_ALLOWED_POSITION_REACTIVATED`. |
| Reactivate → deactivate | Pair inactive. A pauses after reactivate audit at `reactivate_audited_uncommitted`; B nested DELETE is observed waiting on Position. Commit A, then B locks and deactivates. | A: `200 reactivated`. B: `200`. | Position exists; same single junction id, final inactive. No duplicates. | Exactly 1 `ORG_UNIT_ALLOWED_POSITION_REACTIVATED` and 1 `ORG_UNIT_ALLOWED_POSITION_DEACTIVATED`. |
| Missing-junction parent-lock proof | Pair absent. A locks Position and org unit but pauses before INSERT at `missing_junction_parents_locked`. B add runs on another connection; `pg_locks` proves it waits on Position rather than a nonexistent junction. Release A. | A: `201 created`. B: `200 noop`. | Position exists; exactly one active junction/id. No unique violation or false second create. | Exactly 1 `ORG_UNIT_ALLOWED_POSITION_CREATED`. |
| Position and OrgUnit both absent; Position error priority | Org unit is absent before the test. Pair is absent. A holds/deletes Position and pauses at `position_delete_uncommitted`. B add starts on another connection and is observed waiting on Position. Commit A. A query recorder proves B returns immediately after the missing Position lookup without an org-unit lookup. | A global delete: `200`. B add: `404 POSITION_NOT_FOUND`, never `ORG_UNIT_NOT_FOUND`. | Position absent; org unit absent; junction absent. B writes nothing. | 0 F2 events. |
| Child FK INSERT/UPDATE established before Position lock | Writer W completes a real production-schema child INSERT or UPDATE but does not commit. Delete D starts and is observed waiting at `SELECT Position ... FOR UPDATE` through `pg_stat_activity`/`pg_locks`. Commit W; D acquires the Position lock and runs the unmodified detector. | W commits. D returns ordinary `409 POSITION_HAS_DEPENDENCIES`; it does not pass the real dependency check and does not require `race_detected`. | Position and dependent child row exist. Junction cleanup does not commit. | 0 new F2 events; exact baseline remains unchanged. |
| Child FK INSERT/UPDATE starts after Position lock and true empty check | Delete D locks Position/junction, performs cleanup, and obtains a true empty result from the unmodified detector. Writer W then issues a real child INSERT and, separately, UPDATE; each is observed waiting on the parent lock. D deletes Position and commits, then W resumes. | D returns `200`. Each waiting child statement receives PostgreSQL `23503`; no dependency is committed and the error is on the child statement, not Position DELETE. | Position and target junction are absent after D commit; failed child transactions leave no new dependency and remain usable after rollback. | 0 new F2 events; exact baseline remains unchanged. |

Global assertions for every row:

- no unhandled 500, duplicate junction row, stale/false success, or deadlock;
- every non-success transaction is followed by explicit Position, junction count/id/state, and audit queries;
- audit cardinality is compared with the exact pre-scenario baseline;
- forced audit failure separately rolls back create/reactivate/update/deactivate and emits zero committed events;
- locking tests must not monkeypatch the detector or claim a Position-DELETE `23503`; defensive classifier/route evidence remains the separate Stage 5 contract.

**Acceptance:** every row passes repeatedly under explicit synchronization with exact final state and event count; Position lock is proven for missing junction, global delete, and both current-schema child-FK directions.

**Depends on:** Stage 5 accepted and PostgreSQL available.

**Stop for review:** inspect barrier placement, wait proof, both directional outcomes, rollback snapshots, and audit counts. Frontend begins only after acceptance.

### Stage 7 — Frontend API/types/UI

**Goal:** expose soft-deactivation only to canonical sysadmin in exact selected-unit allowed mode.

**Files**

- `corpsite-ui/app/directory/positions/_components/PositionsPageClient.tsx`.
- `corpsite-ui/lib/adminNav.ts` — reuse expected; edit only for a strictly required import/export correction.

**Changes**

- Add local request/response types without changing approved API shape.
- Show **«Убрать из разрешённых»** only for `role_id=2` + concrete org unit + `allowed` scope + active link for that unit.
- Confirmation includes Position and unit names and explains global/other-unit non-impact.
- Confirm calls exact nested DELETE; cancel sends nothing.
- Success reloads scope; failure retains row and shows backend error.
- Keep global **«Удалить»** distinct.

**Tests:** type-check/focused smoke here; full component suite in Stage 8.

**Acceptance:** gate uses only `isSystemAdminRole`; backend remains authoritative; actions cannot be confused.

**Depends on:** Stage 6 accepted.

**Stop for review:** inspect predicate, copy, route, refresh/error behavior, and global-delete separation.

### Stage 8 — Frontend tests

**Goal:** lock role, scope, confirmation, request, refresh, and error contracts.

**Files**

- `corpsite-ui/app/directory/positions/_components/PositionsPageClient.test.tsx`.
- `corpsite-ui/lib/adminNav.test.ts` only if explicit F2 gate coverage is missing.

**Changes**

- Add role/scope fixtures and nested-route request/response fixtures.
- Add interaction coverage for confirmation, cancellation, refresh, and backend failure.
- Preserve existing global-delete and scope-toggle coverage.

**Tests**

- Visible only for role 2 in selected-unit allowed mode.
- Hidden globally, in used scope, and for ordinary/privileged/personnel-admin users.
- Confirmation includes both names and approved effect statement.
- Cancel sends no request; confirm sends exact nested DELETE.
- Success reloads; error retains row and displays message.
- Global Position delete stays separate.
- Fixtures match backend status/error contracts.

**Acceptance:** focused Vitest passes; tests fail if authority broadens; no optimistic removal masks failure.

**Depends on:** Stage 7 accepted.

**Stop for review:** inspect role/scope coverage and backend fixture parity. Do not declare completion.

### Stage 9 — Regression and manual verification

**Goal:** assemble complete automated and manual evidence without direct DB mutation.

**Files:** no new files expected. Only reviewed files may receive defect fixes against this WP.

**Changes:** no feature expansion. Correct only defects against approved ADR/WP contracts, return the affected stage to its review gate, and rerun its evidence. Do not run `git diff`, commit, push, or deploy during this stage before the user completes functional verification and explicitly confirms the result.

**Tests:** run §7 commands; cover F1 allowed/used reads, Position CRUD/dependencies, role gates, scope switching, migration, rollback, and concurrency.

**Manual:** execute §8 in isolated test/staging through application routes only.

**Acceptance:** all checks pass; capture responses, link id, states, and audit counts; no direct SQL, audit mutation, or global deletion of ID 100.

**Depends on:** Stages 1–8 accepted.

**Stop for review:** submit command output, migration/concurrency evidence, and manual checklist for user functional verification. Before the user's explicit functional confirmation, do not run `git diff`, commit, push, or deploy. After confirmation, `git diff` is a separate agreed review step; commit requires a subsequent separate approval; push and deploy each require later, separate approvals.

## 4. ADR-to-WP traceability

| ADR requirement | WP contract | Stages | Evidence |
|---|---|---|---|
| Soft-disable selected pair only | §2.3 | 4–5 | service/API/UI tests |
| Same-row reactivation | §2.2 | 4–6 | stable-id and concurrency tests |
| Omitted/null/integer sort | §2.2 | 4–5 | schema/service/route matrix |
| Four transitions and structured result | §2.2 | 4–5 | service and route tests |
| No audit/timestamp change for noop | §2.2, §2.7 | 2, 4, 6 | audit cardinality assertions |
| Exact HTTP/errors | §2.2–2.4 | 5–6 | API and concurrent HTTP tests |
| Parent-first locks/missing junction | §2.5 | 4, 6 | observed-wait tests |
| Global-delete inactive cleanup/rollback | §2.4–2.5 | 5–6 | success/blocker and defensive-branch rollback tests |
| Current-schema FK lock safety | §2.5, Stage 6 | 6 | child-before-lock and child-after-lock separate-connection tests with real detector |
| Defensive late-FK classifier/API signal | §2.4–2.5, Stage 5 | 5 | real `23503`/constraint/savepoint evidence plus exact 409 envelope and negative matrix |
| Schema-qualified active-only policy | §2.6 | 3, 5 | detector/filter tests |
| Secure default TRUE | §2.6 | 3 | unknown/other-schema tests |
| Four audit types in CHECK/allowlist | §2.7 | 1–2 | migration/allowlist tests |
| Existing audit-writer behavior | §2.7 | 2 | allowlist/return/None/SQL contract tests |
| Non-null audit id and atomic domain rollback | §2.7 | 4, 6 | mutation-caller None/storage/null/SQL cases |
| Guarded downgrade | §2.8 | 1 | PostgreSQL four-type matrix |
| Canonical role 2 only | §2.1 | 5, 7–8 | backend 403/UI visibility |
| Confirmation/scoped UI | §2.3 | 7–8 | component/manual tests |
| Full concurrency matrix | §2.5, Stage 6 | 6 | separate-connection suite |

Every approved ADR requirement maps to an implementation stage and acceptance artifact; none is deferred implicitly.

## 5. Complete expected file inventory

### New

- `alembic/versions/<new_revision>_adr046_f2_allowed_position_audit_events.py`
- `tests/test_adr046_f2_allowed_position_audit_migration.py`
- `tests/test_adr046_f2_org_unit_allowed_positions_crud.py`

### Existing backend

- `app/services/security_audit_service.py`
- `app/services/position_dependencies_service.py`
- `app/services/org_unit_allowed_positions_service.py`
- `app/directory/positions_routes.py`

### Existing backend tests

- `tests/test_directory_contacts_positions_routes.py`
- `tests/test_adr046_f1_org_unit_allowed_positions.py` only if shared read assertions need extension

### Existing frontend/tests

- `corpsite-ui/app/directory/positions/_components/PositionsPageClient.tsx`
- `corpsite-ui/app/directory/positions/_components/PositionsPageClient.test.tsx`
- `corpsite-ui/lib/adminNav.ts` — reuse expected
- `corpsite-ui/lib/adminNav.test.ts` only if explicit F2 gate coverage is needed

Any additional production file requires Implementation Review proof that it only places an approved contract and adds no architecture.

## 6. Risks and prohibitions

| Risk | Control |
|---|---|
| Omitted/null collapse | presence-aware request schema and route tests |
| Duplicate add | Position lock, conflict-safe insert, one-row/id assertions |
| Reactivate/delete race | shared Position lock and post-wait revalidation |
| Policy leaks to other FK/schema | structural key and secure-default tests |
| Check/delete window | Position lock through DELETE plus both real child-FK lock-direction tests |
| Defensive late-FK branch loses machine-readable signal | classifier/savepoint and route assertions require `race_detected=true` without claiming current-schema race reachability |
| Audit silently returns None | required non-null id inside domain transaction |
| Partial inactive cleanup | one delete transaction and rollback assertions |
| Migration loses existing types | exact pre-F2 tuple comparison |
| Downgrade destroys history | four-type pre-DDL guard; deletion prohibited |
| Frontend broadens authority | backend role check plus non-admin UI tests |
| Link action deletes Position | separate routes/actions/copy and GET proof |
| Git actions precede user confirmation | explicit functional-confirmation gate and separately approved Git steps |

Prohibited:

- direct junction, Position, or audit data manipulation to pass tests;
- deletion of Position ID 100;
- automatic deletion/rewrite/archive of F2 audit rows;
- `CASCADE` FK changes or weakening other dependency rules;
- separate-connection/best-effort audit for F2 mutations;
- post-commit transition inference;
- timing-only concurrency tests;
- unreviewed architecture expansion;
- `git diff`, commit, push, or deploy before completed user functional verification and explicit confirmation;
- after that confirmation, running `git diff` without a separate agreement;
- commit without its own subsequent approval;
- push or deploy without their own later, separate approvals.

## 7. Automated verification commands

From repository root:

```powershell
$env:PYTHONPATH='.'
python -m pytest -q tests/test_adr046_f2_allowed_position_audit_migration.py
python -m pytest -q tests/test_adr046_f2_org_unit_allowed_positions_crud.py
python -m pytest -q tests/test_directory_contacts_positions_routes.py tests/test_adr046_f1_org_unit_allowed_positions.py
python -m pytest -q tests/test_adr046_f2_allowed_position_audit_migration.py tests/test_adr046_f2_org_unit_allowed_positions_crud.py tests/test_directory_contacts_positions_routes.py tests/test_adr046_f1_org_unit_allowed_positions.py
```

From `corpsite-ui`:

```powershell
npm test -- --run app/directory/positions/_components/PositionsPageClient.test.tsx lib/adminNav.test.ts
npm run lint -- app/directory/positions/_components/PositionsPageClient.tsx app/directory/positions/_components/PositionsPageClient.test.tsx lib/adminNav.ts lib/adminNav.test.ts
npm run build
```

Migration and concurrency suites require PostgreSQL. Skipping them because PostgreSQL is unavailable is not acceptance evidence.

## 8. Manual verification scenario

Use isolated test/staging data and application routes only. Never globally delete Position ID 100.

### 8.1. Role and visibility

1. Sign in as canonical `role_id=2`.
2. Open `/directory/positions?org_unit_id={HR_ORG_UNIT_ID}&org_unit_name=Отдел%20кадров&position_scope=allowed`.
3. Verify **«Убрать из разрешённых»** is visible for ID 100 only in selected-unit allowed mode.
4. Verify it is hidden globally and in used mode.
5. Sign in as ordinary, privileged non-sysadmin, and personnel-admin fixtures; verify hidden.
6. As non-sysadmin call `DELETE /directory/org-units/{HR_ORG_UNIT_ID}/allowed-positions/100`; expect 403 and no junction/audit change.

### 8.2. Cancel and deactivate

1. As role 2, click the action. Confirmation must name “Менеджер УЧР” and “Отдел кадров” and state global/other-unit non-impact.
2. Cancel; prove no request.
3. Confirm; expect nested DELETE 200 and inactive link.
4. `GET /directory/positions?org_unit_id={HR_ORG_UNIT_ID}&scope=allowed` no longer includes 100.
5. `GET /directory/positions/100` returns 200; another unit is unchanged.
6. Audit inspection shows exactly one DEACTIVATED event with actor/ids/states.
7. Repeat DELETE; expect 200, unchanged timestamp, no second event.

### 8.3. Reactivate, update, noop

1. PUT the nested route with sort field omitted; expect 200/reactivated, original link id, preserved sort, one REACTIVATED.
2. PUT `{sort_order: 100}`; if changed, expect 200/updated and one UPDATED with old/new sort.
3. Repeat same PUT; expect 200/noop, unchanged timestamp, zero new events.
4. PUT `{sort_order: null}`; if changing from 100, expect 200/updated and one event.
5. Reload allowed scope; ID 100 is present again.

### 8.4. Global delete with disposable Position

1. Create/select a disposable Position in isolated data; never use 100.
2. Nested PUT creates active link → 201.
3. Global Position DELETE → 409 while active.
4. Nested DELETE → 200 inactive.
5. With no other dependencies, global DELETE → 200 and inactive link is gone.
6. Repeat setup with a real separate FK blocker; global DELETE → 409 and inactive link is restored.

Record actor role, route/body, HTTP response, link id, Position/junction state, and audit count for every step.

## 9. Definition of Done

Complete only when:

- all nine stage stop-points are reviewed;
- DB CHECK and Python allowlist contain the four approved additions;
- upgrade, empty-event downgrade, and all four guarded refusals pass on PostgreSQL;
- refusal preserves every row, extended CHECK, and consistent DB state before DDL;
- omitted/null/integer behavior passes schema/service/route tests;
- structured transitions produce exact HTTP/state/audit results without reread;
- every real transition has one committed event; every noop/rollback has zero;
- None/missing storage/null-id/SQL audit failures roll back domain state;
- exact schema-qualified dependency exception and secure default pass;
- inactive cleanup commits only with successful Position delete;
- every concurrency row passes with explicit barriers and exact final state/cardinality, including both current-schema child-FK lock directions with the unmodified detector;
- defensive classifier evidence uses a real PostgreSQL `23503` and production-schema inbound FK, proves rollback/connection usability and exact `race_detected=true` envelope, and is not labeled as reachable concurrency proof;
- backend/frontend enforce canonical role 2 only;
- UI confirmation/cancel/refresh/error and global-delete separation pass;
- F1 reads and existing Position behavior regressions pass;
- manual verification completes without direct SQL, ID 100 deletion, or audit mutation;
- evidence is ready for final Implementation Review;
- user functional verification is complete and explicitly confirmed before any `git diff`, commit, push, or deploy;
- after confirmation, `git diff` occurs only as a separately agreed review step;
- commit occurs only after its own subsequent approval;
- push and deploy occur only as later, independently approved steps.

## 10. Document history

| Date | Status | Change |
|---|---|---|
| 2026-08-07 | Draft — Ready for Implementation Review | Initial executable nine-stage work package derived from the approved ADR-046 F2 supplement |
| 2026-08-07 | Blocked — Awaiting ADR Clarification Approval | PostgreSQL experiment proved the former mandatory positive late-FK interleaving unreachable under the current non-deferrable FK schema and Position-first lock order; evidence is split into real lock-safety tests and defensive classifier behavior without changing production semantics |
| 2026-08-07 | Stage 5 Closed — Stage 6 Not Started | Architecture clarification accepted and final independent Stage 5 re-review approved; post-rollback refresh, complete negative classifier matrix, and ordinary/defensive `409` OpenAPI union closed the final findings; authorized checks passed (`34 passed`, `28 passed`); no Stage 5 findings remain and Stage 6 is not authorized |
