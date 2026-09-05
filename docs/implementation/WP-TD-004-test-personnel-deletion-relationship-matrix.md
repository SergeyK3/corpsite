# WP-TD-004 — Матрица связей для удаления тестовых записей персонала

| Поле | Значение |
|---|---|
| Тип | Analysis / relationship and deletion-order matrix |
| Статус | **Approved — Ready for applicant-only implementation planning** |
| Дата анализа | 2026-09-05 |
| Фактическая БД | PostgreSQL `corpsite`, Alembic `b1c2d3e4f5a6` |
| Политика foundation | `WP-TD-002C/v4`, 88 server-owned relationship rules |
| Готовность execution | **Нет**: текущая схема `b1c2d3e4f5a6` ещё не готова к execution |
| Реализация | **Нет**: endpoint, migration, execution service/UI и DML удаления не создавались |

## 1. Цель и границы

Документ фиксирует фактические связи `Person`, `Employee`, претендента и зависимых записей перед возможным проектированием физического удаления. Источники истины, в порядке приоритета:

1. каталог локальной PostgreSQL (`pg_constraint`, `pg_trigger`, `pg_class`) в транзакции `READ ONLY`;
2. применённая цепочка Alembic до `b1c2d3e4f5a6`;
3. raw-SQL и ORM-модели в `app/db/models/`;
4. фактические 88 правил `RELATIONSHIP_MATRIX` в `app/services/test_personnel_deletion_service.py`;
5. решения WP-TD-001…003A.

`Person` и `Employee` не представлены самостоятельными SQLAlchemy ORM-классами. `persons` создана raw-SQL миграцией `u3v4w5x6y7z8`, `employees` — baseline `02b0d99063cd` и расширена той же `u3…`. Претендент также не отдельная таблица: это `persons` + `personnel_record_metadata.hr_relationship_context='CANDIDATE'` + один или несколько эпизодов `personnel_applications`. Для заявок/intake/PPR-разделов ORM есть, но окончательным считается каталог PostgreSQL.

В ходе анализа не выполнялись `DELETE`, `UPDATE`, `INSERT`, DDL, изменяющие endpoint или отключение triggers/constraints.

### 1.1. Проверенная карта исходников схемы

- `02b0d99063cd_baseline.py` — исходная `employees` и legacy ядро;
- `u3v4w5x6y7z8_adr042_phase_b2_1_schema.py` — `persons`, Person↔Employee, assignments, enrollment и security audit;
- `q7r8s9t0u1v2…`, `r8s9t0u1v2w3…`, `s9t0u1v2w3x4…`, `q8r9s0t1u2v3…`, `t0u1v2w3x4y5…`, `u1v2w3x4y5z6…` — application, intake, review/transfer, reconciliation, director resolution и lifecycle audit;
- `j0k1l2m3n4o5…`, `q1r2s3t4u5w6…`, `l2m3n4o5p6q7…` — PPR metadata, person-owned sections/events и command idempotency;
- `c0d1e2f3a4b5…`, `l3m4n5o6p7q8…`, `o6p7q8r9s0t1…`, `p7q8r9s0t1u2…` — photos/provenance, Telegram и verification;
- `p0q1r2s3t4u5…`, `s3t4u5v6w7x8…`, `t4u5v6w7x8y9…` — personnel orders, editorial/evidence и lifecycle audit;
- `v1w2x3y4z5a6…`, `w2x3y4z5a6b7…` — onboarding aggregate, checklist, notifications и audit;
- `d1e2f3a4b5c6…` и последующие WP-II миграции — incoming information и междоменные links;
- `y8z9a0b1c2d3`, `z9a0b1c2d3e4`, `a0b1c2d3e4f5`, `b1c2d3e4f5a6` — approval control-plane, immutable projections, recursive PII guard и relationship indexes.

Сверены ORM-файлы `personnel_applications.py`, `personnel_intake.py`, `personnel_record_metadata.py`, `personnel_migration.py`, `person_photos.py`, `person_telegram.py`, `personnel_verification.py`, `personnel_orders.py`, `employee_identity.py`, `hr_import.py`, `hr_monthly_reference.py` и onboarding repositories. Расхождения ORM и каталога разрешались в пользу каталога применённой БД.

## 2. Значение решений

| Решение | Значение в этой матрице |
|---|---|
| `DELETE` | Строка принадлежит только доказанной тестовой цели и должна быть удалена явно в указанном порядке. Это проектное решение, не реализованная команда. |
| `BLOCK` | Наличие хотя бы одной строки запрещает физическое удаление всей цели. `CASCADE` не отменяет семантический блок. |
| `PRESERVE` | Строка остаётся; допустим только уже существующий `SET NULL` либо логическая ссылка без FK. Нельзя вручную стирать audit/provenance ради прохождения FK. |

Обозначения порядка:

- `R0` — в одной `SERIALIZABLE` execution-транзакции повторно загрузить и заблокировать exact request/target roots, проверить schema/policy/version/approval и полный fingerprint;
- `D1` — удалить intake payload (`personnel_intake_drafts`);
- `D2` — удалить весь набор intake links одной SQL-командой; при поштучном удалении сначала referencer, затем строку из `superseded_by_link_id`;
- `D3` — удалить target-owned PPR shell; этот шаг недоступен, пока журналы PPR остаются `BLOCK`;
- `D4` — удалить **все** заявки удаляемого Person, а не только выбранную заявку;
- `D5` — удалить `persons` последней;
- `P` — сохранить; `SET NULL` выполняется самой FK при удалении parent;
- `—` — порядка удаления нет: вся операция остановлена до DML.

## 3. Fingerprint повторной проверки

Ниже используются профили:

| Код | Что должно входить |
|---|---|
| `F-ROOT` | `policy_version`, environment, `person_id`, canonical SHA-256 полного `to_jsonb(persons)`; отдельно `person_status`, `source`, `updated_at`. |
| `F-APP` | выбранный `application_id` и SHA-256 полной строки; отсортированный список **всех** `application_id` Person и order-independent digest всех полных application rows. |
| `F-ROW` | количество найденных строк и SHA-256 отсортированного набора SHA-256 полных canonical `to_jsonb(row)`; raw/PII не сохраняются. |
| `F-JOIN` | то же, что `F-ROW`, для строк, найденных через Employee/User/order/onboarding join. |
| `F-PROV` | environment, target type/id, provenance id/version, artifact hash, timestamps/expiry и вычисленная по DB time активность; без raw identity. |
| `F-CONTROL` | request id/status/version, approval validity/expiry, target-set hash, manifest pairs/order, decisions/attestation и сохранённые relationship fingerprints. |
| `F-CATALOG` | требуемое расширение для execution: Alembic revision/policy version, ожидаемые tables/columns, `pg_get_constraintdef` значимых FK и определения защитных triggers. Сейчас aggregate fingerprint этого **не содержит**. |

Текущий foundation уже вычисляет `F-ROOT`, `F-APP`, `F-ROW/F-JOIN`, `F-PROV` и aggregate hash. В execution recheck должны участвовать и присутствующие, и отсутствующие правила: появление/исчезновение строки меняет snapshot. Однако отсутствует `F-CATALOG`, а некоторые транзитивные satellites не имеют отдельного rule; это отдельный finding ниже.

## 4. Корни, manifest и control-plane

| Таблица / связь | FK или логическая ссылка | Тип записи | Решение | Порядок | Основание | ON DELETE / CASCADE | Fingerprint |
|---|---|---|---|---|---|---|---|
| `persons` — target root | PK `person_id`; self-FK `fk_persons_merged_into(merged_into_person_id) → persons.person_id` | Каноническая идентичность | `DELETE` | `D5` | Только доказанный synthetic applicant, без Employee и любого `BLOCK`; Person — последний parent | inbound links в основном `RESTRICT`; self-FK `RESTRICT` | `F-ROOT` + inbound-rule absence + `F-CATALOG` |
| `persons.merged_into_person_id` — исходящая merge-ссылка target | `fk_persons_merged_into` | Target уже merged в другую identity | `BLOCK` | — | Текущая matrix проверяет только входящие ссылки, но не запрещает удалять сам `person_status='merged'`; merge chain — identity history | `RESTRICT` относится к target merge-parent, не защищает удаление дочерней merged row | `F-ROOT`; требуется отдельный eligibility code |
| `persons` — входящая merge-ссылка | `other.merged_into_person_id → target.person_id` | Другие identity, merged в target | `BLOCK` | — | Удаление target сломает merge chain | `RESTRICT`; rule `MERGED_PERSON_REFERENCE_PRESENT` | `F-ROW` |
| `personnel_applications` — selected `intake_pending` application | `person_id → persons.person_id` | Ранний эпизод претендента | `DELETE` | `D4` | Director resolution и personnel order должны отсутствовать | Person FK `RESTRICT`; child FK перечислены ниже | `F-APP`; `PERSONNEL_ORDER_PRESENT`, `DIRECTOR_RESOLUTION_PRESENT` |
| `SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED` — selected `intake_submitted` application | тот же FK | Submitted synthetic intake | `DELETE` | `D4` | Только при действующей approval версии с `submitted_synthetic_confirmed=true`; это не снимает остальные blockers | Person FK `RESTRICT` | `F-APP` + `F-CONTROL` attestation |
| `APPLICATION_STATUS_NOT_ELIGIBLE` — selected application | тот же FK | Эпизод с любым иным статусом | `BLOCK` | — | Операционный lifecycle вышел за пределы разрешённого early intake | Person FK `RESTRICT` | `F-APP` |
| `ALL_APPLICATIONS_PRESENT` — все заявки Person | тот же FK | Все эпизоды того же identity, включая selected | `BLOCK` | — | Текущий request target — одна пара `(person_id, application_id)`, но `D5` требует удалить все заявки. После redesign каждая явно frozen application должна получить собственное решение; неявное удаление запрещено | `RESTRICT` | `F-APP` сейчас видит все строки, но target-set hash не требует все application ids |
| `test_personnel_deletion_requests` | root control-plane; нет FK к Person/Application | Неизменяемый запрос | `PRESERVE` | `P` | Юридически/операционно нужен audit запроса | DELETE запрещён `trg_test_personnel_deletion_requests_guard` | `F-CONTROL` |
| `test_personnel_deletion_targets` | `request_id → requests`; `person_id/application_id` — намеренно без FK | Frozen manifest и snapshot | `PRESERVE` | `P` | Должен пережить удаление domain rows | request FK `RESTRICT`; UPDATE/DELETE запрещены target guard | `F-CONTROL` + stored relationship snapshot |
| `test_personnel_deletion_decisions` | `request_id → requests` | HR approve/reject | `PRESERVE` | `P` | Separation-of-duties evidence | `RESTRICT`; append-only trigger | `F-CONTROL` |
| `test_personnel_deletion_history` | `request_id → requests` | Командный audit/idempotent result projection | `PRESERVE` | `P` | Неизменяемая история; recursive PII-key guard из `a0…` | `RESTRICT`; append-only trigger | `F-CONTROL` |
| `PROVENANCE_STATE_RETAINED` — `test_personnel_provenance` | polymorphic logical `(target_type,target_id)`, FK нет | Доказательство тестового происхождения | `PRESERVE` | `P` | Должно пережить domain deletion | append-only trigger; cascade нет | `F-PROV` |

## 5. Applicant, intake и PPR

