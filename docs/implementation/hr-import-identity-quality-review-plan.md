# HR import identity-quality review plan

**Статус:** Draft — Ready for Architecture Re-Review
**Дата:** 2026-09-11

## Цель и границы

Разделить structural parsing errors и проблемы качества identity при импорте
контрольного списка. Строка без корректного ИИН не получает фиктивный ИИН,
не связывается автоматически по ФИО и не останавливает обработку независимых
корректных строк. План не меняет автоматически canonical `Person`/`Employee`
и не изменяет существующий batch 48.

## Утверждённые продуктовые решения

| Решение | Контракт |
|---|---|
| Классификация | `missing_iin` и `invalid_iin` — identity-quality exceptions, не structural parsing errors; они не входят в `hr_import_batches.error_rows`. |
| Единственная автоматическая связь | Разрешён только exact-IIN auto-bind: ровно 12 ASCII-цифр и ровно одна действующая IIN identity активного employee. Любая другая ветка возвращает unbound/conflict без изменения строки. |
| ФИО | Автоматическая привязка по ФИО запрещена во всех import, read, repair, roster и promotion ветках. HR_HEAD видит полное ФИО кандидатов только в пределах действующего personnel scope; ФИО служит только контекстом кандидата. |
| ИИН | Фиктивные ИИН запрещены. Введённый ИИН валидируется только как 12 ASCII-цифр в v1; checksum — отдельный будущий пакет. ИИН в UI маскируется согласно существующим permissions. |
| Ненайденная identity | Проверенный 12-значный ИИН без canonical identity сохраняется как `IIN_UNMATCHED` / `UNRESOLVED`; он блокирует complete-review до штатного promotion/binding либо явного `DEFERRED`. |
| Решение HR | HR может подтвердить ИИН, явно подтвердить согласованную существующую пару `Person`/`Employee` или отложить строку. Source row, candidate search и выбранные Person/Employee всегда проверяются сервером по permission и personnel scope. |
| Completion | `UNRESOLVED` блокирует complete-review. Только явный аудируемый `DEFERRED` снимает identity blocker и допускает `APPLY_PENDING`; audit history не удаляется. Structural errors и решения по REMOVED продолжают работать по своим правилам. |
| Promotion и Stage 0 | `DEFERRED` исключается из roster/document promotion и создаёт отдельный Stage 0 blocker. Успешно resolved строки проходят обычную eligibility-проверку. |
| Аудит | Решения identity review сохраняются в append-only событиях без raw ИИН, ФИО, payload, комментариев или stack trace. |
| Новые кадровые сущности | Identity-review не создаёт `Person`/`Employee`; создание допускается только в существующем явном promotion workflow. |
| Исторические данные | Batch 48 не меняется и не переклассифицируется. После развёртывания исходник повторно импортируется как независимый batch `2606-02`. |
| XLSX date defect | Raw numeric ИИН из date-formatted ячейки допускается только по детерминированно подтверждённому raw XML; отображаемая дата не преобразуется обратно. |

## Текущее состояние и обязательный allowlist binding

Сейчас `scripts/import_hr_control_list.py` помещает `missing_iin` и
`invalid_iin_length:*` в `ParsedRow.errors`, а `hr_import_service` переносит их
в `hr_import_rows.error_codes` и `error_rows`. Complete-review трактует
положительный `error_rows` как blocker. Кроме того,
`resolve_employee_binding()` умеет fallback по ФИО, а roster promotion вызывает
`repair_batch_employee_bindings()`.

IQ-1 обязан устранить ФИО-auto-bind из **всех** перечисленных мест, а не только
из одного resolver:

| Ветка | Требуемое поведение после IQ-1 |
|---|---|
| `resolve_employee_binding()` | Только exact-IIN; не искать employee по ФИО. |
| `auto_bind_import_row()` | Persist только единственный exact-IIN result. |
| `repair_batch_employee_bindings()` и repair endpoint | Повторять только exact-IIN; не исправлять строку по ФИО. |
| `binding_info_for_row()` и read/API serializers | Могут показать scope-filtered кандидатов по ФИО, но никогда не сообщают `BOUND` и не записывают связь по ФИО. |
| roster promotion, включая вызов repair | Не наследует ФИО fallback; promotion использует только explicit binding или exact-IIN. |
| normalized-record promotion | Fail-closed: только `RESOLVED` current identity state и согласованная связь. |

