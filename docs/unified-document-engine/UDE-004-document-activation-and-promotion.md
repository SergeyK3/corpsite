# UDE-004 — Document Activation, Promotion and Lifecycle Orchestration

WP: **UDE-004** — Document Activation, Promotion and Lifecycle Orchestration  
Date: **2026-07-12**  
Status: **Architecture Foundation — Complete**  
Prerequisites: UDE-000 ✓ · UDE-001 ✓ · UDE-002 ✓ · UDE-003 ✓  
Mode: **No runtime changes** — architecture only

**Artifacts:**

| Document | Purpose |
|---|---|
| [UDE-004-promotion-model.md](./UDE-004-promotion-model.md) | Promotion as technical pipeline |
| [UDE-004-document-activation.md](./UDE-004-document-activation.md) | Business event — document birth |
| [UDE-004-lifecycle-bootstrap.md](./UDE-004-lifecycle-bootstrap.md) | DRAFT-only bootstrap |
| [UDE-004-activation-validation.md](./UDE-004-activation-validation.md) | P-series vs E/L validation |
| [UDE-004-immutable-snapshot.md](./UDE-004-immutable-snapshot.md) | Baseline v1 vs signed immutability |
| [UDE-004-publication-boundary.md](./UDE-004-publication-boundary.md) | System visibility |
| [`data/`](./data/) | Activation, preconditions, lifecycle, events, readiness matrices |
| [`diagrams/`](./diagrams/) | Eight architecture diagrams |

---

## 1. Purpose

UDE-004 answers:

> **When and how does Official Draft Package become a full Document Aggregate and begin its predmetnaya life?**

It defines the **Activation Layer** — the boundary between Editorial World and Predmetny World:

```text
Editorial World                    │  Predmetny World
───────────────────────────────────┼────────────────────────────
Draft Workspace                    │
Official Draft Package             │
         │                         │
         ▼                         │
━━━━━━━━ Activation Boundary ━━━━━━━━│
         │                         ▼
         │                    Document Aggregate
         │                         │
         │                    Lifecycle (DRAFT→…)
         │                         │
         │                    Archive / Projection
```

**Promotion** = technical operation. **Document Activation** = business event.

---

## 2. Scope

### 2.1 In scope

- Activation Domain boundaries
- Promotion model (Application Service pipeline)
- Document Activation (birth moment)
- Promotion preconditions (P-series) and outputs
- Document aggregate birth (transfer from package)
- Lifecycle bootstrap (DRAFT only)
- Initial Version 1 and Effective Baseline
- Immutable snapshot semantics (baseline vs signed)
- Activation events (conceptual, no event bus)
- Publication boundary
- Validation orchestration (E / P / L separation)
- Activation Policy and Activation Audit
- UDE-003 mapping, UDE-005 handoff
- PO extraction candidates (analysis only)

### 2.2 Out of scope

- Code, ORM, SQL, API, UI
- Lifecycle transitions beyond DRAFT bootstrap (UDE-005)
- PDF, rendering, execution projection
- Runtime changes to PO or OO

---

## 3. Activation Domain

### 3.1 Responsibility

| In scope | Detail |
|---|---|
| Create Document Aggregate | From OfficialDraftPackage |
| Assign DocumentId | New opaque identity |
| Create Version 1 | Mutable baseline |
| Bootstrap Lifecycle | DRAFT only |
| Start Lifecycle Audit | DOCUMENT_ACTIVATED |
| Create Effective Baseline v1 | Mutable until SIGNED |
| Publish to registry | Journal-eligible |
| Freeze Workspace | DOCUMENT_PROMOTED |
| Handoff downstream | Document exists for UDE-005 |

### 3.2 NOT responsible

Draft Intake, Editorial, Localization, PDF, Rendering, Execution, Tasks.

Diagram: [`diagrams/activation-overview.svg`](./diagrams/activation-overview.svg)

---

## 4. Promotion Model

**Promotion** = **Application Service** (`PromoteOfficialDraft`) executing a **transactional pipeline** of domain services.

| Classification | Verdict |
|---|---|
| Domain Service | Materialization logic |
| Application Service | **Orchestrator** |
| BPM Process | Rejected |
| Pipeline | **Yes — conceptual steps** |

**Rule:** Promotion does not change semantic meaning — copy/transform only.

Detail: [UDE-004-promotion-model.md](./UDE-004-promotion-model.md)

---

## 5. Document Birth

**Moment of birth:** successful atomic **commit** when `DOCUMENT_ACTIVATED` Lifecycle Audit entry is written.