| Rule / таблица | FK или логическая связь | Тип записи | Решение | Порядок | Основание | ON DELETE / CASCADE | Fingerprint |
|---|---|---|---|---|---|---|---|
| `INTAKE_DRAFT_PRESENT` — `personnel_intake_drafts` | `application_id → personnel_applications`; `link_id → personnel_intake_links` | Изменяемый JSONB intake payload | `DELETE` | `D1` | Target-owned персональные данные, не самостоятельный audit | оба `RESTRICT` | `F-ROW`, включая payload digest/status/timestamps |
| `INTAKE_LINK_PRESENT` — `personnel_intake_links` | `application_id → applications`; self-FK `superseded_by_link_id → links` | Секрет/состояние intake-доступа | `DELETE` | `D2` | После draft ссылка не нужна; удаляется весь exact application set | оба `RESTRICT`; cascade нет | `F-ROW`, включая token/ciphertext digest, status/timestamps |
| `INTAKE_REVIEW_PRESENT` — `personnel_intake_section_reviews` | `application_id → applications` | HR review по разделам | `BLOCK` | — | Это уже кадровое решение, foundation запрещает approval | `RESTRICT` | `F-ROW` |
| `INTAKE_TRANSFER_PRESENT` — `personnel_intake_transfers` | `application_id → applications` | Факт переноса intake в PPR | `BLOCK` | — | Durable transfer boundary | `RESTRICT` | `F-ROW` |
| `INTAKE_RECONCILIATION_PRESENT` — `personnel_intake_reconciliation_decisions` | `application_id → applications`, `person_id → persons` | Решение identity reconciliation | `BLOCK` | — | Нельзя стирать решение сопоставления | оба `RESTRICT` | `F-ROW` по Person и всем applications |
| `APPLICATION_BLOCKER_PRESENT` — `personnel_application_blockers` | `application_id → applications` | Бизнес-блокер/его resolution | `BLOCK` | — | Наличие blocker семантически запрещает удаление, даже если FK умеет cascade | **`CASCADE`** от application | `F-ROW` |
| `APPLICATION_EARLY_LIFECYCLE_TOMBSTONE_REQUIRED` — `personnel_application_lifecycle_audit` | `application_id → applications` | `registered`, `intake_link_issued/opened/submitted`, `intake_edited_on_behalf` | `BLOCK` | — | Foundation допускает approval, но future execution=false и tombstone-модель отсутствует | `RESTRICT`; append-only trigger отсутствует, но таблица объявлена audit log | `F-ROW`, early action allowlist |
| `APPLICATION_OFFICIAL_LIFECYCLE_PRESENT` — та же таблица | тот же FK | Любое не-early lifecycle действие | `BLOCK` | — | Официальная кадровая история | `RESTRICT` | `F-ROW` |
| `APPLICATION_RESOLUTION_AUDIT_PRESENT` — `personnel_application_resolution_audit` | `application_id → applications` | Director-resolution audit | `BLOCK` | — | Независимое решение руководителя | `RESTRICT` | `F-ROW` |
| `PERSONNEL_ORDER_PRESENT` — `personnel_applications.personnel_order_id` | application → `personnel_orders` | Связь заявки с приказом | `BLOCK` | — | Претендент перешёл в официальный кадровый процесс | `RESTRICT` | входит в `F-APP` |
| `DIRECTOR_RESOLUTION_PRESENT` — поля application | FK actor → users, resolution status/note/timestamp | Резолюция директора | `BLOCK` | — | Даже без audit row является официальным решением | application root | входит в `F-APP` |
| `PPR_METADATA_PRESENT` — `personnel_record_metadata` | PK/FK `person_id → persons` | PPR shell/state | `DELETE` | `D3` | Для удаляемого synthetic applicant shell не имеет самостоятельной ценности; удалять только после решения журналов | `RESTRICT` | `F-ROW` |
| `PPR_EVENT_TOMBSTONE_REQUIRED` — `personnel_record_events` | `person_id → persons`; employee/migration refs mostly `SET NULL` | Append-oriented domain event journal | `BLOCK` | — | Foundation прямо требует отдельный tombstone/hash; у demo targets обычно есть `PPR_CREATED` | Person FK `RESTRICT`; cascade нет | `F-ROW`, полный event payload hashed |
| `PPR_COMMAND_TOMBSTONE_REQUIRED` — `ppr_command_executions` | `person_id → persons` | Idempotency/command result journal | `BLOCK` | — | Foundation future_execution=false; удаление или tombstone не согласованы | default `NO ACTION`; cascade нет | `F-ROW`, включая request/result payload digest |
| `PPR_EDUCATION_PRESENT` — `person_education` | `person_id → persons`; employee/import refs `SET NULL` | Постоянный профиль образования | `BLOCK` | — | Перенесённые/подтверждённые профильные данные | Person `RESTRICT` | `F-ROW` |
| `PPR_TRAINING_PRESENT` — `person_training` | аналогично | Постоянное повышение квалификации | `BLOCK` | — | Постоянный PPR SoT | Person `RESTRICT` | `F-ROW` |
| `PPR_RELATIVE_PRESENT` — `person_relatives` | `person_id → persons` | Семья/родственники | `BLOCK` | — | Чувствительный постоянный PPR-раздел | `RESTRICT` | `F-ROW` |
| `PPR_EXTERNAL_EMPLOYMENT_PRESENT` — `person_external_employment` | `person_id → persons`; self-FK supersedes; `employee_context_id` логический, без FK | Внешний трудовой стаж | `BLOCK` | — | Постоянный PPR-раздел и supersession chain | Person/self `RESTRICT`; same-person trigger | `F-ROW` |
| `PPR_MILITARY_PRESENT` — `person_military_service` | `person_id → persons`; `employee_context_id` логический, без FK | Воинский учёт | `BLOCK` | — | Чувствительный постоянный PPR-раздел | Person `RESTRICT` | `F-ROW` |
| `PHOTO_PRESENT` — `person_photos` | `person_id → persons` | Canonical/archived фото | `BLOCK` | — | Файл, hash и current-photo invariant; mutation нельзя обходить | `RESTRICT`; DELETE/UPDATE guard trigger | `F-ROW` |
| `PHOTO_PROVENANCE_PRESENT` — `person_photo_sources` | composite `(person_photo_id,person_id) → person_photos`; `source_application_id` логический без FK | Immutable provenance фото | `BLOCK` | — | Должна переживать source application, но не может пережить удаление photo/Person без redesign | `RESTRICT`; append-only trigger | `F-ROW` по Person или всем application ids |
| `TELEGRAM_BINDING_PRESENT` — `person_telegram_bindings` | `person_id → persons` | Telegram identity binding | `BLOCK` | — | Внешняя идентичность/уникальные значения | `RESTRICT` | `F-ROW` |
| `TELEGRAM_ACTIVATION_PRESENT` — `person_telegram_bot_activations` | `person_id → persons` | Bot activation | `BLOCK` | — | Внешнее действие пользователя | `RESTRICT` | `F-ROW` |
| `VERIFICATION_TASK_PRESENT` — `verification_tasks` | `person_id → persons` | Задание проверки биографии | `BLOCK` | — | Контрольная процедура | `RESTRICT`; reference-enforcement trigger | `F-ROW` |
| `VERIFICATION_ATTESTATION_PRESENT` — `verification_attestations` | `person_id → persons`, `task_id → verification_tasks` | Неизменяемая аттестация | `BLOCK` | — | Нормативное подтверждение | `RESTRICT`; immutable trigger | `F-ROW` |
| `IDENTITY_RECONCILIATION_PRESENT` — `identity_reconciliation_items` | `person_id → persons`; `employee_id → employees SET NULL` | Результат сопоставления identity | `BLOCK` | — | Identity history | Person `RESTRICT` | `F-ROW` |
| `HR_CHANGE_EVENT_PRESENT` — `hr_personnel_change_events` | `person_id → persons` | Кадровое lifecycle-событие | `BLOCK` | — | Официальная кадровая история | **`SET NULL`**, но policy строже FK | `F-ROW` |
| `ASSIGNMENT_PRESENT` — `person_assignments` | `person_id → persons` | Каноническое назначение | `BLOCK` | — | Person уже включён в штатный контур | `RESTRICT` | `F-ROW` |
| `ENROLLMENT_QUEUE_PRESENT` — `enrollment_queue` | `person_id → persons`; assignment `RESTRICT`; ряд refs `SET NULL` | Очередь зачисления | `BLOCK` | — | Незавершённый/завершённый enrollment workflow | Person `RESTRICT` | `F-ROW` |
| `ENROLLMENT_HISTORY_RETAINED` — `enrollment_history` | `person_id`, `employee_id`, `assignment_id`, `link_id` — `SET NULL` | История зачисления | `PRESERVE` | `P` | Audit должен сохраниться и схема допускает anonymized detach | Person/Employee `SET NULL`; queue `RESTRICT` | `F-ROW` |
| `HR_REVIEW_OVERRIDE_RETAINED` — `hr_review_overrides` | `person_id → persons SET NULL` | Сохранённое HR override | `PRESERVE` | `P` | История решения сохраняется; target identity отсоединяется FK | `SET NULL`; history child `RESTRICT` | `F-ROW` |
| `HR_REVIEW_OVERRIDE_HISTORY_RETAINED` — `hr_review_override_history` | `override_id → hr_review_overrides` | Append-only override history | `PRESERVE` | `P` | Неизменяемый audit | `RESTRICT`; append-only trigger | `F-JOIN` через override.person_id до detach |
| `SECURITY_AUDIT_RETAINED` — `security_audit_log.target_person_id` | target Person FK | Security audit | `PRESERVE` | `P` | Security evidence сохраняется | `SET NULL` | `F-ROW` |

