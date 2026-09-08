# WP-PPR-IDENTITY-001 — Формирование существующей личной карточки из подтверждённых данных контрольного списка

## Document control

| Field | Value |
|---|---|
| Type | Narrow implementation plan / architecture decision package |
| Status | **Approved — Ready for Implementation Planning** |
| Date | 2026-09-08 |
| Final Architecture Re-Review | 2026-09-08 — Approved: AR-ID-01…AR-ID-07 closed; implementation remains gated by the mandatory prerequisites in §8 |
| ADR number | Not assigned: `ADR-066` already exists as an uncommitted unrelated document; it is not occupied or changed by this work |
| Authorities | [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md), [ADR-065](../adr/ADR-065-personnel-enrollment-orchestration-existing-card-repair.md), [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md), [ADR-054](../adr/ADR-054-personnel-personal-record-aggregate-model.md), [ADR-059](../adr/ADR-059-employee-centric-import-review.md) |

## 1. Decision

Introduce `EXISTING_PERSON_IDENTITY_BACKFILL`: one explicit HR workflow that fills missing
identity fields of an existing Person from one exact control-list row. It is not an automatic
import synchronization and does not change the ownership established by ADR-048.

The motivating local shape is `person_id=91`, linked to `employee_id=2`, where the Person is a
`migration-shell`: `persons.full_name` exists, while `last_name`, `first_name`, `middle_name`,
`iin`, and `birth_date` are NULL. A linked control-list row contains full name, valid IIN, DOB,
Employee binding, and source provenance. PPR metadata is absent, therefore the card is
`NOT_MATERIALIZED`.

Approval of a normalized education/training/certificate fragment is never approval of identity
data in its parent `hr_import_rows.normalized_payload`. In particular, approved education record
`33493` in batch `809` must not authorize this operation.

### Scope

For one existing active non-merged Person and its linked eligible Employee, the workflow:

1. finds and locks one exact bound `hr_import_rows` source row;
2. previews missing Person values and immutable source provenance;
3. requires independent HR confirmation of FIO, IIN, and DOB;
4. atomically fills only currently NULL/blank `last_name`, `first_name`, `middle_name`, `iin`,
   and `birth_date` (and `full_name` only when blank);
5. records immutable audit/provenance and materializes PPR metadata when the criterion holds;
6. derives, but never stores, alphabet from confirmed surname.

### Non-goals and authority boundary

- No Employee→Person repair, Person create/adopt, Employee creation, assignment, C2 command,
  or reconciliation: ADR-048, ADR-065 and ADR-043 remain authoritative.
- No education/training/certificate/document/contact/photo/order promotion. PMF and
  `personnel_migration_ppr_bridge.py` remain the path for person-owned section records.
- No mutation during import approval, row review, roster promotion, or ordinary card opening.
- No overwrite or correction of a non-empty Person field. Conflicting FIO/IIN/DOB needs a
  separate documented personnel/document process; this command fails closed.
- No generic direct Person editor, bulk backfill, or production mutation under this document.

## 2. Roles, UI and permissions

Use one new explicit permission: `PPR_IDENTITY_BACKFILL`. Ordinary import review does not imply
it. For the first rollout its grant package is assigned only to the `HR_HEAD` role. The server
must enforce it and the established organizational scope for the linked Employee/Person; a
client-side hidden action is not authorization. Four-eyes is not required for MVP because this
workflow fills only empty canonical Person fields and rejects every non-empty target value.

There is no standalone current permission named “view full IIN”. The exact existing sensitive
identity gate is `include_sensitive_identity_fields()` in
`app/services/ppr_query_access_service.py`: privileged users or
`evaluate_personnel_admin_access()`, which currently derives from the access-grant codes
`SYSADMIN_CABINET`, `ACCESS_ADMIN`, or `HR_ENROLLMENT_MANAGER`. The exact sensitive-IIN
requirement is therefore the existing single predicate
`include_sensitive_identity_fields(user_ctx) == true`, not an open-ended "equivalent" role.
MVP requires all three conditions to confirm `IIN` or invoke apply:
`PPR_IDENTITY_BACKFILL`, that exact existing predicate, and valid organizational scope. The
first rollout gives the combined `PPR_IDENTITY_BACKFILL` + `HR_ENROLLMENT_MANAGER` package only
to `HR_HEAD`; the predicate's currently enumerated privileged/access-grant alternatives remain
server-defined by the existing function. A user for whom the predicate is false may open a
masked preview but has `apply_available=false`, cannot select `IIN`, and cannot call apply
successfully.

