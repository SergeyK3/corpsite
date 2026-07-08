# PC-CONCEPT-001 — Unified Position Cabinet Concept

## Единая концепция Position Cabinet и Unified User Workspace

---

## Document metadata

| Field | Value |
|-------|-------|
| **ID** | PC-CONCEPT-001 |
| **Title (EN)** | Unified Position Cabinet Concept |
| **Title (RU)** | Единая концепция Position Cabinet |
| **Version** | **0.4 — Architecture Draft (review remediation)** |
| **Status** | **Architecture Draft** (not Approved; no runtime effect) |
| **Scope** | Conceptual architecture — Unified User Workspace, two-contour model, Self Visibility |
| **Normative inputs (read-only)** | [ARCH-001](../architecture/ARCH-001-position-permission-model.md); [ARCH-001 Foundation Summary](../architecture/ARCH-001-foundation-summary.md); [ARCHITECTURE_GOVERNANCE](../architecture/ARCHITECTURE_GOVERNANCE.md); [GLOSS-B4-001](../access/GLOSS-B4-001-position-cabinet-vocabulary.md); [ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md); [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md); [ADR-051](../adr/ADR-051-cabinet-access-resolution.md); [ADR-053](../adr/ADR-053-permission-template-binding-model.md); [PC-MOD-001](../access/PC-MOD-001-position-cabinet-functional-composition.md) |
| **Supersedes** | PC-CONCEPT-001 v0.3 (Architecture Draft) |
| **Runtime effect** | **None** — does not amend Accepted ADR or Reviewed ACCESS documents |

**Purpose:** построить **завершённую концептуальную модель** единого пользовательского рабочего пространства Corpsite HRIS — **Unified User Workspace** — и явно разделить её от доменной сущности **Position Cabinet**, не противореча Accepted baseline.

**Audience:** Architecture Review, product composition (PC-MOD-001), future ADR/amendment authors.

---

## 1. Executive summary

Corpsite принимает **единую точку входа** для аутентифицированного пользователя вместо классического разделения «портал сотрудника» и «рабочее место должности».

Ключевое архитектурное разделение (v0.2+, усилено v0.3–v0.4):

| Concept | Layer | Entity? | Role |
|---------|-------|---------|------|
| **Position Cabinet** | **Domain** | **Yes** | Долговременный domain container **должности** (1:1 с org-unique Position). Создаётся вместе с Position; переживает смену Person, vacancy и acting. Владеет position-owned данными и Permission Template. **Не** является UX shell. |
| **Unified User Workspace** | **Presentation / composition** | **No** | Composition shell после входа: **активный Work Context** + **Self Services**. Maps to **Personal UI Shell** / «личный кабинет» (ARCH-001 §8). **Не** владеет business data. |
| **Work Context** | **Session view** | **No** | Активное **session-level** представление **одного** Position Cabinet внутри UWS. Subsumes **Active Cabinet Context** (ADR-051 §7) plus UI module composition. **Не** владеет данными; не заменяет Cabinet. |
| **Self Visibility** | **Authorization principle** | N/A | Модель доступа Person к **собственным** данным. **Proposed** in this document — **not normative** until separate ADR/register (OQ-PC-001). Ортогональна ACCESS-001. |

**Canonical access chain** (Person/Employee → Cabinet; Work Context — последний UX-шаг):

```text
Person / Employee
    → Employment (Занятие должности)
    → Position
    → Position Cabinet          ← domain entity; persists
    → Work Context (in UWS)     ← session view; not an entity
```

Person / Employee **не получает** доступ к Position Cabinet напрямую. Доступ открывается через **активное Employment** (permanent Занятие должности) или **Acting Assignment** / иной documented delegated access overlay ([ADR-051](../adr/ADR-051-cabinet-access-resolution.md) — normative resolver, not restated here). **Exception grants** (`access_grants` and similar) may **extend** the effective permission set per ADR-051 R17 — they **do not** create a direct Person→Cabinet ownership or access path outside the resolver.

Пользователь **не переключается между порталами**. Он работает в **Unified User Workspace**, внутри которого:

1. **Work Context** — session-level view **одного** Position Cabinet, доступного через Employment или acting; **не** substitute для Cabinet.
2. **Self Services** — личные и кадровые services Person/Employee; **не** зависят от активного Work Context.

Position Cabinet **не агрегирует владение** доменными данными. **Workspace Composer** (концептуальный паттерн) только **компонует** представление модулей из независимых доменов.

---

## 2. Problem statement

### 2.1. Классическая HRIS-проблема

Традиционные системы разделяют:

- **Employee portal** — профиль, отпуска, обучение, кадровая история;
- **Manager / role workspace** — задачи, KPI, журналы, документы функции.

Это приводит к:

- дублированию навигации и UX-паттернов;
- потере контекста при переходе между «личным» и «рабочим»;
- смешению ownership (данные должности показываются как «личные» и наоборот);
- разрозненным моделям доступа (self-read vs admin-read).

### 2.2. Corpsite baseline constraint

Accepted architecture ([ARCH-001](../architecture/ARCH-001-position-permission-model.md), [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md), [GLOSS-B4-001](../access/GLOSS-B4-001-position-cabinet-vocabulary.md)) уже определила:

- Position Cabinet **принадлежит Position**, а не Person;
- operational backlog и position-owned history **переживают** смену занимающего;
- Platform User — только аутентификация;
- Effective permissions — через **Employment** (Занятие должности) → Position → Position Cabinet → Permission Template ([ADR-051](../adr/ADR-051-cabinet-access-resolution.md));

**Проблема v0.1 Draft:** формулировка «Position Cabinet = единое рабочее пространство пользователя» **конфликтовала** с «Position Cabinet = кабинет должности 1:1». v0.2 **снимает конфликт** введением **Unified User Workspace** как composition layer.

---

## 3. Scope

### 3.1. In scope

