# PC-PROFILE-001 — Position Cabinet Functional Profiles

## Status

**Draft (conceptual)** — 2026-07-06

Conceptual product document defining **Cabinet Profile** — the intermediate layer between **Position** and **Module Composition** ([PC-MOD-001](./PC-MOD-001-position-cabinet-functional-composition.md)). Declares which **combinations of functional modules** apply to different **classes of positions**, without implementation, RBAC, or UI design.

| Field | Value |
|-------|-------|
| Register ID | **PC-PROFILE-001** |
| Precedes | Product implementation; profile registry; navigation configuration model |
| Follows | [PC-MOD-001](./PC-MOD-001-position-cabinet-functional-composition.md); WP-B1…WP-B4; [GLOSS-B4-001](./GLOSS-B4-001-position-cabinet-vocabulary.md) |
| Normative sources (unchanged) | ARCH-001 §3–§4; ADR-050; ADR-051; ACCESS-001; ACCESS-002 |
| Runtime effect | **None** |

**Suggested title (RU):** *Функциональные профили Position Cabinet*

---

## 1. Purpose

[PC-MOD-001](./PC-MOD-001-position-cabinet-functional-composition.md) defines **what modules exist** in Position Cabinet (T1 / T2 / T3 tiers). It does **not** define **which modules a given Position should activate**.

This document answers:

> **Which functional profiles exist, and which module combinations does each profile declare for its class of positions?**

### 1.1. Layer model

```text
Position (org-unique staffing unit)
    │
    │  assigned at Position / Cabinet creation or reclassification
    ▼
Cabinet Profile (functional workspace class)
    │
    │  declares module set from PC-MOD-001 catalog
    ▼
Module Composition (enabled T1 / T2 / T3 modules)
    │
    │  instantiated per Cabinet identity
    ▼
Position Cabinet (Persistent Workspace of Position)
    │
    └── Permission Template (configuration — gates actions within modules)
```

**Invariant:** One Position ↔ one Position Cabinet (ADR-050). Profile does **not** create additional Cabinet entities.

| In scope | Out of scope |
|----------|--------------|
| Cabinet Profile definition and catalog | Implementation, schema, API |
| Profile → module mapping | UI layout, tab order |
| Orthogonality to RBAC / domains | RBAC changes, OPS-030 execution |
| Compatibility with governance baseline | ADR amendment, WP-B4 change |
| Module visibility rule (no UI role hardcode) | DEBT-DATA-001, OPS-031 repair |

---

## 2. What is Cabinet Profile

### 2.1. Definition

**Cabinet Profile** (RU: *функциональный профиль кабинета*) — a **declarative classification** of Position Cabinet **functional workspace shape**: which modules from the PC-MOD-001 catalog are **mandatory**, **conditional**, or **excluded** for Positions of that class.

Cabinet Profile is:

| Property | Description |
|----------|-------------|
| **Product-level** | Describes **what the workspace contains**, not how permissions are enforced |
| **Declarative** | A named profile record with module manifest — not imperative code per Position |
| **Stable across occupants** | Bound to **Cabinet / Position**, not to current Person (INV-B4-001) |
| **Reclassifiable** | Organization may change a Position's profile when function changes — audited event in Cabinet History |

### 2.2. What Cabinet Profile is NOT

| Concept | Why it is not Cabinet Profile |
|---------|-------------------------------|
| **RBAC / effective permissions** | Permissions govern **actions inside** modules; Profile governs **which modules exist** in the workspace |
| **Platform Role** (`public.roles`, `users.role_id`) | Legacy **authentication-era** operational center; as-is routing artifact — not target workspace classifier (ARCH-001 §5.4) |
| **Permission Domain** (ACCESS-001 PD-5.x) | Organizational **permission class** for contour → Template binding — orthogonal policy layer |
| **Permission Template** | **Configuration component inside Cabinet** — gates permitted actions; does not replace module catalog |
| **UI hardcode** | Route visibility must **derive from** Profile (+ Template + future config) — not from `if (role === …)` in frontend |
| **Person / Employee type** | Profile follows **Position function**, not individual Person traits |
| **Separate workspace entity** | Profile is metadata **of** Position Cabinet — not a second container |

