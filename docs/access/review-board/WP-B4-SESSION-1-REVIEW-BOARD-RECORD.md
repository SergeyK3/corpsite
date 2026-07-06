# WP-B4 Review Board Session 1 — Record

## Position Cabinet Contour Binding

## Status

**Session complete** — 2026-07-06

Formal governance record for **WP-B4 Review Board Session 1**. **No runtime effect.** **No implementation authority.**

| Field | Value |
|-------|-------|
| Session | WP-B4 Review Board Session 1 |
| Package | WP-B4 — Position Cabinet Contour Binding / HR operational class assignments |
| Ratification package | [WP-B4-RATIFICATION-PACKAGE.md](../WP-B4-RATIFICATION-PACKAGE.md) |
| Brief | [WP-B4-REVIEW-BOARD-BRIEF.md](./WP-B4-REVIEW-BOARD-BRIEF.md) |
| Normative document | [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) — **Accepted (Ratified)** |
| Terminology | [GLOSS-B4-001](../GLOSS-B4-001-position-cabinet-vocabulary.md) |
| Approval authority | HR policy owner + ops lead + executive sponsor (deputy admin) |
| Attestation | **Pending signature** |
| Runtime effect | **None** |

---

## Session outcome (summary)

| Field | Value |
|-------|-------|
| **Overall outcome** | **Ratified with Policy Debt** |
| **Date** | 2026-07-06 |
| **Normative model** | [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) — **Ratified** |
| **INV-B4-001…003** | **Accepted** — binding governance input |
| **HR head `(1, 73, 86)`** | **Ratified** — **PD-5.2**; transitional code **`HR_ENROLLMENT_MANAGER`** for this contour (governance policy; §7 not approved) |
| **Deputy admin `(1, 78, 77)`** | **Ratified** — **PD-5.3**; transitional code **not ratified** |
| **DEBT-B1-004** | **Continues** — transitional code for `(1, 78, 77)` → **WP-B8** (class assignment closed) |
| **DEBT-B1-001** | **Open → WP-B8** — confirmed; **not closed** |
| **OQ-B4-001** | **Open** — deferred; non-blocking |
| **WP-B4 Session 2** | **Not required** |
| **Formal WP-B4 closure** | **Pending** — attestation signatures |

**Explicit session boundaries (recorded):**

- Does **not** approve ACCESS-001 §7 rows or set `policy_status=approved`.
- Does **not** promote ACCESS-001 to **Approved** (WP-X2).
- Does **not** authorize OPS-030, ADR-053 AC3 closure, or Phase 2.6b.
- Does **not** close **DEBT-B1-001** (remains **WP-B8**).
- Does **not** amend Accepted ADR or ARCH-001.
- Implementation gates **unchanged**.

---

## Question records

---

### Q-A1 — INV-B4-001…003 acceptance

#### 5. Board decision

**Accepted**

#### 6. Rationale

