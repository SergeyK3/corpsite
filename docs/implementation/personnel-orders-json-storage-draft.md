# Минимальная JSON-структура кадрового приказа

Статус: аналитический черновик, не контракт реализации. Основание:
[`personnel-order-types-inventory.md`](personnel-order-types-inventory.md).

Документ описывает только JSON-представление одного кадрового приказа. Он не
проектирует БД, API, интерфейс, файловое хранилище или миграции.

## 1. Принципы

- Один объект — один приказ: общая шапка, независимые пункты `actions`,
  основания и файлы самого приказа.
- Один `action` относится к нулю или одному сотруднику. Сводный приказ
  содержит несколько `actions`; у каждого могут быть свои период, поля и
  основания. Например, `ORDER_VOID` может не иметь сотрудника, а
  подтверждённый текст `Ауыстыру туралы` содержит для одного сотрудника
  отдельные `TRANSFER` и `CONCURRENT_DUTY_START`.
- `action_type` — код действия из инвентаря, например `HIRE`, `TRANSFER`,
  `LEAVE_ANNUAL`, `LEAVE_UNPAID`.
- Номер и дата приказа могут быть `null`; их нельзя восстанавливать по имени
  файла, теме, сотруднику или соседним строкам журнала.
- `basis_documents` — документы/входящие записи, обосновывающие приказ или
  пункт. `source_files` — DOCX/PDF/сканы **самого приказа**. Это разные
  объекты.
- Один документ-основание может быть связан с несколькими пунктами; один пункт
  может иметь несколько оснований. Несколько оснований также могут вести к
  нескольким приказам — связь указывается явно в каждом JSON-представлении.

## 2. Общая шапка

```json
{
  "schema_version": "0.1",
  "order": {
    "order_id": "local:po-2026-000042",
    "order_number": null,
    "order_date": null,
    "requisites_status": "MISSING_NUMBER_AND_DATE",
    "title": {
      "kk": "Жұмысқа қабылдау туралы",
      "ru": null
    },
    "order_class": "PERSONNEL",
    "signatory": {
      "name": { "canonical": null, "forms": [] }
    }
  },
  "actions": [],
  "basis_documents": [],
  "source_files": []
}
```

`order_id` — технический идентификатор JSON-записи, а не номер приказа.
`order_number` и `order_date` допускают `null` независимо друг от друга:

| `requisites_status` | Номер | Дата |
|---|---|---|
| `COMPLETE` | строка | `YYYY-MM-DD` |
| `MISSING_NUMBER` | `null` | дата |
| `MISSING_DATE` | строка | `null` |
| `MISSING_NUMBER_AND_DATE` | `null` | `null` |
| `UNVERIFIED` / `CONFLICT` | значение или `null` | значение или `null` |

## 3. Пункты `actions` и ФИО

```json
{
  "action_id": "1",
  "action_type": "TRANSFER",
  "employee": {
    "employee_id": 16,
    "person_id": 105,
    "name": {
      "canonical": "Иванов Иван Иванович",
      "forms": [
        {
          "language": "ru",
          "case": "genitive",
          "text": "Иванова Ивана Ивановича"
        },
        {
          "language": "kk",
          "case": "dative",
          "text": "Иванов Иван Ивановичке"
        }
      ]
    }
  },
  "effective_period": {
    "date_from": "2026-10-01",
    "date_to": null
  },
  "data": {},
  "basis_ids": ["basis-1"]
}
```

`employee` может быть `null` только для действия без определённого
сотрудника, например `ORDER_VOID`. `employee_id` и `person_id`
заполняются только после надёжного сопоставления; иначе они могут быть
`null`. `canonical` — каноническое имя, а `forms` содержит только
фактически найденные формы. Если в источнике форма не встретилась, элемент
массива не создаётся; русские, казахские и все падежи не обязательны.

## 4. Типозависимые поля `data`

Общие поля пункта не дублируются в `data`. Поля ниже добавляются, только если
они действительно обнаружены в приказе.

| `action_type` | Минимальные типозависимые данные |
|---|---|
| `HIRE` | `assignment`: подразделение, должность, ставка; при наличии — образование, сертификат, стаж |
| `TRANSFER` | `from_assignment`, `to_assignment`; при наличии — ставка, временность, правовая ссылка |
| `PERSON_NAME_CHANGE` | `name_changes[]`: только изменённые компоненты имени с прежним и новым значением; дата действия — только в `effective_period` |
| `LEAVE_ANNUAL` | `assignment_snapshot`, `leave_days`, `work_periods[]`; даты отпуска только в `effective_period`; при наличии — `vacation_benefit` |
| `LEAVE_UNPAID` | `assignment_snapshot`, `leave_days`; даты отпуска только в `effective_period` |
| `TERMINATION` | `termination_reason`, `legal_basis`; при наличии — неиспользованный отпуск |
| `CONCURRENT_DUTY_START` | подразделение, должность и ставка по совмещению; итоговая ставка |
| `CONCURRENT_DUTY_END` | снимаемая и остающаяся ставка |
| `TEMPORARY_ASSIGNMENT` | должность, ставка, замещаемый сотрудник, дата окончания |
| `SUPPLEMENTARY_PAY` | период, процент/правило выплаты, причина; при наличии — замещаемый сотрудник |
| `QUALIFICATION_CATEGORY` | категория, срок действия, сертификат |

