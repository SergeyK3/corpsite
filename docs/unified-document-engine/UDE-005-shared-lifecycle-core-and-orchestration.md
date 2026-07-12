# UDE-005 — Shared Lifecycle Core and Orchestration

WP: **UDE-005** — Shared Lifecycle Core and Orchestration  
Date: **2026-07-12**  
Status: **Architecture Foundation — Complete**  
Prerequisites: UDE-000 ✓ · UDE-001 ✓ · UDE-002 ✓ · UDE-003 ✓ · UDE-004 ✓  
Mode: **No runtime changes** — architecture only

**Artifacts:**

| Document | Purpose |
|---|---|
| [UDE-005-lifecycle-state-model.md](./UDE-005-lifecycle-state-model.md) | Five states + archive orthogonality |
| [UDE-005-transition-and-policy-model.md](./UDE-005-transition-and-policy-model.md) | Transitions and orchestrator |
| [UDE-005-cancel-annul-archive-model.md](./UDE-005-cancel-annul-archive-model.md) | void_kind and archive |
| [UDE-005-signed-snapshot-and-registration.md](./UDE-005-signed-snapshot-and-registration.md) | ADR-UDE-009 and RegistrationPolicy |
| [UDE-005-lifecycle-validation.md](./UDE-005-lifecycle-validation.md) | L-series validation |
| [UDE-005-personnel-orders-lifecycle-gap-analysis.md](./UDE-005-personnel-orders-lifecycle-gap-analysis.md) | PO read-only gap analysis |
| [`data/`](./data/) | State, transition, immutability, validation, event, policy, gap, readiness matrices |
| [`diagrams/`](./diagrams/) | Ten architecture diagrams |

---

## 1. Purpose

UDE-005 answers:

> **How does an activated Document Aggregate pass the official lifecycle from DRAFT through registration, cancellation, annulment, and archiving?**

It defines **Shared Lifecycle Core** — the common document lifecycle state machine and orchestration applicable to Personnel Orders, Operational Orders, and future document families.

```text
UDE-004 Activation                    UDE-005 Lifecycle Core
─────────────────────                 ─────────────────────────
Official Draft Package                DRAFT → READY → SIGNED → REGISTERED
       │                                      ↓
       ▼                                 VOIDED (CANCEL|ANNUL)
Document Aggregate (DRAFT)            Archive ⊥ Lifecycle
```

---

## 2. Scope

### 2.1 In scope

- Lifecycle Core domain boundaries
- Document lifecycle state model (5 states)
- Transition and policy model
- Cancel vs Annul (void_kind)
- Archive orthogonality
- Per-state rules (DRAFT through VOIDED)
- Immutability matrix
- Lifecycle validation (L-series)
- Lifecycle Orchestrator
- Transition events (conceptual)
- Lifecycle audit (append-only)
- Signed snapshot model (ADR-UDE-009)
- Registration model (conceptual)
- Three-lifecycle interaction matrix
- Specialization policies
- Authority boundary (capabilities)
- Concurrency and idempotency requirements
- Error model
- PO gap analysis (read-only)
- Extraction strategy and UDE-006 handoff

### 2.2 Out of scope

- Code, ORM, SQL, API, UI, migrations
- Draft Intake, Editorial, Translation, Rendering, PDF implementation
- E-signature, external registration, numbering service
- Execution runtime, task engine
- Runtime changes to PO or OO
- Commit, push, deploy

---

## 3. Context and Inputs

From UDE-004:

| Established | Detail |
|---|---|
| DocumentId | Created at Activation |
| Lifecycle start | DRAFT only |
| Baseline v1 | Mutable in DRAFT |
| Legal immutability | At SIGNED (not Activation) |
| Registration number | At REGISTERED (default) |
| Validation chain | E* → P* → L* |
| UDE-005 input | Activated Document Aggregate in DRAFT |

PO production foundation (read-only, unchanged):

