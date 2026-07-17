# ADR-057 — Control List Interchange Architecture

## Status

**Proposed / Ready for Architectural Review**

| Field | Value |
|-------|-------|
| Work Package | WP-CL-001 … WP-CL-013 (roadmap) |
| Parent | [ARCH-002](./ARCH-002-personnel-personal-record-architecture.md); [ADR-054](../adr/ADR-054-personnel-personal-record-aggregate-model.md) |
| Runtime effect (Phase 1) | **None** — WP-CL-001 is read-only workbook audit only |
| Related legacy | `scripts/import_hr_control_list.py` (Phase 0 dry-run; not canonical SoT) |

---

## 1. Назначение

**Control List Interchange** — ограниченный интеграционный контекст для обмена кадровыми данными между историческими Excel-файлами «Контрольный список» и canonical контуром Corpsite (PPR / Employment).

Контекст отвечает за:

| Направление | Ответственность |
|-------------|-----------------|
| Первичный анализ | Read-only профилирование исходных XLSX без изменения файла |
| Staging | Сохранение raw sheets / rows / cells с полной provenance |
| Нормализация | Специализированные парсеры по смысловым типам → normalized candidates |
| Review | Preview, исправления оператором, approve / reject |
| Provenance | Трассировка до файла, листа, строки, столбца, ячейки |
| Apply | Контролируемая запись в canonical контексты по import_run |
| Export | Обратное формирование Контрольного списка из canonical данных |

Control List Interchange **не является** владельцем кадровых данных. Это переходный и операционный мост для миграции накопленных ручных файлов и последующей регулярной выгрузки из системы.

---

## 2. Целевые направления

### 2.1. Импорт

```text
Excel (исторический Контрольный список)
  → control_list_import_run
  → raw sheets / rows / cells (staging)
  → mapping profile (лист / столбец → semantic field)
  → normalized candidates
  → review (HR operator / HR head)
  → apply events → canonical PPR / Employment / справочники
```

### 2.2. Экспорт

```text
canonical PPR + Employment (+ справочники)
  → control_list_export_profile (настраиваемый профиль выгрузки)
  → projection (column layout, filters, grouping)
  → XLSX (новый Контрольный список)
```

После наполнения системы **основной** Контрольный список формируется из canonical данных, а не из повторного копирования старого raw-текста Excel.

---

## 3. Архитектурные границы

| Контекст | Роль |
|----------|------|
| **Control List Interchange** | Источник, staging, разбор, сопоставление, preview, решения, provenance, export projection |
| **PPR (Personnel Personal Record)** | Владелец сведений Личной карточки (person-owned sections) |
| **Employment BC** | Владелец внутренних назначений, подразделений, должностей в operational contour |
| **Справочники** | Владельцы canonical значений (org units, positions, dictionaries) |

**Границы:**

- Импорт **не пишет** напрямую в canonical таблицы.
- После apply canonical данные живут **независимо** от исходного Excel.
- Исходный XLSX **никогда не изменяется** профилировщиком и import pipeline.
- Сложный входной парсинг — **переходный** миграционный инструмент; не постоянный SoT.
- Новый Контрольный список проецируется из normalized canonical данных, не из legacy raw cells.

---

## 4. Обязательные принципы

1. **Никакой прямой записи** из Excel в canonical таблицы.
2. **Последовательность:** raw staging → candidates → review → apply.
3. **Сохранение исходного значения** без потерь на уровне staging cell.
4. **Provenance** до файла, листа, строки, столбца и ячейки.
5. **Без угадывания** отсутствующих значений; пустое остаётся пустым.
6. **Специализированные парсеры** по смысловым типам (ИИН, телефон, дата, составной текст, образование, ПК).
7. **Идемпотентность** import_run и apply events.
8. **Защита от дублей** (технических и смысловых).
9. **Повторяемый импорт** с явным mapping profile.
10. **Откат по import_run** через зарегистрированные apply events.
11. **Ручная проверка** неоднозначных данных (probable match, conflict).
12. **Canonical система не зависит** от дальнейшего наличия исходного файла.
13. **Исходный файл never mutated** — SHA-256 до/после анализа обязателен для read-only инструментов.

