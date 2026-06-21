# ADR-044 Phase R2 — User Linkage Discovery

## Статус

**R2.1 Validation** (2026-06-21) — read-only SQL pack + dry-run contract documented.

| Phase | Status |
|-------|--------|
| R2.0 Discovery | Complete |
| R2.1 Validation SQL + dry-run contract | **Complete** (this update) |
| R2.2+ Implementation | Not started |

No application code changes. No migrations. No data modifications in R2.1.

## Связанные документы

| Document | Role |
|----------|------|
| [ADR-044 Identity Reconciliation](./ADR-044-identity-reconciliation.md) | Ratified R2 scope, §2.2 priority chain, V3 validation |
| [ADR-044 Phase R1a Blueprint](./ADR-044-phase-r1a-implementation-blueprint.md) | Confirms `users.employee_id` deferred to R2 |
| [ADR-044 Phase R1a Validation SQL](./ADR-044-phase-r1a-validation.sql) | Baseline snapshot helper for `users.employee_id` |
| [ADR-044 Phase R2.1 Validation SQL](./ADR-044-phase-r2-validation.sql) | Read-only user linkage gates (R2.1) |
| [ADR-042 Phase B2 Migration Plan](./ADR-042-phase-b2-migration-plan.md) | `persons`, `employees.person_id`, assignment links |
| [OPS Backlog — OPS-007](../roadmap/ops-backlog.md) | Telegram bot audit blocked by R2 |

---

## 1. Executive summary

ADR-044 **R1a is complete**: `persons.iin`, `employee_identities`, reconciliation journal, and identity candidate apply are implemented.

**R2 is not started.** Schema support for `users.employee_id` exists (nullable FK + partial unique index since migration `c3d8e12a5f01`), but:

- No backfill service or API
- No R2 journal schema (`identity_reconciliation_runs.phase` locked to `'R1a'` only)
- No `USER_EMPLOYEE_LINKED` audit event type
- No admin review queue UI

**June Pilot identity audit (2026-06-20, local pilot DB — ADR-044 Context):**

| Metric | Value |
|--------|-------|
| Active users with `employee_id` | **0 / 273** |
| Active users with `employee_id IS NULL` | **273 / 273** |
| Persons with resolvable IIN gap before R1a | 67/87 (64 with canonical IIN) |

Production/VPS counts must be refreshed with the SQL pack in **Appendix A** before R2 execute. This document treats pilot figures as **reference baseline**, not live guarantees.

**Recommendation:** Proceed with **R2.1 dry-run + review queue** before any auto-link execute. Auto-link only **high-confidence** paths (existing FK, assignment-bridge with single employee). Map user-requested strategies A–E onto ADR §2.2 with explicit collision rules. Defer Telegram operational audit (OPS-007) until R2 completes.

### 1.1 Local audit snapshot (2026-06-21)

Run pack: [`ADR-044-phase-r2-validation.sql`](./ADR-044-phase-r2-validation.sql) against local pilot DB.

**Audit date:** 2026-06-21

**Current local DB results:**

| Metric | Count |
|--------|------:|
| Active users linked (`employee_id` set) | **0** |
| Active users unlinked (`employee_id IS NULL`) | **326** |
| Active employees with linked user | **0** |
| Active employees without linked user | **105** |
| Login pattern candidates | **14** |
| FIO collision groups | **0** |
| Unique 1:1 normalized FIO matches | **31** |
| Telegram without employee | **0** |

**Interpretation:**

- No existing User → Employee linkage exists.
- Login-pattern matches are **review-only** (14 candidates).
- Normalized FIO 1:1 matches are **review-only** unless later approved by policy (31 candidates).
- **No auto-link should execute yet** — `AUTO_LINK_SAFE` bucket must remain empty in R2.1.
- Telegram is not currently blocked by orphan telegram-bound users, but **OPS-007 remains blocked** until R2 validation and execute complete.

VPS/production counts must still be refreshed with the same SQL pack before any R2 execute.

---

## 2. Inventory

### 2.1. Entity relationship (target chain)

```text
users.employee_id  →  employees.employee_id  →  employees.person_id  →  persons
                              ↓
                    employee_identities (IIN mirror)
users.telegram_id  →  users.user_id            (separate auth/delivery contour)
```

### 2.2. `users`

**Migrations:** `alembic/versions/02b0d99063cd_baseline.py`, `u3v4w5x6y7z8_adr042_phase_b2_1_schema.py`, `c3d8e12a5f01_add_users_employee_id.py`

