# WP-B4 — ADR-042 B2.3 Backfill Data Defect Investigation

## Status

**Complete (investigation only)** — 2026-07-06

Read-only inventory of a **systemic migration/backfill data defect** discovered during Position Cabinet diagnostics (case: Сейтказина / `qm_hosp@corp.local`). **No repair executed.** **No runtime changes.**

| Field | Value |
|-------|-------|
| Work package context | [WP-B4](./WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) — Position Cabinet contour binding |
| Trigger | Single-person diagnostic → pattern generalizes across DB |
| Primary migration | `v4w5x6y7z8a9` — ADR-042 Phase B2.3 backfill |
| Secondary migrations | `l6m7n8o9p0q1` ADR-050 Phase 2.2; `n8o9p0q1r2s3` ADR-053 Phase 2.6a |
| Inventory script | `scripts/investigate_backfill_defect.py` → `scripts/backfill_defect_inventory.json` |
| Database snapshot | `corpsite` @ 2026-07-06T10:20:17Z |

---

## 1. Executive summary

Position Cabinet diagnostics for QM_HOSP exposed **not a Position Cabinet runtime bug**, but a **cross-cutting data integrity failure** introduced (or amplified) by **ADR-042 Phase B2.3** idempotent backfill.

The defect has **four coupled layers**:

1. **Employee shell incompleteness** — `employees.position_id` (and often `date_from`, `employment_rate`) left NULL for 42/120 active employees despite migration enrollment.
2. **Fallback assignments** — B2.3 created `person_assignments` with `COALESCE(e.position_id, MIN(positions.position_id))` → **position_id = 1 («Архивариус»)** when employee snapshot lacked position; **10** active migration assignments affected (6 production orgs + 4 pytest orgs).
3. **Legacy user orphanage** — **349/357** active Platform Users have `employee_id IS NULL`; B2.3 **never backfilled** user ↔ employee linkage.
4. **Contact person_id drift** — **37/56** contacts reference `person_id` values that **do not exist** in `public.persons` (pre-migration ID namespace never repointed).

Position Cabinet infrastructure (org-unique Position, Cabinet, LPM) exists for **observed assignment pairs**, but **84/84 permission templates are unbound** (`role_id` and `access_role_id` both NULL) — a **separate governance gap** (OPS-030 / WP-B4 contour rules not applied), not caused by B2.3 alone.

**Conclusion:** Single unified **migration/backfill defect** with downstream impact on HR contour, Platform Accounts, and future Position Cabinet enforcement. **Not QM-only** — QM team is the most visible slice (4/10 fallback rows in org 72).

---

## 2. Defect description

### 2.1 Intended B2.3 behaviour

Migration `alembic/versions/v4w5x6y7z8a9_adr042_phase_b2_3_backfill.py` performs:

| Step | Action |
|------|--------|
| 1 | Materialize `persons` from unlinked `employees` |
| 2 | Link `employees.person_id` (IIN, then match_key) |
| 3 | Insert primary `person_assignments` from **legacy employee snapshot** |
| 4 | Insert `employee_assignment_links` |

Step 3 uses **employee row as sole source of truth** for assignment shape.

### 2.2 Fallback substitution (root mechanism)

```sql
-- Lines 36-45, 230-231 (v4w5x6y7z8a9)
SELECT position_id INTO v_fallback_pos
FROM public.positions
ORDER BY position_id
LIMIT 1;   -- → position_id = 1 («Архивариус»)

COALESCE(e.org_unit_id, v_fallback_org),
COALESCE(e.position_id, v_fallback_pos),
```

**Conditions triggering fallback position:**

| Condition | Effect on assignment |
|-----------|---------------------|
| `e.position_id IS NULL` | Assignment gets `position_id = 1` |
| `e.org_unit_id IS NULL` | Assignment gets first active org_unit |
| `e.date_from IS NULL` | Assignment gets `CURRENT_DATE` at migration time |
| `e.employment_rate IS NULL` | Assignment gets `1.0` |

**What B2.3 does *not* do:**