### 2.3. Module manifest notation

Each profile declares modules using PC-MOD-001 IDs:

| Manifest flag | Meaning |
|---------------|---------|
| **Required** | Module **must** be active when Profile is assigned; core product surface |
| **Conditional** | Module **may** be active — depends on org policy, Template, or submodule config |
| **Excluded** | Module **must not** appear as cabinet module for this Profile (may still exist as platform link outside Cabinet) |
| **Shell (T3)** | Employee-owned modules shown in cabinet context — **default on** for occupied Cabinets unless policy disables |

**Module ID shorthand** (maps to PC-MOD-001 §3):

| ID | Module |
|----|--------|
| `tasks` | Задачи |
| `kpi` | KPI |
| `dashboards` | Дашборды |
| `reports` | Отчёты |
| `journals` | Журналы |
| `docs` | Документы функции |
| `analytics` | Аналитика и статистика |
| `team` | Команда |
| `hr` | Кадровые процессы |
| `history` | История кабинета |
| `notify` | Уведомления |
| `education` | Образование (T3) |
| `competency` | Развитие компетенций (T3) |

---

## 3. Why Cabinet Profile is needed

| Problem without profiles | How profiles resolve |
|--------------------------|----------------------|
| Per-Position bespoke UI logic | Positions **inherit** a named profile manifest |
| Platform Role drives navigation | **Profile + Template** drive module visibility; Role remains transitional |
| «Director screen» vs «nurse screen» as separate products | **One Position Cabinet model**, different **profile compositions** |
| T2 modules ambiguously «conditional» | Profile makes **explicit** which T2 modules apply to each function class |
| Permission Template overloaded as product definition | Template **gates**; Profile **composes** — separation of concerns |

**Design goal:** Position Cabinet remains the **single persistent workspace** model (GLOSS-B4-001); profiles prevent fragmentation into special-purpose interfaces.

---

## 4. Initial profile catalog

Eight **initial** profiles are proposed. IDs are **conceptual registry codes** — not database keys.

| Profile ID | Name (EN) | Name (RU) |
|------------|-----------|-----------|
| **PC-PROF-EXEC** | Executive / Director Cabinet | Кабинет руководителя / директора |
| **PC-PROF-DEPUTY** | Deputy / Management Cabinet | Кабинет заместителя / управленческий |
| **PC-PROF-LINE** | Line Head Cabinet | Кабинет линейного руководителя |
| **PC-PROF-EXPERT** | Expert Cabinet | Кабинет эксперта |
| **PC-PROF-SPEC** | Specialist / Executor Cabinet | Кабинет специалиста / исполнителя |
| **PC-PROF-ADMIN** | Administrative / Support Cabinet | Кабинет административной поддержки |
| **PC-PROF-HR** | HR Function Cabinet | Кабинет кадровой функции |
| **PC-PROF-QM** | Quality Management Cabinet | Кабинет управления качеством |

**Assignment rule (conceptual):** each org-unique Position receives **exactly one** Cabinet Profile at creation or HR reclassification. Profile change **does not** recreate Cabinet (INV-B4-001).

---

## 5. Profile specifications

Common fields for all profiles:

| Field | Common rule |
|-------|-------------|
| **Owner semantics** | Position-owned modules persist per GLOSS-B4-001 §5; T3 modules per §6 |
| **Lifecycle** | Profile assignment co-extensive with Position unless reclassified; Cabinet persists through vacancy |
| **On occupant change** | Profile **unchanged**; module contents persist; T3 follows new Owner's Employee record |
| **Permission Template link** | Profile declares **expected** Template family; Template **gates actions** within enabled modules — see §6.1 |
| **Explicit exclusions (all profiles)** | Platform Account, Auth, HR master data, Global Admin, Reference data catalogs, Personal File editor, System Health — PC-MOD-001 §5.2 |

