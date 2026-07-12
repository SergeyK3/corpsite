# UDE-001 — Shared Terminology and Shared Contracts

WP: **UDE-001** — Shared Terminology and Shared Contracts  
Date: **2026-07-12**  
Status: **Architecture Foundation — Complete**  
Prerequisites: UDE-000 (Approved with Minor Findings)  
Mode: **No runtime changes** — contracts only

**Artifacts:**

| Document | Purpose |
|---|---|
| [UDE-001-shared-glossary.md](./UDE-001-shared-glossary.md) | Single term reference (T001–T034 + extensions) |
| [UDE-001-shared-domain-contracts.md](./UDE-001-shared-domain-contracts.md) | Per-entity contract definitions |
| [UDE-001-shared-value-objects.md](./UDE-001-shared-value-objects.md) | Immutable value types |
| [UDE-001-shared-design-rules.md](./UDE-001-shared-design-rules.md) | Mandatory design rules DR-01–DR-20 |
| [UDE-001-extension-points.md](./UDE-001-extension-points.md) | Registry catalog and priority |
| [UDE-001-contract-guidelines.md](./UDE-001-contract-guidelines.md) | Authoring and change rules |
| [`data/`](./data/) | Contract, VO, extension, dependency, readiness matrices |
| [`diagrams/`](./diagrams/) | Domain model, contract map, extension points, dependencies, package structure |

**Evidence base:** OP-RES-001–006A; ADR-UDE-001–016; UDE-000 terminology freeze.

---

## 1. Purpose

UDE-001 begins the **implementation phase** of Unified Document Engine without changing system behavior. It publishes the shared architectural foundation — terminology, domain contracts, value objects, conceptual interfaces, policies, extension points, and dependency rules — that subsequent work packages (UDE-002, UDE-003, OO-IMP-*) will implement against.

UDE-001 is **not** a refactoring stage. Personnel Orders MVP and Operational Orders (research-only) remain untouched at runtime.

---

## 2. Scope

### 2.1 In scope

- Shared domain contracts for 27 conceptual entities
- Shared value objects (21 minimum)
- Architecture-level and implementation-level enumeration separation
- Conceptual interfaces (10) and policies (10)
- Extension points (10 registries)
- Dependency rules and future package structure
- Glossary as single reference
- Contract readiness review
- Handoff specifications for UDE-002 and UDE-003

### 2.2 Out of scope

- Production code (Python, TypeScript, SQL)
- API, UI, database migrations
- Personnel Orders behavior changes
- Operational Orders runtime
- Commit, push, deploy
- Modification of OP-RES research documents

### 2.3 Compatibility statement

**Personnel Orders:** No behavior change. PO test suite and API surface remain unchanged. UDE-001 contracts describe the target shared model that PO MVP already partially implements (Class A components per OP-RES-006 gap analysis).

---

## 3. Design Principles

Carried from OP-RES-006 §5 and ratified ADRs; normative detail in [UDE-001-shared-design-rules.md](./UDE-001-shared-design-rules.md).

| # | Principle | ADR |
|---|---|---|
| 1 | One Document Core, multiple specializations | ADR-UDE-001 |
| 2 | Composition over inheritance | ADR-UDE-002 |
| 3 | Order Item ≠ Execution Obligation | ADR-UDE-003 |
| 4 | Three independent lifecycles; archive orthogonal | ADR-UDE-004 |
| 5 | Generated ≠ Effective ≠ Submitted | ADR-UDE-005, 012 |
| 6 | Hybrid multilingual workflow | ADR-UDE-006 |
| 7 | Role-first Party Reference | ADR-UDE-007 |
| 8 | Execution projection downstream | ADR-UDE-008 |
| 9 | Immutable signed snapshot | ADR-UDE-009 |
| 10 | Incremental migration; PO convergence last | ADR-UDE-010 |
| 11 | Content author ≠ Record creator | ADR-UDE-011 |
| 12 | Submitted-text intake first-class | ADR-UDE-012 |
| 13 | Text provenance per locale block | ADR-UDE-013 |
| 14 | Content confirmation gates READY (OO default) | ADR-UDE-014 |
| 15 | HR as document operator, not default content owner (OO) | ADR-UDE-015 |
| 16 | Staged Source of Truth | ADR-UDE-016 |

