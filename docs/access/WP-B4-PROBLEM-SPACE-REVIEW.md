# WP-B4 — Problem Space Review (Position Cabinet Contour Binding: Owner vs Acting Assignment)

## Status

**Complete (analysis)** — 2026-07-05

Governance analysis and **architectural invariant record** for WP-B4 under [ACCESS-RATIFICATION-PROGRAM](./ACCESS-RATIFICATION-PROGRAM.md) (Tier G, Phase G1). Defines the **Problem Space** for Position Cabinet **owner-change criteria** and their relationship to **contour binding** decisions. Precedes WP-B4 Review Board session on HR operational class assignments. **No runtime effect.** **No solutions proposed** for implementation.

| Field | Value |
|-------|-------|
| Work package | WP-B4 — HR operational class assignments + Position Cabinet contour binding prerequisites |
| Prior artefacts | [WP-B3 Closure Report](./WP-B3-CLOSURE-REPORT.md); [WP-B2 Binding Principles Review](./WP-B2-BINDING-PRINCIPLES-REVIEW.md); [WP-B1 Closure Report](./WP-B1-CLOSURE-REPORT.md) |
| Question answered | *When does Position Cabinet “ownership” (permanent occupant) change, and when does acting access apply without owner change?* |
| Question not answered | *Specific `access_roles.code` mapping, §7 row disposition, OPS-030 execution* |

---

## 1. Purpose

### 1.1 Governance objective

WP-B4 must assign **organizational permission classes** to HR-service contours `(1, 73, 86)` and `(1, 78, 77)` and resolve **DEBT-B1-004** mapping questions. Contour binding attaches Permission Template baseline to **Position Cabinet identity** (ADR-050, ADR-053), not to a transient Person.

Before class and code decisions, WP-B4 Review Board must share a **single invariant** for **owner-change criteria**:

> **Cabinet Owner (permanent Position Occupant) changes only through HR events that alter permanent Position Occupancy. Temporary duty execution does not change Cabinet Owner.**

This note **records** that invariant for Problem Space Review. It does **not** implement acting overlays, Employment retargeting, or resolver enforcement.

### 1.2 Relationship to program scope

| WP-B4 dimension | This document |
|-----------------|---------------|
| **HR operational class assignments** | Contour `(73, 86)` PD-5.2; contour `(78, 77)` PD-5.3 — class/code mapping remains WP-B4 Review Board scope |
| **Owner vs Acting invariant** | **Prerequisite governance fact** — contour binding must not treat acting access as owner transfer |
| **DEBT-B1-001** | **Open** — transitional code for PD-5.1 remains deferred to **WP-B8**; **not closed** by this note |
| **UI shell** | Position Cabinet sections `/tasks`, `/dashboards`, `/education` already express **position-owned vs employee-owned** split at UI-carcase level only — no backend binding |

---

## 2. Terminology

### 2.1 Position Cabinet entity vs occupant vs acting executor

Three concepts must not be conflated during WP-B4 contour binding discussions.

| Concept | Definition | Changes when… |
|---------|------------|---------------|
| **Position Cabinet (entity)** | Long-lived operational container bound 1:1 to org-unique **Position** (ADR-050). Owned by **organization / Position**, never by Person | Position is abolished or reorganized at HR staffing level |
| **Cabinet Owner / Position Occupant** | **Person** holding **permanent Position Occupancy** via active **Employment** (Занятие должности) on that Position | HR events alter **permanent** occupancy (see §4) |
| **Acting Assignee / Temporary Executor** | **Person** granted **Acting Assignment** overlay (ADR-036 `ACTING_ASSIGNMENT`) — temporary access to another Position’s Cabinet **without** closing primary Employment | Acting period starts / ends; **does not** change Cabinet Owner |

**Clarification — “ownership” in this note:**

- **Entity ownership** (Position Cabinet → Position) is **always** organizational — ARCH-001 §4.1, §4.3.
- **Cabinet Owner** in WP-B4 problem space means **permanent Position Occupant** — the Person whose Employment defines who **holds the position**, not who temporarily **acts in** it.
- **Acting Assignee** receives **delegated / acting access** to perform cabinet functions; **does not** become Cabinet Owner.

