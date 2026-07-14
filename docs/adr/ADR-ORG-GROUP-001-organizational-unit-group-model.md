# ADR-ORG-GROUP-001 — Organizational Unit Group Model

## Status

**Proposed** — architectural ratification (WP-ORG-GROUP-002)

## Date

2026-07-14

## Related documents

- WP-ORG-GROUP-001 investigation report (conversation, 2026-07-14)
- [ADR-014 — Data Sync Policy](./ADR-014-data-sync-policy.md)
- [ADR-023 — RBAC v2 Lean Scope](./ADR-023-rbac-v2-lean-scope-and-approvals.md)
- [ADR-042 Phase E1 — Visibility Scope](./ADR-042-phase-e1-visibility-scope.md)
- [unified_org_filter.md](./unified_org_filter.md)
- [ARCH-001 — Positions & Org Structure Assessment](../architecture/ARCH-001-positions-org-structure-assessment.md)

---

## Problem

The platform uses two different concepts both named **«group»** with overlapping identifiers (`group_id`):

1. **Organizational classification** — medical org groups (clinical / paraclinical / admin-household) stored in `deps_group` and referenced by `org_units.group_id`.
2. **Deputy RBAC bundles** — cross-cutting sets of org units assigned to a deputy user, stored in `org_unit_groups` + `org_unit_group_units`.

The sysadmin org-units CRUD layer (2026-07-14) validates and resolves `org_units.group_id` against `org_unit_groups`, while the database FK `fk_org_units_group` points to `deps_group`. This causes:

- empty `group_name` in admin API when `org_unit_groups` has no matching rows;
- blocked create/update in admin API when `org_unit_groups` is empty but `deps_group` is populated;
- tests seeding `org_unit_groups` to satisfy incorrect validation;
- operator confusion between «группа отделений» (classification) and «группа подразделений заместителя» (RBAC).

Without a ratified model, future features (Position Cabinet, import sync, visibility) risk repeating the same semantic collision.

---

## Context

### Verified facts (WP-ORG-GROUP-001 + WP-ORG-GROUP-002)

| # | Assertion | Status |
|---|-----------|--------|
| 1 | `org_units.group_id` FK in live DB → `deps_group.group_id` (`fk_org_units_group`) | **CONFIRMED** |
| 2 | Org-scope filter uses `org_units.group_id` (not `org_unit_groups`) | **CONFIRMED** — `app/org_scope/apply.py` |
| 3 | Personnel visibility `DEPARTMENT_GROUP` scope validates against `deps_group` and resolves units via `org_units.group_id` | **CONFIRMED** |
| 4 | `/directory/department-groups` CRUD operates on `deps_group` | **CONFIRMED** |
| 5 | `medical_org_groups.py` is code-level canonical registry for ids 1/2/3 (slug + display name) | **CONFIRMED** |
| 6 | `org_unit_groups` primary runtime use is deputy RBAC (`DIRECTORY_RBAC_MODE=groups`) | **CONFIRMED** — `OrgUnitsService.list_group_unit_ids_for_deputy()` |
| 7 | No production INSERT/UPDATE/DELETE on `org_unit_groups` outside tests | **CONFIRMED** — repo search |
| 8 | Admin org-units service validates `group_id` against `org_unit_groups` and JOINs it for `group_name` | **CONFIRMED** — defect |
| 9 | `org_unit_groups` must never be used for org classification | **CONFIRMED** (normative rule; violation exists in admin service) |

### Domain split

| Layer | Tables / modules | Domain |
|-------|------------------|--------|
| **Organizational model** | `deps_group`, `org_units.group_id`, `medical_org_groups.py` | Structure & classification |
| **Security / RBAC model** | `org_unit_groups`, `org_unit_group_units`, `DIRECTORY_RBAC_MODE` | Deputy scope assignment |
| **Visibility overlay** | `personnel_visibility_assignments` | Read-scope grants (uses org model via `deps_group` + `org_units`) |

---

## Decision

### D1 — Authoritative source for org-unit classification

**`public.deps_group`** is the **single authoritative source** for organizational classification referenced by `org_units.group_id`.

Supporting artifacts:

- **`app/medical_org_groups.py`** — canonical code registry for fixed ids 1/2/3 (slug, Russian display name). Enriches API responses; does not replace `deps_group` as DB master under [ADR-014](./ADR-014-data-sync-policy.md).
- **API surface:** `GET/POST/PATCH/DELETE /directory/department-groups`.

