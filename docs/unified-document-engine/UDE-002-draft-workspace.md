# UDE-002 — Draft Workspace

WP: **UDE-002** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Central Question

**What is Draft Workspace?**

Draft Workspace is a **temporary bounded context** with its **own aggregate root** (`DraftWorkspace`), distinct from the Document aggregate. It is the editorial and enrichment container that exists **before** an official Document instance is created.

It is **not** a Document aggregate in DRAFT state. It is **not** a mere UI screen. It is an architectural container with its own identity, lifecycle, audit, and consistency boundary.

---

## 2. Architectural Classification

| Option | Verdict | Rationale |
|---|---|---|
| Separate aggregate from Document | **Yes — recommended** | Different consistency boundary, different lifecycle, different audit; intake mutations must not touch Document lifecycle |
| Editorial container only (no aggregate) | **Insufficient** | Cannot enforce provenance immutability, clarification cycles, or multi-iteration state without a root |
| Document aggregate in disguise | **Rejected** | Would start Document lifecycle at intake; violates ADR-UDE-012 (no auto-READY) and staged SoT |
| Temporary bounded context | **Yes** | Exists only from intake acceptance until Document promotion or abandonment |

**Conclusion:** Draft Workspace = **temporary bounded context** hosting **DraftWorkspace aggregate root**.

---

## 3. Purpose

Draft Workspace holds everything required to transform an external or internal project into an **Official Draft** ready for promotion to Document Aggregate:

| Responsibility | Detail |
|---|---|
| Preserve submitted origin | Submitted text immutable; provenance chain |
| Host editorial work | Structure, numbering, form-only and content edits |
| Track enrichment | Progressive semantic model construction |
| Manage localization | Translation state, RU/KK alignment, staleness |
| Gate promotion | Validation, clarification, content confirmation |
| Isolate pre-official work | No registration, signing, projection, archive |

---

## 4. Contents

```text
DraftWorkspace (Aggregate Root)
├── WorkspaceId                    # created at intake acceptance
├── WorkspaceState                 # conceptual stages (not document lifecycle)
├── DraftMetadata                  # authorship, channel, drafting path
├── SubmittedDraftSnapshot         # frozen intake capture
├── DraftBlocks[]                  # text-bearing units (section/item level)
│     ├── SubmittedText
│     ├── WorkspaceEffectiveDraft  # editorial authority pre-document
│     ├── TextProvenance
│     ├── LocalizationState
│     └── SemanticEnrichmentRef    # link to partial semantic mapping
├── SemanticEnrichmentState        # progressive model (partial OK)
├── DraftAttachments[]             # submitted + workspace + generated-in-workspace
├── IntakeValidationState          # I001–I026 + clarifications
├── ClarificationRequests[]        # open/resolved cycles
├── ContentConfirmationState       # pending/confirmed/rejected
├── DraftAuditEvent[]              # append-only; separate from Document audit
└── PromotionReadiness             # gate for Document creation
```

---

## 5. What Workspace Stores vs Document

| Stored in Workspace only | Promoted to Document | Never in Workspace |
|---|---|---|
| Raw submitted text (immutable) | Official effective text | Document lifecycle state |
| Intake validation (I*) | DocumentMetadata (authorship) | Registration number (final) |
| Clarification requests | DocumentStructure shell | Signed snapshot |
| Workspace effective draft (interim) | OrderItem semantic_payload | Execution projection |
| Draft audit events | LocaleRepresentation (official) | Archive state |
| Enrichment progress markers | AttachmentReference (official) | VOIDED transitions |
| Submission channel metadata | TextProvenance (carried forward) | Task runtime |

**Submitted text** remains in Workspace as historical record after promotion (read-only archive link). Document carries forward provenance references, not a silent overwrite.

---

## 6. Workspace Lifecycle (Conceptual Stages)

Not a Document lifecycle. Not a runtime enum.

```text
SUBMITTED → ACCEPTED → WORKSPACE_CREATED → EDITORIAL_PROCESSING
    → SEMANTIC_ENRICHMENT → LOCALIZATION_PROCESSING
    → CONTENT_CONFIRMATION → OFFICIAL_DRAFT_READY
    → DOCUMENT_PROMOTED | ABANDONED
```

