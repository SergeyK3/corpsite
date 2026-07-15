# ADR-054 — Personnel Personal Record Aggregate Model

## Status

**Accepted**

| Field | Value |
|-------|-------|
| Work Package | WP-PR-001 |
| Open Architectural Decision | OAD-1 — **Closed** |
| Decision Gate | DG-1 — **Closed** (см. §Decision Gate) |
| Parent | [ARCH-002](../architecture/ARCH-002-personnel-personal-record-architecture.md) |
| Roadmap | [ARCH-002-IMPLEMENTATION-ROADMAP](../architecture/ARCH-002-IMPLEMENTATION-ROADMAP.md) |

---

## Context

ARCH-002 утверждает **Personnel Personal Record** (Личный листок по учёту кадров) как центральный предметный объект кадрового контура. Целевая модель:

```text
Person → Personnel Personal Record → Employment Relationship
```

Аудит репозитория (ARCH-002 «Repository Findings», 2026-07-15) подтвердил: person-owned sections существуют фрагментарно (PMF pilot), но единый aggregate boundary с dedicated ID отсутствует.

Roadmap определял **DG-1** как выбор между **Variant A** (отдельная сущность Personnel Personal Record) и **Variant B** (Person как aggregate root, Personnel Personal Record как logical view). **Variant C** (Import Profile + PMF as root) исключён как целевая модель (ARCH-002 normative).

Настоящий ADR фиксирует принятое решение по OAD-1. Документ не изменяет нормативные положения ARCH-002 и не предписывает миграции или код.

---

## Decision Drivers

1. **INV-1 … INV-9** (ARCH-002) — обязательны независимо от persistence path.
2. **Один личный листок на Person** на весь lifecycle (Candidate → Employee → Former Employee).
3. **Personnel Personal Record до Employment** — Candidate должен иметь досье без Employee.
4. **Совместимость с PMF pilot** — `person_education`, `person_training`, `personnel_record_events` уже person-scoped.
5. **Поэтапное внедрение** — без Big Bang; dual-write только при появлении target stores.
6. **Разделение domain decision и persistence decision** — ARCH-002 и ADR-047 допускают логический aggregate без единой физической таблицы на первой фазе.
7. **Backward compatibility** — import pipeline, Personnel Orders apply, Employee Card / HR Dossier остаются работоспособными на период transition.
8. **Понятность для кадровиков** — личный листок как узнаваемый кадровый объект.

---

## Existing Repository Facts

Факты подтверждены read-only проверкой репозитория (WP-PR-001, 2026-07-15).

| Fact | Evidence |
|------|----------|
| Таблица `persons` существует | `alembic/versions/u3v4w5x6y7z8_adr042_phase_b2_1_schema.py` §1; `docs/adr/ADR-042-phase-b1-schema-design.md` §4.1 |
| Семантика `persons`: постоянная идентичность, dedup, merge | `person_id`, `iin`, `full_name`, `match_key`, `person_status`, `merged_into_person_id` |
| `employees.person_id` — nullable FK | `u3v4w5x6y7z8` §3 |
| PMF commit блокируется без `person_id` | `app/services/personnel_migration_commit_service._resolve_employee_person_id()` |
| `person_education`, `person_training`, `personnel_record_events` — `person_id` FK | `app/db/models/personnel_migration.py` |
| PMF REST API и commit | `app/api/personnel_migration_router.py`; `tests/test_pmf_3b_mutation_api.py` |
| `employee_import_profile_overrides` — employee-scoped | `alembic/versions/k4d5e6f7a8b9_adr038_phase_a_employee_profile_overrides.py` |
| Import Profile — staging, не aggregate | `app/services/hr_import_profile_service.build_import_profile()` |
| `employee_identities` — employee-scoped IIN | `app/db/models/employee_identity.py` |
| HIRE apply требует `employee_id` | `app/services/personnel_orders_apply_service._apply_hire()` |
| HR Dossier — composite view | `app/services/hr_import_employee_card_service.py`; `corpsite-ui/lib/personnelCardTerminology.ts` |
| Person без Employee возможен | Schema; `tests/test_adr043_phase_c2_person_assignment_sync.py` |
| Dedicated PPR table / `personal_record_id` | **Отсутствует** |
| ADR-047 D1: logical Personal File on `person_id` | `docs/adr/ADR-047-personnel-personal-file-architecture.md` |

---

## Considered Options

