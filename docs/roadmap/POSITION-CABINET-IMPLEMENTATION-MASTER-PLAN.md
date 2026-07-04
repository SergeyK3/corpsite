# Position Cabinet — Implementation Master Plan

## Status

**Active (planning)** — 2026-07-04

Primary execution roadmap for the remaining Position Cabinet program — from **Reviewed** organizational policy through **production cutover**. **Planning document only** — no runtime effect, no architecture amendment, no policy redesign.

| Field | Value |
|-------|-------|
| Supersedes (for execution sequencing) | Informal backlog items; does **not** amend [ARCH-001 Implementation Roadmap](../architecture/ARCH-001-implementation-roadmap.md) phases 0–8 |
| Architecture baseline (frozen) | [ARCH-001](../architecture/ARCH-001-position-permission-model.md), [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md), [ADR-051](../adr/ADR-051-cabinet-access-resolution.md), [ADR-053](../adr/ADR-053-permission-template-binding-model.md) — all **Accepted** |
| Policy baseline (ratification pending) | [ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md), [ACCESS-002](../access/ACCESS-002-organizational-management-authority-model.md) — **Reviewed** |
| Active governance program | [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) |
| Near-term ops gate | [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) — **Blocked** |

---

## 1. Current state

### 1.1. Architecture — complete

| Artifact | Status | Role |
|----------|--------|------|
| [ARCH-001](../architecture/ARCH-001-position-permission-model.md) | **Accepted** | Domain baseline |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) | **Accepted** | Position + Cabinet entity contract |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | **Accepted** | Cabinet Access Resolver contract |
| [ADR-053](../adr/ADR-053-permission-template-binding-model.md) | **Accepted** | Permission Template binding model |

**Architecture Design** for the Position Cabinet foundation and Organizational Policy Layer is **closed**. **Architecture Freeze** remains in effect. No architectural blockers identified for policy ratification or continued engineering on accepted contracts.

### 1.2. Organizational policy — reviewed, not approved

| Document | Status | Effect today |
|----------|--------|--------------|
| [ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md) | **Reviewed** | Defines permission domains and contour matrix; **no** approved rows; **no** OPS-030 authority |
| [ACCESS-002](../access/ACCESS-002-organizational-management-authority-model.md) | **Reviewed** | Defines management responsibilities; **no** runtime or OPS authority |
| [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) | **Active (planning)** | Governs Reviewed → Approved transition |

Policy documents are **architecturally valid** but **organizationally unratified**. **Reviewed** does not unblock data execution or enforcement cutover.

### 1.3. Implementation — partially complete

Engineering progress within [ARCH-001 Implementation Roadmap](../architecture/ARCH-001-implementation-roadmap.md) **Phase 2** (Position / Cabinet model) and ADR-053 Phase 2.6:

| Sub-phase | Scope | Status |
|-----------|-------|--------|
| **2.1–2.2** | Org-unique Position, Cabinet, Permission Template schema; mapping backfill | **Complete** |
| **2.3–2.4** | Cabinet Access Resolver read path; shadow hook (`CABINET_ACCESS_SHADOW_MODE`) | **Complete** |
| **2.5** | Shadow observation; binding gap analysis → ADR-053 | **Complete** |
| **2.6a** | `access_role_id`, `permission_template_contour_rule`, backfill mechanism, validation SQL | **Complete (engineering)** |
| **2.6b** | Approved contour rules → production template binding | **Blocked** |

Downstream roadmap phases remain **not started** or **incomplete**:

| ARCH-001 phase | Status |
|----------------|--------|
| Phase 2 (Cabinet model) | **In progress** — binding incomplete until 2.6b |
| Phase 3 (Employment retargeting) | **Not started** |
| Phase 4 (Resolver read path) | **Partially delivered** (2.3–2.4); full program incomplete |
| Phase 5 (Dual-read / shadow) | **Partially delivered** — shadow hook exists; subsystem parity program not started |
| Phase 6 (Consumer migration) | **Not started** |
| Phase 7 (Role-centric decommission) | **Not started** |
| Phase 8 (Cleanup) | **Not started** |

**Enforcement authority:** legacy path (`access_grants`, `users.role_id`, user-centric management edges) remains **authoritative** for all user-visible behaviour.

### 1.4. Current blockers