---

## 4. Shared Terminology

34 terms frozen in UDE-000 (T001–T034). UDE-001 publishes the implementation glossary with synonyms, undesirable names, and sources.

**Authoritative reference:** [UDE-001-shared-glossary.md](./UDE-001-shared-glossary.md)

**Staged Source of Truth (T028):**

| Phase | Authority |
|---|---|
| Early Intake | Submitted text + provenance (semantic model may be partial) |
| Editorial Draft | Semantic model (enriched) + effective text under reconciliation |
| Ready for Signature | Validated semantic model + reconciled effective locale representations |
| After Signature | Immutable effective bilingual snapshot + signatory metadata |

---

## 5. Shared Domain Contracts

27 conceptual contracts defined. Summary:

| Layer | Contracts |
|---|---|
| Aggregate | Document, DocumentMetadata, DocumentStructure, DocumentSection |
| Items | OrderItem, OrderItemSequence, BusinessIntent |
| Obligations | ExecutionObligation, ControlObligation, ManagedObject, PartyReference, Deadline, ExpectedResult, EvidenceExpectation |
| Text | LocaleRepresentation, GeneratedText, EffectiveText, SubmittedText, TextProvenance |
| Process | ContentConfirmation, AttachmentReference |
| Downstream | ExecutionProjectionDescriptor |
| Cross-cutting | ValidationResult, DocumentAuditEvent |
| Lifecycle | DocumentLifecycleState, LocalizationLifecycleState, ExecutionLifecycleState |

**Detail:** [UDE-001-shared-domain-contracts.md](./UDE-001-shared-domain-contracts.md)  
**Matrix:** [`data/UDE-001-contract-matrix.csv`](./data/UDE-001-contract-matrix.csv)  
**Diagram:** [`diagrams/shared-domain-model.svg`](./diagrams/shared-domain-model.svg)

---

## 6. Shared Value Objects

21 value objects catalogued. All are immutable conceptual types identified by value.

**Shared across specializations:** DocumentId, DocumentNumber, DocumentKind, LocaleCode, LanguageCode, PartyId, RoleReference, DeadlineType, ValidationCode, EvidenceType, LifecycleTransition, ArchiveState, TranslationState, StalenessState, SourceOfTruth, DraftingPath, TextSourceType.

**Shared concept, specialized values:** ItemType, ScenarioId, ScenarioCode, ManagedObjectType.

**Detail:** [UDE-001-shared-value-objects.md](./UDE-001-shared-value-objects.md)  
**Matrix:** [`data/UDE-001-value-object-matrix.csv`](./data/UDE-001-value-object-matrix.csv)

---

## 7. Shared Enumerations

Enumerations split into **architecture-level** (contract vocabulary) and **implementation-level** (runtime enums in later WPs). UDE-001 defines architecture-level sets only.

### 7.1 Architecture-level

| Enumeration | Values (conceptual) | Notes |
|---|---|---|
| DocumentKind | PersonnelOrder, OperationalOrder, +future | Registry-extensible |
| DocumentSpecialization | Policy bundle key per kind | Not a runtime class |
| DraftingPath | SYMMETRIC, RU_FIRST_TRANSLATION, KK_FIRST, SUBMITTED_INTAKE | Maps Models A/B/C |
| LifecycleCategory | DOCUMENT, LOCALIZATION, EXECUTION | Three independent |
| PartyRole | executor, controller, approver, signer, informed, content_author | Distinct from RBAC |
| TextSourceType | SUBMITTED, GENERATED, TRANSLATED, MANUALLY_*, IMPORTED_LEGACY | Provenance |
| ValidationSeverity | ERROR, WARNING, INFO | ERROR blocks READY |
| ObligationType | EXECUTION, CONTROL | Never merged |
| AttachmentKind | SCAN, ROSTER, PLAN, BASIS, SCHEDULE, OTHER | Registry-extensible |
| EvidenceExpectation | REPORT, ACKNOWLEDGMENT, ATTACHMENT, SIGNATURE, CUSTOM | Optional on obligation |
| TransitionReason | user_action, validation_pass, sign, register, void, archive, waiver, system | Audit support |
| ScenarioFamily | Domain grouping (8 OO domains) | OO registry |
| ItemGenerationMode | scenario_driven, intake_enrichment, manual_compose | Orthogonal to DraftingPath |

