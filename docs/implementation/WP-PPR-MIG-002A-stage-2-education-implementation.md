# WP-PPR-MIG-002A — Stage 2 Education: implementation plan

| Статус | **Approved — Ready for Stage 2 Implementation** |
|---|---|
| Основание | [WP-PPR-MIG-002](WP-PPR-MIG-002-stage-2-education.md), Stage 0 frozen cohort, ADR-PMF-001 и `EducationMigrationPlugin` |
| Граница | Только Stage 2 «Образование»; не Stage 3 и не иной section. |

## Final Implementation Review

| Дата | Решение | Основание |
|---|---|---|
| 2026-09-09 | **APPROVED** | Проверены schema/migration, envelope–PMF ownership, state machine, participant/acceptance pause, rollback, lock order, RBAC/API, acceptance replay и test/visual pilot. Открытых архитектурных решений для реализации Stage 2 нет. |

## 1. Архитектура и migration

Stage 2 добавляет тонкий общий envelope этапного прогона. Он владеет frozen section
cohort, курсором, pause/resume, решением об исключении и итоговым принятием. PMF
остаётся единственным владельцем education draft payload, `personnel_migration_runs`,
`personnel_migration_items`, provenance, `EducationMigrationPlugin` и canonical PPR
commands. Envelope никогда не хранит полный ИИН, ФИО, сырой текст контрольного списка
или payload образования.

Stage 1 `ppr_stage1_general_*` — scalar-Person storage; его расширять или
переиспользовать запрещено. Stage 0 cohort неизменяем; Stage 2 замораживает свой
section snapshot поверх него.

Плановая migration: `s2e1d2u3c4a5_ppr_stage2_education_envelope.py`,
`down_revision = 's1g0e1n2r3a4'`. Это подтверждённый актуальный локальный Alembic
head. Она создаёт ровно две envelope-таблицы (`ppr_stage_runs`,
`ppr_stage_run_participants`), permission с его HR_HEAD grant и два
Stage-2-specific unique index на существующих PMF-таблицах. PMF columns и education
payload schema она не меняет; исторические migrations, Stage 0/1 и canonical education
также не меняются. Downgrade в безопасном порядке удаляет сначала оба новых PMF index,
затем Stage 2 grant/permission, FK от envelope run к participant, participant table и
run table; он не затрагивает PMF rows, columns или payload.

### 1.1 `ppr_stage_runs`

| Поле | Тип, FK и ограничение |
|---|---|
| `stage_run_id` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY`. |
| `stage_code` | `TEXT NOT NULL CHECK (stage_code = 'education')`. |
| `stage0_cohort_run_id` | `BIGINT NOT NULL REFERENCES ppr_stage0_cohort_runs(stage0_cohort_run_id) ON DELETE RESTRICT`. |
| `status` | `TEXT NOT NULL` с check: `DRAFT`, `DRY_RUN_COMPLETED`, `APPROVED`, `RUNNING`, `PAUSED_ON_ERROR`, `COMPLETED_PENDING_REVIEW`, `ACCEPTED`, `CANCELLED`. |
| `preview_fingerprint` | `CHAR(64) NOT NULL CHECK (preview_fingerprint ~ '^[0-9a-f]{64}$')`. |
| `policy_version` | `TEXT NOT NULL CHECK (policy_version = 'EDU-KIND-ALLOWLIST-v1')`. |
| `current_position` | `INTEGER NOT NULL DEFAULT 0 CHECK (current_position >= 0)`. При пустом cohort — `0`; при обработке — следующая позиция `1..N`; после последнего — `N+1`. |
| `safe_snapshot` | `JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(safe_snapshot) = 'object')`; только IDs, версии, hashes, counts и safe codes. |
| actors | `created_by_user_id BIGINT NOT NULL`, nullable `approved_by_user_id`, `accepted_by_user_id`, `cancelled_by_user_id`; каждый `REFERENCES users(user_id) ON DELETE RESTRICT`. |
| времена | `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, nullable `approved_at`, `accepted_at`, `paused_at`, `cancelled_at`. |
| pause | nullable `paused_operation TEXT CHECK (paused_operation IN ('PARTICIPANT_EXECUTION','ACCEPTANCE'))`, `stopped_participant_id BIGINT REFERENCES ppr_stage_run_participants(stage_run_participant_id) ON DELETE RESTRICT`, `last_error_code TEXT`, `last_error_reference TEXT`. FK добавляется после participant table. |
| cancel | nullable `cancel_reason TEXT`. |
| acceptance replay | nullable `accepted_precondition_fingerprint CHAR(64) CHECK (... SHA-256 ...)`, `acceptance_outcome JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(acceptance_outcome)='object')`. |

