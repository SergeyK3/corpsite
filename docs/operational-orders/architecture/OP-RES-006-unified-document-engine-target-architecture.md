# OP-RES-006 — Unified Document Engine Target Architecture

WP: **OP-RES-006** — Unified Document Engine Target Architecture  
Date: **2026-07-12**  
Status: **Architecture research and specification** (no runtime changes)  
Mode: Evidence-based target architecture for ratification

**Supporting artifacts:**

- [Executive Summary](./OP-RES-006-architecture-executive-summary.md)
- [Personnel Orders Gap Analysis](./OP-RES-006-personnel-orders-gap-analysis.md)
- [Migration Roadmap](./OP-RES-006-migration-roadmap.md)
- [ADR Backlog](./OP-RES-006-adr-backlog.md)
- [**OP-RES-006A Addendum**](./OP-RES-006A-initiation-authorship-and-draft-intake-addendum.md) *(initiation, authorship, draft intake — OP-RES-006A findings)*
- [`data/`](./data/) · [`diagrams/`](./diagrams/)

> **OP-RES-006A update (2026-07-12):** Sections marked with *(006A)* reflect addendum findings on content ownership, draft intake, and three drafting paths. Ratify together with OP-RES-006A before UDE-000.

---

## 1. Executive Summary

OP-RES-006 формирует целевую архитектуру **Unified Document Engine (UDE)** на основе исследовательской программы OP-RES-001–005A и read-only анализа production Personnel Orders MVP.

**Главный вывод подтверждён:** Personnel Orders и Operational Orders — **специализации одного механизма документов**, а не параллельные модули.

UDE объединяет:

- общий **document shell** (Header → Preamble → Operative Formula → Items → Attachments → Signature → Agreement → Acknowledgement);
- общую **editorial model** (semantic → generated → effective, manual override);
- **три независимых lifecycle** (document, localization, execution);
- **специализации** через composition + policy/registry;
- **execution projection** как downstream boundary, не часть generation.

Personnel Orders MVP уже реализует ~16 компонентов Class A (foundation). Operational Orders можно добавить **без полного рефакторинга PO** (Phase 4 migration).

---

## 2. Background

### 2.1 Completed research program

| WP | Title | Status |
|---|---|---|
| OP-RES-001 | Corpus inventory | Done |
| OP-RES-002 | Structural patterns | Done |
| OP-RES-003 | Taxonomy | Done |
| OP-RES-004 | Control & execution | Done |
| OP-RES-005 | Generation model | Done |
| OP-RES-005A | Bilingual workflow | Done |
| OP-RES-006 | Target architecture | Done |
| OP-RES-006A | Initiation, authorship, draft intake | Done *(006A)* |

### 2.2 Production context

Personnel Orders — working MVP with lifecycle, bilingual editorial, generation, PDF, audit, archive. Operational Orders — research only, no runtime.

### 2.3 Architectural question

Как сохранить PO MVP, добавить OO без копирования, переиспользовать shell, поддержать разные семантики Order Items, разделить generation/lifecycle/execution, поддержать RU/KK hybrid workflow, и мигрировать инкрементально?

**Ответ:** staged extraction к UDE с parallel OO specialization (см. §35).

---

## 3. Research Evidence

| Source | Key finding |
|---|---|
| OP-RES-001 | 193 files; 183 DOCX; thematic fragmentation |
| OP-RES-002 | Unified shell ~97%; PO-EDIT-001 alignment |
| OP-RES-003 | 8 domains, 21 scenarios; P0 ~59% |
| OP-RES-004 | Order Item → Execution Obligation; Control separate; 92% control |
| OP-RES-005 | Scenario-first; 14 item types; generation ends at export |
| OP-RES-005A | 135 bilingual single-DOCX; RU-first probable; 0 cross-file pairs |
| Personnel Orders | Editorial blocks, lifecycle audit, archive — production proof |

---

## 4. Architectural Drivers

1. **Corpus-proven unified shell** — structural identity PO/OO  
2. **Semantic divergence** — HR events vs operational obligations  
3. **Production PO must not break** — compatibility guarantee  
4. **Bilingual legal requirement** — hybrid symmetric + asymmetric workflow  
5. **Execution is downstream** — task engine exists separately  
6. **Incremental delivery** — P0 scenarios first (~59%)  
7. **No premature ECM/BPM** — bounded scope  

---

## 5. Architectural Principles

| # | Principle | Evidence | Consequence | Violation risk |
|---|---|---|---|---|
| 1 | **One Document Core, Multiple Specializations** | OP-RES-002; PO shell | Shared lifecycle, editorial, structure; kind-specific registries | Duplicate modules; divergent lifecycle |
| 2 | **Semantic Model before Effective Text** | OP-RES-005; PO fingerprint | Generation from structured data; text is projection | Unreproducible documents; stale drift |
| 3 | **Order Item as Generation Unit** | OP-RES-004/005 | Item-level regenerate; clause templates per item type | Document-level-only editing |
| 4 | **Obligation as Semantic Unit** | OP-RES-004 | Management meaning in obligations, not prose | Tasks tied to free text |
| 5 | **Control is not Execution** | OP-RES-004 (92%; 95% role separation) | Control Obligation separate entity | Controller field on executor |
| 6 | **Document Lifecycle ≠ Execution Lifecycle** | OP-RES-004; PO apply | Three independent lifecycles | Overdue task blocks signing |
| 7 | **Legal Equivalence ≠ Editorial Symmetry** | OP-RES-005A | Hybrid drafting paths; reconciliation | Forced symmetric drafting |
| 8 | **Archive is orthogonal to lifecycle** | PO-LC-006 | `archived_at` flag; not a status | Archive conflated with VOIDED |
| 9 | **Generated Text ≠ Effective Text** | PO-EDIT-002 | `effective = override ?? generated` | Override lost on regenerate |
| 10 | **Role-first Party Representation** | OP-RES-004/005 | PositionRole default; NamedPerson optional | HR turnover breaks orders |
| 11 | **Scenario-driven Generation with Manual Override** | OP-RES-005 | Scenario defaults + editable effective text | Rigid templates |
| 12 | **Execution Projection is downstream** | OP-RES-005 | Handoff descriptor only | Task engine in document module |
| 13 | **Export format must not define domain model** | OP-RES-005 scope | Semantic model independent of PDF/DOCX | DOCX structure drives schema |
| 14 | **PO must remain operational during migration** | Production constraint | Adapters; phased extraction | Big-bang rewrite |
| 15 | **Content ownership ≠ Document processing ownership** *(006A)* | Organizational observation | Separate content_author from created_by; intake + content confirmation | HR becomes implicit content author |

