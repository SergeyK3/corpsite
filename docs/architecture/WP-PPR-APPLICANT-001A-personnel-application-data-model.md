--------------------------------------------------

Document Status

Document:
WP-PPR-APPLICANT-001A-personnel-application-data-model

Title:
Personnel Application — Data Model & Lifecycle (Phase A)

Type:
Architecture Work Package — Data Model & ADR Foundation

Status:
Draft — Ready for Review

Revision:
3

Date:
2026-07-17

Parent:
WP-PPR-APPLICANT-001 — Регистрация претендента кадровиком

Program:
ARCH-002 / PIF (Personnel Intake Framework)

Depends on:
ADR-054, ADR-054-NOTE, ADR-048, ADR-057, PIF-001, PIF-004, WP-UI-PPR-CANDIDATE-v1

Companion ADR:
ADR-057 — Personnel Application Aggregate (**Accepted**)

Purpose:
Normative data model, lifecycle, invariants, and migration foundation for **кадровое обращение**
(personnel application episode). **No code, migrations, API, or UI in this WP.**

Follow-on:
WP-PPR-APPLICANT-001B (service + API), WP-PPR-APPLICANT-001C (UI),
WP-PPR-INTAKE-001 (protected link + staging), WP-PPR-APPLICANT-002 (review + director gate)

--------------------------------------------------

# WP-PPR-APPLICANT-001A — Personnel Application Data Model

**Date:** 2026-07-17 (rev. 3)

---

## Revision History

| Rev | Date | Summary |
|-----|------|---------|
| 1 | 2026-07-17 | Initial architecture: `personnel_applications`, lifecycle, migration proposal |
| 2 | 2026-07-17 | Finalization: multi-aggregate model (ADR-057), Compatibility Bridge, domain predicates, roster rules, DATE type, order linkage, IIN policy, retention scope |
| 3 | 2026-07-17 | Compatibility Bridge: clear envelope when no active application; Order cardinality 0..1 ↔ 0..1 |

---

## 0. Delta from prior audit (2026-07-17)

| Element | Prior audit (rev. 0) | **Rev. 2 (finalized)** |
|---------|----------------------|------------------------|
| Episode storage | Envelope columns | **`personnel_applications` — SoT** ([ADR-057](../adr/ADR-057-personnel-application-aggregate.md)) |
| Intended employment | Envelope primary | **Application SoT**; envelope `intended_*` = **Compatibility Bridge projection** (incl. rehire) |
| Aggregate model | Implicit | **Explicit:** Person / PPR / Application / Order / Employee |
| Active invariant | Partial index only | **`is_active()` / `is_terminal()`** + index + Architecture Guard |
| Roster | `CANDIDATE` context | **Target:** active application; **Transition:** CANDIDATE OR active application |
| Former employee | Deferred | **Ratified:** new application; **no** auto `CANDIDATE` switch |
| `application_received_at` | TIMESTAMPTZ | **`DATE`** |
| Order linkage | Nullable FK only | **Nullable FK + UNIQUE + HIRE type check** in service |
| IIN | TBD checksum | **Production util**; 12 digits Phase 1; checksum after legacy audit |
| Intake retention | Mixed with application | **Out of aggregate** — INTAKE-001 |

---

## 1. Purpose & scope

### 1.1 Problem

Нет production aggregate **кадрового обращения** — точки входа кадровика после бумажного заявления.

### 1.2 Goal (001A)

Зафиксировать data model, lifecycle, invariants, migration proposal и ratify [ADR-057](../adr/ADR-057-personnel-application-aggregate.md).

### 1.3 What this WP IS / IS NOT

| Is | Is Not |
|----|--------|
| Data model + lifecycle + invariants | Implementation |
| ADR-057 (Accepted) | Alembic / API / UI |
| Compatibility Bridge spec | READY_FOR_SIGNATURE gate (APPLICANT-002) |
| Retention boundary definition | Intake staging tables |

---

## 2. Domain glossary

