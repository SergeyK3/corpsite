# OO-IMP-005 — Official Documents Architecture

## 1. Status

**Accepted** — architecture reconnaissance and review complete (OO-IMP-005A, OO-IMP-005A-R1, OO-IMP-005A-R2).

Implementation (OO-IMP-005B+) not started. No production code, migrations, or runtime changes in this phase.

### Architecture Acceptance

**Accepted:** 2026-07-13

**Accepted scope:**

- lifecycle authority (`operational_order_documents.status`);
- `PUBLISHED` as full lifecycle state;
- signing, registration, and publication boundaries;
- official PDF artifact prerequisite (005H before 005E);
- official registry read projections;
- security separation (workspace read vs command permissions vs OO-SEC-002);
- authoritative WP dependency graph.

**Not in scope of this acceptance:** implementation, migrations, permissions provisioning, frontend, deploy.

### Architecture Review Corrections (OO-IMP-005A-R1)

| # | Issue in OO-IMP-005A | Correction |
|---|---|---|
| 1 | `PUBLISHED` modeled as `status=REGISTERED` + `published_at` marker | **`PUBLISHED` is a full lifecycle state** in `operational_order_documents.status` |
| 2 | Employee read filtered by `published_at IS NOT NULL` | Employee read filtered by **`status = PUBLISHED`** |
| 3 | UDE extension left as open question defaulting to marker | **Ratified direction:** extend shared UDE enum with `PUBLISHED`; PO does not use it |
| 4 | Registration uniqueness underspecified | **`UNIQUE(registration_year, registration_number)`** with business rationale |
| 5 | `registration_date` vs system timestamp conflated | Split: **`registration_date`** (official calendar) vs **`registered_at`** (system) |
| 6 | Signing authority vs attestation blurred | Strict separation: assignment table vs sign snapshot on header |
| 7 | Read surfaces not fully separated | Two surfaces: **Lifecycle Administration** vs **Organization-Wide Official Registry** |
| 8 | OO-SEC-002 grants bundled into 005G | **OO-SEC-002** is separate WP; depends on 005E + 005F |
| 9 | PDF boundary underspecified | Content authority = immutable version; PDF = rendition; publish requires artifact readiness |
| 10 | Risks accepted marker approach | Risks updated for UDE enum extension and state/metadata invariants |

### Architecture Review Corrections (OO-IMP-005A-R2)

| # | Issue in OO-IMP-005A-R1 | Correction |
|---|---|---|
| 1 | Publication Command (005E) sequenced before PDF Integration (005H) | **005H executes before 005E**; dependency graph is authoritative, not WP letter order |
| 2 | 005E could imply inline PDF generation | **005E only verifies artifact readiness** — no PDF generation, no fake artifact, no weakened precondition |
| 3 | Command permissions stated without repo verification | Permissions marked **Proposed** — not present in `access_roles` today |
| 4 | `INTAKE_READ` implicitly tied to lifecycle commands | **Workspace read ≠ lifecycle command authorization** — sign/register/publish require separate grants |

---

## 2. Context

### Program position

Operational Orders (OO) already implement:

| Capability | WP | State |
|---|---|---|
| Submitted-text Intake | OO-IMP-001 | Complete |
| Editorial workflow | OO-IMP-002 | Complete |
| Promotion → Document Aggregate, immutable Version 1 | OO-IMP-003 / 003A | Complete |
| Workspace freeze after promotion | OO-IMP-003B | Complete |
| Lifecycle `CREATED` ↔ `READY_FOR_SIGNATURE` | OO-IMP-004 | Complete |
| Leadership Workspace Read Policy | OO-SEC-001 | Approved, deployed |
| Organization-Wide Official Read (planning) | OO-SEC-002 | Proposed |

Alembic production head (at reconnaissance): `b2c3d4e5f6a7`.

### Target lifecycle (ratified)

```text
CREATED
  ↓
READY_FOR_SIGNATURE
  ↓
SIGNED
  ↓
REGISTERED
  ↓
PUBLISHED
```

**Allowed return (implemented):** `READY_FOR_SIGNATURE → CREATED`

**Not approved at this stage:** backward transitions from `SIGNED`, `REGISTERED`, or `PUBLISHED`. Future cancellation uses separate void/cancellation lifecycle — not `unpublish`.

### Architectural mandate

| Context | Purpose | Audience |
|---|---|---|
| **Operational Orders Workspace** | Preparation: intake, editorial, promotion | Leadership + designated operators |
| **Official Operational Orders** | Signed, registered, published legal documents | Operators (lifecycle admin) + all employees (`PUBLISHED` read) |

### Ratified constraints (must preserve)

1. Workspace = preparation contour only.
2. Document Aggregate + Document Version = authority for official document text.
3. Immutable Version 1 after promotion.
4. Workspace freeze after successful promotion.
5. OO-SEC-001 — no extension to all employees.
6. OO-SEC-002 — separate future security contour.
7. Append-only audit semantics.
8. Shared UDE runtime for transition rules.
9. Personnel Orders write path unchanged.
10. Current navigation/access integration model (extend, do not replace).
11. OO-IMP-003A Document Identity Policy.

---

## 3. Existing Architecture

### Two-layer model (implemented)

```text
DRAFT WORKSPACE → Promotion → DOCUMENT AGGREGATE (v1) → SIGNING PIPELINE (partial)
```