| Column | Nullable | Notes |
|--------|----------|-------|
| `user_id` | NO | PK, identity |
| `full_name` | NO | Display / matching input |
| `login` | YES | Local auth login |
| `google_login` | YES | Legacy Google auth; **no separate `email` column** |
| `phone` | YES | |
| `telegram_id` | YES | Telegram bind (delivery) |
| `telegram_username` | YES | |
| `telegram_bound_at` | YES | |
| `role_id` | NO | FK → `roles` |
| `unit_id` | YES | FK → `org_units` |
| `employee_id` | YES | **R2 target**; FK → `employees` |
| `is_active` | NO | default TRUE |
| `password_hash`, lock fields, `token_version`, … | ADR-042 B2.1 | Auth policy |

**Constraints:**

| Constraint | Type | Effect |
|------------|------|--------|
| `fk_users_employee` | FK | `employee_id → employees(employee_id)` |
| `uq_users_employee_id` | UNIQUE partial | At most **one user per employee** when linked |
| `fk_users_role`, `fk_users_unit` | FK | Org/auth |

**Gaps:** No FK to `persons`. No IIN on user row. Email match (strategy D) must use `google_login` proxy or external contact tables — not first-class on `users`.

---

### 2.3. `employees`

**Migrations:** baseline + `u3v4w5x6y7z8_adr042_phase_b2_1_schema.py`, `v4w5x6y7z8a9_adr042_phase_b2_3_backfill.py`

| Column | Nullable | Notes |
|--------|----------|-------|
| `employee_id` | NO | PK |
| `full_name` | NO | HR display name |
| `person_id` | YES | FK → `persons`; bridge to identity |
| `operational_status` | NO | `draft` / `active` / `suspended` / `terminated` |
| `org_unit_id`, `position_id`, `department_id` | YES | Org placement |
| `enrolled_at`, `enrolled_by_user_id`, … | YES | Enrollment metadata |

**Constraints:**

| Constraint | Effect |
|------------|--------|
| `fk_employees_person` | `person_id → persons` ON DELETE RESTRICT |
| `uq_employees_person_active` | One active operational employee per `person_id` (partial unique) |
| `ix_employees_person_id` | Lookup by person |

**Linkage note:** Multiple historical employees per person possible if terminated; active cohort governed by partial unique index.

---

### 2.4. `persons`

**Migration:** `u3v4w5x6y7z8_adr042_phase_b2_1_schema.py`

| Column | Nullable | Notes |
|--------|----------|-------|
| `person_id` | NO | PK |
| `full_name`, `last_name`, `first_name`, `middle_name` | mixed | Identity display |
| `iin` | YES | **R1a materialized**; 12-digit CHECK |
| `match_key` | NO | Operational bridge key (`emp:` / `iin:` / `name:`) |
| `person_status` | NO | `active` / `inactive` / `merged` |
| `birth_date` | YES | FIO+dob matching |
| `merged_into_person_id` | YES | FK self |

**Constraints:**

| Index | Effect |
|-------|--------|
| `uq_persons_iin_active` | One active person per IIN |
| `uq_persons_match_key_active` | One active/inactive person per `match_key` |

---

### 2.5. `employee_identities`

**Migration:** `c1a8f92e4b03_hr_import_identity_staging_phase_2a.py`

| Column | Nullable | Notes |
|--------|----------|-------|
| `identity_id` | NO | PK |
| `employee_id` | NO | FK → `employees` CASCADE |
| `identity_type` | NO | e.g. `IIN` |
| `identity_value` | NO | Normalized identity string |
| `valid_from`, `valid_to` | YES | Temporal validity |
| `is_primary` | NO | |
| `created_by` | YES | FK → `users` |

**Constraints:**

| Index | Effect |
|-------|--------|
| `uq_employee_identities_iin_active` | **Globally unique** active IIN (`identity_type='IIN'`, `valid_to IS NULL`) |

**R1a:** Upserts IIN rows for linked employees. Supports IIN-based verification after person↔employee bridge is known.

---

### 2.6. Supporting tables (R2 inputs)

| Table | R2 relevance |
|-------|----------------|
| `employee_assignment_links` | ADR §2.2 priority #2 — assignment bridge → employee |
| `person_assignments` | Context for link integrity |
| `hr_canonical_snapshot_entries` | Roster `employee_id`, names for canonical name match |
| `identity_reconciliation_runs` / `_items` | R1a journal; **phase CHECK = `'R1a'` only** — R2 needs extension |
| `security_audit_log` | `PERSON_IIN_RECONCILED` exists; **`USER_EMPLOYEE_LINKED` not registered** |

---

### 2.7. Row count discovery (operator SQL)

Run on target DB before R2 execute (see Appendix A.1). Expected output shape:

| check_name | metric |
|------------|--------|
| `table_row_counts` | `users`, `employees`, `persons`, `employee_identities` totals |
| `users_with_employee_id` | linked count |
| `users_without_employee_id` | unlinked count |
| `employees_with_user` | employees having ≥1 user |
| `employees_without_user` | active employees with no user |

---

## 3. Current linkage audit

### 3.1. Known state (pilot DB, pre-R2)

| Question | Pilot reference (2026-06-20) |
|----------|------------------------------|
| Users with `employee_id` set | **0** |
| Users with `employee_id IS NULL` | **273** (all active users) |
| Employees with linked user | **~0** (symmetric) |
| Employees without linked user | **all active employees** |

### 3.2. Code paths that consume `users.employee_id`

| Component | Path | Behavior when NULL |
|-----------|------|-------------------|
| Access resolver | `app/services/access_resolver_service.py` | EMPLOYEE/PERSON/ASSIGNMENT grant subjects empty → **grants fail** |
| Working contacts | `app/directory/working_contacts_routes.py` | LEFT JOIN `employees` → **position/org HR fields missing** |
| User create API | `app/directory/users_routes.py` | **Requires** `employee_id` for **new** users only |
| Enrollment | `app/services/enrollment_service.py` | Creates employee + links; **does not set** `users.employee_id` |
| Terminate employee | `app/services/directory_service.py` | Deactivates user `WHERE employee_id = :id` — **no-op if unlinked** |
| R1a reconciliation | `identity_reconciliation_service.py` | **Explicitly read-only** on `users.employee_id` |

### 3.3. Duplicate assignment detection (visibility-adjacent pattern)

R2 should detect **duplicate user→employee links** before write:

- Partial unique index prevents two users on same `employee_id`
- No DB constraint prevents duplicate **logical intent** (same user linked twice via re-run) — journal + idempotency required

For **unlinked** users, duplicate risk is **wrong employee assignment**, not duplicate rows.

---

## 4. Candidate matching strategies

User-requested evaluation order **A → E**, mapped to ADR-044 §2.2 and implementation feasibility.

### 4.1. Strategy A — Existing `users.employee_id`

| | |
|--|--|
| **Rule** | Row already has non-null FK |
| **Confidence** | **Certain** |
| **Auto-link** | N/A (already linked) |
| **Collision risk** | **Low** — validate FK target exists (V3a orphan check) |
| **Pilot estimate** | **0 rows** (all NULL) |

---

### 4.2. Strategy B — IIN match

| | |
|--|--|
| **Rule** | Match user to employee where IIN aligns |
| **Feasible path** | `users` has **no IIN column**. Indirect paths only: (1) user matched to `persons.iin` via another key then single employee for person; (2) future: store IIN on user profile (out of scope) |
| **Data sources** | `persons.iin` (post-R1a), `employee_identities` (IIN), canonical roster IIN |
| **Confidence** | **High** only if IIN available on **both sides** with single employee per person |
| **Collision risks** | **High** if matching user→person by name first then IIN verify — same as FIO ambiguity; **Critical** if two users claim same IIN proxy field |
| **Recommendation** | Use IIN as **verification gate** after assignment-bridge or login match, not standalone primary matcher |
| **Pilot estimate** | **0 auto-link** without upstream person/user match; contributes to review queue when combined with B/E |

---

### 4.3. Strategy C — Login match

