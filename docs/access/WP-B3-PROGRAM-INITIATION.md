# WP-B3 — Program Initiation (Executive HR Decision Model)

## Status

**Open (initiated)** — 2026-07-04

Program initiation document for **WP-B3 — Executive HR Decision Model** under [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) (Tier G, Phase G1). Opens the **second Governance cycle** of the Position Cabinet Implementation Program. **No runtime effect.** **No implementation authority.**

| Field | Value |
|-------|-------|
| Work package | WP-B3 — Кадровое решение model / Executive HR Decision Model |
| Tier / phase | G — Governance / G1 — Policy Ratification |
| Prior cycle baseline | [TIER-G-GOVERNANCE-PROGRESS-REPORT.md](./TIER-G-GOVERNANCE-PROGRESS-REPORT.md) |
| Program | [POSITION-CABINET-IMPLEMENTATION-MASTER-PLAN](../roadmap/POSITION-CABINET-IMPLEMENTATION-MASTER-PLAN.md) |
| Normative policy (unchanged) | [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md) — **Reviewed** |

---

## 1. Purpose

### Why WP-B3 begins a new governance cycle

The first Governance cycle (WP-B1, WP-B2) established the **organizational vocabulary** and **binding rules** for the ACCESS-001 permission layer:

- **WP-B1** ratified four permission domains — including `PD-5.1` (Кадровое решение) — as accepted taxonomy.
- **WP-B2** ratified twelve binding principles P1–P12 — including P7's negative prohibition against substitute codes for executive HR decision authority.

Both cycles recorded **policy debt** where the **positive** executive decision class remains undefined. That gap is the sole reason WP-B1 and WP-B2 remain formally open alongside pending attestation.

**WP-B3 opens the second Governance cycle** because it is the first work package that must produce an **organizational class decision** — not taxonomy acceptance or principle ratification, but a **positive governance model** for executive HR decision authority. This decision will later inform contour binding (WP-B7) and, downstream, the ops mapping annex required for ADR-053 AC3. It does **not** authorize implementation, OPS-030, or runtime binding.

### Position in the Master Plan

Per [POSITION-CABINET-IMPLEMENTATION-MASTER-PLAN](../roadmap/POSITION-CABINET-IMPLEMENTATION-MASTER-PLAN.md):

| Dimension | Position |
|-----------|----------|
| **Program phase** | G1 — Policy Ratification (Track B) |
| **Sequence** | `WP-B1 → WP-B2 → **WP-B3** → WP-B4 → …` |
| **Milestone** | Follows **M2** (ratification program launched); precedes **M3** (ACCESS-001 **Approved**) |
| **Critical path** | WP-B3 resolves the **Director gap** — §5.1 class must exist (or debt be explicitly continued) before Director contour `(78, 62)` may be dispositioned in WP-B7 |
| **Implementation chain** | Governance decision → WP-B4/B7 → WP-X2 → WP-X3 (AC3) → Tier B (OPS-030) — WP-B3 is the **first governance step** on that chain; it is **not** an implementation step |

WP-B3 is the **first work package that connects Governance policy with future implementation** by defining the organizational class that future binding policy may reference. Connection is **directional only** — no execution is authorized by WP-B3 initiation or completion.

---

## 2. Inputs

Mandatory inputs for WP-B3. All are **read-only** references; WP-B3 initiation does not modify them.

| Input | Role in WP-B3 |
|-------|---------------|
| [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md) (**Reviewed**) | Normative source — §5.1 (Кадровое решение); §4 P5, P7; §7 Director contour `(1, 78, 62)` disposition |
| [ACCESS-002](./ACCESS-002-organizational-management-authority-model.md) (**Reviewed**) | Orthogonal layer — executive management responsibilities must not be conflated with permission class (§3, P12) |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) (**Accepted**) | Position Cabinet entity contract — permissions attach to Cabinet, not Person or Platform User |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) (**Accepted**) | Resolver evaluation contract — Template expansion; no grant-copy binding |
| [ADR-053](../adr/ADR-053-permission-template-binding-model.md) (**Accepted**) | Binding model — transitional `access_roles` namespace; contour rules; AC3 ops mapping gate |
| [WP-B1 Closure Report](./WP-B1-CLOSURE-REPORT.md) | `PD-5.1` ratified with Policy Debt; DEBT-B1-001 recorded |
| [WP-B2 Binding Principles Review](./WP-B2-BINDING-PRINCIPLES-REVIEW.md) | P7 ratified with Policy Debt; DEBT-B2-001 recorded; negative prohibitions accepted |
| [TIER-G Governance Progress Report](./TIER-G-GOVERNANCE-PROGRESS-REPORT.md) | Authoritative program snapshot — governance baseline for cycle opening |

