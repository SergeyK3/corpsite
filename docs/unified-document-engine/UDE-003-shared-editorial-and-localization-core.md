# UDE-003 — Shared Editorial and Localization Core

WP: **UDE-003** — Shared Editorial and Localization Core  
Date: **2026-07-12**  
Status: **Architecture Foundation — Complete**  
Prerequisites: UDE-000 ✓ · UDE-001 ✓ · UDE-002 ✓  
Mode: **No runtime changes** — architecture only

**Artifacts:**

| Document | Purpose |
|---|---|
| [UDE-003-official-draft-package.md](./UDE-003-official-draft-package.md) | Official Draft Package classification |
| [UDE-003-editorial-model.md](./UDE-003-editorial-model.md) | Text layers and editorial reality |
| [UDE-003-generated-effective-model.md](./UDE-003-generated-effective-model.md) | Regeneration and fingerprint |
| [UDE-003-localization-core.md](./UDE-003-localization-core.md) | Locale representation and BC |
| [UDE-003-promotion-boundary.md](./UDE-003-promotion-boundary.md) | Workspace → Document transfer |
| [UDE-003-editorial-validation.md](./UDE-003-editorial-validation.md) | E-series promotion gates |
| [`data/`](./data/) | Contract, section, localization, staleness, readiness matrices |
| [`diagrams/`](./diagrams/) | Eight architecture diagrams |

---

## 1. Purpose

UDE-003 answers:

> **How does Draft Workspace become an Official Draft Package ready for Document Aggregate creation — independent of document specialization?**

It defines **Shared Editorial & Localization Core** — the common editorial engine that:

- Operates inside Draft Workspace until promotion
- Continues on Document Aggregate in DRAFT (post-promotion)
- Produces **OfficialDraftPackage** as promotion handoff artifact
- Serves Personnel Orders, Operational Orders, and future document families through shared contracts and registries

---

## 2. Scope

### 2.1 In scope

- Editorial Core domain boundaries
- Official Draft Package architecture
- Editorial model (six text layers)
- Locale Representation refinement
- Generated ↔ Effective lifecycle
- Manual override and regeneration rules
- Universal editorial sections + Section Registry
- Localization Core (locale lifecycle, BC, staleness)
- Editorial validation (E-series)
- Promotion boundary
- Editorial Audit (three-audit model)
- UDE-001/002 contract mapping
- UDE-004 handoff
- PO extraction candidates (analysis only)

### 2.2 Out of scope

- Code, ORM, SQL, API, UI
- Lifecycle orchestration (UDE-004)
- PDF rendering, execution projection
- Draft Intake (UDE-002)
- Runtime changes to PO or OO

### 2.3 Compatibility

No runtime impact. PO MVP continues unchanged. Architecture describes target shared core that PO partially implements (PO-EDIT-001/002).

---

## 3. Editorial Core Domain

### 3.1 Responsibility

| In scope | Detail |
|---|---|
| Editorial structure | Document shell, section ordering |
| Generated text | Semantic → prose snapshots |
| Effective text | override ?? generated |
| Manual editing | Override layer with provenance |
| Regeneration | Item/section scope, fingerprint |
| Section ordering | Registry-driven sequence |
| Locale synchronization | Coordinate with Localization Core |
| Bilingual consistency | BC check orchestration |
| Official Draft Package | Assemble promotion snapshot |

### 3.2 Explicitly NOT responsible

| Out of scope | Contour |
|---|---|
| Draft Intake | UDE-002 |
| Document lifecycle | UDE-004 |
| Registration, signing | Lifecycle |
| Execution, projection | Downstream |
| PDF, DOCX rendering | Renderer/Exporter |
| Machine translation | External |

### 3.3 Boundaries

```text
Draft Workspace
  └── Editorial Core + Localization Core
        └── Validation (E* + BC*)
              └── OfficialDraftPackage
                    └── Promotion (UDE-004) → Document Aggregate
```