### 2.2 Orthogonality to WP-B3 PD-5.1 authorship

[WP-B3 Session 1](./review-board/WP-B3-SESSION-1-REVIEW-BOARD-RECORD.md) ratified: during valid delegation, **PD-5.1 authorship** follows **Director Position Cabinet occupancy context** (including acting access to that Cabinet) — **Cabinet context, not job title string**.

This **does not contradict** the invariant in this note:

| Layer | What moves with acting | What does **not** move |
|-------|------------------------|-------------------------|
| **PD-5.1 authorship (permission exercise)** | Acting Director may author кадровые решения **in context of Director Cabinet** while acting overlay is active | — |
| **Permanent Position Occupancy (Cabinet Owner)** | — | Acting does **not** transfer permanent Employment on Director Position |
| **Employee-owned data** | — | Acting does **not** rebind `/education` or personal HR history to acting Person as “new owner” |
| **Position-owned history** | — | Acting does **not** reset or migrate tasks, KPI, dashboards, reporting history |

WP-B3 governs **who may exercise PD-5.1** in a Cabinet context. This note governs **when permanent occupant identity changes** for Position-bound vs Employee-bound data.

---

## 3. Architectural invariant (recorded)

### INV-B4-001 — Owner change requires permanent occupancy change

> **Cabinet Owner (permanent Position Occupant) changes only through HR events that alter permanent Position Occupancy (Employment on org-unique Position).**

### INV-B4-002 — Acting does not transfer ownership

> **Acting Assignment grants operational and permission access to a Position Cabinet for a bounded period. Acting Assignment does not transfer Cabinet Owner status and must not be interpreted as owner change for contour binding or data ownership.**

### INV-B4-003 — Position Cabinet is the duty shell, not the temporary executor

> **Position Cabinet is the working shell of the **organizational position**, not of the temporary executor. A temporary executor may receive delegated/acting access but does not become Cabinet Owner.**

**Sources (Accepted — not amended):** ARCH-001 §3.2, §4.2–§4.3, §4.6; ADR-050; ADR-051 (Employment + ACTING overlay → accessible cabinets); ADR-036 (`ACTING_ASSIGNMENT` roadmap).

---

## 4. Events that change Cabinet Owner

Cabinet Owner changes when **permanent Position Occupancy** changes — i.e. when the Person recorded as holder of **Employment** on the Position changes through **cadre events** (кадровые события), not through absence or temporary substitution.

| Event class | Examples | Effect on Cabinet Owner |
|-------------|----------|-------------------------|
| **Initial hire on position** | Приём на должность; первичное Занятие должности | New Person becomes Cabinet Owner |
| **Transfer to another position** | Перевод на другую должность; закрытие prior Employment + opening new Employment on different Position | Prior Person ceases to be Owner of source Cabinet; new Person becomes Owner of target Cabinet |
| **Dismissal / termination** | Увольнение; закрытие Employment | Person ceases to be Cabinet Owner; **Position Cabinet persists** (ARCH-001 §4.2) |
| **Re-hire** | Повторный приём на ту же или иную должность | New Employment episode; Owner restored or newly assigned |
| **Position abolition / closure** | Ликвидация или закрытие штатной единицы / Position | Position Cabinet lifecycle ends **with** Position; occupant concept ends |
| **Other permanent occupancy changes** | Любые иные кадровые события, **изменяющие постоянное** Занятие должности (Employment) на Position — e.g. formal replacement of permanent holder, consolidation of positions where Employment records change | Cabinet Owner updates to Person on new active permanent Employment |

**Binding implication for WP-B4:** Permission Template contour rules attach to **Position Cabinet / Position identity**. Owner change **must not** trigger Template rebinding — Template stays on Cabinet; only **access** opens/closes for Persons via Employment lifecycle (ACCESS-001 P1, P2; ADR-053 §3.4).

---

## 5. Events that do not change Cabinet Owner

The following **do not** alter permanent Position Occupancy and **must not** be treated as Cabinet Owner change in governance, contour binding, or future data routing.