### D2 — Purpose of `org_unit_groups`

**`public.org_unit_groups`** models **deputy RBAC bundles** only:

- one row = one logical bundle with optional `deputy_user_id`;
- membership via **`org_unit_group_units`** (M:N group ↔ unit);
- consumed when `DIRECTORY_RBAC_MODE=groups` to compute directory/task scope for deputy users.

It is **not** a classification dictionary and **must not** be joined to `org_units.group_id`.

**Recommended glossary term (documentation):** *Deputy Unit Bundle* / *Заместительская группа подразделений* — not «группа отделений».

### D3 — Semantic naming rules

| Concept | DB table | API param | UI label (RU) |
|---------|----------|-----------|---------------|
| Org classification group | `deps_group` | `org_group_id`, `group_id` on org unit | Группа отделений |
| Deputy RBAC bundle | `org_unit_groups` | *(no public CRUD yet)* | Заместительская группа |
| Unit membership in bundle | `org_unit_group_units` | — | Связь заместительской группы |

**Invariant:** `org_units.group_id` → `deps_group.group_id`. Never → `org_unit_groups.group_id`.

Even if numeric ids collide (both use 1, 2, 3…), they are **different namespaces** and must not be joined without explicit, documented mapping (none exists today).

### D4 — Admin org-units CRUD contract

Sysadmin org-units API (`/admin/org-units`) must:

- validate `group_id` against **`deps_group`**;
- resolve `group_name` via **`deps_group.group_name`** (with optional `medical_org_groups` enrichment);
- count **`org_unit_group_units`** only as a **delete dependency** (RBAC linkage), not as classification source.

### D5 — Future collision prevention

1. New features referencing «org group» must declare in PR/ADR whether they mean **classification** (`deps_group`) or **deputy bundle** (`org_unit_groups`).
2. Code review checklist: any SQL `JOIN … group_id` on `org_units` must target `deps_group`.
3. Long-term (optional): rename `org_unit_groups` → `deputy_org_unit_bundles` in schema migration to remove homonym.

---

## Consequences

### Positive

- Single authoritative classification path for org-scope, visibility, import, sync.
- Clear separation of org model vs security model.
- Admin UI can drop `resolveGroupLabel()` workaround once API returns correct `group_name`.
- Tests stop seeding wrong table.

### Negative / trade-offs

- Two tables remain (by design); operators need glossary discipline.
- `medical_org_groups.py` and `deps_group` must stay aligned on ids 1/2/3 until dynamic groups are required.
- Deputy RBAC bundles have no admin UI yet; table may stay empty in `dept` mode.

### Known defects to fix (out of scope for this ADR)

| Component | Issue |
|-----------|-------|
| `org_units_admin_service._validate_group_exists` | checks `org_unit_groups` |
| `org_units_admin_service` list/get SQL | `LEFT JOIN org_unit_groups` |
| `tests/test_admin_org_units_crud._ensure_org_group` | seeds `org_unit_groups` |
| `adminOrgUnitsApi.client.ts` dependency label | «Связи с группами отделений» for `org_unit_group_units` — misleading |

---

## Rejected Alternatives

### A — Merge `deps_group` into `org_unit_groups`

**Rejected.** Conflates classification (stable reference data, FK from all org units) with deputy bundles (operational RBAC, sparse, user-bound). Would break ADR-014 sync phases and visibility FK.

### B — Merge into `org_unit_groups` only; drop `deps_group`

**Rejected.** Contradicts live FK, ADR-042 E1, ADR-014, org-scope, and entire `/directory/department-groups` contract.

### C — `org_units.group_id` nullable forever; classification only in code (`medical_org_groups.py`)

**Rejected.** Removes DB-enforced integrity; blocks visibility DEPARTMENT_GROUP scope and VPS sync.

### D — Use `org_unit_groups.name` as display source for admin list

**Rejected.** Wrong table; empty in production; names are bundle labels, not medical org class names.

### E — Immediate schema rename without code fix

**Rejected.** Rename alone does not fix wrong JOIN; causes migration churn before behavior is corrected.

---

## Migration Strategy

Phased work packages (no execution in WP-ORG-GROUP-002):

### WP-ORG-GROUP-003 — Fix Admin CRUD

- `org_units_admin_service`: validation + JOIN → `deps_group`
- Return enriched fields consistent with `/directory/department-groups`
- Fix dependency label in admin UI (deputy bundle wording)

### WP-ORG-GROUP-004 — Fix tests

