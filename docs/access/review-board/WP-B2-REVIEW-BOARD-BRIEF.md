# Review Board Brief — WP-B2 Binding Principles

## ACCESS-001 §4 — Principles P1–P12 (unified package)

> Governance analysis: [WP-B2-BINDING-PRINCIPLES-REVIEW.md](../WP-B2-BINDING-PRINCIPLES-REVIEW.md)  
> Prior work: [WP-B1 Closure Report](../WP-B1-CLOSURE-REPORT.md)

## Document metadata

| Field | Value |
|-------|-------|
| Session | WP-B2 Review Board Session 1 |
| Date prepared | 2026-07-04 |
| Package | WP-B2 — Binding Principles |
| Object | ACCESS-001 §4 P1–P12 — **unified governance package** |
| Tier / phase | G — Governance / G1 — Policy Ratification |
| Status | **Decision recorded** — Ratified with Policy Debt (2026-07-04); attestation pending |
| Prior work | WP-B1 — four domains recorded (2026-07-04); attestation signatures pending |
| Sources | [ACCESS-001](../ACCESS-001-organizational-permission-matrix.md) §4; [ACCESS-RATIFICATION-PROGRAM](../ACCESS-RATIFICATION-PROGRAM.md) WP-B2; [WP-B2 review](../WP-B2-BINDING-PRINCIPLES-REVIEW.md) |
| Approval authority | Ops lead + architecture lead |
| Runtime effect | **None** |

---

## 1. Package purpose

WP-B2 ratifies **binding principles** — the organizational rules under which permission domains (WP-B1) may be bound to Position Cabinet Permission Template baselines and transitional `access_roles`.

| Question this package answers | Answer shape |
|--------------------------------|--------------|
| **What** is the binding subject? | Position Cabinet Template — not User, Person, or occupant (P1) |
| **What** may populate baseline binding? | Ops/architecture-approved policy only — not grant-copy or title inference (P2, P11) |
| **How** do baseline and legacy grants coexist? | Template baseline + `access_grants` overlay during Phase 2.6 (P3) |
| **What** binding mistakes are forbidden? | Sysadmin and `HR_ENROLLMENT_MANAGER` misuse by title or contour class (P4–P9) |
| **What** about unmapped Templates? | Allowed during shadow — data debt, not implicit deny (P10) |
| **How** do ACCESS-001 and ACCESS-002 relate? | Orthogonal layers — neither substitutes for the other (P12) |

**WP-B2 does not:** ratify permission domains (WP-B1 — done); define transitional codes (WP-B3/B4/B8); approve §7 rows (WP-B7); promote ACCESS-001 to **Approved** (WP-X2); authorize OPS-030 or Phase 2.6b.

**Program position:** `WP-B1 → WP-B2 → WP-B3 → …` — WP-B2 may proceed while WP-B1 attestation signatures remain pending.

---

## 2. Architectural base (Accepted — fixed)

Architecture Freeze. Review Board **does not redesign** these positions.

| ADR / doc | Fixed position relevant to P1–P12 |
|-----------|-----------------------------------|
| **ARCH-001** | Permissions follow Employment → Cabinet; not User-centric |
| **ARCHITECTURE_GOVERNANCE** | Cabinet = digital representation of Position; permissions follow Employment |
| **ADR-050** | Permission Template inside Position Cabinet 1:1; not assigned to User/Person |
| **ADR-051** | Cabinet Access Resolver; Template load + expand + union; legacy authoritative until cutover |
| **ADR-053 §3.4** | Binding by Position identity; **forbidden:** copy from `users.role_id`, user grants, occupant inference |
| **ADR-053 §3.5** | `access_grants` authoritative during Phase 2.6; baseline for future enforcement |
| **ADR-053 I7** | Empty binding → empty expansion; not deny signal in shadow mode |
| **ADR-053 AC2** | Phase 2.6 read-path / shadow — no enforcement flip from policy ratification |