### 7.2 Implementation-level (deferred)

Production enums for document status, locale state, void_kind, editorial substate — defined in UDE-003, UDE-005, OO-IMP-004. **Not mixed** with architecture-level sets in contract documents.

---

## 8. Shared Interfaces

Conceptual interfaces — responsibility, input, output, guarantees, constraints. No code.

| Interface | Responsibility | Input | Output | Guarantees | Constraints |
|---|---|---|---|---|---|
| **DocumentContract** | Aggregate consistency boundary | DocumentId, mutation commands | Document snapshot, invariants | Atomic item+locale+lifecycle changes; immutable post-sign | No task CRUD; no HR fields in shared mandatory |
| **OrderItemContract** | Item-level semantic and editorial unit | ItemType, semantic_payload, locale edits | OrderItem with obligations and locale state | Item-level regeneration; 0..N obligations | semantic_payload specialized |
| **GenerationContract** | Semantic → generated text | Scenario/inputs, registry version | GeneratedText per locale | Idempotent: same input+version → same output | Ends at export; no execution |
| **LocalizationContract** | Per-locale state and reconciliation | DraftingPath, locale edits, source changes | LocaleRepresentation with lifecycle state | Mandatory locale staleness blocks READY | No machine translation engine |
| **LifecycleContract** | Document state transitions | Transition command, ValidationResult | New DocumentLifecycleState + audit | Append-only audit; archive blocks mutations | No generation internals |
| **ValidationContract** | Multi-layer checks | Document aggregate | ValidationResult | Errors block READY; warnings auditable | No direct persistence mutation |
| **RendererContract** | Prose projection from semantic | Semantic snapshot, LocaleCode, ItemType | GeneratedText | Versioned templates; no semantic mutation | Specialized per item type |
| **ProjectionContract** | Obligation handoff | REGISTERED document | ExecutionProjectionDescriptor[] | Idempotent; compensating on VOIDED | Downstream only; after REGISTERED |
| **AttachmentContract** | Attachment linkage | File ref, AttachmentKind | AttachmentReference | Optional obligation binding | No execution tracking |
| **ScenarioContract** | Blueprint defaults | ScenarioCode, inputs | Item sequence template | Optional path; not required for intake | Specialized registry |

**Readiness:** Document, OrderItem, Localization, Lifecycle, Projection, Attachment — **Ready**. Generation, Validation, Renderer, Scenario — **Deferred** to UDE-003/005/OO-IMP-003.

**Diagram:** [`diagrams/shared-contract-map.svg`](./diagrams/shared-contract-map.svg)

---

## 9. Shared Policies

