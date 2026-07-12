# UDE-000 — Terminology Freeze

WP: **UDE-000** (supporting artifact)  
Date: **2026-07-12**  
Status: **Frozen** — effective upon UDE-000 ratification

Machine-readable registry: [`data/UDE-000-terminology-registry.csv`](./data/UDE-000-terminology-registry.csv)

---

## Governance

| Rule | Detail |
|---|---|
| Authority | UDE-000 ratification |
| Changes | Require ADR amendment or explicit UDE glossary revision WP |
| Scope | Unified Document Engine architecture and implementation contracts |
| Excluded | UI labels, database column names (defined in implementation WPs) |

---

## Core Architectural Terms

### Document layer

| Term | Definition |
|---|---|
| **Document** | Legal act instance; aggregate root containing metadata, structure, items, lifecycle, audit |
| **Document Core** | Shared identity: kind, org, number, date, status, archive, creator, signing metadata |
| **Document Structure** | Ordered shell: header, preamble, operative formula, items, attachments, signature, agreement, acknowledgement |
| **Document Section** | Single block within Document Structure (maps to editorial block kinds in PO) |
| **Unified Document Engine (UDE)** | Shared document mechanism hosting specializations via composition and registries |

### Semantic layer

| Term | Definition |
|---|---|
| **Order Item** | Numbered generation/editorial unit; holds semantic payload and locale renderings |
| **Execution Obligation** | Minimal executable management duty; 0..N per Order Item |
| **Control Obligation** | Supervision duty; distinct from execution; often final meta-item |
| **Managed Object** | Entity governed by obligation (process, employee, commission, document, etc.) |
| **Party** | Actor in organizational context |
| **Party Reference** | Role-first pointer to Party; NamedPerson resolution optional |
| **Scenario** | Business blueprint supplying generation defaults (21 research scenarios) |
| **Item Type** | Semantic family determining clause template (14 OO families; 5 PO MVP types) |

### Editorial and text layer

| Term | Definition |
|---|---|
| **Generated Text** | System-produced prose from semantic model and templates |
| **Effective Text** | Authoritative wording: `override ?? generated`; signing authority pre-sign |
| **Submitted Text** | Text as received at intake **before** official acceptance; **≠ effective text** |
| **Translated Text** | Locale text derived from another locale (`source_type = TRANSLATED`) |
| **Locale Representation** | Per-locale block state including generated, effective, provenance, review status |
| **Text Provenance** | Origin metadata: source_type, source_actor, source_unit, derived_from_version |

### Process and authorship

| Term | Definition |
|---|---|
| **Draft Intake** | Contour accepting external draft; declares author, unit, provenance; does not auto-READY |
| **Content Author** | Owner of management content; typically dept head for OO; **≠ record creator** |
| **Document Operator** | Staff (typically HR) creating and formatting official record |
| **Record Creator** | System user creating document entry (`created_by`); often HR |
| **Submitting Unit** | Organizational unit providing draft |
| **Content Confirmation** | Content Author acknowledgment that meaning preserved after editorial changes |

### Lifecycle

| Term | Definition |
|---|---|
| **Document Lifecycle** | DRAFT → READY_FOR_SIGNATURE → SIGNED/REGISTERED → VOIDED; archive orthogonal |
| **Localization Lifecycle** | Per-locale: CURRENT, STALE, REVIEW_REQUIRED (research states) |
| **Execution Lifecycle** | Downstream task states; independent of document status |
| **Editorial Substate** | Derived condition (intake_review, translation_required, etc.); **not** document status enum |

### Boundaries

| Term | Definition |
|---|---|
| **Execution Projection** | Emission of obligation descriptors to task contour after REGISTERED |
| **Source of Truth (staged)** | See § Staged SoT below |

---

## Staged Source of Truth (resolves ADR-005 + ADR-016)

| Phase | Source of Truth |
|---|---|
| **Early Intake** | Submitted text + provenance (semantic model may be partial) |
| **Editorial Draft** | Semantic model (enriched) + effective text under reconciliation |
| **Ready for Signature** | Validated semantic model + reconciled effective locale representations |
| **After Signature** | Immutable effective bilingual snapshot + signatory metadata |

---

## Specializations

| Term | Definition |
|---|---|
| **Personnel Orders** | UDE specialization: employee events; HR often author and operator; Model A/B |
| **Operational Orders** | UDE specialization: obligations and control; dept author, HR operator; Model C intake P0 |

---

## Drafting Paths (research names)

| Term | Definition |
|---|---|
| **Model A — Semantic-first** | Scenario → structured inputs → semantic → RU/KK render |
| **Model B — Internal RU-first** | RU draft → translation → reconciliation |
| **Model C — Submitted-text Intake** | Submitted text → intake → enrichment → confirmation |
| **drafting_path** | Research attribute: symmetric, ru_first_translation, etc. |

---

## Term Conflicts Resolved

| Potential conflict | Resolution |
|---|---|
| Generated vs Effective vs Submitted | Three distinct layers; only effective is signing authority |
| Author vs Creator vs Operator | Three roles; explicit metadata each |
| Document status vs Editorial substate | Substates derived; never replace DRAFT/READY enum |
| Semantic SoT vs Intake SoT | Staged model by phase (T028) |
| Scenario-first vs Intake-first | Specialization and path specific; both valid in UDE |

---

## First Appearance Index

| Term | First WP |
|---|---|
| Document shell, blocks | OP-RES-002 |
| Domains, scenarios | OP-RES-003 |
| Obligations, parties | OP-RES-004 |
| Generation, item types | OP-RES-005 |
| Bilingual, BC checks | OP-RES-005A |
| UDE architecture | OP-RES-006 |
| Intake, authorship | OP-RES-006A |
| Official freeze | **UDE-000** |

---

*Terminology frozen 2026-07-12 as part of UDE-000 Architecture Ratification*
