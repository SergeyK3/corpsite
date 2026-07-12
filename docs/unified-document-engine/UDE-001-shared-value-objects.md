# UDE-001 — Shared Value Objects

WP: **UDE-001** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Matrix: [`data/UDE-001-value-object-matrix.csv`](./data/UDE-001-value-object-matrix.csv)

> Value Objects are immutable conceptual types identified by their values, not by identity. No code definitions in UDE-001.

---

## Value Object Index

| Value Object | Shared | Why Value Object |
|---|---|---|
| DocumentId | Yes | Opaque identity; equality by value |
| DocumentNumber | Yes | Formatted number string; no entity lifecycle |
| DocumentKind | Yes | Classification key; registry lookup |
| ScenarioId | Specialization | Blueprint identifier |
| ScenarioCode | Specialization | Human-stable scenario code |
| ItemType | Partially shared | Shared contract; registry values specialized |
| LocaleCode | Yes | ISO-like locale tag (ru, kk) |
| LanguageCode | Yes | Editorial language attribute |
| PartyId | Yes | Resolved party identity snapshot |
| RoleReference | Yes | Organizational role pointer |
| ManagedObjectType | Partially shared | Type tag; taxonomy specialized |
| DeadlineType | Yes | Temporal semantics discriminator |
| ValidationCode | Yes | Stable check identifier (V001, BC001) |
| EvidenceType | Yes | Proof category |
| LifecycleTransition | Yes | Named transition with reason |
| ArchiveState | Yes | Archived flag + metadata |
| TranslationState | Yes | Localization process stage |
| StalenessState | Yes | Derived staleness reason |
| SourceOfTruth | Yes | Phase authority marker |
| DraftingPath | Yes | Editorial workflow mode |
| TextSourceType | Yes | Provenance discriminator |

---

## DocumentId

| Aspect | Definition |
|---|---|
| **Value** | Opaque unique identifier for Document instance |
| **Valid states** | Non-empty; immutable after creation |
| **Scope** | All document kinds |
| **Why VO** | Identity reference without exposing persistence strategy |

---

## DocumentNumber

| Aspect | Definition |
|---|---|
| **Value** | Official registration number string (may be null in early DRAFT) |
| **Valid states** | Unassigned, provisional, registered |
| **Scope** | Document Core |
| **Why VO** | Formatting rules vary by org; not an entity |

---

## DocumentKind

| Aspect | Definition |
|---|---|
| **Value** | Classification selecting specialization (PersonnelOrder, OperationalOrder, future) |
| **Valid states** | Registry-defined kinds only |
| **Scope** | Document Core; registry extension |
| **Why VO** | Small closed set at architecture level; registry extends at implementation |

---

## ScenarioId / ScenarioCode

| Aspect | Definition |
|---|---|
| **Value** | Identifier and stable code for business blueprint |
| **Valid states** | Registry-defined; OO: 21 research scenarios; PO: item-first optional |
| **Scope** | Generation; specialization registries |
| **Why VO** | Lookup key; not aggregate root |
| **Shared?** | Contract shape shared; values specialization-specific |

---

## ItemType

| Aspect | Definition |
|---|---|
| **Value** | Semantic family tag determining renderer and validation |
| **Valid states** | PO: HIRE, TRANSFER, TERMINATION, etc.; OO: DIRECT, CREATE_BODY, CONTROL, etc. |
| **Scope** | OrderItem |
| **Why VO** | Immutable tag per item; registry-driven |
| **Shared?** | VO concept shared; enum values per specialization registry |

---

## LocaleCode / LanguageCode

| Aspect | Definition |
|---|---|
| **Value** | Locale tag (ru, kk) and editorial language |
| **Valid states** | Org-mandated set; mandatory locales for READY |
| **Scope** | LocaleRepresentation |
| **Why VO** | No independent lifecycle; compared by value |

---

## PartyId / RoleReference

| Aspect | Definition |
|---|---|
| **Value** | Resolved identity or unresolved role pointer |
| **Valid states** | RoleReference: position/org role; PartyId: snapshot after resolution |
| **Scope** | PartyReference, obligations, authorship |
| **Why VO** | Immutable snapshot at sign; role ref compared by org coordinates |

