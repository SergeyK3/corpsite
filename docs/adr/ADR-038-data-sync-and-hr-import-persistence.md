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
- Phase A — Persistence Foundation
- Phase B — Sync Foundation
- Phase C — Preview & Conflict Engine

## Дополнительные этапы
- Phase D — Admin UI
- Phase E — Bidirectional Sync