---

## 6. Scope and Non-goals

### 6.1 In scope

Target architecture, domain model, boundaries, lifecycles, specialization, migration, ADR backlog, implementation WP sequence.

### 6.2 Non-goals (first phase)

UDE на первом этапе **не является**:

- ECM/EDMS; universal BPM/workflow; external ЭЦП EDO  
- Machine translator; org-wide archive  
- Universal document constructor; task engine replacement  
- Legal expert system; low-code platform  

---

## 7. Unified Document Engine Boundaries

### 7.1 Inside UDE

| Area | Includes | Excludes |
|---|---|---|
| **Document Core** | identity, kind, org, number, date, status, archive, creator, signing metadata | HR employee master data |
| **Document Structure** | header, preamble, formula, items, attachments, signature, agreement, ack | Task assignments |
| **Semantic Content** | scenario, intent, object, parties, deadlines, results, evidence, dependencies | Runtime task status |
| **Localization** | locale representations, generated/effective, drafting path, staleness, reconciliation | Auto-translation engine |
| **Generation** | scenario selection, item construction, rendering, control meta-item, validation, assembly | Execution tracking |
| **Lifecycle** | draft→ready→sign→register→void; archive; audit | Task overdue handling |
| **Execution Projection** | obligation descriptor extraction | Task CRUD, reminders, evidence upload |
| **Specializations** | PO, OO, future kinds | Per-kind microservices |
| **Draft Intake** *(006A)* | Submitted text acceptance, provenance, author/operator separation | Automatic READY; implicit authorship |

### 7.2 Boundary diagram

[`diagrams/unified-document-engine-context.svg`](./diagrams/unified-document-engine-context.svg)

---

## 8. Domain Model

Conceptual entities (not ORM). Matrix: [`data/OP-RES-006-core-vs-specialization-matrix.csv`](./data/OP-RES-006-core-vs-specialization-matrix.csv)

| Entity | Purpose | Scope | Links | Shared/Specialized | Nature | Evidence | Open questions |
|---|---|---|---|---|---|---|---|
| **Document** | Legal act instance | Aggregate root | metadata, structure, items, lifecycle | Shared | Both | OP-RES-002 | Amendment doc vs inline edit |
| **Document Kind** | PO / OO / future | Registry key | specialization policy | Shared | Semantic | OP-RES-006 | Enum vs config table |
| **Document Specialization** | Kind-specific behavior | Policy | registries | Specialized | Semantic | OP-RES-003 | Plugin loading model |
| **Document Metadata** | Identity, status, archive | Header | org, signatory | Shared | Editorial+semantic | PO model | Paper-first numbering |
| **Document Section** | Structural block | Structure | block_kind | Shared | Editorial | OP-RES-002 | Operative formula placement |
| **Preamble** | Normative/factual basis | Section | basis refs | Shared | Editorial | 112/183 RU marker | Auto-detect limits |
| **Basis Reference** | External doc ref | Preamble/item | structured basis | Shared | Semantic | PO basis types | OO basis variety |
| **Operative Formula** | ПРИКАЗЫВАЮ | Section | print chrome | Shared | Editorial | 177/183 | KK mirror |
| **Order Item** | Numbered directive | Structure | obligations, locale | Shared | Both | OP-RES-004 | Sub-item numbering rules |
| **Item Type** | Render template family | Item | renderer, validation | Specialized | Semantic | 14 OO / 5 PO | OTHER fallback |
| **Business Intent** | Management meaning | Obligation | item type | Specialized | Semantic | OP-RES-003 intents | Intent vs type orthogonality |
| **Execution Obligation** | Executable duty unit | Item | party, deadline, object | Specialized | Semantic | OP-RES-004 | Multi-obligation split rules |
| **Control Obligation** | Supervision duty | Document/item | controller, scope | OO-primary | Semantic | 168/183 docs | Embedded vs final item |
| **Managed Object** | What is governed | Obligation | tags | Specialized | Semantic | OP-RES-003 | Tag taxonomy stability |
| **Party** | Actor in org context | Obligation | org structure | Shared | Semantic | OP-RES-004 | External parties rare |
| **Party Reference** | Role-first pointer | Party | resolution | Shared | Semantic | OP-RES-005 | Commission as party |
| **Deadline** | Temporal constraint | Obligation | semantics enum | Shared | Semantic | OP-RES-004 | Event-based deadlines |
| **Expected Result** | Outcome | Obligation | optional | Specialized | Semantic | OP-RES-005 | Do not auto-add |
| **Evidence Expectation** | Proof required | Obligation | ack_list etc | Specialized | Semantic | 102 ack items | Implicit vs explicit |
| **Dependency** | Sequencing | Obligation | item refs | Shared | Semantic | Rare in corpus | Explicit deps |
| **Attachment** | File or structured artifact | Structure | items, obligations | Shared | Both | 35 docs refs | Row-level obligations |
| **Signature** | Signatory block | Structure | frozen snapshot | Shared | Editorial | 99% | Digital sign future |
| **Agreement** | Visa block | Structure | optional | Shared | Editorial | 11 docs | Workflow integration |
| **Acknowledgement** | Distribution/ack | Structure | optional | Shared | Editorial | 25 items | OO more common |
| **Locale Representation** | Per-locale block state | Item/section | generated, effective | Shared | Editorial | PO-EDIT-002 | Per-item vs doc-level |
| **Generated Text** | Auto-rendered prose | Locale | semantic source | Shared | Editorial | PO generators | Versioned templates |
| **Effective Text** | Authoritative wording | Locale | override chain | Shared | Editorial | PO effective_text | Signing authority |
| **Translation Relation** | RU→KK lineage | Locale | source snapshot | Shared | Editorial | OP-RES-005A | Provenance storage |
| **Validation Result** | Check outcome | Document | errors/warnings | Shared | Semantic | V001–W010; BC001–BC025 | Waiver policy |
| **Lifecycle Audit** | Append-only events | Document | actor, timestamp | Shared | Editorial | PO audit | Event store design deferred |
| **Execution Projection** | Downstream snapshot | Outside aggregate | descriptors | Shared | Semantic | OP-RES-005 | Timing: sign vs register |
| **Content Author** *(006A)* | Management content owner | Metadata | PartyReference | OO-primary | Semantic | Org observation | ≠ record creator |
| **Record Creator** *(006A)* | System record creator | Metadata | created_by | Shared | Editorial | PO pattern | ≠ content author |
| **Submitting Unit** *(006A)* | Source org unit | Intake | OrganizationalUnit | OO-primary | Semantic | Org observation | — |
| **Text Provenance** *(006A)* | Origin of locale text | Locale block | source_type, actors | Shared | Editorial | OP-RES-006A | Per-block minimum |
| **Content Confirmation** *(006A)* | Author meaning acknowledgment | Workflow gate | content_author | OO-primary | Semantic | OP-RES-006A | Policy per change class |