| Permission / policy | Allows |
|---|---|
| `PPR_IDENTITY_BACKFILL` | Enables this workflow for `HR_HEAD` within HR scope; never sufficient alone for apply |
| `include_sensitive_identity_fields(user_ctx)` | Existing full-IIN gate, currently based on privileged scope or `SYSADMIN_CABINET`, `ACCESS_ADMIN`, or `HR_ENROLLMENT_MANAGER`; required with backfill permission and scope for `IIN` confirmation/apply |

Place **«Заполнить из контрольного списка»** only in General information on
`/directory/personnel/persons/{personId}/card`, when an authorized user sees an incomplete
card with covered fields missing. It is absent from import review, education promotion and a
generic Person editor.

The existing read route remains `PprQueryApplicationService` →
`PprCompositeReadOrchestrator` → `PprGeneralResponse`; the new flow uses a dedicated API, not
generic PATCH. `PprCardGeneralSection` continues to compute alphabet via
`deriveIntakeSurnameAlphabet(g.last_name)`.

## 3. Source selection and preview

### 3.1 Exact source row

The server selects a candidate from `hr_import_rows`; the client never supplies values. An
eligible row satisfies all of the following:

1. `row.employee_id = employees.employee_id` and `employees.person_id = requested person_id`;
2. non-empty `normalized_payload.full_name`, valid exact 12-digit
   `normalized_payload.iin`, and parseable `normalized_payload.birth_date`;
3. `hr_import_batches.source_type='HR_CONTROL_LIST'` and batch status exactly `IN_REVIEW`.
   The real import enum also contains `UPLOADED`, `PARSED`, `APPLY_PENDING`, `APPLIED`,
   `PARTIALLY_APPLIED`, `FAILED`, and `CANCELLED`; every value except `IN_REVIEW` is blocked;
4. row `match_status='AUTO_MATCH'`, no `INVALID_DATA`/`SKIPPED` match state, and metadata
   `row_type='EMPLOYEE'`, `iin_valid=true`, `employee_binding_status='bound'` for this exact
   Employee. A row with `profile_status` other than `active`, profile deletion/removal marker,
   unresolved removal decision, missing `source_sheet`/`source_row_number`, or unverifiable
   raw/normalized payload provenance is ineligible; and
5. exactly one candidate, or an explicit `{batch_id,row_id}` selection after the server reports
   ambiguity.

Zero candidates is `SOURCE_ROW_NOT_FOUND`; several unselected candidates are
`SOURCE_ROW_AMBIGUOUS`. The source relation is checked again under locks. For the local example
the factual candidate is batch `809`, row `19003`; this plan does not authorize applying it.

The current `hr_import_rows` model has no row lifecycle/deleted enum; physical deletion is by
batch cascade and diff-removal is represented in adjacent review/removal services. Before this
workflow is implemented, its source resolver must map every existing deletion/removal signal to
one of the explicit blockers below. Absence of such a verified mapping is
`SOURCE_PROVENANCE_UNVERIFIABLE`, not an implicit allow.

### 3.2 Immutable preview snapshot

`POST /api/ppr/persons/{person_id}/identity-backfill/preview`

Input is optional exact `{batch_id,row_id}`. Output has current canonical values, proposed
values, field states, source sheet/row/batch, conflicts, and opaque short-lived
`identity-backfill-preview-v1` token. The token is created **before** user confirmation and is
bound to actor, applicable permissions, Person, Employee, selected source, proposal and the
exact groups available for later confirmation; it is not bound to `confirmed_groups`:

