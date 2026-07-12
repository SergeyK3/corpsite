# UDE-005 — Lifecycle State Model

WP: **UDE-005** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Evidence: UDE-001 T022; UDE-004 bootstrap; ADR-UDE-004; PO production lifecycle

---

## 1. Purpose

Define the **Shared Document Lifecycle State Model** — the five lifecycle states and orthogonal archive dimension applicable to all UDE document specializations.

---

## 2. Shared Lifecycle States

| State | Code | Terminal? |
|---|---|---|
| Draft | `DRAFT` | No |
| Ready for Signature | `READY_FOR_SIGNATURE` | No |
| Signed | `SIGNED` | No |
| Registered | `REGISTERED` | No |
| Voided | `VOIDED` | **Yes** |

**Not a lifecycle state:** `ARCHIVED` — orthogonal archive flag (`ArchiveState`: ACTIVE | ARCHIVED).

---

## 3. State Definitions

### 3.1 DRAFT

| Aspect | Rule |
|---|---|
| **Semantic meaning** | Activated document under predmetnaya preparation; editorial and semantic work continues |
| **Entry** | Document Activation (UDE-004) — only bootstrap state |
| **Allowed** | Semantic edit, editorial edit, locale edit, regeneration, attachment edit, validation, MarkReady, Cancel, Archive (if policy) |
| **Forbidden** | Sign, Register, Annul |
| **Outgoing** | → READY_FOR_SIGNATURE; → VOIDED (CANCEL) |
| **Localization** | Mandatory locales may be CURRENT or STALE; STALE blocks READY |
| **Validation** | E* attached; L* on transition commands |
| **Mutability** | Baseline v1 **mutable** (UDE-004 IS1) |
| **Snapshot** | Mutable effective baseline; no signed snapshot |
| **Journal** | Visible (default) |

### 3.2 READY_FOR_SIGNATURE

| Aspect | Rule |
|---|---|
| **Semantic meaning** | Editorial work complete; mandatory locales ready; blocking validations passed; document prepared for signing |
| **Entry** | MarkReady from DRAFT |
| **Allowed** | View, print preview, ReturnToDraft, Sign, Cancel, limited metadata (policy) |
| **Forbidden** | Semantic/editorial/locale content edit, regeneration, item edit, attachment content edit |
| **Outgoing** | → DRAFT (return); → SIGNED; → VOIDED (CANCEL) |
| **Localization** | All mandatory locales CURRENT; REVIEW_REQUIRED blocks without waiver |
| **Validation** | L005, L006 at entry; L* at sign/return |
| **Mutability** | **Content read-only**; write-lock engaged |
| **Snapshot** | Pre-sign baseline frozen pending sign |
| **Journal** | Visible |

**Target architecture (PO READY editability drift):** READY is **not** editable for content. Any correction requires explicit ReturnToDraft. PO docs mentioning READY edit are **debt** — backend already enforces DRAFT-only edit.

### 3.3 SIGNED

| Aspect | Rule |
|---|---|
| **Semantic meaning** | Legally significant boundary; immutable signed snapshot created |
| **Entry** | SignDocument from READY |
| **Allowed** | View, print, Register, Annul, Archive (if policy) |
| **Forbidden** | Content edit, regeneration, Cancel |
| **Outgoing** | → REGISTERED; → VOIDED (ANNUL) |
| **Localization** | Representations **frozen** in signed snapshot |
| **Validation** | L* registration and annul gates |
| **Mutability** | Content **immutable**; registration fields pending |
| **Snapshot** | **Signed Immutable Snapshot** (ADR-UDE-009) |
| **Journal** | Visible |

### 3.4 REGISTERED

| Aspect | Rule |
|---|---|
| **Semantic meaning** | Officially registered; registration number assigned |
| **Entry** | RegisterDocument from SIGNED |
| **Allowed** | View, print, Annul, Archive, Execution Projection (if policy) |
| **Forbidden** | Content edit, Cancel, lifecycle restore |
| **Outgoing** | → VOIDED (ANNUL) only |
| **Localization** | Frozen per signed snapshot |
| **Validation** | L009, specialization projection gates |
| **Mutability** | Content and registration fields **immutable** |
| **Snapshot** | Signed snapshot + registration metadata |
| **Journal** | Official entry; closed-filter per policy |

### 3.5 VOIDED

| Aspect | Rule |
|---|---|
| **Semantic meaning** | Terminal; document voided with `void_kind` and reason; **not deleted** |
| **Entry** | Cancel (DRAFT/READY) or Annul (SIGNED/REGISTERED) |
| **Allowed** | View, print, audit, Archive |
| **Forbidden** | Any mutation, lifecycle restore, repeat void |
| **Outgoing** | None (terminal) |
| **Stored** | void_kind, reason, actor, timestamp, source_state, snapshot ref |
| **Mutability** | Fully immutable |
| **Journal** | Visible per policy; may hide in closed journal |

---

## 4. Archive Orthogonality

```text
DocumentLifecycleState  ×  ArchiveState

Lifecycle: DRAFT | READY | SIGNED | REGISTERED | VOIDED
Archive:   ACTIVE | ARCHIVED
```

| ArchiveState | Meaning |
|---|---|
| ACTIVE | Default; lifecycle transitions allowed per state |
| ARCHIVED | Mutations blocked; view/print/audit/restore only |

Archive does **not** change lifecycle status. Audit records `archive_state_before/after`.

---

## 5. PO Mapping

| UDE state | PO `status` column | Match |
|---|---|---|
| DRAFT | `DRAFT` | ✓ |
| READY_FOR_SIGNATURE | `READY_FOR_SIGNATURE` | ✓ |
| SIGNED | `SIGNED` | ✓ |
| REGISTERED | `REGISTERED` | ✓ |
| VOIDED | `VOIDED` | ✓ |
| ARCHIVED | `archived_at IS NOT NULL` | ✓ orthogonal |

---

*Matrix: [`data/UDE-005-state-operation-matrix.csv`](./data/UDE-005-state-operation-matrix.csv)*  
*Diagram: [`diagrams/shared-document-lifecycle.svg`](./diagrams/shared-document-lifecycle.svg)*
