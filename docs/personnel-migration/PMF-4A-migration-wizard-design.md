# PMF-4A — Migration Wizard Design

| Поле | Значение |
|------|----------|
| **Work Package** | PMF-4A |
| **Тип** | Проектирование (design only) |
| **Статус** | Draft |
| **Дата** | 2026-07-08 |
| **Зависимости** | PMF-3B (Mutation API), PMF-2 (Commit Engine), PMF-1 (Schema) |
| **Связанные ADR** | [ADR-PMF-001](../adr/ADR-PMF-001-personnel-migration-framework.md), [ADR-EDU-001](../adr/ADR-EDU-001-employee-education-migration-architecture.md), [ADR-045](../adr/ADR-045-personnel-hr-processes-split.md) |

---

## Цель документа

Спроектировать полный пользовательский процесс **Personnel Migration Wizard** — UI-оболочку, которая использует уже реализованный PMF Backend (PMF-3B) и не дублирует бизнес-логику commit на клиенте.

**В scope PMF-4A:** проектирование UX, экранов, навигации, компонентов, таблиц, commit/history UX, безопасности и разбиения реализации.

**Вне scope PMF-4A:** код, backend, frontend, migrations, изменения PMF API и Commit Engine.

---

## 1. Общая концепция

### 1.1. Назначение Wizard

**Personnel Migration Wizard** — специализированный HR-workflow для переноса данных из Import Layer (staging) в постоянные кадровые сущности (`person_*` tables). Wizard — единственная точка, через которую HR-оператор может **зафиксировать** (commit) кадровые записи по домену.

Wizard не заменяет Review (проверку staging) и не является редактором personnel records в runtime. Его роль — **контролируемый мост** между approved staging-кандидатами и source of truth.

### 1.2. Какие задачи решает

| Задача | Описание |
|--------|----------|
| **Scope selection** | Выбор домена миграции и сотрудника (operational `employee_id`) |
| **Candidate mapping** | Отображение staging-источника (`source_payload`) и целевого draft (`draft_payload`) в split-view |
| **Draft assembly** | Сборка migration run с draft items до commit |
| **Pre-commit review** | Просмотр и исправление draft до необратимой фиксации |
| **Commit orchestration** | Вызов Commit Engine с подтверждением оператора |
| **Post-commit verification** | Просмотр созданных `target_record_id`, событий, ссылок на domain tab |
| **Rollback (void)** | Компенсирующая отмена committed run через lifecycle, без DELETE |
| **Audit visibility** | История runs и `personnel_record_events` для сотрудника/домена |

### 1.3. Почему Wizard, а не обычная CRUD-форма

| CRUD-форма | Migration Wizard |
|------------|------------------|
| Прямое редактирование personnel records | Запись только через Commit Engine |
| Нет связи со staging | Явная provenance: `source_payload` → `draft_payload` → commit |
| Нет run-level audit | Каждая фиксация = `personnel_migration_run` + items |
| Сложно откатить пакет изменений | Void run откатывает все items run atomically |
| Нет review gate | Wizard принимает только approved candidates (client-side gate + Review contour) |
| Подходит для runtime edits | Подходит для **первичной миграции** и **reconciliation** (future) |

Wizard отражает архитектурный инвариант ADR-PMF-001: после commit runtime UI **не читает** Import Layer для данного домена и сотрудника.

### 1.4. Принципы проектирования

#### Review before commit

- Оператор обязан просмотреть все draft items до commit.
- Commit заблокирован UI, пока есть неразрешённые validation errors (после неудачного commit attempt).
- Подтверждение commit — явное действие с checkbox «Подтверждаю фиксацию» (паттерн `ImportEnrollEmployeeWizard`, `CatchUpRunClient`).
- Серверная валидация выполняется **только при commit** (PMF-3B); Wizard отображает результат и направляет на исправление.

#### Commit Engine как единственная точка записи

- Frontend **не вызывает** прямых API записи в `person_education`, `person_training` и др.
- Единственный write-path: `POST /personnel-migration/runs/{run_id}/commit`.
- Supersede — отдельный controlled endpoint (`POST /personnel-migration/records/supersede`), не inline edit.
- Wizard не эмулирует commit на клиенте; dry-run (если появится) — только read-only preview.

#### Rollback через lifecycle

- Отмена committed run: `POST /personnel-migration/runs/{run_id}/void` с обязательным `void_reason`.
- Backend устанавливает `lifecycle_status = voided` на personnel records; физический DELETE запрещён.
- UI объясняет последствия void до подтверждения (amber warning, reason field).
- Supersede — для точечной замены одной записи, не для batch rollback.

#### Import Layer = staging only

- `source_payload`, `import_batch_id`, `import_row_id` — read-only references на staging.
- Wizard отображает staging слева; редактируется только `draft_payload` справа.
- После commit runtime domain tabs читают personnel tables, не ImportProfile/staging JSONB.
- Marking staging as `migrated` — ответственность backend (future PMF phase); Wizard не пишет в staging.

### 1.5. Архитектурный контекст

