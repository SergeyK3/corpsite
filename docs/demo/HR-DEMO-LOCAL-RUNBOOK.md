# HR Demo — Track B + ADR-034 Local Runbook

## Scope

Demonstration-grade MVP (not production):

- **Track B:** `Кадровый журнал` — org-wide `employee_events` register
- **ADR-034 demo:** `Профессиональные документы` — `certificate_types` + `employee_certificates`

## Migration summary

**Revision:** `e4a1c92b7d10` (`add_professional_documents_demo`)

**Creates:**

| Object | Purpose |
|--------|---------|
| `certificate_types` | Demo document types (`MED_SPEC`, `ACCRED`) |
| `employee_certificates` | Per-employee document records |
| `ix_employee_certificates_employee_type` | Lookup index |

**Seed data:**

- 4 `employee_certificates` rows (`DEMO-*` numbers) with statuses: VALID, ≤60d, ≤30d, EXPIRED
- Active employees without `MED_SPEC` appear as **Нет данных** in UI (computed)

**Track B:** no new tables — reads existing `employee_events`.

### Apply (local)

```bash
cd /opt/projects/corpsite/app
# If alembic.ini DATABASE_URL differs from app .env:
.venv/bin/python -c "
from alembic.config import Config
from alembic import command
from app.db.engine import engine
cfg = Config('alembic.ini')
cfg.set_main_option('sqlalchemy.url', str(engine.url.render_as_string(hide_password=False)))
command.upgrade(cfg, 'head')
"
```

### Rollback

```bash
.venv/bin/alembic downgrade b5e2a81d4c03
```

Or manual:

```sql
DELETE FROM employee_certificates WHERE certificate_number LIKE 'DEMO-%';
DROP TABLE IF EXISTS employee_certificates;
DELETE FROM certificate_types WHERE code IN ('MED_SPEC', 'ACCRED');
DROP TABLE IF EXISTS certificate_types;
```

**Note:** Track B API/routes are code-only; rollback migration does not remove them.

## API (privileged demo)

| Endpoint | Description |
|----------|-------------|
| `GET /directory/personnel-events` | Org-wide journal; filters: `event_type`, `date_from`, `date_to` |
| `GET /directory/professional-documents` | Demo documents register with computed statuses |

## UI routes

| Path | Screen |
|------|--------|
| `/directory/personnel` | Track A — employees + sub-nav |
| `/directory/personnel/journal` | Track B — Кадровый журнал |
| `/directory/personnel/documents` | ADR-034 — Профессиональные документы |

Row click → `EmployeeDrawer` (Track A continuity).

## Local demo flow

1. **Track A:** Персонал → open employee → «Кадровая история»
2. **Track B:** Персонал → Кадровый журнал → filter / click row
3. **ADR-034:** Персонал → Профессиональные документы → status colors

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