## 6. Legacy personnel/contact projections

| Rule / таблица | FK или логическая связь | Тип записи | Решение | Порядок | Основание | ON DELETE / CASCADE | Fingerprint |
|---|---|---|---|---|---|---|---|
| `LEGACY_PERSONNEL_PRESENT` — `personnel` | `person_id` совпадает с Person только логически; FK к `persons` нет | Legacy назначение/контакт, включая закрытое | `BLOCK` | — | Любая строка — кадровая история; `date_to IS NULL` дополнительно действующее назначение | к Person cascade нет | `F-ROW` |
| `CONTACT_PRESENT` — `contacts` | `person_id` логический, FK к `persons/personnel` нет | Отдельная contact projection | `BLOCK` | — | Может использоваться независимо от Person | cascade нет | `F-ROW` |
| `CONTACT_ACCESS_PRESENT` — `contact_access` | `person_id → personnel.person_id` | ACL контакта | `BLOCK` | — | Подтверждает использование legacy identity; не разрешать cascade как cleanup | **`CASCADE`** от `personnel` | `F-ROW` |
| `KEY_CONTACT_PRESENT` — `key_contacts` | `person_id` логический, FK нет | Ключевой контакт | `BLOCK` | — | Организационная публичная проекция | cascade нет | `F-ROW` |
| `ORG_UNIT_KEY_STAFF_PRESENT` — `org_unit_key_staff` | `person_id → personnel.person_id` | Ключевой сотрудник подразделения | `BLOCK` | — | Организационное назначение | **`CASCADE`** от `personnel` | `F-ROW` |

## 7. Employee и связанные контуры

Любая строка `employees` сейчас немедленно блокирует applicant deletion. Поэтому строки ниже не удаляются каскадом и порядок удаления Employee не проектируется.

