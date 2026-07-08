# PMF-PILOT-FREEZE — Personnel Migration Framework Pilot Freeze

## Status

| Field | Value |
|-------|-------|
| Framework | Personnel Migration Framework (PMF) |
| Pilot domain | **Education** (ADR-EDU-001) |
| Pilot readiness | **Pilot Ready with Recommendations** |
| Development status | **Development Frozen** |
| Freeze date | 2026-07-08 |
| Next program | [Personnel Intake Framework (PIF)](../personnel-intake/PIF-001-personnel-intake-framework.md) |

**No runtime effect.** This document records an architectural and program-management decision. It does not modify code, API, schema, or PMF behavior.

---

## 1. Decision

PMF достиг состояния **Pilot Ready with Recommendations** по вертикали **Education**. Разработка PMF **заморожена** (Pilot Freeze). Немедленное продолжение **PMF-4F** не выполняется.

Это **не отмена PMF**. Это **изменение приоритета** развития проекта в пользу более ценной для бизнеса функциональности — **Electronic Personnel Intake** ([PIF](../personnel-intake/PIF-001-personnel-intake-framework.md)).

---

## 2. Причина заморозки

| Factor | Detail |
|--------|--------|
| Business priority | Электронный приём новых сотрудников устраняет двойной ввод (бумага → Excel → HRIS) и даёт прямой путь к кадровым данным |
| PMF pilot outcome | Education vertical завершена end-to-end; критических замечаний Pilot Readiness Review нет |
| Architecture stability | PMF Commit Engine, domain plugin model, provenance и audit считаются **стабильными** и пригодными для controlled pilot |
| Deferred scope | PMF-4F (History, Advanced Mapping, Lifecycle Operations) не блокирует pilot и не блокирует pivot на PIF |

---

## 3. Что считается завершённым (Education Pilot)

Полный путь для домена **Education**:

```text
Import
  ↓
Review
  ↓
Migration Session
  ↓
Draft
  ↓
Commit
  ↓
Success
```

### 3.1. Завершённые work packages

| WP | Scope | Status |
|----|-------|--------|
| PMF-0 | Ratification (ADR-PMF-001, ADR-EDU-001) | ✅ Done |
| PMF-1 | Schema (`personnel_migration_*`, `person_education`, `person_training`, `personnel_record_events`) | ✅ Done |
| PMF-2 | Commit Engine (TX commit, void/supersede, provenance, record events) | ✅ Done |
| PMF-3 | Wizard Shell + REST API | ✅ Done |
| PMF-4A–4E | Education plugin UI: home, session, review, commit, success | ✅ Done |
| PMF-5 | Pilot Readiness Review (Education) | ✅ Done — Pilot Ready with Recommendations |

### 3.2. Архитектурные инварианты (сохраняются)

- Import Layer — **staging only**; после `commit` runtime UI не читает staging для данного домена и сотрудника.
- `person_id` — обязательное предусловие commit ([ADR-PMF-001 §13](../adr/ADR-PMF-001-personnel-migration-framework.md)).
- Бизнес-журнал — `personnel_record_events`; отдельная таблица `personnel_migration_events` **не создаётся**.
- Rollback — `voided` / `superseded`; физический DELETE не используется.
- Контрольный список — **производный отчёт**, не source of truth.

---

## 4. Что переносится в Future (PMF-4F)

| WP | Name | Scope (deferred) |
|----|------|------------------|
| **PMF-4F.1** | History | История миграций, diff между runs, audit timeline в UI |
| **PMF-4F.2** | Advanced Mapping | Расширенное сопоставление полей, bulk mapping, domain-specific transform rules |
| **PMF-4F.3** | Lifecycle Operations | Reconciliation wizard, repeat migration, domain lifecycle (supersede chains, domain rollback UX) |

**Условие возобновления:** отдельное program decision после PIF pilot или по результатам Education controlled pilot в production.

---

## 5. Архитектура PMF — стабильна

Следующие компоненты считаются **зафиксированными** и не подлежат пересмотру в рамках Pilot Freeze:

| Component | Role |
|-----------|------|
| Domain plugin registry | Расширяемость без изменения Commit Engine |
| Migration Run / Item model | Technical audit + idempotent commit |
| Review gate | Human-in-the-loop перед migration session |
| Commit Engine | Единственная точка записи в `person_*` из staging |
| Provenance Writer | `source_record_key`, batch/run linkage |
| Personnel Record Events | Business journal (`EDUCATION_MIGRATED`, …) |
| Education plugin | Первая reference implementation |

PMF остаётся **одним из источников данных** в новой архитектуре Personnel Intake — см. [PIF-001 §5](../personnel-intake/PIF-001-personnel-intake-framework.md).

---

## 6. Controlled pilot (Education)

PMF Education pilot **разрешён** в controlled mode:

- Ограниченный набор HR-операторов;
- Сотрудники с привязанным `person_id`;
- Bootstrap: Import → Review → Migration Session → Commit;
- Мониторинг через `personnel_migration_runs` и `personnel_record_events`.

Новая feature-разработка в PMF **не ведётся** до снятия freeze.

---

## 7. Связанные документы

| Document | Relationship |
|----------|--------------|
| [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md) | Normative PMF architecture (**Ratified**) |
| [ADR-EDU-001](../adr/ADR-EDU-001-employee-education-migration-architecture.md) | Education domain plugin (**Ratified**) |
| [ADR-047](../adr/ADR-047-personnel-personal-file-architecture.md) | Target Personal File aggregate |
| [PIF-001](../personnel-intake/PIF-001-personnel-intake-framework.md) | Successor program — Personnel Intake |
| [PIF-roadmap](../personnel-intake/PIF-roadmap.md) | PIF work package sequence |

---

## 8. Governance note

| Action | Allowed during freeze |
|--------|----------------------|
| Education controlled pilot | ✅ |
| Bugfix / security patch in PMF | ✅ (case-by-case) |
| PMF-4F feature development | ❌ |
| New domain plugins (Service Record, Certificates) | ❌ (deferred) |
| PIF program initiation | ✅ |
