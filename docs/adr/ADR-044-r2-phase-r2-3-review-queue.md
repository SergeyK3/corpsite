# ADR-044 Phase R2.3 — User Linkage Review Queue

## Status

**Implemented** (2026-06-21) — review workflow, decision persistence, audit trail, admin UI.

**No writes to `users.employee_id` occur in Phase R2.3.**

| Phase | Scope | Status |
|-------|-------|--------|
| R2.1 | Validation SQL + dry-run contract | Complete |
| R2.2 | Preview service + read-only API | Complete |
| R2.3 | Review queue + decisions + audit + UI | **Complete** |
| R2.4+ | Execute linkage | Not started |

## Related documents

| Document | Role |
|----------|------|
| [ADR-044 Identity Reconciliation](./ADR-044-identity-reconciliation.md) | Ratified R2 scope |
| [ADR-044 R2 Discovery](./ADR-044-r2-user-linkage-discovery.md) | Inventory, policy |
| [ADR-044 R2.2 Preview](./ADR-044-r2-phase-r2-2-preview.md) | Classification engine |
| [ADR-044 R2.1 Validation SQL](./ADR-044-phase-r2-validation.sql) | Read-only SQL gates |

---

## 1. Architecture

```text
GET /admin/personnel/identity/user-linkage/review
POST /admin/personnel/identity/user-linkage/review/{user_id}/approve|reject|defer
GET /admin/personnel/identity/user-linkage/review/audit
        │
        ▼
personnel_admin_router (require_personnel_admin_api)
        │
        ├── list_user_linkage_review_queue()
        │       └── run_user_linkage_preview()  (R2.2, read-only)
        │       └── merge latest decisions from user_linkage_review_decisions
        │
        ├── record_user_linkage_review_decision()
        │       └── INSERT append-only audit row
        │       └── assert users.employee_id unchanged
        │
        └── list_user_linkage_review_audit()
                └── immutable decision history
```

**Modules:**

- `app/services/user_linkage_preview_service.py` — classification (unchanged from R2.2)
- `app/services/user_linkage_review_service.py` — review queue + decisions + audit
- `corpsite-ui/.../UserLinkageReviewTab.tsx` — System Administrator Cabinet tab

**Migration:** `c2d3e4f5a6b7_adr044_r2_3_user_linkage_review_schema.py`

---

## 2. Review workflow

### Lifecycle

1. **Preview (R2.2)** classifies each active unlinked user.
2. **Review queue (R2.3)** surfaces preview candidates enriched with the latest human decision.
3. **Reviewer action** records intent only — `APPROVE`, `REJECT`, or `DEFER`.
4. **Execute (R2.4, future)** will consume approved decisions and write `users.employee_id`.

### Decision semantics

| Decision | Meaning | Linkage |
|----------|---------|---------|
| `APPROVE` | Reviewer confirms proposed User ↔ Employee match | **Not performed in R2.3** |
| `REJECT` | Reviewer rejects the proposed match | No linkage |
| `DEFER` | Reviewer postpones decision | No linkage |
| `PENDING` | No decision recorded yet (virtual state) | No linkage |

**Approve constraints (R2.3):**

- Allowed only for `REVIEW_REQUIRED` or `AMBIGUOUS` classifications
- Requires `proposed_employee_id` from current preview snapshot
- Does **not** update `users.employee_id`

Reject and defer are allowed for any preview candidate (including `IMPOSSIBLE`), except users that already have `employee_id` set.

---

## 3. Audit model

Table: `public.user_linkage_review_decisions`

Append-only — each reviewer action inserts a new row. Latest decision per `user_id` is derived with `DISTINCT ON (user_id) ... ORDER BY created_at DESC`.

| Column | Purpose |
|--------|---------|
| `decision_id` | Surrogate key |
| `reviewer_user_id` | Who reviewed |
| `user_id` | Candidate user |
| `proposed_employee_id` | Snapshot at decision time |
| `classification` | Preview classification snapshot |
| `match_strategy` | Preview strategy snapshot |
| `decision` | `APPROVE` / `REJECT` / `DEFER` |
| `reason` | Optional reviewer comment |
| `created_at` | Immutable timestamp |

**Audit API:** `GET /admin/personnel/identity/user-linkage/review/audit`

Returns full history (newest first), optionally filtered by `user_id`.

---

## 4. Review queue API

### List queue

`GET /admin/personnel/identity/user-linkage/review`

Query parameters:

| Param | Description |
|-------|-------------|
| `classification` | Filter by preview classification |
| `strategy` | Filter by `LOGIN_SUFFIX` or `NORMALIZED_FIO` |
| `decision_state` | `PENDING`, `APPROVE`, `REJECT`, `DEFER` |
| `search` | Substring match on login, user name, or employee name |
| `limit`, `offset` | Pagination |

Response includes:

- `summary` — counts for review required, ambiguous, approved, rejected, deferred, pending
- `candidates` — preview fields + decision enrichment

### Record decision

| Method | Path |
|--------|------|
| POST | `/admin/personnel/identity/user-linkage/review/{user_id}/approve` |
| POST | `/admin/personnel/identity/user-linkage/review/{user_id}/reject` |
| POST | `/admin/personnel/identity/user-linkage/review/{user_id}/defer` |

Body: `{ "reason": "optional comment" }`

---

## 5. Admin UI

**Location:** System Administrator Cabinet → tab **User Linkage Review**

Sections:

1. **Safety banner** — explicit no-linkage warning
2. **Summary cards** — Review Required, Ambiguous, Approved, Rejected, Deferred
3. **Filters** — classification, strategy, decision state, search
4. **Candidate table** — login, user, proposed employee, strategy, classification, confidence, reason codes, decision, actions
5. **Audit trail** — recent immutable decisions

Actions call approve/reject/defer endpoints only — no execute control.

---

## 6. Safety guarantees

| Guarantee | R2.3 behavior |
|-----------|---------------|
| `users.employee_id` unchanged | Enforced in service before and after decision insert |
| No automatic linking | Preview policy unchanged; `AUTO_LINK_SAFE` still never emitted |
| No execute endpoint | Not implemented |
| Immutable audit | Append-only `user_linkage_review_decisions` table |

---

## 7. Relation to future Execute phase (R2.4)

R2.4 will:

- Read approved decisions (and/or re-validate against fresh preview)
- Write `users.employee_id` inside a transactional execute run
- Extend `identity_reconciliation_runs.phase` to `'R2'`
- Emit `USER_EMPLOYEE_LINKED` security audit events
- Provide explicit execute API with dry-run confirmation

R2.3 decisions are **inputs** to R2.4, not substitutes for execute.

---

## 8. Tests

| Layer | File |
|-------|------|
| Backend service + API | `tests/test_adr044_phase_r2_3_user_linkage_review.py` |
| Frontend API client | `corpsite-ui/.../userLinkageReviewApi.client.test.ts` |
| Frontend tab | `corpsite-ui/.../UserLinkageReviewTab.test.tsx` |

Coverage includes: queue list, filters, approve/reject/defer persistence, audit ordering, auth guard, and `users.employee_id` unchanged after approve.
