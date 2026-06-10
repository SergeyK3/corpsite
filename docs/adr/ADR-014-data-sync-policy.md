# ADR-014 — Data Sync Policy

## Статус

Принято (Accepted)

## Дата

2026-06-10

## Контекст

VPS (`/opt/projects/corpsite/app`, `46.247.42.47`) стал основной pilot/prod-средой Corpsite.

Локальная БД исторически содержит более полный справочник организационных данных:

| Сущность | Local (исторически) | VPS (pilot/prod, 2026-06-10) |
|----------|--------------------:|-----------------------------:|
| `positions` | 96 | 1 |
| `employees` | 37 | 6 |
| `users` | 39 | 7 |

VPS содержит актуальные pilot/prod-данные, которых нет или нет в полном виде на local:

- пользователи пилота (`qm_*@corp.local`, `admin`);
- `users.telegram_id` (3 привязки);
- `regular_tasks` (2 шаблона QM pilot);
- `tasks`, `task_reports` (операционный след);
- `task_events`, `task_event_deliveries` (43 delivery records);
- `task_audit_log`, `regular_task_runs`.

До настоящего момента синхронизация между средами выполнялась вручную (SQL bootstrap, seed scripts) без формальной политики. Это создаёт риск:

- перезаписи prod-данных справочником из local;
- утечки `password_hash` / `telegram_id` через GitHub или незашифрованные каналы;
- row-level sync операционных таблиц с коллизией surrogate ID;
- расхождения `role_id` / `unit_id` между средами.

Настоящий ADR фиксирует **политику синхронизации данных** между local, VPS (prod/pilot) и future hosting.

Связанные документы:

- ADR-031 — Directory contract (сущности справочника)
- ADR-022 — Events delivery queue (operational SoT)
- `README_DEPLOY.md` — backup-before-deploy

---

## Rationale (обоснование)

1. **VPS — живая prod/pilot-среда.** Operational и auth-данные уже существуют только на VPS. Любой импорт с local не должен их затрагивать.

2. **Local — исторический master справочников**, но не операционных данных. После one-time alignment справочников local перестаёт быть равноправным источником истины.

3. **Surrogate ID на prod священны.** Pilot завязан на конкретные `unit_id`, `role_id`, `user_id`. При merge нельзя переназначать prod ID — только дополнять и обновлять атрибуты по natural key.

4. **Row-level sync операционных таблиц опасен.** `task_id`, `audit_id` и delivery trail не имеют стабильных natural keys между средами. Cross-env sync приведёт к дублям и потере audit integrity.

5. **New hosting — cutover, не patch.** Полный `pg_dump` / `pg_restore` сохраняет FK-целостность, sequences, auth и operational trail в одной атомарной операции.

6. **Безопасность персональных данных.** CSV/SQL с PII и secrets не проходят через GitHub. Transfer — только по защищённым каналам.

---

## Решение

### Принятые архитектурные решения

| # | Решение | Формулировка |
|---|---------|--------------|
| 1 | **org_units** | Merge by `code`; **preserve prod `unit_id`** при совпадении code |
| 2 | **employees** | **Delta import only** — только отсутствующие в VPS записи |
| 3 | **contacts** | **Отдельная фаза** после employees (Phase 5) |
| 4 | **roles** | **Extend by `code`** — добавлять новые роли; **не переназначать prod `role_id`** |
| 5 | **Master после cutover** | **VPS — единственный master** после завершения Phase 1–6 |
| 6 | **New hosting** | Основной путь: **`pg_dump` / `pg_restore`** (не row-level sync) |

### Принцип разделения источников истины

| Класс данных | Master после Phase 1–6 | Обоснование |
|--------------|------------------------|-------------|
| Reference | **VPS** | Справочники совпадают с prod org chart |
| Master | **VPS** | Кадры, оргструктура, контакты ведутся в prod |
| Operational | **VPS only** | Задачи, отчёты, audit — только prod |
| Auth / Secrets | **VPS only** | Пароли и Telegram bind — только prod |