Тесты IQ-1 покрывают каждый путь, включая один уникальный ФИО-match: итог — не
привязанная строка и отсутствие записи canonical binding.

## Состояния строки, completion и счётчики

| Условие | Current identity state / code | Complete-review | Promotion | Stage 0 |
|---|---|---|---|---|
| Нет ИИН | `UNRESOLVED` / `IIN_MISSING` | blocker | исключена | `STAGE0_IDENTITY_QUALITY_UNRESOLVED` |
| Формат ИИН неверен | `UNRESOLVED` / `IIN_INVALID_FORMAT` | blocker | исключена | `STAGE0_IDENTITY_QUALITY_UNRESOLVED` |
| ИИН подтверждён, identity не найдена | `UNRESOLVED` / `IIN_UNMATCHED` | blocker | исключена | `STAGE0_IDENTITY_QUALITY_UNRESOLVED` |
| HR подтвердил согласованную pair | `RESOLVED` / `IIN_CONFIRMED` | не blocker | по обычным правилам | обычная eligibility-проверка |
| HR отложил строку | `DEFERRED` / `IIN_DEFERRED` | не blocker | исключена | `STAGE0_IDENTITY_QUALITY_DEFERRED` |

`total_rows` — число импортированных employee rows и никогда не меняется из-за
review. `error_rows` — число строк с хотя бы одним **structural** error code.
`valid_rows = total_rows - error_rows`; identity exception не уменьшает
`valid_rows`. Отдельно сервер возвращает current-state counters по уникальным
row: `identity_exception_rows`, `identity_unresolved_rows`,
`identity_deferred_rows`, `identity_resolved_rows`. Одну строку нельзя считать
дважды в одном current-state counter; исторические audit events не увеличивают
эти счётчики. UI показывает structural errors и identity queue раздельно.

Complete-review допускает `APPLY_PENDING` только при нулевых structural errors,
нулевых обязательных review/removal blockers и нулевом
`identity_unresolved_rows`. `DEFERRED` остаётся в audit и в отдельном счётчике,
но не является completion blocker.

## Identity-review audit и атомарное решение

Нужна отдельная append-only таблица `hr_import_identity_review_events`; обычные
`hr_review_overrides` не использовать: они не имеют import-row scope и их
history может содержать JSON field values.

Минимальные безопасные поля события:

- immutable `event_id`, `idempotency_key`, `batch_id`, `row_id`;
- enum `event_type`: `IIN_CONFIRMED`, `PERSON_EMPLOYEE_LINK_CONFIRMED`,
  `DEFERRED`; resulting state и identity-quality code;
- `actor_user_id`, `occurred_at`;
- nullable выбранные `person_id` и `employee_id`;
- SHA-256 fingerprint original/entered IIN, source-row fingerprint,
  before/after normalized-payload fingerprint;
- optimistic row version / source version и policy version.

В таблице запрещены raw ИИН, ФИО, payload, произвольный комментарий и stack
trace. Подтверждённый ИИН при необходимости хранится только в существующем
`normalized_payload.iin`; исходное значение остаётся в `raw_payload` по
существующим правилам доступа.

Для event table обязательны FK, enum/check constraints, unique
`idempotency_key`, индексы `(batch_id, row_id, occurred_at DESC)` и current
identity queue, а также trigger, отвергающий `UPDATE` и `DELETE`. Idempotency key
при идентичном запросе возвращает прежний результат; тот же key с иным actor,
row, version, fingerprints или decision даёт безопасный conflict без PII.
Current state — последнее валидное событие для текущего source-row fingerprint.

### IQ-2 event matrix and state ordering

| event type | actor type | resulting state / reason | person / employee | original IIN fingerprint | entered IIN fingerprint |
|---|---|---|---|---|---|
| `SYSTEM_IIN_MISSING` | `SYSTEM` (no user) | `UNRESOLVED` / `IIN_MISSING` | forbidden | forbidden | forbidden |
| `SYSTEM_IIN_INVALID_FORMAT` | `SYSTEM` (no user) | `UNRESOLVED` / `IIN_INVALID_FORMAT` | forbidden | required | forbidden |
| `SYSTEM_IIN_UNMATCHED` | `SYSTEM` (no user) | `UNRESOLVED` / `IIN_UNMATCHED` | forbidden | required | forbidden |
| `IIN_CONFIRMED` | `HR` (real user required) | `UNRESOLVED` / `IIN_UNMATCHED` | forbidden | required | required |
| `PERSON_EMPLOYEE_LINK_CONFIRMED` | `HR` (real user required) | `RESOLVED` / `IIN_CONFIRMED` | both required and canonical | required | required |
| `DEFERRED` | `HR` (real user required) | `DEFERRED` / `IIN_DEFERRED` | forbidden | optional | forbidden |