**Implemented transitions:** `CREATED ↔ READY_FOR_SIGNATURE` only.

**Schema CHECK today:** `CREATED`, `READY_FOR_SIGNATURE`, `SIGNED`, `REGISTERED`, `VOIDED` — **`PUBLISHED` not yet in CHECK**.

### OO status mapping to UDE (current vs target)

| OO `status` | UDE `DocumentLifecycleState` (current) | UDE (after extension) | Implemented |
|---|---|---|---|
| `CREATED` | `DRAFT` | `DRAFT` | Yes |
| `READY_FOR_SIGNATURE` | `READY_FOR_SIGNATURE` | `READY_FOR_SIGNATURE` | Yes |
| `SIGNED` | `SIGNED` | `SIGNED` | Schema only |
| `REGISTERED` | `REGISTERED` | `REGISTERED` | Schema only |
| `PUBLISHED` | — | **`PUBLISHED` (new)** | No |
| `VOIDED` | `VOIDED` | `VOIDED` | Schema only |

---

## 4. Repository Findings

*(Summary from OO-IMP-005A reconnaissance — unchanged facts.)*

- **Backend:** `app/operational_orders/` — 30+ API endpoints; lifecycle stops at `READY_FOR_SIGNATURE`.
- **Models:** `operational_order_documents` has `status`; no registration/signature/publication header columns yet.
- **UDE:** Five-state enum in `app/document_engine/value_objects/lifecycle.py`; `LifecycleRules` has no `PUBLISHED` transition.
- **PO reference:** `order_number` + `order_date` on header; `UNIQUE(order_number)` org-wide; strict register requires both; no `PUBLISHED` state (employee visibility ≈ `REGISTERED`).
- **Frontend:** Single preparation gate; tab «Официальные документы» is signing-pipeline list, not employee registry.
- **Gap:** No `OPERATIONAL_ORDERS_OFFICIAL_READ`; no official registry API.

---

## 5. Lifecycle Authority

### Single authoritative lifecycle state

```text
operational_order_documents.status
```

is the **only** authoritative current lifecycle state for Operational Orders documents.

**Rules:**

- Timestamps (`signed_at`, `registered_at`, `published_at`) are **transition metadata** — they do not define status.
- Status is set **only** by audited lifecycle commands.
- No parallel status column, no `published_at`-as-status substitute.

### UDE role

| Layer | Authority |
|---|---|
| **Current lifecycle state** | `operational_order_documents.status` (OO persistence) |
| **Allowed transition rules** | UDE `LifecycleRules` (evaluation only) |
| **Transition validation** | UDE policies + OO specialization validators |
| **Transition history** | `operational_order_lifecycle_audit` (append-only) |

### Permitted status values (target)

```text
CREATED
READY_FOR_SIGNATURE
SIGNED
REGISTERED
PUBLISHED
VOIDED
```

### State ↔ metadata invariants

Enforced by **service layer + DB CHECK constraints** (005B). Timestamps alone never imply status.

#### `status = SIGNED`

Required:

```text
signed_at IS NOT NULL
signed_by_user_id IS NOT NULL
signing_authority_snapshot complete (see §7)
```

Forbidden:

```text
registration_number IS NOT NULL   -- not yet registered
published_at IS NOT NULL        -- not yet published
```

#### `status = REGISTERED`

Required:

```text
signature metadata complete (SIGNED invariants)
registration_number IS NOT NULL
registration_date IS NOT NULL
registered_at IS NOT NULL
registered_by_user_id IS NOT NULL
```

Forbidden:

```text
published_at IS NOT NULL        -- not yet published
status != SIGNED lineage         -- must have passed SIGNED
```

#### `status = PUBLISHED`

Required:

```text
signature metadata complete
registration metadata complete
published_at IS NOT NULL
published_by_user_id IS NOT NULL
official artifact readiness satisfied (see §12)
```

#### Impossible combinations prevented

| Invalid state | Prevention |
|---|---|
| `status = CREATED` with `signed_at` set | Service rejects; CHECK forbids metadata without status |
| `status = REGISTERED` without registration fields | Register command atomic; CHECK on REGISTERED rows |
| `status = PUBLISHED` without `published_at` | Publish command sets both atomically |
| `published_at` with `status != PUBLISHED` (and not VOIDED annul) | CHECK: `published_at` implies `status IN (PUBLISHED, VOIDED)` |
| Skip-step status jump | UDE `LifecycleRules.structurally_allowed` + service guards |

---

## 6. UDE Lifecycle Extension

### Problem

Ratified product lifecycle requires `PUBLISHED`. Current UDE enum ends at `REGISTERED`.

### Decision: single shared enum extension (not OO superset)

**Add `PUBLISHED` to shared `DocumentLifecycleState`** in UDE — one enum for all document domains.

| Principle | Detail |
|---|---|
| **Single enum** | No competing OO-only lifecycle enum |
| **PO compatibility** | PO never transitions to `PUBLISHED`; PO lifecycle unchanged |
| **OO adoption** | OO uses full path including `PUBLISHED` |
| **Existing documents** | Migration adds enum value only; no auto-transition of existing rows |
| **VOIDED** | Remains terminal; annul from `PUBLISHED` allowed (future WP) |

### Minimal safe extension scope (005B — planning only)

