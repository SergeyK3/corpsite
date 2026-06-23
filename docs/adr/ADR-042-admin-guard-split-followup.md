# ADR-042 / ADR-045 Follow-up — Admin Guard Split

**Status:** Proposed  
**Date:** 2026-06-23  
**Related:** [ADR-042 DEP_ADMIN role grants](ADR-042-dep-admin-role-grants.md), [ADR-042 Phase B5](ADR-042-phase-b5-auth-policy.md), [ADR-045](ADR-045-personnel-hr-processes-split.md)

## Problem

Directory env flags (`DIRECTORY_PRIVILEGED_ROLE_IDS`, `DIRECTORY_PRIVILEGED_USER_IDS`) and `is_privileged()` are reused as the **legacy admin gate** for `/admin/*`. That conflates:

| Concern | Intended gate | Current legacy gate |
|---------|---------------|---------------------|
| Directory cross-dept read / deputy scope | `is_privileged`, `is_deputy` | OK |
| HR operational contour (`/directory/personnel/*`) | `HR_ENROLLMENT_MANAGER` grant / `has_personnel_admin` | Partially OK after ROLE grants |
| Sysadmin API (`/admin/users`, `/admin/access/*`, …) | `SYSADMIN_CABINET` / `ACCESS_ADMIN` grant or role_id=2 | **Also opened by directory privileged** |

DEP_ADMIN with `DIRECTORY_PRIVILEGED_ROLE_IDS=13` therefore receives sysadmin API access in `ADR042_ADMIN_GUARD_MODE=legacy` even without `SYSADMIN_CABINET`.

## Goal

Split guards so directory privilege **never** implies sysadmin API access.

## Proposed tasks

### 1. Admin guard policy

- `evaluate_admin_access()` in **all modes** must require `SYSADMIN_CABINET` or `ACCESS_ADMIN` grant (or explicit system-admin role_id=2).
- Remove `is_privileged()` / `DIRECTORY_PRIVILEGED_*` from admin API path.
- Keep emergency fallback as **user allowlist only** (`DIRECTORY_PRIVILEGED_USER_IDS`), not role allowlist — or document a separate `SYSADMIN_EMERGENCY_USER_IDS`.

### 2. Directory privileged scope

- `DIRECTORY_PRIVILEGED_ROLE_IDS` / `DIRECTORY_DEPUTY_ROLE_IDS` remain for directory RBAC and org scope only.
- DEP_ADMIN: keep `DIRECTORY_DEPUTY_ROLE_IDS=13`; **drop** `13` from `DIRECTORY_PRIVILEGED_ROLE_IDS` after guard split.

### 3. Personnel admin path (unchanged intent)

- `has_personnel_admin` = full sysadmin **or** active `HR_ENROLLMENT_MANAGER` (USER or ROLE grant).
- DEP_ADMIN continues to receive HR contour via ROLE grant, not via `is_privileged`.

### 4. Guard mode rollout

| Mode | Admin API | Personnel admin |
|------|-----------|-----------------|
| `legacy` (today) | privileged OR grant (bug) | grant OR full admin |
| `access_grants_shadow` | log mismatch | unchanged |
| `access_grants_enforced` | grant OR emergency user allowlist | unchanged |
| **target** | grant OR role_id=2 OR emergency user allowlist | grant OR full admin |

### 5. Tests

- DEP_ADMIN + ROLE grant → `has_personnel_admin=true`, `/admin/users` → **403**
- Sysadmin grant → `/admin/users` → 200
- `DIRECTORY_PRIVILEGED_ROLE_IDS` alone → directory scope widened, **no** admin API
- Shadow mode logs when legacy privileged would have differed from grant check

### 6. Production cutover checklist

1. Deploy guard split code.
2. Set `ADR042_ADMIN_GUARD_MODE=access_grants_shadow`; review audit mismatches.
3. Confirm DEP_ADMIN has ROLE grant for `HR_ENROLLMENT_MANAGER`.
4. Remove `13` from `DIRECTORY_PRIVILEGED_ROLE_IDS` in `.env`.
5. Switch to `access_grants_enforced` when shadow is clean.

## Out of scope

- UI nav changes (already hide sysadmin for non–role_id=2).
- Replacing directory deputy/privileged semantics for `/directory/staff` visibility (ADR-042 E1).

## Acceptance criteria

- No `/admin/*` route accepts `is_privileged` from directory env alone.
- DEP_ADMIN retains HR operational API/UI via `HR_ENROLLMENT_MANAGER` ROLE grant.
- Documented env template distinguishes directory vs sysadmin allowlists.
