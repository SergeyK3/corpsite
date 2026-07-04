# ARCH-001 — Foundation Architecture Summary

## Document metadata

| Field | Value |
|-------|-------|
| Status | **Draft — Architecture Review** |
| Date | 2026-07-03 |
| Baseline | [ARCH-001 v0.5 — Position Cabinet Architecture](./ARCH-001-position-permission-model.md) |
| Program | [ARCH-001-assessment-program.md](./ARCH-001-assessment-program.md) |
| Purpose | Consolidated conclusions from completed foundation assessments — not a new assessment |
| Source assessments | [tasks](./ARCH-001-task-subsystem-assessment.md), [positions-org-structure](./ARCH-001-positions-org-structure-assessment.md), [personnel-employment](./ARCH-001-personnel-employment-assessment.md), [access-rbac](./ARCH-001-access-rbac-assessment.md), [platform-user-identity](./ARCH-001-platform-user-identity-assessment.md) |
| Implementation contracts | [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md), [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) (**Accepted**) |
| Consolidation review | [ARCH-001-foundation-consolidation-review.md](./ARCH-001-foundation-consolidation-review.md) |

**Constraints applied:** this document consolidates existing assessment findings only. It does not modify ARCH-001, ADRs, assessment conclusions, or the assessment queue.

---

## 1. Executive Summary

Five subsystem assessments — one operational pilot (Tasks) and four Tier-1 foundation assessments (Positions & Org Structure, Personnel & Employment, Access & RBAC, Platform User & Identity) — have been completed against ARCH-001 v0.5.

**Overall conclusion:** all five assessments confirm that **ARCH-001 is sufficient** as the architectural baseline for Corpsite's operational contour. **No new core domain entity** is required beyond what ARCH-001 already defines: Person, Employment (Занятие должности), org-unique Position, Position Cabinet, Permission Template, Permissions, and Platform User (auth only).

The gap across every foundation area is **not conceptual** — it is **implementation alignment**. The current runtime is **user-centric and Employee-centric**: operational meaning, permissions, task routing, and much of identity context live on `public.users` and `public.roles`, while org-unique Position, Position Cabinet, and the Cabinet Access Resolver do not exist in schema or enforcement.

**Foundation phase outcome:**

| Dimension | Status |
|-----------|--------|
| Baseline adequacy | **Confirmed** — ARCH-001 need not be revised for foundation scope |
| As-is compatibility | **Not compatible** without foundational migration |
| Critical path ADRs | [**ADR-050**](../adr/ADR-050-organization-position-cabinet-model.md) (org-unique Position + Position Cabinet), [**ADR-051**](../adr/ADR-051-cabinet-access-resolution.md) (Cabinet Access Resolver) — both **Accepted** |
| Consumer assessments | **Unblocked to proceed** — they inherit foundation conclusions; they do not redefine the baseline |

Implementation contracts [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) and [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) are **Accepted** (2026-07-04). **Phase 2 schema work** may proceed per [IMPLEMENTATION_PLAN](./IMPLEMENTATION_PLAN.md); **enforcement cutover** remains phased per roadmap. Do not bind to catalog FKs, `users.role_id`, or role-centric routing for new operational logic.

---

## 2. Confirmed Architectural Chain

The foundation assessments converge on the following chain as the **confirmed target model** (from ARCH-001; validated, not invented):

```text
Platform User
        │
   (Authentication)
        ▼
Person
        ▼
Active Employments
        ▼
Position
        ▼
Position Cabinet
        ▼
Permission Template
        ▼
Effective Permissions
```

### Layer responsibilities