| Event class | Examples | Effect |
|-------------|----------|--------|
| **Paid leave** | Трудовой отпуск | Owner unchanged; may trigger acting overlay separately |
| **Sick leave** | Больничный | Owner unchanged |
| **Business trip** | Командировка | Owner unchanged |
| **Temporary duty execution** | Временное исполнение обязанностей (и.о.) | **Acting Assignee** gains access; **Owner unchanged** |
| **Temporary substitution** | Временное замещение | Same as acting — access overlay only |
| **Short-term absence of permanent holder** | Краткосрочное отсутствие постоянного владельца без прекращения Employment | Owner unchanged; vacancy-of-person ≠ vacancy-of-position |

**Vacancy note (ARCH-001 §4.2):** Position may be **unoccupied** (no current Owner) while Position Cabinet **persists** with full operational history. Unoccupied Cabinet is not an “owner change to acting Person” — acting is **access**, not **ownership**.

---

## 6. Acting Assignment — governance rules

When permanent holder is absent or position is temporarily served by another Person, the organization uses **Acting Assignment** (ADR-036 `ACTING_ASSIGNMENT`; ADR-051 acting overlay).

| Rule | Statement |
|------|-----------|
| **A1 — Access without ownership** | Acting Assignment may grant access to **tasks**, **management actions**, and **operational cabinet functions** for the target Position Cabinet |
| **A2 — No ownership transfer** | Acting Assignment **does not** transfer Cabinet Owner status |
| **A3 — Employee-owned data unchanged** | Acting Assignment **must not** change **employee-owned** data in `/education` — education, courses, testing, psychological assessments, individual personnel history remain bound to **Employee / Person**, not acting context |
| **A4 — Position-owned history preserved** | Acting Assignment **must not** reset, zero, or migrate **position-owned** KPI history, dashboards, tasks backlog, or reporting history |
| **A5 — Primary Employment preserved** | Acting overlay does **not** close acting Person’s primary Employment (ADR-051; ADR-036) |
| **A6 — Auto-expiry** | When acting period ends, acting access closes; Cabinet Owner and position-owned state **unchanged** |

**Anti-patterns (explicitly forbidden by architecture baseline):**

- Treating acting Person as new Cabinet Owner for contour rebinding or Template copy (violates P2, ADR-053 §3.4).
- Migrating position-owned task/report history to acting Person’s Employee record.
- Rebinding `/education` content to acting Person as if they “inherited” the permanent holder’s personal education profile.

---

## 7. Data ownership split (UI shell and target model)

The Position Cabinet UI carcase already separates sections by **future ownership class** (implementation not in scope for this note):

| UI section / domain | Ownership class | Behaviour on owner change | Behaviour on acting |
|---------------------|-----------------|---------------------------|---------------------|
| `/tasks` | **Position-owned** (existing subsystem; cabinet-scoped target) | Backlog and history **stay in Cabinet** | Acting Person **sees/acts in** Cabinet context; history **not transferred** |
| `/dashboards` | **Position-owned** (cabinet-owned future) | Dashboards, KPI panels **persist in Cabinet** | Acting may **view/use**; **no reset/migration** |
| Reporting history, KPI aggregates | **Position-owned** | **Persist** across occupant change | Accessible under acting; **not zeroed** |
| `/education` | **Employee-owned** | Content **follows Employee / Person** tied to **current Cabinet Owner** (operational shell), not acting Person | Acting Assignee **must not** replace education profile; shows **Owner’s** employee data or policy-defined read-only view — **not** acting Person’s personal record |
| Courses, testing, psych. tests | **Employee-owned** | Bound to Person / Employee | **Not** rebound to acting Person |
| Individual personnel HR history | **Employee-owned** | Person / Employment journal | Acting events recorded on **acting Employee** separately (ADR-036) |

**UI reference (carcase only):** `corpsite-ui/lib/positionCabinetNav.ts` — see [GLOSS-B4-001 §5–§6](./GLOSS-B4-001-position-cabinet-vocabulary.md). **No API, schema, or RBAC change** from this governance note.

**ARCH-001 alignment:** §4.4 (Cabinet composition — tasks, KPI, dashboards); §4.5 exceptions (личное дело → Person); §4.6 (occupant change preserves Cabinet).

---

## 8. Architectural conclusion

