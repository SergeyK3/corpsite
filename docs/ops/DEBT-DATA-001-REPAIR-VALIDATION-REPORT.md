# DEBT-DATA-001 — Repair Validation Report

## Status

**Not produced** — repair not executed.

| Field | Value |
|-------|-------|
| **Debt ID** | DEBT-DATA-001 |
| **Prerequisite** | OPS-031 execution complete |
| **Input** | Post-repair inventory (`scripts/backfill_defect_inventory.post-repair.json`) |
| **Registration** | [DEBT-DATA-001-adr042-b23-backfill-defect.md](./DEBT-DATA-001-adr042-b23-backfill-defect.md) §6 |

---

## Purpose

This report is the **mandatory closure artefact** between post-repair inventory and **Closed** status. It interprets inventory metrics, records pass/fail against exit criteria, and collects sign-off — **not** a duplicate of raw JSON.

**Do not publish until:** OPS-031 executed + post-repair inventory saved.

---

## Template (to complete after repair)

### 1. Environment

| Field | Value |
|-------|-------|
| Database | |
| OPS-031 execution date | |
| Operator | |

### 2. Baseline vs post-repair

| Metric | Pre-repair | Post-repair | Delta |
|--------|----------:|------------:|------:|
| `employees_position_null` (prod) | | | |
| `assignments_active_fallback_pos1` (prod) | | | |
| `employee_assignment_mismatch` | | | |
| `users_employee_id_null_active` (pilot scope) | | | |
| `contacts_orphan_person` | | | |

### 3. Exit criteria (production scope)

| Check | Target | Result | Pass |
|-------|--------|--------|:----:|
| Fallback assignments (prod) | 0 | | ☐ |
| NULL `employees.position_id` (prod) | 0 | | ☐ |
| QM org 72 positions 93–96 | Per HR canonical | | ☐ |
| Pilot `qm_*` linked | 5 / 5 | | ☐ |
| Orphan contacts | 0 | | ☐ |
| Employee ↔ assignment mismatch | 0 | | ☐ |

### 4. Canary cases

| Case | Expected | Result | Pass |
|------|----------|--------|:----:|
| Сейтказина / employee 12 / `qm_hosp@corp.local` | Linked; correct assignment; cabinet resolvable | | ☐ |

### 5. Residual defects

_List any open items. Production-scope closure requires **none**._

### 6. Regression assessment

Confirm repair did **not** damage data that was already correct before OPS-031. All items **must pass** for closure.

| Check | Verified |
|-------|:--------:|
| Existing correct Position Cabinets not damaged | ☐ |
| Existing Platform Users retained linkage (`users.employee_id` unchanged for pre-linked accounts) | ☐ |
| Legacy RBAC continues to work (pilot logins, role-based task visibility spot-check) | ☐ |
| Position Cabinet resolver unchanged for already-correct records (no regression on pre-repair `resolved: true` pairs) | ☐ |
| Migration invariants preserved (`person_assignments` ↔ `employee_assignment_links`; no duplicate primary assignments; `persons.match_key` integrity) | ☐ |

**Notes / evidence:** _SQL queries, spot-check accounts, resolver sample set, or shadow comparison reference._

**Regression verdict:** ☐ Pass — no collateral damage | ☐ Fail — stop; do not close DEBT-DATA-001

### 7. Verdict

| Verdict | ☐ Pass — recommend Close DEBT-DATA-001 | ☐ Fail — repair incomplete |
|---------|----------------------------------------|----------------------------|

_Overall Pass requires: §3 exit criteria Pass + §5 no prod residual defects + §6 regression Pass._

### 8. Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Ops lead | | | Pending |
| Architecture lead | | | Pending |
| HR / personnel policy owner | | | Pending |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-06 | 0.1 | Placeholder — template only; repair not executed |
| 2026-07-06 | 0.2 | Mandatory §6 Regression assessment added |