```text
Import Layer (staging)          PMF Backend (PMF-3B)              Personnel SoT
─────────────────────          ─────────────────────              ───────────────
hr_import_*          ──read──►  Migration Wizard UI  ──API──►   personnel_migration_*
Review (approve)     ──gate──►  draft run + items    ──commit──► person_education
ImportProfile        ──ref───►  Commit Engine        ──events──► personnel_record_events
```

---

## 2. Пользовательский сценарий

### 2.1. Общий workflow

```text
Выбор домена
      ↓
Выбор сотрудника / контекста
      ↓
Создание Migration Run (draft)
      ↓
Добавление items (из candidates или manual)
      ↓
Mapping / редактирование draft_payload
      ↓
Pre-commit review (просмотр run)
      ↓
Commit (confirm=true)
      ↓
  ┌─── успех ───► Просмотр результата + record events
  │
  └─── 422 ─────► Просмотр item_errors → исправление draft → повтор commit
      ↓
(опционально) Void run
      ↓
История runs / events
```

### 2.2. Детализация шагов

#### Шаг 1 — Выбор домена

| Аспект | Описание |
|--------|----------|
| **Цель** | Определить domain plugin (education, certificates, …) |
| **Действия пользователя** | Открыть Migration Home; выбрать домен из списка enabled domains |
| **API** | `GET /personnel-migration/domains` |
| **Ошибки** | **403** — нет HR import admin; **401** — не авторизован; домен `is_enabled=false` — карточка disabled с пояснением |

#### Шаг 2 — Выбор сотрудника

| Аспект | Описание |
|--------|----------|
| **Цель** | Привязать migration session к operational `employee_context_id` |
| **Действия пользователя** | Поиск/выбор сотрудника; переход в wizard session; (future) фильтр по batch |
| **API** | Существующий Directory API для employee lookup; deep link `?employee_id=` |
| **Ошибки** | Сотрудник без `person_id` — блокировка создания draft run (**422** на `POST /runs/draft`) |

#### Шаг 3 — Создание Migration Run

| Аспект | Описание |
|--------|----------|
| **Цель** | Открыть draft session для domain + employee |
| **Действия пользователя** | Нажать «Начать миграцию»; Wizard создаёт run или возобновляет существующий draft (client policy: один active draft per domain+employee) |
| **API** | `POST /personnel-migration/runs/draft` — `{ domain_code, employee_context_id, metadata? }` |
| **Ошибки** | **404** — employee not found; **422** — `person_id` missing, domain disabled; **403/401** — auth |

#### Шаг 4 — Добавление items

| Аспект | Описание |
|--------|----------|
| **Цель** | Сформировать набор draft items для commit |
| **Действия пользователя** | Выбрать approved candidates из staging (client-side resolver через Import/Review APIs); или «Добавить вручную» (manual `source_kind`); для каждого — mapping в `draft_payload` |
| **API** | `POST /personnel-migration/runs/{run_id}/items` — `AddDraftItemRequest`; `GET /personnel-migration/runs/{run_id}` — refresh |
| **Ошибки** | **409** — run не в статусе `draft`; **404** — run not found; **422** — domain validation at item level (partial, если добавлено в future) |

**Примечание PMF-3B:** update/delete draft item endpoints **не реализованы**. Исправление — повторное добавление item с корректным payload или пересоздание run (client policy документируется в PMF-4C).

#### Шаг 5 — Mapping / редактирование

| Аспект | Описание |
|--------|----------|
| **Цель** | Заполнить domain-specific поля `draft_payload` на основе staging |
| **Действия пользователя** | Split-view: слева `source_payload`, справа domain form; Accept / Skip / Save (local state until add item) |
| **API** | Локальное состояние + `POST .../items` при сохранении item; `GET .../runs/{run_id}` для reload |
| **Ошибки** | Client-side required field hints (domain plugin metadata); server validation deferred to commit |

#### Шаг 6 — Pre-commit review

| Аспект | Описание |
|--------|----------|
| **Цель** | Финальный просмотр всех items перед commit |
| **Действия пользователя** | Просмотр Items Grid; проверка summary (N items, domain, employee); переход к Commit Confirmation |
| **API** | `GET /personnel-migration/runs/{run_id}` |
| **Ошибки** | 0 items — commit disabled (client guard + server **422** «no draft items») |

#### Шаг 7 — Commit

| Аспект | Описание |
|--------|----------|
| **Цель** | Транзакционная фиксация всех draft items |
| **Действия пользователя** | Checkbox confirm; кнопка «Зафиксировать»; progress indicator |
| **API** | `POST /personnel-migration/runs/{run_id}/commit` — `{ confirm: true }` |
| **Ошибки** | **422** — validation errors per item (`{ message, items: [{ item_id, validation_errors }] }`); **409** — run already committed / not draft; **404** — run not found |

#### Шаг 8 — Просмотр ошибок и исправление

| Аспект | Описание |
|--------|----------|
| **Цель** | Устранить validation errors после failed commit |
| **Действия пользователя** | Items Grid подсвечивает failed items; открыть item detail; исправить `draft_payload`; (workaround PMF-3B) добавить новый item или пересоздать run |
| **API** | `GET /personnel-migration/runs/{run_id}` — `validation_errors` на items |
| **Ошибки** | Persisted `validation_errors` на item до успешного commit |

#### Шаг 9 — Просмотр результата

