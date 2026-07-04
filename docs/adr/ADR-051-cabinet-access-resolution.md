# ADR-051 — Cabinet Access Resolution

## Status

**Accepted** — 2026-07-04

Operational access-resolution contract derived from [ARCH-001 v0.5](../architecture/ARCH-001-position-permission-model.md), [Architecture Governance](../architecture/ARCHITECTURE_GOVERNANCE.md), [ARCH-001 Foundation Summary](../architecture/ARCH-001-foundation-summary.md), and [ADR-050](./ADR-050-organization-position-cabinet-model.md) (**Accepted**). This ADR **defines how effective permissions are calculated** under Position Cabinet Architecture. It **does not** amend ARCH-001, **does not** redefine Position or Cabinet lifecycle (ADR-050), and **does not** specify authentication, JWT, schema, or API implementation.

| Field | Value |
|-------|-------|
| Depends on | [ADR-050](./ADR-050-organization-position-cabinet-model.md) (**Accepted**) — org-unique Position, Position Cabinet, Permission Template location |
| Enables | RBAC enforcement cutover, `/auth/me` cabinet contract (ADR-042 B5), task cabinet routing (ADR-049), visibility migration (ADR-042 E1) |
| Related | [ADR-036](./ADR-036-hr-events-unified-model.md) (ACTING overlay), [ADR-042 Phase A/B](./ADR-042-phase-a-personnel-access-enrollment-architecture.md), [ADR-023](./ADR-023-rbac-v2-lean-scope-and-approvals.md), [OPS-028](../ops/OPS-028-platform-user-login-policy.md), [access-rbac assessment](../architecture/ARCH-001-access-rbac-assessment.md) |

### Explicitly out of scope

| Topic | Owner |
|-------|-------|
| Position model, org-unique Position identity, Cabinet 1:1 lifecycle | **ADR-050** |
| Authentication, credential policy, JWT transport | ADR-042 B5, ADR-013, OPS-028 |
| SQL schema, table names, indexes, migrations | Implementation program |
| API endpoints, request/response shapes, session storage | ADR-042 B5 and consumer ADRs |
| Task/report/notification rebinding | ADR-049 and consumer ADRs |
| Process policy at vacancy (regular tasks, escalations) | Business Policy (ARCH-001 §4.7.2) |
| Platform Role as architectural entity | **Not introduced** — transitional as-is only |

---

## 1. Problem Statement

Corpsite as-is resolves authorization from **Platform User** attributes — principally `users.role_id`, `users.unit_id`, and partial `access_grants` — not from **Employment → Position Cabinet → Permission Template** as ARCH-001 defines.

This produces systemic failures against the accepted baseline:

| Gap | As-is effect |
|-----|--------------|
| **User-centric permission center** | Operational rights live on login, not on occupied Position |
| **Single role per User** | Совместительство and и.о. cannot be represented without mutating `users.role_id` |
| **No Cabinet entity** | Permission Template has no stable operational container |
| **No Employment-driven access** | `person_assignments` feeds grant subjects but does not open Cabinet access |
| **Acting anti-pattern** | Temporary duties via role swap — loses primary cabinet context |
| **Vacancy conflation** | Role/task binding persists without occupant; no Cabinet-centric vacancy semantics |

Foundation assessments ([access-rbac](../architecture/ARCH-001-access-rbac-assessment.md), [personnel-employment](../architecture/ARCH-001-personnel-employment-assessment.md), [foundation summary](../architecture/ARCH-001-foundation-summary.md)) confirm: the gap is **resolver and enforcement alignment**, not missing baseline concepts. **ADR-050** must establish Position and Cabinet identities first; **ADR-051** defines the **Cabinet Access Resolver** contract that replaces user-centric authorization with **Cabinet-centric authorization** while preserving **Platform User** as the authentication identity.

---

## 2. Context

### 2.1. Authoritative inputs

