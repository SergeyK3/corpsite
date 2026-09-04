# WP-TD-002 — Серверная основа двойного согласования удаления тестовых записей персонала

| Поле | Значение |
|---|---|
| Статус | **Ready for Review** |
| Дата | 2026-09-04 |
| Основание | `test-personnel-data-deletion-approval-plan.md`, `WP-TD-001-test-personnel-deletion-inventory.md` |
| Физическое удаление | **Отсутствует и запрещено в этом WP** |
| Alembic revision | `y8z9a0b1c2d3` после `x7y8z9a0b1c2` |

> **Superseded by WP-TD-002B.** Повторный review потребовал закрыть Alembic URL precedence,
> fingerprint, concurrency, idempotency, RBAC scope, downgrade ownership и legacy gate.
> Актуальное описание: `WP-TD-002B-test-personnel-deletion-foundation-review-closure.md`.
> PPR events/commands и допустимый lifecycle теперь `TOMBSTONE_REQUIRED`, web hard-delete
> всегда отвечает 410 без escape hatch, а approve выполняется атомарно на `SERIALIZABLE`.
> Физическое удаление и execution endpoint отсутствуют.

## 1. Результат

Реализован отдельный server-side aggregate для preview, фиксации manifest,
направления запроса и решения `HR_HEAD`. Ни один новый маршрут не исполняет
удаление. Статусы `EXECUTING`, `COMPLETED`, `FAILED`, SQL `DELETE` целей и кнопка
исполнения намеренно отсутствуют.

Legacy hard-delete Employee закрыт безусловно в web process. Переменные среды,
loopback database, headers и query params не могут открыть gate. Оба старых endpoint
всегда возвращают HTTP 410 и `TD_LEGACY_HARD_DELETE_DISABLED` до delete service.

## 2. Схема

### `test_personnel_provenance`

Append-only ledger будущего тестового происхождения:

* `target_type`, `target_id` без FK на Person/Application;
* `environment`, `test_run_id`, `creation_source`, `purpose`;
* `created_by_user_id`, `created_at`, `source_artifact_hash`, `expires_at`;
* `provenance_version` и unique `(target_type, target_id, provenance_version)`.

DB trigger запрещает `UPDATE`/`DELETE`, а insert-trigger всегда выставляет
`created_at=statement_timestamp()`, поэтому backdating через supplied timestamp
невозможен. Публичного API создания provenance в WP-TD-002 нет. Existing records
не получают provenance автоматически.

### `test_personnel_deletion_requests`

Хранит UUID, человекочитаемый `TD-YYYYMMDD-...`, status, basis
`PROVENANCE|LEGACY_MANIFEST`, reason, безопасные criteria/mask, точный
`target_set_hash`, общий relationship fingerprint, optimistic `version`, actor и
timestamps. Request guard запрещает удаление и изменение manifest identity,
criteria, mask, basis, initiator и hash.

### `test_personnel_deletion_targets`

Хранит immutable `request_id`, `target_type=APPLICANT`, точные `person_id` и
`application_id`, manifest order. FK к Person/Application намеренно отсутствуют.
Eligibility — `ELIGIBLE`, `TOMBSTONE_REQUIRED`, `HR_ATTESTATION_REQUIRED`, `BLOCKED`; также сохраняются
безопасные blocker codes, counts snapshot и fingerprint без ФИО/ИИН/телефона/
intake payload. Target guard запрещает изменение состава и удаление; после
`REAPPROVAL_REQUIRED` могут обновляться только eligibility/snapshot/fingerprint.

### Decisions и history

`test_personnel_deletion_decisions` фиксирует APPROVE/REJECT, actor/role/exact
permission, request version, target hash, comment, submitted synthetic attestation
и время. `test_personnel_deletion_history` фиксирует каждый переход, старую/новую
версию, hash, safe result code и idempotency key. Обе таблицы append-only и не
ссылаются FK на удаляемые цели.

## 3. Статусы и переходы

