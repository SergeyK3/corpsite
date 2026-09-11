# WP-PPR-MIG-005A — Семантика статусов матрицы миграции

| Параметр | Значение |
|---|---|
| Статус | **Approved — Ready for WP-PPR-MIG-005B** |
| Родительский документ | [WP-PPR-MIG-005](WP-PPR-MIG-005-migration-status-matrix-plan.md) |
| Назначение | Детерминированный контракт статуса для одной пары `Person × section`. |
| Не входит в scope | DDL, модели, сервисы, API, UI, миграция данных, изменение permissions. |

## 1. Нормативные термины и scope v1

**Ячейка** — пара активного `person_id` и одного section. Статус вычисляется только сервером из безопасных технических фактов; UI всегда показывает русский текст статуса и русский текст причины, а не только цвет.

В v1 входят только:

| Section | Домен / факты |
|---|---|
| `general` | Stage 1, `persons`, `employees`, `hr_import_rows`, Stage 0 cohort, event `PPR_STAGE1_GENERAL_ACCEPTED` |
| `education` | Stage 2, `ppr_stage_runs`, `ppr_stage_run_participants`, PMF, `person_education` |
| `training` | Stage 3, `ppr_stage_runs`, `ppr_stage_run_participants`, PMF, `person_training` |

`family`, `military`, `employment_biography`, `additional`, `intended_employment`, `assignment`, `orders`, `applications`, `onboarding`, `changes` не входят в v1. Для них матрица **не создаёт и не отображает фиктивный миграционный статус**; они отсутствуют как columns v1, а не получают `NOT_STARTED`.

**Active universe** — один явно выбранный для отчёта `ppr_stage0_cohort_runs` BASE run плюс только явно подключённые к нему supplemental cohorts. «Последний по времени» run активным cohort не делает. Смена active universe создаёт новую область отчёта и не переписывает историю предыдущего.

## 2. Канонический классификатор

Во всех строках «аннулируют» означает: при событии ячейка заново проходит дерево из §3; прежний результат не удаляется из аудита.