| Blocker | Owner | Unblocks |
|---------|-------|----------|
| ACCESS-001 not **Approved** | Organizational ratification ([ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) Track B) | OPS-030, Phase 2.6b |
| ADR-053 **AC3 Pending** | WP-X3 after ACCESS-001 **Approved** | Phase 2.6b production backfill |
| No `policy_status=approved` rows in ACCESS-001 §7 | WP-B4, WP-B7 | OPS-030 contour rule inserts |
| Employment FK still on catalog composite | ARCH-001 Phase 3 | Resolver enforcement cutover (ADR-051 §10 Phase 3) |
| Subsystem consumer ADRs not amended | Per-subsystem programs | Phase 6 cutover |
| ACCESS-002 not **Approved** | Ratification Track A | Future management-authority implementation only — **does not** block Phase 2.6b |

---

## 2. Program phases

The remaining journey is organized into **governance**, **binding**, **foundation completion**, **shadow**, **cutover**, and **decommission** tiers. Phase labels here are **program phases** (this document); they map to ARCH-001 / ADR-051 / ADR-053 phase numbers in §2.2.

### Tier G — Governance (active now)

#### Phase G1 — Policy Ratification

| | |
|---|---|
| **Goal** | Advance ACCESS-001 and ACCESS-002 from **Reviewed** to **Approved** |
| **Program** | [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) |
| **Authority** | Ops + HR + executive stakeholders — not engineering |
| **Runtime effect** | **None** |

Two orthogonal tracks (ACCESS-001 permissions, ACCESS-002 management responsibilities) with cross-layer touchpoints at shared contours (WP-X1).

#### Phase G2 — ADR-053 AC3 closure

| | |
|---|---|
| **Goal** | Formal sign-off that ops mapping annex exists and is approved |
| **Output** | AC3 recorded **Closed**; OPS-030 status → Ready for execution |
| **Dependency** | ACCESS-001 **Approved** + §7 approved rows (minimum: HR-service contour for MVP) |

AC3 is the **governance output** of ratification Track B (WP-X3), not a separate policy design activity.

---

### Tier B — Template binding (legacy enforcement maintained)

#### Phase B1 — OPS-030 preparation

| | |
|---|---|
| **Goal** | Complete runbook, verify production contour IDs, schedule ops window |
| **Artifact** | [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) — steps 1–2 |
| **Enforcement** | Legacy unchanged |

#### Phase B2 — Phase 2.6b production binding

| | |
|---|---|
| **Goal** | Insert approved contour rules; apply backfill; populate `permission_template.access_role_id` |
| **Artifact** | OPS-030 steps 2–4 |
| **Enforcement** | **Legacy unchanged** — ADR-053 I8, AC2 |

#### Phase B3 — Post-bind shadow observation

| | |
|---|---|
| **Goal** | Observe shadow parity improvement for bound contours; document residual mismatches |
| **Artifact** | OPS-030 step 5; validation SQL review |
| **Enforcement** | Legacy unchanged; shadow diagnostic only |

**Tier B completes** ADR-053 Phase 2.6 and ARCH-001 Phase 2 binding work. Templates move from unmapped to ops-approved baseline binding where policy permits.

---

### Tier F — Foundation completion

#### Phase F1 — Employment retargeting

| | |
|---|---|
| **Goal** | Retarget `person_assignments` from catalog composite to org-unique Position FK |
| **Maps to** | ARCH-001 Phase 3; ADR-050 migration Phase 3 |
| **Prerequisite** | Stable org-unique Position/Cabinet identities (Phase 2 structural work complete) |
| **Enforcement** | Legacy |

#### Phase F2 — Resolver program completion

| | |
|---|---|
| **Goal** | Complete Cabinet Access Resolver read path for all employment and acting paths |
| **Maps to** | ARCH-001 Phase 4; ADR-051 §10 Phase 1 |
| **Prerequisite** | Phase F1 (or stable dual-read from catalog mapping during transition) |
| **Enforcement** | Legacy; resolver exposed alongside legacy in `/auth/me` direction (ADR-042 B5) |

---

### Tier S — Shadow validation program

#### Phase S1 — Subsystem shadow parity

| | |
|---|---|
| **Goal** | Run legacy vs resolver decisions in parallel per subsystem; log and classify divergence |
| **Maps to** | ARCH-001 Phase 5; ADR-051 §10 Phase 2 |
| **Prerequisite** | Phase B3 (binding baseline populated); Phase F2 (resolver outputs meaningful codes) |
| **Enforcement** | Legacy authoritative; shadow diagnostic |

