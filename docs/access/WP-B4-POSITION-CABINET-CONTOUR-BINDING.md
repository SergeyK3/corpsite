# WP-B4 — Position Cabinet Contour Binding

## Status

**Accepted (Ratified)** — 2026-07-06

Normative governance document for **WP-B4 — Position Cabinet Contour Binding** under [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) (Tier G, Phase G1). **Ratified** by Review Board Session 1 — see [Session 1 record](./review-board/WP-B4-SESSION-1-REVIEW-BOARD-RECORD.md). **WP-B4 not closed** — attestation signatures pending. **No runtime effect.** **No Accepted ADR amendment.**

| Field | Value |
|-------|-------|
| Work package | WP-B4 — Position Cabinet Contour Binding / HR operational class assignments |
| Tier / phase | G — Governance / G1 — Policy Ratification |
| Ratification | [WP-B4-RATIFICATION-PACKAGE.md](./WP-B4-RATIFICATION-PACKAGE.md); [Session 1 record](./review-board/WP-B4-SESSION-1-REVIEW-BOARD-RECORD.md) — **Ratified with Policy Debt** — 2026-07-06 |
| Terminology | [GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md) — authoritative vocabulary; terms **not redefined** here |
| Preparatory inputs | [GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md); [WP-B4 Problem Space Review](./WP-B4-PROBLEM-SPACE-REVIEW.md); [WP-B4 Conceptual Review](./WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md); [WP-B4 Review Board Brief](./review-board/WP-B4-REVIEW-BOARD-BRIEF.md) |
| Approval authority | HR policy owner + ops lead + executive sponsor (deputy admin) |
| Normative policy (unchanged) | ACCESS-001, ACCESS-002 — **Reviewed**; ARCH-001 — **Accepted** |

---

## 1. Purpose and scope

### 1.1 Purpose

WP-B4 establishes the **governance model for Position Cabinet contour binding** — how organizational permission policy attaches to **Position Cabinet identity** on the Permission Template baseline, independent of transient occupant or acting Person.

The organization **SHALL** treat contour binding as a **Cabinet-stable** property: Permission Template configuration and contour rules bind to org-unique **Position / Position Cabinet**, not to Person, Platform User, or temporary acting access.

WP-B4 also carries the program mandate to assign **HR operational permission classes** to HR-service contours and to disposition **DEBT-B1-004** — within the binding model defined in this document.

### 1.2 Scope

| In scope | Detail |
|----------|--------|
| **Contour binding governance** | Cabinet-stable Template binding; owner vs acting separation; position-owned vs employee-owned data boundaries |
| **Architecture invariants** | **INV-B4-001**, **INV-B4-002**, **INV-B4-003** — binding input for all WP-B4 contour decisions |
| **Persistent Workspace characterisation** | Governance label for Position Cabinet durability — per [Conceptual Review](./WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md); not a new entity |
| **HR operational class assignments** | Contour `(1, 73, 86)` — **PD-5.2** (кадровое оформление); contour `(1, 78, 77)` — **PD-5.3** (кадровый контроль / наблюдение) — **Review Board ratification subject** |
| **DEBT-B1-004** | Transitional code / class mapping for deputy admin contour — **Review Board disposition subject** |

| Out of scope | Owner |
|--------------|-------|
| PD-5.1 transitional `access_roles.code` | **WP-B8** — **DEBT-B1-001 remains open** |
| §7 `policy_status=approved` rows | **WP-B7** |
| OPS-030 / Phase 2.6b execution | **Tier B** / **WP-X3** (AC3) |
| Acting overlay implementation | **ADR-036 Phase 3** — engineering |
| Active Cabinet Session semantics | **OQ-B4-001** — deferred backlog |
| API, schema, migrations, RBAC, UI implementation | Forbidden in Tier G governance |
| Accepted ADR amendment | **Architecture Freeze** |

### 1.3 Relationship to adjacent work packages

```text
WP-B1 (domain taxonomy) ──► WP-B2 (binding principles) ──► WP-B3 (PD-5.1 class)
                                      │
                                      ▼
                            WP-B4 (contour binding model + HR class assignment)
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
               WP-B7 (§7 rows)   WP-B8 (open Q)    WP-X1 (cross-layer)
                    │
                    ▼
            ACCESS-001 Approved + WP-X3 (AC3) ──► OPS-030
```

