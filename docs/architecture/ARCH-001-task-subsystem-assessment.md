# Architecture Assessment — Task Subsystem vs Position Cabinet Architecture

## Document metadata

| Field | Value |
|-------|-------|
| Status | **Draft — Architecture Review** |
| Date | 2026-07-03 |
| Scope | Assessment only — no code, schema, API, or ADR changes |
| Baseline | [ARCH-001 v0.5 — Position Cabinet Architecture](./ARCH-001-position-permission-model.md) |
| Purpose | Validate that Position Cabinet Architecture is sufficient to support the entire Task subsystem before implementation |

---

## 1. Executive summary

The existing Task subsystem is **functionally mature** (FSM, regular-task generation, ad hoc workflow, events, Telegram delivery, org filters) but **architecturally user-centric**. Tasks, visibility, actions, and notifications are routed through `public.users` and `public.roles` (`executor_role_id`, `users.role_id`, `initiator_user_id`), not through a durable organizational container.

**Conclusion:** ARCH-001 Position Cabinet Architecture is **sufficient and appropriate** as the target model for the Task subsystem. No new core domain entity is required beyond what ARCH-001 already defines. The transition is primarily a **re-binding** of operational references from Platform Role / Platform User to **Position Cabinet**, with Person retained for initiator control, audit attribution, and report authorship.

**Primary ownership recommendation:** operational task instances belong to the **executor Position Cabinet**. Regular task templates belong to the **owner Position Cabinet** (or a cabinet representing the organizational function that owns the reporting obligation). Person and Platform User must not be task owners.

**"My Tasks" recommendation:** in the target architecture, "My Tasks" means the **union of open tasks across all Position Cabinets the logged-in Person currently occupies** (primary employments + acting overlays), with an **active cabinet context** selector for focused work and a **combined view** as the default list.

**Implementation readiness:** architectural direction is clear; **implementation must not start** until a dedicated ADR amends task routing ADRs (especially ADR-023, ADR-020, ADR-024) and defines migration/coexistence rules. Estimated effort is a **multi-phase refactor**, not a schema-only patch.

---

## 2. Current state (as-is)

### 2.1. Domain model

| Layer | As-is entity | Role in Tasks |
|-------|--------------|---------------|
| Task instance | `public.tasks` | Central operational object; FSM-driven lifecycle |
| Regular template | `public.regular_tasks` | Scheduler source; dedupe key includes `executor_role_id` |
| Routing | `executor_role_id` → `public.roles` | Executor addressing; visibility and `can_report` |
| Control | `initiator_user_id`, `approver_user_id` → `public.users` | Initiator-centric approve (ADR-023) |
| Auth context | `users.role_id` (single) | "My Tasks" = tasks where `executor_role_id = users.role_id` |
| Org classification | `regular_tasks.owner_unit_id`, task owner unit fields | Org filter (unified org filter note); independent of executor |
| Events | `task_events`, `task_event_recipients`, `task_event_deliveries` | Backend source of truth; recipients resolved via role→users |
| Telegram | `users.telegram_id`, `tg_bindings.user_id` | Delivery channel bound to Platform User |
| HR link (partial) | `users.employee_id` → `employees.position_id` | Team-scope **position filter** only; not task ownership |

There is **no** `position_cabinet_id`, `executor_cabinet_id`, or equivalent in schema or services.

### 2.2. Key behavioural rules (as implemented)

**List scope `mine`** (`GET /tasks?scope=mine`):

```text
executor_role_id = current user's role_id
OR user submitted a report on the task
OR user is explicit approver (WAITING_APPROVAL)
OR legacy regular_tasks.target_role_id approver path
```

**List scope `team`:** manager visibility via `users.unit_id`, QM_HEAD team role sets, or system admin — still keyed to **role and user**, not cabinet.

**Actions (`can_report`, `can_approve`):** compare `current_role_id` to `executor_role_id`; initiator/approver checks use `user_id`.

**Regular task generation:** creates task with `executor_role_id` from template; `initiator_user_id` = system user; dedupe on `(regular_task_id, period_id, executor_role_id)`.

**Notifications** (`resolve_recipients_for_task_event_tx`): recipients = initiator + all active users with `role_id = executor_role_id` + management role set; Telegram delivery filtered to users with `telegram_id`.