- Five lifecycle statuses + VOIDED terminal
- void_kind CANCEL | ANNUL
- Append-only lifecycle audit
- Archive/restore orthogonal
- Immutable archived documents
- Scoped cancellation
- Ownership and org scope

---

## 4. Lifecycle Core Domain

### 4.1 Responsibility

| In scope | Detail |
|---|---|
| Document lifecycle states | DRAFT … VOIDED |
| Allowed transitions | State machine |
| Transition policies | Per-command gates |
| Lifecycle validation | L-series |
| Transition reasons | void_reason, archive reason |
| Lifecycle audit | Append-only stream |
| Signing boundary | SIGNED + signed snapshot |
| Registration boundary | REGISTERED + number |
| Cancel and annulment | void_kind semantics |
| Archive interaction | Orthogonal guard |
| Immutability rules | Per-state matrix |
| Transition orchestration | Atomic commands |

### 4.2 NOT responsible

| Out of scope | Owner |
|---|---|
| Draft Intake | UDE-002 |
| Editorial generation | UDE-003 |
| Translation | Localization Core |
| Rendering, PDF | Renderer |
| Execution Tasks | Execution contour |
| E-signature | External |
| External registration | Adapter |
| Permissions implementation | ACCESS / runtime |

Diagram: [`diagrams/shared-document-lifecycle.svg`](./diagrams/shared-document-lifecycle.svg)

---

## 5. State Model

Five shared lifecycle states. Archive is orthogonal.

Detail: [UDE-005-lifecycle-state-model.md](./UDE-005-lifecycle-state-model.md)  
Matrix: [`data/UDE-005-state-operation-matrix.csv`](./data/UDE-005-state-operation-matrix.csv)

---

## 6. Transition Model

Ten shared transitions (T001–T010). PO adapter shortcuts documented as specialization.

Detail: [UDE-005-transition-and-policy-model.md](./UDE-005-transition-and-policy-model.md)  
Matrix: [`data/UDE-005-transition-matrix.csv`](./data/UDE-005-transition-matrix.csv)

---

## 7. DRAFT

| Rule | Detail |
|---|---|
| Baseline snapshot | **Mutable** (UDE-004 IS1) |
| Version increment | On material editorial/semantic commit |
| Localization STALE | Blocks READY (not DRAFT edit) |
| Audit events | Editorial audit; DOCUMENT_ACTIVATED at birth |
| Void | Cancel allowed (void_kind=CANCEL) |
| Archive | Policy-dependent (default: allowed with caution) |
| Allowed work | Full editorial, semantic, locale, regeneration, attachments |

---

## 8. READY_FOR_SIGNATURE

| Rule | Detail |
|---|---|
| Meaning | Editorial complete; locales ready; validations passed; prepared for sign |
| Write locks | Content read-only engaged |
| Allowed changes | Limited metadata only (policy); view; ReturnToDraft; Sign; Cancel |
| Return to DRAFT | Required for any content correction |
| Localization blockers | STALE (hard); REVIEW_REQUIRED (waivable) |
| Waiver | Head/operator waiver audited |
| Audit | DOCUMENT_READY_FOR_SIGNATURE mandatory |
| Return authority | return_to_draft capability |

**PO READY editability drift — target:** READY is read-only. PO backend already enforces DRAFT-only edit; docs drift is **debt** (UDE-006).

---

## 9. SIGNED

| Rule | Detail |
|---|---|
| Legal boundary | **Signed Immutable Snapshot** created atomically |
| Frozen | Effective texts, structure, items, attachments, signer, version |
| Forbidden | Silent regeneration, content edit |
| Metadata | Non-content technical correction via policy only |
| Errors | Annul + compensating document |
| Waiver | Non-waivable L* only at sign |
| Locale reconciliation | Fixed in signed snapshot |
| Audit | DOCUMENT_SIGNED; SIGNED_SNAPSHOT_CREATED |

