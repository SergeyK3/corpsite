# WP-PPR-MIG-002 — Этап 2: образование из контрольного списка

| Статус | **Approved — Ready for Stage 2 Implementation Planning** |
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

### 2.2 Read-only inventory локального control-list workbook

Read-only inspected file: `контрольный июнь.xlsx` в корне локальной рабочей области
(дата файла 2026-06-16). Анализировал только education columns с заголовком варианта
«ВУЗ / учебное заведение, год окончания» на шести roster sheets. Ни ФИО, ни ИИН, ни
полный source text не сохранялись в документе, логах repository или fixture.

| Обезличенный класс формулировки / структуры | Количество source cells | Предлагаемый результат Stage 2 |
|---|---:|---|
| Непустые education cells в проверенном scope | 729 | Scope inventory, не cohort count. |
| Явный marker интернатуры | 104 | Пример класса для `internship` policy branch. |
| Явный marker резидентуры или ординатуры | 77 | Пример класса для `residency` policy branch. |
| Явный marker магистратуры / магистра | 3 | Пример класса для `masters` policy branch. |
| Явный marker PhD / доктор наук / к.м.н. | 0 | В локальном файле нет примера; ветка `phd` обязана иметь synthetic test. |
| Лексема «высш…» | 113 | Не является достаточным видом образования: может быть частью названия учреждения. `REVIEW_REQUIRED`. |
| Лексема «средн…» | 1 | Не является достаточным видом образования. `REVIEW_REQUIRED`. |
| Marker колледжа | 264 | Указывает на тип/название учреждения, не на `education_kind`. `REVIEW_REQUIRED`. |
| Marker университета / академии / института | 266 | Указывает на учреждение, не на `education_kind`. `REVIEW_REQUIRED`. |
| Обычная или не классифицированная дипломная формулировка без advanced marker | 602 | `REVIEW_REQUIRED`; default запрещён. |
| Несколько explicit advanced markers в одной ячейке | 57 | Сначала fragment-level split; неразделимые или конфликтующие markers — `REVIEW_REQUIRED`. |
| Ячейки с мягким переносом | 37 | Все остаются одной source row/Employee. |
| Мягкий перенос с явно нумерованными несколькими records | 1 | Обязательный visual-pilot class: несколько fragments одной source row, не новые сотрудники. |
| Мягкий перенос без надёжной нумерованной границы | 36 | Сохранить fragment indices; не объединять и не трактовать как новые rows; `REVIEW_REQUIRED`, если parser не отделил records. |

57 cells с несколькими markers могут содержать несколько корректных education
fragments, а не одну конфликтную запись: решение принимается только после
fragment-level parsing и применения policy к каждому fragment.

### 2.3 Enum и фактический `education_level`

Canonical enum `EDUCATION_KINDS` содержит только `basic`, `internship`, `residency`,
`masters`, `phd`, `other`. `EducationNormalizationService` извлекает из текста
`education_level` только лексемы `высшее`, `среднее`, `послевузовское`, `базовое`.
Этот parser не содержит mapping этих лексем в canonical enum.

`education_level` не persisted в Excel как отдельный controlled field и отсутствует в
локальной `corpsite_test` (строк с `education_raw` и normalized
`record_kind=education` там также 0). Legacy profile service выводит отдельные
`record_type` по keywords internship/residency/masters/phd и иначе default-ит в
`basic`; этот legacy default не используется Stage 2: применяется только policy ниже.

### 2.4 Утверждённая versioned policy `EDU-KIND-ALLOWLIST-v1`

Классификация выполняется для каждого уже отделённого fragment, а не для всей Excel
ячейки. Более конкретный marker имеет приоритет над общим уровнем. Два или больше
противоречивых конкретных markers в одном неразделимом fragment блокируют automatic
classification.

| Fragment marker / condition | `education_kind` result |
|---|---|
| `интернатура` или `врач-интерн` | `internship` |
| `резидентура` или `ординатура` | `residency` |
| `магистратура` или `магистр` | `masters` |
| `PhD`, `докторантура` или `доктор философии` | `phd` |
| Явная формулировка уровня `высшее`, `среднее специальное`, `техническое и профессиональное`, `базовое образование`; либо обычный дипломный fragment без явного marker последипломного уровня | `basic` |
| `послевузовское` без уточнения; неразделимые конфликтующие конкретные markers; иная неоднозначная формулировка | `REVIEW_REQUIRED` |
| Candidate `other` | Никогда не назначается автоматически; только явным решением HR с reason и audit. |