| Аспект | Описание |
|--------|----------|
| **Цель** | Подтвердить успешную фиксацию |
| **Действия пользователя** | Commit Result screen: run status `committed`, список `committed_items` с `target_record_id`, links to record events |
| **API** | Response `CommitRunResponse`; `GET /personnel-migration/runs/{run_id}/record-events` |
| **Ошибки** | — |

#### Шаг 10 — Void (опционально)

| Аспект | Описание |
|--------|----------|
| **Цель** | Откат committed run |
| **Действия пользователя** | На Run Details: «Отменить run» → reason → confirm |
| **API** | `POST /personnel-migration/runs/{run_id}/void` — `{ void_reason }` |
| **Ошибки** | **409** — run not committed / already voided; **422** — empty reason |

#### Шаг 11 — Supersede (опционально, вне run)

| Аспект | Описание |
|--------|----------|
| **Цель** | Заменить одну active personnel record |
| **Действия пользователя** | Из Run Details или domain context: выбрать record → replacement form → confirm |
| **API** | `POST /personnel-migration/records/supersede` |
| **Ошибки** | **404** — record not found; **409** — record not active; **422** — validation |

#### Шаг 12 — История

| Аспект | Описание |
|--------|----------|
| **Цель** | Audit trail для сотрудника/домена/run |
| **Действия пользователя** | History tab / side rail; фильтр по domain, run, event type |
| **API** | `GET /personnel-migration/record-events?employee_context_id=&domain_code=`; `GET /personnel-migration/runs/{run_id}/record-events`; `GET /personnel-migration/runs/{run_id}` |
| **Ошибки** | **422** — list record-events без обязательного filter param |

### 2.3. Типовые API-последовательности

**Bootstrap (education pilot):**

```text
1. GET  /personnel-migration/domains
2. POST /personnel-migration/runs/draft
3. POST /personnel-migration/runs/{id}/items  (×N)
4. GET  /personnel-migration/runs/{id}
5. POST /personnel-migration/runs/{id}/commit
6. GET  /personnel-migration/runs/{id}/record-events
```

**Void rollback:**

```text
1. GET  /personnel-migration/runs/{id}
2. POST /personnel-migration/runs/{id}/void
3. GET  /personnel-migration/runs/{id}/record-events
```

---

## 3. Экранная модель

### 3.1. Состав экранов

| # | Экран | Route (planned) |
|---|-------|-----------------|
| 1 | Migration Home | `/directory/personnel/migration` |
| 2 | Domain Selection | (embedded in Home or `/migration/{domain}`) |
| 3 | Employee / Candidates | `/directory/personnel/migration/{domain}/candidates` |
| 4 | Draft Run (Wizard Session) | `/directory/personnel/migration/{domain}/{employeeId}` |
| 5 | Items Grid | (zone within Draft Run + dedicated review step) |
| 6 | Item Detail (Split-view) | (drawer/panel within Draft Run) |
| 7 | Validation / Pre-commit Review | (step within Draft Run) |
| 8 | Commit Confirmation | (modal or step) |
| 9 | Commit Result | (step or `/runs/{runId}?step=result`) |
| 10 | History | (tab on Home + side rail on session) |
| 11 | Run Details | `/directory/personnel/migration/runs/{runId}` |

### 3.2. Migration Home

**Назначение:** точка входа в PMF; dashboard по доменам.

**Элементы UI:**
- Заголовок «Миграция кадровых данных»
- Карточки доменов (`display_name`, `description`, `is_enabled`, `target_table_names`)
- Счётчики (future): pending candidates, recent runs
- Ссылка на History
- Info banner: «Commit — единственная точка записи в кадровую карточку»

**Действия:**
- Выбрать домен → Employee/Candidates
- Открыть Run Details (recent runs list — future API `GET /runs`)
- Перейти в Import Review (cross-link)

### 3.3. Domain Selection

**Назначение:** подтверждение domain context перед выбором сотрудника.

**Элементы UI:**
- Domain header (icon, name, control list columns)
- Prerequisites checklist: domain enabled, Review contour available
- Кнопка «Выбрать сотрудника»

**Действия:**
- Continue → Candidates
- Back → Home

### 3.4. Employee / Candidates

**Назначение:** выбор сотрудника и просмотр approved candidates (client-resolved из Import Layer).

**Элементы UI:**
- Employee search (reuse `TargetSearchField` pattern)
- Employee summary: ФИО, tab №, `person_id` status badge
- Candidates table (pre-run): source_text, review_status, record_kind, confidence
- Batch filter (optional)
- CTA «Начать миграцию»

**Действия:**
- Select employee
- Select candidates (multi)
- Start draft run → Wizard Session
- Deep link from Review: `?employee_id=&candidate_id=`

### 3.5. Draft Run (Wizard Session)

**Назначение:** основная рабочая область; split-view shell по ADR-PMF-001 §4.3.

**Элементы UI:**

| Зона | Содержание |
|------|------------|
| **Header** | Employee, domain, run_id, run_status badge, mode (bootstrap/manual) |
| **Workflow stepper** | Scope → Items → Review → Commit → Result |
| **Left panel** | `source_payload`: source_text, column, parse_method, confidence, review meta |
| **Right panel** | Domain form slot (Education first) |
| **Items Grid** | Compact list of added items |
| **Footer** | Accept item, Skip, Add to run, Go to review, Commit |
| **Side rail** | Run history for employee+domain (record-events snippet) |

