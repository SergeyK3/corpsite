# WP-PPR-MIG-005C — Read-only report API and authorization

| Status | **Completed — Ready for WP-PPR-MIG-005D** |
|---|---|
| Permission | `PPR_MIGRATION_STATUS_READ`; migration assigns a ROLE grant only to `HR_HEAD`. |
| Endpoints | `GET /directory/personnel/migration-status/universes`; `GET /directory/personnel/migration-status` |

The API is read-only. It never rebuilds projection or starts a stage. Permission is evaluated before scope; ADMIN has no implicit bypass. Existing `access_grants` supports future `USER` grants. Scope is injected into SQL before universe visibility, pagination, rows and counts. Responses expose canonical `full_name` only after those gates; they do not expose IIN, raw source, documents, fingerprints or errors.

The matrix contract requires `universe_id`, has page/page_size (max 100), stable `full_name, person_id` sorting and section/status/reason/org-unit/name filters. A cell filter selects matching people while every returned person still has `general`, `education` and `training` cells. Cells contain labels and safe evidence IDs/timestamps. Queries are bounded: universe list plus four report queries, without per-person reads.

Verification completed on isolated `corpsite_test`: HTTP authorization and response-safety contracts, scoped PostgreSQL rows/counts/search/pagination, and a bounded four-query matrix read are covered by `tests/test_ppr_migration_status_report_api.py` and `tests/test_ppr_migration_status_report_postgres.py`. Alembic downgrade/upgrade and single-head checks passed. No report UI, navigation, rebuild endpoint, correction event, or additional permission is included.
