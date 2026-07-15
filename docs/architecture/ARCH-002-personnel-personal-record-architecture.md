--------------------------------------------------

Document Status

Document:
ARCH-002

Title:
Personnel Personal Record Architecture

Type:
Master Architecture Document

Status:
Ready for Architectural Approval

Revision:
3

Repository Audit:
Completed

Purpose:
Defines the target personnel domain architecture.

--------------------------------------------------

# ADR-054 — Личный листок по учёту кадров как центральный объект кадрового контура

**Date:** 2026-07-15

## Классификация разделов

### Normative sections

Следующие разделы **определяют целевую архитектуру** и обязательны для
интерпретации настоящего документа:

-   Предметные определения
-   Архитектурные принципы
-   Границы агрегата
-   Архитектурные инварианты
-   Non-goals
-   Решение (предлагаемое)
-   Предполагаемая модель
-   Жизненный цикл
-   Импорт
-   Приказ HIRE
-   Карточка работника (положения о Composite View)

### Informative sections

Следующие разделы **объясняют контекст, обоснование и фактическое
состояние**; не изменяют нормативные положения:

-   Контекст
-   Problem Statement
-   Электронный личный листок (текущее состояние)
-   PMF как архитектурная основа развития
-   Открытые вопросы (Repository Audit Required)
-   Критерии принятия ADR
-   Repository Findings
-   Current Transitional Architecture
-   Migration Strategy
-   Architecture Variants
-   Open Architectural Decisions
-   Связанные документы
-   Указатель разделов

---

## Контекст

В кадровом контуре Corpsite смешиваются три различных понятия:

1.  Физическое лицо (**Person**);
2.  Трудовые отношения (**Employee**, **Employment Relationship**);
3.  Долговременное кадровое досье (**Personnel Personal Record**).

Подробные определения — в разделе «Предметные определения». Предметная
проблема — в разделе «Problem Statement».

Архитектурный аудит репозитория (2026-07-15) подтвердил наличие
отдельных элементов, приближающихся к целевой модели, но **единый
агрегат Personnel Personal Record как самостоятельный persistent-объект
отсутствует**. Сводка — «Repository Findings»; фактическая картина —
«Current Transitional Architecture».

---

## Предметные определения

Краткие определения ключевых понятий **целевой архитектуры**. Без
описания реализации.

| Понятие | Определение |
|---------|-------------|
| **Person** | Постоянная идентичность физического лица. Существует независимо от текущего трудоустройства. Не удаляется при увольнении. |
| **Personnel Personal Record** (Личный листок по учёту кадров) | Долговременное кадровое досье человека. Принадлежит Person. Содержит typed sections (образование, послужной список и др.). Центральный предметный объект кадрового контура. |
| **Candidate** | Состояние Person (или связанного Personnel Personal Record), при котором трудовые отношения ещё не установлены, но кадровое досье уже ведётся. |
| **Employee** | Операционная оболочка Corpsite для действующего или учтённого работника: доступ, задачи, уведомления, привязка к org structure. Может закрываться без уничтожения Person и Personnel Personal Record. |
| **Employment Relationship** | Трудовые отношения Person с организацией в определённый период. Выражается назначениями, Personnel Orders и employee events; не является хранилищем кадровой биографии. |
| **Employee Card** | Композиционное UI-представление, объединяющее Personnel Personal Record, Employment Relationship, Personnel Orders, employee events и операционный контекст. Не master-storage. |
| **HR Dossier** | Кадровое представление Employee Card в контуре «Кадровые процессы»; read/edit HR data. Подмножество или режим Employee Card, ориентированный на кадровые сведения. |
| **Personnel Orders** | Юридически значимые кадровые приказы (HIRE, TRANSFER, TERMINATION и др.). Относятся к Employment Relationship, не к разделам Personnel Personal Record. |
| **Control Output** | Производный организационный документ (контрольный выходной список), формируемый из актуального среза Personnel Personal Record и Employment Relationship. Не первичный источник данных. |
| **PMF** (Personnel Migration Framework) | Контур controlled migration: перенос проверенных данных из staging в person-owned typed sections Personnel Personal Record. |
| **Import Profile** | Переходное структурированное представление разделов, полученных из внешнего import (контрольный список). Staging artifact; не целевой aggregate. |
| **Transitional Architecture** | Фактическая промежуточная модель репозитория (import-first, employee-centric staging). Не целевая архитектура ARCH-002. |

