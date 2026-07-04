# WP-B3 — Problem Space Review (Executive HR Decision Model)

## Status

**Complete (analysis)** — 2026-07-04

Governance analysis defining the **Problem Space** of WP-B3 under [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) (Tier G, Phase G1). Precedes any solution design or Review Board decision session. **No runtime effect.** **No solutions proposed.**

| Field | Value |
|-------|-------|
| Work package | WP-B3 — Executive HR Decision Model |
| Prior artefact | [WP-B3-PROGRAM-INITIATION.md](./WP-B3-PROGRAM-INITIATION.md) |
| Question answered | *What governance problem must WP-B3 solve?* |
| Question not answered | *How should it be solved?* |

---

## 1. Purpose

### Governance objective of this review

This document performs the **Problem Space analysis** for WP-B3 — the step that precedes solution design, Review Board brief preparation, and ratification sessions.

| Objective | Detail |
|-----------|--------|
| **Identify the problem** | State precisely what organizational governance capability is missing after WP-B1 and WP-B2 |
| **Bound the problem** | Separate established facts, fixed constraints, and open questions from solution space |
| **Prepare Review Board** | Refine governance questions so a future session addresses the problem, not adjacent work packages |
| **Exclude solutions** | No organizational class design, no transitional codes, no implementation model, no contour dispositions |

### Relationship to program initiation

[WP-B3-PROGRAM-INITIATION.md](./WP-B3-PROGRAM-INITIATION.md) **opened** the work package and listed scope, dependencies, and preliminary questions. This review **analyses** whether those inputs constitute a well-defined problem space — without answering the questions or recommending a solution path.

---

## 2. Existing Governance Baseline

Established facts inherited from prior governance and normative documents. **No interpretation.** **No solutions.**

### WP-B1 — Permission Domain Taxonomy

| Fact | Source |
|------|--------|
| Work package substantively complete — 2026-07-04 | [WP-B1-CLOSURE-REPORT.md](./WP-B1-CLOSURE-REPORT.md) |
| Formal status **Open** — attestation signatures pending (HR policy owner + ops lead + architecture lead) | WP-B1 closure report §Remaining signatures |
| Four permission domains recorded via four Review Board sessions | WP-B1 closure report §Completed review sessions |
| `PD-5.1` (Кадровое решение) — decision **Ratified with Policy Debt** | WP-B1 package §6 |
| `PD-5.2`, `PD-5.4` — **Ratified** without policy debt | WP-B1 package §6 |
| `PD-5.3` — **Ratified with Policy Debt** (DEBT-B1-004 → WP-B4 / WP-B8) | WP-B1 package §6.1 |
| **DEBT-B1-001** recorded — transitional `access_roles.code` for кадровое решение not defined; resolution WP → **WP-B3** | WP-B1 package §6.1 |
| No `access_roles` code defined for `PD-5.1` in Reviewed ACCESS-001 | WP-B1 PD-5.1 review sheet |
| `HR_ENROLLMENT_MANAGER` **must not** represent PD-5.1 class | WP-B1 PD-5.1 review sheet; ACCESS-001 §5.1 |
| Director contour `(1, 78, 62)` — `policy_status=rejected` for `SYSADMIN_CABINET` | ACCESS-001 §7 |
| WP-B1 produced **no** §7 approvals, **no** OPS-030 authority, **no** runtime effect | WP-B1 closure report |

### WP-B2 — Binding Principles

