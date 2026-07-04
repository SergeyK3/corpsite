# ADR-050 — Organization Position & Position Cabinet Model

## Status

**Accepted** — 2026-07-04

Implementation contract derived from [ARCH-001 v0.5](../architecture/ARCH-001-position-permission-model.md), [Architecture Governance](../architecture/ARCHITECTURE_GOVERNANCE.md), and completed foundation assessments. This ADR **formalizes** decisions already implied by the accepted baseline; it **does not** amend ARCH-001 or redefine terminology.

| Field | Value |
|-------|-------|
| Supersedes (conceptually) | As-is semantics of `public.positions` as Position |
| Enables | [**ADR-051**](./ADR-051-cabinet-access-resolution.md) (Cabinet Access Resolver — **Accepted**) |
| Related | [ADR-031](./ADR-031-directory-personnel-contacts-contract.md), [ADR-046](./ADR-046-org-unit-allowed-positions.md), [ADR-042 Phase A/B](./ADR-042-phase-a-personnel-access-enrollment-architecture.md), [ADR-032](./ADR-032-employee-transfer-architecture.md), [ADR-036](./ADR-036-hr-events-unified-model.md) |

### Explicitly out of scope (ADR-051 and others)

| Topic | Owner |
|-------|-------|
| Access calculation, permission resolution, RBAC algorithms | **ADR-051** |
| Authentication, JWT, Platform User credential policy | ADR-042 B5, OPS-028 |
| Cabinet Access Resolver inputs/outputs | **ADR-051** |
| Task / report / notification rebinding | ADR-049 and consumer ADRs |
| Concrete SQL migrations, table names, API endpoints | Implementation program |

---

## 1. Problem Statement

Corpsite as-is models **job titles** as a **global catalog** (`public.positions`: unique `lower(name)` per organization-wide string). Org context exists only on **employee and assignment rows** as the composite `(org_unit_id, catalog position_id)`. There is **no** org-unique Position entity and **no** Position Cabinet.

This contradicts the accepted baseline:

- **Position** must be a **unique staffing unit** in org structure (e.g. «Ординатор 2, Хирургия 1»), not a reusable title shared across all units.
- **Position Cabinet** must exist **1:1** with Position as the long-lived operational container for tasks, reports, statistics, and Permission Template configuration.
- **Employment** (Занятие должности / `person_assignments`) must reference **org-unique Position**, not a bare catalog title id.
- **Vacancy**, **liquidation**, and **rename** today affect **catalog rows** or implicit employee absence — not first-class Position/Cabinet lifecycle.

Foundation assessments ([positions-org-structure](../architecture/ARCH-001-positions-org-structure-assessment.md), [personnel-employment](../architecture/ARCH-001-personnel-employment-assessment.md), [foundation summary](../architecture/ARCH-001-foundation-summary.md)) confirm: the gap is **structural implementation**, not missing baseline concepts. **ADR-050** is required before Employment retargeting, Cabinet access (ADR-051), or consumer subsystem migration.

---

## 2. Context

### 2.1. Authoritative inputs

| Document | Relevant conclusion |
|----------|-------------------|
| [ARCHITECTURE_GOVERNANCE](../architecture/ARCHITECTURE_GOVERNANCE.md) | Position = org-unique staffing unit; Cabinet = digital representation; permissions follow Employment, not User |
| [ARCH-001](../architecture/ARCH-001-position-permission-model.md) | §3.3–§4.2, §6, §15.0 — Position/Cabinet 1:1, durability, vacancy, no Slot entity |
| [ARCH-001-foundation-summary](../architecture/ARCH-001-foundation-summary.md) | ADR-050 is critical path gate; no new core entities |
| [ARCH-001-positions-org-structure-assessment](../architecture/ARCH-001-positions-org-structure-assessment.md) | Split global catalog from org-unique Position; simultaneous Cabinet creation |
| [ARCH-001-personnel-employment-assessment](../architecture/ARCH-001-personnel-employment-assessment.md) | Employment FK must retarget org-unique Position; vacancy blocked until this ADR |

### 2.2. As-is vs target (summary)