Detail: [UDE-005-signed-snapshot-and-registration.md](./UDE-005-signed-snapshot-and-registration.md)

---

## 10. REGISTERED

| Rule | Detail |
|---|---|
| Registration number | Assigned at REGISTERED (default) |
| Reservation | Optional earlier via RegistrationPolicy |
| Registration date | Required |
| SIGNED without REGISTERED | **Allowed** |
| VOIDED registration | Cannot register VOIDED document |
| Immutability | Registration fields immutable after commit |
| Journal | Official journal entry |
| Execution Projection | **Default: after REGISTERED** |
| Audit | DOCUMENT_REGISTERED; REGISTRATION_NUMBER_ASSIGNED |

---

## 11. VOIDED

| Rule | Detail |
|---|---|
| Terminal | No lifecycle restore |
| Storage | void_kind, reason, actor, timestamp, source_state, snapshot ref |
| Visibility | Readable; closed journal filter optional |
| Mutability | None |
| Archive | Allowed |
| Registration number | Retained |
| Signed snapshot | Preserved if existed |
| Execution | Void cascade / compensating hint |
| **VOIDED ≠ deleted** | Full history retained |

---

## 12. Cancel vs Annul

| void_kind | Source states | Meaning |
|---|---|---|
| CANCEL | DRAFT, READY | Abandon unsigned project |
| ANNUL | SIGNED, REGISTERED | Invalidate official act |

Status remains **VOIDED** for both. void_kind discriminates semantics.

Detail: [UDE-005-cancel-annul-archive-model.md](./UDE-005-cancel-annul-archive-model.md)

---

## 13. Archive and Restore

```text
Lifecycle Status  ×  ArchiveState (ACTIVE | ARCHIVED)
```

Archive is **not** a lifecycle transition. Archived documents: view, print, audit, restore only.

PO rule confirmed: archived document immutable.

---

## 14. Immutability Model

Matrix: [`data/UDE-005-immutability-matrix.csv`](./data/UDE-005-immutability-matrix.csv)

| Phase | Content | Registration | Archive flag |
|---|---|---|---|
| DRAFT | Editable | N/A | Editable |
| READY | Read-only | N/A | Editable |
| SIGNED | Immutable | Pending | Editable |
| REGISTERED | Immutable | Immutable | Editable |
| VOIDED | Immutable | Retained | Editable |
| ARCHIVED | Immutable | Immutable | Immutable |

---

## 15. Lifecycle Validation

L-series (25 rules). Non-waivable: L001–L004, L010–L011, L013–L014, L016–L018.

Detail: [UDE-005-lifecycle-validation.md](./UDE-005-lifecycle-validation.md)

---

## 16. Lifecycle Orchestrator

**Classification: Application Service** (`LifecycleOrchestrator`)

Coordinates in one atomic transaction:

1. Load aggregate + expected_version
2. L-series + authority + specialization policies
3. Domain mutation (status, void_kind, archive)
4. Snapshot operation (signed snapshot at SIGNED)
5. Lifecycle audit append
6. Conceptual downstream events

| Command | Orchestrator entry |
|---|---|
| MarkReady | `MarkReadyCommand` |
| ReturnToDraft | `ReturnToDraftCommand` |
| SignDocument | `SignDocumentCommand` |
| RegisterDocument | `RegisterDocumentCommand` |
| CancelDocument | `CancelDocumentCommand` |
| AnnulDocument | `AnnulDocumentCommand` |
| ArchiveDocument | `ArchiveDocumentCommand` |
| RestoreDocument | `RestoreDocumentCommand` |

Failure: no partial commit; domain error returned.

Diagram: [`diagrams/lifecycle-orchestration.svg`](./diagrams/lifecycle-orchestration.svg)

---

## 17. Transition Events

Conceptual events (no Event Bus):

