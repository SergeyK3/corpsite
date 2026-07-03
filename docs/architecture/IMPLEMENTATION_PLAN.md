# IMPLEMENTATION_PLAN — Position Cabinet Architecture

## Document metadata

| Field | Value |
|-------|-------|
| Status | **Active** — 2026-07-03 |
| Type | Engineering execution plan (not an ADR, not architecture) |
| Authority | [ARCH-001-implementation-roadmap.md](./ARCH-001-implementation-roadmap.md) — sequencing is **fixed** by this document |
| Baseline (read-only) | [ARCHITECTURE_GOVERNANCE](./ARCHITECTURE_GOVERNANCE.md), [ARCH-001](./ARCH-001-position-permission-model.md) |
| Implementation contracts | [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md), [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) (**Proposed** — not approved by this plan) |

**Purpose:** translate the [implementation roadmap](./ARCH-001-implementation-roadmap.md) into concrete engineering work packages. This document **does not** approve ADRs, **does not** change architecture, and **does not** alter phase sequencing.

**As-is engineering context (informative):** runtime today centers on `public.users.role_id`, `public.roles`, `person_assignments` with catalog `position_id` + `org_unit_id`, `access_resolver_service` (ADR-042 B3 grant overlay), and `_enrich_user_context` in `app/auth.py`. Target state is described in ADR-050/051 and foundation assessments — implementation follows those contracts after Phase 1 approval.

---

## Milestone table

| Milestone | Roadmap phase | Engineering gate | Target status |
|-----------|---------------|-------------------|---------------|
| M0 | Phase 0 | Foundation corpus complete | **Done** |
| M1 | Phase 1 | ADR-050 + ADR-051 approved | **Pending** |
| M2 | Phase 2 | Org-unique Position + Cabinet in DB; legacy mapping stable | Not started |
| M3 | Phase 3 | Employment FK retarget complete | Not started |
| M4 | Phase 4 | Cabinet Access Resolver read path live | Not started |
| M5 | Phase 5 | Shadow/dual-read operational | Not started |
| M6 | Phase 6 | All consumers cut over (6.1–6.9) | Not started |
| M7 | Phase 7 | Role-centric ops keys decommissioned | Not started |
| M8 | Phase 8 | Cleanup complete; program closed | Not started |

---

## Dependency graph

```text
[M0 Done] Phase 0 — Foundation documents
              │
              ▼
[M1 Pending] Phase 1 — ADR approval (architecture session)
              │
    ┌─────────┴─────────┐
    │  (parallel only)  Tier 2 assessments, draft spikes
    └─────────┬─────────┘
              ▼
[M2] Phase 2 — Position / Cabinet schema + data mapping
              │
              ▼
[M3] Phase 3 — Employment retargeting
              │
              ▼
[M4] Phase 4 — Cabinet Access Resolver (read only)
              │
              ▼
[M5] Phase 5 — Dual-read / shadow
              │
              ▼
[M6] Phase 6 — Consumer migrations (sequential 6.1 → 6.9)
              │
              ▼
[M7] Phase 7 — Role-centric decommission
              │
              ▼
[M8] Phase 8 — Cleanup / stabilization
```

**Hard rule:** no milestone M2+ production work until M1 exit criteria met.

---

## Engineering checklist (program-level)

| # | Check | Phase |
|---|-------|-------|
| E1 | ADR-050 and ADR-051 status = Accepted (not Proposed) | 1 |
| E2 | Alembic migrations for Position + Cabinet merged and reviewed | 2 |
| E3 | Legacy `(org_unit_id, catalog position_id)` → Position mapping table populated and audited | 2 |
| E4 | `person_assignments` FK points to org-unique Position | 3 |
| E5 | Person linkage on all operational Platform Users (ADR-048) | 3–4 |
| E6 | `cabinet_access_resolver` service returns fixtures-validated output | 4 |
| E7 | Shadow mode flag + divergence logging enabled | 5 |
| E8 | Per-subsystem cutover checklist signed off (6.1–6.9) | 6 |
| E9 | No authorization path reads `users.role_id` as primary input | 7 |
| E10 | Shadow/compat code removed; runbooks updated | 8 |

---

## Phase 0 — Architecture Foundation Complete

| Field | Value |
|-------|-------|
| **Roadmap status** | Done |
| **Engineering status** | Complete — no build work |

### 1. Objective

Archive and index completed architecture artifacts; establish baseline references for all subsequent engineering phases.

### 2. Expected deliverables

- Published foundation documents (ARCH-001, assessments, ADR-050/051 Proposed, roadmap, this plan).
- Team onboarding pointer to [foundation summary](./ARCH-001-foundation-summary.md) and [consolidation review](./ARCH-001-foundation-consolidation-review.md).

### 3. Source documents