**Supporting references (informative):**

| Document | Relevance |
|----------|-----------|
| [WP-B1 Permission Domain Ratification Package](./WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md) | PD-5.1 review sheet and §6.1 debt register |
| [PERMISSION-DOMAIN-REGISTRY](./PERMISSION-DOMAIN-REGISTRY.md) | `PD-5.1` ratification status |
| [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) §4.3 WP-B3 | Approval authority and expected output |
| [ARCHITECTURE_GOVERNANCE](../architecture/ARCHITECTURE_GOVERNANCE.md) | Architecture baseline principles |
| [ARCH-001](../architecture/ARCH-001-position-permission-model.md) (**Accepted**) | Domain architecture baseline |
| [ADR-045](../adr/ADR-045-personnel-hr-processes-split.md) | Executive read scope — runtime mechanism; not substitute for PD-5.1 class |

---

## 3. Program objective

**Single objective:**

> Establish the governance model for **Executive HR Decision authority** — the positive organizational permission class for domain `PD-5.1` (Кадровое решение) on Position Cabinet Permission Template baseline.

| Statement | Detail |
|-----------|--------|
| **Governance only** | Produce a ratifiable organizational decision (or explicit continued policy debt with recorded rationale) |
| **No implementation** | Does not insert contour rules, populate `access_role_id`, run OPS-030, or change authorization behaviour |
| **No document promotion** | Does not promote ACCESS-001 to **Approved** (WP-X2) |
| **No contour approval** | Does not set §7 `policy_status=approved` for any contour (WP-B7) |

---

## 4. Scope boundary

### In scope

| Item | Detail |
|------|--------|
| **Executive HR Decision class** | Positive organizational permission class definition for `PD-5.1` |
| **Кадровое решение model** | Governance model for executive approval authority: hire, transfer, dismiss, appoint acting duties (per ACCESS-001 §5.1) |
| **DEBT-B1-001 resolution** | Transitional organizational class for executive HR decision authority — decision whether a transitional `access_roles.code` exists or debt continues |
| **DEBT-B2-001 resolution** | P7 positive class at principles layer — converges with DEBT-B1-001 |
| **Director / Acting Director archetype** | Organizational stance for typical holders of `PD-5.1` — class definition, not contour row approval |
| **Separation from substitutes** | Affirm boundaries already ratified in WP-B2 (P4, P5, P7 negative rules) — no substitute via `HR_ENROLLMENT_MANAGER`, `SYSADMIN_CABINET`, or title inference |
| **Orthogonality to ACCESS-002** | Confirm permission class does not substitute executive management responsibilities |

### Out of scope

| Item | Owner |
|------|-------|
| HR enrollment / оформление (`PD-5.2`) | **WP-B4** |
| HR oversight visibility (`PD-5.3`) | **WP-B4** / **WP-B8** (DEBT-B1-004) |
| Line informational boundary (`PD-5.4`) | **WP-B5** |
| §7 contour `policy_status` disposition | **WP-B7** |
| HR head `(73, 86)` or deputy admin `(78, 77)` class assignment | **WP-B4** |
| ACCESS-001 **Reviewed** → **Approved** promotion | **WP-X2** |
| ADR-053 AC3 sign-off | **WP-X3** |
| OPS-030 / Phase 2.6b execution | **Tier B** |
| Runtime bindings, schema changes, grant mutations | Engineering / ops — gated separately |
| ACCESS-002 management responsibility ratification | Track A (WP-A*) |
| Cross-layer shared-contour crosswalk | **WP-X1** (informative input; not a WP-B3 deliverable) |

### Downstream work packages (receive WP-B3 output)