- Does **not** write assignment fields back to `employees`
- Does **not** link `users.employee_id`
- Does **not** repoint `contacts.person_id`
- Does **not** read HR canonical roster as assignment source

### 2.3 Why canonical position was not preserved

| Factor | Evidence |
|--------|----------|
| **Pre-backfill employee snapshot already incomplete** | All 42 NULL-position employees have `enrollment_source = 'migration'`; no alternate source |
| **Pilot seed position not carried forward** | Legacy seed used generic `position_id = 64` for QM rows; current DB shows NULL for QM employee ids 12–15 — position lost in intervening schema/HR evolution **before** B2.3 ran |
| **HR import updated some employees, not all** | 78 employees retain valid `position_id`; director/deputy rows align with assignments; QM/stat subset does not |
| **Fallback masks missing data** | Assignment appears “complete” (org + position + rate + date) while employee shell stays empty |
| **No post-backfill sync job** | `apply_enrollment` copies assignment → employee on **new** enrollments only; migration rows never reconciled |

**Important:** No alembic migration contains `SET position_id = NULL`. The NULL state is **input state to B2.3**, not output of B2.3.

---

## 3. Scale of defect (DB inventory)

### 3.1 Employees and assignments

| Metric | Count | Notes |
|--------|------:|-------|
| Total employees | 120 | |
| `employees.position_id IS NULL` | **42** | All `operational_status = active` |
| Active `person_assignments` | 88 | |
| Active migration assignments with **fallback pos 1** | **10** | `source = 'migration'`, `position_id = 1` |
| └ in org 72 (QM) | **4** | Сейтказина, Акилтаева, Абдина, Мусабеков |
| └ in other production orgs | **6** | stat (68), buh (75), + 4 pytest units |
| `employee_assignment_links` mismatch (any field) | **70** | Active link + active assignment |
| └ position mismatch (`emp_pos` ≠ `pa_pos`) | **10** | All `emp_pos IS NULL`, `pa_pos = 1` |
| └ date/rate mismatch only | **60** | Position/org align; employee `date_from`/`rate` NULL |
| NULL position + active assignment link | **10** | = fallback cohort |
| NULL position + **no** active link | **32** | Mostly pytest (`org_unit_id` NULL: 20) |

**Production-focused subset (exclude pytest org units):**

| Metric | Count |
|--------|------:|
| Fallback assignments (real orgs) | **6** |
| QM org 72 fallback | **4** |
| Employees NULL position in org 72 | **4** |

### 3.2 Platform Users

| Metric | Count | Notes |
|--------|------:|-------|
| Total active users | 357 | |
| `users.employee_id IS NULL` | **349** (97.8%) | Legacy pilot + test accounts |
| `users.employee_id IS NOT NULL` | **8** | Only linked accounts |
| Potential auto-match (normalized `full_name` = employee) | **34** | Unique employee not already linked to another user |
| QM pilot accounts (`qm_*@corp.local`) | **5** | **All** `employee_id IS NULL` |
| └ exact name match | **2** | `qm_head`, `qm_complaint_reg` |
| └ fuzzy mismatch (Kaz/Rus spelling) | **3** | `qm_hosp`, `qm_amb`, `qm_complaint_pat` |

**Person linkage:** `users` table has **no `person_id` column**. Person reachability for Platform User is **only** via `users.employee_id → employees.person_id`. With 349 orphan users, **Person linkage is absent for 97.8% of accounts**.

### 3.3 Contacts integrity

| Metric | Count | Notes |
|--------|------:|-------|
| Total contacts | 56 | |
| Orphan `person_id` (no matching `persons` row) | **37** (66%) | Legacy numeric IDs (e.g. 5552, 731, 6215) |
| `person_id IS NULL` | 19 | Mostly pytest |
| Name mismatch (contact vs person, where person exists) | **0** | |
| Contacts matchable to `persons` by normalized name | **37** | All already carry stale `person_id` |

Orphan contacts include **all pilot roster contacts (ids 1–30)** — systematic failure to repoint after `persons` table introduction.

### 3.4 Position Cabinet / Permission Template gaps

