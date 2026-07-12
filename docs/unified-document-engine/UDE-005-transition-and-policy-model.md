# UDE-005 — Transition and Policy Model

WP: **UDE-005** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Purpose

Define **lifecycle transitions**, command intents, preconditions, and policy coordination for Shared Lifecycle Core.

---

## 2. Transition Overview

```text
                    ┌─────────────┐
                    │   DRAFT     │◄── Activation (UDE-004)
                    └──────┬──────┘
              MarkReady    │    Cancel
                           ▼
                  ┌────────────────┐
         Return   │ READY_FOR_     │  Cancel
         ToDraft  │   SIGNATURE    │
              └────┤                ├────► VOIDED (CANCEL)
                   └────────┬───────┘
                      Sign  │
                            ▼
                      ┌──────────┐
                      │  SIGNED  │──── Annul ────┐
                      └────┬─────┘               │
                    Register│                   │
                            ▼                   ▼
                    ┌──────────────┐      ┌──────────┐
                    │  REGISTERED  │─Annul►│  VOIDED  │
                    └──────────────┘      │(ANNUL)   │
                                          └──────────┘

Archive / Restore: orthogonal — any archivable lifecycle state
```

---

## 3. Shared Transitions

| ID | Transition | Command | Shared |
|---|---|---|---|
| T001 | DRAFT → READY | MarkReady | ✓ |
| T002 | READY → DRAFT | ReturnToDraft | ✓ |
| T003 | READY → SIGNED | SignDocument | ✓ |
| T004 | SIGNED → REGISTERED | RegisterDocument | ✓ |
| T005 | DRAFT → VOIDED | CancelDocument | ✓ |
| T006 | READY → VOIDED | CancelDocument | ✓ |
| T007 | SIGNED → VOIDED | AnnulDocument | ✓ |
| T008 | REGISTERED → VOIDED | AnnulDocument | ✓ |
| T009 | * → ARCHIVED | ArchiveDocument | ✓ |
| T010 | ARCHIVED → ACTIVE | RestoreDocument | ✓ |

---

## 4. Specialization-Specific Transitions

| Pattern | Specialization | Notes |
|---|---|---|
| READY → SIGNED/REGISTERED direct | Personnel Orders adapter | `register_personnel_order` skips separate Sign; UDE-006 adapter maps to T003+T004 or shortcut |
| Register from DRAFT | PO legacy | PO allows register from DRAFT and READY — adapter treats as MarkReady+Sign+Register pipeline |
| Apply (execution) | PO only | Not a document lifecycle transition — Execution Projection |

---

## 5. Command Model

| Command | Input concept | Atomic changes |
|---|---|---|
| **MarkReady** | document_id, expected_version, actor | status→READY; write_lock; audit |
| **ReturnToDraft** | document_id, expected_version, actor, reason? | status→DRAFT; write_lock release; audit |
| **SignDocument** | document_id, signer_ref, expected_version, actor | status→SIGNED; signed_snapshot; audit |
| **RegisterDocument** | document_id, registration_metadata, expected_version, actor | status→REGISTERED; number; audit |
| **CancelDocument** | document_id, reason_code, reason_text, actor | status→VOIDED; void_kind=CANCEL; audit |
| **AnnulDocument** | document_id, void_reason, actor | status→VOIDED; void_kind=ANNUL; projection hook; audit |
| **ArchiveDocument** | document_id, reason_code, reason_text, actor | archived_at; audit; no status change |
| **RestoreDocument** | document_id, actor | archived_at cleared; audit |

---

## 6. Transition Policy Layers

| Layer | Responsibility |
|---|---|
| **LifecycleStateMachine** | Allowed transitions (domain) |
| **LifecycleValidation** | L-series gates |
| **AuthorityPolicy** | Capability check |
| **SpecializationPolicy** | Kind hooks (L021–L025) |
| **ArchiveGuard** | L004 on all mutations |
| **ConcurrencyGuard** | L013, L014 |

---

## 7. Per-Transition Detail

### 7.1 MarkReady (T001)

| Field | Value |
|---|---|
| Preconditions | DRAFT; not archived; E* clear; L005 CURRENT locales; L006 no blockers |
| Actor | mark_ready capability; org scope |
| Side effects | Write-lock READY; optional notification |
| Audit | DOCUMENT_READY_FOR_SIGNATURE |
| Snapshot | Baseline unchanged |
| Rollback | ReturnToDraft |
| Idempotency | Already READY → noop or conflict per policy |

### 7.2 ReturnToDraft (T002)

| Field | Value |
|---|---|
| Preconditions | READY; return policy allows |
| Actor | return_to_draft capability (operator or head) |
| Side effects | Write-lock released |
| Audit | DOCUMENT_RETURNED_TO_DRAFT |
| Idempotency | Already DRAFT → conflict |

### 7.3 SignDocument (T003)

| Field | Value |
|---|---|
| Preconditions | READY; signer present; L008 snapshot ready |
| Actor | sign capability |
| Side effects | Signed snapshot; locale freeze; version pin |
| Audit | DOCUMENT_SIGNED; SIGNED_SNAPSHOT_CREATED |
| Rollback | None — Annul only |
| Idempotency | DOCUMENT_ALREADY_SIGNED |

### 7.4 RegisterDocument (T004)

| Field | Value |
|---|---|
| Preconditions | SIGNED; L009 valid |
| Actor | register capability |
| Side effects | Registration number; official journal |
| Audit | DOCUMENT_REGISTERED; REGISTRATION_NUMBER_ASSIGNED |
| Idempotency | DOCUMENT_ALREADY_REGISTERED |

### 7.5 Cancel / Annul (T005–T008)

See [UDE-005-cancel-annul-archive-model.md](./UDE-005-cancel-annul-archive-model.md).

### 7.6 Archive / Restore (T009–T010)

Orthogonal; lifecycle status unchanged. Archived document: mutations rejected as `DOCUMENT_ARCHIVED`.

---

## 8. Lifecycle Orchestrator Classification

| Role | Verdict |
|---|---|
| Domain Service | State machine rules, snapshot materialization |
| **Application Service** | **LifecycleOrchestrator** — command entry, transaction boundary |
| Policy coordinator | Validation + authority + specialization registries |
| BPM | Rejected |

**LifecycleOrchestrator** coordinates domain services in one atomic commit: validate → authorize → mutate aggregate → snapshot → audit → emit conceptual events.

---

*Matrix: [`data/UDE-005-transition-matrix.csv`](./data/UDE-005-transition-matrix.csv)*  
*Diagram: [`diagrams/lifecycle-orchestration.svg`](./diagrams/lifecycle-orchestration.svg)*