**Действия:**
- Add/edit items
- Navigate steps
- Open Item Detail drawer
- Commit (when on review step)

### 3.6. Items Grid

**Назначение:** tabular overview всех items run (см. §6).

**Элементы UI:**
- Filter: status, record_kind, has errors
- Bulk select (future: skip/remove when API available)
- Row actions: Open detail, Remove (future)

**Действия:**
- Sort/filter
- Open item in split-view
- Navigate to validation summary

### 3.7. Validation / Pre-commit Review

**Назначение:** финальная проверка перед commit.

**Элементы UI:**
- Summary tiles: total items, by record_kind, error count
- Items Grid (read-only mode with error highlights)
- Warning if `person_id` missing (should not reach here)
- Button «Перейти к подтверждению»

**Действия:**
- Fix errors → back to mapping
- Proceed to Commit Confirmation

### 3.8. Commit Confirmation

**Назначение:** explicit consent before irreversible commit.

**Элементы UI:**
- Amber warning panel
- Run summary: domain, employee, N items
- Checkbox «Подтверждаю фиксацию N записей»
- Primary button «Зафиксировать» (disabled until checked)
- Cancel

**Действия:**
- Confirm → commit API
- Cancel → back to review

### 3.9. Commit Result

**Назначение:** success/failure feedback после commit attempt.

**Элементы UI (success):**
- Green success banner
- `committed_items` table: item_id → target_table → target_record_id → event_id
- Links: Run Details, Record Events, (future) Education tab
- Next steps panel (pattern `EnrollmentCompletionPanel`)

**Элементы UI (validation failure):**
- Red error banner with `message`
- Per-item error list from 422 response
- CTA «Исправить ошибки»

**Действия:**
- View run details
- Void run (if needed, from Run Details)
- Start new run

### 3.10. History

**Назначение:** audit visibility across runs and business events.

**Элементы UI:**
- Tabs: «Runs» (future list API), «Record Events»
- Filters: domain, employee, event_type, date range
- Events table: event_type badge, record, actor, timestamp, payload expand

**Действия:**
- Open Run Details
- Open record event detail (`GET /record-events/{event_id}`)
- Export (future, out of scope PMF-4)

### 3.11. Run Details

**Назначение:** read-only audit view committed/voided run.

**Элементы UI:**
- Run metadata panel (status, actors, timestamps, void_reason)
- Items table with full lifecycle
- Record events for run
- Actions: Void (if committed), Supersede item (navigate)

**Действия:**
- Void with reason
- Navigate to employee wizard
- View JSON audit (`JsonViewer`)

---

## 4. Навигация

### 4.1. Размещение Wizard

Wizard размещается в **HR operational contour** (ADR-045):

- Base path: `/directory/personnel/migration/**`
- Layout: `PersonnelLayoutShell` + `PersonnelSectionHeader`
- Sub-nav: новая вкладка **«Миграция»** в `PersonnelSubNav` (после Import или рядом с HR Change Events)

### 4.2. Маршруты

```text
/directory/personnel/migration
  ├── index                              # Migration Home
  ├── [domainCode]/
  │     ├── candidates                   # Employee + candidates picker
  │     └── [employeeId]                 # Wizard session (draft run)
  └── runs/
        └── [runId]                      # Run Details (audit)
```

Query parameters:

| Param | Usage |
|-------|-------|
| `employee_id` | Pre-select employee (from Review CTA) |
| `candidate_id` | Pre-select candidate in session |
| `batch_id` | Filter candidates by import batch |
| `step` | Wizard step override (`review`, `commit`, `result`) |
| `run_id` | Resume existing draft run |

### 4.3. Breadcrumb

Inline pattern (как `UserLinkageOperationsClient`):

```text
Кадровые процессы / Миграция / {domain_display_name} / {employee_name}
Кадровые процессы / Миграция / Run #{run_id}
```

### 4.4. Возвраты и guard rails

| From | Back action | Behavior |
|------|-------------|----------|
| Wizard session | «К списку кандидатов» | Confirm if unsaved local mapping |
| Commit Confirmation | «Назад к review» | Preserve run state |
| Commit Result | «Новая миграция» | Home or same employee |
| Run Details (draft) | «Продолжить редактирование» | `/migration/{domain}/{employeeId}?run_id=` |
| Run Details (committed) | Read-only; no edit | Void only |

**Unsaved changes:** client-side dirty flag on mapping form; `beforeunload` warning optional.

### 4.5. Deep links

| Source | Target |
|--------|--------|
| Import Review CTA | `/directory/personnel/migration/{domain}?employee_id={id}&candidate_id={key}` |
| Employee Import Card | `/directory/personnel/migration/education/{employeeId}` |
| Commit Result | `/directory/personnel/migration/runs/{runId}` |
| Record event | `/directory/personnel/migration/runs/{migration_run_id}` (if linked) |
| Personnel Lifecycle (future cross-link) | Run Details by run_id |

### 4.6. Access guard

