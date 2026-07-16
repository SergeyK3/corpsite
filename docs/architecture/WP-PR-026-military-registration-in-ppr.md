--------------------------------------------------

Document Status

Document:
WP-PR-026-military-registration-in-ppr

Title:
Military Registration in PPR (Воинский учёт) — Architecture Decision Record

Type:
Architecture Decision Record (ADR-style) — EPIC-4 section design

Status:
Accepted — 2026-07-16 (rev. 0.2)

Revision:
0.2

Date:
2026-07-16

Work Package:
WP-PR-026 (design only)

Parent:
EPIC-4 — Person-owned section expansion (ARCH-002)

Depends on:
ADR-054; WP-PR-002 (Completed); WP-PR-003 (Draft — Ready for Review); WP-PR-008…011; WP-PR-012 (R0–R7 Complete); WP-PR-P4-001 (PPR-FAMILY pattern); ADR-056 (Employment Biography — explicit non-overlap; WP-PR-013…025 track)

Related:
ADR-047 appendix §2.2 (form §15); ADR-055 (`OR-HR-MGR-UHR-MIL`); docs-work/WP-PR-P4-BACKLOG-PPR-MILITARY.md

Runtime effect:
**None** — no migrations, tables, code, API, or UI in this ADR

Applicant → Employee:
**Unchanged** — Hire flow, envelope lifecycle per ADR-054-NOTE

Purpose:
Normative architecture for PPR section **PPR-MILITARY** (`person_military_service`) before implementation.

--------------------------------------------------

# WP-PR-026 — Military Registration in PPR (Воинский учёт)

## Status

**Accepted** — 2026-07-16 (rev. 0.2)

| Field | Value |
|-------|-------|
| Work Package | **WP-PR-026** — ADR / design (this document) |
| Implementation track | **WP-PR-027…031** (§19); **не пересекается** с ADR-056 Employment Biography WP-PR-013…025 |
| Parent | [ADR-054](../adr/ADR-054-personnel-personal-record-aggregate-model.md); [ARCH-002](./ARCH-002-personnel-personal-record-architecture.md) |
| Related | [WP-PR-002](./WP-PR-002-aggregate-boundary-specification.md); [WP-PR-003](./WP-PR-003-section-catalog-and-completeness-model.md); [WP-PR-P4-001](./WP-PR-P4-001-person-relatives-ppr-family.md); [ADR-047 appendix](../adr/ADR-047-appendix-four-layer-model.md); [ADR-055](../adr/ADR-055-operational-role-architecture.md); [ADR-056](../adr/ADR-056-employment-biography-in-ppr.md) |
| Runtime effect | **None** — no migrations, tables, or code in this ADR |
| Applicant → Employee | **Unchanged** |

---

## 1. Problem Statement

### 1.1. Симптомы

| Наблюдение | Факт |
|------------|------|
| Официальная форма личного листка §15 | «Воинская обязанность, звание» — **MISSING** в Corpsite |
| PPR section catalog | `PPR-MILITARY` зарегистрирована в WP-PR-003 как **IN**, **0..1**, **CONDITIONAL**, **RESTRICTED** |
| Control list Excel | **Нет** колонки воинского учёта — greenfield, как PPR-FAMILY |
| PPR Query API | `SUPPORTED_SECTION_CODES` не содержит `PPR-MILITARY` |
| UI личной карточки | Секция «Воинский учёт» — Future ([WP-HR-CARD-002](./WP-HR-CARD-002-unified-personnel-record-card.md)) |
| Операционная роль | `OR-HR-MGR-UHR-MIL` («Воинский учёт») существует в ADR-055, но **без** typed person-owned SoT |

### 1.2. Нормативный разрыв

Официальный личный листок по учёту кадров (Приложение № 2, п. 15) требует фиксации **воинской обязанности и звания**. Отдельная **карточка Т-2** (Приказ МО РК № 28) — **другой контур**; в Phase 1 PPR покрывает **кадровый срез §15**, не полный воинский документооборот.

### 1.3. Цель ADR

Зафиксировать архитектуру секции **«Воинский учёт»** в PPR так, чтобы:

1. Определить **person-owned Source of Truth** внутри aggregate Personnel Personal Record.
2. Отделить PPR-MILITARY от PPR-FAMILY, Employment BC, Personnel Orders и формы Т-2.
3. Задать каноническую модель, инварианты, API и UI **до** кодирования.
4. Стать базой для **WP-PR-027…031** (implementation slices).

---

## 2. Existing Architecture

### 2.1. PPR aggregate (ADR-054 Variant B)

```text
Person (aggregate root, person_id)
  ├── personnel_record_metadata     [AGGREGATE-ENVELOPE]
  ├── person_education              [PPR-EDUCATION — implemented]
  ├── person_training               [PPR-TRAINING — implemented]
  ├── person_relatives              [PPR-FAMILY — implemented]
  ├── person_external_employment    [PPR-EMPLOYMENT-BIOGRAPHY — implemented]
  ├── personnel_record_events       [AUDIT]
  └── [missing] person_military_service  [PPR-MILITARY]
```

Composite read собирает `general`, `education`, `training`, `family`, `employment_biography`, `intended_employment` (CANDIDATE), `events`. Military slice **отсутствует**.

### 2.2. Смежные контуры (OUT of PPR-MILITARY)

| Artifact | Role | Relationship to military |
|----------|------|------------------------|
| `persons.sex`, `birth_date`, nationality/citizenship | PPR-GENERAL scalars | **Не** используются для автоматических правил applicability Phase 1 |
| `person_relatives.organization_name` | Family cadre row | Может содержать «Воинская часть …» как **место работы родственника** — **не** воинский учёт сотрудника |
| `employees`, `person_assignments`, `personnel_orders` | Employment BC | **Не** хранят воинский учёт |
| Карточка Т-2 | Отдельный нормативный контур | **Out of scope** Phase 1 ([ADR-047 appendix](../adr/ADR-047-appendix-four-layer-model.md) §2.1) |
| `employee_documents` / file storage | Document registry | **Out of scope** Phase 1 — no scans, no `person_documents` FK |

### 2.3. UI личной карточки (каноническая)

`PprPersonalCardPageClient` — секция «Воинский учёт» **не монтируется**. Навигация и composite API не содержат `PPR-MILITARY`.

### 2.4. Реализованный шаблон секции (reference)

PPR-FAMILY и PPR-EMPLOYMENT-BIOGRAPHY задают vertical slice:

- `SectionRepository` + domain handlers
- `PprSectionApplicationService` + `personnel_record_events`
- `PprSectionAggregationReader` + Query API additive contract
- Read-only UI + lifecycle buckets (`active` / `superseded` / `voided`)
- Architecture guard tests (no cross-BC writes)

**PPR-MILITARY** следует тому же шаблону с учётом cardinality **0..1 active** (§5).

---

## 3. Domain Analysis

### 3.1. Что такое «Воинский учёт» в PPR

| Aspect | Definition |
|--------|------------|
| **Смысл** | Кадровый учёт сведений о воинской обязанности, постановке/снятии с учёта, звании, ВУС и связанных атрибутах **самого человека** (работника/заявителя) |
| **SoT** | **`person_military_service`** (`PPR-MILITARY`) |
| **Projection** | Composite read slice; future print §15; completeness findings |
| **Aggregate owner** | **Personnel Personal Record** (`person_id`) |
| **Lifecycle** | Create; corrections **только** supersede / void; **переживает** Hire, Rehire, Termination |
| **Sensitivity** | **RESTRICTED** (WP-PR-003, WP-PR-005) |

**Не включает:**

- воинские сведения **родственников** (PPR-FAMILY / `organization_name`);
- internal career, приказы, назначения (Employment / Orders BC);
- полный документооборот Т-2 и учётные журналы военкомата;
- **файловые документы** (сканы военного билета, приписного) — Phase 2+.

### 3.2. Связь с формой §15 vs Т-2

| Контур | Норматив | Corpsite Phase 1 |
|--------|----------|------------------|
| **Личный листок §15** | Воинская обязанность, звание (summary) | **PPR-MILITARY** — target |
| **Карточка Т-2** | Полный воинский учёт (Приказ МО РК № 28) | **Out of scope** — отдельный WP / bounded context |

