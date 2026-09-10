# WP-PPR-MIG-003 — инвентаризация следующих доменов личной карточки

| Параметр | Значение |
|---|---|
| Статус | **Draft — Findings for Review** |
| Дата | 2026-09-10 |
| Граница работы | Только инвентаризация. Не является планом реализации, DML или решением о переносе. |
| Предшественники | `WP-PPR-MIG-000…002A`, `WP-CL-006`, `WP-CL-009`, `WP-CL-010`, ADR-056, WP-PR-026 |

## Вывод

Следующий безопасный migration-slice — **обучение и повышение квалификации**: для него уже есть
`TrainingCandidate`, canonical `person_training`, section writer, events и read-model. Это всё же
не разрешает массовый apply: нормализация и dedup/конфликт с canonical training — разные задачи.

**Трудовая биография** также имеет готовый canonical слой, но в контрольном списке нет выделенного
семантического поля или normalizer-а для внешних периодов работы. Переносить её из текущего
`employment.*` нельзя. **Воинский учёт** уже реализован как greenfield person-owned section, но
контрольный список даёт только консервативный summary, а не структурированные реквизиты. Его
автоперенос на текущих данных запрещён. **Трудовая деятельность** не является PPR-section для
импорта: это действующее назначение и приказной Employment/Orders контур.

## Фактическая карточка и границы доменов

Источник подписей — `corpsite-ui/app/directory/personnel/_components/PprPersonalCardPageClient.tsx`
и registry `corpsite-ui/lib/pprCardSections.ts`.

| UI-раздел (точная подпись) | Фактический read source / API | Характер |
|---|---|---|
| `Образование` | `PPR-EDUCATION` → `person_education` | 0..N, исторические person-owned записи; Stage 2 completed. |
| `Обучение и повышение квалификации` | `PPR-TRAINING` → `person_training` | 0..N, исторические/документные person-owned записи. |
| `Родственники` | `PPR-FAMILY` → `person_relatives` | 0..N, чувствительные person-owned записи; не имеет source slice в control list. |
| `Воинский учёт` | `PPR-MILITARY` → `person_military_service` | 0..1 active, superseded/voided history, restricted. |
| `Дополнительные сведения` | `personnel_record_metadata.additional_profile`, intake payload и legacy import profile, merged only for read | Повторяемые языки/награды/степени/звания; сейчас это не единый canonical writer. |
| `Трудовая биография` | `PPR-EMPLOYMENT-BIOGRAPHY` → `person_external_employment` | 0..N внешних (до данной организации) периодов; history by supersede/void. |
| UI registry: `Трудовая деятельность`; реально рендерится как `Текущее назначение` | `EmployeeOperationalAssignmentSection`; `person_assignments` + `employee_assignment_links`, employee snapshot и кадровые приказы | Действующие кадровые данные, историзируемые закрытием назначений; не PPR biography. |
| `Кадровые приказы`, `Кадровые обращения`, `Адаптация`, `История изменений`, для applicant `Предполагаемое трудоустройство` | respective Orders/Applications/Onboarding/Intended-employment services | Операционные или evidence/flow разделы, не кандидаты для copying из control list в Stage 3. |

### Обязательное различие: биография и деятельность

`Трудовая биография` — `PersonExternalEmployment`: person-owned, без FK на employee для
`employee_context_id`; поля работодателя, подразделения, должности, периода, причины прекращения,
документной ссылки и provenance описывают *внешнюю занятость до поступления в организацию*.
Единственные mutations: create, supersede, void.

`Трудовая деятельность` в registry имеет id `assignment`, но production component показывает
`Текущее назначение`: текущие подразделение и должность. Его SoT — `person_assignments`
(`person_id`, `org_unit_id`, `position_id`, rate, dates, active/primary/lifecycle) и links к
employee; юридически значимые изменения видны и проводятся через кадровые приказы. Поэтому
`employment.department_name`, `employment.position_title`, `employment.rate`,
`employment.started_at` из контрольного списка — **temporary EmploymentCandidate**, а не external
biography и не разрешение обновить assignment.

## Матрица source → destination

