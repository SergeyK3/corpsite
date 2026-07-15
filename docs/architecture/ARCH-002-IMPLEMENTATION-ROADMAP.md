--------------------------------------------------

Document Status

Document:
ARCH-002-IMPLEMENTATION-ROADMAP

Title:
Personnel Personal Record — Implementation Roadmap

Type:
Master Implementation Plan

Status:
Draft — Ready for Review

Revision:
1

Parent:
ARCH-002 — Personnel Personal Record Architecture

Purpose:
Defines the safe, phased implementation plan for ARCH-002 without
prescribing implementation details.

--------------------------------------------------

# ARCH-002 Implementation Roadmap

**Date:** 2026-07-15

---

## 1. Purpose

Настоящий документ — **мастер-план внедрения** [ARCH-002](./ARCH-002-personnel-personal-record-architecture.md)
(Personnel Personal Record Architecture) в существующую систему Corpsite.

Документ описывает:

- архитектурные эпики и work packages;
- зависимости и порядок внедрения;
- стратегии migration и compatibility;
- риски, decision gates и критерии завершения.

Документ **не** описывает детали реализации (схемы таблиц, API contracts,
UI mockups, код). Эти артеfacts создаются в последующих ADR и work
packages.

---

## 2. Scope

### In scope

- Поэтапный переход от **Transitional Architecture** к **Target
  Architecture** ARCH-002.
- Сохранение работоспособности import pipeline, PMF pilot, Personnel
  Orders, Employee Card / HR Dossier на всём пути.
- Закрытие Open Architectural Decisions (OAD) ARCH-002 через decision
  gates.
- Data migration и legacy removal **как отдельные поздние эпики**.

### Out of scope

- Изменение нормативных положений ARCH-002.
- Position Cabinet, operational tasks, access control domain (кроме
  read-only отображения в Employee Card).
- Внешние HRIS / EDS integration.
- Календарное планирование (сроки, спринты).

---

## 3. Current Architecture

Краткая ссылочная сводка (детали — ARCH-002 «Repository Findings»,
«Current Transitional Architecture»).

``` text
Import (Control Output Excel as INPUT)
  → JSON staging (hr_import_*)
  → Import Profile (employee/batch scoped)
  → Employee overrides
  → PMF (pilot: education → person-owned sections)
  → Employee Card / HR Dossier (Composite View, partial sections)
  → Personnel Orders (HIRE requires Employee)
  → Reports (canonical Excel, order PDF)
```

**Ключевые traits:** import-first; employee-centric staging; PMF as bridge;
нет единого Personnel Personal Record aggregate; Control Output — input,
не derived export.

---

## 4. Target Architecture

Краткая ссылочная сводка (детали — ARCH-002 normative sections).

``` text
Person
  → Personnel Personal Record (typed sections, lifecycle)
      → Employment Relationship
          → Personnel Orders, Employee events, Assignments
Employee Card / HR Dossier = Composite View (NOT source of truth)
Control Output = DERIVED from Personnel Personal Record + Employment
Import / Import Profile = bootstrap & reconciliation (NOT SoT)
PMF = controlled migration into Personnel Personal Record sections
```

**Инварианты:** INV-1 … INV-9 (ARCH-002). **Variant C rejected** as target.

---

## 5. Transitional Architecture

На период внедрения сохраняется **dual-path**:

| Layer | Transitional (retained) | Target (introduced incrementally) |
|-------|----------------------|-----------------------------------|
| Data ingress | Import Profile, JSON staging | Person-scoped Personnel Personal Record sections |
| Migration | PMF commit (existing) | PMF → expanded domains → aggregate boundary |
| Employment | HIRE on Employee; enroll-from-import | HIRE from Person / Personnel Personal Record |
| UI | HR Dossier operational sections | Personnel Personal Record sections in Composite View |
| Export | Canonical roster Excel (input + export) | Control Output derived from Personnel Personal Record |

Transitional Architecture **не заменяется Big Bang** — каждый эпик
добавляет target path параллельно legacy path до read-switch / cutover.

---

## 6. Architecture Epics

### EPIC-1 — Personnel Personal Record Foundation