| Concept | As-is | Target (this ADR) |
|-------|-------|-------------------|
| Staffing unit | `(org_unit_id, catalog position_id)` composite | **Org-unique Position** (single PK embeds org context) |
| Operational container | None | **Position Cabinet** (1:1 with Position) |
| Title dictionary | `public.positions` conflated with Position | Optional **title taxonomy** reference — not Position |
| Vacancy | No active employee for composite | Position **vacant**; Cabinet **persists** |
| Rename | Global catalog row — affects all units sharing id | **Scoped** to one org-unique Position |
| Employment FK | Catalog `position_id` + separate `org_unit_id` | **Org-unique Position** FK |

### 2.3. Single-tenant organization

Corpsite operates as a **single organization** tenant. **Organization** in this ADR means the medical institution modeled by Corpsite — org structure is expressed through `org_units` and org-unique Positions. Multi-tenant Organization entity is **not** introduced; baseline already treats org structure as given.

---

## 3. Decision

Adopt an **implementation architecture** for org-unique **Position** and **Position Cabinet** with the following contracts:

1. **Introduce org-unique Position** as the atomic staffing unit anchored to org structure (org unit), distinguishable from global title taxonomy.
2. **Introduce Position Cabinet** in **strict 1:1** relationship with Position; create Cabinet **in the same logical operation** as Position creation.
3. **Bind Employment** to org-unique Position (replacing catalog composite semantics over time).
4. **Define Position and Cabinet lifecycle** including vacancy, rename, Person transfer between Positions, and Position liquidation.
5. **Store Permission Template configuration on Cabinet**, not on Platform User or Person.
6. **Defer all access and permission resolution** to **ADR-051**.

No separate **Slot** entity is introduced (ARCH-001 §3.3, §15.0). Uniqueness of «Ординатор 1» vs «Ординатор 2» in the same unit is expressed by **distinct Position rows**, optionally via disambiguator attributes.

---

## 4. Data Model (conceptual only)

Conceptual entities and relationships — **not** SQL schema.

### 4.1. Conceptual model

```text
Organization (implicit single tenant)
        │
        ├── org_units (structure hierarchy)
        │
        └── org-unique Position ──────────────┐
                 │ 1:1                       │ owns
                 ▼                             │
         Position Cabinet ◄────────────────────┘
                 │
                 │ contains (configuration)
                 ▼
         Permission Template
                 ▲
                 │ access period (ADR-051)
                 │
         Employment (person_assignment episode)
                 ▲
                 │
              Person
                 ▲
                 │ authenticates (no ownership)
                 │
         Platform User
```

### 4.2. Entity contracts

#### Organization & org structure

| Entity | Role |
|--------|------|
| **Organization** | Owns staffing policy and org structure (implicit tenant) |
| **Org unit** | Structural anchor; each org-unique Position belongs to exactly one org unit (or policy-defined structural node) |

Org groups (`group_id`, clinical/paraclinical/admin classification) remain **classification** of org units — unchanged conceptually from as-is.

#### Org-unique Position

| Aspect | Contract |
|--------|----------|
| **Identity** | Organization-unique staffing unit — **not** global title string |
| **Uniqueness** | Distinct from all other Positions in the organization by primary key; human identity = org unit + title label + optional disambiguator (e.g. slot index, code) |
| **Attributes (conceptual)** | Org unit reference; display name / title reference; optional disambiguator; category/classification; **lifecycle status**; optional link to title taxonomy entry |
| **Not** | Platform Role, Permission Template, Person, User, Cabinet, Employee |

#### Position Cabinet

| Aspect | Contract |
|--------|----------|
| **Identity** | Stable operational id paired 1:1 with Position |
| **Owner** | Position — **not** Person, **not** Platform User |
| **Contains (future consumers)** | Tasks, reports, journals, statistics, function documents, **Permission Template** — binding of operational objects is consumer ADR scope |
| **Created** | Together with Position — no Cabinet without Position |
| **Destroyed** | Only when Position is **liquidated** per lifecycle policy |

#### Permission Template (configuration only)