| Layer | Responsibility | Confirmed by |
|-------|----------------|--------------|
| **Platform User** | Login, password, account status, JWT subject, Telegram delivery endpoint, authentication audit (`actor_user_id`). **Does not** own org meaning, permissions, tasks, or cabinets. | platform-user-identity, access-rbac, ARCH-001 §3.7 |
| **Authentication** | Credential verification, JWT issuance/validation (`sub`, `exp`, optional `token_version`). **No** role or permission claims in token. | platform-user-identity, access-rbac |
| **Person** | Canonical identity anchor for a human (IIN, FIO, durable across employments). **Not** Employee, User, Position, or Cabinet. | personnel-employment, platform-user-identity |
| **Active Employments** | Time-bounded facts that Person occupies org-unique Position(s); opens access to corresponding Cabinet(s). Acting overlay (ADR-036) adds temporary second Cabinet access without mutating primary Employment. | personnel-employment, access-rbac |
| **Position** | Org-unique staffing unit in structure (not global title catalog). 1:1 with Position Cabinet. | positions-org-structure |
| **Position Cabinet** | Long-lived operational container owned by Position: tasks, reports, journals, statistics, documents (function), **Permission Template**. Survives vacancy and Person change. | All foundation assessments; tasks (executor/owner) |
| **Permission Template** | Named permission bundle **inside** Cabinet (as-is analog: `public.roles` codes — not assigned directly to User in target). | access-rbac, positions-org-structure |
| **Effective Permissions** | Union of Permissions from all Cabinets accessible to Person at time T (multi-employment + acting). Optional `access_grants` as **exception overlay**, not baseline. | access-rbac, ARCH-001 §3.6, §10, §15 |

**Operational ownership** (tasks, reports, cabinet statistics) belongs to **Position Cabinet**, not Person or Platform User. **Person** retains explicit exceptions: initiator-centric approve (ADR-023), report authorship attribution, Personal File (ARCH-001 §4.5).

---

## 3. Confirmed Architectural Invariants

Invariants **confirmed** by the completed assessments (all sourced from ARCH-001 and validated against as-is code):

### Ownership & lifecycle

| # | Invariant | Source |
|---|-----------|--------|
| 1 | **Position Cabinet belongs to Position** — 1:1; created together; same lifecycle; Cabinet survives vacancy and Person change | positions-org-structure, ARCH-001 §4.2 |
| 2 | **Operational objects belong to Cabinet first**, not Platform User or Person (with documented Person exceptions) | tasks, ARCH-001 §4.5 |
| 3 | **Person does not own Cabinet** — access is period-bound via Employment | personnel-employment, ARCH-001 §3.2, §4.3 |
| 4 | **Vacant Cabinet is a normal architectural state** — Cabinet persists; process policy for tasks/notifications is business policy (§4.7.2) | positions-org-structure, personnel-employment |
| 5 | **Employee is operational shell**, not Employment truth nor Cabinet owner — `person_assignments` is the Employment episode model | personnel-employment |
| 6 | **Position ≠ global title catalog** — as-is `public.positions` is technical debt, not ARCH-001 Position | positions-org-structure |

### Access & identity

| # | Invariant | Source |
|---|-----------|--------|
| 7 | **Employment grants access** to Position Cabinet for the employment period (+ acting overlay) | personnel-employment, access-rbac |
| 8 | **Platform User performs authentication only** in target model — login/password/account/Telegram transport | platform-user-identity, ARCH-001 §8 |
| 9 | **Person is the identity anchor** for authorization subject (via User linkage) | platform-user-identity, personnel-employment |
| 10 | **JWT is authentication only** — no role, permission, or org claims in token today (must remain so) | platform-user-identity, access-rbac |
| 11 | **Authorization derives from Employment → Cabinet → Permission Template** — not from `users.role_id` in end state | access-rbac |
| 12 | **Effective permissions = union** of accessible Cabinets (multi-employment, acting) | access-rbac, personnel-employment, tasks ("My Tasks") |
| 13 | **Login is stable** across transfer, role change, and rehire — does not encode role/position/org (OPS-028) | platform-user-identity |

### Tasks (operational consumer, assessed early)

| # | Invariant | Source |
|---|-----------|--------|
| 14 | **Task instance owner = executor Position Cabinet**; template owner = owner Position Cabinet | tasks |
| 15 | **Initiator / approver control may remain Person/user-specific** (ADR-023 exception preserved) | tasks, ARCH-001 §4.5 |
| 16 | **Telegram delivery endpoint = Platform User**; routing resolves from Cabinet → occupants | tasks, platform-user-identity |

---

## 4. Transitional Architecture

Runtime concepts that **exist today** but are **not** permanent architecture under ARCH-001. Classifications come from foundation assessment findings.

