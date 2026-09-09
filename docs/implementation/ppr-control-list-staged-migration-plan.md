# Программа поэтапной миграции личных карточек из контрольного списка

**Статус:** Approved — Ready for Stage 0 Preparation
**Тип:** program-level implementation plan
**Назначение:** верхнеуровневый план последовательного переноса данных уже импортированного контрольного списка в личные карточки PPR.

## 1. Цель и границы

Программа переносит данные в PPR последовательно, по одному разделу карточки за этап. Контрольный список остаётся источником для миграции, но после успешного переноса каноническими данными остаются `Person` и person-owned PPR-разделы.

Каждый этап проходит полный самостоятельный цикл: inventory → dry-run → pilot → исправления → full run → итоговый отчёт → закрытие. Переход к следующему разделу возможен только после закрытия предыдущего.

Перед массовым прогоном каждого следующего этапа обязателен visual pilot соответствующей вкладки личной карточки и явная обратная связь пользователя; без неё массовый прогон не запускается.

Это не новый ADR и не замена существующих ADR/WP. Они остаются подчинёнными техническими документами отдельных этапов. Документ не задаёт DDL, Alembic migrations, DML-команды, production rollout или реализацию сервисов.

### В scope

- подготовка допустимости карточки и заполнение personal-card sections из ранее импортированных данных контрольного списка; этап 1 вправе materialize PPR исключительно через уже утверждённый lifecycle;
- person-owned общие сведения, образование, обучение и трудовая биография;
- dry-run, eligibility, idempotent execution, provenance, отчётность и этапные controls.

### Вне scope

- создание или изменение historical production migrations;
- массовый import файла, исправление source ETL и ручной ввод кадровых данных;
- автоматическое перезаписывание непустых отличающихся канонических данных;
- перенос без отдельного основания разделов «Кадровые приказы», «Кадровые обращения», «Адаптация», «История изменений»;
- отдельные сложные immutable/failure-audit таблицы.

## 2. Архитектурная опора

| Документ / контур | Роль в программе |
|---|---|
| [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md) | `Person` — identity anchor; `Employee` — operational shell. Миграция не подменяет эту ownership-модель. |
| [ADR-054](../adr/ADR-054-personnel-personal-record-aggregate-model.md) | PPR — logical aggregate с `Person` как root; person-owned sections не требуют отдельного `personal_record_id`. |
| [ADR-059](../adr/ADR-059-employee-centric-import-review.md) | Review import и promotion — разные обязанности: migration использует результаты уже импортированного контура, но не меняет HR review workflow. |
| [ADR-065](../adr/ADR-065-personnel-enrollment-orchestration-existing-card-repair.md) | Точный repair существующей связи Employee → Person до допуска записи в карточку. |
| [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md) | Framework для domain-by-domain promotion, source references и person-scoped PPR sections. |
| [WP-PPR-IDENTITY-001](WP-PPR-IDENTITY-001-existing-person-card-control-list-backfill.md) | Технический документ этапа 1: identity backfill, lifecycle и обычный PPR event/idempotency контур. |
| [WP-CL-006](WP-CL-006-employment-normalization.md), [WP-CL-008](WP-CL-008-education-normalization.md), [WP-CL-009](WP-CL-009-training-normalization.md) | Существующие candidate/normalization контуры; normalizing не равен canonical apply. |

Общие prerequisite для ИИН — Gate 1 и Gate 2 — считаются выполненными. Для этапа общих сведений scoped `HR_HEAD` с `PPR_IDENTITY_BACKFILL` видит полный ИИН в dedicated кадровом workflow. Дополнительный sensitive gate и отменённый сложный Gate 3 не возвращаются. Полный ИИН не попадает в логи и технические итоговые отчёты.

## 3. Карта этапов

