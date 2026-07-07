# HR Demo — Track B Local Runbook

## Scope

Demonstration-grade MVP (not production):

- **Track B:** `Кадровый журнал` — org-wide `employee_events` register (**production-safe** with migration `b5e2a81d4c03`)

> **ADR-034 demo retired (WP-CLEAN-005B, 2026-07-07):** `GET /directory/professional-documents*` and `professional_documents_service.py` were removed from runtime. Production documents use [ADR-037](../adr/ADR-037-employee-documents-registry.md) — `GET /directory/employee-documents*`. Optional local ADR-034 SQL scripts remain for historical reference only — see [Appendix A](#appendix-a--adr-034-demo-archive-historical).

## Migration strategy

| Layer | VPS / production | Local demo |
|-------|------------------|------------|
| Track B (`employee_events`) | Alembic `b5e2a81d4c03` | Same |
| ADR-034 tables + seed | **Not in Alembic chain; no runtime API** | Optional local SQL only (Appendix A) |

**Production Alembic head:** `b5e2a81d4c03` (`add_employee_events`)

ADR-034 was removed from Alembic (`e4a1c92b7d10` deleted) so `alembic upgrade head` on VPS will never apply demo seed.

**Track B:** no new tables — reads existing `employee_events`.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /directory/personnel-events` | Track B — org-wide journal (privileged) |

**Documents (production, ADR-037):** `GET /directory/employee-documents*`, `GET /directory/document-types`, `GET /directory/medical-specialties` — not part of this demo runbook; see [ADR-037](../adr/ADR-037-employee-documents-registry.md).

## UI routes

| Path | Screen | Visibility |
|------|--------|------------|
| `/directory/personnel` | Track A — employees + sub-nav | Always |
| `/directory/personnel/journal` | Track B — Кадровый журнал | Always |
| `/directory/personnel/documents` | ADR-037 — Реестр документов (production API) | Always |

## Local demo flow

1. **Track A:** Персонал → open employee → «Кадровая история»
2. **Track B:** Персонал → Кадровый журнал → filter / click row
3. **Documents:** Персонал → Реестр документов → production CRUD via ADR-037 API (no demo SQL required)

## Screenshots

Stored in `docs/demo/screenshots/`:

- `demo-track-a-employee-timeline.png`
- `demo-track-b-personnel-journal.png`
- `demo-adr034-professional-documents.png` — **historical** (pre-005B demo UI; retained for archive)

## Tests

```bash
.venv/bin/pytest tests/test_personnel_demo_routes.py -q
```

Covers **personnel-events only** (4 tests). Demo professional-documents route tests removed in WP-CLEAN-005B.

## Explicitly not included

- Export, dashboard counters, advanced RBAC
- Telegram, tasks, notifications
- ADR-034 demo HTTP API (removed 005B)
- `certificate_requirements` table
- ADR-034 in production Alembic chain

---

## Appendix A — ADR-034 demo archive (historical)

> **Status:** Runtime retired (CCR-008, WP-CLEAN-005B). Local SQL scripts may still exist under `scripts/local_demo/` for dev DB archaeology. **Do not** expect demo API or UI probe behavior.

### Local ADR-034 setup (schema + seed) — optional, no API consumer

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
```

**Creates (local only, no runtime reader after 005B):**

| Object | Purpose |
|--------|---------|
| `certificate_types` | Demo document types (`MED_SPEC`, `ACCRED`) |
| `employee_certificates` | Per-employee document records |
| `ix_employee_certificates_employee_type` | Lookup index |

**Former demo API (removed):**

| Endpoint | Former behavior |
|----------|-----------------|
| ~~`GET /directory/professional-documents/availability`~~ | Whether local ADR-034 tables exist |
| ~~`GET /directory/professional-documents`~~ | Demo register |

**Replacement:** [ADR-037](../adr/ADR-037-employee-documents-registry.md) production registry.
