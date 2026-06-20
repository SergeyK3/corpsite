# ADR-042 Phase B5 — Auth Policy + Admin Guard Hardening

## Статус

**Implemented** (2026-06-20)

## Связанные документы

- [ADR-042 Phase B4 — Admin API](./ADR-042-phase-b4-admin-api.md)
- [ADR-042 Phase B3 — Service Layer](./ADR-042-phase-b3-service-layer.md)

---

## Scope Phase B5

Усиление auth/admin policy **без** изменения default-поведения и без UI/enforcement sidebar/task RBAC.

| In scope | Out of scope |
|----------|--------------|
| Admin guard modes + feature flag | React Sysadmin UI |
| access_grants permission helpers | Sidebar / route enforcement |
| Login lockout + audit | Task RBAC changes |
| token_version / must_change_password (flagged) | Full password reset |
| Password reset design stub | Global must_change without flag |

---

## B5.1 — Admin Guard Modes

**Module:** `app/security/admin_guard.py`

**Flag:** `ADR042_ADMIN_GUARD_MODE`

| Mode | Default | Behavior |
|------|---------|----------|
| `legacy` | **yes** | `is_privileged()` — как до B5 |
| `access_grants_shadow` | | Legacy решает доступ; параллельно проверяются grants; **mismatch** → `security_audit_log` (`ACCESS_CHANGED`, `action=admin_guard_shadow`) |
| `access_grants_enforced` | | Доступ при `SYSADMIN_CABINET` или `ACCESS_ADMIN` grant **или** emergency fallback |

### Emergency fallback (всегда)

- `role_id = 2` (`SYSTEM_ADMIN_ROLE_ID`)
- `DIRECTORY_PRIVILEGED_USER_IDS` / `DIRECTORY_PRIVILEGED_ROLE_IDS`

Не отключается в enforced mode — защита от lock-out.

---

## B5.2 — Admin Permission Codes

**Module:** `app/security/admin_permissions.py`

| Function | Purpose |
|----------|---------|
| `has_admin_permission(user_id, code)` | Active grant with matching `access_roles.code` |
| `has_any_admin_api_permission(user_id)` | `SYSADMIN_CABINET` or `ACCESS_ADMIN` |
| `require_admin_permission(code)` | FastAPI dependency factory |

**Permission codes:**

- `SYSADMIN_CABINET`
- `HR_ENROLLMENT_MANAGER`
- `ACCESS_MANAGER`
- `SECURITY_AUDITOR` (seed migration `w5x6y7z8a9b0`)
- `ACCESS_ADMIN`

**Resolver helper:** `list_active_access_role_codes(user_id)` in `access_resolver_service.py`

---

## B5.3 — Lockout Policy

**Module:** `app/security/auth_policy.py` + `app/auth.py` login

| Rule | Implementation |
|------|----------------|
| `locked_at` set | Login → 403 Account locked |
| Failed login | `failed_login_count++`, `LOGIN_FAILED` audit |
| Threshold exceeded | `locked_at`, `locked_reason=brute_force`, `USER_LOCKED` audit |
| Success | `failed_login_count=0`, `LOGIN_SUCCESS` audit |

**Env:** `ADR042_LOGIN_MAX_FAILED_ATTEMPTS=5` (default 5)

Metadata: login only — **never password/token/hash**.

---

## B5.4 — token_version Policy

| Item | Detail |
|------|--------|
| JWT claim | `token_version` (optional in token) |
| New tokens | Issued with current DB `users.token_version` on login |
| Enforcement | Only when `ADR042_TOKEN_VERSION_ENFORCEMENT=true` |
| Backward compat | Tokens **without** claim still accepted |
| Bump on | unlock, force-password-change, future reset |

Mismatch → 401 `Token invalidated.`

---

## B5.5 — must_change_password Policy

| Item | Detail |
|------|--------|
| Column | `users.must_change_password` |
| Enforcement flag | `ADR042_MUST_CHANGE_PASSWORD_ENFORCEMENT=false` (default) |
| When enabled | Block protected routes except `/auth/login`, `/auth/password-change` |
| Helper | `require_password_not_expired_or_change_allowed()` |
| Stub endpoint | `POST /auth/password-change` → 501 (C1/C2) |

---

## B5.6 — Admin Password Reset Stub

**Module:** `app/services/admin_password_reset_service.py`

`issue_temporary_password(...)` raises `NotImplementedError`.

Planned future behavior:

1. Generate temp password (never store/log plaintext)
2. `hash_password()` only
3. `temp_password_expires_at`, `must_change_password=true`
4. `token_version++`
5. `TEMP_PASSWORD_ISSUED` audit

---

## Feature flags summary

| Variable | Default | Effect |
|----------|---------|--------|
| `ADR042_ADMIN_GUARD_MODE` | `legacy` | Admin guard behavior |
| `ADR042_LOGIN_MAX_FAILED_ATTEMPTS` | `5` | Brute-force lockout threshold |
| `ADR042_TOKEN_VERSION_ENFORCEMENT` | `false` | Reject stale JWT when claim present |
| `ADR042_MUST_CHANGE_PASSWORD_ENFORCEMENT` | `false` | Block API until password change |

---

## Files

| File | Role |
|------|------|
| `app/security/admin_guard.py` | Guard modes |
| `app/security/admin_permissions.py` | Permission helpers |
| `app/security/auth_policy.py` | Lockout, token_version, must_change |
| `app/auth.py` | Login policy, JWT tv claim, password-change stub |
| `app/services/admin_password_reset_service.py` | Reset stub |
| `app/services/access_resolver_service.py` | `list_active_access_role_codes` |
| `alembic/versions/w5x6y7z8a9b0_adr042_phase_b5_access_roles_seed.py` | `SECURITY_AUDITOR` seed |

---

## Tests

```bash
pytest tests/test_adr042_phase_b5_admin_guard.py tests/test_adr042_phase_b5_auth_policy.py -v
```

---

## Deferred to C1/C2

| Item | Phase |
|------|-------|
| Sysadmin React UI | C1 |
| Full password change + admin reset | C1/C2 |
| Sidebar/route enforcement via access_grants | C1 |
| Explicit NONE deny-wins | C2 |
| JWT lockout on every request (locked_at after login) | Already in `get_current_user` |

---

## Rollout recommendation

1. Deploy with all flags at defaults (no behavior change).
2. Set `ADR042_ADMIN_GUARD_MODE=access_grants_shadow` — monitor audit mismatches.
3. Grant `SYSADMIN_CABINET` to operators who should retain access without legacy privilege.
4. Switch to `access_grants_enforced` when grants verified.
5. Enable `ADR042_TOKEN_VERSION_ENFORCEMENT` after clients receive new tokens.
6. Enable `ADR042_MUST_CHANGE_PASSWORD_ENFORCEMENT` when password-change UI exists.
