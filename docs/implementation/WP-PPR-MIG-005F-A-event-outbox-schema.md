# WP-PPR-MIG-005F-A — Immutable correction-event and outbox schema

| Parameter | Value |
|---|---|
| Status | **Completed — Ready for WP-PPR-MIG-005F-B** |
| Parent | [WP-PPR-MIG-005F](WP-PPR-MIG-005F-corrections-invalidation-plan.md) |
| Depends on | [WP-005A semantics](WP-PPR-MIG-005A-status-semantics.md), [WP-005B projection](WP-PPR-MIG-005B-status-projection-read-model.md), [WP-005F design](WP-PPR-MIG-005F-corrections-invalidation-plan.md) |
| Scope | Database-enforced, PII-free immutable correction events and durable targeted-projection outbox only. |
| Out of scope | Domain writers, worker/projector, endpoints, permissions, UI, `personnel_record_events`, production deployment, commit and push. |

## 1. Delivered schema

Revision `ppr005fevent01` follows `ppr005cread01` and remains the only Alembic head.

### `ppr_section_manual_correction_events`

The append-only event row records only typed technical facts:

- generated `event_id` and unique UUID `idempotency_key`;
- technical actor, person, nullable employee context, universe and cohort identifiers;
- `section_code` limited to `general`, `education`, `training`;
- origin limited to `REVIEW_REQUIRED` or `ERROR`, with an allow-listed safe reason code;
- nullable technical Stage/participant/PMF/evidence identifiers;
- required lower-case 64-character SHA-256 before/after source, target and binding fingerprints;
- non-empty policy version, positive optimistic/source version, `occurred_at` and system `recorded_at`.

It explicitly contains no name, IIN, canonical HR value, source fragment, document, raw payload, free text, comment or exception detail. Foreign keys use `RESTRICT`; target and actor lookup indexes are present.

The database trigger rejects every `UPDATE` and `DELETE`. The event type is fixed to `PPR_SECTION_MANUAL_CORRECTED` by a check constraint. No change was made to `personnel_record_events`.

### `ppr_migration_projection_outbox`

Each correction event has one PII-free outbox job, with a unique event reference and idempotency key. It addresses exactly `universe_id × person_id × section_code` and supports job kinds `TARGETED_RECALCULATE`, `TARGETED_INVALIDATE`, and `POLICY_BATCH_INVALIDATE`.

Lifecycle values are `PENDING`, `PROCESSING`, `RETRY`, `COMPLETED`, and `DEAD`. The row stores only operational state: attempts, next eligible attempt, claim timestamp/worker, safe error code, and created/processed timestamps. Its state/claim consistency is checked by the database. A partial ready-claim index covers `next_attempt_at, outbox_id` for `PENDING` and `RETRY` work.

Outbox jobs are deliberately operationally mutable, but a trigger prevents changes to their event association, idempotency key, target address, job kind, or creation timestamp.

## 2. Transactional application helper

`append_correction_event_and_outbox(connection, request=...)` in `app/services/ppr_manual_correction_event_service.py` accepts an existing SQLAlchemy connection and never commits or begins the outer transaction.

It inserts the immutable event and its outbox row in that caller-owned unit of work. Reuse of the same idempotency key with the same complete event and job contract returns the existing IDs. A mismatched event field or job kind raises the controlled `PPR_MANUAL_CORRECTION_IDEMPOTENCY_CONFLICT` error; no duplicate is created. Rolling back the caller transaction rolls back both rows.

The helper is intentionally not wired into any manual HR write path. That atomic composition belongs to WP-005F-C after the targeted projector in WP-005F-B exists.

## 3. Downgrade policy

Downgrade to `ppr005cread01` is allowed only if both F-A tables are empty. If either correction or outbox data exists, the migration raises before dropping any object. Thus audit or queue records are never silently discarded. Empty-table downgrade removes both triggers/functions and tables; subsequent upgrade recreates them.

## 4. PostgreSQL verification

`tests/test_ppr_manual_correction_event_outbox_postgres.py` ran only through the configured loopback `TEST_DATABASE_URL` for `corpsite_test`:

| Check | Result |
|---|---|
| Valid insert; event `UPDATE`/`DELETE` rejection; no PII/raw-payload columns | Pass |
| Section, origin status/reason and SHA-256 constraints | Pass |
| Idempotent duplicate; conflicting duplicate; event/outbox rollback | Pass |
| Outbox lifecycle and immutable identity; ready-claim partial index | Pass |
| Upgrade → downgrade → upgrade; guarded downgrade with durable data; single head | Pass |

Result: **5 passed, 0 failed**.

## 5. Remaining boundary for WP-005F-B

The schema persists work but does not claim, retry, project, or expose it. WP-005F-B must provide an idempotent asynchronous worker with per-`universe × person × section` serialization and safe retry/dead-letter handling. It must not alter the committed canonical correction or immutable event when projection processing fails.
