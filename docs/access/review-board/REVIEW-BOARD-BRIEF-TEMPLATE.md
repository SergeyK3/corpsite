# Review Board Brief — Template

## Назначение

Нейтральный шаблон для сессий **WP-B1 — Permission Domain Taxonomy** (Tier G / G1).

Использование: скопировать в `PD-5.x-REVIEW-BOARD-BRIEF.md`, заполнить поля из [ACCESS-001](../ACCESS-001-organizational-permission-matrix.md) §5, [PERMISSION-DOMAIN-REGISTRY](../PERMISSION-DOMAIN-REGISTRY.md) и [WP-B1 package](../WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md) §3.

**Шаблон не фиксирует решение Review Board.** Бриф описывает политику и вопросы; исход выбирает Board: `Ratified` / `Ratified with Policy Debt` / `Deferred` / `Rejected`.

---

## Document metadata

| Field | Value |
|-------|-------|
| Session | WP-B1 Review Board Session _{N}_ |
| Date prepared | _{YYYY-MM-DD}_ |
| Domain ID | `PD-5._{x}_` |
| Domain name | _{name}_ |
| Work package | WP-B1 — Permission Domain Taxonomy |
| Tier / phase | G — Governance / G1 — Policy Ratification |
| Status | **Briefing only** — no ratification recorded |
| Prior sessions | _{list completed domain decisions or «none»}_ |
| Sources | ACCESS-001 §5._{x}_; relevant principles; PERMISSION-DOMAIN-REGISTRY; WP-B1 package review sheet |
| Runtime effect | **None** |

---

## 1. Domain definition

| Field | Content |
|-------|---------|
| **Domain ID** | `PD-5._{x}_` |
| **Name** | _{from ACCESS-001 §5.x}_ |
| **Purpose** | _{organizational purpose — derived from ACCESS-001}_ |
| **Organizational meaning** | _{from ACCESS-001 §5.x «Meaning»}_ |
| **ACCESS-001 source** | §5._{x}_; principles _{list}_ |
| **Registry entry** | PERMISSION-DOMAIN-REGISTRY §3 — current status _{from registry}_ |

---

## 2. Scope

_{One paragraph: what organizational question this domain answers.}_

**In scope for this session:**

- Ratification of **domain taxonomy** (organizational vocabulary).
- Acceptance of boundaries vs sibling domains and ACCESS-002.
- _{Domain-specific in-scope items — e.g. candidate code acknowledgment, negative boundary model — without assuming approval}_

**Out of scope for this session:**

- ACCESS-001 §7 row disposition — WP-B4, WP-B7.
- OPS-030 / Phase 2.6b execution — Tier B; ACCESS-001 **Approved** + AC3.
- Sibling domains not yet reviewed — remain pending until their sessions.
- Management responsibilities — ACCESS-002 Track A.
- Transitional code definition where deferred — WP-B3 / WP-B4 / WP-B8 as applicable.

---

## 3. Explicitly inside the domain

| Item | Detail |
|------|--------|
| _{row}_ | _{from ACCESS-001 §5.x}_ |

---

## 4. Explicitly outside the domain

| Item | Owner / domain |
|------|----------------|
| _{row}_ | _{sibling domain, ACCESS-002, or downstream WP}_ |

---

## 5. Architectural references (Accepted — fixed)

Architecture Freeze. Review Board **does not redesign** these positions.

| ADR / doc | Fixed position relevant to this domain |
|-----------|----------------------------------------|
| **ARCH-001** | Permissions follow Employment → Cabinet; not User-centric |
| **ADR-050** | Permission Template inside Position Cabinet 1:1 |
| **ADR-051** | Resolver expansion and union; legacy authoritative until cutover |
| **ADR-053** | Transitional `access_role_id` binding; Phase 2.6 scope; grant-copy forbidden |
| **ACCESS-001 P1, P11** | Cabinet-assigned permission; no engineering inference |

**Architectural consistency:** _{«No architectural contradiction identified» OR describe contradiction if discovered}_

---

## 6. Relationship analysis

### 6.1 ACCESS-001

_{Authority, principles, §7 contours, §5.5 mapping rule}_

### 6.2 ACCESS-002

| Dimension | This domain | ACCESS-002 |
|-----------|-------------|------------|
| _{row}_ | _{value}_ | _{value}_ |

