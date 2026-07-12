# OO-IMP-004 — Document Lifecycle: CREATED → READY_FOR_SIGNATURE

**Status:** Implemented (local), R1 integrity review complete  
**Revision:** `a1b2c3d4e5f6`  
**Down revision:** `z0a1b2c3d4e5`  
**Package:** `app/operational_orders/`  
**Depends on:** OO-IMP-003, OO-IMP-003A, OO-IMP-003B

Controlled transition of the official Operational Order document from post-promotion **CREATED** to pre-signature **READY_FOR_SIGNATURE**, with signing authority assignment, snapshot integrity gate, and append-only lifecycle audit.

---

## Scope

| In scope | Out of scope |
|---|---|
| `CREATED` → `READY_FOR_SIGNATURE` | Signing, registration, void |
| `READY_FOR_SIGNATURE` → `CREATED` (return from signature queue) | Version 2, Revision Command |
| Signing authority (historical) | Workspace unfreeze / content edit |
| Pre-signature validation OO401–OO416 | PDF/HTML, UI, notifications |
| Lifecycle audit | Personnel Orders changes |

---

## Lifecycle state model

OO maps UDE `DRAFT` to persistence status **`CREATED`** (post-promotion birth alias per OO-IMP-003A).

```text
Promotion complete
  → Document.status = CREATED
  → Workspace.stage = DOCUMENT_PROMOTED (frozen)
  → DocumentVersion.version_number = 1 (immutable)

Assign signing authority (required)
  → operational_order_signing_authority (ACTIVE)

Mark ready for signature
  → Document.status = READY_FOR_SIGNATURE
  → Document.version += 1 (aggregate optimistic version only)

Return to created (optional, pre-signature only)
  → Document.status = CREATED
  → Workspace remains DOCUMENT_PROMOTED
  → Official text unchanged
```

### Transition matrix

| From | To | Gate | Endpoint |
|---|---|---|---|
| `CREATED` | `READY_FOR_SIGNATURE` | Snapshot + authority + drift | `POST .../ready-for-signature` |
| `READY_FOR_SIGNATURE` | `READY_FOR_SIGNATURE` | Idempotent replay | same |
| `READY_FOR_SIGNATURE` | `CREATED` | Reason required | `POST .../return-to-created` |
| `CREATED` | `CREATED` | Idempotent (return) | same |

See [`data/OO-IMP-004-transition-matrix.csv`](data/OO-IMP-004-transition-matrix.csv).

### Return to CREATED decision

**Ratified P0:** `READY_FOR_SIGNATURE` → `CREATED` is implemented per UDE-005 `RETURN_TO_DRAFT` semantics (mapped to OO `CREATED`).

- Mandatory `reason`
- Does **not** unfreeze workspace
- Does **not** allow official_text mutation
- Serves only to remove document from signature queue before signing exists
- Content changes require future Revision Command (OO-IMP-005+)

---

## Signing authority model

Table: `operational_order_signing_authority` (append-only history; no physical delete).

| Field | Purpose |
|---|---|
| `document_id`, `document_version_id` | Scoped to current immutable snapshot |
| `authority_party_type/reference/display_name` | `PartyReference` semantics |
| `authority_position_id`, `authority_org_unit_id` | Optional directory anchors |
| `authority_basis` | Optional legal basis text |
| `status` | `ACTIVE` / `SUPERSEDED` / `REVOKED` |
| `version` | Row optimistic version |

Partial unique index: one `ACTIVE` row per `document_id`.

Reassignment: previous `ACTIVE` → `SUPERSEDED`; new row `ACTIVE`; audit `SIGNING_AUTHORITY_SUPERSEDED` + `SIGNING_AUTHORITY_ASSIGNED`.

---

## Readiness validation (OO401–OO416)

Layer: `app/operational_orders/validation/signature_readiness_validation.py`