**Position filter (team scope):** joins `users.role_id = executor_role_id` → `employees.position_id` — a **proxy** mapping from role to position name catalog, not org-unique Position.

### 2.3. Architectural character

The subsystem implements **Lean RBAC** (ADR-023): tasks route to **functional roles**, users inherit work through **one Platform Role per login**. This was intentional for pilot scalability but contradicts ARCH-001:

- Replacing an employee requires implicit reassignment via `users.role_id`, not cabinet access change.
- Acting (и.о.) has no first-class task context; workaround is role switching.
- Task history and statistics accrue to **role/user intersection**, not to a durable position container.
- Vacancy behaviour is undefined at domain level — tasks remain tied to a role code that may have zero active users.

### 2.4. Related ADRs (current task semantics)

| ADR | Relevant as-is decision |
|-----|-------------------------|
| ADR-010 | Hierarchy by management level; executor as user or org_unit in concept |
| ADR-020 | Regular tasks keyed by `executor_role_id`; generator idempotency on role |
| ADR-023 | `executor_role_id` + `initiator_user_id`; visibility/notify by role/user |
| ADR-024 | Ad hoc tasks same module; explicit initiator/approver users |
| ADR-012 | Events keyed to `actor_user_id`; assignee user/org in payload |
| ADR-006/007 | "Личный кабинет" = user entry point; not Position Cabinet |
| unified_org_filter | Task org-group by **owner unit**, not executor — already partially org-centric |

---

## 3. Target state (to-be)

Aligned with ARCH-001 v0.5.

### 3.1. Ownership model

```text
Regular Task Template  ──belongs to──►  Owner Position Cabinet
                                              │
                                              │ generates (per period)
                                              ▼
Task Instance          ──belongs to──►  Executor Position Cabinet
                                              │
                    Person accesses via ◄───────┘
                    Employment / ACTING overlay
```

| Candidate owner | Verdict | Rationale |
|-----------------|---------|-----------|
| **Person** | ✗ Not owner | Person is temporary; tasks must survive turnover (ARCH-001 §4.2, §4.6) |
| **Employment** | ✗ Not owner | Employment is an access grant period, not an operational container |
| **Position** | ◄ HR anchor | Position is the org fact; operational binding is through its Cabinet |
| **Position Cabinet** | ✓ **Primary owner** | ARCH-001 §4.5 invariant: tasks belong to cabinet, not login |
| **Platform User** | ✗ Not owner | Auth only (ARCH-001 §3.7, §8) |

**Split ownership (recommended):**

| Concern | Owner |
|---------|-------|
| Task instance lifecycle, backlog, cabinet statistics | **Executor Position Cabinet** |
| Regular task template, schedule, catch-up policy | **Owner Position Cabinet** (often same as executor; may differ for hierarchical reporting) |
| Initiator / approver control | **Person** (explicit ARCH-001 §4.5 exception; ADR-023 initiator-centric approve preserved) |
| Report submission, audit attribution | **Person** acting **in context of** a Cabinet (`person_id`, `cabinet_id`, `timestamp`) |
| Telegram delivery endpoint | **Platform User** (transport); routing resolved from Cabinet → current occupants |

### 3.2. Routing evolution