| Field | Content |
|-------|---------|
| **Цель** | Установить предметную и техническую границу aggregate Personnel Personal Record и закрыть OAD-1. |
| **Почему нужен** | Без foundation все последующие эпики строятся на Import Profile или Employee — нарушение ARCH-002. |
| **Что изменяет** | Domain model, aggregate boundary, section catalog, Person linkage, logical APIs. |
| **Что НЕ изменяет** | Import pipeline, Personnel Orders apply semantics, Employee Card layout (пока). |
| **Компоненты** | `app/` domain services; `docs/architecture/`; `alembic/` (поздние WP); Person / person_* layer. |
| **Зависимости** | ARCH-002 approved; OAD-1 decision (Decision Gate DG-1). |
| **Риски** | Over-engineering aggregate; Person ↔ Personnel Personal Record duplication. |
| **Критерии завершения** | Aggregate boundary documented; Variant A or B selected; section catalog approved; read model defined; no breaking change to existing flows. |

### EPIC-2 — Candidate Lifecycle

| Field | Content |
|-------|---------|
| **Цель** | Ввести Candidate как состояние Person / Personnel Personal Record до Employment Relationship; закрыть OAD-2. |
| **Почему нужен** | ARCH-002 требует Personnel Personal Record до найма; currently absent. |
| **Что изменяет** | Lifecycle states, intake boundary, Candidate search/selection. |
| **Что НЕ изменяет** | Existing Employee enrollment from import (until EPIC-5 convergence). |
| **Компоненты** | Personnel intake contour; Person services; HR processes UI (future). |
| **Зависимости** | EPIC-1 (Foundation); DG-2. |
| **Риски** | Parallel Candidate vs import-enroll paths; business process mismatch. |
| **Критерии завершения** | Candidate creatable with Personnel Personal Record without Employee; lifecycle states queryable; documented coexistence with import enroll. |

### EPIC-3 — Electronic Personnel Personal Record

| Field | Content |
|-------|---------|
| **Цель** | Предоставить Person-scoped electronic form для разделов Personnel Personal Record (OAD-8 phased). |
| **Почему нужен** | Import Profile UI — employee/batch scoped; не target aggregate editor. |
| **Что изменяет** | Personnel Personal Record UI shell, section editors, completeness/review status per section. |
| **Что НЕ изменяет** | Import Profile modal (legacy) until EPIC-9. |
| **Компоненты** | `corpsite-ui/` personnel contour; Personnel Personal Record API layer. |
| **Зависимости** | EPIC-1; EPIC-4 partial (sections with PMF backing); DG-3 (Phase 1 sections). |
| **Риски** | Duplicate UI (Import Profile vs Personnel Personal Record editors). |
| **Критерии завершения** | Phase 1 sections editable Person-scoped; completeness model operational; no Employee prerequisite for Candidate sections. |

### EPIC-4 — PMF Integration

| Field | Content |
|-------|---------|
| **Цель** | Расширить PMF как primary controlled write path в Personnel Personal Record sections; закрыть OAD-3 incrementally. |
| **Почему нужен** | PMF already Person-centric (audit); единственный proven migration engine. |
| **Что изменяет** | PMF domains, target section mapping, commit semantics, personnel_record_events coverage. |
| **Что НЕ изменяет** | PMF pilot education rollback; import staging tables. |
| **Компоненты** | `app/services/personnel_migration*`; `app/api/personnel_migration_router`; PMF UI wizard. |
| **Зависимости** | EPIC-1 (section catalog); can parallel EPIC-3 after Foundation. |
| **Риски** | Domain sprawl; commit failures blocking HR operations. |
| **Kритерии завершения** | Agreed domains committed to person-owned tables; Import Profile → PMF bridge documented; events emitted per section change. |

### EPIC-5 — Personnel Orders Integration

| Field | Content |
|-------|---------|
| **Цель** | HIRE и related flows select Person / Personnel Personal Record Candidate; закрыть OAD-5, OAD-6. |
| **Почему нужен** | Currently HIRE requires Employee — blocks target lifecycle. |
| **Что изменяет** | Order item model (selection), apply semantics, enroll path convergence. |
| **Что НЕ изменеет** | TRANSFER / TERMINATION semantics (Employee-scoped remains valid post-HIRE). |
| **Компоненты** | `app/services/personnel_orders*`; Personnel Orders UI; `employee_events`. |
| **Зависимости** | EPIC-1; EPIC-2; DG-4. |
| **Риски** | Legal/regression on order apply; dual HIRE paths during transition. |
| **Критерии завершения** | HIRE applicable from Candidate without pre-existing Employee; enroll-from-import converged or explicitly bridged; audit trail intact. |

