# WP-PPR-MIG-000A — Stage 0 PREVIEW/FREEZE implementation plan

**Статус:** Draft — Ready for Implementation Review

**Основание:** [program plan](ppr-control-list-staged-migration-plan.md) и
[WP-PPR-MIG-000](WP-PPR-MIG-000-stage-0-cohort-preflight.md). Этот WP определяет
только будущую реализацию Stage 0; он не реализует Stage 1, section apply или PPR
draft visibility.

## 1. Existing patterns и выбранное направление

| Existing pattern | Подтверждённый вывод для реализации |
|---|---|
| `control_list_repair_preflight_service` и `/personnel/lk/control-list-repair/preflight` | Per-IIN preflight уже выполняется в `REPEATABLE READ READ ONLY`, скрывает полный ИИН и использует fail-closed safe codes. Его HTTP API нельзя вызывать циклом для batch scan. |
| `adr048_person_resolution_service` и `adr065_person_link_service` | Exact identity resolution, ownership checks и repair должны остаться едиными; Stage 0 читает их правила через общий domain port, а repair выполняется только отдельно через ADR-065. |
| `ControlListApplyRun` / `ControlListApplyAction` и apply-execution repository | Есть pattern canonical JSON fingerprint, unique fingerprint, `FOR UPDATE` transitions и replay/conflict при несовпадении fingerprint. Он применяется к metadata only, не к PPR writes. |
| `PprLifecycleApplicationService` / `personnel_record_metadata` | Structural lifecycle evidence читается, но Stage 0 не materializes PPR и не проверяет permission будущего section executor. |
| `access_grants`, `admin_permissions`, `compute_scope` | Backend permission check — server-owned; org scope вычисляется сервером. `HR_ENROLLMENT_MANAGER` предоставляется также admin contours, поэтому сам по себе не выражает требование «только HR_HEAD». |
| Alembic permission migrations и PostgreSQL tests | Новые schema и permission будут введены одной будущей migration с revision-local migration tests; integration tests используют только `corpsite_test`. |

## 2. PREVIEW service

### 2.1. Общий read-domain port

Создать future port `Stage0CohortReadPort` и его SQL adapter. Он принимает
`source_batch_id`, optional `supplemental_of_run_id` и server-resolved org scope,
возвращая typed `Stage0CandidateSnapshot`. Adapter делает set-based queries, а не
HTTP calls и не serialный вызов existing per-IIN endpoint.

Port переиспользует либо извлекает из current preflight/ADR-048 один набор:

- exact Employee → Person resolution и active operational checks;
- `HR_CONTROL_LIST` anchor: batch/row/ownership/minimal identity-link provenance;
- approved Stage-0 batch policy и batch-level unresolved-removal gate;
- source ownership/rebinding markers и safe reason codes;
- structural PPR lifecycle-path classification.

Одиночный repair preflight и batch Stage 0 должны иметь один authoritative mapping
в safe reason-code vocabulary. Расхождение между ними — architecture-test failure.

### 2.2. Contract PREVIEW

`preview_stage0_cohort(...)` открывает `REPEATABLE READ READ ONLY` transaction,
выполняет полный scan выбранного batch и классифицирует каждого candidate строго по
матрице WP-PPR-MIG-000. Он возвращает:

- `preview_fingerprint` — SHA-256 canonical JSON source scope, policy version,
  deterministic candidate snapshots и classifications;
- counts по category;
- ordered `ELIGIBLE` candidates с будущими positions;
- blocker list с technical IDs, category и safe reason codes;
- `previewed_at` и safe source/policy versions.

Порядок: `employee_id ASC`, `person_id ASC`, `batch_id ASC`, `row_id ASC`.
Positions присваиваются только `ELIGIBLE` participants непрерывно с `1`.

PREVIEW не создаёт run, report или audit rows и не делает DML. Safe technical response
не содержит полный ИИН, ФИО либо raw payload. Отдельный protected HR_HEAD view может
получить ФИО и минимум данных для correction только после той же server-side RBAC и
org-scope проверки; этот view не изменяет safe export contract.

## 3. FREEZE service

### 3.1. Contract

`freeze_stage0_cohort(source_batch_id, preview_fingerprint, supplemental_of_run_id)`
повторно читает и классифицирует source на сервере. Клиент не передаёт participants,
blockers или raw snapshot как authority.

1. Server recomputes the canonical preview fingerprint under locks.
2. Если fingerprint отличается от submitted value, вернуть `409 STAGE0_PREVIEW_STALE`
   без создания run; пользователь выполняет новый PREVIEW.