| Document | Role |
|----------|------|
| [ARCHITECTURE_GOVERNANCE](./ARCHITECTURE_GOVERNANCE.md) | Baseline principles |
| [ARCH-001](./ARCH-001-position-permission-model.md) | Domain model |
| [Foundation summary](./ARCH-001-foundation-summary.md) | Confirmed chain and invariants |
| [Consolidation review](./ARCH-001-foundation-consolidation-review.md) | Corpus consistency |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md), [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | Implementation contracts (Proposed) |
| [Implementation roadmap](./ARCH-001-implementation-roadmap.md) | Phase sequencing |

### 4. Preconditions

None — phase complete.

### 5. Main implementation tasks

- None (documentation phase complete).
- Engineering: read foundation summary §2–§4 and access-rbac assessment §11 (as-is vs to-be pipeline).

### 6–8. Database / backend / frontend changes

**None.**

### 9. Testing strategy

N/A — no runtime changes.

### 10. Rollback strategy

N/A.

### 11. Exit criteria

- [x] Tier 0 + Tier 1 assessments complete.
- [x] ADR-050 and ADR-051 authored (Proposed).
- [x] Roadmap and implementation plan published.

---

## Phase 1 — Approval Gate

| Field | Value |
|-------|-------|
| **Roadmap status** | Pending |
| **Engineering status** | Preparation only until ADRs Accepted |

### 1. Objective

Obtain architecture session approval of ADR-050 and ADR-051 before any production schema or enforcement work. Engineering prepares execution packages; **does not** treat Proposed ADRs as build authority.

### 2. Expected deliverables

- Architecture session minutes with ADR-050/051 approval decision.
- Updated ADR status fields (session action — **not** this plan).
- Engineering spike notes labeled **draft / pre-approval** (optional).
- Tier 2 assessment documents started or completed (`events-telegram`, etc.) per [assessment program](./ARCH-001-assessment-program.md).
- Draft migration runbook outline referencing ADR-050 §8 phases (no production execution).

### 3. Source documents

| Document | Role |
|----------|------|
| [Implementation roadmap § Phase 1](./ARCH-001-implementation-roadmap.md) | Gate definition |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md), [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | Review subjects |
| [Consolidation review](./ARCH-001-foundation-consolidation-review.md) | Coherence evidence |
| Foundation assessments | Gap inventory for session Q&A |

### 4. Preconditions

- Phase 0 exit criteria met.

### 5. Main implementation tasks

| Task | Owner | Notes |
|------|-------|-------|
| Schedule architecture session | Architecture / PM | ADR-050 then ADR-051 review order |
| Prepare ADR review pack | Engineering lead | Diff vs ARCH-001; open questions from assessments |
| Inventory as-is coupling | Engineering | `users.role_id`, `person_assignments`, tasks `executor_role_id` — from access-rbac assessment |
| Draft Phase 2–3 migration story | Engineering | Align with ADR-050 §8; **no merged migrations** until approved |
| Identify consumer ADR gaps | Engineering | ADR-049, ADR-042 B5/E1 tracking for Phase 6 |
| Optional: time-boxed spikes | Engineering | Prototype resolver signature against fixtures — **throwaway or behind feature flags** |

### 6. Expected database changes

**None in production.** Draft migration scripts may be written locally; not applied to shared environments until M1.

### 7. Expected backend changes

**None in production.** Optional branch-local prototypes only.

### 8. Expected frontend changes

**None.**

### 9. Testing strategy

- Review pack walkthrough with architects.
- Spike tests (if any) run locally only; not CI gate for production.

### 10. Rollback strategy

Discard pre-approval spike branches. No production state to roll back.

### 11. Exit criteria

- [ ] ADR-050 **Accepted** (recorded in ADR decision log).
- [ ] ADR-051 **Accepted** (recorded in ADR decision log).
- [ ] Engineering kickoff for Phase 2 scheduled.
- [ ] No production migrations merged under Proposed-only authority.

---

## Phase 2 — Position / Cabinet Model

| Field | Value |
|-------|-------|
| **Roadmap status** | Not started |
| **Engineering status** | Blocked on Phase 1 |

### 1. Objective

Introduce org-unique **Position** and 1:1 **Position Cabinet** per ADR-050; populate from legacy `(org_unit_id, catalog position_id)` pairs; establish stable mapping for transition.

### 2. Expected deliverables

- Alembic migrations: org-unique Position table, Position Cabinet table (1:1 FK), Permission Template binding on Cabinet.
- Legacy mapping table or columns (catalog pair → org-unique Position id).
- Data migration job: inventory pairs from `employees` and `person_assignments`; create Position + Cabinet per pair; split collisions.
- ADR-046 title dedup applied before/during mapping (per ADR-050 §8 Phase 2).
- Admin/ops script: verify 1:1 invariant, vacancy query at Position level.
- Updated POSITIONS_SYNC_RUNBOOK scope (taxonomy vs staffing) — draft.

### 3. Source documents

| Document | Role |
|----------|------|
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) §4–§8 | Entity contracts, lifecycle, migration phases 1–2 |
| [positions-org-structure assessment §9](./ARCH-001-positions-org-structure-assessment.md) | Engineering phase hints (P1–P2) |
| [ADR-046](../adr/ADR-046-org-unit-allowed-positions.md) | Allowed positions / taxonomy |

### 4. Preconditions

- Phase 1 exit criteria (ADR-050 **Accepted**).
- ADR-051 Accepted (required before Phase 4; recommended before Phase 2 merge to avoid schema rework — per roadmap P1/P2).
- Database backup and migration rehearsal environment available.

### 5. Main implementation tasks

| Task | Detail |
|------|--------|
| Schema design review | Names/columns per **approved ADR-050** engineering appendix (assessment suggests e.g. org-unique positions + `position_cabinets` — final names follow ADR approval pack) |
| 1:1 creation transaction | Position + Cabinet + initial Permission Template in single logical unit of work |
| Mapping inventory | SQL/report: distinct `(org_unit_id, position_id)` from `employees`, `person_assignments` |
| Collision split | One catalog id across multiple units → multiple Position rows |
| Taxonomy separation | Retain `public.positions` (or successor) as title reference only — not staffing FK target |
| Lifecycle columns | Position status: active / vacant / liquidated (ADR-050 §5.1) |
| Constraint enforcement | Org-unique identity — not global `lower(name)` uniqueness |
| Read-only API prep | Internal queries for Cabinet id by legacy pair (no auth cutover) |

### 6. Expected database changes