| Code | Rule |
|---|---|
| OO401 | Document not in CREATED (for mark-ready path) |
| OO402 | Current version missing |
| OO403 | Multiple current versions |
| OO404 | RU localization missing |
| OO405 | KK localization missing |
| OO406 | Localization fingerprint mismatch |
| OO407 | Snapshot fingerprint mismatch |
| OO408 | Signing authority missing |
| OO409 | Signing authority invalid / inactive / version mismatch |
| OO410 | Document aggregate version stale |
| OO411 | Already READY_FOR_SIGNATURE (mark-ready only) |
| OO412 | Document status conflict |
| OO413 | Current version document_id mismatch |
| OO414 | Promotion incomplete / inconsistent |
| OO415 | Workspace not DOCUMENT_PROMOTED / link inconsistent |
| OO416 | Workspace drift → revision required |

Returns shared `ValidationResult` / `ValidationIssue`.

See [`data/OO-IMP-004-validation-rules.csv`](data/OO-IMP-004-validation-rules.csv).

---

## Snapshot integrity gate

Source of truth: **Document Version + Document Localizations** (not live workspace).

Before `READY_FOR_SIGNATURE`:

1. Exactly one `is_current` version belonging to document
2. RU and KK `official_text` present
3. Per-block `content_fingerprint` matches `official_text`
4. `snapshot_fingerprint` matches computed localization fingerprint
5. Workspace `DOCUMENT_PROMOTED`, promotion `COMPLETED`, promotion.document_id match
6. Active signing authority for current version
7. No workspace fingerprint drift vs `created_from_workspace_fingerprint`

---

## Drift / revision policy

**Authoritative gate:** if live workspace fingerprint ≠ promotion fingerprint → **OO416** blocks `READY_FOR_SIGNATURE`.

- Document snapshot remains source of truth for content
- Live workspace is not used for official text
- No administrative bypass in P0
- Resolution deferred to future Revision Command

---

## Authorization

| Permission | Capability |
|---|---|
| `OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ` | Read readiness / authority |
| `OPERATIONAL_ORDERS_ASSIGN_SIGNING_AUTHORITY` | Assign / supersede authority |
| `OPERATIONAL_ORDERS_MARK_READY_FOR_SIGNATURE` | Mark ready |
| `OPERATIONAL_ORDERS_RETURN_FROM_SIGNATURE` | Return to CREATED |

Org scope via `submitting_org_unit_id`; privileged bypass via `DIRECTORY_PRIVILEGED_USER_IDS`. Record creator does not bypass org scope. Content author does not receive lifecycle manage rights by default.

See [`data/OO-IMP-004-permission-matrix.csv`](data/OO-IMP-004-permission-matrix.csv).

---

## API matrix

| Method | Path | Permission |
|---|---|---|
| GET | `/api/operational-orders/documents/{id}` | document read (+ lifecycle enrichment) |
| GET | `/api/operational-orders/documents/{id}/signature-readiness` | SIGNATURE_READINESS_READ |
| GET | `/api/operational-orders/documents/{id}/signing-authority` | SIGNATURE_READINESS_READ |
| POST | `/api/operational-orders/documents/{id}/signing-authority` | ASSIGN_SIGNING_AUTHORITY |
| POST | `/api/operational-orders/documents/{id}/validate-ready-for-signature` | SIGNATURE_READINESS_READ |
| POST | `/api/operational-orders/documents/{id}/ready-for-signature` | MARK_READY_FOR_SIGNATURE |
| POST | `/api/operational-orders/documents/{id}/return-to-created` | RETURN_FROM_SIGNATURE |

All mutating commands accept `expected_version` (document aggregate version).

See [`data/OO-IMP-004-api-matrix.csv`](data/OO-IMP-004-api-matrix.csv).

---

## Optimistic concurrency

- Field: `OperationalOrderDocument.version` (aggregate header)
- Mutations: assign authority, mark ready, return to created
- Conflict: HTTP **409** `OO_DOCUMENT_VERSION_CONFLICT`
- **Not** incremented: `OperationalOrderDocumentVersion.version_number` (stays 1)