```text
{ person_id, employee_id, batch_id, row_id, source_sheet, source_row_number,
  batch_imported_at, batch_import_code,
  normalized_payload_sha256, profile_override_sha256_or_null,
  source_version:{row_updated_at,batch_status,row_employee_id},
  person_version:{updated_at,identity_tuple_hash},
  employee_version:{updated_at,person_id},
  candidate:{full_name,parsed_name,birth_date,iin_fingerprint},
  available_confirmation_groups, parser_version, policy_version }
```

Raw IIN is not put in token, error, log or audit; an HMAC/fingerprint and last four digits are
used for comparisons and safe display.

### 3.3 Preview/apply contract

Preview returns every field as `FILLABLE`, `ALREADY_EQUAL`, `CONFLICT_NONEMPTY`,
`INVALID_SOURCE`, or `MISSING_SOURCE`, plus an explicit notice that normalized-record approval
is irrelevant to identity authorization.

The confirmation screen requires separate confirmation groups:

1. `NAME` — source FIO and its displayed surname/name/patronymic decomposition;
2. `IIN`; and
3. `BIRTH_DATE`.

`POST /api/ppr/persons/{person_id}/identity-backfill/apply` accepts only
`{preview_token, request_id, confirmed_groups}`. The server re-derives values; it never accepts
raw identity values in apply. `confirmed_groups` is supplied only here and must exactly equal
the token's `available_confirmation_groups`; apply repeats both permissions, scope and snapshot
checks after locks. An IIN-bearing preview can be masked, but it cannot be confirmed or applied
without the full-IIN gate above.

### 3.4 FIO parser

Use one versioned Unicode-NFC parser in preview and apply. It closes whitespace and supports
exactly two or three non-empty components in the initial scope:

```text
last_name = component[0]
first_name = component[1]
middle_name = component[2] when present
```

Hyphenated parts are one component. The fail-closed component policy is:

| Components after NFC/whitespace normalization | Proposal | Apply |
|---|---|---|
| Two | surname + name; `middle_name=NULL` proposal | Only after `HR_HEAD` confirms both displayed parts and absence of patronymic |
| Three | surname + name + patronymic | Only after `HR_HEAD` confirms all displayed parts |
| One, more than three, empty/punctuation-only, initials, or reconstruction drift | `NAME_PARSE_AMBIGUOUS` | Never |

A hyphen within one normalized component is retained, never split. The parser creates only a
proposal: `HR_HEAD` sees the three separate target values and explicitly confirms them before
apply. No heuristic fallback writes. Future multi-part naming support requires a new parser
version and reviewed vectors.

## 4. Conflict matrix

| Locked condition | Result | Apply |
|---|---|---|
| Person missing/merged/inactive or Employee→Person changed | `PERSON_OR_EMPLOYEE_LINK_CONFLICT` | No |
| Missing/ambiguous source row | `SOURCE_ROW_NOT_FOUND` / `SOURCE_ROW_AMBIGUOUS` | No |
| Batch not `IN_REVIEW` | `SOURCE_BATCH_STATUS_NOT_ALLOWED` | No |
| Row match/profile/binding/removal state not allowed | `SOURCE_ROW_MATCH_STATUS_NOT_ALLOWED`, `SOURCE_ROW_PROFILE_NOT_ACTIVE`, `SOURCE_ROW_BINDING_CONFLICT`, or `SOURCE_ROW_REMOVAL_PENDING` | No |
| Missing/changed/unverifiable source provenance or superseded snapshot | `SOURCE_PROVENANCE_UNVERIFIABLE` / `SOURCE_SNAPSHOT_SUPERSEDED` | No |
| Invalid/masked source IIN, invalid DOB, ambiguous FIO | field-specific invalid-source result | No |
| Non-empty normalized `persons.full_name` differs from source full name or reconstruction | `PERSON_FULL_NAME_CONFLICT` | No |
| Existing split FIO component differs from its proposal, or components reconstruct a different full name | `PERSON_NAME_COMPONENT_CONFLICT` | No |
| Targeted Person field non-empty and different | `PERSON_FIELD_CONFLICT` | No, correction workflow only |
| Targeted field already equal | `ALREADY_APPLIED` for field | No overwrite |
| IIN on another non-merged Person | `PERSON_IIN_CONFLICT` | No |
| IIN on another active `employee_identities` row | `EMPLOYEE_IIN_CONFLICT` | No |
| Existing Person IIN and linked active Employee IIN differ | `IDENTITY_DRIFT_CONFLICT` | No |
| Batch/row/payload/override/binding/Person/Employee snapshot changed | `STALE_PREVIEW` | No; preview again |
| Same completed request and snapshot fingerprint | Stored replay | Yes; no new writes |
| Same `request_id`, different fingerprint | `REQUEST_ID_REUSE_CONFLICT` | No |

