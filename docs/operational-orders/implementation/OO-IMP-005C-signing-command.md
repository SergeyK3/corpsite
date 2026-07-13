# OO-IMP-005C — Signing Command

**Status:** Accepted
**Revision:** `d4e5f6a7b8c9`
**Down revision:** `c3d4e5f6a7b8`
**Package:** `app/operational_orders/`
**Depends on:** OO-IMP-005B, OO-IMP-004

**Acceptance date:** 2026-07-13

**Accepted scope:**
- READY_FOR_SIGNATURE → SIGNED command;
- immutable signing attestation;
- authority matching;
- privileged override with reason;
- command permission definition without grants;
- idempotency;
- atomic lifecycle/audit persistence;
- replay integrity guards.

Atomic workflow attestation command:

```text
READY_FOR_SIGNATURE → SIGNED
```

No ЭЦП integration in this work package.

---

## Scope

| In scope | Out of scope |
|---|---|
| `POST /documents/{id}/sign` | Registration, publication, PDF |
| `OPERATIONAL_ORDERS_SIGN` permission seed | OO-SEC-002 grants |
| Immutable signing attestation record | Frontend UI |
| Idempotency ledger | Personnel Orders changes |
| Append-only `DOCUMENT_SIGNED` audit | Cryptographic signature |

---

## Command contract

**Endpoint:** `POST /api/operational-orders/documents/{document_id}/sign`

**Request:**

```json
{
  "idempotency_key": "string",
  "override_reason": "string | null",
  "expected_version": "integer | null"
}
```

**Response:** `SignDocumentResultOut`

- `document` — standard document detail
- `signing_attestation` — immutable attestation summary
- `idempotent_replay` — `true` on exact replay

Server sets: `status`, `signed_at`, `signed_by_user_id`, header signatory snapshot fields.

---

## Authorization

| Path | Rule |
|---|---|
| Normal signing | `OPERATIONAL_ORDERS_SIGN` + actor matches assigned authority |
| Privileged override | `is_privileged` + non-empty `override_reason` |
| Workspace read | `OPERATIONAL_ORDERS_INTAKE_READ` does **not** authorize signing |

Authority matching (`PERSON`): `authority_party_reference` equals actor `user_id` or linked `employee_id`.

---

## Attestation authority

### Authority Matrix

| Concern | Authority |
|---|---|
| Assigned authority before signing | `operational_order_signing_authority` |
| Actual signing attestation | `operational_order_signing_attestations` |
| Header signatory fields | Denormalized projection on `operational_order_documents` |
| Signing history | `operational_order_lifecycle_audit` (`DOCUMENT_SIGNED`) |

**Authoritative storage:** `operational_order_signing_attestations` (one row per signed document).

Header mirrors display fields on `operational_order_documents`:

- `signing_authority_id`
- `signatory_display_name`
- `signatory_party_reference`
- `signatory_position`

Full historical payload retained in `snapshot_json` + lifecycle audit `metadata_json`.

Read paths:
- `SignDocumentResultOut.signing_attestation` — from attestation table
- `DocumentSummaryOut.signatory_*` — denormalized header projection only
- Authorization and pre-sign validation — active `operational_order_signing_authority`, never header mirror

---

## Verification Review — OO-IMP-005C-R1

**Date:** 2026-07-13

### Authority vs projection

- Signing command copies active authority into attestation row and header mirror atomically.
- Business validation and authorization use active signing authority, not `signatory_*` header fields.
- Header mirror changes after signing do not alter attestation row.
- Audit is append-only history; attestation table remains authoritative.

### Permission seed without grants

Migration `d4e5f6a7b8c9` upgrade:
- `INSERT INTO public.access_roles` for `OPERATIONAL_ORDERS_SIGN` only
- No `INSERT INTO public.access_grants` in upgrade
- No role/permission mass assignment

Downgrade deletes grants tied to `OPERATIONAL_ORDERS_SIGN` role (if any were added later), then removes the access role.

### Transaction atomicity

`sign_document()` uses one `engine.begin()` transaction. `_append_lifecycle_audit(conn, ...)` uses the same connection — no nested commit.