| Term (RU) | English | Aggregate / SoT |
|-----------|---------|-----------------|
| Person | Identity | `persons` |
| PPR | Personnel Personal Record | Person-owned sections + envelope metadata |
| Кадровое обращение | Personnel Application | **`personnel_applications`** |
| Personnel Order | Legal order document | `personnel_orders` (separate BC) |
| Employee | Operational employment | `employees` — **only after Apply** |

---

## 3. Multi-aggregate model (ADR-057)

### 3.1 Aggregate responsibilities

```text
┌─────────────────┐     identity SoT      ┌─────────────────┐
│     Person      │◄──────────────────────│  merge / IIN    │
└────────┬────────┘                       └─────────────────┘
         │ 1 : 0..1 → 1
         ▼
┌─────────────────┐     cadre dossier SoT   ┌─────────────────┐
│      PPR        │◄──────────────────────│ person_* sections│
│   (envelope)    │                       │ events, lifecycle│
└────────┬────────┘                       └─────────────────┘
         │ 1 : 0..N
         ▼
┌─────────────────┐     episode SoT         ┌─────────────────┐
│   Personnel     │◄──────────────────────│ intended placement│
│   Application   │                       │ contacts, vacancy │
└────────┬────────┘                       │ resolution, audit │
         │ 0..1 link                      └─────────────────┘
         ▼
┌─────────────────┐     order SoT           ┌─────────────────┐
│   Personnel     │◄──────────────────────│ DRAFT…REGISTERED│
│     Order       │                       │ Apply → Employee│
└─────────────────┘                       └─────────────────┘
```

| Aggregate | Creates Employee? | Owns intended placement (episode)? |
|-----------|-------------------|-------------------------------------|
| Person | No | No |
| PPR | No | No (owns cadre sections only) |
| Personnel Application | No | **Yes** |
| Personnel Order | **Yes (via Apply only)** | No (uses order item payload at Apply) |
| Employee | — | No |

### 3.2 Cardinality

| Relationship | Cardinality | Rule |
|--------------|-------------|------|
| Person → PPR envelope | 1 : 0..1 → 1 | Second PPR **forbidden** |
| Person → Application | 1 : 0..N | Full history preserved |
| Person → **Active** Application | 1 : 0..1 | Phase 1 invariant (§6) |
| Application ↔ Order | **0..1 ↔ 0..1** | Nullable FK; UNIQUE when set; link optional both sides (§15) |
| Application → Employee | — | **No direct FK** |
| Application → Intake (future) | 1 : 0..N | **Separate aggregate** — INTAKE-001 |

### 3.3 ER diagram

```mermaid
erDiagram
    persons ||--o| personnel_record_metadata : "PPR envelope"
    persons ||--o{ personnel_applications : "episodes"
    personnel_applications |o--o| personnel_orders : "nullable unique FK"
    persons ||--o{ employees : "after Apply"
    personnel_applications {
        bigint application_id PK
        bigint person_id FK
        text status
        date application_received_at
        bigint intended_org_unit_id FK
        bigint personnel_order_id FK UK
    }
```

---

## 4. Table naming

**Accepted:** `public.personnel_applications`

Rejected: `hr_applications`, `person_applications`

Future nullable column: `vacancy_id BIGINT NULL` (Vacancy registry — later WP).

---

## 5. Schema — `personnel_applications`

### 5.1 Columns

