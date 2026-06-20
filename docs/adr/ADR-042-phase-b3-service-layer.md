# ADR-042 Phase B3 — Service Layer

## Статус

**Implemented** (2026-06-20)

## Связанные документы

- [ADR-042 Phase B2 — Migration Plan](./ADR-042-phase-b2-migration-plan.md)
- [ADR-042 Phase B1 — DB Schema Design](./ADR-042-phase-b1-schema-design.md)

---

## Scope Phase B3

Backend service layer **без API, UI и enforcement**.

| In scope | Out of scope |
|----------|--------------|
| Effective access resolver (read-only) | Sidebar / route enforcement |
| Access grant/revoke services | JWT lockout middleware |
| Assignment reconciliation (dry-run default) | Runtime dual-write |
| Enrollment detector → queue | Auto-create employees |
| Security audit writer | Admin Cabinet UI |
| Unit/integration tests | Task RBAC changes |

---

## Services added

| Service | Path | Role |
|---------|------|------|
| Security audit | `app/services/security_audit_service.py` | Append-only audit + metadata sanitization |
| Access grants | `app/services/access_grant_service.py` | Grant/revoke + audit on change |
| Access resolver | `app/services/access_resolver_service.py` | Effective access calculation |
| Assignment reconciliation | `app/services/assignment_reconciliation_service.py` | Drift detect/fix (explicit apply) |
| Enrollment detector | `app/services/enrollment_detector_service.py` | hr_change_events → enrollment_queue |

---

## B3.1 — Effective Access Resolver

### Public functions

| Function | Description |
|----------|-------------|
| `resolve_effective_access(user_id)` | MAX(level_rank) for user via USER/EMPLOYEE/PERSON/ASSIGNMENT/POSITION/ORG_UNIT grants |
| `resolve_person_access(person_id)` | Same resolver without user context |
| `explain_effective_access(user_id=..., person_id=...)` | Resolver output + step-by-step explanation |

### Behaviour

- **Read-only** — no middleware, no route guards.
- **Orthogonal to task `roles`** — uses `access_roles` / `access_grants` only.
- Filters: `active_flag`, `starts_at <= now`, `ends_at IS NULL OR > now`.
- **Implicit NONE** when no allow grants match (`level_rank = 0`).
- **Explicit NONE deny grants** are returned in `deny_grants[]` but **not applied** to effective rank in B3 (`deny_enforcement_applied: false`).

### Return shape (example)

```json
{
  "effective_role_code": "ACCESS_MANAGER",
  "access_level": "MANAGER",
  "level_rank": 20,
  "matched_grants": [...],
  "deny_grants": [],
  "explanation": { "summary": "...", "deny_enforcement_applied": false }
}
```

---

## B3.2 — Access Grant Service

### Public functions

| Function | Description |
|----------|-------------|
| `grant_access(...)` | Insert grant; validates target; writes `ACCESS_GRANTED` audit |
| `revoke_access(...)` | Soft revoke (`active_flag=false`, `revoked_at`); writes `ACCESS_REVOKED` audit |
| `list_access_grants(...)` | Query grants |
| `validate_grant_target(target_type, target_id)` | Polymorphic FK existence check |
| `create_security_audit_event(...)` | Delegates to security audit service |

### Deny (NONE) policy

- `ACCESS_NONE` grants may be created via `access_role_id` for `ACCESS_NONE`.
- Resolver lists them in `deny_grants` but does **not** auto-deny in B3.
- Full deny-wins enforcement deferred to B4/C.

---

## B3.3 — Assignment Reconciliation Service

### Public functions

| Function | Default | Description |
|----------|---------|-------------|
| `compare_employee_snapshot_to_primary_assignment(employee_id)` | — | Field-level diff employees ↔ primary assignment |
| `list_assignment_drift(limit, offset)` | — | All employees with snapshot drift |
| `reconcile_employee_primary_assignment(employee_id, dry_run=True)` | **dry_run** | Preview or apply sync employees ← assignment |
| `reconcile_all(dry_run=True, limit=500)` | **dry_run** | Batch reconciliation |

