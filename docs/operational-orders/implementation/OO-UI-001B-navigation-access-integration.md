# OO-UI-001B — Navigation & Access Integration

## Scope

Integrate Operational Orders into corpsite navigation and access model as a **standalone Document Domain** (UDE), not nested under Personnel Orders / HR processes. No workflow, lifecycle, or domain changes.

## Problem (before)

1. «Производственные приказы» appeared inside HR navigation via `buildPersonnelSidebarNavItems`, implying Personnel Orders coupling.
2. HR heads (`has_personnel_admin`) saw «Нет доступа» without explanation — technically correct (no OO grants) but poor integration.

## Navigation architecture (after)

Sidebar hierarchy (when permissions allow):

| Order | Node | Gated by |
|---|---|---|
| 1 | Персонал | `canSeePersonnelDirectoryNav` |
| 2 | Кадровые процессы | `canSeeHrProcessesNav` |
| 3 | **Производственные приказы** | `has_operational_orders_read` |
| 4 | Контакты | E1 visibility extras |
| 5 | Должности | E1 visibility extras |

Operational Orders is a **sibling top-level node** — not inside «Кадровые процессы», not a new «Документы» app.

Admin shell (`PRIMARY_ADMIN_NAV`) keeps the same ordering; visibility shell uses `buildDirectorySidebarNavItems`.

## Visibility model

| Flag | Source | Purpose |
|---|---|---|
| `has_operational_orders_read` | `GET /auth/me` via `auth_projection.has_any_operational_orders_read` | Section nav + route access |
| `operational_orders_permissions.*` | `build_operational_orders_permissions` | Action gating inside UI |

**Not used for OO visibility:** `has_personnel_admin`, `has_personnel_visibility`, `has_personnel_access`.

Frontend `canSeeOperationalOrdersNav` now trusts **only** `has_operational_orders_read` (or `is_privileged`).

## Permission review

| Permission | Backend | Frontend nav | Frontend actions | Comment |
|---|---|---|---|---|
| `OPERATIONAL_ORDERS_INTAKE_READ` | list/read workspace & document | via projection | list views | **Minimum recommended for section access** |
| `OPERATIONAL_ORDERS_INTAKE_CREATE` | create workspace | — | — | Not required for nav |
| `OPERATIONAL_ORDERS_INTAKE_OPERATE` | mutate intake | via projection | edit blocks, clarifications | Also grants nav read projection |
| `OPERATIONAL_ORDERS_TRANSLATION_ASSIGN` | assign/cancel | — | translation assign | Action only |
| `OPERATIONAL_ORDERS_TRANSLATION_WORK` | accept/start/complete | — | translator actions | Action only |
| `OPERATIONAL_ORDERS_CONTENT_CONFIRM` | confirm/revoke | — | confirmations | Action only |
| `OPERATIONAL_ORDERS_RECONCILE` | reconcile/invalidate | — | reconciliations | Action only |
| `OPERATIONAL_ORDERS_EDITORIAL_READY` | mark editorial ready | — | editorial ready button | Action only |
| `OPERATIONAL_ORDERS_PROMOTE` | promote | via projection | promote | Also grants nav read projection |
| `OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ` | readiness read | via projection | readiness preview | Also grants nav read projection |
| `OPERATIONAL_ORDERS_ASSIGN_SIGNING_AUTHORITY` | assign authority | — | signing authority | Action only |
| `OPERATIONAL_ORDERS_MARK_READY_FOR_SIGNATURE` | ready transition | — | ready button | Action only |
| `OPERATIONAL_ORDERS_RETURN_FROM_SIGNATURE` | return to CREATED | — | return button | Action only |

**Projection `has_operational_orders_read`** is true when any of: intake_read, intake_operate, promote, signature_readiness_read.

## Minimum access policy (implemented)

To **see** the section: `has_operational_orders_read === true` (typically grant `OPERATIONAL_ORDERS_INTAKE_READ`).

Not required for nav: promote, operate, signing, editorial, translation.

## HR access recommendation (not auto-applied)

For **Руководитель отдела кадров** (HR head / `has_personnel_admin`):

**Recommend granting:**
- `OPERATIONAL_ORDERS_INTAKE_READ` — view workspaces and documents
- optionally `OPERATIONAL_ORDERS_SIGNATURE_READINESS_READ` — view readiness state on documents

**Do not grant by default:** translation, promote, ready-for-signature, signing authority, editorial mutations.

This WP does **not** change production role grants — only documents the recommendation.

## Developer diagnostics

When access is denied, `AccessDeniedPanel` shows a user-friendly explanation. In `NODE_ENV=development`, a collapsible **Developer diagnostics** block lists:

- projection flags (`has_operational_orders_read`, `intake_read`, …)
- missing recommended permission
- HR vs OO note when `has_personnel_admin`
- optional HTTP status / error code / endpoint (403 paths)

Production users see the explanation only.

## Backend changes

Minimal — docstring on `has_any_operational_orders_read` in `auth_projection.py`. No domain/service changes.

## Frontend changes

- `personnelNav.ts` — `buildDirectorySidebarNavItems`; OO removed from personnel-only builder
- `operationalOrdersNav.ts` — icon id on nav item
- `OperationalOrdersNavIcon.tsx` — sidebar icon
- `AppShell.tsx` — icon rendering; directory sidebar includes OO routes
- `permissions.ts` — nav gating via projection only
- `accessDiagnostics.ts`, `AccessDeniedPanel.tsx` — access UX
- `OperationalOrdersLayoutShell.tsx` — layout-level access gate
- `OperationalOrdersSectionHeader.tsx` — production-oriented subtitle

## Tests

- `operationalOrdersNav.test.ts`
- `personnelNav.test.ts` (OO placement)
- `visibilityNav.test.ts` (OO route gating)
- `accessDiagnostics.test.ts`
- `AccessDeniedPanel.test.ts`
- `permissions.test.ts` (updated)

## Deferred

- Automatic HR role grant migration
- Admin UI for OO permission assignment
- OO-IMP-005

## Readiness

Ready for commit after review. Not deployed.
