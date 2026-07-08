# PMF Pilot Readiness Review

## Метаданные

| Поле | Значение |
|------|----------|
| Документ | PMF-PILOT-READINESS-REVIEW |
| Дата review | 2026-07-08 |
| Scope | PMF-4A → PMF-4E (Personnel Migration Wizard, Education pilot) |
| Тип | Engineering + architecture review (read-only) |
| Backend / API / Schema | **Не изменялись** в рамках review |
| Связанные ADR | [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md), [ADR-EDU-001](../adr/ADR-EDU-001-employee-education-migration-architecture.md) |

---

## 1. Executive Summary

Реализована **рабочая вертикаль переноса** для пилота Education по пути **Import Review → Session → Commit → Success**. Bootstrap, auto draft run, candidate selection, review summary и commit UX функционируют на существующих PMF-3B API без изменений backend.

**Итоговая оценка: Pilot Ready with Recommendations**

Пилот допустим для **контролируемого запуска** (1–2 сотрудника, вход из Review) при условии:
- эксперты проходят путь через CTA «Перенести в кадровую карточку»;
- верификация результата — через личную карточку (`/directory/staff`) или админ-инструменты до появления Education tab (PMF-4F).

Критических блокеров commit/bootstrap не выявлено. Основные отклонения от ADR — **отложенные по дизайну** элементы PMF-4F+ (split-view mapping, History, Education tab, Migration Home employee picker).

---

## 2. User Flow Review

### 2.1. Целевой путь (пилот)

```text
Import (ETL)
  ↓
Review (/directory/personnel/import/review)
  ↓  [CTA: Перенести в кадровую карточку]
Transfer (/directory/personnel/migration/education/{employeeId}?candidate_id=…&source=review)
  ↓
Session Bootstrap (auto draft run)
  ↓
Candidate (load approved records → auto-select / manual select)
  ↓
Add Item (POST /runs/{id}/items)
  ↓
Review Summary (шаг «Проверка»)
  ↓
Commit Confirm → POST /runs/{id}/commit
  ↓
Success (шаг «Готово»)
```

### 2.2. Проверка тупиков

| Точка | Статус | Комментарий |
|-------|--------|-------------|
| Review без approve/bind | OK | CTA скрыт (`canShowMigrationCta`) |
| Migration Home | **Dead end** | «Выбрать сотрудника» disabled — не блокирует Review-путь |
| Person blocker | Soft dead end | Нет CTA на привязку Person; только Review / Home |
| run_not_draft (resume committed) | Soft dead end | Info banner, без Success replay |
| Пустой список кандидатов | OK | Сообщение + ссылка на Review |
| Commit validation 422 | OK | HR-friendly error + technical details |
| Success | OK | Ссылка на staff + Review |

**Циклов** в state machine не обнаружено. Повторный commit блокируется backend (409) и HR-сообщением.

### 2.3. Альтернативные входы

| Вход | Поддержка |
|------|-----------|
| Review deep link | **Primary pilot path** — полностью |
| Migration Home → employee | Не реализован (PMF-4F) |
| Deep link без candidate_id | Ручной выбор из списка |
| sessionStorage resume | Draft run resume |
| `?run_id=` query | Resume draft |

---

## 3. Architecture Compliance Matrix

### ADR-PMF-001

| Требование | Статус | Комментарий |
|------------|--------|-------------|
| Wizard = единственная точка commit | **Соответствует** | Commit только через UI → PMF-3B |
| HR не создаёт Draft Run вручную | **Соответствует** | Auto Draft Run Policy (PMF-4C) |
| `person_id` precondition | **Соответствует** | Блокер при draft create; commit gating |
| Review gate без записи в personnel | **Соответствует** | Review отдельно; CTA в Wizard |
| Split-view mapping UI | **Отклонение (deferred)** | Review Summary вместо split-view (PMF-4F) |
| Wizard footer (Skip/Dry-run/Save draft) | **Отклонение (deferred)** | Только confirm commit |
| Run history / audit UI | **Отклонение (deferred)** | PMF-4F History |
| Reconciliation mode | **Отклонение (deferred)** | PMF-9+ |
| `review_status=migrated` marker | **Частично** | Backend PMF; frontend тип `migrated` отсутствует (используется `promoted` в import API) |
| Route `/migration/runs/{id}` | **Отклонение (deferred)** | PMF-4F |

### ADR-EDU-001