| Change | Purpose |
|--------|---------|
| New org-unique **Position** table (or breaking evolution of staffing table) | ADR-050 I1, I5 |
| New **Position Cabinet** table, 1:1 FK to Position | ADR-050 I2, I3 |
| Permission Template storage on Cabinet | ADR-050 I8 |
| Legacy mapping table or columns | Transition from catalog composite |
| Indexes on `(org_unit_id, …)` for staffing lookups | Directory / migration performance |
| **No** Employment FK retarget yet | Phase 3 |
| **No** resolver enforcement tables | Phase 4 |

### 7. Expected backend changes

| Area | Change |
|------|--------|
| Models / repositories | Position, Cabinet, Template entities |
| Migration services | Pair inventory, bulk create, mapping export |
| Directory (read paths) | Optional internal admin endpoints for mapping verification |
| **No change** | `app/auth.py` authorization path; `users.role_id` usage |
| **No change** | Task routing |

### 8. Expected frontend changes

| Area | Change |
|------|--------|
| Minimal or none | Phase 2 is data foundation |
| Optional | Admin-only mapping status page (if needed for ops verification) |
| **No change** | User role drawers, task scope, `/auth/me` contract |

### 9. Testing strategy

| Layer | Tests |
|-------|-------|
| Migrations | Up/down on empty DB; up on staging snapshot |
| Invariants | 1:1 Position↔Cabinet; no orphan Cabinet; liquidated excluded |
| Data migration | Fixture org with multi-unit same catalog id → N Positions |
| Regression | Existing directory/employee flows unchanged (legacy FKs still valid) |

### 10. Rollback strategy

| Step | Action |
|------|--------|
| Pre-migration | Full DB backup; tagged release |
| Rollback | Reverse Alembic revision(s); mapping table truncate |
| Data | Legacy `employees` / `person_assignments` unchanged in Phase 2 — rollback does not require HR data restore if Employment not retargeted |
| Feature flags | N/A — no user-visible behavior change |

### 11. Exit criteria

- [ ] Org-unique Position and Cabinet rows exist for all legacy staffing pairs.
- [ ] Mapping from `(org_unit_id, catalog position_id)` → Position id is complete and audited.
- [ ] Vacancy queryable at Position level (no active Employment optional check — full retarget in Phase 3).
- [ ] 1:1 invariant verified by automated check.
- [ ] **No** Employment FK retarget; **no** resolver enforcement.

---

## Phase 3 — Employment Retargeting

| Field | Value |
|-------|-------|
| **Roadmap status** | Not started |
| **Engineering status** | Blocked on Phase 2 |

### 1. Objective

Retarget Employment (`person_assignments`) from catalog composite to org-unique Position FK; align Employee snapshot; complete Person materialization for resolver inputs.

### 2. Expected deliverables

- Alembic migration: `person_assignments` → org-unique Position FK (nullable transition → NOT NULL).
- Backfill job: map existing rows via Phase 2 mapping table.
- Validation: block new assignments to catalog composite as staffing truth.
- Employee snapshot alignment: `employees.position_id` / org context derived from active Employment (per ADR-042, ADR-041 direction).
- Person materialization completion on operational users (ADR-048).
- Vacancy derivation job/query: Position with no active Employment.

### 3. Source documents

| Document | Role |
|----------|------|
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) §8 Phase 3 | Employment retarget |
| [personnel-employment assessment](./ARCH-001-personnel-employment-assessment.md) | Employment truth, Employee shell |
| [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md) | Person materialization |
| [ADR-042 Phase A/B](../adr/ADR-042-phase-a-personnel-access-enrollment-architecture.md) | `person_assignments` model |

### 4. Preconditions

- Phase 2 exit criteria met.
- Mapping table complete and spot-audited.
- Person backfill plan approved (ADR-048).

### 5. Main implementation tasks

| Task | Detail |
|------|--------|
| FK migration | Add org-unique Position FK; backfill; deprecate catalog composite for new writes |
| Enrollment / HR services | `enrollment_service`, assignment CRUD write org-unique Position |
| Employee sync | Snapshot fields follow Employment; remove dual-write as end state |
| Person linkage | User create / enrollment ensures Person id for operational accounts |
| Validation guards | Reject new `person_assignments` using catalog-only staffing identity |
| Acting prep | Document read hook for ADR-036 overlay (implementation may follow in Phase 4) |
| Directory employment UI | Pick Position in unit, not `(unit + global title)` composite |

### 6. Expected database changes

| Change | Purpose |
|--------|---------|
| `person_assignments` FK → org-unique Position | ADR-050 I5 |
| Deprecate / stop writes to catalog composite columns | Staffing truth |
| Optional: generated column or view for legacy read compat | Dual-read prep |
| Person linkage completeness constraints or reports | ADR-048 |
| **No** authorization cutover | Phase 5–6 |

### 7. Expected backend changes

| Area | Change |
|------|--------|
| `person_assignments` services | FK target, validation |
| `enrollment_service.py`, personnel routes | Org-unique Position selection |
| `employees` sync | Derive from Employment |
| User/Person bridge | Materialization on create/link paths |
| **No change yet** | Route guards still use `users.role_id` |

### 8. Expected frontend changes

| Area | Change |
|------|--------|
| Employee drawer / assignment forms | Select org-unique Position (staffing), not catalog title alone |
| Directory positions | Split taxonomy vs staffing reads (ADR-031 direction) |
| **No change yet** | «Роль Corpsite» / `updateUserRole` — Phase 6+ |

### 9. Testing strategy

| Layer | Tests |
|-------|-------|
| Migration | Backfill count = pre-migration assignment count |
| API | Create/update Employment resolves to correct Cabinet id (internal query) |
| Person | User without Person flagged; enrollment creates Person |
| Regression | Legacy read paths still work during compat window |
| Vacancy | Position with closed Employment shows vacant |