- Концептуальная модель Unified User Workspace;
- двухконтурная архитектура (Work Context / Self Services);
- Self Visibility как архитектурный принцип (proposed — non-normative);
- lifecycle и правила переключения Work Context;
- relationship matrix сущностей;
- architectural invariants, non-goals, open questions;
- рекомендации по downstream decomposition (без утверждения).

### 3.2. Out of scope

- SQL, API, UI implementation, маршруты, RBAC enforcement;
- amendment Accepted ADR или ACCESS-001;
- Permission Template binding rows;
- Personnel Orders MVP implementation;
- Cleanup Program.

---

## 4. Terminology

| Term (EN) | Term (RU) | Definition in this document |
|-----------|-----------|----------------------------|
| **Platform User** | Учётная запись | Техническая сущность аутентификации. Вне Cabinet. |
| **Person** | Персона | Канонический идентификатор человека (IIN, FIO). Вне Cabinet. |
| **Employee** | Сотрудник (операционная оболочка) | Операционное представление Person в HRIS-контуре. **Не** источник истины Employment. |
| **Employment** | **Занятие должности** | **Canonical HR fact:** Person occupies org-unique **Position** for a period (`person_assignments` / ADR-042). Opens access to Position Cabinet. **Primary term** per [ARCH-001 §3.2](../architecture/ARCH-001-position-permission-model.md) — **not** Russian «назначение» (avoids collision with task assignment and ADR-042 assignment semantics). |
| **Acting Assignment** | Исполнение обязанностей (и.о.) | Временный overlay доступа к **чужому** Cabinet без смены Cabinet Owner ([GLOSS-B4-001](../access/GLOSS-B4-001-position-cabinet-vocabulary.md) §4). |
| **Position** | Должность (org-unique) | Уникальная штатная единица в структуре. 1:1 с Position Cabinet. |
| **Position Cabinet** | Кабинет должности | **Domain entity:** долговременный container org-unique **Position** (1:1). Создаётся вместе с Position; переживает vacancy, acting и смену Person. Owner = Position/Organization. **Not** a UX shell. |
| **Unified User Workspace** | Единое пользовательское рабочее пространство | **Composition shell** after login: Work Context view + Self Services. **Not a domain entity.** **Does not own** business data. Conceptual successor to «личный кабинет» / **Personal UI Shell** (ARCH-001 §8). |
| **Work Context** | Рабочий контур | **Session-level active view** of **one** Position Cabinet inside UWS. **Not a domain entity.** **Does not own** data — ownership remains with Position Cabinet. **Includes** ADR-051 **Active Cabinet Context** for scoped operations **plus** presentation of Work Context modules. |
| **Self Services** | Self Services | Контур личных/employee-owned сервисов Person в UWS. **Не** переключается при смене Work Context. |
| **Self Visibility** | Self Visibility | **Proposed** принцип self-read доступа Person к собственным данным. **Not normative** until OQ-PC-001 resolved. |
| **Workspace Composer** | Workspace Composer | Концептуальный паттерн композиции модулей в Unified User Workspace без ownership данных. |
| **Cabinet History** | История кабинета | Position-owned audit trail деятельности в должности. |
| **Personnel History** | Кадровая история | Employee-owned хронология HR-событий Person. |
| **Cabinet Owner** | Владелец кабинета / постоянный занимающий | **Role relation:** Person with active **Employment** on Position linked to Cabinet — not an entity; Cabinet remains Position-owned ([GLOSS-B4-001](../access/GLOSS-B4-001-position-cabinet-vocabulary.md) §3). |

**Usage rules:**

1. Position Cabinet **не переопределяется** этим документом. Unified User Workspace **не вводит** новую таблицу или ADR-сущность.
2. **Employment / Занятие должности** — единственный канонический термин для permanent occupancy. Russian **«назначение»** для этой сущности **не используется** (ARCH-001 §3.2, §15.0).
3. **Persistent Workspace** (GLOSS-B4-001 §2) = Position Cabinet at **domain** level — **not** Unified User Workspace.

### 4.1. Baseline term mapping (PC-CONCEPT ↔ Accepted architecture)

Explicit mapping prevents entity collapse in downstream documents (closes Architecture Review **M-02**; relates to **OQ-B4-001**, **OQ-PC-010**):

| PC-CONCEPT-001 term | Accepted baseline term | Normative source | Notes |
|---------------------|------------------------|------------------|-------|
| **Unified User Workspace** | Personal UI Shell; «личный кабинет» (UI entry) | ARCH-001 §2.3, §8; PC-MOD-001 §2.1 | Presentation aggregation — **not** Position Cabinet |
| **Work Context** | **Active Cabinet Context** (runtime selection) | ADR-051 §7.1–§7.4 | Work Context **adds** module presentation/navigation; does **not** replace resolver semantics |
| **Work Context view lifecycle** | Session-scoped Cabinet selection | ADR-051 §7.2; OQ-B4-001 | Distinct from **Cabinet** / Position lifecycle |
| **Employment** | Занятие должности; `person_assignments` | ARCH-001 §3.2; ADR-050 §4.2; GLOSS-B4-001 §3 | Primary access path to Cabinet |
| **Self Services** | Employee-owned views in Personal UI Shell | ARCH-001 §8; GLOSS-B4-001 §6 | Orthogonal to active Cabinet selection |
| **Persistent Workspace** | Position Cabinet (domain characterisation) | GLOSS-B4-001 §2; ADR-050 | **≠** UWS |

**Effective permissions note (ADR-051 §7.4):** switching Work Context changes **presentation and cabinet-scoped operations** — it does **not** change the **Effective Permission Set** (union across all accessible Cabinets at time T). Global permission checks use the union; object-bound / cabinet-scoped checks require the active Work Context Cabinet ∈ accessible set.

---

## 5. Entity model and distinctions

### 5.1. Platform User vs Person vs Employee

```text
Platform User ──authenticates──► Person
                                      │
                                      ├──► Employee (HR operational shell)
                                      │
                                      └──► Self Services scope (always Person-centric)
```

