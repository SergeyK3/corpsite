# UDE-002 — Editorial Boundary

WP: **UDE-002** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Purpose

Define **Editorial Processing Boundary** — what happens after Draft Intake in Draft Workspace, and what explicitly does **not** belong to editorial processing.

---

## 2. Editorial Boundary Position

```text
Draft Intake ends ──► Editorial Processing begins (in Workspace)
                           │
                           ├── inside editorial boundary
                           └── outside → lifecycle, sign, register, projection, PDF
```

Editorial Processing ends at **OFFICIAL_DRAFT_READY** — handoff to Document promotion and UDE-003 Shared Editorial Core.

---

## 3. Inside Editorial Boundary

| Activity | Actor | Output |
|---|---|---|
| **Structuring** | Editorial Processor | Document shell blocks identified |
| **Numbering** | Editorial Processor | OrderItemSequence draft |
| **Form editing** | Document Operator | Header chrome, formula, date placeholders |
| **Content editing** | Document Operator (with confirmation) | WorkspaceEffectiveDraft updates |
| **Mandatory block addition** | Editorial Processor | Preamble, formula, control meta-item |
| **Semantic mapping** | Editorial Processor + enrichment | Partial → full semantic model |
| **Obligation extraction** | Enrichment | ExecutionObligation drafts |
| **Party resolution** | Enrichment | PartyReference candidates |
| **RU/KK alignment** | Translator + Reviewer | Reconciliation state |
| **Translation** | Translator | TRANSLATED blocks with provenance |
| **Attachment normalization** | Operator | Draft → official attachment candidates |
| **Content confirmation** | Content Author | confirmed_by recorded |
| **Official draft assembly** | Operator | Promotion package |

---

## 4. Outside Editorial Boundary

| Activity | Contour | Why outside |
|---|---|---|
| Registration | Document lifecycle | Requires DocumentId |
| Number assignment (official) | Document lifecycle | Journal sequence |
| READY_FOR_SIGNATURE transition | Document lifecycle | Post-promotion |
| Signing | Document lifecycle | Legal act |
| PDF generation | Renderer/Exporter | Operates on Document effective text |
| Archive | Document orthogonal flag | Post-existence |
| Execution projection | Downstream | After REGISTERED |
| Task creation | Task engine | Downstream |

---

## 5. Edit Classification

Drives Content Confirmation policy (default; interview may refine OQ-04).

| Class | Examples | Confirmation required (default) |
|---|---|---|
| **Form-only** | Numbering, title chrome, city, date placeholder, ПРИКАЗЫВАЮ formula, исп. line formatting | No |
| **Content** | Executors, deadlines, subject matter, controller, commission composition, attachment meaning | **Yes** |
| **Structural-content** | Item split/merge with semantic impact | **Yes** |
| **Localization-only** | KK terminology, calque fix without meaning change | Localization review; author optional |

Edit class recorded in TextProvenance and DraftAuditEvent.

---

## 6. Editorial Workspace vs UDE-003

| UDE-002 (this WP) | UDE-003 (next WP) |
|---|---|
| Editorial boundary definition | Shared Editorial Core implementation contract |
| What happens in Workspace | How Document aggregate hosts effective/generated |
| WorkspaceEffectiveDraft | EffectiveText in LocaleRepresentation |
| Pre-Document editorial rules | Post-promotion editorial rules + write locks |

UDE-002 defines **what** editorial work occurs and **where** (Workspace). UDE-003 defines **how** the editorial engine operates on Document.

---

## 7. Semantic Enrichment Boundary

Semantic enrichment is **inside** editorial boundary but **distinct** from pure form editing:

```text
submitted text → editorial normalization → semantic mapping
  → obligation extraction → party resolution → managed object ID
  → validation → official draft
```

- No NLP/ML specified
- Progressive manual mapping supported
- Partial semantic model valid until OFFICIAL_DRAFT_READY
- May transition Workspace from Model C → Model A path after mapping complete

---

## 8. Multi-editor Rules

| Role | Editorial permissions in Workspace |
|---|---|
| Document Operator | Form edits; structure; routing |
| Editorial Processor | Numbering; shell; enrichment |
| Translator | TRANSLATED blocks only |
| Localization Reviewer | Review flags; not content author |
| Content Author | Confirmation; optional direct edits (audited) |
| Content Author | **Not** record creator by default |

---

## 9. What Editorial Does NOT Do

- Auto-promote submitted to effective
- Auto-create Document
- Auto-READY
- Assign HR as content author
- Mark KK reviewed without localization review
- Hide provenance of edits
- Start lifecycle or projection

---

*Diagram: [`diagrams/editorial-boundary.svg`](./diagrams/editorial-boundary.svg)*
