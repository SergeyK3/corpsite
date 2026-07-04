# ACCESS-002 — Organizational Management Authority Model

## Status

**Reviewed** — 2026-07-04

Organizational policy document. Defines **management responsibilities** assigned to Position Cabinets, the **derived management authority capability groups** those responsibilities produce, and **hierarchy scope** over org subtrees. **No runtime effect by itself** — current enforcement remains on legacy `users.unit_id`, `org_unit_managers`, task RBAC, and ADR-042 visibility assignments until a future implementation program consumes this model. **Approved** status is required before implementation planning. Does **not** unblock [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) or Phase 2.6b (ACCESS-001 + ADR-053 track).

| Field | Value |
|-------|-------|
| Depends on | [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) (**Accepted**) — Position, Cabinet, org-unit placement |
| Depends on | [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) (**Accepted**) — Cabinet access resolution |
| Depends on | [ADR-053](../adr/ADR-053-permission-template-binding-model.md) (**Accepted**) — Permission Template binding |
| Related | [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md) (**Reviewed**) — baseline access permissions (orthogonal) |
| Related | [ADR-010](../adr/ADR-010-regular-tasks-hierarchy.md), [ADR-042 Phase E1](../adr/ADR-042-phase-e1-visibility-scope.md), [ADR-045](../adr/ADR-045-personnel-hr-processes-split.md) |
| Enables | Future management-authority implementation (no OPS runbook yet; gated on **Approved**) |
| Governance | Architecture acceptance complete — no architectural blockers; stakeholder review toward **Approved** |

---

## 1. Scope

This document covers:

- **Organizational management responsibility policy** — which Position Cabinets carry which **management responsibilities** (§3) over which **org subtree** (§6).
- **Derived authority capability groups** — how responsibilities map to implementable capability groups (§4); authorities **derive from** responsibilities, not the reverse.
- **Management hierarchy model** — how responsibilities flow along the org structure and reporting vertical (§5).
- **Subtree management principle** — default and exceptional scope rules for line, deputy, and executive roles (§6).
- **Governance input** for a future implementation that replaces user-centric management edges (`org_unit_managers.user_id`, `users.unit_id` as scope carrier) with **Cabinet-anchored management scope**.

This document does **not**:

- Change application code, schema, migrations, or runtime authorization.
- Define or approve `access_roles` baseline bindings — that is [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md).
- Insert contour rules, visibility assignments, or task-routing configuration.
- Replace `access_grants`, task RBAC, or ADR-042 E1 visibility as current enforcement authority.
- Specify OPS execution procedures — no OPS runbook is attached; **Approved** status required before any OPS runbook or implementation planning.

---

## 2. Principles

