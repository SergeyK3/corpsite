# OPS-028 — Platform User Login Policy

## Статус

**Proposed (Diagnosis complete)** — 2026-07-02

Документ фиксирует целевую корпоративную политику формирования логинов учётных записей Corpsite (Platform User).  
На данном этапе **код не изменяется**, **существующие логины не мигрируются**, **ADR-048 не изменяется**.

| Phase | Scope | Status |
|-------|-------|--------|
| OPS-028.1 | Diagnosis + policy document | **This document** |
| OPS-028.2 | Backend + UI implementation of new generator | Planned |
| OPS-028.3 | Optional legacy login review (out of scope here) | Not started |

## Связанные документы

| Document | Role |
|----------|------|
| [ADR-048](../adr/ADR-048-person-ownership-identity-creation-policy.md) | Person → Employee → User identity chain; login **не** входит в scope ADR-048 |
| [ADR-042 Phase A](../adr/ADR-042-phase-a-personnel-access-enrollment-architecture.md) | U-1: sysadmin создаёт user для enrolled employee вручную |
| [ADR-042 Phase B5](../adr/ADR-042-phase-b5-auth-policy.md) | Auth, lockout, `must_change_password`; пароль принадлежит `users` |
| [ADR-044 R2 User Linkage](../adr/ADR-044-r2-user-linkage-discovery.md) | Backfill-связь user↔employee; `LOGIN_SUFFIX` — **не** политика именования |
| [PILOT_QM_ROSTER](../PILOT_QM_ROSTER.md) | Исторические pilot-логины по коду роли (`qm_head@corp.local`) |

---

## 1. Контекст и постановка проблемы

В ходе проверки полного жизненного цикла сотрудника:

```text
HR Import → Enrollment → Operational Employee → Platform User
```

выявлено расхождение между **архитектурной моделью** и **фактическим алгоритмом предложения логина**.

### 1.1. Архитектурный принцип (принят)

Platform User (`public.users`) — **долгоживущая** сущность аутентификации.  
Role, должность, подразделение и grants — **изменяемые** operational-атрибуты.

```text
Person
   ↓
Operational Employee
   ↓
Platform User          ← login принадлежит здесь
   ↓
Roles / Access Grants
```

**Login не должен зависеть** от роли, должности, подразделения, переводов или реорганизаций.

### 1.2. Историческая ошибка (отклонена как целевая модель)

На раннем этапе pilot/seed использовались логины, отражающие **роль** или **код должности**:

| Пример | Источник | Проблема |
|--------|----------|----------|
| `dep_outpatient_audit@corp.local` | `db/init/020_seed_roles_users_employees.sql` | login = `lower(role_code)@corp.local` |
| `qm_head@corp.local` | pilot bootstrap | login привязан к функции, а не к человеку |

Такая модель допустима только как **временный pilot-артефакт**. Для production-персонала она **не соответствует** целевой архитектуре.

---

## 2. Diagnosis — текущее состояние системы

### 2.1. Где формируется предложение логина

| Layer | Компонент | Поведение |
|-------|-----------|-----------|
| UI (единственный generator) | `corpsite-ui/.../EmployeeAccountSections.tsx` → `translitLoginSeed()` | Предзаполнение поля «Логин» при открытии drawer «Создание пользователя» |
| UI form | `UserCreateForm.tsx` | Поле login **редактируемое**; пароль генерируется отдельно |
| Backend | `POST /directory/users` → `app/directory/users_routes.py` → `create_user()` | Принимает login **как передан**; **нет** server-side suggestion |
| Enrollment | `hr_import_enroll_employee_service.py` | Создаёт employee + contact; **не** создаёт user и **не** генерирует login |

**Flow создания Platform User:**

```text
HR Import enroll (employee + contact)
  → EnrollmentCompletionPanel / EmployeeAccountSections
  → «Создать доступ к Corpsite»
  → translitLoginSeed(FIO) → UserCreateForm (editable)
  → POST /directory/users
```

### 2.2. Текущий алгоритм `translitLoginSeed`

```75:91:corpsite-ui/app/directory/employees/_components/EmployeeAccountSections.tsx
function translitLoginSeed(name: string): string {
  const map: Record<string, string> = { /* Cyrillic → Latin */ };
  const parts = String(name || "")
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return "";
  const last = parts[parts.length - 1] ?? "";
  const firstInitial = (parts[0] ?? "").slice(0, 1);
  const raw = `${last}${firstInitial}`.split("").map((ch) => map[ch] ?? ch).join("");
  return raw.replace(/[^a-z0-9._-]+/g, "").slice(0, 64);
}
```

