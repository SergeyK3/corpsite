# Review Board Brief — WP-B4 Position Cabinet Contour Binding (Problem Space)

## Owner vs Acting Assignment — prerequisite governance input

> Problem space analysis: [WP-B4-PROBLEM-SPACE-REVIEW.md](../WP-B4-PROBLEM-SPACE-REVIEW.md) v0.5  
> Main governance document: [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) (prepared — ratification subject)  
> Terminology: [GLOSS-B4-001](../GLOSS-B4-001-position-cabinet-vocabulary.md)  
> Prior work: [WP-B3 Closure Report](../WP-B3-CLOSURE-REPORT.md); [WP-B2 Binding Principles Review](../WP-B2-BINDING-PRINCIPLES-REVIEW.md); [WP-B1 Closure Report](../WP-B1-CLOSURE-REPORT.md)  
> Program: [ACCESS-RATIFICATION-PROGRAM](../ACCESS-RATIFICATION-PROGRAM.md) WP-B4; [TIER-G report](../TIER-G-GOVERNANCE-PROGRESS-REPORT.md)

## Document metadata

| Field | Value |
|-------|-------|
| Session | WP-B4 Review Board — **Problem Space confirmation** (pre-governance document) |
| Date prepared | 2026-07-05 |
| Package | WP-B4 — HR operational class assignments + Position Cabinet contour binding prerequisites |
| Object | Acceptance of Problem Space, **INV-B4-001…003**, and owner/acting/data-ownership boundaries; ratification of [main WP-B4 governance document](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) (prepared) |
| Tier / phase | G — Governance / G1 — Policy Ratification |
| Status | **Briefing only** — no ratification recorded |
| Prior work | WP-B1–B3 substantively complete; attestation signatures pending on WP-B1/WP-B2 |
| Sources | WP-B4 problem space review v0.5; [GLOSS-B4-001](../GLOSS-B4-001-position-cabinet-vocabulary.md); [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md); ARCH-001; ADR-050/051/053; ADR-036; ACCESS-001 |
| Approval authority (full WP-B4) | HR policy owner + ops lead + executive sponsor (deputy admin) |
| Runtime effect | **None** |

---

## 1. Review purpose

### What this session evaluates

This brief prepares the Review Board to **confirm the WP-B4 Problem Space** — not yet to ratify HR contour class assignments or transitional codes.

| Phase | Review Board object | Outcome artefact |
|-------|---------------------|------------------|
| **This session (Problem Space)** | Are **INV-B4-001…003**, owner/acting boundaries, and data-ownership split **accepted** as governance input for WP-B4? | Recorded confirmation — input to [main governance document](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) ratification |
| **Subsequent session (governance)** | HR operational class per contour `(73, 86)` / `(78, 77)`; **DEBT-B1-004** disposition; normative model ratification | [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) — **prepared**, awaiting Review Board |

The Board is **not** selecting `access_roles.code`, approving §7 rows, or authorizing OPS-030 in this Problem Space session.

### How WP-B4 differs from WP-B3

| Work package | Primary object |
|--------------|----------------|
| **WP-B3** | Positive permission class for **PD-5.1** (Кадровое решение); executive authorship model |
| **WP-B4 (Problem Space)** | **When Cabinet Owner changes** vs **when acting access applies**; contour binding must stay **Cabinet-stable** |
| **WP-B4 (Governance — later)** | Class assignment for **PD-5.2** / **PD-5.3** on HR-service contours |

WP-B3 and WP-B4 Problem Space are **orthogonal layers** (see §6).

---

## 2. Scope of WP-B4

Per [ACCESS-RATIFICATION-PROGRAM](../ACCESS-RATIFICATION-PROGRAM.md) and [WP-B4-PROBLEM-SPACE-REVIEW.md](../WP-B4-PROBLEM-SPACE-REVIEW.md).

### In scope (program — full WP-B4)