| Policy | Responsibility | When applied | Implementer | Specialization-specific? |
|---|---|---|---|---|
| **GenerationPolicy** | Idempotency, regeneration scope, control meta-item rules | On generate/regenerate | Shared orchestration + kind hook | Yes — OO control meta-item |
| **LocalizationPolicy** | Mandatory locales, staleness, drafting_path default | On locale edit/translate | Shared + kind registry | Yes — OO submitted_intake default |
| **ValidationPolicy** | Error/warning thresholds, waiver rules | Before READY, on regenerate | Shared framework + kind rules | Yes — basis_policy (PO), BC (OO) |
| **LifecyclePolicy** | Transition guards, void_kind, archive | On lifecycle commands | Shared LifecycleContract | Yes — content confirmation gate (OO) |
| **ProjectionPolicy** | Timing, idempotency, compensating projection | On REGISTERED, VOIDED | Specialization adapter | Yes — PO apply vs OO tasks |
| **AttachmentPolicy** | Required attachments per kind/scenario | On READY validation | Specialization registry | Yes |
| **ArchivePolicy** | Immutability when archived | On archive/restore | Shared | No |
| **AuditPolicy** | Append-only, event taxonomy | All mutations | Shared | Partial — event kinds per kind |
| **ContentConfirmationPolicy** | When author must confirm meaning | After content-class HR edits | OO default; PO optional | **Yes** — interview gate OQ-04 |
| **TranslationPolicy** | RU→KK workflow, review requirements | On translation request | Shared + kind | Yes — OO HR-translator common |

---

## 10. Shared Extension Points

10 registries defined. Specialization connects via plugin registration, not core imports.

| Registry | Required at MVP | First WP |
|---|---|---|
| Localization Registry | Yes | UDE-002 |
| Document Kind Registry | Yes | UDE-003 |
| Lifecycle Registry | Yes | UDE-002 |
| Attachment Registry | Yes | OO-IMP-001 |
| Party Resolution Registry | Yes | UDE-003 |
| Item Type Registry | Yes (OO-IMP-003) | UDE-003 |
| Renderer Registry | OO-IMP-003 | UDE-003 |
| Scenario Registry | P2 | OO-IMP-003 |
| Validation Registry | UDE-005 | UDE-005 |
| Projection Registry | OO-IMP-005 | PO has adapter |

**Detail:** [UDE-001-extension-points.md](./UDE-001-extension-points.md)  
**Diagram:** [`diagrams/extension-point-model.svg`](./diagrams/extension-point-model.svg)

---

## 11. Dependency Rules

Forbidden dependencies (normative):

| From | Must NOT depend on |
|---|---|
| `shared/` | Personnel Orders internals, Operational Orders internals |
| Generation | Task Engine, execution runtime |
| Localization | Execution lifecycle state |
| Execution Projection | Rendering pipeline |
| Renderer | Semantic mutation |
| Validation | Direct DB mutation |
| Document Core | Scenario-specific semantics |
| Draft Intake | Auto READY promotion |

**Matrix:** [`data/UDE-001-dependency-matrix.csv`](./data/UDE-001-dependency-matrix.csv)  
**Diagram:** [`diagrams/dependency-rules.svg`](./diagrams/dependency-rules.svg)

**Allowed:** Specialization modules → shared contracts (upward adapter). Shared → organization context (read-only for party resolution).

---

## 12. Package Structure

Future logical layout (no files created):

```text
shared/
├── document/          # core, metadata, structure
├── editorial/         # generated, effective, override
├── localization/      # locale, provenance, staleness
├── generation/        # orchestration (not templates)
├── lifecycle/         # transitions, archive
├── validation/        # framework
├── projection/        # descriptor contract
├── attachment/
├── audit/
├── party/
├── contracts/         # conceptual interfaces
├── value-objects/
└── registries/

specializations/
├── personnel/         # PO item registry, apply adapter
└── operational/       # OO intake, scenario, control
```

**Diagram:** [`diagrams/shared-package-structure.svg`](./diagrams/shared-package-structure.svg)

---

## 13. Design Guidelines

Authoring rules for all contract work: [UDE-001-contract-guidelines.md](./UDE-001-contract-guidelines.md)

Mandatory development rules: [UDE-001-shared-design-rules.md](./UDE-001-shared-design-rules.md) (DR-01–DR-20)

Key contract rules:

- Contracts are conceptually immutable; change via ADR only
- No runtime states, SQL, API, or UI in shared contracts
- No HR-specific or OO-specific fields in shared mandatory properties
- Independence checklist before adding to `shared/`

---

## 14. Readiness Review

