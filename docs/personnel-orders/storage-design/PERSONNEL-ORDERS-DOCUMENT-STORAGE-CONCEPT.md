# Personnel Orders — Document Storage Concept

Статус: concept (WP-PO-000)  
Дата: 2026-07-10

## 1. Цель

Разделить три контура хранения документов кадровых приказов:

1. **Git** — только безопасные технические материалы.
2. **Внешний legacy-источник** — локальные исторические файлы для инвентаризации и будущего импорта.
3. **Серверное файловое хранилище + БД** — production-контур бинарных документов и метаданных.

## 2. Локальный источник (legacy)

External import source:

```text
d:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\
```

Этот каталог:

- не находится в Git;
- используется как источник legacy-документов;
- не является постоянным production storage;
- не должен напрямую использоваться backend-приложением;
- может содержать персональные данные и сводные архивы приказов.

Backend не должен читать этот путь как runtime storage root.

## 3. Репозиторий проекта (Git)

Безопасные технические материалы:

```text
docs/personnel-orders/templates/
docs/personnel-orders/samples/anonymized/
docs/personnel-orders/architecture/
docs/personnel-orders/implementation/
docs/personnel-orders/storage-design/
docs/personnel-orders/inventories/
```

В Git допускается только:

- типовые формы без персональных данных;
- обезличенные примеры;
- документация и инвентаризационные отчёты.

## 4. Серверное файловое хранилище

Предлагаемая концепция layout:

```text
/opt/corpsite-storage/
└─ documents/
   └─ personnel-orders/
      ├─ personnel/
      ├─ leave/
      └─ production/
```

Либо абстрактный configurable root:

```text
CORPSITE_DOCUMENT_STORAGE_ROOT
```

Окончательный production-путь на этом этапе **не фиксируется** в коде.  
Конкретный root задаётся конфигурацией окружения.

Рекомендуемые свойства storage key:

- стабильный, не зависящий от исходного имени файла пользователя;
- включает логическую область (`personnel` / `leave` / `production`);
- поддерживает versioning документа;
- не содержит ФИО / ИИН в пути.

Пример логического ключа (не production-контракт):

```text
personnel-orders/{area}/{order_id}/{document_id}/v{version}/{safe_filename}
```

## 5. Что хранится в файловом storage

Бинарные документы:

- исходный DOC/DOCX;
- исходный PDF;
- подписанный PDF (если появится);
- скан;
- архивная версия.

Файловое хранилище **не** является источником истины для кадрового состояния сотрудника.  
Оно хранит вложения и документальные артефакты приказа.

## 6. Что хранится в БД

Метаданные и связи (концептуальный набор полей):

| Field | Purpose |
|---|---|
| `document_id` | Устойчивый идентификатор документа |
| `order_id` | Связь с кадровым приказом |
| `original_filename` | Исходное имя файла при загрузке |
| `storage_key` | Ключ/путь в файловом storage |
| `mime_type` | MIME-тип |
| `size_bytes` | Размер |
| `sha256` | Контрольная сумма содержимого |
| `source_type` | Источник: upload / import / generated / scan |
| `uploaded_at` | Время загрузки |
| `uploaded_by` | Кто загрузил |
| `document_role` | Роль: draft / original / signed / scan / archive |
| `version` | Версия документа |
| `status` | Статус жизненного цикла вложения |

БД также хранит связи приказа с сотрудниками, подразделениями, событиями и workflow — вне scope этого документа, см. architecture PO-003.

## 7. Ключевой принцип

```text
Database stores metadata and relations.
File storage stores binary documents.
Git stores only templates, anonymized examples, and documentation.
```

## 8. Потоки данных

### 8.1 Новый приказ (целевой)

1. Пользователь создаёт/утверждает приказ в системе.
2. Бинарный документ сохраняется в server file storage.
3. Метаданные и `storage_key` пишутся в БД.
4. Git не участвует.

### 8.2 Legacy import (будущий)

1. Read-only инвентаризация внешнего источника.
2. Ручная/полуавтоматическая классификация.
3. Импорт в server storage + создание metadata rows.
4. Операционные файлы **не** копируются в Git.

### 8.3 Подготовка шаблона для разработки

1. Кандидат помечается в инвентаре (`TEMPLATE_CANDIDATE`).
2. Ручной review на ПДн.
3. При необходимости — анонимизация.
4. Только безопасная копия помещается в `docs/personnel-orders/templates/...`.

## 9. Что не делается на WP-PO-000

- нет изменений backend/frontend;
- нет моделей и Alembic migration;
- нет реального импорта;
- нет копирования operational-документов в репозиторий;
- нет фиксации production path в коде.

## 10. Следующие шаги (вне scope WP-PO-000)

1. Ручной review кандидатов на шаблоны.
2. Решение по whitelist `docs/personnel-orders/` в `.gitignore`.
3. Проектирование таблицы document metadata (отдельный WP).
4. Configurable storage adapter (`CORPSITE_DOCUMENT_STORAGE_ROOT`).
5. Контролируемый import pipeline из legacy-источника.
