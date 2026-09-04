# WP-TD-001 — Инвентаризация удаления тестовых данных персонала

| Поле | Значение |
|---|---|
| Тип | Implementation Work Package / schema inventory |
| Статус | **Draft — Ready for Review** |
| Дата | 2026-09-04 |
| Основание | [test-personnel-data-deletion-approval-plan.md](test-personnel-data-deletion-approval-plan.md) |
| Этап | Только этап 1: инвентаризация существующей модели и связей |
| Реализация удаления | **Не** — endpoint, миграция, UI и DML не создавались |

> **Update 2026-09-04 / WP-TD-002:** продуктовые решения по разделу 12 приняты.
> Этот документ остаётся фактической инвентаризацией; актуальный серверный
> контракт описан в `WP-TD-002-test-personnel-deletion-approval-foundation.md`.

## 1. Резюме и границы исследования

Исследование выполнено по фактическому коду, миграциям и каталогу локальной PostgreSQL-БД. Подключение выполнено через loopback-адрес из локального `DATABASE_URL`; каждая диагностическая сессия принудительно переводилась в `SET TRANSACTION READ ONLY`. Текущая локальная ревизия Alembic — `x7y8z9a0b1c2`, она же единственный `head` репозитория.

Ни один `DELETE`, `UPDATE`, `INSERT`, DDL или вызов изменяющего endpoint не выполнялся. Production-БД не использовалась. Полные ИИН, телефоны, токены intake и иные ПДн в этот документ не включены.

Главный вывод: переход к проектированию модели запроса и статусов возможен, но реализацию физического удаления начинать нельзя. До неё владелец продукта должен утвердить матрицу и решить судьбу существующих PPR-журналов, submitted intake, legacy-таблицы `personnel`, фотографий/provenance и старого hard-delete.

Рекомендуемый MVP ограничен ранними претендентами без `Employee`, без legacy-назначения, без submitted/approved кадрового процесса, без приказов, документов, фото, пользователей и иных блокирующих связей. Действующих и бывших сотрудников в MVP включать нельзя.

## 2. Проверка исходников и фактической схемы

Проверены, в частности:

* базовая схема и последующие миграции в `alembic/versions/`;
* ORM в `app/db/models/`;
* SQL-репозитории PPR, кадровых заявок, intake, приказов, входящих документов и импорта;
* существующий runtime hard-delete в `app/services/employee_hard_delete_service.py` и маршруты в `app/directory/employees_routes.py`;
* локальный cleanup toolkit в `scripts/ops/local_data_cleanup/`;
* тесты hard-delete, personnel applications/intake, PPR, orders, incoming information, импорта и cleanup;
* RBAC в `app/security/admin_permissions.py`, `app/security/directory_scope.py`, `app/services/access_resolver_service.py` и `/auth/me` projection;
* фактические FK, `ON DELETE`, CHECK/UNIQUE constraints и пользовательские триггеры из `pg_constraint`, `pg_trigger` и `information_schema`.

Фактический каталог PostgreSQL имеет приоритет над ORM: значительная часть ядра создана raw SQL-миграциями и обслуживается SQL-репозиториями без ORM-классов `Person`/`Employee`.

## 3. Фактическая модель

### 3.1. Person, Employee и legacy personnel

`public.persons` — каноническая идентичность. Основные поля: `person_id`, ИИН, ФИО, разложенные компоненты имени, дата рождения, `match_key`, `person_status`, `merged_into_person_id`, `source`, ссылки на canonical snapshot/entry, timestamps. Разрешённые `source`: `canonical`, `manual`, `migration`, `enrollment`; отдельного `is_test` нет.

`public.employees` — операционный контур сотрудника, опционально связанный с `persons.person_id` через `RESTRICT`. Он хранит текущую проекцию подразделения/должности, активность, `operational_status`, даты, ставку и `enrollment_source`. Допустимые статусы: `draft`, `active`, `suspended`, `terminated`; допустимые источники: `enrollment`, `manual_emergency`, `migration`.

`public.personnel` — legacy-таблица кадровых назначений/контактов. Её `person_id` формально не является FK к `persons`, но логически совпадает с ним и используется views `contacts_working`, `contacts_inactive`, `key_contacts`. Любая строка, включая закрытую, является кадровой историей и блокирует foundation workflow; `date_to IS NULL` дополнительно означает действующее назначение.

`public.contacts.person_id` также не имеет формального FK. Следовательно, одна проверка каталога FK недостаточна.

### 3.2. Претенденты, заявки и intake

Претендент не является отдельной таблицей: это `persons` + `personnel_record_metadata.hr_relationship_context = 'CANDIDATE'`, обычно с `personnel_applications`.

`personnel_applications` ссылается на `persons` через `RESTRICT`. Заявка может ссылаться на кадровый приказ, выбранные оргконтуры и пользователей, выполнивших кадровые действия. Источник сейчас ограничен CHECK-constraint значением `paper`; это не provenance тестового создания.

Контур intake:

* `personnel_intake_links` — ссылки и секреты доступа, включая self-reference `superseded_by_link_id`; FK к заявке и пользователям — `RESTRICT`;
* `personnel_intake_drafts` — JSONB-анкета, один draft на заявку; FK к заявке и link — `RESTRICT`;
* `personnel_intake_section_reviews` — решения по разделам;
* `personnel_intake_transfers` — перенос intake в PPR;
* `personnel_intake_reconciliation_decisions` — долговечные решения сопоставления с `Person`.

