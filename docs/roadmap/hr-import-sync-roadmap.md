# HR Import Sync Roadmap

Статус: Active

## Vision
Создать безопасную систему хранения и переноса HR Import данных между локальной средой и сервером.

## Phase A. Persistence Foundation
- создать employee_import_profile_overrides
- миграция существующих profile_override
- перевести карту сотрудника на employee-level override
- тесты

Результат:
Новые импорты не уничтожают ручные правки.

## Phase B. Sync Foundation
- data_sync_service.py
- export_sync_package.py
- import_sync_package.py
- manifest.json
- checksums.json

## Phase C. Preview & Conflict Engine
- dry-run
- preview
- conflict detection
- conflict report

## Phase D. Admin UI
Раздел:
Администрирование → Обмен данными

Функции:
- Создать пакет
- Загрузить пакет
- Проверить различия
- Применить изменения
- История обменов

## Phase E. Bidirectional Sync
- Server → Local Sync
- Local → Server Sync
- выборочный merge
- разрешение конфликтов