| Event | Trigger |
|---|---|
| DOCUMENT_READY_FOR_SIGNATURE | MarkReady |
| DOCUMENT_RETURNED_TO_DRAFT | ReturnToDraft |
| DOCUMENT_SIGNED | SignDocument |
| DOCUMENT_REGISTERED | RegisterDocument |
| DOCUMENT_VOIDED | Void |
| DOCUMENT_CANCELLED | Cancel |
| DOCUMENT_ANNULLED | Annul |
| DOCUMENT_ARCHIVED | Archive |
| DOCUMENT_RESTORED | Restore |
| SIGNED_SNAPSHOT_CREATED | Sign (atomic) |
| REGISTRATION_NUMBER_ASSIGNED | Register (atomic) |

Matrix: [`data/UDE-005-event-matrix.csv`](./data/UDE-005-event-matrix.csv)

---

## 18. Lifecycle Audit

**Append-only.** Separate from Editorial Audit and Activation Audit.

| Field | Required |
|---|---|
| document identity | Yes |
| event type / action | Yes |
| from_state, to_state | Yes |
| archive_state before/after | Yes |
| actor, authority context | Yes |
| reason, void_kind | When applicable |
| timestamp, version | Yes |
| correlation/reference | Optional |
| snapshot reference | When applicable |
| metadata summary | Optional |

Diagram: [`diagrams/lifecycle-audit-model.svg`](./diagrams/lifecycle-audit-model.svg)

---

## 19. Signed Snapshot

ADR-UDE-009 refined at SIGNED. PDF is separate artifact; snapshot text is authoritative.

Detail: [UDE-005-signed-snapshot-and-registration.md](./UDE-005-signed-snapshot-and-registration.md)  
Diagram: [`diagrams/signed-snapshot-boundary.svg`](./diagrams/signed-snapshot-boundary.svg)

---

## 20. Registration Model

RegistrationPolicy extension point: scope, sequence, reservation, duplicate prevention. Number at REGISTERED. No generator designed.

Diagram: [`diagrams/registration-boundary.svg`](./diagrams/registration-boundary.svg)

---

## 21. Three Lifecycle Interaction

| Interaction | Rule |
|---|---|
| STALE blocks READY | Localization → Document gate |
| REVIEW_REQUIRED blocks READY | Without waiver |
| SIGNED freezes locales | In signed snapshot |
| REGISTERED enables projection | Default execution handoff |
| VOIDED voids projection | Cascade or compensate |
| ARCHIVED ≠ cancel execution | Orthogonal |
| Execution completion | Does not auto-change document status |

Diagram: [`diagrams/three-lifecycle-interaction.svg`](./diagrams/three-lifecycle-interaction.svg)

---

## 22. Specialization Policies

Shared: states, audit, archive, snapshot, validation orchestration.

| Area | PO | OO |
|---|---|---|
| Ready gate | L022 employee readiness | L021 content confirmation |
| Sign/register | Combined adapter shortcut | Full Sign → Register |
| Annul | L024 void chain + event rollback | Projection void |
| Projection | apply → employee_events | commission tasks |

Matrix: [`data/UDE-005-specialization-policy-matrix.csv`](./data/UDE-005-specialization-policy-matrix.csv)

---

## 23. Authority Boundary

Capabilities (not permission implementation):

| Capability | Typical states |
|---|---|
| mark_ready | DRAFT |
| return_to_draft | READY |
| sign | READY |
| register | SIGNED |
| cancel_own / cancel_scope | DRAFT, READY |
| annul | SIGNED, REGISTERED |
| archive | REGISTERED, VOIDED |
| restore | ARCHIVED |
| issue_waiver | MarkReady, Sign |
| view_audit | All |

Authority checked **before** mutation; reflected in audit context.

Diagram: [`diagrams/lifecycle-authority-boundary.svg`](./diagrams/lifecycle-authority-boundary.svg)

---

## 24. Concurrency and Idempotency