3. Если identical frozen run уже существует, вернуть его как idempotent replay.
4. Если fingerprint совпадает и replay нет, одной короткой транзакцией записать
   только Stage 0 run metadata, `ELIGIBLE` participants и blocker report.

FREEZE не изменяет `Employee`, `Person`, `hr_import_*` source, assignments или PPR.
Любая error откатывает целую FREEZE transaction. Один и тот же request/fingerprint
возвращает тот же frozen run; reuse same idempotency context с другим fingerprint
возвращает `409 STAGE0_FREEZE_FINGERPRINT_CONFLICT`.

### 3.2. States

PREVIEW является ephemeral read result, поэтому `DRAFT` и `PREVIEWED` не хранятся.
Persisted Stage 0 run всегда `FROZEN` (или `frozen_at IS NOT NULL` без отдельного
state column). `CANCELLED` и `SUPERSEDED` не нужны: section eligibility решает
актуальность данных, а supplemental run ссылается на base run и не меняет его.
Это не section-execution state machine.

## 4. Future persistence model

Все имена ниже — точная целевая schema proposal для одной будущей Alembic migration;
таблицы сейчас не существуют. JSONB допускается только для безопасного canonical
snapshot, никогда для полного ИИН, ФИО или raw source payload.

### 4.1. `ppr_stage0_cohort_runs`

| Field | Type / constraints |
|---|---|
| `stage0_cohort_run_id` | `BIGINT` PK, identity. |
| `run_kind` | `TEXT NOT NULL CHECK (run_kind IN ('BASE','SUPPLEMENTAL'))`. |
| `supplemental_of_run_id` | nullable FK → same table `ON DELETE RESTRICT`; `BASE` requires NULL, `SUPPLEMENTAL` requires non-NULL. |
| `source_batch_id` | `BIGINT NOT NULL FK hr_import_batches(batch_id) ON DELETE RESTRICT`. |
| `source_type` | `TEXT NOT NULL CHECK (source_type = 'HR_CONTROL_LIST')`. |
| `source_batch_status` | `TEXT NOT NULL CHECK (source_batch_status IN ('APPLY_PENDING','APPLIED','PARTIALLY_APPLIED'))`. |
| `preview_fingerprint` | `CHAR(64) NOT NULL`, lowercase SHA-256 CHECK. |
| `policy_version` | `TEXT NOT NULL`; included in fingerprint. |
| `source_snapshot` | `JSONB NOT NULL`; IDs, statuses, versions and counts only; no PII/raw values. |
| `created_by_user_id` | `BIGINT NOT NULL FK users(user_id) ON DELETE RESTRICT`. |
| `frozen_at` | `TIMESTAMPTZ NOT NULL`. |

Constraints/indexes:

- `UNIQUE (preview_fingerprint)`; fingerprint includes `run_kind`, parent run and source
  scope, so exact repeated FREEZE is replay;
- index `(source_batch_id, frozen_at DESC)`;
- index `(supplemental_of_run_id, frozen_at)`;
- check that parent run is different from self, with application/trigger guard for
  a longer supplemental chain if needed; no cascade delete;
- no mutable status column: persisted rows are `FROZEN` by definition.

### 4.2. `ppr_stage0_cohort_participants`

| Field | Type / constraints |
|---|---|
| `stage0_participant_id` | `BIGINT` PK, identity. |
| `stage0_cohort_run_id` | `BIGINT NOT NULL FK run ON DELETE RESTRICT`. |
| `position` | `INTEGER NOT NULL CHECK (position >= 1)`. |
| `employee_id` / `person_id` | `BIGINT NOT NULL` FKs to `employees`/`persons`, `ON DELETE RESTRICT`. |
| `source_batch_id` / `source_row_id` | `BIGINT NOT NULL` FKs to `hr_import_batches`/`hr_import_rows`, `ON DELETE RESTRICT`. |
| `identity_provenance_record_id` | nullable `BIGINT` FK to `hr_import_normalized_records` `ON DELETE RESTRICT`; only minimal identity/link anchor, never all future section records. |
| `participant_snapshot_version` | `INTEGER NOT NULL DEFAULT 1 CHECK (participant_snapshot_version = 1)`; Stage 0 frozen snapshot is immutable. |
| `safe_fingerprint` | `CHAR(64) NOT NULL` SHA-256 CHECK. |
| `employee_state_version`, `person_state_version`, `ppr_lifecycle_version` | nullable `BIGINT` snapshots; null only where source model has no version/envelope. |
| `created_at` | `TIMESTAMPTZ NOT NULL`. |