| Option | Summary | Outcome |
|--------|---------|---------|
| **Variant A** | Person 1:1 Personnel Personal Record (entity + `personal_record_id`) 1:N sections | **Not selected** for Phase 1 persistence |
| **Variant B** | Person = aggregate root; Personnel Personal Record = logical composition | **Accepted** (Phase 1 persistence) |
| **Variant C** | Import Profile + PMF as root | **Rejected** (ARCH-002) |

---

## Variant A — Explicit Personnel Personal Record Entity (not selected)

```text
Person 1:1 Personnel Personal Record (personal_record_id) → typed sections
Employment Relationship — отдельно
```

Отдельный surrogate ID, lifecycle/completeness на PPR header, миграция FK на pilot-таблицы, transitional dual-key. Риск «пустой оболочки» над `persons`.

**Решение:** не принят для первой фазы. Пересмотр — только при срабатывании Future Triggers (§Consequences).

---

## Variant B — Person as Aggregate Root (accepted)

```text
Person (aggregate root, person_id)
  + person-owned sections
  + completeness / lifecycle / provenance metadata
  = Personnel Personal Record (logical)
Employment Relationship — отдельный bounded context
```

`person_id` — устойчивый идентификатор листка. PMF pilot без изменения FK. Metadata table для lifecycle и completeness — lean scope Phase 1.

---

## Business Object vs Persistence Model

### Domain Decision (принято)

**Personnel Personal Record — самостоятельный предметный объект** кадрового контура Corpsite.

Это бизнес-объект с инвариантами INV-2, INV-3: один листок на Person на весь lifecycle; листок не копируется при HIRE и повторном найме. Объект **не сводится** к Import Profile, Employee Card или Employee.

### Persistence Decision (принято — Phase 1)

**Person-root** — способ хранения первой фазы.

- `person_id` является устойчивым идентификатором Personnel Personal Record.
- Кадровые разделы, completeness metadata, provenance и lifecycle metadata — связанные person-owned данные.
- Отдельная основная таблица Personnel Personal Record и `personal_record_id` **на первой фазе не создаются**.

### Разделение решений

| Решение | Содержание | Статус |
|---------|------------|--------|
| **Domain** | Personnel Personal Record = автономный aggregate concept | **Accepted** |
| **Persistence Phase 1** | Person-root storage | **Accepted** |
| **Persistence Phase 2+** | Отдельная header-сущность | **Deferred** — см. Future Triggers |

Domain decision и persistence decision — **разные архитектурные решения**. Принятие Person-root **не отменяет** предметную самостоятельность Personnel Personal Record.

---

## Decision

Personnel Personal Record признаётся самостоятельным бизнес-объектом кадрового контура Corpsite.

На первой фазе внедрения его persistence model строится по варианту Person-root.

`person_id` является устойчивым идентификатором Personnel Personal Record.

Кадровые разделы, completeness metadata, provenance и lifecycle metadata хранятся как связанные person-owned данные.

Отдельная основная таблица Personnel Personal Record и отдельный `personal_record_id` на первой фазе не создаются.

Необходимость отдельной header-сущности пересматривается только при появлении подтверждённых требований:

- официальный номер личного листка;
- самостоятельный жизненный цикл;
- самостоятельное версионирование;
- multi-organization ownership;
- несколько кадровых листков для одного Person;
- самостоятельные права доступа или workflow,

которые невозможно корректно реализовать в Person-root модели.

---

## Business Decisions

### Decision B-1

На первой фазе отдельный официальный номер личного листка не вводится. `person_id` является устойчивым идентификатором.

### Decision B-2

Person может существовать вне кадрового контура. Personnel Personal Record создаётся, когда Person входит в кадровый процесс (Candidate, кадровый импорт, Employment, либо ручное создание кадровиком).

### Decision B-3

Personnel Personal Record имеет один экземпляр на одного Person. Повторный найм не создаёт новый Personal Record.

### Decision B-4

Personnel Personal Record является самостоятельным кадровым бизнес-объектом, но официальные кадровые документы являются его производными snapshots.

### Decision B-5

На первой фазе достаточно section-level provenance. Полное версионирование Personal Record не требуется.

### Decision B-6

Кадровикам предоставляется отдельный реестр Personnel Personal Record. Этот реестр является read model, а не доказательством необходимости отдельной основной таблицы.

---

## Decision Matrix

Оценки отражают анализ WP-PR-001; принятое решение соответствует **Variant B** (Person-root).

