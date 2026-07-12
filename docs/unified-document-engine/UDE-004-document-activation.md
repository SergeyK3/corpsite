# UDE-004 — Document Activation

WP: **UDE-004** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. What is Document Activation?

**Document Activation** is the business event marking transition from **Editorial World** to **Predmetny World** — the moment a legal act instance exists in Unified Document Engine with identity, lifecycle, and system visibility.

It is **more than** promotion: activation is the **birth ceremony**; promotion is the **materialization mechanism**.

---

## 2. Moment of Birth

**Document is born** at successful **commit** of the Activation pipeline when all of the following are true atomically:

| Condition | Meaning |
|---|---|
| DocumentId assigned | Opaque unique identity |
| Document Aggregate persisted | Metadata, structure, items, locales |
| LifecycleState = DRAFT | Lifecycle bootstrap complete |
| First Lifecycle Audit entry written | `DOCUMENT_ACTIVATED` |
| Workspace frozen | DOCUMENT_PROMOTED |
| Registry entry published | Document discoverable by kind |

**Single moment:** `DOCUMENT_ACTIVATED` audit event timestamp = official birth instant.

Before this moment: no DocumentId, no lifecycle, no journal eligibility.  
After this moment: Document exists; editorial world for this instance is closed (Workspace read-only).

---

## 3. Activation Sequence

```text
Official Draft Package (ready)
    │
    ▼
[PROMOTION_STARTED]          ← Activation Audit
    │
    ▼
Promotion Materialization    ← technical
    │
    ▼
Lifecycle Bootstrap DRAFT
    │
    ▼
Version 1 Baseline created
    │
    ▼
Initial Effective Baseline   ← mutable until SIGNED
    │
    ▼
Registry + Publication
    │
    ▼
[PROMOTION_COMPLETED]
[DOCUMENT_ACTIVATED]         ← Lifecycle Audit (first)
[LIFECYCLE_STARTED]
    │
    ▼
Workspace frozen
```

---

## 4. What Activation Creates

| Artifact | Detail |
|---|---|
| **Document** | Aggregate root |
| **DocumentId** | New identity |
| **Version 1** | First document version (mutable in DRAFT) |
| **Lifecycle** | Initial state DRAFT only |
| **Lifecycle Audit** | Stream begins |
| **Activation Audit** | promotion_started/completed |
| **Effective Baseline v1** | All locale effective texts copied — editable in DRAFT |
| **Registry references** | DocumentKind → specialization policy binding |
| **Publication state** | Visible in system (journal list eligible) |
| **Workspace link** | WorkspaceId ↔ DocumentId bidirectional |

---

## 5. What Activation Does NOT Create

| Not created | When instead |
|---|---|
| Immutable signed snapshot | SIGNED / REGISTERED (ADR-UDE-009) |
| READY_FOR_SIGNATURE state | Lifecycle transition (UDE-005) |
| Registration number (default) | REGISTERED transition |
| Execution projection | REGISTERED + projection policy |
| PDF artifact | Renderer downstream |
| Task instances | Execution contour |

---

## 6. Activation Domain Boundaries

### In scope

- Document aggregate creation
- DocumentId assignment
- Version 1 baseline
- Lifecycle bootstrap (DRAFT)
- Lifecycle Audit initiation
- Activation Audit
- Effective baseline snapshot (mutable)
- Registry publication
- Workspace finalization
- Downstream handoff descriptor (document exists — projection later)

### Out of scope

- Draft Intake, Editorial, Localization (upstream — complete)
- PDF, Rendering
- Execution, Tasks
- Lifecycle transitions beyond DRAFT bootstrap

---

*Diagram: [`diagrams/document-birth.svg`](./diagrams/document-birth.svg)*
