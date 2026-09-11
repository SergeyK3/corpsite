# WP-PPR-MIG-005 — Сводная матрица состояния миграции личных карточек

> **WP-PPR-MIG-005E status:** [Completed — Ready for WP-PPR-MIG-005F](WP-PPR-MIG-005E-card-section-status-display.md).

> **WP-PPR-MIG-005F-C status:** [Deferred — no confirmed manual canonical writers](WP-PPR-MIG-005F-C-manual-write-producers.md). It may resume only after separate manual canonical editing for `general`, `education`, and `training`; Stage/PMF cannot produce `CORRECTED_BY_HR`.

> **WP-PPR-MIG-005F status:** [Approved — WP-PPR-MIG-005F-C deferred pending manual canonical editors](WP-PPR-MIG-005F-corrections-invalidation-plan.md).

> **WP-PPR-MIG-005D status:** [Completed — Ready for WP-PPR-MIG-005E](WP-PPR-MIG-005D-matrix-navigation-ui.md).

> **WP-PPR-MIG-005C status:** [Completed — Ready for WP-PPR-MIG-005D](WP-PPR-MIG-005C-report-api-and-authorization.md). WP-PPR-MIG-005D navigation has not been started.

| Параметр | Значение |
|---|---|
| Статус | **Draft — инвентаризация выполнена; остаются открытые архитектурные решения** |
| Дата | 2026-09-11 |
| Назначение | План объединения пакетной миграции и ручного кадрового согласования |
| Предлагаемый путь в репозитории | `docs/implementation/WP-PPR-MIG-005-migration-status-matrix-plan.md` |
| Точка входа | `/directory/personnel/lk` |

## 1. Цель

Создать единое рабочее представление, в котором руководитель отдела кадров видит состояние миграции личных карточек по всей зафиксированной совокупности сотрудников.

Строки представления соответствуют сотрудникам, столбцы — разделам личной карточки. На пересечении отображается текстовое состояние раздела: обработан автоматически, требует ручной проверки, согласован, не содержит исходных данных, заблокирован и т. п.

Матрица не заменяет существующие процессы:

1. ручное согласование отдельных записей контрольного списка остаётся инструментом разбора и исправления спорных данных;
2. пакетная поэтапная миграция остаётся инструментом формирования cohort, dry-run, выполнения и принятия результатов по разделам;
3. матрица объединяет результаты обоих процессов и показывает, где требуется участие кадровика.

## 2. Основной принцип

Оба процесса используют общую модель состояния `Person × раздел личной карточки`.

- Пакетный процесс записывает результаты автоматической проверки и миграции раздела.
- Ручной процесс записывает решение или исправление кадровика.
- Личная карточка показывает то же состояние внутри соответствующего раздела.
- Сводный отчёт читает те же состояния и не вычисляет собственные независимые метки.
- После изменения источника, кадровой связи или канонических данных состояние становится устаревшим либо пересчитывается контролируемо.

Не допускается наличие двух несогласованных классификаторов: одного для сводной таблицы и другого для личной карточки.

## 3. Два взаимодополняющих процесса

### 3.1. Ручное согласование

Существующий интерфейс покомпонентного согласования применяется, когда:

- ФИО разобрано неоднозначно;
- найден конфликт с каноническими данными;
- источник неполон или содержит ошибку;
- обнаружено несколько возможных соответствий;
- автоматическая миграция запрещена правилами раздела;
- кадровик должен подтвердить или исправить конкретное значение.

Результат ручного действия должен быть связан с `person_id`, разделом, исходной записью, пользователем, временем и причиной решения.

### 3.2. Пакетная миграция «цикл в цикле»

Внешний цикл работает с зафиксированной совокупностью сотрудников. Внутренний цикл последовательно обрабатывает разделы личной карточки:

1. допуск карточки и кадровая связь;
2. общие сведения;
3. образование;
4. обучение и повышение квалификации;
5. трудовая биография и послужной список;
6. родственники;
7. воинский учёт;
8. дополнительные разделы после отдельной инвентаризации источников.