---

## 9. Document Aggregate

### 9.1 Hypothesis confirmed: Document is aggregate root

```text
Document (Aggregate Root)
├── Metadata
├── Structure
├── Items[]
│     ├── Semantic Definition
│     └── Locale Renderings (per block)
├── Attachments[]
├── Locale Representations (document-level aggregate state)
├── Lifecycle State
├── Audit[] (append-only)
└── [Execution Projection — downstream, eventual consistency]
```

Diagram: [`diagrams/document-aggregate-model.svg`](./diagrams/document-aggregate-model.svg)

### 9.2 Consistency boundary

**Inside aggregate (atomic changes):**

- Item semantic edit + locale invalidation  
- Editorial override + fingerprint update  
- Lifecycle transition + audit event  
- Regeneration scope (item or document)  

**Outside aggregate:**

- Execution Projection (eventual consistency OK)  
- Party resolution against live org structure (snapshot at sign)  
- Task runtime state  

### 9.3 Authority rules

| Phase | Authority |
|---|---|
| DRAFT editing | Semantic model |
| Early intake *(006A)* | submitted text + provenance (semantic partial OK) |
| Editorial draft *(006A)* | semantic model + effective text under reconciliation |
| READY gate | Effective text (both mandatory locales) + content confirmation (OO) |
| SIGNED/REGISTERED | Immutable effective text snapshot |
| VOIDED | Legal invalidation; no silent edit |

---

## 10. Common Document Structure

Canonical sequence (OP-RES-002, confirmed 183 DOCX):

```text
Header → Preamble/Basis → Operative Formula → Numbered Items → Attachments → Signature → Agreement → Acknowledgement
```

| Block | PO mapping | OO mapping |
|---|---|---|
| Header | `title` editorial + metadata | Same + scenario-derived title |
| Preamble | `preamble` editorial | Normative + factual basis |
| Operative Formula | Print chrome | Explicit paragraph |
| Items | `item.body`, `item.basis` | Obligation-bearing items + CONTROL meta |
| Attachments | Scans, basis docs | Rosters, plans, schedules |
| Signature | `signed_by_*` frozen | Same |
| Agreement | Rare | Келісілді episodic |
| Acknowledgement | Rare | Танысу парағы more common |

---

## 11. Order Item and Obligation Model

### 11.1 Common Order Item contract

```text
Order Item
├── item_type
├── sequence
├── semantic_payload (specialized)
├── obligations[] (0..N)
├── locale_renderings[] (per block)
├── generated_text / effective_text / override_state
└── validation_result
```

### 11.2 Personnel vs Operational comparison

| Aspect | Personnel Item | Operational Item |
|---|---|---|
| Primary payload | employee_id, dates, org/position/rate | intent, party, object, deadline |
| Obligations | Implicit 1:1 (HR event) | Explicit 1..N Execution Obligation |
| Control | None | Control Obligation (meta-item) |
| Item types | HIRE, TRANSFER, TERMINATION, CONCURRENT_* | 14 families (DIRECT, CREATE_BODY, CONTROL…) |
| Regeneration | Per block, fingerprint | Same + obligation validation |

### 11.3 Why Item ≠ Obligation

- **Editorial unit** (numbered clause, locale text) ≠ **management unit** (who does what by when)  
- 14% items have multiple obligations (OP-RES-004)  
- Control is obligation but often separate item  
- Personnel collapses 1:1 for MVP; OO cannot  