**Local** после завершения sync roadmap переходит в роль **dev/staging consumer**: получает sanitized snapshot с VPS, но **не является master** для организационных или операционных данных.

---

## 1. Source of Truth

### A. Reference Data

**Таблицы:** `positions`, `departments`, `deps_group`, `task_statuses`, `reporting_periods`

| Таблица | Master (текущий) | Master (целевой) | Допустимые направления |
|---------|------------------|------------------|------------------------|
| `positions` | Local | VPS (после Phase 1) | Local → VPS ✅ · VPS → Local ✅ · VPS → hosting ✅ |
| `departments` | Local | VPS (после Phase 2) | Local → VPS ✅ · VPS → Local ✅ · VPS → hosting ✅ |
| `deps_group` | Local | VPS (после Phase 2) | Local → VPS ✅ · VPS → Local ✅ · VPS → hosting ✅ |
| `task_statuses` | Shared seed | Shared seed | Seed/migration only · не row-sync |
| `reporting_periods` | VPS | VPS | VPS → Local ⚠️ · VPS → hosting ✅ |

### B. Master Data

**Таблицы:** `org_units`, `employees`, `contacts`, `contacts_working`, `org_unit_groups`, `org_unit_group_units`, `org_unit_managers`, `user_org_units`, `user_supervisors`, `roles`

| Таблица | Master (текущий) | Master (целевой) | Допустимые направления |
|---------|------------------|------------------|------------------------|
| `org_units` | Split | VPS (после Phase 3) | Local → VPS ⚠️ merge by `code` · VPS → Local ✅ · VPS → hosting ✅ |
| `employees` | Split | VPS (после Phase 4) | Local → VPS ⚠️ delta only · VPS → Local ⚠️ sanitize · VPS → hosting ✅ |
| `roles` | Split | VPS | Local → VPS ⚠️ extend by `code` · VPS → Local ✅ · VPS → hosting ✅ |
| `contacts` | Local (если заполнен) | VPS (после Phase 5) | Local → VPS ✅ · VPS → Local ⚠️ sanitize · VPS → hosting ✅ |
| `org_unit_*`, `user_org_units`, `user_supervisors` | VPS | VPS | VPS → Local ⚠️ · VPS → hosting ✅ |

### C. Operational Data

**Таблицы:** `regular_tasks`, `tasks`, `task_reports`, `task_events`, `task_event_recipients`, `task_event_deliveries`, `task_audit_log`, `regular_task_runs`, `regular_task_run_items`, `notifications`, `audit_log`

| Таблица | Master | Допустимые направления |
|---------|--------|------------------------|
| Все operational | **VPS only** | Local → VPS ❌ · VPS → Local ⚠️ sanitize · VPS → hosting ✅ full restore |

`regular_tasks` — пограничный случай: шаблоны создавались на VPS для пилота и являются **prod configuration**, не historical local data.

### D. Auth / Secrets Data

**Поля и таблицы:**

- `users.password_hash`
- `users.telegram_id`, `users.telegram_username`, `users.telegram_bound_at`
- `users.login` (чувствительный идентификатор)
- `tg_bindings`
- `contacts.phone`, `contacts.telegram_*`

| Master | Допустимые направления |
|--------|------------------------|
| **VPS only** | Local → VPS ❌ · VPS → Local ❌ (только sanitized null) · VPS → hosting ✅ encrypted full restore |

---

## 2. Sync Direction Matrix

Легенда: ✅ рекомендуется · ⚠️ только с политикой конфликтов · ❌ запрещено