> **Согласованность с ADR-047:** в связанном документе используется термин
> *Personal File* для того же предметного слоя. В ARCH-002 для целевой
> модели закреплён термин **Personnel Personal Record**.

---

## Problem Statement

### Почему появилась новая архитектура

Настоящий документ фиксирует **предметную проблему**, а не историю
разработки.

1.  **Import-first восприятие.** Импорт контрольного списка стал
    восприниматься как главный канал наполнения кадровых данных, хотя
    по предметной модели import — bootstrap и сверка, а не source of
    truth.

2.  **Employee Card как хранилище.** Employee Card начала выполнять
    роль master-storage кадровых сведений, смешивая досье человека с
    операционным контекстом должности.

3.  **Отсутствие постоянного объекта Candidate.** Candidate не имел
    устойчивого Personnel Personal Record до найма; анкета и operational
    контур существовали отдельно.

4.  **HIRE привязан к Employee.** Приказ о приёме оказался зависим от
    заранее существующей записи Employee, а не от выбора Person /
    Personnel Personal Record.

5.  **Control Output как источник.** Контрольный список использовался как
    input, хотя по предметной модели Control Output — производный
    документ из Personnel Personal Record.

6.  **Частичная person-owned модель.** Person-owned sections реализованы
    фрагментарно (через PMF pilot), без единого aggregate boundary.

7.  **Отсутствие единого кадрового агрегата.** Разделы личного листка
    распределены по JSON staging, employee overrides и отдельным person-owned
    tables без общей предметной границы.

Целевая архитектура восстанавливает разделение: **Person → Personnel
Personal Record → Employment Relationship**, с import и UI как
вторичными контурами.

---

## Архитектурные принципы

1.  **Single Source of Truth.** Каждый класс кадровых сведений имеет один
    authoritative store в границах Personnel Personal Record или
    Employment Relationship — не дублируется в UI и import без явного
    provenance.

2.  **Один личный листок на одного человека.** У Person — ровно один
    Personnel Personal Record на весь lifecycle (Candidate, Employee,
    Former Employee).

3.  **Person и Employment Relationship разделены.** Идентичность и
    кадровая биография не зависят от текущей должности; Employee может
    закрываться и создаваться заново без потери Personnel Personal Record.

4.  **Candidate и Employee используют один Personnel Personal Record.**
    Переход в Employment Relationship не создаёт новый листок и не
    копирует анкету.

5.  **Документы используют snapshot.** Печатные формы, Personnel Orders
    и exports фиксируют snapshot на момент формирования; не перезаписывают
    authoritative data.

6.  **UI не является master-storage.** Employee Card, HR Dossier и формы
    редактирования — представления и command surface, не источник истины.

7.  **Import не определяет архитектуру хранения.** Import Profile и
    staging — канал загрузки и сверки; целевая модель хранения задаётся
    Personnel Personal Record и PMF, а не форматом Excel.

8.  **Employee Card — представление.** Composite View над Personnel
    Personal Record, Employment Relationship, Personnel Orders и
    операционным контекстом.

9.  **Control Output — производный документ.** Формируется из Personnel
    Personal Record (и при необходимости Employment Relationship
    snapshot), не наоборот.

10. **Предметная модель первична.** Структура таблиц, API и UI
    подчиняются границам агрегата и инвариантам настоящего документа, а
    не текущему import pipeline.

---

## Границы агрегата

### Что входит в Personnel Personal Record