---

## 12. Specialization Model

### 12.1 Options compared

| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| Class inheritance | Familiar OOP | Fragile; cross-cutting concerns | **Reject** |
| Composition + policy | Flexible; PO-proven patterns | Requires registries | **Recommended** |
| Plugin modules | Clean extension | Discovery/versioning | **Recommended** for generators |
| Bounded-context integration | Clear boundaries | Integration overhead | **Defer** service split |
| Duplicate modules | Fast short-term | Debt; divergence | **Reject** |

### 12.2 Recommendation

**Composition + policy/registry + plugin-like specialization modules** (ADR-UDE-002).

Diagram: [`diagrams/document-specialization-model.svg`](./diagrams/document-specialization-model.svg)

---

## 13. Personnel Orders Specialization

| Element | Implementation | UDE role |
|---|---|---|
| Employee event semantics | `employee_events` via apply | Execution projection adapter (HR) |
| Event types | HIRE, TRANSFER, TERMINATION, RATE_CHANGE | Personnel item registry |
| Item registry | 5 MVP types + COMPOSITE header | Personnel specialization policy |
| Validation | `basis_policy`, `ready_gate` | Personnel validation hooks |
| Apply integration | `apply_service` | Domain-specific; stays in PO module |

**Remains personnel-specific (Class C):** HR generators, basis enums, apply/void rollback, employee form registry.

---

## 14. Operational Orders Specialization

| Element | Research source | UDE role |
|---|---|---|
| 8 domains, 21 scenarios | OP-RES-003 | Scenario Registry |
| P0: S_TRAVEL, S_COMMISSION, S_CLINICAL, S_ACCOUNTING | OP-RES-005 (~59%) | P0 blueprints |
| 14 item type families | OP-RES-005 registry CSV | Item Type Registry |
| Execution + Control obligations | OP-RES-004 | Semantic model |
| Commissions, deadlines, attachments | OP-RES-004 matrix | Specialized payloads |

**Cannot artificially universalize:** commission composition rules, travel funding clauses, regulatory mega-orders (30–120 items).

---

## 15. Generation Architecture

Three drafting paths *(006A — see [OP-RES-006A](./OP-RES-006A-initiation-authorship-and-draft-intake-addendum.md))*:

| Path | Flow | OO MVP priority |
|---|---|---|
| **Model A** — Semantic-first | Scenario → Inputs → Semantic → RU/KK Render | P2 (parallel) |
| **Model B** — Internal RU-first | RU Draft → Translation → Reconciliation | P1 |
| **Model C** — Submitted-text Intake | Submitted RU/KK → Intake → Enrichment → Translation → Content Confirm | **P0** |

Pipeline (OP-RES-005 — Model A/B):

```text
Scenario Selection → Input Collection → Semantic Item Construction
→ Obligation Validation → Clause Rendering → Control Meta-item Generation
→ Document Assembly → Locale Rendering → Manual Adjustment
→ Bilingual Validation → Final Validation → Preview/Export
→ Execution Projection (handoff)
```

Model C prepend: `Submitted Text → Intake Validation → Provenance Capture → Editorial Enrichment → [pipeline tail]`

Diagram: [`diagrams/generation-localization-execution-boundaries.svg`](./diagrams/generation-localization-execution-boundaries.svg)

| Stage | Shared | Specialization hook |
|---|---|---|
| Scenario selection | Shell | Scenario Registry per kind |
| Item construction | Order Item contract | Item Type Registry |
| Clause rendering | Orchestration | Renderer Registry |
| Control meta-item | — | OO policy (auto + editable) |
| Validation | Framework | Validation Rule Registry |
| Regeneration | Fingerprint/stale | Per item_type scope |

**Idempotency:** same semantic input + registry version → same generated_text.  
**Regeneration boundaries:** item-level default; document-level optional; never silent post-sign.  
**Blocking vs warning:** V001–V016 errors; W001–W010 warnings; BC P0 errors block READY.

---

## 16. Localization Architecture

### 16.1 Target mode (Model A)

Language-independent semantic model → independent RU renderer + KK renderer.

### 16.2 Observed editorial mode (Model B)

RU effective draft → translation → KK effective draft → bilingual reconciliation.

### 16.3 Locale Representation (part of Document aggregate)

Per-block: `generated_text`, `override_text`, `effective_text`, `review_status`, `source_language`, `drafting_path`, `semantic_version_ref`, `stale_reason`, `reconciliation_result`, `waiver`.

*(006A)* Additional provenance per block: `source_type` (SUBMITTED/GENERATED/TRANSLATED/MANUALLY_*), `source_actor`, `source_unit`, `source_timestamp`, `derived_from_version`, `content_confirmed_by`, `localization_reviewed_by`. **`submitted_text` ≠ `effective_text`** — no automatic promotion.

Document-level aggregate: overall bilingual readiness (derived from mandatory locales).

Diagram: [`diagrams/multilingual-document-architecture.svg`](./diagrams/multilingual-document-architecture.svg)

---

## 17. Hybrid RU/KK Drafting Workflow

| Concept | Definition |
|---|---|
| `source_language` | Editorial primary (probable `ru` default) |
| `drafting_path` | `symmetric` \| `ru_first_translation` \| `kk_first` |
| Locale state | CURRENT, STALE, REVIEW_REQUIRED, UNKNOWN (+ research: translated, reviewed, reconciled, waived) |
| Partial stale | Document READY blocked if **mandatory** locale STALE/REVIEW_REQUIRED |
| Attachment locale | Attachments may have own language status when structured text |