### 10. Rollback strategy

| Step | Action |
|------|--------|
| Compat window | Keep legacy columns populated (dual-write) until Phase 5 shadow sign-off |
| Rollback migration | Restore catalog FK writes; revert FK NOT NULL if needed |
| HR ops | Freeze assignment changes during rollback window |

### 11. Exit criteria

- [ ] All active `person_assignments` resolve to org-unique Position → Cabinet id.
- [ ] New Employments cannot bind to catalog composite as staffing truth.
- [ ] Person linkage on operational users meets ADR-048 threshold.
- [ ] Dual-write ended or legacy columns read-only per plan.
- [ ] **No** resolver enforcement cutover.

---

## Phase 4 — Cabinet Access Resolver

| Field | Value |
|-------|-------|
| **Roadmap status** | Not started |
| **Engineering status** | Blocked on Phase 3 |

### 1. Objective

Implement ADR-051 **read path**: accessible Cabinets, effective permission union, default/active context — exposed alongside legacy auth context, **not** authoritative for enforcement.

### 2. Expected deliverables

- `cabinet_access_resolver` service (or evolution of `access_resolver_service`) per ADR-051 §4–§5.
- Functions: `resolve_accessible_cabinets(person_id, t)`, `effective_permissions(person_id, t)`, provenance metadata.
- Integration: post-auth enrichment hook (after Person resolution).
- Optional `/auth/me` additive fields behind feature flag (ADR-042 B5 direction).
- Unit + integration tests against fixture Persons (multi-employment, vacancy, liquidated exclusion).
- Acting overlay hook (stub or ADR-036 read model when available).

### 3. Source documents

| Document | Role |
|----------|------|
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) §4–§8 | Resolver contract, algorithm, pipeline |
| [access-rbac assessment §11.2](./ARCH-001-access-rbac-assessment.md) | TO-BE pipeline |
| [ADR-042 B5](../adr/ADR-042-phase-b5-auth-policy.md) | `/auth/me` direction |
| Existing `app/services/access_resolver_service.py` | Transitional grant overlay — coexist, do not replace baseline |

### 4. Preconditions

- Phase 3 exit criteria met.
- ADR-051 **Accepted**.
- Permission Templates populated on Cabinets (Phase 2).

### 5. Main implementation tasks

| Task | Detail |
|------|--------|
| Resolver module | Person → active Employments at T → Position → Cabinet |
| Template expansion | Load Permissions per accessible Cabinet; set union |
| Liquidation filter | Exclude liquidated Cabinets |
| Vacancy | Zero occupants via primary Employment; acting hook when available |
| Person bridge | Platform User → Person in auth pipeline |
| Exception overlay | Optional: merge documented `access_grants` exceptions last (ADR-051 R17) |
| JWT | Confirm no permission claims added (ADR-013, ADR-051 R12) |
| **Explicit non-task** | Flip route guards; stop using `users.role_id` |

### 6. Expected database changes

| Change | Purpose |
|--------|---------|
| Queries only (initially) | Read Employments, Cabinets, Templates |
| Optional: resolver cache table | Performance — engineering decision, not architecture |
| Optional: audit log for resolver diagnostics | Shadow phase |
| **No** JWT schema change | Auth-only claims |

### 7. Expected backend changes

| Area | Change |
|------|--------|
| New resolver service | ADR-051 core |
| `app/auth.py` | Call resolver after Person resolution; attach to context dict **additively** |
| `/auth/me` route | Optional `accessible_cabinets[]`, `effective_permissions[]` |
| **Unchanged authority** | Guards still use `_enrich_user_context` legacy flags |
| Tests | `tests/test_cabinet_access_resolver.py` (new) |

### 8. Expected frontend changes

| Area | Change |
|------|--------|
| Optional | Consume new `/auth/me` fields in dev/staging only (feature flag) |
| **No production UX change** | Legacy role-based nav unchanged |

### 9. Testing strategy

| Layer | Tests |
|-------|-------|
| Unit | Union semantics; deterministic T; no role merge |
| Fixtures | Primary + secondary Employment; acting adds Cabinet; acting end removes |
| Vacancy | No access via primary Employment; Cabinet exists |
| Liquidation | Excluded from accessible set |
| JWT | Token payload unchanged |
| Person gap | User without Person → empty accessible set |

### 10. Rollback strategy

| Step | Action |
|------|--------|
| Feature flag | Disable resolver enrichment and `/auth/me` new fields |
| Code | Resolver is read-only — disable calls with no data migration rollback |
| Auth | Legacy path unaffected if flag off |

### 11. Exit criteria

- [ ] Resolver output matches fixture expectations for representative org roster.
- [ ] Person linkage threshold met on operational users.
- [ ] `/auth/me` additive fields available in staging (if flag used).
- [ ] **No** route guard uses resolver as sole authority.
- [ ] JWT remains auth-only.

---

## Phase 5 — Dual-Read Compatibility

| Field | Value |
|-------|-------|
| **Roadmap status** | Not started |
| **Engineering status** | Blocked on Phase 4 |

### 1. Objective

Run cabinet-based authorization **in parallel** with legacy user/role/employee paths; log divergences; keep legacy authoritative until per-subsystem Phase 6 cutover.

### 2. Expected deliverables

- Shadow mode configuration (env or feature flag): `CABINET_ACCESS_SHADOW=1` pattern (analogous to `ADR042_ADMIN_GUARD_MODE`).
- Divergence logger: `(route, user_id, person_id, legacy_decision, resolver_decision, timestamp)`.
- Legacy policy debt inventory: env allowlists → Template permission mapping doc.
- `/auth/me` exposes cabinet fields in staging/production **additively**.
- Ops policy: acting via `users.role_id` swap forbidden (runbook note).
- Parity report template per subsystem before Phase 6 flip.

