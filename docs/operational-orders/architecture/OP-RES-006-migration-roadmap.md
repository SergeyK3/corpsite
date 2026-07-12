# OP-RES-006 — Migration Roadmap

WP: **OP-RES-006** (supporting artifact)  
Updated: **OP-RES-006A** (2026-07-12)  
Date: **2026-07-12**  
Principle: **No big-bang rewrite**

---

## Compatibility Guarantees (mandatory)

Throughout all phases:

- Existing Personnel Orders routes remain functional  
- API compatibility preserved (adapters if needed)  
- Stored personnel orders remain readable  
- PDF/HTML outputs remain reproducible  
- Lifecycle semantics unchanged (CANCEL/ANNUL/archive)  
- Legacy records do not require immediate migration  
- Operational Orders do not depend on full Personnel refactor  

---

## Phase Overview

```text
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
 Ratify      Contracts   Editorial    Lifecycle    OO MVP      Projection   PO Converge
```

Diagram: [`diagrams/personnel-to-unified-migration.svg`](./diagrams/personnel-to-unified-migration.svg)

---

## Phase 0 — Architecture Ratification

| Field | Value |
|---|---|
| **Goal** | Freeze architecture and terminology |
| **Entry** | OP-RES-006 + **OP-RES-006A** complete |
| **Deliverables** | Ratified OP-RES-006/006A, ADR backlog (UDE-001–016), glossary incl. authorship roles |
| **Risks** | Terminology drift if not ratified |
| **Rollback** | N/A (docs only) |
| **Proof** | Stakeholder sign-off checklist (§41 main doc) |

**WP:** UDE-000

---

## Phase 1 — Common Terminology and Roles *(006A update)*

| Field | Value |
|---|---|
| **Goal** | Extract shared concepts + **authorship/process roles** without changing PO behavior |
| **Entry** | Phase 0 ratified |
| **Deliverables** | Document Kind, Order Item, Locale contracts; **Content Author vs Document Operator**; role glossary |
| **Risks** | Premature abstraction |
| **Rollback** | Contracts are additive; no runtime change |
| **Proof** | PO test suite unchanged; no API diff |

**WP:** UDE-001

---

## Phase 1b — Draft Intake and Text Provenance *(006A new)*

| Field | Value |
|---|---|
| **Goal** | Architect submitted-text intake, provenance, content confirmation |
| **Entry** | UDE-001 terminology |
| **Deliverables** | Intake boundary spec; provenance model; I001–I026 validation; content confirmation policy |
| **Risks** | Over-engineering provenance |
| **Rollback** | Spec only; no runtime |
| **Proof** | ADR-UDE-011–016 ratified |

**WP:** UDE-002 *(repurposed from Document Core Extraction Plan — extraction plan moves to UDE-002b or Phase 2)*

---

## Phase 2 — Shared Editorial and Localization Core

| Field | Value |
|---|---|
| **Goal** | Unify generated/effective/override + provenance + staleness |
| **Entry** | Phase 1 + 1b |
| **Deliverables** | Shared editorial abstraction; bilingual staleness; BC + intake check mapping |
| **Risks** | Breaking fingerprint semantics |
| **Rollback** | PO continues using existing tables |
| **Proof** | Regenerate + override + READY gate behavior identical |

**WP:** UDE-003, UDE-004, UDE-005

---

## Phase 2b — Document Core Extraction Plan *(deferred from old Phase 1)*

**WP:** UDE-002b (optional parallel with Phase 2)

---

## Phase 3 — Shared Lifecycle and Audit Abstractions

| Field | Value |
|---|---|
| **Goal** | Lifecycle/audit as shared services behind PO adapters |
| **Entry** | Phase 2 editorial stable |
| **Deliverables** | Shared lifecycle policy interface; audit event taxonomy |
| **Risks** | void_kind regression |
| **Rollback** | Adapter delegates to existing PO services |
| **Proof** | Cancel/annul/archive/audit API responses unchanged |

**WP:** UDE-007

---

## Phase 4 — Operational Orders MVP *(006A: intake-first)*

| Field | Value |
|---|---|
| **Goal** | **Submitted-text Intake MVP** + content confirmation + translation workflow |
| **Entry** | Phases 1–3; UDE-002 intake spec |
| **Deliverables** | OO module with Model C path; RU/KK intake; provenance; content confirmation; preview/PDF |
| **Risks** | Skipping intake for scenario-first; scope creep |
| **Rollback** | OO module feature-flagged; PO unaffected |
| **Proof** | Submitted dept draft → official bilingual draft → content confirmed; no PO regression |

**WP:** OO-IMP-001 (Intake MVP), OO-IMP-002 (Content Confirmation + Translation)

**Parallel (not blocking MVP):** OO-IMP-003 Scenario-driven Generation (Model A)

**Out of scope:** task engine, full 21 scenarios, execution projection

**Also in Phase 4:** OO-IMP-004 (Lifecycle and Approval Integration)

---

## Phase 5 — Execution Projection

| Field | Value |
|---|---|
| **Goal** | Handoff ExecutionObligationDescriptor to task contour |
| **Entry** | OO MVP lifecycle integrated; REGISTERED documents |
| **Deliverables** | Projection adapter; idempotency; compensating cancel on ANNUL |
| **Risks** | Coupling with task engine; weak party resolution |
| **Rollback** | Projection disabled by flag; documents still usable |
| **Proof** | Descriptor emitted on REGISTERED; VOIDED triggers compensating event |

**WP:** OO-IMP-005 (Execution Projection)

---

## Phase 6 — Controlled Personnel Orders Convergence

| Field | Value |
|---|---|
| **Goal** | Gradually route PO through shared core |
| **Entry** | OO MVP proves shared shell; Phases 2–3 abstractions stable |
| **Deliverables** | PO adapters on shared editorial/lifecycle; deprecate legacy localized texts |
| **Risks** | Big-bang temptation; signed document reproducibility |
| **Rollback** | Per-route adapter toggle; instant revert to PO-native path |
| **Proof** | Full PO regression suite; PDF byte-compare on sample set |

**WP:** UDE-006

---

## Revised Implementation WP Sequence *(OP-RES-006A)*

| Order | WP | Risk |
|---|---|---|
| 1 | UDE-000 Architecture Ratification (006 + 006A) | Low |
| 2 | UDE-001 Terminology and Roles | Low |
| 3 | UDE-002 Draft Intake and Text Provenance | Medium |
| 4 | UDE-003 Shared Editorial and Localization Core | Medium |
| 5 | UDE-004 Localization Model (if split from 003) | Medium |
| 6 | UDE-005 Validation Framework | Medium |
| 7 | OO-IMP-001 Submitted-text Intake MVP | High |
| 8 | OO-IMP-002 Content Confirmation + Translation | High |
| 9 | OO-IMP-003 Scenario-driven Generation (parallel) | Medium |
| 10 | OO-IMP-004 Lifecycle and Approval | Medium |
| 11 | OO-IMP-005 Execution Projection | High |
| 12 | UDE-006 Personnel Convergence | High |

Machine-readable: [`data/OP-RES-006-implementation-wp-roadmap.csv`](./data/OP-RES-006-implementation-wp-roadmap.csv) *(updated 006A)*

---

## Decision: Can OO be added without full PO refactor?

**Yes.** Phase 4 explicitly adds Operational Orders in parallel using:

- Shared document shell (conceptual + partial code reuse from Class A components)  
- Separate OO specialization module and registries  
- PO continues on existing implementation until Phase 6  

This is the primary migration strategy recommended by OP-RES-006, **updated by OP-RES-006A** to prioritize submitted-text intake for Operational Orders MVP.
