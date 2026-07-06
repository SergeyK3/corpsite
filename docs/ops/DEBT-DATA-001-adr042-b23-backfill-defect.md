# DEBT-DATA-001 — ADR-042 B2.3 Backfill Data Integrity Defect

## Status

**Registered** — 2026-07-06

Official record for **Implementation Data Debt** `DEBT-DATA-001`. **No repair authorized.**

| Field | Value |
|-------|-------|
| **Debt class** | Implementation Data Debt |
| **Debt ID** | **DEBT-DATA-001** |
| **Origin migration** | `v4w5x6y7z8a9` — [ADR-042 Phase B2.3 backfill](../adr/ADR-042-phase-b2-migration-plan.md) |
| **Architectural decision** | [WP-B4-DATA-DEBT-ARCHITECTURAL-DECISION.md](../access/WP-B4-DATA-DEBT-ARCHITECTURAL-DECISION.md) |
| **Evidence / inventory** | [WP-B4-BACKFILL-DATA-DEFECT-INVESTIGATION.md](../access/WP-B4-BACKFILL-DATA-DEFECT-INVESTIGATION.md) |
| **Planned resolution** | `OPS-031` — **not authored** (blocked) |
| **Inventory script** | `scripts/investigate_backfill_defect.py` → `scripts/backfill_defect_inventory.json` |
| **Post-repair inventory** | `scripts/backfill_defect_inventory.post-repair.json` — **not produced** |
| **Repair validation report** | [DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md](./DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md) — **not produced** |

---

## 1. Problem statement

ADR-042 Phase B2.3 idempotent backfill materialized `persons`, `person_assignments`, and `employee_assignment_links` from legacy `employees` snapshots. When `employees.position_id` was NULL, migration substituted **`position_id = 1` («Архивариус»)** via `COALESCE(e.position_id, v_fallback_pos)`.

Legacy Platform Users and Contacts were **not** repointed in the same migration. The result is a **systemic data integrity defect** affecting HR assignments, employee shells, user linkage, contacts, and future Position Cabinet resolution — **not** a Position Cabinet software defect.

Root mechanism documented in investigation §2.2; migration risk was **anticipated** in [ADR-042 B2 migration plan § Risks](../adr/ADR-042-phase-b2-migration-plan.md) (*Fallback org/position in backfill → manual correction*) but **not tracked** as registered debt until 2026-07-06.

---

## 2. Scope of defect (dev snapshot 2026-07-06)

| Class | Metric | Count |
|-------|--------|------:|
| A — `EMP-POS-NULL` | Active employees with `position_id IS NULL` | 42 |
| B — `ASG-FALLBACK-P1` | Active migration assignments on position 1 | 10 (6 prod orgs) |
| C — `EMP-ASG-DRIFT` | Active employee ↔ assignment field mismatch | 70 |
| D — `USR-EMP-ORPHAN` | Active users with `employee_id IS NULL` | 349 / 357 |
| E — `CT-PERSON-ORPHAN` | Contacts with non-existent `person_id` | 37 / 56 |
| F — `QM-CONTOUR-MISSING` | QM expert positions 93–96 absent in org 72 | 4 catalog positions |
| G — `PT-UNBOUND` | Permission templates without role/access_role | 84 / 84 |

**Canary case:** employee 12 / person 101 / `qm_hosp@corp.local` — see investigation §3.

**Scope note:** Counts include pytest fixtures; production-critical subset documented in investigation §3 (QM org 72: 4 fallback rows).

---

## 3. Impact

| Contour | Impact |
|---------|--------|
| **Position Cabinet (future)** | Cabinet resolver fails or resolves wrong contour when employee staffing incomplete or assignment on fallback pair |
| **HR / personnel UI** | «Работает» with empty position — employee shell not synced from assignment |
| **Platform Accounts** | User exists but unlinked to employee — card shows «account not created» |
| **Contacts / Telegram** | Orphan `person_id` breaks person-scoped joins |
| **Current legacy pilot** | RBAC via `users.role_id` **may still work** — defect **latent** until cabinet enforcement |

---

## 4. Owners

| Role | Responsibility |
|------|----------------|
| **Ops lead** | Repair runbook ownership; ops window; validation re-run |
| **HR / personnel policy owner** | Canonical assignment source; approve correction rules |
| **Architecture lead** | Debt class governance; confirm repair does not amend Accepted ADRs |
| **Engineering** | Execute OPS-031 when authorized — implement validation scripts only until then |

---

## 5. Status lifecycle

```text
Registered
    ↓  acceptance signatures
Accepted
    ↓  OPS-031 authored + reviewed
Repair designed
    ↓  ops window
Repair executed
    ↓  mandatory
Post-repair inventory
    ↓  mandatory
Repair validation report
    ↓  sign-off
Closed
```

