# WP-PPR-MIG-005B — Safe persisted status projection read model

| Параметр | Значение |
|---|---|
| Статус | **Completed — Ready for WP-PPR-MIG-005C** |
| Основание | [WP-PPR-MIG-005](WP-PPR-MIG-005-migration-status-matrix-plan.md), [WP-PPR-MIG-005A](WP-PPR-MIG-005A-status-semantics.md) |
| Scope | Persisted safe read model и transactional rebuild; без API, UI, permissions или automatic backfill. |

## Schema

- `ppr_migration_status_universes`: immutable hash identity `BASE + explicit SUPPLEMENTAL` cohorts.
- `ppr_migration_status_universe_cohorts`: members universe с ролью `BASE` или `SUPPLEMENTAL`.
- `ppr_migration_section_status_projection`: одна строка `(universe_id, person_id, section_code)` для `general`, `education`, `training`.

Проекция хранит только IDs, org-unit context, status/reason, ссылки на stage/PMF evidence, policy/parser versions, fingerprints, timestamp и row version. В ней нет ФИО, ИИН, raw source/document или кадровых values. Alembic migration создаёт пустую схему и не запускает backfill.

## Rebuild contract

`ensure_universe` validates BASE и explicit supplemental attachment. `rebuild_universe` читает только participants active universe, в одной транзакции удаляет прошлый snapshot universe и вставляет ровно три section rows для каждого participant. Повторный запуск не создаёт дубликатов; ошибка откатывает весь rebuild. Cancelled runs не выбираются. Projection supports future scoped reads through `org_unit_id`, but exposes no API.

## Current evidence limits

Backfill can recover `NOT_STARTED`, `PROCESSING`, `AUTO_READY`, `ERROR`, `BLOCKED`, `STALE` and participant-evidenced `ACCEPTED`. `CORRECTED_BY_HR` is intentionally never generated: `PPR_SECTION_MANUAL_CORRECTED` does not exist. `NO_SOURCE_DATA`/`NOT_APPLICABLE` require explicit future evidence not universally represented by current Stage facts, so the conservative fallback remains `NOT_STARTED`/`AUTO_READY`. Empty `general` is never accepted; a section-empty `ACCEPTED` is only accepted where current participant evidence proves it.

## Verification gate

Проверены unit и изолированные PostgreSQL contracts на loopback `corpsite_test`: universe identity и supplemental membership, unique `Person × section`, idempotent rebuild, cancelled latest run, source/policy invalidation, transactional rollback, org scope и отсутствие PII-колонок. Alembic прошёл upgrade → downgrade на один revision → повторный upgrade; repository имеет single head `ppr005bproj01`.

## WP-005C limitations

WP-005C must add a separately authorized report API, pagination/filter contract and scoped RBAC integration. It must not infer correction events, expose personal data, or convert this projection into a write path.