---

## ManagedObjectType

| Aspect | Definition |
|---|---|
| **Value** | Category tag for governed entity |
| **Valid states** | PO: employee, position; OO: process, commission, document, etc. |
| **Scope** | ManagedObject |
| **Why VO** | Discriminator without entity table in contract |

---

## DeadlineType

| Aspect | Definition |
|---|---|
| **Value** | FIXED_DATE, DURATION, BY_EVENT, CONTINUOUS, PERMANENT |
| **Valid states** | Architecture-level set; specialization may extend |
| **Scope** | Deadline |
| **Why VO** | Semantic discriminator paired with value fields |

---

## ValidationCode

| Aspect | Definition |
|---|---|
| **Value** | Stable identifier (V001–V016, BC001–BC025, W001–W010) |
| **Valid states** | Registry-defined; versioned with validation registry |
| **Scope** | ValidationResult |
| **Why VO** | Comparable, loggable, waiver-targetable |

---

## EvidenceType

| Aspect | Definition |
|---|---|
| **Value** | REPORT, ACKNOWLEDGMENT, ATTACHMENT, SIGNATURE, CUSTOM |
| **Valid states** | Architecture-level; registry extends |
| **Scope** | EvidenceExpectation |
| **Why VO** | Classification without behavior |

---

## LifecycleTransition

| Aspect | Definition |
|---|---|
| **Value** | Named transition: from_state, to_state, TransitionReason, actor |
| **Valid states** | Valid per lifecycle policy |
| **Scope** | Document, Localization (not Execution — downstream) |
| **Why VO** | Immutable event descriptor |

---

## ArchiveState

| Aspect | Definition |
|---|---|
| **Value** | is_archived, archived_at, archived_by |
| **Valid states** | Active, Archived |
| **Scope** | Document Core |
| **Why VO** | Orthogonal flag bundle; not lifecycle enum member |

---

## TranslationState / StalenessState

| Aspect | Definition |
|---|---|
| **Value** | Process stage (generated→translated→reviewed→reconciled) and staleness reason |
| **Valid states** | Research stages; STALE reasons: semantic_change, ru_change_after_kk, fingerprint_mismatch |
| **Scope** | LocaleRepresentation |
| **Why VO** | Derived state descriptors; immutable snapshots in audit |

---

## SourceOfTruth

| Aspect | Definition |
|---|---|
| **Value** | Phase authority: INTAKE, EDITORIAL, READY, SIGNED |
| **Valid states** | Staged per ADR-UDE-016 |
| **Scope** | Document editing authority |
| **Why VO** | Policy discriminator; not stored entity |

---

## DraftingPath

| Aspect | Definition |
|---|---|
| **Value** | SYMMETRIC, RU_FIRST_TRANSLATION, KK_FIRST, SUBMITTED_INTAKE |
| **Valid states** | Architecture-level (T033); maps to Models A/B/C |
| **Scope** | LocaleRepresentation; document-level default |
| **Why VO** | Editorial mode tag; influences localization policy |

---

## TextSourceType

| Aspect | Definition |
|---|---|
| **Value** | SUBMITTED, GENERATED, TRANSLATED, MANUALLY_AUTHORED, MANUALLY_EDITED, IMPORTED_LEGACY |
| **Valid states** | Architecture-level set |
| **Scope** | TextProvenance |
| **Why VO** | Provenance discriminator; drives staleness and promotion rules |

---

## Shared vs Specialization Values

| Value Object | Shared concept | PO values | OO values |
|---|---|---|---|
| DocumentKind | Yes | PersonnelOrder | OperationalOrder |
| ItemType | Yes | 5 MVP types | 14 families |
| ScenarioCode | Yes | Optional | 21 scenarios |
| ManagedObjectType | Yes | employee-centric | 8 object families |
| DraftingPath | Yes | symmetric, ru_first | submitted_intake P0 |

---

*Machine-readable matrix: [`data/UDE-001-value-object-matrix.csv`](./data/UDE-001-value-object-matrix.csv)*