### 3. Source documents

| Document | Role |
|----------|------|
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) §10 Phase 2 | Shadow enforcement |
| [access-rbac assessment §9 Phase 0](./ARCH-001-access-rbac-assessment.md) | Shadow pattern |
| [Implementation roadmap § Phase 5](./ARCH-001-implementation-roadmap.md) | Gate before cutover |

### 4. Preconditions

- Phase 4 exit criteria met.
- Resolver stable on staging with production-like data snapshot.

### 5. Main implementation tasks

| Task | Detail |
|------|--------|
| Shadow wrapper | Decorator or middleware on key guards: `tasks_service`, `directory/rbac`, `admin_permissions`, personnel visibility |
| Logging / metrics | Divergence rate dashboards |
| Policy mapping doc | `DIRECTOR_ROLE_IDS`, `QM_HEAD`, etc. → Template equivalents |
| `/auth/me` rollout | Additive fields enabled in production |
| CI smoke | Shadow on in integration tests |
| Sign-off process | Subsystem owner reviews parity report |

### 6. Expected database changes

| Change | Purpose |
|--------|---------|
| Optional shadow audit table | Divergence storage |
| **No** schema required for shadow | Log-only acceptable |

### 7. Expected backend changes

| Area | Change |
|------|--------|
| Guards | Dual evaluation; legacy wins |
| `tasks_service.py`, `tasks_router.py` | Shadow compare mine/team |
| `directory_scope.py`, E1 visibility | Shadow compare |
| `admin_permissions.py` | Shadow compare sysadmin paths |
| Telegram bot auth | Shadow on `require_bot_bound_user` enrichment |

### 8. Expected frontend changes

| Area | Change |
|------|--------|
| `/auth/me` consumers | Read new fields; **do not** switch gates until Phase 6 |
| Dev tools | Optional shadow divergence admin view |

### 9. Testing strategy

| Layer | Tests |
|-------|-------|
| Integration | Same request → legacy allow implies resolver allow (target %) |
| Regression | User-visible behavior identical to pre-shadow |
| Load | Shadow overhead acceptable |
| Manual | Pilot users on staging with multi-employment |

### 10. Rollback strategy

| Step | Action |
|------|--------|
| Flag off | `CABINET_ACCESS_SHADOW=0` — instant return to legacy-only |
| `/auth/me` | Hide additive fields via flag |
| No data rollback | Shadow is observability only |

### 11. Exit criteria

- [ ] Shadow running in staging ≥ agreed soak period.
- [ ] Parity reports drafted for Tasks, Directory, Admin (minimum).
- [ ] Documented intentional differences signed by architecture/engineering.
- [ ] No silent high-rate divergence without ticket.
- [ ] Ops policy published: no role-swap acting.

---

## Phase 6 — Consumer Subsystem Migration

| Field | Value |
|-------|-------|
| **Roadmap status** | Not started |
| **Engineering status** | Blocked on Phase 5 |

### 1. Objective

Migrate each operational consumer to Cabinet-centric ownership and resolver-based authorization **one subsystem at a time**, in roadmap order 6.1 → 6.9.

### 2. Expected deliverables

Per sub-phase: subsystem cutover PR, shadow flip to enforced, subsystem ADR amendment or implementation note, updated tests, parity sign-off.

| Sub | Subsystem | Key deliverables |
|-----|-----------|------------------|
| **6.1** | Tasks / Regular Tasks | `executor_cabinet_id`; mine = accessible Cabinets; ADR-049; ADR-023/020/024 amendments |
| **6.2** | Events & Telegram | Recipient resolution Cabinet → occupants → Platform User |
| **6.3** | Working Contacts | Scope from Cabinet/org policy vs `users.unit_id` alone |
| **6.4** | Directory Contacts | Predicates vs Cabinet/org scope |
| **6.5** | Personal UI Shell | Cabinet list, active context; ADR-007 terminology |
| **6.6** | Personal File | Person-bound validation only — no Cabinet ownership |
| **6.7** | HR Import / Canonical | Person/Employment sync boundaries |
| **6.8** | Employee Documents | Document class split unchanged architecturally |
| **6.9** | Org Sync / Admin | Position/Cabinet config admin; reference data |

**Cross-cutting:** ADR-042 E1 visibility, ADR-042 B5 `/auth/me` cutover, admin gates — migrate with relevant sub-phases.

### 3. Source documents

| Document | Role |
|----------|------|
| [Implementation roadmap § Phase 6](./ARCH-001-implementation-roadmap.md) | Order 6.1–6.9 |
| [tasks assessment](./ARCH-001-task-subsystem-assessment.md) | 6.1 detail |
| Tier 2 assessments (as completed) | 6.2–6.9 detail |
| ADR-049, ADR-023, ADR-020, ADR-024, ADR-042 B5/E1 | Consumer contracts |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) §10 Phase 3 | Enforcement cutover |

### 4. Preconditions

- Phase 5 exit criteria met for **target sub-phase**.
- Subsystem transition ADR published or amended (e.g. ADR-049 before 6.1).
- Parity sign-off for that subsystem.

### 5. Main implementation tasks (by sub-phase)

**6.1 Tasks / Regular Tasks**

| Task | Detail |
|------|--------|
| Schema | `tasks.executor_cabinet_id`, template owner cabinet FK |
| Backfill | Map `executor_role_id` → Cabinet via Employment/Template mapping |
| `tasks_service` / router | Enforce mine/team/actions via resolver |
| Regular tasks scheduler | Generate in owner Cabinet |
| Dedupe key | Migrate per ADR-020 amendment |
| Audit | `(person_id, cabinet_id, action)` |
| UI | Task scope policy from effective permissions |
| Flip | Subsystem flag: `TASKS_CABINET_ENFORCED=1` |

