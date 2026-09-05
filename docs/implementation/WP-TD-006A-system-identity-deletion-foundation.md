# WP-TD-006A — фундамент удаления тестовых системных пользователей и ролей

Статус: **Foundation implementation; execution запрещён**.

Alembic revision: `td006afnd601` поверх `td005exec501`.

## Границы этапа

Этап создаёт только provenance, защищённого технического автора и permissions. Он не создаёт preview/create/approval/execution API, не удаляет User/Role и не добавляет frontend.

## Утверждённые правила

1. User, связанный с Employee прямо или с Person через Employee, физически не удаляется.
2. Только активное серверное provenance с криптографическим artifact hash является доказательством тестового происхождения User/Role.
3. Имя, login, display name, код или название Role, отсутствие активности и fixture-подобный marker доказательством не являются.
4. Обязательные workflow-, ownership- и security-ссылки блокируют удаление. Автоматическая подмена автора или исполнителя запрещена.
5. Исторические audit/journal/control-plane строки сохраняются. Разрешённый `ON DELETE SET NULL` не означает удаление audit-строки.
6. Индивидуальная доказанно тестовая Role может удаляться только атомарно с последним доказанно тестовым User и после проверки отсутствия иных FK/logical consumers.
7. HR_HEAD не участвует в request, approval, execution или audit-read этого процесса.
8. Для одного запроса инициатор, согласующий и исполнитель — разные активные пользователи. Совпадение любого из участников блокирует переход/исполнение.
9. Неизвестная схема, FK, trigger, polymorphic или legacy logical relation означает fail-closed BLOCK.

## Схема фундамента

### Provenance

`test_system_identity_provenance`:

- `provenance_id BIGINT IDENTITY PRIMARY KEY`;
- `object_type TEXT NOT NULL`: только `USER` или `ROLE`;
- `object_id BIGINT NOT NULL`;
- generated `user_id`/`role_id` с настоящими `RESTRICT` FK на `users`/`roles`;
- `source TEXT NOT NULL`;
- `artifact_hash TEXT NOT NULL`, lowercase SHA-256;
- server-stamped `created_at TIMESTAMPTZ NOT NULL`;
- `created_by_user_id BIGINT NOT NULL REFERENCES users ON DELETE RESTRICT`;
- unique `(object_type, object_id, source, artifact_hash)`.

UPDATE, DELETE и TRUNCATE запрещены DB-triggers. Protected system identities не могут получить provenance и потому не могут стать кандидатами.

Миграция не создаёт служебных seed-строк provenance. Поэтому любая строка в `test_system_identity_provenance` является прикладным доказательством и блокирует downgrade. Downgrade также блокируется при любой FK-или известной logical-ссылке на `HISTORICAL_AUTHORSHIP`; таблица provenance, permissions, технический User и вся история при таком отказе сохраняются атомарно.

На этом этапе typed FK имеют `ON DELETE RESTRICT`. Поэтому даже доказанный User/Role ещё не готов к физическому удалению: следующий этап обязан утвердить сохраняемый archival/tombstone-контракт для provenance до появления execution endpoint. Обход FK или отключение append-only trigger не допускаются.

### Технический исторический автор

В `users` добавляются `is_system_identity` и `system_identity_purpose`. Миграция создаёт ровно одну запись с purpose `HISTORICAL_AUTHORSHIP`:

- canonical Role `ADMIN`;
- `employee_id` и `unit_id` отсутствуют; прямой Person-link в User отсутствует;
- `is_active=false`, `locked_at` установлен, `locked_reason='policy'`;
- password, login, Google/Telegram/contact fields отсутствуют;
- запись immutable и защищена от UPDATE/DELETE;
- row-trigger не блокирует штатные UPDATE обычных User, а statement-trigger всегда блокирует `TRUNCATE users`;
- User 1 и User 25 не переиспользуются.

Эта запись предназначена только для будущего утверждённого переназначения обязательного исторического авторства. Само переназначение не входит в WP-TD-006A.

### Permissions

- `TEST_SYSTEM_IDENTITY_DELETION_REQUEST`;
- `TEST_SYSTEM_IDENTITY_DELETION_APPROVE`;
- `TEST_SYSTEM_IDENTITY_DELETION_EXECUTE`;
- `TEST_SYSTEM_IDENTITY_DELETION_AUDIT_READ`.

Все четыре permission по умолчанию назначаются только canonical Role `ADMIN`. HR_HEAD не получает grant. Разделение участников позднее обеспечивается request-level backend gate, а не различием primary Role.

## Следующие этапы

До любого execution обязательны versioned catalog/fingerprint всех FK, CASCADE, append-only triggers и logical relations; immutable manifest; server-owned preview/readiness; append-only request/decision/execute audit; идемпотентность; SERIALIZABLE locking; отдельный физический execution endpoint и frontend с точным подтверждением.