Поддержаны:

* `DRAFT -> PENDING_HR_APPROVAL`;
* `PENDING_HR_APPROVAL -> APPROVED|REJECTED|REAPPROVAL_REQUIRED|EXPIRED`;
* `DRAFT|PENDING_HR_APPROVAL|APPROVED|REAPPROVAL_REQUIRED -> CANCELLED`;
* `REAPPROVAL_REQUIRED -> PENDING_HR_APPROVAL` после нового server recheck и
  обновления fingerprint при неизменном exact manifest.

Submit и approve повторяют relationship check. Drift сохраняет
`RECHECK_FAILED`, увеличивает version, сбрасывает approval timestamps и переводит
request в `REAPPROVAL_REQUIRED`. Approval TTL равен 24 часам. Все команды требуют
`expected_version` и idempotency key; unique `(actor, action, key)` предотвращает
повторное действие.

## 4. Preview и manifest

Разрешён только `persons.full_name`; exact Person/Application IDs передаются
отдельно. Контракт маски:

* Unicode NFC, trim, collapse spaces;
* длина 3–100 code points;
* максимум 10 `*`/`?`, минимум 3 alphanumeric literals;
* `* -> %`, `? -> _` только после literal escaping `\\`, `%`, `_`;
* bound parameter с `ILIKE ... ESCAPE E'\\'`;
* deterministic `ORDER BY person_id, application_id`;
* запрос 201 строки и отказ `TD_PREVIEW_TOO_BROAD`, если result > 200.

Preview использует read-only connection и не создаёт request/history. Create
повторно валидирует точные IDs, сортирует canonical manifest и вычисляет SHA-256.
Маска сохраняется только как explainability metadata и больше не применяется.

## 5. Eligibility policy v1

`POLICY_VERSION=WP-TD-002C/v4`. `BLOCK` дают Employee, legacy personnel, contact,
assignment, профильные PPR sections, photos/provenance, Telegram,
verification, identity reconciliation, HR events, incoming document, intake
review/transfer/reconciliation, application blocker/lifecycle/resolution audit,
onboarding, personnel order/director resolution и неподдерживаемый application
status.

`personnel_record_metadata`, intake links/drafts и retained security/import audit относятся к
`INFORMATIONAL`; полный canonical row digest участвует в fingerprint без сохранения ПДн.
`intake_pending` может быть `ELIGIBLE`. `intake_submitted` получает
`HR_ATTESTATION_REQUIRED`; approve требует
`submitted_synthetic_confirmed=true`. `PROVENANCE` требует актуальную запись для
текущего environment. `LEGACY_MANIFEST` не считает имя, mask, manual source или
idempotency key доказательством происхождения.

`personnel_record_events`, `ppr_command_executions` и допустимый ранний lifecycle audit
относятся к `TOMBSTONE_REQUIRED`: create/approve разрешены, future execution запрещён до
отдельного tombstone/hash WP.

Нормативная классификация foundation:

| Класс связи | Категория | Lookup/digest | Create / submit / approve / future execution |
|---|---|---|---|
| legacy `personnel` и logical `contacts.person_id` | `BLOCK` | Person; canonical row digest | нет / нет / нет / нет |
| профильные PPR, Employee/assignment/user/identity, official order/document | `BLOCK` | Person/Employee/Application inbound graph; canonical row digest | нет / нет / нет / нет |
| `personnel_record_events`, `ppr_command_executions` | `TOMBSTONE_REQUIRED` | Person; canonical row digest | да / да / да / нет |
| ранний application lifecycle allowlist | `TOMBSTONE_REQUIRED` | все Application ID Person + server action allowlist; canonical row digest | да / да / да / нет |
| официальный lifecycle/resolution | `BLOCK` | все Application ID Person; canonical row digest | нет / нет / нет / нет |
| `intake_submitted` application-status policy | `HR_ATTESTATION_REQUIRED` | selected Application status; canonical application digest | да / да / только с решением `HR_HEAD` / повторный recheck |
| `personnel_record_metadata`, все applications, intake links/drafts | `INFORMATIONAL` | Person + все Application ID; canonical full-state digest | да / да / да / повторный recheck |
| retained security/enrollment/import/order audit и provenance state | `INFORMATIONAL` | FK/logical inbound lookup; canonical full-state digest | да / да / да / повторный recheck |

