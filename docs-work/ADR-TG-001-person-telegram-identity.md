# ADR-TG-001 — Person-Level Telegram Identity

## Status

**Accepted for implementation (Phase 1)** — architecture ratification for the first implementation phase; code changes not started beyond pre-implementation artifacts listed below.

| Field | Value |
|-------|-------|
| Date | 2026-07-21 |
| Scope | Phase 1: Person-level Telegram identity across PPR Self-Service and Operational / Regular Tasks contours (first communication channel; see Introduction) |
| Related | [WP-PR-002 §7.2 AB-6](../docs/architecture/WP-PR-002-aggregate-boundary-specification.md), [ARCH-001 Platform User assessment](../docs/architecture/ARCH-001-platform-user-identity-assessment.md), [ADR-044 §7 Telegram impact](../docs/adr/ADR-044-r2-user-linkage-discovery.md), [OPS-007](../docs/ops/OPS-007-telegram-bot-operational-audit.md), [ADR-057](../docs/adr/ADR-057-personnel-application-aggregate.md) |
| Pre-implementation artifacts | Migration `k2l3m4n5o6p7` — table `personnel_intake_telegram_bindings`; ORM `PersonnelIntakeTelegramBinding`; repository `SqlAlchemyPersonnelIntakeTelegramBindingRepository` |
| Supersedes (intent) | После внедрения Person-level модели — `users.telegram_id` как **source of truth** для Telegram ↔ identity (планируется вывод из SoT после завершения миграции) |

---

## Introduction

Corpsite планирует поддержку нескольких **communication channels** для взаимодействия с Person (self-service, operational delivery и др.). **Telegram — первый реализуемый канал** в рамках Phase 1.

Настоящий ADR описывает **только Telegram identity** и принятые для него архитектурные решения. Документ **не исключает** появление других каналов (WhatsApp, Microsoft Teams, мобильное приложение, push-уведомления и т.п.), но их архитектура **в этот ADR не входит** и потребует отдельного рассмотрения при появлении конкретного scope.

---

## 1. Problem

### 1.1. Два независимых Telegram-контура

Сегодня в Corpsite фактически существуют **два раздельных Telegram-контура**:

| Контур | Бот / entrypoint | Текущая привязка | Назначение |
|--------|------------------|------------------|------------|
| **PPR Self-Service** | `corpsite-bot` intake entrypoint (`INTAKE_BOT_TOKEN`), skeleton `/start` | Планировалась отдельная Person-level таблица; идентификация через intake link / будущий self-service | Заполнение личной карточки, applicant self-service |
| **Operational / Regular Tasks** | `corpsite-bot` operational entrypoint (`/bind`, `/tasks`, `/events`) | **`users.telegram_id`** → `users.user_id` → RBAC | Задачи, события, operational delivery |

Контуры используют **разные токены ботов**, разные handler-цепочки и **не разделяют единую модель идентичности**.

### 1.2. Повторная привязка недопустима

Пользовательский и архитектурный инвариант: **один физический Telegram-аккаунт не должен проходить повторную идентификацию / bind** при переходе между ботами (PPR → operational). Повторный `/bind` с one-time code для того же человека создаёт:

- дублирование UX;
- риск рассогласования двух store;
- ложное ощущение «новой регистрации» при смене контура.

### 1.3. `users.telegram_id` не покрывает целевую аудиторию

Исследование схемы, ORM, repository/query-паттернов и **фактических данных текущей БД** (2026-07-21):

| Факт | Значение (локальная БД) |
|------|-------------------------|
| Active employees **без** Platform User | **89 / 94** |
| Persons с контекстом `CANDIDATE` | **30** (путь `person → employee → user`: **0**) |
| `personnel_applications` с user-цепочкой | **0 / 8** |
| Замкнутая цепочка `telegram → user → employee → person` | **0** |
| `users.telegram_id` заполнен | **0** |

**Applicant** получает `person_id` при регистрации заявления (`registration_service`); **Platform User не создаётся**. Operational bind на `users.telegram_id` **принципиально не применим** к основной аудитории PPR Self-Service.

