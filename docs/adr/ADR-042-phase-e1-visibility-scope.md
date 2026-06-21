# ADR-042 Phase E1 — Visibility Scope for Right Sidebar

## Status

Accepted — implemented (Phase E1)

## Context

Access roles (`NONE`, `OBSERVER`, `MANAGER`, `ADMIN`) govern **actions** via the Access Registry (ADR-042 B2–B5). The org-tree right sidebar and personnel directory were previously limited to system admin shell (`role_id = 2`).

Business need: grant **read-only org/personnel visibility** to selected users, positions, or departments (e.g. senior nurse = `OBSERVER` + department scope) without elevating them to system admin or changing task assignment rules.

## Decision

Introduce **Personnel Visibility Assignments** — orthogonal to access levels:

| Concern | Mechanism |
|--------|-----------|
| Actions (tasks, HR, admin) | Access roles / task RBAC (unchanged) |
| What user sees (sidebar, directory) | `personnel_visibility_assignments` |

### Schema

Table `public.personnel_visibility_assignments`:

- **Target** (who receives visibility): `USER`, `POSITION`, `DEPARTMENT`
- **Scope** (what they see): `ORGANIZATION`, `DEPARTMENT` (+ subtree), `DEPARTMENT_GROUP`
- Flags: `can_view_personnel` (default true), `can_view_tasks` (default false, read-only intent)
- Lifecycle: `is_active`, `revoked_at`, audit via `VISIBILITY_GRANTED` / `VISIBILITY_REVOKED`

### Runtime resolution

`resolve_effective_personnel_visibility(user_id)`:

1. **Privileged** (`role_id=2` / env allowlist) → organization-wide (unchanged)
2. **Active assignments** matching user, position, or department target → merged scope (union; any `ORGANIZATION` scope wins)
3. **Implicit** `MANAGER` / `ADMIN` access level (from access grants) → sidebar visible; `MANAGER` keeps dept RBAC scope, `ADMIN` → org-wide view
4. Otherwise → no personnel visibility

Directory APIs call `require_personnel_visibility_or_403`; `/auth/me` exposes `show_org_sidebar`, `has_personnel_visibility`, `personnel_visibility`.

### Admin API (sysadmin only)

- `GET /admin/personnel/visibility/assignments`
- `POST /admin/personnel/visibility/assignments`
- `POST /admin/personnel/visibility/assignments/{id}/revoke`
- `GET /admin/personnel/visibility/effective?user_id=`

### UI

Sysadmin cabinet tab **«Видимость персонала»**. App shell shows limited directory nav + org sidebar when `show_org_sidebar` is true (non-admin layout).

## Non-goals (E1)

- No new role enum / `DIRECTORY_VIEWER`
- No changes to ADR-043 lifecycle execute, ADR-044 identity reconciliation, or task assignment business rules
- `can_view_tasks` is a flag only; task mutation rules unchanged

## Examples

| Persona | role (access) | visibility assignment |
|---------|---------------|------------------------|
| Senior nurse | OBSERVER | USER/POSITION → DEPARTMENT scope |
| Head of unit | MANAGER | dept scope (assignment or implicit dept RBAC) |
| Deputy chief | MANAGER | ORGANIZATION or multi-dept scope |
| System admin | ADMIN (access) | optional org scope; technical, not clinical director |

## Acceptance mapping

1. Role enum unchanged ✓  
2. ADMIN ≠ clinical director ✓  
3. Director = MANAGER + organization scope assignment ✓  
4. Visibility ≠ action grants ✓  
5. Sidebar by user/position/department target ✓  
6. Task dept logic preserved ✓  
7. Read-only tasks via `can_view_tasks` ✓  
8. OBSERVER without assignment: no sidebar ✓  
9. Tests: `tests/test_adr042_phase_e1_visibility.py`, `corpsite-ui/lib/visibilityNav.test.ts` ✓  

## Migration

`alembic/versions/b0c1d2e3f4a5_adr042_phase_e1_personnel_visibility.py`