| # | Критерий | Variant A | Variant B | Примечание |
|---|----------|-----------|-----------|------------|
| 1 | Предметная ясность | STRONG | ACCEPTABLE | Domain autonomy зафиксирован отдельно (§Decision) |
| 2 | Соответствие ARCH-002 | STRONG | STRONG | Оба удовлетворяют target model |
| 3 | INV-1…INV-9 | STRONG | STRONG | 1:1 Person↔PPR enforced logically |
| 8 | PMF integration | ACCEPTABLE | **STRONG** | Pilot tables `person_id`-keyed |
| 16 | Объём миграции | WEAK | **STRONG** | No `personal_record_id` backfill |
| 18 | Риск «пустой оболочки» | HIGH_RISK | ACCEPTABLE | No empty header table Phase 1 |
| 21 | Dual-write requirements | HIGH_RISK | ACCEPTABLE | No dual-key on sections |
| 24 | Сложность ORM / schema | WEAK | **STRONG** | Additive metadata only |

Полная матрица (25 критериев) сохранена в revision 1 decision package; итоговый выбор — Variant B persistence при domain autonomy Variant A.

---

## Consequences

### Positive

- **Минимальная миграция** — pilot `person_education`, `person_training`, `personnel_record_events` без перепривязки FK.
- **Повторное использование PMF** — commit path и API остаются `person_id`-centric.
- **Отсутствие пустой оболочки** — нет surrogate-only `personnel_personal_records` table.
- **Отсутствие преждевременного dual-write** — нет transitional `person_id` + `personal_record_id` на sections.
- **Единый идентификатор** — `person_id` для PMF, composite read, реестра (B-1, B-6).
- **Согласованность с ADR-047** — logical Personal File на `person_id`.

### Negative

- **Metadata постепенно станет богаче** — lifecycle, completeness rollup потребуют lean metadata table (WP-PR-002/003).
- **Возможно появление отдельной header table в будущем** — при срабатывании Future Triggers.
- **`person_id` перегружает смысл** в API — требует чёткой терминологии (WP-PR-052).
- **Риск stealth Variant A** — metadata table может разрастись; контроль scope в WP-PR-002.

### Migration consequences

- Phase 1: additive `personnel_record_metadata` (или эквивалент) — **после** WP-PR-002 spec; без изменения pilot section FKs.
- `employees.person_id` backfill — EPIC-10, не блокирует WP-PR-002…005.
- Alembic для aggregate boundary — после WP-PR-002, не в WP-PR-001.

### Operational consequences

- Реестр личных листков (B-6) — read model поверх Person + metadata + sections.
- Кадровики работают с «личным листком» как бизнес-объектом; технически — `person_id`.
- HIRE, import, orders — без изменения до EPIC-5 / EPIC-2.

### Future constraints

- Новые person-owned sections FK → `person_id` (не `personal_record_id`) до пересмотра ADR.
- `personnel_record_events` остаётся `person_id`-keyed.
- Candidate lifecycle (OAD-2) — metadata / enum, не отдельная PPR entity.

### Future Triggers (пересмотр ADR)

Отдельная header-сущность (`personnel_personal_records`, `personal_record_id`) вводится **только** при подтверждении требований из §Decision:

| Trigger | Action |
|---------|--------|
| Официальный номер листка ≠ `person_id` | Новый ADR amendment |
| Самостоятельный lifecycle / versioning листка целиком | Amendment + WP |
| Multi-organization / несколько листков на Person | Amendment (конфликт с INV-2 — explicit exception) |
| Самостоятельные ACL / workflow на уровне листка | Amendment |

### Rollback implications

- Откат Phase 1: удаление metadata table; sections на `person_id` сохраняются.
- Откат domain decision потребовал бы пересмотра ARCH-002 — **вне scope** данного ADR.

---

## Migration Impact

| Area | Phase 1 (accepted) |
|------|-------------------|
| New DDL | Lean `personnel_record_metadata` (WP-PR-002) |
| `person_education` / `person_training` | Без изменения FK |
| `personnel_record_events` | Без изменения |
| `personal_record_id` | **Не вводится** |
| Dual-write на sections | **Не требуется** |
| `employees.person_id` backfill | EPIC-10 (parallel) |

---

## Compatibility

| Concern | Assessment |
|---------|------------|
| Import pipeline | Backward compatible — Import Profile остаётся bootstrap |
| PMF commit | Fully compatible |
| HIRE apply | Unchanged до EPIC-5 |
| HR Dossier | Backward compatible — composite read |
| `employee_identities` | Unchanged до EPIC-10 |
| ARCH-002 invariants | Satisfied via domain + Person-root persistence |
| Variant C | Rejected |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Metadata creep → stealth Variant A | WP-PR-002 caps metadata scope; Future Trigger review |
| Person vs PPR terminology confusion | WP-PR-052; B-6 read model labels |
| Person/IIN drift | EPIC-10 WP-PR-090 |
| Dual-write drift (Import Profile vs PPR) | EPIC-8 reconciliation; existing roadmap rules |