| Column | Type | Null | Description |
|--------|------|------|-------------|
| `application_id` | BIGINT IDENTITY | NO | PK |
| `person_id` | BIGINT FK → `persons` | NO | Canonical person (post merge) |
| `status` | TEXT | NO | Lifecycle (§7) |
| `application_received_at` | **DATE** | NO | Calendar date paper application received |
| `application_source` | TEXT | NO | Phase 1: `'paper'` |
| `vacancy_check_status` | TEXT | NO | §10 |
| `vacancy_checked_at` | TIMESTAMPTZ | YES | |
| `vacancy_checked_by_user_id` | BIGINT FK → `users` | YES | |
| `intended_org_group_id` | BIGINT FK | YES | **SoT** — episode placement |
| `intended_org_unit_id` | BIGINT FK | YES | **SoT** |
| `intended_position_id` | BIGINT FK | YES | **SoT** |
| `intended_employment_rate` | NUMERIC(4,2) | YES | **SoT** |
| `intended_vacancy_text` | TEXT | YES | **SoT** — free text |
| `contact_mobile_phone` | TEXT | YES | Episode contact (not Person SoT) |
| `contact_email` | TEXT | YES | Episode contact (not Person SoT) |
| `director_resolution_status` | TEXT | YES | pending / approved / rejected |
| `director_resolution_at` | TIMESTAMPTZ | YES | |
| `director_resolution_by_user_id` | BIGINT FK | YES | |
| `director_resolution_note` | TEXT | YES | |
| `personnel_order_id` | BIGINT FK → `personnel_orders` | YES | §15 — nullable, unique |
| `registered_at` | TIMESTAMPTZ | NO | Server event time |
| `registered_by_user_id` | BIGINT FK → `users` | NO | |
| `hr_note` | TEXT | YES | |
| `idempotency_key` | TEXT | YES | |
| `created_at` | TIMESTAMPTZ | NO | |
| `updated_at` | TIMESTAMPTZ | NO | |

**Type rule (ADR-057 D10):** only `application_received_at` is **DATE**; all other business event timestamps are **TIMESTAMPTZ**.

### 5.2 CHECK constraints (sketch)

```sql
CHECK (status IN (...))  -- must match TERMINAL_APPLICATION_STATUSES complement
CHECK (application_source IN ('paper'))  -- extensible later
CHECK (vacancy_check_status IN ('pending', 'confirmed_visually', 'not_confirmed'))
CHECK (director_resolution_status IS NULL OR director_resolution_status IN ('pending', 'approved', 'rejected'))
```

Registration requires `vacancy_check_status = 'confirmed_visually'`.

### 5.3 Indexes

| Index | Purpose |
|-------|---------|
| `ix_personnel_applications_person_id_created_at DESC` | History on card |
| `ix_personnel_applications_status` | Ops queries |
| `uq_personnel_applications_idempotency_key` WHERE `idempotency_key IS NOT NULL` | Retry safety |
| `uq_personnel_applications_personnel_order_id` WHERE `personnel_order_id IS NOT NULL` | One order → one application (§15) |
| `uq_personnel_applications_one_active_per_person` | §6 — synced with domain predicates |

```sql
CREATE UNIQUE INDEX uq_personnel_applications_one_active_per_person
    ON public.personnel_applications (person_id)
    WHERE status NOT IN (
        'completed', 'withdrawn', 'cancelled', 'resolution_rejected'
    );
```

### 5.4 Deletion policy

Hard delete forbidden in production. `ON DELETE RESTRICT` on `person_id`, `personnel_order_id`.

---

## 6. Active application — domain predicates & invariant

### 6.1 Terminal status set (canonical)

```python
TERMINAL_APPLICATION_STATUSES: frozenset[str] = frozenset({
    "completed",
    "withdrawn",
    "cancelled",
    "resolution_rejected",
})

def is_terminal_application_status(status: str) -> bool:
    return status in TERMINAL_APPLICATION_STATUSES

def is_active_application_status(status: str) -> bool:
    return not is_terminal_application_status(status)
```

**Non-terminal (active) examples:** `registered`, `intake_pending`, `intake_submitted`, `under_review`, `awaiting_director_resolution`, `resolution_approved`.

### 6.2 Phase 1 invariant

> **At most one row per `person_id` where `is_active_application_status(status)`.**

### 6.3 Enforcement layers (must stay synchronized)

| Layer | Mechanism |
|-------|-----------|
| Database | Partial unique index (§5.3) — **same four terminal values** |
| Service | Guard before INSERT; duplicate → `opened_existing` |
| Architecture Guard | Test asserts `TERMINAL_APPLICATION_STATUSES` == index predicate set |