| Entity | Owns permissions? | Owns operational backlog? | Owns personnel history? |
|--------|--------------------|-----------------------------|-------------------------|
| **Platform User** | No (auth only) | No | No |
| **Person** | No (access via Employment) | No | Yes (Personnel History) |
| **Employee** | No | No | Operational view of Person HR data |

### 5.2. Position vs Employment vs Position Cabinet

**Access rule:** Person / Employee reaches a Position Cabinet **only through** Employment (Занятие должности) or Acting Assignment — never by direct Person→Cabinet binding. Documented **exception overlays** extend permissions per ADR-051 R17 — they do **not** substitute for Employment/acting access paths.

```text
Person / Employee
  │
  ├── Employment (Занятие должности) ──► Position ── 1:1 ──► Position Cabinet
  │                                              │
  │                                              └── Permission Template
  │
  └── Acting Assignment (overlay) ──► delegated access to another Position Cabinet
                                              (Cabinet Owner unchanged)
```

| Relation | Meaning | Changes when occupant changes? |
|----------|---------|--------------------------------|
| **Position ↔ Position Cabinet** | Structural 1:1; co-created | No — same Cabinet entity |
| **Employment** | HR fact: Person occupies Position for period; **grants access** to Cabinet | Employment ends; **Cabinet persists** |
| **Cabinet Owner** | Person with active **Employment** on Position (permanent occupancy) | Owner identity changes; **Cabinet and position-owned data do not** |
| **Vacancy** | No active Employment / Cabinet Owner | Cabinet **still exists**; no ordinary user Work Context |
| **Acting** | Temporary access overlay to target Cabinet | Target Cabinet **unchanged**; acting Person gets switchable Work Context only |

### 5.3. Position Cabinet vs Unified User Workspace vs Work Context

| Aspect | Position Cabinet | Unified User Workspace | Work Context |
|--------|------------------|------------------------|--------------|
| **Nature** | **Domain entity** | Composition / UX shell | **Session-level view** (not an entity) |
| **Entity?** | **Yes** | **No** | **No** |
| **Data owner?** | **Yes** — position-owned data | **No** | **No** — ownership stays with Cabinet |
| **Cardinality** | One per Position | One shell per authenticated session | One **active** view at a time |
| **Persistence** | Co-extensive with Position; **survives** vacancy, acting, occupant change | Session + UI preference only | Session-scoped selection of which Cabinet is «active» |
| **Created** | Together with org-unique Position ([ADR-050](../adr/ADR-050-organization-position-cabinet-model.md)) | On post-login composition | When user (or policy) selects active Cabinet in UWS |
| **Relation to access** | Target of Employment / acting access | Presents accessible Cabinets | **View over** one accessible Cabinet |
| **Baseline alias** | Persistent Workspace (domain) | Personal UI Shell | Active Cabinet Context (+ UI modules) |

**Anti-confusion rules (v0.3+, retained v0.4):**

| Misread | Correct reading |
|---------|-----------------|
| Position Cabinet = UX shell | **Rejected.** UWS is the shell; Cabinet is domain container. |
| Position Cabinet = Work Context | **Rejected.** Work Context is a **view** of one Cabinet in a session. |
| Work Context owns backlog / KPI | **Rejected.** Position Cabinet owns position-owned data. |
| UWS owns business data | **Rejected.** UWS / Composer route to domain owners only. |
| Self Services follow Work Context switch | **Rejected.** Self Services remain Person/Employee-scoped (§7.2, INV-PC-004). |
| Persistent Workspace = UWS | **Rejected.** Persistent Workspace = Position Cabinet domain characterisation (GLOSS-B4-001 §2). |

**Clarification v0.2 (retained):** Position Cabinet **является** кабинетом должности в domain sense. **Unified User Workspace** — composition shell пользователя. **Work Context** — не substitute для Cabinet, а активное представление одного Cabinet внутри UWS, доступного через Employment или acting.

---

## 6. Unified User Workspace — purpose and lifecycle

### 6.1. Purpose

Unified User Workspace is a **composition shell only** — not a domain entity, not a data owner.

It exists to:

1. Provide **one post-login entry** for all Corpsite HRIS user activities;
2. **Compose** Work Context (session view of one Position Cabinet) and Self Services without merging ownership;
3. Preserve **Accepted invariants** (Cabinet belongs to Position; access via Employment; Employee data follows Person);
4. Reduce context switching while keeping **authorization boundaries** explicit.

**Work Context** inside UWS is likewise **not an entity** — it is the **active session-level view** of one Position Cabinet the Person may access through Employment or acting, aligned with ADR-051 **Active Cabinet Context** (§4.1).

### 6.2. Lifecycle

| Phase | Behaviour (conceptual) |
|-------|------------------------|
| **Pre-auth** | No workspace — login only |
| **Post-auth resolution** | Resolve Person → active **Employments** → acting overlays → set of **accessible Position Cabinets** ([ADR-051](../adr/ADR-051-cabinet-access-resolution.md) — normative for access, not restated here) |
| **Workspace activation** | UWS shell opens; select **default Work Context** = session view of primary Employment's Cabinet (policy TBD — OQ-PC-003; ADR-051 §7.3 precedence applies) |
| **Active use** | User operates in Work Context modules (Cabinet-scoped) and Self Services (Person-scoped) within same shell |
| **Context switch** | User selects another accessible Cabinet → **Work Context view** changes; **Position Cabinets** unchanged; Self Services unchanged; **Effective Permission Set unchanged** (ADR-051 §7.4) |
| **Employment end** | Cabinet access via that Employment closes; **Cabinet entity and history persist**; switch Work Context if needed |
| **Vacancy on Position** | **Cabinet persists**; ordinary occupant Work Context unavailable until new Employment or acting overlay |
| **Leave / sick leave** | Employment may remain active; **access restriction** may apply per business policy — does **not** change Cabinet lifecycle (ARCH-001 §4.7.1) |
| **Logout** | UWS session and active Work Context view end; Cabinets persist |

### 6.3. Workspace Composer (pattern)

