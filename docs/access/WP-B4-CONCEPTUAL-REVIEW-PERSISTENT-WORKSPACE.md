# WP-B4 — Conceptual Review: Position Cabinet as Persistent Workspace

## Status

**Complete (analysis)** — 2026-07-05

Conceptual architecture review under Tier G / WP-B4 — evaluates whether **Position Cabinet** should be recorded as **Persistent Workspace of Position** before the main WP-B4 governance document. **No architectural decision adopted.** **No Accepted ADR amendment.** **No change to INV-B4-001…003 or WP-B4 scope.**

| Field | Value |
|-------|-------|
| Work package | WP-B4 — prerequisite conceptual review |
| Prior artefacts | [WP-B4-PROBLEM-SPACE-REVIEW.md](./WP-B4-PROBLEM-SPACE-REVIEW.md) v0.5; [WP-B4-REVIEW-BOARD-BRIEF.md](./review-board/WP-B4-REVIEW-BOARD-BRIEF.md); [GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md) |
| Question evaluated | Is Position Cabinet a personal employee workspace, a function container, or a position-owned persistent workspace? |
| Runtime effect | **None** |

---

## 1. Purpose

During WP-B4 Problem Space preparation, participants asked whether Position Cabinet should be treated as a **standalone domain concept** — **Persistent Workspace of Position** — distinct from a **personal workspace of Employee**.

This review:

- Compares three interpretive models against **Accepted** architecture;
- Checks compatibility with **INV-B4-001…003**, data-ownership split, acting rules, and **OQ-B4-001**;
- Assesses impact on operational and HR/management contours;
- Recommends a **Review Board stance** without preempting Board ratification of the main WP-B4 governance document.

**Explicit non-goals:** API, schema, migrations, RBAC, UI, DEBT-B1-001 closure, ADR amendment.

---

## 2. Three interpretive models

### 2.1 Model A — Personal workspace of Employee

| Aspect | Assessment |
|--------|------------|
| **Definition** | Cabinet = «личный кабинет» сотрудника; operational data follows Person/Employee across positions |
| **Fit with Accepted architecture** | **Poor — rejected as domain model** |
| **Evidence against** | ARCH-001 §4.1–§4.3: Cabinet **belongs to Position**, not Person; tasks/reports/statistics **do not migrate** on turnover (§4.6). ADR-050: Cabinet owner = Position. ARCHITECTURE_GOVERNANCE principle 4–6. ACCESS-001 P1: permission on Cabinet, not occupant. |
| **Residual truth** | Post-login **UI shell** may present an aggregated «личный кабинет» (ARCH-001 §8) — **presentation layer**, not domain ownership. `/education` is **employee-owned** **inside** the shell, not proof that Cabinet = Employee workspace. |

**Conclusion:** Position Cabinet is **not** the personal workspace of Employee at domain level. Conflating the two contradicts Accepted baseline and **INV-B4-001…003**.

### 2.2 Model B — Function / permission container only

| Aspect | Assessment |
|--------|------------|
| **Definition** | Cabinet = bag of permissions and functional modules without persistent operational state |
| **Fit with Accepted architecture** | **Partial — insufficient alone** |
| **Evidence for container aspect** | Permission Template lives **inside** Cabinet (ADR-050, ADR-053). Cabinet carries permissions configuration (ACCESS-001 P1). |
| **Evidence against «only container»** | ARCH-001 §4.4 lists **persistent contents**: tasks, regular tasks, journals, reports, KPI, dashboards, statistics, function documents. §4.2: state and history **survive** vacancy and occupant change. ADR-050: «Contains (future consumers)» — operational objects, not template alone. |

**Conclusion:** Cabinet **includes** functional and permission configuration, but Accepted architecture defines it as **more** — a **durable operational locus** for position-bound work products.

### 2.3 Model C — Persistent Workspace of Position