| Metric | Count | Notes |
|--------|------:|-------|
| Distinct active assignment staffing pairs | 84 | |
| Active assignment pairs **without** LPM | **0** | ADR-050 2.2 backfill covered observed pairs |
| LPM rows without cabinet | **0** | |
| Cabinets without template row | **0** | |
| Templates with **no** `role_id` and **no** `access_role_id` | **84/84** | Awaiting OPS-030 / contour rules |
| QM expert positions 93–96 in org 72 assignments | **0** | Not assigned — functional gap |
| LPM for `(org=72, pos=93\|94\|95\|96)` | **0** | Cabinets never created for QM expert contours |

**Org 72 active assignments today:**

| person | position_id | catalog name |
|--------|------------:|--------------|
| Масимов | 85 | Руководитель ОВЭиПД |
| Сейтказина | **1** | **Архивариус** (fallback) |
| Акилтаева | **1** | **Архивариус** (fallback) |
| Абдина | **1** | **Архивариус** (fallback) |
| Мусабеков | **1** | **Архивариус** (fallback) |

Expected QM expert catalog positions (unused in org 72):

| position_id | name |
|------------:|------|
| 93 | эксперт ОВЭиПД амбулаторный |
| 94 | эксперт ОВЭиПД госпитальный |
| 95 | эксперт ОВЭиПД по регистрации жалоб |
| 96 | эксперт ОВЭиПД по улаживанию жалоб |

---

## 4. Classification of violations

| Class | ID | Description | Affected rows (indicative) | Severity |
|-------|-----|-------------|---------------------------|----------|
| **A** | `EMP-POS-NULL` | Employee shell missing position | 42 | High |
| **B** | `ASG-FALLBACK-P1` | Migration assignment substituted position 1 | 10 active (6 prod) | **Critical** |
| **C** | `EMP-ASG-DRIFT` | Employee ≠ assignment (position/org/date/rate) | 70 linked pairs | High |
| **D** | `USR-EMP-ORPHAN` | Platform User without employee link | 349 | High |
| **E** | `CT-PERSON-ORPHAN` | Contact → non-existent Person | 37 | Medium |
| **F** | `QM-CONTOUR-MISSING` | No assignment/LPM for QM expert positions in org 72 | 4 positions × 1 org | **Critical** (future PC) |
| **G** | `PT-UNBOUND` | Permission template without role/access_role | 84 | Medium (blocked on governance) |
| **H** | `EMP-NO-PERSON` | Employee without person_id | 13 | Medium |

Classes **B + F** are the direct cause of «QM_HOSP cabinet unreachable». Classes **D + E** explain UI/account symptoms. Class **G** is orthogonal (governance), but blocks Position Cabinet permission resolution.

---

## 5. Scope: QM-only or systemic?

| Scope | Finding |
|-------|---------|
| **QM team (org 72)** | 4/5 QM staff on fallback position 1; 0/4 QM expert functional positions assigned; 5/5 pilot logins unlinked |
| **Other production units** | Fallback also in org 68 (stat), org 75 (buh) — **not QM-specific** |
| **All departments** | 60/70 mismatches are date/rate NULL drift (all migrated employees with valid position) |
| **Platform Users** | 97.8% unlinked — **global legacy gap** |
| **Contacts** | 66% orphan person_id — **global**, predates QM case |
| **Permission templates** | 100% unbound — **global**, awaiting WP-B4/OPS-030 |

**Verdict:** Fallback position defect is **small in count (10)** but **high impact**; user/contact orphanage is **large and global**. QM is the **canary**, not the **sole victim**.

---

## 6. Impact assessment

### 6.1 Position Cabinet (ADR-050 / ADR-051)

| Impact | Detail |
|--------|--------|
| Cabinet resolver | Uses `employees.org_unit_id` + `employees.position_id` → **`employee_staffing_incomplete`** when position NULL |
| Wrong cabinet | Fallback assignment resolves to **Архивариус** cabinet, not QM_HOSP contour |
| Missing cabinet | `(72, 94)` etc. have **no LPM** — resolver returns `legacy_mapping_not_found` even if assignment corrected |
| Permission template | All templates unbound — effective permissions empty in cabinet path |
| Current runtime | Legacy `users.role_id` + `access_grants` still authoritative — **defect latent** until enforcement switch |