Fault-injection (audit failure after document update + attestation + idempotency writes) confirms full rollback: document remains `READY_FOR_SIGNATURE`, no attestation, no idempotency row, no `DOCUMENT_SIGNED` audit.

### Orphan prevention

- DB: FK + `UNIQUE(document_id)` on attestations; no cross-table status CHECK.
- Service: attestation insert only inside signing transaction after successful document update.
- Orphan attestation without post-sign document state: not creatable via service path; manual SQL possible but treated as corruption.
- `SIGNED` without attestation: re-sign blocked; idempotency replay requires attestation row + post-sign document metadata.

### Attestation immutability

- Insert-only in service (no UPDATE/upsert on attestation table).
- `UNIQUE(document_id)` prevents second attestation.
- Exact replay reads existing row without mutation.

### Service invariant for `SIGNED`

After successful command (non-replay):
- `status = SIGNED`
- `signed_at IS NOT NULL`
- `signed_by_user_id IS NOT NULL`
- attestation row exists

Exact replay additionally requires post-sign document state and signing metadata before returning success.

### Concurrency behavior

| Case | Observed behavior |
|---|---|
| Same document + same idempotency key | One success; second exact replay (200) or controlled 409 under race |
| Same document + different keys | One success; second `OO_DOCUMENT_ALREADY_SIGNED`; one attestation; one audit |

Optimistic `version` + `status` guards on document update; unique idempotency key; domain errors mapped — no raw `IntegrityError` to clients.

---

## Idempotency

**Ledger:** `operational_order_lifecycle_command_idempotency`

| Case | Behavior |
|---|---|
| Same key + same document + same payload hash | Exact replay; no new audit |
| Same key + different document/payload | `409 OO_SIGN_IDEMPOTENCY_CONFLICT` |
| Document already `SIGNED` without matching key | `409 OO_DOCUMENT_ALREADY_SIGNED` |

---

## Transaction semantics

Single `engine.begin()` transaction:

1. Resolve idempotency replay
2. Load document context
3. Validate `READY_FOR_SIGNATURE` preconditions
4. Validate readiness (OO401–416)
5. Evaluate UDE `SIGN` gate
6. Resolve authorization (normal or privileged override)
7. Optimistic update document header → `SIGNED`
8. Insert attestation row
9. Insert idempotency ledger row
10. Append `DOCUMENT_SIGNED` audit

---

## Error codes

| Code | HTTP |
|---|---|
| `OO_DOCUMENT_NOT_FOUND` | 404 |
| `OO_FORBIDDEN` | 403 |
| `OO_SIGN_AUTHORITY_MISMATCH` | 403 |
| `OO_SIGN_OVERRIDE_REASON_REQUIRED` | 422 |
| `OO_DOCUMENT_STATUS_CONFLICT` | 409 |
| `OO_DOCUMENT_ALREADY_SIGNED` | 409 |
| `OO_SIGN_IDEMPOTENCY_CONFLICT` | 409 |
| `OO_DOCUMENT_VERSION_CONFLICT` | 409 |
| `OO_VALIDATION_BLOCKED` | 409 |

---

## Migration

`d4e5f6a7b8c9_oo_imp_005c_signing_command.py`

- Header signatory snapshot columns
- `operational_order_signing_attestations`
- `operational_order_lifecycle_command_idempotency`
- Extends lifecycle audit CHECK with `DOCUMENT_SIGNED`
- Seeds `OPERATIONAL_ORDERS_SIGN` in `access_roles` (no mass grants)

---

## Tests

`tests/operational_orders/test_oo_imp_005c_signing_command.py`

Covers success, authorization, state guards, idempotency, privileged override, regression on mark-ready/return, and R1 verification (rollback, replay corruption guard, authority source, migration grants, attestation immutability).

---

## Known limitations

- Workflow attestation only — no ЭЦП, no scanned signature upload
- No registration/publication commands
- Privileged override requires explicit `override_reason`
- Role grants for `OPERATIONAL_ORDERS_SIGN` are not auto-provisioned beyond permission definition seed
