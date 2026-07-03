# Architecture Assessment — Positions & Org Structure vs Position Cabinet Architecture

## Document metadata

| Field | Value |
|-------|-------|
| Status | **Draft — Architecture Review** |
| Date | 2026-07-03 |
| Slug | `positions-org-structure` |
| Program | [ARCH-001-assessment-program.md](./ARCH-001-assessment-program.md) (queue #1) |
| Baseline | [ARCH-001 v0.5 — Position Cabinet Architecture](./ARCH-001-position-permission-model.md) |
| Scope | Assessment only — no code, schema, API, or baseline changes |

---

## 1. Executive Summary

The Positions & Org Structure subsystem provides a **working org-unit hierarchy** and a **global job-title catalog**, but it does **not** implement ARCH-001 **org-unique Position** or **1:1 Position Cabinet**. Today, `public.positions` is a **generic title dictionary** (`name` + `category`); org context lives only on **employee/assignment rows** (`employees.org_unit_id`, `person_assignments.org_unit_id`), not on the Position entity itself.

**Verdict:** **ARCH-001 is sufficient** as the target model for this subsystem — no new architectural entity beyond Position, Position Cabinet, and Organization is required. However, the **current implementation is not compatible** with ARCH-001 without a **foundational schema and semantic migration**. The gap is **structural**, not conceptual.

**Critical blockers for Cabinet implementation:**

| ARCH-001 requirement | As-is support |
|---------------------|---------------|
| Org-unique Position (e.g. «Ординатор 2, Хирургия 1») | ✗ — one `position_id` per title string globally |
| 1:1 Position ↔ Position Cabinet | ✗ — no `position_cabinets` entity |
| Position lifecycle (incl. liquidation, vacancy as cabinet state) | ✗ — only CRUD on title catalog; delete blocked by employee FK |
| Multiple identical titles as separate Positions | ✗ — global `lower(name)` uniqueness |
| Employment → Cabinet access resolver | ✗ — `person_assignments` keys `(org_unit_id, position_id)` to **title catalog**, not org-unique Position |
| Role ≠ Position | ⚠️ — ADR-031 separates them in docs; runtime conflates via `users.role_id`, pilot `employee_id = roles.code` |

**Recommendation:** treat Positions & Org Structure as **Tier-1 foundation migration** before Personnel, Access, or Task cabinet binding. Implement org-unique Position + simultaneous Cabinet creation (ARCH-001 §4.2, §6.1); do not attempt to “stretch” the current `public.positions` catalog into org-unique semantics without schema change.

---

## 2. AS-IS

### 2.1. Scope of this subsystem

| In scope | Primary artifacts |
|----------|-------------------|
| Position catalog | `public.positions`, `GET/POST/PUT/DELETE /directory/positions` |
| Org unit tree | `public.org_units`, `org_unit_groups`, `org_unit_group_units`, `/directory/org-units/*` |
| Org classification | `org_units.group_id`, `app/medical_org_groups.py`, `deps_group` (personnel visibility) |
| Employment binding (partial) | `employees.position_id` + `employees.org_unit_id`, `person_assignments` (ADR-042 B2) |
| Legacy parallel structures | `public.departments`, `org_unit_managers` (user-based heads) |
| Future design only | ADR-046 `org_unit_allowed_positions` (proposed, not implemented) |

**Out of scope for this subsystem (assessed separately):** `public.roles`, `users.role_id`, task routing, `/auth/me` (queue #3–#4).

### 2.2. Data model — positions

**Table `public.positions`** (baseline + migration `f8c2a91b4e10`):

| Column | Semantics |
|--------|-----------|
| `position_id` | Surrogate PK |
| `name` | **Global job title string** (e.g. «Заведующий гинекологическим отделением») |
| `category` | `leaders \| medical \| admin \| technical \| other` |

**Not present:** `org_unit_id`, slot index, staffing unit code, lifecycle status, cabinet FK, effective dates.

**Uniqueness rule** (`positions_routes.py`): `lower(name)` must be unique globally on create/update. Two «Ординатор» in different departments **cannot** exist as separate catalog rows with the same normalized name.

**Org filter on list API:** `GET /positions?org_unit_id=N` returns titles where **EXISTS** `employees` with `(org_unit_id, position_id)` — i.e. **“used in unit”**, not “defined for unit” (ADR-046).

### 2.3. Data model — org structure

**Table `public.org_units`:**

| Column | Semantics |
|--------|-----------|
| `unit_id` | PK |
| `parent_unit_id` | Tree hierarchy |
| `name`, `code` | Unit identity |
| `group_id` | Top-level classification (1=clinical, 2=paraclinical, 3=admin-houshold) via `medical_org_groups.py` |
| `is_active` | Soft active flag |

**Supporting structures:**

- `org_unit_groups` + `org_unit_group_units` — cross-cutting unit grouping (deputy user on group).
- `deps_group` — department-group scope for personnel visibility grants (ADR-042 E1).
- `org_unit_managers` — `(unit_id, user_id, manager_type)` — **Platform User** as head, not Position.

**Legacy:** `public.departments` still referenced from older employee paths; operational truth is **`org_units`** (ADR-031, ADR-032).

### 2.4. Employment binding (as-is)

Two parallel paths attach people to `(org_unit, title)`:

```text
person_assignments(person_id, org_unit_id, position_id, …)   ← ADR-042 canonical employment
employees(org_unit_id, position_id, …)                         ← operational shell
```

Both reference **`position_id` → global title catalog**, not an org-unique Position row. The **pair** `(org_unit_id, position_id)` is the effective staffing fact, but it is **not** a first-class Position entity — it is a composite on Employment/Employee.

`person_assignments.assignment_key` encodes person + org + position + dates — still keyed to catalog `position_id`.

### 2.5. API and UI behaviour

| Endpoint / UI | Behaviour |
|---------------|-----------|
| `GET /directory/positions` | Global catalog; optional filter = titles **used** by employees in org scope |
| `POST /directory/positions` | Creates global title; privileged only |
| `DELETE /directory/positions/{id}` | Allowed only if **no** `employees.position_id` references |
| `GET /directory/org-units/tree` | Hierarchy with RBAC scope from **user** dept visibility |
| Enrollment Wizard | Scoped positions → fallback to global catalog (ADR-046 Phase 3I) |
| Contacts UI slots | `PositionSlot { position_id, name }` from title list — **no org_unit** on slot |

### 2.6. Sync and data quality

- **POSITIONS_SYNC_RUNBOOK** (ADR-014): syncs **title catalog** local→VPS; explicitly excludes employees/org_units; documents VPS case where **one** `position_id=64` renamed while **six employees** in different semantic roles share it — classic **title-catalog vs staffing** mismatch.
- **ADR-046 normalization audit:** duplicate titles («Зам по адм вопросам» vs «Заместитель по адм. вопросам») as separate `position_id` values — evidence that global name catalog ≠ organizational staffing table.

### 2.7. Anti-patterns already documented

| Pattern | Where |
|---------|-------|
| Position = generic job title | ADR-031 (intended separation), ARCH-001 §1.1, §5.4 |
| Role used as position substitute | Pilot seed `employee_id = roles.code`; OPS-029 «Роль Corpsite» vs должность |
| org_unit + role as position proxy | Task team scope, working contacts (`users.unit_id` + role), `org_unit_managers.user_id` |
| User owns org structure edges | `org_unit_managers.user_id`, group `deputy_user_id`, RBAC scope from `users.unit_id` |

### 2.8. Dependencies

| Consumer | Uses positions/org as |
|----------|----------------------|
| `person_assignments` / `employees` | FK to title catalog + org_unit |
| `access_resolver_service` | Collects `POSITION` subject IDs from assignment `position_id` (catalog) |
| `personnel_visibility_resolver` | `target_position_id` on grants |
| HR import / roster promotion | `_get_or_create_position_id(name)` — creates global titles |
| Tasks (team position filter) | `employees.position_id` via `users.role_id` match — **role proxy** |
| Contacts | Title slots without org binding |

---

## 3. TO-BE (per ARCH-001 — baseline unchanged)

### 3.1. Position (org-unique staffing unit)

Per ARCH-001 §3.3, §6:

- **Position** = unique organizational slot in structure: **title + org context + disambiguation** (e.g. «Ординатор 2», «Хирургия 1»).
- **Not** a reusable global string shared across all units.
- **Slot entity not required** if org-unique Position already distinguishes «Ординатор 1» vs «Ординатор 2» in the same department.

Implied attributes (conceptual — not prescribing schema here):

| Attribute | Purpose |
|-----------|---------|
| Org unit (or parent structure node) | Where the slot lives |
| Title / name | Human-readable function name |
| Disambiguator | Distinguish N identical titles in same unit |
| Lifecycle status | Active / vacant / liquidated |
| Organization | Owns staffing table as HR/org policy |

### 3.2. Position Cabinet (1:1)

Per ARCH-001 §3.4, §4.2, §6.1:

- Created **simultaneously** with Position.
- **Same lifecycle** as Position (survives vacancy; ends on position liquidation).
- Holds Permission Template and future operational objects (tasks, stats, etc.).

### 3.3. Org structure role

| Layer | TO-BE role |
|-------|------------|
| **Organization** | Owns org structure definition and staffing table |
| **Org units** | Anchor Position to structure; hierarchy for roll-up and filters |
| **Org groups** | Classification (clinical / paraclinical / admin) — unchanged conceptually |
| **Global title taxonomy** (optional) | May remain as **reference vocabulary** for naming Position rows — **not** the Position itself |

### 3.4. Employment binding (future)

Per ARCH-001 §3.2, §4.3:

- **Занятие должности (Employment)** references **org-unique Position** (not bare title catalog).
- Active employment opens access to **Position Cabinet** of that Position.
- `(org_unit_id, position_catalog_id)` composite **replaced by** `position_id` → org-unique Position (which already embeds org context).

### 3.5. Cabinet access resolver (future)

Resolver input chain (ARCH-001 §8, §10):

```text
Platform User → Person → active Employments (+ ACTING overlays)
    → org-unique Position → Position Cabinet → Permission Template
```

Current `access_resolver_service` POSITION subject IDs must map to **org-unique Position**, then to Cabinet — not to global title `position_id`.

### 3.6. ADR-046 evolution under ARCH-001

`org_unit_allowed_positions` (proposed) defines **which Position rows exist / are allowed** in a unit — closer to **staffing table** than today’s “used titles” filter. Under ARCH-001, allowed rows should reference **org-unique Position** (or define them), each with a Cabinet.

---

## 4. Ownership Analysis

| Object | Owner (ARCH-001) | As-is owner / binding | Gap |
|--------|------------------|----------------------|-----|
| **Organization** | Org structure, staffing policy | Implicit (single tenant); org_units maintained by privileged users | OK at concept level |
| **Org unit** | Organization | `org_units` — no Position children as first-class rows | Positions not anchored to units |
| **Position (target)** | Organization (HR staffing fact) | **Misplaced:** global `positions.name` catalog | **Critical** — wrong entity |
| **Position Cabinet** | Organization (via Position) | **Does not exist** | **Critical** |
| **Title catalog entry** | Organization (reference data) | `public.positions` — conflated with Position | Semantic overload |
| **Employment / assignment** | Person ↔ Position (period) | `person_assignments`, `employees` → catalog `position_id` + `org_unit_id` | Composite proxy, not Position FK |
| **Vacant slot state** | Position / Cabinet persists | Only `employees.is_active` / assignment `active_flag` | Vacancy not on Position |
| **Org unit manager (head)** | Should be Position-based or Cabinet | `org_unit_managers.user_id` | **User-centric** |
| **Platform User** | Auth only | Used as unit head, RBAC scope anchor | **Mismatch** |
| **Person** | Identity; not owner of Position | Correctly not owner of catalog | OK |
| **Role (`public.roles`)** | Permission Template inside Cabinet | Separate catalog; conflated in pilot/runtime | Assessed in `access-rbac` queue |

**Summary:** Organization owns structure and staffing; **Position** is the atomic staffing unit; **Cabinet** is its operational container. As-is **`public.positions` is a shared dictionary**, owned conceptually by Organization but **used as if it were Position** — the core semantic error.

---

## 5. Lifecycle Analysis

| Event | ARCH-001 TO-BE | AS-IS behaviour | Compatible? |
|-------|----------------|-----------------|-------------|
| **Create Position** | Create org-unique Position + Cabinet together | `POST /positions` adds global title; no Cabinet; no org_unit | ✗ |
| **Change Position metadata** | Rename/reclassify staffing unit; Cabinet persists | `PUT /positions` mutates global title — **affects all units** sharing `position_id` | ✗ |
| **Hire / open Employment** | Person gets access to existing Cabinet | Create/update `employees` / `person_assignments` with `(org_unit_id, position_id)` | ⚠️ Partial — binds person to title+unit, not Cabinet |
| **Termination** | Close employment; Cabinet + Position persist | Close employee/assignment; title row unchanged | ⚠️ Vacancy not modeled on Position |
| **Leave / sick leave** | Employment policy; Cabinet persists | No Position-level state; optional person access policy (not implemented) | ⚠️ |
| **Acting (и.о.)** | Temporary access to **another** Cabinet (ADR-036) | No Position-level acting; overlay not on org-unique Position | ✗ |
| **Vacancy** | Normal state: Position + Cabinet exist, no occupant | Absence of active employee for `(unit, title)` — implicit, not queryable as Position state | ✗ |
| **Liquidate Position** | Close Position + Cabinet (org decision) | `DELETE /positions` only if zero employee refs; no Cabinet teardown; **no liquidation workflow** | ✗ |
| **Org unit deactivate** | Positions under unit follow org policy | `org_units.is_active` — positions not linked to unit | ✗ |
| **Multiple same title in unit** | Separate Position rows («Ординатор 1», «Ординатор 2») | Same `position_id` for all «Ординатор» unless names differ globally | ✗ |

**POS sync runbook example:** renaming `position_id=64` on VPS changed label for **all** employees attached to that id — confirms lifecycle is tied to **catalog row**, not per-unit Position.

---

## 6. Access Analysis

### 6.1. What should determine access (ARCH-001)

| Factor | Role in TO-BE |
|--------|---------------|
| **Position Cabinet** | Operational permissions and object visibility |
| **Employment** | Grants / revokes Cabinet access for Person |
| **Person** | Actor in audit; initiator control (tasks) |
| **Platform User** | Authentication only |

### 6.2. What determines access today (positions/org subsystem)

| Mechanism | User-centric? | Notes |
|-----------|---------------|-------|
| `GET /positions`, `/org-units/*` | **Yes** — `get_current_user`, `compute_scope(uid)` | Visibility from **user’s** dept scope, not Cabinet |
| `POST/PUT/DELETE /positions` | **Yes** — `_is_privileged(user)` | Admin = privileged **user**, not org role |
| Org tree filtering | **Yes** — `scope_unit_id` from user RBAC | `org_units_tree` trims tree to user scope |
| `org_unit_managers` | **Yes** — `user_id` | Head = user, not Position/Cabinet |
| `org_unit_groups.deputy_user_id` | **Yes** | Deputy = user |
| `person_assignments` → access resolver | Partial | Uses catalog `position_id`, not Cabinet |
| Employment forms | Partial | Pick **title** from catalog + **unit** separately |

### 6.3. Explicit anti-patterns (requested)

| Anti-pattern | Evidence |
|--------------|----------|
| **Position as generic job title** | `positions(name)` global unique; POSITIONS_SYNC_RUNBOOK; ADR-046 duplicates |
| **Role as substitute for position** | Pilot `employee_id = roles.code`; UserCreateForm «Роль Corpsite» (OPS-029); tasks filter `users.role_id` → `employees.position_id` |
| **org_unit + role as proxy for position** | Working contacts expert rows keyed by `user_id` + `role_name` + `unit_name`; team tasks scope by `users.unit_id` |
| **user_id / employee_id as owner of org structures** | `org_unit_managers.user_id`; `deputy_user_id`; RBAC `compute_scope(user_id)` defines org tree visibility — **user owns the view**, not Organization/Cabinet |
| **employee_id as position identity (pilot)** | Legacy seed ties employee_id to role code — collapses HR slot into platform role |

### 6.4. Future Cabinet access resolver — readiness

| Prerequisite | Status |
|--------------|--------|
| Stable org-unique Position PK | ✗ |
| `position_cabinets` with 1:1 FK | ✗ |
| Employment FK → org-unique Position | ✗ — FK to title catalog today |
| ACTING overlay → Cabinet (ADR-036) | ✗ |
| Resolver: Person → cabinets[] | ✗ — `access_resolver` uses ROLE/USER grants |

**Conclusion:** Org structure subsystem **cannot** support Cabinet access resolver without prior Position entity migration.

---

## 7. Gap Analysis

| # | ARCH-001 requirement | AS-IS | Severity |
|---|------------------------|-------|----------|
| G1 | Org-unique Position | Global title catalog | **Critical** |
| G2 | 1:1 Position Cabinet | No cabinet entity | **Critical** |
| G3 | Simultaneous Position + Cabinet creation | Only title insert | **Critical** |
| G4 | Position embeds org context | org only on employee/assignment | **Critical** |
| G5 | Multiple same titles → multiple Positions | Global name uniqueness prevents | **Critical** |
| G6 | Vacancy as Position/Cabinet state | Implicit via empty employee | **High** |
| G7 | Liquidation ends Position + Cabinet | Delete title if no FK refs | **High** |
| G8 | Staffing table per org unit (ADR-046) | Only “used titles” EXISTS filter | **High** |
| G9 | Title taxonomy separate from Position | Single table conflates both | **Medium** |
| G10 | Unit head as Position/Cabinet | `org_unit_managers.user_id` | **High** |
| G11 | Org hierarchy for roll-up | `org_units` tree exists | **Low** — reusable |
| G12 | Org groups (clinical/para/admin) | `group_id` + `medical_org_groups.py` | **Low** — reusable |
| G13 | Employment → Cabinet | Employment → `(unit, title_id)` | **Critical** |
| G14 | No Slot entity if Position is unique | N/A — Position not unique yet | **Blocked** |
| G15 | Position rename scoped to one slot | Rename affects all FK holders globally | **High** |

**ARCH-001 sufficiency:** baseline covers all gaps conceptually (§3.3, §4.2, §6, §15.0 Slot decision). **No ARCH-001 amendment required** for this subsystem; implementation must **split** title catalog from org-unique Position and **introduce** Cabinet.

---

## 8. Required ADR Changes

### Required

| ADR / document | Change |
|----------------|--------|
| [**ADR-050**](../adr/ADR-050-organization-position-cabinet-model.md) (**Proposed**) | **Org-unique Position + Position Cabinet** — entity definitions, 1:1 invariant, migration from `public.positions`, coexistence rules |
| **ADR-031** | Positions section: global catalog vs org-unique Position; Directory UI contract |
| **ADR-046** | `org_unit_allowed_positions` → staffing table of **Position** rows (or creation workflow), not catalog FK |
| **ADR-046 normalization audit** | Merge strategy feeds into Position migration, not just title dedup |
| **ARCH-001 §14 handoff** | Mark positions-org assessment complete; link [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) |

### Recommended

| ADR / document | Change |
|----------------|--------|
| **ADR-032** | Transfer changes **Employment** on org-unique Position; no catalog rename side effects |
| **ADR-042 Phase B1/B2** | `person_assignments.position_id` → FK semantics documented as org-unique Position post-migration |
| **ADR-014 (sync policy)** | Positions sync runbook split: title taxonomy vs staffing Positions |
| **unified_org_filter** | Owner unit may come from org-unique Position’s unit |

### Optional

| ADR / document | Change |
|----------------|--------|
| **ADR-004 org-units** | Clarify relationship org_unit → child Positions |
| **OPS-029** | Cross-reference Position vs Platform Role when enrolling into staffing slot |
| **POSITIONS_SYNC_RUNBOOK** | Deprecate after migration or restrict to taxonomy layer |

---

## 9. Migration Roadmap

Phases are **design-only**; no implementation in this assessment.

### Phase P0 — Architecture gate (current)

- [x] This assessment
- [ ] Architecture session: approve org-unique Position model vs retain taxonomy layer
- [x] Author [**ADR-050**](../adr/ADR-050-organization-position-cabinet-model.md) (Position + Cabinet — **Proposed**; pending architecture session approval)

### Phase P1 — Model split (foundation)

1. Introduce **`organizational_positions`** (or evolve `positions` with breaking migration) with **`org_unit_id`**, disambiguator, lifecycle status.
2. Introduce **`position_cabinets`** — 1:1 FK, created in same transaction as Position.
3. Retain **`position_titles`** / legacy `positions.name` as optional **taxonomy** for dropdown labels (ADR-046).
4. Unique constraint: `(org_unit_id, title_ref, slot_code)` or equivalent — **not** global `lower(name)`.

### Phase P2 — Data migration

1. Inventory all distinct `(org_unit_id, position_id)` pairs from `employees` and `person_assignments`.
2. For each pair, create **org-unique Position** + Cabinet; map old catalog `position_id` → new Position.
3. Handle collisions (same catalog id, multiple units) — expected split into N Positions.
4. ADR-046 dedup: merge duplicate **titles** before or during migration mapping.
5. Do **not** rename shared catalog rows in place (VPS position_id=64 lesson).

### Phase P3 — API & read paths

1. `/directory/positions` → split endpoints: taxonomy vs org staffing Positions.
2. Implement ADR-046 **allowed/staffing** reads on org-unique Position.
3. Employment CRUD picks **Position in unit**, not `(unit + global title)`.
4. Deprecate global rename `PUT` that spans units.

### Phase P4 — Lifecycle & vacancy

1. Position states: `active | vacant | liquidated` (Cabinet follows).
2. Vacancy = no active Employment; Cabinet persists (ARCH-001 §4.7.1).
3. Liquidation workflow: close Cabinet, archive ops objects per policy.

### Phase P5 — Access resolver prep

1. `person_assignments.position_id` → org-unique Position FK (post P2).
2. Resolver: active assignments → `cabinet_id[]` (feeds queue #3 `access-rbac`).
3. Replace `org_unit_managers.user_id` with Position/Cabinet-based head model (long-term).

### Phase P6 — Consumer alignment

1. Tasks, contacts, visibility grants: remap `target_position_id` to org-unique Position.
2. Update POSITIONS_SYNC_RUNBOOK for taxonomy-only scope.

---

## 10. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Big-bang rename of `public.positions`** | Breaks all FKs; VPS id=64 scenario at scale | New table or additive columns + mapping; no in-place title rename |
| **Treating migration as “catalog cleanup” only** | ARCH-001 still not satisfied | Explicit org-unique Position + Cabinet creation |
| **Keeping global catalog as Position** | Cannot support vacancy, Cabinet 1:1, multi-slot | Architecture session sign-off on split |
| **person_assignments / employees diverge** | Wrong Cabinet access | Single FK target: org-unique Position |
| **ADR-046 deferred again** | First hire in unit still sees global title list | Minimum staffing table in P1 |
| **Role-as-position pilot debt** | Wrong resolver inputs | Parallel cleanup in `access-rbac` assessment |
| **Org unit head on user_id** | User turnover breaks “structural” head | Phase P5 head model |
| **Duplicate title strings (ADR-046 audit)** | Migration maps to wrong Positions | Normalize before P2 mapping |
| **Premature Cabinet ops migration** | Tasks/Personnel bind to wrong ids | **This subsystem first** — assessment program order validated |

---

## 11. Focus validation summary

| Validation focus | Result |
|------------------|--------|
| Org-unique Position | **Not supported** — requires schema + semantic split |
| 1:1 Position Cabinet | **Not supported** — entity absent |
| Position lifecycle | **Partial** — title CRUD only; no vacancy/liquidation |
| Vacancy | **Implicit only** — not Position/Cabinet state |
| Multiple identical job titles as separate Positions | **Blocked** by global name uniqueness |
| Department/group hierarchy | **Supported** — `org_units` + `group_id`; reusable |
| Future Employment binding | **Partial** — pair `(org_unit_id, catalog position_id)` exists; must retarget org-unique Position |
| Future Cabinet access resolver | **Blocked** until G1–G3 resolved |

---

## 12. Conclusion

Positions & Org Structure is the **critical foundation gap** for the entire Position Cabinet program. ARCH-001 describes the target correctly; the current **`public.positions` global catalog is incompatible** with org-unique Position, Cabinet 1:1, vacancy, and multi-slot staffing.

Org **hierarchy and classification** (units, groups) are largely reusable. The **Position entity semantics** must change — not the ARCH-001 baseline.

**Next in program:** [personnel-employment assessment](./ARCH-001-assessment-program.md) (queue #2) — should reference org-unique Position IDs from this migration as prerequisite.

---

## Related documents

| Document | Relation |
|----------|----------|
| [ARCH-001 v0.5](./ARCH-001-position-permission-model.md) | Baseline |
| [ARCH-001-task-subsystem-assessment.md](./ARCH-001-task-subsystem-assessment.md) | Downstream consumer of Position/Cabinet |
| [ADR-031](../adr/ADR-031-directory-personnel-contacts-contract.md) | Positions vs roles contract |
| [ADR-046](../adr/ADR-046-org-unit-allowed-positions.md) | Allowed positions (future) |
| [ADR-046 normalization audit](../adr/ADR-046-position-catalog-normalization-audit.md) | Duplicate titles |
| [POSITIONS_SYNC_RUNBOOK](../ops/POSITIONS_SYNC_RUNBOOK.md) | Catalog sync — id=64 lesson |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 1.0 | Initial assessment — positions & org structure |
