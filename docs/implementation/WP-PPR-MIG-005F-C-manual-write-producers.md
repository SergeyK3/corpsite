# WP-PPR-MIG-005F-C — Manual write producers

| Parameter | Value |
|---|---|
| Status | **Deferred — no confirmed manual canonical writers** |
| Parent | [WP-PPR-MIG-005F](WP-PPR-MIG-005F-corrections-invalidation-plan.md) |
| Depends on | [WP-005F design](WP-PPR-MIG-005F-corrections-invalidation-plan.md), [WP-005F-A event/outbox schema](WP-PPR-MIG-005F-A-event-outbox-schema.md), [WP-005F-B worker](WP-PPR-MIG-005F-B-targeted-projector-worker.md) |

## Deferral decision

WP-005F inventory confirms no safe, existing manual canonical writer for all three v1 sections:

- `general` currently reaches canonical facts only through Stage 1 acceptance;
- `education` has a service-level profile updater, but no confirmed public manual edit path with permission and org-scope contract;
- `training` has no confirmed manual canonical editor.

Stage 1–3 and PMF writes are automated migration paths. They **must not** emit `PPR_SECTION_MANUAL_CORRECTED` and must not be used as a source of `CORRECTED_BY_HR`.

Implementation may resume only after a separate, approved delivery creates manual canonical editing for `general`, `education`, and `training`, with section-specific existing edit authorization and org scope. That delivery must then invoke the F-A event/outbox append helper inside its successful canonical-write transaction.
