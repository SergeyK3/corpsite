# WP-PPR-MIG-004 — Stage 3: перенос обучения и повышения квалификации

| Параметр | Значение |
|---|---|
| Статус | **Approved — Ready for Stage 3 Backend Implementation** |
| Дата | 2026-09-10 |
| Scope | `TrainingCandidate` → PMF proposals → `person_training` |
| Не входит | Education, назначения/приказы, production-DML |
| Основание | `WP-PPR-MIG-003`, Stage 2 Education, `WP-CL-009` |

## 1. Цель и фиксированные правила

Stage 3 переносит рассмотренные HR_HEAD сведения раздела «Обучение и повышение квалификации» в
person-owned `person_training`. Паттерн: frozen Stage-0 cohort, preview без canonical write,
сохраняемые PMF drafts, явное approval/accept и PPR bridge.

1. Существующий `person_training` никогда не перезаписывается. Stage 3 допускает только
   `add_training`, а не update/supersede/void.
2. Stage 3 v1: один source fragment образует **0..1** proposal. Декомпозиция fragment в 0..N
   отложена за пределы Stage 3 v1 и требует нового versioned policy/work package.
3. `READY_FOR_HR_REVIEW` возникает только из полностью детерминированного candidate: его
   `matched_person_id` точно равен `person_id` frozen participant; нет `field_issues`; непустой
   `training_title`; valid `completion_date` **или**
   valid `completion_year`; deterministic `training_kind`. Kind равен нормализованному
   `training_type`, а при его отсутствии — literal `other`. Writer требует non-null `training_kind`;
   title/date-or-year — более строгий Stage-3 safety rule, согласованный с clean fixture
   (title + year без provider/hours/certificate). Provider, hours, certificate optional, но если
   заполнены, обязаны быть valid and exact-normalized.
4. `normalization_ready` необходим, но не достаточен. Любая incomplete запись — только skip с
   причиной; ручное заполнение/исправление proposal запрещено.
5. Incomplete, ambiguous, invalid/unmatched person и possible/contradictory duplicate требуют
   решения HR_HEAD; автоматический execution/apply для них запрещён.
6. Изменение source snapshot, person match/binding, policy, cohort participant или relevant
   canonical training после preview делает предложение stale и запрещает accept.
7. Certificate number restricted: без `VIEW_TRAINING_CERTIFICATE_DETAILS` поле отсутствует во всех
   preview/list/summary DTO, а не приходит как `null` или mask.

## 2. Existing assets и implementation gap

| Слой | Есть сейчас | Что требуется Stage 3 |
|---|---|---|
| Source | `TrainingNormalizationService`/`TrainingCandidate`, row/column/fragment provenance и readiness | Читать только frozen import snapshot; не перепарсивать mutable workbook. |
| Canonical | `person_training`, `TrainingRecord`, `PprSectionApplicationService.add_training`, events `PPR-TRAINING` | Использовать только через PMF bridge; прямой insert запрещён. |
| Bridge | `personnel_migration_ppr_bridge` уже map-ит `record_kind='training'` и вызывает `add_training_participating` в shared UoW | Добавить Stage-3 policy/provenance validation и idempotency tests. |
| Envelope | `ppr_stage_runs`/participants и API Stage 2; DDL ограничен `stage_code='education'` и EDU policy | Additive migration только общей схемы: добавить `stage_code='training'`, сохранив Education constraints/contracts без изменения. |
| Permissions | `PPR_STAGE2_EDUCATION_MANAGE`, HR_HEAD guard; military restricted details | Новые `PPR_STAGE3_TRAINING_MANAGE` и certificate-details grant. |
| Flags | PMF/PPR bridge feature gate | Три новых disabled-by-default Stage-3 flags; apply также требует bridge flag. |

## 3. Persistent model

### 3.1 Envelope

Рекомендуется generalise `ppr_stage_runs`/`ppr_stage_run_participants` additive migration:

* `stage_code='training'`, `policy_version='TRAINING-PROPOSAL-v1'`;
* сохраняются Stage-2-compatible run fields: frozen `stage0_cohort_run_id`, safe snapshot,
  preview fingerprint, actor/timestamp approval/accept/cancel/pause, acceptance outcome;
* participant — один frozen Stage-0 participant (`employee_id`, `person_id`, snapshot version,
  position, safe fingerprint) и не более одного PMF draft run;