**Шаги:**

1. FIO → lowercase, split по пробелам.
2. **`last`** = **последний** токен строки.
3. **`firstInitial`** = первый символ **первого** токена.
4. Конкатенация `last + firstInitial` → транслитерация → очистка до `[a-z0-9._-]` → max 64 символа.
5. **Коллизии не проверяются** (уникальность — только при submit, HTTP 409).

### 2.3. Backend-ограничения при сохранении

| Rule | Implementation |
|------|----------------|
| Uniqueness | `lower(login)` case-insensitive unique |
| One user per employee | partial unique on `users.employee_id` |
| Format validation | length 1–200 only; **нет** regex-политики формата |
| `google_login` | при create устанавливается **равным** `login` (legacy column) |

### 2.4. Что система **не** делает с login сегодня

Подтверждено по кодовой базе:

- login **не** пересчитывается при переводе, смене должности, подразделения или роли;
- login **не** меняется при HR sync / enrollment update;
- пароль **не** сбрасывается автоматически при кадровых событиях;
- server-side API **не** предлагает login и **не** разрешает коллизии.

---

## 3. Root cause: почему для Козгамбаевой Л. Т. предлагается `talaspaevnak`

**ФИО:** `Козгамбаева Ляззат Таласпаевна`

| Step | Value |
|------|-------|
| `parts` | `["козгамбаева", "ляззат", "таласпаевна"]` |
| `last` (алгоритм берёт **последний** токен) | `"таласпаевна"` — **отчество**, не фамилия |
| `firstInitial` (первый символ **первого** токена) | `"к"` — первая буква **фамилии** |
| concat до транслитерации | `"таласпаевна" + "к"` |
| после транслитерации | **`talaspaevnak`** |

### 3.1. Диагноз

Алгоритм **ошибочно трактует порядок ФИО**:

- В корпоративном формате (KZ/RU): **Фамилия Имя Отчество**.
- Код использует **последний** токен как «фамилию» → получается **отчество**.
- Инициал в конце — от **фамилии** (первый токен), а не от имени.

Итог: login **нечитаемый**, **не узнаваемый** по фамилии сотрудника и **не соответствует** человеко-ориентированной политике.

### 3.2. Ожидаемый login по целевой политике (§4)

`kozgambaeva.lt` — фамилия + инициалы имени и отчества.

---

## 4. Целевая корпоративная политика формирования login

### 4.1. Normative format

**Базовый шаблон:**

```text
{translit_surname}.{initials}
```

| Component | Rule | Example (Козгамбаева Ляззат Таласпаевна) |
|-----------|------|----------------------------------------|
| `translit_surname` | Фамилия (1-й токен FIO), lowercase, Cyrillic→Latin | `kozgambaeva` |
| `initials` | Инициалы **имени** и **отчества** (2-й и 3-й токены); если отчества нет — только инициал имени | `lt` |
| separator | Точка `.` между фамилией и инициалами | `kozgambaeva.lt` |

**Эталонные примеры:**

| FIO | Login |
|-----|-------|
| Козгамбаева Ляззат Таласпаевна | `kozgambaeva.lt` |
| Нурбеков Бахдат Байтлевич | `nurbekov.bb` |
| Kim Sergey Viktorovich *(пример)* | `kim.sv` |
| Иванова Мария *(без отчества)* | `ivanova.m` |

### 4.2. Источник FIO для генерации

Приоритет источников (от более точного к fallback):

1. **`persons.last_name` / `first_name` / `middle_name`** — если employee связан с Person и поля заполнены (ADR-048 Person Shell).
2. **`employees.full_name`** — разбор по правилу «Фамилия Имя [Отчество]» (1/2/3 токена).
3. **Override в UI** — администратор может исправить до сохранения (§8).

> **Normative parsing rule:** при разборе `full_name` **первый** токен = фамилия, **второй** = имя, **третий** = отчество. Это противоположно текущей ошибке `translitLoginSeed`.

### 4.3. Транслитерация

Единая таблица Cyrillic→Latin для generator (backend + UI должны использовать **одну** реализацию при OPS-028.2).

| Aspect | Policy |
|--------|--------|
| Case | lowercase only |
| `ё` → `e`, `й` → `y`, digraphs (`zh`, `ch`, `sh`, `sch`, `yu`, `ya`, `ts`) | как в текущем UI map |
| `ъ`, `ь` | удаляются |
| Неизвестные символы | удаляются (не fallback в `?`) |
| Max length | **64** символа (с учётом суффикса коллизии) |

