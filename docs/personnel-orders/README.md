# Personnel Orders — Document Module

Управляемый документный контур модуля кадровых приказов (Personnel Orders).

Этот каталог хранит **только** архитектурные материалы, планы реализации, безопасные шаблоны, обезличенные примеры, схемы хранения и инвентаризационные отчёты.

## Структура

```text
docs/personnel-orders/
├─ architecture/          # утверждённые архитектурные документы
├─ diagrams/              # существующие диаграммы (legacy layout)
├─ review/                # архитектурные review
├─ work-packages/         # существующие WP-отчёты (legacy layout)
├─ implementation/        # implementation plans, reconnaissance, work packages
├─ templates/
│  ├─ personnel/          # типовые кадровые формы без ПДн
│  ├─ leave/              # типовые формы отпусков / возврата из отпуска
│  ├─ production/         # типовые производственные формы
│  └─ shared/             # общие типовые формы / утверждение бланков
├─ samples/
│  └─ anonymized/         # обезличенные тестовые документы
├─ storage-design/        # локальное и серверное хранилище
├─ inventories/           # отчёты об инвентаризации внешних источников
└─ README.md
```

Каталоги `architecture/`, `diagrams/`, `review/`, `work-packages/`, `samples/` существовали до WP-PO-000 и сохранены без удаления.

## Что хранится в Git

- архитектурные документы;
- implementation-документы и work packages;
- типовые формы **без** персональных данных;
- обезличенные примеры;
- схемы хранения (`storage-design/`);
- инвентаризационные отчёты (`inventories/`).

## Что запрещено хранить в Git

- реальные кадровые приказы;
- документы с ФИО;
- документы с ИИН;
- документы с должностями и кадровыми решениями по конкретным сотрудникам;
- сканы подписанных приказов;
- архивы реальных приказов (ZIP / сводные DOC/DOCX);
- выгрузки бумажного журнала;
- любые operational-копии из внешнего источника без предварительной анонимизации и ручного review.

## Рабочий внешний источник (legacy, локальный)

```text
d:\ТОО\4 dept\4A soft\10A soft\27 Corpsite ММЦ\order_samples\
```

Этот путь:

- локальный для рабочей станции;
- **не** является production storage;
- **не** должен напрямую использоваться backend-приложением;
- содержит смесь шаблонов, образцов и реальных приказов с персональными данными;
- используется только как источник для read-only инвентаризации и последующего контролируемого импорта.

Инвентаризация: [`inventories/ORDER-SAMPLES-INVENTORY-REPORT.md`](inventories/ORDER-SAMPLES-INVENTORY-REPORT.md), [`inventories/order-samples-inventory-summary.csv`](inventories/order-samples-inventory-summary.csv).

Полный file-level CSV (`order-samples-inventory.csv`) хранится только локально и не предназначен для Git: в именах/путях встречаются персональные данные.

Концепция хранения: [`storage-design/PERSONNEL-ORDERS-DOCUMENT-STORAGE-CONCEPT.md`](storage-design/PERSONNEL-ORDERS-DOCUMENT-STORAGE-CONCEPT.md).

## Правила копирования в репозиторий

1. Автоматическое копирование из внешнего источника **запрещено**.
2. Кандидаты на шаблоны сначала помечаются в инвентаре (`TEMPLATE_CANDIDATE`).
3. Перед помещением в `templates/` обязателен ручной review на отсутствие ПДн.
4. Перед помещением в `samples/anonymized/` обязательна анонимизация.
5. Операционные документы остаются во внешнем хранилище / будущем серверном storage.

## Связанные артефакты

| Назначение | Путь |
|---|---|
| Архитектура модуля | `architecture/` |
| Печатная форма и статусы | `architecture/PO-PRINT-001-print-form.md` |
| Официальный PDF engine | `architecture/PO-PDF-001-official-pdf-engine.md` |
| Редакционная модель документа (**Approved**) | `architecture/PO-EDIT-001-editorial-document-model.md` |
| Концепция подписания (без реализации) | `PO-SIGN-001-signing-concept.md` |
| Политика удаления / void (без реализации) | `PO-LIFECYCLE-002-delete-and-void-policy.md` |
| Storage concept | `storage-design/PERSONNEL-ORDERS-DOCUMENT-STORAGE-CONCEPT.md` |
| Инвентарь CSV (summary) | `inventories/order-samples-inventory-summary.csv` |
| Инвентарь CSV (full, local only) | `inventories/order-samples-inventory.csv` |
| Инвентарь MD | `inventories/ORDER-SAMPLES-INVENTORY-REPORT.md` |

## Roadmap (editorial / leave)

| WP | Status | Scope |
|---|---|---|
| WP-PO-EDIT-001 | **Ratified** | Editorial architecture + spike (non-prod) |
| WP-PO-EDIT-002 | Next | Persistence; DRAFT-only structured+editorial writes; generate/READY gate |
| WP-PO-EDIT-003 | Planned | DRAFT-only block editor UI |
| WP-PO-EDIT-004 | Planned | Versioned DB clause/template library |
| WP-PO-EDIT-005 | Planned | return-to-DRAFT; audit polish; optional FIO forms |
| WP-PO-LEAVE-001 | Planned | Annual leave structured item model (periods/days/dates/allowance; no balance/payroll) |
| Later | Planned | localized_texts cleanup WP; immutable PDF snapshot |