| # | Conclusion |
|---|------------|
| 1 | **Position Cabinet** is the **working shell of the position**, not of the temporary executor |
| 2 | **Cabinet Owner** = Person on **permanent Employment** for the Position; changes **only** via §4 events |
| 3 | **Acting Assignee** receives **delegated/acting access** — not ownership |
| 4 | **Contour binding** (WP-B4, WP-B7, OPS-030) attaches to **Cabinet / Position**, never to acting Person as pseudo-owner |
| 5 | **Position-owned** operational data survives occupant change and acting periods **inside the Cabinet** |
| 6 | **Employee-owned** personal data follows **Employee / Person**; acting must not corrupt that boundary |
| 7 | **DEBT-B1-001** remains **open** (WP-B8) — this note does not close transitional code debt |

---

## 9. Problem statement for WP-B4 Review Board

### 9.1 What governance capability is required?

WP-B4 must decide **HR operational permission class assignment** per contour while **respecting INV-B4-001…003**. The missing governance guardrail before binding sessions:

> Explicit organizational acceptance that **contour Template binding** and **acting access** are independent dimensions — binding is **Cabinet-stable**; acting is **Person-temporary**.

Without this invariant, WP-B4/WP-B7 risk:

- Inferring Template baseline from **current acting Person** (P2 violation).
- Treating и.о. appointment as **owner substitution** for PD-5.2/PD-5.3 class holders.
- Conflating **Director acting authorship** (WP-B3 PD-5.1) with **HR-service contour owner change**.

### 9.2 Questions WP-B4 must answer (contour binding + HR class)

**Mandatory — owner/acting boundary**

| ID | Question |
|----|----------|
| **M1** | Does the organization **accept INV-B4-001…003** as binding input for all WP-B4 contour class decisions? |
| **M2** | For contours `(73, 86)` and `(78, 77)`, is class assignment understood as **Cabinet baseline property** independent of who temporarily acts in adjacent executive contours? |
| **M3** | For acting periods, what **minimum governance statement** prevents acting Person from being recorded as Cabinet Owner in policy artefacts? |

**Mandatory — HR operational class (program scope)**

| ID | Question |
|----|----------|
| **M4** | What permission class applies to HR head `(1, 73, 86)` for **PD-5.2** (кадровое оформление)? |
| **M5** | What permission class applies to deputy admin `(1, 78, 77)` for **PD-5.3** (кадровый контроль / наблюдение)? |
| **M6** | What is the disposition of **DEBT-B1-004** — transitional code for `(78, 77)` mapping? |

### 9.3 Out of scope

| Topic | Owner |
|-------|-------|
| PD-5.1 transitional `access_roles.code` | **WP-B8** (**DEBT-B1-001** — remains open) |
| §7 `policy_status=approved` rows | **WP-B7** |
| OPS-030 / Phase 2.6b execution | **Tier B** |
| Acting overlay implementation (`employee_acting_assignments`) | **ADR-036 Phase 3** — engineering |
| Employment FK retargeting to org-unique Position | **ARCH-001 Phase 3** |
| UI implementation beyond existing carcase | Engineering — separate work packages |
| Accepted ADR amendment | **Forbidden** — Architecture Freeze |

---

## 10. Existing governance baseline (inputs)

| Input | Status | Relevance |
|-------|--------|-----------|
| WP-B1 | Substantive complete | PD-5.2, PD-5.3 ratified; DEBT-B1-004 → WP-B4 |
| WP-B2 | Substantive complete | P1–P2 Cabinet binding; P6/P8 HR class scope |
| WP-B3 | Substantive complete | PD-5.1 class; acting authorship vs title; **DEBT-B1-001 → WP-B8** |
| ARCH-001 | **Accepted** | Employment, Cabinet durability, §4.6 occupant change |
| ADR-050, ADR-051, ADR-053 | **Accepted** | Cabinet 1:1; resolver; Template binding — not occupant-derived |
| ADR-036 | **Accepted** | `ACTING_ASSIGNMENT` — overlay semantics |
| UI carcase | Deployed (shell only) | `/tasks`, `/dashboards`, `/education` ownership hints — see [GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md) |

---