| Rule / таблица | FK/путь к цели | Тип записи | Решение | Порядок | Основание | ON DELETE / CASCADE | Fingerprint |
|---|---|---|---|---|---|---|---|
| `EMPLOYEE_PRESENT` — `employees` | `person_id → persons` | Действующий/бывший/draft Employee | `BLOCK` | — | WP-TD scope ограничен applicant; employee hard-delete отдельно отключён HTTP 410 | `RESTRICT` | `F-ROW` |
| `USER_IDENTITY_PRESENT` — `users` | `users.employee_id → employees` | Учётная запись | `BLOCK` | — | Нельзя удалять employee/person с login/RBAC/activity history | default `NO ACTION` | `F-JOIN` |
| `EMPLOYEE_ASSIGNMENT_LINK_PRESENT` — `employee_assignment_links` | `employee_id → employees`, `assignment_id → person_assignments` | Operational assignment link | `BLOCK` | — | Штатная история | оба `RESTRICT` | `F-JOIN` |
| `EMPLOYEE_DOCUMENT_PRESENT` — `employee_documents` | `employee_id → employees` | Кадровый/профессиональный документ | `BLOCK` | — | Официальный документ | default `NO ACTION`; cascade нет | `F-JOIN` |
| `EMPLOYEE_EVENT_PRESENT` — `employee_events` | `employee_id → employees`; order/item `RESTRICT` | Кадровое событие | `BLOCK` | — | Append-oriented кадровая история | Employee default `NO ACTION` | `F-JOIN` |
| `EMPLOYEE_IDENTITY_PRESENT` — `employee_identities` | `employee_id → employees` | Документная identity | `BLOCK` | — | Чувствительная идентичность; `CASCADE` не является разрешением | **`CASCADE`** | `F-JOIN` |
| `EMPLOYEE_PROFILE_OVERRIDE_PRESENT` — `employee_import_profile_overrides` | `employee_id → employees` | Ручная поправка импортного профиля | `BLOCK` | — | Утверждённое HR-изменение | **`CASCADE`** | `F-JOIN` |
| `TERMINATION_RECORD_PRESENT` — `employee_termination_records` | `employee_id → employees`; event/batch/row refs | Запись увольнения | `BLOCK` | — | Официальная кадровая запись | `RESTRICT` | `F-JOIN` |
| `TERMINATION_AUDIT_RETAINED` — `employee_termination_record_audit` | record → Employee | Audit увольнения | `PRESERVE` | `P` | Audit не удаляется; сейчас termination record и Employee всё равно блокируют root | audit → record `RESTRICT` | `F-JOIN` |
| `ONBOARDING_PRESENT` — `employee_onboardings` | `application_id → applications`, `employee_id/mentor_employee_id → employees` | Агрегат адаптации | `BLOCK` | — | Отдельный бизнес-процесс | все три `RESTRICT` | `F-ROW/F-JOIN` |
| `ONBOARDING_ITEM_PRESENT` — `employee_onboarding_checklist_items` | `onboarding_id → onboardings`; assignee Employee/User | Checklist item | `BLOCK` | — | Выполнение/ответственность | onboarding **`CASCADE`**, assignees `RESTRICT` | `F-JOIN` |
| `ONBOARDING_ATTACHMENT_PRESENT` — `employee_onboarding_checklist_attachments` | item → onboarding | Вложение checklist | `BLOCK` | — | Документ процесса | item **`CASCADE`** | `F-JOIN` |
| `ONBOARDING_NOTIFICATION_PRESENT` — `employee_onboarding_notifications` | onboarding/item | Уведомление | `BLOCK` | — | История процесса | onboarding `CASCADE`, item `SET NULL` | `F-JOIN` |
| `ONBOARDING_TASK_AUDIT_PRESENT` — `employee_onboarding_task_audit` | onboarding/item | Audit task | `BLOCK` | — | История исполнения | оба `CASCADE`, policy строже | `F-JOIN` |
| `PERSONNEL_MIGRATION_RUN_PRESENT` — `personnel_migration_runs` | `person_id → persons`; employee context `SET NULL` | Migration run | `BLOCK` | — | Run объединяет provenance/items/events | Person `RESTRICT`; items `CASCADE` от run | `F-JOIN` |
| `OPERATIONAL_ORDER_SIGNING_PRESENT` — `operational_order_signing_attestations` | `actor_employee_id → employees` | Официальная подпись production order | `BLOCK` | — | Нельзя анонимизировать участника через test cleanup | `SET NULL`, но policy строже FK | `F-JOIN` |
| `USER_LINKAGE_REVIEW_DECISION_PRESENT` — `user_linkage_review_decisions` | proposed Employee `SET NULL` или linked User | Решение привязки | `BLOCK` | — | Identity governance audit | Employee `SET NULL`, users `RESTRICT` | `F-JOIN` |
| `USER_LINKAGE_EXECUTE_ITEM_PRESENT` — `user_linkage_execute_items` | proposed Employee/User/source decision | Выполнение/rollback identity linkage | `BLOCK` | — | Операционный audit/rollback | Employee `SET NULL`; user/source decision `RESTRICT` | `F-JOIN` |
| `ACCESS_GRANT_RETAINED` — `access_grants` | polymorphic `target_type/id` без FK к Person/Employee/User | RBAC grant | `BLOCK` | — | Для `target_type='PERSON'` preserve создаёт dangling security target, а DELETE теряет security history; Employee/User targets уже блокируются их roots | cascade нет | `F-JOIN`; требуется action-specific classification |
| `PERSONNEL_VISIBILITY_RETAINED` — `personnel_visibility_assignments` | target User → Employee → Person | Scope visibility | `PRESERVE` | `P` | Не удаляется отдельно от учётной записи; User одновременно блокирует root | target user `CASCADE` | `F-JOIN` |

## 8. Импорт, baseline и retained projections

Эти связи возникают через Employee, который уже `BLOCK`. Они перечислены явно, чтобы future widening scope не превратил `SET NULL` в неявное разрешение удалить Employee.