Каждый этап использует собственные правила eligibility, dry-run, review и acceptance. Ошибка одного сотрудника или раздела должна быть видна в матрице и не превращаться в безымянный общий сбой.

### 3.3. Точка встречи процессов

Клик по ячейке матрицы открывает нужную личную карточку сразу на соответствующем разделе. Если требуется ручное согласование, оттуда должен быть доступен существующий интерфейс исправления либо рассмотрения исходной записи.

После сохранения ручного решения пользователь возвращается в матрицу через `return_to`. Затронутая ячейка помечается как требующая повторной проверки либо обновляется после контролируемого пересчёта.

## 4. Общие сведения как обязательный первый этап

До миграции разделов необходимо подтвердить identity anchor и общие кадровые сведения.

Минимальная проверка включает:

- существование активного `Person`;
- однозначную связь `Employee → Person`;
- отсутствие признака merged/rebound для выбранной карточки;
- соответствие ИИН правилам формата и доступности;
- проверку даты рождения;
- разложение ФИО на фамилию, имя и отчество;
- определение отсутствующего отчества без создания фиктивного значения;
- заполнение иных утверждённых общих полей, фактически имеющихся в контрольном списке;
- сохранение provenance и результата проверки.

ФИО не используется как самостоятельный идентификатор сотрудника. Идентификация выполняется по техническим связям и ИИН в пределах разрешённого кадрового процесса.

### 4.1. Разложение ФИО

Обработчик общих сведений должен возвращать:

- исходное ФИО без потери данных;
- предлагаемую фамилию;
- предлагаемое имя;
- предлагаемое отчество либо явный признак его отсутствия;
- версию правила разбора;
- показатель уверенности либо набор диагностических причин;
- сведения о совпадении с уже заполненными каноническими полями.

Автоматическое применение допустимо только при однозначном разборе и отсутствии конфликта с непустыми каноническими значениями. Неоднозначность переводит раздел в состояние `REVIEW_REQUIRED`.

Поле «Алфавит» заполняется только после фиксации действующего бизнес-правила. Нельзя автоматически считать его первой буквой фамилии без подтверждения назначения поля.

## 5. Единый классификатор состояний раздела

| Код | Отображаемая метка | Значение |
|---|---|---|
| `NOT_STARTED` | Не начато | Раздел ещё не проверялся для текущего snapshot. |
| `PROCESSING` | Обрабатывается | Выполняется контролируемая обработка раздела. |
| `AUTO_READY` | Готово автоматически | Проверка успешна, автоматический результат сформирован, но ещё не принят кадровиком или этапом. |
| `REVIEW_REQUIRED` | Требуется ручная проверка | Найдена неоднозначность, неполнота или конфликт, требующий решения кадровика. |
| `CORRECTED_BY_HR` | Исправлено кадровиком | Кадровик сохранил исправление; требуется повторная проверка либо принятие результата. |
| `ACCEPTED` | Согласовано | Результат принят уполномоченным пользователем и соответствует текущему fingerprint. |
| `NO_SOURCE_DATA` | Нет исходных данных | В источнике отсутствуют сведения для данного раздела. Это не техническая ошибка. |
| `NOT_APPLICABLE` | Не применимо | Раздел обоснованно не применяется к данному человеку. Требуется правило или решение с причиной. |
| `BLOCKED` | Заблокировано | Нарушена обязательная предпосылка: identity, связь, permission, source integrity или иной safety gate. |
| `STALE` | Требуется обновление | После проверки изменились источник, связь, правила или значимые канонические данные. |
| `ERROR` | Ошибка обработки | Техническая операция не завершилась; сохраняется безопасный код ошибки. |

### 5.1. Правила использования меток