---

## 5. Концептуальные сущности

Логическая модель Control List Interchange. Физическая staging schema — **WP-CL-002**; mapping profiles — **WP-CL-003**; person normalization — **WP-CL-004**; person matching — **WP-CL-005**; employment normalization — **WP-CL-006**; contacts normalization — **WP-CL-007**; education normalization — **WP-CL-008**; training normalization — **WP-CL-009**; other PPR fields normalization — **WP-CL-010**; review aggregate / apply plan — **WP-CL-011**; candidate persistence / apply execution — в последующих WP.

| Сущность | Назначение |
|----------|------------|
| `control_list_import_run` | Один запуск импорта: файл, SHA-256, конфигурация, статус, timestamps |
| `control_list_import_sheet` | Лист в рамках run: имя, индекс, status (analyzed / excluded), метаданные диапазона |
| `control_list_import_row` | Строка staging: row_index, row_class, raw snapshot |
| `control_list_import_cell` | Ячейка staging: column, raw_value, excel_type, number_format, issues |
| `control_list_mapping_profile` | Именованный профиль сопоставления для семейства книг |
| `control_list_mapping_profile_sheet` | Правила листа: personnel_category, employment_mode, header_row override |
| `control_list_mapping_profile_column` | Столбец → semantic field, parser hints |
| `control_list_import_candidate` | Нормализованный кандидат (Person slice, Employment slice, section payloads) |
| `control_list_review_item` | Review aggregate: candidates + match + issues + readiness + decision (WP-CL-011; in-memory foundation) |
| `control_list_apply_plan` | Декларативный план действий для одной review item (WP-CL-011; immutable, без mutation) |
| `control_list_import_decision` | Решение reviewer: approve, reject, edit, defer, merge |
| `control_list_apply_event` | Факт применения candidate в canonical store с rollback handle |
| `control_list_export_profile` | Профиль выгрузки: листы, колонки, фильтры, grouping из canonical |

### 5.1. Staging snapshot semantics (WP-CL-002)

Поля staging фиксируют **состояние профилировщика на момент `import_run`**, а не canonical mapping или истину системы:

| Поле (staging) | Семантика |
|----------------|-----------|
| `semantic_hint` (cell) | **Рекомендация** профилировщика WP-CL-001 (header alias). **Не** canonical column mapping; окончательное сопоставление — в `control_list_mapping_profile_column` (WP-CL-003+) после review |
| `personnel_category` (sheet) | Snapshot классификации листа на момент run |
| `employment_mode` (sheet) | Snapshot классификации листа на момент run; контекст листа, **не** атрибут Person |
| `sheet_purpose` (sheet) | Snapshot классификации листа на момент run |
| `inferred_type`, `issue_codes`, `row_kind` | Snapshot типизации/классификации профилировщика; не normalized canonical value |

**Инварианты:**

- Staging **не является Source of Truth** — canonical данные живут в PPR / Employment после controlled apply.
- Повторный импорт той же книги (даже с тем же SHA-256) с новой версией профилировщика может дать **другие** snapshot-значения classification / semantic_hint; каждый run хранит свой snapshot.
- Canonical mapping profile и reviewer decisions **не перезаписывают** staging snapshot retroactively.

### 5.2. Mapping profile semantics (WP-CL-003)

Mapping profile — **versioned configuration**, отдельный от staging snapshot и canonical PPR:

| Аспект | Формулировка |
|--------|--------------|
| Profile role | Конфигурация sheet/column → `semantic_field` + `parser_code` для будущего normalization pipeline |
| Not staging | Profile **не заменяет** staging snapshot; staging остаётся immutable per `import_run` |
| Not canonical | Profile **не пишет** в PPR / Employment; canonical данные создаются только после review/apply |
| Versioning | `(profile_code, profile_version)` обязателен; не более одного `active` на `profile_code` |
| Immutability | После публикации (`status = active` или `archived`) profile version **immutable**; правки только через новую version |
| Active change | Смена active profile — **только** создание новой version + archive предыдущей active |
| Import run binding | Будущий `import_run` ссылается на конкретную version (`profile_id` или `profile_code` + `profile_version`) |
| Historical runs | Существующие `import_run` **всегда** остаются привязаны к своей version; retroactive rebind запрещён |
| Vocabulary | `semantic_field` и `parser_code` — import-domain controlled vocabulary, **не** имена колонок PPR |
| vs `semantic_hint` | Staging `semantic_hint` = profiler recommendation; profile column = operator-approved configuration |

### 5.3. Person Candidate semantics (WP-CL-004)

Person Candidate — **temporary normalized import model**, не canonical Person / PPR:

| Аспект | Формулировка |
|--------|--------------|
| Role | Результат normalization pipeline: staging + mapping profile → normalized person slice |
| In-memory | Temporary domain model в памяти; **без** ORM / SQLAlchemy и **без** candidate persistence table |
| Not staging | Candidate не хранит raw cell snapshot; использует profile-driven mapping поверх staging values |
| Not canonical | Candidate **не является** Person aggregate и **не пишет** в PPR / Employment |
| No PPR ids | **Не содержит** `person_id`, `employee_id`, `candidate_id` и других ссылок на canonical PPR |
| Cardinality | Один `import_run` может породить **множество** Person Candidate (по data-строкам) |
| No matching | WP-CL-004 не выполняет поиск совпадений с existing Person |
| Field issues | Normalizers возвращают `issues`; пустые/ошибочные значения не угадываются |
| Downstream | Сопоставление с Person — **только** WP-CL-005; review, apply — последующие WP |

### 5.4. Person Match Result semantics (WP-CL-005)

Person matching — **read-only** слой между Person Candidate (WP-CL-004) и review/apply:

| Аспект | Формулировка |
|--------|--------------|
| Role | `PersonCandidate` → `PersonMatchResult` с `MatchStatus`, `MatchReason`, score/confidence |
| Read-only port | Доступ к `public.persons` только через `PersonMatchReadPort`; domain service **без** прямого SQL |
| No mutation | **Не создаёт** и **не изменяет** Person / PPR; **не выполняет** apply |
| No employee identity | `employee_id` **не используется** как идентичность человека |
| Matchable rows | Только `person_status IN ('active','inactive')`; merged — redirect через `resolve_survivor` |
| Auto recommendation | `recommended_person_id` только для `exact` IIN и single `probable` FIO+DOB; FIO-only — **без** auto-match |
| Downstream | Reviewer decisions, candidate persistence, apply — WP-CL-011+ |

### 5.5. Employment Candidate semantics (WP-CL-006)

Employment Candidate — **temporary normalized import model**, не canonical Employment / assignment:

| Аспект | Формулировка |
|--------|--------------|
| Role | Staging row + mapping profile + `PersonMatchResult` → `EmploymentCandidate` |
| In-memory | Temporary domain model; **без** ORM / SQLAlchemy и **без** Employment DB writes |
| Not canonical | **Не является** current assignment, `employees`, Position или OrgUnit |
| No employee identity | **Не использует** `employee_id` как идентичность человека |
| Person link | `matched_person_id` только при `exact`/`probable` match с `recommended_person_id` |
| Readiness | `normalization_ready` = person matched + source employment fields OK; **не** означает apply в Employment BC |
| Non-ready match | `ambiguous` / `invalid` / `not_found` **не блокируют** создание candidate |
| Resolution deferred | OrgUnit/Position lookup, assignment conflicts, rate/policy checks — последующие WP |
| employment_mode | Берётся из sheet snapshot (`primary` / `concurrent`); **не смешивается** между листами |
| No lookup | **Без** поиска Position / OrgUnit и **без** fuzzy matching |
| Downstream | Review / apply — WP-CL-011+ |

