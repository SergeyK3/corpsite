# WP-PPR-MIG-005G-A — full-section persisted projection

| Параметр | Значение |
|---|---|
| Статус | **Completed — Ready for WP-PPR-MIG-005G-B** |
| Основание | [WP-PPR-MIG-005G](WP-PPR-MIG-005G-full-section-matrix-plan.md) |
| Scope | Расширение безопасной `Person × section` projection с трёх до десяти разделов; без report API и frontend. |

## Реализованный контракт

`ppr_migration_section_status_projection.section_code` принимает только:

```text
general, education, training, relatives, military,
employment_biography, employment_history, foreign_languages,
awards, academic_degrees_titles
```

Rebuild active universe создаёт ровно десять строк на `person_id`. Логика и
результаты `general`, `education`, `training` не меняются. Семь новых разделов
пока не выполняют source/stage lookup и получают безопасный persisted результат:

```text
status_code = NOT_STARTED
reason_code = SECTION_PROCESSING_NOT_CONNECTED
```

`NOT_APPLICABLE` здесь не синтезируется: он потребует отдельного явного policy-rule.
Пустой раздел не является таким rule.

## Migration и backfill

Revision `ppr005gfull01` заменяет только section check constraint и добавляет
недостающие семь строк к существующим `(universe_id, person_id)` из legacy
projection. Backfill использует только уже сохранённые технические IDs и hashes:
не читает source payload и не переносит ФИО, ИИН, кадровые значения, документы или
raw payload. `ON CONFLICT DO NOTHING` делает его повторяемым.

Downgrade намеренно отказывается выполняться, если существуют новые section rows:
данные full catalog не удаляются молча.

## Verification

На isolated loopback `corpsite_test` прошли unit и PostgreSQL contracts:
10 rows per person, сохранение существующего `general` acceptance, добавление семи
catalog rows из legacy three-row snapshot, повторяемый rebuild/backfill и primary-key
unique invariant `(universe_id, person_id, section_code)`.

## Ограничения следующих пакетов

API и UI пока остаются трёхсекционными: их расширение до десяти cells — отдельная
работа. Реальные processors, fingerprints, accepted evidence, policy applicability
и targeted invalidation для семи новых sections также не входят в WP-005G-A.
