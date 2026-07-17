# Control List Import — Read-Only Workbook Profiler (WP-CL-001)

## Назначение

Пакет `scripts/ops/control_list_import` выполняет **read-only** технический аудит исторических Excel-файлов «Контрольный список»:

- инвентаризация листов и фактических диапазонов;
- эвристический поиск строки заголовков;
- рекомендации semantic mapping по aliases;
- классификация типов значений и issue codes;
- обнаружение составных ячеек и наследуемых подразделений;
- **рекомендательная классификация листов** (personnel category, employment mode, sheet purpose);
- формирование JSON и Markdown отчётов.

**Инструмент не импортирует данные в PPR, не подключается к PostgreSQL и не изменяет исходный XLSX.**

## Ограничения

- Только локальный read-only анализ файла.
- Без staging-таблиц, API, frontend и canonical apply.
- Без ML и внешних API.
- Excluded-листы (по умолчанию — имя содержит «декларация») инвентаризируются, но не анализируются содержательно.

## Read-only гарантии

1. Workbook открывается с `data_only=True`; **`workbook.save()` не вызывается**.
2. SHA-256 исходного файла вычисляется **до** и **после** анализа.
3. При несовпадении хешей команда завершается с кодом **2**.
4. Оба значения SHA-256 фиксируются в JSON/Markdown отчёте.

## Запуск (Windows PowerShell)

Из корня репозитория:

```powershell
python -m scripts.ops.control_list_import.inspect_workbook `
  --input "C:\Temp\контрольный июнь.xlsx" `
  --output-json "C:\Temp\control-list-profile.json" `
  --output-md "C:\Temp\control-list-profile.md" `
  --exclude-sheet-name-contains "декларация"
```

## Параметры CLI

| Параметр | Описание |
|----------|----------|
| `--input` | **Обязательный.** Путь к исходному XLSX. |
| `--output-json` | Путь JSON-отчёта (по умолчанию: `<input-stem>-profile.json`). |
| `--output-md` | Путь Markdown-отчёта (по умолчанию: `<input-stem>-profile.md`). |
| `--exclude-sheet-name-contains` | Повторяемый. Подстрока имени листа для exclusion (default: `декларация`). |
| `--max-samples-per-column` | Макс. маскированных примеров на столбец (default: 5). |
| `--header-scan-limit` | Сколько верхних строк сканировать для заголовка (default: 30). |
| `--verbose` | Прогресс в stderr. |

## JSON-отчёт

Минимальная структура:

- `schema_version`
- `source` — filename, size, sha256_before/after, unchanged
- `configuration` — exclusion terms
- `workbook.sheets[]` — analyzed или excluded листы
- `summary` — агрегаты **только** по analyzed-листам

Excluded-лист содержит как минимум:

```json
{
  "sheet_name": "...",
  "sheet_index": 0,
  "status": "excluded",
  "exclusion_reason": "sheet_name_declaration",
  "matched_exclusion_term": "декларация"
}
```

## Markdown-отчёт

Содержит резюме, SHA-256, таблицу листов, excluded-список, детали analyzed-листов, общую статистику и рекомендации для будущего mapping profile.

## Маскирование персональных данных

| Тип | Формат |
|-----|--------|
| ИИН | `******1234` (последние 4 цифры) |
| Телефон | `+7*******609` |
| ФИО | `М******** А****** С********` |

Полные ИИН, телефоны и ФИО **не попадают** в JSON/Markdown.

## Excluded-листы

Правило — **явная конфигурация**, не скрытая эвристика:

- сравнение регистронезависимо;
- после trim;
- после нормализации повторяющихся пробелов;
- по вхождению подстроки в имя листа.

Для excluded-листов **не выполняются**: поиск заголовков, анализ столбцов, samples, row classification, агрегированная статистика.

## Структура пакета

| Модуль | Ответственность |
|--------|-----------------|
| `inspect_workbook.py` | CLI, SHA-256 guard, orchestration |
| `workbook_profile.py` | Чтение Excel, диапазоны, headers, columns, rows |
| `value_types.py` | Типизация, issues, masking, composite detection |
| `header_aliases.py` | Semantic aliases |
| `sheet_classification.py` | Sheet category / employment mode (recommendation) |
| `report_writer.py` | JSON / Markdown writers |

Excluded-листы **не выполняют** содержательный анализ и **не входят** в `rows_by_employment_mode`.

## Классификация листов

- Классификация листа — **рекомендация** для будущего mapping profile (WP-CL-003).
- **`employment_mode` не является атрибутом Person** — это контекст исходного листа и будущего candidate назначения.
- Один Person может иметь **primary** и **concurrent** назначения одновременно в canonical контуре.
- Будущий export Контрольного списка должен поддерживать фильтр: **primary / concurrent / all**.
- Правила классификации вынесены в `sheet_classification.py` и будут перенесены в configurable mapping profiles.

## Связанные документы

- [ADR-057](../../docs/architecture/ADR-057-control-list-interchange-architecture.md)
- [WP-CL-001](../../docs/implementation/WP-CL-001-source-workbook-audit.md)
