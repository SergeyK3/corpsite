# ADR-043 Phase P1 — Override Governance Audit

## Статус

**Prepared** (2026-06-20) — test case catalog and audit checklist; execute during June pilot.

## Objective

Verify override lifecycle (Tier 0/1/2), stewardship rules, effective value, history, audit trail, and permissions **without new code**.

## Reference implementation

| Layer | Location |
|-------|----------|
| Schema | `hr_review_overrides`, `hr_review_override_history` (B2) |
| Service | `hr_review_override_service.py` (B3) |
| Stewardship | `hr_override_stewardship_service.py` |
| API | `/admin/personnel/overrides/*` (C4.1) |
| UI | Overrides tab + drawer (C4.2) |
| Design | [ADR-043 Phase A.1](./ADR-043-phase-a1-override-governance.md) |

## Permissions

| Action | Required |
|--------|----------|
| List / create / revoke / reconfirm | `has_personnel_admin` (ADMIN or `HR_ENROLLMENT_MANAGER`) |
| Approve / reject | `has_hr_governance` |
| Tier 2 approve/reject | `has_hr_governance` + tier check |

---

## Test case matrix

### Legend

- **T0** Tier 0 — auto/low governance (e.g. display fields)
- **T1** Tier 1 — HR manager approval
- **T2** Tier 2 — senior HR / identity-critical

Each case: create → workflow action → verify effective + history + audit.

---

### Case G1 — Tier 0 override (display field)

| Field | Value |
|-------|-------|
| scope_type | `PERSON` |
| field_path | e.g. `display_name` or whitelisted note field |
| tier | 0 |
| owner_domain | `HR` |
| Expected workflow | Create → may auto-activate or fast approve per stewardship |

| # | Verification | Pass |
|---|--------------|------|
| G1.1 | Override created with `created_by_user_id` | ☐ |
| G1.2 | Effective person shows override in `applied_override_ids` | ☐ |
| G1.3 | `effective_payload[field]` = override value when active | ☐ |
| G1.4 | History event `CREATED` (+ `APPROVED` if applicable) | ☐ |

---

### Case G2 — Tier 1 override (roster field)

| Field | Value |
|-------|-------|
| field_path | e.g. `position_raw`, `department_raw` |
| tier | 1 |
| owner_domain | per stewardship seed (e.g. `HR`) |

| # | Step | Expected | Pass |
|---|------|----------|------|
| G2.1 | Create override | `status = pending_approval` | ☐ |
| G2.2 | Effective value **before** approve | Canonical (override not applied) | ☐ |
| G2.3 | Approve (HR governance user) | `status = active` | ☐ |
| G2.4 | Effective value **after** approve | Override value | ☐ |
| G2.5 | History | `CREATED` → `APPROVED` with actor ids | ☐ |
| G2.6 | UI | Approve button only for governance role | ☐ |

---

### Case G3 — Tier 2 override (identity-critical)

| Field | Value |
|-------|-------|
| field_path | e.g. `iin`, `full_name` (identity tier per stewardship) |
| tier | 2 |
| owner_domain | `HR` |

| # | Step | Expected | Pass |
|---|------|----------|------|
| G3.1 | Non-governance user approve | HTTP 403 | ☐ |
| G3.2 | Governance user approve | Success | ☐ |
| G3.3 | `approved_by_user_id` populated | ☐ |
| G3.4 | security_audit or history captures actor | ☐ |

---

### Case G4 — Reject

| # | Step | Expected | Pass |
|---|------|----------|------|
| G4.1 | Create Tier 1 pending override | pending | ☐ |
| G4.2 | Reject with reason | `status = rejected` | ☐ |
| G4.3 | Effective person | Canonical only | ☐ |
| G4.4 | History | `REJECTED` event with reason in metadata | ☐ |
| G4.5 | UI reject without reason | Validation error | ☐ |

---

### Case G5 — Reconfirm (stale)

| # | Step | Expected | Pass |
|---|------|----------|------|
| G5.1 | Active override with `stale_flag = true` | (may require diff or manual stale mark) | ☐ |
| G5.2 | Reconfirm action | Stale cleared; remains active | ☐ |
| G5.3 | History | `RECONFIRMED` event | ☐ |
| G5.4 | UI | Reconfirm visible only when stale + active | ☐ |

---

### Case G6 — Expire

