# ADR-055 — Operational Role Architecture (Proposal)

## Status

**Proposed** — 2026-07-15 (rev. 0.4)

| Field | Value |
|-------|-------|
| Work Package | ORG-ROLE-001 (conceptual) |
| Scope | **Organization-wide** architecture; **Отдел кадров** — first pilot only |
| Parent context | [ARCHITECTURE_GOVERNANCE](../architecture/ARCHITECTURE_GOVERNANCE.md); [ADR-050](./ADR-050-organization-position-cabinet-model.md); [ADR-051](./ADR-051-cabinet-access-resolution.md) |
| Related (unchanged) | [PC-PROFILE-001](../access/PC-PROFILE-001-position-cabinet-functional-profiles.md); [ADR-046](./ADR-046-org-unit-allowed-positions.md); [ADR-042](./ADR-042-phase-b1-schema-design.md) |
| Bootstrap (HR pilot, Stage 1) | [hr_department_positions_bootstrap.sql](../scripts/pilot/hr_department_positions_bootstrap.sql) |
| Runtime effect | **None** — no migrations, tables, or code in this ADR |
| Supersedes (naming) | Draft term *Position Functional Profile (PFP)* — replaced by **Operational Role** |

---

## Context

В организации несколько работников на **одной официальной штатной должности** (`public.positions`) могут исполнять **разные операционные функции**:

- два «Менеджера УЧР» — воинский учёт vs кадровые приказы;
- «секретарь-референт» — приём граждан vs документооборот;
- аналогичные случаи возможны **в любом подразделении**, не только в HR.

Официальная должность остаётся единственным источником для:

- штатного расписания;
- кадровых приказов и HR-документов;
- записей в `positions` / snapshots в приказах.

Внутренние процессы (задачи, workflow, KPI, Position Cabinet slices) требуют **каталога обязанностей/функций**, отделённого от штатного наименования и от конкретного человека.

### Naming decision

| Candidate | Assessment |
|-----------|--------------|
| **Operational Role** ✅ | Универсально; подчёркивает операционный контур; не путается с Platform Role (`public.roles`) при документировании |
| Functional Position Profile | Слишком привязано к Position как UI-объекту; звучит как атрибут должности, а не функции |
| Work Function / Duty | Точно по смыслу, но слабее как registry entity; «function» перегружено в коде |
| Functional Profile | Конфликт с Cabinet Profile (PC-PROFILE-001) |

**Decision:** принять термин **Operational Role** (RU: *операционная роль* / *операционная функция*) для каталога обязанностей. Platform Role в тексте ADR называется явно **Platform Role**, Operational Role — **OR**.

### Stage 1 (HR pilot — catalog positions only)

Официальные должности отдела кадров подготовлены в bootstrap-скрипте (`public.positions`, одна запись на наименование). Это **локальный пилот данных**, не ограничение архитектуры.

### Stage 2 (настоящий ADR)

Описать **organization-wide** модель Operational Role без реализации и без изменения Position / Employment schema.

---

## Decision Drivers

1. **Operational Role описывает обязанность/функцию**, а не сотрудника и не Employment.
2. **Официальная должность неизменна** в кадровых и юридических артефактах.
3. **Привязка исполнения** — через **Employment** (`person_assignments`), не напрямую через `employees`.
4. **Обязательный неизменяемый `code`** для каждой Operational Role в реестре.
5. **Position Cabinet** (ADR-050) остаётся 1:1 с org-unique Position.
6. **PC-PROFILE-001** — класс кабинета (модули); OR — операционная функция внутри должности.
7. **Масштабирование на всю организацию**; HR — первый пилот каталога и назначений.

---

## Terminology

