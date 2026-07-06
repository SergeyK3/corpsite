# WP-B4 — Architectural Decision: ADR-042 B2.3 Backfill Data Defect Registration

## Status

**Accepted (architecture)** — 2026-07-06

Architectural decision on **how** to register the systemic data defect discovered during Position Cabinet investigation. **Does not authorize data repair.** **Does not amend Accepted ADRs.**

| Field | Value |
|-------|-------|
| Context WP | [WP-B4](./WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) — Position Cabinet contour binding |
| Evidence | [WP-B4-BACKFILL-DATA-DEFECT-INVESTIGATION.md](./WP-B4-BACKFILL-DATA-DEFECT-INVESTIGATION.md) |
| Official registration | [DEBT-DATA-001](../ops/DEBT-DATA-001-adr042-b23-backfill-defect.md) |
| Related Accepted ADR | [ADR-042 Phase B2 migration plan](../adr/ADR-042-phase-b2-migration-plan.md) — fallback risk already noted |

---

## 1. Decision summary

| Question | Decision |
|----------|----------|
| Is this a Position Cabinet defect? | **No** — root cause is **ADR-042 Phase B2.3 migration/backfill data state** |
| Is this Policy Debt (`DEBT-B1-*` / `DEBT-B4-*`)? | **No** — no deferred **organizational policy** decision; see §2 |
| Official debt class | **Implementation Data Debt** |
| Official identifier | **`DEBT-DATA-001`** |
| Primary registration document | **`docs/ops/DEBT-DATA-001-adr042-b23-backfill-defect.md`** |
| Repair package | **Blocked** until DEBT-DATA-001 status → **Accepted**; then separate OPS runbook only |

---

## 2. Rationale — why not Policy Debt

Per [GOVERNANCE-WORK-PACKAGE-LIFECYCLE](./GOVERNANCE-WORK-PACKAGE-LIFECYCLE.md) §4.4, **Policy Debt** is:

> explicit deferral of a **named organizational decision** to a future governance work package

| Criterion | DEBT-B1-001 / DEBT-B1-004 (policy debt) | ADR-042 B2.3 data defect |
|-----------|-------------------------------------------|---------------------------|
| Nature | Missing ratified `access_roles.code`, PD class mapping | Incorrect **production data** after migration |
| Resolution path | WP-B8 Review Board / ACCESS-001 | Ops data repair + HR canonical correction |
| Review Board authority | Yes | **No** — not a policy ratification subject |
| Blocks OPS-030 by itself? | Indirectly (governance gate) | **No** — orthogonal; blocks **Position Cabinet enforcement readiness** |
| Register location | WP-B1 §6.1 policy debt register | **Implementation Data Debt register (ops layer)** |

Recording this item in the **policy debt register** would violate §4.4 (*policy debt SHALL NOT authorize implementation*) and blur governance vs ops boundaries.

**Rejected identifier:** `DEBT-B4-DATA-001` — implies Track B **policy** debt; use **`DEBT-DATA-001`** instead (program-wide implementation data debt namespace).

---

## 3. Rationale — why not ADR-042 amendment

| Option | Verdict |
|--------|---------|
| Amend [ADR-042 Phase A](../adr/ADR-042-phase-a-personnel-access-enrollment-architecture.md) | **Rejected** — architecture is **Accepted**; B2.3 fallback behaviour was **documented** in [migration plan § Risks](../adr/ADR-042-phase-b2-migration-plan.md) |
| Amend B2.3 migration revision | **Rejected for registration** — describes **historical** migration; repair is **forward ops**, not retroactive ADR change |
| Cross-reference only | **Accepted** — migration plan risk row remains; DEBT-DATA-001 links to it |

An ADR amendment is required only if we change **architectural contract** (e.g. forbid fallback without canonical source). That is **out of scope** for this debt registration.

---

## 4. Official registration model

### 4.1 Document hierarchy

```text
[Evidence — read-only inventory]
  WP-B4-BACKFILL-DATA-DEFECT-INVESTIGATION.md
        ↓ cites
[Normative registration — THIS DECISION]
  WP-B4-DATA-DEBT-ARCHITECTURAL-DECISION.md
        ↓ registers
[Authoritative debt record]
  docs/ops/DEBT-DATA-001-adr042-b23-backfill-defect.md
        ↓ indexed in
[Program tracking]
  docs/roadmap/ops-backlog.md  (summary row)
        ↓ unblocks (later)
[Repair design — NOT YET AUTHORIZED]
  docs/ops/OPS-031-adr042-backfill-data-repair.md  (placeholder — Blocked)
        ↓ after execution
[Post-repair inventory — mandatory]
  scripts/backfill_defect_inventory.post-repair.json
        ↓ mandatory
[Repair validation report — mandatory]
  docs/ops/DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md
        ↓ sign-off
Close DEBT-DATA-001
```

### 4.2 What each artefact owns

| Artefact | Role | Mutability |
|----------|------|------------|
| Investigation report | Metrics, classification, impact analysis | Updated only by re-inventory |
| **Architectural decision (this doc)** | **Where** and **how** debt is registered; gates | Stable unless registration model changes |
| **DEBT-DATA-001** | Official debt record: scope, owners, status, exit criteria | Updated at acceptance / closure |
| ops-backlog | Discoverability; priority; blocked-by links | Admin sync |
| OPS-031 (future) | Unified repair runbook: phases, SQL, rollback | Created **after** DEBT-DATA-001 **Accepted** |
| Post-repair inventory | Raw metrics JSON after execution | One file per repaired environment |
| **Repair validation report** | Pass/fail interpretation, regression assessment, sign-off | **Mandatory before Closed** |