| Artifact | Change |
|---|---|
| `app/document_engine/value_objects/lifecycle.py` | Add `PUBLISHED = "PUBLISHED"` |
| `app/document_engine/lifecycle/lifecycle_rules.py` | Add `(REGISTERED → PUBLISHED, LifecycleGate.PUBLISH)`; extend `_STRUCTURALLY_ALLOWED` |
| `app/document_engine/lifecycle/lifecycle_models.py` | Add `LifecycleGate.PUBLISH` if not present |
| OO ORM / migration CHECK | Add `PUBLISHED` to `DOCUMENT_STATUSES` |
| PO ORM CHECK | Add `PUBLISHED` to allowed values but **no PO service may set it** |
| Serializers / UI labels | Add `PUBLISHED` label; PO UI never displays it for PO documents |
| Tests | UDE transition tests; PO regression — no PO path reaches `PUBLISHED` |

### Why not domain-specific superset

A separate OO enum would duplicate `LifecycleRules`, break adapter convergence, and create two authorities. Shared enum with optional domain usage is the UDE-006 compatibility pattern.

### Personnel Orders impact

| Aspect | Impact |
|---|---|
| PO write path | **None** — no code changes to transition services |
| PO schema CHECK | Widened to allow enum value; existing rows unaffected |
| PO employee visibility | Still effectively `REGISTERED` (PO has no publish step) |
| PO adapters | Map PO statuses 1:1; `PUBLISHED` unused in PO read models |

---

## 7. Authority Matrix

Lifecycle state separated from transition metadata.

| Concern | Authority | Projection / Consumer | Mutable |
|---|---|---|---|
| **Current lifecycle state** | `operational_order_documents.status` | All APIs, UI badges, registry filters | UDE-gated commands only |
| **Allowed transition rules** | UDE `LifecycleRules` | OO lifecycle service evaluation | Code/deploy only |
| Workspace submitted text | `operational_order_draft_blocks.submitted_text` | Workspace UI | Until frozen |
| Effective editorial text | `operational_order_draft_blocks.workspace_effective_text` | Workspace UI, promotion | Until frozen |
| Official Document ID | `operational_order_documents.id` | All surfaces | Immutable |
| Official Version 1 | `operational_order_document_versions` | Document/version APIs | Immutable after promotion |
| Official localized text | `operational_order_document_localizations.official_text` | Lifecycle admin, official read, PDF source | Immutable after promotion |
| **Assigned signing authority** | `operational_order_signing_authority` | Signing-pipeline UI (pre-sign) | Supersede/revoke before `SIGNED` only |
| **Signing attestation** | Document header snapshot at `SIGNED` | Official surfaces | Immutable after `SIGNED` |
| **Registration identity** | `registration_year` + `registration_number` | Registry, PDF | Immutable after `REGISTERED` |
| **Registration calendar date** | `registration_date` | Registry, PDF, legal display | Immutable after `REGISTERED` |
| **Registration system timestamp** | `registered_at` | Audit, ops | Immutable after `REGISTERED` |
| **Publication metadata** | `published_at`, `published_by_user_id` | Registry, employee read | Set at `PUBLISHED`; immutable |
| **Official PDF artifact** | Print record / attachment table | Official read UI | Immutable after publish |
| **Transition history** | `operational_order_lifecycle_audit` | Operator timeline | Append-only |
| Employee official visibility | `status = PUBLISHED` + `OPERATIONAL_ORDERS_OFFICIAL_READ` | OO-SEC-002 registry | Not a separate flag |

**Rule:** Timestamps confirm transitions; **status** is the sole lifecycle authority.

---

## 8. Lifecycle Model

### State machine

```text
CREATED
  │
  ├── readiness validation (OO401–OO416)
  ▼
READY_FOR_SIGNATURE
  │
  ├── return_for_correction (reason required)
  └──────────────────────────► CREATED
  │
  ├── sign
  ▼
SIGNED
  │
  ├── register
  ▼
REGISTERED
  │
  ├── publish
  ▼
PUBLISHED
```

**Not approved:** `SIGNED → CREATED`, `REGISTERED → SIGNED`, `PUBLISHED → REGISTERED`, or any `unpublish`.

**Future (separate WP):** `→ VOIDED` via `CANCEL` / `ANNUL` — not part of OO-IMP-005 MVP.

### Transition specification

| Transition | Command | Permission | Preconditions | Postconditions | Audit |
|---|---|---|---|---|---|
| → `READY_FOR_SIGNATURE` | `mark_ready_for_signature` | `MARK_READY_FOR_SIGNATURE` | `CREATED`; OO401–416; active authority | `ready_for_signature_*`; status unchanged until mark | `DOCUMENT_READY_FOR_SIGNATURE` |
| → `CREATED` | `return_to_created` | `RETURN_FROM_SIGNATURE` | `READY_FOR_SIGNATURE`; reason | Clear ready fields; `status=CREATED` | `DOCUMENT_RETURNED_TO_CREATED` |
| → `SIGNED` | `sign_document` | `OPERATIONAL_ORDERS_SIGN` (**Proposed**) | `READY_FOR_SIGNATURE`; authority valid | `status=SIGNED`; sign metadata | `DOCUMENT_SIGNED` |
| → `REGISTERED` | `register_document` | `OPERATIONAL_ORDERS_REGISTER` (**Proposed**) | `SIGNED`; number+date; unique key | `status=REGISTERED`; reg metadata | `DOCUMENT_REGISTERED` |
| → `PUBLISHED` | `publish_document` | `OPERATIONAL_ORDERS_PUBLISH` (**Proposed**) | `REGISTERED`; artifact ready (005H); metadata complete | `status=PUBLISHED`; pub metadata | `DOCUMENT_PUBLISHED` |