`personnel_application_lifecycle_audit` и `personnel_application_resolution_audit` имеют `RESTRICT` к заявке. Текущая схема не позволяет сохранить эти строки и одновременно удалить родительскую заявку без отдельного архитектурного решения.

### 3.3. Личная карточка и профильные данные

Карточка PPR — композиция, а не одна таблица:

* shell/state: `personnel_record_metadata`;
* domain events: `personnel_record_events`;
* idempotency/command journal: `ppr_command_executions`;
* разделы: `person_education`, `person_training`, `person_relatives`, `person_external_employment`, `person_military_service`;
* фотографии: `person_photos`, provenance: `person_photo_sources`;
* проверки: `verification_tasks`, `verification_attestations`;
* коммуникационная идентичность: `person_telegram_bindings`, `person_telegram_bot_activations`.

Все разделы связаны с `persons` через `RESTRICT`. У `person_external_employment.employee_context_id` и `person_military_service.employee_context_id` формального FK нет. `person_photo_sources.source_application_id` — намеренная логическая ссылка: provenance должен пережить удаление заявки.

Триггеры БД запрещают `DELETE` из `person_photo_sources` и `verification_attestations`; `person_photos` также защищены mutation guard. Эти сущности нельзя обходить отключением триггеров.

### 3.4. Назначения и кадровые события

Каноническое назначение хранится в `person_assignments`; связь с `Person` — `RESTRICT`. Текущий Employee связывается с назначением через `employee_assignment_links`, оба FK — `RESTRICT`. История `enrollment_history` использует `SET NULL` к Person/Employee/assignment, но сама является кадровым журналом.

`employee_events` — append-oriented кадровые события с типами `HIRE`, `TRANSFER`, `CORRECTION`, `TERMINATION`, `POSITION_CHANGE`, `RATE_CHANGE`, `EMPLOYEE_ENROLLED_FROM_IMPORT`, `ANNUAL_LEAVE`. FK к Employee — `NO ACTION`; FK к кадровому приказу и его пункту — `RESTRICT`. Перед INSERT работает триггер классификации кадрового события.

`hr_personnel_change_events`, `enrollment_queue`, `hr_review_overrides` и связанные history/override таблицы образуют дополнительный lifecycle-контур. Некоторые FK имеют `SET NULL`, но это не означает допустимость физического удаления: журналы и утверждённые решения должны сохраняться.

### 3.5. Документы, приказы и вложения

`employee_documents` связан с Employee через `NO ACTION`; ссылки из импортных кандидатов и normalized records на созданный документ используют `SET NULL`. Это кадровые документы и в MVP всегда `BLOCK`.

`personnel_orders` и дочерние `personnel_order_items`, `personnel_order_attachments`, localized/editorial/print/evidence/lifecycle-audit таблицы соединены `RESTRICT`. Пункт приказа ссылается на Employee через `RESTRICT`; кадровое событие также может ссылаться на приказ/пункт через `RESTRICT`.

В производственных приказах `operational_order_signing_attestations.actor_employee_id` использует `SET NULL`, но участие сотрудника в официальном подписании должно блокировать удаление Employee.

`incoming_documents` может ссылаться на Person как отправителя и на Employee как отправителя/адресата через `RESTRICT`. Назначения, вложения, аудит, изменения сроков, переводы и связи с кадровыми/производственными приказами также используют `RESTRICT`. Любое такое участие — `BLOCK`.

### 3.6. Пользователи и RBAC

Однозначная системная роль существует:

* backend-константа `SYSTEM_ADMIN_ROLE_ID = 2`;
* `/auth/me.is_system_admin` вычисляется как `role_id == 2`;
* локальная БД: role `2 / ADMIN / System Administrator`;
* UI `isSystemAdminRole` также проверяет `role_id === 2`.

При этом есть второй, grant-based контур `access_roles` + `access_grants`: `SYSADMIN_CABINET`, `ACCESS_ADMIN`, `HR_ENROLLMENT_MANAGER`, `SECURITY_AUDITOR` и персональные/контурные grants. `SYSADMIN_CABINET` не равен системной роли для старого hard-delete: UI и backend удаления требуют именно canonical system admin.

Роль `HR_HEAD` существует отдельно (в локальной БД `role_id = 14`). Организационный scope вычисляется существующим personnel visibility resolver. Новые permissions пока не назначаются: выбор между platform role и access grants должен быть утверждён вместе с separation-of-duties.

### 3.7. Аудит

Используются несколько журналов:

* `security_audit_log` — общий security audit, FK к Person/Employee/User имеют `SET NULL`;
* `personnel_application_lifecycle_audit` и `personnel_application_resolution_audit` — `RESTRICT` к заявке;
* `personnel_order_lifecycle_audit` — `RESTRICT` к приказу;
* `incoming_document_audit` — `RESTRICT` к документу;
* `employee_termination_record_audit`, `hr_review_override_history`, `hr_sync_audit_log`, task/document-specific журналы.

`security_audit_service.py` называет `security_audit_log` append-only, но в фактической БД нет запрещающего UPDATE/DELETE триггера. Append-only сейчас обеспечивается соглашением приложения, а существующий локальный cleanup toolkit даже допускает явное включение строк этой таблицы в allowlist. Для нового механизма это недостаточно.

Старый `EMPLOYEE_HARD_DELETED` audit сохраняет ФИО в metadata. Это противоречит требованию минимизации ПДн для нового механизма; новый аудит должен хранить технические ID/hash и безопасные агрегаты.

### 3.8. Staging и provenance

Обнаружены два основных импортных контура:

1. HR import: `hr_import_batches`, `hr_import_rows` (raw/normalized JSONB), `hr_import_normalized_records`, document candidates, canonical snapshots/baselines, monthly references, change events и publication origins.
2. Control-list import: `control_list_import_runs`, `control_list_import_sheets`, `control_list_import_rows`, `control_list_import_cells`, mapping/apply runs.

Есть также `employees_import_stage`, operational-order import staging и immutable `operational_order_text_provenance`.

Импортные batch/row записи часто разделяются несколькими людьми. Их нельзя удалять вместе с одной Person/Employee. Ссылки из канонических объектов на staging в основном должны обнуляться по существующему `SET NULL` либо сохраняться как исторический provenance. Отдельного универсального `is_test` в фактической схеме нет.

## 4. Результаты по локальным маскам

Поиск выполнялся параметризованным `ILIKE` только для диагностики и не менял данные.

| Маска | Person | Employee | Заявки | HR import rows | Control-list rows | `employees_import_stage` |
|---|---:|---:|---:|---:|---:|---:|
| `Debug Applicant*` | 3 | 0 | 3 | 0 | 0 | 0 |
| `Demo Intake Applicant*` | 8 | 0 | 8 | 0 | 0 | 0 |

Итого найдено 11 отдельных Person и 11 заявок. Это претенденты, а не Employee и не staging-записи:

* все Person: `source=manual`, `person_status=active`;
* все metadata: `hr_relationship_context=CANDIDATE`, `ppr_lifecycle_state=CREATED`;
* `Debug Applicant*`: 3 заявки `intake_pending`;
* `Demo Intake Applicant*`: 2 заявки `intake_pending`, 6 заявок `intake_submitted`;
* ни одна заявка не связана с кадровым приказом;
* ни одна цель не имеет `employees`, `person_assignments`, employee events/documents, входящих документов, фото, Telegram binding или пользователя через Employee.

Фактические дочерние строки без раскрытия ПДн:

| Маска | Связь | Количество |
|---|---|---:|
| `Debug Applicant*` | `personnel_intake_drafts` | 3 |
| `Debug Applicant*` | `personnel_intake_links` | 3 |
| `Debug Applicant*` | `personnel_record_events` (`PPR_CREATED`) | 3 |
| `Debug Applicant*` | `ppr_command_executions` (`MaterializePPR/completed`) | 3 |
| `Demo Intake Applicant*` | `personnel_intake_drafts` | 8 |
| `Demo Intake Applicant*` | `personnel_intake_links` | 15 |
| `Demo Intake Applicant*` | `personnel_application_lifecycle_audit` | 3 |
| `Demo Intake Applicant*` | `personnel_record_events` (`PPR_CREATED`) | 8 |
| `Demo Intake Applicant*` | `ppr_command_executions` (`MaterializePPR/completed`) | 8 |
| `Demo Intake Applicant*` | logical `contacts` | 1 |
| `Demo Intake Applicant*` | logical legacy `personnel`, действующая строка | 1 |

Последняя legacy-строка имеет `date_to IS NULL` и попадает в key-contact projection. Соответствующая цель должна быть заблокирована независимо от тестоподобного имени.

У заявок есть слабые признаки происхождения: 3 ключа с префиксом `debug-*`, 7 с `demo-verify-*`, один иной. Скрипт `scripts/verify_applicant_intake_demo.py` действительно создаёт `Demo Intake Applicant` и `demo-verify-*`. Но `idempotency_key`, имя, `source=manual` и наличие такого скрипта не являются защищённым `is_test`/provenance. Они достаточны только как объяснение кандидата оператору, но не как единственное основание удаления.

## 5. Матрица связей

Решения ниже относятся к предлагаемому безопасному MVP. `DELETE` всегда означает: только для уже доказанной тестовой цели, только по фиксированному ID и только при отсутствии любого `BLOCK`/`DECISION_REQUIRED`.