| Status | Meaning |
|--------|---------|
| **Registered** | Debt officially recorded; investigation complete; **no repair** |
| **Accepted** | Ops + architecture + HR owner acknowledged; **OPS-031 design may begin** |
| **Repair designed** | OPS-031 drafted and reviewed; still **no production execution** |
| **Repair executed** | OPS-031 completed in controlled window |
| **Post-repair inventory complete** | `investigate_backfill_defect.py` re-run; snapshot saved — **not yet closed** |
| **Validation report complete** | [Repair validation report](./DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md) published; exit criteria assessed |
| **Closed** | Validation report signed off; debt closed in ops-backlog |

**Current status:** **Registered**

**Rule:** **Closed** requires **both** post-repair inventory **and** repair validation report. Inventory alone is **insufficient**.

---

## 6. Exit criteria and closure artefacts

### 6.1 Post-repair inventory (mandatory)

After OPS-031 execution, re-run on **each** repaired environment:

```bash
python scripts/investigate_backfill_defect.py
```

Save output as **`scripts/backfill_defect_inventory.post-repair.json`** (or environment-specific suffix). This artefact is **raw metrics** — not a closure decision.

### 6.2 Repair validation report (mandatory)

Publish **[DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md](./DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md)** containing at minimum:

| Section | Content |
|---------|---------|
| Environment | Target DB / date / OPS-031 execution reference |
| Baseline vs post-repair | Delta against [investigation](../access/WP-B4-BACKFILL-DATA-DEFECT-INVESTIGATION.md) / pre-repair inventory |
| Exit criteria table | Per-row pass/fail (production scope) |
| Residual defects | Any class A–G still open — **must be empty for prod scope to close** |
| **Regression assessment** | Collateral damage check — existing cabinets, linkages, RBAC, resolver, migration invariants (**must Pass**) |
| Canary cases | QM pilot accounts (incl. Seitkazina / `qm_hosp@corp.local`) — explicit pass/fail |
| Sign-off | Ops lead + architecture lead + HR owner |

**Closure is forbidden** until validation report records **Pass** on all production-scope exit criteria **and** regression assessment **Pass**.

### 6.3 Exit criteria (production scope)

| Check | Target |
|-------|--------|
| Active fallback migration assignments (`position_id=1`, prod orgs) | 0 |
| Active employees with `position_id IS NULL` (prod orgs, excl. test) | 0 |
| QM org 72 expert assignments (positions 93–96) | Populated per HR canonical |
| Pilot `qm_*@corp.local` users linked to employee | 5 / 5 |
| Orphan contacts (`person_id` → missing person) | 0 |
| Employee ↔ primary assignment position/org mismatch | 0 |

Permission template binding (class G) **MAY** remain open under OPS-030 / WP-B8 — **not** part of DEBT-DATA-001 closure unless explicitly merged in OPS-031 scope decision.

---

## 7. Blocked work

| Work | Blocked until |
|------|----------------|
| **OPS-031** repair runbook (design) | DEBT-DATA-001 → **Accepted** |
| **OPS-031** production execution | OPS-031 design reviewed + ops window approved |
| Ad-hoc SQL fixes for Seitkazina / QM only | **Forbidden** — violates unified repair principle |
| New alembic backfill migration | Architecture decision required separately |

**Not blocked by this debt:** ACCESS ratification (WP-B5+), OPS-030 **governance** preparation, legacy RBAC pilot operation.

---

## 8. Acknowledgment (registration acceptance)

| Role | Name | Date | Status |
|------|------|------|--------|
| Ops lead | | | Pending |
| Architecture lead | | | Pending |
| HR / personnel policy owner | | | Pending |

Upon all three signatures: status → **Accepted**; author may begin **OPS-031 design only**.

---

## 9. Traceability

| Link | Document |
|------|----------|
| Registration decision | [WP-B4-DATA-DEBT-ARCHITECTURAL-DECISION.md](../access/WP-B4-DATA-DEBT-ARCHITECTURAL-DECISION.md) |
| Full inventory | [WP-B4-BACKFILL-DATA-DEFECT-INVESTIGATION.md](../access/WP-B4-BACKFILL-DATA-DEFECT-INVESTIGATION.md) |
| Migration risk (pre-existing) | [ADR-042-phase-b2-migration-plan.md § Risks](../adr/ADR-042-phase-b2-migration-plan.md) |
| User linkage repair path | [ADR-044](../adr/ADR-044-r2-user-linkage-discovery.md) — Phase R2 governed linkage |
| Post-repair inventory | `scripts/backfill_defect_inventory.post-repair.json` |
| Repair validation report | [DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md](./DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md) |
| Ops backlog | [ops-backlog.md § DEBT-DATA-001](../roadmap/ops-backlog.md) |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-06 | 1.0 | Initial registration — status Registered |
| 2026-07-06 | 1.1 | Mandatory post-repair inventory + repair validation report before Closed |
| 2026-07-06 | 1.2 | Validation report must include regression assessment §6 |
