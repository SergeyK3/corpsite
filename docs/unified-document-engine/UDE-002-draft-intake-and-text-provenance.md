# UDE-002 — Draft Intake and Text Provenance Architecture

WP: **UDE-002** — Draft Intake and Text Provenance Architecture  
Date: **2026-07-12**  
Status: **Architecture Foundation — Complete**  
Prerequisites: UDE-000 ✓ · UDE-001 ✓  
Mode: **No runtime changes** — architecture only

**Artifacts:**

| Document | Purpose |
|---|---|
| [UDE-002-draft-workspace.md](./UDE-002-draft-workspace.md) | Draft Workspace — central deliverable |
| [UDE-002-submitted-draft-model.md](./UDE-002-submitted-draft-model.md) | Submitted Draft vs Document distinctions |
| [UDE-002-text-provenance-model.md](./UDE-002-text-provenance-model.md) | Provenance granularity and attributes |
| [UDE-002-intake-validation.md](./UDE-002-intake-validation.md) | I001–I026 + W2xx validation |
| [UDE-002-editorial-boundary.md](./UDE-002-editorial-boundary.md) | Editorial processing scope |
| [UDE-002-source-of-truth-stages.md](./UDE-002-source-of-truth-stages.md) | Five-stage SoT model |
| [`data/`](./data/) | Workspace, transition, provenance, validation, readiness matrices |
| [`diagrams/`](./diagrams/) | Eight architecture diagrams |

---

## 1. Purpose

UDE-002 answers the implementation-phase question:

> **How does a document enter the system before it becomes an official Document Aggregate?**

The coarse model `Submitted Text → Document` is replaced by a full intermediate architecture:

```text
Submitted Draft → Draft Intake → Draft Workspace → Semantic Enrichment
  → Editorial Processing → Official Draft → Document Aggregate → Signed Snapshot
```

**Draft Workspace** is the central deliverable — a temporary bounded context with its own aggregate root, distinct from Document.

---

## 2. Scope

### 2.1 In scope

- Draft Intake domain boundaries
- Draft Workspace architecture (aggregate classification, lifecycle, contents)
- Submitted Draft model and minimum P0 requirements
- Draft Submission contract (channels conceptual)
- Text Provenance refinement (per-block minimum)
- Draft Metadata (pre-Document fields)
- Intake Validation (no lifecycle)
- Editorial Processing boundary
- Semantic Enrichment stages (no NLP)
- Clarification model
- Draft Attachments (three kinds)
- Draft Audit (separate from Lifecycle Audit)
- Five-stage Source of Truth
- Workspace → Document transition rules
- UDE-001 contract mapping
- UDE-003 handoff package

### 2.2 Out of scope

- Production code, ORM, SQL, API, UI
- Upload implementation
- Personnel Orders runtime changes
- Operational Orders runtime
- Commit, push, deploy
- OP-RES document modifications

### 2.3 Non-blocking clarification

ContentConfirmationPolicy per change class (OQ-04 interview) — default policy defined; does not block UDE-002 completion.

---

## 3. Draft Intake Domain

### 3.1 Responsibility

Draft Intake **is responsible for:**

| Function | Detail |
|---|---|
| Accept document project | External or internal draft via any channel |
| Determine provenance | source, author, unit, channel, timestamp |
| Determine authorship | content_author, submitter, initiator — explicit |
| Completeness check | Intake validation I001–I026 |
| Create workspace | Instantiate DraftWorkspace aggregate |
| Preserve provenance | Immutable submitted capture |
| Launch editorial processing | Transition to EDITORIAL_PROCESSING |

### 3.2 Explicitly NOT responsible

| Excluded | Contour |
|---|---|
| Registration | Document lifecycle |
| Lifecycle transitions | Document aggregate |
| Signing | Document lifecycle |
| Execution / projection | Downstream |
| PDF generation | Renderer |
| Archive | Document orthogonal flag |

### 3.3 Boundaries

```text
[External world] ──Draft Submission──► [Draft Intake] ──accept──► [Draft Workspace]
                                              │
                                              └── reject → no Workspace, no Document
```

**Forbidden behaviors (ADR-UDE-011, 012, 015):**

- Auto-promote submitted to effective
- Auto-READY or auto-Document
- Assign HR as content author by default
- Treat KK as reviewed without localization review
- Hide edit provenance

Diagram: [`diagrams/draft-intake-overview.svg`](./diagrams/draft-intake-overview.svg)

---

## 4. Submitted Draft

**Submitted Draft** is the pre-Workspace capture — not Document, not Official Draft.