The review state of `hr_import_normalized_records` is not an identity approval predicate. It
may be shown only as context.

Name integrity is a single locked predicate. Normalize Person `full_name`, source `full_name`,
and the parser reconstruction with the same NFC/closed-whitespace profile. A non-empty Person
full name must equal both source and reconstruction exactly after that profile. Each pre-existing
split component may be NULL/blank or exactly equal to its proposal; it is never changed. Before
write, the final effective tuple (`full_name`, `last_name`, `first_name`, `middle_name`) must
reconstruct to the same normalized full name. This prevents a migration shell from acquiring
split components inconsistent with its already canonical display name.

## 5. Transaction, provenance and idempotency

Apply uses one caller-owned PostgreSQL transaction. Lock order is fixed:

1. backfill operation/idempotency record by `request_id`;
2. transaction-scoped advisory IIN lock: execute
   `SELECT pg_advisory_xact_lock(hashtextextended('PPR_IDENTITY_IIN:v1:' || :normalized_iin, 0))`.
   The domain-separated deterministic key is derived from the normalized IIN and is required
   before any Person/Employee-IIN lookup, serializing the absent-row case;
3. linked `employees` row (`FOR UPDATE`);
4. target `persons` row (`FOR UPDATE`);
5. exact `hr_import_batches` and `hr_import_rows` rows (`FOR UPDATE`);
6. candidate Person-IIN and active Employee-IIN identity rows in ascending ID order
   (`FOR UPDATE`); and
7. `personnel_record_metadata`, when present (`FOR UPDATE`).

After locking, repeat authorization, scope, relationship, source hash/version, parser,
full/split-name integrity, target-empty, IIN uniqueness, Employee identity state and
preview-token checks. Execute one conditional Person update guarded by expected empty fields.
No path can overwrite a non-empty identity field.

The advisory lock is a new shared IIN writer protocol; ADR-048's existing resolver is read-only,
and current roster-promotion/reconciliation helpers insert `employee_identities` without this
cross-writer lock. Before activation, all IIN writers — ADR-048 enrollment writer, roster
promotion (`_insert_employee_identity`), identity reconciliation
(`_insert_employee_identity_iin`), and this service — must call one shared
`ensure_employee_iin_identity_tx`/IIN-lock port in the order above. A migration must retain
the existing DB uniqueness constraints `uq_persons_iin_active` and
`uq_employee_identities_iin_active`, and deployment diagnostics must fail rollout if existing
active duplicates or invalid IINs exist. The lock prevents a missing-row race; the constraints
remain the final integrity barrier.

Employee identity is mandatory, not optional. `employee_identities` is the existing operational
IIN authority used by import binding and ADR-065. After the IIN lock, the operation must: adopt
exactly one matching active linked-Employee IIN if present; insert exactly one active primary
IIN through the shared port if absent; or fail `EMPLOYEE_IIN_CONFLICT` if a different active IIN
exists. It must never update/expire an existing active IIN or create a second competing writer.
The Person IIN, Employee IIN identity ID/action (`ADOPT` or `INSERT`), and its expected state
are part of the operation fingerprint, audit and idempotent result.

| IIN writer / path | Required shared protocol before activation |
|---|---|
| ADR-048 enrollment Create-or-Link implementation | Advisory IIN lock → locked Person/Employee identity reread → common Employee-IIN ensure port → existing unique constraints |
| Roster promotion `_insert_employee_identity` | Replace local insert with the common ensure port and same lock order |
| Identity reconciliation `_insert_employee_identity_iin` | Replace local insert with the common ensure port and same lock order |
| `EXISTING_PERSON_IDENTITY_BACKFILL` | Same port; no independent identity insert SQL |

