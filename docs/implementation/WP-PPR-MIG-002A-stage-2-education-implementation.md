# WP-PPR-MIG-002A — Stage 2 Education: implementation plan

| Статус | **Draft — Ready for Implementation Review** |
|---|---|
| Основание | [WP-PPR-MIG-002](WP-PPR-MIG-002-stage-2-education.md), Stage 0 frozen cohort, PMF / `EducationMigrationPlugin` |
| Граница | Только Stage 2 «Образование»; не Stage 3 и не иной section. |

## 1. Architecture and migration

Stage 2 creates a thin common PPR stage-run envelope. Envelope owns the frozen section
cohort, participant cursor, execution/acceptance state and safe snapshots. Existing PMF
remains the sole owner of `personnel_migration_runs/items`, education source/draft
payload, provenance, `EducationMigrationPlugin` and canonical PPR commands. Envelope
tables must never contain raw source text, full IIN, FIO or education payload JSON.

Stage 1 `ppr_stage1_general_*` is scalar-Person storage and is neither reused nor
extended. Stage 0 cohort is immutable prerequisite; Stage 2 freezes its own section
snapshot from it.

One future migration is exact: `alembic/versions/s2e1d2u3c4a5_ppr_stage2_education_envelope.py`,
with `down_revision = 's1g0e1n2r3a4'` (current head). It adds the tables/permission
below; it does not alter historical migrations, Stage 0/1 tables or canonical education.

### 1.1 `ppr_stage_runs`