| Entity | Authority | System identity |
|---|---|---|
| Submitted Draft | Author origin | SubmittedDraftId |
| Official Draft | Validated package in Workspace | PromotionReadiness |
| Document | Legal act | DocumentId |
| Signed Document | Immutable snapshot | Post-SIGNED |

**May contain:** RU only, KK only, both, partial text, Word/PDF refs, notes, attachment drafts.

**Minimum P0 (OO):** content_author, submitting_unit, submitter, title, ≥1 item body, RU or policy waiver, KK or missing-KK declaration, provenance, no contradictions.

Detail: [UDE-002-submitted-draft-model.md](./UDE-002-submitted-draft-model.md)

---

## 5. Draft Workspace

### 5.1 What is Draft Workspace?

**Draft Workspace** is a **temporary bounded context** hosting the **DraftWorkspace aggregate root** — a distinct consistency boundary from Document.

| Question | Answer |
|---|---|
| Separate aggregate? | **Yes** |
| Editorial container only? | **Insufficient alone** — requires aggregate for provenance and multi-iteration integrity |
| Document in disguise? | **No** — DocumentId does not exist during Workspace |
| Temporary bounded context? | **Yes** — lives from intake acceptance until promotion or abandonment |

### 5.2 Contents

Submitted texts, locale versions, provenance, draft metadata, validation state, editorial changes, translation state, clarifications, semantic enrichment progress, content confirmation status, attachment drafts, draft audit.

### 5.3 Lifecycle (conceptual stages)

`SUBMITTED → ACCEPTED → WORKSPACE_CREATED → EDITORIAL_PROCESSING → SEMANTIC_ENRICHMENT → LOCALIZATION_PROCESSING → CONTENT_CONFIRMATION → OFFICIAL_DRAFT_READY → DOCUMENT_PROMOTED | ABANDONED`

Not Document lifecycle. Not runtime enum.

Detail: [UDE-002-draft-workspace.md](./UDE-002-draft-workspace.md)  
Diagram: [`diagrams/draft-workspace-lifecycle.svg`](./diagrams/draft-workspace-lifecycle.svg)

---

## 6. Draft Metadata

Pre-Document metadata captured at intake and enriched in Workspace:

| Field | Mandatory (OO) | Maps to Document |
|---|---|---|
| initiator | Optional | Audit reference |
| content_author | **Yes** | DocumentMetadata.content_author |
| submitting_unit | **Yes** (OO) | DocumentMetadata |
| document_operator | At workspace creation | Record Creator at promotion |
| language_set | Derived | Localization policy |
| attachments | Optional | AttachmentReference |
| submission_channel | **Yes** | Provenance |
| submission_date | **Yes** | Provenance |
| requested_signer | Optional hint | Signing metadata |
| document_family / kind_hint | **Yes** | DocumentKind |
| drafting_path | Inferred or declared | DraftingPath VO |

**Rule:** `content_author ≠ created_by` (record creator assigned at promotion).

---

## 7. Text Provenance

### 7.1 Granularity

| Level | MVP |
|---|---|
| Draft aggregate | Summary bilingual readiness |
| Locale | Completeness, translation origin |
| Section/Block | **Minimum sufficient** |
| Item | When items identified |

### 7.2 Mandatory attributes (per block)

`source`, `author`, `organization`, `language`, `submitted_at`, `derived_from`, `translation_origin`, `edited_by`, `confirmed_by`

### 7.3 Rules

- Submitted text immutable; provenance append-only
- TRANSLATED requires `translation_origin`
- No silent overwrite (I026)
- Carried forward to Document LocaleRepresentation at promotion

Detail: [UDE-002-text-provenance-model.md](./UDE-002-text-provenance-model.md)  
Diagram: [`diagrams/draft-provenance-model.svg`](./diagrams/draft-provenance-model.svg)

---

## 8. Intake Validation

Eight layers; **does not use Document lifecycle.**

| Layer | Severity mix |
|---|---|
| Metadata | Errors (I001–I004) |
| Structure | Errors + warnings (I007–I013) |
| Localization | Errors (I019–I020) + warnings |
| Semantic completeness | Warnings + clarification |
| Attachment completeness | Errors when attachment-driven |
| Provenance completeness | Errors (I023–I026) |
| Content ownership | Errors (author ≠ operator) |
| Translation readiness | Warnings + clarification |

| Severity | Effect |
|---|---|
| **Blocking** | Reject intake or block promotion |
| **Warning** | Proceed with audit |
| **Clarification required** | Pause progression until resolved |

Workspace promotion gates: W201–W204.

Detail: [UDE-002-intake-validation.md](./UDE-002-intake-validation.md)  
Diagram: [`diagrams/intake-validation-flow.svg`](./diagrams/intake-validation-flow.svg)