**Правило MIL-BOUNDARY (closed):** PPR-MILITARY Phase 1 = **кадровый срез §15** для HR-листка. Не замена воинскому столу; не полная Т-2. Расширение до Т-2 parity — отдельное архитектурное решение.

### 3.3. Applicability (CONDITIONAL)

Секция **не универсальна**. Phase 1 **не вводит** автоматических правил по полу, возрасту или гражданству.

| `applicability_result` | Смысл для completeness | Phase 1 default |
|------------------------|------------------------|-----------------|
| `APPLICABLE` | Требуется заполнение `registration` или явная HR attestation `not_applicable` | Manual HR / policy later |
| `NOT_APPLICABLE` | Секция исключена из denominator | Via explicit `not_applicable` row only |
| `UNKNOWN` | Policy/legal не определён — **WARNING**, не BLOCKING | **Default** |

**Closed (D6):** applicability по умолчанию **`UNKNOWN`**. Автоматические правила `MILITARY_KZ_CITIZEN_MALE_18_50` и аналоги — **не вводятся** в Phase 1.

**Closed (D7):** `record_kind = not_applicable` — **явная HR attestation** («не подлежит воинскому учёту»), отличимая от пустой секции и от computed applicability.

---

## 4. Alternatives Considered

### 4.1. Хранить воинский учёт в `person_relatives` или `organization_name`

**Rejected.** [WP-PR-P4-BACKLOG](../docs-work/WP-PR-P4-BACKLOG-PPR-MILITARY.md) явно запрещает.

### 4.2. Scalar columns на `persons` / envelope

**Rejected.** Следовать typed `person_*` section table.

### 4.3. `person_military_service` vs `person_military_registration`

**Accepted:** **`person_military_service`** — per WP-PR-002 / WP-PR-003.

### 4.4. Cardinality 0..N (история званий как multiple active rows)

**Rejected.** Каталог задаёт **0..1 active** per `person_id`. История — **только** через `superseded` / `voided` rows, не multiple active.

### 4.5. `record_kind` — нужен ли?

**Accepted (D4):** `record_kind` **вводится** с двумя значениями: `registration` | `not_applicable`. Episode-style kinds **не нужны**.

### 4.6. Отдельная команда `UpdateMilitaryRegistration`

| Pros | Cons |
|------|------|
| Меньше rows при мелких правках | Два write path; слабее audit; расходится с supersede-first policy |

**Rejected (D9).** Все исправления содержания — **только** `SupersedeMilitaryRegistration` или `VoidMilitaryRegistration` + новый `Create`. In-place update **запрещён**.

---

## 5. Decision Summary (closed)

| ID | Decision | Value |
|----|----------|-------|
| **D1** | Section / table | `PPR-MILITARY` → `person_military_service`; PK `military_id` |
| **D2** | Owner | **`person_id`** only; one Person → one PPR; no fork on Hire |
| **D3** | Т-2 boundary | Phase 1 = **кадровый срез §15**; полная Т-2 **out of scope** |
| **D4** | `record_kind` | `registration` \| `not_applicable` |
| **D5** | Cardinality | **0..1 active** row per `person_id`; history via supersede/void only |
| **D6** | Applicability default | **`UNKNOWN`**; no auto sex/age/citizenship rules Phase 1 |
| **D7** | `not_applicable` | **Explicit HR attestation** row; not inferred from demographics |
| **D8** | Document numbers | **RESTRICTED** scalar fields; redaction on read (§13.4) |
| **D9** | Mutation model | **No** `UpdateMilitaryRegistration`; supersede/void only for corrections |
| **D10** | File documents | **Out of scope** Phase 1 — no scans, no `person_documents` linkage |
| **D11** | Applicant → Employee | Rows **preserved**; Employment BC **does not write** |

### D1. Section code and storage

| Item | Value |
|------|-------|
| **Section code** | `PPR-MILITARY` |
| **Display name (RU)** | Воинский учёт |
| **Storage table** | **`person_military_service`** |
| **PK column** | `military_id` |
| **Cardinality** | **0..1 active** row per `person_id` (+ historical superseded/voided) |
| **Aggregate classification** | **IN** (person-owned PPR section SoT) |

### D4. `record_kind` enum (Phase 1)

