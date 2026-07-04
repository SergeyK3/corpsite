# WP-B1 — Permission Domain Ratification Package

## Status

**In progress (governance)** — 2026-07-04

Package for **WP-B1 — Permission Domain Taxonomy** under [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) (Tier G, Phase G1). **PD-5.1 recorded** — Ratified with Policy Debt (2026-07-04). PD-5.2–PD-5.4 pending. **WP-B1 not closed.** **No runtime effect.**

| Field | Value |
|-------|-------|
| Work package | WP-B1 |
| Tier / phase | G — Policy Ratification / G1 |
| Source policy | [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md) §5 (**Reviewed**) |
| Domain catalog | [PERMISSION-DOMAIN-REGISTRY](./PERMISSION-DOMAIN-REGISTRY.md) |
| Approval authority | HR policy owner + ops lead + architecture lead |
| Does not approve | Implementation, OPS-030, contour rows, `access_roles` bindings |

---

## 1. Purpose

This package assembles all information required for a **formal governance review** of the four Organizational Permission Domains already defined in ACCESS-001 and consolidated in PERMISSION-DOMAIN-REGISTRY.

| Statement | Detail |
|-----------|--------|
| **No new policy** | Content is extracted from Reviewed ACCESS-001 §5 and §3 visibility boundaries. No domains, codes, or bindings are added. |
| **No implementation approved** | Ratifying WP-B1 does not authorize OPS-030, Phase 2.6b, schema changes, or enforcement cutover. |
| **Organizational decisions only** | Reviewers decide whether to accept each domain as the official taxonomy for subsequent work packages (WP-B2, WP-B4, WP-B7, WP-X1). |
| **ACCESS-001 remains normative** | This package supports ratification; ACCESS-001 §5 prevails if any wording diverges. |

**WP-B1 output (when complete):** signed attestation that the four-domain taxonomy is accepted as organizational vocabulary — recorded in §6 and reflected in PERMISSION-DOMAIN-REGISTRY §5 (by governance session, not by this preparatory document).

---

## 2. Ratification scope

Exactly **four** Permission Domains — no additional domains.

| Domain ID | Name | ACCESS-001 source |
|-----------|------|-------------------|
| **PD-5.1** | Кадровое решение | §5.1 |
| **PD-5.2** | Кадровое оформление | §5.2 |
| **PD-5.3** | Кадровый контроль / наблюдение | §5.3 |
| **PD-5.4** | Линейное информирование | §5.4 |

**Out of scope for WP-B1:**

- ACCESS-001 §7 contour row disposition (WP-B7)
- `access_roles.code` approval per contour (WP-B4, WP-B7)
- Кадровое решение transitional code definition (WP-B3 — follows WP-B1)
- Management responsibilities (ACCESS-002 Track A / WP-A1)
- ADR-053 AC3 sign-off (WP-X3)

---

## 3. Domain review sheets

---

### Review sheet — PD-5.1

| Field | Content |
|-------|---------|
| **Domain ID** | `PD-5.1` |
| **Name** | Кадровое решение |
| **Organizational purpose** | Model executive **approval** authority for кадровые решения on Position Cabinet baseline — separate from HR execution, sysadmin, and management oversight |
| **Organizational meaning** | Right and duty to **approve** кадровые решения: hire, transfer, dismiss, appoint acting duties |
| **Why this domain exists** | ACCESS-001 §5 separates кадровое **решение** from кадровое **оформление** (P6, P7). Director title does not imply `HR_ENROLLMENT_MANAGER` or `SYSADMIN_CABINET`. Executive approval requires its own permission class if modeled on Template baseline |
| **What it explicitly does NOT include** | HR document preparation; enrollment execution; `HR_ENROLLMENT_MANAGER`; `SYSADMIN_CABINET`; management visibility (ACCESS-002); line informational boundary (PD-5.4); ADR-045 executive read scope as substitute for this domain |
| **Source (ACCESS-001)** | §5.1; principles P5, P6, P7 |
| **Relationship with ACCESS-002** | Orthogonal. Executive **responsibility for results** and **organizational information** (ACCESS-002 §3.4, §3.5, §3.7 Director proposal) do **not** substitute for this permission domain. Ratifying PD-5.1 does not ratify any ACCESS-002 responsibility on Director contour |
| **Related contours** | `(client_scope_id=1, org_unit_id=78, catalog_position_id=62)` — Директор — `policy_status=rejected` for `SYSADMIN_CABINET`; requires PD-5.1 if executive baseline is ever approved |
| **Related access_roles** | **None defined** in Reviewed ACCESS-001. Separate decision/approval class **not modeled**. `HR_ENROLLMENT_MANAGER` **must not** represent this class |
| **Runtime impact** | **None** upon WP-B1 ratification. No contour insert; legacy enforcement unchanged |