**6.2 Events & Telegram**

| Task | Detail |
|------|--------|
| Recipient resolution | Cabinet occupants → User telegram binding |
| Bot auth | Resolver context for bound user |
| Event payload | `cabinet_id` where applicable (ADR-022 direction) |

**6.3 Working Contacts**

| Task | Detail |
|------|--------|
| `working_contacts_routes` | Scope via Cabinet/org policy |
| Remove | `users.unit_id` as sole scope where replaced |

**6.4 Directory Contacts**

| Task | Detail |
|------|--------|
| `contacts_routes` | Cabinet/org predicates |
| Task contour alignment | With 6.1 |

**6.5 Personal UI Shell**

| Task | Detail |
|------|--------|
| Post-login | Accessible Cabinets list |
| Context switch | Active Cabinet session state |
| Terminology | «Личный кабинет» vs Position Cabinet (ADR-007) |

**6.6 Personal File**

| Task | Detail |
|------|--------|
| Verify | Person-bound documents only (ADR-047) |
| **No** Cabinet ownership introduced |

**6.7 HR Import / Canonical**

| Task | Detail |
|------|--------|
| Import | Person/Employment sync; org-unique Position resolution |
| **No** Cabinet operational object import |

**6.8 Employee Documents**

| Task | Detail |
|------|--------|
| Classify | Personal vs professional vs Cabinet function docs |
| Bind function docs | To Cabinet where required |

**6.9 Org Sync / Admin**

| Task | Detail |
|------|--------|
| Admin UI | Position/Cabinet lifecycle, Template config |
| Sync runbooks | Taxonomy vs staffing separation |

### 6. Expected database changes (by sub-phase)

| Sub | Changes |
|-----|---------|
| 6.1 | Task cabinet FKs; indexes; backfill columns |
| 6.2 | Optional delivery log columns |
| 6.3–6.4 | Query changes primarily |
| 6.5 | Optional session/context storage |
| 6.6–6.8 | Minimal if boundary-only |
| 6.9 | Admin config tables if not in Phase 2 |

### 7. Expected backend changes

Subsystem-specific route and service enforcement flip from legacy to resolver; see tasks above. Each sub-phase merges only its scope.

### 8. Expected frontend changes

| Sub | Changes |
|-----|---------|
| 6.1 | Task lists, filters, actions |
| 6.2 | None or notification admin |
| 6.3–6.4 | Contact visibility |
| 6.5 | Cabinet selector, nav |
| 6.6–6.8 | Boundary validation only |
| 6.9 | Admin panels for Position/Cabinet/Template |

### 9. Testing strategy

| Sub | Tests |
|-----|-------|
| Each | Subsystem integration suite green with enforcement flag on |
| 6.1 | Mine/team parity vs shadow baseline; Telegram recipient spot checks |
| All | Rollback flag returns legacy behavior |
| E2E | Pilot user multi-employment flows |

### 10. Rollback strategy

| Step | Action |
|------|--------|
| Per subsystem | Enforcement flag off → legacy guards |
| 6.1 | Dual-read task columns if retained during transition |
| Data | Cabinet FKs nullable during backfill window |
| Order | Roll back in reverse order (6.9 → 6.1) if systemic issue |

### 11. Exit criteria

- [ ] 6.1–6.9 each: enforcement flag on in production; shadow off for that subsystem.
- [ ] Subsystem ADRs amended or implementation notes published.
- [ ] No subsystem uses `users.role_id` as primary authorization input.
- [ ] Audit records `(person_id, cabinet_id)` on operational actions (where applicable).

---

## Phase 7 — Role-Centric Dependency Decommission

| Field | Value |
|-------|-------|
| **Roadmap status** | Not started |
| **Engineering status** | Blocked on Phase 6 |

### 1. Objective

Remove obsolete operational use of `users.role_id`, catalog `position_id`, `users.unit_id` as standalone auth scope, and ROLE-targeted grants as baseline — per roadmap and ADR-051 Phase 5.

### 2. Expected deliverables

- Stop writes to `users.role_id` for operational access (HR Employment replaces «Роль Corpsite» — OPS-029).
- Remove legacy guard branches that read `role_id` as primary input.
- Retire env role allowlists from active code paths.
- Narrow `access_grants` to documented break-glass exceptions.
- `public.roles` retained as Template definition catalog only.
- Deprecation notices on legacy API fields.
- Migration guide for ops: acting via ADR-036 overlay, not role swap.

### 3. Source documents

| Document | Role |
|----------|------|
| [Implementation roadmap § Phase 7](./ARCH-001-implementation-roadmap.md) | Decommission list |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) §10 Phase 5 | User-centric removal |
| [Foundation summary §4](./ARCH-001-foundation-summary.md) | Transitional inventory |
| [OPS-029](../ops/OPS-029-user-create-form-ux-role-source.md) | User create = auth only |

### 4. Preconditions

- Phase 6 exit criteria (all subsystems cut over).
- Break-glass admin policy verified without `role_id=2` hardcode dependency.

### 5. Main implementation tasks

| Task | Detail |
|------|--------|
| Remove `PATCH users role` for ops access | Replace with Employment admin |
| Delete env allowlist reads | `DIRECTOR_ROLE_IDS`, `DIRECTORY_PRIVILEGED_*`, etc. |
| Clean `_enrich_user_context` | Resolver-only enrichment |
| `EmployeeAccountSections` / UI | Remove Platform Role assignment for access |
| Grant hygiene | ROLE-target grants archived |
| Column deprecation | `users.role_id` nullable or documented unused — **no drop until Phase 8** |