| Таблица/сущность | Связь с целью | Фактический FK или логическая связь | ON DELETE | Решение | Причина |
|---|---|---|---|---|---|
| `persons` | Корень претендента | PK; self-FK `merged_into_person_id` | `RESTRICT` | `DELETE` | Допустимо только для доказанного тестового Person без независимых контуров |
| `employees` | Операционный сотрудник | `person_id -> persons` | `RESTRICT` | `BLOCK` | Employee исключён из MVP; активный/бывший сотрудник требует отдельной политики |
| `personnel` | Legacy назначение | Логическая связь по `person_id`, FK отсутствует | — | `BLOCK` | Может означать действующее или историческое трудоустройство |
| `contacts` | Контакт Person | Логическая связь по `person_id`, FK отсутствует | — | `BLOCK` | Любой legacy-контакт безусловно блокирует foundation workflow |
| `contacts_working`, `contacts_inactive` | Проекции | Views над `contacts`/`personnel` | — | `RETAIN` | Не являются самостоятельно удаляемыми строками |
| `contact_access`, `key_contacts`, `org_unit_key_staff` | Legacy contact/organizational rows | Логическая связь по `person_id` | logical | `BLOCK` | Фактические таблицы схемы; широкое organizational право не доказывает синтетическое происхождение |
| `personnel_record_metadata` | Shell личной карточки | FK `person_id -> persons` | `RESTRICT` | `INFORMATIONAL` | Техническое состояние входит в fingerprint и само не запрещает согласование |
| `personnel_record_events` | PPR domain event | FK к Person | `RESTRICT` | `TOMBSTONE_REQUIRED` | Create/submit/approve разрешены; future execution запрещён до независимого tombstone/hash |
| `ppr_command_executions` | Idempotency/command journal | FK к Person | `NO ACTION` | `TOMBSTONE_REQUIRED` | Create/submit/approve разрешены; future execution запрещён до независимого tombstone/hash |
| `person_education` | Раздел карточки | FK к Person; import refs `SET NULL` | `RESTRICT` | `BLOCK` | Подтверждающие кадровые данные |
| `person_training` | Раздел карточки | FK к Person; import refs `SET NULL` | `RESTRICT` | `BLOCK` | Подтверждающие кадровые данные |
| `person_relatives` | Раздел карточки | FK к Person | `RESTRICT` | `BLOCK` | ПДн третьих лиц и профильная история |
| `person_external_employment` | Раздел карточки | FK к Person; `employee_context_id` логический | `RESTRICT` | `BLOCK` | Provenance и история занятости |
| `person_military_service` | Раздел карточки | FK к Person; `employee_context_id` логический | `RESTRICT` | `BLOCK` | Ограниченные/юридически значимые данные |
| `person_photos` | Каноническое фото | FK к Person | `RESTRICT` + guard trigger | `BLOCK` | Mutation guard и отдельное файловое хранилище |
| `person_photo_sources` | Provenance фото | Composite FK к photo/person; application — логическая ссылка | `RESTRICT`; DELETE запрещён trigger | `BLOCK` | Append-only ledger и mutation guard запрещают foundation workflow |
| `person_telegram_bindings` | Внешняя идентичность | FK к Person | `RESTRICT` | `BLOCK` | Внешнее состояние и безопасность |
| `person_telegram_bot_activations` | Активация бота | FK к Person | `RESTRICT` | `BLOCK` | Внешнее состояние и безопасность |
| `person_assignments` | Каноническое назначение | FK к Person | `RESTRICT` | `BLOCK` | Любое назначение — кадровая история; активное обязательно блокирует |
| `employee_assignment_links` | Employee ↔ assignment | FK к Employee и assignment | `RESTRICT` | `BLOCK` | Подтверждает операционное зачисление |
| `enrollment_queue` | Очередь зачисления | FK к Person/assignment | `RESTRICT` | `BLOCK` | Незавершённое или завершённое кадровое решение |
| `enrollment_history` | История зачисления | FK к Person/Employee `SET NULL`, к queue `RESTRICT` | mixed | `INFORMATIONAL` | Retained кадровый журнал входит в fingerprint |
| `employee_events` | Кадровые события | FK к Employee `NO ACTION`, к orders/items `RESTRICT` | mixed | `BLOCK` | Официальная кадровая история |
| `employee_identities` | Технические идентичности Employee | FK к Employee | `CASCADE` | `BLOCK` | Employee и внешние identity не поддерживаются MVP |
| `employee_documents` | Кадровые документы | FK к Employee | `NO ACTION` | `BLOCK` | Документы нельзя удалять этим механизмом |
| `employee_import_profile_overrides` | Override карточки | FK к Employee | `CASCADE` | `BLOCK` | Каскад может стереть решение HR незаметно |
| `employee_termination_records` | Увольнение | FK к Employee/event/batch/row | `RESTRICT` | `BLOCK` | Доказывает бывшего сотрудника и юридическую историю |
| `employee_termination_record_audit` | Аудит увольнения | FK к termination record | `RESTRICT` | `INFORMATIONAL` | Retained audit входит в fingerprint; Employee всё равно `BLOCK` |
| `employee_onboardings` | Адаптация | FK к Employee и application | `RESTRICT` | `BLOCK` | Кадровый процесс, может иметь исполнителей/вложения |
| `employee_onboarding_checklist_items` | Этапы адаптации | FK к onboarding `CASCADE`; employee assignees `RESTRICT` | mixed | `BLOCK` | Кадровые действия и cross-employee связи |
| `employee_onboarding_checklist_attachments` | Вложения адаптации | FK к checklist item | `CASCADE` | `BLOCK` | Вложения не должны исчезать каскадом |
| onboarding notifications/audit | Уведомления и аудит | FK к onboarding/items/users | mixed | `BLOCK` | Часть блокирующего onboarding-контура |
| `personnel_applications` | Заявка претендента | FK к Person | `RESTRICT` | `INFORMATIONAL` / `HR_ATTESTATION_REQUIRED` | Pending не блокирует; submitted требует формальной HR-attestation; иной статус `BLOCK` |
| `personnel_intake_links` | Intake links/tokens | FK к application/users/self | `RESTRICT` | `INFORMATIONAL` | Полный state/token digest входит в fingerprint без сохранения payload |
| `personnel_intake_drafts` | Intake JSONB | FK к application/link | `RESTRICT` | `INFORMATIONAL` | Полный state/payload digest входит в fingerprint без сохранения payload |
| `personnel_intake_section_reviews` | Review разделов | FK к application/user | `RESTRICT` | `BLOCK` | Наличие кадрового рассмотрения блокирует MVP |
| `personnel_intake_transfers` | Перенос в PPR | FK к application/user | `RESTRICT` | `BLOCK` | Означает применение данных в каноническую карточку |
| `personnel_intake_reconciliation_decisions` | Решения сопоставления | FK к application и Person | `RESTRICT` | `BLOCK` | Durable decision; возможны внешние эффекты |
| `personnel_application_blockers` | Blocker реестр | FK к application | `CASCADE` | `BLOCK` | Каскад не должен скрыто стереть blocker/evidence |
| `personnel_application_lifecycle_audit` | Audit заявки | FK к application | `RESTRICT` | `TOMBSTONE_REQUIRED` / `BLOCK` | Ранний allowlist lifecycle требует tombstone; официальный lifecycle блокирует |
| `personnel_application_resolution_audit` | Решение директора | FK к application | `RESTRICT` | `BLOCK` | Официальное решение и аудит |
| `personnel_orders` | Кадровый приказ | application/event references | `RESTRICT` | `BLOCK` | Приказ не удаляется вместе с человеком |
| `personnel_order_items` | Пункт приказа | FK к order и Employee | `RESTRICT` | `BLOCK` | Официальное кадровое основание |
| order attachments/editorial/evidence/localized/`personnel_order_prints` | Дочерние данные приказа | FK к order/item | `RESTRICT` | `BLOCK` | Юридически значимый документный контур |
| `personnel_order_lifecycle_audit` | Аудит приказа | FK к order | `RESTRICT` | `INFORMATIONAL` | Retained audit; сам приказ и его участие остаются `BLOCK` |
| `incoming_documents` | Отправитель/адресат | FK к Person/Employee | `RESTRICT` | `BLOCK` | Официальный входящий документ |
| incoming assignments/attachments/audit/deadlines/transfers/links | Дочерние связи документа | FK к incoming document | `RESTRICT` | `BLOCK` | Документный контур полностью сохраняется |
| `operational_order_signing_attestations` | Подписант Employee | FK к Employee | `SET NULL` | `BLOCK` | Участие в официальном производственном приказе |
| `users` | Учётная запись Employee | `employee_id -> employees` | `NO ACTION` | `BLOCK` | Новый механизм не должен автоматически удалять аккаунт |
| `access_grants` | Персональные grants пользователя | FK к users для actor columns; target — полиморфная логическая ссылка | mixed | `INFORMATIONAL` | Retained security history входит в fingerprint |
| `personnel_visibility_assignments` | Visibility grants | FK к user/org/position | mixed | `INFORMATIONAL` | Retained security policy/audit входит в fingerprint |
| user linkage review/execute items | Связь user ↔ Employee | FK к users/Employee | `RESTRICT`/`SET NULL` | `BLOCK` | External identity review/operation journal |
| `security_audit_log` | Общий аудит | FK к Person/Employee/User | `SET NULL` | `INFORMATIONAL` | Retained audit входит в fingerprint без копирования ПДн |
| `verification_tasks` | Проверка карточки | FK к Person | `RESTRICT` | `BLOCK` | Проверяемый кадровый объект |
| `verification_attestations` | Аттестация проверки | FK к Person/task | `RESTRICT`; DELETE запрещён trigger | `BLOCK` | Неизменяемое подтверждение блокирует workflow |
| `identity_reconciliation_items` | Identity resolution | FK к Person `RESTRICT`, Employee `SET NULL` | mixed | `BLOCK` | Решение идентичности нельзя терять без отдельной политики |
| `hr_personnel_change_events` | HR lifecycle event | FK к Person/assignment `SET NULL` | `SET NULL` | `BLOCK` | Источник кадровой синхронизации |
| `hr_review_overrides` и history | HR overrides | Person/assignment refs `SET NULL`; history append-only | mixed | `INFORMATIONAL` | Retained решения и provenance входят в fingerprint |
| `hr_import_batches` | Импортный batch | Косвенная связь через rows/records | mixed | `RETAIN` | Batch общий для многих субъектов |
| `hr_import_rows` | Исходная staging-строка | Employee FK `SET NULL`, JSONB provenance | `SET NULL` | `INFORMATIONAL` | Retained импорт и аудит качества входят в fingerprint |
| `hr_import_normalized_records` | Нормализованный staging | Employee/document refs `SET NULL` | `SET NULL` | `INFORMATIONAL` | Retained review/provenance входят в fingerprint |
| canonical snapshots/baselines/monthly refs | Канонический импорт | Employee ID FK или логическая ссылка | `SET NULL`/logical | `INFORMATIONAL` | Retained опубликованные данные входят в fingerprint |
| control-list import runs/sheets/rows/cells/apply | Импорт и apply journal | Иерархия import run | mostly `CASCADE` внутри batch | `RETAIN` | Provenance и apply history, batch не удаляется по Person |
| `employees_import_stage` | Legacy staging | Логический `employee_id`, formal FK отсутствует | — | `RETAIN` | Нельзя доверять/удалять по имени или диапазону |

