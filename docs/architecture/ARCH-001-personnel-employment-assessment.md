# Architecture Assessment — Personnel & Employment vs Position Cabinet Architecture

## Document metadata

| Field | Value |
|-------|-------|
| Status | **Draft — Architecture Review** |
| Date | 2026-07-03 |
| Slug | `personnel-employment` |
| Program | [ARCH-001-assessment-program.md](./ARCH-001-assessment-program.md) (queue #2) |
| Baseline | [ARCH-001 v0.5 — Position Cabinet Architecture](./ARCH-001-position-permission-model.md) |
| Prerequisite assessment | [ARCH-001-positions-org-structure-assessment.md](./ARCH-001-positions-org-structure-assessment.md) |
| Scope | Assessment only — no code, schema, API, or baseline changes |

---

## 1. Executive Summary

Corpsite has **partial infrastructure** for ARCH-001 personnel concepts: `persons`, `person_assignments`, enrollment queue, and HR lifecycle sync (ADR-042, ADR-043, ADR-048) move the model toward **Person → Employment episodes → operational Employee shell**. However, the **dominant runtime path** remains **Employee-centric**: directory CRUD, termination, auth context, documents, and user linkage anchor on `employee_id`, while Employment rows still bind to **catalog** `(org_unit_id, position_id)` rather than org-unique Position or Position Cabinet.

**Verdict:** **ARCH-001 is sufficient** for the personnel-employment domain. No new core entity is required beyond Person, **Занятие должности (Employment)**, org-unique Position, and Position Cabinet already defined in the baseline. The gap is **alignment and completion** of the ADR-042 trajectory, blocked in part by **assessment #1 findings** (org-unique Position + Cabinet do not exist yet).

**What can be assessed now:** semantic mapping of Person / Employee / `person_assignments`; lifecycle coverage; multi-assignment design intent; acting/vacancy gaps; user-centric anti-patterns; access derivation readiness at concept level.

**What is blocked until ADR-050 (Position + Cabinet schema):** Employment → Cabinet access resolver; vacancy at Position/Cabinet level; acting overlay → second Cabinet; any FK retarget from catalog `position_id` to org-unique Position.

**Personnel must not assume before Position migration:** that `person_assignments.position_id` identifies an ARCH-001 Position; that closing an Employee row implies Cabinet access semantics; that `users.role_id` can stand in for Employment or acting.

**Recommendation:** complete Person materialization (ADR-048), unify lifecycle on `person_assignments` as the **sole Employment truth**, and **after ADR-050** add `cabinet_access` derivation from active Employments + ACTING overlays. Do **not** start Cabinet access implementation on current catalog FKs.

---

## 2. AS-IS

### 2.1. Scope

| In scope | Out of scope (other queue items) |
|----------|----------------------------------|
| `persons`, `employees`, `person_assignments`, `employee_assignment_links` | Task ownership (`tasks` assessment) |
| Enrollment: `enrollment_queue`, `enrollment_history`, `apply_enrollment` | Full RBAC / `/auth/me` cabinet list (`access-rbac`) |
| HR lifecycle: `hr_personnel_change_events`, C2 assignment sync | Platform User policy detail (`platform-user-identity`) |
| Operational events: `employee_events`, `personnel_events_service` | Personal File (Person-bound exception) |
| Bridges: `users.employee_id`, `employee_documents.employee_id` | Org-unique Position schema (assessment #1) |

### 2.2. Current meaning of **Person**

**Table `public.persons`** (ADR-042 B2, ADR-048):

| Aspect | As-is |
|--------|-------|
| Purpose | Canonical identity: `match_key`, IIN, FIO, `birth_date`, `person_status` |
| Source | HR canonical sync (C2), enrollment apply, migration backfill |
| Cardinality | 1 Person → N `person_assignments`; 0..N historical `employees` over lifetime |
| UI | Person id on contacts when linked; personnel admin / reconciliation |

**Gap:** operational-first paths (legacy `create_employee`, Phase 3I before Person shell policy) still produce **`employees.person_id = NULL`** (ADR-048 production case). Person is **design anchor**, not yet **universal runtime anchor**.

Person is **not** Employee, User, Position, or Cabinet — consistent with ARCH-001 §3.1 when `person_id` is populated.

### 2.3. Current meaning of **Employee**

**Table `public.employees`** — **operational shell** (ADR-041, ADR-042, ADR-048):

| Aspect | As-is |
|--------|-------|
| Purpose | Enrolled participant in Corpsite operational registry (~pilot subset of full roster) |
| Identity | `employee_id` surrogate; optional `person_id` FK |
| Snapshot fields | `org_unit_id`, `position_id`, `employment_rate`, `date_from`, `date_to`, `is_active` — **primary assignment mirror** (deprecated as sole truth per ADR-042, still authoritative in many paths) |
| Status | `operational_status`: `draft \| active \| suspended \| terminated`; `enrollment_source` |
| Events | `employee_events` append-only (HIRE, TRANSFER, TERMINATION, …) |

**Employee answers:** «Кто участвует в operational контуре Corpsite сейчас?» — **not** «какая org-unique Position занята?» and **not** «кто этот человек навсегда?»

**Dominant API:** `/directory/employees/*` — list, create, terminate, transfer, patch (limited), personnel events — keyed by **`employee_id`**.

### 2.4. Current meaning of **`person_assignments` / bindings**

**`person_assignments`** — closest as-is entity to ARCH-001 **Занятие должности (Employment)**:

| Field | Role |
|-------|------|
| `person_id` | Who |
| `org_unit_id` + `position_id` | Where + **catalog title** (not org-unique Position — see assessment #1) |
| `employment_type` | `primary`, `part_time`, `internal_combo`, `external`, `locum` |
| `rate`, `start_date`, `end_date` | Period and FTE |
| `active_flag`, `lifecycle_status` | `active \| closed \| voided` |
| `is_primary` | Primary vs secondary concurrent assignment |
| `assignment_key` | Dedup: `{person_id}\|{org_unit_id}\|{position_id}\|{employment_type}\|{start_date}` (conceptually) |
| `source` | `canonical`, `enrollment`, `transfer`, `correction`, `migration`, `manual` |

**Bridge:** `employee_assignment_links(employee_id, assignment_id, link_status)` connects operational shell to canonical assignments on enrollment apply.

**HR truth path:** Canonical diff → `hr_personnel_change_events` → C2 `hr_person_assignment_sync_service` mutates `persons` / `person_assignments` (close/open, terminate person).

**Effective Employment fact today:** the **pair** `(org_unit_id, catalog position_id)` on an active `person_assignment` — a **proxy** until org-unique Position exists.

### 2.5. Dual registry (ADR-041)

| Registry | Volume | Role |
|----------|--------|------|
| HR Canonical | Full roster (~3000+) | Analytics, diff, `person_assignments` source |
| Operational (`employees`) | Pilot (~33) | Tasks, Telegram, UI, user linkage, documents |

Enrollment **explicitly** bridges canonical assignment → employee shell; HR import **does not** auto-create employees.

### 2.6. Platform User bridge

| Link | Mechanism |
|------|-----------|
| User → Employee | `users.employee_id` (ADR-044 linkage execute) |
| User → Person | Indirect via `employees.person_id` (often NULL) |
| Auth context | `/auth/me`: `position_id` / `position_name` from **employee snapshot**, not from active assignments union |

### 2.7. Acting, leave, vacancy (as-is)

| Scenario | As-is |
|----------|-------|
| **Acting (и.о.)** | ADR-036 `ACTING_ASSIGNMENT` — **Phase 3 deferred**; `employee_acting_assignments` **not implemented**; explicit decision: **do not change `users.role_id`** for acting MVP |
| **Leave** | ADR-036 leave events — roadmap Phase 3; no standard Employment overlay in production path |
| **Vacancy** | No Position/Cabinet entity; «vacant» = no active employee/assignment for `(unit, title)` — **implicit**, not queryable as staffing slot state |
| **locum** employment_type | Exists on `person_assignments` — temporary replacement semantics at HR level, not tied to Cabinet |

---

## 3. TO-BE under ARCH-001 (baseline unchanged)

### 3.1. Entity alignment

```text
Person (identity, durable)
   │
   ├── Занятие должности (Employment) = person_assignment episode
   │        FK → org-unique Position (post ADR-050)
   │        opens access → Position Cabinet (same period)
   │
   ├── ACTING overlay (ADR-036) → temporary access to another Cabinet
   │        without mutating primary Employment
   │
   └── Employee (operational shell) — optional convenience for enrolled ops;
            NOT owner of Cabinet; NOT substitute for Employment

Platform User → Person (auth) → effective cabinets[] from active Employments + acting
```

### 3.2. Employment (Занятие должности)

Per ARCH-001 §3.2:

- References **org-unique Position** (not global title catalog).
- Multiple concurrent active Employments allowed (совместительство).
- Opens **Position Cabinet access** for `[start_date, end_date]`; closes on `end_date` / termination / void.
- Does **not** own Cabinet contents.

### 3.3. Employee in TO-BE

- Retained as **enrollment / operational index** for pilot-scale ops UI, documents bridge, user linkage — **or** gradually demoted to read-model over Person + Employment.
- Snapshot columns **derived from primary Employment**, not authoritative.
- **Must not** be operational owner of tasks, reports, or Cabinet statistics (ARCH-001 §4.5).

### 3.4. Blocked TO-BE elements (dependency on ADR-050)

| Element | Blocked because |
|---------|-----------------|
| `employment.position_id` → org-unique Position | Catalog FK today |
| `employment → cabinet_id` resolver | No `position_cabinets` table |
| Vacancy on unoccupied Position | No org-unique Position lifecycle |
| Acting → second Cabinet without role merge | No acting access table + no Cabinet |

### 3.5. Assumptions Personnel must NOT make before Position migration

1. **`person_assignments.position_id`** equals ARCH-001 Position — it references **title catalog** only.
2. **One Employee row** equals one Employment — Employee may lag assignments or exist without full Person link.
3. **`terminate_employee`** equals «Position vacant» — it closes operational shell; Cabinet vacancy is a **Position-level** state (post ADR-050).
4. **`users.role_id`** reflects Employment or acting — Platform Role remains separate until `access-rbac` migration.
5. **Cabinet access can be computed** from `(org_unit_id, position_id, person_id)` alone — requires org-unique Position PK and Cabinet 1:1 map.
6. **Enrollment apply** can bind Cabinet IDs — no Cabinet entity to bind to yet.

---

## 4. Ownership Analysis

| Object | ARCH-001 owner | As-is effective owner / key | Gap |
|--------|----------------|------------------------------|-----|
| **Person** | Person (identity) | `persons.person_id` when materialized | Orphan employees without `person_id` |
| **Employment** | Person ↔ org-unique Position (period) | `person_assignments` → catalog position | Wrong Position semantics; dual truth with `employees` |
| **Employee** | **Not** a domain owner — operational shell | `employee_id` used as hub for UI, docs, events, user | **Overloaded** |
| **org-unique Position** | Organization | **Missing** — proxy `(org_unit_id, position_id)` | Assessment #1 |
| **Position Cabinet** | Organization (via Position) | **Missing** | ADR-050 |
| **Platform User** | Auth only | Carries `role_id`, `employee_id`, derived `position_id` in `/auth/me` | **Access carrier anti-pattern** |
| **employee_documents** | Person (professional) / Cabinet (function docs) | `employee_id` FK | Person/Cabinet split not applied |
| **employee_events** | Person / Employment (HR truth) | `employee_id` | Employee-centric journal |
| **tasks / reports** | Position Cabinet | Not via Employee (role/user path) | Tasks assessment |
| **Organization** | Org structure, staffing policy | Implicit single-tenant | OK |

**Summary:** ARCH-001 ownership model is clear. As-is **Employee** and **Platform User** absorb ownership and access semantics that TO-BE assigns to **Employment → Cabinet** and **Person (audit only)**.

---

## 5. Lifecycle Analysis

| Event | ARCH-001 TO-BE | AS-IS | Assessable now? |
|-------|----------------|-------|-----------------|
| **Hire / enroll** | Open Employment on org-unique Position → Cabinet access | Enrollment apply: assignment + link + employee shell; legacy `create_employee` **without** person/assignment | ⚠️ Partial |
| **Multiple concurrent Positions** | N active Employments → N Cabinets | **Designed:** multiple `person_assignments`; **Runtime:** employee snapshot + `/auth/me` single position | ⚠️ Partial |
| **Transfer** | Close Employment + open new on new Position | `transfer_employee` / personnel events → `employee_events` + employee snapshot; C2 closes/opens assignments when lifecycle pipeline runs | ⚠️ Partial |
| **Position change (same unit)** | Close/open Employment | `POSITION_CHANGE` personnel events; C2 handlers | ⚠️ Partial |
| **Rate change** | Append-only Employment episode | `RATE_CHANGE` / close+open in C2 | ✓ Concept OK |
| **Termination** | Close Employment(s); Cabinet persists | `terminate_employee`: `employees.is_active=false`, `users.is_active=false`; **may not** close all `person_assignments` if bypassing C2 | ⚠️ Split paths |
| **Re-hire** | Same Person, new Employment, same Cabinets | Person persists (ADR-048/047); new assignment + RE_ENROLL | ✓ Concept OK |
| **Leave** | HR event; optional access suspend policy | ADR-036 Phase 3 — **not operational** | ✗ Deferred |
| **Acting (и.о.)** | Overlay → temporary Cabinet access | ADR-036 deferred; **no** `employee_acting_assignments`; role_id workaround in ops | ✗ Not represented |
| **Vacancy** | Position + Cabinet remain; no occupant | Implicit absence of person on `(unit, title)` | ✗ Not first-class |
| **Suspend employee** | Admin ops policy | `operational_status=suspended` | ⚠️ Employee-level, not Cabinet |

### 5.1. Focus area answers (1–10)

| # | Question | Answer |
|---|----------|--------|
| 1 | Meaning of Employee | Operational enrollment shell; snapshot of primary staffing; **not** ARCH-001 Employment |
| 2 | Meaning of Person | Canonical identity; **intended** anchor; incomplete materialization |
| 3 | Meaning of bindings | `person_assignments` = Employment episodes; `(org_unit_id, catalog position_id)` proxy |
| 4 | Employment as real entity? | **Yes in schema (person_assignments)**; **Incomplete in runtime** (employee-first APIs, dual write drift) |
| 5 | Multiple Positions per Person? | **Yes in ADR-042/C2**; **Undercut** by single employee snapshot and auth single-position |
| 6 | Acting without merging roles? | **Not yet** — ADR-036 Phase 3; anti-pattern is `users.role_id` swap |
| 7 | Vacancy representable? | **Not** at Position/Cabinet level; only implicit |
| 8 | Termination / transfer / re-hire? | **Partial** — employee_events + C2; paths not unified |
| 9 | Access from active Employment? | **Partial** — resolver reads assignments but grants use ROLE/USER/POSITION catalog; **no Cabinet** |
| 10 | Employee as ops object owner? | **Yes today** for documents, events, user bridge, analytics; **incorrect** per ARCH-001 |

---

## 6. Access Analysis

### 6.1. TO-BE access chain (ARCH-001)

```text
Platform User authenticates Person
  → active Employments (+ ACTING overlays)
  → org-unique Position(s)
  → Position Cabinet(s)
  → Permission Template / effective permissions
```

### 6.2. As-is access inputs

| Mechanism | What it uses | User-centric? |
|-----------|--------------|---------------|
| `access_resolver_service` | USER, ROLE, EMPLOYEE, PERSON, **POSITION (catalog id)**, ORG_UNIT from active `person_assignments` | Mixed — assignments help but **grants not Cabinet-based** |
| `/auth/me` | `users.role_id`, `users.employee_id` → employee `position_id` | **Yes** |
| Directory RBAC | `compute_scope(user_id)` → org unit visibility | **Yes** |
| `personnel_visibility_resolver` | USER, ROLE, PERSON, POSITION, ORG_UNIT targets | **Yes** — grant targets, not Cabinet |
| Enrollment | Creates employee + links assignment; **does not** set Cabinet | N/A (no Cabinet) |
| Termination | Deactivates **user** with employee | **Yes** — conflates employment end with account |

### 6.3. Anti-patterns (explicit)

| Anti-pattern | Evidence |
|--------------|----------|
| **Employee as substitute for Person** | Legacy create employee without `person_id`; UI «Сотрудник» as primary identity; ADR-048 orphan case |
| **Employee as substitute for Employment** | Transfer/terminate on `employee_id`; snapshot fields authoritative in directory_service; reconciliation service compares employee vs primary assignment |
| **Employee as account/access carrier** | `users.employee_id`; terminate deactivates user; working contacts keyed by user |
| **`employee_id` as ownership key** | `employee_documents.employee_id`; `employee_events.employee_id`; `enrollment_queue` → employee; HR normalized records optional `employee_id`; ADR-041 operational analytics on `employees` |
| **`position_id` = generic title** | All assignment FKs → `public.positions` catalog (assessment #1) |
| **`org_unit_id + position_id` proxy for Employment** | `assignment_key`, enrollment wizard, C2 sync — composite proxy, not Position PK |
| **`role_id` proxy for Employment or access** | `/auth/me` role + employee position; pilot seed; tasks visibility; **acting workaround** per ADR-036 §RBAC explicit non-goal for MVP |

### 6.4. Can access be derived from active Employment today?

**Partially — insufficient for ARCH-001.**

- **Available:** query `person_assignments` where `active_flag=true` for `person_id` → yields org unit + catalog title ids.
- **Missing:** org-unique Position → Cabinet map; ACTING overlay table; unified Person on all users; demotion of `users.role_id` as effective ops context.
- **Blocked:** Cabinet access resolver implementation until ADR-050.

---

## 7. Gap Analysis

### 7.1. Assessable now (personnel layer only)

| ID | Gap | Severity |
|----|-----|----------|
| P1 | Employee-first API vs assignment-first truth | **High** |
| P2 | Incomplete Person materialization (`employees.person_id` NULL) | **High** |
| P3 | Dual snapshot drift (employee vs primary assignment) | **Medium** |
| P4 | Terminate path may not close assignments (non-C2) | **Medium** |
| P5 | Multi-assignment designed but UI/auth show one position | **High** |
| P6 | Acting not implemented; role swap risk | **High** |
| P7 | No Employment → Cabinet (Cabinet absent) | **Critical** (blocked) |
| P8 | Vacancy not representable | **High** (blocked on Position) |
| P9 | `locum` type exists but not wired to Cabinet/access | **Medium** |
| P10 | Legacy `create_employee` bypasses enrollment/Person | **Medium** |
| P11 | Employee owns documents/events/analytics | **Medium** |

### 7.2. Blocked until ADR-050 / Position-Cabinet schema

| ID | Gap | Dependency |
|----|-----|------------|
| B1 | Retarget Employment FK to org-unique Position | ADR-050 |
| B2 | Cabinet access resolver | `position_cabinets` + B1 |
| B3 | Vacancy = Position without active Employment | Org-unique Position lifecycle |
| B4 | Acting overlay → second Cabinet | ADR-036 implementation + B2 |
| B5 | Employment open/close drives Cabinet access only | B1, B2 |

### 7.3. ARCH-001 sufficiency

**ARCH-001 is sufficient.** Personnel-employment does not require new baseline entities. It requires:

1. Completing the **Person + Employment** story already started in ADR-042/043/048.
2. **Position migration** (assessment #1 / ADR-050) before Cabinet access.
3. **Demoting Employee** from access/ownership carrier to operational read-model.

---

## 8. Required ADR Changes

### Required

| ADR / document | Change |
|----------------|--------|
| [**ADR-050**](../adr/ADR-050-organization-position-cabinet-model.md) (**Proposed**) | Org-unique Position + Cabinet; Employment FK target |
| **ADR-042 Phase A/B** | Clarify Employee = shell only; Employment = sole staffing truth; remove dual-write as end state |
| **ADR-048** | Person materialization mandatory before user create / enrollment complete |
| **ADR-036** | ACTING_ASSIGNMENT implementation → **Cabinet overlay**, not `users.role_id`; `employee_acting_assignments` or equivalent |
| [**ADR-051**](../adr/ADR-051-cabinet-access-resolution.md) (**Proposed**) | **Employment → Cabinet access contract** (resolver inputs, acting, vacancy, multi-employment union) |

### Recommended

| ADR / document | Change |
|----------------|--------|
| **ADR-043** (C2/C3 lifecycle) | Termination/transfer must always close/open `person_assignments`; employee snapshot derived |
| **ADR-032** | Transfer semantics on Employment + org-unique Position |
| **ADR-041** | Operational analytics: distinguish Person/Employment metrics vs Employee shell counts |
| **ADR-042 B5** | `/auth/me` future: `accessible_cabinets[]` from Employment |
| **ADR-047** | Documents: Person vs employee_documents bridge during migration |

### Optional

| ADR / document | Change |
|----------------|--------|
| **ADR-045** | Enroll-from-import: pick org-unique Position when ADR-050 exists |
| **ADR-044** | User linkage: Person-first, not employee-first where possible |

---

## 9. Migration Roadmap

**No implementation in this assessment.** Phases respect **ADR-050 gate**.

### Phase E0 — Personnel semantics (no Cabinet)

1. ADR-048: enforce Person on all new enrollments; backfill orphans.
2. Single write path: personnel events / C2 → `person_assignments`; employee snapshot **derived** (reconciliation default-on).
3. Deprecate or gate legacy `create_employee` without Person + assignment.
4. Document multi-assignment UX rules (primary vs secondary) without Cabinet switcher yet.

**Do not:** bind Cabinet IDs; retarget `position_id` FK until ADR-050.

### Phase E1 — After ADR-050 (Position + Cabinet exist)

1. Migrate `person_assignments.position_id` → org-unique Position FK (mapping table from old catalog + unit).
2. Implement **Employment → Cabinet** resolver (read-only shadow mode).
3. Extend ADR-036 acting overlay to grant **temporary Cabinet access** record.

### Phase E2 — Access cutover (coordinates with queue #3)

1. `/auth/me` exposes `accessible_cabinets[]` from Employments + acting.
2. Demote `users.role_id` as operational context (keep for transition).
3. Termination: close Employments → revoke Cabinet access; **optional** user deactivate (separate policy).

### Phase E3 — Employee demotion

1. UI pivots from Employee drawer to Person + Employments list.
2. `employee_documents` → Person or Cabinet ownership split.
3. Operational analytics on Employment/Cabinet metrics.

### Phase E4 — Vacancy & acting policy

1. Vacancy visible on org-unique Position (no Employment).
2. Acting chain: LEAVE event + ACTING overlay (ADR-036).
3. Business policies for vacant Cabinet (ARCH-001 §4.7.2) — process config, not personnel schema.

---

## 10. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Implement Cabinet access on catalog FKs** | Wrong resolver forever | Block E1 until ADR-050; explicit “do not assume” list §3.5 |
| **Continue Employee-first features** | Deepens migration cost | E0 Person + assignment first; freeze new employee-owned ops |
| **Acting via `role_id` swap** | Loses primary Cabinet context (ARCH-001 §9) | ADR-036 Cabinet overlay; ops discipline until built |
| **Split terminate paths** | Assignments open after employee terminated | Unify through C2 or personnel_events only |
| **Orphan Person gap** | No Cabinet chain from User | ADR-048 enforcement |
| **Multi-assignment ignored in auth** | User sees wrong single position | Document; fix in access-rbac assessment |
| **Premature Employee removal** | Breaks pilot UI | Demote gradually (E3); keep shell during transition |
| **HR canonical vs operational drift** | Wrong enrollment targets | ADR-041 boundaries; enrollment queue unchanged |

---

## 11. Conclusion

The personnel-employment subsystem is **mid-migration** toward ARCH-001: **Person** and **`person_assignments`** provide the right **shape** for Занятие должности, but **Employee** and **Platform User** still carry access and lifecycle semantics that TO-BE assigns to **Employment → Position Cabinet**.

**ARCH-001 is sufficient** for this subsystem. Foundational work splits into:

1. **Personnel track (now):** Person completeness, assignment-first lifecycle, anti-pattern containment.
2. **Position track (ADR-050, assessment #1):** org-unique Position + Cabinet.
3. **Access track (queue #3):** resolver and `/auth/me` — **after** E1.

Do **not** force a premature Cabinet implementation plan on current FKs. The next program step after this document: **`access-rbac` assessment (#3)**, with explicit dependency on ADR-050 for Cabinet portions.

---

## Related documents

| Document | Relation |
|----------|----------|
| [ARCH-001 v0.5](./ARCH-001-position-permission-model.md) | Baseline |
| [ARCH-001-positions-org-structure-assessment.md](./ARCH-001-positions-org-structure-assessment.md) | Prerequisite; ADR-050 |
| [ARCH-001-task-subsystem-assessment.md](./ARCH-001-task-subsystem-assessment.md) | Downstream consumer |
| [ADR-042 Phase A](../adr/ADR-042-phase-a-personnel-access-enrollment-architecture.md) | Assignment model |
| [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md) | Person ownership |
| [ADR-036](../adr/ADR-036-hr-events-unified-model.md) | Acting / leave roadmap |
| [ADR-041](../adr/ADR-041-dual-personnel-registry-model.md) | Dual registry |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 1.0 | Initial assessment — personnel & employment |