Дополнительные разрывы цепочки:

- `users.employee_id IS NULL` — большинство users;
- `employees.person_id IS NULL` — часть active employees;
- reverse lookup `telegram → person` в коде **отсутствует**.

### 1.4. Уже созданная заготовка data model

В рамках сегодняшней сессии создана таблица `personnel_intake_telegram_bindings` (migration `k2l3m4n5o6p7`) с корректной Person-level семантикой:

- `person_id`, `telegram_user_id`, `revoked_at`;
- partial unique: один active `telegram_user_id` ↔ один active `person_id`;
- ORM + repository с операциями create / revoke / get_active.

Имя таблицы отражает **исторический intake-контур**, но структура соответствует **целевой Person-level identity**, принятой сегодня.

---

## 2. Accepted architectural decisions

### D1 — Telegram identity подтверждается один раз на уровне Person

Первичная идентификация «кто этот Telegram-пользователь» выполняется **один раз** и закрепляется за **`person_id`**, а не за `users.user_id`.

Platform User остаётся контуром **authentication / RBAC / operational delivery**, но **не владеет** канонической Telegram identity для Person-owned self-service.

### D2 — Person является владельцем Telegram identity

**Source of Truth** для связи Telegram ↔ человек:

```text
person_telegram_bindings   (target name; today: personnel_intake_telegram_bindings)
    person_id
    telegram_user_id
    revoked_at | created_at | updated_at
```

Таблица — **Person-owned identity artifact**, вне агрегата PPR (см. AB-6).

### D3 — Все боты используют одну Person-level идентичность

PPR Self-Service bot и Operational / Regular Tasks bot (и будущие Telegram-контуры) **читают одну и ту же** active Person-level привязку. Отдельные bind-store на контур **не создаются**.

### D4 — Повторная идентификация между ботами не требуется

После успешной Person-level привязки переход пользователя в другой бот **не запускает** повторный сценарий IIN / bind code. Бот только **проверяет** существующую привязку.

### D5 — Каждый бот активируется отдельно после первого Start

**Activation** (первый `/start` в конкретном боте) — отдельное понятие от **identity binding**:

| Понятие | Смысл |
|---------|--------|
| **Identity binding** | Один раз: `person_id ↔ telegram_user_id` |
| **Bot activation** | Первый (и последующий) Start в конкретном боте; фиксирует, что Person «включил» этот контур |

Activation **не является** повторной привязкой личности.

### D6 — Target registry per-bot activation (to be introduced)

Минимальная отдельная таблица (WP-001):

```text
person_telegram_bot_activations
    person_id
    bot_code          -- e.g. intake_ppr | operational_tasks
    first_activated_at
    last_activated_at
    UNIQUE (person_id, bot_code)
```

### D7 — `users.telegram_id` — переходный operational store (planned legacy after migration)

Сегодня operational bot использует `users.telegram_id` как store привязки Telegram ↔ Platform User. После реализации Person-level модели (Phase 1) поле **планируется перевести в legacy** и **вывести из роли Source of Truth** после завершения миграции (WP-TG-005) и подтверждения отсутствия функциональных зависимостей.

На период миграции `users.telegram_id` может использоваться как **read-fallback** operational bot. Целевая модель: новые bind **не пишут** в `users.telegram_id` как authoritative store; SoT — `person_telegram_bindings`.

Исключение: **service accounts без Person** — вне Person-контура; user-level transport может сохраняться явно как non-Person exception.

### D8 — Rename intake-scoped table to Person-scoped name (accepted intent)

`personnel_intake_telegram_bindings` → **`person_telegram_bindings`** — выполнить на WP-001, пока потребителей и данных мало.

---

## 3. Lifecycle scenarios

### 3.1. Кандидат → PPR

