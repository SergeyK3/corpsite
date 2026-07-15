--------------------------------------------------

Document Status

Document:
WP-PR-002-aggregate-boundary-specification

Title:
Personnel Personal Record — Aggregate Boundary Specification

Type:
Architecture Work Package

Status:
Completed

Revision:
3

Parent:
ADR-054 — Personnel Personal Record Aggregate Model

Depends on:
ARCH-002, ARCH-002-IMPLEMENTATION-ROADMAP, ADR-054 (DG-1 closed)

Purpose:
Defines the authoritative aggregate boundary for Personnel Personal Record.
Changes to this boundary after acceptance require a new ADR.

--------------------------------------------------

# WP-PR-002 — Aggregate Boundary Specification

**Date:** 2026-07-15

---

## 1. Purpose

Настоящий документ фиксирует **окончательные границы агрегата Personnel Personal Record**
(Личный листок по учёту кадров) для Phase 1 внедрения ARCH-002.

Документ опирается на:

- [ARCH-002](./ARCH-002-personnel-personal-record-architecture.md) — нормативные границы и INV-1…INV-9;
- [ADR-054](../adr/ADR-054-personnel-personal-record-aggregate-model.md) — принятое решение: domain autonomy + Person-root persistence;
- [ARCH-002-IMPLEMENTATION-ROADMAP](./ARCH-002-IMPLEMENTATION-ROADMAP.md) — WP-PR-002 scope.

**Persistence Phase 1 (не подлежит пересмотру в WP-PR-002):**

- Personnel Personal Record — самостоятельный бизнес-объект.
- `person_id` — устойчивый идентификатор Personnel Personal Record.
- Отдельная таблица `personnel_personal_records` и `personal_record_id` **не создаются**.

После утверждения данного документа изменение границ агрегата допускается **только через новый ADR**.

---

## 2. Scope

### In scope

- Границы агрегата Personnel Personal Record (logical + persistence Phase 1).
- Boundary matrix всех связанных repository artifacts.
- Каталог разделов (section catalog) с current/future storage.
- Aggregate invariants, interfaces, events (архитектурный уровень).
- Repository mapping current → future aggregate.
- Boundary risks и Definition of Done.

### Out of scope

- Физическая DDL-схема metadata table (WP-PR-003).
- API contracts и REST paths (WP-PR-005).
- Candidate representation details (OAD-2 / WP-PR-010).
- HIRE apply semantics (OAD-5 / EPIC-5).
- Control Output format (OAD-4 / EPIC-7).
- Код, миграции, UI layout.

### Non-goals

- Повторное обсуждение Variant A/B (DG-1 закрыт).
- Изменение нормативных положений ARCH-002.

---

## 3. Repository Inventory

Read-only инвентаризация сущностей, потенциально связанных с Personnel Personal Record.
Полный аудит ARCH-002 не дублируется.

### 3.1 Identity and Person layer

| Entity | Table / artifact | Location | Role today |
|--------|------------------|----------|------------|
| **Person** | `persons` | `alembic/versions/u3v4w5x6y7z8_adr042_phase_b2_1_schema.py` | **ROOT** / identity anchor Phase 1; permanent identity: `iin`, `full_name`, `match_key`, `person_status`, merge; may exist without activated PPR |
| **Person assignment** | `person_assignments` | same migration §2 | Canonical employment episodes per `person_id` |
| **Employee** | `employees` | `alembic/versions/02b0d99063cd_baseline.py` | Operational shell; `person_id` nullable FK |
| **EmployeeIdentity** | `employee_identities` | `app/db/models/employee_identity.py` | IIN store; employee-scoped |
| **Contacts** | `contacts` | `alembic/versions/f8c2a91b4e10_...` | Operational contact; optional `person_id` |

### 3.2 Employment Relationship layer

| Entity | Table / artifact | Location | Role today |
|--------|------------------|----------|------------|
| **Employment Relationship** | `person_assignments` + `employees` snapshot | ADR-042, C2 sync | Current org placement; not biography store |
| **Employee Events** | `employee_events` | `alembic/versions/b5e2a81d4c03_add_employee_events.py` | Append-only HIRE/TRANSFER/TERMINATION journal |
| **Personnel Orders** | `personnel_orders`, `personnel_order_items`, … | `app/db/models/personnel_orders.py` | Legal employment acts; HIRE requires `employee_id` |
| **Personnel Orders apply** | service | `app/services/personnel_orders_apply_service.py` | Mutates `employees`, emits `employee_events` |
| **HR personnel change events** | `hr_personnel_change_events` | ADR-043 | Canonical diff audit |
| **Canonical snapshot** | `hr_canonical_snapshots`, entries | ADR-040 | Org-wide roster truth |

### 3.3 Personnel Personal Record — implemented sections

| Entity | Table | Location | Role today |
|--------|-------|----------|------------|
| **Person Education** | `person_education` | `app/db/models/personnel_migration.py` | Person-owned SoT (PMF pilot) |
| **Person Training** | `person_training` | same | Person-owned SoT (PMF pilot) |
| **Personnel Record Events** | `personnel_record_events` | same | Section-level **audit/provenance** journal; not section content SoT |
| **PPR metadata** | — | **Not implemented** | Planned: `personnel_record_metadata` (WP-PR-003) |