| Work package | Relationship |
|--------------|--------------|
| **WP-B4** | HR operational class assignments — may proceed in parallel for HR-service scope; Director sequencing depends on WP-B3 outcome |
| **WP-B7** | Matrix row disposition — Director contour `(78, 62)` cannot become `approved` until WP-B3 resolves positive class (or records continued debt with explicit Director rejection rationale) |
| **WP-B8** | Open policy questions — transitional catalog sufficiency; may consume WP-B3 decision on whether a transitional code was approved or debt deferred |

---

## 5. Program dependencies

### Dependency chain

```text
WP-B1  Permission Domain Taxonomy          [substantive complete; attestation pending]
    ↓
WP-B2  Binding Principles                  [substantive complete; attestation pending]
    ↓
WP-B3  Executive HR Decision Model         [this cycle — initiated]
    ↓
WP-B4  HR operational class assignments
    ↓
WP-B7  Matrix row disposition
    ↓
WP-X2  ACCESS-001 → Approved
    ↓
WP-X3  ADR-053 AC3 sign-off
    ↓
OPS-030 / Phase 2.6b                       [Tier B — not authorized by WP-B3]
```

### Dependency assessment

| Predecessor | Status | Effect on WP-B3 |
|-------------|--------|-----------------|
| **WP-B1** | Substantive complete — `PD-5.1` ratified with Policy Debt | **Satisfied** — taxonomy accepted; positive class deferred to WP-B3 |
| **WP-B2** | Substantive complete — P7 negative prohibition ratified | **Satisfied** — binding rules accepted; positive class deferred to WP-B3 |
| **Architecture Accepted** | ADR-050 / ADR-051 / ADR-053 | **Satisfied** — binding contract frozen |
| **WP-B1 / WP-B2 attestation** | Pending signatures | **Does not block** WP-B3 preparation or Review Board per program sequencing |

**Note:** Phase 2.6b MVP path may proceed **without** Director contour approval if WP-B3 records continued debt and HR head contour is approved via WP-B4 + WP-B7 — per ACCESS-RATIFICATION-PROGRAM WP-B3 implementation readiness statement.

---

## 6. Policy debts entering WP-B3

Two open policy debts enter this cycle. Both describe the **same organizational gap** from different governance layers. WP-B3 owns resolution of **both**.

| Debt ID | Source | Item | Why WP-B3 owns resolution |
|---------|--------|------|---------------------------|
| **DEBT-B1-001** | WP-B1 — `PD-5.1` domain taxonomy layer | Transitional `access_roles.code` for кадровое решение / executive HR decision authority not defined in Reviewed ACCESS-001 | WP-B1 ratified the **domain** but explicitly deferred **positive class and code mapping** to WP-B3. Domain taxonomy without class definition is incomplete for contour binding. |
| **DEBT-B2-001** | WP-B2 — principles layer (P7) | Positive **кадровое решение** permission class not defined at principles ratification; P7 **negative** prohibition (no `HR_ENROLLMENT_MANAGER` / `SYSADMIN_CABINET` substitute) ratified | WP-B2 ratified that a **separate class is required** (P7) but deferred the **positive definition** to WP-B3. Cross-references DEBT-B1-001. |

**Convergence:** DEBT-B1-001 and DEBT-B2-001 are **not independent debts**. WP-B3 must produce a single coherent governance outcome that closes both — or records explicit continued debt with assigned owner and rationale.

**This initiation document does not propose solutions.** Resolution options (per ACCESS-RATIFICATION-PROGRAM WP-B3 approval output) are for the governance session:

- (a) Approve transitional organizational class / `access_roles.code` mapping for кадровое решение, or
- (b) Record continued policy debt — Director remains **rejected** for baseline bindings until a future code exists

---

## 7. Governance questions

Questions prepared for WP-B3 governance sessions. **No decisions recorded here.**

### Class definition

1. What constitutes **Executive HR Decision authority** in organizational terms — distinct from HR document preparation, enrollment execution, and management oversight?
2. Which organizational actions fall within кадровое **решение** (approve hire, transfer, dismiss, appoint acting duties) versus кадровое **оформление** (PD-5.2)?
3. What is the minimum **positive class definition** required to close DEBT-B1-001 and DEBT-B2-001 — even if no transitional `access_roles.code` is approved?