| Этап | Раздел / результат | Existing technical basis | Условие перехода |
|---|---|---|---|
| 0 | Допуск карточек: Employee → Person, materialization, cohort | ADR-065; `app/services/adr065_person_link_service.py`; `app/personnel_lk/application/control_list_repair_preflight_service.py` | Сформирован список eligible сотрудников и зафиксированы blockers. |
| 1 | Общие сведения и `COLLECTING` | WP-PPR-IDENTITY-001; PPR identity/lifecycle ports; `ppr_command_executions` и PPR events | Pilot и full report закрыты HR_HEAD. |
| 2 | Все записи образования | `hr_import_normalized_records`; `app/control_list_import/education_normalization/`; `app/services/education_migration_plugin.py`; reconciliation education plugins | Многострочная dedup/provenance проверены. |
| 3 | Обучение, сертификаты, повышение квалификации | `app/control_list_import/training_normalization/`; `app/services/hr_import_training_date_quality_service.py`; `person_training` | Многострочная dedup/provenance проверены. |
| 4 | Трудовая биография / послужной список | `app/control_list_import/employment_normalization/`; `person_external_employment`; employment verification services | Модель биографии, источник и визуальная вкладка подтверждены отдельно от текущего назначения. |
| Далее | Родственники, воинский учёт, дополнительные сведения и иные sections | Проверяются отдельно по source inventory и person-owned model | Добавляются только при подтверждённом источнике и отдельном закрытом этапе. |

## 4. Матрица разделов и источников

| Раздел карточки | Source / normalized kinds | Canonical target | Статус в программе |
|---|---|---|---|
| Общие сведения | control-list row / normalized payload: ФИО, отдельные name fields, ИИН, birth date и иные фактически имеющиеся general fields | `persons`, identity relationship, PPR lifecycle metadata | Этап 1 |
| Кадровая связь | Existing `Employee` ↔ `Person`; verified source row | `employees.person_id` и existing person/assignment relationship | Этап 0 prerequisite, не самостоятельный массовый section apply |
| Образование | `hr_import_normalized_records`, education record kinds; `EducationCandidate` | `person_education` | Этап 2 |
| Обучение | `hr_import_normalized_records`, training/certificate kinds; `TrainingCandidate` | `person_training` | Этап 3 |
| Трудовая биография | `experience_raw` и/или подтверждённые normalized source records; `EmploymentCandidate` лишь как import projection | отдельный person-owned biography model, в том числе `person_external_employment` после подтверждения mapping | Этап 4, model/source gate |
| Трудовая деятельность | current Employee operational assignment | `employees`, assignments | Не заменяется и не смешивается с биографией |
| Родственники | source не подтверждён этой программой | `person_relatives`, если применимо | Последующий этап только при source inventory |
| Воинский учёт | source не подтверждён этой программой | `person_military_service`, если применимо | Последующий этап только при source inventory |
| Дополнительные сведения | source и canonical mapping требуют проверки | `additional_profile` / typed target по отдельному решению | Последующий этап только при source inventory |

### Различие двух трудовых вкладок

Фактическое назначение не объединяется: [ADR-056](../adr/ADR-056-employment-biography-in-ppr.md) фиксирует, что текущая вкладка «Трудовая деятельность» отображает `EmployeeOperationalAssignmentSection` и текущее operational placement. Трудовая биография — хронологические предыдущие места работы, периоды, организации и должности. Этап 4 не меняет current assignment и не использует его как замену биографии.

## 5. Единый lifecycle каждого этапа

### 5.1. Field inventory

До реализации этапа его WP фиксирует:

1. source fields, batch/row/record kinds и допустимые source statuses;
2. целевые PPR модели/таблицы и cardinality;
3. правила normalizing, transformation, dedup и conflict detection;
4. техническую provenance каждой создаваемой записи: `batch_id`, `row_id`, `normalized_record_id` либо иной существующий source reference;
5. явное исключение полей, которых в контрольном списке нет.

### 5.2. Eligibility

Запись допускается только если одновременно выполнены:

- Employee active;
- существует точная, не merged связь Employee → Person;
- source row и source record однозначны;
- source status разрешён для этапа;
- источник не удалён, не pending deletion и не re-bound;
- target не содержит непустого отличающегося значения, требующего conflict disposition.

Неeligible запись не становится ошибочным apply: она классифицируется как skip либо conflict с техническими IDs.

### 5.3. Dry-run

Dry-run сначала проходит весь зафиксированный cohort без записи canonical/PPR данных. Его
задача — выявить максимум проблем до настоящего запуска, а не обнаруживать их по мере
full run. Он возвращает по cohort:

- количество ready к переносу;
- skips и причины;
- conflicts, invalid source data и missing/rebinding states;
- уже перенесённые идемпотентные записи;
- технические IDs затронутых source/target rows.