Creates: Document, DocumentId, Version 1, DRAFT, Lifecycle Audit, Activation Audit, Registry entry, PublicationReady, Workspace frozen.

Does not create: signed immutable snapshot, registration number (default), projection, PDF.

Detail: [UDE-004-document-activation.md](./UDE-004-document-activation.md)  
Diagram: [`diagrams/document-birth.svg`](./diagrams/document-birth.svg)

---

## 6. Promotion Preconditions

P-series (15 checks) at activation command. Editorial E-series must already be attached to package.

| Mandatory (shared) | P101–P107, P109–P111, P113–P115 |
|---|---|
| OO default | P108 content confirmation |
| Specialization | P112 kind hooks |

Failure → `PROMOTION_FAILED`, Workspace unchanged.

Matrix: [`data/UDE-004-promotion-preconditions.csv`](./data/UDE-004-promotion-preconditions.csv)

---

## 7. Promotion Outputs

| Created | Not created |
|---|---|
| Document Aggregate | Immutable signed snapshot |
| DocumentId | READY_FOR_SIGNATURE state |
| Version 1 (mutable) | Registration number (default) |
| LifecycleState = DRAFT | Execution projection |
| Lifecycle Audit (first entry) | PDF |
| Activation Audit | Task instances |
| Effective Baseline v1 | |
| Registry entry | |
| PublicationReady | |
| WorkspaceId ↔ DocumentId link | |

---

## 8. Document Aggregate Birth — Transfer Map

### Transferred from OfficialDraftPackage

| Package | Document |
|---|---|
| draft_metadata | DocumentMetadata |
| document_structure | DocumentStructure |
| order_items + semantic_model_snapshot | OrderItem[], obligations |
| locale_bundle (effective, generated, provenance) | LocaleRepresentation[] |
| attachment_references | AttachmentReference[] |
| validation clearance | ValidationResult |
| content_confirmation_state | ContentConfirmation |

### Remains in Workspace

SubmittedText raw, clarifications, full Draft/Editorial Audit, intake history, workspace intermediates.

(From UDE-003 — unchanged; UDE-004 executes transfer.)

---

## 9. Lifecycle Bootstrap

```text
Activation → DocumentLifecycleState := DRAFT (only)
```

READY, SIGNED, REGISTERED, VOIDED — **UDE-005 Lifecycle Core**.

Also at bootstrap: localization CURRENT (copied), execution not_created, archive null, write-lock DRAFT-editable.

Detail: [UDE-004-lifecycle-bootstrap.md](./UDE-004-lifecycle-bootstrap.md)  
Diagram: [`diagrams/lifecycle-bootstrap.svg`](./diagrams/lifecycle-bootstrap.svg)

---

## 10. Immutable Snapshot

| Snapshot | When | Mutable? |
|---|---|---|
| Initial Effective Baseline v1 | Activation | **Yes in DRAFT** |
| Signed Immutable Snapshot | SIGNED/REGISTERED | **No** (ADR-UDE-009) |

Activation creates **baseline**, not legal immutability. Signed snapshot at lifecycle SIGNED transition (UDE-005).

Detail: [UDE-004-immutable-snapshot.md](./UDE-004-immutable-snapshot.md)

---

## 11. Initial Version

| Version type | Scope |
|---|---|
| Draft versions | Workspace SubmittedDraftSnapshot |
| Editorial versions | Per-block derived_from chain |
| **Document Version 1** | First aggregate baseline at activation |
| Document Version N | Material DRAFT changes (UDE-005) |
| Signed Version | Immutable at SIGNED |

---

## 12. Activation Events

Conceptual events (no Event Bus in UDE-004):

| Event | Audit stream |
|---|---|
| PROMOTION_STARTED | Activation |
| PROMOTION_FAILED | Activation |
| PROMOTION_COMPLETED | Activation |
| DOCUMENT_ACTIVATED | Lifecycle |
| LIFECYCLE_STARTED | Lifecycle |
| DOCUMENT_CREATED | Lifecycle (alias) |
| INITIAL_VERSION_CREATED | Activation |
| INITIAL_SNAPSHOT_CREATED | Activation |
| PUBLICATION_READY | Activation |
| WORKSPACE_PROMOTED | Activation + Workspace |

Matrix: [`data/UDE-004-event-matrix.csv`](./data/UDE-004-event-matrix.csv)

---

## 13. Publication Boundary

At Activation (**PublicationReady**):