| Dimension | Detail |
|-----------|--------|
| **HR operational class assignments** | Contour `(1, 73, 86)` — **PD-5.2** (кадровое оформление); contour `(1, 78, 77)` — **PD-5.3** (кадровый контроль / наблюдение) |
| **DEBT-B1-004** | Transitional code / class mapping for deputy admin contour — disposition in governance session |
| **Contour binding prerequisite** | **INV-B4-001…003** — Template binding on **Position Cabinet identity**, not transient occupant or acting Person |
| **Phase 2.6b MVP gate** | HR head `(73, 86)` `approved` in WP-B7 enables first OPS-030 insert — **downstream**; not unlocked by Problem Space confirmation alone |

### In scope (this Problem Space session only)

| Item | Detail |
|------|--------|
| **INV-B4-001…003** | Organizational acceptance as binding input |
| **Owner vs Acting Assignment** | Terminology and event taxonomy (§4–§5 of problem space review) |
| **Position-owned vs Employee-owned** | Data routing boundaries for future subsystems |
| **UI carcase** | Confirming **directional input** only (§5) |
| **OQ-B4-001** | Acknowledge as **deferred, non-blocking** backlog item |

### Out of scope (all WP-B4 sessions)

| Topic | Owner |
|-------|-------|
| PD-5.1 transitional `access_roles.code` | **WP-B8** — **DEBT-B1-001 remains open** (§8) |
| §7 `policy_status=approved` | **WP-B7** |
| OPS-030 / Phase 2.6b execution | **Tier B** / **WP-X3** (AC3) |
| Acting overlay implementation | **ADR-036 Phase 3** — engineering |
| API, schema, migrations, RBAC, UI implementation | Forbidden in governance phase |
| Accepted ADR amendment | **Architecture Freeze** |

---

## 3. Architectural invariants (INV-B4-001…003)

