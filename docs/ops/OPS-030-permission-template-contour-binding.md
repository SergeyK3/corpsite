# OPS-030 — Permission Template Contour Binding (Phase 2.6b)

## Status

**Placeholder / TODO** — 2026-07-04

Ops runbook for **Phase 2.6b** only. **Not started.** Phase 2.6a engineering support is accepted separately; production template binding is **not complete** until this phase executes.

| Phase | Scope | Status |
|-------|-------|--------|
| **2.6a** | Schema (`access_role_id`, `permission_template_contour_rule`), resolver read-path, shadow taxonomy, idempotent backfill **mechanism**, validation SQL | **Accepted (engineering)** |
| **2.6b** | Approved contour mapping, insert contour rules, apply backfill, validation, shadow parity observation | **Blocked — ADR-053 AC3 Pending** |

## Related documents

| Document | Role |
|----------|------|
| [ADR-053](../adr/ADR-053-permission-template-binding-model.md) | Binding contract; AC3 ops mapping gate |
| [ARCH-001 Permission Template Investigation](../architecture/ARCH-001-permission-template-model-investigation.md) | Backfill derivation principles (§6) |
| `sql/validation/adr053_phase2_6_permission_template_binding_validation.sql` | Post-bind verification queries |

## Preconditions (AC3)

Before production data backfill:

1. Publish and approve **position / staffing contour → `access_role_id`** mapping annex (this runbook body).
2. Document explicit exception list for ambiguous `(org_unit_id, catalog_position_id)` pairs.
3. Confirm ADR-053 AC3 sign-off (mapping annex approved by ops + architecture).

**Do not** derive bindings from `users.role_id`, user-specific `access_grants`, or current Cabinet occupant.

## Phase 2.6b procedure (TODO — draft outline)

### Step 1 — Prepare approved mapping

- [ ] Inventory org-unique positions requiring baseline access role binding.
- [ ] Map each `(client_scope_id, org_unit_id, catalog_position_id)` to intended `access_roles.access_role_id`.
- [ ] Record exceptions and rationale in this document (or linked annex).

### Step 2 — Insert contour rules

Insert approved rows into `public.permission_template_contour_rule`:

```sql
-- Example shape only — replace IDs/codes with approved mapping values.
INSERT INTO public.permission_template_contour_rule (
    client_scope_id,
    org_unit_id,
    catalog_position_id,
    access_role_id,
    is_active,
    notes
)
VALUES (
    1,
    :org_unit_id,
    :catalog_position_id,
    (SELECT access_role_id FROM public.access_roles WHERE code = :access_role_code AND is_active),
    TRUE,
    'OPS-030 approved mapping'
);
```

**No seed data** is shipped with migrations; contour rules are ops-authored only.

### Step 3 — Apply backfill

Re-run the idempotent backfill after contour rules exist:

```bash
# If Alembic head already includes n8o9p0q1r2s3, downgrade one revision and upgrade:
alembic downgrade m7n8o9p0q1r2
alembic upgrade n8o9p0q1r2s3
```

Alternatively execute the `UPDATE` from migration `n8o9p0q1r2s3_adr053_phase2_6_permission_template_binding_backfill.py` manually in a controlled ops window.

Expected: `permission_template.access_role_id` populated only for contours with active rules.

### Step 4 — Run validation SQL

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f sql/validation/adr053_phase2_6_permission_template_binding_validation.sql
```

Review:

- Section 2: `templates_unmapped` should decrease per approved coverage (zero unmapped is target steady state per ADR-053 R5).
- Sections 4–7: must return no violating rows.

### Step 5 — Observe shadow parity

With `CABINET_ACCESS_SHADOW_MODE=true`:

- Grep application logs for `cabinet_access_shadow outcome=match|mismatch`.
- Expect `permission_template_unmapped` to decrease for bound contours.
- Legacy authorization remains authoritative; shadow is diagnostic only.

## Rollback (2.6b data only)

```bash
alembic downgrade m7n8o9p0q1r2   # clears access_role_id via backfill downgrade
```

Or:

```sql
UPDATE public.permission_template SET access_role_id = NULL, updated_at = now()
WHERE access_role_id IS NOT NULL;
```

Auth impact: **none** — legacy path unchanged.

## Open items

- [ ] Approved contour mapping annex (AC3 deliverable)
- [ ] Sign-off checklist
- [ ] Production execution record