| Раздел | Примечание |
|--------|------------|
| Персональные данные | ФИО, дата рождения, пол, гражданство, контакты |
| Образование | Дипломы, специальности, учебные заведения |
| Родственники | Близкие родственники по форме личного листка |
| Семейное положение | Состав семьи |
| Послужной список | Трудовая биография до и вне текущего Employment Relationship |
| Обучение | Курсы, повышение квалификации |
| Языки | Владение иностранными языками |
| Квалификации | Категории, сертификаты как кадровые credentials |
| Награды | Государственные и иные награды |
| Прочие кадровые сведения | Разделы официальной формы, не отнесённые к Employment Relationship |

Все перечисленные разделы **переживают** смену должности, увольнение и
повторный найм.

### Что НЕ входит в Personnel Personal Record

| Объект | Почему не входит |
|--------|------------------|
| Должность, подразделение, штатное назначение | Относятся к **Employment Relationship** — меняются Personnel Orders, не к биографии |
| Position Cabinet | Операционный контур должности (задачи, статистика); см. ARCH-001 |
| Задачи, маршрутизация документов | Operational workflow, не кадровое досье |
| Права доступа, учётная запись | Operational security; привязаны к Employee / User |
| Personnel Orders | Юридические акты Employment Relationship; хранятся в контуре приказов |
| Employee events | Append-only журнал employment lifecycle (HIRE, TRANSFER, TERMINATION) |
| Control Output (как artifact) | Производный export; не часть aggregate, а результат проекции |

Разделение обеспечивает: кадровая биография остаётся у Person; текущее
положение в организации — у Employment Relationship; UI собирает оба
слоя в Employee Card.

---

## Архитектурные инварианты

После внедрения целевой архитектуры **независимо от реализации** должны
оставаться истинными:

| ID | Инвариант |
|----|-----------|
| INV-1 | Один **Person** — одна постоянная идентичность на физическое лицо. |
| INV-2 | Один **Personnel Personal Record** на Person на весь lifecycle. |
| INV-3 | Personnel Personal Record **не копируется** при HIRE, transfer или повторном найме. |
| INV-4 | **Employment Relationship** не хранит кадровую биографию (образование, послужной список, родственники и т.д.). |
| INV-5 | **Employee Card** не становится source of truth; только Composite View. |
| INV-6 | **Документы и exports** используют snapshot; изменение snapshot не изменяет authoritative record без явной команды. |
| INV-7 | **Control Output** строится из Personnel Personal Record (и при необходимости Employment Relationship projection), не является первичным input. |
| INV-8 | **Import Profile** не заменяет Personnel Personal Record; допустим только как transitional/bootstrap channel. |
| INV-9 | **Personnel Orders** изменяют Employment Relationship, не разделы Personnel Personal Record (кроме явно регламентированных post-hire append, напр. награды после приёма — как отдельные section updates с provenance). |

---

## Non-goals

ARCH-002 **не определяет**:

-   физическую структуру таблиц и схему БД;
-   детали ORM, миграций Alembic и mapping;
-   конкретные REST/GraphQL endpoints;
-   layout PDF личного листка и Control Output;
-   структуру экранов, вкладок и навигации UI;
-   порядок и длительность технических миграций;
-   детали PMF Commit Engine, plugins и transaction boundaries;
-   frontend component tree и state management;
-   выбор Architecture Variant (A / B / C) — см. Open Architectural Decisions;
-   интеграцию с внешними HRIS и EDS.

Эти аспекты описываются в последующих ADR, work packages и технических
спецификациях **в рамках** инвариантов настоящего документа.

---

## Решение (предлагаемое)

Целевая архитектура предусматривает **Personnel Personal Record** как
центральный предметный объект кадрового контура (см. «Архитектурные
принципы», «Архитектурные инварианты»).

Краткая сводка:

-   Personnel Personal Record принадлежит **Person**, создаётся до
    Employment Relationship, используется Candidate, Employee и Former
    Employee (INV-2, INV-3, INV-4).