| Статус / текст | Точное назначение и обязательные факты | Допустимые reason codes | Конечный | Аннулируют |
|---|---|---|---|---|
| `NOT_STARTED` — «Не начато» | Person является participant активного cohort; нет актуального section-specific candidate/run/manual result, и нет сильнейшего условия ниже. | `RUN_NO_SECTION_RESULT`, `RUN_NOT_YET_STARTED` | Нет | создание preview/run, blocker, source/binding/policy change |
| `PROCESSING` — «Обрабатывается» | Есть выбранный актуальный participant в non-terminal execution run (`APPROVED`, `RUNNING`; для Stage 1 также `DRY_RUN_COMPLETED` после approve workflow). | `RUN_APPROVED`, `RUN_RUNNING` | Нет | completion, pause/error, cancel, invalidation |
| `AUTO_READY` — «Готово к согласованию» | Есть актуальный preview либо participant result без conflict/error; он завершён и ожидает acceptance. Для Stage 1 participant обязан быть `COMPLETED`; для Stage 2/3 — run `COMPLETED_PENDING_REVIEW` и participant `COMPLETED`. | `RUN_PREVIEW_READY`, `RUN_COMPLETED_PENDING_REVIEW` | Нет | acceptance, source/canonical/binding/policy change, новый conflict |
| `REVIEW_REQUIRED` — «Требуется ручная проверка» | Доступный для person section source/candidate содержит предметный конфликт, ambiguous identity/fragment или обязательную неполноту, устранимую кадровым решением. | `CONFLICT_NAME_PARSE`, `CONFLICT_CANONICAL_VALUE`, `CONFLICT_EDUCATION_IDENTITY`, `CONFLICT_TRAINING_IDENTITY`, `SOURCE_FRAGMENT_UNREVIEWED` | Нет | approved correction и новый preview; source/binding change; policy change |
| `CORRECTED_BY_HR` — «Исправлено кадровиком, требуется перепроверка» | Есть актуальный будущий audited manual-correction event (§4), относящийся к исходному section result; after hash совпадает с текущими facts, но новый machine validation/acceptance ещё не выполнен. | `MANUAL_CORRECTION_PENDING_RECHECK` | Нет | successful recheck (`AUTO_READY`/`ACCEPTED`), любой fingerprint mismatch, revoke/supersede correction |
| `ACCEPTED` — «Согласовано» | Есть конкретный participant-level accepted evidence и подтверждённый canonical target outcome; все текущие fingerprints совпадают. Run-level `ACCEPTED` без participant evidence недостаточен. Пустой `general` никогда не получает этот статус. | `RUN_PARTICIPANT_ACCEPTED` | Да, условно | source/canonical/binding/cohort/policy fingerprint mismatch; later manual correction |
| `NO_SOURCE_DATA` — «Нет исходных данных» | Person в active cohort, binding валиден, а section-specific source отсутствует; это не ошибка и не утверждённое «не применимо». | `SOURCE_GENERAL_MISSING`, `SOURCE_EDUCATION_MISSING`, `SOURCE_TRAINING_MISSING` | Да, условно | появление source, binding/cohort/policy change |
| `NOT_APPLICABLE` — «Не применимо» | Есть актуальное, аудируемое и policy-allowed решение, что section не применим, с reason и actor; отсутствие записей само по себе недостаточно. | `POLICY_NOT_APPLICABLE_APPROVED`, `MANUAL_NOT_APPLICABLE_APPROVED` | Да, условно | revoke/supersede decision, source/binding/policy change |
| `BLOCKED` — «Заблокировано» | Невыполнена safety prerequisite: inactive/merged person, invalid employee→person→source row anchor, ambiguous source anchor, cohort out-of-scope/inactive или non-materializable PPR path. | `BINDING_PERSON_MISSING`, `BINDING_PERSON_INACTIVE`, `BINDING_EMPLOYEE_LINK_STALE`, `BINDING_SOURCE_ANCHOR_AMBIGUOUS`, `BINDING_COHORT_MISMATCH`, `SOURCE_BATCH_PENDING_REMOVALS`, `POLICY_MATERIALIZATION_BLOCKED` | Нет | исправление prerequisite; новый active cohort |
| `STALE` — «Требуется обновление» | Ранее был section result/manual correction/accepted evidence, но его stored fingerprint не совпадает с текущими facts; prerequisites по-прежнему валидны. | `FINGERPRINT_SOURCE_CHANGED`, `FINGERPRINT_TARGET_CHANGED`, `FINGERPRINT_BINDING_CHANGED`, `FINGERPRINT_COHORT_CHANGED`, `FINGERPRINT_POLICY_CHANGED` | Нет | новый актуальный preview/recheck/acceptance; устранение blocker |
| `ERROR` — «Ошибка обработки» | Выбранный актуальный participant/run остановлен безопасной технической ошибкой, без более сильного blocker/stale/review condition. | `RUN_EXECUTION_ERROR`, `RUN_ACCEPTANCE_PAUSED`, `RUN_PARTICIPANT_ERROR` | Нет | retry/new run, cancel, source/binding/policy change |

Конечные статусы условны: они окончательны только для текущего fingerprint и active cohort.

## 3. Детерминированное дерево решений

### 3.1. Нормализация фактов и выбор результата

1. Вход: `(active_cohort_id, person_id, section)`; если section не v1 — ячейка не создаётся.
2. Найти `employee_id` participant активного cohort для person. Если participant не найден, искать blocker активного cohort, привязанный к person/employee/source anchor.
   - есть идентифицируемый blocker → `BLOCKED`;
   - person присутствует среди eligibility universe active source batch, но не был participant и blocker к нему не может быть однозначно привязан → `NOT_STARTED`/`RUN_NOT_YET_STARTED` (он ещё не включён, а не «вне cohort»);
   - person вообще вне active cohort universe → строка не входит в матрицу этого cohort и ячейка **не вычисляется**. Это не `NOT_STARTED`.
3. Для participant собрать section-specific candidates только из runs, ссылающихся на active cohort (или утверждённый supplemental). Отбросить `CANCELLED` runs: они не могут заменить или уничтожить более ранний действующий result.
4. Для каждого candidate вычислить current fingerprint. Candidate актуален только при совпадении stored/current fingerprint и текущем valid binding. Для Stage 1 fingerprint participant (`source_fingerprint` плюс current canonical/binding/policy facts), для Stage 2/3 — participant/run snapshot fingerprint плюс section fingerprint (§5).
5. Выбрать result: сначала наиболее поздний **актуальный participant-level** run по `accepted_at`, иначе `completed_at`, иначе `created_at`; при равенстве — наибольший run id. Более поздний candidate с `CANCELLED` игнорируется. Более поздний candidate с mismatch не «прячет» ранний accepted result: mismatch даёт `STALE` только если он относится к тому же active facts; иначе ранний актуальный accepted остаётся выбранным.