- Метка всегда выводится текстом; цвет может быть только дополнительным признаком.
- `AUTO_READY` не равен `ACCEPTED`.
- `NO_SOURCE_DATA` не равен `NOT_APPLICABLE`.
- `CORRECTED_BY_HR` не означает, что повторная проверка уже пройдена.
- `ERROR` не должен скрывать бизнес-состояние предыдущего успешного snapshot; в деталях показываются обе даты.
- `ACCEPTED` действительно только для зафиксированных версии правила, source fingerprint и relevant canonical fingerprint.

## 6. Отображение состояния в личной карточке

В каждом мигрируемом разделе личной карточки размещается информационный блок состояния.

Он показывает:

- текстовую метку;
- дату и время последней проверки;
- источник результата;
- номер или тип этапа миграции;
- краткую причину, если требуется участие кадровика;
- сведения о последнем решении кадровика без лишних персональных данных;
- действие «Проверить», «Исправить» или «Обновить состояние» при наличии соответствующего права.

Метка отображается внутри самого раздела. Дополнительно рядом с названием вкладки допускается компактный текстовый индикатор, но он не заменяет подробный блок.

Если статус `REVIEW_REQUIRED`, `BLOCKED`, `STALE` или `ERROR`, пользователь должен иметь возможность открыть детали причины. Технические trace и секреты в UI не показываются.

## 7. Сводная матрица

### 7.1. Точка входа

На странице `/directory/personnel/lk` размещается кнопка:

**«Сводка миграции личных карточек»**

Кнопка открывает защищённую страницу сводного отчёта. Она показывается только пользователям с правом просмотра миграции.

### 7.2. Структура

Строка матрицы содержит:

- ФИО;
- подразделение и должность;
- безопасный технический идентификатор;
- общее состояние карточки;
- состояния отдельных разделов.

Столбцы первой версии:

1. Карточка и кадровая связь;
2. Общие сведения;
3. Образование;
4. Обучение и повышение квалификации;
5. Трудовая биография;
6. Родственники;
7. Воинский учёт;
8. Дополнительные сведения.

Кадровые приказы, обращения, адаптация и история изменений не включаются в миграционную матрицу автоматически: для них требуется отдельное решение об источнике и назначении.

### 7.3. Фильтры и навигация

Необходимые фильтры:

- подразделение;
- этап миграции;
- состояние раздела;
- наличие хотя бы одной проблемы;
- сотрудник;
- дата последней проверки;
- конкретный запуск или cohort.

Клик по ФИО открывает полную карточку. Клик по ячейке открывает конкретный раздел с сохранённым `return_to` на текущую выборку матрицы.

Над таблицей отображаются счётчики по каждому состоянию, рассчитанные для текущих фильтров.

## 8. Обновление матрицы

Предусмотреть два действия:

1. **«Обновить строку»** — повторная проверка всех разделов одного сотрудника;
2. **«Обновить сводку»** — контролируемый инкрементальный пересчёт выбранного cohort.

Обновление не должно автоматически переносить спорные данные или принимать результат за кадровика. Оно только повторно вычисляет допустимость и состояние на основании текущих источников, решений и канонических данных.

После ручной коррекции:

1. сохраняется кадровое решение и аудит;
2. соответствующий статус становится `CORRECTED_BY_HR` либо `STALE`;
3. выполняется повторная проверка затронутого раздела;
4. при успехе статус становится `AUTO_READY`;
5. после предусмотренного этапом принятия — `ACCEPTED`.

Массовое обновление выполняется как отдельный идентифицируемый run с прогрессом и возможностью безопасного повторного запуска. Двойной клик не создаёт второй параллельный run.

## 9. Модель хранения и аудит

До реализации требуется инвентаризировать существующие таблицы Stage 0–3, PMF, ручного review и PPR events. Цель — не дублировать уже существующие факты.

Рекомендуемая логическая модель состоит из двух уровней:

- неизменяемые события проверки, ручного решения, выполнения и принятия;
- актуальная проекция `Person × section`, из которой читаются карточка и матрица.