---

## 9. Editorial Processing Boundary

**Inside:** structuring, numbering, form/content edits, mandatory blocks, semantic mapping, obligation extraction, party resolution, RU/KK alignment, translation, attachment normalization, content confirmation, official draft assembly.

**Outside:** registration, lifecycle, signing, PDF, archive, execution projection.

**Edit classification:** form-only (no confirmation default) vs content (confirmation required default).

Detail: [UDE-002-editorial-boundary.md](./UDE-002-editorial-boundary.md)  
Diagram: [`diagrams/editorial-boundary.svg`](./diagrams/editorial-boundary.svg)

---

## 10. Semantic Enrichment

Progressive transformation of free text to semantic model — **no NLP**:

```text
submitted text → editorial normalization → semantic mapping
  → obligation extraction → party resolution → managed object identification
  → validation → official draft
```

| Property | Rule |
|---|---|
| Partial model | Valid until OFFICIAL_DRAFT_READY |
| Model C → Model A | Allowed after mapping complete |
| Regeneration | Not in Workspace scope (UDE-003/OO-IMP-003) |

---

## 11. Draft Audit

**Draft Audit** — append-only history **before** Document exists.

| Event | When |
|---|---|
| DRAFT_SUBMITTED | Submission captured |
| INTAKE_ACCEPTED / REJECTED | Intake decision |
| WORKSPACE_CREATED | Aggregate instantiated |
| EDITORIAL_EDIT | Operator/processor change |
| TRANSLATION_ADDED | KK block created |
| CLARIFICATION_REQUESTED / RESOLVED | Clarification cycle |
| CONTENT_CONFIRMATION_* | Confirmation workflow |
| WORKSPACE_PROMOTED | Document created |

**Lifecycle Audit** starts at DOCUMENT_PROMOTED only. Draft Audit preserved as Workspace archive; summary linked at promotion.

---

## 12. Clarification Model

Handles incomplete intake without rejection.

| Trigger | Example |
|---|---|
| Missing text | Incomplete item body |
| Unclear executor | I014 clarification |
| Missing deadline | I015 |
| Missing KK | I020 declared + translation path |
| Missing attachment | I013 |
| Unclear author | I002 follow-up |
| Missing basis | I006 |

```text
ClarificationRequest
├── question_scope (metadata | semantic | localization | attachment)
├── severity: clarification_required
├── status: open | resolved
└── resolution_ref (text, attachment, or metadata update)
```

**Not a workflow engine** — state derived from validation + audit. Multiple cycles supported.

---

## 13. Attachments

| Kind | Phase | Fate at promotion |
|---|---|---|
| **Submitted attachments** | Intake | Promoted if validated → AttachmentReference |
| **Workspace attachments** | Editorial | Normalized → official |
| **Generated-in-workspace** | Enrichment | e.g. commission roster draft → official |

Submitted attachments retain provenance link to submission channel.

---

## 14. Workspace to Document Transition

### 14.1 Relationship chain

```text
Submitted Draft → Draft Workspace → Official Draft → Document Aggregate → Signed Snapshot
```

### 14.2 Key timing

| Event | When |
|---|---|
| **WorkspaceId** | ACCEPTED / WORKSPACE_CREATED |
| **DocumentId** | DOCUMENT_PROMOTED only |
| **Document created** | OFFICIAL_DRAFT_READY + promotion command + W201–W204 pass |
| **Lifecycle starts** | DOCUMENT_PROMOTED — initial state DRAFT |
| **Lifecycle Audit starts** | DOCUMENT_PROMOTED |
| **Draft Audit** | From DRAFT_SUBMITTED; frozen at promotion |
| **Projection** | After REGISTERED — not in UDE-002 scope |

### 14.3 Promotion package (OfficialDraftPackage)

Transferred to Document Aggregate:

- DocumentMetadata (authorship, kind, operator as created_by)
- DocumentStructure shell
- OrderItem[] with semantic_payload
- LocaleRepresentation[] with EffectiveText + TextProvenance
- AttachmentReference[]
- ValidationResult (promotion gate clearance)

**Preserved in Workspace archive:** SubmittedText immutable copies, full DraftAuditEvent[], clarification history.

Diagram: [`diagrams/submitted-draft-to-document.svg`](./diagrams/submitted-draft-to-document.svg)  
Matrix: [`data/UDE-002-transition-matrix.csv`](./data/UDE-002-transition-matrix.csv)

---

## 15. Source of Truth Stages

Five stages (UDE-002 refinement of UDE-001 four phases):