- Replace `_ensure_org_group()` with `_ensure_deps_group()` or use existing seed ids 1/2/3
- Add negative test: admin create fails when `group_id` not in `deps_group`

### WP-ORG-GROUP-005 — Documentation

- Update ARCH-001 §2.1 org classification row
- Cross-link ADR-014, ADR-023, unified_org_filter
- Glossary in sysadmin runbook

### WP-ORG-GROUP-006 — Regression tests

- Admin list returns non-null `group_name` when `deps_group` populated
- Org-scope + visibility DEPARTMENT_GROUP unchanged
- `DIRECTORY_RBAC_MODE=groups` still uses `org_unit_group_units`

### WP-ORG-GROUP-007 — Schema hygiene (optional, later)

- Add `fk_org_units_group` to Alembic chain if missing on fresh install
- Consider `RENAME org_unit_groups` → `deputy_org_unit_bundles`
- Seed/bootstrap script for `deps_group` in baseline migration

---

## Compatibility

| Consumer | Breaking change if D1 adopted? |
|----------|-------------------------------|
| `/directory/department-groups` | No |
| `/directory/org-units/*` | No |
| `/admin/org-units` | **Behavior fix** — `group_name` populated; stricter validation aligned with FK |
| Org-scope query params | No |
| Personnel visibility | No |
| HR import filters | No |
| `DIRECTORY_RBAC_MODE=groups` | No — uses `org_unit_group_units`, not `org_units.group_id` |
| VPS sync ([ADR-014](./ADR-014-data-sync-policy.md)) | No — already treats `deps_group` as reference master |

---

## Semantic collision register (excerpt)

See WP-ORG-GROUP-002 §4 for full table. Critical entry:

| Symbol | Meaning A | Meaning B | Mitigation |
|--------|-----------|-----------|------------|
| `group_id` on `org_units` | `deps_group` FK (classification) | mistaken join to `org_unit_groups` | ADR D3 invariant + code review |
| `group_id` column name | `deps_group`, `org_unit_groups`, `medical_specialty_groups` | unrelated domains | Prefix in API: `org_group_id`, `specialty_group_id` |
| «Группа отделений» (RU UI) | `deps_group` | `org_unit_group_units` dependency | Glossary + fix labels |

---

## Acceptance criteria (ratification)

- [ ] Engineering acknowledges `deps_group` as authoritative for `org_units.group_id`
- [ ] Engineering acknowledges `org_unit_groups` as deputy RBAC only
- [ ] WP-ORG-GROUP-003..006 scheduled
- [ ] No new code joins `org_units.group_id` to `org_unit_groups`

---

## Appendix — Entity reference

### `deps_group`

- **Models:** medical org classification (reference data)
- **Owner:** HR / org structure administrators via `/directory/department-groups`
- **Domain:** Organizational model
- **Invariants:** `group_id` PK; `group_name` NOT NULL; referenced by `org_units.group_id`, `personnel_visibility_assignments.scope_department_group_id`
- **Writers:** privileged directory API; VPS sync Phase 2 ([ADR-014](./ADR-014-data-sync-policy.md))

### `org_unit_groups` + `org_unit_group_units`

- **Models:** deputy user's bundle of org units for RBAC scope
- **Owner:** Security / directory RBAC configuration (no public CRUD today)
- **Domain:** Security model
- **Invariants:** bundle membership independent of `org_units.group_id`; `deputy_user_id` optional
- **Writers:** manual/SQL or future deputy-admin UI; **not** org-units classification admin

### `org_units`

- **Models:** hierarchical org structure node
- **Owner:** sysadmin + privileged directory operators
- **Domain:** Organizational model
- **Invariants:** single root; `group_id` → `deps_group` when set; tree via `parent_unit_id`
- **Writers:** `/admin/org-units`, `/directory/org-units`

### `personnel_visibility_assignments`

- **Models:** read-scope grant overlay (orthogonal to action access)
- **Owner:** sysadmin visibility tab
- **Domain:** Security overlay on org model
- **Invariants:** `DEPARTMENT_GROUP` scope → `deps_group`; resolution via `org_units.group_id`
- **Writers:** `/admin/personnel/visibility/*`

### `medical_org_groups.py`

- **Models:** immutable code registry for three canonical groups
- **Owner:** Engineering (code deploy)
- **Domain:** Organizational model (presentation + validation layer)
- **Invariants:** ids 1/2/3 align with `deps_group` seed; slugs stable for import filters
- **Writers:** developers only; DB names remain in `deps_group`