| Aspect | Assessment |
|--------|------------|
| **Definition** | Long-lived **рабочее пространство должности**: accumulates position-bound work, history, and configuration; Person receives **time-bounded access** via Employment / acting |
| **Fit with Accepted architecture** | **Strong — already implied by Accepted documents** |
| **Primary sources** | ARCH-001 §4.1 «цифровое представление организационной должности»; §4.2 «долгоживущая сущность»; §4.5 operational objects bind to Cabinet; ADR-050 lifecycle (created with Position, destroyed only on liquidation); ARCHITECTURE_GOVERNANCE principles 4–6 |
| **Terminology note** | Phrase **«Persistent Workspace of Position»** is **not** used verbatim in Accepted ADR text today; semantic content **is** present as «Position Cabinet», «долгоживущая сущность», «operational container». |

**Conclusion:** Model C is **not a new entity proposal** — it is a ** clarifying label** for what Accepted ARCH-001 and ADR-050 already define, useful to disambiguate from Model A (legacy «личный кабинет» UX / user-centric runtime).

### 2.4 Comparative summary

| Model | Domain verdict | Role in Corpsite target architecture |
|-------|----------------|--------------------------------------|
| **A — Employee personal workspace** | **Reject** | UI aggregation only; employee-owned sections (`/education`) are **exceptions**, not Cabinet identity |
| **B — Function container only** | **Reject as sole definition** | Permission Template + modules are **components** of Cabinet |
| **C — Persistent Workspace of Position** | **Accept as primary characterisation** | Aligns with Accepted ARCH-001 / ADR-050; compatible with INV-B4-001…003 |

---

## 3. Compatibility with WP-B4 recorded invariants

| Artefact | Compatibility | Notes |
|----------|---------------|-------|
| **INV-B4-001** (owner change = permanent occupancy) | **Full** | Persistent workspace **persists**; only **access** changes with Employment |
| **INV-B4-002** (acting ≠ ownership) | **Full** | Acting Person **uses** workspace; does not **become** workspace owner |
| **INV-B4-003** (duty shell, not temporary executor) | **Full** | Model C **is** this principle stated as workspace semantics |
| **Position-owned vs Employee-owned** | **Full** | Workspace **holds** position-owned artefacts; employee-owned data **outside** workspace identity (Person/Employee binding) |
| **Owner vs Acting Assignment** | **Full** | Owner = permanent occupant with access entitlement; acting = overlay **into** same persistent workspace |
| **OQ-B4-001** (Owner × Acting × Active Session) | **Full — complementary** | Persistent Workspace answers **what endures**; OQ-B4-001 asks **how session/context selects** among accessible workspaces at runtime — **orthogonal**, not conflicting |

**Finding:** Model C **strengthens** WP-B4 Problem Space; **no invariant amendment required**.

---

## 4. Impact analysis (Model C as primary characterisation)

Assuming Position Cabinet = **Persistent Workspace of Position** (Accepted semantics; governance gloss only).

| Area | Expected behaviour | Model C impact |
|------|-------------------|----------------|
| **Смена владельца (Cabinet Owner)** | Owner changes on permanent Employment events only | Workspace **unchanged**; new Owner **inherits access** to same accumulated state (ARCH-001 §4.6) |
| **Временное исполнение (Acting)** | Acting access to **target** workspace without owner transfer | Acting Person operates **in** persistent workspace B; workspace A (primary) unchanged; **no** history fork to acting Employee |
| **KPI** | Position/function metrics | **Accumulate in workspace**; no reset on occupant change — aligns with ARCH-001 §4.4 and **INV-B4-001** |
| **Dashboards** | Function dashboards (`/dashboards` carcase) | **Position-owned panels** in workspace; UI carcase confirms direction |
| **История должности** | Operational timeline of the **position function** | **Lives in workspace**, not in Employee record; audit attributes actions to Person **in cabinet context** |
| **Накопленные результаты** | Reports, task completion history, statistics | **Persist in workspace** across occupants |
| **Knowledge (future)** | Function knowledge base | **Natural workspace content** if scoped to position function — consumer ADR scope; **not** personal knowledge base |
| **Documents (future)** | Function/regulatory docs vs personal file | Function docs → **workspace**; personal file → **Person** (ARCH-001 §4.5, ADR-047 boundary) |
| **Кадровый контур** | HR events on Person/Employment | **Orthogonal**: HR truth changes **access**; does not recreate workspace (ADR-036 acting; Employment lifecycle) |
| **Управленческий контour** | ACCESS-002 responsibilities on Cabinet | Responsibilities attach to **workspace/Cabinet contour**, not Employee — ACCESS-002 M1 compatible |