**Workspace Composer** is the conceptual mechanism that:

- **Selects** which modules appear in navigation for current Work Context + Self Services;
- **Routes** user actions to authoritative domain services;
- **Does not** store authoritative business data;
- **Does not** replace Permission Template or ACCESS-001 evaluation.

Boundary:

| Composer responsibility | Domain responsibility |
|-------------------------|----------------------|
| Navigation, layout, module visibility gates | CRUD, workflow, retention, audit |
| Active Work Context selection (which Cabinet is «active» in session) | **Position Cabinet** stores backlog, KPI, journals |
| Presenting Self Services in UWS shell | Employee profile, education records, personal notification inbox |

Reference: module catalog in [PC-MOD-001](../access/PC-MOD-001-position-cabinet-functional-composition.md) describes **what** can be composed; PC-CONCEPT-001 describes **how contours relate** (§7.4).

---

## 7. Two-contour model

Unified User Workspace comprises **two orthogonal contours**:

```text
Unified User Workspace (composition shell — not an entity)
├── Work Context   session-level view of ONE Position Cabinet (not an entity; not a data owner)
└── Self Services  Person / Employee–scoped (independent of active Work Context)
```

### 7.1. Work Context (Рабочий контур)

| Dimension | Definition |
|-----------|------------|
| **Nature** | **Session-level active view** — not a domain entity; includes ADR-051 Active Cabinet Context |
| **Purpose** | Present operational modules of **one** Position Cabinet the Person may access via **Employment** or acting |
| **Data owner** | **Position / Position Cabinet** — Work Context **does not own** data ([GLOSS-B4-001](../access/GLOSS-B4-001-position-cabinet-vocabulary.md) §5) |
| **Lifecycle (view)** | Exists for session while Cabinet is selected as active; **Cabinet lifecycle** is independent (co-extensive with Position) |
| **Visibility** | Person must have **accessible Cabinet** via Employment or acting; module visibility further gated by Permission Template + [ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md) for others' data |
| **Authorization model** | **Person → Employment → Position → Position Cabinet → Permission Template → Effective Permissions** ([ADR-051](../adr/ADR-051-cabinet-access-resolution.md)); acting adds overlay without ownership transfer |
| **Primary entities (domain)** | Position, **Position Cabinet**, Employment, Acting Assignment, Permission Template, position-owned artefacts |
| **Typical scenarios** | Execute tasks; review dashboards; run function journals; approve in role; HR operational contour for privileged positions |

**Explicit exclusions:** Work Context **≠** Position Cabinet **≠** Unified User Workspace. Switching Work Context **does not** create, destroy, or migrate Cabinet entities.

**Representative modules (non-exhaustive; see PC-MOD-001):**

| Module class | Tier (PC-MOD-001) | Ownership | Contour |
|--------------|-------------------|-----------|---------|
| Задачи | T1 Core | Position | Work Context |
| KPI / Дашборды | T1 Core | Position | Work Context |
| История кабинета | T1 Core | Position | Work Context |
| Кадровые процессы | T2 function-conditional | Organization (executed from Cabinet) | Work Context |
| Журналы / документы функции | T2 | Position / Organization | Work Context |
| Уведомления (cabinet operational) | T2 | Shared — cabinet delivery profile | Work Context |

**Cabinet operational notifications** (PC-MOD-001 §3.11): events **about position-owned work** (tasks, approvals, cabinet subscriptions). **Not** the Person-level platform inbox (see §7.2).

### 7.2. Self Services

| Dimension | Definition |
|-----------|------------|
| **Purpose** | Person-centric services: view and interact with **own** HR and personal data |
| **Owner (data)** | **Person / Employee** ([GLOSS-B4-001](../access/GLOSS-B4-001-position-cabinet-vocabulary.md) §6) |
| **Lifecycle** | Follows Person career across Positions; **not** reset on Cabinet Owner change or Work Context switch |
| **Visibility** | **Self Visibility** (§8) — default self-read unless elevated confidentiality (**proposed** — non-normative) |
| **Authorization model** | Self Visibility **∪** (optional) administrative permissions when user also holds HR/admin roles via Work Context — contours must not collapse |
| **Primary entities** | Person, Employee, Personnel History, education profile, certificates |
| **Typical scenarios** | View own employment history; update contact prefs; view education; submit HR request; report data error |

**Representative modules (directional):**

| Module | Ownership | Notes | Contour |
|--------|-----------|-------|---------|
| Мой профиль | Employee/Person | Platform User linkage, contacts | Self Services |
| Моя кадровая история | Employee/Person | Distinct from Cabinet History | Self Services |
| Моё образование | Employee | PC-MOD-001 T3 — employee-owned; see §7.4 | Self Services |
| Мои отпуска | Employee/Person | Future | Self Services |
| HR-запросы | Shared workflow | Initiated by Person; processed in org domains | Self Services |
| Сообщить об ошибке | Person | Triggers correction workflows | Self Services |
| Личный inbox уведомлений | Person/Employee | Platform delivery to Person; **not** cabinet operational events | Self Services |

### 7.3. Contour interaction rules

| Rule | Statement |
|------|-----------|
| **R1** | Self Services remain available and **Person-scoped** when user switches Work Context |
| **R2** | Work Context modules must not silently expose **predecessor's** employee-owned data |
| **R3** | Acting user gains Work Context access to **target Cabinet** without acquiring target Owner's Self Services identity |
| **R4** | HR admin acting in Work Context uses **administrative permissions** (ACCESS-001), not Self Visibility, for **others'** data |
| **R5** | Presentation co-location (same top navigation) **does not** merge authorization evaluation |
| **R6** | **Cabinet operational notifications** (Work Context) and **Person notification inbox** (Self Services) are **distinct channels** — no implicit merge or deduplication without explicit Composer policy |

### 7.4. Module classification axes — PC-MOD tier vs PC-CONCEPT contour (M-04 resolution)