Page-level guard (pattern `PersonnelLifecyclePageClient`):

1. Fetch `GET /auth/me`
2. Require `canSeeHrProcessesNav(me)` for shell access
3. Require HR import admin capability for API calls (mirror `require_hr_import_admin_or_403`)
4. Redirect to `/tasks` or show forbidden panel

---

## 5. UI-компоненты

### 5.1. Переиспользование из существующего UI

| Компонент | Path | Применение в Wizard |
|-----------|------|---------------------|
| `PersonnelLayoutShell` | `corpsite-ui/app/directory/personnel/_components/` | HR contour wrapper |
| `PersonnelSubNav` | same | + tab «Миграция» |
| `PersonnelSectionHeader` | same | Page titles |
| `ImportEnrollEmployeeWizard` | `.../ImportEnrollEmployeeWizard.tsx` | Step flow, confirm checkbox, provenance |
| `CatchUpRunClient` / `WorkflowStepper` | `app/admin/regular-tasks/catch-up/` | Pill stepper UI |
| `ImportFieldDiffPanel` | import components | Split-view staging vs target |
| `FieldDiffList` | `app/admin/system/_components/shared/` | Compact field comparison |
| `ProvenanceChain` | wizard/enrollment | Source provenance display |
| `ConfirmDialog` | admin shared | Void, destructive confirm |
| `ErrorBanner` / `SuccessBanner` / `InfoBanner` | admin shared | Feedback |
| `JsonViewer` | admin shared | Audit payload debug |
| `TargetSearchField` | admin shared | Employee search |
| `LifecycleRunsTable` | personnel-lifecycle | Runs history table pattern |
| `EnrollmentCompletionPanel` | import | Post-commit next steps |
| Badge pattern | `PersonnelOrderStatusBadge`, etc. | Run/item status badges |

### 5.2. Новые компоненты (PMF-4 implementation)

| Комponent | Responsibility |
|-----------|----------------|
| `MigrationWizardShell` | Split layout: header / left / right / footer / side rail |
| `MigrationWorkflowStepper` | Domain-agnostic step indicator |
| `MigrationDomainCard` | Home domain picker card |
| `MigrationCandidatesTable` | Pre-run candidate list |
| `MigrationItemsGrid` | Run items table (§6) |
| `MigrationItemDetailDrawer` | Split-view item editor |
| `MigrationRunHeader` | Employee + domain + run status |
| `MigrationCommitPanel` | Confirm + progress + result |
| `MigrationVoidDialog` | Void reason + confirm |
| `MigrationSupersedeForm` | Replacement payload form |
| `MigrationRecordEventsTable` | Business events list |
| `MigrationRunDetailPanel` | Run audit view |
| `PersonnelProvenancePanel` | Shared provenance reader (ADR §4.6) |
| `EducationMigrationForm` | Domain plugin form slot (pilot) |
| `personnelMigrationApi.client.ts` | Typed API client |
| `personnelMigrationLabels.ts` | Status/domain/event labels |

### 5.3. Domain form slot (plugin UI pattern)

```text
MigrationWizardShell
  └── rightPanel={
        <DomainFormSlot domainCode={domain}>
          {domain === 'education' && <EducationMigrationForm ... />}
          {domain === 'certificates' && <CertificatesMigrationForm ... />}  // future
        </DomainFormSlot>
      }
```

Domain form получает: `record_kind`, `draft_payload`, `onChange`, `validationErrors`, `readOnly`.

---

## 6. Таблица Migration Items

### 6.1. Колонки

| Column | Source field | Visibility | Notes |
|--------|--------------|------------|-------|
| # | row index | always | |
| Status | `item_status` | always | Badge (§6.2) |
| Record kind | `record_kind` | always | Domain-specific label |
| Source | `source_kind` + `source_record_id` | always | Icon by source_kind |
| Source preview | `source_payload.source_text` | always | Truncated, tooltip full |
| Target summary | `draft_payload` key fields | draft | Domain-specific (e.g. institution_name) |
| Target record | `target_table_name` / `target_record_id` | post-commit | Link to record |
| Validation | `validation_errors.length` | when > 0 | Error count badge |
| Import ref | `import_batch_id` / `import_row_id` | optional column | Link to import review |
| Timestamps | `created_at`, `committed_at`, `voided_at` | Run Details | |
| Actions | — | always | Open, (future Remove) |

### 6.2. Статусы items

| `item_status` | Label (RU) | Badge color | Meaning |
|---------------|------------|-------------|---------|
| `draft` | Черновик | zinc/gray | В run, не зафиксирован |
| `committed` | Зафиксирован | emerald/green | Запись создана в person_* |
| `voided` | Отменён | amber/orange | Rollback через void run |
| `superseded` | Заменён | blue | Заменён через supersede |
| `failed` | Ошибка | red | Reserved; commit failure |

### 6.3. Валидация в таблице

| State | Visual |
|-------|--------|
| No errors, draft | Normal row |
| Has `validation_errors` | Red left border; error icon in Validation column |
| Selected for edit | Blue highlight |
| Committed success | Green subtle background |
| Voided | Strikethrough on target summary; muted text |

Row expand (optional): inline list of `validation_errors` strings.