Editorial Core is a **shared logical component** (orchestration + contracts), **not** an aggregate root. It mutates DraftWorkspace during pre-promotion; mutates Document in DRAFT post-promotion.

Diagram: [`diagrams/editorial-core-overview.svg`](./diagrams/editorial-core-overview.svg)

---

## 4. Official Draft Package

### 4.1 Classification

| Question | Answer |
|---|---|
| Aggregate? | **No** |
| DTO? | Partially — rich domain snapshot |
| Editorial snapshot? | **Yes** |
| Bounded context? | **No** — artifact within Workspace |

**Official Draft Package** = validated, frozen **promotion handoff snapshot** assembled when `promotion_readiness = true`.

### 4.2 Contents

Document structure, locale bundle (effective + generated + provenance), semantic model snapshot, attachments, validation clearance, editorial metadata, promotion readiness flag.

### 4.3 vs Document

| Official Draft | Document |
|---|---|
| No DocumentId | DocumentId at promotion |
| Workspace stage | Lifecycle entity |
| Editorial Audit culmination | Lifecycle Audit begins |
| Preview-capable | Legal act |

Detail: [UDE-003-official-draft-package.md](./UDE-003-official-draft-package.md)

---

## 5. Editorial Model

Six text layers with distinct roles:

| Layer | Editorial reality | History | Promoted |
|---|---|---|---|
| Submitted | No | Yes | Provenance ref only |
| Generated | Derived | Regenerable | Yes |
| Manual | Yes (override) | Audited | Via effective chain |
| Translated | Process | Provenance | Yes |
| Effective | **Primary** | Current pre-sign | **Yes** |
| Official | **Frozen effective** | At readiness | **Yes** |

```text
effective_text = override_text ?? generated_text
```

Detail: [UDE-003-editorial-model.md](./UDE-003-editorial-model.md)

---

## 6. Locale Representation

### 6.1 Structure

```text
LocaleBundle (per LocaleCode)
├── localization_lifecycle_state
├── translation_state
├── drafting_path / source_language
└── editorial_blocks[] (per section/item)
      ├── generated_text, override_text, effective_text
      ├── text_provenance, staleness_state
      └── editorial_completeness
```

### 6.2 Rules

- Semantic model is language-independent
- Each text-bearing section/item has one block per active locale
- Mandatory locales (default ru + kk) must be CURRENT for promotion
- Document-level locale aggregate derived from mandatory blocks

Detail: [UDE-003-localization-core.md](./UDE-003-localization-core.md)

---

## 7. Generated vs Effective Model

```text
Semantic → Generated → Manual Override → Effective → Official → Signed
```

| Event | Generated | Effective | Staleness |
|---|---|---|---|
| Regenerate, no override | Replaced | = new generated | CURRENT |
| Regenerate, override kept | Replaced | = override (unchanged) | REVIEW_REQUIRED |
| Semantic change + override | Unchanged until regen | = override | STALE |
| Clear override | Current | = generated | CURRENT |

Fingerprint: `SHA-256(canonical semantic inputs + generator_version)` per block (PO-EDIT-002 aligned).

Detail: [UDE-003-generated-effective-model.md](./UDE-003-generated-effective-model.md)  
Diagram: [`diagrams/generated-to-effective-flow.svg`](./diagrams/generated-to-effective-flow.svg)

---

## 8. Manual Override

### 8.1 Granularity (default: block-level)

| Level | Support | Notes |
|---|---|---|
| **Block** (section/item × locale) | **Default** | PO-EDIT-002 model |
| Section | Yes | Title, preamble |
| Item | Yes | body, basis |
| Locale | Implicit | Per-block per locale |
| Document | No | Use block collection |

### 8.2 Preservation rules

| Rule | Behavior |
|---|---|
| MO1 | Override preserved on regenerate (not deleted) |
| MO2 | Override marks STALE/REVIEW_REQUIRED when fingerprint diverges |
| MO3 | Clear override requires explicit confirmed command |
| MO4 | Override recorded in provenance as MANUALLY_EDITED |
| MO5 | Submitted text never overwritten by override |