| Term (EN) | Term (RU) | Definition |
|-----------|-----------|------------|
| **Official Position** | **Официальная должность** | Запись в `public.positions` — штатное наименование |
| **Org-unique Position** | **Орг-уникальная должность** | `(client_scope_id, org_unit_id, catalog_position_id)` → Position Cabinet (ADR-050) |
| **Employment** | **Занятие должности / трудовое назначение** | Эpisode `person_assignments` (ADR-042): Person occupies org-unique Position for `[start, end]` |
| **Operational Role (OR)** | **Операционная роль** | **Каталоговая** запись об обязанности/функции; принадлежит одной official position; **не Person** |
| **OR Assignment** | **Назначение операционной роли** | Связь **Employment ↔ Operational Role** на период (future) |
| **Platform Role** | **Платформенная роль** | `public.roles` / `users.role_id` — legacy auth; **не** Operational Role |
| **Cabinet Profile** | **Профиль кабинета** | PC-PROF-* (PC-PROFILE-001) — состав модулей Position Cabinet |

### What Operational Role IS and IS NOT

| Operational Role **is** | Operational Role **is not** |
|-------------------------|----------------------------|
| Описание функции/обязанности («Воинский учёт») | Профиль сотрудника или Person |
| Стабильная строка реестра с immutable `code` | Должность в штатном расписании |
| Anchor для Tasks / Workflow / KPI | Platform Role |
| Дочерний элемент official position в каталоге | Замена `Employee.position_id` |
| Organization-wide concept | HR-only entity |

### Disambiguation: OR vs Cabinet Profile

| Dimension | Operational Role (OR) | Cabinet Profile (PC-PROF-*) |
|-----------|----------------------|-----------------------------|
| **Question** | *Какую функцию исполняют в рамках должности?* | *Какие модули видит Position Cabinet?* |
| **Granularity** | N roles per **catalog** position | One profile per **org-unique** Position |
| **Binds to** | Employment assignment (future) | Position Cabinet |
| **Example** | `OR-HR-MGR-UHR-PO` «Кадровые приказы» | PC-PROF-HR |

---

## Proposed Target Model

```text
Person
   │
   └── Employment (person_assignments) ──► Official Position (catalog via org-unique Position)
              │                                    │
              │                                    │ 1 : N (catalog scope)
              │                                    ▼
              └── OR Assignment (future) ──► Operational Role (registry: duty / function)
                                                    │ immutable code
                                                    ├── Task Templates
                                                    ├── Workflow routes
                                                    ├── KPI sets
                                                    ├── Position Cabinet slices (future filter)
                                                    ├── Production instructions
                                                    ├── SLA policies
                                                    └── Checklists
```

**Key separation:**

- **Position** answers: *какая штатная должность по документам?*
- **Operational Role** answers: *какую операционную функцию исполняет данное Employment?*
- **Person** receives OR **only through** active Employment episode.

`employees` may remain operational snapshot for as-is UI; **target binding** for OR is **`person_assignments.id`** (Employment), not `employees.employee_id`.

---

## Invariants (normative for future implementation)

| ID | Invariant |
|----|-----------|
| **OR-1** | Operational Role is a **catalog of duties**; it never represents a Person or Employee |
| **OR-2** | Each OR has a **mandatory, globally unique, immutable `code`**; rename/display change via `name_*`, not code |
| **OR-3** | Each OR belongs to **exactly one** `catalog_position_id` (official position) |
| **OR-4** | Official position on Employment / orders **never** replaced by Operational Role |
| **OR-5** | Personnel orders and official HR documents reference **only** official position snapshots |
| **OR-6** | OR Assignment links **Employment ↔ Operational Role**, not Employee ↔ OR directly |
| **OR-7** | OR Assignment is **time-bounded** (`valid_from` / `valid_to`) aligned with Employment period |
| **OR-8** | Changing OR Assignment **does not** rewrite historical document snapshots |
| **OR-9** | OR catalog exists **independently** of vacant positions and unoccupied Employments |
| **OR-10** | Architecture is **organization-wide**; HR catalog entries are **pilot instances**, not a separate domain model |

---

## Proposed Entity Sketch (not implemented)

### Registry: `operational_role` (future — illustrative)

Describes **what function exists**, not who performs it.

| Field | Purpose |
|-------|---------|
| `id` | Surrogate PK |
| **`code`** | **Required, unique, immutable** registry identifier (e.g. `OR-HR-MGR-UHR-MIL`) |
| `catalog_position_id` | FK → `public.positions` — parent official position |
| `name_ru` / `name_kk` | Display names (mutable) |
| `description` | Scope of duty (mutable) |
| `org_unit_id` | Optional **scope hint** for pilot disambiguation (e.g. HR unit 73); not required org-wide |
| `is_active` | Soft disable (code remains) |
| `sort_order` | Admin ordering |
| `pilot_domain` | Optional tag (`HR`, `QM`, …) for rollout tracking — not authorization |