| Requirement | Concept |
|---|---|
| Optimistic concurrency | expected_version on commands |
| Duplicate commands | L015; domain errors for illegal repeat |
| Repeated signing | DOCUMENT_ALREADY_SIGNED |
| Repeated registration | DOCUMENT_ALREADY_REGISTERED |
| Double numbering | L018 conflict |
| Archive/restore races | L014 transition lock |
| Atomic snapshot + state | Single transaction at SIGNED |

Row locking implementation → future WP (not UDE-005).

---

## 25. Error Model

| Category | Examples |
|---|---|
| Domain | INVALID_LIFECYCLE_TRANSITION, VOID_KIND_NOT_APPLICABLE |
| Policy | LOCALIZATION_NOT_READY, VALIDATION_BLOCKED |
| Authority | AUTHORITY_DENIED |
| Concurrency | CONCURRENT_DOCUMENT_UPDATE |
| State | DOCUMENT_ALREADY_SIGNED, DOCUMENT_ALREADY_REGISTERED, ORDER_ALREADY_VOIDED |
| Archive | DOCUMENT_ARCHIVED |
| Infrastructure | SIGNED_SNAPSHOT_FAILED, REGISTRATION_NUMBER_CONFLICT |

No HTTP codes fixed in UDE-005.

---

## 26. Personnel Orders Gap Analysis

Read-only. PO provides A-class foundation; gaps in signed snapshot, return-to-draft, full audit coverage.

Detail: [UDE-005-personnel-orders-lifecycle-gap-analysis.md](./UDE-005-personnel-orders-lifecycle-gap-analysis.md)

---

## 27. Compatibility and Extraction Strategy

| Phase | Goal |
|---|---|
| **A — Preserve PO behavior** | No regression during introduction |
| **B — Shared lifecycle contracts** | Interfaces, L-series, event taxonomy |
| **C — PO adapters** | Wrap existing services behind orchestrator |
| **D — OO shared lifecycle** | Full path for Operational Orders |
| **E — PO converge** | Incremental: audit, snapshot, return-to-draft |

**Compatibility guarantees:**

- Existing PO status values unchanged
- void_kind semantics preserved
- Archive orthogonality preserved
- Cancel scope permissions preserved
- PO register shortcut available via adapter until Phase E

**Rollback boundary:** Adapter layer removable; PO services remain source of truth until Phase E.

---

## 28. Shared Contract Mapping

| UDE-001 Contract | Lifecycle role |
|---|---|
| DocumentLifecycleState | Five states |
| DocumentAuditEvent | Lifecycle audit entries |
| ValidationResult | L-series input |
| LocaleRepresentation | L005 gate |
| DocumentMetadata | Registration fields |
| VoidKind | CANCEL \| ANNUL |

---

## 29. Readiness Review

| Component | Status |
|---|---|
| State model | **Ready** |
| Transition model | **Ready** |
| Cancel / Annul | **Ready** |
| Archive | **Ready** |
| Validation | **Ready** |
| Signed snapshot | **Ready** (concept) |
| Registration | **Ready** (concept) |
| Orchestrator | **Ready** |
| Authority | **Ready** |
| Concurrency | **Ready** (conceptual) |
| PO compatibility | **Ready** (analysis) |
| Event bus | **Rejected** |
| Runtime implementation | **Deferred** (UDE-006+) |

Matrix: [`data/UDE-005-readiness.csv`](./data/UDE-005-readiness.csv)

---

## 30. Handoff to UDE-006

**UDE-006 — Personnel Orders Compatibility and Shared Core Extraction Plan**

Receives:

| Artifact | Use |
|---|---|
| Shared lifecycle contract | PO adapter mapping |
| Specialization policy boundary | PO vs OO hooks |
| Signed snapshot contract | PO gap closure plan |
| RegistrationPolicy | PO numbering adapter |
| Authority requirements | Granular capability migration |
| PO gap analysis | Extraction sequencing |
| Compatibility constraints | Phase A–E boundaries |

