--------------------------------------------------

Document Status

Document:
WP-CL-002-staging-schema

Title:
Control List Staging Schema — Raw Workbook Persistence

Type:
Implementation Work Package

Status:
Ready for Review

Date:
2026-07-17

Work Package:
WP-CL-002

Parent:
[ADR-057](../architecture/ADR-057-control-list-interchange-architecture.md)

Runtime effect:
**Schema + repository foundation only** — no mapping, parsing, apply, API, or PPR mutations

--------------------------------------------------

# WP-CL-002 — Staging Schema

## 1. Цель

Создать физический **staging-слой** для хранения сырого содержимого Excel-книги «Контрольный список» до нормализации и apply.

Staging фиксирует provenance на уровне **run → sheet → row → cell** и не заменяет canonical хранилища PPR / Employment.

## 2. Область

| In scope | Out of scope |
|----------|--------------|
| Alembic migration `x3y4z5a6b7c8` | Mapping profiles (WP-CL-003) |
| SQLAlchemy ORM | Parsing / normalization pipeline |
| Minimal staging repository | Apply в canonical (WP-CL-011+) |
| Schema / FK / cascade tests | API / frontend |
| | Изменения PPR / Employment aggregates |

## 3. Таблицы

### 3.1. `control_list_import_runs`

**Назначение:** один запуск загрузки исходной книги в staging.

| Поле | Описание |
|------|----------|
| `import_run_id` | PK |
| `source_filename` | Имя исходного XLSX |
| `source_sha256` | SHA-256 файла (64 hex, lowercase) |
| `imported_at` | Timestamp загрузки |
| `imported_by` | FK → `users.user_id` (RESTRICT) |
| `profiler_version` | Версия профилировщика WP-CL-001 |
| `status` | `staged` / `failed` / `cancelled` |

**Индексы:** `(status, imported_at)`, `(source_sha256, imported_at)`, `(imported_by, imported_at)`.

### 3.2. `control_list_import_sheets`

**Назначение:** snapshot одного листа книги в рамках run.

| Поле | Описание |
|------|----------|
| `sheet_id` | PK |
| `import_run_id` | FK → run (CASCADE) |
| `sheet_name` | Имя листа Excel |
| `sheet_index` | Порядковый индекс (0-based) |
| `personnel_category` | Snapshot классификации листа **на момент import_run** (рекомендация профилировщика; не canonical) |
| `employment_mode` | Snapshot классификации листа **на момент import_run** (контекст листа; не атрибут Person) |
| `sheet_purpose` | Snapshot классификации листа **на момент import_run** (рекомендация профилировщика; не canonical) |
| `status` | analyzed / excluded |

**Уникальность:** `(import_run_id, sheet_index)`, `(import_run_id, sheet_name)`.

`employment_mode` — **контекст листа**, не атрибут Person (ADR-057 §6.4). Значения `personnel_category`, `employment_mode`, `sheet_purpose` могут отличаться при повторном import_run той же книги после улучшения профилировщика.

### 3.3. `control_list_import_rows`

**Назначение:** snapshot строки Excel с классификацией вида строки.

| Поле | Описание |
|------|----------|
| `row_id` | PK |
| `sheet_id` | FK → sheet (CASCADE) |
| `excel_row_number` | Номер строки Excel (1-based) |
| `row_kind` | empty / header / title / footer / data / section_header / unknown |
| `section_key` | Ключ секции (nullable) |
| `section_caption` | Подпись секции (nullable) |

**Уникальность:** `(sheet_id, excel_row_number)`.

### 3.4. `control_list_import_cells`

**Назначение:** snapshot ячейки с raw value и метаданными типизации.

| Поле | Описание |
|------|----------|
| `cell_id` | PK |
| `row_id` | FK → row (CASCADE) |
| `column_letter` | Буква столбца (A, B, …) |
| `column_index` | Индекс столбца (1-based) |
| `raw_header` | Заголовок столбца (nullable) |
| `raw_value` | Исходное текстовое значение |
| `normalized_text` | Нормализованный текст (nullable) |
| `inferred_type` | Snapshot типизации профилировщика (WP-CL-001 vocabulary); не canonical type |
| `issue_codes` | JSONB array issue codes (snapshot профилировщика) |
| `semantic_hint` | **Рекомендация** профилировщика (header alias, напр. `person.iin`); **не** canonical mapping |
| `is_composite` | Признак составной ячейки (snapshot профилировщика) |