### EPIC-6 — Employee Card Transformation

| Field | Content |
|-------|---------|
| **Цель** | HR Dossier / Employee Card displays Personnel Personal Record sections from target store (read-switch); preserve Composite View (INV-5). |
| **Почему нужен** | Audit: Composite View aligned but portfolio missing from dossier. |
| **Что изменяет** | HR Dossier composition, data sources, terminology. |
| **Что НЕ изменяет** | Working Employee Card (`/directory/staff`) operational role. |
| **Компоненты** | `corpsite-ui/` Employee Card, HR Dossier; composite read services. |
| **Зависимости** | EPIC-1; EPIC-3 (readable sections); EPIC-4 (data availability). |
| **Риски** | Employee Card perceived as SoT; performance of multi-source aggregation. |
| **Критерии завершения** | Phase 1 Personnel Personal Record sections visible in HR Dossier; Import Profile not primary read for migrated sections; INV-5 verified. |

### EPIC-7 — Control Output

| Field | Content |
|-------|---------|
| **Цель** | Control Output as **derived export** from Personnel Personal Record + Employment (INV-7); закрыть OAD-4, OAD-7. |
| **Почему нужен** | Currently Control Output Excel is import **input** — inverted vs target. |
| **Что изменяет** | Export projection, reconciliation with import bootstrap. |
| **Что НЕ изменяет** | Import upload path (retained as bootstrap/sync until OAD-7 cutover decision). |
| **Компоненты** | Export services; canonical snapshot layer; reports. |
| **Зависимости** | EPIC-1; EPIC-4/6 (data completeness); DG-5. |
| **Риски** | Org-wide reporting regression; mismatch with legacy Excel layout. |
| **Критерии завершения** | Derived Control Output export available; reconciliation report vs import; bootstrap path documented. |

### EPIC-8 — Data Migration

| Field | Content |
|-------|---------|
| **Цель** | Безопасный перенос historical data: Import Profile, employee overrides → Person-owned Personnel Personal Record sections. |
| **Почему нужен** | Dual-write alone leaves legacy SoT ambiguous. |
| **Что изменяет** | Data ownership, reconciliation, validation gates. |
| **Что НЕ изменяет** | Append-only employee_events history; committed PMF records (extend only). |
| **Компоненты** | Migration scripts (future WP); PMF bulk; validation reports. |
| **Зависимости** | EPIC-1; EPIC-4; EPIC-3/6 (target stores exist). |
| **Риски** | Data loss; IIN/person matching errors; long dual-write. |
| **Критерии завершения** | Reconciliation thresholds met; dual-write validation passes; rollback procedure tested. |

### EPIC-9 — Legacy Removal

| Field | Content |
|-------|---------|
| **Цель** | Retire transitional artifacts after read-switch and migration complete. |
| **Почему нужен** | Prevent permanent dual-path complexity (INV-8 violation risk). |
| **Что изменяет** | Deprecate Import Profile as SoT, employee overrides, redundant enroll path. |
| **Что НЕ изменяет** | Import as bootstrap channel if OAD-7 selects legacy-only sync. |
| **Компоненты** | Feature flags; API deprecation; UI removal; docs. |
| **Зависимости** | EPIC-6 read-switch; EPIC-8 migration; EPIC-7 export; DG-6. |
| **Риски** | Premature removal; orphaned data in staging. |
| **Критерии завершения** | Legacy read paths disabled by flag; no production dependency on employee-scoped Import Profile SoT; ARCH-002 invariants verified in production. |

### EPIC-10 — Person Identity Alignment

| Field | Content |
|-------|---------|
| **Цель** | Align identity storage (IIN) with Person as permanent identity anchor. |
| **Почему нужен** | Audit: `employee_identities` employee-scoped; rehire and Candidate paths need Person-level identity. |
| **Что изменяет** | Identity linkage model, reconciliation with Person. |
| **Что НЕ изменяет** | Operational Employee access model. |
| **Компоненты** | Identity services; `employee_identities`; Person layer; ADR-048 alignment. |
| **Зависимости** | EPIC-1; parallel with EPIC-2 early stages. |
| **Риски** | Duplicate IIN; migration of active employees. |
| **Критерии завершения** | Person-level identity authoritative for Personnel Personal Record; Employee identities derived or linked; rehire scenario verified. |

