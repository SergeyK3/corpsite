# UDE-003 — Official Draft Package

WP: **UDE-003** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**

---

## 1. Central Question

**What is Official Draft Package?**

Official Draft Package is the **validated editorial snapshot** produced by Shared Editorial & Localization Core when Draft Workspace reaches promotion readiness. It is the **handoff artifact** from Workspace to Document Aggregate — not a legal act, not a lifecycle entity.

---

## 2. Architectural Classification

| Option | Verdict | Rationale |
|---|---|---|
| Aggregate root | **No** | No independent lifecycle; no DocumentId; subordinate to Workspace until promotion |
| DTO / transfer object | **Partially** | Serializable bundle, but rich domain semantics — not anemic DTO |
| Editorial snapshot | **Yes — recommended** | Immutable-at-promotion composed view of structure, locales, semantics, validation |
| Separate bounded context | **No** | Produced inside Workspace boundary by shared core services |

**Conclusion:** Official Draft Package = **editorial snapshot (promotion handoff artifact)** within DraftWorkspace aggregate, frozen at `OFFICIAL_DRAFT_READY`.

---

## 3. Purpose

| Function | Detail |
|---|---|
| Converge editorial work | Structure + locales + semantics + attachments aligned |
| Prove promotion readiness | ValidationResult clearance; localization CURRENT |
| Define promotion payload | Exact content transferred to Document Aggregate |
| Freeze editorial state | No further Workspace mutations without reopening |

---

## 4. Contents

```text
OfficialDraftPackage
├── package_id / workspace_ref          # links to WorkspaceId
├── frozen_at                           # promotion readiness timestamp
├── document_kind                       # specialization selector
├── draft_metadata                      # authorship, operator, drafting_path
├── document_structure                  # ordered EditorialSection[]
├── order_items[]                       # semantic_payload + item editorial blocks
├── locale_bundle[]                     # per LocaleCode aggregate state
│     ├── locale_completeness
│     ├── localization_lifecycle_state
│     └── editorial_blocks[] per section/item
│           ├── generated_text
│           ├── override_text (optional)
│           ├── effective_text          # override ?? generated
│           ├── text_provenance
│           └── staleness_state
├── attachment_references[]             # official candidates
├── semantic_model_snapshot             # obligations, parties, objects
├── editorial_validation_result         # E* checks passed
├── localization_validation_result      # BC* + locale checks
├── promotion_readiness                 # boolean + blocker list
└── content_confirmation_state          # if applicable
```

---

## 5. Official Draft vs Document

| Aspect | Official Draft Package | Document Aggregate |
|---|---|---|
| **Identity** | package_ref / workspace_ref | DocumentId |
| **Legal status** | Pre-official editorial package | Legal act instance |
| **Lifecycle** | Workspace stage OFFICIAL_DRAFT_READY | DRAFT → READY → SIGNED |
| **Audit** | Editorial Audit culmination | Lifecycle Audit begins at promotion |
| **Mutability** | Frozen until promotion or reopen | DRAFT editable (post-promotion rules) |
| **Projection** | None | After REGISTERED |
| **PDF** | Preview only (optional) | Official export |

**Official Draft** is the **last pre-Document state**. Promotion **instantiates** Document from package; package remains in Workspace archive.

---

## 6. Relationship to Draft Workspace

```text
DraftWorkspace
├── ... editorial work in progress ...
├── Editorial Core mutates DraftBlocks
├── Localization Core mutates locale state
└── when promotion_readiness = true:
        OfficialDraftPackage assembled (snapshot)
        WorkspaceState → OFFICIAL_DRAFT_READY
```

| Rule | Description |
|---|---|
| ODP1 | One active OfficialDraftPackage per Workspace at readiness |
| ODP2 | Reopening editorial work invalidates package; must reassemble |
| ODP3 | Package does not exist until validation passes |
| ODP4 | SubmittedText remains in Workspace; not replaced by package |

---

## 7. Relationship to Document Aggregate

Promotion command consumes OfficialDraftPackage:

| Package field | Document field |
|---|---|
| draft_metadata | DocumentMetadata |
| document_structure | DocumentStructure |
| order_items | OrderItem[] |
| locale_bundle effective + provenance | LocaleRepresentation[] |
| attachment_references | AttachmentReference[] |
| semantic_model_snapshot | OrderItem semantic_payload + obligations |

**Not transferred:** raw submitted text (stays Workspace archive), clarification history (Workspace archive), draft audit full log (summary link only).

---

## 8. Source of Truth at Package

At OFFICIAL_DRAFT_READY (Stage 4 per UDE-002):

| Layer | Authority |
|---|---|
| Semantic model | Management meaning — regeneration source |
| Effective text (per locale block) | Signing preparation wording |
| Generated text | Derived — not authority when override present |
| Submitted text | Historical — not in package as authority |

---

*Diagram: [`diagrams/official-draft-package.svg`](./diagrams/official-draft-package.svg)*
