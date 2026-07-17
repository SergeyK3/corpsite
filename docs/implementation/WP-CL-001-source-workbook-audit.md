--------------------------------------------------

Document Status

Document:
WP-CL-001-source-workbook-audit

Title:
Control List Source Workbook Audit — Read-Only Profiler

Type:
Implementation Work Package

Status:
Ready for Review

Date:
2026-07-17

Work Package:
WP-CL-001

Parent:
[ADR-057](../architecture/ADR-057-control-list-interchange-architecture.md)

Runtime effect:
**Read-only CLI only** — no DB, no PPR mutations, no API/UI

--------------------------------------------------

# WP-CL-001 — Source Workbook Audit (Read-Only Profiler)

## 1. Цель

Получить **воспроизводимый технический отчёт** о структуре и качестве исходной книги «Контрольный список» без:

- изменения XLSX;
- подключения к БД;
- импорта в PPR;
- попытки исправления данных.

## 2. Область

| In scope | Out of scope |
|----------|--------------|
| Read-only профилировщик CLI | Staging schema (WP-CL-002) |
| JSON + Markdown отчёты | Mapping profile persistence (WP-CL-003) |
| Header alias recommendations | Person matching (WP-CL-005) |
| Value typing & issue codes | Apply / rollback (WP-CL-011…012) |
| Excluded sheet policy (`декларация`) | Export (WP-CL-013) |
| Sheet classification (category / employment mode) | Employment BC mutations |
| SHA-256 integrity guard | Frontend |

## 3. Пакет

```text
scripts/ops/control_list_import/
    __init__.py
    inspect_workbook.py      # CLI
    workbook_profile.py        # Excel read & analysis
    value_types.py             # Typing, masking, composite detection
    header_aliases.py          # Semantic header aliases
    sheet_classification.py    # Sheet category / employment mode recommendations
    report_writer.py           # JSON / Markdown output
    README.md
```

Разделение ответственности: CLI, чтение Excel, типизация, классификация строк и построение отчёта — **в разных модулях**.

## 4. CLI

```powershell
python -m scripts.ops.control_list_import.inspect_workbook `
  --input "C:\Temp\контрольный июнь.xlsx" `
  --output-json "C:\Temp\control-list-profile.json" `
  --output-md "C:\Temp\control-list-profile.md" `
  --exclude-sheet-name-contains "декларация"
```

### Параметры

- `--input` — обязательный путь к XLSX
- `--output-json`, `--output-md` — обязательны или берут safe default рядом с input
- `--exclude-sheet-name-contains` — повторяемый; default: `декларация`
- `--max-samples-per-column`, `--header-scan-limit`, `--verbose` — опционально

## 5. Read-only гарантии

1. SHA-256 до и после анализа; exit code **2** при изменении файла.
2. `workbook.save()` **не вызывается**.
3. Исходный файл не копируется в репозиторий и не коммитится.

## 6. Excluded-листы

Листы с подстрокой «декларация» в имени (явная конфигурация):

- `status = excluded`
- `exclusion_reason = sheet_name_declaration`
- без header/column/row analysis
- без вклада в `summary` и `rows_by_employment_mode`

## 7. Классификация листов (рекомендация)

Для каждого листа (analyzed и excluded) профилировщик формирует блок `classification`:

- `proposed_personnel_category` — doctor / nursing_staff / junior_medical_staff / other_staff / unknown
- `proposed_employment_mode` — primary / concurrent / unknown
- `proposed_sheet_purpose` — personnel_control_list / declaration / unknown
- `classification_confidence`
- `matched_classification_rules`

Правила — `sheet_classification.py` (profile-driven; в WP-CL-003 переносятся в mapping profile).

**Границы:**

- это **только recommendation**;
- профилировщик **не создаёт** Employment, **не изменяет** Person;
- `employment_mode` **не является** атрибутом Person;
- один Person может иметь primary и concurrent назначения в canonical контуре.

Summary (только analyzed-листы):

- `rows_by_employment_mode` — primary / concurrent / unknown
- `rows_by_personnel_category` — по категориям персонала

Инвариант: сумма значений каждого агрегата = `summary.probable_person_rows`.

## 8. Профилировщик — ключевые выходы

### 8.1. Source

filename, size, sha256_before/after, analyzed_at, schema_version

### 8.2. Sheet inventory

sheet_name, index, hidden, excel max range, **actual** last row/column, merged ranges, status

### 8.3. Header detection

probable_header_row, header_confidence, matched_header_aliases, probable_first_data_row

### 8.4. Column map

raw/normalized header, proposed semantic field, type distribution, issue counts, masked samples (≤5)

### 8.5. Row statistics

probable_person_rows, IIN/phone/composite/inherited section counts

### 8.6. Issue codes

Минимальный набор из ADR-057 / WP-CL-001 spec (iin_*, phone_*, composite_*, inflated_excel_used_range, …)

## 9. Semantic fields (aliases)

Рекомендательный mapping через `header_aliases.py`:

- `person.full_name`, `person.birth_date`, `person.iin`, `person.sex`, …
- `employment.department_name`, `employment.position_title`, …
- `education.records`, `training.records`, `qualification.category`, …

## 10. Маскирование

ИИН, телефоны и ФИО маскируются в отчётах; unit tests используют только синтетические данные.

## 11. Тесты

`tests/ops/test_control_list_workbook_profiler.py` — синтетические временные XLSX, 26+ сценариев из acceptance criteria.

## 12. Acceptance (WP-CL-001)

- [x] ADR-057 создан
- [x] WP-CL-001 создан
- [x] Read-only профилировщик реализован
- [ ] Unit tests pass
- [ ] Запуск на локальном исходном XLSX
- [ ] SHA-256 unchanged подтверждён
- [ ] git diff --check clean

## 13. Следующие WP

WP-CL-002 (staging schema) → WP-CL-003 (mapping profiles) → … → WP-CL-013 (export).