Recorded in [WP-B4-PROBLEM-SPACE-REVIEW.md §3](../WP-B4-PROBLEM-SPACE-REVIEW.md#3-architectural-invariant-recorded). **Board asked to accept or reject as governance input.**

| ID | Invariant |
|----|-----------|
| **INV-B4-001** | **Cabinet Owner** (permanent Position Occupant) changes **only** through HR events that alter permanent **Position Occupancy** (Employment on org-unique Position) |
| **INV-B4-002** | **Acting Assignment** grants operational/permission access for a bounded period; **does not** transfer Cabinet Owner status; must not be interpreted as owner change for contour binding or data ownership |
| **INV-B4-003** | **Position Cabinet** is the working shell of the **organizational position**, not the temporary executor; acting Person may receive delegated access but **does not become** Cabinet Owner |

**Sources (Accepted — not amended):** ARCH-001 §3.2, §4.2–§4.3, §4.6; ADR-050; ADR-051; ADR-036.

**Binding implication:** Permission Template contour rules attach to **Position Cabinet / Position** — owner change **must not** trigger Template rebinding (ACCESS-001 P1, P2; ADR-053 §3.4).

---

## 4. Owner vs Acting Assignment

### Terminology (must not be conflated)

| Concept | Definition |
|---------|------------|
| **Position Cabinet (entity)** | Long-lived container 1:1 with org-unique Position — owned by **organization**, never Person |
| **Cabinet Owner / Position Occupant** | Person with **permanent Employment** on that Position |
| **Acting Assignee / Temporary Executor** | Person with **Acting Assignment** overlay — access without ownership transfer |

### Events that **change** Cabinet Owner

Permanent occupancy change only: приём на должность; перевод; увольнение; повторный приём; ликвидация/закрытие Position; иные кадровые события, изменяющие **постоянное** Занятие должности.

### Events that **do not** change Cabinet Owner

Трудовой отпуск; больничный; командировка; временное исполнение обязанностей; временное замещение; краткосрочное отсутствие владельца **без** прекращения Employment.

**Vacancy:** unoccupied Position ≠ acting Person as owner — Cabinet **persists** (ARCH-001 §4.2).

### Acting Assignment rules (summary A1–A6)

| Rule | Statement |
|------|-----------|
| A1 | Acting may grant access to tasks, management actions, operational cabinet functions |
| A2 | Acting **does not** transfer Cabinet Owner status |
| A3 | Acting **must not** rebind **employee-owned** `/education` data to acting Person |
| A4 | Acting **must not** reset or migrate **position-owned** KPI, dashboards, tasks, reporting history |
| A5 | Primary Employment of acting Person **preserved** |
| A6 | Acting end → access closes; owner and position-owned state **unchanged** |

**Anti-patterns:** Template copy from acting Person; history migration to acting Employee; treating и.о. as owner substitution for contour binding.

---

## 5. Position-owned vs Employee-owned sections

Target data-ownership split (governance direction; implementation deferred):

| Domain | Ownership | On owner change | On acting |
|--------|-----------|-----------------|-----------|
| `/tasks`, task backlog, reporting history | **Position-owned** | Stays in Cabinet | Acting acts **in context**; no transfer |
| `/dashboards`, KPI aggregates | **Position-owned** | Persists in Cabinet | View/use allowed; **no reset** |
| `/education`, courses, testing, psych. tests | **Employee-owned** | Follows **Owner’s** Employee/Person | **Not** rebound to acting Person |
| Individual personnel HR history | **Employee-owned** | Person / Employment journal | Acting events on **acting Employee** separately (ADR-036) |

### UI carcase — confirming input only

Position Cabinet UI shell exposes section split at **carcase level only**:

| Route | Declared ownership (`positionCabinetNav.ts`) |
|-------|-----------------------------------------------|
| `/tasks` | `existing` / position-related |
| `/dashboards` | `position_cabinet` |
| `/education` | `employee` |

| Statement | Detail |
|-----------|--------|
| **Role for WP-B4** | UI carcase **confirms architectural direction** already aligned with INV-B4-001…003 and ARCH-001 §4.4–§4.6 |
| **Not implementation scope** | No API, schema, RBAC, or backend binding implied; **no** governance authorization to extend UI beyond existing stubs |
| **Board action** | Acknowledge as **informative input** — not as delivered feature or runtime behaviour |

---

## 6. Orthogonality with WP-B3

[WP-B3 Session 1](../review-board/WP-B3-SESSION-1-REVIEW-BOARD-RECORD.md) ratified **PD-5.1 authorship** follows **Director Position Cabinet occupancy context** (including valid acting access) — **Cabinet context, not job title**.

| Layer | WP-B3 | WP-B4 Problem Space |
|-------|-------|---------------------|
| **Question** | Who may **exercise** PD-5.1 (author кадровое решение)? | When does **permanent occupant** change vs temporary acting access? |
| **Acting effect** | Authorship may follow acting access to **Director Cabinet** | Acting **does not** transfer permanent Employment / Cabinet Owner |
| **Employee-owned data** | Out of PD-5.1 scope | Acting **must not** rebind `/education` |
| **Position-owned history** | Out of PD-5.1 scope | Tasks/KPI/dashboards **persist**; no migration on acting |

**No contradiction:** WP-B3 governs **permission exercise in Cabinet context**; WP-B4 Problem Space governs **owner-change criteria** and **contour binding stability**.

---

## 7. Open backlog — OQ-B4-001 (deferred, non-blocking)

| Field | Value |
|-------|-------|
| **ID** | **OQ-B4-001** |
| **Question** | Relationship between **Cabinet Owner**, **Acting Assignment**, and **Active Cabinet Session** |
| **Status** | **Open** — deferred |
| **Blocks this session?** | **No** |
| **Blocks WP-B4 governance prep?** | **No** |
| **Likely needed for** | Runtime access enforcement; notifications; electronic document approval; action/audit journals |

**Board acknowledgment requested:** Record OQ-B4-001 as **accepted backlog item** — not resolved in Problem Space session; does not defer INV-B4 acceptance or HR-class governance track.

Full detail: [WP-B4-PROBLEM-SPACE-REVIEW.md §12](../WP-B4-PROBLEM-SPACE-REVIEW.md#12-open-architectural-questions-backlog).

---

## 8. Policy debt — DEBT-B1-001

| Debt ID | Status | Resolution WP | WP-B4 impact |
|---------|--------|---------------|--------------|
| **DEBT-B1-001** | **Open** | **WP-B8** | Transitional `access_roles.code` for **PD-5.1** (Кадровое решение) **not ratified** |

**Explicit confirmation for Board:**

- Problem Space acceptance and HR-service class work (**PD-5.2** / **PD-5.3**) **do not** close DEBT-B1-001.
- Director contour `(1, 78, 62)` code mapping remains **WP-B8** / **WP-B7** — not WP-B4 Problem Space.
- Phase 2.6b MVP path (HR head `(73, 86)` only) remains valid per program without DEBT-B1-001 closure.

Separate open item: **DEBT-B1-004** (PD-5.3 / `(78, 77)`) — disposition in **subsequent** WP-B4 governance session, not Problem Space session.

---

## 9. Architecture boundaries (fixed)

| Fixed position | Source |
|----------------|--------|
| Architecture Design **complete**; Architecture Freeze **in effect** | Master Plan §1.1 |
| Permission on **Position Cabinet**, not User/Person (P1) | ACCESS-001 §4; ADR-050 |
| No binding from occupant inference or grant-copy (P2) | ADR-053 §3.4 |
| `access_grants` overlay during Phase 2.6 (P3) | ADR-053 §3.5 |
| OPS-030 **Blocked**; AC3 **Pending** | ADR-053; OPS-030 |
| Legacy enforcement **authoritative** | Master Plan §1.3 |

**Board must not:** amend Accepted ADRs; authorize OPS-030; approve §7 rows; implement API/schema/RBAC/UI.

---

## 10. Review questions (Problem Space session)

**Not answered in this brief.**

### Topic A — Invariant acceptance

| # | Question |
|---|----------|
| **Q-A1** | Does the organization **accept INV-B4-001…003** as binding governance input for WP-B4 contour class decisions and downstream WP-B7? |
| **Q-A2** | Is **Cabinet-stable Template binding** (independent of acting Person) affirmed for contours `(73, 86)` and `(78, 77)`? |
| **Q-A3** | What **minimum governance statement** prevents acting Person from being recorded as Cabinet Owner in policy artefacts? |

### Topic B — Data ownership boundaries

| # | Question |
|---|----------|
| **Q-B1** | Is the **position-owned vs employee-owned** split (§5) accepted as organizational direction for future subsystems? |
| **Q-B2** | Is the **UI carcase** acknowledged as directional input only — **not** implementation deliverable or runtime behaviour? |

### Topic C — Cross-package boundaries

| # | Question |
|---|----------|
| **Q-C1** | Is **orthogonality with WP-B3 PD-5.1 authorship** (§6) accepted — no reopening of WP-B3 class definition? |
| **Q-C2** | Is **OQ-B4-001** recorded as deferred non-blocking backlog without delaying WP-B4 governance document preparation? |
| **Q-C3** | Is **DEBT-B1-001** confirmed **open → WP-B8** with no accidental closure implied by this session? |

### Out of scope for Problem Space session

| Topic | Session |
|-------|---------|
| M4–M6 HR class assignment (`PD-5.2` / `PD-5.3` / DEBT-B1-004) | **Subsequent** WP-B4 governance session |
| §7 row approval | WP-B7 |
| OPS-030 / AC3 | Tier B / WP-X3 |

---

## 11. Decision space (Problem Space session)

| Option | Meaning |
|--------|---------|
| **Accepted** | Problem Space, INV-B4-001…003, owner/acting boundaries, and data-ownership split **confirmed** — main WP-B4 governance document may proceed |
| **Accepted with recorded gaps** | Core invariants accepted; named item(s) explicitly deferred with owner (must **not** include OQ-B4-001 blocking without rationale) |
| **Deferred** | Problem Space not confirmed — revise problem space review before governance document |

### Session must not (all options)

| Prohibition | Reason |
|-------------|--------|
| Ratify HR contour class or `access_roles.code` | Governance session scope |
| Close **DEBT-B1-001** | WP-B8 only |
| Approve §7 rows or OPS-030 | WP-B7 / Tier B |
| Amend Accepted ADRs | Architecture Freeze |
| Treat UI carcase as implemented feature | Carcase is input only |
| Resolve **OQ-B4-001** | Deferred — runtime design phase |

---

## 12. Downstream impact

### If Problem Space **Accepted**

| Dimension | Impact |
|-----------|--------|
| **Main WP-B4 governance document** | May proceed to Review Board ratification — [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) **prepared** |
| **WP-B7** | Contour disposition may reference INV-B4-001…003 |
| **WP-B8** | DEBT-B1-001 unchanged |
| **OQ-B4-001** | Remains open backlog |
| **Implementation gates** | **Unchanged** — OPS-030 Blocked; AC3 Pending; no runtime effect |

### If Problem Space **Deferred**

| Dimension | Impact |
|-----------|--------|
| **WP-B4 governance document** | **Blocked** until problem space revised |
| **WP-B7 HR MVP path** | Preparation may continue in parallel per program — governance record incomplete |

**Gates unchanged for all outcomes:** ACCESS-001 **Reviewed**; legacy enforcement authoritative; no API/schema/RBAC/UI from this session.

---

## 13. Risks

| ID | Risk | Mitigation |
|----|------|------------|
| **R1** | Conflating WP-B3 authorship with owner transfer | §6 orthogonality table |
| **R2** | Acting Person treated as Cabinet Owner for contour binding | INV-B4-002; Q-A3 |
| **R3** | UI carcase read as delivered implementation | §5 explicit non-scope; Q-B2 |
| **R4** | Accidental DEBT-B1-001 closure | §8; Q-C3 |
| **R5** | OQ-B4-001 blocks governance prep | §7 — non-blocking |
| **R6** | Implementation leakage (OPS-030, §7) | §2 out of scope |
| **R7** | Architecture redesign in session | §9 boundaries |

---

## 14. Readiness assessment

| Criterion | Assessment |
|-----------|------------|
| Problem space documented (v0.5) | **Yes** |
| INV-B4-001…003 stated | **Yes** — §3 |
| Owner vs Acting taxonomy | **Yes** — §4 |
| Position vs Employee ownership | **Yes** — §5 |
| UI carcase role clarified | **Yes** — §5 |
| WP-B3 orthogonality | **Yes** — §6 |
| OQ-B4-001 recorded non-blocking | **Yes** — §7 |
| DEBT-B1-001 → WP-B8 confirmed | **Yes** — §8 |
| Review questions prepared | **Yes** — §10 |
| Architectural contradictions | **None identified** |
| Main governance document prepared | **Yes** — [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) |

**Finding:** Board has **sufficient information** to confirm Problem Space and ratify the prepared main governance document.

**Explicit non-finding:** This brief does **not** ratify HR operational classes, transitional codes, or §7 rows — those are Review Board ratification subjects in the main document §3.3 and Review Board ratification subjects table.

**Approval status:** Briefing complete — **awaiting Review Board ratification session**.

**Primary ratification artefact:** [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](../WP-B4-POSITION-CABINET-CONTOUR-BINDING.md). Conceptual framing: [WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md](../WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md). Terminology: [GLOSS-B4-001](../GLOSS-B4-001-position-cabinet-vocabulary.md).

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-05 | 0.1 | Initial WP-B4 Problem Space brief — INV-B4-001…003; owner/acting; data ownership; WP-B3 orthogonality; OQ-B4-001; DEBT-B1-001 confirmation |
| 2026-07-06 | 0.2 | Traceability — main governance document prepared; GLOSS-B4-001; problem space v0.5 |