| # | Principle |
|---|-----------|
| M0 | **Responsibilities precede authorities.** Organizational **management responsibilities** (§3) are the primary policy object. **Management authority capability groups** (§4) are derived expressions for future enforcement — not the source of governance truth. |
| M1 | **Management responsibility follows Position Cabinet**, not Platform User login. Scope is anchored to the Cabinet's org-unique Position placement, not `users.unit_id` alone. |
| M2 | **Management responsibility is orthogonal to baseline access permissions.** A Cabinet may hold responsibility for personnel oversight without `HR_ENROLLMENT_MANAGER`; holding `HR_ENROLLMENT_MANAGER` does not automatically grant executive **responsibility for results** over all org units. |
| M3 | **Subtree is the default management scope unit.** Line heads are responsible for their org unit and descendants unless policy explicitly narrows or widens scope (§6). |
| M4 | **No implicit org-wide responsibility from title alone.** Director, Deputy, and line-head titles require explicit **management responsibility** assignment in policy — not inferred from catalog position name, global role, or derived capability group. |
| M5 | **Acting duty (и.о.) is not delegation.** ADR-036 **acting assignment** opens the **acted Position's Cabinet** for permission resolution (ADR-051). The Person receives the **acted Cabinet's defined management responsibilities** (§3) only as assigned to that Cabinet contour (§6.5) — **not** automatic inheritance of the primary Cabinet's responsibilities. **Delegation of responsibility** (§3.6, M9) is a separate, time-bounded transfer of duties between Cabinets without Employment change; see §4.5 for the derived expression. |
| M6 | **Vacancy suspends person-bound management, not Position-bound policy.** A vacant line-head Cabinet retains its **defined** management responsibilities for rebinding when occupied; no Person receives that scope until Employment opens the Cabinet (ADR-051 vacancy rule). |
| M7 | **Responsibilities compose independently; derived groups must not be conflated.** Responsibility for personnel ≠ responsibility for tasks ≠ responsibility for results. A derived **visibility** group must not imply **task management** unless the underlying responsibilities include both. |
| M8 | **Responsibility for organizational information is scoped, not org-wide by default.** Statistical and reporting roll-ups apply only within the authorized subtree unless executive responsibility is explicitly approved. |
| M9 | **Delegation transfers responsibility, not merely capability flags.** Temporary delegation is time-bounded, traceable, and recorded at the **responsibility** level — derived authority groups follow the delegated responsibilities. |
| M10 | **Engineering must not infer management policy.** Resolver mechanics, shadow logs, and `org_unit_managers` as-is rows do not substitute for ops/architecture approval of this document. |
| M11 | **Legacy user-centric edges remain transitional.** Until implementation, `org_unit_managers`, `users.unit_id`, ADR-042 visibility assignments, and task `scope=team` behavior are **as-is** — this document defines target policy only. |

---

## 3. Management responsibilities

Owner policy (2026-07-04): organizational governance is expressed as **management responsibilities** — duties a Position Cabinet holder bears toward a defined org subtree. Responsibilities are **separated by function**. A Position Cabinet may hold zero, one, or several responsibilities.

**Policy direction:** assign and approve **responsibilities first**. Implementation programs derive **authority capability groups** (§4) from approved responsibilities. Do not assign capability groups in policy as if they were primary organizational duties.

### 3.1. Responsibility for personnel

| Aspect | Policy |
|--------|--------|
| **Organizational meaning** | Duty to **know and oversee** the staffing and employment state of Positions within the authorized subtree — who occupies which functions, vacancy awareness, line oversight of subordinate staff |
| **Typical holders** | Line department heads, deputies with oversight remit, senior staff with approved narrow remit |
| **Not the same as** | HR **кадровое оформление** or **кадровое решение** (ACCESS-001 §3.1–§3.2), sysadmin user administration, or unrestricted personnel mutation |
| **ACCESS-002 stance (Draft)** | Line heads: **personnel responsibility** over own unit subtree — aligns with ACCESS-001 §3.4 **линейное информирование** as information duty, not HR processing |
| **Derives (§4)** | **Visibility** only — does **not** derive **task management**; task-management authority requires approved **responsibility for tasks** (§3.2) |

### 3.2. Responsibility for tasks

| Aspect | Policy |
|--------|--------|
| **Organizational meaning** | Duty to **ensure work is organized** — define, assign, reassign, and monitor operational tasks for the authorized subtree; maintain regular-task discipline |
| **Typical holders** | Line heads, functional managers, deputies with operational remit |
| **Not the same as** | Personal execution of tasks as a worker, HR enrollment processing, or org-wide sysadmin task administration |
| **ACCESS-002 stance (Draft)** | Line head Cabinets: **task responsibility** over own unit subtree; does not extend to peer departments without explicit policy |
| **Related** | ADR-010 — task responsibility at level 3 (head) is distinct from level 4 (employee execution) |
| **Derives (§4)** | **Task management** |

### 3.3. Responsibility for execution