## 6. Allowlist, blockers и порядок

### 6.1. Точный allowlist для предлагаемого раннего applicant MVP

Следующие таблицы потенциально допустимы к удалению после доказательства тестового происхождения и при полном отсутствии blockers:

1. `personnel_intake_drafts`;
2. `personnel_intake_links`;
3. `personnel_applications`;
4. `personnel_record_metadata`;
5. `persons`.

Это не готовый исполняемый allowlist. Все 11 Person имеют `personnel_record_events` и
`ppr_command_executions`: по решению WP-TD-002A они не блокируют create/approve, но запрещают
future execution до независимого tombstone/hash. Таблицы с нерешённым
`DECISION_REQUIRED` нельзя автоматически добавлять в allowlist.

### 6.2. Полный список категорий blockers

Удаление цели блокируют:

* любой `employees`, включая `draft`, `active`, `suspended`, `terminated`;
* любая legacy-строка `personnel`; отдельно — действующая строка `date_to IS NULL`;
* `person_assignments`, `employee_assignment_links`, enrollment queue/history;
* кадровые события, termination records, HR change events и identity reconciliation;
* employee documents, кадровые и производственные приказы, их пункты/вложения/attestations;
* incoming documents в любой роли Person/Employee;
* user account, Telegram identity или активная внешняя привязка;
* onboarding, section review, intake transfer/reconciliation decision;
* application blockers, director resolution и связанный personnel order;
* photos/photo provenance, verification tasks/attestations;
* любое неизвестное входящее FK или новая логическая ссылка;
* любое расхождение с зафиксированным fingerprint при повторной проверке.