| Fact | Source |
|------|--------|
| Work package substantively complete — 2026-07-04 | [WP-B2-BINDING-PRINCIPLES-REVIEW.md](./WP-B2-BINDING-PRINCIPLES-REVIEW.md) |
| Formal status **Open** — attestation signatures pending (ops lead + architecture lead) | WP-B2 review §12 |
| Review Board Session 1 complete — decision **Ratified with Policy Debt** | WP-B2 review §11 |
| Principles P1–P12 ratified as organizational binding rules | WP-B2 review §11 |
| **P4** — organizational position alone does not confer `SYSADMIN_CABINET` — ratified | ACCESS-001 §4; WP-B2 review |
| **P5** — Director / Acting Director ≠ sysadmin; ≠ `HR_ENROLLMENT_MANAGER` by title — ratified | ACCESS-001 §4; WP-B2 review |
| **P7** — negative prohibition ratified: no `HR_ENROLLMENT_MANAGER` or `SYSADMIN_CABINET` substitute for кадровое решение; positive class **not defined** | WP-B2 review §P7 |
| **DEBT-B2-001** recorded — positive кадровое решение class deferred; resolution WP → **WP-B3**; cross-ref DEBT-B1-001 | WP-B2 review §11.1 |
| WP-B2 ratification **does not** approve §7 rows, OPS-030, or ACCESS-001 **Approved** status | WP-B2 review §11 |
| Implementation gates unchanged after WP-B2 | WP-B2 review §12 |

### ACCESS-001 — Organizational Permission Matrix

| Fact | Source |
|------|--------|
| Document status **Reviewed** — 2026-07-04 | ACCESS-001 header |
| §5.1 defines Кадровое решение — typical holders: Director / Acting Director | ACCESS-001 §5.1 |
| §5.1 meaning: right and duty to **approve** кадровые решения (hire, transfer, dismiss, appoint acting duties) | ACCESS-001 §5.1 |
| §5.1 stance: requires separate decision/approval permission class on Cabinet baseline; **not modeled** in Reviewed text | ACCESS-001 §5.1 |
| §5.5: class clarification precedes OPS-030 insert | ACCESS-001 §5.5 |
| §7: no row has `policy_status=approved` | ACCESS-001 §7 summary |
| §7 Director row `(1, 78, 62)`: `SYSADMIN_CABINET` **rejected**; requires separate кадровое решение class (§5.1) — not defined | ACCESS-001 §7 |
| **Approved** status required before OPS-030 / Phase 2.6b | ACCESS-001 header; §6 |

### ACCESS-002 — Organizational Management Authority Model

| Fact | Source |
|------|--------|
| Document status **Reviewed** — 2026-07-04 | ACCESS-002 header |
| Defines management responsibilities — orthogonal to ACCESS-001 permission domains | ACCESS-001 §3; ACCESS-002 §7 |
| **Does not** gate OPS-030 or Phase 2.6b | ACCESS-002 header |
| Executive management responsibilities (organizational information, responsibility for results) are ACCESS-002 scope — not ACCESS-001 permission classes | ACCESS-001 §3; WP-B1 PD-5.1 review sheet |
| P12 ratified: ACCESS-001 and ACCESS-002 are orthogonal | WP-B2 review |

### ADR-050 — Organization Position & Position Cabinet

| Fact | Source |
|------|--------|
| Status **Accepted** | ADR-050 header |
| Permission Template lives inside Position Cabinet (1:1) | ADR-050; ADR-053 §2.1 |
| Permissions are configuration on Cabinet — not assigned to Platform User or Person | ADR-053 §2.1 |

### ADR-051 — Cabinet Access Resolution

| Fact | Source |
|------|--------|
| Status **Accepted** | ADR-051 header |
| Template load → expand → union into Effective Permission Set | ADR-051 |
| Enforcement cutover not in Phase 2.6 scope | ADR-053; ADR-051 §10 |
| `access_grants` remain exception overlay during Phase 2.6 | ACCESS-001 P3; ADR-053 §3.5 |

### ADR-053 — Permission Template Binding Model

| Fact | Source |
|------|--------|
| Status **Accepted** | ADR-053 header |
| Phase 2.6a engineering **accepted**; Phase 2.6b **blocked on AC3** | ADR-053 header |
| **AC3 Pending** — ops mapping annex required before production backfill | ADR-053 §11 AC3 |
| Binding uses `access_roles` namespace (transitional) | ADR-053 §2.2 |
| Contour rules stored in `permission_template_contour_rule` | ADR-053 |
| Must not derive bindings from `users.role_id`, user grants, or current occupant (§3.4) | ADR-053; ACCESS-001 P2 |
| Architecture Freeze in effect — no ADR amendment from WP-B3 | Master Plan §1.1 |