Для актуального состояния должны быть доступны:

- `person_id`;
- `employee_id` как контекст, если существует;
- `section_code`;
- `status_code`;
- `source_kind` и безопасная ссылка на источник;
- `stage_run_id`/participant id при наличии;
- версии parser/policy;
- source и canonical fingerprints;
- дата проверки;
- дата и автор ручного решения;
- безопасный код причины или ошибки;
- версия строки для конкурентного обновления.

Нельзя хранить полный ИИН, исходные документы и чувствительные значения в общей статусной проекции. Они читаются из разрешённых источников только в специализированном интерфейсе.

## 10. Права доступа

Инвентаризация должна определить возможность переиспользовать существующие permissions Stage 0–3 и кадрового review.

Если общего права недостаточно, рекомендуются отдельные permissions:

- `PPR_MIGRATION_STATUS_READ` — просмотр матрицы и меток;
- `PPR_MIGRATION_STATUS_REFRESH` — запуск повторной проверки;
- существующие stage-specific manage permissions — принятие и выполнение конкретного этапа;
- существующие права кадровой коррекции — исправление исходных или канонических данных.

Организационный scope проверяется сервером во всех запросах. Право просмотра матрицы не даёт права исправлять, принимать или выполнять миграцию.

## 11. Согласование с существующими Stage 0–3

Текущие stage-run и participant statuses не заменяются новым классификатором напрямую. Требуется явная таблица отображения существующих технических состояний в пользовательское состояние раздела.

Примеры:

| Существующий результат | Состояние раздела |
|---|---|
| Участник ещё не обработан | `NOT_STARTED` |
| Preview сформировал однозначное предложение | `AUTO_READY` |
| Candidate содержит field issues | `REVIEW_REQUIRED` |
| Source отсутствует | `NO_SOURCE_DATA` |
| Person/Employee binding нарушен | `BLOCKED` |
| Fingerprint изменился | `STALE` |
| Stage принят и canonical write подтверждён | `ACCEPTED` |

Для каждого Stage 0–3 mapping должен быть утверждён отдельно. Нельзя определять состояние по тексту сообщения frontend.

## 12. API и производительность

Точный контракт определяется после инвентаризации. Минимально потребуются:

- чтение матрицы с серверной пагинацией, сортировкой и фильтрами;
- чтение состояния разделов одного `Person`;
- запуск обновления строки;
- запуск обновления выбранного cohort;
- получение прогресса и итогов обновления.

Запрещается N+1 чтение состояния по сотрудникам или разделам. Сводка должна строиться пакетным запросом либо по поддерживаемой актуальной проекции.

## 13. Последовательность реализации

1. Инвентаризировать ручной review, Stage 0–3, PMF, PPR events и существующие UI-маршруты.
2. Составить точную карту `существующий статус → статус раздела`.
3. Утвердить список разделов первой версии и business rule поля «Алфавит».
4. Спроектировать общую событийную модель и актуальную статусную проекцию без дублирования фактов.
5. Реализовать обработчик общих сведений и безопасное разложение ФИО.
6. Реализовать backend чтения матрицы и состояний карточки.
7. Добавить кнопку «Сводка миграции личных карточек» на `/directory/personnel/lk`.
8. Реализовать таблицу, фильтры, счётчики и переход в нужный раздел карточки.
9. Добавить текстовые метки и детали состояния в разделы личной карточки.
10. Связать ручные исправления с invalidation и повторной проверкой состояния.
11. Реализовать обновление одной строки и инкрементальное обновление cohort.
12. Провести PostgreSQL-интеграционные, RBAC, идемпотентные и визуальные тесты.
13. Выполнить pilot на небольшой утверждённой группе и только затем production rollout.

## 14. Критерии приёмки

