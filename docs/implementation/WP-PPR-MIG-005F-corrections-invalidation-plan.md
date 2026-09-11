# WP-PPR-MIG-005F — Manual correction and targeted invalidation plan

| Parameter | Value |
|---|---|
| Status | **Approved — WP-PPR-MIG-005F-C deferred; manual canonical editors required before resumption** |
| Parent | [WP-PPR-MIG-005](WP-PPR-MIG-005-migration-status-matrix-plan.md) |
| Depends on | [WP-005A semantics](WP-PPR-MIG-005A-status-semantics.md), [WP-005B projection](WP-PPR-MIG-005B-status-projection-read-model.md), [WP-005C API](WP-PPR-MIG-005C-report-api-and-authorization.md), [WP-005E card display](WP-PPR-MIG-005E-card-section-status-display.md) |
| Scope | Design only: audited manual correction and targeted invalidation for `general`, `education`, `training`. |
| Out of scope | DDL, event-enum change, writers, endpoints, UI, rebuild execution, production access, commit and push. |

## 1. Confirmed inventory of v1-relevant write paths

“Existing” below means a repository path was found; it does **not** mean that it is already a WP-005F manual-correction path. `scope` is checked at the route before the writer unless stated otherwise.

| Area / write path | Endpoint | Service / repository | Transaction boundary | Existing permission and scope | Existing audit / event | Section invalidation required |
|---|---|---|---|---|---|---|
| Stage 0 cohort freeze / participant binding baseline | `POST /personnel/ppr-migration/stage-0/freeze` | `ppr_stage0_cohort_service.freeze_stage0_cohort` | `SERIALIZABLE`, route-owned `conn.begin()` | `PPR_STAGE0_COHORT_MANAGE`; `compute_scope` + personnel visibility | Stage-0 run/participant facts; no WP-005F event | All three for every changed participant/binding in the affected universe; rows leaving universe must be removed, not marked. |
| General Stage 1 preview / approve / execute / accept | `POST /personnel/ppr-migration/stage-1/{preview,approve,execute-next,accept}` | `ppr_stage1_general_service` | Preview/approve/execute `engine.begin()`; accept `SERIALIZABLE` | `PPR_STAGE1_GENERAL_MANAGE`; cohort-wide scope check | `PPR_STAGE1_GENERAL_ACCEPTED` in `personnel_record_events` is current acceptance evidence | `general`; any changed employee/person/source-row binding additionally affects all three. |
| Canonical general / FIO from Stage 1 acceptance | no separate general edit route found in the PPR card routes; produced by `accept_stage1_run` | `ppr_stage1_general_service`, PPR event repository | Same `SERIALIZABLE` Stage-1 accept UoW | Stage-1 manage + cohort scope | PPR event; `persons.updated_at` is currently used by WP-005B | `general` immediately. Do not infer `CORRECTED_BY_HR`: no required event exists yet. |
| Education Stage 2 preview / approve / execute / resume / skip / cancel / accept | `POST /personnel/ppr-migration/stage-2/education/...` | `ppr_stage2_education_service` plus PMF commit engine | Preview performs read-only computation then serializable persist; normal mutations `engine.begin()`; accept `SERIALIZABLE` | `PPR_STAGE2_EDUCATION_MANAGE`; cohort scope | Stage run/participant plus PMF run/items and PMF record events | `education`; binding changes also all three. |
| Training Stage 3 create / approve / execute / resume / skip / cancel / accept | `POST /personnel/ppr-migration/stage-3/training/...` | `ppr_stage3_training_service` plus PMF commit engine | Preview read-only; persist/accept `SERIALIZABLE`; other mutations `engine.begin()` | `PPR_STAGE3_TRAINING_MANAGE`; cohort scope | Stage run/participant plus PMF run/items and PMF record events | `training`; binding changes also all three. |
| PMF education/training migration and supersede | `POST /personnel-migration/runs/{id}/commit`, `/void`, `/records/supersede` | `personnel_migration_commit_service`; `emit_personnel_record_event` | service transaction invoked through `call_service`; exact outer UoW is service-owned | `require_hr_import_admin_or_403`; no per-person org-scope check at these legacy routes | `EDUCATION_*` PMF event types; payload is unconstrained JSONB | `education` or `training` according to target table; do not invalidate `general`. |
| Canonical education profile update | No public route confirmed in the inspected API surface | `hr_import_education_profile_service.update_education_profile` | caller-owned connection; no standalone transaction wrapper found | caller responsibility; endpoint/scope **not confirmed** | update timestamp/provenance; no required PPR manual event | `education`. |
| Canonical training manual write | No v1 public create/edit route found; Stage 3/PMF is the confirmed writer | Stage 3 + PMF | as above | as above | as above | `training`. |
| Normalized-record review decision | No public endpoint confirmed in inspected routers | `hr_import_normalized_record_service.update_normalized_record_review` | caller-owned `Connection` | caller responsibility; endpoint/permission/scope **not confirmed** | review columns/timestamps; no confirmed `personnel_record_events` event | `education` and/or `training`, selected by normalized record kind; `general` only if a future general source uses that record. |
| Normalized-record review override | No public endpoint confirmed in inspected routers | `update_normalized_record_review_override` | caller-owned `Connection` | caller responsibility; endpoint/permission/scope **not confirmed** | review-override fields; no WP-005F event | Same as normalized review. Pending/rejected override must not yield `CORRECTED_BY_HR`. |
| Employee/person/source-row binding | No direct route confirmed for the binding service | `hr_import_employee_binding_service.bind_normalized_record_to_employee`; Stage-0 freeze consumes the bindings | caller-owned `Connection` | caller responsibility; endpoint/permission/scope **not confirmed** | binding state only; no projection invalidation event | all sections for the affected person in every containing universe; invalid/missing binding is `BLOCKED`, a valid changed anchor makes prior result `STALE`. |
| Identity reconciliation / person merge materialization | `POST /personnel-admin/identity/reconciliation/r1a/execute` | `identity_reconciliation_service.apply_candidate` | service executes its own transactions | `PERSONNEL_ADMIN`; administrative authorization; separate scope model | reconciliation history and canonical timestamps | all three for affected person(s); merged/inactive person is `BLOCKED`. |
| Approved review override | `POST /personnel-admin/overrides`, then `/{id}/approve`; reject/revoke/reconfirm variants | `hr_review_override_service.create_override/approve_override/...` | each `*_tx` uses `engine.begin()` | create: `PERSONNEL_ADMIN`; approve: HR governance; no person/org scope asserted by this route | `hr_review_overrides` plus append-only `hr_review_override_history` | only after an approved override actually changes a fact included in a section fingerprint. Approval by itself is **not** `CORRECTED_BY_HR`. |
| Source fragment / raw import change | No interactive source-fragment write endpoint found. Sources are created by import/normalization paths (`hr_import_service.create_batch`, normalized/document-candidate services). | `hr_import_service`, `hr_import_normalized_record_service`, document-candidate services | batch/import caller transaction; exact route varies | import/admin authorization; per-person scope not confirmed | import batch/row and normalization timestamps; no projection outbox/event | `general` for name/identity source fields; `education`/`training` for selected normalized fragments. A source row is never copied into the projection. |