Submitted intake (`intake_submitted`) относится к `HR_ATTESTATION_REQUIRED`: create/submit
разрешены, а approve возможен только после явного подтверждения `HR_HEAD`, что запись
синтетическая и не является официальным заявлением.

### 6.3. Предварительный порядок удаления

Для цели, прошедшей все проверки, порядок должен вычисляться из утверждённого allowlist и ещё раз сверяться с live catalog:

1. зафиксировать audit attempt вне удаляемого контура;
2. заблокировать request и точные target rows от конкурентного исполнения;
3. удалить `personnel_intake_drafts`;
4. удалить `personnel_intake_links` в порядке, учитывающем self-FK `superseded_by_link_id` (сначала строки, которые ссылаются на superseding link);
5. удалить `personnel_applications`;
6. удалить разрешённые PPR technical rows — только если решение по ним будет утверждено;
7. удалить `personnel_record_metadata`; любой `contacts` остаётся безусловным `BLOCK`;
8. удалить `persons`;
9. записать итоговые counts/hash в сохраняемый audit в той же атомарной операции;
10. проверить, что удалён весь утверждённый набор и ни одна строка вне него не затронута.

Нельзя полагаться на cascade как на порядок удаления.

### 6.4. Данные, которые должны остаться

Сохраняются:

* request/approval/execution audit нового механизма;
* `security_audit_log` и специализированные юридически значимые audit/provenance журналы;
* import batches, raw/normalized staging, canonical snapshots и publication origins;
* кадровые/производственные приказы, входящие документы и вложения;
* сведения о реальных пользователях и grants;
* неизменяемые photo/verification provenance;
* безопасный hash точного списка ID, counts по таблицам, actors и timestamps без лишних ПДн.

## 7. Риски существующих каскадов и hard-delete

Фактические опасные каскады:

* Employee → `employee_identities`, `employee_import_profile_overrides` (`CASCADE`);
* application → `personnel_application_blockers` (`CASCADE`);
* onboarding → checklist, notifications, audit (`CASCADE`);
* import batch → rows/normalized/document candidates/AI drafts/diff removals (`CASCADE`);
* user → notifications, task-event recipients/deliveries, memberships и visibility rows (`CASCADE`);
* control-list/import и operational-order child hierarchies имеют внутренние cascades.

Существующий runtime hard-delete представляет отдельный блокирующий риск:

* `DELETE /directory/employees/{employee_id}` и `POST /directory/employees/bulk-delete` доступны canonical system admin;
* одобрение `HR_HEAD` отсутствует;
* bulk-delete использует отдельную транзакцию на каждого Employee и допускает partial success;
* сервис явно удаляет кадровые события, документы, заявления/intake, assignment data, пользователя и Person shell;
* cross-employee references местами очищаются через `UPDATE ... SET NULL`;
* список таблиц реализован динамическими helper-функциями и не равен утверждённой матрице;
* audit metadata включает ФИО;
* тесты закрепляют текущую каскадную семантику.

Новый механизм нельзя строить поверх этого endpoint без предварительного решения о его отключении/ограничении и замены его semantics. Иначе двойное подтверждение можно будет обойти старым маршрутом.

Локальный `scripts/ops/local_data_cleanup` имеет полезные guardrails: loopback, dry-run, внешний allowlist, expected signatures, FK graph, backup/confirmation и одна транзакция. Но его общий runner также умеет включать audit, users, employees и persons в удаление и не покрывает новые applicant/PPR/incoming связи полностью. Его можно использовать как источник паттернов, не как production implementation.

## 8. Различие претендента и сотрудника

| Аспект | Ранний претендент | Действующий/бывший сотрудник |
|---|---|---|
| Базовый контур | Person + metadata + application/intake | Person + Employee + assignments/lifecycle |
| Допустимость MVP | Возможна после доказательства test provenance | Запрещена |
| Назначения | Должны отсутствовать, включая legacy `personnel` | Обычно существуют/существовали; `BLOCK` |
| Официальные приказы/кадровые события | Должны отсутствовать; `BLOCK` | Юридическая кадровая история; `BLOCK` |
| PPR events/command executions | `TOMBSTONE_REQUIRED`: create/submit/approve допустимы, future execution нет | Не являются основанием разрешить удаление Employee; Employee остаётся `BLOCK` |
| Документы/вложения | Должны отсутствовать | `BLOCK` |
| Пользователь | Должен отсутствовать | Аккаунт не удаляется этим механизмом |
| Application/intake lifecycle | `intake_pending` — `INFORMATIONAL`; `intake_submitted` — `HR_ATTESTATION_REQUIRED`; официальный lifecycle/resolution — `BLOCK` | Официальный lifecycle — `BLOCK` |
| Metadata/intake links/drafts | `INFORMATIONAL`, полный canonical digest входит в fingerprint | Не отменяют Employee `BLOCK` |
| Retained audit/provenance | `INFORMATIONAL`, сохраняется и входит в fingerprint; provenance identity/validity обязательны для basis `PROVENANCE` | Сохраняется; физическое удаление не поддерживается |