| Домен | Точный source / normalised slice | Canonical destination и существующий writer/audit | Автоматический перенос; конфликты / ручное решение | Приказ / новая модель или DB migration |
|---|---|---|---|---|
| Training | Заголовки `Повышение квалификации`, `Обучение`, `Курсы`, `ПК` → `training.records` → 1 row = 0..N `TrainingCandidate` (`raw_fragment`, provider/title/date/year/hours/certificate/type, provenance). | `person_training`; `PprSectionApplicationService` add/update/void/supersede; `personnel_record_events`, `PPR-TRAINING`. | Только clean `normalization_ready`, matched person и отсутствующий canonical duplicate могут стать proposal. Multi-fragment, unparsed/incomplete, year/date/hours, title≠provider, certificate/date mismatch, person or canonical match conflict — HR review. | Приказ не нужен для исторического certificate/course. Canonical table есть; для Stage 3 нужны proposal/apply policy и, если drafts persist, migration-framework storage, а не новая canonical модель. Certificate number — чувствительный документный реквизит. |
| External employment biography | **Нет поля в vocabulary/control list.** Не путать с `employment.*`. Возможный future source — intake `employment_biography[i]` / подтверждённые трудовые документы. | `person_external_employment`; create/supersede/void, event section `PPR-EMPLOYMENT-BIOGRAPHY`. | Из текущего workbook: нет автоматического переноса. Для нового source: periods overlap, same employer/position with different dates, current employer contamination, incomplete dates/termination and unverified source require review. | Не меняет текущую организационную занятость, поэтому кадровый приказ не нужен; proof/review required. Canonical table exists; нужен новый source normalizer/profile only if scope is expanded. |
| Military | `Воинский учёт` aliases → `ppr.military_summary` → `OtherPprCandidate`: только attestation aliases; parser deliberately does not extract rank/VUS/commissariat. | `person_military_service`; create/supersede/void only; `PPR-MILITARY` events. Standard read omits restricted document numbers; privileged read requires `VIEW_MILITARY_DETAILS`. | **Нет automatic apply.** Summary cannot populate structured registration. Manual HR decision: `registration` only after structured source; `not_applicable` only explicit attestation. Ambiguous/unparsed summary is review-only. | Не кадровый приказ, но restricted кадровое подтверждение; no in-place update. Canonical table exists; no new canonical model. Any import needs explicit policy/provenance and redaction review. |
| Current assignment / “Трудовая деятельность” | `employment.department_name`, `position_title`, `rate`, `started_at` → `EmploymentCandidate`, with `employment_mode`; no OrgUnit/Position lookup. | `person_assignments`, `employee_assignment_links`, employee snapshot; assignment/order services and Orders audit, not PPR section writer. | Normalization-ready is not apply-ready. Resolve org/position, active-primary/concurrent collision, date/rate and canonical snapshot drift manually. Never map to `person_external_employment`. | **Нельзя менять без применимого кадрового приказа/его authoritative assignment path**: org unit, position, rate, employment type, start/end, active/primary/lifecycle. Tables already exist; no Stage-3 direct migration. |
| Family | No `person_relatives` control-list semantic field; structured military data also explicitly excluded from WP-CL-010. | `person_relatives`; section service + events `PPR-FAMILY`. | No automatic transfer. HR must identify relationship, person and sensitive address/birth data. | No employment order; sensitive data. Canonical table exists; new importer slice only if authorized. |
| Additional: languages, awards, degrees, titles | Current normalized list has `person.awards`, `qualification.category`, `qualification.degree`; no structured languages/title record slice. `OtherPprCandidate` is scalar and temporary. | Read merge is `personnel_record_metadata.additional_profile`/intake/import profile; `save_person_additional_profile` is a direct metadata writer, not a section command/event canonical writer. | Do not auto-merge: scalar category/degree cannot safely create structured display records; multiple awards, documents/dates and “none declared” conflict with existing profile require review. | No кадровый приказ normally; document numbers can be sensitive. A dedicated canonical model + events/versioned writer is recommended before mass migration (or an explicit accepted metadata-ownership decision plus migration). |
| Marital status / disability / notes / citizenship/nationality | `ppr.marital_status`, `ppr.disability_summary`, `person.notes`, citizenship/nationality, normalized conservatively by WP-CL-010. | Marital target in catalog is future `person_marital_status` / `PPR-MARITAL-STATUS`; no current supported section/table. Disability has summary only, no designated PPR writer; notes lack a safe canonical destination. | Alias code is not sufficient for automatic legal/status mutation; ambiguity, supporting documents, effective date and existing declaration need manual decision. | No employment order; **sensitive**, especially disability. New model/migration and scoped permissions/audit are required before migration. |