#### Phase S2 — Parity sign-off per subsystem

| | |
|---|---|
| **Goal** | Document acceptable parity or intentional differences before any enforcement flip |
| **Output** | Subsystem readiness record per consumer |
| **Gate** | Required before Phase C1 cutover for that subsystem |

---

### Tier C — Production cutover

#### Phase C1 — Subsystem enforcement cutover

| | |
|---|---|
| **Goal** | Flip enforcement from legacy to resolver **one subsystem at a time** |
| **Maps to** | ARCH-001 Phase 6; ADR-051 §10 Phase 3 |
| **Order (recommended)** | Tasks → visibility/directory → admin gates → personnel admin → remaining consumers per [ARCH-001 roadmap §Phase 6](../architecture/ARCH-001-implementation-roadmap.md) |
| **Prerequisite** | Phase S2 sign-off for target subsystem; consumer ADR amendments (ADR-049, ADR-042 B5/E1, ADR-023, …) |

#### Phase C2 — Acting overlay integration

| | |
|---|---|
| **Goal** | Wire ADR-036 acting into resolver; forbid role-swap acting |
| **Maps to** | ADR-051 §10 Phase 4 |
| **Prerequisite** | Phase C1 progress on core access paths; HR acting read model operational |

#### Phase C3 — Atomic permission expansion (future ADR)

| | |
|---|---|
| **Goal** | Move from single-code transitional binding to Template atomic permissions |
| **Maps to** | ADR-053 target state; ADR-051 §5.2 step 2 |
| **Prerequisite** | Separate ADR; not required for Phase 2.6 completion |
| **Note** | Out of near-term scope; tracked as architectural follow-on |

---

### Tier D — Decommission

#### Phase D1 — User-centric authorization decommission

| | |
|---|---|
| **Goal** | Stop `users.role_id` as operational access input; narrow `access_grants` to exceptions |
| **Maps to** | ARCH-001 Phase 7; ADR-051 §10 Phase 5 |
| **Prerequisite** | Phase C1 complete for all critical subsystems |

#### Phase D2 — Cleanup and stabilization

| | |
|---|---|
| **Goal** | Remove shadow/dual-read shims; finalize runbooks; verify invariants |
| **Maps to** | ARCH-001 Phase 8 |

---

### Parallel track — Management authority (orthogonal)

#### Phase M1 — Management authority implementation

| | |
|---|---|
| **Goal** | Implement Cabinet-anchored management scope from ACCESS-002 approved responsibilities |
| **Prerequisite** | ACCESS-002 **Approved**; contour responsibility matrix (WP-A7); future OPS runbook |
| **Does not block** | Tiers B–D on the ACCESS-001 / ADR-053 track |
| **Enforcement** | Separate consumer program (tasks, visibility, analytics scope) |

This track runs **in parallel** after ACCESS-002 ratification but must not be conflated with Permission Template baseline binding.

### 2.1. Phase map to authoritative documents

| Program phase (this plan) | ARCH-001 roadmap | ADR-051 §10 | ADR-053 |
|---------------------------|------------------|-------------|---------|
| G1–G2 | — (governance) | — | AC3 |
| B1–B3 | Phase 2 (binding) | Phase 2 shadow prep | Phase 2.6b |
| F1 | Phase 3 | — | Phase 3 (Employment) |
| F2 | Phase 4 | Phase 1 | — |
| S1–S2 | Phase 5 | Phase 2 | — |
| C1–C2 | Phase 6 | Phase 3–4 | Phase 4–5 |
| D1 | Phase 7 | Phase 5 | Phase 5+ |
| D2 | Phase 8 | — | — |
| M1 | — (ACCESS-002) | — | — |

---

## 3. Dependencies

### 3.1. Phase dependency graph

```text
[Done] Architecture Accepted (ADR-050/051/053)
[Done] Phase 2.6a engineering
        │
        ▼
   G1 Policy Ratification ─────────────────────────────► M1 (parallel, ACCESS-002 track)
        │
        ▼
   G2 AC3 closure
        │
        ▼
   B1 OPS-030 prep ──► B2 Phase 2.6b bind ──► B3 Shadow observation
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
   F1 Employment retarget            S1 Subsystem shadow (may overlap F2)
        │
        ▼
   F2 Resolver completion
        │
        ▼
   S1 ──► S2 Parity sign-off (per subsystem)
        │
        ▼
   C1 Enforcement cutover (per subsystem)
        │
        ▼
   C2 Acting integration
        │
        ▼
   D1 Decommission ──► D2 Cleanup
```

