# Phase 2 Readiness Review — Position/Cabinet Foundation

## Document metadata

| Field | Value |
|-------|-------|
| Status | **Active** — 2026-07-03 |
| Type | Architecture kickoff / Phase 2 readiness review (read-only) |
| Scope | Sprint 1 gate before Phase 2 engineering |
| Baseline (read-only) | [ARCH-001](../ARCH-001-position-permission-model.md), [ADR-050](../../adr/ADR-050-organization-position-cabinet-model.md), [ADR-051](../../adr/ADR-051-cabinet-access-resolution.md), [IMPLEMENTATION_PLAN](../IMPLEMENTATION_PLAN.md) |
| Mandatory chain | Platform User → Person → Employment → Position → Position Cabinet → Permission Template → Effective Permissions |

**Review method:** architecture documents read in mandated order; codebase inspected for models, migrations, API, frontend consumers, and tests. **No production code, migrations, or architecture documents were modified during this review.**

---

## 1. Executive verdict

### `READY WITH PRECONDITIONS`

**Rationale:**

| Dimension | Assessment |
|-----------|------------|
| Architecture baseline | **Ready** — ARCH-001, foundation assessments, ADR-050/051, and IMPLEMENTATION_PLAN define a coherent Phase 2 target. |
| Codebase clarity | **Ready** — as-is coupling points are well mapped; no hidden Cabinet/Position entities exist. |
| Phase 1 gate | **Met** (2026-07-04) — ADR-050 and ADR-051 **Accepted**; recorded in ADR decision logs. |
| Schema foundation | **Absent (expected)** — org-unique Position and Position Cabinet tables do not exist; legacy `public.positions` catalog remains staffing proxy. |

Phase 2 engineering **may proceed** per IMPLEMENTATION_PLAN. Remaining operational preconditions (engineering kickoff, staging backup policy) apply before first production migration merge.

### Preconditions (must pass before first Phase 2 implementation merge)

**Satisfied (2026-07-04):**

1. **ADR-050 Accepted** — recorded in ADR decision log.
2. **ADR-051 Accepted** — recorded in ADR decision log.
3. **No production work** under Proposed-only ADR authority (IMPLEMENTATION_PLAN E1, IR1).

**Remaining:**

4. **Engineering kickoff scheduled** with approved table/column naming pack from ADR-050 session.
5. **Staging DB backup policy** confirmed for first Alembic revision.

---

## 2. Current implementation map

### 2.1. Database / migrations

| Artifact | Current state | Phase 2 relevance |
|----------|---------------|-------------------|
| `public.roles` | Platform Role catalog (`role_id`, `name`, `code`); task routing codes | **Legacy** — Permission Template analog; assigned to User today |
| `public.users` | Auth identity; **`role_id` NOT NULL**; `unit_id`; `employee_id` bridge | User-centric authz carrier — must not expand in Phase 2 |
| `public.positions` | Global title catalog (`position_id`, `name`, `category`); global `lower(name)` uniqueness | **Not** org-unique Position — transitional taxonomy |
| `public.employees` | Operational shell; `org_unit_id` + catalog `position_id` snapshot | Composite staffing proxy, not Employment truth |
| `public.persons` | Person identity (ADR-042 B2) | Required upstream for ADR-051; not Cabinet owner |
| `public.person_assignments` | Employment episodes; FK to **catalog** `positions.position_id` + `org_unit_id` | Employment exists but references wrong Position semantics |
| `public.access_roles` / `public.access_grants` | ADR-042 grant overlay; targets include USER, ROLE, EMPLOYEE, PERSON, ASSIGNMENT, **POSITION (catalog)**, ORG_UNIT | Transitional exception overlay — not Cabinet baseline |
| `public.personnel_visibility_assignments` | E1 visibility; POSITION target = catalog id | Consumer debt — not Phase 2 scope |
| `tasks.executor_role_id` | Task instances route to Platform Role | Consumer debt — Phase 6 |
| **Missing** | `position_cabinets`, org-unique Position table, Permission Template on Cabinet, legacy mapping table | **Phase 2 deliverables** |

**Key migrations inspected:**