* unique constraints stay independent by `stage_code`; existing education rows/contracts remain valid.

Используются **только общие** `ppr_stage_runs` и `ppr_stage_run_participants`; отдельные
Stage-3 tables не создаются. Additive migration обязана проверить и изменить только нужные
constraints/indexes: (1) run CHECK допускает исключительно пары `(education, EDU-KIND-ALLOWLIST-v1)`
и `(training, TRAINING-PROPOSAL-v1)`; (2) common status/actor/timestamp/pause/accept/cancel CHECKs
сохраняются для обоих stage codes, а service asserts expected code; (3) preview uniqueness остаётся
`(stage_code, stage0_cohort_run_id, preview_fingerprint)`, participant uniqueness — per run;
(4) Stage-2 and Stage-3 partial PMF metadata/source-key indexes имеют разные predicates/keys;
(5) FK participant→run и all selects/updates исключают cross-stage ownership. Canonical
`person_training` schema менять не требуется.

### 3.2 PMF proposal

Для executable proposal создаётся один PMF draft run на participant:

```text
domain_code = education  # existing shared PMF plugin
deterministic_run_key = stage3-pmf-run:v1:{run}:{participant}:{snapshot_version}
source_kind = stage3_training_proposal
source_record_id = {source_record_key}:{fragment_index}
record_kind = training
```

`education` is the existing shared PMF domain: its registered plugin owns both
`person_education` and `person_training`; Stage 3 is distinguished by
`record_kind = training` and its Stage-3 provenance. No unsupported synthetic
`training` PMF domain is introduced.

`draft_payload` содержит canonical TrainingRecord shape: `training_kind`, `title`,
`organization_name`, `hours`, `started_at`, `completed_at`, `certificate_number`,
`document_date`, `employee_context_id`, metadata. `source_payload` неизменно хранит
import/profile/sheet/row/column, fragment index, parser/policy/candidate/proposal fingerprints,
decision, dedup outcome and raw-fragment hash. В PMF не хранить raw fragment: только required
structured payload, provenance and hash. Raw source/certificate plaintext не включать в ordinary
audit or list DTO.

Добавить partial unique `(run_id, source_record_id)` for `stage3_training_proposal` и unique
deterministic PMF-run key: resume/retry не создаёт второй draft item.

### 3.3 States

```text
DRY_RUN_COMPLETED → APPROVED → RUNNING → COMPLETED_PENDING_REVIEW → ACCEPTED
                         ↘ PAUSED_ON_ERROR ── resume/retry ──┘
any workable non-ACCEPTED state → CANCELLED
```

Participants: `PENDING`, `COMPLETED`, `ERROR`, `SKIPPED_BY_DECISION`. A blocked participant must
be skipped with reason; it is never silently treated as successful empty import. Proposal outcomes:
`READY_FOR_HR_REVIEW`, `REVIEW_REQUIRED`, `DUPLICATE_CANONICAL`, `DUPLICATE_IN_RUN`, `STALE`,
`SKIPPED_BY_DECISION`, `ACCEPTED_TO_PMF`, `COMMITTED`.

## 4. Fingerprint and dedup policy

SHA-256 over canonical JSON (stable ordering, normalised strings/dates, explicit nulls and version).

| Fingerprint | Inputs | Purpose |
|---|---|---|
| Source/candidate | import/profile version; row/column/fragment identity; raw hash; parsed fields; person match; parser version | Source/match staleness. |
| Proposal | candidate fingerprint; proposal index; target payload; decision/policy | Stable proposal identity. |
| Dedup | person; normalized provider/title; completed date or year; hours; keyed hash of certificate; policy | canonical/in-run duplicate detection. |
| Participant | snapshot version; all candidate/proposal fingerprints; relevant canonical training projection | preview/execute staleness. |
| Preview/acceptance | frozen cohort and policy / preview plus decision-set, PMF items and current canonical projection | explicit preconditions. |

Compare active canonical rows of the same person and all Stage-3 proposals. No fuzzy matching,
aliases or hour rounding: comparison is only exact normalisation of strings, dates and decimal
numbers. Missing values are not wildcards; date wins over year. Certificate dedup uses versioned
server-side HMAC; its secret is not stored in DB, PMF metadata, fingerprints or events. Plaintext
certificate never appears in a fingerprint/event.