### 6. Expected database changes

| Change | Purpose |
|--------|---------|
| Optional: deprecate columns | Mark unused, not drop |
| Grant cleanup migration | Archive obsolete ROLE grants |
| **No drop** of `users`, `roles` tables in Phase 7 | Phase 8+ |

### 7. Expected backend changes

| Area | Change |
|------|--------|
| `app/auth.py` | Legacy enrichment removed |
| All guards | Resolver-only |
| `users_routes.py` | Role patch restricted/removed |
| `platformRoleCatalog` backend | Definition catalog only |

### 8. Expected frontend changes

| Area | Change |
|------|--------|
| User create / employee drawer | Remove «Роль Corpsite» as access control |
| Admin nav | From effective permissions |
| Task scope policy | Remove `role_id==2` heuristics |

### 9. Testing strategy

| Layer | Tests |
|-------|-------|
| Full regression | All modules with role-centric tests updated |
| Negative | No code path reads `users.role_id` for authz (grep CI check) |
| Break-glass | Admin access via exception grants still works |

### 10. Rollback strategy

| Step | Action |
|------|--------|
| Keep | Legacy columns through Phase 7 |
| Rollback | Re-enable legacy enrichment branch via flag (temporary) |
| Data | Role assignments frozen pre-phase — restore from backup if needed |

### 11. Exit criteria

- [ ] Grep/CI rule: no primary `role_id` authorization reads in `app/`.
- [ ] Shadow modes disabled.
- [ ] Ops confirms acting playbook without role swap.
- [ ] Break-glass documented and tested.

---

## Phase 8 — Cleanup / Stabilization

| Field | Value |
|-------|-------|
| **Roadmap status** | Not started |
| **Engineering status** | Blocked on Phase 7 |

### 1. Objective

Remove compatibility shims; finalize runbooks and monitoring; verify invariants in production; close migration program.

### 2. Expected deliverables

- Delete shadow/dual-read code and feature flags.
- Drop or archive deprecated columns (if approved in separate change control).
- Updated runbooks: POSITIONS_SYNC, org structure, enrollment, acting (ADR-036).
- Production invariant checklist signed (ADR-050 I1–I13, ADR-051 R1–R17).
- Monitoring dashboards: resolver errors, empty accessible sets, Person linkage gaps.
- Architecture session: migration program closure minutes.

### 3. Source documents

| Document | Role |
|----------|------|
| [Implementation roadmap § Phase 8](./ARCH-001-implementation-roadmap.md) | Cleanup activities |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) §8.1 | Single pipeline target |
| [Consolidation review](./ARCH-001-foundation-consolidation-review.md) | Invariant reference |

### 4. Preconditions

- Phase 7 exit criteria met.
- Soak period in production with resolver-only auth (≥ agreed duration).

### 5. Main implementation tasks

| Task | Detail |
|------|--------|
| Remove compat flags | `CABINET_ACCESS_SHADOW`, subsystem legacy flags |
| Code deletion | Legacy enrichment, dual-write paths |
| Schema cleanup | Drop deprecated columns (change-controlled) |
| Runbook updates | All ops docs in `docs/ops/` |
| Monitoring | Alerts on resolver failure rate |
| Audit verification | Sample `(person_id, cabinet_id, permission)` trails |
| Program closure | Final report to architecture session |

### 6. Expected database changes

| Change | Purpose |
|--------|---------|
| Drop deprecated columns | `users.role_id`, legacy composite cols — **only after explicit approval** |
| Archive tables | Legacy mapping if no longer needed |
| Index maintenance | Post-cleanup analyze |

### 7. Expected backend changes

| Area | Change |
|------|--------|
| Delete dead code | Shadow, legacy guards, env allowlists |
| Simplify auth pipeline | Single ADR-051 path |
| Test cleanup | Remove obsolete role-centric tests |

### 8. Expected frontend changes

| Area | Change |
|------|--------|
| Remove | Legacy role-based UI gates, compat fields |
| Finalize | Cabinet-centric UX from Phase 6.5 |

### 9. Testing strategy

| Layer | Tests |
|-------|-------|
| Full suite | CI green |
| Invariant probes | Scheduled job: 1:1 Cabinet, Employment→Position |
| Pen test spot | Authz bypass attempts on deprecated endpoints |

### 10. Rollback strategy

| Step | Action |
|------|--------|
| Pre-drop | Backup + tagged release before column drop |
| Rollback | Restore DB from backup; redeploy prior release |
| **Note** | Phase 8 rollback is expensive — require explicit go/no-go |

### 11. Exit criteria

- [ ] Single authorization pipeline per ADR-051 §8.1 in production.
- [ ] No shadow/compat code in main branch.
- [ ] Runbooks current.
- [ ] Monitoring and alerts operational.
- [ ] Architecture session closure recorded.

---

## Implementation risks

| ID | Risk | Phase | Mitigation (engineering) |
|----|------|-------|--------------------------|
| IR1 | Build before ADR approval | 1–2 | M1 gate; draft labels on branches |
| IR2 | Schema names diverge from approved ADR-050 pack | 2 | Schema review against Accepted ADR only |
| IR3 | Incomplete mapping → wrong Cabinet on retarget | 2–3 | Audit reports; block Phase 3 until 100% mapped |
| IR4 | Resolver performance on hot path | 4–5 | Cache with TTL; benchmark before shadow prod |
| IR5 | Shadow log volume | 5 | Sampled logging; rate limits |
| IR6 | Task backfill errors | 6.1 | Shadow period; nullable FKs; rollback flag |
| IR7 | Telegram duplicate/missed notifications | 6.2 | Recipient diff tool during shadow |
| IR8 | Premature column drop | 8 | Separate change control; backup |
| IR9 | CI still testing role-centric paths | 7–8 | Grep gate; update tests with each sub-phase |
| IR10 | Person linkage gaps at cutover | 3–6 | Pre-cutover report; block user if empty set |

