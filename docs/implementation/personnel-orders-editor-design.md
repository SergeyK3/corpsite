# Проект: полноценный редактор кадровых приказов

## 1. Цель и границы

Цель — штатный редактор в разделе **Кадровые процессы → Приказы → Кадровые приказы**. Он должен позволять кадровику создавать отсутствующие и нигде не зарегистрированные приказы, исправлять восстановленные приказы, а также выполнять документную коррекцию зарегистрированного приказа.

Редактор позволяет:

- менять номер, дату, исходное название и тип действия;
- добавлять, исправлять, void-восстанавливать пункты;
- связывать пункт с сотрудником либо оставлять исходного `UNRESOLVED`-фигуранта;
- просматривать RU/KK документ до сохранения;
- подтверждать документ кадровой службой или возвращать его на проверку;
- видеть понятную историю изменений.

Принятое правило: документная коррекция зарегистрированного приказа меняет только документные данные. Она **никогда автоматически не меняет** `employee_events` и `person_assignments`. Любое отдельное кадровое применение или компенсация должно быть самостоятельным явно подтверждённым процессом.

Не входит в этот проект: электронная подпись директора, массовая регенерация документов, self-service редактирование работником и физическое удаление зарегистрированных документов.

## 2. Исследование существующей системы

| Механизм | Что уже можно использовать | Чего не хватает для редактора | Схема / риск зарегистрированного приказа |
|---|---|---|---|
| `personnel_orders` | Header: номер, дата, тип, lifecycle, источник `source_mode` (сейчас только `PAPER`/`DIGITAL`), подписант, basis summary, `storage_json`, комментарий, timestamps | Нет `MANUAL` source, отдельных полей для исходного названия, языка, причины ручного создания/документной коррекции и версии коррекции | Нужны нормализованные поля, расширение source validation до `MANUAL` либо отдельная source classification; нельзя разрешить обычный draft PATCH для REGISTERED |
| `personnel_order_items` | Номер пункта, тип, `employee_id`, даты, период, JSON context, `ACTIVE`/`VOIDED`, причина и автор void | Нет first-class исходного ФИО, match status, версии строки и редакторских RU/KK полей вне payload | Для зарегистрированного приказа физическое удаление недопустимо; нужен void/restore и audit |
| `personnel_order_localized_texts` | Legacy RU/KK title, preamble, body, authoritative flag | Не хранит историю и не разделяет структурное исправление от ручного editorial override | Можно оставить для обратной совместимости; не делать его единственным audit-источником |
| Editorial blocks / revisions | `personnel_order_editorial_blocks` и revision-цепочка; order blocks `title`, `preamble`, `closing`, item blocks `body`, `basis`; generation, stale/review statuses и optimistic conflict для block patch | Работают как редактура текста и сейчас ориентированы на DRAFT; не покрывают header/item before/after | Повторно использовать для текста и статусов review, расширять документную коррекцию отдельно от кадрового применения |
| Evidence scopes | Transactional lock/create/advance scope при изменениях командного слоя | Нет пользовательского экрана объяснения изменённого evidence scope | Использовать в каждой транзакции изменения документа; не смешивать со сканом/основанием без явной связи |
| Lifecycle audit | Есть `personnel_order_lifecycle_audit` и API чтения; фиксирует cancel/annul/archive/restore/void applied и связанные действия | Не содержит событий документного редактирования header/item/confirmation | Базу lifecycle не подменять; расширение существующего append-only audit предпочтительнее дублирующей истории |
| Acknowledgement events | Append-only `personnel_order_acknowledgement_events`: `RECORDED`, `CORRECTED`, `CLEARED`, конкретная пара приказ+работник, текущим является последнее событие | Не является audit изменений текста и не заменяет document confirmation | Повторно использовать без копирования в item; при document correction не перезаписывать acknowledgement |
| Command service | Создание DRAFT, добавление/update/delete draft item, register, ready-for-signature, stale editorial; пересчёт header type при registration | Draft-only edit guard, browser передаёт payload, delete доступен для DRAFT; нет duplicate preview и document-correction transaction | Создать отдельный command path для correction, не ослаблять текущие draft guards |
| Generation service | Классификация, bilingual titles/preamble/body/basis, presentation context, review statuses | Нет preview от несохранённого typed command и нет запрета на произвольную browser metadata | Вызывать серверный генератор с allowlisted command DTO, не принимать raw JSON |
| Existing API | Read list/detail; create/update/header; create/update/delete item; editorial; acknowledgement; lifecycle audit; print/PDF route | Нет confirmation/reopen, duplicate preview, correction API, history API и protected registered-edit contract | Существующие draft endpoints сохранить; новые endpoints отделить по назначению |
| `PersonnelOrderDetailDrawer` | Загружает detail/editorial, вкладки Document/Data, lifecycle actions, acknowledgement HR UI, language switch, print entrypoint | Нет вкладок «Реквизиты», «Пункты», «История» как единого редактора; Document tab не должен становиться raw editor | Расширить drawer поэтапно, сохранив read-only document projection и HR-only элементы |
| `PersonnelOrderItemEditor` | Селекторы сотрудника, подразделения/должности, типовые поля, basis UI, draft item create/update | Сейчас ориентирован на DRAFT, умеет delete, не моделирует unresolved subject и document-correction reason | Переиспользовать field components/валидацию, заменить delete на void/restore в новом режиме |
| Document preview / print | `PersonnelOrderDocumentView`, approved template registry и HTML/PDF print view model; общий footer для HR print | Preview не принимает transient typed draft; обычный просмотр и print имеют разные разрешённые блоки | Оставить единый renderer; HR print включает footer, обычный просмотр — нет |
| RBAC | Все текущие HR order routes требуют `require_personnel_admin_or_403`; есть granular admin permissions, включая archive/restore/audit read | Нет отдельного разрешения на document correction/confirmation | На первом этапе использовать существующее HR edit permission для privileged personnel admin; отдельный narrow permission рассмотреть после matrix-аудита |