---

## 7. Work Package Breakdown

Work packages (**WP-PR-***) — небольшие, independently verifiable units.
Implementation details — в дочерних WP documents (создаются при старте
эпика).

### EPIC-1 — Foundation

| WP | Name | Priority |
|----|------|----------|
| WP-PR-001 | Architecture Variant decision package (OAD-1) | Must Have |
| WP-PR-002 | Personnel Personal Record aggregate boundary specification | Must Have |
| WP-PR-003 | Section catalog & completeness model | Must Have |
| WP-PR-004 | Person ↔ Personnel Personal Record linkage rules | Must Have |
| WP-PR-005 | Logical read model & composite projection contract | Must Have |
| WP-PR-006 | Provenance & personnel_record_events alignment | Should Have |

### EPIC-2 — Candidate Lifecycle

| WP | Name | Priority |
|----|------|----------|
| WP-PR-010 | Candidate lifecycle ADR (OAD-2) | Must Have |
| WP-PR-011 | Candidate creation without Employee | Must Have |
| WP-PR-012 | Candidate ↔ Personnel Personal Record binding | Must Have |
| WP-PR-013 | Candidate search & selection contract (for HIRE) | Must Have |
| WP-PR-014 | Coexistence spec: Candidate vs import-enroll | Should Have |

### EPIC-3 — Electronic Personnel Personal Record

| WP | Name | Priority |
|----|------|----------|
| WP-PR-020 | Phase 1 section scope decision (OAD-8) | Must Have |
| WP-PR-021 | Personnel Personal Record UI shell (Person-scoped) | Must Have |
| WP-PR-022 | Section editor: personal data & contacts | Must Have |
| WP-PR-023 | Section editor: education (PMF-backed read) | Must Have |
| WP-PR-024 | Section completeness & review status UI | Should Have |
| WP-PR-025 | Personnel Personal Record print/export specification | Could Have |

### EPIC-4 — PMF Integration

| WP | Name | Priority |
|----|------|----------|
| WP-PR-030 | PMF domain roadmap & Personnel Personal Record mapping | Must Have |
| WP-PR-031 | PMF domain: training (extend pilot) | Must Have |
| WP-PR-032 | PMF domain: qualifications / certificates | Should Have |
| WP-PR-033 | PMF domain: awards | Should Have |
| WP-PR-034 | Import Profile → PMF draft item bridge hardening | Must Have |
| WP-PR-035 | personnel_record_events taxonomy extension | Should Have |

### EPIC-5 — Personnel Orders Integration

| WP | Name | Priority |
|----|------|----------|
| WP-PR-040 | HIRE redesign ADR (OAD-5, OAD-6) | Must Have |
| WP-PR-041 | Order editor: Person / Personnel Personal Record picker | Must Have |
| WP-PR-042 | HIRE apply: create/link Employment from Candidate | Must Have |
| WP-PR-043 | Enroll-from-import → HIRE path convergence spec | Must Have |
| WP-PR-044 | HIRE regression & pilot verification package | Must Have |

### EPIC-6 — Employee Card Transformation

| WP | Name | Priority |
|----|------|----------|
| WP-PR-050 | HR Dossier: Personnel Personal Record sections panel | Must Have |
| WP-PR-051 | Read-switch feature flag (Import Profile → Personnel Personal Record) | Must Have |
| WP-PR-052 | Terminology alignment (кадровое досье / личный листок) | Should Have |
| WP-PR-053 | Working Employee Card vs HR Dossier boundary review | Should Have |

### EPIC-7 — Control Output

| WP | Name | Priority |
|----|------|----------|
| WP-PR-060 | Control Output ADR (OAD-4) | Must Have |
| WP-PR-061 | Export projection: Personnel Personal Record → Control Output | Must Have |
| WP-PR-062 | Reconciliation: derived export vs import bootstrap | Must Have |
| WP-PR-063 | Canonical roster export coexistence strategy (OAD-7) | Should Have |

### EPIC-8 — Data Migration

| WP | Name | Priority |
|----|------|----------|
| WP-PR-070 | Migration inventory & matching rules (Person / IIN) | Must Have |
| WP-PR-071 | Backfill: Import Profile → person-owned sections | Must Have |
| WP-PR-072 | Backfill: employee overrides → Person-owned store | Must Have |
| WP-PR-073 | Dual-write validation & reconciliation dashboards | Must Have |
| WP-PR-074 | Migration rollback drill | Must Have |