Снимок назначения имеет одну форму:

```json
{
  "unit": { "id": 73, "kk": "Кадрлар бөлімі", "ru": "Отдел кадров" },
  "position": { "id": 29, "kk": "Маман", "ru": "Специалист" },
  "rate": "1.00"
}
```

`id` может быть `null`, если текст не сопоставлен со справочником. Текстовый
снимок при этом сохраняется.

Для подтверждённого варианта смены фамилии, имени или отчества не создаются
пустые поля для остальных компонентов. Один реально встретившийся компонент
выглядит так:

```json
{
  "action_id": "1",
  "action_type": "PERSON_NAME_CHANGE",
  "employee": {
    "employee_id": null,
    "person_id": null,
    "name": { "canonical": "Прежнее ФИО", "forms": [] }
  },
  "effective_period": { "date_from": "2026-05-19", "date_to": null },
  "data": {
    "name_changes": [
      { "component": "surname", "before": "Прежняя фамилия", "after": "Новая фамилия" }
    ]
  },
  "basis_ids": ["basis:application:person-name-change", "basis:identity-document:person-name-change"]
}
```

Допустимые значения `component`: `surname`, `given_name`,
`patronymic`. В проверенном DOCX есть только `surname`; добавлять другие
компоненты без текста источника нельзя.

## 5. Основания и файлы приказа

### `basis_documents`

Основание описывается один раз со стабильным `basis_id`, уникальным в пределах
всего набора данных, а не одного приказа; пункт ссылается на него через
`basis_ids`. Это позволяет одному основанию явно связываться с несколькими
приказами. Допустимые `document_type`: `LETTER`, `SERVICE_MEMO`,
`REPORT_MEMO`, `EXPLANATORY_NOTE`, `RAPORT`, `EMPLOYEE_APPLICATION`,
`COMPLAINT_OR_APPEAL`, `SUBMISSION`, `ACT`, `PRESCRIPTION`,
`PROTOCOL`, `REQUEST_FORM`, `NOTICE`, `INQUIRY`,
`MANAGER_INSTRUCTION`, `SUPERVISORY_BODY_DOCUMENT`,
`COURT_OR_ENFORCEMENT_DOCUMENT`, `EMPLOYMENT_CONTRACT`,
`MEDICAL_CERTIFICATE`, `DONOR_CERTIFICATE`, `BIRTH_CERTIFICATE`,
`PREVIOUS_ORDER`, `COLLECTIVE_AGREEMENT`, `IDENTITY_DOCUMENT`,
`OTHER`.

```json
{
  "basis_id": "basis-1",
  "document_type": "EMPLOYEE_APPLICATION",
  "description": {
    "kk": "Қызметкердің жеке өтініші",
    "ru": "Личное заявление работника"
  },
  "document_number": null,
  "document_date": "2026-09-15",
  "incoming_record_ref": {
    "record_id": "ВХ-2026-0042",
    "status": "FUTURE_REGISTRY_REFERENCE"
  },
  "local_file_ref": {
    "path": "D:\\HR\\applications\\application-2026-09-15.pdf",
    "availability": "NOT_CHECKED"
  },
  "source_text": "Негіз: қызметкердің жеке өтініші."
}
```

Пока реестр входящей информации является будущим контуром, `local_file_ref.path`
на локальный файл или архивный путь допустим. В дальнейшем он может
сосуществовать с `incoming_record_ref` либо быть заменён этой ссылкой.
Отсутствующие номер, дата, запись реестра и путь разрешены как `null`.

### `source_files`

Здесь хранятся файлы **самого приказа**, а не заявления, справки или служебные
записки.

```json
{
  "source_file_id": "order-file-1",
  "file_role": "ORDER_ORIGINAL",
  "format": "DOCX",
  "local_file_ref": {
    "path": "D:\\HR\\2026-orders\\order-draft.docx",
    "availability": "NOT_CHECKED"
  },
  "page_or_block": null,
  "source_language": "kk"
}
```

Допустимы `ORDER_ORIGINAL`, `SIGNED_COPY`, `SCAN`,
`JOURNAL_REFERENCE`. Журнальная страница не становится текстом приказа только
из-за того, что содержит его регистрацию.

## 6. Короткие примеры

### Приём