| Aspect | Contract |
|--------|----------|
| **Location** | **Inside** Position Cabinet |
| **Nature** | Named configuration bundle (e.g. codes analogous to as-is `public.roles.code`) |
| **Not assigned to** | Platform User or Person directly |
| **Resolution** | How Person receives effective permissions — **ADR-051 only** |

This ADR states **where** Template lives, not **how** permissions are calculated.

#### Employment (Занятие должности)

| Aspect | Contract |
|--------|----------|
| **Canonical store** | `person_assignments` (ADR-042) |
| **References** | **Person** + **org-unique Position** + period + employment type |
| **Effect** | Establishes HR fact of occupancy; **grants access** to Position Cabinet for the period — enforcement in ADR-051 |
| **Cardinality** | N active Employments per Person allowed (совместительство); N Employments over time per Position (sequential occupants) |
| **Not** | Owner of Cabinet; substitute for Permission Template |

#### Person

| Aspect | Contract |
|--------|----------|
| **Role relative to Position/Cabinet** | Temporary occupant via Employment; **never owner** |
| **Acting (и.о.)** | Separate overlay (ADR-036) granting access to **another** Position's Cabinet without mutating primary Employment — overlay mechanics in ADR-051 |

#### Platform User

| Aspect | Contract |
|--------|----------|
| **Role** | Authentication and delivery endpoint only |
| **Never owns** | Position, Cabinet, Permission Template, or operational objects |
| **Link to Person** | Indirect (ADR-044, ADR-048); **no** FK from User to Position or Cabinet |

#### Employee (operational shell)

| Aspect | Contract |
|--------|----------|
| **Role** | Operational convenience / enrollment shell (ADR-041, ADR-042) — **not** defined by this ADR |
| **Position reference** | Must **derive from or align with** Employment on org-unique Position post-migration — not independent staffing truth |

#### Title taxonomy (optional reference layer)

| Aspect | Contract |
|--------|----------|
| **Purpose** | Shared vocabulary for naming Positions (ADR-046 evolution) |
| **Not** | Position itself; renaming taxonomy entry **must not** rename or merge org-unique Positions |
| **As-is analog** | Legacy `public.positions` catalog — **transitional** until split |

### 4.3. Relationship summary

| From | To | Cardinality | Semantics |
|------|-----|-------------|-----------|
| Org unit | Position | 1:N | Position anchored in structure |
| Position | Position Cabinet | 1:1 | Simultaneous creation; shared lifecycle end |
| Position | Employment | 1:N (over time) | Occupancy episodes |
| Person | Employment | 1:N | Concurrent allowed |
| Employment | Position | N:1 | Each episode references one Position |
| Position Cabinet | Permission Template | 1:1 (config) | Template belongs to Cabinet |
| Person | Cabinet | — | **Access only** via Employment (ADR-051) — **no ownership** |
| Platform User | Cabinet | — | **None** |

---

## 5. Lifecycle

### 5.1. Position lifecycle states (conceptual)

| State | Meaning |
|-------|---------|
| **active** | Position exists in staffing table; may be occupied or vacant |
| **vacant** | Position is **active** but has **no** active Employment for that Position (derived or explicit — implementation choice) |
| **liquidated** | Position removed from active staffing by org decision; **terminal** for Position and Cabinet |

**Vacant** is a **normal** state (ARCH-001 §4.7.1), not an error. Vacancy **does not** delete or suspend Cabinet.

Business policy for operational processes during vacancy (regular tasks, notifications) is **process policy**, not defined here (ARCH-001 §4.7.2).

### 5.2. Cabinet lifecycle

Cabinet lifecycle **equals** Position lifecycle:

| Position event | Cabinet behavior |
|----------------|------------------|
| Position created | Cabinet **created** (same transaction / logical unit of work) |
| Position vacant | Cabinet **unchanged** — persists with history and operational objects |
| Person change on Position | Cabinet **unchanged** — only access changes (ADR-051) |
| Employment ends | Cabinet **unchanged** |
| Position renamed | Cabinet **unchanged** (same cabinet id) |
| Position liquidated | Cabinet **terminated** per liquidation policy |

### 5.3. Position creation

**Trigger:** organizational decision to add a staffing unit ( штатная единица ) to structure.

**Contract:**