### Program baseline

| Fact | Source |
|------|--------|
| [TIER-G-GOVERNANCE-PROGRESS-REPORT.md](./TIER-G-GOVERNANCE-PROGRESS-REPORT.md) is authoritative program snapshot until superseded | Tier G report §11 |
| WP-B3 initiated — 2026-07-04 | [WP-B3-PROGRAM-INITIATION.md](./WP-B3-PROGRAM-INITIATION.md) |
| Master Plan sequence: `WP-B1 → WP-B2 → WP-B3 → WP-B4 → …` | ACCESS-RATIFICATION-PROGRAM §2.1 |

---

## 3. Problem Statement

### What governance capability is currently missing?

After WP-B1 and WP-B2, the organization has:

- An **accepted domain name** (`PD-5.1` — Кадровое решение) with defined organizational meaning (executive approval of hire, transfer, dismiss, acting appointment).
- **Accepted negative rules** prohibiting substitute baseline codes (`HR_ENROLLMENT_MANAGER`, `SYSADMIN_CABINET`) and title-inferred binding for Director / Acting Director (P4, P5, P7 negative).
- A **rejected** Director contour row with no approved alternative class.
- **Recorded policy debt** (DEBT-B1-001, DEBT-B2-001) pointing to WP-B3.

What the organization **does not** have:

> A **positive organizational permission class** for Executive HR Decision authority — the governance definition that states what PD-5.1 **is** as an assignable permission class on Position Cabinet baseline, distinct from what it is **not**.

Without this positive class (or an explicit, attested decision to defer it with recorded rationale), the organization cannot:

- Complete the governance model for domain `PD-5.1` beyond taxonomy and prohibitions.
- Inform WP-B7 whether Director contour `(78, 62)` may ever move toward `approved` and under what class.
- Close DEBT-B1-001 and DEBT-B2-001 as a coherent single outcome.
- Satisfy ACCESS-001 §5.5 precondition ("class clarification precedes OPS-030 insert") for any executive contour — without WP-B3, class clarification for PD-5.1 remains open.

**The missing capability is governance definition, not engineering implementation.**

### Why can WP-B1 and WP-B2 not resolve it?

| Work package | What it was authorized to decide | Why it stopped short |
|--------------|----------------------------------|----------------------|
| **WP-B1** | Whether four permission **domains** are accepted as organizational vocabulary | Scope was **taxonomy ratification** — accept domain boundaries and meaning. WP-B1 explicitly deferred positive class and `access_roles.code` mapping to WP-B3 (DEBT-B1-001). Ratifying PD-5.1 "with Policy Debt" was the designed outcome, not a failure. |
| **WP-B2** | Whether binding **principles** P1–P12 are accepted as organizational rules | Scope was **principle ratification** — including P7's negative prohibition. WP-B2 explicitly deferred P7's **positive** class definition to WP-B3 (DEBT-B2-001). Ratifying P7 "with Policy Debt" was the designed outcome. |

WP-B1 and WP-B2 are **structurally incapable** of closing this gap: their approval outputs per ACCESS-RATIFICATION-PROGRAM are taxonomy acceptance and principle ratification — not positive permission class design. Both work packages **recorded** the gap as policy debt and assigned resolution to WP-B3 by design.

### Why does the Master Plan introduce WP-B3?

Per [POSITION-CABINET-IMPLEMENTATION-MASTER-PLAN](../roadmap/POSITION-CABINET-IMPLEMENTATION-MASTER-PLAN.md) and [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md):