## Writers, audit, permissions and scope

* Existing PPR sections route mutations through `PprSectionApplicationService`/`SectionRepository` and
  append `personnel_record_events` (`PPR_SECTION_ADDED`, `UPDATED`, `SUPERSEDED`, `VOIDED`) with
  command idempotency and optimistic `updated_at` token. Biography and military intentionally use
  supersede/void for correction; military has no update command.
* Section writes currently use `HrImportAdminAuthorizationAdapter`: privileged or personnel-admin
  access, with actor identity check. Query reads are fail-closed via personnel visibility plus
  org scope; person reads resolve visible employee(s), or an intended org unit for applicants.
  This differs from Stage 0/1/2 admin grants (`PPR_STAGE*_..._MANAGE`), so Stage 3 must explicitly
  choose and test its authorization contract rather than assume Stage-2 permission applies.
* Assignment is a separate authoritative and order/audit-bound contour. PPR events must never be
  used to backfill or mutate it.
* Sensitive classifications: relatives (identity/address), military (especially document series/
  numbers, plus VUS/fitness), disability, marital status, IIN/identity, and certificate/diploma
  numbers. The current military DTO already has an elevated details gate; equivalent redaction is
  absent for the other proposed new domains and must precede migration.

## Recommended Stage 3+ order

1. **Stage 3 — training proposal/apply design and pilot:** reuse `TrainingCandidate` provenance;
   define fingerprint/dedup, non-overwrite policy, review queue, event payload and acceptance
   revalidation. Do not use clean parsing as automatic acceptance.
2. **Stage 4 — external-employment source decision:** either explicitly defer (the current control
   list cannot feed it) or first introduce a verified intake/document source and normalizer; then
   use existing biography commands.
3. **Stage 5 — military review-only bridge:** allow summary to produce a manual HR task, never a
   registration row; validate restricted-field permissions and explicit attestation policy before
   any apply capability.
4. **Stage 6 — additional/status architecture:** settle SoT and event/redaction model for marital,
   disability and additional-profile fields. Add canonical schema only after those decisions; do
   not bulk-write metadata as a shortcut.
5. **Outside the PPR migration sequence — assignment reconciliation/orders:** separately reconcile
   `EmploymentCandidate` to OrgUnit/Position and current assignment through the existing
   authoritative кадровый-приказ workflow. It must not be bundled with Stages 3–6.

## Explicit non-actions and review questions

No backend/frontend, migrations, endpoints, DML, seed, commit, push or production action was
performed. Before approval, confirm: (1) whether Stage 3 may persist migration proposals in the
PMF schema; (2) legal/evidence rules for external employment; (3) whether VUS is standard-HR or
elevated-only; and (4) whether additional metadata is accepted as canonical or must be replaced
with record-level models.

## Evidence inspected

* PPR UI/sections: `PprPersonalCardPageClient.tsx`, `pprCardSections.ts`.
* Canonical model/repository/application/read path: `app/db/models/personnel_migration.py`,
  `app/ppr/domain/section_models.py`, `app/ppr/application/section_service.py`,
  `app/ppr/infrastructure/section_repository.py`, `app/ppr/read/query_service.py`.
* Control-list interchange: `domain/vocabulary.py`, `WP-CL-006`, `WP-CL-009`, `WP-CL-010`,
  `header_aliases.py`.
* Assignment and policy: ADR-042 schema migration, `ppr_query_access_service.py`, ADR-056 and
  WP-PR-026.
