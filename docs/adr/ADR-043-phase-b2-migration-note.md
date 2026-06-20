# ADR-043 Phase B2 — Migration Note

## Статус

**Implemented** (2026-06-20)

## Alembic revision

| Revision | File | Depends on |
|----------|------|------------|
| `x6y7z8a9b0c1` | `alembic/versions/x6y7z8a9b0c1_adr043_phase_b2_personnel_lifecycle_schema.py` | `w5x6y7z8a9b0` |

```bash
alembic upgrade head
```

## Deliverables

| Artifact | Path |
|----------|------|
| DDL migration | `alembic/versions/x6y7z8a9b0c1_adr043_phase_b2_personnel_lifecycle_schema.py` |
| Validation SQL | `docs/adr/ADR-043-phase-b2-validation.sql` |
| Schema tests | `tests/test_adr043_phase_b2_schema.py` |

## Tables created

- `hr_source_files`
- `hr_override_stewardship_rules` (+ seed)
- `hr_review_overrides`
- `hr_review_override_history` (+ append-only trigger)
- `hr_personnel_change_events`
- `hr_snapshot_effective_entries`

## ALTER

- `hr_import_batches.source_file_id`
- `enrollment_queue.personnel_event_id`

## B2 clarifications (vs B1 draft)

| Topic | Decision |
|-------|----------|
| Active override uniqueness | **Separate** partial uniques: one `active`, one `pending_approval` per `(scope_key, field_path)` |
| Pending replacement | `supersedes_override_id` → active override being replaced; pending **не** участвует в Effective Value |
| `scope_key` format | `PERSON:…`, `ASSIGNMENT:…`, `DOCUMENT:…`, `TRAINING:…`, `CERTIFICATE:…`, `CATEGORY:…` |
| History append-only | **Trigger** `trg_hroh_append_only` (not PostgreSQL RULE — RULE breaks FK checks on `users`) |
| Effective cache freshness | `override_version_hash` + `override_ids` + `computed_at` + `payload_hash` |

## Stewardship seed

12 rules inserted idempotently (identity Tier 2 / HR, roster Tier 1, specialty/category/training owners, fallback `%`).

## Validation

```bash
psql $DATABASE_URL -f docs/adr/ADR-043-phase-b2-validation.sql
```

Empty result sets = OK for violation queries.

## Tests

```bash
python -m pytest tests/test_adr043_phase_b2_schema.py -v
```

## Out of scope (Phase B3+)

- Override service / diff integration
- Person sync job
- Personnel event materialization
- Enrollment detector on `personnel_event_id`
- Backfill from `_canonical_correction_fields`

## Rollback

```bash
alembic downgrade w5x6y7z8a9b0
```

Drops all ADR-043 B2 objects; removes `source_file_id` and `personnel_event_id` columns.