| Reason | Detail |
|--------|--------|
| **Mandatory work package** | WP-B3 is mandatory for ACCESS-001 **Approved** on Track B |
| **Director gap** | §5.1 class must exist (or debt be explicitly continued) before Director contour row may be dispositioned in WP-B7 |
| **First class-decision cycle** | WP-B3 is the first package requiring a **positive organizational class decision**, not vocabulary or rule acceptance |
| **Policy debt convergence** | DEBT-B1-001 and DEBT-B2-001 both assign resolution to WP-B3 |
| **Downstream chain** | WP-B4, WP-B7, WP-X2, WP-X3, and AC3 consume WP-B3 output — but WP-B3 does not execute any downstream step |

WP-B3 exists because the Master Plan separates **"what domains exist"** (WP-B1), **"what binding rules apply"** (WP-B2), and **"what positive class PD-5.1 is"** (WP-B3) into distinct governance decisions.

---

## 4. Existing Constraints

Constraints already fixed. WP-B3 must operate **within** these; it cannot relax them without a separate architecture amendment program.

### Architecture

| Constraint | Source |
|------------|--------|
| Architecture Design **complete**; Architecture Freeze **in effect** | Master Plan §1.1 |
| ARCH-001, ADR-050, ADR-051, ADR-053 — **Accepted**; not subject to WP-B3 redesign | ADR headers |
| Authority follows Position occupancy, not Platform User attributes | ARCHITECTURE_GOVERNANCE; ARCH-001 |
| Permission Template on Cabinet (1:1); binding is Cabinet configuration | ADR-050; ADR-053 |
| Transitional binding namespace is `access_roles` (not `roles`) | ADR-053 §2.2 |
| No binding from `users.role_id`, user grants, or occupant inference | ADR-053 §3.4; ACCESS-001 P2 |
| Phase 2.6a accepted; Phase 2.6b blocked on AC3 | ADR-053 §11 |
| `access_grants` remain overlay through Phase 2.6; no grant removal | ADR-053 §3.5 |
| AC3 ops mapping annex required before production backfill | ADR-053 AC3 |

### Policy

| Constraint | Source |
|------------|--------|
| ACCESS-001 status **Reviewed** — not **Approved** | ACCESS-001 header |
| ACCESS-002 status **Reviewed** — orthogonal layer | ACCESS-002 header |
| PD-5.1 domain meaning fixed in §5.1 (approve кадровые решения) | ACCESS-001 §5.1 |
| `HR_ENROLLMENT_MANAGER` **must not** represent PD-5.1 | ACCESS-001 §5.1; P6; P7 |
| Director / Acting Director **must not** receive `SYSADMIN_CABINET` or `HR_ENROLLMENT_MANAGER` by title | P4; P5; P7 (ratified WP-B2) |
| Separate кадровое решение class **required** if modeled on baseline — class **not defined** | P7 (ratified WP-B2) |
| Class clarification precedes OPS-030 insert | ACCESS-001 §5.5 |
| Director contour `(78, 62)` — `SYSADMIN_CABINET` **rejected** | ACCESS-001 §7 |
| No §7 row is `approved` | ACCESS-001 §7 |
| ADR-045 executive read scope is **not** substitute for PD-5.1 | WP-B1 PD-5.1 review sheet |
| ACCESS-001 and ACCESS-002 are orthogonal (P12 ratified) | WP-B2 review |

### Governance

| Constraint | Source |
|------------|--------|
| WP-B1 and WP-B2 substantively complete; attestation pending — does not block WP-B3 | ACCESS-RATIFICATION-PROGRAM sequencing |
| DEBT-B1-001 and DEBT-B2-001 assigned to WP-B3 resolution | WP-B1 §6.1; WP-B2 §11.1 |
| WP-B3 approval authority: executive sponsor + HR policy owner + ops lead | ACCESS-RATIFICATION-PROGRAM §4.1 |
| WP-B3 does not approve §7 rows (WP-B7), promote ACCESS-001 (WP-X2), or authorize OPS-030 | WP-B3 initiation §4 |
| Engineering artefacts do not substitute for work-package approval (P11 ratified) | WP-B2 review |
| Phase 2.6b MVP may proceed without Director approval if debt continued | ACCESS-RATIFICATION-PROGRAM WP-B3 |

