# PC-MOD-001 — Position Cabinet Functional Module Composition

## Status

**Draft (conceptual)** — 2026-07-06

Conceptual product-composition document for **Position Cabinet** as **Persistent Workspace of Position**. Defines the **stable functional module catalog** of the cabinet — what permanently belongs to the workspace, how modules relate, and what is deliberately outside.

| Field | Value |
|-------|-------|
| Register ID | **PC-MOD-001** |
| Precedes | Product implementation work packages; UI/API/RBAC design |
| Follows | WP-B1…WP-B4 (**Accepted** governance baseline); [GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md) |
| Normative sources (unchanged) | ARCH-001 §3–§4; ADR-050; ADR-051; GLOSS-B4-001 |
| Runtime effect | **None** |

**Suggested title (RU):** *Функциональная композиция модулей Position Cabinet*  
**Alternative title (EN):** *Position Cabinet — Persistent Workspace Module Catalog*

---

## 1. Purpose

After WP-B4, Position Cabinet is architecturally defined as a **Persistent Workspace of Position** — not a personal employee workspace, not a permission bag alone. The UI skeleton (`/tasks`, `/dashboards`, `/education`) proves navigation separation but does **not** define the full functional product.

This document answers:

> **What functional modules permanently compose Position Cabinet as a user-facing operational product?**

| In scope | Out of scope |
|----------|--------------|
| Functional module catalog | Implementation, schema, API |
| Module purpose, ownership, lifecycle | UI layout, navigation design |
| Cabinet boundaries (in / out) | RBAC, Permission Template binding |
| Inter-module relationships | ADR amendment |
| Extensibility principle | DEBT-DATA-001 repair |

**Usage rule:** Subsequent product and implementation documents **SHOULD cite PC-MOD-001** when introducing a new cabinet section or rebinding subsystem ownership. Citation does not authorize implementation.

---

## 2. Position Cabinet as functional container

### 2.1. Definition (derived — not new)

**Position Cabinet** = long-lived operational workspace of an org-unique **Position**. Synonymous with **Persistent Workspace of Position** (GLOSS-B4-001 §2).

Functional composition is the **catalog of durable product modules** hosted inside this workspace. It is **not** identical to:

| Concept | Distinction |
|---------|-------------|
| **Personal UI Shell** («личный кабинет») | Post-login **presentation** layer; may aggregate one or more Position Cabinets plus employee-owned views (ARCH-001 §8; ADR-007 legacy term) |
| **Permission Template** | **Configuration component** inside Cabinet — enables/constrains modules; not a user-facing functional module |
| **Platform User** | Authentication account — outside Cabinet entirely |

### 2.2. Module tiers

Modules are classified by **product permanence**, not by current implementation status.

| Tier | Meaning | Examples |
|------|---------|----------|
| **T1 — Core** | Always part of Position Cabinet concept for any occupied function | Задачи, KPI, Дашборды, История кабинета |
| **T2 — Function-conditional** | Permanent **module type**; visibility depends on Position function / organizational role | Команда, Кадровые процессы, Документы функции, Журналы |
| **T3 — Shell-attached** | Shown **in cabinet context** for current occupant; **not** position-owned | Образование, Развитие компетенций |

**Invariant:** Tier classification does **not** change the 1:1 Position ↔ Position Cabinet model (ADR-050).

---

## 3. Module catalog

Each module is described by:

- **Назначение** — why the module exists in the workspace;
- **Owner** — authoritative data owner: **Position**, **Employee**, **Organization**, **Shared**;
- **Жизненный цикл** — when the module appears, persists, ends;
- **При смене занимающего** — behaviour on Cabinet Owner change (INV-B4-001);
- **Отношение к Position Cabinet** — structural role inside the workspace.

**Owner legend:**

| Owner | Meaning |
|-------|---------|
| **Position** | Position-owned data (GLOSS-B4-001 §5) — persists in Cabinet across occupant change |
| **Employee** | Employee-owned data (GLOSS-B4-001 §6) — follows Person, not Cabinet identity |
| **Organization** | Org-level truth referenced or executed from Cabinet context; master data lives outside Cabinet |
| **Shared** | Combines Position-persistent artefacts with Organization rules or cross-cabinet visibility |

---

### 3.1. Задачи (Tasks)