1. На `/directory/personnel/lk` доступна кнопка открытия сводки для уполномоченного кадровика.
2. Матрица показывает одну строку на участника зафиксированного cohort и один столбец на раздел.
3. Каждая ячейка содержит текстовую метку, а не только цвет.
4. `AUTO_READY` однозначно отличается от `ACCEPTED`.
5. `NO_SOURCE_DATA` отличается от `NOT_APPLICABLE` и технической ошибки.
6. Клик по ячейке открывает соответствующий раздел карточки и позволяет вернуться к прежней выборке.
7. Та же метка и её причина отображаются внутри раздела личной карточки.
8. Общие сведения проверяют связь Employee–Person, ИИН, дату рождения и разложение ФИО.
9. Неоднозначное ФИО не применяется автоматически.
10. Ручная коррекция фиксируется в аудите и инициирует повторную проверку только нужного состояния.
11. Обновление сводки не выполняет несанкционированный canonical write или approval.
12. Изменение источника или значимых канонических данных переводит результат в `STALE`.
13. Повторный запуск идемпотентен и не создаёт параллельные дублирующие операции.
14. Организационный scope и permissions проверяются сервером.
15. Матрица строится без N+1 запросов.
16. Существующие ручной review и Stage 0–3 продолжают работать без изменения их утверждённых правил.

## 15. Обязательные findings до написания миграции и endpoint

До реализации Codex должен представить:

- перечень существующих stage/run/participant/proposal статусов и таблиц;
- перечень событий ручной коррекции и кадрового согласования;
- карту разделов PPR и их section codes;
- источники общих сведений, отдельных частей ФИО и поля «Алфавит»;
- действующие permissions и организационный scope страницы `/directory/personnel/lk`;
- способ открытия карточки на конкретном разделе и сохранения `return_to`;
- оценку объёма cohort и пакетного запроса матрицы;
- перечень открытых архитектурных решений.

До утверждения этих findings нельзя создавать новую таблицу статусов, migration DDL или массовый endpoint обновления.

## 16. Не-действия

Этот документ является планом. Он не разрешает изменение production-данных, запуск миграции, создание DDL, endpoint, кнопки или фоновой задачи. Реализация начинается отдельным work package после утверждения findings.

## 17. Findings инвентаризации (2026-09-11)

Статус semantics для `Person × section` зафиксирован в [WP-PPR-MIG-005A — Status semantics](WP-PPR-MIG-005A-status-semantics.md): **Approved — Ready for WP-PPR-MIG-005B**. [WP-PPR-MIG-005B — read model безопасной актуальной status projection](WP-PPR-MIG-005B-status-projection-read-model.md): **Completed — Ready for WP-PPR-MIG-005C**. Следующий scope — WP-005C report API/RBAC.

### 17.1. Точная карта существующего контура

