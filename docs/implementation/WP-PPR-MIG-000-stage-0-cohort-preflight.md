# WP-PPR-MIG-000 — Stage 0: cohort preflight

**Статус:** Approved — Ready for Stage 0 Implementation Planning

**Связанная программа:** [поэтапная миграция личных карточек из контрольного списка](ppr-control-list-staged-migration-plan.md).

## 1. Цель и границы

Stage 0 формирует базовый program cohort сотрудников, допускаемых к последующей
поэтапной миграции PPR. Он состоит из двух явно разделённых операций.

| Операция | Граница |
|---|---|
| `PREVIEW` | Полностью read-only: сканирует и классифицирует кандидатов, возвращает технический отчёт и ничего не сохраняет в БД. |
| `FREEZE` | Явное действие только после проверки preview. В короткой транзакции сохраняет только metadata будущего program cohort, participant snapshots, порядок, fingerprints и blockers. |

`FREEZE` не изменяет `Employee`, `Person`, import source или PPR; не выполняет
materialization либо repair. Обе операции не переносят section data и не изменяют
общие сведения, образование или послужной список; Stage 0 не создаёт собственный
путь materialization PPR и не заменяет ADR-065.

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
| `app/services/hr_import_employee_binding_service.py` | Binding row/normalized records к Employee; metadata states `bound`, `unbound`, `conflict`; conflicting/rebinding records supersede open records. | Используется для проверки source ownership/binding. |
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
4. Подтверждён ровно один source anchor типа `HR_CONTROL_LIST`: `batch_id`, `row_id`,
   source-row Employee ownership и минимальная identity/link provenance, достаточная
   для однозначного сопоставления anchor с этой Employee/Person pair. Это не выбор
   полного набора normalized records будущих sections.
5. Нет unresolved source deletion/removal или rebinding/ownership marker, относящегося
   к anchor: нет ownership conflict, binding `unbound`/`conflict`; если в выбранном
   `batch_id` существует хотя бы один unresolved `hr_import_diff_removals`, `FREEZE`
   блокируется для всего batch.
6. Для Person существует допустимый **структурный** lifecycle path: envelope уже
   materialized либо lifecycle state допускает existing `MaterializePPR` /
   `StartCollection`. Permission конкретного оператора не является eligibility
   сотрудника и проверяется при запуске соответствующего section run. Stage 0 не
   materializes PPR и не делает это предположение молча.

Любая неоднозначность, отсутствующий evidence или нераспознанный status — fail-closed:
участник не входит в frozen cohort.

### Утверждённая batch policy

Source anchor допускается только при `source_type = 'HR_CONTROL_LIST'` и batch status
одном из `APPLY_PENDING`, `APPLIED`, `PARTIALLY_APPLIED`. `UPLOADED`, `PARSED`,
`IN_REVIEW`, `FAILED` и `CANCELLED` не допускаются. Первая реализация применяет
консервативную batch-level проверку pending removals: хотя бы один unresolved removal
в выбранном batch блокирует `FREEZE`. Точное связывание removal с отдельным provenance
set — последующее безопасное улучшение; до него batch-level блокировку ослаблять нельзя.

### Граница source eligibility и section status

Stage 0 подтверждает только устойчивость source anchor и минимальной identity/link
provenance. Он не требует, чтобы normalized records образования, обучения, биографии
или иных будущих разделов уже были `approved`. Каждый section run выполняет свежую
eligibility-проверку только относящихся к нему record kinds. Поэтому неподготовленная
training record не исключает участника из program cohort или из будущего Stage 1
общих сведений.

В существующем per-IIN ADR-065 preflight все специально выбранные normalized records
должны иметь `review_status = 'approved'`; это правило repair selection, а не
универсальный фильтр Stage 0. В normalized record service существуют `pending`,
`approved`, `rejected`, `promoted`, `superseded`. `promoted` не является общей
ошибкой: promotion service выставляет его одновременно с `promoted_document_id` и
классифицирует повторную promotion как skip/already-promoted. Соответствующий section
run должен решать `approved`/`promoted`/other status по своему record kind: уже
перенесённая подтверждённая запись — `already applied` или replay, если это
подтверждает его existing contract.