### EPIC-9 — Legacy Removal

| WP | Name | Priority |
|----|------|----------|
| WP-PR-080 | Deprecation plan: Import Profile as authoritative read | Should Have |
| WP-PR-081 | Retire employee_import_profile_overrides as SoT | Should Have |
| WP-PR-082 | Retire redundant enroll path (if converged) | Could Have |
| WP-PR-083 | Feature flag & legacy adapter cleanup | Should Have |

### EPIC-10 — Person Identity Alignment

| WP | Name | Priority |
|----|------|----------|
| WP-PR-090 | Person-level identity model ADR | Must Have |
| WP-PR-091 | employee_identities → Person linkage migration plan | Must Have |
| WP-PR-092 | Rehire identity continuity verification | Should Have |

---

## 8. Dependency Graph

### Critical path

``` text
EPIC-1 Foundation
    ↓
EPIC-10 Person Identity (partial parallel after WP-PR-004)
    ↓
EPIC-2 Candidate Lifecycle
    ↓
EPIC-5 Personnel Orders (HIRE redesign)
    ↓
EPIC-6 Employee Card (read-switch)
    ↓
EPIC-7 Control Output
    ↓
EPIC-8 Data Migration (overlap with above; finalize before legacy removal)
    ↓
EPIC-9 Legacy Removal
```

### Parallel tracks (after EPIC-1 DG-1)

``` text
                    EPIC-1 Foundation
                   /         |         \
                  /          |          \
        EPIC-10 Identity   EPIC-4 PMF   EPIC-3 Electronic PPR
                  \          |          /
                   \         |         /
                    EPIC-6 Employee Card (after EPIC-3 partial + EPIC-4 data)
                              |
                         EPIC-7 Control Output
                              |
                         EPIC-8 Data Migration
                              |
                         EPIC-9 Legacy Removal
```

**EPIC-4 PMF** может продолжаться параллельно EPIC-2 после section
catalog (WP-PR-003). **EPIC-3 UI** depends on Foundation + at least one
PMF-backed section. **EPIC-5 HIRE** blocks on Candidate (EPIC-2), not on
Control Output. **EPIC-7** blocks on sufficient Personnel Personal Record
data coverage (EPIC-4 + EPIC-6 read-switch for Phase 1).

---

## 9. Migration Strategy

| Change type | DB migration | Dual-write | Read-switch | Feature flag | Examples |
|-------------|--------------|------------|-------------|--------------|----------|
| Terminology / docs only | No | No | No | No | WP-PR-052 |
| Logical API additive | No* | No | No | Optional | WP-PR-005 read model |
| New person-owned tables | Yes | Yes | No → Yes | Yes | EPIC-1, EPIC-4 domains |
| PMF new domain commit | Yes | No** | No | Yes | WP-PR-031–033 |
| Candidate lifecycle | Yes | Yes | No | Yes | EPIC-2 |
| HIRE apply semantic change | Yes | Yes | No | Yes | EPIC-5 |
| HR Dossier data source | No*** | Yes | Yes | Yes | EPIC-6 WP-PR-051 |
| Control Output export | Optional | No | Yes | Yes | EPIC-7 |
| Historical backfill | Yes | Yes | N/A | Yes | EPIC-8 |
| Legacy removal | Yes (drop deferred) | Off | Full switch | Remove flag | EPIC-9 |

\* May add views or RPC without schema change.  
\** PMF commit is write to target; Import Profile remains until cutover.  
\*** Read-switch may require no schema change if target tables exist.

### Dual-write period rules

1.  **Writes** to Personnel Personal Record sections go through PMF or
    authoritative Person-scoped API — not Import Profile alone.
2.  **Import Profile** continues receiving import updates (bootstrap).
3.  **Reconciliation** (WP-PR-073) required before read-switch per
    section.
4.  **No Big Bang** cutover — section-by-section or domain-by-domain.

### Read-switch pattern

1.  Feature flag: `ppr_read_<section>` defaults off.
2.  Shadow read: compare Import Profile vs Personnel Personal Record
    (logging only).
3.  Flag on for HR Dossier read path.
4.  Deprecate Import Profile authoritative read (EPIC-9).

---

## 10. Compatibility Strategy