### Evidence and limits of the inventory

Confirmed route files are `app/api/ppr_stage{0,1,2,3}_*_router.py`, `app/api/personnel_migration_router.py`, and `app/api/personnel_admin_router.py`. The status implementation currently reads Stage/PFM facts in `app/services/ppr_migration_status_projection_service.py`; it has no writer hook or incremental rebuild method. The repository contains service-level writers with no corresponding inspected public route; they are explicitly recorded as **not confirmed**, rather than assumed accessible.

## 2. Event storage decision: separate immutable correction-event table

### Findings

| Required property | Existing state | Decision for WP-005F |
|---|---|---|
| Event-type constraint | `event_type TEXT NOT NULL`; no check enum was found. | Add an allow-list/check or a separately governed registry before relying on the event. |
| Payload contract | `event_payload JSONB NOT NULL` is arbitrary JSON; existing PMF record-event read API returns it verbatim. | A versioned, allow-listed, PII-free schema and validation are required. |
| Append-only guarantee | No trigger preventing `UPDATE`, `DELETE`, or `TRUNCATE` was found for this table. (Unlike `hr_review_override_history`, which has an append-only trigger.) | Do not call the table an immutable audit log until database enforcement is added. |
| Downgrade | Existing nullable-domain revision refuses downgrade whenever any row has `domain_code IS NULL`. Base PMF downgrade drops the table with `CASCADE`. | A new migration needs an explicit reversible policy; it must not silently leave the required event unrepresentable. |
| Indexes/idempotency | Only `(person_id, domain_code)` index exists; no event-type/correlation/idempotency unique index. | Add a unique idempotency key and lookup index as part of the future event-storage work. |
| Existing readers | PMF query routes expose raw payload to HR-import admins; PPR event repository reads/writes this table and checks correlation/source event IDs in payload. | New payload must remain PII-free, and readers must be reviewed/redacted before exposing a correction event. |