-   **Employee Card** — Composite View (принцип 8, INV-5).
-   **Control Output** — производный документ (принцип 9, INV-7).
-   **PMF** — controlled migration в разделы Personnel Personal Record
    (принцип 7).
-   **HIRE** выбирает Person / Personnel Personal Record Candidate, не
    требует предварительного Employee (см. «Приказ HIRE»; детали
    redesign — OAD-5).

> **Scope.** Нормативные положения описывают **целевую архитектуру**.
> Фактическое состояние — «Repository Findings», «Current Transitional
> Architecture».

---

## Предполагаемая модель

``` text
Person
    │
    └── Personnel Personal Record (Личный листок)
            ├── Персональные сведения
            ├── Контакты
            ├── Семья и родственники
            ├── Образование
            ├── Послужной список
            ├── Курсы и обучение
            ├── Квалификации
            ├── Языки
            ├── Награды
            └── Прочие кадровые разделы

                    │
                    └── Employment Relationship(s)
                            │
                            ├── Assignments
                            ├── Personnel Orders
                            ├── Employee Events
                            └── Position Cabinet
```

Границы разделов — «Границы агрегата».

---

## Жизненный цикл

``` text
CANDIDATE
    ↓
EMPLOYEE
    ↓
FORMER_EMPLOYEE
```

Переходы **не создают** новый Personnel Personal Record (INV-2, INV-3).
Представление lifecycle Candidate — OAD-2.

---

## Импорт

Целевая формулировка:

> Импорт кадровых данных в личный листок по учёту кадров.

Каждый раздел Personnel Personal Record имеет статус полноты и проверки.
Import не определяет storage architecture (принцип 7, INV-8).

Transitional: import → Import Profile / JSON staging — «Current
Transitional Architecture», «Migration Strategy».

---

## Приказ HIRE

Целевая архитектура: приказ HIRE выбирает Person / Personnel Personal
Record Candidate, не требует предварительного Employee (см. Problem
Statement, п. 4).

Currently implemented: HIRE привязан к Employee — transitional
architecture («Repository Findings»). Redesign — OAD-5, «Migration
Strategy», этап 5.

---

## Карточка работника

Employee Card и HR Dossier — **Composite View** (см. «Предметные
определения»; принцип 8; INV-5). Объединяют:

-   Personnel Personal Record;
-   Employment Relationship (назначение, должность);
-   Personnel Orders;
-   employee events;
-   операционный контекст (доступ, documents workflow).

### Employee Card как Composite View (подтверждено аудитом)

Аудит подтвердил: HR Dossier **currently implemented** as Composite View
— **aligned with target architecture**. UI агрегирует operational и
кадровые разделы из нескольких источников; единого store Personnel
Personal Record нет.

**Gap (transitional):** не все разделы Personnel Personal Record
отображаются в HR Dossier; portfolio из Import Profile не включён.
Это transitional gap, не отмена принципа Composite View.

---

## Электронный личный листок

### Целевая архитектура

Единый aggregate **Personnel Personal Record** — typed sections, lifecycle,
identity (explicit entity или Person-as-root — OAD-1, «Architecture
Variants»).

### Текущее состояние (по результатам аудита)

Единый aggregate **не подтверждён**. Существуют transitional building
blocks:

| Компонент | Роль |
|-----------|------|
| Import Profile | Staging; partial section mimic |
| JSON staging | Temporary store pre-PMF |
| Employee overrides | Employee-scoped editable portfolio |
| PMF | Migration path to person-owned sections |
| Person-owned sections (pilot) | Education, training — post-commit |
| Import Profile UI | Section form; no aggregate ID |

Вывод: migration target, не full target implementation («Repository
Findings»).

---

## PMF как архитектурная основа развития (подтверждено аудитом)

PMF **currently operates around Person**: person-owned tables (education,
training), personnel record events, controlled commit. **Aligned with
target direction** — architectural foundation for expanding Personnel
Personal Record sections via PMF domains.

