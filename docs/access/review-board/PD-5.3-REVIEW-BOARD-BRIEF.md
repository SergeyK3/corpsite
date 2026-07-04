# Review Board Brief — WP-B1 Session 3

## PD-5.3 — Кадровый контроль / наблюдение

> Template: [REVIEW-BOARD-BRIEF-TEMPLATE.md](./REVIEW-BOARD-BRIEF-TEMPLATE.md)

## Document metadata

| Field | Value |
|-------|-------|
| Session | WP-B1 Review Board Session 3 |
| Date prepared | 2026-07-04 |
| Domain ID | `PD-5.3` |
| Domain name | Кадровый контроль / наблюдение |
| Work package | WP-B1 — Permission Domain Taxonomy |
| Tier / phase | G — Governance / G1 — Policy Ratification |
| Status | **Briefing only** — no ratification recorded |
| Prior sessions | PD-5.1 — Ratified with Policy Debt (2026-07-04); PD-5.2 — Session 2 brief prepared, not ratified; [WP-B1 package §6](../WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md#6-ratification-outcome) |
| Sources | [ACCESS-001](../ACCESS-001-organizational-permission-matrix.md) §5.3, P8, §3 visibility boundary; [PERMISSION-DOMAIN-REGISTRY](../PERMISSION-DOMAIN-REGISTRY.md); [WP-B1 package](../WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md) |
| Runtime effect | **None** |

---

## 1. Domain definition

| Field | Content |
|-------|---------|
| **Domain ID** | `PD-5.3` |
| **Name** | Кадровый контроль / наблюдение (HR oversight visibility) |
| **Purpose** | HR oversight visibility permission domain — see кадровые процессы for control/compliance within approved HR operational scope without executing HR processing |
| **Organizational meaning** | May **see** кадровые процессы for HR control/compliance within approved HR operational scope; **does not execute** HR processing |
| **ACCESS-001 source** | [§5.3](../ACCESS-001-organizational-permission-matrix.md#53-кадровый-контроль--наблюдение-hr-oversight-visibility); principle P8; [§3 visibility boundary](../ACCESS-001-organizational-permission-matrix.md#3-relationship-to-access-002) |
| **Registry entry** | [PERMISSION-DOMAIN-REGISTRY §3 — PD-5.3](../PERMISSION-DOMAIN-REGISTRY.md#pd-53--кадровый-контроль--наблюдение) — **Defined (Reviewed)** — pending ratification |

---

## 2. Scope

PD-5.3 governs organizational permission policy for **HR oversight visibility** — the ability to observe кадровые процессы for control and compliance on Cabinet Permission Template baseline, distinct from HR execution, executive decision, line informational boundaries, and management visibility.

**In scope for Session 3:**

- Ratification of domain taxonomy.
- Boundary review vs PD-5.1, PD-5.2, PD-5.4, and ACCESS-002.
- Review of deputy admin contour `(1, 78, 77)` as the **likely** PD-5.3 association (acknowledgment only — not contour assignment).
- Review of absence of a dedicated transitional `access_roles.code` in Reviewed ACCESS-001 (acknowledgment only — not code definition).
- Delegation exception rule: `HR_ENROLLMENT_MANAGER` on a PD-5.3 holder only via explicit organizational delegation per §5.3.

**Out of scope for Session 3:**

- ACCESS-001 §7 row approval for `(1, 78, 77)` — WP-B4, WP-B7.
- OPS-030 / Phase 2.6b — Tier B.
- Dedicated transitional `access_roles.code` definition — WP-B4, WP-B8.
- PD-5.1 transitional code — WP-B3 (DEBT-B1-001).
- PD-5.2, PD-5.4 ratification — separate sessions (PD-5.2 Session 2 outcome independent of this session).
- ACCESS-002 management responsibilities — Track A.
- Deputy admin **management remit** (personnel oversight, organizational information) — ACCESS-002 §3.7.

---

## 3. Explicitly inside the domain

| Item | Detail |
|------|--------|
| **Organizational duty** | HR oversight visibility — see кадровые процессы for HR control/compliance within approved HR operational scope; does not execute HR processing |
| **Typical holders** | Deputy for administrative affairs (`Зам по адм вопросам`); legal service; other authorized oversight roles per organizational policy |
| **Primary contour (ACCESS-001 stance)** | `(1, 78, 77)` — Зам по адм вопросам — pending; likely this domain |
| **Principle P8** | Deputy administrative / legal oversight is not HR processing; may belong to кадровый контроль / наблюдение |
| **§3 visibility boundary** | HR oversight visibility is ACCESS-001 §5.3; management visibility is ACCESS-002 |
| **Delegation exception** | `HR_ENROLLMENT_MANAGER` may apply to a PD-5.3 holder **only** if explicit organizational delegation is approved (§5.3) |
| **Runtime (transitional)** | ADR-045 / access baseline when approved — runtime mechanism only; not policy owner |

---

## 4. Explicitly outside the domain

| Item | Owner / domain |
|------|----------------|
| HR document preparation and enrollment execution | PD-5.2 |
| Executive approval (hire, transfer, dismiss, acting) | PD-5.1 |
| Line-head informational boundary | PD-5.4 |
| Management visibility over personnel / subtree | ACCESS-002 §3.1 |
| Deputy admin management responsibilities (personnel oversight, organizational information) | ACCESS-002 §3.7 |
| Default `HR_ENROLLMENT_MANAGER` on deputy admin contour | Excluded by default — §5.3; PD-5.2 unless delegation |
| Director / Acting Director as HR oversight holder by title alone | Not defined in Reviewed ACCESS-001 for this domain |
| Line department heads as HR oversight processors | Excluded; different typical holders vs PD-5.4 |
| Sysadmin / break-glass | Explicit sysadmin policy (P4, P5) |
| §7 row `approved` | WP-B7 |
| Enforcement cutover | ADR-051 §10 Phase 3+ |

---

## 5. Architectural references (Accepted — fixed)

Architecture Freeze. Review Board **does not redesign** these positions.

| ADR / doc | Fixed position relevant to PD-5.3 |
|-----------|-----------------------------------|
| **ARCH-001** | Permissions follow Employment → Cabinet; not User-centric |
| **ADR-050** | Permission Template inside Position Cabinet 1:1 |
| **ADR-051** | Resolver expansion and union; legacy authoritative until cutover |
| **ADR-053** | Transitional `access_role_id` binding; Phase 2.6 scope; grant-copy forbidden |
| **ADR-045** | «Кадровые процессы» contour — runtime baseline when approved; not policy owner for PD-5.3 |
| **ACCESS-001 P1, P8, P11, P12** | Cabinet-assigned permission; deputy oversight ≠ HR processing; no engineering inference; orthogonal to ACCESS-002 |

**Architectural consistency:** No architectural contradiction identified.

---

## 6. Relationship analysis

### 6.1 ACCESS-001

| Dimension | Relationship |
|-----------|--------------|
| **Authority** | §5.3 normative; brief derived |
| **P8** | Deputy admin / legal oversight → likely §5.3, not `HR_ENROLLMENT_MANAGER` by default |
| **§3 visibility table** | HR oversight visibility → ACCESS-001 §5.3; management visibility → ACCESS-002 |
| **§7** | `(78, 77)` pending — likely §5.3 |
| **§5.5** | Domain ratification ≠ contour insert |

### 6.2 ACCESS-002

| Dimension | PD-5.3 | ACCESS-002 |
|-----------|--------|------------|
| **Policy object** | HR-process visibility for control/compliance on baseline | Management responsibilities |
| **Deputy admin `(78, 77)`** | Pending PD-5.3 candidate (permission domain) | Personnel oversight + organizational information (§3.7 draft proposal) |
| **Visibility type** | HR oversight visibility (see кадровые процессы for control) | Management visibility from personnel responsibility (§3.1) |
| **Independence** | Ratifying PD-5.3 does not ratify ACCESS-002 responsibilities | M2 / P12 |

**Ambiguity:** None identified. Shared contour `(78, 77)` carries **orthogonal** policy layers per ACCESS-001 §3 and WP-B1 package §4.3.

### 6.3 ADR-050 / ADR-051 / ADR-053

Factual: when a dedicated `access_roles.code` is approved for this domain and contour row reaches `approved`, binding attaches to Cabinet Template via contour rule; resolver emits code on shadow path when bound; OPS-030 gated on ACCESS-001 **Approved** + §7 + AC3. Reviewed ACCESS-001 defines **no** dedicated transitional code for PD-5.3 — binding path is downstream (WP-B4/B8).

### 6.4 Sibling domains

| Domain | Relationship |
|--------|--------------|
| **PD-5.1** | Decision vs oversight — §5.3 does not execute; does not approve кадровые решения |
| **PD-5.2** | Processing vs oversight — P8; §5.3 may see but not execute; deputy admin excluded from PD-5.2 by default |
| **PD-5.3** | *(this domain)* |
| **PD-5.4** | HR oversight vs line informational — §3 visibility table assigns distinct owners; different typical holders |

---

## 7. Contour analysis

Contours with direct or explicit relevance in ACCESS-001 §7. **Matrix not modified.**

### Contour 1 — Primary association (pending)

| Field | Value |
|-------|-------|
| **Contour** | `(1, 78, 77)` |
| **Position** | Зам по адм вопросам |
| **Organizational rationale** | Deputy for administrative affairs — typical PD-5.3 holder per §5.3 and P8 |
| **Association** | Likely PD-5.3 per ACCESS-001 §7 |
| **Policy status** | `pending` |

### Contour 2 — Exclusion (HR processing by default)

| Field | Value |
|-------|-------|
| **Contour** | `(1, 78, 77)` — same contour |
| **Association** | Excluded from PD-5.2 / `HR_ENROLLMENT_MANAGER` by default — P8, §5.3 |
| **Policy status** | `pending` (class TBD; not HR processing by default) |

### Contour 3 — Exclusion (executive)

| Field | Value |
|-------|-------|
| **Contour** | `(1, 78, 62)` — Директор |
| **Association** | Excluded — PD-5.1 domain; not PD-5.3 typical holder |
| **Policy status** | `rejected` (`SYSADMIN_CABINET`) |

### Contour 4 — Exclusion (line heads)

| Field | Value |
|-------|-------|
| **Contours** | Twelve §7 rows citing §5.4 — e.g. `(1, 42, 74)` … `(1, 55, 65)` |
| **Association** | Excluded — PD-5.4 informational boundary; not HR oversight domain |
| **Policy status** | `rejected` for `HR_ENROLLMENT_MANAGER` |

**Contours reviewed:** 4 groups (1 association, 3 exclusion groups).

**Note:** Legal service and other oversight roles listed as typical holders in §5.3 have **no** explicit §7 row in Reviewed ACCESS-001 — outside contour inventory for this session.

---

## 8. Review questions requiring governance confirmation

From WP-B1 package review sheet. **Not answered in this brief.**

| # | Question |
|---|----------|
| **Q1** | Is **HR oversight visibility** correctly distinguished from **management visibility** over personnel/subtree (ACCESS-002)? |
| **Q2** | Is assignment of deputy admin contour `(1, 78, 77)` to PD-5.3 (rather than PD-5.2) acceptable as the default organizational stance? |
| **Q3** | Under what conditions, if any, may `HR_ENROLLMENT_MANAGER` apply to a PD-5.3 holder — only via **explicit organizational delegation** per ACCESS-001 §5.3? |
| **Q4** | Is it acceptable to ratify PD-5.3 without a dedicated transitional `access_roles.code` (deferred to WP-B4/B8 policy debt register)? |

---

## 9. Architectural answers already fixed

| Question | Fixed answer |
|----------|--------------|
| Grant-copy / shadow inference binding? | **No** — ADR-053 §3.4, ACCESS-001 P2, P11 |
| Ratification changes enforcement? | **No** — ADR-053 AC2 |
| Ratification authorizes OPS-030? | **No** — ACCESS-001 **Reviewed**, §7 row `pending`, AC3 |
| Dedicated `access_roles.code` defined for PD-5.3 in Reviewed policy? | **No** — documented gap; not engineering assignment |
| PD-5.3 ratifies ACCESS-002 responsibilities? | **No** — orthogonal layers (P12) |
| PD-5.3 subsumes PD-5.2 execution? | **No** — P8; §5.3 does not execute |
| Deputy admin gets `HR_ENROLLMENT_MANAGER` by default? | **No** — P8; delegation exception only |
| Architecture redesign required? | **No** |

---

## 10. Remaining governance questions

| # | Topic | Nature |
|---|-------|--------|
| **G1** | HR oversight vs management visibility separation | Organizational — Q1 |
| **G2** | Deputy admin default domain assignment | Organizational — Q2 |
| **G3** | Delegation conditions for `HR_ENROLLMENT_MANAGER` on PD-5.3 holder | Organizational — Q3 |
| **G4** | Ratification without dedicated transitional code | Process — Q4 |
| **G5** | Scope of «other authorized oversight roles» beyond deputy admin | Organizational |

**Unresolved architectural questions:** None.

---

## 11. Readiness for Board decision

Factual assessment only — **does not recommend** Ratified / Deferred / Policy Debt.

| Criterion | Assessment |
|-----------|------------|
| Domain definition complete per ACCESS-001 §5.3 | Yes |
| Boundaries consistent with sibling domains | Yes — WP-B1 package §4.1 |
| Architectural conflicts | None |
| Cross-domain dependencies satisfied for discussion | Yes — PD-5.1 recorded; PD-5.2 brief available; cross-domain consistency review accepted in WP-B1 §4 |
| Materials sufficient for Board to render decision | Yes |

**Approval status:** **Not ratified** — briefing only. Board selects outcome in §14.

---

## 12. Risks

| ID | Risk | Mitigation (if applicable) |
|----|------|----------------------------|
| **R1** | Conflation of PD-5.3 HR oversight visibility with ACCESS-002 management visibility on deputy admin | §3 visibility table; Q1; ACCESS-002 §3.7 |
| **R2** | Conflation with PD-5.2 HR processing | P8; Q2; §5.3 «does not execute» |
| **R3** | `HR_ENROLLMENT_MANAGER` assigned to deputy admin without delegation | P8; Q3; §5.3 delegation rule |
| **R4** | Ratification mistaken for contour `(78, 77)` approval | §5.5; WP-B7 |
| **R5** | Engineering grant-copy bind from ADR-042 ROLE grant | ADR-053 §3.4; ACCESS-001 §7 notes |
| **R6** | Absence of dedicated code misread as «no domain needed» | Q4; WP-B4/B8; PERMISSION-DOMAIN-REGISTRY §3 |
| **R7** | Terminology overlap: ACCESS-002 §3.7 «кадровый контроль» vs PD-5.3 domain name | Orthogonal layers; distinct policy objects |

---

## 13. Possible policy debt items

Items **that may be recorded** if Board selects **Ratified with Policy Debt**. Empty if Board selects **Ratified** without debt or **Deferred**.

| Debt ID (proposed) | Condition (if Board chooses debt path) | Resolution WP |
|--------------------|----------------------------------------|-----------------|
| **DEBT-B1-004** | No dedicated transitional `access_roles.code` for PD-5.3 in Reviewed ACCESS-001 | WP-B4 / WP-B8 |
| **DEBT-B1-005** | Class assignment on `(1, 78, 77)` deferred | WP-B4 |

**Note:** Contour `pending` after taxonomy ratification may be **normal** per §5.5 — record as debt only if Board explicitly defers a named item.

---

## 14. Decision options (Review Board)

Board selects **one** option per domain. Brief does not presuppose outcome.

| Option | Meaning |
|--------|---------|
| **Ratified** | PD-5.3 taxonomy accepted as organizational vocabulary for subsequent WPs |
| **Ratified with Policy Debt** | Taxonomy accepted; named item(s) in §13 recorded with owner and resolution WP |
| **Deferred** | Taxonomy not accepted; further policy work required before re-session |

**Session must not:** modify ACCESS-001 §7 rows; insert contour rules; open OPS-030; change runtime enforcement.

---

## 15. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial Session 3 brief from template |