**Out of scope v1:** транслитерация казахских специфических букв (`ә`, `і`, `ң`, …) — зафиксировать в OPS-028.2 как отдельную задачу, если потребуется; до этого — поведение как у текущей Latin map.

### 4.4. Allowed character set

```text
[a-z0-9._-]
```

- Точка **обязательна** между фамилией и инициалами в базовом шаблоне.
- `@corp.local` и прочие domain-suffix **не добавляются** автоматически (Corpsite login — локальный идентификатор в `users.login`).

### 4.5. Explicit non-goals (login MUST NOT encode)

| Attribute | Must NOT appear in login |
|-----------|--------------------------|
| `roles.code` / role name | ✗ (legacy pilot only) |
| `positions` / должность | ✗ |
| `org_units` / подразделение | ✗ |
| `employee_id` | ✗ (кроме legacy `LOGIN_SUFFIX` backfill — §5.3) |
| Access grants | ✗ |

---

## 5. Политика разрешения коллизий

### 5.1. Uniqueness scope

Login уникален **глобально** в `public.users` (case-insensitive), включая неактивных пользователей, если запись не удалена.

### 5.2. Алгоритм (normative)

1. Вычислить **base login** по §4.
2. Если `base` свободен → предложить `base`.
3. Если занят → перебирать суффиксы **`2`, `3`, …, `99`**:

```text
kozgambaeva.lt   → занят
kozgambaeva.lt2  → занят
kozgambaeva.lt3  → свободен ✓
```

**Правило суффикса:** цифры **в конце всей строки login**, без дополнительного разделителя.

4. Если `base99` исчерпан → generator возвращает ошибку; администратор задаёт login вручную.

### 5.3. Проверка коллизий — server-side (OPS-028.2)

| Requirement | Rationale |
|-------------|-----------|
| `GET /directory/users/suggest-login?employee_id=…` (или эквивалент) | Единый источник истины; UI не дублирует логику |
| Проверка при `POST /directory/users` | Защита от race / ручного ввода |
| Preview в UI до submit | Администратор видит итоговый login |

### 5.4. Legacy `LOGIN_SUFFIX` (не путать с naming policy)

ADR-044 R2 использует pattern `^.+_[0-9]+$` для **обнаружения** связи user↔employee при backfill.  
Это **migration/discovery** инструмент, **не** целевой формат новых логинов.

---

## 6. Immutability — когда login **не** меняется

Login Platform User **остаётся неизменным** при следующих событиях:

| Event | Login | Password | Role / unit / grants |
|-------|-------|----------|----------------------|
| Перевод сотрудника | **unchanged** | unchanged | may change |
| Смена должности | **unchanged** | unchanged | may change |
| Смена подразделения | **unchanged** | unchanged | `unit_id` may change |
| Смена role (task role) | **unchanged** | unchanged | changes |
| Изменение access grants | **unchanged** | unchanged | changes |
| HR Import / canonical sync (FIO update) | **unchanged** | unchanged | — |
| Deactivate / reactivate user | **unchanged** | unchanged | — |

**Rationale:** login — стабильный идентификатор аутентификации и audit trail (`AUTH_LOGIN*`, export metadata). Operational attributes меняются через role/grants/employee link, не через переименование login.

### 6.1. Admin-initiated login change (exception)

Смена login **после** создания — **исключительная** операция (брак при создании, юридическое требование, коллизия legacy).  
Требования OPS-028.2:

- отдельное admin action + audit event;
- проверка uniqueness;
- **не** автоматизировать при routine HR events.

---

## 7. Политика при смене фамилии

| Scenario | Policy |
|----------|--------|
| **Default** | Login **остаётся прежним** |
| **Rationale** | Стабильность входа, audit, Telegram bind (`users.telegram_id`), внешние ссылки; смена фамилии ≠ смена identity |
| **UI** | В карточке user допустимо показывать актуальное `full_name` employee/person **отдельно** от login |
| **Voluntary change** | По запросу сотрудника — admin may change login по §6.1 (не автоматически) |
| **Alias / dual login** | **Not in v1** — отложить; при необходимости отдельный ADR (secondary login → same `user_id`) |
| **New employment episode** | Тот же Person / тот же User при rehire — login **не** пересоздаётся |

> **Согласование с ADR-048:** Person переживает смену фамилии; login привязан к User, User может переживать несколько employee episodes одного Person. Смена `persons.last_name` **не** триггерит rename login.

---

## 8. Пароль — принадлежность Platform User