---

### 5.1. PC-PROF-EXEC — Executive / Director Cabinet

| Field | Content |
|-------|---------|
| **Назначение** | Top-level **organizational leadership** workspace: executive oversight, strategic monitoring, approval-oriented task surface, org-wide or institution-wide situational picture |
| **Типовые должности** | Директор; исполняющий обязанности директора; генеральный директор (single-tenant org executive) |
| **Required modules** | `tasks`, `kpi`, `dashboards`, `reports`, `history`, `notify` |
| **Conditional modules** | `team` (executive subtree / institution scope per ACCESS-002), `analytics` (executive roll-ups), `docs` (regulatory / strategic), `hr` (**кадровое решение** initiation/approval surface — **not** HR processing execution) |
| **Shell (T3)** | `education`, `competency` — default on for occupied executive |
| **Excluded modules** | `journals` (operational shift logs — line/clinical), full `hr` **processing** execution (PD-5.2 — ACCESS-001 P5/P6) |
| **Template relationship** | Expects executive Template family; **must not** default-map to `SYSADMIN_CABINET` or `HR_ENROLLMENT_MANAGER` (ACCESS-001 P4/P5/P7) |
| **Not included** | System administration, HR enrollment execution, line clinical journals, platform ops |

**ACCESS alignment:** Director contour `(1, 78, 62)` — `SYSADMIN_CABINET` **rejected**; separate PD-5.1 class **not yet ratified** (DEBT-B1-001). Profile declares **product surface** for executive HR **decisions** without substituting permission policy.

---

### 5.2. PC-PROF-DEPUTY — Deputy / Management Cabinet

| Field | Content |
|-------|---------|
| **Назначение** | **Cross-functional management** and administrative coordination: deputy executives, institution-wide oversight without full executive authority scope |
| **Типовые должности** | Заместитель директора; зам по административным вопросам `(1, 78, 77)`; функциональные заместители |
| **Required modules** | `tasks`, `kpi`, `dashboards`, `reports`, `history`, `notify` |
| **Conditional modules** | `team` (assigned subtree per ACCESS-002), `analytics` (scoped roll-ups), `docs`, `hr` (**oversight / initiation** — PD-5.3 visibility class, not PD-5.2 processing) |
| **Shell (T3)** | `education`, `competency` |
| **Excluded modules** | `journals` (unless dual-classified Position), `hr` as **enrollment execution** (PD-5.2 — not default for `(78, 77)`) |
| **Template relationship** | Deputy admin contour likely PD-5.3 (**DEBT-B1-004** — code not ratified); Profile independent of transitional code debt |
| **Not included** | HR master data admin, sysadmin API, line-department operational journals by default |

**ACCESS alignment:** WP-B4 ratified PD-5.3 for `(1, 78, 77)`; Profile compatible — HR module is **oversight**, not processing.

---

### 5.3. PC-PROF-LINE — Line Head Cabinet

| Field | Content |
|-------|---------|
| **Назначение** | **Line management** of org subtree: department/section daily operations, team coordination, operational KPI of the unit |
| **Типовые должности** | Заведующий отделением; заведующий службой; начальник участка; руководитель структурного подразделения |
| **Required modules** | `tasks`, `kpi`, `dashboards`, `reports`, `history`, `team`, `notify` |
| **Conditional modules** | `journals` (department operational logs), `analytics` (subtree scope), `docs` (department SOPs), `hr` (**initiation / line informed** — §5.4 boundary, not HR processing) |
| **Shell (T3)** | `education`, `competency` |
| **Excluded modules** | `hr` as **PD-5.2 processing** (`HR_ENROLLMENT_MANAGER` — ACCESS-001 P9), org-wide executive analytics |
| **Template relationship** | Line Template codes (e.g. department-head variants); **no** `HR_ENROLLMENT_MANAGER` baseline |
| **Not included** | Institution-wide team view (unless ACCESS-002 widens scope), HR enrollment execution |

