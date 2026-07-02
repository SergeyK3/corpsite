# OPS-029 — UserCreateForm UX & Role Source

## Статус

**Implemented (UX + role source fix)** — 2026-07-02

| Phase | Scope | Status |
|-------|-------|--------|
| OPS-029.1 | Diagnosis + UX restructure + full roles catalog | **This update** |
| OPS-029.2 | `org_unit_allowed_roles` (if approved) | Architecture gap — not implemented |

## Связанные документы

| Document | Role |
|----------|------|
| [OPS-028](./OPS-028-platform-user-login-policy.md) | Login policy (unchanged) |
| [ADR-046](../adr/ADR-046-org-unit-allowed-positions.md) | Analogous gap for positions |
| [ADR-042 Phase A](../adr/ADR-042-phase-a-personnel-access-enrollment-architecture.md) | Task `roles` vs access `access_roles` |

---

## 1. Diagnosis — поле «Роль» в UserCreateForm

### 1.1. Что отображается

| Вопрос | Ответ |
|--------|--------|
| Кадровая должность? | **Нет** — `employees.position` не используется |
| Access Role (RBAC)? | **Нет** — это `public.access_roles` / `GET /admin/access/roles` |
| Platform / Task Role? | **Да** — `public.roles` → `users.role_id` |

Поле **«Роль Corpsite»** — это **Platform Task Role** (QM_HEAD, DEP_ADMIN, …), не кадровая должность.

### 1.2. Источник данных (до OPS-029)

| Layer | Поведение |
|-------|-----------|
| `EmployeeAccountSections` | `getRoles({ limit: 200 })` — **без** org-параметров |
| `GET /directory/roles` без фильтров | **Полный каталог** `public.roles` |
| `GET /directory/roles?org_group_id=&org_unit_id=` | **Roles in use** — EXISTS на `users` с active user в org scope |
| `RolesPageClient` (справочник ролей) | Передаёт org params → **filtered by existing users** |

**Production-симптом «только уже используемые роли»** возникает, если:

1. Сравнение со **справочником ролей** при активном org-filter в URL (list API filtered).
2. Путаница с **должностями** (`GET /directory/positions?org_unit_id=` — тоже «used in unit»).
3. Лимит 200 + субъективно «знакомые» role names из pilot.

UserCreateForm **не должен** вызывать scoped roles API.

### 1.3. Architecture gap

**`org_unit_allowed_roles` не существует.**

| Layer | Positions (ADR-046) | Roles (OPS-029) |
|-------|---------------------|-----------------|
| Global catalog | `public.positions` | `public.roles` |
| Allowed per unit | proposed junction | **missing** |
| Used in unit | `GET /positions?org_unit_id=` | `GET /roles?org_unit_id=` |
| Form dropdown (target) | catalog + optional hint | **full catalog** via `listPlatformRoleCatalog()` |

Org filters в форме — **prefill / navigation / UX**, не источник разрешённых ролей.

---

## 2. UX — новая структура формы

```text
Создание пользователя
Аккаунт для: {ФИО}          ← read-only header

Группа отделений            ← OrgScopeFilter (controlled)
Отделение                   ← OrgUnitScopeFilter (controlled, filtered by group)
Роль Corpsite               ← full public.roles catalog
Логин                       ← OPS-028 policy
Пароль
☑ Активный пользователь
```

Prefill: `resolveEmployeeOrgScopePrefill()` из `employees.org_unit_id`.

---

## 3. Implementation map

| Artifact | Change |
|----------|--------|
| `components/OrgScopeFilter.tsx` | Optional controlled `value` / `onChange` |
| `components/OrgUnitScopeFilter.tsx` | Optional controlled `orgGroupId` / `value` / `onChange` |
| `lib/platformRoleCatalog.ts` | `listPlatformRoleCatalog()` — no org scope |
| `lib/userCreateOrgScope.ts` | Prefill helpers |
| `UserCreateForm.tsx` | New field order + internal role load |
| `EmployeeAccountSections.tsx` | Org prefill; drawer kept mounted on reload |

---

## 4. Out of scope (confirmed)

- RBAC / `access_roles` changes
- `org_unit_allowed_roles` table
- Login policy changes
- Creating Platform User for Kozgambaeva (test only)

---

## 5. Tests

- `lib/userCreateOrgScope.test.ts` — group resolution + employee unit id
- `lib/platformRoleCatalog.test.ts` — no org scope in API query
- `UserCreateForm.test.tsx` — org filter interaction, full catalog, login policy
- `EmployeeAccountSections.loginSuggestion.test.tsx` — prefill + login