```text
1. HR регистрирует заявление → persons.person_id (часто по IIN)
2. Кандидат открывает PPR / intake Telegram bot → /start
3. Если person_telegram_bindings ACTIVE отсутствует:
      → one-time Person identification (IIN + проверки; см. риски §5)
      → create_binding(person_id, telegram_user_id)
4. upsert person_telegram_bot_activations(bot_code = intake_ppr)
5. Self-service PPR / intake без повторной идентификации в сессии
```

Кандидат **не имеет** Platform User; identity только через Person.

### 3.2. Кандидат → сотрудник

```text
1. HIRE / Order Apply → employees + hr_relationship_context → EMPLOYED
2. person_telegram_bindings НЕ сбрасывается (тот же person_id, тот же telegram_user_id)
3. При первом /start operational bot:
      → lookup существующей Person-level bind
      → upsert activation (operational_tasks)
      → derive user_id через person → employee → users (если Platform User существует)
      → БЕЗ повторной идентификации
```

### 3.3. Сотрудник → руководитель

Смена роли / должности **не меняет** Person nor Telegram identity. Тот же `person_id`, та же bind. Меняются RBAC / Cabinet / assignments через Platform User и Employment — **не через Telegram re-bind**.

### 3.4. Руководитель впервые запускает operational bot

```text
1. Person-level bind уже существует (например, создан при PPR self-service)
2. /start в operational bot:
      → resolve telegram_user_id → person_id (canonical)
      → record bot activation (operational_tasks)
      → resolve Platform User для RBAC (если есть)
3. /bind с one-time code НЕ требуется
```

Если Platform User отсутствует — operational функции недоступны, но Person identity сохраняется для PPR-контура.

### 3.5. Бывший сотрудник

```text
1. Employment terminated; Person и PPR сохраняются
2. person_telegram_bindings сохраняется (пока не revoked administratively)
3. hr_relationship_context может оставаться FORMER_EMPLOYEE (ADR-057 D4)
4. Повторное заявление (rehire path) → новый Personnel Application, тот же Person
5. Telegram re-identification НЕ требуется при повторном входе в PPR / operational bot
```

Revoke bind — **отдельное административное действие**, не следствие termination.

### 3.6. Повторный вход в любой бот

```text
/start → lookup active person_telegram_bindings by telegram_user_id
      → if found: upsert last_activated_at for bot_code; продолжить сценарий бота
      → if not found: Person identification flow (§3.1 step 3)
```

---

## 4. Architectural invariants

| ID | Invariant |
|----|-----------|
| **TG-1** | Не более **одной active** привязки на `telegram_user_id` |
| **TG-2** | Не более **одной active** привязки на `person_id` |
| **TG-3** | Одна Person-level Telegram identity **общая для всех** Telegram-ботов Corpsite |
| **TG-4** | Запуск нового бота (**activation**) **не требует** повторной Person identification |
| **TG-5** | Каждый бот имеет **собственный** статус activation (`person_id`, `bot_code`) |
| **TG-6** | **RBAC, tasks, events authorization** остаются на **Platform User** (`users`, roles, Cabinet resolver) — Telegram identity их **не заменяет** |
| **TG-7** | Telegram identity **не является частью агрегата PPR** (AB-6); хранится как Person-owned transport identity рядом с `persons` |
| **TG-8** | Operational contour **derive** `user_id` из `person_id` (через Employment), а не наоборот как SoT |
| **TG-9** | Revoke binding — soft (`revoked_at`); история строк сохраняется |
| **TG-10** | Service accounts без Person — **вне** TG-1…TG-3; явно документированное исключение |

---

## 5. Consequences

### 5.1. Benefits

- **Единый UX:** один Telegram-аккаунт — одна идентичность; переход PPR ↔ tasks без `/bind`.
- **Покрытие applicants:** Person-level bind работает **без Platform User**.
- **Согласованность с Person ownership:** identity на `person_id` согласуется с ADR-048, ADR-054, ADR-057.
- **Чистое разделение:** transport identity (Person) vs authorization (Platform User) vs PPR aggregate (cadre SoT).
- **Ранняя заготовка:** таблица и repository уже созданы; rename дешёвый при пустых данных.