### 3.2. Дерево (строгий порядок)

```text
if section not in V1: no cell
if person outside active cohort universe: no row/cell
if active-cohort blocker or invalid binding/materialization: BLOCKED
if accepted/manual/result evidence exists and its fingerprint mismatches current facts: STALE
if current selected candidate has actionable source/canonical conflict: REVIEW_REQUIRED
if current approved manual-correction event is valid and no post-correction recheck: CORRECTED_BY_HR
if current selected candidate has safe technical error/pause: ERROR
if current participant has accepted evidence AND canonical outcome proof: ACCEPTED
if current approved not-applicable decision: NOT_APPLICABLE
if section source is conclusively absent: NO_SOURCE_DATA
if current selected candidate is completed pending acceptance or preview-ready: AUTO_READY
if current selected candidate is approved/running: PROCESSING
else: NOT_STARTED
```

This order intentionally gives `BLOCKED` priority over all results, then `STALE`; a stale acceptance never appears accepted. A current factual conflict wins over a manual correction awaiting a recheck. `ERROR` is lower than correction because a valid correction explicitly supersedes the faulty attempt. `ACCEPTED` is participant-specific: Stage 1 run `ACCEPTED` qualifies only when the same person’s Stage-1 participant is `COMPLETED`, its current fingerprint matches, and `PPR_STAGE1_GENERAL_ACCEPTED` evidence/canonical write exists. Stage 2/3 require that participant’s `COMPLETED`/PMF outcome and matching canonical records, not just run `ACCEPTED`.

## 4. Будущий строгий контракт `CORRECTED_BY_HR`

Такого универсального события в системе сейчас **нет**. Требуемый будущий audit event (название предлагается: `PPR_SECTION_MANUAL_CORRECTED`) создаётся системой только после успешного commit ручной коррекции; кадровик не создаёт его отдельным действием. Event обязан содержать:

| Атрибут | Контракт |
|---|---|
| Автор | System emitter сохраняет actor успешного manual commit. Сам commit доступен только пользователю с будущей явно утверждённой кадровой correction capability и server-validated org scope; Stage manage grant сам по себе не означает право correction. |
| Связь | `person_id`, `section_code`, `employee_context_id` (если есть), `active_cohort_id`, `source_row_id`, исходный `run_id`/`participant_id`/PMF item либо explicit `null` с safe reason. |
| Основание | `origin_status` только `REVIEW_REQUIRED` или `ERROR`; `origin_reason_code`; id исходного аудируемого факта. Pending/rejected override не создаёт событие. |
| Данные аудита | actor id, `occurred_at`, `recorded_at`, safe `reason_code`, `before_fingerprint`, `after_fingerprint`, `source_fingerprint`, `canonical_target_fingerprint`, `binding_fingerprint`, `policy_version`, optimistic concurrency/version. Никаких ФИО, ИИН, raw documents или values в reason. |
| Актуальность | `CORRECTED_BY_HR` действует, пока after/source/target/binding/policy hashes совпадают и нет recheck/acceptance после события. |
| Устаревание | Любое несовпадение перечисленных fingerprints, revoke/supersede event, новый source/binding/policy либо canonical edit после `occurred_at` → `STALE`. |

`CORRECTED_BY_HR` означает «человек внёс аудируемое исправление, автоматическая проверка ещё не подтвердила его». `REVIEW_REQUIRED` означает, что решения нет. `ACCEPTED` означает подтверждённый participant result и canonical target после проверки; он не может быть установлен лишь manual event.

## 5. Fingerprint и invalidation

Все fingerprints — SHA-256 canonical JSON безопасных нормализованных values/ids/versions; значения секретных полей не выдаются в reason. Хеш строится сервером. Timestamp сам по себе включается только когда он является версией конкретного fact; нерелевантный `updated_at` не должен invalidировать section.

### 5.1. `general`