Constraints/indexes: `UNIQUE (stage0_cohort_run_id, position)`,
`UNIQUE (stage0_cohort_run_id, employee_id)`,
`UNIQUE (stage0_cohort_run_id, person_id)`, and indexes on `(employee_id)` and
`(person_id)`. `source_batch_id` must equal the parent run's batch in repository
validation; PostgreSQL trigger is optional only if cross-table invariant is required
at DB level.

### 4.3. `ppr_stage0_cohort_blockers`

| Field | Type / constraints |
|---|---|
| `stage0_blocker_id` | `BIGINT` PK, identity. |
| `stage0_cohort_run_id` | `BIGINT NOT NULL FK run ON DELETE RESTRICT`. |
| candidate IDs | nullable `employee_id`, `person_id`, `source_batch_id`, `source_row_id`, `identity_provenance_record_id`, all restrictive FKs when present. |
| `candidate_key` | `CHAR(64) NOT NULL` safe fingerprint of technical candidate identity. |
| `category` | `TEXT NOT NULL CHECK` over approved `BLOCKED_*` categories from WP-PPR-MIG-000. |
| `reason_code` / `safe_detail` | `TEXT NOT NULL`; safe code/message only. |
| `snapshot_version` / `safe_fingerprint` | `INTEGER NOT NULL CHECK (= 1)` and `CHAR(64) NOT NULL` SHA-256 CHECK. |
| `created_at` | `TIMESTAMPTZ NOT NULL`. |

`UNIQUE (stage0_cohort_run_id, candidate_key, category, reason_code)` prevents report
duplication. Index `(stage0_cohort_run_id, category)` serves counts/report views.
No `full_name`, IIN, raw payload, raw normalized payload or source text fields exist.

## 5. Source, stale protection и supplemental runs

Source is only `HR_CONTROL_LIST` with batch status `APPLY_PENDING`, `APPLIED` or
`PARTIALLY_APPLIED`. `UPLOADED`, `PARSED`, `IN_REVIEW`, `FAILED`, `CANCELLED` fail
closed. Any unresolved diff removal in the selected batch blocks FREEZE. The first
implementation deliberately does not weaken this to a row-level removal match.

The fingerprint includes batch identity/status, unresolved-removal count, selected anchor
IDs, source ownership/binding evidence, Employee/Person state, merge/link state,
lifecycle envelope/version, policy version, supplemental parent and ordered outcome.
Thus a changed Employee, Person, source ownership, removal/rebinding or lifecycle
between PREVIEW and FREEZE produces stale conflict, not a silent freeze.

Supplemental runs are `run_kind='SUPPLEMENTAL'` and reference one frozen base/supplemental
run. Their candidate scope is limited explicitly to new Employees or previously blocked
candidates after correction. They make a new frozen run; they never append to or edit
the original participant list or blocker report.

## 6. RBAC и API contracts

### 6.1. Permission

Introduce one future server-owned access role `PPR_STAGE0_COHORT_MANAGE`. It must be
granted to platform role `HR_HEAD` only; each endpoint additionally checks current
primary role code `HR_HEAD` and `compute_scope` coverage of every returned/frozen
Employee. This is necessary because `HR_ENROLLMENT_MANAGER` currently also serves
admin/personnel contours and cannot meet the strict HR_HEAD-only requirement alone.

No frontend check is authoritative. An out-of-scope candidate is omitted from PREVIEW
and cannot be frozen; a caller without permission receives `403`, not a broader report.

### 6.2. Future endpoints

| Endpoint | Request / response | Server guard |
|---|---|---|
| `POST /api/personnel/ppr-migration/stage-0/preview` | `{source_batch_id, supplemental_of_run_id?}` → ephemeral fingerprint, counts, safe candidate/blocker report; protected representation opt-in. | `PPR_STAGE0_COHORT_MANAGE` + primary `HR_HEAD` + org scope. |
| `POST /api/personnel/ppr-migration/stage-0/freeze` | `{source_batch_id, preview_fingerprint, supplemental_of_run_id?}` → frozen run ID, replay flag, counts; `409` stale/conflict. | Same guard; server recomputes. |
| `GET /api/personnel/ppr-migration/stage-0/runs/{run_id}` | Frozen metadata and safe ordered participants. | Same guard + re-check scope of every participant; fail closed if scope changed. |
| `GET /api/personnel/ppr-migration/stage-0/runs/{run_id}/blockers` | Safe blocker report; HR_HEAD protected mode may return correction-minimum fields. | Same guard + org scope; no export of full IIN/raw source. |

Pydantic schemas must separate `Safe*Response` from `HrHeadCorrection*Response` so a
future mapper cannot accidentally include protected fields in a technical response.

