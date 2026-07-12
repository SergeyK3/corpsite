# UDE-005 — Cancel, Annul and Archive Model

WP: **UDE-005** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Evidence: UDE-000 terminology; PO void_kind; WP-PO-LC-DEL-004/005

---

## 1. Purpose

Define **void_kind** semantics (CANCEL vs ANNUL), VOIDED terminal state, and **orthogonal Archive** model.

---

## 2. Void Kind — Ratified Model

```text
status = VOIDED
void_kind ∈ { CANCEL, ANNUL }
```

Single lifecycle terminal state **VOIDED** with discriminating `void_kind` — not separate CANCELLED/ANNULLED statuses.

---

## 3. CANCEL vs ANNUL

| Aspect | CANCEL | ANNUL |
|---|---|---|
| **Meaning** | Project termination; unsigned document abandoned | Signed/registered document declared invalid |
| **Historical fact** | Draft never became official | Official act invalidated; record retained |
| **Typical source** | DRAFT, READY_FOR_SIGNATURE | SIGNED, REGISTERED |
| **Signed snapshot** | Not created / not required | **Preserved** immutably |
| **Registration number** | Never assigned or N/A | **Retained** on record |
| **Execution projection** | Not created | Voided or compensating process required |
| **Compensating order** | Not required | May be required (specialization; not designed here) |

---

## 4. Applicability Matrix

| Source state | void_kind | Command |
|---|---|---|
| DRAFT | CANCEL | CancelDocument |
| READY_FOR_SIGNATURE | CANCEL | CancelDocument |
| SIGNED | ANNUL | AnnulDocument |
| REGISTERED | ANNUL | AnnulDocument |
| VOIDED | — | Idempotent error |

**L011:** CANCEL from SIGNED/REGISTERED → `VOID_KIND_NOT_APPLICABLE`.  
**L011:** ANNUL from DRAFT/READY → `VOID_KIND_NOT_APPLICABLE`.

---

## 5. VOIDED State Storage

| Field | Required | Notes |
|---|---|---|
| void_kind | Yes | CANCEL \| ANNUL |
| void_reason | Yes | Text or reason_code + text |
| voided_by / actor | Yes | Audit context |
| voided_at / timestamp | Yes | |
| source_state | Yes | previous_status in audit |
| supporting_reference | Optional | Link to replacement order |
| affected_snapshot | Yes | snapshot ref if SIGNED existed |

**VOIDED ≠ deleted.** Document remains in registry with full audit trail.

---

## 6. VOIDED Effects

| Concern | Rule |
|---|---|
| Visibility | Readable; journal may filter closed/voided |
| Mutability | None |
| Archive | Allowed (PO: VOIDED archivable) |
| Lifecycle restore | **No** — terminal |
| Registration number | Retained; not reused |
| Signed snapshot | Unchanged if existed |
| Execution projection | Void cascade (PO: employee_events VOIDED + rollback) |

---

## 7. Archive Orthogonality

### 7.1 Why Archive Is Not a Lifecycle Status

| Reason | Detail |
|---|---|
| Independent dimension | Document may be REGISTERED and ACTIVE or ARCHIVED |
| Restore without lifecycle change | Restore returns to same SIGNED/REGISTERED/VOIDED |
| Journal semantics | Hide completed records without voiding |
| PO production proof | `archived_at` orthogonal to `status` |

### 7.2 Archive States

| State | Code |
|---|---|
| Active | `ACTIVE` (archived_at = null) |
| Archived | `ARCHIVED` (archived_at set) |

### 7.3 Archivable Lifecycle States (default)

| State | Archivable default |
|---|---|
| DRAFT | Policy-dependent (usually no) |
| READY | Policy-dependent (usually no) |
| SIGNED | Policy-dependent |
| REGISTERED | **Yes** |
| VOIDED | **Yes** |

PO implements: REGISTERED, VOIDED only.

### 7.4 Archived Immutability

After archive, **only** permitted:

- view
- print
- audit
- restore

Any mutation → `DOCUMENT_ARCHIVED` conflict. PO: `assert_order_not_archived` on all write paths.

### 7.5 Archive and Execution

Archive does **not** automatically cancel execution projection. Execution may continue unless annulled separately.

---

## 8. Audit Events

| Action | Audit action code |
|---|---|
| Cancel | CANCEL → VOIDED |
| Annul | ANNUL → VOIDED |
| Archive | ARCHIVE (status unchanged) |
| Restore | RESTORE (status unchanged) |

---

*Diagram: [`diagrams/cancel-annul-archive.svg`](./diagrams/cancel-annul-archive.svg)*