### Forbidden transitions

| From | Forbidden | Reason |
|---|---|---|
| `CREATED` | `SIGNED`, `REGISTERED`, `PUBLISHED` | Must pass ready queue |
| `READY_FOR_SIGNATURE` | `REGISTERED`, `PUBLISHED` | Must sign |
| `SIGNED` | `PUBLISHED`, `CREATED`, `READY_FOR_SIGNATURE` | Must register; no backward |
| `REGISTERED` | `PUBLISHED` skip via marker without command | Must use publish command |
| `REGISTERED` | `SIGNED`, `CREATED` | No backward |
| `PUBLISHED` | `REGISTERED`, `SIGNED`, any non-VOID | Terminal (until future annul) |

---

## 9. Signing Semantics

### Strict separation

| Concept | Storage | Phase |
|---|---|---|
| **Assigned signing authority** | `operational_order_signing_authority` | Pre-sign: who is designated to sign |
| **Actual signing attestation** | Document header snapshot + `signed_at` | Post-sign: what was attested |

Assignment does **not** equal signature. Attestation is a separate `sign_document` command.

### Assigned signing authority (pre-sign)

- Assigned via `POST /documents/{id}/signing-authority` (existing OO-IMP-004).
- Fields: party type/ref, display name, position, org unit, basis.
- One `ACTIVE` authority per document (partial unique index).
- May be superseded before `SIGNED`; **frozen into snapshot at sign**.

### Signing attestation (post-sign)

**MVP = workflow attestation** — operator attests paper/legal signing completed. **No ЭЦП integration** in OO-IMP-005.

| Field | Set at `SIGNED` |
|---|---|
| `signed_at` | System timestamp (UTC storage; display in org timezone) |
| `signed_by_user_id` | Actor who executed command |
| `signing_authority_id` | FK to authority row snapshotted |
| `signatory_display_name` | Copied from active authority |
| `signatory_position` | Copied from active authority |
| `signatory_party_reference` | Copied from authority |

### Who may execute `sign_document`

| Actor | Allowed? |
|---|---|
| User matching assigned authority (`PERSON` reference) | **Yes** (primary) |
| User with `OPERATIONAL_ORDERS_SIGN` grant | **Yes** |
| `is_privileged` admin | **Yes**, with **mandatory `reason`** in command + audit `metadata_json.override=true` |

Actor **need not** match authority when grant or privileged override applies; override requires reason.

### Post-sign authority changes

If signatory's position changes after `SIGNED`: **no effect** — snapshot on header is authoritative for display and PDF.

### Return from `SIGNED`

**Not allowed** in OO-IMP-005. Correction via future annul + new document.

---

## 10. Registration Identity

### Business key (ratified)

```text
UNIQUE (registration_year, registration_number)
```

### Rationale

| Pattern | Source | Why not chosen for OO |
|---|---|---|
| `UNIQUE(registration_number)` | PO `uq_personnel_orders_order_number` | PO numbers are org-permanent HR identifiers; OO production-order journals **reset annually** |
| `UNIQUE(document_kind, registration_year, registration_number)` | Future-proof | MVP has only `OPERATIONAL_ORDER`; year+number sufficient; kind can be added in 005B if multi-kind introduced |
| `MAX(number)+1` | — | **Forbidden** — race unsafe |

**`registration_year`** = `EXTRACT(YEAR FROM registration_date)` — stored explicitly for index clarity and backdating safety.

**Scope:** Single hospital organization (MVP). Multi-org future adds `organization_id` to unique key.

### Field separation

| Field | Semantics | Type | Set by |
|---|---|---|---|
| `registration_number` | Official journal number (manual entry) | TEXT | Registrar at register command |
| `registration_date` | Official calendar date of registration | DATE | Registrar — may differ from `registered_at` |
| `registered_at` | System timestamp of register operation | TIMESTAMPTZ | Server clock at commit |
| `registered_by_user_id` | Actor | BIGINT | Authenticated user |

### Timezone

- Storage: UTC for `registered_at`, `signed_at`, `published_at`.
- `registration_date`: **calendar date** without timezone — official business date.
- Display: organization timezone (existing Corpsite convention).

### Backdating

**Allowed:** registrar may set `registration_date` in the past (paper journal back-entry). Requires optional `reason` in command; recorded in lifecycle audit `metadata_json`.

### Manual number entry

**Yes** — operator types `registration_number` (PO paper-first pattern). No auto-sequence in MVP.

### Collision handling

1. Validate uniqueness on `(registration_year, registration_number)` inside transaction.
2. On conflict → HTTP 409; **full rollback** — status remains `SIGNED`.
3. No partial reservation — number is not reserved before successful commit.

### Idempotency

Re-submitting register with **same** `document_id` + `registration_year` + `registration_number` → safe replay (return existing `REGISTERED` state).

Different number on already-`REGISTERED` document → 409 conflict.

### Rollback after failure

Transaction boundary: validate → update status → write metadata → append audit → commit. Any failure rolls back all fields.

---

## 11. Publication Boundary

### Transition

```text
REGISTERED → PUBLISHED
```

Separate audited, idempotent command. **`status` becomes `PUBLISHED`** — not a marker on `REGISTERED`.