### 3.2. Per-phase specification

| Phase | Prerequisites | Outputs | Implementation gate |
|-------|---------------|---------|---------------------|
| **G1** | Architecture Accepted; ACCESS docs **Reviewed** | Signed work packages; ratification register | None — governance only |
| **G2** | G1 Track B complete; ACCESS-001 **Approved**; ≥1 approved §7 row | AC3 closed; OPS-030 unblocked | **Opens** Tier B |
| **B1** | G2 | Runbook ready; production ID verification | None — planning only |
| **B2** | B1; approved contour list | `permission_template_contour_rule` rows; `access_role_id` populated | **Data mutation** — legacy enforcement only |
| **B3** | B2 | Shadow parity report; validation SQL clean | **Tier B complete** — binding program done |
| **F1** | B3 or parallel start after 2.2 stable mapping | Employment → org-unique Position FK | Blocks enforcement cutover |
| **F2** | F1 (recommended) | Full resolver read outputs | Blocks meaningful shadow parity |
| **S1** | B3 + F2 | Divergence logs per subsystem | Blocks C1 for that subsystem |
| **S2** | S1 per subsystem | Subsystem parity sign-off | **Opens** C1 for that subsystem |
| **C1** | S2 + consumer ADR | Subsystem uses resolver for enforcement | **User-visible auth change** |
| **C2** | C1 core paths | Acting in resolver | Enhances C1 |
| **C3** | Future ADR | Atomic Template permissions | Optional long-term |
| **D1** | C1 all critical subsystems | `role_id` not auth input | **Programmatic decommission** |
| **D2** | D1 | Single pipeline; shadow removed | **Program complete** |
| **M1** | ACCESS-002 **Approved** | Management scope consumer | Independent of Tier B |

### 3.3. Hard gates (must not bypass)

| Gate | Rule |
|------|------|
| **No OPS-030 without Approved ACCESS-001** | Engineering, shadow, or grant-copy substitutes forbidden (ACCESS-001 P11, ADR-053 R3) |
| **No 2.6b backfill without AC3** | ADR-053 AC3 |
| **No enforcement flip without shadow sign-off** | ADR-051 §10 Phase 2 → 3 |
| **No Employment cutover on catalog FK** | ARCH-001 Phase 2 before Phase 3 |
| **No global big-bang cutover** | ARCH-001 Phase 6 — subsystem order |
| **No grant removal in Phase 2.6** | ADR-053 §3.5 |
| **ACCESS-002 does not substitute ACCESS-001** | Orthogonal layers (ACCESS-001 §3, ACCESS-002 §7) |

---

## 4. Milestones

| ID | Milestone | Phase | Success signal | Target state |
|----|-----------|-------|----------------|--------------|
| **M0** | Architecture baseline accepted | *(done)* | ADR-050/051/053 Accepted | **Achieved** 2026-07-04 |
| **M1** | Phase 2.6a engineering accepted | *(done)* | Schema, resolver read-path, backfill mechanism | **Achieved** 2026-07-04 |
| **M2** | Policy ratification program launched | G1 | ACCESS-RATIFICATION-PROGRAM active; WP register open | **Current** |
| **M3** | ACCESS-001 Approved | G1–G2 | Document status **Approved**; HR head contour row `approved` | Next governance gate |
| **M4** | ADR-053 AC3 closed | G2 | Sign-off recorded; OPS-030 Ready | Unblocks Tier B |
| **M5** | First production template binding | B2 | OPS-030 executed; validation SQL pass | Phase 2.6b MVP |
| **M6** | Phase 2.6 program complete | B3 | Shadow observation report; Tier B exit criteria met | Binding debt closed |
| **M7** | Employment retarget complete | F1 | Active assignments on org-unique Position FK | Foundation ready |
| **M8** | Resolver read program complete | F2 | Representative fixtures pass; Person linkage on operational users | Shadow-ready |
| **M9** | First subsystem shadow sign-off | S2 | Documented parity for one consumer (e.g. admin gates or visibility) | Cutover-ready (one) |
| **M10** | First subsystem enforcement cutover | C1 | One subsystem authoritative on resolver | First production cutover |
| **M11** | All critical subsystems cut over | C1 | Tasks, visibility, admin, personnel per roadmap | Major cutover complete |
| **M12** | Acting integrated | C2 | ADR-036 in resolver path; role-swap banned in ops | Full resolver semantics |
| **M13** | User-centric auth decommissioned | D1 | No production path reads `users.role_id` for access | Legacy retired |
| **M14** | Position Cabinet program complete | D2 | §6 Definition of Done satisfied | Program closed |
| **M-parallel** | ACCESS-002 Approved | G1 | Management responsibility matrix annex | Enables M1 planning only |