### Риски изменения зарегистрированного приказа

1. Документ может расходиться с уже созданным кадровым событием. Это допустимо только при явном маркированном предупреждении и аудите, но не должно скрыто изменять событие.
2. Изменение номера может нарушить уникальность `personnel_orders.order_number` и ссылки на бумажный журнал. Нужны duplicate preview и server-side unique check.
3. Обновление `payload` целиком из браузера может затереть evidence/presentation context. Новый API принимает только типизированные allowlisted поля.
4. Изменение одного item должно пометить связанную редактуру stale, но не выполнять массовую регенерацию остальных приказов.

## 3. Предлагаемый интерфейс

### Таблица приказов

Над журналом: кнопка **Создать приказ**. В каждой строке: **Открыть**, **Редактировать** (если разрешено), статус lifecycle и отдельный статус документной проверки: «не подтверждён», «на проверке», «подтверждён кадровой службой».

Фильтры и поиск остаются journal-level. Technical type codes не показываются; выводятся локализованные названия.

### Drawer приказа

Drawer содержит четыре вкладки:

1. **Документ** — RU/KK preview, review warning, basis, без raw payload.
2. **Реквизиты** — typed form header и документная причина.
3. **Пункты** — список, typed form пункта, void/restore.
4. **История** — lifecycle, editorial и document-correction события в хронологическом порядке.

Print открывается из HR drawer и использует тот же approved renderer; acknowledgement/executor/footer отображаются только в официальном HR print, не в self-service `/profile/orders`.

### Реквизиты

Поля: номер, дата, исходное название, язык исходного названия, источник, причина создания/исправления и примечание кадровика. Lifecycle status не редактируется dropdown-ом: его меняют только отдельные lifecycle actions.

### Пункты

Для каждого пункта: номер, сотрудник либо исходное ФИО, match status, тип действия, effective date, period start/end, должность RU/KK, подразделение RU/KK, ставка при применимости, основание и review state.

Операции: добавить, изменить, пометить недействующим, восстановить. Физическое удаление из пользовательского UI запрещено. `UNRESOLVED` означает сохранение исходного ФИО и отсутствие `employee_id`; система не должна угадывать совпадение.

## 4. Правила типа приказа

Header type рассчитывается сервером из активных items:

- один item — его `item_type_code`;
- несколько items одного типа — этот общий type;
- разные типы — `COMPOSITE`.

Пользователь меняет тип пункта, а не вручную header type. Система пересчитывает header type в той же транзакции.

Текущий допустимый набор: `HIRE`, `TRANSFER`, `TERMINATION`, `CONCURRENT_DUTY_START`, `CONCURRENT_DUTY_END`, `SUPPLEMENTARY_PAY`, `RETURN_FROM_CHILDCARE_LEAVE`, `LEAVE.ANNUAL.GRANT`, `LEAVE.UNPAID.GRANT`, `LEAVE.CHILDCARE.GRANT`, `COMPOSITE` (только header при разнородных items).

## 5. Создание отсутствующего приказа

Новый приказ создаётся как `DRAFT`, с `source=MANUAL`, обязательной причиной ручного создания и минимум одним item до перехода к регистрации. Он не создаёт `employee_events` и `person_assignments`. Допускается `UNRESOLVED` subject с исходным ФИО и match status `UNRESOLVED`.

Текущая модель знает только `PAPER`/`DIGITAL`, поэтому `MANUAL` требует явного schema/command-service решения в будущем этапе; нельзя подменять его значением `PAPER` или неявным JSON-флагом.