| Таблица | Local → VPS | VPS → Local | VPS → New Hosting |
|---------|:-----------:|:-----------:|:-----------------:|
| `positions` | ✅ | ✅ | ✅ `pg_dump` / restore |
| `departments` | ✅ | ✅ | ✅ `pg_dump` / restore |
| `deps_group` | ✅ | ✅ | ✅ `pg_dump` / restore |
| `org_units` | ⚠️ merge by `code`, preserve prod id | ✅ | ✅ `pg_dump` / restore |
| `employees` | ⚠️ delta only | ⚠️ sanitize | ✅ `pg_dump` / restore |
| `users` | ❌ | ⚠️ sanitize (no secrets) | ✅ `pg_dump` / restore |
| `roles` | ⚠️ extend by `code` | ✅ | ✅ `pg_dump` / restore |
| `contacts` | ✅ (Phase 5) | ⚠️ sanitize | ✅ `pg_dump` / restore |
| `regular_tasks` | ⚠️ new codes only | ✅ | ✅ `pg_dump` / restore |
| `tasks` | ❌ | ⚠️ sanitize / exclude | ✅ `pg_dump` / restore |
| `task_reports` | ❌ | ⚠️ sanitize / exclude | ✅ `pg_dump` / restore |
| `task_events` | ❌ | ⚠️ sanitize / exclude | ✅ `pg_dump` / restore |
| `task_event_deliveries` | ❌ | ❌ | ✅ `pg_dump` / restore |
| `task_audit_log` | ❌ | ⚠️ sanitize / exclude | ✅ `pg_dump` / restore |

---

## 3. Data Classification

### A. Reference

Стабильные справочники с малым объёмом, низкой частотой изменений, чёткими natural keys.

- `positions` — должности (`position_id`, `name`, `category`)
- `departments` — отделы (`department_id`, `name`)
- `deps_group` — группы отделений (`group_id`, `name`)
- `task_statuses` — коды статусов задач (`code` UNIQUE)
- `reporting_periods` — отчётные периоды

**Sync method:** CSV export/import, staging table, upsert, sequence fix.

### B. Master

Организационные и кадровые данные с FK-зависимостями.

- `org_units` — дерево подразделений (`code` UNIQUE, self-FK `parent_unit_id`)
- `employees` — кадровые записи (FK → `departments`, `positions`, `org_units`)
- `roles` — системные роли (`code` UNIQUE)
- `contacts` — контактные карточки (отдельно от `employees`, ADR-031)
- `org_unit_groups`, `org_unit_group_units`, `org_unit_managers`
- `user_org_units`, `user_supervisors`

**Sync method:** ordered import (FK chain), merge/delta policy, no blind replace.

### C. Operational

Данные жизненного цикла приложения; append-heavy; привязаны к prod timeline.

- `regular_tasks` — шаблоны (prod config)
- `tasks`, `task_reports`
- `task_events`, `task_event_recipients`, `task_event_deliveries`
- `task_audit_log`
- `regular_task_runs`, `regular_task_run_items`
- `notifications`, `audit_log`

**Sync method:** no row-level cross-environment sync; only full DB backup/restore.

### D. Auth / Secrets

Учётные данные и привязки мессенджеров.

- `users.password_hash`, `users.login`
- `users.telegram_id`, `users.telegram_username`, `users.telegram_bound_at`
- `tg_bindings`
- `contacts.phone`, `contacts.telegram_numeric_id`, `contacts.telegram_username`

**Sync method:** never auto-sync; VPS → hosting via encrypted `pg_dump` only.

---

## 4. Conflict Policy

### 4.1 Natural Keys