### 4.3 What is explicitly NOT the register

| Location | Why excluded |
|----------|--------------|
| WP-B1 §6.1 policy debt register | Wrong debt class |
| WP-B4 Closure Report § Policy debt | WP-B4 policy debts (**DEBT-B1-004**) remain separate; DATA-001 referenced under **implementation blockers** only |
| Review Board Session Record | No policy decision required |
| Accepted ADR body text | No architectural contract change |

---

## 5. Debt identifier and namespace

### 5.1 Identifier

**`DEBT-DATA-001`** — *ADR-042 B2.3 backfill assignment / linkage / contact integrity defect*

Future implementation data debts: **`DEBT-DATA-{nnn}`** — orthogonal to **`DEBT-B{track}-{nnn}`** (policy) and **`OQ-{WP}-{nnn}`** (open questions).

### 5.2 Minimum fields (per registration doc)

| Field | Value |
|-------|-------|
| **Class** | Implementation Data Debt |
| **Origin** | Alembic `v4w5x6y7z8a9` — ADR-042 Phase B2.3 |
| **Discovery** | WP-B4 Position Cabinet diagnostic → systemic investigation 2026-07-06 |
| **Owner (repair)** | Ops lead + HR ops (joint) |
| **Owner (architecture)** | Architecture lead |
| **Resolution artefact** | OPS-031 (to be authored) |
| **Blocks** | Position Cabinet enforcement readiness; ADR-044 linkage completeness; HR card truthfulness |
| **Does not block** | Legacy RBAC pilot; OPS-030 governance gate (ACCESS-001 Approved) |

---

## 6. Acceptance authority (registration gate)

DEBT-DATA-001 moves from **Registered** → **Accepted** by **ops + architecture acknowledgment** — **not** Review Board ratification.

| Role | Acknowledgment |
|------|----------------|
| **Ops lead** | Confirms inventory scope and ops ownership |
| **Architecture lead** | Confirms debt class, document hierarchy, no ADR amendment required |
| **HR / personnel policy owner** | Confirms HR canonical source will govern assignment correction (not raw SQL guesswork) |

Until **Accepted**: **no repair design**, **no production UPDATE**, **no new backfill migration**.

---

## 7. Gate — repair package design

| Stage | Status | Artefact |
|-------|--------|----------|
| Investigation | ☑ Complete | [Investigation report](./WP-B4-BACKFILL-DATA-DEFECT-INVESTIGATION.md) |
| Architectural decision | ☑ Complete | This document |
| Official registration | ☑ Published | [DEBT-DATA-001](../ops/DEBT-DATA-001-adr042-b23-backfill-defect.md) — status **Registered** |
| Registration acceptance | ☐ Pending | Signatures on DEBT-DATA-001 |
| Unified repair **design** | **Blocked** | OPS-031 — **do not author until Accepted** |
| Unified repair **execution** | **Blocked** | OPS-031 — after design review + ops window |
| **Post-repair inventory** | **Blocked** | `backfill_defect_inventory.post-repair.json` — after execution |
| **Repair validation report** | **Blocked** | [DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md](../ops/DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md) — after inventory |
| **Close DEBT-DATA-001** | **Blocked** | Validation report **Pass** + sign-off — inventory alone insufficient |

**Repair package SHALL include (design scope only — future OPS-031):**

1. Assignment correction from HR canonical source  
2. Employee shell sync  
3. Platform User linkage (ADR-044 governed paths)  
4. Contact `person_id` repointing  
5. Position Cabinet contour creation for missing pairs  
6. Validation gate reusing investigation SQL (feeds **post-repair inventory**, not closure by itself)  
7. **Repair validation report** template and sign-off workflow  

**Repair package SHALL NOT be merged with:** OPS-030 contour binding, WP-B8 policy code ratification, or Position Cabinet enforcement toggle.

**Closure rule:** Execution → post-repair inventory → repair validation report (exit criteria + **regression assessment**) → **Closed**. Skipping the validation report or regression section is **forbidden**.

---

## 8. Relationship to WP-B4 policy work

| Layer | Item | Interaction |
|-------|------|-------------|
| **Policy (WP-B4)** | DEBT-B1-004 → WP-B8 | Independent — transitional code for PD-5.3 |
| **Data (ops)** | DEBT-DATA-001 | Must be resolved **before** Position Cabinet pilot accounts reflect real contours |
| **Investigation trigger** | Seitkazina / QM_HOSP | Canary case for DEBT-DATA-001 — not separate debt ID |

WP-B4 Session 1 **does not** close DEBT-DATA-001. Closure Report **MAY** reference it under *Related implementation blockers* without listing it as policy debt.

---

## 9. Explicit non-authorizations

This architectural decision **does not**:

- Authorize data UPDATE, INSERT, DELETE, or new alembic migrations  
- Amend Accepted ADR-042, ADR-050, ADR-051, ADR-053  
- Close or open Policy Debt items  
- Promote ACCESS-001 or unblock OPS-030  
- Design OPS-031 repair steps (deferred to post-Acceptance)  

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-06 | 1.0 | Initial architectural decision — DEBT-DATA-001 registration model |
| 2026-07-06 | 1.1 | Mandatory repair validation report between post-repair inventory and Closed |
| 2026-07-06 | 1.2 | Validation report must include regression assessment |
