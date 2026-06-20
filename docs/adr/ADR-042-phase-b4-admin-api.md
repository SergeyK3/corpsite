# ADR-042 Phase B4 — Sysadmin REST API

## Статус

**Implemented** (2026-06-20)

## Связанные документы

- [ADR-042 Phase B3 — Service Layer](./ADR-042-phase-b3-service-layer.md)
- [ADR-042 Phase B2 — Migration Plan](./ADR-042-phase-b2-migration-plan.md)
- [ADR-042 Phase A — Architecture](./ADR-042-phase-a-personnel-access-enrollment-architecture.md)

---

## Scope Phase B4

Backend REST API для будущего Sysadmin Cabinet UI.

| In scope | Out of scope |
|----------|--------------|
| `/admin/*` REST routes | React UI |
| Access / enrollment / drift / audit / users admin | Sidebar / route enforcement |
| Privileged guard (temporary) | Task RBAC changes |
| Pydantic schemas + tests | JWT lockout middleware |
| Security audit on dangerous actions | Password reset flow |

---

## Auth guard

All `/admin/*` routes require JWT via `get_current_user` and **`require_sysadmin_api`** (`app/security/admin_guard.py`).

| Who passes | Mechanism |
|------------|-----------|
| System admin | `role_id = 2` (`SYSTEM_ADMIN_ROLE_ID`) |
| Env privileged | `DIRECTORY_PRIVILEGED_USER_IDS` / `DIRECTORY_PRIVILEGED_ROLE_IDS` |

Uses existing `is_privileged()` — see [Phase B5 auth policy](./ADR-042-phase-b5-auth-policy.md) for guard modes (`ADR042_ADMIN_GUARD_MODE`).

Non-privileged users receive **403 Admin access required.**

---

## Endpoints

Base prefix: **`/admin`**

### B4.1 — Access API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/access/effective` | Paginated effective access per user (`explain_effective_access`) |
| GET | `/admin/access/effective/{user_id}` | Effective access + matched/deny grants explanation |
| GET | `/admin/access/grants` | List grants (`target_type`, `target_id`, `active_only`, pagination) |
| POST | `/admin/access/grants` | Create grant (validates target; writes `ACCESS_GRANTED` audit) |
| DELETE | `/admin/access/grants/{grant_id}` | Soft revoke (`ACCESS_REVOKED` audit) |

**Policy:** explicit `ACCESS_NONE` grants appear in `deny_grants[]`; resolver does **not** auto-deny (same as B3).

#### POST `/admin/access/grants` body

```json
{
  "access_role_id": 2,
  "target_type": "PERSON",
  "target_id": 123,
  "resource_key": "*",
  "scope_type": "GLOBAL",
  "scope_id": null,
  "include_subtree": false,
  "starts_at": null,
  "ends_at": null,
  "reason": "optional"
}
```

#### Effective access response (shape)

```json
{
  "user_id": 1,
  "employee_id": 10,
  "person_id": 5,
  "effective_role_code": "ACCESS_MANAGER",
  "access_level": "MANAGER",
  "level_rank": 20,
  "matched_grants": [],
  "deny_grants": [],
  "explanation": { "summary": "...", "steps": ["..."], "deny_enforcement_applied": false }
}
```

---

### B4.2 — Enrollment API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/enrollment/queue` | List queue items (`queue_status`, pagination) |
| POST | `/admin/enrollment/detect` | Run detector (`batch_id`, `dry_run`, `limit`) |
| POST | `/admin/enrollment/queue/{queue_id}/approve` | Approve PENDING item |
| POST | `/admin/enrollment/queue/{queue_id}/reject` | Reject PENDING/APPROVED item |
| POST | `/admin/enrollment/queue/{queue_id}/apply` | Apply APPROVED → employee + link |

**Rules:**

- Detect/enqueue **never** creates employees.
- Apply: one employee per person (reuse if exists).
- Assignment is enrollment unit (`employee_assignment_links`).
- Rejected items not reopened without new `change_event_id` (detector rule preserved).
- Approve/reject/apply → `enrollment_history` + `security_audit_log`.