### Runtime

| Constraint | Source |
|------------|--------|
| Legacy enforcement (`access_grants`, `users.role_id`) remains **authoritative** | Master Plan §1.3 |
| OPS-030 **Blocked** — ADR-053 AC3 Pending | OPS-030 header |
| No `permission_template_contour_rule` inserts authorized | ACCESS-001 §9; OPS-030 |
| WP-B3 initiation and completion produce **no** runtime effect | WP-B3 initiation |
| All 34 active templates have `role_id IS NULL` — binding deferred by design | ADR-053 §2.3 |

---

## 5. Inputs entering WP-B3

Every document and policy debt that enters WP-B3 as input.

### Normative and architectural inputs

| Input | Status | Role |
|-------|--------|------|
| [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md) | **Reviewed** | §5.1 domain text; §4 P5, P7; §7 Director row |
| [ACCESS-002](./ACCESS-002-organizational-management-authority-model.md) | **Reviewed** | Orthogonality boundary for executive contours |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) | **Accepted** | Cabinet as permission configuration anchor |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | **Accepted** | Resolver contract; no grant-copy |
| [ADR-053](../adr/ADR-053-permission-template-binding-model.md) | **Accepted** | Transitional binding model; AC3 gate |
| [ARCH-001](../architecture/ARCH-001-position-permission-model.md) | **Accepted** | Domain architecture baseline |
| [ARCHITECTURE_GOVERNANCE](../architecture/ARCHITECTURE_GOVERNANCE.md) | **Active** | Architecture baseline principles |
| [ADR-045](../adr/ADR-045-personnel-hr-processes-split.md) | Related | Executive read scope — runtime; not policy owner for PD-5.1 |

### Governance artefact inputs

| Input | Status | Role |
|-------|--------|------|
| [WP-B1 Closure Report](./WP-B1-CLOSURE-REPORT.md) | Prepared | PD-5.1 ratification summary; debt pointer |
| [WP-B1 Permission Domain Ratification Package](./WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md) | Open | PD-5.1 review sheet; §6.1 debt register |
| [WP-B2 Binding Principles Review](./WP-B2-BINDING-PRINCIPLES-REVIEW.md) | Open | P7 analysis; §11.1 debt register |
| [PERMISSION-DOMAIN-REGISTRY](./PERMISSION-DOMAIN-REGISTRY.md) | Updated | `PD-5.1` ratification status |
| [TIER-G Governance Progress Report](./TIER-G-GOVERNANCE-PROGRESS-REPORT.md) | Active baseline | Program snapshot |
| [WP-B3 Program Initiation](./WP-B3-PROGRAM-INITIATION.md) | Open (initiated) | Scope, questions, success criteria |
| [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) §4.3 WP-B3 | Active | Approval authority; expected output types |

### Policy debts entering WP-B3

| Debt ID | Source | Item | Why it enters WP-B3 |
|---------|--------|------|---------------------|
| **DEBT-B1-001** | WP-B1 — `PD-5.1` taxonomy layer | Transitional `access_roles.code` for кадровое решение / executive HR decision authority not defined | WP-B1 ratified the domain but recorded that **positive class and code mapping** are undefined. Resolution WP explicitly assigned: **WP-B3**. |
| **DEBT-B2-001** | WP-B2 — P7 principles layer | Positive кадровое решение permission class not defined; negative prohibition ratified | WP-B2 ratified that a **separate class is required** but recorded that the **positive definition** is undefined. Resolution WP explicitly assigned: **WP-B3**. Cross-references DEBT-B1-001. |

**Convergence fact:** DEBT-B1-001 and DEBT-B2-001 describe one organizational gap at two governance layers. Both enter WP-B3 as a **single problem**, not two independent problems.

---

## 6. Questions that WP-B3 must answer

Refined from the sixteen questions in [WP-B3-PROGRAM-INITIATION.md](./WP-B3-PROGRAM-INITIATION.md) §7. **No answers recorded.**

### Mandatory