**Rule (mandatory):** `READY_FOR_SIGNATURE` **not allowed** when mandatory locale is STALE or REVIEW_REQUIRED without explicit policy-based waiver (audited).

### 17.1 BC checks — signing blockers vs warnings

| Block READY (errors) | Warnings |
|---|---|
| BC001 item count match | BC006 block order |
| BC002 numbering sequence | BC022 calque detection |
| BC007 date values | BC024 structural drift (→ REVIEW_REQUIRED) |
| BC008 amounts | BC025 cross-file pair |
| BC010 party role parity | W009 bilingual asymmetry |
| BC013–BC016 semantic parity (assisted) | |
| BC019 clause completeness | |
| BC020 no placeholders | |
| BC021 terminology (human) | |
| BC023 ru_change_after_kk (staleness) | |

Personnel Orders READY gate maps to BC019-equivalent; extend for BC001–BC023 in OO.

---

## 18. Document Lifecycle

| State | Meaning |
|---|---|
| `DRAFT` | Editable |
| `READY_FOR_SIGNATURE` | Validation passed; awaiting sign |
| `SIGNED` | Signed; may precede registration |
| `REGISTERED` | Registered in journal |
| `VOIDED` | Legally void (`void_kind`: CANCEL or ANNUL) |

**Archive:** orthogonal `archived_at` — immutable; hidden from default journal.

**PO implemented:** lifecycle audit, CANCEL (pre-reg), ANNUL (post-reg), archive/restore, locked post-sign.

Diagram: [`diagrams/three-lifecycles-model.svg`](./diagrams/three-lifecycles-model.svg)

---

## 19. Localization Lifecycle

Research states (not production enums):

| State | Meaning |
|---|---|
| CURRENT | Aligned with semantic/fingerprint |
| STALE | Source changed after derivation |
| REVIEW_REQUIRED | Structural/terminology drift |
| UNKNOWN | Legacy import |

Process stages: generated → translated → reviewed → reconciled → (waived).

---

## 20. Execution Lifecycle

| State | Meaning |
|---|---|
| created | Projection emitted |
| waiting | Not started |
| in_progress | Active |
| completed / partially_completed | Outcome |
| overdue | Past deadline |
| cancelled / replaced | Void or superseded |
| continuous | Permanent duty |
| closed_by_controller | Control closure |

**Downstream only** — not stored in Document aggregate.

---

## 21. Lifecycle Interaction Rules

Matrix: [`data/OP-RES-006-lifecycle-interaction-matrix.csv`](./data/OP-RES-006-lifecycle-interaction-matrix.csv)

| Rule | Description |
|---|---|
| L1 | Document, localization, execution lifecycles are **independent** |
| L2 | STALE/REVIEW_REQUIRED mandatory locale **blocks** READY_FOR_SIGNATURE |
| L3 | VOIDED CANCEL — no projection; ANNUL — compensating projection |
| L4 | Archive blocks **all** document mutations |
| L5 | Execution overdue does **not** change document status |
| L6 | Signed document — semantic model changes require amendment, not regenerate |
| L7 | Waiver of locale blocker requires audit event |
| L8 *(006A)* | Content confirmation gates READY for OO when content changes detected |
| L9 *(006A)* | Editorial substates (intake_review, translation_required, etc.) are derived conditions, not document status enum |

---

## 22. Party and Responsibility Model

### 22.1 Party Reference types

- NamedPerson (optional resolution)  
- PositionRole (preferred for permanent duties)  
- OrganizationalUnit  
- Commission / WorkingGroup  
- ExternalParty (rare in corpus)

### 22.2 Role distinctions

| Role | Meaning |
|---|---|
| executor / responsible | Execution Obligation assignee |
| controller | Control Obligation assignee |
| approver | Agreement block (not access permission) |
| signer | Signature metadata |
| informed | Acknowledgement / distribution |

### 22.3 Resolution rules

- **DRAFT:** live org resolution allowed  
- **SIGNED:** frozen ResolvedPartySnapshot  
- **Role vs person:** permanent duties → role; one-time personal directive → NamedPerson acceptable  

**Not mixed with:** access permissions, task assignee runtime state.

### 22.4 Process roles vs Party model *(006A)*

| Role | Party model? |
|---|---|
| Content Author, Business Initiator | PartyReference |
| Executor, Controller (in text) | PartyReference |
| Document Operator, Translator, Registrar | System actor in audit (not access permission) |

**Forbidden:** `created_by` (Record Creator) automatically implies Content Author.

---

## 23. Attachment Architecture

| Type | Role |
|---|---|
| attachment as file | SIGNED_SCAN, BASIS_DOCUMENT (PO) |
| attachment as generated section | Commission roster generated from data |
| attachment as structured artifact | Schedule, employee list, estimate |
| attachment as obligation source | Rows → Execution Obligations when item delegates |

OO types: commission roster, action plan, schedule, employee list, estimate, equipment list, regulation, report form.

| Concern | Rule |
|---|---|
| Lifecycle | Draft-editable; frozen at sign |
| Localization | May have per-attachment locale status |
| Stale propagation | Semantic change → attachment stale if derived |
| Execution | Row-level projection when configured |

---

## 24. Validation Architecture

| Layer | Examples | Severity |
|---|---|---|
| Semantic | mandatory items, party, object, deadline, controller, commission | errors |
| Structural | numbering, refs, block order, placeholders | errors/warnings |
| Localization | BC001–BC025, staleness | errors (P0 BC) |
| Intake *(006A)* | I001–I026 metadata, provenance, structure | errors/warnings |
| Lifecycle | transition guards, archive immutability, READY | errors |
| Projection | resolvable party, deadline semantics | errors at handoff |