До dry-run создаётся `stage_run_id` с его фиксированным cohort: точным списком пар
Employee/Person, стабильным порядком, позицией каждого сотрудника и fingerprint исходных
данных этапа. Dry-run проверяет именно этот snapshot; при успехе он переводит run в
`DRY_RUN_COMPLETED`. Новые сотрудники не добавляются самопроизвольно в уже начатый
прогон; они попадут только в отдельный, последующий run по явному решению.

Dry-run является основанием для решения HR_HEAD о pilot/full run, но не является
per-employee manual confirmation.

`DRY_RUN_COMPLETED` нельзя перевести в `APPROVED`, пока остаются неразобранные
blocking errors или conflicts. Допустимы только: исправление проблемы с повторным
dry-run, явное документированное исключение участника либо отмена run. Диагностическая
классификация skip в dry-run не является `SKIPPED_BY_DECISION`: последний статус
появляется только после отдельного осознанного решения «Пропустить и продолжить».

### 5.4. Pilot

Pilot использует несколько специально выбранных eligible сотрудников и включает:

1. повторный dry-run выбранного cohort;
2. визуальную проверку соответствующей вкладки личной карточки;
3. PostgreSQL-проверку canonical rows, cardinality, provenance и absence of duplicates;
4. проверку повторного запуска;
5. исправление выявленных ошибок до массового запуска.

HR_HEAD после preview/pilot подтверждает запуск этапа целиком, а не каждую отдельную запись.

### 5.5. Stage run: snapshot, состояния и подвешенный результат

Массовый запуск — это явно идентифицируемый `stage_run_id`, а не одна длительная
транзакция на весь cohort. До запуска сохраняются неизменяемый cohort, его порядок,
позиция каждого участника и stage-specific source fingerprint. Это позволяет
воспроизводимо объяснить, что именно было рассмотрено и обработано данным run.

Статусы stage run:

| Статус | Значение |
|---|---|
| `DRAFT` | Run создан, его cohort/snapshot подготовлен и ожидает dry-run. |
| `DRY_RUN_COMPLETED` | Зафиксированы результат preview, cohort, порядок и source fingerprint. |
| `APPROVED` | HR_HEAD утвердил запуск данного stage run после preview/pilot. |
| `RUNNING` | Обрабатывается текущая позиция frozen cohort. |
| `PAUSED_ON_ERROR` | Текущий сотрудник завершился ошибкой; run остановлен, позиция и техническая причина сохранены. |
| `COMPLETED_PENDING_REVIEW` | Обработан весь cohort, включая явные skips; ожидается итоговая проверка. |
| `ACCEPTED` | HR_HEAD рассмотрел итоговый отчёт и принял этап. Только это открывает следующий этап. |
| `CANCELLED` | Run прекращён до принятия; причина и состояние уже обработанных участников остаются доступными для отчёта, а сохранённые результаты не удаляются автоматически. |

Для каждого участника run сохраняется текстовый статус, а не только цветовой индикатор:

| Статус | Значение |
|---|---|
| `PENDING` | Участник ещё не обработан. |
| `COMPLETED` | Его транзакция успешно завершена. |
| `ERROR` | Его транзакция откатилась; run остановлен на этой позиции. |
| `SKIPPED_BY_DECISION` | Участник исключён из продолжения явным ответственным решением. |

После `COMPLETED` данные физически сохраняются в БД, но помечаются как результат
конкретного ещё не закрытого `stage_run_id`. До завершения всего cohort этап не
закрыт и не даёт права перехода далее. После полного cohort run становится
`COMPLETED_PENDING_REVIEW`; только после итоговой проверки уполномоченным HR_HEAD он
становится `ACCEPTED`. Ошибка следующего этапа не отменяет и не переоткрывает ранее
принятый этап.

### 5.6. Draft visibility незавершённого этапа

До `ACCEPTED` сохранённый результат участника — черновой результат его `stage_run_id`.
HR_HEAD видит его для проверки; сотрудник не видит сведения данного этапа до
`ACCEPTED`. После `ACCEPTED` сведения этапа доступны сотруднику по обычным правилам
доступа. Ранее принятые этапы остаются видимыми независимо от состояния следующего
этапа. В интерфейсе видимость и статус обозначаются текстом, а не только цветом.