Questions WP-B3 **must** answer to close the problem space and produce a ratifiable governance outcome.

| ID | Question |
|----|----------|
| **M1** | What constitutes **Executive HR Decision authority** in organizational terms — distinct from HR document preparation (PD-5.2), enrollment execution, HR oversight visibility (PD-5.3), and management responsibilities (ACCESS-002)? |
| **M2** | Which organizational actions fall within кадровое **решение** (approve hire, transfer, dismiss, appoint acting duties) versus кадровое **оформление** (PD-5.2)? |
| **M3** | What is the **positive organizational permission class** for `PD-5.1` — the minimum governance definition required to close DEBT-B1-001 and DEBT-B2-001? |
| **M4** | How is qualification for this class expressed on a **Position Cabinet contour** without relying on job title alone — consistent with P1 and Architecture Baseline principle 5? |
| **M5** | How does **Acting Director** (исполняющий обязанности) relate to the Executive HR Decision class? |
| **M6** | How is the permission class **separated from ACCESS-002** executive management responsibilities (organizational information, responsibility for results, subtree scope)? |
| **M7** | What is the **governance disposition** of DEBT-B1-001 and DEBT-B2-001 — closed with a defined class, or continued with explicit rationale, owner, and implications for Director contour binding? |
| **M8** | How does **ADR-045 executive read scope** relate to PD-5.1 — complementary mechanism versus substitute for the permission class? |

### Supporting

Questions that clarify process, confirm established facts, or strengthen the ratification record. WP-B3 may address them in session; they are not the core undefined capability.

| ID | Question | Note |
|----|----------|------|
| **S1** | Why does Director contour `(1, 78, 62)` remain **rejected** for `SYSADMIN_CABINET` and `HR_ENROLLMENT_MANAGER` pending WP-B3? | Largely **established** by P4, P5, P7 and §7 — session may confirm, not rediscover |
| **S2** | What class would be **required** for any future `approved` disposition of Director contour `(78, 62)`? | Follows from M3 outcome; frames WP-B7 dependency without approving a row |
| **S3** | How is **positive class definition** separated from **contour binding and execution** — what does WP-B3 decide vs what WP-B7 and OPS-030 own? | Process boundary; reduces implementation leakage risk |
| **S4** | If no transitional `access_roles.code` is approved at governance level, what **continued policy debt** must be recorded — and is Phase 2.6b MVP (HR head contour only) still valid per program rules? | Debt-continuation path; MVP validity is **already stated** in ACCESS-RATIFICATION-PROGRAM — session confirms applicability |
| **S5** | Which **architectural constraints** are fixed and not subject to WP-B3 redesign? | Documented in §4 of this review and WP-B3 initiation §8 — Review Board acknowledgment |
| **S6** | Does WP-B3 require ACCESS-002 **Approved** as precondition, or only informative alignment per P12? | **Already answered** in program: not a hard precondition for WP-B3; orthogonal layers |
| **S7** | Who must attest the outcome (executive sponsor, HR policy owner, ops lead) and what ratification record wording prevents misread as OPS-030 or §7 authorization? | Defined in ACCESS-RATIFICATION-PROGRAM §4.1 — session applies to WP-B3 record |

### Out of scope

Questions that belong to other work packages or implementation. WP-B3 Review Board must **not** treat these as in-scope decisions.

| ID | Topic | Owner |
|----|-------|-------|
| **O1** | Selection or engineering of a specific `access_roles.code` in the catalog | WP-B8 / engineering — if governance approves a class name, catalog mapping is downstream |
| **O2** | §7 contour `policy_status` disposition for Director or any contour | **WP-B7** |
| **O3** | HR head `(73, 86)` or deputy admin `(78, 77)` class and code assignment | **WP-B4** |
| **O4** | HR oversight visibility class / DEBT-B1-004 | **WP-B4** / **WP-B8** |
| **O5** | Line-head informational boundary confirmation | **WP-B5** |
| **O6** | ACCESS-001 **Reviewed** → **Approved** promotion | **WP-X2** |
| **O7** | ADR-053 AC3 sign-off | **WP-X3** |
| **O8** | OPS-030 execution, `permission_template_contour_rule` insert, backfill | **Tier B** |
| **O9** | ACCESS-002 management responsibility ratification | **Track A** (WP-A*) |
| **O10** | Cross-layer shared-contour crosswalk | **WP-X1** |
| **O11** | Runtime binding, schema change, grant mutation | Engineering / ops — separate gates |

