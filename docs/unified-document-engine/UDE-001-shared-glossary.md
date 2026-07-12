# UDE-001 — Shared Glossary

WP: **UDE-001** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation — Single Reference**  
Authority: UDE-000 Terminology Freeze (T001–T034)

> **This glossary is the only authoritative term reference for UDE implementation phase.**  
> Source registry: [`../operational-orders/architecture/data/UDE-000-terminology-registry.csv`](../operational-orders/architecture/data/UDE-000-terminology-registry.csv)

---

## Governance

| Rule | Detail |
|---|---|
| Changes | ADR amendment or explicit UDE glossary revision WP only |
| Scope | UDE architecture and implementation contracts |
| Excluded | UI labels, database column names (defined in later WPs) |
| Language | Official names in English; Russian examples permitted in specialization docs |

---

## Glossary

### Document layer

| ID | Official name | Definition | Synonyms | Undesirable names | Source |
|---|---|---|---|---|---|
| T001 | **Document** | Legal act instance; aggregate root containing metadata, structure, items, lifecycle, and audit | Legal document, order (contextual) | Order record, file, case | OP-RES-006; ADR-UDE-001 |
| T002 | **Document Core** | Shared identity: kind, organization, number, date, status, archive, creator, signing metadata | Document header metadata | Document table row | OP-RES-006 |
| T003 | **Document Structure** | Ordered shell: header, preamble, operative formula, items, attachments, signature, agreement, acknowledgement | Document shell, block sequence | Template, layout | OP-RES-002 |
| T004 | **Document Section** | Single structural block within Document Structure | Block, editorial block | Paragraph, field | OP-RES-006 |
| T029 | **Unified Document Engine (UDE)** | Shared document mechanism hosting specializations via composition and registries | Document engine | ECM, EDMS, BPM | OP-RES-006; ADR-UDE-001 |

### Semantic layer

| ID | Official name | Definition | Synonyms | Undesirable names | Source |
|---|---|---|---|---|---|
| T005 | **Order Item** | Numbered generation and editorial unit; holds semantic payload and locale renderings | Numbered item, clause, directive item | Line item, task item | OP-RES-004; ADR-UDE-003 |
| T006 | **Execution Obligation** | Minimal executable management duty; 0..N per Order Item | Executor duty, assignment | Task, поручение (alone) | OP-RES-004 |
| T007 | **Control Obligation** | Supervision duty; distinct from execution; often final meta-item | Supervision duty | Controller field, oversight flag | OP-RES-004 |
| T008 | **Managed Object** | Entity governed by obligation (process, employee, commission, document, etc.) | Governed object, subject matter | Target, object ref (ambiguous) | OP-RES-003 |
| T009 | **Party** | Actor in organizational context for obligations | Actor, participant | User, employee (as primary key) | OP-RES-004 |
| T010 | **Party Reference** | Role-first pointer to Party; NamedPerson resolution optional | Party ref, assignee ref | employee_id (as sole representation) | OP-RES-005; ADR-UDE-007 |
| T011 | **Scenario** | Business blueprint supplying generation defaults | Blueprint, scenario template | Template (alone), form | OP-RES-003 |
| T012 | **Item Type** | Semantic family determining clause template and validation hooks | Item family, clause type | Event type (PO-specific) | OP-RES-005 |

### Editorial and text layer

| ID | Official name | Definition | Synonyms | Undesirable names | Source |
|---|---|---|---|---|---|
| T013 | **Generated Text** | System-produced prose from semantic model and templates | Auto text, rendered text | Draft text (ambiguous) | OP-RES-005; ADR-UDE-005 |
| T014 | **Effective Text** | Authoritative wording: override ?? generated; signing authority pre-sign | Final text, official text | Body text (alone), content | PO-EDIT-002; ADR-UDE-005 |
| T015 | **Submitted Text** | Text as received at intake before official acceptance; ≠ effective text | Incoming draft, source draft | Draft (alone), original | OP-RES-006A; ADR-UDE-012 |
| T016 | **Translated Text** | Locale text derived from another locale (source_type = TRANSLATED) | Translation | Machine translation output | OP-RES-006A; ADR-UDE-013 |
| T017 | **Locale Representation** | Per-locale block state including generated, effective, provenance, review status | Locale block, language version | Translation row | OP-RES-006; ADR-UDE-006 |
| T027 | **Text Provenance** | Origin metadata: source_type, source_actor, source_unit, derived_from_version | Text origin, source lineage | Author field (alone) | OP-RES-006A; ADR-UDE-013 |
| T028 | **Source of Truth** | Authority for decisions varies by phase (staged SoT model) | SoT, authority | Single source (incorrect) | ADR-UDE-005+016 |
| T034 | **Editorial Substate** | Derived condition (intake_review, translation_required, etc.); not document status enum | Workflow condition | Status, phase | OP-RES-006A |

### Process and authorship