| Code | RU label (display) | Purpose |
|------|-------------------|---------|
| `registration` | Сведения о воинском учёте | Основная запись |
| `not_applicable` | Не подлежит воинскому учёту | **Явная HR attestation** |

---

## 6. Aggregate Boundaries

```text
┌──────────────────────────────────────────────────────────────────────┐
│         PERSONNEL PERSONAL RECORD (aggregate, person_id)              │
│                                                                       │
│  IN SoT:                                                              │
│    person_military_service     ← PPR-MILITARY (NEW)                  │
│    person_education, person_training, person_relatives, …             │
│                                                                       │
│  AUDIT: personnel_record_events                                       │
│  ENVELOPE: personnel_record_metadata                                  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ person_id
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   PPR-GENERAL              EMPLOYMENT BC            PERSONNEL ORDERS BC
   persons scalars          employees                 personnel_orders
   (no auto applicability)  person_assignments        (no military write)
                            employee_events
        │
        ▼
   OUT OF SCOPE Phase 1
   Т-2 card · военкомат journal · file documents
```

### 6.1. Invariants

| ID | Invariant |
|----|-----------|
| **MIL-1** | Owner = **`person_id`** only; `employee_id` is not SoT owner |
| **MIL-2** | At most **one** row with `lifecycle_status = active` per `person_id` |
| **MIL-3** | Content corrections **only** via **supersede** or **void** + new create; **no** in-place update command; hard delete forbidden |
| **MIL-4** | `record_kind = not_applicable` forbids all military attribute fields (rank, VUS, commissariat, document numbers, obligation_status, …) — only `notes` / `provenance` allowed |
| **MIL-5** | `record_kind = registration` requires **at least one** structured field among: `obligation_status`, `registration_category`, `military_rank`, `registration_status`. **`notes` alone is insufficient.** |
| **MIL-6** | Rows **survive** Hire, Rehire, Termination on same `person_id` |
| **MIL-7** | Employment BC and Personnel Orders **must not** write `person_military_service` |
| **MIL-8** | **No** FK from `person_military_service` to `employees`, `person_assignments`, `personnel_orders` |
| **MIL-9** | Sensitivity **RESTRICTED** — RBAC/redaction on read; grant `VIEW_MILITARY_DETAILS` (§13.4) |
| **MIL-10** | PPR-FAMILY `organization_name` **must not** be used as proxy for employee military data |
| **MIL-11** | Internal → military reverse sync **forbidden** (no derivation from orders/events) |
| **MIL-12** | `employee_context_id` — optional audit; **not** FK to `employees` |
| **MIL-13** | Phase 1 **forbids** file document storage / `person_documents` FK on military rows |

### 6.2. Summary rule

> **Правило MIL-SUM:** Воинский учёт — **постоянный person-owned слой** PPR. Одна **active** запись на Person; история **только** supersede/void; переживает смену `hr_relationship_context`; единственный write path — PPR section commands (create / supersede / void / verify); единственный read SoT — `person_military_service`.

---

## 7. Source of Truth

| Data domain | Primary SoT | Transitional input | PPR role |
|-------------|-------------|-------------------|----------|
| **Воинский учёт сотрудника/заявителя** | `person_military_service` | None (greenfield) | **IN SoT** |
| **HR attestation «не подлежит»** | `person_military_service` row `record_kind = not_applicable` | Manual HR | **IN SoT** |
| **Applicability (computed)** | Completeness engine | Manual policy later | Default **`UNKNOWN`** Phase 1 |
| **Воинская часть родственника** | `person_relatives.organization_name` | — | **PPR-FAMILY** — separate |
| **Карточка Т-2** | External / future BC | — | **OUT** Phase 1 |
| **Скан военного билета** | — | — | **OUT** Phase 1 |

---

## 8. Data Provenance

### 8.1. `source_type`

| `source_type` | Phase 1 |
|---------------|---------|
| `entered` | ✅ Primary (HR manual) |
| `imported` / `normalized` / `derived` | ❌ Reserved |

PMF plugin: **not required** Phase 1 (no legacy source).

### 8.2. Audit trail

Все мутации → `personnel_record_events` with `section_code = PPR-MILITARY`, `record_table_name = person_military_service`.

Event types: `PPR_SECTION_RECORD_ADDED`, `VOIDED`, `SUPERSEDED`, `VERIFIED` — **no** `UPDATED` (update command absent).

