# ARCH-001 — Implementation Roadmap

## Document metadata

| Field | Value |
|-------|-------|
| Status | **Active** — 2026-07-03 |
| Type | Architecture implementation sequencing (not an ADR, not an assessment) |
| Baseline | [ARCH-001 v0.5 — Position Cabinet Architecture](./ARCH-001-position-permission-model.md) |
| Governance | [ARCHITECTURE_GOVERNANCE.md](./ARCHITECTURE_GOVERNANCE.md) |
| Implementation contracts | [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md), [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) (**Proposed**) |
| Foundation inputs | [Foundation summary](./ARCH-001-foundation-summary.md), [Consolidation review](./ARCH-001-foundation-consolidation-review.md), [Assessment program](./ARCH-001-assessment-program.md) |

**Scope:** recommended **sequence** for implementing the Position Cabinet architecture already defined in authoritative documents. This roadmap **does not** change architectural decisions, approve Proposed ADRs, or specify SQL, API, or UI implementation.

---

## 1. Executive Summary

The **architecture foundation phase is complete**. ARCH-001, five foundation assessments, the foundation summary, and consolidation review confirm that the baseline is sufficient and coherent. Implementation contracts [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) (org-unique Position + Position Cabinet) and [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) (Cabinet Access Resolver) are **authored (Proposed)**.

**Production implementation is gated** by architecture session **approval** of ADR-050 and ADR-051. Until that gate closes, engineering must not treat Proposed ADRs as approved build authority, bind operational logic to catalog `(org_unit_id, position_id)` composites, or cut over authorization from `users.role_id`.

This roadmap closes the architecture phase as a **sequencing bridge**: it tells engineering and Tier 2 consumer assessments **in what order** to proceed after approval, without redefining the model.

| Dimension | Status |
|-----------|--------|
| Architecture foundation | **Complete** (Phase 0) |
| Implementation contracts | **Proposed** — approval required (Phase 1) |
| Tier 2 consumer assessments | **May proceed** in parallel with Phase 1; use this roadmap as sequencing context |
| Production cutover | **Blocked** until Phases 1–4 complete |

---

## 2. Preconditions

Implementation work under this roadmap **must not start** until all preconditions below are satisfied.

| # | Precondition | Rationale |
|---|--------------|-----------|
| P1 | **[ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) approved** (Proposed → Accepted) | Position/Cabinet entity and lifecycle contract is build authority |
| P2 | **[ADR-051](../adr/ADR-051-cabinet-access-resolution.md) approved** (Proposed → Accepted) | Access resolver and effective-permission contract is build authority |
| P3 | **[ARCH-001](./ARCH-001-position-permission-model.md) remains baseline** | No implementation may amend or contradict the domain model |
| P4 | **[ARCHITECTURE_GOVERNANCE](./ARCHITECTURE_GOVERNANCE.md) respected** | Person ≠ permissions; User = auth only; permissions follow Employment |
| P5 | **Consumer migrations do not redefine foundation** | Tier 2 assessments and subsystem ADRs consume Position, Employment, Cabinet, resolver — they do not invent alternate semantics |
| P6 | **Person materialization viable** (ADR-048) | Resolver requires Person from Platform User linkage on operational accounts |
| P7 | **Subsystem transition ADRs identified before cutover** | e.g. ADR-049 (Tasks), ADR-042 B5/E1 (auth/me, visibility) — consumer-specific, not baseline |

**Note:** Tier 2 **assessments** (read-only analysis) may run **before** P1/P2 approval. Tier 2 **implementation** follows Phases 2–6 of this roadmap after approval.

---

## 3. Phase Roadmap

### Phase 0 — Architecture Foundation Complete

| | |
|---|---|
| **Status** | **Done** |
| **Goal** | Establish baseline, assess fit, author implementation contracts |

**Deliverables (complete):**

| Artifact | Role |
|----------|------|
| [ARCH-001](./ARCH-001-position-permission-model.md) | Baseline domain model |
| [ARCHITECTURE_GOVERNANCE](./ARCHITECTURE_GOVERNANCE.md) | Baseline principles |
| [Assessment program](./ARCH-001-assessment-program.md) | Queue and rules |
| Tier 0 + Tier 1 assessments (Tasks, positions-org, personnel-employment, access-rbac, platform-user-identity) | Fit/gap analysis |
| [Foundation summary](./ARCH-001-foundation-summary.md) | Consolidated conclusions |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) | Position + Cabinet implementation contract (**Proposed**) |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | Access resolver contract (**Proposed**) |
| [Consolidation review](./ARCH-001-foundation-consolidation-review.md) | Corpus consistency verified |

