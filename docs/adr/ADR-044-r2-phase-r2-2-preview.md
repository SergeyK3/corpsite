# ADR-044 Phase R2.2 — User Linkage Dry-Run Preview Engine

## Status

**Implemented** (2026-06-21) — backend preview only.

**No writes occur in Phase R2.2.**

| Phase | Scope | Status |
|-------|-------|--------|
| R2.1 | Validation SQL + dry-run contract | Complete |
| R2.2 | Preview service + read-only API | **Complete** |
| R2.3+ | Execute, journal, UI | Not started |

## Related documents

| Document | Role |
|----------|------|
| [ADR-044 Identity Reconciliation](./ADR-044-identity-reconciliation.md) | Ratified R2 scope |
| [ADR-044 R2 Discovery](./ADR-044-r2-user-linkage-discovery.md) | Inventory, policy, local audit |
| [ADR-044 R2.1 Validation SQL](./ADR-044-phase-r2-validation.sql) | Read-only SQL gates |

---

## 1. Architecture

```text
GET /admin/personnel/identity/user-linkage/preview
        │
        ▼
personnel_admin_router.admin_preview_user_linkage()
        │
        ▼
user_linkage_preview_service.run_user_linkage_preview(conn)
        │
        ├── load active unlinked users (employee_id IS NULL)
        ├── load active employees (draft/active/suspended)
        ├── build FIO + login indexes
        └── classify each user → candidate DTO
```

**Module:** `app/services/user_linkage_preview_service.py`

**Guarantees:**

- SELECT-only database access
- No `users.employee_id` updates
- No execute mode
- `AUTO_LINK_SAFE` count always **0** under current policy

---

## 2. Classification rules

### Outcome buckets

| Classification | Meaning |
|----------------|---------|
| `AUTO_LINK_SAFE` | Disabled in R2.2 — never emitted |
| `REVIEW_REQUIRED` | Medium-confidence match — HR review only |
| `AMBIGUOUS` | Multiple users and/or employees — no link |
| `IMPOSSIBLE` | No valid target |
| `EXCLUDED_SERVICE_ACCOUNT` | Admin/system/service — skip linkage |

### Evaluation order (per user)

1. **Service exclusion** → `EXCLUDED_SERVICE_ACCOUNT`
2. **Ambiguity: conflicting employee targets** (login vs FIO disagree) → `AMBIGUOUS` / `MULTIPLE_EMPLOYEE_MATCHES`
3. **Ambiguity: multiple users, same login target** → `AMBIGUOUS` / `MULTIPLE_USER_MATCHES`
4. **Ambiguity: FIO collision group** (>1 user or >1 employee same normalized name) → `AMBIGUOUS` / `FIO_COLLISION`
5. **Login suffix → missing employee** → `IMPOSSIBLE` / `MISSING_EMPLOYEE`
6. **Login suffix → inactive employee** → `IMPOSSIBLE` / `INACTIVE_EMPLOYEE`
7. **Login suffix → active employee** → `REVIEW_REQUIRED` / `LOGIN_SUFFIX_MATCH`
8. **Unique FIO 1:1** → `REVIEW_REQUIRED` / `FIO_EXACT_MATCH`
9. **No match** → `IMPOSSIBLE` / `NO_MATCH`

### Match strategies

| Strategy | Rule | Classification |
|----------|------|----------------|
| `LOGIN_SUFFIX` | `login ~ '^.+_[0-9]+$'` and suffix = `employees.employee_id` | `REVIEW_REQUIRED` |
| `NORMALIZED_FIO` | `normalize(user.full_name) = normalize(employee.full_name)` with exactly one user and one employee | `REVIEW_REQUIRED` |

**Normalization:** lowercase, trim, collapse whitespace.

### Service account exclusion (R2.1 parity)

- `role_id = 2` (SYSTEM_ADMIN)
- Login / google_login prefix: `admin`, `system`, `service`, `cron`, `bot`, `api`, `internal`, `sysadmin`
- Login `admin_*` or `*_admin`
- Display name markers: `системн`, `service account`, `bot`, `cron`

---

## 3. API contract

### Endpoint

```http
GET /admin/personnel/identity/user-linkage/preview
Authorization: Bearer <token>
```

**Auth:** personnel admin (`require_personnel_admin_api`) — same as other `/admin/personnel/*` routes.