`acceptance_outcome` хранит только server-derived `participant_count`,
`completed_count`, `skipped_count`, `already_applied_count`,
`created_record_count`, `committed_item_count`, `event_count` и safe acceptance
fingerprint.

Полные row-local check-инварианты:

- В `DRAFT` и `DRY_RUN_COMPLETED` пара `approved_by_user_id`/`approved_at` null; в
  `APPROVED`, `RUNNING`, `PAUSED_ON_ERROR`, `COMPLETED_PENDING_REVIEW`, `ACCEPTED` она
  вся non-null; в `CANCELLED` она либо вся null (отмена до approval), либо вся non-null
  (отмена утверждённого run). Частично заполненная пара запрещена.
- `accepted_by_user_id IS NOT NULL`, `accepted_at IS NOT NULL`,
  `accepted_precondition_fingerprint IS NOT NULL` и
  `acceptance_outcome <> '{}'::jsonb` **iff** `status='ACCEPTED'`; иначе null/`{}`.
- `cancelled_by_user_id`, `cancelled_at` и непустой `cancel_reason` **iff**
  `status='CANCELLED'`; иначе null.
- В `PAUSED_ON_ERROR` обязательны `paused_at`, `paused_operation`, непустые
  `last_error_code` и `last_error_reference`; вне него все пять pause-полей,
  включая `stopped_participant_id`, null. При
  `paused_operation='PARTICIPANT_EXECUTION'` `stopped_participant_id` обязателен;
  при `paused_operation='ACCEPTANCE'` он обязательно null. Это выражается одним
  status/operation/stopped-participant CHECK.

`DRAFT` — только кратковременное внутреннее состояние transaction создания и не
возвращается как сохранённый PREVIEW result; следовательно, публичный cancel endpoint
адресует только сохранённые состояния, начиная с `DRY_RUN_COMPLETED`. Единственный
transition writer — service; trigger не нужен.

Ограничения и индексы: `UNIQUE(stage_code, stage0_cohort_run_id,
preview_fingerprint)`, `INDEX(stage0_cohort_run_id, stage_code, created_at DESC)`,
`INDEX(status, created_at DESC)`, `INDEX(stopped_participant_id)` и обычные индексы
всех FK, если не покрыты указанными composite indexes.

### 1.2 `ppr_stage_run_participants`

Одна строка — один Employee/Person, а не один education fragment.