Architecture Review finding **M-04** (T3 modules «inside Cabinet» in PC-MOD vs Self Services in PC-CONCEPT) is **rejected as an architectural defect** of this document and **deferred** to formal cross-document mapping (**OQ-PC-005**).

**Rationale (Reject + Defer):**

| Axis | Document | Question answered |
|------|----------|-----------------|
| **Product catalog / ownership tier** | PC-MOD-001 (T1 / T2 / T3) | What modules belong to the **duty workspace product**, and who **owns the data**? |
| **Presentation contour** | PC-CONCEPT-001 (Work Context / Self Services) | In which **UWS contour** is a module **rendered**, and does it **switch** with Work Context? |

These axes are **orthogonal**. T3 modules (e.g. Образование) are **employee-owned** in **both** documents (GLOSS-B4-001 §6; PC-MOD-001 §3.12). PC-MOD «inside Position Cabinet» means **functional product catalog** and **shell-attached presentation in duty context** — **not** domain ownership and **not** Work Context contour.

**Directional mapping (v0.4 — not exhaustive; formal register in OQ-PC-005 / PC-MOD-001 v0.2):**

| PC-MOD tier | Typical owner | PC-CONCEPT contour | Switches with Work Context? |
|-------------|---------------|-------------------|----------------------------|
| T1, T2 (position-operational) | Position / Shared | **Work Context** | Yes — modules of **active** Cabinet |
| T3 (shell-attached) | Employee | **Self Services** | **No** — INV-PC-004 |
| Permission Template | Organization / Position | Configuration — not a contour | No |

**No change required** to Self Services placement for T3. Downstream: **PC-MOD-001 v0.2** adds explicit contour column; diagram clarification that T3 is shell-attached in **product catalog**, not position-owned domain data.

---

## 8. Self Visibility

> **Normative status:** Self Visibility is **proposed** in PC-CONCEPT-001 only. It **does not block** approval of the entity/contour model. It **does block** Self Services product expansion until **OQ-PC-001** / **OQ-PC-002** resolve (separate ADR or ACCESS register).

### 8.1. Why Self Visibility exists

1. **Personhood** — каждый работник имеет legitimate interest видеть свои кадровые факты;
2. **Data quality** — прозрачность снижает ошибки оформления («кадровая прозрачность»);
3. **Separation of concerns** — self-read не должен проходить через матрицу «доступ к чужим данным»;
4. **Unified UX** — Self Services требуют **базового** права читать себя без role simulation.

### 8.2. Why Self Visibility is not part of ACCESS-001

[ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md) governs:

- organizational **permission domains** on Position Cabinet contours;
- which `access_roles` may bind to Permission Template for **operating on organizational data** (including other employees within authorized scope).

Self Visibility governs:

- **Person → own Employee/Person data** regardless of Cabinet contour;
- **not** expressed as contour permission row;
- **not** delegatable via Permission Template to third parties as «self-read of Alice by Bob».

| Model | Subject | Object | Normative home (today) |
|-------|---------|--------|------------------------|
| **ACCESS-001** | Person via Cabinet permissions | Others' org/HR data within granted scope | ACCESS-001 |
| **Self Visibility** | Person | Own Person/Employee data | **Not yet normative register** — proposed in PC-CONCEPT-001 (**OQ-PC-001**) |

Models are **orthogonal**: satisfying ACCESS-001 row is neither necessary nor sufficient for Self Visibility; vice versa.

### 8.3. Interaction with ACCESS-001

```text
Effective view (conceptual) =
    Self Visibility (own data)
  ∪ Administrative permissions (ACCESS-001 / Template / ADR-051 — others' data in scope)
```

| Scenario | Self Visibility | ACCESS-001 |
|----------|-----------------|------------|
| Employee views own employment history | **Yes** | Not applicable |
| HR head views subordinate's history | No (not «self») | **Yes** — if permitted |
| Employee views own tasks in Work Context | Via Work Context access to **own Cabinet** | Not via self-read of «foreign» data |
| Employee with HR role opens personnel journal | No for others' rows | **Yes** — Work Context admin scope |

**Non-goal:** Self Visibility **must not** elevate user to HR admin capabilities.

### 8.4. Limitations and exceptions

| Category | Default Self Visibility | Exception |
|----------|-------------------------|-----------|
| Identity (FIO, IIN, employment dates) | Allowed | Legal restriction — TBD register |
| Compensation / sensitive payroll | **Restricted** by default | Explicit policy + legal basis |
| Disciplinary / investigation records | **Restricted** | Elevated confidentiality class |
| Medical / psychological assessments | **Restricted** | Regulatory class |
| Peer review about others | **Denied** | Not «self» data |
| Aggregated org analytics | **Denied** | Organizational data |

**Open (for review):** formal **confidentiality taxonomy** binding categories → Self Visibility default (**OQ-PC-002**).

### 8.5. Illustrative self-visible categories (non-normative)

> **⚠ Non-normative illustration only.** The list below is **not** policy, **not** enforcement, and **not** a Permission Template input. It informs future Self Visibility ADR / register work (**OQ-PC-001**, **OQ-PC-002**). Do **not** implement as defaults without normative approval.

Pending dedicated ADR/register, the following categories are **candidates** for self-visible treatment unless explicitly restricted by future policy:

- Own Person identifiers and contact channels designated «employee-editable»
- Own active **Employments** (Занятие должности facts) and acting periods affecting self
- Own Personnel History events designated «employee-visible» in HR policy
- Own education, certificates, competencies marked employee-owned (PC-MOD-001 T3)
- Own submitted HR requests and their status
- Own **Person notification inbox** (distinct from cabinet operational notifications — §7.1, R6)

---

## 9. Multi-Employment switching

### 9.1. Preconditions

A Person may simultaneously:

- hold **multiple Employments** (совместительство);
- hold **acting overlay** on additional Cabinet(s);
- retain **one** Platform User login ([ARCH-001](../architecture/ARCH-001-foundation-summary.md) invariant: stable login).

Each accessible Cabinet is reached via **Employment** or **Acting Assignment** — not by direct Person→Cabinet link.