**Questions for ratification**

1. Is the organizational purpose of **executive approval** (hire / transfer / dismiss / acting appointment) correctly separated from HR **оформление** (PD-5.2)?
2. Is it acceptable to ratify PD-5.1 as a **defined domain** while no transitional `access_roles.code` exists (policy debt deferred to WP-B3)?
3. Is rejection of `SYSADMIN_CABINET` and `HR_ENROLLMENT_MANAGER` for Director contour `(78, 62)` consistent with this domain definition?
4. Does the organization accept that ratifying this domain **does not** approve any ACCESS-002 management responsibility for the Director Cabinet?

---

### Review sheet — PD-5.2

| Field | Content |
|-------|---------|
| **Domain ID** | `PD-5.2` |
| **Name** | Кадровое оформление |
| **Organizational purpose** | Model HR department **execution** of кадровые процессы on Cabinet baseline — document preparation and enrollment, not executive decision |
| **Organizational meaning** | Prepares documents, performs enrollment, executes кадровые процессы (ADR-045 «Кадровые процессы» contour) |
| **Why this domain exists** | ACCESS-001 §5 assigns HR-service operational processing to a distinct class. P6 states `HR_ENROLLMENT_MANAGER` means оформление, not решение. Line and executive roles must not absorb HR processing by title inference |
| **What it explicitly does NOT include** | Executive кадровое решение (PD-5.1); HR oversight visibility without execution (PD-5.3); line informational boundary (PD-5.4); management responsibilities or subtree command (ACCESS-002); automatic assignment to non-HR contours |
| **Source (ACCESS-001)** | §5.2; principle P6 |
| **Relationship with ACCESS-002** | Orthogonal. HR head contour has **no line management subtree** in ACCESS-002 §7 shared example — HR operational scope only. Ratifying PD-5.2 does not assign personnel/task/result responsibilities to HR head Cabinet |
| **Related contours** | `(1, 73, 86)` — Руководитель отдела кадров — `policy_status=pending`; likely PD-5.2; not approved until class + code ratified |
| **Related access_roles** | `HR_ENROLLMENT_MANAGER` — **transitional code (candidate only)**; **if and only if** approved for a specific HR-service Cabinet contour |
| **Runtime impact** | **None** upon WP-B1 ratification. `HR_ENROLLMENT_MANAGER` binding requires WP-B4 + WP-B7 + ACCESS-001 **Approved** |

**Questions for ratification**

1. Does the organization accept **кадровое оформление** as the correct class for the HR department / кадровая служба (`Отдел кадров`)?
2. Is `HR_ENROLLMENT_MANAGER` accepted as the **candidate** transitional code for this domain only — not for Director, deputy admin, or line heads?
3. Is the pending status of contour `(1, 73, 86)` acceptable pending WP-B4/B7 — i.e. domain ratification now, contour binding later?
4. Does the organization confirm that PD-5.2 does **not** grant executive decision authority (PD-5.1)?

---

### Review sheet — PD-5.3

