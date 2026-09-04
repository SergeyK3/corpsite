# WP-TD-002A — Foundation Hardening

| Поле | Значение |
|---|---|
| Статус | **Ready for Review** |
| Дата | 2026-09-04 |
| Миграция | `y8z9a0b1c2d3` после `x7y8z9a0b1c2` |
| Физическое удаление | **Не реализовано** |

> **Закрыто WP-TD-002B.** Актуальный нормативный контракт находится в
> `WP-TD-002B-test-personnel-deletion-foundation-review-closure.md`.

## Результат

WP-TD-002A исправляет findings строгого review, не добавляя execution. В новом контуре нет
SQL `DELETE` целей, execution endpoint и кнопки исполнения. Permission
`TEST_PERSONNEL_DELETION_EXECUTE` зарезервирован, но endpoint отсутствует.

Десять из одиннадцати найденных синтетических записей проходят создание точного
`LEGACY_MANIFEST`, submit и согласование. Шесть `intake_submitted` требуют
`submitted_synthetic_confirmed=true` от `HR_HEAD`. Одна запись с legacy `personnel` и
`contacts` остаётся `BLOCK`. Имена, число и ID не зашиты в runtime.

## Relationship matrix и fingerprint

Каждое server-owned правило содержит category, постоянный lookup, ключи, state digest,
safe result code и допустимость create/approve/future execution. SQL identifiers и predicates
не поступают от клиента. Найденные строки преобразуются в canonical JSON и SHA-256;
сохраняются count/digest/category/code. Значимый `UPDATE` меняет fingerprint при прежнем
числе строк, а ПДн и payload не сохраняются.

| Таблица/связь | Категория | Lookup и digest | Create / approve / future execute |
|---|---|---|---|
| все `personnel_applications` Person | INFORMATIONAL | `person_id`, полный state digest | да / да / да |
| `employees`, legacy `personnel`, `contacts`, `contact_access`, `key_contacts`, `org_unit_key_staff`, `person_assignments`, `enrollment_queue` | BLOCK | Person | нет / нет / нет |
| `personnel_record_events` | TOMBSTONE_REQUIRED | Person, canonical row digest | да / да / нет |
| `ppr_command_executions` | TOMBSTONE_REQUIRED | Person, canonical row digest | да / да / нет |
| `personnel_record_metadata` | INFORMATIONAL | Person, state/version | да / да / да |
| профильные PPR-разделы | BLOCK | Person | нет / нет / нет |
| `person_photos`, `person_photo_sources` | BLOCK | Person и все Application ID | нет / нет / нет |
| Telegram bindings/activations | BLOCK | Person | нет / нет / нет |
| verification, identity reconciliation, `hr_personnel_change_events` | BLOCK | Person | нет / нет / нет |
| baseline/monthly/import candidates и `hr_change_events` | INFORMATIONAL | Employee → Person | да / да / да |
| `personnel_migration_runs` | BLOCK | Person или Employee context | нет / нет / нет |
| `incoming_documents` | BLOCK | inbound `sender_person_id` | нет / нет / нет |
| `persons.merged_into_person_id` | BLOCK | inbound link | нет / нет / нет |
| intake review/transfer/blockers/resolution/onboarding | BLOCK | все Application ID Person | нет / нет / нет |
| intake reconciliation | BLOCK | Person и все его Application ID | нет / нет / нет |
| допустимый early lifecycle audit | TOMBSTONE_REQUIRED | все приложения + server action allowlist | да / да / нет |
| прочий lifecycle audit | BLOCK | все приложения | нет / нет / нет |
| intake links/drafts | INFORMATIONAL | все приложения; status/timestamps/payload/token digest | да / да / да |
| enrollment history, HR override/history, security audit | INFORMATIONAL | Person/join | да / да / да |
| HR import rows/normalized | INFORMATIONAL | join Employee/Person | да / да / да |
| users, user-linkage review/execute и employee documents | BLOCK | join Employee/Person | нет / нет / нет |
| onboarding notifications/task audit | BLOCK | onboarding → заявки Person/Employee | нет / нет / нет |
| incoming children и order links | BLOCK | официальный incoming document/Employee | нет / нет / нет |
| order attachments/editorial/evidence/item bases/localized/prints | BLOCK | order item/signatory Employee | нет / нет / нет |

Во всех строках digest означает SHA-256 canonical full-row state, отсортированный по
стабильному техническому ключу/row hash; lookup keys и stage flags являются обязательными
непустыми полями server-owned contract. Retained audit не удаляется и относится к
`INFORMATIONAL`; official lifecycle, metadata и intake не смешиваются с PPR technical journals.