Статический finding текущего PPR read-path: lifecycle `COLLECTING` передаётся в
read-model как metadata, а `assert_ppr_read_allowed_for_person` и
`assert_ppr_read_allowed_for_employee` применяют RBAC и organisation scope без
проверки lifecycle или `stage_run_id`. Следовательно, `COLLECTING` сам по себе не
обеспечивает требуемое разделение видимости по этапам. Будущий technical stage WP
обязан до apply определить и проверить явный read/visibility control для draft
stage results, HR_HEAD review и employee visibility после acceptance. Этот план не
задаёт DDL или реализацию такого контроля.

При `CANCELLED` уже сохранённые результаты не удаляются автоматически: они остаются
черновыми и недоступными сотруднику. Они должны быть либо продолжены в явно связанном
replacement run, либо урегулированы отдельным контролируемым rollback/disposition
решением будущего WP. Универсальный rollback данным планом не проектируется.

### 5.7. Full run, остановка и продолжение

Full run обрабатывает только frozen cohort конкретного этапа:

- отдельный feature flag или явный enable/run control обязателен для каждого этапа;
- один Employee/Person обрабатывается в собственной короткой транзакции;
- успешная транзакция сохраняет результат и связывает его с текущим `stage_run_id`;
- command/idempotency fingerprint и PPR event-механизмы используются повторно;
- повторный запуск не создаёт duplicate multi-row records;
- непустые отличающиеся canonical values никогда автоматически не перезаписываются:
  они остаются conflicts в отчёте.

Для команды обработки необходим детерминированный `command_id`, образованный из
`stage_run_id`, stage, технического Employee/Person ID и participant snapshot version.
Повтор команды с тем же fingerprint — это replay, а не новая запись. Если исходные
данные изменились, новый fingerprint обязан пройти повторную eligibility/dry-run
проверку; система не должна незаметно применять прежний результат.

Во время выполнения оператору показываются текстом, а не только цветом: номер и
статус run, этап, `N` обработанных из `M`, текущий сотрудник (в разрешённом кадровом
интерфейсе), точка остановки, безопасный код и описание ошибки, а также счётчики
`COMPLETED`, `ERROR` и `SKIPPED_BY_DECISION`. Экран выполнения и технический отчёт не
содержат полный ИИН или лишние персональные данные.

Ошибка текущего сотрудника откатывает только его транзакцию. Результаты ранее
успешно обработанных сотрудников остаются сохранёнными, но run немедленно
останавливается в `PAUSED_ON_ERROR`. Вместе с позицией фиксируется техническая
причина остановки.

После остановки оператор анализирует проблему и исправляет единичный случай вручную
либо повторяющуюся проблему программно. Frozen cohort и порядок не меняются. Исходный
snapshot проблемного участника сохраняется в истории; после исправления создаётся
новая participant snapshot version только этого участника и рассчитывается новый
fingerprint. Eligibility и dry-run повторяются только для этой позиции. При успехе
создаётся новый детерминированный `command_id`, после чего тот же `stage_run_id`
сначала повторно обрабатывает сотрудника на error-позиции и лишь затем — следующего.
Ранее `COMPLETED` участники не изменяются повторно; идемпотентность предотвращает
дублирование.

Точечное исправление участника в рамках прежних mapping, migration policy и frozen
cohort не требует повторного `APPROVED` всего run. Результат точечной повторной
проверки сохраняется в аудите и итоговом отчёте. Изменение cohort, порядка, mapping,
migration policy или набора переносимых полей требует нового dry-run и нового
`APPROVED`; такие изменения нельзя незаметно внести в уже утверждённый run.

Автоматически пропускать проблемного сотрудника и продолжать нельзя. Разрешено только
явное действие «Пропустить и продолжить», которое создаёт `SKIPPED_BY_DECISION` и
обязательно хранит причину, пользователя, дату/время и технический Employee/Person ID.
Такое исключение включается в итоговый отчёт; наличие skip не означает автоматического
принятия этапа и должно быть явно рассмотрено HR_HEAD.

### 5.8. Итоговый отчёт

Итог этапа содержит `stage_run_id`, source fingerprint, frozen cohort size и counts:
найдено, перенесено, already existed, skipped, conflict и error. Для каждой error или
`SKIPPED_BY_DECISION` позиции отчёт включает технический ID, позицию run, text status,
техническую classification и, для skip, decision metadata. ФИО, полный ИИН, raw source
text и иные избыточные персональные данные не дублируются в техническом отчёте.