**Code rules:**

- Format: uppercase registry convention `OR-{DOMAIN}-{...}` (exact grammar — OQ-OR-003).
- **Insert-only identity:** `code` never updated after creation; deactivation via `is_active=false`.
- Human-readable rename does not create a new code.

### Assignment: `employment_operational_role` (future — illustrative)

Describes **which OR is active on which Employment episode**.

| Field | Purpose |
|-------|---------|
| `id` | Surrogate PK |
| `person_assignment_id` | FK → `person_assignments` (**Employment**) |
| `operational_role_id` | FK → `operational_role` |
| `valid_from` / `valid_to` | Assignment window ⊆ Employment window |
| `is_primary` | Primary function when multiple OR allowed (OQ-OR-002) |
| `assigned_by_user_id` | Audit |
| `assigned_at` | Audit |

**Rejected:** `employee_operational_role` as primary FK — bypasses canonical Employment model (ADR-042, ADR-051).

---

## Illustrative Catalog — HR Pilot (not seeded)

Examples only. Each row is a **duty**, not a person.

### Parent official position: Менеджер УЧР

| code (immutable) | name_ru (duty) |
|------------------|----------------|
| `OR-HR-MGR-UHR-MIL` | Воинский учёт |
| `OR-HR-MGR-UHR-PO` | Кадровые приказы |
| `OR-HR-MGR-UHR-OO` | Производственные приказы |
| `OR-HR-MGR-UHR-HIRE` | Приём сотрудников |
| `OR-HR-MGR-UHR-TRANSFER` | Переводы |
| `OR-HR-MGR-UHR-DISMISS` | Увольнения |

### Parent official position: секретарь-референт

| code | name_ru |
|------|---------|
| `OR-HR-SEC-RECEPTION` | Приём граждан |
| `OR-HR-SEC-DOCFLOW` | Документооборот |

### Other HR pilot positions (TBD with HR)

| Official position | OR strategy |
|-------------------|-------------|
| Руководитель отдела кадров | Supervisory / approval ORs; cross-view, not substitute for subordinate duties |
| Менеджер | Generalist HR operation ORs |
| Переводчик казахского языка | Bilingual document ORs |

### Organization-wide examples (future, non-HR)

| Official position (example) | Operational Role (example) |
|----------------------------|----------------------------|
| Заведующий отделением | `OR-CLIN-HEAD-ROSTER` — оперативное расписание |
| Медсестра палаты | `OR-CLIN-NRS-MEDS` — лекарственное обеспечение |
| Специалист ОВЭиПД | `OR-QM-AUDIT-IPCA` — внутренний аудит |

Same registry model; HR is **first population**, not a separate schema.

---

## Future Consumers

| Consumer | Binding |
|----------|---------|
| **Production tasks** | Owner scope = OR `code` |
| **Workflow** | Route by OR, not Platform Role |
| **Task Templates** | Template key = OR `code` |
| **Dashboard** | Widget sets per OR |
| **KPI** | Metrics keyed by OR `code` |
| **Position Cabinet** | Optional slice filter by active OR on Employment |
| **Production instructions** | Document binding to OR `code` |
| **SLA** | Policies per OR `code` |
| **Checklists** | Templates per OR `code` |

Official documents and штатное расписание **do not** reference Operational Role.

---

## Relationship to Existing Architecture

| Artifact | Relationship |
|----------|--------------|
| **ADR-042 `person_assignments`** | Canonical Employment; OR Assignment attaches here |
| **ADR-051 Cabinet Access** | Access still from Employment → Position Cabinet; OR does not grant permissions by itself |
| **ADR-050 Position / Cabinet** | Unchanged |
| **PC-PROFILE-001** | Orthogonal product layer |
| **ADR-046 allowed positions** | **Not implemented** — bootstrap seeds global catalog only; junction table deferred to ADR-046 F1 |
| **Personnel Orders** | Official position snapshots only |
| **Platform Role / RBAC** | Unchanged; OR is not RBAC |