| Field | Content |
|-------|---------|
| **Domain ID** | `PD-5.3` |
| **Name** | Кадровый контроль / наблюдение (HR oversight visibility) |
| **Organizational purpose** | Model **HR oversight visibility** — ability to see кадровые процессы for control/compliance within approved HR operational scope, without executing HR processing |
| **Organizational meaning** | May **see** кадровые процессы for HR control/compliance; **does not execute** HR processing |
| **Why this domain exists** | ACCESS-001 §5 and P8 separate deputy administrative / legal **oversight** from HR **processing**. §3 visibility boundary assigns HR oversight visibility to ACCESS-001, not ACCESS-002 management visibility |
| **What it explicitly does NOT include** | `HR_ENROLLMENT_MANAGER` unless explicit organizational delegation approved; management visibility / personnel subtree oversight (ACCESS-002 §3.1); кадровое решение (PD-5.1); кадровое оформление execution (PD-5.2); line informational boundary (PD-5.4) |
| **Source (ACCESS-001)** | §5.3; principle P8; §3 visibility boundary table |
| **Relationship with ACCESS-002** | Orthogonal. Deputy admin **personnel oversight** and **organizational information** (ACCESS-002 §3.7 deputy proposal) are management responsibilities — **not** this permission domain. PD-5.3 governs HR-process **visibility for control**; ACCESS-002 governs management remit and subtree |
| **Related contours** | `(1, 78, 77)` — Зам по адм вопросам — `policy_status=pending`; likely PD-5.3, not `HR_ENROLLMENT_MANAGER` by default |
| **Related access_roles** | **None defined** in Reviewed ACCESS-001. ADR-045 / access baseline when approved — runtime mechanism only; not policy owner for this domain |
| **Runtime impact** | **None** upon WP-B1 ratification. No dedicated `access_roles.code` in Reviewed policy |

**Questions for ratification**

1. Is **HR oversight visibility** correctly distinguished from **management visibility** over personnel/subtree (ACCESS-002)?
2. Is assignment of deputy admin contour `(1, 78, 77)` to PD-5.3 (rather than PD-5.2) acceptable as the default organizational stance?
3. Under what conditions, if any, may `HR_ENROLLMENT_MANAGER` apply to a PD-5.3 holder — only via **explicit organizational delegation** per ACCESS-001 §5.3?
4. Is it acceptable to ratify PD-5.3 without a dedicated transitional `access_roles.code` (deferred to WP-B4/B8 policy debt register)?

---

### Review sheet — PD-5.4

| Field | Content |
|-------|---------|
| **Domain ID** | `PD-5.4` |
| **Name** | Линейное информирование (informational permission domain) |
| **Organizational purpose** | Define **negative permission boundary** for line department heads — what baseline `access_roles` binding **must not** grant; does not assign line-management responsibility |
| **Organizational meaning** | Line heads may need **information** on results of relevant кадровые процессы for their own staff — expressed as a permission domain boundary, not as management remit or HR processing authority |
| **Why this domain exists** | ACCESS-001 P9 and §5.4 prevent line clinical/lab heads from receiving `HR_ENROLLMENT_MANAGER` by title. Separates HR informational permission boundary from ACCESS-002 line-head management responsibilities (personnel, tasks, execution, results) |
| **What it explicitly does NOT include** | HR processing (`HR_ENROLLMENT_MANAGER`); executive decision (PD-5.1); HR oversight for compliance (PD-5.3); assignment of management authority — management visibility scope is **ACCESS-002 exclusively** (§3.1, §3.7) |
| **Source (ACCESS-001)** | §5.4; principle P9; §3 visibility boundary table |
| **Relationship with ACCESS-002** | Complementary but **orthogonal layers**. Line heads hold personnel + tasks + execution + results responsibilities over unit subtree (ACCESS-002 §7 example `(42, 74)`). PD-5.4 governs only what **permission baseline must not grant** — not management remit. ADR-042 E1 visibility is runtime mechanism only; ACCESS-002 owns management visibility policy |
| **Related contours** | Twelve **rejected** line-head contours in ACCESS-001 §7 citing §5.4: `(1,42,74)`, `(1,43,75)`, `(1,44,64)`, `(1,45,71)`, `(1,46,72)`, `(1,47,68)`, `(1,48,73)`, `(1,49,69)`, `(1,50,66)`, `(1,53,70)`, `(1,54,67)`, `(1,55,65)` — all `HR_ENROLLMENT_MANAGER` **rejected** |
| **Related access_roles** | **None approved.** Negative boundary only — no approved `access_roles` baseline for PD-5.4 in Reviewed ACCESS-001 |
| **Runtime impact** | **None** upon WP-B1 ratification. Rejection of HR processing codes for line heads is policy stance only until ACCESS-001 **Approved** |

**Questions for ratification**