### 3.4 PMF (Personnel Migration Framework)

| Entity | Table | Location | Role today |
|--------|-------|----------|------------|
| **PMF domains** | `personnel_migration_domains` | `personnel_migration.py` | Plugin registry; `education` enabled |
| **PMF runs** | `personnel_migration_runs` | same | Wizard session audit; keyed by `person_id` |
| **PMF items** | `personnel_migration_items` | same | Staging → target mapping |
| **PMF commit** | service | `personnel_migration_commit_service.py` | Writes `person_*` + events |
| **PMF API** | router | `app/api/personnel_migration_router.py` | `/personnel-migration/*` |
| **Education plugin** | service | `app/services/education_migration_plugin.py` | Domain `education` |

### 3.5 Import and transitional staging

| Entity | Table / artifact | Location | Role today |
|--------|------------------|----------|------------|
| **Import batches/rows** | `hr_import_batches`, `hr_import_rows` | `app/db/models/hr_import.py` | Excel ingest; `normalized_payload` JSONB |
| **Import Profile** | logical (built) | `hr_import_profile_service.build_import_profile()` | Structured sections from staging |
| **Employee Import Profile Overrides** | `employee_import_profile_overrides` | `k4d5e6f7a8b9_adr038_...` | Employee-scoped editable portfolio |
| **Normalized records** | `hr_import_normalized_records` | ADR-039 | Typed import fragments |
| **Document candidates** | `hr_import_document_candidates` | `hr_import.py` | Pre-normalization fragments |
| **Employee documents** | `employee_documents` | `d9e8f71a2b05_...` | Mixed registry; employee-scoped — requires subject split (§5) |

### 3.6 UI projections

| Entity | Artifact | Location | Role today |
|--------|----------|----------|------------|
| **Employee Card (working)** | UI | `corpsite-ui/lib/personnelCardTerminology.ts` | Operational quick view |
| **HR Dossier** | UI + service | `hr_import_employee_card_service.py` | Composite HR view; Import Profile + employee data |
| **Import Profile UI** | components | `ImportProfileCardSections.tsx` | Staging section editor |
| **PPR registry (target)** | — | **Not implemented** | Read model per ADR-054 B-6 |

### 3.7 Exports and derived artifacts

| Entity | Artifact | Location | Role today |
|--------|----------|----------|------------|
| **Control list Excel (import input)** | Excel import | import pipeline | **TEMPORARY** bootstrap input; not target Control Output |
| **Control Output (target)** | — | EPIC-7 (planned) | **DERIVED** from PPR + Employment (INV-7); not implemented |
| **Canonical roster export** | `export_canonical_snapshot_xlsx` | `hr_canonical_snapshot_service` | **DERIVED** legacy/transitional; source = canonical registry, not PPR |
| **Personnel Order print/PDF** | snapshots | Document Engine adapters | **DERIVED** from Personnel Orders; not from PPR |

### 3.8 Access, operations, and adjacent domains

| Entity | Service / doc | Location | Role today |
|--------|---------------|----------|------------|
| **Personnel Visibility** | resolver | `personnel_visibility_resolver_service.py` | ADR-042 E1 read scope by org/position |
| **Position Cabinet** | architecture | ARCH-001, ADR-050 | Operational position container; **out of PPR** |
| **Document Engine (Personnel)** | adapters | `app/document_engine/adapters/personnel/` | Read Personnel **Orders** for print/locale |
| **Candidate** | — | **Not implemented** | Target lifecycle state (OAD-2) |
| **Enrollment queue** | `enrollment_queue` | ADR-042 | Operational enroll path |

---

## 4. Boundary Matrix

Для каждой сущности — один статус относительно агрегата **Personnel Personal Record**.

| Status | Meaning |
|--------|---------|
| **ROOT** | Persistence root Phase 1; identity anchor агрегата (`persons`); не кадровый раздел |
| **IN** | Внутри границы агрегата; authoritative person-owned section data или aggregate envelope |
| **OUT** | Вне агрегата; отдельный bounded context |
| **REFERENCE** | Агрегат ссылается, но не владеет; read/link only |
| **PROJECTION** | Read model / composite view; never SoT |
| **DERIVED** | Производный artifact из aggregate и/или других источников |
| **TEMPORARY** | Transitional/bootstrap; не authoritative SoT |
| **AUDIT** | Внутри логической границы; audit trail / provenance / change history; **не** SoT содержимого разделов |

### Person vs Personnel Personal Record (Phase 1)

| Statement | True |
|-----------|------|
| Person — самостоятельная identity-сущность | ✅ |
| Person — **не** кадровый раздел PPR | ✅ |
| `person_id` — идентификатор Personnel Personal Record Phase 1 | ✅ |
| Personnel Personal Record не существует без Person | ✅ |
| Person может существовать без **активированного** PPR | ✅ (ADR-054 B-2) |
| Наличие Person само по себе **не означает** наличие кадрового листка | ✅ |