| Class | Behavior |
|---|---|
| errors | Block transition |
| warnings | Allow with acknowledgment |
| waivable blockers | STALE locale with policy waiver (audited) |
| non-waivable | Missing mandatory item, empty effective text, archive mutation |

---

## 25. Audit and Versioning

| Event type | Append-only |
|---|---|
| lifecycle (CANCEL, ANNUL, ARCHIVE, RESTORE) | yes |
| semantic change | yes |
| locale change / regeneration | yes |
| manual override | yes |
| translation review / reconciliation | yes |
| execution projection | yes |
| draft_submitted *(006A)* | yes |
| content_author_declared *(006A)* | yes |
| submitted_text_captured *(006A)* | yes |
| content_confirmed / rejected *(006A)* | yes |
| translation_requested / completed *(006A)* | yes |
| editorial_form_only *(006A)* | yes |

**Principle *(006A)*:** Record creator ≠ Content author — must be distinguishable in audit.

**Reproducibility:** signed effective text snapshot enables PDF reproduction.  
**No silent regeneration** after SIGNED/REGISTERED.

---

## 26. Immutability Rules

| State | Editable? | Correction path |
|---|---|---|
| DRAFT | Yes (semantic + effective) | Direct edit |
| READY | Policy: return-to-DRAFT or limited edit | PO debt: still editable |
| SIGNED / REGISTERED | **No** semantic/effective edit | Amendment/compensating order |
| VOIDED | No | New document |
| ARCHIVED | **Immutable** | Restore only (non-archived voided) |
| Locale reconciled (signed) | Frozen | N/A |
| Execution projected | Descriptor immutable; tasks mutable downstream | Compensating projection |

---

## 27. Execution Projection Boundary

### 27.1 Execution Obligation Descriptor (handoff contract)

| Field | Required |
|---|---|
| source_document_id, source_item_id | yes |
| scenario, business_intent | yes |
| managed_object | yes |
| responsible_party_reference | yes |
| co_executors | optional |
| deadline_semantics | conditional |
| expected_result, evidence_expectation | optional |
| dependencies | optional |
| controller, control_scope | conditional |
| attachment_source | optional |
| locale_independent_description | yes |

### 27.2 Projection rules

| Rule | Policy |
|---|---|
| Moment | **After REGISTERED** (draft preview optional, non-binding) |
| Idempotency | Re-projection yields same logical descriptor set |
| VOIDED CANCEL | No projection / cancel draft preview |
| VOIDED ANNUL | Compensating cancel projection |
| Amendment | New projection version; link to superseded |

**PO today:** `apply_service` → `employee_events` is HR-specific execution projection.

---

## 28. Rendering and Export

| Layer | Source |
|---|---|
| Semantic Document | Structured model |
| Effective Localized Document | effective_text per block |
| Print View Model | Projection (PO: `PersonnelOrderPrintViewModel`) |
| HTML Preview | On-demand |
| Official PDF | Playwright (existing PO path) |
| Future DOCX | Versioned templates |

| Rule | Detail |
|---|---|
| Renderer independence | Templates versioned; semantic model stable |
| Signed artifact | effective snapshot + template version → reproducible PDF |
| Bilingual layout | `kk`, `ru`, `kk-ru` composition at render time |
| Watermark | By lifecycle status (extend void_kind awareness) |
| PO compatibility | Do not change current PDF contour in OP-RES-006 |

---

## 29. Logical Components

[`data/OP-RES-006-component-responsibility-matrix.csv`](./data/OP-RES-006-component-responsibility-matrix.csv)  
[`diagrams/unified-document-engine-components.svg`](./diagrams/unified-document-engine-components.svg)

**Forbidden dependencies:** Generation → Task engine; Document Core → Execution runtime.

---

## 30. Bounded Contexts

[`diagrams/target-bounded-contexts.svg`](./diagrams/target-bounded-contexts.svg)

| Context | Relationship |
|---|---|
| Document Management | Core upstream |
| Document Generation | Uses registries |
| Document Localization | Part of generation tail |
| Personnel / Operational Domain | Specializations |
| Organization & Parties | Upstream for resolution |
| Execution Management | **Downstream** |
| File/Attachment Management | Supporting |

**Modular monolith** — no microservices until proven need (ADR: **no** at MVP).

---

## 31. Conceptual Data Architecture

| Data kind | Source of truth | Notes |
|---|---|---|
| Canonical semantic data | Semantic model | Authority pre-sign |
| Effective localized text | Editorial blocks | Authority for READY/signing |
| Immutable signed snapshot | Frozen at SIGNED/REGISTERED | Authority post-sign |
| Generated artifacts | Regenerable from semantic + registry version | Not authority |
| Audit events | Append-only log | Historical reproducibility |
| Attachments | File store + metadata | May contain structured rows |
| Execution projections | Downstream store | Eventual consistency |

| Question | Answer |
|---|---|
| Pre-sign authority | **Semantic model** (effective text derived); *(006A)* early intake: submitted+provenance; editorial: partial semantic OK |
| Post-sign authority | **Immutable effective localized snapshot** |
| Bilingual package | Per-block locale rows + document-level aggregate state |
| PDF reproducibility | effective snapshot + template version + renderer version |
| Old doc with new renderer | Possible if snapshot + template version retained |

---

## 32. Access and Authority Boundary

Capabilities (not full access model):

create, edit_own_draft, edit_scoped_draft, translate_locale, review_translation, reconcile_bilingual, approve_content, mark_ready, sign, register, cancel_own, cancel_scope, annul, archive, restore, view_audit, preview_pdf, issue_waiver, project_execution.