### 6.2 HR / personnel contour

| Impact | Detail |
|--------|--------|
| Employee card UI | Shows «Работает» from `operational_status`; position/rate/date from **employee** → empty |
| Assignment truth | `person_assignments` holds data (sometimes wrong); not mirrored to employee |
| Enrollment queue | Empty — migration bypassed queue; no pending corrections |
| HR events | Future events may conflict with stale migration assignments |

### 6.3 Platform Accounts

| Impact | Detail |
|--------|--------|
| Account existence | Pilot users **exist** (`qm_hosp@corp.local` user_id=4) |
| Employee card | Shows «account not created» — lookup by `employee_id` fails |
| Login | Auth is user-based; **may work** with correct password — independent of employee link |
| Person/Cabinet access path | Requires `user → employee → person → assignment → cabinet` — **broken** |

### 6.4 Contacts / Telegram

| Impact | Detail |
|--------|--------|
| Operational contact sync | `ensure_operational_contact_for_employee` uses employee_id; pilot contacts pre-date person model |
| Orphan person_id | Contact directory joins to `persons` fail silently or show stale linkage |

---

## 7. Risk evaluation

| Risk | Likelihood | Impact | Phase |
|------|------------|--------|-------|
| Wrong permissions when Cabinet enforcement enabled | High | Critical | Post WP-B7 |
| QM tasks routed to wrong role/cabinet | Medium | High | Near-term pilot |
| HR decisions on incorrect assignment data | Medium | High | Current |
| Mass login/account provisioning failure | Low (legacy RBAC works) | Medium | Current |
| Contact/TG notification misdelivery | Medium | Medium | Current |
| Accidental partial manual fix worsens idempotency | Medium | High | During repair |

**Overall risk:** **High** for Position Cabinet programme; **Medium** for current legacy-RBAC pilot **if** repairs deferred past enforcement milestone.

---

## 8. Root cause chain (condensed)

```
[Historical employee rows: position_id NULL for subset]
        ↓
[ADR-042 B2.3 Step 3: COALESCE(position_id, 1)]
        ↓
[person_assignments with «Архивариус» + employee shell still NULL]
        ↓
[ADR-050 2.2: LPM/cabinet for wrong pair (72,1) not (72,94)]
        ↓
[Position Cabinet resolver: staffing incomplete / wrong contour]
        +
[users.employee_id never backfilled in B2.3]
        ↓
[UI: no account; PC path: no Person linkage]
        +
[contacts.person_id never remapped to new persons.* IDs]
        ↓
[Orphan contacts]
```

---

## 9. Recommended unified repair plan (proposal only — NOT authorized)

Repair should be **one governed ops package**, not ad-hoc SQL. Suggested phases:

### Phase 0 — Preconditions (read-only)

- [ ] Export `scripts/backfill_defect_inventory.json` baseline per environment
- [ ] Confirm HR canonical roster / import card as **source of truth** for position corrections
- [ ] Freeze manual user creation for affected pilot logins

### Phase 1 — Assignment correction (HR contour)

- [ ] Replace migration fallback assignments (`source='migration'`, `position_id=1`) with canonical positions from HR data
- [ ] For QM org 72: assign positions **93–96** per role mapping (not role codes on user)
- [ ] Close/supersede incorrect assignment rows; preserve history via `assignment_key` / events
- [ ] **Do not** hand-edit single person in isolation — apply rule to all **10** fallback rows (+ validate org 72 QM set)

### Phase 2 — Employee shell sync

- [ ] Sync `employees.position_id`, `date_from`, `employment_rate`, `org_unit_id` from corrected primary assignment
- [ ] Re-run mismatch query; target **0** class C position/org mismatches

### Phase 3 — Platform User linkage (ADR-044)