| Entity | Status | Explanation |
|--------|--------|---------------|
| **Person** (`persons`) | **ROOT** | Persistence root Phase 1; identity anchor; `person_id` = PPR identifier; Person ≠ PPR; activation отдельно (ADR-054 B-2) |
| **Personnel Personal Record** (logical) | **IN** | Бизнес-объект: ROOT Person + metadata + person-owned sections; не существует без Person |
| **personnel_record_metadata** (planned) | **IN** | Lean envelope: lifecycle, completeness, activation, provenance rollup; не отдельный aggregate root |
| **person_education** | **IN** | Education section **SoT** |
| **person_training** | **IN** | Training section **SoT** |
| **personnel_record_events** | **AUDIT** | Provenance / change history внутри boundary; section tables = SoT, events = audit trail |
| **Future `person_*` sections** | **IN** | Target typed section **SoT** per catalog §6 |
| **Prior Employment / External Service Record** | **IN** | Предыдущие работодатели, внешняя биография до/вне ММЦ; target `person_external_employment` |
| **Internal Employment History** | **PROJECTION** | In-org career: assignments, transfers, orders; sources = Employment BC |
| **Employee** | **OUT** | Operational shell (access, tasks, notifications) |
| **Employment Relationship** | **OUT** | `person_assignments`, `employees` placement snapshot, assignments lifecycle |
| **EmployeeIdentity** | **OUT** | Employee-scoped IIN; bridges to Person via EPIC-10 |
| **Employee Events** | **REFERENCE** | Append-only employment journal; feeds Internal Employment History **projection** |
| **Person Assignments** | **OUT** | Employment episodes; belong to Employment Relationship BC |
| **Personnel Orders** | **OUT** | Legal acts on Employment |
| **Personnel Orders (Document Engine read)** | **REFERENCE** | UDE reads order data for print; not PPR storage |
| **PMF runs / items** | **TEMPORARY** | Controlled migration workflow; audit trail, not section SoT |
| **PMF commit path** | **REFERENCE** | Authoritative **write gateway** into IN sections; framework, not data owner |
| **Import Profile** | **TEMPORARY** | Staging mapper from `hr_import_rows`; bootstrap/reconciliation (INV-8) |
| **employee_import_profile_overrides** | **TEMPORARY** | Employee-scoped transitional portfolio; legacy SoT until read-switch |
| **hr_import_rows / batches** | **TEMPORARY** | Import ingress; JSON staging |
| **hr_import_normalized_records** | **TEMPORARY** | Typed import fragments pre-PMF |
| **PPR personal documents** (target) | **IN** | Удостоверения, дипломы, сертификаты — подтверждения разделов листка |
| **employee_documents** (as-is) | **OUT** | Employee-scoped registry; subject reclassification on migration (§5) |
| **Employment / order documents** | **OUT** | Приказы, employment acts — Personnel Orders / Employment BC |
| **Employee Card (working)** | **PROJECTION** | Operational composite; INV-5 |
| **HR Dossier** | **PROJECTION** | HR composite view; aggregates PPR sections + Employment + import staging |
| **PPR registry UI** (target) | **PROJECTION** | Read model list per B-6; not proof of separate entity table |
| **Control Output (target export)** | **DERIVED** | Future: from PPR + Employment (INV-7, EPIC-7) |
| **Control list Excel (import)** | **TEMPORARY** | Current bootstrap input; not target Control Output |
| **Canonical roster export** | **DERIVED** | Legacy/transitional; source = canonical registry, **not** PPR |
| **Personnel Order PDF/print** | **DERIVED** | From Personnel Orders; **not** from PPR (INV-6) |
| **PPR print snapshot** (target) | **DERIVED** | Personal dossier PDF from PPR sections; snapshot only |
| **Candidate** (lifecycle) | **IN** | HR lifecycle state on aggregate metadata when materialized; not separate entity Phase 1 |
| **Personnel Visibility** | **OUT** | Access control resolver; reads Employment/Person context |
| **Position Cabinet** | **OUT** | ARCH-001 operational contour |
| **Contacts** | **OUT** | Operational contact contour (OPS-026); optional `person_id` link |
| **Users / RBAC** | **OUT** | Security; Employee/User linked |
| **Canonical Registry** | **OUT** | Org roster analytics layer; feeds assignment sync |
| **Enrollment queue** | **OUT** | Operational enroll workflow |

### Aggregate boundary diagram (Phase 1)

```text
┌─────────────────────────────────────────────────────────────┐
│           PERSONNEL PERSONAL RECORD (aggregate)              │
│  Identifier: person_id (ADR-054)                             │
│                                                              │
│  ROOT: persons (identity anchor; Person ≠ PPR)               │
│  IN: personnel_record_metadata (planned envelope)            │
│  IN: person_education, person_training, future person_*       │
│  IN: prior employment / external service record              │
│  AUDIT: personnel_record_events (provenance; not SoT)       │
│  IN: lifecycle / completeness / activation (metadata)        │
│                                                              │
│  Person may exist without activated PPR (ADR-054 B-2)        │
└──────────────────────────┬──────────────────────────────────┘
                           │ person_id
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   TEMPORARY           OUT (Employment)    PROJECTION
   Import Profile      person_assignments   HR Dossier
   Control list Excel  employees            Employee Card
   PMF staging         employee_events      PPR registry (read)
   overrides           Personnel Orders     Internal Employment
                       (Employment BC)      History view
                           │
                           ▼
                      DERIVED (separate sources)
                      Control Output (target) ← PPR + Employment
                      Canonical export ← canonical registry (legacy)
                      Order PDF ← Personnel Orders
                      PPR print snapshot ← PPR sections
```