| Package | Relationship |
|---------|--------------|
| **WP-B1** | Supplies permission domain taxonomy (**PD-5.2**, **PD-5.3**); **DEBT-B1-004** recorded |
| **WP-B2** | Supplies binding principles **P1**, **P2**, **P6**, **P8** — Cabinet-centric binding; HR class scope constraints |
| **WP-B3** | Supplies **PD-5.1** positive class and PD-5.1/PD-5.2 boundary; **DEBT-B1-001 → WP-B8** — does not block HR-service WP-B4 path |
| **WP-B7** | Consumes contour binding model for row disposition; **≥1** `approved` row required for AC3 |
| **WP-B8** | Resolves **DEBT-B1-001** and transitional catalog questions |

---

## 2. Position Cabinet in platform architecture

Position Cabinet is the **central operational anchor** of the Position Cabinet Architecture (ARCH-001). At platform level:

| Layer | Role |
|-------|------|
| **Organization** | Owns staffing structure; Position is org-unique штатная единица |
| **Position** | Unique organizational staffing unit; lifecycle defines Cabinet lifecycle |
| **Position Cabinet** | Digital representation of Position — 1:1 (ADR-050); see [GLOSS-B4-001 §1](./GLOSS-B4-001-position-cabinet-vocabulary.md) |
| **Permission Template** | Configuration component **inside** Cabinet — transitional `access_roles` binding per ADR-053 |
| **Person / Platform User** | Authentication and identity; **not** baseline permission binding subject (ACCESS-001 P1) |

Effective permissions for a Person are derived from **accessible Position Cabinets** (Employment + acting overlay per ADR-051) — not from User account attributes or job title inference (ADR-053 §3.4).

**Governance stance:** Position Cabinet is the **Persistent Workspace of Position** — a characterisation of existing Accepted architecture, not a separate domain entity ([GLOSS-B4-001 §2](./GLOSS-B4-001-position-cabinet-vocabulary.md)).

---

## 3. Contour binding

Contour binding attaches organizational permission policy to a **Position Cabinet** identified by org-unique contour tuple `(client_scope_id, org_unit_id, catalog_position_id)` per ACCESS-001 §7 and ADR-053.

### 3.1 Binding dimensions

| Dimension | Contour binding role |
|-----------|---------------------|
| **Position** | Contour identifies org-unique Position; Cabinet binds 1:1 to Position |
| **Employment / Position Occupancy** | Permanent Employment opens or closes **access** to Cabinet; **does not** rebind Template to Person |
| **Person / Employee** | Person holds Cabinet Owner relation via Employment; Employee record carries **employee-owned** data — orthogonal to Template identity |
| **Organization** | Position and Cabinet are organizational assets; entity ownership is Position/organization, never Person |
| **Permission domains (ACCESS-001 §5)** | Organizational permission **class** assigned to Cabinet contour through governance (WP-B4/WP-B7); domain ratification (WP-B1) precedes row approval |
| **Management hierarchy (ACCESS-002)** | Management **responsibilities** attach to Cabinet contour orthogonally — WP-X1 alignment before shared-contour row approvals |
| **ACCESS-001** | Permission matrix §7 rows disposition **policy_status**; class clarification precedes OPS-030 insert (§5.5) |
| **ACCESS-002** | Management responsibility matrix for same contours — must not be conflated with permission class assignment |

### 3.2 Cabinet-stable binding rule

> **Permission Template contour binding SHALL attach to Position Cabinet / Position identity. Owner change, acting overlay, or vacancy SHALL NOT trigger Template rebinding, Template copy from occupant, or baseline inference from current Person.**

Sources: ACCESS-001 **P1**, **P2**; ADR-053 §3.4; **INV-B4-001**, **INV-B4-002**.

### 3.3 HR-service contours in WP-B4 program scope

| Contour | Catalog position (typical) | Permission domain (program scope) | Binding note |
|---------|---------------------------|-----------------------------------|--------------|
| `(1, 73, 86)` | Руководитель отдела кадров | **PD-5.2** — кадровое оформление | Class + transitional code — **Review Board ratification**; Phase 2.6b MVP candidate |
| `(1, 78, 77)` | Зам по адм вопросам | **PD-5.3** — кадровый контроль / наблюдение | Class + code — **Review Board ratification**; **DEBT-B1-004** disposition |

Director contour `(1, 78, 62)` (**PD-5.1**) is **not** WP-B4 binding scope for transitional code — positive class ratified WP-B3; **DEBT-B1-001** remains **open → WP-B8**.