| Change | Classification | Bridge |
|--------|----------------|--------|
| Add Person-scoped Personnel Personal Record tables | Backward Compatible | Import Profile unchanged |
| Add Candidate without Employee | Backward Compatible | Import enroll still works |
| PMF new domain commit | Backward Compatible | Import Profile staging retained |
| HIRE from Candidate | **Breaking** (semantic) | Temporary: dual apply paths + flag |
| HR Dossier read-switch | Backward Compatible (read) | Legacy adapter serves Import Profile if flag off |
| Control Output derived export | Forward Compatible | Import input retained parallel |
| Remove employee override SoT | **Breaking** | Legacy adapter read-only archive |
| Person-level IIN | Breaking (identity) | Dual-link employee_identities during migration |

**Temporary Bridge** components (explicitly time-limited):

- Import Profile → PMF draft bridge (existing; hardened WP-PR-034).
- Enroll-from-import alongside HIRE-from-Candidate (until WP-PR-043).
- employee_identities + Person identity dual-link (EPIC-10).
- Canonical roster export alongside Control Output derived (EPIC-7).

---

## 11. Risks

| Risk | Probability | Impact | Mitigation | Rollback |
|------|-------------|--------|------------|----------|
| Big Bang pressure | Medium | High | Section-by-section gates; this roadmap | N/A — prevent |
| Dual-write data drift | High | High | WP-PR-073 reconciliation; block read-switch | Flag off read-switch |
| HIRE legal/regression | Medium | High | Pilot package WP-PR-044; dual path | Flag revert to Employee-first HIRE |
| Person/IIN mismatch on migration | Medium | High | WP-PR-070 inventory; manual review queue | Rollback migration batch |
| PMF commit failure blocks HR | Medium | Medium | Async retry; void run; keep Import Profile | Void PMF run; read from staging |
| Employee Card becomes de facto SoT | Medium | High | INV-5 reviews; composite-only tests | Documentation + architecture review |
| Premature legacy removal | Low | High | EPIC-9 only after DG-6; feature flags | Re-enable legacy flag |
| OAD-1 delay blocks all epics | Medium | High | Time-box Variant decision DG-1 | Continue PMF expansion only (limited) |
| Duplicate UI (Import vs PPR editors) | High | Medium | Phased section migration; hide migrated sections in Import modal | Show both until switch |
| Control Output layout mismatch | Medium | Medium | Reconciliation report; subset export | Keep import input parallel |

---

## 12. Decision Gates

| Gate | After | Decision required | Blocks |
|------|-------|-------------------|--------|
| **DG-0** | Roadmap approval | Proceed with EPIC-1 | All implementation |
| **DG-1** | WP-PR-001 | OAD-1: Variant A vs B | EPIC-2, schema WP |
| **DG-2** | WP-PR-010 | OAD-2: Candidate representation | EPIC-5 HIRE picker |
| **DG-3** | WP-PR-020 | OAD-8: Phase 1 sections | EPIC-3 editors, EPIC-4 priority domains |
| **DG-4** | WP-PR-040 | OAD-5, OAD-6: HIRE redesign & enroll convergence | EPIC-5 implementation |
| **DG-5** | WP-PR-060 | OAD-4, OAD-7: Control Output format & import role | EPIC-7 export cutover |
| **DG-6** | EPIC-8 complete | OAD-3: Import Profile cutover / dual-write end | EPIC-9 legacy removal |
| **DG-7** | EPIC-9 complete | ARCH-002 full implementation acceptance | — |

Each gate produces a recorded decision (ADR or architecture decision
record). **No gate skipped** for Breaking changes.

---

## 13. Definition of Ready / Definition of Done

### EPIC-1 Foundation

| DoR | DoD |
|-----|-----|
| ARCH-002 approved; DG-0 passed | DG-1 passed; aggregate boundary doc; section catalog; logical read contract published |
| Stakeholder for Variant decision identified | Zero regression in import / PMF / orders smoke paths |

### EPIC-2 Candidate Lifecycle

| DoR | DoD |
|-----|-----|
| EPIC-1 DoD; DG-1 | DG-2 passed; Candidate creatable; Personnel Personal Record bound; coexistence doc |
| | No requirement for Employee to edit Candidate Personnel Personal Record |

### EPIC-3 Electronic Personnel Personal Record

