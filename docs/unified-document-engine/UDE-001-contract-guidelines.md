# UDE-001 — Contract Guidelines

WP: **UDE-001** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Authority: UDE-000 ratification; ADR-UDE-001–016

---

## 1. Purpose

These guidelines govern how shared Unified Document Engine contracts are authored, extended, and consumed. They apply to all implementation work packages from UDE-002 onward.

---

## 2. Contract Nature

| Rule | Description |
|---|---|
| **Conceptual only** | Contracts describe domain meaning, responsibilities, and boundaries — not classes, tables, or API endpoints |
| **Immutable semantics** | Contract meaning changes only via ADR amendment or explicit glossary revision WP |
| **No runtime states** | Contracts define allowed states conceptually; production enums are implementation WPs |
| **No persistence design** | No ORM, SQL, column names, or migration scripts in contract documents |
| **No transport design** | No REST paths, GraphQL schemas, or UI component specs in shared contracts |
| **No specialization leakage** | Shared contracts must not reference HR events, employee_id, or OO scenario codes |

---

## 3. What Belongs in Shared Contracts

| Include | Exclude |
|---|---|
| Purpose and responsibility of each entity | Python/TypeScript type definitions |
| Mandatory properties (conceptual) | Database indexes |
| Mandatory relationships (conceptual) | Serializer formats |
| Invariants and authority rules | Permission matrix implementation |
| Extension points and registry hooks | Concrete generator code |
| Independence and coupling declarations | PO/OO module internals |

---

## 4. Naming and Terminology

| Rule | Detail |
|---|---|
| **Single glossary** | [UDE-001-shared-glossary.md](./UDE-001-shared-glossary.md) is the only authoritative term reference |
| **Frozen terms** | T001–T034 from UDE-000; changes require ADR or glossary revision WP |
| **Preferred names** | Use official English names in contracts; Russian may appear in examples only |
| **Undesirable names** | See glossary `undesirable_names` column — do not introduce synonyms without ADR |
| **Process vs domain** | Distinguish process roles (Content Author, Document Operator) from Party model entities |

---

## 5. Specialization Rules

| Rule | Description |
|---|---|
| **Composition over inheritance** | Specializations extend via policy + registry, not subclassing Document |
| **Shared shell, specialized payload** | Order Item contract is shared; `semantic_payload` is specialization-specific |
| **Registry ownership** | Each specialization owns its scenario, item type, renderer, and validation entries |
| **Adapter pattern** | Execution projection adapters are specialization-specific; descriptor contract is shared |
| **No forced universalization** | Commission rules, HR apply, travel funding — remain in specialization modules |

---

## 6. Text Layer Rules

| Rule | ADR | Description |
|---|---|---|
| Generated ≠ Effective | ADR-UDE-005 | Two distinct layers; effective = override ?? generated |
| Submitted ≠ Effective | ADR-UDE-012 | Submitted text never auto-promotes to effective |
| Staged Source of Truth | ADR-UDE-016 | SoT varies by phase: intake → editorial → ready → signed |
| Provenance required | ADR-UDE-013 | Per locale block: source_type, actor, unit, derived_from |
| Manual override preserved | ADR-UDE-005 | Regeneration marks stale; does not silently delete override |

---

## 7. Lifecycle Rules

| Rule | ADR | Description |
|---|---|---|
| Three lifecycles | ADR-UDE-004 | Document, Localization, Execution — independent |
| Archive orthogonal | ADR-UDE-004 | `archived_at` is not a document status |
| Editorial substate derived | ADR-UDE-004 | intake_review, translation_required — not status enum |
| Signed immutability | ADR-UDE-009 | Effective localized snapshot frozen at SIGNED/REGISTERED |
| Projection downstream | ADR-UDE-008 | Execution projection after REGISTERED; not in aggregate |

---

## 8. Independence Checklist

Before adding a contract to `shared/`, verify:

- [ ] Does not require Personnel Orders semantics
- [ ] Does not require Operational Orders semantics
- [ ] Usable for future document kinds (protocols, commissions, directives)
- [ ] No HR-specific fields in mandatory properties
- [ ] No task engine runtime in contract boundary

If any check fails → move to specialization contract, not shared.

---

## 9. Versioning and Change Control

| Change type | Process |
|---|---|
| New shared entity | UDE contract WP + ADR if boundary change |
| New value object | UDE contract WP; update matrices |
| New registry | Extension point WP + ADR-UDE-002 confirmation |
| Terminology change | Glossary revision WP; never silent rename |
| Breaking contract change | ADR amendment + migration note in implementation WP |

---

## 10. Implementation Mapping (Future)

When implementation WPs create code:

1. Map one conceptual contract → one module boundary (not necessarily one class)
2. Value objects → immutable types in `shared/value-objects/`
3. Registries → plugin registration in specialization modules
4. Policies → injectable strategy objects, not hard-coded in core
5. Tests → contract conformance tests per specialization

**UDE-001 does not create any of the above.**

---

## 11. Prohibitions (Reaffirmed)

- No production code changes
- No API changes
- No database migrations
- No Personnel Orders behavior changes
- No Operational Orders runtime
- No commit/push/deploy as part of UDE-001

---

*Contract guidelines effective upon UDE-001 completion. Supersedes informal naming in OP-RES documents for implementation phase.*