**Approved decision:** v1 uses a new, separate immutable table named `ppr_section_manual_correction_events`; `PPR_SECTION_MANUAL_CORRECTED` is not stored in `personnel_record_events`. WP-005F does not alter `personnel_record_events` in any way. Potential journal unification remains a separate future architecture task.

WP-005F-A also creates a separate transactional outbox for targeted projection work. The correction-event row and the outbox row are PII-free, immutable and independently versioned; both belong to the canonical-write transaction.

## 3. Required future event contract

`PPR_SECTION_MANUAL_CORRECTED/v1` is system-emitted **only after** the canonical write and its optimistic version check both succeed in the same database transaction. An HR user never creates it directly.

| Field | Contract |
|---|---|
| Event identity | server-generated event ID; opaque `idempotency_key` unique per correction command and expected canonical version. |
| Actor | authenticated technical `actor_id`; no display name. |
| Target | `person_id`, nullable `employee_context_id`, `section_code` in `general|education|training`, `universe_id` and source cohort ID. |
| Origin | origin status/reason, stage run/participant, PMF run/item and evidence IDs if present; all are technical identifiers. |
| Fingerprints | `before_*` and `after_*` for source, target and binding; all SHA-256 safe fingerprints. `after_*` are calculated after canonical write in the locked UoW. |
| Versioning | `policy_version`, parser version if applicable, canonical expected/committed row version, event schema version. |
| Payload prohibition | No FIO, IIN, source/target values, source text, documents, raw payload, exception text, free-form notes, or document references. |
| Relation | `record_table_name`/`record_id` identify the canonical changed record; general uses `persons` and person ID. |

The event establishes `CORRECTED_BY_HR` / `MANUAL_CORRECTION_PENDING_RECHECK` only while its after-fingerprints equal current facts and policy is unchanged. A change to included source, target, binding/cohort, or policy fingerprint turns it into `STALE` with the corresponding `FINGERPRINT_*_CHANGED` reason. It is distinct from `ACCEPTED` (participant-level accepted migration evidence) and `REVIEW_REQUIRED` (unresolved source/canonical conflict).

## 4. Recommended targeted recalculation design

**Approved design:** use a separate transactional outbox plus asynchronous, idempotent targeted projector; do not call `rebuild_universe` synchronously from arbitrary writers.

