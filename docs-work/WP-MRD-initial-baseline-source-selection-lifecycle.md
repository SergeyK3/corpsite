# WP-MRD — Initial Baseline Source Selection Lifecycle

Status: **Accepted interim workflow** (2026-07-19)

Related: [ADR-058](../docs/adr/ADR-058-monthly-reference-dataset-architecture.md) (D8 bootstrap, D9 no publish from batch)

## Purpose

`hr_initial_baseline_source_selections` stores the **operator's current choice** of import batch
(`2606-01` vs `2606-02`) while preparing the **first MRD** for a report period.

This table is a **temporary workflow pointer**, not the authoritative link period ↔ batch.

## Lifecycle

```text
[No selection]
  → operator clicks «Выбрать» on Import page
  → row lifecycle_status = ACTIVE

[ACTIVE, no MRD versions for period]
  → operator may switch batch (UPSERT same report_period)
  → selected batch cannot be deleted (FK RESTRICT + delete assessment)

[create_initial_mrd_from_review — not implemented yet]
  → hr_monthly_references.source_batch_id = chosen batch
  → hr_reference_version_events CREATE with event_context.source_batch_id
  → consume selection: lifecycle_status = CONSUMED, consumed_mrd_id set

[CONSUMED or any MRD row for period]
  → selection is frozen (POST blocked) — including all-CLOSED periods
  → SoT = MRD provenance + version events, not this table
```

## Invariants

| Rule | Enforcement |
|------|-------------|
| One row per `report_period` | PK on `report_period` |
| Mutable only before first MRD | `lifecycle_status = ACTIVE` AND no `hr_monthly_references` row for period |
| Frozen after first CREATE | any MRD version for period OR `lifecycle_status = CONSUMED` |
| No silent batch delete | `source_batch_id` FK `ON DELETE RESTRICT` |
| Provenance after CREATE | `hr_monthly_references.source_batch_id` (nullable, populated by future command) |

## API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/directory/personnel/import/initial-baseline-source` | Returns `lifecycle_status`, `mutable` |
| POST | `/directory/personnel/import/initial-baseline-source` | 409 if frozen |

## Retirement

After `create_initial_mrd_from_review` is live, this table remains for audit of pre-CREATE choice
(CONSUMED rows). UI reads **mutable ACTIVE** selections only for «Для эталона» column.