The organization accepts **INV-B4-001**, **INV-B4-002**, and **INV-B4-003** as binding governance input for WP-B4 contour class decisions and downstream **WP-B7**, per [Main doc §8](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md#8-architecture-invariants).

#### 7. Downstream consequence

**WP-B7** — contour disposition may reference INV-B4 as binding input.

---

### Q-A2 — Cabinet-stable Template binding

#### 5. Board decision

**Accepted**

#### 6. Rationale

Cabinet-stable Template binding affirmed for contours `(1, 73, 86)` and `(1, 78, 77)`. Permission Template contour binding attaches to Position Cabinet / Position identity; owner change, acting overlay, or vacancy does not trigger Template rebinding.

#### 7. Downstream consequence

**WP-B7**, **OPS-030** — governance policy recorded; OPS-030 remains blocked until WP-B7 + AC3.

---

### Q-A3 — Acting Person not recorded as Cabinet Owner

#### 5. Board decision

**Accepted**

#### 6. Rationale

Minimum governance statement recorded:

> **Acting Assignee SHALL NOT be recorded as Cabinet Owner in policy artefacts, contour binding records, or Template disposition.** Acting Assignment grants time-bounded access only ([GLOSS-B4-001 §4](../GLOSS-B4-001-position-cabinet-vocabulary.md)).

#### 7. Downstream consequence

**WP-B7**, **WP-B8** — policy records must distinguish acting access from permanent occupancy.

---

### Q-B1 — Position-owned vs Employee-owned split

#### 5. Board decision

**Accepted**

#### 6. Rationale

The organization accepts the position-owned vs employee-owned data split as organizational direction: Position-owned Data remains in Position Cabinet across owner change and acting; Employee-owned Data follows Person / Employee; acting must not inherit permanent Owner's employee-owned profile.

#### 7. Downstream consequence

Future subsystems — governance direction recorded; implementation deferred.

---

### Q-B2 — UI carcase as directional input only

#### 5. Board decision

**Accepted**

#### 6. Rationale

UI carcase (`/tasks`, `/dashboards`, `/education`) acknowledged as **informative directional input** only — not implementation deliverable, not runtime behaviour, not authorization to extend UI.

#### 7. Downstream consequence

Engineering work packages — separate from WP-B4 ratification.

---

### Q-C1 — Orthogonality with WP-B3

#### 5. Board decision

**Accepted**

#### 6. Rationale

Orthogonality with WP-B3 PD-5.1 authorship accepted. PD-5.1 authorship may follow acting access to Director Cabinet; acting does not transfer permanent Employment or Cabinet Owner status. WP-B3 outcomes consumed as fixed input — not reopened.

#### 7. Downstream consequence

**WP-B7** Director row — class prerequisite satisfied; code remains **WP-B8**.

---

### Q-C2 — OQ-B4-001 deferred backlog

#### 5. Board decision

**Accepted**

#### 6. Rationale

**OQ-B4-001** recorded as **open, deferred, non-blocking** for WP-B4. Resolution deferred to runtime access design phase (notifications, document approval, audit journals).

#### 7. Downstream consequence

Implementation-phase ADR or assessment — when runtime program starts.

---

### Q-C3 — DEBT-B1-001 confirmation

#### 5. Board decision

**Accepted**

#### 6. Rationale

**DEBT-B1-001** confirmed **Open**; resolution WP **WP-B8**. Session 1 does **not** ratify transitional `access_roles.code` for PD-5.1. HR-service WP-B4 scope does not close this debt.

#### 7. Downstream consequence

**WP-B8** — owns PD-5.1 code mapping; Phase 2.6b MVP (HR head path) valid without **DEBT-B1-001** closure.

---

### Q-D1 — Persistent Workspace characterisation

#### 5. Board decision

**Accepted**

#### 6. Rationale

**Persistent Workspace of Position** accepted as governance characterisation of Position Cabinet — synonymous at domain level; not a separate entity; disambiguates from Employee personal workspace and legacy «личный кабинет» UI shell. No Accepted ADR amendment.

#### 7. Downstream consequence

Downstream WPs — shared vocabulary via [GLOSS-B4-001](../GLOSS-B4-001-position-cabinet-vocabulary.md).

---

### Q-D2 — Normative model ratification

#### 5. Board decision

**Accepted**

#### 6. Rationale

The organization **ratifies** [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) as the binding governance model for Position Cabinet contour binding — including binding rules **BR-A1…A6**, ownership preservation rules, scope, invariants, non-goals, and downstream implications.

#### 7. Downstream consequence

**WP-B7**, **WP-X1**, **WP-B8** — consume ratified model. Main document status → **Accepted (Ratified)**.

---

### Q-E1 — HR head contour class `(1, 73, 86)`

#### 5. Board decision

**Accepted**

#### 6. Rationale

Contour `(1, 73, 86)` — organizational permission class **PD-5.2** (кадровое оформление) ratified on Position Cabinet baseline. Transitional `access_roles.code` **`HR_ENROLLMENT_MANAGER`** ratified for **this contour only** at governance policy level — consistent with WP-B1 candidate and WP-B2 P6. §7 row remains **pending** — disposition is **WP-B7**, not WP-B4.

#### 7. Downstream consequence

**WP-B7** — HR head row disposition; **Phase 2.6b MVP** candidate path after WP-B7 `approved` + WP-X2 + WP-X3.

---

### Q-E2 — Deputy admin contour class `(1, 78, 77)`

#### 5. Board decision

**Accepted**

#### 6. Rationale

Contour `(1, 78, 77)` — organizational permission class **PD-5.3** (кадровый контроль / наблюдение) ratified on Position Cabinet baseline. No dedicated transitional `access_roles.code` ratified — see Q-F1 (**DEBT-B1-004** continues). §7 row remains **pending**.

#### 7. Downstream consequence

**WP-B7** — deputy admin row disposition; **WP-B8** — transitional code for PD-5.3.

---

### Q-F1 — DEBT-B1-004 disposition

#### 5. Board decision

**Accepted**

#### 6. Rationale

| Debt | Disposition | Detail |
|------|-------------|--------|
| **DEBT-B1-004** | **Continues** | Class assignment for `(1, 78, 77)` **closed** (PD-5.3 ratified Q-E2); transitional `access_roles.code` **not ratified** — deferred to **WP-B8** |

Split disposition mirrors WP-B3: class governance closed; code mapping debt continues at narrower scope.

#### 7. Downstream consequence

**WP-B8** — owns remaining code/catalog work for PD-5.3 contour; **PERMISSION-DOMAIN-REGISTRY** — update pending.

---

### Q-G1 — Session boundary without implementation

#### 5. Board decision

**Accepted**

#### 6. Rationale

WP-B4 Session 1 outcome valid **without** §7 row approval, OPS-030 authorization, ACCESS-001 **Approved** promotion, or runtime effect. Implementation gates **unchanged**.

#### 7. Downstream consequence

**OPS-030** — Blocked; **AC3** — Pending; legacy enforcement authoritative.

---

### Q-G2 — Ratification record wording

#### 5. Board decision

**Accepted**

#### 6. Rationale

Ratification record **includes**:

> This WP-B4 ratification accepts the Position Cabinet contour binding governance model and HR operational class assignments as recorded in Session 1. It **does not** approve ACCESS-001 §7 rows, promote ACCESS-001 to **Approved**, authorize OPS-030 or Phase 2.6b, close ADR-053 AC3, close **DEBT-B1-001** (remains **WP-B8**), insert contour rules, or change runtime enforcement. **DEBT-B1-004** continues for PD-5.3 transitional code (WP-B8).

#### 7. Downstream consequence

**WP-B4 closure record** — wording template for attestation signatures.

---

## Final session summary

### Questions accepted

| # | Question |
|---|----------|
| Q-A1 | INV-B4-001…003 acceptance |
| Q-A2 | Cabinet-stable Template binding |
| Q-A3 | Acting not recorded as Cabinet Owner |
| Q-B1 | Position-owned vs Employee-owned split |
| Q-B2 | UI carcase directional input only |
| Q-C1 | WP-B3 orthogonality |
| Q-C2 | OQ-B4-001 deferred |
| Q-C3 | DEBT-B1-001 open → WP-B8 |
| Q-D1 | Persistent Workspace characterisation |
| Q-D2 | Normative model ratification |
| Q-E1 | HR head `(1, 73, 86)` — PD-5.2 |
| Q-E2 | Deputy admin `(1, 78, 77)` — PD-5.3 |
| Q-F1 | DEBT-B1-004 disposition |
| Q-G1 | Session boundary without implementation |
| Q-G2 | Ratification record wording |

**Total accepted:** 14 / 14 mandatory questions.

### Questions deferred

None.

### Questions rejected

None.

### Ratification subject disposition

| # | Subject | Disposition |
|---|---------|-------------|
| 1 | **INV-B4-001…003** | **Accepted** — binding governance input |
| 2 | **Cabinet-stable contour binding model** | **Ratified** |
| 3 | **Persistent Workspace characterisation** | **Ratified** |
| 4 | **Position-owned vs Employee-owned boundaries** | **Ratified** |
| 5 | **HR class `(1, 73, 86)`** | **Ratified** — PD-5.2 + `HR_ENROLLMENT_MANAGER` (governance policy) |
| 6 | **HR class `(1, 78, 77)`** | **Ratified** — PD-5.3; code open |
| 7 | **DEBT-B1-004** | **Continues → WP-B8** (code only) |
| 8 | **DEBT-B1-001** | **Open → WP-B8** — confirmed only |

### Policy debt register (post–Session 1)

| Debt ID | Status | Item | Resolution WP |
|---------|--------|------|---------------|
| **DEBT-B1-001** | **Open** | Transitional `access_roles.code` for PD-5.1 not ratified | **WP-B8** |
| **DEBT-B1-004** | **Open** | Transitional `access_roles.code` for PD-5.3 / `(1, 78, 77)` not ratified | **WP-B8** |

**No new policy debt ID recorded.** DEBT-B1-004 continues at narrower scope (code mapping only; PD-5.3 class ratified).

### Unresolved items

None requiring WP-B4 Session 2.

| Item | Status | Note |
|------|--------|------|
| **OQ-B4-001** | Deferred backlog | Non-blocking — not unresolved for WP-B4 closure purposes |

### Action items

| # | Action | Owner / WP | Priority |
|---|--------|------------|----------|
| AI-1 | Collect WP-B4 attestation signatures (HR policy owner + ops lead + executive sponsor) | Program admin | Before formal WP-B4 closure |
| AI-2 | Update PERMISSION-DOMAIN-REGISTRY — contour class assignments; DEBT-B1-004 → WP-B8 | Governance session | After attestation |
| AI-3 | WP-B7 §7 row disposition for `(73, 86)` and `(78, 77)` | **WP-B7** | After WP-B4 attestation |
| AI-4 | Resolve **DEBT-B1-004** and **DEBT-B1-001** transitional codes | **WP-B8** | Parallel |
| AI-5 | WP-X1 crosswalk before shared-contour row **approved** disposition | **WP-X1** | Before WP-B7 approvals on shared contours |

### Remaining governance work

| Item | Owner / WP | Status |
|------|------------|--------|
| WP-B4 attestation signatures | HR policy owner + ops lead + executive sponsor | **Pending** |
| WP-B4 formal closure | Program register | **Pending** signatures |
| **DEBT-B1-001** | **WP-B8** | **Open** |
| **DEBT-B1-004** | **WP-B8** | **Open** |
| **WP-B7** | §7 row disposition | **Ready** after WP-B4 attestation |
| **OQ-B4-001** | Runtime design | **Open** — non-blocking |
| **WP-B5** | Next Track B WP | **Ready** |

### Whether WP-B4 Session 2 is required

**No.**

All 14 mandatory questions **Accepted** in Session 1. Overall outcome **Ratified with Policy Debt** is complete for session purposes.

### WP-B4 readiness for formal closure

| Criterion | Status |
|-----------|--------|
| Session 1 decisions recorded | ☑ |
| Overall outcome determined | ☑ **Ratified with Policy Debt** |
| DEBT disposition coherent | ☑ |
| Implementation gates unchanged | ☑ verified |
| Attestation signatures | ☐ **Pending** |
| WP-B4 formally **Closed** | ☐ **Pending** signatures |

---

## Ratified governance summary (Session 1)

Governance assignments ratified — **not** §7 row approval or runtime binding:

| Element | Ratified stance |
|---------|-----------------|
| **Contour binding model** | Cabinet-stable; INV-B4-001…003; binding rules BR-A1…A6 — per [Main doc](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) |
| **Persistent Workspace** | Governance characterisation of Position Cabinet — [GLOSS-B4-001 §2](../GLOSS-B4-001-position-cabinet-vocabulary.md) |
| **HR head `(1, 73, 86)`** | **PD-5.2** — кадровое оформление; **`HR_ENROLLMENT_MANAGER`** transitional code (governance policy for this contour) |
| **Deputy admin `(1, 78, 77)`** | **PD-5.3** — кадровый контроль / наблюдение; transitional code **not ratified** |
| **DEBT-B1-004** | **Continues → WP-B8** (code only) |
| **DEBT-B1-001** | **Open → WP-B8** (unchanged) |
| **Runtime effect** | **None** |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-06 | 0.1 | Initial Session 1 record — prepared for Review Board; decisions pending |
| 2026-07-06 | 1.0 | Review Board Session 1 — **Ratified with Policy Debt**; 14/14 questions Accepted |