**Near-term critical path:** M2 → M3 → M4 → M5 → M6.

---

## 5. Risks

### 5.1. Organizational and policy risks

| ID | Risk | Impact | Mitigation |
|----|------|--------|------------|
| **O1** | Ratification stalls on кадровое решение class (Director) | Blocks full §7 matrix; may delay M3 | MVP path: approve HR-service contour only; record §5.1 as policy debt per WP-B3 |
| **O2** | ACCESS-001 and ACCESS-002 conflated at shared contours | Contradictory ops decisions | WP-X1 crosswalk before row approvals; orthogonal layer training for approvers |
| **O3** | Engineering infers policy from shadow or grants | Wrong contour bindings; governance violation | OPS-030 explicit ban; ACCESS-001 P11 / ACCESS-002 M10 |
| **O4** | Partial ratification treated as full Approved | Premature OPS-030 scope creep | WP-X2 document promotion only when mandatory WPs closed; debt register |
| **O5** | ACCESS-002 delay blocks Phase 2.6b by misconception | False dependency | Document and communicate: ACCESS-002 does not gate OPS-030 (this plan §3.3) |

### 5.2. Architectural and technical risks

| ID | Risk | Impact | Mitigation |
|----|------|--------|------------|
| **A1** | Premature enforcement cutover | Lockout, wrong access | Tier S mandatory; subsystem-by-subsystem C1; break-glass grants retained |
| **A2** | Catalog `position_id` treated as org-unique Position | Permanent resolver corruption | F1 hard gate; mapping table discipline per ADR-050 |
| **A3** | Namespace mismatch (`roles.code` vs `access_roles.code`) | False shadow parity | ADR-053 binding via `access_role_id`; Tier B before meaningful S1 |
| **A4** | Grant removal during binding phase | Authorization regression | ADR-053 §3.5 explicit non-goal through Phase 2.6 |
| **A5** | JWT or frontend embeds resolver permissions | Stale claims; baseline violation | ADR-051 R12; consumer ADRs reviewed at C1 |
| **A6** | Acting via `users.role_id` swap | Lost cabinet context | ADR-036 + ops playbook; C2 integration |
| **A7** | Transitional single-code binding assumed as end state | Under-modeled permissions | C3 tracked as future ADR; policy debt in WP-B8 |

### 5.3. Implementation and operational risks

| ID | Risk | Impact | Mitigation |
|----|------|--------|------------|
| **I1** | Production contour ID drift vs ACCESS-001 §7 | Wrong rule inserts | B1 VPS verification step; OPS-030 precondition |
| **I2** | Ops window failure mid-backfill | Partial binding state | Idempotent backfill (ADR-053); OPS-030 rollback procedure |
| **I3** | Shadow noise without binding baseline | Parity metrics meaningless | Sequence B3 before S1 program expansion |
| **I4** | Consumer ADR wave delays C1 | Extended dual-read period | Per-subsystem S2/C1; prioritize high-risk consumers first |
| **I5** | Person linkage gaps on operational users | Empty accessible set | ADR-048 materialization gate in F2 |
| **I6** | Big-bang subsystem migration | Outage | ARCH-001 Phase 6 ordering; one flip at a time |

---

## 6. Definition of Done

The **Position Cabinet implementation program** is **complete** when all objective conditions below are satisfied.

### 6.1. Governance

| # | Criterion |
|---|-----------|
| D-G1 | ACCESS-001 and ACCESS-002 status = **Approved** (or explicit program closure decision recorded for deferred policy debt) |
| D-G2 | [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) completion criteria (§6.1 C1–C8) met |

### 6.2. Binding and foundation

| # | Criterion |
|---|-----------|
| D-B1 | ADR-053 Phase 2.6 complete — Tier B exit (B3): ops-approved contours bound; validation SQL steady state |
| D-B2 | Employment retarget complete (F1) — `person_assignments` reference org-unique Position |
| D-B3 | Permission Template baseline uses approved organizational policy; no grant-copy binding |

