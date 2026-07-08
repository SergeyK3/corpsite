# Personnel Migration Framework (PMF) — Documentation Index

Индекс проектной документации **Personnel Migration Framework (PMF)** — архитектуры переноса данных из Import Layer (staging) в постоянные кадровые сущности (`person_*`).

| Поле | Значение |
|------|----------|
| **Контур** | Кадровые процессы → Миграция |
| **Канонический формат** | **Markdown** (`.md`) |
| **Последнее обновление индекса** | 2026-07-08 |

---

## Канонический формат

**Markdown является каноническим форматом PMF-документации.**

- Ratified ADR, design-документы и roadmap публикуются как `.md` в `docs/`.
- DOCX, extracted text и прочие форматы — вспомогательные артефакты; при расхождении приоритет у Markdown.
- Именование WP-документов: `PMF-{phase}-{topic}.md` (например, `PMF-4A-migration-wizard-design.md`).

---

## Статус Work Packages

| WP | Название | Статус | Артефакты |
|----|----------|--------|-----------|
| **PMF-0** | Architecture | **done** | [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md), [ADR-EDU-001](../adr/ADR-EDU-001-employee-education-migration-architecture.md) |
| **PMF-1** | Schema | **done** | Alembic `q1r2s3t4u5w6_pmf_1_personnel_migration_schema`; `tests/test_pmf_1_schema.py` |
| **PMF-2** | Commit Engine | **done** | `app/services/personnel_migration_commit_service.py`; `tests/test_pmf_2_commit_engine.py` |
| **PMF-3A** | Draft API | **done** | `app/api/personnel_migration_router.py` (draft layer); `tests/test_pmf_3a_api.py` |
| **PMF-3B** | Mutation API | **done** | [PMF-3B-mutation-api-design.md](./PMF-3B-mutation-api-design.md); `tests/test_pmf_3b_mutation_api.py` |
| **PMF-4A** | Wizard Design | **done** | [PMF-4A-migration-wizard-design.md](./PMF-4A-migration-wizard-design.md) |
| **PMF-4B** | Navigation + shell | **next** | — |
| PMF-4C | Draft Run UI | planned | см. [PMF-4A §12](./PMF-4A-migration-wizard-design.md#12-реализация--разбиение-pmf-4) |
| PMF-4D | Items Grid + mapping | planned | см. PMF-4A §12 |
| PMF-4E | Commit UI | planned | см. PMF-4A §12 |
| PMF-4F | History UI | planned | см. PMF-4A §12 |
| PMF-4G | Pilot (Education) | planned | см. PMF-4A §12 |

> **PMF-3A** реализован в коде; отдельного design-документа в `docs/personnel-migration/` нет. Контракт draft-layer описан в [PMF-3B-mutation-api-design.md](./PMF-3B-mutation-api-design.md) и [ADR-PMF-001 §4](../adr/ADR-PMF-001-personnel-migration-framework.md#4-детализация-компонентов).

---

## Документы в `docs/personnel-migration/`

| Документ | Описание |
|----------|----------|
| [README.md](./README.md) | Этот индекс |
| [PMF-3B-mutation-api-design.md](./PMF-3B-mutation-api-design.md) | Design mutation API: commit, void, supersede, record events |
| [PMF-4A-migration-wizard-design.md](./PMF-4A-migration-wizard-design.md) | Design Migration Wizard UI (экраны, UX, навигация, PMF-4B–4G) |

---

## Ratified ADR (архитектура)

| Документ | Описание |
|----------|----------|
| [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md) | Personnel Migration Framework — общая архитектура, компоненты, commit/audit |
| [ADR-EDU-001](../adr/ADR-EDU-001-employee-education-migration-architecture.md) | Education — первая domain-plugin реализация PMF |

---

## Связанные ADR (контекст миграции)

| Документ | Связь с PMF |
|----------|-------------|
| [ADR-045](../adr/ADR-045-personnel-hr-processes-split.md) | UI contour: Wizard в «Кадровые процессы» |
| [ADR-047](../adr/ADR-047-personnel-personal-file-architecture.md) | Целевой aggregate; PMF = Phase D bridge |
| [ADR-047 Appendix — Four-Layer Model](../adr/ADR-047-appendix-four-layer-model.md) | Import Layer = staging only |
| [ADR-038](../adr/ADR-038-employee-identity-hr-import-architecture.md) | HR Import — источник staging |
| [ADR-039 Phase 3B](../adr/ADR-039-Phase-3B-schema.md) | Normalized records как candidate source |
| [ADR-040](../adr/ADR-040-canonical-hr-snapshot-monthly-diff.md) | Reconciliation input (future PMF-6) |
| [ADR-044](../adr/ADR-044-identity-reconciliation.md) | Reference pattern: runs + items + dry-run/commit |

---

## Known backend gaps for Wizard

Ограничения **реализованного** PMF Backend (PMF-3B), влияющие на Migration Wizard UI. Полная таблица: [PMF-4A Appendix B](./PMF-4A-migration-wizard-design.md#appendix-b--known-pmf-3b-gaps-wizard-workarounds).

| Gap | Wizard workaround | Future WP |
|-----|-------------------|-----------|
| **Нет `GET /personnel-migration/runs` (list runs)** | Session recent list + deep links по `run_id` | PMF-3C |
| Нет update/delete draft item | Re-add item / пересоздать run | PMF-3C |
| Нет candidate resolver API | Client integration с Import/Review APIs | PMF-5 |
| Нет dry-run endpoint | Client required-field hints | PMF-3C |
| Нет staging `mark_migrated` после commit | Informational only post-commit | PMF-2 enhancement |
| Domain `is_enabled=false` по умолчанию | Enable для pilot через admin/seed | PMF-4G runbook |
| `run_mode` не в schema | Хранить в `metadata` | PMF-3C |

**Реализованные endpoints** (PMF-3B): см. [PMF-4A Appendix A](./PMF-4A-migration-wizard-design.md#appendix-a--pmf-3b-api-reference-implemented).

---

## Дорожная карта PMF-4B–PMF-4G

Детальное описание: [PMF-4A §12 — Реализация](./PMF-4A-migration-wizard-design.md#12-реализация--разбиение-pmf-4).

```text
PMF-4A (design) ──► PMF-4B ──► PMF-4C ──► PMF-4D ──► PMF-4E ──► PMF-4F ──► PMF-4G (pilot)
```

| WP | Название | Deliverable |
|----|----------|-------------|
| **PMF-4B** | Navigation + shell | Routes `/directory/personnel/migration/**`, sub-nav, guards, `MigrationWizardShell`, domain cards |
| **PMF-4C** | Draft Run UI | Employee select, `POST /runs/draft`, workflow stepper, session route |
| **PMF-4D** | Items Grid + mapping | Candidates table, split-view, `EducationMigrationForm`, `POST .../items` |
| **PMF-4E** | Commit UI | Pre-commit review, confirm, 422 errors, void/supersede dialogs |
| **PMF-4F** | History UI | Record events table, Run Details, side rail |
| **PMF-4G** | Pilot (Education) | E2E pilot, Review/Import Card links, domain enablement runbook |

**Optional (вне PMF-4):** PMF-3C (list runs, update/delete items), PMF-4H (reconciliation UI), PMF-4I (second domain UI).

---

## Быстрые ссылки

| Задача | Документ |
|--------|----------|
| Понять архитектуру PMF | [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md) |
| Education domain | [ADR-EDU-001](../adr/ADR-EDU-001-employee-education-migration-architecture.md) |
| Backend API (commit/void/events) | [PMF-3B-mutation-api-design.md](./PMF-3B-mutation-api-design.md) |
| Wizard UX и экраны | [PMF-4A-migration-wizard-design.md](./PMF-4A-migration-wizard-design.md) |
| Backend gaps для UI | [PMF-4A Appendix B](./PMF-4A-migration-wizard-design.md#appendix-b--known-pmf-3b-gaps-wizard-workarounds) |
