# UDE-001 — Shared Design Rules

WP: **UDE-001** (supporting artifact)  
Date: **2026-07-12**  
Status: **Architecture Foundation**  
Evidence: OP-RES-006 §5; ADR-UDE-001–016

---

## Mandatory Design Rules

These rules are **binding** for all UDE implementation work packages. Violation requires explicit ADR exception.

| # | Rule | Meaning | Violation risk | ADR |
|---|---|---|---|---|
| DR-01 | **Composition over inheritance** | Specialize via policy + registry + composition; reject class hierarchies for Document kinds | Fragile inheritance; cross-cutting breakage | ADR-UDE-002 |
| DR-02 | **Semantic before rendering** | Structured semantic model precedes prose; text is projection of semantics | Unreproducible documents; stale drift | ADR-UDE-005 |
| DR-03 | **Generated ≠ Effective** | System output and authoritative wording are separate layers; override preserved | Silent loss of manual edits on regenerate | ADR-UDE-005 |
| DR-04 | **Submitted ≠ Effective** | Intake text is not signing authority; promotion requires explicit acceptance | HR edits bypass author intent | ADR-UDE-012 |
| DR-05 | **Document ≠ Execution** | Document lifecycle independent of task/execution lifecycle | Overdue task blocks signing | ADR-UDE-004 |
| DR-06 | **Localization independent** | Per-locale state machine separate from document status | Conflated READY with translation done | ADR-UDE-006 |
| DR-07 | **Archive orthogonal** | Archive flag separate from VOIDED and lifecycle states | Archive mistaken for cancellation | ADR-UDE-004 |
| DR-08 | **Role-first** | PartyReference defaults to organizational role; NamedPerson optional | HR turnover breaks historical orders | ADR-UDE-007 |
| DR-09 | **Submitted-text supported** | Model C intake is first-class drafting path, not workaround | OO MVP blocked on scenario-first only | ADR-UDE-012 |
| DR-10 | **Scenario optional** | Scenario-driven generation is one path; intake-first equally valid | Forced scenario for all documents | ADR-UDE-012 |
| DR-11 | **Manual override preserved** | Regeneration marks override stale; does not delete without explicit action | Authoritative edits lost | ADR-UDE-005 |
| DR-12 | **Renderer independent** | Renderers consume semantic/locale state; do not own domain logic | Template drives schema | OP-RES-005 |
| DR-13 | **Projection downstream** | Execution projection emits descriptors only; no task CRUD in UDE | Task engine embedded in document module | ADR-UDE-008 |
| DR-14 | **Append-only audit** | Lifecycle and editorial events are immutable history | Mutable audit corrupts legal trace | PO-LC pattern |
| DR-15 | **Control ≠ Execution** | Control Obligation is distinct entity from Execution Obligation | Controller field on executor | ADR-UDE-003 |
| DR-16 | **Order Item ≠ Obligation** | Item is editorial/generation unit; obligation is semantic management unit | 1:1 collapse breaks multi-obligation items | ADR-UDE-003 |
| DR-17 | **Content author ≠ Record creator** | Management content ownership separate from system record creation | HR becomes implicit author | ADR-UDE-011 |
| DR-18 | **Staged Source of Truth** | Authority varies by phase: intake → editorial → ready → signed | Single SoT breaks intake path | ADR-UDE-016 |
| DR-19 | **Content confirmation gated** | Meaning-preservation acknowledgment blocks READY when content changed (OO default) | HR self-approves semantic edits | ADR-UDE-014 |
| DR-20 | **Export format ≠ domain** | PDF/DOCX are outputs; semantic model does not depend on export format | DOCX structure drives schema | OP-RES-005 |

---

## Derived Rules (from mandatory set)

| Rule | Derives from | Application |
|---|---|---|
| Item-level regeneration default | DR-02, DR-03 | Regenerate one Order Item; document-level optional |
| Fingerprint / staleness tracking | DR-03, DR-06 | Locale STALE when source semantic or effective changes |
| Immutable signed snapshot | DR-03, DR-05 | Post-SIGNED: effective text only; no silent regenerate |
| Idempotent projection | DR-13 | Same registered document → same obligation descriptors |
| Waiver requires audit | DR-06, DR-14 | BC/locale blocker bypass must be logged |
| Editorial substate not status | DR-05, DR-06 | `intake_review` derived; never replaces DRAFT enum |
| Party snapshot at sign | DR-08 | ResolvedPartySnapshot frozen at SIGNED |
| Registry version in generation | DR-12 | Same input + registry version → same generated_text |

---

## Specialization-Specific Applications

| Rule | Personnel Orders | Operational Orders |
|---|---|---|
| DR-09 Submitted-text | Optional (Model B common) | **P0 required** (Model C) |
| DR-10 Scenario optional | Item-first picker MVP | Scenario registry P2 parallel |
| DR-15 Control ≠ Execution | N/A (no control obligation) | Control meta-item standard |
| DR-16 Item ≠ Obligation | Collapsed 1:1 for MVP | Explicit 1..N required |
| DR-19 Content confirmation | Optional / HR self-approve | Default gate on content change |
| DR-17 Content author | Often HR (same as operator) | External dept head |

---

## Enforcement Points

| Phase | Rules enforced |
|---|---|
| Contract authoring (UDE-001+) | DR-01–DR-20 in contract documents |
| Draft Intake (UDE-002) | DR-04, DR-09, DR-17, DR-18 |
| Editorial Core (UDE-003) | DR-02, DR-03, DR-06, DR-11, DR-12 |
| Validation (UDE-005) | DR-06, DR-14, DR-19 |
| OO MVP (OO-IMP-001+) | DR-09, DR-17, DR-19 |
| PO Convergence (UDE-006) | All; adapters preserve PO behavior |

---

*These rules are normative for implementation. OP-RES research documents remain historical evidence; conflicts resolve in favor of UDE-000 ratified ADRs.*