| ID | Official name | Definition | Synonyms | Undesirable names | Source |
|---|---|---|---|---|---|
| T018 | **Draft Intake** | Contour accepting external draft; declares author, unit, provenance; does not auto-READY | Intake, draft submission | Import, upload | OP-RES-006A; ADR-UDE-012 |
| T019 | **Content Author** | Owner of management content; typically dept head for OO; ≠ record creator | Business author, content owner | Author (alone), created_by | OP-RES-006A; ADR-UDE-011 |
| T020 | **Document Operator** | Staff (typically HR) creating and formatting official record | HR operator, editorial processor | Creator, author | OP-RES-006A; ADR-UDE-015 |
| T021 | **Record Creator** | System user creating document entry (created_by); often HR | System creator | Author, owner | OP-RES-006A; ADR-UDE-011 |
| T032 | **Submitting Unit** | Organizational unit providing draft to document operator | Source unit, initiating unit | Department (free text) | OP-RES-006A |
| T026 | **Content Confirmation** | Content Author acknowledgment that meaning preserved after editorial changes | Author confirmation, meaning sign-off | Approval (alone) | OP-RES-006A; ADR-UDE-014 |

### Lifecycle

| ID | Official name | Definition | Synonyms | Undesirable names | Source |
|---|---|---|---|---|---|
| T022 | **Document Lifecycle** | DRAFT → READY_FOR_SIGNATURE → SIGNED/REGISTERED → VOIDED; archive orthogonal | Document status | Workflow state (alone) | OP-RES-006; ADR-UDE-004 |
| T023 | **Localization Lifecycle** | Per-locale: CURRENT, STALE, REVIEW_REQUIRED (research states) | Locale state, translation state | Document status | OP-RES-005A; ADR-UDE-006 |
| T024 | **Execution Lifecycle** | Downstream task states; independent of document status | Task lifecycle | Document execution status | OP-RES-004; ADR-UDE-004 |
| T025 | **Execution Projection** | Emission of obligation descriptors to task contour after REGISTERED | Projection handoff, apply | Task creation (in UDE) | OP-RES-005; ADR-UDE-008 |

### Specializations

| ID | Official name | Definition | Synonyms | Undesirable names | Source |
|---|---|---|---|---|---|
| T030 | **Personnel Orders** | UDE specialization: employee events; HR often author and operator; Model A/B | Personnel order, HR order | HR module (alone) | OP-RES-006 |
| T031 | **Operational Orders** | UDE specialization: obligations and control; dept author, HR operator; Model C intake P0 | Operational order, production order | Business order (ambiguous) | OP-RES-003 |
| T033 | **drafting_path** | Research attribute: symmetric, ru_first_translation, kk_first, submitted_intake | Drafting mode | Production enum (premature) | OP-RES-005A; ADR-UDE-006 |

---

## Extended Terms (UDE-001 additions, not frozen T-IDs)

These terms appear in domain contracts but were implicit in research. They inherit freeze governance upon UDE-001 completion.

| Term | Definition | Related T-ID | Source |
|---|---|---|---|
| **Business Intent** | Management meaning attached to obligation or item; specialization payload | T011, T012 | OP-RES-003 |
| **Deadline** | Temporal constraint on obligation with typed semantics | — | OP-RES-004 |
| **Expected Result** | Declared outcome of obligation; optional explicit | — | OP-RES-005 |
| **Evidence Expectation** | Proof or acknowledgment required for obligation closure | — | OP-RES-004 |
| **Attachment Reference** | File or structured artifact linked to document or obligation | — | OP-RES-004 |
| **Validation Result** | Outcome of semantic, structural, locale, or lifecycle checks | — | OP-RES-005 |
| **Document Audit Event** | Append-only record of lifecycle, editorial, or projection action | — | PO-LC |
| **Document Lifecycle State** | Current state in document lifecycle state machine | T022 | OP-RES-006 |
| **Localization Lifecycle State** | Current per-locale alignment state | T023 | OP-RES-005A |
| **Execution Lifecycle State** | Current downstream execution state (outside aggregate) | T024 | OP-RES-004 |
| **Execution Projection Descriptor** | Downstream handoff payload for one obligation | T025 | OP-RES-005 |
| **Order Item Sequence** | Ordering and numbering of items within document structure | T005 | OP-RES-002 |
| **Document Metadata** | Identity and status fields of Document Core | T002 | OP-RES-006 |
| **Document Kind** | Classification key selecting specialization (PersonnelOrder, OperationalOrder, future) | T029 | ADR-UDE-001 |
| **Document Specialization** | Kind-specific behavior bundle via registries and policies | T030, T031 | ADR-UDE-002 |

---

## Term Conflict Resolutions (Carried from UDE-000)

| Conflict | Resolution |
|---|---|
| Generated vs Effective vs Submitted | Three distinct layers; only effective is signing authority pre-sign |
| Author vs Creator vs Operator | Three roles; explicit metadata each; never auto-equate |
| Document status vs Editorial substate | Substates derived; never replace DRAFT/READY enum |
| Semantic SoT vs Intake SoT | Staged model by phase (T028) |
| Scenario-first vs Intake-first | Both valid; specialization and drafting path determine priority |

---

*Glossary published as part of UDE-001. Replaces informal term usage in implementation discussions.*