The ADR-048 resolver currently in `adr048_person_resolution_service.py` is read-only and is not
an identity writer to reuse; the common transactional writer must be extracted from the existing
roster-promotion/reconciliation insert behavior rather than duplicating it.

The later schema implementation must add immutable `person_identity_backfill_operations`, keyed
by `request_id` and request fingerprint. Each row stores `person_id`, `employee_id`, `batch_id`,
`row_id`, source snapshot version and hashes, Person/Employee expected versions, parser/policy
versions, selected confirmation groups, safe hashes/fingerprints (never raw protected IIN),
initiator, created/finalized timestamps, outcome/result and replay data. A separate immutable
provenance projection/table is optional only if it is a one-to-one operation detail; it must not
split the mandatory audit facts above across an unverifiable join.

Write one `personnel_record_events` event `PERSON_IDENTITY_BACKFILLED`, referencing operation
and provenance IDs but containing no raw protected values. Successful Person update,
provenance, event, PPR decision and final idempotency result commit together. Fault or stale
state rolls back all of them.

Failure audit is deliberately outside that participating transaction. After rollback, a separate
safe append-only transaction writes `person_identity_backfill_failure_audit` with request ID,
fingerprint, actor ID, Person/Employee IDs, batch/row IDs when known, error/stage code,
timestamp, correlation ID and safe source/person/IIN fingerprints. It contains no raw IIN,
full name, DOB, proposed values, SQL bind values, or partial business-state IDs. A technical
failure does not finalize a success operation: retry is permitted only with the same request ID
and exactly the same fingerprint; reuse with another fingerprint is permanently rejected. The
failure audit itself is best-effort but must not mask the business failure or create Person/PPR
state.

## 6. PPR materialization

This workflow never calls the education/training PMF bridge. After identity validation it may
call a dedicated caller-owned PPR lifecycle port, not a direct metadata writer.

Initial criterion for identity-card materialization:

```text
active non-merged Person
AND non-empty last_name and first_name
AND non-empty valid iin and birth_date
AND one linked eligible Employee
```

`COLLECTING` is already a valid persisted lifecycle state in
`app/ppr/domain/models.py`; `validate_start_collection()` in
`app/ppr/domain/lifecycle_transitions.py` permits `CREATED → COLLECTING` and idempotent
`COLLECTING → COLLECTING`. However, `PprLifecycleApplicationService.materialize_ppr()` creates
the envelope with the existing initial state `CREATED`. Therefore, when metadata is absent the
transaction must call the existing materialize command and then the existing StartCollection
transition through a caller-owned participating UoW, yielding `COLLECTING`; it must not write
`personnel_record_metadata` directly or invent a new initial state. Derive HR relationship only
from existing Employment authority. When metadata exists, preserve state and use the transition
guard. This is not dossier completeness, hire readiness, or education migration.

## 7. Future implementation surfaces

| Layer | Existing reference | Planned addition |
|---|---|---|
| API | `app/api/ppr_router.py`, `app/api/ppr_schemas.py` | Dedicated preview/apply contracts; no generic Person PATCH |
| Person/PPR read | `app/ppr/read/query_service.py`, `app/ppr/read/orchestrator.py`, `app/ppr/infrastructure/person_repository.py` | Reuse card state; new transactional identity-backfill service/repository |
| Import | `hr_import_rows`, `app/services/hr_import_normalized_record_service.py` | Locked snapshot resolver; no normalized-review approval gate |
| PPR lifecycle | `app/ppr/application/lifecycle_service.py`, `personnel_record_metadata` | Caller-owned materialization port with lifecycle invariants |
| UI | `PprPersonalCardPageClient.tsx`, `PprCardGeneralSection.tsx`, `pprQueryApi.client.ts` | Conditional action, preview dialog, confirmations, safe masking |

## 8. Test and rollout matrix

### PostgreSQL/integration