1. A domain writer locks the canonical target and validates permission, org scope, active-universe membership, expected version and current fingerprints.
2. In one transaction it commits the canonical change, appends `PPR_SECTION_MANUAL_CORRECTED/v1` to `ppr_section_manual_correction_events`, and inserts one PII-free outbox job keyed by `(event_id, universe_id, person_id, section_code)`.
3. Commit makes the correction and event durable even if projection work fails. The asynchronous worker locks the universe/person/section (advisory or row lock), recomputes only that cell from authoritative facts, upserts it using row version, then marks the outbox row delivered.
4. Replays use the same idempotency key and compare payload digest; equal replay is a no-op, unequal replay is a conflict. The job may be retried safely.
5. Projector failure does not roll back an already committed correction, never removes the event, and leaves/requeues the outbox job for retry. The read API remains read-only. The existing “Обновить данные отчёта” button continues GET reload only; it shows the new `calculated_at` after the worker commits the projection.

Synchronous in-transaction projection replacement is not recommended: it couples every legacy writer to Stage/PMF reads and makes canonical correction unavailable when the read model fails. A transactional outbox prevents losing the event while avoiding a global rebuild.

## 5. Invalidation matrix

| Trigger | Affected section(s) | Immediate projected status / reason | Recheck | New fingerprint source |
|---|---|---|---|---|
| Successful manual general correction | `general` | `CORRECTED_BY_HR` / `MANUAL_CORRECTION_PENDING_RECHECK` if event after-hashes match | targeted cell | canonical person + source row + binding snapshot. |
| Successful manual education correction | `education` | `CORRECTED_BY_HR` / `MANUAL_CORRECTION_PENDING_RECHECK` | targeted cell | active `person_education`, selected normalized fragments, PMF/binding. |
| Successful manual training correction | `training` | `CORRECTED_BY_HR` / `MANUAL_CORRECTION_PENDING_RECHECK` | targeted cell | active `person_training`, selected normalized fragments, PMF/binding. |
| Included source general/FIO fragment changes | `general` | `STALE` / `FINGERPRINT_SOURCE_CHANGED` | targeted cell | `hr_import_rows.normalized_payload` and Stage-1 source facts. |
| Included education/training normalized fragment or approved review changes | respective section | `STALE` / `FINGERPRINT_SOURCE_CHANGED`; unresolved review remains/returns `REVIEW_REQUIRED` | targeted cell | normalized record revision/review and section parser facts. |
| Canonical target edit/supersede/void outside a matching correction event | respective section | `STALE` / `FINGERPRINT_TARGET_CHANGED` | targeted cell | current active canonical rows and PMF provenance. |
| employee/person/source-row rebind or person merge/inactivation | all three | invalid anchor: `BLOCKED` / `BINDING_*`; valid changed anchor: `STALE` / `FINGERPRINT_BINDING_CHANGED` | all cells for that person in containing universes | employee/person/cohort/source-row binding. |
| Stage participant execution/error/cancel/accept | owning section | recompute WP-005A tree; cancelled latest run cannot erase older valid acceptance | targeted cell | current eligible run/participant/evidence selection. |
| Correction event after-fingerprint no longer matches | event section | `STALE` / matching `FINGERPRINT_*_CHANGED` | targeted cell | current authoritative facts versus event after-hashes. |
| Any v1 policy/parser version change | dependent section(s), normally all cells for that policy | `STALE` / `FINGERPRINT_POLICY_CHANGED` | bounded batch by universe/section; never infer compatibility | current policy/parser registry version. |
| Outside-active-universe change | none in that universe | no row | none | n/a. |

## 6. Permissions and scope

**Approved:** no permission to “create a correction event” exists. The system emits the event only after a write permitted by the **existing section-specific edit permission** and person/org-scope assertion; report-read permission is never sufficient.

