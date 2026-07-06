# Governance Work Package Lifecycle — Tier G Standard

## Status

**Draft — pending Review Board** — 2026-07-06

Normative process standard for **Tier G — Governance** work packages under any organizational policy ratification program. Defines mandatory lifecycle stages, artefact expectations, decision authorities, and cross-cutting rules.

| Field | Value |
|-------|-------|
| Tier / phase | **G — Governance** / **G1 — Policy Ratification** (and equivalent governance phases) |
| Scope | Work package lifecycle only — **not** a policy document, architecture document, or Review Board session record |
| Applies to | Any Governance Work Package (`WP-*`) registered in a Tier G program |
| Does not apply to | Runtime implementation, engineering delivery, ops execution, ADR amendment |
| Reference implementation | Four completed work packages in the ACCESS-RATIFICATION-PROGRAM Track B sequence — see [Appendix A](#appendix-a--reference-implementation-patterns) |

**Explicit rule:** This standard produces **no runtime effect**. Adopting or following it does not ratify policy, approve matrix rows, authorize ops runbooks, or change enforcement behaviour.

---

## 1. Purpose

### 1.1 Why this standard exists

Governance Work Packages in Tier G follow a recurring pattern: **understand the problem → prepare normative governance text → assemble a ratification package → decide at Review Board → record closure**. After several packages, that pattern is stable enough to formalize as a **program-wide lifecycle standard**.

This document answers:

- *What stages must every Governance Work Package pass through?*
- *What artefact enters and leaves each stage?*
- *Who decides when a stage is complete?*
- *How do policy debt, open questions, architecture freeze, and traceability interact with the lifecycle?*

### 1.2 Relationship to other governance layers

| Layer | Role relative to this standard |
|-------|--------------------------------|
| **Program charter** (e.g. ratification program document) | Registers work packages, approval authorities per package, program sequencing — **does not replace** this lifecycle |
| **Normative policy documents** (Reviewed → Approved) | Subject matter being ratified — **not modified** by lifecycle compliance alone |
| **Accepted architecture** (ARCH-*, Accepted ADRs) | Fixed input — consumed, not redesigned, during Tier G |
| **Review Board** | Decision authority for ratification sessions |
| **Program progress report** | Optional program-level snapshot — aggregates WP closure state; not a lifecycle stage |
| **Tier B / implementation** | Downstream — **forbidden** as output of any lifecycle stage |

### 1.3 Non-goals

This standard **SHALL NOT**:

- Provide implementation guidance, runbook steps, schema design, or code change instructions.
- Amend Accepted ADRs or promote normative policy documents to **Approved**.
- Replace work-package-specific scope defined in the program register.
- Retroactively alter completed work packages or their traceability.

---

## 2. Lifecycle overview

### 2.1 Mandatory sequence

Every Governance Work Package **SHALL** traverse the stages below in order. Stages **MAY** be merged into a single physical document when the program register explicitly allows it (see Appendix A), but the **logical obligations** of each stage remain.

```text
1. Program Initiation
        ↓
2. Problem Space Review
        ↓
3. Conceptual Review                    [optional — see §4.3]
        ↓
4. Review Board Brief
        ↓
5. Main Governance Document
        ↓
6. Governance Package Consistency Review
        ↓
7. Ratification Package
        ↓
8. Review Board Session
        ↓
9. Closure Report
```

### 2.2 Work package states (summary)

| State | Meaning |
|-------|---------|
| **Not started** | Registered in program; no initiation artefact |
| **Open (initiated)** | Program Initiation recorded; lifecycle in progress |
| **Substantive complete** | Review Board Session recorded all mandatory decisions; Closure Report prepared; **attestation may still be pending** |
| **Closed** | All exit criteria met including mandatory attestation signatures recorded in Closure Report |

**Substantive complete ≠ Closed.** A work package **MAY** unblock downstream **preparation** after substantive completion while remaining **Open** pending signatures.

### 2.3 Parallel work

| Activity | Rule |
|----------|------|
| Attestation signature collection | **MAY** run in parallel with downstream WP **preparation** — does not block Problem Space or Brief work on successor packages unless program register says otherwise |
| Multiple Review Board sessions | **MAY** be required when mandatory questions are not resolved in Session 1 |
| Open Questions backlog | **MAY** continue across sessions — non-blocking unless Review Board declares otherwise |

---

## 3. Stage definitions

Each subsection uses the same template: **Goal → Inputs → Outputs → Completion criteria → Allowable outcomes → Decision authority**.

Naming convention for artefacts (recommended, not mandatory):

| Stage | Typical artefact name |
|-------|----------------------|
| 1 | `WP-{ID}-PROGRAM-INITIATION.md` |
| 2 | `WP-{ID}-PROBLEM-SPACE-REVIEW.md` |
| 3 | `WP-{ID}-CONCEPTUAL-REVIEW-{TOPIC}.md` |
| 4 | `review-board/WP-{ID}-REVIEW-BOARD-BRIEF.md` |
| 5 | `WP-{ID}-{SUBJECT}.md` (or program-equivalent combined review document) |
| 7 | `WP-{ID}-RATIFICATION-PACKAGE.md` |
| 8 | `review-board/WP-{ID}-SESSION-{N}-REVIEW-BOARD-RECORD.md` |
| 9 | `WP-{ID}-CLOSURE-REPORT.md` |

Optional supporting artefacts (e.g. `GLOSS-{ID}-{nnn}-*.md` vocabulary registers) **MAY** be produced between stages 3 and 5 when terminology must be stabilized before normative text.

---

### 3.1 Stage 1 — Program Initiation

| Dimension | Definition |
|-----------|------------|
| **Goal** | Open the work package as a governed unit: state **why** it exists now, **what** decision it must produce, **who** approves it, and **what is explicitly out of scope**. |
| **Inputs** | Program register entry for the work package; predecessor WP closure or substantive-complete reports; normative policy documents at **Reviewed** (or program-equivalent); Accepted architecture references; program progress snapshot (if maintained). |
| **Outputs** | Program Initiation document containing: objective (single sentence), scope boundary (in / out tables), mandatory inputs list, approval authority, success criteria, explicit non-authorizations (no runtime, no document promotion, no ops). |
| **Completion criteria** | Initiation document published with status **Open (initiated)**; scope boundary reviewed by program owner; no contradiction with Architecture Freeze identified at initiation time (or escalated as blocker). |
| **Allowable outcomes** | **Initiated** — work package is authorized to proceed to Problem Space Review. **Blocked** — initiation deferred pending predecessor WP or architecture clarification (record rationale). |
| **Decision authority** | **Program owner** (or delegated governance lead) — confirms the WP is the correct next unit of work. Architecture lead **MAY** be consulted for freeze compatibility — consult only, not initiation veto unless hard contradiction. |

---

### 3.2 Stage 2 — Problem Space Review

| Dimension | Definition |
|-----------|------------|
| **Goal** | Establish shared understanding of the **organizational problem** before any normative solution or Review Board ratification vote. Record boundaries, dependencies, contradictions, and architectural invariants **as governance input** (without amending Accepted ADRs). |
| **Inputs** | Program Initiation; normative policy sections in scope; predecessor WP decisions and policy debt register; Accepted architecture; cross-track dependencies (if any). |
| **Outputs** | Problem Space Review document containing: problem statement, scope confirmation, dependency analysis, explicit **non-solutions** (what this WP will not decide), readiness finding (“sufficiently understood” / “not yet”), optional **architectural invariant record** (governance labels only — not ADR text). |
| **Completion criteria** | Document states Problem Space is **sufficiently understood** to proceed to Brief preparation **OR** lists blocking gaps with owner; no undocumented contradiction with Accepted architecture; out-of-scope items assigned to owning WP IDs. |
| **Allowable outcomes** | **Complete — proceed**; **Incomplete — rework** (return to analysis); **Escalated** — architectural conflict requires architect decision before Brief (does not authorize ADR amendment by WP). |
| **Decision authority** | **Governance author** (document preparer) recommends readiness; **program owner** accepts readiness finding. Review Board **does not** ratify Problem Space unless a dedicated confirmation session is scheduled (see Stage 4). |

**Constraint:** Problem Space Review **SHALL NOT** propose implementation designs, API contracts, schema changes, or ops runbook steps.

---

### 3.3 Stage 3 — Conceptual Review *(optional)*

| Dimension | Definition |
|-----------|------------|
| **Goal** | When Problem Space alone is insufficient, provide a **conceptual governance framing** — metaphors, characterisations, vocabulary boundaries — that the Main Governance Document will rely on, without becoming normative until ratified. |
| **When required** | **Optional.** Required when: (a) new governance vocabulary is introduced; (b) a cross-cutting concept must be stabilized before normative rules; (c) Review Board Brief cannot be written without conceptual alignment. **MAY** be skipped when Problem Space + existing program vocabulary suffice. |
| **Inputs** | Completed Problem Space Review; Accepted architecture; prior glossary or registry artefacts; sibling WP conceptual decisions. |
| **Outputs** | Conceptual Review document; optional glossary register (`GLOSS-{ID}-*`) if terminology must be authoritative before Main Document drafting. |
| **Completion criteria** | Conceptual framing is internally consistent with Problem Space and Architecture Freeze; terms either defined in glossary or explicitly deferred as Open Question; Main Document author confirms conceptual inputs are sufficient. |
| **Allowable outcomes** | **Complete**; **Merged into Main Document** (if program allows single-artefact pattern — conceptual sections must remain identifiable); **Deferred** — concept unresolved; Open Question recorded. |
| **Decision authority** | **Governance author** + **program owner**; architecture lead consulted when conceptual framing touches Accepted contracts. |

---

### 3.4 Stage 4 — Review Board Brief

| Dimension | Definition |
|-----------|------------|
| **Goal** | Prepare the Review Board to render a **bounded decision**: state session object, in/out scope, mandatory review questions, fixed architectural answers, decision options, and risks — **without presupposing outcome**. |
| **Inputs** | Problem Space Review; Conceptual Review (if any); draft or outline of Main Governance Document (if available); program register approval authority; predecessor session records. |
| **Outputs** | Review Board Brief with status **Briefing only — no ratification recorded**; numbered mandatory questions; explicit non-authorizations; proposed policy debt items (conditional — if debt path chosen). |
| **Completion criteria** | All mandatory questions enumerated; scope boundaries match Program Initiation; Architecture Freeze section lists Accepted references; readiness table completed factually; brief does **not** contain ratification outcome. |
| **Allowable outcomes** | **Briefing complete — ready for session**; **Briefing incomplete** — return to Problem Space or Main Document draft; **Split session plan** — Problem Space confirmation session vs ratification session (two briefs or two sections — both allowed). |
| **Decision authority** | **Governance author** publishes brief; **Review Board chair** (or program owner) confirms session readiness. |

**Note:** A brief **SHALL NOT** fix Review Board decisions. Wording such as “recommended outcome” is discouraged; factual readiness assessment is permitted.

---

### 3.5 Stage 5 — Main Governance Document

| Dimension | Definition |
|-----------|------------|
| **Goal** | Produce the **normative governance text** that Review Board will ratify (or reject) — organizational rules, class definitions, binding models, principles, or disposition tables as defined by the work package scope. |
| **Inputs** | Problem Space Review; Conceptual Review / glossary (if any); Brief (may iterate concurrently); Accepted architecture; normative policy (**Reviewed** — not promoted by this stage). |
| **Outputs** | Main Governance Document — status **Prepared** until Review Board ratifies; document history section; traceability header to preparatory inputs; explicit scope and non-authorizations. |
| **Completion criteria** | Full normative content for ratification scope drafted; internal cross-references resolve; no contradiction with Accepted architecture unless recorded as Open Question with architect acknowledgment; approval authority stated; status is **Prepared** (not **Accepted (Ratified)**). |
| **Allowable outcomes** | **Prepared — ready for consistency review**; **Draft incomplete**; **Withdrawn** — scope absorbed by program revision (record in initiation). |
| **Decision authority** | **Governance author** (with domain owner review); **architecture lead** confirms non-contradiction with Accepted ADRs — consultative sign-off before Consistency Review, not ratification. |

**Merged-document pattern:** Some work packages combine Stages 5–7 in one physical document (e.g. principles review + ratification outcome sections). The Main Governance portion **SHALL** remain identifiable and **SHALL** receive a distinct status transition upon ratification.

---

### 3.6 Stage 6 — Governance Package Consistency Review

| Dimension | Definition |
|-----------|------------|
| **Goal** | Verify the **assembled governance package** (Problem Space through Main Document + Brief) is internally consistent, traceable, and ready for formal ratification assembly — applying **editorial** fixes only. |
| **Inputs** | All preparatory artefacts (stages 1–5); Brief; optional glossary; program debt register entries referenced by the WP. |
| **Outputs** | Consistency Review record — **MAY** be a section inside Ratification Package or Main Document; lists findings, editorial fixes applied, blocking issues (if any); readiness statement. |
| **Completion criteria** | No unresolved internal contradictions; stale cross-references corrected; version/status fields aligned; Architecture Freeze respected; explicit statement: **ready for Ratification Package** or **not ready** with owner. |
| **Allowable outcomes** | **Accepted — ready for Ratification Package**; **Editorial fixes applied** — documented; **Blocked — architectural issue** — escalate to architect; do not ratify until resolved or scoped as Open Question. |
| **Decision authority** | **Governance author** performs review; **program owner** accepts readiness. Architecture lead **SHALL** be involved if review touches invariant records or Accepted ADR alignment. |

See [§5 — Editorial vs architectural changes](#5-editorial-vs-architectural-changes) for fix boundaries.

---

### 3.7 Stage 7 — Ratification Package

| Dimension | Definition |
|-----------|------------|
| **Goal** | Assemble **everything Review Board needs** for a formal session: document inventory, ratification scope, review criteria checklist, session question index, attestation requirements, and outcome template. |
| **Inputs** | Consistency Review completion; all staged artefacts; program register approval authority; policy debt items in scope. |
| **Outputs** | Ratification Package — status **Prepared** until session; § Ratification outcome (template pre-session; filled post-session); links to Session Record. |
| **Completion criteria** | Document inventory complete with version/status; in-scope / out-of-scope ratification subjects listed; review criteria checklist populated; mandatory questions mapped to session record template; attestation roles listed. |
| **Allowable outcomes** | **Prepared — ready for Review Board Session**; **Incomplete**; **Merged package** (combined with Main Document — outcome section still filled post-session). |
| **Decision authority** | **Program owner** declares package ready for scheduling; **Review Board chair** accepts package for session. |

---

### 3.8 Stage 8 — Review Board Session

| Dimension | Definition |
|-----------|------------|
| **Goal** | Render **organizational governance decisions** on each ratification subject and mandatory question; record dispositions, policy debt, and explicit non-authorizations. |
| **Inputs** | Ratification Package; Review Board Brief; Main Governance Document (**Prepared**); Session Record template; quorum per program register. |
| **Outputs** | Session Record (`SESSION-{N}`) with: per-question answers; ratification subject disposition table; policy debt register updates; attestation block (may remain pending); action items. |
| **Completion criteria** | All mandatory questions answered; overall session outcome recorded (`Ratified` / `Ratified with Policy Debt` / `Deferred` / `Rejected`); Main Document status updated if ratified; Ratification Package outcome section filled; no silent scope expansion. |
| **Allowable outcomes (session level)** | See [§8 — Ratification](#8-ratification). |
| **Allowable outcomes (per question)** | **Accepted** / **Rejected** / **Deferred** — as defined in brief. |
| **Decision authority** | **Review Board** — mandatory authorities per program register **SHALL** participate or delegate per charter. Governance authors **SHALL NOT** self-ratify. |

**Multi-session rule:** If mandatory questions remain **Deferred** or **Rejected**, Session `{N+1}` **MAY** be scheduled. Substantive completion requires all mandatory questions **Accepted** or explicitly covered by a valid session outcome.

**Post-session document updates (allowed without architect):**

- Main Governance Document status → **Accepted (Ratified)** when session ratifies — **body unchanged** unless Review Board ordered editorial sync only.
- Ratification Package → **Decision recorded**.
- Document history entries on ratified artefacts.

**Post-session updates (forbidden without architect / new WP):**

- Main Governance Document **substantive** changes after **Rejected** or **Deferred** architectural finding.
- Accepted ADR amendment.

---

### 3.9 Stage 9 — Closure Report

| Dimension | Definition |
|-----------|------------|
| **Goal** | Summarize **what was completed**, **what was decided**, **what debt remains**, **what signatures are pending**, and **which downstream WPs may begin** — without itself closing the WP unless exit criteria are met. |
| **Inputs** | Session Record(s); Ratification Package outcome; Main Document final status; program register exit criteria. |
| **Outputs** | Closure Report — status **Prepared — not closed** until attestation complete; deliverables table; ratification summary; policy debt summary; remaining signatures; substantive completion checklist. |
| **Completion criteria (substantive)** | All session decisions summarized; debt register reflected; downstream readiness stated; explicit “does not close WP” until signatures — unless all exit criteria met. |
| **Completion criteria (formal closure)** | All mandatory attestation signatures recorded; program register updated to **Closed**; Closure Report status → **Closed**. |
| **Allowable outcomes** | **Prepared — substantive complete**; **Closed**; **Reopened** — only via new program decision (out of scope for this standard). |
| **Decision authority** | **Program owner** declares formal closure after signatures; Review Board outcomes are **not** re-litigated in Closure Report. |

---

## 4. Cross-cutting rules

### 4.1 Traceability

Traceability is **mandatory** across the lifecycle.

| Rule | Requirement |
|------|-------------|
| **Forward chain** | Each stage output **SHALL** cite its immediate inputs by document ID and version/status. |
| **Backward chain** | Session Record and Closure Report **SHALL** link to Ratification Package, Brief, Main Document, and Problem Space. |
| **Decision authority trace** | Ratification subjects **SHALL** map to session question IDs and brief sections. |
| **Debt trace** | Every policy debt item **SHALL** cite origin WP/session and resolution WP. |
| **Non-mutation of history** | Completing a successor WP **SHALL NOT** rewrite ratified text of predecessor WPs — only administrative registers **MAY** be synced when factual errors are found (correction process in §5). |
| **Registers** | Program **MAY** maintain central debt / ratification registers; Closure Reports **SHALL** remain authoritative for per-WP summaries. |

Traceability **SHALL NOT** be confused with implementation dependency: downstream engineering gates are out of scope.

### 4.2 Document statuses

Statuses apply to **artefacts**, not organizational policy unless explicitly stated.

#### Work package (program register)

| Status | Meaning |
|--------|---------|
| **Not started** | Registered only |
| **Open (initiated)** | Lifecycle underway |
| **Open (substantive complete)** | Session complete; attestation pending |
| **Closed** | All exit criteria met |

#### Lifecycle artefacts

| Status | Typical use |
|--------|-------------|
| **Open (initiated)** | Program Initiation |
| **Complete** | Problem Space, Conceptual Review, Session Record |
| **Briefing only** | Review Board Brief — pre-session |
| **Prepared** | Main Document, Ratification Package — pre-ratification |
| **Prepared — not closed** | Closure Report — post-session, pre-signatures |
| **Decision recorded** | Ratification Package / combined review doc — post-session |
| **Accepted (Ratified)** | Main Governance Document — post-session ratification |
| **Active** | Glossary / registry supporting artefact |
| **Closed** | Closure Report — all signatures collected |

#### Normative policy documents (external to WP)

| Status | Meaning |
|--------|---------|
| **Reviewed** | Architecture-validated; organizational approval incomplete |
| **Approved** | Document-level promotion — **not** achieved by WP ratification alone; requires program document-promotion WP |

**Forbidden status shortcuts:** A Main Document **SHALL NOT** carry **Accepted (Ratified)** before Review Board Session. A WP **SHALL NOT** be marked **Closed** without recorded attestation when program register requires signatures.

### 4.3 Architecture Freeze

| Rule | Statement |
|------|-----------|
| **Fixed inputs** | Accepted ARCH-* and Accepted ADRs are **read-only** inputs for all lifecycle stages. |
| **Consumption, not redesign** | Governance Work Packages **consume** architecture — they do **not** amend it. |
| **Review Board boundary** | Review Board **SHALL NOT** redesign Accepted contracts; it **MAY** accept governance invariants that **align with** Accepted architecture without opening an ADR amendment. |
| **Contradiction handling** | If Problem Space or Main Document reveals contradiction with Accepted architecture: **stop ratification**; escalate to architecture lead; resolution path is **ADR amendment or new ADR** — outside Tier G WP authority. |
| **Invariant records** | Problem Space **MAY** record governance invariant labels (e.g. `INV-{WP}-{nnn}`) as **binding input** for the WP — these are governance artefacts, not ADR replacements. |
| **Explicit non-authorization** | Every stage from Initiation through Closure **SHALL** restate: no Accepted ADR amendment by this WP. |

### 4.4 Policy Debt handling

Policy debt is an **explicit deferral** of a named organizational decision to a future work package while still allowing **Ratified with Policy Debt** outcomes.

| Element | Rule |
|---------|------|
| **Identifier** | `DEBT-{track}{origin-WP}-{nnn}` — unique within program |
| **Minimum fields** | Origin WP/session; item description; status (`Open` / `Closed` / `Continues`); resolution WP; date recorded |
| **Creation** | Review Board **MAY** create or continue debt at session; Brief **MAY** propose conditional debt paths |
| **Closure** | Only a later WP session **MAY** close debt — with recorded disposition |
| **Partial closure** | Debt **MAY** narrow (e.g. class closed, code still open) — same ID, updated description |
| **Substantive completion** | WP **MAY** be substantively complete while leaving debt **Open** — debt must appear in Session Record and Closure Report |
| **Valid outcome** | **Ratified with Policy Debt** is a **successful** session outcome — not a failure |
| **Register sync** | Program-level debt register **SHOULD** be updated after session — administrative action, not runtime config |

Policy debt **SHALL NOT** authorize implementation, ops execution, or silent matrix approval.

### 4.5 Open Questions

Open Questions differ from policy debt: they record **unresolved conceptual or architectural topics** that do **not** block ratification of the current scope.

| Element | Rule |
|---------|------|
| **Identifier** | `OQ-{WP}-{nnn}` |
| **Disposition** | Typically **Deferred — non-blocking** unless Review Board states otherwise |
| **Location** | Problem Space backlog and/or Session Record |
| **Resolution owner** | Future WP, architecture program, or engineering phase — assigned at deferral |
| **Not debt** | Open Questions **SHALL NOT** be double-recorded as policy debt unless they imply a mandatory organizational policy decision with program WP owner |

### 4.6 Editorial vs architectural changes

| Class | Examples | Who may apply | When |
|-------|----------|---------------|------|
| **Editorial** | Typo; broken link; stale version reference; status field sync; table formatting; alignment with ratified session wording without meaning change | Governance author during Consistency Review | Before or immediately after session if Review Board ordered sync only |
| **Architectural** | Invariant definition change; new binding rule; class redefinition; contradiction resolution with Accepted ADR; scope expansion | **Architect** + new Review Board cycle | **Not** during Consistency Review; requires architect decision |
| **Policy substantive** | New organizational rule not in Brief mandatory questions | Review Board session or **Deferred** | Requires session — not author self-edit after **Prepared** |

**Stop rule:** If Review Board **Rejected** or required architectural change: governance author **SHALL NOT** edit Main Document unilaterally — prepare remark list; await architect direction; schedule new session.

### 4.7 Ratification

Ratification is the **Review Board act** recorded in Session `{N}` — not document publication alone.

#### Session outcomes

| Outcome | Meaning | Main Document | WP substantive status |
|---------|---------|---------------|------------------------|
| **Ratified** | All subjects accepted; no new debt | → **Accepted (Ratified)** | Substantive complete |
| **Ratified with Policy Debt** | Subjects accepted; named deferrals recorded | → **Accepted (Ratified)** | Substantive complete |
| **Deferred** | Mandatory items unresolved | Remains **Prepared** | Not substantively complete |
| **Rejected** | Subject not accepted | Remains **Prepared** or withdrawn | Not substantively complete |

#### Explicit non-authorizations (every session)

Review Board sessions **SHALL** record that ratification **does not**:

- Promote normative policy documents to **Approved** (unless session object is explicitly document promotion — rare, separate WP type).
- Approve matrix rows, ops runbooks, or production data changes.
- Close downstream engineering gates.
- Amend Accepted ADRs.
- Change runtime enforcement.

Attestation signatures **MAY** be collected after substantive completion; their absence **SHALL NOT** invalidate recorded Review Board decisions unless program charter explicitly requires signatures before decisions take effect (default: signatures gate **formal closure**, not decision recording).

### 4.8 Closure

Closure is a **program register transition**, not a Review Board session.

| Criterion type | Examples |
|----------------|----------|
| **Substantive (Closure Report “Prepared”)** | Sessions complete; Main Document ratified if applicable; debt recorded; deliverables listed |
| **Formal (Closure Report “Closed”)** | Mandatory attestation signatures collected; program owner marks WP **Closed** |

Closure Report **SHALL** state which downstream WPs **may begin preparation** and which **require** formal closure first — per program register, defaulting to: preparation allowed after substantive completion.

---

## 5. Editorial vs architectural changes

*(Normative summary — see §4.6 for table.)*

Governance Package Consistency Review is the **last gate** for editorial correction before Review Board. After a **Ratified** session, only **editorial sync** explicitly ordered by Review Board is permitted without a new session. Any change that alters organizational meaning **SHALL** trigger a new Brief and Session.

---

## 6. Roles and decision matrix

| Role | Typical responsibilities across lifecycle |
|------|------------------------------------------|
| **Program owner** | Initiation approval; consistency readiness; schedule Review Board; formal closure |
| **Governance author** | Draft artefacts stages 1–7; perform Consistency Review; prepare Session Record draft |
| **Domain owner** (HR, ops, executive as scoped) | Review Main Document; mandatory attestation per program register |
| **Architecture lead** | Freeze compliance; consult on invariants; **no** ratification vote unless also Board member |
| **Review Board chair** | Session conduct; confirms mandatory authorities present |
| **Review Board** | Ratification decisions stage 8 |

Mandatory authorities are defined **per work package** in the program register — this standard does not override them.

---

## 7. Exit criteria checklist (template)

Use in Closure Report § “Why substantively complete”:

| # | Criterion | Evidence |
|---|-----------|----------|
| 1 | Program Initiation recorded | Initiation doc |
| 2 | Problem Space complete | Problem Space Review readiness finding |
| 3 | Conceptual Review complete or waived | Doc or waiver in Initiation |
| 4 | Review Board Brief complete | Brief status |
| 5 | Main Governance Document **Prepared** → **Accepted (Ratified)** if in scope | Main doc status |
| 6 | Consistency Review **Accepted** | Ratification Package or review section |
| 7 | Ratification Package complete | Package inventory |
| 8 | Session `{N}` outcome recorded | Session Record |
| 9 | Policy debt / OQ dispositions recorded | Session Record |
| 10 | Implementation gates unchanged verified | Session explicit non-authorizations |
| 11 | Attestation signatures | Program register |
| 12 | WP formally **Closed** | Program register |

Items 1–10 → **substantive complete**. Items 11–12 → **formal closure**.

---

## 8. Ratification

*(Normative summary — see §4.7 for outcomes and non-authorizations.)*

The **authoritative ratification record** is the Session Record. Ratification Package § Ratification outcome **SHALL** mirror Session Record for program audit. Main Governance Document status **SHALL** reflect session disposition on the normative text.

---

## 9. Closure

*(Normative summary — see §4.8.)*

Closure Report is the **work-package summary of record** for stakeholders. It **SHALL NOT** contradict Session Record. Formal closure requires attestation when mandated by program charter.

---

## Appendix A — Reference implementation patterns

The following patterns were observed in four Track B work packages that completed substantive governance (ACCESS-RATIFICATION-PROGRAM). They illustrate **allowed variations** — not additional requirements.

| Pattern | Example | Stages affected |
|---------|---------|-----------------|
| **Full multi-document lifecycle** | Later package with Problem Space → Conceptual Review → Main Document → Ratification Package → Session → Closure | 1–9 explicit |
| **Combined review + ratification doc** | Principles review with outcome § inside same file | 5 + 7 + 8 merged; Session Record still separate |
| **Ratification package as primary assembly** | Taxonomy package with review sheets + consistency § + outcome § | 5–7 merged |
| **Multi-session taxonomy** | Four domain sessions under one WP | Stage 8 repeated; one Closure Report |
| **Split Brief purpose** | Problem Space confirmation session vs full ratification session | Stage 4 duplicated logically |
| **Optional Conceptual Review skipped** | Packages where Problem Space + policy text sufficed | Stage 3 waived |
| **Initiation implicit** | Early packages initiated directly from program register | Stage 1 minimal or implicit |

These patterns confirm: **logical stages are mandatory; physical document splitting is flexible** if Consistency Review and Session Record preserve traceability.

---

## Appendix B — Relationship to program documents

| Document type | Relationship |
|---------------|--------------|
| Ratification program charter | Registers WP scope and authorities — **parent** of this lifecycle |
| Tier G progress report | Aggregates WP states — **informative**, not a lifecycle stage |
| Normative policy (Reviewed) | Subject matter — status promotion is separate program gate |
| Review Board brief template | Stage 4 starter — **does not override** this standard |

This standard **SHALL** be cited by future program charters as the mandatory WP process. Adoption of this standard **does not** retroactively change completed work packages.

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-06 | 0.1 | Initial draft — Tier G Governance Work Package Lifecycle standard; derived from WP-B1…B4 reference implementation; pending Review Board |