`intake_submitted` получает формальное server-owned policy-rule
`SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED` категории `HR_ATTESTATION_REQUIRED`: create
разрешён, approve требует `submitted_synthetic_confirmed=true`, future
execution обязан повторить проверку. Любой иной status кроме `intake_pending` — `BLOCK`.

## Manifest, drift и атомарность

Manifest обязан содержать все приложения выбранного Person. После создания неизменяемы IDs,
order, basis, criteria, mask, initiator и `target_set_hash`. Маска остаётся explainability
metadata и больше не исполняется.

Submit и approve используют `SERIALIZABLE`, request row lock и согласованный snapshot.
Relationship tables блокируются в `SHARE` до чтения, поэтому конкурентная новая/изменённая
связь не проходит между recheck и `APPROVED`. Serialization failure имеет ограниченный retry
и безопасный код. Исчезновение цели или неполный набор приложений переводит запрос в
`REAPPROVAL_REQUIRED` с безопасной history. Future execution обязан сделать отдельный recheck.

## Idempotency, expiry и аудит

Idempotency identity: actor + action + key. Canonical SHA-256 включает action, request ID и
payload; transaction advisory lock сериализует совпадающие команды. Повтор с иным request или
payload даёт `TD_IDEMPOTENCY_PAYLOAD_CONFLICT`; необработанный unique violation невозможен.
History хранит actor/role/permission, request, версии, set hash, command hash, result code и
неизменяемую безопасную result projection. Replay возвращает первоначальную projection, а не
текущее состояние request.

DB `statement_timestamp()` определяет 24-часовой срок. После `approval_expires_at` чтение
возвращает effective `EXPIRED`; просроченный pending decision создаёт transition/history.
Append-only triggers запрещают UPDATE/DELETE provenance, decisions и history; target/request
guards защищают manifest. Сохраняемый аудит не имеет FK к Person/Application.

Обязательная свободная reason заменена на `reason_code`. Необязательный comment после trim
имеет 1–500 символов; очевидные ИИН, телефоны и email отклоняются кодом
`TD_COMMENT_PII_FORBIDDEN`. Decision comment хранится один раз и не копируется в history.
Retention: политика security audit/legal hold; автоматическое удаление не реализовано.

## RBAC и scope

Create/submit/cancel требуют primary role `ADMIN` и REQUEST grant. Approve/reject требуют
active primary role `HR_HEAD` и APPROVE grant. Personal cross-grant не меняет обязанность
роли; self-approval запрещён по `user_id`. Инициатор видит свой request, чужой — только с
APPROVE/AUDIT_READ. HR queue/detail применяют organizational PPR scope к каждой цели. ИИН в
WP-TD-002B всегда маскируется: отдельного canonical sensitive-identity permission в проекте
нет, а широкий organizational/personnel scope не считается таким правом.

Migration fail closed при существующем permission code. Downgrade удаляет только grants/roles
с точным owner marker; внешний grant блокирует downgrade. Триггеры удаляются до таблиц,
функции — после.

## Unicode search

Mask нормализуется NFC, имеет длину 3–100, максимум 10 wildcard и минимум три
буквенно-цифровых literal. `*`/`?` преобразуются после escaping `\\`, `%`, `_`; SQL
параметризован. DB contract: `normalize(full_name, NFC) COLLATE "und-x-icu" ILIKE ...`.
Composed/decomposed Unicode и Unicode-регистр покрыты PostgreSQL-тестом.

## Legacy hard-delete

`DELETE /directory/employees/{id}` и `POST /directory/employees/bulk-delete` безусловно
возвращают HTTP 410 `TD_LEGACY_HARD_DELETE_DISABLED` до delete service. Web process не имеет
escape hatch: `APP_ENV`, ошибочное имя среды, `ALLOW_LEGACY_PERSONNEL_HARD_DELETE`, loopback
`DATABASE_URL`, headers и query params не включают удаление. Backend capability и frontend
capability всегда false; role-id fallback отсутствует. CLI не добавлялся.

## Проверка и граница

PostgreSQL tests выполняются на одноразовых БД `_test`, клонированных из фактической локальной
production-compatible схемы и удаляемых после прогона. Покрыты реальный chain
`x7y8z9a0b1c2 → y8z9a0b1c2d3 → x7y8z9a0b1c2`, RBAC ownership, concurrent transitions,
idempotency, same-count drift, missing target, scope, expiry, hostile PII, Unicode и
hard-delete fail-closed.

Alembic explicit `Config.sqlalchemy.url` имеет приоритет над process `DATABASE_URL` и `.env`.
Harness до миграционного DDL проверяет test suffix, loopback host, отличие от основной БД и
фактический `current_database()`.

Execution запрещён до отдельного WP с независимыми tombstone/hash для PPR events/commands и
допустимого lifecycle audit, плюс execution-time catalog/relation recheck.
