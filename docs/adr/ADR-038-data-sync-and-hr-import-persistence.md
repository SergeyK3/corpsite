# ADR-038. Data Sync Platform и сохранение HR Import данных

Статус: Approved
Дата: 2026-06-17

## Контекст
В Corpsite сформировался новый слой данных HR Import:
- контрольные кадровые выгрузки;
- staging-импорт сотрудников;
- карточки импорта сотрудников;
- ручные корректировки кадровиков;
- перекодировка отделений;
- кандидаты документов;
- AI-черновики извлечения данных.

## Решение
### Принцип 1. Импорт и ручные правки разделяются
Импортированные данные считаются источником информации.
Ручные изменения считаются пользовательскими данными.

### Принцип 2. Employee-level overrides
Создаётся таблица:
`employee_import_profile_overrides`

### Принцип 3. Карта сотрудника формируется через merge
Последний импорт + Ручные правки = Карта сотрудника.

### Принцип 4. Новый импорт не уничтожает ручные правки
Ручные изменения должны автоматически сохраняться между импортами.

### Принцип 5. Data Sync Package
Обмен данными между окружениями выполняется через пакет синхронизации.

## Формат обмена
corpsite_sync_YYYYMMDD_HHMMSS.zip

Содержимое:
- manifest.json
- checksums.json
- hr_import_batches.jsonl
- hr_import_rows.jsonl
- employee_import_profile_overrides.jsonl
- department_recoding.jsonl
- hr_import_document_candidates.jsonl
- hr_import_ai_extraction_drafts.jsonl

## Обязательные этапы
- Phase A — Persistence Foundation ✅
- Phase A.1 — Import Integrity Hardening ✅ ([ADR-038-A1](ADR-038-A1-import-integrity-hardening.md))
- Phase B — Sync Foundation ([ADR-038-B Stage 0](ADR-038-B-sync-foundation.md))
- Phase C — Preview & Conflict Engine

## Merge-модель (Phase A / A.1)

Карта формируется как **section-level replace**:

```
display_profile = apply_profile_override(import_base, employee_override)
```

Для каждой секции (`education`, `training`, `categories`, `certificates`, `degree`, `awards`, `notes`):
если ключ **присутствует** в override — секция **полностью заменяется**;
данные импорта для этой секции **не мержатся** по элементам.

**Known limitation (до Phase C):** новые данные импорта в overridden-секции не отображаются.
Пример: override certificates=[B] скрывает certificate C из нового импорта.

Тест: `test_certificate_override_hides_new_import_certificate`.

## Дополнительные этапы
- Phase D — Admin UI
- Phase E — Bidirectional Sync