---

## 9. Regeneration Rules

### 9.1 Triggers

| Trigger | Scope | Auto-rebuild |
|---|---|---|
| Semantic changed | Affected item/section blocks | Generated yes; effective if no override |
| Scenario/registry version changed | Registered scope | Generated |
| Item added | New item blocks | Generate new |
| Item removed | Removed blocks archived | N/A |
| Party/deadline changed | Item fingerprint | Item-level |
| Translation source (RU) updated | KK derived blocks | STALE + BC023 |

### 9.2 Confirmation required

| Action | Confirmation |
|---|---|
| Regenerate with override → REVIEW_REQUIRED | Operator review |
| Clear override | Explicit user command |
| Content-class effective change (OO) | Content confirmation (E113) |

### 9.3 Default scope

**Item block** regeneration default; document-level optional explicit command.

---

## 10. Editorial Sections

Universal section types (16):

| Section | Mandatory default | PO | OO |
|---|---|---|---|
| HEADER | Yes | ✓ | ✓ |
| TITLE | Yes | ✓ | ✓ |
| PREAMBLE | Yes | ✓ | ✓ |
| BASIS | Conditional | item basis | preamble refs |
| OPERATIVE_FORMULA | Yes | ✓ | ✓ |
| BODY | Optional | closing | rare |
| ORDER_ITEMS | Yes | ✓ | ✓ |
| ITEM_BODY | Yes | ✓ | ✓ |
| ITEM_BASIS | Conditional | basis_required | scenario |
| CONTROL_BLOCK | OO default | — | ✓ |
| EFFECTIVE_CLAUSE | Optional | derived | derived |
| ATTACHMENTS | Conditional | scans | rosters |
| SIGNATURE | Yes | ✓ | ✓ |
| AGREEMENT | Optional | rare | episodic |
| ACKNOWLEDGEMENT | Optional | rare | common |
| FOOTER | Optional | ✓ | ✓ |

Matrix: [`data/UDE-003-section-registry.csv`](./data/UDE-003-section-registry.csv)

---

## 11. Section Registry

Conceptual extension point:

```text
Section Type → Renderer binding → Validation rules → Ordering weight → Localization policy
```

- **Owner:** Shared platform + per-DocumentKind plugins
- **Specialization:** ITEM_BODY renderer per ItemType; CONTROL_BLOCK OO policy
- **No implementation** in UDE-003

Diagram: [`diagrams/section-registry.svg`](./diagrams/section-registry.svg)

---

## 12. Localization Core

Responsible for: locale lifecycle, translation state, BC checks, locale completeness, staleness propagation.

**Not responsible for:** machine translation, task execution, lifecycle, PDF.

Operates via LocaleBundle on Workspace and Document. Invoked by Editorial Core on locale mutations.

Diagram: [`diagrams/localization-core.svg`](./diagrams/localization-core.svg)  
Matrix: [`data/UDE-003-localization-matrix.csv`](./data/UDE-003-localization-matrix.csv)

---

## 13. Bilingual Consistency

| Check | Severity | Blocks promotion |
|---|---|---|
| BC001 section/item count match | error | Yes |
| BC002 numbering sequence | error | Yes |
| BC007 date values | error | Yes |
| BC010 party role parity | error | Yes |
| BC013–BC016 semantic parity (assisted) | error | Yes |
| BC019 clause completeness | error | Yes |
| BC020 no placeholders | error | Yes |
| BC023 ru_change_after_kk | error | Yes |
| BC006 block order | warning | No |
| BC022 calque detection | warning | No |
| BC024 structural drift | warning | → REVIEW_REQUIRED |

---

## 14. Staleness

| State | Meaning | Cleared by |
|---|---|---|
| **CURRENT** | Aligned with fingerprint | — |
| **STALE** | Override + fingerprint mismatch | Regenerate, edit, or clear |
| **REVIEW_REQUIRED** | Post-regen override kept; structural drift | Human review |
| **UNKNOWN** | Legacy import | Editorial normalize |