**Уникальность:** `(row_id, column_index)`.

## 3.5. Profiler snapshot vs canonical mapping

Staging хранит **immutable snapshot** результатов профилировщика на момент `import_run`. Эти поля **не являются Source of Truth**:

| Поле | Что фиксируется | Что это **не** |
|------|-----------------|----------------|
| `semantic_hint` | Рекомендация header alias от WP-CL-001 | Canonical column → semantic field mapping (`control_list_mapping_profile_column`, WP-CL-003+) |
| `personnel_category` | Классификация листа на момент run | Постоянная характеристика Person / PPR |
| `employment_mode` | Классификация листа на момент run | Атрибут Person; canonical Employment record |
| `sheet_purpose` | Классификация листа на момент run | Canonical document classification |
| `inferred_type`, `issue_codes`, `row_kind` | Типизация/классификация профилировщика | Normalized canonical value |

**Повторный импорт:** та же книга (в т.ч. с тем же `source_sha256`), загруженная в новый `import_run` после обновления профилировщика, может получить **иные** snapshot-значения. Старый run сохраняет свой snapshot; staging не обновляется retroactively.

**Canonical mapping** появляется только в mapping profile (WP-CL-003+) и подтверждается reviewer / apply pipeline — отдельно от staging snapshot.

## 4. Связи и ON DELETE

```text
users
  └── control_list_import_runs (imported_by, RESTRICT)
        └── control_list_import_sheets (CASCADE)
              └── control_list_import_rows (CASCADE)
                    └── control_list_import_cells (CASCADE)
```

| FK | ON DELETE | Обоснование |
|----|-----------|-------------|
| `runs.imported_by → users` | RESTRICT | Сохранить audit trail; запретить удаление пользователя с активными staging runs |
| `sheets → runs` | CASCADE | Staging — ephemeral per run; удаление run удаляет весь snapshot |
| `rows → sheets` | CASCADE | Строки не существуют без листа |
| `cells → rows` | CASCADE | Ячейки не существуют без строки |

## 5. Lifecycle

1. **Create run** — загрузка метаданных книги (`status = staged`).
2. **Persist sheets** — inventory листов с classification metadata.
3. **Persist rows/cells** — raw snapshot содержимого (будущий WP-CL-003+ pipeline).
4. **Downstream** — mapping → candidates → review → apply (не в WP-CL-002).
5. **Teardown** — удаление run каскадно удаляет sheets/rows/cells; canonical данные не затрагиваются.

## 6. Почему staging не является canonical SoT

| Принцип | Формулировка |
|---------|--------------|
| Не Source of Truth | Staging — **не** operational SoT; canonical данные — PPR / Employment после apply |
| Snapshot semantics | `semantic_hint` и sheet classification — рекомендации профилировщика на момент run, не финальный mapping |
| Re-import drift | Повторный import_run может изменить classification / semantic_hint без изменения исходного XLSX |
| Владелец данных | PPR и Employment BC владеют canonical кадровыми данными |
| Переходный слой | Staging — временный мост для миграции legacy Excel |
| Raw ≠ normalized | Ячейки хранят **исходный** текст; canonical значения создаются только после review/apply |
| Независимость | После apply canonical записи живут без staging |
| No direct write | ADR-057 запрещает прямую запись из Excel в canonical таблицы |
| Provenance only | Staging служит трассировке и откату, а не операционному чтению |

## 7. Артефакты

| Артефакт | Путь |
|----------|------|
| Migration | `alembic/versions/x3y4z5a6b7c8_wp_cl_002_staging_schema.py` |
| ORM | `app/db/models/control_list_import.py` |
| Repository | `app/control_list_import/infrastructure/repository.py` |
| Tests | `tests/test_wp_cl_002_staging_schema.py` |

## 8. Acceptance

- [x] Migration revision `x3y4z5a6b7c8` chained from `w2x3y4z5a6b7`
- [x] 4 staging tables with FK, indexes, CHECK constraints
- [x] SQLAlchemy ORM models
- [x] Minimal repository (`create_run/sheet/row/cell`)
- [x] Unit tests pass
- [x] Snapshot semantics documented (§3.5, ADR-057 §5.1)
- [ ] `git diff --check` clean

## 9. Следующий WP

WP-CL-003 — mapping profiles persistence.