### 6.4. Цветовые состояния (run-level overlay)

| Run status | Grid behavior |
|------------|---------------|
| `draft` | Editable actions enabled |
| `committed` | Read-only; show target columns |
| `voided` | Read-only; all items voided styling |
| `failed` | Error banner above grid |

### 6.5. Массовые операции

| Operation | PMF-4A design | PMF-3B support |
|-----------|---------------|----------------|
| Select all draft | UI checkbox column | — |
| Add selected candidates | Batch `POST .../items` | Sequential API calls |
| Remove selected | **Future** — no delete endpoint | Not in PMF-3B |
| Skip candidate | Don't add item | Client-only |
| Re-validate all | Re-fetch run after failed commit | `GET .../runs/{id}` |

**PMF-4A policy:** bulk remove deferred to future API (PMF-3C+); pilot uses single-item add flow.

---

## 7. Commit UX

### 7.1. Validation errors (pre-commit, client hints)

- Domain form shows required field markers (`education_kind`, `training_kind`, etc.)
- Items Grid shows error count = 0 until server commit attempt
- No server-side dry-run in PMF-3B; client hints are advisory only

### 7.2. Validation errors (post-commit 422)

**Display pattern:**

```text
┌─ ErrorBanner ─────────────────────────────────────┐
│ Не удалось зафиксировать: validation failed         │
└─────────────────────────────────────────────────────┘

Items Grid:
  Row 3  [ERROR]  education  «education_kind is required»
  Row 7  [ERROR]  training   «training_kind is required»

[Исправить] → opens Item Detail for first error item
```

**Data mapping:** `HTTP 422 detail.items[]` → `{ item_id, validation_errors: string[] }` → merge into grid row state + persist from `GET run` (`item.validation_errors`).

### 7.3. Commit progress

| Phase | UI |
|-------|-----|
| Idle | Button «Зафиксировать» enabled after checkbox |
| Submitting | Button disabled; spinner «Фиксация…»; block navigation |
| Success | Transition to Commit Result step |
| Failure (422) | Stay on confirmation; show errors; enable «Исправить» |
| Failure (409/500) | ErrorBanner with message; retry allowed for transient errors |

No WebSocket/polling — single request/response (PMF-3B commit is synchronous TX).

### 7.4. Commit completed

**Success panel contents:**
- Run ID, committed_at, committed_by
- Table `committed_items`: item_id → table → record_id → event_id
- Event count summary
- Provenance note: «Записи созданы с lifecycle_status=active»
- CTAs: Run Details, Record Events, (future) открыть вкладку «Образование»

### 7.5. Void UX

**Entry points:** Run Details (committed runs only)

**Flow:**
1. Button «Отменить run» (destructive, amber)
2. `ConfirmDialog` + required `void_reason` textarea (min 1 char)
3. Warning: «Все N записей получат lifecycle_status=voided. Физическое удаление не выполняется.»
4. Submit → `POST .../void`
5. Success → run status `voided`; items voided styling; new void events in history

**Errors:**
- **409** — «Run уже отменён» / «Run не в статусе committed»
- Show void_reason in Run Details after success

### 7.6. Supersede UX

**Context:** standalone operation, not part of run commit flow.

**Flow:**
1. Select active record (from Run Details committed item link or future domain tab)
2. Open Supersede form (replacement `draft_payload` + provenance)
3. Confirm dialog: «Текущая запись будет помечена superseded»
4. Submit → `POST /records/supersede`
5. Result: old record superseded, new record active; two events (`*_SUPERSEDED`, `*_MIGRATED`)

**Visual:** superseded records in history with blue badge; link old → new record IDs.

---

## 8. История

### 8.1. Три слоя audit

| Layer | Source | Audience | UI location |
|-------|--------|----------|-------------|
| **Business events** | `personnel_record_events` | HR, domain owners | History tab, side rail |
| **Technical run audit** | `personnel_migration_runs` + `items` | HR admin, DevOps | Run Details |
| **Import audit** | `hr_import_*` | Import operators | Cross-link to Import Review |

PMF-4A фокус: business events + run audit. Import audit — cross-link only.

### 8.2. personnel_record_events

**API:**
- By run: `GET /personnel-migration/runs/{run_id}/record-events`
- By employee: `GET /personnel-migration/record-events?employee_context_id=&domain_code=`
- By person: `?person_id=`
- Single: `GET /personnel-migration/record-events/{event_id}`

**Table columns:**

| Column | Field |
|--------|-------|
| Event | `event_type` badge |
| When | `event_at` |
| Who | `actor_id` |
| Record | `record_table_name` #`record_id` |
| Domain | `domain_code` |
| Run link | `migration_run_id` (if set) |
| Payload | `event_payload` expand (JsonViewer) |

**Education event types (PMF-3B):**
- `EDUCATION_MIGRATED` — commit / supersede replacement
- `EDUCATION_VOIDED` — void run
- `EDUCATION_SUPERSEDED` — supersede old record

### 8.3. Run history

**Current gap:** `GET /personnel-migration/runs?domain=&employee_id=` **не реализован** в PMF-3B.

**PMF-4A design (client workarounds until PMF-3C):**
- Side rail: store `run_id` in session/local recent list after create/commit
- Run Details as primary history entry point via deep link
- Future: runs list table (pattern `LifecycleRunsTable`)