### Propagation

- RU effective change → KK TRANSLATED: STALE (BC023)
- Semantic item change → all locales for item: fingerprint mismatch
- Mandatory locale STALE/REVIEW_REQUIRED → blocks promotion (E103, E104)

Matrix: [`data/UDE-003-staleness-matrix.csv`](./data/UDE-003-staleness-matrix.csv)

---

## 15. Editorial Validation

E-series (15 checks) + BC P0 subset. Layers: structure, editorial, ordering, locale, generated/effective, override, mandatory sections, promotion readiness.

**Does not use Document lifecycle.** Gates OfficialDraftPackage assembly only.

| Blockers | IDs |
|---|---|
| Missing effective on required blocks | E102 |
| Mandatory locale not CURRENT | E103 |
| REVIEW_REQUIRED uncleared | E104 |
| GENERATION_FAILED | E105 |
| Semantic incomplete | E112 |
| Content confirmation pending | E113 |
| BC P0 errors | BC001–BC023 subset |

Detail: [UDE-003-editorial-validation.md](./UDE-003-editorial-validation.md)  
Diagram: [`diagrams/editorial-validation-flow.svg`](./diagrams/editorial-validation-flow.svg)

---

## 16. Promotion Boundary

### Document receives

Structure, OrderItems + semantic, LocaleRepresentation[] (effective + generated + provenance), AttachmentReference[], DocumentMetadata, ValidationResult, ContentConfirmation.

### Stays in Workspace

SubmittedText raw, clarifications, full Draft Audit, intake validation history.

### Created at promotion

DocumentId, DocumentLifecycleState=DRAFT, Lifecycle Audit.

Detail: [UDE-003-promotion-boundary.md](./UDE-003-promotion-boundary.md)  
Diagram: [`diagrams/promotion-boundary.svg`](./diagrams/promotion-boundary.svg)

---

## 17. Editorial Audit

Three append-only streams:

| Audit | Scope | Starts |
|---|---|---|
| **Draft Audit** | Intake, clarifications | DRAFT_SUBMITTED |
| **Editorial Audit** | Edits, regen, translation, confirmation, package assembly | EDITORIAL_STARTED |
| **Lifecycle Audit** | READY, SIGNED, VOIDED | DOCUMENT_PROMOTED |

Editorial events: `EDITORIAL_EDIT`, `REGENERATED`, `OVERRIDE_SAVED`, `OVERRIDE_CLEARED`, `TRANSLATION_ADDED`, `LOCALIZATION_REVIEWED`, `CONTENT_CONFIRMED`, `OFFICIAL_PACKAGE_ASSEMBLED`.

Diagram: [`diagrams/editorial-audit-model.svg`](./diagrams/editorial-audit-model.svg)

---

## 18. Shared Contract Mapping

### UDE-002 → UDE-003

| UDE-002 | UDE-003 consumption |
|---|---|
| DraftBlock.workspace_effective | Feeds generation/enrichment → effective |
| SemanticEnrichmentState | semantic_model_snapshot in package |
| LocalizationState | LocaleBundle.localization_lifecycle_state |
| TextProvenance | Carried into editorial blocks |
| OFFICIAL_DRAFT_READY | Triggers package assembly |

### UDE-001 → UDE-003

| Contract | Role in UDE-003 |
|---|---|
| LocaleRepresentation | Target shape for editorial blocks |
| GeneratedText, EffectiveText | Core editorial layers |
| TextProvenance | Per-block in LocaleBundle |
| DocumentStructure, DocumentSection | Shell from sections registry |
| OrderItem | Item blocks + semantic |
| ValidationResult | E* + BC output |
| LocalizationContract | Localization Core interface |
| OrderItemContract | Item regeneration scope |

---

## 19. Compatibility