| Field | Type and constraint |
|---|---|
| `stage_run_id` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY`. |
| `stage_code` | `TEXT NOT NULL CHECK (stage_code='education')`; another stage requires an approved expansion. |
| `stage0_cohort_run_id` | `BIGINT NOT NULL REFERENCES ppr_stage0_cohort_runs ON DELETE RESTRICT`. |
| `status` | `TEXT NOT NULL CHECK` over `DRAFT`, `DRY_RUN_COMPLETED`, `APPROVED`, `RUNNING`, `PAUSED_ON_ERROR`, `COMPLETED_PENDING_REVIEW`, `ACCEPTED`, `CANCELLED`. |
| `preview_fingerprint` | lowercase SHA-256 `CHAR(64) NOT NULL`. |
| `policy_version` | `TEXT NOT NULL DEFAULT 'EDU-KIND-ALLOWLIST-v1'`. |
| `current_position` | `INTEGER NOT NULL DEFAULT 1 CHECK (current_position>=1)`. |
| actor/times | restrictive `created_by_user_id`, nullable `approved_by_user_id`, `accepted_by_user_id`; `created_at`, nullable approved/accepted/paused/cancelled timestamps. |
| safe state | `safe_snapshot JSONB NOT NULL DEFAULT '{}'`, nullable `last_error_code`, `last_error_reference`; no PII/raw data. |

`UNIQUE(stage_code, stage0_cohort_run_id, preview_fingerprint)` is replay fence.
Indexes: `(stage0_cohort_run_id,stage_code,created_at DESC)` and `(status,created_at)`.
Checks require accepted actor/time iff `ACCEPTED`, and approval actor/time for states
after `APPROVED`. Transition service is the sole status writer; no trigger.

### 1.2 `ppr_stage_run_participants`

One row is one Employee/Person, never one fragment.

| Field | Type and constraint |
|---|---|
| `stage_run_participant_id` | identity `BIGINT` PK. |
| `stage_run_id`, `stage0_participant_id` | restrictive FKs to envelope and Stage 0 participant. |
| `position` | `INTEGER NOT NULL CHECK(position>=1)`. |
| `employee_id`, `person_id` | restrictive FKs; copied technical anchors only. |
| `participant_snapshot_version`, `safe_fingerprint` | `INTEGER NOT NULL DEFAULT 1 CHECK(>=1)`, required SHA-256. |
| `status` | check `PENDING`, `COMPLETED`, `ERROR`, `SKIPPED_BY_DECISION`; completed means drafts ready, not canonical. |
| `pmf_run_id` | nullable unique restrictive FK to `personnel_migration_runs`; one PMF education run per participant. |
| execution state | nullable completion/error safe fields; skip reason/actor/time all required iff skipped. |

Constraints: unique `(stage_run_id,position)`, `(stage_run_id,stage0_participant_id)`,
`(stage_run_id,employee_id)`, and `(pmf_run_id)`. Indexes: `(stage_run_id,status,position)`,
`(employee_id)`, `(person_id)`. Repository verifies copied Employee/Person match Stage 0.

### 1.3 PMF links without payload duplication

The participant's PMF run has `domain_code='education'`, matching `person_id` and
`employee_context_id`. Its existing PMF items represent every fragment. Only metadata
is added to PMF run/item provenance:

```text
stage_run_id, stage_run_participant_id, participant_snapshot_version,
education_kind_policy_version, classification_outcome, source_record_key, fragment_index
```

`source_payload`/`draft_payload` remain exclusively in PMF. A link/payload fourth table
is prohibited.

## 2. EDU-KIND-ALLOWLIST-v1

Create pure `app/ppr_migration/education_kind_policy.py` returning immutable
`EducationKindClassification(kind, outcome, reason_code, policy_version,
specific_markers)`. It implements exactly WP-PPR-MIG-002 §2.4 per parser fragment:
specific marker priority, conflicting markers → `REVIEW_REQUIRED`, no default and no
automatic `other`. It uses Unicode/casefold matching and emits safe codes, not marker
text.

`EDU-KIND-ALLOWLIST-v1` is written into envelope `policy_version`, participant safe
fingerprint, PMF provenance and protected preview response. A changed policy version
makes prior preview stale and requires new PREVIEW/APPROVED. `other` can arise only
from a separately audited explicit HR action; `execute-next` has no branch for it.

## 3. Operations and state transitions

### PREVIEW

`POST /api/personnel/ppr-migration/stage-2/education/preview` accepts only
`{stage0_cohort_run_id}`. Under `REPEATABLE READ READ ONLY`, it loads Stage 0
participants in position order, rechecks source/Employee/Person/lifecycle eligibility,
selects education normalized records, splits fragments, classifies policy, loads active
canonical education and forms source/current/proposal/match comparisons. It has no DML.

After the read scan, a short write transaction rechecks fingerprint and persists envelope
and participants as `DRY_RUN_COMPLETED`. Exact unique fingerprint returns existing run.
Blocking errors/conflicts remain visible and prohibit approval; they do not prohibit
preview. Protected HR_HEAD detail may show name and Excel row for correction; safe
reports/logs never contain full IIN/raw payload.

### Approval and sequential draft execution

`approve_stage2_run` locks envelope+participants and permits only
`DRY_RUN_COMPLETED`; all blockers must be corrected or explicitly
`SKIPPED_BY_DECISION`. It rechecks fingerprint/policy then records `APPROVED` actor/time.
Cohort/order/mapping/policy/field-set changes return `409 STAGE2_APPROVAL_STALE`.

`execute_next_stage2_run` permits `APPROVED`/`RUNNING`, processes only cursor position,
creates or verifies its PMF run and one PMF draft item per fragment, then marks the
participant `COMPLETED`, increments cursor and moves to `RUNNING` or
`COMPLETED_PENDING_REVIEW`. Writes are draft-only.

Failure rolls back that participant transaction. A separate short transaction locks
only envelope/failed participant and records `ERROR`, `PAUSED_ON_ERROR`, cursor and safe
reason. `resume_stage2_run` permits only `PAUSED_ON_ERROR`, re-evaluates the same
position and continues only after its success. Earlier drafts stay unchanged.
`skip_stage2_participant` is explicit HR_HEAD action with reason/actor/time and appears
in report/acceptance dialog; it is never automatic.

### Acceptance

`accept_stage2_run` permits only `COMPLETED_PENDING_REVIEW`. In one `SERIALIZABLE`
transaction it locks envelope/full cohort, rechecks source/canonical fingerprints and
duplicate/match preconditions, then commits ready PMF items through existing education
plugin/PPR gateway. Equal canonical record is replay/no write. Conflict, stale or PPR
error rolls back canonical records, events and PMF item-status changes together; items
remain `draft`.

After rollback a distinct service transaction writes only `PAUSED_ON_ERROR`, safe error
code/reference and stopped participant. It must not claim a failed PMF item was stored
inside the rolled-back transaction. Accepted replay returns stored outcome without new
commands/events.

## 4. Locks and stale protection

Worker, resume and acceptance follow one exact order:

```text
envelope run → participant → source rows / normalized records → Employee → Person
→ active canonical education → PMF runs/items → existing PPR locks
```

Collections sort technical IDs ascending; participants sort position ascending.
Acceptance is `SERIALIZABLE`; preview is read-only; worker/resume use existing PPR
write transaction isolation, always with the order above.

Fingerprint canonical JSON has no raw source/name/full IIN and includes Stage 0/source
fingerprint; Employee/Person/PPR versions; batch/row/normalized IDs/status/update
tokens; source record key/index; active education identity/`updated_at`; parser/mapping
versions; policy version and classification outcome. Changed source ownership/removal/
rebinding, canonical token, lifecycle or policy is stale and pauses without canonical
write. A changed cohort/order/mapping/policy requires new PREVIEW and APPROVED.

## 5. RBAC and exact APIs

Migration creates `PPR_STAGE2_EDUCATION_MANAGE` and grants it only to `HR_HEAD`.
Every endpoint additionally verifies active primary role `HR_HEAD` and server-computed
org scope over every selected Employee; frontend checks are non-authoritative.
Out-of-scope returns `403 STAGE2_COHORT_OUT_OF_SCOPE`, shown as «Прогон недоступен в
вашем подразделении».

| Endpoint | Request | Result |
|---|---|---|
| `POST /api/personnel/ppr-migration/stage-2/education/preview` | `{stage0_cohort_run_id}` | run, counts, ordered protected comparisons; stale `409`. |
| `GET /api/personnel/ppr-migration/stage-2/education/runs/{run_id}` | — | envelope, participants, PMF fragment comparisons, progress, policy/acceptance summary. |
| `POST .../runs/{run_id}/approve` | `{}` | approved run; blockers/stale `409`. |
| `POST .../runs/{run_id}/execute-next` | `{}` | one processed position/progress. |
| `POST .../runs/{run_id}/resume` | `{}` | retry stopped position. |
| `POST .../runs/{run_id}/participants/{id}/skip` | `{reason}` | audited skip. |
| `POST .../runs/{run_id}/accept` | `{}` | accepted outcome or replay. |

Pydantic safe reports are separate from protected HR comparison responses. Errors use
Russian safe messages/codes; neither contain full IIN/raw source.

## 6. HR_HEAD UI and visibility

Extend existing `/directory/personnel/ppr-migration` with `Stage2EducationPanel`.
Russian textual statuses include «Проверка завершена», «Утверждён к запуску»,
«Выполняется», «Остановлен из-за ошибки», «Готов к принятию», «Этап принят»,
«Черновик подготовлен», «Данные записаны», «Требуется проверка».

Protected table groups fragment cards by one employee and Excel source row. Each card
shows fragment index, «В контрольном списке», «Сейчас в карточке», «Будет записано»,
policy outcome/reason. Full IIN is never rendered. Soft-line-break fragments display
under the same source row, never as another employee.

Before `ACCEPTED`, employee paths read only active canonical `person_education`; HR_HEAD
sees PMF drafts under permission/scope. After acceptance, normal card/employee rules
expose canonical records. Confirmation uses accessible custom dialog: stage, employee
count, ready records by kind, skipped/conflict count, no-overwrite and atomicity text,
no IIN; buttons «Отмена»/«Принять этап» and in-flight double-submit guard.

## 7. Test matrix and visual pilot

| Level | Required coverage |
|---|---|
| Unit | every allowlist branch, priority/conflict, no `other`, split/fingerprint/dedup. |
| Service | no canonical write in preview/execute; approval blockers; same-position resume; skip audit; rollback then separate pause; acceptance replay. |
| PostgreSQL | migration constraints/FKs/indexes, Stage0/PMF links, SERIALIZABLE stale/concurrency, lock-order characterization, only `corpsite_test`. |
| API/RBAC | permission/primary role/org scope, protected/safe redaction, Russian errors, invalid transitions. |
| Frontend | Russian states/reasons, grouped fragments, no IIN, progress/pause/resume/dialog/accepted screen. |
| Security | no raw payload/full IIN in reports/logs; employee cannot read drafts. |

Local synthetic pilot in one permitted org scope must contain: (1) two fragments in one
soft-line-break cell with distinct indices; (2) already-applied equal canonical record;
(3) visible conflict; (4) ambiguous marker causing pause; (5) correction/resume,
atomic acceptance and replay. It uses only synthetic data in `corpsite_test`.

## 8. Exact future file map and visual-review readiness

| Path | Responsibility |
|---|---|
| `alembic/versions/s2e1d2u3c4a5_ppr_stage2_education_envelope.py` | schema/indexes/permission grant. |
| `app/db/models/ppr_stage_run.py` | ORM and status vocabulary. |
| `app/ppr_migration/education_kind_policy.py` | pure v1 classifier. |
| `app/services/ppr_stage2_education_service.py` | all Stage 2 state/acceptance operations. |
| `app/api/ppr_stage2_education_router.py`, `app/api/ppr_stage2_education_schemas.py` | contracts/RBAC/scope. |
| `app/security/ppr_stage2_permissions.py`, `app/security/admin_permissions.py`, `app/main.py` | permission and router registration. |
| `corpsite-ui/app/directory/personnel/ppr-migration/Stage2EducationPanel.tsx` | HR_HEAD UI/dialog. |
| `tests/test_ppr_stage2_education_{unit,postgres,api}.py` and `Stage2EducationPanel.test.tsx` | test matrix. |
| `scripts/dev/seed_stage2_education_visual_pilot.py` | synthetic test-only fixture. |

Local readiness sequence: verify exactly `127.0.0.1:5432/corpsite_test`; upgrade test
DB; run PG/unit/API/frontend tests; seed only synthetic pilot; start backend with test
DSN and frontend API base `http://127.0.0.1:8011`; check `/health`, `/openapi.json`,
HR_HEAD login and `/directory/personnel/ppr-migration`. Visual Review is ready only
when the complete pilot is visible in correct org scope, drafts remain employee-hidden,
acceptance is atomic/replay-safe and all reports mask full IIN.

Out of scope: implementation, migration/DML, production connection, Stage 3 or changes
to approved Stage 0/1/2 documents.