| # | Step | Expected | Pass |
|---|------|----------|------|
| G6.1 | Override past expiry policy (if configured) | `status = expired` | ☐ |
| G6.2 | Effective value | Falls back to canonical | ☐ |
| G6.3 | History | `EXPIRED` event | ☐ |

*Note: if auto-expire job not scheduled, document manual SQL simulation for pilot only.*

---

### Case G7 — Revoke

| # | Step | Expected | Pass |
|---|------|----------|------|
| G7.1 | Revoke active override | Reason ≥ 10 chars required | ☐ |
| G7.2 | Status | `revoked` | ☐ |
| G7.3 | Effective value | Canonical restored | ☐ |
| G7.4 | History | `REVOKED` with reason | ☐ |
| G7.5 | UI confirm dialog | Shown before revoke | ☐ |

---

### Case G8 — Supersede

| # | Step | Expected | Pass |
|---|------|----------|------|
| G8.1 | Create override A (active) | active | ☐ |
| G8.2 | Create override B with `supersedes_override_id = A` | pending or active per rules | ☐ |
| G8.3 | Override A status | `superseded` | ☐ |
| G8.4 | `superseded_by_override_id` linked | ☐ |
| G8.5 | History on both | `SUPERSEDED` on A; `CREATED` on B | ☐ |
| G8.6 | Only one active per (scope_key, field_path) | B2 partial unique constraint | ☐ |

---

## Audit checklist — effective value

For each test override, record:

| Check | SQL / API | Pass |
|-------|-----------|------|
| Canonical value stored | `GET /admin/personnel/overrides/{id}` → `canonical_value` | ☐ |
| Override value stored | `override_value` | ☐ |
| Effective matches policy | `GET /admin/personnel/effective-person?person_key=…` | ☐ |
| Applied override IDs | `applied_override_ids` contains active override only | ☐ |
| Pending not in effective | pending override absent from effective payload | ☐ |

---

## Audit checklist — history

```sql
SELECT event_type, actor_user_id, event_at, metadata
FROM hr_review_override_history
WHERE override_id = :id
ORDER BY event_id;
```

| Event type | Must appear when | Verified |
|------------|------------------|----------|
| CREATED | Always on insert | ☐ |
| APPROVED | After approve | ☐ |
| REJECTED | After reject | ☐ |
| RECONFIRMED | After reconfirm | ☐ |
| MARKED_STALE | Stale detection | ☐ |
| EXPIRED | Expiry | ☐ |
| REVOKED | Revoke | ☐ |
| SUPERSEDED | Supersede chain | ☐ |
| VALUE_CHANGED | Value update (if supported) | ☐ |

**Append-only:** attempt UPDATE/DELETE on history → must fail (trigger).

---

## Audit checklist — permissions

| Actor | Create | Approve T1 | Approve T2 | Reject | Revoke | List |
|-------|--------|--------------|--------------|--------|--------|------|
| Regular user | 403 | 403 | 403 | 403 | 403 | 403 |
| HR_ENROLLMENT_MANAGER | 200 | 200 | 200 | 200 | 200 | 200 |
| SysAdmin (privileged) | 200 | 200 | 200 | 200 | 200 | 200 |
| HR without grant | 403 | 403 | 403 | 403 | 403 | 403 |

Execute via API or UI with JWT for each actor.

---

## Audit checklist — stewardship

| # | Check | Pass |
|---|-------|------|
| S1 | Tier for `iin` matches seed (Tier 2) | ☐ |
| S2 | Unknown field_path falls back to `%` rule | ☐ |
| S3 | Wrong `owner_domain` rejected on create | ☐ |
| S4 | Duplicate active override blocked | ☐ |

```sql
SELECT field_path, tier, owner_domain
FROM hr_override_stewardship_rules
ORDER BY field_path;
```

---

## Duplicate override validation (post-lifecycle)

From validation panel / API:

| Check | Expected |
|-------|----------|
| `duplicate_active_overrides` count | 0 |
| Samples empty | ☐ |

---

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| HR governance owner | | | |
| SysAdmin | | | |

---

## Related documents

- [P1 Pilot Checklist](./ADR-043-phase-p1-pilot-checklist.md)
- [ADR-043 Phase A.1](./ADR-043-phase-a1-override-governance.md)
- [ADR-043 Phase B2 validation SQL](./ADR-043-phase-b2-validation.sql)