| Document | Relevant conclusion |
|----------|-------------------|
| [ARCHITECTURE_GOVERNANCE](../architecture/ARCHITECTURE_GOVERNANCE.md) | Permissions follow Employment, not User; Cabinet = digital representation of Position |
| [ARCH-001](../architecture/ARCH-001-position-permission-model.md) | §3.2, §3.6, §7, §9, §10 — Employment opens access; effective permissions = union of accessible Cabinets; acting adds second Cabinet |
| [ARCH-001-foundation-summary](../architecture/ARCH-001-foundation-summary.md) | Confirmed chain: User → Person → Employments → Cabinet → Template → Effective Permissions; ADR-051 is critical path gate #2 |
| [ADR-050](./ADR-050-organization-position-cabinet-model.md) | Permission Template **inside** Cabinet; Employment grants access **for period**; access enforcement deferred to this ADR |
| [access-rbac assessment](../architecture/ARCH-001-access-rbac-assessment.md) | TO-BE pipeline §11.2; union semantics; `users.role_id` demoted; JWT auth-only confirmed |

### 2.2. Architectural boundary

This ADR sits **between** HR truth and operational enforcement:

```text
┌─────────────────────────────────────────────────────────────────┐
│  HR truth (ADR-050, ADR-042, ADR-036)                           │
│  Person · Employment · Position · ACTING overlay                │
└────────────────────────────┬────────────────────────────────────┘
                             │ inputs
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  ADR-051 — Cabinet Access Resolver (this ADR)                   │
│  Accessible Cabinets · Effective Permission Set · Runtime ctx   │
└────────────────────────────┬────────────────────────────────────┘
                             │ outputs
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Consumer enforcement (ADR-023, ADR-042 B5/E1, ADR-049, …)      │
│  Route guards · task routing · visibility · UI session context  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3. Single-tenant organization

Corpsite operates as a **single organization** tenant. **Organization boundary** in this ADR means: all Positions, Cabinets, Employments, and Permission Templates belong to the same implicit organization. Cross-organization access is **out of scope**. Org structure scope (org unit subtree, department groups) is derived from **Position / Cabinet placement** and **Permissions**, not from `users.unit_id` as a standalone carrier in the target model.

### 2.4. Terminology (unchanged from baseline)

| Term | Meaning |
|------|---------|
| **Занятие должности / Employment** | Time-bounded fact that Person occupies org-unique Position (`person_assignments` in ADR-042) |
| **Acting duty / и.о.** | Temporary overlay (ADR-036 `ACTING_ASSIGNMENT`) granting access to **another** Position's Cabinet without closing primary Employment |
| **Permission Template** | Named permission bundle **inside** Position Cabinet (ADR-050) |
| **Effective Permission Set** | Deterministic union of Permissions from all accessible Cabinets at evaluation time T |
| **Cabinet Access Resolver** | Architectural component that computes accessible Cabinets and effective permissions from Person + active access periods |

**Platform Role** and **user roles** are **not** architectural entities in the target model. As-is `public.roles` / `users.role_id` are **transitional** stand-ins for Permission Template codes assigned to User — to be demoted during migration (foundation summary §4).

---

## 3. Decision

Adopt a **Cabinet Access Resolver** as the **sole baseline source** of operational authorization, with the following contracts:

1. **Authentication** remains **Platform User** responsibility — login establishes identity only.
2. **Authorization** derives exclusively from **Person → active Employments (+ acting overlays) → accessible Position Cabinets → Permission Templates**.
3. **Effective Permission Set** is the **set union** of Permissions from all accessible Cabinets at time T, unless a specific permission evaluation explicitly requires **active Cabinet context** (see §7).
4. **Acting duties add** Cabinets to the accessible set; they **never replace** primary Employment access.
5. **Vacancy** grants **no Person access** to the vacant Position's Cabinet via primary Employment; acting overlay may still grant temporary access per ADR-036.
6. **Deterministic calculation** — same inputs at time T always yield the same accessible Cabinet set and effective permissions.
7. **JWT never contains effective permissions** — authorization is resolved per request from authoritative stores after authentication.
8. **Exception overlays** (`access_grants` and similar transitional mechanisms) may **extend** the effective set only where explicitly documented as policy exceptions — they do **not** replace Cabinet baseline (ARCH-001 §15.0).

No **Slot** entity. No permission assignment on **Platform User** or **Person** directly in the target model.

---

## 4. Cabinet Access Resolver

### 4.1. Role

The **Cabinet Access Resolver** is the architectural component responsible for translating **HR access facts** into **operational authorization inputs**.

It answers:

| Question | Output |
|----------|--------|
| Which Position Cabinets can this Person access **right now**? | **Accessible Cabinet set** |
| What Permissions does this Person effectively hold? | **Effective Permission Set** |
| Which Cabinet is the Person **acting in** for scoped operations? | **Active Cabinet context** (runtime) |
| Does this Person hold a specific Permission for a decision? | **Authorization decision** input |

It does **not** authenticate credentials, mutate Employments, or manage Cabinet lifecycle.

### 4.2. Inputs (conceptual)

| Input | Source | Required |
|-------|--------|----------|
| **Platform User id** | Authentication layer | Yes — entry point for request pipeline |
| **Person id** | User → Person linkage (ADR-044, ADR-048) | Yes — authorization subject |
| **Evaluation timestamp T** | Request time or explicit policy time | Yes — deterministic period checks |
| **Active Employments** | `person_assignments` filtered by lifecycle, active flag, `[start, end]` at T | Yes |
| **Acting overlays** | ADR-036 acting records filtered by period at T | When present |
| **Position → Cabinet map** | ADR-050 1:1 pairing | Yes |
| **Permission Templates** | Configuration inside each accessible Cabinet | Yes |
| **Position lifecycle state** | ADR-050 — active / vacant / liquidated | Yes — liquidated Cabinets excluded |
| **Optional exception grants** | Transitional `access_grants` overlay | Policy-defined exceptions only |
| **Active Cabinet selection** | Runtime session context | For scoped evaluations |

### 4.3. Outputs (conceptual)

| Output | Description |
|--------|-------------|
| **Accessible Cabinets[]** | Ordered list of Position Cabinet ids Person may access at T, each with access **provenance** (primary Employment, secondary Employment, acting) |
| **Effective Permission Set** | Set of Permission codes (union across accessible Cabinets, plus documented exceptions) |
| **Default Cabinet** | Cabinet selected when no explicit active context — see §7.3 |
| **Active Cabinet context** | Currently selected Cabinet for scoped operations, if any |
| **Denial reason** | Structured reason when access or permission check fails — for audit and UX (implementation detail elsewhere) |

### 4.4. Responsibilities

| Responsibility | Owner |
|----------------|-------|
| Resolve Person from authenticated Platform User | Resolver (or immediate upstream identity bridge) |
| Filter Employments active at T | Resolver |
| Map Employment → org-unique Position → Position Cabinet | Resolver |
| Merge acting overlay Cabinets into accessible set | Resolver |
| Exclude liquidated Positions/Cabinets | Resolver |
| Load Permission Template per accessible Cabinet | Resolver |
| Compute permission union | Resolver |
| Apply active Cabinet context for scoped checks | Resolver + consumer |
| Verify specific Permission for authorization decision | Resolver (check) + route consumer (enforce) |
| Audit `(person_id, cabinet_id, permission, timestamp)` | Consumer subsystems |

### 4.5. Non-responsibilities

| Concern | Owner |
|---------|-------|
| Credential verification, JWT issuance | Authentication layer |
| Opening/closing Employment | HR / personnel ADRs |
| Creating Position or Cabinet | ADR-050 lifecycle |
| Editing Permission Template configuration | Org admin / platform config ADRs |
| Task routing, directory scope algorithms | Consumer ADRs (use resolver outputs) |
| UI cabinet selector rendering | Personal UI Shell ADRs |

---

## 5. Effective Permission Algorithm

### 5.1. Definition

At evaluation time **T**, for Person **P**:

```text
EffectivePermissionSet(P, T) =
    ⋃  Permissions(Template(C))
        C ∈ AccessibleCabinets(P, T)
    ∪  ExceptionGrants(P, T)     -- optional; transitional overlay only
