# UDE-006 — Characterization and Compatibility Testing

WP: **UDE-006** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Mode: **Strategy only — no tests written in UDE-006**

---

## 1. Purpose

Define **characterization test strategy** and **compatibility harness** required before any PO extraction or shared write-path change.

---

## 2. Minimum Baseline Before Refactoring

| Priority | Category | Must pass |
|---|---|---|
| P0 | Lifecycle transitions | DRAFT→READY→REGISTERED→VOIDED paths |
| P0 | Cancel/annul void_kind | CANCEL vs ANNUL by source status |
| P0 | Archive immutability | Writes rejected when archived |
| P0 | Authority scope | CANCEL_OWN, CANCEL_SCOPE |
| P0 | Journal filter | Default hides closed; include_closed works |
| P1 | Locale editing | RU/KK independent effective |
| P1 | Regeneration/override | Generated vs effective semantics |
| P1 | Employee event chain | Apply + void + ADR-035 |
| P1 | Register shortcut | From DRAFT and READY |
| P2 | HTML snapshot | Print VM structure |
| P2 | PDF semantic | Structure not pixel-perfect |
| P2 | Adapter parity | Legacy vs adapter view (UDE-007) |

---

## 3. Test Categories (18)

See [`data/UDE-006-characterization-test-matrix.csv`](./data/UDE-006-characterization-test-matrix.csv)

| ID | Category |
|---|---|
| T001–T005 | API, lifecycle, authority, archive, cancel/annul |
| T006–T007 | Locale, regeneration |
| T008–T009 | HTML, PDF semantic |
| T010–T012 | Journal, audit, employee events |
| T013–T016 | Register, ready gate, print language, applied badge |
| T017–T018 | Synthetic activation, adapter parity |

---

## 4. Compatibility Harness (Conceptual)

```text
┌─────────────────┐     ┌──────────────────────┐
│ Legacy PO Path  │     │ Shared Adapter Path  │
│ (authoritative) │     │ (read projection)    │
└────────┬────────┘     └──────────┬───────────┘
         │                         │
         └───────────┬─────────────┘
                     ▼
            ┌────────────────┐
            │ Compare Views  │
            └────────────────┘
```

### 4.1 Compared Dimensions

| Dimension | Acceptance |
|---|---|
| lifecycle view | status, void_kind, archive identical |
| effective text | RU/KK byte-identical |
| print VM | structural equivalence |
| audit representation | no fabricated rows |
| error behavior | same codes for same inputs |
| permissions | same allow/deny decisions |

### 4.2 Acceptance Criterion

**Same observable behavior** — adapter path must not change user-visible outcomes.

Diagram: [`diagrams/characterization-harness.svg`](./diagrams/characterization-harness.svg)

---

## 5. Existing Test Coverage

PO already has substantial coverage:

- `test_wp_po_lc_del_004_cancel_api.py`
- `test_wp_po_lc_del_005_archive_api.py`
- `test_wp_po_lc_del_005a_archived_immutability_api.py`
- `test_wp_po_edit_002_editorial_api.py`
- `test_wp_po_006_e2e_validation.py`

**Gap:** HTML/PDF semantic golden, adapter parity (UDE-007 scope)

---

## 6. UDE-007 Test Obligations

UDE-007 (first code WP) must add:

1. Characterization test inventory document
2. Adapter parity test stubs (may skip until adapters exist)
3. CI gate: no behavior change on existing tests

---

*Matrix: [`data/UDE-006-characterization-test-matrix.csv`](./data/UDE-006-characterization-test-matrix.csv)*