1. Does the organization accept **линейное информирование** as a **negative boundary domain** (what not to bind) rather than a positive `access_roles` assignment?
2. Is rejection of `HR_ENROLLMENT_MANAGER` for all twelve listed line-head contours consistent with this domain?
3. Is it clear that line-head **management visibility** remains exclusively under ACCESS-002, not PD-5.4?
4. Should any line-head contour receive a **positive** `access_roles` baseline under PD-5.4 in future policy — or does the organization confirm PD-5.4 remains boundary-only per Reviewed ACCESS-001?

---

## 4. Cross-domain consistency review

### 4.1. Overlap analysis

| Domain pair | Overlap risk | ACCESS-001 resolution |
|-------------|--------------|----------------------|
| PD-5.1 ↔ PD-5.2 | Decision vs execution | §5.1 / §5.2 explicitly separated; P6/P7 forbid `HR_ENROLLMENT_MANAGER` for решение |
| PD-5.1 ↔ PD-5.3 | Decision vs oversight | §5.3 does not execute; does not approve decisions |
| PD-5.1 ↔ PD-5.4 | Executive vs line boundary | §5.4 line-only; §5.1 Director/Acting Director |
| PD-5.2 ↔ PD-5.3 | Processing vs oversight | P8; §5.3 may see but not execute; delegation exception only |
| PD-5.2 ↔ PD-5.4 | HR processing vs line boundary | P9; line heads rejected for `HR_ENROLLMENT_MANAGER` |
| PD-5.3 ↔ PD-5.4 | HR oversight vs line informational | §3 visibility table assigns distinct owners; different typical holders |

**Finding:** No overlapping domain definitions. Each domain addresses a distinct organizational function per ACCESS-001 §5 intro (separated by function).

### 4.2. Contradiction analysis

| Check | Result |
|-------|--------|
| Domains contradict each other | **No** — mutual exclusions documented in each §5.x «Not the same as» |
| PD-5.1 requires code but forbids `HR_ENROLLMENT_MANAGER` | **Consistent** — intentional policy debt; separate class required (P7) |
| PD-5.4 is boundary-only while PD-5.2 requires positive code | **Consistent** — R7 in registry; §5.4 stance explicit |
| Director rejected for sysadmin and HR processing | **Consistent** — P4, P5, P7 |

### 4.3. Ownership preservation

| Owner | Preserved |
|-------|-----------|
| **ACCESS-001** | Permission domains, `access_roles` binding policy, §7 matrix — unchanged; this package cites only |
| **ACCESS-002** | Management responsibilities, hierarchy, subtree, derived capability groups — not defined or altered by WP-B1 |

### 4.4. Consistency conclusion

**No architectural inconsistencies identified.**

**Note for reviewers (not inconsistencies):** PD-5.1 and PD-5.3 lack transitional `access_roles.code` in Reviewed ACCESS-001. This is **documented policy debt** (WP-B3, WP-B8), not a conflict between domains. WP-B1 ratifies **taxonomy**; code mapping is downstream.

---

## 5. Ratification checklist

Complete one checklist per domain during governance session.

### PD-5.1 — Кадровое решение

**Recorded:** 2026-07-04 — **Ratified with Policy Debt** (see §6, §6.1).

| # | Item | Decision |
|---|------|----------|
| 1 | Organizational purpose accepted | ☑ |
| 2 | Boundary accepted (exclusions list) | ☑ |
| 3 | Relationship with ACCESS-002 accepted | ☑ |
| 4 | Related contours accepted `(1, 78, 62)` stance | ☑ |
| 5 | Related access_roles accepted (none defined; rejections affirmed) | ☑ |
| 6 | Ready for Approved | ☑ |

### PD-5.2 — Кадровое оформление

| # | Item | Decision |
|---|------|----------|
| 1 | Organizational purpose accepted | ☐ |
| 2 | Boundary accepted (exclusions list) | ☐ |
| 3 | Relationship with ACCESS-002 accepted | ☐ |
| 4 | Related contours accepted `(1, 73, 86)` likely assignment | ☐ |
| 5 | Related access_roles accepted (`HR_ENROLLMENT_MANAGER` as candidate only) | ☐ |
| 6 | Ready for Approved | ☐ |