```

Where:

```text
AccessibleCabinets(P, T) =
    { Cabinet(pos) | ∃ Employment E :
        E.person = P
        ∧ E.activeAt(T)
        ∧ E.position = pos
        ∧ pos.lifecycle ≠ liquidated
    }
    ∪
    { Cabinet(pos) | ∃ Acting A :
        A.person = P
        ∧ A.activeAt(T)
        ∧ A.targetPosition = pos
        ∧ pos.lifecycle ≠ liquidated
    }
```

**Union semantics:** if Permission `X` appears in Template of Cabinet A and Template of Cabinet B, `X` appears **once** in the effective set. There is **no role merging**, **no rank MAX**, and **no inheritance hierarchy** between Cabinets — only set union of atomic Permissions.

### 5.2. Permission Template evaluation

For each accessible Cabinet **C**:

1. Load the **Permission Template** bound to **C** (ADR-050 I8).
2. Expand Template to its constituent **Permissions** (module, action, visibility, routing codes as defined by platform policy).
3. Add all Permissions to the accumulating effective set.

Template evaluation is **local to Cabinet** — Templates do not reference other Cabinets. Cross-Cabinet effects arise **only** through union of multiple accessible Cabinets, not through Template-to-Template rules.

### 5.3. Determinism requirements

| Rule | Contract |
|------|----------|
| **Same inputs → same outputs** | Given identical Person, Employments, acting records, Cabinet configurations, and T, the resolver produces identical accessible set and effective permissions |
| **Time-bound evaluation** | All period checks use explicit T — typically request timestamp; backdated evaluation uses supplied T |
| **No User attributes in baseline path** | `users.role_id`, `users.unit_id` are **not** inputs to baseline calculation in target state |
| **Stable Cabinet id** | Permission history accrues to stable Cabinet id across rename and occupant change (ADR-050 I13) |
| **Liquidation exclusion** | Liquidated Position/Cabinet contributes **no** Permissions and is **not** accessible |

### 5.4. Vacancy behavior

| State | Accessible via primary Employment? | Cabinet exists? | Permission Template |
|-------|----------------------------------|-------------------|---------------------|
| Position **occupied** (active Employment) | **Yes** — occupant Person | Yes | Active inside Cabinet |
| Position **vacant** (no active Employment) | **No** — no Person | Yes — persists (ADR-050 §5.6) | Active inside Cabinet; unreachable until Employment or acting |
| Position **liquidated** | **No** | Terminated | Ceased with Cabinet |

**Vacancy grants no access.** A vacant Cabinet is **not** an error state — it is a Cabinet with **zero current occupants** in the accessible set. Process behavior for tasks and notifications during vacancy is **Business Policy** (ARCH-001 §4.7.2), not resolver scope.

**Acting during vacancy:** Person P may receive temporary access to vacant Position's Cabinet via **acting overlay** (ADR-036) without opening primary Employment on that Position. Acting **adds** the Cabinet; it does not imply ownership or permanent Employment.

### 5.5. Organization boundary

All Cabinets in the accessible set belong to the **same organization** (single tenant). Permissions that express org scope (e.g. visibility across org units) are evaluated from:

- **Cabinet's Position placement** in org structure, and
- **Permission codes** in the Template,

not from a separate org claim on Platform User. Resolver does not model multi-tenant org switching.

---

## 6. Multiple Cabinet Resolution

Person may hold **multiple accessible Cabinets simultaneously**. The resolver represents each access path **explicitly** — without collapsing Cabinets into a synthetic role.

### 6.1. Access provenance types

| Type | Source | Effect on accessible set |
|------|--------|--------------------------|
| **Primary Employment** | Active Employment marked or inferred as primary assignment | Adds Cabinet for occupied Position |
| **Secondary Employment** | Additional concurrent Employment (совместительство) | **Adds** second Cabinet — does not replace primary |
| **Acting duty (и.о.)** | ADR-036 overlay for temporary replacement | **Adds** target Position's Cabinet for overlay period |
| **Temporary appointment** | Time-bounded Employment or acting with explicit `[start, end]` | Cabinet access **auto-expires** at period end |

Each accessible Cabinet entry carries **provenance metadata** (which Employment or acting record granted access). Provenance is used for audit and default Cabinet selection — not for permission rank.

### 6.2. Resolution rules

| Rule | Contract |
|------|----------|
| **Additive only** | New Employment or acting **adds** Cabinets; ending one path **removes only** Cabinets from that path |
| **Acting never replaces primary** | Closing acting removes acting Cabinet only; primary Employment Cabinets unchanged |
| **No role merging** | Effective permissions = **union** of Template Permissions — no composite role, no MAX rank, no super-role |
| **Independent Templates** | Each Cabinet's Template evaluated independently before union |
| **Concurrent Positions** | N active Employments → up to N Cabinets (subject to lifecycle filters) |
| **Overlap periods** | Multiple paths to same Cabinet at T — Cabinet appears **once** in accessible set |
| **End of acting** | At `valid_to`, acting Cabinet removed from accessible set **automatically** — no manual User mutation |

### 6.3. Example (conceptual)

```text
Person: Петров
T = 2026-07-15