- DocumentId exists
- Visible in default journal (DRAFT)
- Openable and editable (DRAFT)
- Lifecycle transitions eligible (UDE-005)

**Not** at activation (default): official registration number, execution projection, immutable signed snapshot.

Detail: [UDE-004-publication-boundary.md](./UDE-004-publication-boundary.md)

---

## 14. Activation Validation

| Layer | WP | When |
|---|---|---|
| Editorial (E*, BC) | UDE-003 | Before package |
| **Activation (P*)** | **UDE-004** | At command |
| Lifecycle (L*) | UDE-005 | READY, SIGN, etc. |

Diagram: [`diagrams/activation-validation-flow.svg`](./diagrams/activation-validation-flow.svg)

---

## 15. Activation Policy

Activation **forbidden** when:

- Missing mandatory locale / not CURRENT (P104)
- Blocking editorial errors on package (P105)
- promotion_readiness false (P106)
- Workspace not OFFICIAL_DRAFT_READY (P107)
- Content confirmation pending — OO default (P108)
- Already promoted (P109)
- promotion_lock set (P114)
- Package corruption (P115)

---

## 16. Activation Audit

**Fourth stream** (in addition to Draft, Editorial, Lifecycle):

| Event | When |
|---|---|
| PROMOTION_STARTED | Command received |
| PROMOTION_FAILED | P-series or rollback |
| PROMOTION_COMPLETED | Pre-commit success |
| INITIAL_VERSION_CREATED | v1 baseline |
| INITIAL_SNAPSHOT_CREATED | Effective baseline |
| PUBLICATION_READY | Registry published |

Lifecycle Audit starts with `DOCUMENT_ACTIVATED` at same commit.

Diagram: [`diagrams/activation-audit-model.svg`](./diagrams/activation-audit-model.svg)

---

## 17. Shared Contract Mapping

### UDE-003 → UDE-004

```text
OfficialDraftPackage → PromoteOfficialDraftCommand → Document Aggregate
```

| UDE-001 Contract | Activation role |
|---|---|
| Document | Created |
| DocumentMetadata | From package metadata |
| DocumentStructure | Transferred |
| OrderItem | Transferred |
| LocaleRepresentation | From locale_bundle |
| TextProvenance | Carried forward |
| ValidationResult | P103 verifies clearance |
| DocumentLifecycleState | Bootstrap DRAFT |
| DocumentAuditEvent | DOCUMENT_ACTIVATED |
| AttachmentReference | Transferred |
| ContentConfirmation | Carried |

---

## 18. Compatibility

| Target | Fit |
|---|---|
| **Operational Orders** | Full path: Workspace → Activation |
| **Personnel Orders** | Adapter: PO early creation → synthetic activation (UDE-006) |
| **Future families** | Same Activation Layer + kind registry |
| **Task Engine** | No dependency |
| **HR apply** | After REGISTERED projection — not activation |

---

## 19. Readiness Review

| Component | Status |
|---|---|
| Activation Domain | **Ready** |
| Promotion Model | **Ready** |
| Document Activation | **Ready** |
| P-series Preconditions | **Ready** |
| Lifecycle Bootstrap | **Ready** |
| Initial Version / Baseline | **Ready** |
| Activation Events | **Ready** |
| Publication Boundary | **Ready** |
| Activation Validation | **Ready** |
| Activation Audit | **Ready** |
| Signed immutability | **Deferred** (UDE-005 SIGNED) |
| PO early-creation adapter | **Deferred** (UDE-006) |
| Event bus | **Rejected** |

Matrix: [`data/UDE-004-readiness.csv`](./data/UDE-004-readiness.csv)

---

## 20. Handoff to UDE-005

**UDE-005 — Shared Lifecycle Core and Orchestration** receives:

| From Activation | UDE-005 use |
|---|---|
| Document Aggregate in DRAFT | Lifecycle state machine host |
| DocumentId | Identity for all transitions |
| Version 1 baseline | Versioning on material changes |
| Lifecycle Audit stream | Continue append-only |
| WriteLockPolicy (DRAFT editable) | Enforce READY+ read-only |
| Localization state (CURRENT) | READY gate BC re-check |
| ValidationResult seed | READY gate input |
| Registry entry | Journal and kind policies |
| PublicationReady | Already visible — lifecycle adds READY path |
| ContentConfirmation state | READY gate OO default |

UDE-005 implements: DRAFT→READY→SIGNED→REGISTERED→VOIDED, archive, return-to-DRAFT, signed immutable snapshot creation, registration number assignment, READY/L-series validation.