---

## 9. Canonical Data Model (design only)

### 9.1. Domain entity: `MilitaryServiceRecord`

```text
MilitaryServiceRecord
├── military_id: int | None
├── person_id: int                    # aggregate owner (FK → persons)
├── record_kind: str                  # registration | not_applicable
├── obligation_status: str | None
├── registration_category: str | None
├── military_rank: str | None
├── military_specialty_code: str | None
├── personnel_composition: str | None
├── fitness_category: str | None
├── registration_status: str | None
├── commissariat_name: str | None
├── registered_at: date | None
├── deregistered_at: date | None
├── military_id_book_series: str | None       # RESTRICTED — optional Phase 1
├── military_id_book_number: str | None        # RESTRICTED — optional Phase 1
├── registration_certificate_series: str | None  # RESTRICTED — optional Phase 1
├── registration_certificate_number: str | None
├── notes: str | None
├── verification_status: str
├── lifecycle_status: str             # active | superseded | voided
├── source_type: str
├── provenance: Mapping[str, Any] | None
├── employee_context_id: int | None   # audit only, non-FK
├── metadata: Mapping[str, Any] | None
├── created_at: datetime | None
└── updated_at: datetime | None       # optimistic token on supersede (interim)
```

### 9.2. Field mandatory matrix

| Field | `registration` | `not_applicable` | Notes |
|-------|----------------|------------------|-------|
| `person_id` | **Yes** | **Yes** | |
| `record_kind` | **Yes** | **Yes** | |
| `obligation_status` | Optional* | ❌ must be empty | *MIL-5 structured set |
| `registration_category` | Optional* | ❌ | |
| `military_rank` | Optional* | ❌ | |
| `registration_status` | Optional* | ❌ | |
| `military_specialty_code` | Optional | ❌ | |
| `personnel_composition` | Optional | ❌ | |
| `fitness_category` | Optional | ❌ | |
| `commissariat_name` | Optional | ❌ | |
| `registered_at` / `deregistered_at` | Optional | ❌ | |
| Document number fields | Optional | ❌ | **RESTRICTED**; §13.4 |
| `notes` | Optional | Optional | **Cannot satisfy MIL-5 alone** for `registration` |
| `verification_status` | **Yes** (default `pending`) | **Yes** | |
| `lifecycle_status` | **Yes** (default `active`) | **Yes** | |
| `source_type` | **Yes** (default `entered`) | **Yes** | |

**MIL-5 rule:** for `registration`, at least **one** of `obligation_status`, `registration_category`, `military_rank`, `registration_status` must be non-empty.

### 9.3. Enum sketches (Phase 1 — extensible, free text allowed)

**`obligation_status`:** `liable`, `not_liable`, `exempt`, `unknown`

**`registration_category`:** `I`, `II`, `III`, `IV`, `V`, `other`

**`registration_status`:** `registered`, `deregistered`, `reserved`, `deferment`, `unknown`

**`personnel_composition`:** `soldiers`, `sergeants`, `officers`, `other`

### 9.4. Table constraints (conceptual)

- Partial unique index: **one `active` row per `person_id`** (MIL-2).
- `not_applicable` rows: military attribute columns NULL (MIL-4).
- FK: only `person_id → persons`.
- No `draft` on row — PMF wizard draft stays on `migration_items`.

---

## 10. Lifecycle and Verification

### 10.1. Row lifecycle

| Status | Meaning |
|--------|---------|
| `active` | Current authoritative record (0..1 per person) |
| `superseded` | Replaced by newer row — **history** |
| `voided` | Annulled erroneous entry — **history** |

**Transitions:** `active` → `superseded` (Supersede); `active` → `voided` (Void). New content after void → `CreateMilitaryRegistration`.

**Forbidden:** in-place content update; resurrect voided/superseded rows.

### 10.2. Verification

`VerifyMilitaryRecord` / `UnverifyMilitaryRecord` — gated by **AUTH-2** (WP-PR-008).

### 10.3. Section lifecycle vs envelope

| Event | Behavior |
|-------|----------|
| Materialize PPR (CANDIDATE) | Rows may be created |
| Apply HIRE / Rehire / Termination | Rows **preserved** |
| Demographics change on Person | Applicability may be re-evaluated manually; data **not auto-voided** |