## 4. Матрица результатов

| Категория | Fail-closed условие | Подтверждённые technical reason codes / evidence |
|---|---|---|
| `ELIGIBLE` | Выполнены все правила §3. | Exact Employee/Person/source anchor IDs и minimal identity/link provenance. |
| `BLOCKED_NO_PERSON` | `employees.person_id` отсутствует либо Person по ссылке не найден. | `EMPLOYEE_NOT_FOUND`, `S_LINK_MISSING_PERSON`, `S_LINK_MISSING_PERSON_ABSENT` — только как repair diagnostics, не eligibility. |
| `BLOCKED_AMBIGUOUS_PERSON` | Exact identity resolution возвращает больше одного candidate Person. | `AMBIGUOUS_PERSON`, `PERSON_IIN_AMBIGUOUS`. |
| `BLOCKED_PERSON_MERGED_OR_DELETED` | Person не active или имеет `merged_into_person_id`. | `INCOMPATIBLE_PERSON`, `PERSON_INCOMPATIBLE`; merged marker подтверждён. |
| `BLOCKED_SOURCE_MISSING` | Нет HR control-list source anchor или его минимальной identity/link provenance. | `CONTROL_LIST_RECORD_NOT_FOUND`, `IMPORT_ROW_NOT_FOUND`, `IMPORT_NORMALIZED_RECORD_NOT_FOUND`. |
| `BLOCKED_SOURCE_AMBIGUOUS` | Нельзя выбрать ровно один source anchor или identity/link provenance. | `IMPORT_SELECTION_REQUIRED`, `IMPORT_SELECTION_INCOMPLETE`. |
| `BLOCKED_SOURCE_STATUS` | Batch/source-anchor status не отвечает утверждённой policy; section-record statuses сюда не входят. | `IMPORT_BATCH_SOURCE_MISMATCH`; policy §3. |
| `BLOCKED_SOURCE_DELETION_OR_REBINDING` | Removal/binding/ownership evidence не позволяет подтвердить stable anchor ownership. | `IMPORT_ROW_OWNERSHIP_CONFLICT`, `IMPORT_NORMALIZED_RECORD_OWNERSHIP_CONFLICT`, `IMPORT_NORMALIZED_RECORD_SCOPE_MISMATCH`, `IMPORT_NORMALIZED_RECORD_BATCH_MISMATCH`; binding states `unbound`/`conflict`; pending diff removal. |
| `BLOCKED_MATERIALIZATION_PATH` | Нет envelope и нет допустимого структурного existing lifecycle path. Authorization оператора сюда не входит. | Новая safe code family требуется; готового batch-preflight code в коде нет. |
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
- inactive/historical Employee link сам по себе не блокирует active Employee → active
  Person pair; он блокирует только при фактической неоднозначности source ownership,
  identity resolution или текущей связи;
- стабильный порядок должен быть задан явно и детерминированно: сначала
  `employee_id ASC`, затем `person_id ASC`, затем `batch_id ASC`, `row_id ASC`.

## 6. PREVIEW, FREEZE и frozen cohort contract

`PREVIEW` вычисляет следующий contract полностью read-only и может быть повторён без
сохранения результатов. Только после review оператор запускает `FREEZE`: короткая
транзакция сохраняет результат уже проверенного preview. Она не пересчитывает и не
меняет business data; при stale input должна fail-closed завершиться без frozen cohort.
Frozen cohort содержит только `ELIGIBLE` participants с непрерывными позициями.
`BLOCKED_*` candidates не становятся его участниками: их IDs, категории и причины
сохраняются в связанном blocker report. Для каждого frozen participant `FREEZE`
сохраняет только технические данные:

| Поле | Контракт |
|---|---|
| `stage_run_id` | Идентификатор базового program-cohort run; Stage 0 не выполняет section apply. |
| IDs | `employee_id`, `person_id`, `batch_id`, `row_id` и только IDs minimal identity/link provenance anchor; не полный набор normalized records будущих sections. |
| `position` | Непрерывная позиция согласно детерминированному порядку. |
| `participant_snapshot_version` | Начальная версия `1`; последующие изменения участника создают новую версию, не меняя cohort/order. |
| `safe_fingerprint` | SHA-256 canonical JSON из technical IDs, record review status, source-record keys, relevant Person/Employee/PPR versions and policy/version identifiers; без полного ИИН, ФИО и raw payload. |
| `formed_at` | Время завершения read-only snapshot. |
| `eligibility_result` | Всегда `ELIGIBLE`; blocker categories/codes принадлежат связанному blocker report, а не participant snapshot. |

`stage_run_id`, persistency snapshot и batch execution не существуют как готовый
Stage 0 implementation в текущем коде. Этот раздел — обязательный contract для
следующего implementation WP, а не утверждение о существующей таблице.

Перед каждым subsequent section run выполняется новая stage-specific eligibility
проверка и формируется отдельный frozen cohort этого section run на основе базового
Stage 0 cohort. Изменение Employee, Person, source ownership, removal/rebinding или
lifecycle между этапами блокирует участника только текущего section run; оно не
отменяет ранее `ACCEPTED` этапы и не меняет задним числом исходный Stage 0 snapshot.
Новые сотрудники добавляются только отдельным supplemental Stage 0 run, не в
существующий frozen program cohort. Тот же supplemental Stage 0 run используется после
исправления ранее blocked candidate: исходный frozen cohort не расширяется задним числом.

## 7. Preflight result

Результат возвращает:

- counts по каждой категории §4;
- отдельный `ELIGIBLE` список для frozen cohort;
- связанный blocker report: по каждому blocked candidate — technical
  Employee/Person/source IDs, safe category и safe reason codes;
- timestamp и policy/source version identifiers;
- без полного ИИН, ФИО, raw source text, normalized payload или иных лишних
  персональных данных.

Существующий per-IIN API уже redacts input IIN to presence/last four in its response и
исполняется в `REPEATABLE READ READ ONLY`; batch API/report с этим exact output пока
не реализован. Технический отчёт не содержит полного ИИН или лишних ПДн. В защищённом
HR_HEAD interface разрешены ФИО и минимально необходимые сведения для фактического
исправления участника — только по existing RBAC и organisation scope; это не означает
их включение в технический report/export.

## 8. Acceptance criteria

Stage 0 готов к использованию только когда implementation WP докажет:

1. полное read-only сканирование выбранного source scope и детерминированную
   classification всех candidate Employees;
2. fail-closed применение всех строк §4;
3. неизменяемый frozen cohort snapshot с contract §6 и stable ordering;
4. `PREVIEW` не выполняет DML, а `FREEZE` записывает только contract metadata §6;
   ни одна операция не выполняет PPR section writes, materialization или
   Person/Employee repair;
5. отдельный safe report и accurate counts без полного ИИН/лишних PII;
6. повторяемый результат на неизменном source snapshot;
7. направляемые repair cases используют ADR-065, а не альтернативный mechanism.

## 9. Оставшиеся implementation gaps

1. Реализовать batch `PREVIEW` service/API/CLI и `FREEZE` persistence для `stage_run`,
   participant snapshots и связанного blocker report.
2. Не вызывать HTTP per-IIN endpoint циклом: выделить либо переиспользовать общий
   read-domain port/service, сохранив одинаковые fail-closed rules и safe reason codes
   для одиночного и batch preflight.
3. Реализовать утверждённые predicates batch policy, conservative pending-removal
   check, historical-link handling и structural lifecycle-path classification вместе с
   их safe codes.
4. Реализовать fresh stage-specific eligibility/freeze из базового program cohort и
   supplemental Stage 0 run без изменения исторического snapshot.

Вне scope этого WP: реализация, DDL/Alembic, DML, production execution, проектирование
Stage 1 и изменение утверждённого program plan.
