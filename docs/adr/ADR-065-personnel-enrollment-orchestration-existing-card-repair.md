# ADR-065 — Personnel enrollment orchestration and existing-card repair protocol

## Status

**Approved — Ready for Implementation**

**READY FOR IMPLEMENTATION: YES**

| Field | Value |
|---|---|
| Date | 2026-08-07 |
| Revision | R14 — Architecture Review approved the R13 contracts for implementation |
| Extends | [ADR-043 Phase C2](./ADR-043-phase-c2-person-assignment-sync.md), [ADR-048](./ADR-048-person-ownership-identity-creation-policy.md) |
| Does not supersede | ADR-042, ADR-043, ADR-048 |
| Scope | Application orchestration for complete Phase 3I enrollment and existing-card repair |

---

## 1. Authority boundary

Phase 3I currently creates import binding, `Employee`, `employee_identity`, operational
events/audit, and `Contact`, but does not complete the ADR-048 Person link or canonical C2
assignment lifecycle. This ADR adds application orchestration without moving authority:

1. **ADR-048 remains the only authority for enrollment Person Create-or-Link.** The
   orchestrator calls its transactional port and never copies its matching rules.
2. **ADR-043/C2 remains the only authority for `person_assignments`.** The orchestrator
   calls strict C2 commands and never writes `person_assignments` directly.
3. **Reconciliation is projection only:** assignment → legacy Employee snapshot. It does
   not create, close, void, or interpret assignments.
4. **Phase 3I remains an enrollment flow, not assignment authority.** It supplies a
   separately confirmed assignment intent to C2.
5. **The orchestrator owns coordination only:** authorization, preview, idempotency,
   stale-state verification, transaction boundary, lock order, and domain-port ordering.

### 1.1. ADR-048 INV-11

`Person Create-or-Link` and `C2 Assignment Command` are separate commands with separate
preconditions, evidence, results, and events. Person Shell creation never creates or
triggers an assignment. A Shell may exist without an assignment outside an operation
that claims successful active enrollment.

`ACTIVE_ENROLLMENT` is a composite application command. It invokes C2 only when the
request contains an explicit, authorized, complete, separately evidenced assignment
intent. Complete enrollment therefore does not reinterpret Shell creation and preserves
ADR-048 INV-11.

---

## 2. Closed command vocabulary and complete normative outcome matrix

The operation enum is closed: `ACTIVE_ENROLLMENT | EXISTING_CARD_REPAIR`. The final mode
enum is also closed and has no NULL, empty, alias, or implementation-defined value:

```text
ENROLL_NEW_ACTIVE
VERIFY_CONSISTENT
LINK_AND_OPEN_MISSING_ASSIGNMENT
LINK_ONLY
OPEN_MISSING_ASSIGNMENT
CORRECT_ERRONEOUS_RECORD
CORRECT_ERRONEOUS_RECORD_WITH_REPLACEMENT
COMPLETE_REAL_LIFECYCLE_EPISODE
COMPLETE_REAL_LIFECYCLE_EPISODE_WITH_SUCCESSOR
TRANSFER
POSITION_CHANGE
TRANSFER_AND_POSITION_CHANGE
ASSIGNMENT_TERMS_CHANGE
PRESERVE_FUTURE_ASSIGNMENT
TRANSITION_FUTURE_UNCHANGED_ASSIGNMENT
TRANSITION_FUTURE_TRANSFER
TRANSITION_FUTURE_POSITION_CHANGE
TRANSITION_FUTURE_TRANSFER_AND_POSITION_CHANGE
TRANSITION_FUTURE_ASSIGNMENT_TERMS_CHANGE
```

`ACTIVE_ENROLLMENT` accepts only `ENROLL_NEW_ACTIVE` and `VERIFY_CONSISTENT`.
`EXISTING_CARD_REPAIR` accepts every other mode and `VERIFY_CONSISTENT`. Every other
operation/mode pair returns `INVALID_OPERATION_MODE` before state classification.

After common errors are excluded, locked request-relative state is classified into
exactly one mutually exclusive class below. “Terms” means `rate` or `employment_type`;
a terms-change class wins over every org/position delta class. With terms unchanged,
org/position deltas select exactly one transfer/position/combined class.

```text
S_ENROLLABLE_NO_EMPLOYEE             S_CONSISTENT
S_LINK_MISSING_PERSON                S_LINK_MISSING_PERSON_ABSENT
S_NO_NONVOID_PRIMARY                 S_ERRONEOUS_VOID_ONLY
S_ERRONEOUS_WITH_REPLACEMENT         S_COMPLETE_NO_SUCCESSOR
S_COMPLETE_UNCHANGED_SUCCESSOR       S_CURRENT_TRANSFER
S_CURRENT_POSITION_CHANGE            S_CURRENT_TRANSFER_POSITION
S_CURRENT_TERMS_CHANGE               S_FUTURE_EXACT_PRESERVE
S_FUTURE_UNCHANGED_SUCCESSOR         S_FUTURE_TRANSFER
S_FUTURE_POSITION_CHANGE             S_FUTURE_TRANSFER_POSITION
S_FUTURE_TERMS_CHANGE                S_UNSUPPORTED
```

The classifier is a normative function, not a list of suggestive names. It uses these
closed derived predicates over the trusted request and the locked §7 state. `D` is computed
independently from `transaction_timestamp()` in fixed UTC+05:00 inside the caller-owned
transaction as specified by §5.1; `watermark.effective_date` does not define `D`. Only a
watermark with `effective_date=D` is usable; a stale or future watermark blocks
classification and never changes `D`. `P0` means zero ADR-048-compatible non-merged Person candidates;
`P1` means exactly one; any other candidate cardinality is neither. `E0` means no target
Employee exists and `E1` means exactly the requested Employee exists. `L0` means its
`person_id` is NULL and `L1` means it equals the unique selected Person. `A0` means no
non-void primary assignment exists for that Person. `T` is the explicitly identified
assignment with matching expected `row_version`. `CUR(T)` means `T` is the unique
non-void primary eligible at `D`; `FUT(T)` means `NONVOID(T)` and the locked persisted
`T.start_date` is non-NULL and strictly greater than `D`; `HIST(T)` means its
inclusive end is before `D`. `BADCHAIN` means invalid dates, more than one eligible
primary, overlap, branching replacement lineage, or any §5 invariant failure.

`intent_shape` is derived before mode comparison solely from request fields and verified
evidence type: `OPEN`, `VERIFY`, `LINK_AND_OPEN`, `LINK`, `CORRECT_VOID`, `CORRECT_REPLACE`,
`COMPLETE_CLOSE`, `COMPLETE_SUCCESSOR`, `TRANSITION`, or `PRESERVE_FUTURE`. These values
are disjoint: for example `CORRECT_VOID` forbids successor fields while
`CORRECT_REPLACE` requires the complete replacement object; `COMPLETE_SUCCESSOR` requires
completion evidence while `TRANSITION` requires transfer/change evidence. `delta` compares
the successor with the predecessor using business attributes
`(org_unit_id, position_id, rate, employment_type, is_primary)` and has exactly one value
`UNCHANGED | ORG | POSITION | ORG_POSITION | TERMS`; `TERMS` wins when rate or
employment type differs. Temporal `start_date` is not part of `delta`.

The following predicates are literal. `valid-common` means authenticated/authorized,
complete typed non-operation fields, one current watermark, no `BADCHAIN`, and all explicit
IDs exist. Operation/mode are preserved as decoded ASCII identifiers here; membership and
compatibility are checked only at the later fixture step;
failure of one of those common preconditions is handled before classification by the
precedence below.

| State class | Exact predicate after `valid-common` |
|---|---|
| `S_ENROLLABLE_NO_EMPLOYEE` | operation=`ACTIVE_ENROLLMENT` AND intent=`OPEN` AND `E0 AND P0` |
| `S_CONSISTENT` | intent=`VERIFY` AND every field of the requested final state equals the locked §7 tuple and no write would occur |
| `S_UNLINKED_NO_PRIMARY_P0_WITH_INTENT` | operation=`EXISTING_CARD_REPAIR` AND intent=`LINK_AND_OPEN` AND `E1 AND L0 AND P0` AND `COMPLETE_CONFIRMED_ASSIGNMENT_INTENT`; after Shell INSERT, the new Person scope is locked and `A0` is asserted before C2 |
| `S_UNLINKED_NO_PRIMARY_P1_WITH_INTENT` | operation=`EXISTING_CARD_REPAIR` AND intent=`LINK_AND_OPEN` AND `E1 AND L0 AND P1 AND A0` AND `COMPLETE_CONFIRMED_ASSIGNMENT_INTENT` |
| `S_LINK_MISSING_PERSON` | (`ACTIVE_ENROLLMENT`, `OPEN`, `E0 AND P1`) OR (`EXISTING_CARD_REPAIR`, `LINK`, `E1 AND L0 AND P1`) |
| `S_LINK_MISSING_PERSON_ABSENT` | operation=`EXISTING_CARD_REPAIR` AND intent=`LINK` AND `E1 AND L0 AND P0`; the retained label means the Person anchor is absent, not that Employee absence status is inferred |
| `S_NO_NONVOID_PRIMARY` | operation=`EXISTING_CARD_REPAIR` AND intent=`OPEN` AND `E1 AND L1 AND A0` |
| `S_ERRONEOUS_VOID_ONLY` | operation=`EXISTING_CARD_REPAIR` AND intent=`CORRECT_VOID` AND `T` is non-void and correction evidence identifies exactly `T` |
| `S_ERRONEOUS_WITH_REPLACEMENT` | same persisted target rule, intent=`CORRECT_REPLACE`, and a complete non-overlapping replacement object is present |
| `S_COMPLETE_NO_SUCCESSOR` | intent=`COMPLETE_CLOSE` AND `CUR(T)` AND confirmed `old_end_date < D` and no successor object |
| `S_COMPLETE_UNCHANGED_SUCCESSOR` | intent=`COMPLETE_SUCCESSOR` AND `CUR(T)` AND `transition_date <= D` AND `delta=UNCHANGED` |
| `S_CURRENT_TRANSFER` | intent=`TRANSITION` AND `CUR(T)` AND `transition_date <= D` AND `delta=ORG` |
| `S_CURRENT_POSITION_CHANGE` | same with `delta=POSITION` |
| `S_CURRENT_TRANSFER_POSITION` | same with `delta=ORG_POSITION` |
| `S_CURRENT_TERMS_CHANGE` | same with `delta=TERMS` |
| `S_FUTURE_EXACT_PRESERVE` | intent=`PRESERVE_FUTURE` AND `FUT(T)` AND every submitted expected field equals `T` |
| `S_FUTURE_UNCHANGED_SUCCESSOR` | intent=`TRANSITION` AND `CUR(T)` AND `transition_date > D` AND `delta=UNCHANGED` |
| `S_FUTURE_TRANSFER` | same with `delta=ORG` |
| `S_FUTURE_POSITION_CHANGE` | same with `delta=POSITION` |
| `S_FUTURE_TRANSFER_POSITION` | same with `delta=ORG_POSITION` |
| `S_FUTURE_TERMS_CHANGE` | same with `delta=TERMS` |
| `S_UNSUPPORTED` | `valid-common` AND NOT(the disjunction of the preceding twenty-one predicates) |

The predicates are pairwise disjoint: the closed `intent_shape` partitions the major
branches; within a branch `P0/P1`, `E0/E1`, and `L0/L1` are exclusive; current/future is
partitioned by `transition_date <= D` versus `> D`; and `delta` has one value. The only
multi-operation class has disjoint operation clauses. Their disjunction plus the literal
complement is exhaustive for every `valid-common` snapshot. The classifier is serialized
as a machine-readable fixture with columns `state_code`, `operation`, `intent_shape`,
`employee_cardinality`, `person_candidate_cardinality`, `link_state`, `target_temporality`,
`successor_presence`, and `delta`; NULL is an explicit wildcard only where the table above
says the field is irrelevant. CI expands the fixture and proves no input vector matches
zero or two predicates.

This is the complete allowed matrix after `valid-common=true`. `app identity` means the §4
C2-only create/adopt protocol. `none` means normatively absent. The tuple function first rejects a pair absent
from the compatibility table as `INVALID_OPERATION_MODE`. Only for a compatible pair does
it classify state. If and only if classification returns `S_UNSUPPORTED`, the result is
`UNSUPPORTED_SOURCE_STATE` **before** allowed-row lookup. For any other classified state,
an absent allowed row returns `MODE_SOURCE_STATE_MISMATCH`; an existing row returns its
single success. Thus all `2 × 19 × 22 = 836` enum tuples have exactly one result without
overlapping defaults.

| State | Operation / mode | Required request/evidence and date rule | Exact C2/adoption/reconciliation | Canonical / personnel / Employee event | Stable result | Apply |
|---|---|---|---|---|---|---|
| `S_ENROLLABLE_NO_EMPLOYEE` | `ACTIVE_ENROLLMENT / ENROLL_NEW_ACTIVE` | import IDs; zero Person candidate; exact §8.1 Shell create intention; confirmed org/position; rate; primary employment type; start; assignment intent/evidence | ADR-048 creates Shell; create Employee/identity/link; C2 `OPEN_ASSIGNMENT`; app identity; reconcile opened ID | none / exactly `PERSON_SHELL_CREATED` and `EMPLOYEE_PERSON_LINKED` / none | `ENROLLED_CREATED` | yes |
| `S_CONSISTENT` | either / `VERIFY_CONSISTENT` | complete expected state; verifier/time/reference and evidence | no C2, adoption, or reconciliation | none / none / none | `ALREADY_CONSISTENT` | yes, no-op |
| `S_LINK_MISSING_PERSON` | `ACTIVE_ENROLLMENT / ENROLL_NEW_ACTIVE` | no Employee; exactly one existing compatible Person; Employee expected-field tuple; assignment intent/evidence | link existing Person; create Employee/identity; C2 `OPEN_ASSIGNMENT`; app identity; reconcile opened ID | none / exactly `EMPLOYEE_PERSON_LINKED` / none | `ENROLLED_CREATED` | yes |
| `S_UNLINKED_NO_PRIMARY_P0_WITH_INTENT` | `EXISTING_CARD_REPAIR / LINK_AND_OPEN_MISSING_ASSIGNMENT` | exact Employee/identity expected state; P0; exact §8.1 Shell-create input; explicitly operator-confirmed org unit, position, rate, employment type, `is_primary=true`, start date, evidence and controlled reason | ADR-048 creates Shell; link existing Employee; save/verify exact IIN identity; C2 `OPEN_ASSIGNMENT`; create/adopt application identity; reconcile opened ID; persist import provenance/binding | none / exactly `PERSON_SHELL_CREATED` and `EMPLOYEE_PERSON_LINKED` / none | `EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED` | yes, one transaction |
| `S_UNLINKED_NO_PRIMARY_P1_WITH_INTENT` | `EXISTING_CARD_REPAIR / LINK_AND_OPEN_MISSING_ASSIGNMENT` | exact Employee/identity expected state; P1 selected-Person expected state; zero non-VOID primary; the same eight explicitly confirmed assignment inputs | ADR-048 adopts the unique compatible Person; link existing Employee; verify exact IIN identity; C2 `OPEN_ASSIGNMENT`; create/adopt application identity; reconcile opened ID; persist import provenance/binding | none / exactly `EMPLOYEE_PERSON_LINKED` / none | `EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED` | yes, one transaction |
| `S_LINK_MISSING_PERSON` | `EXISTING_CARD_REPAIR / LINK_ONLY` | Employee exact expected tuple; exactly one compatible existing Person; link evidence | set `employees.person_id`; no C2/adoption/reconciliation; preserve every other Employee field | none / exactly `EMPLOYEE_PERSON_LINKED` / none | `EMPLOYEE_PERSON_REPAIRED` | yes |
| `S_LINK_MISSING_PERSON_ABSENT` | `EXISTING_CARD_REPAIR / LINK_ONLY` | Employee exact expected tuple; zero Person candidate; exact §8.1 Shell create intention and ADR-048 Shell evidence | ADR-048 creates Shell, then set `employees.person_id`; no C2/adoption/reconciliation; preserve every other Employee field | none / exactly `PERSON_SHELL_CREATED` and `EMPLOYEE_PERSON_LINKED` / none | `EMPLOYEE_PERSON_REPAIRED` | yes |
| `S_NO_NONVOID_PRIMARY` | `EXISTING_CARD_REPAIR / OPEN_MISSING_ASSIGNMENT` | complete assignment intent/start/attributes/evidence | C2 `OPEN_ASSIGNMENT`; app identity; reconcile opened ID | none / none / none | `MISSING_ASSIGNMENT_OPENED` | yes |
| `S_ERRONEOUS_VOID_ONLY` | `EXISTING_CARD_REPAIR / CORRECT_ERRONEOUS_RECORD` | original ID/version; correction evidence; no successor fields | C2 `CORRECT_ASSIGNMENT` void-only; no adoption; always reconcile `post_current_primary_id`, defined as the unique post-command row eligible at `D` or JSON/SQL NULL when none | none / exactly one `ASSIGNMENT_CORRECTED` / none | `ERRONEOUS_ASSIGNMENT_VOIDED` | yes |
| `S_ERRONEOUS_WITH_REPLACEMENT` | `EXISTING_CARD_REPAIR / CORRECT_ERRONEOUS_RECORD_WITH_REPLACEMENT` | original ID/version; complete replacement attributes/dates/evidence | C2 atomic void+open; app identity for replacement; always reconcile `post_current_primary_id`, the unique post-command row eligible at `D` or JSON/SQL NULL when none | none / exactly one `ASSIGNMENT_CORRECTED` linking IDs / none | `ERRONEOUS_ASSIGNMENT_REPLACED` | yes |
| `S_COMPLETE_NO_SUCCESSOR` | `EXISTING_CARD_REPAIR / COMPLETE_REAL_LIFECYCLE_EPISODE` | current ID/version; `old_end_date < effective_date`; completion evidence; no successor | C2 `CLOSE_ASSIGNMENT`; no adoption; reconcile NULL | none / none / none | `LIFECYCLE_EPISODE_COMPLETED` | yes |
| `S_COMPLETE_UNCHANGED_SUCCESSOR` | `EXISTING_CARD_REPAIR / COMPLETE_REAL_LIFECYCLE_EPISODE_WITH_SUCCESSOR` | current ID/version; `transition_date <= effective_date`; successor business attributes org, position, rate, employment type and primary flag unchanged; successor start equals transition date | C2 continuous `TRANSITION_ASSIGNMENT`; app identity derived with the new start date; reconcile successor | none / none / none | `LIFECYCLE_EPISODE_COMPLETED_WITH_SUCCESSOR` | yes |
| `S_CURRENT_TRANSFER` | `EXISTING_CARD_REPAIR / TRANSFER` | org only changes; all other defining attributes unchanged; current ID/version; transition/evidence | C2 continuous `TRANSITION_ASSIGNMENT`; app identity; reconcile successor | none / none / `TRANSFER` | `ASSIGNMENT_TRANSFERRED` | yes |
| `S_CURRENT_POSITION_CHANGE` | `EXISTING_CARD_REPAIR / POSITION_CHANGE` | position only changes; confirmed ID/name; all other defining attributes unchanged; transition/evidence | C2 continuous `TRANSITION_ASSIGNMENT`; app identity; reconcile successor | none / none / `POSITION_CHANGE` | `ASSIGNMENT_POSITION_CHANGED` | yes |
| `S_CURRENT_TRANSFER_POSITION` | `EXISTING_CARD_REPAIR / TRANSFER_AND_POSITION_CHANGE` | org+position change; terms unchanged; transition/evidence | C2 continuous `TRANSITION_ASSIGNMENT`; app identity; reconcile successor | none / none / one `TRANSFER` with before/after org+position IDs | `ASSIGNMENT_TRANSFERRED_AND_POSITION_CHANGED` | yes |
| `S_CURRENT_TERMS_CHANGE` | `EXISTING_CARD_REPAIR / ASSIGNMENT_TERMS_CHANGE` | rate and/or employment type changes; exact `changed_fields`; all other deltas explicit; transition/evidence | C2 continuous `TRANSITION_ASSIGNMENT`; app identity; reconcile successor | none / none / `ASSIGNMENT_TERMS_CHANGE` with exact before/after attributes | `ASSIGNMENT_TERMS_CHANGED` | yes |
| `S_FUTURE_EXACT_PRESERVE` | `EXISTING_CARD_REPAIR / PRESERVE_FUTURE_ASSIGNMENT` | future ID/version and complete equal timeline; preservation evidence | no C2/adoption/reconciliation | none / none / none | `FUTURE_ASSIGNMENT_PRESERVED` | yes, no-op |
| `S_FUTURE_UNCHANGED_SUCCESSOR` | `EXISTING_CARD_REPAIR / TRANSITION_FUTURE_UNCHANGED_ASSIGNMENT` | future continuous transition; every defining attribute unchanged | C2 schedules `TRANSITION_ASSIGNMENT`; app identity; no immediate reconciliation | none / none / none at scheduling/boundary | `FUTURE_UNCHANGED_ASSIGNMENT_SCHEDULED` | yes |
| `S_FUTURE_TRANSFER` | `EXISTING_CARD_REPAIR / TRANSITION_FUTURE_TRANSFER` | future transition; org only changes; terms/position unchanged; evidence | C2 schedules `TRANSITION_ASSIGNMENT`; app identity; no immediate reconciliation; boundary reconciles successor | none / none / scheduled `TRANSFER` with future effective date | `FUTURE_ASSIGNMENT_TRANSFER_SCHEDULED` | yes |
| `S_FUTURE_POSITION_CHANGE` | `EXISTING_CARD_REPAIR / TRANSITION_FUTURE_POSITION_CHANGE` | future transition; position only changes; terms/org unchanged; evidence | C2 schedules `TRANSITION_ASSIGNMENT`; app identity; no immediate reconciliation; boundary reconciles successor | none / none / scheduled `POSITION_CHANGE` | `FUTURE_ASSIGNMENT_POSITION_CHANGE_SCHEDULED` | yes |
| `S_FUTURE_TRANSFER_POSITION` | `EXISTING_CARD_REPAIR / TRANSITION_FUTURE_TRANSFER_AND_POSITION_CHANGE` | future transition; org+position change; terms unchanged; evidence | C2 schedules `TRANSITION_ASSIGNMENT`; app identity; no immediate reconciliation; boundary reconciles successor | none / none / scheduled `TRANSFER` with before/after org+position IDs | `FUTURE_ASSIGNMENT_TRANSFER_POSITION_SCHEDULED` | yes |
| `S_FUTURE_TERMS_CHANGE` | `EXISTING_CARD_REPAIR / TRANSITION_FUTURE_ASSIGNMENT_TERMS_CHANGE` | future rate and/or employment type change; all other deltas explicit; exact `changed_fields`; evidence | C2 schedules `TRANSITION_ASSIGNMENT`; app identity; no immediate reconciliation; boundary reconciles successor | none / none / scheduled `ASSIGNMENT_TERMS_CHANGE` | `FUTURE_ASSIGNMENT_TERMS_CHANGE_SCHEDULED` | yes |

### 2.1. Atomic composite existing-card repair

`LINK_AND_OPEN_MISSING_ASSIGNMENT` is one composite mode with stable success outcome
`EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED`. Its two static P0/P1 matrix rows are evaluated before the
`LINK_ONLY` and `OPEN_MISSING_ASSIGNMENT` rows. The distinct `LINK_AND_OPEN` intent
shape makes the rows disjoint; this priority does not broaden or change either standalone
mode. A caller wanting only a Person link still uses `LINK_ONLY`; a caller whose Employee
is already linked still uses `OPEN_MISSING_ASSIGNMENT`.

The exact, mutually exclusive apply predicates are:

```text
P0:
valid-common
AND operation = EXISTING_CARD_REPAIR
AND mode = LINK_AND_OPEN_MISSING_ASSIGNMENT
AND intent_shape = LINK_AND_OPEN
AND E1 AND L0 AND P0
AND COMPLETE_CONFIRMED_ASSIGNMENT_INTENT

P1:
valid-common
AND operation = EXISTING_CARD_REPAIR
AND mode = LINK_AND_OPEN_MISSING_ASSIGNMENT
AND intent_shape = LINK_AND_OPEN
AND E1 AND L0 AND P1 AND A0
AND COMPLETE_CONFIRMED_ASSIGNMENT_INTENT
```

`COMPLETE_CONFIRMED_ASSIGNMENT_INTENT` is true only when the authorized operator has
separately and explicitly confirmed the exact `org_unit_id` plus normalized org
reference, `position_id` plus normalized position name, `rate`, `employment_type`,
`is_primary=true`, `start_date`, allowed evidence reference, controlled `reason_code`,
verifier, and confirmation time. No value may be omitted, defaulted, copied, or inferred
from an import row, Employee projection, HIRE event, personnel order, normalized payload,
or another historical/technical timestamp. A personnel order is evidence only after the
operator separately confirms that it is admissible evidence and separately confirms the
assignment date; its date never becomes `start_date` automatically.

P0 means no ADR-048-compatible non-merged Person candidate for the confirmed IIN. It
requires the complete §8.1 Shell-create intention and Shell evidence; ADR-048 creates the
Person Shell. P1 means exactly one compatible, non-merged, non-conflicting Person candidate.
It requires that Person ID and expected-state hash; ADR-048 normatively adopts it and must
not create a second Person. P1 also requires zero non-VOID primary assignments for that
Person. Candidate cardinality greater than one, a merged/forbidden candidate, mismatching
IIN, conflicting Employee/Person identity, any non-VOID primary, or a create/adopt decision
different from preview fails closed before business DML. P0 is rechecked under the identity
lock; P1 is rechecked under both the identity lock and selected Person row lock.

The complete expected state binds the Employee row and row version/hash, NULL
`employees.person_id`, employee identity rows, actual submitted IIN verifier, P0/P1
candidate set and selected/create intention, absence of a non-VOID primary, org and
position references, assignment episode, evidence scope/generation and rows, watermark,
and exact import provenance set. Any difference between preview and locked apply returns
`STALE_EXPECTED_STATE` before the first business mutation. Identity collision or
incompatible Person/IIN returns the existing exact identity conflict code; ambiguity
returns the existing ADR-048 ambiguity code. Missing or unconfirmed intent returns
`ASSIGNMENT_INTENT_INCOMPLETE`; it must not fall through to `LINK_ONLY`.

One caller-owned PostgreSQL transaction, using only authority writers, performs in order:

1. ADR-048 Person Create-or-Link creates the P0 Shell or adopts the P1 Person.
2. The ADR-048 link/identity ports set the existing Employee's `person_id`, save or verify
   the exact IIN identity without overwrite, and assert Employee, Person, and identity
   consistency.
3. Strict ADR-043/C2 `OPEN_ASSIGNMENT` creates/adopts the one primary episode; neither the
   orchestrator nor import code writes assignment tables directly.
4. The reconciliation port projects the returned assignment ID to that Employee and
   verifies assignment → Person → Employee consistency.
5. Personnel event and success-audit writers append the outcome, actor, reason, evidence
   fingerprint, Person/Employee/assignment IDs, idempotency correlation, and P0/P1 branch.
   P0 emits exactly `PERSON_SHELL_CREATED` then `EMPLOYEE_PERSON_LINKED`; P1 emits
   exactly `EMPLOYEE_PERSON_LINKED`. C2 retains ownership of any canonical assignment
   event; no synthetic canonical event or event macro is added.
6. Import writers persist the immutable binding/provenance and normalized propagation,
   followed by the safe idempotency result.
7. The transaction commits once, only after every postcondition succeeds.

The lock order is the §9.2 global order: operation/idempotency; boundary watermark when
current-state is read; identity advisory key; org then position references; evidence scope
and evidence rows; existing/adopted Person row (the P0 row immediately after INSERT);
assignment-scope advisory lock; existing Employee; assignment rows and links; import rows;
later projections/audit rows. Locks are never released or reacquired out of order before
commit. Participating authority writers are ADR-048 Create-or-Link and link/identity
ports, strict ADR-043/C2, transactional reconciliation, personnel event, strict success
audit, import binding/normalized-propagation, and idempotency ports.

The pre-operation business digest binds the exact closed §8.1 request inputs: operation
type and mode, request schema/identity and correlation, the exact sorted
`(batch_id,row_id)` set and sorted `normalized_record_ids`, source fingerprints,
Employee and requested/created Person identity, assignment intent, actor, evidence
fingerprint, and the static P0 or P1 request shape. Generated `operation_id` is not a
digest input. The idempotency port computes the digest first, then creates the operation
row and obtains `operation_id`; every operation-owned event, audit, assignment
application provenance, import binding and result row subsequently persists that ID as
an FK/provenance reference in the same transaction. Retry may neither substitute another
import row nor expand the set. Absence,
duplication, prior binding to another Employee/Person/assignment, or changed provenance is
a conflict or stale state, never a best-effort omission.

Idempotency follows §8: the same scoped key, actual raw-IIN verifier, canonical business
digest, and committed request returns the stored success with `replayed=true` and performs
no write. The same key with any changed Employee, Person decision, assignment intent,
evidence, expected state, or provenance conflicts. An unknown commit is recovered by the
authoritative operation/provenance keys; it is never retried with a new key or decomposed
into `LINK_ONLY` then `OPEN_MISSING_ASSIGNMENT`.

The committed postcondition requires one compatible Person, the existing Employee linked
to it, matching saved/verified IIN identity, exactly one returned non-VOID primary
assignment with the confirmed terms, reconciliation to that assignment, exact event/audit
outcome, and complete provenance/binding. Failure of any assertion raises and rolls back
the whole transaction. In particular, the intermediate state “Employee is linked to
Person but assignment has not been created” may exist only as uncommitted state inside
this transaction and is forbidden as a committed result. Rollback restores the P1 Person
unchanged or removes the P0 Shell, restores `employees.person_id IS NULL` and every
Employee projection, removes identity/assignment/link/event/audit/provenance changes, and
leaves no successful idempotency result.
The composite appends only its required personnel/audit/provenance rows: it never updates,
deletes or relabels pre-existing Employee events or personnel-order rows, and it preserves
every Employee field except `person_id` and the exact assignment-derived projection fields
returned by §3.3 reconciliation.

The following literal fixture uses option B: the closed UTF-8 ASCII DSL
`adr065-outcome-function-v1`. Parsing is schema-directed and uses this complete lexical/
BNF grammar (`SP` is ASCII space/tab/CR/LF and is insignificant):

```text
identifier     := [A-Za-z_][A-Za-z0-9_-]*
unsigned       := 0 | [1-9][0-9]*
document       := '{' member (',' member)* '}'
member         := identifier ':' value
value          := identifier | unsigned | array | document
array          := '[' (typed-value (',' typed-value)*)? ']'
typed-value    := value | predicate | input-set
input-set      := identifier (';' identifier)*
predicate      := or-expression
or-expression := and-expression ('||' and-expression)*
and-expression:= unary-expression ('&&' unary-expression)*
unary-expression := '!' unary-expression | '(' predicate ')' | comparison | function | identifier
comparison     := identifier ('='|'<'|'<='|'>'|'>=') identifier
function       := ('CUR'|'NONVOID'|'FUT'|'EVIDENCE_EXACT') '(' identifier ')'
```

The second member of every `state_predicates` record and the `date_rule` member of an
allowed record are `predicate`; `required_inputs` and multi-event fields are `input-set`;
all other record members are identifiers. Operator precedence is parentheses/function/
`!`, then comparison, then `&&`, then `||`; the lexer takes the longest comparison token
and equal-precedence operators associate left.
`identifier` therefore accepts `valid-common`, and the grammar literally accepts
`CUR(T)`, `transition_date<=D` and `old_end_date<D`. No other operator, function, wildcard,
quote, escape, comment, alias or omitted value exists. Unknown document member, enum,
function, token or request-field identifier fails fixture validation.

Top-level members are exactly `schema_version`, `operations`, `modes`, `states`,
`compatibility`, `predicate_operators`, `predicate_functions`, `action_ids`,
`result_codes`, `state_predicates`, `precedence`, `allowed_columns`, `allowed_records`, and
`expected_counts`, in that order. Array order is normative and duplicates are forbidden.
`BOTH` is the only wildcard and expands in `operations` order. Allowed records use the
exact column order in `allowed_columns`; semicolon lists are closed sets of §8 request
members and are serialized in the listed order. `NONE` is explicit absence.
The `precedence` member is itself a closed enum list and must equal byte-for-byte the
literal sequence in the fixture; the only admitted values are `AUTHENTICATION`,
`AUTHORIZATION`, `REQUEST_COMPLETENESS`, `IDEMPOTENCY_LOOKUP`,
`IDENTITY_INPUT_BINDING`, `COMMITTED_REPLAY`,
`COMMON_PRECONDITIONS`, `INVALID_OPERATION_MODE`, `CLASSIFY`,
`UNSUPPORTED_SOURCE_STATE`, `ALLOWED_LOOKUP`, `MODE_SOURCE_STATE_MISMATCH`, and
`ALLOWED_OUTCOME`. Unknown, missing, duplicate or reordered phases fail parsing.

Canonical serialization parses to the typed AST, emits top-level members and arrays in
their normative order, emits no whitespace, emits identifiers/operators byte-for-byte,
adds only precedence-required parentheses, and preserves allowed-record column order.
Two conforming implementations must therefore produce identical UTF-8 bytes. The literal
block, not a future generated file, is normative; a parser that cannot consume it fails.

```adr065-outcome-v1
{
  schema_version: adr065-outcome-function-v1,
  operations: [ACTIVE_ENROLLMENT, EXISTING_CARD_REPAIR],
  modes: [ENROLL_NEW_ACTIVE, VERIFY_CONSISTENT, LINK_AND_OPEN_MISSING_ASSIGNMENT, LINK_ONLY, OPEN_MISSING_ASSIGNMENT, CORRECT_ERRONEOUS_RECORD, CORRECT_ERRONEOUS_RECORD_WITH_REPLACEMENT, COMPLETE_REAL_LIFECYCLE_EPISODE, COMPLETE_REAL_LIFECYCLE_EPISODE_WITH_SUCCESSOR, TRANSFER, POSITION_CHANGE, TRANSFER_AND_POSITION_CHANGE, ASSIGNMENT_TERMS_CHANGE, PRESERVE_FUTURE_ASSIGNMENT, TRANSITION_FUTURE_UNCHANGED_ASSIGNMENT, TRANSITION_FUTURE_TRANSFER, TRANSITION_FUTURE_POSITION_CHANGE, TRANSITION_FUTURE_TRANSFER_AND_POSITION_CHANGE, TRANSITION_FUTURE_ASSIGNMENT_TERMS_CHANGE],
  states: [S_ENROLLABLE_NO_EMPLOYEE, S_CONSISTENT, S_UNLINKED_NO_PRIMARY_P0_WITH_INTENT, S_UNLINKED_NO_PRIMARY_P1_WITH_INTENT, S_LINK_MISSING_PERSON, S_LINK_MISSING_PERSON_ABSENT, S_NO_NONVOID_PRIMARY, S_ERRONEOUS_VOID_ONLY, S_ERRONEOUS_WITH_REPLACEMENT, S_COMPLETE_NO_SUCCESSOR, S_COMPLETE_UNCHANGED_SUCCESSOR, S_CURRENT_TRANSFER, S_CURRENT_POSITION_CHANGE, S_CURRENT_TRANSFER_POSITION, S_CURRENT_TERMS_CHANGE, S_FUTURE_EXACT_PRESERVE, S_FUTURE_UNCHANGED_SUCCESSOR, S_FUTURE_TRANSFER, S_FUTURE_POSITION_CHANGE, S_FUTURE_TRANSFER_POSITION, S_FUTURE_TERMS_CHANGE, S_UNSUPPORTED],
  compatibility: {
    ACTIVE_ENROLLMENT: [ENROLL_NEW_ACTIVE, VERIFY_CONSISTENT],
    EXISTING_CARD_REPAIR: [VERIFY_CONSISTENT, LINK_AND_OPEN_MISSING_ASSIGNMENT, LINK_ONLY, OPEN_MISSING_ASSIGNMENT, CORRECT_ERRONEOUS_RECORD, CORRECT_ERRONEOUS_RECORD_WITH_REPLACEMENT, COMPLETE_REAL_LIFECYCLE_EPISODE, COMPLETE_REAL_LIFECYCLE_EPISODE_WITH_SUCCESSOR, TRANSFER, POSITION_CHANGE, TRANSFER_AND_POSITION_CHANGE, ASSIGNMENT_TERMS_CHANGE, PRESERVE_FUTURE_ASSIGNMENT, TRANSITION_FUTURE_UNCHANGED_ASSIGNMENT, TRANSITION_FUTURE_TRANSFER, TRANSITION_FUTURE_POSITION_CHANGE, TRANSITION_FUTURE_TRANSFER_AND_POSITION_CHANGE, TRANSITION_FUTURE_ASSIGNMENT_TERMS_CHANGE]
  },
  predicate_operators: [NOT, AND, OR, EQ, LT, LTE, GT, GTE],
  predicate_functions: [CUR, NONVOID, FUT, EVIDENCE_EXACT],
  action_ids: [ENROLL_CREATE, ENROLL_LINK_EXISTING, VERIFY_NOOP, COMPOSITE_LINK_AND_OPEN_P0, COMPOSITE_LINK_AND_OPEN_P1, LINK_EXISTING_PERSON, CREATE_SHELL_AND_LINK, OPEN_MISSING, VOID_ERRONEOUS, VOID_AND_REPLACE, COMPLETE_CLOSE, COMPLETE_CONTINUOUS, CURRENT_TRANSFER, CURRENT_POSITION, CURRENT_TRANSFER_POSITION, CURRENT_TERMS, PRESERVE_FUTURE, FUTURE_UNCHANGED, FUTURE_TRANSFER, FUTURE_POSITION, FUTURE_TRANSFER_POSITION, FUTURE_TERMS],
  result_codes: [INVALID_OPERATION_MODE, UNSUPPORTED_SOURCE_STATE, MODE_SOURCE_STATE_MISMATCH, ENROLLED_CREATED, ALREADY_CONSISTENT, EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED, EMPLOYEE_PERSON_REPAIRED, MISSING_ASSIGNMENT_OPENED, ERRONEOUS_ASSIGNMENT_VOIDED, ERRONEOUS_ASSIGNMENT_REPLACED, LIFECYCLE_EPISODE_COMPLETED, LIFECYCLE_EPISODE_COMPLETED_WITH_SUCCESSOR, ASSIGNMENT_TRANSFERRED, ASSIGNMENT_POSITION_CHANGED, ASSIGNMENT_TRANSFERRED_AND_POSITION_CHANGED, ASSIGNMENT_TERMS_CHANGED, FUTURE_ASSIGNMENT_PRESERVED, FUTURE_UNCHANGED_ASSIGNMENT_SCHEDULED, FUTURE_ASSIGNMENT_TRANSFER_SCHEDULED, FUTURE_ASSIGNMENT_POSITION_CHANGE_SCHEDULED, FUTURE_ASSIGNMENT_TRANSFER_POSITION_SCHEDULED, FUTURE_ASSIGNMENT_TERMS_CHANGE_SCHEDULED],
  state_predicates: [
    [S_ENROLLABLE_NO_EMPLOYEE, valid-common&&operation=ACTIVE_ENROLLMENT&&intent=OPEN&&E0&&P0],
    [S_CONSISTENT, valid-common&&intent=VERIFY&&EXACT_FINAL_STATE],
    [S_UNLINKED_NO_PRIMARY_P0_WITH_INTENT, valid-common&&operation=EXISTING_CARD_REPAIR&&intent=LINK_AND_OPEN&&E1&&L0&&P0&&COMPLETE_CONFIRMED_ASSIGNMENT_INTENT],
    [S_UNLINKED_NO_PRIMARY_P1_WITH_INTENT, valid-common&&operation=EXISTING_CARD_REPAIR&&intent=LINK_AND_OPEN&&E1&&L0&&P1&&A0&&COMPLETE_CONFIRMED_ASSIGNMENT_INTENT],
    [S_LINK_MISSING_PERSON, valid-common&&((operation=ACTIVE_ENROLLMENT&&intent=OPEN&&E0&&P1)||(operation=EXISTING_CARD_REPAIR&&intent=LINK&&E1&&L0&&P1))],
    [S_LINK_MISSING_PERSON_ABSENT, valid-common&&operation=EXISTING_CARD_REPAIR&&intent=LINK&&E1&&L0&&P0],
    [S_NO_NONVOID_PRIMARY, valid-common&&operation=EXISTING_CARD_REPAIR&&intent=OPEN&&E1&&L1&&A0],
    [S_ERRONEOUS_VOID_ONLY, valid-common&&operation=EXISTING_CARD_REPAIR&&intent=CORRECT_VOID&&NONVOID(T)&&EVIDENCE_EXACT(T)],
    [S_ERRONEOUS_WITH_REPLACEMENT, valid-common&&operation=EXISTING_CARD_REPAIR&&intent=CORRECT_REPLACE&&NONVOID(T)&&EVIDENCE_EXACT(T)&&COMPLETE_NONOVERLAPPING_REPLACEMENT],
    [S_COMPLETE_NO_SUCCESSOR, valid-common&&intent=COMPLETE_CLOSE&&CUR(T)&&old_end_date<D&&!SUCCESSOR],
    [S_COMPLETE_UNCHANGED_SUCCESSOR, valid-common&&intent=COMPLETE_SUCCESSOR&&CUR(T)&&transition_date<=D&&delta=UNCHANGED],
    [S_CURRENT_TRANSFER, valid-common&&intent=TRANSITION&&CUR(T)&&transition_date<=D&&delta=ORG],
    [S_CURRENT_POSITION_CHANGE, valid-common&&intent=TRANSITION&&CUR(T)&&transition_date<=D&&delta=POSITION],
    [S_CURRENT_TRANSFER_POSITION, valid-common&&intent=TRANSITION&&CUR(T)&&transition_date<=D&&delta=ORG_POSITION],
    [S_CURRENT_TERMS_CHANGE, valid-common&&intent=TRANSITION&&CUR(T)&&transition_date<=D&&delta=TERMS],
    [S_FUTURE_EXACT_PRESERVE, valid-common&&intent=PRESERVE_FUTURE&&FUT(T)&&EXACT_SUBMITTED_TARGET],
    [S_FUTURE_UNCHANGED_SUCCESSOR, valid-common&&intent=TRANSITION&&CUR(T)&&transition_date>D&&delta=UNCHANGED],
    [S_FUTURE_TRANSFER, valid-common&&intent=TRANSITION&&CUR(T)&&transition_date>D&&delta=ORG],
    [S_FUTURE_POSITION_CHANGE, valid-common&&intent=TRANSITION&&CUR(T)&&transition_date>D&&delta=POSITION],
    [S_FUTURE_TRANSFER_POSITION, valid-common&&intent=TRANSITION&&CUR(T)&&transition_date>D&&delta=ORG_POSITION],
    [S_FUTURE_TERMS_CHANGE, valid-common&&intent=TRANSITION&&CUR(T)&&transition_date>D&&delta=TERMS],
    [S_UNSUPPORTED, valid-common&&!ANY_PRECEDING_21_PREDICATE]
  ],
  precedence: [AUTHENTICATION, AUTHORIZATION, REQUEST_COMPLETENESS, IDEMPOTENCY_LOOKUP, IDENTITY_INPUT_BINDING, COMMITTED_REPLAY, COMMON_PRECONDITIONS, INVALID_OPERATION_MODE, CLASSIFY, UNSUPPORTED_SOURCE_STATE, ALLOWED_LOOKUP, MODE_SOURCE_STATE_MISMATCH, ALLOWED_OUTCOME],
  allowed_columns: [operation, mode, state, action_id, required_inputs, evidence, date_rule, gap_overlap, temporal_behavior, c2_command, adoption, reconciliation, canonical_event, personnel_event, employee_event, success_code],
  allowed_records: [
    [ACTIVE_ENROLLMENT, ENROLL_NEW_ACTIVE, S_ENROLLABLE_NO_EMPLOYEE, ENROLL_CREATE, import_ids;person_create_input;employee_expected;org_position_expected;episode;verifier_confirmation, ASSIGNMENT_INTENT, OPEN_START_DATE, NO_PRIMARY_OVERLAP, CURRENT_OPEN, OPEN_ASSIGNMENT, CREATE_APP_IDENTITY, OPENED_ID, NONE, PERSON_SHELL_CREATED;EMPLOYEE_PERSON_LINKED, NONE, ENROLLED_CREATED],
    [ACTIVE_ENROLLMENT, ENROLL_NEW_ACTIVE, S_LINK_MISSING_PERSON, ENROLL_LINK_EXISTING, import_ids;person_target;employee_expected;org_position_expected;episode;verifier_confirmation, ASSIGNMENT_INTENT, OPEN_START_DATE, NO_PRIMARY_OVERLAP, CURRENT_OPEN, OPEN_ASSIGNMENT, CREATE_APP_IDENTITY, OPENED_ID, NONE, EMPLOYEE_PERSON_LINKED, NONE, ENROLLED_CREATED],
    [BOTH, VERIFY_CONSISTENT, S_CONSISTENT, VERIFY_NOOP, complete_expected_state;verifier_confirmation, VERIFICATION_EVIDENCE, NO_DATE_MUTATION, NO_MUTATION, NO_MUTATION, NONE, NONE, NONE, NONE, NONE, NONE, ALREADY_CONSISTENT],
    [EXISTING_CARD_REPAIR, LINK_AND_OPEN_MISSING_ASSIGNMENT, S_UNLINKED_NO_PRIMARY_P0_WITH_INTENT, COMPOSITE_LINK_AND_OPEN_P0, employee_target;employee_expected;person_create_input;episode;org_position_expected;verifier_confirmation;import_ids, ASSIGNMENT_INTENT, OPEN_START_DATE, NO_PRIMARY_OVERLAP, CURRENT_OPEN, OPEN_ASSIGNMENT, CREATE_APP_IDENTITY, OPENED_ID, NONE, PERSON_SHELL_CREATED;EMPLOYEE_PERSON_LINKED, NONE, EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED],
    [EXISTING_CARD_REPAIR, LINK_AND_OPEN_MISSING_ASSIGNMENT, S_UNLINKED_NO_PRIMARY_P1_WITH_INTENT, COMPOSITE_LINK_AND_OPEN_P1, employee_target;employee_expected;person_target;episode;org_position_expected;verifier_confirmation;import_ids, ASSIGNMENT_INTENT, OPEN_START_DATE, NO_PRIMARY_OVERLAP, CURRENT_OPEN, OPEN_ASSIGNMENT, CREATE_APP_IDENTITY, OPENED_ID, NONE, EMPLOYEE_PERSON_LINKED, NONE, EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED],
    [EXISTING_CARD_REPAIR, LINK_ONLY, S_LINK_MISSING_PERSON, LINK_EXISTING_PERSON, employee_target;employee_expected;person_target, LINK_EVIDENCE, NO_DATE_MUTATION, NO_ASSIGNMENT_MUTATION, NO_ASSIGNMENT_MUTATION, NONE, NONE, NONE, NONE, EMPLOYEE_PERSON_LINKED, NONE, EMPLOYEE_PERSON_REPAIRED],
    [EXISTING_CARD_REPAIR, LINK_ONLY, S_LINK_MISSING_PERSON_ABSENT, CREATE_SHELL_AND_LINK, employee_target;employee_expected;person_create_input, PERSON_SHELL_EVIDENCE, NO_DATE_MUTATION, NO_ASSIGNMENT_MUTATION, NO_ASSIGNMENT_MUTATION, NONE, NONE, NONE, NONE, PERSON_SHELL_CREATED;EMPLOYEE_PERSON_LINKED, NONE, EMPLOYEE_PERSON_REPAIRED],
    [EXISTING_CARD_REPAIR, OPEN_MISSING_ASSIGNMENT, S_NO_NONVOID_PRIMARY, OPEN_MISSING, person_target;employee_target;episode;org_position_expected, ASSIGNMENT_INTENT, OPEN_START_DATE, NO_PRIMARY_OVERLAP, CURRENT_OPEN, OPEN_ASSIGNMENT, CREATE_APP_IDENTITY, OPENED_ID, NONE, NONE, NONE, MISSING_ASSIGNMENT_OPENED],
    [EXISTING_CARD_REPAIR, CORRECT_ERRONEOUS_RECORD, S_ERRONEOUS_VOID_ONLY, VOID_ERRONEOUS, original_assignment_id;original_row_version, CORRECTION_EVIDENCE, PRESERVE_RECORDED_DATES, REVALIDATE_FULL_CHAIN, BACKDATED_OR_CURRENT_CORRECTION, CORRECT_ASSIGNMENT_VOID_ONLY, NONE, POST_CURRENT_PRIMARY_OR_NULL, NONE, ASSIGNMENT_CORRECTED, NONE, ERRONEOUS_ASSIGNMENT_VOIDED],
    [EXISTING_CARD_REPAIR, CORRECT_ERRONEOUS_RECORD_WITH_REPLACEMENT, S_ERRONEOUS_WITH_REPLACEMENT, VOID_AND_REPLACE, original_assignment_id;original_row_version;replacement_episode;org_position_expected, CORRECTION_EVIDENCE, REPLACEMENT_EXACT_DATES, NO_PRIMARY_OVERLAP, BACKDATED_CURRENT_OR_FUTURE_REPLACEMENT, CORRECT_ASSIGNMENT_ATOMIC_REPLACEMENT, CREATE_APP_REPLACEMENT_IDENTITY, POST_CURRENT_PRIMARY_OR_NULL, NONE, ASSIGNMENT_CORRECTED, NONE, ERRONEOUS_ASSIGNMENT_REPLACED],
    [EXISTING_CARD_REPAIR, COMPLETE_REAL_LIFECYCLE_EPISODE, S_COMPLETE_NO_SUCCESSOR, COMPLETE_CLOSE, current_assignment_id;current_row_version;old_end_date, COMPLETION_EVIDENCE, old_end_date<D, NO_SUCCESSOR, BACKDATED_COMPLETION, CLOSE_ASSIGNMENT, NONE, NULL, NONE, NONE, NONE, LIFECYCLE_EPISODE_COMPLETED],
    [EXISTING_CARD_REPAIR, COMPLETE_REAL_LIFECYCLE_EPISODE_WITH_SUCCESSOR, S_COMPLETE_UNCHANGED_SUCCESSOR, COMPLETE_CONTINUOUS, current_assignment_id;current_row_version;successor_episode, COMPLETION_EVIDENCE, ADJACENT_TRANSITION, NO_GAP_NO_OVERLAP, CURRENT_CONTINUOUS, TRANSITION_ASSIGNMENT, CREATE_APP_IDENTITY, SUCCESSOR_ID, NONE, NONE, NONE, LIFECYCLE_EPISODE_COMPLETED_WITH_SUCCESSOR],
    [EXISTING_CARD_REPAIR, TRANSFER, S_CURRENT_TRANSFER, CURRENT_TRANSFER, current_assignment_id;current_row_version;successor_episode;org_expected, CHANGE_EVIDENCE, ADJACENT_TRANSITION, NO_GAP_NO_OVERLAP, BACKDATED_OR_CURRENT, TRANSITION_ASSIGNMENT, CREATE_APP_IDENTITY, SUCCESSOR_ID, NONE, NONE, TRANSFER, ASSIGNMENT_TRANSFERRED],
    [EXISTING_CARD_REPAIR, POSITION_CHANGE, S_CURRENT_POSITION_CHANGE, CURRENT_POSITION, current_assignment_id;current_row_version;successor_episode;position_expected, CHANGE_EVIDENCE, ADJACENT_TRANSITION, NO_GAP_NO_OVERLAP, BACKDATED_OR_CURRENT, TRANSITION_ASSIGNMENT, CREATE_APP_IDENTITY, SUCCESSOR_ID, NONE, NONE, POSITION_CHANGE, ASSIGNMENT_POSITION_CHANGED],
    [EXISTING_CARD_REPAIR, TRANSFER_AND_POSITION_CHANGE, S_CURRENT_TRANSFER_POSITION, CURRENT_TRANSFER_POSITION, current_assignment_id;current_row_version;successor_episode;org_position_expected, CHANGE_EVIDENCE, ADJACENT_TRANSITION, NO_GAP_NO_OVERLAP, BACKDATED_OR_CURRENT, TRANSITION_ASSIGNMENT, CREATE_APP_IDENTITY, SUCCESSOR_ID, NONE, NONE, TRANSFER, ASSIGNMENT_TRANSFERRED_AND_POSITION_CHANGED],
    [EXISTING_CARD_REPAIR, ASSIGNMENT_TERMS_CHANGE, S_CURRENT_TERMS_CHANGE, CURRENT_TERMS, current_assignment_id;current_row_version;successor_episode;changed_fields, CHANGE_EVIDENCE, ADJACENT_TRANSITION, NO_GAP_NO_OVERLAP, BACKDATED_OR_CURRENT, TRANSITION_ASSIGNMENT, CREATE_APP_IDENTITY, SUCCESSOR_ID, NONE, NONE, ASSIGNMENT_TERMS_CHANGE, ASSIGNMENT_TERMS_CHANGED],
    [EXISTING_CARD_REPAIR, PRESERVE_FUTURE_ASSIGNMENT, S_FUTURE_EXACT_PRESERVE, PRESERVE_FUTURE, future_assignment_id;future_row_version;complete_expected_episode, PRESERVATION_EVIDENCE, NO_DATE_MUTATION, NO_MUTATION, FUTURE_NOOP, NONE, NONE, NONE, NONE, NONE, NONE, FUTURE_ASSIGNMENT_PRESERVED],
    [EXISTING_CARD_REPAIR, TRANSITION_FUTURE_UNCHANGED_ASSIGNMENT, S_FUTURE_UNCHANGED_SUCCESSOR, FUTURE_UNCHANGED, current_assignment_id;current_row_version;successor_episode, CHANGE_EVIDENCE, ADJACENT_TRANSITION, NO_GAP_NO_OVERLAP, FUTURE_SCHEDULE, TRANSITION_ASSIGNMENT, CREATE_APP_IDENTITY, NONE, NONE, NONE, NONE, FUTURE_UNCHANGED_ASSIGNMENT_SCHEDULED],
    [EXISTING_CARD_REPAIR, TRANSITION_FUTURE_TRANSFER, S_FUTURE_TRANSFER, FUTURE_TRANSFER, current_assignment_id;current_row_version;successor_episode;org_expected, CHANGE_EVIDENCE, ADJACENT_TRANSITION, NO_GAP_NO_OVERLAP, FUTURE_SCHEDULE, TRANSITION_ASSIGNMENT, CREATE_APP_IDENTITY, NONE, NONE, NONE, TRANSFER, FUTURE_ASSIGNMENT_TRANSFER_SCHEDULED],
    [EXISTING_CARD_REPAIR, TRANSITION_FUTURE_POSITION_CHANGE, S_FUTURE_POSITION_CHANGE, FUTURE_POSITION, current_assignment_id;current_row_version;successor_episode;position_expected, CHANGE_EVIDENCE, ADJACENT_TRANSITION, NO_GAP_NO_OVERLAP, FUTURE_SCHEDULE, TRANSITION_ASSIGNMENT, CREATE_APP_IDENTITY, NONE, NONE, NONE, POSITION_CHANGE, FUTURE_ASSIGNMENT_POSITION_CHANGE_SCHEDULED],
    [EXISTING_CARD_REPAIR, TRANSITION_FUTURE_TRANSFER_AND_POSITION_CHANGE, S_FUTURE_TRANSFER_POSITION, FUTURE_TRANSFER_POSITION, current_assignment_id;current_row_version;successor_episode;org_position_expected, CHANGE_EVIDENCE, ADJACENT_TRANSITION, NO_GAP_NO_OVERLAP, FUTURE_SCHEDULE, TRANSITION_ASSIGNMENT, CREATE_APP_IDENTITY, NONE, NONE, NONE, TRANSFER, FUTURE_ASSIGNMENT_TRANSFER_POSITION_SCHEDULED],
    [EXISTING_CARD_REPAIR, TRANSITION_FUTURE_ASSIGNMENT_TERMS_CHANGE, S_FUTURE_TERMS_CHANGE, FUTURE_TERMS, current_assignment_id;current_row_version;successor_episode;changed_fields, CHANGE_EVIDENCE, ADJACENT_TRANSITION, NO_GAP_NO_OVERLAP, FUTURE_SCHEDULE, TRANSITION_ASSIGNMENT, CREATE_APP_IDENTITY, NONE, NONE, NONE, ASSIGNMENT_TERMS_CHANGE, FUTURE_ASSIGNMENT_TERMS_CHANGE_SCHEDULED]
  ],
  expected_counts: {expanded_total: 836, invalid_operation_mode: 396, unsupported_source_state: 20, allowed: 23, mode_source_state_mismatch: 397}
}
```

Expansion iterates operation × mode × state in the array order. It assigns
`INVALID_OPERATION_MODE` when compatibility is absent; otherwise assigns
`UNSUPPORTED_SOURCE_STATE` for `S_UNSUPPORTED`; otherwise expands `BOTH`, rejects duplicate
allowed tuples, and uses the matching allowed success or default
`MODE_SOURCE_STATE_MISMATCH`. Validation fails on unknown enum/token, a record with other
than 16 fields, duplicate tuple, two matching defaults, a conditional/empty field, count
mismatch, or any tuple without exactly one result. PG-62 and PG-118 consume this literal
block; they do not construct policy.

The validator also asserts exactly 2 operations, 19 modes, 22 states, 38 operation/mode
pairs, 20 compatible pairs, 22 physical allowed records and 23 records after the one
`BOTH` expansion; zero unknown members/enums/tokens, zero duplicate AST/tuple, zero
unmatched tuple, and exactly one result for every expanded tuple. It evaluates at least
one valid-common vector to `S_UNSUPPORTED`, proves that the invalid/unsupported/mismatch
defaults are disjoint, and compares the canonical bytes from two independent parsers.

Fixture tokens are closed by the following literal registry; no token means “implementation
decides.” Predicate operators map `NOT` to `!`, `AND` to `&&`, `OR` to `||`, `EQ` to `=`,
`LT` to `<`, `LTE` to `<=`, `GT` to `>`, and `GTE` to `>=`. `D` is the one fixed-UTC+05
business DATE computed from `transaction_timestamp()` by §5.1; the singleton watermark is
usable only when its `effective_date=D`. `T` is the explicit locked assignment row with matching ID
and expected `row_version`. `NONVOID(T)` is true exactly when persisted
`T.lifecycle_status IS NOT NULL AND T.lifecycle_status <> 'voided'`; `voided` is the only
void lifecycle value and SQL NULL fails `valid-common`. `CUR(T)` means `NONVOID(T)` and T
is the unique primary with non-NULL `start_date`, `start_date<=D`, and
`end_date IS NULL OR end_date>=D`. `FUT(T)` means `NONVOID(T)`, non-NULL
`T.start_date`, and `T.start_date>D`; it is false for a future row whose lifecycle is
`voided`. No function reads request mode or desired outcome.
`EVIDENCE_EXACT(T)` means the locked §6 evidence record identifies T's ID and row version
and its fingerprint equals the trusted request fingerprint. `ANY_PRECEDING_21_PREDICATE`
means the OR, in fixture order, of the twenty-one preceding predicate ASTs. The remaining
predicate primitives `E0/E1`, `P0/P1`, `L0/L1`, `A0`, `SUCCESSOR`, `EXACT_FINAL_STATE`,
`EXACT_SUBMITTED_TARGET`, `COMPLETE_NONOVERLAPPING_REPLACEMENT`,
`COMPLETE_CONFIRMED_ASSIGNMENT_INTENT`, `delta`, `intent`, and
`valid-common` are exactly the finite cardinality/tuple definitions in the table above;
none reads desired mode outcome.

| Token family | Token | Literal semantics |
|---|---|---|
| date | `OPEN_START_DATE` | submitted `start_date<=D` and `end_date IS NULL OR end_date>=D` |
| date | `NO_DATE_MUTATION` | no assignment date column may change |
| date | `PRESERVE_RECORDED_DATES` | void target retains OLD start/end using `IS NOT DISTINCT FROM` |
| date | `REPLACEMENT_EXACT_DATES` | replacement start/end equal trusted request; end NULL or >= start |
| date | `old_end_date<D` | `old_end_date>=T.start_date AND old_end_date<D` |
| date | `ADJACENT_TRANSITION` | transition > T.start; predecessor end=transition-1 day; successor start=transition |
| gap/overlap | `NO_PRIMARY_OVERLAP` | §5.3 exclusion predicate is false after proposed command |
| gap/overlap | `NO_GAP_NO_OVERLAP` | exact adjacency plus no §5.3 overlap |
| gap/overlap | `REVALIDATE_FULL_CHAIN` | lock/recheck every non-void primary episode; no changed non-target row |
| gap/overlap | `NO_SUCCESSOR` | every successor/replacement request member is NULL and no successor INSERT occurs |
| gap/overlap | `NO_MUTATION` / `NO_ASSIGNMENT_MUTATION` | respectively no business DML / no assignment or reconciliation DML |
| temporal | `CURRENT_OPEN` | inserted episode is eligible at D and reconciled immediately |
| temporal | `BACKDATED_OR_CURRENT_CORRECTION` | T starts <=D; recorded dates preserved; post-command D projection recomputed |
| temporal | `BACKDATED_CURRENT_OR_FUTURE_REPLACEMENT` | replacement dates are exact; start<=D recomputes D projection, start>D leaves current projection unchanged; the one `POST_CURRENT_PRIMARY_OR_NULL` call covers both |
| temporal | `BACKDATED_COMPLETION` | `T.start_date<=old_end_date<D`; no successor; reconcile SQL NULL |
| temporal | `CURRENT_CONTINUOUS` | `T.start_date<transition_date<=D`; exact adjacency; successor reconciled now |
| temporal | `BACKDATED_OR_CURRENT` | `T.start_date<transition_date<=D`; intervening/later episodes only validated, never changed |
| temporal | `FUTURE_NOOP` | explicit future T and exact submitted tuple; zero DML |
| temporal | `FUTURE_SCHEDULE` | `transition_date>D`; predecessor remains current through transition-1; successor active lifecycle/false flag; no immediate reconciliation |
| evidence | `ASSIGNMENT_INTENT`, `VERIFICATION_EVIDENCE`, `LINK_EVIDENCE`, `PERSON_SHELL_EVIDENCE`, `CORRECTION_EVIDENCE`, `COMPLETION_EVIDENCE`, `CHANGE_EVIDENCE`, `PRESERVATION_EVIDENCE` | the exact operation/mode-specific §6 evidence allowlist and fingerprint; any other evidence type rejects before classification |
| C2 | `OPEN_ASSIGNMENT`, `CORRECT_ASSIGNMENT_VOID_ONLY`, `CORRECT_ASSIGNMENT_ATOMIC_REPLACEMENT`, `CLOSE_ASSIGNMENT`, `TRANSITION_ASSIGNMENT` | the exact caller-owned C2 commands in §§3.2,4,5; `NONE` prohibits a C2 call |
| adoption | `CREATE_APP_IDENTITY`, `CREATE_APP_REPLACEMENT_IDENTITY` | respectively §4 direct identity or same-identity atomic replacement; `NONE` prohibits create/adopt |
| reconciliation | `OPENED_ID`, `SUCCESSOR_ID` | exactly one caller-owned reconciliation with the inserted/adopted ID |
| reconciliation | `NULL` | exactly one caller-owned reconciliation with SQL NULL |
| reconciliation | `POST_CURRENT_PRIMARY_OR_NULL` | exactly one call with unique post-command primary eligible at D, else SQL NULL; never conditional |
| event | any named canonical/personnel/Employee event | exactly one event with the §5.4/§11 payload; `NONE` prohibits it; semicolon means each listed event exactly once |

Required-input identifiers expand before completeness checking by this closed registry;
the right side contains exact §8.1 trusted request members and JSON null remains an
explicit value, never omission:

| Input identifier | Exact expansion |
|---|---|
| `import_ids` | `import_batch_ids;import_row_ids;normalized_record_ids` |
| `person_target` | `target_person_id;target_person_expected_state_hash;identity_type;identity_fingerprint_profile_id;identity_fingerprint_key_id;identity_fingerprint` |
| `person_create_input` | `target_person_id` and `target_person_expected_state_hash` must both be JSON null; top-level `identity_type;identity_fingerprint_profile_id;identity_fingerprint_key_id;identity_fingerprint;identity_input_binding_profile_id;identity_input_binding_key_id;identity_input_binding_verifier` are non-null and byte-equal to the exact non-null `person_shell_create_intention` object in §8.1 |
| `employee_target` | `target_employee_id` |
| `employee_expected` | `target_employee_expected_state_hash;identity_expected_state_hash` |
| `org_expected` | `org_unit_id;org_unit_normalized_stable_code;operator_confirmed_normalized_org_name` |
| `position_expected` | `position_id;operator_confirmed_normalized_position_name` |
| `org_position_expected` | union of `org_expected` and `position_expected` in the preceding order |
| `episode` | `org_unit_id;position_id;employment_type;rate;is_primary;start_date;end_date` |
| `replacement_episode` | `org_unit_id;position_id;employment_type;rate;is_primary;replacement_start_date;replacement_end_date` |
| `successor_episode` | `org_unit_id;position_id;employment_type;rate;is_primary;transition_date` |
| `complete_expected_episode` | `future_assignment_id;future_assignment_expected_version;org_unit_id;position_id;employment_type;rate;is_primary;start_date;end_date` |
| `complete_expected_state` | `target_employee_id;target_employee_expected_state_hash;target_person_id;target_person_expected_state_hash;identity_expected_state_hash;original_assignment_id;original_assignment_expected_version;current_assignment_id;current_assignment_expected_version;future_assignment_id;future_assignment_expected_version;replacement_target_assignment_id;replacement_target_expected_version;org_unit_id;org_unit_normalized_stable_code;operator_confirmed_normalized_org_name;position_id;operator_confirmed_normalized_position_name;employment_type;rate;is_primary;start_date;end_date;old_end_date;transition_date;replacement_start_date;replacement_end_date;changed_fields` |
| `verifier_confirmation` | `verifier_user_id;confirmation_at;confirmation_reference` |
| `original_row_version` | `original_assignment_expected_version` |
| `current_row_version` | `current_assignment_expected_version` |
| `future_row_version` | `future_assignment_expected_version` |
| `changed_fields` and every raw identifier already named in §8.1 | that one exact request member |

Action IDs have no hidden behavior: each identifies its complete sixteen-column allowed
record. The expansion above is recursive only for `org_position_expected` and terminates
after one step; fields are de-duplicated by first occurrence. Required values may not be
defaulted or inferred, and an unknown identifier fails parsing.

There is one complete error precedence. After request decoding, preview/apply performs
authentication → authorization → read-only bounded `REQUEST_COMPLETENESS`; for composite
mode this phase returns `ASSIGNMENT_INTENT_INCOMPLETE` for the first absent/unconfirmed
§6 decision, before idempotency-row INSERT or any other write. It then performs scoped
idempotency lookup. For CREATE requests selected
by that lookup, the server then derives the §8.1 replay verifier from the **actually
submitted authenticated raw IIN** and the stored caller/context/key scope; only a matching
verifier may release a committed result. A mismatch returns
`IDEMPOTENCY_IDENTITY_INPUT_CONFLICT`; an unavailable or revoked verifier key returns its
exact §8.1 binding-key code. Only after that check may `IDEMPOTENCY_KEY_REUSED` or a
matching committed replay return; replay still does not parse the preview token. LINK
requests require all three binding columns NULL and have no raw-IIN binding step. On a replay
miss it performs token signature/purpose/time validation and the remaining ordered
`valid-common` gate: `PERSON_TARGET_INTENT_CONFLICT`,
`PERSON_SHELL_FIO_INVALID`, and `PERSON_SHELL_FIO_MISMATCH` → fingerprint profile/key syntax
and retained-key verification → identity/import/rehire conditions → explicit target existence → target lifecycle
(`lifecycle_status='voided'` returns `ASSIGNMENT_TARGET_VOIDED`) → expected `row_version`
→ `ACTIVE_STATE_STALE` → locked watermark → locked position
(`STALE_POSITION_REFERENCE`) → other `STALE_EXPECTED_STATE` → timeline/date checks.
For R13 the generic `ACTIVE_STATE_STALE → locked watermark` wording above is expanded
normatively by §5.1 to `ACTIVE_STATE_SCHEMA_UNAVAILABLE`,
`ACTIVE_STATE_WATERMARK_INVALID`, `ACTIVE_STATE_STALE`, then
`ACTIVE_STATE_FUTURE`; only a valid row at `effective_date=D` continues. The complete
§6.1 evidence validation follows the Person-resolution gate and precedes successful
classification. The first failure returns its existing stable code and classification
does not run.

Before token issuance, personnel-order scope structural validation precedes digest
construction and returns `ORDER_EVIDENCE_SCOPE_INVALID`. On apply of that valid token,
scope absence, malformed replacement, membership or generation drift occupies the single
“other `STALE_EXPECTED_STATE`” slot above; it is never re-run as the preview structural
error.

Only after `valid-common=true` does fixture precedence apply: operation/mode compatibility
→ `INVALID_OPERATION_MODE`; classify exactly one state; `S_UNSUPPORTED` →
`UNSUPPORTED_SOURCE_STATE`; allowed lookup; compatible supported unlisted →
`MODE_SOURCE_STATE_MISMATCH`; otherwise the single listed outcome. Initial preview
position ID/name inequality remains `POSITION_NAME_MISMATCH` before token issuance. Apply
never reclassifies a post-preview rename as that code. Thus `valid-common=false` always has
a stable pre-classification result and never leaves a snapshot outside all states. After
one supported state is known but before releasing its proposed outcome, the exact §6.2
state/mode/reason row is validated; mismatch returns `REASON_MODE_INCOMPATIBLE`.

Protocol races have these deterministic outcomes independently of the business-state rows:

| Protocol state | Normative outcome |
|---|---|
| exact non-void application key owner, compatible episode | lock/adopt; `ASSIGNMENT_ADOPTED_EXACT_KEY`; no insert |
| exactly one compatible semantic non-void application candidate | lock/adopt; `ASSIGNMENT_ADOPTED_SEMANTIC`; no insert |
| zero semantic candidate | C2 inserts the canonical row; `CANONICAL_ASSIGNMENT_INSERTED` |
| multiple candidates, stale episode revision, or contradictory owner | respectively `ASSIGNMENT_ADOPTION_AMBIGUOUS`, `ADOPTION_STALE_APPLICATION_EPISODE`, or `ASSIGNMENT_ADOPTION_CONFLICT`; rollback; no insert |
| two canonical events concurrently adopt one application row | Person-scope serialization; winner adopts; loser rereads and returns `ASSIGNMENT_ADOPTION_CONFLICT`; no parallel assignment |
| repeated adoption by the same canonical event/key | no mutation; `ASSIGNMENT_ADOPTION_REPLAYED` |
| first request for an unused idempotency key | execute once; return the business row's success code |
| concurrent same-key/same-business-request | one execution; waiter returns stored result with `replayed=true`, code unchanged |
| committed same-key replay after preview expiry | stored result with `replayed=true`, code unchanged; no token expiry/state read |
| same key/different expanded business digest | `IDEMPOTENCY_KEY_REUSED`; no mutation |

---

## 3. Domain ports

### 3.1. ADR-048 Person Create-or-Link port

The port receives a caller-owned PostgreSQL connection and held identity lock. It:

- requires valid 12-digit IIN for an enrollment-created Shell;
- matches exact canonical IIN only, never name;
- creates one `source='enrollment'`, `match_key='iin:{iin}'` Shell when none exists;
- returns `CREATED | LINKED | ALREADY_LINKED` and `person_id`;
- refuses multiple candidates, merged targets, drift, or conflicting Employee link;
- does not create Employee, assignment, link, Contact, or import binding;
- opens/commits/rolls back no transaction.

Full IIN is usable only inside the transaction. Outside it, only presence, last four when
needed, or environment-scoped HMAC identity fingerprint is allowed.

### 3.2. Strict C2 transactional port

The orchestrator must not call the current batch `sync_personnel_events_tx` wrapper. C2
must expose `execute_assignment_command_tx(conn, command)` using the same canonical C2
lifecycle primitives. It:

- uses the caller connection and no owned transaction;
- supports `OPEN_ASSIGNMENT`, `CLOSE_ASSIGNMENT`, `TRANSITION_ASSIGNMENT`,
  `CORRECT_ASSIGNMENT`;
- accepts only a verified active numeric org-unit ID and an existing numeric
  `public.positions.position_id`; position validity is the locked ID/name contract in §12.3
  because the actual `positions` schema has no activity/version column;
- never chooses fallback org, creates position from `position_raw`, uses `date.today()`,
  or supplies default rate/other кадровые values;
- requires all relevant effective dates/rate;
- applies §§4–5 identity/timeline rules;
- fails fast, never marks a batch item failed and continues;
- returns exact opened/closed/voided/adopted IDs;
- propagates every error for rollback by the caller.

This is an application-facing port to C2 authority, not another lifecycle implementation.

### 3.3. Transactional reconciliation port

The existing public `reconcile_employee_primary_assignment` wrapper is forbidden inside
the orchestrator. A new
`reconcile_employee_primary_assignment_tx(conn, expected_employee_id,
expected_person_id, expected_assignment_id_or_null)`:

- uses only caller connection, no nested connection/transaction/post-commit read;
- verifies all expected IDs under §9 locks;
- accepts `expected_assignment_id` as either one positive assignment ID or NULL according
  to the exact C2 command result;
- for a non-NULL ID, requires exactly one operational current active primary assignment
  equal to it and projects its name/org/position/rate/dates;
- for NULL, requires zero operational current active primary assignments and clears only
  assignment-derived Employee org/position/rate/dates, preserving identity, operational
  status, and absence state;
- refuses ambiguity, a non-NULL assignment other than the current C2 result, or absence
  when a non-NULL result was expected;
- returns changed fields and creates no assignment/history event.

Failure is fatal. Contact likewise uses caller connection, runs last, and creates no
identity or personnel history.

---

## 4. Application assignment identity and later C2 adoption

### 4.1. Exact JCS identity

The payload has exactly seven members and is JSON, not pseudocode. This example uses
deliberately synthetic IDs unrelated to either first-batch person and is a valid pre-JCS
value (JCS will sort member names):

```json
{
  "version": "person-assignment-business-v1",
  "person_id": "9000001",
  "employment_type": "primary",
  "is_primary": true,
  "org_unit_id": "9000002",
  "position_id": "9000003",
  "start_date": "2099-01-01"
}
```

`version`, `person_id`, `employment_type`, `org_unit_id`, `position_id`, and
`start_date` are JSON strings; `is_primary` is a JSON boolean. IDs are canonical
positive base-10 strings matching `^[1-9][0-9]*$` with no sign or leading zero.
`employment_type` is one exact lowercase database enum value (`primary | part_time |
internal_combo | external | locum`), with no whitespace/case coercion.
`start_date` is the real PostgreSQL DATE rendered exactly `YYYY-MM-DD`. Unicode strings
are accepted only after application validation; JCS performs no Unicode normalization,
so the validated code point sequence is hashed unchanged. Rate, end date, names, and
free text are excluded because they are mutable episode facts, not application identity.
No eighth member is accepted. The exact JCS UTF-8/ASCII bytes for this fixture are:

```text
{"employment_type":"primary","is_primary":true,"org_unit_id":"9000002","person_id":"9000001","position_id":"9000003","start_date":"2099-01-01","version":"person-assignment-business-v1"}
```

```text
jcs_bytes = UTF-8(RFC8785-JCS(payload))
business_identity_hash = lowercase_hex(SHA-256(jcs_bytes))
application_assignment_key = app:v1: + business_identity_hash
```

The fixture hash is
`8c0f911bacab0d6ecd2b5b8cbfb9e667e9769d300aec89e454fef39e44124a76`; its exact key is
`app:v1:8c0f911bacab0d6ecd2b5b8cbfb9e667e9769d300aec89e454fef39e44124a76`.
Every key matches `^app:v1:[0-9a-f]{64}$` and has exactly 71 ASCII characters.

### 4.2. DDL-level key and provenance contract

The reviewed migration adds these exact columns to `public.person_assignments`. The
dedicated `assignment_origin_kind` is the only application-origin discriminator; existing
`source` retains its ADR-043 meaning. C2 canonical transfers may continue to persist
`source='transfer'` with `assignment_origin_kind IS NULL`.

| Column | PostgreSQL type | FK / rule |
|---|---|---|
| `assignment_origin_kind` | `TEXT NULL` | only NULL or exact `personnel_orchestration` |
| `application_assignment_key` | `TEXT NULL` | immutable; format check above |
| `business_identity_hash` | `CHAR(64) NULL` | lowercase hex check |
| `origin_operation_id` | `BIGINT NULL` | FK operations `operation_id ON DELETE RESTRICT` |
| `evidence_reference_fingerprint` | `CHAR(64) NULL` | lowercase hex check |
| `replaces_assignment_id` | `BIGINT NULL` | self-FK `assignment_id ON DELETE RESTRICT`; not self |
| `canonical_adopted_by_event_id` | `BIGINT NULL` | FK `hr_personnel_change_events(personnel_event_id) ON DELETE RESTRICT` |
| `canonical_adopted_at` | `TIMESTAMPTZ NULL` | database time; paired with adopted event |
| `row_version` | `BIGINT NOT NULL DEFAULT 1` | positive; every assignment UPDATE increments once |

For an unadopted application row, the existing mandatory `assignment_key` is not the
reusable business identity key. C2 sets it exactly to
`app-row:v1:<origin_operation_id>:<business_identity_hash>`, where the operation ID is a
positive base-10 string. A correction replacement therefore has a different physical row
key even when it legitimately reuses `application_assignment_key`/hash. Adoption alone
changes `assignment_key` to the canonical C2 key.

```sql
ALTER TABLE public.person_assignments
  ADD COLUMN assignment_origin_kind TEXT NULL,
  ADD COLUMN application_assignment_key TEXT NULL,
  ADD COLUMN business_identity_hash CHAR(64) NULL,
  ADD COLUMN origin_operation_id BIGINT NULL,
  ADD COLUMN evidence_reference_fingerprint CHAR(64) NULL,
  ADD COLUMN replaces_assignment_id BIGINT NULL,
  ADD COLUMN canonical_adopted_by_event_id BIGINT NULL,
  ADD COLUMN canonical_adopted_at TIMESTAMPTZ NULL,
  ADD COLUMN row_version BIGINT NOT NULL DEFAULT 1,
  ADD CONSTRAINT fk_pa_origin_operation FOREIGN KEY (origin_operation_id)
    REFERENCES public.personnel_orchestration_operations(operation_id) ON DELETE RESTRICT,
  ADD CONSTRAINT fk_pa_replaces_assignment FOREIGN KEY (replaces_assignment_id)
    REFERENCES public.person_assignments(assignment_id) ON DELETE RESTRICT,
  ADD CONSTRAINT fk_pa_canonical_adopt_event FOREIGN KEY (canonical_adopted_by_event_id)
    REFERENCES public.hr_personnel_change_events(personnel_event_id) ON DELETE RESTRICT,
  ADD CONSTRAINT chk_pa_row_version CHECK (row_version > 0),
  ADD CONSTRAINT chk_pa_application_provenance CHECK (
    (
      assignment_origin_kind IS NULL
      AND application_assignment_key IS NULL
      AND business_identity_hash IS NULL
      AND origin_operation_id IS NULL
      AND evidence_reference_fingerprint IS NULL
      AND replaces_assignment_id IS NULL
      AND canonical_adopted_by_event_id IS NULL
      AND canonical_adopted_at IS NULL
    ) OR (
      assignment_origin_kind IS NOT NULL
      AND assignment_origin_kind = 'personnel_orchestration'
      AND application_assignment_key IS NOT NULL
      AND application_assignment_key ~ '^app:v1:[0-9a-f]{64}$'
      AND business_identity_hash IS NOT NULL
      AND business_identity_hash ~ '^[0-9a-f]{64}$'
      AND application_assignment_key = 'app:v1:' || business_identity_hash
      AND origin_operation_id IS NOT NULL
      AND evidence_reference_fingerprint IS NOT NULL
      AND evidence_reference_fingerprint ~ '^[0-9a-f]{64}$'
      AND source IN ('enrollment', 'correction', 'transfer')
      AND (
        (
          canonical_adopted_by_event_id IS NULL
          AND assignment_key = ('app-row:v1:' || origin_operation_id::text || ':' || business_identity_hash)
        ) OR (
          canonical_adopted_by_event_id IS NOT NULL
          AND assignment_key <> ('app-row:v1:' || origin_operation_id::text || ':' || business_identity_hash)
        )
      )
    )
  ),
  ADD CONSTRAINT chk_pa_adoption_pair CHECK (
    (canonical_adopted_by_event_id IS NULL AND canonical_adopted_at IS NULL)
    OR
    (canonical_adopted_by_event_id IS NOT NULL AND canonical_adopted_at IS NOT NULL)
  ),
  ADD CONSTRAINT chk_pa_replacement_not_self CHECK (
    replaces_assignment_id IS NULL OR replaces_assignment_id <> assignment_id
  );
```

The application branch has four and only four persisted shapes:

| Shape | Required values |
|---|---|
| direct application episode | marker/key/hash/origin/evidence non-NULL; replacement, adoption pair and canonical snapshot/entry NULL; physical `app-row:v1:` key; `row_version=1`, lifecycle `active` |
| correction replacement | same NULL adoption/canonical shape, but `replaces_assignment_id` is the locked voided application original with the same Person/key/hash/identity tuple; `row_version=1`, lifecycle `active` or `closed` |
| semantically or exact-key adopted | either preceding shape; adoption event/time both non-NULL; canonical `assignment_key`; every application identity/origin/lineage value retained |
| corrected/voided original | either adopted or unadopted shape with lifecycle `voided`; every provenance value retained unchanged |

This exact trigger is part of the reviewed DDL. An UPDATE already holds the target tuple
lock. The replacement INSERT obtains the original tuple `FOR UPDATE`; C2 has already taken
the Person scope and assignment locks in §9 order, so the trigger never introduces a new
order or deadlock inversion.

```sql
CREATE FUNCTION public.pa_application_provenance_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  original_row public.person_assignments%ROWTYPE;
  adoption_transition boolean;
  allowed_transition boolean;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF NEW.assignment_origin_kind IS DISTINCT FROM OLD.assignment_origin_kind
       OR NEW.application_assignment_key IS DISTINCT FROM OLD.application_assignment_key
       OR NEW.business_identity_hash IS DISTINCT FROM OLD.business_identity_hash
       OR NEW.origin_operation_id IS DISTINCT FROM OLD.origin_operation_id
       OR NEW.evidence_reference_fingerprint IS DISTINCT FROM OLD.evidence_reference_fingerprint
       OR NEW.replaces_assignment_id IS DISTINCT FROM OLD.replaces_assignment_id THEN
      RAISE EXCEPTION 'APPLICATION_PROVENANCE_IMMUTABLE' USING ERRCODE = '23514';
    END IF;
    -- A legacy/canonical row cannot become application-origin by UPDATE.
    IF OLD.assignment_origin_kind IS NULL AND
       (NEW.assignment_origin_kind IS NOT NULL
        OR NEW.canonical_adopted_by_event_id IS NOT NULL
        OR NEW.canonical_adopted_at IS NOT NULL) THEN
      RAISE EXCEPTION 'APPLICATION_PROVENANCE_IMMUTABLE' USING ERRCODE = '23514';
    END IF;

    IF OLD.assignment_origin_kind = 'personnel_orchestration' THEN
      -- Complete immutable episode-definition set from the deployed assignment schema.
      IF NEW.assignment_id IS DISTINCT FROM OLD.assignment_id
         OR NEW.person_id IS DISTINCT FROM OLD.person_id
         OR NEW.org_unit_id IS DISTINCT FROM OLD.org_unit_id
         OR NEW.position_id IS DISTINCT FROM OLD.position_id
         OR NEW.department_id IS DISTINCT FROM OLD.department_id
         OR NEW.employment_type IS DISTINCT FROM OLD.employment_type
         OR NEW.rate IS DISTINCT FROM OLD.rate
         OR NEW.start_date IS DISTINCT FROM OLD.start_date
         OR NEW.is_primary IS DISTINCT FROM OLD.is_primary
         OR NEW.source IS DISTINCT FROM OLD.source
         OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'APPLICATION_ASSIGNMENT_TRANSITION_INVALID' USING ERRCODE = '23514';
      END IF;

      adoption_transition :=
        OLD.canonical_adopted_by_event_id IS NULL
        AND OLD.canonical_adopted_at IS NULL
        AND OLD.canonical_snapshot_id IS NULL
        AND OLD.canonical_entry_id IS NULL
        AND NEW.canonical_adopted_by_event_id IS NOT NULL
        AND NEW.canonical_adopted_at IS NOT NULL
        AND NEW.canonical_snapshot_id IS NOT NULL
        AND NEW.canonical_entry_id IS NOT NULL
        AND NEW.assignment_key IS DISTINCT FROM OLD.assignment_key;

      IF adoption_transition THEN
        allowed_transition :=
          OLD.lifecycle_status <> 'voided'
          AND NEW.lifecycle_status IS NOT DISTINCT FROM OLD.lifecycle_status
          AND NEW.active_flag IS NOT DISTINCT FROM OLD.active_flag
          AND NEW.end_date IS NOT DISTINCT FROM OLD.end_date;
      ELSE
        IF NEW.canonical_adopted_by_event_id IS DISTINCT FROM OLD.canonical_adopted_by_event_id
           OR NEW.canonical_adopted_at IS DISTINCT FROM OLD.canonical_adopted_at
           OR NEW.canonical_snapshot_id IS DISTINCT FROM OLD.canonical_snapshot_id
           OR NEW.canonical_entry_id IS DISTINCT FROM OLD.canonical_entry_id
           OR NEW.assignment_key IS DISTINCT FROM OLD.assignment_key THEN
          RAISE EXCEPTION 'APPLICATION_ADOPTION_IMMUTABLE' USING ERRCODE = '23514';
        END IF;

        allowed_transition :=
          -- boundary projection only
          (NEW.lifecycle_status IS NOT DISTINCT FROM OLD.lifecycle_status
           AND NEW.end_date IS NOT DISTINCT FROM OLD.end_date
           AND NEW.active_flag IS DISTINCT FROM OLD.active_flag)
          OR
          -- schedule one future inclusive end; C2 additionally validates it against watermark
          (OLD.lifecycle_status = 'active' AND NEW.lifecycle_status = 'active'
           AND OLD.end_date IS NULL AND NEW.end_date IS NOT NULL
           AND NEW.end_date >= NEW.start_date AND NEW.active_flag = OLD.active_flag)
          OR
          -- close the real episode
          (OLD.lifecycle_status = 'active' AND NEW.lifecycle_status = 'closed'
           AND NEW.end_date IS NOT NULL AND NEW.end_date >= NEW.start_date
           AND NEW.active_flag IS FALSE)
          OR
          -- correction/void preserves its recorded dates and all provenance
          (OLD.lifecycle_status IN ('active','closed') AND NEW.lifecycle_status = 'voided'
           AND NEW.end_date IS NOT DISTINCT FROM OLD.end_date
           AND NEW.active_flag IS FALSE);
      END IF;

      IF NOT allowed_transition
         OR NEW.row_version <> OLD.row_version + 1
         OR NEW.updated_at < OLD.updated_at THEN
        RAISE EXCEPTION 'APPLICATION_ASSIGNMENT_TRANSITION_INVALID' USING ERRCODE = '23514';
      END IF;
    END IF;
  END IF;

  IF TG_OP = 'INSERT' AND NEW.assignment_origin_kind = 'personnel_orchestration'
     AND (NEW.canonical_adopted_by_event_id IS NOT NULL
          OR NEW.canonical_adopted_at IS NOT NULL
          OR NEW.canonical_snapshot_id IS NOT NULL
          OR NEW.canonical_entry_id IS NOT NULL
          OR NEW.row_version <> 1
          OR (NEW.replaces_assignment_id IS NULL AND NEW.lifecycle_status <> 'active')
          OR (NEW.replaces_assignment_id IS NOT NULL
              AND NEW.lifecycle_status NOT IN ('active','closed'))) THEN
    RAISE EXCEPTION 'APPLICATION_ADOPTION_TRANSITION_INVALID' USING ERRCODE = '23514';
  END IF;
  IF TG_OP = 'INSERT' AND NEW.assignment_origin_kind = 'personnel_orchestration'
     AND NEW.replaces_assignment_id IS NOT NULL THEN
    SELECT * INTO original_row FROM public.person_assignments
    WHERE assignment_id = NEW.replaces_assignment_id FOR UPDATE;
    IF NOT FOUND
       OR original_row.person_id IS DISTINCT FROM NEW.person_id
       OR original_row.assignment_origin_kind IS DISTINCT FROM 'personnel_orchestration'
       OR original_row.lifecycle_status IS DISTINCT FROM 'voided'
       OR original_row.application_assignment_key IS DISTINCT FROM NEW.application_assignment_key
       OR original_row.business_identity_hash IS DISTINCT FROM NEW.business_identity_hash
       OR original_row.employment_type IS DISTINCT FROM NEW.employment_type
       OR original_row.is_primary IS DISTINCT FROM NEW.is_primary
       OR original_row.org_unit_id IS DISTINCT FROM NEW.org_unit_id
       OR original_row.position_id IS DISTINCT FROM NEW.position_id
       OR original_row.start_date IS DISTINCT FROM NEW.start_date
       OR original_row.origin_operation_id IS NOT DISTINCT FROM NEW.origin_operation_id THEN
      RAISE EXCEPTION 'APPLICATION_REPLACEMENT_CONFLICT' USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_pa_application_provenance_guard
BEFORE INSERT OR UPDATE ON public.person_assignments
FOR EACH ROW EXECUTE FUNCTION public.pa_application_provenance_guard();
```

The state machine above is closed. Direct application creation is INSERT with NULL
adoption/canonical links; semantic adoption is the single all-NULL → all-non-NULL
transition; boundary flag projection, one future-end schedule, lifecycle close, and
date-preserving void are the only later UPDATE shapes. A business change to Person,
organization, position, department, rate, employment type, primary role, start date or
source requires a new C2 successor/replacement episode. A canonical row cannot become an
application row by UPDATE, and no application row can lose its marker, identity, origin,
lineage, canonical snapshot/entry or adoption pair.

C2 performs replacement in one transaction and exact order: Person-scope lock; original
`FOR UPDATE`; original UPDATE to `voided`; replacement INSERT with `replaces_assignment_id`;
link/reconciliation/events; commit. Both partial unique indexes are immediate. The void
UPDATE releases the logical identity for the INSERT only within that uncommitted
transaction; no other transaction can observe an ownerless state, and rollback after the
void restores the original. Concurrent attempts block on the Person/original locks. At
the C2 port boundary, SQLSTATE `23505` for either application partial index and SQLSTATE
`23514` carrying `APPLICATION_REPLACEMENT_CONFLICT` are both rolled back,
followed by one locked owner reread, and mapped to the single non-retryable stable result
`APPLICATION_REPLACEMENT_CONFLICT`. No PostgreSQL exception text leaks as a second
business outcome.

No implication runs from `source` to `assignment_origin_kind`; a canonical
`source='transfer'` row satisfies the first branch. Every C2/application assignment UPDATE
uses `SET row_version = row_version + 1`; R1 disables writers that do not. Adoption never
rewrites source, origin marker, application key/hash, operation, or evidence fingerprint.

Uniqueness is exact and database-enforced:

```sql
CREATE UNIQUE INDEX uq_pa_assignment_key_ci
  ON public.person_assignments (lower(assignment_key));
CREATE UNIQUE INDEX uq_pa_application_assignment_key
  ON public.person_assignments (application_assignment_key)
  WHERE assignment_origin_kind = 'personnel_orchestration'
    AND lifecycle_status <> 'voided';
CREATE UNIQUE INDEX uq_pa_business_identity_hash
  ON public.person_assignments (business_identity_hash)
  WHERE assignment_origin_kind = 'personnel_orchestration'
    AND lifecycle_status <> 'voided';
```

The first scope preserves ADR-043/C2 identity. The application predicates permit an
atomic correction to void the erroneous owner and insert a proven replacement with the
same identity while forbidding two non-void owners. A voided row is never adoptable.
Preflight reports duplicates under all three exact predicates and blocks without repair.
A uniqueness violation is not idempotency until the owner is locked and proven equal in
event and episode identity.

### 4.3. Exact-key, semantic, and concurrent adoption

Only C2 performs adoption, under the Person assignment-scope lock and in the canonical
event transaction. It first locks any owner of incoming `canonical_entry_id` and
canonical `assignment_key`, then follows this exhaustive order:

1. If both are already owned by the same row and its adopted event equals the incoming
   event, return `ASSIGNMENT_ADOPTION_REPLAYED`. If ownership is split or belongs to a
   different adopted event, return `ASSIGNMENT_ADOPTION_CONFLICT`.
2. Search the partial-index population for the exact `application_assignment_key`
   supplied in canonical compatibility metadata. Exactly one compatible non-void row
   is adopted and returns `ASSIGNMENT_ADOPTED_EXACT_KEY`; an incompatible owner returns
   `ASSIGNMENT_ADOPTION_CONFLICT`.
3. If no exact application key is available, search equality on exactly
   `(person_id, employment_type, is_primary, org_unit_id, position_id, start_date)` among
   rows with `assignment_origin_kind='personnel_orchestration'` and
   `lifecycle_status <> 'voided'`, including adopted rows. Exactly one
   unowned row returns `ASSIGNMENT_ADOPTED_SEMANTIC`; exactly one row owned by this same
   event returns `ASSIGNMENT_ADOPTION_REPLAYED`; exactly one row owned by another event
   returns `ASSIGNMENT_ADOPTION_CONFLICT`; more than one returns
   `ASSIGNMENT_ADOPTION_AMBIGUOUS`. Only zero permits normal canonical insert.

Compatibility is not the six-column search alone. C2 locks the candidate and requires
canonical metadata to equal its `assignment_id`, `row_version`, `start_date`, nullable
`end_date`, `rate`, lifecycle status, and nullable `replaces_assignment_id`, plus the six
search fields. JSON null represents a NULL end/replacement. A timeline correction or any
mutation after event production changes `row_version` and returns
`ADOPTION_STALE_APPLICATION_EPISODE`; it may not fall through to another semantic row.
Contradictory replacement lineage returns `ASSIGNMENT_ADOPTION_CONFLICT`. Normalization or
a later correction therefore cannot attach a canonical event to the wrong episode.

Adoption atomically sets canonical entry/snapshot/adoption event/time, increments
`row_version`, and changes only `assignment_key`, retaining application key/hash/source/
origin/evidence. Correction replacement first voids and increments the original, then
inserts the replacement; the partial unique predicates release the voided owner before
the INSERT statement.

Two canonical events targeting one application row serialize on the Person scope. The
winner adopts and increments its version; the loser rereads and returns
`ASSIGNMENT_ADOPTION_CONFLICT`, rolls back, and does not insert. Replay of the winner is
the only adoption replay. Concurrent replacement/adoption serialize on the same Person
scope and assignment row. Approximate/name matching is forbidden. PG-20–24 and PG-81–86
prove exact, semantic, ambiguous, replay, JCS, canonical transfer, replacement,
concurrency, corrected-timeline, and wrong-episode behavior.

---

## 5. Assignment repair, timeline, and hard guarantee

### 5.1. Persisted-state model

Assignment intervals are inclusive `[start_date,end_date]`; NULL `end_date` is unbounded.
The lifecycle vocabulary retains its existing exact values and means:

- `active`: a real episode that C2 has opened and has not yet crossed its persisted close
  boundary or been voided. It may be future, operationally current, or scheduled to end;
- `closed`: a real completed episode whose inclusive `end_date` is earlier than the
  boundary writer's persisted effective date; `end_date` is mandatory and is never before start;
- `voided`: a row proven erroneous; original dates and values are retained, and it never
  participates in employment timeline or operational selection.

`active_flag` is a strictly maintained persisted projection, not a clock-driven fact and
not independent lifecycle authority. The project business-day authority is its existing
fixed UTC+5 contract. “Qyzylorda local day” is only a display label and does not introduce
a second timezone rule. Database computation is exactly:

```sql
business_date = ((transaction_timestamp() AT TIME ZONE 'UTC') + INTERVAL '5 hours')::date
```

For one C2 worker run with fixed `effective_date = business_date`:

```text
eligible(row, effective_date) =
  lifecycle_status = 'active'
  AND start_date <= effective_date
  AND (end_date IS NULL OR end_date >= effective_date)

active_flag = eligible(row, effective_date)
```

This equality is mandatory for primary and secondary rows after a successful boundary
run. In that same state, every `active` row has NULL end or `end_date >= effective_date`,
and every `closed` row has `end_date < effective_date`. Therefore true always means
lifecycle-active and date-eligible; false means future, closed, voided, or otherwise
ineligible for that fixed date. The exact supporting DDL is:

```sql
ALTER TABLE public.person_assignments
  ADD CONSTRAINT chk_pa_active_requires_active_lifecycle
    CHECK (NOT active_flag OR lifecycle_status = 'active'),
  ADD CONSTRAINT chk_pa_closed_requires_end
    CHECK (lifecycle_status <> 'closed' OR end_date IS NOT NULL);
-- Existing chk_pa_dates remains: end_date IS NULL OR end_date >= start_date.

CREATE TABLE public.person_assignment_activation_watermark (
  singleton BOOLEAN PRIMARY KEY,
  effective_date DATE NOT NULL,
  processed_at TIMESTAMPTZ NOT NULL,
  generation BIGINT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT chk_paaw_singleton CHECK (singleton IS TRUE),
  CONSTRAINT chk_paaw_generation CHECK (generation > 0),
  CONSTRAINT chk_paaw_timestamp_order CHECK (processed_at <= updated_at)
);

CREATE FUNCTION public.adr065_boundary_error_metadata_valid(p_value JSONB)
RETURNS BOOLEAN
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE
SET search_path=pg_catalog,public AS $$
DECLARE
  count_value NUMERIC;
BEGIN
  IF jsonb_typeof(p_value) IS DISTINCT FROM 'object' THEN
    RETURN FALSE;
  END IF;
  IF p_value - ARRAY['reason_code','conflicting_person_count','stale_component']
       <> '{}'::jsonb THEN
    RETURN FALSE;
  END IF;
  IF p_value ? 'reason_code' THEN
    IF jsonb_typeof(p_value->'reason_code') IS DISTINCT FROM 'string'
       OR length(p_value->>'reason_code') = 0 THEN
      RETURN FALSE;
    END IF;
  END IF;
  IF p_value ? 'stale_component' THEN
    IF jsonb_typeof(p_value->'stale_component') IS DISTINCT FROM 'string'
       OR length(p_value->>'stale_component') = 0 THEN
      RETURN FALSE;
    END IF;
  END IF;
  IF p_value ? 'conflicting_person_count' THEN
    IF jsonb_typeof(p_value->'conflicting_person_count') IS DISTINCT FROM 'number' THEN
      RETURN FALSE;
    END IF;
    BEGIN
      count_value := (p_value->>'conflicting_person_count')::NUMERIC;
    EXCEPTION
      WHEN invalid_text_representation OR numeric_value_out_of_range THEN
        RETURN FALSE;
    END;
    IF count_value < 0 OR trunc(count_value) <> count_value
       OR count_value > 9223372036854775807::NUMERIC THEN
      RETURN FALSE;
    END IF;
  END IF;
  RETURN TRUE;
END $$;

CREATE FUNCTION public.adr065_boundary_outcome_metadata_valid(
  p_outcome TEXT, p_value JSONB
) RETURNS BOOLEAN
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE
SET search_path=pg_catalog,public AS $$
DECLARE n BIGINT;
BEGIN
  IF public.adr065_boundary_error_metadata_valid(p_value) IS NOT TRUE THEN
    RETURN FALSE;
  END IF;
  CASE p_outcome
    WHEN 'BOUNDARY_RUN_ADVANCED' THEN RETURN p_value = '{}'::jsonb;
    WHEN 'BOUNDARY_RUN_DUPLICATE' THEN RETURN p_value = '{}'::jsonb;
    WHEN 'BOUNDARY_RUN_CANCELLED' THEN
      RETURN p_value = jsonb_build_object('reason_code','scheduler_cancelled');
    WHEN 'BOUNDARY_RUN_OUT_OF_ORDER' THEN
      RETURN p_value = jsonb_build_object('reason_code','out_of_order');
    WHEN 'BOUNDARY_RUN_FUTURE_DATE' THEN
      RETURN p_value = jsonb_build_object('reason_code','future_date');
    WHEN 'BOUNDARY_WATERMARK_INVALID' THEN
      RETURN p_value = jsonb_build_object(
        'reason_code','watermark_invalid','stale_component','watermark');
    WHEN 'BOUNDARY_DUPLICATE_PROJECTION_INCONSISTENT' THEN
      IF (p_value - ARRAY['reason_code','stale_component','conflicting_person_count']) <> '{}'::jsonb
         OR p_value->>'reason_code' <> 'projection_inconsistent'
         OR p_value->>'stale_component' NOT IN ('assignment','assignment_link','employee_projection')
         OR NOT (p_value ?& ARRAY['reason_code','stale_component','conflicting_person_count']) THEN
        RETURN FALSE;
      END IF;
      n := (p_value->>'conflicting_person_count')::BIGINT;
      RETURN n >= 1;
    WHEN 'INVALID_SUCCESSOR_CHAIN' THEN
      IF (p_value - ARRAY['reason_code','stale_component','conflicting_person_count']) <> '{}'::jsonb
         OR p_value->>'reason_code' <> 'invalid_successor_chain'
         OR p_value->>'stale_component' <> 'assignment'
         OR NOT (p_value ?& ARRAY['reason_code','stale_component','conflicting_person_count']) THEN
        RETURN FALSE;
      END IF;
      n := (p_value->>'conflicting_person_count')::BIGINT;
      RETURN n >= 1;
    WHEN 'ACTIVE_PRIMARY_ASSIGNMENT_CONFLICT' THEN
      IF (p_value - ARRAY['reason_code','stale_component','conflicting_person_count']) <> '{}'::jsonb
         OR p_value->>'reason_code' <> 'active_primary_assignment_conflict'
         OR p_value->>'stale_component' <> 'assignment'
         OR NOT (p_value ?& ARRAY['reason_code','stale_component','conflicting_person_count']) THEN
        RETURN FALSE;
      END IF;
      n := (p_value->>'conflicting_person_count')::BIGINT;
      RETURN n >= 2;
    ELSE RETURN FALSE;
  END CASE;
EXCEPTION
  WHEN invalid_text_representation OR numeric_value_out_of_range THEN RETURN FALSE;
END $$;

CREATE TABLE public.person_assignment_boundary_runs (
  boundary_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scheduler_run_id UUID NOT NULL UNIQUE,
  scheduler_context_fingerprint CHAR(64) NOT NULL,
  target_effective_date DATE NOT NULL,
  run_status TEXT NOT NULL,
  attempted_at TIMESTAMPTZ NOT NULL,
  lease_owner_id UUID NOT NULL,
  lease_acquired_at TIMESTAMPTZ NOT NULL,
  lease_expires_at TIMESTAMPTZ NOT NULL,
  t1_started_at TIMESTAMPTZ NULL,
  recovery_count INTEGER NOT NULL DEFAULT 0,
  completed_at TIMESTAMPTZ NULL,
  outcome_code TEXT NULL,
  projection_consistent BOOLEAN NULL,
  watermark_before_date DATE NULL,
  watermark_before_generation BIGINT NULL,
  watermark_after_date DATE NULL,
  watermark_after_generation BIGINT NULL,
  service_actor TEXT NOT NULL,
  requested_by_user_id BIGINT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
  retry_of_boundary_run_id BIGINT NULL REFERENCES public.person_assignment_boundary_runs(boundary_run_id) ON DELETE RESTRICT,
  retry_ordinal INTEGER NOT NULL DEFAULT 0,
  error_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT chk_pabr_context CHECK ((scheduler_context_fingerprint ~ '^[0-9a-f]{64}$') IS TRUE),
  CONSTRAINT chk_pabr_status CHECK ((run_status IN ('STARTED','COMPLETED')) IS TRUE),
  CONSTRAINT chk_pabr_service_actor CHECK ((service_actor = 'assignment_boundary_worker') IS TRUE),
  CONSTRAINT chk_pabr_retry CHECK (((retry_of_boundary_run_id IS NULL AND retry_ordinal = 0)
    OR (retry_of_boundary_run_id IS NOT NULL AND retry_ordinal > 0)) IS TRUE),
  CONSTRAINT chk_pabr_recovery CHECK ((recovery_count >= 0) IS TRUE),
  CONSTRAINT chk_pabr_lease CHECK ((lease_acquired_at < lease_expires_at) IS TRUE),
  CONSTRAINT chk_pabr_error_metadata CHECK (
    public.adr065_boundary_error_metadata_valid(error_metadata) IS TRUE
  ),
  CONSTRAINT chk_pabr_completion CHECK (
    ((run_status = 'STARTED' AND completed_at IS NULL AND outcome_code IS NULL AND projection_consistent IS NULL)
    OR (run_status = 'COMPLETED' AND completed_at IS NOT NULL
      AND ((outcome_code = 'BOUNDARY_RUN_CANCELLED' AND t1_started_at IS NULL)
        OR (outcome_code <> 'BOUNDARY_RUN_CANCELLED' AND t1_started_at IS NOT NULL))
      AND outcome_code IN (
      'BOUNDARY_RUN_ADVANCED','BOUNDARY_RUN_DUPLICATE','BOUNDARY_DUPLICATE_PROJECTION_INCONSISTENT',
      'BOUNDARY_RUN_OUT_OF_ORDER','BOUNDARY_RUN_FUTURE_DATE','BOUNDARY_WATERMARK_INVALID',
      'INVALID_SUCCESSOR_CHAIN','ACTIVE_PRIMARY_ASSIGNMENT_CONFLICT','BOUNDARY_RUN_CANCELLED')))
      IS TRUE
  ),
  CONSTRAINT chk_pabr_projection_result CHECK (
    ((outcome_code = 'BOUNDARY_RUN_DUPLICATE' AND projection_consistent IS TRUE)
    OR (outcome_code = 'BOUNDARY_DUPLICATE_PROJECTION_INCONSISTENT' AND projection_consistent IS FALSE)
    OR (outcome_code IS DISTINCT FROM 'BOUNDARY_RUN_DUPLICATE'
        AND outcome_code IS DISTINCT FROM 'BOUNDARY_DUPLICATE_PROJECTION_INCONSISTENT'
        AND projection_consistent IS NULL)) IS TRUE
  ),
  CONSTRAINT chk_pabr_watermark_shape CHECK (
    ((run_status = 'STARTED' AND watermark_before_date IS NULL AND watermark_before_generation IS NULL
      AND watermark_after_date IS NULL AND watermark_after_generation IS NULL)
    OR (run_status = 'COMPLETED' AND outcome_code IN ('BOUNDARY_WATERMARK_INVALID','BOUNDARY_RUN_CANCELLED')
        AND watermark_before_date IS NULL AND watermark_before_generation IS NULL
        AND watermark_after_date IS NULL AND watermark_after_generation IS NULL)
    OR (run_status = 'COMPLETED' AND outcome_code = 'BOUNDARY_RUN_ADVANCED'
        AND watermark_before_date IS NOT NULL AND watermark_before_generation IS NOT NULL
        AND watermark_after_date = target_effective_date
        AND watermark_after_generation = watermark_before_generation + 1)
    OR (run_status = 'COMPLETED' AND outcome_code NOT IN ('BOUNDARY_WATERMARK_INVALID','BOUNDARY_RUN_ADVANCED')
        AND watermark_before_date IS NOT NULL AND watermark_before_generation IS NOT NULL
        AND watermark_after_date IS NOT DISTINCT FROM watermark_before_date
        AND watermark_after_generation IS NOT DISTINCT FROM watermark_before_generation)) IS TRUE
  ),
  CONSTRAINT chk_pabr_error_outcome CHECK (
    (CASE WHEN run_status='STARTED' THEN error_metadata='{}'::jsonb
      ELSE public.adr065_boundary_outcome_metadata_valid(outcome_code,error_metadata)
     END) IS TRUE
  ),
  CONSTRAINT chk_pabr_time_order CHECK (
    ((run_status = 'STARTED' AND completed_at IS NULL)
      OR (run_status = 'COMPLETED' AND completed_at >= attempted_at)) IS TRUE
  )
);

CREATE UNIQUE INDEX uq_pabr_one_retry_child
  ON public.person_assignment_boundary_runs(retry_of_boundary_run_id)
  WHERE retry_of_boundary_run_id IS NOT NULL;

CREATE FUNCTION public.pabr_retry_lineage_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent public.person_assignment_boundary_runs%ROWTYPE;
BEGIN
  IF NEW.retry_of_boundary_run_id IS NULL THEN
    IF NEW.retry_ordinal <> 0 THEN
      RAISE EXCEPTION 'BOUNDARY_RUN_RETRY_LINEAGE_INVALID' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
  END IF;
  SELECT * INTO parent FROM public.person_assignment_boundary_runs
   WHERE boundary_run_id=NEW.retry_of_boundary_run_id FOR SHARE;
  IF NOT FOUND OR parent.run_status <> 'COMPLETED'
     OR parent.outcome_code NOT IN ('BOUNDARY_DUPLICATE_PROJECTION_INCONSISTENT',
       'BOUNDARY_WATERMARK_INVALID','INVALID_SUCCESSOR_CHAIN','ACTIVE_PRIMARY_ASSIGNMENT_CONFLICT')
     OR NEW.target_effective_date IS DISTINCT FROM parent.target_effective_date
     OR NEW.scheduler_context_fingerprint IS DISTINCT FROM parent.scheduler_context_fingerprint
     OR NEW.service_actor IS DISTINCT FROM parent.service_actor
     OR NEW.requested_by_user_id IS DISTINCT FROM parent.requested_by_user_id
     OR NEW.retry_ordinal <> parent.retry_ordinal + 1 THEN
    RAISE EXCEPTION 'BOUNDARY_RUN_RETRY_LINEAGE_INVALID' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_pabr_retry_lineage
BEFORE INSERT ON public.person_assignment_boundary_runs
FOR EACH ROW EXECUTE FUNCTION public.pabr_retry_lineage_guard();

CREATE FUNCTION public.pabr_insert_shape_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.run_status IS DISTINCT FROM 'STARTED'
     OR NEW.t1_started_at IS NOT NULL
     OR NEW.completed_at IS NOT NULL
     OR NEW.outcome_code IS NOT NULL
     OR NEW.projection_consistent IS NOT NULL
     OR NEW.watermark_before_date IS NOT NULL
     OR NEW.watermark_before_generation IS NOT NULL
     OR NEW.watermark_after_date IS NOT NULL
     OR NEW.watermark_after_generation IS NOT NULL
     OR NEW.error_metadata IS DISTINCT FROM '{}'::jsonb
     OR NEW.recovery_count IS DISTINCT FROM 0
     OR NEW.attempted_at IS NULL
     OR NEW.lease_owner_id IS NULL
     OR NEW.lease_acquired_at IS NULL
     OR NEW.lease_expires_at IS NULL
     OR NEW.updated_at IS NULL THEN
    RAISE EXCEPTION 'BOUNDARY_RUN_T0_SHAPE_INVALID' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_pabr_insert_shape
BEFORE INSERT ON public.person_assignment_boundary_runs
FOR EACH ROW EXECUTE FUNCTION public.pabr_insert_shape_guard();

CREATE FUNCTION public.pabr_transition_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN
    RAISE EXCEPTION 'BOUNDARY_RUN_IMMUTABLE' USING ERRCODE='23514';
  END IF;
  IF OLD.run_status='COMPLETED' THEN
    RAISE EXCEPTION 'BOUNDARY_RUN_FINALIZATION_CONFLICT' USING ERRCODE='23514';
  END IF;

  IF NEW.run_status='STARTED' THEN
    IF OLD.t1_started_at IS NULL AND NEW.t1_started_at IS NOT NULL THEN
      IF (to_jsonb(NEW) - ARRAY['t1_started_at','updated_at']) IS DISTINCT FROM
         (to_jsonb(OLD) - ARRAY['t1_started_at','updated_at'])
         OR NEW.t1_started_at IS DISTINCT FROM transaction_timestamp()
         OR NEW.updated_at IS DISTINCT FROM transaction_timestamp()
         OR OLD.lease_expires_at <= statement_timestamp() THEN
        RAISE EXCEPTION 'BOUNDARY_RUN_LEASE_CONFLICT' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END IF;
    IF (to_jsonb(NEW) - ARRAY['lease_owner_id','lease_acquired_at','lease_expires_at',
          'recovery_count','updated_at']) IS DISTINCT FROM
       (to_jsonb(OLD) - ARRAY['lease_owner_id','lease_acquired_at','lease_expires_at',
          'recovery_count','updated_at'])
       OR OLD.t1_started_at IS NOT NULL OR NEW.t1_started_at IS NOT NULL
       OR OLD.lease_expires_at > statement_timestamp()
       OR NEW.recovery_count <> OLD.recovery_count + 1
       OR NEW.lease_owner_id IS NOT DISTINCT FROM OLD.lease_owner_id
       OR NEW.lease_acquired_at IS DISTINCT FROM transaction_timestamp()
       OR NEW.lease_expires_at <= NEW.lease_acquired_at
       OR NEW.updated_at IS DISTINCT FROM transaction_timestamp() THEN
      RAISE EXCEPTION 'BOUNDARY_RUN_LEASE_CONFLICT' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
  END IF;

  IF NEW.run_status <> 'COMPLETED'
     OR (to_jsonb(NEW) - ARRAY['run_status','completed_at','outcome_code',
          'projection_consistent','watermark_before_date','watermark_before_generation',
          'watermark_after_date','watermark_after_generation','error_metadata','updated_at'])
        IS DISTINCT FROM
        (to_jsonb(OLD) - ARRAY['run_status','completed_at','outcome_code',
          'projection_consistent','watermark_before_date','watermark_before_generation',
          'watermark_after_date','watermark_after_generation','error_metadata','updated_at'])
     OR NEW.completed_at IS DISTINCT FROM transaction_timestamp()
     OR NEW.updated_at IS DISTINCT FROM transaction_timestamp() THEN
    RAISE EXCEPTION 'BOUNDARY_RUN_FINALIZATION_CONFLICT' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_pabr_transition_guard
BEFORE UPDATE OR DELETE ON public.person_assignment_boundary_runs
FOR EACH ROW EXECUTE FUNCTION public.pabr_transition_guard();

CREATE FUNCTION public.pabr_t1_commit_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  current_status TEXT;
  current_t1_started_at TIMESTAMPTZ;
BEGIN
  SELECT run_status, t1_started_at
    INTO current_status, current_t1_started_at
    FROM public.person_assignment_boundary_runs
   WHERE boundary_run_id=NEW.boundary_run_id;
  IF FOUND AND current_status='STARTED' AND current_t1_started_at IS NOT NULL THEN
    RAISE EXCEPTION 'BOUNDARY_RUN_T1_INCOMPLETE' USING ERRCODE='23514';
  END IF;
  RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER trg_pabr_t1_commit_guard
AFTER INSERT OR UPDATE ON public.person_assignment_boundary_runs
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION public.pabr_t1_commit_guard();

CREATE FUNCTION public.claim_person_assignment_boundary_run(
  p_scheduler_run_id UUID,
  p_scheduler_context_fingerprint CHAR(64),
  p_target_effective_date DATE,
  p_lease_owner_id UUID,
  p_requested_by_user_id BIGINT,
  p_retry_of_boundary_run_id BIGINT,
  p_retry_ordinal INTEGER
) RETURNS TABLE(
  claim_code TEXT,
  boundary_run_id BIGINT,
  run_status TEXT,
  outcome_code TEXT,
  persisted_lease_owner_id UUID
) LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE
  claimed_id BIGINT;
  existing public.person_assignment_boundary_runs%ROWTYPE;
  claim_now TIMESTAMPTZ := transaction_timestamp();
BEGIN
  INSERT INTO public.person_assignment_boundary_runs(
    scheduler_run_id,scheduler_context_fingerprint,target_effective_date,run_status,
    attempted_at,lease_owner_id,lease_acquired_at,lease_expires_at,t1_started_at,
    recovery_count,completed_at,outcome_code,projection_consistent,
    watermark_before_date,watermark_before_generation,
    watermark_after_date,watermark_after_generation,
    service_actor,requested_by_user_id,retry_of_boundary_run_id,retry_ordinal,
    error_metadata,updated_at)
  VALUES (
    p_scheduler_run_id,p_scheduler_context_fingerprint,p_target_effective_date,'STARTED',
    claim_now,p_lease_owner_id,claim_now,claim_now+INTERVAL '5 minutes',NULL,
    0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,
    'assignment_boundary_worker',p_requested_by_user_id,
    p_retry_of_boundary_run_id,p_retry_ordinal,'{}'::jsonb,claim_now)
  ON CONFLICT (scheduler_run_id) DO NOTHING
  RETURNING person_assignment_boundary_runs.boundary_run_id INTO claimed_id;

  IF claimed_id IS NOT NULL THEN
    RETURN QUERY SELECT 'BOUNDARY_RUN_CLAIMED'::TEXT, claimed_id, 'STARTED'::TEXT,
      NULL::TEXT, p_lease_owner_id;
    RETURN;
  END IF;

  SELECT * INTO existing
    FROM public.person_assignment_boundary_runs
   WHERE scheduler_run_id=p_scheduler_run_id
   FOR SHARE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'BOUNDARY_RUN_CLAIM_UNKNOWN_COMMIT' USING ERRCODE='40001';
  END IF;
  IF existing.scheduler_context_fingerprint IS DISTINCT FROM p_scheduler_context_fingerprint
     OR existing.target_effective_date IS DISTINCT FROM p_target_effective_date
     OR existing.service_actor IS DISTINCT FROM 'assignment_boundary_worker'
     OR existing.requested_by_user_id IS DISTINCT FROM p_requested_by_user_id
     OR existing.retry_of_boundary_run_id IS DISTINCT FROM p_retry_of_boundary_run_id
     OR existing.retry_ordinal IS DISTINCT FROM p_retry_ordinal THEN
    RETURN QUERY SELECT 'BOUNDARY_RUN_CORRELATION_REUSED'::TEXT,
      existing.boundary_run_id,existing.run_status,existing.outcome_code,
      existing.lease_owner_id;
    RETURN;
  END IF;
  RETURN QUERY SELECT
    CASE WHEN existing.run_status='COMPLETED'
      THEN 'BOUNDARY_RUN_RESULT_REPLAYED' ELSE 'BOUNDARY_RUN_CLAIM_REPLAYED' END,
    existing.boundary_run_id,existing.run_status,existing.outcome_code,
    existing.lease_owner_id;
END $$;

CREATE FUNCTION public.begin_person_assignment_boundary_run_t1(
  p_scheduler_run_id UUID, p_lease_owner_id UUID
) RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE affected INTEGER;
BEGIN
  -- The T1 transaction obtains the global boundary lock before any evidence-row lock.
  PERFORM pg_advisory_xact_lock(65002, 1);
  UPDATE public.person_assignment_boundary_runs
     SET t1_started_at=transaction_timestamp(), updated_at=transaction_timestamp()
   WHERE scheduler_run_id=p_scheduler_run_id AND run_status='STARTED'
     AND lease_owner_id=p_lease_owner_id AND t1_started_at IS NULL
     AND lease_expires_at>statement_timestamp();
  GET DIAGNOSTICS affected=ROW_COUNT;
  IF affected <> 1 THEN
    RAISE EXCEPTION 'BOUNDARY_RUN_LEASE_CONFLICT' USING ERRCODE='23514';
  END IF;
END $$;

CREATE FUNCTION public.finalize_person_assignment_boundary_run(
  p_scheduler_run_id UUID, p_lease_owner_id UUID, p_outcome_code TEXT,
  p_projection_consistent BOOLEAN, p_watermark_before_date DATE,
  p_watermark_before_generation BIGINT, p_watermark_after_date DATE,
  p_watermark_after_generation BIGINT, p_error_metadata JSONB
) RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE
  affected INTEGER;
  actual_watermark_date DATE;
  actual_watermark_generation BIGINT;
BEGIN
  IF public.adr065_boundary_outcome_metadata_valid(p_outcome_code,p_error_metadata) IS NOT TRUE THEN
    RAISE EXCEPTION 'BOUNDARY_RUN_METADATA_INVALID' USING ERRCODE='23514';
  END IF;
  IF p_outcome_code='BOUNDARY_RUN_ADVANCED' THEN
    SELECT effective_date, generation
      INTO actual_watermark_date, actual_watermark_generation
      FROM public.person_assignment_activation_watermark
     WHERE singleton IS TRUE
     FOR UPDATE;
    IF NOT FOUND
       OR actual_watermark_date IS DISTINCT FROM p_watermark_after_date
       OR actual_watermark_generation IS DISTINCT FROM p_watermark_after_generation THEN
      RAISE EXCEPTION 'BOUNDARY_RUN_FINALIZATION_CONFLICT' USING ERRCODE='23514';
    END IF;
  END IF;
  UPDATE public.person_assignment_boundary_runs
     SET run_status='COMPLETED', completed_at=transaction_timestamp(),
         outcome_code=p_outcome_code, projection_consistent=p_projection_consistent,
         watermark_before_date=p_watermark_before_date,
         watermark_before_generation=p_watermark_before_generation,
         watermark_after_date=p_watermark_after_date,
         watermark_after_generation=p_watermark_after_generation,
         error_metadata=p_error_metadata, updated_at=transaction_timestamp()
   WHERE scheduler_run_id=p_scheduler_run_id
     AND run_status='STARTED'
     AND lease_owner_id=p_lease_owner_id
     AND ((p_outcome_code='BOUNDARY_RUN_CANCELLED' AND t1_started_at IS NULL)
       OR (p_outcome_code<>'BOUNDARY_RUN_CANCELLED'
           AND t1_started_at IS NOT NULL));
  GET DIAGNOSTICS affected=ROW_COUNT;
  IF affected <> 1 THEN
    RAISE EXCEPTION 'BOUNDARY_RUN_FINALIZATION_CONFLICT' USING ERRCODE='23514';
  END IF;
END $$;

REVOKE INSERT, UPDATE, DELETE ON public.person_assignment_boundary_runs FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.claim_person_assignment_boundary_run(
  UUID,CHAR,DATE,UUID,BIGINT,BIGINT,INTEGER) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.begin_person_assignment_boundary_run_t1(UUID,UUID) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.finalize_person_assignment_boundary_run(
  UUID,UUID,TEXT,BOOLEAN,DATE,BIGINT,DATE,BIGINT,JSONB) FROM PUBLIC;

CREATE FUNCTION public.recover_person_assignment_boundary_run(
  p_scheduler_run_id UUID, p_scheduler_context_fingerprint CHAR(64),
  p_new_lease_owner_id UUID
) RETURNS public.person_assignment_boundary_runs
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE recovered public.person_assignment_boundary_runs%ROWTYPE;
BEGIN
  UPDATE public.person_assignment_boundary_runs
     SET lease_owner_id=p_new_lease_owner_id,
         lease_acquired_at=transaction_timestamp(),
         lease_expires_at=transaction_timestamp()+INTERVAL '5 minutes',
         recovery_count=recovery_count+1, updated_at=transaction_timestamp()
   WHERE scheduler_run_id=p_scheduler_run_id
     AND scheduler_context_fingerprint=p_scheduler_context_fingerprint
     AND run_status='STARTED'
     AND lease_expires_at <= statement_timestamp()
  RETURNING * INTO recovered;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'BOUNDARY_RUN_LEASE_CONFLICT' USING ERRCODE='23514';
  END IF;
  RETURN recovered;
END $$;

REVOKE EXECUTE ON FUNCTION public.recover_person_assignment_boundary_run(
  UUID,CHAR,UUID) FROM PUBLIC;

CREATE ROLE adr065_boundary_runtime NOLOGIN;
GRANT USAGE ON SCHEMA public TO adr065_boundary_runtime;
GRANT SELECT ON public.person_assignment_boundary_runs TO adr065_boundary_runtime;
REVOKE INSERT,UPDATE,DELETE ON public.person_assignment_boundary_runs
  FROM adr065_boundary_runtime;
GRANT EXECUTE ON FUNCTION public.claim_person_assignment_boundary_run(
  UUID,CHAR,DATE,UUID,BIGINT,BIGINT,INTEGER) TO adr065_boundary_runtime;
GRANT EXECUTE ON FUNCTION public.begin_person_assignment_boundary_run_t1(UUID,UUID)
  TO adr065_boundary_runtime;
GRANT EXECUTE ON FUNCTION public.finalize_person_assignment_boundary_run(
  UUID,UUID,TEXT,BOOLEAN,DATE,BIGINT,DATE,BIGINT,JSONB)
  TO adr065_boundary_runtime;
GRANT EXECUTE ON FUNCTION public.recover_person_assignment_boundary_run(
  UUID,CHAR,UUID) TO adr065_boundary_runtime;
```

Guarded downgrade first proves that no boundary worker role/session is enabled and that
`person_assignment_boundary_runs` contains zero rows. Because evidence retention is
indefinite, any persisted STARTED or COMPLETED row makes downgrade a normative refusal;
there is no export-and-delete exception. The empty-table downgrade then revokes function
EXECUTE and runtime-role membership, drops `trg_pabr_t1_commit_guard`,
`trg_pabr_insert_shape`, the transition/retry triggers, claim/begin/recover/finalize
functions and all corresponding guard functions, drops
`person_assignment_boundary_runs`, and only then drops
`adr065_boundary_outcome_metadata_valid`, then
`adr065_boundary_error_metadata_valid`. Any failed preflight refuses before DDL.

The outcome-aware function is the exhaustive persisted metadata matrix: advanced and
consistent duplicate forbid metadata; cancelled, out-of-order and future-date require
their one exact reason object; watermark invalid requires the exact watermark component;
projection inconsistency requires a positive count and one of its three component enums;
invalid chain requires assignment plus a positive count; active-primary conflict requires
assignment plus a count of at least two. No key is optional in those exact branches and no
key from another branch is accepted. SQL NULL, JSON null, missing/extra key, wrong type,
range or enum returns false. Finalization calls the same function before its conditional
UPDATE and maps failure only to `BOUNDARY_RUN_METADATA_INVALID`; the table CHECK is the
independent final authority. Audit receives only the committed exact object and never
enriches or reinterprets it.

`conflicting_person_count` is a JSON number whose PostgreSQL `numeric` value must be an
exact integer in `0..9223372036854775807`; JSON exponent spelling such as `1e3` is accepted
as the same value as `1000` because JSONB canonicalizes numeric value. A numeric-looking
JSON string, fraction, negative value, boolean, array, object, JSON null, overflow or SQL
NULL is rejected without a cast exception. Outcome branches further require the positive
minima stated below.

Values are derived by one query-plan-independent rule. For duplicate projection checking,
form three sets keyed by `person_id`: `assignment` contains a Person when any assignment
eligibility/flag/lifecycle/date tuple or eligible-primary cardinality differs;
`assignment_link` contains it when any sorted link tuple differs; and
`employee_projection` contains it when the exact Employee projection tuple differs.
`conflicting_person_count` is the cardinality of the union of those Person-ID sets.
`stale_component` is the first non-empty set in the closed precedence
`assignment > assignment_link > employee_projection`; later simultaneous components are
still included in the union count but never change the selected component. For
`INVALID_SUCCESSOR_CHAIN`, the count is the number of distinct non-void primary
`assignment_id` values participating in an invalid date, overlap, branching or
replacement-lineage component for all affected Persons. For
`ACTIVE_PRIMARY_ASSIGNMENT_CONFLICT`, it is the number of distinct non-void primary
assignment IDs eligible at the target date for the one conflicting Person. All source
queries use `COUNT(DISTINCT ...)` and ascending numeric-ID ordering before aggregation;
row order and query plan cannot affect the persisted object.

#### Current activation watermark and deployment dependency

For ADR-065 v1 the business timezone is fixed, not configurable:
`business_timezone=UTC+05:00`. Preview computes `D` exactly once inside its caller-owned
`REPEATABLE READ READ ONLY` transaction using the SQL expression in §5.1. A configuration
override, another timezone name, operating-system local time, application-clock date, or
client-supplied date is forbidden; changing this rule requires a new reviewed ADR revision.

The only **current watermark** is exactly one row of
`public.person_assignment_activation_watermark` with `singleton IS TRUE`, positive
`generation`, non-NULL timestamps satisfying `processed_at <= updated_at`, and
`effective_date = D`. The total read result is classified without repair:

| Physical state inside the snapshot | Stable result | Classification/mode/outcome |
|---|---|---|
| table or required column/constraint is absent | `ACTIVE_STATE_SCHEMA_UNAVAILABLE` | all NULL; blocked |
| zero rows, more than one logical singleton, invalid types/NULLs, false singleton, non-positive generation, or invalid timestamp order | `ACTIVE_STATE_WATERMARK_INVALID` | all NULL; blocked |
| one valid row with `effective_date < D` | `ACTIVE_STATE_STALE` | all NULL; blocked |
| one valid row with `effective_date = D` | current; continue | permitted after earlier gates |
| one valid row with `effective_date > D` | `ACTIVE_STATE_FUTURE` | all NULL; blocked |

A future watermark is never treated as current and never expands the open-assignment
window. `OPEN_START_DATE` always means the independently operator-confirmed
`start_date <= D`; because a usable watermark must equal `D`, comparing only to a future
or stale `watermark.effective_date` is forbidden. The watermark/schema gate runs after
wire and assignment-intent completeness and structural import/provenance validation, and
before Person classification and evidence-fingerprint validation. Every failure above
returns `preflight_complete=false`; this read-only slice always returns
`apply_available=false`.

The DDL in this section is a **normative target schema, not deployed fact**. As of R13 no
approved migration in repository history creates this table. A separately reviewed
schema/migration slice is therefore an unconditional deployment prerequisite. Ad hoc DDL
in a test database may test SQL behavior but is not evidence of production readiness.
Until the approved migration is applied and catalog-verified, the endpoint must translate
undefined-table/undefined-column/catalog mismatch to `ACTIVE_STATE_SCHEMA_UNAVAILABLE`
without HTTP 500 and without P0/P1, mode, or proposed outcome.

The migration owns schema creation and deterministic initialization only. Runtime
advancement remains exclusively owned by ADR-043/C2
`assignment_boundary_activation_tx`; no ADR-065 preflight or apply code may write the
watermark. The BOOLEAN primary key plus `singleton IS TRUE` CHECK permits at most one
physical row, while operational readiness requires exactly one. C2 advances it atomically
with assignment flags and reconciliation, under the class-1a exclusive advisory/row lock,
using the expected `(effective_date,generation)` compare-and-set in §5.1. Advancement is
monotonic, may target only `persisted_effective_date < target_effective_date <= D`, and
increments generation exactly once. Same target is an idempotent duplicate; lower target
is out of order; target above `D` is future and performs no DML. Concurrent attempts
serialize, and every failed transaction rolls back entity state, watermark, and boundary
evidence together. Successful advancement is covered by the existing immutable
`person_assignment_boundary_runs` audit/observability contract.

Rollout order for this dependency is: approved ADR-065 revision; reviewed migration;
catalog/data preflight; migration plus deterministic initialization; C2 writer deployment
and catch-up to `D`; readiness probe proving exact schema, one current row and writer
health; only then backend preflight enablement. Downgrade refuses before DDL whenever the
endpoint/writer is enabled or retained assignment/boundary state depends on the watermark;
it never deletes or rewinds the row as implicit rollback.

All five watermark columns are explicitly `NOT NULL`; none has a column `DEFAULT`. The only initial
values are supplied by the following migration DML, so omission cannot introduce a second
clock-dependent initialization rule.

The migration transaction captures one `:initial_effective_date` using the expression
above, performs the reviewed deterministic flag/lifecycle backfill for that same value,
then executes exactly:

```sql
INSERT INTO public.person_assignment_activation_watermark
       (singleton, effective_date, processed_at, generation, updated_at)
VALUES (TRUE, :initial_effective_date, transaction_timestamp(), 1,
        transaction_timestamp())
ON CONFLICT (singleton) DO NOTHING;
```

It then selects the row and refuses migration unless it is the only row and its
`effective_date=:initial_effective_date`, `generation=1`. Re-running against an existing
production row never rewinds or overwrites it; unequal state is a migration preflight
failure. DDL contains no clock predicate: passage of time cannot mutate persisted data.

Only ADR-043/C2 `assignment_boundary_activation_tx` writes flags/watermark; the scheduler
owns only boundary-run evidence. Evidence retention is indefinite: completed rows are
immutable and runtime maintenance never deletes them. A retry has a new
`scheduler_run_id`, references the immediately preceding row, and has exactly predecessor
`retry_ordinal + 1`; `uq_pabr_one_retry_child` forbids retry-chain forks and the INSERT
trigger requires the same target, scheduler context, service/manual actor and a retryable
completed parent. Duplicate delivery reuses the same UUID and never increments ordinal.
SQLSTATE `23505` naming `uq_pabr_one_retry_child` and `23514` from the lineage trigger are
rolled back and both map only to `BOUNDARY_RUN_RETRY_LINEAGE_INVALID`; unrelated integrity
errors retain their own mapping.

Every delivery first performs claim transaction T0. T0 is exactly one call to the
`SECURITY DEFINER` claim function followed by caller commit; the scheduler adapter owns
this short transaction and no other SQL is permitted in it. It uses the authenticated
scheduler-context fingerprint and a fresh worker-instance UUID:

```sql
SELECT *
FROM public.claim_person_assignment_boundary_run(
  :scheduler_run_id,:context_hash,:target,:worker_id,:user_id,:retry_of,:retry_ordinal);
```

The function is the only production INSERT authority. It inserts the complete literal
STARTED shape in the DDL, and `trg_pabr_insert_shape` independently rejects every INSERT
having a T1 marker, completion/outcome/projection/watermark value, non-empty metadata or
nonzero recovery count. A fresh row returns `BOUNDARY_RUN_CLAIMED`; the same correlation
already STARTED returns `BOUNDARY_RUN_CLAIM_REPLAYED` with the persisted lease owner;
the same completed correlation returns `BOUNDARY_RUN_RESULT_REPLAYED`; a reused UUID
with another target/context/actor/retry tuple returns
`BOUNDARY_RUN_CORRELATION_REUSED`. The caller commits T0 before work, so a crash is
durably distinguishable from an unknown commit.

Worker transaction T1 first calls `begin_person_assignment_boundary_run_t1`; its literal
conditional UPDATE is equivalent to `FOR UPDATE`, requires the scheduler UUID, STARTED,
current lease owner, unexpired lease and NULL `t1_started_at`, and persists
`t1_started_at=transaction_timestamp()` inside T1. The same function acquires
`pg_advisory_xact_lock(65002,1)`, so the transaction owning the marker also owns the global
boundary namespace until commit. Zero affected rows causes a terminal-row
reread: matching `COMPLETED` is replayed, otherwise `BOUNDARY_RUN_LEASE_CONFLICT`; no
boundary/entity lock is taken. A non-cancellation finalizer requires that marker and the
same lease-owner UUID, so it cannot be called directly before T1. Timestamp equality is
not transaction identity and is deliberately not a finalizer predicate:
`transaction_timestamp()` remains observability only and two transactions may have an
equal value. The proof is instead MVCC plus locking and the deferred guard. The marker is
uncommitted in live T1 and cannot be observed by another transaction; T1 retains the run
row lock; a separate marker commit is rejected at deferred constraint time; rollback
removes it. Hence only the transaction that established the visible-to-self marker can
finalize before its commit, and marker, domain DML, reconciliation, watermark and terminal
evidence commit or roll back together. Once T1 owns the tuple lock, lease expiry does not
permit takeover: a recovery UPDATE waits for T1 and then sees the committed terminal row
or rolled-back STARTED row. Every accepted run,
including manual catch-up and a duplicate date, then executes before discovery/entity
locks:

```sql
SELECT pg_advisory_xact_lock(65002, 1);
SELECT singleton, effective_date, generation
FROM public.person_assignment_activation_watermark
WHERE singleton IS TRUE
FOR UPDATE;
```

The run row is class 1; boundary advisory lock and singleton row are class 1a in §9.2,
before identity/Person locks. Missing/multiple singleton is
`BOUNDARY_WATERMARK_INVALID`. No two runs can discover, mutate, or advance concurrently.
For requested `target_effective_date`: lower than persisted returns
`BOUNDARY_RUN_OUT_OF_ORDER`; equal returns committed no-op `BOUNDARY_RUN_DUPLICATE` after
verifying projection consistency; greater than the run's computed business date returns
`BOUNDARY_RUN_FUTURE_DATE`; otherwise greater performs catch-up. No rejection/no-op changes
generation. Successful advance requires
`persisted_effective_date < target_effective_date <= business_date`, sets
the target date, `generation=generation+1`, and both timestamps through exactly this final
statement; a zero-row RETURNING result is `BOUNDARY_WATERMARK_INVALID` and rolls back:

```sql
UPDATE public.person_assignment_activation_watermark
SET effective_date = :target_effective_date,
    processed_at = transaction_timestamp(),
    generation = generation + 1,
    updated_at = transaction_timestamp()
WHERE singleton IS TRUE
  AND effective_date = :persisted_effective_date
  AND generation = :persisted_generation
RETURNING effective_date, generation;
```

Every terminal controlled outcome, including out-of-order, future-date, invalid chain,
conflict, duplicate and successful advance, calls
`finalize_person_assignment_boundary_run` as the last T1 statement. Its literal conditional
UPDATE must affect one row; zero rows raises `BOUNDARY_RUN_FINALIZATION_CONFLICT` and rolls
back T1. For `BOUNDARY_RUN_ADVANCED` it first locks the singleton and proves that the
actual date/generation equals the supplied after-watermark; a terminal advanced result
cannot commit without the watermark DML in that same T1. The trigger rejects COMPLETED UPDATE/DELETE and every non-lease/non-finalization
shape. The migration-owned SECURITY DEFINER functions are owned by a NOLOGIN migration
role. Production service logins may inherit only `adr065_boundary_runtime`: that role has
SELECT and EXECUTE on claim/begin/recover/finalize, but no INSERT/UPDATE/DELETE, table
ownership, migration-role membership or trigger-disable privilege. Catalog preflight
compares all role memberships, ACLs, function owners/security-definer flags and enabled
triggers literally and fails on any excess. The migration owner can perform DDL/owner
maintenance only while every production entrypoint is disabled; it is not a runtime path.
Even owner INSERT with triggers enabled can create only the exact STARTED shape. Disabling
the insert/deferred/transition trigger, `session_replication_role` bypass, superuser use or
direct migration-owner DML is a production gate failure. Thus runtime direct STARTED,
COMPLETED, error, forged-marker, fake-root and terminal-parent INSERTs are impossible.
No external scheduler log is authority.

`trg_pabr_t1_commit_guard` is a deferred constraint trigger and is the commit-time
atomicity boundary. Each queued INSERT/UPDATE event rereads the one current row by PK at
constraint time; it never reasons from an old queued `NEW` image. A T1 that has finalized
therefore rereads `COMPLETED` and commits. A transaction that calls begin and attempts to
commit while the current row remains `STARTED` with non-NULL `t1_started_at` raises
`BOUNDARY_RUN_T1_INCOMPLETE` at commit and rolls back the marker, all domain DML,
reconciliation and watermark. This also covers an accidental early commit by the
authorized worker. The required transaction owner is the strict C2 boundary worker port;
the begin call, every entity mutation, caller-owned reconciliation, watermark statement
and finalizer share its one `Connection`/transaction. Static call-graph and runtime
transaction-token evidence are blocking rollout proofs; no alternate transaction-owning
wrapper is permitted.

An equal-date run has exactly two outcomes. While still holding exclusive class 1a, the
singleton `FOR UPDATE`, then every Person, assignment-scope, Employee, assignment and link
lock in §9 order, it scans the complete assignment table. For every row it compares
`(assignment_id, person_id, lifecycle_status, active_flag, is_primary, start_date,
end_date, org_unit_id, position_id, rate, employment_type, row_version)` with
`eligible(row,persisted_effective_date)`. For each Person it also compares the unique
eligible primary ID or NULL with every `employee_assignment_links` row and the Employee
projection tuple `(person_id,org_unit_id,position_id,department_id,date_from,date_to,
employment_rate,is_active,operational_status)`. Exact equality returns
`BOUNDARY_RUN_DUPLICATE`. Any unequal flag/lifecycle/date, duplicate eligible primary,
link mismatch, or Employee projection mismatch returns
`BOUNDARY_DUPLICATE_PROJECTION_INCONSISTENT`.

Both duplicate outcomes execute zero **business** DML: generation/watermark do not advance
and no reconciliation is attempted. T1 performs exactly one evidence UPDATE, setting
`COMPLETED`, completion time, stable code, projection boolean, identical watermark
before/after tuples and safe metadata, then commits. The inconsistent result is therefore
scheduler-visible and durable without an orchestration operation row. It is retryable
after 60 seconds plus 0–5 second jitter with a new linked run row and repeats until an
authorized repair; consistent duplicate is terminal. Precedence is missing/invalid
watermark → out-of-order → future-date → invalid successor chain → duplicate projection
inconsistency → duplicate success.

A catch-up run scans the complete `person_assignments` table for every non-void row whose
eligibility/lifecycle/flag differs at target date or whose start/end boundary lies in
`(persisted_effective_date,target_effective_date]`; it also loads every other primary row
for each discovered Person. Persons, Employees, assignments and links are then locked in
§9 order, sorted by ID. For each Person, C2 validates the full primary chain, closes every
still-`active` episode with `end_date < target`, sets all flags to exact target-date
eligibility, activates at most one eligible primary, and reconciles the final current ID
or NULL. Several sequential future successors are legal when all inclusive ranges are
non-overlapping: a long catch-up closes skipped completed successors and activates only
the unique row eligible at target. More than one eligible row, invalid dates, overlap, or
contradictory replacement lineage returns `INVALID_SUCCESSOR_CHAIN`; all entity changes
and the watermark roll back.

The writer runs at 00:00:05 fixed UTC+5 and every 60 seconds, with retry after failure at
60 seconds plus 0–5 second jitter. Startup performs catch-up before serving current reads.
If watermark date is below business date, reads and mutating commands return
`ACTIVE_STATE_STALE`. Crash after T0 but before T1 commit leaves `STARTED` and no committed
domain change; the same delivery resumes that row. Watermark/entity changes and final
evidence UPDATE share T1, with watermark last among business DML and evidence finalization
last overall. Unknown commit is resolved only by `scheduler_run_id`: `STARTED` retries;
`COMPLETED` replays. Crash after commit leaves complete state and stored result. The full
guarantee is enabled only after every R1 writer is migrated or technically disabled.

A run is **abandoned** only when its persisted state is `STARTED` and
`lease_expires_at <= statement_timestamp()`. The scheduler scans that predicate at startup
and every 60 seconds. Recovery owns a short separate transaction, calls
`recover_person_assignment_boundary_run` with the same scheduler UUID/context and a fresh
worker UUID, and returns scheduler control result `BOUNDARY_RUN_RECOVERY_ACQUIRED`; the
persisted run remains STARTED with `recovery_count+1`. If the original worker already owns
T1, recovery blocks on the row and then returns the stored COMPLETED result or acquires the
rolled-back STARTED row; if the original worker has not entered T1, its old lease can no
longer satisfy the T1 predicate. Exactly one worker can therefore enter domain work.

Cancellation is accepted only before T1 obtains the run-row lock. The cancellation
transaction locks the row `FOR UPDATE`; matching STARTED is finalized through the same
function as `BOUNDARY_RUN_CANCELLED`, NULL projection/watermark fields and non-empty
`reason_code='scheduler_cancelled'`. It performs no business DML. If T1 already owns the
row, cancellation waits and then returns the committed outcome; it cannot overwrite it.
An unknown cancellation commit is resolved by scheduler UUID exactly like T1. Cancelled,
advanced, duplicate, out-of-order and future-date rows are terminal/non-retryable.
Projection inconsistency, watermark invalidity, invalid chain and active conflict may
create the one trigger-validated retry child after the specified delay. STARTED and
COMPLETED rows are retained indefinitely; a STARTED row may only be recovered or cancelled,
never deleted or administratively rewritten.

An explicit attempt to activate a row before `start_date` returns
`ASSIGNMENT_NOT_EFFECTIVE_YET`. When the boundary is reached, C2 atomically deactivates
the prior ended row then activates the successor under the Person lock. A still-eligible
active primary or a uniqueness violation returns `ACTIVE_PRIMARY_ASSIGNMENT_CONFLICT`;
the transaction and watermark do not advance.

### 5.2. Timeline command preconditions

C2 loads and locks the complete Person primary timeline, including current, future,
closed, voided, and inactive-by-date rows, before DML. It then applies exactly these
preconditions:

- every row satisfies `end_date IS NULL OR end_date >= start_date`;
- a continuous transition requires `transition_date > old.start_date`, sets
  `old.end_date = transition_date - 1 day`, and sets
  `new.start_date = transition_date`;
- no mode in this ADR accepts an explicit-gap successor. Supplying `old_end_date` and
  `new_start_date` with a successor returns `ASSIGNMENT_TIMELINE_GAP_UNSUPPORTED`; a real
  gap requires two separately authorized lifecycle facts outside this composite command;
- close without successor requires confirmed `old_end_date >= old.start_date`,
  `old_end_date < effective_date`, and no successor fields; equality means the inclusive
  episode is still current that day and returns `ASSIGNMENT_STILL_EFFECTIVE_ON_END_DATE`;
- any non-void primary overlap is forbidden; gaps are never inferred or created by a
  successor mode in this ADR;
- a backdated command may change only its explicit target(s), must not overlap an
  intervening/later episode, and recomputes flags for the fixed effective date;
- `COMPLETE_REAL_LIFECYCLE_EPISODE` requires the past end rule above;
  `COMPLETE_REAL_LIFECYCLE_EPISODE_WITH_SUCCESSOR`, `TRANSFER`, `POSITION_CHANGE`,
  `TRANSFER_AND_POSITION_CHANGE`, and `ASSIGNMENT_TERMS_CHANGE` require
  `transition_date <= effective_date`;
- every `TRANSITION_FUTURE_*` mode requires `transition_date > effective_date`, keeps the
  old row `lifecycle_status='active'` and `active_flag=true` through the day before that
  start, inserts the successor as lifecycle-active with `active_flag=false`, and leaves
  the current Employee projection unchanged until the boundary writer atomically closes/
  deactivates old and activates/reconciles successor;
- successor continuity is temporal: `successor.start_date=transition_date` and
  `predecessor.end_date=transition_date - 1 day`; predecessor and successor start dates
  are therefore not compared for equality. Business classification compares only
  `(org_unit_id, position_id, rate, employment_type, is_primary)`. Terms delta wins;
  otherwise exact org/position delta selects unchanged/transfer/position/combined.
  Department is a legacy Employee projection and is not an assignment-defining input.
  The §4 business identity of the successor is newly derived with its own start date.
  A submitted mode unequal to this classification returns
  `MODE_SOURCE_STATE_MISMATCH` before DML;
- later non-target episodes are validated but never changed implicitly.

Violation before DML returns `INVALID_ASSIGNMENT_DATES`,
`ASSIGNMENT_TIMELINE_GAP_UNSUPPORTED`, or `ASSIGNMENT_TIMELINE_OVERLAP` as applicable.
Correction voids and preserves the original;
only `CORRECT_ERRONEOUS_RECORD_WITH_REPLACEMENT` opens a replacement and sets its
`replaces_assignment_id`.

### 5.3. Database hard guarantees and rollout

Maximum-one operational active primary is enforced independently of locks:

```sql
CREATE UNIQUE INDEX uq_pa_one_current_active_primary_per_person
  ON public.person_assignments (person_id)
  WHERE is_primary = TRUE
    AND active_flag = TRUE
    AND lifecycle_status = 'active';
```

Semantic non-overlap of all historical, current, and future non-void primary episodes is
a separate hard guarantee; the partial index alone is insufficient:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE public.person_assignments
  ADD CONSTRAINT ex_pa_primary_period_no_overlap
  EXCLUDE USING gist (
    person_id WITH =,
    daterange(start_date, end_date, '[]') WITH &&
  )
  WHERE (is_primary = TRUE AND lifecycle_status <> 'voided')
  DEFERRABLE INITIALLY IMMEDIATE;
```

The exclusion constraint is made deferred only inside a C2 transition transaction that
closes/voids the old row before inserting the successor, and is forced `SET CONSTRAINTS
ex_pa_primary_period_no_overlap IMMEDIATE` before reconciliation. Advisory locks provide
serialization; these two database objects provide the absolute guarantees.

Preflight is bidirectional for a fixed recorded `:effective_date`: it rejects duplicate
rows matching the unique predicate; any overlapping non-void primary ranges; every
`active_flag=true` row that is not `eligible`; and every `eligible` row with
`active_flag=false`. It also rejects every lifecycle-`active` row with end before the
fixed date, every `closed` row with NULL end or end on/after the fixed date, every
closed/voided row with `active_flag=true`, other invalid date combinations, and a watermark
behind `:effective_date`. No preflight mutates data. Upgrade order is checks and
watermark → reviewed deterministic flag backfill for the fixed date → exclusion
constraint → partial unique index → enable boundary writer. Apply remains disabled until
the writer/lock gate and one successful catch-up. Downgrade refuses while retained code
depends on either guarantee or watermark and never repairs/deletes data.

### 5.4. One event outcome per mode

| Mode/change | C2 canonical event | `personnel_record_event` | Employee event | Stable success |
|---|---|---|---|---|
| `ENROLL_NEW_ACTIVE` / `S_ENROLLABLE_NO_EMPLOYEE` | none; application command is not C1 | exactly shell plus link events; no assignment personnel event | none; HIRE is not inferred | `ENROLLED_CREATED` |
| `ENROLL_NEW_ACTIVE` / `S_LINK_MISSING_PERSON` | none; application command is not C1 | exactly link event; existing Person means no shell event | none; HIRE is not inferred | `ENROLLED_CREATED` |
| `LINK_AND_OPEN_MISSING_ASSIGNMENT` / `S_UNLINKED_NO_PRIMARY_P0_WITH_INTENT` | none; C2 retains canonical authority | exactly `PERSON_SHELL_CREATED` then `EMPLOYEE_PERSON_LINKED`; assignment/reconciliation outcome is carried by C2 result, strict audit and immutable provenance, not a synthetic personnel event | none; existing Employee events are preserved | `EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED` |
| `LINK_AND_OPEN_MISSING_ASSIGNMENT` / `S_UNLINKED_NO_PRIMARY_P1_WITH_INTENT` | none; C2 retains canonical authority | exactly `EMPLOYEE_PERSON_LINKED`; assignment/reconciliation outcome is carried by C2 result, strict audit and immutable provenance, not a synthetic personnel event | none; existing Employee events are preserved | `EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED` |
| `OPEN_MISSING_ASSIGNMENT` | none | none | none | `MISSING_ASSIGNMENT_OPENED` |
| `CORRECT_ERRONEOUS_RECORD` | none | one `ASSIGNMENT_CORRECTED` | none | `ERRONEOUS_ASSIGNMENT_VOIDED` |
| `CORRECT_ERRONEOUS_RECORD_WITH_REPLACEMENT` | none | one `ASSIGNMENT_CORRECTED` linking both IDs | none | `ERRONEOUS_ASSIGNMENT_REPLACED` |
| `COMPLETE_REAL_LIFECYCLE_EPISODE` close without successor | none | none | none | `LIFECYCLE_EPISODE_COMPLETED` |
| `COMPLETE_REAL_LIFECYCLE_EPISODE_WITH_SUCCESSOR`, business delta unchanged and successor start set to transition date | none | none | none | `LIFECYCLE_EPISODE_COMPLETED_WITH_SUCCESSOR` |
| `TRANSFER` close plus real successor | none | none | `TRANSFER` | `ASSIGNMENT_TRANSFERRED` |
| `POSITION_CHANGE` close plus real successor | none | none | `POSITION_CHANGE` | `ASSIGNMENT_POSITION_CHANGED` |
| `TRANSFER_AND_POSITION_CHANGE` close plus real successor | none | none | one `TRANSFER` with position IDs | `ASSIGNMENT_TRANSFERRED_AND_POSITION_CHANGED` |
| `ASSIGNMENT_TERMS_CHANGE` | none | none | one `ASSIGNMENT_TERMS_CHANGE` with exact changed fields | `ASSIGNMENT_TERMS_CHANGED` |
| `PRESERVE_FUTURE_ASSIGNMENT` | none | none | none | `FUTURE_ASSIGNMENT_PRESERVED` |
| `TRANSITION_FUTURE_UNCHANGED_ASSIGNMENT` | none | none | none | `FUTURE_UNCHANGED_ASSIGNMENT_SCHEDULED` |
| `TRANSITION_FUTURE_TRANSFER` | none | none | scheduled `TRANSFER`; boundary emits none | `FUTURE_ASSIGNMENT_TRANSFER_SCHEDULED` |
| `TRANSITION_FUTURE_POSITION_CHANGE` | none | none | scheduled `POSITION_CHANGE`; boundary emits none | `FUTURE_ASSIGNMENT_POSITION_CHANGE_SCHEDULED` |
| `TRANSITION_FUTURE_TRANSFER_AND_POSITION_CHANGE` | none | none | scheduled `TRANSFER` with org/position IDs; boundary emits none | `FUTURE_ASSIGNMENT_TRANSFER_POSITION_SCHEDULED` |
| `TRANSITION_FUTURE_ASSIGNMENT_TERMS_CHANGE` | none | none | scheduled `ASSIGNMENT_TERMS_CHANGE`; boundary emits none | `FUTURE_ASSIGNMENT_TERMS_CHANGE_SCHEDULED` |
| `LINK_ONLY` / `S_LINK_MISSING_PERSON` | none | exactly link event; existing Person means no shell event | none | `EMPLOYEE_PERSON_REPAIRED` |
| `LINK_ONLY` / `S_LINK_MISSING_PERSON_ABSENT` | none | exactly shell plus link events; every pre-existing Employee operational/absence field retained | none | `EMPLOYEE_PERSON_REPAIRED` |
| `VERIFY_CONSISTENT` | none | none | none | `ALREADY_CONSISTENT` |

Canonical C1 events that later arrive may produce the adoption outcomes in §4; the
application command never synthesizes one. One request selects exactly one §2 matrix row and
cannot synthesize acting duty, termination, rehire, HIRE, completion, or transfer.

---

## 6. Evidence and prohibited inference

Apply requires controlled `reason_code`, allowlisted `evidence_type`, internal
`personnel_order_id` or safe external reference fingerprint, actor/verifier IDs,
verification time, and all effective dates. Evidence text/document bodies/full IIN/
phone/email/credentials/unrestricted comments are prohibited from tokens, operations,
events, audit, and results.

The evidence discriminator is closed: `PERSONNEL_ORDER | EXTERNAL_REFERENCE`. For
`PERSONNEL_ORDER`, both IDs are non-NULL, `personnel_order_id` is
`public.personnel_orders.order_id`, `evidence_record_id` is
`public.personnel_order_items.item_id`, and the locked item must have that `order_id`;
`evidence_fingerprint` is the state-safe fingerprint of the four §7.1 order collections.
For `EXTERNAL_REFERENCE`, both IDs are NULL and the non-NULL fingerprint is the sole
reference. The opposite NULL/non-NULL shapes are `EVIDENCE_REFERENCE_INVALID`. Text,
JSON payload, basis/free-text and attachment path/URL values included in the order-state
fingerprint are protected only by the exact §6.1 column framing before outer JCS; their
raw values never enter the token. The exact protected columns are
`personnel_orders.basis_summary`, `personnel_orders.comment`,
`personnel_order_items.payload`, `personnel_order_item_bases.free_text`,
`personnel_order_item_bases.metadata`, and
`personnel_order_attachments.file_path|file_url|file_comment`.

### 6.1. Normative PERSONNEL_ORDER evidence fingerprint profile

The one supported profile is:

| Wire member | Exact v1 contract |
|---|---|
| `evidence_profile_id` | required literal ASCII `adr065-po-evidence` |
| `evidence_profile_version` | required JSON integer literal `1` |
| `evidence_key_id` | required ASCII matching `^[a-z0-9][a-z0-9._-]{0,63}$` |
| `evidence_fingerprint` | required 64-character lowercase hexadecimal HMAC |

These profile members are required only with `evidence_type=PERSONNEL_ORDER`; all three
must be JSON null for `EXTERNAL_REFERENCE`, whose fingerprint remains an opaque exact
external reference. Unknown members are forbidden. Authenticated server context, not the
request, supplies `organization_scope_id`, an immutable deployment/tenant identifier
matching the `evidence_key_id` ASCII expression.

Profile v1 uses HMAC-SHA-256 for every protected column and for the final fingerprint. The
environment security/key-management authority owns the
`PERSONNEL_ORDER_EVIDENCE_HMAC` key ring and assigns each `evidence_key_id`. One entry
contains two independent uniformly random 32-byte secrets: `column_hmac_key` and
`outer_hmac_key`. Key reuse between those purposes or with IIN/preview/idempotency
profiles is forbidden. Runtime obtains the bundle only through the authenticated
KMS/secret-provider port, before opening the business snapshot, using workload identity and
`(organization_scope_id,evidence_profile_id,evidence_profile_version,evidence_key_id)`.
The provider returns an immutable request-scoped verification handle/key snapshot; no
provider refresh is permitted after `BEGIN`. Configuration contains only provider
location and public metadata. Neither secret may be
stored in PostgreSQL, request/response, token, fingerprint payload, event, audit, log,
exception, fixture, or source control; it may exist only in provider and process memory
for the verification call.

Define `U64(n)` as unsigned 64-bit big-endian byte length and
`LP(b)=U64(length(b))||b`. `ASCII(x)` means the exact ASCII bytes of token `x` between
the parentheses; the parentheses are notation and are not included. `||` is concatenation.
TEXT is its exact UTF-8 scalar sequence with no trim, case conversion, or Unicode
normalization. Typed values use this complete framing:

| SQL/logical value | `TV(v)` bytes |
|---|---|
| NULL | ASCII `N` |
| boolean | ASCII `B` plus byte `00` or `01` |
| integer/BIGINT | ASCII `I` + `LP` of canonical base-10 ASCII |
| decimal/NUMERIC | ASCII `D` + `LP` of exact non-exponent canonical decimal ASCII |
| DATE | ASCII `d` + `LP(ASCII(YYYY-MM-DD))` |
| TIMESTAMPTZ | ASCII `t` + `LP` of UTC `YYYY-MM-DDTHH:MM:SS.ffffffZ` ASCII |
| UUID | ASCII `u` + `LP` of lowercase canonical UUID ASCII |
| bytes | ASCII `x` + `LP` of raw bytes |
| TEXT | ASCII `s` + `LP` of exact UTF-8 |
| JSON/JSONB | ASCII `j` + `LP` of RFC-8785 JCS UTF-8 |

JSON/JSONB with a non-finite or non-RFC-8785/IEEE-754-domain number is
`EVIDENCE_STRUCTURAL_CONFLICT`, never implementation-defined stringification. An absent
tuple member is invalid and differs from NULL. `TV(NULL)` is the normative null frame
where a typed value is framed; a protected NULL column remains mandatory JSON null and
does not create a replacement HMAC object. Empty TEXT is `s||U64(0)`.

For every protected non-NULL column `c` of table `T` and row primary key `pk`:

```text
column_message =
  ASCII(ADR065-PO-EVIDENCE-COLUMN) || 00 ||
  LP(ASCII(adr065-po-evidence)) || LP(ASCII(1)) ||
  LP(UTF8(organization_scope_id)) || LP(UTF8(evidence_key_id)) ||
  LP(ASCII(T)) || LP(ASCII(primary_key_column_name)) ||
  LP(ASCII(canonical_decimal_primary_key_value)) || LP(ASCII(c)) ||
  LP(TV(database_value))
column_mac = HMAC-SHA-256(column_hmac_key, column_message)
```

The replacement object has exactly `algorithm=HMAC-SHA-256`,
`profile_id=adr065-po-evidence`, `profile_version=1`, `key_id`, and
`fingerprint=lowercase_hex(column_mac)`. Protected NULL remains JSON null, but its field
is mandatory. Raw protected values never enter the outer envelope.

The four collections are exactly the literal §7.1 tuples: one selected order header; all
items of that order; all bases of those items; and all attachments of that order. Header
is a one-element array. Items, bases, and attachments sort by `item_id`,
`item_basis_id`, and `attachment_id`, ascending numeric value. Every tuple is a JSON
array in the exact §7.1 field order and scalar representation, except protected columns
use the HMAC object above. The selected `evidence_record_id` must be present among the
item tuples even though all order items are included.

The outer envelope is one object with these exact members and no others:

| Member | Exact value |
|---|---|
| `algorithm` | ASCII string `HMAC-SHA-256` |
| `profile_id` | ASCII string `adr065-po-evidence` |
| `profile_version` | JSON integer `1` |
| `key_id` | exact request `evidence_key_id` |
| `organization_scope_id` | trusted server-scope ASCII value |
| `personnel_order_id` | selected positive decimal string |
| `selected_evidence_item_id` | selected positive decimal string |
| `evidence_scope_generation` | selected positive decimal string |
| `header` | array containing the one exact header tuple |
| `items` | sorted array of all exact item tuples |
| `item_bases` | sorted array of all exact basis tuples |
| `attachments` | sorted array of all exact attachment tuples |

Serialize that populated object to UTF-8 RFC-8785 JCS bytes `E`. Compute exactly:

```text
outer_message =
  ASCII(ADR065-PO-EVIDENCE-OUTER) || 00 ||
  LP(ASCII(adr065-po-evidence)) || LP(ASCII(1)) ||
  LP(UTF8(organization_scope_id)) || LP(UTF8(evidence_key_id)) ||
  LP(E)
evidence_fingerprint =
  lowercase_hex(HMAC-SHA-256(outer_hmac_key, outer_message))
```

Both `personnel_order_id` and selected `evidence_record_id` are explicitly bound even
though all items are present. A fingerprint from another order, selected item,
organization scope, profile version, or key cannot verify. Compare the 32 decoded request
bytes to the computed 32 bytes with a constant-time equality primitive; ordinary string
equality is forbidden.

Key states are closed: `SCHEDULED | ACTIVE | VERIFICATION_ONLY | REVOKED | DESTROYED`.
Exactly one key may be ACTIVE for new fingerprints in one organization/profile/version.
Rotation atomically changes the old ACTIVE key to VERIFICATION_ONLY and activates the new
key. A request remains verifiable with its exact old key while it is VERIFICATION_ONLY
and retained; verification never substitutes the current ACTIVE key. REVOKED/DESTROYED
keys cannot verify. Profile v1 assigns no time-based expiry to VERIFICATION_ONLY:
verification remains permitted until an explicit authority transition. Destruction is
forbidden while any live preview or nonterminal operation references the key. A committed
result replays before evidence-key validation, and retained audit/fingerprint metadata is
historical evidence rather than a request to recompute, so committed-only references do
not require the secret to remain available.

Computation reads only the actual four database collections and exact
`personnel_order_evidence_scopes.generation` inside the same caller-owned
`REPEATABLE READ READ ONLY` transaction. It performs no DML, sequence access,
audit/event call, remote mutable business-state read, or partial/fallback digest. It uses
only the pre-transaction immutable verification handle; no KMS/secret-provider call or
other external mutable-state read occurs inside the transaction.
Stable evidence-stage precedence is:

1. missing required evidence/profile member — `ASSIGNMENT_INTENT_INCOMPLETE`;
2. invalid discriminator/NULL shape or order/item reference — `EVIDENCE_REFERENCE_INVALID`;
3. absent required order/header/item/scope collection — `EVIDENCE_STATE_INCOMPLETE`;
4. cross-order, cross-item, cross-scope/tenant, duplicate or malformed tuple —
   `EVIDENCE_STRUCTURAL_CONFLICT`;
5. unknown profile/version — `EVIDENCE_PROFILE_UNSUPPORTED` /
   `EVIDENCE_PROFILE_VERSION_UNSUPPORTED`;
6. unknown/scheduled/revoked/destroyed key — `EVIDENCE_KEY_UNKNOWN` /
   `EVIDENCE_KEY_NOT_YET_VALID` / `EVIDENCE_KEY_REVOKED` /
   `EVIDENCE_KEY_DESTROYED`;
7. known permitted key whose secret/provider/primitive is unavailable —
   `EVIDENCE_FINGERPRINT_UNVERIFIABLE`;
8. complete verifiable state with unequal constant-time comparison —
   `EVIDENCE_FINGERPRINT_MISMATCH`.

Incomplete evidence is not called mismatch; unavailable key material is not called
mismatch; mismatch never retries another profile/key or a collection subset. Every
evidence failure blocks P0/P1, mode and proposed outcome, returns
`preflight_complete=false`, and leaves `apply_available=false`.

For `ASSIGNMENT_INTENT`, the operator confirms eight separate decisions before preview
can become applicable for apply: (1) exact org unit ID and confirmation tuple, (2) exact
position ID and confirmation tuple, (3) rate, (4) employment type, (5)
`is_primary=true`, (6) start date, (7) evidence admissibility and its complete
allowlisted reference structure defined above, and (8) controlled `reason_code`.
Evidence and reason are not one field: evidence is the closed
`PERSONNEL_ORDER | EXTERNAL_REFERENCE` structure plus fingerprint, while reason is a
separate non-empty controlled code. Absence, JSON null where non-null is required, or lack
of explicit operator confirmation for any one decision returns
`ASSIGNMENT_INTENT_INCOMPLETE` in the common completeness gate before classification,
operation-row INSERT, or any domain/import write.

### 6.2. Closed operator reason vocabulary

`reason_code` is a required JSON string for every supported successful §2 row, including
verified no-op rows. It must byte-equal one ASCII value below; trim, case conversion,
aliases, JSON null, and empty string are forbidden. It explains the operator's business
intent; it never selects classification, mode, C2 command, or proposed outcome. Every
listed code permits both evidence types,
subject to the complete evidence contract above. The closed vocabulary is:

| `reason_code` | Нормативный смысл и подтверждаемый факт | Allowed states / modes | Required intent |
|---|---|---|---|
| `ACTIVE_ENROLLMENT_CONFIRMED` | Оператор подтверждает первичную явную материализацию активного трудоустройства | `ACTIVE_ENROLLMENT / ENROLL_NEW_ACTIVE`; `S_ENROLLABLE_NO_EMPLOYEE | S_LINK_MISSING_PERSON` | complete assignment intent |
| `CONSISTENT_STATE_VERIFIED` | Оператор подтверждает проверку уже согласованного состояния без кадровой мутации | `ACTIVE_ENROLLMENT | EXISTING_CARD_REPAIR / VERIFY_CONSISTENT`; `S_CONSISTENT` | verifier, evidence and complete expected state; no assignment mutation |
| `EXISTING_CARD_PERSON_LINK_GAP_CONFIRMED` | В существующей карточке подтверждён только пробел Person-link | `EXISTING_CARD_REPAIR / LINK_ONLY`; `S_LINK_MISSING_PERSON | S_LINK_MISSING_PERSON_ABSENT` | exact identity/link evidence; assignment intent is forbidden |
| `EXISTING_CARD_PERSON_AND_ASSIGNMENT_GAP_CONFIRMED` | В существующей карточке одновременно подтверждены пробелы Person-link и primary assignment | `EXISTING_CARD_REPAIR / LINK_AND_OPEN_MISSING_ASSIGNMENT`; `S_UNLINKED_NO_PRIMARY_P0_WITH_INTENT | S_UNLINKED_NO_PRIMARY_P1_WITH_INTENT` | all eight assignment decisions |
| `MISSING_PRIMARY_ASSIGNMENT_CONFIRMED` | Person/link существуют, но отсутствие primary assignment подтверждено как кадровый пробел | `EXISTING_CARD_REPAIR / OPEN_MISSING_ASSIGNMENT`; `S_NO_NONVOID_PRIMARY` | all eight assignment decisions |
| `ERRONEOUS_ASSIGNMENT_RECORD_CONFIRMED` | Оператор подтверждает, что выбранная assignment-запись ошибочна, а не отражает реальный lifecycle | `EXISTING_CARD_REPAIR / CORRECT_ERRONEOUS_RECORD | CORRECT_ERRONEOUS_RECORD_WITH_REPLACEMENT`; `S_ERRONEOUS_VOID_ONLY | S_ERRONEOUS_WITH_REPLACEMENT` respectively | correction evidence; complete replacement intent only for replacement |
| `REAL_LIFECYCLE_EPISODE_COMPLETION_CONFIRMED` | Оператор подтверждает реальное завершение эпизода, а не исправление ошибки | `EXISTING_CARD_REPAIR / COMPLETE_REAL_LIFECYCLE_EPISODE | COMPLETE_REAL_LIFECYCLE_EPISODE_WITH_SUCCESSOR`; `S_COMPLETE_NO_SUCCESSOR | S_COMPLETE_UNCHANGED_SUCCESSOR` respectively | completion date/evidence; complete successor intent only with successor |
| `CURRENT_ASSIGNMENT_CHANGE_CONFIRMED` | Оператор подтверждает текущий перевод, смену должности или условий | `EXISTING_CARD_REPAIR / TRANSFER | POSITION_CHANGE | TRANSFER_AND_POSITION_CHANGE | ASSIGNMENT_TERMS_CHANGE`; respectively `S_CURRENT_TRANSFER | S_CURRENT_POSITION_CHANGE | S_CURRENT_TRANSFER_POSITION | S_CURRENT_TERMS_CHANGE` | complete transition intent and exact changed fields |
| `FUTURE_ASSIGNMENT_PRESERVATION_CONFIRMED` | Оператор подтверждает, что существующая future assignment должна быть сохранена без изменения | `EXISTING_CARD_REPAIR / PRESERVE_FUTURE_ASSIGNMENT`; `S_FUTURE_EXACT_PRESERVE` | exact target/version/timeline and preservation evidence; no successor mutation |
| `FUTURE_ASSIGNMENT_CHANGE_CONFIRMED` | Оператор подтверждает запланированный future transition | `EXISTING_CARD_REPAIR / TRANSITION_FUTURE_UNCHANGED_ASSIGNMENT | TRANSITION_FUTURE_TRANSFER | TRANSITION_FUTURE_POSITION_CHANGE | TRANSITION_FUTURE_TRANSFER_AND_POSITION_CHANGE | TRANSITION_FUTURE_ASSIGNMENT_TERMS_CHANGE`; respectively `S_FUTURE_UNCHANGED_SUCCESSOR | S_FUTURE_TRANSFER | S_FUTURE_POSITION_CHANGE | S_FUTURE_TRANSFER_POSITION | S_FUTURE_TERMS_CHANGE` | complete future transition intent and exact changed fields |

The code is mandatory only with one compatible successful row; every cross-row or
cross-mode use returns `REASON_MODE_INCOMPATIBLE` and blocks preview completion.
Arbitrary text and additional comment fields are forbidden. Unknown ASCII values return
`REASON_CODE_UNSUPPORTED`. A mode is never a reason:
`LINK_AND_OPEN_MISSING_ASSIGNMENT` is expressly invalid as `reason_code`.
`scheduler_cancelled`, `future_date`, and `projection_inconsistent` belong only to
their existing technical metadata contracts and are also forbidden operator reasons.

Future apply persists the exact code in the operation row, business request digest,
strict success audit, and operation-owned provenance; it is immutable and retained with
the result. The code does not change the stable outcome. The temporary backend placeholder
`LINK_AND_OPEN_MISSING_ASSIGNMENT` has no compatibility alias and must be removed before
enablement. Because no approved production operation schema/apply exists yet, no value
migration is permitted or needed: readiness preflight requires zero nonterminal/persisted
requests using the placeholder, and tests/fixtures must submit the new controlled code.

HIRE date, personnel-order date, import/creation timestamp, technical audit date, legacy
snapshot date, import row, normalized payload, or Employee projection never establishes
assignment intent, attributes, or effective date by itself. Missing evidence/date blocks
apply but not preview. Historical events are not synthesized. Assignment intent may not
be derived automatically from an import row, Employee projection, HIRE event, or order;
the operator must explicitly confirm org unit, position, rate, employment type, primary
flag, start date, evidence admissibility/reference, and controlled reason.

---

## 7. Preview and expected-state token

### 7.1. Consistent snapshot

Preview uses one transaction:

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
```

All plan/candidate/digest SELECTs run there; preview takes no locks, writes, sequence
advances, or external effects and ends with rollback.

Every mode uses one closed top-level state object; an inapplicable collection is an empty
JSON array, never omitted or NULL:

```text
state_schema_version, schema_manifest_hash, watermark,
persons, employees, employee_identities,
person_assignments, employee_assignment_links,
org_units, positions, personnel_orders, personnel_order_items,
personnel_order_item_bases, personnel_order_attachments,
personnel_order_evidence_scopes,
hr_import_batches, hr_import_rows, hr_import_normalized_records,
contacts
```

Selection is the following finite outcome-state closure, not an open-ended “FK closure.” Start with every ID
in the trusted request. Add all Person candidates returned by the ADR-048 exact identity
lookup; `employees.person_id` for selected Employees; Persons of selected assignments;
all Employees whose `person_id` is in that set; every assignment of those Persons in all
lifecycle/flag/date states; every assignment link for those assignments or Employees;
every requested import row/normalized record plus its batch/parent row and every sibling
row explicitly listed in the binding request. For `PERSONNEL_ORDER` evidence add exactly
the requested order header, **all** items where `order_id` equals it, all zero-or-one bases
whose `order_item_id` belongs to those items, and all attachments whose `order_id` equals
it; require the requested evidence item among that item collection. Empty bases and
attachments are literal `[]`, so absent 1:1 basis is represented. Add every
org/position referenced by request, selected Employee, assignment, evidence or order; and
every Contact whose nullable `person_id` is selected (the deployed `contacts` table has no
`employee_id` column). Repeat closure until no ID is added. The result is independent of
mode branches and covers all twenty-one non-unsupported state
predicates; no unrequested same-IIN row is silently added except the complete ADR-048
Person-candidate set. Localized texts, editorial blocks, prints,
`personnel_order_lifecycle_audit`, and `employee_events` do not participate in evidence
validity or any §2 outcome and are normatively excluded; adding any of them later requires
a new state-schema version, lock contract, inventory row and re-review.

Each collection is sorted by its numeric primary key, then by composite key components.
Each row is represented by all physical persisted columns from the reviewed deployed
schema, with keys equal to column names; schema-manifest hash and ordered `pg_attribute`
list are token context, so an added/dropped column invalidates preview. PostgreSQL NULL is
JSON null; BIGINT/INTEGER and NUMERIC are canonical decimal strings; BOOLEAN is JSON
boolean; DATE is `YYYY-MM-DD`; TIMESTAMPTZ is UTC with six fractional digits and `Z`;
TEXT is NFC without trimming; JSON/JSONB is recursively JCS-canonicalized; arrays preserve
database element order. Identity/contact sensitive values are replaced before state JCS
by their existing environment-scoped HMAC object with exact members
`algorithm='HMAC-SHA-256'`, `key_id`, and lowercase-hex `fingerprint`:
`persons.iin`, `employee_identities.identity_value`, `contacts.phone`,
`contacts.telegram_username`, and the decimal-string value of
`contacts.telegram_numeric_id`. The order-evidence columns enumerated in §6 instead use
only the distinct `adr065-po-evidence` profile, typed framing, five-member replacement
object, outer envelope, and key ring of §6.1; no generic environment HMAC may substitute.
NULL remains JSON null;
`contacts.full_name` and every non-sensitive persisted field remain in their ordinary
typed representation. Thus preview and locked apply cannot choose different redaction
sets.

For the two composite predicates the closure is additionally exact, not inferred from
mode: P0 contains the complete empty ADR-048 candidate result plus the Shell-create
intention and its identity-input verifier; P1 contains the complete singleton candidate
row, its expected-state hash and the selected Person row. Both contain the full existing
Employee row with the expected Employee hash and NULL `person_id`, all Employee identity
rows and IIN identity existence/value expectations, the assignment-scope key material and
every assignment/link row proving the required absence of a non-VOID primary, and the
exact requested import batch, `(batch_id,row_id)`, normalized-record and sibling binding
collections. Person/Employee/identity/assignment `row_version` values are included where
the factual schema provides them; otherwise whole-row membership, existence/nonexistence
and the state digest are the version expectation. Apply reacquires the identity and
assignment-scope advisory locks, rebuilds these P0/P1 collections, and returns
`STALE_EXPECTED_STATE` before business DML for any candidate, resolution, link, identity,
assignment, import membership, version, existence or nonexistence difference.

There is no `person_assignment_links` table: Person linkage is represented exactly by
`employees.person_id` and the complete selected Employee row. The following
outcome-critical fields are therefore necessarily present, not abstract
versions: all Person identity/status/merge/source/link fields; every Employee field
including nullable `updated_at`; every `employee_identities` field; every assignment field
including current/future/closed/voided/replacement IDs and §4 `row_version`; every link
field; org `(unit_id,name,code,parent_unit_id,is_active)`; position `(position_id,name)`;
the personnel-order tuples are exact and ordered as follows:

- header by `order_id`: `(order_id,order_number,order_date,order_type_code,order_class,
  status,source_mode,legal_basis_article,signed_by_employee_id,signed_by_name,
  signed_by_position,executor_name,basis_summary,comment,void_reason,voided_at,voided_by,
  void_kind,archived_at,archived_by,archive_reason_code,archive_reason_text,created_by,
  created_at,updated_at)`;
- items by `item_id`: `(item_id,order_id,item_number,item_type_code,employee_id,
  effective_date,period_start,period_end,payload,item_status,void_reason,voided_at,
  voided_by,created_at)`;
- bases by `item_basis_id`: `(item_basis_id,order_item_id,basis_type,
  subject_employee_id,document_date,document_number,free_text,metadata,created_at,
  updated_at)`;
- attachments by `attachment_id`: `(attachment_id,order_id,attachment_kind,storage_type,
  file_path,file_url,file_comment,locale,created_by,created_at)`.

These lists are literal for `state_schema_version=adr065-state-v2`; schema-manifest drift
invalidates every token. Text/JSON normalization and JSON-null encoding are the common
rules above. Import binding,
review, match, normalized
payload/metadata and normalized-record fields; and complete Contact rows. Whole-row
inclusion is the deterministic concurrency marker for tables without `row_version`; there
is no invented Employee, Person, identity, org, position, import or Contact version.
- `personnel_order_evidence_scopes` is a top-level JSON array. It contains exactly one
  object for every selected `personnel_orders.order_id`, selected by equality on that ID,
  sorted by numeric `order_id`, with no duplicate `order_id`. Each object has exactly
  `order_id` and `generation`; both BIGINT values are positive canonical decimal JSON
  strings. If no personnel order is selected the array is exactly `[]`. A selected order
  with no scope row, more than one scope row, NULL/non-positive generation, or a scope row
  without its selected order fails the **initial preview** with
  `ORDER_EVIDENCE_SCOPE_INVALID`; the digest path never creates or repairs a scope row.
  This identical array is used in the
  preview JCS object, token state digest, locked-reread JCS object and stale comparison.
  Once a valid preview has been issued, **every** apply-time difference from that array is
  only `STALE_EXPECTED_STATE`: this includes a missing or malformed formerly valid scope
  row, added/deleted selected order, membership change, `order_id` change, generation
  change, or a replacement row that cannot reproduce the preview tuple. Apply does not
  reclassify such drift as initial structural invalidity. `ORDER_EVIDENCE_SCOPE_INVALID`
  is never returned by the apply path for a valid preview token; an invalid/nonexistent
  preview token fails token validation before any scope read; and
- the one watermark object has exact members `singleton=true`, `effective_date` as
  `YYYY-MM-DD`, positive decimal-string `generation`, and JSON string
  `business_timezone="UTC+05:00"`.

State digest is lowercase SHA-256 of UTF-8 JCS bytes. Identity values are converted to
environment-scoped HMAC fingerprints first. Any participating row creation/deletion/change
must change it. A matching committed replay returns before any boundary/personnel read.
Only after replay misses and the token is trusted, apply takes the shared class-1a lock
`pg_advisory_xact_lock_shared(65002,1)`, then reads the singleton `FOR SHARE`; the boundary
writer takes the exclusive variant. Apply then completes the full §9 lock pass before the
first business INSERT/UPDATE/DELETE: identity rows `FOR UPDATE`; org/position `FOR SHARE`;
each selected personnel-order scope row `FOR UPDATE`, followed by the exact four
collections `FOR SHARE`; existing Persons, Employees, assignments,
links, import/normalized rows
and Contacts `FOR UPDATE`, all in sorted class order. It rebuilds the finite outcome-state closure and
state object under those locks and compares the JCS digest. Missing rows are protected by
the identity/Person-scope advisory locks and applicable unique/FK constraints. The exact
§5.1 schema/current-watermark gate applies before Person classification: absent schema is
`ACTIVE_STATE_SCHEMA_UNAVAILABLE`, invalid cardinality/shape is
`ACTIVE_STATE_WATERMARK_INVALID`, `effective_date<D` is `ACTIVE_STATE_STALE`, and
`effective_date>D` is `ACTIVE_STATE_FUTURE`. Only equality with `D` is current. An
otherwise current row whose date or generation differs from a valid preview returns
`STALE_EXPECTED_STATE`. No branch reaches assignment DML.

### 7.2. Interoperable token

```text
encoded = base64url_no_padding(UTF-8(RFC8785-JCS(payload)))
token = encoded + . + base64url_no_padding(HMAC-SHA256(purpose_key, ASCII(encoded)))
```

Mandatory payload has exactly: `token_version=personnel-preview-v1`, `kid`,
`issued_at`, `expires_at`, `actor_user_id`, `operation_type`, `mode`, nullable
`target_employee_id`, `request_digest`, and `expected_state_digest`. IDs use canonical
decimal strings; digests are 64 lowercase hex. New-enrollment import IDs are bound by
the request digest, not copied into the token. No full IIN or sensitive/free text appears.

Both timestamps are exactly 20 ASCII characters in UTC-seconds form
`YYYY-MM-DDTHH:MM:SSZ`; fractions and offsets other than `Z` are malformed.
`expires_at` must equal `issued_at + 1800 seconds`. Validation fetches database time once
and truncates it down to UTC seconds as `now`. A token is future-invalid when
`issued_at > now + 300 seconds`; equality is accepted. A token is live only while
`now < expires_at`: one second before expiry is live, equality and every later instant
are expired. The five-minute allowance is future clock skew, not an extension of expiry.

Keys come from the dedicated `PERSONNEL_PREVIEW_HMAC` ring, never a general application
secret. The active key has a unique `kid`. On rotation at UTC-second `retired_at`, the old
mapping verifies only while `now < retired_at + 2100 seconds`; at equality it becomes
unknown/retired. A token signed one second before rotation remains verifiable through its
30-minute lifetime because the old key is retained for 35 minutes; token expiry still
wins first at its own boundary.

First-mutation validation is ordered and bounded:

1. reject input over 4096 ASCII bytes, other than exactly two non-empty base64url segments,
   padding, decoded payload over 2048 bytes, duplicate JSON members, or schema/type error;
2. read untrusted `kid` only to select the preview-ring key; absent/unknown/out-of-window
   `kid` returns `PREVIEW_TOKEN_UNKNOWN_KID`;
3. verify HMAC over the encoded segment in constant time; failure returns
   `PREVIEW_TOKEN_INVALID_SIGNATURE`;
4. only after signature success trust and validate purpose/version, actor, operation,
   mode, target, and §8 business request digest;
5. apply the exact TTL/future/expiry rules, then reread and compare locked state digest.

Malformed, unknown-kid, and bad-signature payloads are never trusted for digest or
context. A matching committed replay does not parse the token at all under §8.3.

| Failure | Stable code |
|---|---|
| malformed encoding/schema | `PREVIEW_TOKEN_MALFORMED` |
| unknown/retired key | `PREVIEW_TOKEN_UNKNOWN_KID` |
| bad signature | `PREVIEW_TOKEN_INVALID_SIGNATURE` |
| issued more than five minutes in future | `PREVIEW_TOKEN_NOT_YET_VALID` |
| expired | `PREVIEW_TOKEN_EXPIRED` |
| request digest mismatch | `PREVIEW_REQUEST_MISMATCH` |
| actor/target/mode/operation mismatch | `PREVIEW_CONTEXT_MISMATCH` |
| valid token, changed DB | `STALE_EXPECTED_STATE` |

Signature proves authenticity, not database freshness.

---

## 8. PostgreSQL idempotency and replay

### 8.1. Storage/digest

Migration creates `personnel_orchestration_operations`: identity PK, operation type/mode,
`idempotency_key_fingerprint=lowercase SHA-256(raw key)`, request digest, correlation,
actor/targets, composite `person_resolution_code`, status `IN_PROGRESS|SUCCEEDED`, safe
JSON result and timestamps. `person_resolution_code` is exactly `P0_CREATE | P1_ADOPT`
for `LINK_AND_OPEN_MISSING_ASSIGNMENT` and NULL for every other mode; it is derived from
the already validated static request shape before INSERT and is not generated identity.
The operation table CHECK enforces that closed mode/code relation. Raw key has
at least 128 bits entropy and is never stored/logged. Idempotency is not operation-scoped.
The exact caller/context columns and uniqueness are:

```sql
actor_user_id BIGINT NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
authorization_context_fingerprint CHAR(64) NOT NULL
  CHECK (authorization_context_fingerprint ~ '^[0-9a-f]{64}$'),
idempotency_key_fingerprint CHAR(64) NOT NULL
  CHECK (idempotency_key_fingerprint ~ '^[0-9a-f]{64}$'),
request_digest CHAR(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
identity_input_binding_profile_id TEXT NULL,
identity_input_binding_key_id TEXT NULL,
identity_input_binding_verifier CHAR(64) NULL,
person_resolution_code TEXT NULL,
CONSTRAINT chk_poo_person_resolution CHECK (((
  mode = 'LINK_AND_OPEN_MISSING_ASSIGNMENT'
  AND (
    (
      person_resolution_code = 'P0_CREATE'
      AND target_person_id IS NULL
      AND identity_input_binding_profile_id IS NOT NULL
      AND identity_input_binding_key_id IS NOT NULL
      AND identity_input_binding_verifier IS NOT NULL
    )
    OR
    (
      person_resolution_code = 'P1_ADOPT'
      AND target_person_id IS NOT NULL
      AND identity_input_binding_profile_id IS NULL
      AND identity_input_binding_key_id IS NULL
      AND identity_input_binding_verifier IS NULL
    )
  )
) OR (
  mode <> 'LINK_AND_OPEN_MISSING_ASSIGNMENT'
  AND person_resolution_code IS NULL
)) IS TRUE),
CONSTRAINT chk_poo_identity_input_binding CHECK (((
  identity_input_binding_profile_id IS NULL AND identity_input_binding_key_id IS NULL
  AND identity_input_binding_verifier IS NULL) OR (
  identity_input_binding_profile_id='adr065-idempotency-iin-binding-v1'
  AND identity_input_binding_key_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'
  AND identity_input_binding_verifier ~ '^[0-9a-f]{64}$')) IS TRUE);

CREATE UNIQUE INDEX uq_personnel_orchestration_caller_key
ON public.personnel_orchestration_operations
   (actor_user_id, authorization_context_fingerprint, idempotency_key_fingerprint);
```

`authorization_context_fingerprint` is lowercase SHA-256 over JCS of exactly
`environment_id`, authenticated `actor_user_id`, sorted effective role IDs, sorted allowed
org-unit IDs, and authorization-policy version; IDs are decimal strings and empty arrays
are explicit. Authentication and authorization are recomputed before lookup. Different
caller/context scopes never select one another's row or result. Within one scope the raw
key selects one row for its lifetime; operation is part of `request_digest`, not the
unique key, so changing operation returns `IDEMPOTENCY_KEY_REUSED`.

The **business request digest** is independent of preview state and token bytes. It is
lowercase SHA-256 over UTF-8 RFC8785-JCS of an object with exactly these members; every
member is present and an inapplicable scalar is JSON `null`:

```text
request_schema_version, operation, mode, correlation_id,
actor_user_id, verifier_user_id, confirmation_at, confirmation_reference,
target_employee_id, target_employee_expected_state_hash,
target_person_id, target_person_expected_state_hash, person_shell_create_intention,
identity_expected_state_hash,
identity_input_binding_profile_id, identity_input_binding_key_id,
identity_input_binding_verifier,
import_batch_ids, import_row_ids, normalized_record_ids,
identity_type, identity_fingerprint_profile_id, identity_fingerprint_key_id,
identity_fingerprint,
original_assignment_id, original_assignment_expected_version,
current_assignment_id, current_assignment_expected_version,
future_assignment_id, future_assignment_expected_version,
replacement_target_assignment_id, replacement_target_expected_version,
personnel_order_id, evidence_record_id, evidence_type,
evidence_profile_id, evidence_profile_version, evidence_key_id, evidence_fingerprint,
org_unit_id, org_unit_normalized_stable_code, operator_confirmed_normalized_org_name,
position_id, operator_confirmed_normalized_position_name,
employment_type, rate, is_primary,
start_date, end_date, old_end_date, transition_date,
replacement_start_date, replacement_end_date,
changed_fields, reason_code
```

`correlation_id` is the caller-supplied UUID request identity and participates in the
business digest; it is persisted byte-identically in the operation row and all
operation-owned event/audit/provenance rows. Generated `operation_id` is deliberately
absent from this list: it does not exist until the operation INSERT returns it.

`person_shell_create_intention` is a separate typed value; it never overloads the
persisted-Person expected-state hash. It is JSON null for every link/use-existing-Person
request. It is non-null only when ADR-048 Create-or-Link has selected the CREATE branch,
and then `target_person_id` and `target_person_expected_state_hash` are both JSON null.
Conversely, a non-null `target_person_id` requires a non-null persisted-state hash and a
null create intention. For composite mode the first shape derives `P0_CREATE` and the
second derives `P1_ADOPT`; any other combination fails before idempotency INSERT with
`PERSON_TARGET_INTENT_CONFLICT`.

The create intention is an object with exactly the following members. Unknown or
duplicate members are rejected before JCS; the displayed order is the typed schema order,
while RFC 8785 emits object keys in its required lexicographic order:

```text
{
  schema_version: adr048-person-shell-create-v2,
  identity_type: IIN,
  identity_fingerprint_profile_id: adr065-person-iin-fp-v1,
  identity_fingerprint_key_id: <1..64 ASCII [A-Za-z0-9._-]>,
  identity_fingerprint: <64 lowercase hex>,
  identity_input_binding_profile_id: adr065-idempotency-iin-binding-v1,
  identity_input_binding_key_id: <1..64 ASCII [A-Za-z0-9._-]>,
  identity_input_binding_verifier: <64 lowercase hex>,
  fio_normalization_profile_id: adr065-fio-nfc-ws-v1-unicode-15.1,
  full_name: <non-empty normalized string>,
  last_name: <normalized string or null>,
  first_name: <normalized string or null>,
  middle_name: <normalized string or null>,
  birth_date: <YYYY-MM-DD or null>,
  source: enrollment,
  match_key_scheme: iin,
  person_status: active
}
```

The authenticated body supplies the raw 12-digit IIN to the ADR-048 port, but the JCS
object contains only the closed fingerprint triple
`(identity_fingerprint_profile_id,identity_fingerprint_key_id,identity_fingerprint)`.
The profile is exactly `adr065-person-iin-fp-v1`; its formula is
`HMAC-SHA-256(operational_secret(identity_fingerprint_key_id), message_bytes)` with these
exact `message_bytes`:

```text
ASCII(ADR065) || BYTE(0x00) || ASCII(PERSON_SHELL_IIN) || BYTE(0x00) ||
ASCII(adr065-person-iin-fp-v1) || BYTE(0x00) || ASCII(normalized_iin)
```

Here `ASCII(x)` means every displayed character of `x` encoded as one US-ASCII byte (it
is not PostgreSQL `ascii()`), `BYTE(0x00)` is one NUL byte, and `||` is byte concatenation.

`normalized_iin` is accepted only when it is exactly twelve ASCII bytes `0x30..0x39`;
punctuation, Unicode digits and whitespace are rejected rather than transformed. The
fixed NUL-delimited prefix is the domain separator and makes framing unambiguous. Output
is the 32 HMAC bytes encoded as exactly 64 lowercase hexadecimal ASCII characters.
`match_key_scheme=iin` means ADR-048 derives persisted
`match_key='iin:' || normalized_iin` from that same authenticated raw value. Raw IIN is
never placed in a token, business/state digest, operation row, audit, event, error metadata
or result.

The environment security/key-management authority, not ADR-065 or a domain table, owns
the operational fingerprint secrets. Its signed registry has exactly the states
`SCHEDULED | ACTIVE | VERIFICATION_ONLY | REVOKED | DESTROYED`, activation and retirement
instants, and an immutable `(profile_id,key_id)` identity. The only ordinary transitions
are `SCHEDULED→ACTIVE→VERIFICATION_ONLY→DESTROYED`; emergency authority may move any
non-destroyed key to `REVOKED`, and `REVOKED→DESTROYED` is permitted only after the
retention constraints below. At most one key is ACTIVE for the profile. `SCHEDULED` cannot
create or verify; `ACTIVE` can create and verify; `VERIFICATION_ONLY` can verify an issued
preview/replay miss but cannot create; `REVOKED` and `DESTROYED` can do neither.

Preview chooses the ACTIVE key and binds its triple into the request and token. Apply on a
replay miss verifies the actual raw IIN with that exact retained key; it never substitutes
the current key. The key may not become DESTROYED while an unexpired token (TTL plus skew)
or nonterminal operation references it. Emergency REVOKED takes effect immediately even
for an unexpired token. Replay-miss codes are
`IDENTITY_FINGERPRINT_PROFILE_UNSUPPORTED`,
`IDENTITY_FINGERPRINT_KEY_NOT_YET_VALID`, `IDENTITY_FINGERPRINT_KEY_UNKNOWN`,
`IDENTITY_FINGERPRINT_KEY_RETIRED`, `IDENTITY_FINGERPRINT_KEY_REVOKED`,
`IDENTITY_FINGERPRINT_KEY_DESTROYED`, and `IDENTITY_FINGERPRINT_MISMATCH` respectively.
A nonterminal request blocked by revocation is not silently re-keyed: the client must use
a new idempotency key and preview after the failed operation is resolved by the existing
operation recovery contract. A committed replay does not require this operational key;
it is released only after the independent replay binding below succeeds. Rotation changes
only new previews and never changes bytes of an issued request.

The separate profile `adr065-idempotency-iin-binding-v1` binds the actual identity input
to the idempotency row and is not the operational Person-match fingerprint. Its HMAC key
authority retains verification capability for at least the complete lifetime of every
referencing `personnel_orchestration_operations` row. The exact message is:

```text
HMAC-SHA-256(binding_secret,
  ASCII(ADR065) || BYTE(0x00) || ASCII(IDEMPOTENCY_IIN_BINDING) || BYTE(0x00) ||
  ASCII(adr065-idempotency-iin-binding-v1) || BYTE(0x00) ||
  ASCII(actor_user_id_decimal) || BYTE(0x00) ||
  ASCII(authorization_context_fingerprint) || BYTE(0x00) ||
  ASCII(idempotency_key_fingerprint) || BYTE(0x00) || ASCII(normalized_iin))
```

The output is 64 lowercase hexadecimal characters. All segments are exact ASCII and NUL
framing prevents ambiguity. The server derives it from the authenticated raw IIN; a
caller-supplied verifier is never trusted. Initial CREATE persists the profile ID, key ID
and verifier in the operation row and includes the same triple in the closed request JCS
and token. After scoped lookup, every CREATE retry/replay recomputes with the stored key
and actual submitted raw IIN, compares in constant time, and only then compares business
digest or releases `SUCCEEDED`. Different IIN with a copied object/fingerprint therefore
returns `IDEMPOTENCY_IDENTITY_INPUT_CONFLICT`. Missing/destroyed binding verification
authority returns `IDEMPOTENCY_IDENTITY_BINDING_KEY_UNAVAILABLE`; emergency compromise
returns `IDEMPOTENCY_IDENTITY_BINDING_KEY_REVOKED`. Binding keys have states
`SCHEDULED | ACTIVE | VERIFICATION_ONLY | REVOKED | DESTROYED` and the same ordinary
transition graph as operational keys. `SCHEDULED` returns
`IDEMPOTENCY_IDENTITY_BINDING_KEY_NOT_YET_VALID`; unknown or DESTROYED returns
`IDEMPOTENCY_IDENTITY_BINDING_KEY_UNAVAILABLE`; REVOKED returns the dedicated revoked
code. Rotation moves ACTIVE to VERIFICATION_ONLY and never changes an existing row. Only
ACTIVE creates a verifier; ACTIVE or VERIFICATION_ONLY verifies one. A referencing
operation prevents ordinary destruction; emergency destruction intentionally makes its
result unreleasable rather than bypassing identity verification. Raw IIN is never
persisted or emitted.

The object's profile, key ID, `identity_type` and fingerprint must be byte-equal to the
existing top-level members; inequality is `PERSON_TARGET_INTENT_CONFLICT`, not a choice of
identity source. Consequently the top-level business-request schema also contains
`identity_fingerprint_profile_id` and `identity_fingerprint_key_id` immediately before
`identity_fingerprint`; all three are required together or JSON null together.

All name inputs use immutable profile `adr065-fio-nfc-ws-v1-unicode-15.1`: Unicode NFC
under Unicode 15.1.0, then each maximal run of the following closed Unicode 15.1
`White_Space` code points is replaced by one U+0020 and leading/trailing U+0020 is
removed: `U+0009..U+000D, U+0020, U+0085, U+00A0, U+1680, U+2000..U+200A,
U+2028, U+2029, U+202F, U+205F, U+3000`. No runtime Unicode-property lookup is
normative. Punctuation and hyphens are preserved byte-for-byte after NFC, and no case
conversion or transliteration occurs. The fixed member
`fio_normalization_profile_id=adr065-fio-nfc-ws-v1-unicode-15.1` is required; another
value returns `PERSON_SHELL_FIO_PROFILE_UNSUPPORTED`.
`full_name` is authoritative, required and non-empty. Components have exactly two legal
shapes: all three JSON null; or non-null `last_name` and `first_name` with nullable
`middle_name`. A supplied component normalizing to empty is invalid, never null. When
components are present, compare exactly `last_name + U+0020 + first_name` plus
`U+0020 + middle_name` only when middle name is non-null; the result must equal normalized
`full_name` byte-for-byte. The port passes authoritative `full_name` and never rebuilds it.
Mixed shape returns `PERSON_SHELL_FIO_INVALID`; unequal composition returns
`PERSON_SHELL_FIO_MISMATCH`, before idempotency INSERT and ADR-048 invocation. The exact
counterexample `full_name=Иванов Иван; last_name=Петров; first_name=Иван;
middle_name=null` has only `PERSON_SHELL_FIO_MISMATCH`.
`birth_date` is either JSON null or the exact Gregorian
`YYYY-MM-DD` encoding already used by ADR-048. `schema_version`, `identity_type`,
`source`, `match_key_scheme`, and `person_status` are fixed literals and cannot be
caller-selected. The ADR-048 port validates that these fields describe the same Shell it
will create; ADR-065 defines only request representation and does not become Person
authority.

Fixed non-secret vectors are normative: `Иванов<U+00A0>Иван`,
`Иванов<U+202F>Иван`, `Иванов<U+2003>Иван`, and `Иванов<U+3000>Иван` each normalize to
`Иванов Иван`; the decomposed sequence `Cafe` plus U+0301 normalizes to `Café`; ASCII
hyphen and punctuation remain unchanged. In addition, the conformance vector set inserts
every individual code point from the closed list (including every member of both ranges)
between `A` and `B` and requires exactly `A B`. Angle-bracket notation identifies the
single Unicode scalar, not literal angle-bracket text. Implementations execute the entire
set, not a sample of a range.

`person_shell_create_intention_digest` is the lowercase SHA-256 of the UTF-8 RFC 8785 JCS
bytes of that object. It is a derived diagnostic value, not an additional request member;
the complete object itself is the `person_shell_create_intention` member of the business
request JCS. Therefore a change in normalized name, birth date, identity or any fixed
Shell semantic changes the business request digest. Normalization-equivalent input yields
identical bytes. Existing-Person link requests contain JSON null and cannot smuggle a
create payload.

All database IDs and assignment expected versions are positive canonical decimal JSON
strings. Assignment version means §4.2 `row_version`; a new replacement has both target
fields null. Dates are `YYYY-MM-DD`; `confirmation_at` is UTC-seconds
`YYYY-MM-DDTHH:MM:SSZ`; rate is a canonical non-exponent decimal string with no redundant
leading/trailing zero; booleans are JSON booleans. Enum/code/name normalization follows
§§2,4,12. `identity_fingerprint` and `evidence_fingerprint` are 64 lowercase hex.
For PERSONNEL_ORDER, profile ID/version/key ID and fingerprint obey §6.1 and all four
members participate in the digest; for EXTERNAL_REFERENCE the three profile members are
JSON null and the opaque fingerprint remains non-null.
`confirmation_reference` is validated ASCII matching
`^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$` and is hashed byte-for-byte; reason/evidence/org
codes are their exact persisted trimmed ASCII values with no case coercion.
`import_batch_ids`, `import_row_ids`, and `normalized_record_ids` are arrays of
unique decimal strings sorted by numeric value. `changed_fields` is a duplicate-free array
sorted by ASCII member name from the closed set `employment_type|is_primary|org_unit_id|
position_id|rate`. No other collection is permitted.

The three expected-state hashes are lowercase SHA-256 over JCS exact tuples, not abstract
versions. Employee tuple is `(employee_id,person_id,full_name,department_id,position_id,
date_from,date_to,employment_rate,is_active,org_unit_id,operational_status,enrolled_at,
enrolled_by_user_id,enrollment_source,updated_at)`. Person tuple is `(person_id,iin HMAC,
full_name,last_name,first_name,middle_name,birth_date,match_key,person_status,
merged_into_person_id,source,canonical_snapshot_id,canonical_entry_id,created_at,
updated_at)`. Identity tuple is the numerically sorted array of `(identity_id,employee_id,
identity_type,identity_value HMAC,valid_from,valid_to,is_primary,created_at,created_by)`.
SQL NULL is JSON null; dates and timestamps use the §7 encoding; NUMERIC is a canonical
decimal string; text is NFC without trimming unless a field-specific rule above says
otherwise. Because every persisted field is included, correctness does not depend on the
nullable `employees.updated_at` being maintained by every legacy writer.

`target_person_expected_state_hash` remains exclusively the hash of an already persisted
locked Person tuple below. It is never computed for an absent Person and never encodes a
proposed Shell. Consequently different original/current/future/replacement assignment IDs, different
expected versions, verifier/confirmation, personnel-order/evidence record, or any episode
attribute, expected normalized org name, or Employee/Person/identity expected tuple
or Person Shell create intention necessarily changes the digest. `expected_state_digest`,
preview token and raw IIN are not members. Normalized Shell name fields are the only
Person-create text members; no unstructured note/free-text field may be added without a
new request schema version. The object is derived entirely from the authenticated body
before token parsing; authorization-before-replay and §8.3 replay ordering are unchanged.

### 8.2. Exact state machine

After authorization and successful read-only `REQUEST_COMPLETENESS`, derive the exact
caller/context fingerprint, acquire the §9
operation advisory lock from `context_fingerprint + U+0000 + key_fingerprint`, then
first select a committed row by the three unique-key columns `FOR UPDATE`; operation type
is deliberately not a lookup predicate. A found row follows the replay/conflict rules
below before token or personnel reads.

If no committed row exists, the already completeness-validated request executes:

```sql
INSERT INTO personnel_orchestration_operations (..., status)
VALUES (..., 'IN_PROGRESS')
ON CONFLICT (actor_user_id, authorization_context_fingerprint,
             idempotency_key_fingerprint) DO NOTHING
RETURNING operation_id;
```

The held advisory lock makes an unexpected zero-row INSERT a contract violation rather
than a retry branch. The returned generated `operation_id` is then used only as the
operation-owned FK/provenance reference; it was not an input to `request_digest`.
Token validation and the remaining reference/identity/locked-state gates then run in the
§2 precedence and §9 lock order before the first business/domain/import write; any failure
rolls back the uncommitted operation row.
Before inspecting a previously committed row's digest or result, a CREATE request
recomputes the stored-profile §8.1 identity-input verifier from the actually
submitted raw IIN and stored scope. A binding mismatch, unavailable key, or revoked key
returns the exact binding code and never exposes stored result metadata. A LINK request
requires the row binding triple to be all NULL. The advisory lock means the predecessor
finished:

- `SUCCEEDED` + same digest → stored result with `replayed=true`;
- different digest → `IDEMPOTENCY_KEY_REUSED`;
- committed `IN_PROGRESS` → `IDEMPOTENCY_OPERATION_INCOMPLETE`, no business write;
- no row after predecessor rollback → rerun the no-row completeness/token/state path and
  execute one fresh INSERT only after it passes.

Normal `IN_PROGRESS` exists only within the transaction; rollback removes it and every
business write. Only `SUCCEEDED` normally commits. SQLSTATE `40001`/`40P01` may restart
the whole transaction at most three times with bounded jitter and the same key/request.
Domain unique conflicts are not blind retries.

Stored result supports replay without personnel reads: codes, operation/correlation IDs,
Employee/Person outcomes, assignment/link/import/Contact/audit IDs, completion time; no
names, IIN, evidence text, phone/email/credentials.

For timeout/unknown commit outcome the client retries the same key/request. Committed
success returns stored result; rollback starts one fresh atomic attempt; changed request
conflicts. No outcome is inferred from personnel rows.

### 8.3. Replay before preview expiry

This ADR selects protocol A: replay uses only the trusted request body's business digest.
The mandatory algorithm is:

1. authenticate and authorize the actor for the request-body operation/target;
2. validate `REQUEST_COMPLETENESS`, including the eight composite assignment decisions
   and the actual raw IIN only in the authenticated transient input, and derive operation,
   mode, correlation, key fingerprint and §8.1 business request digest; return
   `ASSIGNMENT_INTENT_INCOMPLETE` before lookup/INSERT when applicable and do not parse
   the preview token;
3. acquire the operation advisory lock and select the committed operation by unique key;
4. for a selected CREATE row, recompute the stored-profile identity-input verifier from
   the actual raw IIN and stored caller/context/key scope; mismatch/unavailable/revoked
   returns its stable code before result or digest disclosure; LINK requires a NULL triple;
5. only after step 4, `SUCCEEDED` plus equal business digest returns stored result with
   `replayed=true` and performs no token, personnel, operational-fingerprint-key or
   freshness read;
6. an existing unequal digest returns stable `IDEMPOTENCY_KEY_REUSED`, even if the token
   contains some other digest;
7. only when no committed result exists, run the complete §7.2 token validation, require
   its trusted request digest/context to equal the body, and then compare locked state;
8. only a live, fully valid token may begin the first mutation.

Consequently an expired token blocks first mutation but a matching, authorized,
identity-input-bound committed replay survives expiry and operational-key rotation.
Malformed, unknown-kid, and bad-signature token content is never a trusted digest source.
A copied create object/fingerprint submitted with a different raw IIN cannot pass step 4.
A same-key/different-business request always conflicts. Optional replay-audit failure
neither blocks the stored result nor starts a new operation.

---

## 9. Global lock protocol and rollout

### 9.1. Discovery and advisory keys

Unlocked discovery reads may only collect candidate IDs. Every decision row is reread
after locks before write.

Use transaction advisory locks `(namespace_int32,key_int32)`:

| Namespace | Value | UTF-8 key material before SHA-256 |
|---|---:|---|
| operation | `65001` | `authorization_context_fingerprint + U+0000 + idempotency_key_fingerprint` |
| boundary run | `65002` | fixed second key `1`; exclusive for worker, shared for apply |
| identity | `65003` | `identity_type + U+0000 + environment identity fingerprint` |
| assignment scope | `65004` | decimal `person_id` |

Second key is first four SHA-256 bytes interpreted signed big-endian int32. Multiple keys
sort by `(namespace,key)`. Collision only over-serializes; exact DB values/constraints are
always revalidated, so collision never establishes identity or correctness.

Personnel-order evidence uses a persisted scope row, not predicate/child-row locking:

```sql
CREATE TABLE public.personnel_order_evidence_scopes (
  order_id BIGINT PRIMARY KEY
    REFERENCES public.personnel_orders(order_id) ON DELETE RESTRICT,
  generation BIGINT NOT NULL DEFAULT 1 CHECK (generation > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp()
);
INSERT INTO public.personnel_order_evidence_scopes(order_id)
SELECT order_id FROM public.personnel_orders
ON CONFLICT (order_id) DO NOTHING;
```

Migration preflight requires exactly one scope row per existing order and no orphan.
Rollout quiesces every order/evidence route, worker and CLI while the table/backfill is
installed; then deploys all migrated helpers as one artifact; then static/runtime/catalog
proof and startup gate run; only then may those writers be re-enabled together. There is
no interval in which scoped and unscoped writers are both enabled.
Every new-order writer INSERTs header then scope row in the same transaction **before**
any item/basis/attachment INSERT. For an existing order, every header/item/basis/
attachment INSERT, UPDATE or DELETE first locks its scope row using this literal query;
multiple order IDs sort ascending:

```sql
SELECT order_id, generation
FROM public.personnel_order_evidence_scopes
WHERE order_id = ANY(:sorted_order_ids)
ORDER BY order_id
FOR UPDATE;
```

The writer performs child/header DML and finally increments each retained scope row by
one (`generation=generation+1, updated_at=transaction_timestamp()`). Hard delete locks the
scope, deletes children, deletes the scope, then deletes the header in one transaction.
For a writer or initial preview, missing scope or count mismatch is
`ORDER_EVIDENCE_SCOPE_INVALID`. Apply with a valid preview takes the same
exclusive scope lock, locks/rereads the exact §7.1 header/items/bases/attachments, and
recomputes digest before mutation; this excludes phantom INSERT, UPDATE, DELETE and
replacement. Any missing/count/membership/generation difference at that apply reread is
only `STALE_EXPECTED_STATE`. Rollback releases the lock and generation change; retry rereads it. This
protocol is mandatory for orchestrator and every direct/indirect writer. It becomes a
production guarantee only when §9.4 proves that no unknown/dynamic writer can bypass it.

### 9.2. One global order

Writers may skip unused classes but never return to an earlier class:

1. operation advisory lock and operation row; boundary worker instead locks its exact
   `person_assignment_boundary_runs` row here;
1a. boundary serialization: worker takes exclusive
   `pg_advisory_xact_lock(65002,1)` then watermark `FOR UPDATE`; first mutation after a
   replay miss takes `pg_advisory_xact_lock_shared(65002,1)` then watermark `FOR SHARE`;
2. identity advisory locks;
3. referenced org-unit rows by `unit_id`, then position rows by `position_id`, both
   `FOR SHARE` when their current attributes participate in a decision;
3a. personnel-order evidence scope rows by `order_id` `FOR UPDATE`;
3b. personnel-order header, items, bases and attachments in that order, each by primary
   key `FOR SHARE` for apply; their writers already hold 3a and acquire row UPDATE locks;
4. Person rows by `person_id`;
5. assignment-scope advisory locks by `person_id`;
6. Employee rows by `employee_id`;
7. assignments by `assignment_id`;
8. assignment links by `link_id`;
9. import rows by `(batch_id,row_id,normalized_record_id)`;
10. Contact rows by `contact_id`;
11. personnel application rows by `application_id`;
12. onboarding rows by `onboarding_id`;
13. onboarding checklist rows by `item_id`, then attachments by `attachment_id`;
14. task-audit rows, then notifications by `notification_id`, recipients by `user_id`;
15. delivery rows by `(notification_id,user_id,channel)`, then delivery attempts by
    `attempt_no`.

Class 1a is omitted only by a writer that cannot read or alter assignment-current state;
classes 3a/3b are mandatory for every selected personnel-order evidence reader/writer.
every assignment/current-Employee writer takes it. New Person uses identity lock before INSERT. Employee without Person resolves/locks or
creates Person before locking Employee. C2 without IIN uses known Person scope. The unique
index is the hard guarantee where no assignment row exists. Application-apply retains
3a/3b through classes 11–15. Standalone onboarding/task/reminder/ACK paths do not read or
mutate personnel-order evidence and therefore skip 3a/3b, but begin at their first used
class and never acquire an earlier class later. Multi-item paths sort unique onboarding and
item IDs before any row lock.

### 9.3. Writer matrix

Every migrated callsite uses one shared lock helper. “Current” is evidence from this
revision, not approval. Each row below names concrete repository paths; the generated
artifact expands every SQL/ORM call in each path to `file:line`, normalized SQL fingerprint,
entrypoint, and disposition. `Manifest+CI` means the callsite fingerprint must show the
approved helper sequence, or CI/startup proves the entrypoint absent/disabled.

| Exact writer path(s) / mutating callable(s) | Mutated tables/entity classes | Current locks | Required order | Disposition | Disposition proof |
|---|---|---|---|---|---|
| `app/services/hr_import_service.py` | batches, `hr_import_rows` | no common helper at direct DML | batch immediately before sorted import class 9 | migrate | Manifest+CI; route branch coverage supplemental |
| `app/services/hr_import_monthly_diff_service.py` | rows, normalized records, diff removals | none common | linked entities then sorted class 9 | migrate or disable | Manifest+CI |
| `app/services/hr_import_education_profile_service.py` | `hr_import_rows` override/review/status | none common | sorted class 9 | migrate | Manifest+CI |
| `app/services/hr_import_employee_binding_service.py` | rows, normalized records, Employee binding | none common | identity→Person→scope→Employee→9 | migrate all functions | Manifest+CI |
| `app/services/hr_import_enroll_employee_service.py` | Employee, identities, rows, normalized, events, audit, Contact | caller transaction but no common order | operation 1→shared 1a→2–10 | disable legacy apply; replace with orchestrator | package exclusion + route-disabled assertion |
| `app/services/hr_import_review_exception_detail_service.py` | rows, normalized review/detail/decision | none common | linked entities then 9 | migrate | Manifest+CI |
| `app/services/hr_import_roster_promotion_service.py` | Employee, identity, rows, normalized | none common | identity→Person→scope→Employee→9 | migrate or disable | Manifest+CI |
| `app/services/hr_import_normalized_record_service.py` | normalized INSERT/UPSERT/UPDATE/DELETE and review state | no common helper | sorted class 9 | migrate every mutating function | Manifest+CI; all SQL fingerprints required |
| `app/services/hr_import_promotion_service.py` | employee documents, normalized promotion state | no common helper | Person/scope→Employee→document→9 | migrate or disable | Manifest+CI |
| `app/services/hr_import_diff_removal_decision_service.py` | diff removals/decisions and binding effects | no common order | linked Person/scope/Employee then 9 | migrate or disable | Manifest+CI |
| `app/services/hr_import_document_candidate_service.py` | document candidates/import state | no common order | linked entities then 9 | migrate or disable | Manifest+CI |
| `app/services/hr_import_complete_review_service.py`, `hr_baseline_service.py`, `hr_import_control_list_storage.py` | import batches/control/baseline state | local transactions | class 9, batch before child rows | migrate or disable mutating entrypoints | Manifest+CI |
| `app/services/hr_import_complete_review_service.py::complete_import_review`; incoming manual complete-review routes | indirect `_transition_batch_to_apply_pending` UPDATE of batch status/review completion after blocker reads | caller `Connection` | class 9 batch `FOR UPDATE` before child/blocker reads | migrate caller and helper as one conditional transition or disable manual completion | callable/helper/route fingerprints + complete/replay runtime + batch status catalog proof |
| `app/services/hr_baseline_service.py::publish_baseline_from_batch`; incoming baseline publication route/service | INSERT `hr_control_list_baselines`, ordered `hr_baseline_entries`, INSERT/UPDATE `hr_publication_origins` | caller transaction | class 9 source batch → baseline → entries by source row → publication origin | migrate full callable; identical published batch reread, conflicting force request rejected | every statement/caller fingerprint + zero/many/rollback runtime + baseline/origin catalog proof |
| `app/services/hr_import_control_list_storage.py::_insert_source_file`; incoming `create_control_list_batch` | INSERT `hr_source_files` content/hash/name/import metadata | caller transaction | class 9 import code/source-file identity before batch | migrate parent callable; file hash/import code idempotency; caller rollback | callable/INSERT/parent fingerprints + identical/conflict runtime + source-file unique/catalog proof |
| `app/services/hr_personnel_lifecycle_service.py::_create_lifecycle_run`; incoming lifecycle execution entrypoint | INSERT `hr_personnel_lifecycle_runs` request/options/status | lifecycle caller transaction | class 1a boundary/shared gate → class 9 snapshot/run | migrate to controlled run identity; replay by run correlation only | callable/INSERT/entrypoint fingerprint + create/crash runtime + run PK/status catalog proof |
| `app/services/hr_personnel_lifecycle_service.py::_finalize_lifecycle_run`; incoming lifecycle execution `finally` path | UPDATE `hr_personnel_lifecycle_runs` terminal counts/report/status | same lifecycle transaction when caller-owned; current alternate boundaries disabled | class 1a → class 9 locked run | migrate to conditional expected STARTED finalization; no detached success evidence | callable/UPDATE/all exit edges + rollback/unknown-commit runtime + run CHECK catalog proof |
| `app/services/hr_import_ai_extraction_service.py`, `hr_import_analytics_service.py` | import extraction/analytics persisted state | local transactions | sorted class 9 | disable mutation or migrate | Manifest+CI |
| `app/services/hr_import_review_exception_service.py` | none currently | read-only | none | keep read-only; disable on any DML fingerprint | static gate assertion |
| `app/directory/hr_import_routes.py` | indirect entrypoint to all listed HR-import writers | route-level only | inherits each called writer order | disable each route whose callee is not migrated | call-graph manifest + route enablement assertion |
| `scripts/prepare_adr059_phase1_ui_batch.py` | batches, rows, normalized, removals indirectly | no common lock | class 9 | exclude/disable in production | signed package deny-list + static manifest |
| `scripts/prepare_adr059_phase2_ui_batch.py` | rows and monthly-diff state | no common lock | class 9 | exclude/disable in production | signed package deny-list + static manifest |
| `scripts/backfill_hr_import_normalized_records.py::main` → `hr_import_normalized_record_service.populate_normalized_records` | `hr_import_normalized_records` INSERT/UPDATE/DELETE for each selected batch | `engine.begin`, no common entity locks | sorted class 9 after FK-closure lock pass | migrate CLI and callee or disable command | CLI call-graph fingerprint + package/command disable assertion + runtime branch observation |
| `scripts/repair_hr_import_employee_bindings.py::main` → `hr_import_employee_binding_service.repair_batch_employee_bindings` | `hr_import_rows`, `hr_import_normalized_records`, Employee binding references | `engine.begin`, no common order | identity→Person→scope→Employee→sorted class 9 | migrate CLI and every called mutator or disable command | CLI call-graph fingerprint + package/command disable assertion + runtime branch observation |
| `scripts/hr_import_fio_fix_rebuild_report.py` apply path | rows; normalized rebuild with intermediate commits | no common lock; owns commits | class 9, one transaction | disable `--apply` in production | packaging exclusion + startup command deny-list |
| `app/services/employee_hard_delete_service.py` dynamic table-name paths | Employee, identities, assignments/links, `hr_import_*`, events, Contact, Person | Employee `FOR UPDATE`; incomplete order | identity→Person→scope→Employee→assignment/link→9→10 | disable the route wherever assignments/Person are reachable; direct assignment DELETE is forbidden and cannot be re-enabled by this ADR | route-disabled assertion + dynamic target list fingerprint |
| `app/services/enrollment_service.py` | Employee, assignment links, queue, Contact | route-local | operation 1→shared 1a→identity→Person→scope→Employee→links→queue→10 | migrate | Manifest+CI |
| `app/services/enrollment_service.py::_create_employee_for_assignment`; incoming `enroll_from_assignment` | dynamic-column INSERT `employees` including Person/assignment-derived projection fields | enrollment caller transaction | shared 1a → identity/Person/scope → Employee | migrate behind strict orchestrator/C2 projection or disable legacy enrollment path | callable/dynamic-column INSERT/caller fingerprint + column-set runtime + Employee catalog proof |
| `app/services/enrollment_service.py::_ensure_assignment_link`; incoming `enroll_from_assignment` | SELECT then UPDATE or INSERT `employee_assignment_links(employee_id,assignment_id,source_event_id,linked_at,linked_by_user_id,...)` | same enrollment transaction | assignment scope/rows → Employee → assignment link | migrate to common lock helper; identical link replay, conflicting owner rejected | callable/two DML/caller fingerprints + insert/update/race runtime + unique/FK catalog proof |
| `app/services/hr_effective_monthly_diff_service.py::materialize_personnel_change_events`, `run_effective_monthly_diff`, `run_effective_monthly_diff_tx` | `hr_personnel_change_events` INSERT and downstream review-queue state | caller/local transaction; no global helper | shared 1a before canonical event materialization, then Person/scope references; event before C2 consumption | migrate all three entrypoints; never disable canonical authority silently | SQL fingerprint + call-graph manifest + runtime scheduled/manual branch + catalog FK proof |
| `app/services/hr_person_assignment_sync_service.py`, `hr_personnel_lifecycle_service.py` all mutating handlers | Person, assignments, links, canonical status, Employee | C2-local only | shared 1a→identity/Person→scope→Employee→assignments/links | migrate all handlers and increment `row_version`; C2 remains authority | Manifest+CI and direct-assignment ownership assertion |
| C2 `assignment_boundary_activation_tx` | assignment lifecycle/flags, Employee projection, watermark | new | exclusive class 1a→Person→scope→Employee→assignment; watermark UPDATE last | implement only in C2 | namespace/callsite fingerprint + PG-76–80 |
| new orchestrator, ADR-048, strict-C2 and reconciliation ports | operation, Person, Employee, identity, assignment/link, import, events/audit, Contact | new | operation 1→shared 1a→exact 2–10 | enable only after gate | signed manifest + startup gate |
| `app/personnel_applications/application/hire_order_draft_service.py::_create_draft_hire_order`, `create_hire_order_draft_for_application` | INSERT `personnel_orders`, then INSERT `personnel_order_items` | caller transaction; no scope row | class 3a immediately after new header, before item | migrate: insert scope before item and bump generation | two SQL fingerprints + call graph + runtime transaction/scope tokens |
| `app/services/personnel_orders_command_service.py::{create_personnel_order_draft,update_personnel_order_draft,create_personnel_order_item,update_personnel_order_item,upsert_personnel_order_localized_text,mark_personnel_order_ready_for_signature,register_personnel_order}` and `_mark_editorial_stale`/order touch paths | INSERT/UPDATE order; INSERT/UPDATE item; localized-text DML that also touches order | service transactions; row checks, no common scope | class 3a→3b before every outcome-state DML; new header creates scope | migrate all named branches | per-callable SQL fingerprint + runtime branch/scope-generation evidence |
| `app/services/personnel_orders_archive_service.py::{archive_personnel_order,restore_personnel_order}` | UPDATE order archive/status fields | order read, no scope | class 3a→header UPDATE | migrate | two SQL fingerprints + helper-token runtime evidence |
| `app/services/personnel_orders_editorial/repository.py::{ensure_default_basis,touch_order_updated_at}` reached from `generation_service.generate_editorial` | INSERT `personnel_order_item_bases`; UPDATE order timestamp | basis existence read; no phantom-safe lock | resolve order→class 3a→basis/header | migrate direct functions and indirect path | direct+indirect call-graph fingerprint, absent-basis runtime branch and generation assertion |
| `app/services/personnel_orders_void_service.py::{_mark_item_voided,_mark_order_voided,_void_item_with_events,_maybe_promote_order_void,void_personnel_order,void_personnel_order_item}` | UPDATE items/orders; lifecycle/event side state, with Employee restore paths | route-local locks, no evidence scope | shared 1a when current projection participates→identity/org refs→3a→3b→Person/Employee/event | migrate | all statement/caller fingerprints + scope-first runtime evidence |
| `app/services/personnel_orders_cancel_service.py::cancel_personnel_order` → void helpers | UPDATE items/orders plus lifecycle audit | engine transaction; no evidence scope | class 3a→3b before audit | migrate caller and shared void helpers | direct/indirect graph + all item-loop branches + scope-generation evidence |
| `app/directory/personnel_orders_routes.py::{create_personnel_order_route,update_personnel_order_route,create_personnel_order_item_route,update_personnel_order_item_route,upsert_personnel_order_localized_text_route,mark_personnel_order_ready_for_signature_route,generate_personnel_order_editorial_route,register_personnel_order_route,apply_personnel_order_route,cancel_personnel_order_route,archive_personnel_order_route,restore_personnel_order_route,void_personnel_order_route,void_personnel_order_item_route}`; `app/directory/personnel_applications_routes.py` hire-draft branch | indirect entrypoints to the preceding order/header/item/basis writers and order-linked Employee/event writers | route-level `call_service`; no independent scope | inherits class 3a/3b and every later class of each reachable callee | disable each route until every reachable writer is migrated | route-to-callee graph fingerprint + route enablement assertion + runtime branch coverage |
| `app/services/personnel_order_hire_from_person_service.py::{create_employee_for_hire,ensure_person_assignment_for_hire,link_order_item_employee}` | Employee, direct assignment/link, UPDATE order item employee | route-local direct assignment SQL; item update no scope | shared 1a→identity/org refs→3a→3b→Person→assignment scope→Employee→assignment/link | remove direct assignment SQL in favor of strict C2; migrate item update | static absence assertion + C2 fingerprint + item scope token |
| `scripts/local_demo/wp_po_007_pilot_seed.py::{_cleanup_order,_cleanup_pilot,main,create_order,add_item,register,apply}` | INSERT/UPDATE/DELETE orders/items/localized text and related Employee/events | script transaction, no scope | class 3a→3b before child/header cleanup | disable entire script in production package | exact callable/SQL fingerprints + signed package/command deny-list |
| `scripts/ops/local_data_cleanup/position_contours_domain.py::{build_delete_steps_from_allowlist,run_position_contours_execute}` | dynamic DELETE orders/items/bases/attachments and other discovered child tables | allowlist/signature checks; no scope lock | sorted class 3a→3b, then later entity classes | disable execute command in production; a future enablement must migrate dynamic delete helper | dynamic table allowlist fingerprint + packaging/startup command denial |
| `alembic/versions/p0q1r2s3t4u5_wp_po_003_personnel_orders_foundation.py::{upgrade,downgrade}`, `r2s3t4u5v6w7_wp_po_008_nullable_order_registration_fields.py::{upgrade,downgrade}`, `s3t4u5v6w7x8_wp_po_edit_002_editorial_persistence.py::{upgrade,downgrade}`, `t4u5v6w7x8y9_wp_po_lc_del_003_lifecycle_audit_foundation.py::{upgrade,downgrade}` | create/drop/ALTER order evidence tables; t4 UPDATEs order lifecycle/archive fields | Alembic transaction; no runtime locks | migration-only, before R6 scope migration; never runtime | classify exact revisions applied; pending execution requires separate reviewed migration plan | Alembic current/head + exact revision/SQL/catalog fingerprint |
| `app/services/personnel_orders_apply_service.py::{apply_personnel_order,apply_personnel_order_in_conn,_apply_hire,_apply_transfer,_apply_termination,_apply_rate_change}`, `personnel_events_service.py::{_handle_transfer,_handle_position_change,_handle_rate_change}` | order/item reads drive Employee/event writes | route-local; Employee `FOR UPDATE`, no evidence scope | shared 1a when assignment projection→identity/org refs→mandatory 3a/3b→Person/scope→Employee→event | migrate every read-to-write path | per-callable read/DML fingerprint + scope token + runtime branch evidence |
| `app/personnel_applications/application/application_apply_service.py::{orchestrate_hire_apply_for_application,apply_hire_for_application,try_complete_linked_application_after_order_apply,complete_application_after_hire,_complete_application}` | SELECT personnel application, order header and `employee_events`; through `apply_personnel_order_in_conn` UPDATE Employee/users and INSERT Employee events; UPDATE `personnel_applications.status,updated_at,completed_at,closed_at,closed_by_user_id`; UPDATE `personnel_record_metadata` intended projection; INSERT application lifecycle audit; through onboarding bootstrap INSERT onboarding/checklist/notification rows | precheck uses a separate read transaction; `orchestrate_hire_apply_for_application` owns main `engine.begin`; reverse hook inherits order-apply connection; no order scope in the reviewed code | any authoritative order-derived branch reacquires sorted class 3a then 3b before its final order/event/application reread; then Person/Employee/event, application metadata/audit, onboarding and notification rows; it never relies on the precheck snapshot | migrate the main and reverse-hook branches as one caller-owned transaction or disable both entrypoints; precheck remains advisory only | direct callable and terminal SQL fingerprints + route/service/reverse-hook graph + runtime fresh/already-applied/replay/rollback branches + catalog FK/trigger inventory |
| `app/directory/personnel_applications_routes.py::post_application_apply` → `orchestrate_hire_apply_for_application` → `apply_hire_for_application` → `apply_personnel_order_in_conn`/completion closure | indirect route for the complete preceding order/event/application/onboarding closure | route auth then callee-owned transactions | inherits mandatory 3a/3b and every later class; no route-local DML | disable route until every reachable callable, including photo precondition paths, has a disposition and the authoritative transaction reacquires scope | exact route-to-terminal-DML graph + route enablement assertion + runtime route success/failure/replay evidence |
| `app/services/personnel_orders_apply_service.py::apply_personnel_order_in_conn` → `application_apply_service.try_complete_linked_application_after_order_apply` → `complete_application_after_hire` | reverse order hook UPDATEs application/metadata, INSERTs application lifecycle audit and bootstraps onboarding/checklist/notifications after Employee events | same caller `Connection`; currently invoked after order apply | scope 3a/3b is retained from order reread through hook completion; application/onboarding DML remains after Employee/event classes and before commit | migrate hook and caller together; disabling only the forward route is insufficient | reverse-edge call-graph fingerprint + same-connection token + runtime linked/unlinked/already-completed branches + catalog closure |
| `app/person_photos/application/hire_apply_hook.py::{ensure_hire_photo_ready,_upsert_open_blocker_durable,_resolve_photo_blockers_durable}` → exact photo/blocker rows below | SELECT application/intake photo; durable blocker/photo/PPR DML described below | separate `engine.begin` transactions before main application apply | identity/Person/photo/PPR order; never holds or substitutes for order scope; main transaction subsequently takes sorted 3a/3b and rereads | migrate/retain only as idempotent precondition; disable application apply if any exact edge below is absent | exact callable/SQL fingerprints + transaction-owner/runtime blocker/canonicalization/retry evidence + catalog proof |
| `app/employee_onboarding/application/bootstrap_service.py::create_onboarding_from_hire` → exact repository rows below | onboarding/checklist/notification outbox DML described below; replay SELECT only | caller connection from application completion | retained sorted 3a/3b → Person/Employee/events → onboarding/checklist/notification IDs | migrate all exact rows in the caller transaction or disable application apply | exact terminal fingerprints + graph + runtime first/replay/rollback + catalog FK proof |
| `app/personnel_applications/infrastructure/repository.py::SqlAlchemyPersonnelApplicationRepository.update_application_fields`; incoming forward/reverse chain `complete_application_after_hire` → `_complete_application` | UPDATE `personnel_applications` by `application_id`: `status`, `updated_at` (and only when supplied resolution/order fields) | forward main `engine.begin`; reverse caller `Connection` | sorted 3a/3b retained, then application row; no independent commit | migrate with main/reverse closure; rollback is caller-wide; replay sees completed status | callable+dynamic-SET SQL fingerprint; forward/reverse runtime branches; column/catalog proof |
| `app/personnel_applications/application/envelope_projection.py::sync_envelope_intended_projection`; incoming `_complete_application` | UPDATE `personnel_record_metadata` by `person_id`: `intended_org_group_id,intended_org_unit_id,intended_position_id,intended_employment_rate,updated_at` | same caller transaction | retained 3a/3b → Person/Employee → metadata | migrate in same transaction; idempotent projection; rollback/retry with completion | two UPDATE fingerprints (set/clear) + runtime active/absent branch + catalog proof |
| `app/personnel_applications/application/lifecycle_service.py::record_completed_from_apply`; incoming `complete_application_after_hire` | UPDATE `personnel_applications.completed_at,closed_at,closed_by_user_id` using `COALESCE` | same caller transaction | after application status/metadata, before lifecycle audit | migrate in same transaction; replay preserves first terminal values; caller rollback | direct UPDATE fingerprint + fresh/replay/rollback runtime evidence + catalog proof |
| `app/personnel_applications/infrastructure/lifecycle_repository.py::SqlAlchemyPersonnelApplicationLifecycleRepository.append_audit`; incoming `record_completed_from_apply` → `append_lifecycle_audit` | INSERT `personnel_application_lifecycle_audit(application_id,action,previous_status,new_status,comment,actor_user_id,metadata,created_at)` | same caller transaction | application row before audit ID | migrate in same transaction; one completion audit on fresh path, none on completed replay; caller rollback | INSERT/call-chain fingerprint + cardinality runtime assertion + FK/catalog proof |
| `app/services/ppr_candidate_service.py::save_intended_employment`; incoming `app/api/ppr_router.py` save route and `update_hr_relationship_context_tx/sync_hr_context_after_hire` callers | UPDATE `personnel_record_metadata.intended_org_group_id,intended_org_unit_id,intended_position_id,intended_employment_rate,updated_at` by `person_id` | caller `Connection`; envelope read, no common lock | identity/Person → class 11 metadata row `FOR UPDATE`; referenced org/position class 3 first | migrate all callers; expected metadata tuple/digest; caller rollback and identical replay | exact UPDATE/caller fingerprints + API/sync runtime branches + metadata/org/position catalog proof |
| `app/ppr/read/additional_reader.py::save_person_additional_profile`; incoming `personnel_intake.application.transfer_service.transfer_intake_to_ppr` | INSERT/ON-CONFLICT UPDATE `personnel_record_metadata.additional_profile,updated_at` | transfer caller transaction | identity/Person → class 11 metadata row | migrate despite module name `read`; locked expected tuple; whole transfer rollback/replay | UPSERT and transfer-edge fingerprints + insert/update runtime + PK/catalog proof |
| `app/personnel_applications/application/lifecycle_service.py::cancel_application`; incoming `personnel_applications_routes` cancel route | UPDATE application terminal status/closed fields; close intake link; INSERT lifecycle audit | route `engine.begin` | class 11 application → intake child → lifecycle audit | migrate as one conditional transition; identical terminal reread, conflicting terminal rejection | all terminal statements/callers + cancel/race/rollback runtime + status/FK catalog proof |
| `app/personnel_applications/application/lifecycle_service.py::expire_due_applications`; incoming list/maintenance path in `personnel_applications_routes` | ordered UPDATE applications and intake links plus lifecycle audit for each expired application | caller route transaction; current ordered SELECT lacks common locks | sorted application IDs class 11, then each intake link/audit; no order-scope lock | migrate whole batch or disable expiry side effect; no partial commit; repeat skips terminal rows | SELECT/UPDATE/audit fingerprints + zero/one/many/retry runtime + catalog proof |
| `app/personnel_applications/application/lifecycle_service.py::record_terminal_from_resolution`; incoming `resolution_service::{approve_resolution,reject_resolution}` | UPDATE `personnel_applications.closed_at,closed_by_user_id`; INSERT lifecycle audit | resolution caller transaction | class 11 application before lifecycle audit | migrate all resolution branches; COALESCE replay preserves first terminal values; caller rollback | UPDATE/audit and two incoming-edge fingerprints + terminal replay/runtime + catalog proof |
| `app/personnel_intake/application/intake_service.py::_transition_application_status`; incoming `issue_intake_link,open_intake_session,reopen_intake_for_applicant_rework,submit_intake_draft,submit_intake_draft_for_application` from public/directory/on-behalf routes | UPDATE `personnel_applications.status,updated_at` | route-owned transaction | class 11 application before intake link/draft children | migrate every named caller to conditional expected-status transition or disable route | direct UPDATE plus all incoming route/service fingerprints + transition/runtime + status catalog proof |
| `app/personnel_intake/application/review_service.py::_transition_application_status`; incoming `accept_intake_section,rework_intake_section,skip_intake_section` from directory intake routes | UPDATE `personnel_applications.status,updated_at` after review-section writes | route-owned transaction | class 11 application before sorted review children/audit | migrate three branches together; caller rollback; repeat uses exact section/application state | UPDATE and three route/service graphs + accept/rework/skip runtime + catalog proof |
| `app/personnel_intake/application/transfer_service.py::_transition_application_status`; incoming `transfer_intake_to_ppr` from directory intake route | UPDATE `personnel_applications.status,updated_at` | transfer caller transaction | class 11 application before section commands | migrate with entire transfer; no partial section/application commit | UPDATE/route/transfer fingerprints + failure ordinal/replay runtime + catalog proof |
| `app/personnel_intake/application/transfer_service.py::_transfer_general_and_contacts`; incoming `transfer_intake_to_ppr` | UPDATE `persons.full_name,birth_date`; UPDATE application phone/email; downstream section/contact commands | same transfer transaction | identity → Person → class 11 application → Contact/section writers in their declared order | disable until ADR-048-approved Person-field command replaces direct Person UPDATE; application/contact pieces migrate atomically | each UPDATE/call edge + route-disabled assertion + runtime no-partial-write + Person/application catalog proof |
| `app/employee_onboarding/infrastructure/repository.py::SqlAlchemyEmployeeOnboardingRepository.create_onboarding`; incoming `complete_application_after_hire` → `create_onboarding_from_hire` | INSERT `employee_onboardings(employee_id,application_id,status,started_at,planned_end_at,responsible_hr_id,mentor_employee_id,notes)` | same caller transaction | retained 3a/3b → Employee/application → onboarding | migrate; unique lookup makes replay read-only; caller-wide rollback/retry | INSERT/call-chain fingerprint + fresh/replay/rollback + unique/FK catalog proof |
| `app/employee_onboarding/infrastructure/repository.py::SqlAlchemyEmployeeOnboardingRepository.seed_standard_checklist`; incoming `create_onboarding_from_hire` | ordered INSERTs `employee_onboarding_checklist_items(onboarding_id,item_code,title,sort_order,is_custom,status,due_date,assignee_kind,priority)` | same caller transaction | onboarding then checklist rows in deterministic `STANDARD_CHECKLIST_CODES` order | migrate; only new onboarding seeds; any ordinal failure rolls back all | per-ordinal INSERT fingerprint + item-count/order runtime evidence + catalog proof |
| `app/employee_onboarding/infrastructure/notification_repository.py::create_onboarding_notification_tx`; incoming `create_onboarding_from_hire` → `notification_service.notify_task_assigned` | INSERT notification, recipient, delivery and target-contract delivery-attempt-1 rows | same caller transaction; no external send | onboarding/checklist then notification ID, sorted recipients/channels, class-15 delivery/attempt | disable application apply until migrated; dedup makes retry no-op and every INSERT ordinal rolls back with caller | four terminal SQL fingerprints + recipient/channel/attempt runtime evidence + unique/FK/catalog proof |
| `app/employee_onboarding/infrastructure/notification_repository.py::ack_onboarding_delivery`; incoming `app/directory/employee_onboarding_internal_routes.py::post_delivery_ack` after `get_pending_deliveries` | current unconditional UPDATE of delivery status/error/sent time; target contract in §9.3.1 also updates one attempt row | internal route-owned `engine.begin` after domain commit | class 15 delivery then attempt key; no order scope or application completion | **disable until replaced** by §9.3.1 conditional state machine; current DML is not idempotent | exact route/DML fingerprint + state-machine concurrency evidence + delivery/attempt CHECK catalog proof |
| `app/person_photos/infrastructure/blocker_repository.py::PersonPhotoBlockerRepository.upsert_open_blocker`; incoming `ensure_hire_photo_ready` → `_upsert_open_blocker_durable` | INSERT/ON-CONFLICT UPDATE `personnel_application_blockers(application_id,blocker_code,detail_json)` | helper-owned durable `engine.begin`, before main transaction | application reference → blocker; no order-scope lock and no claim of apply success | retain idempotent precondition; main apply disabled if fingerprint absent; durable blocker survives main failure by design | INSERT/UPSERT fingerprint + missing/error/retry branches + partial-unique/catalog proof |
| `app/person_photos/infrastructure/blocker_repository.py::PersonPhotoBlockerRepository.resolve_photo_blockers`; incoming `ensure_hire_photo_ready` → `_resolve_photo_blockers_durable` | UPDATE open photo blockers `resolved_at,resolved_by_user_id` by application/code | helper-owned durable `engine.begin`, before main transaction | application reference → blocker | retain idempotent resolution; main transaction still reacquires 3a/3b and authoritative state | UPDATE fingerprint + zero/one/many blocker runtime branches + catalog proof |
| `app/person_photos/infrastructure/repository.py::PersonPhotoRepository.insert_photo`; incoming `ensure_hire_photo_ready` → `canonicalize_person_photo` → `_commit_new_canonical_photo` | INSERT `person_photos(person_id,file_id,storage_rel_path,mime_type,byte_size,checksum_sha256,is_active,superseded_at,uploaded_by_user_id)` | canonicalization-owned durable `engine.begin` | identity → locked Person → existing photo → new photo | retain idempotent photo precondition; prepared file cleanup on DB rollback; main apply may subsequently fail without asserting success | INSERT/call-chain/storage fingerprint + collision/retry/rollback runtime evidence + catalog proof |
| `app/person_photos/infrastructure/repository.py::PersonPhotoRepository.supersede_photo`; same incoming `_commit_new_canonical_photo` | UPDATE `person_photos.is_active,superseded_at` by `person_photo_id` | same canonicalization transaction | locked Person → old photo ID → new photo | retain; old/new photo and PPR writes rollback together | UPDATE fingerprint + active-photo replacement runtime branch + immutable-trigger/catalog proof |
| `app/person_photos/infrastructure/repository.py::PersonPhotoRepository.insert_source`; incoming `_commit_new_canonical_photo` or `_link_provenance_only` | INSERT `person_photo_sources(person_photo_id,person_id,source_kind,canonicalization_mode,source_application_id,source_intake_photo_file_id,command_id,correlation_id,application_status_snapshot,canonicalized_by_user_id)` | same canonicalization transaction | locked Person/photo → source | retain; `command_id` provides replay identity; DB rollback removes source | INSERT fingerprint + new/link/replay branches + unique/FK/catalog proof |
| `app/ppr/infrastructure/ppr_event_repository.py::SqlAlchemyPprEventRepository.append`; incoming photo `_commit_new_canonical_photo`/`_link_provenance_only` via event builder | INSERT `personnel_record_events(person_id,employee_context_id,domain_code,record_table_name,record_id,event_type,event_at?,actor_id,event_payload,migration_run_id,migration_item_id)` | same canonicalization transaction; repository never commits | locked Person/photo/source → PPR event | migrate common PPR lock assertion; event rolls back with photo/source; source/correlation replay prevents duplicate event | both INSERT fingerprints + two event-builder edges + replay/cardinality runtime evidence + event/FK/catalog proof |
| `app/services/assignment_reconciliation_service.py` | Employee projection | owns transaction in public wrapper | shared 1a→Person→scope→Employee→assignment | orchestrator uses tx port; migrate/disable public overlap | call graph + Manifest+CI |
| `app/api/admin_router.py` enrollment/reconciliation entrypoints | indirect Employee/assignment projection writes | route-level only | inherits enrollment/reconciliation order | disable until respective callee migrated | call-graph manifest + route enablement assertion |
| `app/services/directory_service.py::{create_employee,terminate_employee,update_employee,transfer_employee,correct_employee,_insert_employee_event}`, `directory_import_csv.py`, `directory_import_xlsx.py`, `app/directory/employees_routes.py` | Employee fields and `employee_events` INSERT, plus import-created Employees | no universal order | identity→Person→scope→Employee→Employee event; shared 1a for assignment-derived fields | make assignment fields projection-only; migrate event path; disable bypass create/update | per-callable SQL/call-graph fingerprints + route enablement assertion + runtime branch evidence |
| `app/services/directory_import_csv.py::import_employees_csv_bytes`; incoming directory CSV route | per row SELECT then INSERT or UPDATE `employees` identity/name/department/position/status fields | function-owned engine transaction(s) | identity/Person → scope → Employee IDs ascending; current order incompatible | disable production CSV import until migrated to deterministic batch locks and assignment-derived projection rules | callable/INSERT/UPDATE/route fingerprints + mixed-row rollback/runtime + Employee catalog proof |
| `app/services/directory_import_xlsx.py::import_employees_xlsx_bytes`; incoming directory XLSX route | per row SELECT then INSERT or UPDATE `employees` fields | function-owned engine transaction(s) | same target order as CSV; current order incompatible | disable production XLSX import until migrated with CSV as one rollout unit | callable/INSERT/UPDATE/route fingerprints + mixed-row rollback/runtime + Employee catalog proof |
| `app/services/personnel_order_lifecycle_audit_service.py::append_personnel_order_lifecycle_audit`; incoming order create/edit/register/apply/void/cancel/archive flows | INSERT `personnel_order_lifecycle_audit` exact before/after status/void-kind and actor/details | caller `Connection` | class 3a order scope → header/item DML → lifecycle audit class 3b | migrate every caller to retained scope lock; append in caller transaction only | callable/INSERT/all incoming edges + rollback/runtime + audit FK/catalog proof |
| `app/services/identity_reconciliation_service.py` | Person/merge, Employees, assignments/links | ADR-044-local | identity→all Persons→scopes→Employees→assignments/links | migrate ordering; ADR-044 retains authority | Manifest+CI |
| `app/personnel_applications/application/registration_service.py`, `app/personnel_intake/application/transfer_service.py` | Person | local transaction | identity→Person | migrate only ADR-048-approved calls; otherwise disable | authority call graph + Manifest+CI |
| `app/directory/contacts_routes.py`, `app/services/operational_contact_service.py` | Contact/linkage | Contact-local/caller conn | identity→Person→Employee→10 when linked; 10 otherwise | migrate or disable overlap | Manifest+CI |
| `app/services/personnel_record_event_service.py` | personnel records/events | caller transaction | owning Person/entity then event before import/Contact | migrate helper assertion | Manifest+CI |
| `app/ppr/infrastructure/ppr_event_repository.py` | `personnel_record_events` | caller unit-of-work; no global assertion | owning Person/entity then event | migrate helper assertion | Manifest+CI; both INSERT branches fingerprinted |
| `app/ppr/infrastructure/application_unit_of_work.py`, `app/person_photos/application/canonicalization_service.py` | indirect callers of `SqlAlchemyPprEventRepository.append`; legacy personnel/photo event rows | caller unit-of-work | owning Person/entity then event | migrate common repository lock assertion; no new orchestration event vocabulary | caller-to-repository graph fingerprint + runtime transaction-owner evidence |
| `app/services/personnel_migration_commit_service.py`, `personnel_migration_ppr_bridge.py` | personnel records/events | PMF-local | owning Person/entity then event | migrate or disable overlapping commits | Manifest+CI |
| `app/services/security_audit_service.py` | `security_audit_log` | caller conn or own transaction | after business events, before import/Contact | strict caller-conn path only; disable own-tx use in orchestration | call graph + Manifest+CI |
| `app/directory/users_routes.py`, `app/security/admin_guard.py`, `app/security/auth_policy.py`, `app/services/access_grant_service.py`, `admin_users_service.py`, `assignment_reconciliation_service.py`, `employee_hard_delete_service.py`, `enrollment_service.py`, `hr_import_complete_review_service.py`, `hr_import_enroll_employee_service.py`, `identity_reconciliation_service.py`, `org_unit_allowed_positions_service.py`, `org_units_admin_service.py`, `personnel_orders_command_service.py`, `app/services/personnel_orders_editorial/audit.py`, `personnel_visibility_service.py`, `user_linkage_execute_service.py`, `user_linkage_operations_service.py`, `app/tg_bind.py`, `scripts/ops/ops_009_18c_admin_unlock.py` | exact indirect callers of `write_security_event`; audit plus each caller's already listed or unrelated business state | caller-specific; audit helper may own transaction | caller's entity order, then audit, then import/Contact | orchestration-reachable callers must use strict caller connection; non-orchestration callers retain their own reviewed transaction; script excluded or separately gated | complete caller-graph fingerprint + transaction-owner token + script/package disposition |
| `scripts/dev/seed_ppr_applicants.py`, `scripts/local_demo/wp_po_007_pilot_seed.py`, `scripts/ops/create_demo_ppr_applicants.py`, `scripts/pilot/qm_roles_users_bootstrap.sql`, `scripts/smoke_phase2b_user_create.py` | Person and/or Employee fixture data | script-local | identity→Person→scope→Employee | exclude from production execution/package | exact signed deny-list entries |
| `scripts/dev/seed_ppr_applicants.py::_ensure_candidate_envelope`; incoming `_materialize_candidate,seed,main` | INSERT/ON-CONFLICT UPDATE `personnel_record_metadata(person_id,ppr_lifecycle_state,hr_relationship_context,version,updated_at)` | script `engine.begin` | identity → Person → class 11 metadata | exclude entire script from production; development retry is deterministic UPSERT | callable/UPSERT/caller fingerprints + signed package/command deny-list + metadata catalog proof |
| `scripts/dev/seed_ppr_applicants.py::_upsert_person`; incoming `seed,main` | SELECT then UPDATE `persons.full_name,birth_date,person_status,updated_at` or INSERT `persons(full_name,iin,birth_date,match_key,person_status,source)` | per-applicant script `engine.begin` | identity advisory → Person; no assignment/order scope | exclude entire script from production; it is not an ADR-048 port and cannot be migrated as orchestration authority | both DML/caller fingerprints + signed production-package/command deny-list + Person catalog proof |
| `scripts/dev/seed_ppr_applicants.py::_insert_education`; incoming `seed,main` | DELETE matching `person_education`, then INSERT verified active education row | per-applicant script transaction | Person → sorted education identity; two statement ordinals | exclude entire script from production; dev retry is delete-and-replace only inside one transaction | DELETE/INSERT/caller fingerprints + package deny-list + education FK/index catalog proof |
| `scripts/dev/seed_ppr_applicants.py::_replace_training`; incoming `seed,main` | DELETE every Person training row then ordered INSERT `person_training` records | per-applicant script transaction | Person → all training rows by ID before delete; input records in deterministic list order | exclude entire script from production; no production automatic retry | DELETE/each INSERT/caller fingerprints + package deny-list + training catalog proof |
| `scripts/dev/seed_ppr_applicants.py::_seed_relatives`; incoming `seed,main` | indirect PPR `add_relative` command writes command execution/event and `person_relatives` | PPR command owns each command transaction, not outer seed transaction | identity → Person → command ID → relative row | exclude entire script from production; command ID is the only dev replay identity | callable/command/terminal graph + package deny-list + command/event/relative catalog proof |
| `scripts/ops/create_demo_ppr_applicants.py::_ensure_candidate_envelope`; incoming `execute_manifest,run,main` through PPR lifecycle command | indirect INSERT/UPDATE `personnel_record_metadata` and command execution/event rows | script caller transaction plus lifecycle service transaction boundary | identity → Person → class 11 metadata → command/event | exclude execute mode from production; dry-run remains read-only; every indirect terminal callable separately inventoried by graph | exact callable/command graph + execute deny-list/runtime dry-run assertion + command/metadata catalog proof |
| `scripts/ops/create_demo_ppr_applicants.py::_insert_demo_person`; incoming `_ensure_demo_person,execute_manifest,run,main` | INSERT demo `persons(full_name,iin,birth_date,match_key,person_status,source)` | script caller transaction | identity advisory → Person | disable execute mode in production; direct Person INSERT is never an ADR-048 orchestration port | callable/INSERT/full call graph + execute deny-list + Person catalog proof |
| `scripts/ops/create_demo_ppr_applicants.py::_ensure_education`; incoming `execute_manifest,run,main` | indirect PPR `add_education` command writes command/event and `person_education` | PPR command transaction | identity → Person → command ID → education row | disable execute mode in production; dry-run read-only; command replay only by command ID | callable/command/terminal graph + execute deny-list + command/event/education catalog proof |
| `scripts/ops/create_demo_ppr_applicants.py::_ensure_training`; incoming `execute_manifest,run,main` | indirect PPR `add_training` command writes command/event and `person_training` | PPR command transaction | identity → Person → command ID → training row | disable execute mode in production; dry-run read-only; command replay only by command ID | callable/command/terminal graph + execute deny-list + command/event/training catalog proof |
| `scripts/ops/create_demo_ppr_applicants.py::_purge_demo_marked_section_rows`; incoming `_delete_person_demo_data,rollback_demo_applicants,run,main` | dynamic-table DELETE from closed tuple `person_relatives,person_military_service,person_external_employment,person_training,person_education` | rollback script transaction | Person → tables in displayed order → rows by table PK | disable rollback execute in production; parser must expand all five literal dynamic targets | callable/dynamic-SQL expansion + execute deny-list + five table/FK catalog proofs |
| `scripts/ops/create_demo_ppr_applicants.py::_void_demo_applicant_sections`; incoming `rollback_demo_applicants,run,main` | indirect PPR `void_education` and `void_training` commands update lifecycle and append command/events | one PPR command transaction per sorted record; outer connection is discovery only | identity → Person → education IDs ascending, then training IDs ascending → command/event | disable rollback execute in production; no claim of one atomic outer transaction; command ID/expected timestamp governs replay | callable/two command graphs + execute deny-list + lifecycle/command/event catalog proof |
| `scripts/ops/create_demo_ppr_applicants.py::_delete_person_demo_data`; incoming `rollback_demo_applicants,run,main` | ordered DELETE demo section rows, `personnel_record_events`, `ppr_command_executions`, `personnel_record_metadata`, then `persons` | script transaction | identity → Person lock → sorted section/event/command/metadata rows; Person last | disable rollback execute in production; no partial retry; dry-run inventory only | every DELETE/caller fingerprint + production command deny-list + cascade/catalog graph |
| historical data-mutating revisions `a1b2c3d4e5f7_hr_import_control_list_storage.py`, `b3c4d5e6f7a8_hr_baseline_publication_origin.py`, `c7f3d92a1e04_hr_events_phase_1a.py`, `d3e4f5a6b7c8_hr_import_phase_2b_match_not_processed.py`, `e2c4f8a1b3d5_hr_import_phase_2c_document_candidates.py`, `o7p8q9r0s1t2_adr039_phase_3f_qualification_category_document_type.py`, `t2u3v4w5x6y7_adr039_promotion_specialty_policy.py`, `v4w5x6y7z8a9_adr042_phase_b2_3_backfill.py` upgrade/downgrade DML blocks | batches, rows, normalized records, document candidates, diff removals, Employee events, Persons, Employees, assignments and links | Alembic transaction | migration-only; never enters runtime lock order | classify exact revision as applied or block pending execution for separate migration review | Alembic current/head proof + signed revision/SQL fingerprint + catalog postcondition |
| historical schema migrations `u3v4w5x6y7z8_adr042_phase_b2_1_schema.py`, `x6y7z8a9b0c1_adr043_phase_b2_personnel_lifecycle_schema.py`, `q1r2s3t4u5w6_pmf_1_personnel_migration_schema.py` | assignment/event DDL | migration transaction | migration-only | applied/disabled; new ADR migration separately reviewed | Alembic head+DDL fingerprint |
| `alembic/versions/c0d1e2f3a4b5_adr061_001b_person_photo_schema_foundation.py::{upgrade,downgrade}` | CREATE/DROP `person_photos`, `person_photo_sources`, `personnel_application_blockers` and immutable triggers/indexes | Alembic transaction | migration-only; no runtime scope lock | exact revision applied, or pending revision blocks rollout for separate migration review | Alembic current/head + revision/SQL hash + table/trigger/index catalog fingerprint |
| `alembic/versions/q7r8s9t0u1v2_wp_ppr_applicant_001b_personnel_applications.py::{upgrade,downgrade}` | CREATE/DROP `personnel_applications` and FK/index/check state | Alembic transaction | migration-only | applied or separately reviewed before rollout | revision/SQL hash + application table/FK/catalog proof |
| `alembic/versions/j0k1l2m3n4o5_ppr_r1_personnel_record_metadata.py::{upgrade,downgrade}` | CREATE/DROP `personnel_record_metadata` | Alembic transaction | migration-only | applied or separately reviewed | revision/SQL hash + metadata PK/FK/catalog proof |
| `alembic/versions/m3n4o5p6q7r8_ppr_candidate_intended_employment.py::{upgrade,downgrade}` | ALTER intended-employment columns on `personnel_record_metadata` | Alembic transaction | migration-only | applied or separately reviewed | revision/SQL hash + exact column catalog proof |
| `alembic/versions/n5o6p7q8r9s0_ppr_additional_profile.py::{upgrade,downgrade}` | ALTER additional `personnel_record_metadata` profile columns | Alembic transaction | migration-only | applied or separately reviewed | revision/SQL hash + exact column catalog proof |
| `alembic/versions/r8s9t0u1v2w3_wp_ppr_intake_001_links_and_drafts.py::{upgrade,downgrade}` | CREATE/DROP `personnel_intake_links`, `personnel_intake_drafts` application evidence children | Alembic transaction | migration-only | applied or separately reviewed | revision/SQL hash + FK/catalog proof |
| `alembic/versions/s9t0u1v2w3x4_wp_ppr_intake_002_review_and_transfer.py::{upgrade,downgrade}` | CREATE/DROP intake review/transfer tables; ALTER application status CHECK | Alembic transaction | migration-only | applied or separately reviewed | revision/SQL hash + table/CHECK catalog proof |
| `alembic/versions/t0u1v2w3x4y5_wp_ppr_applicant_002_director_resolution.py::{upgrade,downgrade}` | CREATE/DROP resolution audit; ALTER and downgrade-UPDATE `personnel_applications` resolution/status fields | Alembic transaction | migration-only; data UPDATE never runtime | applied or pending blocks rollout for separate data-migration review | revision/SQL hash + data preflight + table/CHECK catalog proof |
| `alembic/versions/u1v2w3x4y5z6_wp_ppr_applicant_004_lifecycle_archive.py::{upgrade,downgrade}` | ALTER/UPDATE `personnel_applications`; CREATE/DROP `personnel_application_lifecycle_audit` | Alembic transaction | migration-only | applied or pending blocks rollout for separate data-migration review | revision/SQL hash + status-data preflight + audit/FK/catalog proof |
| `alembic/versions/m4n5o6p7q8r9_wp_ppr_intake_on_behalf_edit_audit.py::{upgrade,downgrade}` | ALTER and downgrade-DELETE `personnel_application_lifecycle_audit` actor/action data | Alembic transaction | migration-only | applied or pending blocks rollout for guarded destructive downgrade review | revision/SQL hash + downgrade row-count preflight + column/catalog proof |
| `alembic/versions/q8r9s0t1u2v3_wp_ppr_card_coordination_003_reconciliation_decisions.py::{upgrade,downgrade}` | CREATE/DROP application-linked reconciliation decision rows | Alembic transaction | migration-only | applied or separately reviewed | revision/SQL hash + application FK/catalog proof |
| `alembic/versions/v1w2x3y4z5a6_wp_onboarding_001_foundation.py::{upgrade,downgrade}` | CREATE/DROP `employee_onboardings`, `employee_onboarding_checklist_items` | Alembic transaction | migration-only | applied or separately reviewed | revision/SQL hash + table/unique/FK/catalog proof |
| `alembic/versions/w2x3y4z5a6b7_wp_onboarding_002_tasks_notifications.py::{upgrade,downgrade}` | ALTER checklist; CREATE/DROP onboarding attachments, task audit, notifications, recipients and deliveries | Alembic transaction | migration-only | applied or separately reviewed | revision/SQL hash + all table/index/FK/catalog fingerprints |
| `app/employee_onboarding/infrastructure/repository.py::SqlAlchemyEmployeeOnboardingRepository.add_custom_checklist_item`; incoming `employee_onboarding_routes.post_custom_checklist_item` → `checklist_service.add_custom_checklist_item` | INSERT checklist item: onboarding, null item code, title, sort order, custom flag, pending status plus §9.3.2 identity triple | route `engine.begin` | class 12 onboarding `FOR UPDATE` → class 13 sorted item INSERT; no order scope | migrate to §9.3.2 unique scope/key/digest; caller rollback; exact replay/conflict | route/service/repository SQL fingerprints + first/retry runtime + identity index/item catalog proof |
| `app/employee_onboarding/infrastructure/repository.py::SqlAlchemyEmployeeOnboardingRepository.update_checklist_item_status`; incoming `post_checklist_complete` → `complete_checklist_item`, `post_checklist_skip` → `skip_checklist_item`, and `post_bulk_complete_tasks` → `bulk_complete_tasks` → `complete_checklist_item` | UPDATE checklist status, completion actor/time and comment | one route `engine.begin`; bulk owns one transaction for the sorted set | class 12 → class 13 sorted items; no order scope | migrate all callers; conditional expected-status UPDATE; caller-wide rollback; identical terminal action is replay, incompatible terminal action conflicts | every direct/indirect fingerprint + complete/skip/bulk/replay runtime + CHECK/catalog proof |
| `app/employee_onboarding/infrastructure/repository.py::SqlAlchemyEmployeeOnboardingRepository.update_onboarding_status`; incoming `post_onboarding_complete` → `complete_onboarding` and `post_onboarding_cancel` → `cancel_onboarding` | UPDATE onboarding status, completed time, notes, updated time | route `engine.begin` | class 12 onboarding only; no order scope | migrate to conditional lifecycle transition; identical terminal replay/no conflicting overwrite | both chains/SQL fingerprints + complete/cancel race runtime + status CHECK catalog proof |
| `app/employee_onboarding/infrastructure/repository.py::SqlAlchemyEmployeeOnboardingRepository.update_checklist_item_fields`; incoming `patch_checklist_task` → `update_checklist_task`, `post_bulk_assign_tasks` → `bulk_assign_tasks` → `update_checklist_task`, and `post_bulk_due_date` → `bulk_update_due_dates` → `update_checklist_task` | dynamic UPDATE due date, assignee kind/user/employee, priority, comment, updated time | route/bulk `engine.begin` | referenced user/Employee before class 12; then class 13 sorted items; no order scope | migrate every dynamic SET branch; expected-state conditional write; whole route rollback/retry | AST dynamic-column manifest + route/bulk branch runtime + FK/CHECK/catalog proof |
| `app/employee_onboarding/infrastructure/repository.py::SqlAlchemyEmployeeOnboardingRepository.add_checklist_attachment`; incoming `employee_onboarding_routes.post_checklist_attachment` → `task_service.add_checklist_attachment` | INSERT checklist attachment item ID, file URL/comment, creator plus §9.3.2 identity triple | route `engine.begin` | class 12 → class 13 item then attachment; no order scope | migrate to §9.3.2 unique scope/key/digest; attachment and audit commit/rollback together | route/service/repository fingerprints + identical/conflicting/unknown-commit runtime + identity/FK catalog proof |
| `app/employee_onboarding/infrastructure/repository.py::SqlAlchemyEmployeeOnboardingRepository.write_task_audit`; incoming complete/skip and every changed branch of `update_checklist_task`, plus `add_checklist_attachment` | INSERT task audit item/onboarding/action/actor/payload plus §9.3.2 mutation identity triple | same caller transaction as owning item mutation | class 13 item mutation → class 14 audit INSERT | migrate every ordinal to derived sub-key/digest; audit failure rolls back owner; exact replay/conflict | repository INSERT plus caller/action/ordinal fingerprints + unknown-commit runtime + identity/FK catalog proof |
| `app/employee_onboarding/application/checklist_service.py::{complete_checklist_item,skip_checklist_item,complete_onboarding,cancel_onboarding,add_custom_checklist_item}`; exact incoming routes `post_checklist_complete,post_checklist_skip,post_onboarding_complete,post_onboarding_cancel,post_custom_checklist_item` | indirect closure to the exact status/onboarding/custom-item/audit/notification terminal rows above | each route owns `engine.begin` | classes 12→14; no order scope | migrate each callable and disable its exact route until every reachable terminal row passes | route/service/terminal graph fingerprints + success/error/replay/rollback runtime + full catalog closure |
| `app/employee_onboarding/application/task_service.py::{update_checklist_task,add_checklist_attachment}`; incoming `employee_onboarding_routes.patch_checklist_task,post_checklist_attachment` | indirect closure to checklist dynamic UPDATE, attachment INSERT, task-audit INSERT and assigned notification INSERTs | route `engine.begin` | references → classes 12→14; no order scope | migrate both; disable exact route on any missing terminal/disposition proof | graph/dynamic branch fingerprints + attachment/assignee rollback/retry runtime + catalog closure |
| `app/employee_onboarding/application/bulk_service.py::{bulk_assign_tasks,bulk_update_due_dates,bulk_complete_tasks}`; incoming `post_bulk_assign_tasks,post_bulk_due_date,post_bulk_complete_tasks` | loops exact task/checklist UPDATE, audit and notification terminal writers | one route-owned `engine.begin` per request | sort unique onboarding/item IDs before class 12/13; class 14 last; no order scope | migrate: a pre-DML item validation rejection is a listed partial result; any SQL/post-write failure escapes and rolls back the whole request; retry uses expected state and notification dedup | bulk call graph + every item/order/error branch runtime + terminal SQL/catalog proof |
| `app/employee_onboarding/application/notification_service.py::notify_task_assigned`; incoming onboarding bootstrap and `update_checklist_task` | indirect INSERT notification/recipient/delivery through `create_onboarding_notification_tx` | owning application/task transaction | classes 12/13 → class 14 sorted recipients/channels | migrate both incoming edges; dedup/retry identity is exact event/item key | both edge and terminal fingerprints + bootstrap/reassign replay runtime + unique catalog proof |
| `app/employee_onboarding/application/notification_service.py::notify_task_completed`; incoming `complete_checklist_item` and bulk completion | indirect INSERT notification/recipient/delivery | owning checklist/bulk transaction | classes 12/13 → class 14 | migrate; notification rollback with completion; exact dedup identity on retry | direct/bulk edges + SQL fingerprints + replay/rollback/catalog proof |
| `app/employee_onboarding/application/notification_service.py::{notify_task_due_soon,notify_task_overdue}`; incoming `employee_onboarding_internal_routes.post_run_reminders` → `reminder_service.run_onboarding_reminders` | indirect INSERT notification/recipient/delivery with due-date dedup key | internal route `engine.begin` | classes 12/13 reads/locks in sorted item order → class 14; no order scope | migrate scheduler route; one transaction; same due-date key replay is no-op | route/job/service/two terminal edge fingerprints + due/overdue/retry runtime + unique/catalog proof |
| `app/services/employee_hard_delete_service.py::_clear_cross_employee_references`; incoming `bulk_hard_delete_employees,hard_delete_employee` | dynamic conditional UPDATE onboarding mentor and checklist assignee Employee FKs to NULL | hard-delete caller transaction | referenced Employee then sorted classes 12/13; no order scope | disable hard-delete entrypoints in production until migrated with the common order; no partial enable | two dynamic UPDATE fingerprints + table/column branch runtime + FK/catalog proof + route-disable assertion |
| `app/services/employee_hard_delete_service.py::_delete_onboarding_for_employee`; incoming `bulk_hard_delete_employees,hard_delete_employee`; `_delete_applications_for_person` separately reaches onboarding DELETE by application | DELETE checklist items and onboardings; cascades/related notification, attachment and audit rows per deployed FKs | hard-delete caller transaction | Employee/application → sorted classes 12→15; no order scope | disable all reachable hard-delete paths until every explicit/cascade table is inventoried and ordered | direct/dynamic DELETE and caller fingerprints + cascade catalog graph + rollback/runtime + route-disable assertion |

The four personnel-order evidence tables and `personnel_order_evidence_scopes` are
controlled tables. Localized/editorial/print/lifecycle-audit rows remain inventoried as
writers but are outside §7 outcome state. Any indirect call that reaches a controlled
writer inherits its disposition; naming a route never substitutes for naming its callee.
The reviewed repository has no production application DML writer for
`personnel_order_attachments`; its current mutating paths are foundation migration
upgrade/downgrade and the dynamic position-contour cleanup. That absence is a signed
static assertion, not permission for an unlisted future attachment writer.

The callable-level baseline behind those rows is closed as follows; line/fingerprint drift
fails §9.4 even when the callable name remains. Indirect route/CLI entries are included
after the direct writers rather than treated as coverage of them:

```text
hr_import_service: create_batch, _persist_rows, _update_batch_counts
hr_import_monthly_diff_service: _clear_batch_diff_state, _persist_row_diff,
  _persist_normalized_diff, compute_batch_monthly_diff
hr_import_education_profile_service: _apply_to_aggregate_rows
hr_import_employee_binding_service: persist_row_binding_metadata,
  persist_row_employee_binding, _supersede_normalized_record,
  propagate_employee_id_to_normalized_records, repair_batch_employee_bindings
hr_import_enroll_employee_service: _insert_enrolled_event,
  _persist_row_enroll_metadata, enroll_employee_from_normalized_record
hr_import_review_exception_detail_service: _mark_staging_exception_resolved,
  clear_import_review_overrides_for_batch, _save_row_import_review_override
hr_import_roster_promotion_service: _insert_employee_identity,
  _update_employee_name_if_needed, _persist_row_roster_metadata, promote_roster_batch
hr_import_normalized_record_service: _supersede_open_normalized_record,
  _supersede_conflicting_open_records_for_insert, _execute_insert_staging_row,
  _delete_rebuildable_records, dedupe_open_normalized_records,
  update_normalized_record_review, update_normalized_record_review_override,
  populate_normalized_records
hr_import_promotion_service: _mark_record_promoted
hr_import_diff_removal_decision_service: restore_removal_decisions,
  record_diff_removal_decision, revert_diff_removal_decision
hr_import_document_candidate_service: _insert_candidate,
  parse_and_persist_document_candidates, rebuild_document_candidates
hr_import_complete_review_service: _transition_batch_to_apply_pending,
  maybe_reopen_import_review, complete_import_review
hr_baseline_service: mark_batches_stale_for_baseline, update_batch_diff_tracking,
  publish_baseline_from_batch
hr_import_control_list_storage: create_control_list_batch, cleanup_failed_control_list_batch,
  _insert_source_file
hr_import_ai_extraction_service: run_ai_extraction
hr_import_analytics_service: delete_batch
hr_effective_monthly_diff_service: materialize_personnel_change_events,
  run_effective_monthly_diff, run_effective_monthly_diff_tx
hr_person_assignment_sync_service: _mark_event_applied, _mark_event_failed,
  _create_person, _update_person_fields, _close_assignment, _create_assignment,
  _update_assignment_fields, _ensure_employee_assignment_link,
  _handle_terminated_person, _handle_field_changed
hr_personnel_lifecycle_service: _create_lifecycle_run, _finalize_lifecycle_run
directory_service: create_employee, terminate_employee, update_employee,
  _insert_employee_event, _apply_employee_org_change, _correct_employee_general,
  _correct_employee_assignment, transfer_employee, correct_employee
directory bulk import: directory_import_csv.import_employees_csv_bytes,
  directory_import_xlsx.import_employees_xlsx_bytes
enrollment_service: _create_employee_for_assignment, _ensure_assignment_link
assignment_reconciliation_service: reconcile_employee_primary_assignment
identity_reconciliation_service: _insert_employee_identity_iin, apply_candidate
personnel_order_hire_from_person_service: create_employee_for_hire,
  ensure_person_assignment_for_hire, link_order_item_employee
hire_order_draft_service: _create_draft_hire_order,
  create_hire_order_draft_for_application
personnel_orders_command_service: _mark_editorial_stale,
  create_personnel_order_draft, update_personnel_order_draft,
  create_personnel_order_item, update_personnel_order_item,
  upsert_personnel_order_localized_text,
  mark_personnel_order_ready_for_signature, register_personnel_order
personnel_orders_archive_service: archive_personnel_order, restore_personnel_order
personnel_orders_editorial.repository: ensure_default_basis, touch_order_updated_at
personnel_orders_editorial.generation_service: generate_editorial
personnel_orders_apply_service: _apply_hire, _apply_transfer, _apply_termination,
  _apply_rate_change
personnel_order_lifecycle_audit_service: append_personnel_order_lifecycle_audit
application_apply_service: orchestrate_hire_apply_for_application,
  apply_hire_for_application, try_complete_linked_application_after_order_apply,
  complete_application_after_hire, _complete_application
application-apply route: personnel_applications_routes.post_application_apply
application lifecycle closure: SqlAlchemyPersonnelApplicationRepository.update_application_fields,
  envelope_projection.sync_envelope_intended_projection,
  lifecycle_service.record_completed_from_apply,
  lifecycle_service.cancel_application, lifecycle_service.expire_due_applications,
  lifecycle_service.record_terminal_from_resolution,
  SqlAlchemyPersonnelApplicationLifecycleRepository.append_audit
PPR metadata closure: ppr_candidate_service.save_intended_employment,
  additional_reader.save_person_additional_profile
intake application closure: intake_service._transition_application_status,
  review_service._transition_application_status,
  transfer_service._transition_application_status,
  transfer_service._transfer_general_and_contacts
application photo precondition closure: hire_apply_hook.ensure_hire_photo_ready,
  hire_apply_hook._upsert_open_blocker_durable,
  hire_apply_hook._resolve_photo_blockers_durable,
  PersonPhotoBlockerRepository.upsert_open_blocker,
  PersonPhotoBlockerRepository.resolve_photo_blockers,
  canonicalization_service.canonicalize_person_photo,
  canonicalization_service._commit_new_canonical_photo,
  canonicalization_service._link_provenance_only,
  PersonPhotoRepository.insert_photo, PersonPhotoRepository.supersede_photo,
  PersonPhotoRepository.insert_source, SqlAlchemyPprEventRepository.append
onboarding closure: bootstrap_service.create_onboarding_from_hire,
  SqlAlchemyEmployeeOnboardingRepository.create_onboarding,
  SqlAlchemyEmployeeOnboardingRepository.seed_standard_checklist,
  notification_service.notify_task_assigned,
  notification_repository.create_onboarding_notification_tx,
  notification_repository.ack_onboarding_delivery
onboarding checklist/task closure: checklist_service.complete_checklist_item,
  skip_checklist_item, add_custom_checklist_item, complete_onboarding, cancel_onboarding;
  task_service.update_checklist_task, add_checklist_attachment;
  SqlAlchemyEmployeeOnboardingRepository.add_custom_checklist_item,
  update_checklist_item_status, update_onboarding_status, update_checklist_item_fields,
  add_checklist_attachment, write_task_audit
onboarding bulk/reminder/notification closure: bulk_service.bulk_assign_tasks,
  bulk_update_due_dates, bulk_complete_tasks; reminder_service.run_onboarding_reminders;
  notification_service.notify_task_completed, notify_task_due_soon, notify_task_overdue;
  employee_onboarding_routes.post_bulk_assign_tasks, post_bulk_due_date,
  post_bulk_complete_tasks, patch_checklist_task, post_checklist_attachment,
  post_checklist_complete, post_checklist_skip, post_custom_checklist_item,
  post_onboarding_complete, post_onboarding_cancel;
  employee_onboarding_internal_routes.post_run_reminders, post_delivery_ack
onboarding cleanup closure: employee_hard_delete_service._clear_cross_employee_references,
  _delete_onboarding_for_employee, _delete_applications_for_person,
  bulk_hard_delete_employees, hard_delete_employee
personnel_orders_void_service: _restore_employee_from_pre_apply_state,
  _rollback_hire_snapshot, _rollback_transfer_snapshot,
  _rollback_termination_snapshot, _rollback_snapshot_for_event, _void_employee_events,
  _mark_item_voided, _mark_order_voided, _void_item_with_events,
  _maybe_promote_order_void, void_personnel_order, void_personnel_order_item
personnel_orders_cancel_service: cancel_personnel_order
personnel_events_service: _handle_transfer, _handle_position_change, _handle_rate_change
personnel_record_event_service: emit_personnel_record_event
ppr_event_repository: append
ppr indirect callers: PprApplicationUnitOfWork._bind_repositories/events,
  canonicalization_service.canonicalize_person_photo,
  canonicalization_service._commit_new_canonical_photo,
  canonicalization_service._link_provenance_only
security_audit_service: write_security_event
security-audit indirect callers: users_routes, admin_guard, auth_policy,
  access_grant_service, admin_users_service, assignment_reconciliation_service,
  employee_hard_delete_service, enrollment_service, hr_import_complete_review_service,
  hr_import_enroll_employee_service, identity_reconciliation_service,
  org_unit_allowed_positions_service, org_units_admin_service,
  personnel_orders_command_service, personnel_orders_editorial.audit,
  personnel_visibility_service, user_linkage_execute_service,
  user_linkage_operations_service, tg_bind, ops_009_18c_admin_unlock
operational_contact_service: ensure_operational_contact_for_employee
contacts_routes: create_contact, update_contact, delete_contact
employee_hard_delete_service: _delete_assignment_contour,
  _delete_full_person_contour, hard_delete_employee
registration_service: _insert_person
personnel_intake.transfer_service: _transfer_general_and_contacts
direct CLI: prepare_adr059_phase1_ui_batch._reset_batch_diff_for_ui_recalc,
  prepare_adr059_phase2_ui_batch.main, hr_import_fio_fix_rebuild_report._reclassify_batch,
  backfill_hr_import_normalized_records.main, repair_hr_import_employee_bindings.main,
  wp_po_007_pilot_seed._cleanup_order/_cleanup_pilot/main/create_order/add_item/register/apply,
  position_contours_domain.build_delete_steps_from_allowlist/run_position_contours_execute
exact PPR fixture CLI terminals: seed_ppr_applicants._upsert_person,
  seed_ppr_applicants._ensure_candidate_envelope, seed_ppr_applicants._insert_education,
  seed_ppr_applicants._replace_training, seed_ppr_applicants._seed_relatives,
  create_demo_ppr_applicants._insert_demo_person,
  create_demo_ppr_applicants._ensure_candidate_envelope,
  create_demo_ppr_applicants._ensure_education,
  create_demo_ppr_applicants._ensure_training,
  create_demo_ppr_applicants._purge_demo_marked_section_rows,
  create_demo_ppr_applicants._void_demo_applicant_sections,
  create_demo_ppr_applicants._delete_person_demo_data
```

`hr_import_routes`, `employees_routes`, `admin_router`, `personnel_orders_routes`,
`personnel_applications_routes` including `post_application_apply`, the two directory import modules,
the five exact seed/demo/smoke paths, and both new CLI paths are the indirect entrypoint
closure. Their proof must name every reachable callable above; a reachable callable with
no matrix disposition is an unknown writer and blocks rollout.

For the application-apply chain the manifest expands service imports and runtime callback
edges, not only syntactic calls in one module. Its terminal closure is the order/item reads,
Employee/user and `employee_events` writes, `personnel_applications`,
`personnel_application_lifecycle_audit`, `personnel_record_metadata`, onboarding/checklist/
notification tables, photo/source/PPR events, and application blockers. Missing any direct
function, reverse hook, bootstrap callback, or exact terminal callable named above is a
static failure. The phrases “reached repository”, “corresponding writer” and wildcards are
forbidden manifest identities;
missing its maintained branch is a runtime failure; an unlisted FK cascade, trigger or
writable routine is a catalog failure. Any one failure keeps every production orchestrator
and application-order apply entrypoint disabled.

`create_onboarding_notification_tx` writes only the three PostgreSQL outbox tables named
above. It does not call Telegram, HTTP, SMTP, a broker or another process. External
delivery consumes committed `PENDING` rows after the caller transaction; its ACK writer
`app/employee_onboarding/infrastructure/notification_repository.py::ack_onboarding_delivery`
is separately inventoried as an outbox-consumer UPDATE and is not part of domain atomicity.
Rollback of application apply therefore exposes neither an outbox row nor an external
send. Multi-order entrypoints sort distinct `order_id` numerically before acquiring every
class-3a scope row; the reverse hook reuses that retained sorted lock set and may not
reacquire a lower class.

Photo canonicalization is deliberately a different durable idempotent precondition, not
part of application/order success atomicity. A main-transaction failure may leave a valid
canonical Person photo/source/PPR provenance row, but leaves no completed application,
Employee/order success, onboarding or notification row. Replay validates the photo
`command_id`/source and reuses it; blocker UPSERT/resolution is independently repeatable.
A DB failure after file preparation removes the prepared file best-effort and leaves the
durable reconciliation scan responsible for any crash orphan. No photo branch may emit or
imply application apply success.

### 9.3.1. Delivery ACK target state machine

The deployed unconditional ACK UPDATE does **not** satisfy this ADR. The ACK route, old
pending reader and delivery worker remain disabled until a reviewed migration implements
this contract. Logical identity is `(notification_id,user_id,channel)`; immutable attempt
identity adds positive `attempt_no`. The closed failure-code enum is
`TRANSPORT_TIMEOUT | TRANSPORT_UNAVAILABLE | REMOTE_REJECTED | RATE_LIMITED |
PAYLOAD_REJECTED | AUTHENTICATION_FAILED | UNKNOWN_DELIVERY_FAILURE`; regex-only or
provider-supplied values are forbidden. The ACK body has exactly
`notification_id,user_id,channel,attempt_no,delivery_claim_owner_id,terminal_status,
error_code`. Status is `SENT|FAILED`. Its `ack_request_fingerprint` is lowercase
SHA-256 of RFC-8785 JCS of those seven members; numeric identities are positive decimal
strings, UUID is lowercase canonical text, and absent error is explicit JSON null.

```sql
ALTER TABLE public.employee_onboarding_notification_deliveries
  ADD COLUMN current_attempt_no BIGINT NOT NULL DEFAULT 1,
  ADD COLUMN ack_updated_at TIMESTAMPTZ NULL,
  ADD CONSTRAINT chk_eond_attempt_positive CHECK (current_attempt_no > 0),
  ADD CONSTRAINT chk_eond_state_shape CHECK ((
    (status='PENDING' AND error_code IS NULL AND sent_at IS NULL
      AND ((current_attempt_no=1 AND ack_updated_at IS NULL)
        OR (current_attempt_no>1 AND ack_updated_at IS NOT NULL))) OR
    (status='SENT' AND error_code IS NULL AND sent_at IS NOT NULL
      AND ack_updated_at IS NOT NULL) OR
    (status='FAILED' AND error_code IN (
      'TRANSPORT_TIMEOUT','TRANSPORT_UNAVAILABLE','REMOTE_REJECTED','RATE_LIMITED',
      'PAYLOAD_REJECTED','AUTHENTICATION_FAILED','UNKNOWN_DELIVERY_FAILURE')
      AND sent_at IS NULL AND ack_updated_at IS NOT NULL)
  ) IS TRUE);

CREATE TABLE public.employee_onboarding_notification_delivery_attempts (
  notification_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  channel TEXT NOT NULL,
  attempt_no BIGINT NOT NULL,
  attempt_status TEXT NOT NULL DEFAULT 'PENDING',
  retry_request_fingerprint CHAR(64) NULL,
  ack_request_fingerprint CHAR(64) NULL,
  error_code TEXT NULL,
  attempted_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
  claim_owner_id UUID NULL,
  claim_acquired_at TIMESTAMPTZ NULL,
  claim_expires_at TIMESTAMPTZ NULL,
  acked_at TIMESTAMPTZ NULL,
  PRIMARY KEY(notification_id,user_id,channel,attempt_no),
  FOREIGN KEY(notification_id,user_id,channel)
    REFERENCES public.employee_onboarding_notification_deliveries
      (notification_id,user_id,channel) ON DELETE CASCADE,
  CHECK (attempt_no > 0),
  CHECK (((attempt_no=1 AND retry_request_fingerprint IS NULL)
    OR (attempt_no>1 AND retry_request_fingerprint ~ '^[0-9a-f]{64}$')) IS TRUE),
  CHECK ((ack_request_fingerprint IS NULL OR
    ack_request_fingerprint ~ '^[0-9a-f]{64}$') IS TRUE),
  CHECK ((
    (attempt_status='PENDING' AND ack_request_fingerprint IS NULL
      AND error_code IS NULL AND acked_at IS NULL
      AND ((claim_owner_id IS NULL AND claim_acquired_at IS NULL AND claim_expires_at IS NULL)
        OR (claim_owner_id IS NOT NULL AND claim_acquired_at IS NOT NULL
          AND claim_expires_at>claim_acquired_at))) OR
    (attempt_status='SENT' AND ack_request_fingerprint IS NOT NULL
      AND error_code IS NULL AND acked_at IS NOT NULL
      AND claim_owner_id IS NULL AND claim_acquired_at IS NULL AND claim_expires_at IS NULL) OR
    (attempt_status='FAILED' AND ack_request_fingerprint IS NOT NULL
      AND error_code IN (
        'TRANSPORT_TIMEOUT','TRANSPORT_UNAVAILABLE','REMOTE_REJECTED','RATE_LIMITED',
        'PAYLOAD_REJECTED','AUTHENTICATION_FAILED','UNKNOWN_DELIVERY_FAILURE')
      AND acked_at IS NOT NULL
      AND claim_owner_id IS NULL AND claim_acquired_at IS NULL AND claim_expires_at IS NULL)
  ) IS TRUE)
);

CREATE UNIQUE INDEX uq_eonda_retry_request
  ON public.employee_onboarding_notification_delivery_attempts(
    notification_id,user_id,channel,retry_request_fingerprint)
  WHERE retry_request_fingerprint IS NOT NULL;

CREATE FUNCTION public.assert_onboarding_delivery_projection_consistent()
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER VOLATILE
SET search_path=pg_catalog,public AS $$
BEGIN
  IF EXISTS (
    SELECT 1
      FROM public.employee_onboarding_notification_deliveries d
      LEFT JOIN public.employee_onboarding_notification_delivery_attempts a
        ON (a.notification_id,a.user_id,a.channel,a.attempt_no)=
           (d.notification_id,d.user_id,d.channel,d.current_attempt_no)
     WHERE a.attempt_no IS NULL
        OR a.attempt_status IS DISTINCT FROM d.status
        OR a.error_code IS DISTINCT FROM d.error_code
        OR (d.status='SENT' AND d.sent_at IS DISTINCT FROM a.acked_at)
        OR (d.status<>'SENT' AND d.sent_at IS NOT NULL)
  ) THEN
    RAISE EXCEPTION 'ONBOARDING_DELIVERY_PROJECTION_INCONSISTENT'
      USING ERRCODE='23514';
  END IF;
  RETURN TRUE;
END $$;
REVOKE EXECUTE ON FUNCTION public.assert_onboarding_delivery_projection_consistent()
  FROM PUBLIC;

CREATE FUNCTION public.claim_onboarding_delivery_attempts(
  p_claim_owner_id UUID, p_limit INTEGER
) RETURNS TABLE(
  notification_id BIGINT,user_id BIGINT,channel TEXT,attempt_no BIGINT,
  event_type TEXT,payload JSONB,onboarding_id BIGINT,item_id BIGINT,
  claim_owner_id UUID,claim_expires_at TIMESTAMPTZ
) LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
WITH guard AS MATERIALIZED (
  SELECT public.assert_onboarding_delivery_projection_consistent() AS ok
), locked AS (
  SELECT d.notification_id,d.user_id,d.channel,d.current_attempt_no,
         n.event_type,n.payload,n.onboarding_id,n.item_id
  FROM public.employee_onboarding_notification_deliveries d
  JOIN public.employee_onboarding_notification_delivery_attempts a
    ON (a.notification_id,a.user_id,a.channel,a.attempt_no)=
       (d.notification_id,d.user_id,d.channel,d.current_attempt_no)
  JOIN public.employee_onboarding_notifications n
    ON n.notification_id=d.notification_id
  CROSS JOIN guard
  WHERE guard.ok AND d.status='PENDING' AND a.attempt_status='PENDING'
    AND (a.claim_owner_id IS NULL OR a.claim_expires_at<=statement_timestamp())
  ORDER BY d.created_at,d.notification_id,d.user_id,d.channel,d.current_attempt_no
  LIMIT GREATEST(1,LEAST(p_limit,500))
  FOR UPDATE OF d,a SKIP LOCKED
), claimed AS (
  UPDATE public.employee_onboarding_notification_delivery_attempts a
     SET claim_owner_id=p_claim_owner_id,
         claim_acquired_at=transaction_timestamp(),
         claim_expires_at=transaction_timestamp()+INTERVAL '60 seconds'
    FROM locked l
   WHERE (a.notification_id,a.user_id,a.channel,a.attempt_no)=
         (l.notification_id,l.user_id,l.channel,l.current_attempt_no)
  RETURNING a.notification_id,a.user_id,a.channel,a.attempt_no,
            a.claim_owner_id,a.claim_expires_at
)
SELECT c.notification_id,c.user_id,c.channel,c.attempt_no,
       l.event_type,l.payload,l.onboarding_id,l.item_id,
       c.claim_owner_id,c.claim_expires_at
FROM claimed c JOIN locked l USING(notification_id,user_id,channel)
ORDER BY c.notification_id,c.user_id,c.channel,c.attempt_no
$$;

CREATE FUNCTION public.ack_onboarding_delivery(
  p_notification_id BIGINT,p_user_id BIGINT,p_channel TEXT,p_attempt_no BIGINT,
  p_claim_owner_id UUID,p_terminal_status TEXT,p_error_code TEXT,
  p_ack_request_fingerprint CHAR(64)
) RETURNS TEXT LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE d public.employee_onboarding_notification_deliveries%ROWTYPE;
        a public.employee_onboarding_notification_delivery_attempts%ROWTYPE;
        affected INTEGER;
BEGIN
  IF p_terminal_status NOT IN ('SENT','FAILED') THEN
    RETURN 'ONBOARDING_DELIVERY_ACK_STATUS_INVALID';
  END IF;
  IF p_ack_request_fingerprint !~ '^[0-9a-f]{64}$' THEN
    RETURN 'ONBOARDING_DELIVERY_ACK_FINGERPRINT_INVALID';
  END IF;
  IF (p_terminal_status='SENT' AND p_error_code IS NOT NULL)
     OR (p_terminal_status='FAILED' AND
       p_error_code NOT IN ('TRANSPORT_TIMEOUT','TRANSPORT_UNAVAILABLE',
       'REMOTE_REJECTED','RATE_LIMITED','PAYLOAD_REJECTED',
       'AUTHENTICATION_FAILED','UNKNOWN_DELIVERY_FAILURE')) THEN
    RETURN 'ONBOARDING_DELIVERY_ACK_ERROR_INVALID';
  END IF;
  SELECT * INTO d FROM public.employee_onboarding_notification_deliveries
   WHERE (notification_id,user_id,channel)=
         (p_notification_id,p_user_id,p_channel) FOR UPDATE;
  IF NOT FOUND THEN RETURN 'ONBOARDING_DELIVERY_NOT_FOUND'; END IF;
  SELECT * INTO a FROM public.employee_onboarding_notification_delivery_attempts
   WHERE (notification_id,user_id,channel,attempt_no)=
         (p_notification_id,p_user_id,p_channel,p_attempt_no) FOR UPDATE;
  IF NOT FOUND THEN RETURN 'ONBOARDING_DELIVERY_NOT_FOUND'; END IF;
  IF p_attempt_no<>d.current_attempt_no THEN
    RETURN 'ONBOARDING_DELIVERY_ATTEMPT_STALE';
  END IF;
  IF a.attempt_status IN ('SENT','FAILED') THEN
    IF a.ack_request_fingerprint=p_ack_request_fingerprint THEN
      RETURN 'ONBOARDING_DELIVERY_ACK_REPLAYED';
    END IF;
    RETURN 'ONBOARDING_DELIVERY_ACK_CONFLICT';
  END IF;
  IF a.claim_owner_id IS DISTINCT FROM p_claim_owner_id
     OR a.claim_expires_at<=statement_timestamp() THEN
    RETURN 'ONBOARDING_DELIVERY_CLAIM_STALE';
  END IF;
  UPDATE public.employee_onboarding_notification_delivery_attempts
     SET attempt_status=p_terminal_status,
         ack_request_fingerprint=p_ack_request_fingerprint,
         error_code=CASE WHEN p_terminal_status='FAILED' THEN p_error_code ELSE NULL END,
         acked_at=transaction_timestamp(),
         claim_owner_id=NULL,claim_acquired_at=NULL,claim_expires_at=NULL
   WHERE (notification_id,user_id,channel,attempt_no)=
         (p_notification_id,p_user_id,p_channel,p_attempt_no)
     AND attempt_status='PENDING' AND claim_owner_id=p_claim_owner_id;
  GET DIAGNOSTICS affected=ROW_COUNT;
  IF affected<>1 THEN RAISE EXCEPTION 'ONBOARDING_DELIVERY_PROJECTION_CONFLICT'; END IF;
  UPDATE public.employee_onboarding_notification_deliveries
     SET status=p_terminal_status,
         error_code=CASE WHEN p_terminal_status='FAILED' THEN p_error_code ELSE NULL END,
         sent_at=CASE WHEN p_terminal_status='SENT'
           THEN transaction_timestamp() ELSE NULL END,
         ack_updated_at=transaction_timestamp()
   WHERE (notification_id,user_id,channel)=
         (p_notification_id,p_user_id,p_channel)
     AND current_attempt_no=p_attempt_no AND status='PENDING';
  GET DIAGNOSTICS affected=ROW_COUNT;
  IF affected<>1 THEN RAISE EXCEPTION 'ONBOARDING_DELIVERY_PROJECTION_CONFLICT'; END IF;
  RETURN 'ONBOARDING_DELIVERY_ACKED';
END $$;

CREATE FUNCTION public.begin_onboarding_delivery_retry(
  p_notification_id BIGINT,p_user_id BIGINT,p_channel TEXT,
  p_retry_request_fingerprint CHAR(64)
) RETURNS TEXT LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE d public.employee_onboarding_notification_deliveries%ROWTYPE;
        a public.employee_onboarding_notification_delivery_attempts%ROWTYPE;
        affected INTEGER;
        violated_constraint TEXT;
BEGIN
  IF p_retry_request_fingerprint !~ '^[0-9a-f]{64}$' THEN
    RETURN 'ONBOARDING_DELIVERY_RETRY_FINGERPRINT_INVALID';
  END IF;
  SELECT * INTO d FROM public.employee_onboarding_notification_deliveries
   WHERE (notification_id,user_id,channel)=
         (p_notification_id,p_user_id,p_channel) FOR UPDATE;
  IF NOT FOUND THEN RETURN 'ONBOARDING_DELIVERY_NOT_FOUND'; END IF;
  IF EXISTS (SELECT 1 FROM public.employee_onboarding_notification_delivery_attempts
    WHERE (notification_id,user_id,channel,retry_request_fingerprint)=
          (p_notification_id,p_user_id,p_channel,p_retry_request_fingerprint)) THEN
    RETURN 'ONBOARDING_DELIVERY_RETRY_REPLAYED';
  END IF;
  SELECT * INTO a FROM public.employee_onboarding_notification_delivery_attempts
   WHERE (notification_id,user_id,channel,attempt_no)=
         (p_notification_id,p_user_id,p_channel,d.current_attempt_no) FOR UPDATE;
  IF NOT FOUND OR a.attempt_status<>'FAILED' OR d.status<>'FAILED' THEN
    RETURN 'ONBOARDING_DELIVERY_RETRY_CONFLICT';
  END IF;
  IF d.current_attempt_no=9223372036854775807 THEN
    RETURN 'ONBOARDING_DELIVERY_ATTEMPT_EXHAUSTED';
  END IF;
  INSERT INTO public.employee_onboarding_notification_delivery_attempts(
    notification_id,user_id,channel,attempt_no,attempt_status,
    retry_request_fingerprint)
  VALUES (p_notification_id,p_user_id,p_channel,d.current_attempt_no+1,'PENDING',
          p_retry_request_fingerprint);
  UPDATE public.employee_onboarding_notification_deliveries
     SET current_attempt_no=d.current_attempt_no+1,status='PENDING',
         error_code=NULL,sent_at=NULL,ack_updated_at=transaction_timestamp()
   WHERE (notification_id,user_id,channel)=
         (p_notification_id,p_user_id,p_channel)
     AND current_attempt_no=d.current_attempt_no AND status='FAILED';
  GET DIAGNOSTICS affected=ROW_COUNT;
  IF affected<>1 THEN RAISE EXCEPTION 'ONBOARDING_DELIVERY_PROJECTION_CONFLICT'; END IF;
  RETURN 'ONBOARDING_DELIVERY_RETRY_STARTED';
EXCEPTION WHEN unique_violation THEN
  GET STACKED DIAGNOSTICS violated_constraint=CONSTRAINT_NAME;
  IF violated_constraint IN (
    'employee_onboarding_notification_delivery_attempts_pkey',
    'uq_eonda_retry_request') THEN
    RETURN 'ONBOARDING_DELIVERY_RETRY_CONFLICT';
  END IF;
  RAISE;
END $$;

CREATE ROLE adr065_delivery_runtime NOLOGIN;
REVOKE INSERT,UPDATE,DELETE ON
  public.employee_onboarding_notification_deliveries,
  public.employee_onboarding_notification_delivery_attempts
  FROM PUBLIC,adr065_delivery_runtime;
GRANT SELECT ON
  public.employee_onboarding_notification_deliveries,
  public.employee_onboarding_notification_delivery_attempts
  TO adr065_delivery_runtime;
GRANT EXECUTE ON FUNCTION public.claim_onboarding_delivery_attempts(UUID,INTEGER),
  public.ack_onboarding_delivery(BIGINT,BIGINT,TEXT,BIGINT,UUID,TEXT,TEXT,CHAR),
  public.begin_onboarding_delivery_retry(BIGINT,BIGINT,TEXT,CHAR)
  TO adr065_delivery_runtime;
```

Migration creates exactly one attempt matching every existing delivery. For a legacy
terminal row its fingerprint is SHA-256/JCS of the explicit
`legacy-onboarding-ack-v1` persisted tuple; no request replay is inferred from it.
Before adding the shape CHECK it deterministically sets `sent_at=created_at` only for the
known legacy system-delivery shape `channel='system',status='SENT',sent_at IS NULL,
error_code IS NULL`; that existing INSERT means immediate in-system delivery. It refuses
every other pre-existing SENT-without-time, FAILED-with-time, PENDING-with-error/time,
unknown status/error shape or duplicate key before DDL. New notification creation inserts
delivery and attempt 1 as PENDING in the same transaction; immediate system delivery uses
the same worker/ACK transition.

`claim_onboarding_delivery_attempts(p_claim_owner_id UUID,p_limit INTEGER)` is a
`SECURITY DEFINER` function. In one transaction it selects only parent/current-attempt
PENDING pairs whose claim is absent or expired, ordered by
`(delivery.created_at,notification_id,user_id,channel,attempt_no)`, using
`FOR UPDATE OF delivery,attempt SKIP LOCKED`; it sets one 60-second claim tuple and
returns exactly `notification_id,user_id,channel,attempt_no,event_type,payload,
onboarding_id,item_id,claim_owner_id,claim_expires_at`. The worker therefore always
receives the current attempt identity.

`ack_onboarding_delivery` is the only ACK mutation function. It validates the closed
body/fingerprint, locks the parent then attempt, and applies this total function:

- absent parent or attempt → `ONBOARDING_DELIVERY_NOT_FOUND`;
- requested attempt is not current → `ONBOARDING_DELIVERY_ATTEMPT_STALE`;
- PENDING but claim owner differs or claim expired →
  `ONBOARDING_DELIVERY_CLAIM_STALE`;
- terminal with identical fingerprint → `ONBOARDING_DELIVERY_ACK_REPLAYED`;
- terminal with different fingerprint, SENT→FAILED or FAILED overwrite →
  `ONBOARDING_DELIVERY_ACK_CONFLICT`;
- current claimed PENDING → conditional attempt UPDATE followed by conditional parent
  UPDATE; both must affect exactly one row, otherwise
  `ONBOARDING_DELIVERY_PROJECTION_CONFLICT` aborts the transaction.

The attempt transition clears its claim, sets `acked_at`, fingerprint and exact terminal
error. The parent receives the same status/error, `sent_at=transaction_timestamp()` only
for SENT and NULL for FAILED, and `ack_updated_at=transaction_timestamp()`. Successful
pair transition returns the one normative code `ONBOARDING_DELIVERY_ACKED`.

`begin_onboarding_delivery_retry(...,p_retry_request_fingerprint)` locks the parent and
current attempt and first looks up the fingerprint under `uq_eonda_retry_request`; exact
match returns `ONBOARDING_DELIVERY_RETRY_REPLAYED`. Otherwise current status must be
FAILED. At `current_attempt_no=9223372036854775807` it returns
`ONBOARDING_DELIVERY_ATTEMPT_EXHAUSTED` before arithmetic. It inserts exactly the next
PENDING attempt and atomically projects the parent to PENDING with NULL error/sent time
and non-NULL `ack_updated_at`. Both row counts must be one. Only `23505` naming
`employee_onboarding_notification_delivery_attempts_pkey` or
`uq_eonda_retry_request` maps to `ONBOARDING_DELIVERY_RETRY_CONFLICT`; every unrelated
integrity error is re-raised; success returns
`ONBOARDING_DELIVERY_RETRY_STARTED`. An ACK for any older attempt is always stale.

The three functions and notification creation are owned by the migration NOLOGIN role.
`adr065_delivery_runtime` receives SELECT and EXECUTE only, and no direct parent/attempt
INSERT/UPDATE/DELETE. Catalog ACL/function/trigger proof is a rollout gate; attempt and
parent cannot commit separately. Startup and each claim compare every parent with its
current attempt. Drift returns `ONBOARDING_DELIVERY_PROJECTION_INCONSISTENT` and blocks
delivery/ACK/retry. Repair is not implicit: a separately authorized transaction locks both
rows, projects only the immutable current attempt, records security audit
`ONBOARDING_DELIVERY_PROJECTION_REPAIRED`, and refuses ambiguous/missing attempts.

Unknown status returns `ONBOARDING_DELIVERY_ACK_STATUS_INVALID`; an unknown closed-enum
error or wrong SENT/FAILED null shape returns
`ONBOARDING_DELIVERY_ACK_ERROR_INVALID`; malformed request fingerprint returns
`ONBOARDING_DELIVERY_ACK_FINGERPRINT_INVALID`. No provider text is stored as a code.

Future work is explicit: add/backfill the attempt table and columns/CHECKs; replace the
unconditional UPDATE and old pending reader with these three functions; close worker/route
schemas and result vocabulary; revoke table DML; add runtime concurrency/catalog proofs;
only then re-enable pending-delivery, ACK and retry entrypoints. Current code is not
declared conforming merely by this revision.

### 9.3.2. Persisted retry identity for onboarding INSERT writers

Custom checklist-item, checklist-attachment and task-audit INSERTs use the same closed
three-column identity profile; prose-only title/file/action matching is forbidden:

```sql
ALTER TABLE public.employee_onboarding_checklist_items
  ADD COLUMN create_scope_fingerprint CHAR(64) NULL,
  ADD COLUMN create_idempotency_key_fingerprint CHAR(64) NULL,
  ADD COLUMN create_request_digest CHAR(64) NULL,
  ADD CONSTRAINT chk_eoci_create_identity CHECK (((is_custom IS FALSE AND
      create_scope_fingerprint IS NULL AND create_idempotency_key_fingerprint IS NULL
      AND create_request_digest IS NULL) OR (is_custom IS TRUE AND ((
      create_scope_fingerprint IS NULL AND create_idempotency_key_fingerprint IS NULL
      AND create_request_digest IS NULL) OR (
      create_scope_fingerprint ~ '^[0-9a-f]{64}$' AND
      create_idempotency_key_fingerprint ~ '^[0-9a-f]{64}$' AND
      create_request_digest ~ '^[0-9a-f]{64}$')))) IS TRUE);
CREATE UNIQUE INDEX uq_eoci_custom_create_request
  ON public.employee_onboarding_checklist_items(
    onboarding_id,create_scope_fingerprint,create_idempotency_key_fingerprint)
  WHERE is_custom IS TRUE;

ALTER TABLE public.employee_onboarding_checklist_attachments
  ADD COLUMN create_scope_fingerprint CHAR(64) NULL,
  ADD COLUMN create_idempotency_key_fingerprint CHAR(64) NULL,
  ADD COLUMN create_request_digest CHAR(64) NULL,
  ADD CONSTRAINT chk_eoca_create_identity CHECK (((create_scope_fingerprint IS NULL
    AND create_idempotency_key_fingerprint IS NULL AND create_request_digest IS NULL) OR (
    create_scope_fingerprint ~ '^[0-9a-f]{64}$' AND
    create_idempotency_key_fingerprint ~ '^[0-9a-f]{64}$' AND
    create_request_digest ~ '^[0-9a-f]{64}$')) IS TRUE);
CREATE UNIQUE INDEX uq_eoca_create_request
  ON public.employee_onboarding_checklist_attachments(
    item_id,create_scope_fingerprint,create_idempotency_key_fingerprint);

ALTER TABLE public.employee_onboarding_task_audit
  ADD COLUMN mutation_scope_fingerprint CHAR(64) NULL,
  ADD COLUMN mutation_idempotency_key_fingerprint CHAR(64) NULL,
  ADD COLUMN mutation_request_digest CHAR(64) NULL,
  ADD CONSTRAINT chk_eota_mutation_identity CHECK (((mutation_scope_fingerprint IS NULL
    AND mutation_idempotency_key_fingerprint IS NULL
    AND mutation_request_digest IS NULL) OR (
    mutation_scope_fingerprint ~ '^[0-9a-f]{64}$' AND
    mutation_idempotency_key_fingerprint ~ '^[0-9a-f]{64}$' AND
    mutation_request_digest ~ '^[0-9a-f]{64}$')) IS TRUE);
CREATE UNIQUE INDEX uq_eota_mutation_request
  ON public.employee_onboarding_task_audit(
    item_id,action,mutation_scope_fingerprint,mutation_idempotency_key_fingerprint);
```

Upgrade adds the columns nullable, records existing all-NULL triples as
`legacy-unreplayable` in the migration report and infers no identity. The CHECK retains
that explicit legacy branch; every post-gate INSERT is required by a BEFORE INSERT trigger
to supply all three fields. No automatic retry is permitted for a legacy-null row:
authoritative locked reread returns
`ONBOARDING_INSERT_RETRY_UNSUPPORTED_LEGACY`.

`scope_fingerprint` is SHA-256/JCS of authenticated actor ID, authorization-context
fingerprint and route purpose. The raw idempotency key is HMAC-fingerprinted under the
operation-key authority. `request_digest` is SHA-256/JCS of the exact mutation: custom
item uses `(onboarding_id,title,sort_order)`; attachment uses
`(item_id,file_url,file_comment,created_by)`; audit uses
`(item_id,onboarding_id,action,actor_user_id,payload,owning_mutation_ordinal)`.
Strings/NULL use §8 canonical rules and maps use RFC 8785. Each business transaction
derives a distinct audit sub-key from its operation key and fixed numeric ordinal.

Each repository INSERTs with `ON CONFLICT DO NOTHING`, then selects the unique scope/key
row. Equal digest returns `ONBOARDING_INSERT_REPLAYED`; unequal digest returns
`ONBOARDING_INSERT_IDEMPOTENCY_REUSED`; no row after unknown commit returns
`ONBOARDING_INSERT_COMMIT_UNKNOWN` and may only repeat the same lookup. Concurrent
identical writers produce one insert/one replay; conflicting writers produce one
insert/one conflict. Identity columns and rows are immutable and retained with the
business/audit row. Attachment, audit and owning checklist mutation share one caller
transaction, so any ordinal failure rolls all of them back.

### 9.4. Automated completeness proof

The table is the reviewed baseline. The **primary blocking completeness proof** is a
branch-independent static inventory of the entire shipped repository source tree:
`app/**`, every `scripts/**` Python/SQL file whether packaged or denied, and every
`alembic/versions/**` revision. Each build produces signed
`personnel-sql-writer-inventory.json`. AST/data-flow plus SQL parsing enumerates SQLAlchemy
ORM flush listeners, Core DML, bulk methods, textual INSERT/UPDATE/DELETE/MERGE/writable
CTE, procedure calls, scheduler/job/CLI registration, and constant/dynamic table-name
construction for Person, Employee, identities, assignments/links, all `hr_import_*`,
Contact, operation, audit, personnel events, `personnel_orders`,
`personnel_order_items`, `personnel_order_item_bases`, `personnel_order_attachments`, and
`personnel_order_evidence_scopes`; and the application-apply closure
`personnel_applications`, `personnel_application_lifecycle_audit`,
`personnel_application_blockers`, `personnel_record_metadata`, `employee_onboardings`,
`employee_onboarding_checklist_items`, `employee_onboarding_checklist_attachments`,
`employee_onboarding_task_audit`, `employee_onboarding_notifications`,
`employee_onboarding_notification_recipients`, `employee_onboarding_notification_deliveries`,
`employee_onboarding_notification_delivery_attempts`,
`person_photos`, `person_photo_sources`, `personnel_record_events`, `employee_events` and
`security_audit_log`. It also expands
indirect callers to the terminal DML.
An unresolved dynamic target, unparsed
SQL fragment, mutating callsite absent from §9.3, changed file:line/SQL fingerprint, or
missing migrate/disable proof fails CI. It is not permissible to mark an unknown callsite
covered by executing a neighboring route or branch.
The gate also requires one static, one runtime and one catalog evidence record for every
baseline row; absence or staleness of any one record, an incomplete incoming call graph,
or a production-packaged support/hard-delete writer without disposition disables all
personnel application/order/orchestration apply entrypoints as one rollout unit.

Two independent supplementary proofs must also pass but never compensate for a static
failure:

1. SQLAlchemy `before_cursor_execute` runtime instrumentation records normalized DML,
   callsite, entrypoint, transaction owner, and lock-helper tokens across the maintained
   route/worker/CLI branch corpus. A runtime-only callsite fails the static inventory;
   lack of observation fails release coverage but does not declare an unexecuted branch
   read-only.
2. PostgreSQL catalog inventory records every non-system trigger, rewrite rule, writable
   function/procedure, event trigger, and FK cascade action that can touch a controlled
   table. A catalog-only writer or changed definition fails the manifest.

Tests/fixtures are reported in a separate non-production section and cannot satisfy route
coverage. Historical Alembic revisions are recorded by revision and classified disabled
for runtime execution on an already-upgraded schema; any pending/new migration is a live
writer and needs an explicit migrate-or-disable disposition. The artifact contains
repository commit, deployed package hash, callsite, entity classes,
route/worker entrypoint, transaction owner, observed locks, approved §9.2 class sequence,
and `migrate | disable` disposition plus its proof (`helper fingerprint`, route/command
disable assertion, package deny-list, or applied migration revision). CI fails on an
unclassified writer, missing disposition proof, required runtime coverage gap, any catalog
writer absent from the artifact, or a deployed artifact hash mismatch. Production
startup independently compares the signed inventory/package hash to the reviewed rollout
manifest and keeps orchestrator apply disabled on mismatch. This automated gate, not the
phrase “newly discovered writer,” is the normative completeness proof.

### 9.5. Rollout gate

Orchestrator apply is forbidden until §9.4 passes against the exact deployed artifact;
every matrix writer uses the common helper or its entrypoint is technically disabled;
every order/evidence writer uses class 3a or is technically disabled;
direct assignment writes outside C2 are removed; old/new paths cannot run with different
orders; §5 checks, watermark, exclusion constraint, unique index, and boundary writer are
installed and caught up; concurrency scenarios cover orchestrator with C2, boundary
activation, enrollment queue, Phase 3I, personnel-order hire, and identity reconciliation.
Preview may precede this gate because it is read-only. Production apply has no per-route
exception or staged bypass before this common gate.

---

## 10. Final atomic sequence

After authenticated/authorized idempotency replay processing and trusted-token validation,
one PostgreSQL transaction acquires the full §9.2 lock set, including the order-evidence
scope lock; rereads every top-level row and each finite §7.1 child collection with the
specified lock mode/order; recomputes JCS state digest; compares it; and only then enters
the first business mutation. A concurrent child INSERT waits on class 3a; UPDATE/DELETE
waits there before touching a child; after wake-up the generation/collection mismatch is
`STALE_EXPECTED_STATE`. No mutation may precede this reread.

| Step | Authority | Preconditions/action/result | Rollback assertion |
|---:|---|---|---|
| 1 | orchestrator | auth, request/identity/assignment/evidence/environment validation | no write |
| 2 | idempotency | operation lock; insert/resolve row; replay/conflict before mutation | operation row disappears |
| 3 | common locks | complete finite §7.1 outcome-state lock pass through class 10, including 3a scope and 3b ordered order collections; rebuild/compare full state digest before business DML | locks release; stale state writes nothing |
| 4 | ADR-048 | Create-or-Link exactly one Person | new Shell disappears |
| 5 | Employee port | create one for enrollment or validate existing for repair | Employee disappears; repair never creates |
| 6 | ADR-048 link port | verify/set `employees.person_id` after conflicts | link disappears |
| 7 | identity port | create/verify exact `employee_identity`, never overwrite | identity disappears |
| 8 | strict C2 | execute separate evidenced assignment intent | all assignment/link changes disappear; old row restored |
| 9 | reconciliation tx port | project exact C2 result | Employee projection disappears |
| 10 | event/audit ports | append required provenance and strict success audit | no success event/audit |
| 11 | import binding | bind exact `hr_import_rows` source rows | row binding disappears |
| 12 | normalized propagation | propagate Employee ID/review binding to normalized records | normalized changes disappear |
| 13 | import metadata | write enrollment metadata to `hr_import_rows.normalized_payload` | metadata disappears independently of binding |
| 14 | Contact | project expected Employee/Person | Contact change disappears |
| 15 | idempotency | safe result; status `SUCCEEDED` | result disappears |
| 16 | transaction owner | commit only after all checks | all-or-nothing |

The operation-row INSERT in step 2 is idempotency state, not business mutation. Every
existing mutable row through Contact class 10 is locked and reread in step 3 before step
4. Watermark-behind, position rename, or any other digest difference returns respectively
`ACTIVE_STATE_STALE`, `STALE_POSITION_REFERENCE`, or `STALE_EXPECTED_STATE`; operation-row
rollback leaves no first business mutation. No failure leaves partial Person, Employee, identity, link,
assignment, Contact, binding, success audit/result. Combined transition cannot leave old
row closed/voided without required replacement.

### 10.1. One fault scenario per physical write boundary

Fault injection is not grouped by service step. The implementation must expose these
distinct injection points; a mode that omits a boundary marks that scenario not applicable,
never silently combines it with another point.

| Fault point | Inject exactly | Required rollback assertion |
|---|---|---|
| `FI-01` | after operation `IN_PROGRESS` INSERT | operation row/result absent; no domain write |
| `FI-02` | after Person Shell INSERT | Person/link and every later entity absent/restored |
| `FI-03` | after Employee INSERT | Employee, Person/link, and every later entity absent/restored |
| `FI-04` | after Employee–Person link UPDATE | link, Employee, Person, and every later entity absent/restored |
| `FI-05` | after `employee_identity` INSERT, or after locked exact identity validation when no INSERT is required | identity write when present and all earlier/later writes absent/restored; validation-only branch restores the earlier link and performs no later write |
| `FI-06` | after old assignment close or void UPDATE | old assignment restored; no successor/projection/event/binding/Contact/result |
| `FI-07` | after new assignment INSERT | new assignment and old row restored; all other entities restored |
| `FI-08` | after `employee_assignment_links` INSERT/UPDATE | assignment link and all other entities restored; provenance columns roll back with assignment row |
| `FI-09` | after reconciliation Employee UPDATE | Employee projection plus assignment/identity/Employee/Person/link restored |
| `FI-10` | after `PERSON_SHELL_CREATED` personnel event INSERT | shell event and every domain/import/Contact/operation write restored |
| `FI-11` | after Employee operational event INSERT | Employee event and every other write restored |
| `FI-12` | after strict success-audit INSERT | audit and every business write restored |
| `FI-13` | after each individual `hr_import_rows` binding UPDATE; scenario iterates every emitted statement ordinal | all row bindings and earlier/later writes restored |
| `FI-14` | after each `hr_import_normalized_records` propagation UPDATE; every statement ordinal | normalized and row bindings plus all earlier/later writes restored |
| `FI-15` | after each subsequent `hr_import_rows.normalized_payload` metadata UPDATE; every statement ordinal | metadata, normalized, bindings and every earlier/later write restored |
| `FI-16` | Contact INSERT/UPDATE itself fails before success | no Contact change; all import layers, events/audit, reconciliation, assignment, identity, Employee, Person/link, operation state/result restored |
| `FI-17` | immediately after successful Contact write, before result persistence | Contact plus every entity listed for `FI-16` restored; no success state/result |
| `FI-18` | operation result JSON or `status='SUCCEEDED'` UPDATE fails | Contact plus every import/event/audit/projection/assignment/link/identity/Employee/Person write restored; no success state/result |
| `FI-19` | after `EMPLOYEE_PERSON_LINKED` personnel event INSERT | link event and every domain/import/Contact/operation write restored |
| `FI-20` | after `ASSIGNMENT_CORRECTED` personnel event INSERT | correction event and every domain/import/Contact/operation write restored |
| `FI-21` | after canonical adoption/provenance UPDATE of an existing assignment, before assignment-link DML | assignment key/adoption/version restored; no link/projection/event/import/Contact/result |

PG-02–14 map to FI-01–13; PG-74/75 map to FI-14/15; PG-15–17 map to
FI-16–18; PG-72/73 map to FI-19/20; PG-100 maps to FI-21. A repeated SQL boundary is not grouped away: its PG
scenario injects after every concrete statement ordinal in the request. Each snapshots
and compares
Person/link, Employee, `employee_identity`, assignment/link/provenance, Employee event,
`personnel_record_events`, security audit, import binding, normalized propagation,
row metadata, Contact, and
operation status/result, even when the injected failure occurs after only a subset.
Together with the mandatory composite expansion below, this is the atomicity proof for
all mutating boundaries in the sequence; neither paragraph alone claims composite
completeness.

PG-337 is the mandatory composite expansion of that mapping. It runs a separate
transaction for every physical statement ordinal and for both static branches:

| Composite branch/boundary | Exact FI mapping |
|---|---|
| P0 Shell INSERT | FI-02; P1 marks FI-02 not applicable |
| P0/P1 Employee–Person link UPDATE | FI-04 |
| P0/P1 identity INSERT or locked validation boundary | FI-05 |
| P0/P1 C2 assignment INSERT and application provenance write | FI-07; if C2 adopts an existing application assignment instead of INSERT, FI-21 replaces FI-07 for that physical branch |
| P0/P1 assignment-link INSERT/UPDATE | FI-08 |
| P0/P1 reconciliation Employee UPDATE | FI-09 |
| P0 `PERSON_SHELL_CREATED` INSERT | FI-10; P1 marks FI-10 not applicable |
| Employee operational event | FI-11 is explicitly not applicable because both composite rows require no Employee event |
| P0/P1 strict success-audit INSERT | FI-12 |
| each P0/P1 import binding UPDATE sorted by `(batch_id,row_id)` | FI-13, one transaction per statement ordinal |
| each P0/P1 normalized-record propagation statement | FI-14, one transaction per statement ordinal |
| each separate P0/P1 import metadata UPDATE | FI-15, one transaction per statement ordinal |
| P0/P1 Contact failure and successful Contact boundary | FI-16 and FI-17 respectively |
| P0/P1 operation result/status finalization | FI-18 |
| P0/P1 `EMPLOYEE_PERSON_LINKED` INSERT | FI-19 |
| `ASSIGNMENT_CORRECTED` | FI-20 is explicitly not applicable to an open-assignment composite |

Every PG-337 injection asserts the complete pre-operation committed snapshot, including
P0 Person absence or unchanged P1 Person, NULL Employee link, identity, assignment/link,
Employee projection, both event tables, audit, every import layer, Contact and operation
row/result. No grouped service-step injection substitutes for an emitted SQL ordinal.
After rollback, retry with the same key/request begins from that original committed
snapshot and may execute one fresh atomic attempt. A link without its C2 assignment,
reconciliation, required branch events, audit, provenance and result can never commit.

For FI-13 the physical order is exact: target import rows sort by `(batch_id,row_id)`;
ordinal `n` is the one UPDATE of row `n` setting `employee_id`, `match_status`, and the
binding portion of `normalized_payload`. After each such UPDATE its FI-13 injection runs
before any normalized propagation for that row. FI-14 then iterates that row's normalized
record UPDATE/supersede statements by `normalized_record_id`; FI-15 is the subsequent one
metadata UPDATE of the same import row. One FI type may be parameterized by ordinal, but
the mandatory scenario count is the number of emitted SQL statements: zero skipped
ordinals and one injected transaction per ordinal. A new binding SQL shape or additional
statement changes the static manifest and automatically expands PG-14.

---

## 11. Events, audit, and migration

### 11.1. Roles and exact vocabulary

The four C2 commands remain non-persisted command types. This ADR adds exactly three
`personnel_record_events` values: `PERSON_SHELL_CREATED`, `EMPLOYEE_PERSON_LINKED`, and
`ASSIGNMENT_CORRECTED`. It does not add any value to `hr_personnel_change_events`.

The migration adds these exact columns to `public.personnel_record_events`:

| Column | PostgreSQL type | Nullability / FK |
|---|---|---|
| `orchestration_operation_id` | `BIGINT` | NULL for legacy; FK `personnel_orchestration_operations(operation_id) ON DELETE RESTRICT` |
| `correlation_id` | `UUID` | NULL for legacy |
| `orchestration_mode` | `TEXT` | NULL for legacy; one exact §2 mode for new types |
| `evidence_reference_fingerprint` | `CHAR(64)` | NULL for legacy; lowercase-hex CHECK |
| `replacement_assignment_id` | `BIGINT` | NULL; FK `person_assignments(assignment_id) ON DELETE RESTRICT` |
| `before_lifecycle_status` | `TEXT` | NULL except correction; CHECK in `active|closed` |
| `after_lifecycle_status` | `TEXT` | NULL except correction; exact `voided` |
| `outcome_code` | `TEXT` | NULL for legacy; exact value below |

For all three new event types, `person_id`, `domain_code`, `record_table_name`,
`record_id`, `event_type`, `event_at`, `actor_id`, every common new column except the
type-specific nullable fields, and `event_payload` are persisted. `actor_id` is non-empty
text for these types; `event_payload` is exactly `'{}'::jsonb` because normative facts
are columns, not an extensible payload. `migration_run_id` and `migration_item_id` are
NULL. These rows have the following only valid values:

| `event_type` | domain/table/record | employee context | mode | correction columns | `outcome_code` |
|---|---|---|---|---|---|
| `PERSON_SHELL_CREATED` | `PERSON_IDENTITY` / `persons` / new `person_id` | NULL | `ENROLL_NEW_ACTIVE`, `LINK_ONLY`, or `LINK_AND_OPEN_MISSING_ASSIGNMENT` P0 | all NULL | `PERSON_SHELL_CREATED` |
| `EMPLOYEE_PERSON_LINKED` | `PERSON_IDENTITY` / `employees` / linked `employee_id` | equals `record_id` | `ENROLL_NEW_ACTIVE`, `LINK_ONLY`, or `LINK_AND_OPEN_MISSING_ASSIGNMENT` P0/P1 | all NULL | `EMPLOYEE_PERSON_LINKED` |
| `ASSIGNMENT_CORRECTED` void-only | `ASSIGNMENT_LIFECYCLE` / `person_assignments` / original assignment | nullable Employee | `CORRECT_ERRONEOUS_RECORD` | replacement NULL; before `active|closed`; after `voided` | `ERRONEOUS_ASSIGNMENT_VOIDED` |
| `ASSIGNMENT_CORRECTED` replacement | same | nullable Employee | `CORRECT_ERRONEOUS_RECORD_WITH_REPLACEMENT` | replacement non-NULL and not record ID; before `active|closed`; after `voided` | `ERRONEOUS_ASSIGNMENT_REPLACED` |

The DDL leaves no event/idempotency choice to migration authors (the later migration may
wrap these clauses for idempotent deployment but may not alter them):

```sql
ALTER TABLE public.personnel_record_events
  DROP CONSTRAINT personnel_record_events_employee_context_id_fkey,
  ADD CONSTRAINT fk_pre_employee_context
    FOREIGN KEY (employee_context_id)
    REFERENCES public.employees(employee_id)
    ON DELETE RESTRICT;

ALTER TABLE public.personnel_record_events
  ADD COLUMN orchestration_operation_id BIGINT NULL,
  ADD COLUMN correlation_id UUID NULL,
  ADD COLUMN orchestration_mode TEXT NULL,
  ADD COLUMN evidence_reference_fingerprint CHAR(64) NULL,
  ADD COLUMN replacement_assignment_id BIGINT NULL,
  ADD COLUMN before_lifecycle_status TEXT NULL,
  ADD COLUMN after_lifecycle_status TEXT NULL,
  ADD COLUMN outcome_code TEXT NULL,
  ADD CONSTRAINT fk_pre_orchestration_operation
    FOREIGN KEY (orchestration_operation_id)
    REFERENCES public.personnel_orchestration_operations(operation_id)
    ON DELETE RESTRICT,
  ADD CONSTRAINT fk_pre_replacement_assignment
    FOREIGN KEY (replacement_assignment_id)
    REFERENCES public.person_assignments(assignment_id)
    ON DELETE RESTRICT,
  ADD CONSTRAINT chk_pre_evidence_fingerprint CHECK (
    evidence_reference_fingerprint IS NULL
    OR evidence_reference_fingerprint ~ '^[0-9a-f]{64}$'
  ),
  ADD CONSTRAINT chk_pre_orchestration_contract CHECK ((
    (
      event_type NOT IN (
        'PERSON_SHELL_CREATED', 'EMPLOYEE_PERSON_LINKED', 'ASSIGNMENT_CORRECTED'
      )
      AND orchestration_operation_id IS NULL
      AND correlation_id IS NULL
      AND orchestration_mode IS NULL
      AND evidence_reference_fingerprint IS NULL
      AND replacement_assignment_id IS NULL
      AND before_lifecycle_status IS NULL
      AND after_lifecycle_status IS NULL
      AND outcome_code IS NULL
    )
    OR
    (
      event_type IS NOT NULL
      AND event_type IS NOT DISTINCT FROM 'PERSON_SHELL_CREATED'
      AND domain_code IS NOT NULL
      AND domain_code IS NOT DISTINCT FROM 'PERSON_IDENTITY'
      AND record_table_name IS NOT NULL
      AND record_table_name IS NOT DISTINCT FROM 'persons'
      AND record_id IS NOT NULL AND person_id IS NOT NULL
      AND record_id IS NOT DISTINCT FROM person_id
      AND employee_context_id IS NULL
      AND orchestration_operation_id IS NOT NULL
      AND correlation_id IS NOT NULL
      AND orchestration_mode IS NOT NULL
      AND orchestration_mode IN (
        'ENROLL_NEW_ACTIVE', 'LINK_ONLY', 'LINK_AND_OPEN_MISSING_ASSIGNMENT'
      )
      AND evidence_reference_fingerprint IS NOT NULL
      AND replacement_assignment_id IS NULL
      AND before_lifecycle_status IS NULL
      AND after_lifecycle_status IS NULL
      AND outcome_code IS NOT NULL
      AND outcome_code IS NOT DISTINCT FROM 'PERSON_SHELL_CREATED'
      AND actor_id IS NOT NULL AND length(trim(actor_id)) > 0
      AND event_payload IS NOT NULL
      AND event_payload IS NOT DISTINCT FROM '{}'::jsonb
      AND migration_run_id IS NULL AND migration_item_id IS NULL
    )
    OR
    (
      event_type IS NOT NULL
      AND event_type IS NOT DISTINCT FROM 'EMPLOYEE_PERSON_LINKED'
      AND domain_code IS NOT NULL
      AND domain_code IS NOT DISTINCT FROM 'PERSON_IDENTITY'
      AND record_table_name IS NOT NULL
      AND record_table_name IS NOT DISTINCT FROM 'employees'
      AND record_id IS NOT NULL
      AND employee_context_id IS NOT NULL
      AND employee_context_id IS NOT DISTINCT FROM record_id
      AND orchestration_operation_id IS NOT NULL
      AND correlation_id IS NOT NULL
      AND orchestration_mode IS NOT NULL
      AND orchestration_mode IN (
        'ENROLL_NEW_ACTIVE', 'LINK_ONLY', 'LINK_AND_OPEN_MISSING_ASSIGNMENT'
      )
      AND evidence_reference_fingerprint IS NOT NULL
      AND replacement_assignment_id IS NULL
      AND before_lifecycle_status IS NULL
      AND after_lifecycle_status IS NULL
      AND outcome_code IS NOT NULL
      AND outcome_code IS NOT DISTINCT FROM 'EMPLOYEE_PERSON_LINKED'
      AND actor_id IS NOT NULL AND length(trim(actor_id)) > 0
      AND event_payload IS NOT NULL
      AND event_payload IS NOT DISTINCT FROM '{}'::jsonb
      AND migration_run_id IS NULL AND migration_item_id IS NULL
    )
    OR
    (
      event_type IS NOT NULL
      AND event_type IS NOT DISTINCT FROM 'ASSIGNMENT_CORRECTED'
      AND domain_code IS NOT NULL
      AND domain_code IS NOT DISTINCT FROM 'ASSIGNMENT_LIFECYCLE'
      AND record_table_name IS NOT NULL
      AND record_table_name IS NOT DISTINCT FROM 'person_assignments'
      AND record_id IS NOT NULL
      AND orchestration_operation_id IS NOT NULL
      AND correlation_id IS NOT NULL
      AND evidence_reference_fingerprint IS NOT NULL
      AND before_lifecycle_status IS NOT NULL
      AND before_lifecycle_status IN ('active', 'closed')
      AND after_lifecycle_status IS NOT NULL
      AND after_lifecycle_status IS NOT DISTINCT FROM 'voided'
      AND actor_id IS NOT NULL AND length(trim(actor_id)) > 0
      AND event_payload IS NOT NULL
      AND event_payload IS NOT DISTINCT FROM '{}'::jsonb
      AND migration_run_id IS NULL AND migration_item_id IS NULL
      AND (
        (
          orchestration_mode IS NOT NULL
          AND orchestration_mode IS NOT DISTINCT FROM 'CORRECT_ERRONEOUS_RECORD'
          AND replacement_assignment_id IS NULL
          AND outcome_code IS NOT NULL
          AND outcome_code IS NOT DISTINCT FROM 'ERRONEOUS_ASSIGNMENT_VOIDED'
        )
        OR
        (
          orchestration_mode IS NOT NULL
          AND orchestration_mode IS NOT DISTINCT FROM 'CORRECT_ERRONEOUS_RECORD_WITH_REPLACEMENT'
          AND replacement_assignment_id IS NOT NULL
          AND replacement_assignment_id IS DISTINCT FROM record_id
          AND outcome_code IS NOT NULL
          AND outcome_code IS NOT DISTINCT FROM 'ERRONEOUS_ASSIGNMENT_REPLACED'
        )
      )
    )
  ) IS TRUE);

CREATE FUNCTION public.pre_orchestration_event_reference_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  employee_person BIGINT;
  stored_mode TEXT;
  stored_person_resolution TEXT;
  assignment_row RECORD;
  assignment_count INTEGER := 0;
  expected_assignment_count INTEGER := 0;
BEGIN
  SELECT o.mode, o.person_resolution_code
  INTO stored_mode, stored_person_resolution
  FROM public.personnel_orchestration_operations o
  WHERE o.operation_id = NEW.orchestration_operation_id
  FOR KEY SHARE;
  IF NOT FOUND OR stored_mode IS DISTINCT FROM NEW.orchestration_mode THEN
    RAISE EXCEPTION 'PERSONNEL_EVENT_MODE_RESOLUTION_MISMATCH'
      USING ERRCODE = '23514';
  END IF;
  IF NEW.orchestration_mode = 'LINK_AND_OPEN_MISSING_ASSIGNMENT' THEN
    IF NEW.event_type = 'PERSON_SHELL_CREATED'
       AND stored_person_resolution IS DISTINCT FROM 'P0_CREATE' THEN
      RAISE EXCEPTION 'PERSONNEL_EVENT_MODE_RESOLUTION_MISMATCH'
        USING ERRCODE = '23514';
    END IF;
    IF NEW.event_type = 'EMPLOYEE_PERSON_LINKED'
       AND stored_person_resolution NOT IN ('P0_CREATE', 'P1_ADOPT') THEN
      RAISE EXCEPTION 'PERSONNEL_EVENT_MODE_RESOLUTION_MISMATCH'
        USING ERRCODE = '23514';
    END IF;
  END IF;

  PERFORM 1 FROM public.persons p
  WHERE p.person_id = NEW.person_id
  FOR KEY SHARE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'PERSONNEL_EVENT_REFERENCE_MISMATCH' USING ERRCODE = '23514';
  END IF;

  IF NEW.event_type = 'EMPLOYEE_PERSON_LINKED' THEN
    SELECT e.person_id INTO employee_person
    FROM public.employees e WHERE e.employee_id = NEW.record_id
    FOR NO KEY UPDATE;
    IF NOT FOUND OR employee_person IS DISTINCT FROM NEW.person_id THEN
      RAISE EXCEPTION 'PERSONNEL_EVENT_REFERENCE_MISMATCH' USING ERRCODE = '23514';
    END IF;
  END IF;

  IF NEW.event_type = 'ASSIGNMENT_CORRECTED' AND NEW.employee_context_id IS NOT NULL THEN
    SELECT e.person_id INTO employee_person
    FROM public.employees e WHERE e.employee_id = NEW.employee_context_id
    FOR NO KEY UPDATE;
    IF NOT FOUND OR employee_person IS DISTINCT FROM NEW.person_id THEN
      RAISE EXCEPTION 'PERSONNEL_EVENT_REFERENCE_MISMATCH' USING ERRCODE = '23514';
    END IF;
  END IF;

  IF NEW.event_type = 'ASSIGNMENT_CORRECTED' THEN
    expected_assignment_count := CASE WHEN NEW.replacement_assignment_id IS NULL THEN 1 ELSE 2 END;
    FOR assignment_row IN
      SELECT a.assignment_id, a.person_id
      FROM public.person_assignments a
      WHERE a.assignment_id = NEW.record_id
         OR a.assignment_id = NEW.replacement_assignment_id
      ORDER BY a.assignment_id
      FOR NO KEY UPDATE
    LOOP
      assignment_count := assignment_count + 1;
      IF assignment_row.person_id IS DISTINCT FROM NEW.person_id THEN
        RAISE EXCEPTION 'PERSONNEL_EVENT_REFERENCE_MISMATCH' USING ERRCODE = '23514';
      END IF;
    END LOOP;
    IF assignment_count <> expected_assignment_count THEN
      RAISE EXCEPTION 'PERSONNEL_EVENT_REFERENCE_MISMATCH' USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_pre_orchestration_reference_guard
BEFORE INSERT OR UPDATE ON public.personnel_record_events
FOR EACH ROW
WHEN (NEW.event_type IN
  ('PERSON_SHELL_CREATED', 'EMPLOYEE_PERSON_LINKED', 'ASSIGNMENT_CORRECTED'))
EXECUTE FUNCTION public.pre_orchestration_event_reference_guard();

CREATE FUNCTION public.pre_orchestration_coupling_update_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'employees' THEN
    IF TG_OP = 'DELETE' OR NEW.person_id IS DISTINCT FROM OLD.person_id THEN
      PERFORM 1 FROM public.personnel_record_events e
      WHERE (e.event_type = 'EMPLOYEE_PERSON_LINKED' AND e.record_id = OLD.employee_id)
         OR (e.event_type = 'ASSIGNMENT_CORRECTED' AND e.employee_context_id = OLD.employee_id)
      ORDER BY e.event_id FOR SHARE;
      IF FOUND AND (TG_OP = 'DELETE' OR EXISTS (
        SELECT 1 FROM public.personnel_record_events e
        WHERE ((e.event_type = 'EMPLOYEE_PERSON_LINKED' AND e.record_id = OLD.employee_id)
            OR (e.event_type = 'ASSIGNMENT_CORRECTED' AND e.employee_context_id = OLD.employee_id))
          AND e.person_id IS DISTINCT FROM NEW.person_id
      )) THEN
        RAISE EXCEPTION 'PERSONNEL_EVENT_REFERENCE_MISMATCH' USING ERRCODE = '23514';
      END IF;
    END IF;
  ELSE
    IF TG_OP = 'DELETE' OR NEW.person_id IS DISTINCT FROM OLD.person_id THEN
      PERFORM 1 FROM public.personnel_record_events e
      WHERE e.event_type = 'ASSIGNMENT_CORRECTED'
        AND (e.record_id = OLD.assignment_id OR e.replacement_assignment_id = OLD.assignment_id)
      ORDER BY e.event_id FOR SHARE;
      IF FOUND AND (TG_OP = 'DELETE' OR EXISTS (
        SELECT 1 FROM public.personnel_record_events e
        WHERE e.event_type = 'ASSIGNMENT_CORRECTED'
          AND (e.record_id = OLD.assignment_id OR e.replacement_assignment_id = OLD.assignment_id)
          AND e.person_id IS DISTINCT FROM NEW.person_id
      )) THEN
        RAISE EXCEPTION 'PERSONNEL_EVENT_REFERENCE_MISMATCH' USING ERRCODE = '23514';
      END IF;
    END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_employee_personnel_event_coupling_guard
BEFORE UPDATE OF person_id OR DELETE ON public.employees
FOR EACH ROW EXECUTE FUNCTION public.pre_orchestration_coupling_update_guard();

CREATE TRIGGER trg_assignment_personnel_event_coupling_guard
BEFORE UPDATE OF person_id OR DELETE ON public.person_assignments
FOR EACH ROW EXECUTE FUNCTION public.pre_orchestration_coupling_update_guard();

CREATE UNIQUE INDEX uq_pre_orchestration_event
  ON public.personnel_record_events
     (event_type, orchestration_operation_id, record_table_name, record_id)
  WHERE orchestration_operation_id IS NOT NULL;
```

The outer `(...) IS TRUE` is normative: PostgreSQL `UNKNOWN` is rejected, not accepted as
a successful CHECK. Shell requires NULL employee context; link requires a non-NULL context
equal to `record_id`; correction alone permits NULL employee context, and when non-NULL
the exact locked trigger proves that Employee belongs to event `person_id`. The same
trigger proves original/replacement assignment ownership and the link Employee–Person
coupling. It is deliberately non-deferrable: every event writer already owns the
operation row, then obtains Person, optional Employee, assignment scope, and assignments
in §9 order; the trigger reacquires compatible locks in operation → Person → Employee →
numerically sorted assignment order and holds them to transaction end. Multiple events in
one transaction reuse those locks and must be
inserted in `(person_id,employee_context_id,record_id,replacement_assignment_id)` order.
Concurrent coupling UPDATE blocks on `FOR NO KEY UPDATE`; reverse-order compliant writers
block before event INSERT rather than deadlock. The two reciprocal BEFORE triggers make
the coupling permanent: later `person_id` changes or deletes lock matching event rows by
`event_id` and reject if the post-state would disagree. Employee DELETE is also blocked
by the `ON DELETE RESTRICT` FK. Person DELETE is blocked by the event `person_id` FK.
The exact stable rejections are `PERSONNEL_EVENT_MODE_RESOLUTION_MISMATCH` for an
operation-mode/P0/P1 mismatch and `PERSONNEL_EVENT_REFERENCE_MISMATCH` for an entity
coupling mismatch, both mapped from SQLSTATE `23514`. The guard is a read-only integrity
trigger, not an assignment writer.
The factual legacy FK used `ON DELETE SET NULL`; that action would violate the mandatory
link-event CHECK during Employee deletion. The exact reviewed migration therefore changes
this one FK to `ON DELETE RESTRICT`. Preflight requires the exact old generated constraint
name and blocks if another definition is present. Guarded downgrade may restore SET NULL
only when no new event row depends on the non-NULL context; otherwise it refuses before DDL.
Every common mode/outcome/evidence/operation field is explicitly non-NULL in its branch;
every prohibited type-specific field is explicitly NULL. PG-91–95 insert each valid type,
then independently vary every mandatory field to NULL, every prohibited field to non-NULL,
link context to NULL/unequal, and a legacy canonical C2 event. Only the three exact valid
branches and unchanged legacy C2 row are accepted. PG-345–348 additionally exercise the
actual composite P0/P1 operation-resolution CHECK, event CHECK and locked trigger,
including wrong-branch and wrong-mode rejection.

The operation FK and partial unique index mean replay returns the existing event ID; a different record or
event type may have its one intentional row in the same operation. A uniqueness conflict
with unequal persisted values is `PERSONNEL_EVENT_IDEMPOTENCY_CONFLICT` and rolls back.

Security audit types remain `PERSONNEL_ORCHESTRATION_APPLIED`,
`PERSONNEL_ORCHESTRATION_REJECTED_STALE`, `PERSONNEL_ORCHESTRATION_REPLAYED`, and
`EMPLOYEE_PERSON_LINK_REPAIRED` with §11.2 durability. `ASSIGNMENT_CORRECTED` is one
personnel event linking original/replacement; separate correction close/open events are
forbidden. Application commands create no synthetic canonical snapshots/events.
`person_assignments` remains SSoT; Employee events are operational chronology; personnel
journal, audit, and idempotency are not parallel assignment history.

### 11.2. Strict audit durability

Mutating apply uses caller-connection strict audit. Missing table, rejected type, write
failure, or missing returned `audit_id` is fatal; commit without success audit is
impossible. Required fields: actor, reason, operation/mode, correlation,
`idempotency_key_fingerprint`, before/after IDs, evidence fingerprint, result, success,
database timestamp. No sanitizer-forbidden `hash`/`token`/`secret` metadata key is used.

Success audit shares the business transaction. Stale/validation/auth rejection may write
a separate best-effort attempt audit only after rollback; it is not personnel/domain
history and its failure does not change the result into retry. Replay audit is optional;
failure does not block stored result or start another operation.

### 11.3. Migration contract

No migration is created here. Repository migration history at R13 does not contain
`person_assignment_activation_watermark`; the §5.1 DDL is target architecture only.
Watermark schema/initialization is a separate mandatory implementation slice and must be
applied before the read-only preflight is operationally enabled. A test-created ad hoc
table cannot satisfy this deployment gate. A later reviewed migration provides:

1. exact operation table/checks/unique constraint from §8, including
   `person_resolution_code` and `chk_poo_person_resolution`;
2. exact §4.2 origin/provenance/version columns, FKs, checks, three uniqueness scopes, and
   the immutable one-way provenance trigger;
3. §5.1 five-column watermark and `person_assignment_boundary_runs`, the strict immutable
   `adr065_boundary_error_metadata_valid` function, NULL-safe checks, retry/transition
   triggers, deferred `trg_pabr_t1_commit_guard`, retry-child index,
   begin-T1/recover/finalize SECURITY DEFINER functions and runtime privilege/catalog
   contract, initialization, class-1/1a
   compatibility and §5.3 guarantees;
4. domain seeds `PERSON_IDENTITY` and `ASSIGNMENT_LIFECYCLE`;
5. the eight exact event columns, two new FKs, exact replacement of the existing
   employee-context FK by `ON DELETE RESTRICT`, two CHECKs, the locked event-reference
   guard plus reciprocal Employee/assignment coupling guards, and partial unique index in §11.1;
6. DB security-audit CHECK additions for the four named security types and matching Python
   allowlist additions;
7. no application command/event value in the canonical-event CHECK.
8. Employee-event registry/DB allowlist support for exact `ASSIGNMENT_TERMS_CHANGE`; this
   is operational chronology and never a C1 canonical event.
9. §9.1 `personnel_order_evidence_scopes`, deterministic backfill/count preflight and
   class-3a helper required by every controlled order/evidence writer.
10. §9.3.1 delivery current-attempt columns/CHECKs, delivery-attempt table/backfill,
    conditional ACK/retry functions, closed route enum and runtime privilege changes;
    current ACK and application-notification paths remain disabled until this entire item
    and its catalog/data preflight pass.

Schema preflight verifies exact names, types, nullability, FK targets/actions, CHECK
definitions, predicates, extension availability, and absence of conflicting objects.
Data preflight separately reports: duplicate assignment keys and non-void application
keys/hashes under their exact predicates; canonical `source='transfer'` rows are required
to have NULL application marker/provenance unless independently application-created;
both directions of §5 flag eligibility; temporal overlaps; invalid provenance/adoption
pairs; duplicate proposed event idempotency tuples; and, for each of the three new event
types, every row violating its exact domain/table/record/employee/mode/evidence/
correction/outcome/payload rule. Any finding blocks before DDL; no implicit repair.

Upgrade order is additive columns and `row_version=1` → deterministic technical backfill only where
the reviewed mapping is one-to-one → domain seeds → FKs/format and type-contract CHECKs →
event/assignment uniqueness → provenance and event-coupling triggers → temporal/active
guarantees, singleton/scope initialization and boundary evidence → security vocabulary. Existing
events are not relabeled as any new type. Apply remains disabled through §9.5.

Downgrade preflight counts, by each new event type and each new column, every non-NULL
value; each operation/provenance/adoption value; each assignment depending on new key or
temporal guarantees; and each audit type. Any count or retained-code dependency refuses
before DDL. Downgrade never nulls, deletes, relabels, or rewrites event, audit, assignment,
or operation data; a forward fix is required.

---

## 12. Acceptance and first-batch examples

### 12.1. Макибаева Акмарал Сабитовна — normative acceptance example

This case-specific normative acceptance fixture, not a general ID-selection rule, uses
`employee_id=138`, confirmed masked IIN `********2378`, `batch_id=809`, `row_id=19968`,
and `normalized_record_ids=[35934,35935,35936]`. It must select
`LINK_AND_OPEN_MISSING_ASSIGNMENT` only if the locked predicate in §2.1 is complete; P0
creates a Shell and P1 adopts exactly one admissible Person, after which the existing
Employee link, identity, C2 assignment, reconciliation, events/audit, and these exact
import bindings commit atomically.

Required assignment fields remain deliberately unpopulated:
`production_position_id = UNCONFIRMED` and
`operator_confirmed_expected_normalized_position_name = UNCONFIRMED`. Apply remains
blocked until the operator supplies both and separately confirms the ADR-048 identity
decision, production org unit, position, rate, employment type, primary flag, assignment
start date, evidence admissibility, and reason. Neither `employees.date_from=2026-07-02`
nor `2026-07-10` associated with order №125-к is selected automatically. The operator
must separately confirm the start date and whether order №125-к is admissible evidence.
No concrete ID other than the case fixture, position name, second Employee, assignment
attribute, or leave/return date is generalized or inferred.

### 12.2. Өсерова Айсара Асанқызы — non-normative

The protocol may preserve `employee_id=16`, `person_id=11`. Apply remains blocked until
operator chooses correction or real-lifecycle completion and confirms the old episode’s
nature, required dates, manager org ID, evidence, and reason. Required position fields
remain deliberately unpopulated: `production_position_id = UNCONFIRMED` and
`operator_confirmed_expected_normalized_position_name = UNCONFIRMED`. This ADR does not
call the old row erroneous, temporary, acting-duty, manager, or head. The row is preserved
by the exact confirmed mode. Any successful operation remains subject to locked production
state and operator confirmation.

### 12.3. Position ID/name confirmation protocol

The two `UNCONFIRMED` markers above are documentation markers, never request values.
Preview is non-applicable for apply until the operator supplies a positive production
position ID and the expected position name. Both the operator value and the current
`public.positions.name` value for `positions.position_id` use one normalization: Unicode NFC; trim leading/trailing Unicode
whitespace; replace each internal whitespace run by one ASCII space; Unicode casefold;
NFC again. Empty output is invalid.

Preview reads the production position by ID in its §7.1 snapshot, requires the row to
exist, compares normalized database name byte-for-byte with the operator-confirmed
normalized name, and returns `POSITION_CONFIRMATION_REQUIRED` when either input is absent
or `POSITION_NAME_MISMATCH` on inequality. The request business digest includes both the
decimal-string ID and normalized operator name; the expected-state digest independently
includes the same ID and current normalized database name. The actual table has no
position activity or version column, so this ADR does not invent either.

Apply locks that exact position row `FOR SHARE` at §9.2 reference-lock class, rereads and
normalizes `positions.name` before Person or Employee DML. There is no activity check
because the factual schema has no activity field. Missing row or any normalized-name
change from the preview state returns `STALE_POSITION_REFERENCE`. An initial preview in
which the existing row name differs from the submitted confirmed name returns
`POSITION_NAME_MISMATCH`; apply never returns that code for a post-preview rename. No
fallback ID, raw `position_name`, or approximate
match is allowed. Neither person's actual production ID/name is established by this ADR,
and production apply for both remains prohibited pending confirmation and the common
rollout gate.

---

## 13. Normative invariants

1. **ORCH-1:** ADR-048 exclusively owns Person Create-or-Link.
2. **ORCH-2:** C2 exclusively owns assignment lifecycle/adoption.
3. **ORCH-3:** Orchestrator never writes assignments directly.
4. **ORCH-4:** Reconciliation is projection, not history.
5. **ORCH-5:** Shell and assignment remain separate commands.
6. **ORCH-6:** Active enrollment commits complete chain atomically.
7. **ORCH-7:** Repair never creates Employee.
8. **ORCH-8:** Every write-boundary failure leaves no partial operation rows.
9. **ORCH-9:** Every statically discovered callsite has a verified migrate/disable
   disposition; runtime/catalog evidence cannot waive a static failure.
10. **ORCH-10:** Partial unique index prevents two operational active primaries and the
    exclusion constraint prevents overlapping non-void primary episodes.
11. **ORCH-11:** `active_flag` is the C2-maintained projection for one fixed business date;
    exclusive/shared class-1a serialization and monotonic watermark make stale state fail
    closed; future/ended/closed/voided semantics are exact.
12. **ORCH-12:** C2 adoption cannot insert on ambiguity/conflict.
13. **ORCH-13:** Strict C2 has no fallbacks/defaults.
14. **ORCH-14:** Strict C2 is fail-fast.
15. **ORCH-15:** Reconciliation uses caller transaction/expected IDs.
16. **ORCH-16:** Repair mode is explicit.
17. **ORCH-17:** Missing date/evidence blocks apply, not preview.
18. **ORCH-18:** Technical/HIRE/import dates are never inferred.
19. **ORCH-19:** Preview is one repeatable-read read-only snapshot.
20. **ORCH-20:** Apply always rereads locked state.
21. **ORCH-21:** Any participating change, including watermark date/generation, makes
    first apply stale.
22. **ORCH-22:** Same key/digest returns stored result without personnel access.
23. **ORCH-23:** Same key with any changed assignment target/version, verifier,
    evidence/order, episode attribute, actor, operation, or mode conflicts.
24. **ORCH-24:** Expiry blocks first mutation, not committed replay.
25. **ORCH-25:** Unknown outcome retries only same key/request.
26. **ORCH-26:** Main audit failure rolls back; attempt/replay audit creates no domain state.
27. **ORCH-27:** Sensitive identity/free text/raw key never enters metadata.
28. **ORCH-28:** Correction voids and preserves original.
29. **ORCH-29:** Backdated/future repair never changes non-target episodes implicitly.
30. **ORCH-30:** Application commands create no synthetic canonical events.
31. **ORCH-31:** Upgrade/downgrade preflight fails before invalidating DDL.
32. **ORCH-32:** Termination, absence, acting duty, rehire are never inferred.
33. **ORCH-33:** Position ID and operator-confirmed normalized name must match at preview
    and locked apply and participate in separate request/state digests.
34. **ORCH-34:** New personnel event values have the exact §11.1 DDL contract and never
    become synthetic canonical C1 events.
35. **ORCH-35:** Compatibility-first precedence, twenty-one formal predicates, their
    literal complement, allowed rows and compatible-pair default define all 836 tuples;
    tests never invent an outcome.
36. **ORCH-36:** Successor delta classification is disjoint; a rate/employment-type delta
    selects terms-change before org/position classification.
37. **ORCH-37:** Equal-date inconsistent projection fails with its exact code, zero business DML, and one durable result finalization.
38. **ORCH-38:** Application marker/identity/origin/adoption/lineage never clears or changes;
    only the one-way adoption transition and atomic void/replacement are permitted.
39. **ORCH-39:** Idempotency scope is caller/context plus raw-key fingerprint, never operation.
40. **ORCH-40:** Preview and apply use the same finite outcome-state closure, persisted order scope and exact tuples; no abstract version.
41. **ORCH-41:** Locked event and reciprocal entity triggers prevent every committed coupling mismatch.
42. **ORCH-42:** Successor temporal identity changes start date while unchanged business delta remains exact.
43. **ORCH-43:** Composite existing-card repair never commits a Person link without its
    confirmed C2 assignment, reconciliation, events/audit, and provenance.
44. **ORCH-44:** Composite assignment intent is explicit operator input and is never
    inferred from import, Employee, HIRE, or personnel-order data.
45. **ORCH-45:** PERSONNEL_ORDER evidence has exactly one byte-level profile; no partial,
    fallback, cross-order/item/scope/version/key fingerprint is valid.
46. **ORCH-46:** Every successful matrix row has exactly a compatible closed operator
    reason; mode names, technical metadata, and arbitrary text are never reasons.
47. **ORCH-47:** Business date `D` is fixed UTC+05 and only a valid singleton watermark
    with `effective_date=D` is current; stale and future rows fail closed.
48. **ORCH-48:** Watermark schema migration, C2 writer catch-up, key infrastructure and
    catalog/readiness proof precede operational preflight; ad hoc test DDL proves nothing
    about deployment readiness.

---

## 14. Mandatory PostgreSQL scenarios

All tests require a DB name containing `_test` or `-test`.

| ID | Scenario | Assertion |
|---|---|---|
| PG-01 | Complete enrollment | one complete chain/result |
| PG-02 | `FI-01` operation row | exact §10.1 rollback |
| PG-03 | `FI-02` Person Shell | exact §10.1 rollback |
| PG-04 | `FI-03` Employee | exact §10.1 rollback |
| PG-05 | `FI-04` Employee–Person link | exact §10.1 rollback |
| PG-06 | `FI-05` employee identity | exact §10.1 rollback |
| PG-07 | `FI-06` old assignment close/void | old row restored; full rollback |
| PG-08 | `FI-07` successor assignment insert | both assignment states restored; full rollback |
| PG-09 | `FI-08` assignment link/provenance | exact §10.1 rollback |
| PG-10 | `FI-09` reconciliation | projection and all earlier writes rollback |
| PG-11 | `FI-10` personnel event | event and full operation rollback |
| PG-12 | `FI-11` Employee event | event and full operation rollback |
| PG-13 | `FI-12` success audit | audit and full operation rollback |
| PG-14 | `FI-13` every individual import-binding UPDATE and every `(batch_id,row_id)` statement ordinal | one isolated injected transaction per ordinal; current/prior/following bindings, propagation, metadata and all domain writes rollback; zero skipped ordinals |
| PG-15 | `FI-16` Contact write failure | Contact and every listed entity/result rollback |
| PG-16 | `FI-17` fault after successful Contact | Contact and every listed entity/result rollback |
| PG-17 | `FI-18` result/status persistence failure | Contact and entire operation rollback; no success result |
| PG-18 | automatic writer inventory sees unknown/static-only/runtime-only/catalog writer | rollout gate fails |
| PG-19 | orchestrator races C2, boundary worker, queue, Phase 3I, order hire, identity merge | common order; no deadlock/duplicate/stale write |
| PG-20 | exact application-key adoption | existing row adopted; exact-key code; no insert |
| PG-21 | unique semantic adoption | one compatible row adopted; semantic code; no insert |
| PG-22 | ambiguous semantic adoption | ambiguous code; no adoption/insert |
| PG-23 | concurrent adoption of one application row | winner adopts; loser controlled conflict; no parallel row |
| PG-24 | same canonical event repeats adoption | replay code; no mutation |
| PG-25 | inconsistent legacy flags and lifecycle/date state in both directions | preflight separately reports true/ineligible, false/eligible, active/past-end, and closed/non-past-end rows |
| PG-26 | two operational active-primary inserts | at most one commits; controlled conflict |
| PG-27 | overlapping historical/current/future non-void primaries | exclusion constraint rejects every overlap; void/secondary unaffected |
| PG-28 | boundary activation with ended current and due successor | deactivate then activate, reconcile, watermark atomically |
| PG-29 | boundary activation with still-eligible active conflict | controlled conflict; flags/watermark rollback |
| PG-30 | missed date boundary | stale watermark makes reads/commands fail `ACTIVE_STATE_STALE` |
| PG-31 | process restart catch-up | catch-up commits before current reads are served |
| PG-32 | early explicit future activation | `ASSIGNMENT_NOT_EFFECTIVE_YET`, no mutation |
| PG-33 | strict C2 missing/inactive org | refuse; no fallback |
| PG-34 | strict C2 missing position ID/row or raw name only | refuse; no creation/fallback |
| PG-35 | strict C2 missing date/rate | refuse; no default |
| PG-36 | C2 internal error | propagates; total rollback |
| PG-37 | reconciliation | caller transaction, exact assignment, no post-commit read |
| PG-38 | initial unused idempotency key | one execution and business success code |
| PG-39 | concurrent same key/same business digest | one execution; stored replay |
| PG-40 | first operation INSERT rolls back | no row; one safe fresh attempt |
| PG-41 | same key/different expanded body digest | `IDEMPOTENCY_KEY_REUSED`; zero mutation |
| PG-42 | unknown commit outcome | stored replay or safe fresh execution only |
| PG-43 | committed replay after preview expiry | stored result; token not parsed; no personnel access |
| PG-44 | malformed/unknown-kid/bad-signature token on first mutation | distinct code; untrusted payload unused |
| PG-45 | one second before token expiry | accepted if all other checks pass |
| PG-46 | exactly at token expiry | `PREVIEW_TOKEN_EXPIRED` |
| PG-47 | one second after token expiry | `PREVIEW_TOKEN_EXPIRED` |
| PG-48 | issued at future-skew equality / one second beyond | equality accepted; beyond `PREVIEW_TOKEN_NOT_YET_VALID` |
| PG-49 | retired kid one second inside / exactly at / one second outside window | inside signature verifies (then normal expiry rules apply); equality and outside return `PREVIEW_TOKEN_UNKNOWN_KID` |
| PG-50 | token issued one second before rotation | verifies only until its own expiry; retention is sufficient |
| PG-51 | context/request digest mismatch after good signature | exact context/request code; no state read/write |
| PG-52 | preview snapshot consistency | no mixed-state token |
| PG-53 | identity/assignment/import/link/org/position/Contact/watermark change | exact stale code; no first mutation |
| PG-54 | confirmed position ID/name match, preview mismatch, locked apply change | success / `POSITION_NAME_MISMATCH` / `STALE_POSITION_REFERENCE` |
| PG-55 | continuous transition at invalid/effective boundary | `transition_date > old.start_date`; exact adjacent dates |
| PG-56 | explicit-gap successor fields | `ASSIGNMENT_TIMELINE_GAP_UNSUPPORTED`; no mutation |
| PG-57 | explicit or backdated overlap/intervening episode | controlled overlap error; no implicit change |
| PG-58 | valid historical backdate before current | target changes; current/non-target rows unchanged |
| PG-59 | future preserve | verified no-op; no event/reconciliation |
| PG-60 | each future transition mode | exact delta classification; old active through inclusive end; successor inactive; boundary reconciles atomically |
| PG-61 | close, correction void-only, correction with replacement | exact distinct event/no-event and success codes from §5.4 |
| PG-62 | machine-readable expansion of all 836 state × operation × mode tuples | incompatible pair gets only `INVALID_OPERATION_MODE`; compatible allowed row gets its one outcome; compatible unlisted row gets only `MODE_SOURCE_STATE_MISMATCH`; unsupported gets only its exact rejection |
| PG-63 | Makibaeva-shaped unconfirmed position fixture | confirmation blocker; no second Employee |
| PG-64 | Oserova-shaped unconfirmed fact/position fixture | apply blocked; no reclassification |
| PG-65 | exact schema/migration preflight | names/types/nullability/FKs/CHECKs/predicates and all data directions verified |
| PG-66 | downgrade with each new field/event/key/guarantee dependency | refusal before DDL; no data loss |
| PG-67 | Person Shell outside enrollment | no assignment implied |
| PG-68 | orchestrator attempts direct assignment SQL | architecture/rollout test rejects; only C2 mutates |
| PG-69 | success audit table/type missing or write fails | total rollback |
| PG-70 | success audit returns no ID | total rollback |
| PG-71 | replay audit fails | stored result still returned; no mutation |
| PG-72 | `FI-19` Employee–Person personnel event | event and full operation rollback |
| PG-73 | `FI-20` assignment-correction personnel event | event and full operation rollback |
| PG-74 | `FI-14` normalized-record propagation; every statement ordinal | normalized/import and full operation rollback |
| PG-75 | `FI-15` subsequent import-row metadata; every statement ordinal | metadata/normalized/import and full operation rollback |
| PG-76 | overlapping boundary workers with different dates | exclusive class 1a serializes; monotonic generation/date; no lost advance |
| PG-77 | first singleton initialization and repeated migration | exact five columns/row; same-date recheck passes; unequal existing row blocks |
| PG-78 | stale, duplicate, out-of-order and future-date boundary request | exact `BOUNDARY_RUN_DUPLICATE`/`BOUNDARY_RUN_OUT_OF_ORDER`/`BOUNDARY_RUN_FUTURE_DATE`; zero lifecycle/reconciliation mutation |
| PG-79 | several sequential future successors and long catch-up | skipped episodes close; only target-eligible successor activates; invalid chain rolls back |
| PG-80 | crash before watermark UPDATE, after UPDATE-before-commit, and after commit | first two fully rollback; post-commit restart returns duplicate |
| PG-81 | exact §4 JSON/JCS fixture | exact bytes, hash and `app:v1:` key asserted |
| PG-82 | canonical C2 `source='transfer'` | NULL origin/provenance accepted; no application provenance inferred |
| PG-83 | correction replacement after original void | same application key/hash and different exact `app-row:v1:` physical keys commit; never two non-void owners |
| PG-84 | concurrent replacement and canonical adoption | Person/row locks yield one controlled winner; no parallel episode |
| PG-85 | semantic candidate changed after canonical event | version mismatch returns `ADOPTION_STALE_APPLICATION_EPISODE`; no fallback candidate |
| PG-86 | two similar episodes and normalization variants | exact compatibility selects correct ID or ambiguity/conflict; never wrong adoption |
| PG-87 | equal business fields, different assignment target IDs | distinct request digests |
| PG-88 | equal target, different expected `row_version` | distinct request digests |
| PG-89 | different verifier, confirmation, evidence or personnel-order ID | distinct request digests |
| PG-90 | same key with any PG-87–89 digest difference | stable `IDEMPOTENCY_KEY_REUSED`; no token parse/mutation |
| PG-91 | one valid row for each of the four §11.1 event rows/three types | accepted with exact persisted values |
| PG-92 | NULL in each mandatory type-specific field, one at a time | CHECK rejects every row, proving no UNKNOWN acceptance |
| PG-93 | non-NULL in each prohibited type-specific field | CHECK rejects every row |
| PG-94 | link employee context NULL or unequal; correction context NULL, matching, or non-matching | link variants reject; correction NULL and matching accept under its exact branch; non-matching rejects in the locked reference guard |
| PG-95 | unchanged legacy/canonical C2 personnel event plus upgrade/downgrade preflight | legacy accepted; no synthetic C1 value; guarded downgrade |
| PG-96 | current unchanged/transfer/position/combined/terms successors | exactly one delta class, event and success code each |
| PG-97 | future unchanged/transfer/position/combined/terms successors | exactly one future mode and scheduled Employee event rule each |
| PG-98 | rate/type delta combined with org/position delta | terms mode wins deterministically; every other submitted mode rejects |
| PG-99 | initial position mismatch, post-preview rename, stale watermark and other stale state together | exact §2 precedence: mismatch only at preview; apply returns active-state or position stale in order |
| PG-100 | `FI-21` existing-assignment adoption/provenance UPDATE | assignment key, adoption columns and row version restore; full operation rollback |
| PG-101 | duplicate-date run with one false eligible flag, lifecycle/date mismatch, link drift, or Employee projection drift | each variant returns `BOUNDARY_DUPLICATE_PROJECTION_INCONSISTENT`; zero business DML/watermark advance, durable evidence finalizes; retry repeats until repair |
| PG-102 | UPDATE application row clearing marker, key, hash, origin, evidence, replacement lineage, adoption event, or adoption time one field at a time | exact immutable/adoption error; original row and partial-index owner unchanged |
| PG-103 | UPDATE application key/hash to another valid value or convert canonical row to application by UPDATE | `APPLICATION_PROVENANCE_IMMUTABLE`; no identity owner change |
| PG-104 | C2 atomically voids application original then inserts same-identity replacement | trigger locks original; one non-void owner commits with retained lineage; rollback restores original |
| PG-105 | two concurrent replacements for one original | Person/original serialization; one commits, loser exact `APPLICATION_REPLACEMENT_CONFLICT`; never two owners |
| PG-106 | canonical `source='transfer'` INSERT with every application/adoption/replacement field NULL | accepted; remains outside application partial indexes |
| PG-107 | one caller/context and raw key: `ACTIVE_ENROLLMENT`, then `EXISTING_CARD_REPAIR` | one unique row; second request returns `IDEMPOTENCY_KEY_REUSED` before token parsing |
| PG-108 | same caller/context/key/operation with changed digest | `IDEMPOTENCY_KEY_REUSED`; no stored result disclosure or mutation |
| PG-109 | same raw key under different actor or authorization-context fingerprint | foreign row is not selected; independent scoped row may execute only after its own authorization |
| PG-110 | only operator-confirmed normalized org name differs | request digests differ; same scoped key conflicts |
| PG-111 | only one persisted Employee tuple field differs while all request IDs remain | Employee expected-state hash and locked state digest differ; first mutation forbidden |
| PG-112 | event transaction locks matching Employee; concurrent writer changes `employees.person_id` | writer blocks; after event commit reciprocal guard rejects incompatible change, after event rollback it proceeds; no mismatch persists |
| PG-113 | event transaction locks original/replacement assignments; concurrent writer changes either `person_id` | writer blocks; after event commit reciprocal guard rejects, after rollback it proceeds; all permutations preserve coupling |
| PG-114 | reverse start order: coupling writer holds compliant Person/Employee/assignment locks before event insert | event waits in the same global direction, then accepts new matching state or rejects `PERSONNEL_EVENT_REFERENCE_MISMATCH`; no deadlock inversion |
| PG-115 | concurrent DELETE referenced Employee with link/correction event | `ON DELETE RESTRICT`/row lock permits at most one compatible outcome; committed referenced event prevents DELETE |
| PG-116 | multiple sorted events in one transaction plus concurrent Employee/assignment updates | locks are reused in mandated order; all events commit consistently or transaction rolls back |
| PG-117 | mutate each whole-row field in Person, Employee, identity, assignment/link, evidence/order, import/normalized/metadata, Contact, org/position and watermark one at a time | rebuilt locked state digest changes; exact stale precedence; no first business DML |
| PG-118 | classifier fixture cross-product including zero/one/multiple Person candidates, link states, target temporality, intent and five deltas | every valid-common vector matches exactly one of twenty-one predicates or literal `S_UNSUPPORTED`; the composite P0/P1 intersection is empty and both precede standalone link/open states |
| PG-119 | unchanged continuous successor | old end is transition minus one day; new start is transition; business delta `UNCHANGED`; distinct start dates; no gap/overlap; exact completion result |
| PG-120 | discovered CLI/canonical-event/Employee-event/migration writer removed from §9 manifest or changed fingerprint | static gate fails; runtime/catalog proof cannot waive; production apply remains disabled |
| PG-121 | same preview request with missing/added row in any finite outcome-state collection | collection membership and state digest change; locked reread returns `STALE_EXPECTED_STATE` before step 4 |
| PG-122 | concurrent attachment INSERT after preview and before apply mutation | writer/apply serialize on order scope; apply reread sees generation/member change and returns `STALE_EXPECTED_STATE` |
| PG-123 | concurrent 1:1 basis INSERT when preview encoded no basis | scope lock prevents phantom; exactly one waits; apply succeeds on old snapshot or returns stale, never misses committed basis |
| PG-124 | concurrent order item/basis/attachment UPDATE | class 3a serializes before child lock; digest changes; no first orchestration mutation |
| PG-125 | concurrent child DELETE or replacement | scope generation and ordered collections change atomically; stale or pre-delete snapshot, never mixed state |
| PG-126 | writer attempts child/entity locks before order scope | common helper rejects lock-order inversion before DML; rollout fingerprint fails |
| PG-127 | known writer omits mandatory order scope token | static/runtime proof fails and production apply remains globally disabled |
| PG-128 | dynamic SQL targets an order evidence table without resolved scope protocol | unresolved dynamic writer blocks static inventory and rollout |
| PG-129 | either scope-lock participant rolls back then retries | row/generation/children rollback together; waiter rereads deterministic committed state |
| PG-130 | consistent equal-date boundary delivery | durable row completes `BOUNDARY_RUN_DUPLICATE`, projection true, identical watermark tuples, zero business DML |
| PG-131 | inconsistent equal-date boundary delivery | durable row completes `BOUNDARY_DUPLICATE_PROJECTION_INCONSISTENT`, projection false, exact compared tuple variant, zero business DML/watermark |
| PG-132 | crash before T0 claim commit | no run row; identical scheduler delivery safely claims once |
| PG-133 | crash after T0 commit before T1 finalization | durable `STARTED`; same UUID resumes; no domain change |
| PG-134 | crash after domain/watermark and evidence UPDATE but before T1 commit | all T1 changes roll back; row remains `STARTED`; retry is safe |
| PG-135 | retry after unknown T1 commit | lookup returns immutable `COMPLETED` result or resumes `STARTED`; never double-advances |
| PG-136 | duplicate scheduler delivery of one UUID | unique row; matching tuple replays result, conflicting tuple returns `BOUNDARY_RUN_CORRELATION_REUSED` |
| PG-137 | retry-chain and retention behavior | ordinal/link checks hold; completed rows remain indefinitely replayable and undeleted |
| PG-138 | change each application defining field (`person/org/position/department/type/rate/primary/start/source/created_at`) | trigger returns `APPLICATION_ASSIGNMENT_TRANSITION_INVALID`; row unchanged |
| PG-139 | clear or replace canonical snapshot after adoption | `APPLICATION_ADOPTION_IMMUTABLE`; adoption/provenance retained |
| PG-140 | clear or replace canonical entry after adoption | `APPLICATION_ADOPTION_IMMUTABLE`; adoption/provenance retained |
| PG-141 | repeat adoption or change its event/time/key | replay through C2 returns adoption replay only for identical canonical event; every UPDATE variant is rejected |
| PG-142 | permitted close, future-end schedule, boundary flag and date-preserving void transitions | each exact OLD/NEW predicate succeeds; every near-miss returns `APPLICATION_ASSIGNMENT_TRANSITION_INVALID` |
| PG-143 | atomic void-and-replacement | immediate uniqueness, original lock and trigger produce one retained identity owner at commit; rollback restores original |
| PG-144 | two concurrent replacements | one winner; every trigger/unique loser path maps after rollback/reread to `APPLICATION_REPLACEMENT_CONFLICT` |
| PG-145 | direct unique violation on either application partial index | SQLSTATE/constraint mapping yields `APPLICATION_REPLACEMENT_CONFLICT`, no raw DB outcome |
| PG-146 | fault after original void before replacement INSERT | transaction rollback restores original owner/provenance and releases no committed identity gap |
| PG-147 | parse and expand literal outcome fixture | exactly 836 unique tuples and category counts 396/20/23/397; no unknown enum, conditional field, macro, duplicate or overlap |
| PG-148 | compatible pair with `S_UNSUPPORTED` and a non-unsupported unlisted state | first returns only `UNSUPPORTED_SOURCE_STATE`; second only `MODE_SOURCE_STATE_MISMATCH` |
| PG-149 | application apply through `post_application_apply` | route graph reaches scope-locked order reread and complete application/onboarding transaction; no unlisted terminal DML |
| PG-150 | direct `orchestrate_hire_apply_for_application` and `apply_hire_for_application` fresh/already-applied paths | precheck is advisory; main transaction reacquires 3a/3b and terminal closure is identical |
| PG-151 | order apply reverse hook to `try_complete_linked_application_after_order_apply` | retained scope/connection covers application lifecycle and onboarding completion; unlinked/replay branches are deterministic |
| PG-152 | each terminal application lifecycle, metadata, onboarding/checklist/notification and photo/blocker/PPR DML | every callable and transaction owner appears as a separate manifest edge with disposition |
| PG-153 | remove one concrete application-apply callable/inverse hook/repository row from inventory | static gate fails and all production apply entrypoints remain disabled |
| PG-154 | omit respectively static, runtime-maintained-branch, or catalog evidence for one application-apply terminal writer | each independent variant fails the common rollout gate |
| PG-155 | fault/rollback then retry at every main application-apply terminal statement; photo precondition already committed | main transaction fully rolls back and retry is idempotent; durable photo/blocker state is reread as precondition, never mistaken for order success |
| PG-156 | UPDATE a COMPLETED boundary row to another otherwise valid COMPLETED shape | trigger returns `BOUNDARY_RUN_FINALIZATION_CONFLICT`; stored result is byte-identical |
| PG-157 | DELETE a STARTED or COMPLETED boundary row | trigger returns `BOUNDARY_RUN_IMMUTABLE`; row remains indefinitely retained |
| PG-158 | two finalizers race, and a finalizer uses wrong/expired lease owner | exactly one conditional UPDATE affects one row; loser/zero-row path is `BOUNDARY_RUN_FINALIZATION_CONFLICT` and cannot change domain state |
| PG-159 | error result with absent `reason_code`, JSON null, non-string, or empty string | every variant is rejected because CHECK is FALSE, never UNKNOWN |
| PG-160 | each non-success boundary outcome with its exact §5.1 reason/component/count object | matching row finalizes once; an object from another outcome rejects |
| PG-161 | expired STARTED lease with no live T1 | one recovery transaction increments `recovery_count`, returns `BOUNDARY_RUN_RECOVERY_ACQUIRED`, and the new owner alone may enter T1 |
| PG-162 | recovery races a live T1 that owns the run row | recovery waits; it then replays COMPLETED or acquires rolled-back STARTED, with no simultaneous domain work |
| PG-163 | cancellation obtains STARTED row before T1 | durable `BOUNDARY_RUN_CANCELLED`, reason `scheduler_cancelled`, NULL watermark/projection and zero business DML |
| PG-164 | cancellation races T1 or has unknown commit | row lock serializes; lookup returns exactly cancellation or T1 result, never a contradictory second completion |
| PG-165 | retry with missing/nonretryable parent, wrong target/context/actor/ordinal, or second child | trigger/unique index returns `BOUNDARY_RUN_RETRY_LINEAGE_INVALID` or the named unique conflict mapping; no child commits |
| PG-166 | duplicate scheduler delivery after terminal result | immutable stored result replays; different claim tuple is `BOUNDARY_RUN_CORRELATION_REUSED` |
| PG-167 | one selected personnel order and scope | top-level array is exactly one `{order_id,generation}` object with decimal-string members |
| PG-168 | multiple selected orders supplied in different request orders | scope array is sorted numerically by `order_id`; JCS bytes are identical |
| PG-169 | no personnel-order evidence in the outcome | top-level `personnel_order_evidence_scopes` is exactly `[]`, never omitted or NULL |
| PG-170 | initial preview selected order has missing/duplicate/invalid scope row | `ORDER_EVIDENCE_SCOPE_INVALID`; no digest-time repair and no first business DML |
| PG-171 | only scope generation changes after preview | locked array differs and returns `STALE_EXPECTED_STATE` at the common precedence position |
| PG-172 | scoped writer increments generation then rolls back | preview/apply digest remains the prior committed digest; retry increments exactly once on commit |
| PG-173 | preview and locked apply read identical order/scope state | canonical top-level representation and SHA-256 state digest are byte-for-byte equal |
| PG-174 | parse/evaluate every declared operator and `CUR/NONVOID/FUT/EVIDENCE_EXACT` function | grammar accepts each valid form; one locked row/date produces the same result in classifier table, registry and both parsers |
| PG-175 | expand every date/gap/temporal/C2/adoption/reconciliation token and required-input bundle | each maps to exactly one registry predicate/action or ordered §8.1 field set; no action-ID inference is used |
| PG-176 | invalid character, operator, function syntax, quote, escape, comment or lexical token | fixture parser rejects before expansion |
| PG-177 | unknown top-level member, enum, action, result, token, function or request-field identifier | closed-schema validation rejects before tuple derivation |
| PG-178 | duplicate enum, allowed record, BOTH-expanded tuple or top-level member | duplicate detection rejects; no last-writer rule exists |
| PG-179 | `valid-common=false` for each common-precondition stage | first stable common error returns and source-state classification is not invoked |
| PG-180 | one common failure combined with an incompatible operation/mode | common error wins exactly as fixture/prose precedence; `INVALID_OPERATION_MODE` is not returned |
| PG-181 | valid-common compatible snapshot matching none of the nineteen supported predicates | classifier returns reachable `S_UNSUPPORTED`, then only `UNSUPPORTED_SOURCE_STATE` |
| PG-182 | valid-common compatible supported state with no allowed record | only `MODE_SOURCE_STATE_MISMATCH` |
| PG-183 | two independent conforming parsers serialize the literal fixture | identical canonical UTF-8 bytes and identical AST/token registry |
| PG-184 | full fixture cross-product/count assertion | 2 operations, 19 modes, 22 states, 38 pairs, 20 compatible, 22 physical/23 expanded allowed, categories 396/20/23/397 and total 836 |
| PG-185 | PG-62/118/147/148 consume the literal parser, registry and precedence | none constructs missing policy; all yield the same 836 outcomes |
| PG-186 | `conflicting_person_count` is JSON number `0`, positive integer and `9223372036854775807` | validator returns TRUE without exception; valid error outcome commits |
| PG-187 | count is numeric-looking JSON string, `not-a-number`, JSON null, array, object or boolean; metadata is SQL NULL | validator/CHECK returns FALSE, never `22P02`, numeric overflow or SQL UNKNOWN |
| PG-188 | count is negative, fractional or greater than BIGINT max; metadata has an unknown key | validator returns FALSE with no cast exception and no evidence row |
| PG-189 | exact projection-inconsistent `{reason_code,stale_component,conflicting_person_count}` and malformed reason variants | exact matching outcome commits; another outcome and every malformed variant reject |
| PG-190 | call begin-T1 and attempt to commit while row remains `STARTED` with non-NULL marker | deferred guard rereads current row and raises `BOUNDARY_RUN_T1_INCOMPLETE`; marker and transaction roll back |
| PG-191 | crash/rollback after begin or during domain DML | marker/domain/reconciliation/watermark all roll back; expired row is recoverable by one new lease owner |
| PG-192 | live T1 versus recovery/cancellation and two finalizers | run-row plus advisory locks serialize; exactly one terminal result commits; old/recovered owner loses deterministically |
| PG-193 | begin and terminal finalization in one T1, with both deferred trigger events queued | each event rereads final `COMPLETED`; legitimate commit succeeds independently of queued OLD/NEW order |
| PG-194 | attempt `BOUNDARY_RUN_ADVANCED` without matching actual locked after-watermark | finalizer raises `BOUNDARY_RUN_FINALIZATION_CONFLICT`; terminal evidence and all T1 work roll back |
| PG-195 | initial preview has no scope row or a duplicate impossible/corrupt scope mapping | only `ORDER_EVIDENCE_SCOPE_INVALID`; token is not issued |
| PG-196 | initial preview scope has NULL/non-positive generation, malformed typed encoding or orphan membership | only `ORDER_EVIDENCE_SCOPE_INVALID`; digest path performs no repair |
| PG-197 | valid preview then formerly selected scope/order is deleted before apply | locked reread returns only `STALE_EXPECTED_STATE`, never preview structural error |
| PG-198 | valid preview then selected membership or generation changes | only `STALE_EXPECTED_STATE` at the common stale slot; no business DML |
| PG-199 | scope writer rolls back, or apply encounters a committed malformed replacement row representable after bypass/corruption | rollback preserves digest; malformed/drifted apply state returns only `STALE_EXPECTED_STATE` |
| PG-200 | locked future assignment has `start_date>D` but lifecycle `voided` | `NONVOID(T)=FALSE`, `FUT(T)=FALSE`; exact-target non-void common gate returns `ASSIGNMENT_TARGET_VOIDED` before classification and preserve-future is unreachable |
| PG-201 | table/registry/parser evaluation of `CUR(T)`, `NONVOID(T)`, `FUT(T)`, `EVIDENCE_EXACT(T)` over NULL, void, current and future rows | all four definitions agree byte-for-byte; no mode/outcome input is read by a function |
| PG-202 | ADR-048 CREATE branch with null persisted Person target/hash and complete Shell create object | request is valid; object is JCS-bound and Shell is created only by ADR-048 port |
| PG-203 | identical Shell payload and normalization-equivalent Unicode/whitespace input | canonical object bytes, create-intention digest and business digest are identical |
| PG-204 | Shell requests differ only in normalized `full_name` or one optional name | create-intention and business digests differ |
| PG-205 | Shell requests differ only in `birth_date` | create-intention and business digests differ |
| PG-206 | optional name JSON null versus supplied empty/whitespace-only string | null is canonical absence; empty input is rejected and is never normalized to null |
| PG-207 | same caller/context/idempotency key with a different Shell create intention | unique lookup finds prior row and returns `IDEMPOTENCY_KEY_REUSED`; no token parse or second Shell |
| PG-208 | existing-Person LINK branch | persisted target ID/hash are required and `person_shell_create_intention` is exactly null; same request replays |
| PG-209 | request supplies both persisted Person target state and non-null Shell create intention, or neither for a create/link-required mode | `PERSON_TARGET_INTENT_CONFLICT` before operation INSERT; no Person/Employee mutation |
| PG-210 | remove/rename any exact application/photo/PPR/onboarding/notification terminal callable or use `_persist_blocker_durable` | static manifest fails; all application/order/orchestrator production apply entrypoints remain disabled |
| PG-211 | omit or drift any exact application/photo/metadata/lifecycle/onboarding historical revision row | revision/SQL/catalog proof fails closed; production apply remains disabled pending separate migration review |
| PG-212 | custom checklist route/service/repository chain | exact item INSERT; class-12/13 order; retry and rollback evidence |
| PG-213 | complete, skip, onboarding complete and cancel paths | each exact status UPDATE/audit chain has one transition or stable replay/conflict |
| PG-214 | patch task plus bulk assign/due-date dynamic SET branches | every column branch is inventoried, sorted, locked and atomically rolled back |
| PG-215 | application checklist attachment | attachment and task audit commit once or roll back together |
| PG-216 | bulk complete over multiple onboarding/item IDs | numeric deterministic locks; no inversion; notification/audit ordinals covered |
| PG-217 | due-soon and overdue reminder job | both exact notification paths deduplicate and commit in the internal route transaction |
| PG-218 | hard delete clears onboarding mentor/assignee | disabled pre-rollout; migrated form locks references then classes 12/13 |
| PG-219 | hard delete onboarding/application closure | every direct/cascade table through class 15 rolls back together or route remains disabled |
| PG-220 | remove one onboarding writer, caller, disposition or static/runtime/catalog proof | global production apply gate fails closed |
| PG-221 | first ACK SENT for current PENDING attempt | attempt and parent each update once; exact `ONBOARDING_DELIVERY_ACKED`; non-NULL sent time |
| PG-222 | identical terminal ACK replay | no DML; `ONBOARDING_DELIVERY_ACK_REPLAYED`; persisted bytes unchanged |
| PG-223 | SENT then FAILED for the same attempt | `ONBOARDING_DELIVERY_ACK_CONFLICT`; SENT parent remains unchanged |
| PG-224 | identical FAILED ACK replay | no DML; exact replay code and same error |
| PG-225 | begin retry after FAILED then ACK SENT | next attempt alone becomes SENT; parent has NULL error and non-NULL sent time |
| PG-226 | same FAILED attempt, different error/fingerprint | `ONBOARDING_DELIVERY_ACK_CONFLICT`; no overwrite |
| PG-227 | unknown ACK status or invalid SENT/FAILED error shape | exact status/error invalid code before DML |
| PG-228 | missing logical delivery key | `ONBOARDING_DELIVERY_NOT_FOUND`; affected row count zero is not success |
| PG-229 | two concurrent ACKs for one attempt | one affected row; loser exact replay or conflict by fingerprint |
| PG-230 | conditional parent or attempt UPDATE affects zero/one | zero maps conflict, one maps ACKED; no unexamined row count |
| PG-231 | stale attempt while newer attempt is current | `ONBOARDING_DELIVERY_ATTEMPT_STALE`; neither row changes |
| PG-232 | ACK old attempt after newer attempt committed SENT | stale code; new success and sent time remain authoritative |
| PG-233 | normalized full name equals last+first+middle components | CREATE shape accepted; authoritative full name passed unchanged to ADR-048 |
| PG-234 | full name surname conflicts with component surname | only `PERSON_SHELL_FIO_MISMATCH`; no operation INSERT |
| PG-235 | full name given name conflicts with component first name | only `PERSON_SHELL_FIO_MISMATCH`; no Person mutation |
| PG-236 | non-null last/first and null middle | comparison omits middle and accepts exact two-component name |
| PG-237 | supplied empty/whitespace middle | `PERSON_SHELL_FIO_INVALID`, never coerced to null |
| PG-238 | components reordered relative to full name | exact mismatch; implementation never rearranges them |
| PG-239 | equivalent Unicode White_Space runs | one U+0020 normalization gives identical JCS |
| PG-240 | canonically equivalent Unicode spelling | NFC gives identical authoritative name/JCS |
| PG-241 | all three components absent | three JSON null values are accepted with authoritative non-empty full name |
| PG-242 | full name absent/empty or mixed last/first presence | `PERSON_SHELL_FIO_INVALID`; ADR-048 is not invoked |
| PG-243 | same IIN/profile/key | exact domain-separated message, HMAC bytes and lowercase fingerprint repeat |
| PG-244 | different valid IIN under same profile/key | different fingerprint and business digest |
| PG-245 | different profile ID | `IDENTITY_FINGERPRINT_PROFILE_UNSUPPORTED` before mutation |
| PG-246 | key rotation between preview and apply | apply uses token-bound retained old key; business digest is unchanged |
| PG-247 | authorized committed replay after key rotation/destruction | stored matching result returns before token/key validation |
| PG-248 | retired key still inside verification retention | replay miss verifies old preview with that exact key |
| PG-249 | old key unavailable or outside retention on replay miss | exact unknown or retired key code; no recompute with active key |
| PG-250 | malformed fingerprint/profile/key ID | closed-schema validation fails before operation INSERT |
| PG-251 | wrong existing key ID with mismatching HMAC | `IDENTITY_FINGERPRINT_MISMATCH`; no Person lookup/mutation |
| PG-252 | same scoped idempotency key with another actual raw IIN and copied create triple | server-derived replay verifier differs; `IDEMPOTENCY_IDENTITY_INPUT_CONFLICT` precedes digest/result disclosure |
| PG-253 | trusted IIN supplied with punctuation/Unicode digits/whitespace | rejected; exact twelve-ASCII input is the only normalized representation |
| PG-254 | each of nine boundary terminal outcomes with its exact metadata object | finalizer UPDATE and table CHECK accept every listed positive branch |
| PG-255 | missing required outcome metadata key | finalizer returns `BOUNDARY_RUN_METADATA_INVALID`; evidence remains STARTED/rolled back |
| PG-256 | extra allowlisted key or key belonging to another outcome | outcome-aware function and table CHECK reject it |
| PG-257 | SQL NULL, JSON null, wrong type, invalid component enum or invalid count range | no cast exception/UNKNOWN; exact metadata-invalid result |
| PG-258 | `BOUNDARY_RUN_ADVANCED` or `BOUNDARY_RUN_DUPLICATE` with non-empty metadata | rejected; exact empty object alone commits |
| PG-259 | `BOUNDARY_RUN_CANCELLED` with exact reason versus any additional/key/value variant | exact reason commits; every variant rejects |
| PG-260 | direct table INSERT/UPDATE bypass attempt for every positive/negative metadata fixture | table CHECK independently accepts/rejects exactly like finalizer helper |
| PG-261 | metadata failure after domain work in T1 | finalizer exception rolls back domain, reconciliation, watermark and evidence together |
| PG-262 | begin marker and terminal finalization in one T1 | current row commits terminal; both deferred events reread terminal state |
| PG-263 | marker-only commit | deferred guard raises `BOUNDARY_RUN_T1_INCOMPLETE`; marker rolls back |
| PG-264 | another transaction inspects/finalizes during live T1 | it cannot see uncommitted marker and waits on row; no terminal mutation |
| PG-265 | another transaction after first T1 rollback | sees NULL marker; finalizer fails, recovery may acquire only by lease rules |
| PG-266 | two transactions have artificially equal transaction timestamps | equality grants no authority; MVCC/owner/marker/row lock still decide |
| PG-267 | stale lease owner calls finalizer | conditional UPDATE affects zero and returns `BOUNDARY_RUN_FINALIZATION_CONFLICT` |
| PG-268 | recovery after marker/domain rollback | new owner records one recovery then may begin a fresh atomic T1 |
| PG-269 | finalizer without marker | zero rows and exact finalization conflict; no terminal evidence |
| PG-270 | finalizer after terminal result | immutable stored result; conflicting finalization cannot update it |
| PG-271 | two concurrent finalizers | row lock plus conditional status/owner predicate permits one terminal result only |
| PG-272 | legacy delivery migration | exact immediate-system SENT shape gets `sent_at=created_at` and one legacy attempt; every other invalid legacy shape blocks before DDL |
| PG-273 | every positive boundary outcome/metadata pair through `finalize_person_assignment_boundary_run` | valid JSONB reaches conditional UPDATE and independent table CHECK; terminal row commits |
| PG-274 | base-valid metadata belonging to another outcome | finalizer returns `BOUNDARY_RUN_METADATA_INVALID`; direct table INSERT/UPDATE is rejected by independent `chk_pabr_error_outcome` |
| PG-275 | SQL NULL, JSON null, unknown/extra key, invalid enum and numeric boundary variants through actual table DML | CHECK returns false without `22P02`, UNKNOWN acceptance or partial terminal evidence |
| PG-276 | all literal fixed metadata objects | PostgreSQL parses every `jsonb_build_object` branch and persisted outcome vocabulary matches table/finalizer exactly |
| PG-277 | T0 through `claim_person_assignment_boundary_run` | exact STARTED shape commits once and returns `BOUNDARY_RUN_CLAIMED` |
| PG-278 | runtime role attempts direct exact-shape STARTED INSERT | ACL rejects; function remains the only production claim path |
| PG-279 | runtime role attempts direct COMPLETED/success or error INSERT | ACL and insert-shape trigger independently reject; no fake evidence |
| PG-280 | owner invokes direct terminal INSERT during production-enabled state | startup/catalog gate disables all entrypoints and reports owner bypass; production path cannot proceed |
| PG-281 | forged STARTED insert with `t1_started_at`, outcome, completion or watermark | insert-shape trigger rejects every variant |
| PG-282 | forged retry root/child columns | retry-lineage and insert-shape guards reject inconsistent root, target, context or ordinal |
| PG-283 | same scheduler UUID replay through claim function | exact correlation returns claim/result replay; changed target/context returns `BOUNDARY_RUN_CORRELATION_REUSED` |
| PG-284 | migration owner installs objects | only migration window with runtime entrypoints disabled permits owner DDL/DML; catalog ACL preflight must pass before enablement |
| PG-285 | privilege catalog verification | runtime has SELECT/EXECUTE only; any table DML grant, public EXECUTE, missing trigger/function owner or changed definition blocks rollout |
| PG-286 | candidate intended-employment API and hire sync call chains | manifest resolves `save_intended_employment` to exact metadata UPDATE, locks and caller transaction |
| PG-287 | additional-profile transfer chain | manifest resolves `save_person_additional_profile` UPSERT despite read-module path and exercises INSERT/UPDATE rollback |
| PG-288 | cancel/expire/resolution lifecycle paths | each exact callable and terminal application/link/audit DML has its own row, ordered lock and migrate/disable proof |
| PG-289 | three personnel-intake transition helpers | each module-qualified callable maps to its own UPDATE and complete incoming call graph; one missing edge blocks all apply |
| PG-290 | `_transfer_general_and_contacts` | production route remains disabled until ADR-048-approved Person mutation replaces direct UPDATE; no partial application/contact result |
| PG-291 | seed/demo envelope and `_delete_person_demo_data` | signed production package/command deny-list plus catalog graph prevents execute/rollback writers; dry-run remains read-only |
| PG-292 | worker claim returns one current attempt | result includes exact `attempt_no`, owner and lease; parent/current projection is locked and consistent |
| PG-293 | two concurrent retry creators with same fingerprint | one next attempt commits and loser returns `ONBOARDING_DELIVERY_RETRY_REPLAYED`; no duplicate attempt number |
| PG-294 | two concurrent retry creators with different fingerprints | one commits and loser returns `ONBOARDING_DELIVERY_RETRY_CONFLICT`; parent points to the single new attempt |
| PG-295 | two concurrent ACKs | one terminal pair transition; loser is exact replay or conflict and cannot change parent |
| PG-296 | old ACK after newer attempt or newer success | `ONBOARDING_DELIVERY_ATTEMPT_STALE`; no old result overwrites current projection |
| PG-297 | FAILED retry and duplicate retry request | first produces next PENDING attempt; identical request replays; different request conflicts |
| PG-298 | SENT then FAILED request or FAILED with another error | `ONBOARDING_DELIVERY_ACK_CONFLICT`; `FAILED AND sent_at IS NOT NULL` is never committed |
| PG-299 | crash after attempt UPDATE but before parent UPDATE | one function transaction rolls both back; retry sees original PENDING pair |
| PG-300 | parent/current-attempt projection drift | claim/ACK/retry returns `ONBOARDING_DELIVERY_PROJECTION_INCONSISTENT`; authorized repair locks and audits exact projection |
| PG-301 | current attempt at BIGINT maximum | retry returns `ONBOARDING_DELIVERY_ATTEMPT_EXHAUSTED` before addition or INSERT |
| PG-302 | unknown provider error or affected row count zero/more than one | closed error validation or projection conflict aborts both rows |
| PG-303 | current incompatible ACK route/reader/worker enabled before target migration | static/runtime/catalog rollout proof fails and all related entrypoints remain disabled |
| PG-304 | identical retry of custom item, attachment and task audit INSERT | each unique scope/key row is selected and exact digest returns `ONBOARDING_INSERT_REPLAYED` |
| PG-305 | same persisted key with different request digest for each INSERT writer | `ONBOARDING_INSERT_IDEMPOTENCY_REUSED`; no second business/audit row |
| PG-306 | concurrent identical/conflicting INSERT retries | named unique index elects one owner; loser deterministically replays or conflicts |
| PG-307 | unknown commit for each INSERT writer | authoritative unique-key reread recovers committed row or returns `ONBOARDING_INSERT_COMMIT_UNKNOWN`; no blind second INSERT |
| PG-308 | committed CREATE replay with the same actual raw IIN | stored binding key recomputes equal verifier before exact stored result release |
| PG-309 | committed replay with different raw IIN but copied fingerprint/object | verifier mismatch returns `IDEMPOTENCY_IDENTITY_INPUT_CONFLICT`; no result metadata leaks |
| PG-310 | different raw IIN and different create object under same scoped key | identity binding check precedes and rejects; it is not inferred solely from business digest |
| PG-311 | operational fingerprint rotation/retirement/destruction before committed replay | independent retained idempotency binding still verifies actual IIN and permits matching replay |
| PG-312 | binding key rotated to verification-only | existing operation recomputes with stored key; new operation uses active key |
| PG-313 | binding key revoked or unavailable | exact `IDEMPOTENCY_IDENTITY_BINDING_KEY_REVOKED` or `IDEMPOTENCY_IDENTITY_BINDING_KEY_UNAVAILABLE`; result is not released |
| PG-314 | copied key across caller/context | scoped lookup cannot select the row; no verifier/result disclosure |
| PG-315 | raw-IIN leakage scan | token, digests, operation payload, result, audit, event, metadata and logs contain only approved HMAC values and identifiers |
| PG-316 | SCHEDULED operational key | preview/apply rejects `IDENTITY_FINGERPRINT_KEY_NOT_YET_VALID`; no creation or verification |
| PG-317 | ACTIVE then VERIFICATION_ONLY rotation | new preview uses new ACTIVE; issued preview verifies with retained old key and unchanged digest |
| PG-318 | emergency REVOKED operational key | unexpired preview/replay miss returns `IDENTITY_FINGERPRINT_KEY_REVOKED`; no silent re-key |
| PG-319 | DESTROYED operational key on replay miss | exact `IDENTITY_FINGERPRINT_KEY_DESTROYED`; committed replay still depends only on R39 binding |
| PG-320 | ordinary destruction with unexpired token/nonterminal reference | key authority rejects transition; retention invariant remains true |
| PG-321 | unknown key ID versus retired verification window | exact distinct `IDENTITY_FINGERPRINT_KEY_UNKNOWN`/`IDENTITY_FINGERPRINT_KEY_RETIRED` |
| PG-322 | revoked binding key versus operational key | separate purpose/profile produces separate stable code and never cross-verifies secrets |
| PG-323 | every scalar in closed Unicode 15.1 whitespace set | versioned vector normalizes `A<scalar>B` to exact `A B` |
| PG-324 | U+00A0, U+202F, U+2003 and U+3000 FIO vectors | each produces byte-identical normalized FIO/JCS |
| PG-325 | decomposed acute versus precomposed NFC | both produce the same Unicode-15.1 NFC bytes and business digest |
| PG-326 | punctuation, hyphen and case variants | preserved distinctions produce distinct canonical intentions where bytes differ |
| PG-327 | unknown FIO normalization profile | `PERSON_SHELL_FIO_PROFILE_UNSUPPORTED` before idempotency INSERT/ADR-048 invocation |
| PG-328 | runtime Unicode library upgrade | fixed code-point table/vectors keep canonical output unchanged; library property drift cannot alter digest |
| PG-329 | simultaneous assignment/link/Employee duplicate drift | component precedence selects assignment while count is union of distinct affected Persons |
| PG-330 | only link and Employee drift | component is assignment_link and union count is stable under randomized row/query order |
| PG-331 | invalid successor chain with multiple overlap/branch/replacement causes | count is distinct participating non-void primary assignment IDs, never raw joined-row count |
| PG-332 | active-primary conflict with duplicate join rows | count is distinct eligible primary assignment IDs for the one Person and is at least two |
| PG-333 | repeated metadata derivation under different plans/orderings | canonical object, audit payload and finalizer input are byte-identical |
| PG-334 | SCHEDULED replay-binding key or new binding under VERIFICATION_ONLY key | exact not-yet-valid code for scheduled verification; only ACTIVE creates, while retained VERIFICATION_ONLY verifies existing rows |
| PG-335 | composite P0 with existing Employee, NULL Person link, no compatible Person, no primary, complete confirmed intent and provenance | one Shell, link, verified IIN, C2 assignment, reconciliation, exact P0 event/audit bundle and provenance commit with `EMPLOYEE_PERSON_AND_ASSIGNMENT_REPAIRED` |
| PG-336 | composite P1 with exactly one compatible Person and no non-VOID primary | existing Person is adopted unchanged; no new Person; link, IIN verification, C2 assignment, reconciliation, exact P1 event/audit bundle and provenance commit atomically |
| PG-337 | execute the exact §10.1 composite PG↔FI table for P0 and P1, with a separate injected transaction after every applicable physical statement ordinal, including Shell, link, identity validation/write, C2 assignment/provenance/link, reconciliation, branch events, audit, each import binding/propagation/metadata statement, Contact and result finalization | every injection fully rolls back to the original committed state; retry with the same key/request starts fresh; P0 Shell disappears, P1 is unchanged, Employee remains unlinked, and no assignment, projection, event/audit, provenance/binding, Contact or result survives |
| PG-338 | exact same composite request after successful commit | stored success is returned with `replayed=true`; no port or writer runs and row/event counts do not change |
| PG-339 | P1 Person/IIN mismatch, Employee identity collision, ambiguous candidate, or Person already having any non-VOID primary | exact identity/ambiguity/assignment conflict before business DML; no fallback to P0, `LINK_ONLY`, or `OPEN_MISSING_ASSIGNMENT` |
| PG-340 | any one of org unit, position, rate, employment type, primary flag, start date, evidence admissibility, reason, verifier, or confirmation time absent/unconfirmed | `ASSIGNMENT_INTENT_INCOMPLETE`; zero business DML and no Person link |
| PG-341 | any bound Employee/link/identity/candidate/assignment/reference/evidence/watermark/import state changes after preview | `STALE_EXPECTED_STATE` before first business DML |
| PG-342 | import row or normalized payload contains plausible org, position, rate, or date but operator omitted a confirmation | inference is prohibited; `ASSIGNMENT_INTENT_INCOMPLETE`; no link or assignment |
| PG-343 | Employee projection, HIRE event, or personnel order contains plausible assignment data but separate operator confirmation is absent | inference is prohibited; no composite selection and zero business DML |
| PG-344 | Makibaeva fixture exposes `employees.date_from=2026-07-02` and order №125-к-associated `2026-07-10` | neither date is selected; apply remains blocked until start date and order admissibility as evidence are separately confirmed |
| PG-345 | P0 operation row has `P0_CREATE`; insert exact composite `PERSON_SHELL_CREATED` then `EMPLOYEE_PERSON_LINKED` rows through actual §11.1 CHECK and trigger | both DDL writes pass with their exact mode, references and outcome codes; the full composite may commit only after every later postcondition |
| PG-346 | P0 operation row with P1 code, wrong mode, reversed event/reference ownership, or a prohibited personnel event shape | each variant is rejected by operation CHECK, event CHECK or `PERSONNEL_EVENT_MODE_RESOLUTION_MISMATCH`; no partial event bundle commits |
| PG-347 | P1 operation row has `P1_ADOPT`; insert exact composite `EMPLOYEE_PERSON_LINKED` through actual §11.1 CHECK and trigger | link event passes; no Shell event is required or emitted; all later composite outcomes remain mandatory |
| PG-348 | P1 operation attempts `PERSON_SHELL_CREATED`, uses P0 code, wrong mode, or mismatched Employee/Person reference | each variant is rejected by operation/event CHECK or locked trigger and the entire transaction rolls back |
| PG-349 | independent fixture-side `adr065-po-evidence` v1 vector | fixture code does not call production helper; exact column frames, four sorted collections, outer JCS bytes and final HMAC match |
| PG-350 | mutate each of the four collections; use another order/item/scope/profile/version/key and randomized physical row order | each semantic mutation changes or blocks the fingerprint; row-order permutation is stable; no cross-context fingerprint verifies |
| PG-351 | ACTIVE/VERIFICATION_ONLY rotation plus unknown/scheduled/revoked/destroyed/unavailable key and unequal HMAC | exact §6.1 status; mismatch differs from unverifiable; retained old key verifies without fallback; constant-time comparison path is exercised |
| PG-352 | protected-value and raw-IIN leakage scan across success/error/SQL/application logs | no secret, protected raw order value, full IIN, SQL bind or request payload appears |
| PG-353 | every §6.2 reason with its allowed row; unknown code, arbitrary text, technical metadata, cross-mode code, and mode-as-reason | positives pass compatibility; every prohibited combination returns the exact reason error and no classification success |
| PG-354 | absent watermark schema, invalid cardinality/shape, stale, current and future row | exact §5.1 code; only `effective_date=D` permits continuation; every other state has NULL classification/mode/outcome |
| PG-355 | `start_date` before/equal/after `D`; future watermark present | before/equal pass OPEN_START_DATE when otherwise valid; after fails; future watermark never expands the window |
| PG-356 | migration/readiness proof and successful EXTERNAL_REFERENCE/PERSONNEL_ORDER preflight fixtures | ad hoc test DDL never satisfies production readiness; reviewed schema/current writer/key ring permit one normative path of each evidence type with `apply_available=false` |

There are exactly twenty-one FI types and three hundred fifty-six sequential PG IDs. The FI mapping is
the exact mapping in §10.1; PG-14/74/75 iterate every concrete statement ordinal. Combining
physical fault boundaries does not satisfy this ADR.

---

## 15. Review traceability

| Finding | Section | Decision | Invariant | Scenarios |
|---|---|---|---|---|
| AR065-R1 | §7.1, §9.1–§9.5 | concrete HR/order/application/photo/PPR plus every checklist/task/bulk/reminder/cleanup terminal callable; independent static/runtime/catalog fail-closed evidence | ORCH-9 | PG-18–19,120,122–129,149–155,210–220,286–291 |
| AR065-R2 | §5.1–§5.3, §9.1–§9.2 | exact singleton/T0/T1; outcome-aware metadata matrix; deferred MVCC/row-lock commit guard; durable duplicate/cancel/recovery/retry | ORCH-10–11,37 | PG-25–32,65–66,76–80,101,130–137,156–166,186–194,254–271 |
| AR065-R3 | §4, §2 protocol table | literal JCS; complete immutable episode-definition trigger state machine; atomic replacement and single loser code | ORCH-12,38 | PG-20–24,65,81–86,102–106,138–146 |
| AR065-R4 | §10–§10.1 | twenty-one FI types; every physical binding/normalized/metadata statement ordinal receives its own injected transaction, including the static composite P0/P1 expansions | ORCH-5–8 | PG-01–17,67–70,72–75,100,337 |
| AR065-R5 | §3.2 | strict fail-fast C2; no fallback | ORCH-13–14 | PG-33–36 |
| AR065-R6 | §3.3 | caller-tx reconciliation | ORCH-15 | `PG-37` |
| AR065-R7 | §8.1–§8.2 | exact INSERT/conflict/retry machine | ORCH-22–25 | PG-38–42 |
| AR065-R8 | §2, §8.1, §8.3, §9.1 | persisted Person hash separated from exact FIO-validated Shell intention; actual raw identity input is server-bound before committed result release | ORCH-22–25,39 | PG-38–44,87–90,107–111,202–209,233–253,308–322 |
| AR065-R9 | §7.2 | exact UTC seconds, TTL/skew operators, retired-key window and rotation boundaries | ORCH-20 | PG-44–51 |
| AR065-R10 | §5.1, §7.1, §9.1–§9.2, §10 | finite top-level closure; initial invalid scope is distinct from any post-preview apply drift; full locked reread before first business DML | ORCH-19–21,40 | PG-30–31,52–54,76–80,111,117,121–129,167–173,195–199 |
| AR065-R11 | §11.1, §11.3 | NULL-safe event DDL; non-deferrable locked reference trigger and reciprocal Employee/assignment guards | ORCH-30–31,34,41 | PG-61,65–66,91–95,112–116 |
| AR065-R12 | §11.2 | strict success audit; separate attempts/replay | ORCH-26–27 | PG-13,69–71 |
| AR065-R13 | §2, §5.2, §5.4 | temporal start identity separated from unchanged business delta; exact continuous predecessor/successor dates | ORCH-28–30,36,42 | PG-55–61,96–98,119 |
| AR065-R14 | §2, §5.4, §8.1 | executable v1 BNF, closed semantic/input registry including static composite P0/P1 records and the exact Person create triple, common precedence and literal 396/20/23/397 fixture | ORCH-16–18,32,35–36 | PG-20–24,38–43,62–64,96–99,118,147–148,174–185,200–209,233–253,335–348 |
| AR065-R15 | §2, §7.1, §8.1, §9.2, §12.1–§12.3 | factual ID/name-only schema; preview mismatch versus locked rename; both digests; values remain unconfirmed | ORCH-33 | PG-53–54,63–64,99 |
| AR065-R16 | §7.1, §9.1–§9.5, §10 | persisted per-order scope plus complete application/onboarding writer closure, deterministic locks and global rollout blocker | ORCH-9,19–21,40 | PG-121–129,149–155,167–173,210–220 |
| AR065-R17 | §5.1, §9.3.1, §14 | one boundary and delivery stable-code vocabulary; no semantic shorthand remains in PG | ORCH-10–11 | PG-76–80,101,130–137,258–259,292–303 |
| AR065-R18 | §5.1 | type-safe outcome metadata, immutable evidence, MVCC/row-lock/deferred same-T1 guard, recovery/cancellation and privilege gate | ORCH-10–11,37 | PG-130–137,156–166,186–194,254–271 |
| AR065-R19 | §2, §8.1 | complete BNF/registry, exact FIO/fingerprint Shell input bundle, canonical serializer and common precedence | ORCH-16–18,32,35–36 | PG-62,118,147–148,174–185,200–209,233–253 |
| AR065-R20 | §9.3–§9.5 | exact application/reverse/photo/PPR plus checklist/task/bulk/reminder/cleanup/ACK identities with three independent proofs | ORCH-9 | PG-149–155,210–232 |
| AR065-R21 | §7.1, §9.1–§9.2 | exact top-level scope-generation member; initial structural error versus apply drift; canonical preview/apply encoding | ORCH-19–21,40 | PG-167–173,195–199 |
| AR065-R22 | §9.3–§9.5 | every application/photo/onboarding/checklist/notification terminal repository callable and migration is separately manifest-matchable | ORCH-9 | PG-149–155,210–232 |
| AR065-R23 | §5.1 | type-safe base validator plus exhaustive outcome-aware PL/pgSQL function and independent table CHECK | ORCH-10–11,37 | PG-159–160,186–189,254–261,273–276 |
| AR065-R24 | §5.1 | deferred current-row guard plus MVCC visibility, run-row ownership and non-NULL marker make all T1 writes atomic; timestamp is observability only | ORCH-10–11,37 | PG-158,161–164,190–194,262–271 |
| AR065-R25 | §2, §7.1, §9.1–§9.2 | initial malformed/missing scope returns `ORDER_EVIDENCE_SCOPE_INVALID`; every difference after valid preview returns only `STALE_EXPECTED_STATE` | ORCH-19–21,40 | PG-170–173,195–199 |
| AR065-R26 | §2 fixture/classifier registry | `FUT(T)` is exactly locked non-void, non-NULL `start_date>D`; void future target cannot enter preserve state | ORCH-16–18,32 | PG-174,200–201 |
| AR065-R27 | §2, §8.1–§8.3 | exact FIO-consistent, versioned-HMAC ADR-048 Shell create object remains separate and is included whole in trusted business JCS | ORCH-22–25,39 | PG-202–209,233–253 |
| AR065-R28 | §9.2–§9.5 | exact repository/service/route/job/bulk/attachment/reminder/hard-delete onboarding closure, classes 12–15 and three-proof fail-closed disposition | ORCH-9 | PG-212–220 |
| AR065-R29 | §9.3.1 | current ACK disabled; logical delivery plus immutable attempt identity, deterministic legacy backfill, conditional ACK/replay/conflict/stale/retry | ORCH-9 | PG-221–232,272 |
| AR065-R30 | §8.1 | authoritative normalized full name; exact optional component shapes/composition; mismatch/invalid codes before ADR-048 | ORCH-22–25,39 | PG-233–242 |
| AR065-R31 | §8.1–§8.3 | domain-separated versioned HMAC profile/key triple, rotation retention and replay-before-key-validation contract | ORCH-22–25,39 | PG-243–253 |
| AR065-R32 | §5.1 | exhaustive outcome-to-metadata matrix enforced both by finalizer and table CHECK | ORCH-10–11,37 | PG-254–261 |
| AR065-R33 | §5.1 | timestamp is observability; same T1 is enforced by uncommitted marker visibility, row lock and deferred current-row guard | ORCH-10–11,37 | PG-262–271 |
| AR065-R34 | §5.1 | every fixed JSONB value uses executable `jsonb_build_object`; finalizer and independent CHECK share the exact persisted-code matrix | ORCH-10–11,37 | PG-273–276 |
| AR065-R35 | §5.1 | exact-shape `SECURITY DEFINER` T0 claim, insert guard and SELECT/EXECUTE-only runtime ACL prevent direct terminal/marker evidence | ORCH-10–11,37 | PG-277–285 |
| AR065-R36 | §9.3–§9.5 | separately matchable candidate/additional/lifecycle/intake/transfer/seed/demo/delete callables and terminal DML closure | ORCH-9 | PG-286–291 |
| AR065-R37 | §9.3.1 | literal claim/ACK/retry functions, immutable attempt identity, atomic parent projection, closed errors and disabled legacy path | ORCH-9 | PG-292–303 |
| AR065-R38 | §9.3.2 | persisted scoped key/digest uniqueness and authoritative reread for custom item, attachment and task-audit INSERT retries | ORCH-9 | PG-304–307 |
| AR065-R39 | §2, §8.1–§8.3 | independent retained HMAC verifier derived from actual raw IIN and caller/context/key scope precedes committed result release | ORCH-22–25,39 | PG-308–315 |
| AR065-R40 | §8.1 | closed operational/binding key states, transitions, retention, revocation/destruction behavior and distinct stable codes | ORCH-22–25,39 | PG-311–322,334 |
| AR065-R41 | §8.1 | immutable Unicode-15.1 NFC/closed-whitespace FIO profile and complete non-secret normalization vectors | ORCH-22–25,39 | PG-323–328 |
| AR065-R42 | §5.1 | query-plan-independent distinct-ID counting and deterministic component precedence derive every persisted metadata value | ORCH-10–11,37 | PG-329–333 |

### 15.1. R11 composite Architecture Re-Review disposition

The finding labels in this subsection are scoped to the R11 composite re-review request;
they do not renumber or replace the historical finding rows above that used the same
short labels in earlier review cycles.

| Composite finding | Severity | Resolution in R12 | Status |
|---|---|---|---|
| AR065-R5 | CRITICAL | §§2.1/5.4/11.1 permit exact composite P0 shell+link and P1 link events; operation resolution CHECK plus locked event guard rejects wrong branch/mode; PG-345–348 exercise positive/negative DDL | `RESOLVED — PENDING ARCHITECTURE RE-REVIEW CONFIRMATION` |
| AR065-R6 | HIGH | §2 fixture has separate static, disjoint P0/P1 predicates, action IDs, required-input sets and literal event lists; no conditional field or event macro remains | `RESOLVED — PENDING ARCHITECTURE RE-REVIEW CONFIRMATION` |
| AR065-R7 | HIGH | §§2.1/8.1/8.2 exclude generated `operation_id` from digest, bind `correlation_id`, create the operation row after request completeness, then persist the returned ID only as FK/provenance | `RESOLVED — PENDING ARCHITECTURE RE-REVIEW CONFIRMATION` |
| AR065-R8 | MEDIUM | §7.1 covers exactly twenty-one non-unsupported predicates and explicitly closes candidate/resolution, Employee/link/IIN, assignment-scope and import expected state for P0/P1 | `RESOLVED — PENDING ARCHITECTURE RE-REVIEW CONFIRMATION` |
| AR065-R9 | MEDIUM | `REQUEST_COMPLETENESS` places exact `ASSIGNMENT_INTENT_INCOMPLETE` before operation INSERT; §6 defines eight separate operator decisions and prohibited inference | `RESOLVED — PENDING ARCHITECTURE RE-REVIEW CONFIRMATION` |
| AR065-R10 | MEDIUM | §10.1 maps PG-337 across every applicable FI and physical ordinal for P0/P1, including Contact, separate import metadata and finalization, with fresh retry from the original committed state | `RESOLVED — PENDING ARCHITECTURE RE-REVIEW CONFIRMATION` |

Regression disposition for the previously closed AR065-R1–R4 is `NOT REOPENED`:
R1 gains no writer or bypass and remains under the same §9 inventory/rollout gate; R2
retains the same serialized assignment uniqueness/timeline guarantees; R3 retains literal
JCS, immutable provenance and C2-only adoption while the two fixture rows are now static;
R4 now explicitly includes PG-337 in the exact FI mapping rather than relying on a grouped
composite assertion.

### 15.2. R13 backend-preview blocker disposition

| Review blocker | Normative decision | Draft status |
|---|---|---|
| PERSONNEL_ORDER fingerprint underdetermined | §6.1 exact profile, byte framing, four collections, outer envelope, KMS/key rotation and stable failures | `RESOLVED IN DRAFT — PENDING ARCHITECTURE REVIEW` |
| operator reason vocabulary absent | §6.2 closed business codes and state/mode compatibility; mode placeholder rejected | `RESOLVED IN DRAFT — PENDING ARCHITECTURE REVIEW` |
| stale/future watermark ambiguity | §5.1 computes fixed-offset `D`; only equality is current; stale/future fail closed | `RESOLVED IN DRAFT — PENDING ARCHITECTURE REVIEW` |
| watermark table absent from migration history | §5.1/§11.3/§17 make a separate reviewed migration and C2 readiness mandatory | `RESOLVED IN DRAFT — PENDING ARCHITECTURE REVIEW` |

---

## 16. Parent compatibility

| Parent rule | Preserved | Addition |
|---|---|---|
| ADR-048 Person authority | only ADR-048 port creates/links Person | transaction/locks |
| ADR-048 INV-4 | successful active enrollment cannot retain NULL Person | atomic chain |
| ADR-048 INV-11 | Shell command creates no assignment; C2 needs separate intent/evidence/date | composite orchestration |
| ADR-043 C2 authority | all assignment mutation/adoption uses C2 primitives | strict caller-tx port |
| C1 canonical event origin | no synthetic canonical snapshots/events | separate application provenance |
| ADR-042 secondary assignments | unique predicate targets current active primary only | hard guarantee/timeline validation |

No parent invariant is weakened. If shared C2 primitives cannot support this strict port
without changing ADR-043 authority, implementation stops with
`BLOCKED — PARENT ARCHITECTURE CHANGE REQUIRED`; it must not create another writer.

## 17. Gates and non-goals

At R13, implementation readiness was not yet asserted; the next gate was an external
Architecture Review of exactly four decisions: §6.1 fingerprint profile/key infrastructure,
§6.2 reason vocabulary, §5.1 current-watermark rule, and the watermark migration
dependency. That subsequent review closed the gate. The current R14 verdict is
`Approved — Ready for Implementation`; `READY FOR IMPLEMENTATION: YES`. The approved
implementation package may add the reviewed watermark migration and align the backend
preflight. That package must prove
the KMS profile/key readiness, exact controlled reasons, current watermark at `D`,
fail-closed absent/stale/future states, and no ad hoc-test-DDL dependency. A final
read-only backend review must pass before any frontend slice is started.

Apply remains disabled until: Architecture Re-Review passes; migration design is reviewed;
all §9 writers migrate/disable; strict ports reuse authority; unique-index preflight/index
complete; all §14 tests pass; production and first-batch facts receive separate approval.

This ADR does not choose real dates, identity matches, positions, org units, evidence, or
modes for Makibaeva/Oserova; model absence/acting duty; authorize rehire/Person merge;
create migrations/code/tests/production commands/data; or make orchestration/reconciliation
a second personnel-history authority.

## 18. History

| Revision | Date | Change |
|---|---|---|
| R1 | 2026-08-07 | Initial orchestration decision for Architecture Review. |
| R2 | 2026-08-08 | First revision after review; retained unresolved precision and completeness findings. |
| R3 | 2026-08-08 | Architecture-only revision addressing AR065-R1, R2, R3, R4, R8, R9, R11, R13, R14, and R15 with exact writer, state, DDL, replay, time, outcome, position, and PG contracts; status remains `Draft — Ready for Architecture Re-Review`. |
| R4 | 2026-08-08 | Second re-review revision: concrete writer callsites/gates; serialized singleton watermark; valid JCS and separate application origin; 21 FI/100 PG; expanded request/state digests; NULL-safe events; complete 720-tuple outcome rule and deterministic current/future change modes; status remains `Draft — Ready for Architecture Re-Review`. |
| R5 | 2026-08-08 | Third re-review revision: completed discovered writer/CLI/migration baseline; duplicate inconsistency outcome; immutable application provenance; caller-context idempotency; closed whole-row preview lock pass; reciprocal event coupling guards; formal state predicates/total 720-tuple function; corrected successor temporal identity; 21 FI types/121 PG scenarios. Status remains `Draft — Ready for Architecture Re-Review`; no implementation readiness is asserted. |
| R6 | 2026-08-08 | Fourth re-review correction: completed personnel-order evidence writers; phantom-safe persisted scope lock; durable boundary-run claim/finalize evidence; closed application episode transition trigger and replacement conflict mapping; finite locked state closure; literal 720-tuple fixture with unambiguous unsupported precedence; normalized boundary codes; 21 FI types/148 PG scenarios. Status remains `Draft — Ready for Architecture Re-Review`; findings are not declared closed and implementation readiness is not asserted. |
| R7 | 2026-08-08 | Fifth re-review correction: added the complete application-apply/reverse-hook/photo/onboarding inventory closure; made boundary evidence lease-backed, NULL-safe, immutable and conditionally finalized with recovery/cancellation/retry lineage; placed scope generation in the literal preview object; replaced the incomplete outcome grammar with executable schema-directed BNF and a closed token registry/common precedence; retained 720 tuple counts and expanded to 21 FI types/185 PG scenarios. Status remains `Draft — Ready for Architecture Re-Review`; `READY FOR IMPLEMENTATION: NO`; findings are not declared closed. |
| R8 | 2026-08-08 | Sixth re-review correction: replaced approximate application/photo/onboarding identities with exact terminal callables and migration rows; added type-safe boundary metadata validation and a deferred incomplete-T1 commit guard; separated preview scope invalidity from apply drift; unified non-void `FUT(T)` semantics; separated the persisted Person hash from an exact ADR-048 Shell create-intention object in the business digest; retained 720 tuple counts and 21 FI types, expanded to 211 PG scenarios. Status remains `Draft — Ready for Architecture Re-Review`; `READY FOR IMPLEMENTATION: NO`; findings are not declared closed. |
| R9 | 2026-08-08 | Seventh re-review correction: completed checklist/task/bulk/reminder/hard-delete writer baseline; replaced the non-idempotent ACK claim with a disabled-until-migrated delivery-attempt state machine; fixed authoritative FIO composition and a versioned domain-separated IIN fingerprint profile; added outcome-specific boundary metadata enforcement; replaced timestamp identity claims with MVCC/row-lock/deferred-guard proof; retained 720 tuple counts and 21 FI types, expanded to 272 PG scenarios. Status remains `Draft — Ready for Architecture Re-Review`; `READY FOR IMPLEMENTATION: NO`; findings are not declared closed. |
| R10 | 2026-08-08 | Eighth re-review correction: made boundary metadata literals executable and direct terminal evidence impossible for runtime roles; completed newly found callable writers; closed delivery-attempt claim/ACK/retry and persisted onboarding INSERT retry identity; bound committed replay to the actual raw IIN with a separately retained verifier; defined operational-key revocation/destruction, Unicode-15.1 FIO normalization and deterministic metadata derivation; corrected stable-code shorthand; retained 720 tuple counts and 21 FI types, expanded to 334 PG scenarios. Status remains `Draft — Ready for Architecture Re-Review`; `READY FOR IMPLEMENTATION: NO`; findings are not declared closed. |
| PAUSED | 2026-08-08 | ADR-065 moved to `PAUSED AS A WHOLE — REFERENCE-ONLY` by decision of the project owner. The general review cycle is stopped; the document is retained for selective verification and local updating within future narrow personnel work. All unclosed findings remain unclosed. |
| R11 | 2026-08-09 | Added the distinct atomic `LINK_AND_OPEN_MISSING_ASSIGNMENT` existing-card repair outcome for P0/P1, explicit operator-confirmed assignment intent, expected-state/locks/idempotency/provenance/event/rollback contracts, and PG-335–344. Corrected the Makibaeva acceptance fixture to `employee_id=138` and retained date/evidence confirmation as unresolved. Status is `Draft — Ready for Architecture Re-Review`; `READY FOR IMPLEMENTATION: NO`. |
| R12 | 2026-08-09 | Resolved composite re-review AR065-R5–R10: aligned §5.4/§11.1 event DDL and P0/P1 mode checks; replaced the conditional composite fixture with two static predicates/records; removed generated `operation_id` from digest inputs and bound correlation; completed §7 expected state and §6 request completeness; mapped PG-337 to all composite FI boundaries; added PG-345–348. Fixture is 2 operations × 19 modes × 22 states = 836 tuples, with 21 non-unsupported predicates, 22 physical/23 expanded allowed records and counts 396/20/23/397. Status remains `Draft — Ready for Architecture Re-Review`; `READY FOR IMPLEMENTATION: NO`. |
| R13 | 2026-08-09 | Compact architecture-blocker closure: defined byte-level `adr065-po-evidence` v1 HMAC profile and rotation/error contract; added closed operator `reason_code` vocabulary; made only `effective_date=D` current and future watermark fail-closed; recorded the absent watermark migration as a mandatory deployment dependency; added PG-349–356 and retained the Architecture Review gate. Status remains `Draft — Ready for Architecture Re-Review`; `READY FOR IMPLEMENTATION: NO`. |
| R14 | 2026-08-09 | Final scoped Architecture Review approved the PERSONNEL_ORDER fingerprint, controlled reason vocabulary, current watermark/business-date rule, and schema/deployment prerequisite without normative changes. Status is `Approved — Ready for Implementation`; `READY FOR IMPLEMENTATION: YES`. |