| Требование | Статус | Комментарий |
|------------|--------|-------------|
| Education/training → `person_education/training` | **Соответствует** | Commit Engine plugin |
| Review CTA для approved+bound | **Соответствует** | `ImportNormalizedRecordDrawer` |
| Field mapping staging → personnel | **Упрощение** | Auto `buildDraftPayloadFromNormalizedRecord`; без UI редактирования |
| Education tab verify (`/employees/{id}/education`) | **Отклонение (deferred)** | Success → `/directory/staff` |
| Split-view mock (§4.4) | **Отклонение (deferred)** | `MigrationWorkspaceSkeleton` не подключён |
| Pilot 1–2 employees | **Соответствует** | Нет allowlist UI (backend guard optional) |

### PMF-4A (API client foundation)

| Аспект | Статус |
|--------|--------|
| Frontend tag PMF-4A | Отсутствует в коде |
| Фактическая реализация | `personnelMigrationApi.client.ts` — domains, draft, get, items, commit |
| Оценка | **Соответствует** по смыслу (потребление PMF-3A/3B) |

### PMF-4B (Migration Home)

| Аспект | Статус |
|--------|--------|
| HR-first home, domain cards, process chain | **Соответствует** |
| Employee picker | **Отклонение** — disabled stub |
| Technical details collapsed | **Соответствует** |

### PMF-4C (Session Bootstrap)

| Аспект | Статус |
|--------|--------|
| Auto Draft Run Policy | **Соответствует** |
| Entry source resolver | **Соответствует** |
| sessionStorage resume | **Соответствует** (временный до PMF-3C list-runs) |
| Person blocker | **Соответствует** (UX polish: без remediation CTA) |
| Route `/{domain}/{employeeId}` | **Улучшение** vs ADR query `?employee_id=` — чище для Next.js |

### PMF-4D (Mapping Workspace Phase 1)

| Аспект | Статус |
|--------|--------|
| Candidate list + auto-select | **Соответствует** |
| Add item API | **Соответствует** |
| Source context panel | **Соответствует** (после polish: HR label «Ключ записи») |
| Workspace skeleton | **Частично** — компонент есть, не в основном flow |
| Stepper «Записи» | **Улучшение** — активен во время adding (polish) |

### PMF-4E (Commit UX)

| Аспект | Статус |
|--------|--------|
| Review Summary | **Соответствует** |
| Commit CTA + confirm | **Соответствует** |
| Success state | **Соответствует** |
| HR error mapping | **Соответствует** |
| Stepper «Готово» | **Соответствует** |

---

## 4. UX Review

### 4.1. HR-first terminology

| Область | Оценка |
|---------|--------|
| Commit / confirm / success | Хорошо |
| Review Summary | Хорошо |
| Process chain на Home | Хорошо |
| Nav / breadcrumb «Миграция» | Minor: расходится с «Перенос» в hero |
| Technical Details | Корректно свёрнуты; technical terms допустимы |
| Person blocker | Исправлено: убрано «Person» из заголовка |

### 4.2. Состояния и ошибки

| Состояние | Понятность |
|-----------|------------|
| Loading bootstrap | OK |
| Forbidden | OK |
| Domain missing/disabled | OK |
| Employee missing | OK |
| Person blocker | OK (без remediation) |
| run_not_draft | OK (ограниченно) |
| Select / review / success phases | OK |
| Commit errors | OK — HR mapping, raw в technical block |

### 4.3. Navigation

- Review ↔ Session: двусторонние ссылки
- Success → staff, Review
- Home: информативный, не operational entry для пилота

---

## 5. State Flow Review

| Transition | Корректность | Риск |
|------------|--------------|------|
| Bootstrap → ready | OK | — |
| Resume draft (storage/query) | OK | Stale storage очищается при invalid run |
| Auto-add from candidate_id | OK | `autoAddAttemptedRef` предотвращает loop |
| add item → review phase | OK | — |
| commit → success + GET refresh | OK | — |
| clear sessionStorage on success | OK | — |
| committed run via resume | Info banner | Не success replay |
| Duplicate item same source | OK | Skip re-POST |

**Неконсистентные состояния:** явных race не выявлено; `runRef` защищает async callbacks.

---

## 6. Error Flow Review

| Error class | HR UI | Technical details |
|-------------|-------|-------------------|
| Network | `migrationHrLoadError` / `migrationHrCommitError` | lastError |
| 403 forbidden | Dedicated panel | — |
| person_id 422 | Person blocker | — |
| run not draft | Info banner | run status |
| validation 422 (commit) | Generic HR message | lastError (raw) |
| 409 double commit | HR «уже завершён» | lastError |

Raw backend errors **не показываются** как primary text в commit flow.

---

## 7. Component Review