*Architectural risk IDs R1–R12 remain in [implementation roadmap §6](./ARCH-001-implementation-roadmap.md).*

---

## Validation checklist before entering next phase

Use this checklist at each phase boundary. **All items must pass** before starting the next phase.

### Enter Phase 2 (from Phase 1)

- [ ] ADR-050 **Accepted** (written record)
- [ ] ADR-051 **Accepted** (written record)
- [ ] Engineering kickoff scheduled
- [ ] Staging DB backup policy confirmed
- [ ] No production migrations merged under Proposed-only authority

### Enter Phase 3 (from Phase 2)

- [ ] M2 exit criteria (§ Phase 2) complete
- [ ] Mapping audit signed
- [ ] 1:1 Position↔Cabinet automated check green
- [ ] Legacy HR flows still functional

### Enter Phase 4 (from Phase 3)

- [ ] M3 exit criteria complete
- [ ] Person linkage threshold met
- [ ] Active assignments resolve to Cabinet id in SQL spot check
- [ ] New assignment API rejects catalog-only staffing

### Enter Phase 5 (from Phase 4)

- [ ] M4 exit criteria complete
- [ ] Resolver fixture suite green
- [ ] JWT payload unchanged (automated assertion)
- [ ] No guard uses resolver as sole authority

### Enter Phase 6 (from Phase 5)

- [ ] M5 exit criteria complete
- [ ] Parity reports for Tasks, Directory, Admin signed
- [ ] ADR-049 published (before 6.1)
- [ ] Shadow soak period complete

### Enter Phase 6.x+1 (within Phase 6)

- [ ] Sub-phase 6.x enforcement flag stable ≥ soak period
- [ ] Sub-phase 6.x rollback tested
- [ ] Subsystem tests green

### Enter Phase 7 (from Phase 6)

- [ ] All 6.1–6.9 exit criteria complete
- [ ] No production subsystem on legacy enforcement
- [ ] Break-glass path documented without `role_id=2`

### Enter Phase 8 (from Phase 7)

- [ ] M7 exit criteria complete
- [ ] Grep/CI: no primary `role_id` authz reads
- [ ] Production soak with resolver-only complete

### Program complete (after Phase 8)

- [ ] M8 exit criteria complete
- [ ] Architecture session closure minutes
- [ ] IMPLEMENTATION_PLAN marked complete in program tracker

---

## Appendix A — Consistency review

**Review question:** Does IMPLEMENTATION_PLAN introduce architectural decisions beyond the existing baseline?

**Method:** Compare each phase against [ARCH-001](./ARCH-001-position-permission-model.md), [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md), [ADR-051](../adr/ADR-051-cabinet-access-resolution.md), and [implementation roadmap](./ARCH-001-implementation-roadmap.md). Flag any new entities, invariants, sequencing changes, or ADR status changes.

| Check | Result | Evidence |
|-------|--------|----------|
| New core entities introduced | **No** | Same entities as ARCH-001: Person, Employment, Position, Cabinet, Template, Platform User |
| Phase sequencing changed | **No** | Phases 0–8 match roadmap §3 exactly |
| ADR-050/051 approved by this plan | **No** | Phase 1 explicitly requires session approval; milestones show Proposed |
| ARCH-001 modified | **No** | Read-only reference |
| Resolver semantics redefined | **No** | Union, acting additive, vacancy — per ADR-051 |
| User-centric role as end state | **No** | Phase 7 decommission aligns with foundation summary §4 |
| SQL/API/UI specified as architecture | **No** | Engineering expectations only; contracts remain in ADRs |
| Subsystem order changed | **No** | 6.1–6.9 matches roadmap table |
| JWT permissions introduced | **No** | Phase 4/5 explicitly forbid |
| Employee as Employment truth | **No** | Phase 3 aligns Employee as shell per assessments |
| Slot entity | **No** | Not mentioned |
| New invariants | **No** | Engineering checklist E1–E10 operationalize existing ADR invariants |

**Conclusion:** IMPLEMENTATION_PLAN is a **translation layer** only. It packages engineering work (migrations, services, flags, tests, rollbacks) around decisions already fixed in the roadmap and ADR-050/051. Table names cited from [positions-org-structure assessment §9](./ARCH-001-positions-org-structure-assessment.md) are **engineering hints from an existing assessment**, not new architecture — final schema follows **Accepted ADR-050** engineering specifications.

**Explicit non-actions of this plan:**

- Does not accept or reject ADR-050 / ADR-051
- Does not add entities, Slot, Platform Role, or User-attached permissions
- Does not reorder consumer migrations
- Does not specify business policy at vacancy (ARCH-001 §4.7.2)

---

## Appendix B — Related documents

| Document | Relationship |
|----------|--------------|
| [ARCH-001-implementation-roadmap.md](./ARCH-001-implementation-roadmap.md) | **Authority for sequencing** |
| [ARCH-001-foundation-summary.md](./ARCH-001-foundation-summary.md) | Invariants and transitional inventory |
| [ARCH-001-assessment-program.md](./ARCH-001-assessment-program.md) | Tier 2 assessments parallel to Phase 1 |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) | Phase 2–3 contract |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | Phase 4–7 contract |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 1.0 | Initial engineering implementation plan from roadmap Phases 0–8 |
