# WP-PPR-MIG-000 — Stage 0: cohort preflight

**Статус:** Draft — Ready for Architecture Review

**Связанная программа:** [поэтапная миграция личных карточек из контрольного списка](ppr-control-list-staged-migration-plan.md).

## 1. Цель и границы

Stage 0 формирует точный frozen cohort сотрудников, допускаемых к последующей
поэтапной миграции PPR. Это read-only preflight: он классифицирует состояние,
фиксирует безопасный snapshot и возвращает технический отчёт. Он не переносит
никакие section data, не изменяет общие сведения, образование или послужной список,
не создаёт собственный путь materialization PPR и не заменяет ADR-065.

Если связь `Employee → Person` отсутствует или требует исправления, допустимый путь
только один: существующий ADR-065 existing-card repair contour. Stage 0 не вызывает
его автоматически и не создаёт `Person`, `Employee`, assignment либо PPR envelope.

## 2. Подтверждённая существующая опора

| Component | Подтверждённое назначение | Использование Stage 0 |
|---|---|---|
| [ADR-065](../adr/ADR-065-personnel-enrollment-orchestration-existing-card-repair.md) | Единственный authority-preserving contour repair `Employee → Person`; exact-IIN, fail-closed resolution, provenance и stale-precondition protection. | Направляет blocked link cases в repair, но не выполняется самим preflight. |
| `app/services/adr065_person_link_service.py` | Транзакционный link/adopt/create с request fingerprint; проверяет status Employee, активный IIN, approved normalized records, Person status/merge и конфликт другого operational Employee. | Источник подтверждённых safe codes и правил conflict; не batch-preflight executor. |
| `app/personnel_lk/application/control_list_repair_preflight_service.py` | Read-only exact-IIN preflight: source selection, ownership, approved normalized records, ADR-048 resolution, primary-assignment inspection. | Переиспользуемая логика и контракт для per-participant diagnostic; её HTTP route использует `REPEATABLE READ READ ONLY`. |
| `POST /directory/personnel/lk/control-list-repair/preflight` | HR-admin API к этому read-only per-IIN preflight. | Может переиспользоваться для diagnosis/repair preview, не является API массового cohort run. |
| `app/services/adr048_person_resolution_service.py` | Exact identity resolution с result `P0_CREATE`, `P1_ADOPT`, `AMBIGUOUS`, `INCOMPATIBLE`, `CONFLICT`. | Основа fail-closed Person resolution. |
| `hr_import_batches`, `hr_import_rows`, `hr_import_normalized_records` | Ранее импортированный `HR_CONTROL_LIST`: `batch_id`, `row_id`, `normalized_record_id`, `employee_id`, source key и review provenance. | Канонический source для Stage 0, если выбран именно этот import contour. |
| `app/services/hr_import_employee_binding_service.py` | Binding row/normalized records к Employee; metadata states `bound`, `unbound`, `conflict`; conflicting/rebinding records supersede open records. | Используется для проверки source ownership/binding; batch policy для cohort пока отсутствует. |
| `app/services/hr_import_diff_removal_decision_service.py` и complete-review service | Учитывают unresolved `hr_import_diff_removals`; batch review не готов при pending removal. | Подтверждённый deletion/removal marker, который Stage 0 обязан учесть при выборе source. |
| `PprLifecycleApplicationService` и `personnel_record_metadata` | Existing lifecycle: `MaterializePPR`, `StartCollection`, `ActivatePPR`; envelope хранит state/version. | Только подтверждает существование разрешённого lifecycle path; Stage 0 его не вызывает. |

`control_list_import_*` staging и apply-execution контур также имеют immutable plan
snapshot/fingerprint и idempotency. Они полезны как технический precedent, но это иной
import model; этот WP не объявляет их source of truth вместо `hr_import_*` и не
предписывает их прямое переиспользование.

## 3. Точное правило cohort

Единица рассмотрения — пара `(employee_id, person_id)` вместе с одним выбранным
source provenance set. Пара получает `ELIGIBLE` только если одновременно выполнены
все условия:

1. `Employee` operationally active; для установленного Stage 0 это
   `employees.operational_status = 'active'` (и, где доступны поля projection,
   `is_active = true` и дата действия не исключает сотрудника).
2. Существует ровно одна текущая связь `employees.person_id` с одним `Person`.
3. `Person` имеет `person_status = 'active'` и `merged_into_person_id IS NULL`.
4. Выбран ровно один допустимый `HR_CONTROL_LIST` provenance set: один `batch_id`,
   один `row_id` и полный набор его выбранных `normalized_record_id`; row и каждый
   normalized record принадлежат тому же `employee_id`.