| Таблица | Primary Key | Natural Key (для match) | Fallback |
|---------|-------------|---------------------------|----------|
| `positions` | `position_id` | `position_id` | `normalize(name)` |
| `departments` | `department_id` | `department_id` | `normalize(name)` ⚠️ |
| `deps_group` | `group_id` | `group_id` | `normalize(name)` ⚠️ |
| `org_units` | `unit_id` | `code` (UNIQUE) | — |
| `employees` | `employee_id` | `employee_id` | — (delta: only missing PK) |
| `users` | `user_id` | `login` | — |
| `roles` | `role_id` | `code` (UNIQUE) | — |
| `contacts` | `contact_id` | `contact_id` | `full_name` + `phone` ⚠️ |
| `regular_tasks` | `regular_task_id` | `code` (UNIQUE) | — |
| `tasks` | `task_id` | — (только surrogate) | ❌ no cross-sync |
| `task_reports` | `report_id` | — | ❌ |
| `task_events` | `audit_id` | — | ❌ |
| `task_event_deliveries` | `(audit_id, user_id, channel)` | — | ❌ |
| `task_audit_log` | `audit_id` | — | ❌ |

`normalize(name)` — та же логика, что в `positions_routes.py`: trim, collapse spaces, нормализация дефисов.

### 4.2 Duplicate Handling

| Ситуация | Действие |
|----------|----------|
| Same PK, different attributes | `UPDATE` whitelist fields (см. 4.3) |
| Same natural key (`code`), different PK | **Preserve prod PK**; UPDATE attributes only |
| Staging row, PK отсутствует в prod | `INSERT` с `OVERRIDING SYSTEM VALUE` |
| Staging row, PK есть в prod, данные идентичны | `SKIP` |
| Staging row, PK есть в prod (employees delta) | `SKIP` — delta policy |
| Name collision, different PK | `CONFLICT` в diff report; default **SKIP** |
| FK target missing | **BLOCK apply** до импорта зависимости |

### 4.3 Update Policy

| Класс | Разрешённые поля для UPDATE | Запрещённые |
|-------|----------------------------|-------------|
| Reference | `name`, `category` (positions) | PK |
| Master `org_units` | `name`, `parent_unit_id`, `group_id`, `is_active` | **`unit_id` на prod** (preserve prod id) |
| Master `employees` | — (delta: no update of existing) | UPDATE существующих prod rows |
| Master `roles` | `name` для существующих prod roles | **`role_id`**, `code` на prod |
| Master `contacts` | `full_name`, phone fields (без telegram) | `contact_id` на prod |
| Auth `users` | `full_name`, `role_id`, `unit_id`, `is_active`, `employee_id` | `password_hash`, `telegram_*`, `login` |
| Operational | — | **Любые** при cross-env sync |

#### Принятые политики по сущностям

**org_units — merge by `code`, preserve prod `unit_id`:**

- Match: `org_units.code` (UNIQUE).
- Если `code` есть на prod: **сохранить prod `unit_id`**, обновить `name`, `parent_unit_id`, `group_id`, `is_active`.
- Если `code` только на local: INSERT с local `unit_id` (после проверки FK).
- **Никогда** не менять prod `unit_id`, на который ссылаются `users.unit_id`, `employees.org_unit_id`, `regular_tasks.owner_unit_id`.
- Пример: `unit_id=44` (`qm_ovipd`) остаётся 44.

**employees — delta import only:**

- Import только записей, чей `employee_id` **отсутствует** на VPS.
- Существующие prod employees (pilot ids 1–5, smoke) — **SKIP**, без UPDATE.
- Перед INSERT: проверить FK (`position_id`, `org_unit_id`, `department_id`).
- Полный replace или update существующих — **запрещён**.

**roles — extend by `code`, preserve prod `role_id`:**

- Match: `roles.code` (UNIQUE).
- Если `code` есть на prod: UPDATE `name` only; **`role_id` не менять**.
- Если `code` только на local: INSERT новой роли.
- Prod pilot roles (`QM_HEAD`, `QM_HOSP`, …) сохраняют свои `role_id` (3–7).

**contacts — отдельная фаза (Phase 5):**

- Не объединять с employees import.
- Delta/additive policy; sanitize telegram fields при VPS → local.

**Известный допустимый конфликт (Phase 1):**

- `position_id = 64`: local `Заведующий гинекологическим отделением` vs VPS `Специалист` (pilot placeholder) → **UPDATE разрешён**.