Pilot: domain education enabled; roadmap sections — «Repository
Findings», «Migration Strategy».

---

## Открытые вопросы (Repository Audit Required)

> **Статус:** аудит завершён (2026-07-15). Ответы — «Repository Findings»,
> «Open Architectural Decisions». Раздел сохранён для трассируемости.

| Вопрос | Ответ (кратко) |
|--------|----------------|
| Электронный личный листок — persistent object? | Нет — см. «Электронный личный листок» |
| Person vs отдельный Personnel Personal Record? | OAD-1 |
| Роль Employee? | Operational shell — «Repository Findings» |
| Lifecycle Candidate? | Target only — OAD-2 |
| Разделы личного листка? | Частично — «Repository Findings» |
| PMF и Personnel Personal Record? | Transitional bridge — «PMF как архитектурная основа» |
| Control Output? | Target: export from Personnel Personal Record; current: import input |
| Терминология vs модель? | «Migration Strategy», OAD |

---

## Критерии принятия ADR

Архитектурный аудит выполнен. Документ содержит нормативные и
информативные разделы (см. «Классификация разделов»).

**Status:** Ready for Architectural Approval. Утверждение как Master
Architecture Document — после закрытия Open Architectural Decisions и
выбора Architecture Variant.

---

## Repository Findings

Сводка read-only аудита (2026-07-15). **Personnel Personal Record** =
целевой aggregate; **Import Profile** = transitional artifact.

### Подтверждено аудитом

-   Person и Employee — раздельные понятия (schema level).
-   Employee Card / HR Dossier — Composite View (target-aligned).
-   PMF — controlled migration в person-owned sections.
-   Personnel Orders — HIRE, TRANSFER, TERMINATION → employee events.
-   Employee History — append-only employee events.
-   employee_identities — persistent IIN (employee-scoped).
-   Import pipeline — Control Output Excel as **input** (transitional).
-   Control list ≠ official Personnel Personal Record form (ADR-047
    appendix aligned).

### Частично реализовано

-   Import Profile — JSON + UI; ~45% official form sections.
-   Personnel Personal Record sections: education, training (person-owned
    post-PMF); остальное — JSON staging.
-   HIRE — Personnel Orders с привязкой к Employee (transitional).
-   Enrollment — import path + admin queue; partial person→employee bridge.
-   Control Output — import in + canonical roster export; not
    Personnel-Personal-Record-derived.

### Не реализовано

-   Единый aggregate Personnel Personal Record (dedicated ID / boundary).
-   Candidate lifecycle domain states.
-   Candidate intake form.
-   Person-scoped Import Profile.
-   HIRE by Person / Personnel Personal Record without Employee.
-   Control Output as Personnel-Personal-Record-derived export.
-   Personnel Personal Record PDF / print.
-   Sections: relatives, marital, military, languages, structured service
    record, birthplace, photo и др.

---

## Current Transitional Architecture

**Not target architecture.** Factual pipeline at audit time:

``` text
Import (Control Output Excel as input)
    ↓
JSON staging
    ↓
Import Profile
    ↓
Employee overrides
    ↓
PMF
    ↓
Person-owned sections (pilot)
    ↓
Employee Card / HR Dossier (Composite View)
    ↓
Personnel Orders → Employee events
    ↓
Reports (canonical Excel, order PDF; not Personnel Personal Record PDF)
```

Характеристики: import-first; employee-centric staging; PMF as bridge;
HIRE on Employee; Control Output as input. Target inverts to **Person →
Personnel Personal Record → Employment Relationship** («Предполагаемая
модель»).

---

## Migration Strategy

Architectural stages (no implementation detail):

``` text
1. Current Import Profile     → bootstrap; not SoT
2. Person-owned sections      → expand PMF domains
3. Personnel Personal Record  → aggregate (OAD-1)
4. Candidate lifecycle        → OAD-2
5. HIRE redesign              → OAD-5
6. Control Output             → OAD-4
```

