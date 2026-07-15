# ADR-046 F1 — Allowed Positions Deployment Note

**Work package:** WP-ADR-046-F1  
**Alembic revision:** `i9j0k1l2m3n4`  
**Date:** 2026-07-15

## What ships

- Table `public.org_unit_allowed_positions` (junction: org unit ↔ catalog position)
- Read API: `GET /directory/positions?org_unit_id={id}&scope=allowed|used`
- HR pilot seed: `scripts/pilot/hr_department_allowed_positions_seed.sql`
- Frontend consumers switched to `scope=allowed` where appropriate (enroll, transfer, personnel orders, correction drawer)

**Out of scope:** headcount, vacancies, OR registry, admin CRUD UI for allowed links.

## Deployment checklist

1. **Pull** branch with WP-ADR-046-F1.
2. **Backend dependencies** — no new packages expected; verify `requirements.txt` unchanged unless CI reports otherwise.
3. **Migrate:** `alembic upgrade head` (must reach `i9j0k1l2m3n4`).
4. **Restart backend** (FastAPI / uvicorn).
5. **Frontend build/deploy** if UI changed (`corpsite-ui`).
6. **Catalog bootstrap** (if five HR titles missing):
   ```bash
   psql -U postgres -d corpsite -v ON_ERROR_STOP=1 \
     -f scripts/pilot/hr_department_positions_bootstrap.sql
   ```
7. **Allowed positions seed** (post-migration only):
   ```bash
   psql -U postgres -d corpsite -v ON_ERROR_STOP=1 \
     -f scripts/pilot/hr_department_allowed_positions_seed.sql
   ```
8. **Verification queries:**
   ```sql
   -- Table exists
   SELECT to_regclass('public.org_unit_allowed_positions');

   -- HR unit links (resolve unit by code=HR or fallback 73)
   SELECT oap.sort_order, p.name
   FROM public.org_unit_allowed_positions oap
   JOIN public.positions p ON p.position_id = oap.position_id
   WHERE oap.org_unit_id = (
     SELECT unit_id FROM public.org_units
     WHERE lower(trim(code)) = 'hr' AND COALESCE(is_active, TRUE)
     LIMIT 1
   )
   ORDER BY oap.sort_order;
   ```
9. **Smoke-test API:**
   - `GET /directory/positions?org_unit_id=73&scope=allowed` — five HR titles (after seed)
   - `GET /directory/positions?org_unit_id=73` — still **used** semantics (may be empty before hires)
   - `GET /directory/positions` — global catalog unchanged
10. **Smoke-test UI:** Enrollment Wizard / Transfer / Personnel order item — allowed group visible before first hire.

## Rollback

```bash
alembic downgrade h8i9j0k1l2m3
```

Drops `org_unit_allowed_positions`. Does not remove catalog positions or employees.

## Follow-up

- WP-ADR-046-F2: admin CRUD for allowed links
- PositionsPageClient toggle «Используемые / Разрешённые» (optional UI)