| Section | Recommended future authorization | Current evidence |
|---|---|---|
| `general` | Stage-1/general editor capability plus `assert_ppr_read_allowed_for_person`-equivalent write scope. | `PPR_STAGE1_GENERAL_MANAGE` controls stage changes; a separate canonical general editor route was not found. |
| `education` | existing education editor/PMF editor capability plus person/org scope. | `PPR_STAGE2_EDUCATION_MANAGE` controls Stage 2; legacy PMF uses `HR_IMPORT_ADMIN` without demonstrated per-person scope. |
| `training` | existing training editor/PMF editor capability plus person/org scope. | `PPR_STAGE3_TRAINING_MANAGE` controls Stage 3; no separate canonical training editor route found. |

The implementation must fail closed if no existing editor permission maps to the actual canonical writer. It must not create an implicit `ADMIN` bypass. An approved override without a successful canonical write creates neither `PPR_SECTION_MANUAL_CORRECTED` nor `CORRECTED_BY_HR`.

## 7. Small implementation work packages

| WP | Deliverable | Gate |
|---|---|---|
| WP-005F-A | [Completed — Ready for WP-PPR-MIG-005F-B](WP-PPR-MIG-005F-A-event-outbox-schema.md): immutable `ppr_section_manual_correction_events` and separate transactional outbox schema; PII-safe contract, idempotency, append-only and downgrade tests. | Event and outbox storage are DB-enforced immutable and safe. |
| WP-005F-B | [Completed — Ready for WP-PPR-MIG-005F-C](WP-PPR-MIG-005F-B-targeted-projector-worker.md): idempotent targeted projector and asynchronous worker for `universe × person × section`. | Retry is safe; projector failure cannot lose an event or produce partial projection. |
| WP-005F-C | [Deferred — no confirmed manual canonical writers](WP-PPR-MIG-005F-C-manual-write-producers.md). Resume only after a separate implementation provides manual canonical editors for all three sections. | Stage/PMF automated writes are never a source of `CORRECTED_BY_HR`. |
| WP-005F-D | Source, binding, override and policy invalidation producers. | Policy invalidation is emitted as small batch/outbox work, never an HTTP-time global rebuild; override-only has no correction event. |
| WP-005F-E | Observability, retry/dead-letter and end-to-end PostgreSQL tests. | Lag/retry/dead-letter are observable; report refresh remains GET-only. |

## 8. Product decisions — Approved

| Decision | Recommended option | Alternatives | Consequence / approval needed |
|---|---|---|---|
| Event storage | Separate immutable `ppr_section_manual_correction_events`; do not change `personnel_record_events`. | Future journal unification in a separate architecture task. | **Approved:** isolation from legacy unconstrained payload readers and no shared-journal hardening in WP-005F. |
| Correction authority | Reuse the actual existing section edit permission **and** per-person org scope; no read-permission escalation. | New dedicated correction permission. | Approve who may correct each section where legacy writer lacks scope. |
| Projection delivery | Separate transactional outbox + asynchronous idempotent targeted projector. | Synchronous in-UoW projection update. | **Approved:** event persists and retries despite projector failure; committed HR correction is never rolled back. |
| Atomicity | Canonical write + correction/invalidation event + outbox row in one transaction. | Multi-transaction best effort. | **Approved:** no committed correction without a durable event/job. |
| Policy rollout | Mark dependent cells `STALE`, then batch/outbox recheck in small portions. | HTTP-time recomputation; global rebuild; compatibility mapping. | **Approved:** no user-request global rebuild and no compatibility mapping in v1. |
| Override meaning | Only system-emitted event after canonical commit yields `CORRECTED_BY_HR`; approved import override alone does not. | Treat approved override as correction. | **Approved:** prevents false correction audit claims. |

## 9. Verification required before implementation

Before WP-005F-A, re-check on a disposable PostgreSQL test database: exact migration conventions for new immutable event/outbox tables; all current canonical writers and their transaction ownership; true public routes for normalized review/binding/profile writers; and the selected worker runtime. `personnel_record_events` is inventory-only and must not be changed. No production data or production connection is needed for this work.