---

## 5. Aggregate Ownership

Владелец данных по предметным областям. **Owner: none** = projection only.

### 5.1 Aggregate metadata (logical IN; physical table — WP-PR-003)

Следующие metadata **логически входят** в Personnel Personal Record. Физическая таблица в WP-PR-002 **не определяется**. Metadata — **не** отдельный aggregate root; envelope внутри PPR на `person_id`.

| Metadata kind | Content | Notes |
|---------------|---------|-------|
| **Lifecycle metadata** | Candidate / Employee / Former Employee state | On planned envelope; OAD-2 |
| **Completeness metadata** | Per-section rollup, review status | WP-PR-003 |
| **Provenance metadata** | Aggregate-level change basis summary | Complements `personnel_record_events` |
| **Activation metadata** | PPR materialized timestamp, source, dossier status | ADR-054 B-2: activation ≠ Person creation |

### 5.2 Section and domain ownership

| Data domain | Owner | Notes |
|-------------|-------|-------|
| Permanent identity (IIN, match_key, merge) | **Person** (`persons`) | **ROOT**; identity BC; не кадровый раздел PPR |
| Aggregate envelope (lifecycle, completeness, activation) | **Personnel Personal Record** | Logical metadata envelope (planned) |
| Персональные сведения (ФИО, ДР, пол, гражданство) | **Personnel Personal Record** | Identity columns in `persons` (ROOT); cadre-specific fields in future section/metadata |
| Контакты (кадровые) | **Personnel Personal Record** | Target person-owned; today split import / `contacts` (OUT) |
| Адреса | **Personnel Personal Record** | Not implemented |
| **Персональные документы** (удостоверение, диплом, сертификат) | **Personnel Personal Record** | IN — подтверждения разделов листка; target person-owned registry |
| **Employment / order documents** | **Personnel Orders / Employment** | OUT — приказы, employment acts; не PPR |
| **System / access documents** | **none (OUT)** | Operational; не PPR |
| Образование | **Personnel Personal Record** | `person_education` |
| Курсы / обучение | **Personnel Personal Record** | `person_training` |
| Квалификации / категории | **Personnel Personal Record** | Today import JSONB; target `person_qualifications` |
| Учёные степени | **Personnel Personal Record** | Today import `degrees` |
| Языки | **Personnel Personal Record** | Not implemented |
| Награды | **Personnel Personal Record** | Today import `award_records` |
| Родственники / семья | **Personnel Personal Record** | Not implemented |
| Воинский учёт | **Personnel Personal Record** | Not implemented |
| **Prior Employment / External Service Record** | **Personnel Personal Record** | Предыдущие работодатели, периоды, причины; target `person_external_employment`; today `experience_raw` |
| **Internal Employment History** | **Employment / Personnel Orders** | PROJECTION over `employee_events`, `person_assignments`, orders; **не** PPR SoT |
| Должность (текущая) | **Employment Relationship** | `employees.position_id`, assignments |
| Подразделение (текущее) | **Employment Relationship** | `employees.org_unit_id` |
| Ставка, даты назначения | **Employment Relationship** | `employees`, `person_assignments` |
| Приказы HIRE/TRANSFER/TERMINATION | **Personnel Orders** | Employment BC; snapshots in DERIVED PDF |
| Employee Card / HR Dossier | **none** | PROJECTION only (INV-5) |
| Control Output (target) | **none** | DERIVED from PPR + Employment |
| Canonical roster export | **none** | DERIVED from canonical registry (legacy) |
| Import Profile | **none** | TEMPORARY staging |
| Access rights | **none** | OUT — User/Employee/RBAC |
| Tasks / Position Cabinet | **none** | OUT — operational |
| `personnel_record_events` | **none (AUDIT)** | Audit trail; section tables = SoT |

---

## 6. Section Catalog

Полный каталог разделов Personnel Personal Record. Official form superset — ADR-047 appendix §2.2.

**Legend — Current implementation:**

| Code | Meaning |
|------|---------|
| `PERSON_TABLE` | `persons` columns |
| `PMF_TABLE` | person-owned committed table |
| `IMPORT_JSON` | Import Profile / overrides JSONB |
| `IMPORT_NORM` | `hr_import_normalized_records` |
| `EMP_DOC` | `employee_documents` |
| `NONE` | Not implemented |
| `PROJECTION` | Read-only composite |