### 3.4 Contour binding vs permission exercise (WP-B3 orthogonality)

| Layer | Governs |
|-------|---------|
| **WP-B3 (PD-5.1)** | Who may **exercise** executive HR decision authority **in Director Cabinet context** — including valid acting access |
| **WP-B4 (this document)** | When **permanent Cabinet Owner** changes; when acting is **access overlay only**; Template binding stability |

These layers **SHALL NOT** be conflated: PD-5.1 authorship may follow acting access to Director Cabinet; acting **SHALL NOT** transfer permanent Employment or Cabinet Owner status on any contour.

---

## 4. Cabinet ownership model

Terminology: [GLOSS-B4-001 §3–§6](./GLOSS-B4-001-position-cabinet-vocabulary.md).

### 4.1 Entity ownership

| Entity | Owner |
|--------|-------|
| **Position Cabinet** | **Position / organization** — never Person, Employee, or Platform User |
| **Cabinet Owner** | **Role relation** — Person with permanent Employment on Position; not an entity owner |
| **Acting Assignment** | **Access overlay** — not an ownership relation |
| **Position-owned Data** | **Position Cabinet** |
| **Employee-owned Data** | **Person / Employee** |

### 4.2 Cabinet Owner

Cabinet Owner is the Person holding **permanent Position Occupancy** via active **Employment** on the Position linked to the Cabinet.

Cabinet Owner **SHALL** change **only** through HR events that alter permanent Position Occupancy (**INV-B4-001**).

### 4.3 Acting Assignment

Acting Assignment is a **time-bounded overlay** granting a Person access to another Position's Cabinet **without** closing primary Employment and **without** transferring Cabinet Owner status (**INV-B4-002**, **INV-B4-003**).

Acting Assignee **SHALL NOT** be recorded as Cabinet Owner in policy artefacts, contour binding records, or Template disposition.

### 4.4 Position-owned Data

Position-owned operational artefacts **SHALL** remain bound to Position Cabinet across owner change and acting periods. See [GLOSS-B4-001 §5](./GLOSS-B4-001-position-cabinet-vocabulary.md).

Governance examples (directional): tasks and backlog, KPI aggregates, dashboards, reporting history, function documents — per ARCH-001 §4.4.

### 4.5 Employee-owned Data

Employee-owned personal and HR artefacts **SHALL** remain bound to Person / Employee — not to Position Cabinet identity. See [GLOSS-B4-001 §6](./GLOSS-B4-001-position-cabinet-vocabulary.md).

Acting Assignee **SHALL NOT** inherit, replace, or rebind permanent Cabinet Owner's employee-owned profile.

---

## 5. Persistent Workspace

Position Cabinet **SHALL** be characterised in governance as the **Persistent Workspace of Position** ([GLOSS-B4-001 §2](./GLOSS-B4-001-position-cabinet-vocabulary.md)).

| Statement | Detail |
|-----------|--------|
| **Synonymy** | Persistent Workspace is a **governance characterisation** of Position Cabinet — **not** a separate entity, table, or ADR scope |
| **Durability** | Position-bound tasks, results, KPI, dashboards, function artefacts, and Permission Template configuration **accumulate and endure** across occupants |
| **Access model** | Person receives **time-bounded access** via Employment and acting overlay; workspace state **persists** independently |
| **Distinction** | Post-login **UI shell** («личный кабинет») is presentation aggregation — not domain ownership (ARCH-001 §8; ADR-007 legacy UX term) |

This characterisation **does not** amend Accepted ADR text; it aligns governance vocabulary with ARCH-001 §4.1–§4.6 and ADR-050 lifecycle semantics.

---

## 6. Binding rules

### 6.1 Owner lifecycle

Cabinet Owner **SHALL** change when permanent Position Occupancy changes through cadre events including:

- Initial hire on position (приём; первичное Занятие должности)
- Transfer to another position (перевод)
- Dismissal / termination (увольнение)
- Re-hire (повторный приём)
- Position abolition / closure (ликвидация штатной единицы)
- Other HR events altering **permanent** Employment on the Position

On owner change:

- Position Cabinet **persists** unchanged
- Permission Template **remains** on Cabinet — **no rebinding**
- Position-owned Data **remains** in Cabinet
- New Cabinet Owner **inherits access** to existing workspace state
- Prior Cabinet Owner **retains** their Employee-owned Data