**Architectural consistency:** No architectural contradiction identified ([WP-B2 review §4](../WP-B2-BINDING-PRINCIPLES-REVIEW.md#4-relationship-to-accepted-adrs)).

**Derivation split (factual):**

| Tier | Principles | Source |
|------|------------|--------|
| Architecture-derived | P1, P2, P3, P10 | ADR-050 / ADR-051 / ADR-053 |
| Governance policy on architecture | P4, P5, P6, P7, P8, P9, P11, P12 | ACCESS-001 §4 — organizational binding rules |

---

## 3. Overview — principles P1–P12

Single ratification object. Wording per [ACCESS-001 §4](../ACCESS-001-organizational-permission-matrix.md#4-principles) — not modified in this brief.

### 3.1 Foundation and mechanics

| # | Summary | Role in package |
|---|---------|-----------------|
| **P1** | Permission assigned to **Position Cabinet**, not User / Person / occupant | Binding subject |
| **P2** | Occupants and individual grants **not source of truth** for baseline; no grant-copy onto Templates | Binding population rule |
| **P3** | `access_grants` remain **exception overlay** during Phase 2.6; union at future enforcement | Coexistence rule |
| **P10** | **Unmapped Cabinet allowed** until matrix approval; NULL = data debt in shadow (ADR-053 I7) | Shadow-phase rule |

### 3.2 Class and contour prohibitions

| # | Summary | WP-B1 link |
|---|---------|------------|
| **P4** | No `SYSADMIN_CABINET` from organizational position alone | Executive / all contours |
| **P5** | Director ≠ sysadmin; ≠ `HR_ENROLLMENT_MANAGER` by title; ADR-045 read scope separate | Director contour |
| **P6** | `HR_ENROLLMENT_MANAGER` = **кадровое оформление**, not решение | PD-5.2 |
| **P7** | Separate **кадровое решение** class required; no substitute codes | PD-5.1 — positive class → WP-B3 |
| **P8** | Deputy admin / legal oversight ≠ HR processing by default; management visibility → ACCESS-002 | PD-5.3 |
| **P9** | Line heads ≠ HR processing; §5.4 boundary only; management visibility → ACCESS-002 | PD-5.4 |

### 3.3 Process and cross-document rules

| # | Summary | Role in package |
|---|---------|-----------------|
| **P11** | Engineering must **not infer** organizational policy from matrices or resolver mechanics | Approval gate |
| **P12** | ACCESS-001 and ACCESS-002 **orthogonal** — neither ratifies the other | Cross-track rule |

### 3.4 Package scope boundaries

**In scope for this session:**

- Ratification of **P1–P12 as a unified binding-principles package**.
- Confirmation that architecture-derived principles (P1–P3, P10) align with Accepted ADRs.
- Confirmation that governance principles (P4–P9, P11–P12) operationalize WP-B1 domain taxonomy without re-ratifying domains.

**Out of scope for this session:**

- ACCESS-001 §5 domain definitions — WP-B1 recorded.
- ACCESS-001 §7 row disposition — WP-B7.
- Transitional `access_roles.code` per domain — WP-B3, WP-B4, WP-B8.
- ACCESS-002 management responsibilities — Track A / WP-A*.
- OPS-030 / Phase 2.6b — Tier B; ACCESS-001 **Approved** + AC3.
- ACCESS-001 document status change — WP-X2.

---

## 4. Relationship to WP-B1 and downstream packages

| Package | Relationship |
|---------|--------------|
| **WP-B1** | Domain taxonomy recorded; P6–P9 express domain boundaries in binding vocabulary |
| **WP-B3** | P7 positive кадровое решение class — DEBT-B1-001 |
| **WP-B4** | P6/P8 semantic constraints; contour class + code mapping |
| **WP-B5** | P9 line-head negative boundary confirmation |
| **WP-B7** | §7 row `approved` — P10/P11 govern process only |
| **WP-X1** | P8/P9/P12 — shared contours require cross-layer sign-off before binding approvals |
| **OPS-030** | Forbidden from grant-copy / title-inference per WP-B2 output — execution gated separately |

---

## 5. Review questions requiring governance confirmation

**Not answered in this brief.**

| # | Question |
|---|----------|
| **Q1** | Does the organization accept **P1–P12 as a unified binding-principles package** for Position Cabinet Template baseline policy? |
| **Q2** | Are **P1, P2, P3, P10** accepted as consistent with Accepted ADR-050 / ADR-051 / ADR-053 without amending architecture? |
| **Q3** | Are **P4–P9** accepted as binding prohibitions operationalizing WP-B1 domain taxonomy (Director, HR processing, oversight, line boundary)? |
| **Q4** | Are **P11** (no engineering inference) and **P12** (ACCESS-001 / ACCESS-002 orthogonality) accepted as process and cross-document rules? |
| **Q5** | Is it acceptable to ratify this package **without** §7 row approval, OPS-030 authorization, or ACCESS-001 **Approved** status? |
| **Q6** | Is **P7** text referencing «this Draft» understood as a stale label — ACCESS-001 document status is **Reviewed** — without changing the substantive prohibition? |

---

## 6. Architectural answers already fixed

| Question | Fixed answer |
|----------|--------------|
| May baseline binding derive from user grants / shadow / occupant? | **No** — ADR-053 §3.4, P2, P11 |
| Are `access_grants` authoritative during Phase 2.6? | **Yes** — ADR-053 §3.5, P3 |
| Does principle ratification change enforcement? | **No** — ADR-053 AC2 |
| Does principle ratification authorize OPS-030? | **No** — ACCESS-001 **Reviewed**; §7 rows not approved; AC3 open |
| Does principle ratification approve §7 rows or domains? | **No** — domains WP-B1; rows WP-B7 |
| Does P12 ratify ACCESS-002 responsibilities? | **No** — orthogonal layers |
| Does P1–P12 require architecture redesign? | **No** |
| Is NULL Template binding an implicit deny in shadow? | **No** — ADR-053 I7, P10 |

---

## 7. Remaining governance questions

| # | Topic | Nature |
|---|-------|--------|
| **G1** | Unified package vs per-principle ratification | Process — Q1 |
| **G2** | Architecture-derived subset | Architectural alignment — Q2 |
| **G3** | Class prohibitions vs WP-B1 domains | Organizational — Q3 |
| **G4** | Process / orthogonality rules | Organizational — Q4 |
| **G5** | Scope boundary vs OPS-030 / Approved status | Process — Q5 |
| **G6** | P7 «Draft» terminology | Terminology — Q6 |

**Unresolved architectural questions:** None.

**Items deferred to later work packages (not WP-B2 blockers, not policy debt for P4):**

| Item | Principle | Resolution WP | Note |
|------|-----------|---------------|------|
| Positive кадровое решение class | P7 | WP-B3 (DEBT-B1-001) | Open gap — unlike P4 |
| Contour class + code mapping | P6, P8 | WP-B4 | Downstream assignment |
| §7 row disposition | P11 context | WP-B7 | Row approval |

**P4 after ratification:** **Nothing remains unfinished for P4.** The negative rule (no `SYSADMIN_CABINET` from organizational position alone) is complete; Director contour `(78, 62)` is already `rejected` in §7. The phrase «break-glass / explicit sysadmin policy» describes **where sysadmin may come from** (not from title) — not an open ACCESS-001 action item. Platform break-glass mechanics (grants, `role_id`, ADR-042) are **outside** ACCESS-001 §4 scope. WP-B8 inputs are transitional catalog / atomic permissions — **not** a dedicated «SysAdmin Policy» work package per [ACCESS-RATIFICATION-PROGRAM](../ACCESS-RATIFICATION-PROGRAM.md) WP-B8.

---

## 8. Readiness for Board decision

Factual assessment only — **does not recommend** Ratified / Deferred / Policy Debt.

| Criterion | Assessment |
|-----------|------------|
| Full principle set P1–P12 defined in ACCESS-001 §4 | Yes |
| Internal consistency across P1–P12 | Yes — [WP-B2 review §3](../WP-B2-BINDING-PRINCIPLES-REVIEW.md#3-cross-principle-consistency) |
| Alignment with Accepted ADRs | Yes — no contradictions |
| WP-B1 domain taxonomy recorded (P6–P9 context) | Yes |
| Materials sufficient for Board to render decision | Yes |

**Approval status:** Briefing complete — Board decision recorded in [WP-B2 review §11](../WP-B2-BINDING-PRINCIPLES-REVIEW.md#11-ratification-outcome).

**Board decision (recorded):** **Ratified with Policy Debt** — 2026-07-04. Policy debt **DEBT-B2-001** → **WP-B3** (see DEBT-B1-001). WP-B2 **open** pending ops lead + architecture lead attestation.

---

## 9. Risks

| ID | Risk | Mitigation (if applicable) |
|----|------|----------------------------|
| **R1** | WP-B2 ratification misread as OPS-030 or §7 authorization | Q5; P11; §5 out-of-scope |
| **R2** | P6–P9 ratified without WP-B1 domain context | WP-B1 decisions recorded; §3.2 WP-B1 links |
| **R3** | P2/P11 bypass — grant-copy binding | ADR-053 §3.4; WP-B2 ratification attestation |
| **R4** | P8/P9/P12 ignored at shared-contour binding | WP-X1 before WP-B4/B5/B7 approvals |
| **R5** | P7 «Draft» wording causes document-maturity confusion | Q6 |
| **R6** | P12 orthogonality lost when ACCESS-002 Track A progresses | Independent ratification tracks |

---

## 10. Possible policy debt items

**Recorded** — Board selected **Ratified with Policy Debt** (2026-07-04).

| Debt ID | Condition | Resolution WP | Status |
|---------|-----------|---------------|--------|
| **DEBT-B2-001** | P7 positive кадровое решение class ratification deferred at principles layer | **WP-B3** — see also DEBT-B1-001 | ☑ Recorded in [WP-B2 review §11.1](../WP-B2-BINDING-PRINCIPLES-REVIEW.md#111-policy-debt-register-wp-b2) |

---

## 11. Decision options (Review Board)

**Selected:** **Ratified with Policy Debt** — 2026-07-04 (recorded in [WP-B2 review §11](../WP-B2-BINDING-PRINCIPLES-REVIEW.md#11-ratification-outcome)).

| Option | Meaning |
|--------|---------|
| **Ratified** | Binding principles P1–P12 accepted as organizational rules for subsequent Track B work packages |
| **Ratified with Policy Debt** | Principles accepted; named item(s) in §10 recorded with owner and resolution WP |
| **Deferred** | Package not accepted; further policy work required before re-session |

**Session must not:** modify ACCESS-001 text; approve §7 rows; insert contour rules; open OPS-030; change runtime enforcement; promote ACCESS-001 to **Approved**.

---

## 12. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial WP-B2 Session 1 brief — unified P1–P12 package |
| 2026-07-04 | 0.2 | Removed DEBT-B2-002 — P4 negative rule complete; no WP-B2 policy debt for sysadmin |
| 2026-07-04 | 0.3 | Board decision **Ratified with Policy Debt** recorded in WP-B2 review §11 |
