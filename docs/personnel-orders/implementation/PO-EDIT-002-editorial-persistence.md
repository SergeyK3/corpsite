# PO-EDIT-002 — Editorial Persistence, Generation API and Print ViewModel Integration

**Status:** Implemented  
**WP:** WP-PO-EDIT-002  
**Architecture:** [PO-EDIT-001](../architecture/PO-EDIT-001-editorial-document-model.md) (R1–R12 unchanged)  
**Migration:** Alembic `s3t4u5v6w7x8`

> Physical storage refined from wide-row draft to normalized block-row model in WP-PO-EDIT-002. Architectural semantics R1–R12 remain unchanged.

---

## 1. Final schema

### `personnel_order_editorial_blocks`

| Field | Notes |
|---|---|
| Unique | `(order_id, locale, block_type)` |
| `block_type` | `title` \| `preamble` \| `closing` |
| Texts | `generated_text`, `override_text` |
| Generator | `generator_key`, `generator_version`, `source_fingerprint` |
| `review_status` | `CURRENT` \| `STALE` \| `REVIEW_REQUIRED` \| `GENERATION_FAILED` |
| Audit | `generated_at`, `edited_at`, `edited_by_user_id`, `revision`, timestamps |

### `personnel_order_item_editorial_blocks`

| Field | Notes |
|---|---|
| Unique | `(order_item_id, locale, block_type)` |
| `block_type` | `body` \| `basis` |
| Same text/generator/review fields | + `basis_required` |

### `personnel_order_item_bases`

1:1 with item (`order_item_id` UNIQUE). Structured facts only — not JSONB-as-primary.

`personnel_order_localized_texts` kept as read fallback; not extended; new writes go to editorial tables only.

---

## 2. Review status semantics

| Status | Meaning |
|---|---|
| `CURRENT` | Generated matches current structured fingerprint; override absent, or override present with unchanged fingerprint |
| `STALE` | Override present and structured fingerprint changed without regenerate |
| `REVIEW_REQUIRED` | Regenerate kept override while fingerprint changed; or unsupported basis policy |
| `GENERATION_FAILED` | Last generate attempt failed |

Transitions:

- Successful generate, no override → `CURRENT`
- Regenerate with override + fingerprint change → keep override, set `REVIEW_REQUIRED`
- Structured write with override present → `STALE`
- Generator exception → `GENERATION_FAILED`

---

## 3. Fingerprint algorithm

`SHA-256` hex of canonical JSON:

- only structured fields that affect the specific block;
- stable key ordering;
- no timestamps / irrelevant fields;
- includes `generator_key` and `generator_version`;
- identical input → identical fingerprint.

Implementation: `app/services/personnel_orders_editorial/fingerprint.py`

---

## 4. Basis storage and `basis_required`

- Table `personnel_order_item_bases` (dedicated, 1:1).
- Policy resolver (`basis_policy.py`): P0 types `HIRE`, `TRANSFER`, `TERMINATION`, `CONCURRENT_DUTY_*` → `basis_required=true`.
- Unknown item type → fail-closed (`UNSUPPORTED_ITEM_TYPE` / review-required), never silently optional.

Default seed on generate: `PERSONAL_APPLICATION` with `subject_employee_id = item.employee_id` when missing.

---

## 5. Generator ownership

**Authority: backend** (`app/services/personnel_orders_editorial/generators.py`).

Package layout after implementation review:

```text
app/services/personnel_orders_editorial_service.py   # thin public facade
app/services/personnel_orders_editorial/
  generators.py / fingerprint.py / basis_policy.py / constants.py
  repository.py          # SQL persistence
  generation_service.py  # generate/regenerate orchestration
  ready_gate.py          # DRAFT→READY editorial validation
  fallback.py            # legacy localized_texts mapping
  mapper.py              # effective_text + API serialization
  audit.py               # security audit (no prose text)
  write_lock.py          # DRAFT-only editorial writes
  stale.py               # structured-change → STALE
  service.py             # get/patch/reset public commands
```

Frontend spike generators remain non-authoritative; print uses ViewModel effective text from API/DB, with deterministic TS templates only as last fallback when no editorial rows exist.

Contracts:

- `generate_order_block(...)`
- `generate_item_body(...)`
- `generate_basis_text(...)`

No React, no raw HTML input, no PDF-specific logic.