| Область | Таблицы / модель | Сервисы и API | Frontend |
|---|---|---|---|
| Ручной контрольный список и correction | `hr_import_batches`, `hr_import_rows`, нормализованные записи и review overrides (контур уже используется Stage 0) | `hr_import_row_review_service.py`, `hr_import_normalized_record_service.py`, `hr_import_employee_binding_service.py`, `hr_import_diff_removal_decision_service.py`, `hr_review_override_service.py`; административный router `/admin/personnel/overrides` (create, approve, reject, revoke, reconfirm) | `PersonnelImportRowsPageClient`, `PersonnelImportRowReviewPageClient`, `PersonnelImportNormalizedRecordsReviewPageClient` |
| Stage 0: cohort | `ppr_stage0_cohort_runs`, `ppr_stage0_cohort_participants`, `ppr_stage0_cohort_blockers`; ORM `app/db/models/ppr_stage0_cohort.py` | `ppr_stage0_cohort_service.py`, router `/personnel/ppr-migration/stage-0` | `ppr-migration/PprMigrationPageClient.tsx` |
| Stage 1: general | `ppr_stage1_general_runs`, `ppr_stage1_general_participants` (proposal и conflicts — JSONB в participant) | `ppr_stage1_general_service.py`, router `/personnel/ppr-migration/stage-1`: `preview`, `runs/{id}`, `approve`, `execute-next`, `accept` | отдельной Stage-1 панели в текущем migration UI не найдено |
| Stage 2: education | общие `ppr_stage_runs`, `ppr_stage_run_participants`; PMF `personnel_migration_runs`, `personnel_migration_items`, `person_education` | `ppr_stage2_education_service.py`, `education_migration_plugin.py`, router `/personnel/ppr-migration/stage-2/education` | `Stage2EducationPanel.tsx`, `personnelMigrationApi.client.ts` |
| Stage 3: training | общие `ppr_stage_runs`, `ppr_stage_run_participants`; `person_training` | `ppr_stage3_training_service.py`, router `/personnel/ppr-migration/stage-3/training` | `Stage3TrainingPanel.tsx`, `personnelMigrationApi.client.ts` |
| PMF и PPR audit | `personnel_migration_domains`, `personnel_migration_runs`, `personnel_migration_items`, `personnel_record_events`; PPR event repository в `app/ppr/infrastructure` | `personnel_migration_commit_service.py`, `personnel_migration_ppr_bridge.py`, `personnel_migration_record_events_query_service.py`, `app/ppr/application/import_bridge_service.py` | `Migration*` components и `MigrationSessionWorkspace.tsx` |
| PPR card | `persons`, `employees`, `personnel_record_metadata`, section SoT: `person_education`, `person_training`, `person_relatives`, `person_external_employment`, `person_military_service` | `ppr_router.py`, `ppr_query_access_service.py` | `/directory/personnel/persons/[personId]/card` → `PprPersonalCardPageClient.tsx`; `/directory/personnel/lk` → `PersonnelLkPageClient.tsx` |

Stage 0 использует snapshot контрольного списка и блокеры; Stage 1 имеет собственные run/participant таблицы. Stages 2–3 используют общий envelope `ppr_stage_runs`/`ppr_stage_run_participants`, а фактическое применение проходит через PMF/PPR bridge. `personnel_record_events` — существующий аудит доменных изменений; отдельного факта «статус ячейки матрицы» нет.

### 17.2. Подтверждённое отображение технического состояния в единый статус раздела

| Источник / точное техническое состояние | Единый статус раздела |
|---|---|
| Нет Stage-0 participant или stage run для текущего cohort | `NOT_STARTED` |
| Stage 0 blocker: `SOURCE_MISSING` / source-row отсутствует | `NO_SOURCE_DATA` |
| Stage 0 blocker: duplicate/ambiguous anchor, pending removal/rebind, employee/person binding | `BLOCKED` |
| Stage 1 preview: participant `PENDING`, proposal без conflicts | `AUTO_READY` |
| Stage 1 participant `ERROR` с `conflicts` | `REVIEW_REQUIRED`; с иной ошибкой — `ERROR` |
| Stage 1 run `APPROVED` или `RUNNING` | `PROCESSING` |
| Stage 1 run `COMPLETED_PENDING_REVIEW` | `AUTO_READY` |
| Stage 1 run `ACCEPTED` | `ACCEPTED` для `general`, только пока source/person fingerprint актуален |
| Stage 2/3 run `DRAFT`/`APPROVED`/`RUNNING` | `PROCESSING` (до этого preview без persist — `AUTO_READY`) |
| Stage 2/3 participant `SKIPPED_BY_DECISION` | `NOT_APPLICABLE` только при утверждённом reason; иначе `REVIEW_REQUIRED` |
| Stage 2/3 run `PAUSED_ON_ERROR` или participant `ERROR` | `ERROR` |
| Stage 2/3 run `COMPLETED_PENDING_REVIEW` | `AUTO_READY` |
| Stage 2/3 run `CANCELLED` | `NOT_STARTED` (не является результатом раздела) |
| Stage 2/3 run `ACCEPTED` и соответствующий PMF/PPR write подтверждён | `ACCEPTED` |
| Сменился fingerprint источника, `persons.updated_at`, binding либо policy после результата | `STALE` |