### 10.4. Mutation commands (closed set)

| Command | Purpose | Idempotency |
|---------|---------|-------------|
| `CreateMilitaryRegistration` | First active row (or after void) | `command_id` |
| `SupersedeMilitaryRegistration` | Replace active row (all content corrections) | New command each supersede |
| `VoidMilitaryRegistration` | Void active row | `command_id` |
| `VerifyMilitaryRecord` | Set verification_status | `command_id` |

**Guard:** `CreateMilitaryRegistration` **rejected** if active row exists → must **Supersede** or **Void** first.

**Explicitly absent:** `UpdateMilitaryRegistration` (D9).

---

## 11. Person and Employee Relationship

| Question | Answer |
|----------|--------|
| Who owns data? | **Person** (`person_id`) |
| CANDIDATE visibility? | **Yes** — same section as EMPLOYED |
| Does Hire copy rows? | **No** |
| Employee self-service read? | **No** — section omitted (closed) |
| Operational role `OR-HR-MGR-UHR-MIL` | Write via PPR command path after RBAC binding |

---

## 12. Change History

| Layer | Mechanism |
|-------|-----------|
| **Content history** | **Only** `superseded` / `voided` rows + `personnel_record_events` |
| **Audit journal** | Append-only `personnel_record_events` |
| **UI** | Collapsible superseded/voided buckets; aggregate «История изменений» tab |

---

## 13. Query API Requirements

### 13.1. Composite read extension (additive)

```json
{
  "sections": {
    "PPR-MILITARY": {
      "section_code": "PPR-MILITARY",
      "applicability": {
        "rule_code": null,
        "result": "UNKNOWN",
        "reason": null
      },
      "active": [],
      "superseded": [],
      "voided": []
    }
  }
}
```

**0..1 shape:** `active` has **0 or 1** element (server-enforced).

### 13.2. Response types — standard vs privileged (D8, redaction closed)

**Standard DTO** (`PprMilitaryRecordResponse`) — fields visible without elevated grant:

```python
class PprMilitaryRecordResponse(BaseModel):
    record_id: int | None = None
    record_kind: str
    record_kind_label: str | None = None
    obligation_status: str | None = None
    obligation_status_label: str | None = None
    registration_category: str | None = None
    military_rank: str | None = None
    military_specialty_code: str | None = None
    personnel_composition: str | None = None
    fitness_category: str | None = None
    registration_status: str | None = None
    registration_status_label: str | None = None
    commissariat_name: str | None = None
    registered_at: date | None = None
    deregistered_at: date | None = None
    notes: str | None = None
    verification_status: str
    lifecycle_status: str
    # RESTRICTED fields ABSENT from standard DTO
```

**Privileged DTO** (`PprMilitaryRecordDetailsResponse`) — only with grant **`VIEW_MILITARY_DETAILS`**:

```python
class PprMilitaryRecordDetailsResponse(PprMilitaryRecordResponse):
    military_id_book_series: str | None = None
    military_id_book_number: str | None = None
    registration_certificate_series: str | None = None
    registration_certificate_number: str | None = None
```

### 13.3. Redaction decision (closed)

| Caller | RESTRICTED fields (`military_id_book_*`, `registration_certificate_*`) |
|--------|--------------------------------------------------------------------------|
| **No grant** | **Absent** from composite payload (fields omitted, not `null`) |
| **Standard HR** (section visible) | **Absent** — standard DTO only |
| **`VIEW_MILITARY_DETAILS`** | Full privileged DTO; values **unmasked** |
| **Employee self** | Entire `PPR-MILITARY` section **omitted** |
| **Anonymous** | Section **omitted** |

**Implementation rule:** mapper selects DTO variant at read time; **no** masked placeholder strings in standard DTO (contrast: optional future `**####` only in privileged partial views — **not** Phase 1).

Non-document RESTRICTED policy (e.g. VUS visibility for standard HR) — see OQ-MIL-3.

### 13.4. Summary fields

```python
military_active_count: int = 0   # 0 or 1
military_section_present: bool = False
```

### 13.5. Breaking changes

**None.** Additive extension only.

---

## 14. Mutation API Requirements