| Category | Ready | Needs clarification | Deferred |
|---|---|---|---|
| Domain contracts | 26 | 1 (ContentConfirmation) | 0 |
| Interfaces | 6 | 0 | 4 |
| Policies | 8 | 1 (ContentConfirmationPolicy) | 1 (GenerationPolicy detail) |
| Extension points | 7 | 0 | 3 |
| Glossary T001–T034 | 34 | 0 | 0 |

**Needs clarification:**

- **ContentConfirmation / ContentConfirmationPolicy** — mandatory policy per change class requires organizational interview (OQ-04). Contract shape is ready; policy thresholds deferred to UDE-002.

**Deferred (not rejected):**

- GenerationContract, ValidationContract, RendererContract, ScenarioContract — require editorial core (UDE-003) or validation catalog (UDE-005) before implementation binding.

**Matrix:** [`data/UDE-001-readiness-matrix.csv`](./data/UDE-001-readiness-matrix.csv)

---

## 15. Handoff to UDE-002

**UDE-002 — Draft Intake and Text Provenance Architecture**

### Contracts consumed

| Contract | UDE-002 use |
|---|---|
| SubmittedText | Intake capture; never auto-effective |
| TextProvenance | Per-block source_type, actor, unit, derived_from |
| LocaleRepresentation | Host submitted and provenance state |
| DocumentMetadata | content_author, submitting_unit, record creator separation |
| PartyReference | Content Author declaration |
| AttachmentReference | Draft attachments at intake |
| ContentConfirmation | Shape only; policy in UDE-002 |
| Draft Intake (T018) | Intake contour boundaries |
| Editorial Substate (T034) | intake_review derived condition |

### Value objects consumed

DraftingPath (SUBMITTED_INTAKE), TextSourceType (SUBMITTED), SourceOfTruth (INTAKE phase), LocaleCode, RoleReference.

### Policies consumed

LocalizationPolicy (intake defaults), AttachmentPolicy, ContentConfirmationPolicy (draft), LifecyclePolicy (no auto-READY).

### Extension points consumed

Localization Registry, Lifecycle Registry (intake guards), Attachment Registry.

### UDE-002 must NOT

- Implement runtime intake UI
- Promote submitted to effective automatically
- Equate created_by with content_author

---

## 16. Handoff to UDE-003

**UDE-003 — Shared Editorial and Localization Core**

### Contracts consumed

| Contract | UDE-003 use |
|---|---|
| Document, DocumentStructure, DocumentSection | Editorial shell |
| OrderItem, OrderItemSequence | Item-level editing |
| LocaleRepresentation | Per-block editorial state |
| GeneratedText, EffectiveText | override ?? generated |
| TextProvenance | Full provenance model |
| LocalizationLifecycleState | CURRENT, STALE, REVIEW_REQUIRED |
| DocumentLifecycleState | Editorial write locks by status |
| DocumentAuditEvent | Append-only editorial events |
| ValidationResult | Pre-READY checks (shape) |

### Value objects consumed

LocaleCode, LanguageCode, DraftingPath, StalenessState, TranslationState, ArchiveState, LifecycleTransition.

### Interfaces consumed

DocumentContract, OrderItemContract, LocalizationContract, LifecycleContract, AttachmentContract.

### Policies consumed

LocalizationPolicy, TranslationPolicy, ArchivePolicy, AuditPolicy, LifecyclePolicy.

### Extension points consumed

Document Kind Registry, Party Resolution Registry, Item Type Registry (binding), Renderer Registry (orchestration contract only).

---

## 17. Conclusions

UDE-001 completes the architectural foundation for Unified Document Engine implementation. The project now has:

- A **single glossary** as term reference
- **27 shared domain contracts** independent of PO and OO implementations
- **21 value objects** with shared vs specialized value distinction
- **10 conceptual interfaces** and **10 policies**
- **10 extension points** with implementation priority order
- **Explicit dependency rules** preventing core contamination
- **Readiness assessment** with one clarification item (content confirmation policy)
- **Handoff packages** for UDE-002 (intake/provenance) and UDE-003 (editorial/localization)

No runtime, API, database, or existing PO/OO code was modified.

