# ADR-042 / ADR-045 Follow-up — Admin Guard Split

**Status:** Implemented  
**Date:** 2026-06-23  
**Related:** [ADR-042 DEP_ADMIN role grants](ADR-042-dep-admin-role-grants.md), [ADR-042 Phase B5](ADR-042-phase-b5-auth-policy.md), [ADR-045](ADR-045-personnel-hr-processes-split.md)

## Problem (resolved)

Directory env flags (`DIRECTORY_PRIVILEGED_ROLE_IDS`) and `is_privileged()` were reused as the **legacy admin gate** for sysadmin `/admin/*` routes. That conflated directory cross-dept scope with sysadmin API access.

DEP_ADMIN with `DIRECTORY_PRIVILEGED_ROLE_IDS=13` received sysadmin API access (`/admin/users`, `/admin/access/grants`) even without `SYSADMIN_CABINET` or `ACCESS_ADMIN` grants.

## Decision

**Directory privileged ≠ sysadmin API.** Split implemented in `app/security/admin_guard.py`.

### Sysadmin API gate (`require_sysadmin_api`)

Access allowed only via:

| Path | Mechanism |
|------|-----------|
| a | `role_id=2` (system admin) |
| b | `DIRECTORY_PRIVILEGED_USER_IDS` (break-glass user allowlist) |
| c | Active `SYSADMIN_CABINET` or `ACCESS_ADMIN` access grant |

`DIRECTORY_PRIVILEGED_ROLE_IDS` **does not** open sysadmin APIs. It remains valid for:

- `is_privileged()` / directory RBAC scope
- `require_dept_scope()` bypass
- `require_privileged_or_403()` on directory write routes
- `is_deputy()` companion: `DIRECTORY_DEPUTY_ROLE_IDS`

### `/auth/me` flags

| Flag | DEP_ADMIN (production pattern) |
|------|-------------------------------|
| `is_privileged` | `true` (while `13 ∈ DIRECTORY_PRIVILEGED_ROLE_IDS`) |
| `is_system_admin` | `false` |
| `has_sysadmin_api` | **`false`** |
| `has_personnel_admin` | `true` (via `HR_ENROLLMENT_MANAGER` ROLE grant) |
| `has_hr_governance` | `true` (via same grant) |

### Frontend

`canSeeSysadminCabinetNav` uses `role_id=2` or `has_sysadmin_api=true` — not generic `is_privileged`.

Personnel lifecycle / HR routes still use `has_personnel_admin`.

### Guard modes

All modes (`legacy`, `access_grants_shadow`, `access_grants_enforced`) use the same sysadmin decision:

```
allowed = sysadmin_emergency_fallback OR admin_api_grants
```

`access_grants_shadow` logs to `security_audit_log` when pre-split `is_privileged()` differed from the new decision.

## DEP_ADMIN after split

**Keeps:**

- Personnel directory / HR Processes UI
- `DIRECTORY_DEPUTY_ROLE_IDS=13` deputy scope
- `/admin/personnel/*` via `HR_ENROLLMENT_MANAGER` ROLE grant
- `/directory/personnel/*` via `has_personnel_admin`

**Loses:**

- `/admin/users`, user lock/unlock/password admin
- `/admin/access/grants` and other sysadmin cabinet APIs under `require_sysadmin_api`

## Production cutover checklist

1. Deploy guard split code (this change).
2. Confirm DEP_ADMIN has `HR_ENROLLMENT_MANAGER` → `target_type=ROLE`, `target_id=13`.
3. Verify `/auth/me`: `has_personnel_admin=true`, `has_sysadmin_api=false`.
4. Verify `/admin/users` → 403 for DEP_ADMIN, 200 for system admin.
5. Optional: set `ADR042_ADMIN_GUARD_MODE=access_grants_shadow`; review audit mismatches.
6. Optional: remove `13` from `DIRECTORY_PRIVILEGED_ROLE_IDS` if directory cross-dept scope is no longer needed for DEP_ADMIN (deputy scope via `DIRECTORY_DEPUTY_ROLE_IDS=13` remains).

## Tests

- `tests/test_adr042_admin_guard_split.py`
- `tests/test_adr042_role_targeted_grants.py::test_directory_privileged_role_denied_sysadmin_api_legacy_mode`
- `corpsite-ui/lib/adminNav.test.ts`

## Acceptance criteria

- [x] No `/admin/*` sysadmin route accepts `is_privileged` from directory role allowlist alone.
- [x] DEP_ADMIN retains HR operational API via `HR_ENROLLMENT_MANAGER` ROLE grant.
- [x] Break-glass user allowlist and admin grants still work.
- [x] `has_sysadmin_api` exposed on `/auth/me`.