Лексемы, являющиеся частью имени учреждения (например, «высший … колледж»), не
считаются явной формулировкой уровня без контекста. If fragment contains `ординатура`
и общий marker `послевузовское`, применяется более конкретный `residency`; если
одновременно присутствуют неразделимые `интернатура` и `резидентура`, результат —
`REVIEW_REQUIRED`.

### 2.5 Existing canonical contour

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
| parsed full `end_date` / `issue_date` | `completed_at` | Только полная календарная дата; year-only сохраняется в provenance без canonical date. | Подтверждено с условием |
| parsed `document_number` | `diploma_number` | Только если реально извлечён для education fragment. Текущий normalizer обычно не формирует его из пустого source. | Подтверждено с условием |
| `EDU-KIND-ALLOWLIST-v1` marker classification | `education_kind` | Классифицировать только per-fragment по §2.4; сохранять policy version и outcome. | Утверждено |
| — | `institution_type`, `document_date` | Нет подтверждённого source mapping. | Не включать |
| `education_level` | `education_kind` | Возможная будущая таблица классификации; до её утверждения automatic mapping отсутствует. | Не включать |

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
3. `approved` normalized record допускается при выполнении остальных проверок;
   `pending`, `rejected`, `superseded` и неизвестный status не add-ready;
4. fragment имеет source row, source key и index, непустое institution value и
   `education_kind` из `EDU-KIND-ALLOWLIST-v1`;
5. shared-context ambiguity, parse issue, person/source mismatch и stale source
   классифицируются отдельно, без записи canonical данных.

`promoted` считается `ALREADY_APPLIED` только при точном match active canonical record
и его import provenance с тем же source batch/row/key/fragment. Existing promotion
service сама по себе такого PPR match не доказывает: при отсутствии точного evidence
`promoted` классифицируется `REVIEW_REQUIRED`, а не silent replay.

PREVIEW полностью read-only. Для HR_HEAD в разрешённом org scope он показывает:

- сотрудника и номер исходной Excel-строки, batch/row technical IDs и fragment №;
- «В контрольном списке», «Сейчас в карточке», «Будет записано» для каждого fragment;
- исходный текст fragment только в защищённом кадровом view, text status, policy
  version/classification outcome и safe reason code в раскрываемых сведениях;
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
| Точные повторы fragments внутри одной source row | Не объединять и не удалять похожие fragments автоматически; сохранить все source fragment indices. | `DUPLICATE_SOURCE_FRAGMENT` — blocking review для HR |
| Неполный/неразобранный fragment или shared ambiguous context | Не создавать canonical запись. | `REVIEW_REQUIRED` — blocking до решения/исправления |

Stage 2 не выполняет auto-update, supersede или void existing education record в
массовом прогоне. Они имеют отдельные reconciliation actions и не являются
«заполнением пустого поля» Stage 1.

## 6. Draft/run/acceptance модель

Семантика Stage 1 переиспользуется: stage-specific frozen cohort, read-only preview,
пер-Employee последовательная обработка, `PAUSED_ON_ERROR`, resume с той же позиции,
HR_HEAD-only draft visibility, final review и atomic acceptance. Сотрудник до
acceptance читает только canonical education tab.

Оркестрация создаёт тонкий общий PPR stage-run envelope поверх existing PMF
`personnel_migration_runs/items`. Envelope — единственный владелец frozen cohort,
участников, position cursor, pause/resume, итоговой проверки и stage acceptance.
PMF остаётся единственным владельцем education draft items, their source/draft payload,
provenance и canonical commands. Envelope хранит только IDs, status/cursor, snapshot
versions и safe fingerprints; он не дублирует education payload.

Persistence Stage 1 (`ppr_stage1_general_*`) специализирована под scalar Person
fields и не расширяется и не используется Stage 2.

### Единственный владелец статусов и переходы

Envelope владеет aggregate status и participant execution status. PMF run/item status
не дублирует stage lifecycle: до acceptance item остаётся `draft`; только после
успешного commit атомарной acceptance он становится `committed`. При rollback canonical
acceptance PMF items остаются `draft`. Canonical command status принадлежит existing
PPR idempotency store, а не envelope.

