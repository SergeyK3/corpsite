# WP-B4 — Position Cabinet Contour Binding Ratification Package

## Status

**Decision recorded (Review Board Session 1)** — 2026-07-06

Formal ratification package for **WP-B4 — Position Cabinet Contour Binding** under [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) (Tier G, Phase G1). **Ratification decision recorded** — see §6. **WP-B4 not closed** — attestation signatures pending. **No runtime effect.**

| Field | Value |
|-------|-------|
| Work package | WP-B4 — Position Cabinet Contour Binding / HR operational class assignments |
| Tier / phase | G — Governance / G1 — Policy Ratification |
| Normative document | [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](./WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) (**Prepared** — ratification subject) |
| Terminology | [GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md) |
| Session record | [review-board/WP-B4-SESSION-1-REVIEW-BOARD-RECORD.md](./review-board/WP-B4-SESSION-1-REVIEW-BOARD-RECORD.md) | **Complete** — 14/14 Accepted |
| Approval authority | HR policy owner + ops lead + executive sponsor (deputy admin) |
| Does not approve | OPS-030, §7 `policy_status=approved` rows, ACCESS-001 **Approved**, ADR-053 AC3 closure, runtime binding |

---

## 1. Purpose

This package assembles all information required for **formal Review Board ratification** of WP-B4.

| Statement | Detail |
|-----------|--------|
| **Normative model** | Ratifies [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](./WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) — Cabinet-stable contour binding, ownership model, binding rules, Persistent Workspace characterisation |
| **HR operational class assignments** | Assigns permission classes to contours `(1, 73, 86)` and `(1, 78, 77)` per program scope |
| **Policy debt disposition** | Dispositions **DEBT-B1-004**; confirms **DEBT-B1-001** remains **open → WP-B8** |
| **No new architecture** | Content derives from Accepted ARCH-001, ADR-050/051/053/036, and completed WP-B1–B3 outputs |
| **No implementation approved** | Ratifying WP-B4 does not authorize OPS-030, Phase 2.6b, schema changes, or enforcement cutover |
| **Terminology** | Uses [GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md) — terms not redefined in this package |

**WP-B4 output (when complete):** signed attestation that the Position Cabinet contour binding model and HR operational class assignments are accepted — recorded in Session 1 record and §6 of this package.

---

## 2. Ratification scope

### 2.1 In scope