| Rule / таблица | FK/путь | Тип записи | Решение | Порядок | Основание | ON DELETE / CASCADE | Fingerprint |
|---|---|---|---|---|---|---|---|
| `HR_IMPORT_ROW_RETAINED` — `hr_import_rows` | `employee_id → employees` | Raw import row | `PRESERVE` | `P` | Batch может содержать других людей | `SET NULL` | `F-JOIN` |
| `HR_IMPORT_NORMALIZED_RETAINED` — `hr_import_normalized_records` | `employee_id → employees` | Нормализованная строка | `PRESERVE` | `P` | Shared import provenance | `SET NULL` | `F-JOIN` |
| `HR_IMPORT_DOCUMENT_CANDIDATE_RETAINED` — `hr_import_document_candidates` | `employee_id → employees` | Кандидат документа | `PRESERVE` | `P` | Часть shared batch; созданный document отдельно блокирует | `SET NULL` | `F-JOIN` |
| `HR_BASELINE_ENTRY_RETAINED` — `hr_baseline_entries` | `employee_id → employees` | Canonical baseline entry | `PRESERVE` | `P` | Историческая публикация/baseline | `SET NULL`; entry может каскадно зависеть от baseline, но не Employee | `F-JOIN` |
| `HR_CHANGE_EVENT_RETAINED` — `hr_change_events` | `employee_id → employees` | Diff/change event | `PRESERVE` | `P` | История импорта | `SET NULL` | `F-JOIN` |
| `HR_MONTHLY_REFERENCE_ENTRY_RETAINED` — `hr_monthly_reference_entries` | `employee_id → employees` | Закрытая/открытая monthly reference entry | `PRESERVE` | `P` | Нормативный reference; closed MRD защищён trigger | `SET NULL`; mutation guard для closed MRD | `F-JOIN` |
| `LEGACY_IMPORT_STAGE_RETAINED` — `employees_import_stage` | `employee_id` логический, FK нет | Legacy staging row | `PRESERVE` | `P` | Shared/import evidence; future Employee deletion потребует отдельной detach policy, иначе ссылка станет dangling | cascade нет | `F-JOIN` |

## 9. Personnel orders

Любое участие Employee или application в приказе — `BLOCK`. Дочерние rows не являются кандидатами cascade cleanup.

| Rule / таблица | FK/путь | Тип записи | Решение | Порядок | Основание | ON DELETE / CASCADE | Fingerprint |
|---|---|---|---|---|---|---|---|
| `PERSONNEL_ORDER_ITEM_PRESENT` — `personnel_order_items` | `employee_id → employees`, `order_id → personnel_orders` | Пункт кадрового приказа | `BLOCK` | — | Официальный документ | оба `RESTRICT` | `F-JOIN` |
| `PERSONNEL_ORDER_SIGNATORY_PRESENT` — `personnel_orders.signed_by_employee_id` | Employee FK | Подписант приказа | `BLOCK` | — | Факт подписи/участия | `SET NULL`, policy строже | `F-JOIN` |
| `PERSONNEL_ORDER_AUDIT_RETAINED` — `personnel_order_lifecycle_audit` | `order_id → personnel_orders` | Lifecycle audit | `PRESERVE` | `P` | Нормативный audit; order остаётся из-за blocker | `RESTRICT` | `F-JOIN` |
| `PERSONNEL_ORDER_ATTACHMENT_PRESENT` — `personnel_order_attachments` | order FK | Вложение | `BLOCK` | — | Часть официального приказа | `RESTRICT` | `F-JOIN` |
| `PERSONNEL_ORDER_EDITORIAL_BLOCK_PRESENT` — `personnel_order_editorial_blocks` | order FK | Редакционный текст | `BLOCK` | — | Часть документа | `RESTRICT` | `F-JOIN` |
| `PERSONNEL_ORDER_EVIDENCE_SCOPE_PRESENT` — `personnel_order_evidence_scopes` | order FK | Evidence scope | `BLOCK` | — | Обоснование документа | `RESTRICT` | `F-JOIN` |
| `PERSONNEL_ORDER_ITEM_BASIS_PRESENT` — `personnel_order_item_bases` | `order_item_id → items`; subject Employee `SET NULL` | Основание пункта | `BLOCK` | — | Документальное основание | item `RESTRICT` | `F-JOIN` |
| `PERSONNEL_ORDER_LOCALIZED_TEXT_PRESENT` — `personnel_order_localized_texts` | order FK | Локализованный текст | `BLOCK` | — | Официальная версия | `RESTRICT` | `F-JOIN` |
| `PERSONNEL_ORDER_PRINT_PRESENT` — `personnel_order_prints` | order FK | Зафиксированный print/PDF metadata | `BLOCK` | — | Неизменяемый артефакт выдачи | `RESTRICT` | `F-JOIN` |

## 10. Incoming information

`_INCOMING_DOCUMENT_IDS_SQL` считает участием прямого Person, target Employee и связанного User в ролях sender/addressee/controller/creator/updater/closer/canceller/transfer actor/external recipient. Любое такое участие блокирует цель.

