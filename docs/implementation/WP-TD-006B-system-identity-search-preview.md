# WP-TD-006B — безопасный поиск и preview системных User/Role

Статус: **backend search/preview; любые изменения и execution запрещены**.

Поддерживаемая Alembic revision: только `td006afnd601`.

## API и права

- `POST /directory/test-system-identity-deletion/search` выполняет поиск по
  точному техническому ID и/или безопасной glob-маске `*`/`?`.
- `POST /directory/test-system-identity-deletion/preview` принимает только
  точный список `{object_type, object_id}`; маска в preview не допускается.
- Для User разрешены только `full_name` и `login`; для Role — `name` и `code`.
- Оба endpoint требуют активного primary Role `ADMIN` и permission
  `TEST_SYSTEM_IDENTITY_DELETION_REQUEST`. Даже ошибочный будущий grant не
  открывает workflow для `HR_HEAD`.

Search и preview используют `REPEATABLE READ, READ ONLY`; они не создают
запросы, решения, audit-команды, тестовые записи и не изменяют бизнес-данные.
Request/approval/execute endpoints в 006B отсутствуют.

## Допуск и блокировки

Search возвращает только User/Role с записью в
`test_system_identity_provenance`. Preview точного ID дополнительно показывает
причину отказа, если provenance отсутствует.

- `HISTORICAL_AUTHORSHIP` исключается из search и всегда блокируется в preview.
- User с `employee_id` или через Employee с `person_id` блокируется.
- canonical Role `ADMIN`/`HR_HEAD` блокируется независимо от provenance.
- Role с `is_active=true` блокируется независимо от provenance.
- Role с любым связанным User блокируется как shared/in-use Role.
- Полиморфный security grant на User/Role блокируется.

## Связи и fingerprints

Каждая найденная связь возвращает только метаданные, count и digest полного
состояния строк; исходные строки и чувствительные поля не выдаются. Категории:

- `BLOCKING` — связь требует отдельного решения и делает запись неготовой;
- `PRESERVE` — строка должна сохраниться, включая `ON DELETE SET NULL` и typed
  provenance;
- `REBIND_HISTORICAL_AUTHORSHIP` — только кандидат для будущей отдельно
  согласованной перепривязки обязательного авторства;
- `DELETE_ALLOWLIST` — точный статический список десяти известных CASCADE
  satellites; 006B не удаляет их.

Typed IDs дедуплицируются и сортируются сначала по типу, затем по ID. Ответ
содержит `WP-TD-SYSTEM-MANIFEST/v1` hash списка и aggregate
`WP-TD-SYSTEM-RELATIONSHIP/v1` fingerprint, включающий catalog hash и каждый
per-target relationship fingerprint.

`WP-TD-SYSTEM-CATALOG/v2` фиксирует только identity-deletion contract:
релевантные колонки `users`, `roles` и `test_system_identity_provenance`,
защищённое состояние `HISTORICAL_AUTHORSHIP`, все входящие FK на `users`/`roles`,
triggers на этих таблицах и таблицах-источниках FK, search/canonical/CASCADE
allowlist и точный registry logical-ссылок. Reviewed hash:
`516e9c2db97527314e44434c8d090b4c91e89109018cf4d60ca2320922ed62f8`.

Посторонние public, staging, import и contact-объекты сами по себе не входят в
catalog fingerprint. Зарегистрированная logical-ссылка учитывается только для
выбранного User/Role при точном совпадении `user_id`/`role_id`, `roles.code` или
`roles.name`. Неизвестный входящий FK, identity-подобная logical-колонка,
релевантный trigger/column shape или Alembic revision по-прежнему приводит к
`TD_SYSTEM_CATALOG_MISMATCH` до оценки кандидатов.

## Отложенные решения

006B не утверждает механизм сохранения typed provenance после физического
удаления, способ перепривязки авторства или фактический порядок CASCADE DELETE.
Эти категории являются inventory для следующего review, а не разрешением на
изменение данных. Также отложены manifest persistence, request/approval,
separation of duties, execution, feature flag и frontend.
