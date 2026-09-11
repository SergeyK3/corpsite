# WP-PPR-MIG-005F-B — Targeted projector and outbox worker

| Parameter | Value |
|---|---|
| Status | **Completed — Ready for WP-PPR-MIG-005F-C** |
| Parent | [WP-PPR-MIG-005F](WP-PPR-MIG-005F-corrections-invalidation-plan.md) |
| Depends on | [WP-005B projection](WP-PPR-MIG-005B-status-projection-read-model.md), [WP-005F design](WP-PPR-MIG-005F-corrections-invalidation-plan.md), [WP-005F-A schema](WP-PPR-MIG-005F-A-event-outbox-schema.md) |
| Scope | Addressed outbox claiming, retry lifecycle and one-cell projection only. |
| Out of scope | HR write-path integration, scheduler/runtime registration, API, frontend, permissions and production deployment. |

```mermaid
flowchart LR
  W[Кадровая запись] --> E[Immutable correction event]
  E --> O[Transactional outbox]
  O --> P[Targeted projector]
  P --> R[Status projection]
  R --> V[Матрица / личная карточка]
```

## Delivered behaviour

`app/services/ppr_migration_projection_outbox_worker.py` contains no scheduler and no HTTP surface. A future runtime calls `run_outbox_batch`; the worker itself:

- first returns expired `PROCESSING` leases to `RETRY` using a bounded lease timeout;
- atomically claims ready `PENDING`/`RETRY` rows with `FOR UPDATE SKIP LOCKED`, increments attempts and records the worker identity;
- recomputes only the addressed `universe_id × person_id × section_code` cell from authoritative facts, never calls `rebuild_universe`;
- ignores an old job when a newer immutable correction event already exists for that same target;
- removes a cell if its person no longer belongs to the event cohort within the active universe;
- updates the cell idempotently: an equal replay does not create a row or advance `row_version`;
- applies `CORRECTED_BY_HR` / `MANUAL_CORRECTION_PENDING_RECHECK` only for the latest event whose after source/target/binding fingerprints and policy still match current facts. `BLOCKED`, fingerprint mismatch (`STALE`), and a later participant recheck/acceptance supersede that interim status;
- marks successful work `COMPLETED`; failures are captured only as safe `PROJECTOR_INTERNAL`, retried with delay, then moved to `DEAD` at the configured attempt limit.

Claim and processing use separate short transactions. Consequently a crashed worker cannot leave a lock indefinitely, and a committed HR correction/event is never rolled back by projection failure.

## PostgreSQL verification

`tests/test_ppr_migration_projection_outbox_worker_postgres.py` uses only `TEST_DATABASE_URL` for the loopback `corpsite_test` database and cleans its own committed fixture graphs.

| Check | Result |
|---|---|
| One targeted general cell becomes `CORRECTED_BY_HR` | Pass |
| Repeat processing creates no duplicate cell | Pass |
| `RETRY` then `COMPLETED` | Pass |
| Attempt limit results in `DEAD` | Pass |
| Competing workers skip a locked job | Pass |
| Expired `PROCESSING` lease is recovered and completed | Pass |

Result: **5 passed, 0 failed**.

## Boundary for WP-005F-C

The worker has no producer connected to actual general, education or training writers. WP-005F-C must append the immutable event and outbox job inside each approved canonical-write transaction, under the existing section edit permission and org scope. It must not add a correction endpoint or a scheduler.