| Section | Owner | Current storage | Current implementation | Lifecycle | Completeness | SoT today | Expected future state |
|---------|-------|-----------------|------------------------|-----------|--------------|-----------|----------------------|
| **Персональные сведения** | PPR | `persons` + IMPORT_JSON `basic` | Partial: identity in `persons`; sex/nationality import-only | `person_status` on Person | Partial import | Split Person/import | `persons` identity + PPR metadata; PMF/manual for cadre fields |
| **Прежние ФИО** | PPR | NONE | MISSING | — | — | — | `person_name_history` or section table |
| **Фото** | PPR | NONE | MISSING | — | — | — | `person_photo` / files linkage |
| **Документы — персональные / подтверждающие** | PPR | EMP_DOC + IMPORT_NORM | `employee_documents` (employee-scoped); normalized fragments | Per document | Partial | Employee-scoped (OUT today) | Person-owned PPR documents: ID, diplomas, certificates; reclassify on migration |
| **Документы — приказы / employment** | Personnel Orders | `personnel_orders`, attachments | Order PDF via Document Engine | Order lifecycle | N/A | Employment BC | OUT; DERIVED PDF from orders |
| **Контакты** | PPR | IMPORT_JSON `phone_raw` + `contacts` | Split operational vs import | — | Partial | Split | `person_contacts` person-owned |
| **Адреса** | PPR | NONE | MISSING | — | — | — | `person_addresses` |
| **Образование** | PPR | PMF_TABLE + IMPORT_JSON | `person_education` (PMF); import portfolio | `lifecycle_status` per row | PMF `verification_status` | **Dual**: PMF committed = SoT for migrated; import for rest | `person_education` authoritative; import bootstrap only |
| **Специальности** | PPR | PMF_TABLE / IMPORT_JSON | Embedded in education records | Per education row | Partial | Same as education | Column on `person_education` |
| **Квалификации / категории** | PPR | IMPORT_JSON `category_records` | Parser from `certification_raw` | — | Import confidence | IMPORT_JSON | `person_qualifications`; PMF domain |
| **Сертификаты** | PPR | IMPORT_JSON `certificate_records` + IMPORT_NORM | Normalized + profile | — | Partial | IMPORT | `person_certificates`; PMF domain |
| **Курсы / обучение** | PPR | PMF_TABLE + IMPORT_JSON | `person_training` (PMF pilot planned); `training_records` | `lifecycle_status` | `verification_status` | Dual path | `person_training` authoritative |
| **Учёные степени** | PPR | IMPORT_JSON `degrees` | `degree_raw` parser | — | Partial | IMPORT | `person_academic_degrees` |
| **Языки** | PPR | NONE | MISSING | — | — | — | `person_languages` |
| **Награды** | PPR | IMPORT_JSON `award_records` | `awards_raw` parser | — | Partial | IMPORT | `person_awards`; PMF domain |
| **Воинский учёт** | PPR | NONE | MISSING (form §15) | — | — | — | `person_military_service` or out-of-scope flag |
| **Семейное положение** | PPR | NONE | MISSING | — | — | — | `person_marital_status` |
| **Родственники** | PPR | NONE | MISSING (form §13) | — | — | — | `person_relatives` |
| **Prior Employment / External Service Record** | PPR | IMPORT_JSON `experience_raw` | Unstructured text; external employers | Per employment episode | Low | IMPORT | `person_external_employment` structured (employer, dept, position, period, termination reason) |
| **Internal Employment History** | Employment (PROJECTION) | `employee_events`, `person_assignments` | ADR-047 timeline SQL; in-org only | Event append-only | N/A | Employment BC | Read projection; edits via orders/events only; **не** mutable PPR section |
| **Дисциплинарные взыскания** | PPR | NONE | ADR-036 designed; not implemented | — | — | — | Append-only person-owned or event-linked |
| **Дополнительные сведения** | PPR | IMPORT_JSON `notes_raw`, `portfolio_totals` | Misc import fields | — | — | IMPORT | `person_misc` or typed extensions |
| **Aggregate metadata** | PPR | NONE | Not implemented | Candidate/Employee/Former (OAD-2) | Rollup TBD | — | `personnel_record_metadata` per ADR-054 |

### Phase 1 authoritative sections (committed SoT)

| Section | Table | Write path |
|---------|-------|------------|
| Education | `person_education` | PMF commit |
| Training | `person_training` | PMF commit (domain planned) |

All other sections remain import-staged or missing until PMF domain expansion (EPIC-4) or direct person-scoped API (EPIC-3).

---

## 7. Aggregate Invariants

Расширяют ARCH-002 INV-1…INV-9. Противоречие ARCH-002 **запрещено**.

### 7.1 From ARCH-002 (mandatory)

| ID | Invariant |
|----|-----------|
| INV-1 | Один Person — одна постоянная идентичность |
| INV-2 | Один Personnel Personal Record на Person на весь lifecycle |
| INV-3 | PPR не копируется при HIRE, transfer, rehire |
| INV-4 | Employment Relationship не хранит кадровую биографию |
| INV-5 | Employee Card / HR Dossier — только Composite View |
| INV-6 | Документы и exports — snapshot; не mutating authoritative data |
| INV-7 | Control Output — производный, не первичный input (target) |
| INV-8 | Import Profile — transitional/bootstrap only |
| INV-9 | Personnel Orders меняют Employment, не PPR sections (кроме post-hire append с provenance) |

### 7.2 Aggregate boundary invariants (WP-PR-002)