**Exit criteria:** foundation assessments complete; no baseline revision required; ADR-050/051 authored.

---

### Phase 1 — Approval Gate

| | |
|---|---|
| **Status** | **Pending** |
| **Goal** | Move ADR-050 and ADR-051 from **Proposed** to **approved** status before implementation |

**Activities (architecture session — not engineering):**

1. Review ADR-050 against ARCH-001 and foundation assessments.
2. Review ADR-051 against ADR-050 and access-rbac assessment.
3. Confirm ARCH-001 acceptance path (Draft → Accepted) and governance alignment.
4. Record approval decisions in ADR decision logs (status change is session action — **this roadmap does not approve ADRs**).

**Parallel work allowed:**

- Tier 2 consumer-subsystem **assessments** (`events-telegram`, `working-contacts`, …).
- Implementation **planning** and spike design **against Proposed ADRs** — clearly labeled draft until P1 closes.

**Exit criteria:** ADR-050 and ADR-051 **Approved/Accepted**; architecture session minutes recorded.

**Hard stop:** no Phase 2+ production schema binding, resolver enforcement, or consumer cutover until exit criteria met.

---

### Phase 2 — Position / Cabinet Model

| | |
|---|---|
| **Status** | **Not started** (blocked on Phase 1) |
| **Goal** | Introduce org-unique **Position** and 1:1 **Position Cabinet** per [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) |

**Architectural outcomes (conceptual — detail in ADR-050 and engineering program):**

1. Org-unique Position entity — distinct from global title catalog (`public.positions` as taxonomy reference only).
2. Position Cabinet created **atomically** with Position (strict 1:1).
3. Permission Template configuration stored **inside** Cabinet.
4. Legacy `(org_unit_id, catalog position_id)` → new Position **mapping** maintained for transition.
5. Title dedup / ADR-046 normalization applied **before or during** mapping — no in-place global catalog rename blast radius.

**Aligns with ADR-050 migration Phases 1–2** (model introduction + data mapping).

**Exit criteria:** stable org-unique Position and Cabinet identities; mapping from legacy catalog pairs; vacancy queryable at Position level.

**Must not:** implement resolver enforcement; retarget Employment FK before mapping stable; treat catalog `position_id` as ARCH-001 Position.

---

### Phase 3 — Employment Retargeting

| | |
|---|---|
| **Status** | **Not started** (blocked on Phase 2) |
| **Goal** | Move Employment (`person_assignments`) from `(org_unit_id + catalog position_id)` proxy to **org-unique Position** FK |

**Architectural outcomes:**

1. `person_assignments` references org-unique Position — sole staffing truth for Employment episodes.
2. Employee operational snapshot **derives from or aligns with** Employment (not independent staffing truth).
3. Vacancy derived from absence of active Employment on Position.
4. New Employments **blocked** from binding to catalog composite as staffing identity.
5. Person materialization (ADR-048) sufficient for resolver input paths.

**Aligns with ADR-050 migration Phase 3** (Employment retarget).

**Exit criteria:** active Employments resolve to org-unique Position → Cabinet id; dual-write with legacy composite ended or read-only.

**Must not:** open Cabinet access enforcement on catalog FKs; conflate Employee row with Employment truth.

---

### Phase 4 — Cabinet Access Resolver

| | |
|---|---|
| **Status** | **Not started** (blocked on Phase 3) |
| **Goal** | Implement [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) **read path** and effective permission calculation |

**Architectical outcomes:**

1. **Cabinet Access Resolver** computes `Accessible Cabinets[]` from Person + active Employments (+ acting overlays when available).
2. **Effective Permission Set** = deterministic **union** of Permission Template permissions across accessible Cabinets.
3. Resolver outputs available to session/auth consumer (ADR-042 B5 direction) **alongside** legacy fields — not yet authoritative for enforcement.
4. JWT remains auth-only — no effective permissions in token.
5. Acting overlay (ADR-036) integrated when HR read model exists — additive Cabinets only.