| Stage | Authority | Location |
|---|---|---|
| 1 Submitted Text | Author origin | DraftBlock.submitted |
| 2 Workspace Effective Draft | Editorial interim | DraftBlock.workspace_effective |
| 3 Semantic Model | Management meaning | SemanticEnrichmentState |
| 4 Official Effective Draft | Signing preparation | Promotion → Document |
| 5 Signed Snapshot | Legal immutability | Document SIGNED |

Stages 1–3 overlap in Workspace. Stage 4 converges at OFFICIAL_DRAFT_READY.

Detail: [UDE-002-source-of-truth-stages.md](./UDE-002-source-of-truth-stages.md)  
Diagram: [`diagrams/staged-source-of-truth.svg`](./diagrams/staged-source-of-truth.svg)

---

## 16. Shared Contract Mapping (UDE-001)

| UDE-001 Contract | UDE-002 role |
|---|---|
| SubmittedText | DraftBlock.submitted — immutable |
| TextProvenance | Per-block in Workspace; copied at promotion |
| LocaleRepresentation | Target shape; built during enrichment |
| GeneratedText | Optional in Workspace after enrichment |
| EffectiveText | Official effective at Stage 4 / promotion |
| DocumentMetadata | DraftMetadata → promoted |
| PartyReference | content_author, submitter, parties in enrichment |
| AttachmentReference | DraftAttachment → promoted |
| ContentConfirmation | ContentConfirmationState in Workspace |
| ValidationResult | IntakeValidationState + promotion gate |
| Document | Created at promotion only |
| DocumentAuditEvent | Starts at promotion; not Draft Audit |
| DocumentLifecycleState | Starts DRAFT at promotion |
| LocalizationLifecycleState | LocalizationState in Workspace |
| OrderItem | Built during enrichment; promoted |
| ExecutionObligation | Drafted in enrichment; promoted |

| UDE-001 VO | UDE-002 usage |
|---|---|
| DraftingPath | SUBMITTED_INTAKE default for OO |
| TextSourceType | Provenance discriminator |
| SourceOfTruth | Five stages |
| LocaleCode | Per-block locale payloads |
| RoleReference | Author, submitter refs |

| UDE-001 Extension Point | UDE-002 usage |
|---|---|
| Localization Registry | Mandatory locales, missing-KK policy |
| Lifecycle Registry | No lifecycle until promotion; intake guards |
| Attachment Registry | Draft attachment kinds |

---

## 17. Compatibility

| Target | Impact |
|---|---|
| **Personnel Orders** | No runtime change. PO may bypass Workspace (Model A/B). UDE-006 adapter for convergence. |
| **Operational Orders** | Model C P0 path fully specified. OO-IMP-001 implements against this architecture. |
| **Future families** | Same Draft Intake + Workspace contracts; kind-specific validation hooks. |

Workspace does not break existing PO behavior — it is additive architecture.

---

## 18. Readiness Review

| Component | Status | Notes |
|---|---|---|
| Draft Intake Domain | **Ready** | |
| Draft Workspace | **Ready** | Central deliverable |
| Submitted Draft | **Ready** | |
| Draft Submission Contract | **Ready** | Channels deferred to OO-IMP-001 |
| Text Provenance | **Ready** | |
| Draft Metadata | **Ready** | |
| Intake Validation | **Ready** | |
| Editorial Boundary | **Ready** | |
| Semantic Enrichment | **Ready** | No NLP |
| Clarification Model | **Ready** | |
| Draft Attachments | **Ready** | |
| Draft Audit | **Ready** | |
| Source of Truth Stages | **Ready** | |
| Workspace → Document Transition | **Ready** | |
| ContentConfirmationPolicy | **Needs clarification** | OQ-04; default defined |
| Upload/API implementation | **Deferred** | OO-IMP-001 |
| PO Workspace adapter | **Deferred** | UDE-006 |
| NLP obligation extraction | **Rejected** | Explicit non-goal |

Matrix: [`data/UDE-002-readiness.csv`](./data/UDE-002-readiness.csv)

---

## 19. Handoff to UDE-003

**UDE-003 — Shared Editorial and Localization Core** receives from Draft Workspace:

### At promotion (Document created)

| From Workspace | To Document (UDE-003) |
|---|---|
| OfficialDraftPackage | Document aggregate initialization |
| LocaleRepresentation shape | Editorial Core per-block state |
| EffectiveText | override ?? generated chain |
| TextProvenance | Carried forward |
| OrderItem semantic_payload | OrderItem contract |
| LocalizationState | LocalizationLifecycleState |
| DocumentStructure shell | DocumentStructure |

### Contracts UDE-003 must implement