### 5.6. Contact Candidate semantics (WP-CL-007)

Contact Candidate — **temporary normalized import model**, не canonical Person contact record:

| Аспект | Формулировка |
|--------|--------------|
| Role | Staging row + mapping profile + `PersonMatchResult` → `ContactCandidate` |
| In-memory | Temporary domain model; **без** ORM / SQLAlchemy и **без** PPR contact writes |
| Not canonical | **Не является** canonical Person contact и **не выполняет** merge/update existing contacts |
| No employee identity | **Не использует** `employee_id` как идентичность человека |
| Person link | `matched_person_id` только при `exact`/`probable` match с `recommended_person_id` |
| Empty skip | Полностью пустые контактные значения → **no candidate** (skip), не пустая запись |
| Readiness | `normalization_ready` = person matched + contact fields normalized; **не** apply-ready |
| Phone reuse | Телефонная нормализация переиспользует WP-CL-004 `normalize_phone` |
| Downstream | Contact merge/update policy — последующие WP |

### 5.7. Education Candidate semantics (WP-CL-008)

Education Candidate — **temporary normalized import model**, не canonical `person_education` record:

| Аспект | Формулировка |
|--------|--------------|
| Role | Staging row + mapping profile + `PersonMatchResult` → `list[EducationCandidate]` |
| Cardinality | **1 staging row → 0..N** EducationCandidate (composite cell → несколько записей) |
| In-memory | Temporary domain model; **без** ORM / SQLAlchemy и **без** PPR education writes |
| Not canonical | **Не является** canonical education record и **не выполняет** dedup с `person_education` |
| No employee identity | **Не использует** `employee_id` как идентичность человека |
| Person link | `matched_person_id` только при `exact`/`probable` match с `recommended_person_id` |
| Empty skip | Пустая / technical-empty education cell → **пустой список** |
| Raw fragment | Каждый candidate **обязан** сохранять `raw_fragment` и cell provenance |
| Incomplete keep | Неполный / неразобранный фрагмент → candidate с issue, **не discard** |
| Readiness | `normalization_ready` = person matched + fragment parsed cleanly; **не** apply-ready |
| Split delimiters | Newline, `;`, `\|` — **не** каждая запятая |
| Downstream | Education apply / dedup policy — последующие WP |

### 5.8. Training Candidate semantics (WP-CL-009)

Training Candidate — **temporary normalized import model**, не canonical `person_training` record:

| Аспект | Формулировка |
|--------|--------------|
| Role | Staging row + mapping profile + `PersonMatchResult` → `list[TrainingCandidate]` |
| Cardinality | **1 staging row → 0..N** TrainingCandidate (composite cell → несколько записей) |
| In-memory | Temporary domain model; **без** ORM / SQLAlchemy и **без** PPR training writes |
| Not canonical | **Не является** canonical training record и **не выполняет** dedup с `person_training` |
| No employee identity | **Не использует** `employee_id` как идентичность человека |
| Person link | `matched_person_id` только при `exact`/`probable` match с `recommended_person_id` |
| Empty skip | Пустая / technical-empty training cell → **пустой список** |
| Raw fragment | Каждый candidate **обязан** сохранять `raw_fragment` и cell provenance |
| Conservative parse | `provider_name` только по **явным меткам**; title курса **не** становится provider |
| Incomplete keep | Неполный / неразобранный фрагмент → candidate с issue, **не discard** |
| Readiness | `normalization_ready` = person matched + fragment parsed cleanly; **не** apply-ready |
| Split delimiters | Newline, `;`, `\|` — **не** каждая запятая |
| Downstream | Training apply / dedup policy — последующие WP |

### 5.9. Other PPR Candidate semantics (WP-CL-010)

Other PPR Candidate — **temporary normalized import model** for PPR fields not covered by WP-CL-004…009:

| Аспект | Формулировка |
|--------|--------------|
| Role | Staging row + mapping profile + `PersonMatchResult` → `list[OtherPprCandidate]` |
| Cardinality | **1 staging row → 0..N** candidates (one per populated supported cell) |
| In-memory | Temporary domain model; **без** ORM / SQLAlchemy и **без** PPR writes |
| Scope | Citizenship, nationality, marital/military/disability summaries, awards, notes, qualification |
| Excluded | Employment, Contacts, Education, Training, core Person identity (WP-CL-004…009) |
| Raw value | Каждый candidate **обязан** сохранять `raw_value` без потери текста |
| Conservative | Controlled aliases only; **не** выдумывать значения из неоднозначного текста |
| Unsupported | Unknown semantic fields → candidate с issue, не silent discard |
| Readiness | `normalization_ready` = person matched + field normalized; **не** apply-ready |
| Downstream | PPR apply / dedup policy — последующие WP |

### 5.10. Review aggregate and apply plan semantics (WP-CL-011)

Review aggregate — **temporary in-memory assembly**, не canonical PPR/Employment:

| Аспект | Формулировка |
|--------|--------------|
| Role | Normalization + matching outputs → `ControlListReviewRun` / `ControlListReviewItem` |
| Cardinality | **1 staging data row → 1 review item**; candidates grouped strictly by provenance (`source_row_id`) |
| Not canonical | Review item **не является** Person, Employment или PPR record |
| Not staging | Review **не заменяет** staging snapshot; ссылается на candidates и match results |
| Issues | `blocking_issues` запрещают approve и executable apply plan; `non_blocking_issues` информируют оператора |
| Person match | `ambiguous` / `invalid` — **always blocking**; `not_found` — blocking для auto-apply, допускает только explicit `create_person` в plan (`is_ready=false`) |
| Slice readiness | `normalization_ready` отдельного candidate **не означает** готовность всего review item |
| Empty sections | Отсутствующие optional slices (employment, contacts, education, …) **не создают** ложные блокировки |
| Decision | `ReviewDecision` (`pending` / `approved` / `rejected` / `needs_correction`) — **отделено** от apply execution |
| Blocked + approved | **Запрещено** — blocked item нельзя перевести в `approved` |
| Approve ≠ apply | `approved` **не выполняет** mutation; только разрешает формирование executable plan |
| Apply plan | `ApplyPlan` — **immutable declarative** snapshot; `is_executable` **не означает**, что execution уже выполнен |
| Employment BC | `EmploymentCandidate` (primary **и** concurrent) → `resolve_assignment` в Employment BC; `employment_mode` передаётся в preconditions |
| Not external employment | `employment_mode=concurrent` на листе Control List = **внутреннее** совместительство / назначение в ММЦ ([ADR-056](../adr/ADR-056-employment-aggregate-architecture.md)); **не** `person_external_employment` |
| create_external_employment | Vocabulary element для явного источника **внешней** трудовой биографии; WP-CL-011 **не генерирует** его из WP-CL-006 |
| No mutation | WP-CL-011 **не пишет** в Person/PPR/Employment и **не вызывает** canonical repositories на mutation |
| Execution deferred | Фактический apply pipeline, transactions, idempotency persistence, rollback — **WP-CL-012+** |

---

## 6. Классификация листов

### 6.1. personnel_category

| Значение | Описание |
|----------|----------|
| `doctor` | Врачи |
| `nursing_staff` | Средний медперсонал (медсёстры и аналоги) |
| `junior_medical_staff` | Младший медперсонал |
| `other_staff` | Прочий персонал |
| `unknown` | Не определено |

### 6.2. employment_mode

| Значение | Описание |
|----------|----------|
| `primary` | Основное место работы |
| `concurrent` | Совместительство |
| `unknown` | Не определено |

### 6.3. sheet_purpose

| Значение | Описание |
|----------|----------|
| `personnel_control_list` | Кадровый контрольный лист |
| `declaration` | Декларация (отдельный контур) |
| `unknown` | Не определено |

### 6.4. employment_mode — не атрибут Person

**employment_mode** описывает контекст **исходного листа** и будущего **назначения (Employment projection)**, а не личность человека.