| Concept | Classification | Why transitional / legacy | Target owner |
|---------|----------------|---------------------------|--------------|
| **`users.role_id`** | **Transitional → Legacy** | Single Platform Role on User; ops permission center, task mine scope, admin heuristics | Permission Template via Cabinet Access Resolver |
| **`public.roles` as user assignment target** | **Transitional** | Global catalog doubles as Permission Template; assigned to User not Cabinet | Permission Template inside Cabinet |
| **`executor_role_id` / role-centric task routing** | **Transitional** | Tasks route to role, not cabinet | `executor_cabinet_id` (conceptual) |
| **`users.unit_id` on User row** | **Transitional** | Directory dept RBAC scope on auth entity | Employment / Cabinet org scope |
| **`users.employee_id` bridge** | **Transitional** | 1:1 User↔Employee; indirect Person path | Person linkage; Employee as optional shell |
| **`employees` as runtime anchor** | **Transitional** | Directory CRUD, terminate, documents, user create keyed on `employee_id` | Person + Employment |
| **Employee snapshot fields** (`org_unit_id`, `position_id` on `employees`) | **Transitional** | Dual-write with `person_assignments`; authoritative in many paths | Derived from Employment; org-unique Position FK |
| **Catalog `position_id`** (`public.positions` global title) | **Legacy** | Not org-unique Position; used in assignments, visibility, `/auth/me` | Org-unique Position (ADR-050) |
| **`/auth/me` role + single position fields** | **Transitional** | Bundles auth, authorization, one position | Identity + `accessible_cabinets[]` + resolver output |
| **`access_grants` on USER / ROLE targets** | **Transitional** | ADR-042 overlay; partial enforcement | Exception overlay only (ARCH-001 §15) |
| **`personnel_visibility_assignments`** | **Transitional** | E1 USER/POSITION/DEPARTMENT targets | Cabinet visibility permissions |
| **Env role allowlists** (`DIRECTOR_ROLE_IDS`, `DIRECTORY_PRIVILEGED_*`, etc.) | **Legacy** | Undocumented policy in config | Cabinet Template / org policy |
| **`role_id == 2` system admin hardcode** | **Transitional** | Break-glass until admin Cabinet/grant policy | Platform admin permission via grants or designated Cabinet |
| **Pilot role-based logins** (`qm_head@corp.local`) | **Legacy** | Seed artifact; grandfathered (OPS-028) | Person-based login format |
| **`users.full_name` duplicate** | **Legacy** | Copied from employee on create | Person canonical FIO |
| **`google_login` = login** | **Legacy** | Legacy column on create | Auth-only fields |
| **`X-User-Id` header** | **Legacy** | Dev migration fallback | JWT only |
| **Terminate employee → deactivate User** | **Transitional** | Conflates employment end with account lifecycle | Policy-separated: revoke cabinet access; optional account disable |
| **Acting via `users.role_id` swap** | **Legacy anti-pattern** | ADR-036 deferred; explicit non-goal for MVP | ACTING overlay → second Cabinet |

### Permanent (technical) — remain on Platform User or transport

| Concept | Classification |
|---------|----------------|
| `user_id`, `login`, `password_hash` | **Permanent** (technical) |
| JWT `sub`, lockout, `token_version`, `must_change_password` | **Permanent** (technical) |
| `users.telegram_id` (delivery endpoint) | **Permanent** (technical) |
| Security audit `actor_user_id` for auth events | **Permanent** (technical) |
| Person, Employment, Position, Position Cabinet, Permission Template | **Permanent** (architectural) |
| Org structure (`org_units`) as organization truth | **Permanent** (architectural) |

---

## 5. Confirmed Migration Dependencies

Dependency graph **as identified across foundation assessments** (consolidation only):

```text
ADR-050
  Org-unique Position schema
  Position Cabinet entity (1:1 with Position)
  Permission Template storage inside Cabinet
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
ADR-051                           Personnel alignment
  Cabinet Access Resolver            Person materialization (ADR-048)
  Inputs: Person, active Employments,  Employment FK → org-unique Position
          ACTING overlays              Close Employee-centric dual-write
        │
        ▼
RBAC / Identity migration
  Demote users.role_id, users.unit_id
  /auth/me → accessible_cabinets[], effective permissions
  Enforcement gate (shadow → cutover)
        │
        ├──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
  ADR-049 +        ADR-042 B5/E1   ADR-044 +      OPS-028
  ADR-023/020/024  visibility      User/Person    login policy
  (Tasks)          grants          linkage        implementation
        │
        ▼
Consumer subsystem migration
  Events & Telegram, Working Contacts, Directory Contacts,
  Personal UI Shell, HR Import, Employee Documents, Org Sync
```