| Aspect | Policy |
|--------|--------|
| **Organizational meaning** | Duty to **ensure assigned work is performed** — monitor progress, intervene on delays, enforce operational discipline within the authorized subtree. Does **not** include accepting subordinate reports or owning upward consolidation — that is **responsibility for results** (§3.4) |
| **Typical holders** | Line heads, deputies with operational remit |
| **Not the same as** | Personal task completion, report acceptance (§3.4), HR processing, or system-level job execution |
| **ACCESS-002 stance (Draft)** | Bundled with line-head remit over own subtree; always separable from **responsibility for results** in derivation |
| **Derives (§4)** | **Task management** (monitoring and discipline facet) only — does **not** derive **execution control** |

### 3.4. Responsibility for results

| Aspect | Policy |
|--------|--------|
| **Organizational meaning** | Duty to **own and accept outcomes** — receive subordinate reports, approve or return work, consolidate upward in the management vertical (**управленческий приём отчётности**) |
| **Typical holders** | Line heads (level 3→2 handoff), deputies (level 2→1), director (level 1 consolidation) per ADR-010 |
| **Not the same as** | Task assignment alone, HR **кадровое решение**, or passive analytics viewing |
| **ACCESS-002 stance (Draft)** | Mapped to ADR-010 hierarchical reporting chain; each level's result responsibility follows §5 hierarchy model |
| **Note** | Executive **кадровое решение** (ACCESS-001 §3.1) is HR decision authority — **not** result responsibility over regular operational task reports unless explicitly combined in policy |
| **Derives (§4)** | **Execution control** exclusively — report acceptance and upward consolidation; may also derive **analytics** (aggregated roll-up view) where result ownership includes summary indicators. Does **not** derive **task management** |

### 3.5. Responsibility for organizational information

| Aspect | Policy |
|--------|--------|
| **Organizational meaning** | Duty to **use and interpret organizational information** — aggregated indicators, statistical reports, management dashboards, and cross-unit situational awareness within remit |
| **Typical holders** | Head of statistics (`Отдел статистики`), QM leadership, executive deputies with analytics remit, director for consolidated executive view |
| **Not the same as** | Line personnel oversight alone, task assignment, or org-wide sysadmin reporting |
| **ACCESS-002 stance (Draft)** | Statistics/QM contours (ACCESS-001 §5 pending rows for units 68, 72) require **organizational information responsibility** before any baseline permission binding — task-role namespaces (`STAT_EROB_ANALYTICS`, etc.) are not responsibilities by themselves |
| **Scope default** | Subtree of anchor org unit; org-wide information responsibility only for explicitly approved executive policy |
| **Derives (§4)** | **Analytics**; **visibility** (read-only information access) |

### 3.6. Delegation of responsibility

| Aspect | Policy |
|--------|--------|
| **Organizational meaning** | Duty-holder **temporarily transfers** one or more management responsibilities (§3.1–§3.5) to another Position Cabinet **without** changing Employment |
| **Typical use** | Deputy covers line head during leave; director delegates organizational-information review window |
| **Not the same as** | ADR-036 **acting** (Employment overlay opening another Cabinet), permanent grant copy, or ACCESS-001 permission baseline |
| **ACCESS-002 stance (Draft)** | Delegation rules **not operationalized** in Draft — responsibility transfer defined for future policy matrix. Acting grants **access** to acted Cabinet; delegation transfers **management responsibilities** per explicit policy record |
| **Requirements (future)** | Delegator Cabinet, delegate Cabinet, responsibilities delegated, valid-from/to, revocable, audit trail |
| **Derives (§4)** | **Delegation** capability group — expression of transferred responsibilities, not a standalone organizational duty |

### 3.7. Responsibility combination rules