### Organizational responsibility

4. Which **organizational responsibility** qualifies a Position Cabinet holder for the Executive HR Decision class — and how is that responsibility expressed without relying on job title alone?
5. How does **Acting Director** (исполняющий обязанности) relate to the class — same class, separate class, or acting-specific policy debt?
6. How is the class **separated from ACCESS-002** executive management responsibilities (organizational information, responsibility for results, subtree scope)?

### Cabinet vs title

7. How does the positive class relate to **Position Cabinet** rather than job title — consistent with P1 (Cabinet baseline binding) and Architecture Baseline principle 5 (authority follows position occupancy)?
8. Why must Director contour `(1, 78, 62)` remain **rejected** for `SYSADMIN_CABINET` and `HR_ENROLLMENT_MANAGER` pending WP-B3 — and what class would be required for any future `approved` disposition?

### Governance vs implementation

9. How is **positive class definition separated from implementation** — i.e., what does WP-B3 decide vs what WP-B7 and OPS-030 execute later?
10. If a transitional `access_roles.code` is approved, what governance attestation is required before that code may appear in §7 or OPS-030 — and which work package owns each step?
11. If no transitional code is approved, what **continued policy debt** must be recorded, and does Phase 2.6b MVP (HR head contour only) remain valid?

### Architectural constraints

12. Which **architectural constraints are already fixed** and therefore not subject to WP-B3 redesign — Cabinet binding path, `access_roles` namespace, no grant-copy binding, legacy enforcement unchanged?
13. How does **ADR-045 executive read scope** relate to PD-5.1 — complementary runtime mechanism vs substitute for permission class?
14. Does WP-B3 require **ACCESS-002 ratification** as a precondition, or only informative alignment per orthogonal layer rule (P12)?

### Approval and process

15. Who must attest the WP-B3 outcome — executive sponsor, HR policy owner, ops lead — and what constitutes **ratified** vs **ratified with continued policy debt**?
16. What explicit statement must the ratification record include to prevent misread as OPS-030 authorization or §7 row approval?

---

## 8. Architecture baseline

Architectural decisions **already fixed**. Architecture Freeze remains in effect. WP-B3 **does not** amend ARCH-001, ADR-050, ADR-051, or ADR-053. Governance may **consume** these contracts; it may not **redesign** them.

### Architecture governance principles

Per [ARCHITECTURE_GOVERNANCE](../architecture/ARCHITECTURE_GOVERNANCE.md) and [ARCH-001](../architecture/ARCH-001-position-permission-model.md) (**Accepted**):

| # | Fixed principle |
|---|-----------------|
| 1 | Person does not define authority |
| 2 | Platform User is authentication only |
| 3 | Position is the unique organizational staffing unit |
| 4 | Position Cabinet is the digital representation of Position |
| 5 | Authority follows position occupancy (including acting), not user account attributes |
| 6 | Work processes attach to Position Cabinet where domain permits |

### ADR-050 — Position Cabinet model (**Accepted**)

| Fixed decision | Implication for WP-B3 |
|----------------|----------------------|
| Permission Template lives inside Cabinet (1:1) | Executive HR Decision class binds to **Cabinet baseline**, not Person or Platform User |
| Cabinet is configuration anchor | Class definition is organizational policy on Cabinet contour — not grant on user |

### ADR-051 — Cabinet Access Resolver (**Accepted**)

| Fixed decision | Implication for WP-B3 |
|----------------|----------------------|
| Template load → expand → union | Class maps to Template `access_role_id` at implementation time — not at WP-B3 |
| `access_grants` remain exception overlay through Phase 2.6 | WP-B3 decision does not mutate grants |
| No enforcement cutover in Phase 2.6 | Legacy path remains authoritative |

### ADR-053 — Permission Template binding model (**Accepted**)

