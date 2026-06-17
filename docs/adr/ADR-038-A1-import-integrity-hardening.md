# ADR-038-A1. Import Integrity Hardening (Phase A.1)

Статус: Approved  
Дата: 2026-06-17  
Родитель: [ADR-038](ADR-038-data-sync-and-hr-import-persistence.md)

## Контекст

Phase A (Persistence Foundation) обеспечила сохранение employee-level overrides между импортами.
Аудит выявил риски устаревших данных, отсутствия provenance и неоднозначного сопоставления сотрудников.

Phase A.1 устраняет эти риски **до** Phase B (Sync Foundation).

## Решения

### 1. Import provenance

Таблица `employee_import_profile_overrides` дополнена полями:

| Поле | Назначение |
|---|---|
| `base_batch_id` | Batch, на основании которого была сохранена правка |
| `base_row_id` | Строка импорта при save |
| `base_imported_at` | Дата импорта base на момент save |

При каждом save Карты2 provenance **обновляется** (отражает batch, открытый при сохранении).

API возвращает `base_batch_id`, `base_row_id`, `base_imported_at` из override-записи.

### 2. Missing from latest import

API Карты2 возвращает:

```json
{
  "card_batch_id": 123,
  "latest_batch_id": 456,
  "missing_from_latest_import": true
}
```

Логика:
- `latest_batch_id` — batch с максимальным `imported_at`
- `card_batch_id` — batch строки, использованной для base profile
- `missing_from_latest_import = true`, если сотрудник не найден в latest batch **или** `card_batch_id ≠ latest_batch_id`

UI показывает предупреждение при `missing_from_latest_import`.

### 3. Audit fields

Паттерн как в `employee_documents`: `created_by` при первом insert, `updated_by` при каждом update.

Заполняется из `user_id` текущего privileged-пользователя.

### 4. Ambiguous employee matching

`resolve_directory_employee_id()`:
- при >1 совпадении по ФИО или ИИН → `None`, `logger.warning`
- employee override **не создаётся**
- override остаётся только на `hr_import_rows` (batch row)

### 5. Merge model (known limitation)

**Section-level replace** — без изменений в Phase A.1.

Если ключ секции присутствует в `profile_override`, секция **полностью заменяется** override;
новые данные импорта для этой секции **не видны** до снятия/обновления override.

Пример (certificates): июнь A → правка B → июль C → display **B only**.

Разрешение — Phase C (Conflict Engine), не Phase A.1.

### 6. Orphan override (исследование, код не менялся)

**Проблема:** override в `employee_import_profile_overrides` сохраняется, но GET Карты2 → 404, если нет import row.

#### Вариант A — override-only режим

GET возвращает:
- `profile` из override (+ пустой/minimal base)
- `missing_import_row: true`
- `orphan_override: true`

PATCH/DELETE работают без import row.

**Плюсы:** данные HR не теряются; можно редактировать осиротевшие правки.  
**Минусы:** нет base для merge; UI сложнее; sync-конфликты при восстановлении import.

#### Вариант B — текущее поведение (404)

**Плюсы:** простота; нет «карты без импорта».  
**Минусы:** silent data orphan; override недоступен через API.

#### Рекомендация

**Phase B:** оставить Вариант B, но sync-пакет **обязан** включать overrides.  
**Phase C:** реализовать Вариант A как fallback + admin UI «осиротевшие overrides».

## Миграция

`l5e6f7a8b9c0` — добавляет provenance + `created_by`, backfill provenance из latest row.

## API Карты2 (дополнительные поля)

```json
{
  "batch_id": 456,
  "card_batch_id": 456,
  "latest_batch_id": 456,
  "missing_from_latest_import": false,
  "base_batch_id": 123,
  "base_row_id": 789,
  "base_imported_at": "2026-06-01T10:00:00+00:00",
  "created_by": 1,
  "updated_by": 1,
  "has_override": true
}
```

`batch_id` сохранён для обратной совместимости (= `card_batch_id`).

## Готовность к Phase B

Phase A.1 **не блокирует** Sync Foundation:
- provenance и audit поля включаются в `employee_import_profile_overrides.jsonl`
- integrity flags — read-time, не влияют на sync format
- merge limitation документирована для Phase C

## Этапы ADR-038 (актуализировано)

| Phase | Статус |
|---|---|
| A — Persistence Foundation | Done |
| A.1 — Import Integrity Hardening | Done |
| B — Sync Foundation | Next |
| C — Preview & Conflict Engine | Planned |
| D — Admin UI | Planned |
| E — Bidirectional Sync | Planned |