Это mapping первой версии, а не существующая persisted-проекция: правила приоритета между Stage 0 blocker, ручным override и несколькими runs ещё нужно утвердить.

### 17.3. Ручная коррекция: подтверждённые события и эффект

| Действие | Существующий механизм | Эффект для матрицы |
|---|---|---|
| Review/изменение нормализованной записи | `update_normalized_record_review`, `update_normalized_record_review_override` | `general` или затронутый section → `STALE`, затем повторная проверка |
| Привязка либо repair Employee–Person/source row | `persist_row_employee_binding`, `bind_normalized_record_to_employee`, `repair_batch_employee_bindings` | снимает/создаёт Stage-0 blocker; все зависящие разделы → `STALE` или `BLOCKED` |
| Решение об удалении/ребиндинге строки | `hr_import_diff_removal_decision_service.py` | Stage 0 cohort становится недействительным для затронутого participant: `STALE`/`BLOCKED` |
| Override: create/approve/reject/revoke/reconfirm/supersede | `hr_review_override_service.py`; `/admin/personnel/overrides/*` | approved override делает зависимый section `STALE`; pending/rejected override сам по себе не равен `CORRECTED_BY_HR` |
| Ручная корректировка канонического section в PPR/PMF | domain writer и `personnel_record_events` | `CORRECTED_BY_HR` допустим только при явном аудируемом manual event; такого единого события/проекции пока нет |

Следствие: текущие контуры надёжно дают invalidation (`STALE`/`BLOCKED`), но не дают готовый единый журнал решения `CORRECTED_BY_HR`; его семантику и источник необходимо спроектировать отдельно.

### 17.4. Разделы первой версии и источники общих сведений

Первая версия матрицы должна ограничиться разделами, для которых уже есть stage/SoT: `general`, `education`, `training`. `family`, `military`, `employment_biography` имеют PPR section codes (`PPR-FAMILY`, `PPR-MILITARY`, `PPR-EMPLOYMENT-BIOGRAPHY`) и read UI, но stage-run для них не найден; поэтому в v1 они не должны притворяться мигрированными. `additional`, `intended_employment`, `assignment`, `orders`, `applications`, `onboarding`, `changes` — UI sections, а не подтверждённые миграционные domains v1.

| Поле общих сведений | Подтверждённый источник / чтение |
|---|---|
| identity, canonical ФИО, ИИН, дата рождения | `persons`; PPR composite read через `ppr_router.py` / `pprQueryApi.client.ts` |
| кадровый контекст и org unit | `employees` и `personnel_record_metadata`; scope вычисляется из employee org unit |
| source ФИО для Stage 1 | `hr_import_rows.normalized_payload->>'full_name'` и snapshot участника Stage 0 |
| фамилия, имя, отчество в карточке | `PprCompositeReadResponse.general.last_name/first_name/middle_name`, получаемые из canonical PPR read; Stage 1 сейчас формирует proposal из `employees` + `persons` + `hr_import_rows`, но отдельные source columns ФИО не являются отдельными persisted-колонками Stage 1 |
| «Алфавит» | **решение найдено:** `PprCardGeneralSection.tsx` вызывает `deriveIntakeSurnameAlphabet(last_name)` из `app/intake/_lib/intakePersonalFields.ts`; это первая Unicode-графема фамилии в верхнем регистре `ru-RU`, поле не хранится и не мигрируется |

### 17.5. Permissions, scope, маршрут и возврат

Переиспользование возможно частично: Stage 0–3 уже требуют роль `HR_HEAD` и соответственно `PPR_STAGE0_COHORT_MANAGE`, `PPR_STAGE1_GENERAL_MANAGE`, `PPR_STAGE2_EDUCATION_MANAGE`, `PPR_STAGE3_TRAINING_MANAGE`; Stage 3 дополнительно маскирует детали сертификата без `VIEW_TRAINING_CERTIFICATE_DETAILS`. Во всех stage routers применяется `compute_scope(...)` и `require_personnel_visibility_or_403(...)`, затем cohort проверяется по `employees.org_unit_id`. PPR card read применяет тот же scope в `ppr_query_access_service.py`.