### 6.2 Employee lifecycle

Employee-owned Data **SHALL** follow Person / Employee career across Positions and Cabinets.

Employee lifecycle events **SHALL NOT**:

- Define Cabinet Owner change by themselves
- Migrate Position-owned Data out of Cabinet
- Trigger Template rebinding

### 6.3 Cabinet lifecycle

| Event | Cabinet |
|-------|---------|
| Position created | Cabinet **created** together with Position |
| Vacancy (no active Owner) | Cabinet **persists** with full operational history |
| Owner change | Cabinet **persists** — access opens/closes for Persons |
| Acting period | Cabinet **persists** — acting Person receives overlay access |
| Position abolished | Cabinet lifecycle **ends** with Position |

### 6.4 Acting overlay

| Rule | Requirement |
|------|-------------|
| **BR-A1** | Acting **MAY** grant access to tasks, management actions, and operational cabinet functions for target Cabinet (Problem Space rules **A1**) |
| **BR-A2** | Acting **SHALL NOT** transfer Cabinet Owner status |
| **BR-A3** | Acting **SHALL NOT** rebind Employee-owned Data to acting Person |
| **BR-A4** | Acting **SHALL NOT** reset, zero, or migrate Position-owned KPI, dashboards, tasks, or reporting history |
| **BR-A5** | Acting Person's primary Employment **SHALL** remain unchanged (ADR-036, ADR-051) |
| **BR-A6** | On acting period end, acting access closes; Cabinet Owner and position-owned state **SHALL** remain unchanged |

### 6.5 Ownership preservation

The organization **SHALL** preserve the following invariants across all contour binding and HR class decisions:

1. **Template stability** — contour rules attach to Cabinet identity, not occupant
2. **Workspace continuity** — position-owned operational state survives owner change and acting
3. **Employee boundary** — personal HR data stays Person-bound; acting does not corrupt the split
4. **Vacancy clarity** — unoccupied Position ≠ acting Person as owner

**Forbidden anti-patterns:** Template copy from acting Person; occupant-inferred binding; treating и.о. as owner substitution for contour class assignment; migrating position-owned history to acting Employee record.

---

## 7. Relationship with normative sources