**ACCESS alignment:** Line head contours **rejected** for `HR_ENROLLMENT_MANAGER`; Profile **excludes** HR processing module actions — consistent with P9.

---

### 5.4. PC-PROF-EXPERT — Expert Cabinet

| Field | Content |
|-------|---------|
| **Назначение** | **Expert / methodological / supervisory** function without primary line-management duty: deep domain work, audits, expert conclusions, cross-unit advisory tasks |
| **Типовые должности** | Госпитальный эксперт; методист; ведущий специалист-эксперт; аудитор функции (non-QM-dedicated) |
| **Required modules** | `tasks`, `kpi`, `dashboards`, `reports`, `history`, `notify` |
| **Conditional modules** | `analytics` (domain-scoped), `docs` (regulatory / methodological library), `journals` (expert examination logs), `team` (**only if** ACCESS-002 assigns coordination responsibility — default **excluded**) |
| **Shell (T3)** | `education`, `competency` — often **required by compliance** for expert roles |
| **Excluded modules** | `team` as default line-management surface, `hr` processing, executive org-wide analytics |
| **Template relationship** | Expert Template family (e.g. `QM_HOSP`-like codes for clinical experts **without** conflating Profile with Template code) |
| **Not included** | Subtree management dashboard (unless dual profile or ACCESS-002 assignment), HR execution |

---

### 5.5. PC-PROF-SPEC — Specialist / Executor Cabinet

| Field | Content |
|-------|---------|
| **Назначение** | **Primary operational execution**: individual contributor performing position duties with minimal management surface — the default profile for most staffing units |
| **Типовые должности** | Ординатор; медсестра; экономист; инженер; специалист; исполнитель регламентных задач |
| **Required modules** | `tasks`, `reports`, `history`, `kpi`, `dashboards`, `notify` |
| **Conditional modules** | `journals` (role-mandated logs), `docs` (job instructions), `analytics` (personal/position scope only) |
| **Shell (T3)** | `education`, `competency` |
| **Excluded modules** | `team`, `hr` (except self-service requests if org policy adds — default excluded), deep `analytics` |
| **Template relationship** | Task-executor Template family; task-only contours per ACCESS-001 §7 |
| **Not included** | Management team views, HR processing, executive dashboards |

**Note:** Closest match to current UI skeleton scope (`/tasks`, `/dashboards`, `/education`).

---

### 5.6. PC-PROF-ADMIN — Administrative / Support Cabinet

| Field | Content |
|-------|---------|
| **Назначение** | **Administrative support** and back-office operations: document flow support, scheduling assistance, registry functions — execution-heavy, low management |
| **Типовые должности** | Секретарь; делопроизводитель; регистратор; офис-администратор; помощник (non-executive) |
| **Required modules** | `tasks`, `reports`, `history`, `dashboards`, `notify` |
| **Conditional modules** | `docs` (document templates / office library), `journals` (office logs), `kpi` (lightweight throughput metrics) |
| **Shell (T3)** | `education`, `competency` |
| **Excluded modules** | `team`, `analytics` (deep), `hr` processing, `journals` (clinical) |
| **Template relationship** | Support / admin Template family |
| **Not included** | Line management, QM audit instruments, HR execution |

---

### 5.7. PC-PROF-HR — HR Function Cabinet