Location (001B): `app/personnel_applications/domain/status.py` + `tests/architecture/test_personnel_application_invariants.py`.

---

## 7. Application lifecycle

### 7.1 Status catalogue

| Status | Terminal? | WP |
|--------|-----------|-----|
| `registered` | No | 001B/C |
| `intake_pending` | No | INTAKE-001 |
| `intake_submitted` | No | INTAKE-001 |
| `under_review` | No | APPLICANT-002 |
| `awaiting_director_resolution` | No | APPLICANT-002 |
| `resolution_approved` | No | APPLICANT-002 |
| `resolution_rejected` | **Yes** | APPLICANT-002 |
| `completed` | **Yes** | After Apply |
| `withdrawn` | **Yes** | |
| `cancelled` | **Yes** | |

Personnel Order statuses (`DRAFT`, `READY_FOR_SIGNATURE`, …) **are not copied** into application status.

### 7.2 State machine

See rev. 1 diagram — unchanged structurally. `resolution_approved` remains active until `completed` (Apply done).

---

## 8. Intended employment — Source of Truth

### 8.1 Normative rule (ADR-057 D2, D3)

| Concern | Source of Truth |
|---------|-----------------|
| Episode placement (group, unit, position, rate, vacancy text) | **`personnel_applications`** |
| Hire order draft prefill (target) | **Active Personnel Application** |
| Composite read «Предполагаемое трудоустройство» (target) | **Active application** slice |
| Post-Apply operational placement | **`employees`** / assignments — unchanged (ADR-054-NOTE) |

**`personnel_record_metadata.intended_*` is NOT Source of Truth** for new flows.

### 8.2 Write path (001B)

1. Registration / update → write **`personnel_applications`** intended fields.
2. Trigger Compatibility Bridge projection → envelope (§9).
3. Do **not** accept direct PATCH to envelope `intended_*` as authoritative for new code paths (legacy endpoints may delegate to active application during transition).

### 8.3 Rehire

Former employee with new application: intended placement SoT is the **new application row**. Compatibility Bridge still projects to envelope so legacy `hire-defaults` consumers keep working **without** requiring `CANDIDATE` context switch.

---

## 9. Compatibility Bridge (envelope `intended_*` projection)

Temporary transition mechanism — **not an aggregate**.

### 9.1 Purpose

Existing code paths read envelope `intended_org_group_id`, `intended_org_unit_id`, `intended_position_id`, `intended_employment_rate`:

- `GET /api/ppr/persons/{id}/hire-defaults`
- `PATCH /api/ppr/persons/{id}/intended-employment`
- `PprCompositeReadOrchestrator` intended slice fallback

### 9.2 Projection rules

**Principle:** Compatibility Bridge reflects **only the current active** Personnel Application.
Envelope `intended_*` **must not** retain stale values. Historical intended placement lives
**exclusively** in `personnel_applications` (terminal and active rows).

| Event | Action |
|-------|--------|
| Application registered / active application intended fields updated | Mirror **that** active application → envelope `intended_*` |
| Active application becomes terminal | Recompute projection (see next row) |
| Another active application exists for same Person | Switch projection to the **remaining** active application |
| **No active application** for Person | **Clear** envelope `intended_*` (set all four columns to `NULL`) |
| Read historical intended placement | Query `personnel_applications` history — **not** envelope |

**Scope:** when an active application exists, projection runs for **any** `hr_relationship_context`, including **`FORMER_EMPLOYEE`**.

**Implementation note (001B):** `sync_envelope_intended_projection(person_id)` invoked after every application
status transition and intended-field update; idempotent; clear-on-no-active is mandatory.

### 9.3 Prohibited

- Adding registration metadata to envelope
- Treating envelope as SoT for new registrations
- Storing episode `contact_email` on envelope
- **Retaining stale `intended_*` on envelope** after terminal transition or when no active application exists

### 9.4 Retirement

After 001C: migrate hire-defaults and composite read to active application; mark envelope fields deprecated; remove dual-write in cleanup WP.