| # | Subject | Source |
|---|---------|--------|
| 1 | **INV-B4-001…003** as binding governance input | [Problem Space Review §3](./WP-B4-PROBLEM-SPACE-REVIEW.md#3-architectural-invariant-recorded); Main doc §8 |
| 2 | **Cabinet-stable contour binding model** | Main doc §3, §6 |
| 3 | **Persistent Workspace characterisation** | Main doc §5; [Conceptual Review](./WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md) |
| 4 | **Position-owned vs Employee-owned boundaries** | Main doc §4, §6; GLOSS-B4-001 §5–§6 |
| 5 | **HR class assignment** — contour `(1, 73, 86)` | **PD-5.2** (кадровое оформление) |
| 6 | **HR class assignment** — contour `(1, 78, 77)` | **PD-5.3** (кадровый контроль / наблюдение) |
| 7 | **DEBT-B1-004 disposition** | WP-B1 §6.1; Main doc §1.2 |
| 8 | **DEBT-B1-001 confirmation** | Remains **open → WP-B8** — no closure |

### 2.2 Out of scope

| Topic | Owner |
|-------|-------|
| PD-5.1 transitional `access_roles.code` | **WP-B8** — **DEBT-B1-001** |
| §7 `policy_status=approved` rows | **WP-B7** |
| OPS-030 / Phase 2.6b execution | **Tier B** / **WP-X3** (AC3) |
| Acting overlay implementation | **ADR-036 Phase 3** |
| Active Cabinet Session semantics | **OQ-B4-001** — deferred backlog |
| Accepted ADR amendment | **Architecture Freeze** |
| API, schema, migrations, RBAC, UI implementation | Forbidden in Tier G |

---

## 3. Documents submitted

| # | Document | Role | Version / status |
|---|----------|------|------------------|
| 1 | [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](./WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) | **Normative governance model** | v0.1 — Prepared |
| 2 | [GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md) | Authoritative terminology | v1.1 — Active |
| 3 | [WP-B4-PROBLEM-SPACE-REVIEW.md](./WP-B4-PROBLEM-SPACE-REVIEW.md) | Problem Space analysis; INV-B4 record | v0.5 — Complete |
| 4 | [WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md](./WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md) | Persistent Workspace conceptual justification | v0.2 — Complete |
| 5 | [review-board/WP-B4-REVIEW-BOARD-BRIEF.md](./review-board/WP-B4-REVIEW-BOARD-BRIEF.md) | Review Board briefing | v0.2 — Briefing complete |
| 6 | [review-board/WP-B4-SESSION-1-REVIEW-BOARD-RECORD.md](./review-board/WP-B4-SESSION-1-REVIEW-BOARD-RECORD.md) | Session 1 record | **Complete** |
| 7 | This ratification package | Assembly and checklists | v0.1 — Prepared |

**Prior work packages (inputs — not re-ratified):**

| Package | Relevance |
|---------|-----------|
| [WP-B1](./WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md) | PD-5.2, PD-5.3 taxonomy; **DEBT-B1-004** |
| [WP-B2](./WP-B2-BINDING-PRINCIPLES-REVIEW.md) | P1, P2, P6, P8 |
| [WP-B3 Closure Report](./WP-B3-CLOSURE-REPORT.md) | PD-5.1 class; **DEBT-B1-001 → WP-B8** |

**Governance Package Consistency Review:** internally consistent and ready for Review Board ratification (2026-07-06).

---

## 4. Review criteria

Review Board **SHALL** verify before recording ratification:

| # | Criterion | Evidence |
|---|-----------|----------|
| RC-1 | **INV-B4-001…003** accepted as binding input | Session Q-A1; Main doc §8 |
| RC-2 | Cabinet-stable Template binding affirmed | Session Q-A2; Main doc §3.2 |
| RC-3 | Acting Person not recorded as Cabinet Owner | Session Q-A3; Main doc §4.3 |
| RC-4 | Position-owned vs Employee-owned split accepted | Session Q-B1; GLOSS §5–§6 |
| RC-5 | UI carcase acknowledged as directional input only | Session Q-B2 |
| RC-6 | WP-B3 orthogonality preserved | Session Q-C1 |
| RC-7 | **OQ-B4-001** deferred — non-blocking | Session Q-C2 |
| RC-8 | **DEBT-B1-001** confirmed open → **WP-B8** | Session Q-C3 |
| RC-9 | Persistent Workspace characterisation accepted | Session Q-D1; Main doc §5 |
| RC-10 | Normative model ([Main doc](./WP-B4-POSITION-CABINET-CONTOUR-BINDING.md)) ratified | Session Q-D2 |
| RC-11 | HR head contour `(1, 73, 86)` class assigned | Session Q-E1; Review sheet §5.1 |
| RC-12 | Deputy admin contour `(1, 78, 77)` class assigned | Session Q-E2; Review sheet §5.2 |
| RC-13 | **DEBT-B1-004** disposition recorded | Session Q-F1 |
| RC-14 | Session does not authorize implementation | Session Q-G1 |
| RC-15 | Ratification record wording includes explicit non-authorizations | Session Q-G2 |
| RC-16 | No Accepted ADR contradiction | Architecture Freeze |
| RC-17 | Mandatory approvers identified | ACCESS-RATIFICATION-PROGRAM §4.1 WP-B4 |

---

## 5. Ratification checklist

Complete during Review Board Session 1. Record outcomes in [Session 1 record](./review-board/WP-B4-SESSION-1-REVIEW-BOARD-RECORD.md) and §6 below.

### 5.1 Contour binding model

| # | Item | Decision |
|---|------|----------|
| 1 | **INV-B4-001** accepted | ☑ |
| 2 | **INV-B4-002** accepted | ☑ |
| 3 | **INV-B4-003** accepted | ☑ |
| 4 | Cabinet-stable binding rule accepted (Main doc §3.2) | ☑ |
| 5 | Binding rules **BR-A1…A6** accepted (Main doc §6.4) | ☑ |
| 6 | Ownership preservation rules accepted (Main doc §6.5) | ☑ |
| 7 | Persistent Workspace characterisation accepted (Main doc §5) | ☑ |
| 8 | Position-owned vs Employee-owned split accepted | ☑ |
| 9 | WP-B3 orthogonality affirmed | ☑ |
| 10 | **OQ-B4-001** recorded as deferred backlog | ☑ |
| 11 | **DEBT-B1-001** confirmed open → **WP-B8** (not closed) | ☑ |

### 5.2 Contour review sheet — `(1, 73, 86)` HR head

| Field | Content |
|-------|---------|
| **Contour** | `(client_scope_id=1, org_unit_id=73, catalog_position_id=86)` — Руководитель отдела кадров |
| **Program scope** | **PD-5.2** — кадровое оформление |
| **Organizational purpose** | HR department execution of кадровые процессы — document preparation and enrollment, not executive decision |
| **Not the same as** | PD-5.1 (кадровое решение); PD-5.3; line boundary (PD-5.4); ACCESS-002 management responsibilities |
| **Binding note** | Class assignment is **Cabinet baseline property** — independent of acting Person on adjacent executive contours (**INV-B4-002**) |
| **Related access_roles** | `HR_ENROLLMENT_MANAGER` — **candidate** transitional code only (WP-B1); Board may ratify class with or without code approval |
| **§7 status today** | **Pending** — row disposition is **WP-B7**; not approved by WP-B4 alone |
| **Runtime impact** | **None** upon WP-B4 ratification alone |

| # | Checklist item | Decision |
|---|----------------|----------|
| 1 | **PD-5.2** accepted as permission class for this contour | ☑ |
| 2 | Contour binding understood as Cabinet-stable | ☑ |
| 3 | Transitional code **`HR_ENROLLMENT_MANAGER`** for `(1, 73, 86)` ratified (governance policy) | ☑ |
| 4 | Does not approve §7 row or OPS-030 | ☑ |

### 5.3 Contour review sheet — `(1, 78, 77)` deputy admin

| Field | Content |
|-------|---------|
| **Contour** | `(client_scope_id=1, org_unit_id=78, catalog_position_id=77)` — Зам по адм вопросам |
| **Program scope** | **PD-5.3** — кадровый контроль / наблюдение |
| **Organizational purpose** | HR oversight visibility — see кадровые процессы for control/compliance without HR processing execution |
| **Not the same as** | PD-5.1; PD-5.2 execution; `HR_ENROLLMENT_MANAGER` by default (P8); ACCESS-002 management visibility |
| **Binding note** | Class assignment is **Cabinet baseline property** — acting on executive contours does not transfer ownership (**INV-B4-002**) |
| **Related access_roles** | **None defined** in Reviewed ACCESS-001 — **DEBT-B1-004** disposition required |
| **§7 status today** | **Pending** — row disposition is **WP-B7** |
| **Runtime impact** | **None** upon WP-B4 ratification alone |

| # | Checklist item | Decision |
|---|----------------|----------|
| 1 | **PD-5.3** accepted as permission class for this contour | ☑ |
| 2 | Contour binding understood as Cabinet-stable | ☑ |
| 3 | **DEBT-B1-004** disposition recorded — **Continues → WP-B8** | ☑ |
| 4 | Does not approve §7 row or OPS-030 | ☑ |

### 5.4 WP-B4 package completion

| # | Item | Decision |
|---|------|----------|
| 1 | All Session 1 mandatory questions answered | ☑ (14/14) |
| 2 | Normative model ratified or deferred with rationale | ☑ **Ratified** |
| 3 | HR contour class assignments recorded (§6) | ☑ |
| 4 | Policy debt disposition coherent (§6.4) | ☑ |
| 5 | Ratification record wording accepted (Session Q-G2) | ☑ |
| 6 | WP-B4 closed — attestation signed by HR policy owner + ops lead + executive sponsor | ☐ |

---

## 6. Ratification outcome

Recorded from [Session 1 record](./review-board/WP-B4-SESSION-1-REVIEW-BOARD-RECORD.md) — 2026-07-06.

### 6.1 Overall session outcome

| Field | Value |
|-------|-------|
| **Session** | WP-B4 Review Board Session 1 |
| **Date** | 2026-07-06 |
| **Overall outcome** | **Ratified with Policy Debt** |
| **Approved by** | Pending signature (HR policy owner + ops lead + executive sponsor) |
| **Runtime effect** | **None** |

### 6.2 Normative model ratification

| Subject | Decision | Date | Comments |
|---------|----------|------|----------|
| **WP-B4 Position Cabinet Contour Binding** (Main doc) | **Ratified** | 2026-07-06 | Status → **Accepted (Ratified)**; INV-B4-001…003; binding rules; Persistent Workspace; data ownership |
| **INV-B4-001…003** | **Accepted** | 2026-07-06 | Binding governance input for WP-B7 |

### 6.3 HR operational class assignments

| Contour | Permission class | Decision | Transitional code | Comments |
|---------|------------------|----------|-------------------|----------|
| `(1, 73, 86)` | **PD-5.2** — кадровое оформление | **Ratified** | **`HR_ENROLLMENT_MANAGER`** (governance policy for this contour) | §7 row **not approved** — **WP-B7** |
| `(1, 78, 77)` | **PD-5.3** — кадровый контроль / наблюдение | **Ratified** | **Not ratified** | **DEBT-B1-004** continues → **WP-B8** |

### 6.4 Policy debt register (post–Session 1)

| Debt ID | Status | Item | Resolution WP | Recorded |
|---------|--------|------|---------------|----------|
| **DEBT-B1-001** | **Open** | Transitional `access_roles.code` for PD-5.1 not ratified | **WP-B8** | 2026-07-04 (WP-B3) — confirmed Session 1 |
| **DEBT-B1-004** | **Open** | Transitional `access_roles.code` for PD-5.3 / `(1, 78, 77)` not ratified | **WP-B8** | 2026-07-06 — class closed; code continues |

### 6.5 Explicit non-authorizations (recorded in Session 1)

Session **SHALL** record that WP-B4 ratification:

- **Does not** approve ACCESS-001 §7 rows or set `policy_status=approved`
- **Does not** promote ACCESS-001 to **Approved** (WP-X2)
- **Does not** authorize OPS-030, ADR-053 AC3 closure, or Phase 2.6b
- **Does not** close **DEBT-B1-001** (remains **WP-B8**)
- **Does not** amend Accepted ADR or ARCH-001
- **Does not** change runtime enforcement

---

## 7. References

| Document | Role |
|----------|------|
| [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) | WP-B4 criteria, sequencing, approval authority |
| [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](./WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) | Normative governance model |
| [GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md) | Terminology |
| [WP-B4-PROBLEM-SPACE-REVIEW.md](./WP-B4-PROBLEM-SPACE-REVIEW.md) | Problem Space; INV-B4; M1–M6 |
| [WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md](./WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md) | Persistent Workspace justification |
| [review-board/WP-B4-REVIEW-BOARD-BRIEF.md](./review-board/WP-B4-REVIEW-BOARD-BRIEF.md) | Review Board briefing |
| [review-board/WP-B4-SESSION-1-REVIEW-BOARD-RECORD.md](./review-board/WP-B4-SESSION-1-REVIEW-BOARD-RECORD.md) | Session 1 formal record |
| [ACCESS-001](./ACCESS-001-organizational-permission-matrix.md) | Normative policy — **Reviewed** |
| [ACCESS-002](./ACCESS-002-organizational-management-authority-model.md) | Orthogonal management layer — **Reviewed** |
| [ARCH-001](../architecture/ARCH-001-position-permission-model.md) | **Accepted** architecture |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) | Cabinet model |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | Access resolution |
| [ADR-053](../adr/ADR-053-permission-template-binding-model.md) | Template binding |
| [ADR-036](../adr/ADR-036-hr-events-unified-model.md) | Acting overlay |
| [PERMISSION-DOMAIN-REGISTRY](./PERMISSION-DOMAIN-REGISTRY.md) | Domain catalog |
| [POSITION-CABINET-IMPLEMENTATION-MASTER-PLAN](../roadmap/POSITION-CABINET-IMPLEMENTATION-MASTER-PLAN.md) | Program context |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-06 | 0.1 | Initial ratification package — prepared for Review Board Session 1 |
| 2026-07-06 | 1.0 | Review Board Session 1 — **Ratified with Policy Debt**; §6 outcome recorded |