### Refinement summary

| Category | Count | Change from initiation §7 |
|----------|-------|---------------------------|
| **Mandatory** | 8 | Condensed from 16 — merged overlapping class/Cabinet/debt questions; removed process questions with fixed answers |
| **Supporting** | 7 | Process, confirmation, and anti-leakage framing |
| **Out of scope** | 11 | Explicitly excluded adjacent packages and implementation |

---

## 7. Success Definition

What WP-B3 **success** means in governance terms only. No implementation outcomes.

### Successful WP-B3 produces

| Outcome | Description |
|---------|-------------|
| **Positive class defined** | Organization has a ratified **positive permission class** for `PD-5.1` — stated in organizational terms, separable from PD-5.2, PD-5.3, PD-5.4, and ACCESS-002 |
| **Or debt explicitly continued** | Organization has a ratified decision to **defer** positive class with recorded rationale, owner, and explicit implications (Director contour binding remains blocked) |
| **Debts dispositioned** | DEBT-B1-001 and DEBT-B2-001 are **closed** (coherent with class definition) or **continued** (coherent recorded deferral) — single outcome, not contradictory states |
| **Orthogonality affirmed** | Ratification record states permission class does not substitute ACCESS-002 management responsibilities |
| **Boundary affirmed** | Ratification record states outcome does not approve §7 rows, promote ACCESS-001 to **Approved**, authorize OPS-030, or change runtime behaviour |
| **Authority satisfied** | Executive sponsor + HR policy owner + ops lead signatures recorded |
| **Traceability** | Outcome recorded in governance artefacts; downstream packages (WP-B4, WP-B7, WP-B8) can reference decision without ambiguity |

### Successful WP-B3 does not require

| Non-requirement | Reason |
|-----------------|--------|
| A specific `access_roles.code` in production catalog | Catalog is implementation; class may be defined without code approval |
| Director contour `approved` | Contour disposition is WP-B7 |
| ACCESS-001 **Approved** | Document promotion is WP-X2 |
| ADR-053 AC3 closure | AC3 is WP-X3 |
| OPS-030 readiness | Tier B follows G2 |
| Any runtime or database change | Governance-only work package |

### Failure modes (problem space not resolved)

| Mode | Description |
|------|-------------|
| **Unresolved gap** | Session ends without positive class definition and without explicit continued debt |
| **Contradictory outcome** | DEBT-B1-001 closed while DEBT-B2-001 continued with incompatible statements |
| **Layer conflation** | Outcome conflates permission class with ACCESS-002 responsibility or ADR-045 read scope |
| **Title coupling** | Outcome defines class by job title alone, contradicting P1 and Architecture Baseline |
| **Implementation leakage** | Outcome reads as OPS-030 authorization, §7 approval, or contour insert permission |

---

## 8. Risks

Governance risks specific to WP-B3 problem space and Review Board preparation. Not implementation or technical risks.