---

## Idempotency

Check order for mutating commands: **expected_version conflict → business/idempotent branch → mutation**.

| Command | Behavior |
|---|---|
| `ready-for-signature` when already READY | HTTP **200**, `idempotent_replay=true` if `expected_version` matches; **no new audit**, version unchanged |
| `ready-for-signature` stale version | HTTP **409** `OO_DOCUMENT_VERSION_CONFLICT` (before idempotent replay) |
| Identical authority reassignment | HTTP **200**, `idempotent_replay=true`; no new authority row or audit |
| `return-to-created` from CREATED | HTTP **200**, `idempotent_replay=true` only when `expected_version` matches |
| `return-to-created` stale version | HTTP **409** `OO_DOCUMENT_VERSION_CONFLICT` |

`POST .../validate-ready-for-signature` is validation-only; default `record_audit=false`.

---

## Return to CREATED — readiness projection policy

On `READY_FOR_SIGNATURE` → `CREATED`:

- `ready_for_signature_at` / `ready_for_signature_by_user_id` **cleared** on document header
- Prior readiness preserved in lifecycle audit (`DOCUMENT_READY_FOR_SIGNATURE`)
- Signing authority stays `ACTIVE`; workspace stays `DOCUMENT_PROMOTED`

---

## Permission migration convention

Matches OO-IMP-001/002/003: `access_roles` seed via `ON CONFLICT DO UPDATE`; no automatic user grants; downgrade removes grants then roles.

---

## Lifecycle audit

Table: `operational_order_lifecycle_audit` (append-only).

Mutation actions: `SIGNING_AUTHORITY_ASSIGNED`, `SIGNING_AUTHORITY_SUPERSEDED`, `DOCUMENT_READY_FOR_SIGNATURE`, `DOCUMENT_RETURNED_TO_CREATED`.

Optional diagnostic actions (off by default): `SIGNATURE_READINESS_VALIDATED`, `SIGNATURE_READINESS_FAILED` via `record_audit=true`.

Idempotent replay and failed mutations do **not** append audit rows. `document_version_before/after` = aggregate header version.

Promotion audit and draft audit are **not** extended.

---

## Migration

- **Revision:** `a1b2c3d4e5f6`
- **Down:** `z0a1b2c3d4e5`
- Adds: `operational_order_signing_authority`, `operational_order_lifecycle_audit`
- Extends: `operational_order_documents.ready_for_signature_at`, `ready_for_signature_by_user_id`
- Seeds: four lifecycle permissions
- Existing CREATED documents remain CREATED

Verified: `upgrade` → `downgrade z0a1b2c3d4e5` → `upgrade`.

---

## Tests

| File | Coverage |
|---|---|
| `test_lifecycle_readiness.py` | Readiness, mark ready, idempotency, version conflict, auth |
| `test_signing_authority.py` | Assign, supersede, idempotent assign, permissions |
| `test_return_to_created.py` | Return transition, reason, frozen workspace |
| `test_oo_imp_004_r1_integrity.py` | R1 idempotency order, audit semantics, snapshot immutability |

Regression: `tests/operational_orders/` (117 passed), `tests/document_engine/` (147 passed), `tests/personnel_orders/characterization/` (42 passed).

OO-IMP-004 dedicated tests: **27** (8 + 6 + 4 + 9).

See [`data/OO-IMP-004-test-coverage.csv`](data/OO-IMP-004-test-coverage.csv).

---

## Deferred scope

- Actual signing / e-signature / certificate verification
- Registration, official number, journal
- Version 2 / Revision Command (OO-IMP-005)
- Business Intent / superseding lineage
- Frontend (OO-UI-001)
- Execution projection

---

## Readiness

| Next WP | Ready |
|---|---|
| **OO-UI-001** | Yes — API surfaces readiness, authority, lifecycle status |
| **OO-IMP-005** | Yes — signing workflow can attach to READY_FOR_SIGNATURE documents |
