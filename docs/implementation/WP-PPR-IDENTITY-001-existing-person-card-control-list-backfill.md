# WP-PPR-IDENTITY-001 — Формирование существующей личной карточки из подтверждённых данных контрольного списка

## Document control

| Field | Value |
|---|---|
| Type | Narrow implementation plan |
| Status | **Approved — Ready for Simplified Implementation** |
| Date | 2026-09-08 |
| Simplified Architecture Re-Review | 2026-09-08 — Approved: existing PPR command idempotency and the PPR event journal are sufficient with the ordinary additive event-catalog implementation change described in §6 |
| Authorities | [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md), [ADR-065](../adr/ADR-065-personnel-enrollment-orchestration-existing-card-repair.md), [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md), [ADR-054](../adr/ADR-054-personnel-personal-record-aggregate-model.md) |

## 1. Decision and boundary

`EXISTING_PERSON_IDENTITY_BACKFILL` is one explicit HR workflow that fills missing identity fields
of an existing Person from one exact control-list row. It is not automatic import synchronization,
and approval of education, training or another normalized fragment is never identity approval.

The motivating case remains `person_id=91`, linked to `employee_id=2`: the migration-shell Person
has only `full_name`, while the exact bound control-list row has FIO, valid IIN, DOB and provenance.
Approved education record `33493` in batch `809` cannot authorize a backfill.

The workflow may fill only blank `persons.last_name`, `first_name`, `middle_name`, `iin`, and
`birth_date` (and `full_name` only when blank). It never changes a non-empty field. Correcting
current FIO, IIN or DOB needs the separate personnel-order and supporting-document process.

### Non-goals

- No ADR-065 Employee→Person repair, Person create/adopt, Employee create, enrollment, roster promotion, assignment or reconciliation.
- No mutation on import approval; no education/training/certificate/contact/photo/order promotion; no generic Person editor or bulk backfill.
- No new failure-audit table, immutable trigger, privilege revocation or guarded downgrade.
- No production mutation without independently approved production change authority.

ADR-048 owns identity ownership, ADR-065 owns link/assignment repair, and the PMF bridge owns person-owned sections.

## 2. Access and card placement

Place **«Заполнить из контрольного списка»** in General information of
`/directory/personnel/persons/{personId}/card`, only when the card is incomplete. First rollout
requires all of: `HR_HEAD`; `PPR_IDENTITY_BACKFILL`; and active organizational scope for the linked Employee/Person.

That scoped HR_HEAD sees the full IIN in this dedicated workflow. No additional
`include_sensitive_identity_fields()` gate is required. Backend, not just UI, repeats role,
permission and organizational-scope checks in preview and apply.

A Person sees full IIN only in their own card under existing self-card authorization. Every other
context uses normal masking. The action never appears in import review, education promotion or generic Person editing.

## 3. Exact source and one preview

The backend, never the client, resolves one eligible `hr_import_rows` row. It must: belong to the
linked Employee which still points to requested Person; have non-empty normalized FIO, a valid
normalized 12-digit IIN and parseable DOB; be from `HR_CONTROL_LIST` batch status `IN_REVIEW`;
be `AUTO_MATCH`, bound to that Employee, with verifiable sheet/row and raw/normalized provenance;
and be neither removed nor pending removal. An unknown deletion/removal indication fails closed
as `SOURCE_PROVENANCE_UNVERIFIABLE`.

No row is `SOURCE_ROW_NOT_FOUND`; several rows are `SOURCE_ROW_AMBIGUOUS` until explicit
`{batch_id,row_id}` selection is server-revalidated. Rebinding, bad batch/row state, invalid
payload, superseded/stale source or unverifiable provenance blocks the workflow.

`POST /api/ppr/persons/{person_id}/identity-backfill/preview` optionally receives `{batch_id,row_id}`
and returns current values, proposal, source batch/sheet/row/provenance, conflicts, parser/policy
versions, safe snapshot hashes and short-lived opaque `preview_token`. The token binds actor, Person,
Employee, exact source, proposal, versions and authorization-relevant state. It holds no raw IIN,
raw payload or user confirmation.

## 4. One confirmation and apply

There are no `confirmed_groups`. Parser output is only a proposal: authorized HR_HEAD sees separate
surname, name and patronymic plus full IIN, then gives one confirmation:

**«Подтверждаю перенос данных»**.

`POST /api/ppr/persons/{person_id}/identity-backfill/apply` accepts only
`{preview_token, request_id, confirmed=true}`. Other identity values, source fields or confirmation
groups are rejected. `confirmed=false` does not mutate. Apply re-derives proposal and repeats
authorization, scope, exact source, Employee→Person link, target-empty, IIN format/uniqueness
and stale checks after locks.

One versioned Unicode-NFC, whitespace-normalizing parser accepts only two or three non-empty
components: surname + name, optional patronymic. Hyphen stays within one component. One or more
than three components, initials, punctuation-only components or reconstruction drift yield
`NAME_PARSE_AMBIGUOUS`. When existing `persons.full_name` is non-empty, it, source FIO and parsed
reconstruction must agree exactly after the same normalization. Existing split components are
blank or exactly equal to proposal only; disagreement is `PERSON_FULL_NAME_CONFLICT` or
`PERSON_NAME_COMPONENT_CONFLICT`.

## 5. Transaction and IIN integrity

