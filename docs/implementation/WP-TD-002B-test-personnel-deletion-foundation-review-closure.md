# WP-TD-002B — Foundation Review Closure

| Поле | Значение |
|---|---|
| Статус | **Ready for Review** |
| Дата | 2026-09-04 |
| Миграция | `z9a0b1c2d3e4` после applied foundation `y8z9a0b1c2d3` |
| Физическое удаление | **Отсутствует** |

## Результат

WP-TD-002B закрывает повторный review foundation без добавления execution endpoint, UI или
SQL удаления Person/Application/Employee. Legacy Employee hard-delete web routes остаются
безусловным HTTP 410 до вызова delete service.

## Alembic и test database

Явный `Alembic Config.sqlalchemy.url` является авторитетным. Только при его отсутствии
`alembic/env.py` загружает `.env` с `override=false` и использует штатный `DATABASE_URL`.

Migration harness до миграционного DDL проверяет:

* PostgreSQL URL и suffix `_test`/`-test`;
* URL host `127.0.0.1`, `localhost` или `::1`;
* отличие target от основной БД и template test database;
* фактический `current_database()` после подключения к target и до Alembic DDL.

Любое несовпадение завершает тест до миграции. Process `DATABASE_URL` не заменяет explicit
Alembic URL.

## Server-owned relationship/policy matrix

Каждое правило содержит safe code, table/policy source, lookup, ключи, state digest,
категорию, допустимость create/submit/approve/future execution и при необходимости обязательное
решение HR. Identifiers и predicates не поступают от клиента.

| Класс | Категория | Create / submit / approve / future execute |
|---|---|---|
| legacy `personnel`, `contacts`, `contact_access`, `key_contacts`, `org_unit_key_staff`, Employee, assignments/users/identities | `BLOCK` | нет / нет / нет / нет |
| профильные PPR sections, Telegram, verification/reconciliation | `BLOCK` | нет / нет / нет / нет |
| `personnel_record_events`, `ppr_command_executions` | `TOMBSTONE_REQUIRED` | да / да / да / нет |
| ранний application lifecycle allowlist | `TOMBSTONE_REQUIRED` | да / да / да / нет |
| официальный lifecycle/resolution | `BLOCK` | нет / нет / нет / нет |
| `intake_submitted` policy | `HR_ATTESTATION_REQUIRED` | да / да / только с attestation / повторный recheck |
| `personnel_record_metadata`, applications, intake links/drafts | `INFORMATIONAL` | да / да / да / повторный recheck |
| retained enrollment/security/import audit | `INFORMATIONAL` | да / да / да / повторный recheck |
| `personnel_migration_runs` | `BLOCK` | нет / нет / нет / нет |
| HR baseline/monthly/import candidates/`hr_change_events` | `INFORMATIONAL` | да / да / да / повторный recheck |
| incoming document и все assignments/attachments/audit/deadlines/transfers/order links | `BLOCK` | нет / нет / нет / нет |
| personnel order attachments/editorial/evidence/item bases/localized/prints | `BLOCK` | нет / нет / нет / нет |
| onboarding notifications/task audit | `BLOCK` | нет / нет / нет / нет |
| user-linkage review/execute items | `BLOCK` | нет / нет / нет / нет |

`SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED` является обычным формальным policy-rule над
`personnel_applications.status`, имеет digest и
`required_hr_decision=submitted_synthetic_confirmed=true`; ad hoc классификации нет.

## Fingerprint и provenance

Полное состояние каждой найденной строки сначала преобразуется в canonical SHA-256 row
hash. Row hashes сортируются до итогового digest, поэтому план и порядок выдачи PostgreSQL не
создают ложный drift. Значимый UPDATE при прежнем количестве строк меняет digest.