### 5.2. Limitations

- Operational bot **не работает** только по Telegram bind — нужен **derive path** `person → employee → user`; при отсутствии user задачи недоступны.
- **Identification evidence** (IIN и т.д.) сегодня **не доказывает владение** Telegram-аккаунтом (нет OTP / verified phone) — см. риски.
- **Backfill** с `users.telegram_id` покроет только узкое подмножество (users с employee + person).
- Два bot token / два deployment entrypoint остаются; меняется только **shared identity layer**.

### 5.3. Risks

| Risk | Severity | Mitigation (future WP) |
|------|----------|------------------------|
| **Impersonation** по IIN без proof-of-possession | High | Out-of-scope Phase 1; HR-provisioned intake link / future OTP; rate limits |
| **Dual-read** person table vs `users.telegram_id` during migration | Medium | Person-first resolver; conflict audit; planned sunset of writes to `users.telegram_id` after migration |
| **Broken chain** person → user для staff | Medium | Graceful degradation; HR enrollment creates user; clear UX |
| **No DB UNIQUE** on current `users.telegram_id` | Low | Person table partial uniques authoritative; migration reconcile |

### 5.4. Migration questions (open, non-blocking for ADR)

1. Точный **bot_code** enum (`intake_ppr`, `operational_tasks`, others?).
2. Политика **revoke** при смене Telegram-устройства (self-service vs HR-only).
3. Срок **deprecation** `users.telegram_id` и `/bind` для Person-контура.
4. Backfill script scope на VPS vs local dev counts.

---

## 6. Preliminary implementation roadmap

Без технических деталей реализации. Work Packages **последовательны по зависимостям**.

| WP | Title | Outcome |
|----|-------|---------|
| **WP-TG-001 Data Model** | Person Telegram Identity schema | Rename → `person_telegram_bindings`; introduce `person_telegram_bot_activations`; align ORM/repository naming |
| **WP-TG-002 Resolver** | Canonical `telegram_user_id → person_id` | Single backend resolver; Person-first; legacy fallback policy for `users.telegram_id` |
| **WP-TG-003 Bot Activation** | Per-bot Start activation | `/start` handlers record activation; no re-identification when bind exists |
| **WP-TG-004 Operational Bot Integration** | Tasks / events contour on Person identity | Replace `/bind`-first UX for Person-contour users; derive `user_id` for RBAC |
| **WP-TG-005 Legacy Migration** | Deprecate `users.telegram_id` as SoT | Backfill, dual-read sunset, OPS-007 alignment, documentation update |

---

## 7. Target architecture (reference)

```text
                    ┌─────────────────────────────┐
                    │   person_telegram_bindings   │  ← SoT (Person-owned)
                    │   person_id ↔ telegram_user_id│
                    └──────────────┬──────────────┘
                                   │ person_id
           ┌───────────────────────┼───────────────────────┐
           ▼                       ▼                       ▼
┌────────────────────┐  ┌────────────────────┐  ┌─────────────────────┐
│ bot_activations    │  │ PPR Self-Service   │  │ persons → employees │
│ intake_ppr         │  │ intake / PPR UI    │  │      → users (RBAC) │
│ operational_tasks  │  └────────────────────┘  └─────────────────────┘
└────────────────────┘                                      │
           ▲                                                ▼
           │                                    Operational / Tasks bot
    /start in each bot                          (authorization via User)
```

---

## 8. Decision log

| Date | Decision |
|------|----------|
| 2026-07-21 | Person-level single Telegram identity adopted; hybrid user-bind rejected as SoT |
| 2026-07-21 | `personnel_intake_telegram_bindings` accepted as basis; rename to `person_telegram_bindings` on WP-TG-001 |
| 2026-07-21 | Per-bot activation as separate registry, not part of bind row |
| 2026-07-21 | `users.telegram_id` — planned transition to legacy after WP-TG-005 migration and dependency audit |

---

*End of ADR-TG-001*