| ID | Invariant |
|----|-----------|
| **AB-1** | Person — **ROOT** Phase 1; Person ≠ Personnel Personal Record; у Person — не более одного PPR (logical) |
| **AB-2** | `person_id` — единственный публичный идентификатор PPR в Phase 1 |
| **AB-3** | Personnel Personal Record **не хранит** текущую должность, подразделение, ставку |
| **AB-4** | Personnel Personal Record **не хранит** Personnel Orders, order items, order lifecycle |
| **AB-5** | Personnel Personal Record **не хранит** права доступа, RBAC, User, Position Cabinet |
| **AB-6** | Personnel Personal Record **не хранит** operational tasks, notifications, Telegram binding |
| **AB-7** | **Prior Employment / External Service Record** — IN PPR; structured external biography preserved |
| **AB-8** | **Internal Employment History** — PROJECTION/REFERENCE; owned by Employment / Personnel Orders, not PPR |
| **AB-9** | Наличие Person **не означает** автоматическую активацию PPR; activation — отдельное событие (B-2) |
| **AB-10** | PPR не существует без Person; Person может существовать без activated PPR |
| **AB-11** | Все authoritative PPR section **content** — person-owned tables (`person_id` FK); не employee-scoped SoT |
| **AB-12** | `personnel_record_events` — **AUDIT** trail; section tables = SoT; events не заменяют section data |
| **AB-13** | PMF commit — controlled write path into IN sections; PMF workflow tables — TEMPORARY |
| **AB-14** | Import Profile и overrides — never authoritative after read-switch per section (EPIC-6) |
| **AB-15** | PPR registry UI — read model; не создаёт отдельный aggregate ID (B-6) |
| **AB-16** | DERIVED artifacts (Control Output, order PDF, PPR print, canonical export) — snapshots; **не** SoT |

---

## 8. Aggregate Interfaces

Архитектурные взаимодействия (не API). «Кто» — bounded context / subsystem.

### 8.1 Read

| Actor | May read | Constraint |
|-------|----------|------------|
| **HR Dossier composite reader** | All IN sections + Employment REFERENCE | PROJECTION; flag-gated read-switch (EPIC-6) |
| **PPR registry read model** | Aggregate metadata + section summaries | Read-only list (B-6) |
| **PMF wizard** | Staging + committed sections for domain | Employee context for UX; writes via commit |
| **Import Profile UI** | TEMPORARY staging only | Legacy until section migrated |
| **Personnel Visibility resolver** | Indirect via Employment/Person | OUT; org scope |
| **Control Output exporter** (target) | IN sections + Employment projection | DERIVED from PPR; EPIC-7 |
| **Canonical export** | Canonical registry | DERIVED legacy; not PPR source |
| **Document Engine (orders)** | Personnel Orders only | DERIVED PDF; not PPR |
| **Internal Employment History view** | `employee_events`, `person_assignments`, orders | PROJECTION; Employment BC |
| **Prior Employment section reader** | `person_external_employment` (target) | IN section SoT |
| **Employee (self)** | Policy-gated subset via Employee Card | PROJECTION |

### 8.2 Write / mutate

| Actor | May mutate | Constraint |
|-------|------------|------------|
| **PMF commit** | IN section tables | Per domain plugin; requires `person_id` |
| **Person-scoped PPR API** (future EPIC-3) | IN sections + metadata | Direct authoritative write |
| **Import pipeline** | TEMPORARY staging only | Bootstrap; not aggregate SoT |
| **HR manual correction** (future) | IN sections | Requires provenance event |
| **Personnel Orders apply** | Employment OUT entities only | INV-9; no direct PPR section mutation |
| **Employee Card / HR Dossier** | **Never** | INV-5; command surface routes to services |

### 8.3 Section lifecycle operations

| Operation | Actor | Target |
|-----------|-------|--------|
| Add section record | PMF / PPR API | IN section table + event |
| Supersede / void section | PMF mutation API | `lifecycle_status` on section + event |
| Update completeness | Metadata service | `personnel_record_metadata` rollup |
| Verify section | HR reviewer | `verification_status` on section row |

### 8.4 Snapshots and exports

| Operation | Actor | Output |
|-----------|-------|--------|
| Form PPR print snapshot | Export service (future) | DERIVED PDF from PPR sections; INV-6 |
| Form Control Output (target) | Export service (EPIC-7) | DERIVED Excel from PPR + Employment |
| Form canonical roster export | Canonical service | DERIVED Excel from canonical registry (legacy) |
| Form order print | Document Engine | DERIVED PDF from Personnel Orders; not PPR |

### 8.5 Cross-aggregate operations

| Operation | Actor | Notes |
|-----------|-------|-------|
| Create Candidate | HR intake (EPIC-2) | Materialize PPR metadata; no Employee required |
| Create Employment | HIRE apply (EPIC-5) | **External** — Employment BC; PPR only consumes/reflected in projection |
| Form HIRE order | Personnel Orders editor | Selects Person/PPR Candidate; applies to Employment |
| Materialize Person on enroll | EPIC-10 / enrollment | Creates/links `persons`; may create PPR metadata |

---

## 9. Aggregate Events

Архитектурная event model. Не меняет `personnel_record_events` schema в WP-PR-002.