| Поле | Тип, FK и ограничение |
|---|---|
| `stage_run_participant_id` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY`. |
| `stage_run_id` | `BIGINT NOT NULL REFERENCES ppr_stage_runs(stage_run_id) ON DELETE RESTRICT`. |
| `stage0_participant_id` | `BIGINT NOT NULL REFERENCES ppr_stage0_cohort_participants(stage0_participant_id) ON DELETE RESTRICT`. |
| `position` | `INTEGER NOT NULL CHECK (position >= 1)`. |
| `employee_id`, `person_id` | `BIGINT NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT` и `BIGINT NOT NULL REFERENCES persons(person_id) ON DELETE RESTRICT`. |
| snapshot | `participant_snapshot_version INTEGER NOT NULL DEFAULT 1 CHECK (participant_snapshot_version >= 1)`, `safe_fingerprint CHAR(64) NOT NULL CHECK (... SHA-256 ...)`. |
| `status` | `TEXT NOT NULL CHECK (status IN ('PENDING','COMPLETED','ERROR','SKIPPED_BY_DECISION'))`. `COMPLETED` означает drafts готовы либо exact already-applied подтверждён, а не canonical write. |
| `pmf_run_id` | nullable unique `BIGINT REFERENCES personnel_migration_runs(run_id) ON DELETE RESTRICT`; null допустим для `PENDING`, exact ALREADY_APPLIED или skip; completed participant с хотя бы одним новым fragment обязан иметь PMF run. |
| completion/error | nullable `completed_at`; nullable `error_code`, `error_reference`, `errored_at`. Error триада вся non-null **iff** `ERROR`; иначе вся null. |
| skip audit | nullable `skipped_by_user_id BIGINT REFERENCES users(user_id) ON DELETE RESTRICT`, `skipped_at TIMESTAMPTZ`, `skip_reason TEXT`; триада с непустой причиной **iff** `SKIPPED_BY_DECISION`. |

`completed_at IS NOT NULL` iff `status='COMPLETED'`; для иных статусов он null.
`ERROR` не имеет `completed_at`; успешный participant resume переводит строку в
`COMPLETED` и очищает всю error-триаду. `SKIPPED_BY_DECISION` не может иметь PMF
committed item. Подходящего неизменяемого participant-error audit/event контракта в
имеющейся PMF/PPR схеме для этого envelope не найден: история очищенной error-триады
остаётся только safe operational log history, а не заявляется сохранённой в participant
row. Service additionally проверяет точное соответствие Employee/Person Stage 0
participant.

Ограничения: `UNIQUE(stage_run_id, position)`,
`UNIQUE(stage_run_id, stage0_participant_id)`, `UNIQUE(stage_run_id, employee_id)`,
`UNIQUE(pmf_run_id)`. Индексы: `(stage_run_id, status, position)`,
`(stage_run_id, position)`, `(employee_id)`, `(person_id)`,
`(stage0_participant_id)`.

Позиции непрерывны только для frozen eligible cohort; service проверяет `count=N`,
`min=1`, `max=N` перед approval и acceptance. При `N=0` participants нет,
`current_position=0`, и после explicit approval run становится
`COMPLETED_PENDING_REVIEW`: это допустимый пустой результат, явно показанный HR_HEAD.

### 1.3 PMF links и фактические provenance paths

PMF schema уже содержит `personnel_migration_runs.metadata`, а item — только
`source_payload`, `draft_payload`, `validation_errors` (отдельного item metadata
нет). Используются ровно эти paths:

```text
personnel_migration_runs.metadata.stage2 = {
  envelope_run_id, participant_id, participant_snapshot_version,
  policy_version, deterministic_run_key
}
personnel_migration_items.source_payload.stage2 = {
  source_record_key, fragment_index, item_key, classification_outcome,
  policy_version, source_snapshot_fingerprint
}
personnel_migration_items.draft_payload.metadata.stage2 = {
  envelope_run_id, participant_id, participant_snapshot_version,
  source_record_key, fragment_index, policy_version, item_key
}
person_education.metadata.stage2 = same immutable provenance after commit
```

`draft_payload`/`source_payload` остаются PMF-only education data; envelope хранит
лишь safe IDs/counts/fingerprints. `person_education` также получает существующие
`import_batch_id`, `import_row_id`, `source_field`, `source_text`,
`parse_method`, `confidence`, `migrated_at`, `migrated_by` через существующий
plugin.

Deterministic keys:

- `deterministic_run_key = sha256('stage2-pmf-run:v1:' + stage_run_id + ':' +
  participant_id + ':' + participant_snapshot_version)`; хранится в
  `runs.metadata.stage2.deterministic_run_key`. Migration добавляет partial unique
  expression index `UNIQUE ((metadata #>> '{stage2,deterministic_run_key}')) WHERE
  metadata ? 'stage2'`.
- `item_key = sha256('stage2-pmf-item:v1:' + deterministic_run_key + ':' +
  source_record_key + ':' + fragment_index + ':' + source_snapshot_fingerprint)`; это
  `source_record_id`, и migration добавляет
  `UNIQUE(run_id, source_record_id) WHERE source_kind='stage2_control_list_fragment'`.
- PPR command id — фактический helper
  `build_pmf_commit_command_id(migration_run_id, migration_item_id)`: SHA-256 от
  `pmf-bridge-v1:commit:{run_id}:{item_id}` с префиксом `ppr-cmd-`.

Только fragment, требующий новой записи, создаёт PMF draft item. Exact
ALREADY_APPLIED item не создаёт: это participant-safe disposition, а не фиктивный
no-op payload. Нормальный Stage 2 переход — PMF run `draft → committed` и созданные
items `draft → committed` в одной acceptance transaction. При rollback они остаются
`draft`; Stage 2 не использует PMF `failed`, `voided`, `superseded` как pause.

ALREADY_APPLIED допускается только если ровно одна active `person_education` имеет:
совпадающие mapped canonical semantic fields, тот же `import_batch_id/import_row_id`
и точные `metadata.stage2.source_record_key`, `fragment_index`, `policy_version`,
`item_key`. Отсутствие/расхождение provenance, более одного match либо семантическое
отличие — `REVIEW_REQUIRED`/conflict, не ALREADY_APPLIED.

## 2. EDU-KIND-ALLOWLIST-v1

`app/ppr_migration/education_kind_policy.py` — pure classifier, возвращающий immutable
`EducationKindClassification(kind, outcome, reason_code, policy_version,
specific_markers)`. Он реализует WP-PPR-MIG-002 §2.4: приоритет specific marker,
conflicting markers → `REVIEW_REQUIRED`, никакого default и никакого автоматического
`other`.

Stage 2 v1 намеренно не предоставляет HR override для `other`. Fragment, которому
потребовался бы `other`, остаётся `REVIEW_REQUIRED`; HR исправляет authoritative
source и запускает новый PREVIEW либо явно исключает participant. Не добавляются
override persistence/API/UI/fingerprint branch. Policy version входит в envelope и
participant fingerprint, PMF provenance и protected PREVIEW response; его изменение
всегда требует нового PREVIEW и approval.

## 3. Operations и state machine

### 3.1 Точный двухфазный PREVIEW

`POST /api/personnel/ppr-migration/stage-2/education/preview` принимает только
`{stage0_cohort_run_id}`.

1. **Compute phase:** одна `REPEATABLE READ READ ONLY` transaction сканирует Stage 0
   participants в frozen position order; rechecks source/Employee/Person/lifecycle
   eligibility, loads normalized education, splits fragments, применяет policy, читает
   active canonical education и строит source/current/proposal/match comparison и safe
   fingerprint. Она не выполняет DML вообще.
2. **Persist phase:** отдельная короткая `SERIALIZABLE` write transaction берёт
   transaction advisory lock по `(stage_code, stage0_cohort_run_id)`, затем locks
   selected Stage 0 cohort/participants по position. Она повторно вычисляет тот же safe
   fingerprint и stale preconditions перед атомарным созданием envelope и eligible
   participants. Exact unique replay возвращает существующий run; иной recomputed
   fingerprint возвращает `409 STAGE2_PREVIEW_STALE`, не создавая второй run.
   Serialization failure повторяется только полным новым compute phase.

Persist phase может писать **только** Stage 2 envelope, participant и safe
blocker/count snapshot. Она не пишет canonical education и не создаёт PMF run/item.
Blocking errors/conflicts остаются видимыми и запрещают approval, но не PREVIEW.
Protected HR detail может показывать ФИО и Excel row для исправления; safe reports/logs
не содержат полного ИИН или raw payload.

### 3.2 Transition table и idempotency

| Operation | Allowed source state | Success / replay | Rejection |
|---|---|---|---|
| `approve` | `DRY_RUN_COMPLETED` | → `APPROVED`; replay в `APPROVED` возвращает run без нового audit row. | blockers `409 STAGE2_APPROVAL_BLOCKED`; stale `409 STAGE2_APPROVAL_STALE`; terminal/cancelled `409 STAGE2_INVALID_STATE`. |
| `execute-next` | `APPROVED`, `RUNNING` | один cursor participant; → `RUNNING` или `COMPLETED_PENDING_REVIEW`. Retry возвращает stored participant result и не создаёт второй PMF key/item. | paused `409 STAGE2_RUN_PAUSED`; completed `409 STAGE2_EXECUTION_COMPLETE`; terminal `409 STAGE2_INVALID_STATE`. |
| `resume` | только `PAUSED_ON_ERROR` с `paused_operation='PARTICIPANT_EXECUTION'` | locks stopped `ERROR` participant, очищает pause fields, переводит run в `RUNNING` и retry только этой позиции; после успеха продолжает с неё. | иной pause/не-paused `409 STAGE2_RUN_NOT_RESUMABLE`; stale `409 STAGE2_RESUME_STALE`; terminal `409 STAGE2_INVALID_STATE`. |
| `retry-accept` | только `PAUSED_ON_ERROR` с `paused_operation='ACCEPTANCE'` | повторяет всю atomic acceptance непосредственно из paused state; при успехе → `ACCEPTED`, без participant retry. | stale/conflict `409 STAGE2_ACCEPTANCE_STALE` и требуется новый PREVIEW; иной pause/не-paused `409 STAGE2_ACCEPTANCE_NOT_RETRYABLE`. |
| `skip` | `DRY_RUN_COMPLETED`: `PENDING` blocking participant; `PAUSED_ON_ERROR/PARTICIPANT_EXECUTION`: только stopped `ERROR` participant | audited → `SKIPPED_BY_DECISION`; pre-approval skip позволяет approval без blockers; paused execution skip advances cursor и возвращает `APPROVED` для explicit next execution. | `409 STAGE2_SKIP_NOT_ALLOWED` для acceptance-pause, `RUNNING`, completed, accepted, cancelled, уже `COMPLETED`/skipped participant или любого PMF-committed item. |
| `cancel` | сохранённые `DRY_RUN_COMPLETED`, `APPROVED`, `RUNNING`, `PAUSED_ON_ERROR`, `COMPLETED_PENDING_REVIEW` | → `CANCELLED` с actor/time/reason; тот же cancel replay возвращает saved state. PMF drafts не меняются. | accepted `409 STAGE2_RUN_ALREADY_ACCEPTED`; иной cancel reason `409 STAGE2_CANCEL_REPLAY_MISMATCH`. |
| `accept` | `COMPLETED_PENDING_REVIEW` | atomically → `ACCEPTED`; later replay возвращает stored `acceptance_outcome`. | pending/error/conflict `409 STAGE2_ACCEPTANCE_NOT_READY`; stale `409 STAGE2_ACCEPTANCE_STALE`; cancelled `409 STAGE2_INVALID_STATE`. |

Все operations дополнительно возвращают
`403 PPR_STAGE2_EDUCATION_PERMISSION_DENIED` при отсутствии permission/HR_HEAD role и
`403 STAGE2_COHORT_OUT_OF_SCOPE` при server-side scope failure. Frontend не принимает
authorization решение.

Approval locks envelope/participants и rechecks fingerprint/policy. Cohort, порядок,
mapping, policy или field set меняются только через новый PREVIEW/APPROVED. Для
recoverable participant-execution error resume заново строит snapshot stopped
participant и требует его точного равенства frozen fingerprint; иначе
`STAGE2_RESUME_STALE` и нужен новый PREVIEW. Acceptance stale/conflict не образует
resumable pause: run остаётся `COMPLETED_PENDING_REVIEW`, response требует нового
PREVIEW, а не `retry-accept`.

### 3.3 Sequential draft execution, rollback и acceptance

`execute-next` создаёт/проверяет один deterministic PMF run для cursor participant и
PMF drafts только для новых education records, потом отмечает participant
`COMPLETED`. Canonical education не меняется. У каждого participant своя transaction;
ранние drafts сохраняются.

Worker/resume error откатывает исходную participant transaction. Затем отдельная
service transaction locks envelope, потом stopped participant, и conditionally меняет
run на `PAUSED_ON_ERROR/PARTICIPANT_EXECUTION` только если он всё ещё captured expected
`APPROVED` или `RUNNING`. Она ставит participant в `ERROR` и записывает safe details.

Transient acceptance failure откатывает исходную atomic acceptance transaction. Отдельная
service transaction locks только envelope и conditionally меняет
`COMPLETED_PENDING_REVIEW` на `PAUSED_ON_ERROR/ACCEPTANCE`; конкретный participant не
назначается. Stale/conflict acceptance не является resumable: после rollback run
остаётся `COMPLETED_PENDING_REVIEW`, а caller получает `409 STAGE2_ACCEPTANCE_STALE` и
должен создать новый PREVIEW. Обе служебные transactions не перезаписывают
`CANCELLED`/`ACCEPTED`: concurrent retry/cancel/accept, изменивший expected state,
выигрывает и перечитывается. Если сама служебная transaction не удалась, service делает
safe structured operational log и возвращает `500 STAGE2_PAUSE_RECORDING_FAILED`; он не
утверждает, что pause сохранён.

`accept` сначала locks envelope и проверяет `status='ACCEPTED'` **до** проверки нового
short-lived acceptance fingerprint. Для ACCEPTED replay он немедленно возвращает
сохранённый `acceptance_outcome`, даже после истечения исходного fingerprint, и не
запускает PMF/PPR command либо event. Для неповторного accept это одна `SERIALIZABLE`
transaction: locks full cohort, повторно вычисляет server-derived counts и acceptance
fingerprint, сравнивает UI-provided fingerprint, rechecks source/canonical snapshots и
PMF drafts, затем вызывает existing education plugin/PPR gateway. Canonical records,
PMF item/run statuses и PPR events commit together. Conflict/stale/PPR error откатывает
всё, оставляя items `draft`. Double submit cannot create a second record/event.

## 4. Locks и stale protection

Единый lock order не инвертируется:

```text
envelope run → participants → source rows / normalized records → Employee → Person
→ canonical education → PMF runs/items → existing PPR locks
```

Collections сортируются по technical ID (participants — по position). Применимые
подмножества:

| Operation | Locks в global order |
|---|---|
| compute PREVIEW | нет; `REPEATABLE READ READ ONLY`. |
| persist PREVIEW | advisory cohort key, затем Stage 0 selected rows/source rows → Employee → Person; pre-existing envelope/participant нет. |
| approve | envelope → all participants → source/normalized rows → Employee → Person → canonical education. |
| execute-next/resume | envelope → cursor/stopped participant → source/normalized rows → Employee → Person → canonical education → PMF run/items → PPR locks. |
| skip | envelope → selected participant. |
| cancel | envelope. |
| accept | envelope → all participants → source/normalized rows → Employee → Person → canonical education → PMF runs/items → PPR locks. |
| retry-accept | envelope → all participants → source/normalized rows → Employee → Person → canonical education → PMF runs/items → PPR locks. |
| post-rollback pause: participant execution | envelope → stopped participant. |
| post-rollback pause: acceptance | envelope only. |

Fingerprint canonical JSON не содержит raw source/name/full IIN: Stage 0/source
fingerprints; Employee/Person/PPR versions; batch/row/normalized IDs/status/update
tokens; source key/fragment index; active education identity/`updated_at`;
parser/mapping versions; policy version и classification outcome. Source
ownership/removal/rebinding, canonical token, lifecycle или policy drift — stale.
Cohort/order/mapping/policy change всегда требует нового PREVIEW/approval.

## 5. RBAC и API

Migration создаёт `PPR_STAGE2_EDUCATION_MANAGE`, grant только `HR_HEAD`. Каждый
endpoint дополнительно проверяет active primary role `HR_HEAD` и server-computed org
scope каждого Employee. Scope failure показывается как «Прогон недоступен в вашем
подразделении», с safe code `STAGE2_COHORT_OUT_OF_SCOPE`.

| Endpoint | Request / response contract |
|---|---|
| `POST /api/personnel/ppr-migration/stage-2/education/preview` | `{stage0_cohort_run_id}` → protected comparisons, safe counts, run и `preview_fingerprint`; two-phase contract выше. |
| `GET .../runs/{run_id}` | envelope, progress, participants, PMF fragment comparisons, safe errors и stored acceptance outcome. |
| `POST .../runs/{run_id}/approve` | `{}` → transition/replay из table. |
| `POST .../runs/{run_id}/execute-next` | `{}` → ровно один stored/replayed cursor result. |
| `POST .../runs/{run_id}/resume` | `{}` → «Продолжить обработку»: retry только stopped participant-execution position. |
| `POST .../runs/{run_id}/retry-accept` | `{}` → «Повторить принятие»: повторить всю atomic acceptance только после transient acceptance pause. |
| `POST .../runs/{run_id}/participants/{participant_id}/skip` | `{reason}` → только допустимый audited skip. |
| `POST .../runs/{run_id}/cancel` | `{reason}` → audited cancellation/replay. |
| `GET .../runs/{run_id}/acceptance-summary` | server-recomputed employee/record/kind counts, skipped/conflict counts и short-lived `acceptance_fingerprint`; без write. |
| `POST .../runs/{run_id}/accept` | `{acceptance_fingerprint}` → atomic accepted outcome или stored ACCEPTED replay. |

Pydantic safe reports отделены от protected HR comparisons. Ни один response не содержит
full IIN/raw source. UI не может подменить permission скрытием кнопки.

## 6. HR_HEAD UI и visibility

Extend existing `/directory/personnel/ppr-migration` with
`Stage2EducationPanel`. Russian textual statuses: «Проверка завершена»,
«Утверждён к запуску», «Выполняется», «Остановлен из-за ошибки», «Готов к принятию»,
«Этап принят», «Черновик подготовлен», «Данные записаны», «Требуется проверка»,
«Исключён по решению». Цвет — только дополнительный сигнал.

Protected table groups fragment cards по employee и Excel source row. Карточка показывает
fragment index, «В контрольном списке», «Сейчас в карточке», «Будет записано», policy
outcome/reason и раскрываемые safe technical details. Soft line break fragments остаются
под той же source row и никогда не образуют другого employee. Full IIN не отображается.

До `ACCEPTED` employee paths читают только active canonical `person_education`;
HR_HEAD видит PMF drafts только при permission/scope. После acceptance normal employee
card rules показывают canonical records. При participant-execution pause UI показывает
текстовую кнопку «Продолжить обработку» и position; при acceptance pause — отдельную
кнопку «Повторить принятие», без ложного указания employee. Stale/conflict acceptance
показывает «Требуется новая проверка» и не показывает ни одну из этих кнопок. Accessible
custom confirmation dialog загружает
только server-derived acceptance summary и явно называет stage, employee count, records
by kind, skipped/conflict counts, отсутствие перезаписи непустых canonical values,
atomicity и отсутствие full IIN. Кнопки «Отмена»/«Принять этап»; in-flight guard
исключает второй submit.

## 7. Test matrix и visual pilot

| Level | Required coverage |
|---|---|
| Unit | every allowlist branch, priority/conflict, no `other`, split/fingerprint/dedup и exact provenance match. |
| Service | two-phase read/write PREVIEW, no PMF/canonical write in PREVIEW, approval blockers, keys/replays, cursor rules, skip/cancel guards, participant-vs-acceptance pause и conditional post-rollback recording. |
| PostgreSQL | all FKs/checks/unique/indexes including pause discriminator/error clearing, PMF JSON paths/keys, Stage0 links, SERIALIZABLE stale/concurrency, lock-order characterization и acceptance rollback/replay; only `corpsite_test`. |
| API/RBAC | permission/primary role/org scope, protected/safe redaction, Russian errors, every transition/listed 403/409 code, ACCEPTED replay after fingerprint expiry. |
| Frontend | Russian states/reasons, grouped fragments, no IIN, progress, «Продолжить обработку» versus «Повторить принятие», accept dialog/counts и accepted screen. |
| Security | no raw payload/full IIN в reports/logs; employee cannot read drafts. |

Synthetic visual pilot в одном permitted org scope включает: (1) одного employee с двумя
fragments в одной soft-line-break cell, разными indices и одной Excel row; (2) exact
already-applied canonical/provenance match; (3) visible canonical conflict; (4)
ambiguous marker, уже `REVIEW_REQUIRED` в PREVIEW и блокирующий approval до
authoritative-source correction либо explicit skip; (5) **отдельного** approved clean
participant, получающего controlled post-approval worker error,
`PAUSED_ON_ERROR/PARTICIPANT_EXECUTION` и resume только после восстановления исходного
frozen participant fingerprint; (6) отдельную transient acceptance failure с
`PAUSED_ON_ERROR/ACCEPTANCE` и полной atomic retry; (7) acceptance stale/conflict,
требующий нового PREVIEW, а не retry. Conflict также исправляется или skipped до
acceptance. Любое изменение
cohort/order/mapping/policy использует новый PREVIEW/approval, не простой resume. Только
synthetic `corpsite_test` data.

## 8. Exact future file map и visual-review readiness

| Path | Responsibility |
|---|---|
| `alembic/versions/s2e1d2u3c4a5_ppr_stage2_education_envelope.py` | schema, constraints, expression/partial indexes и permission grant. |
| `app/db/models/ppr_stage_run.py` | ORM и status vocabulary. |
| `app/ppr_migration/education_kind_policy.py` | pure v1 classifier. |
| `app/services/ppr_stage2_education_service.py` | Stage 2 state, locks, PMF и acceptance operations. |
| `app/api/ppr_stage2_education_router.py`, `app/api/ppr_stage2_education_schemas.py` | contracts, RBAC и scope. |
| `app/security/ppr_stage2_permissions.py`, `app/security/admin_permissions.py`, `app/main.py` | permission и router registration. |
| `corpsite-ui/app/directory/personnel/ppr-migration/Stage2EducationPanel.tsx` | HR_HEAD UI/dialog. |
| `tests/test_ppr_stage2_education_{unit,postgres,api}.py`, `Stage2EducationPanel.test.tsx` | test matrix. |
| `scripts/dev/seed_stage2_education_visual_pilot.py` | synthetic test-only fixture. |

Local readiness: проверить только `127.0.0.1:5432/corpsite_test`; upgrade test DB;
run PG/unit/API/frontend tests; seed only synthetic pilot; start backend с test DSN и
frontend API base `http://127.0.0.1:8011`; проверить `/health`, `/openapi.json`,
HR_HEAD login и `/directory/personnel/ppr-migration`. Visual Review готов лишь когда
pilot виден в правильном org scope, drafts скрыты от employee, acceptance atomic/replay
safe и все reports mask full IIN.

Out of scope: implementation, migration/DML, production connection, Stage 3 и изменения
approved Stage 0/1/2 documents.