| Match | Handling |
|---|---|
| Exact: all comparable populated values match, none conflicts | `DUPLICATE_CANONICAL` or `DUPLICATE_IN_RUN`; no PMF item. |
| Possible: provider/title match but date/year/hours/certificate missing or conflicts | `REVIEW_REQUIRED`; no automatic apply. |
| Distinct: sufficient non-conflicting evidence | `READY_FOR_HR_REVIEW`; still requires explicit approval. |
| Contradictory: e.g. one certificate for different provider/title/date | `REVIEW_REQUIRED`; preserve source, no auto-fix. |

## 5. Preview, review and apply flow

1. **Dry-run preview**: HR_HEAD previews a frozen Stage-0 cohort under repeatable-read/read-only
   transaction. It creates no stage run/participants, PMF draft, `person_training` or personnel event;
   it returns preview fingerprint and redacted proposed disposition only.
2. **Создать запуск**: separate explicit HR_HEAD action serializably recomputes the dry-run preview
   using the submitted fingerprint. Only equality persists run/participants; mismatch is stale and
   requires a new dry-run preview. This action still makes no canonical write.
3. Review screen shows provenance, parsed non-sensitive fields, issues, duplicate evidence, current
   canonical non-sensitive summary and stale markers. Certificate is conditionally omitted.
4. HR_HEAD explicitly approves after each unresolved reviewer item is skipped with required reason.
   Approval rejects stale/review-required/possible or contradictory duplicate/unmatched items.
5. `execute-next` locks one participant, re-derives fingerprints and writes approved distinct
   proposal(s) only to PMF draft. It pauses atomically on error; resume repeats same position.
6. Acceptance summary supplies an acceptance fingerprint. `accept` serializably locks run,
   participants and PMF items; it rechecks source, policy, person binding, all decisions, duplicate
   set and canonical fingerprints.
7. Only then PMF `commit_run` uses existing PPR bridge; it materializes PPR if necessary and calls
   `PprSectionApplicationService.add_training_participating`. PMF item, `person_training` and
   `personnel_record_events` are one UoW.
8. Any changed input/concurrent canonical row rolls back all acceptance writes and conditionally
   pauses run in separate post-rollback transaction. A new preview/review is required. Deterministic
   PMF/item/PPR command ids make retry idempotent; no batch auto-accept exists.

## 6. Proposed API

Prefix: `/personnel/ppr-migration/stage-3/training`.

| Route | Action |
|---|---|
| `POST /preview` | Dry-run only: `stage0_cohort_run_id`; read-only compute, zero writes, returns preview fingerprint. |
| `POST /runs` | Explicit «Создать запуск»: cohort id plus preview fingerprint; serializable recomputation persists run/participants only on equality. |
| `GET /runs/{id}` | Redacted run, participants and proposal dispositions. |
| `POST /runs/{id}/approve` | Explicit HR_HEAD approval after blockers resolved/skipped. |
| `POST /runs/{id}/execute-next`, `/resume` | One participant → PMF drafts; no canonical write. |
| `POST /runs/{id}/participants/{pid}/skip` | Requires reason and records decision. |
| `POST /runs/{id}/cancel` | Requires reason. |
| `GET /runs/{id}/acceptance-summary` | Counts, redacted evidence, acceptance fingerprint. |
| `POST /runs/{id}/accept`, `/retry-accept` | Explicit acceptance fingerprint; serializable canonical commit. |

No client may supply `person_id`, canonical payload or duplicate disposition. Mutating operations
carry idempotency/correlation identifiers. Responses expose safe code/reference only.

## 7. Permissions, scope, flags and UI

* `PPR_STAGE3_TRAINING_MANAGE`: HR_HEAD plus explicit grant, distinct from Stage 2. All routes also
  require personnel visibility; org scope fails closed unless every cohort unit is visible.
* `VIEW_TRAINING_CERTIFICATE_DETAILS` controls detailed source/draft/canonical DTOs independently
  of apply and is assigned to `HR_HEAD`. No grant: field absent, never client-side hidden plaintext.
* Default-false flags: `PPR_STAGE3_TRAINING_PREVIEW_ENABLED`,
  `PPR_STAGE3_TRAINING_EXECUTION_ENABLED`, `PPR_STAGE3_TRAINING_ACCEPT_ENABLED`. Accept also needs
  `PPR_PMF_BRIDGE_ENABLED`; no direct-writer fallback.