- DocumentContract (post-promotion mutations)
- OrderItemContract (item-level regeneration)
- LocalizationContract (staleness, reconciliation)
- LifecycleContract (DRAFT write locks → READY)
- AttachmentContract (official attachments)

### Policies UDE-003 inherits

- LocalizationPolicy (mandatory locales, BC checks)
- TranslationPolicy (post-promotion staleness BC023)
- ArchivePolicy, AuditPolicy (Lifecycle Audit continuation)
- GenerationPolicy shape (orchestration — templates in OO-IMP-003)

### What UDE-003 does NOT re-design

- Draft Intake boundaries
- Workspace aggregate
- Submitted text immutability
- Pre-promotion provenance rules

---

## 20. Conclusions

UDE-002 replaces the coarse `Submitted Text → Document` model with a complete pre-Document architecture:

1. **Draft Intake** — acceptance, authorship, validation, provenance capture  
2. **Draft Workspace** — temporary bounded context with own aggregate root  
3. **Text Provenance** — per-block minimum, five-stage SoT  
4. **Editorial Boundary** — clear inside/outside scope  
5. **Promotion** — DocumentId and lifecycle begin only at DOCUMENT_PROMOTED  

No runtime impact. Full foundation for UDE-003 Shared Editorial Core and OO-IMP-001 intake MVP.

**Next authorized WP:** UDE-003 — Shared Editorial and Localization Core.

---

## Mandatory Answers

### 1. Что такое Draft Workspace?

Временный **bounded context** с собственным aggregate root (`DraftWorkspace`), содержащий весь предофициальный материал: submitted texts, provenance, enrichment, editorial changes, clarifications, confirmation — до promotion в Document.

### 2. Является ли он Aggregate?

**Да.** Отдельный aggregate root с WorkspaceId, собственным Draft Audit и consistency boundary. **Не** является Document aggregate.

### 3. Когда создаётся Document?

При переходе **DOCUMENT_PROMOTED** — когда Workspace достиг OFFICIAL_DRAFT_READY и прошёл gates W201–W204.

### 4. Когда начинается Lifecycle?

При **DOCUMENT_PROMOTED** — Document создаётся в состоянии DRAFT. До этого lifecycle не существует.

### 5. Когда появляется Audit?

**Draft Audit** — с DRAFT_SUBMITTED. **Lifecycle Audit** — с DOCUMENT_PROMOTED. Два контура, не смешиваются.

### 6. Когда появляется DocumentId?

Только при **DOCUMENT_PROMOTED**. Workspace использует WorkspaceId с момента ACCEPTED.

### 7. Где хранится Submitted Text?

В **DraftBlock.submitted** внутри Draft Workspace (SubmittedDraftSnapshot). Immutable. Сохраняется в Workspace archive после promotion.

### 8. Где хранится Effective Draft?

**Stage 2–4:** DraftBlock.workspace_effective (Workspace Effective Draft) → Official Draft package. **После promotion:** Document LocaleRepresentation.EffectiveText.

### 9. Где хранится Semantic Model?

В **SemanticEnrichmentState** внутри Draft Workspace (partial OK). При promotion → OrderItem.semantic_payload в Document Aggregate.

### 10. Как работает Provenance?

Per-block TextProvenance: source, author, org, language, timestamps, derived_from, translation_origin, edited_by, confirmed_by. Append-only chain. SUBMITTED immutable. Копируется в Document при promotion.

### 11. Какие Validation выполняются?

Intake: I001–I026 (metadata, structure, localization, semantic, provenance). Workspace promotion: W201–W204. Severity: blocker, warning, clarification. **Без Document lifecycle.**

### 12. Что такое Editorial Boundary?

Граница редакционной обработки в Workspace: structuring, numbering, edits, enrichment, translation, confirmation. **Вне границы:** registration, lifecycle, sign, PDF, projection.

### 13. Что такое Clarification?

Пауза прогрессии при `clarification_required` — не rejection. ClarificationRequest open → resolved. Множественные циклы. Не workflow engine.

### 14. Когда появляется Official Draft?

При достижении **OFFICIAL_DRAFT_READY** — validated semantic + reconciled effective locales + confirmations. Ещё в Workspace; Document не создан.

### 15. Что передаётся в UDE-003?

OfficialDraftPackage: DocumentMetadata, DocumentStructure, OrderItem[], LocaleRepresentation[] с EffectiveText и Provenance, AttachmentReference[], ValidationResult. UDE-003 реализует post-promotion Editorial Core и lifecycle write locks.

---

*UDE-002 completed 2026-07-12. No runtime changes. Prerequisites for UDE-003 satisfied.*