| Field | Content |
|-------|---------|
| **Tier** | T1 — Core |
| **Назначение** | Primary **execution surface** of the position: adhoc tasks, regular tasks, catch-up, approvals, operational backlog. Answers: *«Что должность должна выполнить сейчас?»* |
| **Owner** | **Position** — task backlog, instances, and completion history bind to Position Cabinet (ARCH-001 §4.4–§4.5) |
| **Жизненный цикл** | Active from Cabinet creation; individual tasks have own business lifecycle; module persists until Position abolition |
| **При смене занимающего** | **Unchanged in Cabinet.** Backlog and history remain; new occupant inherits operational context. Audit records which Person acted in cabinet context |
| **Отношение к Position Cabinet** | **Central module** — primary input to KPI, dashboards, and cabinet history; anchor of daily work |

**Includes (conceptual):** adhoc tasks, regular task templates/instances scoped to Cabinet, task events, approval cycles where bound to Cabinet executor.

**Excludes:** platform notification transport; global task administration; tasks owned purely by Person exceptions (e.g. initiator-specific approve — ARCH-001 §4.5 oговорка).

---

### 3.2. KPI (Показатели)

| Field | Content |
|-------|---------|
| **Tier** | T1 — Core |
| **Назначение** | **Normative and factual performance measures** of the position: targets, thresholds, control points, compliance indicators. Answers: *«Выполняется ли функция должности по заданным показателям?»* |
| **Owner** | **Position** — KPI definitions, periods, and accumulated results are cabinet-scoped |
| **Жизненный цикл** | KPI periods roll forward while Position exists; historical series retained in Cabinet |
| **При смене занимающего** | **Fully preserved.** No reset, zeroing, or migration to predecessor/successor Employee |
| **Отношение к Position Cabinet** | **Derived layer** over Tasks, Reports, and Journals — not a standalone activity stream |

**Note:** KPI **targets** may be set by Organization policy; **recorded values and history** remain Position-owned inside Cabinet.

---

### 3.3. Дашборды (Dashboards)

| Field | Content |
|-------|---------|
| **Tier** | T1 — Core |
| **Назначение** | **Synthesized operational picture** for the position: status panels, trend views, exception highlights. Answers: *«Как выглядит состояние функции должности в целом?»* |
| **Owner** | **Position** — dashboard layouts, widgets, and saved views belong to Cabinet |
| **Жизненный цикл** | Evolves with Cabinet; persists through vacancy and occupant change |
| **При смене занимающего** | **Persist unchanged.** New occupant sees existing dashboards; may adjust views per business policy without destroying cabinet history |
| **Отношение к Position Cabinet** | **Presentation aggregation** over Tasks, KPI, Reports, Statistics — read-mostly product face of the workspace |

**Distinction:** Dashboards are **not** system health monitoring (platform ops) or org-wide executive BI outside cabinet scope.

---

### 3.4. Отчёты (Reports)

| Field | Content |
|-------|---------|
| **Tier** | T1 — Core (may share UX surface with Задачи) |
| **Назначение** | **Submitted operational reports** and approval history produced in course of duty. Answers: *«Что должность доложила и что было принято?»* |
| **Owner** | **Position** — report artefacts and submission history bind to Cabinet |
| **Жизненный цикл** | Accumulates over Position lifetime; individual reports immutable after acceptance |
| **При смене занимающего** | **History preserved in Cabinet.** Authorship attributed to Person in audit; report record stays cabinet-scoped |
| **Отношение к Position Cabinet** | **Output module** feeding KPI and Dashboards; tightly coupled to Tasks execution cycle |

---

### 3.5. Журналы (Operational Journals)

| Field | Content |
|-------|---------|
| **Tier** | T2 — Function-conditional |
| **Назначение** | **Continuous operational logs** required by function or regulation (shift journals, department logs, checklists). Answers: *«Что происходило в операционном контуре должности по времени?»* |
| **Owner** | **Position** |
| **Жизненный цикл** | Journal series persist for Cabinet lifetime; entries append-only per business rules |
| **При смене занимающего** | **Journal continuity in Cabinet** — no transfer to Employee record |
| **Отношение к Position Cabinet** | **Structured operational memory** — input to KPI and audit; common in clinical/administrative functions |

---

### 3.6. Документы функции (Function Documents)

| Field | Content |
|-------|---------|
| **Tier** | T2 — Function-conditional |
| **Назначение** | **Regulations, templates, SOPs, and function knowledge** applicable to the position's duty — not personal HR documents. Answers: *«По каким правилам и материалам работает должность?»* |
| **Owner** | **Shared** — Organization publishes authoritative documents; **Position** holds cabinet-scoped references, working copies, and function-specific document sets |
| **Жизненный цикл** | Org master versions managed outside Cabinet; cabinet binding and working artefacts persist with Cabinet |
| **При смене занимающего** | **Cabinet document set unchanged**; new occupant accesses same function library |
| **Отношение к Position Cabinet** | **Reference and working library** for execution — distinct from Employee Personal File (ARCH-001 §4.5; ADR-047) |