**Aligns with ADR-051 migration Phase 1** (resolver read path).

**Exit criteria:** resolver produces correct accessible set and effective permissions for representative Person fixtures; Person linkage on operational users.

**Must not:** cut over route guards to resolver-only; mutate `users.role_id` for operational access; embed permissions in JWT.

---

### Phase 5 — Dual-Read Compatibility

| | |
|---|---|
| **Status** | **Not started** (blocked on Phase 4) |
| **Goal** | Run cabinet-based access **alongside** existing user/role/employee paths for verification |

**Architectural outcomes:**

1. **Shadow mode:** legacy authorization decision and resolver decision computed in parallel; divergences logged.
2. Legacy paths remain **authoritative** for user-visible behavior until subsystem cutover.
3. Env role allowlists and `access_grants` documented as **legacy policy debt** mapped to Template equivalents for comparison.
4. `/auth/me` exposes `accessible_cabinets[]` and effective permissions **in addition to** transitional role fields.
5. Acting via `users.role_id` swap **explicitly forbidden** in operations policy.

**Aligns with ADR-051 migration Phase 2** (shadow enforcement) and access-rbac assessment Phase 0 shadow pattern.

**Exit criteria:** shadow run demonstrates acceptable parity per subsystem **or** documented intentional differences before cutover; no silent divergence.

**Must not:** flip enforcement globally without subsystem-specific acceptance; remove legacy paths before Phase 6 per-subsystem cutover.

---

### Phase 6 — Consumer Subsystem Migration

| | |
|---|---|
| **Status** | **Not started** (blocked on Phase 5) |
| **Goal** | Migrate operational consumers to Cabinet-centric ownership and authorization **in dependency order** |

Migrate **one subsystem at a time** — flip enforcement from legacy to resolver after shadow parity for that subsystem.

| Order | Subsystem | Primary architectural shift | Key ADR / assessment |
|-------|-----------|----------------------------|----------------------|
| 6.1 | **Tasks / Regular Tasks** | Executor/owner → Position Cabinet; mine = accessible Cabinets union | ADR-049, ADR-023, ADR-020, ADR-024; [tasks assessment](./ARCH-001-task-subsystem-assessment.md) |
| 6.2 | **Events & Telegram** | Recipients from Cabinet → occupants; delivery still Platform User | Tier 2 assessment; ADR-022 amendment |
| 6.3 | **Working Contacts** | Read model scoped via Cabinet/org policy, not `users.unit_id` alone | Tier 2 assessment |
| 6.4 | **Directory Contacts** | Contact predicates vs Cabinet/org scope | Tier 2 assessment |
| 6.5 | **Personal UI Shell** | Post-login: accessible Cabinets, active context; «личный кабинет» ≠ Position Cabinet | ADR-007; Tier 2 assessment |
| 6.6 | **Personal File** | Validate Person-bound exception — no Cabinet drift | ADR-047; Tier 2 assessment |
| 6.7 | **HR Import / Canonical** | HR truth boundaries; Person/Employment sync — not Cabinet ownership | Tier 2 assessment |
| 6.8 | **Employee Documents** | Personal vs professional vs Cabinet function documents | Tier 2 assessment |
| 6.9 | **Org Sync / Admin** | Reference data; Position/Cabinet config administration | Tier 2 assessment |

**Cross-cutting during Phase 6:**

- Directory RBAC and personnel visibility (ADR-042 E1) migrate with access-rbac assessment guidance.
- `/auth/me` (ADR-042 B5) transitions from role-centric to cabinet-centric claims per subsystem readiness.
- Admin/sysadmin gates migrate from `role_id=2` heuristics to platform policy + exception grants.

**Aligns with ADR-051 migration Phase 3** (enforcement cutover per subsystem) and ADR-050 migration Phases 4–5 (directory semantics + consumer preparation).

**Exit criteria:** each subsystem enforces authorization from resolver; operational objects bind to Cabinet where domain requires; subsystem ADR amendments published.

**Must not:** big-bang cutover all subsystems at once; migrate tasks before Cabinet FKs exist; redefine resolver semantics in consumer ADRs.

---

### Phase 7 — Role-Centric Dependency Decommission

