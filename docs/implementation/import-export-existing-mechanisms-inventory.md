# Инвентаризация существующих механизмов импорта, экспорта и синхронизации

Дата: 2026-09-13  
Статус: исследование перед общим каркасом; не является спецификацией нового API.

## Проверенные контуры

| Контур | Вход/выход | Повторно использовать | Нельзя использовать как общий контейнер |
|---|---|---|---|
| HR control-list import | `POST /directory/personnel/import/upload`; XLSX/XLSM → `hr_import_batches`, `hr_import_rows` | безопасное чтение workbook, staging, row-review, exact employee binding, provenance | модель и payload относятся к контрольному списку и import-profile; она не представляет приказы |
| HR sync | `/admin/sync`; Corpsite sync ZIP export/preview/apply | SHA-256/checksums, package validator, preview/apply gate, audit-log patterns | ZIP schema предназначена для репликации employees/import-profile overrides; upload временный, не общий файл-реестр |
| Control-list export | personnel control-list export endpoints/services | permission-gated server-side XLSX generation, export audit, formula-safe spreadsheet conventions | это конкретная проекция контрольного списка, не эталонный экспорт для order matching |
| Operational-order archive staging | manifest CLI → `operational_order_import_batches`/`operational_order_import_rows` | immutable manifest snapshot, SHA-256, path safety, review states | относится к архиву производственных приказов и `operational_order_documents`, не к кадровым/личным приказам |
| Personnel orders | `personnel_orders`, items, lifecycle and command/apply services | canonical order/items model, evidence-scope locks, lifecycle audit, transactional apply | нельзя писать исторические распознанные документы напрямую до отдельного review/import decision |

## Карта реализации

### UI и sync

- `corpsite-ui/app/admin/sync/` и `app/directory/hr_sync_routes.py` реализуют только проверяемые ZIP sync packages.
- `app/services/sync/{package_schema,package_validator,package_writer,preview_service,import_service,export_service,audit_service}.py` содержат полезные шаблоны checksum, dry-run и audit, но их предметная схема не расширяется для приказов.
- `app/directory/rbac.py::require_privileged_or_403` недостаточен для требуемого раздельного доступа к каждой стадии нового контура: новый контур должен опираться на явные permission grants, а не на неявный admin bypass.

### Контрольный список

- `app/directory/hr_import_routes.py` и `app/services/hr_import_service.py` создают `hr_import_batches`/`hr_import_rows`.
- `app/db/models/hr_import.py` хранит нормализованный профиль и review-состояния контрольного списка.
- Существующие `employee_import_profile_overrides`, normalized records и promotion относятся к личной карточке/ростеру, а не к историческим приказам.

### Приказы

- Канонические кадровые приказы: `app/db/models/personnel_orders.py`, `app/directory/personnel_orders_routes.py`, `app/services/personnel_orders_{command,apply,archive,query}_service.py`.
- У модели есть header, items, attachments, localized/editorial blocks, bases и append-only lifecycle audit. Уникальность заголовка сейчас задана только как `personnel_orders.order_number`; для исторического импортёра требуется отдельное решение о business key с датой/классом/источником, а не молчаливое переиспользование этого ограничения.
- `app/db/models/operational_order_archive_import.py` — отдельный immutable staging archive для производственных приказов. Его не смешивать с personnel orders.

### Экспорт

- `app/services/hr_canonical_snapshot_export_service.py` и `app/services/hr_change_events_export_service.py` экспортируют специализированные HR-проекции.
- `app/services/control_list_*`/`app/directory/*control*` содержат XLSX export и audit-паттерны. Для идентификации приказов нужен новый ограниченный эталонный export с `employee_id` и контрольным ФИО.

## Что должен предоставить общий каркас

1. Отдельный технический реестр пакетов и строк preview, не `hr_import_batches`.
2. Явная registry/specification сценариев: код, версия схемы, допустимый формат/размер, permissions, business key, row validator, preview/dry-run/apply/export handler.
3. Неизменяемый blob/временное контролируемое хранилище с SHA-256 и безопасным именем; результат preview и dry-run, связанный с hash, schema version и data-version fingerprint.
4. Состояния жизненного цикла и CAS/row locking для confirm/apply; один транзакционный apply по умолчанию.
5. Отдельные permissions `VIEW`, `UPLOAD_PREVIEW`, `DRY_RUN`, `CONFIRM_APPLY`, `EXPORT_REFERENCE`; backend проверяет каждую стадию.
6. Структурированный row-level preview/audit без значений, опасных для logs/Excel formulas.

## Обязательные границы данных

- Не смешивать control-list staging, HR import profiles, operational-order archive staging и кадровые приказы.
- Нельзя автоматически подтверждать employee link по ФИО; только `employee_id` в подготовленном workbook может пройти apply.
- OCR/PDF/DOCX extraction остаётся внешним CLI-процессом; сервер получает только версионированный подготовленный workbook.
- До отдельного review/import decision не создавать и не применять official employee events из исторических приказов.

## Подтверждённые пробелы

- Нет общего сценарного registry, общего package lifecycle или отдельного audit/preview model для разных импортеров.
- Нет текущего server-side order-import Excel schema/handler.
- Нет canonical reference XLSX export, предназначенного для external order-preparation matching.
- ADR-038-D.1 описывает ранний read-only sync UI; код уже содержит D.2 apply, поэтому его нельзя использовать как норматив для нового каркаса без уточнения.
