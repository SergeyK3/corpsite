# UDE-002 — Source of Truth Stages

WP: **UDE-002** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Evidence: ADR-UDE-016; UDE-000 T028; OP-RES-006A §17

---

## 1. Purpose

Refine **staged Source of Truth** for the Draft Intake and Draft Workspace phases. UDE-001 defined four phases; UDE-002 expands to **five stages** covering the full path from submission to signed snapshot.

---

## 2. Five Stages

```text
Stage 1: Submitted Text
    ↓
Stage 2: Workspace Effective Draft
    ↓
Stage 3: Semantic Model (enriched)
    ↓
Stage 4: Official Effective Draft
    ↓
Stage 5: Signed Snapshot
```

---

## 3. Stage Definitions

| Stage | Name | Authority | Location | Valid when |
|---|---|---|---|---|
| **1** | Submitted Text | Author-origin wording + provenance | DraftBlock.submitted | Intake → enrichment start |
| **2** | Workspace Effective Draft | Editorial interim wording | DraftBlock.workspace_effective | Editorial processing |
| **3** | Semantic Model | Structured obligations, parties, objects | SemanticEnrichmentState | Enrichment → pre-promotion |
| **4** | Official Effective Draft | Reconciled effective + validated semantic | Promotion package → Document DRAFT | OFFICIAL_DRAFT_READY → READY_FOR_SIGNATURE |
| **5** | Signed Snapshot | Immutable effective bilingual | Document signed snapshot | SIGNED / REGISTERED |

---

## 4. Authority Rules per Stage

### Stage 1 — Submitted Text

| Aspect | Rule |
|---|---|
| **SoT for** | Provenance disputes; author intent reference |
| **Not SoT for** | Signing; semantic validation; official wording |
| **Mutability** | Immutable after capture |
| **ADR** | ADR-UDE-012, ADR-UDE-016 |

### Stage 2 — Workspace Effective Draft

| Aspect | Rule |
|---|---|
| **SoT for** | Editorial presentation during Workspace work |
| **Coexists with** | Submitted text (preserved); partial semantic model |
| **Mutability** | Editable with provenance chain |
| **Promotion** | Feeds Stage 4; never auto-replaces submitted |

### Stage 3 — Semantic Model

| Aspect | Rule |
|---|---|
| **SoT for** | Management meaning; obligation structure; regeneration input |
| **May be** | Partial during enrichment |
| **Mutability** | Enrichment edits; invalidates dependent generated text |
| **ADR** | ADR-UDE-005 (pre-sign semantic authority) |

### Stage 4 — Official Effective Draft

| Aspect | Rule |
|---|---|
| **SoT for** | Signing preparation; bilingual reconciliation |
| **Requires** | Semantic + effective consistency |
| **Location** | Workspace at OFFICIAL_DRAFT_READY; then Document LocaleRepresentation |
| **Gates** | Content confirmation; localization CURRENT |

### Stage 5 — Signed Snapshot

| Aspect | Rule |
|---|---|
| **SoT for** | Legal immutability; PDF; audit |
| **Mutability** | None — amendment requires new document |
| **ADR** | ADR-UDE-009 |

---

## 5. Stage Transitions

| From | To | Trigger |
|---|---|---|
| 1 → 2 | First editorial acceptance of wording | Operator saves workspace effective |
| 2 → 3 | Semantic mapping begins | Enrichment milestone |
| 3 → 4 | Promotion readiness | Validation + confirmation + localization |
| 4 → 5 | Signature | Lifecycle SIGNED transition |

Stages 1–3 may **overlap** in Workspace. Stage 4 is the convergence point.

---

## 6. Mapping to UDE-001 Phases

| UDE-001 Phase | UDE-002 Stages |
|---|---|
| Early Intake | Stage 1 |
| Editorial Draft | Stages 2 + 3 (parallel) |
| Ready for Signature | Stage 4 |
| After Signature | Stage 5 |

---

## 7. SourceOfTruth Value Object

| Value | Active stage |
|---|---|
| SUBMITTED | Stage 1 |
| WORKSPACE_EFFECTIVE | Stage 2 |
| SEMANTIC | Stage 3 |
| OFFICIAL_EFFECTIVE | Stage 4 |
| SIGNED | Stage 5 |

Used in policy decisions — not a runtime enum in UDE-002.

---

## 8. Conflict Resolution

| Conflict | Resolution |
|---|---|
| Submitted vs workspace effective | Both preserved; effective does not delete submitted |
| Semantic vs effective mismatch | Block promotion (W201); clarification or reconcile |
| Generated vs override | override ?? generated (Stage 4) |
| Post-sign semantic edit attempt | Rejected — Stage 5 frozen |

---

*Diagram: [`diagrams/staged-source-of-truth.svg`](./diagrams/staged-source-of-truth.svg)*