| Revision | Content |
|----------|---------|
| `02b0d99063cd_baseline.py` | `roles`, `users.role_id`, catalog `positions`, `employees`, task `executor_role_id` |
| `u3v4w5x6y7z8_adr042_phase_b2_1_schema.py` | `persons`, `person_assignments` → catalog `position_id`, `access_roles`, `access_grants` |
| `f8c2a91b4e10_add_directory_contacts_and_positions_category.py` | `positions.category` |
| `b0c1d2e3f4a5_adr042_phase_e1_personnel_visibility.py` | Visibility assignments with catalog position targets |
| `w5x6y7z8a9b0_adr042_phase_b5_access_roles_seed.py` | Access role seed data |

**Grep confirmation:** no `position_cabinet`, `organizational_position`, or `org_unique` identifiers exist in the codebase.

### 2.2. Backend models

| Layer | State |
|-------|-------|
| ORM models (`app/db/models/`) | HR import, aliases, employee identity only — **no** Position/Cabinet ORM |
| Data access | Raw SQL via `sqlalchemy.text` in route and service modules |
| `app/services/platform_roles_catalog.py` | Filters pytest roles from `public.roles` catalog — auth-adjacent helper only |
| `app/services/access_resolver_service.py` | ADR-042 B3 read-only grant resolver; collects catalog POSITION ids from assignments; MAX rank — **not** Cabinet Access Resolver |
| `app/auth.py` | `_get_user_by_id` loads `role_id`, employee snapshot `position_id`/`position_name`; `_enrich_user_context` adds privilege flags from `role_id` and grant helpers |

### 2.3. Backend services / auth

| Component | Behavior |
|-----------|----------|
| **Authentication** | JWT HS256: `sub`, `iat`, `exp`, `token_version` only — **correct** (ADR-013, ADR-051 R12) |
| **Authorization pipeline** | `get_current_user` → `_enrich_user_context` → user-centric flags — **legacy** |
| **`access_resolver_service`** | USER + ROLE (`users.role_id`) + assignment/catalog POSITION subjects → MAX grant rank |
| **`personnel_visibility_resolver_service`** | E1 visibility; catalog `position_id` from active assignments |
| **`tasks_service.can_view_team_tasks`** | Uses `current_role_id`; role code/name heuristics; env allowlists |
| **`admin_permissions` / `admin_guard`** | `role_id==2`, env allowlists, `access_grants` shadow/enforced modes |
| **`directory_scope.is_privileged`** | `role_id==2` OR env user/role allowlists |

**Cabinet Access Resolver (ADR-051):** not implemented.

### 2.4. API endpoints

| Area | Endpoints / behavior | Legacy assumption |
|------|---------------------|-------------------|
| Auth | `GET /auth/me` — `role_id`, `role_name_ru`, `position_id`, `position_name` (employee snapshot), `is_system_admin`, `can_view_all_tasks`, personnel visibility | Single role + single position; User-centric |
| Users | `POST /directory/users`, `PATCH .../role` — **`role_id` required** on create | User → Role assignment |
| Roles | `GET/POST/PUT/DELETE /directory/roles` — Platform Role CRUD | Role catalog as ops identity |
| Positions | `GET/POST/PUT/DELETE /directory/positions` — global title catalog | Not org-unique Position |
| Employees / personnel | Assignment CRUD uses catalog `position_id` + `org_unit_id` | Composite staffing |
| Tasks | `executor_role_id` on tasks and regular_tasks | Role-centric routing |
| Working contacts | Privileged read joins `users` → `roles` → catalog `positions` | User/role display |
| Admin | Access grants UI (`/admin/system`) — `access_roles`, `access_grants` | Grant overlay, not Cabinet |

### 2.5. Frontend consumers