*(006A)* Additional capabilities: `submit_operational_draft`, `create_draft_on_behalf`, `declare_content_author`, `accept_draft_into_intake`, `request_clarification`, `edit_official_form`, `request_translation`, `provide_translation`, `review_localization`, `confirm_content`, `reject_editorial_changes`.

**PO implemented:** ownership (`created_by`), CANCEL_OWN/CANCEL_SCOPE, ARCHIVE/RESTORE.  
**Deferred:** granular void, audit read grants, waiver capability.

**Document authority ≠ executor responsibility.**

---

## 33. Current Personnel Orders Gap Analysis

See dedicated artifact: [OP-RES-006-personnel-orders-gap-analysis.md](./OP-RES-006-personnel-orders-gap-analysis.md)

**Summary:** 16 Class A (reuse), 5 Class B (extract), 5 Class C (PO-specific), 3 Class D (debt), 13 Class E (missing for OO).

---

## 34. Compatibility Requirements

- Existing PO routes functional  
- API compatibility  
- Stored orders readable  
- PDF/HTML reproducible  
- Lifecycle semantics unchanged  
- Archive/cancel behavior unchanged  
- No mandatory legacy migration  
- Feature flags/adapters conceptually allowed  
- OO independent of full PO refactor  

---

## 35. Migration Strategy

See: [OP-RES-006-migration-roadmap.md](./OP-RES-006-migration-roadmap.md) *(updated OP-RES-006A)*

Phases 0–6; no big-bang; OO in Phase 4 with **intake-first MVP (Model C)**; PO convergence Phase 6.

---

## 36. ADR Backlog

See: [OP-RES-006-adr-backlog.md](./OP-RES-006-adr-backlog.md) — ADR-UDE-001 through ADR-UDE-016 *(006A adds 011–016)*.

---

## 37. Implementation Roadmap

[`data/OP-RES-006-implementation-wp-roadmap.csv`](./data/OP-RES-006-implementation-wp-roadmap.csv)  
[`diagrams/implementation-roadmap.svg`](./diagrams/implementation-roadmap.svg)

**First WP after OP-RES-006:** **UDE-000 — Architecture Ratification**

---

## 38. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Over-generalization | Scenario/item registries; no universal payload |
| Premature DSL | Template registry, not custom language |
| Big-bang refactor | 6-phase migration; adapters |
| Semantic/effective divergence | Fingerprint + staleness; semantic authority pre-sign |
| Bilingual drift | BC checks; READY block; reconciliation workflow |
| Registry explosion | P0 registries only; defer full 21 scenarios |
| Task engine coupling | Projection descriptor boundary |
| Weak party identity | Role-first + snapshot at sign |
| PO migration breakage | Per-phase compatibility proof; rollback toggles |
| Signed reproducibility | Immutable snapshot + template version |
| Attachment complexity | Phased; structured attachments in OO-IMP-008 |
| Lifecycle coupling | Three independent lifecycles (ADR-UDE-004) |
| Legal/task conflation | Execution downstream |
| Insufficient KK evidence | BC checks + human review; organizational interview |
| ECM scope creep | Non-goals §6.2 |

---

## 39. Open Questions

1. Amendment document workflow vs inline correction for signed orders  
2. Mandatory KK for all order types (S_TRAVEL only 33% bilingual in archive)  
3. Approval/visa workflow priority  
4. Projection moment: SIGNED vs REGISTERED for OO  
5. Structured attachment row schema for commission rosters  
6. Template versioning and legal approval of clause library  
7. Waiver authority for locale blockers — which role?  
8. *(006A)* Content confirmation — mandatory for all OO or scenario-based?  
9. *(006A)* Authoritative locale on RU/KK conflict  
10. *(006A)* KK delay workflow and waiver policy  
11. *(006A)* Form-only vs content change classification — org policy  

See also: [OP-RES-006A Interview Guide](./OP-RES-006A-organizational-interview-guide.md)

---

## 40. Organizational Interview Questions

1. Who translates RU → KK? Internal role or external?  
2. Is READY allowed before KK reconciliation?  
3. Authoritative version on RU/KK conflict at signing?  
4. Domain-specific bilingual policy (travel vs commission)?  
5. Who may issue locale staleness waiver?  
6. Is projection to tasks required at registration or later?  
7. Commission roster: inline vs attachment as SoT?  

---

## 41. Architecture Ratification Criteria

- [ ] ADR-UDE-001–016 accepted *(006A: includes 011–016)*  
- [ ] OP-RES-006A addendum ratified  
- [ ] Terminology glossary frozen (incl. content author, document operator, submitted text)  
- [ ] Three lifecycles accepted  
- [ ] Execution boundary accepted  
- [ ] Migration phases accepted  
- [ ] PO compatibility guarantees acknowledged  
- [ ] Non-goals acknowledged  
- [ ] Organizational interviews scheduled (§40; [006A guide](./OP-RES-006A-organizational-interview-guide.md))  
- [ ] Three drafting paths accepted; Model C as OO MVP P0  
- [ ] UDE-000 WP authorized  

---

## 42. Conclusions

OP-RES-006 defines a **evidence-based, incrementally adoptable** Unified Document Engine architecture that:

1. Unifies Personnel and Operational Orders under one document mechanism  
2. Preserves production Personnel Orders MVP  
3. Separates document, localization, and execution concerns  
4. Reuses PO editorial/lifecycle foundation (16 Class A components)  
5. Adds OO via parallel specialization without full PO refactor  
6. Supports hybrid RU/KK workflow  
7. Defers execution runtime to projection boundary  
8. Provides migration path, ADR backlog, and implementation WP sequence  