| Rule / таблица | FK/путь | Тип записи | Решение | Порядок | Основание | ON DELETE / CASCADE | Fingerprint |
|---|---|---|---|---|---|---|---|
| `INCOMING_DOCUMENT_PRESENT` / `INCOMING_DOCUMENT_PARTICIPATION_PRESENT` — `incoming_documents` | sender Person/Employee, addressee Employee/User и user-role FKs | Входящий документ | `BLOCK` | — | Официальный документооборот | Person/Employee значимые FK `RESTRICT`; часть actor FK `SET NULL` | `F-ROW/F-JOIN` |
| `INCOMING_DOCUMENT_ASSIGNMENT_PRESENT` — `incoming_document_assignments` | document; assignee Employee/User | Назначение | `BLOCK` | — | Ответственность/исполнение | document `RESTRICT`, assignees `RESTRICT` | `F-JOIN` |
| `INCOMING_DOCUMENT_ATTACHMENT_PRESENT` — `incoming_document_attachments` | document FK | Вложение | `BLOCK` | — | Часть документа | `RESTRICT` | `F-JOIN` |
| `INCOMING_DOCUMENT_AUDIT_RETAINED` — `incoming_document_audit` | document FK | Audit документа | `BLOCK` | — | Audit надо сохранять, а parent удалить нельзя | `RESTRICT` | `F-JOIN` |
| `INCOMING_DOCUMENT_DEADLINE_CHANGE_PRESENT` — `incoming_document_deadline_changes` | document FK | История сроков | `BLOCK` | — | Официальная история | `RESTRICT` | `F-JOIN` |
| `INCOMING_DOCUMENT_OPERATIONAL_ORDER_LINK_PRESENT` — `incoming_document_operational_order_links` | document/order | Связь с production order | `BLOCK` | — | Междоменная evidence link | `RESTRICT` | `F-JOIN` |
| `INCOMING_DOCUMENT_PERSONNEL_ORDER_LINK_PRESENT` — `incoming_document_personnel_order_links` | document/personnel order | Связь с кадровым приказом | `BLOCK` | — | Междоменная evidence link | `RESTRICT` | `F-JOIN` |
| `INCOMING_DOCUMENT_TRANSFER_PRESENT` — `incoming_document_transfers` | document/user | Передача документа | `BLOCK` | — | История маршрутизации | `RESTRICT` | `F-JOIN` |

## 11. Транзитивные satellites, не имеющие отдельного правила из 88

Они не позволяют обойти blocker родителя, но показывают границу полноты текущего fingerprint.

| Таблицы / путь | Решение | Причина и FK | Fingerprint status |
|---|---|---|---|
| `personnel_order_item_editorial_blocks` → `personnel_order_items` | `BLOCK` | Item уже `BLOCK`; child FK `RESTRICT` | Отдельного rule нет; изменение child не меняет `PERSONNEL_ORDER_ITEM_PRESENT` row digest |
| `employee_onboarding_notification_recipients`, `employee_onboarding_notification_deliveries` → notification | `BLOCK` | Notification/onboarding уже `BLOCK`; child FK `CASCADE` | Отдельных rules нет |
| `personnel_migration_items` → migration run | `BLOCK` | Run уже `BLOCK`; items `CASCADE` от run | Отдельного rule нет |
| Связи target Employee как `mentor_employee_id`, checklist `assignee_employee_id`, verification `verifier_employee_id`, identity-reconciliation `employee_id`, PPR `employee_context_id` | `BLOCK` | Сам `employees` уже `BLOCK`; FK варьируются `RESTRICT`/`SET NULL`, два PPR context поля логические | Не все роли имеют отдельные joins; root Employee blocker должен повторно проверяться первым |
| User satellites: `tasks`, `task_reports`, `task_events`, `task_audit_log`, `audit_log`, `notifications`, `tg_bindings`, `user_org_units`, `user_supervisors`, org managers/groups, access/control-list/import/order actor refs | `BLOCK` через `USER_IDENTITY_PRESENT` | Удаление User не входит в scope; downstream FK варьируются `RESTRICT`, `SET NULL`, `CASCADE`, `NO ACTION` | Не хэшируются отдельно; безопасно только пока наличие самого User безусловно блокирует execution |
| `security_audit_log.target_employee_id` | `PRESERVE` | Security history использует `SET NULL`; Employee всё равно блокирует root | Текущий `SECURITY_AUDIT_RETAINED` не хэширует эту роль отдельно |
| polymorphic `access_grants` Employee/User targets | `BLOCK` | Logical target без FK; действует консервативное решение из строки `ACCESS_GRANT_RETAINED` | Нужна раздельная классификация по `target_type` |

Вывод: для текущего applicant-only scope отсутствие отдельных satellite rules не открывает путь удаления, потому что соответствующий parent (`Employee`, `User`, order, onboarding, migration run) уже `BLOCK`. Если scope когда-либо расширится до Employee, матрицу нельзя переиспользовать без полного транзитивного пересмотра.

## 12. Допустимый порядок — только после закрытия blockers

Текущая схема **не имеет исполнимого порядка** для типичного early applicant с `PPR_CREATED` и `MaterializePPR`: `personnel_record_events`, `ppr_command_executions` и часто early lifecycle audit удерживают `RESTRICT/NO ACTION` и классифицированы `BLOCK` до отдельного решения.

После реализации всех утверждённых решений отдельными work packages и расширения manifest до всех applications Person минимальная последовательность должна быть такой:

1. `R0`: одна новая `SERIALIZABLE` транзакция; advisory/request lock не заменяет row/catalog recheck. Проверить current DB/environment, `b1c2d3e4f5a6` или явно совместимую revision, policy version, permission, separation of duties, `APPROVED`, expiry, request version, target-set hash и `F-CATALOG`.
2. Повторно вычислить полный batch fingerprint для exact Person set. Проверить, что множество target applications равно множеству всех applications каждого удаляемого Person. Любой drift → `REAPPROVAL_REQUIRED`, без DML.
3. Проверить отсутствие каждого `BLOCK`, включая логические tables без FK и новые catalog relations. Не полагаться на ошибку FK как на policy guard.
4. `D1`: удалить exact drafts по frozen application ids и проверить ожидаемое количество/hash.
5. `D2`: удалить exact links по тем же ids одной командой с `RETURNING`/count verification; это разрешает self-FK внутри удаляемого множества.
6. Выполнить отдельно утверждённое действие для PPR/application journals. Пока такого действия нет, остановиться до `D3`.
7. `D3`: удалить `personnel_record_metadata` exact person ids.
8. `D4`: удалить все и только frozen application ids; row count обязан совпасть.
9. `D5`: удалить все и только frozen person ids; row count обязан совпасть.
10. До commit повторно проверить, что target roots исчезли, preserved audit/provenance существуют, `SET NULL` сработал только на ожидаемых rows, dangling logical references не возникли. Записать PII-free execution result в append-only control-plane.