| As-is field | To-be field / resolution |
|-------------|--------------------------|
| `executor_role_id` | `executor_cabinet_id` (FK → Position Cabinet); Permission Template derived from cabinet |
| `regular_tasks.executor_role_id` | `owner_cabinet_id` + optional `executor_cabinet_id` if template specifies executor cabinet explicitly |
| Dedupe key | `(regular_task_id, period_id, executor_cabinet_id)` |
| `scope=mine` | Cabinets accessible to Person via active Employments + ACTING overlays |
| Visibility / `can_report` | Person has active access to executor cabinet **and** cabinet permissions include action |
| Recipients | Resolve occupants of relevant cabinets (executor, initiator's cabinet if needed, escalation cabinet) → Platform Users |

Permission Template (`QM_HOSP`, `DEP_OUTPATIENT_AUDIT`, etc.) becomes **configuration inside Position Cabinet**, not a standalone routing key on `public.roles`.

### 3.3. UI / session model

After login, Platform User sees **available Position Cabinets** (ARCH-001 §8, §10):

- **Active cabinet context** — selected cabinet; actions default to this context.
- **Combined "My Tasks"** — union across all accessible cabinets (see §4.2).
- **Team / supervisor views** — scoped by cabinet hierarchy or org structure, not `users.unit_id` alone.

Terminology: distinguish **личный кабинет** (user UI shell, ADR-007) from **Кабинет должности** (Position Cabinet, ARCH-001 §2.3).

---

## 4. Answers to assessment questions

### 4.1. Task ownership — recommendation

**Primary owner: Position Cabinet (executor cabinet for instances; owner cabinet for templates).**

Justification:

1. Matches ARCH-001 durability invariant — tasks persist through vacancy and person change without migration.
2. Aligns with organizational reality — reporting obligations attach to **functions in structure**, not individuals.
3. Supports multi-cabinet access (совместительство, и.о.) without duplicating tasks.
4. Permission Template lives in cabinet — routing and authorization co-locate.
5. Person remains in the loop only where management control is inherently personal (initiator approve, audit).

**Employment** opens/closes access; it does not own tasks. **Position** is the HR identity of the cabinet. **Platform User** must never appear as owner in domain model.

---

### 4.2. "My Tasks" — meaning and trade-offs

Three interpretive models:

| Model | Definition | Advantages | Disadvantages |
|-------|------------|------------|---------------|
| **A. Person-assigned** | Tasks explicitly assigned to Person | Simple mental model for ad hoc | Breaks on turnover; contradicts ARCH-001; poor fit for regular tasks |
| **B. Active cabinet only** | Tasks of the **currently selected** Position Cabinet | Clear context; avoids mixing responsibilities; matches "working in cabinet B" | User must switch context to see all work; easy to miss acting tasks |
| **C. Union of all cabinets** | All tasks from cabinets Person currently occupies | Complete operational picture; matches Telegram "what needs attention"; good for и.о. | Mixed list needs cabinet badges; risk of confusion without labelling |
| **D. Combined default (recommended)** | **Default = union (C)**; **optional filter = active cabinet (B)** | Balances completeness and focus; aligns with ARCH-001 §10 context switch | Requires UI affordances (cabinet chip, filter, counts per cabinet) |

**Recommendation:** **D — union as default, cabinet filter for focus.**

"My Tasks" is **not** "tasks of my Platform User" or "tasks matching my single `role_id`". It is **"tasks of Position Cabinets I can act in today"**.

Initiator-only tasks (where Person is approver but not executor) may appear as a **secondary slice** ("Awaiting my approval") — still Person-scoped for control, not ownership.

---

### 4.3. Multiple occupied positions (primary + acting)

ARCH-001 §9–§12 already defines the model. Task subsystem implications:

| Aspect | Recommendation |
|--------|----------------|
| **Cabinet separation** | **Yes — remain separate.** Primary cabinet and acting cabinet are distinct containers with distinct templates, backlogs, and statistics. |
| **Task list** | Default combined view with **cabinet label** on each row; filter by cabinet; optional "active context only". |
| **Actions** | Every mutation records **acting cabinet context** in audit (`cabinet_id`). Person must have active access to that cabinet. |
| **Permissions** | Effective permissions = union of both cabinets; action eligibility checked against **the cabinet of the task**, not global union. |
| **Regular tasks** | Amb tasks generate in Cabinet A; hosp и.о. tasks generate in Cabinet B — no cross-contamination. |
| **After acting ends** | Access to Cabinet B closes; Person's combined list loses B tasks; Cabinet B backlog **unchanged** for next occupant. |

**Combined view is required** for usability (Telegram, mobile, daily work). **Separate cabinet views are also required** for role clarity and statistics.

Example (ARCH-001 §12 — Akiltaeva и.о. hosp): during 05.07–25.07 she sees amb + hosp tasks; after 25.07 only amb tasks in default union; hosp cabinet unchanged for Seitkazina's return.

---

### 4.4. Vacancy — business policy options

Architecture (fixed per ARCH-001 §4.7.1): **Position Cabinet survives; Person disappears; tasks remain in cabinet.**

Only **process policy** is open. Options for organization configuration:

| Policy | Behaviour | Typical use |
|--------|-----------|-------------|
| **P1. Suspend generation** | Regular task scheduler skips vacant cabinets; existing open tasks remain | Strict "no executor" compliance |
| **P2. Hold and escalate** | Open tasks stay; notifications go to **supervisor cabinet** or org-unit head cabinet | Clinical continuity |
| **P3. Acting assignment** | ACTING overlay (ADR-036) opens cabinet to substitute; tasks flow normally | Planned leave |
| **P4. Acting queue without person** | Tasks visible to HR/admin cabinet until и.о. assigned | HR-managed vacancy |
| **P5. Auto-archive after N days** | Vacant cabinet tasks archived with reason | Low-criticality admin tasks |
| **P6. Position-type matrix** | Different policies per Permission Template / org group | Enterprise flexibility |

**Recommendation:** implement **policy registry per cabinet or template**, default **P2 + P3** for clinical roles, **P1** for optional admin reporting. Architecture does not mandate one policy.

Notifications during vacancy: no occupant → route to **escalation cabinet** or **acting cabinet** if overlay exists; never to departed Person.

---

### 4.5. Statistics — cabinet vs person

#### Position Cabinet statistics (organizational, durable)

| Indicator | Notes |
|-----------|-------|
| Open / overdue task count by period | Backlog health of the function |
| Regular task compliance rate | % instances completed on time vs generated |
| Average cycle time (create → approve) | Process efficiency of the position |
| Rejection rate | Quality signal for reports |
| Catch-up / scheduler gaps | Operational risk |
| Vacancy-period backlog delta | Policy effectiveness |
| Hierarchical roll-ups | Sum/average across child cabinets or org units |

Cabinet statistics **do not reset** on person change.

#### Person statistics (individual, tenure-bound)

| Indicator | Notes |
|-----------|-------|
| Tasks completed while occupying cabinet X | Performance during assignment |
| Reports submitted (count, timeliness) | Individual delivery |
| Approvals given as initiator | Managerial activity |
| Acting period contribution | Separate slice for и.о. |
| Audit trail of actions | `(person_id, cabinet_id)` pairs |

Person statistics are **historical attribution**, not ownership. After transfer, person retains **personal** history; cabinet retains **organizational** history.

**Rule of thumb:** if the metric answers "how is this **function** performing?" → cabinet. If "how did this **individual** perform in a role?" → person.

---

### 4.6. Regular tasks — belong to Position, Cabinet, or Person?

| Option | Verdict |
|--------|---------|
| Person | ✗ Templates must survive turnover |
| Position (HR) | ◄ Indirect — Position defines which cabinet exists |
| **Position Cabinet** | ✓ **Recommended owner** |

**Justification:**

1. Regular tasks encode **organizational reporting obligations** ("every month the hosp expert submits X") — a function of the position, not the individual.
2. Scheduler runs against **cabinet configuration** (template list inside cabinet or linked via `owner_cabinet_id`).
3. Catch-up on vacancy is a **cabinet policy** (§4.4), not a person policy.
4. Dedupe and idempotency naturally key on cabinet + period.
5. Hierarchical regular tasks (ADR-010) map to **cabinet hierarchy** (employee cabinet → head cabinet), not user hierarchy.

**Template placement:** store under **owner Position Cabinet**; generated instances carry **executor Position Cabinet** (may differ in hierarchical receive-report patterns).

---

### 4.7. Telegram notifications

#### Binding layers

| Layer | Bind to | Reason |
|-------|---------|--------|
| **Transport** | Platform User (`telegram_id`) | Channel is personal device identity |
| **Routing logic** | Position Cabinet | Event concerns a cabinet's task |
| **Resolution** | Person(s) with active cabinet access → their Platform User(s) | Last mile delivery |

Notifications **follow the task's cabinet**, resolved to **current occupants' Platform Users**. They do **not** follow a static role code or departed user.

#### Scenario behaviour

| Scenario | Behaviour |
|----------|-----------|
| **Normal occupancy** | Task event in Cabinet A → notify Platform Users of Person(s) with access to A |
| **Acting appointment** | Events for Cabinet B (acting) → notify acting Person's Platform User; Cabinet A events unchanged |
| **Employee replacement** | New occupant of same Position → same Cabinet → **automatic** notification routing; no rebind of task records |
| **Vacancy** | No occupant → apply escalation policy (§4.4): supervisor cabinet, admin alert, or hold |
| **Multi-user same cabinet** | Rare in target model (1 Position : 1 Cabinet : 1 primary occupant); if shared access exists, notify all active accessors |
| **APPROVED/REJECTED** | Notify report author Person (UX rule preserved) via their Platform User, plus initiator |

**Acting end:** stop notifying acting Person for Cabinet B; do not retroactively change past delivery logs.

---

### 4.8. Existing implementation — architectural mismatches

Places where the codebase remains **user-centric** (no code changes proposed; inventory only):

| Area | As-is coupling | ARCH-001 mismatch |
|------|----------------|-------------------|
| **Task schema** | `executor_role_id`, no cabinet FK | Ownership tied to Platform Role, not cabinet |
| **Regular tasks schema** | `executor_role_id`, `initiator_role_id`, `target_role_id` | Template routing by role catalog |
| **Task list `mine`** | `t.executor_role_id = :role_id` from `users.role_id` | Single-role assumption; ignores multi-cabinet |
| **Task list team** | `users.unit_id`, QM_HEAD role codes | Dept scope on user, not cabinet tree |
| **Position filter** | `users` → `employees.position_id` via role match | Proxies position catalog, not org-unique Position/Cabinet |
| **Visibility** | `_is_task_visible_to_user` via role_id sets | No cabinet access check |
| **`can_report_or_update`** | `current_role_id` vs `executor_role_id` | Action by role, not by cabinet permission |
| **`can_approve`** | `initiator_user_id`, `approver_user_id` | Partially correct (initiator Person); executor side role-based |
| **Auth `/auth/me`** | `role_id`, `can_view_all_tasks` from role heuristics | Single effective role; no cabinet list |
| **Event recipients** | `users.role_id = executor_role_id` | All users with role notified — wrong for vacancy, multi-position, и.о. |
| **Telegram** | `tg_bindings.user_id`, `task_event_deliveries.user_id` | Transport OK; routing input is user/role-centric |
| **Task events audit** | `actor_user_id`, optional `actor_role_id` | Missing `actor_person_id`, `cabinet_id` context |
| **Task reports** | `submitted_by`, `approved_by` as user_id | Missing cabinet context for attribution |
| **Manual task create** | Picks executor role from role catalog | No cabinet picker |
| **Regular task generator** | Inserts with `executor_role_id`; dedupe on role | Generator not cabinet-aware |
| **Org filter** | Owner unit on task/template | Aligned partially — but executor still role-based |
| **Pilot seed** | `employee_id = roles.code`, login per role | Anti-pattern per ARCH-001 §1.1 |
| **Employee transfer (ADR-032)** | Sync `users.unit_id`; no task migration | Confirms tasks aren't position-bound today |
| **UI task scope policy** | `can_view_all_tasks`, `defaultTaskScope(me)` | User capability flags, not cabinet grants |
| **Bot API** | Same `/tasks` handlers with user JWT | Inherits all mismatches above |

**No implementation area currently treats Position Cabinet as a first-class entity.**

---

### 4.9. Required ADRs

| Action | Document | Justification |
|--------|----------|---------------|
| **New ADR (required)** | e.g. **ADR-049 — Task Subsystem Position Cabinet Transition** | Single place for ownership, routing, migration, coexistence, dedupe key change, audit shape, notification resolution, vacancy policy hook |
| **Amend (required)** | **ADR-023** | Replace `executor_role_id` centric RBAC with cabinet-centric visibility/actions; preserve initiator Person approve |
| **Amend (required)** | **ADR-020** | Regular tasks owned by cabinet; scheduler policy; dedupe key |
| **Amend (required)** | **ADR-024** | Ad hoc tasks: executor/initiator addressing via cabinet |
| **Amend (recommended)** | **ADR-010** | Hierarchy in cabinet terms |
| **Amend (recommended)** | **ADR-012**, **ADR-022** | Event payload: `cabinet_id`, `actor_person_id`; recipient resolution rules |
| **Amend (recommended)** | **ADR-006**, **ADR-007** | Clarify личный кабинет vs Position Cabinet in Tasks UX |
| **Amend (recommended)** | **ADR-021** | `can_*` rules in cabinet context |
| **Cross-reference** | **ADR-036** | ACTING → temporary cabinet access drives task visibility |
| **Cross-reference** | **ADR-032** | Transfer closes cabinet access; no task migration |
| **Update after approval** | **ARCH-001** §13.2, §14 | Mark task assessment complete; narrow open questions |
| **No ADR change** | ADR-013 (JWT), ADR-047 (personal file) | Out of scope |

**Verdict:** **New ADR + amendments to existing task ADRs.** ARCH-001 alone is insufficient for implementation detail — it defines the domain; task ADRs define contracts that must be revised.

---

## 5. Gap analysis

| Capability | ARCH-001 target | As-is | Gap severity |
|------------|-----------------|-------|--------------|
| Durable task ownership | Cabinet | Role | **Critical** |
| Employee turnover | Access change only | Role/login reassignment | **Critical** |
| Acting (и.о.) | Second cabinet access | No model | **High** |
| Multi-position (совместительство) | Multiple cabinets | Single `users.role_id` | **High** |
| Vacancy handling | Cabinet persists + policy | Undefined / empty role users | **High** |
| Regular task scheduler | Cabinet-keyed | Role-keyed | **High** |
| Statistics continuity | Cabinet aggregates | Implicit via role history | **Medium** |
| Audit attribution | Person + cabinet | User only | **Medium** |
| Notifications | Cabinet → occupants | Role → all users with role | **High** |
| Org filter by owner unit | Yes | Partially implemented | **Low** |
| Initiator approve | Person | Person (`initiator_user_id`) | **None** |
| FSM / events infrastructure | Reuse | Mature | **None** (reuse) |
| Position Cabinet entity in DB | Required | Absent | **Critical** (prerequisite program) |

**Dependency:** Task subsystem transition **depends on** [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) (Position Cabinet entity) and [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) (Cabinet access). Tasks cannot migrate before cabinets exist, Employments map to them, and the access resolver contract is approved.

---

## 6. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Big-bang migration** | Production outage, lost visibility | Phased coexistence: dual-read role + cabinet; feature flag |
| **Role ↔ cabinet mapping ambiguity** | Wrong routing | Pilot matrix: each `roles.code` → Permission Template in specific cabinet; validate on real org structure |
| **`public.positions` vs Position** | Incorrect cabinet identity | Complete ADR-046 normalization before cabinet creation |
| **Initiator vs cabinet tension** | Approve rules break | Keep initiator as Person; document in ADR-023 revision |
| **Telegram routing change** | Missed or duplicate notifications | Shadow-mode recipient comparison before cutover |
| **QM_HEAD team view** | Supervisor dashboards break | Redefine team scope as cabinet hierarchy / org tree |
| **Dedupe key change** | Duplicate regular tasks | Migration script + unique index transition plan |
| **UI complexity** | User confusion with multi-cabinet | Cabinet badges, context selector, sensible defaults (§4.2) |
| **Vacancy policy absent** | Operational stall or silent backlog | Mandate default policy per template class before go-live |
| **Deferred transition** | Continued manual role swapping | ARCH-001 §13.4 — history loss on turnover |

---

## 7. Recommendations

### 7.1. Architectural decisions to lock before implementation

1. **Task instance owner = executor Position Cabinet** (non-negotiable per ARCH-001).
2. **Regular task template owner = owner Position Cabinet.**
3. **"My Tasks" = union of accessible cabinets** with active-context filter.
4. **Cabinets stay separated** under multi-position; combined view is a presentation layer.
5. **Initiator / approver remain Person-linked**; audit always records `(person_id, cabinet_id)`.
6. **Telegram: route by cabinet, deliver to Platform User.**
7. **Vacancy: configurable process policy** per template or cabinet class.
8. **No task migration on turnover** — only access grants change.

### 7.2. Non-goals for first implementation phase

- Rewriting FSM or event type taxonomy.
- Person-level task ownership for regular reporting.
- Binding Telegram to Person instead of Platform User (transport stays on user).
- Merging ARCH-001 with ADR-007 "личный кабинет" into one UI concept.

### 7.3. Coexistence strategy (recommended)

1. Introduce `position_cabinets` + employment → cabinet access (prerequisite).
2. Add nullable `executor_cabinet_id` / `owner_cabinet_id` on tasks and regular_tasks.
3. Backfill from `(role, org_unit, position)` mapping table — **pilot-specific, not generic role_id**.
4. Dual-read: resolve executor by cabinet if set, else fall back to `executor_role_id`.
5. Switch write path to cabinet-first; deprecate role executor for new tasks.
6. Remove fallback after validation window.

---

## 8. Proposed implementation roadmap

Phases are **sequential**; each ends with validation on pilot org structure.

### Phase 0 — Architecture gate (current)

- [x] Task subsystem assessment (this document)
- [ ] Architecture session: approve ownership, "My Tasks", vacancy default policies
- [ ] Author **ADR-049** and revision scope for ADR-023/020/024
- [ ] Approve ARCH-001 v0.5 → baseline in ARCHITECTURE_GOVERNANCE

### Phase 1 — Foundation (prerequisite program)

- Define Position Cabinet schema (1:1 Position)
- Employment / ACTING → cabinet access resolver
- `/auth/me` returns `accessible_cabinets[]` + permissions per cabinet
- No task schema change yet; prove access resolver

### Phase 2 — Dual model (tasks read path)

- Add cabinet FKs to `tasks`, `regular_tasks` (nullable)
- Backfill pilot cabinets
- Implement cabinet-based visibility alongside role fallback
- UI: cabinet selector + badges on task list (read-only experiment)

### Phase 3 — Write path + scheduler

- Manual/ad hoc task create uses `executor_cabinet_id`
- Regular task generator keys on cabinet; updated dedupe
- `can_report` / `can_approve` cabinet-aware
- Audit fields: `cabinet_id` on events and reports

### Phase 4 — Notifications

- Recipient resolver: cabinet → occupants → platform users
- Shadow diff vs role-based recipients
- Cutover Telegram routing

### Phase 5 — Deprecate role executor

- Remove `executor_role_id` from write paths (keep historical column read-only)
- Team scope on cabinet hierarchy
- Vacancy policy engine for scheduler + notifications
- Statistics split: cabinet dashboards + person tenure views

### Phase 6 — Pilot validation

- Scenarios: turnover, и.о. (ARCH-001 §12), vacancy, совместительство
- Compare task counts and notification delivery pre/post
- Ops runbook update (regular tasks scheduler, Telegram)

---

## 9. Conclusion

Position Cabinet Architecture **is sufficient** to host the full Task subsystem. The assessment found **no missing core concept** — only a systematic shift from **role/user routing** to **cabinet routing**, with Person retained for control and audit and Platform User retained for authentication and Telegram transport.

The existing implementation is **not blocking** reuse of FSM, events, regular-task machinery, or UI shells — but **every ownership, visibility, action, and notification path** must be re-grounded on Position Cabinet before the organization-centric model delivers its primary benefit: **continuity of operational work across HR change without migration**.

**Next step:** architecture session → **ADR-049** → Phase 1 foundation (Position Cabinet entity + access resolver).

---

## Related documents

| Document | Relation |
|----------|----------|
| [ARCH-001 v0.5](./ARCH-001-position-permission-model.md) | Target domain model |
| [ADR-023](../adr/ADR-023-rbac-v2-lean-scope-and-approvals.md) | Current task RBAC — requires amendment |
| [ADR-020](../adr/ADR-020-regular-tasks-contract-v1.md) | Regular tasks contract — requires amendment |
| [ADR-024](../adr/ADR-024-adhoc-tasks-contract.md) | Ad hoc tasks — requires amendment |
| [ADR-036](../adr/ADR-036-hr-events-unified-model.md) | ACTING overlay → cabinet access |
| [unified_org_filter](../adr/unified_org_filter.md) | Owner-unit org filter — compatible, extend |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 1.0 | Initial assessment — Task subsystem vs Position Cabinet Architecture |