### Apply mode

- `dry_run=False` updates legacy `employees` snapshot columns from primary `person_assignments`.
- Writes `ACCESS_CHANGED` audit with `metadata.action = assignment_reconciled`.
- **No runtime dual-write** — apply is explicit operator/service action only.

### Expected on dev DB after B2

~70 drift rows (mostly `date_from` NULL vs assignment `start_date`).

---

## B3.4 — Enrollment Detector

### Public functions

| Function | Default | Description |
|----------|---------|-------------|
| `detect_enrollment_candidates(batch_id=None, dry_run=True)` | **dry_run** | Scan `hr_change_events` → candidate list |
| `enqueue_enrollment_candidate(...)` | dry_run=False when called directly | Insert into `enrollment_queue` + `DETECTED` history |
| `supersede_stale_queue_items(..., dry_run=True)` | **dry_run** | Mark old PENDING/APPROVED as SUPERSEDED |
| `explain_candidate(queue_id)` | — | Human-readable queue item explanation |

### Rules enforced

- **Never creates `employees`** — queue only.
- Idempotency via `idempotency_key` (unique for active PENDING/APPROVED).
- **REJECTED** items not reopened without new `change_event_id`.
- Event mapping: `NEW` → `NEW_ASSIGNMENT`, `REMOVED` → `REMOVED_ASSIGNMENT`, `POSITION_CHANGED`/`DEPARTMENT_CHANGED` → `CHANGED_ASSIGNMENT`.

---

## B3.5 — Security Audit Writer

### Public functions

| Function | Description |
|----------|-------------|
| `write_security_event(...)` | Insert append-only row |
| `list_security_events(...)` | Filtered query |
| `sanitize_metadata(metadata)` | Strip/forbid password-like keys |

### Forbidden metadata keys (reject)

`password`, `password_plain`, `password_hash`, `temp_password`, `token`, `secret`, `hash`, and pattern matches.

---

## Tests

```bash
pytest tests/test_adr042_phase_b3_access_resolver.py -v
pytest tests/test_adr042_phase_b3_assignment_reconciliation.py -v
pytest tests/test_adr042_phase_b3_enrollment_detector.py -v
pytest tests/test_adr042_phase_b3_security_audit.py -v
```

Coverage:

1. USER/EMPLOYEE/PERSON grants → effective access  
2. POSITION/ORG_UNIT inherited grants  
3. MAX rank resolver  
4. Revoked grant ignored  
5. Audit on grant/revoke  
6. Password-like metadata rejected  
7. Drift detection  
8. Reconciliation dry_run no mutation  
9. Enrollment enqueue idempotent  
10. Detector dry_run no new employees  

---

## Enforcement status

| Capability | B3 status |
|------------|-----------|
| Calculate effective access | ✅ Service only |
| Enforce access on UI/API | ❌ B4/C |
| Auto sync assignments on HR ops | ❌ B4 dual-write flag |
| JWT lockout / must_change_password | ❌ B4 auth |
| Enrollment approve/apply API | ❌ B4 |
| Admin Cabinet UI | ❌ C |

---

## Remains for B4 / C

- REST API: `/admin/access/*`, `/admin/enrollment/*`, `/admin/audit/*`
- Middleware / dependency for optional access checks (feature-flagged)
- Auth policy using `users.token_version`, lockout columns
- Enrollment approve → apply (create links, not auto employee unless approved)
- Deny-wins evaluator for explicit NONE grants
- Sysadmin Cabinet UI (SA-1 … SA-14)
- Extend `security_audit_log.event_type` CHECK if new actions needed

---

## Usage examples (Python shell)

```python
from app.services.access_resolver_service import explain_effective_access
from app.services.assignment_reconciliation_service import list_assignment_drift, reconcile_all
from app.services.enrollment_detector_service import detect_enrollment_candidates

explain_effective_access(user_id=1)
list_assignment_drift(limit=20)
reconcile_all(dry_run=True)
detect_enrollment_candidates(dry_run=True)
```