| Source | WP-B4 consumption |
|--------|-------------------|
| **[WP-B1](./WP-B1-PERMISSION-DOMAIN-RATIFICATION-PACKAGE.md)** | **PD-5.2**, **PD-5.3** domain taxonomy ratified; **DEBT-B1-004** → WP-B4 |
| **[WP-B2](./WP-B2-BINDING-PRINCIPLES-REVIEW.md)** | **P1** Cabinet binding subject; **P2** no occupant/grant inference; **P6**/**P8** HR class scope |
| **[WP-B3](./WP-B3-CLOSURE-REPORT.md)** | **PD-5.1** class; PD-5.1/PD-5.2 boundary; **DEBT-B1-001 → WP-B8** |
| **[ARCH-001](../architecture/ARCH-001-position-permission-model.md)** | Employment, Cabinet durability §4.2–§4.6; occupant change preserves Cabinet |
| **[ARCHITECTURE_GOVERNANCE](../architecture/ARCHITECTURE_GOVERNANCE.md)** | Principles 4–6 — Position, Cabinet, authority follows occupancy |
| **[ACCESS-001](./ACCESS-001-organizational-permission-matrix.md)** | §4 principles; §5 domains; §7 contour inventory — **Reviewed** |
| **[ACCESS-002](./ACCESS-002-organizational-management-authority-model.md)** | Orthogonal management responsibilities — **Reviewed** |
| **[ADR-050](../adr/ADR-050-organization-position-cabinet-model.md)** | Position 1:1 Cabinet; Template inside Cabinet |
| **[ADR-051](../adr/ADR-051-cabinet-access-resolution.md)** | Employment + acting → accessible cabinets; no enforcement cutover in Phase 2.6 |
| **[GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md)** | Authoritative Tier G terminology for WP-B4 and downstream packages |

**Explicit:** WP-B4 **does not** amend any of the above sources.

---

## 8. Architecture invariants

The following invariants **SHALL** govern all WP-B4 contour binding and HR class decisions and **SHALL** be accepted as binding governance input for downstream **WP-B7** disposition.

### INV-B4-001 — Owner change requires permanent occupancy change

> Cabinet Owner (permanent Position Occupant) changes **only** through HR events that alter permanent Position Occupancy (Employment on org-unique Position).

### INV-B4-002 — Acting does not transfer ownership

> Acting Assignment grants operational and permission access to a Position Cabinet for a bounded period. Acting Assignment **does not** transfer Cabinet Owner status and **must not** be interpreted as owner change for contour binding or data ownership.

### INV-B4-003 — Position Cabinet is the duty shell

> Position Cabinet is the working shell of the **organizational position**, not of the temporary executor. A temporary executor may receive delegated/acting access but **does not** become Cabinet Owner.

**Accepted sources (not amended):** ARCH-001 §3.2, §4.2–§4.3, §4.6; ADR-050; ADR-051; ADR-036.

---

## 9. Explicit non-goals

WP-B4 **SHALL NOT**:

| Non-goal | Detail |
|----------|--------|
| Amend Accepted ADR or ARCH-001 | Architecture Freeze in effect |
| Promote ACCESS-001 to **Approved** | **WP-X2** |
| Approve §7 `policy_status=approved` rows | **WP-B7** |
| Authorize OPS-030 or close ADR-053 AC3 | **Tier B** / **WP-X3** |
| Close **DEBT-B1-001** | Remains **open → WP-B8** |
| Implement acting overlay, Employment retargeting, or resolver enforcement | Engineering programs |
| Define Active Cabinet Session semantics | **OQ-B4-001** — deferred |
| Create API, schema, RBAC, or UI deliverables | Implementation scope |
| Introduce new domain entities | Persistent Workspace is glossary characterisation only |
| Re-ratify WP-B3 PD-5.1 class definition | Consumed as input only |

**Runtime:** Legacy enforcement remains authoritative. No governance artefact from WP-B4 changes authorization behaviour until future approved implementation gates close.

---

## 10. Downstream implications

### 10.1 WP-B7 — Matrix row disposition

- Contour binding **SHALL** reference **INV-B4-001…003** when dispositioning HR and executive rows
- HR head `(1, 73, 86)` `approved` is Phase 2.6b MVP gate — **after** WP-B4 class/code ratification and WP-B7 session
- Director `(1, 78, 62)` `approved` **blocked** until **WP-B8** resolves **DEBT-B1-001** code mapping

### 10.2 WP-B8 — Open policy questions

- **DEBT-B1-001** (PD-5.1 transitional `access_roles.code`) — **unchanged**, **open**
- Transitional catalog sufficiency may also address **DEBT-B1-004** elements

### 10.3 WP-X1 — Cross-layer boundary

- Shared contours (HR head, deputy admin, Director, line heads) **SHOULD** complete WP-X1 crosswalk before row **approved** disposition

### 10.4 Implementation chain (not authorized by WP-B4)

```text
WP-B4 ratification (governance)
    → WP-B7 §7 disposition (≥1 approved row)
    → WP-X2 ACCESS-001 Approved
    → WP-X3 ADR-053 AC3
    → Tier B OPS-030 / Phase 2.6b
```

### 10.5 Deferred backlog — OQ-B4-001

**OQ-B4-001** (Cabinet Owner × Acting Assignment × Active Cabinet Session) **remains open** and **does not block** WP-B4 ratification or HR class assignment. Resolution belongs to runtime access design phase — notifications, electronic document approval, audit journals.

---

## Review Board ratification subjects

Upon Review Board session, the organization **SHALL** ratify or reject:

| # | Subject | This document section |
|---|---------|----------------------|
| 1 | **INV-B4-001…003** as binding governance input | §8 |
| 2 | **Cabinet-stable contour binding model** | §3, §6 |
| 3 | **Persistent Workspace characterisation** | §5 |
| 4 | **Position-owned vs Employee-owned boundaries** | §4, §6 |
| 5 | **HR class assignment** — `(73, 86)` / `(78, 77)` | §3.3 — **separate Review Board decision** |
| 6 | **DEBT-B1-004 disposition** | §1.2 — **separate Review Board decision** |
| 7 | **DEBT-B1-001 remains open → WP-B8** | §9 — confirmation only |

Until Review Board ratification is recorded, this document **SHALL NOT** be treated as organizational policy approval, OPS-030 authorization, or §7 row approval.

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-06 | 0.1 | Initial normative governance document — consolidated from WP-B4 preparatory artefacts; awaiting Review Board |
| 2026-07-06 | 1.0 | Review Board Session 1 — **Accepted (Ratified)**; see Session 1 record |
