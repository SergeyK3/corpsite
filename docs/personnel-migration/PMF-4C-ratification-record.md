# PMF-4C — Ratification Record

| Поле | Значение |
|------|----------|
| **Тип документа** | Architecture Ratification Record |
| **Статус** | **Approved** |
| **Дата** | 2026-07-08 |
| **Work Package** | PMF-4C (Entry Architecture) |

## Основа

| Документ | Роль |
|----------|------|
| [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md) | Ratified framework |
| [ADR-EDU-001](../adr/ADR-EDU-001-employee-education-migration-architecture.md) | First domain plugin |
| [PMF-4A-migration-wizard-design.md](./PMF-4A-migration-wizard-design.md) | Wizard UX design |
| PMF-4B | Navigation + shell (implemented) |
| PMF-4B.1 | HR-first UX polish (implemented) |
| [PMF-4C-entry-architecture.md](./PMF-4C-entry-architecture.md) | Entry layer contract |
| PMF-4C Pre-Implementation Architecture Review | Dual entry verdict |
| Architecture Consistency Review | Consistency gate (2026-07-08) |

---

## 1. Purpose

Настоящий документ фиксирует завершение архитектурной подготовки PMF-4C и разрешает переход к реализации.

- Документ **не вводит** новых архитектурных решений.
- Документ фиксирует **принятое состояние** архитектуры.

---

## 2. Review Summary

Проведены:

- Architecture Review (PMF-4A, ADR alignment)
- Pre-Implementation Architecture Review (dual entry model)
- Architecture Consistency Review (`PMF-4C-entry-architecture.md`)

Полученные результаты:

| Severity | Count |
|----------|-------|
| Critical | 0 |
| Major | 3 |
| Minor | 6 |
| Editorial | 3 |

---

## 3. Review Outcome

Рассмотрение показало:

- архитектурных противоречий не обнаружено;
- PMF соответствует [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md);
- PMF соответствует [ADR-EDU-001](../adr/ADR-EDU-001-employee-education-migration-architecture.md);
- Entry Architecture согласована с PMF-4B.1;
- Commit Engine остаётся единственной точкой записи;
- Dual Entry Model признана корректной.

---

## 4. Accepted Decisions

Утверждаются следующие решения.

### 4.1 Primary Entry

```text
Import
  ↓
Review
  ↓
Transfer to Personnel Record
  ↓
Migration Wizard
  ↓
Commit
```

### 4.2 Secondary Entry

```text
Personnel Processes
  ↓
Migration
  ↓
Employee
  ↓
Migration Wizard
```

### 4.3 Migration Home

Migration Home является **Dashboard PMF**.

Он **не является** основной рабочей точкой входа для пилотного процесса.

### 4.4 Migration Session

Migration Session является **единственной рабочей сессией** Wizard независимо от точки входа.

Канонический route: `/directory/personnel/migration/{domainCode}/{employeeId}` (см. [PMF-4C-entry-architecture.md §8](./PMF-4C-entry-architecture.md#8-navigation)).

### 4.5 Draft Run

Draft Run создаётся **автоматически** при открытии Migration Session.

Пользователь **не инициирует** создание Run вручную.

### 4.6 UX Boundary

HR-пользователь **не взаимодействует** напрямую с:

- Migration Run
- Commit Engine
- `person_*` tables (как терминология UI)
- plugin registry
- техническими lifecycle-состояниями

Технические термины допустимы только в блоке «Техническая информация» (PMF-4B.1).

---

## 5. Accepted Review Findings

**Major** замечания признаны **документационными**.

Они **не требуют** изменения архитектуры.

Синхронизация документации (PMF-4A §4, ADR-PMF-001 §4.2 CTA text, README index) может выполняться **отдельно** и не блокирует реализацию.

**Minor** и **Editorial** замечания не блокируют реализацию.

| ID | Severity | Resolution |
|----|----------|------------|
| M1 | Major | PMF-4C authoritative for entry routes; PMF-4A sync deferred |
| M2 | Major | Path-based `employee_id` canonical per PMF-4C §9.4; ADR §4.2 editorial sync deferred |
| M3 | Major | Resolved by this ratification record |

---

## 6. Architecture Authority

Для **Entry Layer** источником истины является:

**[PMF-4C-entry-architecture.md](./PMF-4C-entry-architecture.md)**

При расхождении с более ранними проектными документами (включая PMF-4A §4.2, ADR-PMF-001 §4.2 CTA URL) применяется **PMF-4C Entry Architecture**.

---

## 7. Authorization for Implementation

Архитектурная подготовка PMF-4C считается **завершённой**.

Разрешается переход к реализации следующих Work Packages **без дополнительного архитектурного проектирования**:

| WP | Scope |
|----|-------|
| **PMF-4C** | Session Bootstrap |
| **PMF-4D** | Mapping Workspace |
| **PMF-4E** | Commit UX |
| **PMF-4F** | History |

---

## 8. Closure

Архитектурная фаза Migration Wizard Entry Layer считается **завершённой**.

Дальнейшие изменения Entry Architecture допускаются только через amendment соответствующих архитектурных документов (PMF-4C-entry-architecture rev. 2 или ADR amendment).

---

## Status

**Architecture Ready for Implementation**

---

## Status Log

| Date | Event |
|------|-------|
| 2026-07-08 | PMF-4C Entry Architecture drafted |
| 2026-07-08 | Architecture Consistency Review completed (0 Critical) |
| 2026-07-08 | **Approved** — Architecture Ready for Implementation |