**Run Details audit fields:**
- `started_at/by`, `committed_at/by`, `voided_at/by/reason`
- Per-item: source → target mapping, validation_errors history, void_reason

### 8.4. Side rail (Wizard Session)

Compact timeline for current employee + domain:
- Last 5 record events (newest first)
- Link «Вся история» → History tab
- Highlight current run if active

---

## 9. Безопасность

### 9.1. Роли и доступ

| Actor | Shell access | Wizard API access |
|-------|--------------|-------------------|
| System admin (`role_id=2`) | ✅ HR contour | ✅ |
| Privileged operator | ✅ | ✅ |
| HR enrollment manager (`has_personnel_admin`) | ✅ | ✅ |
| Personnel visibility (E1 read-only) | ❌ HR contour | ❌ |
| Regular user | ❌ | ❌ |

### 9.2. Backend permission check

Все PMF routes используют:

```python
require_hr_import_admin_or_403(user)
```

(`app/directory/rbac.py`) — allows privileged operator OR personnel admin (HR enrollment manager).

### 9.3. Действия по уровням

| Action | Required permission |
|--------|---------------------|
| View Migration Home | `canSeeHrProcessesNav` |
| List domains | HR import admin |
| Create draft run | HR import admin |
| Add items | HR import admin |
| Commit | HR import admin |
| Void | HR import admin |
| Supersede | HR import admin |
| View record events | HR import admin |
| View Run Details | HR import admin |

### 9.4. Frontend permission pattern

1. **Shell gate:** `AppShell` + HR contour routes
2. **Page gate:** fetch `/auth/me`; redirect if `!canSeeHrProcessesNav(me)`
3. **API gate:** handle **403** with «Недостаточно прав для миграции кадровых данных»
4. **Feature flag:** `GET /domains` → hide/disable domains with `is_enabled=false`

### 9.5. Дополнительные ограничения

| Constraint | Enforcement |
|------------|-------------|
| `employees.person_id` required | Server **422** at draft create; client pre-check on employee select |
| Domain enabled | Server check + UI disabled card |
| Pilot allowlist (future `run_mode=pilot`) | Deferred; use `metadata.pilot=true` + client guard until backend guard exists |
| No cross-employee run access | Run scoped to `employee_context_id`; UI validates on load |

---

## 10. Future plugins

### 10.1. Универсальность Wizard

Wizard спроектирован как **domain-agnostic shell**. Domain-specific поведение изолировано в:

1. **Domain registry** — `GET /domains` (display_name, target_table_names, control_list_columns)
2. **Domain form slot** — right panel UI component per plugin
3. **Domain plugin backend** — `validate_draft`, `write_records`, event types (PMF-2)

Изменение shell, navigation, commit UX, history, void/supersede flow **не требуется** при добавлении нового домена.

### 10.2. Планируемые domain plugins

После Education (pilot) тот же Wizard поддержит без архитектурных изменений:

| Domain code | Target tables | Notes |
|-------------|---------------|-------|
| `education` | `person_education`, `person_training` | PMF-4G pilot |
| `certificates` | `person_certificates` (future) | New form slot |
| `qualifications` | TBD | |
| `work_history` / `service_record` | `person_work_history` (future) | Timeline layout variant |
| `awards` | TBD | Multi-record from profile fragments |
| `scientific_degrees` | TBD | |
| `languages` | TBD | |
| `categories` | TBD | |
| Any future PMF plugin | Per registry | Register in `personnel_migration_domains` + implement plugin |

### 10.3. Что меняется per domain

| Layer | Domain-specific |
|-------|-----------------|
| Candidates resolver | Source fields, record_kind enum |
| Right panel form | Fields, validators (client hints) |
| Items Grid | Target summary column formatter |
| Record events | `event_type` labels |
| Control list columns | From domain registry |

### 10.4. Что остаётся shared

- MigrationWizardShell, stepper, commit/void/supersede UX
- Run/items lifecycle UI
- History / record events tables
- API client structure
- Permission model

---

## 11. Out of scope

Следующее **явно не реализуется** в рамках PMF-4 (включая PMF-4A design phase — только документ):

| Item | Notes |
|------|-------|
| Frontend code | PMF-4B–4G |
| React pages / components | Separate WPs |
| Backend changes | PMF-3C+ if needed |
| PMF API extensions | e.g. list runs, update/delete items |
| Commit Engine changes | PMF-2 frozen for 4.x |
| Database migrations | — |
| File import | Wizard consumes Review output; no CSV/Excel upload |
| Mass migration / batch jobs | Single employee session per run |
| Background jobs / scheduler | Synchronous commit only |
| Reconciliation diff engine | PMF-6 |
| Candidate resolver API | Client uses Import/Review APIs |
| Staging `mark_migrated` wiring | Future commit engine enhancement |
| Control list generator | PMF-9 |
| Education domain tab (read UI) | Separate WP |
| Dry-run preview endpoint | Client hints only in PMF-4 |
| Export / reporting | Future |

---

## 12. Реализация — разбиение PMF-4

Рекомендуемое разбиение PMF-4 на небольшие Work Packages после утверждения PMF-4A.