Для чтения новой матрицы existing stage-manage grants непригодны как единственное право: они дают capability выполнения и требуют `HR_HEAD`. Для отчёта нужен отдельный read grant (предлагаемый `PPR_MIGRATION_STATUS_READ`) либо явно утверждённое расширение существующего personnel-read policy; выполнение stage и correction должны оставаться на текущих grants.

Точный новый маршрут отчёта **ещё не существует**. Рекомендуемый маршрут для отдельного будущего WP: `/directory/personnel/migration-status`. Точный существующий переход в карточку: `/directory/personnel/persons/{personId}/card?section={PprCardSectionId}&return_to={encoded-relative-url}`. Но `employeeCardNav.ts` типизирует только legacy `EmployeeCardSectionId`, поэтому для PPR sections (`education`, `training`, `family`, `military`, `employment_biography`) matrix UI должен строить PPR URL самостоятельно либо сначала расширить nav helper. Карточка разбирает section через `parsePprCardSection`, scrolls to section id, а `return_to` валидируется `normalizeReturnTo` (только относительный путь, не `//`) и используется кнопкой Back. Существующий LK подтверждённо открывает карточку с `return_to=/directory/personnel/lk`.

### 17.6. Риски, пробелы и открытые решения

1. Нет persisted status projection `Person × section` и нет единого события ручной коррекции; нельзя выводить `CORRECTED_BY_HR` достоверно из текстов UI или PMF status.
2. Stage 1 general отличается моделью от Stage 2–3; proposals/conflicts в JSONB, а не в общем envelope. Семантика выбора нескольких runs и active universe утверждена в WP-005A; её реализация остаётся задачей WP-005B.
3. Нужны утверждённые правила invalidation: точные поля/fingerprint, приоритет `BLOCKED`/`STALE`/manual correction и срок действия accepted результата.
4. Матрица нужна с серверной pagination и bulk aggregation: контракта, индексов и допустимого cohort size ещё нет. N+1 недопустим.
5. У `PprCardGeneralSection` «Алфавит» — derived display, а не canonical value; нельзя добавлять его в source/migration rule без отдельного решения владельца данных.
6. Новый route/report permission и UX перехода в PPR section не существуют; `employeeCardNav.ts` не покрывает PPR section IDs.
7. Доступ к full IIN и restricted military details уже ограничен; матрица должна показывать только safe status/reason codes.

### 17.7. Рекомендуемые небольшие work packages

1. **WP-PPR-MIG-005A — status semantics:** утвердить v1 sections, mapping/priorities и fingerprint/invalidation contract без DDL/UI.
2. **WP-PPR-MIG-005B — read model:** миграция и сервис актуальной safe status projection, backfill только из существующих facts, PostgreSQL/RBAC tests.
3. **WP-PPR-MIG-005C — report API and authorization:** отдельный read permission, scoped paginated endpoint и aggregation/performance tests.
4. **WP-PPR-MIG-005D — navigation:** PPR-safe card href helper, report route, matrix table и `return_to`; без execution actions.
5. **WP-PPR-MIG-005E — card status display:** метка и reason внутри `general`/`education`/`training` section с доступным текстом.
6. **WP-PPR-MIG-005F — corrections/invalidation:** аудируемый manual-correction event и targeted recalculation after approved review/binding/source changes.
7. **WP-PPR-MIG-005G — full section matrix:** утверждён каталог десяти migration sections; [WP-005G-A](WP-PPR-MIG-005G-A-full-section-projection.md) — **Completed — Ready for WP-PPR-MIG-005G-B**: persisted projection/rebuild для всех десяти codes выполнен, без расширения report API и frontend.