**Next authorized WP:** UDE-002 — Draft Intake and Text Provenance Architecture.

---

## Mandatory Answers

### 1. Какие контракты являются truly shared?

**Fully shared (no mandatory HR/OO semantics):** Document, DocumentMetadata, DocumentStructure, DocumentSection, OrderItem (shell), OrderItemSequence, PartyReference, Deadline, AttachmentReference, LocaleRepresentation, GeneratedText, EffectiveText, SubmittedText, TextProvenance, ValidationResult, DocumentAuditEvent, DocumentLifecycleState, LocalizationLifecycleState, ExecutionLifecycleState (reference), ExecutionProjectionDescriptor (shape).

### 2. Какие контракты должны оставаться specialization-specific?

**Specialized payload or primary use:** BusinessIntent values, ManagedObject taxonomy, ExpectedResult, EvidenceExpectation (OO-rich), ControlObligation (OO-primary), ContentConfirmation policy defaults (OO), semantic_payload in OrderItem, Scenario registry values, ItemType registry values, Projection adapters (PO apply, OO tasks), GenerationPolicy hooks (control meta-item).

### 3. Какие Value Objects являются общими?

DocumentId, DocumentNumber, DocumentKind, LocaleCode, LanguageCode, PartyId, RoleReference, DeadlineType, ValidationCode, EvidenceType, LifecycleTransition, ArchiveState, TranslationState, StalenessState, SourceOfTruth, DraftingPath, TextSourceType — plus shared **concept** for ItemType, ScenarioCode, ManagedObjectType with specialization-specific registry values.

### 4. Какие зависимости запрещены?

shared → PO/OO internals; Generation → Task Engine; Localization → Execution; Execution Projection → Rendering; Renderer → semantic mutation; Validation → DB mutation; Draft Intake → auto READY. Full matrix in `UDE-001-dependency-matrix.csv`.

### 5. Какие registries действительно нужны?

**MVP-required:** Localization, Document Kind, Lifecycle, Attachment, Party Resolution, Item Type, Projection (PO exists). **P2/deferred:** Scenario, Renderer (orchestration in UDE-003, templates in OO-IMP-003), Validation (UDE-005).

### 6. Какие extension points будут использоваться первыми?

1. Localization Registry (UDE-002)  
2. Lifecycle Registry (UDE-002)  
3. Document Kind Registry (UDE-003)  
4. Attachment Registry (OO-IMP-001)  
5. Party Resolution Registry (UDE-003)

### 7. Какие правила являются обязательными?

DR-01 through DR-20 in [UDE-001-shared-design-rules.md](./UDE-001-shared-design-rules.md), especially: Composition over inheritance, Generated ≠ Effective ≠ Submitted, Document ≠ Execution, Localization independent, Archive orthogonal, Role-first, Submitted-text supported, Manual override preserved, Projection downstream, Append-only audit.

### 8. Какие контракты готовы к реализации?

26 of 27 domain contracts Ready. 6 of 10 interfaces Ready. ContentConfirmation Needs clarification (policy only). Generation, Validation, Renderer, Scenario interfaces Deferred to later WPs.

### 9. Что потребуется UDE-002?

SubmittedText, TextProvenance, LocaleRepresentation, DocumentMetadata authorship fields, PartyReference for Content Author, AttachmentReference, DraftingPath/SUBMITTED_INTAKE, SourceOfTruth INTAKE phase, Localization and Lifecycle registries, ContentConfirmation shape, prohibition of auto-effective promotion.

### 10. Что потребуется UDE-003?

Document aggregate shell, OrderItem editorial model, GeneratedText/EffectiveText/override chain, full LocaleRepresentation with LocalizationLifecycleState, DocumentLifecycleState write locks, DocumentAuditEvent, LocalizationContract, LifecycleContract, Document Kind and Party Resolution registries, TranslationPolicy, ArchivePolicy.

---

*UDE-001 completed 2026-07-12. Architecture foundation ready for UDE-002.*