Все шаги должны быть атомарны. Частичный commit между `D1`…`D5` недопустим.

## 13. Утверждённые безопасные решения

Следующие 17 решений утверждены как обязательные границы applicant-only implementation planning. Они не означают, что execution уже реализован или разрешён на текущей схеме.

| № | Утверждённое решение | Обязательные последствия |
|---:|---|---|
| 1 | Execution manifest имеет корень `PERSON` и содержит полный неизменяемый список всех application IDs этого Person. Target-set hash включает весь список. | Старые запросы с manifest пары `(person_id, application_id)` исполнению не подлежат; требуется новая версия manifest и новое согласование. |
| 2 | Для `personnel_record_events` обязателен PII-free append-only tombstone: event IDs, типы, timestamps и digest; исходные rows можно удалять только после атомарной записи tombstone. | Требуются отдельная схема и проверка целостности; до их появления строки остаются `BLOCK`. |
| 3 | Для `ppr_command_executions` обязателен detached PII-free tombstone с command ID/type/status и digest request/result payload. | Требуется retention contract; raw payload не переносится, старый idempotent replay для удалённой цели может стать недоступен. |
| 4 | Для разрешённого early `personnel_application_lifecycle_audit` обязателен PII-free lifecycle tombstone с application ID, action, timestamp, actor technical ID и metadata digest. | Исходный `RESTRICT` audit можно удалить только после подтверждённой атомарной записи tombstone. |
| 5 | Applicant-only execution допускает только `person_status='active'` и `merged_into_person_id IS NULL`; любая входящая или исходящая merge-связь — `BLOCK`. | Inactive/merged identities не входят в первый MVP. |
| 6 | Execution fingerprint обязательно включает `F-CATALOG`: policy version, совместимую Alembic revision, ожидаемые tables/columns, определения значимых FK и защитных triggers. | Любой неизвестный schema drift блокирует DML и требует обновления compatibility allowlist/reapproval. |
| 7 | Любой polymorphic `access_grants` target для Person/Employee/User — `BLOCK` в первом MVP. | Никакие grants не удаляются и не остаются dangling; цель сначала должна пройти отдельный штатный процесс RBAC. |
| 8 | `enrollment_history`, `hr_review_overrides`, `hr_review_override_history` и `security_audit_log` сохраняются после `SET NULL` только при наличии до detach достаточных technical IDs и digest. Иначе связь — `BLOCK`. | Preserved audit обязан оставаться проверяемым без join к удалённому Person. |
| 9 | Вводится versioned server-owned registry логических связей; `personnel`, `contacts`, `key_contacts`, `employees_import_stage` и polymorphic targets проверяются вместе с FK-каталогом. | Любая найденная legacy logical row блокирует первый MVP; одного `pg_constraint` недостаточно. |
| 10 | `intake_submitted` допускается только при active provenance, действующей HR-attestation `submitted_synthetic_confirmed=true` и закрытых tombstone gates. | HR-attestation сама по себе не снимает lifecycle/PPR blockers. |
| 11 | Photos, attachments и любые внешние blobs остаются `BLOCK` в первом MVP. | Storage transaction/outbox/compensation не входят в applicant-only MVP; SQL delete blob metadata запрещён. |
| 12 | Execution требует active append-only provenance с artifact hash. `LEGACY_MANIFEST` разрешён только для анализа/approval, но не для исполнения. | Legacy fixtures без безопасного provenance backfill остаются неудаляемыми. |
| 13 | Execution выполняется в новой `SERIALIZABLE` транзакции с root row locks и доказанным concurrency contract. При недостаточности SSI обязателен единый per-Person advisory-lock protocol для всех writers. | До PostgreSQL concurrency tests и закрытия race с созданием child rows execution запрещён. |
| 14 | Append-only history получает отдельное действие `EXECUTE` и PII-free result projection: IDs, counts, before/after hashes, policy/catalog versions и result code. | Execution должен быть полностью аудируемым и идемпотентным; schema support пока отсутствует. |
| 15 | Для item editorial blocks, onboarding notification recipients/deliveries, migration items и остальных транзитивных satellites добавляются отдельные server-owned relationship rules. | Fingerprint должен охватывать satellites независимо от parent blocker; расширение scope без этих rules запрещено. |
| 16 | `EMPLOYEE_PRESENT` остаётся безусловным `BLOCK`; отдельно учитываются роли mentor/assignee/verifier/employee context. | Первый MVP остаётся applicant-only. Удаление Employee проектируется отдельным будущим процессом и не переиспользует эту матрицу без расширения. |
| 17 | Execution использует только explicit DELETE по frozen IDs с `RETURNING` и expected count/hash. `ON DELETE CASCADE` не считается разрешённой операцией cleanup. | Любой неожиданный cascade или несовпадение количества приводит к rollback всей транзакции. |

## 14. Итоговое решение этапа

Матрица и все 17 безопасных решений утверждены, поэтому следующий этап готов к **applicant-only implementation planning**. Это утверждение границ и gates, а не разрешение выполнять удаление.

Текущая схема `b1c2d3e4f5a6` **ещё не готова к execution**: новый PERSON-root manifest, tombstone structures, `F-CATALOG`, дополнительные relationship rules, execution audit и concurrency guarantees отсутствуют. Они должны быть спроектированы и проверены отдельными work packages до появления исполняющей команды, endpoint или UI.