Primary Employment  → Position «Ординатор 1, Хирургия 1»  → Cabinet A  → Template permissions {P1, P2}
Acting overlay      → Position «Заведующий, Хирургия 1»   → Cabinet B  → Template permissions {P3, P4}
                                              (05.07 – 25.07)

Accessible Cabinets at T: { A, B }
Effective Permission Set: { P1, P2, P3, P4 }

At T = 2026-07-26 (acting ended):
Accessible Cabinets: { A }
Effective Permission Set: { P1, P2 }
Cabinet B persists on Position — unchanged; Петров no longer in accessible set for B
```

---

## 7. Active Cabinet Context

Runtime access context separates **what Person may do in aggregate** (effective union) from **which Cabinet Person is operating as** for scoped actions.

### 7.1. Concepts

| Concept | Definition |
|---------|------------|
| **Available Cabinets** | Full accessible set from resolver at T — all Cabinets Person may enter |
| **Current Cabinet / Active Cabinet** | Single Cabinet selected for **Cabinet-scoped** operations in current session |
| **Default Cabinet** | Cabinet used when scoped operation requires context but none explicitly selected |
| **Global operations** | Operations authorized by Permission presence in **effective union** without requiring active Cabinet |
| **Cabinet-scoped operations** | Operations that require active Cabinet context — e.g. submit report **as** a specific function, execute task bound to executor Cabinet |

### 7.2. Switching Cabinet context

Person with multiple accessible Cabinets may **switch active Cabinet context** without re-authentication. Switching:

- Changes **current Cabinet** for scoped operations and UI presentation;
- Does **not** change effective permission union (union is independent of selection);
- Does **not** grant access to Cabinets outside accessible set;
- Must be **auditable** — actions record `(person_id, active_cabinet_id, ...)`.

No UI implementation is defined here. Consumer ADRs (ADR-007, Personal UI Shell) consume **available Cabinets[]** and **active Cabinet** from resolver/session contract.

### 7.3. Default Cabinet selection

When scoped operation requires active Cabinet and none is selected, default selection follows **deterministic precedence**:

| Priority | Rule |
|----------|------|
| 1 | Explicit session selection, if valid member of accessible set |
| 2 | **Primary Employment** Cabinet, if exactly one primary |
| 3 | If single accessible Cabinet — that Cabinet |
| 4 | If multiple without primary marker — platform policy defines tie-break (e.g. lexicographic stable Cabinet id) — must remain deterministic |

Default selection is **not** authorization — it is context convenience. Authorization still requires Permission in effective set (and scoped rules where applicable).

### 7.4. Global vs Cabinet-scoped permission evaluation

| Evaluation mode | Question | Inputs |
|-----------------|----------|--------|
| **Global** | Does Person hold Permission P at T? | Effective Permission Set (union) |
| **Cabinet-scoped** | Does Person hold Permission P **in context of Cabinet C** at T? | C ∈ Accessible Cabinets **and** P ∈ Template(C) |
| **Object-bound** | May Person act on object O? | Object's bound Cabinet + Permission + optional initiator Person rule (ADR-023 exception) |

Consumers must declare which mode applies. Task mine/execute against cabinet-bound tasks uses **object-bound** or **Cabinet-scoped** evaluation — not `users.role_id`.

---

## 8. Authorization Pipeline

### 8.1. Conceptual pipeline (mandatory)

Every authorized request in the target model follows this chain:

```text
HTTP Request
        │
        ▼