| ID | Risk | Description | Problem-space relevance |
|----|------|-------------|-------------------------|
| **GR-B3-01** | **Accidental architecture redesign** | WP-B3 session proposes changes to ADR-050/051/053 binding contract, Cabinet model, or resolver semantics | Problem is **policy class definition** within frozen architecture — not contract amendment |
| **GR-B3-02** | **Implementation leakage** | Ratification record or session discussion treated as OPS-030 authorization, AC3 satisfaction, or Phase 2.6b unblock | Problem is **governance definition** — implementation gates remain unchanged at WP-B3 exit |
| **GR-B3-03** | **Role-title coupling** | Executive HR Decision class defined by «Директор» title rather than Cabinet contour and occupancy | Contradicts P1, P5, P7, and Architecture Baseline principle 5 — would misstate the problem as title assignment |
| **GR-B3-04** | **Cabinet/title confusion** | Conflation of catalog position name, Position Cabinet contour, and permission class holder | Problem requires class on **Cabinet baseline** — contour `(1, 78, 62)` is context, not the class definition itself |
| **GR-B3-05** | **Premature contour approval** | Session approves Director §7 row or implies `policy_status=approved` | Contour disposition is **WP-B7** — WP-B3 owns class only |
| **GR-B3-06** | **Substitute code reintroduction** | Pressure to assign `HR_ENROLLMENT_MANAGER` or `SYSADMIN_CABINET` to Director pending "temporary" class | Violates ratified P5, P7 negative rules — problem is **positive class**, not substitute |
| **GR-B3-07** | **ACCESS-002 conflation** | Executive management responsibilities treated as satisfying PD-5.1 | Violates ratified P12 and WP-B1 PD-5.1 boundary — orthogonal layers |
| **GR-B3-08** | **ADR-045 substitution** | Executive read scope treated as PD-5.1 permission class | WP-B1 explicitly excluded ADR-045 as substitute — problem remains organizational class |
| **GR-B3-09** | **Split debt outcome** | DEBT-B1-001 and DEBT-B2-001 resolved inconsistently | Single gap at two layers — must produce one coherent disposition |
| **GR-B3-10** | **False Phase 2.6b dependency** | Stakeholders believe WP-B3 must complete before any Track B planning | Program allows MVP without Director; WP-B3 blocks **Director binding**, not all AC3 paths |

---

## 9. Readiness Assessment

### Is the Problem Space sufficiently understood?

| Criterion | Assessment |
|-----------|------------|
| Missing capability identified | **Yes** — positive organizational permission class for `PD-5.1` |
| Why WP-B1/WP-B2 insufficient | **Yes** — taxonomy and negative rules by design; debt assigned to WP-B3 |
| Why Master Plan requires WP-B3 | **Yes** — mandatory class-decision work package; Director gap |
| Constraints catalogued | **Yes** — architecture, policy, governance, runtime (§4) |
| Inputs and debts enumerated | **Yes** — documents and DEBT-B1-001 / DEBT-B2-001 (§5) |
| Questions refined and scoped | **Yes** — 8 mandatory, 7 supporting, 11 out of scope (§6) |
| Success and failure modes defined | **Yes** — governance outcome only (§7) |
| Risks identified | **Yes** — governance risks including leakage and conflation (§8) |
| Solution space excluded | **Yes** — no class, code, or binding proposed in this document |

### WP-B3 Review Board preparation readiness

| Question | Assessment |
|----------|------------|
| Is the governance problem precisely stated? | **Yes** |
| Are mandatory questions distinguishable from out-of-scope? | **Yes** |
| Are fixed constraints explicit enough to prevent architecture redesign in session? | **Yes** |
| Are policy debts and their convergence documented? | **Yes** |
| Are WP-B1 and WP-B2 outputs sufficient as inputs? | **Yes** — substantive complete; attestation pending does not block |
| Are architectural contradictions identified in problem space? | **None identified** — problem is undefined positive class within consistent negative rules |
| Can Review Board brief preparation begin? | **Yes** |

**Finding:** The Problem Space is **sufficiently understood** to begin **WP-B3 Review Board preparation**.

**Explicit non-finding:** This assessment does **not** recommend any solution, class design, transitional code, or contour disposition. It confirms only that the **question** is well-formed and bounded.

### Recommended next artefact (informational)

Review Board brief preparation — following the pattern established for WP-B1 (`review-board/PD-5.*`) and WP-B2 (`review-board/WP-B2-REVIEW-BOARD-BRIEF.md`). Brief creation is **not** part of this problem space review deliverable.

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial problem space review — governance problem defined; questions refined; Review Board prep readiness assessed |