**Ambiguity:** _{«None identified» OR list}_

### 6.3 ADR-050 / ADR-051 / ADR-053

_{Domain-specific use of Accepted contracts — factual only}_

### 6.4 Sibling domains

| Domain | Relationship |
|--------|--------------|
| **PD-5.1** | _{factual}_ |
| **PD-5.2** | _{factual}_ |
| **PD-5.3** | _{factual}_ |
| **PD-5.4** | _{factual}_ |

---

## 7. Contour analysis

Contours with direct or explicit relevance in ACCESS-001 §7. **Matrix not modified.**

### Contour _{n}_ — _{association | exclusion | note}_

| Field | Value |
|-------|-------|
| **Contour** | `(_{scope_id}_, _{org_unit_id}_, _{position_id}_)` |
| **Position** | _{name}_ |
| **Organizational rationale** | _{from matrix}_ |
| **Association** | _{belongs | excluded | pending — per ACCESS-001}_ |
| **Policy status** | _{approved | pending | rejected}_ |

_{Repeat per contour group. State total count.}_

---

## 8. Review questions requiring governance confirmation

From WP-B1 package review sheet. **Not answered in this brief.**

| # | Question |
|---|----------|
| **Q1** | _{question}_ |
| **Qn** | _{question}_ |

---

## 9. Architectural answers already fixed

| Question | Fixed answer |
|----------|--------------|
| May binding derive from user grants / shadow? | **No** — ADR-053 §3.4, ACCESS-001 P2, P11 |
| Does domain ratification change enforcement? | **No** — ADR-053 AC2 |
| Does domain ratification authorize OPS-030? | **No** — ACCESS-001 **Approved**, §7 row `approved`, AC3 |
| Does this domain ratify ACCESS-002 responsibilities? | **No** — orthogonal layers |
| Architecture redesign required? | _{No — unless contradiction found}_ |

_{Add domain-specific fixed answers only where ACCESS-001 / Accepted ADRs already decide.}_

---

## 10. Remaining governance questions

| # | Topic | Nature |
|---|-------|--------|
| **G1** | _{topic}_ | _{organizational | process}_ |

**Unresolved architectural questions:** _{none | list}_

---

## 11. Readiness for Board decision

Factual assessment only — **does not recommend** Ratified / Deferred / Policy Debt.

| Criterion | Assessment |
|-----------|------------|
| Domain definition complete per ACCESS-001 §5._{x}_ | _{Yes | No | Partial — explain}_ |
| Boundaries consistent with sibling domains | _{Yes | No | Partial}_ |
| Architectural conflicts | _{None | list}_ |
| Cross-domain dependencies satisfied for discussion | _{e.g. prior sessions completed}_ |
| Materials sufficient for Board to render decision | _{Yes | No}_ |

**Approval status:** **Not ratified** — briefing only.

---

## 12. Risks

| ID | Risk | Mitigation (if applicable) |
|----|------|----------------------------|
| **R1** | _{risk}_ | _{mitigation}_ |

---

## 13. Possible policy debt items

Items **that may be recorded** if Board selects **Ratified with Policy Debt**. Empty if Board selects **Ratified** without debt or **Deferred**.

| Debt ID (proposed) | Condition (if Board chooses debt path) | Resolution WP |
|--------------------|----------------------------------------|-----------------|
| _{DEBT-B1-00x}_ | _{condition}_ | _{WP}_ |

**Note:** Contour `pending` after taxonomy ratification may be **normal** per §5.5 — record as debt only if Board explicitly defers a named item.

---

## 14. Decision options (Review Board)

Board selects **one** option per domain. Brief does not presuppose outcome.

| Option | Meaning |
|--------|---------|
| **Ratified** | Domain taxonomy accepted as organizational vocabulary for subsequent WPs |
| **Ratified with Policy Debt** | Taxonomy accepted; named item deferred with owner and resolution WP |
| **Deferred** | Taxonomy not accepted; further policy work required before re-session |
| **Rejected** | Domain not accepted; requires ACCESS-001 revision cycle (out of WP-B1 scope) |

**Session must not:** modify ACCESS-001 §7 rows; insert contour rules; open OPS-030; change runtime enforcement.

---

## 15. Document history

| Date | Version | Change |
|------|---------|--------|
| _{date}_ | 0.1 | Initial brief from template |