---

### 3.7. Аналитика и статистика (Analytics & Statistics)

| Field | Content |
|-------|---------|
| **Tier** | T2 — Function-conditional |
| **Назначение** | **Aggregated analysis** beyond dashboard snapshots: trends, comparisons, drill-down, export-oriented views for the position's scope. Answers: *«Какие закономерности видны в деятельности должности?»* |
| **Owner** | **Position** for cabinet-scoped aggregates; **Organization** for cross-cabinet or org-wide datasets referenced read-only |
| **Жизненный цикл** | Historical aggregates accumulate in Cabinet; org-wide cubes may outlive single Cabinet |
| **При смене занимающего** | **Position-scoped statistics persist in Cabinet** |
| **Отношение к Position Cabinet** | **Analytical depth layer** over Tasks, KPI, Reports — may overlap Dashboards conceptually but serves exploration, not daily status alone |

---

### 3.8. Команда (Team)

| Field | Content |
|-------|---------|
| **Tier** | T2 — Function-conditional |
| **Назначение** | **Subordinate operational context** for management positions: visibility of team members' cabinets, delegated work, team backlog health. Answers: *«Какова нагрузка и состояние подчинённых функций?»* |
| **Owner** | **Shared** — subordinate **Position Cabinets** remain Position-owned; **Organization** defines hierarchy; manager Cabinet holds **view and coordination context** only |
| **Жизненный цикл** | Active while Position has management scope; updates as org structure changes |
| **При смене занимающего** | **Team structure unchanged** (org truth); manager's saved team views may persist in manager Cabinet per policy |
| **Отношение к Position Cabinet** | **Cross-cabinet coordination module** — not a duplicate of subordinates' Tasks modules |

**Boundary:** Management **authority** (ACCESS-002) is orthogonal to this module's existence; module describes **functional product surface**, not permission policy.

---

### 3.9. Кадровые процессы (HR Processes)

| Field | Content |
|-------|---------|
| **Tier** | T2 — Function-conditional |
| **Назначение** | **HR operational workflows** initiated or executed from position context: enrollment, transfer initiation, acting appointment requests, HR document flows. Answers: *«Какие кадровые действия относятся к этой функции?»* |
| **Owner** | **Shared** — **Organization** owns HR truth and master events (ADR-036); **Position** owns cabinet-scoped process instances and duty-related HR tasks; **Employee** owns personal HR outcomes on Person record |
| **Жизненный цикл** | Process instances complete per HR lifecycle; cabinet-scoped operational residue may persist in HR-service or initiator Cabinets |
| **При смене занимающего** | **Open position-owned HR tasks stay in Cabinet**; employee-owned HR history follows Person |
| **Отношение к Position Cabinet** | **Bridge module** between operational workspace and HR contour — not HR master data administration |

**Distinction:** PD-5.1…PD-5.3 permission classes govern **who may act**; this module describes **what HR process surface** appears in relevant Cabinets.

---

### 3.10. История кабинета (Cabinet History)

| Field | Content |
|-------|---------|
| **Tier** | T1 — Core |
| **Назначение** | **Durable audit and narrative** of significant cabinet events: occupant changes, major configuration shifts, milestone completions. Answers: *«Что происходило с этой должностью в Corpsite over time?»* |
| **Owner** | **Position** |
| **Жизненный цикл** | Append-only from Cabinet creation until abolition |
| **При смене занимающего** | **Continuous record** — owner change is an event **in** history, not a break |
| **Отношение к Position Cabinet** | **Meta-module** — indexes and contextualizes other modules' significant events |

**Includes:** occupancy timeline, acting periods (as access events), major backlog milestones, template rebinding events (audit).

**Excludes:** platform auth logs; global admin audit.

---

### 3.11. Уведомления (Notifications Profile)

| Field | Content |
|-------|---------|
| **Tier** | T2 — Function-conditional |
| **Назначение** | **Cabinet-scoped delivery preferences and event subscriptions** — which operational events reach current occupants and through which channels. Answers: *«Как должность узнаёт о своих операционных событиях?»* |
| **Owner** | **Shared** — **Position** owns cabinet default profile; **Employee** may hold person-level channel preferences applied when occupying Cabinet |
| **Жизненный цикл** | Profile persists with Cabinet; channel bindings follow active access |
| **При смене занимающего** | **Cabinet defaults persist**; personal channel prefs follow new occupant's Employee record |
| **Отношение к Position Cabinet** | **Cross-cutting concern** — not a business domain module but permanent functional facet |