| Dependency | Allowed? |
|---|---|
| Personnel Orders internals | **No** — adapter at specialization registry only |
| Operational Orders internals | **No** — adapter only |
| Task Engine | **Forbidden** |
| HR employee_events | **Forbidden** |
| Draft Intake | **Upstream** — Editorial starts after intake |
| Lifecycle | **Downstream** — UDE-004 orchestrates post-promotion |

Editorial Core uses **composition + Section Registry + ItemType Registry** — same pattern as UDE-001 ADR-UDE-002.

---

## 20. Readiness Review

| Component | Status |
|---|---|
| Editorial Core Domain | **Ready** |
| Localization Core | **Ready** |
| Official Draft Package | **Ready** |
| Editorial Model | **Ready** |
| Locale Representation | **Ready** |
| Generated/Effective | **Ready** |
| Manual Override | **Ready** |
| Regeneration | **Ready** |
| Section Registry | **Ready** |
| Staleness | **Ready** |
| Editorial Validation | **Ready** |
| Promotion Boundary | **Ready** |
| Editorial Audit | **Ready** |
| ContentConfirmationPolicy | **Needs clarification** (OQ-04) |
| Lifecycle READY orchestration | **Deferred** (UDE-004) |
| Renderer impl | **Deferred** (OO-IMP-003) |
| PDF | **Rejected** |

Matrix: [`data/UDE-003-readiness.csv`](./data/UDE-003-readiness.csv)

---

## 21. Handoff to UDE-004

**UDE-004 — Promotion, Lifecycle and Validation Orchestration** receives:

| From Editorial Core | UDE-004 use |
|---|---|
| OfficialDraftPackage | Promotion command input |
| promotion_readiness + ValidationResult | Execute DOCUMENT_PROMOTED |
| Editorial validation clearance | Seed Document validation state |
| LocaleBundle effective texts | Initialize Document LocaleRepresentation |
| WriteLockPolicy (DRAFT-only) | Lifecycle guard integration |
| BC clearance | Reuse for READY_FOR_SIGNATURE gate |

UDE-004 orchestrates:

- Promotion execution (Workspace → Document)
- DocumentLifecycleState transitions
- Lifecycle Audit initiation
- READY gate (reuses E* + BC)
- Return-to-DRAFT compatibility (PO-EDIT R2)

UDE-003 does **not** define lifecycle state machine — only editorial prerequisites.

---

## 22. Personnel Orders Extraction Candidates

Architectural analysis only — **no code changes**. PO-EDIT-001/002 already implement ~70% of shared editorial semantics for PO.

| PO component | Shared core candidate | Notes |
|---|---|---|
| `effective = override ?? generated` | **Class A — extract** | Core editorial invariant |
| Block-level editorial (title, preamble, item body/basis) | **Class A** | Maps to EditorialBlock |
| `review_status` CURRENT/STALE/REVIEW_REQUIRED | **Class A** | = StalenessState |
| Fingerprint + `source_fingerprint` | **Class A** | Regeneration contract |
| Regenerate preserving override | **Class A** | R9 semantics |
| `ready_gate` editorial validation | **Class A** | → E-series generalization |
| `write_lock` DRAFT-only | **Class A** | Shared WriteLockPolicy |
| Generation orchestration (`generation_service`) | **Class B** | Shell shared; HR generators stay PO |
| `mapper` effective_text serialization | **Class B** | Contract shared; PO fields adapter |
| `audit` editorial events (no prose) | **Class B** | Merge into Editorial Audit taxonomy |
| `basis_policy` per item type | **Class C — stay PO** | HR-specific |
| HR `generators.py` templates | **Class C — stay PO** | Item Type Registry PO entries |
| `fallback` localized_texts | **Class C — deprecate** | Migration adapter UDE-006 |
| Print ViewModel / PDF | **Class C — stay PO** | Renderer downstream |

**Extraction sequence (UDE-006):** Class A contracts first → PO adapter wraps existing tables → OO uses same core from start.

---

## 23. Conclusions

UDE-003 defines Shared Editorial & Localization Core:

1. **Editorial Core** — structure, generated/effective, override, regeneration, sections
2. **Localization Core** — locale lifecycle, BC, staleness propagation
3. **OfficialDraftPackage** — editorial snapshot (not aggregate) at promotion readiness
4. **Six text layers** with clear reality vs history distinction
5. **Block-level override** with fingerprint staleness (PO-proven)
6. **Section Registry** — 16 universal blocks with specialization hooks
7. **E-series validation** — promotion gates without lifecycle
8. **Three audit streams** — Draft, Editorial, Lifecycle
9. **Independence** from PO, OO, Task Engine
10. **UDE-004 handoff** — promotion and lifecycle orchestration

No runtime changes. Foundation ready for UDE-004 and OO editorial implementation.

**Next authorized WP:** UDE-004 — Promotion, Lifecycle and Validation Orchestration.

---

## Mandatory Answers

### 1. Что такое Official Draft Package?

Валидированный **editorial snapshot** — составной пакет структуры, locale bundle, semantic snapshot, attachments и validation clearance, замороженный при OFFICIAL_DRAFT_READY. Handoff artifact для promotion.

### 2. Является ли он Aggregate?

**Нет.** Артефакт внутри DraftWorkspace aggregate. Нет DocumentId, нет lifecycle.

### 3. Чем отличается Official Draft от Document?

Official Draft — предофициальный пакет в Workspace. Document — legal act с DocumentId и lifecycle. Promotion инстанцирует Document из пакета.

### 4. Как устроена Locale Representation?

LocaleBundle per LocaleCode → editorial_blocks[] per section/item с generated, override, effective, provenance, staleness. Semantic language-independent.

### 5. Как взаимодействуют Generated и Effective?

`effective = override ?? generated`. Generated пересоздаётся при regen. Override сохраняется → REVIEW_REQUIRED при fingerprint mismatch.

### 6. Как работает Manual Override?

Block-level (section/item × locale). Сохраняется при regen. STALE при semantic change. Очистка — явная команда. Provenance MANUALLY_EDITED.

### 7. Как работает Regeneration?

Item-block scope default. Новый generated из semantic + registry version. Без override → effective = generated. С override → effective неизменен, REVIEW_REQUIRED.

### 8. Как распространяется Staleness?

Semantic change → item blocks STALE. RU effective change → KK TRANSLATED STALE (BC023). Mandatory locale STALE → blocks promotion E103.

### 9. Какие проверки выполняет Editorial Validation?

E101–E115 (structure, editorial, ordering, locale, override, promotion) + BC P0 (BC001, BC002, BC007, BC010, BC013–016, BC019, BC020, BC023).

### 10. Что блокирует Promotion?

E102–E105, E112–E115, E103–E104, BC P0 errors, pending content confirmation (E113), open clarifications.

### 11. Что получает Document Aggregate?

Metadata, Structure, OrderItems + semantic, LocaleRepresentation[], Attachments, ValidationResult, ContentConfirmation; новые DocumentId + DRAFT + Lifecycle Audit.

### 12. Что остаётся в Draft Workspace?

SubmittedText raw, clarifications, full Draft Audit, Workspace frozen with package archive.

### 13. Как устроен Editorial Audit?

Три потока: Draft (intake), Editorial (edits/regen/translation/confirmation/package), Lifecycle (post-promotion). Append-only, не смешиваются.

### 14. Какие компоненты готовы к реализации?

Editorial Core, Localization Core, Official Draft Package, editorial model, locale representation, override/regen/staleness, section registry, E-validation, promotion boundary, editorial audit — **Ready**.

### 15. Какие элементы PO потенциально извлекаются?

**Class A:** effective semantics, block model, review_status/staleness, fingerprint, regen-with-override, ready_gate, write_lock. **Class B:** generation orchestration shell, mapper, audit taxonomy. **Class C (stay PO):** HR generators, basis_policy, PDF/ViewModel.

---

*UDE-003 completed 2026-07-12. No runtime changes.*
