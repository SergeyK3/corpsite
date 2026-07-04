# ACCESS-RATIFICATION-PROGRAM — Policy Ratification Program

## Status

**Active (planning)** — 2026-07-04

Organizational approval program to advance [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md) and [ACCESS-002](./ACCESS-002-organizational-management-authority-model.md) from **Reviewed** to **Approved**. **Planning document only** — no runtime effect, no policy redesign, no architecture amendment.

| Field | Value |
|-------|-------|
| Precedes | ACCESS-001 / ACCESS-002 status promotion to **Approved** |
| Does not modify | [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md), [ADR-051](../adr/ADR-051-cabinet-access-resolution.md), [ADR-053](../adr/ADR-053-permission-template-binding-model.md) (all **Accepted**) |
| Enables (indirectly) | [ADR-053 AC3](../adr/ADR-053-permission-template-binding-model.md#11-acceptance-criteria-ratified) → [OPS-030](../ops/OPS-030-permission-template-contour-binding.md) → Phase 2.6b |
| Related | [ops-backlog § Organizational Policy Layer](../roadmap/ops-backlog.md) |

---

## 1. Objectives

### 1.1. Purpose of Policy Ratification

**Policy Ratification** is the organizational governance phase in which stakeholders **approve** the Organizational Policy Layer as binding organizational truth. It follows **Architecture Design** (complete) and precedes **runtime execution** where policy gates apply.

The phase answers: *"Do we, as an organization, accept these policy definitions as the authoritative basis for future binding and implementation?"*

Ratification produces **Approved** policy documents. Approved status is a **governance gate**, not a technical deployment.

### 1.2. Distinction from architecture design

| Dimension | Architecture design | Policy Ratification |
|-----------|---------------------|---------------------|
| **Question** | *How may the system represent and evaluate permissions?* | *Which organizational contours may receive which permissions and responsibilities?* |
| **Artifacts** | ARCH-001, ADR-050 / ADR-051 / ADR-053 (**Accepted**) | ACCESS-001, ACCESS-002 (**Reviewed** → **Approved**) |
| **Authority** | Architecture review | Ops + HR + executive stakeholders |
| **Output** | Binding contract, resolver semantics, schema authorization | Approved permission domains, matrix rows, management responsibility assignments |
| **Runtime effect** | Engineering may build to contract (Phase 2.6a done) | **None by itself** — unlocks ops execution gates |

Architecture acceptance is **complete**. No ADR amendment is required for ratification. Ratification **consumes** accepted architecture; it does not redesign it.

### 1.3. Distinction from runtime implementation

| Dimension | Policy Ratification | Runtime implementation |
|-----------|---------------------|------------------------|
| **Question** | *What is our organizational policy?* | *How do we apply approved policy in production data and code?* |
| **Artifacts** | ACCESS document status, signed work packages, AC3 annex | OPS-030 runbook, migrations, backfill, shadow observation |
| **Mutates production** | **No** | **Yes** (contour rules, template binding — Phase 2.6b) |
| **Enforcement** | Unchanged — legacy `access_grants`, user-centric management edges | Future cutover programs (separate from this phase) |

**Explicit rule:** advancing a work package to **ratified** does not insert contour rules, change schema, modify grants, or alter authorization behaviour. OPS-030 and Phase 2.6b remain **blocked** until ACCESS-001 reaches **Approved** and AC3 is signed — ratification work packages are prerequisites, not execution.

### 1.4. Program outcomes

At successful completion:

1. ACCESS-001 and ACCESS-002 carry status **Approved** with recorded approvers and date.
2. All mandatory ratification work packages (§3) are closed or explicitly deferred with recorded rationale.
3. ADR-053 AC3 ops mapping annex is satisfied by **Approved** ACCESS-001 (§7 matrix + §5 permission domains).
4. Phase 2.6b / OPS-030 may begin **planning and execution** — still subject to engineering validation and ops window controls.
5. Future management-authority implementation may begin **planning** — gated on ACCESS-002 **Approved**; no OPS runbook exists yet.

---

## 2. Approval sequence

### 2.1. Recommended order

Ratification runs on **two orthogonal tracks** with **sequenced touchpoints** at shared contours.

```text
Track A — ACCESS-002 (management responsibilities)
──────────────────────────────────────────────────
  WP-A1 → WP-A2 → WP-A3 → WP-A5 → WP-A6 → WP-A7 → WP-A8
           │                              ▲
           └──────── WP-A4 ───────────────┘

Track B — ACCESS-001 (organizational permissions)
──────────────────────────────────────────────────
  WP-B1 → WP-B2 → WP-B3 → WP-B4 → WP-B5 → WP-B7 → WP-B8
                              │       │
                              └── WP-B6 (non-HR pending contours)

Cross-track touchpoints (shared contours)
─────────────────────────────────────────
  WP-X1 (after WP-A2 + WP-B1) → before WP-B4 / WP-B7 row approvals
  WP-X2 (document promotion)    → after all mandatory WPs on each track
  WP-X3 (AC3 record)            → after ACCESS-001 WP-X2
```

**Recommended sequencing principle:**

| Stage | Order | Rationale |
|-------|-------|-----------|
| **Foundations (parallel)** | WP-A1 + WP-B1 + WP-B2 | Responsibility taxonomy and permission domain taxonomy are orthogonal definitions; both can be ratified without cross-dependency |
| **Combination rules** | WP-A2 before WP-A7 | Contour matrix requires approved combination rules |
| **Delegation** | WP-A3 before WP-A7 | Delegation policy must be ratified before contour rows reference delegated remit |
| **Subtree & hierarchy** | WP-A5 + WP-A6 before WP-A7 | Contour matrix annex requires subtree defaults |
| **Cross-layer boundary** | WP-X1 before WP-B4, WP-B5, WP-B7 | Shared contours need aligned HR-permission vs management-responsibility boundaries |
| **Director gap** | WP-B3 before Director contour row in WP-B7 | §5.1 кадровое решение class must exist before any Director binding approval |
| **Document promotion** | WP-X2 per track | **Approved** status only after mandatory WPs closed on that track |
| **AC3 closure** | WP-X3 after ACCESS-001 WP-X2 | Formal AC3 sign-off references Approved annex |

### 2.2. Should ACCESS-002 be approved before ACCESS-001?

**Short answer:** **Not as a hard gate for Phase 2.6b**, but **yes for contour-level coherence** on shared Position Cabinets.

| Criterion | ACCESS-002 before ACCESS-001? | Explanation |
|-----------|-------------------------------|-------------|
| **OPS-030 / Phase 2.6b unblock** | **No** | ACCESS-002 **does not** gate OPS-030. Only ACCESS-001 **Approved** + `policy_status=approved` rows + AC3 sign-off unblock Phase 2.6b |
| **Shared contour consistency** | **Yes (partial)** | Deputy admin `(78, 77)`, line heads, Director `(78, 62)` appear in both documents. ACCESS-001 row approval for these contours should follow ratification of the corresponding ACCESS-002 responsibility assignments (WP-A7 rows for same contours) |
| **Full document Approved status** | **Independent** | Either document may reach **Approved** on its own mandatory work-package set; neither is a prerequisite for the other's document-level promotion |
| **Minimum Phase 2.6b path** | ACCESS-001 only | HR head `(73, 86)` approval requires WP-B1 + WP-B4 + WP-B7 only — no ACCESS-002 contour dependency for HR service scope |

**Recommendation:**

1. **Do not delay ACCESS-001 document promotion** waiting for full ACCESS-002 **Approved** if Phase 2.6b is the near-term priority — ratify ACCESS-001 permission domains and HR-service contour first.
2. **Do ratify ACCESS-002 foundations (WP-A1–A6) before approving ACCESS-001 rows** for executive, deputy, and line-head contours — prevents contradictory policy on the same Cabinet.
3. **Run tracks in parallel** where orthogonal; **serialize only at WP-X1 touchpoints** and contour-row approvals.

### 2.3. Dependency map

```text
Accepted architecture (frozen)
  ADR-050 ──┬──► ACCESS-001 ──► WP-X3 (AC3) ──► OPS-030 ──► Phase 2.6b
  ADR-051 ──┤         ▲
  ADR-053 ──┘         │ WP-X1 (informative alignment)
            ADR-050 ──┼──► ACCESS-002 ──► (future management implementation)
            ADR-051 ──┘
            ADR-053 ──┘

ACCESS-001 ⊥ ACCESS-002   (orthogonal layers; informative cross-links only)
ACCESS-002 ↛ OPS-030      (no blocking edge)
ACCESS-001 → OPS-030      (hard gate)
```

| Dependency | Type | Effect if unmet |
|------------|------|-----------------|
| ADR-050 / ADR-051 / ADR-053 Accepted | **Hard** (satisfied) | Architecture design would still be open |
| ACCESS-001 **Approved** | **Hard** for Phase 2.6b | OPS-030 forbidden |
| ACCESS-001 §7 `policy_status=approved` rows | **Hard** for inserts | No contour rules may be inserted for that contour |
| ADR-053 AC3 sign-off | **Hard** for backfill | Phase 2.6b data step blocked |
| ACCESS-002 **Approved** | **Soft** for Phase 2.6b; **Hard** for future management implementation | Phase 2.6b may proceed; management-scope program remains unplanned |
| WP-X1 cross-layer alignment | **Soft** (strongly recommended) | Risk of contradictory policy on shared contours |

---

## 3. Ratification work packages

Work packages are **discrete approval units**. Closing a work package produces a **ratification record** (§4) — not a document edit unless the ratification session identifies a correction requiring a new policy revision cycle (out of scope for this program's planning assumption: documents remain as **Reviewed** text; ratification affirms content).

### Track A — ACCESS-002 (Management Authority Model)

| ID | Work package | Source sections | Mandatory for ACCESS-002 **Approved**? |
|----|--------------|-----------------|----------------------------------------|
| **WP-A1** | Management responsibility taxonomy | §3.1–§3.5 definitions | **Yes** |
| **WP-A2** | Responsibility combination rules | §3.7 | **Yes** |
| **WP-A3** | Delegation policy | §3.6, M9 | **Yes** |
| **WP-A4** | Derived capability group integrity | §4, §3.8, M0, M7 | **Yes** — confirms derivation rules; does **not** approve capability groups as primary policy objects |
| **WP-A5** | Management hierarchy & reporting vertical | §5.1–§5.4, ADR-010 alignment | **Yes** |
| **WP-A6** | Subtree management principle | §6.1–§6.5 | **Yes** |
| **WP-A7** | Contour → responsibility → subtree matrix | New annex (§9.1 planned deliverable) | **Yes** — populate draft matrix for all 35 operational contours mirroring ACCESS-001 §7 inventory |
| **WP-A8** | Open policy questions | Acting vs delegation edge cases; executive org-wide scope; statistics/QM subtree | **Yes** — each item **resolved**, **deferred with owner**, or **accepted as explicit policy debt** |

### Track B — ACCESS-001 (Organizational Permission Matrix)

| ID | Work package | Source sections | Mandatory for ACCESS-001 **Approved**? |
|----|--------------|-----------------|----------------------------------------|
| **WP-B1** | Permission domain taxonomy | §5.1–§5.4 HR operational classes | **Yes** |
| **WP-B2** | Binding principles | §4 P1–P12 | **Yes** |
| **WP-B3** | Кадровое решение model | §5.1 — Director / Acting Director class | **Yes** — must resolve whether a transitional `access_roles.code` exists or policy debt is recorded |
| **WP-B4** | HR operational class assignments | §5.2–§5.3 — HR head `(73, 86)`, deputy admin `(78, 77)` | **Yes** for Phase 2.6b MVP; class + code mapping must be ratified before row `approved` |
| **WP-B5** | Line-head informational boundary | §5.4 — reject `HR_ENROLLMENT_MANAGER`; negative boundary | **Yes** |
| **WP-B6** | Non-HR pending contours | §7 pending rows (statistics, QM, finance, deputies clinical, etc.) | **Conditional** — each row must reach `approved`, `rejected`, or `deferred` with rationale; deferred rows do not block document **Approved** if explicitly listed in policy debt register |
| **WP-B7** | Matrix row disposition | §7 — all 35 rows | **Yes** — every row has final `policy_status`; at least one `approved` row required for AC3 / Phase 2.6b |
| **WP-B8** | Open policy questions | Transitional code sufficiency; future atomic permissions; task-role namespace contours | **Yes** — triage same as WP-A8 |

### Cross-track

| ID | Work package | Scope | Mandatory |
|----|--------------|-------|-----------|
| **WP-X1** | Cross-layer boundary confirmation | ACCESS-001 §3 + ACCESS-002 §7 — shared contour table | **Yes** before WP-B4 / WP-B5 / WP-B7 approvals on shared contours |
| **WP-X2** | Document status promotion | Reviewed → **Approved** per document | **Yes** — one per track |
| **WP-X3** | ADR-053 AC3 sign-off record | Formal attestation that ACCESS-001 Approved satisfies ops mapping annex | **Yes** for Phase 2.6b |

---

## 4. Approval criteria

### 4.1. Approval authorities

| Role | Scope |
|------|-------|
| **Architecture lead** | Confirms ratification does not contradict Accepted ADRs; signs WP-X3 with ops |
| **Ops lead** | Signs contour matrix row dispositions; co-signs document **Approved** and AC3 |
| **HR / personnel policy owner** | Mandatory for WP-B1–B4, WP-B7 rows touching HR classes; кадровое решение / оформление / контроль |
| **Executive sponsor** (Director or delegated authority) | Mandatory for WP-B3, WP-A7 executive/deputy contours, org-wide subtree widening |
| **Line management representative** | Recommended for WP-A7 line-head rows, WP-B5 boundary confirmation |

A work package is **ratified** when all **mandatory** authorities for that package have signed the ratification record.

### 4.2. Track A work packages

#### WP-A1 — Management responsibility taxonomy

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-002 §3.1–§3.5 (Reviewed text); ADR-010 level model; ACCESS-001 §5 visibility boundary statements |
| **Approval authority** | Ops lead + HR policy owner + architecture lead |
| **Approval output** | Signed attestation that six responsibility classes are accepted as organizational vocabulary; derivation overview (§3.8) acknowledged |
| **Implementation readiness** | Enables WP-A7 matrix population; **no** OPS or runtime effect |

#### WP-A2 — Responsibility combination rules

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-002 §3.7 Draft proposals (line head minimum, deputy admin, director) |
| **Approval authority** | Ops lead + executive sponsor + line management representative |
| **Approval output** | Ratified combination rules per role archetype; explicit list of **forbidden** combinations |
| **Implementation readiness** | Required before WP-A7; informs future Management Scope Resolver inputs |

#### WP-A3 — Delegation policy

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-002 §3.6, M5 (acting vs delegation), §4.5 |
| **Approval authority** | Ops lead + HR policy owner + architecture lead |
| **Approval output** | Delegation policy **ratified** or **deferred** with minimum viable rules (e.g. "no operational delegation registry until implementation program") |
| **Implementation readiness** | Delegation registry design blocked until ratified; does not affect Phase 2.6b |

#### WP-A4 — Derived capability group integrity

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-002 §4, §4.6 integrity rules |
| **Approval authority** | Architecture lead + ops lead |
| **Approval output** | Confirmation that capability groups are **derived only**; integrity rules (personnel→visibility only, execution≠results, etc.) are binding for future implementation |
| **Implementation readiness** | Engineering may map responsibilities → groups at implementation time; prevents orphan-capability policy drift |

#### WP-A5 — Management hierarchy & reporting vertical

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-002 §5; ADR-010; §5.3 staff-function placement |
| **Approval authority** | Ops lead + executive sponsor |
| **Approval output** | Ratified level 1–4 responsibility mapping; staff-function subtree defaults (HR, statistics, QM) |
| **Implementation readiness** | Task routing and report-acceptance consumers may be designed against ratified hierarchy |

#### WP-A6 — Subtree management principle

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-002 §6; §6.4 multi-Cabinet union rule |
| **Approval authority** | Ops lead + executive sponsor + architecture lead |
| **Approval output** | Default/narrow/widen rules ratified; explicit list of contours requiring non-default subtree |
| **Implementation readiness** | Subtree parameters for WP-A7 matrix; no runtime scope change |

#### WP-A7 — Contour responsibility matrix

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-001 §7 contour inventory (35 rows); ratified WP-A1–A6 outputs; WP-X1 crosswalk |
| **Approval authority** | Ops lead + HR policy owner + executive sponsor (for executive rows) |
| **Approval output** | Annex: `(client_scope_id, org_unit_id, catalog_position_id) → {responsibilities} + subtree rule` for each contour |
| **Implementation readiness** | Prerequisite for future management-authority OPS runbook; **does not** enable OPS-030 |

#### WP-A8 — Open policy questions (ACCESS-002)

| Field | Value |
|-------|-------|
| **Inputs** | Draft gaps: acting inheritance, delegation registry timing, statistics org-wide scope, QM functional filter |
| **Approval authority** | Ops lead + architecture lead + relevant domain owner per question |
| **Approval output** | **Policy debt register** — each item: resolved / deferred / accepted debt with owner and target phase |
| **Implementation readiness** | Deferred items must not block ACCESS-002 **Approved** if explicitly recorded |

### 4.3. Track B work packages

#### WP-B1 — Permission domain taxonomy

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-001 §5.1–§5.4 class definitions |
| **Approval authority** | HR policy owner + ops lead + architecture lead |
| **Approval output** | Four HR operational domains + informational boundary accepted as organizational vocabulary |
| **Implementation readiness** | Required before any §7 row moves to `approved` |

#### WP-B2 — Binding principles

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-001 §4 P1–P12 |
| **Approval authority** | Ops lead + architecture lead |
| **Approval output** | Principles ratified — including P4/P5/P7 (Director ≠ sysadmin; ≠ HR_ENROLLMENT_MANAGER) |
| **Implementation readiness** | OPS-030 forbidden from grant-copy or title-inference binding |

#### WP-B3 — Кадровое решение model

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-001 §5.1; Director contour `(78, 62)` rejected status; ADR-045 executive read scope |
| **Approval authority** | Executive sponsor + HR policy owner + ops lead |
| **Approval output** | Decision: (a) approve transitional `access_roles.code` for кадровое решение, or (b) record policy debt — Director remains **rejected** for all baseline bindings until future code exists |
| **Implementation readiness** | Director row in §7 cannot become `approved` until (a); Phase 2.6b may proceed without Director approval |

#### WP-B4 — HR operational class assignments

| Field | Value |
|-------|-------|
| **Inputs** | WP-B1 output; contours `(73, 86)` HR head, `(78, 77)` deputy admin; WP-X1 alignment |
| **Approval authority** | HR policy owner + ops lead + executive sponsor (deputy admin) |
| **Approval output** | Class assignment per contour: оформление vs контроль; transitional code mapping (`HR_ENROLLMENT_MANAGER` or none) |
| **Implementation readiness** | **Phase 2.6b MVP gate** — HR head `(73, 86)` `approved` enables first OPS-030 insert |

#### WP-B5 — Line-head informational boundary

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-001 §5.4; 13 rejected line-head rows; ACCESS-002 §3.1 personnel responsibility (WP-X1) |
| **Approval authority** | Ops lead + line management representative + HR policy owner |
| **Approval output** | Confirmed: line heads **rejected** for `HR_ENROLLMENT_MANAGER`; informational domain is negative boundary only |
| **Implementation readiness** | Prevents erroneous OPS-030 inserts for clinical/lab heads |

#### WP-B6 — Non-HR pending contours

| Field | Value |
|-------|-------|
| **Inputs** | §7 pending rows (statistics, QM, finance, generic titles, shared catalog `position_id=1`) |
| **Approval authority** | Ops lead + domain owner per contour |
| **Approval output** | Each row: `approved` + code, `rejected`, or `deferred` with rationale |
| **Implementation readiness** | Deferred rows excluded from OPS-030; do not block ACCESS-001 **Approved** if registered as debt |

#### WP-B7 — Matrix row disposition

| Field | Value |
|-------|-------|
| **Inputs** | All prior WP-B outputs; production ID verification note (§7 header) |
| **Approval authority** | Ops lead + architecture lead; HR policy owner for HR rows |
| **Approval output** | Final §7 matrix with every row dispositioned; **≥1** `approved` row |
| **Implementation readiness** | **Hard gate** — OPS-030 inserts only `policy_status=approved` rows |

#### WP-B8 — Open policy questions (ACCESS-001)

| Field | Value |
|-------|-------|
| **Inputs** | Transitional single-code model vs future atomic permissions; task-role-only contours; `access_roles` catalog gaps |
| **Approval authority** | Architecture lead + ops lead + HR policy owner |
| **Approval output** | Policy debt register; explicit statement that Phase 2.6 uses single-code transitional binding per ADR-053 |
| **Implementation readiness** | Clarifies Phase 2.6b scope boundary; atomic permissions remain future ADR |

### 4.4. Cross-track work packages

#### WP-X1 — Cross-layer boundary confirmation

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-001 §3; ACCESS-002 §7 shared examples; WP-A2 + WP-B1 outputs |
| **Approval authority** | Ops lead + HR policy owner + architecture lead |
| **Approval output** | Signed crosswalk table for shared contours (minimum: line head, HR head, Director, deputy admin) confirming orthogonal layers |
| **Implementation readiness** | Prevents conflation at OPS-030 and future management implementation |

#### WP-X2 — Document status promotion

| Field | Value |
|-------|-------|
| **Inputs** | All mandatory WPs closed on respective track; policy debt registers accepted |
| **Approval authority** | Ops lead + architecture lead (+ HR policy owner for ACCESS-001; + executive sponsor for ACCESS-002) |
| **Approval output** | Document status field updated to **Approved** with date and approver list |
| **Implementation readiness** | ACCESS-001 **Approved** unlocks OPS-030 planning; ACCESS-002 **Approved** unlocks management implementation planning |

#### WP-X3 — ADR-053 AC3 sign-off record

| Field | Value |
|-------|-------|
| **Inputs** | ACCESS-001 **Approved**; §7 approved rows; OPS-030 precondition checklist |
| **Approval authority** | Ops lead + architecture lead |
| **Approval output** | Recorded AC3 closure in ADR-053 decision log or linked sign-off annex; OPS-030 status may move from Blocked to Ready |
| **Implementation readiness** | **Phase 2.6b execution gate open** (engineering + ops window remains) |

---

## 5. Relationship with implementation

Ratification **enables** implementation gates. It does **not** perform implementation.

### 5.1. Chain to Phase 2.6b

```text
ADR-053 (Accepted)
    │
    │  defines binding contract + AC3 requirement
    ▼
ACCESS-001 Policy Ratification
    │
    │  WP-B1…B7 → §7 approved rows
    │  WP-X2  → document **Approved**
    │  WP-X3  → AC3 satisfied
    ▼
ADR-053 AC3 — Closed
    │
    │  ops mapping annex = Approved ACCESS-001 §7
    ▼
OPS-030 (execution runbook)
    │
    │  insert permission_template_contour_rule
    │  apply backfill; validation SQL; shadow observation
    ▼
Phase 2.6b (production template binding)
    │
    │  legacy enforcement unchanged
    ▼
Shadow parity improvement (diagnostic only)
```

| Step | What ratification provides | What ratification explicitly does **not** do |
|------|---------------------------|-----------------------------------------------|
| **ADR-053 AC3** | Approved organizational mapping annex (ACCESS-001 §7) | Insert contour rules; populate `access_role_id` |
| **OPS-030** | Authorised row list + exception register | Run migrations in production without ops window |
| **Phase 2.6b** | Policy permission to execute blocked data step | Change guards, `/auth/me`, JWT, or grant tables |

### 5.2. ACCESS-002 and Phase 2.6

ACCESS-002 ratification **does not** participate in the Phase 2.6b chain. Management responsibilities, subtree scope, and derived capability groups are **out of scope** for `permission_template_contour_rule` per ADR-053 and ACCESS-002 §8.3.

ACCESS-002 **Approved** enables a **separate** future program:

```text
ACCESS-002 (Approved)
    ▼
Management responsibility matrix annex (WP-A7)
    ▼
Future OPS runbook (not yet numbered)
    ▼
Management Scope Resolver + legacy edge migration
```

No Phase 2.6b dependency exists on this chain.

### 5.3. Minimum viable unblock vs full ratification

| Milestone | Minimum ratification scope | Full program scope |
|-----------|---------------------------|-------------------|
| **Phase 2.6b first insert** | WP-B1, B2, B4, B7 (HR head row) + WP-X2 (ACCESS-001) + WP-X3 | All WP-B + debt register |
| **OPS-030 complete** | All contours intended for binding dispositioned in §7 | Same |
| **Program complete** | — | All WP-A + WP-B + WP-X; both documents **Approved** |

Engineering may assist with **inventory verification** (production contour IDs) during ratification, but engineering artefacts **do not substitute** for work-package approval (ACCESS-001 P11, ACCESS-002 M10).

---

## 6. Completion criteria

### 6.1. Policy Ratification program complete

The **Policy Ratification** phase is **complete** when all of the following hold:

| # | Criterion | Verification |
|---|-----------|--------------|
| C1 | ACCESS-001 status = **Approved** | Document status field + WP-X2 record |
| C2 | ACCESS-002 status = **Approved** | Document status field + WP-X2 record |
| C3 | All mandatory work packages (§3) closed on both tracks | Ratification register indexed by WP ID |
| C4 | ACCESS-001 §7 — every row has final `policy_status` | Matrix audit: no `pending` without explicit deferral in debt register |
| C5 | ACCESS-002 contour responsibility annex exists (WP-A7) | Annex published alongside Approved document |
| C6 | Policy debt registers (WP-A8, WP-B8) published | Each open item has owner and target phase |
| C7 | WP-X1 crosswalk signed for all shared archetype contours | Crosswalk annex |
| C8 | No ratification record asserts runtime authority transfer | Explicit statement: legacy enforcement unchanged |

### 6.2. Phase 2.6b readiness (subset)

Phase 2.6b may be **ready for execution** before the full program completes (C1–C8), when:

| # | Criterion |
|---|-----------|
| R1 | ACCESS-001 **Approved** (C1) |
| R2 | ADR-053 AC3 closed (WP-X3 / C1 + approved annex) |
| R3 | ≥1 §7 row with `policy_status=approved` and verified production IDs |
| R4 | OPS-030 preconditions checklist complete |
| R5 | Phase 2.6a engineering accepted (already satisfied) |

R1–R5 are **necessary and sufficient** for OPS-030 execution. C2 (ACCESS-002 **Approved**) is **not** among them.

### 6.3. Explicit non-completion states

| State | Meaning |
|-------|---------|
| **Reviewed** (current) | Architecture validation done; organizational approval not done; Phase 2.6b blocked |
| **ACCESS-001 Approved only** | Phase 2.6b chain may open; Policy Ratification program **not** complete (C2, C5 unset) |
| **Partial WP closure** | Progress recorded; document remains **Reviewed** until WP-X2 |
| **Approved with policy debt** | Valid end state if debt register is complete and deferred items do not block approved rows |

### 6.4. Ratification register (recommended artefact)

Maintain a lightweight **ratification register** (spreadsheet or markdown annex) with:

- Work package ID
- Date ratified
- Approvers
- Linked contours / sections
- Policy debt items spawned
- Blocked downstream consumers (if any)

The register is a **governance artefact**, not a runtime configuration source.

---

## 7. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial planning document — Policy Ratification program for ACCESS-001 / ACCESS-002 |
