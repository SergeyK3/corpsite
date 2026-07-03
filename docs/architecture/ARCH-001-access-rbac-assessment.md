# Architecture Assessment — Access & RBAC vs Position Cabinet Architecture

## Document metadata

| Field | Value |
|-------|-------|
| Status | **Draft — Architecture Review** |
| Date | 2026-07-03 |
| Slug | `access-rbac` |
| Program | [ARCH-001-assessment-program.md](./ARCH-001-assessment-program.md) (queue #3) |
| Baseline | [ARCH-001 v0.5 — Position Cabinet Architecture](./ARCH-001-position-permission-model.md) |
| Prerequisite assessments | [positions-org-structure](./ARCH-001-positions-org-structure-assessment.md), [personnel-employment](./ARCH-001-personnel-employment-assessment.md), [tasks](./ARCH-001-task-subsystem-assessment.md) |
| Scope | Assessment only — no code, schema, API, or baseline changes |

---

## 1. Executive Summary

Corpsite implements **dual-layer authorization**: (1) **user-centric Platform RBAC** centered on `users.role_id` and `public.roles`, which drives tasks, directory scope, admin gates, and most UI flags; and (2) a **partial ADR-042 overlay** — `access_grants`, `access_roles`, and `personnel_visibility_assignments` — with a read-only effective-access resolver and **selective enforcement** (admin API, personnel admin, visibility scope). Authentication (JWT) is correctly separated from authorization (DB-loaded context per request), but authorization **does not** derive from Position Cabinet, Employment, or Permission Template as ARCH-001 defines.

**Verdict:** **ARCH-001 is sufficient** for the Access & RBAC domain. No new core architectural entity is required beyond Person, Employment, org-unique Position, Position Cabinet, and Permission Template already in the baseline. The gap is **implementation alignment**: the current subsystem is **not compatible** with cabinet-exclusive permission resolution without foundational migration.

**Can effective permissions be derived exclusively from active Employment → Position Cabinet → Permission Template today?** **No.** No `position_cabinets` entity exists; `users.role_id` remains the operational center; `access_grants` and env-based role allowlists provide parallel paths; acting and multi-employment are not represented in effective permission calculation.

**What blocks implementation before ADR-050 and ADR-051:**

| Blocker | Source assessment |
|---------|-------------------|
| Org-unique Position + Position Cabinet schema | ADR-050 (assessment #1) |
| Employment → Cabinet access resolver contract | ADR-051 (assessment #2) |
| Person materialization on all operational users | personnel-employment P2 |
| Permission Template relocation from `public.roles` / `users.role_id` | This assessment |

**Recommendation:** treat Access & RBAC as a **Tier-1 migration consumer** — design the cabinet access resolver only after ADR-050/051; meanwhile document and retire user-centric anti-patterns incrementally per subsystem ADRs (ADR-023, ADR-042 B5/E1, ADR-049).

---

## 2. AS-IS

### 2.1. Scope

| In scope | Out of scope (other queue items) |
|----------|----------------------------------|
| `users.role_id`, `public.roles` (Platform Role catalog) | Platform User identity policy detail (`platform-user-identity`) |
| `access_grants`, `access_roles`, `access_resolver_service` | Task FSM / routing detail (covered in `tasks` assessment) |
| `personnel_visibility_assignments`, E1 resolver | HR Import write paths (partial overlap via personnel admin) |
| `/auth/me`, JWT, `get_current_user`, guards | JWT transport ADR-013 (confirmed domain-independent) |
| Directory RBAC (`directory_scope`, `directory/rbac`) | Personal File Person exception |
| Admin guards (`admin_guard`, `admin_permissions`, `personnel_admin_guard`) | |
| Task RBAC enforcement (`tasks_service`, `tasks_router`) | |
| Regular tasks admin ACL | |
| UI authorization flags (`/auth/me` enrichment, `visibilityNav`, `taskScopePolicy`) | |
| Telegram bot auth (`bot_internal_auth`) | |
| Enrollment / HR governance permission codes | |

### 2.2. Authentication vs authorization (as-is)

| Layer | Mechanism | Domain coupling |
|-------|-----------|-----------------|
| **Authentication** | JWT HS256: claims `sub` (user_id), `iat`, `exp`, `token_version` only | **None** — correct transport boundary (ADR-013) |
| **Session context** | `get_current_user` → `_get_user_by_id` + `_enrich_user_context` | Loads `role_id`, `unit_id`, employee→position snapshot, privilege flags |
| **Authorization** | Per-route guards + inline checks on enriched user dict | **Heavy** domain coupling via `role_id`, `unit_id`, grants |

Authentication **does not** embed roles or permissions in JWT. Every authorized request re-resolves authorization from DB — good for revocation, but the **resolved model is user-centric**, not cabinet-centric.

### 2.3. Data model — permission-related tables

| Table / concept | Role in authorization |
|-----------------|----------------------|
| `public.users` | Auth identity; **`role_id`** (single Platform Role); **`unit_id`** (dept scope); **`employee_id`** bridge |
| `public.roles` | Platform Role catalog — task routing codes (`QM_HEAD`, `DEP_*`), UI labels; **de facto Permission Template stand-in** |
| `public.access_roles` | ADR-042 named access levels (`ACCESS_OBSERVER`, `SYSADMIN_CABINET`, `HR_ENROLLMENT_MANAGER`, …) |
| `public.access_grants` | Grants on targets: USER, ROLE, EMPLOYEE, PERSON, ASSIGNMENT, POSITION (catalog id), ORG_UNIT |
| `public.personnel_visibility_assignments` | E1 visibility: USER, POSITION (catalog), DEPARTMENT targets; scope ORGANIZATION / DEPARTMENT / DEPARTMENT_GROUP |
| `public.person_assignments` | Feeds POSITION / ORG_UNIT subject IDs into access resolver when Person linked |
| `public.employees` | Indirect: `users.employee_id` → snapshot `position_id`; EMPLOYEE grant target |
| Env allowlists | `DIRECTORY_PRIVILEGED_*`, `DIRECTOR_ROLE_IDS`, `DEPUTY_ROLE_IDS`, `SUPERVISOR_ROLE_IDS`, `DIRECTORY_DEPUTY_*` |

**Not present:** `position_cabinets`, cabinet-scoped permission templates, acting access overlay, multi-role union on user, cabinet context session.

### 2.4. Authorization subsystems (behavioural map)

#### 2.4.1. Directory / org structure RBAC

- **`is_privileged(user_ctx)`** — `role_id == 2` (SYSTEM_ADMIN) OR env user/role allowlists → **unrestricted directory scope**.
- **`require_dept_scope`** — non-privileged users scoped to `users.unit_id` (deputy sees parent unit).
- **`directory/rbac.compute_scope`** — merges privileged bypass, E1 personnel visibility, or empty scope.
- **Working contacts** — privileged-only read of `users` joined to `roles`, `employees`, catalog `positions`.

#### 2.4.2. Admin / sysadmin API

- **`require_sysadmin_api`** — `role_id=2`, break-glass user allowlist, OR `access_grants` with `SYSADMIN_CABINET` / `ACCESS_ADMIN`.
- **`ADR042_ADMIN_GUARD_MODE`** — `legacy` | `access_grants_shadow` | `access_grants_enforced` (shadow logs divergence).
- **`DIRECTORY_PRIVILEGED_ROLE_IDS`** grants directory privilege but **not** sysadmin API (post-split).

#### 2.4.3. Personnel admin & HR governance

- **`evaluate_personnel_admin_access`** — sysadmin API OR `HR_ENROLLMENT_MANAGER` / related grant codes via `list_active_access_role_codes`.
- **`evaluate_hr_governance_access`** — tier-2 override paths (enrollment approve/reject).
- **`require_hr_import_admin_or_403`** — privileged OR personnel admin.

#### 2.4.4. Personnel visibility (E1)

- **`resolve_effective_personnel_visibility`** — priority: privileged → explicit assignments → implicit from `access_level` MANAGER/ADMIN → none.
- Position targets use **catalog** `position_id` from active `person_assignments`.
- Enriched onto `/auth/me` as `has_personnel_visibility`, `personnel_visibility.*`.

#### 2.4.5. Task RBAC (ADR-023 lean)

- **Mine scope:** `tasks.executor_role_id = users.role_id` (+ initiator/approver user exceptions).
- **Team scope:** `can_view_team_tasks` — system admin, heuristics on role **code/name** (`_looks_like_manager_role`), org-tree role visibility via `compute_visible_executor_role_ids_for_tasks`.
- **Actions:** `can_report`, `can_approve` compare `current_role_id` to `executor_role_id`; initiator checks use `user_id`.
- **Hard-coded role sets:** `QM_HEAD` team executor codes, `DIRECTOR_ROLE_IDS`, `DEPUTY_ROLE_IDS`, `SUPERVISOR_ROLE_IDS` env.
- **Position filter (team):** proxy join `users.role_id = executor_role_id` → `employees.position_id` (catalog title).

#### 2.4.6. Regular tasks admin

- **`_require_admin_or_privileged`** — `role_id == 2` or `is_privileged`.
- Run journal ACL — system admin role gate (tests confirm).

#### 2.4.7. `/auth/me` enrichment

Returns: `role_id`, `role_name_ru`, `unit_id`, `position_id`/`position_name` (from **employee snapshot**, not assignment union), `is_privileged`, `is_system_admin` (`role_id==2`), `has_sysadmin_api`, `has_personnel_admin`, `has_hr_governance`, `can_view_all_tasks`, personnel visibility block.

**Single role, single position** — incompatible with ARCH-001 multi-cabinet union (§10).

#### 2.4.8. UI authorization (client)

- **`adminNav`** — `is_privileged`.
- **`visibilityNav`** — `/auth/me` visibility flags; route guards for directory/tasks read-only.
- **`taskScopePolicy.isTaskSystemAdmin`** — duplicates backend: `role_id==2`, role code/name heuristics.
- **`platformRoleCatalog`** — lists `public.roles` for user create / role edit drawers (OPS-029 tension).
- **EmployeeAccountSections** — `updateUserRole` mutates `users.role_id` (operational access change via Platform Role, not Employment).

#### 2.4.9. Telegram authorization

- Bot internal API: `X-Internal-Api-Token` + `X-Telegram-User-Id` → bound `user_id`.
- **`require_bot_bound_user`** — loads user, `_enrich_user_context` — **inherits full user-centric RBAC context**.
- Service accounts blocked by login/name pattern.
- Task notifications resolve recipients by **`role_id = executor_role_id`** (tasks assessment).

#### 2.4.10. ADR-042 access resolver (Phase B3)

- **`resolve_effective_access(user_id)`** — collects grant targets from USER, ROLE (`users.role_id`), EMPLOYEE, PERSON, ASSIGNMENT, **POSITION (catalog)**, ORG_UNIT; picks MAX(`level_rank`) allow grant.
- **Read-only** for most routes; used by admin permission helpers and E1 fallback.
- **Deny grants (ACCESS_NONE)** listed but **not enforced** in B3.
- **Not wired** as universal authorization gate.

### 2.5. Effective permission calculation (as-is summary)

```text
Effective ops context ≈ users.role_id (primary)
                    ∪ access_grants (partial, MAX rank)
                    ∪ personnel_visibility_assignments (visibility only)
                    ∪ env role/user allowlists (privileged, director/deputy/supervisor task trees)
                    ∪ users.unit_id (directory dept scope)
```

There is **no** union across multiple Employments; **no** Cabinet-derived Permission Template; **no** acting overlay.

### 2.6. Scope calculation (as-is)

| Scope type | Source |
|------------|--------|
| Directory dept subtree | `users.unit_id` + deputy parent rule + `DIRECTORY_RBAC_MODE` |
| Personnel visibility units | E1 assignments or implicit MANAGER/ADMIN access_level |
| Task team visibility | Role hierarchy env sets + org unit tree of **other users' role_ids** |
| Org filter (tasks/contacts) | `owner_unit_id` / org scope params — partially org-centric |
| Organization boundary | Single-tenant; no multi-org ACL |
| Admin | Global for sysadmin / privileged |

All scope carriers are **user-attached** (`unit_id`, `role_id`) or **grant-target** (USER, ROLE), not **Cabinet-attached**.

### 2.7. Focus area answers

| Focus area | AS-IS |
|------------|-------|
| **Auth vs authz separation** | ✓ JWT auth-only; ✗ authz model is user/role-centric |
| **Permission ownership** | Platform Role on User (`users.role_id`); grants on mixed targets; **not** Cabinet |
| **Effective permission calc** | Single role + grant MAX rank + env lists; **not** cabinet union |
| **Scope calculation** | `users.unit_id`, role-tree env, E1 assignments |
| **Multi-position access** | ✗ — one `role_id`; assignments feed grants but do not drive task/auth context |
| **Acting duties** | ✗ — ADR-036 deferred; ops workaround = change `users.role_id` (anti-pattern) |
| **Vacancy behaviour** | Role/task binding persists; no occupant resolution via Cabinet |
| **Organization boundary** | Implicit single org; scope via org_units subtree |
| **API authorization** | Per-module guards on `role_id`, `is_privileged`, grants |
| **UI authorization** | Mirrors `/auth/me` flags; client-side admin heuristics duplicate backend |
| **Report visibility** | Task list filters by `executor_role_id`; team position filter via role→employee proxy |
| **Task visibility** | ADR-023 role/user model (see tasks assessment) |
| **Admin permissions** | `role_id=2` + grants + env break-glass |
| **Enrollment permissions** | `HR_ENROLLMENT_MANAGER` grant code via access_grants |
| **Telegram authorization** | Bound Platform User → inherits user RBAC; delivery by role_id |

---

## 3. TO-BE under ARCH-001 (baseline unchanged)

### 3.1. Target ownership

| Concern | Owner (ARCH-001) |
|---------|------------------|
| Authentication | **Platform User** only |
| Identity for authorization | **Person** (via User linkage) |
| Access period | **Employment** (+ ACTING overlay) |
| Operational permission container | **Position Cabinet** |
| Permission definition | **Permission Template** inside Cabinet |
| Atomic rights | **Permissions** in Template |
| Exception overlays | `access_grants` as **policy exceptions** only (ARCH-001 §15.0) |

### 3.2. Effective permissions

Per ARCH-001 §3.6, §10:

```text
Effective Permissions (Person, at time T) =
  ⋃ PermissionTemplate.permissions
    for each Position Cabinet C
    where Person has active access to C
    via primary Employment and/or ACTING overlay at T
  ∪ explicit grant exceptions (if policy allows)
```

- **Multi-employment:** union of all accessible Cabinets.
- **Acting:** temporary union member; auto-expires with overlay period.
- **Vacancy:** Cabinet persists; no Person access until new Employment/acting — process policy for task generation (§4.7.2).
- **Platform User:** never stores Permission Template; never the union operand.

### 3.3. Scope under Cabinet model

| Scope type | TO-BE source |
|------------|--------------|
| Operational actions | Permissions in **active Cabinet context** |
| Directory / personnel read | Cabinet Template visibility permissions + org structure roll-up |
| Task mine | Cabinets accessible via Employment |
| Task team / supervisor | Cabinet hierarchy or org-position tree — **not** `users.unit_id` alone |
| Admin | Explicit platform admin Cabinets or break-glass grants — not `role_id=2` hardcode |
| UI session | **Active cabinet context** selector + combined union view |

### 3.4. Authentication vs authorization (TO-BE)

Unchanged transport: JWT identifies Platform User only. Post-auth pipeline resolves Person → Employments → Cabinets → effective permission set. Authorization decisions **never** read `users.role_id` as primary input in end state.

### 3.5. Transitional coexistence (conceptual)

During migration (not implementation):

1. **Phase A:** Cabinet entity + resolver read side-by-side with legacy role checks (shadow mode, analogous to `access_grants_shadow`).
2. **Phase B:** Route enforcement flips to cabinet resolver; `users.role_id` deprecated for ops.
3. **Phase C:** `public.roles` retired as user assignment target; codes migrate into Cabinet Permission Templates.
4. **Phase D:** `access_grants` narrowed to documented exceptions only.

---

## 4. Ownership Analysis

| Object / concept | AS-IS owner | TO-BE owner (ARCH-001) | Gap |
|------------------|-------------|------------------------|-----|
| Login session | Platform User | Platform User | ✓ |
| Platform Role assignment | Platform User (`users.role_id`) | **None** (auth only on User) | **Critical** |
| Permission Template | `public.roles` (global catalog on User) | **Position Cabinet** | **Critical** |
| Task executor addressing | `executor_role_id` → Platform Role | **Executor Position Cabinet** | High (tasks ADR) |
| Directory dept scope | `users.unit_id` | Cabinet/org structure policy | High |
| Personnel visibility row | USER / catalog POSITION / DEPARTMENT | Cabinet visibility permissions | Medium |
| Access grant | Mixed targets incl. ROLE, USER | Exception overlay only | Medium |
| Admin break-glass | `role_id=2`, env lists | Platform policy + grants | Medium |
| Effective permission set | User + grants | Person via Cabinets | **Critical** |
| Telegram delivery identity | Platform User | Platform User (transport) | ✓ |
| Report authorship | Person (user_id) + role_id context | Person + **cabinet_id** context | Medium |

---

## 5. Lifecycle Analysis

| Event | AS-IS authorization effect | TO-BE (ARCH-001) |
|-------|---------------------------|------------------|
| **User create** | Assign `role_id`, optional `employee_id`, `unit_id` | User = auth; access opens when Employment links Person to Position → Cabinet |
| **Enrollment apply** | Creates employee; may link user; **does not** derive cabinet access | Open Employment → Cabinet access |
| **Employment start** | May add POSITION subject to grant resolver | **Opens** Cabinet access |
| **Employment end** | Terminate may deactivate user; assignments may close async | **Closes** Cabinet access; User may remain for auth |
| **Transfer** | Update employee snapshot; manual role change risk | Close/open Employment; **same Cabinets** on positions |
| **Acting start** | Not implemented; role_id swap workaround | Temporary **second** Cabinet access |
| **Acting end** | Manual role revert | Auto-close acting Cabinet access |
| **Vacancy** | Role/tasks remain; zero users with role | Cabinet persists; permissions unreachable until occupant |
| **Position liquidation** | N/A (no Position lifecycle) | Cabinet lifecycle ends with Position |
| **Role catalog edit** | Changes behaviour for all users with that `role_id` | Edit Permission Template **inside Cabinet** — localized blast radius |
| **Grant add/revoke** | Immediate effect via resolver | Exception overlay; baseline from Cabinet |
| **User lock / token_version** | Auth blocked | Unchanged (auth layer) |

---

## 6. Access Analysis

### 6.1. What grants access today

| Grant mechanism | Grants what | ARCH-001 equivalent |
|-----------------|-------------|---------------------|
| `users.role_id` | Task execution, team visibility, UI role label, admin heuristics | **Permission Template via Cabinet** |
| `users.unit_id` | Directory dept RBAC | Cabinet/org scope policy |
| `access_grants` on ROLE/USER | Admin, enrollment, access_level | Exception overlay |
| `access_grants` on PERSON/ASSIGNMENT/POSITION/ORG_UNIT | Partial resolver subjects | Employment → Cabinet path |
| `personnel_visibility_assignments` | Org sidebar, personnel read, task read-only | Cabinet visibility permissions |
| Env allowlists | Privileged, director/deputy/supervisor trees | **Retire** — express in Cabinet Template or org policy |
| `users.employee_id` | Position name on `/auth/me`; working contacts | Person → Employment → Cabinet |
| Telegram binding | Bot acts as User | Unchanged transport |

### 6.2. User-centric couplings (inventory)

| Coupling | Locations (representative) |
|----------|---------------------------|
| `users.role_id` as ops center | `auth.py`, `tasks_service.py`, `tasks_router.py`, `directory_scope.py`, `users_routes.py`, UI role drawers |
| `employee_id` bridge | `auth.py` `_get_user_by_id`, `access_resolver_service`, working contacts |
| Catalog `position_id` | `/auth/me`, E1 resolver, access grant POSITION targets |
| Role **code** string checks | `QM_HEAD`, `ADMIN`, `DEP_*`, `_looks_like_manager_role`, `taskScopePolicy.ts` |
| Hard-coded `role_id == 2` | `SYSTEM_ADMIN_ROLE_ID`, `is_system_admin`, regular tasks admin, journal ACL |
| Static env role sets | `DIRECTOR_ROLE_IDS`, `DEPUTY_ROLE_IDS`, `SUPERVISOR_ROLE_IDS`, `privileged_role_ids` |
| JWT role claims | **None** (positive) |

### 6.3. Can access derive from Employment → Cabinet → Template today?

**No.**

- Cabinet entity absent (assessment #1).
- Resolver uses assignments only to collect catalog POSITION ids for **grants**, not to open Cabinets.
- `/auth/me` ignores assignment union.
- `users.role_id` would contradict cabinet-exclusive derivation if left in parallel without shadow migration.

---

## 7. Gap Analysis

### 7.1. Architectural gaps

| ID | Gap | Severity |
|----|-----|----------|
| R1 | **No Position Cabinet** — cannot host Permission Template | **Critical** (blocked ADR-050) |
| R2 | **`users.role_id` is operational center** — contradicts ARCH-001 §3.7, §8 | **Critical** |
| R3 | **`public.roles` conflates** Platform Role, task routing, and permission template | **Critical** |
| R4 | **Single role per user** — no multi-cabinet union | **High** |
| R5 | **Acting via role swap** — ADR-036 explicit non-goal for MVP | **High** |
| R6 | **Effective access resolver not enforcement gate** | **High** |
| R7 | **Deny grants not enforced** (B3) | **Medium** |
| R8 | **Env-based role hierarchy** for task visibility — undeclared business policy in config | **High** |
| R9 | **Hard-coded SYSTEM_ADMIN role_id=2** | **Medium** (transitional break-glass) |
| R10 | **E1 visibility on catalog POSITION**, not org-unique Position/Cabinet | **High** |
| R11 | **UI mutates `users.role_id`** for «Роль Corpsite» — wrong abstraction (OPS-029) | **High** |
| R12 | **Telegram inherits user-centric context** — will inherit cabinet union when migrated | **Medium** |
| R13 | **Person not universal** on users — weakens assignment-based grant path | **High** (personnel P2) |
| R14 | **Auth/me single position** from employee snapshot | **High** |
| R15 | **Client-side role heuristics** duplicate backend (`isTaskSystemAdmin`) | **Low** |

### 7.2. Blocked until ADR-050 / ADR-051

| ID | Gap | Dependency |
|----|-----|------------|
| B1 | Cabinet-scoped Permission Template storage | ADR-050 |
| B2 | Employment → accessible Cabinets resolver | ADR-051 + ADR-050 |
| B3 | ACTING → temporary Cabinet access in resolver | ADR-036 + B2 |
| B4 | Retarget E1 POSITION targets to org-unique Position / Cabinet | ADR-050 |
| B5 | Task RBAC cabinet enforcement | ADR-049 + B2 |
| B6 | `/auth/me` `accessible_cabinets[]` | B2 |

### 7.3. ARCH-001 sufficiency

**ARCH-001 is sufficient.** RBAC does not require new baseline entities. It requires:

1. Implementing Cabinet + Template (ADR-050).
2. Defining resolver contract (ADR-051).
3. **Demoting** `users.role_id` from operational center to transitional compatibility.
4. Migrating subsystem guards (tasks, directory, admin, UI) to cabinet-effective permissions.

---

## 8. Required ADR Changes

### Required

| ADR / document | Change |
|----------------|--------|
| **ADR-050** | [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) (**Proposed**) | Org-unique Position + Position Cabinet; Template storage |
| **ADR-051** | [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) (**Proposed**) | **Cabinet access resolver** — inputs, union semantics, acting, vacancy, active context |
| **ADR-042 Phase B5** | `/auth/me` — replace role-centric claims with `accessible_cabinets[]`, effective permissions, active cabinet |
| **ADR-023** | Task RBAC — `executor_cabinet_id`; visibility/actions via cabinet access + permissions |
| **ADR-042 dep-admin role grants** | `target_type=ROLE` → Cabinet Template or explicit exception policy |
| **ADR-042 Phase E1** | Visibility scope derived from Cabinet permissions; retire USER/ROLE-centric targets as baseline |
| **OPS-029** | User create / role edit — auth-only User; **remove** Platform Role as employment substitute |

### Recommended

| ADR / document | Change |
|----------------|--------|
| **ADR-031** | Platform Role → Permission Template inside Cabinet terminology |
| **ADR-007** | UI shell — cabinet context selector; distinguish from Position Cabinet |
| **ADR-033** | Governance — who administers Cabinet Templates vs HR Employments |
| **ADR-036** | ACTING → resolver overlay; forbid role_id swap |
| **ADR-049** (tasks transition) | Coexistence/shadow mode for role vs cabinet enforcement |
| **ADR-042 B3/B4** | Promote access resolver to **enforcement**; enforce deny grants |
| **ADR-045** | Split HR process permissions from Cabinet operational permissions |

### Optional

| ADR / document | Change |
|----------------|--------|
| **ADR-013** | Confirm no role claims in JWT when cabinet resolver live (documentation only) |
| **ADR-022** | Event delivery recipients — cabinet occupants |
| **ADR-044** | User linkage UI — show cabinet access not role_id |

---

## 9. Migration Roadmap

**No implementation in this assessment.** Phases respect **ADR-050 → ADR-051** gate.

### Phase 0 — Inventory & shadow (pre-Cabinet schema)

- Extend admin/task guard shadow logging (pattern: `access_grants_shadow`) for **cabinet vs role** decisions once resolver stub exists.
- Document env role allowlists as **legacy policy debt** to be encoded in Templates.

### Phase 1 — Foundation (ADR-050 + ADR-051)

- Create Position Cabinet + Permission Template schema.
- Implement **read-only** `resolve_accessible_cabinets(person_id)` and `effective_permissions(person_id, cabinet_id?)`.
- Add `/auth/me` cabinets[] alongside legacy fields (compat).

### Phase 2 — Enforcement pivot

- Task list/actions: shadow compare role vs cabinet paths (ADR-049).
- Directory scope: map dept visibility to Cabinet org scope.
- Admin: migrate `require_sysadmin_api` to permission codes on platform admin Cabinet or retained break-glass grants.

### Phase 3 — Decommission user-centric ops

- Stop writing `users.role_id` for operational purpose; UI Employment/Cabinet management replaces «Роль Corpsite».
- Migrate `public.roles` task routing to cabinet FKs.
- Remove env DIRECTOR/DEPUTY/SUPERVISOR role sets — express in org/Cabinet policy.

### Phase 4 — Cleanup

- Narrow `access_grants` to documented exceptions.
- Remove shadow modes; delete obsolete ROLE-target grants.
- Retire `users.role_id` column or repurpose auth-only metadata if needed.

---

## 10. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Parallel role + cabinet enforcement** diverges | Wrong access in production | Mandatory shadow mode + audit before cutover |
| **Premature `role_id` removal** before all guards migrated | Outage / lockout | Phase enforcement per subsystem; break-glass grants retained |
| **Acting via role swap continues** | Lost primary cabinet context | ADR-036 explicit ban; ops playbook |
| **Env role hierarchy hidden policy** | Regression when env migrated | Inventory → Template encoding before env removal |
| **Grant ROLE targets multiply** | Template duplication | ADR-042 dep-admin amendment; grant hygiene |
| **UI/client heuristics drift from backend** | Users see actions they cannot perform | Single source: `/auth/me` effective permissions |
| **Telegram delivery during migration** | Missed notifications | Recipient resolution dual-path until cabinet path proven |
| **Deferring RBAC migration** | Every new feature binds to `role_id` | Architecture session gate on new role_id dependencies |

---

## 11. Access Resolution Algorithm

### 11.1. AS-IS — complete pipeline

```text
HTTP Request
    │
    ▼
Authorization: Bearer JWT
    │
    ▼
decode_and_verify_token()
    │  claims: sub=user_id, exp, token_version
    │  (no role/permission claims)
    ▼
get_current_user()
    │
    ├─► _get_user_by_id(user_id)
    │       SELECT users.role_id, users.unit_id, users.employee_id
    │       JOIN roles → role_name_ru
    │       JOIN employees → catalog positions (position_id, position_name)
    │
    └─► _enrich_user_context(user)
            │
            ├─► is_privileged(user)
            │       role_id == 2 (SYSTEM_ADMIN)
            │       OR user_id ∈ DIRECTORY_PRIVILEGED_USER_IDS
            │       OR role_id ∈ DIRECTORY_PRIVILEGED_ROLE_IDS
            │
            ├─► is_system_admin → role_id == 2
            │
            ├─► evaluate_admin_access(user)
            │       role_id == 2 OR break-glass user_id
            │       OR access_grants → SYSADMIN_CABINET | ACCESS_ADMIN
            │       (mode: legacy | access_grants_shadow | access_grants_enforced)
            │
            ├─► has_any_personnel_read_permission / has_hr_governance_permission
            │       access_grants role codes via list_active_access_role_codes(user_id)
            │
            ├─► enrich_user_with_personnel_visibility(user)
            │       if privileged → org-wide visibility
            │       else personnel_visibility_assignments (USER, catalog POSITION, DEPARTMENT)
            │       else resolve_effective_access → MANAGER/ADMIN implicit scope
            │       else none
            │
            └─► can_view_team_tasks(user_id, role_id)
                    role_id == 2 OR manager role heuristics (code/name)
                    OR compute_visible_executor_role_ids_for_tasks(user_id)
                          → users.unit_id + DIRECTOR/DEPUTY/SUPERVISOR env role sets
    ▼
Enriched user context dict → route handler
    │
    ├─► Directory routes: compute_scope(uid, user_ctx)
    │       privileged bypass | E1 visibility scope | empty
    │       dept RBAC: require_dept_scope → users.unit_id subtree
    │
    ├─► Task routes: get_user_role_id(conn, user_id) → users.role_id
    │       mine: executor_role_id = role_id
    │       team: can_view_team_tasks + unit/role/QM_HEAD rules
    │       actions: compare role_id, user_id to task fields
    │
    ├─► Admin routes: require_sysadmin_api / require_personnel_admin_api
    │
    ├─► Regular tasks admin: role_id == 2 | is_privileged
    │
    └─► Telegram bot: require_bot_bound_user → same enrichment chain
    ▼
Authorization Decision (allow / 403)
```

#### 11.1.1. Dependency inventory (AS-IS)

| Step | Depends on |
|------|------------|
| JWT validation | `user_id` only |
| User load | **`user_id`**, **`role_id`**, **`unit_id`**, **`employee_id`** |
| Position display | **`employee_id`** → catalog **`position_id`** |
| Privileged | **`role_id==2`**, **`user_id`** allowlist, **`role_id`** allowlist |
| Admin API | **`role_id==2`**, **`user_id`**, **`access_grants`** (USER/ROLE/…) |
| Personnel visibility | **`user_id`**, **`unit_id`**, catalog **`position_id`**, **`role_id`** via grants |
| Task mine/execute | **`user_id`**, **`role_id`**, **`executor_role_id`** |
| Task team | **`user_id`**, **`role_id`**, **`unit_id`**, env **`role_id`** sets, role **code** (`QM_HEAD`) |
| Task approve | **`user_id`** (initiator), **`role_id`** |
| Directory scope | **`unit_id`**, **`role_id`** (deputy), privileged |
| Working contacts | **`is_privileged`** |
| UI gates | `/auth/me` flags → **`role_id`**, **`role_code`**, heuristics |

**Hard-coded role names / codes (non-exhaustive):** `SYSTEM_ADMIN`, `ADMIN`, `DIRECTOR`, `QM_HEAD`, `DEP_*`, `*_HEAD`, `*_DEPUTY`, Russian «руководител», «директор», «заместител».

**Static permission mapping:** `PERMISSION_CODES` → grant codes; env `DIRECTOR_ROLE_IDS`, `DEPUTY_ROLE_IDS`, `SUPERVISOR_ROLE_IDS`; `QM_HEAD_TEAM_EXECUTOR_ROLE_CODES`; `DIRECTORY_PRIVILEGED_*`.

### 11.2. TO-BE — complete pipeline (ARCH-001)

```text
HTTP Request
    │
    ▼
Authorization: Bearer JWT
    │
    ▼
Platform User authenticated (user_id)
    │
    ▼
Resolve Person (users → persons bridge)
    │
    ▼
Load active Employments (person_assignments)
    │  filter: active_flag, lifecycle_status, date range
    │
    ├─► Primary employments → org-unique Position → Position Cabinet
    │
    └─► ACTING overlays (ADR-036) → additional Position Cabinet(s)
    │
    ▼
Accessible Position Cabinet set (0..N)
    │
    ▼
For each Cabinet: load Permission Template → Permissions
    │
    ▼
Effective Permission Set = ⋃ Template.permissions
    │  (optional: ∪ explicit access_grant exceptions)
    │
    ▼
Resolve active cabinet context (UI/session selection; default combined)
    │
    ▼
Scope rules from Permissions + org structure
    │  (visibility, dept subtree, org-wide, task modules, admin)
    │
    ▼
Authorization Decision
    audit: (person_id, cabinet_id, permission, timestamp)
```

#### 11.2.1. TO-BE decision inputs (no `users.role_id`)

| Decision type | Inputs |
|---------------|--------|
| Task mine | Person ∈ occupants(C_executor) for task's executor cabinet |
| Task action | Permission in Template + cabinet context + initiator Person rule |
| Directory read | Visibility permission + org scope from Cabinet/org policy |
| Admin | Platform admin permission in designated Cabinet or exception grant |
| Enrollment | HR governance permission via Cabinet Template or exception grant |
| Multi-position | Union across cabinets; action requires context cabinet unless permission is global |
| Acting | Time-bounded cabinet in accessible set |
| Vacancy | Cabinet exists; permission set empty for all Persons until Employment |
| Telegram | Platform User → Person → same accessible cabinet set for delivery routing |

---

## 12. Permission Sources

Classification: **architectural** (permanent in ARCH-001), **transitional** (migration compatibility), **obsolete** (must not remain operational center post-migration).

| Source | Classification | Role | Notes |
|--------|----------------|------|-------|
| **Platform User** | Architectural | Authentication, account status, Telegram binding | Must **not** own permissions (ARCH-001 §3.7) |
| **Person** | Architectural | Identity anchor for authorization subject | Via User linkage; incomplete materialization today |
| **Employment** (`person_assignments`) | Architectural | Opens Cabinet access for period | AS-IS: feeds grant subjects only; not access gate |
| **Position** (org-unique) | Architectural | HR anchor for Cabinet | **Not implemented** — blocked ADR-050 |
| **Position Cabinet** | Architectural | Operational permission container | **Not implemented** |
| **Permission Template** | Architectural | Named permission bundle inside Cabinet | AS-IS stand-in: `public.roles` on User |
| **Permissions** (atomic) | Architectural | Module/action/visibility rights | Partially implicit in role codes and grant codes |
| **`users.role_id`** | Transitional → **Obsolete** | Single Platform Role on User | **Primary anti-pattern**; pilot + task RBAC center |
| **`public.roles`** | Transitional | Global role catalog | Becomes Template **definitions** inside Cabinets, not user FK |
| **`access_grants` / `access_roles`** | Transitional | ADR-042 overlay; admin/enrollment | TO-BE: **exception** layer only (ARCH-001 §15.0) |
| **`personnel_visibility_assignments`** | Transitional | E1 read-scope | Replace with Cabinet visibility permissions |
| **JWT claims** | Architectural (transport) | `sub`, `token_version`, `exp` | Correctly excludes roles — keep |
| **Organization** | Architectural | Single-tenant boundary | Implicit today |
| **`org_units` / org structure** | Architectural | Scope roll-up, Position placement | Used via `unit_id` proxy today |
| **`users.unit_id`** | Transitional | Directory dept RBAC scope | TO-BE: derived from Employment/Cabinet org context |
| **`users.employee_id`** | Transitional | Bridge to snapshot position | TO-BE: Person → Employment path |
| **Catalog `positions.position_id`** | Obsolete for auth | Title dictionary FK | Must not drive permissions post ADR-050 |
| **`employee_id` as grant target** | Transitional | ADR-042 EMPLOYEE grants | Replace with Person/Employment/Cabinet |
| **`ROLE` grant target** | Transitional → Obsolete | Grants on Platform Role id | Conflicts with cabinet-exclusive model |
| **`USER` grant target** | Transitional | Direct user grants | Narrow to break-glass exceptions |
| **Env role allowlists** | Obsolete | Director/deputy/supervisor task trees, privileged roles | Undocumented policy — encode in Templates |
| **`role_id == 2` hardcode** | Transitional | System admin break-glass | Retain until admin Cabinet or grant policy exists |
| **`initiator_user_id`** | Architectural (exception) | Initiator-centric approve (ADR-023) | Person-specific; not a permission source |
| **Internal API token** | Architectural (transport) | Bot/service authentication | Not domain RBAC |
| **Telegram binding** | Architectural (transport) | Delivery endpoint on Platform User | Authorization still Person/Cabinet-derived |

### 12.1. Permanent architecture (summary)

Platform User (auth) → Person → Employment (+ acting) → Position Cabinet → Permission Template → Permissions → effective set (+ optional explicit exceptions).

### 12.2. Transitional-only (must not appear in end state as primary)

`users.role_id`, user-attached Platform Role, ROLE-targeted grants as baseline, `users.unit_id` as standalone scope carrier, catalog `position_id` in visibility rules, env role hierarchy sets.

### 12.3. Obsolete as authorization centers

Treating **`public.roles`** as assignable operational identity on User; **`employee_id`** as access carrier; **`role_id` swap** for acting; **`role_code`** string checks as authoritative policy (`QM_HEAD`, `_looks_like_manager_role`).

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 1.0 | Initial access-rbac assessment (queue #3) |