5. Все выбранные normalized records имеют `review_status = 'approved'`.
6. Нет unresolved source deletion/removal или rebinding/ownership marker, относящегося
   к выбранному source scope: нет `superseded` record в выбранном наборе, нет
   ownership conflict, binding `unbound`/`conflict`, и нет применимого pending
   `hr_import_diff_removals` без decision.
7. Для Person существует разрешённый existing PPR path: envelope уже materialized
   либо Stage-specific authorization может применить существующий
   `PprLifecycleApplicationService.materialize_ppr`/`start_collection`. Stage 0 не
   materializes PPR и не делает это предположение молча.

Любая неоднозначность, отсутствующий evidence или нераспознанный status — fail-closed:
участник не входит в frozen cohort.

### Source-status boundary

Подтверждённая per-record норма существующего ADR-065 preflight — только
`hr_import_normalized_records.review_status = 'approved'`. В коде существуют также
`pending`, `rejected`, `promoted`, `superseded`; они не допустимы для новой source
selection Stage 0 без отдельного policy decision. `hr_import_batches` имеет статусы
`UPLOADED`, `PARSED`, `IN_REVIEW`, `APPLY_PENDING`, `APPLIED`, `PARTIALLY_APPLIED`,
`FAILED`, `CANCELLED`, но текущий per-IIN preflight не задаёт cohort-wide allowable
batch status. Выбор допустимого batch-status — открытое архитектурное решение ниже.

## 4. Матрица результатов

| Категория | Fail-closed условие | Подтверждённые technical reason codes / evidence |
|---|---|---|
| `ELIGIBLE` | Выполнены все правила §3. | Exact Employee/Person/source IDs и approved complete provenance set. |
| `BLOCKED_NO_PERSON` | `employees.person_id` отсутствует либо Person по ссылке не найден. | `EMPLOYEE_NOT_FOUND`, `S_LINK_MISSING_PERSON`, `S_LINK_MISSING_PERSON_ABSENT` — только как repair diagnostics, не eligibility. |
| `BLOCKED_AMBIGUOUS_PERSON` | Exact identity resolution возвращает больше одного candidate Person. | `AMBIGUOUS_PERSON`, `PERSON_IIN_AMBIGUOUS`. |
| `BLOCKED_PERSON_MERGED_OR_DELETED` | Person не active или имеет `merged_into_person_id`. | `INCOMPATIBLE_PERSON`, `PERSON_INCOMPATIBLE`; merged marker подтверждён. |
| `BLOCKED_SOURCE_MISSING` | Нет HR control-list row/selected normalized record. | `CONTROL_LIST_RECORD_NOT_FOUND`, `IMPORT_ROW_NOT_FOUND`, `IMPORT_NORMALIZED_RECORD_NOT_FOUND`. |
| `BLOCKED_SOURCE_AMBIGUOUS` | Нельзя выбрать ровно один provenance set или полный набор records. | `IMPORT_SELECTION_REQUIRED`, `IMPORT_SELECTION_INCOMPLETE`. |
| `BLOCKED_SOURCE_STATUS` | Record не approved либо selected batch/source type не допустимы. | `IMPORT_RECORD_NOT_APPROVED`, `IMPORT_BATCH_SOURCE_MISMATCH`; statuses перечислены в §3. |
| `BLOCKED_SOURCE_DELETION_OR_REBINDING` | Superseded/removal/binding/ownership evidence не позволяет подтвердить stable source ownership. | `IMPORT_ROW_OWNERSHIP_CONFLICT`, `IMPORT_NORMALIZED_RECORD_OWNERSHIP_CONFLICT`, `IMPORT_NORMALIZED_RECORD_SCOPE_MISMATCH`, `IMPORT_NORMALIZED_RECORD_BATCH_MISMATCH`; binding states `unbound`/`conflict`; pending diff removal. |
| `BLOCKED_MATERIALIZATION_PATH` | Нет envelope и Stage-specific policy не подтверждает existing lifecycle path. | Новая safe code family требуется; готового batch-preflight code в коде нет. |
| `BLOCKED_PERSON_EMPLOYEE_CONFLICT` | Один Person уже связан с другим operational Employee в conflict scope. | `PERSON_EMPLOYEE_CONFLICT`, `PERSON_ALREADY_LINKED`. |
| `BLOCKED_EMPLOYEE_NOT_ACTIVE` | Employee не `active` или IIN state конфликтен. | `EMPLOYEE_STATE_NOT_ELIGIBLE`, `EMPLOYEE_IIN_CONFLICT`. |