### 9.2. Active Work Context rules (conceptual)

| Rule | Statement |
|------|-----------|
| **SW-1** | Exactly **one active Work Context** (session view of one Position Cabinet) at a time in UWS |
| **SW-2** | Work Context **selects which already-accessible Cabinet** is active — it **does not grant** access by itself |
| **SW-2a** | Switching Work Context does **not** change **Effective Permission Set** (union at T) — ADR-051 §7.4 |
| **SW-3** | Default active Work Context = session view of **primary Employment's Cabinet** per resolver policy (TBD — OQ-PC-003; ADR-051 §7.3 precedence) |
| **SW-4** | User **explicitly switches** Work Context when multiple Cabinets accessible; **Cabinet entities unchanged** |
| **SW-5** | Self Services **do not switch** with Work Context (INV-PC-004) |
| **SW-6** | Acting access appears as **switchable Work Context** over **target Cabinet**, labeled as acting — not ownership transfer |
| **SW-7** | Vacant Cabinet: **entity persists**; **not** selectable as user Work Context unless Person has **acting overlay** on that Position's Cabinet (ADR-036 / ADR-051 §5.4). **No** alternate «admin» or direct Person→Cabinet path — break-glass uses **exception grants** extending effective permissions, not vacancy Work Context selection |

### 9.3. Lifecycle diagram

```text
Person / Employee logs in
     │
     ▼
Resolve Employments + acting
     → accessible Position Cabinets {Cab₁, Cab₂, …}
     │
     ▼
Open UWS (composition shell)
     │
     ▼
Set active Work Context = session view of default(Cabᵢ)
     │
     ├── user switches Work Context ──► view moves to Cabⱼ (Cabᵢ unchanged)
     │
     ├── Employment for Cabᵢ ends ──► Cabᵢ drops from accessible set;
     │                                 Cabᵢ entity persists; reselect if was active
     │
     └── acting on Cabₖ starts ──► Cabₖ added to accessible set;
                                     user may switch Work Context view to Cabₖ
```

---

## 10. History: Cabinet History vs Personnel History

| History type | Owner | Content | Survives occupant change? | UI contour |
|--------------|-------|---------|---------------------------|------------|
| **Cabinet History** | Position Cabinet | Tasks completed, approvals, reports, function documents in role | **Yes** — inside same Cabinet | Work Context |
| **Personnel History** | Person/Employee | Hire, transfer, promotion, leave, termination HR events | **Yes** — follows Person | Self Services |

**Invariant H1:** Cabinet History **must not** be migrated to departing Employee as personal archive.

**Invariant H2:** Personnel History **must not** replace Cabinet operational audit.

**UX rule:** Unified User Workspace may present both, but **labeling and navigation** must preserve semantic separation (PC-MOD-001 + Self Services modules).

---

## 11. Relationship matrix

Legend: **●** direct structural relation · **○** contextual / compositional · **—** orthogonal · **→** derives / governs · **⇢** session view (not ownership)

|  | Employee | Platform User | Employment | Cabinet Owner | Position | **Pos. Cabinet** | Work Context | Self Services | ACCESS-001 | Self Visibility |
|--|:--------:|:-------------:|:----------:|:-------------:|:--------:|:----------------:|:------------:|:-------------:|:----------:|:---------------:|
| **Employee** | — | ○ via Person | ● fact | ○ may be | ○ via Employment | ○ via Employment only | ○ viewer | ● scope | ○ others' data | ○ self (proposed) |
| **Platform User** | ○ | — | — | — | — | — | ○ session shell | ○ session shell | — | ○ auth Person |
| **Employment** | ● | — | — | → defines | ● | → **grants access to** | → enables view of | — | → Template perms | — |
| **Cabinet Owner** | ○ | — | ● via active Employment | — | ● relation | ○ access only | ○ when active | — | — | — |
| **Position** | — | — | ● target | ● at most one active | — | ● **1:1 entity** | ○ via Cabinet | — | ○ contour | — |
| **Pos. Cabinet** | — | — | ○ access path | ○ Owner relation | ● | — | ⇢ **target of** active view | — | ○ contour policy | — |
| **Work Context** | ○ | ○ | ○ active Employment | ○ | ○ | ⇢ **views one** | — | ○ co-presented | ○ admin perms | — |
| **Self Services** | ● | ○ | — | — | — | — | ○ **independent of** | — | — | ● authorization (proposed) |
| **ACCESS-001** | ○ others' data | — | ○ via Cabinet | — | ○ contour | ○ on Cabinet contour | ○ others' org data | — | — | — |
| **Self Visibility** | ● own data | — | — | — | — | — | — | ● own data | — | — |

**Reading guide:**

- **Position Cabinet** is the **only** column that is a **persistent domain entity** among UWS presentation columns.
- **Work Context** has **no ●** relation to data ownership — only **⇢ views** Position Cabinet.
- **Self Services** have **no ●** to Work Context or Employment — Person/Employee scope only.
- **Cabinet Owner** is a **role relation** via Employment — not an entity owner of Cabinet.

---

## 12. Architectural invariants