1. Create **org-unique Position** with org unit anchor and human-readable identity (title + disambiguator as needed).
2. Create **Position Cabinet** paired 1:1 ** atomically** with Position.
3. Initialize **Permission Template** on Cabinet (may reference existing template code catalog — configuration detail for implementation).
4. Position may be **vacant** immediately after creation.

**Must not:** create Cabinet without Position; create Position without org context; reuse global catalog row as Position id.

### 5.4. Position rename

**Trigger:** change of display name, title reference, or disambiguator for **one** staffing unit.

**Contract:**

- Rename affects **only** the targeted org-unique Position metadata.
- **Does not** change Position primary identity, Cabinet id, or Employment/Cabinet FK targets.
- **Does not** perform global catalog rename that impacts other units (as-is anti-pattern — VPS `position_id=64` lesson).
- Operational history remains under the **same** Cabinet.

### 5.5. Position transfer rules

Distinguish two cases:

#### A. Person transfer (HR — смена занятия)

**Trigger:** Person moves from Position A to Position B (transfer, hire on new slot).

**Contract:**

- **Close** Employment on Position A (end date, lifecycle).
- **Open** Employment on Position B.
- **Position A and B unchanged** — Cabinets persist; operational objects stay with each Cabinet.
- **No migration** of tasks/reports between Cabinets unless explicit business process (out of scope).
- Person may hold **both** Employments only when policy allows concurrent assignments — separate Positions.

This aligns with ARCH-001 §4.6 and [ADR-032](./ADR-032-employee-transfer-architecture.md) direction.

#### B. Structural move of a staffing slot (org restructuring)

**Trigger:** org unit merge/split/move of a **Position** to another org unit.

**Contract:**

- **Preferred:** treat as **liquidation** of old Position + Cabinet (with archival policy) and **creation** of new Position + Cabinet if operational history must remain immutable per org unit.
- **Alternative (explicit org policy only):** controlled **re-anchor** of Position to new org unit **without** changing Position/Cabinet ids — only when implementation and audit accept updated org context on same id.
- **Must not:** silently retarget Employment FKs by renaming shared catalog titles.

Default architectural recommendation from assessments: **avoid in-place org moves** when Cabinet holds operational history; prefer liquidation + new Position.

### 5.6. Vacancy behavior

| Aspect | Rule |
|--------|------|
| **Definition** | No active Employment referencing the Position |
| **Position** | Remains **active** (not liquidated) |
| **Cabinet** | **Persists** — tasks, reports, statistics, configuration remain |
| **Access** | No Person has Cabinet access via primary Employment until new Employment opens (ADR-051) |
| **Acting** | Temporary access to vacant Position's Cabinet possible via ADR-036 overlay — ADR-051 |
| **Operational processes** | Business/process policy (§4.7.2 ARCH-001) |

### 5.7. Position liquidation

**Trigger:** organizational decision to **eliminate** a staffing unit (упразднение штатной единицы).

**Contract:**

1. **Close** all active Employments on the Position (HR prerequisite).
2. Transition Position to **liquidated** (terminal).
3. **Terminate** paired Position Cabinet per archival policy:
   - Cabinet operational objects **archived or frozen** — consumer ADRs define task/report handling.
   - **No** new Employments on liquidated Position.
4. **Permission Template** ceases with Cabinet.

Liquidation is the **only** architectural event that **ends** Cabinet lifecycle (ARCH-001 §4.2 invariant).

**Must not:** delete Position/Cabinet implicitly when last employee terminates — that is **vacancy**, not liquidation.

### 5.8. Relationship events (Person, User, Employment)

| Event | Position / Cabinet | Person | Platform User |
|-------|-------------------|--------|---------------|
| Hire / open Employment | Unchanged; vacancy → occupied | Gains access period (ADR-051) | Unchanged |
| Termination / close Employment | Unchanged; occupied → vacant | Loses access (ADR-051) | Account policy separate (ADR-033) |
| Rehire same Person | Same or new Position | New Employment episode | Same login may persist (OPS-028) |
| User create | No effect | No direct link to Position | Auth only |
| Acting overlay | Unchanged | Temporary access to another Cabinet | Unchanged |

---