```json
{
  "schema_version": "0.1",
  "order": { "order_id": "local:hire-1", "order_number": null, "order_date": null, "requisites_status": "MISSING_NUMBER_AND_DATE", "title": { "kk": "Жұмысқа қабылдау туралы", "ru": "О приёме на работу" }, "order_class": "PERSONNEL" },
  "actions": [{
    "action_id": "1", "action_type": "HIRE",
    "employee": { "employee_id": 16, "person_id": 105, "name": { "canonical": "Иванов Иван Иванович", "forms": [{ "language": "kk", "case": "accusative", "text": "Иванов Иван Ивановичті" }] } },
    "effective_period": { "date_from": "2026-10-01", "date_to": null },
    "data": { "assignment": { "unit": { "id": 73, "kk": "Кадрлар бөлімі", "ru": "Отдел кадров" }, "position": { "id": 29, "kk": "Маман", "ru": "Специалист" }, "rate": "1.00" } },
    "basis_ids": ["basis:application:2026-09-15:employee-16", "basis:employment-contract:employee-16"]
  }],
  "basis_documents": [{ "basis_id": "basis:application:2026-09-15:employee-16", "document_type": "EMPLOYEE_APPLICATION", "document_number": null, "document_date": "2026-09-15" }, { "basis_id": "basis:employment-contract:employee-16", "document_type": "EMPLOYMENT_CONTRACT", "description": { "kk": null, "ru": "Трудовой договор" }, "document_number": null, "document_date": null }],
  "source_files": []
}
```

### Перевод

```json
{
  "schema_version": "0.1",
  "order": { "order_id": "local:transfer-1", "order_number": "346-ж", "order_date": "2026-09-20", "requisites_status": "COMPLETE", "title": { "kk": "Ауыстыру туралы", "ru": "О переводе" }, "order_class": "PERSONNEL" },
  "actions": [{
    "action_id": "1", "action_type": "TRANSFER",
    "employee": { "employee_id": 16, "person_id": 105, "name": { "canonical": "Иванов Иван Иванович", "forms": [{ "language": "ru", "case": "dative", "text": "Иванову Ивану Ивановичу" }] } },
    "effective_period": { "date_from": "2026-10-01", "date_to": null },
    "data": { "from_assignment": { "unit": { "id": null, "kk": null, "ru": "Отдел кадров" }, "position": { "id": null, "kk": null, "ru": "Специалист" }, "rate": "1.00" }, "to_assignment": { "unit": { "id": null, "kk": null, "ru": "Отдел статистики" }, "position": { "id": null, "kk": null, "ru": "Ведущий специалист" }, "rate": "1.00" } },
    "basis_ids": ["basis:incoming:ВХ-2026-0042"]
  }],
  "basis_documents": [{ "basis_id": "basis:incoming:ВХ-2026-0042", "document_type": "SERVICE_MEMO", "document_number": null, "document_date": null, "incoming_record_ref": { "record_id": "ВХ-2026-0042", "status": "FUTURE_REGISTRY_REFERENCE" } }],
  "source_files": [{ "source_file_id": "order-file-1", "file_role": "ORDER_ORIGINAL", "format": "DOCX", "local_file_ref": { "path": "D:\\HR\\orders\\transfer.docx", "availability": "NOT_CHECKED" }, "page_or_block": null, "source_language": "kk" }]
}
```

### Ежегодный трудовой отпуск

```json
{
  "schema_version": "0.1",
  "order": { "order_id": "local:leave-1", "order_number": "321-д", "order_date": "2026-07-03", "requisites_status": "COMPLETE", "title": { "kk": "Еңбек демалысы туралы", "ru": null }, "order_class": "PERSONNEL" },
  "actions": [{
    "action_id": "1", "action_type": "LEAVE_ANNUAL",
    "employee": { "employee_id": 16, "person_id": 105, "name": { "canonical": "Иванов Иван Иванович", "forms": [{ "language": "kk", "case": "dative", "text": "Иванов Иван Ивановичке" }] } },
    "effective_period": { "date_from": "2026-08-03", "date_to": "2026-08-30" },
    "data": { "leave_days": 28, "work_periods": [{ "date_from": "2025-08-01", "date_to": "2026-07-31", "days": 28 }], "vacation_benefit": null },
    "basis_ids": ["basis:application:employee-16:leave-2026-08-03"]
  }],
  "basis_documents": [{ "basis_id": "basis:application:employee-16:leave-2026-08-03", "document_type": "EMPLOYEE_APPLICATION", "description": { "kk": "Қызметкердің жеке өтініші", "ru": "Личное заявление работника" }, "document_number": null, "document_date": null, "source_text": "Негіз: қызметкердің жеке өтініші." }],
  "source_files": []
}
```

Примеры иллюстративны: они не подтверждают существование указанных сотрудников,
номеров, путей или файлов. В сводном приказе следующий сотрудник добавляется
новым `action` со своими `data.work_periods` и `basis_ids`; его основания
не переносятся автоматически.

## 7. Границы черновика

JSON сохраняет исходные значения и их отсутствие; он не делает юридический
вывод, не генерирует текст приказа и не подтверждает связь с сотрудником или
основанием автоматически. Неизвестный вид остаётся явным `OTHER` с исходным
заголовком/текстом до ручной проверки.