| Rule | Policy |
|------|--------|
| **Independence** | Responsibilities compose; absence of one does not imply absence of another unless policy forbids the combination |
| **Minimum line head (Draft proposal)** | Personnel + tasks + execution + results over **own unit subtree** — not HR processing |
| **Deputy admin (Draft proposal)** | Personnel oversight (кадровый контроль) + organizational information over approved scope — aligns with ACCESS-001 §3.3; **not** task responsibility over clinical units by default |
| **Director (Draft proposal)** | Results + organizational information at **org-wide or policy-defined executive subtree**; **кадровое решение** remains separate (ACCESS-001 §3.1) |

### 3.8. Derivation overview

```text
Management responsibilities (§3)          Derived capability groups (§4)
─────────────────────────────────          ────────────────────────────────
personnel          ───────────────────────►  visibility
tasks              ───────────────────────►  task management
execution          ───────────────────────►  task management (monitoring facet only)
results            ───────────────────────►  execution control; analytics (partial)
organizational     ───────────────────────►  analytics; visibility (partial)
information
delegation of      ───────────────────────►  delegation (transfer mechanism)
responsibility
```

**Governance rule:** policy matrices and approval workflows ratify **responsibilities** and **subtree scope**. Engineering maps approved responsibilities to capability groups at implementation time.

---

## 4. Derived management authority capability groups

The groups below are **derived** from §3 management responsibilities. They exist so that a future implementation can express organizational duties as enforceable capabilities. **They are not primary policy objects.**

A Position Cabinet receives a capability group **only because** it holds the corresponding responsibility (or receives it via §3.6 delegation). Capability groups without an underlying approved responsibility are **forbidden** in policy.

### 4.1. Visibility *(derived)*

| Aspect | Policy |
|--------|--------|
| **Derived from** | **Responsibility for personnel** (§3.1); partial derivation from **responsibility for organizational information** (§3.5) where read-only access suffices |
| **Technical meaning** | Read-only access to personnel, org structure, and (optionally) task/report **status** within the authorized subtree |
| **Not the same as** | HR processing (`HR_ENROLLMENT_MANAGER`), sysadmin API, or task assign/approve |
| **Legacy overlap** | ADR-042 E1 `personnel_visibility_assignments`; target state consolidates under Cabinet-anchored responsibility scope |

### 4.2. Task management *(derived)*

| Aspect | Policy |
|--------|--------|
| **Derived from** | **Responsibility for tasks** (§3.2); monitoring facet of **responsibility for execution** (§3.3). Requires the corresponding §3 responsibility — **not** derivable from personnel responsibility (§3.1) alone |
| **Technical meaning** | Create, assign, reassign, and monitor **operational tasks** for Positions/Cabinets within the authorized subtree — including regular-task template scope and catch-up visibility |
| **Not the same as** | Executing tasks as worker, HR enrollment, or org-wide sysadmin task admin |
| **Related** | ADR-010 — derived group at level 3 (head) is distinct from level 4 (employee execution) |

### 4.3. Execution control *(derived)*

| Aspect | Policy |
|--------|--------|
| **Derived from** | **Responsibility for results** (§3.4) exclusively — report acceptance and upward consolidation. **Not** derived from responsibility for execution (§3.3) |
| **Technical meaning** | Accept subordinate reports, approve completions, reject/return for rework, escalate within the management vertical |
| **Not the same as** | Task management (assigning work), HR **кадровое решение**, or analytics roll-up |
| **Related** | ADR-010 hierarchical reporting chain |

### 4.4. Analytics *(derived)*

| Aspect | Policy |
|--------|--------|
| **Derived from** | **Responsibility for organizational information** (§3.5); partial derivation from **responsibility for results** (§3.4) where roll-up indicators are part of result ownership |
| **Technical meaning** | Access aggregated indicators, statistical reports, and management dashboards for the authorized subtree |
| **Not the same as** | Line visibility alone, task assignment, or org-wide sysadmin reporting |
| **Scope default** | Subtree of anchor org unit; org-wide analytics only where organizational information responsibility is explicitly approved at executive scope |

### 4.5. Delegation *(derived)*