| Envelope status | Допустимый переход | Значение |
|---|---|---|
| `DRAFT` | → `DRY_RUN_COMPLETED`, `CANCELLED` | Создано намерение run; canonical write нет. |
| `DRY_RUN_COMPLETED` | → `APPROVED`, `CANCELLED` | Read-only preview завершён для всего frozen cohort. Blocking errors/conflicts запрещают `APPROVED`, кроме явного `SKIPPED_BY_DECISION`. |
| `APPROVED` | → `RUNNING`, `CANCELLED` | HR_HEAD разрешил draft execution по неизменным cohort/policy/mapping snapshot. |
| `RUNNING` | → `PAUSED_ON_ERROR`, `COMPLETED_PENDING_REVIEW`, `CANCELLED` | Последовательная подготовка draft items. |
| `PAUSED_ON_ERROR` | → `RUNNING`, `CANCELLED` | После исправления повторяется та же position. |
| `COMPLETED_PENDING_REVIEW` | → `ACCEPTED`, `PAUSED_ON_ERROR`, `CANCELLED` | Все participants завершены или осознанно исключены; HR_HEAD проверяет итог. |
| `ACCEPTED` / `CANCELLED` | terminal | `ACCEPTED` не запускает commands повторно; `CANCELLED` не удаляет PMF drafts автоматически. |

Participant statuses принадлежат только envelope: `PENDING`, `COMPLETED` (его PMF
draft items подготовлены, но ещё не canonical), `ERROR`, `SKIPPED_BY_DECISION`.
Последний требует причины, actor, времени и technical Employee ID и остаётся видимым
HR_HEAD в итоговом отчёте.

### Stop/resume

Каждый Employee обрабатывается в собственной транзакции draft-only. Ошибка fragment
или Employee откатывает только эту позицию, фиксирует safe reason и переводит run в
`PAUSED_ON_ERROR`; ранее подготовленные drafts сохраняются. Resume повторяет
остановленную позицию, не меняет предыдущие successful drafts и не добавляет duplicate
items при неизменном participant snapshot/fingerprint.

### Snapshot, stale protection и locks

У participant snapshot fingerprint входит canonical JSON без ФИО, полного ИИН и raw
source payload: `stage_run_id`, Stage 0 participant/source fingerprint,
Employee/Person IDs и versions, batch/row IDs, selected normalized-record IDs,
`source_record_key` и `fragment_index`, review status, source/normalized update tokens,
PPR lifecycle version, `education_kind_policy_version=EDU-KIND-ALLOWLIST-v1`,
classification outcome, parser/mapping versions, а также active canonical education
identity и `updated_at` tokens. PMF item payload хранится только в PMF и
связан с envelope через IDs.

Worker, resume и acceptance используют единственный lock order: envelope run →
participant → source rows (включая selected normalized records, по technical ID) →
Employee → Person → active canonical `person_education` (по `education_id`) → PMF
runs/items → existing PPR locks. Acceptance использует `SERIALIZABLE`; worker/resume
использует тот же порядок в scope одной position. Это устраняет инверсию lock order.

Если source, ownership, policy fingerprint, Person/Employee/PPR version или canonical
identity меняются, preview/final check возвращает text safe stale/conflict reason.
Drafts сохраняются, но envelope переходит в `PAUSED_ON_ERROR`; canonical writes не
выполняются. Resume возможен только после новой проверки той же позиции. Изменение
cohort, order, mapping/policy или field set требует нового preview и нового
`APPROVED`, а не resume старого run.

### Atomic acceptance

После полного cohort без неразрешённых blocking conflicts HR_HEAD принимает этап.
Сервер в одной SERIALIZABLE транзакции повторно проверяет cohort/source snapshots,
canonical identity/preconditions и idempotency. Затем он добавляет только
`READY_TO_ADD` records через PPR/PMF gateway, сохраняет provenance и
`EDUCATION_MIGRATED` events, а `ALREADY_APPLIED` оставляет без write. Любой stale
source, duplicate, conflict или command failure откатывает всю acceptance transaction:
ни canonical `person_education`, ни events, ни изменения PMF item status не остаются
частично записанными; PMF items остаются `draft`.

После rollback отдельная короткая служебная transaction блокирует только envelope
run/остановленного participant и фиксирует `PAUSED_ON_ERROR` с safe reason code и
technical diagnostic reference. Она не записывает failed PMF item внутри уже
откаченной acceptance transaction и не меняет canonical/source data.