| Принцип | Формулировка |
|---------|--------------|
| Источник mode | `employment_mode` определяется из контекста исходного листа (и mapping profile), не из Person |
| Не Person attribute | **Запрещено** сохранять `employment_mode` как постоянную характеристику Person / PPR |
| Candidate scope | В import pipeline mode переносится в **candidate назначения** (`control_list_import_candidate` → Employment slice) |
| Dual presence | Один Person **может одновременно** иметь primary и concurrent назначения в canonical контуре |
| Export filter | Контрольный список, формируемый из canonical данных, должен поддерживать фильтр: `primary` / `concurrent` / `all` |
| Profile-driven | Пары листов («врачи» / «врачи совместители») задаются **mapping profile**, а не hardcode одной книги |

**Пример (рекомендация профилировщика WP-CL-001):**

| Лист | personnel_category | employment_mode | sheet_purpose |
|------|-------------------|-----------------|---------------|
| `врачи` | `doctor` | `primary` | `personnel_control_list` |
| `врачи совместители` | `doctor` | `concurrent` | `personnel_control_list` |

Provenance: mode живёт на `control_list_import_sheet`, `control_list_import_row`, candidate и export projection — **не** на Person aggregate.

### 6.5. Имя листа и excluded-листы

- **Имя листа** — атрибут источника (import metadata), **не** canonical характеристика Person.
- Листы, в имени которых содержится слово **«декларация»** (регистронезависимо, после trim и нормализации пробелов), на текущем этапе получают `status = excluded`, `exclusion_reason = sheet_name_declaration`.
- Excluded-листы **учитываются в инвентаризации** книги, но **не участвуют** в содержательном аналise, mapping и агрегированной статистике.
- Правило исключения — **явная конфигурация** (`exclude_sheet_name_contains`), не скрытая эвристика.

---

## 7. Сопоставление Person (WP-CL-005)

Реализовано как read-only matching layer (`PersonMatchingService`). Политика приоритетов:

| Уровень | MatchStatus | Политика |
|---------|-------------|----------|
| **Exact IIN** | `exact` | Валидный 12-значный ИИН → точное совпадение; `recommended_person_id` разрешён при отсутствии attribute conflict |
| **FIO + birth_date** | `probable` | Нормализованное ФИО + дата рождения → вероятное совпадение; `recommended_person_id` только при единственном hit |
| **Normalized FIO only** | `probable` / `ambiguous` | Слабое совпадение; **автоматический выбор запрещён** (`recommended_person_id = null`) |
| **Multiple hits** | `ambiguous` | Несколько подходящих Person → ручное решение reviewer |
| **IIN vs FIO/DOB conflict** | `invalid` | ИИН найден, но ФИО/дата рождения расходятся → без автоматического выбора |
| **No match** | `not_found` | Нет подходящих Person по доступным ключам |
| **Similar FIO / fuzzy** | — | **Запрещено** — fuzzy matching и auto-confirm не реализуются |

**Граница:** matching определяет outcome и confidence; финальное решение, правки оператора и apply — последующие WP (review UI, apply events).

---

## 8. Дедупликация

### 8.1. Технический дубль (внутри import_run)

- Fingerprint источника: `(sheet_name, row_index, column_set_hash)` или staging row id.
- Exact duplicate rows в одном run помечаются и не создают второй candidate без явного решения.

### 8.2. Смысловой дубль (относительно canonical)

- Fingerprint нормализованного кандидата: `(iin)` или `(normalized_fio, birth_date)` или section-level hash.
- Классификация:
  - **exact duplicate** — совпадение с существующей canonical записью;
  - **probable duplicate** — совпадение по probable ключу;
  - **conflict** — совпадение частичное, поля расходятся;
  - **new record** — новая запись.

---

## 9. Provenance и откат

- Каждая **применённая** canonical запись сохраняет `import_run_id` и ссылку на `control_list_apply_event`.
- Источник трассируется до **листа, строки, столбца, ячейки** staging.
- **Откат** по import_run:
  - работает по зарегистрированным apply events;
  - **не удаляет и не изменяет** данные, созданные пользователем вручную после импорта;
  - **не уничтожает** raw staging при частичном apply.
