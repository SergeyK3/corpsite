# WP-PPR-MIG-002 — Этап 2: образование из контрольного списка

| Статус | **Draft — Ready for Architecture Review** |
|---|---|
| Программа | [Поэтапная миграция личных карточек](ppr-control-list-staged-migration-plan.md) |
| Предпосылки | Accepted Stage 1; frozen Stage 0 cohort; [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md); [ADR-EDU-001](../adr/ADR-EDU-001-employee-education-migration-architecture.md); [WP-CL-008](WP-CL-008-education-normalization.md) |

## 1. Цель и границы

Stage 2 переносит только подтверждённые записи об образовании в canonical
`person_education` для участников Stage 0 cohort. Обучение, сертификаты и повышение
квалификации остаются Stage 3. Этап не меняет общие сведения Stage 1, не создаёт
Employee/Person-связи и не использует import profile как read-model карточки.

Контрольный список остаётся bootstrap-источником; после принятия источником истины
является person-owned `person_education`. Canonical write выполняется только через
существующие PPR/PMF command, idempotency, provenance и `personnel_record_events`
контуры.

## 2. Подтверждённые findings

### 2.1 Source, ownership и несколько образований в одной ячейке

Источник — `HR_CONTROL_LIST` batch/row, уже однозначно привязанный Stage 0 к
`Employee → Person`. В существующем import contour образование формируется из
`education_raw`, с дополнительным контекстом `diploma_specialty_raw` и
`qualification_raw`; persisted normalized record имеет `record_kind = education`.
Он сохраняет `batch_id`, `row_id`, `employee_id`, `fragment_index`,
`source_field`, `source_text` и стабильный `source_record_key`.

`EducationNormalizationService` и legacy `parse_education_raw` поддерживают `1 row →
0..N` education fragments. Разделителями являются в том числе newline / мягкий
перенос, `;`, `|` и numbered fragments; запятая сама по себе не является разделителем.
Для каждого fragment сохраняются исходная строка и `source_fragment_index`.

**Обязательное правило Stage 2:** несколько записей в одной Excel-ячейке, в том
числе разделённые мягкими переносами, принадлежат одному Employee и одной source row.
Они создают несколько candidate/draft education records этого участника; перенос
строки никогда не означает нового сотрудника, новую строку контрольного списка или
нового участника cohort.

Shared specialty/qualification tail может быть распространён parser-ом на несколько
fragments и помечается `shared_context_ambiguous`. Такой marker не даёт права молча
принять или перезаписать canonical значение.

### 2.2 Existing canonical contour

Canonical target — `person_education`, owner `person_id`; `employee_context_id` —
контекст входа, а не владелец диплома. Вкладка карточки уже читает active,
superseded и voided person-owned records по Person. Существующие PPR commands:
`AddEducationRecord`, `UpdateEducationRecord`, `SupersedeEducationRecord`,
`VoidEducationRecord`; optimistic token — `updated_at`.

PMF уже содержит `personnel_migration_runs`, `personnel_migration_items`,
`personnel_record_events`, `EducationMigrationPlugin` и disabled education domain.
Reconciliation plugin определяет identity `(education_kind, normalized institution)`
и проверяет live canonical preconditions. Existing PPR duplicate guard также
fail-closed для active `(education_kind, institution_name)`.

## 3. Подтверждённый source → canonical mapping

Ниже приведён только mapping, подтверждённый существующими parser/service/model
контрактами. «Условно» означает, что поле допускается в proposal лишь когда parser
дал соответствующее значение без blocking issue; это не разрешение выдумывать
значение.