### 5.9. Закрытие и переход

Следующий этап запрещён до фиксации всех пунктов:

1. локальные tests для stage-specific field rules, dry-run, apply/idempotency и conflicts;
2. завершённый pilot и устранённые defects;
3. production dry-run и review итогового preview;
4. явное утверждение запуска HR_HEAD;
5. production full run до `COMPLETED_PENDING_REVIEW`;
6. контрольная выборка карточек и PostgreSQL evidence;
7. сохранённый final report, commit/deployment/result reference;
8. явное `ACCEPTED` от HR_HEAD с рассмотрением всех conflicts и
   `SKIPPED_BY_DECISION`.

## 6. Детализация этапов

### Этап 0. Подготовка карточек

Цель — сформировать cohort и определить допустимость карточки, а не переносить section
data. Проверяются active Employee, `employees.person_id`, Person status и допустимый
путь materialization PPR. Отсутствующие или некорректные связи Employee → Person
исправляются только через уже реализованный ADR-065 contour. Сотрудники без Person, с
ambiguous identity, deleted/rebinding source или без разрешённого lifecycle пути
materialization включаются в preflight report, но не в migration cohort.

### Этап 1. Общие сведения

Переносятся подтверждённые ФИО и отдельные фамилия/имя/отчество, ИИН, дата рождения и другие general fields, которые действительно присутствуют в control-list source. Technical basis — WP-PPR-IDENTITY-001. Этап 1 может materialize PPR только через уже утверждённый lifecycle и при выполнении его established criteria, после чего PPR переводится в `COLLECTING`; программа не создаёт собственного альтернативного механизма materialization и это не заявление о полноте всей карточки.

### Этап 2. Образование

Один Person может иметь несколько education records. Existing `EducationNormalizationService` и `EducationCandidate` дают source decomposition/provenance, а existing promotion/PMF and reconciliation education contours — техническую основу для последующего canonical apply. Approval education не является approval общих сведений: section имеет свой lifecycle и отчёт.

### Этап 3. Обучение и повышение квалификации

Один Person может иметь несколько records: courses, certificates, qualifications and other actually present training types. `TrainingNormalizationService` сохраняет fragment-level context; canonical target — `person_training`. Dedup key и граница между одинаковой повторной записью и разными курсами одного Person должны быть зафиксированы в stage WP до pilot.

### Этап 4. Трудовая биография / послужной список

Переносятся previous employers, periods, organizations, positions and deterministic ordering. Этап обязан отдельно классифицировать missing/partial dates и overlapping periods. До реализации требуется подтвердить source mapping и target semantics для person-owned biography; current assignment, «Трудовая деятельность» и biography не объединяются автоматически.

### Последующие этапы

Для relatives, military registration, additional details и других tabs сначала выполняется отдельный source inventory. Если control list не содержит достоверного источника, section исключается из автоматической миграции. Появление existing target table само по себе не является основанием для автоматического переноса.

## 7. Открытые вопросы

| Вопрос | Требуемое решение до соответствующего этапа |
|---|---|
| Какие конкретные general fields, кроме заданных, надёжно присутствуют в source? | Field inventory этапа 1 с mapping и null/conflict policy. |
| Какая canonical dedup/provenance shape для education и training? | Этапы 2–3 WP должны подтвердить existing PMF/promotion contract и record identity. |
| Какой source и typed mapping для трудовой биографии, включая `experience_raw`? | Этап 4 architecture review; не подменять biography operational assignment. |
| Имеются ли в control list надёжные данные родственников, воинского учёта и additional profile? | Отдельная source inventory до включения каждого section в roadmap. |
| Какие feature flags/run controls уже подходят для stage execution? | Выбрать existing control или минимально определить явный control в technical WP; не включать этап неявно. |

## 8. Техническое состояние вне scope

- `corpsite_test` восстановлена до Alembic head `m1n2o3p4q5r6`;
- `h5`, `i6` и `db/init/020` возвращены к `HEAD`;
- старые Gate 3 files удалены и не восстанавливаются;
- `PermissionError` в `%LOCALAPPDATA%\Temp\pytest-of-Sergei` — внешний локальный pytest blocker, не ошибка БД и не часть архитектуры этой программы.

Эти сведения не изменяют scope этапов и не требуют действий в рамках данного документа.