## 6. Invariants

The following invariants are **mandatory** and **non-negotiable** within this ADR. They restate ARCH-001 and foundation assessment conclusions as implementation contracts.

| # | Invariant |
|---|-----------|
| I1 | **Position is organization-unique** — identifies one staffing unit in org structure, not a global reusable title. |
| I2 | **Position owns exactly one Position Cabinet** — strict 1:1. |
| I3 | **Cabinet cannot exist without Position** — created together; no orphan Cabinet. |
| I4 | **Cabinet survives occupant changes** — Person change, Employment end, leave: Cabinet persists. |
| I5 | **Employment references org-unique Position** — not bare catalog title as staffing identity. |
| I6 | **Person never owns Cabinet** — Person may receive **access** for a period; no ownership FK. |
| I7 | **Platform User never owns Cabinet** — auth and delivery only. |
| I8 | **Permission Template belongs to Cabinet** — not to User or Person. |
| I9 | **Vacancy does not destroy Cabinet** — vacant Position is normal; Cabinet remains. |
| I10 | **Position liquidation destroys Cabinet** according to lifecycle policy — the only terminal end state. |
| I11 | **Operational object ownership** (tasks, reports, etc.) binds to **Cabinet**, not Person or User — consumer ADRs apply ARCH-001 §4.5 exceptions. |
| I12 | **No Slot entity** — disambiguation is on Position when needed (ARCH-001 §15.0). |
| I13 | **Cabinet id is stable** across rename and occupant change — operational history accrues to Cabinet. |

---

## 7. Compatibility with ARCH-001

| ARCH-001 principle | ADR-050 contract |
|--------------------|-----------------|
| §3.3 Position = org-unique staffing unit | §4.2 Org-unique Position identity |
| §3.4 Cabinet 1:1, long-lived | §4.2, §5.2, I2–I4 |
| §3.2 Employment opens access | §4.2 Employment → Position FK; access enforcement deferred to ADR-051 |
| §3.5 Permission Template inside Cabinet | §4.2, I8 |
| §3.7 Platform User auth only | §4.2, I7 |
| §4.2 Durability / vacancy | §5.1, §5.6, I9 |
| §4.6 Person change without ops migration | §5.5.A |
| §4.7.2 Process policy at vacancy | Explicitly excluded |
| §15.0 No Slot entity | I12 |

**No baseline amendment required.** ADR-050 implements ARCH-001; it does not extend the entity model beyond baseline entities.

---

## 8. Migration Strategy (high level)

Architectural direction only — **no** concrete SQL, **no** ordered migration scripts. Phases align with [ARCH-001-positions-org-structure-assessment §9](../architecture/ARCH-001-positions-org-structure-assessment.md).

### Phase 1 — Model introduction

- Introduce org-unique **Position** and **Position Cabinet** entities (1:1).
- Optionally retain legacy title catalog as **taxonomy reference** only (ADR-046 direction).
- Enforce organization-unique identity constraints — **not** global `lower(name)` uniqueness on Position.

### Phase 2 — Data mapping

- Inventory distinct as-is `(org_unit_id, catalog position_id)` pairs from `employees` and `person_assignments`.
- For each pair, create org-unique Position + Cabinet; maintain **mapping** from legacy catalog ids to new Position ids.
- Split collisions (one catalog id, multiple units) into **multiple** Positions.
- Apply ADR-046 title dedup **before or during** mapping — do not rename shared catalog rows in place.

### Phase 3 — Employment retarget

- Retarget `person_assignments` (and aligned Employee snapshot) to org-unique Position FK.
- Derive vacancy from Employment absence on Position.
- Block new bindings to catalog composite as staffing truth.

### Phase 4 — API and directory semantics

- Separate **taxonomy** reads from **staffing Position** reads (directory contract — ADR-031 amendment).
- Staffing table / allowed-positions (ADR-046) references org-unique Position rows.
- Position rename and liquidation workflows enforce §5.4–§5.7.

### Phase 5 — Consumer preparation

- Enable ADR-051 resolver inputs (Position → Cabinet id map).
- Consumer subsystems (tasks, visibility, contacts) remap to Cabinet/Position ids in their ADRs — not in ADR-050.