`Employee.is_active = false` или `operational_status = terminated` не делает запись тестовой и не разрешает её физическое удаление.

## 9. Безопасный контракт маски

### 9.1. Разрешённые поля

Для MVP маску разрешить только по:

* `persons.full_name` для типа `PERSON/APPLICANT`;
* `employees.full_name` только в режиме предварительного обнаружения blockers, но не как разрешение удалить Employee;
* будущему отдельному неизменяемому `test_provenance_key`, если он будет утверждён и добавлен позднее.

`persons.match_key` не следует показывать как «тестовый идентификатор»: он используется identity matching и может быть производным от реальных данных. Поиск по JSONB staging, ИИН, телефону, email, token/hash, свободному SQL-полю и всем таблицам сразу запрещается. Точные технические ID поддерживаются отдельным параметром без маски.

### 9.2. Синтаксис и нормализация

Предлагаемый контракт:

* Unicode NFC, trim и collapse повторных пробелов;
* длина нормализованной маски 3–100 Unicode code points;
* не более 10 wildcard-символов и не менее 3 буквенно-цифровых литералов;
* `*` означает 0+ символов, `?` — ровно один символ;
* `%`, `_` и `\` всегда считаются литералами и экранируются;
* regex/SQL fragments не интерпретируются;
* поиск без учёта регистра через параметризованный PostgreSQL `ILIKE ... ESCAPE '\'`;
* преобразование: сначала экранировать `\`, `%`, `_`, затем заменить только контрактные `*` на `%` и `?` на `_`;
* значение передаётся bind parameter, а имена полей выбираются только из server-side allowlist.

### 9.3. Лимиты и фиксация

Сервер запрашивает максимум 201 строку. Если найдено более 200, запрос отклоняется как слишком широкий — результаты нельзя молча усекать.

После ручного подтверждения сервер формирует отсортированный массив объектов `{target_type, technical_id}`. Hash считается по canonical JSON UTF-8 с фиксированной схемой/version marker, например SHA-256. Маска и фильтры сохраняются только как explainability metadata. Approval и execution используют исключительно этот массив ID, его version и hash.

Fingerprint должен включать по каждой цели: core row version/timestamps, тип/статус, IDs и безопасные state markers всех allowlisted и blocking links, а также текущую ревизию policy/relationship matrix. Появление новой связи или изменение статуса аннулирует approval.

### 9.4. Preview для ролей

Сисадмину и `HR_HEAD` показываются:

* технический ID и тип (`APPLICANT`, `EMPLOYEE_BLOCKED`);
* ФИО в объёме, разрешённом scope;
* маскированный ИИН только при наличии отдельного права; полный ИИН не нужен для этой операции;
* `person_status`, application/intake status, Employee/legacy employment indicator;
* source/provenance и объяснение, почему запись считается тестовой;
* counts связанных строк по категориям без содержимого анкет/документов;
* явные blockers и `DECISION_REQUIRED`;
* список предполагаемых таблиц/counts, hash/version и срок действия.

Телефоны, email, содержимое intake JSONB, документы, токены и полные идентификаторы не показываются в очереди без отдельной необходимости и права.

## 10. Кабинеты, очереди и точки размещения

### 10.1. Системный администратор

Фактический кабинет — `/admin/system`, компонент `SystemAdminClient`, с tabs users/access/visibility/enrollment/assignments/user-linkage-review/audit и отдельными маршрутами `/admin/system/personnel-lifecycle`, `/admin/system/personnel-identity/operations`.

Рекомендуемая точка: отдельный sibling route `/admin/system/test-personnel-data` с названием «Управление тестовыми данными персонала» и ссылкой из `SystemAdminClient`. Не помещать исполнение в общий список сотрудников, где уже есть legacy hard-delete.

Доступ должен проверяться backend по отдельным permissions, а не только видимостью UI. Хотя canonical system admin однозначно подтверждён, автоматическое назначение новых permissions роли `ADMIN` пока не утверждено.

### 10.2. HR_HEAD

Фактический HR-контур — `/directory/personnel/*` и `PersonnelSubNav`: кадровый журнал, личные карточки/претенденты, onboarding, приказы, документы, verification и import. Роль `HR_HEAD` получает этот контур через `has_personnel_admin`/grants и действующий organizational scope.

Рекомендуемая точка: `/directory/personnel/test-data-deletion-approvals` как отдельная очередь «Согласование удаления тестовых данных» в `PersonnelSubNav`. Backend должен дополнительно требовать точный approval permission и роль/actor separation; один `has_personnel_admin` недостаточен.

### 10.3. Существующие паттерны согласований

Можно переиспользовать архитектурные идеи, но не таблицы напрямую:

* enrollment queue с approve/reject/apply;
* user-linkage review queue + отдельный execute;
* personnel application resolution/lifecycle audit;
* tasks `WAITING_APPROVAL` с approve/reject;
* HR review overrides и append-only history;
* personnel order lifecycle audit/idempotency.

Для удаления нужен отдельный domain aggregate, потому что общая task approval не фиксирует immutable target ID set, relationship fingerprint и атомарный execution result.

## 11. Рекомендуемый MVP

1. Только `APPLICANT`, у которого отсутствуют `employees` и legacy `personnel`.
2. `intake_pending` допускается; `intake_submitted` требует явной `HR_ATTESTATION_REQUIRED` при отсутствии иных blockers.
3. Только `persons.source=manual` плюс защищённый provenance/явный reviewed allowlist; имя или `idempotency_key` сами по себе недостаточны.
4. Нет assignments, orders, events, documents, photos, verification, onboarding, review/transfer/reconciliation, users, Telegram и import application effects.
5. Все unknown links fail closed.
6. Отдельный request/approval/execution audit с минимизацией ПДн.
7. Legacy hard-delete должен быть закрыт новым permission/feature gate либо выведен из production маршрутизации до включения MVP.

По уточнению WP-TD-002A десять записей допускаются к exact `LEGACY_MANIFEST` и approve;
шесть submitted требуют явной HR attestation. Одна Demo с legacy personnel/contact остаётся
`BLOCK`. PPR events/commands запрещают только future execution до tombstone/hash.

## 12. Блокирующие риски и вопросы владельцу продукта

1. Решено: `intake_submitted` требует явной HR-attestation и не является безусловным `BLOCK`.
2. Решено для foundation: `personnel_record_events`, `ppr_command_executions` и допустимый
   ранний lifecycle — `TOMBSTONE_REQUIRED`; их окончательная судьба определяется отдельным
   execution-пакетом после независимого tombstone/hash.
3. Решено: официальный lifecycle/resolution audit остаётся `BLOCK`; допустимый ранний
   lifecycle относится к `TOMBSTONE_REQUIRED` и требует будущего redesign/snapshot.
4. Может ли кандидат с любым профильным разделом быть удалён, или наличие education/training/relative/employment/military всегда блокирует? Рекомендация MVP: блокировать.
5. Подтвердить, что любая строка legacy `personnel`, даже закрытая, означает кадровую историю и блокирует.
6. Подтвердить абсолютный запрет Employee в MVP, включая inactive/terminated/draft.
7. Утвердить долговечный test provenance. Предпочтительно отдельный server-controlled marker/source record, а не имя/маска/idempotency key.
8. Решено: существующие web hard-delete endpoints безусловно возвращают
   `410 TD_LEGACY_HARD_DELETE_DISABLED`; включаемого production escape hatch нет.
9. Подтвердить retention для `security_audit_log` на уровне БД; сейчас физическая неизменяемость не обеспечена trigger/privilege policy.
10. Определить, кто получает request/execute permissions: canonical role `ADMIN`, access grant `SYSADMIN_CABINET` или новый специализированный grant. Автоматическое назначение не выполнять до решения.
11. Определить, достаточно ли role code `HR_HEAD` вместе с approval permission, и как применять organizational scope к смешанному набору целей.
12. Утвердить лимит 200 целей и 24-часовой срок approval.

## 13. Решение о следующем этапе

К проектированию модели запроса, version/hash/fingerprint, статусов и immutable audit можно переходить в режиме design-only.

Нельзя переходить к endpoint исполнения, миграции удаления, кнопке исполнения или production DML, пока:

* владелец продукта не утвердит эту матрицу;
* не закрыты вопросы 1–10 выше;
* не определён способ сохранения audit/provenance при удалении parent rows;
* старый hard-delete не исключён как обход двойного подтверждения;
* allowlist не проверен повторно на PostgreSQL после любых новых миграций.

## 13A. Уточнение WP-TD-002A

Для реализации действует четырёхкатегорийная server-owned matrix из WP-TD-002A.
Предыдущая классификация `personnel_record_events`, `ppr_command_executions` и допустимого
раннего application lifecycle как постоянного `BLOCK` отменена: это
`TOMBSTONE_REQUIRED`, разрешающий create/approve и запрещающий только future execution.
Submitted synthetic application требует `HR_ATTESTATION_REQUIRED`. По фактическим 11
локальным записям десять проходят точный `LEGACY_MANIFEST` и согласование (шесть — только с
явной attestation), одна с legacy personnel/contact остаётся `BLOCK`. Runtime не содержит
их имён, количества или ID.

## 14. Закрытие решений для WP-TD-002

Для foundation закреплены следующие уточнения матрицы:

* `contacts` меняется с предварительного `DELETE` на `BLOCK`: логический контакт нельзя автоматически признать синтетическим;
* `intake_submitted` меняется с безусловного blocker на `HR_ATTESTATION_REQUIRED`, но только при отсутствии иных blockers;
* профильные PPR-разделы и Telegram-связи — `BLOCK`;
* `personnel_record_events`, `ppr_command_executions` и допустимый early application lifecycle — `TOMBSTONE_REQUIRED`: create/approve разрешены, future execution запрещён до tombstone/hash; resolution/официальный lifecycle остаются `BLOCK`;
* Employee любого статуса, legacy `personnel`, назначения, кадровые события, приказы, официальные документы, пользователи и внешние identity — `BLOCK`;
* существующие записи без provenance могут использовать только `LEGACY_MANIFEST`; автоматический backfill по имени/маске запрещён;
* будущие записи должны иметь server-controlled append-only provenance;
* canonical `ADMIN` подтверждён и получает REQUEST/EXECUTE/AUDIT_READ, `HR_HEAD` получает APPROVE/AUDIT_READ через точные `access_grants` на `ROLE`;
* лимит preview — 200, approval TTL — 24 часа;
* старые Employee hard-delete endpoints сохраняют URL только для совместимости и безусловно отвечают HTTP 410 во всех web-средах; escape hatch отсутствует.

После этих решений можно проектировать и реализовывать request/approval foundation.
Переход к физическому удалению по-прежнему запрещён до отдельного WP и утверждения
allowlist/tombstone-модели.