---

## 10. Vacancy visual check

Unchanged from rev. 1. Registration requires `vacancy_check_status = confirmed_visually`.

---

## 11. Former employee semantics (ratified)

| Rule | Detail |
|------|--------|
| Person | **Reuse** |
| PPR envelope | **Reuse** — no second materialize |
| Personnel Application | **Create new row** |
| `hr_relationship_context` | **Do not** auto-switch `FORMER_EMPLOYEE` → `CANDIDATE` |
| Compatibility Bridge | **Still projects** intended_* from new active application |
| Employee | Created only via Apply (unchanged) |
| HIRE-from-person (current code) | Requires `CANDIDATE` — **blocked for FORMER_EMPLOYEE** until APPLICANT-002 / rehire WP |

---

## 12. Person & PPR registration

| Case | Actions |
|------|---------|
| New IIN | INSERT Person → MaterializePPR(`CANDIDATE`) → INSERT application |
| Existing Person (incl. former) | Reuse Person → ensure envelope exists → INSERT application (**no** context auto-switch) |
| Never | Create Employee, order, or hire events |

---

## 13. Episode contacts

`contact_mobile_phone`, `contact_email` on application only. Promotion to canonical contact model → PIF-004 / APPLICANT-002.

---

## 14. IIN validation (ADR-057 D9)

| Rule | Detail |
|------|--------|
| Module location | **`app/domain/iin.py`** (or `app/personnel_applications/domain/iin.py`) — production utility |
| Do not import from | `scripts/import_hr_control_list.py` |
| Phase 1 (001B) | Normalize to 12 decimal digits; reject empty/short/long |
| Checksum | **Deferred** — adopt only after legacy IIN data audit |
| Tests | Unit tests on production module; registration service uses same entry point |

---

## 15. Linkage with Personnel Order

### 15.1 Schema — cardinality **0..1 ↔ 0..1**

| Side | Cardinality | Mechanism |
|------|-------------|-----------|
| Application → Order | **0..1** | `personnel_order_id BIGINT NULL` — application may have no linked order |
| Order → Application | **0..1** | `UNIQUE INDEX` on `personnel_order_id` WHERE NOT NULL — order may be unlinked |

- `personnel_applications.personnel_order_id BIGINT NULL REFERENCES personnel_orders(order_id)`
- **`UNIQUE INDEX`** `uq_personnel_applications_personnel_order_id` WHERE `personnel_order_id IS NOT NULL`
- Optional link both ways: draft order may exist before bind; application may never receive an order (terminal withdrawal/rejection)

### 15.2 Service-layer rules (001B)

Before binding `personnel_order_id`:

1. Order exists and belongs to same org context (existing PO guards).
2. **`order_type` / item type is HIRE** (reject TRANSFER, TERMINATION, …).
3. Order not already linked to another application.
4. Application is active (or policy allows link only from `under_review` onward — APPLICANT-002 may tighten).

Binding may occur when HR creates draft from card or explicitly associates existing draft.

### 15.3 Process reference

```text
Register → intake/PPR → HR review → DRAFT HIRE (+ bind order_id)
  → director resolution → resolution_approved
  → READY_FOR_SIGNATURE (gate — APPLICANT-002, NOT this WP)
  → Sign → Register → Apply → completed + Employee
```

**001A/B/C do not modify** `POST .../ready-for-signature` behaviour.

Negative resolution: `resolution_rejected` (terminal); Person/PPR preserved; order voided separately if needed.

---

## 16. Retention policy

### 16.1 In scope — Personnel Application aggregate

| Data | Retention |
|------|-----------|
| **`personnel_applications` rows** | **Permanent** — full episode history including terminal states |
| Audit fields (`registered_at`, `registered_by`, resolution fields) | Permanent (part of row) |

### 16.2 Out of scope — WP-PPR-INTAKE-001 (not part of this aggregate)