**Hard rule:** do not implement ADR-051 or RBAC cutover until Phase 1–3 Position/Cabinet identities exist and mapping is stable.

---

## 9. Consequences

### Positive

- Stable operational container (Cabinet) survives HR turnover — aligns with organization-centric model.
- Vacancy and liquidation become **queryable** staffing states.
- Employment, tasks, RBAC, and visibility can share one **Position / Cabinet** identity graph.
- Rename scoped to one slot — eliminates global catalog rename blast radius.
- Unblocks ADR-051 and foundation migration critical path.

### Negative / costs

- **Breaking semantic change** from as-is `public.positions` — all FKs and UIs referencing catalog as Position require migration.
- **Dual-write or mapping period** likely during Phases 2–3.
- **Org unit head** and other user-centric structure edges (`org_unit_managers.user_id`) remain transitional until consumer ADRs retarget to Position/Cabinet.
- **Implementation effort** is foundational — must complete before task cabinet binding or resolver enforcement.

### Neutral

- Title taxonomy may remain as reference layer — optional, not a new core entity.
- Employee operational shell persists — alignment with Employment is personnel ADR scope.
- Process policy at vacancy unchanged in scope.

---

## 10. Decision Log

| Date | Decision |
|------|----------|
| 2026-07-03 | **Proposed ADR-050** — formalize org-unique Position + Position Cabinet implementation contract from ARCH-001 and foundation assessments. |
| 2026-07-03 | **No Slot entity** — confirmed per ARCH-001 §15.0. |
| 2026-07-03 | **1:1 Position ↔ Cabinet** — atomic creation; shared liquidation; Cabinet survives vacancy and occupant change. |
| 2026-07-03 | **Split** legacy global title catalog from org-unique Position — taxonomy optional reference, not Position. |
| 2026-07-03 | **Employment references org-unique Position** — retarget from `(org_unit_id, catalog position_id)` composite. |
| 2026-07-03 | **Permission Template on Cabinet** — access resolution explicitly deferred to **ADR-051**. |
| 2026-07-03 | **Person transfer** closes/opens Employment; **does not** move Cabinet ownership. |
| 2026-07-03 | **Liquidation** is terminal for Position and Cabinet; **termination of last employee** is vacancy, not liquidation. |
| 2026-07-03 | **Platform User** excluded from Position/Cabinet ownership — auth only. |
| 2026-07-04 | **Accepted ADR-050** — ratified as Phase 2 implementation baseline (org-unique Position + Position Cabinet); architecture session gate closed. |

---

## Appendix A — As-is mapping reference (informative)

| As-is artifact | Target role post-migration |
|----------------|----------------------------|
| `public.positions` (global catalog) | Title **taxonomy** reference — not org-unique Position |
| `(employees.org_unit_id, employees.position_id)` | Source pairs for Position **creation mapping** |
| `person_assignments.org_unit_id + position_id` | Employment → retarget to org-unique Position FK |
| `public.roles.code` | Analog for Permission **Template code** on Cabinet — not user assignment |
| No entity | **Position Cabinet** — new |

---

## Appendix B — Related assessment cross-reference

| Assessment | ADR-050 dependency |
|------------|-------------------|
| [positions-org-structure](../architecture/ARCH-001-positions-org-structure-assessment.md) | Primary source for lifecycle gaps and migration phases |
| [personnel-employment](../architecture/ARCH-001-personnel-employment-assessment.md) | Employment FK retarget; vacancy; acting blocked until this ADR |
| [access-rbac](../architecture/ARCH-001-access-rbac-assessment.md) | Blocked on Position/Cabinet ids; resolver is ADR-051 |
| [platform-user-identity](../architecture/ARCH-001-platform-user-identity-assessment.md) | User remains auth-only; no Position FK on User |
| [tasks](../architecture/ARCH-001-task-subsystem-assessment.md) | Executor/owner Cabinet FKs require Position/Cabinet from this ADR |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 0.1 | Initial proposed ADR — implementation contract from ARCH-001 foundation phase |
| 2026-07-04 | 1.0 | Status Proposed → Accepted — Phase 2 implementation gate |