| Категория | В fingerprint | `STALE` | `BLOCKED` | `REVIEW_REQUIRED` | Не аннулирует |
|---|---|---|---|---|---|
| Source facts | `source_row_id`, normalized `full_name`, source `iin`, `birth_date`, source-row version | изменение любого включённого source fact | — | FIO не раскладывается однозначно; invalid IIN/date; source противоречит canonical non-empty value | форматирование/пробелы, дающие тот же normalized value; display «Алфавит» |
| Canonical target | `persons.person_id`, `full_name`, `last_name`, `first_name`, `middle_name`, IIN, birth date и versions именно этих fields | изменение любого указанного target fact после result | merged/inactive person | proposal расходится с непустым canonical field | изменение фото, адреса, иных section facts |
| Binding/cohort | active cohort id/fingerprint, `employee_id`, `employees.person_id`, `source_row_id`, employee active/operational state | корректная смена anchor/cohort | missing/inactive/ambiguous employee/person/source anchor, pending removal | — | org data, не меняющие scope/anchor |
| Policy | Stage 0/1 policy versions; FIO parser/policy version | version change | materialization prohibited | parser yields ambiguous parse | UI label/localization change |

`Алфавит` не является stored или migrated fact и **не включается**: это derived первая Unicode-графема `last_name` в upper-case `ru-RU`.

### 5.2. `education`

| Категория | В fingerprint | `STALE` | `BLOCKED` | `REVIEW_REQUIRED` | Не аннулирует |
|---|---|---|---|---|---|
| Source facts | normalized-record ids/versions, record kind, source key/field, normalized title/provider/specialty/qualification/dates/document identity, review status | изменение included fragment или review-approved content | missing row/source anchor | unreviewed fragment, ambiguous/serial-conflict identity | unrelated import fragments/other sections |
| Target | active `person_education` identity/value hashes, lifecycle, PMF item/run outcome | target edit/supersede/void or PMF outcome mismatch | person/binding invalid | existing canonical identity conflict | non-education canonical changes |
| Binding/cohort | §5.1 anchors plus participant snapshot | valid anchor/cohort change | Stage 0 blocker | — | unrelated employee metadata |
| Policy | Stage 2 `POLICY_VERSION`, education identity policy | policy version change | bridge/materialization gate | policy classifies fragment review-required | display-only copy |

### 5.3. `training`

| Категория | В fingerprint | `STALE` | `BLOCKED` | `REVIEW_REQUIRED` | Не аннулирует |
|---|---|---|---|---|---|
| Source facts | normalized-record ids/versions, kind, source key/field, title/provider/hours/dates/certificate identity, review status | изменение included fragment | missing row/source anchor | unreviewed/ambiguous certificate or identity | unrelated training fragments not selected by candidate |
| Target | active `person_training` identity/value hashes, lifecycle, PMF item/run outcome | target edit/supersede/void or PMF mismatch | person/binding invalid | canonical identity conflict | education/family/etc. changes |
| Binding/cohort | §5.1 anchors plus participant snapshot | valid anchor/cohort change | Stage 0 blocker | — | non-anchor metadata |
| Policy | Stage 3 policy and bridge version | policy version change | bridge/materialization gate | policy requires manual review | UI copy and certificate visibility grant changes |

Для `education` и `training` `NO_SOURCE_DATA` требует explicit completed source scan active participant с zero eligible section fragments. Пустой результат может быть `ACCEPTED` только для этих двух sections, если participant-level acceptance evidence явно подтверждает отсутствие данных; иначе это `NO_SOURCE_DATA`. Пустой `general` никогда не получает `ACCEPTED`.

## 6. Стабильный safe reason-code enum

