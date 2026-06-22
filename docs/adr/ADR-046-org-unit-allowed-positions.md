# ADR-046 — Org-unit allowed positions (Future)

**Status:** Proposed (Future — not scheduled)  
**Date:** 2026-06-22  
**Related:** ADR-031 (Directory contract), ADR-045 (Phase 3I enroll-from-import), `GET /directory/positions?org_unit_id=`

## Context

В Corpsite должности сегодня хранятся как **глобальный справочник** `public.positions` (`name`, `category`). Связь с отделением **не прямую**, а через операционных сотрудников:

```text
org_unit ──< employees >── position
```

Фильтр `GET /directory/positions?org_unit_id=N` возвращает должности, для которых **EXISTS** сотрудник с этой парой `(org_unit_id, position_id)` в scope отделения (см. `app/directory/positions_routes.py`).

### Phase 3I interim fix (2026-06-22)

Enrollment Wizard (`ImportEnrollEmployeeWizard`) использует двухшаговую загрузку:

1. scoped: `GET /positions?org_unit_id=N` — должности, **уже используемые** в отделении;
2. fallback: `GET /positions?limit=500` — **глобальный справочник**, если scoped пуст (отдел без сотрудников / первая запись / новая должность).

Commit: `103be25` — `fix(hr-import): fallback to global positions for empty departments`.

Это снимает блокировку «Нет доступных должностей», но **не** вводит явную модель «разрешённых для отдела должностей».

## Problem

Три разные семантики смешиваются в одном UI-фильтре:

| Семантика | Вопрос | Текущий источник |
|-----------|--------|------------------|
| **Global catalog** | Какие должности существуют в организации? | `public.positions` |
| **Allowed / typical for unit** | Какие должности *можно* назначить в этом отделении? | *Нет модели* |
| **Used in unit** | Какие должности *уже заняты* сотрудниками отделения? | `employees` + scoped `GET /positions` |

Последствия без явной модели allowed:

- первый сотрудник в отделе видит весь глобальный справочник (fallback Phase 3I);
- кадровик не получает «штатное расписание отделения»;
- нельзя заранее завести типовые должности для отдела до появления сотрудников;
- фильтр `org_unit_id` на API не означает «разрешено», только «используется».

## Decision (Future)

Ввести явную связь **отделение ↔ разрешённые должности**, отдельно от факта занятости.

### Рабочее имя сущности

Предпочтительно: **`org_unit_allowed_positions`**  
Альтернатива в документации: `department_positions` (legacy naming; в коде — `org_unit_id`).

### Целевая схема (draft)

```sql
CREATE TABLE public.org_unit_allowed_positions (
    org_unit_id   INTEGER NOT NULL REFERENCES public.org_units(unit_id) ON DELETE CASCADE,
    position_id   INTEGER NOT NULL REFERENCES public.positions(position_id) ON DELETE CASCADE,
    is_primary    BOOLEAN NOT NULL DEFAULT FALSE,  -- optional: типовая / основная для отдела
    sort_order    INTEGER NULL,
    effective_from DATE NULL,
    effective_to   DATE NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    INTEGER NULL REFERENCES public.users(user_id),
    PRIMARY KEY (org_unit_id, position_id)
);
```

Индексы: `(position_id)`, `(org_unit_id, sort_order)`.

### Три слоя в UI и API

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. Global catalog          public.positions                 │
│    CRUD: /directory/positions                               │
├─────────────────────────────────────────────────────────────┤
│ 2. Allowed for org unit    org_unit_allowed_positions       │
│    Admin: привязка должностей к отделению (future UI)       │
├─────────────────────────────────────────────────────────────┤
│ 3. Used in org unit        employees(org_unit_id, position) │
│    Derived: scoped GET /positions?org_unit_id= (existing)   │
└─────────────────────────────────────────────────────────────┘
```

### Рекомендуемая семантика API (future)

| Endpoint / param | Meaning |
|------------------|---------|
| `GET /positions` | Global catalog |
| `GET /positions?org_unit_id=N&scope=allowed` | Allowed for unit (from junction table) |
| `GET /positions?org_unit_id=N&scope=used` | Used by employees (current EXISTS behaviour) |
| `GET /positions?org_unit_id=N` (default TBD) | **Breaking change risk** — default should be documented explicitly in implementation ADR |

### Enrollment Wizard (future behaviour)

При наличии allowed-positions:

1. **Primary:** allowed for selected org unit;
2. **Secondary highlight:** subset already used (`scope=used`);
3. **Fallback:** global catalog только если allowed пуст *и* политика организации разрешает (config / privileged override);
4. Import `position_hint` — подсказка без auto-select (unchanged).

## Non-goals (this ADR)

- Нет миграции и реализации в Phase 3I hotfix track.
- Нет изменения текущего `GET /positions?org_unit_id=` semantics до отдельной фазы.
- Нет автоматического backfill allowed-positions из истории `employees` (optional follow-up script, not mandatory).

## Consequences

### If implemented

- Кадровик видит «штатное расписание» отдела до первого найма.
- Enrollment / create / transfer forms могут фильтровать по allowed, а не по факту занятости.
- Global catalog остаётся единым источником имён должностей (ADR-031).

### If deferred

- Phase 3I fallback на global catalog остаётся корректным минимальным решением.
- Риск: в fallback пользователь видит должности, не типичные для отдела (UX, не data integrity).

## Implementation phases (backlog)

| Phase | Scope |
|-------|--------|
| **F1 Schema** | Migration `org_unit_allowed_positions`, RBAC for maintain |
| **F2 Admin API** | CRUD junction; bulk import from org template |
| **F3 Read API** | `scope=allowed` / `scope=used`; deprecate ambiguous default |
| **F4 UI** | Org unit editor: «Должности отделения»; Positions sync runbook update |
| **F5 Consumers** | Enrollment Wizard, EmployeeCreateForm, EmployeeTransferForm, EmployeeDrawer |

## References

- ADR-031 — должность vs сотрудник vs роль
- ADR-045 — Phase 3I enroll-from-import
- `app/directory/positions_routes.py` — current `org_unit_id` filter (EXISTS employees)
- `corpsite-ui/.../ImportEnrollEmployeeWizard.tsx` — scoped + catalog fallback
- `docs/ops/POSITIONS_SYNC_RUNBOOK.md` — positions seed/sync

## Tracking

| Event | Date |
|-------|------|
| ADR proposed (Phase 3I hotfix audit) | 2026-06-22 |
| Interim fallback shipped (`103be25`) | 2026-06-22 |