## 11. Constraints (unchanged)

| Constraint | Detail |
|------------|--------|
| **Governance only** | No API, migrations, schema, RBAC, or UI changes from this artefact |
| **Architecture Freeze** | No Accepted ADR amendment |
| **DEBT-B1-001** | **Remains open** until WP-B8 |
| **Runtime** | Legacy enforcement authoritative; OPS-030 **Blocked** |
| **Implementation** | Invariant recorded for Review Board — not enforced in code by this note |

---

## 12. Open architectural questions (backlog)

Recorded open questions for WP-B4 and downstream implementation. **Non-blocking** for current governance work (contour class assignment, Review Board preparation, INV-B4-001…003 acceptance).

| ID | Question | Status | Blocks current WP-B4? | Likely resolution phase |
|----|----------|--------|------------------------|-------------------------|
| **OQ-B4-001** | **Relationship between Cabinet Owner, Acting Assignment and Active Cabinet Session** | **Open** | **No** | Runtime access design; notifications; electronic document approval; action / audit journals |

### OQ-B4-001 — detail

**Question:** How do **Cabinet Owner** (permanent Position Occupant), **Acting Assignment** (temporary overlay access), and **Active Cabinet Session** (Person's selected working context among accessible cabinets) relate at runtime?

**Context (established, not open):**

- INV-B4-001…003 fix **owner-change criteria** and **acting vs ownership** at governance level.
- ARCH-001 §10 and task-subsystem assessment describe **active cabinet context** and **union of accessible cabinets** when Person holds primary Employment plus acting overlay — but do **not** define session semantics for audit, notifications, or approval routing.

**Why recorded now:** Contour binding and permission class assignment do **not** require session model resolution. Almost certainly required before:

- Cabinet Access Resolver **enforcement** cutover (ADR-051 Phase 3+);
- notification routing (Telegram / in-app — which Cabinet context labels an event);
- electronic document approval (authorship vs acting context vs selected session);
- action and audit journals (`person_id`, `cabinet_id`, `session_context` — which tuple is authoritative for display and replay).

**Explicit non-scope:** This question does **not** reopen owner-change criteria (§4–§5), PD-5.1 authorship (WP-B3), or contour Template binding (WP-B4 Review Board scope). It extends INV-B4-002 into **runtime session design**.

**Disposition:** Deferred — no target work package assigned. May migrate to implementation-phase ADR or assessment when runtime access program starts.

---

## 13. Readiness assessment

| Criterion | Assessment |
|-----------|------------|
| Owner vs Acting distinction defined | **Yes** — §2, §3 |
| Owner-change event taxonomy | **Yes** — §4, §5 |
| Acting Assignment rules | **Yes** — §6 |
| Data ownership linked to UI split | **Yes** — §7 |
| Architectural conclusion recorded | **Yes** — §8 |
| WP-B4 Review Board questions prepared | **Yes** — §9 |
| Open architectural backlog recorded | **Yes** — §12 (OQ-B4-001) |
| Solution / code / binding proposed | **No** — by design |

**Finding:** Problem Space for **Owner vs Acting Assignment invariant** is **sufficiently defined** for WP-B4 Review Board preparation.

**Recommended next artefact (informational):** [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](./WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) (prepared — Review Board ratification); [review-board/WP-B4-REVIEW-BOARD-BRIEF.md](./review-board/WP-B4-REVIEW-BOARD-BRIEF.md) — Problem Space confirmation session. Conceptual framing: [WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md](./WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md).

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-05 | 0.1 | Initial problem space review — INV-B4-001…003; owner-change criteria; acting rules; data ownership split; WP-B4 Review Board questions |
| 2026-07-05 | 0.2 | Open architectural backlog — **OQ-B4-001** (Cabinet Owner × Acting Assignment × Active Cabinet Session) |
| 2026-07-05 | 0.3 | Cross-reference — [Conceptual Review: Persistent Workspace](./WP-B4-CONCEPTUAL-REVIEW-PERSISTENT-WORKSPACE.md) |
| 2026-07-05 | 0.4 | Terminology — [GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md) |
| 2026-07-06 | 0.5 | Traceability — main governance document link in §13 readiness |