IQ-2 creates only this contract; IQ-3 is the first package allowed to emit system
classification events. The effective state materializes `event_id`, batch/row,
source fingerprint, resulting state, and reason code. The deterministic latest
event order is `(occurred_at ASC, event_id ASC)`; equal timestamps are broken by
the immutable identity value. Deferred triggers lock the stable
`hr_import_rows(batch_id,row_id)` parent first, then the current-state row, and
at `SET CONSTRAINTS ... IMMEDIATE` or commit require every event to have a state
that selects that latest event. Future writers retain this parent-row-first
`FOR UPDATE` order.

### Транзакционный контракт HR action

Каждое action выполняется одной DB-транзакцией:

1. Сервер авторизует actor на source batch/row и выбранную canonical identity
   через действующий personnel scope; поиск кандидатов также scope-filtered.
2. Сервис блокирует import row, latest identity event/current-state и при
   необходимости employee, person и active IIN identity через `FOR UPDATE`.
3. Сверяется request idempotency key, optimistic row version и source/payload
   fingerprints. Несовпадение даёт `409` без изменения данных.
4. Для `PERSON_EMPLOYEE_LINK_CONFIRMED` сервер проверяет существование и
   активность employee, точную связь employee с переданным person и exact match
   подтверждённого ИИН с единственной действующей IIN identity этого employee.
5. В одной транзакции записываются event, допустимое изменение
   `normalized_payload.iin`, materialized identity state, `employee_id` binding
   и propagation rebuildable normalized records. Любая ошибка откатывает всё.

Ни UI, ни API не могут передать доверенный `employee_id`/`person_id` без этих
проверок. ФИО никогда не является условием binding.

## PII redaction и API

Audit events, security metadata, application logs, exception messages, metrics
labels и API errors не содержат raw ИИН, ФИО, payload или SQL details. Ошибки
возвращают только стабильные safe codes; ИИН в обычных HR responses маскируется
по существующим permissions. Полное ФИО кандидата доступно только HR_HEAD в
scope; candidate search не раскрывает людей вне scope. Тесты проверяют JSON,
audit rows и captured logs на отсутствие этих значений.

## Completion, promotion и Stage 0

Promotion читает current identity state в SQL и fail-closed исключает
`UNRESOLVED` и `DEFERRED`, даже если иной batch-level путь передал row ID.

Stage 0 при классификации source rows присоединяет current identity state до
проверки `employee_id`. Приоритет фиксирован:

1. `UNRESOLVED` → `STAGE0_IDENTITY_QUALITY_UNRESOLVED`;
2. `DEFERRED` → `STAGE0_IDENTITY_QUALITY_DEFERRED`;
3. только затем отсутствие employee → `STAGE0_SOURCE_EMPLOYEE_MISSING`;
4. остальные существующие eligibility checks.

`ppr_stage0_cohort_blockers` уже допускает source row без employee/person; для
таких blockers сохраняются source row ID, safe candidate key и safe fingerprint,
но не PII. Valid rows того же run остаются eligible.

## Детерминированное восстановление date-formatted ИИН из XLSX

Обычная строковая/numeric обработка сохраняется. Дополнительный raw-XML fallback
допустим только если `openpyxl` вернул `date`/`datetime` для распознанного IIN
поля текущей employee row и одновременно выполнены все условия:

1. Sheet XML определяется по title через `xl/workbook.xml` и relationship target
   из `xl/_rels/workbook.xml.rels`; порядок листов не используется.
2. Координата XML cell точно равна координате распознанного IIN field. Cell не
   является shared string (`t="s"`), inline string или formula cell.
3. `styles.xml` подтверждает, что style этой cell имеет date format; relationship
   и style index существуют и однозначны.