| Aspect | Policy |
|--------|--------|
| **Derived from** | **Delegation of responsibility** (§3.6) — mechanism, not a standalone duty |
| **Technical meaning** | Time-bounded transfer of derived capability groups corresponding to delegated responsibilities from delegator Cabinet to delegate Cabinet |
| **Not the same as** | ADR-036 **acting**, permanent grant copy, or ACCESS-001 permission baseline |
| **Requirements (future)** | Delegator responsibilities, delegate Cabinet, derived groups, valid-from/to, revocable, audit trail |

### 4.6. Derivation integrity rules

| Rule | Policy |
|------|--------|
| **No orphan capabilities** | A capability group must trace to at least one approved §3 responsibility |
| **No responsibility by capability** | Approving **visibility** alone does not approve **responsibility for personnel** — ratify the responsibility, then derive |
| **Personnel does not imply tasks** | **Responsibility for personnel** (§3.1) derives **visibility** only. **Task management** requires **responsibility for tasks** (§3.2) and/or **responsibility for execution** (§3.3) |
| **Execution vs results** | **Responsibility for execution** (§3.3) derives **task management** (monitoring) only. **Responsibility for results** (§3.4) derives **execution control** exclusively. The two responsibilities do not share a derived group |
| **Combination follows responsibilities** | Line head minimum (§3.7) derives visibility + task management + execution control over own subtree — because responsibilities include personnel, tasks, execution, and results |
| **Implementation vocabulary** | Future Permission Template atoms, scope resolver flags, and UI labels may use capability group names — policy annexes use **responsibilities** |

---

## 5. Management hierarchy model

Management responsibilities are evaluated relative to **org structure** and the **reporting vertical** defined for regular tasks and operational governance.

### 5.1. Structural anchor

```text
Organization (single tenant)
        │
        ├── org_units (tree: parent_id hierarchy)
        │
        └── org-unique Position (exactly one org_unit anchor)
                 │
                 └── Position Cabinet ──► management responsibilities (§3)
                          │                      │
                          │                      └──► derived capability groups (§4)
                          │
                          └── authorized subtree (§6)
```

Each Position Cabinet has an **anchor org unit** — the org unit of its org-unique Position (ADR-050). Responsibility scope is computed from this anchor unless policy assigns a **cross-cutting anchor** (e.g. deputy with parent-unit scope).

### 5.2. Reporting vertical (informative)

Aligned with [ADR-010](../adr/ADR-010-regular-tasks-hierarchy.md):

| Level | Typical role | Management responsibility (§3) | Upward handoff |
|-------|--------------|----------------------------------|----------------|
| **4** | Line staff (ordinary worker) | **None** — outside ACCESS-002 management responsibility model | Report to level 3 |
| **3** | Line department head | **Responsibility for results** (accept level-4 reports); typically also tasks, execution, personnel (§3.7) | Report to level 2 |
| **2** | Deputy | **Responsibility for results** (accept level-3 consolidated reports) | Report to level 1 |
| **1** | Director | **Responsibility for results** (accept level-2 consolidated reports) | — |

**Policy rule:** **Responsibility for results** at level N (levels 1–3 only) applies to submissions from level N+1 **within the authorized subtree** for that Cabinet — not globally unless executive scope is approved. Level 4 Positions are task executors, not management-responsibility holders under this document.

### 5.3. Cross-cutting and staff functions

| Function | Hierarchy placement | Default subtree |
|----------|---------------------|-----------------|
| **HR service** (`Отдел кадров`) | Staff / support — not line command | HR operational contour (ADR-045); **not** line management subtree |
| **Statistics / QM** | Staff / support with organizational information responsibility | Defined analytics subtree — often org-wide read for approved roles only |
| **Administration deputies** | Executive branch | Parent or org-wide personnel/information remit; result responsibility only where ADR-010 level applies |

### 5.4. Transitional as-is edges (informative)