---

## HR Pilot — Stage 1 Official Positions

Script: `scripts/pilot/hr_department_positions_bootstrap.sql`

### Official titles (global catalog — one row per name)

| # | Official position | Catalog rule |
|---|-------------------|--------------|
| 1 | Руководитель отдела кадров | Reuse by name; create `position_id=86` only if free |
| 2 | Менеджер УЧР | Reuse or insert by normalized name |
| 3 | Менеджер | Reuse or insert by normalized name |
| 4 | секретарь-референт | Reuse or insert by normalized name |
| 5 | Переводчик казахского языка | Reuse or insert by normalized name |

### Staffing units (informational — not persisted in DB)

| Official position | Staff units |
|-------------------|-------------|
| Руководитель отдела кадров | **1** |
| Менеджер УЧР | **4** |
| Менеджер | **4** |
| секретарь-референт | **3** |
| Переводчик казахского языка | **1** |

Recording staff units requires an existing or future **штатное расписание / staffing contour** (ADR-046 F1+, org-unique positions, or dedicated staffing entity). Until then, counts live in bootstrap comments and HR source documents only.

### Org unit allowed positions (deferred — ADR-046)

Bootstrap **does not** create `org_unit_allowed_positions` or application schema. Per repository audit (2026-07-15):

| Check | Result |
|-------|--------|
| ORM model | **Absent** (`app/db/models/` — no `OrgUnitAllowedPosition`) |
| Alembic migration | **Absent** (no `org_unit_allowed_positions` in `alembic/versions/`) |
| ADR-046 status | **Proposed (Future)** — draft DDL only, not scheduled |
| Production/local schema via migrations | **Table does not exist** in canonical chain |

**Split of work:**

1. **This commit track:** ADR-055 + `hr_department_positions_bootstrap.sql` — global `public.positions` catalog only.
2. **Future WP ADR-046-F1:** Alembic migration + ORM + admin API + read API + tests + HR allowed-positions seed script.

Until ADR-046 F1 lands, **department position list cannot be persisted** in a canonical table. Headcount (1/4/4/3/1) remains informational.

### API / UI gap (verified 2026-07-15)

Current `GET /directory/positions?org_unit_id=N` in `app/directory/positions_routes.py` filters via:

```sql
EXISTS (SELECT 1 FROM employees e WHERE e.position_id = p.position_id AND …)
```

It **does not read** `org_unit_allowed_positions`. Therefore:

| Data state | Visible in scoped list before endpoint fix? |
|------------|---------------------------------------------|
| Allowed links only (bootstrap applied, no employees) | **No** |
| Employees assigned | **Yes** (existing behaviour) |
| Empty department, no allowed table | Fallback to global catalog in Enrollment Wizard (ADR-045) |

### Consumer impact matrix (`GET /directory/positions?org_unit_id=`)

Impact analysis only — **no API/UI changes in this commit**.

| Consumer | Path | Passes `org_unit_id`? | Current semantics | Required semantics | Notes |
|----------|------|----------------------|-------------------|------------------|-------|
| **ImportEnrollEmployeeWizard** | `usePersonnelOrderPositionOptions` → `loadScopedPositionOptions` | Yes | **used** + **global fallback** | **allowed** (preferred for «штат отдела»); keep global for ad-hoc titles | HR positions visible via global group after catalog bootstrap |
| **PersonnelOrderItemEditor** | same hook | Yes | used + global groups | **allowed** preferred | Groups label scoped as «used in unit» today |
| **EmployeeAssignmentCorrectionDrawer** | same hook (`scopedOptions` only) | Yes | **used only** (no global merge in drawer) | **allowed** | Empty unit → empty select until employee exists |
| **PositionsPageClient** | direct `GET /directory/positions` | Yes (sidebar filter) | **used only** | **TBD** — admin may want allowed ∪ used or toggle | Empty HR filter until first hire |
| **TaskOrgFiltersBar** | `loadScopedPositionOptions` | Yes | **used** (task journal filter) | **used** (correct) | Filter «who has this title in unit» |
| **EmployeeCreateForm** | `getEmployees` → derive `unitPositionIds` | No (not this endpoint) | used via employees | **allowed** (different data path) | Global position list + highlight |
| **EmployeeTransferForm** | global `getPositions` + `getEmployees` filter | No | global + used highlight | **allowed** for target unit | Does not call scoped API |
| **EmployeesPageClient** | global `getPositions` | No | global catalog | N/A | Position filter on employee list |
| **VisibilityTab** | global `getPositions` | No | global | N/A | Admin visibility rules |
| **contacts / working-contacts** | global `POSITIONS_API` | No | global | N/A | |
| **personnelOrderPrintLoad** | global `getPositions` | No | global (labels) | N/A | |
| **EmployeePersonnelHistorySection** | global `getPositions` | No | global (labels) | N/A | |
| **Backend tests** | `tests/test_positions_org_scope.py` | Yes | documents **used** | extend when `scope=` lands | |