**Принцип:** section tables / person-owned data = **Source of Truth**; `personnel_record_events` = **audit / provenance / change history** (AUDIT); не дублируют и не заменяют section content.

### 9.1 Internal aggregate events (emitted by PPR)

События, которые агрегат **выпускает** при изменении своих IN stores или metadata.

| Event | Trigger | Aggregate role |
|-------|---------|----------------|
| `PERSONNEL_PERSONAL_RECORD_ACTIVATED` | Person enters HR contour; metadata materialized | Envelope |
| `PERSONNEL_PERSONAL_RECORD_LIFECYCLE_CHANGED` | Internal lifecycle metadata update | Envelope |
| `PERSONNEL_PERSONAL_RECORD_COMPLETENESS_CHANGED` | Section rollup recompute | Envelope |
| `PERSONNEL_PERSONAL_RECORD_ARCHIVED` | Dossier closed | Envelope |
| `SECTION_UPDATED` | Manual/PMF section write | Section + AUDIT event row |
| `EDUCATION_MIGRATED` / `EDUCATION_VERIFIED` / … | PMF domain commit | Section + AUDIT (✅ partial) |
| `RELATIVE_ADDED` / `AWARD_APPENDED` / … | Future section writes | Section + AUDIT |
| `SNAPSHOT_GENERATED` | PPR print/export formed | DERIVED artifact; does not mutate SoT (INV-6) |

### 9.2 Audit events (`personnel_record_events`)

| Role | Description |
|------|-------------|
| **Classification** | AUDIT — inside logical boundary |
| **SoT** | **No** — audit trail only |
| **Content SoT** | `person_education`, `person_training`, future `person_*` tables |
| **Purpose** | Provenance, actor, migration run linkage, change history |

### 9.3 External / integration events (consumed or reflected, not owned)

События других bounded contexts. PPR **не выпускает** их; может **отражать** в projection или metadata.

| Event | Owner BC | PPR relation |
|-------|----------|--------------|
| `CANDIDATE_STATUS_CHANGED` | HR intake / lifecycle (EPIC-2) | May update lifecycle metadata; external trigger |
| `EMPLOYMENT_CREATED` | Employment (HIRE apply) | **External** — not internal PPR event |
| `EMPLOYMENT_TERMINATED` | Employment | **External** — reflected in Internal Employment History projection |
| `HIRE` / `TRANSFER` / `TERMINATION` | `employee_events` | Feeds Internal Employment History projection |
| `PERSONNEL_ORDER_APPLIED` | Personnel Orders | Employment BC; DERIVED order PDF |
| `IMPORT_BATCH_APPLIED` | Import | Updates TEMPORARY staging only |
| `PMF_RUN_COMMITTED` | PMF | Triggers internal section + AUDIT events |
| `CONTROL_OUTPUT_EXPORTED` | Export (EPIC-7) | DERIVED from PPR + Employment |
| `CANONICAL_ROSTER_EXPORTED` | Canonical registry | DERIVED legacy; independent of PPR |

---

## 10. Repository Mapping

Current repository artifact → future aggregate role.

| Current repository | Future aggregate role |
|--------------------|----------------------|
| `persons` | **ROOT** — identity anchor; `person_id` = PPR identifier; Person ≠ PPR |
| `personnel_record_metadata` (planned) | **IN** — envelope (lifecycle, completeness, activation); not separate root |
| `person_education` | **Education Section** (IN, SoT) |
| `person_training` | **Training Section** (IN, SoT) |
| `person_external_employment` (planned) | **Prior Employment Section** (IN, SoT) |
| `personnel_record_events` | **AUDIT** — provenance journal; not section SoT |
| `personnel_migration_runs` / `items` | **TEMPORARY** migration workflow |
| `personnel_migration_domains` | PMF domain registry (REFERENCE config) |
| `hr_import_rows.normalized_payload` | **TEMPORARY** import staging |
| `build_import_profile()` output | **TEMPORARY** Import Profile view |
| `employee_import_profile_overrides` | **TEMPORARY** legacy portfolio per employee |
| `hr_import_normalized_records` | **TEMPORARY** typed import fragments |
| `employee_documents` (PPR-relevant subset) | Reclassify → **IN** personal/confirming docs only |
| `employee_documents` (employment subset) | **OUT** — employment/order docs |
| `employees` | **Employment Relationship** (OUT) |
| `person_assignments` | **Employment Relationship** (OUT) |
| `employee_events` | **Internal Employment History** projection source (REFERENCE) |
| `employee_identities` | **OUT**; bridge to Person (EPIC-10) |
| `personnel_orders` + items | **Personnel Orders** (OUT) |
| `hr_import_employee_card_service` | **HR Dossier PROJECTION** composer |
| `corpsite-ui` Employee Card / Dossier | **PROJECTION** UI |
| Control list Excel import | **TEMPORARY** bootstrap input |
| Control Output export (target) | **DERIVED** from PPR + Employment (EPIC-7) |
| `export_canonical_snapshot_xlsx` | **DERIVED** legacy from canonical registry |
| Document Engine `personnel/*` adapters | **DERIVED** order PDF from Personnel Orders |
| Internal Employment History view | **PROJECTION** over Employment sources |
| `personnel_visibility_resolver_service` | **OUT** access scope |
| Candidate (not implemented) | **IN** lifecycle state on metadata |
| `contacts` | **OUT** operational; optional link to Person |
| `hr_canonical_snapshots` | **OUT** canonical registry |
| `enrollment_queue` | **OUT** operational enroll |

