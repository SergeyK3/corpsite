# ADR-042 — DEP_ADMIN role-targeted access grants (production backport)

**Status:** Accepted  
**Date:** 2026-06-23  
**Related:** [ADR-042 Phase B1](ADR-042-phase-b1-schema-design.md), [ADR-042 Phase B5](ADR-042-phase-b5-auth-policy.md), [ADR-045](ADR-045-personnel-hr-processes-split.md), migration `i8j9k0l1m2n3`

## Context

Production hotfix enabled `target_type='ROLE'` on `access_grants` so that operational permissions can follow **directory job roles** (`users.role_id`) instead of per-user grants only.

DEP_ADMIN (`role_id=13` in production) must receive the HR operational contour as a **position rule**, not as a sysadmin.

## Production configuration (reference)

| Setting | Value | Purpose |
|---------|-------|---------|
| `roles.role_id` | 13 (`DEP_ADMIN`) | Directory job role |
| `access_grants` | `HR_ENROLLMENT_MANAGER` → `target_type=ROLE`, `target_id=13` | Personnel admin via grant resolver |
| `DIRECTORY_DEPUTY_ROLE_IDS` | 13 | Deputy org scope (parent unit) |
| `DIRECTORY_PRIVILEGED_ROLE_IDS` | 13 | **Temporary** — legacy directory privileged flag |
| `DIRECTORY_PRIVILEGED_USER_IDS` | 1 | Emergency operator allowlist |

## Decision

1. **Schema:** extend `chk_ag_target_type` to allow `ROLE` alongside existing values (`USER`, `POSITION`, `ORG_UNIT`, `PERSON`, `ASSIGNMENT`, `EMPLOYEE`). Migration: `i8j9k0l1m2n3_adr042_role_targeted_access_grants.py`.

2. **Resolver:** `access_resolver_service` collects `users.role_id` as subject `ROLE:{role_id}` and matches active grants with `target_type='ROLE'`.

3. **Grant service:** `validate_grant_target` accepts `ROLE` and verifies `roles.role_id` exists.

4. **DEP_ADMIN effective access:**
   - `HR_ENROLLMENT_MANAGER` via ROLE grant → `has_personnel_admin=true` on `/auth/me`
   - `DIRECTORY_DEPUTY_ROLE_IDS=13` → deputy department scope
   - `DIRECTORY_PRIVILEGED_ROLE_IDS=13` → **legacy only**; see security gap below

## Security gap (documented, not fixed here)

With `ADR042_ADMIN_GUARD_MODE=legacy` (production default):

- `DIRECTORY_PRIVILEGED_ROLE_IDS=13` sets `is_privileged=true` for all DEP_ADMIN users.
- `evaluate_admin_access()` in legacy mode returns `is_privileged`, which **opens** `/admin/users`, `/admin/access/grants`, and other `/admin/*` routes.
- UI sysadmin nav remains hidden for non–role_id=2 users, but **API responds 200**.

This is broader than intended: DEP_ADMIN should have HR operational access, not sysadmin API access.

**Mitigation until guard split:** keep `DIRECTORY_PRIVILEGED_ROLE_IDS` only if legacy admin API access is explicitly accepted; prefer removing `13` from privileged roles once [ADR-042 Admin Guard Split](ADR-042-admin-guard-split-followup.md) ships.

Regression test: `test_directory_privileged_role_opens_admin_api_legacy_mode` in `tests/test_adr042_role_targeted_grants.py`.

## Rollback

Migration downgrade is blocked if any `target_type='ROLE'` rows exist. Revoke or re-target grants before downgrade.

## Follow-up

- [ADR-042 Admin Guard Split](ADR-042-admin-guard-split-followup.md) — separate directory privileged from sysadmin API policy.