**Implemented in OO-IMP-005E** — which runs **only after OO-IMP-005H** delivers a working artifact mechanism.

```text
SIGNED      ≠ REGISTERED
REGISTERED  ≠ PUBLISHED
```

### What OO-IMP-005E does (and does not do)

**005E responsibility:**

- Verify official PDF artifact readiness (§12 invariants)
- Execute audited transition `REGISTERED → PUBLISHED`
- Set `published_at`, `published_by_user_id`
- Append `DOCUMENT_PUBLISHED` audit event

**005E must NOT:**

- Generate PDF
- Contain a temporary PDF generator
- Use a fake/stub artifact in production path
- Weaken the PDF readiness precondition
- Duplicate OO-IMP-005H artifact storage responsibility

### Preconditions

- `status` strictly `REGISTERED`
- Current immutable official version exists (`is_current` version row)
- Signature metadata complete (§7 invariants)
- Registration metadata complete (§7 invariants)
- Official PDF artifact **ready** (see §12) — **required for MVP publish**
- Actor has `OPERATIONAL_ORDERS_PUBLISH`
- Document not `VOIDED` / cancelled
- `status != PUBLISHED` (not already published)

### Postconditions

```text
status = PUBLISHED
published_at = system timestamp (UTC)
published_by_user_id = actor user_id
```

### Audit event `DOCUMENT_PUBLISHED`

Records:

- `document_id`
- `transition_from = REGISTERED`
- `transition_to = PUBLISHED`
- `actor_user_id`
- `created_at`
- `metadata_json`: `{ "idempotency_key": "...", "artifact_id": "...", "document_version": N }`

### Idempotency

Identical publish command on already-`PUBLISHED` document → 200 with `replay=true`; no duplicate audit row.

### Unpublish

**Not permitted** in MVP. `PUBLISHED` does not revert to `REGISTERED`.

---

## 12. PDF Boundary

### Authoritative sequence

```text
REGISTERED
  → generate immutable PDF artifact        (OO-IMP-005H)
  → verify artifact metadata/hash          (OO-IMP-005H + 005E pre-check)
  → PUBLISHED                              (OO-IMP-005E)
```

**OO-IMP-005H** must deliver a fully working artifact mechanism **before** OO-IMP-005E publication transition is implemented.

WP letter order (`005E` before `005H`) is **not** execution order. See §20 dependency graph.

### Authority model

| Layer | Role |
|---|---|
| **Immutable structured official version** (`official_text` localizations) | **Content authority** |
| **Official PDF** | **Immutable rendition/artifact** derived from content authority + registration metadata |

Content authority is **not** the PDF. PDF is a rendered artifact.

### MVP rules

| Question | Answer |
|---|---|
| PDF required before publish? | **Yes** — `PUBLISHED` requires artifact readiness |
| PDF contains registration number/date? | **Yes** — generated after `REGISTERED` |
| PDF before registration? | **No** — preview only in operator UI (watermarked) |
| PDF immutable after publish? | **Yes** — store hash; no overwrite |
| Artifact hash stored? | **Yes** — `content_hash` / `sha256` on print record |
| Publish without PDF? | **No** in MVP |
| PDF generation failure? | Status stays `REGISTERED`; operator retries via 005H |

### Transaction boundary (ratified)

**Two-phase — mandatory:**

1. **OO-IMP-005H:** At `REGISTERED` status, generate and persist immutable PDF artifact (outside publish transaction).
2. **OO-IMP-005E:** Publish command verifies artifact readiness invariants, then atomically sets `status=PUBLISHED` + audit.

005E transaction contains **verification + status transition only** — never PDF rendering.

### Artifact readiness invariants (005H defines storage; these are publication gates)

A PDF artifact is **ready for publication** when all of the following hold:

| Invariant | Requirement |
|---|---|
| Artifact exists | Storage reference resolvable |
| Document binding | `document_id` matches target document |
| Version binding | `document_version_id` matches current `is_current` official version |
| Artifact type | Declared type (e.g. `OFFICIAL_PDF`) |
| Storage reference | Non-empty pointer to persisted bytes |
| Content hash | SHA-256 (or equivalent) present and verifiable |
| Generated at | System timestamp recorded |
| Generator metadata | Generator name/version recorded |
| Registration snapshot | Embedded `registration_number` + `registration_date` match document header |
| Language variant | Rendering variant declared (e.g. bilingual PDF policy) |
| Immutability | `immutable=true` or equivalent — no in-place overwrite permitted |
| Generation status | `SUCCESS` — not `FAILED` or `PENDING` |

**Publication forbidden when:**

- Artifact absent for current version
- Artifact bound to stale document version
- Hash missing or mismatch on re-verification
- Registration metadata in artifact ≠ document header
- Generation ended in error state
- Artifact replaced without audit trail
- Artifact marked mutable

Specific table/schema for artifact storage is **not ratified here** — OO-IMP-005H selects PO print-record pattern or equivalent. Invariants above are mandatory regardless of table design.

---

## 13. Read Projections

Two distinct read surfaces from one authoritative table (`operational_order_documents`).

### A. Official Lifecycle Administration

**Audience:** Operators with workspace/official lifecycle permissions.

**API:** Existing `/api/operational-orders/documents/*` (extended) + future lifecycle admin list.

**May display:**

```text
SIGNED
REGISTERED
PUBLISHED
```