### 14.1. Application Layer

- Writes through **`PprSectionApplicationService`**
- Materialized PPR envelope gate
- Atomic: section mutation + `personnel_record_events`
- Optimistic concurrency: `expected_updated_at` on **Supersede** / **Void** only

### 14.2. Idempotency

| Command | Idempotent retry |
|---------|------------------|
| `CreateMilitaryRegistration` | Yes |
| `VoidMilitaryRegistration` | Yes |
| `SupersedeMilitaryRegistration` | **No** |
| `VerifyMilitaryRecord` | Yes |

### 14.3. Authorization

- **AUTH-2** before handler
- `VIEW_MILITARY_DETAILS` — read-only elevated grant
- Align write with `OR-HR-MGR-UHR-MIL` (ADR-055) in WP-PR-029

---

## 15. UI Requirements (личная карточка)

### 15.1. Navigation

```text
{ id: "military", title: "Воинский учёт" }
```

Position: after «Родственники» (finalize in WP-PR-030).

### 15.2. `PprCardMilitarySection` (read-only Phase 1)

- `not_applicable` row → prominent badge «Не подлежит воинскому учёту»; no military attributes
- `registration` row → structured fields per standard DTO
- Document numbers → **not rendered** without `VIEW_MILITARY_DETAILS`
- Empty applicable → «Сведения о воинском учёте не внесены»
- CANDIDATE + EMPLOYED — **same section**
- superseded/voided — collapsible

### 15.3. Explicit non-goals UI

- Т-2 layout / print
- File upload / scan viewer
- Military office workflow

---

## 16. Demo Seed Requirements

### 16.1. Script

`scripts/ops/seed_demo_military_service.py` — PPR command path only; idempotent; `CORPSITE_ALLOW_DEMO_PPR_SEED=1` for execute.

### 16.2. Demo personas

| Demo key | Seed intent |
|----------|-------------|
| `ahmetov` | `registration` — obligation + category + rank + status |
| `seitova` | `not_applicable` — explicit HR attestation in `notes` |

### 16.3. Example (`ahmetov`)

```python
{
    "demo_record_key": "ahmetov:military:registration-v1",
    "record_kind": "registration",
    "obligation_status": "liable",
    "registration_category": "II",
    "military_rank": "рядовой",
    "registration_status": "registered",
    "military_specialty_code": "123456",
    "commissariat_name": "Районный военкомат г. Алматы",
    "registered_at": date(2008, 6, 15),
}
```

---

## 17. Migration Strategy

Greenfield — no import column, no PMF plugin Phase 1.

DDL in **WP-PR-027**. Read-switch after **WP-PR-029**.

---

## 18. Architecture Guards

| Guard ID | Assertion |
|----------|-----------|
| **AG-MIL-1** | FK references **only** `persons` |
| **AG-MIL-2** | `employee_context_id` is **not** FK |
| **AG-MIL-3** | No writes from employment/order services |
| **AG-MIL-4** | `SUPPORTED_SECTION_CODES` inclusion tested |
| **AG-MIL-5** | Composite read ≤1 active record |
| **AG-MIL-6** | Hire E2E: row count unchanged |
| **AG-MIL-7** | `not_applicable` rejects populated military attributes |
| **AG-MIL-8** | MIL-5: `registration` without structured field fails validation |
| **AG-MIL-9** | Standard DTO omits RESTRICTED fields without `VIEW_MILITARY_DETAILS` |
| **AG-MIL-10** | No `UpdateMilitaryRegistration` command handler registered |

---

## 19. Implementation Roadmap

Military track **WP-PR-026…031**. Employment Biography remains **WP-PR-013…025** per [ADR-056](../adr/ADR-056-employment-biography-in-ppr.md).