**Boundary:** Telegram bot transport, email infrastructure = platform — outside Cabinet.

---

### 3.12. Образование (Education)

| Field | Content |
|-------|---------|
| **Tier** | T3 — Shell-attached |
| **Назначение** | **Personal learning record** of current Cabinet Owner: courses, tests, certifications required or completed by the **Person** holding the position. Answers: *«Соответствует ли занимающий должность личным образовательным требованиям?»* |
| **Owner** | **Employee** (Person) — GLOSS-B4-001 §6 |
| **Жизненный цикл** | Follows Person career across Positions; not recreated on Cabinet entry |
| **При смене занимающего** | **Incoming Owner brings their own** education profile; **predecessor retains theirs.** No migration between Persons |
| **Отношение к Position Cabinet** | **Contextual view in workspace shell** — shown because occupant must meet duty requirements; **not** part of position-owned persistence |

**Acting rule (INV-B4-002):** Acting Assignee **must not** inherit or replace permanent Owner's education profile.

---

### 3.13. Развитие компетенций (Competency Development)

| Field | Content |
|-------|---------|
| **Tier** | T3 — Shell-attached |
| **Назначение** | **Personal competency trajectory** linked to duty requirements: gaps, development plans, assessments, skill profiles. Answers: *«Как занимающий развивает компетенции, необходимые для функции?»* |
| **Owner** | **Employee** — personal development artefacts; **Organization** may define competency frameworks externally |
| **Жизненный цикл** | Spans Employments; plans may reference Position requirements read-only |
| **При смене занимающего** | **Same as Образование** — follows Person; position requirement catalog is org reference |
| **Отношение к Position Cabinet** | **Downstream personal module** from Образование and duty requirements — still employee-owned |

---

### 3.14. Configuration component — Permission Template

Not a user-facing functional module. Included for boundary clarity.

| Field | Content |
|-------|---------|
| **Role** | Defines which modules are **enabled**, which actions are **permitted**, and contour binding baseline for the Cabinet |
| **Owner** | **Organization / Position** — template is component **inside** Cabinet (ARCH-001 §3.5) |
| **Жизненный цикл** | Co-extensive with Cabinet; rebinding is audited event |
| **При смене занимающего** | **Unchanged** — INV-B4-001; acting does not rebind template to acting Person |
| **Product note** | Template **gates** modules; it does not **replace** them |

---

## 4. Summary matrix

| Module | Tier | Owner | Persists on occupant change | In current UI skeleton |
|--------|------|-------|----------------------------|-------------------------|
| Задачи | T1 | Position | Yes | Yes (`/tasks`) |
| KPI | T1 | Position | Yes | No |
| Дашборды | T1 | Position | Yes | Yes (`/dashboards`) |
| Отчёты | T1 | Position | Yes | Partial (within Tasks) |
| Журналы | T2 | Position | Yes | No |
| Документы функции | T2 | Shared | Yes (cabinet binding) | No |
| Аналитика / статистика | T2 | Position (+ Org ref) | Yes (cabinet scope) | No |
| Команда | T2 | Shared | Structure yes; views policy | No |
| Кадровые процессы | T2 | Shared | Position-owned tasks yes | No |
| История кабинета | T1 | Position | Yes | No |
| Уведомления | T2 | Shared | Defaults yes | No |
| Образование | T3 | Employee | Follows Person | Yes (`/education`) |
| Развитие компетенций | T3 | Employee | Follows Person | No |

---

## 5. Boundaries of Position Cabinet

### 5.1. What belongs inside (functional product scope)

Position Cabinet **functionally includes**:

1. **Position-owned operational modules** (T1, T2 with Position owner) — durable workspace contents.
2. **Shell-attached employee modules** (T3) — shown in cabinet context for current Owner without becoming cabinet property.
3. **Permission Template** — internal configuration gating module availability.
4. **Cross-module relationships** — Tasks → KPI → Dashboards → Analytics chain; Education → Competency Development chain.

**Product question answered:** *«Everything needed to perform, monitor, and improve the organizational function of this Position inside Corpsite.»*

### 5.2. What deliberately does not belong

The following are **outside** Position Cabinet functional composition:

| Exclusion | Rationale |
|-----------|-----------|
| **Platform Account (Platform User)** | Authentication identity only — ARCH-001 §3.7, §8 |
| **Authentication & session** | Technical contour |
| **HR master data** | Person, Employment, org structure truth — referenced, not owned by Cabinet |
| **Global Administration** | System config, user provisioning, platform ops |
| **Reference data catalogs** | Positions catalog (as-is), org units, global dictionaries — Organization scope |
| **Personal File (Личное дело)** | Employee-owned HR documents — ADR-047; Person-bound exception (ARCH-001 §4.5) |
| **Permission domain ratification** | ACCESS-001 / ACCESS-002 governance — precedes enforcement, not a cabinet module |
| **Implementation data repair** | DEBT-DATA-001 — ops/governance; not product functionality |
| **System Health / infra monitoring** | Platform operations — not duty workspace |
| **Org structure editing** | Positions & Org Structure administration — Tier-1 foundation, not cabinet interior |

**Rule:** If an artefact's **authoritative owner** is Platform or global Organization master data with **no cabinet-scoped operational instance**, it is **not** a Position Cabinet module — at most a **link** from a module.

### 5.3. Boundary diagram

```text
┌─────────────────────────────────────────────────────────────┐
│                    Position Cabinet                          │
│  (Persistent Workspace of Position)                          │
│                                                              │
│  T1 Core          T2 Conditional        T3 Shell-attached    │
│  ─────────        ──────────────        ─────────────────    │
│  Задачи           Журналы               Образование          │
│  KPI              Документы функции     Развитие компетенций │
│  Дашборды         Аналитика                                  │
│  Отчёты           Команда                                    │
│  История          Кадровые процессы                          │
│                   Уведомления                                │
│                                                              │
│  [ Permission Template — configuration ]                     │
└─────────────────────────────────────────────────────────────┘
         ▲                              ▲
         │ access via Employment        │ Person-owned data
         │                              │ (not cabinet property)
    ┌────┴────┐                    ┌────┴────┐
    │ Person  │                    │ Employee │
    └────┬────┘                    └──────────┘
         │
    ┌────┴────────────── OUTSIDE CABINET ──────────────────────┐
    │ Platform User · Auth · HR Master · Global Admin ·        │
    │ Reference Data · Personal File · System Health             │
    └────────────────────────────────────────────────────────────┘
```

---

## 6. Inter-module relationships

### 6.1. Primary operational chain

The **duty execution loop** is the backbone of Position Cabinet:

```text
        ┌──────────┐
        │  Задачи  │  ← primary work intake & execution
        └────┬─────┘
             │ produces completions, delays, approvals
             ▼
        ┌──────────┐
        │   KPI    │  ← measures against norms
        └────┬─────┘
             │ aggregates status & trends
             ▼
        ┌──────────┐
        │ Дашборды │  ← daily operational picture
        └────┬─────┘
             │ deeper analysis
             ▼
        ┌──────────┐
        │ Аналитика│  ← exploration & reporting
        └──────────┘
```

**Supporting inputs:**

| Source | Feeds |
|--------|-------|
| **Отчёты** | KPI, Дашборды, История кабинета |
| **Журналы** | KPI, Аналитика |
| **Документы функции** | Задачи (execution rules), Образование (required materials) |
| **Команда** | Дашборды, Задачи (delegation/coordination views) |
| **Кадровые процессы** | Задачи (HR-driven work items), История кабинета |

**All position-owned links preserve INV-B4-001:** data flows **within** Cabinet continuity — not across Employee turnover migration.

### 6.2. Personal development chain

```text
   ┌─────────────┐         duty requirements (org reference)
   │ Образование │ ◄──────────────────────────────────────┐
   └──────┬──────┘                                          │
          │ identifies gaps                                  │
          ▼                                                  │
   ┌─────────────────────┐                                  │
   │ Развитие компетенций│ ──► may generate learning Tasks ─┘
   └─────────────────────┘         (Position-owned in Cabinet)
```

**Cross-chain rule:** Learning **records** are Employee-owned; **assigned development tasks** triggered by competency gaps are Position-owned **Tasks** in Cabinet. The chains intersect but **ownership boundary holds**.

### 6.3. Meta-layer

**История кабинета** spans all modules — records significant events without replacing subsystem history.

**Уведомления** spans all modules — delivery facet, not data owner.

---

## 7. Extensibility principle

