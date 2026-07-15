# ADR-046 — Org-unit allowed positions

**Status:** Accepted — Implemented by WP-ADR-046-F1 (2026-07-15)  
**Date:** 2026-06-22 (proposed); 2026-07-15 (F1 implementation)  
**Related:** ADR-031, ADR-045, ADR-050, ADR-053, ADR-055, `GET /directory/positions`

## Context

Corpsite stores official titles in global `public.positions`. Before F1, org-unit filtering on `GET /directory/positions?org_unit_id=` returned only positions **already used** by employees (`EXISTS` on `employees`).

Phase 3I interim fix (`103be25`) added global-catalog fallback in Enrollment Wizard when scoped list was empty — UX relief, not a staffing model.

## Decision

Introduce explicit junction **`org_unit_allowed_positions`**: which catalog positions are **allowed / typical** for a given org unit, separate from occupancy.

### Semantic layers

```text
public.positions                     — global official catalog
org_unit_allowed_positions           — allowed for org unit (F1)
employees / person_assignments       — actual assignments
Operational Role (ADR-055, future)   — duty/function layer
```

| Layer | Question |
|-------|----------|
| Global catalog | What titles exist organization-wide? |
| **Allowed** | What titles may be assigned in this unit? |
| **Used** | What titles are already held by employees in scope? |
| Employment | Who holds which title, when? |

**Headcount (1/4/4/3/1 for HR)** is informational only — not stored in F1.

## Implemented schema (F1)

Table `public.org_unit_allowed_positions`:

| Column | Purpose |
|--------|---------|
| `org_unit_allowed_position_id` | Surrogate PK |
| `org_unit_id` | FK → `org_units` **ON DELETE RESTRICT** |
| `position_id` | FK → `positions` **ON DELETE RESTRICT** |
| `sort_order` | Stable UI ordering |
| `is_active` | Soft-disable link without delete |
| `created_at` / `updated_at` | Audit timestamps |

Constraints: `UNIQUE (org_unit_id, position_id)`; indexes on `org_unit_id`, `position_id`, `(org_unit_id, sort_order)`.

**No parent-subtree inheritance** for `scope=allowed` — links apply to the selected unit directly.

## API (F1 read path)

| Request | Semantics |
|---------|-----------|
| `GET /directory/positions` | Global catalog (unchanged) |
| `GET /directory/positions?org_unit_id=N` | **Default = used** (backward compatible) |
| `GET /directory/positions?org_unit_id=N&scope=used` | Explicit used (employees) |
| `GET /directory/positions?org_unit_id=N&scope=allowed` | Active rows from junction |
| `scope=allowed` without `org_unit_id` / `org_group_id` | **422** |

Unknown `scope` → **422**.

## HR pilot (F1)

1. Catalog: `scripts/pilot/hr_department_positions_bootstrap.sql` (ADR-055, commit `77fb923`)
2. Allowed links: `scripts/pilot/hr_department_allowed_positions_seed.sql` (post-migration)

Five titles; unit resolved by `code='HR'` with guarded fallback `unit_id=73`.

## Frontend consumers (F1)

| Consumer | Scope |
|----------|-------|
| ImportEnrollEmployeeWizard, PersonnelOrderItemEditor | `allowed` + global fallback group |
| EmployeeAssignmentCorrectionDrawer | `allOptions` (allowed + global) |
| EmployeeCreateForm, EmployeeTransferForm | `allowed` + global fallback |
| TaskOrgFiltersBar | **`used`** (unchanged) |
| PositionsPageClient | **`used`** (unchanged; toggle = follow-up) |

Fallback rule: if allowed list empty → global catalog (transitional; does not hide configured allowed group when non-empty).

## Out of scope (F1)

- Staffing headcount / vacancies / штатное расписание
- Org-unique Position redesign (ADR-050)
- Operational Role registry (ADR-055)
- Admin CRUD UI for allowed links
- Automatic inheritance along org tree
- Backfill allowed links from employee history

## Implementation phases

| Phase | Status |
|-------|--------|
| **F1 Schema + ORM + read API + HR seed + consumers** | **Done** (WP-ADR-046-F1) |
| F2 Admin API / CRUD junction | Backlog |
| F3 Positions admin UI toggle allowed/used | Backlog |
| F4 Bulk import / org templates | Backlog |

## References

- `alembic/versions/i9j0k1l2m3n4_adr046_f1_org_unit_allowed_positions_schema.py`
- `app/services/org_unit_allowed_positions_service.py`
- `app/directory/positions_routes.py`
- `docs/ops/ADR-046-F1-allowed-positions-deployment.md`
- ADR-055 Operational Role architecture

## Tracking

| Event | Date |
|-------|------|
| ADR proposed (Phase 3I audit) | 2026-06-22 |
| Interim global fallback (`103be25`) | 2026-06-22 |
| ADR-055 catalog bootstrap (`77fb923`) | 2026-07-15 |
| **F1 implemented (WP-ADR-046-F1)** | 2026-07-15 |