* Build a protected migration workspace, not personal-card editor: dry-run preview with zero-write
  disclosure and separately enabled «Создать запуск» action bound to preview fingerprint; then
  participant queue, dedup/issue evidence, required skip reasons, stale banners and explicit
  fingerprint-bound acceptance. Before `ACCEPTED` the card may show the separate staging-review
  block defined by [WP-PPR-MIG-004A](WP-PPR-MIG-004A-training-staging-review-and-validity.md); it
  is not `person_training`, PMF acceptance or canonical adoption. The canonical card section reads
  accepted data only through the current `PPR-TRAINING` composite read.

## 8. Audit and provenance

Migration audit records preview/approve/skip/execute/pause/resume/cancel/accept with actor,
timestamp, run/participant/proposal key, reason, safe fingerprints and correlation id. Use PMF
audit for proposal lifecycle; omit raw source/certificate from generic journals.

Bridge commit emits existing `personnel_record_events`: section `PPR-TRAINING`, event
`PPR_SECTION_ADDED`, table/record id and deterministic command id. Event metadata links PMF and
Stage-3 identifiers, policy and source hash. Skips/stale/rejections create migration audit only,
not PPR section events.

## 9. Test plan

Unit/contract tests:

* one fragment → 0/1 proposal only; attempted 0..N decomposition is rejected/deferred;
* precise READY mandatory matrix: match, no issues, title, date-or-year and deterministic kind;
  clean parsing cannot approve itself; incomplete/review/unmatched/ambiguous paths only skip;
* exact-normalised (no fuzzy/alias/rounding) possible/contradictory/in-run dedup, null semantics,
  versioned certificate HMAC, secret absence from DB/events, and certificate redaction;
* deterministic fingerprints and stale source/policy/person/canonical changes;
* flags and permission/scope fail closed; idempotent preview/execute/accept retry.

Required PostgreSQL integration tests:

* dry-run preview against frozen cohort produces zero writes to stage/PMF/canonical/event tables;
  explicit create-run serializably rechecks fingerprint and persists only run/participants;
* expanded common CHECK/UNIQUE constraints reject education-with-training-policy and
  training-with-education-policy; Stage-2 partial indexes/keys and Stage-3 keys coexist;
* serializable create-run constraints/advisory lock and deterministic PMF indexes tolerate retries;
* execute creates PMF drafts only; accept creates exactly one canonical training row and matching
  `PPR-TRAINING` event atomically through bridge;
* existing training remains unchanged; duplicate gets no PMF/canonical item;
* source/profile/person-binding/canonical change after preview rolls back acceptance completely;
* PPR/PMF command idempotency prevents duplicate row/event; disabled flags prohibit every action;
* no production-DML/seed route is introduced;
* mandatory Stage-2 Education PostgreSQL and API regression suite passes unchanged after common
  schema extension: education preview/create-run-equivalent, approval, execute/resume, skip,
  cancellation, stale acceptance, PMF bridge and existing permission/scope contracts.

## 10. Closed implementation decisions

* Stage 3 v1 is 0..1 proposal per source fragment; no PMF proposal editing, fuzzy matching or
  decomposition. A кадровик may correct the normalized/staging record through the controlled review
  workflow in [WP-PPR-MIG-004A](WP-PPR-MIG-004A-training-staging-review-and-validity.md), but may
  not edit a PMF proposal directly. A checked staging record is the input to the next Stage 3 preview;
  any later staging correction makes a dependent preview/proposal stale and requires a new preview.
* Incomplete candidate is skipped with a mandatory reason. `VIEW_TRAINING_CERTIFICATE_DETAILS` is
  distinct and assigned to HR_HEAD; certificate remains absent without it.
* Shared stage envelope is extended additively, with the cross-stage CHECK/UNIQUE regression set
  in §9; it does not alter Education policy, statuses, API behaviour or data.
* Only structured payload, provenance and hashes persist in PMF; ordinary audit/list DTOs never carry
  raw fragment. Certificate comparison is versioned server-side HMAC with secret outside DB/events.

## 11. Non-actions

This is an implementation plan only. No code, migration, endpoint, test, DML, seed, commit, push
or production action is authorised or performed.