**Target architecture diagram (confirmed):**

```text
Unified Document Engine
│
├── Document Core
│      ├── Identity and Metadata
│      ├── Structure
│      ├── Items
│      ├── Attachments
│      └── Audit
│
├── Editorial Core
│      ├── Semantic Model
│      ├── Generated Text
│      ├── Effective Text
│      └── Manual Overrides
│
├── Draft Intake *(006A)*
│      ├── Submitted Text Acceptance
│      ├── Authorship and Provenance
│      └── Content Confirmation
│
├── Localization
│      ├── RU / KK Representations
│      ├── Text Provenance per Block
│      ├── Translation Workflow
│      ├── Staleness
│      └── Reconciliation
│
├── Generation
│      ├── Scenarios
│      ├── Item Registries
│      ├── Renderers
│      └── Validation
│
├── Lifecycle
│      ├── Document Lifecycle
│      ├── Archive
│      └── Lifecycle Audit
│
├── Specializations
│      ├── Personnel Orders
│      └── Operational Orders
│
├── Rendering
│      ├── HTML Preview
│      ├── PDF
│      └── Future DOCX
│
└── Execution Boundary
      └── Execution Projection
```

---

## Mandatory Questions — Direct Answers

| # | Question | Answer |
|---|---|---|
| 1 | Ядро UDE? | **Document Core** (identity, structure, lifecycle, audit) + **Editorial Core** + **Localization** + **Generation** + **Rendering**, orchestrated as modular monolith. |
| 2 | Общая сущность PO/OO? | **Document** with shared shell, **Order Item**, **Locale Representation** (generated/effective/override), lifecycle states, audit. |
| 3 | Специализация? | Scenario taxonomy, item type registries, obligation semantics, validation policies, apply/projection adapters, HR vs OO generators. |
| 4 | Document aggregate root? | **Да.** Execution Projection outside aggregate boundary. |
| 5 | Единица генерации? | **Order Item** (numbered clause with locale renderings). |
| 6 | Единица управленческого смысла? | **Execution Obligation** (Control Obligation — отдельная разновидность). |
| 7 | Почему Item ≠ Obligation? | Item = editorial/navigation unit; obligation = executable meaning; 14% multi-obligation items; control often separate item. |
| 8 | Почему Control отдельно? | Controller ≠ executor in 95%+ cases; 92% docs; meta-item auto-generatable; scope differs from execution. |
| 9 | Три lifecycle? | **Document**, **Localization**, **Execution**. |
| 10 | Какие независимы? | **Все три** — взаимодействуют через rules (L1–L7), не сливаются в один FSM. |
| 11 | Локализация блокирует READY? | **STALE** и **REVIEW_REQUIRED** на mandatory locale — без policy waiver. |
| 12 | Semantic-first + RU-first? | **Hybrid:** Model A renderers + Model B translation path; `drafting_path` per document/locale. |
| 13 | SoT до подписания? | **Semantic model** (effective text derived from it). |
| 14 | SoT после подписания? | **Immutable effective localized snapshot** (+ signatory metadata). |
| 15 | generated vs effective? | Separate fields per locale block; `effective = override ?? generated`; both stored. |
| 16 | Manual overrides? | `override_text` preserved; regeneration marks STALE, never silent delete. |
| 17 | Bilingual reconciliation? | Audit event + `reconciliation_result` + BC checks; READY requires CURRENT on mandatory locales. |
| 18 | Attachments in generation/execution? | Structured attachments feed item generation; rows may source obligations; frozen at sign; own locale status. |
| 19 | Party representation? | **PartyReference** (role-first) → optional **ResolvedPartySnapshot**. |
| 20 | Person vs role? | Permanent duties → **role**; one-time personal directive → NamedPerson; snapshot at sign. |
| 21 | Где заканчивается UDE? | Validated export + projection descriptor emission + audit. |
| 22 | Где начинается execution? | Task/work item creation from projection — downstream contour. |
| 23 | Когда projection? | **After REGISTERED** (draft preview optional, non-binding). |
| 24 | VOIDED/ANNUL на projection? | CANCEL: no effect; ANNUL: **compensating** cancel projection. |
| 25 | PO reusable now? | Editorial blocks, staleness, lifecycle audit, archive, void_kind, print VM, PDF renderer, generation orchestration, ready gate pattern (16 Class A). |
| 26 | Extract to core? | Print VM interface, command patterns, editorial package, lifecycle/validation frameworks (Class B). |
| 27 | PO-specific? | HR generators, apply/void rollback, basis policy, employee form registry, employee_events (Class C). |
| 28 | OO без полного PO refactor? | **Да** — Phase 4 parallel OO module on shared shell concepts. |
| 29 | Миграция без big-bang? | 6 phases; adapters; PO convergence last; per-phase rollback. |
| 30 | Compatibility guarantees? | Routes, API, stored data, PDF/HTML, lifecycle, archive — unchanged (§34). |
| 31 | Микросервисы? | **Нет** на MVP — modular monolith; split only with proven need. |
| 32 | Нужные registries? | Document Kind, Scenario, Item Type, Renderer, Validation Rule, Party Resolution Policy, Attachment Type, Lifecycle Policy, Execution Projection Policy — **9 registries**, scoped P0 first. |
| 33 | Over-generalization risk? | Universal obligation payload, universal generator, premature DSL — **mitigate** via specialization policies. |
| 34 | ADR до реализации? | **ADR-UDE-001–010** ratified in UDE-000. |
| 35 | Первый WP? | **UDE-000 — Architecture Ratification**. |

---

*End of OP-RES-006 Target Architecture Specification*