Детерминированный command ID должен включать `stage_run_id`, `stage=education`,
`employee_id`, `person_id`, participant snapshot version и fragment source key/index.
Повторный acceptance сначала блокирует envelope. Для `ACCEPTED` он возвращает уже
зафиксированный outcome без PMF/PPR command. Для любой иной stale/conflict проверки
вся transaction откатывается; deterministic PPR command IDs дополнительно делают
повтор того же accepted command replay без новых records/events.

### Видимость

До `ACCEPTED` PMF education drafts и source/current/proposal comparison доступны только
HR_HEAD с нужным permission и org scope; employee read paths используют только active
canonical `person_education`. После `ACCEPTED` новые canonical records отображаются
сотруднику по обычным правилам доступа к карточке. Ранее принятые sections не скрываются
из-за `DRAFT`, `RUNNING` или `PAUSED_ON_ERROR` этого Stage 2 envelope. UI показывает
status и visibility текстом, а не только цветом.

PMF provenance для каждого draft/committed item дополнительно содержит
`education_kind_policy_version`, classifier outcome, selected canonical kind и safe
reason code (если есть); raw marker text не дублируется в envelope.

## 7. Visual pilot и критерии приёмки

До full run HR_HEAD проводит visual pilot минимум на:

1. сотруднике с двумя valid education fragments в одной Excel-ячейке, разделёнными
   мягким переносом: обе записи видны как два records того же сотрудника и остаются
   связанными с одной исходной Excel-строкой (различаются только fragment index);
2. сотруднике, у которого уже есть semantic-equal canonical record: нет duplicate;
3. сотруднике с visible canonical conflict или ambiguous/shared context: run
   останавливается, UI объясняет требуемую проверку и не раскрывает полный ИИН;
4. pause/resume после исправления source или решения issue;
5. acceptance: до неё employee не видит drafts; после неё вкладка показывает active
   person-owned records с provenance/events; повтор acceptance не создаёт writes.

Visual pilot должен также проверить Russian text statuses, org scope, protected
HR_HEAD source view, final report и отображение нескольких записей одного Employee.
Только после feedback HR_HEAD и принятия pilot допускается массовый Stage 2 run.

### Policy test criteria

Implementation tests обязаны покрыть каждый результат `EDU-KIND-ALLOWLIST-v1`:

1. `интернатура` и `врач-интерн` → `internship`;
2. `резидентура` и `ординатура` → `residency`;
3. `магистратура` и `магистр` → `masters`;
4. `PhD`, `докторантура`, `доктор философии` → `phd` (synthetic, поскольку в
   локальной inventory count равен нулю);
5. каждый basic branch: явный общий уровень и ordinary diploma fragment;
6. `послевузовское` без уточнения, каждый conflict of specific markers и ambiguous
   wording → `REVIEW_REQUIRED`;
7. `other` нельзя получить без explicit HR decision;
8. specific marker побеждает общий level marker;
9. soft-line-break pilot из inventory: два fragments одной Excel row имеют разные
   indices, один Employee/Person и не становятся двумя control-list rows;
10. fingerprint/provenance/preview содержат `EDU-KIND-ALLOWLIST-v1`, а изменение
    policy version делает approved preview stale и требует нового preview/approval.

## 8. Architecture Review record

2026-09-09 Architecture Review утвердил `EDU-KIND-ALLOWLIST-v1`, thin common stage-run
envelope over PMF и правила rollback/служебной pause transaction. WP переведён в
`Approved — Ready for Stage 2 Implementation Planning`.

Отсутствие полной даты само по себе не блокирует Stage 2 record: canonical
`person_education.started_at` и `completed_at` nullable, а PPR add handler требует
только valid `education_kind`. Год сохраняется в provenance и не превращается в
`01.01`. Existing reconciliation add gate сейчас stricter (блокирует incomplete/both
missing dates); implementation planning должно привести его execution path в
соответствие с этой утверждённой Stage 2 policy, не меняя canonical дату.

Остаются только implementation gaps: thin envelope schema/API/RBAC/tests, exact
provenance comparator для `promoted`, и deterministic parser/profile version capture.

## 9. Вне scope

Реализация, миграции, API/UI, DML, создание Stage 2 fixtures, включение PMF domain,
изменение Stage 1 или документации Stage 0 не входят в этот WP.