- [ ] Link 34 name-matched users via governed linkage operation (not raw UPDATE)
- [ ] QM pilot: include **fuzzy name** rules (Kaz/Rus orthography) for 3 remaining accounts
- [ ] Verify no duplicate `users.employee_id` violations

### Phase 4 — Contact repointing

- [ ] Map contacts 1–30 (+ others) to `persons.person_id` via normalized name + employee bridge
- [ ] Validate zero orphan `person_id` references

### Phase 5 — Position Cabinet infrastructure

- [ ] Create LPM + cabinet + template for new staffing pairs `(72, 93–96)` etc.
- [ ] Apply OPS-030 / `permission_template_contour_rule` bindings (WP-B4 governance)
- [ ] Run cabinet access shadow comparison before enforcement toggle

### Phase 6 — Post-repair inventory (mandatory)

- [ ] Re-run `scripts/investigate_backfill_defect.py` on repaired environment
- [ ] Save `scripts/backfill_defect_inventory.post-repair.json`

Raw metrics only — **does not close** DEBT-DATA-001.

### Phase 7 — Repair validation report (mandatory)

- [ ] Publish [DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md](../ops/DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md)
- [ ] Record pass/fail on production-scope exit criteria (incl. canary cases)
- [ ] Complete **regression assessment** — no collateral damage to correct pre-repair data
- [ ] Collect sign-off: ops + architecture + HR owner

| Check | Expected |
|-------|----------|
| Fallback assignments active (prod) | 0 |
| `employees.position_id IS NULL` (active, prod) | 0 |
| QM org 72 expert positions assigned | 4 |
| Pilot `qm_*` users linked | 5 |
| Orphan contacts | 0 |
| Cabinet resolver for QM_HOSP employee | `resolved: true` |
| Shadow mode parity | Documented acceptable delta |

**Close DEBT-DATA-001** only after validation report **Pass** (exit criteria + regression assessment) — not after inventory alone.

### Phase 8 — Password / pilot readiness (optional, separate approval)

- [ ] `scripts/reset_pilot_password.py --dry-run` for QM accounts **after** linkage verified

---

## 10. Explicit non-goals (this investigation)

- No `UPDATE` / `INSERT` / `DELETE` executed
- No new alembic migrations
- No ADR or architecture changes
- No Position Cabinet enforcement toggle
- No RBAC changes

---

## 11. Artefacts

| Artefact | Path |
|----------|------|
| Inventory script | `scripts/investigate_backfill_defect.py` |
| Snapshot JSON | `scripts/backfill_defect_inventory.json` |
| B2.3 migration | `alembic/versions/v4w5x6y7z8a9_adr042_phase_b2_3_backfill.py` |
| ADR-050 cabinet backfill | `alembic/versions/l6m7n8o9p0q1_adr050_phase2_2_position_cabinet_backfill.py` |
| Prior single-person diagnostic | Conversation / Seitkazina QM_HOSP case (2026-07-06) |

---

## 12. Registration and next steps

**Registered as Implementation Data Debt:** [**DEBT-DATA-001**](../ops/DEBT-DATA-001-adr042-b23-backfill-defect.md)

| Artefact | Role |
|----------|------|
| [WP-B4-DATA-DEBT-ARCHITECTURAL-DECISION.md](./WP-B4-DATA-DEBT-ARCHITECTURAL-DECISION.md) | Where/how debt is registered; repair design gate |
| [DEBT-DATA-001](../ops/DEBT-DATA-001-adr042-b23-backfill-defect.md) | Official debt record — status **Registered** |
| [DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md](../ops/DEBT-DATA-001-REPAIR-VALIDATION-REPORT.md) | Mandatory closure artefact (after repair) — **not produced** |
| This investigation | Pre-repair evidence and inventory only |

**Not Policy Debt** — do **not** add to WP-B1 §6.1 register (`DEBT-B1-*`).

**Minimum immediate action:** re-run inventory on target environment; collect **Accepted** acknowledgments on DEBT-DATA-001 (ops + architecture + HR owner). **OPS-031 repair design blocked** until Accepted.