| | |
|---|---|
| **Status** | **Not started** (blocked on Phase 6) |
| **Goal** | Remove `users.role_id`, `employee_id`, catalog `position_id`, and related fields as **operational authorization/ownership keys** where obsolete |

**Architectural outcomes:**

1. **`users.role_id`** — no longer written for operational access; not read as primary authorization input.
2. **`public.roles`** — Template **definition catalog** only; not assigned to User as operational identity.
3. **`users.unit_id`** — not standalone directory scope carrier; scope from Employment/Cabinet org context.
4. **Catalog `position_id`** — not used for staffing truth, visibility targets, or permission resolution.
5. **`access_grants` on ROLE/USER** — narrowed to documented break-glass exceptions (ARCH-001 §15.0).
6. **Env role allowlists** (`DIRECTOR_ROLE_IDS`, etc.) — retired; policy encoded in Cabinet Templates or org policy.
7. **Employee** — operational shell only; not Employment truth or access carrier.

**Aligns with ADR-051 migration Phase 5** and foundation summary §4 transitional decommission list.

**Exit criteria:** no production authorization path depends on user-centric role assignment; shadow modes removed; legacy fields deprecated or repurposed auth-only metadata.

**Must not:** remove break-glass before admin Cabinet/grant policy exists; delete legacy columns before all consumers migrated.

---

### Phase 8 — Cleanup / Stabilization

| | |
|---|---|
| **Status** | **Not started** (blocked on Phase 7) |
| **Goal** | Remove compatibility paths; verify invariants; finalize operational readiness |

**Activities:**

1. Remove dual-read / shadow code paths and compatibility shims.
2. Update ops runbooks (positions sync, org structure, enrollment, acting playbook).
3. Verify mandatory invariants (ADR-050 I1–I13, ADR-051 R1–R17, foundation summary §3) in production behavior.
4. Audit trail shape stable: `(person_id, cabinet_id, permission, timestamp)` on operational actions.
5. Monitoring for resolver failures, empty accessible sets, Person linkage gaps.
6. Architecture session: close migration program; record technical debt retirement.

**Exit criteria:** single authorization pipeline per ADR-051 §8.1; no user-centric anti-patterns in active code paths; runbooks current.

---

## 4. Dependency Graph

### Primary implementation chain

```text
ARCH-001 (baseline)
        │
        ▼
ADR-050 (Position + Cabinet — approval gate)
        │
        ▼
ADR-051 (Cabinet Access Resolver — approval gate)
        │
        ▼
Position / Cabinet implementation          ← Phase 2
        │
        ▼
Employment retargeting                   ← Phase 3
        │
        ▼
Cabinet Access Resolver (read path)      ← Phase 4
        │
        ▼
Dual-read / shadow compatibility       ← Phase 5
        │
        ▼
Consumer migrations (ordered)              ← Phase 6
        │
        ▼
Role-centric decommission                ← Phase 7
        │
        ▼
Cleanup / stabilization                  ← Phase 8
```

### Parallel tracks

```text
Phase 0 ──complete──► Phase 1 (approval)
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   Tier 2 assessments   Planning/spikes   ARCH-001 acceptance
   (read-only)          (draft only)      (governance)
         │                 │
         └────────┬────────┘
                  ▼
         Informs Phase 6 ordering
                  │
         (after Phase 1 closes)
                  ▼
         Phases 2 → 8 sequential
```

**Hard sequencing rules:**

- Phase 2 before Phase 3 (Cabinet ids before Employment FK retarget).
- Phase 3 before Phase 4 (Employments must reference org-unique Position for resolver).
- Phase 4 before Phase 5 (resolver must exist before shadow).
- Phase 5 before Phase 6 cutover per subsystem (shadow before flip).
- Phase 6 before Phase 7 (consumers before legacy key removal).
- Phase 7 before Phase 8 (decommission before cleanup).

---

## 5. Non-Goals

This roadmap **does not**:

| Non-goal | Where defined instead |
|----------|----------------------|
| Define SQL migrations, table names, or indexes | Engineering implementation program post-approval |
| Define API contracts or `/auth/me` response shapes | ADR-042 B5, consumer ADRs |
| Define UI details (cabinet selector, drawers) | ADR-007, Personal UI Shell assessment, OPS-029 |
| Change [ARCH-001](./ARCH-001-position-permission-model.md) baseline | Architecture session amendment only |
| Change [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) or [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | ADR amendment process |
| Approve Proposed ADRs by itself | Phase 1 requires explicit architecture session |
| Replace Tier 2 assessments | Assessments remain required per [assessment program](./ARCH-001-assessment-program.md) |
| Specify process policy at vacancy (regular tasks, escalations) | Business Policy (ARCH-001 §4.7.2) |
| Author ADR-049 or other consumer ADRs | Separate ADR tasks |

---

## 6. Risk Register

| ID | Risk | Impact | Mitigation |
|----|------|--------|------------|
| R1 | **Premature implementation before ADR approval** | Build on draft contracts; rework on approval changes | Phase 1 hard gate; label pre-approval work as draft/spike only |
| R2 | **Reintroducing User → Role model** | Baseline violation; acting/совместительство broken | Code review gate; no new `role_id` dependencies; OPS-029 alignment |
| R3 | **Treating catalog `position_id` as ARCH-001 Position** | Wrong resolver forever; rename blast radius | Phase 2 mapping; block Employment retarget until org-unique ids stable |
| R4 | **Treating Employee as Employment** | Dual truth; terminate conflates access and account | ADR-042/ADR-041; Employment = `person_assignments` only |
| R5 | **Mixing authentication and authorization** | Permissions in JWT; stale claims | ADR-013 + ADR-051 R12; resolver post-auth only |
| R6 | **Breaking Tasks during dual-read** | Wrong mine/team scope; missed notifications | Phase 5 shadow mandatory; ADR-049 coexistence; per-subsystem flip |
| R7 | **Losing audit attribution during migration** | Compliance gap | Preserve `(person_id, cabinet_id)` in audit; initiator Person exception (ADR-023) |
| R8 | **Big-bang cutover** | Outage, lockout | Phased Phase 6; break-glass grants until admin policy migrated |
| R9 | **Acting via `users.role_id` swap** | Lost primary cabinet context | ADR-036 overlay + ADR-051; ops playbook ban |
| R10 | **Tier 2 assessment redefines foundation** | Corpus contradiction | Assessment program rules; consolidation review guardrails |
| R11 | **Parallel role + cabinet enforcement drift** | Silent wrong access | Shadow logging; no flip without parity sign-off |
| R12 | **Person linkage incomplete** | Empty accessible set for valid users | ADR-048 gate in Phase 3–4 |

---

## 7. Acceptance Criteria

This roadmap is **complete** when:

| Criterion | Met |
|-----------|-----|
| Implementation sequence is clear across Phases 0–8 | **Yes** |
| Approval gates are explicit (Phase 1; preconditions P1–P2) | **Yes** |
| Dependency order is documented (§4) | **Yes** |
| No new architecture introduced | **Yes** — sequences existing ADR-050/051 and assessment conclusions only |
| Tier 2 assessments can use roadmap as sequencing context | **Yes** — parallel track in §4 |
| Non-goals bound scope (§5) | **Yes** |
| Risks documented (§6) | **Yes** |

**Program-level exit (architecture phase closed for implementation):** Phase 1 approval recorded → engineering may enter Phase 2 under approved ADR-050/051.

---

## 8. Related documents

| Document | Relationship |
|----------|--------------|
| [ARCH-001-position-permission-model.md](./ARCH-001-position-permission-model.md) | Baseline — unchanged by this roadmap |
| [ARCHITECTURE_GOVERNANCE.md](./ARCHITECTURE_GOVERNANCE.md) | Mandatory principles |
| [ARCH-001-foundation-summary.md](./ARCH-001-foundation-summary.md) | Foundation conclusions and readiness |
| [ARCH-001-foundation-consolidation-review.md](./ARCH-001-foundation-consolidation-review.md) | Corpus consistency |
| [ARCH-001-assessment-program.md](./ARCH-001-assessment-program.md) | Tier 2+ assessment queue |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) | Phase 2–3 authority |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | Phase 4–7 authority |
| [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) | Engineering execution plan per roadmap phase |
| Individual `ARCH-001-*-assessment.md` | Subsystem detail for Phase 6 |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 1.0 | Initial implementation roadmap — foundation phase close, sequencing bridge to engineering |