| Component | Lines | Responsibility | Refactor need |
|-----------|-------|----------------|---------------|
| `MigrationSessionWorkspace` | ~361 | **Main orchestrator** | Medium — кандидат на split (commit phase hook) в PMF-4F |
| `MigrationSessionPageClient` | ~326 | Bootstrap FSM | Low |
| `personnelMigrationEntry` | ~113 | Draft run policy | Low |
| `personnelMigrationCandidates` | ~136 | Candidate helpers | Low |
| `personnelMigrationHrLabels` | ~237 | HR copy | Low — centralised |
| `MigrationReviewSummaryPanel` | ~81 | Pre-commit summary | Low |
| `MigrationCommitConfirmDialog` | ~61 | Confirm modal | Low |
| `MigrationCommitSuccessPanel` | ~79 | Success | Low |
| `MigrationWorkspaceSkeleton` | ~81 | Unused stub | Remove or wire in PMF-4F |
| `MigrationWorkflowStepper` | ~53 | Visual only | Low |

**MigrationSessionWorkspace** — единственный компонент с повышенной сложностью; для PMF-4F рекомендуется выделить `useMigrationSessionPhase` hook без изменения пилотного поведения.

---

## 8. Technical Debt Register

### Critical (блокирует Pilot)

*Не выявлено.*

### Major (не блокирует Pilot; планировать PMF-4F)

| ID | Категория | Описание | Pilot |
|----|-----------|----------|-------|
| M-01 | Architecture | Нет split-view field mapping (ADR §4.3, EDU §4.4) | Не блокирует |
| M-02 | Architecture | Нет Education tab `/employees/{id}/education` | Не блокирует |
| M-03 | UX | Migration Home employee picker disabled | Не блокирует |
| M-04 | UX | run_not_draft не показывает Success replay | Не блокирует |
| M-05 | Code | Тонкое тест-покрытие workspace/bootstrap | Не блокирует |
| M-06 | Architecture | sessionStorage вместо list-runs API | Не блокирует |

### Minor (не блокирует Pilot)

| ID | Категория | Описание | Pilot |
|----|-----------|----------|-------|
| m-01 | UX | Nav «Миграция» vs «Перенос» | Не блокирует |
| m-02 | UX | Person blocker без remediation CTA | Не блокирует |
| m-03 | Code | `MigrationWorkspaceSkeleton` unused | Не блокирует |
| m-04 | Architecture | Auto draft payload `education_kind: "other"` always | Не блокирует* |
| m-05 | Documentation | ADR route shape vs path param | Не блокирует |
| m-06 | UX | Дублирование stepper в blocker shell | Не блокирует |

\* Риск validation 422 при несовпадении record type — низкий для типовых training records.

### Editorial

| ID | Описание |
|----|----------|
| E-01 | PMF-4A не тегирован в коде (маппится на API client) |
| E-02 | Skeleton placeholders ссылаются на «PMF-4E» вместо «PMF-4F» |
| E-03 | `review_status=migrated` в ADR vs `promoted` в import types |

---

## 9. Polish Applied During Review

| File | Change |
|------|--------|
| `personnelMigrationHrLabels.ts` | Person blocker без термина «Person» |
| `MigrationCandidateSourcePanel.tsx` | `candidate_id` → «Ключ записи» |
| `MigrationCandidateList.tsx` | `ID n` → «Запись № n» |
| `MigrationSessionWorkspace.tsx` | Stepper «Записи» активен во время adding |

---

## 10. Test & Build Status (at review time)

| Check | Result |
|-------|--------|
| `npm run build` | Pass (PMF-4E baseline) |
| Unit tests (migration) | 17+ tests pass (candidates, drawer CTA, stepper, commit labels, API) |
| E2E / integration | Not present |

---

## 11. PMF-4F Recommendations (next WP)

1. **History UI** — runs list, run detail, committed replay
2. **Split-view mapping** — wire or replace `MigrationWorkspaceSkeleton`
3. **Education tab** — `EmployeeEducationPageClient` + post-commit verify link
4. **Migration Home employee picker** — pilot employee selection
5. **Workspace integration tests** — bootstrap, add item, commit phases
6. **Person remediation CTA** — link to personnel identity operations
7. **Optional:** Void/Supersede (out of pilot scope per ADR defer)

---

## 12. References

### Frontend inventory (key paths)

```text
corpsite-ui/app/directory/personnel/migration/
corpsite-ui/app/directory/personnel/_components/Migration*.tsx
corpsite-ui/app/directory/personnel/_lib/personnelMigration*.ts
corpsite-ui/app/directory/personnel/_components/ImportNormalizedRecordDrawer.tsx
```

### API consumed (unchanged)

- `GET /personnel-migration/domains`
- `POST /personnel-migration/runs/draft`
- `GET /personnel-migration/runs/{run_id}`
- `POST /personnel-migration/runs/{run_id}/items`
- `POST /personnel-migration/runs/{run_id}/commit`
- `GET /directory/personnel/import/normalized-records` (candidate source)