| Area | Files / behavior | Legacy dependency |
|------|------------------|-------------------|
| Platform Role catalog | `corpsite-ui/lib/platformRoleCatalog.ts` — lists `/directory/roles` | User → Role UX |
| Employee account / access drawer | `EmployeeAccountSections.tsx`, `UserRoleEditDrawer.tsx`, `UserCreateForm.tsx` — `role_id`, `updateUserRole` | Operational access via Platform Role |
| Task scope | `taskScopePolicy.ts` — `role_id==2`, role code/name heuristics; `can_view_all_tasks` from `/auth/me` | User-centric task admin |
| Admin nav | `adminNav.ts`, `visibilityNav.ts` — `is_privileged`, `/auth/me` flags | User privilege flags |
| Position display | `employeeOperationalAssignment.ts` — `position_name` from employee snapshot | Catalog title, not org-unique Position |
| Contacts / journal | `role_name_ru`, `executor_role_name` display fields | Role labels as identity |
| HR import UI | `position_name` in roster promotion tables | Catalog title strings |

**No frontend consumer** reads `accessible_cabinets[]` or Cabinet context — fields do not exist in the API.

### 2.6. Tests

| Category | Representative tests | Coverage focus |
|----------|---------------------|----------------|
| `/auth/me` | `test_auth_me_position.py`, `test_auth_me_can_view_all_tasks.py`, `test_auth_me_telegram.py` | Employee snapshot position; `can_view_all_tasks`; Telegram — **not** Cabinet |
| Roles / users | `test_users_update_role.py`, `test_users_create.py`, `test_roles_org_scope.py` | User → Role CRUD |
| Access / grants | `test_adr042_phase_b3_access_resolver.py`, `test_adr042_role_targeted_grants.py`, `test_adr042_admin_guard_split.py` | Grant overlay; admin guard modes |
| Positions | `test_positions_org_scope.py`, `test_directory_contacts_positions_routes.py` | Catalog positions API |
| Assignments | `test_adr043_phase_c2_person_assignment_sync.py`, `test_personnel_events_position_change.py` | Catalog `position_id` employment |
| Tasks | `test_tasks_list_position_filter.py`, `test_qm_team_scope.py`, `test_tasks_admin_team_scope.py` | `executor_role_id`, role heuristics |
| Platform roles catalog | `test_platform_roles_catalog.py` | pytest role exclusion helper |
| Schema | `test_adr042_phase_b2_schema.py` | persons, person_assignments, access_* tables |

**Gap:** no tests for org-unique Position, Position Cabinet, 1:1 invariant, or Cabinet mapping — expected pre-Phase 2.

---

## 3. Architecture mismatch list

| # | File path | Current behavior | Architectural concern | Blocks Phase 2? |
|---|-----------|------------------|----------------------|---------------|
| M1 | `alembic/versions/02b0d99063cd_baseline.py` | `users.role_id` NOT NULL FK to `roles`; tasks `executor_role_id` | User → Role model; task routing by Platform Role | **No** — coexist during Phase 2; blocks Phase 6+ cutover |
| M2 | `public.positions` / `app/directory/positions_routes.py` | Global title catalog; `lower(name)` unique org-wide | Position ≠ org-unique staffing unit (ADR-050 I1) | **Yes** — Phase 2 must introduce separate org-unique entity or breaking evolution |
| M3 | `alembic/versions/u3v4w5x6y7z8_*.py` — `person_assignments` | FK to catalog `positions.position_id` + separate `org_unit_id` | Employment references composite catalog proxy, not org-unique Position (ADR-050 I5) | **Yes** — retarget deferred to Phase 3, but Phase 2 must create mapping targets |
| M4 | `app/auth.py` — `_get_user_by_id`, `_enrich_user_context` | Loads single `role_id`, single employee `position_id`/`position_name`; `is_system_admin = role_id==2` | Platform User carries authorization semantics (ADR-051 R2) | **No** for Phase 2 schema task; **Yes** for later resolver cutover |
| M5 | `app/directory/users_routes.py` | `UserCreateIn.role_id` required; `UserRoleUpdateIn` patches `users.role_id` | User → Role forbidden in target model | **No** in Phase 2 — explicit non-goal |
| M6 | `app/services/access_resolver_service.py` | MAX-rank grant union; ROLE subject from `users.role_id`; POSITION = catalog id | Not Cabinet-centric union (ADR-051 §5.1) | **No** in Phase 2 — Phase 4 concern |
| M7 | `app/services/tasks_service.py` (and routers) | Mine/team scope via `executor_role_id` ↔ `users.role_id` | Tasks owned by Role, not Cabinet (ARCH-001 §4.5) | **No** in Phase 2 |
| M8 | `app/services/personnel_visibility_resolver_service.py` | `target_position_id` = catalog id | Visibility not Cabinet-scoped | **No** in Phase 2 |
| M9 | `corpsite-ui/app/directory/employees/_components/EmployeeAccountSections.tsx` | `updateUserRole`, `role_id` on user create | Ops access change via Platform Role (OPS-029 tension) | **No** in Phase 2 |
| M10 | `corpsite-ui/lib/platformRoleCatalog.ts` | Full `public.roles` list for operator UX | Role catalog presented as assignable access | **No** in Phase 2 |
| M11 | `corpsite-ui/lib/taskScopePolicy.ts` | `isTaskSystemAdmin` checks `role_id==2` and role strings | User-attached admin detection | **No** in Phase 2 |
| M12 | `app/security/directory_scope.py` | `is_privileged` uses `role_id==2` + env allowlists | Env role allowlists as policy (legacy) | **No** in Phase 2 |
| M13 | `db/init/020_seed_roles_users_employees.sql` | Pilot: `employee_id = roles.code` | Role/position/user conflation | **No** — data debt; mapping job addresses pairs |
| M14 | **Absent** `position_cabinets` table | No operational container entity | Cabinet 1:1 missing (ADR-050 I2) | **Yes** — primary Phase 2 deliverable |
| M15 | **Absent** Permission Template on Cabinet | `public.roles` assigned to User instead | Template must live inside Cabinet (ADR-050 I8) | **Yes** — Phase 2 schema includes Template binding placeholder |
| M16 | `app/security/bot_internal_auth.py` | `_enrich_user_context` for bot user | Bot inherits user-centric RBAC | **No** in Phase 2 |