| Code | Статус | Пользовательский текст |
|---|---|---|
| `SOURCE_GENERAL_MISSING` | `NO_SOURCE_DATA` | «В контрольном списке нет общих сведений для раздела.» |
| `SOURCE_EDUCATION_MISSING` | `NO_SOURCE_DATA` | «В контрольном списке нет сведений об образовании.» |
| `SOURCE_TRAINING_MISSING` | `NO_SOURCE_DATA` | «В контрольном списке нет сведений об обучении.» |
| `SOURCE_FRAGMENT_UNREVIEWED` | `REVIEW_REQUIRED` | «Исходная запись требует кадровой проверки.» |
| `SOURCE_BATCH_PENDING_REMOVALS` | `BLOCKED` | «Изменения контрольного списка ещё не урегулированы.» |
| `BINDING_PERSON_MISSING` | `BLOCKED` | «Не определена связь с личной карточкой.» |
| `BINDING_PERSON_INACTIVE` | `BLOCKED` | «Личная карточка неактивна или объединена.» |
| `BINDING_EMPLOYEE_LINK_STALE` | `BLOCKED` | «Кадровая связь сотрудника изменилась.» |
| `BINDING_SOURCE_ANCHOR_AMBIGUOUS` | `BLOCKED` | «Строка контрольного списка определена неоднозначно.» |
| `BINDING_COHORT_MISMATCH` | `BLOCKED` | «Данные не относятся к активной группе миграции.» |
| `CONFLICT_NAME_PARSE` | `REVIEW_REQUIRED` | «ФИО нельзя однозначно разложить на поля.» |
| `CONFLICT_CANONICAL_VALUE` | `REVIEW_REQUIRED` | «Исходные сведения расходятся с личной карточкой.» |
| `CONFLICT_EDUCATION_IDENTITY` | `REVIEW_REQUIRED` | «Не удалось однозначно сопоставить запись об образовании.» |
| `CONFLICT_TRAINING_IDENTITY` | `REVIEW_REQUIRED` | «Не удалось однозначно сопоставить запись об обучении.» |
| `RUN_NO_SECTION_RESULT` | `NOT_STARTED` | «Для раздела ещё нет результата обработки.» |
| `RUN_NOT_YET_STARTED` | `NOT_STARTED` | «Сотрудник ожидает включения в обработку.» |
| `RUN_APPROVED` | `PROCESSING` | «Этап утверждён и ожидает выполнения.» |
| `RUN_RUNNING` | `PROCESSING` | «Выполняется обработка раздела.» |
| `RUN_PREVIEW_READY` | `AUTO_READY` | «Автоматический результат готов к согласованию.» |
| `RUN_COMPLETED_PENDING_REVIEW` | `AUTO_READY` | «Результат сформирован и ожидает принятия.» |
| `RUN_PARTICIPANT_ACCEPTED` | `ACCEPTED` | «Результат сотрудника подтверждён.» |
| `RUN_EXECUTION_ERROR` | `ERROR` | «Обработка не завершилась; требуется повторный запуск.» |
| `RUN_ACCEPTANCE_PAUSED` | `ERROR` | «Принятие результата приостановлено из-за ошибки.» |
| `RUN_PARTICIPANT_ERROR` | `ERROR` | «Не удалось обработать сведения сотрудника.» |
| `FINGERPRINT_SOURCE_CHANGED` | `STALE` | «Изменились исходные сведения.» |
| `FINGERPRINT_TARGET_CHANGED` | `STALE` | «Изменились сведения личной карточки.» |
| `FINGERPRINT_BINDING_CHANGED` | `STALE` | «Изменилась кадровая или исходная связь.» |
| `FINGERPRINT_COHORT_CHANGED` | `STALE` | «Изменилась зафиксированная группа миграции.» |
| `FINGERPRINT_POLICY_CHANGED` | `STALE` | «Изменились правила обработки.» |
| `MANUAL_CORRECTION_PENDING_RECHECK` | `CORRECTED_BY_HR` | «Исправление сохранено и ожидает перепроверки.» |
| `MANUAL_NOT_APPLICABLE_APPROVED` | `NOT_APPLICABLE` | «Неприменимость раздела подтверждена кадровиком.» |
| `POLICY_NOT_APPLICABLE_APPROVED` | `NOT_APPLICABLE` | «Неприменимость раздела подтверждена правилом.» |
| `POLICY_MATERIALIZATION_BLOCKED` | `BLOCKED` | «Правила не разрешают сформировать личную карточку.» |

Новые коды добавляются только append-only; отображаемый текст меняется версионно, а не путём переиспользования code с другим смыслом.

## 7. Контрольные сценарии

