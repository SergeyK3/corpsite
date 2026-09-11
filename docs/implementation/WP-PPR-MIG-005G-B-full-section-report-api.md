# WP-PPR-MIG-005G-B — full-section report API

| Параметр | Значение |
|---|---|
| Статус | **Completed — frontend expansion pending** |
| Основание | [WP-005G](WP-PPR-MIG-005G-full-section-matrix-plan.md), [WP-005G-A](WP-PPR-MIG-005G-A-full-section-projection.md) |
| Scope | Read-only matrix и person-status API для десяти persisted section cells; без frontend, rebuild или новых permissions. |

## Контракт

`GET /directory/personnel/migration-status?universe_id={id}` возвращает по каждой
matrix row `cells` в следующем неизменном порядке:

```text
general, education, training, relatives, military,
employment_biography, employment_history, foreign_languages,
awards, academic_degrees_titles
```

`GET /directory/personnel/migration-status/persons/{person_id}?universe_id={id}`
возвращает тот же упорядоченный набор десяти cells без ФИО. Оба endpoint читают
только persisted projection; они не запускают rebuild, stage или mutation и не
создают fallback cells.

Каждая cell содержит только safe status/reason codes, backend labels, timestamp и
разрешённые evidence IDs. В ответах отсутствуют ИИН, fingerprints, raw payload,
документы, кадровые значения и внутренние ошибки. Canonical ФИО matrix row
по-прежнему присоединяется после permission и org-scope check; person endpoint
вообще не возвращает identity.

## Integrity contract

Все десять cells обязательны для каждого видимого `person_id` active universe.
Если projection неполна, report service поднимает `ProjectionIntegrityError`; HTTP
router возвращает безопасный `409` с code
`MIGRATION_STATUS_PROJECTION_INTEGRITY_ERROR`. Он не подменяет отсутствие строки
выдуманным `NOT_STARTED` и не раскрывает, какая внутренняя запись повреждена.

## Сохранённые гарантии

- `PPR_MIGRATION_STATUS_READ`, персональные grants и отсутствие ADMIN bypass не изменены.
- Universe visibility, org scope, pagination, status/reason/name/org-unit filters и
  canonical name join сохраняются.
- Section filter принимает все десять codes из единого
  `PPR_MIGRATION_SECTIONS` catalog.
- Seven пока неподключённых persisted cells остаются
  `NOT_STARTED` / `SECTION_PROCESSING_NOT_CONNECTED`; `NOT_APPLICABLE` не
  синтезируется без policy-rule.
- Matrix remains bounded: integrity, universe visibility, rows, aggregates and
  total use a fixed five-query read rather than per-person queries.

## Verification

На loopback `corpsite_test` прошли HTTP и PostgreSQL tests: stable full-catalog
order, section filter `awards`, person slice, scope/permission isolation,
absence of IIN and response secrets, safe integrity error и bounded query count.