| ID | Invariant |
|----|-----------|
| **INV-PC-001** | **Position Cabinet is a domain entity** — 1:1 with org-unique Position; co-created; **unchanged** from ADR-050 / INV-B4-001 |
| **INV-PC-001a** | **Position Cabinet persists** through vacancy, acting overlays, and Person change — only access and Owner relation change |
| **INV-PC-002** | **Unified User Workspace is not a domain entity** — composition shell only; **no** persistent ownership of business data |
| **INV-PC-002a** | **Work Context is not a domain entity** — session-level active **view** of one Position Cabinet; **does not own** data |
| **INV-PC-003** | **Exactly one active Work Context view** per session (switchable among accessible Cabinets) |
| **INV-PC-003a** | **Cabinet access requires Employment or acting** — no direct Person/Employee → Cabinet access path; exception grants extend permissions only (ADR-051 R17) |
| **INV-PC-004** | **Self Services scope = Person/Employee**, **independent** of active Work Context |
| **INV-PC-005** | **Workspace Composer does not own domain data** |
| **INV-PC-006** | **Self Visibility ⊥ ACCESS-001** — orthogonal models; both may apply in one session without merge |
| **INV-PC-007** | **Acting grants access, not ownership** (INV-B4-002) — acting Work Context ≠ Cabinet Owner |
| **INV-PC-008** | **Cabinet History ≠ Personnel History** — distinct owners, retention, and UX semantics |
| **INV-PC-009** | **Employee-owned data does not transfer** between Cabinet Owners |
| **INV-PC-010** | **Platform User performs authentication only** — no permission ownership |
| **INV-PC-011** | **Presentation unity must not imply authorization unity** |
| **INV-PC-012** | **Cabinet operational notifications ≠ Person notification inbox** — distinct ownership and contour (§7.1, §7.2, R6) |

---

## 13. Architectural non-goals

| ID | Non-goal |
|----|----------|
| **NG-PC-001** | Replace Accepted ADR-050 / ADR-051 entity model |
| **NG-PC-002** | Collapse Position Cabinet into Work Context, UWS, or «User Workspace» domain entity |
| **NG-PC-002a** | Treat Work Context as owner of position-owned backlog, KPI, or Cabinet History |
| **NG-PC-003** | Encode Self Visibility as Permission Template row |
| **NG-PC-004** | Merge ACCESS-001 and Self Visibility documents without review |
| **NG-PC-005** | Define API, schema, UI routes, or feature flags in this concept |
| **NG-PC-006** | Mandate immediate migration from as-is `users.role_id` model |
| **NG-PC-007** | Eliminate HR operational contour («Кадровые процессы») — it remains Work Context module for privileged roles |
| **NG-PC-008** | Redefine PC-MOD-001 module **ownership** tier — contour mapping is additive (OQ-PC-005), not an ownership change |

---

## 14. Future extensions (not approved)

| Extension | Description | Likely downstream artefact |
|-----------|-------------|----------------------------|
| **Self Visibility register** | Normative confidentiality taxonomy + defaults | ACCESS amendment or ACCESS-003 / ADR |
| **Work Context resolver policy** | Default Cabinet selection, acting labels | ADR amendment to ADR-051 or ops policy |
| **Vacation / leave Self Service** | Employee-owned absence views | PC-MOD module + personnel ADR |
| **Multi-org User Workspace** | Not applicable single-tenant — reserved | N/A |
| **Delegate access** | Assistant acting on behalf with audit | Separate ADR — not Self Visibility; distinct from Acting Assignment (ADR-036) unless explicitly unified |
| **Cabinet History export** | Position-owned archive on liquidation | ADR + retention policy |
| **Workspace personalization** | User layout prefs (not business data) | Implementation WP |
| **Non-Position workspaces** | Project / committee / temporary team shells | Requires new ADR — outside Position 1:1 Cabinet model |

---

## 15. Open questions (Architecture Review gate)

| ID | Question | Blocks | v0.4 status |
|----|----------|--------|-------------|
| **OQ-PC-001** | Where is Self Visibility normatively registered — ACCESS family vs standalone ADR? | Self Services expansion | Open |
| **OQ-PC-002** | Formal confidentiality taxonomy for exceptions to default self-read | ACCESS / legal review | Open |
| **OQ-PC-003** | Default active Work Context algorithm for multi-employment (which Employment wins) | ADR-051 policy annex | Open — ADR-051 §7.3 gives interim precedence |
| **OQ-PC-004** | Should «Unified User Workspace» become glossary term (GLOSS-B4-002)? | Terminology drift | Open |
| **OQ-PC-005** | Map every PC-MOD-001 module → Work Context vs Self Services officially | PC-MOD-001 amendment | **Deferred** — directional mapping in §7.4; M-04 **rejected** as PC-CONCEPT defect |
| **OQ-PC-006** | HR admin dual contour UX — single nav vs separated admin shell | UX architecture WP | Open |
| **OQ-PC-007** | Personnel Orders — Work Context module ownership (Organization) confirmation | Personnel architecture | Open |
| **OQ-PC-008** | Relationship PC-CONCEPT-001 ↔ ARCH-001 §8 «личный кабинет» — merge or cross-reference amendment | ARCH-001 hygiene | **Partially addressed** — §4.1 mapping |
| **OQ-PC-009** | Retention/legal hold interaction with Self Visibility | Compliance ADR | Open |
| **OQ-PC-010** | Confirm glossary register for Work Context vs Position Cabinet (prevent entity collapse) | GLOSS / PC-MOD | **Partially addressed** — §4.1; full register still open |

---

## 16. Recommended downstream decomposition

**Not approved — recommendations only.**

| Recommendation | Type | Rationale |
|----------------|------|-----------|
| **Accept PC-CONCEPT-001 v0.4** as Architecture Draft after review | Governance | Review remediation — terminology, mapping, notifications |
| **GLOSS register update** (UWS, Work Context, Self Visibility) | Glossary amendment | OQ-PC-004, OQ-PC-010 |
| **PC-MOD-001 v0.2** — explicit contour column per module | Product composition | OQ-PC-005 formal mapping |
| **ADR: Self Visibility model** | New ADR | OQ-PC-001; orthogonal to ACCESS-001 |
| **ADR-051 policy annex: active Work Context** | ADR amendment proposal | OQ-PC-003 |
| **ARCH-001 §8 cross-reference** | ARCH amendment proposal | OQ-PC-008 — link «личный кабинет» to PC-CONCEPT-001 |
| **Do not amend ACCESS-001** until Self Visibility ADR reviewed | Process guard | NG-PC-004 |

---

## 17. Traceability