UDE-006 scope: extraction plan and adapter design — **not** full extraction execution.

---

## 31. Conclusions

Shared Lifecycle Core is **architecturally ready for implementation**. Five states, void_kind, archive orthogonality, L-series validation, orchestrator model, and signed snapshot boundary are defined. PO production patterns validate the design. Operational Orders can adopt shared lifecycle without PO big-bang refactor via phased adapters (UDE-006).

---

## Mandatory Answers

| # | Question | Answer |
|---|---|---|
| 1 | Shared Document Lifecycle states? | **DRAFT, READY_FOR_SIGNATURE, SIGNED, REGISTERED, VOIDED** |
| 2 | Why Archive is not lifecycle status? | **Orthogonal retention dimension; restore without lifecycle change; journal hide without voiding** |
| 3 | Shared transitions? | **T001–T010: MarkReady, ReturnToDraft, Sign, Register, Cancel, Annul, Archive, Restore** |
| 4 | Specialization-specific? | **PO register-from-DRAFT shortcut; combined sign+register adapter; apply/projection; void chain** |
| 5 | CANCEL vs ANNUL? | **CANCEL abandons unsigned; ANNUL invalidates signed/registered official act; both → VOIDED** |
| 6 | CANCEL applicable? | **DRAFT, READY_FOR_SIGNATURE** |
| 7 | ANNUL applicable? | **SIGNED, REGISTERED** |
| 8 | Allowed in DRAFT? | **Semantic, editorial, locale edit, regeneration, attachments, validation, MarkReady, Cancel** |
| 9 | Blocked in READY? | **Content edit, regeneration, item edit, locale edit, Sign without gates** |
| 10 | Immutable at SIGNED? | **Semantic model, texts, items, structure, attachments, signer, version** |
| 11 | Legal immutable snapshot when? | **At SIGNED transition (SignDocument)** |
| 12 | Registration number when? | **At REGISTERED transition (default)** |
| 13 | SIGNED without REGISTERED? | **Yes, allowed** |
| 14 | Number after VOIDED? | **Retained on voided record; not reused** |
| 15 | Edit REGISTERED? | **No content edit; registration fields immutable** |
| 16 | ARCHIVED operations? | **View, print, audit, restore only** |
| 17 | VOIDED restore? | **No — terminal** |
| 18 | Localization blocking READY? | **STALE (hard); REVIEW_REQUIRED (waivable)** |
| 19 | Non-waivable L*? | **L001–L004, L010–L011, L013–L014, L016–L018** |
| 20 | Lifecycle Orchestrator? | **Application Service coordinating validation, policies, mutation, snapshot, audit atomically** |
| 21 | Mandatory audit events? | **All transition commands + SIGNED_SNAPSHOT_CREATED + REGISTRATION_NUMBER_ASSIGNED** |
| 22 | Transition idempotency? | **expected_version + L015; illegal repeats → domain errors** |
| 23 | Lifecycle ↔ execution projection? | **Projection after REGISTERED default; VOIDED cascades; ARCHIVED does not auto-cancel** |
| 24 | PO reusable components? | **Status enum, void_kind, lifecycle audit, archive guard, cancel/annul split** |
| 25 | PO specialization-specific? | **apply/employee_events, void chain, cancel scope, item void** |
| 26 | Technical debts? | **READY doc drift, no sign snapshot, no return-to-draft, incomplete lifecycle audit, broad admin on register** |
| 27 | OO without full PO refactor? | **Yes — adapter pattern Phases A–D** |
| 28 | Compatibility guarantees? | **PO status/void_kind/archive/cancel scope unchanged during migration** |
| 29 | Ready for implementation? | **Yes — architecture foundation complete** |
| 30 | UDE-006 scope? | **PO compatibility plan, adapter design, extraction sequencing — not runtime extraction** |

---

*End of UDE-005 — Shared Lifecycle Core and Orchestration*