Principles: non-breaking; PMF-first expansion; dual-write period;
terminology alignment to Personnel Personal Record.

---

## Architecture Variants

Audit **does not decide** variant. Final choice — Open Architectural
Decisions.

### Variant A: Person → Personnel Personal Record → Employment

Explicit Personnel Personal Record entity with own ID.

| | |
|-|-|
| **Strengths** | Strong Candidate/rehire; clear business object; clean HIRE |
| **Weaknesses** | Largest scope; Person↔Personnel Personal Record boundary risk |
| **Impact** | High schema/API/UI change |

### Variant B: Person as Aggregate Root

Typed sections on Person; Personnel Personal Record = logical view.

| | |
|-|-|
| **Strengths** | Fits existing person-owned tables; lower scope; PMF-aligned |
| **Weaknesses** | No explicit aggregate ID; Person metadata overload risk |
| **Impact** | Medium change |

### Variant C: Import Profile + PMF as root

No Person-bound aggregate; re-scope staging.

| | |
|-|-|
| **Strengths** | Minimal delta to current code |
| **Weaknesses** | Weak Candidate/rehire; import-first persists; misses INV-2, INV-7, INV-8 |
| **Impact** | Low change; **does not satisfy target architecture** |

---

## Open Architectural Decisions

Следующие решения **не закрыты** настоящим документом и требуют
отдельного архитектурного или бизнес-решения:

| ID | Question | Note |
|----|----------|------|
| OAD-1 | **Personnel Personal Record ID** — отдельная сущность (Variant A) или logical view на Person (Variant B)? | Связано с «Architecture Variants» |
| OAD-2 | **Candidate lifecycle** — enum, status на Person, или отдельная сущность? | Target lifecycle задан; representation open |
| OAD-3 | **Import Profile migration** — cutover strategy, dual-write duration | «Migration Strategy» |
| OAD-4 | **Control Output** — format, subset Personnel Personal Record, relation to canonical export | Target: derived export (INV-7) |
| OAD-5 | **HIRE redesign** — Person-first vs Employee prerequisite | Target: Person-first; implementation open |
| OAD-6 | Unified HIRE vs enroll-from-import event path | Два transitional paths |
| OAD-7 | Import-first permanent vs legacy-only after cutover | «Migration Strategy» |
| OAD-8 | Phase 1 in-scope sections (relatives, military, languages) | «Границы агрегата» — full catalog |

**Исключено из OAD** (закрыто текстом документа):

-   Employee Card as Composite View — подтверждено аудитом, нормативно
    зафиксировано (принцип 8, INV-5).
-   PMF as Person-centric migration path — подтверждено аудитом,
    информативно зафиксировано.
-   Variant C as target — отклонён normatively («Architecture Variants»).

---

## Связанные документы

| Document | Relation |
|----------|----------|
| [ADR-047 — Personnel Personal File](../adr/ADR-047-personnel-personal-file-architecture.md) | Same subject layer; uses term *Personal File* |
| [ADR-048 — Person Ownership](../adr/ADR-048-person-ownership-identity-creation-policy.md) | Person persistence across rehire |
| [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md) | PMF technical framework |
| [ADR-047 Four-Layer Model](../adr/ADR-047-appendix-four-layer-model.md) | Control list vs official form analysis |

---

## Указатель разделов

| Тема | Раздел |
|------|--------|
| Классификация | Классификация разделов |
| Определения | Предметные определения |
| Зачем документ | Problem Statement |
| Правила | Архитектурные принципы, Архитектурные инварианты |
| Границы aggregate | Границы агрегата |
| Вне scope | Non-goals |
| Target model | Предполагаемая модель, Решение |
| Audit facts | Repository Findings |
| As-is | Current Transitional Architecture |
| Roadmap | Migration Strategy |
| Options | Architecture Variants, OAD |