| Statement | Status in codebase |
|-----------|-------------------|
| Пароль хранится в `users.password_hash` | ✓ |
| Пароль задаётся при `POST /directory/users` | ✓ |
| Кадровые события **не** меняют пароль автоматически | ✓ (нет такого кода) |
| Lockout / `must_change_password` / `token_version` — политика auth, не HR | ADR-042 B5 |

**Normative policy:**

- Пароль принадлежит **Platform User**, не Employee и не Role.
- Перевод, смена должности, подразделения, роли, grants — **не** инициируют reset пароля.
- Reset / temp password — только **явные** admin/security действия (`admin_password_reset_service`, будущий UI).

---

## 9. UX при создании Platform User

| Requirement | Current | Target |
|-------------|---------|--------|
| Auto-suggest login по политике | UI-only, buggy algorithm | Server-side suggest (§5.3) |
| Admin может изменить до save | ✓ `UserCreateForm` editable | ✓ сохранить |
| Auto-generate password | ✓ client-side | ✓ сохранить (optional: server-side) |
| Role preselect from position | not required by this policy | out of scope |
| Uniqueness feedback | on submit (409) | preview + on submit |

**Normative UX copy (ru):** «Логин предложен автоматически по фамилии и инициалам. Вы можете изменить его до сохранения.»

---

## 10. Scope boundaries (этот документ)

| In scope | Out of scope |
|----------|--------------|
| Policy definition | Code implementation |
| Diagnosis текущего алгоритма | Migration существующих pilot logins |
| Collision rules | ADR-048 amendments |
| Immutability rules | SSO / external IdP integration |
| Password ownership confirmation | Argon2 migration (ADR-042 B5) |

**Existing logins** (`dep_admin@corp.local`, `qm_head@corp.local`, manually created, etc.) **grandfathered** — не требуют изменения до отдельного решения по legacy cleanup.

---

## 11. Implementation checklist (OPS-028.2)

Для последующей реализации — **не выполнять в OPS-028.1**:

- [ ] Shared module `login_suggestion.py` (+ unit tests с таблицей FIO → login)
- [ ] API `suggest-login` с collision loop §5.2
- [ ] Replace `translitLoginSeed` в UI вызовом API
- [ ] Optional: format validation regex on `UserCreateIn`
- [ ] Audit event `USER_LOGIN_SUGGESTED` (debug) / `USER_CREATED` (existing)
- [ ] Admin doc link из drawer создания user

### 11.1. Test vectors (acceptance)

| Input FIO | Expected base | Notes |
|-----------|---------------|-------|
| Козгамбаева Ляззат Таласпаевна | `kozgambaeva.lt` | regression for OPS-028 bug |
| Нурбеков Бахдат Байтлевич | `nurbekov.bb` | seed employee |
| Иванова Мария | `ivanova.m` | no patronymic |
| Козгамбаева Ляззат Таласпаевна *(duplicate person)* | `kozgambaeva.lt2` | if base taken |

---

## 12. Summary

| # | Question | Answer |
|---|----------|--------|
| 1 | Почему `talaspaevnak`? | Bug: алгоритм берёт **отчество** (последний токен) + инициал **фамилии** |
| 2 | Целевой формат | `{surname}.{initials}` — `kozgambaeva.lt`, `nurbekov.bb` |
| 3 | Коллизии | суффиксы `2`, `3`, … в конце login; проверка server-side |
| 4 | Перевод / role / unit | login **не меняется** |
| 5 | Смена фамилии | login **по умолчанию не меняется**; смена — только admin exception |
| 6 | Пароль | принадлежит Platform User; HR events **не** сбрасывают |
| 7 | Создание | auto-suggest + manual override до save |

---

## Appendix A — Comparison: current vs target algorithm

```text
FIO: "Козгамбаева Ляззат Таласпаевна"

CURRENT (translitLoginSeed):
  last_token     = "таласпаевна"   ← wrong (patronymic)
  first_initial  = "к"             ← from surname, appended at end
  result         = "talaspaevnak"

TARGET (OPS-028):
  surname        = "козгамбаева"
  initials       = "л" + "т"
  result         = "kozgambaeva.lt"
```

## Appendix B — Code references

| Artifact | Path |
|----------|------|
| Current UI generator | `corpsite-ui/app/directory/employees/_components/EmployeeAccountSections.tsx` |
| User create form | `corpsite-ui/app/directory/employees/_components/UserCreateForm.tsx` |
| User create API | `app/directory/users_routes.py` |
| Legacy role-based seed | `db/init/020_seed_roles_users_employees.sql` |
| LOGIN_SUFFIX discovery | `app/services/user_linkage_preview_service.py` |