| DoR | DoD |
|-----|-----|
| EPIC-1 DoD; DG-3 Phase 1 sections | Phase 1 sections editable Person-scoped; completeness visible |
| At least one PMF-backed section (EPIC-4 partial) | Import Profile not required for Phase 1 Candidate edit |

### EPIC-4 PMF Integration

| DoR | DoD |
|-----|-----|
| EPIC-1 section catalog | Agreed domains live; events emitted; bridge hardened |
| PMF pilot stable | Domain commit success rate acceptable in pilot |

### EPIC-5 Personnel Orders Integration

| DoR | DoD |
|-----|-----|
| EPIC-2 DoD; DG-4 | HIRE from Candidate in pilot; WP-PR-044 passed |
| | Enroll convergence documented or implemented |

### EPIC-6 Employee Card Transformation

| DoR | DoD |
|-----|-----|
| EPIC-3 Phase 1 readable; EPIC-4 data | HR Dossier shows Personnel Personal Record sections; read-switch flag works |
| | INV-5 audit checklist passed |

### EPIC-7 Control Output

| DoR | DoD |
|-----|-----|
| EPIC-6 Phase 1 read-switch; DG-5 | Derived export available; reconciliation report |
| | Import bootstrap path explicit in ops docs |

### EPIC-8 Data Migration

| DoR | DoD |
|-----|-----|
| Target stores exist; dual-write running | Reconciliation thresholds met; rollback tested |
| WP-PR-070 inventory complete | DG-6 input criteria satisfied |

### EPIC-9 Legacy Removal

| DoR | DoD |
|-----|-----|
| DG-6 passed; EPIC-6/7/8 DoD | Legacy SoT paths disabled; flags removed per plan |
| | ARCH-002 invariant verification report |

### EPIC-10 Person Identity Alignment

| DoR | DoD |
|-----|-----|
| EPIC-1 Person linkage rules | Person-level identity authoritative; rehire case verified |
| ADR-048 reviewed | employee_identities bridge documented |

---

## 14. Repository Impact

Постепенное изменение **подсистем** (не файлов):

| Subsystem | Epics | Nature of change |
|-----------|-------|------------------|
| `app/` services (personnel, hr_import, personnel_orders, enrollment) | 1–5, 8, 10 | Domain logic, apply semantics, composite read |
| `app/api/`, `app/directory/` routes | 1–7 | Additive APIs, read-switch |
| `app/db/models/`, `alembic/` | 1, 2, 4, 8, 10 | New tables, person-owned sections, identity |
| `corpsite-ui/` personnel contour | 3, 5, 6 | Personnel Personal Record UI, order editor, dossier |
| `corpsite-ui/` import / PMF wizards | 4, 6, 9 | Bridge hardening, deprecation |
| `tests/` | All | Contract, reconciliation, HIRE regression, invariant tests |
| `docs/architecture/`, `docs/adr/` | All | ADRs, WP specs, decision records |
| `scripts/` (import) | 7, 8 | Bootstrap role documentation; optional validation scripts |

**Stable during transition:** Personnel Orders print/PDF; operational
Employee Card staff browse; admin enrollment queue (until convergence);
security/access subsystem.

---

## 15. Future ADRs

Вероятные отдельные ADR в процессе реализации (не сами ADR — только
перечень):

| ADR topic | Trigger | Related OAD |
|-----------|---------|-------------|
| Personnel Personal Record Aggregate Model | DG-1 | OAD-1 |
| Candidate Lifecycle Representation | DG-2 | OAD-2 |
| Phase 1 Personnel Personal Record Section Scope | DG-3 | OAD-8 |
| Import Profile Cutover & Dual-Write Policy | DG-6 | OAD-3 |
| Control Output Derived Export | DG-5 | OAD-4 |
| HIRE Redesign & Employment Creation | DG-4 | OAD-5, OAD-6 |
| Enroll-from-Import Convergence | DG-4 | OAD-6 |
| Person-Level Identity & IIN Policy | EPIC-10 | ADR-048 extension |
| PMF Domain Expansion Catalog | EPIC-4 | — |
| Personnel Personal Record Print & Official Form | EPIC-3 WP-PR-025 | — |
| HR Dossier Composite Read Model | EPIC-6 | — |
| Canonical Export vs Control Output Coexistence | DG-5 | OAD-7 |

---

## 16. Anti-Patterns