| Data | Policy |
|------|--------|
| Intake auto-save draft payload | TTL delete |
| Submitted intake payload | Until review complete + grace period |
| One-time tokens | Short TTL; delete on use/expiry |
| Post-Apply intake payload | Minimize/delete; retain audit facts only |

Re-application after long interval: **new application row** + new intake link; PPR prefill from **current PPR read**, not old intake payload.

---

## 17. Applicant roster rules

### 17.1 Target (long-term)

```text
include_applicants = Person has ≥1 active Personnel Application
                   AND no active Employee
```

Roster **does not depend** on `hr_relationship_context = CANDIDATE` alone.

### 17.2 Transition mode (001B–C)

```text
include_applicants = (
    Person has active Personnel Application
    OR (
        hr_relationship_context = 'CANDIDATE'
        AND no active Employee
        AND no personnel_applications row yet   -- legacy/demo rows
    )
)
```

Remove transition OR-branch after demo backfill / feature flag sunset.

Implementation touchpoint: `list_ppr_applicants()` → evolve to `list_personnel_applicant_roster()`.

---

## 18. Duplicate resolution

Algorithm unchanged (rev. 1) with IIN via production util (§14) and active-application check via `is_active_application_status()`.

---

## 19. Migration proposal (Alembic in 001B)

1. `CREATE TABLE personnel_applications` — §5
2. Indexes including partial unique + order unique — §5.3
3. **No** envelope schema changes
4. **No** intake tables

---

## 20. Repository & API boundaries (001B preview)

| Component | Path (suggested) |
|-----------|------------------|
| Domain status + IIN | `app/personnel_applications/domain/` |
| Repository | `app/personnel_applications/infrastructure/repository.py` |
| Registration service | `app/personnel_applications/application/registration_service.py` |
| Compatibility Bridge | `app/personnel_applications/application/envelope_projection.py` |
| Routes | `app/directory/personnel_applications_routes.py` |

API paths: `/directory/personnel-applications/*`, `/api/ppr/persons/{person_id}/applications`.

---

## 21. UI contract (001C preview)

Unchanged from rev. 1 — register drawer + «Кадровое обращение» panel + history list.

---

## 22. WP breakdown

```text
001A (this doc + ADR-057) ──► 001B (DDL, service, API, tests)
                           ──► 001C (UI)
                           ──► INTAKE-001 (link, staging, retention)
                           ──► APPLICANT-002 (review, resolution, order gate)
```

---

## 23. Open questions (unresolved only)

| ID | Question | Owner |
|----|----------|-------|
| OQ-1 | Exact moment `registered` → `intake_pending` (auto on link issue vs manual HR action) | INTAKE-001 |
| OQ-2 | Whether registration form may update `persons.full_name` on Person reuse without explicit HR confirm | APPLICANT-002 |
| OQ-3 | Sunset date / feature flag for roster transition OR-branch | 001C ops |

**Closed in rev. 2:** aggregate boundaries, SoT, Compatibility Bridge, former employee, invariants, roster target, DATE type, order linkage shape, retention scope, IIN Phase 1 policy, checksum deferral.

---

## 24. Test matrix (001B/C)

Add to rev. 1 matrix:

- Architecture guard: terminal set == partial index predicate
- Compatibility Bridge: project on register; switch on new active; **clear envelope** when no active application
- Order linkage UNIQUE + HIRE type rejection
- Roster transition OR logic
- `application_received_at` DATE persistence

---

## 25. References

- [ADR-057](../adr/ADR-057-personnel-application-aggregate.md) — **Accepted**
- [ADR-054](../adr/ADR-054-personnel-personal-record-aggregate-model.md)
- [ADR-054-NOTE](../adr/ADR-054-NOTE-intended-employment-lifecycle.md)
- [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md)
- [PIF-001](../personnel-intake/PIF-001-personnel-intake-framework.md)
- [WP-UI-PPR-CANDIDATE-v1](../../docs-work/WP-UI-PPR-CANDIDATE-v1-pre-commit-report.md)

---

**End of WP-PPR-APPLICANT-001A (rev. 3)**