| Phase | ID | Goal | Delivers | Depends on |
|-------|-----|------|----------|------------|
| 0 | **WP-PR-026** | **ADR / design** | This document (accepted) | R0–R7; PPR-FAMILY pattern |
| 1 | **WP-PR-027** | Schema + domain | Migration `person_military_service`; enums; `MilitaryServiceRecord`; MIL-5/MIL-4 validation; AG-MIL-1/2/7/8 | WP-PR-026 |
| 2 | **WP-PR-028** | Section Repository | `SectionRepository` load/write; contract tests | WP-PR-027 |
| 3 | **WP-PR-029** | Application + Query API | Commands (no Update); events; `load_military()`; DTO redaction; summary fields; AG-MIL-9/10 | WP-PR-028, R5–R7 |
| 4 | **WP-PR-030** | UI | `PprCardMilitarySection`; nav; applicability/empty states | WP-PR-029 |
| 5 | **WP-PR-031** | Demo seed + guards | `seed_demo_military_service.py`; AG-MIL-3…6; ops tests | WP-PR-029 |

**Deferred post-031:** completeness engine rules (R8); automatic applicability; `person_documents` evidence; Т-2 extension ADR.

---

## 20. Consequences

### Positive

- GAP §15 closed with clear person-owned SoT.
- No numbering collision with Employment Biography WP-PR-013…025.
- Supersede-only corrections — strong audit trail.
- Redaction model explicit before implementation.

### Negative / costs

- Every field change creates superseded row (0..1 sections).
- `UNKNOWN` applicability — no automated completeness blocking Phase 1.
- Two DTO variants increase mapper complexity.

### Risks

| Risk | Mitigation |
|------|------------|
| HR путает §15 и Т-2 | MIL-BOUNDARY; UI labels |
| Supersede-only UX friction | Acceptable for RESTRICTED cadre data |
| Document numbers in standard API leak | AG-MIL-9; absent-from-DTO policy |

---

## 21. Open Questions

| ID | Question | Status |
|----|----------|--------|
| ~~OQ-MIL-1~~ | Legal auto-applicability rules | **Closed** — not Phase 1; default `UNKNOWN` (D6) |
| ~~OQ-MIL-2~~ | Mandatory structured fields for `registration` | **Closed** — MIL-5 |
| ~~OQ-MIL-4~~ | Redaction matrix | **Closed** — §13.3; `VIEW_MILITARY_DETAILS` |
| ~~OQ-MIL-5~~ | Update vs Supersede | **Closed** — no Update command (D9) |
| ~~OQ-MIL-6~~ | Employee self-service read | **Closed** — section omitted |
| ~~OQ-MIL-7~~ | File documents / `person_documents` | **Closed** — out of Phase 1 (D10) |
| ~~OQ-MIL-8~~ | Т-2 digitization relation | **Closed** — separate ADR; §15 slice remains |
| **OQ-MIL-3** | National enum catalog for ranks / VUS | **Open** — free text Phase 1; enum Phase 2+ |
| **OQ-MIL-9** | Nav position in card (after family vs after training) | **Open** — default after «Родственники» |
| **OQ-MIL-10** | Completeness mandatory policy when applicability known | **Open** — deferred post WP-PR-031 / R8 |
| **OQ-MIL-11** | Whether standard HR sees `military_specialty_code` (VUS) or it moves to privileged DTO | **Open** — default: visible in standard DTO |

---

## 22. Compliance Checklist

- [x] Согласовано с WP-PR-002 aggregate boundaries
- [x] Согласовано с WP-PR-003 catalog (`PPR-MILITARY`, 0..1, CONDITIONAL, RESTRICTED)
- [x] Не меняет ADR-054-NOTE / Hire flow
- [x] Explicit non-overlap с PPR-FAMILY, ADR-056, Employment BC
- [x] Т-2 boundary documented (MIL-BOUNDARY)
- [x] `record_kind` decision closed (D4)
- [x] Roadmap WP-PR-026…031 — no collision with ADR-056
- [x] Architecture guards defined (§18)
- [ ] EPIC-4 entry в ARCH-002-IMPLEMENTATION-ROADMAP (при старте WP-PR-027)

---

## Appendix C — Implementation boundary statement

**Подтверждение:** rev. 0.2 — **только** документация; код, DDL, миграции, API, UI **не изменялись**.

---

## Revision history

| Rev | Date | Changes |
|-----|------|---------|
| 0.1 | 2026-07-16 | Initial proposed ADR |
| 0.2 | 2026-07-16 | Final review: WP-PR-026…031 roadmap; closed decisions D1–D11; MIL-5 strengthened; redaction §13.3; no Update command; `record_kind` lowercase; open questions triaged |

---

*End of WP-PR-026*