| Field | Content |
|-------|---------|
| **Назначение** | **HR operational function** workspace: кадровое оформление, enrollment execution, HR document preparation — the duty shell of HR-service Positions |
| **Типовые должности** | Руководитель отдела кадров `(1, 73, 86)`; специалист отдела кадров; HR enrollment officer |
| **Required modules** | `tasks`, `kpi`, `dashboards`, `reports`, `history`, `hr`, `docs`, `notify` |
| **Conditional modules** | `analytics` (HR operational metrics), `journals` (HR processing log) |
| **Shell (T3)** | `education`, `competency` |
| **Excluded modules** | `team` (line subtree management — ACCESS-002 separate), clinical `journals`, executive **кадровое решение** approval (PD-5.1 — not HR processing) |
| **Template relationship** | PD-5.2 / `HR_ENROLLMENT_MANAGER` **candidate** for `(73, 86)` — WP-B4 ratified class; Profile aligns with **processing**, not PD-5.1 |
| **Not included** | HR **master data** administration (Person/Employment editor as org admin), line management, QM audits |

**ACCESS alignment:** WP-B4 ratified PD-5.2 for HR head contour; Profile **requires** `hr` module — consistent. Transitional code debt (DEBT-B1-001) does not change Profile definition.

---

### 5.8. PC-PROF-QM — Quality Management Cabinet

| Field | Content |
|-------|---------|
| **Назначение** | **Quality management** function: QM tasks, audits, compliance monitoring, expert review workflows — OВЭиПД / quality department Positions |
| **Типовые должности** | Руководитель ОВЭиПД `(1, 72, 85)`; госпитальный/амбulatorный QM эксперт; QM coordinator |
| **Required modules** | `tasks`, `kpi`, `dashboards`, `reports`, `history`, `analytics`, `docs`, `notify` |
| **Conditional modules** | `journals` (audit / inspection logs), `team` (**QM functional scope** — see OQ-PROF-003; not default org subtree) |
| **Shell (T3)** | `education`, `competency` — frequently mandatory for QM roles |
| **Excluded modules** | `hr` processing (PD-5.2), executive institution-wide `team` by default, sysadmin |
| **Template relationship** | QM Template family (`QM_HOSP`, `QM_AMB`, `QM_HEAD` — ARCH-001 examples); ACCESS-001 `(72, 85)` pending separate QM policy |
| **Not included** | HR enrollment, line-department head management (unless dual-classified Position) |

---

## 6. Profile summary matrix

| Module | EXEC | DEPUTY | LINE | EXPERT | SPEC | ADMIN | HR | QM |
|--------|:----:|:------:|:----:|:------:|:----:|:-----:|:--:|:--:|
| `tasks` | R | R | R | R | R | R | R | R |
| `kpi` | R | R | R | R | R | C | R | R |
| `dashboards` | R | R | R | R | R | R | R | R |
| `reports` | R | R | R | R | R | R | R | R |
| `history` | R | R | R | R | R | R | R | R |
| `notify` | R | R | R | R | R | R | R | R |
| `team` | C | C | R | X/C | X | X | X | C |
| `analytics` | C | C | C | C | C | X | C | R |
| `docs` | C | C | C | C | C | C | R | R |
| `journals` | X | X | C | C | C | C | C | C |
| `hr` | C† | C‡ | C§ | X | X | X | R | X |
| `education` | S | S | S | S | S | S | S | S |
| `competency` | S | S | S | S | S | S | S | S |

**Legend:** R = Required · C = Conditional · X = Excluded · S = Shell (T3, default on)

| Symbol | `hr` module meaning |
|--------|---------------------|
| † | Executive **decision** surface (PD-5.1 target — policy not ratified) |
| ‡ | HR **oversight** (PD-5.3) |
| § | Line **initiation / informed** (§5.4 boundary — not processing) |

---

## 7. Relationship model

### 7.1. Cabinet Profile vs Permission Template

| Dimension | Cabinet Profile | Permission Template |
|-----------|-----------------|---------------------|
| **Layer** | Product composition | Configuration inside Cabinet |
| **Question answered** | *Which modules exist?* | *Which actions are permitted inside modules?* |
| **Binding** | Position / Cabinet metadata | Component of Cabinet (ARCH-001 §3.5; ADR-050) |
| **Changes on occupant change** | **No** | **No** (INV-B4-001) |
| **Typical coupling** | Profile **PC-PROF-HR** expects Template permitting PD-5.2 actions | Template **does not** define module list alone |