| Fixed decision | Implication for WP-B3 |
|----------------|----------------------|
| Binding via `access_roles` namespace (transitional) | If WP-B3 approves a code, it must exist in or be added to `access_roles` catalog — catalog change is downstream engineering, not WP-B3 scope |
| Contour rules in `permission_template_contour_rule` | Contour binding is WP-B7 + OPS-030 — not WP-B3 |
| No binding from `users.role_id`, user grants, or occupant inference (R3, §3.4) | WP-B3 class must not be derived from current occupants or grants |
| AC3 ops mapping annex required before Phase 2.6b backfill | WP-B3 contributes to future annex content; does not satisfy AC3 |
| Phase 2.6a engineering accepted; 2.6b blocked on AC3 | WP-B3 does not unblock 2.6b |

### ACCESS-001 binding principles already ratified (WP-B2)

| Principle | Fixed prohibition relevant to WP-B3 |
|-----------|--------------------------------------|
| **P4** | Organizational position alone does not confer `SYSADMIN_CABINET` |
| **P5** | Director / Acting Director ≠ sysadmin; ≠ `HR_ENROLLMENT_MANAGER` by title |
| **P7** (negative) | No substitute codes for кадровое решение — separate class required |
| **P11** | Engineering artefacts do not substitute for work-package approval |
| **P12** | ACCESS-001 and ACCESS-002 are orthogonal |

**Explicit statement:** Any WP-B3 outcome must be **consistent with** the above. Contradiction requires an architecture amendment program — not a WP-B3 policy session.

---

## 9. Success criteria

Objective completion criteria for **WP-B3**. Governance only — no implementation criteria.

| # | Criterion | Evidence |
|---|-----------|----------|
| SC-1 | **Executive HR Decision class** governance model ratified — positive organizational permission class for `PD-5.1` defined or explicit continued debt recorded with rationale | Signed WP-B3 ratification record |
| SC-2 | **DEBT-B1-001** closed or explicitly continued with owner and target phase | Policy debt register update |
| SC-3 | **DEBT-B2-001** closed or explicitly continued — coherent with SC-2 outcome | Policy debt register update |
| SC-4 | Ratification authority satisfied | Executive sponsor + HR policy owner + ops lead signatures per ACCESS-RATIFICATION-PROGRAM §4.1 |
| SC-5 | No Accepted ADR contradiction attested | Architecture lead confirmation (if consulted) |
| SC-6 | Explicit statement: ratification **does not** approve §7 rows, promote ACCESS-001 to **Approved**, authorize OPS-030, or change runtime behaviour | Ratification record wording |
| SC-7 | Orthogonality to ACCESS-002 affirmed in ratification record | Recorded boundary statement |
| SC-8 | Governance artefacts updated — ratification outcome traceable in program register | WP-B3 outcome record; PERMISSION-DOMAIN-REGISTRY or companion register if established |

**Out of scope for WP-B3 success:** ACCESS-001 **Approved**; any §7 row `approved`; ADR-053 AC3 closure; OPS-030 execution; `permission_template_contour_rule` insert; `access_role_id` population.

---

## 10. Exit criteria

Conditions that must be true before **WP-B4** may begin (or continue class-assignment work that depends on WP-B3 outcome).

| # | Exit criterion | Required state |
|---|----------------|----------------|
| EC-1 | WP-B3 ratification decision recorded | **Ratified** or **Ratified with Continued Policy Debt** |
| EC-2 | DEBT-B1-001 disposition recorded | **Closed** (class defined) or **Continued** (explicit debt with owner — Director binding remains blocked) |
| EC-3 | DEBT-B2-001 disposition recorded | **Closed** or **Continued** — aligned with EC-2 |
| EC-4 | Mandatory approvers signed | Executive sponsor + HR policy owner + ops lead |
| EC-5 | WP-B3 formally **Closed** in program register | Closure attestation recorded |
| EC-6 | Downstream packages informed of outcome | WP-B4 / WP-B7 / WP-B8 can reference WP-B3 decision without ambiguity |

**WP-B4 may begin HR-service scope preparation in parallel** (contour `(73, 86)` — PD-5.2) while WP-B3 is in progress. WP-B4 decisions that depend on Director sequencing or cross-executive class boundaries require EC-1 through EC-6.

**Implementation gates remain unchanged at WP-B3 exit:** ACCESS-001 **Reviewed**; OPS-030 **Blocked**; ADR-053 AC3 **Pending**; no approved §7 rows; legacy enforcement authoritative.

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial program initiation — WP-B3 cycle opened; governance questions prepared; no decisions recorded |