---

## 11. Boundary Risks

| Risk | Reason | Mitigation |
|------|--------|------------|
| **Дублирование данных** | Import Profile + `person_education` dual path | Section-by-section read-switch; reconciliation WP-PR-073; AB-14 |
| **Перемещение ownership** | `employee_documents` mixed employment + personal | Subject classification §5; PPR-relevant subset only → IN |
| **Metadata creep** | `personnel_record_metadata` grows into stealth header entity | Lean scope WP-PR-003; ADR-054 Future Triggers; not separate root |
| **Projection becomes SoT** | HR Dossier edit saves to overrides | INV-5 reviews; commands route to PMF/PPR API only |
| **Import-first regression** | New sections only in Import JSON | AB-11; new sections must be `person_id` FK tables |
| **Service Record conflation** | Merging prior + internal employment into one editable table | AB-7 vs AB-8; preserve structured prior employment IN PPR |
| **Internal history in PPR** | Storing assignments/orders inside PPR | AB-8; Internal Employment History = projection only |
| **Employment data in PPR** | `basic.position_raw` in Import Profile | AB-3; strip from target PPR sections on migration |
| **employee_identities drift** | IIN on Employee not Person | EPIC-10 alignment |
| **PMF bypass** | Direct SQL to `person_education` | All writes through PMF or PPR API; AUDIT events required (AB-12) |
| **Registry implies entity** | PPR list UI drives `personal_record_id` demand | B-6 explicit: read model ≠ persistence proof |
| **Audit mistaken for SoT** | Rebuilding sections from `personnel_record_events` alone | AB-12; section tables authoritative |
| **Export conflation** | Treating canonical export or order PDF as PPR SoT | AB-16; separate DERIVED sources |

---

## 12. Definition of Done

WP-PR-002 считается **завершённым**, когда:

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Документ `WP-PR-002-aggregate-boundary-specification.md` опубликован в `docs/architecture/` | ✅ |
| 2 | Boundary matrix покрывает все сущности из §3 inventory | ✅ |
| 3 | Section catalog содержит все разделы ARCH-002 «Границы агрегата» + gaps из ADR-047 | ✅ |
| 4 | Aggregate invariants AB-1…AB-16 не противоречат INV-1…INV-9 | ✅ |
| 5 | Person-root persistence (ADR-054) отражён; Variant A не предлагается | ✅ |
| 6 | Repository mapping current → future задокументирован | ✅ |
| 7 | Stakeholder review: границы приняты или замечания зафиксированы | ✅ |
| 8 | WP-PR-003 может начаться без неопределённости ownership по разделам | ✅ |

**Изменение границ после acceptance:** только новый ADR + amendment trail.

---

## 13. Related Documents

| Document | Relation |
|----------|----------|
| [ARCH-002](./ARCH-002-personnel-personal-record-architecture.md) | Normative aggregate scope; INV-1…INV-9 |
| [ARCH-002-IMPLEMENTATION-ROADMAP](./ARCH-002-IMPLEMENTATION-ROADMAP.md) | WP-PR-002; EPIC-1 Foundation |
| [ADR-054](../adr/ADR-054-personnel-personal-record-aggregate-model.md) | Accepted aggregate model; DG-1 closed; B-1…B-6 |
| [ADR-047](../adr/ADR-047-personnel-personal-file-architecture.md) | Personal File sections; Service Record projection |
| [ADR-047 Four-Layer Model](../adr/ADR-047-appendix-four-layer-model.md) | Official form section catalog; import vs PF |
| [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md) | Person materialization policy |
| [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md) | PMF commit framework |
| [ADR-EDU-001](../adr/ADR-EDU-001-employee-education-migration-architecture.md) | Education domain migration |
| [ADR-042 Phase B1](../adr/ADR-042-phase-b1-schema-design.md) | `persons`, `person_assignments` |
| [ADR-050](../adr/ADR-050-organization-position-cabinet-model.md) | Position Cabinet — OUT of PPR |

### Downstream work packages unlocked

| WP | Dependency from WP-PR-002 |
|----|---------------------------|
| WP-PR-003 | Section catalog §6 → completeness model |
| WP-PR-004 | AB-1, AB-9, AB-10 → linkage rules |
| WP-PR-005 | §8 interfaces → composite read contract |
| WP-PR-006 | §9 events → taxonomy extension |

---

## Document History

| Revision | Date | Change |
|----------|------|--------|
| 1 | 2026-07-15 | Initial aggregate boundary specification (WP-PR-002) |
| 2 | 2026-07-15 | Final review: Person→ROOT; service record split; AUDIT events; internal/external events; export separation; metadata §5.1; document boundary; AB-1…AB-16 |
| 3 | 2026-07-15 | Accepted; status Completed; Definition of Done closed |