Authentication
        │  (credential verification; JWT validates Platform User identity only)
        ▼
Platform User
        │  (login, account status — no operational permissions)
        ▼
Person
        │  (canonical human identity via User linkage)
        ▼
Active Employments (+ Acting overlays at T)
        │  (time-filtered HR access facts)
        ▼
Accessible Position Cabinets
        │  (0..N Cabinets; provenance per path)
        ▼
Permission Templates
        │  (one per accessible Cabinet)
        ▼
Effective Permission Set
        │  (deterministic union + optional documented exceptions)
        ▼
Active Cabinet Context (when scoped evaluation required)
        │
        ▼
Authorization Decision
        │  (allow / deny; audit person + cabinet + permission)
```

### 8.2. Stage contracts

| Stage | Contract |
|-------|----------|
| **Authentication** | Establishes **Platform User** identity. **Fails closed** on invalid/expired/revoked credentials. **No** permission claims in token. |
| **Person resolution** | Every operational Platform User maps to **Person** for authorization. User without Person linkage receives **empty** accessible set unless break-glass exception policy applies. |
| **Employment load** | Only **active** Employments at T qualify. Closed, future, or inactive episodes excluded. |
| **Acting merge** | Active acting overlays **union** additional Cabinets. Acting on vacant Position permitted. |
| **Cabinet filter** | Exclude **liquidated** Cabinets. Include **vacant** Cabinets only as acting target — not via primary Employment without occupant. |
| **Template load** | Load Template configuration from each accessible Cabinet. Missing Template = implementation error at Cabinet setup — not resolver fallback to User role. |
| **Effective set** | Union Permissions. Exception grants applied last per documented exception policy only. |
| **Context** | Resolve active Cabinet for scoped checks. |
| **Decision** | Consumer compares required Permission / scope against resolver outputs. |

### 8.3. Independence from login method

Authorization pipeline inputs are **identical** regardless of login method (password, future SSO, service account policy). Login method affects **authentication** only. Telegram bot and internal API authenticate as Platform User, then enter the **same** Person → Cabinet → Permission pipeline.

### 8.4. Transitional coexistence (conceptual)

During migration, legacy user-centric checks may run **in shadow** alongside resolver output for comparison. Shadow mode is **transitional** — not part of target architecture. Cutover retires `users.role_id` as authorization input per migration phases (§10).

---

## 9. Invariants

Mandatory invariants for Cabinet access resolution. They restate ARCH-001, ADR-050, and foundation assessment conclusions as **operational contracts**.

| # | Invariant |
|---|-----------|
| R1 | **Authentication remains Platform User responsibility** — login, password, account status, token subject. |
| R2 | **Authorization never originates from Platform User** — `users.role_id` and User-attached attributes are not baseline permission sources in target state. |
| R3 | **Authorization derives from active Employments** — primary path: Person occupies Position → Cabinet access for employment period. |
| R4 | **Employment grants access to Position Cabinet** — not to Permission Template directly on Person; access is to Cabinet, Permissions inherited via Template inside Cabinet. |
| R5 | **Permission Templates define permissions** — Templates live inside Cabinet (ADR-050 I8); not assigned to User or Person. |
| R6 | **Effective permissions are the union of accessible Cabinets** unless evaluation explicitly requires active Cabinet context or object binding. |
| R7 | **Acting duties add Cabinets; they never replace ownership** — primary Employment Cabinets remain; acting Cabinet removed when overlay ends. |
| R8 | **Vacancy grants no access** via primary Employment — vacant Cabinet persists but has zero occupants in accessible set until Employment or acting. |
| R9 | **Cabinet identity is stable** — same Cabinet id across rename and occupant change; resolver keys on stable Cabinet id. |
| R10 | **Permission calculation is deterministic** — same Person, access records, Cabinet configs, and T → same outputs. |
| R11 | **Authorization is independent of login method** — pipeline after authentication is identical. |
| R12 | **JWT never contains effective permissions** — no role, permission, cabinet, or org claims in token for authorization purposes. |
| R13 | **No Slot entity** — multi-Cabinet access from multiple Positions, not Slot indirection (ARCH-001 §15.0, ADR-050 I12). |
| R14 | **No user roles as architectural entities** — Platform Role assignment on User is transitional; target model has Permission Template in Cabinet only. |
| R15 | **Person never owns Cabinet** — Person appears in accessible set as **grantee of access period**, not owner (ADR-050 I6). |
| R16 | **Liquidated Cabinet is inaccessible** — terminal lifecycle excludes Cabinet from accessible set. |
| R17 | **Exception overlays extend, not replace** — `access_grants` and similar mechanisms are documented exceptions atop Cabinet baseline, not parallel permission centers. |

---

## 10. Migration Strategy

Architectural phases only — **no** SQL, **no** code, **no** API specifications. Phases assume [ADR-050 migration](./ADR-050-organization-position-cabinet-model.md) Phase 1–3 complete (org-unique Position, Cabinet entity, Employment retarget).

### Phase 1 — Resolver definition and read path

- Implement Cabinet Access Resolver as **read-only** computation from Person + Employments + acting + Cabinet Templates.
- Expose outputs to `/auth/me` consumer **alongside** legacy role fields (compatibility — ADR-042 B5).
- Person materialization complete on operational users (ADR-048 gate).

### Phase 2 — Shadow enforcement

- Route guards and task checks compute **both** legacy user-centric decision and resolver decision.
- Log divergence; no user-visible behavior change unless shadow confirms parity for subsystem.
- Encode env role allowlists as **legacy policy debt** mapped to Template permissions for comparison.

### Phase 3 — Enforcement cutover (per subsystem)

- Flip enforcement to resolver for tasks (ADR-049), directory visibility (ADR-042 E1), admin gates, personnel admin — **subsystem by subsystem**.
- Retain break-glass exception grants during cutover.
- Stop writing `users.role_id` for operational access changes; HR Employment management replaces «Роль Corpsite» semantics (OPS-029).

### Phase 4 — Acting overlay integration

- Wire ADR-036 acting records into resolver acting merge path.
- Explicitly forbid role-swap acting anti-pattern in operations policy.

### Phase 5 — Decommission user-centric authorization

- Remove legacy role fields from authorization inputs.
- Narrow `access_grants` to documented exceptions.
- Retire shadow modes; `public.roles` retained as Template **definition catalog** only — not User assignment target.

**Hard rule:** do not cut over enforcement until ADR-050 Position/Cabinet identities and Employment FK retarget are stable.

---

## 11. Consequences

### Positive

- **Single authorization truth** — Employment and acting drive access; aligns runtime with HR facts.
- **Multi-position and и.о. without User mutation** — union semantics support совместительство and acting natively.
- **Deterministic audit trail** — `(person_id, cabinet_id, permission)` replaces implicit role context.
- **Vacancy clarity** — Cabinet persists; access empty until occupant — no phantom permissions from stale User role.
- **Localized permission blast radius** — Template changes affect one Cabinet, not all Users sharing legacy role id.
- **Unblocks consumer migration** — tasks, visibility, Telegram routing consume resolver outputs.

### Negative / costs

- **Every request pays resolver cost** — mitigated by caching policy (implementation); revocation remains DB-authoritative.
- **Person linkage required** — Users without Person cannot receive cabinet access (by design).
- **Migration complexity** — shadow period mandatory; premature `role_id` removal risks lockout.
- **Consumer ADR wave** — ADR-023, ADR-042 B5/E1, ADR-049, OPS-029 require amendment before full cutover.
- **Acting HR overlay must exist** — resolver acting path blocked until ADR-036 operational read model available.

### Neutral

- JWT transport unchanged — auth-only claims preserved.
- Exception grants may coexist as overlay — narrowed over time.
- Default Cabinet selection policy is convenience — does not alter union semantics.
- Business process policy at vacancy unchanged in scope.

---

## 12. Decision Log

| Date | Decision |
|------|----------|
| 2026-07-03 | **Proposed ADR-051** — Cabinet Access Resolver operational contract from ARCH-001, foundation assessments, ADR-050. |
| 2026-07-03 | **Cabinet-centric authorization** replaces user-centric RBAC as baseline; Platform User remains auth-only. |
| 2026-07-03 | **Effective Permission Set = union** of Template Permissions across accessible Cabinets — no role merging. |
| 2026-07-03 | **Acting adds Cabinets** — never replaces primary Employment access; auto-expires with overlay period. |
| 2026-07-03 | **Vacancy grants no access** — vacant Cabinet persists; zero occupants in accessible set. |
| 2026-07-03 | **Deterministic resolver** — explicit evaluation time T; stable Cabinet id; no User role inputs in target path. |
| 2026-07-03 | **JWT excludes effective permissions** — authorization resolved post-authentication from authoritative stores. |
| 2026-07-03 | **Active Cabinet context** — separate runtime concept for scoped ops; switching without re-auth. |
| 2026-07-03 | **No Platform Role / user role entity** — transitional as-is only; Permission Template inside Cabinet is sole baseline definition. |
| 2026-07-03 | **No Slot entity** — confirmed per ARCH-001 §15.0 and ADR-050. |
| 2026-07-03 | **Exception grants** — overlay only; do not replace Cabinet baseline (ARCH-001 §15.0). |
| 2026-07-04 | **Accepted ADR-051** — ratified as implementation baseline for Cabinet Access Resolver; depends on Accepted ADR-050. |

---

## Appendix A — Resolver vs ADR-050 boundary

| Concern | ADR-050 | ADR-051 (this ADR) |
|---------|---------|-------------------|
| Position identity | Defines | Consumes |
| Cabinet 1:1 lifecycle | Defines | Consumes (excludes liquidated) |
| Permission Template location | Inside Cabinet | Evaluates Template contents |
| Employment FK target | Org-unique Position | Reads active Employments |
| Vacancy definition | HR state on Position | Zero access via primary Employment |
| Access calculation | Deferred | **Defines** |
| Active Cabinet UI | — | Context contract only |

---

## Appendix B — Related assessment cross-reference

| Assessment | ADR-051 dependency |
|------------|-------------------|
| [access-rbac](../architecture/ARCH-001-access-rbac-assessment.md) | Primary source for TO-BE pipeline §11.2, union semantics, migration phases |
| [personnel-employment](../architecture/ARCH-001-personnel-employment-assessment.md) | Employment as access gate; acting blocked until resolver |
| [platform-user-identity](../architecture/ARCH-001-platform-user-identity-assessment.md) | JWT auth-only; Person linkage |
| [foundation summary](../architecture/ARCH-001-foundation-summary.md) | Critical path gate #2; confirmed chain |
| [tasks](../architecture/ARCH-001-task-subsystem-assessment.md) | Consumer of accessible Cabinets for executor routing |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 0.1 | Initial proposed ADR — Cabinet Access Resolver operational contract |
| 2026-07-04 | 1.0 | Status Proposed → Accepted — Phase 2 implementation gate |
