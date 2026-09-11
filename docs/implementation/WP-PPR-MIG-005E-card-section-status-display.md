# WP-PPR-MIG-005E — Card section status display

| Status | **Completed — Ready for WP-PPR-MIG-005F** |
|---|---|
| Endpoint | `GET /directory/personnel/migration-status/persons/{person_id}?universe_id=` |

The endpoint uses `PPR_MIGRATION_STATUS_READ` and SQL org scope, returns a safe exact-person slice of only `general`, `education`, and `training` cells, and returns 404 for unknown or inaccessible person/universe. It has no mutation or rebuild path.

The PPR-safe card link includes `migration_universe_id` and preserves the relative encoded report `return_to`. Card blocks are read-only and display backend status/reason text and calculated time. They never expose PII, fingerprints, source payloads, or documents.