### 4.4 Delete Policy

| Правило | Значение |
|---------|----------|
| Default | **DELETE запрещён** |
| Staging vs prod: row only in prod | `KEEP` (не удалять) |
| Explicit flag | `--allow-delete` только для non-operational, non-auth tables, с отдельным ops approval |
| Orphan cleanup | Не автоматизировать в MVP |

---

## 5. Security Rules

### 5.1 Запрещено хранить в GitHub

- SQL dumps (полные или табличные)
- CSV/Excel с персональными данными (`employees`, `users`, `contacts`)
- `.env`, secrets, `password_hash`
- `telegram_id`, `telegram_username`, `tg_bindings`
- `task_event_deliveries` exports
- Diff reports с PII

### 5.2 Разрешено передавать через CSV (при соблюдении канала)

| Таблица | Разрешённые колонки | Канал |
|---------|---------------------|-------|
| `positions` | `position_id`, `name`, `category` | SCP / SFTP |
| `departments` | `department_id`, `name` | SCP / SFTP |
| `deps_group` | `group_id`, `name` | SCP / SFTP |
| `org_units` | `unit_id`, `code`, `name`, `parent_unit_id`, `group_id`, `is_active` | SCP / SFTP |
| `employees` | `employee_id`, `full_name`, FK ids, dates, `is_active` (без phone) | SCP / SFTP |
| `roles` | `role_id`, `code`, `name` | SCP / SFTP |
| `contacts` | `contact_id`, `person_id`, `full_name`, `phone` — **без** `telegram_*` | SCP / SFTP |
| `users` (Phase 6) | `user_id`, `login`, `full_name`, `role_id`, `unit_id`, `employee_id`, `is_active` — **без** `password_hash`, **без** `telegram_*` | SCP / SFTP |

### 5.3 Требует encrypted transfer

- Полный `pg_dump` / `pg_restore`
- Любой export с `users.password_hash`
- Любой export с `telegram_id` / `tg_bindings`
- `task_event_deliveries`, `task_events` (содержат user_id trail)
- Prod → local snapshot (даже sanitized — рекомендуется encryption)

Рекомендуемые механизмы: SCP over SSH, `age`, `gpg`, internal encrypted storage.

---

## 6. Migration Policy

### 6.A Local → VPS

**Цель:** одноразовое выравнивание справочников и master data; VPS остаётся master для operational/auth.

**Обязательный pipeline:**

1. Export source (CSV) на local
2. Transfer по SCP/SFTP (не GitHub)
3. **Backup VPS** (`pg_dump` full DB) до apply
4. Load в staging / temp table
5. **Dry-run diff** → preview report
6. Operator approval → `--apply`
7. Upsert / delta insert (не replace)
8. `setval` для identity sequences
9. Verify: counts, FK, API smoke
10. Ops log (без PII) на VPS

**Порядок фаз (см. §7):** positions → departments/deps_group → org_units → employees → contacts → users (no auth).

**Запрещено:**

- Import operational tables
- Overwrite `password_hash`, `telegram_id`
- `TRUNCATE` / `DELETE` prod rows
- Apply без dry-run
- UPDATE существующих prod employees
- Reassign prod `unit_id` или `role_id`

### 6.B VPS → Local

**Цель:** dev/staging environment для разработки, **не** зеркало prod auth.

**Политика:**

- Основной путь: **sanitized snapshot** (subset или full schema + masked data)
- Mask/null: `password_hash` → dummy, `telegram_id` → NULL, `tg_bindings` → empty
- Operational tables: optional exclude или anonymize `user_id` references
- **Не** считать local master после snapshot

### 6.C VPS → New Hosting

**Цель:** cutover prod на новый сервер без потери pilot trail.

**Основной и единственный рекомендуемый путь: `pg_dump` / `pg_restore`**