---

## Decision Gate

| Field | Value |
|-------|-------|
| **Gate** | DG-1 |
| **Status** | **Closed** |
| **Date** | 2026-07-15 |
| **Work Package** | WP-PR-001 |
| **OAD** | OAD-1 — Closed |

### Основание закрытия

1. Decision package WP-PR-001 выполнен.
2. Варианты A, B документированы; Variant C исключён.
3. Принято решение: domain autonomy + Person-root persistence Phase 1.
4. Business Decisions B-1 … B-6 зафиксированы.
5. ADR-054 статус **Accepted**.

### Связанные документы

- [ARCH-002](../architecture/ARCH-002-personnel-personal-record-architecture.md)
- [ARCH-002-IMPLEMENTATION-ROADMAP](../architecture/ARCH-002-IMPLEMENTATION-ROADMAP.md)

### Разблокировано

Переход к WP-PR-002 … WP-PR-006 **без повторного обсуждения Variant A/B** для Phase 1.

---

## Roadmap Impact

После закрытия DG-1 разрешается немедленный переход к:

| WP | Название | Примечание |
|----|----------|------------|
| **WP-PR-002** | Aggregate boundary specification | Person-root boundary |
| **WP-PR-003** | Section catalog & completeness model | Metadata rollup на `person_id` |
| **WP-PR-004** | Person ↔ Personnel Personal Record linkage | `person_id` = linkage |
| **WP-PR-005** | Logical read model & composite projection | Resolver: Employee → Person → sections |
| **WP-PR-006** | Provenance & personnel_record_events alignment | Events `person_id`-keyed |

Повторное сравнение Variant A/B для Phase 1 **не требуется**. EPIC-2 (OAD-2), EPIC-5 (OAD-5) остаются на своих decision gates.

---

## Impact on Subsequent Work Packages

### WP-PR-002 — Aggregate boundary

Boundary = Person root + lean metadata + person-owned section tables. Employment data explicitly outside boundary.

### WP-PR-003 — Section catalog & completeness

Per-section completeness + metadata rollup; section FK target = `person_id`.

### WP-PR-004 — Person ↔ PPR linkage

`person_id` IS the stable linkage; metadata 1:1 when Personnel Personal Record materialized; merge follows Person survivor.

### WP-PR-005 — Logical read model

Composite read keyed by `person_id`; `personnelPersonalRecordId` = `personId` Phase 1 alias in API contract.

### WP-PR-006 — Event taxonomy

Events remain `person_id`-keyed; optional envelope events on metadata lifecycle changes.

### EPIC-10 — Person Identity Alignment

Person authoritative; metadata row created when Person enters HR contour (B-2).

### Candidate lifecycle (EPIC-2)

`hr_lifecycle_state` on metadata; OAD-2 still required for representation.

### HIRE redesign (EPIC-5)

Order picker selects `person_id` where lifecycle = Candidate.

### PMF expansion (EPIC-4)

New domains FK → `person_id`; no `personal_record_id`.

### Control Output (EPIC-7)

Projection from person-owned sections; independent of aggregate ID.

---

## Related Documents

| Document | Relation |
|----------|----------|
| [ARCH-002](../architecture/ARCH-002-personnel-personal-record-architecture.md) | Normative target; INV-1…INV-9; OAD-1 closed |
| [ARCH-002-IMPLEMENTATION-ROADMAP](../architecture/ARCH-002-IMPLEMENTATION-ROADMAP.md) | DG-1 closed; WP-PR-001…006 unblocked |
| [ADR-047](./ADR-047-personnel-personal-file-architecture.md) | Personal File logical model; `person_id` anchor |
| [ADR-048](./ADR-048-person-ownership-identity-creation-policy.md) | Person materialization; `employees.person_id` |
| [ADR-PMF-001](./ADR-PMF-001-personnel-migration-framework.md) | PMF technical framework |
| [ADR-042 Phase B1](./ADR-042-phase-b1-schema-design.md) | `persons` schema |
| [ADR-EDU-001](./ADR-EDU-001-employee-education-migration-architecture.md) | Education person-owned SoT |

---

## Document History

| Revision | Date | Change |
|----------|------|--------|
| 1 | 2026-07-15 | Initial decision package (WP-PR-001), Proposed |
| 2 | 2026-07-15 | Accepted; OAD-1 closed; DG-1 closed; renumbered ADR-054 |
