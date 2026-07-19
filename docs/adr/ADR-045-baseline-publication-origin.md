# ADR-045 — HR Control List Baseline & PublicationOrigin

## Статус

**Accepted / In progress** (2026-07-19)

## Решение

Import Batch — временная рабочая область. Baseline — отдельный агрегат утверждённого контрольного списка.

- Baseline **не имеет** `version` и `status`.
- Эталон периода: `resolve_effective_baseline(report_period)` → max(`published_at`) среди `deleted_at IS NULL`.
- `PublicationOrigin` — immutable provenance для кадровых данных (`employee_documents.publication_origin_id`).
- Delete Baseline: soft delete → restore → hard delete (admin). Import Batch delete независим.
- При soft/hard delete baseline: batch получает `diff_status=STALE`, lazy recalc через `ensure_batch_diff_fresh()`.

## Таблицы

| Таблица | Назначение |
|---------|------------|
| `hr_publication_origins` | Immutable provenance |
| `hr_control_list_baselines` | Baseline aggregate (legacy rename from `hr_canonical_snapshots`) |
| `hr_baseline_entries` | Entries (legacy rename from `hr_canonical_snapshot_entries`) |
| `hr_baseline_deletion_log` | Audit soft/hard delete |

## API

| Method | Path | Описание |
|--------|------|----------|
| GET | `/personnel/baselines` | Список baseline |
| GET | `/personnel/baselines/{id}` | Детали |
| POST | `/personnel/baselines/publish` | Publish from batch |
| POST | `/personnel/baselines/{id}/soft-delete` | Soft delete (HR_HEAD) |
| POST | `/personnel/baselines/{id}/restore` | Restore |
| DELETE | `/personnel/baselines/{id}` | Hard delete (admin) |

Archive import batch **снят**. Delete batch всегда разрешён.

## Совместимость

- `hr_canonical_snapshots` / `hr_canonical_snapshot_entries` — read-only VIEW над baseline tables.
- `build_canonical_snapshot_from_batch()` делегирует в `publish_baseline_from_batch()`.
- `snapshot_id` в API responses = `baseline_id`.

## Тесты

- `tests/test_hr_baseline_lifecycle.py` — publish, effective baseline, soft/restore/hard delete
- `tests/test_hr_import_phase_040a_canonical_snapshot.py` — совместимость snapshot API с baseline
- `tests/test_hr_import_analytics.py`, `tests/test_hr_import_phase_2e_operations.py` — batch delete без archive

Клиент API и UI: `importApi.client.ts`, страница `/directory/personnel/baselines`.

Alembic revision `b3c4d5e6f7a8`: rename tables, backfill origins, batch diff columns, FK fixes.
Revision `c4d5e6f7a8b9`: rename baseline `promoted_at/promoted_by` → `published_at/published_by`.