### PD-5.3 — Кадровый контроль / наблюдение

| # | Item | Decision |
|---|------|----------|
| 1 | Organizational purpose accepted | ☐ |
| 2 | Boundary accepted (exclusions list) | ☐ |
| 3 | Relationship with ACCESS-002 accepted | ☐ |
| 4 | Related contours accepted `(1, 78, 77)` likely assignment | ☐ |
| 5 | Related access_roles accepted (none defined; delegation rule noted) | ☐ |
| 6 | Ready for Approved | ☐ |

### PD-5.4 — Линейное информирование

| # | Item | Decision |
|---|------|----------|
| 1 | Organizational purpose accepted | ☐ |
| 2 | Boundary accepted (negative boundary model) | ☐ |
| 3 | Relationship with ACCESS-002 accepted | ☐ |
| 4 | Related contours accepted (twelve line-head rejections) | ☐ |
| 5 | Related access_roles accepted (none; `HR_ENROLLMENT_MANAGER` rejected) | ☐ |
| 6 | Ready for Approved | ☐ |

### WP-B1 package completion

| # | Item | Decision |
|---|------|----------|
| 1 | All four domain checklists complete | ☐ (1/4 — PD-5.1 only) |
| 2 | Cross-domain consistency review accepted (§4) | ☑ |
| 3 | Ratification outcome recorded (§6) | ☐ (1/4 — PD-5.1 only) |
| 4 | WP-B1 closed — attestation signed by HR policy owner + ops lead + architecture lead | ☐ |

---

## 6. Ratification outcome

Governance decisions recorded during WP-B1 ratification sessions.

| Domain ID | Domain | Decision | Approved by | Date | Comments |
|-----------|--------|----------|-------------|------|----------|
| `PD-5.1` | Кадровое решение | **Ratified with Policy Debt** | Pending signature (HR policy owner + ops lead + architecture lead) | 2026-07-04 | Transitional `access_roles.code` for кадровое решение / executive HR decision authority **not defined**. Debt resolution deferred to **WP-B3**. Director contour `(1, 78, 62)` remains without approved baseline binding. **No runtime effect.** |
| `PD-5.2` | Кадровое оформление | Pending | — | — | |
| `PD-5.3` | Кадровый контроль / наблюдение | Pending | — | — | |
| `PD-5.4` | Линейное информирование | Pending | — | — | |

**Decision values (suggested):** `Ratified` / `Ratified with Policy Debt` / `Deferred` / `Rejected`

**WP-B1 closure rule:** all four domains reach `Ratified` or `Ratified with Policy Debt` (debt recorded in §6.1) — per [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) WP-B1 approval output. **WP-B1 remains open** (3/4 domains pending).

### 6.1 Policy debt register (WP-B1)

| Debt ID | Domain | Item | Resolution WP | Owner | Recorded | Runtime effect |
|---------|--------|------|---------------|-------|----------|----------------|
| **DEBT-B1-001** | `PD-5.1` | Transitional `access_roles.code` for кадровое решение / executive HR decision authority not defined in Reviewed ACCESS-001 | **WP-B3** | Pending assignment (HR policy owner + ops lead) | 2026-07-04 | **None** |

---

## 7. References

| Document | Role |
|----------|------|
| [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md) | Normative policy — §5 domains |
| [PERMISSION-DOMAIN-REGISTRY](./PERMISSION-DOMAIN-REGISTRY.md) | Domain catalog — update §5 after session |
| [ACCESS-002](./ACCESS-002-organizational-management-authority-model.md) | Orthogonal management layer — §3, §7 |
| [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) | WP-B1 criteria and sequencing |
| [POSITION-CABINET-IMPLEMENTATION-MASTER-PLAN](../roadmap/POSITION-CABINET-IMPLEMENTATION-MASTER-PLAN.md) | Tier G execution context |

---

## 8. Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-04 | 0.1 | Initial WP-B1 ratification package — four review sheets, consistency review, checklists, outcome template |
| 2026-07-04 | 0.2 | PD-5.1 recorded — Ratified with Policy Debt; DEBT-B1-001 → WP-B3; PD-5.2–PD-5.4 pending; WP-B1 open |
