# WP-TD-002C — Batched Relationship Evaluation

## Scope

WP-TD-002C closes the remaining foundation-review findings without adding an execution
endpoint, execution UI, or physical deletion of Person, Application, Employee, legacy
personnel, or contact data.

## Batch architecture

The server freezes the exact `(person_id, application_id)` manifest and loads Person and all
Person applications in two set-based queries. It then supplies every selected target, including
that Person's complete application-id set, to a server-owned PostgreSQL CTE. Each of the 88
relationship branches are combined by WP-TD-002D into one bounded `UNION ALL` statement. The
result is keyed back to the selected target and retains the rule code, category, count, canonical
state digest and the contract's create/submit/approve/future-execution flags.

Each target still receives its own deterministic fingerprint. Row states are hashed as canonical
JSON; row hashes, relationship codes and target tuples are sorted before aggregate hashing.
Raw relationship rows and identity payloads are never persisted in the snapshot.

## Query budget

WP-TD-002C originally established a constant 90-SELECT ceiling. WP-TD-002D supersedes that
implementation with three SELECT statements: two base-state reads and one combined relationship
statement containing all 88 rule branches. The count remains three for 1, 11 and 200 targets.
Preview adds one bounded manifest selection query outside the relationship evaluator.

## Transactional consistency

Submit and approval remain `SERIALIZABLE` transactions with a bounded three-attempt retry for
PostgreSQL serialization failures. Blanket `LOCK TABLE ... IN SHARE MODE` locks on operational
tables are removed. Every command evaluates one transactionally consistent MVCC snapshot;
changes committed before that snapshot are observed as drift, and serialization conflicts are
retried. Any observed target, relationship or provenance drift produces
`REAPPROVAL_REQUIRED`. A future execution work package must repeat the complete batch evaluation
immediately before execution.

## Security closure

The test guard resolves the main URL from process configuration or reads `.env` without mutating
the process environment, redacts URLs from errors, validates the test suffix and loopback host,
compares main and target identities, and checks `current_database()` before test DDL/DML.

Until a dedicated sensitive-identity permission exists, `safe_identity` has no full-IIN option
and always masks a valid twelve-digit IIN. Immutable command projections are protected by a
recursive JSONB key check at every object/array depth.

## Behavioral coverage

The PostgreSQL matrix suite creates a real linked row for every one of the 88 rules and verifies
detection, expected category, non-empty digest, stage admissibility and fingerprint change after
a meaningful same-row update. Separate tests cover the constant query budget, provenance
physical disappearance across create→submit and submit→approve, nested PII rejection, and the
database/service-free HTTP 410 boundary of both legacy endpoints.

No UI, execution route or target-deletion SQL is introduced by WP-TD-002C.