**Rule CP-T1:** Profile and Template **SHOULD align** (HR Profile + HR Template family). Mismatch is **allowed** during transition — Template may restrict actions in modules Profile exposes (safe); Profile **must not** expose modules that Template cannot legally support (unsafe — product/policy review).

**Rule CP-T2:** Permission Template **must not** be misused as the sole module catalog — that overloads RBAC with product composition (anti-pattern noted in PC-MOD-001 §3.14).

### 7.2. Cabinet Profile vs Platform Role

| Dimension | Cabinet Profile | Platform Role (as-is) |
|-----------|-----------------|------------------------|
| **Status in target model** | **Primary** workspace classifier | **Transitional** routing / legacy enforcement |
| **Scope** | Per Position Cabinet | Global catalog row + `users.role_id` |
| **UI visibility** | **Must derive from Profile** | **Must not** hardcode nav from Role |

**Rule CP-R1:** Platform Role **may correlate** with Profile during migration (e.g. `QM_HOSP` ↔ PC-PROF-EXPERT or PC-PROF-QM) — correlation is **ops mapping**, not identity.

**Rule CP-R2 (mandatory):** **Forbidden:** `if (user.role === 'QM_HEAD') showDashboard` in UI. **Required:** module visibility from **resolved Cabinet Profile** (+ Template effective permissions).

### 7.3. Cabinet Profile vs Permission Domain

| Dimension | Cabinet Profile | Permission Domain (ACCESS-001) |
|-----------|-----------------|-------------------------------|
| **Layer** | Product / functional | Organizational permission policy |
| **Governance** | Product architecture | Review Board ratification (WP-B1…B4) |
| **Example** | PC-PROF-HR **requires** `hr` module | PD-5.2 **permits** HR processing actions on contour |

**Rule CP-D1:** Permission Domain **does not define** Profile — but Profile **must not contradict** ratified domain boundaries (e.g. LINE Profile excludes PD-5.2 processing).

**Rule CP-D2:** ACCESS-002 management responsibilities **may enable** conditional modules (e.g. `team`) — responsibility is **not** a Profile substitute; implementation joins Profile manifest with ACCESS-002 scope at runtime (future — not specified here).

### 7.4. Cabinet Profile vs Position

```text
Position ──1:1──► Position Cabinet
                      │
                      ├── cabinet_profile_id  (conceptual — PC-PROF-*)
                      ├── module_composition   (derived from profile + overrides)
                      └── permission_template  (configuration)
```

| Rule | Statement |
|------|-----------|
| **CP-P1** | One Cabinet holds **one active Profile** at a time |
| **CP-P2** | Profile reassignment **preserves** Cabinet identity and position-owned module data |
| **CP-P3** | Position **title rename** does not change Profile unless function class changes |
| **CP-P4** | Position **liquidation** ends Cabinet — Profile ends with it |

### 7.5. Cabinet Profile vs UI navigation

| Layer | Responsibility |
|-------|----------------|
| **Cabinet Profile** | Declares **available modules** (nav items / sections eligibility) |
| **Permission Template** | Declares **reachable actions** within each module |
| **UI design** | Maps modules to tabs, sidebar, or hubs — **downstream** of Profile |
| **Personal UI Shell** | Aggregates multiple Cabinets — may show different profiles per active Cabinet context |

**Rule CP-U1:** Navigation is a **projection** of Profile + Template + active Cabinet context — not a hardcoded route table per Platform Role.

**Rule CP-U2:** T3 shell modules (`education`, `competency`) appear in navigation when Profile includes Shell flag **and** occupant has Employee record.

---

## 8. Module visibility rule (normative)

The following rule is **binding for all future implementation** of Position Cabinet product surfaces:

> **MOD-VIS-001:** Module visibility **SHALL NOT** be determined by hardcoded Platform Role checks, `users.role_id` branching, or ad hoc contour ID tests in UI code. Module visibility **SHALL** be derived from the **resolved Cabinet Profile** (module manifest), **effective Permission Template** constraints, and a **future configuration model** that exposes this resolution to the client.

| Allowed input to visibility | Forbidden as primary visibility driver |
|-----------------------------|--------------------------------------|
| Resolved `PC-PROF-*` manifest | `if (role === 'HR_ENROLLMENT_MANAGER')` |
| Template-gated module action map | Hardcoded `(org_unit_id, position_id)` in React components |
| Explicit org policy overrides (audited) | Duplicated per-screen role lists |
| Active Cabinet context from ADR-051 resolver | `users.role_id` alone |

**Rationale:** Hardcoded role checks recreate the as-is anti-pattern (ARCH-001 §5.4; access-rbac assessment R2) and break INV-B4-001 when Role and Cabinet diverge.

**Transition note:** Legacy Role-based visibility **may persist temporarily** outside Position Cabinet shell — but **must not expand**; Cabinet shell migration replaces Role checks with Profile resolution.

---

## 9. Compatibility review

| Source | Compatibility | Notes |
|--------|---------------|-------|
| **WP-B4** | **Full** | Profiles respect INV-B4-001…003; occupant change does not rebind Profile; acting uses target Cabinet's Profile |
| **GLOSS-B4-001** | **Full** | Position-owned modules persist per §5; T3 per §6; Profile bound to Cabinet not Person |
| **PC-MOD-001** | **Full** | Profiles reference only registered modules; T1/T2/T3 tiers preserved |
| **ACCESS-001** | **Full with policy debt awareness** | LINE/EXEC exclude wrong HR classes; HR Profile aligns PD-5.2; PD-5.1 executive `hr` surface conditional until DEBT-B1-001 closed |
| **ACCESS-002** | **Full (orthogonal)** | `team` / `analytics` scope driven by management responsibilities — Profile declares module; ACCESS-002 declares subtree |
| **ADR-050** | **Full** | 1:1 Position ↔ Cabinet; Profile metadata on Cabinet; no new entity |
| **ADR-051** | **Full** | Resolver returns accessible Cabinets; Profile resolution is **per Cabinet** after access granted |
| **Architecture Freeze** | **Full** | No Accepted ADR amendment; no new domain entities; derived from Accepted baseline |

**Explicitly not mixed with:**

| Track | Separation |
|-------|------------|
| **DEBT-DATA-001** | Data repair — not Profile design |
| **OPS-031** | Ops execution — not Profile catalog |
| **WP-B4 attestation** | Profile doc does not close or reopen WP-B4 |

---

## 10. Profile assignment (conceptual)

| Event | Profile behaviour |
|-------|-------------------|
| Position + Cabinet creation | Default Profile selected from **function class** (HR position → PC-PROF-HR) |
| Position function reclassification | Profile updated; **module data persists**; History records event |
| Permission Template rebind | Template changes; Profile **unchanged** unless coordinated policy event |
| Acting assignment | Acting Person accesses **target Cabinet's Profile** — not primary Cabinet's |
| Vacancy | Profile **remains** on Cabinet; modules may be empty or policy-suspended (Business Policy) |

**Default mapping heuristic (illustrative — OQ-PROF-001):**

| Organization function signal | Suggested Profile |
|------------------------------|-------------------|
| Executive / director title in org structure | PC-PROF-EXEC |
| Deputy / vice title | PC-PROF-DEPUTY |
| Department head with subtree responsibility | PC-PROF-LINE |
| QM / OВЭиПД unit | PC-PROF-QM |
| HR department unit | PC-PROF-HR |
| Expert / senior specialist without head duty | PC-PROF-EXPERT |
| Administrative support title | PC-PROF-ADMIN |
| **Default fallback** | PC-PROF-SPEC |

