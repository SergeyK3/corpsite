# Review Board Brief — WP-B1 Session 4

## PD-5.4 — Линейное информирование

> Template: [REVIEW-BOARD-BRIEF-TEMPLATE.md](./REVIEW-BOARD-BRIEF-TEMPLATE.md)

## Document metadata

| Field | Value |
|-------|-------|
| Session | WP-B1 Review Board Session 4 |
| Date prepared | 2026-07-04 |
| Domain ID | `PD-5.4` |
| Domain name | Линейное информирование |
| Work package | WP-B1 — Permission Domain Taxonomy |
| Tier / phase | G — Governance / G1 — Policy Ratification |
| Status | **Briefing only** — no ratification recorded |
| Prior sessions | PD-5.1 — Ratified with Policy Debt (2026-07-04); PD-5.2 — Session 2 brief prepared, not ratified; PD-5.3 — Session 3 brief prepared, not ratified; [WP-B1 package §6](../WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md#6-ratification-outcome) |
| Sources | [ACCESS-001](../ACCESS-001-organizational-permission-matrix.md) §5.4, P9, §3 visibility boundary; [PERMISSION-DOMAIN-REGISTRY](../PERMISSION-DOMAIN-REGISTRY.md); [WP-B1 package](../WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md) |
| Runtime effect | **None** |

---

## 1. Domain definition

| Field | Content |
|-------|---------|
| **Domain ID** | `PD-5.4` |
| **Name** | Линейное информирование (informational permission domain) |
| **Purpose** | HR informational permission domain — defines what baseline `access_roles` binding **must not** grant to line department heads; does not assign line-management responsibility |
| **Organizational meaning** | Line heads may need **information** on results of relevant кадровые процессы for their own staff — expressed as a **permission domain**, not as management remit or HR processing authority |
| **ACCESS-001 source** | [§5.4](../ACCESS-001-organizational-permission-matrix.md#54-линейное-информирование-informational-permission-domain); principle P9; [§3 visibility boundary](../ACCESS-001-organizational-permission-matrix.md#3-relationship-to-access-002) |
| **Registry entry** | [PERMISSION-DOMAIN-REGISTRY §3 — PD-5.4](../PERMISSION-DOMAIN-REGISTRY.md#pd-54--линейное-информирование) — **Defined (Reviewed)** — pending ratification |

---

## 2. Scope

PD-5.4 governs organizational permission policy for **line-head informational boundaries** on Cabinet Permission Template baseline — what baseline binding must **not** grant — distinct from HR execution, HR oversight, executive decision, sysadmin authority, and ACCESS-002 management responsibilities.

**In scope for Session 4:**

- Ratification of domain taxonomy.
- Boundary review vs PD-5.1, PD-5.2, PD-5.3, and ACCESS-002.
- Confirmation that PD-5.4 is an **informational permission-domain boundary**, not management authority.
- Review of twelve §7 line-head contours explicitly citing §5.4 — all `HR_ENROLLMENT_MANAGER` **rejected** (acknowledgment only — not row disposition change).
- Domain character assessment: negative boundary vs positive code assignment (per existing governance documents only).

**Out of scope for Session 4:**

- ACCESS-001 §7 row disposition changes — rows already `rejected`; formal WP-B5 boundary confirmation is downstream.
- OPS-030 / Phase 2.6b — Tier B.
- Positive `access_roles.code` definition for line heads — WP-B8 if ever required.
- PD-5.1 transitional code — WP-B3 (DEBT-B1-001).
- PD-5.2, PD-5.3 ratification outcomes — independent sessions.
- ACCESS-002 management responsibilities and subtree visibility — Track A / WP-A7.
- WP-X1 cross-layer boundary sign-off — before WP-B5 / shared-contour approvals.

### 2.1 Domain character (per existing governance documents only)

| Aspect | Stance in Reviewed policy |
|--------|---------------------------|
| **First-class permission domain** | **Yes** — PERMISSION-DOMAIN-REGISTRY R7: negative boundaries are domains, not absence of policy |
| **Negative boundary for baseline binding** | **Yes** — ACCESS-001 §5.4: defines what `access_roles` binding **must not** grant; «negative boundary (what not to bind)» |
| **Positive `access_roles` baseline** | **No** — «No approved `access_roles` baseline for §5.4 in this Draft»; none approved in Reviewed ACCESS-001 |
| **Organizational informational need** | **Described** in §5.4 Meaning — line heads may need information on staff process outcomes; expressed as domain vocabulary, **not** as an approved Cabinet baseline code grant |
| **Both positive and negative** | **Not both in binding policy** — taxonomy includes informational purpose; **binding policy is boundary-only** until a future positive code is explicitly approved (Q4) |

---

## 3. Explicitly inside the domain

| Item | Detail |
|------|--------|
| **Organizational duty (boundary)** | Permission-domain boundary for line heads — baseline must not grant HR processing, executive decision, HR oversight, or sysadmin authority by title inference |
| **Typical holders** | Heads of clinical, laboratory, and other line departments (permission-boundary purposes only) |
| **§7 line-head contours** | Twelve rows citing §5.4 — e.g. `(1, 42, 74)` … `(1, 55, 65)` — `HR_ENROLLMENT_MANAGER` **rejected** |
| **Principle P9** | Line department heads are not HR processing; §5.4 is informational permission domain boundary only |
| **§3 visibility boundary** | HR informational visibility (line staff process outcomes) → ACCESS-001 §5.4; management visibility → ACCESS-002 |
| **Registry R7** | Negative boundary is a first-class registry entry |
| **Runtime (transitional)** | ADR-042 Phase E1 visibility — runtime mechanism only; management visibility policy owner is ACCESS-002 |

---

## 4. Explicitly outside the domain

| Item | Owner / domain |
|------|----------------|
| HR document preparation and enrollment execution | PD-5.2 — **must not grant** via PD-5.4 baseline |
| Executive approval (hire, transfer, dismiss, acting) | PD-5.1 — **must not grant** |
| HR oversight visibility for control/compliance | PD-5.3 — **must not grant** |
| System administration / break-glass | Explicit sysadmin policy (P4) — **must not grant** |
| `HR_ENROLLMENT_MANAGER` on line-head contours | **Rejected** in §7 — P9 |
| Management responsibilities (personnel, tasks, execution, results) | ACCESS-002 |
| Management visibility over personnel / subtree | ACCESS-002 §3.1, §3.7 exclusively |
| Line-management authority or hierarchy | ACCESS-002 — PD-5.4 does **not** assign |
| §7 row disposition change | WP-B5, WP-B7 |
| Enforcement cutover | ADR-051 §10 Phase 3+ |

---

## 5. Architectural references (Accepted — fixed)

Architecture Freeze. Review Board **does not redesign** these positions.

| ADR / doc | Fixed position relevant to PD-5.4 |
|-----------|-----------------------------------|
| **ARCH-001** | Permissions follow Employment → Cabinet; not User-centric |
| **ADR-050** | Permission Template inside Position Cabinet 1:1 |
| **ADR-051** | Resolver expansion and union; legacy authoritative until cutover |
| **ADR-053** | Transitional binding; grant-copy forbidden; unmapped Cabinet allowed (P10 / I7) |
| **ADR-042 Phase E1** | Visibility assignments — runtime mechanism only; not organizational policy owner for management visibility |
| **ACCESS-001 P1, P9, P11, P12** | Cabinet-assigned; line heads ≠ HR processing; no engineering inference; orthogonal to ACCESS-002 |

**Architectural consistency:** No architectural contradiction identified.

---

## 6. Relationship analysis

### 6.1 ACCESS-001

| Dimension | Relationship |
|-----------|--------------|
| **Authority** | §5.4 normative; brief derived |
| **P9** | Line heads must not receive `HR_ENROLLMENT_MANAGER` as Cabinet baseline |
| **§3 visibility table** | HR informational visibility → §5.4; management visibility → ACCESS-002 |
| **§7** | Twelve line-head rows `rejected` — cite §5.4 domain boundary |
| **§5.5** | Domain ratification ≠ contour insert; line-head rows remain `rejected`, not `approved` |

### 6.2 ACCESS-002

| Dimension | PD-5.4 | ACCESS-002 |
|-----------|--------|------------|
| **Policy object** | Informational permission-domain boundary (what not to bind) | Management responsibilities |
| **Line head `(42, 74)` example** | §5.4 boundary — reject `HR_ENROLLMENT_MANAGER` | Personnel + tasks + execution + results over unit subtree (§7 example) |
| **Visibility type** | HR informational visibility (staff process outcomes) — boundary only | Management visibility from personnel responsibility (§3.1) |
| **Independence** | Ratifying PD-5.4 does not ratify ACCESS-002 responsibilities | P12 |

**Ambiguity:** None identified. PD-5.4 governs **permission baseline must not grant**; ACCESS-002 governs **management remit** — complementary orthogonal layers per WP-B1 package §3 PD-5.4 review sheet.

### 6.3 ADR-050 / ADR-051 / ADR-053

Factual: line-head contours have no approved `access_roles` baseline in Reviewed policy; NULL / unmapped Template is permitted during shadow phase (P10, ADR-053 I7). Rejection of `HR_ENROLLMENT_MANAGER` is policy stance — OPS-030 must not insert contour rules for `rejected` rows. ADR-042 E1 may provide runtime visibility mechanism; organizational owner for management visibility remains ACCESS-002.

### 6.4 Sibling domains

| Domain | Relationship |
|--------|--------------|
| **PD-5.1** | Executive vs line boundary — §5.4 line-only; Director / Acting Director are PD-5.1 typical holders, not PD-5.4 |
| **PD-5.2** | HR processing vs line boundary — P9; line heads **rejected** for `HR_ENROLLMENT_MANAGER` |
| **PD-5.3** | HR oversight vs line informational — §3 visibility table assigns distinct owners; different typical holders |
| **PD-5.4** | *(this domain)* |

---

## 7. Contour analysis

Contours with direct or explicit relevance in ACCESS-001 §7. **Matrix not modified.**

### Contour group 1 — Line-head association (rejected baseline)

| Field | Value |
|-------|-------|
| **Contours** | `(1, 42, 74)`, `(1, 43, 75)`, `(1, 44, 64)`, `(1, 45, 71)`, `(1, 46, 72)`, `(1, 47, 68)`, `(1, 48, 73)`, `(1, 49, 69)`, `(1, 50, 66)`, `(1, 53, 70)`, `(1, 54, 67)`, `(1, 55, 65)` |
| **Positions** | Заведующие clinical / laboratory / line departments |
| **Organizational rationale** | Line dept head — §5.4 domain boundary only; not HR processing |
| **Association** | PD-5.4 informational boundary |
| **Policy status** | `rejected` for `HR_ENROLLMENT_MANAGER`; `proposed_access_role_code` = `—` |

### Contour group 2 — Exclusion (HR processing)

| Field | Value |
|-------|-------|
| **Contours** | Same twelve line-head contours |
| **Association** | Excluded from PD-5.2 — P9; must not receive `HR_ENROLLMENT_MANAGER` by title |
| **Policy status** | `rejected` |

### Contour group 3 — Exclusion (HR oversight)

| Field | Value |
|-------|-------|
| **Contours** | Same twelve line-head contours |
| **Association** | Excluded from PD-5.3 — different typical holders; HR oversight vs line informational per §3 |
| **Policy status** | `rejected` for HR processing codes |

### Contour group 4 — Exclusion (executive / sysadmin)

| Field | Value |
|-------|-------|
| **Contours** | Line heads — not Director `(1, 78, 62)` |
| **Association** | Excluded from PD-5.1 executive decision; no `SYSADMIN_CABINET` from line title (P4) |
| **Policy status** | N/A for line rows — executive row `rejected` for `SYSADMIN_CABINET` |

**Contours reviewed:** 4 groups — twelve line-head contours in groups 1–3; one exclusion class (group 4).

---

## 8. Review questions requiring governance confirmation

From WP-B1 package review sheet. **Not answered in this brief.**

| # | Question |
|---|----------|
| **Q1** | Does the organization accept **линейное информирование** as a **negative boundary domain** (what not to bind) rather than a positive `access_roles` assignment? |
| **Q2** | Is rejection of `HR_ENROLLMENT_MANAGER` for all twelve listed line-head contours consistent with this domain? |
| **Q3** | Is it clear that line-head **management visibility** remains exclusively under ACCESS-002, not PD-5.4? |
| **Q4** | Should any line-head contour receive a **positive** `access_roles` baseline under PD-5.4 in future policy — or does the organization confirm PD-5.4 remains boundary-only per Reviewed ACCESS-001? |

---

## 9. Architectural answers already fixed

| Question | Fixed answer |
|----------|--------------|
| Grant-copy / shadow inference binding? | **No** — ADR-053 §3.4, ACCESS-001 P2, P11 |
| Ratification changes enforcement? | **No** — ADR-053 AC2 |
| Ratification authorizes OPS-030? | **No** — line-head rows `rejected`; no approved baseline for PD-5.4 |
| Approved `access_roles` baseline for PD-5.4 in Reviewed policy? | **No** — negative boundary only |
| PD-5.4 ratifies ACCESS-002 responsibilities? | **No** — orthogonal layers (P12) |
| PD-5.4 grants HR execution, HR oversight, executive decision, or sysadmin? | **No** — §5.4, P9; exclusions in §4 |
| Line-head `rejected` status changes on taxonomy ratification? | **No** — §5.5; WP-B5 confirms boundary downstream |
| Architecture redesign required? | **No** |

---

## 10. Remaining governance questions

| # | Topic | Nature |
|---|-------|--------|
| **G1** | Negative boundary vs positive code model | Organizational — Q1 |
| **G2** | Twelve line-head `HR_ENROLLMENT_MANAGER` rejections | Organizational — Q2 |
| **G3** | PD-5.4 vs ACCESS-002 management visibility | Organizational — Q3 |
| **G4** | Future positive baseline under PD-5.4 | Organizational / process — Q4 |

**Unresolved architectural questions:** None.

---

## 11. Readiness for Board decision

Factual assessment only — **does not recommend** Ratified / Deferred / Policy Debt.

| Criterion | Assessment |
|-----------|------------|
| Domain definition complete per ACCESS-001 §5.4 | Yes |
| Boundaries consistent with sibling domains | Yes — WP-B1 package §4.1 |
| Architectural conflicts | None |
| Cross-domain dependencies satisfied for discussion | Yes — PD-5.1 recorded; PD-5.2 / PD-5.3 briefs available; cross-domain consistency review accepted in WP-B1 §4 |
| Materials sufficient for Board to render decision | Yes |

**Approval status:** **Not ratified** — briefing only. Board selects outcome in §14.

---

## 12. Risks

| ID | Risk | Mitigation (if applicable) |
|----|------|----------------------------|
| **R1** | PD-5.4 conflated with ACCESS-002 line-head management authority | §3 visibility table; Q3; §5.4 «does not assign management authority» |
| **R2** | Negative boundary misread as «no policy needed» | Registry R7; Q1 |
| **R3** | `HR_ENROLLMENT_MANAGER` inserted for line heads despite §7 rejections | P9; Q2; WP-B5 |
| **R4** | Ratification mistaken for positive code approval | §5.4 stance; Q4; WP-B8 |
| **R5** | Engineering grant-copy bind from shadow / ADR-042 E1 | ADR-053 §3.4; §7 notes |
| **R6** | ADR-042 E1 runtime visibility treated as PD-5.4 policy owner | §5.4 runtime note; ACCESS-002 owns management visibility |
| **R7** | Informational need in Meaning interpreted as mandatory positive baseline | Q1, Q4; boundary-only stance in Reviewed policy |

---

## 13. Possible policy debt items

Items **that may be recorded** if Board selects **Ratified with Policy Debt**. Empty if Board selects **Ratified** without debt or **Deferred**.

| Debt ID (proposed) | Condition (if Board chooses debt path) | Resolution WP |
|--------------------|----------------------------------------|-----------------|
| **DEBT-B1-006** | Future positive `access_roles` baseline for line-head informational access under PD-5.4 not resolved at ratification | WP-B8 |
| **DEBT-B1-007** | Formal WP-B5 line-head boundary confirmation deferred | WP-B5 |

**Note:** Twelve §7 `rejected` rows citing §5.4 are **already recorded** in Reviewed ACCESS-001 — not automatically debt on taxonomy ratification.

---

## 14. Decision options (Review Board)

Board selects **one** option per domain. Brief does not presuppose outcome.

| Option | Meaning |
|--------|---------|
| **Ratified** | PD-5.4 taxonomy accepted as organizational vocabulary for subsequent WPs |
| **Ratified with Policy Debt** | Taxonomy accepted; named item(s) in §13 recorded with owner and resolution WP |
| **Deferred** | Taxonomy not accepted; further policy work required before re-session |

**Session must not:** modify ACCESS-001 §7 rows; insert contour rules; open OPS-030; change runtime enforcement.

---

## 15. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.2 | §7 inventory aligned to twelve rows citing §5.4 (registry / WP-B5 traceability) |