**Default without `scope`:** preserve current **used** behaviour for backward compatibility (ADR-046). New consumers should pass `scope=allowed` explicitly after F3.

**Endpoint overload vs separate resource:** extending `GET /directory/positions` with `scope=allowed|used` reuses pagination and RBAC; separate `GET /directory/org-units/{id}/allowed-positions` is clearer but duplicates list contract. **Recommendation:** query param on existing endpoint (ADR-046 §Recommended API).

### Minimal follow-up work packages (not in this commit)

**WP-ADR-046-F1 — Allowed positions foundation**

| Step | Deliverable |
|------|-------------|
| F1 | Alembic migration `org_unit_allowed_positions` (ADR-046 draft DDL) |
| F2 | SQLAlchemy model + repository |
| F3 | Read API: `GET /directory/positions?org_unit_id={id}&scope=allowed` |
| F4 | Preserve current default: `scope=used` (or document breaking change) |
| F5 | HR seed script: link 5 positions → unit `HR` |
| F6 | Tests + update consumers (see matrix below) |

**Alternative considered:** separate endpoint `GET /directory/org-units/{id}/allowed-positions` — clearer semantics, avoids overloading default; may duplicate pagination. **Recommendation:** extend existing endpoint with explicit `scope=` param per ADR-046 §Recommended API.

---

## Open Questions

| ID | Question | Default stance |
|----|----------|----------------|
| OQ-OR-001 | One or many OR assignments per Employment? | One **primary** OR; secondary via delegation (future) |
| OQ-OR-002 | Must OR.catalog_position match Employment's official position? | **Yes** — OR invalid if parent position mismatch |
| OQ-OR-003 | Exact `code` grammar and registry authority? | Central org admin; prefix by domain |
| OQ-OR-004 | Auto-suggest OR on Employment open? | Suggest only; explicit assignment |
| OQ-OR-005 | Relationship to acting (`ACTING_ASSIGNMENT`)? | Acting Employment may carry **temporary** OR overlay |

---

## Conscious Non-Goals (this phase)

| Non-goal | Status |
|----------|--------|
| Migrations / tables for OR | **Not done** |
| Changes to Position / Employee / `person_assignments` | **Not done** |
| OR seed data | **Not done** |
| RBAC / Workflow wiring | **Not done** |
| Git commit | **Deferred** |

---

## Consequences

### Positive

- Universal, org-wide model with immutable codes suitable for integration.
- Clear duty-centric registry; Employment-based assignment aligns with ADR-042/051.
- HR pilot validates model without forking architecture.

### Risks

- **Name collision** on generic positions («Менеджер») — mitigated by immutable `code` + optional `org_unit_id` scope.
- **Term overload** with Platform Role — mitigated by explicit naming in docs and UI.
- **Dual profile concepts** (OR + PC-PROF) — requires resolver documentation when implemented.

---

## Document History

| Date | Version | Change |
|------|---------|--------|
| 2026-07-15 | 0.1 | Initial draft (*Position Functional Profile*) |
| 2026-07-15 | 0.4 | Bootstrap: catalog-only (Variant B); ADR-046 junction deferred; consumer matrix |