**Hard gates (no implementation before):**

| Gate | Blocks |
|------|--------|
| **ADR-050** | Cabinet access resolver design, Employment FK retarget, vacancy at Position level, acting → Cabinet, any cabinet FK on tasks |
| **ADR-051** | Effective permission calculation, multi-cabinet union, `/auth/me` cabinet list, RBAC enforcement cutover |
| **Person materialization** (ADR-048) | Reliable Person from User; grant/resolver paths; identity chain |
| **ADR-049 + task ADR amendments** | Task cabinet re-binding (can be planned in parallel; must not ship without coexistence rules) |

**Explicit non-starters** (repeated across assessments):

- Do not implement Cabinet access on catalog `(org_unit_id, position_id)` composite.
- Do not treat `users.role_id` as standing in for Employment or acting.
- Do not assume `person_assignments.position_id` is org-unique Position until ADR-050.

---

## 6. Assessment Results Matrix

| Assessment | Verdict | Baseline sufficient | Blockers | New entities required |
|------------|---------|---------------------|----------|----------------------|
| **[Tasks](./ARCH-001-task-subsystem-assessment.md)** (Tier 0 pilot) | ARCH-001 sufficient; re-bind tasks from role/user to **executor/owner Cabinet**; Person kept for initiator/audit | **Yes** | ADR-049; ADR-023, ADR-020, ADR-024 amendments; ADR-050/051 for cabinet FKs and access | **None** |
| **[Positions & Org Structure](./ARCH-001-positions-org-structure-assessment.md)** | ARCH-001 sufficient; as-is **not compatible** — global title catalog ≠ org-unique Position; no Cabinet entity | **Yes** | **ADR-050** (org-unique Position + Cabinet schema) | **None** |
| **[Personnel & Employment](./ARCH-001-personnel-employment-assessment.md)** | ARCH-001 sufficient; partial Person/assignments; **Employee-centric runtime** | **Yes** | **ADR-050**; Person materialization (ADR-048); ADR-051 for Cabinet access; ADR-036 acting | **None** |
| **[Access & RBAC](./ARCH-001-access-rbac-assessment.md)** | ARCH-001 sufficient; **user-centric RBAC** not cabinet-compatible; JWT auth separation OK | **Yes** | **ADR-050**, **ADR-051**; ADR-023, ADR-042 B5/E1, dep-admin grants; Person on all users | **None** |
| **[Platform User & Identity](./ARCH-001-platform-user-identity-assessment.md)** | ARCH-001 sufficient; User **can stay auth-only**; Person link indirect/incomplete | **Yes** | ADR-048, ADR-042 B5, ADR-044, ADR-051; OPS-028 implementation; decouple terminate/account | **None** |

**Cross-cutting blocker summary:** every foundation assessment that touches access or operations is blocked on **ADR-050 → ADR-051** in that order. Tasks additionally require **ADR-049** and task-routing ADR amendments before implementation cutover.

---

## 7. Remaining Program

Tier-1 **foundation assessments are complete**. Remaining queue items (Tiers 2–4) are **consumer subsystems**: they **consume** the confirmed chain (Person → Employment → Cabinet → Permissions) rather than defining it.

| # | Subsystem | Tier | Why consumer (not foundation) |
|---|-----------|------|-------------------------------|
| 5 | **Events & Telegram** | Operational | Delivery infrastructure; binds to Platform User for transport; recipients/tasks already assessed — validates bot, bindings, non-task future against Cabinet→occupant model |
| 6 | **Working Contacts** | Operational | Read model over `users` + `employees`; assumes foundation identity/RBAC conclusions |
| 7 | **Directory Contacts** | Operational | Contact contour and predicates; org/person vs cabinet scoping |
| 8 | **Personal UI Shell** | UI | Post-login UX, ADR-007 «личный кабинет» vs Position Cabinet; needs foundation auth + access conclusions |
| 9 | **Personal File** | HR exception | ARCH-001 §4.5 Person-bound exception — validates boundary, does not define Cabinet |
| 10 | **HR Import & Canonical Registry** | HR truth | Full roster import; Person/Employment sync boundaries, not Cabinet ownership |
| 11 | **Employee Documents** | HR / ops split | Personal vs professional vs Cabinet function documents |
| 12 | **Org Sync & Admin** | Platform | Reference data, sync runbooks; indirect coupling to Position/Cabinet config |

