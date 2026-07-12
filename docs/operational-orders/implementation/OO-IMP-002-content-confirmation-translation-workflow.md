# OO-IMP-002 — Content Confirmation and Translation Workflow

**Status:** Implemented (local)  
**Revision:** `x8y9z0a1b2c3`  
**Down revision:** `w7x8y9z0a1b2`  
**Package:** `app/operational_orders/`

Extends Draft Workspace bounded context after `READY_FOR_EDITORIAL` gate (OO-IMP-001 entry point).

---

## Scope

Implemented:

- Translation assignment lifecycle (RU-only / KK-only intake paths)
- Per-block content confirmation with fingerprint binding
- Bilingual reconciliation per RU/KK block pair
- Editorial package validation gate (`OO201`–`OO213`)
- `EDITORIAL_PACKAGE_READY` workspace stage
- REST API under `/api/operational-orders/draft-workspaces/{id}/…`
- Append-only provenance/audit extensions
- Granular permissions for assign / translate / confirm / reconcile / ready

Not implemented (deferred):

- Document Aggregate / DocumentId
- Activation, promotion, signing, registration, archive
- PDF/HTML, execution projection, notifications
- Machine translation
- Frontend workflow
- Personnel Orders changes

---

## Aggregate boundary

Remains **OperationalOrderDraftWorkspace** aggregate within OO module.

| Entity | Table | Purpose |
|---|---|---|
| `OperationalOrderTranslationAssignment` | `operational_order_translation_assignments` | Human translation work unit |
| `OperationalOrderContentConfirmation` | `operational_order_content_confirmations` | Role-bound text confirmation |
| `OperationalOrderBilingualReconciliation` | `operational_order_bilingual_reconciliations` | RU/KK semantic alignment record |

Reuses OO-IMP-001 entities: workspace, blocks, provenance, clarifications, audit.

---

## Workspace stage extension

| Stage | Meaning |
|---|---|
| `READY_FOR_EDITORIAL` | OO-IMP-001 gate passed; OO-IMP-002 entry |
| `TRANSLATION_REQUIRED` | Missing target locale; assignment needed |
| `TRANSLATION_IN_PROGRESS` | Active translation assignment |
| `CONTENT_CONFIRMATION_REQUIRED` | Both locales present; confirmations pending |
| `BILINGUAL_RECONCILIATION` | Confirmations satisfied; reconciliation pending |
| `EDITORIAL_PACKAGE_READY` | Gate passed; ready for next WP |

Existing OO-IMP-001 stages unchanged. Existing rows at `READY_FOR_EDITORIAL` remain valid.

---

## Translation assignment lifecycle

```text
POST translation-assignments → REQUESTED (+ TRANSLATION_REQUIRED)
POST …/accept              → ACCEPTED
POST …/start               → IN_PROGRESS
POST …/complete            → COMPLETED (+ target text + fingerprint)
POST …/cancel              → CANCELLED
Source text change         → prior COMPLETED kept; new REQUESTED or SUPERSEDED active
```

One active assignment per `(workspace_id, target_locale)` enforced by partial unique index.

---

## Confirmation matrix (P0)

| Locale origin | Required roles |
|---|---|
| Source / author locale block | `CONTENT_AUTHOR` |
| Translated locale block | `TRANSLATOR` + `CONTENT_AUTHOR` (semantic equivalence) |

`DOCUMENT_OPERATOR` may confirm technical readiness only; does not replace `CONTENT_AUTHOR`.

Confirmation binds: `block_id`, `block_version`, `content_fingerprint`, `confirmation_role`.

Text change → prior `CONFIRMED` → `SUPERSEDED` (history retained).

---

## Reconciliation model

One record per RU/KK block pair (`block_type` + `sequence`).

Status: `PENDING` → `RECONCILED` | `INVALIDATED` | `SUPERSEDED`.

Any fingerprint change on either side → active `RECONCILED` → `INVALIDATED`.

---

## Validation rules (editorial gate)

| Code | Condition |
|---|---|
| OO201 | RU effective text missing |
| OO202 | KK effective text missing |
| OO203 | Active translation assignment required |
| OO204 | Translation assignment incomplete |
| OO205 | RU content author confirmation missing |
| OO206 | KK content author confirmation missing |
| OO207 | Translator confirmation missing |
| OO208 | Reconciliation missing |
| OO209 | Reconciliation stale |
| OO210 | Blocking clarification open |
| OO211 | Block version mismatch |
| OO212 | Content fingerprint mismatch |
| OO213 | Workspace version conflict |

---

## Authorization matrix

| Permission | Actions |
|---|---|
| `OPERATIONAL_ORDERS_TRANSLATION_ASSIGN` | Create/cancel assignments |
| `OPERATIONAL_ORDERS_TRANSLATION_WORK` | Accept/start/complete (assigned party or grant) |
| `OPERATIONAL_ORDERS_CONTENT_CONFIRM` | Create confirmations (party identity enforced for CONTENT_AUTHOR) |
| `OPERATIONAL_ORDERS_RECONCILE` | Create/invalidate reconciliation |
| `OPERATIONAL_ORDERS_EDITORIAL_READY` | Validate + mark editorial package ready |

Privileged users bypass permission checks. Org scope enforced via `scope.py`.

---

## API matrix

See `data/OO-IMP-002-api-matrix.csv`.

---

## Provenance / audit events

| Event | Audit action |
|---|---|
| Translation requested | `TRANSLATION_REQUESTED` |
| Translator assigned | `TRANSLATOR_ASSIGNED` |
| Assignment accepted | `ASSIGNMENT_ACCEPTED` |
| Translation started | `TRANSLATION_STARTED` |
| Translation completed | `TRANSLATION_COMPLETED` |
| Confirmation created | `CONFIRMATION_CREATED` |
| Confirmation revoked | `CONFIRMATION_REVOKED` |
| Confirmation superseded | `CONFIRMATION_SUPERSEDED` |
| Reconciliation created | `RECONCILIATION_CREATED` |
| Reconciliation invalidated | `RECONCILIATION_INVALIDATED` |
| Stage transition | `WORKSPACE_STAGE_CHANGED` |
| Editorial package ready | `EDITORIAL_PACKAGE_READY` |
| Gate failed | `EDITORIAL_PACKAGE_VALIDATION_FAILED` |

Provenance: `TRANSLATION` action on translated text create/update.

---

## Concurrency model

All mutating commands accept `expected_version` (workspace and/or entity version).

409 with `OO_VERSION_CONFLICT` / `OO_WORKSPACE_VERSION_CONFLICT` on mismatch.

---

## Migration

`x8y9z0a1b2c3_oo_imp_002_content_confirmation_translation.py`

- Extends workspace stage CHECK
- Extends audit/provenance action CHECKs
- Creates 3 new tables with indexes and partial unique constraint
- Seeds 5 new permissions

---

## Test evidence

See `data/OO-IMP-002-test-coverage.csv`.

Run: `pytest tests/operational_orders/ -q`

---

## Deferred scope

Document Aggregate, activation, signing, registration, archive, PDF/HTML, execution, frontend, notifications, machine translation, Personnel Orders.

---

## Readiness for next WP

When `EDITORIAL_PACKAGE_READY`:

- RU and KK effective texts exist
- Required confirmations for current fingerprints
- Reconciled block pairs for current versions
- Provenance and audit complete
- No DocumentId created

Next WP: editorial runtime handoff / official draft package (UDE-003 continuation).
