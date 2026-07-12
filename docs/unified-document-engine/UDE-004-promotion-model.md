# UDE-004 — Promotion Model

WP: **UDE-004** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Promotion vs Activation

| Concept | Nature | Responsibility |
|---|---|---|
| **Promotion** | Technical operation | Materialize Document Aggregate from OfficialDraftPackage |
| **Document Activation** | Business event | Document born — predmetnaya zhizn begins |

```text
Promotion (technical)  ⊂  Document Activation (business)
```

Activation **includes** promotion plus lifecycle bootstrap, audit initiation, registry publication, and workspace finalization.

---

## 2. Promotion Classification

| Option | Verdict | Rationale |
|---|---|---|
| Domain Service | Partial | Aggregate materialization is domain logic |
| Application Service | **Yes — orchestrator** | Coordinates validation, promotion, bootstrap, audit atomically |
| BPM Process | **No** | No workflow engine at activation |
| Pipeline | **Yes — conceptual** | Ordered steps with rollback semantics |

**Conclusion:** Promotion is an **Application Service command** (`PromoteOfficialDraft`) invoking **domain services** in a **transactional pipeline**. Document Activation is the **successful outcome** of that pipeline.

---

## 3. Promotion Pipeline (conceptual)

```text
PromoteOfficialDraftCommand
  1. Load OfficialDraftPackage + Workspace ref
  2. Activation Validation (P-series) — idempotent pre-check
  3. Promotion Materialization — create Document aggregate in memory
  4. Assign DocumentId
  5. Bootstrap Lifecycle (DRAFT)
  6. Create Version 1 baseline
  7. Write Initial Lifecycle Audit + Activation Audit
  8. Register in Document Kind Registry
  9. Freeze Workspace (DOCUMENT_PROMOTED)
 10. Emit activation events (conceptual)
 11. Commit (single consistency boundary)
```

**Rule PR1:** Promotion does not alter semantic meaning — copy only.  
**Rule PR2:** Promotion is idempotent per WorkspaceId (same package → same DocumentId or reject duplicate).  
**Rule PR3:** Failed promotion leaves Workspace unchanged (no partial Document).

---

## 4. Inputs

| Input | Source |
|---|---|
| OfficialDraftPackage | Draft Workspace (frozen) |
| WorkspaceId | Draft Workspace |
| Promotion actor | Document Operator (system actor) |
| Specialization policy | Document Kind Registry |

---

## 5. Outputs

| Output | Created |
|---|---|
| Document Aggregate | Yes |
| DocumentId | Yes |
| Document Version 1 | Yes (mutable baseline) |
| LifecycleState = DRAFT | Yes |
| Lifecycle Audit (first entry) | Yes |
| Activation Audit entries | Yes |
| Registry entry | Yes |
| Workspace frozen | Yes |
| Immutable signed snapshot | **No** — at SIGNED (ADR-UDE-009) |
| Execution projection | **No** — at REGISTERED |
| Registration number | **Optional** — may be null until REGISTERED |
| PDF | **No** |

---

## 6. What Promotion Does NOT Do

- Re-run full editorial editing
- Machine translation
- Assign registration number (unless kind policy requires at activation — default deferred)
- Transition to READY_FOR_SIGNATURE
- Sign, project, render PDF
- Modify package semantic content

---

*Diagram: [`diagrams/promotion-boundary.svg`](./diagrams/promotion-boundary.svg)*