**Risk if Model A prevails in implementation:** task/report migration on turnover, KPI resets, permission bound to `users.role_id` — all flagged as foundation gaps in assessments.

---

## 5. Contradiction check

| Document | Contradiction with Model C? | Notes |
|----------|----------------------------|-------|
| **ARCH-001** | **No** | Model C restates §4.1–§4.6 |
| **ARCHITECTURE_GOVERNANCE** | **No** | Principles 4–6 |
| **ADR-050** | **No** | Operational container 1:1 Position |
| **ADR-051** | **No** | Access to workspace via Employment + acting overlay |
| **ADR-053** | **No** | Template configuration **inside** workspace |
| **ACCESS-001** | **No** | P1 Cabinet-centric binding |
| **ACCESS-002** | **No** | Management responsibilities on Cabinet |
| **WP-B1…WP-B3** | **No** | Domain taxonomy and PD-5.1 authorship **in Cabinet context** — consistent |

### Terminology tensions (not architectural contradictions)

| Source | Tension | Resolution |
|--------|---------|------------|
| **ADR-007** — «личные кабинеты» (MVP UI matrix, 2026-01) | Legacy **role-centric UX** vocabulary predates Position Cabinet model | ARCH-001 §13.4 / foundation summary #8 **Personal UI Shell** — explicit future disambiguation; governance gloss **Persistent Workspace** vs **personal UI shell** |
| **As-is runtime** | User-centric tasks/RBAC | **Implementation debt** — assessments confirm gap; Model C describes **target**, not current enforcement |
| **Russian «кабинет» in UI header** | Shows employee **position title** (`resolveCabinetTitle`) while navigating **position workspace** sections | UX labelling debt — carcase sections already split ownership; not a domain contradiction |

**Finding:** **No contradiction** with Accepted architecture or Tier G outcomes. Tensions are **legacy naming and as-is implementation**, addressable in UX/glossary programs without ADR amendment.

---

## 6. Benefits and risks (governance vocabulary adoption)

### Benefits of recording «Persistent Workspace of Position»

| # | Benefit |
|---|---------|
| B1 | Disambiguates **Position Cabinet** from **Employee personal workspace** and ADR-007 «личный кабинет» |
| B2 | Unifies narrative for KPI, dashboards, tasks, future Knowledge/Documents under one durability rule |
| B3 | Reinforces WP-B4 contour binding: Template binds to **workspace identity**, not occupant |
| B4 | Gives Review Board and implementers shared term without inventing a new entity |

### Risks

| ID | Risk | Mitigation |
|----|------|------------|
| CR-01 | Treated as **new ADR scope** requiring schema entity «Workspace» separate from `position_cabinets` | Record as **glossary / direction only** — ADR-050 entity remains Position Cabinet |
| CR-02 | Confusion with **Active Cabinet Session** (OQ-B4-001) | Session = **which** workspace is active for Person now; Persistent Workspace = **what** endures — keep both terms |
| CR-03 | Premature implementation pressure | Governance-only record; no API/UI mandate |
| CR-04 | Employee-owned sections perceived as «inside workspace ownership» | Reiterate `/education` = employee-owned **content shown in shell**, not workspace property |

---

## 7. Evaluation of OQ-B4-002

Proposed open question:

> **OQ-B4-002** — «Conceptual definition of Position Cabinet as a Persistent Workspace of Position rather than a personal workspace of Employee.»

| Criterion | Assessment |
|-----------|------------|
| Is the question **architecturally open** at Accepted baseline? | **Largely no** — ARCH-001 / ADR-050 already decide in favour of Model C over Model A |
| Would OQ-B4-002 block WP-B4 governance? | **No** |
| Would OQ-B4-002 add clarity vs noise? | **Marginal** — risks implying Accepted architecture is undecided |
| Is there residual open nuance? | **Yes, minor** — canonical **English/Russian glossary term**, relationship to ADR-007 disambiguation, explicit listing in governance artefacts |

**Recommendation on OQ-B4-002:** **Do not register as open architectural question.** Substance is **decided** at Accepted layer; remaining work is **terminology alignment**, not architectural fork.

**Alternative (if Board wants traceability):** record **[GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md)** — governance glossary (published 2026-07-05).

---

## 8. Review Board recommendations

| # | Recommendation |
|---|----------------|
| R1 | **Accept Model C** as **architectural direction (governance vocabulary)** for WP-B4 and downstream implementation planning — **without** amending Accepted ADR |
| R2 | **Reject Model A** as domain definition of Position Cabinet; treat «личный кабинет» as **UI shell** term requiring future disambiguation (ADR-007 legacy) |
| R3 | **Reject Model B as sole definition**; acknowledge Cabinet **contains** permissions and functions **as components** of persistent workspace |
| R4 | **Affirm** Model C is **compatible** with INV-B4-001…003, position/employee split, acting rules, and **OQ-B4-001** |
| R5 | **Do not open OQ-B4-002** — **[GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md)** published for glossary traceability |
| R6 | **Do not** expand WP-B4 program scope — HR class assignment and Problem Space confirmation remain unchanged |
| R7 | **Do not close DEBT-B1-001** — remains **WP-B8** |

---

## 9. Conclusion (for Review Board)

| Decision option | Verdict | Rationale |
|-----------------|---------|-----------|
| **Accept as architectural direction** | **Recommended** | Model C already encoded in Accepted ARCH-001 / ADR-050; governance gloss reduces ADR-007 / as-is UX confusion |
| **Register OQ-B4-002** | **Not recommended** | Question substantially **answered**; OQ would misrepresent architecture as undecided |
| **Reject concept** | **Not recommended** | Would contradict Accepted baseline and WP-B4 invariants |

**One-line summary:** Position Cabinet **is already architecturally** a **Persistent Workspace of Position**; WP-B4 should **name and ratify that direction in governance vocabulary**, not reopen domain definition and **not** introduce OQ-B4-002.

---

## 10. Relationship to adjacent artefacts

| Artefact | Relationship |
|----------|--------------|
| [WP-B4-PROBLEM-SPACE-REVIEW.md](./WP-B4-PROBLEM-SPACE-REVIEW.md) | INV-B4 and ownership split **unchanged**; this review **extends** conceptual framing only |
| [WP-B4-REVIEW-BOARD-BRIEF.md](./review-board/WP-B4-REVIEW-BOARD-BRIEF.md) | Problem Space session may **acknowledge** GLOSS-B4-001; no brief amendment required before Board reads this review |
| **Main WP-B4 governance document** | [WP-B4-POSITION-CABINET-CONTOUR-BINDING.md](./WP-B4-POSITION-CABINET-CONTOUR-BINDING.md) — prepared; cites **[GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md)**; HR class decisions **Review Board ratification subject** |
| **OQ-B4-001** | **Remains open** — session/context layer atop persistent workspaces |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-05 | 0.1 | Initial conceptual review — three models; compatibility; impact; OQ-B4-002 evaluation; recommendation to accept direction, not open OQ |
| 2026-07-06 | 0.2 | Traceability — main governance document link; fix erroneous INV-B4-004 reference |