| Source / normalized education record | Canonical `person_education` | Правило Stage 2 | Статус |
|---|---|---|---|
| `record_kind = education`, `batch_id`, `row_id`, `employee_id`, `source_record_key`, `fragment_index`, `source_field`, `source_text`, parse/confidence | provenance: `import_batch_id`, `import_row_id`, `source_field`, `source_text`, `parse_method`, `confidence`, metadata | Сохраняются на каждой записи; `fragment_index` и source key должны остаться в metadata/provenance. | Подтверждено |
| fragment `institution` / normalized `title` (из `education_raw`) | `institution_name` | Только непустое нормализованное значение конкретного fragment. | Подтверждено |
| `specialty_text` / parsed specialty, включая контекст `diploma_specialty_raw` | `specialty` | Только для этого fragment; shared/ambiguous context требует review, пока не утверждена отдельная policy. | Подтверждено с условием |
| parsed qualification / `qualification_raw` | `qualification` | Только непустое, не-ambiguous значение конкретного fragment. | Подтверждено с условием |
| parsed full `start_date` | `started_at` | Только полная календарная дата. Год сам по себе не конвертируется в `YYYY-01-01`. | Подтверждено с условием |
| parsed full `end_date` / `issue_date` | `completed_at` | Только полная календарная дата; year-only остаётся source/provenance, пока не принято правило его canonical representation. | Подтверждено с условием |
| parsed `document_number` | `diploma_number` | Только если реально извлечён для education fragment. Текущий normalizer обычно не формирует его из пустого source. | Подтверждено с условием |
| — | `education_kind` | Нельзя выводить из одного `record_kind=education` и нельзя silently default to `basic`. | Открытое решение |
| — | `institution_type`, `document_date` | Нет подтверждённого source mapping. | Не включать |
| `education_level` | `education_kind` | Возможная будущая таблица классификации, но её нет в существующем code contract. | Открытое решение |

Следовательно, Stage 2 preview обязан исключать из proposal все неподтверждённые
поля, а не подставлять default. Если для fragment нельзя получить допустимый
`education_kind`, он не является add-ready.

## 4. Stage-specific eligibility и preview

Перед Stage 2 формируется отдельный frozen section cohort из базового Stage 0 cohort.
Для каждого участника повторно проверяются active Employee/Person pair, source
ownership, отсутствие removal/rebinding и допустимый lifecycle, как требует
программа. Затем проверяются только education records:

1. ровно один source anchor того же Employee/Person и `record_kind=education`;
2. допустимый Stage 0 batch policy и отсутствие unresolved batch removal;
3. normalized record имеет status, выбранный для Stage 2 policy; `pending`,
   `rejected`, `superseded` и неизвестный status не add-ready;
4. fragment имеет source row, source key и index, непустое institution value и все
   поля, обязательные для утверждённого `education_kind` mapping;
5. shared-context ambiguity, parse issue, person/source mismatch и stale source
   классифицируются отдельно, без записи canonical данных.

`promoted` нельзя автоматически называть «уже применено»: существующая promotion
служба ставит этот статус вместе с `promoted_document_id` в document contour, а не
доказывает наличие идентичной `person_education`. Until explicit provenance matching
is implemented, `promoted` требует отдельной classification policy, а не silent replay.

PREVIEW полностью read-only. Для HR_HEAD в разрешённом org scope он показывает:

- сотрудника и номер исходной Excel-строки, batch/row technical IDs и fragment №;
- «В контрольном списке», «Сейчас в карточке», «Будет записано» для каждого fragment;
- исходный текст fragment только в защищённом кадровом view, status текстом и safe
  reason code в раскрываемых сведениях;
- counts `готово к добавлению`, `уже существует`, `конфликт`, `нужна проверка`,
  `ошибка source`; без полного ИИН и без лишних ПДн в техническом отчёте.

## 5. Match, dedup и conflicts

Для каждого candidate надо загрузить active `person_education` этого Person и
использовать существующий education reconciliation identity: `education_kind` +
normalised `institution_name` (strip/casefold). Это согласовано с existing PPR
duplicate guard.

| Result | Правило | Preview / execution result |
|---|---|---|
| Нет identity match, данные add-ready | Создать один draft item на fragment. | `READY_TO_ADD` |
| Ровно один semantic-equal match | Canonical запись не менять; сохранить provenance decision. | `ALREADY_APPLIED` / replay |
| Ровно один identity match, но есть различия | Не перезаписывать; показать source/current field differences. | `CANONICAL_CONFLICT` — blocking |
| Более одного identity match | Не выбирать запись эвристически. | `AMBIGUOUS_CANONICAL_MATCH` — blocking |
| Дубликаты внутри одной source cell / row | Deduplicate только одинаковые fragment identity после нормализации; разные fragments остаются отдельными. | duplicate source issue либо один candidate по детерминированному policy |
| Неполный/неразобранный fragment, year-only date при required date, shared ambiguous context | Не создавать canonical запись. | `REVIEW_REQUIRED` — blocking до решения/исправления |

Stage 2 не выполняет auto-update, supersede или void existing education record в
массовом прогоне. Они имеют отдельные reconciliation actions и не являются
«заполнением пустого поля» Stage 1.