1. Pre-cutover: freeze writes (maintenance window) или brief downtime
2. `pg_dump -Fc` full database с VPS
3. Encrypted transfer
4. `pg_restore` на new hosting
5. Verify: Alembic version, counts, health, smoke
6. DNS / reverse proxy cutover
7. Post-cutover smoke (QM pilot flow)

**Row-level sync на new hosting — запрещён** как primary path.

Допустимо после restore: дельта-миграция Alembic, если schema drift.

---

## 7. Phase Roadmap

### Phase 1 — `positions`

| | |
|--|--|
| **Scope** | `position_id`, `name`, `category` |
| **Direction** | Local → VPS |
| **Method** | CSV, staging, upsert by `position_id`, setval |
| **Risk** | Low |
| **Exit criteria** | VPS count = 96; id=64 обновлён; FK valid; API 200 |

### Phase 2 — `departments`, `deps_group`

| | |
|--|--|
| **Scope** | `department_id`, `name`; `group_id`, `name` |
| **Direction** | Local → VPS |
| **Method** | Upsert by PK |
| **Risk** | Medium (`department_id=44` уже в prod) |
| **Dependency** | None |

### Phase 3 — `org_units`

| | |
|--|--|
| **Scope** | Full org tree from local |
| **Direction** | Local → VPS |
| **Method** | **Merge by `code`; preserve prod `unit_id`** |
| **Risk** | High — RBAC, `users.unit_id`, `regular_tasks.owner_unit_id` |
| **Dependency** | Phase 2 |
| **Exit criteria** | Prod `unit_id=44` сохранён; все pilot FK valid |

### Phase 4 — `employees`

| | |
|--|--|
| **Scope** | Кадровые записи, отсутствующие на VPS |
| **Direction** | Local → VPS |
| **Method** | **Delta import only** (INSERT missing `employee_id`) |
| **Risk** | High — FK chain |
| **Dependency** | Phase 1–3 |
| **Exit criteria** | Pilot employees 1–5 untouched; new rows FK-valid |

### Phase 5 — `contacts`

| | |
|--|--|
| **Scope** | Контактные карточки (отдельно от employees, ADR-031) |
| **Direction** | Local → VPS |
| **Method** | Delta/additive; без `telegram_*` overwrite |
| **Risk** | Medium — PII (`phone`) |
| **Dependency** | Phase 4 |
| **Exit criteria** | Contacts count aligned; no telegram overwrite |

### Phase 6 — `users` (без auth fields)

| | |
|--|--|
| **Scope** | Directory linkage: `full_name`, `role_id`, `unit_id`, `employee_id`, `is_active` |
| **Direction** | Local → VPS |
| **Method** | Delta by `login`; SKIP prod pilot users |
| **Explicit deny** | `password_hash`, `telegram_*` |
| **Risk** | Critical |
| **Dependency** | Phase 4–5 |
| **Prod pilot users** | `qm_*`, `admin` — SKIP или UPDATE только non-auth fields |

### Phase 2 (parallel) — `roles` extension

| | |
|--|--|
| **Scope** | Роли, отсутствующие на VPS |
| **Direction** | Local → VPS |
| **Method** | **Extend by `code`**; UPDATE `name` for existing; INSERT new |
| **Constraint** | **Do not reassign prod `role_id`** |
| **Risk** | Medium |
| **Dependency** | Может выполняться до или параллельно Phase 3 |
| **Exit criteria** | Pilot `role_id` 3–7 preserved; new roles added |

### Не входит в roadmap

- Operational sync (tasks, events, audit)
- Auth sync (`password_hash`, `telegram_id`, `tg_bindings`)
- Row-level VPS → new hosting sync

### Cutover milestone

После успешного завершения **Phase 1–6**:

- **VPS становится единственным master** для reference, master и directory data.
- Local переходит в режим **sanitized consumer**.
- Дата cutover фиксируется в ops log.

---

## 8. Обязательные операционные правила (все фазы)