(and `CREATED`, `READY_FOR_SIGNATURE` in signing pipeline)

**Includes:** lifecycle actions, signing authority, registration form, publish control, internal metadata, workspace link.

**Permission examples:** `INTAKE_READ` (exists), `SIGN`/`REGISTER`/`PUBLISH` (**Proposed** — separate grants required).

### B. Organization-Wide Official Registry (OO-SEC-002)

**Audience:** All active employees (future grant).

**API:** `GET /api/operational-orders/official-documents/*` — **separate endpoints**.

**Displays only:**

```text
status = PUBLISHED
```

(future: `VOIDED` annulled former published docs with cancelled marker — separate WP)

**Must not expose:**

- Workspace submitted text, clarifications, provenance, editorial validation
- Translation assignments, reconciliations
- `SIGNED`, `REGISTERED`, `CREATED`, `READY_FOR_SIGNATURE` documents
- Signing controls, internal audit trail

**Permission:** `OPERATIONAL_ORDERS_OFFICIAL_READ` (OO-SEC-002 — not in 005G).

### Query filter summary

| Surface | Filter |
|---|---|
| Lifecycle admin | `status IN (...)` per operator permission |
| Employee official registry | **`status = 'PUBLISHED'`** |
| Preparation workspace | `draft_workspaces` only |

---

## 14. Official Registry (employee read model)

Built from document header + current version localizations — no separate registry table in MVP.

Employee-visible fields: document ID, kind, registration number/date, titles RU/KK, `published_at`, signatory summary, PDF link, cancellation marker (future).

**Default sort:** `published_at DESC`.

**Indexes:** `(status, published_at DESC)` WHERE `status = PUBLISHED`; `UNIQUE(registration_year, registration_number)`.

---

## 15. UI Boundary

```text
/directory/operational-orders              → preparation + lifecycle admin
/directory/operational-orders/workspaces/[id]
/directory/operational-orders/documents/[id]   → signing pipeline + lifecycle actions

/directory/operational-orders/official         → employee registry (005G shell; OO-SEC-002 gate)
/directory/operational-orders/official/[id]
```

**005G** may ship operator-preview UI under lifecycle permissions. **Organization-wide employee visibility** activates only after **OO-SEC-002** grants — not bundled in 005G.

Rename misleading tab «Официальные документы» → «Документы (жизненный цикл)» until official routes exist.

---

## 16. Security Boundary

### Workspace read vs lifecycle commands (ratified separation)

| Permission class | Examples | Grants |
|---|---|---|
| **Workspace read** | `OPERATIONAL_ORDERS_INTAKE_READ` | Preparation contour visibility — workspaces, signing-pipeline read |
| **Lifecycle command** | `OPERATIONAL_ORDERS_SIGN`, `_REGISTER`, `_PUBLISH` | Specific mutation only |

**`OPERATIONAL_ORDERS_INTAKE_READ` does NOT imply:**

- sign attestation
- registration
- publication

Leadership Workspace Read Policy (OO-SEC-001) is **unchanged**. Command authorization is checked **separately per action** in route handlers.

### Workspace (OO-SEC-001 — unchanged)

Leadership `INTAKE_READ` + operators. Employees: **no access**.

### Official employee read (OO-SEC-002 — separate WP)

- `OPERATIONAL_ORDERS_OFFICIAL_READ` (**Proposed permission code**) via ORG_UNIT grant
- **`status = PUBLISHED` only**
- Read-only; no workspace/editorial
- **Not** a lifecycle command permission

### Lifecycle command permissions (repository verification 2026-07-13)

| Permission | Status | Repository evidence | Purpose |
|---|---|---|---|
| `OPERATIONAL_ORDERS_SIGN` | **Proposed** | Not in `app/security/admin_permissions.py`, `access_roles`, or Alembic seeds | Signing attestation command |
| `OPERATIONAL_ORDERS_REGISTER` | **Proposed** | Not in repository | Assign official number and date |
| `OPERATIONAL_ORDERS_PUBLISH` | **Proposed** | Not in repository | Transition `REGISTERED → PUBLISHED` |
| `OPERATIONAL_ORDERS_LIFECYCLE_ADMIN_READ` | **Proposed** (optional) | Not in repository | Lifecycle admin list read |
| `OPERATIONAL_ORDERS_OFFICIAL_READ` | **Proposed** | OO-SEC-002 spec only | Organization-wide read of published documents |

**Existing related permission (not a lifecycle command):**

| Permission | Status | Location |
|---|---|---|
| `OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ` | **Exists** | OO-IMP-004; `lifecycle_permissions.py`; migration `a1b2c3d4e5f6` |

Command permissions are **not** OO-SEC-002. OO-SEC-002 governs only organization-wide **read** of `PUBLISHED` documents.

### Permission implementation scope (recommended)

| Activity | WP |
|---|---|
| `access_roles` code registration (seed) | **005B** — lifecycle foundation |
| Command route enforcement wiring | Respective command WP (005C / 005D / 005E) |
| Role/user grants for command permissions | **Explicit migration per command WP** — auditable, not mass-granted |
| Employee ORG_UNIT grant for official read | **OO-SEC-002** only |

**Must not:**

- Grant command permissions to all employees
- Extend `OPERATIONAL_ORDERS_INTAKE_READ` semantics to cover sign/register/publish
- Bundle command grants into OO-SEC-002