| № | Факты | Итог |
|---|---|---|
| 1 | Person находится в source universe active cohort, participant ещё не frozen; blocker нет. | `NOT_STARTED` / `RUN_NOT_YET_STARTED` |
| 2 | Person не принадлежит source universe active cohort. | Ячейка не создаётся (не `NOT_STARTED`). |
| 3 | Для `general` participant валиден, source `full_name` отсутствует после completed scan. | `NO_SOURCE_DATA` / `SOURCE_GENERAL_MISSING` |
| 4 | В active cohort две source rows для employee. | `BLOCKED` / `BINDING_SOURCE_ANCHOR_AMBIGUOUS` |
| 5 | Stage 1 participant `PENDING`, source/proposal корректны, conflicts пусты. | `AUTO_READY` / `RUN_PREVIEW_READY` |
| 6 | Stage 1 обнаружил FIO с неоднозначным разбором. | `REVIEW_REQUIRED` / `CONFLICT_NAME_PARSE` |
| 7 | Stage 1 run `ACCEPTED`, participant этого person `COMPLETED`, event и `persons` outcome совпадают с fingerprint. | `ACCEPTED` / `RUN_PARTICIPANT_ACCEPTED` |
| 8 | После scenario 7 изменилось source ФИО. | `STALE` / `FINGERPRINT_SOURCE_CHANGED` |
| 9 | После scenario 6 создан approved future manual-correction event с совпадающим after hash; recheck ещё нет. | `CORRECTED_BY_HR` / `MANUAL_CORRECTION_PENDING_RECHECK` |
| 10 | После scenario 9 изменена source row. | `STALE` / `FINGERPRINT_SOURCE_CHANGED` |
| 11 | Stage 2 acceptance подтверждает completed participant и пустой scanned набор education fragments. | `ACCEPTED` / `RUN_PARTICIPANT_ACCEPTED` |
| 12 | Для education есть approved N/A decision по policy, source scan и audit context сохранены. | `NOT_APPLICABLE` / `POLICY_NOT_APPLICABLE_APPROVED` |
| 13 | Stage 3 participant `ERROR`, run paused, facts актуальны. | `ERROR` / `RUN_PARTICIPANT_ERROR` |
| 14 | Есть старый accepted Stage 2 result; новый Stage 2 preview имеет conflict по identity. | `REVIEW_REQUIRED` / `CONFLICT_EDUCATION_IDENTITY` |
| 15 | Последний Stage 3 run `CANCELLED`; предыдущий accepted participant evidence актуален. | `ACCEPTED` / `RUN_PARTICIPANT_ACCEPTED` |
| 16 | После accepted training изменена Stage 3 policy version. | `STALE` / `FINGERPRINT_POLICY_CHANGED` |
| 17 | Pending override создан, но не approved; иных conflicts нет. | Его наличие не меняет статус: например `AUTO_READY` / `RUN_PREVIEW_READY`. |
| 18 | Person merged после completed Stage 1 result. | `BLOCKED` / `BINDING_PERSON_INACTIVE` |

## 8. Решения владельца продукта — Approved

| Решение | Рекомендуемый вариант | Альтернативы | Последствия | Что утвердить |
|---|---|---|---|---|
| Active cohort | Один явно выбранный BASE cohort плюс только явно подключённые supplemental cohorts. | Последний frozen cohort; объединение всех cohorts. | Воспроизводимая матрица и отсутствие смешения batch. | **Approved:** active universe определяется этим правилом. |
| v1 scope | Только `general`, `education`, `training`. | Добавить прочие read-only sections. | Нет фиктивных статусов и непроверяемых claims. | **Approved:** список v1 columns. |
| `NO_SOURCE_DATA` vs accepted empty | Empty result может быть `ACCEPTED` только для `education`/`training` с participant-level evidence явного подтверждения отсутствия данных; иначе `NO_SOURCE_DATA`. Пустой `general` никогда не `ACCEPTED`. | Всегда `NO_SOURCE_DATA`. | Сохраняет факт согласованной пустоты, не маскируя пустой general. | **Approved:** указанное section-specific правило. |
| Manual correction | Система append-only создаёт audited event после успешного commit ручной коррекции, затем требуется recheck. | Считать любой approved override correction. | Не смешиваются import-review и status semantics; actor и before/after fingerprints сохраняются автоматически. | **Approved:** system-emitted event, не отдельное действие кадровика. |
| Policy change | Любая version change в v1 → `STALE`. | Selective compatibility mapping. | Безопасно, но требует recheck. | **Approved:** без compatibility mapping в v1. |
| Matrix membership | Только active universe; вне его нет строки/ячейки. | Показывать всех Persons как `NOT_STARTED`. | Не искажает coverage активной миграции. | **Approved:** люди вне active universe исключаются. |
| Navigation/API | Отдельный будущий WP после этого контракта. | Реализовать вместе с semantics. | WP-005A остаётся без implementation. | **Approved:** Navigation/API/UI вне WP-005A. |

Решения утверждены. Документ готовит WP-PPR-MIG-005B и не разрешает создание новой таблицы, API, UI, permission или миграцию данных.