| | |
|--|--|
| **Rule** | `users.login` equals canonical/login identifier OR pattern `*_{employee_id}` (ADR §2.2 #4) |
| **Feasible paths** | (1) Regex `^(.+)_([0-9]+)$` → candidate `employee_id`; (2) Exact login match to HR import login if materialized |
| **Confidence** | **Medium** for pattern; **Low–Medium** for exact login without HR source |
| **Collision risks** | **Medium** — false parse (`user_123_extra`); **High** — login reused across employees; numeric suffix ≠ `employee_id` |
| **ADR policy** | Pattern match → **review queue only** (no auto-apply) |
| **Pilot estimate** | **Review required:** legacy `login_{id}` cohort (ADR-044 R2 expected note); count via Appendix A.3 |

---

### 4.4. Strategy D — Email match

| | |
|--|--|
| **Rule** | Match user email to employee/person contact |
| **Schema reality** | **`users` has no `email` column.** Proxies: `google_login` (sparse), directory contacts (separate contour, person/employee linkage varies) |
| **Confidence** | **Low** without normalized email registry on both sides |
| **Collision risks** | **High** — shared mailboxes, ex-employee addresses, `google_login` ≠ work email |
| **Recommendation** | **Defer** in R2 v1 unless HR canonical exports work email and coverage audit passes (>90% on active users). Optional P6 in R2.1 dry-run report only |
| **Pilot estimate** | **Impossible / deferred** for v1 auto-link |

---

### 4.5. Strategy E — Normalized FIO match

| | |
|--|--|
| **Rule** | `normalize(users.full_name) = normalize(employees.full_name)` with uniqueness guards |
| **ADR mapping** | §2.2 priority #3 — person-linked employee + **unique** user with same normalized name |
| **Confidence** | **Medium** |
| **Collision risks** | **High** — homonyms, maiden names, transliteration (`ё`/`е`), partial names; **Critical** if two employees same name in org |
| **Required guards** | Restrict to single active employee per person; single unmatched user candidate; optional `unit_id` agreement |
| **ADR policy** | **Review queue only** |
| **Pilot estimate** | **Review required:** largest bucket; **Ambiguous:** all cases with >1 employee or >1 user candidate |

---

### 4.6. ADR §2.2 priority #2 — Assignment bridge (recommended auto-link)

Not in user A–E list but **ratified high-confidence** path:

| | |
|--|--|
| **Rule** | `employee_assignment_links` + exactly one active operational employee for person on assignment |
| **Confidence** | **High → auto** |
| **Collision risks** | **Low** if single employee; **Medium** if assignment links stale or multiple active links |
| **Implementation** | Join user → `person_assignments` / enrollment context OR user `unit_id` + assignment ownership rules (needs dry-run proof on pilot data) |

**Merged priority for R2 v1 execute:**

| Tier | Strategy | Action |
|------|----------|--------|
| 0 | A — existing FK | Validate only |
| 1 | Assignment bridge (§2.2 #2) | **Auto-link** |
| 2 | C — login `_*_{employee_id}` pattern | Review queue |
| 3 | E — normalized FIO + unique guards | Review queue |
| 4 | B — IIN verify after candidate | Confirm in review UI |
| 5 | D — email | Defer / report-only |
| — | Ambiguous | **No link** |

---

## 5. Reconciliation report (estimated counts)

Estimates for **pilot DB (~273 users, all unlinked)**. Recompute with Appendix A before production execute.

| Category | Definition | Pilot estimate | Notes |
|----------|------------|----------------|-------|
| **Auto-link safe** | Tier 0–1: valid existing FK + high-confidence assignment bridge with single employee | **0–30** | Upper bound if enrollment created assignment links without user FK; **requires dry-run** |
| **Review required** | Tier 2–3: login pattern or unique FIO match | **80–180** | Largest expected bucket for legacy accounts |
| **Ambiguous** | Multiple employees or multiple users for same match key | **30–80** | Homonyms, shared units, incomplete HR data |
| **Impossible** | No employee, terminated-only employee, orphan user, deferred email | **remainder** | Includes service accounts without HR employee |

**Duplicate visibility assignments (separate concern):** After R2, check for multiple active users targeting same employee (blocked by `uq_users_employee_id`) and multiple assignment rows implying same user intent (journal audit).

### 5.1. R2.1 dry-run output contract

Dry-run API / CLI (R2.2+) must return a **read-only classification** per unlinked active user candidate. No writes in R2.1.

**Top-level response shape (proposed):**

```json
{
  "phase": "R2",
  "dry_run": true,
  "generated_at": "2026-06-21T12:00:00Z",
  "summary": {
    "AUTO_LINK_SAFE": 0,
    "REVIEW_REQUIRED": 45,
    "AMBIGUOUS": 0,
    "IMPOSSIBLE": 267,
    "EXCLUDED_SERVICE_ACCOUNT": 14
  },
  "candidates": []
}
```

**Per-candidate item (required fields):**

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | int | Source user |
| `login` | string \| null | Auth login |
| `user_display_name` | string | `users.full_name` |
| `normalized_user_name` | string \| null | Lowercase, collapsed whitespace FIO |
| `proposed_employee_id` | int \| null | Target employee when resolvable |
| `employee_fio` | string \| null | `employees.full_name` for proposed target |
| `match_strategy` | enum | See strategies below |
| `confidence` | enum | `certain` \| `high` \| `medium` \| `low` |
| `outcome` | enum | Classification bucket (below) |
| `reason_codes` | string[] | Machine-readable explainers |
| `blockers` | string[] | Hard stops preventing link |
| `requires_manual_confirmation` | boolean | `true` for all R2.1 review paths |

**Outcome buckets:**

| Outcome | Meaning |
|---------|---------|
| `AUTO_LINK_SAFE` | Deterministic bridge approved for batch execute |
| `REVIEW_REQUIRED` | Medium-confidence match — HR queue only |
| `AMBIGUOUS` | Multiple users and/or employees for same key |
| `IMPOSSIBLE` | No valid target (missing employee, inactive-only, parse miss) |
| `EXCLUDED_SERVICE_ACCOUNT` | Admin/system/service account — never link automatically |

**`match_strategy` values (R2.1):**

| Strategy | Typical outcome | Notes |
|----------|-----------------|-------|
| `EXISTING_FK` | `AUTO_LINK_SAFE` if valid target | Validate orphan/inactive gates |
| `ASSIGNMENT_BRIDGE` | `AUTO_LINK_SAFE` when implemented | Requires stronger deterministic bridge than login/FIO |
| `LOGIN_PATTERN` | `REVIEW_REQUIRED` | Suffix `_*_{employee_id}` |
| `FIO_UNIQUE_1_1` | `REVIEW_REQUIRED` | Single user ↔ single employee normalized name |
| `FIO_COLLISION` | `AMBIGUOUS` | >1 user or >1 employee for normalized name |
| `SERVICE_EXCLUSION` | `EXCLUDED_SERVICE_ACCOUNT` | role_id=2, admin/service login heuristics |
| `MISSING_EMPLOYEE` | `IMPOSSIBLE` | Login suffix parses but employee row absent |
| `INACTIVE_EMPLOYEE` | `IMPOSSIBLE` | Target terminated / not in active cohort |
| `NONE` | `IMPOSSIBLE` | No matcher hit |

**Example candidate:**

```json
{
  "user_id": 28,
  "login": "amb_surg_head_28",
  "user_display_name": "Акильтаева Бакыт Сагитовна",
  "normalized_user_name": "акильтаева бакыт сагитовна",
  "proposed_employee_id": 28,
  "employee_fio": "Акильтаева Бакыт Сагитовна",
  "match_strategy": "LOGIN_PATTERN",
  "confidence": "medium",
  "outcome": "REVIEW_REQUIRED",
  "reason_codes": ["LOGIN_SUFFIX_MATCHES_EMPLOYEE_ID"],
  "blockers": [],
  "requires_manual_confirmation": true
}
```

### 5.2. R2.1 linkage policy (validation phase)

**Policy decision (2026-06-21):** `AUTO_LINK_SAFE` **must remain empty** until a stronger deterministic bridge than login/FIO is implemented and signed off (e.g. assignment-bridge with single employee, validated existing FK).

**Allowed review-only strategies:**

- Login suffix → `employees.employee_id` (`LOGIN_PATTERN`)
- Unique normalized FIO 1:1 (`FIO_UNIQUE_1_1`)

**Explicitly excluded from auto-link:**

- ADMIN / system / service users (`EXCLUDED_SERVICE_ACCOUNT`)
- Ambiguous FIO groups (`FIO_COLLISION` → `AMBIGUOUS`)
- Missing employee targets (`MISSING_EMPLOYEE` → `IMPOSSIBLE`)
- Inactive / terminated employees (`INACTIVE_EMPLOYEE` → `IMPOSSIBLE`)
- Multiple active users on one employee (`V3b` — blocked by `uq_users_employee_id`)
- One user matching multiple employees (`AMBIGUOUS`)

**Execute invariants (unchanged from §6.2):**

```text
NEVER auto-link medium confidence in R2.1
NEVER populate AUTO_LINK_SAFE from login or FIO alone
NEVER link if uq_users_employee_id would violate
NEVER link to terminated-only employee without explicit review
```

### 5.3. R2.1 verification commands

**Local (read-only):**

```bash
# Direct psql
psql "postgresql://postgres:postgres@127.0.0.1:5432/corpsite" \
  -v ON_ERROR_STOP=1 \
  -f docs/adr/ADR-044-phase-r2-validation.sql

# From repo root using .env DATABASE_URL (strip SQLAlchemy driver suffix)
python - <<'PY'
from pathlib import Path
from sqlalchemy import create_engine, text
import os, re
url = os.environ["DATABASE_URL"]
url = re.sub(r"^postgresql\+[^:]+", "postgresql", url)
sql = Path("docs/adr/ADR-044-phase-r2-validation.sql").read_text(encoding="utf-8")
engine = create_engine(url)
with engine.connect() as conn:
    for stmt in sql.split(";"):
        s = stmt.strip()
        if not s or s.startswith("--"):
            continue
        rows = conn.execute(text(s)).mappings().all()
        if rows:
            print(f"--- {len(rows)} row(s) ---")
            for r in rows[:5]:
                print(dict(r))
PY
```

**VPS (read-only session recommended):**

```bash
# SSH to VPS, then:
export DATABASE_URL='postgresql://…'   # operator-provided, read-only role preferred
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f docs/adr/ADR-044-phase-r2-validation.sql | tee /tmp/r2-validation-$(date +%F).log
```

**Expected “no writes” guarantee:**

- File contains **SELECT-only** statements (verified in R2.1 review).
- No `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `CREATE`, `ALTER`, or `DROP`.
- Safe to run against production for discovery; execute/auto-link remains a separate gated phase (R2.3+).

**Pass criteria before R2 execute:**

| Gate | SQL section | Pass |
|------|-------------|------|
| V3a orphan FK | R2.1-S9 | 0 rows in detail |
| V3b duplicate user per employee | R2.1-S8 | 0 rows in detail |
| Inactive employee targets | R2.1-S9 | 0 rows in detail |
| HR sign-off on review buckets | R2.1-S3, S4 | Counts documented |

---

## 6. R2 implementation proposal

### 6.1. Migration requirements (ADR-044 B4 — no execute in discovery phase)

| Change | Purpose |
|--------|---------|
| Extend `identity_reconciliation_runs.phase` CHECK | Allow `'R2'` (or new `user_linkage_runs` table) |
| Extend `identity_reconciliation_items` | Store `user_id`, `previous_employee_id`, `proposed_employee_id`, strategy, confidence |
| Register `USER_EMPLOYEE_LINKED` in `security_audit_log` allowed types | Audit trail per ADR §2.3 |
| Optional: `user_linkage_review_queue` | Persist medium-confidence items until HR approve/deny |

**Non-goals:** No change to `employees`, `persons`, `employee_identities` DDL for R2.

---

### 6.2. Service changes

| Service | Change |
|---------|--------|
| **New:** `user_linkage_service.py` | R2 dry-run scan; tiered matcher; execute auto-link batch; apply reviewed items |
| `identity_reconciliation_service.py` | No change to R1a paths; optional shared normalize helpers |
| `access_resolver_service.py` | **Read-only benefit** — no code change required for linkage itself |
| `enrollment_service.py` | **Optional R2.2:** post-enrollment hook to set `users.employee_id` when enrollment actor known (policy decision — ADR says enrollment apply unchanged in v1) |
| `directory_service.py` | Terminate/deactivate paths start working once linked |

**Execute invariants:**

```text
NEVER auto-link medium confidence
NEVER link if uq_users_employee_id would violate
NEVER link to terminated-only employee without explicit review
ALWAYS write audit USER_EMPLOYEE_LINKED with before/after mapping
```

---

### 6.3. API changes

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/personnel/identity/reconciliation/r2/preview` | POST | Dry-run report (counts + items) |
| `/admin/personnel/identity/reconciliation/r2/execute` | POST | Auto-link tier 0–1 only |
| `/admin/personnel/user-linkage/review-queue` | GET | Medium-confidence pending items |
| `/admin/personnel/user-linkage/review-queue/{id}/approve` | POST | Apply single reviewed link |
| `/admin/personnel/user-linkage/review-queue/{id}/reject` | POST | Dismiss candidate |
| `/admin/personnel/users/{user_id}/employee-link` | PATCH | Manual admin link (ADR §2.3) with audit |

All sysadmin-only; mirror R1a router patterns in `personnel_admin_router.py`.

---

### 6.4. UI / admin changes

| Surface | Change |
|---------|--------|
| System Admin → Personnel / Identity | R2 preview + execute panel (mirror R1a UX) |
| Review queue table | User name, candidate employee, strategy, evidence, approve/reject |
| User admin drawer | Show `employee_id`, link status, manual override |
| Identity health panel (ADR B5) | Add V3 metrics: unlinked high-confidence, orphan FKs, review queue depth |

**Non-goals:** No change to Visibility tab, enrollment wizard business rules, or Telegram bot UI.

---

### 6.5. Rollback strategy

| Level | Action |
|-------|--------|
| **L1 — per user** | `UPDATE users SET employee_id = NULL WHERE user_id = :id` using R2 journal `rollback_payload` |
| **L2 — batch** | Reverse execute run from `identity_reconciliation_items` where `status='applied'` |
| **L3 — snapshot** | `pg_restore` / CSV export taken immediately before R2 execute (same as R1a) |

**Validation after rollback:** V3a orphan count = 0; restored NULL state matches pre-R2 snapshot.

---

### 6.6. Implementation phases

| Phase | Deliverable | Risk |
|-------|-------------|------|
| **R2.0** | This discovery doc + Appendix A run on VPS | None |
| **R2.1** | Dry-run contract + `ADR-044-phase-r2-validation.sql` (read-only gates) | **Complete** (2026-06-21) |
| **R2.2** | Journal DDL migration + `USER_EMPLOYEE_LINKED` audit | Low |
| **R2.3** | Auto-link execute (high confidence only) | Medium |
| **R2.4** | Review queue API + admin UI | Medium |
| **R2.5** | Manual link PATCH + V3 validation gate | Low |
| **R3** | Post-R2 validation gate (ADR-044 §R3) | — |

**Suggested order:** R2.0 → R2.1 (VPS dry-run sign-off) → R2.2 → R2.3 → R2.4 → R2.5 → R3.

---

## 7. Telegram impact assessment

Telegram integration binds **`telegram_id → users.user_id`**, not employee. R2 completes the HR chain **downstream of user**.

### 7.1. Current chain

```text
Telegram account  →  users.telegram_id  →  users.user_id  →  users.employee_id (NULL)  →  employees  →  persons / IIN
                         ✓ implemented              ✗ R2 gap
```

### 7.2. After R2 completion

| Link | Improvement |
|------|-------------|
| **User → Employee** | `users.employee_id` populated → HR context available in auth contour |
| **Employee → Identity** | Already via `employees.person_id` + R1a IIN; R2 enables user-scoped access to same chain |
| **Employee → Telegram** | **Still indirect:** `employees` → `users.employee_id` → `users.telegram_id`. R2 enables reverse lookup for delivery targeting by employee |
| **Working contacts / directory** | Position and department populate via `u.employee_id` join |
| **EMPLOYEE-target access grants** | Access resolver `_collect_subject_ids` includes employee/person/assignment subjects |
| **Bot `/whoami`, task cards** | Can show employee name, position, unit without extra joins if API reads linked employee |
| **OPS-007 Telegram audit** | Unblocked — delivery tests can validate HR-enriched messages per linked user |

### 7.3. Remaining gaps post-R2

| Gap | Owner |
|-----|-------|
| User bound to Telegram but **no** employee link | R2 review queue / manual link |
| User linked to employee but **no** Telegram bind | Existing bind flow (`/auth/self-bind`) — orthogonal |
| R1b `match_key` alignment | C1 event person_id resolution — separate phase |
| Bot local `bindings.json` cache vs DB | OPS-007 scope |

**Conclusion:** R2 is **prerequisite** for HR-complete Telegram operational audit and EMPLOYEE-scoped authorization demos. It does **not** replace Telegram bind nor change ADR-INFRA-005 service topology.

---

## 8. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Wrong user–employee link → access leak | **Critical** | Medium confidence → review only; audit every link; partial unique index |
| Homonym FIO auto-link | **High** | Never auto-link strategy E |
| Login pattern false positive | **Medium** | Review queue; regex strictness |
| Pilot counts stale on VPS | **Medium** | Mandatory Appendix A before execute |
| R2 journal schema drift from R1a | **Low** | Extend phase CHECK in dedicated migration |
| Enrollment still skips user FK | **Medium** | Document limitation; optional future hook |
| Email strategy assumed but unavailable | **Low** | Defer strategy D; document `google_login` proxy limits |

---

## 9. Validation gates (V3 — planned)

| ID | Check | Pass |
|----|-------|------|
| V3a | Orphan `users.employee_id` (FK missing) | 0 |
| V3b | Duplicate active user per `employee_id` | 0 |
| V3c | High-confidence resolvable users still unlinked | 0 |
| V3d | Medium-confidence candidates | All in review queue, not auto-applied |

Deliverable: [`ADR-044-phase-r2-validation.sql`](./ADR-044-phase-r2-validation.sql) — **authored in R2.1** (2026-06-21).

---

## 10. Recommendation

1. **Approve R2 implementation track** per ADR-044 B4/B5 with this discovery as R2.0 baseline.
2. **Run Appendix A SQL on VPS** to replace pilot estimates with live counts.
3. **Implement R2.1 dry-run first** — no writes until HR signs off on auto-link vs review buckets.
4. **Do not enable strategy D (email)** in v1 auto/review matchers without email column and coverage audit.
5. **Keep enrollment apply unchanged** in R2 v1; manual + batch link covers legacy cohort.
6. **Schedule OPS-007** after R2.5 validation gate passes.

---

## Appendix A — Discovery SQL pack

**Canonical pack:** [`ADR-044-phase-r2-validation.sql`](./ADR-044-phase-r2-validation.sql) (R2.1 — supersedes ad-hoc snippets below for ops runs).

Legacy inline snippets (equivalent subsets) — paste manually if needed:

### A.1 Table row counts

```sql
SELECT 'users' AS table_name, COUNT(*) AS row_count FROM public.users
UNION ALL SELECT 'employees', COUNT(*) FROM public.employees
UNION ALL SELECT 'persons', COUNT(*) FROM public.persons
UNION ALL SELECT 'employee_identities', COUNT(*) FROM public.employee_identities;
```

### A.2 User ↔ employee linkage

```sql
-- Users with / without employee_id
SELECT
    'users_linkage' AS check_name,
    COUNT(*) FILTER (WHERE employee_id IS NOT NULL) AS with_employee_id,
    COUNT(*) FILTER (WHERE employee_id IS NULL) AS without_employee_id,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE is_active) AS active_total,
    COUNT(*) FILTER (WHERE is_active AND employee_id IS NOT NULL) AS active_linked,
    COUNT(*) FILTER (WHERE is_active AND employee_id IS NULL) AS active_unlinked
FROM public.users;

-- Employees with / without linked user
SELECT
    'employees_user_coverage' AS check_name,
    COUNT(*) FILTER (WHERE u.user_id IS NOT NULL) AS with_user,
    COUNT(*) FILTER (WHERE u.user_id IS NULL) AS without_user,
    COUNT(*) AS total_active_employees
FROM public.employees e
LEFT JOIN public.users u ON u.employee_id = e.employee_id AND u.is_active
WHERE e.operational_status IN ('draft', 'active', 'suspended');

-- Orphan employee_id on users (V3a precursor)
SELECT
    'orphan_users_employee_id' AS check_name,
    u.user_id,
    u.employee_id
FROM public.users u
LEFT JOIN public.employees e ON e.employee_id = u.employee_id
WHERE u.employee_id IS NOT NULL AND e.employee_id IS NULL;
```

### A.3 Login pattern candidates (review bucket precursor)

```sql
SELECT
    'login_pattern_candidates' AS check_name,
    u.user_id,
    u.login,
    u.full_name,
    (regexp_match(u.login, '^(.+)_([0-9]+)$'))[2]::bigint AS parsed_employee_id
FROM public.users u
WHERE u.employee_id IS NULL
  AND u.is_active
  AND u.login ~ '^.+_[0-9]+$'
  AND EXISTS (
      SELECT 1 FROM public.employees e
      WHERE e.employee_id = (regexp_match(u.login, '^(.+)_([0-9]+)$'))[2]::bigint
  );
```

### A.4 Normalized FIO ambiguous matches

```sql
WITH norm AS (
    SELECT
        u.user_id,
        lower(regexp_replace(trim(u.full_name), '\s+', ' ', 'g')) AS nname
    FROM public.users u
    WHERE u.employee_id IS NULL AND u.is_active
),
emp_norm AS (
    SELECT
        e.employee_id,
        lower(regexp_replace(trim(e.full_name), '\s+', ' ', 'g')) AS nname
    FROM public.employees e
    WHERE e.operational_status IN ('draft', 'active', 'suspended')
)
SELECT
    'fio_ambiguous' AS check_name,
    n.nname,
    COUNT(DISTINCT n.user_id) AS user_count,
    COUNT(DISTINCT en.employee_id) AS employee_count
FROM norm n
JOIN emp_norm en ON en.nname = n.nname
GROUP BY n.nname
HAVING COUNT(DISTINCT n.user_id) > 1 OR COUNT(DISTINCT en.employee_id) > 1
ORDER BY user_count DESC, employee_count DESC
LIMIT 50;
```

### A.5 Telegram bind without employee link

```sql
SELECT
    'telegram_without_employee' AS check_name,
    COUNT(*) AS cnt
FROM public.users
WHERE telegram_id IS NOT NULL
  AND employee_id IS NULL
  AND is_active;
```

### A.6 R1a readiness context

```sql
SELECT
    'persons_iin_active' AS check_name,
    COUNT(*) FILTER (WHERE iin IS NOT NULL) AS with_iin,
    COUNT(*) AS total
FROM public.persons
WHERE person_status IN ('active', 'inactive');

SELECT
    'employee_identities_iin_active' AS check_name,
    COUNT(*) AS active_iin_rows
FROM public.employee_identities
WHERE identity_type = 'IIN' AND valid_to IS NULL;
```

---

## Appendix B — Glossary

| Term | Meaning |
|------|---------|
| Auto-link safe | High-confidence match eligible for batch execute |
| Review required | Medium-confidence — HR must approve in queue |
| Ambiguous | Multiple valid targets — no link |
| Impossible | No valid employee target |
| Identity chain | Canonical HR → person → employee → user |