Сохраняются только count, category, safe code и digest — raw row, intake payload, ИИН,
телефон и email не сохраняются. Provenance snapshot включает только безопасные technical ID,
target/environment, version, artifact hash, timestamps и вычисленную по
`transaction_timestamp()` validity. Исчезновение, появление, изменение identity или
истечение provenance меняет aggregate fingerprint. Для basis `PROVENANCE` submit и approve
переводят request в `REAPPROVAL_REQUIRED`, если validity изменилась.

## Idempotency и аудит

Область idempotency: actor + action + key; canonical command hash также включает request ID и
payload. History хранит immutable, PII-free `result_projection`. Успешный replay возвращает
эту первоначальную projection даже после последующего изменения request. Другой payload или
request с тем же ключом возвращает `TD_IDEMPOTENCY_PAYLOAD_CONFLICT`.

Result projection содержит только request technical identity/status/version/hashes и
безопасные target IDs/category codes. Append-only trigger запрещает UPDATE/DELETE projection.

## Privacy

Отдельного canonical permission полного ИИН в проекте не найдено. Поэтому WP-TD-002B всегда
возвращает маскированный ИИН независимо от широкого ADMIN/HR organizational scope. Добавление
полного значения возможно только будущим отдельным permission и отдельным review.

## Downgrade RBAC

Ownership определяется точным tuple permission access role, canonical target role,
`target_type=ROLE`, reason marker, active flag и ожидаемым количеством строк. Внешний,
дополнительный или поддельный grant вызывает fail-closed downgrade. Удаление выполняется по
точному join с expected tuples; глобального `DELETE WHERE reason IN (...)` нет. Триггеры
удаляются до таблиц, функции — после таблиц.

## Сценарий локальных 11 записей

Самодостаточный PostgreSQL-сценарий создаёт ровно 3 Debug + 8 Demo, пять pending и
шесть submitted. Все 11 получают PPR technical journals и поэтому
`TOMBSTONE_REQUIRED`, не постоянный `BLOCK`. Десять записей допускают
`draft → submit → approve`; все шесть submitted требуют HR-attestation. Одна запись с legacy
personnel/contact остаётся `BLOCK`. Технические ID и суффиксы не hardcoded.

## Закрытие findings повторного review

| Finding | Severity | Закрытие |
|---|---|---|
| Alembic URL precedence и migration guard | High | Explicit Config URL авторитетен; host/name/main/current_database negatives выполняются до DDL |
| Неполная relationship matrix | High | Сверена с физическими FK/логическими ключами; обязательные review-связи и дополнительные contact/print tables включены |
| Provenance validity/identity drift | High | Safe identity, target, expiry и DB-time validity входят в snapshot; submit/approve переводят в `REAPPROVAL_REQUIRED` |
| Неточный idempotent replay | High | Revision `z9…` добавляет append-only PII-free immutable result projection; replay возвращает исходный status/version |
| Полный ИИН по широкому scope | High | Отдельного canonical permission нет; ADMIN и HR_HEAD получают только masked ИИН |
| Недетерминированный fingerprint | Medium | Canonical row hashes сортируются; order-change стабилен, значимый update меняет digest |
| Небезопасный RBAC downgrade | High | Проверяется точный permission/target tuple и count; внешний same-reason grant блокирует downgrade |
| Несогласованные нормативные таблицы | Medium | Исходные секции WP‑TD‑001/002/002A и основного плана приведены к единой классификации |
| Ad hoc HR-attestation | Medium | Application-status rule формализован с lookup/digest/stages/обязательным решением `HR_HEAD` |
| Недостаточные negative/concurrency/no-delete tests | Medium | Добавлены spy, append-only/projection, четыре класса concurrent drift и самодостаточный сценарий 11 записей |

## Граница

Permission `TEST_PERSONNEL_DELETION_EXECUTE` остаётся зарезервированным RBAC-кодом. Endpoint,
service command, SQL удаления целей и execution UI отсутствуют. Будущий execution требует
отдельного WP, независимого tombstone/hash и нового execution-time catalog/fingerprint check.