---

## 4. Phase 2 readiness risks

### Blocking

| ID | Risk | Mitigation |
|----|------|------------|
| B1 | ~~ADR-050/051 Proposed~~ — **Resolved** (Accepted 2026-07-04) | — |
| B2 | **No org-unique Position entity** — cannot create Cabinet 1:1 | Phase 2 additive schema per ADR-050 §8 Phase 1 |
| B3 | **Catalog `position_id` shared across org units** — one title id, many staffing slots | Phase 2 mapping must split `(org_unit_id, catalog position_id)` → N Position rows (ADR-050 §8 Phase 2) |
| B4 | **Global `lower(name)` uniqueness on `public.positions`** — blocks multi-slot same title | New org-unique table must not inherit global name constraint (assessment §9 P1) |

### Non-blocking

| ID | Risk | Notes |
|----|------|-------|
| NB1 | Dual-write period complexity when mapping is populated | Legacy FKs remain valid in Phase 2 per IMPLEMENTATION_PLAN — Employment retarget is Phase 3 |
| NB2 | `person_assignments` / `employees` divergence | Mapping audit script should cross-check both sources |
| NB3 | ADR-046 duplicate title strings | Apply dedup before/during mapping — ops task, not schema blocker |
| NB4 | Incomplete Person linkage on users | Blocks Phase 4 resolver, not Phase 2 schema introduction |
| NB5 | `org_unit_managers.user_id` user-centric heads | Long-term consumer debt (assessment P5) |

### Informational

| ID | Risk | Notes |
|----|------|-------|
| I1 | VPS `position_id=64` rename blast radius documented in POSITIONS_SYNC_RUNBOOK | Reinforces taxonomy vs staffing split |
| I2 | `platform_roles_catalog` pytest filter recently added | Hygiene only; does not change architecture |
| I3 | `access_grants` shadow/enforced modes already exist | Useful pattern for future ADR-051 shadow (Phase 5) |
| I4 | JWT auth-only boundary already correct | Phase 2 must preserve — no permission claims |

---

## 5. Minimal safe first engineering task

### Recommended task (single)

> **Add an additive, reversible Alembic migration introducing org-unique Position storage, Position Cabinet (strict 1:1 FK), Permission Template binding column(s) on Cabinet, and a legacy mapping table `(org_unit_id, catalog_position_id) → org_unique_position_id` — schema only; no data backfill; no Employment FK retarget; no auth/resolver/consumer changes.**

