# OO-UI-001 — Developer / Tester UI

## Scope

First working frontend for Operational Orders — internal developer/tester interface to visualize and verify backend workflow without curl or direct DB access. Not production UX.

## Design

Follows corpsite-ui directory patterns (`PersonnelOrdersPageClient`, feature `_lib/*Api.client.ts`, `TaskOrgFiltersBar`, badge/validation panels). Separate bounded area under `/directory/operational-orders` — not mixed with Personnel Orders.

### Route map

| Route | Screen |
|---|---|
| `/directory/operational-orders` | Hub: tabs «Рабочие проекты» / «Официальные документы» |
| `/directory/operational-orders/workspaces/{workspaceId}` | Workspace detail |
| `/directory/operational-orders/documents/{documentId}` | Document detail |

### Component structure

```
corpsite-ui/app/directory/operational-orders/
├── layout.tsx
├── page.tsx
├── workspaces/[workspaceId]/page.tsx
├── documents/[documentId]/page.tsx
├── _lib/ api.ts types.ts status.ts errors.ts permissions.ts mappers.ts
└── _components/ list/detail/badges/validation panels
```

Navigation: `OPERATIONAL_ORDERS_NAV_ITEM` in `PRIMARY_ADMIN_NAV` + HR sidebar via `buildPersonnelSidebarNavItems`, gated by `has_operational_orders_read` / `operational_orders_permissions`.

### Optimistic concurrency

All mutations pass `expected_version` / `expected_document_version` from latest detail load. On 409 conflict — user message + manual refresh; no auto-retry.

### Backend additions (minimal)

1. `GET /api/operational-orders/documents` — document list (was missing)
2. `/auth/me` — `operational_orders_permissions`, `has_operational_orders_read`
3. Workspace list — all stages by default; `document_id`, clarification/translation flags; `promoted` filter

Personnel Orders UI unchanged.

## Deferred

Production UX polish (partially addressed in **OO-UI-001A**), signing/EDS, registration, PDF, revision command, Version 2, notifications, mobile-first redesign.

## Follow-up

**OO-UI-001A** replaces raw JSON workflow blocks with structured cards, timelines, and human-readable labels. See [`OO-UI-001A-workspace-experience-polish.md`](OO-UI-001A-workspace-experience-polish.md).

## Readiness

Ready for commit after review. Not deployed. Production UX iteration is a separate WP.