| Case | Required proof |
|---|---|
| Orazbekov-shaped fixture | Exact bound-row preview; education approval alone cannot apply identity |
| Empty migration shell | One atomic fill, provenance, event, PPR metadata |
| Existing full/split FIO | Exact normalized source/reconstruction equality permits empty-field fill; any inconsistent full or component value blocks |
| Duplicate Person IIN, active Employee IIN, identity drift | Shared IIN lock plus constraints reject without writes; linked Employee identity is adopt-or-insert only |
| Two simultaneous Persons, same absent new IIN | One wins advisory lock/constraints; other returns uniqueness conflict; never two active identities |
| Source states | Each non-allowlisted batch, invalid/skipped match, inactive/deleted/removal-pending profile, reassigned row, superseded/unverifiable provenance returns its exact error |
| Source reassignment/payload override/hash or Person/Employee change after preview | `STALE_PREVIEW`, no writes |
| FIO parser vectors | NFC, whitespace, hyphen, 2/3 parts, initials, 4 parts, malformed values |
| Concurrent apply and retries | Exactly one commit; exact replay; request reuse rejected |
| Fault injection after every success-path write | Participating transaction has no orphan metadata/event/provenance/operation result; separate failure audit has safe code/fingerprint only |
| RBAC/logging | `HR_HEAD`, `PPR_IDENTITY_BACKFILL`, `include_sensitive_identity_fields(user_ctx) == true`, and scope required inside apply; no raw IIN in errors/audit/logs |
| Lifecycle | Existing Materialize then StartCollection produces `COLLECTING`; no direct metadata write or false `READY` |

### Frontend

- A non-sensitive user sees a masked preview only; apply and IIN confirmation controls are absent
  or disabled with a textual access explanation.
- The action/apply is visible only to `HR_HEAD` with `PPR_IDENTITY_BACKFILL`,
  `include_sensitive_identity_fields(user_ctx) == true`, and valid scope; backend repeats all
  gates even if the UI state is stale.
- Preview displays current/proposed/provenance/conflict before confirmation.
- Three independent confirmations are required; proposed values are not editable in apply.
- IIN is masked without sensitive permission in dialogs, toasts, copied text and errors.
- Stale/conflict forces re-preview; replay is rendered as the stored success. The UI distinguishes
  `PERSON_FULL_NAME_CONFLICT`, source-state blockers and IIN access denial by text, not colour.
- On success the card shows split FIO, IIN, DOB, derived alphabet and textual state
  «Сбор сведений»/`COLLECTING`; it never claims full-card completion or education migration.

### Rollout

#### Mandatory pre-implementation gates

Implementation work and feature-flag activation are blocked until all of these gates have
evidence from the reviewed implementation branch:

1. **IIN duplicate diagnostics:** a PostgreSQL diagnostic proves there are no active duplicate
   normalized IINs, and no invalid IINs, under the existing Person and active Employee-identity
   uniqueness domains; violations require cleanup through their owning process before rollout.
2. **One IIN-writer protocol:** every listed writer — the ADR-048 enrollment Create-or-Link
   implementation, roster promotion, identity reconciliation, and this workflow — uses the
   same advisory-lock / locked-reread / `ensure_employee_iin_identity_tx` protocol and lock
   order. No legacy local identity insert remains on an activation path.
3. **Immutable audit schema:** migrations for both
   `person_identity_backfill_operations` and
   `person_identity_backfill_failure_audit` are reviewed, deployed and covered by rollback and
   idempotency tests before the feature can be enabled.
4. **Fail-closed removal signal:** the source resolver has an explicit, tested mapping for each
   existing deleted and pending-deletion/removal indication. An unrecognized or absent mapping
   returns `SOURCE_PROVENANCE_UNVERIFIABLE`; it can never admit the row.

1. Architecture review approves authority boundary, permissions, parser, audit model and PPR
   lifecycle port.
2. Implement behind a disabled feature flag; run unit, PostgreSQL concurrency/fault, and UI
   suites on a clean reviewed branch.
3. Verify once locally with the Orazbekov-shaped record and authorized operator, preserving
   only masked evidence. This is not a bulk repair.
4. Produce a separate deployment/readiness review.
5. Request a separate production verification only after that review, with an explicitly
   selected record, operator confirmation and production change authority.

## 9. Architecture self-check