**Why this task:**

| Criterion | Fit |
|-----------|-----|
| Small | One migration revision + schema tests |
| Reversible | Drop new tables on downgrade; legacy tables untouched |
| Architecture-aligned | Implements ADR-050 §8 Phase 1 and IMPLEMENTATION_PLAN Phase 2 §6 |
| No consumer migration | Explicitly excludes `/auth/me`, UI, task routing |
| Unblocks next step | Mapping backfill and inventory scripts become the Phase 2 task #2 |

**Suggested engineering sequence after this task:**

1. Mapping inventory SQL/report (read-only).
2. Data migration job creating Position + Cabinet per legacy pair (the Phase 2 task #2 — separate PR).

**Table naming:** follow **Accepted ADR-050** engineering pack from architecture session. Assessment hints (`organizational_positions`, `position_cabinets`) are informative only per IMPLEMENTATION_PLAN Appendix A.

---

## 6. Explicit non-goals (first Phase 2 task)

The first implementation task **must not**:

| # | Non-goal |
|---|----------|
| NG1 | **Consumer migration** — no changes to `/auth/me`, route guards, tasks, directory UI, Telegram bot |
| NG2 | **Role decommission** — `users.role_id`, `public.roles`, `PATCH /users/role` remain unchanged |
| NG3 | **JWT permission expansion** — no cabinet, role, or permission claims in token |
| NG4 | **`/auth/me` resolver rewrite** — no `accessible_cabinets[]` or effective permissions fields |
| NG5 | **Employment FK retarget** — `person_assignments.position_id` stays on catalog until Phase 3 |
| NG6 | **Data backfill / production mapping execution** — schema-only in first task |
| NG7 | **Cabinet Access Resolver implementation** — ADR-051 is Phase 4 |
| NG8 | **Architecture document edits** — no changes to ARCH-001, ADR-050, ADR-051, IMPLEMENTATION_PLAN, or roadmap |
| NG9 | **In-place evolution of `public.positions`** into org-unique semantics without explicit ADR-approved design |
| NG10 | **Task `executor_role_id` migration** — Phase 6 consumer work |

---

## 7. Proposed validation commands

Run from repository root after the first future implementation task (schema migration merged).

### Python — environment

```powershell
cd "D:\MyActivity\MyInfoBusiness\MyPythonApps\09 Corpsite"
# Ensure DATABASE_URL points at migration test DB
alembic upgrade head
```

### Python — schema and regression (new + existing)

```powershell
# New Phase 2 schema tests (to be added with migration)
pytest tests/test_phase2_position_cabinet_schema.py -v

# Confirm ADR-042 foundation tables still valid
pytest tests/test_adr042_phase_b2_schema.py -v

# /auth/me contract unchanged (no cabinet fields yet)
pytest tests/test_auth_me_position.py tests/test_auth_me_can_view_all_tasks.py tests/test_auth_me_telegram.py -v

# Positions catalog API unchanged
pytest tests/test_positions_org_scope.py tests/test_directory_contacts_positions_routes.py -v

# Assignment paths still use catalog FK (pre-Phase 3)
pytest tests/test_adr043_phase_c2_person_assignment_sync.py -v

# Platform role catalog helper (if touched)
pytest tests/test_platform_roles_catalog.py -v
```

### Python — broader smoke (optional, staging)

```powershell
pytest tests/test_users_create.py tests/test_users_update_role.py -v
pytest tests/test_adr042_phase_b3_access_resolver.py -v
```

### Frontend

```powershell
cd corpsite-ui
npm test
# Targeted regressions for unchanged role/position UX
npx vitest run lib/platformRoleCatalog.test.ts lib/taskScopePolicy.test.ts lib/visibilityNav.test.ts
```

### Manual invariant checks (SQL, post-migration)

```sql
-- New tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('organizational_positions', 'position_cabinets', 'legacy_position_mapping');
-- Adjust names to match Accepted ADR-050 pack

-- 1:1 invariant (empty until backfill)
SELECT COUNT(*) FROM position_cabinets c
LEFT JOIN organizational_positions p ON p.position_id = c.position_id
WHERE p.position_id IS NULL;

-- Legacy tables unchanged
SELECT COUNT(*) FROM public.positions;
SELECT COUNT(*) FROM public.person_assignments;
```

### Alembic rollback drill

```powershell
alembic downgrade -1
alembic upgrade head
```

---

## 8. Source-of-truth alignment summary

| Source | Key conclusion for Phase 2 |
|--------|---------------------------|
| **ARCH-001** | Position = org-unique staffing unit; Cabinet 1:1; Person/User do not own Cabinet; Employment opens access (enforcement in ADR-051) |
| **ADR-050** | Introduce org-unique Position + Cabinet atomically; Template on Cabinet; mapping from legacy composite; Employment retarget is Phase 3 |
| **ADR-051** | Deferred — no resolver in Phase 2; JWT stays auth-only |
| **IMPLEMENTATION_PLAN** | M1 gate (ADR Accepted) before M2; Phase 2 = schema + mapping; no auth/consumer changes |

---

## 9. Files inspected

### Architecture documents

- `docs/architecture/ARCH-001-position-permission-model.md`
- `docs/architecture/ARCH-001-foundation-summary.md`
- `docs/architecture/ARCH-001-implementation-roadmap.md`
- `docs/architecture/ARCH-001-positions-org-structure-assessment.md`
- `docs/architecture/ARCH-001-personnel-employment-assessment.md`
- `docs/architecture/ARCH-001-access-rbac-assessment.md`
- `docs/architecture/ARCH-001-platform-user-identity-assessment.md`
- `docs/architecture/IMPLEMENTATION_PLAN.md`
- `docs/adr/ADR-050-organization-position-cabinet-model.md`
- `docs/adr/ADR-051-cabinet-access-resolution.md`

### Database / migrations

- `alembic/versions/02b0d99063cd_baseline.py`
- `alembic/versions/u3v4w5x6y7z8_adr042_phase_b2_1_schema.py`
- `alembic/versions/f8c2a91b4e10_add_directory_contacts_and_positions_category.py`
- `alembic/versions/b0c1d2e3f4a5_adr042_phase_e1_personnel_visibility.py`
- `alembic/versions/w5x6y7z8a9b0_adr042_phase_b5_access_roles_seed.py`
- `db/schema/001_init_mvp_monthly.sql`
- `db/init/020_seed_roles_users_employees.sql`

### Backend

- `app/auth.py`
- `app/main.py`
- `app/directory/roles_routes.py`
- `app/directory/positions_routes.py`
- `app/directory/users_routes.py`
- `app/directory/working_contacts_routes.py`
- `app/services/access_resolver_service.py`
- `app/services/personnel_visibility_resolver_service.py`
- `app/services/platform_roles_catalog.py`
- `app/security/directory_scope.py`
- `app/security/bot_internal_auth.py`
- `app/db/models/` (all modules)

### Frontend

- `corpsite-ui/lib/platformRoleCatalog.ts`
- `corpsite-ui/lib/taskScopePolicy.ts`
- `corpsite-ui/lib/visibilityNav.ts`
- `corpsite-ui/lib/employeeOperationalAssignment.ts`
- `corpsite-ui/app/directory/employees/_components/EmployeeAccountSections.tsx`
- `corpsite-ui/app/directory/employees/_components/UserRoleEditForm.tsx`
- `corpsite-ui/package.json`

### Tests

- `tests/test_adr042_phase_b2_schema.py`
- `tests/test_adr042_phase_b3_access_resolver.py`
- `tests/test_auth_me_position.py`
- `tests/test_auth_me_can_view_all_tasks.py`
- `tests/test_auth_me_telegram.py`
- `tests/test_platform_roles_catalog.py`
- `tests/test_positions_org_scope.py`
- `tests/test_users_create.py`
- `tests/test_users_update_role.py`
- `tests/conftest.py`

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 1.0 | Initial Phase 2 readiness review — Sprint 1 kickoff gate |
| 2026-07-04 | 1.1 | Phase 1 gate met — ADR-050/051 Accepted; preconditions and risks updated |