Следующие практики **запрещены** на протяжении внедрения ARCH-002:

1.  **Копировать данные из Candidate в Employee при HIRE** — Employment
    создаётся; Personnel Personal Record **не копируется** (INV-3).

2.  **Big Bang migration** — единовременный cutover всех sections,
    tables или UI.

3.  **Employee Card / HR Dossier как Source of Truth** — только Composite
    View (INV-5).

4.  **Смешивать Person и Employment Relationship** в одном store
    (должность, приказы, events в Personnel Personal Record).

5.  **Строить target architecture вокруг Import Profile** — Variant C
    rejected; Import Profile = transitional (INV-8).

6.  **Удалять legacy до DG-6** — EPIC-9 только после migration validation.

7.  **Control Output как input без derived path** — import bootstrap
    допустим параллельно, но target export обязателен (INV-7).

8.  **Новые employee-scoped authoritative stores** для кадровой
    биографии — только Person-owned Personnel Personal Record sections.

9.  **Skip decision gates** для Breaking changes (HIRE, identity, legacy
    removal).

10. **Dual-write без reconciliation** — read-switch блокируется.

---

## 17. Recommended Implementation Order

``` text
Phase A — Decide & Bound
  DG-0 → EPIC-1 (WP-PR-001 … WP-PR-006) → DG-1

Phase B — Parallel Foundation Tracks
  Track B1: EPIC-10 (identity) after WP-PR-004
  Track B2: EPIC-4 (PMF domains) after WP-PR-003
  Track B3: DG-3 → EPIC-3 Phase 1 UI shell

Phase C — Lifecycle & Orders
  EPIC-2 → DG-2 → EPIC-5 → DG-4 → pilot HIRE

Phase D — Composite & Export
  EPIC-6 read-switch → EPIC-7 → DG-5

Phase E — Migrate & Retire
  EPIC-8 → DG-6 → EPIC-9 → DG-7
```

**Must Have minimum viable ARCH-002 alignment:** Phase A + EPIC-2 + EPIC-5
+ EPIC-4 (education/training already pilot) + EPIC-6 (partial read-switch)
+ EPIC-1 invariants verified.

**Should Have for full personnel contour:** Phase D + EPIC-3 Phase 1
complete + EPIC-7.

**Could Have / Future:** EPIC-3 print; EPIC-4 extended domains (languages,
relatives); EPIC-9 full legacy removal if OAD-7 keeps import bootstrap.

---

## 18. Expected End State

После завершения всех epics и DG-7:

| Aspect | End state |
|--------|-----------|
| **Domain model** | Person → Personnel Personal Record → Employment Relationship |
| **Candidate** | Personnel Personal Record до Employee; HIRE из Candidate |
| **Data SoT** | Person-owned typed sections; PMF controlled migration |
| **Import Profile** | Bootstrap/reconciliation only (per OAD-7); not authoritative |
| **Employee Card** | Full Composite View including Personnel Personal Record sections |
| **Control Output** | Derived export; reconciliation with optional import sync |
| **Invariants** | INV-1 … INV-9 verified |
| **Legacy** | employee-scoped override SoT removed; redundant enroll path retired or bridged |
| **Documentation** | OAD closed; child ADRs published; ARCH-002 status → Implemented |

---

## 19. MoSCoW Summary (all Work Packages)

| Priority | Work Packages |
|----------|---------------|
| **Must Have** | WP-PR-001–005, 010–013, 020–023, 030–031, 034, 040–044, 050–051, 060–062, 070–074, 090–091 |
| **Should Have** | WP-PR-006, 014, 024, 032–033, 035, 052–053, 063, 080–081, 083, 092 |
| **Could Have** | WP-PR-025, 082 |
| **Future** | Remaining PMF domains beyond Phase 1 (languages, relatives, military, structured service record, photo); Personnel Personal Record PDF production rollout |

---

## 20. Related Documents

| Document | Role |
|----------|------|
| [ARCH-002](./ARCH-002-personnel-personal-record-architecture.md) | Normative target architecture |
| [ADR-047](../adr/ADR-047-personnel-personal-file-architecture.md) | Related subject layer (*Personal File*) |
| [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md) | Person persistence |
| [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md) | PMF technical framework |

---

## Document History

| Revision | Date | Change |
|----------|------|--------|
| 1 | 2026-07-15 | Initial implementation roadmap |