| Check | Result |
|---|---|
| ADR boundaries | Pass: ADR-048 owns Person identity, ADR-065 link/assignment repair is excluded, PMF education is excluded, and non-empty correction requires document plus personnel order |
| RBAC and scope | Pass: `PPR_IDENTITY_BACKFILL` + `include_sensitive_identity_fields(user_ctx) == true` + server-side scope; first grant package is `HR_HEAD` only |
| IIN safety | Pass: masked preview without sensitive gate; IIN confirmation/apply requires full-IIN gate and repeats all authorization after locks |
| Full/split FIO integrity | Pass: non-empty full name must equal source and reconstructed proposal; pre-existing components must be equal or empty |
| SoT and provenance | Pass: control list is locked evidence, `persons` remains SoT, and one immutable operations row holds complete source snapshot/audit facts |
| Single source row / multiple batches | Pass: `IN_REVIEW` control-list batch plus bound/valid row allowlist; ambiguity, deletion/removal and unverifiable provenance block; batch/row/hashes are token-bound |
| Preview/apply and stale state | Pass: pre-confirmation token fixes proposal and available groups; apply supplies exact groups and rereads permissions/snapshot after locks |
| IIN absent-row race / writer matrix | Pass: common domain-separated advisory IIN lock precedes rereads; Person and Employee unique indexes remain final barriers; every IIN writer must adopt the common port |
| Employee identity authority | Pass: linked active Employee IIN is mandatory and is exact-adopt-or-insert only through the common writer port |
| Locks, transaction, rollback | Pass: participating transaction has complete atomic business outcome; post-rollback failure audit is separate, safe and contains no partial business state |
| Idempotency | Pass: `request_id` plus exact snapshot fingerprint replays; changed reuse blocks |
| PPR lifecycle | Pass: code confirms `COLLECTING` is valid; materialize-to-`CREATED` then StartCollection is required in the same participating transaction |
| PostgreSQL and frontend tests | Pass in plan: matrices cover concurrency/faults/RBAC and text-visible state rather than color only |

**Final Architecture Re-Review — 2026-09-08: Approved.** No architectural contradiction remains
in the documented design. Approval authorizes implementation planning only; it does not waive
the mandatory pre-implementation gates in §8. Schema, lifecycle port, permission registration
and tests remain future implementation work, not evidence that `COLLECTING` is unsupported.

### Architecture review findings closure

| Finding | Closure |
|---|---|
| AR-ID-01 | Exact current full-IIN predicate identified; `PPR_IDENTITY_BACKFILL` + `include_sensitive_identity_fields(user_ctx) == true` + scope are mandatory for IIN confirmation/apply and rechecked inside apply |
| AR-ID-02 | Locked normalized `persons.full_name`, source name and parser reconstruction must agree; existing components are equal-or-empty only |
| AR-ID-03 | Domain-separated transaction advisory IIN lock, two existing active-IIN unique indexes, duplicate preflight, and mandatory shared writer matrix close absent-row races |
| AR-ID-04 | Participating business transaction fully rolls back; distinct post-rollback safe failure audit contains identifiers/codes/fingerprints only and request reuse is fingerprint-bound |
| AR-ID-05 | Active linked Employee IIN is mandatory: exact adopt or common-port insert, never a competing writer or overwrite |
| AR-ID-06 | `IN_REVIEW` batch plus bound/valid provenance allowlist and exact source-state errors close batch/row/removal/snapshot ambiguity; education approval remains irrelevant |
| AR-ID-07 | Token is created before confirmation and fixes proposal/available groups; `confirmed_groups` appear only in apply and must exactly match after locked rereads |

## 10. Open architecture questions

1. Should the immutable operations table be implemented as a specialized table (recommended for
   the narrow MVP) or as a PMF identity plugin? Either choice must preserve the complete
   operation row and keep normal import approval non-executable.
2. Which legally sufficient document and personnel-order variant must the separate correction
   workflow require for a non-empty FIO, IIN or DOB conflict?
3. Is the strict initial 2–3 component FIO policy sufficient for all supported naming rules?
   Recommendation: launch only with this fail-closed policy and add other patterns by a
   versioned, independently reviewed parser.