Каждая конкретная строка server-owned matrix фиксирует непустые `lookup`, технические
`keys`, описание digest и stage admissibility. Raw rows и ПДн в snapshot не сохраняются.

## 6. RBAC

Созданы permissions:

| Permission | ROLE grant |
|---|---|
| `TEST_PERSONNEL_DELETION_REQUEST` | `ADMIN` |
| `TEST_PERSONNEL_DELETION_APPROVE` | `HR_HEAD` |
| `TEST_PERSONNEL_DELETION_EXECUTE` | `ADMIN` (endpoint отсутствует) |
| `TEST_PERSONNEL_DELETION_AUDIT_READ` | `ADMIN`, `HR_HEAD` |

Каждый endpoint вызывает точную `has_admin_permission`; canonical role не даёт
bypass. Approver не может совпадать с initiator независимо от grants.

## 7. API

ADMIN/request permission:

* `POST /directory/test-personnel-deletion/preview`;
* `POST /directory/test-personnel-deletion/requests`;
* `GET /directory/test-personnel-deletion/requests`;
* `GET /directory/test-personnel-deletion/requests/{request_id}`;
* `POST /directory/test-personnel-deletion/requests/{request_id}/submit`;
* `POST /directory/test-personnel-deletion/requests/{request_id}/cancel`.

HR_HEAD/approve permission:

* `GET /directory/test-personnel-deletion/approvals`;
* `GET /directory/test-personnel-deletion/approvals/{request_id}`;
* `POST /directory/test-personnel-deletion/approvals/{request_id}/approve`;
* `POST /directory/test-personnel-deletion/approvals/{request_id}/reject`.

Execution route отсутствует. API не принимает regex/SQL field, ИИН, phone,
arbitrary preview JSON или client-supplied blocker/fingerprint.

## 8. Старые endpoints и UI

Закрыты:

* `DELETE /directory/employees/{employee_id}`;
* `POST /directory/employees/bulk-delete`.

`/auth/me.can_hard_delete_employee` теперь всегда false. Frontend fail closed и больше не
выводит hard-delete по fallback `role_id=2`/`is_system_admin`. Остальные delete
маршруты относятся к документам/import-card/orders и не являются прямым
hard-delete Person/Employee/Application.

## 9. Проверка

Актуальная проверка WP-TD-002A выполняется на одноразовых loopback PostgreSQL-БД с
суффиксом `_test`, клонированных из production-compatible локальной схемы и удаляемых после
каждого прогона.

Подтверждены upgrade `x7y8z9a0b1c2 -> y8z9a0b1c2d3`, downgrade обратно и
повторный upgrade. Целевые integration tests покрывают RBAC, glob escaping,
read-only preview, frozen manifest, blockers, submitted attestation, transitions,
optimistic locking, idempotency, drift/reapproval, expiry, actor separation,
audit minimization, append-only, production gate и отсутствие execution route.

Фактические 11 локальных кандидатов: 3 Debug + 8 Demo. PPR events/commands дают
`TOMBSTONE_REQUIRED`, но не блокируют create/approve. Десять записей согласуемы; шесть
submitted требуют HR attestation. Одна Demo блокируется `LEGACY_PERSONNEL_PRESENT` и
`CONTACT_PRESENT`. Количество не hardcoded в runtime.

## 10. Граница следующего WP

Переход к проектированию физического исполнения запрещён до отдельного решения о
tombstone для PPR/lifecycle журналов, повторной catalog-проверки allowlist и
проектирования атомарного delete plan. Permission EXECUTE является только
зарезервированной capability и не используется ни одним endpoint.