#### Approve/reject body

```json
{ "comment": "optional decision note" }
```

#### Detect body

```json
{ "batch_id": null, "dry_run": false, "limit": 500 }
```

#### Apply response

```json
{
  "queue_id": 1,
  "queue_status": "ENROLLED",
  "person_id": 5,
  "assignment_id": 12,
  "employee_id": 99,
  "link_id": 7,
  "created_employee": true,
  "audit_id": 42
}
```

---

### B4.3 — Assignment reconciliation API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/assignments/drift` | Employees with snapshot drift vs primary assignment |
| POST | `/admin/assignments/reconcile/{employee_id}` | Reconcile one employee |

Query param **`dry_run`** defaults to **`true`**. Set `dry_run=false` to apply snapshot sync and write `ACCESS_CHANGED` audit.

---

### B4.4 — Security audit API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/security-audit` | Filtered audit log, newest first |

Query filters: `event_type`, `actor_user_id`, `target_user_id`, `target_person_id`, `target_employee_id`, `date_from`, `date_to`, `limit`, `offset`.

Metadata is sanitized on write — no password/token/secret/hash keys.

---

### B4.5 — Users admin API (minimal)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/users` | List users (no password fields) |
| GET | `/admin/users/{user_id}` | User detail |
| POST | `/admin/users/{user_id}/lock` | Set `locked_at`, `locked_reason`; bump `token_version`; `USER_LOCKED` audit |
| POST | `/admin/users/{user_id}/unlock` | Clear lock columns; `USER_UNLOCKED` audit |
| POST | `/admin/users/{user_id}/force-password-change` | Set `must_change_password=true`; bump `token_version` |

**Not included:** password reset (no hashing flow in B4).

Lock query param `reason`: `brute_force` | `admin` | `policy` | `security` (default `admin`).

---

## Files added

| File | Role |
|------|------|
| `app/security/admin_guard.py` | Temporary privileged guard |
| `app/api/admin_schemas.py` | Pydantic request/response models |
| `app/api/admin_router.py` | FastAPI routes |
| `app/services/enrollment_service.py` | Approve/reject/apply/list queue |
| `app/services/admin_users_service.py` | Lock/unlock/force-password-change |
| `tests/test_adr042_phase_b4_admin_api.py` | API integration tests |

**Modified:** `app/main.py` (router registration), `app/services/security_audit_service.py` (extended list filters).

---

## Services reused (B3)

- `access_resolver_service` — effective access
- `access_grant_service` — grant/revoke
- `enrollment_detector_service` — detect
- `assignment_reconciliation_service` — drift/reconcile
- `security_audit_service` — audit read/write

---

## Deferred to B5 / C1

| Item | Phase |
|------|-------|
| `access_grants` enforcement for `/admin/*` | B5 |
| JWT `token_version` validation on login | B5 |
| Login lockout / `must_change_password` middleware | B5 |
| Explicit NONE deny-wins enforcement | C1 |
| Sysadmin Cabinet React UI | C1 |
| Password reset admin action | When hashing flow ready |
| `REMOVED_ASSIGNMENT` apply (unenroll) | Future enrollment phase |

---

## Test coverage

`tests/test_adr042_phase_b4_admin_api.py`:

1. Non-admin → 403 on `/admin/*`
2. Admin lists effective access
3. Grant creates `access_grants` row
4. Revoke soft-revokes row
5. Grant/revoke writes `security_audit_log`
6. Detect does not create employees
7. Approve/reject writes `enrollment_history`
8. Apply creates/reuses employee + link
9. Reconcile defaults to `dry_run=true`
10. Lock/unlock updates columns + audit
11. Security audit filters and newest-first sort

Run:

```bash
pytest tests/test_adr042_phase_b4_admin_api.py -v
```

Requires ADR-042 B2 migrations applied.
