# UDE-006 — ADR Addendum

WP: **UDE-006** (supporting artifact)  
Date: **2026-07-12**  
Status: **Proposed — for UDE-000 ratification track**

---

## ADR-UDE-017 — Compatibility Adapter before Persistence Migration

| Field | Content |
|---|---|
| **Question** | Must shared UDE persistence unify before adapters? |
| **Recommendation** | **Yes — adapters first.** PO persistence remains authoritative; shared views via read adapters. |
| **Alternatives** | Direct schema migration; big-bang shared tables |
| **Consequences** | Dual model period; adapter maintenance until Phase F |
| **Evidence** | PO production MVP; UDE-005 gap analysis; no migration need proven |

---

## ADR-UDE-018 — Controlled Dual Model Period

| Field | Content |
|---|---|
| **Question** | Is PO-legacy + OO-shared coexistence acceptable? |
| **Recommendation** | **Yes — expected controlled stage**, not debt by default. |
| **Alternatives** | Force unified persistence before OO; block OO until PO converged |
| **Consequences** | Reporting uses adapters; two persistence shapes temporarily |
| **Evidence** | UDE-004 PO early-creation vs OO full path |

---

## ADR-UDE-019 — Legacy Effective Text as Authority

| Field | Content |
|---|---|
| **Question** | What is SoT for legacy PO locale text? |
| **Recommendation** | **Existing effective text is authority.** No silent regeneration on read. |
| **Alternatives** | Regenerate from semantic model; infer from generated only |
| **Consequences** | Adapters may lack fingerprint; STALE flags preserved as stored |
| **Evidence** | PO-EDIT-002; production editorial behavior |

---

## ADR-UDE-020 — Personnel Event Subject vs Party Reference (F-003)

| Field | Content |
|---|---|
| **Question** | How reconcile employee_id with role-first PartyReference? |
| **Recommendation** | **Event Subject ≠ Responsible Party.** PO stores authoritative `employee_id`; adapter projects `PartyReference(type=PERSON, ref=employee_id)`. Role-first applies to operational obligations, not personnel event subjects. |
| **Alternatives** | Replace employee_id with PartyReference in DB; ignore PartyReference for PO |
| **Consequences** | Dual representation: persistence vs contract view; historical employee snapshot separate |
| **Evidence** | UDE-001 T010; PO item model; OP-RES-004 party model |

---

## ADR-UDE-021 — No Historical Audit Fabrication

| Field | Content |
|---|---|
| **Question** | May migration backfill DOCUMENT_ACTIVATED / mark_ready audit? |
| **Recommendation** | **No fabrication without evidence.** Synthetic activation is derived metadata only. |
| **Alternatives** | Mass backfill audit rows; assume all DRAFT were activated |
| **Consequences** | Audit stream has gaps for legacy; forward-only enrichment on convergence |
| **Evidence** | Missing mark_ready/register audit in PO; legal audit integrity |

---

## ADR-UDE-022 — Operational Orders Independent of Full PO Convergence

| Field | Content |
|---|---|
| **Question** | Must PO fully converge before OO MVP? |
| **Recommendation** | **No.** OO uses native shared-core path (Phase D). PO remains legacy-backed. |
| **Alternatives** | Sequential PO-first migration; shared persistence gate |
| **Consequences** | Parallel development; harness validates PO unchanged |
| **Evidence** | UDE-005 conclusion; OO-IMP roadmap |

---

## ADR-UDE-023 — Characterization Tests before Extraction

| Field | Content |
|---|---|
| **Question** | When must characterization tests exist? |
| **Recommendation** | **Before any extraction or write-path convergence** (UDE-007 minimum P0). |
| **Alternatives** | Test after refactor; manual QA only |
| **Consequences** | UDE-007 is first code WP; CI gate on existing tests |
| **Evidence** | R001 accidental behavior change; existing partial test suite |

---

## ADR-UDE-024 — Incremental Shared Runtime Adoption

| Field | Content |
|---|---|
| **Question** | How introduce shared runtime? |
| **Recommendation** | **Contracts → read adapters → OO native → optional PO convergence.** No big-bang. |
| **Alternatives** | Direct extraction; rewrite PO services first |
| **Consequences** | Phased flags; rollback per phase |
| **Evidence** | UDE-006 phases A–F; Preserve behavior first principle |

---

## Ratification Status

| ADR | Status |
|---|---|
| ADR-UDE-017 | Proposed |
| ADR-UDE-018 | Proposed |
| ADR-UDE-019 | Proposed |
| ADR-UDE-020 | Proposed |
| ADR-UDE-021 | Proposed |
| ADR-UDE-022 | Proposed |
| ADR-UDE-023 | Proposed |
| ADR-UDE-024 | Proposed |

Add to `docs/operational-orders/architecture/OP-RES-006-adr-backlog.md` in future ratification WP.