Apply runs in one PostgreSQL transaction. It obtains the shared Gate 2 advisory IIN lock before
IIN conflict reads, then locks: linked Employee; Person; exact batch and row; candidate Person-IIN
and active Employee-IIN rows by ascending ID; then PPR metadata when present. After locks it
repeats every condition and fails closed for link/source/provenance change, stale token, non-empty
divergent target, invalid IIN/DOB, ambiguous FIO, Person or active Employee identity duplicate,
or Person/linked-Employee identity drift. Existing unique constraints are final barriers.

Gate 2's common advisory-lock / locked-reread / Employee-IIN writer port is mandatory. A matching
active linked Employee identity is adopted; if absent, exactly one active identity is inserted through
that port. The workflow never updates, expires or creates a competing identity.

Only then does the transaction fill Person fields, adopt/insert Employee identity, and materialize
PPR if its established criterion holds. Alphabet is derived, never stored, from confirmed `last_name`.
If metadata is absent, lifecycle port materializes `CREATED` and starts collection to `COLLECTING`
in the same transaction. `COLLECTING` is not a full-card completion claim. Fault rolls back Person,
identity, PPR lifecycle and event together.

## 6. Provenance, event and retry

`PERSON_IDENTITY_BACKFILLED` is a planned canonical PPR event type, not an already registered
catalog value. The implementation adds its constant/builder through the ordinary event-catalog
implementation change; no audit table is required. `personnel_record_events.event_type` is TEXT
and its repository already accepts JSONB event payloads. The event uses `record_table_name='persons'`,
`record_id=person_id`, `employee_context_id=employee_id`, and a safe payload containing only
`batch_id`, `row_id`, parser/policy versions, source snapshot fingerprint and result code. It never
contains full IIN, FIO, DOB, raw payload or SQL bind values. If event-catalog governance requires
DDL, that is one ordinary additive implementation migration, not an immutable-audit migration.

Reuse the existing PPR command idempotency mechanism: `ppr_command_executions.command_id` is the
global primary key; `begin_idempotent_command()` and `complete_idempotent_command()` in
`app/ppr/application/idempotency.py`, backed by
`SqlAlchemyCommandIdempotencyRepository`, reserve and complete it inside the caller-owned UoW.
Backfill maps API `request_id` to `command_id`, uses command type
`PERSON_IDENTITY_BACKFILL`, and fingerprints only the actor, Person/Employee IDs, preview/source
snapshot hashes, parser/policy versions and safe proposal/IIN fingerprint. Same command ID and
fingerprint returns the stored completion as exact replay; a different fingerprint or command type
raises `PprCommandIdConflictError`, mapped at the API boundary to code-only
`REQUEST_ID_REUSE_CONFLICT`. No new table is needed.

## 7. Tests and rollout

### Required PostgreSQL tests

- Orazbekov-shaped preview; education approval alone cannot authorize identity apply.
- Exact source, ambiguity, invalid batch/row/deletion/removal state and stale source/link fail closed.
- Empty migration shell fills atomically; all divergent non-empty FIO/IIN/DOB fields block.
- FIO NFC/whitespace/hyphen/two-part/three-part/initials/over-three vectors.
- IIN format, Person/active Employee identity uniqueness, drift, Gate 2 lock concurrency, rollback and Person/Employee consistency.
- Token stale behavior; exact replay is write-free; changed request fingerprint conflicts.
- `PERSON_IDENTITY_BACKFILLED` exists only after success and never exposes protected values.
- Lifecycle port reaches textual `COLLECTING`, never false full-card completion.

### Required frontend tests

- Only scoped HR_HEAD with `PPR_IDENTITY_BACKFILL` sees action and full IIN in this workflow.
- Person self-card full-IIN rule; non-self contexts remain masked.
- One preview shows current/proposed/source/conflicts and one confirmation text.
- Apply sends only token, request ID and `confirmed=true`; stale/conflict state is textual.

### Pre-implementation gates

1. **Gate 1 — completed:** run PostgreSQL IIN integrity diagnostics for target environment; deviations use their owning remediation process.
2. **Gate 2 — completed:** all runtime IIN writers use common advisory-lock and locked-reread protocol; this workflow uses its port, never direct IIN SQL.
3. Source resolver must map every deleted/pending-deletion signal explicitly and test it.
4. Verify existing request-id mechanism for replay and conflicting reuse; only if insufficient may one minimal table be designed.

First validate locally on Orazbekov-shaped case with masked evidence, then conduct separate production
readiness and change-authority review. The `h5c6d7e8f9a0` / `i6j7k8l9m0n1` clean-bootstrap
incompatibility is a separate test-environment migration issue, not an identity-backfill requirement.

## 8. Simplified architecture self-check

| Check | Result |
|---|---|
| Boundary | ADR-048 identity ownership, ADR-065 repair and PMF sections remain separate |
| Access | `HR_HEAD` + `PPR_IDENTITY_BACKFILL` + organization scope; no extra sensitive-IIN gate here |
| Confirmation | One preview and `confirmed=true`; no groups |
| Safety | Exact source, blank target, FIO consistency, IIN checks, stale checks and Gate 2 lock remain mandatory |
| Event | Ordinary canonical-event catalog addition; existing JSONB journal stores only safe source references |
| Retry | Reuse `ppr_command_executions.command_id` and its fingerprinted command-id protocol; no new table |
| PPR | Existing lifecycle port materializes `CREATED` then `COLLECTING` atomically |
| Environment | h5/i6 bootstrap blocker is explicitly outside identity backfill |

**Simplified Architecture Re-Review — 2026-09-08: Approved.** This approval authorizes
simplified implementation planning only. It does not waive the Gate 1/2 evidence, source-removal
mapping, request-id tests, or separate production change authority.