### 6.3. Resolver and shadow

| # | Criterion |
|---|-----------|
| D-R1 | Cabinet Access Resolver is the **sole authoritative** access computation path (ADR-051 §8.1) |
| D-R2 | Shadow modes **retired** — no dual-read shims in production |
| D-R3 | Acting overlay integrated per ADR-036 (C2) |

### 6.4. Consumer cutover

| # | Criterion |
|---|-----------|
| D-C1 | All Phase 6 subsystems in [ARCH-001 Implementation Roadmap](../architecture/ARCH-001-implementation-roadmap.md) enforce from resolver or documented exception path |
| D-C2 | `/auth/me` and route guards migrated per ADR-042 B5 and consumer ADRs |
| D-C3 | Management authority track (M1) either **complete** or **explicitly scoped out** with recorded deferral — not a blocker for access cutover completion |

### 6.5. Decommission

| # | Criterion |
|---|-----------|
| D-D1 | `users.role_id` not used as operational authorization input |
| D-D2 | `access_grants` narrowed to documented break-glass exceptions (ADR-051 R17, ARCH-001 §15) |
| D-D3 | `public.roles` is Template definition catalog only — not User assignment target |
| D-D4 | User-centric management edges (`org_unit_managers.user_id` as scope carrier) retired or re-homed per approved ACCESS-002 implementation |

### 6.6. Operational readiness

| # | Criterion |
|---|-----------|
| D-O1 | Ops runbooks current (positions sync, org structure, enrollment, acting, binding) |
| D-O2 | Mandatory invariants verified in production (ADR-050 I*, ADR-051 R*) |
| D-O3 | Audit trail uses `(person_id, cabinet_id, permission, timestamp)` on operational actions |
| D-O4 | Monitoring for resolver failures, empty accessible sets, Person linkage gaps |

### 6.7. Program closure

| # | Criterion |
|---|-----------|
| D-P1 | Architecture session records program closure |
| D-P2 | No active Position Cabinet migration phase remains in **Blocked** or **In progress** state on this plan |
| D-P3 | Residual technical debt items transferred to normal OPS backlog with owners |

**Note:** D-C3 management authority may complete **after** D-R1–D-D4 if ACCESS-002 implementation is deferred — access cutover and management scope are **orthogonal programs**.

---

## 7. Relationship with ACCESS-RATIFICATION-PROGRAM

| Dimension | ACCESS-RATIFICATION-PROGRAM | This master plan |
|-----------|----------------------------|------------------|
| **Scope** | Organizational approval only (Reviewed → Approved) | Full journey to production cutover |
| **Phases** | WP-A*, WP-B*, WP-X* work packages | G1–D2 program phases |
| **Runtime** | Explicitly none | Tier B onward mutates data; Tier C onward mutates enforcement |
| **Role** | **Gate** for Tier B (via G2 / AC3) | **Orchestrator** for all remaining work |

```text
ACCESS-RATIFICATION-PROGRAM (G1)
         │
         ├── Track B ──► G2 AC3 ──► Tier B (OPS-030 / 2.6b)
         │
         └── Track A ──► M1 (parallel; future management program)

This master plan ──► Tiers F, S, C, D (after or parallel to B)
```

**Near-term execution focus:** complete [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) Track B through WP-X3 to unlock Tier B. Track A may proceed in parallel but does not unblock OPS-030.

---

## 8. Document map

| Document | Role in remaining program |
|----------|---------------------------|
| [ACCESS-RATIFICATION-PROGRAM](../access/ACCESS-RATIFICATION-PROGRAM.md) | Active governance — how to reach Approved |
| [ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md) | OPS-030 row authority |
| [ACCESS-002](../access/ACCESS-002-organizational-management-authority-model.md) | Future management program input |
| [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) | Tier B execution runbook |
| [ADR-053](../adr/ADR-053-permission-template-binding-model.md) | Binding contract + AC3 |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | Resolver + cutover phases |
| [ARCH-001 Implementation Roadmap](../architecture/ARCH-001-implementation-roadmap.md) | Phases 2–8 authoritative sequencing |
| [ops-backlog](../roadmap/ops-backlog.md) | Operational task tracking (not modified by this plan) |

---

## 9. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial master plan — post-architecture execution roadmap |