Последние две категории включены, потому что они подтверждены существующим кодом и
не должны маскироваться под другую неоднозначность. `deleted` как отдельное поле
Person в рассмотренных моделях не подтверждено: для Person применяется точная
проверка `person_status` и `merged_into_person_id`, а не выдуманный `deleted_at`.

## 5. Cardinality и порядок

У `employees.person_id` нет подтверждённого поля «основная Employee-связь». Понятие
`is_primary` в существующем коде относится к `person_assignments`, а не к отношению
Employee → Person. Поэтому Stage 0 не выбирает «основной Employee» эвристически.

- cohort содержит одну `(Employee, Person)` pair, а не одну строку на Person;
- один Person, связанный с несколькими operational Employee, —
  `BLOCKED_PERSON_EMPLOYEE_CONFLICT` и не входит в cohort;
- inactive/historical links не дают права считать другой link primary без отдельной
  policy; если они влияют на identity resolution или source ownership, результат
  fail-closed;
- стабильный порядок должен быть задан явно и детерминированно: сначала
  `employee_id ASC`, затем `person_id ASC`, затем `batch_id ASC`, `row_id ASC`.

## 6. Frozen cohort contract

После полного read-only preflight создаётся snapshot будущего `stage_run_id`. Для
каждого `ELIGIBLE` participant сохраняются только технические данные:

| Поле | Контракт |
|---|---|
| `stage_run_id` | Идентификатор будущего section run; Stage 0 не выполняет section apply. |
| IDs | `employee_id`, `person_id`, `batch_id`, `row_id`, полный selected set `normalized_record_id`. |
| `position` | Непрерывная позиция согласно детерминированному порядку. |
| `participant_snapshot_version` | Начальная версия `1`; последующие изменения участника создают новую версию, не меняя cohort/order. |
| `safe_fingerprint` | SHA-256 canonical JSON из technical IDs, record review status, source-record keys, relevant Person/Employee/PPR versions and policy/version identifiers; без полного ИИН, ФИО и raw payload. |
| `formed_at` | Время завершения read-only snapshot. |
| `eligibility_result` | `ELIGIBLE` либо одна/несколько safe blocker categories и codes. |

`stage_run_id`, persistency snapshot и batch execution не существуют как готовый
Stage 0 implementation в текущем коде. Этот раздел — обязательный contract для
следующего implementation WP, а не утверждение о существующей таблице.

## 7. Preflight result

Результат возвращает:

- counts по каждой категории §4;
- отдельный `ELIGIBLE` список для frozen cohort;
- по каждому blocked participant — technical Employee/Person/source IDs, safe category
  и safe reason codes;
- timestamp и policy/source version identifiers;
- без полного ИИН, ФИО, raw source text, normalized payload или иных лишних
  персональных данных.

Существующий per-IIN API уже redacts input IIN to presence/last four in its response и
исполняется в `REPEATABLE READ READ ONLY`; batch API/report с этим exact output пока
не реализован.

## 8. Acceptance criteria

Stage 0 готов к использованию только когда implementation WP докажет:

1. полное read-only сканирование выбранного source scope и детерминированную
   classification всех candidate Employees;
2. fail-closed применение всех строк §4;
3. неизменяемый frozen cohort snapshot с contract §6 и stable ordering;
4. отсутствие PPR section writes, materialization, Person/Employee repair и DML во
   время preflight;
5. отдельный safe report и accurate counts без полного ИИН/лишних PII;
6. повторяемый результат на неизменном source snapshot;
7. направляемые repair cases используют ADR-065, а не альтернативный mechanism.

## 9. Gaps и открытые архитектурные решения

1. Не существует готового batch cohort preflight service/API/CLI, `stage_run_id` store
   или participant snapshot store. Нужен отдельный implementation WP.
2. Нужно утвердить допустимые `hr_import_batches.status` для Stage 0. Существующий
   код подтверждает per-record `approved`, но не cohort-wide batch-status rule.
3. Нужно формально определить, как связать pending `hr_import_diff_removals` с exact
   selected provenance set; текущая проверка pending removals работает на уровне batch.
4. Нужно утвердить policy для historical/inactive Employee links одного Person; current
   code не даёт relationship-level primary flag.
5. Нужно подтвердить stage-specific authorization predicate «существует разрешённый
   PPR materialization path» и его safe code. Existing lifecycle commands есть, но
   cohort-level policy/read model отсутствует.
6. Нужно решить, будет ли implementation переиспользовать внутреннюю логику
   `control_list_repair_preflight` напрямую либо выделит общий read port; HTTP
   per-IIN endpoint сам по себе не является массовым runner.

Вне scope этого WP: реализация, DDL/Alembic, DML, production execution, проектирование
Stage 1 и изменение утверждённого program plan.