`OPERATIONAL_ORDERS_OFFICIAL_READ` belongs to **OO-SEC-002**, not OO-IMP-005B–G.

---

## 17. Cancellation Compatibility (future — not MVP)

Architecture preserves:

- Published documents are **never physically deleted**
- Cancellation does **not** remove publication history
- Registry continues to show document with **cancelled/voided marker**
- Original published PDF **preserved**
- Link to **superseding** or **annulling** document (future column)
- **`PUBLISHED` does not revert to `REGISTERED`**
- Cancellation modeled as **`VOIDED`** + `void_kind=ANNUL` overlay (UDE gate) — separate WP
- Exact void implementation deferred until UDE cancellation architecture ratified for OO

---

## 18. Data Model Changes (proposed — 005B)

### Extend `operational_order_documents`

| Column | Type | Set at |
|---|---|---|
| `registration_year` | SMALLINT | REGISTER |
| `registration_number` | TEXT | REGISTER |
| `registration_date` | DATE | REGISTER |
| `registered_at` | TIMESTAMPTZ | REGISTER |
| `registered_by_user_id` | BIGINT | REGISTER |
| `signed_at` | TIMESTAMPTZ | SIGN |
| `signed_by_user_id` | BIGINT | SIGN |
| `signing_authority_id` | BIGINT | SIGN |
| `signatory_display_name` | TEXT | SIGN |
| `signatory_position` | TEXT | SIGN |
| `published_at` | TIMESTAMPTZ | PUBLISH |
| `published_by_user_id` | BIGINT | PUBLISH |

### Constraints (target)

```sql
-- Status enum includes PUBLISHED
CHECK (status IN ('CREATED','READY_FOR_SIGNATURE','SIGNED','REGISTERED','PUBLISHED','VOIDED'))

UNIQUE (registration_year, registration_number)
  WHERE registration_number IS NOT NULL

-- Metadata invariants (representative)
CHECK (status != 'SIGNED' OR signed_at IS NOT NULL)
CHECK (status != 'REGISTERED' OR (registration_number IS NOT NULL AND registration_date IS NOT NULL))
CHECK (status != 'PUBLISHED' OR published_at IS NOT NULL)
```

---

## 19. API Surface (planned)

| Method | Path | Surface | WP |
|---|---|---|---|
| `POST` | `/documents/{id}/sign` | Lifecycle admin | 005C |
| `POST` | `/documents/{id}/register` | Lifecycle admin | 005D |
| `POST` | `/documents/{id}/generate-official-pdf` | Lifecycle admin | **005H** |
| `POST` | `/documents/{id}/publish` | Lifecycle admin | **005E** (after 005H) |
| `GET` | `/official-documents` | Employee registry | 005F |
| `GET` | `/official-documents/{id}` | Employee registry | 005F |
| `GET` | `/official-documents/{id}/pdf` | Employee registry | 005H |

---

## 20. Implementation Work Packages

### WP identifiers (stable)

```text
OO-IMP-005A    — Architecture & Repository Reconnaissance
OO-IMP-005A-R1 — Architecture Correction
OO-IMP-005A-R2 — Final Sequencing Correction
OO-IMP-005B    — Lifecycle and Schema Foundation
OO-IMP-005C    — Signing Command
OO-IMP-005D    — Registration Command
OO-IMP-005H    — Official PDF Integration
OO-IMP-005E    — Publication Command and Boundary
OO-IMP-005F    — Official Registry Backend
OO-IMP-005G    — Official Registry UI
OO-SEC-002     — Organization-Wide Official Read Policy
OO-IMP-005R    — Integrity Review
```

**Note:** WP letter suffix does **not** define execution order. The dependency graph below is **authoritative**.

### Authoritative execution order

```text
005A → 005A-R1 → 005A-R2 (documentation)
  → 005B
  → 005C
  → 005D
  → 005H          ← PDF artifact mechanism (before publication)
  → 005E          ← publication command (verifies artifact only)
  → 005F
  → 005G
  → OO-SEC-002    (parallel after 005E+005F; not part of 005G)
  → 005R
```

### Dependency graph

```text
OO-IMP-005B
  └─ foundation for all subsequent WPs

OO-IMP-005C depends on: OO-IMP-005B
OO-IMP-005D depends on: OO-IMP-005C

OO-IMP-005H depends on:
  - OO-IMP-005B
  - OO-IMP-005C
  - OO-IMP-005D

OO-IMP-005E depends on:
  - OO-IMP-005H

OO-IMP-005F depends on:
  - OO-IMP-005E

OO-IMP-005G depends on:
  - OO-IMP-005F

OO-SEC-002 depends on:
  - OO-IMP-005E
  - OO-IMP-005F

OO-IMP-005R depends on:
  - OO-IMP-005C, 005D, 005H, 005E, 005F, 005G
  - OO-SEC-002 (if employee read in scope of review)
```

**OO-SEC-002** is **not** part of 005G. UI shell may ship under operator permissions in 005G; **organization-wide employee visibility** activates only after **OO-SEC-002** grants.

### WP summaries