4. Literal raw `<v>` существует и состоит ровно из 12 ASCII-цифр; scientific
   notation, whitespace, знак, decimal и cached formula value отклоняются.
5. Не используются Excel serial conversion, display text, округление, эвристика,
   1900/1904 epoch или иной способ восстановить дату.

При любом нарушении строка остаётся identity-quality exception. Regression
fixtures включают `прочее!E50`, shared string, formula, неверный relationship,
изменённый sheet order, non-date style и неоднозначный/нечисловой raw XML.

## Schema-only migration, downgrade и исторические batches

Migration создаёт только новую event/state schema и индексы: без backfill,
reclassification, изменения `error_codes`, counters, bindings или payload
исторических batches. Readers применяют identity state только при наличии
события/нового state; batch 48 остаётся неизменным.

Downgrade разрешён только на пустых новых event/state tables. При существующем
audit или materialized identity state он fail-closed завершается ошибкой до
любого `DROP`; `CASCADE` запрещён. Миграция и downgrade проверяют rowcount и
postconditions в транзакции.

## Последовательность work packages

| Package | Scope | Совместимый результат |
|---|---|---|
| IQ-1 — Completed | Убрать ФИО auto-bind из полного allowlist путей; exact-IIN regressions | Закрывает небезопасную связь без изменения batch data. |
| IQ-2 — Completed | Schema-only Alembic/ORM: append-only events, current state, guarded downgrade | Есть надёжное хранилище до изменения parser semantics. |
| IQ-3 | Parser разделяет structural и identity quality; детерминированный raw XML; persist current identity state при import | Новые imports не создают identity `error_rows`, но имеют persistent queue. |
| IQ-4 | Service/API queue и три HR action с transaction/RBAC/scope/idempotency contract | Проверяемые индивидуальные решения без auto-create. |
| IQ-5 | Completion counters/UI, promotion exclusions, Stage 0 precedence/blockers | Сквозной fail-closed workflow. |
| IQ-6 | PostgreSQL/API/UI races, replay, security and controlled-release runbook | Доказательство атомарности, auditability и обратимости схемы. |

## Обязательные тесты

- exact-IIN allowlist во всех resolver, auto-bind, repair, read/binding-info,
  roster и promotion путях; уникальный ФИО-match не создаёт binding;
- structural errors по-прежнему блокируют complete-review; `UNRESOLVED` блокирует,
  а только `DEFERRED` снимает identity blocker;
- точные counters и UI counters не смешивают current rows, audit history и
  structural errors;
- Person/Employee/IIN mismatch, inactive identity, stale row version и source
  fingerprint mismatch отклоняются атомарно;
- одинаковый idempotency request replay безопасен, конфликтный replay отклонён;
  два конкурентных HR action не создают два effective state;
- event, payload, binding и propagation полностью откатываются при искусственной
  ошибке; append-only trigger отвергает update/delete;
- RBAC/scope для row, candidate search и selected Person/Employee; API/log/audit
  не содержат raw ИИН, ФИО, payload, stack trace или SQL detail;
- exact Stage 0 precedence и blocker без employee/person; unresolved/deferred не
  попадают в promotion;
- raw XML positive case и все отрицательные cases из раздела XLSX;
- PostgreSQL migration upgrade → downgrade → upgrade, single head, guarded
  downgrade с данными и отсутствие частичных изменений при отказе;
- исторический batch 48 не изменяется миграцией или readers без нового event.

## Требуемые изменения при реализации

- `scripts/import_hr_control_list.py`;
- `app/services/hr_import_service.py`;
- `app/services/hr_import_employee_binding_service.py`;
- `app/services/hr_import_complete_review_service.py`;
- `app/services/hr_import_roster_promotion_service.py`;
- `app/services/hr_import_promotion_service.py`;
- `app/services/ppr_stage0_cohort_service.py`;
- новый identity-review service/repository, ORM model и Alembic migration;
- `app/directory/hr_import_routes.py` и request/response schemas;
- import-review frontend components/API client;
- unit, API и PostgreSQL integration tests.

## Вне scope

- Переклассификация, изменение или исправление batch 48.
- Автоматическое создание Person/Employee из identity-quality queue.
- IIN checksum validation.
- Массовое подтверждение identity решений.
- Изменения production, данных, кода или миграций в рамках этого документа.