Перед созданием сервер возвращает duplicate preview:

| Проверка | Результат |
|---|---|
| Совпадает нормализованный номер | blocking duplicate, если нет документно подтверждённой причины различия |
| Совпадают номер и дата | blocking duplicate по умолчанию |
| Совпадает source identifier | blocking, если идентификатор надёжен |
| Совпадают сотрудник, действие и effective date | warning: возможны разные пункты/приказы, кадровик обязан подтвердить |

Блокировка не должна заменять unique constraint: она только заранее объясняет конфликт.

## 6. Исправление зарегистрированного приказа

Для `SIGNED`/`REGISTERED` доступен отдельный режим **Исправление документа**. Он требует reason, показывает before/after и явное предупреждение: «Документная коррекция не меняет ранее созданные кадровые события и назначения».

Требования transaction:

- actor user ID, server timestamp, reason code/text;
- optimistic concurrency (`updated_at` или отдельная document revision);
- lock evidence scope и запись before/after;
- пересчёт type, точечная stale/regenerate обработка только этого приказа;
- no-op при семантически идентичном command;
- предупреждение о linked `employee_events` и запрет на скрытый apply/compensate.

## 7. Подтверждение кадровой службой

Действия: **Подтвердить кадровой службой** и **Вернуть на проверку**.

Подтверждение означает, что кадровик проверил документные данные. Оно не является ЭЦП директора, не применяет кадровое событие и не меняет assignment. После подтверждения большие жёлтые document-review warnings скрываются в обычной проекции, но детальная история и причина остаются доступны HR.

При reopening состояние возвращается на проверку с обязательной причиной; прежнее подтверждение сохраняется в append-only истории.

## 8. Аудит

| Вариант | Оценка |
|---|---|
| Расширить lifecycle/editorial audit | Предпочтительно: уже append-only по назначению, actor/time и lifecycle read API существуют; нужен новый document-audit event contract и JSON before/after с allowlisted полями |
| Новая отдельная history table | Резервный вариант, если существующая lifecycle schema намеренно ограничена lifecycle-only и её нельзя расширять без смешения семантик |

Минимальный рекомендуемый вариант: расширить существующий personnel-order lifecycle audit документными событиями и typed `metadata`/before-after snapshot, без второй конкурирующей history table. Если DB constraint не допускает новые action values, потребуется линейная миграция именно для enum/check и индексов, а не новая сущность.

События: `CREATE`, `HEADER_UPDATED`, `ITEM_ADDED`, `ITEM_UPDATED`, `ITEM_VOIDED`, `ITEM_RESTORED`, `DOCUMENT_CONFIRMED`, `DOCUMENT_REOPENED`. У каждого: `order_id`, optional `item_id`, actor, timestamp, reason code/text, bounded structured before/after, command id/idempotency key и correlation with evidence scope.

## 9. Предлагаемый API-контракт

Все команды принимают typed DTO. Browser не передаёт raw `payload`, `storage_json`, evidence metadata или server-owned lifecycle fields.

| API | Назначение |
|---|---|
| `POST /directory/personnel-orders/editor` | Создать manual DRAFT с причиной; items создаются отдельными typed commands или в атомарном typed create request |
| `POST /directory/personnel-orders/duplicate-preview` | Возвращает blocking/warning candidates до записи |
| `PATCH /directory/personnel-orders/{id}/document-header` | Header correction с expected revision и reason |
| `POST /directory/personnel-orders/{id}/document-items` | Добавить typed item |
| `PATCH /directory/personnel-orders/{id}/document-items/{itemId}` | Изменить typed item |
| `POST /directory/personnel-orders/{id}/document-items/{itemId}/void` | Void с причиной |
| `POST /directory/personnel-orders/{id}/document-items/{itemId}/restore` | Restore с причиной |
| `POST /directory/personnel-orders/{id}/document-preview` | Server-built RU/KK preview из сохранённого или transient typed command, без записи |
| `POST /directory/personnel-orders/{id}/document-confirmation` | Confirm/reopen с reason и optimistic revision |
| `GET /directory/personnel-orders/{id}/document-history` | Объединённая HR history projection |

Текущие draft endpoints сохраняются для обратной совместимости; новый namespace не должен расширять их на registered orders неявно.

## 10. Общий footer

Footer не копируется в каждую DB запись. Его выводит общий официальный HR print template из signatory/acknowledgement/executor projection.

KK:

```text
Директор ____________________ М. Тулеутаев

Бұйрықпен таныстым: ____________________
Аты-жөні: ______________________________
«___» ______________ {год} ж.

Орындаушы: М. Умерзакова
```

RU:

```text
Директор ____________________ М. Тулеутаев

С приказом ознакомлен(а): ____________________
Фамилия И.: _________________________________
«___» ______________ {год} г.

Исполнитель: М. Умерзакова
```

Написание ФИО директора должно быть подтверждено по кадровым DOC/DOCX-шаблонам до реализации. До подтверждения нельзя превращать эту строку в неизменяемую каноническую DB-ценность.

## 11. Первый сценарий приёмки (будущий)

Этот сценарий описывает будущую коррекцию через редактор и **не разрешает выполнять её сейчас**:

- `order_id=128`;
- номер `125-к` → `125-ж`;
- исходное название: `Бала күтіміне байланысты демалыстан жұмысқа шығу туралы`;
- item type остаётся `RETURN_FROM_CHILDCARE_LEAVE`;
- effective date остаётся `05.08.2026`;
- сотрудник и presentation context сохраняются;
- совмещение не добавляется;
- `employee_events` и `person_assignments` не меняются;
- reason: `USER_CONFIRMED_ORDER_NUMBER_AND_SOURCE_TITLE`;
- повторное сохранение того же typed command — no-op.

Acceptance должен фиксировать before/after document audit и отсутствие записей в кадровых event/assignment таблицах.

## 12. Этапы будущей реализации

| Этап | Слои и файлы | Миграции | Тесты / критерий готовности | Rollback |
|---|---|---|---|---|
| 1. Audit и document confirmation | lifecycle audit service/routes/schemas, HR drawer history/status badge | Вероятно расширение audit action check и confirmation/revision metadata | confirm/reopen, actor/reason/time, no event/assignment writes | Disable action behind permission; данные audit append-only |
| 2. Header editing | typed schema, dedicated correction command, drawer requisites tab | Вероятно source title/language/reason/version fields или constrained metadata | concurrency, duplicate conflict, no-op, registered correction | Disable correction route; audit remains |
| 3. Item editing | typed item command, shared field components, void/restore UI | Возможно item source name/match status/version | unresolved, type recalculation, void/restore, stale only target order | Disable route; no physical deletion |
| 4. Создание приказа | create wizard, duplicate preview, command orchestration | `MANUAL` source validation; возможно source identifier index | manual DRAFT, required reason, at least one item, duplicate matrix | Hide create action; draft data remains auditable |
| 5. RU/KK preview | server preview DTO, renderer adapters, Document tab | Нет, если preview stateless | no raw JSON, incomplete-data warning, print parity | Revert UI only |
| 6. Локальная приёмка 128 | isolated local smoke scripts/tests | Нет новой миграции | сценарий из раздела 11, no events/assignments | Transaction rollback or explicit audit correction, never direct SQL |
| 7. Rollout | RBAC matrix, observability, HR guide | Нет | staged HR user acceptance; read-only fallback remains | Feature flag / route disable, no destructive rollback |

## 13. Решения и открытые вопросы

| Вопрос | Предлагаемое решение | Нужен ответ пользователя | Блокирует реализацию |
|---|---|---:|---:|
| Источник фамилии директора | Проверить утверждённые кадровые DOC/DOCX; до этого оставить print fallback как временный | Да | Блокирует фиксацию канонического footer, не editor MVP |
| Исправление уже применённого кадрового события | **Принято:** document correction никогда автоматически не меняет `employee_events`/`person_assignments`; отдельный compensation/apply workflow находится вне редактора | Нет | Нет |
| Изменение номера REGISTERED | **Принято:** разрешено только через correction mode с обязательной причиной, duplicate-check, optimistic concurrency и append-only audit | Нет | Нет |
| Хранение исходного названия | **Принято:** использовать нормализованные nullable-поля `source_title` и `source_title_locale`; не хранить каноническое значение только в `storage_json` | Нет | Нет |
| Delete/void | UI — только void/restore; physical delete исключительно never-registered DRAFT service и не из editor UI | Нет | Нет |
| Права HR_HEAD/ADMIN | Первый этап: существующий privileged personnel-admin edit access; затем выделить narrow correction/confirmation permissions при audit matrix | Да | Да до production rollout |
| Связь confirmation с self-service | Self-service показывает только derived safe confirmation state и не даёт actions | Да | Нет для HR editor |
| `UNRESOLVED` subject | Хранить original name и explicit match status; не auto-match | Нет | Нет |
| Audit storage | Расширить lifecycle audit, если check/metadata позволяют; иначе отдельная append-only table | Нет, требует технической проверки | Да для этапа 1 |

### Рекомендуемый минимальный первый этап

Начать с **этапа 1: append-only document audit и confirmation/reopen для существующих приказов**, без изменения header/items и без новых кадровых событий. Он даёт прозрачный статус проверки, основу истории и безопасный permission boundary. Только после подтверждения модели audit и прав переходить к typed header correction.
