--------------------------------------------------

Document Status

Document:
WP-CL-003-mapping-profiles

Title:
Control List Mapping Profiles — Versioned Import Configuration

Type:
Implementation Work Package

Status:
Ready for Review

Date:
2026-07-17

Work Package:
WP-CL-003

Parent:
[ADR-057](../architecture/ADR-057-control-list-interchange-architecture.md)

Runtime effect:
**Schema + repository + vocabulary only** — no profile application, candidates, apply, or PPR mutations

--------------------------------------------------

# WP-CL-003 — Mapping Profiles

## 1. Цель

Реализовать **конфигурируемые mapping profiles** — versioned configuration между staging snapshot и будущей семантической моделью импорта.

Profile описывает, как интерпретировать листы и столбцы книги «Контрольный список», **не создавая** PPR / Employment записей.

## 2. Область

| In scope | Out of scope |
|----------|--------------|
| Alembic migration `y4z5a6b7c8d9e0` | Применение profile к staging run |
| SQLAlchemy ORM | Normalized candidates (WP-CL-004+) |
| Controlled vocabulary (`semantic_field`, `parser_code`) | Apply в canonical |
| Mapping profile repository | API / frontend |
| | Изменения PPR / Employment aggregates |

## 3. Архитектурные роли

| Слой | Роль | Source of Truth? |
|------|------|------------------|
| **Staging** (WP-CL-002) | Immutable snapshot профилировщика на `import_run` | **Нет** |
| **Mapping profile** (WP-CL-003) | Versioned configuration: sheet/column → semantic field + parser | **Нет** (конфигурация) |
| **Canonical PPR / Employment** | Операционные кадровые данные после controlled apply | **Да** |

**Инварианты:**

- Profile — это **конфигурация**, не snapshot и не canonical data.
- Staging `semantic_hint` — recommendation профилировщика; profile column mapping — operator-approved configuration.
- Canonical PPR **не изменяется** на этом этапе.
- **Versioning profile обязателен:** `(profile_code, profile_version)` unique; не более одного `active` на `profile_code`.

## 4. Таблицы

### 4.1. `control_list_mapping_profiles`

| Поле | Описание |
|------|----------|
| `profile_id` | PK |
| `profile_code` | Стабильный код семейства книг |
| `profile_version` | Версия профиля (>= 1) |
| `profile_name` | Человекочитаемое имя |
| `description` | Описание (nullable) |
| `status` | `draft` / `active` / `archived` |
| `created_at`, `created_by` | Audit |
| `updated_at` | Nullable |

**Unique:** `(profile_code, profile_version)`
**Partial unique:** один `active` на `profile_code`

### 4.2. `control_list_mapping_profile_sheets`

| Поле | Описание |
|------|----------|
| `profile_sheet_id` | PK |
| `profile_id` | FK → profile (CASCADE) |
| `sheet_name` | Имя листа Excel |
| `personnel_category` | Конфигурация листа |
| `employment_mode` | Конфигурация листа (не Person attribute) |
| `sheet_purpose` | Конфигурация листа |
| `header_row_override` | Override строки заголовка (nullable) |

**Unique:** `(profile_id, sheet_name)`

### 4.3. `control_list_mapping_profile_columns`

| Поле | Описание |
|------|----------|
| `profile_column_id` | PK |
| `profile_sheet_id` | FK → profile sheet (CASCADE) |
| `column_index` | 1-based Excel column |
| `column_letter`, `raw_header` | Metadata (nullable) |
| `semantic_field` | Controlled vocabulary — import-domain target |
| `parser_code` | Controlled vocabulary — parser selection |
| `is_required` | Required for candidate generation (future) |

**Unique:** `(profile_sheet_id, column_index)`

## 5. Controlled vocabulary

Module: `app/control_list_import/domain/vocabulary.py`

### 5.1. `semantic_field`

Dot-notation import interchange targets (aligned with WP-CL-001 header aliases):

- `person.full_name`, `person.birth_date`, `person.iin`, …
- `employment.department_name`, `employment.position_title`, …
- `education.records`, `training.records`, …

**Не привязаны** к именам колонок или таблиц PPR.

### 5.2. `parser_code`

Parser selection for future normalization pipeline:

- `identity.iin`, `identity.phone`, `date.excel_serial`, `date.text`
- `records.education`, `records.training`, …

**Не выполняют** parse/apply на этапе WP-CL-003.

## 6. Repository

`SqlAlchemyControlListMappingProfileRepository`:

| Method | Purpose |
|--------|---------|
| `create_profile()` | Create versioned profile row |
| `create_profile_sheet()` | Add sheet rule |
| `create_profile_column()` | Add column mapping |
| `get_profile()` | Load profile with nested sheets/columns |
| `list_active_profiles()` | List profiles with `status = active` |

Без бизнес-логики применения profile к staging.

## 7. Versioning lifecycle

### 7.1. Инварианты versioning

| Правило | Формулировка |
|---------|--------------|
| Immutability after publish | Profile version становится **immutable** после публикации (`status = active` или `archived`); sheet/column rules не редактируются in-place |
| Change via new version | Изменение active profile выполняется **только** созданием новой `(profile_code, profile_version)` |
| Archive previous active | При активации новой version предыдущая `active` для того же `profile_code` переводится в `archived` |
| Import run reference | Будущий `import_run` будет хранить ссылку на конкретную version: `profile_id` **или** `(profile_code, profile_version)` |
| Historical binding | Старые `import_run` **всегда** остаются привязаны к своей version profile; retroactive rebind запрещён |

> FK `import_run → profile` будет добавлен в последующем WP (normalization pipeline). WP-CL-003 создаёт только profile persistence.

### 7.2. Lifecycle steps

1. Create profile `draft` v1.
2. Add sheet/column rules (editable while `draft`).
3. Activate v1 (`status = active`) — предыдущий active для того же `profile_code` → `archived`; v1 становится immutable.
4. Create v2 as new row для изменений конфигурации.
5. Новые import runs используют явно выбранную version; старые runs сохраняют свою привязку.

## 8. Артефакты

| Артефакт | Путь |
|----------|------|
| Migration | `alembic/versions/y4z5a6b7c8d9e0_wp_cl_003_mapping_profiles.py` |
| Vocabulary | `app/control_list_import/domain/vocabulary.py` |
| ORM | `app/db/models/control_list_mapping.py` |
| Repository | `app/control_list_import/infrastructure/mapping_profile_repository.py` |
| Tests | `tests/test_wp_cl_003_mapping_profiles.py` |

## 9. Acceptance

- [x] Migration revision `y4z5a6b7c8d9e0` chained from `x3y4z5a6b7c8`
- [x] 3 mapping profile tables
- [x] Controlled vocabulary
- [x] ORM + repository
- [x] Unit tests pass
- [x] Versioning immutability documented (§7.1, ADR-057 §5.2)
- [ ] `git diff --check` clean

## 10. Следующий WP

WP-CL-004 — идентификационные поля Person (normalization pipeline).
