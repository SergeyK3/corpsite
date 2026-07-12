# OO-IMP-001 — Submitted-text Intake MVP

**Status:** Complete (local)  
**Revision:** `w7x8y9z0a1b2`  
**Package:** `app/operational_orders/`

First production-oriented Operational Orders WP and first native consumer of Shared UDE contracts (not write runtime).

---

## Scope

Implemented:

- Draft workspace aggregate persistence (separate from Document Aggregate)
- Submitted-text intake (P0 drafting path)
- Text blocks with immutable `submitted_text` and editable `workspace_effective_text`
- Append-only text provenance and draft audit
- Intake validation and clarification records
- READY_FOR_EDITORIAL gate
- REST API under `/api/operational-orders/draft-workspaces`

Not implemented (deferred):

- Document Aggregate / DocumentId
- Activation, promotion, lifecycle, signing, registration
- PDF/HTML rendering, execution projection
- Archive/restore, machine translation, task engine

---

## Architecture

```text
Business Initiator
  → POST /draft-workspaces (SUBMITTED)
  → POST .../accept (ACCEPTED)
  → POST .../validate (INTAKE_REVIEW / CLARIFICATION_REQUIRED)
  → POST .../ready-for-editorial (READY_FOR_EDITORIAL)
```

Bounded context: `app/operational_orders/`  
ORM models: `app/db/models/operational_orders.py`  
Persistence owned by OO module — Shared UDE has no OO tables.

### Workspace stage model

| Stage | Meaning |
|---|---|
| SUBMITTED | Submission recorded; not yet accepted |
| ACCEPTED | Intake operator accepted submission |
| INTAKE_REVIEW | Validation passed or under review |
| CLARIFICATION_REQUIRED | Open clarifications or validation blockers |
| READY_FOR_EDITORIAL | Gate passed; handoff to editorial processing |

**Workspace Stage ≠ Document Lifecycle State** (no DRAFT/SIGNED/REGISTERED on workspace).

---

## Content Author vs Record Creator

| Role | Storage | Notes |
|---|---|---|
| Content Author | `content_author_*` party reference | Who authored submitted text |
| Record Creator | `record_creator_user_id` | Authenticated user creating intake record |
| Document Operator | `document_operator_user_id` (nullable) | Extension point; not auto-filled |

API never auto-substitutes record creator as content author.

---

## Submitted vs Effective Text

| Field | Mutability | Purpose |
|---|---|---|
| `submitted_text` | Immutable after create | Original submission from business unit |
| `workspace_effective_text` | Editable via PATCH | Editorial/intake adjustments |

RU effective edit marks KK blocks `REVIEW_REQUIRED` (minimal staleness policy).

---

## Provenance

Append-only table `operational_order_text_provenance`:

- Created on submission, acceptance, block add, effective edit
- Service-level policy: no update/delete
- Uses shared `TextSourceType`; stores content SHA-256 fingerprint

---

## Shared UDE Usage

| Contract | Usage |
|---|---|
| `DraftingPath` | Added in UDE-007 extension; workspace uses `SUBMITTED_TEXT` |
| `LocaleCode` / `LOCALE_RU`/`KK` | Block locales, validation |
| `TextSourceType` | Block and provenance source typing |
| `StalenessState` / review_state | KK staleness after RU edit |
| `ValidationIssue` / `ValidationResult` | Intake validation aggregation |
| `PartyReference` / `PartyReferenceType` | Initiator, author, signer refs |
| `DocumentKind.OPERATIONAL_ORDER` | Intended document kind |

**Not used:** `DocumentEngineWriteFacade`, `DocumentId`, `DocumentLifecycleState`

---

## API

Prefix: `/api/operational-orders/draft-workspaces`

| Method | Path | Action |
|---|---|---|
| POST | `/` | Create submission |
| GET | `/` | List workspaces |
| GET | `/{id}` | Detail |
| POST | `/{id}/accept` | Accept submission |
| POST | `/{id}/blocks` | Add block |
| PATCH | `/{id}/blocks/{block_id}` | Edit effective text |
| POST | `/{id}/validate` | Run validation |
| POST | `/{id}/clarifications/{id}/resolve` | Resolve clarification |
| POST | `/{id}/ready-for-editorial` | Mark ready |

---

## Permissions (bootstrap)

| Code | Purpose |
|---|---|
| `OPERATIONAL_ORDERS_INTAKE_CREATE` | Create submissions |
| `OPERATIONAL_ORDERS_INTAKE_READ` | Read scoped workspaces |
| `OPERATIONAL_ORDERS_INTAKE_OPERATE` | Accept, edit, validate, ready |

MVP access: privileged users; record creator; granted permissions.

---

## Validation Rules

| Code | Severity (intake) | Severity (ready gate) |
|---|---|---|
| OI001–OI007 | ERROR | ERROR |
| OI008 | WARNING | WARNING |
| OI009 missing RU | WARNING | **ERROR** |
| OI010 missing KK | WARNING | **ERROR** |
| OI011 provenance | WARNING | ERROR |
| OI012–OI014 | ERROR | ERROR |

Missing locale allows workspace creation; both locales required for READY_FOR_EDITORIAL.

---

## Tests

```bash
pytest tests/operational_orders/ -q
pytest tests/document_engine/ -q
pytest tests/personnel_orders/characterization/ -q
```

---

## Known Limitations

- No OO read adapter yet (UDE-008 pattern pending)
- Content confirmation workflow deferred to OO-IMP-002
- Org scope uses organization_id = submitting unit by default
- No archive/restore

---

## Handoff to OO-IMP-002

Next WP: **Content Confirmation and Translation Workflow**

- Clarification resolution policies
- Content confirmation extension point
- KK translation/review workflow
- Editorial runtime integration via OO read adapter

---

*Implementation record — OO-IMP-001*