Position Cabinet **must** accept new functional modules without revising the architectural model (1:1 Position ↔ Cabinet, Persistent Workspace, INV-B4-001…003).

### 7.1. Module registration rules

A new module **SHOULD** declare:

| # | Declaration |
|---|-------------|
| 1 | **Module ID** and human name |
| 2 | **Tier** (T1 / T2 / T3) |
| 3 | **Owner class** (Position / Employee / Organization / Shared) |
| 4 | **Lifecycle** (cabinet-coextensive vs item-level) |
| 5 | **Occupant-change behaviour** (persist / follow Person / policy exception) |
| 6 | **Upstream / downstream module links** |
| 7 | **Explicit exclusions** (what the module must not absorb) |

**Gate:** New module **must not** introduce a second workspace entity or Employee-owned operational backlog disguised as cabinet content.

### 7.2. Activation model

| Mechanism | Role |
|-----------|------|
| **T1 Core modules** | Always conceptually present; may be empty for some functions |
| **T2 modules** | Activated by **Position function profile** and/or **Permission Template** |
| **T3 modules** | Always available in shell when occupant has Employee record |
| **Business policy** | Controls vacancy behaviour, acting visibility — not module ownership |

Adding a module **does not require** schema changes to Position or Cabinet identity — only subsystem binding to `position_cabinet_id` (future implementation concern; not specified here).

### 7.3. Anti-patterns (forbidden extensions)

| Anti-pattern | Why forbidden |
|--------------|---------------|
| Employee-owned task backlog as «personal cabinet» | Violates Persistent Workspace model (Model A — rejected, WP-B4 Conceptual Review) |
| Cloning Cabinet on occupant change | Violates INV-B4-001 |
| Acting Person becomes implicit Owner of position-owned history | Violates INV-B4-002 |
| HR master data editor inside every Cabinet | Blurs Organization truth with duty workspace |
| Platform admin inside Cabinet | Breaks §5.2 boundary |

### 7.4. Future module candidates (illustrative — not ratified)

Examples that **may** be registered later via §7.1 without architectural change:

- **Knowledge base** (function-scoped) — likely T2, Shared/Position;
- **Quality audits** — T2, Position;
- **Budget / resource tracking** — T2, Shared;
- **Incidents / safety register** — T2, Position.

Illustrative list **does not** authorize implementation.

---

## 8. Relation to current UI skeleton

The existing Position Cabinet UI carcase ([`positionCabinetNav.ts`](../../corpsite-ui/lib/positionCabinetNav.ts)) implements **three navigation tabs** — a **minimal shell**, not the full module catalog:

| Tab | Maps to module | Ownership hint in code |
|-----|----------------|------------------------|
| Мои задачи | §3.1 Задачи | `existing` → Position-owned target |
| Дашборды | §3.3 Дашборды | `position_cabinet` |
| Образование | §3.12 Образование | `employee` |

PC-MOD-001 **does not** mandate navigation structure. Future modules **may** appear as tabs, sections, or cross-links — product decision deferred.

---

## 9. Explicit non-goals

| Non-goal | Note |
|----------|------|
| ADR amendment | Derived from Accepted sources only |
| RBAC / ACCESS-001 rows | Permission gating is downstream |
| API or schema design | Implementation phase |
| UI/UX specification | Product design phase |
| DEBT-DATA-001 resolution | Separate ops track |
| Vacancy process policy | Business Policy (ARCH-001 §4.7.2) |

---

## 10. Downstream consumers

| Consumer | Usage |
|----------|-------|
| Product roadmap | Module prioritization after WP-B4 |
| Subsystem ADRs | Ownership binding (`position_cabinet_id`) |
| UI product design | Section catalog — not layout |
| ACCESS / OPS programs | Distinguish cabinet modules from platform admin |
| Implementation master plan | Phase sequencing per module tier |

---

## 11. Open points (conceptual only)

| ID | Question | Default stance in this document |
|----|----------|--------------------------------|
| **OQ-MOD-001** | Should **Отчёты** remain a distinct module or a Tasks sub-domain? | Distinct module conceptually; may share UX |
| **OQ-MOD-002** | Minimum T1 set for **vacant** Cabinet product surface? | T1 modules **exist**; visibility = Business Policy |
| **OQ-MOD-003** | Where does **Personal File** link from — Cabinet or Employee contour only? | **Outside** Cabinet; link from Кадровые процессы if needed |

Open points **do not block** using this document as composition baseline.

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-06 | 0.1 | Initial draft — functional module catalog; boundaries; relationships; extensibility principle |