- Исходный XLSX остаётся вне системы или в immutable storage; canonical не зависит от его дальнейшего наличия.

---

## 10. RBAC (предварительно)

| Роль | Полномочия |
|------|------------|
| **Sysadmin** | Загрузка файла; запуск read-only анализа; настройка mapping profile; повторный запуск нормализации |
| **HR operator** | Проверка кадровых candidates; исправление распознанных значений; approve / reject на уровне записи |
| **HR head** | Утверждение набора импорта; запуск controlled apply; настройка и формирование итогового Контрольного списка (export) |

---

## 11. Поэтапная дорожная карта

| WP | Содержание |
|----|------------|
| **WP-CL-001** | Аудит книги и read-only профилировщик (текущий этап) |
| **WP-CL-002** | Staging schema |
| **WP-CL-003** | Mapping profiles |
| **WP-CL-004** | Идентификационные поля Person |
| **WP-CL-005** | Сопоставление Person |
| **WP-CL-006** | Подразделение, должность и назначение |
| **WP-CL-007** | Контакты |
| **WP-CL-008** | Образование |
| **WP-CL-009** | Повышение квалификации |
| **WP-CL-010** | Прочие PPR-поля (гражданство, семейное положение, воинский учёт, награды, категории) |
| **WP-CL-011** | Review aggregate + declarative apply planning foundation (in-memory; no canonical writes) |
| **WP-CL-011b** *(planned)* | Preview / review UI |
| **WP-CL-012** | Apply execution, rollback, audit, повторный импорт |
| **WP-CL-013** | Configurable Control List export |

---

## 12. Отложенные решения

Явно **не решаются** в ADR-057:

- Физическая staging schema (таблицы, индексы) — **WP-CL-002** (foundation реализован)
- Mapping profile persistence — **WP-CL-003** (foundation реализован; application pipeline — позже)
- Person matching thresholds beyond fixed tiers — **WP-CL-005** (foundation реализован)
- Конкретный frontend review UI — WP-CL-011b *(planned)*
- Apply execution / transaction commit — WP-CL-012
- Точные правила каждого PPR-парсера — WP-CL-004 … WP-CL-010
- Формат export templates — WP-CL-013
- Правила **обновления** существующих canonical записей vs create-only
- Policy автоматического apply без HR head approval
- Поддержка содержательного импорта листов «декларация»

---

## Связанные документы

- [WP-CL-001 — Source Workbook Audit](../implementation/WP-CL-001-source-workbook-audit.md)
- [WP-CL-002 — Staging Schema](../implementation/WP-CL-002-staging-schema.md)
- [WP-CL-003 — Mapping Profiles](../implementation/WP-CL-003-mapping-profiles.md)
- [WP-CL-004 — Person Normalization](../implementation/WP-CL-004-person-normalization.md)
- [WP-CL-005 — Person Matching](../implementation/WP-CL-005-person-matching.md)
- [WP-CL-006 — Employment Normalization](../implementation/WP-CL-006-employment-normalization.md)
- [WP-CL-007 — Contacts Normalization](../implementation/WP-CL-007-contacts-normalization.md)
- [WP-CL-008 — Education Normalization](../implementation/WP-CL-008-education-normalization.md)
- [WP-CL-009 — Training Normalization](../implementation/WP-CL-009-training-normalization.md)
- [WP-CL-010 — Other PPR Fields Normalization](../implementation/WP-CL-010-other-ppr-fields-normalization.md)
- [WP-CL-011 — Review and Apply Foundation](../implementation/WP-CL-011-review-and-apply-foundation.md)
- [ARCH-002 — Personnel Personal Record Architecture](./ARCH-002-personnel-personal-record-architecture.md)
- [ADR-054 — PPR Aggregate Model](../adr/ADR-054-personnel-personal-record-aggregate-model.md)