| # | Правило |
|---|---------|
| 1 | Dry-run обязателен |
| 2 | Backup обязателен |
| 3 | DELETE запрещён по умолчанию |
| 4 | Import только через preview + explicit apply |
| 5 | `users.password_hash` / `telegram_id` — never overwrite без `--force-auth-fields` + ops approval |
| 6 | Prod → local — только sanitized snapshot |
| 7 | VPS → new hosting — **`pg_dump` / `pg_restore`**, не row-level sync |
| 8 | Personal data — не в GitHub |
| 9 | Preserve prod `unit_id` и `role_id` |
| 10 | Employees — delta only |

---

## Последствия

### Положительные

- Явное разделение master для reference/master vs operational/auth
- Снижение риска порчи pilot prod при импорте справочников
- Предсказуемый cutover на new hosting через full dump/restore
- Сохранение pilot FK (`unit_id=44`, `role_id` 3–7) при merge
- Основа для будущего `scripts/ops/*` tooling (вне scope данного ADR)

### Отрицательные / trade-offs

- Local перестаёт быть равноправным master — нужна дисциплина dev workflow
- org_units merge потребует mapping `parent_unit_id` при разных id-деревьях
- Delta employees не выравнивает атрибуты существующих prod записей
- Phase 6 users не решает полную синхронизацию учёток — только directory linkage

---

## Итоговый вывод

### VPS — единственный master после Phase 1–6

**Да.**

| Область | VPS = единственный master? |
|---------|:--------------------------:|
| Справочники (`positions`, `departments`, `deps_group`) | **Да** |
| Оргструктура (`org_units` + связанные) | **Да** |
| Кадры (`employees`) | **Да** |
| Контакты (`contacts`) | **Да** |
| Роли (`roles`) | **Да** |
| Directory users (без secrets) | **Да** |
| Auth (`password_hash`, `telegram_*`) | **Да** (уже сейчас) |
| Operational (tasks, events, audit) | **Да** (уже сейчас) |
| Local dev DB | **Нет** — consumer sanitized snapshot |

**Local** остаётся средой разработки. Изменения справочников после cutover вносятся **в VPS** (через UI Directory или controlled ops import), затем при необходимости отражаются в local через sanitized pull.

---

## Open Questions (оставшиеся)

1. **New hosting timeline:** blue/green или hard cutover?
2. **Ops log location:** `docs/ops/` (без PII в git) vs `/var/lib/corpsite/ops/` only?
3. **DB role для sync scripts:** отдельный least-privilege user?
4. **org_units parent mapping:** при merge by `code` — как резолвить `parent_unit_id`, если parent имеет другой `unit_id` на local?

---

## Suggested Follow-up Issue

**Title:** `ops: Phase 1 positions sync (local → VPS) per ADR-014`

**Scope:**

- Implement `scripts/ops/export_reference_data.py` + `import_reference_data.py` (positions only)
- Runbook `docs/ops/POSITIONS_SYNC_RUNBOOK.md`
- Execute import on VPS after SCP of local CSV
- Verify: count=96, position_id=64, FK, API smoke
- Ops log entry (no PII in git)

**Blocked by:** local CSV export + secure transfer (not GitHub).

---

## Связанные таблицы VPS (snapshot 2026-06-10)

Для справки:

```
positions=1, departments=1, deps_group=3, org_units=2,
employees=6, users=7, roles=6, contacts=0,
regular_tasks=2, tasks=7, task_reports=6,
task_events=12, task_event_deliveries=43, task_audit_log=12,
tg_bindings=0, users_with_telegram_id=3
```

---

## История изменений

| Дата | Версия | Изменение |
|------|--------|-----------|
| 2026-06-10 | Draft | Первоначальная версия на основе VPS audit |
| 2026-06-10 | Accepted | Приняты решения: org_units preserve prod id; employees delta; contacts Phase 5; roles extend by code; VPS sole master; pg_dump for hosting |
