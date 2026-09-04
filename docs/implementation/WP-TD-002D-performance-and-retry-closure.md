# WP-TD-002D — Performance and Retry Closure

## Scope

WP-TD-002D closes relationship lookup, round-trip latency and `SERIALIZABLE` retry findings in
the approval foundation. It does not add an execution endpoint, execution UI, or SQL that
physically deletes Person, Application, Employee, legacy personnel, or contact records.

The active runtime contract remains `POLICY_VERSION=WP-TD-002C/v4`.

## Bounded batch evaluation

The exact target manifest is canonicalized as sorted `(person_id, application_id)` pairs. Person
state and all applications for the selected people are loaded in two set-based queries. A third
server-owned statement passes the complete target set through one `selected` CTE and combines all
88 relationship branches with `UNION ALL`. Every output row carries both target keys and its
constant server-owned rule code. Unknown target/rule combinations fail closed.

The evaluator therefore performs exactly three SELECT statements for 1, 11 and 200 targets. It
retains each rule's category, code, canonical state digest and create/submit/approve/future-
execution flags. Per-target fingerprints remain deterministic under target or row-order changes.
Behavioral PostgreSQL coverage remains 88/88 rules, including a real related row and meaningful
same-row mutation for every rule. A permanent two-target test proves that a relationship belonging
to one target cannot contaminate the other.

Guarded disposable PostgreSQL measurements on 2026-09-04:

| Targets | SQL round trips | Cold | Warm |
|---:|---:|---:|---:|
| 1 | 3 | 0.141 s | 0.063 s |
| 11 | 3 | 0.066 s | 0.058 s |
| 200 | 3 | 0.245 s | 0.238 s |

The combined relationship statement disables JIT transaction-locally in the same protocol round
trip. This avoids disproportionate compilation time for the fixed 88-branch expression without
changing the database, role, session default, or global PostgreSQL configuration. The permanent
warm-latency guard is 2.5 seconds to allow bounded CI scheduling variance around the <2 second
runtime target.

## Relationship lookup indexes

Migration `b1c2d3e4f5a6` follows `a0b1c2d3e4f5` and adds only missing predicate-leading indexes:

* `incoming_documents`: `sender_person_id`; Employee participants `sender_employee_id` and
  `addressee_employee_id`; User participants `addressee_user_id`, `controller_user_id`,
  `created_by_user_id`, `updated_by_user_id`, `closed_by_user_id`, `cancelled_by_user_id`,
  `transferred_by_user_id`, and `external_recipient_user_id`;
* employee/import lookups: `employees_import_stage.employee_id`, `hr_import_rows.employee_id`,
  `hr_baseline_entries.employee_id`, and `hr_monthly_reference_entries.employee_id`;
* migration/person lookups: `personnel_migration_runs.person_id`,
  `personnel_migration_runs.employee_context_id`, and `persons.merged_into_person_id`;
* order lookups: `personnel_orders.signed_by_employee_id`,
  `operational_order_signing_attestations.actor_employee_id`, and
  `personnel_order_item_bases.subject_employee_id`;
* onboarding/termination lookups: `employee_onboarding_notifications.onboarding_id`,
  `employee_onboarding_task_audit.onboarding_id`, and
  `employee_termination_record_audit.termination_record_id`;
* linkage/security lookups: `user_linkage_review_decisions.proposed_employee_id`,
  `access_grants(target_type, target_id)`, and
  `personnel_visibility_assignments(target_user_id)`.

Catalog regression verifies table identity and exact key-column order on upgrade, absence after
downgrade to `a0`, and restoration on re-upgrade. Existing suitable PK, unique, FK-supporting or
predicate-leading indexes are not duplicated. The full access-grant and visibility indexes are
intentional companions to existing active-only partial indexes because retained/inactive rows are
part of the relationship contract.

## Transaction and retry contract

Submit and approve execute at PostgreSQL `SERIALIZABLE` isolation without blanket operational-
table locks. SQLSTATE `40001` causes a bounded retry with a new transaction. The maximum is three
attempts; exhaustion returns `TD_SERIALIZATION_RETRY_EXHAUSTED`. Tests inject deterministic
serialization failures and prove rollback of partial request status, decision and history writes
before either a successful second attempt or terminal exhaustion. Future execution must perform
its own complete drift evaluation immediately before any destructive work.

## Guard and safety regression

An isolated `.env`-only pytest integration test proves that the main database identity is resolved
without mutating the parent environment, a matching target is rejected without revealing its
credential, and the guard terminates before project conftest import or any DDL/DML boundary.
Legacy deletion routes continue to return HTTP 410 before database/service access. Full IIN remains
unconditionally masked, and no execution surface or physical target-deletion SQL is introduced.
