# ADR-045 — Разделение «Персонал» и «Кадровые процессы»

**Status:** Accepted  
**Date:** 2026-06-22  
**Related:** ADR-031, ADR-042 (E1 visibility), ADR-043 (HR operations)

## Context

Раздел «Персонал» в левом сайдбаре совмещал управленческий просмотр сотрудников и кадровый операционный контур (import, journal, reconciliation, enrollment и т.д.). Это создавало путаницу ролей и показывало заведующим/директорам экраны, для которых у них нет полномочий.

## Decision

Левый сайдбар делится на три независимых контура:

| Раздел | Маршрут | Назначение | Кто видит |
|--------|---------|------------|-----------|
| **Персонал** | `/directory/staff` | Read-only personnel browser: список, фильтры, карточка на просмотр | Заведующие, руководители, главный врач, директор, HR, System Administrator |
| **Кадровые процессы** | `/directory/personnel/*` | HR operational contour: journal, documents, import, hr-change-events | HR (`has_personnel_admin`), System Administrator, role_id=2 |
| **Кабинет системного администратора** | `/admin/system` | Системное администрирование (без изменений) | Только System Administrator (`is_privileged` / role_id=2) |

### Роли высшего звена

**Главный врач** и **директор** — управленцы с расширенным просмотром (через ADR-042 visibility assignments), но **не** системные администраторы и **не** кадровики. Они видят «Персонал», не видят «Кадровые процессы» и «Кабинет системного администратора».

### Read-only «Персонал»

- Таблица: ФИО, должность, отделение, статус, ставки, «Открыть».
- Pre-filter по группам отделений через существующий `OrgScopeFilter` / `org_group_id` (ADR-042, unified org filter).
- Карточка сотрудника: просмотр без edit/transfer/archive/enrollment/account actions.
- API: существующие `GET /directory/employees` с visibility scope (ADR-042 E1).

### «Кадровые процессы»

- Прежний функционал под `/directory/personnel/*` без изменения бизнес-логики.
- Корень `/directory/personnel` — role-aware redirect через `resolvePersonnelRootRedirect` (HR → journal, managers → staff, иначе → tasks).
- Заголовок секции и sub-nav: «Кадровые процессы»; пункт «Сотрудники» убран (перенесён в «Персонал»).

## Frontend guards

- `corpsite-ui/lib/personnelNav.ts` — `canSeePersonnelDirectoryNav`, `canSeeHrProcessesNav`, route helpers.
- `adminNav.isForbiddenAdminRoute` — блокирует HR-маршруты для visibility-only пользователей.
- `visibilityNav.canAccessDirectoryRoute` — разделяет доступ к staff vs personnel.

## Non-goals

- Без миграций БД.
- Без перестройки HR-проcess backend.
- Без изменения sysadmin cabinet.

## Consequences

- Заведующие получают изолированный read-only контур без кадровых действий.
- HR и sysadmin работают в «Кадровых процессах»; HR не видит sysadmin cabinet (как и раньше).
- Дублирование legacy `/directory/employees` сохранено для обратной совместимости; primary entry — `/directory/staff`.