### PMF-4B — Navigation + Shell

**Scope:**
- Routes scaffold under `/directory/personnel/migration/**`
- `PersonnelSubNav` tab «Миграция»
- Page guards (`canSeeHrProcessesNav`, 403 handling)
- `MigrationWizardShell` layout (empty slots)
- `personnelMigrationApi.client.ts` — domains + auth error mapping
- `personnelMigrationLabels.ts` — run/item status labels
- Migration Home with domain cards (`GET /domains`)

**Deliverable:** navigable empty shell; domain list works.

**Depends on:** PMF-4A ratified.

---

### PMF-4C — Draft Run UI

**Scope:**
- Employee search + select
- `POST /runs/draft` integration
- Run header (status, employee, domain)
- `MigrationWorkflowStepper` (Scope → Items → Review → Commit → Result)
- Session route `/migration/{domain}/{employeeId}`
- Deep links: `?employee_id=`, `?run_id=`
- `person_id` missing blocker

**Deliverable:** operator can create draft run and navigate steps.

**Depends on:** PMF-4B.

---

### PMF-4D — Items Grid + Split-view Mapping

**Scope:**
- `MigrationCandidatesTable` (client-resolved from Import/Review APIs)
- `POST /runs/{id}/items`
- `MigrationItemsGrid` (§6)
- `MigrationItemDetailDrawer` — split-view (`ImportFieldDiffPanel` pattern)
- `EducationMigrationForm` (pilot domain form)
- `PersonnelProvenancePanel`
- Local mapping state + add-to-run flow

**Deliverable:** operator can add education/training items to draft run.

**Depends on:** PMF-4C.

**Note:** candidate resolver — client integration with existing Import APIs; document contract in PMF-4D spec.

---

### PMF-4E — Commit UI

**Scope:**
- Pre-commit review step
- `MigrationCommitPanel` — confirm checkbox, submit, progress
- 422 error display + item error merge
- Commit Result step
- `MigrationVoidDialog` on Run Details
- `MigrationSupersedeForm` (basic)

**Deliverable:** full draft → commit → result → void cycle works for education.

**Depends on:** PMF-4D.

---

### PMF-4F — History UI

**Scope:**
- `MigrationRecordEventsTable`
- `MigrationRunDetailPanel` — `/runs/{runId}`
- Side rail events snippet
- History tab on Home
- `GET /record-events` filters
- Recent runs local cache (until list runs API)

**Deliverable:** audit visibility for committed/voided runs.

**Depends on:** PMF-4E.

---

### PMF-4G — Pilot (Education)

**Scope:**
- End-to-end pilot checklist
- Review → Migration CTA link
- Employee Import Card → Migration link
- Domain `education` enablement runbook
- Pilot operator docs
- UX polish: labels, empty states, error messages RU
- Feedback template integration

**Deliverable:** HR operator can migrate approved education candidates for pilot employees.

**Depends on:** PMF-4F.

---

### Optional future WPs (not PMF-4)

| WP | Scope |
|----|-------|
| PMF-3C | API: list runs, update/delete draft items |
| PMF-4H | Reconciliation mode UI (after PMF-6) |
| PMF-4I | Second domain plugin UI (certificates) |

### Suggested timeline dependency graph

```text
PMF-4A (design) ──► PMF-4B ──► PMF-4C ──► PMF-4D ──► PMF-4E ──► PMF-4F ──► PMF-4G (pilot)
```

---

## Appendix A — PMF-3B API reference (implemented)

| Method | Route |
|--------|-------|
| GET | `/personnel-migration/domains` |
| POST | `/personnel-migration/runs/draft` |
| GET | `/personnel-migration/runs/{run_id}` |
| POST | `/personnel-migration/runs/{run_id}/items` |
| POST | `/personnel-migration/runs/{run_id}/commit` |
| POST | `/personnel-migration/runs/{run_id}/void` |
| GET | `/personnel-migration/runs/{run_id}/record-events` |
| GET | `/personnel-migration/record-events` |
| GET | `/personnel-migration/record-events/{event_id}` |
| POST | `/personnel-migration/records/supersede` |

## Appendix B — Known PMF-3B gaps (Wizard workarounds)

| Gap | Wizard workaround | Future WP |
|-----|-------------------|-----------|
| No list runs API | Session recent list + deep links | PMF-3C |
| No update/delete draft item | Re-add item / recreate run | PMF-3C |
| No candidate resolver API | Import/Review client integration | PMF-5 |
| No dry-run endpoint | Client required-field hints | PMF-3C |
| No staging mark_migrated | Informational only post-commit | PMF-2 enhancement |
| Domain `is_enabled=false` by default | Enable for pilot via admin/seed | PMF-4G runbook |
| `run_mode` not in schema | Store in `metadata` | PMF-3C |

---

## Appendix C — Ratification checklist

- [ ] UX workflow reviewed by HR operator representative
- [ ] Split-view layout aligned with ADR-PMF-001 §4.3
- [ ] Permission model confirmed with ADR-045 / RBAC
- [ ] PMF-4B–4G scope approved
- [ ] Pilot entry criteria defined (PMF-4G)
- [ ] Document status → **Ratified**