### Response

```json
{
  "phase": "R2",
  "dry_run": true,
  "generated_at": "2026-06-21T15:30:00+00:00",
  "summary": {
    "total_users": 326,
    "auto_link_safe": 0,
    "review_required": 45,
    "ambiguous": 0,
    "impossible": 279,
    "excluded": 2
  },
  "candidates": [
    {
      "user_id": 28,
      "login": "amb_surg_head_28",
      "proposed_employee_id": 28,
      "employee_name": "Акильтаева Бакыт Сагитовна",
      "match_strategy": "LOGIN_SUFFIX",
      "classification": "REVIEW_REQUIRED",
      "confidence": "medium",
      "reason_codes": ["LOGIN_SUFFIX_MATCH"],
      "blockers": [],
      "requires_manual_confirmation": true
    }
  ]
}
```

### Candidate fields

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | int | Source user |
| `login` | string \| null | Auth login |
| `proposed_employee_id` | int \| null | Suggested employee target |
| `employee_name` | string \| null | Target employee display name |
| `match_strategy` | string \| null | `LOGIN_SUFFIX` or `NORMALIZED_FIO` |
| `classification` | string | Outcome bucket |
| `confidence` | string \| null | `medium` for review, `low` for impossible |
| `reason_codes` | string[] | Machine-readable explainers |
| `blockers` | string[] | Hard validation stops |
| `requires_manual_confirmation` | bool | `true` for `REVIEW_REQUIRED` |

### Reason codes

| Code | Classification |
|------|----------------|
| `LOGIN_SUFFIX_MATCH` | `REVIEW_REQUIRED` |
| `FIO_EXACT_MATCH` | `REVIEW_REQUIRED` |
| `SERVICE_ACCOUNT` | `EXCLUDED_SERVICE_ACCOUNT` |
| `MULTIPLE_EMPLOYEE_MATCHES` | `AMBIGUOUS` |
| `MULTIPLE_USER_MATCHES` | `AMBIGUOUS` |
| `FIO_COLLISION` | `AMBIGUOUS` |
| `MISSING_EMPLOYEE` | `IMPOSSIBLE` |
| `INACTIVE_EMPLOYEE` | `IMPOSSIBLE` |
| `NO_MATCH` | `IMPOSSIBLE` |

---

## 4. Examples

### Login suffix (review)

User `admission_head_7` → employee `7` (active):

```json
{
  "classification": "REVIEW_REQUIRED",
  "match_strategy": "LOGIN_SUFFIX",
  "reason_codes": ["LOGIN_SUFFIX_MATCH"],
  "requires_manual_confirmation": true
}
```

### FIO 1:1 (review)

User and employee share unique normalized full name, no login suffix:

```json
{
  "classification": "REVIEW_REQUIRED",
  "match_strategy": "NORMALIZED_FIO",
  "reason_codes": ["FIO_EXACT_MATCH"],
  "requires_manual_confirmation": true
}
```

### Service account (excluded)

```json
{
  "classification": "EXCLUDED_SERVICE_ACCOUNT",
  "reason_codes": ["SERVICE_ACCOUNT"],
  "requires_manual_confirmation": false
}
```

### FIO collision (ambiguous)

Two employees share the same normalized name:

```json
{
  "classification": "AMBIGUOUS",
  "reason_codes": ["FIO_COLLISION"],
  "requires_manual_confirmation": true
}
```

---

## 5. Verification

```bash
# Run tests
pytest tests/test_adr044_phase_r2_2_user_linkage_preview.py -q

# Call API (privileged user)
curl -s -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/admin/personnel/identity/user-linkage/preview | jq .
```

Compare summary counts with [R2.1 validation SQL](./ADR-044-phase-r2-validation.sql) on the same database.

---

## 6. Non-goals (R2.2)

- No migrations
- No `users.employee_id` writes
- No execute endpoint
- No admin UI
- No review queue persistence
- No `AUTO_LINK_SAFE` candidates

---

## 7. Next phase (R2.3 preview)

- Journal DDL (`identity_reconciliation_runs.phase = 'R2'`)
- `USER_EMPLOYEE_LINKED` audit event
- Execute endpoint (auto-link tier 0–1 only, when policy allows)
- Review queue API + admin UI