**Dependency rationale (from program):** foundation graph edges `ACC → UIS`, `ACC → WC`, `ACC → DC`, `PUI → UIS`, `TSK → EVT`, etc. Consumers **must not** redefine Position, Employment, Cabinet, or resolver semantics — they report fit, gaps, and ADR amendments within their contour only.

**Next default assessment:** `events-telegram` (queue #5) per [assessment program](./ARCH-001-assessment-program.md).

---

## 8. Readiness Assessment

### Architecture readiness

| Criterion | Ready? | Notes |
|-----------|--------|-------|
| Baseline model defined (ARCH-001) | **Yes** | v0.5 draft; foundation assessments did not require baseline revision |
| Foundation subsystem fit assessed | **Yes** | Five assessments complete |
| Confirmed chain & invariants documented | **Yes** | This summary + source assessments |
| Critical path ADRs identified | **Yes** | ADR-050, ADR-051 primary; subsystem ADRs catalogued in each assessment §8 |
| Consumer scope bounded | **Yes** | Tiers 2–4 inherit foundation; no new core entities expected |

**Architecture readiness for implementation planning: YES** — the organization-centric model is confirmed adequate; gaps are migration and ADR work, not baseline redesign.

### Implementation readiness

| Criterion | Ready? | Notes |
|-----------|--------|-------|
| ADR-050 (Position + Cabinet schema) | **Accepted** | Ratified 2026-07-04; schema implementation per Phase 2 |
| ADR-051 (Cabinet Access Resolver) | **Accepted** | Ratified 2026-07-04; resolver implementation per Phase 4 |
| Schema exists for org-unique Position / Cabinet | **No** | positions-org-structure finding |
| Resolver implemented or shadowed | **No** | access-rbac finding |
| Person universal on operational users | **No** | personnel-employment P2 |
| Task ADR coexistence (ADR-049) | **No** | tasks assessment |
| Consumer subsystems assessed | **No** | Eight assessments remain — inform migration sequencing, not baseline |

**Implementation readiness: PARTIAL** — ADR-050 and ADR-051 are **Accepted**; Phase 2 schema work may begin. Cabinet binding, resolver enforcement, and role demotion in production paths remain phased per roadmap (ADR-049 for tasks, ADR-042 B5/E1 for auth/me and visibility).

### Distinction

| | Architecture readiness | Implementation readiness |
|---|------------------------|---------------------------|
| **Question** | Is the target model right and complete? | Can we safely build and cut over? |
| **Foundation phase answer** | **Yes** — ARCH-001 sufficient, no new entities | **Partial** — ADR contracts Accepted; schema/resolver/cutover remain |
| **Next step** | Continue Tier 2 consumer assessments | Phase 2 Position/Cabinet schema per IMPLEMENTATION_PLAN |

---

## Related documents

| Document | Role |
|----------|------|
| [ARCH-001-position-permission-model.md](./ARCH-001-position-permission-model.md) | Baseline (unchanged) |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md), [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | Implementation contracts (**Accepted**) |
| [ARCH-001-assessment-program.md](./ARCH-001-assessment-program.md) | Queue and rules (unchanged by this summary) |
| [ARCH-001-implementation-roadmap.md](./ARCH-001-implementation-roadmap.md) | Post-approval implementation sequencing (Phases 0–8) |
| [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) | Engineering work packages per roadmap phase |
| Individual `ARCH-001-*-assessment.md` | Source detail for each subsystem |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 1.0 | Initial foundation consolidation after Tier-0 + Tier-1 assessments complete |
| 2026-07-03 | 1.1 | Link ADR-050/051 (Proposed); clarify implementation planning vs approval gate |
| 2026-07-04 | 1.2 | ADR-050/051 status → Accepted; implementation readiness partial |