## 6. Draft/run/acceptance модель

Семантика Stage 1 переиспользуется: stage-specific frozen cohort, read-only preview,
пер-Employee последовательная обработка, `PAUSED_ON_ERROR`, resume с той же позиции,
HR_HEAD-only draft visibility, final review и atomic acceptance. Сотрудник до
acceptance читает только canonical education tab.

Однако persistence Stage 1 (`ppr_stage1_general_*`) специализирована под scalar
Person fields и не должна копироваться или использоваться для education records.
PMF `personnel_migration_runs/items` уже предоставляет per-person draft item,
provenance, commit audit и event pattern, но его текущие run statuses не представляют
frozen section-wide cohort, pause/resume и единый stage-wide acceptance. Поэтому
следующий implementation WP должен выбрать один явный orchestration owner:

- расширить общий stage-run contract поверх PMF items; либо
- создать минимальный Stage 2 run/participant/draft layer, который использует PMF
  items и PPR commands как единственный canonical write gateway.

Нельзя объявлять готовые Stage 1 tables generic implementation.

### Stop/resume

Каждый Employee обрабатывается в собственной транзакции draft-only. Ошибка fragment
или Employee откатывает только эту позицию, фиксирует safe reason и переводит run в
`PAUSED_ON_ERROR`; ранее подготовленные drafts сохраняются. Resume повторяет
остановленную позицию, не меняет предыдущие successful drafts и не добавляет duplicate
items при неизменном participant snapshot/fingerprint.

### Atomic acceptance

После полного cohort без неразрешённых blocking conflicts HR_HEAD принимает этап.
Сервер в одной SERIALIZABLE транзакции повторно проверяет cohort/source snapshots,
canonical identity/preconditions и idempotency. Затем он добавляет только
`READY_TO_ADD` records через PPR/PMF gateway, сохраняет provenance и
`EDUCATION_MIGRATED` events, а `ALREADY_APPLIED` оставляет без write. Любой stale
source, duplicate, conflict или command failure откатывает всю acceptance transaction:
ни canonical `person_education`, ни events не остаются частично записанными.

Детерминированный command ID должен включать `stage_run_id`, `stage=education`,
`employee_id`, `person_id`, participant snapshot version и fragment source key/index.
Повтор принятия accepted run — replay без новых records/events.

## 7. Visual pilot и критерии приёмки

До full run HR_HEAD проводит visual pilot минимум на:

1. сотруднике с двумя valid education fragments в одной Excel-ячейке, разделёнными
   мягким переносом: обе записи видны как два records того же сотрудника/source row;
2. сотруднике, у которого уже есть semantic-equal canonical record: нет duplicate;
3. сотруднике с visible canonical conflict или ambiguous/shared context: run
   останавливается, UI объясняет требуемую проверку и не раскрывает полный ИИН;
4. pause/resume после исправления source или решения issue;
5. acceptance: до неё employee не видит drafts; после неё вкладка показывает active
   person-owned records с provenance/events; повтор acceptance не создаёт writes.

Visual pilot должен также проверить Russian text statuses, org scope, protected
HR_HEAD source view, final report и отображение нескольких записей одного Employee.
Только после feedback HR_HEAD и принятия pilot допускается массовый Stage 2 run.

## 8. Открытые решения для implementation planning

1. Утвердить mapping `education_level → education_kind` либо явную HR review policy;
   без него Stage 2 не может add canonical record.
2. Утвердить, допускаются ли year-only source dates в canonical education и, если да,
   их модель без фиктивного дня; текущий reconciliation contour их fail-closed.
3. Утвердить policy для shared `specialty`/`qualification` context, который parser
   копирует на несколько fragments с `shared_context_ambiguous`.
4. Утвердить status/provenance policy для `approved` и `promoted` normalized records:
   document promotion не должен ошибочно считаться PPR replay.
5. Выбрать минимальную section-wide orchestration persistence для frozen cohort,
   pause/resume и atomic acceptance поверх existing PMF items; не использовать Stage 1
   scalar tables как generic storage.
6. Подтвердить, какие raw header variants фактически входят в выбранный production
   profile; WP не предполагает mapping для отсутствующих или неизвестных headers.

## 9. Вне scope

Реализация, миграции, API/UI, DML, создание Stage 2 fixtures, включение PMF domain,
изменение Stage 1 или документации Stage 0 не входят в этот WP.