| Stage | Meaning |
|---|---|
| SUBMITTED | External draft received; pre-acceptance |
| ACCEPTED | Intake validation passed minimum; WorkspaceId assigned |
| WORKSPACE_CREATED | Aggregate instantiated; provenance captured |
| EDITORIAL_PROCESSING | HR/operator structuring and form edits |
| SEMANTIC_ENRICHMENT | Progressive obligation/party/deadline mapping |
| LOCALIZATION_PROCESSING | Translation, review, reconciliation |
| CONTENT_CONFIRMATION | Author meaning acknowledgment (if required) |
| OFFICIAL_DRAFT_READY | All promotion gates passed |
| DOCUMENT_PROMOTED | Document Aggregate created; Workspace frozen |
| ABANDONED | Intake rejected or withdrawn; no Document |

Diagram: [`diagrams/draft-workspace-lifecycle.svg`](./diagrams/draft-workspace-lifecycle.svg)

---

## 7. Multi-actor and Multi-iteration Support

| Capability | Mechanism |
|---|---|
| Multiple editors | Document Operator, Editorial Processor, Translator — system actors in DraftAuditEvent |
| Multiple languages | Per-block DraftBlocks with independent LocalizationState |
| Multiple iterations | Clarification cycles; resubmission creates new SubmittedDraftSnapshot version linked by provenance |
| Multiple clarification cycles | ClarificationRequest open → resolved → may reopen on new edit |

Workspace does **not** implement workflow engine. Stages are **derived** from validation state + audit, consistent with T034 Editorial Substate.

---

## 8. Relationship to Document Aggregate

```text
Submitted Draft ──intake──► Draft Workspace ──promotion──► Document Aggregate ──sign──► Signed Snapshot
     │                            │                              │
     │                            │                              └── DocumentId, Lifecycle, Lifecycle Audit
     │                            └── WorkspaceId, Draft Audit, Workspace State
     └── Pre-system or channel entry
```

| Event | Workspace | Document |
|---|---|---|
| Intake acceptance | Created | Does not exist |
| Editorial edits | Mutations allowed | Does not exist |
| Official Draft Ready | Promotion gate open | Still does not exist |
| Document Created | Frozen (read-only) | Created in DRAFT |
| READY_FOR_SIGNATURE | Frozen reference | Lifecycle transition |
| SIGNED | Historical link | Immutable snapshot |

**One Workspace → one Document** (1:1 promotion). Resubmission after abandonment creates new Workspace.

---

## 9. Identity Rules

| Identifier | When created | Scope |
|---|---|---|
| **WorkspaceId** | At ACCEPTED / WORKSPACE_CREATED | Draft bounded context |
| **DocumentId** | At DOCUMENT_PROMOTED / Document Created | Document aggregate |
| **SubmittedDraftId** | At SUBMITTED capture | Immutable intake snapshot |

DocumentId **must not** exist during Workspace editorial work. PO today creates document early — UDE target defers DocumentId until promotion (OO MVP path). PO convergence (UDE-006) may adapter-map existing early-creation pattern.

---

## 10. Audit Separation

| Audit type | Scope | Starts |
|---|---|---|
| **Draft Audit** | Workspace mutations | At DRAFT_SUBMITTED |
| **Document Lifecycle Audit** | Document aggregate | At DOCUMENT_PROMOTED |

Draft Audit events: `DRAFT_SUBMITTED`, `INTAKE_ACCEPTED`, `EDITORIAL_EDIT`, `TRANSLATION_ADDED`, `CLARIFICATION_REQUESTED`, `CLARIFICATION_RESOLVED`, `CONTENT_CONFIRMATION_REQUESTED`, `CONTENT_CONFIRMED`, `WORKSPACE_PROMOTED`.

Document Audit inherits provenance summary at promotion; does not replay full draft history.

---

## 11. Compatibility

| Specialization | Workspace usage |
|---|---|
| **Operational Orders MVP** | Primary path — Model C submitted-text intake |
| **Personnel Orders** | Optional — PO may skip Workspace (Model A/B direct Document); adapter in UDE-006 |
| **Future families** | Same Workspace contract; kind-specific intake validation hooks |

Workspace does not break PO: PO continues unchanged at runtime. Workspace is additive architecture.

---

## 12. Future Package Placement

```text
shared/intake/
├── draft-workspace/       # DraftWorkspace aggregate contract
├── draft-submission/      # submission channel contract
├── provenance/            # TextProvenance (shared with editorial)
├── intake-validation/     # I* checks
└── clarification/         # clarification model
```

---

*Draft Workspace is the central deliverable of UDE-002. See main document §5 and transition matrix for promotion rules.*