---

## 6. API

Prefix: `/directory/personnel-orders/{order_id}/…`  
Auth: same as detail/edit (`require_personnel_admin_or_403`).

| Method | Path | Notes |
|---|---|---|
| GET | `/editorial` | kk+ru blocks, effective, review_status, basis_required, editable |
| POST | `/editorial/generate` | initial + regenerate; optional scope; keeps overrides |
| PATCH | `/editorial/blocks/{block_id}` | override_text / clear_override; DRAFT only |
| POST | `/editorial/blocks/{block_id}/reset-to-generated` | clear override |

`effective_text = override_text ?? generated_text`

---

## 7. Lifecycle write-lock

| Status | Structured user write | Editorial user write |
|---|---|---|
| `DRAFT` | Allowed | Allowed |
| `READY_FOR_SIGNATURE` | Rejected | Rejected |
| `SIGNED` / `REGISTERED` / `VOIDED` | Rejected | Rejected |

Internal lifecycle/apply/void operations unchanged. return-to-DRAFT deferred to EDIT-005.

Enforcement: `EDITABLE_ORDER_STATUSES = {DRAFT}` in command service; UI `isEditablePersonnelOrderStatus` DRAFT-only.

---

## 8. READY gate

Before `DRAFT → READY_FOR_SIGNATURE`, for each of `kk` and `ru`:

- non-empty effective `title`, `preamble`;
- non-empty effective `body` for every active item;
- non-empty effective `basis` when `basis_required=true`;
- reject `GENERATION_FAILED`, unresolved `STALE`, unresolved `REVIEW_REQUIRED`, unsupported basis policy.

Failure → HTTP 422:

```json
{ "code": "READY_GATE_FAILED", "problems": [ { "code": "...", "locale": "ru", "block_type": "title", ... } ] }
```

No full document text in problems or audit logs.

---

## 9. Fallback priority (print ViewModel)

```text
new editorial override
→ new editorial generated
→ mapped legacy localized text (title/preamble only)
→ deterministic renderer fallback (personnelOrderPrintItemText / type titles)
```

Legacy `body_text` is not item-level SoT.

HTML preview and PDF share `PersonnelOrderPrintViewModel` + `buildPersonnelOrderPrintDocumentHtml`.

---

## 10. ViewModel integration

- Loaders (preview client + PDF server) fetch `GET …/editorial` (graceful null if unavailable).
- Title / preamble / item body / item basis use effective editorial when present.
- Signature, acknowledgements, watermarks remain structured/rendered.
- Override text escaped at HTML render (`escapePersonnelOrderPrintHtml`).

---

## 11. Audit events

Allowed in `security_audit_service`:

- `EDITORIAL_GENERATED`
- `EDITORIAL_REGENERATED`
- `EDITORIAL_OVERRIDE_UPDATED`
- `EDITORIAL_OVERRIDE_CLEARED`
- `EDITORIAL_MARKED_STALE`
- `READY_GATE_REJECTED`

Metadata: order_id, item_id, block_type, locale, result, generator_version, review_status — never full prose, FIO in generated text, IIN, raw payloads, auth headers.

---

## 12. Tests

| Area | Files |
|---|---|
| Fingerprint | `tests/test_wp_po_edit_002_fingerprint.py` |
| Basis policy | `tests/test_wp_po_edit_002_basis_policy.py` |
| Generators | `tests/test_wp_po_edit_002_generators.py` |
| Migration | `tests/test_wp_po_edit_002_migration.py` |
| API / lifecycle / gate | `tests/test_wp_po_edit_002_editorial_api.py` |
| ViewModel / print | `corpsite-ui/.../personnelOrderPrint.test.ts` (+ existing PDF tests) |

---

## 13. Out of scope (unchanged)

- Block editor UI (EDIT-003)
- return-to-DRAFT (EDIT-005)
- DB clause library (EDIT-004)
- Full FIO morphology / leave multi-period / ЭЦП / signed PDF storage

---

## 14. Operational notes

1. Apply `alembic upgrade head` (revision `s3t4u5v6w7x8`) before using editorial API.
2. Existing drafts: call `POST …/editorial/generate` before READY.
3. After READY, corrections require EDIT-005 return-to-DRAFT (not yet available).
4. Legacy localized write API still exists but is not the editorial SoT path.