Heuristic **does not** authorize automated assignment implementation.

---

## 11. Extensibility

New profiles **SHOULD** be registered with:

1. Profile ID (`PC-PROF-*`)
2. Purpose and typical Positions
3. Full module manifest (R / C / X / S)
4. Template family expectation
5. ACCESS domain boundary statement
6. Explicit exclusions

New profiles **must not** violate MOD-VIS-001 or PC-MOD-001 ownership rules.

**Dual profiles:** A Position **should not** hold two Profiles simultaneously. Dual-function Positions (e.g. head who is also QM lead) use **one primary Profile** + conditional modules — or org policy splits into two Positions (preferred architecturally).

---

## 12. Open questions

| ID | Question | Default stance | Blocks baseline? |
|----|----------|----------------|------------------|
| **OQ-PROF-001** | Who is authoritative for Profile assignment — HR, org admin, or automated from org structure? | HR + org admin governance; no auto-bind without approval | **No** |
| **OQ-PROF-002** | Should Profile be stored on Position or Cabinet record at implementation? | Cabinet metadata (follows ADR-050 storage of Template) | **No** |
| **OQ-PROF-003** | PC-PROF-QM `team` module — QM functional filter vs org subtree? | Conditional; scope = **QM task domain**, not line subtree by default | **No** |
| **OQ-PROF-004** | PC-PROF-EXEC `hr` module before PD-5.1 code ratification — show read-only or hide? | Conditional module **declared**; surface gated by Template until PD-5.1 approved | **No** |
| **OQ-PROF-005** | Org-specific Profile variants (e.g. `PC-PROF-SPEC-CLINICAL`) — central catalog vs tenant extension? | Start with **8 global profiles**; extensions via conditional flags first | **No** |
| **OQ-PROF-006** | Relationship to ADR-046 allowed-positions / title taxonomy? | Title catalog informs **suggested** Profile; org-unique Position holds **assigned** Profile | **No** |

Open questions **do not block** using this document as conceptual baseline for product and implementation planning.

---

## 13. Review Board and baseline usage

| Question | Assessment |
|----------|------------|
| **Review Board required?** | **No** for conceptual baseline — PC-PROFILE-001 is **product architecture**, not organizational permission ratification. No ACCESS-001 §7 row changes proposed. |
| **Recommended review** | **Product owner + architecture steward** review for ACCESS alignment (§9) — lightweight, not full Review Board session |
| **Review Board trigger** | Required **only if** a profile manifest **contradicts ratified** PD class (e.g. requiring `HR_ENROLLMENT_MANAGER` actions on LINE Profile) or seeks policy exception |
| **Implementation baseline?** | **Yes** — suitable as **conceptual baseline** for profile registry design, resolver extension, and UI visibility model — after product owner acknowledgment |

**Distinction from WP-B4:** WP-B4 ratified **contour permission binding** and Persistent Workspace governance. PC-PROFILE-001 ratifies **nothing** — it catalogs product profiles for downstream design.

---

## 14. Explicit non-goals

| Non-goal | Note |
|----------|------|
| Implementation / API / schema | Deferred |
| UI navigation design | Deferred |
| RBAC / OPS-030 execution | Deferred |
| ADR / WP-B4 amendment | None |
| DEBT-DATA-001 / OPS-031 | Out of scope |
| Profile assignment automation | OQ-PROF-001 |

---

## 15. Downstream consumers

| Consumer | Usage |
|----------|-------|
| Profile registry (future) | Authoritative manifest store |
| Cabinet Access Resolver extension (future) | Return `cabinet_profile_id` with Cabinet |
| UI shell | MOD-VIS-001 compliance |
| Product roadmap | Prioritize modules per Profile |
| QM / HR subsystem design | Align surfaces with PC-PROF-HR, PC-PROF-QM |

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-06 | 0.1 | Initial draft — 8 profiles; relationship model; MOD-VIS-001; compatibility review |
