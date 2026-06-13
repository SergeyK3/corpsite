# HR Demo — Track B + ADR-034 Local Runbook

## Scope

Demonstration-grade MVP (not production):

- **Track B:** `Кадровый журнал` — org-wide `employee_events` register (**production-safe** with migration `b5e2a81d4c03`)
- **ADR-034 demo:** `Профессиональные документы` — **local-demo-only** (`certificate_types` + `employee_certificates`)

## Migration strategy

| Layer | VPS / production | Local demo |
|-------|------------------|------------|
| Track B (`employee_events`) | Alembic `b5e2a81d4c03` | Same |
| ADR-034 tables + seed | **Not in Alembic chain** | SQL scripts under `scripts/local_demo/` |

**Production Alembic head:** `b5e2a81d4c03` (`add_employee_events`)

ADR-034 was removed from Alembic (`e4a1c92b7d10` deleted) so `alembic upgrade head` on VPS will never apply demo seed.

### Local ADR-034 setup (schema + seed)

```bash
cd /opt/projects/corpsite/app
# Use the same DATABASE_URL as the app (.env)
psql "$DATABASE_URL" -f scripts/local_demo/adr034_professional_documents_schema.sql
psql "$DATABASE_URL" -f scripts/local_demo/adr034_professional_documents_seed.sql
```

### Local ADR-034 rollback

```bash
psql "$DATABASE_URL" -f scripts/local_demo/adr034_professional_documents_rollback.sql
```

### If local DB still shows `e4a1c92b7d10` in `alembic_version`

The old demo migration is gone from the repo. Reconcile with:

```bash
psql "$DATABASE_URL" -f scripts/local_demo/adr034_professional_documents_rollback.sql  # optional cleanup
.venv/bin/python -c "
from alembic.config import Config
from alembic import command
from app.db.engine import engine
cfg = Config('alembic.ini')
cfg.set_main_option('sqlalchemy.url', str(engine.url.render_as_string(hide_password=False)))
command.stamp(cfg, 'b5e2a81d4c03')
"
# Re-apply local demo if needed:
psql "$DATABASE_URL" -f scripts/local_demo/adr034_professional_documents_schema.sql
psql "$DATABASE_URL" -f scripts/local_demo/adr034_professional_documents_seed.sql
```

**Creates (local only):**

| Object | Purpose |
|--------|---------|
| `certificate_types` | Demo document types (`MED_SPEC`, `ACCRED`) |
| `employee_certificates` | Per-employee document records |
| `ix_employee_certificates_employee_type` | Lookup index |

**Seed data:**

- 4 `employee_certificates` rows (`DEMO-*` numbers) with statuses: VALID, ≤60d, ≤30d, EXPIRED
- Active employees without `MED_SPEC` appear as **Нет данных** in UI (computed)

**Track B:** no new tables — reads existing `employee_events`.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /directory/personnel-events` | Track B — org-wide journal (privileged) |
| `GET /directory/professional-documents/availability` | Whether local ADR-034 tables exist |
| `GET /directory/professional-documents` | Demo register; returns empty + `available: false` when tables absent |

## UI routes

| Path | Screen | Visibility |
|------|--------|------------|
| `/directory/personnel` | Track A — employees + sub-nav | Always |
| `/directory/personnel/journal` | Track B — Кадровый журнал | Always |
| `/directory/personnel/documents` | ADR-034 — Профессиональные документы | Nav hidden unless demo tables exist |

## Local demo flow

1. **Track A:** Персонал → open employee → «Кадровая история»
2. **Track B:** Персонал → Кадровый журнал → filter / click row
3. **ADR-034:** apply local SQL scripts → Персонал → Профессиональные документы → status colors

## Screenshots

Stored in `docs/demo/screenshots/`:

- `demo-track-a-employee-timeline.png`
- `demo-track-b-personnel-journal.png`
- `demo-adr034-professional-documents.png`

## Tests

```bash
.venv/bin/pytest tests/test_personnel_demo_routes.py -q
```

## Explicitly not included

- Export, dashboard counters, advanced RBAC
- Telegram, tasks, notifications
- `certificate_requirements` table
- Production CRUD for documents
- ADR-034 in production Alembic chain