| Source | Relationship |
|--------|--------------|
| [ARCH-001](../architecture/ARCH-001-position-permission-model.md) | Domain chain Person → **Employment** → Position → Cabinet — **preserved**; UWS/Work Context = Personal UI Shell / Active Cabinet Context (§4.1) |
| [GLOSS-B4-001](../access/GLOSS-B4-001-position-cabinet-vocabulary.md) | Position Cabinet entity + ownership — **preserved**; Employment / Acting Assignment terms aligned; UWS terms **not** in glossary yet (OQ-PC-004, OQ-PC-010) |
| [PC-MOD-001](../access/PC-MOD-001-position-cabinet-functional-composition.md) | T1/T2 → Work Context; T3 → Self Services (§7.4) — **ownership unchanged**; formal module→contour table deferred **OQ-PC-005** |
| [ACCESS-001](../access/ACCESS-001-organizational-permission-matrix.md) | **Unchanged** — others' data on Cabinet contour via Employment access path |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) | Cabinet 1:1 Position; co-lifecycle — **unchanged** |
| [ADR-051](../adr/ADR-051-cabinet-access-resolution.md) | Resolver over Employments + acting — **unchanged**; Work Context ↔ Active Cabinet Context mapped (§4.1); selection policy open (OQ-PC-003) |
| [PC-CONCEPT-001-review-notes](./PC-CONCEPT-001-review-notes.md) | Prior review backlog — entity/view split addressed v0.2–v0.3; terminology/contour remediation v0.4 |

---

## 18. Architecture diagram (consolidated)

```text
                         Platform User
                              │ auth
                              ▼
           Person / Employee ──────────────────────┐
                              │                     │
                   Employment (Занятие)            │ Self Visibility (proposed)
                              │                     │
                              ▼                     ▼
                          Position            Self Services
                              │              (Employee-owned;
                              │ 1:1 entity     not tied to Work Context)
                              ▼
                    Position Cabinet ◄──────── domain persistence:
                    (position-owned data)       survives vacancy,
                              │                 acting, Person change
                              │
                              │  accessible via Employment / acting
                              ▼
                   Unified User Workspace  ≈ Personal UI Shell
                   (composition shell — not an entity)
                   ┌──────────┴──────────┐
                   │                     │
             Work Context           Self Services
          session VIEW of           (same Person scope
           ONE Cabinet)              regardless of view)
                   │                     │
                   │                     └── T3 modules, personal inbox, …
                   └── presents T1/T2 modules owned by that Cabinet
                       (Tasks, Dashboards, cabinet notifications, …)
```

---

## Document history

| Date | Version | Change |
|------|---------|--------|
| 2026-07-08 | 0.1 | Initial short Draft (DOCX origin) |
| 2026-07-08 | 0.2 | Architecture Draft — UWS vs Cabinet split; two-contour formalization; Self Visibility; invariants; matrix |
| 2026-07-08 | 0.3 | Alignment pass — entity vs session view; access chain; anti-confusion rules; matrix/invariants strengthened |
| 2026-07-08 | 0.4 | Architecture Review remediation — Employment terminology; baseline mapping §4.1; notifications split; M-04 resolution §7.4; Self Visibility non-normative marking |

---

## Appendix A — v0.1 → v0.2 semantic corrections

| v0.1 statement | v0.2 resolution |
|----------------|-----------------|
| «Position Cabinet — не кабинет должности» | **Retired.** Cabinet **is** position domain entity; **UWS** is user composition layer |
| «Position Cabinet = единое рабочее пространство пользователя» | **Refined:** **Unified User Workspace** = user shell; opened **through** Employment |
| Two contours listed without formal dimensions | **§7** — full owner/lifecycle/visibility/auth/entities/scenarios |
| Self Visibility asserted without limits | **§8** — rationale, orthogonality, limits, defaults (Draft) |

---

## Appendix B — v0.2 → v0.3 alignment corrections

| v0.2 ambiguity | v0.3 resolution |
|----------------|-----------------|
| Work Context «bound to Cabinet lifecycle» (§7.1) | Split: **Cabinet lifecycle** (domain) vs **Work Context view lifecycle** (session) |
| Work Context listed without **Entity?** column in summary | Explicit **not an entity** / **not data owner** throughout |
| «Employment → Cabinet» shorthand in auth model | Full chain: **Person → Employment → Position → Position Cabinet** |
| Position Cabinet column absent in relationship matrix | **Pos. Cabinet** column added; Work Context uses **⇢ views** not **● owns** |
| Self Services «independent» stated once | Reinforced in §6, §7, §9 SW-5, matrix, INV-PC-004 |
| Access path could imply Person → Cabinet direct | **INV-PC-003a**, §5.2 access rule, §9 SW-2 |

---

## Appendix C — v0.3 → v0.4 Architecture Review remediation

| Review ID | Finding | v0.4 resolution |
|-----------|---------|-----------------|
| **M-01** | «Position Assignment» / «Назначение» vs ARCH-001 Employment | **Closed.** Employment / Занятие должности — primary term throughout; Russian «назначение» removed |
| **M-02** | Work Context vs Active Cabinet Context / Personal UI Shell | **Closed.** §4.1 baseline mapping; ADR-051 §7.4 union note |
| **M-03** | SW-7 undefined «admin access» | **Closed.** SW-7 — acting only; exception grants per ADR-051 R17; INV-PC-003a clarified |
| **M-04** | T3 PC-MOD vs Self Services | **Rejected + Deferred.** §7.4 — orthogonal axes; OQ-PC-005; no Self Services placement change |
| **M-05** | Self Visibility without normative home | **Closed.** §8 normative banner; §8.5 non-normative illustration |
| **M-06** | Notifications split undefined | **Closed.** §7.1 cabinet operational vs §7.2 Person inbox; R6; INV-PC-012 |
| **m-01** | Cabinet Owner absent from matrix | **Closed.** Matrix expanded (§11) |
| **m-02** | Leave access restriction | **Closed.** §6.2 lifecycle row |
| **m-03** | Union vs Work Context switch | **Closed.** SW-2a; §4.1; §6.2 context switch row |
| **m-05** | ARCH-001 full doc traceability | **Closed.** Normative inputs + §17 |