Until implementation, these **user-centric** structures remain authoritative at runtime:

| As-is artifact | Transitional role |
|----------------|-------------------|
| `org_unit_managers.user_id` | Unit head as Platform User — **not** Position Cabinet |
| `users.unit_id` | RBAC dept/subtree scope carrier |
| `personnel_visibility_assignments` | ADR-042 E1 visibility — orthogonal to Cabinet |
| Task `scope=team` / executor role | Task RBAC — not Cabinet-scoped |

Target state: management scope derives from **occupied Cabinet + responsibility policy**, with capability groups as implementation expressions, consumed by task routing, visibility, and resolver-aware scope algorithms in a future program.

---

## 6. Subtree management principle

### 6.1. Default rule

**Default authorized subtree** for a management responsibility = **org unit subtree rooted at the Cabinet's anchor org unit**, including the anchor node and all descendant `org_units`. Derived capability groups inherit the same subtree unless policy narrows or widens at the responsibility level.

```text
Anchor org unit (Position's org_unit)
        │
        ├── child unit A          ◄── included
        │       └── child unit A1 ◄── included
        └── child unit B          ◄── included

Sibling branch (peer of anchor)   ◄── excluded unless policy widens
Parent unit                       ◄── excluded unless deputy/executive policy applies
```

### 6.2. Narrowing

Policy may **narrow** subtree below the default:

| Narrowing | Example |
|-----------|---------|
| **Direct staff only** | Personnel responsibility limited to Positions with Employment in anchor unit — **not** descendant units |
| **Exclude subtree** | Organizational information responsibility on anchor unit aggregates only — `include_subtree=false` semantics |
| **Functional filter** | QM analytics over clinical group subset — via org group classification, not whole org tree |

Narrowing must be **explicit in policy** — never inferred from title string.

### 6.3. Widening

Policy may **widen** subtree above the default:

| Widening | Example | Guard |
|----------|---------|-------|
| **Parent-unit deputy scope** | Deputy admin personnel oversight over administration subtree | Must not auto-grant HR processing (ACCESS-001 P8) |
| **Org-wide executive scope** | Director result + organizational information responsibility | Requires executive approval — not default |
| **Multi-unit assignment** | ADR-042 E1-style ORGANIZATION or multi-dept scope | Target: Cabinet responsibility policy row, not ad-hoc user grant |

Widening **does not** substitute for ACCESS-001 baseline permissions.

### 6.4. Subtree vs Permission Template union (ADR-051)

When Person holds multiple Cabinets (совместительство, acting):

- **Effective access permissions** = union of Template permissions (ADR-051) — unchanged.
- **Management responsibility scope** = union of **authorized subtrees per responsibility** from each accessible Cabinet — evaluated per consumer; derived capability groups follow the same union.
- **No inheritance between Cabinets** — same as ADR-051 permission union: no rank-MAX; explicit responsibility on each Cabinet only.

### 6.5. Vacancy and liquidation

| Event | Subtree policy |
|-------|----------------|
| **Vacancy** | Management responsibilities remain **defined on Cabinet**; no Person receives scope until Employment opens access |
| **Acting overlay** | Person may receive acted Cabinet's responsibilities **only if** policy assigns them to that Cabinet contour — acting alone does not copy delegator's subtree |
| **Position liquidation** | Management responsibilities end with Cabinet lifecycle (ADR-050) — subtree anchor removed |

---

## 7. Relationship to ACCESS-001

ACCESS-001 and ACCESS-002 are **orthogonal policy layers** on the same Position Cabinet contour:

```text
                         Position Cabinet (contour)
                                    │
           ┌────────────────────────┼────────────────────────┐
           │                        │                        │
           ▼                        ▼                        │
      ACCESS-001               ACCESS-002                    │
      (orthogonal)             (this document)               │
           │                        │                        │
           ▼                        ▼                        │
   baseline access            management responsibilities     │
   permissions (§3)           + authorized subtree (§6)      │
   [ACCESS-001 track]                │                        │
           │                        ▼                        │
           │            derived management authority          │
           │            capability groups (§4)                  │
           │            ─ ─ ─ implementation-derived;           │
           │                not normative policy ─ ─ ─        │
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    ▼
                         future runtime permissions
                         (enforcement — separate program;
                          no Draft effect)
```

| Dimension | ACCESS-001 | ACCESS-002 |
|-----------|------------|------------|
| **Question answered** | Which `access_roles.code` may bind to this contour? | Which **management responsibilities** over which **subtree**? |
| **Examples** | `HR_ENROLLMENT_MANAGER`, future кадровое решение code | Line head personnel + task + result responsibilities; deputy organizational information |
| **Enforcement path (future)** | ADR-053 Template binding → ADR-051 expansion | Consumer scope resolver (tasks, visibility, reports) |
| **OPS gate** | [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) | No OPS runbook in Draft |
| **Class overlap** | §3 кадровые классы (решение / оформление / контроль / информирование) | §3 управленческие responsibilities; §4 derived capability groups |

**Explicit rule:** approving `HR_ENROLLMENT_MANAGER` for a contour in ACCESS-001 **does not** approve any ACCESS-002 management responsibility for that contour, and vice versa.

**Shared contour examples (Draft):**

| Contour | ACCESS-001 (Reviewed) | ACCESS-002 (Reviewed) |
|---------|-------------------|-------------------|
| Line head `(42, 74)` | Rejected for `HR_ENROLLMENT_MANAGER`; §3.4 информирование | **Personnel + tasks + execution + results** over unit 42 subtree → derives visibility, task management, execution control |
| HR head `(73, 86)` | Pending — likely §3.2 оформление | **No line management subtree**; HR operational scope only |
| Director `(78, 62)` | Rejected `SYSADMIN_CABINET`; §3.1 решение TBD | **Results + organizational information** at executive scope; not sysadmin |
| Deputy admin `(78, 77)` | Pending — likely §3.3 контроль | **Personnel oversight + organizational information** for кадровый контроль scope |

---

## 8. Relationship to ADR-050 / ADR-051 / ADR-053

### 8.1. ADR-050 — Organization Position & Position Cabinet Model

| ADR-050 contract | ACCESS-002 use |
|------------------|----------------|
| Org-unique Position anchored to org unit | **Anchor org unit** for subtree computation (§5.1, §6.1) |
| Position Cabinet 1:1 with Position | **Management responsibilities** attach to Cabinet policy — not User |
| Permission Template on Cabinet | Management responsibilities attach to Cabinet policy — not User; encoding mechanism is implementation scope (§9) |
| `org_unit_managers.user_id` transitional | ACCESS-002 target replaces user-centric head edges (§5.4) |

ACCESS-002 **does not** amend ADR-050 lifecycle or entity definitions.

### 8.2. ADR-051 — Cabinet Access Resolution

| ADR-051 contract | ACCESS-002 use |
|------------------|----------------|
| Accessible Cabinets from Employment (+ acting) | Person receives management scope only from Cabinets they can access |
| Effective Permission Set = Template union | **Separate** from management responsibility subtree union (§6.4) |
| Org scope from Position/Cabinet placement | Aligns with M1 — target replaces `users.unit_id` as scope carrier |
| Active Cabinet context | Scoped management actions (e.g. accept report **as** head Cabinet) use active context |
| No inheritance between Cabinets | Same non-inheritance rule for management responsibilities (§6.4) |

ACCESS-002 defines **policy inputs** for a future management-scope consumer (not ADR-051 core) to load alongside Cabinet Access Resolver outputs. Consumer design is implementation scope (§9).

### 8.3. ADR-053 — Permission Template Binding Model