| WP | Goal | Execution note |
|---|---|---|
| **005B** | UDE `PUBLISHED` enum + rules; OO schema; **Proposed** permission seeds | First implementation WP |
| **005C** | `sign_document`: `READY_FOR_SIGNATURE → SIGNED` | After 005B |
| **005D** | `register_document`: `SIGNED → REGISTERED` | After 005C |
| **005H** | Immutable PDF artifact: generate, store, hash, readiness API | **Before 005E** |
| **005E** | `publish_document`: verify artifact → `REGISTERED → PUBLISHED` | **After 005H**; no PDF gen |
| **005F** | `/official-documents` API; `status=PUBLISHED` filter | After 005E |
| **005G** | Official UI routes (operator; employee gate = OO-SEC-002) | After 005F |
| **OO-SEC-002** | `OPERATIONAL_ORDERS_OFFICIAL_READ` + ORG_UNIT grants | After 005E + 005F |
| **005R** | End-to-end integrity review | Last |

---

## 21. Testing Strategy

Minimum tests (in addition to 005A list):

- `status=PUBLISHED` set only by publish command
- `published_at` without `PUBLISHED` status rejected
- `REGISTERED` with `published_at` rejected
- UDE `LifecycleRules`: `REGISTERED → PUBLISHED` allowed; `PUBLISHED → REGISTERED` forbidden
- PO regression: no PO document reaches `PUBLISHED`
- Registration unique `(year, number)` collision → 409
- Employee registry returns only `PUBLISHED`
- `SIGNED`/`REGISTERED` absent from employee official API
- Publish blocked without PDF artifact (005E after 005H)
- 005E rejects publish when 005H artifact not ready
- Metadata invariants enforced per status

---

## 22. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| UDE enum extension affects all domains | **High** | PO regression tests; PO services never emit `PUBLISHED` |
| Schema CHECK + Python enum drift | **High** | Atomic 005B migration + enum sync in one deploy |
| API/UI must handle new `PUBLISHED` status | Medium | Labels, filters, badges in 005E–G |
| Migration must preserve existing statuses | Medium | Add enum value only; no row updates |
| Registration uniqueness scope needs business sign-off | Medium | Documented rationale; year+number default |
| PDF readiness affects publish transaction | Medium | **005H before 005E**; two-phase; failure leaves `REGISTERED` |
| WP letter order misleading (E before H) | Medium | Dependency graph authoritative per 005A-R2 |
| State/metadata invariant complexity | Medium | CHECK constraints + service validation + tests |
| Conflated «Официальные документы» tab | High | Rename; separate routes |
| Cancellation scope creep | Medium | Deferred; architecture hooks only |

**Removed risk:** ~~`published_at` marker on `REGISTERED`~~ — rejected per 005A-R1.

---

## 23. Open Questions

| # | Question | Status after 005A-R1 |
|---|---|---|
| 1 | `PUBLISHED` as full state vs marker? | **Resolved:** full state |
| 2 | UDE enum extension? | **Resolved:** shared `PUBLISHED` |
| 3 | Registration unique scope? | **Resolved:** `(registration_year, registration_number)` |
| 4 | PDF required for publish? | **Resolved:** yes; 005H before 005E |
| 5 | Include voided in employee list? | Open — future cancellation WP |
| 6 | Auto vs manual registration numbers? | **Resolved:** manual |
| 7 | ЭЦП integration? | **Resolved:** out of scope |
| 8 | `document_kind` in unique key? | Deferred — MVP single kind |
| 9 | 005E vs 005H sequencing? | **Resolved:** 005H first (005A-R2) |

---

## 24. Recommended Decision

1. **`operational_order_documents.status`** is the sole lifecycle authority.
2. **`PUBLISHED`** is a full lifecycle state — not `published_at` on `REGISTERED`.
3. **Extend UDE** `DocumentLifecycleState` with `PUBLISHED`; PO unchanged in behavior.
4. **Strict path:** `CREATED → READY_FOR_SIGNATURE → SIGNED → REGISTERED → PUBLISHED`.
5. **Registration key:** `UNIQUE(registration_year, registration_number)`.
6. **Signing:** assignment ≠ attestation; MVP workflow attestation without ЭЦП.
7. **Publish:** `REGISTERED → PUBLISHED` command (005E); verifies PDF artifact from **005H** — does not generate PDF.
8. **Sequencing:** 005H (PDF) **before** 005E (publication); dependency graph authoritative.
9. **Employee read:** `status = PUBLISHED` only via OO-SEC-002 — separate from 005G.
10. **Content authority** = immutable version; **PDF** = immutable rendition.
11. **Workspace read ≠ command auth** — `INTAKE_READ` does not grant sign/register/publish.
12. **No unpublish**; future cancellation via `VOIDED`/`ANNUL` WP.

---

## 25. Acceptance Checklist

- [x] OO-IMP-005A reconnaissance complete
- [x] OO-IMP-005A-R1 corrections applied
- [x] OO-IMP-005A-R2 sequencing correction applied
- [x] Architecture accepted 2026-07-13
- [x] 005H before 005E dependency documented
- [x] Command permissions verified as Proposed
- [x] Workspace read vs command auth separated
- [x] `PUBLISHED` as full lifecycle state documented
- [x] Single lifecycle authority: `operational_order_documents.status`
- [x] UDE extension scope defined
- [x] Registration identity scope chosen
- [x] Signing assignment vs attestation separated
- [x] Publication boundary with pre/postconditions
- [x] Read projections separated (admin vs employee)
- [x] PDF boundary defined
- [x] Decomposition updated; OO-SEC-002 separate
- [x] No production code changed
- [x] No migrations / permissions / commit / push / deploy

---

*Path: `docs/operational-orders/architecture/OO-IMP-005-official-documents-architecture.md`*