UDE-004 does **not** implement lifecycle transitions beyond DRAFT bootstrap.

---

## 21. Personnel Orders Extraction Candidates

Analysis only — no code changes.

| PO element | Shared Activation candidate | Class |
|---|---|---|
| Order creation → DRAFT status | Lifecycle bootstrap pattern | **A** |
| `personnel_orders` identity (order_id) | DocumentId assignment pattern | **A** |
| Lifecycle audit events | Lifecycle Audit taxonomy | **A** |
| Status write-lock (DRAFT only editorial) | WriteLockPolicy | **A** |
| Journal list query by status | Publication / registry | **B** |
| Early document creation (no Workspace) | Activation adapter | **B** — UDE-006 |
| Sign/register transitions | Lifecycle Core | **C** — stays PO until UDE-005/006 |
| apply_service projection | Execution adapter | **C** — not Activation |
| PDF/print | Renderer | **C** — excluded |

**Extraction sequence:** Activation pipeline contract (A) → PO wraps existing order creation as synthetic activation → OO uses full Workspace path.

---

## 22. Conclusions

UDE-004 completes the **Activation Layer**:

1. **Document Activation** — business birth at `DOCUMENT_ACTIVATED` commit  
2. **Promotion** — Application Service pipeline, no semantic change  
3. **P-series** — activation preconditions separate from E and L  
4. **DRAFT-only bootstrap** — lifecycle depth in UDE-005  
5. **Version 1 baseline** — mutable; signed immutability later  
6. **PublicationReady** — system visibility at activation  
7. **Four audit streams** — Draft, Editorial, Activation, Lifecycle  
8. **Independence** from PO, OO internals, Task Engine  

No runtime changes. Foundation for **UDE-005 Shared Lifecycle Core**.

**Next authorized WP:** UDE-005 — Shared Lifecycle Core and Orchestration.

---

## Mandatory Answers

### 1. Что такое Document Activation?

Бизнес-событие рождения документа — переход из редакционного мира в предметный. Успешный atomic commit с `DOCUMENT_ACTIVATED`.

### 2. Чем Activation отличается от Promotion?

**Promotion** — техническая материализация aggregate из package. **Activation** — бизнес-событие, включающее promotion + lifecycle bootstrap + audit + registry + publication.

### 3. Когда рождается Document Aggregate?

При успешном commit Activation pipeline — момент `DOCUMENT_ACTIVATED`.

### 4. Когда создаётся DocumentId?

В том же commit, до персистенции aggregate — шаг 4 pipeline.

### 5. Когда начинается Lifecycle?

При Activation — начальное состояние **DRAFT** only.

### 6. Когда начинается Lifecycle Audit?

Первая запись `DOCUMENT_ACTIVATED` в том же commit что и birth.

### 7. Что входит в Initial Snapshot?

Effective + generated + provenance per locale block, semantic model, structure, metadata. **Mutable в DRAFT.** Не legally immutable.

### 8. Что переносится из Official Draft Package?

Metadata, structure, items, semantic, locale representations, attachments, validation, confirmation.

### 9. Что остаётся в Draft Workspace?

SubmittedText raw, clarifications, Draft/Editorial Audit полный, intake history — Workspace frozen.

### 10. Какие проверки блокируют Activation?

P101–P115: package present, frozen, E-clearance, locale CURRENT, promotion_readiness, confirmation (OO), idempotency, integrity, kind hooks.

### 11. Когда документ становится видимым в системе?

При **PublicationReady** сразу после Activation — journal list, open, DRAFT edit. Reg number — при REGISTERED (UDE-005).

### 12. Какие события публикуются после Activation?

DOCUMENT_ACTIVATED, LIFECYCLE_STARTED, PROMOTION_COMPLETED, INITIAL_VERSION_CREATED, PUBLICATION_READY, WORKSPACE_PROMOTED.

### 13. Что получает Lifecycle Core?

Document в DRAFT, DocumentId, Version 1, audit stream, write-lock, localization state, validation seed, registry entry.

### 14. PO extraction candidates?

Class A: DRAFT bootstrap, DocumentId pattern, lifecycle audit, write-lock. Class B: journal/registry, synthetic activation adapter. Class C: sign/apply/PDF.

### 15. Готов ли Activation Layer?

**Да** — все компоненты Ready кроме signed immutability (UDE-005) и PO adapter (UDE-006). Event bus rejected.

---

*UDE-004 completed 2026-07-12. No runtime changes.*