| ADR-053 contract | ACCESS-002 use |
|------------------|----------------|
| `access_role_id` baseline binding (ACCESS-001) | **Does not** encode subtree or management responsibility |
| Transitional single-code expansion (Phase 2.6) | Insufficient for management responsibilities and subtree scope — consumer design is implementation scope (§9) |
| Contour rules ops-approved only | ACCESS-002 contour matrix (future §9) follows same governance pattern — separate annex |
| Shadow parity vocabulary | Management scope has **no shadow mode** — not part of Phase 2.6 |

ACCESS-002 **does not** block or enable OPS-030. Phase 2.6 binding remains ACCESS-001 + ADR-053 scope only.

---

## 9. Future implementation notes (no runtime effect)

The following are **informative placeholders** for a future program. **Nothing in this section is executable at Reviewed status** — implementation planning requires **Approved** status (§9.3).

### 9.1. Planned deliverables (TODO)

| Item | Description |
|------|-------------|
| **Management responsibility matrix** | Contour → responsibility set → subtree rule annex (mirror ACCESS-001 §5 structure); capability groups derived at implementation |
| **Management Scope Resolver** | Consumer component: given Person + time T, compute authorized subtrees per responsibility from accessible Cabinets; emit derived capability groups |
| **Cabinet policy storage** | Schema TBD — possibly Template atomic permissions, `management_responsibility_contour_rule`, or hybrid |
| **Legacy edge migration** | Retire `org_unit_managers.user_id`; re-home ADR-042 visibility targets to Cabinet responsibility policy where appropriate |
| **Task routing alignment** | ADR-010 levels + ADR-049 consumer migration — `scope=team` from Cabinet subtree, not `users.unit_id` |
| **Delegation registry** | Time-bounded responsibility transfer records per §3.6 |
| **OPS runbook** | Future OPS item (not numbered in Draft) — execution gated on ACCESS-002 **Approved** |

### 9.2. Explicit non-goals until Approved

- No migrations, API changes, or UI for management authority configuration.
- No automatic backfill from `org_unit_managers`, `users.unit_id`, or ACCESS-001 matrix rows.
- No change to ADR-053 Phase 2.6 shadow or enforcement timeline.
- No conflation of ACCESS-002 responsibilities or derived groups with ACCESS-001 `access_roles.code` without explicit crosswalk approval.

### 9.3. Suggested approval workflow

```text
Draft → Reviewed → Approved
```

Same governance pattern as ACCESS-001 §4. Future implementation and any OPS runbook may begin **only** after ACCESS-002 reaches **Approved** and contour/responsibility matrix is ratified. **Reviewed** status does not authorize implementation, data changes, or OPS execution. Phase 2.6b and [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) remain blocked on the ACCESS-001 + ADR-053 track.

### 9.4. Dependency ordering (informative)

```text
ADR-050 ──► ADR-051 ──► ADR-053 ──► ACCESS-001 ──► OPS-030
                │
                └──► ACCESS-002 ──► (future management-authority implementation)
```

ACCESS-001 and ACCESS-002 are both **Reviewed**. Architecture design for the Organizational Policy Layer is complete; project phase is **Policy Ratification** (Reviewed → Approved). Must not be conflated with OPS-030 execution gates. **Reviewed** status does not affect Phase 2.6b blockers — **Approved** policy required.

---

## 10. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial Draft — management authority classes, hierarchy, subtree principle, ACCESS-001 / ADR-050/051/053 relationships |
| 2026-07-04 | 0.2 | Refactored to responsibility-first model (§3); authority classes reframed as derived capability groups (§4); M0 derivation principle; section renumbering |
| 2026-07-04 | 0.3 | Targeted cleanup — M5 acting/delegation; personnel→visibility-only; execution/results derivation split; §7 diagram; §5.2 hierarchy; §8 ADR wording |
| 2026-07-04 | — | **Reviewed** — final architecture acceptance review completed; no architectural blockers identified; advanced Draft → Reviewed; no runtime effect |