## 7. Transactions и concurrency

| Operation | Transaction / locking |
|---|---|
| PREVIEW | `REPEATABLE READ READ ONLY`; no locks beyond normal snapshot reads and no DML. |
| FREEZE | `SERIALIZABLE` read-write, short transaction. First acquire `pg_advisory_xact_lock` on stable key `PPR_STAGE0:FREEZE:<source_batch_id>:<parent-or-0>`. Then lock selected data in fixed order: batch, source rows by `row_id`, minimal provenance records by ID, Employees by `employee_id`, Persons by `person_id`, PPR envelopes by `person_id`, using `FOR SHARE`; recompute snapshot/fingerprint; insert only Stage 0 tables. |

`UNIQUE(preview_fingerprint)` is the final replay fence. A unique violation is re-read
as replay only if all request context fields match; otherwise it is conflict. A
serialization failure is a retryable `409 STAGE0_FREEZE_RETRY_REQUIRED`, with no
persisted partial result. Any validation, lock, or insertion error rolls back all three
Stage 0 tables. No domain table is written or locked `FOR UPDATE` by FREEZE.

## 8. Test matrix

| Level | Required coverage |
|---|---|
| Unit | category predicates; deterministic ordering/positions; fingerprint canonicalization; batch policy; removal gate; supplemental eligibility; no PII in safe models. |
| API/RBAC | no permission/role → 403; HR_HEAD in scope succeeds; HR_HEAD out of scope cannot preview/freeze/read; protected view is denied or redacted outside scope. |
| PostgreSQL integration | PREVIEW makes no writes; FREEZE writes only three Stage 0 tables; exact frozen IDs/positions/blockers; source/person/PPR tables unchanged. |
| Stale/idempotency | source/Employee/Person/lifecycle/removal change after preview → `409`; identical FREEZE → same run/replay; altered fingerprint/context → conflict. |
| Concurrency | simultaneous same FREEZE yields one run plus replay; competing changed source yields serializable retry/stale outcome; no duplicate participants/blockers. |
| Supplemental | new Employee and repaired former blocker create linked supplemental run without editing original frozen cohort. |
| Security | safe endpoints/reports never contain complete IIN, FIO or raw payload; test logging/error responses too. |
| DB guard | fixtures assert `corpsite_test`; production DSNs/hostnames are rejected before tests; no production connection. |

## 9. Exact future file map

| Future file | Responsibility |
|---|---|
| `alembic/versions/<revision>_ppr_stage0_cohort_preview_freeze.py` | Three tables, constraints/indexes, `PPR_STAGE0_COHORT_MANAGE` access role and HR_HEAD role grant. |
| `app/db/models/ppr_stage0_cohort.py` | SQLAlchemy models and declared constants/check vocabulary. |
| `app/ppr_migration/stage0/domain/models.py` | Immutable snapshots, categories, fingerprints and result DTOs. |
| `app/ppr_migration/stage0/domain/ports.py` | Read and persistence protocols. |
| `app/ppr_migration/stage0/infrastructure/read_repository.py` | Set-based shared read-domain adapter. |
| `app/ppr_migration/stage0/infrastructure/cohort_repository.py` | SERIALIZABLE FREEZE persistence/replay queries. |
| `app/ppr_migration/stage0/application/preview_service.py` | Read-only PREVIEW orchestration. |
| `app/ppr_migration/stage0/application/freeze_service.py` | Stale verification, locks, idempotent FREEZE. |
| `app/security/admin_permissions.py` and a dedicated `app/security/ppr_stage0_permissions.py` | New permission helper, strict HR_HEAD role and scope gate. |
| `app/api/ppr_stage0_cohort_router.py`, `app/api/ppr_stage0_cohort_schemas.py`, `app/main.py` | Backend routes, safe/protected schemas and router registration. |
| `tests/ppr_migration/test_stage0_*.py` | Unit, API/RBAC, PostgreSQL, migration, PII and concurrency cases from §8. |

## 10. Open implementation decisions

1. Select the canonical repository boundary for the shared read port: extract reusable
   queries from `control_list_repair_preflight_service` or compose an ADR-048 adapter
   around its existing domain service. Its externally observable safe codes must not
   change.
2. Confirm whether `employees` exposes a durable row-version. If absent, fingerprint
   its approved structural fields rather than inventing a version column.
3. Decide whether cross-table source-batch equality is repository-validated first or
   reinforced by a PostgreSQL trigger; the schema contract itself remains unchanged.

Out of scope: creating these files, executing migration, connecting to production,
changing approved documents, any section run and any PPR data migration.
