# Architecture Assessment — Platform User & Identity vs Position Cabinet Architecture

## Document metadata

| Field | Value |
|-------|-------|
| Status | **Draft — Architecture Review** |
| Date | 2026-07-03 |
| Slug | `platform-user-identity` |
| Program | [ARCH-001-assessment-program.md](./ARCH-001-assessment-program.md) (queue #4) |
| Baseline | [ARCH-001 v0.5 — Position Cabinet Architecture](./ARCH-001-position-permission-model.md) |
| Prerequisite assessments | [positions-org-structure](./ARCH-001-positions-org-structure-assessment.md), [personnel-employment](./ARCH-001-personnel-employment-assessment.md), [access-rbac](./ARCH-001-access-rbac-assessment.md), [tasks](./ARCH-001-task-subsystem-assessment.md) |
| Scope | Assessment only — no code, schema, API, or baseline changes |

---

## 1. Executive Summary

Corpsite has a **clear technical identity layer** (`public.users`) with password-based authentication, JWT transport (auth-only claims), lockout policy, and Telegram binding on the Platform User row. **Authentication is largely separated from authorization** at the JWT boundary. However, the **same `users` row carries substantial organizational and permission semantics** — `role_id`, `unit_id`, `employee_id`, duplicated `full_name`, and enriched `/auth/me` fields — that ARCH-001 assigns to Person, Employment, and Position Cabinet.

**Verdict:** **ARCH-001 is sufficient** for the identity layer. **No additional architectural entity is required.** Platform User **can and must** remain a purely technical identity in the target model; the gap is **field responsibility and linkage**, not missing identity concepts.

**Can Platform User remain auth-only?** **Yes, architecturally** — ARCH-001 §3.7, §8, OPS-028, and ADR-048 already define this. **Not yet in runtime:** user create still requires `role_id`; `/auth/me` exposes operational context; termination deactivates the User account as a side effect of employee termination; Person is reached only indirectly (`users.employee_id → employees.person_id`, often NULL).

**Recommendation:** preserve Platform User as the **stable authentication anchor** (login, password, account status, Telegram delivery endpoint, audit `actor_user_id`); migrate **all operational meaning** to Person → Employment → Cabinet Access Resolver (ADR-051); decouple account lifecycle from Employment lifecycle where business policy allows rehire with same login.

---

## 2. AS-IS

### 2.1. Scope

| In scope | Out of scope (covered elsewhere) |
|----------|----------------------------------|
| `public.users` — auth and linkage columns | Permission enforcement detail ([access-rbac](./ARCH-001-access-rbac-assessment.md)) |
| Login, password, JWT, `token_version`, lockout | Task ownership ([tasks](./ARCH-001-task-subsystem-assessment.md)) |
| `users.employee_id` bridge (ADR-044 R2) | Position / Cabinet schema (assessment #1) |
| Person resolution path (indirect) | Employment lifecycle detail (assessment #2) |
| User create / role patch / terminate side effects | HR Import pipeline |
| Telegram bind (`tg_bind`, `users.telegram_id`) | |
| `/auth/me`, `get_current_user` | |
| Security audit (`security_audit_log`, `actor_user_id`) | |
| OPS-028 login policy (proposed) | |
| Legacy `X-User-Id`, `google_login` | |

### 2.2. Platform User data model (identity-relevant)

**Table `public.users`** (baseline + ADR-042 B2.1 + ADR-044 `employee_id`):

| Column | Identity / auth role | Business coupling |
|--------|---------------------|-------------------|
| `user_id` | PK; JWT `sub`; audit actor | None (technical) |
| `login` | Authentication identifier | Should be person-stable (OPS-028); pilot legacy role-based logins exist |
| `password_hash` | Credential storage (PBKDF2) | None |
| `google_login` | Legacy alias; set equal to `login` on create | None (legacy) |
| `is_active` | Account enabled flag | **Coupled:** terminated via `terminate_employee` |
| `token_version` | Session invalidation (optional enforcement) | None |
| `locked_at`, `locked_until`, `locked_reason`, `failed_login_count` | Auth policy (ADR-042 B5) | None |
| `must_change_password` | Auth policy gate | None |
| `last_login_at` | Auth telemetry | None |
| `telegram_id`, `telegram_username`, `telegram_bound_at` | Delivery channel binding | Bound to User, not Person directly |
| `employee_id` | **Bridge** to operational shell (0..1 unique) | **Not** Person FK; employment proxy |
| `role_id` | **Required on create** | **Permission / ops center** (anti-pattern) |
| `unit_id` | Org scope for directory RBAC | **Organizational** (anti-pattern on User) |
| `full_name` | Display; copied from employee on create | Duplicates Person/Employee identity |

**Not present:** `users.person_id` FK; refresh token table; server-side session store; OAuth/SSO identity provider linkage (beyond legacy `google_login` column name).

### 2.3. Identity chain (as-is)

```text
Platform User (users)
    │
    ├── employee_id ──► Employee (operational shell)
    │                       │
    │                       └── person_id ──► Person (optional / often NULL)
    │                                              │
    │                                              └── person_assignments (Employment)
    │
    ├── role_id ──► public.roles (Platform Role — permission stand-in)
    │
    └── unit_id ──► org_units (dept scope on User row)
```

**Person is not a first-class join from User.** Resolution path:

```text
user_id → users.employee_id → employees.person_id → persons
```

When `employee_id` or `person_id` is NULL, **Person is unreachable** from Platform User despite authentication succeeding.

### 2.4. Authentication lifecycle

| Stage | Implementation | Notes |
|-------|----------------|-------|
| **Login** | `POST /auth/login` — verify `login` + `password_hash` | Records `LOGIN_SUCCESS` / `LOGIN_FAILED`; lockout on threshold |
| **JWT issuance** | `create_access_token(user_id, token_version?)` | Claims: `sub`, `iat`, `exp`, optional `token_version` |
| **JWT validation** | `decode_and_verify_token` on each request | Signature + expiry |
| **Account gates** | `is_active`, `is_user_locked`, `validate_token_version_claim`, `must_change_password` | Applied in `get_current_user` |
| **Logout** | Client-side JWT discard | No server session; `LOGOUT` event type exists but no dedicated endpoint assessed |
| **Password change (self)** | `POST /auth/password-change` | **501 Not Implemented** |
| **Password reset (admin)** | `admin_password_reset_service` | **Design stub only** — `NotImplementedError` |
| **Session invalidation** | Increment `token_version` (admin unlock ops); env-gated claim check | No refresh token rotation |

**Refresh token:** **not implemented**. Stateless JWT until expiry or `token_version` bump.

### 2.5. User lifecycle (platform)

| Event | Behaviour | Identity impact |
|-------|-----------|-----------------|
| **Create** | `POST /directory/users` — requires `employee_id`, `role_id`, `login`, `password`; copies employee `full_name`; default `unit_id` from employee | 1:1 User↔Employee enforced; Person not validated |
| **Role change** | `PATCH /users/{id}/role` — privileged; audit `ACCESS_CHANGED` | Mutates ops permission center on User |
| **Link / unlink employee** | ADR-044 R2.4/R2.5 operations journal | Mutates `users.employee_id` |
| **Lock / unlock** | Admin API — `lock_user`, `unlock_user`; brute-force auto-lock | Auth-only |
| **Deactivate account** | `users.is_active = false` | Blocks login |
| **Terminate employee** | `terminate_employee` → sets employee inactive **and** `users.is_active = false` where `employee_id` matches | **Conflates** employment end with account disable |
| **Rehire** | New employee episode; same Person may get new Employee; User may remain inactive unless manually reactivated | Login **immutable** (OPS-028 policy); link may need update |
| **Telegram bind** | One-time code → `users.telegram_id` | Persists across employment changes |

### 2.6. Person linkage & enrollment

| Path | Sets `users.employee_id`? | Sets Person? |
|------|---------------------------|--------------|
| HR enrollment apply | No (manual user create follows) | Creates/links Person via assignment |
| `POST /directory/users` | Yes (required) | Indirect only if employee has `person_id` |
| ADR-044 linkage execute | Yes (R2.4+) | Indirect |
| Pilot seed | Yes | Often 1:1 employee = role code |

Enrollment **does not** auto-provision Platform User (ADR-042 U-1: sysadmin creates manually).

### 2.7. `/auth/me` (identity + authorization mix)

`GET /auth/me` returns authenticated **Platform User** row enriched with:

| Field category | Examples | Layer |
|----------------|----------|-------|
| **Auth / identity** | `user_id`, `login`, `telegram_bound`, lock/must-change flags | ✓ Technical |
| **Transitional ops** | `role_id`, `role_name_ru`, `unit_id` | Authorization |
| **Employee proxy** | `position_id`, `position_name` from employee snapshot | Organizational (single) |
| **Authorization flags** | `is_privileged`, `has_sysadmin_api`, `can_view_all_tasks`, `personnel_visibility` | Authorization |

**Does not expose:** `person_id`, `employee_id`, accessible cabinets, employment list, active cabinet context.

### 2.8. Telegram identity

| Aspect | AS-IS |
|--------|-------|
| Storage | `users.telegram_id` (TEXT), `telegram_username` |
| Bind flow | User requests code (`/me/tg-bind-code`) → bot consumes (`/tg/bind/consume`) |
| Bot API auth | Internal token + `X-Telegram-User-Id` → resolve `user_id` |
| Person link | **None** — Telegram → Platform User only |
| Service accounts | Blocked from bot by login/name pattern |

Telegram is correctly a **transport identity on Platform User**; bot then loads full user-centric RBAC context.

### 2.9. Audit identity

**Primary audit actor key:** `actor_user_id` → `users.user_id` in `security_audit_log`.

| Event family | Actor | Target | Person? |
|--------------|-------|--------|---------|
| Login success/fail | `user_id` | `user_id` | No |
| Access / role change | admin `user_id` | target `user_id` | Optional `target_employee_id` |
| Enrollment | admin `user_id` | queue item | No |
| Task events | `actor_user_id` | task / recipients | Separate from security audit |
| Future ARCH-001 audit | — | — | Should add `person_id` + `cabinet_id` for ops actions |

Using Platform User as **audit actor pointer** is **architecturally correct** (who logged in). **Operational attribution** (who acted for which Cabinet) requires additional Person + cabinet context — not yet standard.

### 2.10. Legacy / compatibility identity paths

| Mechanism | Status |
|-----------|--------|
| `X-User-Id` header | Legacy dev fallback when JWT missing (`ENABLE_LEGACY_X_USER_ID`) |
| Internal API token + `X-User-Id` | Bot / automation impersonation |
| Pilot logins (`qm_head@corp.local`) | Role-coded; grandfathered (OPS-028) |
| `google_login` column | Duplicates `login` on create; not separate IdP flow |

### 2.11. Focus area answers

| Focus area | AS-IS |
|------------|-------|
| **Login model** | Local `users.login` + password; OPS-028 target `{surname}.{initials}`; UI suggestion module exists |
| **Password ownership** | ✓ `users.password_hash`; HR events do not reset |
| **Authentication lifecycle** | JWT stateless; lockout + optional token_version |
| **Platform User lifecycle** | Long-lived; immutable login policy; can outlive single Employee |
| **Person linkage** | Indirect via Employee; incomplete |
| **Multiple active employments** | Not visible on User; single employee link |
| **Multiple cabinet access** | Not represented |
| **Acting duties** | No User-level overlay; role swap anti-pattern |
| **User creation** | Employee-required; role_id required; privileged operator |
| **User blocking** | `is_active`, lock fields, terminate side effect |
| **Password reset** | Stub only; self-change 501 |
| **Audit trail** | `user_id`-centric security audit |
| **Telegram identity** | On User row; correct layer |
| **API identity** | JWT Bearer → `user_id` |
| **Session invalidation** | `token_version`; no refresh token |
| **Token contents** | Auth-only (good) |
| **`/auth/me`** | Mixed auth + authorization + single position |
| **Identity during vacancy** | User account independent of position vacancy |
| **Identity after termination** | User deactivated with employee |
| **Identity after rehire** | Same login possible; manual re-link / reactivate |

---

## 3. TO-BE under ARCH-001 (baseline unchanged)

### 3.1. Platform User (technical identity only)

Per ARCH-001 §3.7, §8 and OPS-028:

| Responsibility | Platform User |
|----------------|---------------|
| `login` | ✓ Stable auth identifier (Person-associated, not role-coded) |
| `password_hash` / credential policy | ✓ |
| `is_active`, lockout, `token_version`, `must_change_password` | ✓ |
| `telegram_id` (delivery endpoint) | ✓ |
| JWT `sub` = `user_id` | ✓ |
| Audit **authentication** events | ✓ |
| `actor_user_id` in audit (who used the account) | ✓ |

| **Not** Platform User | Owner |
|-----------------------|-------|
| Permission Template | Position Cabinet |
| Org scope / dept visibility | Cabinet permissions + org policy |
| Task/report ownership | Position Cabinet |
| Employment / position | Person + Employment |
| Display FIO (authoritative) | Person |
| Operational `full_name` on user row | Deprecated or read-only mirror |

### 3.2. Person linkage (TO-BE)

```text
Platform User ──0..1──► Person
         (direct FK or enforced bridge via employment policy)
```

Minimum architectural requirement: **every operational Platform User resolves to exactly one Person** before cabinet access is granted. Employee bridge may remain as **convenience denormalization**, not identity source.

### 3.3. Post-authentication context (TO-BE)

After authentication, system resolves:

```text
Platform User → Person → active Employments (+ acting)
    → Cabinet Access Resolver (ADR-051)
    → accessible_cabinets[], effective_permissions, active_cabinet_context
```

`/auth/me` should expose **identity + cabinet access summary**, not `role_id` as primary ops context.

### 3.4. Lifecycle decoupling (TO-BE)

| Event | Platform User | Employment / Cabinet |
|-------|---------------|----------------------|
| Termination | **Policy choice:** deactivate account OR keep auth-only for rehire | Close Employment; revoke Cabinet access |
| Rehire | Reactivate **same** User + login (OPS-028) | New Employment; Cabinet access restored |
| Acting | Unchanged login | Temporary cabinet access via overlay |
| Vacancy | User unchanged | No cabinet access for vacant position |
| Role/template change | **No** `users.role_id` mutation | Cabinet Template configuration |

### 3.5. Audit (TO-BE)

| Layer | Key |
|-------|-----|
| Authentication | `actor_user_id` (Platform User) |
| Operational action | `person_id` + `cabinet_id` + `actor_user_id` |

Platform User remains the **login account** in audit; Person + Cabinet carry **organizational meaning**.

---

## 4. Ownership Analysis

| Object | AS-IS owner / carrier | TO-BE owner | Gap |
|--------|----------------------|-------------|-----|
| Login | Platform User | Platform User | ✓ (fix generator — OPS-028) |
| Password | Platform User | Platform User | ✓ |
| JWT | Transport / User id | Transport / User id | ✓ |
| Telegram binding | Platform User | Platform User | ✓ |
| Natural person identity | Person (when linked) | Person | Employee-first create |
| Employment period | `person_assignments` | Employment | User not involved |
| Org placement | Employee snapshot + User.`unit_id` | Position / Employment | `unit_id` on User |
| Permissions | User.`role_id` | Cabinet Template | Critical |
| Task context | User + role | Cabinet | Critical |
| Display name (auth UI) | User.`full_name` | Person | Duplicate |
| Account active flag | User.`is_active` | User (auth policy) | Terminate coupling |
| Audit login actor | User | User | ✓ |
| Audit ops actor | User (+ sometimes employee_id) | Person + Cabinet + User | Partial |

---

## 5. Lifecycle Analysis

| Event | AS-IS Platform User | TO-BE Platform User | AS-IS coupling risk |
|-------|--------------------|--------------------|---------------------|
| **First hire + user create** | New row; link employee; assign role | New row; link Person; **no** ops role on User | role_id required today |
| **Concurrent employments** | One employee_id max | Same User; resolver sees N cabinets | Cannot represent |
| **Acting period** | No change; ops may swap role_id | Same User; acting overlay in resolver | role swap |
| **Transfer** | unit_id may change; login unchanged | login unchanged; cabinet access follows Employment | unit_id on User |
| **Termination** | `is_active=false` | Configurable: disable auth or keep dormant | **Over-closes** account |
| **Rehire** | Manual reactivate + re-link | Same login; Employment reopen | OK if login preserved |
| **Password lock** | Auth blocked | Unchanged | ✓ |
| **Admin force password change** | Planned stub | Unchanged | ✓ |
| **Telegram rebind** | User-level | User-level | ✓ |
| **Person merge** | No User impact defined | User → surviving Person | Gap |
| **Vacant position** | User unaffected | User unaffected; cabinet access empty | ✓ |

---

## 6. Access Analysis

This assessment treats **access** only where it intersects **identity** (what the authenticated subject represents).

### 6.1. What Platform User currently grants (incorrectly)

| Mechanism | Identity confusion |
|-----------|-------------------|
| `users.role_id` | User **is** the operational role |
| `users.unit_id` | User **is** dept-scoped actor |
| `/auth/me` position fields | User **is** single-position worker |
| `terminate_employee` → deactivate user | User lifecycle **is** employment lifecycle |
| User create requires `role_id` | Provisioning **is** permission assignment |
| Working contacts keyed by `user_id` | Directory identity **is** User |

### 6.2. What should grant access (TO-BE)

Only **Cabinet Access Resolver** output — derived from Person's Employments — defines operational access. Platform User answers: **is this login allowed to authenticate?**

### 6.3. Authentication vs authorization boundary (assessment)

| Check | Layer | Correct? |
|-------|-------|----------|
| Password verify | Auth | ✓ |
| JWT signature / exp | Auth | ✓ |
| `is_active`, locked, token_version | Auth | ✓ |
| `role_id`, privileges, task flags | **Authorization** | ✓ layer separation at JWT, ✗ loaded in same `/auth/me` |
| Personnel visibility | Authorization | ✓ |
| Employee → position on me | **Organizational** | ✗ on identity endpoint |

---

## 7. Gap Analysis

### 7.1. Identity-layer gaps

| ID | Gap | Severity |
|----|-----|----------|
| I1 | No `users.person_id` — Person unreachable when employee unlinked | **High** |
| I2 | `role_id` required at user create — embeds authorization in identity provisioning | **High** |
| I3 | `unit_id` on User — org structure on auth row | **Medium** |
| I4 | `/auth/me` exposes authorization + single position — not identity summary | **High** |
| I5 | Termination deactivates User — conflates auth account with employment end | **Medium** |
| I6 | `full_name` duplicated on User — identity data not anchored on Person | **Low** |
| I7 | Incomplete Person materialization breaks identity chain | **High** (personnel P2) |
| I8 | One User ↔ one Employee — blocks multi-employment identity view | **Medium** |
| I9 | Password self-service / admin reset not implemented | **Medium** (auth completeness) |
| I10 | Audit ops attribution lacks `person_id` / `cabinet_id` standard | **Medium** |
| I11 | Pilot role-based logins | **Low** (legacy grandfathered) |
| I12 | Login suggestion not server-side (OPS-028.2 pending) | **Low** |

### 7.2. Not identity gaps (handled in other assessments)

| Item | Owner assessment |
|------|------------------|
| Cabinet entity | #1 positions-org-structure |
| Employment → Cabinet resolver | #2 personnel, ADR-051 |
| Permission enforcement | #3 access-rbac |
| Task ownership | tasks |

### 7.3. ARCH-001 sufficiency

**ARCH-001 is sufficient.** Identity layer needs **boundary enforcement**, not new entities.

---

## 8. Required ADR Changes

### Required

| ADR / document | Change |
|----------------|--------|
| **ADR-048** | Mandate Person resolution for every operational User; direct or enforced indirect link; identity chain invariant |
| **ADR-042 Phase B5** | `/auth/me` contract: identity fields vs authorization fields; future `person_id`, `accessible_cabinets[]` |
| **ADR-044** | User linkage: Person-first validation on link/create; rehire re-link policy |
| **OPS-028** | Login immutability + Person-based suggestion (implementation phase) |
| **ADR-051** | Resolver invoked post-auth; Platform User not an input to permission union |

### Recommended

| ADR / document | Change |
|----------------|--------|
| **ADR-042 Phase A (U-1)** | User create: auth fields only; decouple from `role_id` when cabinet resolver exists |
| **ADR-033** | Termination: separate **account disable** policy from **employment end** |
| **ADR-013** | Document invariant: JWT must not carry role/cabinet claims |
| **ADR-047** | Audit attribution: Person + cabinet on operational events |
| **ADR-007** | Post-login identity: cabinet list from Person, not User role |

### Optional

| ADR / document | Change |
|----------------|--------|
| **ADR-042 B5** | Refresh token strategy (if introduced) — still auth-only claims |
| **ADR-022** | Telegram: optional Person display from User bridge |

---

## 9. Migration Roadmap

**No implementation in this assessment.**

### Phase 0 — Identity invariants (pre-Cabinet)

- Enforce Person on user create when `employees.person_id` present; block or queue when missing.
- Document terminate → deactivate as **explicit policy** pending decoupling decision.
- Implement OPS-028 login suggest (server-side).

### Phase 1 — Person anchor (parallel ADR-050)

- Add read-only `person_id` on `/auth/me` via employee bridge.
- Stop requiring `role_id` on user create for new deployments (feature flag).

### Phase 2 — Cabinet resolver (ADR-051)

- `/auth/me`: `accessible_cabinets[]`, remove primary reliance on `role_id` / single `position_id`.
- Authorization middleware reads resolver, not `users.role_id`.

### Phase 3 — Lifecycle decoupling

- Termination: close Employment + revoke cabinet access; User deactivate **optional** per policy.
- Rehire: reactivate User + link Employment; login unchanged.

### Phase 4 — Cleanup

- Deprecate `users.role_id`, `users.unit_id` for ops; retain for migration read-only.
- Remove duplicate `full_name` authority from User row (display from Person).

---

## 10. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Treating User deactivate as mandatory on terminate | Rehire friction, login loss | Explicit policy in ADR-033; default keep User dormant not deleted |
| Adding `person_id` to User without governance | Drift vs employee bridge | Single write path; reconciliation with ADR-044 |
| `/auth/me` breaking change | UI regressions | Phased fields; parallel legacy flags |
| Telegram bound to deactivated User | Delivery failures | Bind persists; bot checks auth + cabinet separately |
| Pilot logins imply role identity | Operator confusion | OPS-028 grandfather + UI labels |
| JWT scope creep (role claims) | Stale permissions in token | ADR-013 guardrail |
| Identity assessment deferred past RBAC migration | User row remains ops center | Queue order already mitigates — enforce in ADR-051 |

---

## 11. Identity Resolution Pipeline

### 11.1. AS-IS — complete flow

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ AUTHENTICATION (technical)                                               │
└─────────────────────────────────────────────────────────────────────────┘

Credentials (login + password)
        │
        ▼
POST /auth/login
        │  fetch_user_auth_policy_row_by_login
        │  verify_password(password, password_hash)
        │  gates: is_active, is_user_locked
        ▼
create_access_token(user_id, token_version)
        │  JWT payload: { sub, iat, exp, token_version? }
        │  NO role, NO permissions, NO org data
        ▼
Client stores Bearer token

───────────────────────────────────────────────────────────────────────────

Authenticated HTTP request
        │
        ▼
JWTBearer → decode_and_verify_token
        │  signature, exp
        ▼
get_current_user
        │
        ├─► sub → user_id
        │
        ├─► _get_user_by_id(user_id)
        │       users ⟕ roles (role_id, role_name_ru)
        │       users ⟕ employees (employee_id)
        │       employees ⟕ positions (catalog position_id, position_name)
        │       auth policy columns (must_change_password, token_version, locked_*)
        │
        ├─► validate_token_version_claim (optional env)
        ├─► require_password_not_expired_or_change_allowed
        │
        └─► _enrich_user_context  ─── AUTHORIZATION BOUNDARY CROSSED ───
                is_privileged (role_id, env allowlists)
                evaluate_admin_access
                has_personnel_admin / has_hr_governance
                enrich_user_with_personnel_visibility
                can_view_team_tasks(user_id, role_id)
        ▼
Handler receives enriched user dict

Optional parallel lookups (not universal):
        │
        ├─► access_resolver: user → employee → person → assignments → grant subjects
        ├─► Telegram bot: tg_id → users.user_id → same enrichment
        └─► Legacy: X-User-Id / internal token → user_id

┌─────────────────────────────────────────────────────────────────────────┐
│ AUDIT IDENTITY                                                           │
└─────────────────────────────────────────────────────────────────────────┘

Security events: actor_user_id (= Platform User)
Task events: actor_user_id, initiator_user_id
Enrollment: actor_user_id, enrolled_by_user_id
User linkage: actor_user_id on link/unlink operations
```

#### 11.1.1. Lookup matrix (AS-IS)

| Step | Table / object | When |
|------|----------------|------|
| Authentication | `users.login`, `users.password_hash` | Login only |
| JWT validation | JWT crypto | Every request |
| Platform User | `users` by `user_id` | Every request |
| Role lookup | `roles` via `users.role_id` | Every `/auth/me` + most handlers |
| Employee lookup | `employees` via `users.employee_id` | `/auth/me`, resolver, contacts |
| Person lookup | `persons` via `employees.person_id` | Resolver, visibility (if linked) |
| Organization lookup | `org_units` via `users.unit_id` | Directory scope, user create |
| Position (catalog) | `positions` via `employees.position_id` | `/auth/me` display |
| Employment | `person_assignments` via `person_id` | Grant subject collection only |
| Telegram identity | `users.telegram_id` | Bot bind + delivery |

**Authentication stops at:** active, unlocked User with valid JWT.  
**Everything after `_enrich_user_context` is authorization or organizational context** — currently bundled into the identity endpoint.

### 11.2. TO-BE — complete flow (ARCH-001)

```text
Credentials
        │
        ▼
Platform User authentication
        │  verify login + password_hash
        │  account policy: is_active, locked, token_version, must_change_password
        │  JWT: sub = user_id ONLY
        ▼
Authenticated session (stateless JWT)
        │
        ▼
Resolve Person
        │  users → person_id (direct or via employee bridge)
        │  invariant: operational users MUST resolve Person
        ▼
Load active Employments (+ ACTING overlays)
        │  person_assignments + ADR-036 acting
        ▼
Cabinet Access Resolver (ADR-051)
        │  Employments → org-unique Position → Position Cabinet
        │  Permission Templates → effective permission set
        │  active_cabinet_context (UI selection)
        ▼
Authorization & operational handlers
        │  decisions use Person + Cabinet context
        │  audit: (actor_user_id, person_id, cabinet_id)
        ▼
Response

Telegram / bot parallel:
        Telegram id → Platform User → (same Person → Resolver chain)
```

**Platform User does not participate** in Permission Template union or org-unique Position resolution.

---

## 12. Identity Ownership Matrix

| Object | Owner (domain) | Purpose | Lifecycle | Classification |
|--------|----------------|---------|-----------|----------------|
| **Platform User** | Platform (auth admin) | Login account, credential, Telegram endpoint | Long-lived; survives employment changes | **Architectural** (technical identity) |
| **Person** | HR / Canonical | Canonical human identity | Durable across employments | **Architectural** |
| **Employment** | HR | Period Person occupies Position | Episode-based | **Architectural** |
| **Position** | Organization | Org-unique staffing unit | HR lifecycle | **Architectural** |
| **Position Cabinet** | Organization / platform config | Operational container | = Position lifecycle | **Architectural** |
| **login** | Platform User | Authentication identifier | Immutable after create (OPS-028) | **Architectural** — **Technical only** |
| **password** | Platform User | Authentication secret | Rotates on reset/change | **Technical only** |
| **JWT** | Auth transport | Proof of authentication | Short-lived; no refresh token today | **Technical only** |
| **refresh token** | — | — | **Not implemented** | N/A |
| **authentication session** | Client-held JWT | Stateless session | Until exp or token_version bump | **Technical only** |
| **Telegram account** | Platform User (`telegram_id`) | Notification delivery | Bind/unbind on User | **Technical only** (transport) |
| **audit identity (auth)** | Platform User (`actor_user_id`) | Who authenticated | Append-only log | **Architectural** — **Technical only** |
| **audit identity (ops)** | Person + Cabinet (+ User) | Who acted for which function | Append-only | **Architectural** (to-be standard) |
| **users.role_id** | Platform User (today) | Ops permission center | Changes on role patch | **Transitional** → **Legacy** |
| **users.unit_id** | Platform User (today) | Dept RBAC scope | Changes on transfer/create | **Transitional** |
| **users.employee_id** | Platform User (today) | Bridge to Employee shell | Link/unlink (ADR-044) | **Transitional** |
| **users.full_name** | Platform User (today) | Display copy | Set on create from employee | **Legacy** duplicate |
| **google_login** | Platform User | Legacy column | = login on create | **Legacy** |
| **password_hash** | Platform User | Stored credential | Admin/user reset | **Technical only** |
| **token_version** | Platform User | Invalidate JWTs | Increment on security events | **Technical only** |
| **lockout fields** | Platform User | Brute-force protection | Auto/admin | **Technical only** |
| **X-User-Id header** | Dev compatibility | Legacy impersonation | Migration period | **Legacy** |

---

## 13. Identity Boundary Analysis

### 13.1. Mixing map (AS-IS)

| Location | Identity | Authentication | Authorization | Org structure | Ops ownership |
|----------|----------|----------------|---------------|---------------|---------------|
| `users` table | user_id, login | password_hash, lock, token_version | **role_id**, **unit_id** | **unit_id**, employee bridge | **employee_id** |
| `POST /directory/users` | creates User | sets password | **requires role_id** | sets unit_id | links employee |
| `GET /auth/me` | user_id, login | lock flags | **full RBAC enrich** | **position_id**, unit implied | **can_view_all_tasks** |
| `terminate_employee` | — | **deactivates User** | — | closes employee | — |
| `tasks.initiator_user_id` | — | — | approve rule | — | **user as initiator** (Person exception) |
| Working contacts | lists **users** | — | privileged gate | role_name, position via employee | User as contact row |
| Telegram bind | **user_id** | — | bot loads RBAC | — | — |
| JWT | user_id | ✓ | ✗ | ✗ | ✗ |

### 13.2. Platform User carrying business meaning (anti-patterns)

| Anti-pattern | Evidence | Should belong to |
|--------------|----------|------------------|
| **Permission owner** | `users.role_id` required; `PATCH .../role` | Cabinet Permission Template via Employment |
| **Organizational scope owner** | `users.unit_id` in directory RBAC | Employment / Cabinet org context |
| **Single-position identity** | `/auth/me` `position_id` from employee snapshot | Person + active Employments (N positions) |
| **Employee substitute** | User create requires `employee_id`; 1:1 unique | Person primary; Employee optional shell |
| **Person substitute** | `users.full_name`; login from employee FIO only | Person canonical FIO |
| **Employment substitute** | Terminate deactivates User with employee | Employment close ≠ always account disable |
| **Task owner** (implicit) | `executor_role_id = users.role_id` mine scope | Executor Position Cabinet |
| **Report owner** (implicit) | Report actions keyed to user role | Person in cabinet context |
| **Document owner** (indirect) | User → employee → employee_documents | Person / Cabinet split (assessment #11) |
| **Cabinet owner** | No cabinet — User+role acts as virtual cabinet | Position Cabinet |
| **Operational "who am I"** | `/auth/me` role_name_ru | Person + active cabinet context label |

### 13.3. JWT and `/auth/me` specific findings

| Check | Result |
|-------|--------|
| JWT contains organizational meaning | **No** ✓ |
| JWT contains permission decisions | **No** ✓ |
| JWT assumes single position or role | **No** ✓ |
| `/auth/me` exposes transitional concepts | **Yes** — `role_id`, `role_name_ru`, `is_privileged`, `can_view_all_tasks`, single `position_id`, `personnel_visibility` |
| `/auth/me` exposes architectural identity | **Partial** — `user_id`, `login`, telegram; **missing** `person_id`, employments, cabinets |

### 13.4. What must remain on Platform User (permanent)

- Authentication credentials and account status
- Telegram delivery binding (until separate delivery registry exists)
- JWT subject identifier
- Security audit actor for login/account events
- Long-lived login string (OPS-028 immutability)

### 13.5. What must migrate off Platform User

| Field / behaviour | Migrate to |
|-------------------|------------|
| `role_id` | Cabinet Permission Template (via resolver) |
| `unit_id` (ops scope) | Employment / Cabinet org scope |
| `position_id` display on `/auth/me` | Person → active Employments → Positions |
| Permission flags on `/auth/me` | Cabinet effective permissions |
| Termination → auto deactivate | Policy: Employment access revoke; optional account disable |
| User create `role_id` requirement | Post-auth cabinet access only |
| Operational contact keyed as User | Person / Employee / Cabinet directory models |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 1.0 | Initial platform-user-identity assessment (queue #4) |
